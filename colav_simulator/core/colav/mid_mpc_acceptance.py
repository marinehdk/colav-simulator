"""Deterministic pre-dispatch acceptance for Mid-MPC plans."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any

import numpy as np

from colav_simulator.core.tracking.trackers import TrackKey

REQUEST_SCHEMA = "colav.mid_mpc.acceptance.request@1"
RESULT_SCHEMA = "colav.mid_mpc.acceptance.result@1"


class AcceptanceMode(StrEnum):
    FRESH_CANDIDATE = "FRESH_CANDIDATE"
    HELD_ACCEPTED_PLAN = "HELD_ACCEPTED_PLAN"


class AcceptanceProfile(StrEnum):
    MASS_PARITY = "MASS_PARITY"
    COLAV_STRICT = "COLAV_STRICT"


class AcceptanceLayer(StrEnum):
    INTEGRITY = "integrity"
    NUMERICAL = "numerical"
    SAFETY = "safety"
    COLREG = "COLREG"
    TRACKABILITY = "trackability"
    QUALITY = "quality"
    EVIDENCE = "evidence"


class AcceptanceOutcome(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "N/A"
    NOT_EVALUATED = "NOT_EVALUATED"


@dataclass(frozen=True)
class NumericalEvidence:
    normalized_status: str
    return_status: str
    objective_total: float
    raw_f: float
    raw_x: np.ndarray
    raw_g: np.ndarray
    lbx: np.ndarray
    ubx: np.ndarray
    lbg: np.ndarray
    ubg: np.ndarray
    heading_count: int
    speed_count: int
    cpa_row_indices: tuple[int, ...]
    strict_slack_bounds: bool
    cpa_slack: float
    direction_slack: float
    preparation_profile: str
    preparation_hash: str
    solver_hash: str
    preparation_parent_problem_hash: str = ""
    solver_parent_preparation_hash: str = ""
    same_point_multipliers_available: bool = False

    def __post_init__(self) -> None:
        """Freeze and validate raw numerical evidence."""
        for name in ("raw_x", "raw_g", "lbx", "ubx", "lbg", "ubg"):
            object.__setattr__(self, name, _readonly_vector(getattr(self, name), name))
        if self.raw_x.shape != self.lbx.shape or self.raw_x.shape != self.ubx.shape:
            raise ValueError("raw decision and decision bounds must align")
        if self.raw_g.shape != self.lbg.shape or self.raw_g.shape != self.ubg.shape:
            raise ValueError("raw constraints and constraint bounds must align")
        if self.heading_count < 0 or self.speed_count < 0:
            raise ValueError("decision counts must be non-negative")
        if self.heading_count + self.speed_count + 2 > self.raw_x.size:
            raise ValueError("decision counts exceed raw decision vector")
        cpa_rows = tuple(int(index) for index in self.cpa_row_indices)
        if any(index < 0 or index >= self.raw_g.size for index in cpa_rows):
            raise ValueError("CPA row index is outside raw constraint vector")
        object.__setattr__(self, "cpa_row_indices", cpa_rows)


@dataclass(frozen=True)
class CandidateEvidence:
    profile: AcceptanceProfile
    times_s: np.ndarray
    north_m: np.ndarray
    east_m: np.ndarray
    course_rad: np.ndarray
    speed_mps: np.ndarray
    numerical: NumericalEvidence
    parent_problem_hash: str

    def __post_init__(self) -> None:
        """Freeze and validate candidate state vectors."""
        object.__setattr__(self, "profile", AcceptanceProfile(self.profile))
        sizes = set()
        for name in ("times_s", "north_m", "east_m", "course_rad", "speed_mps"):
            value = _readonly_vector(getattr(self, name), name)
            object.__setattr__(self, name, value)
            sizes.add(value.size)
        if len(sizes) != 1:
            raise ValueError("candidate state vectors must have equal length")


@dataclass(frozen=True)
class AuthorityTarget:
    key: TrackKey
    encounter: str
    role: str
    risk: str
    commitment: str
    passing_side: str
    baseline_course_rad: float | None
    required_course_change_rad: float
    action_achieved: bool
    route_recovery_allowed: bool
    reachability_verified: bool
    committed_at_s: float | None = None
    action_start_deadline_s: float | None = None
    action_achievement_deadline_s: float | None = None
    actual_course_change_rad: float | None = None


@dataclass(frozen=True)
class AuthorityEvidence:
    epoch: str
    sequence: int
    sim_time_s: float
    profile_hash: str
    targets: tuple[AuthorityTarget, ...] = ()

    def __post_init__(self) -> None:
        """Freeze authority targets."""
        object.__setattr__(self, "targets", tuple(self.targets))


@dataclass(frozen=True)
class ExecutionTarget:
    key: TrackKey
    length_m: float
    width_m: float
    north_m: np.ndarray
    east_m: np.ndarray
    uncertainty_m: np.ndarray

    def __post_init__(self) -> None:
        """Freeze and validate one target prediction."""
        sizes = set()
        for name in ("north_m", "east_m", "uncertainty_m"):
            value = _readonly_vector(getattr(self, name), name)
            object.__setattr__(self, name, value)
            sizes.add(value.size)
        if len(sizes) != 1:
            raise ValueError("execution target vectors must have equal length")
        if not math.isfinite(self.length_m) or not math.isfinite(self.width_m) or min(self.length_m, self.width_m) <= 0:
            raise ValueError("execution target geometry must be finite and positive")
        if np.any(self.uncertainty_m < 0.0):
            raise ValueError("target uncertainty must be non-negative")


@dataclass(frozen=True)
class PlantCapabilityEvidence:
    plant: str
    controller: str
    valid_at_s: float
    heading_window_rad: float
    speed_bounds_mps: tuple[float, float]
    rot_max_rad_s: float
    accel_max_mps2: float
    decel_max_mps2: float
    exact_tuple: str
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Validate exact active plant/controller capability."""
        if not self.plant or not self.controller or not self.exact_tuple:
            raise ValueError("capability identity and exact tuple are required")
        values = (
            self.valid_at_s,
            self.heading_window_rad,
            *self.speed_bounds_mps,
            self.rot_max_rad_s,
            self.accel_max_mps2,
            self.decel_max_mps2,
        )
        if not np.isfinite(values).all() or min(values) < 0.0:
            raise ValueError("capability values must be finite and non-negative")
        if self.speed_bounds_mps[0] >= self.speed_bounds_mps[1]:
            raise ValueError("capability speed bounds must be ordered")
        object.__setattr__(self, "limitations", tuple(self.limitations))


@dataclass(frozen=True)
class ExecutionEvidence:
    sim_time_s: float
    ownship_length_m: float
    ownship_width_m: float
    targets: tuple[ExecutionTarget, ...]
    capability: PlantCapabilityEvidence
    tracker_id: str
    static_clearance_m: float | None = None
    static_context_required: bool = False

    def __post_init__(self) -> None:
        """Freeze execution targets."""
        object.__setattr__(self, "targets", tuple(self.targets))


@dataclass(frozen=True)
class PriorEvidence:
    mode: AcceptanceMode
    previous_acceptance_hash: str | None = None
    previous_course_rad: np.ndarray | None = None

    def __post_init__(self) -> None:
        """Freeze prior accepted-plan evidence."""
        object.__setattr__(self, "mode", AcceptanceMode(self.mode))
        if self.previous_course_rad is not None:
            object.__setattr__(
                self,
                "previous_course_rad",
                _readonly_vector(self.previous_course_rad, "previous_course_rad"),
            )


@dataclass(frozen=True)
class PlanAcceptancePolicy:
    control_intervals: int = 80
    state_samples: int = 81
    horizon_dt_s: float = 15.0
    hard_hull_clearance_m: float = 50.0
    advisory_hull_clearance_m: float = 150.0
    max_relevant_targets: int = 16
    total_deadline_s: float = 20.0
    inline_limit_bytes: int = 8192
    scenario_id: str = "unspecified"
    algorithm_seed: int = 0
    tracker_id: str = "unspecified"
    allowed_capability_tuples: tuple[str, ...] = (
        "single-encounter:viknes:flsc",
        "multiship:kinematic_csog:pass_through_cs",
    )

    def __post_init__(self) -> None:
        """Validate frozen acceptance policy."""
        if self.control_intervals < 1 or self.state_samples != self.control_intervals + 1:
            raise ValueError("acceptance grid must contain one more state than control intervals")
        numeric = (
            self.horizon_dt_s,
            self.hard_hull_clearance_m,
            self.advisory_hull_clearance_m,
            self.total_deadline_s,
        )
        if not np.isfinite(numeric).all() or min(numeric) <= 0.0:
            raise ValueError("acceptance policy values must be finite and positive")
        if self.advisory_hull_clearance_m < self.hard_hull_clearance_m:
            raise ValueError("advisory clearance cannot be below hard clearance")
        if self.max_relevant_targets < 1 or self.inline_limit_bytes < 1:
            raise ValueError("acceptance limits must be positive")
        if not self.scenario_id or self.algorithm_seed < 0 or not self.tracker_id:
            raise ValueError("acceptance runtime identity must be complete")
        object.__setattr__(self, "allowed_capability_tuples", tuple(self.allowed_capability_tuples))


@dataclass(frozen=True)
class AcceptanceRequest:
    schema_version: str
    candidate: CandidateEvidence
    authority: AuthorityEvidence
    execution: ExecutionEvidence
    prior: PriorEvidence
    policy: PlanAcceptancePolicy


@dataclass(frozen=True)
class AcceptanceFinding:
    layer: AcceptanceLayer
    outcome: AcceptanceOutcome
    code: str
    message: str
    mandatory: bool
    target_key: TrackKey | None = None
    witness: dict[str, Any] | None = None


@dataclass(frozen=True)
class LayerVerdict:
    layer: AcceptanceLayer
    outcome: AcceptanceOutcome
    mandatory: bool


@dataclass(frozen=True)
class TargetSafetyWitness:
    key: TrackKey
    interval_index: int
    absolute_time_s: float
    center_distance_m: float
    clearance_lower_bound_m: float
    own_position_ne_m: tuple[float, float]
    target_position_ne_m: tuple[float, float]


@dataclass(frozen=True)
class AcceptanceResult:
    schema_version: str
    accepted: bool
    aggregate: AcceptanceOutcome
    profile: AcceptanceProfile
    request_hash: str
    acceptance_hash: str
    layers: tuple[LayerVerdict, ...]
    findings: tuple[AcceptanceFinding, ...]
    target_safety: tuple[TargetSafetyWitness, ...]

    def to_dict(self) -> dict[str, Any]:
        return _json_value(self)


class MidMpcPlanAcceptance:
    """Pure L4 gate over one immutable Mid-MPC candidate bundle."""

    def evaluate(self, request: AcceptanceRequest) -> AcceptanceResult:
        request_hash = _request_hash(request)
        findings: list[AcceptanceFinding] = []
        target_witnesses: list[TargetSafetyWitness] = []

        integrity_ok = self._integrity(request, findings)
        if integrity_ok:
            self._numerical(request, findings)
            target_witnesses.extend(self._safety(request, findings))
            self._colreg(request, findings)
            self._trackability(request, findings)
            self._quality(request, findings)
            self._evidence(request, findings)
        else:
            for layer in tuple(AcceptanceLayer)[1:]:
                findings.append(
                    AcceptanceFinding(
                        layer=layer,
                        outcome=AcceptanceOutcome.NOT_EVALUATED,
                        code="INTEGRITY_SHORT_CIRCUIT",
                        message="layer not evaluated after integrity failure",
                        mandatory=layer is not AcceptanceLayer.QUALITY,
                    )
                )

        layers = tuple(_layer_verdict(layer, findings) for layer in AcceptanceLayer)
        mandatory_failure = any(
            finding.mandatory and finding.outcome in {AcceptanceOutcome.FAIL, AcceptanceOutcome.UNKNOWN}
            for finding in findings
        )
        if request.candidate.profile is AcceptanceProfile.MASS_PARITY:
            accepted = False
            aggregate = AcceptanceOutcome.NOT_EVALUATED
            findings.append(
                AcceptanceFinding(
                    layer=AcceptanceLayer.EVIDENCE,
                    outcome=AcceptanceOutcome.NOT_EVALUATED,
                    code="PROFILE_DIAGNOSTIC_ONLY",
                    message="MASS_PARITY cannot authorize command, receipt, or warm start",
                    mandatory=True,
                )
            )
            layers = tuple(_layer_verdict(layer, findings) for layer in AcceptanceLayer)
        else:
            accepted = not mandatory_failure
            aggregate = AcceptanceOutcome.PASS if accepted else AcceptanceOutcome.FAIL

        semantic = {
            "schema_version": RESULT_SCHEMA,
            "accepted": accepted,
            "aggregate": aggregate,
            "profile": request.candidate.profile,
            "request_hash": request_hash,
            "layers": layers,
            "findings": findings,
            "target_safety": target_witnesses,
        }
        return AcceptanceResult(
            schema_version=RESULT_SCHEMA,
            accepted=accepted,
            aggregate=aggregate,
            profile=request.candidate.profile,
            request_hash=request_hash,
            acceptance_hash=_hash_document(semantic),
            layers=layers,
            findings=tuple(findings),
            target_safety=tuple(target_witnesses),
        )

    @staticmethod
    def _integrity(request: AcceptanceRequest, findings: list[AcceptanceFinding]) -> bool:
        failures: list[tuple[str, str]] = []
        candidate = request.candidate
        if request.schema_version != REQUEST_SCHEMA:
            failures.append(("INTEGRITY_SCHEMA", "unsupported acceptance request schema"))
        if candidate.profile.value != candidate.numerical.preparation_profile:
            failures.append(("INTEGRITY_PROFILE", "candidate and numerical preparation profiles differ"))
        if not math.isclose(request.authority.sim_time_s, request.execution.sim_time_s, abs_tol=1.0e-9):
            failures.append(("INTEGRITY_CYCLE", "authority and execution times differ"))
        if candidate.times_s.size != request.policy.state_samples:
            failures.append(("INTEGRITY_GRID", "candidate state sample count differs from policy"))
        elif not np.allclose(
            candidate.times_s,
            np.arange(request.policy.state_samples) * request.policy.horizon_dt_s,
            atol=1.0e-9,
            rtol=0.0,
        ):
            failures.append(("INTEGRITY_TIME_AXIS", "candidate time axis differs from policy"))
        execution_keys = [target.key for target in request.execution.targets]
        authority_keys = [target.key for target in request.authority.targets]
        if len(set(execution_keys)) != len(execution_keys) or len(set(authority_keys)) != len(authority_keys):
            failures.append(("INTEGRITY_TARGET_IDENTITY", "target keys must be unique within each namespace"))
        if set(execution_keys) != set(authority_keys):
            failures.append(("INTEGRITY_TARGET_RECONCILIATION", "authority and execution target sets differ"))
        if len(request.execution.targets) > request.policy.max_relevant_targets:
            failures.append(("INTEGRITY_CAPACITY", "execution target count exceeds frozen capacity"))
        for code, message in failures:
            findings.append(
                AcceptanceFinding(
                    AcceptanceLayer.INTEGRITY,
                    AcceptanceOutcome.FAIL,
                    code,
                    message,
                    True,
                )
            )
        if not failures:
            findings.append(
                AcceptanceFinding(
                    AcceptanceLayer.INTEGRITY,
                    AcceptanceOutcome.PASS,
                    "INTEGRITY_VALID",
                    "request identity, profile, grid, and targets are coherent",
                    True,
                )
            )
        return not failures

    @staticmethod
    def _numerical(request: AcceptanceRequest, findings: list[AcceptanceFinding]) -> None:
        evidence = request.candidate.numerical
        eligible = evidence.normalized_status in {"Converged", "FeasibleNonOptimal", "Timeout"}
        if not eligible:
            _fail(findings, AcceptanceLayer.NUMERICAL, "NUMERICAL_TERMINATION", "solver termination is not eligible")
        allowed_terminations = {
            "Converged": {"Solve_Succeeded"},
            "FeasibleNonOptimal": {"Solved_To_Acceptable_Level", "User_Requested_Stop"},
            "Timeout": {"Maximum_CpuTime_Exceeded", "User_Requested_Stop"},
        }
        if evidence.return_status not in allowed_terminations.get(evidence.normalized_status, set()):
            _fail(
                findings,
                AcceptanceLayer.NUMERICAL,
                "NUMERICAL_TERMINATION_MISMATCH",
                "normalized solver status does not match the native IPOPT return status",
            )
        scalar_values = (evidence.objective_total, evidence.raw_f, evidence.cpa_slack, evidence.direction_slack)
        bounds = (evidence.lbx, evidence.ubx, evidence.lbg, evidence.ubg)
        if (
            not np.isfinite(evidence.raw_x).all()
            or not np.isfinite(evidence.raw_g).all()
            or any(np.isnan(vector).any() for vector in bounds)
            or not np.isfinite(scalar_values).all()
        ):
            _fail(findings, AcceptanceLayer.NUMERICAL, "NUMERICAL_NONFINITE", "candidate numerical evidence is non-finite")
        x_violation = _bound_violations(evidence.raw_x, evidence.lbx, evidence.ubx)
        x_tolerances = np.full(evidence.raw_x.size, 1.0e-4)
        x_tolerances[: evidence.heading_count] = 1.0e-6
        speed_start = evidence.heading_count
        x_tolerances[speed_start : speed_start + evidence.speed_count] = 1.0e-6
        x_tolerances[-2:] = 1.0e-7
        if np.any(x_violation > x_tolerances + 1.0e-10 * np.maximum(np.abs(evidence.lbx), np.abs(evidence.ubx))):
            _fail(
                findings,
                AcceptanceLayer.NUMERICAL,
                "NUMERICAL_ORIGINAL_BOUNDS",
                "raw decision violates original bounds",
                witness={"max_violation": float(np.max(x_violation))},
            )
        g_violation = _bound_violations(evidence.raw_g, evidence.lbg, evidence.ubg)
        g_tolerances = np.full(evidence.raw_g.size, 1.0e-6)
        if evidence.cpa_row_indices:
            g_tolerances[np.array(evidence.cpa_row_indices)] = 1.0e-4
        if np.any(g_violation > g_tolerances + 1.0e-10 * np.maximum(np.abs(evidence.lbg), np.abs(evidence.ubg))):
            _fail(
                findings,
                AcceptanceLayer.NUMERICAL,
                "NUMERICAL_CONSTRAINT_BOUNDS",
                "raw constraints violate original bounds",
                witness={"max_violation": float(np.max(g_violation))},
            )
        objective_tolerance = 1.0e-8 + 1.0e-10 * max(abs(evidence.objective_total), abs(evidence.raw_f))
        if abs(evidence.objective_total - evidence.raw_f) > objective_tolerance:
            _fail(findings, AcceptanceLayer.NUMERICAL, "NUMERICAL_OBJECTIVE", "objective evidence is inconsistent")
        if request.candidate.profile is AcceptanceProfile.COLAV_STRICT:
            if not evidence.strict_slack_bounds or max(abs(evidence.cpa_slack), abs(evidence.direction_slack)) > 1.0e-7:
                _fail(
                    findings,
                    AcceptanceLayer.NUMERICAL,
                    "NUMERICAL_STRICT_SLACK",
                    "strict candidate contains nonzero or unbounded hard slack",
                )
        if not any(item.layer is AcceptanceLayer.NUMERICAL and item.outcome is AcceptanceOutcome.FAIL for item in findings):
            findings.append(
                AcceptanceFinding(
                    AcceptanceLayer.NUMERICAL,
                    AcceptanceOutcome.PASS,
                    "NUMERICAL_PRIMAL_VALID",
                    "eligible same-point candidate satisfies original primal evidence",
                    True,
                )
            )
        if not evidence.same_point_multipliers_available:
            findings.append(
                AcceptanceFinding(
                    AcceptanceLayer.NUMERICAL,
                    AcceptanceOutcome.WARN,
                    "NUMERICAL_KKT_NOT_EVALUATED",
                    "same-point multipliers unavailable; KKT remains advisory",
                    False,
                )
            )

    @staticmethod
    def _safety(
        request: AcceptanceRequest,
        findings: list[AcceptanceFinding],
    ) -> tuple[TargetSafetyWitness, ...]:
        candidate = request.candidate
        own_radius = 0.5 * math.hypot(
            request.execution.ownship_length_m,
            request.execution.ownship_width_m,
        )
        witnesses: list[TargetSafetyWitness] = []
        for target in sorted(request.execution.targets, key=lambda item: (item.key.target_id, item.key.generation)):
            if target.north_m.size != candidate.times_s.size:
                _fail(
                    findings,
                    AcceptanceLayer.SAFETY,
                    "SAFETY_TARGET_GRID",
                    "target prediction grid differs from ownship grid",
                    target_key=target.key,
                )
                continue
            target_radius = 0.5 * math.hypot(target.length_m, target.width_m)
            best: TargetSafetyWitness | None = None
            for index in range(candidate.times_s.size - 1):
                own_start = np.array([candidate.north_m[index], candidate.east_m[index]])
                own_end = np.array([candidate.north_m[index + 1], candidate.east_m[index + 1]])
                target_start = np.array([target.north_m[index], target.east_m[index]])
                target_end = np.array([target.north_m[index + 1], target.east_m[index + 1]])
                relative_start = target_start - own_start
                relative_delta = (target_end - own_end) - relative_start
                denominator = float(relative_delta @ relative_delta)
                fraction = (
                    0.0
                    if denominator <= 1.0e-18
                    else float(np.clip(-float(relative_start @ relative_delta) / denominator, 0.0, 1.0))
                )
                relative = relative_start + fraction * relative_delta
                own_at_min = own_start + fraction * (own_end - own_start)
                target_at_min = target_start + fraction * (target_end - target_start)
                center = float(np.linalg.norm(relative))
                uncertainty = max(float(target.uncertainty_m[index]), float(target.uncertainty_m[index + 1]))
                clearance = center - own_radius - target_radius - uncertainty
                witness = TargetSafetyWitness(
                    key=target.key,
                    interval_index=index,
                    absolute_time_s=request.execution.sim_time_s
                    + float(candidate.times_s[index] + fraction * request.policy.horizon_dt_s),
                    center_distance_m=center,
                    clearance_lower_bound_m=clearance,
                    own_position_ne_m=(float(own_at_min[0]), float(own_at_min[1])),
                    target_position_ne_m=(float(target_at_min[0]), float(target_at_min[1])),
                )
                if best is None or witness.clearance_lower_bound_m < best.clearance_lower_bound_m:
                    best = witness
            if best is not None:
                witnesses.append(best)
                if best.clearance_lower_bound_m < request.policy.hard_hull_clearance_m:
                    _fail(
                        findings,
                        AcceptanceLayer.SAFETY,
                        "SAFETY_SWEPT_CLEARANCE",
                        "synchronized swept hull clearance is below the physical hard gate",
                        target_key=target.key,
                        witness=_json_value(best),
                    )
        if request.execution.static_context_required:
            static = request.execution.static_clearance_m
            if static is None or not math.isfinite(static) or static < request.policy.hard_hull_clearance_m:
                _fail(
                    findings,
                    AcceptanceLayer.SAFETY,
                    "SAFETY_STATIC_CLEARANCE",
                    "required static-hazard clearance is missing or below the hard gate",
                )
        if not any(item.layer is AcceptanceLayer.SAFETY and item.outcome is AcceptanceOutcome.FAIL for item in findings):
            findings.append(
                AcceptanceFinding(
                    AcceptanceLayer.SAFETY,
                    AcceptanceOutcome.PASS,
                    "SAFETY_SWEPT_VALID",
                    "all relevant targets satisfy synchronized swept hull clearance",
                    True,
                )
            )
        return tuple(witnesses)

    @staticmethod
    def _colreg(  # noqa: C901, PLR0912, PLR0915 - explicit rule predicate conjunction
        request: AcceptanceRequest,
        findings: list[AcceptanceFinding],
    ) -> None:
        candidate = request.candidate
        execution_by_key = {target.key: target for target in request.execution.targets}
        candidate_sides = {
            target.passing_side
            for target in request.authority.targets
            if target.risk == "CANDIDATE"
            and target.commitment == "NONE"
            and target.role in {"GIVE_WAY", "OVERTAKING"}
            and target.passing_side in {"PORT", "STARBOARD"}
        }
        if len(candidate_sides) > 1:
            _fail(
                findings,
                AcceptanceLayer.COLREG,
                "COLREG_CONFLICTING_LOCKED_SIDES",
                "candidate contains incompatible provisional passing corridors",
            )
        for target in sorted(request.authority.targets, key=lambda item: (item.key.target_id, item.key.generation)):
            stand_on_obligation = (
                target.role in {"STAND_ON", "OVERTAKEN"} and target.commitment == "NONE" and target.risk == "ACTIVE"
            )
            if stand_on_obligation:
                give_way_obligation = any(
                    peer.role in {"GIVE_WAY", "OVERTAKING"} and peer.risk in {"CANDIDATE", "ACTIVE", "PAST_CLEAR"}
                    for peer in request.authority.targets
                )
                if give_way_obligation:
                    continue
                if target.baseline_course_rad is None or not math.isfinite(target.baseline_course_rad):
                    _fail(
                        findings,
                        AcceptanceLayer.COLREG,
                        "COLREG_BASELINE_MISSING",
                        "stand-on target lacks a frozen course baseline",
                        target_key=target.key,
                    )
                else:
                    drift = max(
                        abs(_wrap(float(course - target.baseline_course_rad)))
                        for course in candidate.course_rad
                    )
                    if drift > math.radians(5.0) + 1.0e-6:
                        _fail(
                            findings,
                            AcceptanceLayer.COLREG,
                            "COLREG_STAND_ON_DRIFT",
                            "stand-on candidate changes course before Rule 17 authority",
                            target_key=target.key,
                            witness={"maximum_course_drift_rad": drift},
                        )
                continue
            candidate_obligation = (
                target.risk == "CANDIDATE" and target.commitment == "NONE" and target.role in {"GIVE_WAY", "OVERTAKING"}
            )
            committed_obligation = target.commitment == "COMMITTED" and target.risk in {"ACTIVE", "PAST_CLEAR"}
            if not (candidate_obligation or committed_obligation):
                continue
            if target.baseline_course_rad is None or not math.isfinite(target.baseline_course_rad):
                _fail(
                    findings,
                    AcceptanceLayer.COLREG,
                    "COLREG_BASELINE_MISSING",
                    "committed target lacks frozen course baseline",
                    target_key=target.key,
                )
                continue
            contract_values = (
                target.committed_at_s,
                target.action_start_deadline_s,
                target.action_achievement_deadline_s,
                target.actual_course_change_rad,
            )
            if committed_obligation and any(value is None or not math.isfinite(value) for value in contract_values):
                _fail(
                    findings,
                    AcceptanceLayer.COLREG,
                    "COLREG_ACTION_CONTRACT_INCOMPLETE",
                    "committed target lacks action timing or actual-achievement evidence",
                    target_key=target.key,
                )
                continue
            if not target.reachability_verified:
                _fail(
                    findings,
                    AcceptanceLayer.COLREG,
                    "COLREG_REACHABILITY_UNKNOWN",
                    "committed action lacks a valid reachability certificate",
                    target_key=target.key,
                )
            side_sign = 1.0 if target.passing_side == "STARBOARD" else -1.0 if target.passing_side == "PORT" else 0.0
            deltas = np.array([_wrap(float(course - target.baseline_course_rad)) for course in candidate.course_rad])
            if side_sign != 0.0:
                signed = side_sign * deltas
                if not target.action_achieved and float(np.min(signed)) < -1.0e-6:
                    _fail(
                        findings,
                        AcceptanceLayer.COLREG,
                        "COLREG_LOCKED_SIDE",
                        "candidate initially moves against the Lifecycle-locked passing side",
                        target_key=target.key,
                    )
                if candidate_obligation:
                    continue
                start_deadline_s = (
                    float(target.action_start_deadline_s)
                    if target.action_start_deadline_s is not None
                    else request.execution.sim_time_s + request.policy.horizon_dt_s
                )
                start_offset_s = max(0.0, start_deadline_s - request.execution.sim_time_s)
                start_delta = side_sign * _course_delta_at(candidate, target.baseline_course_rad, start_offset_s)
                if not target.action_achieved and start_delta < math.radians(1.0):
                    _fail(
                        findings,
                        AcceptanceLayer.COLREG,
                        "COLREG_ACTION_START_DEADLINE",
                        "candidate does not start the locked maneuver by its absolute deadline",
                        target_key=target.key,
                    )
                achievement_deadline_s = (
                    float(target.action_achievement_deadline_s)
                    if target.action_achievement_deadline_s is not None
                    else request.execution.sim_time_s + 2.0 * request.policy.horizon_dt_s
                )
                achievement_offset_s = max(0.0, achievement_deadline_s - request.execution.sim_time_s)
                achieved_delta = side_sign * _course_delta_at(
                    candidate,
                    target.baseline_course_rad,
                    achievement_offset_s,
                )
                if not target.action_achieved and achieved_delta + 1.0e-6 < target.required_course_change_rad:
                    _fail(
                        findings,
                        AcceptanceLayer.COLREG,
                        "COLREG_ACTION_DEADLINE",
                        "candidate does not achieve the locked maneuver by its absolute deadline",
                        target_key=target.key,
                    )
                if not target.action_achieved and float(np.max(signed)) + 1.0e-6 < target.required_course_change_rad:
                    _fail(
                        findings,
                        AcceptanceLayer.COLREG,
                        "COLREG_ACTION_ACHIEVEMENT",
                        "candidate never reaches the committed minimum course change",
                        target_key=target.key,
                    )
            execution_target = execution_by_key[target.key]
            relative_at_cpa = _closest_relative_position(candidate, execution_target)
            relative_knots = np.column_stack(
                (
                    execution_target.north_m - candidate.north_m,
                    execution_target.east_m - candidate.east_m,
                )
            )
            cpa_inside_horizon = int(np.argmin(np.linalg.norm(relative_knots, axis=1))) < candidate.times_s.size - 1
            if (
                not target.action_achieved
                and cpa_inside_horizon
                and target.encounter == "HEAD_ON"
                and target.passing_side == "STARBOARD"
            ):
                starboard_normal = np.array([-math.sin(target.baseline_course_rad), math.cos(target.baseline_course_rad)])
                if float(relative_at_cpa @ starboard_normal) >= 0.0:
                    _fail(
                        findings,
                        AcceptanceLayer.COLREG,
                        "COLREG_HEAD_ON_PASSING_SIDE",
                        "head-on candidate does not produce port-to-port passing geometry",
                        target_key=target.key,
                    )
            if (
                not target.action_achieved
                and cpa_inside_horizon
                and target.encounter == "CROSSING"
                and target.role == "GIVE_WAY"
            ):
                target_displacement = np.array(
                    [
                        execution_target.north_m[-1] - execution_target.north_m[0],
                        execution_target.east_m[-1] - execution_target.east_m[0],
                    ]
                )
                if float(relative_at_cpa @ target_displacement) <= 0.0:
                    _fail(
                        findings,
                        AcceptanceLayer.COLREG,
                        "COLREG_CROSSING_BOW",
                        "crossing give-way candidate does not pass astern",
                        target_key=target.key,
                    )
            if (
                target.action_start_deadline_s is not None
                and request.execution.sim_time_s > target.action_start_deadline_s
                and float(target.actual_course_change_rad or 0.0) < math.radians(1.0)
            ):
                _fail(
                    findings,
                    AcceptanceLayer.COLREG,
                    "COLREG_ACTUAL_START_DEADLINE",
                    "actual vessel maneuver missed the Lifecycle action-start deadline",
                    target_key=target.key,
                )
            if (
                target.action_achievement_deadline_s is not None
                and request.execution.sim_time_s > target.action_achievement_deadline_s
                and not target.action_achieved
            ):
                _fail(
                    findings,
                    AcceptanceLayer.COLREG,
                    "COLREG_ACTION_DEADLINE",
                    "actual maneuver achievement missed the Lifecycle deadline",
                    target_key=target.key,
                )
        if not any(item.layer is AcceptanceLayer.COLREG and item.outcome is AcceptanceOutcome.FAIL for item in findings):
            findings.append(
                AcceptanceFinding(
                    AcceptanceLayer.COLREG,
                    AcceptanceOutcome.PASS,
                    "COLREG_AUTHORITY_VALID",
                    "candidate is consistent with Lifecycle-locked obligations",
                    True,
                )
            )

    @staticmethod
    def _trackability(request: AcceptanceRequest, findings: list[AcceptanceFinding]) -> None:
        capability = request.execution.capability
        candidate = request.candidate
        if capability.exact_tuple not in request.policy.allowed_capability_tuples:
            _fail(
                findings,
                AcceptanceLayer.TRACKABILITY,
                "TRACKABILITY_CAPABILITY_TUPLE",
                "active plant/controller tuple is not allowed by the frozen policy",
            )
        if capability.limitations:
            _fail(
                findings,
                AcceptanceLayer.TRACKABILITY,
                "TRACKABILITY_CAPABILITY_INCOMPLETE",
                "active capability contains unresolved limitations",
                witness={"limitations": list(capability.limitations)},
            )
        if not math.isclose(capability.valid_at_s, request.execution.sim_time_s, abs_tol=1.0e-9):
            _fail(
                findings,
                AcceptanceLayer.TRACKABILITY,
                "TRACKABILITY_CAPABILITY_STALE",
                "active capability is not valid at the request time",
            )
        low, high = capability.speed_bounds_mps
        speed_tolerance = max(1.0e-6, 1.0e-5 * max(1.0, abs(low), abs(high)))
        commanded_speed = candidate.speed_mps[1:]
        if np.any(commanded_speed < low - speed_tolerance) or np.any(commanded_speed > high + speed_tolerance):
            _fail(findings, AcceptanceLayer.TRACKABILITY, "TRACKABILITY_SPEED", "candidate speed exceeds active bounds")
        course_steps = np.array(
            [
                _wrap(float(end - start))
                for start, end in zip(candidate.course_rad[:-1], candidate.course_rad[1:], strict=True)
            ]
        )
        if course_steps.size and np.any(
            np.abs(course_steps) > capability.rot_max_rad_s * request.policy.horizon_dt_s + 1.0e-4
        ):
            _fail(findings, AcceptanceLayer.TRACKABILITY, "TRACKABILITY_ROT", "candidate turn exceeds active rate")
        speed_steps = np.diff(candidate.speed_mps)
        if speed_steps.size:
            if np.any(speed_steps > capability.accel_max_mps2 * request.policy.horizon_dt_s + 1.0e-6):
                _fail(
                    findings,
                    AcceptanceLayer.TRACKABILITY,
                    "TRACKABILITY_ACCEL",
                    "candidate acceleration exceeds active bound",
                )
            if np.any(-speed_steps > capability.decel_max_mps2 * request.policy.horizon_dt_s + 1.0e-6):
                _fail(
                    findings,
                    AcceptanceLayer.TRACKABILITY,
                    "TRACKABILITY_DECEL",
                    "candidate deceleration exceeds active bound",
                )
        if not any(
            item.layer is AcceptanceLayer.TRACKABILITY and item.outcome is AcceptanceOutcome.FAIL for item in findings
        ):
            findings.append(
                AcceptanceFinding(
                    AcceptanceLayer.TRACKABILITY,
                    AcceptanceOutcome.PASS,
                    "TRACKABILITY_ACTIVE_PREFIX_VALID",
                    "candidate active prefix satisfies the exact active capability tuple",
                    True,
                )
            )

    @staticmethod
    def _quality(request: AcceptanceRequest, findings: list[AcceptanceFinding]) -> None:
        course_steps = np.diff(np.unwrap(request.candidate.course_rad))
        speed_steps = np.diff(request.candidate.speed_mps)
        witness = {
            "max_course_step_rad": float(np.max(np.abs(course_steps))) if course_steps.size else 0.0,
            "max_speed_step_mps": float(np.max(np.abs(speed_steps))) if speed_steps.size else 0.0,
            "straightness_rad": float(np.ptp(np.unwrap(request.candidate.course_rad))),
        }
        outcome = AcceptanceOutcome.PASS
        code = "QUALITY_OBSERVED"
        message = "quality metrics recorded; V1 remains advisory"
        if (
            request.prior.previous_course_rad is not None
            and request.prior.previous_course_rad.size == request.candidate.course_rad.size
        ):
            churn = np.max(np.abs(np.unwrap(request.candidate.course_rad) - np.unwrap(request.prior.previous_course_rad)))
            witness["cross_solve_course_churn_rad"] = float(churn)
            if churn > math.radians(20.0):
                outcome = AcceptanceOutcome.WARN
                code = "QUALITY_COURSE_CHURN"
                message = "large cross-solve course churn observed"
        findings.append(AcceptanceFinding(AcceptanceLayer.QUALITY, outcome, code, message, False, witness=witness))

    @staticmethod
    def _evidence(request: AcceptanceRequest, findings: list[AcceptanceFinding]) -> None:
        numerical = request.candidate.numerical
        hashes = (
            request.candidate.parent_problem_hash,
            numerical.preparation_hash,
            numerical.solver_hash,
            request.authority.profile_hash,
        )
        parent_chain_valid = (
            numerical.preparation_parent_problem_hash == request.candidate.parent_problem_hash
            and numerical.solver_parent_preparation_hash == numerical.preparation_hash
        )
        if any(len(value) != 64 for value in hashes) or not parent_chain_valid:
            _fail(
                findings,
                AcceptanceLayer.EVIDENCE,
                "EVIDENCE_HASH_CHAIN",
                "request evidence hashes must be complete SHA-256 values",
            )
        else:
            findings.append(
                AcceptanceFinding(
                    AcceptanceLayer.EVIDENCE,
                    AcceptanceOutcome.PASS,
                    "EVIDENCE_CHAIN_VALID",
                    "request carries complete problem, preparation, solver, and policy parents",
                    True,
                )
            )


def _fail(
    findings: list[AcceptanceFinding],
    layer: AcceptanceLayer,
    code: str,
    message: str,
    *,
    target_key: TrackKey | None = None,
    witness: dict[str, Any] | None = None,
) -> None:
    findings.append(AcceptanceFinding(layer, AcceptanceOutcome.FAIL, code, message, True, target_key, witness))


def _layer_verdict(layer: AcceptanceLayer, findings: list[AcceptanceFinding]) -> LayerVerdict:
    relevant = [finding for finding in findings if finding.layer is layer]
    if not relevant:
        outcome = AcceptanceOutcome.NOT_EVALUATED
    elif any(finding.outcome is AcceptanceOutcome.FAIL for finding in relevant):
        outcome = AcceptanceOutcome.FAIL
    elif any(finding.outcome is AcceptanceOutcome.UNKNOWN for finding in relevant):
        outcome = AcceptanceOutcome.UNKNOWN
    elif any(finding.outcome is AcceptanceOutcome.WARN for finding in relevant):
        outcome = AcceptanceOutcome.WARN
    elif all(finding.outcome is AcceptanceOutcome.NOT_EVALUATED for finding in relevant):
        outcome = AcceptanceOutcome.NOT_EVALUATED
    else:
        outcome = AcceptanceOutcome.PASS
    return LayerVerdict(layer=layer, outcome=outcome, mandatory=layer is not AcceptanceLayer.QUALITY)


def _bound_violations(values: np.ndarray, lower: np.ndarray, upper: np.ndarray) -> np.ndarray:
    return np.maximum(np.maximum(lower - values, values - upper), 0.0)


def _closest_relative_position(candidate: CandidateEvidence, target: ExecutionTarget) -> np.ndarray:
    best_distance = math.inf
    best_relative = np.zeros(2)
    for index in range(candidate.times_s.size - 1):
        own_start = np.array([candidate.north_m[index], candidate.east_m[index]])
        own_end = np.array([candidate.north_m[index + 1], candidate.east_m[index + 1]])
        target_start = np.array([target.north_m[index], target.east_m[index]])
        target_end = np.array([target.north_m[index + 1], target.east_m[index + 1]])
        relative_start = target_start - own_start
        relative_delta = (target_end - own_end) - relative_start
        denominator = float(relative_delta @ relative_delta)
        fraction = (
            0.0
            if denominator <= 1.0e-18
            else float(np.clip(-float(relative_start @ relative_delta) / denominator, 0.0, 1.0))
        )
        relative = relative_start + fraction * relative_delta
        distance = float(relative @ relative)
        if distance < best_distance:
            best_distance = distance
            best_relative = relative
    return best_relative


def _course_delta_at(candidate: CandidateEvidence, baseline_rad: float, offset_s: float) -> float:
    position = float(np.clip(offset_s / (candidate.times_s[1] - candidate.times_s[0]), 0.0, candidate.times_s.size - 1))
    lower = int(math.floor(position))
    upper = min(lower + 1, candidate.course_rad.size - 1)
    fraction = position - lower
    lower_delta = _wrap(float(candidate.course_rad[lower] - baseline_rad))
    step = _wrap(float(candidate.course_rad[upper] - candidate.course_rad[lower]))
    return lower_delta + fraction * step


def _readonly_vector(value: object, name: str) -> np.ndarray:
    array = np.asarray(value, dtype=float)
    if array.ndim != 1:
        raise ValueError(f"{name} must be a vector")
    copy = np.array(array, dtype=float, copy=True)
    copy.setflags(write=False)
    return copy


def _wrap(value: float) -> float:
    return math.atan2(math.sin(value), math.cos(value))


def _hash_document(value: object) -> str:
    payload = json.dumps(_json_value(value), sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _request_hash(request: AcceptanceRequest) -> str:
    document = _json_value(request)
    document["authority"]["targets"] = sorted(
        document["authority"]["targets"],
        key=lambda item: (item["key"]["target_id"], item["key"]["generation"]),
    )
    document["execution"]["targets"] = sorted(
        document["execution"]["targets"],
        key=lambda item: (item["key"]["target_id"], item["key"]["generation"]),
    )
    return _hash_document(document)


def _json_value(value: object) -> Any:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        if math.isinf(value):
            return "Infinity" if value > 0.0 else "-Infinity"
        if math.isnan(value):
            raise ValueError("acceptance semantic evidence cannot contain NaN")
        return value
    if isinstance(value, np.ndarray):
        return _json_value(value.tolist())
    if isinstance(value, np.generic):
        return _json_value(value.item())
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, TrackKey):
        return {"target_id": value.target_id, "generation": value.generation}
    if hasattr(value, "__dataclass_fields__"):
        return _json_value(asdict(value))
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    raise TypeError(f"unsupported acceptance evidence value: {type(value).__name__}")
