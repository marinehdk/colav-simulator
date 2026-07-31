from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from colav_simulator.core.colav.diagnostics import ColavExecutionError
from colav_simulator.experiment.busy_water import (
    ACCEPTANCE_EVENTS,
    build_busy_water_document,
    preflight_document,
)
from colav_simulator.experiment.capabilities import CapabilityCatalog
from colav_simulator.integrations import IntegrationRegistry
from gui_server.main import app


def test_acceptance_scenario_is_deterministic_and_matches_committed_yaml() -> None:
    generated = build_busy_water_document("acceptance")
    committed = yaml.safe_load(Path("scenarios/romsdal_busy_water_16.yaml").read_text(encoding="utf-8"))

    assert generated == committed
    assert len(generated["ship_list"]) == 16
    assert len({ship["id"] for ship in generated["ship_list"]}) == 16


def test_stress_scenario_is_seeded_and_matches_committed_yaml() -> None:
    generated = build_busy_water_document("stress")
    committed = yaml.safe_load(Path("scenarios/romsdal_busy_water_80_stress.yaml").read_text(encoding="utf-8"))

    assert generated == committed
    assert len(generated["ship_list"]) == 80
    assert generated != build_busy_water_document("stress", seed=20250732)


def test_acceptance_preflight_covers_six_nominal_encounter_roles_without_target_collision() -> None:
    result = preflight_document(build_busy_water_document("acceptance"))

    detected = [item["detected_encounter"] for item in result["planned_events"]]
    assert len(result["planned_events"]) == len(ACCEPTANCE_EVENTS) == 8
    assert {
        "head_on",
        "crossing_give_way",
        "crossing_stand_on",
        "overtaking",
        "overtaken",
    }.issubset(detected)
    assert result["nominal_target_collision_count"] == 0
    assert result["routes_inside_map"] is True


def test_stress_preflight_reports_79_targets_and_valid_routes() -> None:
    result = preflight_document(build_busy_water_document("stress"))

    assert result["ship_count"] == 80
    assert result["target_count"] == 79
    assert result["active_windows_valid"] is True
    assert result["routes_inside_map"] is True


def test_capability_api_marks_busy_water_scenarios_experimental_not_g3() -> None:
    with TestClient(app) as client:
        response = client.get("/api/capabilities?validation_rule_id=multiship")

    assert response.status_code == 200
    catalog = response.json()
    scenarios = {item["id"]: item for item in catalog["scenarios"]}
    for scenario_id in ("romsdal_busy_water_16", "romsdal_busy_water_80_stress"):
        assert scenarios[scenario_id]["readiness_grade"] == "G2"
        assert scenarios[scenario_id]["selectable"] is True
        assert scenarios[scenario_id]["verified_combinations"] == []
        assert scenarios[scenario_id]["experimental_combinations"]
    assert all(
        item["scenario_id"] not in {"romsdal_busy_water_16", "romsdal_busy_water_80_stress"}
        for item in catalog["verified_combinations"]
    )


def test_experimental_busy_water_tuple_is_selectable_only_for_colreg_fan_mpc() -> None:
    catalog = CapabilityCatalog(IntegrationRegistry())

    assert (
        catalog.validate(
            "multiship",
            "romsdal_busy_water_16",
            "potocnik_colreg_fan_mpc",
            "god",
        )
        == "multiship:romsdal_busy_water_16:potocnik_colreg_fan_mpc:god"
    )
    with pytest.raises(ColavExecutionError, match="No selectable capability tuple"):
        catalog.validate("multiship", "romsdal_busy_water_16", "vo", "god")
