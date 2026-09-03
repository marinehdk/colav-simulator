"""GNC stack catalog API and additive telemetry evidence metadata (Issue #60)."""

from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from colav_simulator.core import ship
from colav_simulator.experiment.contracts import RunSpec
from colav_simulator.modular_gnc.adapter import ModularShipAdapter
from colav_simulator.modular_gnc.catalog import (
    STACK_EVIDENCE_SCHEMA_VERSION,
    list_stack_catalog,
    stack_evidence_document,
)
from colav_simulator.modular_gnc.configuration import normalize_ship_modules
from colav_simulator.modular_gnc.contracts import ControlTask
from colav_simulator.modular_gnc.stack import ModularShipStack
from gui_server.main import (
    SessionCreateRequest,
    _modular_gnc_telemetry_metadata,
    app,
    manager,
)


def _ship_config_with_modules(ship_modules: dict) -> ship.Config:
    return ship.Config.from_dict(
        {
            "id": 4,
            "mmsi": 44,
            "csog_state": [10.0, 20.0, 3.0, 5.0],
            "waypoints": [[10.0, 100.0], [20.0, 25.0]],
            "speed_plan": [3.0, 3.0],
            "guidance": {"los": {}},
            "ship_modules": ship_modules,
        }
    )


def _modular_ship() -> ModularShipAdapter:
    config = _ship_config_with_modules(
        {
            "preset": "legacy_equivalent",
            "modules": {
                "plant": {
                    "identity": "generic_3dof_plant",
                    "parameters": {"mass_kg": 1.6e7, "i_z_kgm2": 3.0e10},
                },
                "guidance": {"identity": "pass_through_guidance", "parameters": {}},
                "controller": {"identity": "pass_through_controller", "parameters": {}},
                "allocator": {
                    "identity": "data_driven_allocator",
                    "parameters": {"layout_asset_id": "default_triple_actuator_layout_v1"},
                },
            },
        }
    )
    stack = ModularShipStack.from_config(config.ship_modules)
    return ModularShipAdapter.from_legacy_config(config, stack)


def test_gnc_stacks_endpoint_serves_catalog() -> None:
    with TestClient(app) as client:
        response = client.get("/api/gnc/stacks")

    assert response.status_code == 200
    document = response.json()
    assert document["schema_version"] == "modular-gnc.stack-catalog.v1"
    assert document["stacks"]
    assert document["default_stack_id"] in {entry["stack_id"] for entry in document["stacks"]}


def test_unprepared_telemetry_payload_carries_modular_gnc_key() -> None:
    payload = manager._telemetry(None)

    assert payload["schema_version"] == "1.0"
    assert "modular_gnc" in payload
    assert payload["modular_gnc"] is None


def test_telemetry_metadata_is_none_for_legacy_ship() -> None:
    legacy_ship = SimpleNamespace()  # legacy Ship exposes no modular_stack_config

    assert _modular_gnc_telemetry_metadata(SimpleNamespace(ship_list=[legacy_ship])) is None
    assert _modular_gnc_telemetry_metadata(SimpleNamespace(ship_list=[])) is None


def test_telemetry_metadata_document_for_modular_ship() -> None:
    document = _modular_gnc_telemetry_metadata(SimpleNamespace(ship_list=[_modular_ship()]))

    assert document is not None
    assert document["schema_version"] == STACK_EVIDENCE_SCHEMA_VERSION
    assert document["fidelity_profile"] == "ideal"
    assert {module["role"]: module["identity"] for module in document["modules"]}["allocator"] == (
        "data_driven_allocator"
    )
    assert document["asset_trust"] == [
        {
            "asset_id": "default_triple_actuator_layout_v1",
            "asset_type": "actuator_layout",
            "trust_level": "mock",
        }
    ]
    assert document["supported_tasks"] == ["MANUAL_LOAD", "TRANSIT"]


def test_adapter_exposes_stack_config_and_tasks_for_telemetry() -> None:
    adapter = _modular_ship()

    expected = normalize_ship_modules(adapter.modular_stack_config.to_dict())
    assert adapter.modular_stack_config.config_hash == expected.config_hash
    assert adapter.modular_stack_supported_tasks == frozenset(
        {ControlTask.TRANSIT, ControlTask.MANUAL_LOAD}
    )


def test_evidence_document_assembles_stack_when_tasks_not_given() -> None:
    config = normalize_ship_modules(_modular_ship().modular_stack_config.to_dict())

    document = stack_evidence_document(config)

    assert document["supported_tasks"] == ["MANUAL_LOAD", "TRANSIT"]
    assert all(entry["config_hash"] != config.config_hash for entry in list_stack_catalog()["stacks"])


def _a_resolved_stack_id() -> str:
    return next(
        entry["stack_id"] for entry in list_stack_catalog()["stacks"] if entry["fidelity_profile"] == "resolved"
    )


def test_create_request_maps_gnc_stack_id_into_run_spec() -> None:
    request = SessionCreateRequest(validation_rule_id="rule14", gnc_stack_id="some-stack")

    spec = request.to_spec()

    assert spec.ownship_gnc_stack_id == "some-stack"
    assert SessionCreateRequest(validation_rule_id="rule14").to_spec().ownship_gnc_stack_id is None


def test_run_spec_serialization_round_trips_stack_id() -> None:
    spec = RunSpec(scenario_id="head_on", validation_rule_id="rule14", ownship_gnc_stack_id="some-stack")

    document = spec.to_dict()
    assert document["ownship_gnc_stack_id"] == "some-stack"
    assert RunSpec.from_dict(document).ownship_gnc_stack_id == "some-stack"
    assert RunSpec(scenario_id="head_on").ownship_gnc_stack_id is None


def test_create_session_with_gnc_stack_binds_modular_ownship() -> None:
    with TestClient(app) as client:
        created = client.post(
            "/api/sessions",
            json={
                "validation_rule_id": "multiship",
                "scenario_id": "paper_ccta2023_multiship",
                "algorithm_id": "vo",
                "tracker_id": "god",
                "t_end": 0.2,
                "gnc_stack_id": _a_resolved_stack_id(),
            },
        )
        assert created.status_code == 200
        session_id = created.json()["session_id"]

        stepped = client.post(f"/api/sessions/{session_id}/step")

    assert stepped.status_code == 200
    modular = stepped.json()["modular_gnc"]
    assert modular is not None
    assert modular["stack_id"] == _a_resolved_stack_id()
    assert isinstance(manager.prepared.session.ship_list[0], ModularShipAdapter)


def test_create_session_without_gnc_stack_keeps_legacy_ownship() -> None:
    with TestClient(app) as client:
        created = client.post(
            "/api/sessions",
            json={
                "validation_rule_id": "multiship",
                "scenario_id": "paper_ccta2023_multiship",
                "algorithm_id": "vo",
                "tracker_id": "god",
                "t_end": 0.2,
            },
        )
        assert created.status_code == 200
        session_id = created.json()["session_id"]

        stepped = client.post(f"/api/sessions/{session_id}/step")

    assert stepped.status_code == 200
    assert stepped.json()["modular_gnc"] is None


def test_create_session_with_unknown_gnc_stack_is_rejected_with_422() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/sessions",
            json={
                "validation_rule_id": "multiship",
                "scenario_id": "paper_ccta2023_multiship",
                "algorithm_id": "vo",
                "tracker_id": "god",
                "gnc_stack_id": "not-a-catalog-stack",
            },
        )

    assert response.status_code == 422
    assert "not-a-catalog-stack" in response.json()["detail"]["reason"]


def test_create_historical_scene_with_gnc_stack_is_rejected_with_422() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/sessions",
            json={
                "validation_rule_id": "multiship",
                "scenario_id": "hais_romsdal_20260701_120007_121007",
                "algorithm_id": "vo",
                "tracker_id": "god",
                "gnc_stack_id": _a_resolved_stack_id(),
            },
        )

    assert response.status_code == 422
    assert "GNC stack" in response.json()["detail"]["reason"]
