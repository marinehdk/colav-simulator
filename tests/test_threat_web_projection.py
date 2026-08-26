from fastapi.testclient import TestClient

from colav_simulator.core.colav.threat_management import ThreatManagementCoordinator
from colav_simulator.experiment.threat_baseline import BASELINE_EPOCH, baseline_due
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


def test_product_session_exposes_baseline_threat_over_rest_and_websocket() -> None:
    """VO sessions publish the session-owned baseline cycle (ADR-0002), not UNAVAILABLE."""
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
        assert threat["status"] == "AVAILABLE"
        assert threat["snapshot"] is not None
        assert len(threat["vectors"]) == 3
        assert threat["unavailable_reason"] is None
        assert all(
            vector["display_class"] in {"CLEAR", "LOW", "HIGH", "UNKNOWN"}
            and isinstance(vector["avoidance_action_active"], bool)
            for vector in threat["vectors"]
        )
        selection = threat["snapshot"]["lifecycle_snapshot"]["primary_selection_evidence"]
        assert selection["winner"] is not None
        assert selection["winning_class"]
        assert selection["decisive_factor"]
        assert selection["switch_reason"]
        assert isinstance(selection["preempted"], bool)
        # Legacy browser-computed aliases stay inert.
        assert payload["primary_encounter"] is None
        assert payload["dcpa"] is None
        assert payload["tcpa"] is None
        assert payload["colregs"] is None


def test_baseline_due_gate_skips_when_adapter_owns_the_lifecycle() -> None:
    coordinator = ThreatManagementCoordinator()
    assert baseline_due(coordinator, sim_time_s=1.0, dt_s=0.5) is True

    class _AdapterSnapshot:
        epoch = "mid-mpc-0"  # Mid-MPC HOLD ticks leave the snapshot stale on purpose
        sim_time_s = 1.0

    coordinator._last_snapshot = _AdapterSnapshot()  # noqa: SLF001 - gate unit under test
    assert baseline_due(coordinator, sim_time_s=1.5, dt_s=0.5) is False
    assert baseline_due(coordinator, sim_time_s=60.0, dt_s=0.5) is False

    class _BaselineSnapshot:
        epoch = BASELINE_EPOCH
        sim_time_s = 1.0

    coordinator._last_snapshot = _BaselineSnapshot()  # noqa: SLF001
    assert baseline_due(coordinator, sim_time_s=1.5, dt_s=0.5) is False
    assert baseline_due(coordinator, sim_time_s=2.5, dt_s=0.5) is True
