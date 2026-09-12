"""Replay playback never re-executes solver work (ticket #72, Seam A).

The solver-execution counter for Mid-MPC is the content-addressed
``artifacts/mid_mpc/`` journal plus the recorded ``solver_executed`` facts.
This suite drives the full read path (descriptor, static context, many
bounded window seeks at presentation-rate-equivalent spans, event reads) and
proves the counter and the sealed evidence are untouched, with the replay
router unable to mutate anything. Isolated from live execution: the runs root
is a temporary directory and no Simulator/Planner is importable here.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from colav_simulator.decision_replay.sink import TraceSink, TraceSinkPolicy
from gui_server.replay import RUNS_ROOT_ENV, RunReplayStore, build_replay_router

RUN_ID = "72727272-7272-4272-8272-727272727272"

DT = 0.1
TICKS = 600  # 60.0 s of recorded simulation time


@dataclass
class FakeSnapshot:
    sequence: int
    sim_time: float
    state: Any = None
    step_time_ms: float = 1.0
    payload: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)


def frame_payload(sequence: int) -> dict[str, Any]:
    return {
        "Ship0": {
            "id": 0,
            "mmsi": 100,
            "state": [2000.0 + sequence, 1000.0 - sequence, 0.2, 2.0, 0.0, 0.01],
            "active": True,
            "colav": {
                "planner": {
                    "algorithm_id": "mid_mpc_ipopt",
                    "solve_id": max(1, sequence // 10),
                    "solver_executed": sequence % 10 == 1,
                    "status": "OK",
                }
            },
        }
    }


def append_frame(sink: TraceSink, sequence: int, dt: float = DT) -> None:
    sink.append(
        FakeSnapshot(
            sequence=sequence,
            sim_time=dt * sequence,
            state="RUNNING",
            payload=frame_payload(sequence),
            events=[],
        )
    )


def record_trace(run_dir: Path) -> None:
    sink = TraceSink.open(run_dir, policy=TraceSinkPolicy(max_queue_records=TICKS + 10, worker=False))
    for sequence in range(1, TICKS + 1):
        append_frame(sink, sequence)
    sink.close(events=[{"type": "session_started", "sim_time": DT, "details": {}}])


def write_manifest(run_dir: Path) -> None:
    manifest = {
        "run_id": run_dir.name,
        "created_at_utc": "2026-09-12T08:00:00Z",
        "state": "FINISHED",
        "requested_algorithm": "mid_mpc_ipopt",
        "executed_algorithm": "mid_mpc_ipopt",
        "requested_tracker": "god",
        "executed_tracker": "god",
        "spec": {"scenario_id": "head_on", "validation_rule_id": "rule14"},
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def write_solver_artifacts(run_dir: Path) -> list[Path]:
    """Content-addressed solver evidence: one artifact per recorded solve."""
    artifact_dir = run_dir / "artifacts" / "mid_mpc"
    artifact_dir.mkdir(parents=True)
    paths = []
    for solve_id in range(1, TICKS // 10 + 1):
        path = artifact_dir / f"{solve_id:064x}.json.gz"
        path.write_bytes(b"solver-artifact-bytes")
        paths.append(path)
    return paths


@pytest.fixture()
def runs_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "runs"
    root.mkdir()
    monkeypatch.setenv(RUNS_ROOT_ENV, str(root))
    return root


@pytest.fixture()
def counted_run(runs_root: Path) -> tuple[Path, list[Path]]:
    run_dir = runs_root / RUN_ID
    run_dir.mkdir()
    write_manifest(run_dir)
    record_trace(run_dir)
    artifacts = write_solver_artifacts(run_dir)
    return run_dir, artifacts


@pytest.fixture()
def api_client(runs_root: Path, counted_run: tuple[Path, list[Path]]) -> TestClient:
    app = FastAPI()
    app.include_router(build_replay_router(RunReplayStore(runs_root)))
    return TestClient(app)


def _solver_counter(run_dir: Path) -> tuple[int, tuple[str, ...]]:
    artifact_dir = run_dir / "artifacts" / "mid_mpc"
    files = sorted(path.name for path in artifact_dir.iterdir())
    return len(files), tuple(files)


def _index_digest(run_dir: Path) -> dict[str, Any]:
    index = json.loads((run_dir / "decision" / "index.json").read_text(encoding="utf-8"))
    return {key: index.get(key) for key in ("tick_count", "t_start", "t_end", "frames_sha256", "truncated")}


def test_playback_reads_leave_the_solver_execution_counter_unchanged(api_client: TestClient, counted_run) -> None:
    run_dir, artifacts = counted_run
    before_count, before_names = _solver_counter(run_dir)
    before_index = _index_digest(run_dir)
    assert before_count == TICKS // 10

    descriptor = api_client.get(f"/api/runs/{RUN_ID}/replay")
    assert descriptor.status_code == 200
    assert descriptor.json()["replay"]["state"] == "READY"

    # A presentation-rate sweep across the whole trace, including repeated
    # seeks and boundary windows — the exact reads playback performs.
    for rate_span in (0.5, 2.0, 8.0, 40.0):
        cursor = 0.0
        while cursor < 60.0:
            window = api_client.get(
                f"/api/runs/{RUN_ID}/replay/window?from={cursor}&to={min(60.0, cursor + rate_span)}"
            )
            assert window.status_code == 200
            cursor += rate_span
    events = api_client.get(f"/api/runs/{RUN_ID}/replay/events")
    assert events.status_code == 200

    after_count, after_names = _solver_counter(run_dir)
    assert (after_count, after_names) == (before_count, before_names)
    assert _index_digest(run_dir) == before_index
    for artifact in artifacts:
        assert artifact.read_bytes() == b"solver-artifact-bytes"


def test_recorded_solver_facts_are_read_verbatim_never_recomputed(api_client: TestClient, counted_run) -> None:
    run_dir, _ = counted_run
    # First window of the trace: solve_id 1, solver_executed only on tick 1.
    window = api_client.get(f"/api/runs/{RUN_ID}/replay/window?from=0.0&to=0.5")
    assert window.status_code == 200
    frames = window.json()["frames"]
    assert len(frames) >= 5
    for frame in frames:
        planner = frame["payload"]["Ship0"]["colav"]["planner"]
        assert planner["algorithm_id"] == "mid_mpc_ipopt"
        assert planner["solve_id"] == max(1, frame["sequence"] // 10)
        assert planner["solver_executed"] == (frame["sequence"] % 10 == 1)


def test_replay_router_stays_read_only_under_playback(api_client: TestClient) -> None:
    for method in ("post", "put", "patch", "delete"):
        response = getattr(api_client, method)(f"/api/runs/{RUN_ID}/replay/window?from=0&to=1")
        assert response.status_code == 405, f"{method.upper()} must not be routable on the replay API"
