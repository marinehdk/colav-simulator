from __future__ import annotations

import numpy as np
import pytest

from colav_simulator.core.colav.diagnostics import PlanStatus
from colav_simulator.integrations import IntegrationRegistry


def test_official_sbmpc_reference_matches_native_head_on_golden() -> None:
    registry = IntegrationRegistry()
    status = registry.statuses()["sbmpc_reference"]
    if not status.available:
        pytest.skip(status.reason)

    planner = registry.build_algorithm("sbmpc_reference")
    assert planner is not None
    covariance = np.eye(4)
    plan = planner.plan(
        t=0.0,
        waypoints=np.array([[0.0, 2000.0], [0.0, 0.0]]),
        speed_plan=np.array([7.0, 7.0]),
        ownship_state=np.array([0.0, 0.0, 0.0, 7.0, 0.0, 0.0]),
        do_list=[
            (
                1,
                np.array([500.0, 0.0, -7.0, 0.0]),
                covariance,
                10.0,
                3.0,
            )
        ],
        enc=None,
        os_length=10.0,
        os_width=3.0,
        os_draft=1.0,
        dt=0.5,
    )

    assert plan.shape == (9, 1)
    assert plan[2, 0] == pytest.approx(np.deg2rad(15.0))
    assert plan[3, 0] == pytest.approx(7.0)
    diagnostics = planner.get_diagnostics()
    assert diagnostics.status == PlanStatus.SUCCESS
    assert diagnostics.executed_algorithm == "sbmpc_reference"
    trace = planner.get_colav_data()["planner"]
    assert trace["solver_executed"] is True
    assert np.asarray(trace["predicted_trajectory"]).shape == (9, 220)
    assert trace["algorithm_details"]["implementation"] == "official_native_sbmpc"
    assert trace["algorithm_details"]["core_commit"] == "8b78d009d173db20af28e1a2a662417c8d893f12"


def test_official_sbmpc_reference_holds_last_command_between_solves() -> None:
    registry = IntegrationRegistry()
    status = registry.statuses()["sbmpc_reference"]
    if not status.available:
        pytest.skip(status.reason)

    planner = registry.build_algorithm("sbmpc_reference")
    assert planner is not None
    inputs = {
        "waypoints": np.array([[0.0, 2000.0], [0.0, 0.0]]),
        "speed_plan": np.array([7.0, 7.0]),
        "ownship_state": np.array([0.0, 0.0, 0.0, 7.0, 0.0, 0.0]),
        "do_list": [],
        "enc": None,
        "os_length": 10.0,
        "os_width": 3.0,
        "os_draft": 1.0,
        "dt": 0.5,
    }
    first = planner.plan(t=0.0, **inputs)
    held = planner.plan(t=1.0, **inputs)

    assert held == pytest.approx(first)
    assert planner.get_colav_data()["planner"]["solver_executed"] is False
