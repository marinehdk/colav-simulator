from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from colav_simulator.core.colav.diagnostics import ColavExecutionError
from colav_simulator.experiment.busy_water import (
    DEFAULT_ENCOUNTER_MIX,
    allocate_encounter_counts,
    build_busy_water_document,
    preflight_document,
)
from colav_simulator.experiment.capabilities import CapabilityCatalog
from colav_simulator.integrations import IntegrationRegistry
from gui_server import main as gui_main


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


def test_crossing_dominant_mix_uses_exact_largest_remainder_counts() -> None:
    assert allocate_encounter_counts(15, DEFAULT_ENCOUNTER_MIX) == {
        "crossing": 9,
        "head_on": 3,
        "overtaking": 3,
    }
    assert allocate_encounter_counts(12, DEFAULT_ENCOUNTER_MIX) == {
        "crossing": 7,
        "head_on": 3,
        "overtaking": 2,
    }


def test_acceptance_preflight_has_balanced_roles_and_valid_routes() -> None:
    result = preflight_document(build_busy_water_document("acceptance"))

    configured = [item["configured_encounter"] for item in result["planned_events"]]
    assert result["configured_encounter_counts"] == {"crossing": 9, "head_on": 3, "overtaking": 3}
    assert abs(configured.count("crossing_give_way") - configured.count("crossing_stand_on")) <= 1
    assert abs(configured.count("overtaking") - configured.count("overtaken")) <= 1
    assert result["routes_inside_map"] is True
    assert result["initial_footprints_separated"] is True


def test_configurable_target_count_and_seed_are_repeatable() -> None:
    first = build_busy_water_document("acceptance", target_count=9, seed=41)
    second = build_busy_water_document("acceptance", target_count=9, seed=41)

    assert first == second
    assert len(first["ship_list"]) == 10
    assert preflight_document(first, seed=41)["configured_encounter_counts"] == {
        "crossing": 5,
        "head_on": 2,
        "overtaking": 2,
    }
    with pytest.raises(ValueError, match="target_count"):
        build_busy_water_document("acceptance", target_count=2)


def test_stress_preflight_reports_79_targets_and_valid_routes() -> None:
    result = preflight_document(build_busy_water_document("stress"))

    assert result["ship_count"] == 80
    assert result["target_count"] == 79
    assert result["active_windows_valid"] is True
    assert result["routes_inside_map"] is True


def test_busy_water_scenarios_expose_four_experimental_algorithms_not_g3() -> None:
    with TestClient(gui_main.app) as client:
        response = client.get("/api/capabilities?validation_rule_id=multiship")

    assert response.status_code == 200
    catalog = response.json()
    scenarios = {item["id"]: item for item in catalog["scenarios"]}
    expected = {"nominal", "vo", "sbmpc", "potocnik_colreg_fan_mpc"}
    for scenario_id in ("romsdal_busy_water_16", "romsdal_busy_water_80_stress"):
        assert scenarios[scenario_id]["readiness_grade"] == "G2"
        assert scenarios[scenario_id]["verified_combinations"] == []
        algorithms = {
            item["algorithm_id"]
            for item in scenarios[scenario_id]["experimental_combinations"]
        }
        assert algorithms == expected


@pytest.mark.parametrize("algorithm_id", ("nominal", "vo", "sbmpc", "potocnik_colreg_fan_mpc"))
def test_experimental_busy_water_algorithms_are_selectable(algorithm_id: str) -> None:
    catalog = CapabilityCatalog(IntegrationRegistry())

    assert catalog.validate("multiship", "romsdal_busy_water_16", algorithm_id, "god") == (
        f"multiship:romsdal_busy_water_16:{algorithm_id}:god"
    )
    with pytest.raises(ColavExecutionError, match="No selectable capability tuple"):
        catalog.validate("multiship", "romsdal_busy_water_16", algorithm_id, "kf")


def test_busy_water_generate_and_draft_round_trip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gui_main, "DRAFT_DIR", tmp_path)
    with TestClient(gui_main.app) as client:
        generated = client.get(
            "/api/busy-water/generate",
            params={"profile": "acceptance", "target_count": 9, "seed": 23},
        )
        assert generated.status_code == 200
        payload = generated.json()
        assert payload["preflight"]["target_count"] == 9
        assert payload["encounter_mix"] == {"crossing": 0.6, "head_on": 0.2, "overtaking": 0.2}

        saved = client.post(
            "/api/busy-water/drafts",
            json={
                "name": "Harbor Trial",
                "base_scenario_id": "romsdal_busy_water_16",
                "seed": 23,
                "encounter_mix": {"crossing": 0.7, "head_on": 0.2, "overtaking": 0.1},
                "document": payload["document"],
            },
        )
        assert saved.status_code == 200
        draft_id = saved.json()["id"]
        loaded = client.get(f"/api/busy-water/drafts/{draft_id}")
        listed = client.get("/api/busy-water/drafts")

    assert loaded.status_code == 200
    assert loaded.json()["document"] == payload["document"]
    assert loaded.json()["target_count"] == 9
    assert loaded.json()["encounter_mix"] == {"crossing": 0.7, "head_on": 0.2, "overtaking": 0.1}
    assert listed.json() == [
        {
            "id": draft_id,
            "name": "Harbor Trial",
            "base_scenario_id": "romsdal_busy_water_16",
            "seed": 23,
            "target_count": 9,
            "encounter_mix": {"crossing": 0.7, "head_on": 0.2, "overtaking": 0.1},
        }
    ]


def test_busy_water_generate_rejects_invalid_count() -> None:
    with TestClient(gui_main.app) as client:
        response = client.get("/api/busy-water/generate", params={"target_count": 80})

    assert response.status_code == 422


def test_override_session_exposes_all_ships_and_routes_while_created() -> None:
    document = build_busy_water_document("acceptance", target_count=3, seed=31)
    with TestClient(gui_main.app) as client:
        created = client.post(
            "/api/sessions",
            json={
                "validation_rule_id": "multiship",
                "scenario_id": "romsdal_busy_water_16",
                "algorithm_id": "nominal",
                "tracker_id": "god",
                "seed": 31,
                "t_end": 0.1,
                "scenario_override": document,
            },
        )
        assert created.status_code == 200, created.json()
        session_id = created.json()["session_id"]
        with client.websocket_connect(f"/ws/sessions/{session_id}") as websocket:
            telemetry = websocket.receive_json()

    assert telemetry["state"] == "CREATED"
    assert telemetry["scenario_id"] == "romsdal_busy_water_16"
    assert len(telemetry["obstacles"]) == 3
    assert len(telemetry["target_routes"]) == 3
