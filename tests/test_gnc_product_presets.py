"""Product presets bind complete, executable stacks without mutating old bindings."""

from types import SimpleNamespace

import numpy as np
import pytest
from fastapi.testclient import TestClient

from colav_simulator.core.colav.threat_management import MID_MPC_VALIDATION_DOMAIN_PROFILE
from colav_simulator.core.stochasticity import Config as DisturbanceConfig
from colav_simulator.experiment.runner import _inject_ownship_gnc_stack
from colav_simulator.modular_gnc.catalog import LEGACY_WITHOUT_MODULES, list_stack_catalog, stack_evidence_document
from colav_simulator.modular_gnc.contracts import CommandInput, ControlTask, DirectReference, NavigationState, TrackedRoute
from colav_simulator.modular_gnc.stack import ModularShipStack
from gui_server.main import app, manager


def _entry(preset_id: str, environment: str) -> dict:
    catalog = list_stack_catalog()
    preset = next(p for p in catalog["product_presets"] if p["id"] == preset_id)
    return next(e for e in catalog["stacks"] if e["stack_id"] == preset["variants"][environment])


def test_four_presets_share_plant_and_environment_switch_changes_only_environment() -> None:
    presets = list_stack_catalog()["product_presets"][:4]
    assert [p["display_name"] for p in presets] == [
        "Legacy Without Modules",
        "FCB 4DOF Ideal Actuation",
        "FCB Without Guidance",
        "FCB Full Stack",
    ]
    assert presets[0]["variants"] == {"off": LEGACY_WITHOUT_MODULES}
    plants = []
    for preset in presets[1:]:
        off = _entry(preset["id"], "off")["config"]["modules"]
        on = _entry(preset["id"], "on")["config"]["modules"]
        assert {k: v for k, v in on.items() if k not in {"environment", "load_model"}} == off
        assert on["load_model"]["identity"] == "fcb45_environmental_load"
        assert off["plant"]["identity"] == "fcb45_roll_4dof_plant"
        assert off["controller"]["identity"] == "fcb45_marine_pid"
        assert ("allocator" in off) == (preset["id"] != "ideal")
        plants.append(off["plant"])
    assert plants[0] == plants[1] == plants[2]


def test_explicit_legacy_preset_removes_modules_and_weather_preserving_original_chain() -> None:
    original = object()
    ownship = SimpleNamespace(ship_modules=object(), model=original, guidance=original, controller=original)
    scenario = SimpleNamespace(ship_list=[ownship], stochasticity=DisturbanceConfig())
    _inject_ownship_gnc_stack(scenario, LEGACY_WITHOUT_MODULES)
    assert ownship.ship_modules is None
    assert scenario.stochasticity is None
    assert ownship.model is ownship.guidance is ownship.controller is original


@pytest.mark.parametrize("preset_id", ["ideal", "without_guidance", "full"])
@pytest.mark.parametrize("environment", ["off", "on"])
def test_each_preset_executes_its_input_and_environment_contract(preset_id: str, environment: str) -> None:
    entry = _entry(preset_id, environment)
    scenario = SimpleNamespace(ship_list=[SimpleNamespace(ship_modules=None)], stochasticity=DisturbanceConfig())
    _inject_ownship_gnc_stack(scenario, entry["stack_id"])
    assert scenario.stochasticity is None
    stack = ModularShipStack.from_config(scenario.ship_list[0].ship_modules, dt_s=0.1)
    stack.reset(NavigationState(0.0, 0.0, 0.0, 6.0, 0.0, 0.0), seed=0)
    route = TrackedRoute(
        "preset-route", 0, True, 0, 300, np.array([[0.0, 1000.0], [0.0, 0.0]]), np.array([6.0, 6.0]), ControlTask.TRANSIT
    )
    for tick in range(200):
        reference = DirectReference(np.array([0.0, 0.0, 0.0, 6.0, 0.0, 0.0, 0.0, 0.0, 0.0]), tick)
        command = CommandInput.route(tick, route) if preset_id == "full" else CommandInput.direct(tick, reference)
        result = stack.step(command, 0.1)
        assert result.failure is None
        assert np.isfinite(result.plant.values).all()
        assert (result.environmental_loads is not None) == (environment == "on")
        assert (result.actuator_trace is not None) == (preset_id != "ideal")
    assert result.navigation.north_m > 100.0
    assert (stack.modules.guidance_trace() is not None) == (preset_id == "full")
    assert stack_evidence_document(stack.config)["stack_id"] == entry["stack_id"]


@pytest.mark.parametrize(
    "preset_id,environment",
    [
        ("legacy", "off"),
        ("ideal", "off"),
        ("ideal", "on"),
        ("without_guidance", "off"),
        ("without_guidance", "on"),
        ("full", "off"),
        ("full", "on"),
    ],
)
def test_new_product_session_creates_and_executes(preset_id: str, environment: str) -> None:
    preset = next(p for p in list_stack_catalog()["product_presets"] if p["id"] == preset_id)
    stack_id = preset["variants"][environment]
    with TestClient(app) as client:
        response = client.post(
            "/api/sessions",
            json={
                "scenario_id": "head_on",
                "validation_rule_id": "rule14",
                "algorithm_id": "mid_mpc_ipopt",
                "tracker_id": "god",
                "gnc_stack_id": stack_id,
                "t_end": 5.0,
                "domain_profile": MID_MPC_VALIDATION_DOMAIN_PROFILE.to_dict(),
            },
        )
        assert response.status_code == 200, response.text
        session_id = response.json()["session_id"]
        for _ in range(3):
            response = client.post(f"/api/sessions/{session_id}/step")
            assert response.status_code == 200, response.text
            assert response.json().get("failure_reason") is None
        modular = response.json()["modular_gnc"]
        if preset_id == "legacy":
            assert modular is None
        else:
            assert modular["stack_id"] == stack_id
            stack = manager.prepared.session.ship_list[0].stack
            assert (stack.modules.guidance_trace() is not None) == (preset_id == "full")
            assert (stack.modules.environmental_loads() is not None) == (environment == "on")
            assert (stack.modules.actuator_trace() is not None) == (preset_id != "ideal")
