"""Original-backend identity, ownership and approved route-bridge contracts."""

from __future__ import annotations

import copy
import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import numpy as np
import pytest

from colav_simulator.core.ship import Config, build_ship
from colav_simulator.modular_gnc.catalog import list_stack_catalog
from colav_simulator.original_gnc.configuration import ORIGINAL_OFF, ORIGINAL_ON, OriginalGncConfig
from colav_simulator.original_gnc.native import OriginalGncError
from colav_simulator.original_gnc.plan_bridge import OriginalPlanBridge
from colav_simulator.original_gnc.stack import NativeStack
from colav_simulator.original_gnc.telemetry import speed_contract
from gui_server.gnc_balance import balance_telemetry


@pytest.fixture
def original_ship():
    configuration = OriginalGncConfig.from_dict({})
    if not (configuration.build_directory / "build-manifest.json").exists():
        pytest.skip("Optional original GNC is not built")
    config = Config(
        id=0,
        mmsi=123456789,
        csog_state=np.array([1000.0, 2000.0, 7.8, 0.0]),
        waypoints=np.array([[1000.0, 3500.0], [2000.0, 2000.0]]),
        speed_plan=np.array([7.8, 7.8]),
        original_gnc=configuration,
    )
    ship = build_ship(config, dt_s=0.1)
    yield ship
    ship.close()


def test_original_catalog_does_not_change_existing_full_bindings():
    catalog = list_stack_catalog()
    assert [p["id"] for p in catalog["product_presets"]] == ["legacy", "ideal", "without_guidance", "full", "original_gnc"]
    full = next(p for p in catalog["product_presets"] if p["id"] == "full")
    hashes = {entry["stack_id"]: entry["config_hash"] for entry in catalog["stacks"]}
    assert hashes[full["variants"]["off"]] == "a61684f1ab619ce856f227be78b04c8a6a65e5e599199f00630d1169424a2ac6"
    assert hashes[full["variants"]["on"]] == "802307cace0a7df049e8d26b891870347819583546fcd638eaff1a0ac1933d5a"
    assert {entry["stack_id"] for entry in catalog["original_gnc_stacks"]} == {ORIGINAL_OFF, ORIGINAL_ON}
    assert all("modules" not in entry["config"] for entry in catalog["original_gnc_stacks"])


def test_balance_uses_recorded_frame_after_native_stack_advances(original_ship):
    original_ship.forward(0.5)
    frame = {"Ship0": original_ship.get_sim_data(0.5, 0)}
    session = SimpleNamespace(ship_list=[original_ship])
    before = balance_telemetry(session, frame=frame)
    original_ship.forward(0.5)
    after = balance_telemetry(session, frame=frame)
    assert before == after
    assert after["speed_contract"]["sample_time_s"] == 0.5
    assert balance_telemetry(session)["speed_contract"]["sample_time_s"] == 1.0


def test_source_dependency_failure_does_not_select_full(tmp_path, monkeypatch):
    monkeypatch.setenv("COLAV_ORIGINAL_GNC_BUILD", str(tmp_path / "missing"))
    catalog = list_stack_catalog()
    assert all(not entry["available"] for entry in catalog["original_gnc_stacks"])
    assert next(p for p in catalog["product_presets"] if p["id"] == "full")["variants"]["off"]


def test_original_catalog_reports_loaded_build_identity():
    configuration = OriginalGncConfig.from_dict({})
    manifest_path = configuration.build_directory / "build-manifest.json"
    if not manifest_path.is_file():
        pytest.skip("Optional original GNC is not built")
    manifest = json.loads(manifest_path.read_text())
    proposals = (manifest.get("colleague_proposal") or {}).get("proposals") or []
    proposal_ids = [item.get("id") if isinstance(item, dict) else item for item in proposals]
    expected = {
        "execution_lane": "candidate" if proposal_ids else "baseline",
        "candidate": "colleague_proposal" if proposal_ids else None,
        "proposal_ids": proposal_ids,
        "source_manifest_sha256": manifest["source_manifest_sha256"],
        "library_sha256": manifest["library_sha256"],
    }
    catalog = list_stack_catalog()
    assert all(entry["build_identity"] == expected for entry in catalog["original_gnc_stacks"])
    preset = next(p for p in catalog["product_presets"] if p["id"] == "original_gnc")
    assert preset["build_identity"] == expected
    if proposal_ids:
        assert preset["description"] == (
            "Original GNC candidate · " + ", ".join(proposal_ids) + " · independent local C++ backend"
        )
        assert "Baseline fidelity evidence does not automatically cover this candidate" in preset["note"]
    else:
        assert preset["description"] == "Native C++ · course / route input."
    assert "Original GNC acceptance remains diagnostic" in preset["note"]


def test_original_config_roundtrip_and_exclusive_execution():
    original = OriginalGncConfig.from_dict({"environment": True})
    config = Config(original_gnc=original)
    restored = Config.from_dict(config.to_dict())
    assert restored.original_gnc == original
    assert restored.ship_modules is None
    config.ship_modules = object()
    with pytest.raises(ValueError, match="both modular and original"):
        build_ship(config)


def test_original_motion_and_telemetry_never_execute_legacy_control(original_ship):
    with patch("colav_simulator.core.ship.erk4_integration_step", side_effect=AssertionError("old integrator executed")):
        with patch.object(
            original_ship._legacy._controller, "compute_inputs", side_effect=AssertionError("old controller executed")
        ):
            for _ in range(10):
                original_ship.forward(0.1)
            data = original_ship.get_sim_data(1.0, 0)
    eta = original_ship.stack.states["ship_dynamics_node"]["eta"]
    assert original_ship.state[0] == eta[0] + 1000
    assert original_ship.state[1] == eta[1] + 2000
    assert data["original_gnc"]["stack_id"] == ORIGINAL_OFF
    assert data["original_gnc"]["state_8d"] == original_ship.original_state.tolist()
    assert original_ship.get_ship_info()["length"] == 44.1
    assert len(original_ship.original_balance_telemetry()["propulsion"]) == 7


def test_initial_template_clone_owns_fresh_kernels(original_ship):
    clone = copy.deepcopy(original_ship)
    try:
        untouched = copy.deepcopy(clone.stack.states)
        original_ship.forward(0.3)
        assert clone.stack.states == untouched
        clone.forward(0.1)
        clone.forward(0.2)
        assert clone.stack.states == original_ship.stack.states
        with pytest.raises(OriginalGncError, match="opaque state cannot be copied"):
            copy.deepcopy(original_ship)
    finally:
        clone.close()


def test_adapter_matches_direct_core_and_reset_at_each_shared_time(original_ship):
    ship = original_ship
    with NativeStack(
        ship.configuration.build_directory,
        copy.deepcopy(ship._kernel_parameters),
        ship._package_roots,
        ship._policy_config,
        asset_paths=ship._asset_paths,
    ) as direct:
        for request in ship.requested_plans:
            direct.publish("/route_planning/route_plan", "ship_interfaces/msg/RoutePlan", request["message"])
            direct.publish_initial_state()
        for index in range(200):
            # Exercise different external partitions without changing source periods.
            direct.advance(0.5)
            ship.forward(0.13)
            ship.forward(0.37)
            assert ship.stack.states == direct.states, index
            assert ship.stack.latest == direct.latest, index
        expected = copy.deepcopy(direct.states)
    ship.reset(0)
    ship.forward(100.0)
    assert ship.stack.states == expected


def _intent() -> Any:
    return {
        "planner": {
            "algorithm_id": "vo",
            "solver_executed": True,
            "solve_id": 1,
            "feasible": True,
            "selected_command": {"course_rad": 0.2, "speed_mps": 7.8},
            "algorithm_details": {
                "hard_constraint_count": 1,
                "active_rules": {"1": ["HO"]},
                "give_way_commitment_active": True,
                "stand_on_hold_active": False,
                "static_hazard_count": 0,
                "solve_period_s": 1.0,
            },
        }
    }


def test_approved_velocity_intent_is_admitted_and_expires(original_ship):
    ship = original_ship
    ship.forward(11)
    ship._planner_time_origin = 0
    data = _intent()
    ship._legacy._colav = SimpleNamespace(
        get_route_authority=lambda: data,
        get_colav_data=lambda: data,
        get_diagnostics=lambda: SimpleNamespace(to_dict=lambda: {}),
    )
    bridge = OriginalPlanBridge(ship, 0.1)
    ship._plan_bridge = bridge
    bridge.submit(11)
    request = ship.requested_plans[-1]
    assert request["identity"]["authority"] == "velocity_intent"
    assert request["message"]["speed_mps"] == pytest.approx(7.8)
    assert request["message"]["valid_until"] == {"sec": 2_000_000_012, "nanosec": 0}
    assert "latitude" not in request["message"]
    assert bridge.last_outcome["accepted"] and not bridge.last_outcome["rejected"]
    doc = ship.original_balance_telemetry()
    assert doc["speed_contract"]["input_kind"] == "velocity_intent"
    count = len(ship.requested_plans)
    data["planner"]["solver_executed"] = False
    ship.forward(0.1)
    bridge.submit(11.1)
    assert len(ship.requested_plans) == count
    ship.forward(2.0)
    with pytest.raises(OriginalGncError, match="Expired"):
        bridge.submit(13.1)


def test_cleared_constraints_keep_the_planner_velocity_owner(original_ship):
    ship = original_ship
    ship.forward(11)
    ship._planner_time_origin = 0
    data = _intent()
    ship._legacy._colav = SimpleNamespace(get_route_authority=lambda: data)
    bridge = OriginalPlanBridge(ship, 0.1)
    bridge.submit(11)
    data["planner"]["algorithm_details"].update(hard_constraint_count=0, active_rules={}, give_way_commitment_active=False)
    data["planner"]["solve_id"] = 2
    ship.forward(0.1)
    bridge.submit(11.1)
    assert ship.stack.states["active_route_manager_node"]["active_velocity_intent"]
    assert ship.requested_plans[-1]["message"]["behavior_mode"] == "cruise"


def test_speed_projection_does_not_materialize_full_diagnostics(original_ship, monkeypatch):
    planner = {"selected_command": {"speed_mps": 4.25}, "sim_time": 12.0}
    original_ship._legacy._colav = SimpleNamespace(get_colav_data=lambda: {"planner": planner})

    def expensive_snapshot():
        raise AssertionError("Speed projection must not copy complete planner diagnostics")

    monkeypatch.setattr(original_ship._legacy, "get_colav_data", expensive_snapshot)
    result = speed_contract(original_ship)
    assert result["planner_speed_mps"] == 4.25
    assert result["planner_sample_time_s"] == 12.0
