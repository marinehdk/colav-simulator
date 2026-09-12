"""Replay window/events/static-context API (ticket #71, Seam A).

Builds real Decision Trace evidence with the shared TraceSink and asserts the
external read-path behavior required for direct paused seek: bounded versioned
frame windows with an explicit predecessor/successor bracket, direct late seek
without sequential scan through earlier simulation time, canonical event
reads, static chart context, typed rejections, Run-ID confinement and the
no-simulator-runtime import boundary.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from colav_simulator.decision_replay.sink import TraceSink, TraceSinkPolicy
from gui_server.replay import (
    MAX_WINDOW_FRAMES,
    MAX_WINDOW_SPAN_S,
    RUNS_ROOT_ENV,
    RunReplayStore,
    build_replay_router,
)

RUN_WINDOW = "11111111-1111-4111-8111-111111111111"
RUN_DENSE = "12121212-1212-4212-8212-121212121212"
RUN_REDUCED = "22222222-2222-4222-8222-222222222222"
RUN_TAMPER = "32323232-3232-4232-8232-323232323232"
RUN_CRASH = "42424242-4242-4242-8442-424242424242"
RUN_UNKNOWN = "00000000-0000-0000-0000-000000000000"

DT = 0.1
TICKS = 400  # 400 sealed ticks -> 40.0 s of recorded simulation time


@dataclass
class FakeSnapshot:
    sequence: int
    sim_time: float
    state: Any = None
    step_time_ms: float = 1.0
    payload: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)


def frame_payload(sequence: int) -> dict[str, Any]:
    """Deterministic stand-in for one raw simulator frame."""
    return {
        "Ship0": {
            "id": 0,
            "mmsi": 100 + sequence,
            "state": [100.0 * sequence, -50.0 * sequence, 0.2, 2.0, 0.0, 0.01],
            "csog_state": [100.0 * sequence, -50.0 * sequence, 2.2, 0.21],
            "waypoints": [[0.0, 500.0], [900.0, 900.0]],
            "references": [0.0, 0.0, 0.19, 2.1],
            "colav": {
                "planner": {
                    "algorithm_id": "vo",
                    "solve_id": sequence,
                    "solver_executed": sequence % 10 == 0,
                    "status": "OK",
                }
            },
        },
        "Ship1": {
            "id": 1,
            "mmsi": 200,
            "state": [30.0 * sequence, 70.0 * sequence, 1.2, 1.0, 0.1, 0.0],
            "csog_state": [30.0 * sequence, 70.0 * sequence, 1.4, 1.21],
            "active": True,
        },
    }


def append_frame(sink: TraceSink, sequence: int, dt: float = DT) -> None:
    sink.append(
        FakeSnapshot(
            sequence=sequence,
            sim_time=dt * sequence,
            state="RUNNING",
            step_time_ms=5.0 + sequence % 3,
            payload=frame_payload(sequence),
            events=(
                [{"type": "planner_solved", "sim_time": DT * sequence, "details": {"solve_id": sequence}}]
                if sequence % 10 == 0
                else []
            ),
        )
    )


def record_window_trace(run_dir: Path, *, ticks: int = TICKS, dt: float = DT) -> None:  # noqa: FURB110
    # Deterministic capture for reader tests: one synchronous worker, no
    # bounded-queue timing dependence (a real gap is a typed state, not a
    # test flake — see test_window_rejects_evidence_that_is_not_seekable).
    sink = TraceSink.open(run_dir, policy=TraceSinkPolicy(max_queue_records=MAX_WINDOW_FRAMES + 600, worker=False))
    for sequence in range(1, ticks + 1):
        append_frame(sink, sequence, dt=dt)
    sink.close(
        events=[
            {"type": "session_started", "sim_time": dt, "details": {}},
            {"type": "threat_schedule_update", "sim_time": dt * 10, "details": {"target_id": 1}},
            {"type": "collision", "sim_time": dt * ticks, "details": {}},
        ]
    )


def write_manifest(run_dir: Path, *, created_at: str = "2026-09-11T12:00:00Z", state: str = "FINISHED") -> None:
    manifest = {
        "run_id": run_dir.name,
        "created_at_utc": created_at,
        "state": state,
        "requested_algorithm": "vo",
        "executed_algorithm": "vo",
        "requested_tracker": "god",
        "executed_tracker": "god",
        "spec": {"scenario_id": "head_on", "validation_rule_id": "rule14"},
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def write_static_context(run_dir: Path) -> None:
    """Capture-side persisted static chart context (written by the product path)."""
    (run_dir / "static_context.json").write_text(
        json.dumps(
            {
                "schema_version": "colav.run-replay.static-context@1",
                "scenario_id": "head_on",
                "enc": {
                    "origin_east_m": 39500.0,
                    "origin_north_m": 6957500.0,
                    "width_m": 4000.0,
                    "height_m": 6000.0,
                    "utm_zone": 32,
                },
                "enc_navigation_area": {
                    "schema_version": "1.0",
                    "coordinate_frame": "local_north_east_m",
                    "safe_water": {"type": "MultiPolygon", "polygons": [[[0.0, 0.0], [10.0, 0.0], [10.0, 10.0]]]},
                },
                "ships": [
                    {"id": 0, "mmsi": 100, "length_m": 45.0, "width_m": 8.0},
                    {"id": 1, "mmsi": 200, "length_m": 30.0, "width_m": 6.0},
                ],
            }
        ),
        encoding="utf-8",
    )


def make_window_run(root: Path, name: str, *, ticks: int = TICKS, context: bool = True, enc_png: bool = True) -> Path:
    run_dir = root / name
    run_dir.mkdir(parents=True)
    write_manifest(run_dir)
    record_window_trace(run_dir, ticks=ticks)
    if context:
        write_static_context(run_dir)
    if enc_png:
        (run_dir / "enc.png").write_bytes(b"png-bytes")
    return run_dir


@pytest.fixture()
def runs_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "runs"
    root.mkdir()
    monkeypatch.setenv(RUNS_ROOT_ENV, str(root))
    return root


@pytest.fixture()
def api_client(runs_root: Path) -> TestClient:
    make_window_run(runs_root, RUN_WINDOW)
    app = FastAPI()
    app.include_router(build_replay_router(RunReplayStore(runs_root)))
    return TestClient(app)


# ---------------------------------------------------------------------------
# Bounded window with explicit bracket
# ---------------------------------------------------------------------------


def test_window_returns_stored_frames_verbatim_with_bracket(api_client: TestClient) -> None:
    response = api_client.get(f"/api/runs/{RUN_WINDOW}/replay/window", params={"from": 2.0, "to": 2.5})
    assert response.status_code == 200
    document = response.json()
    assert document["schema_version"] == "colav.run-replay.window@1"
    assert document["run_id"] == RUN_WINDOW
    assert document["requested"] == {"from_s": 2.0, "to_s": 2.5}
    times = [frame["sim_time"] for frame in document["frames"]]
    assert times == pytest.approx([2.0, 2.1, 2.2, 2.3, 2.4, 2.5])
    # Stored source records pass through verbatim (sealed evidence, no rewrite).
    first = document["frames"][0]
    assert first["sequence"] == 20
    assert first["state"] == "RUNNING"
    assert first["step_time_ms"] == 5.0 + 20 % 3
    assert first["payload"]["Ship0"]["mmsi"] == 100 + 20
    assert first["payload"]["Ship0"]["colav"]["planner"]["solve_id"] == 20
    assert first["events"][0]["type"] == "planner_solved"
    assert document["frames"][1]["events"] == []
    # Explicit predecessor/successor bracket at the window boundaries.
    assert document["before"]["sim_time"] == pytest.approx(1.9)
    assert document["before"]["sequence"] == 19
    assert document["after"]["sim_time"] == pytest.approx(2.6)
    assert document["after"]["sequence"] == 26


def test_window_at_trace_boundaries_has_null_bracket_frames(api_client: TestClient) -> None:
    start = api_client.get(f"/api/runs/{RUN_WINDOW}/replay/window", params={"from": 0.0, "to": 0.2})
    assert start.status_code == 200
    document = start.json()
    assert [frame["sim_time"] for frame in document["frames"]] == pytest.approx([0.1, 0.2])
    assert document["before"] is None
    assert document["after"]["sim_time"] == pytest.approx(0.3)

    end = api_client.get(f"/api/runs/{RUN_WINDOW}/replay/window", params={"from": 39.9, "to": 40.0})
    assert end.status_code == 200
    document = end.json()
    assert [frame["sim_time"] for frame in document["frames"]] == pytest.approx([39.9, 40.0])
    assert document["before"]["sim_time"] == pytest.approx(39.8)
    assert document["after"] is None


# ---------------------------------------------------------------------------
# Direct late seek (never sequential from zero)
# ---------------------------------------------------------------------------


def test_late_direct_seek_returns_only_the_requested_neighborhood(api_client: TestClient) -> None:
    response = api_client.get(f"/api/runs/{RUN_WINDOW}/replay/window", params={"from": 39.0, "to": 39.2})
    assert response.status_code == 200
    document = response.json()
    returned_times = [frame["sim_time"] for frame in document["frames"]]
    assert returned_times == pytest.approx([39.0, 39.1, 39.2])
    all_times = returned_times + [document["before"]["sim_time"], document["after"]["sim_time"]]
    assert min(all_times) >= 38.9, "late seek must not drag frames from simulation time zero"
    assert len(all_times) == 5


# ---------------------------------------------------------------------------
# Typed rejections
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("params", "reason"),
    [
        ({"from": 3.0, "to": 2.0}, "REPLAY_RANGE_INVALID"),
        ({"from": -0.5, "to": 2.0}, "REPLAY_RANGE_INVALID"),
        ({"from": float("nan"), "to": 2.0}, "REPLAY_RANGE_INVALID"),
        ({"from": 0.0, "to": float("inf")}, "REPLAY_RANGE_INVALID"),
        ({"from": 0.0, "to": MAX_WINDOW_SPAN_S + 1.0}, "REPLAY_WINDOW_TOO_LARGE"),
    ],
)
def test_window_rejects_invalid_ranges_with_typed_errors(api_client: TestClient, params: dict, reason: str) -> None:
    response = api_client.get(f"/api/runs/{RUN_WINDOW}/replay/window", params=params)
    assert response.status_code == 422
    assert response.json()["detail"]["reason"] == reason


def test_window_rejects_missing_range_parameters(api_client: TestClient) -> None:
    assert api_client.get(f"/api/runs/{RUN_WINDOW}/replay/window").status_code == 422
    assert api_client.get(f"/api/runs/{RUN_WINDOW}/replay/window", params={"from": 1.0}).status_code == 422


def test_window_rejects_unknown_run_id_with_typed_error(api_client: TestClient) -> None:
    response = api_client.get(f"/api/runs/{RUN_UNKNOWN}/replay/window", params={"from": 0.0, "to": 1.0})
    assert response.status_code == 404
    assert response.json()["detail"]["reason"] == "RUN_NOT_FOUND"
    malformed = api_client.get("/api/runs/not-a-uuid/replay/window", params={"from": 0.0, "to": 1.0})
    assert malformed.status_code == 404
    assert malformed.json()["detail"]["reason"] == "RUN_ID_INVALID"
    traversal = api_client.get("/api/runs/..%2F..%2Fsecret/replay/window", params={"from": 0.0, "to": 1.0})
    assert traversal.status_code == 404, "path syntax must never reach the store"


def test_window_rejects_evidence_that_is_not_seekable(runs_root: Path) -> None:
    reduced = runs_root / RUN_REDUCED
    reduced.mkdir()
    write_manifest(reduced)
    (reduced / "trajectory.parquet").write_bytes(b"parquet-bytes")

    tampered = make_window_run(runs_root, RUN_TAMPER, context=False, enc_png=False)
    frames_path = tampered / "decision" / "frames.jsonl.gz"
    blob = bytearray(frames_path.read_bytes())
    blob[-20] ^= 0xFF
    frames_path.write_bytes(bytes(blob))

    crash = runs_root / RUN_CRASH
    crash.mkdir()
    write_manifest(crash)
    sink = TraceSink.open(crash, policy=TraceSinkPolicy(max_queue_records=16, worker=False))
    for sequence in range(1, 6):
        append_frame(sink, sequence)
    # No close(): a crash leaves the plain prefix without a finalized index.

    app = FastAPI()
    app.include_router(build_replay_router(RunReplayStore(runs_root)))
    client = TestClient(app)

    reduced_response = client.get(f"/api/runs/{RUN_REDUCED}/replay/window", params={"from": 0.0, "to": 1.0})
    assert reduced_response.status_code == 409
    assert reduced_response.json()["detail"]["reason"] == "REDUCED_TRAJECTORY_ONLY"

    tampered_response = client.get(f"/api/runs/{RUN_TAMPER}/replay/window", params={"from": 0.0, "to": 1.0})
    assert tampered_response.status_code == 409
    assert tampered_response.json()["detail"]["reason"] == "TRACE_DIGEST_MISMATCH"

    crash_response = client.get(f"/api/runs/{RUN_CRASH}/replay/window", params={"from": 0.0, "to": 1.0})
    assert crash_response.status_code == 409
    assert crash_response.json()["detail"]["reason"] == "TRACE_TRUNCATED"


def test_window_rejects_frames_beyond_the_frozen_count_cap(runs_root: Path) -> None:
    dense = runs_root / RUN_DENSE
    dense.mkdir()
    write_manifest(dense)
    record_window_trace(dense, ticks=MAX_WINDOW_FRAMES + 500, dt=0.01)
    app = FastAPI()
    app.include_router(build_replay_router(RunReplayStore(runs_root)))
    client = TestClient(app)
    span = 0.01 * (MAX_WINDOW_FRAMES + 400)
    response = client.get(f"/api/runs/{RUN_DENSE}/replay/window", params={"from": 0.0, "to": span})
    assert response.status_code == 422
    assert response.json()["detail"]["reason"] == "REPLAY_WINDOW_TOO_LARGE"


# ---------------------------------------------------------------------------
# Canonical events
# ---------------------------------------------------------------------------


def test_events_preserve_recorded_identity_order_and_details(api_client: TestClient) -> None:
    response = api_client.get(f"/api/runs/{RUN_WINDOW}/replay/events")
    assert response.status_code == 200
    document = response.json()
    assert document["schema_version"] == "colav.run-replay.events@1"
    assert document["run_id"] == RUN_WINDOW
    assert document["count"] == 3
    assert document["truncated"] is False
    assert [event["type"] for event in document["events"]] == [
        "session_started",
        "threat_schedule_update",
        "collision",
    ]
    assert document["events"][1]["details"] == {"target_id": 1}
    assert document["events"][1]["sim_time"] == pytest.approx(1.0)
    # Repeated reads are semantically identical.
    assert api_client.get(f"/api/runs/{RUN_WINDOW}/replay/events").json() == document


def test_events_are_bounded_by_limit_and_report_truncation(api_client: TestClient) -> None:
    response = api_client.get(f"/api/runs/{RUN_WINDOW}/replay/events", params={"limit": 2})
    assert response.status_code == 200
    document = response.json()
    assert document["count"] == 3
    assert len(document["events"]) == 2
    assert document["truncated"] is True


def test_events_read_the_gzipped_product_journal(api_client: TestClient, runs_root: Path) -> None:
    """Product capture stores events.jsonl.gz (#70); the endpoint reads it unmodified."""
    gz_run = runs_root / "61616161-6161-4616-8161-616161616161"
    gz_run.mkdir()
    write_manifest(gz_run)
    sink = TraceSink.open(gz_run, policy=TraceSinkPolicy(max_queue_records=32, worker=False, events_gzip=True))
    for sequence in range(1, 6):
        append_frame(sink, sequence)
    sink.close(events=[{"type": "session_started", "sim_time": 0.1, "details": {}}])
    assert (gz_run / "decision" / "events.jsonl.gz").is_file()

    app = FastAPI()
    app.include_router(build_replay_router(RunReplayStore(runs_root)))
    client = TestClient(app)
    document = client.get(f"/api/runs/{gz_run.name}/replay/events").json()
    assert document["count"] == 1
    assert document["events"][0]["type"] == "session_started"


def test_events_reject_unknown_run_and_non_seekable_evidence(api_client: TestClient, runs_root: Path) -> None:
    assert api_client.get(f"/api/runs/{RUN_UNKNOWN}/replay/events").status_code == 404
    reduced = runs_root / RUN_REDUCED
    reduced.mkdir()
    write_manifest(reduced)
    (reduced / "trajectory.parquet").write_bytes(b"parquet-bytes")
    response = api_client.get(f"/api/runs/{RUN_REDUCED}/replay/events")
    assert response.status_code == 409
    assert response.json()["detail"]["reason"] == "REDUCED_TRAJECTORY_ONLY"


# ---------------------------------------------------------------------------
# Static chart context + ENC raster
# ---------------------------------------------------------------------------


def test_static_context_projects_persisted_capture_context(api_client: TestClient) -> None:
    response = api_client.get(f"/api/runs/{RUN_WINDOW}/replay/context")
    assert response.status_code == 200
    document = response.json()
    assert document["schema_version"] == "colav.run-replay.context@1"
    assert document["run_id"] == RUN_WINDOW
    assert document["scenario_id"] == "head_on"
    assert document["enc"]["origin_east_m"] == 39500.0
    assert document["enc"]["utm_zone"] == 32
    assert document["enc"]["image_url"] == f"/api/runs/{RUN_WINDOW}/replay/enc.png"
    assert document["enc_navigation_area"]["safe_water"]["type"] == "MultiPolygon"
    assert document["ships"][0] == {"id": 0, "mmsi": 100, "length_m": 45.0, "width_m": 8.0}


def test_static_context_degrades_to_episode_facts_for_legacy_runs(runs_root: Path) -> None:
    legacy = runs_root / "89898989-9898-4898-9898-989898989898"
    legacy.mkdir()
    write_manifest(legacy)
    (legacy / "episode.json").write_text(
        json.dumps(
            {
                "config": {
                    "map_origin_enu": [39500.0, 6957500.0],
                    "map_size": [4000.0, 6000.0],
                    "utm_zone": 32,
                    "ship_list": [{"id": 0, "mmsi": 100}, {"id": 1, "mmsi": 200}],
                }
            }
        ),
        encoding="utf-8",
    )
    app = FastAPI()
    app.include_router(build_replay_router(RunReplayStore(runs_root)))
    client = TestClient(app)
    document = client.get(f"/api/runs/{legacy.name}/replay/context").json()
    assert document["enc"]["origin_east_m"] == 39500.0
    assert document["enc"]["origin_north_m"] == 6957500.0
    assert document["enc_navigation_area"] is None
    assert document["ships"][0]["length_m"] is None
    assert document["enc"]["image_url"] is None


def test_enc_raster_is_served_confined_per_run(api_client: TestClient, runs_root: Path) -> None:
    response = api_client.get(f"/api/runs/{RUN_WINDOW}/replay/enc.png")
    assert response.status_code == 200
    assert response.content == b"png-bytes"
    bare = runs_root / "70707070-0707-4707-8707-070707070707"
    bare.mkdir()
    write_manifest(bare)
    record_window_trace(bare, ticks=3)
    missing = api_client.get(f"/api/runs/{bare.name}/replay/enc.png")
    assert missing.status_code == 404


# ---------------------------------------------------------------------------
# Read-only surface + structural import boundary
# ---------------------------------------------------------------------------


def test_replay_routes_are_get_only(runs_root: Path) -> None:
    router = build_replay_router(RunReplayStore(runs_root))
    replay_routes = [route for route in router.routes if "replay" in str(getattr(route, "path", ""))]
    assert replay_routes, "replay routes must exist"
    for route in replay_routes:
        assert set(route.methods) <= {"GET"}, "replay state is never mutated over HTTP"


def test_replay_read_path_never_imports_simulator_runtime(runs_root: Path) -> None:
    probe = (
        "import sys, gui_server.replay, gui_server.canonical_threat; "
        "banned = [name for name in sys.modules if name.startswith("
        "('colav_simulator.simulator', 'colav_simulator.core', 'colav_simulator.evaluation', "
        "'colav_simulator.experiment.session', 'colav_simulator.experiment.runner', 'gui_server.main'))]; "
        "print(banned); sys.exit(1 if banned else 0)"
    )
    result = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, check=False)
    assert result.returncode == 0, f"read path imported simulator runtime: {result.stdout}{result.stderr}"
