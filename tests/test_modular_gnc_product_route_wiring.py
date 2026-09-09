"""Product integration must execute selected ILOS and publish real vessel identity."""

from types import SimpleNamespace

import numpy as np
import pytest

from colav_simulator.core import ship
from colav_simulator.core.colav.custom_mpc_adapter import FactoryContext
from colav_simulator.core.colav.threat_assessment import OwnshipThreatPrediction
from colav_simulator.core.colav.threat_management import AcceptedPlanReceipt
from colav_simulator.integrations.mid_mpc_ipopt import create
from colav_simulator.modular_gnc.catalog import list_stack_catalog
from colav_simulator.modular_gnc.factory import build_modular_ship_adapter
from colav_simulator.modular_gnc.route_bridge import ProductRouteBridge


def _ship_config(modules) -> ship.Config:
    return ship.Config.from_dict(
        {
            "id": 0,
            "mmsi": 100,
            "csog_state": [0.0, 20.0, 4.0, 0.0],
            "waypoints": [[0.0, 500.0], [0.0, 0.0]],
            "speed_plan": [4.0, 4.0],
            "guidance": {"los": {}},
            "ship_modules": modules,
        }
    )


def test_factory_uses_mission_route_when_ilos_is_selected():
    config = _ship_config(
        {
            "preset": "legacy_equivalent",
            "overrides": {"scheduler": {"controller_period_ticks": 1, "guidance_period_ticks": 1}},
            "modules": {
                "plant": {"identity": "pass_through_plant"},
                "controller": {"identity": "pass_through_controller"},
                "guidance": {"identity": "integral_line_of_sight"},
            },
        }
    )
    adapter = build_modular_ship_adapter(config, dt_s=0.1)
    adapter.reset(0)
    adapter.plan(0.0, 0.1, [])
    adapter.forward(0.1)
    trace = adapter.stack.modules.guidance_trace()
    assert trace is not None
    assert trace.cross_track_error_m == pytest.approx(20.0)
    assert trace.heading_reference_rad < 0.0


def test_planner_receives_physical_fcb_dimensions_and_controller_identity():
    entry = next(x for x in list_stack_catalog()["stacks"] if "fcb45_environmental_load" in x["stack_id"])
    adapter = build_modular_ship_adapter(_ship_config(entry["config"]), dt_s=0.1)
    received = {}

    def plan(*args, **kwargs) -> np.ndarray:
        received.update(kwargs)
        return np.zeros((9, 1))

    adapter._legacy._colav = SimpleNamespace(plan=plan)
    adapter.plan(0.0, 0.1, [])
    assert (received["os_length"], received["os_width"], received["os_draft"]) == (44.1, 8.0, 2.0)
    assert received["os_model_name"] == "fcb45_roll_4dof_plant"
    assert received["os_controller_name"] == "fcb45_marine_pid"
    assert received["os_max_turn_rate_radps"] == 0.05


@pytest.mark.parametrize("algorithm", ["vo", "potocnik_colreg_fan_mpc"])
def test_accepted_velocity_intent_keeps_its_anchor_between_holds(algorithm):
    ownship = SimpleNamespace(state=np.array([0.0, 0.0, 0.0, 4.0, 0.0, 0.0]))
    bridge = ProductRouteBridge(ownship, 0.1)
    data = {
        "planner": {"algorithm_id": algorithm, "feasible": True, "selected_command": {"course_rad": 0.0, "speed_mps": 4.0}}
    }
    first = bridge.current_route(tick=0, planner_data=data)
    ownship.state[:2] = [10.0, 2.0]
    held = bridge.current_route(tick=1, planner_data=data)
    assert first.failure is held.failure is None
    np.testing.assert_array_equal(first.route.waypoints_ne_m, held.route.waypoints_ne_m)
    assert first.route.revision == held.route.revision


def test_mid_route_uses_executable_speed_and_only_explicit_continuation_window():
    prediction = OwnshipThreatPrediction(times_s=[0.0, 20.0], states_enu=[[0.0, 0.0, 4.0, 0.0], [80.0, 0.0, 4.0, 0.0]])
    receipt = AcceptedPlanReceipt.issue(
        accepted_sequence=1,
        accepted_at_s=0.0,
        valid_until_s=5.0,
        accepted_prediction=prediction,
        prediction_hash=prediction.semantic_hash,
    ).to_dict()
    bridge = ProductRouteBridge(SimpleNamespace(), 0.5)
    data = {
        "planner": {
            "algorithm_id": "mid_mpc_ipopt",
            "feasible": True,
            "selected_command": {"course_rad": 0.0, "speed_mps": 6.0},
            "algorithm_details": {"accepted_plan_receipt": receipt},
        }
    }
    first = bridge.current_route(tick=0, planner_data=data)
    assert first.route.speed_mps.tolist() == [6.0, 6.0]
    expired = bridge.current_route(tick=11, planner_data=data)
    assert expired.route.valid_until_tick == 10
    data["planner"]["algorithm_details"]["hold_acceptance"] = {
        "accepted": True,
        "mode": "ROLLING_PLAN_CONTINUATION",
        "checked_at_s": 5.0,
        "valid_until_s": 10.0,
    }
    continued = bridge.current_route(tick=11, planner_data=data)
    assert continued.route.valid_until_tick == 20
    late = bridge.current_route(tick=21, planner_data=data)
    assert late.route.valid_until_tick == 10
    assert receipt["valid_until_s"] == 5.0  # Original receipt/hash was not rewritten.
    data["planner"]["algorithm_details"]["hold_acceptance"]["checked_at_s"] = 5.0 + 1e-12
    at_boundary = bridge.current_route(tick=10, planner_data=data)
    assert at_boundary.route.valid_until_tick == 20


def test_route_authority_does_not_inherit_the_display_cache_delay():
    adapter = create(context=FactoryContext(requested_algorithm="mid_mpc_ipopt", algorithm_seed=0), horizon_steps=4)
    adapter._planner_trace.algorithm_details = {"hold_acceptance": {"valid_until_s": 5.0}}
    cached = adapter.get_colav_data()
    adapter._planner_trace.sim_time = 0.1
    adapter._planner_trace.algorithm_details = {"hold_acceptance": {"valid_until_s": 6.0}}
    assert adapter.get_colav_data() is cached
    assert cached["planner"]["algorithm_details"]["hold_acceptance"]["valid_until_s"] == 5.0
    assert adapter.get_route_authority()["planner"]["algorithm_details"]["hold_acceptance"]["valid_until_s"] == 6.0
