"""Stateless mapping from lifecycle decisions to the frozen Mid-MPC core."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from colav_simulator.core.colav.custom_mpc_adapter import PlannerInput, TrackedObstacle
from colav_simulator.core.colav.encounter_lifecycle import (
    DecisionSnapshot,
    EncounterKind,
    LifecycleError,
    LifecycleFailure,
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


@dataclass(frozen=True)
class AssembledMidMpcProblem:
    problem: MidMpcProblem
    selected_target_keys: tuple[TrackKey, ...]
    selected_tracks: tuple[TrackedObstacle, ...]
    effective_cpa_hard_m: float


def assemble_mid_mpc_problem(
    planner_input: PlannerInput,
    snapshot: DecisionSnapshot,
    *,
    route_bearing_rad: float,
    planned_speed_mps: float,
    config: MidMpcAssemblyConfig,
) -> AssembledMidMpcProblem:
    """Map one immutable decision snapshot without retaining business state."""
    track_by_key = {TrackKey(track.target_id, track.generation or 1): track for track in planner_input.tracks}
    missing = [key for key in snapshot.directive.required_targets if key not in track_by_key]
    if missing:
        raise LifecycleError(
            LifecycleFailure.CORE_CAPABILITY_MISMATCH,
            f"lifecycle target keys missing from PlannerInput: {missing}",
        )
    selected_keys = snapshot.directive.required_targets
    selected_tracks = tuple(track_by_key[key] for key in selected_keys)
    decision_by_key = {decision.key: decision for decision in snapshot.targets}
    selected_decisions = tuple(decision_by_key[key] for key in selected_keys)
    required_sides = {
        decision.passing_side for decision in selected_decisions if decision.passing_side is not PassingSide.NONE
    }
    if required_sides and required_sides != {snapshot.directive.passing_side} and not snapshot.directive.stop_required:
        raise LifecycleError(
            LifecycleFailure.CORE_CAPABILITY_MISMATCH,
            "aggregate direction cannot represent all required target corridors",
        )

    preferred_side = {
        PassingSide.NONE: 0,
        PassingSide.PORT: -1,
        PassingSide.STARBOARD: 1,
    }[snapshot.directive.passing_side]
    lateral_active = snapshot.directive.minimum_course_change_rad > 0.0
    committed_route_bearing = route_bearing_rad
    corridor_decisions = tuple(decision for decision in selected_decisions if not decision.route_recovery_allowed)
    if corridor_decisions:
        corridor = max(corridor_decisions, key=lambda decision: decision.required_course_change_rad)
        if corridor.baseline_course_rad is None:
            raise ValueError(f"committed target {corridor.key} has no baseline course")
        committed_route_bearing = corridor.baseline_course_rad + preferred_side * corridor.required_course_change_rad
    elif selected_decisions:
        recovery_delta = _wrap(route_bearing_rad - float(planner_input.ownship_state[2]))
        recovery_step = config.rot_max_rad_s * config.decision_period_s
        committed_route_bearing = float(planner_input.ownship_state[2]) + float(
            np.clip(recovery_delta, -recovery_step, recovery_step)
        )

    ownship = planner_input.ownship_state
    effective_cpa_hard_m = _effective_node_clearance(planner_input, selected_tracks, config)
    approaching_tcpa = [
        decision.geometry.signed_tcpa_s for decision in selected_decisions if decision.geometry.signed_tcpa_s > 0.0
    ]
    cpa_hard_from_k = config.horizon_steps
    if approaching_tcpa:
        cpa_hard_from_k = max(
            0,
            min(
                config.horizon_steps,
                math.floor(min(approaching_tcpa) / config.horizon_dt_s) - 2,
            ),
        )
    minimum_change = snapshot.directive.minimum_course_change_rad if lateral_active else 0.0
    reachable_per_step = config.rot_max_rad_s * config.horizon_dt_s
    min_alt_hard_from_k = max(0, math.ceil(minimum_change / reachable_per_step) - 1) if lateral_active else 0
    row_schedule = MidMpcRowSchedule(
        cpa_hard_from_k=cpa_hard_from_k,
        direction_hard_from_k=0,
        min_alt_hard_from_k=min_alt_hard_from_k,
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
        planned_speed_mps=0.0 if snapshot.directive.stop_required else planned_speed_mps,
        heading_bounds_rad=(
            float(ownship[2]) - config.heading_window_rad,
            float(ownship[2]) + config.heading_window_rad,
        ),
        speed_bounds_mps=snapshot.directive.speed_bounds_mps,
        cpa_safe_m=max(config.cpa_safe_m, effective_cpa_hard_m),
        cpa_hard_m=effective_cpa_hard_m,
        rot_max_rad_s=config.rot_max_rad_s,
        decel_max_mps2=config.decel_max_mps2,
        lateral_active=lateral_active,
        preferred_side=preferred_side,
        starboard_asymmetry_active=starboard_asymmetry,
        min_alteration_rad=minimum_change,
        route_frame=MidMpcRouteFrame(
            origin_m=(0.0, 0.0),
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
    return AssembledMidMpcProblem(
        problem=problem,
        selected_target_keys=selected_keys,
        selected_tracks=selected_tracks,
        effective_cpa_hard_m=effective_cpa_hard_m,
    )


def _effective_node_clearance(
    planner_input: PlannerInput,
    tracks: tuple[TrackedObstacle, ...],
    config: MidMpcAssemblyConfig,
) -> float:
    if not tracks:
        return config.cpa_hard_m
    own_radius = 0.5 * math.hypot(planner_input.ownship_length_m, planner_input.ownship_width_m)
    own_step_allowance = config.speed_bounds_mps[1] * config.horizon_dt_s
    target_allowances = []
    for track in tracks:
        footprint = 0.5 * math.hypot(track.length_m, track.width_m)
        covariance_allowance = math.sqrt(max(0.0, float(np.max(np.linalg.eigvalsh(track.covariance[:2, :2]))))) * math.sqrt(
            9.210340371976184
        )
        target_allowances.append(footprint + covariance_allowance)
    return config.cpa_hard_m + own_radius + max(target_allowances) + own_step_allowance


def _wrap(angle: float) -> float:
    return math.atan2(math.sin(angle), math.cos(angle))
