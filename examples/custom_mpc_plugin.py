"""Deterministic contract fixture for the CustomMPCAdapter quick-start."""

from __future__ import annotations

import numpy as np

from colav_simulator.core.colav.custom_mpc_adapter import (
    AlgorithmDescriptor,
    CustomMPCAdapter,
    ExecutionProfile,
    FactoryContext,
    MPCSolution,
    PlannerInput,
)

__version__ = "1.0.0"


class StraightLineFixture:
    """Simple deterministic predictor used only to verify the plugin contract."""

    def __init__(self, horizon_steps: int, horizon_dt_s: float) -> None:
        self.horizon_steps = horizon_steps
        self.horizon_dt_s = horizon_dt_s
        self.solve_count = 0

    def reset(self) -> None:
        self.solve_count = 0

    def solve(self, planner_input: PlannerInput) -> MPCSolution:
        self.solve_count += 1
        state = planner_input.ownship_state
        trajectory = np.zeros((9, self.horizon_steps), dtype=float)
        trajectory[:6, 0] = state
        for index in range(1, self.horizon_steps):
            elapsed = index * self.horizon_dt_s
            trajectory[0, index] = state[0] + state[3] * np.cos(state[2]) * elapsed
            trajectory[1, index] = state[1] + state[3] * np.sin(state[2]) * elapsed
            trajectory[2:6, index] = state[2:6]
        reference = trajectory[:, min(1, self.horizon_steps - 1)].reshape(9, 1)
        return MPCSolution(
            control_reference=reference,
            predicted_trajectory=trajectory,
            horizon_dt_s=self.horizon_dt_s,
            objective=0.0,
            iterations=1,
            feasible=True,
            constraints={"collision_clearance_m": None},
            algorithm_details={"fixture": True, "solve_count": self.solve_count},
        )


def create(
    *,
    context: FactoryContext,
    horizon_steps: int = 5,
    horizon_dt_s: float = 0.5,
    solve_period_s: float = 1.0,
    deadline_s: float = 1.0,
) -> CustomMPCAdapter:
    """Create a strict adapter around the deterministic fixture solver."""
    solver = StraightLineFixture(horizon_steps, horizon_dt_s)
    descriptor = AlgorithmDescriptor(
        algorithm_id=context.requested_algorithm,
        version=__version__,
        control_form="course_speed_reference",
        state_layout=("x", "y", "psi", "u", "v", "r", "x_ddot", "y_ddot", "psi_dot"),
        predictor_model="constant_course_speed_fixture",
        horizon_dt=horizon_dt_s,
        horizon_steps=horizon_steps,
        objective_terms=("not_applicable",),
        constraint_terms=("not_applicable",),
        solver="deterministic_fixture",
        seed_policy="deterministic_no_rng",
        execution_profile=ExecutionProfile(
            solve_period_s=solve_period_s,
            deadline_s=deadline_s,
        ),
    )
    return CustomMPCAdapter(
        descriptor=descriptor,
        solve=solver.solve,
        reset=solver.reset,
        context=context,
    )
