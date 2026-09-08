"""Finite mission endpoints must be approached and stopped at, not extended."""

from __future__ import annotations

import numpy as np
from conftest import empty_enc

from colav_simulator.core.colav.custom_mpc_adapter import FactoryContext, PlannerInput
from colav_simulator.core.colav.mid_mpc_arrival import arrival_references
from colav_simulator.integrations.mid_mpc_ipopt import create


def test_clear_route_prediction_brakes_and_stops_at_finite_goal() -> None:
    adapter = create(context=FactoryContext("mid_mpc_ipopt", 0))
    data = PlannerInput(
        sim_time_s=0.0,
        dt_sim_s=0.1,
        ownship_state=np.array([0.0, 0.0, 0.0, 4.0, 0.0, 0.0]),
        waypoints_enu_m=np.array([[0.0, 300.0], [0.0, 0.0]]),
        speed_plan_mps=np.array([4.0, 4.0]),
        tracks=(),
        enc=empty_enc(),
        goal_state=np.array([300.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
        disturbance=None,
        algorithm_seed=0,
        ownship_length_m=45.0,
        ownship_width_m=8.0,
        ownship_draft_m=3.0,
        ownship_model="KinematicCSOG",
        ownship_controller="PassThroughCS",
    )
    solution = adapter._solve.__self__.solve(data)
    assert solution.feasible
    trajectory = solution.predicted_trajectory
    assert np.linalg.norm(trajectory[:2, -1] - [300.0, 0.0]) <= 5.0
    assert abs(trajectory[3, -1]) <= 0.1
    assert np.max(trajectory[0]) <= 305.0


def test_measured_arrival_requires_low_speed_and_small_position_error() -> None:
    adapter = create(context=FactoryContext("mid_mpc_ipopt", 0))
    waypoints = np.array([[0.0, 300.0], [0.0, 0.0]])
    assert adapter.goal_reached(np.array([300.0, 0.0, 0.0, 4.0, 0.0, 0.0]), waypoints) is False
    assert adapter.goal_reached(np.array([100.0, 0.0, 0.0, 0.0, 0.0, 0.0]), waypoints) is False
    assert adapter.goal_reached(np.array([299.0, 0.0, 0.0, 0.02, 0.0, 0.0]), waypoints) is True


def test_intermediate_leg_does_not_trigger_terminal_arrival() -> None:
    assert (
        arrival_references(
            ((0.0, 0.0), (1000.0, 0.0), (1000.0, 1000.0)),
            (0.0, 0.0),
            0.0,
            4.0,
            4.0,
            5.0,
            80,
            0.3,
            0.05,
            15.0,
            (0.0, 0.0),
            0.0,
        )
        is None
    )
