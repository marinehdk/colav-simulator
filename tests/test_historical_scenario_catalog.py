from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from colav_simulator.historical_scenario_catalog import (
    HISTORICAL_AIS_SCENARIO_ID,
    HistoricalAISScenarioCatalog,
    HistoricalAISScenarioReadiness,
    HistoricalAISScenarioSourceReadiness,
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
    assert descriptor.current_window["target_mmsi"] == (257252000, 258764000)
    assert descriptor.current_window["reference_mmsi"] == 259189000
    assert "CURRENT_WINDOW_ONLY" in descriptor.limitations
    assert "CURRENT_ACTOR_SET_ONLY" in descriptor.limitations
    assert "ARCHIVE_NOT_FULLY_ENC_QUALIFIED" in descriptor.limitations
    assert descriptor.readiness().status is HistoricalAISScenarioReadiness.SOURCE_BINDING_MISSING

    document = descriptor.to_dict()
    assert descriptor.descriptor_sha256 == descriptor.to_dict()["descriptor_sha256"]
    assert "/Users/" not in json.dumps(document)
    assert "Downloads" not in json.dumps(document)


def test_descriptor_is_deeply_immutable_and_separates_capability_evidence() -> None:
    descriptor = HistoricalAISScenarioCatalog().get(HISTORICAL_AIS_SCENARIO_ID)

    assert descriptor.runtime_binding["historical_scenario_id"] == HISTORICAL_AIS_SCENARIO_ID
    assert "paper_ccta2023_multiship" not in json.dumps(descriptor.to_dict()["runtime_binding"])
    evidence = descriptor.algorithm_capability_evidence
    assert evidence["binding_role"] == "ALGORITHM_CAPABILITY_ONLY"
    assert evidence["geometry_equivalence"] is False
    assert evidence["exact_tuple"] == (
        "multiship",
        "paper_ccta2023_multiship",
        "mid_mpc_ipopt",
        "god",
    )

    with pytest.raises(TypeError):
        descriptor.current_window["bbox"][0] = 0.0
    with pytest.raises(TypeError):
        descriptor.dimensions["records"][0]["length_m"] = 1.0
    with pytest.raises(TypeError):
        descriptor.runtime_binding["domain_profile"]["fore_m"] = 1.0


def test_descriptor_digest_covers_nested_facts(tmp_path) -> None:
    original = HistoricalAISScenarioCatalog().get(HISTORICAL_AIS_SCENARIO_ID)
    source = Path(__file__).parents[1] / "colav_simulator" / "data" / "historical_ais_scenarios.json"
    document = json.loads(source.read_text(encoding="utf-8"))
    document["dimensions"]["records"][0]["length_m"] = 84.7
    changed_path = tmp_path / "historical_ais_scenarios.json"
    changed_path.write_text(json.dumps(document), encoding="utf-8")

    changed = HistoricalAISScenarioCatalog(changed_path).get(HISTORICAL_AIS_SCENARIO_ID)

    assert changed.descriptor_sha256 != original.descriptor_sha256


def test_published_presentation_keeps_scene_qualification_and_runtime_separate(monkeypatch) -> None:
    monkeypatch.delenv("COLAV_HAIS_ARCHIVE_PATH", raising=False)
    document = HistoricalAISScenarioCatalog().document(HISTORICAL_AIS_SCENARIO_ID)

    assert document["presentation"]["scenario"] == {
        "id": HISTORICAL_AIS_SCENARIO_ID,
        "kind": "HISTORICAL_AIS",
    }
    assert document["presentation"]["operability"] == {"status": "UNAVAILABLE", "scope": "BOUNDED"}
    assert document["presentation"]["qualification"]["status"] == "NOT_QUALIFIED"
    assert document["presentation"]["runtime"]["modes"] == ["HISTORICAL_REPLAY", "COUNTERFACTUAL"]
    assert document["presentation"]["digests"]["descriptor_sha256"] == document["descriptor_sha256"]
    assert document["presentation"]["digests"]["entry_sha256"] == document["current_window"]["entry_sha256"]


def test_ready_bounded_scene_does_not_claim_predictive_cluster_qualification() -> None:
    descriptor = HistoricalAISScenarioCatalog().get(HISTORICAL_AIS_SCENARIO_ID)
    ready = HistoricalAISScenarioSourceReadiness(
        HistoricalAISScenarioReadiness.READY,
        descriptor.archive_sha256,
        descriptor.archive_sha256,
    )

    presentation = descriptor.presentation(ready)

    assert presentation["operability"] == {"status": "AVAILABLE", "scope": "BOUNDED"}
    assert presentation["qualification"]["status"] == "NOT_QUALIFIED"
    assert presentation["qualification"]["code"] == "THREAT_EVIDENCE_INCOMPLETE"
    assert presentation["qualification"]["source_readiness"] == "READY"
    serialized = json.dumps(descriptor.to_dict())
    assert "expected_cluster_count" not in serialized
    assert "sealed_expected_cluster" not in serialized


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
