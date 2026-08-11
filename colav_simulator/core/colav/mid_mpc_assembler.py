"""Stateless mapping from lifecycle decisions to the frozen Mid-MPC core."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any

import numpy as np

from colav_simulator.core.colav.custom_mpc_adapter import PlannerInput, TrackedObstacle
from colav_simulator.core.colav.encounter_lifecycle import (
    DecisionSnapshot,
    EncounterKind,
    PassingSide,
)
from colav_simulator.core.colav.mid_mpc import (
    MidMpcOwnShip,
    MidMpcProblem,
    MidMpcRouteFrame,
    MidMpcRowSchedule,
    MidMpcTarget,
)
from colav_simulator.core.tracking.trackers import TrackKey


@dataclass(frozen=True)
class MidMpcAssemblyConfig:
    horizon_steps: int = 80
    horizon_dt_s: float = 15.0
    heading_window_rad: float = math.radians(45.0)
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
    planned_speed_mps: float

    def __post_init__(self) -> None:
        """Validate immutable route evidence."""
        values = (*self.anchor_ne_m, self.bearing_rad, self.planned_speed_mps)
        if not np.isfinite(values).all():
            raise ValueError("route reference values must be finite")


@dataclass(frozen=True)
class CapabilitySnapshot:
    heading_window_rad: float
    speed_bounds_mps: tuple[float, float]
    rot_max_rad_s: float
    decel_max_mps2: float
    source: str = "published_kinematic_csog"

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
        if not self.source:
            raise ValueError("capability source is required")


class AssemblyProfile(StrEnum):
    MASS_PARITY = "MASS_PARITY"
    COLAV_STRICT = "COLAV_STRICT"


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
    route: RouteReference
    capability: CapabilitySnapshot
    config: MidMpcAssemblyConfig
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
class TargetPrediction:
    key: TrackKey
    times_s: np.ndarray
    north_m: np.ndarray
    east_m: np.ndarray
    position_uncertainty_m: np.ndarray

    def __post_init__(self) -> None:
        """Copy prediction vectors into immutable arrays."""
        lengths: set[int] = set()
        for name in ("times_s", "north_m", "east_m", "position_uncertainty_m"):
            values = np.array(getattr(self, name), dtype=float, copy=True)
            if values.ndim != 1 or not np.isfinite(values).all():
                raise ValueError(f"{name} must be a finite vector")
            values.setflags(write=False)
            object.__setattr__(self, name, values)
            lengths.add(values.size)
        if len(lengths) != 1:
            raise ValueError("target prediction vectors must have equal length")


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
    problem_hash: str
    profile: AssemblyProfile
    target_predictions: tuple[TargetPrediction, ...]
    activation_plan: ConstraintActivationPlan
    grid: GridSpec
    preparation: NumericalPreparationPlan


class _AssemblyInputError(ValueError):
    def __init__(self, code: AssemblyFailureCode, message: str) -> None:
        super().__init__(message)
        self.code = code


class MidMpcProblemAssembler:
    """Atomic, stateless L1/L2 semantic problem assembler."""

    def assemble(self, request: AssemblyRequest) -> AssemblySuccess | AssemblyFailure:
        identity = _identity(request.snapshot)
        if not math.isclose(request.planner_input.sim_time_s, request.snapshot.sim_time_s, abs_tol=1.0e-9):
            return AssemblyFailure(
                code=AssemblyFailureCode.CYCLE_MISMATCH,
                message="planner input and lifecycle snapshot times differ",
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
    profile: AssemblyProfile,
) -> AssemblySuccess:
    """Map one immutable decision snapshot without retaining business state."""
    track_by_key = {TrackKey(track.target_id, track.generation or 1): track for track in planner_input.tracks}
    missing = [key for key in snapshot.directive.required_targets if key not in track_by_key]
    if missing:
        raise _AssemblyInputError(
            AssemblyFailureCode.TARGET_BINDING_MISSING,
            f"lifecycle target keys missing from PlannerInput: {missing}",
        )
    selected_keys = tuple(
        sorted(
            snapshot.directive.required_targets,
            key=lambda key: (key.target_id, key.generation),
        )
    )
    selected_tracks = tuple(track_by_key[key] for key in selected_keys)
    decision_by_key = {decision.key: decision for decision in snapshot.targets}
    selected_decisions = tuple(decision_by_key[key] for key in selected_keys)
    required_sides = {
        decision.passing_side for decision in selected_decisions if decision.passing_side is not PassingSide.NONE
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
    corridor_decisions = tuple(decision for decision in selected_decisions if not decision.route_recovery_allowed)
    if corridor_decisions:
        corridor = max(corridor_decisions, key=lambda decision: decision.required_course_change_rad)
        if corridor.baseline_course_rad is None:
            raise ValueError(f"committed target {corridor.key} has no baseline course")
        committed_route_bearing = corridor.baseline_course_rad + preferred_side * corridor.required_course_change_rad
    elif selected_decisions:
        recovery_delta = _wrap(route.bearing_rad - float(planner_input.ownship_state[2]))
        recovery_step = config.rot_max_rad_s * config.decision_period_s
        committed_route_bearing = float(planner_input.ownship_state[2]) + float(
            np.clip(recovery_delta, -recovery_step, recovery_step)
        )

    ownship = planner_input.ownship_state
    effective_cpa_hard_m = _effective_node_clearance(planner_input, selected_tracks, config)
    minimum_change = snapshot.directive.minimum_course_change_rad if lateral_active else 0.0
    reachable_per_step = config.rot_max_rad_s * config.horizon_dt_s
    min_alt_hard_from_k = max(0, math.ceil(minimum_change / reachable_per_step) - 1) if lateral_active else 0
    activation_plan = _activation_plan(
        selected_decisions,
        selected_tracks,
        planner_input,
        effective_cpa_hard_m,
        minimum_change,
        min_alt_hard_from_k,
        config,
    )
    row_schedule = MidMpcRowSchedule(
        cpa_hard_from_k=activation_plan.global_cpa_hard_from_k,
        direction_hard_from_k=activation_plan.global_direction_hard_from_k,
        min_alt_hard_from_k=activation_plan.global_min_alt_hard_from_k,
        terminal_rows_enabled=False,
    )
    starboard_asymmetry = any(
        decision.passing_side is PassingSide.STARBOARD
        and decision.encounter in {EncounterKind.HEAD_ON, EncounterKind.CROSSING}
        for decision in selected_decisions
    )
    problem = MidMpcProblem(
        own_ship=MidMpcOwnShip(psi_rad=float(ownship[2]), u_mps=float(ownship[3])),
        route_bearing_rad=committed_route_bearing,
        planned_speed_mps=0.0 if snapshot.directive.stop_required else route.planned_speed_mps,
        heading_bounds_rad=(
            float(ownship[2]) - capability.heading_window_rad,
            float(ownship[2]) + capability.heading_window_rad,
        ),
        speed_bounds_mps=speed_bounds,
        cpa_safe_m=max(config.cpa_safe_m, effective_cpa_hard_m),
        cpa_hard_m=effective_cpa_hard_m,
        rot_max_rad_s=capability.rot_max_rad_s,
        decel_max_mps2=capability.decel_max_mps2,
        lateral_active=lateral_active,
        preferred_side=preferred_side,
        starboard_asymmetry_active=starboard_asymmetry,
        min_alteration_rad=minimum_change,
        route_frame=MidMpcRouteFrame(
            origin_m=(
                route.anchor_ne_m[0] - float(ownship[0]),
                route.anchor_ne_m[1] - float(ownship[1]),
            ),
            normal=(-math.sin(committed_route_bearing), math.cos(committed_route_bearing)),
            bearing_rad=committed_route_bearing,
            lateral_scale_m=config.route_lateral_scale_m,
            weight=config.route_weight,
        ),
        row_schedule=row_schedule,
        audit_row_count=len(selected_tracks),
        targets=tuple(
            MidMpcTarget(
                x_m=float(track.state_enu[0] - ownship[0]),
                y_m=float(track.state_enu[1] - ownship[1]),
                cog_rad=float(math.atan2(track.state_enu[3], track.state_enu[2])),
                sog_mps=float(np.linalg.norm(track.state_enu[2:4])),
            )
            for track in selected_tracks
        ),
    )
    target_predictions = _target_predictions(selected_keys, track_by_key, config)
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
            "target_count": len(selected_tracks),
            "audit_row_count": problem.audit_row_count,
            "row_schedule": asdict(problem.row_schedule),
            "slack_topology": ["cpa", "direction"],
            "terminal_rows_enabled": problem.row_schedule.terminal_rows_enabled,
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
    request_hash = _hash_document(
        {
            "identity": _identity(snapshot),
            "decision_snapshot": asdict(snapshot),
            "route": asdict(route),
            "capability": asdict(capability),
            "config": asdict(config),
            "profile": profile.value,
            "ownship": planner_input.ownship_state.tolist(),
            "tracks": [
                _track_document(track)
                for track in sorted(
                    planner_input.tracks,
                    key=lambda item: (item.target_id, item.generation or 1),
                )
            ],
        }
    )
    problem_document = asdict(problem)
    problem_document["target_predictions"] = [_prediction_document(item) for item in target_predictions]
    problem_document["activation_plan"] = _activation_document(activation_plan)
    problem_document["grid"] = asdict(grid)
    problem_document["preparation"] = asdict(preparation)
    return AssemblySuccess(
        problem=problem,
        selected_target_keys=selected_keys,
        selected_tracks=selected_tracks,
        effective_cpa_hard_m=effective_cpa_hard_m,
        request_hash=request_hash,
        problem_hash=_hash_document(problem_document),
        profile=profile,
        target_predictions=target_predictions,
        activation_plan=activation_plan,
        grid=grid,
        preparation=preparation,
    )


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
        target_step_allowance = float(np.linalg.norm(track.state_enu[2:4])) * config.horizon_dt_s
        target_allowances.append(footprint + covariance_allowance + target_step_allowance)
    return config.cpa_hard_m + own_radius + max(target_allowances)


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
        "times_s": prediction.times_s.tolist(),
        "north_m": prediction.north_m.tolist(),
        "east_m": prediction.east_m.tolist(),
        "position_uncertainty_m": prediction.position_uncertainty_m.tolist(),
    }


def _activation_plan(
    decisions: tuple[Any, ...],
    tracks: tuple[TrackedObstacle, ...],
    planner_input: PlannerInput,
    effective_cpa_hard_m: float,
    minimum_change_rad: float,
    min_alt_hard_from_k: int,
    config: MidMpcAssemblyConfig,
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
        minimum_change_rad / config.rot_max_rad_s if config.rot_max_rad_s > 0.0 else 0.0,
    )
    targets = tuple(
        TargetActivation(
            key=decision.key,
            cpa_hard_from_s=activation_s,
            cpa_hard_from_k=min(
                config.horizon_steps,
                math.floor(activation_s / config.horizon_dt_s),
            ),
            direction_hard_from_s=0.0,
            direction_hard_from_k=0,
            min_alt_hard_from_s=min_alt_hard_from_k * config.horizon_dt_s,
            min_alt_hard_from_k=min_alt_hard_from_k,
        )
        for decision, activation_s in zip(
            decisions,
            (
                _cpa_activation_time_s(
                    track,
                    ownship[:2],
                    own_velocity,
                    effective_cpa_hard_m,
                    lead_time_s,
                    config,
                )
                for track in tracks
            ),
            strict=True,
        )
    )
    return ConstraintActivationPlan(
        targets=targets,
        global_cpa_hard_from_k=min((target.cpa_hard_from_k for target in targets), default=config.horizon_steps),
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


def _hash_document(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()
