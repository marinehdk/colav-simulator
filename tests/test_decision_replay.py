"""Decision-replay harness: record round-trip and offline probe contracts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from colav_simulator.decision_replay import probes
from colav_simulator.decision_replay.bundle import TraceBundle
from colav_simulator.decision_replay.recorder import record
from colav_simulator.experiment.contracts import RunSpec

RUN_TIMEOUT_S = 600


@pytest.fixture(scope="module")
def recorded_run(tmp_path_factory: pytest.TempPathFactory) -> Path:
    tmp_path = tmp_path_factory.mktemp("decision_replay")
    spec = RunSpec(
        scenario_id="head_on",
        validation_rule_id="rule14",
        algorithm_id="vo",
        tracker_id="god",
        seed=4,
        t_end=20.0,
        output_root=str(tmp_path),
    )
    result = record(spec)
    assert result.state == "FINISHED"
    return result.run_dir


def test_record_persists_full_frames_with_index(recorded_run: Path) -> None:
    trace_dir = recorded_run / "decision"
    assert (trace_dir / "frames.jsonl.gz").is_file()
    assert (trace_dir / "events.jsonl").is_file()
    index = json.loads((trace_dir / "index.json").read_text(encoding="utf-8"))
    assert index["trace_schema"] == "colav.decision-replay.v1"
    assert index["tick_count"] > 0
    assert index["truncated"] is False


def test_bundle_matches_finalize_written_events(recorded_run: Path) -> None:
    bundle = TraceBundle(recorded_run)
    assert bundle.evidence_level == "full"
    recorded = [event for frame in bundle.frames() for event in frame["events"]]
    finalized = bundle.events()
    recorded_keys = {(event["type"], event["sim_time"]) for event in recorded}
    finalized_keys = {(event["type"], event["sim_time"]) for event in finalized if event.get("sim_time") is not None}
    assert recorded_keys <= finalized_keys
    assert bundle.tick_count == len(list(bundle.frames()))


def test_frame_and_time_navigation(recorded_run: Path) -> None:
    bundle = TraceBundle(recorded_run)
    first = bundle.frame(1)
    assert first["sequence"] == 1
    last = bundle.frame(bundle.tick_count)
    seq = bundle.seq_at_time(signals_time(last) / 2.0)
    assert 1 <= seq <= bundle.tick_count
    window = bundle.window(0.0, signals_time(last) / 2.0)
    assert window and window[-1]["sim_time"] <= signals_time(last) / 2.0 + 1e-9


def signals_time(frame: dict) -> float:
    return frame["sim_time"]


def test_startup_timeline_explains_control_source(recorded_run: Path) -> None:
    report = probes.startup_timeline(TraceBundle(recorded_run), seconds=30.0)
    assert report["rows"], "expected at least one startup row"
    assert {"seq", "t", "control_source", "applied"} <= set(report["rows"][0])


def test_why_primary_returns_schedule_or_reason(recorded_run: Path) -> None:
    report = probes.why_primary(TraceBundle(recorded_run), at=1.0)
    assert report["run_id"] == recorded_run.name
    assert "primary" in report


def test_planner_timeline_solves_are_fresh(recorded_run: Path) -> None:
    report = probes.planner_timeline(TraceBundle(recorded_run))
    solve_ids = [solve["solve_id"] for solve in report["solves"]]
    assert len(solve_ids) == len(set(solve_ids))


def test_compare_self_is_identical(recorded_run: Path) -> None:
    bundle = TraceBundle(recorded_run)
    report = probes.compare_runs(bundle, TraceBundle(recorded_run))
    assert report["identical"] is True


def test_route_adherence_reports_cross_track_and_terminal(recorded_run: Path) -> None:
    report = probes.route_adherence(TraceBundle(recorded_run), interval_s=10.0)
    assert report["run_id"] == recorded_run.name
    assert report["samples"], "expected at least one route sample"
    assert {"t", "cross_track_m", "mode", "committed"} <= set(report["samples"][0])
    assert report["max_cross_track_m"] >= 0.0
    assert report["final"] is not None
    assert any(event["type"] == "session_finished" for event in report["terminal_events"])


def test_reduced_legacy_run_dir(tmp_path: Path) -> None:
    run_dir = tmp_path / "legacy"
    run_dir.mkdir()
    (run_dir / "events.jsonl").write_text(
        json.dumps({"event_id": 1, "sequence": 1, "sim_time": 0.5, "type": "session_started", "details": {}}) + "\n",
        encoding="utf-8",
    )
    bundle = TraceBundle(run_dir)
    assert bundle.evidence_level == "reduced"
    assert bundle.tick_count == 0
    assert bundle.events()[0]["type"] == "session_started"
