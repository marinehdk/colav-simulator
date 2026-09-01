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
from colav_simulator.core.colav.rolling_plan import RollingPlanReference
from colav_simulator.core.tracking.trackers import TrackKey


@dataclass(frozen=True)
class MidMpcAssemblyConfig:
    horizon_steps: int = 80
    horizon_dt_s: float = 5.0
    heading_window_rad: float = math.radians(45.0)
    stand_on_course_tolerance_rad: float = math.radians(5.0)
    speed_bounds_mps: tuple[float, float] = (0.0, 8.0)
    cpa_safe_m: float = 150.0
    cpa_hard_m: float = 50.0
    rot_max_rad_s: float = math.radians(3.0)
    decel_max_mps2: float = 0.3
    route_lateral_scale_m: float = 1000.0
    route_weight: float = 1.0
    decision_period_s: float = 5.0
    max_targets: int = 16


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
    binding = _bind_targets(planner_input, snapshot, route, config)
    policy = _resolve_policy(planner_input, snapshot, route, capability, binding)
    target_predictions = _target_predictions(
        tuple(sorted(binding.track_by_key, key=lambda key: (key.target_id, key.generation))),
        binding.track_by_key,
        planner_input.sim_time_s,
        config,
    )
    effective_cpa_hard_m = _effective_node_clearance(planner_input, binding.selected_tracks, config)
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
    )


def _bind_targets(
    planner_input: PlannerInput,
    snapshot: DecisionSnapshot,
    route: RouteReference,
    config: MidMpcAssemblyConfig,
) -> _TargetBinding:
    track_by_key = {TrackKey(track.target_id, track.generation or 1): track for track in planner_input.tracks}
    safety_conflict_keys = _mission_route_conflict_keys(planner_input, route, snapshot, track_by_key, config)
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
        committed_route_bearing = corridor.baseline_course_rad + preferred_side * corridor.required_course_change_rad
    elif binding.required_decisions:
        committed_route_bearing = float(planner_input.ownship_state[2])

    return _PolicyResolution(
        speed_bounds_mps=speed_bounds,
        preferred_side=preferred_side,
        lateral_active=lateral_active,
        committed_route_bearing_rad=committed_route_bearing,
    )


def _compile_semantic_problem(
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
) -> _SemanticAssembly:
    ownship = planner_input.ownship_state
    minimum_change = snapshot.directive.minimum_course_change_rad if policy.lateral_active else 0.0
    reachable_per_step = capability.rot_max_rad_s * config.horizon_dt_s
    min_alt_hard_from_k = max(0, math.ceil(minimum_change / reachable_per_step) - 1) if policy.lateral_active else 0
    activation_plan = _activation_plan(
        binding.selected_decisions,
        binding.selected_tracks,
        planner_input,
        effective_cpa_hard_m,
        minimum_change,
        min_alt_hard_from_k,
        config,
        capability,
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
    )
    candidate_hold = not lateral_active and any(
        decision.risk is RiskPhase.CANDIDATE and decision.role in {OwnshipRole.GIVE_WAY, OwnshipRole.OVERTAKING}
        for decision in binding.selected_decisions
    )
    hold_first_interval = stand_on_hold or candidate_hold
    heading_bounds = (
        float(ownship[2]) - capability.heading_window_rad,
        float(ownship[2]) + capability.heading_window_rad,
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
    )
    route_frame_bearing = (
        route.mission_leg_bearing_rad if route_objective is not None else policy.committed_route_bearing_rad
    )
    problem = MidMpcProblem(
        own_ship=MidMpcOwnShip(psi_rad=float(ownship[2]), u_mps=float(ownship[3])),
        route_bearing_rad=policy.committed_route_bearing_rad,
        planned_speed_mps=0.0 if snapshot.directive.stop_required else route.planned_speed_mps,
        heading_bounds_rad=heading_bounds,
        speed_bounds_mps=policy.speed_bounds_mps,
        cpa_safe_m=max(config.cpa_safe_m, effective_cpa_hard_m),
        cpa_hard_m=effective_cpa_hard_m,
        rot_max_rad_s=capability.rot_max_rad_s,
        decel_max_mps2=capability.decel_max_mps2,
        lateral_active=lateral_active,
        preferred_side=preferred_side,
        starboard_asymmetry_active=starboard_asymmetry,
        min_alteration_rad=minimum_change,
        prefix_active_k=1 if hold_first_interval else 0,
        prefix_psi_rad=(float(ownship[2]),) if hold_first_interval else (),
        prefix_u_mps=(float(ownship[3]),) if hold_first_interval else (),
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
        audit_row_count=len(binding.selected_tracks),
        targets=tuple(
            MidMpcTarget(
                x_m=float(track.state_enu[0] - ownship[0]),
                y_m=float(track.state_enu[1] - ownship[1]),
                cog_rad=float(math.atan2(track.state_enu[3], track.state_enu[2])),
                sog_mps=float(np.linalg.norm(track.state_enu[2:4])),
                crossing_astern_required=(
                    decision.encounter is EncounterKind.CROSSING
                    and decision.role is OwnshipRole.GIVE_WAY
                    and decision.risk in {RiskPhase.ACTIVE, RiskPhase.PAST_CLEAR}
                    and not decision.action_achieved
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
        stop_k = (
            horizon_steps
            if target_window is None or target_window.recovery_from_k is None
            else min(target_window.recovery_from_k, horizon_steps)
        )
        cpa_windows.append(MidMpcHardWindow(start_k, max(start_k, stop_k)))
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
        continuity_heading_reference_rad=(rolling_plan.heading_reference_rad if rolling_plan is not None else ()),
        continuity_speed_reference_mps=(rolling_plan.speed_reference_mps if rolling_plan is not None else ()),
        continuity_weight=(rolling_plan.objective_weight if rolling_plan is not None else ()),
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
    for phase in plan.phases[:-1]:
        absolute_position = np.asarray(ownship_position_ne_m, dtype=float) + position
        mission, mission_anchor = _mission_route_projection(route, absolute_position)
        cross_track = float((position - route_origin) @ route_normal)
        lateral_references.append(cross_track)
        if phase in {HorizonEncounterPhase.ALTER, HorizonEncounterPhase.PASS}:
            desired_heading = corridor
        elif speed > 1.0e-9 and maximum_recovery_delta > 1.0e-9:
            if mission_anchor is not None:
                mission_normal = np.array((-math.sin(mission), math.cos(mission)), dtype=float)
                mission_cross_track = float((absolute_position - np.asarray(mission_anchor, dtype=float)) @ mission_normal)
            else:
                mission_cross_track = cross_track
            requested_lateral_velocity = float(np.clip(-mission_cross_track / dt_s, -speed, speed))
            recovery_delta = math.asin(requested_lateral_velocity / speed)
            recovery_delta = float(np.clip(recovery_delta, -maximum_recovery_delta, maximum_recovery_delta))
            desired_heading = mission + recovery_delta
        else:
            desired_heading = mission
        desired_heading = ownship_heading_rad + _wrap(desired_heading - ownship_heading_rad)
        desired_heading = previous_heading + _wrap(desired_heading - previous_heading)
        heading = previous_heading + float(
            np.clip(desired_heading - previous_heading, -maximum_heading_step, maximum_heading_step)
        )
        if not headings and recovery_first_step:
            # Corridor release: a first reference sitting exactly on the rot bound
            # makes the interior-point seed start on the active constraint and
            # IPOPT crawls the barrier for dozens of iterations; anchor the first
            # step on the current heading and let the ramp pull from step one.
            heading = ownship_heading_rad
        headings.append(heading)
        position += speed * dt_s * np.array((math.cos(heading), math.sin(heading)), dtype=float)
        previous_heading = heading

    return tuple(headings), tuple(lateral_references)


def _mission_route_projection(
    route: RouteReference,
    position_ne_m: np.ndarray,
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
    _, _, bearing, anchor = min(candidates, key=lambda candidate: (candidate[0], -candidate[1]))
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
        prefix=ExecutionPrefixPlan(),
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
    )
    plan = compile_horizon_encounter_plan(
        HorizonEncounterPlanRequest(
            reference_time_s=planner_input.sim_time_s,
            times_s=np.arange(config.horizon_steps + 1, dtype=float) * config.horizon_dt_s,
            own_position_ne_m=(float(planner_input.ownship_state[0]), float(planner_input.ownship_state[1])),
            mission_route_anchor_ne_m=route.anchor_ne_m,
            own_heading_rad=float(planner_input.ownship_state[2]),
            own_speed_mps=0.0 if snapshot.directive.stop_required else route.planned_speed_mps,
            mission_route_bearing_rad=route.mission_leg_bearing_rad,
            avoidance_corridor_bearing_rad=policy.committed_route_bearing_rad,
            rot_max_rad_s=capability.rot_max_rad_s,
            heading_window_rad=capability.heading_window_rad,
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
        "ownship": {
            "state": planner_input.ownship_state.tolist(),
            "length_m": planner_input.ownship_length_m,
            "width_m": planner_input.ownship_width_m,
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
                    else _cpa_activation_time_s(
                        track,
                        ownship[:2],
                        own_velocity,
                        effective_cpa_hard_m,
                        lead_time_s,
                        config,
                    )
                )
                for decision, track in zip(decisions, tracks, strict=True)
            ),
            strict=True,
        )
    )
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
