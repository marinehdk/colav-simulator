"""BALANCE reads real stack state, including OFF/ideal and changed limits."""

import json
import math
from types import SimpleNamespace

import numpy as np
import pytest

from colav_simulator.modular_gnc.catalog import list_stack_catalog
from colav_simulator.modular_gnc.contracts import CommandInput, ControlTask, DirectReference, NavigationState, TrackedRoute
from colav_simulator.modular_gnc.stack import ModularShipStack
from gui_server.gnc_balance import balance_telemetry


def make_stack(preset: str, environment: str) -> ModularShipStack:
    catalog = list_stack_catalog()
    selected = next(p for p in catalog["product_presets"] if p["id"] == preset)
    config = next(s["config"] for s in catalog["stacks"] if s["stack_id"] == selected["variants"][environment])
    return ModularShipStack.from_config(config, dt_s=0.1)


def session_for(stack: ModularShipStack) -> SimpleNamespace:
    return SimpleNamespace(ship_list=[SimpleNamespace(stack=stack, modular_stack_config=stack.config)])


@pytest.mark.parametrize("preset", ["full", "without_guidance", "ideal"])
@pytest.mark.parametrize("environment", ["on", "off"])
def test_balance_reports_executed_state_without_advancing_stack(preset, environment):
    stack = make_stack(preset, environment)
    stack.reset(NavigationState(0, 0, 0, 6, 0, 0), seed=3)
    route = TrackedRoute(
        "balance", 0, True, 0, 200, np.array([[0.0, 1000.0], [0.0, 80.0]]), np.array([6.0, 6.0]), ControlTask.TRANSIT
    )
    for tick in range(20):
        ref = DirectReference(np.array([0.0, 0.0, 0.08, 6.0, 0.0, 0.0, 0.0, 0.0, 0.0]), tick)
        command = CommandInput.route(tick, route) if preset == "full" else CommandInput.direct(tick, ref)
        assert stack.step(command, 0.1).failure is None
    before_tick = stack.tick
    before_state = stack.modules.plant_state().values.copy()
    doc = balance_telemetry(session_for(stack))
    assert doc == balance_telemetry(session_for(stack))
    assert stack.tick == before_tick
    np.testing.assert_array_equal(stack.modules.plant_state().values, before_state)
    json.dumps(doc, allow_nan=False)
    assert doc["roll_deg"] == pytest.approx(math.degrees(stack.modules.plant_state().roll_rad))
    assert doc["environment"]["forecast"] is None
    assert doc["weather_limits"] is None
    assert doc["environment"]["status"] == ("AVAILABLE" if environment == "on" else "OFF")
    if environment == "on":
        assert doc["environment"]["wind_speed_mps"] == pytest.approx(math.hypot(6, 2))
        assert doc["environment"]["wind_from_deg"] == pytest.approx(198.4349488)
        assert doc["environment"]["current_to_deg"] == pytest.approx(333.4349488)
        assert doc["environment"]["wave_hs_m"] == 1
    else:
        assert doc["environment"]["wind_speed_mps"] is None
    if preset == "ideal":
        assert doc["propulsion"] == []
        assert doc["propulsion_status"] == "IDEAL"
    else:
        assert len(doc["propulsion"]) == 7
        trace = stack.modules.actuator_trace()
        for actuator in doc["propulsion"]:
            assert actuator["actual_n"] == trace.actuator_outputs_n[actuator["id"]]
            if actuator["kind"] == "rudder":
                assert actuator["angle_deg"] == pytest.approx(math.degrees(trace.rudder_angles_rad[actuator["id"]]))
        assert doc["bow_authority"] == 0


def test_constraints_follow_selected_parameters_not_display_defaults():
    base = make_stack("full", "on").config.to_dict()
    base["modules"]["actuator"]["parameters"]["fcb45_parameters"]["rudder_angle_limit_rad"] = 0.4
    base["modules"]["allocator"]["parameters"]["fcb45_parameters"]["rudder_angle_limit_rad"] = 0.4
    stack = ModularShipStack.from_config(base, dt_s=0.1)
    doc = balance_telemetry(session_for(stack))
    limits = {row["label"]: row for row in doc["constraints"]}
    assert limits["Max rudder angle"]["value"] == pytest.approx(math.degrees(0.4))
    assert all(item["actual_n"] is None for item in doc["propulsion"])
    assert doc["propulsion_status"] == "WAITING"


def test_legacy_and_no_ownship_have_no_fabricated_gnc_values():
    assert balance_telemetry(SimpleNamespace(ship_list=[])) is None
    assert balance_telemetry(SimpleNamespace(ship_list=[SimpleNamespace()])) is None
