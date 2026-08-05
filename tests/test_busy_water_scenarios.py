from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from colav_simulator.core.colav.diagnostics import ColavExecutionError
from colav_simulator.experiment.busy_water import (
    BUSY_WATER_DURATION_S,
    DEFAULT_ENCOUNTER_MIX,
    allocate_encounter_counts,
    build_busy_water_document,
    normalize_single_pass_document,
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
    assert generated["t_end"] == BUSY_WATER_DURATION_S == 1200.0
    assert generated["ship_list"][0]["model"]["csog"]["length"] == 45.0
    assert generated["ship_list"][0]["model"]["csog"]["width"] == 8.0
    targets = generated["ship_list"][1:]
    assert all(ship["model"]["csog"]["length"] == 12.0 for ship in targets)
    assert all(ship["model"]["csog"]["width"] == 4.0 for ship in targets)
    assert all(0.0 <= ship["t_start"] < ship["t_end"] <= BUSY_WATER_DURATION_S for ship in targets)
    assert all(ship["t_end"] < BUSY_WATER_DURATION_S for ship in targets)


def test_stress_scenario_is_seeded_and_matches_committed_yaml() -> None:
    generated = build_busy_water_document("stress")
    committed = yaml.safe_load(Path("scenarios/romsdal_busy_water_80_stress.yaml").read_text(encoding="utf-8"))

    assert generated == committed
    assert len(generated["ship_list"]) == 80
    assert generated != build_busy_water_document("stress", seed=20250732)
    assert generated["t_end"] == BUSY_WATER_DURATION_S


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
    empty = build_busy_water_document("acceptance", target_count=0)
    assert preflight_document(empty)["target_count"] == 0
    with pytest.raises(ValueError, match="target_count"):
        build_busy_water_document("acceptance", target_count=-1)


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


def test_single_pass_normalization_recomputes_manual_target_exit_time() -> None:
    document = build_busy_water_document("acceptance", target_count=1, seed=17)
    target = document["ship_list"][1]
    target["csog_state"] = [6_956_500.0, 39_800.0, 5.0, 0.0]
    target["waypoints"] = [[6_956_500.0, 6_957_000.0], [39_800.0, 39_800.0]]
    target["t_start"] = 20.0
    target["t_end"] = BUSY_WATER_DURATION_S

    normalized = normalize_single_pass_document(document)

    assert normalized["ship_list"][1]["t_end"] == pytest.approx(120.0)
    assert document["ship_list"][1]["t_end"] == BUSY_WATER_DURATION_S


def test_busy_water_generate_rejects_invalid_count() -> None:
    with TestClient(gui_main.app) as client:
        response = client.get("/api/busy-water/generate", params={"target_count": 80})

    assert response.status_code == 422


def test_busy_water_coordinate_conversion_round_trip() -> None:
    with TestClient(gui_main.app) as client:
        geographic = client.get(
            "/api/coordinates/to-wgs84",
            params={"north": 6_956_650.0, "east": 39_800.0, "utm_zone": 33},
        )
        assert geographic.status_code == 200
        projected = client.get(
            "/api/coordinates/to-utm",
            params={**geographic.json(), "utm_zone": 33},
        )

    assert projected.status_code == 200
    assert projected.json()["north"] == pytest.approx(6_956_650.0, abs=0.01)
    assert projected.json()["east"] == pytest.approx(39_800.0, abs=0.01)


def test_busy_water_draft_preserves_unknown_role(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gui_main, "DRAFT_DIR", tmp_path)
    document = build_busy_water_document("acceptance", target_count=1, seed=17)
    document["ship_list"][1]["encounter_role"] = "unknown"
    with TestClient(gui_main.app) as client:
        saved = client.post(
            "/api/busy-water/drafts",
            json={
                "name": "Current Multiship",
                "base_scenario_id": "romsdal_busy_water_16",
                "seed": 17,
                "document": document,
            },
        )
        assert saved.status_code == 200, saved.json()
        loaded = client.get("/api/busy-water/drafts/current-multiship")

    assert loaded.status_code == 200
    assert loaded.json()["document"]["ship_list"][1]["encounter_role"] == "unknown"


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
