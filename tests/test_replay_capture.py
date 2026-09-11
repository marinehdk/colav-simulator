"""Product-path full replay evidence capture (ticket #70).

Seam: product Active Session evidence + the reusable TraceSink extracted from
the debug-only decision replay recorder. Tests assert external behavior: on-disk
evidence, descriptor-visible state, never writer/queue internals.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

import gui_server.main as gui_main
from colav_simulator.decision_replay import probes
from colav_simulator.decision_replay.bundle import TraceBundle
from colav_simulator.decision_replay.sink import TraceSink, TraceSinkPolicy
from colav_simulator.experiment.contracts import RunSpec, SessionState
from gui_server.main import WebSessionManager

TICK_LIMIT = 400
FINALIZE_TIMEOUT_S = 120.0


@dataclass
class FakeSnapshot:
    """Mirror of SessionSnapshot's public fields."""

    sequence: int
    sim_time: float
    state: SessionState = SessionState.RUNNING
    step_time_ms: float = 1.0
    payload: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)


def make_spec(tmp_path: Path, *, t_end: float = 6.0) -> RunSpec:
    return RunSpec(
        scenario_id="head_on",
        validation_rule_id="rule14",
        algorithm_id="vo",
        tracker_id="god",
        seed=4,
        t_end=t_end,
        output_root=str(tmp_path),
    )


def run_to_finished(manager: WebSessionManager, *, tick_limit: int = TICK_LIMIT) -> str:
    """Drive the session from the backend only: no browser/WebSocket exists."""
    session_id = manager.session_id
    assert session_id
    manager.start(session_id)
    ticks = 0
    while manager.tick() is not None:
        ticks += 1
        assert ticks <= tick_limit, "run exceeded tick budget"
    assert manager.prepared is not None
    assert manager.prepared.session.state == SessionState.FINISHED
    return session_id


def wait_for_result(manager: WebSessionManager, *, timeout_s: float = FINALIZE_TIMEOUT_S) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if manager.result is not None:
            return
        time.sleep(0.02)
    raise AssertionError("result generation did not finish in time")


def read_index(run_dir: Path) -> dict[str, Any]:
    return json.loads((run_dir / "decision" / "index.json").read_text(encoding="utf-8"))


def wait_for_file(path: Path, *, timeout_s: float = 30.0) -> None:
    deadline = time.monotonic() + timeout_s
    while not path.exists():
        assert time.monotonic() < deadline, f"{path} never appeared"
        time.sleep(0.05)


# ---------------------------------------------------------------------------
# TraceSink unit behavior (evidence artifact contract)
# ---------------------------------------------------------------------------


def test_sink_close_writes_durable_full_evidence(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-a"
    sink = TraceSink.open(run_dir)
    for sequence in range(1, 4):
        sink.append(
            FakeSnapshot(
                sequence=sequence,
                sim_time=0.1 * sequence,
                payload={"Ship0": {"state": [sequence, 0, 0, 0, 0, 0]}},
                events=[{"type": "session_started", "sim_time": 0.1 * sequence}],
            )
        )
    index = sink.close(events=[{"type": "session_started", "sim_time": 0.1}])

    assert sink.state == "READY"
    assert sink.reason is None
    trace_dir = run_dir / "decision"
    assert (trace_dir / "frames.jsonl.gz").is_file()
    assert not (trace_dir / "frames.jsonl").exists(), "plain frames must not survive close"
    assert (trace_dir / "events.jsonl").is_file()
    assert index["trace_schema"] == "colav.decision-replay.v1"
    assert index["tick_count"] == 3
    assert index["truncated"] is False
    assert index["t_start"] == pytest.approx(0.1)
    assert index["t_end"] == pytest.approx(0.3)
    compressed = (trace_dir / "frames.jsonl.gz").read_bytes()
    assert index["frames_sha256"] == hashlib.sha256(gzip.decompress(compressed)).hexdigest()
    assert hashlib.sha256(compressed).hexdigest() != index["frames_sha256"], "digest covers uncompressed frames"

    bundle = TraceBundle(run_dir)
    assert bundle.evidence_level == "full"
    assert bundle.tick_count == 3
    assert bundle.frame(1)["payload"]["Ship0"]["state"][0] == 1
    assert [event["type"] for event in bundle.events()] == ["session_started"]


def test_sink_close_supports_gzipped_event_journal(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-gz"
    sink = TraceSink.open(run_dir, policy=TraceSinkPolicy(events_gzip=True))
    sink.append(FakeSnapshot(sequence=1, sim_time=0.0, payload={"t": 1}))
    sink.close(events=[{"type": "session_started", "sim_time": 0.0}])

    trace_dir = run_dir / "decision"
    assert (trace_dir / "events.jsonl.gz").is_file()
    assert not (trace_dir / "events.jsonl").exists()
    bundle = TraceBundle(run_dir)
    assert [event["type"] for event in bundle.events()] == ["session_started"]


def test_sink_crash_leaves_readable_prefix_without_index(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-crash"
    sink = TraceSink.open(run_dir)
    sink.append(FakeSnapshot(sequence=1, sim_time=0.1, payload={"t": 1}))
    sink.append(FakeSnapshot(sequence=2, sim_time=0.2, payload={"t": 2}))
    # Simulate hard crash: the process dies without close().

    assert sink.state == "CAPTURING"
    assert (run_dir / "decision" / "frames.jsonl").is_file()
    assert not (run_dir / "decision" / "index.json").exists()


def test_sink_backpressure_is_typed_incomplete_never_silent(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-backpressure"
    sink = TraceSink.open(run_dir, policy=TraceSinkPolicy(max_queue_records=1, worker=False))
    sink.append(FakeSnapshot(sequence=1, sim_time=0.1, payload={"t": 1}))
    sink.append(FakeSnapshot(sequence=2, sim_time=0.2, payload={"t": 2}))  # queue cannot absorb this

    assert sink.state == "INCOMPLETE"
    assert sink.reason == "TRACE_GAP"
    index = sink.close()
    assert index["truncated"] is True
    assert index["incomplete_reason"] == "TRACE_GAP"
    bundle = TraceBundle(run_dir)
    assert bundle.tick_count == 1, "only the durable prefix survives"


def test_sink_byte_budget_is_typed_incomplete(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-budget"
    big_payload = {"blob": "x" * 2048}
    sink = TraceSink.open(run_dir, policy=TraceSinkPolicy(max_total_bytes=4096, worker=False))
    for sequence in range(1, 4):
        sink.append(FakeSnapshot(sequence=sequence, sim_time=0.1 * sequence, payload=dict(big_payload)))

    assert sink.state == "INCOMPLETE"
    assert sink.reason == "TRACE_BUDGET_EXCEEDED"
    index = sink.close()
    assert index["truncated"] is True
    assert index["incomplete_reason"] == "TRACE_BUDGET_EXCEEDED"
    assert index["tick_count"] < 3


def test_sink_index_seal_failure_is_typed_incomplete_and_never_raises(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-index-seal-fail"
    sink = TraceSink.open(run_dir)
    sink.append(FakeSnapshot(sequence=1, sim_time=0.1, payload={"t": 1}))
    # Filesystem-level seal block: index.json cannot be written, no mocks.
    (run_dir / "decision" / "index.json").mkdir()

    index = sink.close()  # must not raise

    assert sink.state == "INCOMPLETE"
    assert sink.reason == "TRACE_WRITE_FAILED"
    assert sink.finalized is True
    assert index == {}
    trace_dir = run_dir / "decision"
    assert (trace_dir / "frames.jsonl.gz").is_file(), "frame evidence survives a failed seal"
    assert not (trace_dir / "frames.jsonl").exists()


def test_sink_fail_records_typed_reason_and_keeps_prefix(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-fail"
    sink = TraceSink.open(run_dir)
    sink.append(FakeSnapshot(sequence=1, sim_time=0.1, payload={"t": 1}))
    sink.fail("EXECUTION_FAILED")
    index = sink.close(events=[{"type": "session_failed", "sim_time": 0.1}])

    assert index["truncated"] is True
    assert index["incomplete_reason"] == "EXECUTION_FAILED"
    bundle = TraceBundle(run_dir)
    assert bundle.tick_count == 1


def test_sink_close_is_idempotent(tmp_path: Path) -> None:
    sink = TraceSink.open(tmp_path / "run-idem")
    sink.append(FakeSnapshot(sequence=1, sim_time=0.1, payload={"t": 1}))
    first = sink.close()
    second = sink.close()
    assert first == second
    assert sink.state == "READY"


# ---------------------------------------------------------------------------
# Product session capture (manager seam, backend-owned, no browser)
# ---------------------------------------------------------------------------


@pytest.fixture()
def manager() -> Any:
    instance = WebSessionManager()
    yield instance
    instance._result_executor.shutdown(wait=True)


@pytest.fixture(scope="module")
def finished_vo_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    """One normal product VO run through the manager with zero consumers."""
    tmp_path = tmp_path_factory.mktemp("replay_capture_vo")
    manager = WebSessionManager()
    try:
        manager.create(make_spec(tmp_path))
        run_to_finished(manager)
        wait_for_result(manager)
        prepared = manager.prepared
        return {"run_dir": prepared.run_dir, "describe": manager.describe()}
    finally:
        manager._result_executor.shutdown(wait=True)


def test_product_run_records_full_trace_without_any_browser(finished_vo_run: dict[str, Any]) -> None:
    run_dir: Path = finished_vo_run["run_dir"]
    trace_dir = run_dir / "decision"
    assert (trace_dir / "frames.jsonl.gz").is_file()
    # Product policy stores the event journal gzipped (measured: it dominates
    # the stored trace for VO); TraceBundle reads both forms additively.
    journal = trace_dir / "events.jsonl.gz"
    assert journal.is_file() and not (trace_dir / "events.jsonl").exists()
    index = read_index(run_dir)
    assert index["trace_schema"] == "colav.decision-replay.v1"
    assert index["tick_count"] > 0
    assert index["truncated"] is False

    bundle = TraceBundle(run_dir)
    assert bundle.evidence_level == "full"
    assert bundle.tick_count == index["tick_count"]


def test_product_trace_is_readable_by_existing_probes(finished_vo_run: dict[str, Any]) -> None:
    bundle = TraceBundle(finished_vo_run["run_dir"])
    report = probes.startup_timeline(bundle, seconds=30.0)
    assert report["rows"], "probe must inspect product evidence without re-running"


def test_finished_product_run_reports_replay_ready(finished_vo_run: dict[str, Any]) -> None:
    describe = finished_vo_run["describe"]
    assert describe["state"] == "FINISHED"
    assert describe["result_ready"] is True
    assert describe["replay_status"] == "READY"
    assert describe["replay_reason"] is None


def test_capturing_state_is_visible_while_running(manager: Any, tmp_path: Path) -> None:
    manager.create(make_spec(tmp_path))
    session_id = manager.session_id
    manager.start(session_id)
    assert manager.tick() is not None
    describe = manager.describe()
    assert describe["state"] == "RUNNING"
    assert describe["replay_status"] == "CAPTURING"
    status = manager.replay_status_for(session_id)
    assert status is not None and status["state"] == "CAPTURING"

    frames = manager.prepared.run_dir / "decision" / "frames.jsonl"
    deadline = time.monotonic() + 10.0
    while frames.read_bytes().count(b"\n") < 1:
        assert time.monotonic() < deadline, "background capture writer did not persist the first tick"
        time.sleep(0.02)
    baseline = frames.read_bytes().count(b"\n")
    manager.tick()
    deadline = time.monotonic() + 10.0
    while frames.read_bytes().count(b"\n") < baseline + 1:
        assert time.monotonic() < deadline, "background capture writer did not persist the next tick"
        time.sleep(0.02)


def test_replay_ready_publishes_before_result_ready(manager: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manager.create(make_spec(tmp_path))
    release = threading.Event()
    real_finalize = manager.runner.finalize

    def slow_evaluation(*args: Any, **kwargs: Any) -> Any:
        release.wait(timeout=60)
        return real_finalize(*args, **kwargs)

    monkeypatch.setattr(manager.runner, "finalize", slow_evaluation)
    run_to_finished(manager)

    deadline = time.monotonic() + 30.0
    describe = manager.describe()
    while describe["replay_status"] != "READY":
        assert time.monotonic() < deadline, "replay trace was not finalized after execution ended"
        time.sleep(0.05)
        describe = manager.describe()
    assert describe["state"] == "FINISHED"
    assert describe["replay_reason"] is None
    assert read_index(manager.prepared.run_dir)["truncated"] is False
    assert describe["result_ready"] is False, "evaluation still pending"

    release.set()
    wait_for_result(manager)
    assert manager.describe()["result_ready"] is True


def test_browser_disconnect_does_not_stop_capture(tmp_path: Path) -> None:
    """The GUI app's backend loop keeps capturing after the WebSocket dies."""
    spec = make_spec(tmp_path)
    manager = gui_main.manager
    manager.create(spec)
    session_id = manager.session_id
    run_dir = manager.prepared.run_dir
    try:
        with TestClient(gui_main.app) as client:
            manager.start(session_id)
            with client.websocket_connect(f"/ws/sessions/{session_id}") as websocket:
                first = websocket.receive_json()
            assert first.get("run_id") == session_id
            # Browser disconnected here; the backend session keeps executing.
            deadline = time.monotonic() + FINALIZE_TIMEOUT_S
            while manager.prepared.session.state == SessionState.RUNNING:
                assert time.monotonic() < deadline, "run did not finish after browser disconnect"
                time.sleep(0.05)
        wait_for_result(manager)
        index = read_index(run_dir)
        assert index["truncated"] is False
        assert index["tick_count"] > 1, "capture must survive the disconnect"
    finally:
        pass


def test_capture_opt_out_is_truthfully_classified(manager: Any, tmp_path: Path) -> None:
    manager.create(make_spec(tmp_path), record_replay_trace=False)
    run_to_finished(manager)
    wait_for_result(manager)

    run_dir = manager.prepared.run_dir
    assert not (run_dir / "decision").exists(), "opt-out must not create partial evidence"
    describe = manager.describe()
    assert describe["replay_status"] == "UNAVAILABLE"
    assert describe["replay_reason"] == "TRACE_CAPTURE_DISABLED"


def test_session_reset_closes_previous_trace_without_frame_bleed(manager: Any, tmp_path: Path) -> None:
    manager.create(make_spec(tmp_path))
    session_id = manager.session_id
    manager.start(session_id)
    for _ in range(5):
        assert manager.tick() is not None
    manager.pause(session_id)
    old_run_dir = manager.prepared.run_dir

    manager.reset(session_id)
    new_session_id = manager.session_id
    assert new_session_id != session_id

    wait_for_file(old_run_dir / "decision" / "index.json")
    old_index = read_index(old_run_dir)
    assert old_index["truncated"] is True
    assert old_index["incomplete_reason"] == "SESSION_REPLACED"
    assert old_index["tick_count"] == 5

    assert manager.describe()["replay_status"] == "CAPTURING"
    run_to_finished(manager, tick_limit=TICK_LIMIT)
    wait_for_result(manager)
    expected_ticks = manager.prepared.session.sequence
    assert expected_ticks > 2
    new_index = read_index(manager.prepared.run_dir)
    assert new_index["tick_count"] == expected_ticks, "no cross-run frame bleed (one run = one episode)"


def test_trace_persistence_failure_is_incomplete_never_ready(
    manager: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manager.create(make_spec(tmp_path))
    session_id = manager.session_id
    manager.start(session_id)
    assert manager.tick() is not None

    def broken_close(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise OSError("simulated disk failure")

    monkeypatch.setattr(TraceSink, "close", broken_close)
    while manager.tick() is not None:
        pass
    wait_for_result(manager)

    describe = manager.describe()
    assert describe["replay_status"] == "INCOMPLETE"
    assert describe["replay_reason"] == "CAPTURE_FINALIZE_FAILED"
    assert describe["result_ready"] is True, "execution evidence must survive capture failure"


def test_failed_execution_closes_trace_truthfully(manager: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manager.create(make_spec(tmp_path))
    session_id = manager.session_id
    manager.start(session_id)
    assert manager.tick() is not None

    prepared = manager.prepared

    def exploding_advance() -> Any:
        raise RuntimeError("solver exploded")

    monkeypatch.setattr(prepared.session, "advance", exploding_advance)
    assert manager.tick() is None  # failure path
    wait_for_file(prepared.run_dir / "decision" / "index.json")
    index = read_index(prepared.run_dir)
    assert index["truncated"] is True
    assert index["incomplete_reason"] == "EXECUTION_FAILED"
    assert manager.describe()["replay_status"] == "INCOMPLETE"


# ---------------------------------------------------------------------------
# Per-Run capture budget env policy (ticket #70)
# ---------------------------------------------------------------------------


def test_capture_budget_env_sets_budget_in_both_directions(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(gui_main.CAPTURE_BUDGET_ENV, "1234")
    assert gui_main.capture_budget_policy().max_total_bytes == 1234, "env may lower the budget"

    raised = gui_main.DEFAULT_CAPTURE_BUDGET_BYTES * 2
    monkeypatch.setenv(gui_main.CAPTURE_BUDGET_ENV, str(raised))
    policy = gui_main.capture_budget_policy()
    assert policy.max_total_bytes == raised, "env may raise the budget"
    assert policy.events_gzip is True


def test_capture_budget_env_invalid_falls_back_to_default_with_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    for raw in ["not-a-number", "0", "-512", "2 GiB"]:
        monkeypatch.setenv(gui_main.CAPTURE_BUDGET_ENV, raw)
        with caplog.at_level(logging.WARNING, logger="gui_server"):
            policy = gui_main.capture_budget_policy()
        assert policy.max_total_bytes == gui_main.DEFAULT_CAPTURE_BUDGET_BYTES, raw
        assert any(gui_main.CAPTURE_BUDGET_ENV in record.getMessage() for record in caplog.records), raw

    monkeypatch.delenv(gui_main.CAPTURE_BUDGET_ENV, raising=False)
    assert gui_main.capture_budget_policy().max_total_bytes == gui_main.DEFAULT_CAPTURE_BUDGET_BYTES
