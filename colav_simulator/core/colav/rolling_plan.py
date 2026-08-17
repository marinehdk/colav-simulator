"""Rolling-plan continuity authority for successive Mid-MPC solves."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

import numpy as np


class PlanRevisionReason(StrEnum):
    """Typed reason for preserving or revising the accepted Rolling Plan."""

    INITIAL_PLAN = "INITIAL_PLAN"
    CONTINUITY_PRESERVED = "CONTINUITY_PRESERVED"
    RESET = "RESET"
    MISSION_ROUTE_CHANGED = "MISSION_ROUTE_CHANGED"
    TARGET_GENERATION_CHANGED = "TARGET_GENERATION_CHANGED"
    CAPABILITY_CHANGED = "CAPABILITY_CHANGED"
    COLREG_AUTHORITY_CHANGED = "COLREG_AUTHORITY_CHANGED"
    PRIOR_PLAN_UNSAFE = "PRIOR_PLAN_UNSAFE"
    PREFIX_CONTINUITY_EXCEEDED = "PREFIX_CONTINUITY_EXCEEDED"
    PASSING_SIDE_CHANGED = "PASSING_SIDE_CHANGED"
    RECOVERY_TIME_CHANGED = "RECOVERY_TIME_CHANGED"


@dataclass(frozen=True)
class RollingPlanIdentity:
    """Facts whose change invalidates continuity authority."""

    route_hash: str
    target_keys: tuple[tuple[int, int], ...]
    capability_hash: str
    authority_hash: str


@dataclass(frozen=True)
class RollingPlanPolicy:
    """Fixed continuity bands and acceptance thresholds."""

    prefix_until_s: float = 30.0
    bounded_until_s: float = 120.0
    prefix_heading_rms_deg: float = 3.0
    prefix_heading_max_deg: float = 10.0
    prefix_position_max_m: float = 10.0
    bounded_heading_max_deg: float = 5.0
    bounded_position_max_m: float = 25.0
    advisory_heading_rms_deg: float = 5.0
    advisory_position_max_m: float = 150.0
    recovery_drift_max_s: float = 5.0
    prefix_objective_weight: float = 200.0
    bounded_objective_weight: float = 120.0
    advisory_objective_weight: float = 100.0


@dataclass(frozen=True)
class RollingPlanReference:
    """Absolute-time-aligned references packed into one fixed NLP graph."""

    active: bool
    revision_reason: PlanRevisionReason
    accepted_at_s: float | None
    current_time_s: float
    recovery_at_s: float | None
    heading_reference_rad: tuple[float, ...]
    speed_reference_mps: tuple[float, ...]
    objective_weight: tuple[float, ...]
    overlap_intervals: int


@dataclass(frozen=True)
class ContinuityBandMetrics:
    """Plan-to-plan change measured on one absolute-time band."""

    sample_count: int
    heading_rms_deg: float
    heading_max_deg: float
    position_max_m: float
    within_policy: bool


@dataclass(frozen=True)
class RollingPlanAssessment:
    """Mandatory prefix decision plus bounded/advisory continuity evidence."""

    accepted: bool
    revision_reason: PlanRevisionReason
    prior_plan_safe: bool
    passing_side_consistent: bool
    recovery_time_drift_s: float | None
    prefix: ContinuityBandMetrics
    bounded: ContinuityBandMetrics
    advisory: ContinuityBandMetrics


@dataclass(frozen=True)
class _AcceptedRollingPlan:
    accepted_at_s: float
    dt_s: float
    north_m: np.ndarray
    east_m: np.ndarray
    course_rad: np.ndarray
    speed_mps: np.ndarray
    identity: RollingPlanIdentity
    passing_side: str
    recovery_at_s: float | None


class RollingPlan:
    """Own accepted-plan alignment, revision authority, and continuity gates."""

    def __init__(self, policy: RollingPlanPolicy | None = None) -> None:
        self._policy = policy or RollingPlanPolicy()
        self._accepted: _AcceptedRollingPlan | None = None

    @property
    def has_accepted_plan(self) -> bool:
        return self._accepted is not None

    def reset(self) -> None:
        self._accepted = None

    def reference(
        self,
        *,
        current_time_s: float,
        horizon_steps: int,
        dt_s: float,
        identity: RollingPlanIdentity,
        prior_plan_safe: bool,
    ) -> RollingPlanReference:
        reason = self._revision_reason(current_time_s, identity, prior_plan_safe)
        active = reason is PlanRevisionReason.CONTINUITY_PRESERVED
        zeros = (0.0,) * horizon_steps
        if not active or self._accepted is None:
            return RollingPlanReference(
                active=False,
                revision_reason=reason,
                accepted_at_s=None if self._accepted is None else self._accepted.accepted_at_s,
                current_time_s=current_time_s,
                recovery_at_s=None if self._accepted is None else self._accepted.recovery_at_s,
                heading_reference_rad=zeros,
                speed_reference_mps=zeros,
                objective_weight=zeros,
                overlap_intervals=0,
            )

        accepted = self._accepted
        source_times = accepted.accepted_at_s + np.arange(accepted.course_rad.size, dtype=float) * accepted.dt_s
        query_times = current_time_s + (np.arange(horizon_steps, dtype=float) + 1.0) * dt_s
        overlap = query_times <= source_times[-1] + 1.0e-9
        headings = np.interp(query_times, source_times, np.unwrap(accepted.course_rad))
        speeds = np.interp(query_times, source_times, accepted.speed_mps)
        relative_s = query_times - current_time_s
        weights = np.select(
            [relative_s <= self._policy.prefix_until_s, relative_s <= self._policy.bounded_until_s],
            [self._policy.prefix_objective_weight, self._policy.bounded_objective_weight],
            default=self._policy.advisory_objective_weight,
        )
        weights[~overlap] = 0.0
        return RollingPlanReference(
            active=True,
            revision_reason=reason,
            accepted_at_s=accepted.accepted_at_s,
            current_time_s=current_time_s,
            recovery_at_s=accepted.recovery_at_s,
            heading_reference_rad=tuple(float(value) for value in headings),
            speed_reference_mps=tuple(float(value) for value in speeds),
            objective_weight=tuple(float(value) for value in weights),
            overlap_intervals=int(np.count_nonzero(overlap)),
        )

    def assess(
        self,
        reference: RollingPlanReference,
        *,
        north_m: np.ndarray,
        east_m: np.ndarray,
        course_rad: np.ndarray,
        passing_side: str,
        recovery_at_s: float | None,
        prior_plan_safe: bool,
    ) -> RollingPlanAssessment:
        empty = ContinuityBandMetrics(0, 0.0, 0.0, 0.0, True)
        if not reference.active or self._accepted is None:
            return RollingPlanAssessment(
                accepted=True,
                revision_reason=reference.revision_reason,
                prior_plan_safe=prior_plan_safe,
                passing_side_consistent=True,
                recovery_time_drift_s=None,
                prefix=empty,
                bounded=empty,
                advisory=empty,
            )

        accepted = self._accepted
        candidate_north = np.asarray(north_m, dtype=float)
        candidate_east = np.asarray(east_m, dtype=float)
        candidate_course = np.asarray(course_rad, dtype=float)
        if not (candidate_north.shape == candidate_east.shape == candidate_course.shape):
            raise ValueError("candidate Rolling Plan vectors must have equal shape")
        query_times = reference.current_time_s + np.arange(candidate_course.size, dtype=float) * accepted.dt_s
        source_times = accepted.accepted_at_s + np.arange(accepted.course_rad.size, dtype=float) * accepted.dt_s
        overlap = query_times <= source_times[-1] + 1.0e-9
        baseline_north = np.interp(query_times, source_times, accepted.north_m)
        baseline_east = np.interp(query_times, source_times, accepted.east_m)
        baseline_course = np.interp(query_times, source_times, np.unwrap(accepted.course_rad))
        baseline_north += candidate_north[0] - baseline_north[0]
        baseline_east += candidate_east[0] - baseline_east[0]
        heading_error_deg = np.degrees(
            np.abs(np.arctan2(np.sin(candidate_course - baseline_course), np.cos(candidate_course - baseline_course)))
        )
        position_error_m = np.hypot(candidate_north - baseline_north, candidate_east - baseline_east)
        relative_s = query_times - reference.current_time_s
        future = relative_s > 1.0e-9
        prefix = self._band_metrics(
            overlap & future & (relative_s <= self._policy.prefix_until_s + 1.0e-9),
            heading_error_deg,
            position_error_m,
            heading_rms_limit=self._policy.prefix_heading_rms_deg,
            heading_max_limit=self._policy.prefix_heading_max_deg,
            position_limit=self._policy.prefix_position_max_m,
        )
        bounded = self._band_metrics(
            overlap
            & (relative_s > self._policy.prefix_until_s + 1.0e-9)
            & (relative_s <= self._policy.bounded_until_s + 1.0e-9),
            heading_error_deg,
            position_error_m,
            heading_rms_limit=math.inf,
            heading_max_limit=self._policy.bounded_heading_max_deg,
            position_limit=self._policy.bounded_position_max_m,
        )
        advisory = self._band_metrics(
            overlap & (relative_s > self._policy.bounded_until_s + 1.0e-9),
            heading_error_deg,
            position_error_m,
            heading_rms_limit=self._policy.advisory_heading_rms_deg,
            heading_max_limit=math.inf,
            position_limit=self._policy.advisory_position_max_m,
        )
        passing_side_consistent = passing_side == accepted.passing_side
        recovery_drift = _optional_time_delta(recovery_at_s, accepted.recovery_at_s)
        recovery_consistent = recovery_drift is not None and recovery_drift <= self._policy.recovery_drift_max_s
        if recovery_at_s is None and accepted.recovery_at_s is None:
            recovery_consistent = True
            recovery_drift = None
        elif accepted.recovery_at_s is not None and reference.current_time_s >= accepted.recovery_at_s - 1.0e-9:
            recovery_complete = recovery_at_s is None or recovery_at_s <= reference.current_time_s + accepted.dt_s + 1.0e-9
            if recovery_complete:
                recovery_consistent = True
                recovery_drift = 0.0

        reason = PlanRevisionReason.CONTINUITY_PRESERVED
        if not passing_side_consistent:
            reason = PlanRevisionReason.PASSING_SIDE_CHANGED
        elif not recovery_consistent:
            reason = PlanRevisionReason.RECOVERY_TIME_CHANGED
        elif not prefix.within_policy:
            reason = PlanRevisionReason.PREFIX_CONTINUITY_EXCEEDED
        return RollingPlanAssessment(
            accepted=(passing_side_consistent and recovery_consistent and prefix.within_policy),
            revision_reason=reason,
            prior_plan_safe=prior_plan_safe,
            passing_side_consistent=passing_side_consistent,
            recovery_time_drift_s=recovery_drift,
            prefix=prefix,
            bounded=bounded,
            advisory=advisory,
        )

    def commit(
        self,
        *,
        accepted_at_s: float,
        dt_s: float,
        north_m: np.ndarray,
        east_m: np.ndarray,
        course_rad: np.ndarray,
        speed_mps: np.ndarray,
        identity: RollingPlanIdentity,
        passing_side: str,
        recovery_at_s: float | None,
    ) -> None:
        vectors = tuple(np.asarray(value, dtype=float).copy() for value in (north_m, east_m, course_rad, speed_mps))
        if len({value.shape for value in vectors}) != 1 or vectors[0].ndim != 1 or vectors[0].size < 2:
            raise ValueError("accepted Rolling Plan vectors must be equal one-dimensional state grids")
        for value in vectors:
            if not np.isfinite(value).all():
                raise ValueError("accepted Rolling Plan vectors must be finite")
            value.setflags(write=False)
        self._accepted = _AcceptedRollingPlan(
            accepted_at_s=float(accepted_at_s),
            dt_s=float(dt_s),
            north_m=vectors[0],
            east_m=vectors[1],
            course_rad=vectors[2],
            speed_mps=vectors[3],
            identity=identity,
            passing_side=passing_side,
            recovery_at_s=recovery_at_s,
        )

    def _revision_reason(
        self,
        current_time_s: float,
        identity: RollingPlanIdentity,
        prior_plan_safe: bool,
    ) -> PlanRevisionReason:
        accepted = self._accepted
        if accepted is None:
            return PlanRevisionReason.INITIAL_PLAN
        if current_time_s < accepted.accepted_at_s - 1.0e-9:
            return PlanRevisionReason.RESET
        if identity.route_hash != accepted.identity.route_hash:
            return PlanRevisionReason.MISSION_ROUTE_CHANGED
        if identity.target_keys != accepted.identity.target_keys:
            return PlanRevisionReason.TARGET_GENERATION_CHANGED
        if identity.capability_hash != accepted.identity.capability_hash:
            return PlanRevisionReason.CAPABILITY_CHANGED
        if identity.authority_hash != accepted.identity.authority_hash:
            return PlanRevisionReason.COLREG_AUTHORITY_CHANGED
        if not prior_plan_safe:
            return PlanRevisionReason.PRIOR_PLAN_UNSAFE
        return PlanRevisionReason.CONTINUITY_PRESERVED

    @staticmethod
    def _band_metrics(
        mask: np.ndarray,
        heading_error_deg: np.ndarray,
        position_error_m: np.ndarray,
        *,
        heading_rms_limit: float,
        heading_max_limit: float,
        position_limit: float,
    ) -> ContinuityBandMetrics:
        count = int(np.count_nonzero(mask))
        if count == 0:
            return ContinuityBandMetrics(0, 0.0, 0.0, 0.0, True)
        headings = heading_error_deg[mask]
        positions = position_error_m[mask]
        rms = float(np.sqrt(np.mean(np.square(headings))))
        maximum = float(np.max(headings))
        position = float(np.max(positions))
        return ContinuityBandMetrics(
            sample_count=count,
            heading_rms_deg=rms,
            heading_max_deg=maximum,
            position_max_m=position,
            within_policy=(rms <= heading_rms_limit and maximum <= heading_max_limit and position <= position_limit),
        )


def _optional_time_delta(left: float | None, right: float | None) -> float | None:
    if left is None or right is None:
        return None
    return abs(float(left) - float(right))
