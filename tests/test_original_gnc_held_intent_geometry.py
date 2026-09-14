"""Scalar-planner regression: recorded OT commands must not become invented routes."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from colav_simulator.original_gnc.plan_bridge import OriginalPlanBridge


@pytest.mark.parametrize("algorithm", ["vo", "potocnik_colreg_fan_mpc"])
def test_recorded_ot_command_is_forwarded_without_route_geometry(algorithm):
    case = json.loads((Path(__file__).parent / "fixtures/original_gnc/overtaking-splice-428s.json").read_text())
    details = {
        "solve_period_s": 5.0,
        "hard_constraint_count": 3,
        "active_rules": {},
        "give_way_commitment_active": False,
        "stand_on_hold_active": False,
        "static_hazard_count": 0,
        "active_encounters": ["overtaking"],
        "static_constraint_active": False,
        "dynamic_safety_buffer_recovery": False,
    }
    data = {
        "planner": {
            "algorithm_id": algorithm,
            "solver_executed": True,
            "solve_id": 7,
            "feasible": True,
            "selected_command": case["command"],
            "algorithm_details": details,
        }
    }
    epoch = 2_000_000_000_000_000_000
    ship = SimpleNamespace(
        _legacy=SimpleNamespace(_colav=SimpleNamespace(get_route_authority=lambda: data)),
        stack=SimpleNamespace(time_ns=epoch + 428_000_000_000, epoch_ns=epoch),
        _nominal_id="mission",
        _nominal_revision=1,
        _planner_time_origin=0,
    )
    bridge = OriginalPlanBridge(ship, 0.5)
    published = []

    def deliver(request, identity, *, kind):
        published.append((request, identity, kind))
        bridge.last_outcome = {"rejected": False}

    bridge._deliver = deliver
    bridge.submit(428.0)
    request, identity, kind = published[0]
    assert kind == "velocity_intent"
    assert request["course_rad"] == case["command"]["course_rad"]
    assert request["speed_mps"] == case["command"]["speed_mps"]
    assert "latitude" not in request and "longitude" not in request
    assert identity["synthetic_route"] is False
