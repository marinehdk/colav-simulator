"""Run Evidence/Results document (ticket #74, Seam A).

`GET /api/runs/{run_id}/replay/evidence` is the backend-owned projection
powering the Evaluation Results and Evidence local views: manifest identity,
result readiness (Original Evaluation surfaced read-only), replay
classification, artifact/digest identities and typed limitations. The browser
never parses raw files; missing evidence degrades truthfully.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from gui_server.replay import RunReplayStore, build_replay_router
from test_replay_window import RUN_REDUCED, RUN_WINDOW, api_client, make_window_run, runs_root  # noqa: F401


def _make_legacy_run_with_result(root: Path, name: str) -> Path:
    """A legacy Run: reduced trajectory + evaluation result, no full trace."""
    run_dir = root / name
    run_dir.mkdir(parents=True)
    manifest = {
        "run_id": name,
        "created_at_utc": "2026-08-01T00:00:00Z",
        "state": "FINISHED",
        "requested_algorithm": "vo",
        "executed_algorithm": "vo",
        "requested_tracker": "god",
        "executed_tracker": "god",
        "spec": {"scenario_id": "head_on", "validation_rule_id": "rule14"},
        "spec_hash": "deadbeef" * 8,
        "scenario_hash": "cafe1111" * 8,
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (run_dir / "trajectory.parquet").write_bytes(b"parquet-bytes")
    (run_dir / "enc.png").write_bytes(b"png")
    evaluation = {
        "schema_version": "colav.evaluation@1",
        "evaluation_status": "COMPLETED",
        "hard_gate": {"verdict": "PASS"},
        "evaluator_id": "ccta_2023_demo-v1",
        "reproduction_status": "NOT_RUN",
    }
    (run_dir / "evaluation.json").write_text(json.dumps(evaluation), encoding="utf-8")
    return run_dir


def test_evidence_reports_reduced_truthfully_with_result_facts(
    runs_root: Path,  # noqa: F811
) -> None:
    make_window_run(runs_root, RUN_REDUCED, context=False)
    run_dir = runs_root / RUN_REDUCED
    # Strip the full trace: a legacy reduced run.
    for path in (run_dir / "decision").iterdir():
        path.unlink()
    (run_dir / "decision").rmdir()
    (run_dir / "trajectory.parquet").write_bytes(b"parquet-bytes")
    manifest = {
        "run_id": RUN_REDUCED,
        "created_at_utc": "2026-08-01T00:00:00Z",
        "state": "FINISHED",
        "requested_algorithm": "vo",
        "executed_algorithm": "vo",
        "requested_tracker": "god",
        "executed_tracker": "god",
        "spec": {"scenario_id": "head_on", "validation_rule_id": "rule14"},
        "spec_hash": "deadbeef" * 8,
        "scenario_hash": "cafe1111" * 8,
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    evaluation = {
        "schema_version": "colav.evaluation@1",
        "evaluation_status": "COMPLETED",
        "hard_gate": {"verdict": "FAIL"},
        "evaluator_id": "ccta_2023_demo-v1",
    }
    (run_dir / "evaluation.json").write_text(json.dumps(evaluation), encoding="utf-8")

    from fastapi import FastAPI

    from gui_server.replay import RunReplayStore, build_replay_router

    app = FastAPI()
    app.include_router(build_replay_router(RunReplayStore(runs_root)))
    client = TestClient(app)

    response = client.get(f"/api/runs/{RUN_REDUCED}/replay/evidence")
    assert response.status_code == 200
    document = response.json()
    assert document["schema_version"] == "colav.run-replay.evidence@1"
    assert document["evidence"]["replay"]["state"] == "REDUCED"
    assert "REDUCED_TRAJECTORY_ONLY" in document["limitations"]
    assert "RESULT_PENDING" not in document["limitations"]
    assert document["result"]["result_ready"] is True
    assert document["result"]["evaluation_status"] == "COMPLETED"
    assert document["result"]["hard_gate"] == {"verdict": "FAIL"}
    assert document["evidence"]["trajectory_present"] is True
    assert document["run"]["scenario_id"] == "head_on"
    assert document["evidence"]["digests"]["spec_hash"] == "deadbeef" * 8


def test_evidence_reports_ready_replay_and_pending_result(
    api_client: TestClient,  # noqa: F811
) -> None:
    response = api_client.get(f"/api/runs/{RUN_WINDOW}/replay/evidence")
    assert response.status_code == 200
    document = response.json()
    assert document["evidence"]["replay"]["state"] == "READY"
    assert document["evidence"]["replay"]["frames_sha256"]
    assert "RESULT_PENDING" in document["limitations"]
    assert document["result"]["result_ready"] is False
    assert document["run"]["executed_algorithm"] == "vo"


def test_evidence_rejects_unknown_and_malformed_run_ids(
    api_client: TestClient,  # noqa: F811
) -> None:
    assert api_client.get("/api/runs/00000000-0000-0000-0000-000000000000/replay/evidence").status_code == 404
    for bad in ("..%2f..%2fetc", "not-a-uuid", ""):
        assert api_client.get(f"/api/runs/{bad}/replay/evidence").status_code in (400, 404)
