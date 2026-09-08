"""Finite mission endpoints must be approached and stopped at, not extended."""

from __future__ import annotations

import numpy as np
from conftest import empty_enc

from colav_simulator.core.colav.custom_mpc_adapter import FactoryContext, PlannerInput
from colav_simulator.core.colav.mid_mpc_arrival import arrival_references, terminal_weight
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


def test_terminal_reference_rejoins_line_before_final_approach_when_space_exists() -> None:
    refs = arrival_references(
        ((0.0, 0.0), (2000.0, 0.0)),
        (0.0, 300.0),
        0.0,
        6.0,
        6.0,
        5.0,
        120,
        0.3,
        0.05,
        35.0,
        (0.0, 0.0),
        0.0,
    )
    assert refs is not None
    headings, _, speeds, _ = refs
    positions = np.array([0.0, 300.0]) + np.cumsum(
        np.column_stack([np.cos(headings), np.sin(headings)]) * np.array(speeds)[:, None] * 5.0, axis=0
    )
    halfway = np.flatnonzero(positions[:, 0] >= 1000.0)[0]
    assert abs(positions[halfway, 1]) < 10.0
    assert abs(headings[0]) <= 0.25 + 1e-9
    assert max(abs(np.diff([0.0, *headings]))) <= 0.25 + 1e-9
    assert np.linalg.norm(positions[-1] - [2000.0, 0.0]) <= 5.0


def test_near_endpoint_does_not_force_a_rejoin_past_the_goal() -> None:
    refs = arrival_references(
        ((0.0, 0.0), (150.0, 0.0)),
        (0.0, 150.0),
        -0.4,
        3.0,
        6.0,
        5.0,
        80,
        0.3,
        0.05,
        35.0,
        (0.0, 0.0),
        0.0,
    )
    assert refs is not None
    headings, _, speeds, _ = refs
    positions = np.array([0.0, 150.0]) + np.cumsum(
        np.column_stack([np.cos(headings), np.sin(headings)]) * np.array(speeds)[:, None] * 5.0, axis=0
    )
    assert max(positions[:, 0]) <= 155.0
    assert np.linalg.norm(positions[-1] - [150.0, 0.0]) <= 5.0


def test_rejoin_reference_does_not_jump_at_terminal_horizon_entry() -> None:
    args = (0.0, 6.0, 6.0, 5.0, 80, 0.3, 0.05, 35.0, (0.0, 0.0), 0.0)
    before = arrival_references(((0.0, 0.0), (2400.0, 0.0)), (0.0, 300.0), *args)
    after = arrival_references(((0.0, 0.0), (2400.0, 0.0)), (30.0, 300.0), *args)
    assert before is not None and after is not None
    assert before[3] is None and after[3] is not None
    np.testing.assert_allclose(before[0][:10], after[0][:10], atol=np.deg2rad(1.0))


def test_terminal_objective_enters_continuously_at_horizon_boundary() -> None:
    assert terminal_weight(3201.0, 8.0, 400.0, 35.0, 0.3) == 0.0
    assert terminal_weight(3200.0, 8.0, 400.0, 35.0, 0.3) == 0.0
    assert terminal_weight(3199.0, 8.0, 400.0, 35.0, 0.3) < 0.0001
    assert terminal_weight(500.0, 8.0, 400.0, 35.0, 0.3) == 1.0


def test_zero_speed_endpoint_keeps_terminal_position_correction() -> None:
    adapter = create(context=FactoryContext("mid_mpc_ipopt", 0))
    data = PlannerInput(
        sim_time_s=0.0,
        dt_sim_s=0.1,
        ownship_state=np.array([290.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
        waypoints_enu_m=np.array([[0.0, 300.0], [0.0, 0.0]]),
        speed_plan_mps=np.array([4.0, 0.0]),
        tracks=(),
        enc=empty_enc(),
        goal_state=None,
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
    assert np.linalg.norm(solution.predicted_trajectory[:2, -1] - [300.0, 0.0]) < 5.0
    assert solution.control_reference[3, 0] > 0.01
