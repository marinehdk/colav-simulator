from __future__ import annotations

import json

from fastapi.testclient import TestClient

from colav_simulator.historical_scenario_catalog import (
    HISTORICAL_AIS_SCENARIO_ID,
    HistoricalAISScenarioCatalog,
    HistoricalAISScenarioReadiness,
)
from gui_server.main import app


def test_catalog_publishes_one_independent_bounded_ais_scene(monkeypatch) -> None:
    monkeypatch.delenv("COLAV_HAIS_ARCHIVE_PATH", raising=False)
    descriptor = HistoricalAISScenarioCatalog().get(HISTORICAL_AIS_SCENARIO_ID)

    assert descriptor.scenario_id == "hais_romsdal_20260701_120000_120100"
    assert descriptor.kind == "HISTORICAL_AIS"
    assert descriptor.modes == ("HISTORICAL_REPLAY", "COUNTERFACTUAL")
    assert descriptor.archive_scope["day_count"] == 23
    assert descriptor.archive_scope["row_count"] == 51_522_509
    assert descriptor.archive_scope["union_mmsi_count"] == 1_226
    assert descriptor.current_window["source_row_count"] == 24
    assert descriptor.current_window["selection_filter_mmsi_count"] == 4
    assert descriptor.current_window["runtime_actor_count"] == 3
    assert descriptor.current_window["target_mmsi"] == [257252000, 258764000]
    assert descriptor.current_window["reference_mmsi"] == 259189000
    assert "CURRENT_WINDOW_ONLY" in descriptor.limitations
    assert "CURRENT_ACTOR_SET_ONLY" in descriptor.limitations
    assert "ARCHIVE_NOT_FULLY_ENC_QUALIFIED" in descriptor.limitations
    assert descriptor.readiness().status is HistoricalAISScenarioReadiness.SOURCE_BINDING_MISSING

    document = descriptor.to_dict()
    assert descriptor.descriptor_sha256 == descriptor.to_dict()["descriptor_sha256"]
    assert "/Users/" not in json.dumps(document)
    assert "Downloads" not in json.dumps(document)


def test_historical_scenario_catalog_api_is_separate_from_legacy_scenarios(monkeypatch) -> None:
    monkeypatch.delenv("COLAV_HAIS_ARCHIVE_PATH", raising=False)
    with TestClient(app) as client:
        scenarios = client.get("/api/historical/scenarios")
        descriptor = client.get(f"/api/historical/scenarios/{HISTORICAL_AIS_SCENARIO_ID}")
        legacy = client.get("/api/scenarios")

    assert scenarios.status_code == 200
    assert [item["id"] for item in scenarios.json()] == [HISTORICAL_AIS_SCENARIO_ID]
    assert descriptor.status_code == 200
    assert descriptor.json()["kind"] == "HISTORICAL_AIS"
    assert descriptor.json()["readiness"]["status"] == "SOURCE_BINDING_MISSING"
    assert HISTORICAL_AIS_SCENARIO_ID not in {item["id"] for item in legacy.json()}


def test_historical_scenario_workflow_creation_fails_closed_without_archive_binding(monkeypatch) -> None:
    monkeypatch.delenv("COLAV_HAIS_ARCHIVE_PATH", raising=False)
    with TestClient(app) as client:
        response = client.post(
            f"/api/historical/scenarios/{HISTORICAL_AIS_SCENARIO_ID}/workflows",
            json={"mode": "HISTORICAL_REPLAY"},
        )

    assert response.status_code == 422
    assert response.json()["detail"]["status"] == "SOURCE_BINDING_MISSING"
