"""Config → Deployment session creation for the Historical AIS scene.

ADR-0004: selecting the Historical AIS scene through POST /api/sessions builds
a Counterfactual Active Session (ordinary WebSessionManager hosting, ordinary
telemetry/playback).  Fail-closed source binding and product tuple policy are
asserted without the real archive; the end-to-end create/advance path runs only
when the user-provided HAIS archive is bound.
"""

from __future__ import annotations

import math
import os

import pytest
from fastapi.testclient import TestClient

from gui_server.main import app

HISTORICAL_AIS_SCENE_ID = "hais_romsdal_20260701_120007_121007"


def test_hais_scene_listed_with_source_presence_gate(monkeypatch) -> None:
    monkeypatch.delenv("COLAV_HAIS_ARCHIVE_PATH", raising=False)
    with TestClient(app) as client:
        scenarios = client.get("/api/scenarios").json()
        catalog = client.get("/api/capabilities", params={"validation_rule_id": "multiship"}).json()

    entry = next(item for item in scenarios if item["id"] == HISTORICAL_AIS_SCENE_ID)
    assert entry["supported_rules"] == ["multiship"]
    assert entry["readiness_grade"] == "G2"
    assert entry["ships"] == 4
    assert entry["historical_ais"]["playback_start_utc"] == "2026-07-01T12:00:07+00:00"
    assert entry["historical_ais"]["duration_s"] == 600
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
    assert experimental == {
        ("vo", "god"),
        ("potocnik_colreg_fan_mpc", "god"),
        ("mid_mpc_ipopt", "god"),
    }


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


def test_hais_session_create_rejects_fallback_enabled(monkeypatch) -> None:
    monkeypatch.delenv("COLAV_HAIS_ARCHIVE_PATH", raising=False)
    with TestClient(app) as client:
        response = client.post(
            "/api/sessions",
            json={
                "validation_rule_id": "multiship",
                "scenario_id": HISTORICAL_AIS_SCENE_ID,
                "algorithm_id": "vo",
                "tracker_id": "god",
                "strict_no_fallback": False,
            },
        )

    assert response.status_code == 422
    assert "Historical AIS sessions require strict_no_fallback=true" in response.text


def test_hais_session_create_allows_mid_mpc_tuple_to_reach_source_gate(monkeypatch) -> None:
    monkeypatch.delenv("COLAV_HAIS_ARCHIVE_PATH", raising=False)
    with TestClient(app) as client:
        response = client.post(
            "/api/sessions",
            json={
                "validation_rule_id": "multiship",
                "scenario_id": HISTORICAL_AIS_SCENE_ID,
                "algorithm_id": "mid_mpc_ipopt",
                "tracker_id": "god",
            },
        )

    assert response.status_code == 422
    assert "COLAV_HAIS_ARCHIVE_PATH" in response.text


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
        actors = document["spec"]["historical_replay"]["actor_set"]["actors"]
        assert [actor["mmsi"] for actor in actors] == [
            259189000,
            257252000,
            258764000,
            259257000,
        ]

        first = client.post(f"/api/sessions/{session_id}/step")
        assert first.status_code == 200, first.text
        first_frame = first.json()
        assert first_frame["sim_time"] == 0.0
        assert first_frame["source_time_s"] == 60.0
        assert first_frame["ais_utc"] == "2026-07-01T12:00:07+00:00"
        assert first_frame["os"]["id"] == 0
        assert first_frame["os"]["mmsi"] == 259189000
        assert first_frame["shadow_ownship"] is None
        assert not any(event["type"] == "algorithm_handoff" for event in first_frame["events"])

        handoff_frame = None
        for _ in range(10):
            stepped = client.post(f"/api/sessions/{session_id}/step")
            assert stepped.status_code == 200, stepped.text
            candidate = stepped.json()
            if any(event["type"] == "algorithm_handoff" for event in candidate["events"]):
                handoff_frame = candidate
                break
        assert handoff_frame is not None
        assert handoff_frame["source_time_s"] == 67.0
        assert len(handoff_frame["waypoints"][0]) == 3
        assert len(handoff_frame["waypoints"][1]) == 3

        shadow = client.post(f"/api/sessions/{session_id}/step")
        assert shadow.status_code == 200, shadow.text
        shadow_frame = shadow.json()
        assert shadow_frame["shadow_ownship"]["label"] == "AIS SHADOW"
        assert shadow_frame["shadow_comparison"]["status"] == "AVAILABLE"
        assert shadow_frame["shadow_comparison"]["deviation_m"] >= 0.0

        # Deterministic stepping (no background loop race): the selected
        # algorithm remains armed while factual traffic advances.
        while shadow_frame["sim_time"] < 35.0:
            stepped = client.post(f"/api/sessions/{session_id}/step")
            assert stepped.status_code == 200, stepped.text
            shadow_frame = stepped.json()

        current = client.get("/api/sessions/current").json()
        assert current["state"] == "PAUSED"
        assert current["sim_time"] >= 35.0
        assert current["source_time_s"] >= 95.0


def test_hais_mid_mpc_first_control_frame_preserves_the_active_handoff_snapshot() -> None:
    """The canonical ACTIVE snapshot reaches Mid-MPC without a second Lifecycle cycle."""
    if not _archive_bound():
        pytest.skip("real HAIS archive not bound via COLAV_HAIS_ARCHIVE_PATH")
    with TestClient(app) as client:
        created = client.post(
            "/api/sessions",
            json={
                "validation_rule_id": "multiship",
                "scenario_id": HISTORICAL_AIS_SCENE_ID,
                "algorithm_id": "mid_mpc_ipopt",
                "tracker_id": "god",
            },
        )
        assert created.status_code == 200, created.text
        session_id = created.json()["session_id"]

        first = client.post(f"/api/sessions/{session_id}/step")
        assert first.status_code == 200, first.text
        assert first.json()["source_time_s"] == 60.0
        assert first.json()["os"]["sog"] > 6.0

        handoff_frame = None
        for _ in range(10):
            stepped = client.post(f"/api/sessions/{session_id}/step")
            assert stepped.status_code == 200, stepped.text
            candidate = stepped.json()
            if any(event["type"] == "algorithm_handoff" for event in candidate["events"]):
                handoff_frame = candidate
                break

        assert handoff_frame is not None
        assert 66.0 <= handoff_frame["source_time_s"] <= 67.0

        controlled = client.post(f"/api/sessions/{session_id}/step")
        assert controlled.status_code == 200, controlled.text
        control_frame = controlled.json()
        planner = control_frame["planner"]
        assert planner["algorithm_id"] == "mid_mpc_ipopt"
        assert planner["solver_executed"] is True
        assert planner["sim_time"] == handoff_frame["source_time_s"] + 1.0
        lifecycle = planner["algorithm_details"]["lifecycle"]
        assert lifecycle["epoch"] == "session-baseline"
        assert any(target["risk"] == "ACTIVE" for target in lifecycle["targets"])
        assert planner["algorithm_details"]["selected_target_ids"]
        applied_course = control_frame["execution"]["applied_course_ref_rad"]
        course_delta = math.atan2(
            math.sin(applied_course - control_frame["os"]["psi"]),
            math.cos(applied_course - control_frame["os"]["psi"]),
        )
        assert abs(course_delta) <= math.radians(3.0) + 1.0e-6
