"""Replay evidence store, descriptor and run discovery (ticket #70, Seam A).

Tests build real Decision Trace evidence with the shared TraceSink, then assert
external read-path behavior: truthful classification, descriptor identity,
path confinement, bounded discovery and budget-driven retention.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import gui_server.replay as replay_module
from colav_simulator.decision_replay.sink import TraceSink
from gui_server.replay import (
    DEFAULT_RETENTION_BUDGET_BYTES,
    RETENTION_BUDGET_ENV,
    RUNS_ROOT_ENV,
    RunReplayError,
    RunReplayStore,
    build_replay_router,
    replay_retention_budget_bytes,
    runs_root,
)

RUN_READY = "11111111-1111-4111-8111-111111111111"
RUN_TAMPER = "22222222-2222-4222-8222-222222222222"
RUN_SCHEMA = "33333333-3333-4333-8333-333333333333"
RUN_CRASH = "44444444-4444-4444-8444-444444444444"
RUN_LEGACY = "55555555-5555-4555-8555-555555555555"
RUN_BARE = "66666666-6666-4666-8666-666666666666"
RUN_LIVE = "77777777-7777-4777-8777-777777777777"
RUN_OLD = "88888888-8888-4888-8888-888888888888"
RUN_MID = "99999999-9999-4999-8999-999999999999"
RUN_NEW = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
RUN_UNKNOWN = "00000000-0000-0000-0000-000000000000"


@dataclass
class FakeSnapshot:
    sequence: int
    sim_time: float
    state: Any = None
    step_time_ms: float = 1.0
    payload: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)


def write_manifest(run_dir: Path, *, created_at: str, state: str = "FINISHED") -> None:
    manifest = {
        "run_id": run_dir.name,
        "created_at_utc": created_at,
        "state": state,
        "requested_algorithm": "vo",
        "executed_algorithm": "vo",
        "requested_tracker": "god",
        "executed_tracker": "god",
        "validation_rule_id": "rule14",
        "spec": {"scenario_id": "head_on"},
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def record_trace(run_dir: Path, *, ticks: int = 3, events: list[dict[str, Any]] | None = None) -> None:
    sink = TraceSink.open(run_dir)
    for sequence in range(1, ticks + 1):
        sink.append(
            FakeSnapshot(
                sequence=sequence,
                sim_time=0.1 * sequence,
                payload={"Ship0": {"state": [sequence]}},
                events=[{"type": "planner_solved", "sim_time": 0.1 * sequence}],
            )
        )
    sink.close(
        events=events
        if events is not None
        else [{"type": "session_started", "sim_time": 0.1}, {"type": "collision", "sim_time": 0.2}]
    )


def make_run(
    root: Path,
    name: str,
    *,
    created_at: str,
    trace: bool = True,
    trajectory: bool = True,
    finalized: bool = True,
) -> Path:
    run_dir = root / name
    run_dir.mkdir(parents=True)
    write_manifest(run_dir, created_at=created_at)
    if trace:
        if finalized:
            record_trace(run_dir)
        else:
            sink = TraceSink.open(run_dir)
            sink.append(FakeSnapshot(sequence=1, sim_time=0.1, payload={"t": 1}))
            sink.append(FakeSnapshot(sequence=2, sim_time=0.2, payload={"t": 2}))
    if trajectory:
        (run_dir / "trajectory.parquet").write_bytes(b"parquet-bytes")
    return run_dir


@pytest.fixture()
def store(tmp_path: Path) -> RunReplayStore:
    return RunReplayStore(tmp_path / "runs")


# ---------------------------------------------------------------------------
# Classification truthfulness
# ---------------------------------------------------------------------------


def test_ready_run_classifies_full_with_integrity(store: RunReplayStore, tmp_path: Path) -> None:
    run_dir = make_run(tmp_path / "runs", RUN_READY, created_at="2026-09-11T10:00:00Z")
    facts = store.classify(run_dir)
    assert facts["state"] == "READY"
    assert facts["evidence_level"] == "full"
    assert facts["reason"] is None
    assert facts["frame_count"] == 3
    assert facts["truncated"] is False
    assert facts["trace_schema"] == "colav.decision-replay.v1"
    assert facts["trusted_t_end"] == pytest.approx(0.3)


def test_digest_mismatch_classifies_incomplete(store: RunReplayStore, tmp_path: Path) -> None:
    run_dir = make_run(tmp_path / "runs", RUN_TAMPER, created_at="2026-09-11T10:00:00Z")
    gz = run_dir / "decision" / "frames.jsonl.gz"
    gz.write_bytes(gz.read_bytes()[:-1] + bytes([gz.read_bytes()[-1] ^ 0xFF]))
    facts = store.classify(run_dir)
    assert facts["state"] == "INCOMPLETE"
    assert facts["reason"] == "TRACE_DIGEST_MISMATCH"


def test_unsupported_schema_fails_closed(store: RunReplayStore, tmp_path: Path) -> None:
    run_dir = make_run(tmp_path / "runs", RUN_SCHEMA, created_at="2026-09-11T10:00:00Z")
    index_path = run_dir / "decision" / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["trace_schema"] = "colav.decision-replay.v99"
    index_path.write_text(json.dumps(index), encoding="utf-8")
    facts = store.classify(run_dir)
    assert facts["state"] == "UNAVAILABLE"
    assert facts["reason"] == "TRACE_SCHEMA_UNSUPPORTED"


def test_crashed_prefix_classifies_incomplete_with_trusted_end(store: RunReplayStore, tmp_path: Path) -> None:
    run_dir = make_run(tmp_path / "runs", RUN_CRASH, created_at="2026-09-11T10:00:00Z", finalized=False)
    facts = store.classify(run_dir)
    assert facts["state"] == "INCOMPLETE"
    assert facts["reason"] == "TRACE_TRUNCATED"
    assert facts["frame_count"] == 2
    assert facts["trusted_t_end"] == pytest.approx(0.2)
    assert facts["truncated"] is True


def test_legacy_run_classifies_reduced_without_fabricated_facts(store: RunReplayStore, tmp_path: Path) -> None:
    run_dir = make_run(tmp_path / "runs", RUN_LEGACY, created_at="2026-09-11T10:00:00Z", trace=False)
    facts = store.classify(run_dir)
    assert facts["state"] == "REDUCED"
    assert facts["evidence_level"] == "reduced"
    assert facts["reason"] == "REDUCED_TRAJECTORY_ONLY"
    assert facts["frame_count"] == 0
    assert facts["frames_sha256"] is None


def test_bare_manifest_classifies_unavailable(store: RunReplayStore, tmp_path: Path) -> None:
    run_dir = make_run(tmp_path / "runs", RUN_BARE, created_at="2026-09-11T10:00:00Z", trace=False, trajectory=False)
    facts = store.classify(run_dir)
    assert facts["state"] == "UNAVAILABLE"
    assert facts["reason"] == "TRACE_MISSING"


# ---------------------------------------------------------------------------
# Descriptor
# ---------------------------------------------------------------------------


def test_descriptor_reports_versioned_identity_and_facts(store: RunReplayStore, tmp_path: Path) -> None:
    run_dir = make_run(tmp_path / "runs", RUN_READY, created_at="2026-09-11T10:00:00Z")
    descriptor = store.descriptor(run_dir.name)
    assert descriptor["schema_version"] == "colav.run-replay.descriptor@1"
    assert descriptor["run_id"] == run_dir.name
    assert descriptor["run"]["scenario_id"] == "head_on"
    assert descriptor["run"]["requested_algorithm"] == "vo"
    assert descriptor["run"]["executed_tracker"] == "god"
    assert descriptor["run"]["execution_state"] == "FINISHED"
    assert descriptor["run"]["result_ready"] is False
    assert descriptor["replay"]["state"] == "READY"
    assert descriptor["replay"]["evidence_level"] == "full"
    assert descriptor["replay"]["frame_count"] == 3
    assert descriptor["replay"]["t_start"] == pytest.approx(0.1)
    assert descriptor["replay"]["t_end"] == pytest.approx(0.3)
    assert len(descriptor["replay"]["frames_sha256"]) == 64
    assert descriptor["replay"]["truncated"] is False
    assert descriptor["events"]["count"] >= 2
    assert "collision" in descriptor["events"]["categories"]
    assert descriptor["capabilities"]["full_frame"] is True
    assert descriptor["capabilities"]["planner_detail"] is True


def test_descriptor_merges_active_capturing_state(store: RunReplayStore, tmp_path: Path) -> None:
    run_dir = make_run(tmp_path / "runs", RUN_LIVE, created_at="2026-09-11T10:00:00Z", trace=False)
    active = {"state": "CAPTURING", "reason": None, "frame_count": 12}
    descriptor = store.descriptor(run_dir.name, active=active)
    assert descriptor["replay"]["state"] == "CAPTURING"
    assert descriptor["replay"]["frame_count"] == 12
    assert descriptor["replay"]["evidence_level"] == "full"
    assert descriptor["capabilities"]["full_frame"] is True
    assert descriptor["capabilities"]["planner_detail"] is False, "READY-only facts must not be claimed while capturing"


def test_reduced_descriptor_claims_no_planner_capabilities(store: RunReplayStore, tmp_path: Path) -> None:
    run_dir = make_run(tmp_path / "runs", RUN_LEGACY, created_at="2026-09-11T10:00:00Z", trace=False)
    descriptor = store.descriptor(run_dir.name)
    assert descriptor["replay"]["state"] == "REDUCED"
    assert descriptor["capabilities"]["full_frame"] is False
    assert descriptor["capabilities"]["planner_detail"] is False


# ---------------------------------------------------------------------------
# Identity / path confinement
# ---------------------------------------------------------------------------


def test_invalid_run_ids_are_rejected(store: RunReplayStore, tmp_path: Path) -> None:
    (tmp_path / "runs" / "secret").mkdir(parents=True)
    for bad in ["../secret", "..", "not-a-uuid", "a/b", "", "urn:uuid:1234"]:
        with pytest.raises(RunReplayError) as excinfo:
            store.run_dir(bad)
        assert excinfo.value.status == 404
        assert excinfo.value.reason in {"RUN_ID_INVALID", "RUN_NOT_FOUND"}


def test_valid_but_unknown_run_id_is_not_found(store: RunReplayStore) -> None:
    with pytest.raises(RunReplayError) as excinfo:
        store.run_dir(RUN_UNKNOWN)
    assert excinfo.value.reason == "RUN_NOT_FOUND"


def test_valid_run_id_resolves_inside_root(store: RunReplayStore, tmp_path: Path) -> None:
    run_dir = make_run(tmp_path / "runs", RUN_READY, created_at="2026-09-11T10:00:00Z")
    resolved = store.run_dir(run_dir.name)
    assert resolved == run_dir.resolve()
    assert resolved.is_relative_to((tmp_path / "runs").resolve())


def test_traversal_target_is_never_resolved_even_if_it_exists(store: RunReplayStore, tmp_path: Path) -> None:
    outside = tmp_path / "secret"
    outside.mkdir()
    write_manifest(outside, created_at="2026-09-11T10:00:00Z")
    with pytest.raises(RunReplayError) as excinfo:
        store.run_dir("../secret")
    assert excinfo.value.reason in {"RUN_ID_INVALID", "RUN_NOT_FOUND"}
    assert not (tmp_path / "runs" / "secret").exists()


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def test_list_runs_sorted_and_filterable(store: RunReplayStore, tmp_path: Path) -> None:
    root = tmp_path / "runs"
    make_run(root, RUN_OLD, created_at="2026-09-11T08:00:00Z", finalized=False)
    ready = make_run(root, RUN_NEW, created_at="2026-09-11T10:00:00Z")
    make_run(root, RUN_LEGACY, created_at="2026-09-11T09:00:00Z", trace=False)

    entries = store.list_runs()
    assert [entry["run_id"] for entry in entries] == [RUN_NEW, RUN_LEGACY, RUN_OLD]
    states = {entry["run_id"]: entry["replay"]["state"] for entry in entries}
    assert states[RUN_NEW] == "READY"
    assert states[RUN_LEGACY] == "REDUCED"
    assert states[RUN_OLD] == "INCOMPLETE"

    replayable = store.list_runs(replayable=True)
    assert [entry["run_id"] for entry in replayable] == [ready.name]
    assert replayable[0]["scenario_id"] == "head_on"

    limited = store.list_runs(limit=1)
    assert len(limited) == 1


def test_list_runs_bounded_and_empty_safe(store: RunReplayStore, tmp_path: Path) -> None:
    assert store.list_runs() == []
    root = tmp_path / "runs"
    root.mkdir()
    (root / "not-a-run.txt").write_text("x", encoding="utf-8")
    assert store.list_runs() == []


# ---------------------------------------------------------------------------
# Runs-root resolution (writer/discovery must never diverge)
# ---------------------------------------------------------------------------


def test_runs_root_env_override_is_honored(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    override = tmp_path / "override-runs"
    monkeypatch.setenv(RUNS_ROOT_ENV, str(override))
    assert runs_root() == override.resolve()


def test_runs_root_is_project_anchored_not_cwd_relative(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv(RUNS_ROOT_ENV, raising=False)
    cwd_a = tmp_path / "cwd-a"
    cwd_b = tmp_path / "cwd-b"
    cwd_a.mkdir()
    cwd_b.mkdir()

    monkeypatch.chdir(cwd_a)
    anchored = runs_root()
    monkeypatch.chdir(cwd_b)

    assert runs_root() == anchored, "the runs root must not depend on the process cwd"
    assert anchored != cwd_a / "runs"


def test_store_from_runs_root_discovers_run_written_under_project_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The writer resolves RunSpec.output_root="runs" against the project root;
    # simulate exactly that layout, then discover it from an unrelated cwd.
    runs = tmp_path / "runs"
    make_run(runs, RUN_READY, created_at="2026-09-11T10:00:00Z")
    elsewhere = tmp_path / "cwd"
    elsewhere.mkdir()
    monkeypatch.delenv(RUNS_ROOT_ENV, raising=False)
    monkeypatch.setattr(replay_module, "PROJECT_ROOT", tmp_path)
    monkeypatch.chdir(elsewhere)

    store = RunReplayStore(runs_root())

    assert [entry["run_id"] for entry in store.list_runs()] == [RUN_READY]
    descriptor = store.descriptor(RUN_READY)
    assert descriptor["replay"]["state"] == "READY"


# ---------------------------------------------------------------------------
# Retention pruning (LRU over decision/ only)
# ---------------------------------------------------------------------------


def test_prune_removes_oldest_traces_within_budget(store: RunReplayStore, tmp_path: Path) -> None:
    root = tmp_path / "runs"
    make_run(root, RUN_OLD, created_at="2026-09-11T08:00:00Z")
    keep_a = make_run(root, RUN_MID, created_at="2026-09-11T09:00:00Z")
    keep_b = make_run(root, RUN_NEW, created_at="2026-09-11T10:00:00Z")

    def size(path: Path) -> int:
        return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())

    old_size = size(root / RUN_OLD / "decision")
    candidates_total = old_size + size(keep_a / "decision")
    budget = candidates_total - old_size + 10  # force exactly one eviction

    events: list[dict[str, Any]] = []
    pruned = store.prune_traces(
        budget_bytes=budget,
        keep_run_ids=frozenset({keep_b.name}),
        log_event=lambda run_dir, document: events.append(document),
    )

    assert pruned == [RUN_OLD]
    assert not (root / RUN_OLD / "decision").exists()
    assert (root / RUN_OLD / "manifest.json").is_file(), "manifests are never pruned"
    assert (root / RUN_OLD / "trajectory.parquet").is_file(), "trajectories are never pruned"
    assert (keep_a / "decision" / "index.json").is_file()
    assert events and events[0]["type"] == "replay_trace_pruned"
    assert events[0]["run_id"] == RUN_OLD

    facts = store.classify(root / RUN_OLD)
    assert facts["state"] == "REDUCED", "pruned run must report its truthful degraded state"


def test_prune_never_touches_unfinalized_traces(store: RunReplayStore, tmp_path: Path) -> None:
    root = tmp_path / "runs"
    make_run(root, RUN_CRASH, created_at="2026-09-11T08:00:00Z", finalized=False)

    pruned = store.prune_traces(budget_bytes=1)
    assert pruned == [], "capturing/crashed traces without index.json are never pruned"
    assert (root / RUN_CRASH / "decision" / "frames.jsonl").is_file()


def test_prune_noop_within_budget_or_disabled(store: RunReplayStore, tmp_path: Path) -> None:
    root = tmp_path / "runs"
    make_run(root, RUN_OLD, created_at="2026-09-11T08:00:00Z")
    assert store.prune_traces(budget_bytes=0) == []
    assert store.prune_traces(budget_bytes=10**9) == []
    assert (root / RUN_OLD / "decision" / "index.json").is_file()


def test_retention_budget_env_override_is_honored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(RETENTION_BUDGET_ENV, "123456789")
    assert replay_retention_budget_bytes() == 123456789


def test_retention_budget_env_garbage_never_disables_retention(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    for raw in ["garbage", "0", "-1", "4 GiB"]:
        monkeypatch.setenv(RETENTION_BUDGET_ENV, raw)
        with caplog.at_level(logging.WARNING, logger="gui_server.replay"):
            budget = replay_retention_budget_bytes()
        assert budget == DEFAULT_RETENTION_BUDGET_BYTES, "a garbage value must never disable retention"
        assert any(RETENTION_BUDGET_ENV in record.getMessage() for record in caplog.records), raw

    monkeypatch.delenv(RETENTION_BUDGET_ENV, raising=False)
    assert replay_retention_budget_bytes() == DEFAULT_RETENTION_BUDGET_BYTES


# ---------------------------------------------------------------------------
# Read-only HTTP router
# ---------------------------------------------------------------------------


@pytest.fixture()
def api_client(tmp_path: Path) -> TestClient:
    store = RunReplayStore(tmp_path / "runs")
    make_run(tmp_path / "runs", RUN_READY, created_at="2026-09-11T10:00:00Z")
    app = FastAPI()
    app.include_router(build_replay_router(store))
    return TestClient(app)


def test_api_lists_replayable_runs(api_client: TestClient) -> None:
    response = api_client.get("/api/runs", params={"replayable": "true"})
    assert response.status_code == 200
    entries = response.json()
    assert [entry["run_id"] for entry in entries] == [RUN_READY]
    assert entries[0]["replay"]["state"] == "READY"


def test_api_descriptor_by_run_id(api_client: TestClient) -> None:
    response = api_client.get(f"/api/runs/{RUN_READY}/replay")
    assert response.status_code == 200
    assert response.json()["schema_version"] == "colav.run-replay.descriptor@1"


def test_api_descriptor_merges_active_capturing_state(tmp_path: Path) -> None:
    store = RunReplayStore(tmp_path / "runs")
    make_run(tmp_path / "runs", RUN_LIVE, created_at="2026-09-11T10:00:00Z", trace=False)
    def active(_run_id: str) -> dict[str, Any]:
        return {"state": "CAPTURING", "reason": None, "frame_count": 7}

    app = FastAPI()
    app.include_router(build_replay_router(store, active_replay_status=active))
    client = TestClient(app)
    response = client.get(f"/api/runs/{RUN_LIVE}/replay")
    assert response.status_code == 200
    assert response.json()["replay"]["state"] == "CAPTURING"


def test_api_rejects_traversal_and_unknown_ids(api_client: TestClient) -> None:
    traversal = api_client.get("/api/runs/..%2F..%2Fsecret/replay")
    assert traversal.status_code == 404, "path syntax must never reach the store"
    unknown = api_client.get(f"/api/runs/{RUN_UNKNOWN}/replay")
    assert unknown.status_code == 404
    assert unknown.json()["detail"]["reason"] == "RUN_NOT_FOUND"
    malformed = api_client.get("/api/runs/not-a-uuid/replay")
    assert malformed.status_code == 404
    assert malformed.json()["detail"]["reason"] == "RUN_ID_INVALID"
