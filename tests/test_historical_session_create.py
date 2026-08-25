"""Config → Deployment session creation for the Historical AIS scene.

ADR-0004: selecting the Historical AIS scene through POST /api/sessions builds
a Counterfactual Active Session (ordinary WebSessionManager hosting, ordinary
telemetry/playback).  Fail-closed source binding and product tuple policy are
asserted without the real archive; the end-to-end create/advance path runs only
when the user-provided HAIS archive is bound.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from gui_server.main import app

HISTORICAL_AIS_SCENE_ID = "hais_romsdal_20260701_120000_120100"


def test_hais_scene_listed_with_source_presence_gate(monkeypatch) -> None:
    monkeypatch.delenv("COLAV_HAIS_ARCHIVE_PATH", raising=False)
    with TestClient(app) as client:
        scenarios = client.get("/api/scenarios").json()
        catalog = client.get("/api/capabilities", params={"validation_rule_id": "multiship"}).json()

    entry = next(item for item in scenarios if item["id"] == HISTORICAL_AIS_SCENE_ID)
    assert entry["supported_rules"] == ["multiship"]
    assert entry["readiness_grade"] == "G2"
    assert entry["ships"] == 3
    assert entry["historical_ais"]["t0_utc"] == "2026-07-01T12:00:30+00:00"
    # Without the archive binding the scene stays listed but not selectable.
    assert entry["selectable"] is False
    assert "COLAV_HAIS_ARCHIVE_PATH" in (entry["incompatibility_reason"] or "")

    catalog_entry = next(
        item for item in catalog["scenarios"] if item["id"] == HISTORICAL_AIS_SCENE_ID
    )
    assert catalog_entry["supported_rules"] == ["multiship"]
    experimental = {
        (item["algorithm_id"], item["tracker_id"])
        for item in catalog["experimental_combinations"]
        if item["scenario_id"] == HISTORICAL_AIS_SCENE_ID
    }
    assert experimental == {("vo", "god"), ("potocnik_colreg_fan_mpc", "god"), ("mid_mpc_ipopt", "god")}


def test_hais_session_create_fails_closed_without_source(monkeypatch) -> None:
    monkeypatch.delenv("COLAV_HAIS_ARCHIVE_PATH", raising=False)
    with TestClient(app) as client:
        response = client.post(
            "/api/sessions",
            json={
                "validation_rule_id": "multiship",
                "scenario_id": HISTORICAL_AIS_SCENE_ID,
                "algorithm_id": "vo",
                "tracker_id": "god",
            },
        )
    assert response.status_code == 422
    assert "COLAV_HAIS_ARCHIVE_PATH" in response.text


def test_hais_session_create_rejects_non_product_algorithm(monkeypatch) -> None:
    monkeypatch.delenv("COLAV_HAIS_ARCHIVE_PATH", raising=False)
    with TestClient(app) as client:
        response = client.post(
            "/api/sessions",
            json={
                "validation_rule_id": "multiship",
                "scenario_id": HISTORICAL_AIS_SCENE_ID,
                "algorithm_id": "nominal",
                "tracker_id": "god",
            },
        )
    assert response.status_code == 422
    assert "not selectable" in response.text or "No product capability tuple" in response.text


def test_hais_session_create_rejects_foreign_rule(monkeypatch) -> None:
    monkeypatch.delenv("COLAV_HAIS_ARCHIVE_PATH", raising=False)
    with TestClient(app) as client:
        response = client.post(
            "/api/sessions",
            json={
                "validation_rule_id": "rule14",
                "scenario_id": HISTORICAL_AIS_SCENE_ID,
                "algorithm_id": "vo",
                "tracker_id": "god",
            },
        )
    assert response.status_code == 422
    assert "rule14" in response.text


def _archive_bound() -> bool:
    raw = os.environ.get("COLAV_HAIS_ARCHIVE_PATH", "").strip()
    return bool(raw) and os.path.isfile(raw)


def test_hais_counterfactual_session_creates_and_advances() -> None:
    """End-to-end Config→Deployment path: ordinary Active Session on AIS actors."""
    if not _archive_bound():
        pytest.skip("real HAIS archive not bound via COLAV_HAIS_ARCHIVE_PATH")
    with TestClient(app) as client:
        created = client.post(
            "/api/sessions",
            json={
                "validation_rule_id": "multiship",
                "scenario_id": HISTORICAL_AIS_SCENE_ID,
                "algorithm_id": "vo",
                "tracker_id": "god",
            },
        )
        assert created.status_code == 200, created.text
        document = created.json()
        assert document["state"] == "CREATED"
        session_id = document["session_id"]
        assert document["spec"]["historical_scenario_id"] == HISTORICAL_AIS_SCENE_ID
        assert document["spec"]["algorithm_id"] == "vo"

        # Deterministic stepping (no background loop race): advance past T0
        # (12:00:30Z, t=30 s) so the selected algorithm takes over ownship.
        for _ in range(35):
            stepped = client.post(f"/api/sessions/{session_id}/step")
            assert stepped.status_code == 200, stepped.text

        current = client.get("/api/sessions/current").json()
        assert current["state"] == "PAUSED"
        assert current["sim_time"] >= 31.0
