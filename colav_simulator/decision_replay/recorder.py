"""Record one headless run with full per-tick decision evidence.

The web GUI consumes ``SimulationSession.frames`` (verbatim per-tick payloads)
but ``ExperimentRunner.finalize`` persists only reduced trajectory rows, so the
decision evidence dies with the process. This recorder streams the full frames
plus the event journal into ``runs/<run_id>/decision/`` while the run executes,
making every later question an offline read instead of a re-run.

Since ticket #70 the streaming writer is the shared :class:`TraceSink`, also
used by the normal product Active Session capture path.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from colav_simulator.decision_replay.bundle import TRACE_SCHEMA  # re-exported for compatibility
from colav_simulator.decision_replay.sink import TraceSink
from colav_simulator.experiment.contracts import RunSpec, SessionState
from colav_simulator.experiment.runner import ExperimentRunError, ExperimentRunner, PreparedRun

__all__ = ["TRACE_SCHEMA", "RecordResult", "record"]


@dataclass(frozen=True)
class RecordResult:
    run_dir: Path
    trace_dir: Path
    manifest: Any
    state: str


def record(spec: RunSpec, *, runner: ExperimentRunner | None = None) -> RecordResult:
    """Run ``spec`` headless once, persisting the full decision trace."""
    runner = runner or ExperimentRunner()
    prepared: PreparedRun = runner.prepare(spec)
    writer = TraceSink.open(prepared.run_dir)
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
        writer.fail("RECORDING_ABORTED")
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
