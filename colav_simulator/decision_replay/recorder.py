"""Record one headless run with full per-tick decision evidence.

The web GUI consumes ``SimulationSession.frames`` (verbatim per-tick payloads)
but ``ExperimentRunner.finalize`` persists only reduced trajectory rows, so the
decision evidence dies with the process. This recorder streams the full frames
plus the event journal into ``runs/<run_id>/decision/`` while the run executes,
making every later question an offline read instead of a re-run.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from colav_simulator.experiment.contracts import RunSpec, SessionState
from colav_simulator.experiment.persistence import jsonable
from colav_simulator.experiment.runner import ExperimentRunError, ExperimentRunner, PreparedRun

TRACE_SCHEMA = "colav.decision-replay.v1"


@dataclass(frozen=True)
class RecordResult:
    run_dir: Path
    trace_dir: Path
    manifest: Any
    state: str


class _TraceWriter:
    """Stream one JSONL line per tick; gzip and index on close."""

    def __init__(self, run_dir: Path) -> None:
        self._dir = run_dir / "decision"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._frames_path = self._dir / "frames.jsonl"
        self._handle = self._frames_path.open("w", encoding="utf-8")
        self._tick_count = 0
        self._t_start: float | None = None
        self._t_end: float | None = None
        self._truncated = True

    def append(self, snapshot: Any) -> None:
        payload = jsonable(snapshot.payload)
        record = {
            "sequence": snapshot.sequence,
            "sim_time": snapshot.sim_time,
            "step_time_ms": snapshot.step_time_ms,
            "state": snapshot.state.value if hasattr(snapshot.state, "value") else str(snapshot.state),
            "payload": payload,
            "events": jsonable(snapshot.events),
        }
        self._handle.write(json.dumps(record, allow_nan=False) + "\n")
        self._handle.flush()
        self._tick_count += 1
        if self._t_start is None:
            self._t_start = snapshot.sim_time
        self._t_end = snapshot.sim_time

    def close(self, *, events: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        self._handle.close()
        data = self._frames_path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        with gzip.GzipFile(str(self._dir / "frames.jsonl.gz"), "wb", mtime=0) as gz:
            gz.write(data)
        self._frames_path.unlink()
        self._truncated = False
        if events is not None:
            events_path = self._dir / "events.jsonl"
            with events_path.open("w", encoding="utf-8") as stream:
                for event in events:
                    stream.write(json.dumps(jsonable(event), allow_nan=False) + "\n")
        index = {
            "trace_schema": TRACE_SCHEMA,
            "tick_count": self._tick_count,
            "t_start": self._t_start,
            "t_end": self._t_end,
            "frames_sha256": digest,
            "truncated": self._truncated,
        }
        (self._dir / "index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
        return index


def record(spec: RunSpec, *, runner: ExperimentRunner | None = None) -> RecordResult:
    """Run ``spec`` headless once, persisting the full decision trace."""
    runner = runner or ExperimentRunner()
    prepared: PreparedRun = runner.prepare(spec)
    writer = _TraceWriter(prepared.run_dir)
    try:
        session = prepared.session
        session.start()
        while session.state == SessionState.RUNNING:
            writer.append(session.advance())
        result = runner.finalize(prepared)
        writer.close(events=prepared.session.events)
        return RecordResult(
            run_dir=prepared.run_dir,
            trace_dir=prepared.run_dir / "decision",
            manifest=result.manifest,
            state=result.manifest.state.value,
        )
    except Exception as exc:
        writer.close()
        prepared.artifact_sink.close(timeout_s=2.0)
        ExperimentRunner.persist_failure(
            prepared.manifest,
            prepared.writer,
            exc,
            prepared.session.frames,
            prepared.session.events,
        )
        raise ExperimentRunError(prepared.manifest, prepared.run_dir) from exc
