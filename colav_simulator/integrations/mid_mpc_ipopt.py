"""Colav-native facade for the parity-complete Mid-MPC IPOPT core."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import numpy as np

from colav_simulator.core.colav.custom_mpc_adapter import (
    AlgorithmDescriptor,
    CustomMPCAdapter,
    ExecutionProfile,
    FactoryContext,
    MPCSolution,
    PlannerInput,
    TrackedObstacle,
)
from colav_simulator.core.colav.diagnostics import PlanStatus
from colav_simulator.core.colav.mid_mpc import (
    MidMpcConfig,
    MidMpcIpoptSolver,
    MidMpcOwnShip,
    MidMpcProblem,
    MidMpcRouteFrame,
    MidMpcRowSchedule,
    MidMpcStatus,
    MidMpcTarget,
)
from colav_simulator.core.guidances import LOSGuidance
from colav_simulator.evaluation.encounter import classify_geometry, velocity_ne

__version__ = "1.0.0"


@dataclass(frozen=True)
class _FacadeConfig:
    horizon_steps: int
    horizon_dt_s: float
    hold_selection_horizon_s: float
    heading_window_rad: float
    speed_bounds_mps: tuple[float, float]
    cpa_safe_m: float
    cpa_hard_m: float
    overtaking_clear_distance_m: float
    rot_max_rad_s: float
    decel_max_mps2: float
    min_alteration_rad: float
    route_lateral_scale_m: float
    route_weight: float


@dataclass(frozen=True)
class _OptimizerPolicy:
    intent: str
    preferred_side: int
    starboard_asymmetry_active: bool


@dataclass(frozen=True)
class _TargetDecision:
    track: TrackedObstacle
    encounter: str
    optimizer_policy: _OptimizerPolicy
    dcpa_m: float
    tcpa_s: float
    signed_tcpa_s: float
    relative_bearing_deg: float
    newly_committed: bool


class _MidMpcFacade:
    def __init__(self, config: _FacadeConfig) -> None:
        self._config = config
        self._los = LOSGuidance()
        self._solver = MidMpcIpoptSolver(MidMpcConfig(horizon_steps=config.horizon_steps, dt_s=config.horizon_dt_s))
        self._hard_direction_solver = MidMpcIpoptSolver(
            MidMpcConfig(
                horizon_steps=config.horizon_steps,
                dt_s=config.horizon_dt_s,
                dir_slack_enabled=False,
            )
        )
        self._last_guidance_time_s: float | None = None
        self._committed_policies: dict[int, _OptimizerPolicy] = {}
        self._commitment_courses_rad: dict[int, float] = {}
        self._released_target_ids: set[int] = set()

    def reset(self) -> None:
        self._los.reset()
        self._last_guidance_time_s = None
        self._committed_policies.clear()
        self._commitment_courses_rad.clear()
        self._released_target_ids.clear()

    def solve(self, planner_input: PlannerInput) -> MPCSolution:
        ownship = planner_input.ownship_state
        guidance_dt_s = (
            planner_input.dt_sim_s
            if self._last_guidance_time_s is None
            else planner_input.sim_time_s - self._last_guidance_time_s
        )
        reference = self._los.compute_references(
            planner_input.waypoints_enu_m,
            planner_input.speed_plan_mps,
            None,
            ownship,
            guidance_dt_s,
        )
        self._last_guidance_time_s = planner_input.sim_time_s
        route_bearing = _unwrap_near(float(reference[2, 0]), float(ownship[2]))
        target_decisions = self._target_decisions(planner_input)
        optimization_decisions = self._optimization_decisions(target_decisions)
        optimizer_policy = _aggregate_policy(target_decisions)
        course_commitment_active = optimizer_policy.intent == "GIVE_WAY"
        if course_commitment_active:
            committed_course = next(
                self._commitment_courses_rad[decision.track.target_id]
                for decision in target_decisions
                if decision.optimizer_policy.intent == "GIVE_WAY"
                and decision.track.target_id in self._commitment_courses_rad
            )
            route_bearing = _unwrap_near(
                committed_course + optimizer_policy.preferred_side * self._config.min_alteration_rad,
                float(ownship[2]),
            )
        lateral_active = any(decision.newly_committed for decision in optimization_decisions)
        minimum_alteration_active = lateral_active
        row_schedule = self._row_schedule(optimization_decisions, lateral_active)
        effective_cpa_hard_m = self._effective_cpa_hard_m(optimization_decisions, planner_input)
        problem = MidMpcProblem(
            own_ship=MidMpcOwnShip(psi_rad=float(ownship[2]), u_mps=float(ownship[3])),
            route_bearing_rad=route_bearing,
            planned_speed_mps=float(reference[3, 0]),
            heading_bounds_rad=(
                float(ownship[2]) - self._config.heading_window_rad,
                float(ownship[2]) + self._config.heading_window_rad,
            ),
            speed_bounds_mps=self._config.speed_bounds_mps,
            cpa_safe_m=max(self._config.cpa_safe_m, effective_cpa_hard_m),
            cpa_hard_m=effective_cpa_hard_m,
            rot_max_rad_s=self._config.rot_max_rad_s,
            decel_max_mps2=self._config.decel_max_mps2,
            lateral_active=lateral_active,
            preferred_side=optimizer_policy.preferred_side,
            starboard_asymmetry_active=optimizer_policy.starboard_asymmetry_active,
            min_alteration_rad=self._config.min_alteration_rad if minimum_alteration_active else 0.0,
            route_frame=MidMpcRouteFrame(
                origin_m=(0.0, 0.0),
                normal=(-math.sin(route_bearing), math.cos(route_bearing)),
                bearing_rad=route_bearing,
                lateral_scale_m=self._config.route_lateral_scale_m,
                weight=self._config.route_weight,
            ),
            row_schedule=row_schedule,
            audit_row_count=sum(decision.encounter != "clear" for decision in optimization_decisions),
            targets=tuple(
                MidMpcTarget(
                    x_m=float(decision.track.state_enu[0] - ownship[0]),
                    y_m=float(decision.track.state_enu[1] - ownship[1]),
                    cog_rad=float(math.atan2(decision.track.state_enu[3], decision.track.state_enu[2])),
                    sog_mps=float(np.linalg.norm(decision.track.state_enu[2:4])),
                )
                for decision in optimization_decisions
            ),
        )
        solver = self._hard_direction_solver if lateral_active else self._solver
        result = solver.solve(problem)
        predicted, controls = _native_trajectories(result.trajectory, ownship, self._config.horizon_dt_s)
        status, feasible = _plan_status(result.status, result.max_constraint_violation)
        continuous_cpa = result.continuous_cpa_min_m if math.isfinite(result.continuous_cpa_min_m) else None
        objective_components = asdict(result.objective_components)
        constraints = {
            "row_layout": result.row_layout.to_dict(),
            "active_row_indices": list(result.active_row_indices),
            "tight_row_indices": list(result.tight_row_indices),
            "max_constraint_violation": result.max_constraint_violation,
            "cpa_slack": result.cpa_slack,
            "direction_slack": max(0.0, result.raw_dir_slack),
            "continuous_cpa_min_m": continuous_cpa,
            "continuous_cpa_violated": result.continuous_cpa_violated,
            "row_schedule": asdict(row_schedule),
            "configured_hull_clearance_m": self._config.cpa_hard_m,
            "effective_node_cpa_hard_m": effective_cpa_hard_m,
        }
        details = {
            "formulation": "mass-l3-mid-mpc-ipopt-frozen",
            "solver_backend": "ipopt",
            "ipopt_return_status": result.ipopt_return_status,
            "normalized_solver_status": result.status.value,
            "solver_elapsed_ms": result.elapsed_ms,
            "objective_components": objective_components,
            "warm_start_used": False,
            "target_selection": "future_cpa_then_range",
            "decision_intent": optimizer_policy.intent,
            "preferred_side": _side_name(optimizer_policy.preferred_side),
            "starboard_asymmetry_active": optimizer_policy.starboard_asymmetry_active,
            "minimum_alteration_active": minimum_alteration_active,
            "overtaking_course_commitment_active": (
                course_commitment_active and not optimizer_policy.starboard_asymmetry_active
            ),
            "route_reference_mode": "give_way_commitment" if course_commitment_active else "los",
            "direction_constraint_mode": (
                "hard" if lateral_active else "route_reference" if course_commitment_active else "disabled"
            ),
            "selected_target_ids": [decision.track.target_id for decision in optimization_decisions],
            "los_guidance_dt_s": guidance_dt_s,
        }
        return MPCSolution(
            control_reference=controls[:, :1],
            predicted_trajectory=predicted,
            control_trajectory=controls,
            status=status,
            horizon_dt_s=self._config.horizon_dt_s,
            objective=result.objective_total,
            iterations=result.ipopt_iterations,
            feasible=feasible,
            constraints=constraints,
            target_predictions=tuple(self._target_prediction(decision, planner_input) for decision in target_decisions),
            algorithm_details=details,
        )

    def _target_decisions(self, planner_input: PlannerInput) -> tuple[_TargetDecision, ...]:
        ownship = planner_input.ownship_state
        own_speed = float(np.hypot(ownship[3], ownship[4]))
        own_course = float(ownship[2] + math.atan2(ownship[4], ownship[3]))
        own_velocity = velocity_ne(own_speed, own_course)
        decisions = []
        seen_target_ids = set()
        for track in planner_input.tracks:
            seen_target_ids.add(track.target_id)
            encounter, dcpa_m, tcpa_s, signed_tcpa_s, relative_bearing_deg = classify_geometry(
                ownship[:2],
                own_velocity,
                track.state_enu[:2],
                track.state_enu[2:4],
                planner_input.ownship_length_m,
                track.length_m,
            )
            classified_policy = _policy_for_encounter(encounter, relative_bearing_deg)
            committed_policy = self._committed_policies.get(track.target_id)
            overtaking_past_and_clear = self._overtaking_past_and_clear(ownship, track)
            release_commitment = committed_policy is not None and (
                overtaking_past_and_clear if not committed_policy.starboard_asymmetry_active else signed_tcpa_s <= 0.0
            )
            if release_commitment:
                self._committed_policies.pop(track.target_id, None)
                self._commitment_courses_rad.pop(track.target_id, None)
                self._released_target_ids.add(track.target_id)
                committed_policy = None
            released = track.target_id in self._released_target_ids
            newly_committed = classified_policy.intent == "GIVE_WAY" and committed_policy is None and not released
            if classified_policy.intent == "GIVE_WAY" and not released:
                if committed_policy is None:
                    self._commitment_courses_rad[track.target_id] = own_course
                committed_policy = committed_policy or classified_policy
                self._committed_policies[track.target_id] = committed_policy
            effective_policy = committed_policy or classified_policy
            if released:
                effective_policy = _OptimizerPolicy("HOLD", 0, False)
            decisions.append(
                _TargetDecision(
                    track=track,
                    encounter=encounter,
                    optimizer_policy=effective_policy,
                    dcpa_m=dcpa_m,
                    tcpa_s=tcpa_s,
                    signed_tcpa_s=signed_tcpa_s,
                    relative_bearing_deg=relative_bearing_deg,
                    newly_committed=newly_committed,
                )
            )
        self._committed_policies = {
            target_id: policy for target_id, policy in self._committed_policies.items() if target_id in seen_target_ids
        }
        self._commitment_courses_rad = {
            target_id: course
            for target_id, course in self._commitment_courses_rad.items()
            if target_id in self._committed_policies
        }
        self._released_target_ids.intersection_update(seen_target_ids)
        decisions.sort(
            key=lambda decision: (
                decision.signed_tcpa_s <= 0.0,
                decision.tcpa_s if decision.signed_tcpa_s > 0.0 else math.inf,
                decision.dcpa_m,
                float(np.linalg.norm(decision.track.state_enu[:2] - ownship[:2])),
                decision.track.target_id,
            )
        )
        return tuple(decisions[:16])

    def _overtaking_past_and_clear(self, ownship: np.ndarray, track: TrackedObstacle) -> bool:
        relative_position = ownship[:2] - track.state_enu[:2]
        distance_m = float(np.linalg.norm(relative_position))
        target_velocity = track.state_enu[2:4]
        target_speed_mps = float(np.linalg.norm(target_velocity))
        if target_speed_mps <= 0.25:
            return False
        along_track_m = float(relative_position @ target_velocity / target_speed_mps)
        return (
            along_track_m >= self._config.overtaking_clear_distance_m
            and distance_m >= self._config.overtaking_clear_distance_m
        )

    def _optimization_decisions(
        self,
        decisions: tuple[_TargetDecision, ...],
    ) -> tuple[_TargetDecision, ...]:
        return tuple(
            decision
            for decision in decisions
            if decision.optimizer_policy.intent == "GIVE_WAY"
            or (0.0 < decision.signed_tcpa_s <= self._config.hold_selection_horizon_s)
        )

    def _effective_cpa_hard_m(
        self,
        decisions: tuple[_TargetDecision, ...],
        planner_input: PlannerInput,
    ) -> float:
        if not decisions:
            return self._config.cpa_hard_m
        own_radius = 0.5 * math.hypot(planner_input.ownship_length_m, planner_input.ownship_width_m)
        target_allowances = [0.5 * math.hypot(decision.track.length_m, decision.track.width_m) for decision in decisions]
        own_step_allowance = self._config.speed_bounds_mps[1] * self._config.horizon_dt_s
        return self._config.cpa_hard_m + own_radius + max(target_allowances) + own_step_allowance

    def _row_schedule(
        self,
        decisions: tuple[_TargetDecision, ...],
        lateral_active: bool,
    ) -> MidMpcRowSchedule:
        approaching = [decision.tcpa_s for decision in decisions if decision.signed_tcpa_s > 0.0]
        cpa_hard_from_k = self._config.horizon_steps
        if approaching:
            cpa_hard_from_k = max(
                0,
                min(
                    self._config.horizon_steps,
                    math.floor(min(approaching) / self._config.horizon_dt_s) - 2,
                ),
            )
        min_alt_hard_from_k = 0
        if lateral_active:
            reachable_per_step = self._config.rot_max_rad_s * self._config.horizon_dt_s
            min_alt_hard_from_k = max(
                0,
                math.ceil(self._config.min_alteration_rad / reachable_per_step) - 1,
            )
        return MidMpcRowSchedule(
            cpa_hard_from_k=cpa_hard_from_k,
            direction_hard_from_k=0,
            min_alt_hard_from_k=min_alt_hard_from_k,
            terminal_rows_enabled=False,
        )

    def _target_prediction(
        self,
        decision: _TargetDecision,
        planner_input: PlannerInput,
    ) -> dict[str, object]:
        times = np.arange(self._config.horizon_steps, dtype=float) * self._config.horizon_dt_s
        state = decision.track.state_enu
        return {
            "target_id": decision.track.target_id,
            "encounter": decision.encounter,
            "optimizer_intent": decision.optimizer_policy.intent,
            "policy_committed": decision.track.target_id in self._committed_policies,
            "preferred_side": _side_name(decision.optimizer_policy.preferred_side),
            "dcpa_m": decision.dcpa_m,
            "tcpa_s": decision.tcpa_s,
            "signed_tcpa_s": decision.signed_tcpa_s,
            "relative_bearing_deg": decision.relative_bearing_deg,
            "north_m": (state[0] + state[2] * times).tolist(),
            "east_m": (state[1] + state[3] * times).tolist(),
            "velocity_ne_mps": state[2:4].tolist(),
            "prediction_model": "constant_velocity",
            "degraded": decision.track.degraded,
            "ownship_reference_time_s": planner_input.sim_time_s,
        }


def create(  # noqa: PLR0913
    *,
    context: FactoryContext,
    horizon_steps: int = 80,
    horizon_dt_s: float = 15.0,
    hold_selection_horizon_s: float = 90.0,
    solve_period_s: float = 5.0,
    deadline_s: float = 20.0,
    heading_window_deg: float = 45.0,
    speed_min_mps: float = 0.25,
    speed_max_mps: float = 8.0,
    cpa_safe_m: float = 150.0,
    cpa_hard_m: float = 50.0,
    overtaking_clear_distance_m: float = 190.0,
    rot_max_deg_s: float = 3.0,
    decel_max_mps2: float = 0.3,
    min_alteration_deg: float = 5.0,
    route_lateral_scale_m: float = 1000.0,
    route_weight: float = 1.0,
) -> CustomMPCAdapter:
    """Build Mid-MPC under the strict native adapter contract."""
    config = _FacadeConfig(
        horizon_steps=horizon_steps,
        horizon_dt_s=horizon_dt_s,
        hold_selection_horizon_s=hold_selection_horizon_s,
        heading_window_rad=float(np.deg2rad(heading_window_deg)),
        speed_bounds_mps=(speed_min_mps, speed_max_mps),
        cpa_safe_m=cpa_safe_m,
        cpa_hard_m=cpa_hard_m,
        overtaking_clear_distance_m=overtaking_clear_distance_m,
        rot_max_rad_s=float(np.deg2rad(rot_max_deg_s)),
        decel_max_mps2=decel_max_mps2,
        min_alteration_rad=float(np.deg2rad(min_alteration_deg)),
        route_lateral_scale_m=route_lateral_scale_m,
        route_weight=route_weight,
    )
    facade = _MidMpcFacade(config)
    descriptor = AlgorithmDescriptor(
        algorithm_id=context.requested_algorithm,
        version=__version__,
        control_form="course_speed_reference",
        state_layout=("x", "y", "psi", "u", "v", "r", "x_ddot", "y_ddot", "psi_dot"),
        predictor_model="heading_speed_point_mass_constant_velocity_targets",
        horizon_dt=config.horizon_dt_s,
        horizon_steps=config.horizon_steps,
        objective_terms=(
            "colreg_barrier",
            "heading_tracking",
            "speed_tracking",
            "route_tracking",
            "starboard_asymmetry",
            "terminal_lateral",
            "cpa_slack",
            "direction_slack",
        ),
        constraint_terms=(
            "yaw_rate",
            "deceleration",
            "cpa_distance",
            "preferred_side",
            "minimum_alteration",
        ),
        solver="casadi-3.7.2-ipopt",
        seed_policy="deterministic_cold_start",
        execution_profile=ExecutionProfile(
            solve_period_s=solve_period_s,
            deadline_s=deadline_s,
            requires_enc=False,
        ),
    )
    return CustomMPCAdapter(
        descriptor=descriptor,
        solve=facade.solve,
        reset=facade.reset,
        context=context,
    )


def _unwrap_near(angle: float, reference: float) -> float:
    return reference + math.atan2(math.sin(angle - reference), math.cos(angle - reference))


def _policy_for_encounter(encounter: str, _relative_bearing_deg: float) -> _OptimizerPolicy:
    if encounter in {"head_on", "crossing_give_way"}:
        return _OptimizerPolicy("GIVE_WAY", 1, True)
    if encounter == "overtaking":
        return _OptimizerPolicy("GIVE_WAY", 1, False)
    return _OptimizerPolicy("HOLD", 0, False)


def _aggregate_policy(decisions: tuple[_TargetDecision, ...]) -> _OptimizerPolicy:
    give_way = [decision.optimizer_policy for decision in decisions if decision.optimizer_policy.intent == "GIVE_WAY"]
    if not give_way:
        return _OptimizerPolicy("HOLD", 0, False)
    mandatory_starboard = any(policy.starboard_asymmetry_active for policy in give_way)
    preferred_side = 1 if mandatory_starboard else give_way[0].preferred_side
    return _OptimizerPolicy("GIVE_WAY", preferred_side, mandatory_starboard)


def _side_name(preferred_side: int) -> str:
    return {1: "starboard", -1: "port", 0: "none"}[preferred_side]


def _plan_status(status: MidMpcStatus, max_violation: float) -> tuple[PlanStatus, bool]:
    if status is MidMpcStatus.CONVERGED:
        return PlanStatus.SUCCESS, True
    if status is MidMpcStatus.TIMEOUT and max_violation <= 1.0e-3:
        return PlanStatus.TIMEOUT_FEASIBLE, True
    if status is MidMpcStatus.INFEASIBLE:
        return PlanStatus.INFEASIBLE, False
    return PlanStatus.NUMERICAL_FAILURE, False


def _native_trajectories(
    points: tuple,
    ownship: np.ndarray,
    dt_s: float,
) -> tuple[np.ndarray, np.ndarray]:
    count = len(points)
    predicted = np.zeros((9, count), dtype=float)
    controls = np.zeros((9, count), dtype=float)
    north0, east0 = map(float, ownship[:2])
    headings = np.array([point.psi_rad for point in points], dtype=float)
    speeds = np.array([point.u_mps for point in points], dtype=float)
    north = north0 + np.array([point.x_m for point in points], dtype=float)
    east = east0 + np.array([point.y_m for point in points], dtype=float)
    yaw_rate = np.zeros(count, dtype=float)
    acceleration_ne = np.zeros((2, count), dtype=float)
    yaw_rate[0] = (headings[0] - float(ownship[2])) / dt_s
    velocity_ne_mps = np.vstack((speeds * np.cos(headings), speeds * np.sin(headings)))
    own_velocity_ne_mps = np.array(
        [
            ownship[3] * math.cos(ownship[2]) - ownship[4] * math.sin(ownship[2]),
            ownship[3] * math.sin(ownship[2]) + ownship[4] * math.cos(ownship[2]),
        ]
    )
    acceleration_ne[:, 0] = 2.0 * (velocity_ne_mps[:, 0] - own_velocity_ne_mps) / dt_s
    if count > 1:
        yaw_rate[1:] = np.diff(headings) / dt_s
        acceleration_ne[:, 1:] = np.diff(velocity_ne_mps, axis=1) / dt_s
    controls[0] = north
    controls[1] = east
    controls[2] = headings
    controls[3] = speeds
    controls[5] = yaw_rate
    controls[6:8] = acceleration_ne
    controls[8] = yaw_rate
    predicted[:] = controls
    predicted[:6, 0] = ownship
    predicted[8, 0] = ownship[5]
    return predicted, controls
