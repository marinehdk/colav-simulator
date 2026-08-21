"""Independent five-domain comparison for Historical AIS benchmarks.

The comparator consumes sealed trajectories and an Independent Evaluator result.
It never changes the evaluator verdict and never exposes Human Similarity as a
safety or COLREG gate.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Any

COMPARE_SCHEMA_VERSION = "historical-benchmark-compare.v1"
ALIGNMENT_SCHEMA_VERSION = "historical-compare-alignment.v1"
SIMILARITY_METRIC_VERSION = "historical-similarity.v1"


class HistoricalCompareStatus(str, Enum):
    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"
    INVALID_REQUEST = "INVALID_REQUEST"


class HistoricalCompareDomainStatus(str, Enum):
    COMPLETE = "COMPLETE"
    NOT_AVAILABLE = "NOT_AVAILABLE"
    INCOMPLETE = "INCOMPLETE"


@dataclass(frozen=True)
class HistoricalBenchmarkAlignmentProfile:
    """Versioned absolute-time alignment policy; no time warping is allowed."""

    profile_id: str = ALIGNMENT_SCHEMA_VERSION
    metric_version: str = SIMILARITY_METRIC_VERSION
    sample_step_s: float = 1.0
    minimum_overlap_s: float = 0.0
    action_course_delta_rad: float = math.radians(5.0)
    action_speed_delta_mps: float = 0.5

    def __post_init__(self) -> None:
        """Validate the absolute-time alignment and action thresholds."""
        for name in (
            "sample_step_s",
            "minimum_overlap_s",
            "action_course_delta_rad",
            "action_speed_delta_mps",
        ):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value < 0.0 or (name == "sample_step_s" and value <= 0.0):
                raise ValueError(f"{name} must be finite and valid")
            object.__setattr__(self, name, value)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": ALIGNMENT_SCHEMA_VERSION,
            "profile_id": self.profile_id,
            "metric_version": self.metric_version,
            "sample_step_s": self.sample_step_s,
            "minimum_overlap_s": self.minimum_overlap_s,
            "action_course_delta_rad": self.action_course_delta_rad,
            "action_speed_delta_mps": self.action_speed_delta_mps,
        }

    @property
    def digest(self) -> str:
        return _sha256_json(self.to_dict())


@dataclass(frozen=True)
class HistoricalBenchmarkTrajectory:
    """One trajectory in a shared absolute simulation frame."""

    timestamps_s: tuple[float, ...]
    positions_xy: tuple[tuple[float, float], ...]
    courses_rad: tuple[float, ...] = ()
    speeds_mps: tuple[float, ...] = ()
    source: str = "UNKNOWN"
    trajectory_digest: str = ""

    def __post_init__(self) -> None:
        """Normalize and validate immutable trajectory samples."""
        timestamps = tuple(float(value) for value in self.timestamps_s)
        positions = tuple(tuple(float(item) for item in point) for point in self.positions_xy)
        if len(timestamps) != len(positions) or len(timestamps) < 2:
            raise ValueError("trajectory requires equal timestamps/positions with at least two samples")
        if any(not math.isfinite(value) for value in timestamps) or any(
            right <= left for left, right in zip(timestamps, timestamps[1:], strict=False)
        ):
            raise ValueError("trajectory timestamps must be finite and strictly increasing")
        if any(len(point) != 2 or not all(math.isfinite(value) for value in point) for point in positions):
            raise ValueError("trajectory positions must be finite xy pairs")
        courses = tuple(float(value) for value in self.courses_rad)
        speeds = tuple(float(value) for value in self.speeds_mps)
        if courses and len(courses) != len(timestamps):
            raise ValueError("courses_rad must match trajectory sample count")
        if speeds and len(speeds) != len(timestamps):
            raise ValueError("speeds_mps must match trajectory sample count")
        object.__setattr__(self, "timestamps_s", timestamps)
        object.__setattr__(self, "positions_xy", positions)
        object.__setattr__(self, "courses_rad", courses)
        object.__setattr__(self, "speeds_mps", speeds)
        if not self.trajectory_digest:
            object.__setattr__(self, "trajectory_digest", _sha256_json(self._identity_dict()))

    @property
    def start_s(self) -> float:
        return self.timestamps_s[0]

    @property
    def end_s(self) -> float:
        return self.timestamps_s[-1]

    def _identity_dict(self) -> dict[str, Any]:
        return {
            "timestamps_s": list(self.timestamps_s),
            "positions_xy": [list(point) for point in self.positions_xy],
            "courses_rad": list(self.courses_rad),
            "speeds_mps": list(self.speeds_mps),
            "source": self.source,
        }

    def to_dict(self) -> dict[str, Any]:
        result = self._identity_dict()
        result["trajectory_digest"] = self.trajectory_digest
        return result

    @classmethod
    def from_session_frames(
        cls, frames: Sequence[Mapping[str, Any]], *, ship_key: str = "Ship0", source: str
    ) -> HistoricalBenchmarkTrajectory:
        """Project one realized session trajectory without re-evaluating safety."""
        timestamps: list[float] = []
        positions: list[tuple[float, float]] = []
        courses: list[float] = []
        speeds: list[float] = []
        for frame in frames:
            ship = frame.get(ship_key)
            if not isinstance(ship, Mapping) or not ship:
                continue
            state = ship.get("csog_state")
            if state is None or len(state) < 4:
                continue
            timestamp = float(ship.get("timestamp", frame.get("timestamp", len(timestamps))))
            values = tuple(float(state[index]) for index in range(4))
            if not math.isfinite(timestamp) or not all(math.isfinite(value) for value in values):
                continue
            if timestamps and timestamp <= timestamps[-1]:
                continue
            timestamps.append(timestamp)
            positions.append((values[0], values[1]))
            speeds.append(values[2])
            courses.append(values[3])
        return cls(tuple(timestamps), tuple(positions), tuple(courses), tuple(speeds), source=source)


@dataclass(frozen=True)
class HistoricalBenchmarkCompareRequest:
    """Inputs for the public ``compare`` seam."""

    case_digest: str
    dataset_digest: str
    t0_s: float
    counterfactual: HistoricalBenchmarkTrajectory
    human_reference: HistoricalBenchmarkTrajectory | None
    evaluation: Any | None
    nominal_intent: HistoricalBenchmarkTrajectory | None = None
    threat_evidence: Mapping[str, Any] | None = None
    run_id: str | None = None
    alignment_profile: HistoricalBenchmarkAlignmentProfile = field(default_factory=HistoricalBenchmarkAlignmentProfile)
    evaluation_digest: str | None = None

    def __post_init__(self) -> None:
        """Validate the compare frame and freeze optional evidence mappings."""
        t0 = float(self.t0_s)
        if not math.isfinite(t0) or t0 < 0.0:
            raise ValueError("t0_s must be finite and non-negative")
        object.__setattr__(self, "t0_s", t0)
        if not isinstance(self.counterfactual, HistoricalBenchmarkTrajectory):
            raise TypeError("counterfactual must be HistoricalBenchmarkTrajectory")
        if self.human_reference is not None and not isinstance(self.human_reference, HistoricalBenchmarkTrajectory):
            raise TypeError("human_reference must be HistoricalBenchmarkTrajectory")
        if self.threat_evidence is not None:
            object.__setattr__(self, "threat_evidence", MappingProxyType(dict(self.threat_evidence)))

    @classmethod
    def from_counterfactual_run(
        cls,
        case: Any,
        result: Any,
        *,
        human_reference: HistoricalBenchmarkTrajectory | None = None,
        threat_evidence: Mapping[str, Any] | None = None,
    ) -> HistoricalBenchmarkCompareRequest:
        """Bind an existing Counterfactual Run and Independent Evaluator result."""
        manifest = result.manifest
        return cls(
            case_digest=str(getattr(manifest, "historical_case_digest", None) or case.case_digest),
            dataset_digest=str(case.dataset_digest),
            t0_s=float(case.t0_candidate.time_s),
            counterfactual=HistoricalBenchmarkTrajectory.from_session_frames(
                result.session.frames,
                source="COUNTERFACTUAL_REALIZED",
            ),
            human_reference=human_reference,
            evaluation=result.evaluation,
            threat_evidence=threat_evidence,
            run_id=str(getattr(manifest, "run_id", "")),
        )


@dataclass(frozen=True)
class HistoricalSafetyComparison:
    status: HistoricalCompareDomainStatus
    independent_verdict: str | None
    collision_count: int | None = None
    grounding_count: int | None = None
    minimum_realized_clearance_m: float | None = None
    evaluator_evidence: Mapping[str, Any] = field(default_factory=dict)
    threat_projection_evidence: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _dataclass_dict(self)


@dataclass(frozen=True)
class HistoricalCOLREGComparison:
    status: HistoricalCompareDomainStatus
    independent_verdict: str | None
    evaluator_profile_id: str | None = None
    checked_rule_ids: tuple[str, ...] = ()
    evaluator_evidence: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _dataclass_dict(self)


@dataclass(frozen=True)
class HistoricalManeuverComparison:
    status: HistoricalCompareDomainStatus
    human_action_onset_s: float | None
    counterfactual_action_onset_s: float | None
    action_onset_delta_s: float | None
    human_course_change_rad: float | None
    counterfactual_course_change_rad: float | None
    human_speed_change_mps: float | None
    counterfactual_speed_change_mps: float | None
    cpa_time_s: float | None = None
    clear_time_s: float | None = None
    recovery_time_s: float | None = None
    unavailable_fields: tuple[str, ...] = ()
    evidence: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _dataclass_dict(self)


@dataclass(frozen=True)
class HistoricalEfficiencyComparison:
    status: HistoricalCompareDomainStatus
    human_path_length_m: float | None
    counterfactual_path_length_m: float | None
    path_length_delta_m: float | None
    human_duration_s: float | None
    counterfactual_duration_s: float | None
    duration_delta_s: float | None
    route_deviation_m: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return _dataclass_dict(self)


@dataclass(frozen=True)
class HistoricalHumanSimilarityComparison:
    status: HistoricalCompareDomainStatus
    advisory: bool = True
    metric_version: str = SIMILARITY_METRIC_VERSION
    alignment_profile_digest: str = ""
    alignment_start_s: float | None = None
    alignment_end_s: float | None = None
    sample_count: int = 0
    position_rmse_m: float | None = None
    position_mean_error_m: float | None = None
    position_max_error_m: float | None = None
    discrete_frechet_m: float | None = None
    unavailable_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _dataclass_dict(self)


@dataclass(frozen=True)
class HistoricalBenchmarkCompareDomains:
    safety: HistoricalSafetyComparison
    colreg: HistoricalCOLREGComparison
    maneuver: HistoricalManeuverComparison
    efficiency: HistoricalEfficiencyComparison
    human_similarity: HistoricalHumanSimilarityComparison

    def to_dict(self) -> dict[str, Any]:
        return {
            "safety": self.safety.to_dict(),
            "colreg": self.colreg.to_dict(),
            "maneuver": self.maneuver.to_dict(),
            "efficiency": self.efficiency.to_dict(),
            "human_similarity": self.human_similarity.to_dict(),
        }


@dataclass(frozen=True)
class HistoricalBenchmarkCompareOutcome:
    status: HistoricalCompareStatus
    domains: HistoricalBenchmarkCompareDomains
    overall_assurance_verdict: str | None
    lineage: Mapping[str, Any]
    compare_digest: str
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": COMPARE_SCHEMA_VERSION,
            "status": self.status.value,
            "message": self.message,
            "overall_assurance_verdict": self.overall_assurance_verdict,
            "lineage": _jsonable(dict(self.lineage)),
            "domains": self.domains.to_dict(),
            "compare_digest": self.compare_digest,
        }


class HistoricalBenchmarkComparator:
    """Build deterministic independent-domain comparison evidence."""

    def compare(self, request: HistoricalBenchmarkCompareRequest) -> HistoricalBenchmarkCompareOutcome:
        if not isinstance(request, HistoricalBenchmarkCompareRequest):
            domains = _unavailable_domains("INVALID_REQUEST")
            return self._outcome(HistoricalCompareStatus.INVALID_REQUEST, domains, None, {}, "invalid request")
        safety = self._safety(request)
        colreg = self._colreg(request)
        maneuver = self._maneuver(request)
        efficiency = self._efficiency(request)
        similarity = self._similarity(request)
        domains = HistoricalBenchmarkCompareDomains(safety, colreg, maneuver, efficiency, similarity)
        complete = all(
            domain.status is HistoricalCompareDomainStatus.COMPLETE
            for domain in (safety, colreg, maneuver, efficiency, similarity)
        )
        status = HistoricalCompareStatus.COMPLETE if complete else HistoricalCompareStatus.INCOMPLETE
        verdict = safety.independent_verdict or colreg.independent_verdict
        return self._outcome(status, domains, verdict, self._lineage(request), "")

    @staticmethod
    def _safety(request: HistoricalBenchmarkCompareRequest) -> HistoricalSafetyComparison:
        evaluation = request.evaluation
        if evaluation is None:
            return HistoricalSafetyComparison(
                status=HistoricalCompareDomainStatus.NOT_AVAILABLE,
                independent_verdict=None,
                threat_projection_evidence=request.threat_evidence or {},
            )
        aggregate = dict(getattr(evaluation, "aggregate", {}) or {})
        pairs = list(getattr(evaluation, "pair_results", []) or [])
        clearance = [float(item.minimum_hull_clearance_m) for item in pairs if item.minimum_hull_clearance_m is not None]
        evaluator_evidence = {
            "evaluator_id": getattr(evaluation, "evaluator_id", None),
            "evaluator_profile_id": getattr(evaluation, "evaluator_profile_id", None),
            "evaluation_status": getattr(evaluation, "evaluation_status", None),
            "hard_gate": _enum_value(getattr(getattr(evaluation, "hard_gate", None), "outcome", None)),
            "pair_evidence": [
                {
                    "ownship_id": getattr(item, "ownship_id", None),
                    "target_id": getattr(item, "target_id", None),
                    "initial_cpa": getattr(item, "initial_cpa", None),
                    "actual_cpa": getattr(item, "actual_cpa", None),
                    "minimum_hull_clearance_m": getattr(item, "minimum_hull_clearance_m", None),
                }
                for item in pairs
            ],
        }
        evaluation_status = getattr(evaluation, "evaluation_status", None)
        return HistoricalSafetyComparison(
            status=(
                HistoricalCompareDomainStatus.COMPLETE
                if evaluation_status in (None, "COMPLETE")
                else HistoricalCompareDomainStatus.INCOMPLETE
            ),
            independent_verdict=evaluator_evidence["hard_gate"],
            collision_count=_int_or_none(aggregate.get("collision_count")),
            grounding_count=_int_or_none(aggregate.get("grounding_count")),
            minimum_realized_clearance_m=(
                min(clearance) if clearance else aggregate.get("minimum_clearance_m", aggregate.get("minimum_distance_m"))
            ),
            evaluator_evidence=evaluator_evidence,
            threat_projection_evidence=request.threat_evidence or {},
        )

    @staticmethod
    def _colreg(request: HistoricalBenchmarkCompareRequest) -> HistoricalCOLREGComparison:
        evaluation = request.evaluation
        if evaluation is None:
            return HistoricalCOLREGComparison(HistoricalCompareDomainStatus.NOT_AVAILABLE, None)
        checks = list(getattr(getattr(evaluation, "hard_gate", None), "checks", []) or [])
        rule_ids = tuple(
            sorted(
                {
                    str(getattr(check, "check_id", ""))
                    for check in checks
                    if any(token in str(getattr(check, "check_id", "")).lower() for token in ("colreg", "rule"))
                }
            )
        )
        rule_outcomes = [
            _enum_value(getattr(check, "outcome", None)) for check in checks if getattr(check, "check_id", None) in rule_ids
        ]
        verdict = (
            "FAIL"
            if "FAIL" in rule_outcomes
            else (
                "PASS"
                if rule_outcomes and all(item == "PASS" for item in rule_outcomes)
                else _enum_value(getattr(getattr(evaluation, "hard_gate", None), "outcome", None))
            )
        )
        pair_results = list(getattr(evaluation, "pair_results", []) or [])
        evaluation_status = getattr(evaluation, "evaluation_status", None)
        return HistoricalCOLREGComparison(
            status=(
                HistoricalCompareDomainStatus.COMPLETE
                if evaluation_status in (None, "COMPLETE")
                else HistoricalCompareDomainStatus.INCOMPLETE
            ),
            independent_verdict=verdict,
            evaluator_profile_id=getattr(evaluation, "evaluator_profile_id", None),
            checked_rule_ids=rule_ids,
            evaluator_evidence={
                "source": "INDEPENDENT_EVALUATOR",
                "check_count": len(checks),
                "pair_count": len(pair_results),
                "fsm_transition_count": sum(len(getattr(item, "fsm_transitions", ())) for item in pair_results),
            },
        )

    def _maneuver(self, request: HistoricalBenchmarkCompareRequest) -> HistoricalManeuverComparison:
        human = request.human_reference
        if human is None:
            return HistoricalManeuverComparison(
                HistoricalCompareDomainStatus.NOT_AVAILABLE, None, None, None, None, None, None, None
            )
        human_action = _action_onset(human, request.t0_s, request.alignment_profile)
        cf_action = _action_onset(request.counterfactual, request.t0_s, request.alignment_profile)
        status = (
            HistoricalCompareDomainStatus.COMPLETE
            if human.courses_rad
            and human.speeds_mps
            and request.counterfactual.courses_rad
            and request.counterfactual.speeds_mps
            else HistoricalCompareDomainStatus.INCOMPLETE
        )
        return HistoricalManeuverComparison(
            status=status,
            human_action_onset_s=human_action[0] if human_action else None,
            counterfactual_action_onset_s=cf_action[0] if cf_action else None,
            action_onset_delta_s=(cf_action[0] - human_action[0]) if human_action and cf_action else None,
            human_course_change_rad=human_action[1] if human_action else None,
            counterfactual_course_change_rad=cf_action[1] if cf_action else None,
            human_speed_change_mps=human_action[2] if human_action else None,
            counterfactual_speed_change_mps=cf_action[2] if cf_action else None,
            cpa_time_s=_evaluator_cpa_time(request.evaluation),
            unavailable_fields=("clear_time_s", "recovery_time_s"),
            evidence={"source": "trajectory_and_independent_evaluator"},
        )

    def _efficiency(self, request: HistoricalBenchmarkCompareRequest) -> HistoricalEfficiencyComparison:
        start = request.t0_s
        human = request.human_reference
        cf = request.counterfactual
        human_path = _path_length_after(human, start) if human is not None else None
        cf_path = _path_length_after(cf, start)
        human_duration = (human.end_s - start) if human is not None and human.end_s >= start else None
        cf_duration = cf.end_s - start if cf.end_s >= start else None
        status = (
            HistoricalCompareDomainStatus.COMPLETE
            if human_path is not None and cf_path is not None
            else HistoricalCompareDomainStatus.NOT_AVAILABLE
        )
        return HistoricalEfficiencyComparison(
            status=status,
            human_path_length_m=human_path,
            counterfactual_path_length_m=cf_path,
            path_length_delta_m=(cf_path - human_path) if human_path is not None and cf_path is not None else None,
            human_duration_s=human_duration,
            counterfactual_duration_s=cf_duration,
            duration_delta_s=(cf_duration - human_duration)
            if human_duration is not None and cf_duration is not None
            else None,
        )

    @staticmethod
    def _similarity(request: HistoricalBenchmarkCompareRequest) -> HistoricalHumanSimilarityComparison:
        profile = request.alignment_profile
        if request.human_reference is None:
            return HistoricalHumanSimilarityComparison(
                status=HistoricalCompareDomainStatus.NOT_AVAILABLE,
                alignment_profile_digest=profile.digest,
                unavailable_reason="HUMAN_REFERENCE_NOT_AVAILABLE",
            )
        aligned = _aligned_positions(request.human_reference, request.counterfactual, request.t0_s, profile)
        if aligned is None:
            return HistoricalHumanSimilarityComparison(
                status=HistoricalCompareDomainStatus.INCOMPLETE,
                alignment_profile_digest=profile.digest,
                unavailable_reason="INSUFFICIENT_ABSOLUTE_TIME_OVERLAP",
            )
        times, human_points, cf_points = aligned
        errors = [_distance(left, right) for left, right in zip(human_points, cf_points, strict=True)]
        return HistoricalHumanSimilarityComparison(
            status=HistoricalCompareDomainStatus.COMPLETE,
            alignment_profile_digest=profile.digest,
            alignment_start_s=times[0],
            alignment_end_s=times[-1],
            sample_count=len(times),
            position_rmse_m=math.sqrt(sum(error * error for error in errors) / len(errors)),
            position_mean_error_m=sum(errors) / len(errors),
            position_max_error_m=max(errors),
            discrete_frechet_m=_discrete_frechet(human_points, cf_points),
        )

    @staticmethod
    def _lineage(request: HistoricalBenchmarkCompareRequest) -> dict[str, Any]:
        return {
            "dataset_digest": request.dataset_digest,
            "case_digest": request.case_digest,
            "counterfactual_trajectory_digest": request.counterfactual.trajectory_digest,
            "human_reference_digest": request.human_reference.trajectory_digest if request.human_reference else None,
            "run_id": request.run_id,
            "t0_s": request.t0_s,
            "alignment_profile_digest": request.alignment_profile.digest,
            "evaluation_digest": request.evaluation_digest or _evaluation_digest(request.evaluation),
            "comparison_contract": COMPARE_SCHEMA_VERSION,
        }

    @classmethod
    def _outcome(
        cls,
        status: HistoricalCompareStatus,
        domains: HistoricalBenchmarkCompareDomains,
        verdict: str | None,
        lineage: Mapping[str, Any],
        message: str,
    ) -> HistoricalBenchmarkCompareOutcome:
        identity = {
            "status": status.value,
            "domains": domains.to_dict(),
            "overall_assurance_verdict": verdict,
            "lineage": dict(lineage),
            "message": message,
        }
        return HistoricalBenchmarkCompareOutcome(
            status=status,
            domains=domains,
            overall_assurance_verdict=verdict,
            lineage=MappingProxyType(dict(lineage)),
            compare_digest=_sha256_json(identity),
            message=message,
        )


def _unavailable_domains(reason: str) -> HistoricalBenchmarkCompareDomains:
    return HistoricalBenchmarkCompareDomains(
        HistoricalSafetyComparison(HistoricalCompareDomainStatus.NOT_AVAILABLE, None),
        HistoricalCOLREGComparison(HistoricalCompareDomainStatus.NOT_AVAILABLE, None),
        HistoricalManeuverComparison(HistoricalCompareDomainStatus.NOT_AVAILABLE, None, None, None, None, None, None, None),
        HistoricalEfficiencyComparison(HistoricalCompareDomainStatus.NOT_AVAILABLE, None, None, None, None, None, None),
        HistoricalHumanSimilarityComparison(HistoricalCompareDomainStatus.NOT_AVAILABLE, unavailable_reason=reason),
    )


def _action_onset(
    trajectory: HistoricalBenchmarkTrajectory, t0_s: float, profile: HistoricalBenchmarkAlignmentProfile
) -> tuple[float, float, float] | None:
    if not trajectory.courses_rad or not trajectory.speeds_mps:
        return None
    before = [index for index, timestamp in enumerate(trajectory.timestamps_s) if timestamp < t0_s]
    after = [index for index, timestamp in enumerate(trajectory.timestamps_s) if timestamp >= t0_s]
    if not before or not after:
        return None
    baseline_course = trajectory.courses_rad[before[-1]]
    baseline_speed = trajectory.speeds_mps[before[-1]]
    for index in after:
        course_delta = abs(_angle_delta(trajectory.courses_rad[index], baseline_course))
        speed_delta = abs(trajectory.speeds_mps[index] - baseline_speed)
        if course_delta >= profile.action_course_delta_rad or speed_delta >= profile.action_speed_delta_mps:
            return trajectory.timestamps_s[index], course_delta, speed_delta
    return None


def _path_length_after(trajectory: HistoricalBenchmarkTrajectory | None, start_s: float) -> float | None:
    if trajectory is None:
        return None
    points = [
        point
        for timestamp, point in zip(trajectory.timestamps_s, trajectory.positions_xy, strict=True)
        if timestamp >= start_s
    ]
    if len(points) < 2:
        return None
    return sum(_distance(left, right) for left, right in zip(points, points[1:], strict=False))


def _aligned_positions(
    human: HistoricalBenchmarkTrajectory,
    counterfactual: HistoricalBenchmarkTrajectory,
    t0_s: float,
    profile: HistoricalBenchmarkAlignmentProfile,
) -> tuple[list[float], list[tuple[float, float]], list[tuple[float, float]]] | None:
    start = max(t0_s, human.start_s, counterfactual.start_s)
    end = min(human.end_s, counterfactual.end_s)
    if end - start < profile.minimum_overlap_s or end < start:
        return None
    times: list[float] = []
    cursor = start
    while cursor <= end + 1e-9:
        times.append(min(cursor, end))
        cursor += profile.sample_step_s
    if len(times) < 2:
        return None
    human_points = [_interpolate(human, time_s) for time_s in times]
    cf_points = [_interpolate(counterfactual, time_s) for time_s in times]
    if any(point is None for point in (*human_points, *cf_points)):
        return None
    return times, [point for point in human_points if point is not None], [point for point in cf_points if point is not None]


def _interpolate(trajectory: HistoricalBenchmarkTrajectory, time_s: float) -> tuple[float, float] | None:
    if time_s < trajectory.start_s or time_s > trajectory.end_s:
        return None
    for index, timestamp in enumerate(trajectory.timestamps_s):
        if math.isclose(timestamp, time_s, abs_tol=1e-9):
            return trajectory.positions_xy[index]
        if timestamp > time_s and index > 0:
            left_time = trajectory.timestamps_s[index - 1]
            fraction = (time_s - left_time) / (timestamp - left_time)
            left = trajectory.positions_xy[index - 1]
            right = trajectory.positions_xy[index]
            return (left[0] + fraction * (right[0] - left[0]), left[1] + fraction * (right[1] - left[1]))
    return trajectory.positions_xy[-1]


def _discrete_frechet(first: Sequence[tuple[float, float]], second: Sequence[tuple[float, float]]) -> float:
    dynamic = [[0.0 for _ in second] for _ in first]
    for i in range(len(first)):
        for j in range(len(second)):
            distance = _distance(first[i], second[j])
            if i == 0 and j == 0:
                dynamic[i][j] = distance
            elif i == 0:
                dynamic[i][j] = max(dynamic[i][j - 1], distance)
            elif j == 0:
                dynamic[i][j] = max(dynamic[i - 1][j], distance)
            else:
                dynamic[i][j] = max(min(dynamic[i - 1][j], dynamic[i - 1][j - 1], dynamic[i][j - 1]), distance)
    return dynamic[-1][-1]


def _evaluator_cpa_time(evaluation: Any | None) -> float | None:
    if evaluation is None:
        return None
    values = [float(item.cpa_time_s) for item in getattr(evaluation, "pair_results", []) if item.cpa_time_s is not None]
    return min(values) if values else None


def _evaluation_digest(evaluation: Any | None) -> str | None:
    if evaluation is None:
        return None
    return _sha256_json(
        {
            "evaluator_id": getattr(evaluation, "evaluator_id", None),
            "evaluator_profile_hash": getattr(evaluation, "evaluator_profile_hash", None),
            "evaluation_status": getattr(evaluation, "evaluation_status", None),
            "hard_gate": _enum_value(getattr(getattr(evaluation, "hard_gate", None), "outcome", None)),
        }
    )


def _distance(first: tuple[float, float], second: tuple[float, float]) -> float:
    return math.hypot(first[0] - second[0], first[1] - second[1])


def _angle_delta(first: float, second: float) -> float:
    return (first - second + math.pi) % (2.0 * math.pi) - math.pi


def _enum_value(value: Any) -> Any:
    return getattr(value, "value", value)


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _dataclass_dict(value: Any) -> dict[str, Any]:
    output = {}
    for name in value.__dataclass_fields__:
        output[name] = _jsonable(getattr(value, name))
    return output


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(json.dumps(_jsonable(value), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (datetime,)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if hasattr(value, "to_dict"):
        return _jsonable(value.to_dict())
    return str(value)


__all__ = [
    "ALIGNMENT_SCHEMA_VERSION",
    "COMPARE_SCHEMA_VERSION",
    "HistoricalBenchmarkAlignmentProfile",
    "HistoricalBenchmarkComparator",
    "HistoricalBenchmarkCompareDomains",
    "HistoricalBenchmarkCompareOutcome",
    "HistoricalBenchmarkCompareRequest",
    "HistoricalBenchmarkTrajectory",
    "HistoricalCOLREGComparison",
    "HistoricalCompareDomainStatus",
    "HistoricalCompareStatus",
    "HistoricalEfficiencyComparison",
    "HistoricalHumanSimilarityComparison",
    "HistoricalManeuverComparison",
    "HistoricalSafetyComparison",
]
