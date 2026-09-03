"""GNC stack catalog API and additive telemetry evidence metadata (Issue #60)."""

from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from colav_simulator.core import ship
from colav_simulator.modular_gnc.adapter import ModularShipAdapter
from colav_simulator.modular_gnc.catalog import (
    STACK_EVIDENCE_SCHEMA_VERSION,
    list_stack_catalog,
    stack_evidence_document,
)
from colav_simulator.modular_gnc.configuration import normalize_ship_modules
from colav_simulator.modular_gnc.contracts import ControlTask
from colav_simulator.modular_gnc.stack import ModularShipStack
from gui_server.main import _modular_gnc_telemetry_metadata, app, manager


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
    assert any(entry["config_hash"] == config.config_hash for entry in list_stack_catalog()["stacks"])
