"""All planners under one GNC stack share the navigation arrival policy."""

from types import SimpleNamespace

import numpy as np
import pytest
from conftest import empty_enc

from colav_simulator.core.colav.custom_mpc_adapter import FactoryContext, PlannerInput
from colav_simulator.core.colav.mid_mpc_arrival import goal_reached as precise_mid_goal
from colav_simulator.core.colav.retained_route import RetainedRouteConstraint
from colav_simulator.integrations.mid_mpc_ipopt import create
from colav_simulator.original_gnc.adapter import OriginalGncShipAdapter
from colav_simulator.simulator import Simulator


@pytest.mark.parametrize(("distance", "expected"), [(308.69, True), (308.71, False)])
def test_gnc_arrival_uses_shared_gate_and_reports_precision_separately(distance, expected):
    ship = object.__new__(OriginalGncShipAdapter)
    state = np.array([1000 - distance, 0.0, 0.0, 8.0, 0.0, 0.0])
    waypoints = np.array([[0.0, 1000.0], [0.0, 0.0]])
    ship._legacy = SimpleNamespace(
        state=state,
        waypoints=waypoints,
        goal_csog_state=np.array([]),
        goal_reached=lambda: precise_mid_goal(state, waypoints),
    )
    ship._parameters = {"ship_dynamics_node": {"vessel.Lpp": {"value": 44.1}}}
    simulator = SimpleNamespace(ship_list=[ship], ownship=ship)
    assert bool(Simulator.determine_ship_goal_reached(simulator)) is expected
    assert precise_mid_goal(state, waypoints) is False


def test_native_mid_arrival_plan_does_not_request_precision_braking():
    adapter = create(context=FactoryContext("mid_mpc_ipopt", 0))
    value = PlannerInput(
        sim_time_s=0.0,
        dt_sim_s=0.5,
        ownship_state=np.array([0.0, 0.0, 0.0, 4.0, 0.0, 0.0]),
        waypoints_enu_m=np.array([[0.0, 1000.0], [0.0, 0.0]]),
        speed_plan_mps=np.array([4.0, 4.0]),
        tracks=(),
        enc=empty_enc(),
        goal_state=None,
        disturbance=None,
        algorithm_seed=0,
        ownship_length_m=44.1,
        ownship_width_m=8.0,
        ownship_draft_m=2.0,
        ownship_model="original_gnc_20260824_v2",
        ownship_controller="original_ship_control_20260824_v2",
        ownship_min_steerage_speed_mps=3.0,
        ownship_max_turn_rate_rad_s=np.radians(1.2),
        execution_route_constraint=RetainedRouteConstraint(
            "mission",
            ((0.0, 0.0), (1000.0, 0.0)),
            (4.0, 4.0),
            ("cruise", "cruise"),
            160.0,
            32.0,
            480.0,
            execution_speed_mps=(4.0, 4.0),
        ),
    )
    solution = adapter._solve.__self__.solve(value)
    assert solution.feasible
    trajectory = solution.predicted_trajectory
    assert np.min(np.linalg.norm(trajectory[:2].T - [1000.0, 0.0], axis=1)) < 308.7
    assert trajectory[0, -1] > 1100.0
    nearest = int(np.argmin(np.linalg.norm(trajectory[:2].T - [1000.0, 0.0], axis=1)))
    assert trajectory[3, nearest] > 2.0
    assert solution.algorithm_details["execution_route"]["navigation_modes"][-1] == "cruise"
