from fastapi.testclient import TestClient

from gui_server.main import _canonical_threat_projection, app


def test_backend_projection_preserves_canonical_snapshot_schedule_conflicts_and_unavailable_reason() -> None:
    snapshot = {"semantic_hash": "snapshot-1", "vectors": [{"key": {"target_id": 2, "generation": 1}}]}
    candidate = {
        "status": "AVAILABLE",
        "snapshot": snapshot,
        "schedule": {"current_primary": {"target_id": 2, "generation": 1}},
        "conflicts": {"edges": [{"type": "DIRECT_WINDOW_OVERLAP"}]},
        "unavailable_reason": None,
    }

    projected = _canonical_threat_projection({}, {"threat_management": candidate})

    assert projected["status"] == "AVAILABLE"
    assert projected["snapshot"] == snapshot
    assert projected["vectors"] == snapshot["vectors"]
    assert projected["schedule"] == candidate["schedule"]
    assert projected["conflicts"] == candidate["conflicts"]
    assert projected["unavailable_reason"] is None
    assert _canonical_threat_projection({}, {"algorithm_details": {"threat_management": candidate}}) == projected


def test_legacy_session_exposes_typed_threat_unavailable_over_rest_and_websocket() -> None:
    with TestClient(app) as client:
        created = client.post(
            "/api/sessions",
            json={
                "scenario_id": "paper_ccta2023_multiship",
                "validation_rule_id": "multiship",
                "algorithm_id": "vo",
                "tracker_id": "god",
                "t_end": 0.2,
            },
        )
        assert created.status_code == 200, created.json()
        session_id = created.json()["session_id"]
        rest = client.post(f"/api/sessions/{session_id}/step")
        assert rest.status_code == 200, rest.json()
        with client.websocket_connect(f"/ws/sessions/{session_id}") as websocket:
            streamed = websocket.receive_json()

    for payload in (rest.json(), streamed):
        threat = payload["threat_management"]
        assert threat["schema_version"] == "colav.threat-management.projection@1"
        assert threat["status"] == "UNAVAILABLE"
        assert threat["snapshot"] is None
        assert threat["vectors"] == []
        assert threat["schedule"] is None
        assert threat["conflicts"] is None
        assert threat["unavailable_reason"] == "THREAT_SNAPSHOT_UNAVAILABLE"
        assert payload["primary_encounter"] is None
        assert payload["dcpa"] is None
        assert payload["tcpa"] is None
        assert payload["colregs"] is None
