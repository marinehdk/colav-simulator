"""Python port of Potočnik's simplified fan-trajectory MPC.

The implementation follows Equations (7)-(17) and the reference MATLAB
implementation at ppotoc/MPC-Autonomous-Ship-Navigation, commit
3683e92f9949cf884540d40a7ce096c3785273b3.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import numpy as np

from colav_simulator.core.colav.custom_mpc_adapter import (
    AlgorithmDescriptor,
    CustomMPCAdapter,
    ExecutionProfile,
    FactoryContext,
    MPCSolution,
    PlannerInput,
)
from colav_simulator.core.colav.diagnostics import ColavExecutionError, FailureSource, PlanStatus

UPSTREAM_COMMIT: Final = "3683e92f9949cf884540d40a7ce096c3785273b3"
PAPER_COLREG_ZONE_M: Final = 3.0 * 1852.0
__version__ = f"paper-2025-port.2+{UPSTREAM_COMMIT[:12]}"


@dataclass(frozen=True)
class PotocnikMPCParams:
    """Paper and execution parameters for the simplified MPC."""

    prediction_steps: int = 20
    candidate_count: int = 45
    horizon_dt_s: float = 5.0
    solve_period_s: float = 5.0
    deadline_s: float = 0.1
    max_heading_increment_deg: float = 10.0
    heading_increment_decay: float = 0.95
    collision_distance_m: float = 0.5 * 1852.0
    colreg_zone_distance_m: float = PAPER_COLREG_ZONE_M
    continuity_weight: float = 4.0
    clearance_weight: float = 2.0
    reversal_weight: float = 2.0
    max_command_change_deg: float = 5.0

    def __post_init__(self) -> None:
        """Reject configurations that change the algorithm into an invalid fan."""
        finite_positive = (
            self.horizon_dt_s,
            self.solve_period_s,
            self.deadline_s,
            self.max_heading_increment_deg,
            self.collision_distance_m,
            self.colreg_zone_distance_m,
            self.continuity_weight,
            self.clearance_weight,
            self.reversal_weight,
            self.max_command_change_deg,
        )
        if not np.isfinite(finite_positive).all() or min(finite_positive) <= 0.0:
            raise ValueError("time, heading and collision parameters must be finite and positive")
        if self.prediction_steps < 1:
            raise ValueError("prediction_steps must be positive")
        if self.candidate_count < 3 or self.candidate_count % 2 == 0:
            raise ValueError("candidate_count must be an odd integer of at least three")
        if not np.isfinite(self.heading_increment_decay) or not 0.0 < self.heading_increment_decay <= 1.0:
            raise ValueError("heading_increment_decay must be in (0, 1]")


@dataclass(frozen=True)
class _CandidateSelection:
    selected_index: int
    mode: str
    score: float
    route_score: float
    continuity_score: float
    clearance_score: float
    reversal_penalty: float
    rate_limit_relaxed: bool


class PotocnikSimplifiedMPC:
    """Exhaustive fan generation, feasibility filtering and route selection."""

    def __init__(self, params: PotocnikMPCParams) -> None:
        self.params = params
        self.solve_count = 0
        self._previous_command_course: float | None = None
        self._previous_command_change_sign = 0
        self._turn_reversal_count = 0
        self._avoidance_turn_sign = 0
        self._nominal_feasible_solves = 0
        self._heading_increments = np.linspace(
            -np.deg2rad(params.max_heading_increment_deg),
            np.deg2rad(params.max_heading_increment_deg),
            params.candidate_count,
        )

    def reset(self) -> None:
        self.solve_count = 0
        self._previous_command_course = None
        self._previous_command_change_sign = 0
        self._turn_reversal_count = 0
        self._avoidance_turn_sign = 0
        self._nominal_feasible_solves = 0

    def solve(self, planner_input: PlannerInput) -> MPCSolution:
        self.solve_count += 1
        ownship = planner_input.ownship_state
        speed_mps = float(np.hypot(ownship[3], ownship[4]))
        if speed_mps <= 1e-6:
            speed_mps = float(max(planner_input.speed_plan_mps[0], 1e-3))
        goal_ne = _next_waypoint(ownship[:2], planner_input.waypoints_enu_m)
        candidates = self.generate_candidate_trajectories(ownship, speed_mps)
        target_predictions = self._target_predictions(planner_input)
        minimum_clearance = self._minimum_clearance(candidates, target_predictions)
        feasible = minimum_clearance >= self.params.collision_distance_m
        feasible_indices = np.flatnonzero(feasible)
        if feasible_indices.size == 0:
            raise ColavExecutionError(
                PlanStatus.INFEASIBLE,
                "Potočnik simplified MPC found no collision-free fan trajectory",
                source=FailureSource.ALGORITHM,
                details={
                    "candidate_count": self.params.candidate_count,
                    "collision_distance_m": self.params.collision_distance_m,
                },
            )

        nominal_index = self.params.candidate_count // 2
        nominal_feasible = bool(feasible[nominal_index])
        self._update_avoidance_state(nominal_feasible)
        target_course = float(np.arctan2(goal_ne[1] - ownship[1], goal_ne[0] - ownship[0]))
        selection = self._select_candidate(
            candidates=candidates,
            feasible_indices=feasible_indices,
            minimum_clearance=minimum_clearance,
            goal_ne=goal_ne,
            ownship_course=float(ownship[2]),
            target_course=target_course,
            speed_mps=speed_mps,
            nominal_feasible=nominal_feasible,
        )
        selected_index = selection.selected_index
        selected = candidates[selected_index]
        command = selected[:, 0].copy()
        command[2] = selected[2, 1]
        command[3] = speed_mps
        command[4:] = 0.0
        selected_increment = float(self._heading_increments[selected_index])
        self._record_command(float(command[2]), selected_increment, nominal_feasible)

        selected_clearance = float(minimum_clearance[selected_index])
        constraints = {
            "dynamic_collision": {
                "required_clearance_m": self.params.collision_distance_m,
                "minimum_predicted_clearance_m": selected_clearance if np.isfinite(selected_clearance) else None,
            },
            "heading_increment": {
                "limit_rad": float(np.deg2rad(self.params.max_heading_increment_deg)),
                "selected_rad": selected_increment,
                "maximum_command_change_rad": float(np.deg2rad(self.params.max_command_change_deg)),
                "rate_limit_relaxed": selection.rate_limit_relaxed,
            },
            "planning_zone": {
                "distance_m": self.params.colreg_zone_distance_m,
                "semantics": "paper_colreg_zone_reference",
            },
        }
        target_bearing_offset = float(_wrap_angle(target_course - float(ownship[2])))
        prediction_distance = float(np.sum(np.linalg.norm(np.diff(selected[:2], axis=1), axis=0)))
        details = {
            "paper": "Potočnik 2025 JMSE 13(7):1246",
            "upstream_commit": UPSTREAM_COMMIT,
            "formulation": "simplified_mpc_equations_13_17",
            "candidate_count": self.params.candidate_count,
            "candidate_heading_increments_rad": self._heading_increments.tolist(),
            "candidate_feasible": feasible.tolist(),
            "candidate_minimum_clearance_m": [
                float(value) if np.isfinite(value) else None for value in minimum_clearance
            ],
            "feasible_candidate_count": int(feasible_indices.size),
            "selected_candidate_index": selected_index,
            "selected_heading_increment_rad": selected_increment,
            "selection_mode": selection.mode,
            "selection_score": selection.score,
            "selection_score_unit": "normalized",
            "route_score": selection.route_score,
            "continuity_score": selection.continuity_score,
            "clearance_score": selection.clearance_score,
            "reversal_penalty": selection.reversal_penalty,
            "target_course_rad": target_course,
            "target_bearing_offset_rad": target_bearing_offset,
            "goal_ne_m": goal_ne.tolist(),
            "prediction_steps": self.params.prediction_steps,
            "prediction_step_s": self.params.horizon_dt_s,
            "prediction_distance_m": prediction_distance,
            "decision_sector_limit_rad": float(np.pi / 2.0),
            "heading_increment_decay": self.params.heading_increment_decay,
            "speed_scale": 1.0,
            "solve_period_s": self.params.solve_period_s,
            "solve_count": self.solve_count,
            "nominal_candidate_feasible": nominal_feasible,
            "avoidance_turn_sign": self._avoidance_turn_sign,
            "turn_reversal_count": self._turn_reversal_count,
        }
        return MPCSolution(
            control_reference=command.reshape(9, 1),
            predicted_trajectory=selected,
            horizon_dt_s=self.params.horizon_dt_s,
            objective=selection.score,
            iterations=self.params.candidate_count,
            feasible=True,
            constraints=constraints,
            target_predictions=tuple(target_predictions),
            algorithm_details=details,
        )

    def _update_avoidance_state(self, nominal_feasible: bool) -> None:
        if not nominal_feasible:
            self._nominal_feasible_solves = 0
            return
        self._nominal_feasible_solves += 1
        if self._nominal_feasible_solves >= 2:
            self._avoidance_turn_sign = 0

    def _select_candidate(  # noqa: PLR0913
        self,
        *,
        candidates: np.ndarray,
        feasible_indices: np.ndarray,
        minimum_clearance: np.ndarray,
        goal_ne: np.ndarray,
        ownship_course: float,
        target_course: float,
        speed_mps: float,
        nominal_feasible: bool,
    ) -> _CandidateSelection:
        selection_indices = feasible_indices
        previous_course = self._previous_command_course
        rate_limit_relaxed = False
        if previous_course is not None:
            course_changes = np.abs(
                _wrap_angle(candidates[selection_indices, 2, 1] - previous_course)
            )
            executable = selection_indices[
                course_changes <= np.deg2rad(self.params.max_command_change_deg) + 1e-12
            ]
            if executable.size:
                selection_indices = executable
            else:
                rate_limit_relaxed = True

        approaching = abs(_wrap_angle(ownship_course - target_course)) <= np.pi / 2.0
        if approaching:
            route_score = np.abs(_wrap_angle(candidates[selection_indices, 2, 1] - target_course))
            mode = "initial_heading"
        else:
            terminal_delta = candidates[selection_indices, :2, -1] - goal_ne[:, None].T
            route_score = np.linalg.norm(terminal_delta, axis=1)
            route_score /= max(speed_mps * self.params.horizon_dt_s * self.params.prediction_steps, 1.0)
            mode = "terminal_distance"

        continuity_score = np.zeros(selection_indices.size)
        if previous_course is not None:
            continuity_score = np.abs(
                _wrap_angle(candidates[selection_indices, 2, 1] - previous_course)
            )
        reversal_score = np.zeros(selection_indices.size)
        if not nominal_feasible and self._avoidance_turn_sign:
            candidate_signs = np.sign(self._heading_increments[selection_indices])
            reversal_score[candidate_signs == -self._avoidance_turn_sign] = 1.0
        selected_clearances = minimum_clearance[selection_indices]
        clearance_score = np.zeros(selection_indices.size)
        finite_clearance = np.isfinite(selected_clearances)
        clearance_score[finite_clearance] = np.minimum(
            1.0,
            self.params.collision_distance_m / selected_clearances[finite_clearance],
        )
        score = (
            route_score
            + self.params.continuity_weight * continuity_score
            + self.params.clearance_weight * clearance_score
            + self.params.reversal_weight * reversal_score
        )
        best = int(np.argmin(score))
        return _CandidateSelection(
            selected_index=int(selection_indices[best]),
            mode=mode,
            score=float(score[best]),
            route_score=float(route_score[best]),
            continuity_score=float(continuity_score[best]),
            clearance_score=float(clearance_score[best]),
            reversal_penalty=float(reversal_score[best]),
            rate_limit_relaxed=rate_limit_relaxed,
        )

    def _record_command(
        self,
        command_course: float,
        selected_increment: float,
        nominal_feasible: bool,
    ) -> None:
        selected_turn_sign = _signed_change(selected_increment)
        if not nominal_feasible and not self._avoidance_turn_sign and selected_turn_sign:
            self._avoidance_turn_sign = selected_turn_sign
        previous_course = self._previous_command_course
        command_change = (
            selected_increment
            if previous_course is None
            else float(_wrap_angle(command_course - previous_course))
        )
        command_change_sign = _signed_change(command_change)
        if (
            self._previous_command_change_sign
            and command_change_sign
            and command_change_sign != self._previous_command_change_sign
        ):
            self._turn_reversal_count += 1
        if command_change_sign:
            self._previous_command_change_sign = command_change_sign
        self._previous_command_course = command_course

    def generate_candidate_trajectories(self, ownship: np.ndarray, speed_mps: float) -> np.ndarray:
        """Generate the M fan trajectories from MATLAB lines 480-508."""
        horizon = self.params.prediction_steps + 1
        candidates = np.zeros((self.params.candidate_count, 9, horizon), dtype=float)
        candidates[:, :6, 0] = ownship
        headings = np.full(self.params.candidate_count, float(ownship[2]))
        north = np.full(self.params.candidate_count, float(ownship[0]))
        east = np.full(self.params.candidate_count, float(ownship[1]))
        increments = self._heading_increments.copy()
        for step in range(1, horizon):
            headings = _wrap_angle(headings + increments)
            north = north + speed_mps * np.cos(headings) * self.params.horizon_dt_s
            east = east + speed_mps * np.sin(headings) * self.params.horizon_dt_s
            candidates[:, 0, step] = north
            candidates[:, 1, step] = east
            candidates[:, 2, step] = headings
            candidates[:, 3, step] = speed_mps
            candidates[:, 5, step] = increments / self.params.horizon_dt_s
            candidates[:, 8, step] = increments / self.params.horizon_dt_s
            increments *= self.params.heading_increment_decay
        return candidates

    def _target_predictions(self, planner_input: PlannerInput) -> list[dict]:
        times = np.arange(self.params.prediction_steps + 1, dtype=float) * self.params.horizon_dt_s
        output = []
        for track in planner_input.tracks:
            north = track.state_enu[0] + track.state_enu[2] * times
            east = track.state_enu[1] + track.state_enu[3] * times
            output.append(
                {
                    "target_id": track.target_id,
                    "north_m": north.tolist(),
                    "east_m": east.tolist(),
                    "velocity_ne_mps": track.state_enu[2:4].tolist(),
                    "prediction_model": "constant_velocity",
                }
            )
        return output

    def _minimum_clearance(self, candidates: np.ndarray, targets: list[dict]) -> np.ndarray:
        minimum = np.full(self.params.candidate_count, np.inf)
        for target in targets:
            target_ne = np.vstack((target["north_m"], target["east_m"]))
            delta = candidates[:, :2, 1:] - target_ne[None, :, 1:]
            minimum = np.minimum(minimum, np.min(np.linalg.norm(delta, axis=1), axis=1))
        return minimum


def create(
    *,
    context: FactoryContext,
    prediction_steps: int = 20,
    candidate_count: int = 45,
    horizon_dt_s: float = 5.0,
    solve_period_s: float = 5.0,
    deadline_s: float = 0.1,
    max_heading_increment_deg: float = 10.0,
    heading_increment_decay: float = 0.95,
    collision_distance_m: float = 0.5 * 1852.0,
    colreg_zone_distance_m: float = PAPER_COLREG_ZONE_M,
    continuity_weight: float = 4.0,
    clearance_weight: float = 2.0,
    reversal_weight: float = 2.0,
    max_command_change_deg: float = 5.0,
) -> CustomMPCAdapter:
    """Build the paper algorithm through the formal Phase 2 adapter."""
    params = PotocnikMPCParams(
        prediction_steps=prediction_steps,
        candidate_count=candidate_count,
        horizon_dt_s=horizon_dt_s,
        solve_period_s=solve_period_s,
        deadline_s=deadline_s,
        max_heading_increment_deg=max_heading_increment_deg,
        heading_increment_decay=heading_increment_decay,
        collision_distance_m=collision_distance_m,
        colreg_zone_distance_m=colreg_zone_distance_m,
        continuity_weight=continuity_weight,
        clearance_weight=clearance_weight,
        reversal_weight=reversal_weight,
        max_command_change_deg=max_command_change_deg,
    )
    solver = PotocnikSimplifiedMPC(params)
    descriptor = AlgorithmDescriptor(
        algorithm_id=context.requested_algorithm,
        version=__version__,
        control_form="course_speed_reference",
        state_layout=("x", "y", "psi", "u", "v", "r", "x_ddot", "y_ddot", "psi_dot"),
        predictor_model="discrete_point_mass_constant_speed_fan",
        horizon_dt=params.horizon_dt_s,
        horizon_steps=params.prediction_steps + 1,
        objective_terms=("waypoint_alignment", "command_continuity", "dynamic_clearance"),
        constraint_terms=("heading_increment_limit", "dynamic_collision_distance"),
        solver="exhaustive_discrete_fan_filter",
        seed_policy="deterministic_no_rng",
        execution_profile=ExecutionProfile(
            solve_period_s=params.solve_period_s,
            deadline_s=params.deadline_s,
            requires_enc=False,
        ),
    )
    return CustomMPCAdapter(
        descriptor=descriptor,
        solve=solver.solve,
        reset=solver.reset,
        context=context,
    )


def _next_waypoint(position_ne: np.ndarray, waypoints_ne: np.ndarray) -> np.ndarray:
    distances = np.linalg.norm(waypoints_ne.T - position_ne, axis=1)
    nearest = int(np.argmin(distances))
    target_index = min(nearest + 1, waypoints_ne.shape[1] - 1)
    return waypoints_ne[:, target_index].copy()


def _wrap_angle(value: float | np.ndarray) -> float | np.ndarray:
    return np.arctan2(np.sin(value), np.cos(value))


def _signed_change(value: float) -> int:
    return 0 if abs(value) < np.deg2rad(0.25) else int(np.sign(value))
