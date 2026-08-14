"""Prediction-horizon encounter intent compiled from one lifecycle snapshot."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

import numpy as np

from colav_simulator.core.tracking.trackers import TrackKey


class HorizonEncounterPhase(StrEnum):
    """One semantic phase at a prediction-grid state sample."""

    MISSION = "MISSION"
    ALTER = "ALTER"
    PASS = "PASS"
    RECOVER = "RECOVER"


@dataclass(frozen=True)
class TargetPrediction:
    """Immutable constant-velocity target prediction on the state grid."""

    key: TrackKey
    reference_time_s: float
    velocity_ne_mps: tuple[float, float]
    times_s: np.ndarray
    north_m: np.ndarray
    east_m: np.ndarray
    position_uncertainty_m: np.ndarray

    def __post_init__(self) -> None:
        """Copy prediction vectors into immutable arrays."""
        lengths: set[int] = set()
        for name in ("times_s", "north_m", "east_m", "position_uncertainty_m"):
            values = _immutable_vector(getattr(self, name), name)
            object.__setattr__(self, name, values)
            lengths.add(values.size)
        if len(lengths) != 1:
            raise ValueError("target prediction vectors must have equal length")
        velocity = tuple(float(value) for value in self.velocity_ne_mps)
        if len(velocity) != 2 or not np.isfinite(velocity).all():
            raise ValueError("target prediction velocity must be a finite pair")
        object.__setattr__(self, "velocity_ne_mps", velocity)
        if not math.isfinite(self.reference_time_s):
            raise ValueError("target prediction reference time must be finite")


@dataclass(frozen=True)
class HorizonTargetIntent:
    """Lifecycle facts required to project one target through the horizon."""

    key: TrackKey
    required_course_change_rad: float
    recovery_clearance_m: float
    action_achieved: bool
    route_recovery_allowed: bool
    prediction: TargetPrediction

    def __post_init__(self) -> None:
        """Validate the lifecycle-to-prediction binding."""
        if self.key != self.prediction.key:
            raise ValueError("target intent and prediction keys must match")
        if not math.isfinite(self.required_course_change_rad) or self.required_course_change_rad < 0.0:
            raise ValueError("required course change must be finite and non-negative")
        if not math.isfinite(self.recovery_clearance_m) or self.recovery_clearance_m <= 0.0:
            raise ValueError("recovery clearance must be finite and positive")


@dataclass(frozen=True)
class HorizonEncounterPlanRequest:
    """Immutable facts used by the horizon encounter compiler."""

    reference_time_s: float
    times_s: np.ndarray
    own_position_ne_m: tuple[float, float]
    mission_route_anchor_ne_m: tuple[float, float]
    own_heading_rad: float
    own_speed_mps: float
    mission_route_bearing_rad: float
    avoidance_corridor_bearing_rad: float
    rot_max_rad_s: float
    heading_window_rad: float
    targets: tuple[HorizonTargetIntent, ...]

    def __post_init__(self) -> None:
        """Normalize and validate the fixed state grid."""
        times = _immutable_vector(self.times_s, "times_s")
        if times.size < 2 or not math.isclose(float(times[0]), 0.0, abs_tol=1.0e-12):
            raise ValueError("horizon time grid must start at zero and contain at least two samples")
        increments = np.diff(times)
        if np.any(increments <= 0.0) or not np.allclose(increments, increments[0], atol=1.0e-12, rtol=0.0):
            raise ValueError("horizon time grid must be strictly increasing and uniform")
        position = tuple(float(value) for value in self.own_position_ne_m)
        route_anchor = tuple(float(value) for value in self.mission_route_anchor_ne_m)
        scalar_values = (
            self.reference_time_s,
            *position,
            *route_anchor,
            self.own_heading_rad,
            self.own_speed_mps,
            self.mission_route_bearing_rad,
            self.avoidance_corridor_bearing_rad,
            self.rot_max_rad_s,
            self.heading_window_rad,
        )
        if len(position) != 2 or len(route_anchor) != 2 or not np.isfinite(scalar_values).all():
            raise ValueError("horizon encounter request values must be finite")
        if self.own_speed_mps < 0.0 or self.rot_max_rad_s <= 0.0 or self.heading_window_rad <= 0.0:
            raise ValueError("speed and turn rate must be physically valid")
        targets = tuple(self.targets)
        if len({target.key for target in targets}) != len(targets):
            raise ValueError("horizon target intents must have unique keys")
        for target in targets:
            if target.prediction.times_s.shape != times.shape or not np.array_equal(target.prediction.times_s, times):
                raise ValueError("target predictions must use the horizon time grid")
            if not math.isclose(target.prediction.reference_time_s, self.reference_time_s, abs_tol=1.0e-9):
                raise ValueError("target prediction reference time must match the horizon request")
        object.__setattr__(self, "times_s", times)
        object.__setattr__(self, "own_position_ne_m", position)
        object.__setattr__(self, "mission_route_anchor_ne_m", route_anchor)
        object.__setattr__(self, "targets", targets)


@dataclass(frozen=True)
class TargetHorizonWindow:
    """Projected action and recovery indices for one target."""

    key: TrackKey
    action_complete_k: int
    recovery_from_k: int | None
    route_recovery_allowed_at_start: bool
    recovery_clearance_m: float
    minimum_predicted_route_dcpa_m: float


@dataclass(frozen=True)
class HorizonEncounterPlan:
    """Complete avoid-pass-recover semantics for one prediction horizon."""

    reference_time_s: float
    times_s: np.ndarray
    mission_route_bearing_rad: float
    avoidance_corridor_bearing_rad: float
    phases: tuple[HorizonEncounterPhase, ...]
    target_windows: tuple[TargetHorizonWindow, ...]
    recovery_from_k: int | None
    solver_consumed: bool = False

    def __post_init__(self) -> None:
        """Validate one phase per prediction state sample."""
        times = _immutable_vector(self.times_s, "times_s")
        phases = tuple(self.phases)
        windows = tuple(self.target_windows)
        if len(phases) != times.size:
            raise ValueError("one horizon phase is required per state sample")
        if not all(isinstance(phase, HorizonEncounterPhase) for phase in phases):
            raise TypeError("phases must contain HorizonEncounterPhase values")
        if self.recovery_from_k is not None and not 0 <= self.recovery_from_k < times.size:
            raise ValueError("recovery index must fall inside the horizon")
        object.__setattr__(self, "times_s", times)
        object.__setattr__(self, "phases", phases)
        object.__setattr__(self, "target_windows", windows)


def compile_horizon_encounter_plan(request: HorizonEncounterPlanRequest) -> HorizonEncounterPlan:
    """Project current lifecycle commitments into avoid-pass-recover phases."""
    if not request.targets:
        return _plan(request, (HorizonEncounterPhase.MISSION,) * request.times_s.size, (), 0)

    dt_s = float(request.times_s[1] - request.times_s[0])
    recovery_paths = _recovery_paths(
        request.times_s,
        own_heading_rad=request.own_heading_rad,
        own_speed_mps=request.own_speed_mps,
        mission_bearing_rad=request.mission_route_bearing_rad,
        corridor_bearing_rad=request.avoidance_corridor_bearing_rad,
        route_origin_ne_m=(
            request.mission_route_anchor_ne_m[0] - request.own_position_ne_m[0],
            request.mission_route_anchor_ne_m[1] - request.own_position_ne_m[1],
        ),
        rot_max_rad_s=request.rot_max_rad_s,
        heading_window_rad=request.heading_window_rad,
    )

    windows = tuple(
        _target_window(
            target,
            recovery_paths,
            own_position_ne_m=request.own_position_ne_m,
            action_step_rad=request.rot_max_rad_s * dt_s,
        )
        for target in request.targets
    )
    action_complete_k = max(window.action_complete_k for window in windows)
    recovery_indices = tuple(window.recovery_from_k for window in windows)
    recovery_from_k = None if any(index is None for index in recovery_indices) else max(recovery_indices)
    phases = [HorizonEncounterPhase.PASS] * request.times_s.size
    phases[:action_complete_k] = [HorizonEncounterPhase.ALTER] * action_complete_k
    if recovery_from_k is not None:
        phases[recovery_from_k:] = [HorizonEncounterPhase.RECOVER] * (len(phases) - recovery_from_k)
    return _plan(request, tuple(phases), windows, recovery_from_k)


def horizon_encounter_plan_document(plan: HorizonEncounterPlan) -> dict[str, object]:
    """Return JSON-safe evidence for hashing, replay, and diagnostics."""
    return {
        "schema_version": "colav.mid_mpc.horizon-encounter-plan@1",
        "reference_time_s": plan.reference_time_s,
        "times_s": plan.times_s.tolist(),
        "mission_route_bearing_rad": plan.mission_route_bearing_rad,
        "avoidance_corridor_bearing_rad": plan.avoidance_corridor_bearing_rad,
        "phases": [phase.value for phase in plan.phases],
        "recovery_from_k": plan.recovery_from_k,
        "solver_consumed": plan.solver_consumed,
        "target_windows": [
            {
                "key": {"target_id": window.key.target_id, "generation": window.key.generation},
                "action_complete_k": window.action_complete_k,
                "recovery_from_k": window.recovery_from_k,
                "route_recovery_allowed_at_start": window.route_recovery_allowed_at_start,
                "recovery_clearance_m": window.recovery_clearance_m,
                "minimum_predicted_route_dcpa_m": window.minimum_predicted_route_dcpa_m,
            }
            for window in plan.target_windows
        ],
    }


def _target_window(
    target: HorizonTargetIntent,
    recovery_paths: np.ndarray,
    *,
    own_position_ne_m: tuple[float, float],
    action_step_rad: float,
) -> TargetHorizonWindow:
    target_positions = np.column_stack((target.prediction.north_m, target.prediction.east_m))
    action_complete_k = 0 if target.action_achieved else math.ceil(target.required_course_change_rad / action_step_rad)
    if target.route_recovery_allowed:
        action_complete_k = 0
    action_complete_k = min(action_complete_k, target.prediction.times_s.size)
    absolute_own_paths = recovery_paths + np.asarray(own_position_ne_m, dtype=float)[None, None, :]
    relative = target_positions[None, :, :] - absolute_own_paths
    node_distance_m = np.linalg.norm(relative, axis=2)
    interval_start = relative[:, :-1, :]
    interval_delta = relative[:, 1:, :] - interval_start
    interval_delta_sq = np.sum(interval_delta * interval_delta, axis=2)
    projection = np.zeros_like(interval_delta_sq)
    moving = interval_delta_sq > 1.0e-12
    projection[moving] = -np.sum(interval_start * interval_delta, axis=2)[moving] / interval_delta_sq[moving]
    projection = np.clip(projection, 0.0, 1.0)
    swept_distance_m = np.linalg.norm(interval_start + projection[:, :, None] * interval_delta, axis=2)
    clearance_m = target.recovery_clearance_m + target.prediction.position_uncertainty_m
    node_safe = node_distance_m >= clearance_m[None, :]
    interval_clearance_m = np.maximum(clearance_m[:-1], clearance_m[1:])
    swept_safe = swept_distance_m >= interval_clearance_m[None, :]
    recovery_safe = np.zeros(recovery_paths.shape[0], dtype=bool)
    prediction_dt_s = float(target.prediction.times_s[1] - target.prediction.times_s[0])
    recovery_guard_intervals = max(1, math.ceil(15.0 / prediction_dt_s)) + 1
    for recovery_k in range(action_complete_k, recovery_paths.shape[0]):
        route_cpa_k = int(np.argmin(node_distance_m[recovery_k]))
        # Preserve 15 seconds plus one synchronization interval after nominal
        # CPA so reduced-order tracking cannot release before actual CPA.
        if recovery_k < route_cpa_k + recovery_guard_intervals:
            continue
        recovery_safe[recovery_k] = bool(
            np.all(node_safe[recovery_k, recovery_k:]) and np.all(swept_safe[recovery_k, recovery_k:])
        )
    safe_indices = np.flatnonzero(recovery_safe)
    recovery_from_k = int(safe_indices[0]) if safe_indices.size else None
    return TargetHorizonWindow(
        key=target.key,
        action_complete_k=action_complete_k,
        recovery_from_k=recovery_from_k,
        route_recovery_allowed_at_start=target.route_recovery_allowed,
        recovery_clearance_m=target.recovery_clearance_m,
        minimum_predicted_route_dcpa_m=float(np.min(node_distance_m)),
    )


def _recovery_paths(
    times_s: np.ndarray,
    *,
    own_heading_rad: float,
    own_speed_mps: float,
    mission_bearing_rad: float,
    corridor_bearing_rad: float,
    route_origin_ne_m: tuple[float, float],
    rot_max_rad_s: float,
    heading_window_rad: float,
) -> np.ndarray:
    """Precompute one rate-limited corridor-to-mission path per recovery knot."""
    dt_s = float(times_s[1] - times_s[0])
    step_count = times_s.size - 1
    paths = np.zeros((times_s.size, times_s.size, 2), dtype=float)
    mission_normal = np.array((-math.sin(mission_bearing_rad), math.cos(mission_bearing_rad)), dtype=float)
    maximum_recovery_delta = heading_window_rad
    maximum_heading_step = rot_max_rad_s * dt_s
    recovery_indices = np.arange(times_s.size)
    heading = np.full(times_s.size, own_heading_rad, dtype=float)
    for k in range(step_count):
        cross_track = (paths[:, k, :] - np.asarray(route_origin_ne_m, dtype=float)) @ mission_normal
        desired_heading = np.full(times_s.size, corridor_bearing_rad, dtype=float)
        recovering = k >= recovery_indices
        if own_speed_mps > 1.0e-9 and maximum_recovery_delta > 1.0e-9:
            lateral_velocity = np.clip(-cross_track / dt_s, -own_speed_mps, own_speed_mps)
            recovery_delta = np.clip(
                np.arcsin(lateral_velocity / own_speed_mps),
                -maximum_recovery_delta,
                maximum_recovery_delta,
            )
            desired_heading[recovering] = mission_bearing_rad + recovery_delta[recovering]
        else:
            desired_heading[recovering] = mission_bearing_rad
        desired_offset = np.arctan2(
            np.sin(desired_heading - own_heading_rad),
            np.cos(desired_heading - own_heading_rad),
        )
        desired_heading = own_heading_rad + np.clip(
            desired_offset,
            -heading_window_rad,
            heading_window_rad,
        )
        heading_delta = np.arctan2(np.sin(desired_heading - heading), np.cos(desired_heading - heading))
        heading += np.clip(heading_delta, -maximum_heading_step, maximum_heading_step)
        paths[:, k + 1, 0] = paths[:, k, 0] + own_speed_mps * dt_s * np.cos(heading)
        paths[:, k + 1, 1] = paths[:, k, 1] + own_speed_mps * dt_s * np.sin(heading)
    return paths


def _plan(
    request: HorizonEncounterPlanRequest,
    phases: tuple[HorizonEncounterPhase, ...],
    windows: tuple[TargetHorizonWindow, ...],
    recovery_from_k: int | None,
) -> HorizonEncounterPlan:
    return HorizonEncounterPlan(
        reference_time_s=request.reference_time_s,
        times_s=request.times_s,
        mission_route_bearing_rad=request.mission_route_bearing_rad,
        avoidance_corridor_bearing_rad=request.avoidance_corridor_bearing_rad,
        phases=phases,
        target_windows=windows,
        recovery_from_k=recovery_from_k,
    )


def _immutable_vector(values: np.ndarray, name: str) -> np.ndarray:
    vector = np.array(values, dtype=float, copy=True)
    if vector.ndim != 1 or not np.isfinite(vector).all():
        raise ValueError(f"{name} must be a finite vector")
    vector.setflags(write=False)
    return vector


def _wrap(angle: float) -> float:
    return math.atan2(math.sin(angle), math.cos(angle))
