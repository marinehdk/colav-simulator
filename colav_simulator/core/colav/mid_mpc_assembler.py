"""Stateless mapping from lifecycle decisions to the frozen Mid-MPC core."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, replace
from enum import StrEnum
from typing import Any

import numpy as np

from colav_simulator.core.colav.custom_mpc_adapter import PlannerInput, TrackedObstacle
from colav_simulator.core.colav.encounter_lifecycle import (
    CommitmentPhase,
    DecisionSnapshot,
    EncounterKind,
    OwnshipRole,
    PassingSide,
    RiskPhase,
    Rule17Stage,
    TargetDecision,
)
from colav_simulator.core.colav.horizon_encounter_plan import (
    HorizonEncounterPhase,
    HorizonEncounterPlan,
    HorizonEncounterPlanRequest,
    HorizonTargetIntent,
    TargetPrediction,
    compile_horizon_encounter_plan,
    horizon_encounter_plan_document,
)
from colav_simulator.core.colav.mid_mpc import (
    MidMpcHardWindow,
    MidMpcOwnShip,
    MidMpcProblem,
    MidMpcRouteFrame,
    MidMpcRouteObjective,
    MidMpcRowSchedule,
    MidMpcTarget,
)
from colav_simulator.core.colav.mid_mpc_arrival import arrival_references, on_final_leg, terminal_weight
from colav_simulator.core.colav.mid_mpc_static import (
    compile_static_field,
    held_course_clears_static_hazards,
    static_execution_context,
)
from colav_simulator.core.colav.retained_route import (
    RetainedPrefixPlan,
    _UnreachablePrefix,
    compile_retained_prefix,
    degraded_stub_prefix,
)
from colav_simulator.core.colav.rolling_plan import RollingPlanReference
from colav_simulator.core.tracking.trackers import TrackKey


@dataclass(frozen=True)
class MidMpcAssemblyConfig:
    horizon_steps: int = 80
    horizon_dt_s: float = 5.0
    heading_window_rad: float = math.radians(45.0)
    # Numerical search envelope used only after every encounter has released
    # the route.  This is a planner-domain allowance, not a GNC turn-rate or
    # safety relaxation; active encounter bounds remain at heading_window_rad.
    recovery_heading_window_rad: float = math.radians(90.0)
    stand_on_course_tolerance_rad: float = math.radians(5.0)
    speed_bounds_mps: tuple[float, float] = (0.0, 8.0)
    cpa_safe_m: float = 150.0
    cpa_hard_m: float = 50.0
    rot_max_rad_s: float = math.radians(3.0)
    decel_max_mps2: float = 0.3
    route_lateral_scale_m: float = 1000.0
    route_weight: float = 1.0
    decision_period_s: float = 10.0
    max_targets: int = 16

    def __post_init__(self) -> None:
        """Validate the phase-specific numerical search envelopes."""
        if not np.isfinite((self.heading_window_rad, self.recovery_heading_window_rad)).all():
            raise ValueError("heading search windows must be finite")
        if self.heading_window_rad <= 0.0 or self.recovery_heading_window_rad <= 0.0:
            raise ValueError("heading search windows must be positive")
        if self.recovery_heading_window_rad > math.pi:
            raise ValueError("recovery heading search window cannot exceed pi")


@dataclass(frozen=True)
class RouteReference:
    anchor_ne_m: tuple[float, float]
    bearing_rad: float
    mission_leg_bearing_rad: float
    planned_speed_mps: float
    mission_waypoints_ne_m: tuple[tuple[float, float], ...] = ()

    def __post_init__(self) -> None:
        """Validate immutable route evidence."""
        values = (
            *self.anchor_ne_m,
            self.bearing_rad,
            self.mission_leg_bearing_rad,
            self.planned_speed_mps,
        )
        if not np.isfinite(values).all():
            raise ValueError("route reference values must be finite")
        waypoints = tuple((float(point[0]), float(point[1])) for point in self.mission_waypoints_ne_m)
        if waypoints and len(waypoints) < 2:
            raise ValueError("mission route requires at least two waypoints when supplied")
        if waypoints and not np.isfinite(waypoints).all():
            raise ValueError("mission route waypoints must be finite")
        object.__setattr__(self, "mission_waypoints_ne_m", waypoints)


@dataclass(frozen=True)
class CapabilitySnapshot:
    heading_window_rad: float
    speed_bounds_mps: tuple[float, float]
    rot_max_rad_s: float
    decel_max_mps2: float
    odd_source: str = "published_kinematic_csog"
    plant_source: str | None = None
    gnc_source: str | None = None
    limitations: tuple[str, ...] = ("NO_LIVE_PLANT_OR_GNC_ENVELOPE",)

    def __post_init__(self) -> None:
        """Validate immutable capability evidence."""
        values = (
            self.heading_window_rad,
            *self.speed_bounds_mps,
            self.rot_max_rad_s,
            self.decel_max_mps2,
        )
        if not np.isfinite(values).all() or min(values) < 0.0:
            raise ValueError("capability values must be finite and non-negative")
        if self.speed_bounds_mps[0] >= self.speed_bounds_mps[1]:
            raise ValueError("capability speed bounds must be ordered")
        if not self.odd_source:
            raise ValueError("capability ODD source is required")
        if not self.limitations:
            raise ValueError("capability limitations must be explicit")


class AssemblyProfile(StrEnum):
    MASS_PARITY = "MASS_PARITY"
    COLAV_STRICT = "COLAV_STRICT"


class AssemblyFrame(StrEnum):
    ENU = "ENU"
    NED = "NED"


class AssemblyFailureCode(StrEnum):
    CYCLE_MISMATCH = "CYCLE_MISMATCH"
    CAPACITY_EXCEEDED = "CAPACITY_EXCEEDED"
    TARGET_BINDING_MISSING = "TARGET_BINDING_MISSING"
    CORE_CAPABILITY_MISMATCH = "CORE_CAPABILITY_MISMATCH"
    INVALID_INPUT = "INVALID_INPUT"


@dataclass(frozen=True)
class AssemblyRequest:
    planner_input: PlannerInput
    snapshot: DecisionSnapshot
    cycle_input_hash: str
    lifecycle_profile_hash: str
    route: RouteReference
    capability: CapabilitySnapshot
    config: MidMpcAssemblyConfig
    rolling_plan: RollingPlanReference | None = None
    frame: AssemblyFrame = AssemblyFrame.ENU
    profile: AssemblyProfile = AssemblyProfile.COLAV_STRICT


@dataclass(frozen=True)
class AssemblyFailure:
    code: AssemblyFailureCode
    message: str
    identity: dict[str, object]
    owner: str = "ASSEMBLER"
    recoverability: str = "FIX_INPUT_THEN_NEW_SESSION"
    problem: None = None


@dataclass(frozen=True)
class TargetActivation:
    key: TrackKey
    cpa_hard_from_s: float
    cpa_hard_from_k: int
    direction_hard_from_s: float
    direction_hard_from_k: int
    min_alt_hard_from_s: float
    min_alt_hard_from_k: int


@dataclass(frozen=True)
class ConstraintActivationPlan:
    targets: tuple[TargetActivation, ...]
    global_cpa_hard_from_k: int
    global_direction_hard_from_k: int
    global_min_alt_hard_from_k: int


@dataclass(frozen=True)
class GridSpec:
    control_intervals: int
    state_samples: int
    dt_s: float
    duration_s: float


@dataclass(frozen=True)
class ExecutionPrefixPlan:
    active_intervals: int = 0
    source: str = "NO_EXECUTION_ACKNOWLEDGEMENT"


@dataclass(frozen=True)
class SeedPlan:
    source: str = "DETERMINISTIC_COLD_START"
    warm_start_used: bool = False
    accepted_plan_hash: str | None = None


@dataclass(frozen=True)
class SlackBoundsPlan:
    cpa_bounds: tuple[float, float | None]
    direction_bounds: tuple[float, float | None]


@dataclass(frozen=True)
class NumericalPreparationPlan:
    formulation_id: str
    layout_version: str
    structural_signature: str
    prefix: ExecutionPrefixPlan
    seed: SeedPlan
    slack: SlackBoundsPlan


@dataclass(frozen=True)
class AssemblySuccess:
    problem: MidMpcProblem
    selected_target_keys: tuple[TrackKey, ...]
    selected_tracks: tuple[TrackedObstacle, ...]
    effective_cpa_hard_m: float
    request_hash: str
    request_stage_json: str
    problem_hash: str
    profile: AssemblyProfile
    target_predictions: tuple[TargetPrediction, ...]
    horizon_encounter_plan: HorizonEncounterPlan
    activation_plan: ConstraintActivationPlan
    grid: GridSpec
    preparation: NumericalPreparationPlan
    execution_prefix: RetainedPrefixPlan | None = None
    retained_degraded: str | None = None


class _AssemblyInputError(ValueError):
    def __init__(self, code: AssemblyFailureCode, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class _TargetBinding:
    track_by_key: dict[TrackKey, TrackedObstacle]
    required_keys: tuple[TrackKey, ...]
    selected_keys: tuple[TrackKey, ...]
    selected_tracks: tuple[TrackedObstacle, ...]
    selected_decisions: tuple[TargetDecision, ...]
    required_decisions: tuple[TargetDecision, ...]
    safety_conflict_keys: frozenset[TrackKey]


@dataclass(frozen=True)
class _PolicyResolution:
    speed_bounds_mps: tuple[float, float]
    preferred_side: int
    lateral_active: bool
    committed_route_bearing_rad: float


@dataclass(frozen=True)
class _SemanticAssembly:
    problem: MidMpcProblem
    effective_cpa_hard_m: float
    activation_plan: ConstraintActivationPlan


class MidMpcProblemAssembler:
    """Atomic, stateless L1/L2 semantic problem assembler."""

    def assemble(self, request: AssemblyRequest) -> AssemblySuccess | AssemblyFailure:
        identity = _identity(request.snapshot)
        if request.frame is not AssemblyFrame.ENU or request.planner_input.coordinate_frame != AssemblyFrame.ENU.value:
            return AssemblyFailure(
                code=AssemblyFailureCode.INVALID_INPUT,
                message="Mid-MPC assembler requires an explicit ENU input frame",
                identity=identity,
            )
        if not math.isclose(request.planner_input.sim_time_s, request.snapshot.sim_time_s, abs_tol=1.0e-9):
            return AssemblyFailure(
                code=AssemblyFailureCode.CYCLE_MISMATCH,
                message="planner input and lifecycle snapshot times differ",
                identity=identity,
            )
        if request.snapshot.input_hash != request.cycle_input_hash:
            return AssemblyFailure(
                code=AssemblyFailureCode.CYCLE_MISMATCH,
                message="lifecycle snapshot input hash does not match the assembled cycle",
                identity=identity,
            )
        if request.snapshot.profile_hash != request.lifecycle_profile_hash:
            return AssemblyFailure(
                code=AssemblyFailureCode.CYCLE_MISMATCH,
                message="lifecycle snapshot profile hash does not match the assembled cycle",
                identity=identity,
            )
        if len(request.snapshot.directive.required_targets) > request.config.max_targets:
            return AssemblyFailure(
                code=AssemblyFailureCode.CAPACITY_EXCEEDED,
                message="required target count exceeds frozen core capacity",
                identity=identity,
            )
        try:
            return _assemble_problem(
                request.planner_input,
                request.snapshot,
                route=request.route,
                capability=request.capability,
                config=request.config,
                rolling_plan=request.rolling_plan,
                frame=request.frame,
                profile=request.profile,
            )
        except _AssemblyInputError as exc:
            return AssemblyFailure(code=exc.code, message=str(exc), identity=identity)
        except (TypeError, ValueError) as exc:
            return AssemblyFailure(
                code=AssemblyFailureCode.INVALID_INPUT,
                message=str(exc),
                identity=identity,
            )


def _assemble_problem(
    planner_input: PlannerInput,
    snapshot: DecisionSnapshot,
    *,
    route: RouteReference,
    capability: CapabilitySnapshot,
    config: MidMpcAssemblyConfig,
    rolling_plan: RollingPlanReference | None,
    frame: AssemblyFrame,
    profile: AssemblyProfile,
) -> AssemblySuccess:
    """Map one immutable decision snapshot without retaining business state."""
    binding = _bind_targets(
        planner_input,
        snapshot,
        route,
        config,
        consider_terminal_stop=profile is AssemblyProfile.COLAV_STRICT,
        include_reachable_targets=profile is AssemblyProfile.COLAV_STRICT,
    )
    policy = _resolve_policy(planner_input, snapshot, route, capability, binding, config)
    execution_prefix = None
    retained_degraded = None
    if (
        profile is AssemblyProfile.COLAV_STRICT
        and planner_input.execution_route_constraint is not None
        and planner_input.execution_route_constraint.trajectory_updates
    ):
        execution_prefix = degraded_stub_prefix(planner_input.execution_route_constraint, planner_input.ownship_state)
    elif profile is AssemblyProfile.COLAV_STRICT and planner_input.execution_route_constraint is not None:
        try:
            execution_prefix = compile_retained_prefix(
                planner_input.execution_route_constraint,
                planner_input.ownship_state,
                horizon_steps=config.horizon_steps,
                dt_s=config.horizon_dt_s,
                max_speed_mps=capability.speed_bounds_mps[1],
                rot_max_rad_s=capability.rot_max_rad_s,
                accel_max_mps2=capability.decel_max_mps2,
                min_speed_mps=float(planner_input.ownship_min_steerage_speed_mps or 0.0),
                navigation_mode=(
                    "cruise"
                    if all(
                        decision.route_recovery_allowed or decision.risk in {RiskPhase.CLEAR, RiskPhase.RELEASED}
                        for decision in snapshot.targets
                    )
                    else "avoidance"
                ),
                target_course_rad=(
                    policy.committed_route_bearing_rad
                    if any(
                        decision.role in {OwnshipRole.GIVE_WAY, OwnshipRole.OVERTAKING}
                        and decision.risk in {RiskPhase.ACTIVE, RiskPhase.PAST_CLEAR}
                        and not decision.route_recovery_allowed
                        for decision in snapshot.targets
                    )
                    else None
                ),
            )
        except _UnreachablePrefix as exc:
            # The mirror's execution schedule is GNC-owned (terminal
            # slowdown, turn pre-brake, stop window) and pins the retained
            # forecast at or past the motion envelope in unknown phases
            # (T1050/T240/T1620). That is a schedule effect, not a contract
            # error: degrade to the discard-stub exit — free re-solve plus
            # spliced publication — instead of failing the session. The
            # witness rides the replay artifact; contract/data errors still
            # raise.
            retained_degraded = f"retained compile unreachable: {exc}"
            execution_prefix = degraded_stub_prefix(
                planner_input.execution_route_constraint,
                planner_input.ownship_state,
                knot_trim_reason=str(exc) if str(exc).startswith("knot_trim") else None,
            )
    target_predictions = _target_predictions(
        tuple(sorted(binding.track_by_key, key=lambda key: (key.target_id, key.generation))),
        binding.track_by_key,
        planner_input.sim_time_s,
        config,
    )
    effective_cpa_hard_m = _effective_node_clearance(planner_input, binding.selected_tracks, config)
    execution_prefix = _discard_cpa_conflicting_prefix(
        execution_prefix, target_predictions, effective_cpa_hard_m, planner_input, config, capability
    )
    contract_recovery = None
    if execution_prefix is not None:
        execution_prefix, contract_recovery = _discard_contract_conflicting_prefix(
            execution_prefix, snapshot, planner_input, capability, config
        )
    # A discard stub only strips the pinned beats: the semantic problem keeps
    # the retained corridor (limit and points) so the optimized recovery arc
    # stays inside the same GNC admission envelope as a normal route update.
    horizon_encounter_plan = _compile_horizon_encounter_plan(
        planner_input,
        snapshot,
        route,
        capability,
        config,
        binding,
        policy,
        target_predictions,
    )
    if profile is AssemblyProfile.COLAV_STRICT:
        horizon_encounter_plan = replace(horizon_encounter_plan, solver_consumed=True)
    semantic = _compile_semantic_problem(
        planner_input,
        snapshot,
        route,
        capability,
        config,
        binding,
        policy,
        effective_cpa_hard_m,
        profile,
        horizon_encounter_plan,
        rolling_plan,
        execution_prefix,
        contract_recovery,
    )
    grid, preparation = _compile_numerical_preparation(
        config,
        profile,
        binding,
        semantic.problem,
    )
    request_document = request_hash_document(
        planner_input,
        snapshot,
        route,
        capability,
        config,
        rolling_plan,
        frame=frame,
        profile=profile,
    )
    request_stage_json = _canonical_json(request_document)
    request_hash = hashlib.sha256(request_stage_json.encode("utf-8")).hexdigest()
    problem_document = problem_hash_document(
        semantic.problem,
        target_predictions,
        horizon_encounter_plan,
        semantic.activation_plan,
        grid,
        preparation,
        parent_request_hash=request_hash,
    )
    return AssemblySuccess(
        problem=semantic.problem,
        selected_target_keys=binding.selected_keys,
        selected_tracks=binding.selected_tracks,
        effective_cpa_hard_m=semantic.effective_cpa_hard_m,
        request_hash=request_hash,
        request_stage_json=request_stage_json,
        problem_hash=_hash_document(problem_document),
        profile=profile,
        target_predictions=target_predictions,
        horizon_encounter_plan=horizon_encounter_plan,
        activation_plan=semantic.activation_plan,
        grid=grid,
        preparation=preparation,
        execution_prefix=execution_prefix,
        retained_degraded=retained_degraded,
    )


def _bind_targets(
    planner_input: PlannerInput,
    snapshot: DecisionSnapshot,
    route: RouteReference,
    config: MidMpcAssemblyConfig,
    *,
    consider_terminal_stop: bool = False,
    include_reachable_targets: bool = False,
) -> _TargetBinding:
    track_by_key = {TrackKey(track.target_id, track.generation or 1): track for track in planner_input.tracks}
    safety_conflict_keys = _mission_route_conflict_keys(
        planner_input,
        route,
        snapshot,
        track_by_key,
        config,
        consider_terminal_stop=consider_terminal_stop,
    )
    if include_reachable_targets:
        # Duty release never removes a reachable vessel from physical safety.
        duration = config.horizon_steps * config.horizon_dt_s
        own_radius = math.hypot(planner_input.ownship_length_m, planner_input.ownship_width_m) / 2
        released_keys = {decision.key for decision in snapshot.targets if _admission_rank(decision) == 0}
        reachable = frozenset(
            key
            for key, track in track_by_key.items()
            if key in released_keys
            and np.linalg.norm(track.state_enu[:2] - planner_input.ownship_state[:2])
            <= (config.speed_bounds_mps[1] + np.linalg.norm(track.state_enu[2:4])) * duration
            + config.cpa_hard_m
            + own_radius
            + math.hypot(track.length_m, track.width_m) / 2
        )
        safety_conflict_keys = safety_conflict_keys | reachable
    required_keys, selected_keys = _admit_target_keys(
        snapshot,
        track_by_key,
        config.max_targets,
        safety_conflict_keys=safety_conflict_keys,
    )
    decision_by_key = {decision.key: decision for decision in snapshot.targets}
    selected_tracks = tuple(track_by_key[key] for key in selected_keys)
    selected_decisions = tuple(decision_by_key[key] for key in selected_keys)
    required_decisions = tuple(decision_by_key[key] for key in required_keys)
    return _TargetBinding(
        track_by_key=track_by_key,
        required_keys=required_keys,
        selected_keys=selected_keys,
        selected_tracks=selected_tracks,
        selected_decisions=selected_decisions,
        required_decisions=required_decisions,
        safety_conflict_keys=safety_conflict_keys,
    )


def _resolve_policy(
    planner_input: PlannerInput,
    snapshot: DecisionSnapshot,
    route: RouteReference,
    capability: CapabilitySnapshot,
    binding: _TargetBinding,
    config: MidMpcAssemblyConfig,
) -> _PolicyResolution:
    required_sides = {
        decision.passing_side for decision in binding.required_decisions if decision.passing_side is not PassingSide.NONE
    }
    if required_sides and required_sides != {snapshot.directive.passing_side} and not snapshot.directive.stop_required:
        raise _AssemblyInputError(
            AssemblyFailureCode.CORE_CAPABILITY_MISMATCH,
            "aggregate direction cannot represent all required target corridors",
        )
    speed_bounds = (
        max(snapshot.directive.speed_bounds_mps[0], capability.speed_bounds_mps[0]),
        min(snapshot.directive.speed_bounds_mps[1], capability.speed_bounds_mps[1]),
    )
    if (
        planner_input.ownship_min_steerage_speed_mps is not None
        and not snapshot.directive.stop_required
    ):
        speed_bounds = (max(speed_bounds[0], planner_input.ownship_min_steerage_speed_mps), speed_bounds[1])
    if speed_bounds[0] > speed_bounds[1]:
        raise _AssemblyInputError(
            AssemblyFailureCode.CORE_CAPABILITY_MISMATCH,
            "lifecycle speed directive has no intersection with capability envelope",
        )

    preferred_side = {
        PassingSide.NONE: 0,
        PassingSide.PORT: -1,
        PassingSide.STARBOARD: 1,
    }[snapshot.directive.passing_side]
    lateral_active = snapshot.directive.minimum_course_change_rad > 0.0
    committed_route_bearing = route.bearing_rad
    corridor_decisions = tuple(
        decision
        for decision in binding.required_decisions
        if not decision.route_recovery_allowed
        and (decision.passing_side is not PassingSide.NONE or decision.required_course_change_rad > 0.0)
    )
    if corridor_decisions:
        corridor = max(corridor_decisions, key=lambda decision: decision.required_course_change_rad)
        if corridor.baseline_course_rad is None:
            raise ValueError(f"committed target {corridor.key} has no baseline course")
        committed_route_bearing = _guidance_course_target(planner_input, route, corridor, preferred_side)
        if _parallel_pass_clear(planner_input, route, binding, preferred_side, config):
            committed_route_bearing = route.mission_leg_bearing_rad
    elif binding.required_decisions:
        committed_route_bearing = float(planner_input.ownship_state[2])
    elif planner_input.execution_route_constraint is not None:
        candidates = tuple(
            decision
            for decision in binding.selected_decisions
            if decision.risk is RiskPhase.CANDIDATE
            and decision.role is OwnshipRole.GIVE_WAY
            and decision.passing_side is not PassingSide.NONE
        )
        if candidates:
            # Preview the observed maneuver behind GNC's protected near leg.
            # A mission-only preview can pin another full confirmation cycle
            # of straight travel, leaving too little response time on commit.
            candidate = max(candidates, key=lambda decision: decision.required_course_change_rad)
            side = -1 if candidate.passing_side is PassingSide.PORT else 1
            committed_route_bearing = _guidance_course_target(planner_input, route, candidate, side)

    return _PolicyResolution(
        speed_bounds_mps=speed_bounds,
        preferred_side=preferred_side,
        lateral_active=lateral_active,
        committed_route_bearing_rad=committed_route_bearing,
    )


def _parallel_pass_clear(
    planner_input: PlannerInput,
    route: RouteReference,
    binding: _TargetBinding,
    side: int,
    config: MidMpcAssemblyConfig,
) -> bool:
    """Stop pressing outward once the achieved maneuver admits a clear pass.

    This changes the reference only: the encounter remains committed and all
    physical clearance rows stay active. Both the locked passing side and
    every tracked vessel must permit the parallel course before it is used.
    """
    if planner_input.execution_route_constraint is None or not side or not binding.required_decisions:
        return False
    if any(not decision.action_achieved for decision in binding.required_decisions):
        return False
    tangent = np.array([math.cos(route.mission_leg_bearing_rad), math.sin(route.mission_leg_bearing_rad)])
    normal = np.array([-tangent[1], tangent[0]])
    clearance = _effective_node_clearance(planner_input, binding.selected_tracks, config)
    position = planner_input.ownship_state[:2]
    for decision in binding.required_decisions:
        relative = position - binding.track_by_key[decision.key].state_enu[:2]
        if side * float(relative @ normal) < clearance:
            return False
    for track in binding.selected_tracks:
        relative = track.state_enu[:2] - position
        velocity = track.state_enu[2:4] - route.planned_speed_mps * tangent
        speed2 = float(velocity @ velocity)
        tcpa = float(
            np.clip(-float(relative @ velocity) / max(speed2, 1e-12), 0.0, config.horizon_steps * config.horizon_dt_s)
        )
        if float(np.linalg.norm(relative + tcpa * velocity)) < clearance:
            return False
    return True


def _guidance_course_target(
    planner_input: PlannerInput, route: RouteReference, decision: TargetDecision, side: int
) -> float:
    baseline = decision.baseline_course_rad
    if baseline is None:
        raise ValueError("committed guidance target requires a baseline course")
    target = baseline + side * decision.required_course_change_rad
    if (
        planner_input.ownship_course_time_constant_s is not None
        and decision.committed_at_s is not None
        and decision.action_achievement_deadline_s is not None
    ):
        # Invert the declared course response over the committed action budget,
        # excluding the protected near leg. This changes the guidance target;
        # Lifecycle's minimum alteration and deadline remain unchanged.
        constraint = planner_input.execution_route_constraint
        delay = (
            0.0
            if constraint is None or constraint.trajectory_updates
            else constraint.minimum_update_distance_m / max(route.planned_speed_mps, 1e-6)
        )
        response_time = decision.action_achievement_deadline_s - decision.committed_at_s - delay
        if response_time <= 0:
            raise _AssemblyInputError(
                AssemblyFailureCode.CORE_CAPABILITY_MISMATCH,
                "retained route consumes the committed maneuver response budget",
            )
        response_gain = -math.expm1(-response_time / planner_input.ownship_course_time_constant_s)
        target = baseline + side * decision.required_course_change_rad / response_gain
    return target


def _scheduled_corridor_threshold(
    *,
    own_psi_rad: float,
    corridor_bearing_rad: float,
    passing_side: int,
    required_course_change_rad: float,
    action_complete_k: int,
    knot: int,
    prefix_hold_k: int,
    rot_max_rad_s: float,
    horizon_dt_s: float,
) -> float:
    """Rate-aware hard corridor bound for one knot, symmetric across sides.

    The observed heading can leave an already-achieved corridor under GNC
    dynamics or disturbances, so the bound demands a rate-limited return, not
    an impossible first-knot jump. A prefix hold pins the first knot on the
    measured heading, so its rotation budget is zero: the (k + 1 - hold)
    envelope never demands rotation the prefix forbids. Both sides share the
    same construction and the original hard corridor remains once reachable
    (multiship seam: the starboard-only clamp left port corridors demanding
    prefix-impossible rotation and Infeasible_Problem_Detected NLPs).
    """
    corridor = own_psi_rad + _wrap(corridor_bearing_rad - own_psi_rad)
    threshold = (
        corridor
        if knot >= action_complete_k
        else corridor - passing_side * required_course_change_rad
    )
    reachable = own_psi_rad + passing_side * max(knot + 1 - prefix_hold_k, 0) * rot_max_rad_s * horizon_dt_s
    return min(threshold, reachable) if passing_side > 0 else max(threshold, reachable)


def _candidate_course_schedule(
    schedule: MidMpcRowSchedule,
    execution_prefix: RetainedPrefixPlan | None,
    candidate_hold: bool,
    binding: _TargetBinding,
    horizon_steps: int,
) -> MidMpcRowSchedule:
    if (
        execution_prefix is None
        or (_is_discard_stub(execution_prefix) and not execution_prefix.constraint.trajectory_updates)
        or not candidate_hold
        or binding.required_keys
    ):
        return schedule
    overtaking = any(
        decision.role is OwnshipRole.OVERTAKING and decision.risk is RiskPhase.CANDIDATE
        for decision in binding.selected_decisions
    )
    sides = {
        decision.passing_side
        for decision in binding.selected_decisions
        if decision.role is OwnshipRole.GIVE_WAY and decision.risk is RiskPhase.CANDIDATE
    }
    if not overtaking and sides not in ({PassingSide.STARBOARD}, {PassingSide.PORT}):
        return schedule
    # Overtaking still awaits side selection and keeps a neutral follow/brake
    # route. An observed give-way side may hold or alter on that side, but
    # must not load the opposite turn into GNC's protected near leg before
    # confirmation. No minimum alteration is imposed before commitment.
    hold_course = execution_prefix.incoming_course_rad
    candidate_bounds = (
        (hold_course, hold_course)
        if overtaking
        else (hold_course, None)
        if sides == {PassingSide.STARBOARD}
        else (None, hold_course)
    )
    bounds = tuple(
        (None, None) if k < len(execution_prefix.course_rad) else candidate_bounds for k in range(horizon_steps)
    )
    return replace(schedule, course_bounds_rad=bounds)


def _recovery_search_active(
    planner_input: PlannerInput,
    snapshot: DecisionSnapshot,
    horizon_encounter_plan: HorizonEncounterPlan,
    *,
    lateral_active: bool,
    profile: AssemblyProfile,
) -> bool:
    """Allow a wider numerical heading search only during route recovery.

    The wider envelope is meaningful only for the native GNC route contract:
    the planner is returning to the mission line after the encounter duties
    have released.  It never changes per-target CPA rows, route-corridor rows,
    yaw-rate rows, or active COLREG heading bounds.
    """
    return bool(
        profile is AssemblyProfile.COLAV_STRICT
        and planner_input.execution_route_constraint is not None
        and horizon_encounter_plan.recovery_from_k is not None
        and not lateral_active
        and snapshot.targets
        and all(
            decision.route_recovery_allowed or decision.risk in {RiskPhase.CLEAR, RiskPhase.RELEASED}
            for decision in snapshot.targets
        )
    )


def _compile_semantic_problem(  # noqa: PLR0912, PLR0915 - compile lifecycle and terminal arrival constraints
    planner_input: PlannerInput,
    snapshot: DecisionSnapshot,
    route: RouteReference,
    capability: CapabilitySnapshot,
    config: MidMpcAssemblyConfig,
    binding: _TargetBinding,
    policy: _PolicyResolution,
    effective_cpa_hard_m: float,
    profile: AssemblyProfile,
    horizon_encounter_plan: HorizonEncounterPlan,
    rolling_plan: RollingPlanReference | None,
    execution_prefix: RetainedPrefixPlan | None = None,
    contract_recovery: _ContractRecovery | None = None,
) -> _SemanticAssembly:
    ownship = planner_input.ownship_state
    own_speed = float(np.hypot(ownship[3], ownship[4])) if profile is AssemblyProfile.COLAV_STRICT else float(ownship[3])
    minimum_change = snapshot.directive.minimum_course_change_rad if policy.lateral_active else 0.0
    reachable_per_step = capability.rot_max_rad_s * config.horizon_dt_s
    # A discard stub carries no pinned tail; the remaining alteration then
    # reads from the measured heading like a prefix-free beat.
    prefix_tail_rad = (
        float(execution_prefix.course_rad[-1])
        if execution_prefix is not None and execution_prefix.course_rad
        else float(ownship[2])
    )
    remaining_change = (
        minimum_change
        if execution_prefix is None
        else max(0.0, minimum_change - policy.preferred_side * _wrap(prefix_tail_rad - float(ownship[2])))
    )
    min_alt_hard_from_k = (
        (0 if execution_prefix is None else len(execution_prefix.course_rad))
        + max(0, math.ceil(remaining_change / reachable_per_step) - 1)
        if policy.lateral_active
        else 0
    )
    activation_plan = _activation_plan(
        binding.selected_decisions,
        binding.selected_tracks,
        planner_input,
        effective_cpa_hard_m,
        minimum_change,
        min_alt_hard_from_k,
        config,
        capability,
        reachable_when_diverging=profile is AssemblyProfile.COLAV_STRICT,
        scheduled_motion=bool(horizon_encounter_plan.corridor_reference_rad),
    )
    starboard_asymmetry = policy.lateral_active and any(
        decision.passing_side is PassingSide.STARBOARD
        and decision.encounter in {EncounterKind.HEAD_ON, EncounterKind.CROSSING}
        for decision in binding.required_decisions or binding.selected_decisions
    )
    preferred_side = policy.preferred_side
    lateral_active = policy.lateral_active
    row_schedule = _compile_row_schedule(
        profile,
        activation_plan,
        horizon_encounter_plan,
        binding.selected_decisions,
        safety_conflict_keys=binding.safety_conflict_keys,
        lateral_active=lateral_active,
        horizon_steps=config.horizon_steps,
    )
    give_way_obligation = any(
        decision.role in {OwnshipRole.GIVE_WAY, OwnshipRole.OVERTAKING}
        and decision.risk in {RiskPhase.CANDIDATE, RiskPhase.ACTIVE, RiskPhase.PAST_CLEAR}
        for decision in binding.selected_decisions
    )
    stand_on_hold = (
        not lateral_active
        and not give_way_obligation
        and any(
            decision.role in {OwnshipRole.STAND_ON, OwnshipRole.OVERTAKEN} and decision.rule17 is Rule17Stage.STAND_ON
            for decision in binding.selected_decisions
        )
        and all(
            held_course_clears_static_hazards(
                planner_input,
                own_position_ne_m=(float(ownship[0]), float(ownship[1])),
                # A stand-on decision without a frozen baseline cannot be
                # checked here; it fails the baseline requirement below.
                baseline_course_rad=float(ownship[2])
                if decision.baseline_course_rad is None
                else float(decision.baseline_course_rad),
                max_speed_mps=policy.speed_bounds_mps[1],
                horizon_steps=config.horizon_steps,
                dt_s=config.horizon_dt_s,
            )
            for decision in binding.selected_decisions
            if decision.role in {OwnshipRole.STAND_ON, OwnshipRole.OVERTAKEN} and decision.rule17 is Rule17Stage.STAND_ON
        )
    )
    candidate_hold = not lateral_active and any(
        decision.risk is RiskPhase.CANDIDATE
        and decision.role in {OwnshipRole.GIVE_WAY, OwnshipRole.OVERTAKING}
        and decision.planned_action_at_s is None
        for decision in binding.selected_decisions
    )
    hold_first_interval = stand_on_hold or candidate_hold
    recovery_search_active = _recovery_search_active(
        planner_input,
        snapshot,
        horizon_encounter_plan,
        lateral_active=lateral_active,
        profile=profile,
    )
    search_heading_window_rad = capability.heading_window_rad
    if recovery_search_active:
        search_heading_window_rad = max(search_heading_window_rad, config.recovery_heading_window_rad)
    heading_bounds = (
        float(ownship[2]) - search_heading_window_rad,
        float(ownship[2]) + search_heading_window_rad,
    )
    if profile is AssemblyProfile.COLAV_STRICT:
        staged_headings = (
            float(ownship[2]) + _wrap(horizon_encounter_plan.mission_route_bearing_rad - float(ownship[2])),
            float(ownship[2]) + _wrap(horizon_encounter_plan.avoidance_corridor_bearing_rad - float(ownship[2])),
        )
        heading_bounds = (
            min(heading_bounds[0], *staged_headings),
            max(heading_bounds[1], *staged_headings),
        )
    if stand_on_hold:
        stand_on_baselines = tuple(
            float(ownship[2]) + _wrap(float(decision.baseline_course_rad) - float(ownship[2]))
            for decision in binding.selected_decisions
            if decision.role in {OwnshipRole.STAND_ON, OwnshipRole.OVERTAKEN}
            and decision.rule17 is Rule17Stage.STAND_ON
            and decision.baseline_course_rad is not None
        )
        if not stand_on_baselines:
            raise _AssemblyInputError(
                AssemblyFailureCode.INVALID_INPUT,
                "stand-on authority requires a frozen course baseline",
            )
        heading_bounds = (
            max(
                heading_bounds[0],
                *(baseline - config.stand_on_course_tolerance_rad for baseline in stand_on_baselines),
            ),
            min(
                heading_bounds[1],
                *(baseline + config.stand_on_course_tolerance_rad for baseline in stand_on_baselines),
            ),
        )
        if heading_bounds[0] > heading_bounds[1]:
            raise _AssemblyInputError(
                AssemblyFailureCode.CORE_CAPABILITY_MISMATCH,
                "stand-on course authorities have no common feasible heading corridor",
            )
    recovery_lookahead_m = (
        max(own_speed, route.planned_speed_mps)
        * max(
            1.0 / capability.rot_max_rad_s,
            2.0 * config.horizon_dt_s,
            float(planner_input.ownship_course_time_constant_s or 0.0),
        )
        if execution_prefix is not None
        else 0.0
    )
    route_objective = _route_objective(
        profile,
        horizon_encounter_plan,
        route,
        ownship_position_ne_m=(float(ownship[0]), float(ownship[1])),
        ownship_heading_rad=float(ownship[2]),
        planned_speed_mps=0.0 if snapshot.directive.stop_required else route.planned_speed_mps,
        dt_s=config.horizon_dt_s,
        rot_max_rad_s=capability.rot_max_rad_s,
        heading_window_rad=capability.heading_window_rad,
        rolling_plan=rolling_plan,
        recovery_lookahead_m=recovery_lookahead_m,
        timed_execution=execution_prefix is not None and execution_prefix.constraint.trajectory_updates,
    )
    if route_objective is not None and not stand_on_hold:
        if all(d.route_recovery_allowed or d.risk in {RiskPhase.CLEAR, RiskPhase.RELEASED} for d in snapshot.targets):
            arrival_cruise = min(
                capability.speed_bounds_mps[1],
                max(
                    route.planned_speed_mps,
                    float(planner_input.speed_plan_mps[-2]) if planner_input.speed_plan_mps.size >= 2 else 0.0,
                ),
            )
            arrival = arrival_references(
                route.mission_waypoints_ne_m,
                tuple(map(float, ownship[:2])),
                float(ownship[2]),
                float(np.linalg.norm(ownship[3:5])),
                arrival_cruise,
                config.horizon_dt_s,
                config.horizon_steps,
                capability.decel_max_mps2,
                capability.rot_max_rad_s,
                max(
                    3.0 * config.decision_period_s + config.horizon_dt_s,
                    config.decision_period_s
                    + config.horizon_dt_s
                    + 4.0 * float(planner_input.ownship_speed_time_constant_s or 0.0),
                ),
                route.anchor_ne_m,
                horizon_encounter_plan.mission_route_bearing_rad,
                # First-order speed-loop lag: the terminal braking tail is
                # modelled against the executed command band, not the padded
                # approach reserve (crossing-E4 13.5 m terminal undershoot).
                float(planner_input.ownship_speed_time_constant_s or 0.0),
                arrival_radius_m=(
                    7.0 * planner_input.ownship_length_m if planner_input.execution_route_constraint is not None else None
                ),
                finite_navigation_tail=(execution_prefix is not None and execution_prefix.constraint.trajectory_updates),
                navigation_lookahead_m=recovery_lookahead_m or None,
                approach_heading_reference_rad=(
                    route_objective.heading_reference_rad
                    if execution_prefix is not None and execution_prefix.constraint.trajectory_updates
                    else None
                ),
            )
            if arrival is not None:
                headings, lateral, speeds, terminal = arrival
                route_objective = replace(
                    route_objective,
                    heading_reference_rad=headings,
                    lateral_reference_m=lateral,
                    speed_reference_mps=speeds,
                    terminal_position_m=terminal,
                    terminal_weight=terminal_weight(
                        float(np.linalg.norm(np.asarray(route.mission_waypoints_ne_m[-1]) - ownship[:2])),
                        arrival_cruise,
                        config.horizon_steps * config.horizon_dt_s,
                        3.0 * config.decision_period_s + config.horizon_dt_s,
                        config.decel_max_mps2,
                    ),
                    continuity_speed_reference_mps=speeds,
                    continuity_weight=tuple(
                        weight
                        * max(
                            0.0, 1.0 - (k + 1) * config.horizon_dt_s / (3.0 * config.decision_period_s + config.horizon_dt_s)
                        )
                        * min(1.0, speeds[k] / max(arrival_cruise, 0.1)) ** 2
                        for k, weight in enumerate(route_objective.continuity_weight)
                    ),
                )
        # These references already obey the turn-rate ramp. A bound centered
        # only on today's heading must not exclude later mission legs.
        heading_bounds = (
            min(heading_bounds[0], *route_objective.heading_reference_rad),
            max(heading_bounds[1], *route_objective.heading_reference_rad),
        )
    scheduled = bool(horizon_encounter_plan.corridor_reference_rad) and profile is AssemblyProfile.COLAV_STRICT
    if scheduled:
        # A prefix hold pins the first knot on the measured heading, so its
        # rotation budget is zero. Both corridor sides must stage re-entry
        # with the same rate-aware, prefix-aware construction: the observed
        # heading can leave an already-achieved corridor under GNC dynamics
        # or disturbances, and demanding more rotation than the envelope
        # allows (or than the prefix permits) makes the NLP infeasible.
        prefix_hold_k = (
            len(execution_prefix.course_rad) if execution_prefix is not None else (1 if hold_first_interval else 0)
        )
        overdue_actions = {
            decision.key
            for decision in binding.selected_decisions
            if decision.commitment is CommitmentPhase.COMMITTED
            and not decision.action_achieved
            and decision.action_achievement_deadline_s is not None
            and decision.action_achievement_deadline_s < planner_input.sim_time_s
        }
        bounds: list[tuple[float | None, float | None]] = []
        for k in range(config.horizon_steps):
            lower, upper = None, None
            for window in horizon_encounter_plan.target_windows:
                stop = config.horizon_steps if window.recovery_from_k is None else window.recovery_from_k
                if not window.action_start_k <= k < stop or not window.passing_side:
                    continue
                threshold = _scheduled_corridor_threshold(
                    own_psi_rad=float(ownship[2]),
                    corridor_bearing_rad=float(window.corridor_bearing_rad),
                    passing_side=int(window.passing_side),
                    required_course_change_rad=float(window.required_course_change_rad),
                    # L4 checks the first executable knot after an absolute
                    # deadline. Replanning must not grant another ALTER beat.
                    action_complete_k=0 if window.key in overdue_actions else window.action_complete_k,
                    knot=k,
                    prefix_hold_k=prefix_hold_k,
                    rot_max_rad_s=capability.rot_max_rad_s,
                    horizon_dt_s=config.horizon_dt_s,
                )
                if window.passing_side > 0:
                    lower = threshold if lower is None else max(lower, threshold)
                else:
                    upper = threshold if upper is None else min(upper, threshold)
            bounds.append((lower, upper))
        # Overlapping corridor windows can hand over with a heading step far
        # beyond the rot envelope (multiship seam: the give-way hold corridor
        # still binds one knot before the next encounter window demands its
        # own corridor, a ~12 rot-step jump between adjacent knots). IPOPT
        # then dies on the seam rot rows (persisted multiship-E4 NLPs:
        # Infeasible_Problem_Detected / timeout restorations with the iterate
        # riding the jump). Ramp the staged bounds across the seam at the rot
        # envelope: a demand that tightens faster than one rot step per knot
        # is eased to the reachable corridor; one that eases or is already
        # reachable stays untouched. Bounds never leave their staged
        # interval, and each window's deadline demand survives wherever the
        # hull can reach it.
        rot_step_rad = capability.rot_max_rad_s * config.horizon_dt_s
        ramped: list[tuple[float | None, float | None]] = []
        previous_lower: float | None = None
        previous_upper: float | None = None
        for lower, upper in bounds:
            if lower is not None and previous_lower is not None:
                lower = min(lower, previous_lower + rot_step_rad)
            if upper is not None and previous_upper is not None:
                upper = max(upper, previous_upper - rot_step_rad)
            ramped.append((lower, upper))
            previous_lower = lower
            previous_upper = upper
        bounds = ramped
        # The horizon search envelope must contain mandatory future corridors,
        # not just today's heading and the rate-ramped soft reference. The
        # per-knot hard corridors and physical turn-rate rows stay unchanged.
        scheduled_headings = tuple(value for bound in bounds for value in bound if value is not None)
        heading_bounds = (
            min((heading_bounds[0], *scheduled_headings)),
            max((heading_bounds[1], *scheduled_headings)),
        )
        row_schedule = replace(
            row_schedule,
            direction_hard_window=MidMpcHardWindow(0, 0),
            min_alt_hard_window=MidMpcHardWindow(0, 0),
            course_bounds_rad=tuple(bounds),
        )
    route_frame_bearing = (
        route.mission_leg_bearing_rad if route_objective is not None else policy.committed_route_bearing_rad
    )
    prefix_count = len(execution_prefix.course_rad) if execution_prefix is not None else (1 if hold_first_interval else 0)
    retained_corridor = execution_prefix is not None and not execution_prefix.constraint.trajectory_updates
    corridor_points = execution_prefix.corridor_points_m if retained_corridor else ()
    route_update_limit = execution_prefix.constraint.lateral_limit_m if retained_corridor else None
    row_schedule = _candidate_course_schedule(row_schedule, execution_prefix, candidate_hold, binding, config.horizon_steps)
    row_schedule = _contract_recovery_schedule(
        row_schedule,
        recovery=contract_recovery,
        own_psi_rad=float(ownship[2]),
        rot_step_rad=reachable_per_step,
        min_alteration_rad=minimum_change,
        horizon_steps=config.horizon_steps,
        scheduled=scheduled,
    )
    problem = MidMpcProblem(
        own_ship=MidMpcOwnShip(psi_rad=float(ownship[2]), u_mps=own_speed),
        route_bearing_rad=policy.committed_route_bearing_rad,
        planned_speed_mps=0.0 if snapshot.directive.stop_required else route.planned_speed_mps,
        heading_bounds_rad=heading_bounds,
        speed_bounds_mps=policy.speed_bounds_mps,
        cpa_safe_m=max(config.cpa_safe_m, effective_cpa_hard_m),
        cpa_hard_m=effective_cpa_hard_m,
        rot_max_rad_s=capability.rot_max_rad_s,
        decel_max_mps2=capability.decel_max_mps2,
        lateral_active=lateral_active and not scheduled,
        preferred_side=preferred_side,
        starboard_asymmetry_active=starboard_asymmetry and not scheduled,
        min_alteration_rad=minimum_change,
        prefix_active_k=prefix_count,
        prefix_psi_rad=execution_prefix.course_rad
        if execution_prefix is not None
        else ((float(ownship[2]),) if hold_first_interval else ()),
        prefix_u_mps=execution_prefix.speed_mps
        if execution_prefix is not None
        else ((own_speed,) if hold_first_interval else ()),
        route_constraint_points_m=corridor_points,
        route_constraint_limit_m=route_update_limit,
        timed_execution=execution_prefix is not None and execution_prefix.constraint.trajectory_updates,
        minimum_turn_radius_m=(execution_prefix.constraint.minimum_turn_radius_m if execution_prefix is not None else 0.0),
        maximum_lateral_acceleration_mps2=(
            execution_prefix.constraint.maximum_lateral_acceleration_mps2 if execution_prefix is not None else 0.0
        ),
        navigation_recovery_lookahead_m=(
            # A finite native arrival already has one capture-and-braking
            # reference. Recomputing a second, constant-lead LOS objective
            # here would reward entering the goal disk before rejoining.
            recovery_lookahead_m
            if execution_prefix is not None
            and on_final_leg(np.asarray(route.mission_waypoints_ne_m), ownship[:2])
            and not (
                execution_prefix.constraint.trajectory_updates
                and route_objective is not None
                and route_objective.terminal_position_m is not None
            )
            else 0.0
        ),
        cpa_braking_floor_mps=(
            float(planner_input.ownship_min_steerage_speed_mps or 0.0)
            if not snapshot.directive.stop_required
            else 0.0
        ),
        route_suffix_min_extent_m=(
            execution_prefix.constraint.minimum_segment_m
            if execution_prefix is not None and not snapshot.directive.stop_required
            else 0.0
        ),
        route_frame=MidMpcRouteFrame(
            origin_m=(
                route.anchor_ne_m[0] - float(ownship[0]),
                route.anchor_ne_m[1] - float(ownship[1]),
            ),
            normal=(
                -math.sin(route_frame_bearing),
                math.cos(route_frame_bearing),
            ),
            bearing_rad=route_frame_bearing,
            lateral_scale_m=config.route_lateral_scale_m,
            weight=config.route_weight,
        ),
        route_objective=route_objective,
        row_schedule=row_schedule,
        static_field=compile_static_field(planner_input) if profile is AssemblyProfile.COLAV_STRICT else None,
        static_origin_ne_m=tuple(map(float, ownship[:2])),
        audit_row_count=len(binding.selected_tracks),
        targets=tuple(
            MidMpcTarget(
                x_m=float(track.state_enu[0] - ownship[0]),
                y_m=float(track.state_enu[1] - ownship[1]),
                cog_rad=float(math.atan2(track.state_enu[3], track.state_enu[2])),
                sog_mps=float(np.linalg.norm(track.state_enu[2:4])),
                crossing_astern_required=(
                    # Course achievement is not completion of the encounter's
                    # passing obligation; keep it until Lifecycle releases it.
                    decision.encounter is EncounterKind.CROSSING
                    and decision.role is OwnshipRole.GIVE_WAY
                    and (
                        decision.risk in {RiskPhase.ACTIVE, RiskPhase.PAST_CLEAR}
                        or (
                            decision.risk is RiskPhase.CANDIDATE
                            and decision.planned_action_at_s is not None
                            and decision.planned_action_at_s
                            < planner_input.sim_time_s + config.horizon_steps * config.horizon_dt_s
                            and 0 < decision.geometry.signed_tcpa_s < config.horizon_steps * config.horizon_dt_s
                        )
                    )
                ),
                crossing_astern_margin_m=0.0,
            )
            for track, decision in zip(binding.selected_tracks, binding.selected_decisions, strict=True)
        ),
    )
    return _SemanticAssembly(
        problem=problem,
        effective_cpa_hard_m=effective_cpa_hard_m,
        activation_plan=activation_plan,
    )


def _compile_row_schedule(
    profile: AssemblyProfile,
    activation_plan: ConstraintActivationPlan,
    horizon_plan: HorizonEncounterPlan,
    selected_decisions: tuple[TargetDecision, ...],
    *,
    safety_conflict_keys: frozenset[TrackKey],
    lateral_active: bool,
    horizon_steps: int,
) -> MidMpcRowSchedule:
    """Compile phase semantics into bounds-only windows for the fixed NLP graph."""
    legacy = MidMpcRowSchedule(
        cpa_hard_from_k=activation_plan.global_cpa_hard_from_k,
        direction_hard_from_k=activation_plan.global_direction_hard_from_k,
        min_alt_hard_from_k=activation_plan.global_min_alt_hard_from_k,
        terminal_rows_enabled=False,
    )
    if profile is AssemblyProfile.MASS_PARITY:
        return legacy

    target_windows = {window.key: window for window in horizon_plan.target_windows}
    activation_by_key = {target.key: target for target in activation_plan.targets}
    cpa_windows = []
    for decision in selected_decisions:
        activation_start_k = activation_by_key[decision.key].cpa_hard_from_k
        target_window = target_windows.get(decision.key)
        route_recovery_conflict = (
            target_window is not None
            and target_window.route_recovery_allowed_at_start
            and target_window.minimum_predicted_route_dcpa_m < target_window.recovery_clearance_m
        )
        start_k = 0 if route_recovery_conflict or decision.key in safety_conflict_keys else activation_start_k
        # Predicted recovery releases maneuver duties, not collision safety.
        # A return can approach the target again well after the staged CPA;
        # physical clearance must remain constrained through the entire suffix.
        cpa_windows.append(MidMpcHardWindow(start_k, horizon_steps))
    if not horizon_plan.target_windows:
        recovery_stop_k = 0
    elif horizon_plan.recovery_from_k is None:
        recovery_stop_k = horizon_steps
    else:
        recovery_stop_k = min(horizon_plan.recovery_from_k, horizon_steps)
    direction_window = None
    min_alt_window = None
    if lateral_active:
        direction_start = min(
            (
                activation_plan.global_direction_hard_from_k
                if horizon_plan.target_windows
                else activation_plan.global_cpa_hard_from_k
            ),
            horizon_steps,
        )
        min_alt_start = min(
            (
                activation_plan.global_min_alt_hard_from_k
                if horizon_plan.target_windows
                else max(
                    activation_plan.global_min_alt_hard_from_k,
                    activation_plan.global_cpa_hard_from_k,
                )
            ),
            horizon_steps,
        )
        direction_stop_k = (
            horizon_steps if horizon_plan.target_windows or direction_start < horizon_steps else recovery_stop_k
        )
        min_alt_stop_k = (
            horizon_steps if not horizon_plan.target_windows and min_alt_start < horizon_steps else recovery_stop_k
        )
        direction_window = MidMpcHardWindow(direction_start, max(direction_start, direction_stop_k))
        min_alt_window = MidMpcHardWindow(min_alt_start, max(min_alt_start, min_alt_stop_k))
    return replace(
        legacy,
        prefix_softening=True,
        cpa_hard_windows=tuple(cpa_windows),
        direction_hard_window=direction_window,
        min_alt_hard_window=min_alt_window,
    )


def _route_objective(
    profile: AssemblyProfile,
    horizon_encounter_plan: HorizonEncounterPlan,
    route: RouteReference,
    *,
    ownship_position_ne_m: tuple[float, float],
    ownship_heading_rad: float,
    planned_speed_mps: float,
    dt_s: float,
    rot_max_rad_s: float,
    heading_window_rad: float,
    rolling_plan: RollingPlanReference | None,
    recovery_lookahead_m: float = 0.0,
    timed_execution: bool = False,
) -> MidMpcRouteObjective | None:
    if profile is AssemblyProfile.MASS_PARITY:
        return None
    heading_references, lateral_references = _staged_route_references(
        horizon_encounter_plan,
        route,
        ownship_position_ne_m=ownship_position_ne_m,
        ownship_heading_rad=ownship_heading_rad,
        planned_speed_mps=planned_speed_mps,
        dt_s=dt_s,
        rot_max_rad_s=rot_max_rad_s,
        heading_window_rad=heading_window_rad,
        recovery_lookahead_m=recovery_lookahead_m,
        timed_execution=timed_execution,
    )
    avoidance_active_until_k = next(
        (
            index
            for index, phase in enumerate(horizon_encounter_plan.phases[1:], start=1)
            if phase is HorizonEncounterPhase.RECOVER
        ),
        len(heading_references),
    )
    return MidMpcRouteObjective(
        mission_bearing_rad=horizon_encounter_plan.mission_route_bearing_rad,
        avoidance_corridor_bearing_rad=horizon_encounter_plan.avoidance_corridor_bearing_rad,
        heading_reference_rad=heading_references,
        lateral_reference_m=lateral_references,
        avoidance_active_until_k=avoidance_active_until_k,
        continuity_heading_reference_rad=(rolling_plan.heading_reference_rad if rolling_plan is not None and rolling_plan.active else ()),
        continuity_speed_reference_mps=(rolling_plan.speed_reference_mps if rolling_plan is not None and rolling_plan.active else ()),
        continuity_weight=(rolling_plan.objective_weight if rolling_plan is not None and rolling_plan.active else ()),
    )


def _staged_route_references(
    plan: HorizonEncounterPlan,
    route: RouteReference,
    *,
    ownship_position_ne_m: tuple[float, float],
    ownship_heading_rad: float,
    planned_speed_mps: float,
    dt_s: float,
    rot_max_rad_s: float,
    heading_window_rad: float,
    recovery_lookahead_m: float = 0.0,
    timed_execution: bool = False,
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Compile one reachable avoid-pass-rejoin reference on the mission frame."""
    mission = plan.mission_route_bearing_rad
    corridor = plan.avoidance_corridor_bearing_rad
    route_normal = np.array((-math.sin(mission), math.cos(mission)), dtype=float)
    route_origin = np.asarray(route.anchor_ne_m, dtype=float) - np.asarray(ownship_position_ne_m, dtype=float)
    position = np.zeros(2, dtype=float)
    speed = max(0.0, float(planned_speed_mps))
    maximum_recovery_delta = heading_window_rad
    maximum_heading_step = rot_max_rad_s * dt_s
    recovery_first_step = bool(plan.phases) and plan.phases[0] is HorizonEncounterPhase.RECOVER
    previous_heading = ownship_heading_rad
    headings: list[float] = []
    lateral_references: list[float] = []
    for k, phase in enumerate(plan.phases[:-1]):
        absolute_position = np.asarray(ownship_position_ne_m, dtype=float) + position
        mission, mission_anchor = _mission_route_projection(
            route,
            absolute_position,
            recovery_heading_rad=(
                previous_heading if phase in {HorizonEncounterPhase.MISSION, HorizonEncounterPhase.RECOVER} else None
            ),
            lookahead_m=max(speed / max(rot_max_rad_s, 1.0e-9), speed * dt_s),
        )
        cross_track = float((position - route_origin) @ route_normal)
        lateral_references.append(cross_track)
        if phase in {HorizonEncounterPhase.ALTER, HorizonEncounterPhase.PASS}:
            desired_heading = plan.corridor_reference_rad[k] if plan.corridor_reference_rad else corridor
        elif speed > 1.0e-9 and maximum_recovery_delta > 1.0e-9:
            if mission_anchor is not None:
                mission_normal = np.array((-math.sin(mission), math.cos(mission)), dtype=float)
                mission_cross_track = float((absolute_position - np.asarray(mission_anchor, dtype=float)) @ mission_normal)
            else:
                mission_cross_track = cross_track
            requested_lateral_velocity = float(np.clip(-mission_cross_track / dt_s, -speed, speed))
            recovery_delta = (
                -math.atan2(mission_cross_track, recovery_lookahead_m)
                if recovery_lookahead_m > 0.0
                else math.asin(requested_lateral_velocity / speed)
            )
            recovery_delta = float(np.clip(recovery_delta, -maximum_recovery_delta, maximum_recovery_delta))
            desired_heading = mission + recovery_delta
        else:
            desired_heading = mission
        desired_heading = ownship_heading_rad + _wrap(desired_heading - ownship_heading_rad)
        desired_heading = previous_heading + _wrap(desired_heading - previous_heading)
        heading = previous_heading + float(
            np.clip(desired_heading - previous_heading, -maximum_heading_step, maximum_heading_step)
        )
        if not timed_execution and not headings and recovery_first_step:
            # Corridor release: a first reference sitting exactly on the rot bound
            # makes the interior-point seed start on the active constraint and
            # IPOPT crawls the barrier for dozens of iterations; anchor the first
            # step on the current heading and let the ramp pull from step one.
            # A timed route already carries the measured state at sample zero;
            # repeating it at sample one would postpone recovery on every replan.
            heading = ownship_heading_rad
        headings.append(heading)
        position += speed * dt_s * np.array((math.cos(heading), math.sin(heading)), dtype=float)
        previous_heading = heading

    return tuple(headings), tuple(lateral_references)


def _mission_route_projection(
    route: RouteReference,
    position_ne_m: np.ndarray,
    *,
    recovery_heading_rad: float | None = None,
    lookahead_m: float = 0.0,
) -> tuple[float, tuple[float, float] | None]:
    """Project one predicted stage onto the mission polyline and retain its tangent."""
    if not route.mission_waypoints_ne_m:
        return route.mission_leg_bearing_rad, None

    points = tuple(np.asarray(point, dtype=float) for point in route.mission_waypoints_ne_m)
    candidates: list[tuple[float, int, float, np.ndarray]] = []
    for segment_index, (start, end) in enumerate(zip(points[:-1], points[1:], strict=True)):
        delta = end - start
        length = float(np.linalg.norm(delta))
        if length <= 1.0e-9:
            continue
        fraction = float(np.clip((position_ne_m - start) @ delta / (length * length), 0.0, 1.0))
        anchor = start + fraction * delta
        bearing = math.atan2(float(delta[1]), float(delta[0]))
        candidates.append((float(np.linalg.norm(position_ne_m - anchor)), segment_index, bearing, anchor))
    if not candidates:
        return route.mission_leg_bearing_rad, None
    # At a shared waypoint both adjacent segments have the same projection;
    # prefer the later segment so the horizon turns instead of sticking to the
    # completed leg.
    _, index, bearing, anchor = min(candidates, key=lambda candidate: (candidate[0], -candidate[1]))
    if recovery_heading_rad is not None and lookahead_m > 0.0 and index + 2 < len(points):
        corner = points[index + 1]
        outgoing = points[index + 2] - corner
        length = float(np.linalg.norm(outgoing))
        if length > 1.0e-9:
            outgoing /= length
            incoming = np.array((math.cos(bearing), math.sin(bearing)))
            normal_in = np.array((-incoming[1], incoming[0]))
            normal_out = np.array((-outgoing[1], outgoing[0]))
            relative = position_ne_m - corner
            error_in = float(relative @ normal_in)
            error_out = float(relative @ normal_out)
            progress_out = float(relative @ outgoing)
            turn = float(incoming[0] * outgoing[1] - incoming[1] * outgoing[0])
            course_in = bearing - math.atan2(error_in, lookahead_m)
            course_out = math.atan2(outgoing[1], outgoing[0]) - math.atan2(error_out, lookahead_m)
            delta_in = _wrap(course_in - recovery_heading_rad)
            delta_out = _wrap(course_out - recovery_heading_rad)
            if (
                abs(error_in) > lookahead_m
                and error_in * turn > 0.0
                and 0.0 < progress_out < length
                and delta_in * turn < 0.0 <= delta_out * turn
                and abs(delta_out) < math.pi / 2.0
            ):
                bearing = math.atan2(outgoing[1], outgoing[0])
                anchor = corner + progress_out * outgoing
    return bearing, (float(anchor[0]), float(anchor[1]))


def _compile_numerical_preparation(
    config: MidMpcAssemblyConfig,
    profile: AssemblyProfile,
    binding: _TargetBinding,
    problem: MidMpcProblem,
) -> tuple[GridSpec, NumericalPreparationPlan]:
    grid = GridSpec(
        control_intervals=config.horizon_steps,
        state_samples=config.horizon_steps + 1,
        dt_s=config.horizon_dt_s,
        duration_s=config.horizon_steps * config.horizon_dt_s,
    )
    slack_bound = 0.0 if profile is AssemblyProfile.COLAV_STRICT else None
    structural_signature = _hash_document(
        {
            "formulation": "mass-l3-mid-mpc-ipopt@ced58f8576f3772ef7c1bc72bb0f8b0368688b5a",
            "layout_version": "frozen-row-layout@1",
            "horizon_steps": config.horizon_steps,
            "horizon_dt_s": config.horizon_dt_s,
            "target_count": len(binding.selected_tracks),
            "audit_row_count": problem.audit_row_count,
            "cpa_hard_m": problem.cpa_hard_m,
            "route_objective_layout": (
                "staged-heading-reference@1" if problem.route_objective is not None else "frozen-scalar@1"
            ),
            "slack_topology": ["cpa", "direction"],
        }
    )
    preparation = NumericalPreparationPlan(
        formulation_id="mass-l3-mid-mpc-ipopt@ced58f8576f3772ef7c1bc72bb0f8b0368688b5a",
        layout_version="frozen-row-layout@1",
        structural_signature=structural_signature,
        prefix=ExecutionPrefixPlan(
            problem.prefix_active_k,
            "RETAINED_ROUTE_WITH_PLANNER_TRANSITION"
            if problem.route_constraint_limit_m is not None
            else "NO_EXECUTION_ACKNOWLEDGEMENT",
        ),
        seed=SeedPlan(),
        slack=SlackBoundsPlan(
            cpa_bounds=(0.0, slack_bound),
            direction_bounds=(0.0, slack_bound),
        ),
    )
    return grid, preparation


def _compile_horizon_encounter_plan(
    planner_input: PlannerInput,
    snapshot: DecisionSnapshot,
    route: RouteReference,
    capability: CapabilitySnapshot,
    config: MidMpcAssemblyConfig,
    binding: _TargetBinding,
    policy: _PolicyResolution,
    target_predictions: tuple[TargetPrediction, ...],
) -> HorizonEncounterPlan:
    prediction_by_key = {prediction.key: prediction for prediction in target_predictions}
    own_radius_m = 0.5 * math.hypot(planner_input.ownship_length_m, planner_input.ownship_width_m)
    horizon_decisions = tuple(
        decision
        for decision in binding.selected_decisions
        if decision.key in binding.required_keys
        or (decision.commitment is CommitmentPhase.COMMITTED and decision.risk in {RiskPhase.ACTIVE, RiskPhase.PAST_CLEAR})
        or (decision.planned_action_at_s is not None and decision.risk is RiskPhase.CANDIDATE)
        or (
            planner_input.execution_route_constraint is not None
            and decision.risk is RiskPhase.CANDIDATE
            and decision.role is OwnshipRole.GIVE_WAY
            and decision.passing_side is not PassingSide.NONE
        )
    )
    scheduled = any(decision.planned_action_at_s is not None for decision in horizon_decisions)
    nominal_headings: tuple[float, ...] = ()
    nominal_positions = np.empty((0, 2))
    if scheduled:
        nominal_plan = HorizonEncounterPlan(
            reference_time_s=planner_input.sim_time_s,
            times_s=np.arange(config.horizon_steps + 1) * config.horizon_dt_s,
            mission_route_bearing_rad=route.mission_leg_bearing_rad,
            avoidance_corridor_bearing_rad=route.mission_leg_bearing_rad,
            phases=(HorizonEncounterPhase.MISSION,) * (config.horizon_steps + 1),
            target_windows=(),
            recovery_from_k=0,
        )
        nominal_headings, _ = _staged_route_references(
            nominal_plan,
            route,
            ownship_position_ne_m=tuple(planner_input.ownship_state[:2]),
            ownship_heading_rad=float(planner_input.ownship_state[2]),
            planned_speed_mps=route.planned_speed_mps,
            dt_s=config.horizon_dt_s,
            rot_max_rad_s=capability.rot_max_rad_s,
            heading_window_rad=capability.heading_window_rad,
        )

        nominal_positions = planner_input.ownship_state[:2] + np.cumsum(
            route.planned_speed_mps
            * config.horizon_dt_s
            * np.column_stack((np.cos(nominal_headings), np.sin(nominal_headings))),
            axis=0,
        )

    def corridor_for(decision: TargetDecision) -> float | None:
        if not scheduled:
            return None
        offset = max(0.0, (decision.planned_action_at_s or planner_input.sim_time_s) - planner_input.sim_time_s)
        if decision.risk is RiskPhase.CANDIDATE and offset > 0.0:
            index = min(config.horizon_steps - 1, max(0, math.ceil(offset / config.horizon_dt_s) - 1))
            baseline, _ = _mission_route_projection(route, nominal_positions[index])
        else:
            baseline = (
                decision.baseline_course_rad if decision.baseline_course_rad is not None else route.mission_leg_bearing_rad
            )
        sign = -1 if decision.passing_side is PassingSide.PORT else 1
        if decision.risk is not RiskPhase.CANDIDATE:
            return _guidance_course_target(planner_input, route, decision, sign)
        return baseline + sign * decision.required_course_change_rad

    plan = compile_horizon_encounter_plan(
        HorizonEncounterPlanRequest(
            reference_time_s=planner_input.sim_time_s,
            times_s=np.arange(config.horizon_steps + 1, dtype=float) * config.horizon_dt_s,
            own_position_ne_m=(float(planner_input.ownship_state[0]), float(planner_input.ownship_state[1])),
            mission_route_anchor_ne_m=route.anchor_ne_m,
            own_heading_rad=float(planner_input.ownship_state[2]),
            own_speed_mps=(
                0.0
                if snapshot.directive.stop_required
                else float(np.hypot(planner_input.ownship_state[3], planner_input.ownship_state[4]))
                if planner_input.execution_route_constraint is not None
                else route.planned_speed_mps
            ),
            mission_route_bearing_rad=route.mission_leg_bearing_rad,
            avoidance_corridor_bearing_rad=policy.committed_route_bearing_rad,
            rot_max_rad_s=capability.rot_max_rad_s,
            heading_window_rad=capability.heading_window_rad,
            # Stage the recovery turn-back on the qualified course response, so
            # advisory RECOVER knots stay executable by the lagged plant
            # (advisory release preceded the executed CPA by ~9 knots).
            course_time_constant_s=float(planner_input.ownship_course_time_constant_s or 0.0),
            targets=tuple(
                HorizonTargetIntent(
                    key=decision.key,
                    required_course_change_rad=decision.required_course_change_rad,
                    recovery_clearance_m=(
                        config.cpa_safe_m
                        + own_radius_m
                        + 0.5
                        * math.hypot(
                            binding.track_by_key[decision.key].length_m,
                            binding.track_by_key[decision.key].width_m,
                        )
                    ),
                    action_achieved=decision.action_achieved,
                    route_recovery_allowed=decision.route_recovery_allowed,
                    prediction=prediction_by_key[decision.key],
                    action_start_s=max(
                        0.0, (decision.planned_action_at_s or planner_input.sim_time_s) - planner_input.sim_time_s
                    )
                    if decision.risk is RiskPhase.CANDIDATE
                    else 0.0,
                    corridor_bearing_rad=corridor_for(decision),
                    passing_side=0
                    if decision.risk is RiskPhase.CANDIDATE and decision.planned_action_at_s is None
                    else -1
                    if decision.passing_side is PassingSide.PORT
                    else 1
                    if decision.passing_side is PassingSide.STARBOARD
                    else 0,
                )
                for decision in horizon_decisions
            ),
        )
    )
    return plan


def request_hash_document(
    planner_input: PlannerInput,
    snapshot: DecisionSnapshot,
    route: RouteReference,
    capability: CapabilitySnapshot,
    config: MidMpcAssemblyConfig,
    rolling_plan: RollingPlanReference | None = None,
    *,
    frame: AssemblyFrame,
    profile: AssemblyProfile,
) -> dict[str, object]:
    """Return canonical cycle evidence used as the hash-chain root."""
    route_document = asdict(route)
    if not route.mission_waypoints_ne_m:
        route_document.pop("mission_waypoints_ne_m")
    return {
        "schema_version": "colav.mid_mpc.request@2",
        "frame": frame.value,
        "identity": _identity(snapshot),
        "decision_snapshot": asdict(snapshot),
        "route": route_document,
        "capability": asdict(capability),
        "config": asdict(config),
        "rolling_plan": None if rolling_plan is None else asdict(rolling_plan),
        "profile": profile.value,
        "static_context": static_execution_context(planner_input) if profile is AssemblyProfile.COLAV_STRICT else None,
        "ownship": {
            "state": planner_input.ownship_state.tolist(),
            "state_representation": "ground_course_speed"
            if planner_input.ownship_state[4] == 0.0 and planner_input.ownship_state[3] >= 0.0
            else "heading_body_velocity",
            "length_m": planner_input.ownship_length_m,
            "width_m": planner_input.ownship_width_m,
            "draft_m": planner_input.ownship_draft_m,
            "speed_time_constant_s": planner_input.ownship_speed_time_constant_s,
            # The qualified course lag changes the recovery staging envelope,
            # so the request hash must cover it like the speed channel.
            "course_time_constant_s": planner_input.ownship_course_time_constant_s,
            "mission_speed_plan_mps": planner_input.speed_plan_mps.tolist(),
            "execution_route_constraint": None
            if planner_input.execution_route_constraint is None
            else asdict(planner_input.execution_route_constraint),
        },
        "tracks": [
            _track_document(track)
            for track in sorted(
                planner_input.tracks,
                key=lambda item: (item.target_id, item.generation or 1),
            )
        ],
    }


def problem_hash_document(
    problem: MidMpcProblem,
    target_predictions: tuple[TargetPrediction, ...],
    horizon_encounter_plan: HorizonEncounterPlan,
    activation_plan: ConstraintActivationPlan,
    grid: GridSpec,
    preparation: NumericalPreparationPlan,
    *,
    parent_request_hash: str,
) -> dict[str, object]:
    """Return canonical, parent-linked semantic problem evidence."""
    return {
        "schema_version": "colav.mid_mpc.problem@3",
        "parent_request_hash": parent_request_hash,
        "problem": asdict(problem),
        "target_predictions": [_prediction_document(item) for item in target_predictions],
        "horizon_encounter_plan": horizon_encounter_plan_document(horizon_encounter_plan),
        "activation_plan": _activation_document(activation_plan),
        "grid": asdict(grid),
        "preparation": asdict(preparation),
    }


def _effective_node_clearance(
    planner_input: PlannerInput,
    tracks: tuple[TrackedObstacle, ...],
    config: MidMpcAssemblyConfig,
) -> float:
    if not tracks:
        return config.cpa_hard_m
    own_radius = 0.5 * math.hypot(planner_input.ownship_length_m, planner_input.ownship_width_m)
    target_allowances = []
    for track in tracks:
        footprint = 0.5 * math.hypot(track.length_m, track.width_m)
        covariance_allowance = math.sqrt(max(0.0, float(np.max(np.linalg.eigvalsh(track.covariance[:2, :2]))))) * math.sqrt(
            9.210340371976184
        )
        target_allowances.append(footprint + covariance_allowance)
    own_step_allowance = config.speed_bounds_mps[1] * config.horizon_dt_s
    return config.cpa_hard_m + own_radius + max(target_allowances) + own_step_allowance


def _wrap(angle: float) -> float:
    return math.atan2(math.sin(angle), math.cos(angle))


def _identity(snapshot: DecisionSnapshot) -> dict[str, object]:
    return {
        "epoch": snapshot.epoch,
        "sequence": snapshot.sequence,
        "sim_time_s": snapshot.sim_time_s,
        "input_hash": snapshot.input_hash,
        "profile_hash": snapshot.profile_hash,
    }


def _track_document(track: TrackedObstacle) -> dict[str, Any]:
    return {
        "target_id": track.target_id,
        "generation": track.generation,
        "state_enu": track.state_enu.tolist(),
        "covariance": track.covariance.tolist(),
        "length_m": track.length_m,
        "width_m": track.width_m,
        "observed_at_s": track.observed_at_s,
        "generated_at_s": track.generated_at_s,
        "status": track.status,
        "source": track.source,
    }


def _discard_cpa_conflicting_prefix(
    execution_prefix: RetainedPrefixPlan | None,
    target_predictions: tuple[TargetPrediction, ...],
    effective_cpa_hard_m: float,
    planner_input: PlannerInput,
    config: MidMpcAssemblyConfig,
    capability: CapabilitySnapshot,
) -> RetainedPrefixPlan | None:
    """Drop a retained prefix whose pinned geometry already violates CPA clearance.

    Pinning strips the optimizer of every degree of freedom inside the prefix,
    so a window that comes inside the hard clearance under the current
    predictions cannot be repaired by the free suffix; committing it would
    freeze an unsafe geometry as a promise. The prefix is discarded whole
    instead of truncated: a shortened head still hands the free beats the
    pinned corridor's deepest excursion and couples the corridor rows with a
    cut-off head. Mirrors the solver CPA rows: own steps first, targets
    advance linearly across the same interval.

    Beyond the pinned window the prefix hands the free suffix a straight
    continuation, so the release point is also certified: if the closest
    approach under that continuation sits inside the hard clearance and an
    immediate optimal-side rate turn cannot rebuild the missing margin
    before the meet, the promise is discarded whole as well. A discard
    returns the transport stub instead of ``None`` so the planner can still
    publish a GNC execution route.
    """
    if execution_prefix is None:
        return None
    north_m = float(planner_input.ownship_state[0])
    east_m = float(planner_input.ownship_state[1])
    for k, (course_rad, speed_mps) in enumerate(zip(execution_prefix.course_rad, execution_prefix.speed_mps, strict=True)):
        north_m += speed_mps * config.horizon_dt_s * math.cos(course_rad)
        east_m += speed_mps * config.horizon_dt_s * math.sin(course_rad)
        for prediction in target_predictions:
            distance_m = math.hypot(north_m - float(prediction.north_m[k]), east_m - float(prediction.east_m[k]))
            if distance_m < effective_cpa_hard_m:
                return _discard_stub_prefix(execution_prefix, planner_input)
    if not _release_point_margin_ok(
        execution_prefix,
        north_m,
        east_m,
        target_predictions,
        effective_cpa_hard_m,
        planner_input,
        config,
        capability,
    ):
        return _discard_stub_prefix(execution_prefix, planner_input)
    return execution_prefix


def _release_point_margin_ok(
    execution_prefix: RetainedPrefixPlan,
    end_north_m: float,
    end_east_m: float,
    target_predictions: tuple[TargetPrediction, ...],
    effective_cpa_hard_m: float,
    planner_input: PlannerInput,
    config: MidMpcAssemblyConfig,
    capability: CapabilitySnapshot,
) -> bool:
    """Certify that a rate turn after release can rebuild the CPA shortfall.

    The straight continuation along the prefix end course meets each linear
    prediction at its closest approach; the missing margin there must be
    covered by the lateral offset an optimal-side turn integrates at the
    full rate envelope, using max(prefix end speed, speed cap) as the
    conservative travel rate. Mirrors the offline release-margin certificate:
    turn away from the meet bearing, one rot step per beat, offset capped by
    the distance actually sailed. A discard/degraded stub pins nothing and
    promises no continuation, so it passes without a certificate.
    """
    if not execution_prefix.course_rad:
        return True
    dt_s = config.horizon_dt_s
    rot_step_rad = capability.rot_max_rad_s * dt_s
    u_last_mps = float(execution_prefix.speed_mps[-1])
    u_eff_mps = max(u_last_mps, capability.speed_bounds_mps[1])
    end_course_rad = float(execution_prefix.course_rad[-1])
    own_vn_mps = u_last_mps * math.cos(end_course_rad)
    own_ve_mps = u_last_mps * math.sin(end_course_rad)
    heading_hi_rad = float(planner_input.ownship_state[2]) + capability.heading_window_rad
    heading_lo_rad = float(planner_input.ownship_state[2]) - capability.heading_window_rad
    prefix_time_s = len(execution_prefix.course_rad) * dt_s
    for prediction in target_predictions:
        target_vn_mps, target_ve_mps = prediction.velocity_ne_mps
        rel_n_m = end_north_m - (float(prediction.north_m[0]) + target_vn_mps * prefix_time_s)
        rel_e_m = end_east_m - (float(prediction.east_m[0]) + target_ve_mps * prefix_time_s)
        rel_vn_mps = own_vn_mps - target_vn_mps
        rel_ve_mps = own_ve_mps - target_ve_mps
        speed_sq = rel_vn_mps * rel_vn_mps + rel_ve_mps * rel_ve_mps
        meet_offset_s = max(0.0, -(rel_n_m * rel_vn_mps + rel_e_m * rel_ve_mps) / speed_sq) if speed_sq > 1.0e-12 else 0.0
        meet_n_m = rel_n_m + rel_vn_mps * meet_offset_s
        meet_e_m = rel_e_m + rel_ve_mps * meet_offset_s
        required_m = effective_cpa_hard_m - math.hypot(meet_n_m, meet_e_m)
        if required_m <= 0.0:
            continue
        # The optimal side turns away from the meet bearing; integrate the
        # rate-ramped lateral offset against the prefix end course baseline.
        bearing_rad = math.atan2(-meet_e_m, -meet_n_m)
        turn = -1.0 if _wrap(bearing_rad - end_course_rad) > 0.0 else 1.0
        course_rad = end_course_rad
        best_m = 0.0
        for _ in range(int(meet_offset_s / dt_s)):
            target_course_rad = heading_hi_rad if turn > 0.0 else heading_lo_rad
            course_rad += min(max(target_course_rad - course_rad, -rot_step_rad), rot_step_rad)
            best_m += u_eff_mps * dt_s * abs(math.sin(course_rad - end_course_rad))
        if min(best_m, u_eff_mps * meet_offset_s) < required_m:
            return False
    return True


@dataclass(frozen=True)
class _ContractRecovery:
    """Locked-side shaping evidence carried by a contract-driven prefix discard."""

    side: int
    baseline_course_rad: float


def _is_discard_stub(execution_prefix: RetainedPrefixPlan | None) -> bool:
    """True when the prefix is the transport stub of a discarded route.

    ``compile_retained_prefix`` always pins two or more beats and a discard
    removes every one of them, so the empty-course stub is unambiguous.
    """
    return execution_prefix is not None and not execution_prefix.course_rad


def _discard_stub_prefix(
    execution_prefix: RetainedPrefixPlan,
    planner_input: PlannerInput,
) -> RetainedPrefixPlan:
    """Transport stub replacing a discarded retained prefix.

    The discard strips every pinned beat, but the planner must still publish
    a GNC-executable route on the same admission envelope: the retained
    corridor (constraint identity, ``lateral_limit_m`` and the corridor
    points) is what keeps the committed geometry inside the GNC lateral
    update guard — a discard is exactly the largest lateral rewrite, so the
    avoidance-coded stub re-anchors the route at the measured position (the
    anchor ``compile_execution_route`` validates against ``predicted[:, 0]``)
    and lets the optimized suffix own the geometry from beat one while the
    corridor bound still caps it.
    """
    return RetainedPrefixPlan(
        constraint=execution_prefix.constraint,
        points_ne_m=(tuple(map(float, planner_input.ownship_state[:2])),),
        route_speed_mps=execution_prefix.route_speed_mps[:1],
        # GNC admission protocol: a plain route update may only deviate
        # 100 m from the last feedback path (max_dynamic_lateral_delta_m),
        # while route points carrying the avoidance code relax the guard to
        # the 500 m avoidance envelope. The mode code is the planner's
        # semantic declaration of the maneuver class, and a contract/CPA
        # discard beat is an avoidance maneuver: the reversal away from the
        # discarded route is far larger than the cruise guard allows.
        navigation_modes=("avoidance",),
        course_rad=(),
        speed_mps=(),
        incoming_course_rad=float(planner_input.ownship_state[2]),
        retained_point_count=1,
        corridor_points_m=execution_prefix.corridor_points_m,
        knot_trim_reason=execution_prefix.knot_trim_reason,
    )


def _discard_contract_conflicting_prefix(
    execution_prefix: RetainedPrefixPlan,
    snapshot: DecisionSnapshot,
    planner_input: PlannerInput,
    capability: CapabilitySnapshot,
    config: MidMpcAssemblyConfig,
) -> tuple[RetainedPrefixPlan | None, _ContractRecovery | None]:
    """Drop a retained prefix that cannot honor a committed COLREG obligation.

    While Lifecycle holds an unmet COMMITTED obligation, a retained prefix
    that turns against the locked passing side — the same predicate and
    observed-state floor the L4 COLREG_LOCKED_SIDE check applies — or whose
    released geometry cannot reach the required alteration by the achievement
    deadline even with a full rate ramp, dead-ends every candidate exactly
    like the pinned CPA violation: the acceptance layer would reject any plan
    built on it. The discard is whole, on the same exit as the safety guard,
    and reports the locked side so the beat can stage the immediate recovery.
    No commitment, an achieved action, or a side-less obligation leaves the
    prefix untouched. A discard returns the transport stub (the caller reads
    the recovery evidence separately), never a bare ``None``. A prefix the
    safety guard already stubbed is left as-is: its recovery shaping stays
    reserved for contract discards.
    """
    if _is_discard_stub(execution_prefix):
        return execution_prefix, None
    dt_s = config.horizon_dt_s
    prefix_k = len(execution_prefix.course_rad)
    own_psi_rad = float(planner_input.ownship_state[2])
    for decision in snapshot.targets:
        side = {PassingSide.STARBOARD: 1, PassingSide.PORT: -1}.get(decision.passing_side, 0)
        if (
            side == 0
            or decision.action_achieved
            or decision.commitment is not CommitmentPhase.COMMITTED
            or decision.risk not in {RiskPhase.ACTIVE, RiskPhase.PAST_CLEAR}
            or decision.baseline_course_rad is None
            or not math.isfinite(decision.baseline_course_rad)
        ):
            continue
        baseline_rad = float(decision.baseline_course_rad)
        # The L4 deadline check reads the first executable beat once the
        # absolute deadline has passed; a prefix releases at its own end.
        if decision.action_achievement_deadline_s is not None:
            deadline_offset_s = max(0.0, float(decision.action_achievement_deadline_s) - planner_input.sim_time_s)
        else:
            deadline_offset_s = 2.0 * dt_s
        floor = min(0.0, side * _wrap(own_psi_rad - baseline_rad))
        span_k = min(prefix_k, max(1, math.ceil(deadline_offset_s / dt_s)))
        locked_side_violated = any(
            side * _wrap(float(course_rad) - baseline_rad) < floor - 1.0e-3
            for course_rad in execution_prefix.course_rad[:span_k]
        )
        ramp_s = max(0.0, deadline_offset_s - prefix_k * dt_s)
        reachable_rad = (
            side * _wrap(float(execution_prefix.course_rad[-1]) - baseline_rad) + capability.rot_max_rad_s * ramp_s
        )
        if not locked_side_violated and reachable_rad + 1.0e-6 >= decision.required_course_change_rad:
            continue
        return _discard_stub_prefix(execution_prefix, planner_input), _ContractRecovery(
            side=side, baseline_course_rad=baseline_rad
        )
    return execution_prefix, None


def _contract_recovery_schedule(
    schedule: MidMpcRowSchedule,
    *,
    recovery: _ContractRecovery | None,
    own_psi_rad: float,
    rot_step_rad: float,
    min_alteration_rad: float,
    horizon_steps: int,
    scheduled: bool,
) -> MidMpcRowSchedule:
    """Stage the immediate locked-side recovery on a contract-discard beat.

    k=1 is pressed to the committed baseline side (the heading must not cross
    to the disfavored side of the baseline), relaxed only by the rotation
    beats the free knot owns — the same rate-aware staging the scheduled
    corridor uses. From k=2 the substantial-alteration window is advanced to
    its rot-feasible beat so the freed horizon plans the committed maneuver
    immediately instead of behind the released prefix tail; the solver clips
    its interior-point seed into the same course box, which anchors the seed
    on the locked side too. A scheduled corridor already owns the alteration
    staging, so there only the course bounds are combined.
    """
    if recovery is None:
        return schedule
    side = recovery.side
    bounds = list(schedule.course_bounds_rad) or [(None, None)] * horizon_steps
    lower_rad, upper_rad = bounds[1]
    if side > 0:
        bound_rad = min(recovery.baseline_course_rad, own_psi_rad + 2.0 * rot_step_rad)
        bounds[1] = (bound_rad if lower_rad is None else max(lower_rad, bound_rad), upper_rad)
    else:
        bound_rad = max(recovery.baseline_course_rad, own_psi_rad - 2.0 * rot_step_rad)
        bounds[1] = (lower_rad, bound_rad if upper_rad is None else min(upper_rad, bound_rad))
    if not scheduled:
        start_k = max(2, math.ceil(min_alteration_rad / rot_step_rad) - 1)
        stop_k = max(
            start_k,
            schedule.min_alt_hard_window.stop_k if schedule.min_alt_hard_window is not None else horizon_steps,
        )
        schedule = replace(schedule, min_alt_hard_window=MidMpcHardWindow(start_k, stop_k))
    return replace(schedule, course_bounds_rad=tuple(bounds))


def _target_predictions(
    selected_keys: tuple[TrackKey, ...],
    track_by_key: dict[TrackKey, TrackedObstacle],
    reference_time_s: float,
    config: MidMpcAssemblyConfig,
) -> tuple[TargetPrediction, ...]:
    times = np.arange(config.horizon_steps + 1, dtype=float) * config.horizon_dt_s
    predictions = []
    for key in selected_keys:
        track = track_by_key[key]
        covariance_margin = math.sqrt(max(0.0, float(np.max(np.linalg.eigvalsh(track.covariance[:2, :2]))))) * math.sqrt(
            9.210340371976184
        )
        predictions.append(
            TargetPrediction(
                key=key,
                reference_time_s=reference_time_s,
                velocity_ne_mps=(float(track.state_enu[2]), float(track.state_enu[3])),
                times_s=times,
                north_m=track.state_enu[0] + track.state_enu[2] * times,
                east_m=track.state_enu[1] + track.state_enu[3] * times,
                position_uncertainty_m=np.full(times.shape, covariance_margin),
            )
        )
    return tuple(predictions)


def _prediction_document(prediction: TargetPrediction) -> dict[str, Any]:
    return {
        "key": asdict(prediction.key),
        "reference_time_s": prediction.reference_time_s,
        "velocity_ne_mps": list(prediction.velocity_ne_mps),
        "times_s": prediction.times_s.tolist(),
        "north_m": prediction.north_m.tolist(),
        "east_m": prediction.east_m.tolist(),
        "position_uncertainty_m": prediction.position_uncertainty_m.tolist(),
    }


def _activation_plan(
    decisions: tuple[TargetDecision, ...],
    tracks: tuple[TrackedObstacle, ...],
    planner_input: PlannerInput,
    effective_cpa_hard_m: float,
    minimum_change_rad: float,
    min_alt_hard_from_k: int,
    config: MidMpcAssemblyConfig,
    capability: CapabilitySnapshot,
    *,
    reachable_when_diverging: bool = False,
    scheduled_motion: bool = False,
) -> ConstraintActivationPlan:
    ownship = planner_input.ownship_state
    own_velocity = np.array(
        [
            ownship[3] * math.cos(ownship[2]) - ownship[4] * math.sin(ownship[2]),
            ownship[3] * math.sin(ownship[2]) + ownship[4] * math.cos(ownship[2]),
        ]
    )
    lead_time_s = max(
        2.0 * config.horizon_dt_s,
        minimum_change_rad / capability.rot_max_rad_s if capability.rot_max_rad_s > 0.0 else 0.0,
    )
    targets = tuple(
        TargetActivation(
            key=decision.key,
            cpa_hard_from_s=activation_s,
            cpa_hard_from_k=min(
                config.horizon_steps,
                math.floor(activation_s / config.horizon_dt_s),
            ),
            direction_hard_from_s=(config.horizon_dt_s if decision.risk is RiskPhase.CANDIDATE else 0.0),
            direction_hard_from_k=(1 if decision.risk is RiskPhase.CANDIDATE else 0),
            min_alt_hard_from_s=min_alt_hard_from_k * config.horizon_dt_s,
            min_alt_hard_from_k=min_alt_hard_from_k,
        )
        for decision, activation_s in zip(
            decisions,
            (
                (
                    config.horizon_steps * config.horizon_dt_s
                    if decision.role in {OwnshipRole.STAND_ON, OwnshipRole.OVERTAKEN}
                    and decision.rule17 is Rule17Stage.STAND_ON
                    else _reachable_cpa_activation_time_s(
                        track,
                        ownship[:2],
                        effective_cpa_hard_m,
                        config,
                    )
                    if decision.role is OwnshipRole.NONE and decision.risk is RiskPhase.CLEAR
                    else min(
                        _cpa_activation_time_s(
                            track,
                            ownship[:2],
                            own_velocity,
                            effective_cpa_hard_m,
                            lead_time_s,
                            config,
                        ),
                        # The linear TCPA staging assumes current velocities.
                        # A maneuvering ownship can create an encounter earlier
                        # (head_on seam-01: TCPA staged the hard window at k=51
                        # while the candidate closed to 42 m at k=34), so the
                        # hard window also starts once a violation becomes
                        # physically possible. Knots before that point are
                        # trivially satisfied by every motion, so the earlier
                        # start adds enforcement without infeasibility risk.
                        _reachable_cpa_activation_time_s(
                            track,
                            ownship[:2],
                            effective_cpa_hard_m,
                            config,
                        ),
                    )
                )
                for decision, track in zip(decisions, tracks, strict=True)
            ),
            strict=True,
        )
    )
    if reachable_when_diverging:
        updated = []
        for activation, decision, track in zip(targets, decisions, tracks, strict=True):
            next_activation = activation
            stand_on = (
                decision.role in {OwnshipRole.STAND_ON, OwnshipRole.OVERTAKEN} and decision.rule17 is Rule17Stage.STAND_ON
            )
            if (scheduled_motion or activation.cpa_hard_from_k == config.horizon_steps) and not stand_on:
                # Turning away eliminates current-motion CPA, not the contact's
                # physical safety obligation during later predicted route turns.
                seconds = _reachable_cpa_activation_time_s(track, ownship[:2], effective_cpa_hard_m, config)
                seconds = min(seconds, activation.cpa_hard_from_s)
                next_activation = replace(
                    activation,
                    cpa_hard_from_s=seconds,
                    cpa_hard_from_k=min(config.horizon_steps, math.floor(seconds / config.horizon_dt_s)),
                )
            updated.append(next_activation)
        targets = tuple(updated)
    return ConstraintActivationPlan(
        targets=targets,
        global_cpa_hard_from_k=min(
            (target.cpa_hard_from_k for target in targets),
            default=config.horizon_steps,
        ),
        global_direction_hard_from_k=min(
            (target.direction_hard_from_k for target in targets),
            default=0,
        ),
        global_min_alt_hard_from_k=min(
            (target.min_alt_hard_from_k for target in targets),
            default=0,
        ),
    )


def _cpa_activation_time_s(
    track: TrackedObstacle,
    own_position_ne_m: np.ndarray,
    own_velocity_ne_mps: np.ndarray,
    effective_cpa_hard_m: float,
    lead_time_s: float,
    config: MidMpcAssemblyConfig,
) -> float:
    relative_position = track.state_enu[:2] - own_position_ne_m
    relative_velocity = track.state_enu[2:4] - own_velocity_ne_mps
    duration_s = config.horizon_steps * config.horizon_dt_s
    if float(relative_position @ relative_position) <= effective_cpa_hard_m**2:
        return 0.0
    relative_speed_squared = float(relative_velocity @ relative_velocity)
    if relative_speed_squared <= 1.0e-12:
        return duration_s
    tcpa_s = -float(relative_position @ relative_velocity) / relative_speed_squared
    if tcpa_s <= 0.0 or tcpa_s > duration_s:
        return duration_s
    relative_at_cpa = relative_position + relative_velocity * tcpa_s
    if float(relative_at_cpa @ relative_at_cpa) > effective_cpa_hard_m**2:
        return duration_s
    return max(0.0, tcpa_s - lead_time_s)


def _reachable_cpa_activation_time_s(
    track: TrackedObstacle,
    own_position_ne_m: np.ndarray,
    effective_cpa_hard_m: float,
    config: MidMpcAssemblyConfig,
) -> float:
    relative_position = track.state_enu[:2] - own_position_ne_m
    duration_s = config.horizon_steps * config.horizon_dt_s
    if float(relative_position @ relative_position) <= effective_cpa_hard_m**2:
        return 0.0
    max_own_speed_mps = config.speed_bounds_mps[1]
    for k in range(1, config.horizon_steps + 1):
        time_s = k * config.horizon_dt_s
        target_offset = relative_position + track.state_enu[2:4] * time_s
        reachable_clearance = float(np.linalg.norm(target_offset)) - max_own_speed_mps * time_s
        if reachable_clearance <= effective_cpa_hard_m:
            return max(0.0, time_s - config.horizon_dt_s)
    return duration_s


def _activation_document(plan: ConstraintActivationPlan) -> dict[str, Any]:
    return {
        "targets": [
            {
                **asdict(target),
                "key": asdict(target.key),
            }
            for target in plan.targets
        ],
        "global_cpa_hard_from_k": plan.global_cpa_hard_from_k,
        "global_direction_hard_from_k": plan.global_direction_hard_from_k,
        "global_min_alt_hard_from_k": plan.global_min_alt_hard_from_k,
    }


def _admission_rank(decision: TargetDecision) -> int:
    if decision.risk is RiskPhase.RELEASED and not decision.recovery_guard_active:
        return 0
    if decision.rule17 is Rule17Stage.MUST_ACT:
        return 5
    if decision.commitment is CommitmentPhase.COMMITTED and decision.risk is RiskPhase.ACTIVE:
        return 4
    if decision.rule17 is Rule17Stage.MAY_ACT:
        return 3
    if decision.rule17 is Rule17Stage.STAND_ON:
        return 2
    if decision.risk is RiskPhase.ACTIVE:
        return 3
    if decision.risk is RiskPhase.CANDIDATE:
        return 2
    if decision.risk is RiskPhase.PAST_CLEAR or decision.recovery_guard_active:
        return 1
    return 1


def _admit_target_keys(
    snapshot: DecisionSnapshot,
    track_by_key: dict[TrackKey, TrackedObstacle],
    max_targets: int,
    *,
    safety_conflict_keys: frozenset[TrackKey],
) -> tuple[tuple[TrackKey, ...], tuple[TrackKey, ...]]:
    missing_tracks = [key for key in snapshot.directive.required_targets if key not in track_by_key]
    if missing_tracks:
        raise _AssemblyInputError(
            AssemblyFailureCode.TARGET_BINDING_MISSING,
            f"lifecycle target keys missing from PlannerInput: {missing_tracks}",
        )
    decision_by_key = {decision.key: decision for decision in snapshot.targets}
    missing_decisions = [key for key in track_by_key if key not in decision_by_key]
    if missing_decisions:
        raise _AssemblyInputError(
            AssemblyFailureCode.TARGET_BINDING_MISSING,
            f"PlannerInput target keys missing lifecycle decisions: {missing_decisions}",
        )
    required_keys = tuple(sorted(snapshot.directive.required_targets, key=lambda key: (key.target_id, key.generation)))
    eligible = sorted(
        (
            decision
            for decision in snapshot.targets
            if decision.key not in required_keys
            and decision.key in track_by_key
            and (_admission_rank(decision) > 0 or decision.key in safety_conflict_keys)
        ),
        key=_admission_sort_key,
    )
    selected_keys = required_keys + tuple(decision.key for decision in eligible[: max_targets - len(required_keys)])
    return required_keys, selected_keys


def _mission_route_conflict_keys(
    planner_input: PlannerInput,
    route: RouteReference,
    snapshot: DecisionSnapshot,
    track_by_key: dict[TrackKey, TrackedObstacle],
    config: MidMpcAssemblyConfig,
    *,
    consider_terminal_stop: bool = False,
) -> frozenset[TrackKey]:
    """Retain non-obligated tracks whose constant-velocity mission route enters the safety domain."""
    own_position = np.asarray(planner_input.ownship_state[:2], dtype=float)
    own_velocity = route.planned_speed_mps * np.array(
        (math.cos(route.bearing_rad), math.sin(route.bearing_rad)),
        dtype=float,
    )
    own_radius = 0.5 * math.hypot(planner_input.ownship_length_m, planner_input.ownship_width_m)
    horizon_s = config.horizon_steps * config.horizon_dt_s
    conflicts: set[TrackKey] = set()
    for decision in snapshot.targets:
        if decision.risk not in {RiskPhase.CLEAR, RiskPhase.RELEASED} or decision.recovery_guard_active:
            continue
        track = track_by_key.get(decision.key)
        if track is None:
            continue
        if consider_terminal_stop and route.mission_waypoints_ne_m:
            goal = np.asarray(route.mission_waypoints_ne_m[-1])
            earliest_arrival = float(np.linalg.norm(goal - own_position)) / config.speed_bounds_mps[1]
            if earliest_arrival < horizon_s:
                start = track.state_enu[:2] + track.state_enu[2:4] * earliest_arrival
                travel = track.state_enu[2:4] * (horizon_s - earliest_arrival)
                fraction = float(np.clip((goal - start) @ travel / max(float(travel @ travel), 1e-12), 0.0, 1.0))
                clearance = _effective_node_clearance(planner_input, (track,), config)
                if np.linalg.norm(goal - start - fraction * travel) < clearance:
                    # A released overtaking contact can catch a stopped ownship.
                    # Keep it as a numerical safety obstacle; do not reclassify
                    # the completed COLREG encounter or discard tail safety.
                    conflicts.add(decision.key)
                    continue
        relative_position = np.asarray(track.state_enu[:2], dtype=float) - own_position
        relative_velocity = np.asarray(track.state_enu[2:4], dtype=float) - own_velocity
        relative_speed_sq = float(relative_velocity @ relative_velocity)
        if relative_speed_sq <= 1.0e-12:
            continue
        tcpa_s = -float(relative_position @ relative_velocity) / relative_speed_sq
        if not 0.0 <= tcpa_s <= horizon_s:
            continue
        dcpa_m = float(np.linalg.norm(relative_position + relative_velocity * tcpa_s))
        target_radius = 0.5 * math.hypot(track.length_m, track.width_m)
        if dcpa_m < config.cpa_safe_m + own_radius + target_radius:
            conflicts.add(decision.key)
    return frozenset(conflicts)


def _admission_sort_key(decision: TargetDecision) -> tuple[float, ...]:
    tcpa_s = decision.geometry.signed_tcpa_s
    return (
        -float(_admission_rank(decision)),
        tcpa_s if tcpa_s >= 0.0 else math.inf,
        decision.geometry.range_m,
        float(decision.key.target_id),
        float(decision.key.generation),
    )


def _hash_document(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
