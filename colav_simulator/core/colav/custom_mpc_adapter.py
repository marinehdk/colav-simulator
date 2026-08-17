"""Strict ICOLAV adapter for user-developed MPC collision avoidance algorithms."""

from __future__ import annotations

import hashlib
import json
import math
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, field, replace
from enum import StrEnum
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import seacharts.enc as senc

from colav_simulator.core import stochasticity
from colav_simulator.core.colav.colav_interface import ICOLAV
from colav_simulator.core.colav.diagnostics import (
    ColavExecutionError,
    FailureSource,
    PlanDiagnostics,
    PlannerTrace,
    PlanStatus,
)
from colav_simulator.core.colav.prediction_evidence import (
    EvidenceEnvelope,
    EvidenceEvent,
    EvidenceEventType,
    OccurrenceId,
    RuntimeAppliedReference,
    TerminalOutcome,
    reduce_evidence,
    render_snapshot,
)
from colav_simulator.core.tracking.trackers import TrackSnapshot

SCHEMA_VERSION = "1.0"
UNKNOWN_IDENTITY = "UNKNOWN"


class DeadlineMode(StrEnum):
    """Wall-clock deadline policy for one algorithm run."""

    ENFORCE = "ENFORCE"
    OFF = "OFF"


@dataclass(frozen=True)
class FactoryContext:
    """Runtime values injected by the experiment runner into a plugin factory."""

    requested_algorithm: str
    algorithm_seed: int
    strict_no_fallback: bool = True
    scenario_id: str = "UNSPECIFIED"
    tracker_id: str = "UNSPECIFIED"
    solve_period_override_s: float | None = None
    deadline_mode: DeadlineMode = DeadlineMode.ENFORCE
    event_sink: Callable[[Any], object] | None = field(default=None, compare=False, repr=False)
    artifact_sink: Callable[[Any], object] | None = field(default=None, compare=False, repr=False)

    def __post_init__(self) -> None:
        """Normalize and validate injected runtime values."""
        algorithm_id = self.requested_algorithm.strip().lower()
        if not algorithm_id:
            raise ValueError("requested_algorithm is required")
        if self.algorithm_seed < 0:
            raise ValueError("algorithm_seed must be non-negative")
        if not self.scenario_id.strip() or not self.tracker_id.strip():
            raise ValueError("scenario_id and tracker_id must be non-empty")
        if self.solve_period_override_s is not None and (
            not np.isfinite(self.solve_period_override_s) or self.solve_period_override_s <= 0.0
        ):
            raise ValueError("solve_period_override_s must be finite and positive")
        if self.event_sink is not None and not callable(self.event_sink):
            raise TypeError("event_sink must be callable when specified")
        if self.artifact_sink is not None and not callable(self.artifact_sink):
            raise TypeError("artifact_sink must be callable when specified")
        object.__setattr__(self, "requested_algorithm", algorithm_id)
        if isinstance(self.deadline_mode, str):
            object.__setattr__(self, "deadline_mode", DeadlineMode(self.deadline_mode.upper()))


@dataclass(frozen=True)
class ExecutionProfile:
    """Static execution and validation limits for an MPC implementation."""

    solve_period_s: float
    deadline_s: float
    max_consecutive_timeout: int = 1
    requires_enc: bool = False
    degraded_track_age_s: float = 1.0
    max_track_age_s: float = 5.0
    first_state_tolerance_m: float = 0.25
    first_state_tolerance_rad: float = 1e-3
    state_tolerance: float = 1e-3

    def __post_init__(self) -> None:
        """Validate execution timing and input-quality limits."""
        if not np.isfinite(self.solve_period_s) or self.solve_period_s <= 0.0:
            raise ValueError("solve_period_s must be finite and positive")
        if not np.isfinite(self.deadline_s) or self.deadline_s <= 0.0:
            raise ValueError("deadline_s must be finite and positive")
        if self.max_consecutive_timeout < 1:
            raise ValueError("max_consecutive_timeout must be at least one")
        if not np.isfinite((self.degraded_track_age_s, self.max_track_age_s)).all() or not (
            0.0 <= self.degraded_track_age_s <= self.max_track_age_s
        ):
            raise ValueError("track age limits must satisfy 0 <= degraded <= max")
        tolerances = (
            self.first_state_tolerance_m,
            self.first_state_tolerance_rad,
            self.state_tolerance,
        )
        if not np.isfinite(tolerances).all() or min(tolerances) < 0.0:
            raise ValueError("state tolerances must be finite and non-negative")


@dataclass(frozen=True)
class AlgorithmDescriptor:
    """Canonical static declaration for one MPC algorithm configuration."""

    algorithm_id: str
    version: str
    control_form: str
    state_layout: tuple[str, ...]
    predictor_model: str
    horizon_dt: float
    horizon_steps: int
    objective_terms: tuple[str, ...]
    constraint_terms: tuple[str, ...]
    solver: str
    seed_policy: str
    execution_profile: ExecutionProfile
    state_samples: int | None = None

    def __post_init__(self) -> None:
        """Normalize and validate the canonical static descriptor."""
        for name in ("algorithm_id", "version", "control_form", "predictor_model", "solver", "seed_policy"):
            value = str(getattr(self, name)).strip()
            if not value:
                raise ValueError(f"{name} is required")
            object.__setattr__(self, name, value.lower() if name == "algorithm_id" else value)
        object.__setattr__(self, "state_layout", _string_tuple(self.state_layout, "state_layout"))
        object.__setattr__(self, "objective_terms", _string_tuple(self.objective_terms, "objective_terms"))
        object.__setattr__(self, "constraint_terms", _string_tuple(self.constraint_terms, "constraint_terms"))
        if not np.isfinite(self.horizon_dt) or self.horizon_dt <= 0.0:
            raise ValueError("horizon_dt must be finite and positive")
        if self.horizon_steps < 1:
            raise ValueError("horizon_steps must be positive")
        if self.state_samples is not None and self.state_samples < 2:
            raise ValueError("state_samples must be at least two when specified")
        if not isinstance(self.execution_profile, ExecutionProfile):
            raise TypeError("execution_profile must be ExecutionProfile")

    def to_dict(self) -> dict[str, Any]:
        return {
            "algorithm_id": self.algorithm_id,
            "version": self.version,
            "control_form": self.control_form,
            "state_layout": list(self.state_layout),
            "predictor_model": self.predictor_model,
            "horizon_dt": self.horizon_dt,
            "horizon_steps": self.horizon_steps,
            "state_samples": self.state_samples or self.horizon_steps,
            "objective_terms": list(self.objective_terms),
            "constraint_terms": list(self.constraint_terms),
            "solver": self.solver,
            "seed_policy": self.seed_policy,
            "execution_profile": asdict(self.execution_profile),
        }

    @property
    def hash(self) -> str:
        return _content_hash(self.to_dict())

    def envelope(self, build_identity: BuildIdentity | None = None) -> dict[str, Any]:
        identity = build_identity or BuildIdentity()
        return {
            "schema_version": SCHEMA_VERSION,
            "descriptor": self.to_dict(),
            "descriptor_hash": self.hash,
            "role": "collision_avoidance",
            "supported_obstacles": ["dynamic_tracks", *(["enc"] if self.execution_profile.requires_enc else [])],
            "fallback_policy": "forbidden",
            "build_identity": identity.to_dict(),
            "build_identity_hash": identity.hash,
        }


@dataclass(frozen=True)
class BuildIdentity:
    """Hashes proving which plugin source and dependencies were executed."""

    factory_ref: str = UNKNOWN_IDENTITY
    module_sha256: str = UNKNOWN_IDENTITY
    dependency_lock_sha256: str = UNKNOWN_IDENTITY
    config_sha256: str = UNKNOWN_IDENTITY
    source_version: str = UNKNOWN_IDENTITY

    def __post_init__(self) -> None:
        """Normalize identity fields without treating blanks as evidence."""
        for name, value in self.to_dict().items():
            normalized = str(value).strip() or UNKNOWN_IDENTITY
            object.__setattr__(self, name, normalized)

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    @property
    def hash(self) -> str:
        return _content_hash(self.to_dict())

    @property
    def complete(self) -> bool:
        return all(value and value != UNKNOWN_IDENTITY for value in self.to_dict().values())


@dataclass(frozen=True)
class TrackedObstacle:
    """Validated dynamic-obstacle input presented to a custom MPC."""

    target_id: int
    state_enu: np.ndarray
    covariance: np.ndarray
    length_m: float
    width_m: float
    observed_at_s: float
    age_s: float
    degraded: bool = False
    generation: int | None = None
    status: str = "LEGACY_UNKNOWN"
    source: str = "legacy"
    generated_at_s: float | None = None

    def __post_init__(self) -> None:
        """Copy and validate one tracked obstacle."""
        if self.target_id < 0:
            raise ValueError("target_id must be non-negative")
        object.__setattr__(self, "state_enu", _readonly_array(self.state_enu, (4,), "track state"))
        covariance = _readonly_array(self.covariance, (4, 4), "track covariance")
        if not np.allclose(covariance, covariance.T, rtol=0.0, atol=1e-10):
            raise ValueError("track covariance must be symmetric")
        if float(np.min(np.linalg.eigvalsh(covariance))) < -1e-9:
            raise ValueError("track covariance must be positive semidefinite")
        object.__setattr__(self, "covariance", covariance)
        geometry = (self.length_m, self.width_m, self.observed_at_s, self.age_s)
        if not np.isfinite(geometry).all():
            raise ValueError("track geometry and timestamps must be finite")
        if self.length_m <= 0.0 or self.width_m <= 0.0:
            raise ValueError("track length_m and width_m must be positive")
        if self.observed_at_s < 0.0 or self.age_s < 0.0:
            raise ValueError("track timestamps and age must be non-negative")
        if self.generation is not None and self.generation < 1:
            raise ValueError("track generation must be positive when known")
        if not self.status or not self.source:
            raise ValueError("track status and source must be non-empty")
        generated_at_s = self.observed_at_s + self.age_s if self.generated_at_s is None else self.generated_at_s
        if not np.isfinite(generated_at_s) or generated_at_s < self.observed_at_s:
            raise ValueError("track generated_at_s must not precede observation")
        object.__setattr__(self, "generated_at_s", float(generated_at_s))

    @property
    def identity_known(self) -> bool:
        return self.generation is not None


@dataclass(frozen=True)
class PlannerInput:
    """Typed input constructed at the existing ICOLAV.plan boundary."""

    sim_time_s: float
    dt_sim_s: float
    waypoints_enu_m: np.ndarray
    speed_plan_mps: np.ndarray
    ownship_state: np.ndarray
    tracks: tuple[TrackedObstacle, ...]
    enc: senc.ENC | None
    goal_state: np.ndarray | None
    disturbance: stochasticity.DisturbanceData | None
    algorithm_seed: int
    coordinate_frame: str = "ENU"
    linear_unit: str = "SI"
    angle_unit: str = "rad"
    ownship_length_m: float = 15.0
    ownship_width_m: float = 4.0
    ownship_draft_m: float = 0.5
    ownship_model: str = "UNKNOWN"
    ownship_controller: str = "UNKNOWN"
    ownship_course_time_constant_s: float | None = None
    ownship_speed_time_constant_s: float | None = None
    ownship_max_turn_rate_rad_s: float | None = None

    def __post_init__(self) -> None:
        """Copy and validate all planner inputs."""
        if not np.isfinite(self.sim_time_s) or self.sim_time_s < 0.0:
            raise ValueError("sim_time_s must be finite and non-negative")
        if not np.isfinite(self.dt_sim_s) or self.dt_sim_s <= 0.0:
            raise ValueError("dt_sim_s must be finite and positive")
        waypoints = _readonly_matrix(self.waypoints_enu_m, 2, "waypoints_enu_m")
        if waypoints.shape[1] < 2:
            raise ValueError("waypoints_enu_m requires at least two columns")
        speed_plan = _readonly_vector(self.speed_plan_mps, "speed_plan_mps")
        if speed_plan.size != waypoints.shape[1]:
            raise ValueError("speed_plan_mps must align with waypoints_enu_m")
        object.__setattr__(self, "waypoints_enu_m", waypoints)
        object.__setattr__(self, "speed_plan_mps", speed_plan)
        object.__setattr__(self, "ownship_state", _readonly_array(self.ownship_state, (6,), "ownship_state"))
        object.__setattr__(self, "tracks", tuple(self.tracks))
        if any(not isinstance(track, TrackedObstacle) for track in self.tracks):
            raise TypeError("tracks must contain only TrackedObstacle values")
        target_ids = [track.target_id for track in self.tracks]
        if len(set(target_ids)) != len(target_ids):
            raise ValueError("track target_id values must be unique")
        if self.goal_state is not None:
            object.__setattr__(self, "goal_state", _readonly_array(self.goal_state, (6,), "goal_state"))
        if self.algorithm_seed < 0:
            raise ValueError("algorithm_seed must be non-negative")
        geometry = (self.ownship_length_m, self.ownship_width_m, self.ownship_draft_m)
        if not np.isfinite(geometry).all() or min(geometry) <= 0.0:
            raise ValueError("ownship geometry must be finite and positive")
        if not self.ownship_model.strip() or not self.ownship_controller.strip():
            raise ValueError("ownship model and controller identity are required")
        dynamics = (
            self.ownship_course_time_constant_s,
            self.ownship_speed_time_constant_s,
            self.ownship_max_turn_rate_rad_s,
        )
        if any(value is not None and (not np.isfinite(value) or value <= 0.0) for value in dynamics):
            raise ValueError("ownship dynamics metadata must be finite and positive when present")
        if (self.coordinate_frame, self.linear_unit, self.angle_unit) != ("ENU", "SI", "rad"):
            raise ValueError("PlannerInput requires ENU/SI/rad")


@dataclass(frozen=True)
class MPCSolution:
    """One native solve normalized to the public controller and trace contracts."""

    control_reference: np.ndarray
    predicted_trajectory: np.ndarray
    status: PlanStatus = PlanStatus.SUCCESS
    horizon_dt_s: float = 1.0
    objective: float | None = None
    iterations: int | None = None
    feasible: bool = True
    constraints: Mapping[str, Any] = field(default_factory=dict)
    target_predictions: Sequence[Mapping[str, Any]] = field(default_factory=tuple)
    algorithm_details: Mapping[str, Any] = field(default_factory=dict)
    control_trajectory: np.ndarray | None = None
    evidence: EvidenceEnvelope | None = None
    post_commit: Callable[[], Mapping[str, Any] | None] | None = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        """Copy and validate the normalized solver result."""
        object.__setattr__(
            self,
            "control_reference",
            _readonly_array(self.control_reference, (9, 1), "control_reference"),
        )
        object.__setattr__(
            self,
            "predicted_trajectory",
            _readonly_matrix(self.predicted_trajectory, 9, "predicted_trajectory"),
        )
        if self.control_trajectory is not None:
            object.__setattr__(
                self,
                "control_trajectory",
                _readonly_matrix(self.control_trajectory, 9, "control_trajectory"),
            )
        if isinstance(self.status, str):
            object.__setattr__(self, "status", PlanStatus(self.status))
        if not np.isfinite(self.horizon_dt_s) or self.horizon_dt_s <= 0.0:
            raise ValueError("horizon_dt_s must be finite and positive")
        if self.objective is not None and not np.isfinite(self.objective):
            raise ValueError("objective must be finite when present")
        if self.iterations is not None and self.iterations < 0:
            raise ValueError("iterations must be non-negative")
        if not isinstance(self.feasible, bool):
            raise TypeError("feasible must be bool")
        if not isinstance(self.constraints, Mapping):
            raise TypeError("constraints must be a mapping")
        if any(not isinstance(item, Mapping) for item in self.target_predictions):
            raise TypeError("target_predictions must contain mappings")
        if not isinstance(self.algorithm_details, Mapping):
            raise TypeError("algorithm_details must be a mapping")
        if self.evidence is not None and not isinstance(self.evidence, EvidenceEnvelope):
            raise TypeError("evidence must be EvidenceEnvelope when present")
        if self.post_commit is not None and not callable(self.post_commit):
            raise TypeError("post_commit must be callable when present")
        object.__setattr__(self, "constraints", _json_copy(self.constraints))
        object.__setattr__(self, "target_predictions", tuple(_json_copy(item) for item in self.target_predictions))
        object.__setattr__(self, "algorithm_details", _json_copy(self.algorithm_details))


class CustomMPCAdapter(ICOLAV):
    """Validate, schedule and expose one user MPC through ICOLAV."""

    def __init__(
        self,
        *,
        descriptor: AlgorithmDescriptor,
        solve: Callable[[PlannerInput], MPCSolution],
        context: FactoryContext,
        reset: Callable[[], None] | None = None,
        validate_hold: Callable[[PlannerInput, MPCSolution, float], Mapping[str, Any]] | None = None,
        capture_evidence: bool = False,
    ) -> None:
        if descriptor.algorithm_id != context.requested_algorithm:
            raise ColavExecutionError(
                PlanStatus.INVALID_INPUT,
                f"descriptor algorithm_id {descriptor.algorithm_id!r} does not match requested "
                f"{context.requested_algorithm!r}",
                source=FailureSource.ALGORITHM,
            )
        if not callable(solve):
            raise TypeError("solve must be callable")
        if reset is not None and not callable(reset):
            raise TypeError("reset must be callable")
        if validate_hold is not None and not callable(validate_hold):
            raise TypeError("validate_hold must be callable")
        if not isinstance(capture_evidence, bool):
            raise TypeError("capture_evidence must be bool")
        self.descriptor = descriptor
        self.context = context
        self._solve = solve
        self._reset_solver = reset
        self._validate_held_solution = validate_hold
        self._capture_evidence = capture_evidence
        self._build_identity = BuildIdentity()
        self._solve_period_s = context.solve_period_override_s or descriptor.execution_profile.solve_period_s
        self._solve_id = 0
        self._last_solve_time_s: float | None = None
        self._last_rejected_solve_time_s: float | None = None
        self._preserved_plan_until_s: float | None = None
        self._last_plan_time_s: float | None = None
        self._solution: MPCSolution | None = None
        self._current_plan = np.zeros((9, 1), dtype=float)
        self._consecutive_timeouts = 0
        self._effective_status = PlanStatus.SUCCESS
        self._pending_hold_replan_reason: str | None = None
        self._hold_acceptance: Mapping[str, Any] | None = None
        self._evidence_run_id = str(uuid.uuid4())
        self._evidence_epoch = 0
        self._evidence_seq = 0
        self._evidence_events: list[EvidenceEvent] = []
        self._evidence_cycle_start = 0
        self._evidence_window_start = 0
        self._evidence_envelope: EvidenceEnvelope | None = None
        self._evidence_history_envelope: EvidenceEnvelope | None = None
        self._evidence_artifact_reference: dict[str, object] | None = None
        self._evidence_receipt: dict[str, object] | None = None
        self._artifact_semantic_hashes: dict[str, str] = {}
        self._diagnostics = self._new_diagnostics()
        self._planner_trace = PlannerTrace(descriptor.algorithm_id, 0, 0.0, False)

    @property
    def build_identity(self) -> BuildIdentity:
        return self._build_identity

    @property
    def solve_period_s(self) -> float:
        return self._solve_period_s

    def attach_build_identity(self, identity: BuildIdentity) -> None:
        """Attach loader-computed identity exactly once before execution."""
        if self._solve_id or self._last_plan_time_s is not None:
            raise RuntimeError("build identity cannot change after planning starts")
        self._build_identity = identity
        self._diagnostics = self._new_diagnostics()

    def descriptor_document(self) -> dict[str, Any]:
        return self.descriptor.envelope(self._build_identity)

    def reset(self) -> None:
        reset_time_s = 0.0 if self._last_plan_time_s is None else self._last_plan_time_s
        if self._reset_solver is not None:
            self._reset_solver()
        self._solve_id = 0
        self._last_solve_time_s = None
        self._last_rejected_solve_time_s = None
        self._preserved_plan_until_s = None
        self._last_plan_time_s = None
        self._solution = None
        self._current_plan = np.zeros((9, 1), dtype=float)
        self._consecutive_timeouts = 0
        self._effective_status = PlanStatus.SUCCESS
        self._pending_hold_replan_reason = None
        self._hold_acceptance = None
        self._evidence_epoch += 1
        self._evidence_seq = 0
        self._evidence_events = []
        self._evidence_cycle_start = 0
        self._evidence_window_start = 0
        self._evidence_envelope = None
        self._evidence_history_envelope = None
        self._evidence_artifact_reference = None
        self._evidence_receipt = None
        self._artifact_semantic_hashes = {}
        if self._capture_evidence:
            self._append_evidence_event(
                EvidenceEventType.RESET,
                reset_time_s,
                payload={"reason": "adapter_reset"},
            )
        self._diagnostics = self._new_diagnostics()
        self._planner_trace = PlannerTrace(self.descriptor.algorithm_id, 0, 0.0, False)

    def plan(
        self,
        t: float,
        waypoints: np.ndarray,
        speed_plan: np.ndarray,
        ownship_state: np.ndarray,
        do_list: list[tuple[int, np.ndarray, np.ndarray, float, float]],
        enc: senc.ENC | None = None,
        goal_state: np.ndarray | None = None,
        w: stochasticity.DisturbanceData | None = None,
        **kwargs: Any,
    ) -> np.ndarray:
        if self._capture_evidence:
            try:
                raw_sim_time = float(t)
            except (TypeError, ValueError):
                raw_sim_time = 0.0
            evidence_sim_time = raw_sim_time if np.isfinite(raw_sim_time) and raw_sim_time >= 0.0 else 0.0
            self._poll_artifact_completions(evidence_sim_time)
            self._append_evidence_event(
                EvidenceEventType.CYCLE_STARTED,
                evidence_sim_time,
                payload={"raw_sim_time_valid": evidence_sim_time == raw_sim_time},
            )
        try:
            planner_input = self._planner_input(
                t,
                waypoints,
                speed_plan,
                ownship_state,
                do_list,
                enc,
                goal_state,
                w,
                kwargs,
            )
            self._validate_schedule(planner_input)
        except ColavExecutionError as exc:
            if self._capture_evidence:
                self._append_evidence_event(
                    EvidenceEventType.PLAN_FAILED,
                    evidence_sim_time,
                    terminal_outcome=TerminalOutcome.FAILED,
                )
                self._record_pre_input_failure(evidence_sim_time, exc)
            raise
        if self._capture_evidence:
            self._append_evidence_event(
                EvidenceEventType.INPUT_VALIDATED,
                planner_input.sim_time_s,
                payload={"track_count": len(planner_input.tracks)},
            )
        decision_time_s = self._last_solve_time_s
        if self._last_rejected_solve_time_s is not None:
            decision_time_s = max(decision_time_s or -math.inf, self._last_rejected_solve_time_s)
        should_solve = decision_time_s is None or (
            planner_input.sim_time_s + 1e-9 >= decision_time_s + self._solve_period_s
        )
        if should_solve:
            return self._execute_solve(planner_input)
        if self._preserved_plan_until_s is not None and planner_input.sim_time_s < self._preserved_plan_until_s - 1.0e-9:
            return self._execute_hold(planner_input)
        if self._validate_held_solution is not None and self._solution is not None and self._last_solve_time_s is not None:
            elapsed_s = planner_input.sim_time_s - self._last_solve_time_s
            try:
                self._hold_acceptance = self._validate_held_solution(planner_input, self._solution, elapsed_s)
            except ColavExecutionError as exc:
                self._pending_hold_replan_reason = str(exc.details.get("failure_code", "HOLD_REJECTED"))
                if self._capture_evidence:
                    self._append_evidence_event(
                        EvidenceEventType.REPLAN_REQUESTED,
                        planner_input.sim_time_s,
                        semantic_hash=(
                            self._solution.evidence.semantic_record.semantic_hash
                            if self._solution.evidence is not None
                            else None
                        ),
                        payload={"reason": self._pending_hold_replan_reason},
                    )
                return self._execute_solve(planner_input)
        return self._execute_hold(planner_input)

    def get_current_plan(self) -> np.ndarray:
        if self._solution is None:
            return self._current_plan.copy()
        return self._solution.predicted_trajectory.copy()

    def get_diagnostics(self) -> PlanDiagnostics:
        return self._diagnostics

    def get_colav_data(self) -> dict[str, Any]:
        return {
            "planner": self._planner_trace.to_dict(),
            "algorithm_descriptor": self.descriptor_document(),
        }

    def plot_results(self, ax_map: plt.Axes, enc: senc.ENC, plt_handles: dict, **kwargs: Any) -> dict:  # noqa: ARG002
        return plt_handles

    def _planner_input(
        self,
        t: float,
        waypoints: np.ndarray,
        speed_plan: np.ndarray,
        ownship_state: np.ndarray,
        do_list: list[tuple[int, np.ndarray, np.ndarray, float, float]],
        enc: senc.ENC | None,
        goal_state: np.ndarray | None,
        disturbance: stochasticity.DisturbanceData | None,
        kwargs: Mapping[str, Any],
    ) -> PlannerInput:
        try:
            dt_sim_s = float(kwargs.get("dt", 0.0))
            track_ages = kwargs.get("track_ages_s", {})
            tracks = []
            for raw_track in do_list:
                target_id, state, covariance, length, width = raw_track
                if isinstance(raw_track, TrackSnapshot):
                    age_s = raw_track.age_s
                    observed_at_s = raw_track.observed_at_s
                    generation = raw_track.key.generation
                    status = raw_track.status.value
                    source = raw_track.source
                    generated_at_s = raw_track.generated_at_s
                else:
                    age_s = float(track_ages.get(target_id, 0.0))
                    observed_at_s = max(0.0, float(t) - age_s)
                    generation = None
                    status = "LEGACY_UNKNOWN"
                    source = "legacy"
                    generated_at_s = float(t)
                if age_s > self.descriptor.execution_profile.max_track_age_s:
                    raise ValueError(f"track {target_id} age {age_s}s exceeds profile maximum")
                tracks.append(
                    TrackedObstacle(
                        target_id=int(target_id),
                        state_enu=state,
                        covariance=covariance,
                        length_m=float(length),
                        width_m=float(width),
                        observed_at_s=observed_at_s,
                        age_s=age_s,
                        degraded=age_s > self.descriptor.execution_profile.degraded_track_age_s,
                        generation=generation,
                        status=status,
                        source=source,
                        generated_at_s=generated_at_s,
                    )
                )
            planner_input = PlannerInput(
                sim_time_s=float(t),
                dt_sim_s=dt_sim_s,
                waypoints_enu_m=waypoints,
                speed_plan_mps=speed_plan,
                ownship_state=ownship_state,
                tracks=tuple(tracks),
                enc=enc,
                goal_state=goal_state if goal_state is not None and np.asarray(goal_state).size else None,
                disturbance=disturbance,
                algorithm_seed=self.context.algorithm_seed,
                ownship_length_m=float(kwargs.get("os_length", 15.0)),
                ownship_width_m=float(kwargs.get("os_width", 4.0)),
                ownship_draft_m=float(kwargs.get("os_draft", 0.5)),
                ownship_model=str(kwargs.get("os_model_name", "UNKNOWN")),
                ownship_controller=str(kwargs.get("os_controller_name", "UNKNOWN")),
                ownship_course_time_constant_s=_optional_positive(kwargs.get("os_course_time_constant_s")),
                ownship_speed_time_constant_s=_optional_positive(kwargs.get("os_speed_time_constant_s")),
                ownship_max_turn_rate_rad_s=_optional_positive(kwargs.get("os_max_turn_rate_radps")),
            )
            if self.descriptor.execution_profile.requires_enc and planner_input.enc is None:
                raise ValueError("algorithm execution profile requires ENC")
            return planner_input
        except ColavExecutionError:
            raise
        except Exception as exc:
            raise ColavExecutionError(
                PlanStatus.INVALID_INPUT,
                f"invalid PlannerInput: {exc}",
                source=FailureSource.SCENARIO,
            ) from exc

    def _validate_schedule(self, planner_input: PlannerInput) -> None:
        if self._last_plan_time_s is not None and planner_input.sim_time_s < self._last_plan_time_s - 1e-9:
            raise ColavExecutionError(
                PlanStatus.INVALID_INPUT,
                "simulation time moved backwards",
                source=FailureSource.ADAPTER,
            )
        ratio = self._solve_period_s / planner_input.dt_sim_s
        if not np.isclose(ratio, round(ratio), rtol=0.0, atol=1e-9):
            raise ColavExecutionError(
                PlanStatus.INVALID_INPUT,
                "solve_period_s must be an integer multiple of dt_sim_s",
                source=FailureSource.ADAPTER,
            )
        coverage = ((self.descriptor.state_samples or self.descriptor.horizon_steps) - 1) * self.descriptor.horizon_dt
        if coverage + 1e-9 < self._solve_period_s:
            raise ColavExecutionError(
                PlanStatus.INVALID_INPUT,
                "prediction horizon does not cover the next solve time",
                source=FailureSource.ALGORITHM,
            )
        self._last_plan_time_s = planner_input.sim_time_s

    def _execute_solve(self, planner_input: PlannerInput) -> np.ndarray:  # noqa: C901, PLR0912, PLR0915
        started = time.perf_counter()
        if self._capture_evidence:
            self._evidence_artifact_reference = None
            self._evidence_receipt = None
            self._append_evidence_event(
                EvidenceEventType.SOLVE_ATTEMPTED,
                planner_input.sim_time_s,
                payload={"next_solve_id": self._solve_id + 1},
            )
        try:
            solution = self._solve(planner_input)
        except ColavExecutionError as exc:
            if exc.details.get("preserve_accepted_plan") is True and self._solution is not None:
                elapsed_ms = (time.perf_counter() - started) * 1000.0
                self._last_rejected_solve_time_s = planner_input.sim_time_s
                self._preserved_plan_until_s = planner_input.sim_time_s + self._solve_period_s
                self._hold_acceptance = {
                    "accepted": True,
                    "mode": "ROLLING_PLAN_CONTINUATION",
                    "candidate_rejected": True,
                    "revision_reason": exc.details.get("revision_reason"),
                    "rolling_plan": exc.details.get("rolling_plan"),
                }
                command = self._execute_hold(planner_input)
                continuation = {
                    "solver_executed": True,
                    "candidate_committed": False,
                    "candidate_rejected": True,
                    "solver_attempt_elapsed_ms": elapsed_ms,
                    "revision_reason": exc.details.get("revision_reason"),
                    "rolling_plan": exc.details.get("rolling_plan"),
                }
                self._diagnostics.elapsed_ms = elapsed_ms
                self._diagnostics.details.update(continuation)
                self._planner_trace.solver_executed = True
                self._planner_trace.elapsed_ms = elapsed_ms
                self._planner_trace.algorithm_details.update(continuation)
                return command
            self._record_execution_failure(
                planner_input,
                exc,
                elapsed_ms=(time.perf_counter() - started) * 1000.0,
            )
            raise
        except ImportError as exc:
            error = ColavExecutionError(
                PlanStatus.DEPENDENCY_UNAVAILABLE,
                f"custom MPC dependency unavailable: {exc}",
                source=FailureSource.ALGORITHM,
            )
            self._record_execution_failure(planner_input, error, elapsed_ms=(time.perf_counter() - started) * 1000.0)
            raise error from exc
        except Exception as exc:
            error = ColavExecutionError(
                PlanStatus.NUMERICAL_FAILURE,
                f"custom MPC solve failed: {exc}",
                source=FailureSource.ALGORITHM,
            )
            self._record_execution_failure(planner_input, error, elapsed_ms=(time.perf_counter() - started) * 1000.0)
            raise error from exc
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        try:
            self._validate_solution(solution, planner_input)
        except ColavExecutionError as exc:
            self._record_execution_failure(planner_input, exc, elapsed_ms=elapsed_ms)
            raise
        except Exception as exc:
            error = ColavExecutionError(
                PlanStatus.INVALID_INPUT,
                f"invalid MPCSolution: {exc}",
                source=FailureSource.ALGORITHM,
            )
            self._record_execution_failure(planner_input, error, elapsed_ms=elapsed_ms)
            raise error from exc

        status = solution.status
        strict_total_deadline = bool(solution.algorithm_details.get("strict_total_deadline", False))
        if (
            self.context.deadline_mode == DeadlineMode.ENFORCE
            and elapsed_ms > self.descriptor.execution_profile.deadline_s * 1000.0
            and status == PlanStatus.SUCCESS
        ):
            status = PlanStatus.TIMEOUT_FEASIBLE if solution.feasible else PlanStatus.NUMERICAL_FAILURE
        if status == PlanStatus.TIMEOUT_FEASIBLE:
            self._consecutive_timeouts += 1
        else:
            self._consecutive_timeouts = 0
        if self._consecutive_timeouts > self.descriptor.execution_profile.max_consecutive_timeout:
            error = ColavExecutionError(
                PlanStatus.NUMERICAL_FAILURE,
                "REALTIME: consecutive TIMEOUT_FEASIBLE limit exceeded",
                source=FailureSource.ALGORITHM,
            )
            self._record_execution_failure(planner_input, error, elapsed_ms=elapsed_ms)
            raise error
        if status not in {PlanStatus.SUCCESS, PlanStatus.TIMEOUT_FEASIBLE}:
            error = ColavExecutionError(
                status,
                f"custom MPC returned {status.value}",
                source=FailureSource.ALGORITHM,
            )
            self._record_execution_failure(planner_input, error, elapsed_ms=elapsed_ms)
            raise error
        if not solution.feasible:
            error = ColavExecutionError(
                PlanStatus.NUMERICAL_FAILURE,
                f"{status.value} requires feasible=true",
                source=FailureSource.ALGORITHM,
            )
            self._record_execution_failure(planner_input, error, elapsed_ms=elapsed_ms)
            raise error

        next_solve_id = self._solve_id + 1
        next_plan = solution.control_reference.copy()
        details = {
            **dict(solution.algorithm_details),
            "solve_time_s": planner_input.sim_time_s,
            "descriptor_hash": self.descriptor.hash,
            "build_identity_hash": self._build_identity.hash,
            "deadline_mode": self.context.deadline_mode.value,
        }
        if self._pending_hold_replan_reason is not None:
            details["hold_replan_reason"] = self._pending_hold_replan_reason
        next_diagnostics = PlanDiagnostics(
            status=status,
            elapsed_ms=elapsed_ms,
            iterations=solution.iterations,
            feasible=solution.feasible,
            objective=solution.objective,
            requested_algorithm=self.context.requested_algorithm,
            executed_algorithm=self.descriptor.algorithm_id,
            fallback_used=False,
            algorithm_descriptor=self.descriptor_document(),
            details={"solve_id": next_solve_id, "solver_executed": True, **details},
        )
        terminal_event_index: int | None = None
        if solution.evidence is not None:
            self._evidence_envelope = solution.evidence
            semantic_hash = solution.evidence.semantic_record.semantic_hash
            self._append_evidence_event(
                EvidenceEventType.CANDIDATE_PRODUCED,
                planner_input.sim_time_s,
                semantic_hash=semantic_hash,
                derived_from=(
                    solution.evidence.semantic_record.candidate_hash,
                    solution.evidence.semantic_record.acceptance_hash,
                ),
            )
            self._append_evidence_event(
                EvidenceEventType.L4_EVALUATED,
                planner_input.sim_time_s,
                semantic_hash=semantic_hash,
                derived_from=(solution.evidence.semantic_record.acceptance_hash,),
                payload={
                    "accepted": solution.evidence.semantic_record.acceptance.get("accepted"),
                    "acceptance_hash": solution.evidence.semantic_record.acceptance_hash,
                },
            )
            receipt = solution.algorithm_details.get("accepted_plan_receipt", {})
            receipt_hash = receipt.get("receipt_hash") if isinstance(receipt, Mapping) else None
            if not isinstance(receipt_hash, str) or not receipt_hash:
                error = ColavExecutionError(
                    PlanStatus.INVALID_INPUT,
                    "Prediction Evidence requires a committed receipt hash",
                    source=FailureSource.ALGORITHM,
                )
                self._record_execution_failure(
                    planner_input,
                    error,
                    elapsed_ms=(time.perf_counter() - started) * 1000.0,
                )
                raise error
            self._evidence_receipt = dict(receipt)
            terminal_event_index = len(self._evidence_events)
            self._append_evidence_event(
                EvidenceEventType.PLAN_COMMITTED,
                planner_input.sim_time_s,
                semantic_hash=semantic_hash,
                terminal_outcome=TerminalOutcome.COMMITTED,
                derived_from=(semantic_hash, receipt_hash),
                payload={"receipt_hash": receipt_hash},
            )
            self._append_evidence_event(
                EvidenceEventType.COMMAND_APPLIED,
                planner_input.sim_time_s,
                semantic_hash=semantic_hash,
                derived_from=(receipt_hash,),
                payload=_selected_command(next_plan),
            )
        evidence_fields = self._evidence_trace_fields(solution, elapsed_s=0.0)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        if (
            strict_total_deadline
            and self.context.deadline_mode == DeadlineMode.ENFORCE
            and elapsed_ms > self.descriptor.execution_profile.deadline_s * 1000.0
        ):
            if terminal_event_index is not None:
                del self._evidence_events[terminal_event_index:]
                self._evidence_seq = terminal_event_index
            error = ColavExecutionError(
                PlanStatus.NUMERICAL_FAILURE,
                "REALTIME: Prediction Evidence transaction missed total commit deadline",
                source=FailureSource.ADAPTER,
                details={"failure_code": "TOTAL_DEADLINE_EXCEEDED"},
            )
            self._record_execution_failure(planner_input, error, elapsed_ms=elapsed_ms)
            raise error
        details["commit_elapsed_ms"] = elapsed_ms
        next_diagnostics.elapsed_ms = elapsed_ms
        next_diagnostics.details["commit_elapsed_ms"] = elapsed_ms
        next_trace = PlannerTrace(
            algorithm_id=self.descriptor.algorithm_id,
            solve_id=next_solve_id,
            sim_time=planner_input.sim_time_s,
            solver_executed=True,
            status=status,
            feasible=solution.feasible,
            elapsed_ms=elapsed_ms,
            iterations=solution.iterations,
            objective=solution.objective,
            predicted_trajectory=solution.predicted_trajectory,
            horizon_dt_s=solution.horizon_dt_s,
            selected_command=_selected_command(next_plan),
            target_predictions=list(solution.target_predictions),
            constraints=dict(solution.constraints),
            algorithm_details=details,
            **evidence_fields,
        )
        self._solution = solution
        self._effective_status = status
        self._last_solve_time_s = planner_input.sim_time_s
        self._last_rejected_solve_time_s = None
        self._preserved_plan_until_s = None
        self._solve_id = next_solve_id
        self._current_plan = next_plan
        self._diagnostics = next_diagnostics
        self._planner_trace = next_trace
        if solution.evidence is not None:
            self._evidence_history_envelope = solution.evidence
        self._pending_hold_replan_reason = None
        self._hold_acceptance = None
        if solution.post_commit is not None:
            try:
                artifact = solution.post_commit()
            except Exception as exc:  # commit is authoritative; evidence callback cannot revoke it
                artifact = {
                    "status": "INCOMPLETE",
                    "reason": "POST_COMMIT_CALLBACK_FAILED",
                    "error_type": type(exc).__name__,
                }
            if artifact is not None:
                details["assembly"]["artifact"] = dict(artifact)
                self._diagnostics.details["assembly"]["artifact"] = dict(artifact)
                self._planner_trace.algorithm_details["assembly"]["artifact"] = dict(artifact)
                self._record_artifact_status(artifact, planner_input.sim_time_s)
                updated_evidence = self._evidence_trace_fields(solution, elapsed_s=0.0)
                self._planner_trace.schema_version = str(updated_evidence.get("schema_version", "1.0"))
                self._planner_trace.evidence = updated_evidence.get("evidence")  # type: ignore[assignment]
                self._planner_trace.evidence_timeline = updated_evidence.get("evidence_timeline")  # type: ignore[assignment]
                self._planner_trace.prediction_render = updated_evidence.get("prediction_render")  # type: ignore[assignment]
        return self._current_plan.copy()

    def _record_execution_failure(
        self,
        planner_input: PlannerInput,
        error: ColavExecutionError,
        *,
        elapsed_ms: float,
    ) -> None:
        if self._capture_evidence:
            if isinstance(error.evidence, EvidenceEnvelope):
                self._evidence_envelope = error.evidence
                self._append_evidence_event(
                    EvidenceEventType.CANDIDATE_PRODUCED,
                    planner_input.sim_time_s,
                    semantic_hash=error.evidence.semantic_record.semantic_hash,
                    derived_from=(
                        error.evidence.semantic_record.candidate_hash,
                        error.evidence.semantic_record.acceptance_hash,
                    ),
                )
                self._append_evidence_event(
                    EvidenceEventType.L4_EVALUATED,
                    planner_input.sim_time_s,
                    semantic_hash=error.evidence.semantic_record.semantic_hash,
                    derived_from=(error.evidence.semantic_record.acceptance_hash,),
                    payload={
                        "accepted": error.evidence.semantic_record.acceptance.get("accepted"),
                        "acceptance_hash": error.evidence.semantic_record.acceptance_hash,
                    },
                )
            rejected = error.details.get("failure_code") == "L4_PLAN_REJECTED"
            self._append_evidence_event(
                EvidenceEventType.PLAN_REJECTED if rejected else EvidenceEventType.PLAN_FAILED,
                planner_input.sim_time_s,
                semantic_hash=(
                    self._evidence_envelope.semantic_record.semantic_hash if self._evidence_envelope is not None else None
                ),
                terminal_outcome=TerminalOutcome.REJECTED if rejected else TerminalOutcome.FAILED,
                payload={"failure_code": error.details.get("failure_code", error.status.value)},
            )
            artifact = error.details.get("artifact")
            if isinstance(artifact, Mapping):
                self._record_artifact_status(artifact, planner_input.sim_time_s)
        self._solution = None
        self._last_solve_time_s = None
        self._current_plan = np.zeros((9, 1), dtype=float)
        details = {
            **error.details,
            "solve_id": self._solve_id,
            "solver_executed": False,
            "cached_plan_used": False,
            "failure_source": (error.source.value if error.source is not None else FailureSource.ALGORITHM.value),
            "descriptor_hash": self.descriptor.hash,
            "build_identity_hash": self._build_identity.hash,
            "deadline_mode": self.context.deadline_mode.value,
        }
        if self._pending_hold_replan_reason is not None:
            details["hold_replan_reason"] = self._pending_hold_replan_reason
        self._diagnostics = PlanDiagnostics(
            status=error.status,
            elapsed_ms=elapsed_ms,
            feasible=False,
            requested_algorithm=self.context.requested_algorithm,
            executed_algorithm=self.descriptor.algorithm_id,
            fallback_used=False,
            algorithm_descriptor=self.descriptor_document(),
            details=details,
        )
        self._planner_trace = PlannerTrace(
            algorithm_id=self.descriptor.algorithm_id,
            solve_id=self._solve_id,
            sim_time=planner_input.sim_time_s,
            solver_executed=False,
            status=error.status,
            feasible=False,
            elapsed_ms=elapsed_ms,
            reason=str(error),
            algorithm_details=details,
            **self._evidence_trace_fields(None, elapsed_s=None),
        )
        self._pending_hold_replan_reason = None
        self._hold_acceptance = None

    def _record_pre_input_failure(self, sim_time_s: float, error: ColavExecutionError) -> None:
        self._solution = None
        self._last_solve_time_s = None
        self._current_plan = np.zeros((9, 1), dtype=float)
        details = {
            **error.details,
            "solve_id": self._solve_id,
            "solver_executed": False,
            "cached_plan_used": False,
            "failure_source": (error.source.value if error.source is not None else FailureSource.ADAPTER.value),
            "descriptor_hash": self.descriptor.hash,
            "build_identity_hash": self._build_identity.hash,
            "deadline_mode": self.context.deadline_mode.value,
        }
        self._diagnostics = PlanDiagnostics(
            status=error.status,
            elapsed_ms=0.0,
            feasible=False,
            requested_algorithm=self.context.requested_algorithm,
            executed_algorithm=self.descriptor.algorithm_id,
            fallback_used=False,
            algorithm_descriptor=self.descriptor_document(),
            details=details,
        )
        self._planner_trace = PlannerTrace(
            algorithm_id=self.descriptor.algorithm_id,
            solve_id=self._solve_id,
            sim_time=sim_time_s,
            solver_executed=False,
            status=error.status,
            feasible=False,
            reason=str(error),
            algorithm_details=details,
            **self._evidence_trace_fields(None, elapsed_s=None),
        )
        self._hold_acceptance = None

    def _execute_hold(self, planner_input: PlannerInput) -> np.ndarray:
        if self._solution is None or self._last_solve_time_s is None:
            raise ColavExecutionError(
                PlanStatus.NUMERICAL_FAILURE,
                "hold requested before first solve",
                source=FailureSource.ADAPTER,
            )
        elapsed_s = planner_input.sim_time_s - self._last_solve_time_s
        executable_trajectory = (
            self._solution.control_trajectory
            if self._solution.control_trajectory is not None
            else self._solution.predicted_trajectory
        )
        self._current_plan = _sample_trajectory(
            executable_trajectory,
            self._solution.horizon_dt_s,
            elapsed_s,
        )
        details = {
            **dict(self._solution.algorithm_details),
            "solve_time_s": self._last_solve_time_s,
            "trajectory_source": "held_plan",
            "held_elapsed_s": elapsed_s,
            "descriptor_hash": self.descriptor.hash,
            "build_identity_hash": self._build_identity.hash,
            "deadline_mode": self.context.deadline_mode.value,
        }
        if self._hold_acceptance is not None:
            details["hold_acceptance"] = dict(self._hold_acceptance)
            if self._hold_acceptance.get("mode") == "ROLLING_PLAN_CONTINUATION":
                details.update(
                    {
                        "candidate_committed": False,
                        "candidate_rejected": True,
                        "revision_reason": self._hold_acceptance.get("revision_reason"),
                        "rolling_plan": self._hold_acceptance.get("rolling_plan"),
                    }
                )
        self._diagnostics = PlanDiagnostics(
            status=self._effective_status,
            elapsed_ms=0.0,
            iterations=self._solution.iterations,
            feasible=self._solution.feasible,
            objective=self._solution.objective,
            requested_algorithm=self.context.requested_algorithm,
            executed_algorithm=self.descriptor.algorithm_id,
            fallback_used=False,
            algorithm_descriptor=self.descriptor_document(),
            details={"solve_id": self._solve_id, "solver_executed": False, **details},
        )
        if self._solution.evidence is not None:
            semantic_hash = self._solution.evidence.semantic_record.semantic_hash
            self._append_evidence_event(
                EvidenceEventType.PLAN_HELD,
                planner_input.sim_time_s,
                semantic_hash=semantic_hash,
                terminal_outcome=TerminalOutcome.HELD,
                payload={"elapsed_s": elapsed_s},
            )
            self._append_evidence_event(
                EvidenceEventType.COMMAND_APPLIED,
                planner_input.sim_time_s,
                semantic_hash=semantic_hash,
                payload=_selected_command(self._current_plan),
            )
        self._planner_trace = PlannerTrace(
            algorithm_id=self.descriptor.algorithm_id,
            solve_id=self._solve_id,
            sim_time=planner_input.sim_time_s,
            solver_executed=False,
            status=self._effective_status,
            feasible=self._solution.feasible,
            predicted_trajectory=self._solution.predicted_trajectory,
            horizon_dt_s=self._solution.horizon_dt_s,
            selected_command=_selected_command(self._current_plan),
            target_predictions=list(self._solution.target_predictions),
            constraints=dict(self._solution.constraints),
            algorithm_details=details,
            **self._evidence_trace_fields(self._solution, elapsed_s=elapsed_s),
        )
        return self._current_plan.copy()

    def _validate_solution(self, solution: MPCSolution, planner_input: PlannerInput) -> None:
        if not isinstance(solution, MPCSolution):
            raise TypeError("solve callable must return MPCSolution")
        if self._capture_evidence:
            if solution.evidence is None:
                raise ValueError("Prediction Evidence is required before Mid-MPC command commit")
            solution.evidence.to_inline_dict()
        trajectory = solution.predicted_trajectory
        expected_state_samples = self.descriptor.state_samples or self.descriptor.horizon_steps
        if trajectory.shape[1] != expected_state_samples:
            raise ValueError(
                f"predicted horizon has {trajectory.shape[1]} samples; descriptor requires {expected_state_samples}"
            )
        if not np.isclose(solution.horizon_dt_s, self.descriptor.horizon_dt, rtol=0.0, atol=1e-12):
            raise ValueError("MPCSolution horizon_dt_s differs from descriptor")
        if solution.control_trajectory is not None and solution.control_trajectory.shape[1] != self.descriptor.horizon_steps:
            raise ValueError(
                f"control horizon has {solution.control_trajectory.shape[1]} steps; descriptor requires "
                f"{self.descriptor.horizon_steps}"
            )
        profile = self.descriptor.execution_profile
        position_error = float(np.linalg.norm(trajectory[:2, 0] - planner_input.ownship_state[:2]))
        heading_error = abs(_wrap_angle(float(trajectory[2, 0] - planner_input.ownship_state[2])))
        state_error = float(np.max(np.abs(trajectory[3:6, 0] - planner_input.ownship_state[3:6])))
        if position_error > profile.first_state_tolerance_m:
            raise ValueError(f"trajectory col-0 position error {position_error:.6g}m exceeds tolerance")
        if heading_error > profile.first_state_tolerance_rad:
            raise ValueError(f"trajectory col-0 heading error {heading_error:.6g}rad exceeds tolerance")
        if state_error > profile.state_tolerance:
            raise ValueError(f"trajectory col-0 velocity error {state_error:.6g} exceeds tolerance")
        if trajectory.shape[1] > 1:
            displacement = np.linalg.norm(np.diff(trajectory[:2], axis=1), axis=0)
            speed = np.hypot(trajectory[3], trajectory[4])
            acceleration = np.hypot(trajectory[6], trajectory[7])
            motion_bound = (
                np.maximum(speed[:-1], speed[1:]) * solution.horizon_dt_s
                + 0.5 * np.maximum(acceleration[:-1], acceleration[1:]) * solution.horizon_dt_s**2
                + profile.first_state_tolerance_m
            )
            if np.any(displacement > motion_bound + 1e-9):
                raise ValueError("predicted trajectory violates translational motion continuity")
        if solution.status in {PlanStatus.SUCCESS, PlanStatus.TIMEOUT_FEASIBLE} and not solution.feasible:
            raise ValueError(f"{solution.status.value} requires feasible=true")

    def _append_evidence_event(
        self,
        event_type: EvidenceEventType,
        sim_time_s: float,
        *,
        semantic_hash: str | None = None,
        terminal_outcome: TerminalOutcome | None = None,
        derived_from: Sequence[str] = (),
        payload: Mapping[str, object] | None = None,
    ) -> None:
        if event_type is EvidenceEventType.CYCLE_STARTED:
            self._evidence_cycle_start = len(self._evidence_events)
        caused_by = self._evidence_events[-1].occurrence_id if self._evidence_events else None
        event = EvidenceEvent(
            occurrence_id=OccurrenceId(
                run_id=self._evidence_run_id,
                epoch=self._evidence_epoch,
                event_seq=self._evidence_seq,
            ),
            event_type=event_type,
            sim_time_s=sim_time_s,
            semantic_hash=semantic_hash,
            terminal_outcome=terminal_outcome,
            caused_by=caused_by,
            derived_from=tuple(derived_from),
            payload={} if payload is None else payload,
        )
        self._evidence_events.append(event)
        if event_type in {
            EvidenceEventType.PLAN_COMMITTED,
            EvidenceEventType.PLAN_REJECTED,
            EvidenceEventType.PLAN_FAILED,
        }:
            self._evidence_window_start = self._evidence_cycle_start
        self._evidence_seq += 1

    def _runtime_evidence_events(self) -> tuple[EvidenceEvent, ...]:
        events = tuple(self._evidence_events[self._evidence_window_start :])
        if self._evidence_window_start == 0 or not events:
            return events
        first = replace(events[0], caused_by=None)
        epoch_event = self._evidence_events[0]
        if epoch_event.event_type is EvidenceEventType.RESET:
            return (epoch_event, first, *events[1:])
        return (first, *events[1:])

    def _record_artifact_status(self, artifact: Mapping[str, object], sim_time_s: float) -> None:
        if not self._capture_evidence or self._evidence_envelope is None:
            return
        status = str(artifact.get("status", "COMPLETE")).upper()
        self._evidence_artifact_reference = dict(artifact)
        event_by_status = {
            "QUEUED": EvidenceEventType.ARTIFACT_QUEUED,
            "COMPLETE": EvidenceEventType.ARTIFACT_COMPLETE,
            "INCOMPLETE": EvidenceEventType.ARTIFACT_INCOMPLETE,
            "BACKPRESSURE": EvidenceEventType.ARTIFACT_BACKPRESSURE,
            "NOT_CONFIGURED": EvidenceEventType.ARTIFACT_INCOMPLETE,
        }
        event_type = event_by_status.get(status, EvidenceEventType.ARTIFACT_INCOMPLETE)
        semantic_hash = self._evidence_envelope.semantic_record.semantic_hash
        submission_id = artifact.get("submission_id")
        if status == "QUEUED" and isinstance(submission_id, str) and submission_id:
            self._artifact_semantic_hashes[submission_id] = semantic_hash
        self._append_evidence_event(
            event_type,
            sim_time_s,
            semantic_hash=semantic_hash,
            payload=dict(artifact),
        )

    def _poll_artifact_completions(self, sim_time_s: float) -> None:
        sink = self.context.artifact_sink
        poll = getattr(sink, "poll_completions", None)
        if not callable(poll):
            return
        for completion in poll():
            if not isinstance(completion, Mapping):
                continue
            submission_id = completion.get("submission_id")
            semantic_hash = (
                self._artifact_semantic_hashes.pop(submission_id, None) if isinstance(submission_id, str) else None
            )
            if semantic_hash is None:
                continue
            status = str(completion.get("status", "INCOMPLETE")).upper()
            event_type = {
                "COMPLETE": EvidenceEventType.ARTIFACT_COMPLETE,
                "BACKPRESSURE": EvidenceEventType.ARTIFACT_BACKPRESSURE,
            }.get(status, EvidenceEventType.ARTIFACT_INCOMPLETE)
            self._append_evidence_event(
                event_type,
                sim_time_s,
                semantic_hash=semantic_hash,
                payload=dict(completion),
            )

    def _evidence_trace_fields(
        self,
        solution: MPCSolution | None,
        *,
        elapsed_s: float | None,
    ) -> dict[str, object]:
        envelope = solution.evidence if solution is not None and solution.evidence is not None else self._evidence_envelope
        if envelope is None:
            if not self._capture_evidence:
                return {}
            return {
                "schema_version": "1.1",
                "evidence": None,
                "evidence_timeline": reduce_evidence(self._runtime_evidence_events()).to_dict(),
                "prediction_render": None,
            }
        timeline = reduce_evidence(self._runtime_evidence_events())
        runtime_reference: RuntimeAppliedReference | None = None
        if solution is not None and elapsed_s is not None:
            executable = (
                solution.control_trajectory if solution.control_trajectory is not None else solution.predicted_trajectory
            )
            runtime_reference = RuntimeAppliedReference.linear(
                elapsed_s=elapsed_s,
                dt_s=solution.horizon_dt_s,
                heading_rad=executable[2],
                speed_mps=np.hypot(executable[3], executable[4]),
            )
        prediction_render = render_snapshot(
            envelope.semantic_record,
            timeline,
            runtime_reference=runtime_reference,
        )
        history = self._evidence_history_envelope
        if history is not None and history.semantic_record.semantic_hash != envelope.semantic_record.semantic_hash:
            history_render = render_snapshot(history.semantic_record, timeline)
            history_render["style"] = "INVALID_HISTORY"
            history_render["executable"] = False
            prediction_render["history"] = history_render
        else:
            prediction_render["history"] = None
        return {
            "schema_version": "1.1",
            "evidence": envelope.to_inline_dict(
                artifact_reference=self._evidence_artifact_reference,
                authority={
                    "latest_terminal_outcome": (
                        timeline.latest_terminal_outcome.value if timeline.latest_terminal_outcome is not None else None
                    ),
                    "active_semantic_hash": timeline.active_semantic_hash,
                    "active_receipt_hash": timeline.active_receipt_hash,
                    "last_committed_semantic_hash": timeline.last_committed_semantic_hash,
                    "last_committed_executable": timeline.last_committed_executable,
                    "artifact_state": timeline.artifact_state.value,
                    "receipt": (
                        self._evidence_receipt
                        if self._evidence_receipt is not None
                        and self._evidence_receipt.get("receipt_hash") == timeline.active_receipt_hash
                        else None
                    ),
                },
            ),
            "evidence_timeline": timeline.to_dict(),
            "prediction_render": prediction_render,
        }

    def _new_diagnostics(self) -> PlanDiagnostics:
        return PlanDiagnostics(
            requested_algorithm=self.context.requested_algorithm,
            executed_algorithm=self.descriptor.algorithm_id,
            fallback_used=False,
            algorithm_descriptor=self.descriptor.envelope(self._build_identity),
        )


def _readonly_array(value: Any, shape: tuple[int, ...], name: str) -> np.ndarray:
    array = np.array(value, dtype=float, copy=True)
    if array.shape != shape:
        raise ValueError(f"{name} must have shape {shape}, got {array.shape}")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} must contain only finite values")
    array.setflags(write=False)
    return array


def _readonly_matrix(value: Any, rows: int, name: str) -> np.ndarray:
    array = np.array(value, dtype=float, copy=True)
    if array.ndim != 2 or array.shape[0] != rows or array.shape[1] < 1:
        raise ValueError(f"{name} must have shape ({rows}, N>=1), got {array.shape}")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} must contain only finite values")
    array.setflags(write=False)
    return array


def _readonly_vector(value: Any, name: str) -> np.ndarray:
    array = np.array(value, dtype=float, copy=True)
    if array.ndim != 1 or array.size < 1:
        raise ValueError(f"{name} must be a non-empty vector, got {array.shape}")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} must contain only finite values")
    array.setflags(write=False)
    return array


def _string_tuple(value: Sequence[str], name: str) -> tuple[str, ...]:
    output = tuple(str(item).strip() for item in value)
    if not output or any(not item for item in output):
        raise ValueError(f"{name} must contain non-empty strings")
    if len(set(output)) != len(output):
        raise ValueError(f"{name} must not contain duplicates")
    return output


def _optional_positive(value: Any) -> float | None:
    if value is None:
        return None
    result = float(value)
    if not np.isfinite(result) or result <= 0.0:
        raise ValueError("optional dynamics value must be finite and positive")
    return result


def _content_hash(value: Mapping[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _json_copy(value: Any) -> Any:
    return json.loads(json.dumps(value, sort_keys=True, allow_nan=False, default=_json_default))


def _json_default(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, StrEnum):
        return value.value
    raise TypeError(f"{type(value).__name__} is not JSON serializable")


def _selected_command(plan: np.ndarray) -> dict[str, float]:
    return {
        "course_rad": float(plan[2, 0]),
        "speed_mps": float(plan[3, 0]),
    }


def _sample_trajectory(trajectory: np.ndarray, dt_s: float, elapsed_s: float) -> np.ndarray:
    position = max(0.0, elapsed_s / dt_s)
    lower = min(int(np.floor(position)), trajectory.shape[1] - 1)
    upper = min(lower + 1, trajectory.shape[1] - 1)
    fraction = min(max(position - lower, 0.0), 1.0)
    sample = (1.0 - fraction) * trajectory[:, lower] + fraction * trajectory[:, upper]
    heading_delta = _wrap_angle(float(trajectory[2, upper] - trajectory[2, lower]))
    sample[2] = _wrap_angle(float(trajectory[2, lower] + fraction * heading_delta))
    return sample.reshape(9, 1)


def _wrap_angle(value: float) -> float:
    return float((value + np.pi) % (2.0 * np.pi) - np.pi)
