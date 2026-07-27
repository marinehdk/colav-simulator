from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from colav_simulator.experiment import ExperimentRunner, RunSpec
from gui_server.main import app


def test_real_session_api_and_websocket() -> None:
    with TestClient(app) as client:
        scenarios = client.get("/api/scenarios")
        assert scenarios.status_code == 200
        assert any(item["id"] == "paper_ccta2023_multiship" for item in scenarios.json())

        created = client.post(
            "/api/sessions",
            json={"scenario_id": "paper_ccta2023_multiship", "t_end": 0.2},
        )
        assert created.status_code == 200
        session_id = created.json()["session_id"]

        first = client.post(f"/api/sessions/{session_id}/step")
        assert first.status_code == 200
        assert first.json()["state"] == "PAUSED"
        assert first.json()["schema_version"] == "1.0"
        assert len(first.json()["obstacles"]) == 3
        assert len(first.json()["truth"]) == 4
        assert first.json()["measurements"] is not None
        assert first.json()["tracks"] is not None
        assert first.json()["tracks"][0]["states"][0][0] < 5000.0

        second = client.post(f"/api/sessions/{session_id}/step")
        assert second.status_code == 200
        assert second.json()["state"] == "FINISHED"

        result = client.get(f"/api/sessions/{session_id}/result")
        assert result.status_code == 200
        assert result.json()["manifest"]["reproduction_status"] == "functional_reproduction"

        artifacts = client.get(f"/api/sessions/{session_id}/artifacts")
        names = {artifact["name"] for artifact in artifacts.json()}
        assert {"enc.png", "manifest.json", "trajectory.parquet", "evaluation.json", "report.html"}.issubset(names)

        with client.websocket_connect(f"/ws/sessions/{session_id}") as websocket:
            telemetry = websocket.receive_json()
            assert telemetry["run_id"] == session_id
            assert telemetry["state"] == "FINISHED"

        replay = client.post(f"/api/sessions/{session_id}/replay")
        assert replay.status_code == 200
        replay_id = replay.json()["session_id"]
        client.post(f"/api/sessions/{replay_id}/step")
        client.post(f"/api/sessions/{replay_id}/step")
        replay_result = client.get(f"/api/sessions/{replay_id}/result")
        assert replay_result.json()["manifest"]["replay_of_run_id"] == session_id
        assert replay_result.json()["manifest"]["replay_verified"] is True


def test_rule14_capability_api_and_combination_validation() -> None:
    with TestClient(app) as client:
        response = client.get("/api/capabilities", params={"validation_rule_id": "rule14"})
        assert response.status_code == 200
        catalog = response.json()
        assert catalog["schema_version"] == "1.0"
        assert catalog["defaults"] == {
            "validation_rule_id": "rule14",
            "scenario_id": "head_on",
            "algorithm_id": "nominal",
            "tracker_id": "god",
        }
        capability_fields = {
            "readiness_grade",
            "dependency_available",
            "runtime_ready",
            "selectable",
            "supported_rules",
            "supported_scenarios",
            "supported_obstacles",
            "verified_combinations",
            "latest_evidence",
            "known_failure",
            "incompatibility_reason",
        }
        for category in ("rules", "scenarios", "algorithms", "trackers"):
            assert all(capability_fields.issubset(item) for item in catalog[category])
        assert next(item for item in catalog["scenarios"] if item["id"] == "head_on")["selectable"] is True
        algorithms = {item["id"]: item for item in catalog["algorithms"]}
        assert {name for name, item in algorithms.items() if item["selectable"]} == {"nominal", "vo", "sbmpc"}
        assert algorithms["psbmpc"]["incompatibility_reason"]
        assert algorithms["rrt"]["incompatibility_reason"]
        assert algorithms["rlmpc"]["incompatibility_reason"]
        trackers = {item["id"]: item for item in catalog["trackers"]}
        assert {name for name, item in trackers.items() if item["selectable"]} == {"god", "kf"}

        rejected = client.post(
            "/api/sessions",
            json={
                "validation_rule_id": "rule14",
                "scenario_id": "paper_ccta2023_head_on",
                "algorithm_id": "nominal",
                "tracker_id": "god",
            },
        )
        assert rejected.status_code == 422
        assert rejected.json()["detail"]["status"] == "INVALID_INPUT"
        assert "not a selectable rule14" in rejected.json()["detail"]["reason"]


def test_rule14_web_telemetry_preserves_latest_real_solve() -> None:
    with TestClient(app) as client:
        created = client.post(
            "/api/sessions",
            json={
                "validation_rule_id": "rule14",
                "scenario_id": "head_on",
                "algorithm_id": "sbmpc",
                "tracker_id": "god",
                "t_end": 6.0,
            },
        )
        assert created.status_code == 200
        session_id = created.json()["session_id"]
        telemetry = None
        for _ in range(12):
            response = client.post(f"/api/sessions/{session_id}/step")
            assert response.status_code == 200
            telemetry = response.json()

        assert telemetry is not None
        assert telemetry["state"] == "FINISHED"
        assert telemetry["selected_rule"] == "rule14"
        assert telemetry["requested_algorithm"] == telemetry["executed_algorithm"] == "sbmpc"
        assert telemetry["requested_tracker"] == telemetry["executed_tracker"] == "god"
        assert telemetry["planner"]["solver_executed"] is False
        assert telemetry["planner"]["solve_id"] == 1
        assert telemetry["latest_planner_solve"]["solver_executed"] is True
        assert telemetry["latest_planner_solve"]["solve_id"] == 1
        assert len(telemetry["plans"]["prediction_horizon"]) == 60
        assert telemetry["encounters"][0]["validation_rule_id"] == "rule14"


def test_rule14_web_and_offline_trajectory_hashes_match(tmp_path: Path) -> None:
    request = {
        "validation_rule_id": "rule14",
        "scenario_id": "head_on",
        "algorithm_id": "nominal",
        "tracker_id": "god",
        "seed": 0,
        "t_end": 1.0,
    }
    with TestClient(app) as client:
        created = client.post("/api/sessions", json=request)
        assert created.status_code == 200, created.json()
        session_id = created.json()["session_id"]
        for _ in range(2):
            telemetry = client.post(f"/api/sessions/{session_id}/step")
            assert telemetry.status_code == 200
        assert telemetry.json()["state"] == "FINISHED"
        web_manifest = client.get(f"/api/sessions/{session_id}/result").json()["manifest"]

    offline = ExperimentRunner().run(
        RunSpec(**request, output_root=str(tmp_path / "offline"))
    )
    assert web_manifest["episode_hash"] == offline.manifest.episode_hash
    assert web_manifest["trajectory_hash"] == offline.manifest.trajectory_hash
