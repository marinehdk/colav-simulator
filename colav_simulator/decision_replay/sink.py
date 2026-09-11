"""Reusable per-tick decision trace evidence sink (ticket #70).

Extracted from the debug-only recorder's ``_TraceWriter`` so the normal product
Active Session path (``gui_server``) and the ``decision_replay record`` CLI share
ONE producer-facing writer. The on-disk artifact contract is unchanged: the
``colav.decision-replay.v1`` schema, ``decision/frames.jsonl.gz``,
``decision/events.jsonl[.gz]`` and ``decision/index.json``.

Capture is asynchronous with a bounded queue: the simulation thread pays one
``jsonable`` + ``json.dumps`` per tick and a background worker owns file I/O.
No frame is ever silently discarded — queue backpressure, byte-budget
exhaustion and persistence failures all switch the sink to a typed
``INCOMPLETE`` state, stop admission, and keep the durable prefix truthful.
A hard process crash leaves the plain ``frames.jsonl`` prefix without an
``index.json``, which downstream classifiers report as INCOMPLETE.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import queue
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from colav_simulator.decision_replay.bundle import TRACE_SCHEMA
from colav_simulator.experiment.persistence import jsonable

STATE_CAPTURING = "CAPTURING"
STATE_READY = "READY"
STATE_INCOMPLETE = "INCOMPLETE"

REASON_TRACE_GAP = "TRACE_GAP"
REASON_TRACE_BUDGET_EXCEEDED = "TRACE_BUDGET_EXCEEDED"
REASON_TRACE_WRITE_FAILED = "TRACE_WRITE_FAILED"
REASON_TRACE_SERIALIZE_FAILED = "TRACE_SERIALIZE_FAILED"

WORKER_POLL_S = 0.05


@dataclass(frozen=True)
class TraceSinkPolicy:
    """Bounded capture policy; exceeding any bound is a typed failure."""

    max_queue_records: int = 128
    max_total_bytes: int = 512 * 1024 * 1024
    events_gzip: bool = False
    worker: bool = True  # False only exercised by tests to force backpressure


class TraceSink:
    """Stream one immutable JSONL frame per tick; gzip and index on close."""

    def __init__(self, run_dir: Path, policy: TraceSinkPolicy) -> None:
        self._policy = policy
        self._dir = run_dir / "decision"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._frames_path = self._dir / "frames.jsonl"
        self._handle = self._frames_path.open("wb")
        self._lock = threading.Lock()
        self._records: queue.Queue[tuple[float, bytes]] = queue.Queue(maxsize=policy.max_queue_records)
        self._state = STATE_CAPTURING
        self._reason: str | None = None
        self._closed = False
        self._finalized = False
        self._index: dict[str, Any] = {}
        self._tick_count = 0
        self._t_start: float | None = None
        self._t_end: float | None = None
        self._produced_bytes = 0
        self._worker = threading.Thread(target=self._write_loop, name="decision-trace", daemon=True)
        if policy.worker:
            self._worker.start()

    @classmethod
    def open(cls, run_dir: Path, *, policy: TraceSinkPolicy | None = None) -> TraceSink:
        return cls(run_dir, policy or TraceSinkPolicy())

    @property
    def state(self) -> str:
        with self._lock:
            return self._state

    @property
    def reason(self) -> str | None:
        with self._lock:
            return self._reason

    @property
    def finalized(self) -> bool:
        """True once close() has durably written index/artifacts (or failed to)."""
        with self._lock:
            return self._finalized

    @property
    def tick_count(self) -> int:
        with self._lock:
            return self._tick_count

    @property
    def produced_bytes(self) -> int:
        with self._lock:
            return self._produced_bytes

    def append(self, snapshot: Any) -> None:
        """Admit one immutable frame record. Never raises; typed on failure."""
        with self._lock:
            if self._closed or self._state != STATE_CAPTURING:
                return
            record = self._serialize(snapshot)
            if record is None:
                self._enter_failure_locked(REASON_TRACE_SERIALIZE_FAILED)
                return
            sim_time = float(snapshot.sim_time)
            size = len(record) + 1
            if self._produced_bytes + size > self._policy.max_total_bytes:
                self._enter_failure_locked(REASON_TRACE_BUDGET_EXCEEDED)
                return
            try:
                self._records.put_nowait((sim_time, record))
            except queue.Full:
                self._enter_failure_locked(REASON_TRACE_GAP)
                return
            self._produced_bytes += size

    def fail(self, reason: str) -> None:
        """Stop admission and mark the trace typed-INCOMPLETE (prefix survives)."""
        with self._lock:
            if self._state == STATE_CAPTURING:
                self._state = STATE_INCOMPLETE
                self._reason = str(reason)

    def close(self, *, events: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        """Drain, gzip, digest and index the trace. Idempotent; never raises."""
        with self._lock:
            self._closed = True
        if self._worker.is_alive() and self._worker is not threading.current_thread():
            self._worker.join()
        self._drain_remaining()
        if self._finalized:
            return self._index
        self._finalize(events)
        return self._index

    # -- internals ---------------------------------------------------------

    def _serialize(self, snapshot: Any) -> bytes | None:
        try:
            payload = jsonable(snapshot.payload)
            record = {
                "sequence": snapshot.sequence,
                "sim_time": snapshot.sim_time,
                "step_time_ms": snapshot.step_time_ms,
                "state": snapshot.state.value if hasattr(snapshot.state, "value") else str(snapshot.state),
                "payload": payload,
                "events": jsonable(snapshot.events),
            }
            return json.dumps(record, allow_nan=False).encode("utf-8")
        except (TypeError, ValueError):
            return None

    def _enter_failure_locked(self, reason: str) -> None:
        self._state = STATE_INCOMPLETE
        if self._reason is None:
            self._reason = reason

    def _write_loop(self) -> None:
        while True:
            try:
                entry = self._records.get(timeout=WORKER_POLL_S)
            except queue.Empty:
                with self._lock:
                    exhausted = self._closed and self._records.empty()
                if exhausted:
                    return
                continue
            self._persist(entry)

    def _drain_remaining(self) -> None:
        while True:
            try:
                entry = self._records.get_nowait()
            except queue.Empty:
                return
            self._persist(entry)

    def _persist(self, entry: tuple[float, bytes]) -> None:
        sim_time, record = entry
        try:
            self._handle.write(record)
            self._handle.write(b"\n")
            self._handle.flush()
        except OSError:
            with self._lock:
                self._enter_failure_locked(REASON_TRACE_WRITE_FAILED)
                self._closed = True
            return
        with self._lock:
            if self._tick_count == 0:
                self._t_start = sim_time
            self._t_end = sim_time
            self._tick_count += 1

    def _finalize(self, events: list[dict[str, Any]] | None) -> None:
        try:
            index = self._write_final_artifacts(events)
        except OSError:
            with self._lock:
                self._enter_failure_locked(REASON_TRACE_WRITE_FAILED)
                self._finalized = True
                self._index = {}
            return
        with self._lock:
            if self._state == STATE_CAPTURING:
                self._state = STATE_READY
            index["state"] = self._state
            self._finalized = True
            self._index = index
        try:
            self._dir.joinpath("index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
        except OSError:
            # Sealing failed: the trace stays truthful — no durable index, typed
            # INCOMPLETE — and close() still never raises.
            with self._lock:
                self._enter_failure_locked(REASON_TRACE_WRITE_FAILED)
                self._index = {}

    def _write_final_artifacts(self, events: list[dict[str, Any]] | None) -> dict[str, Any]:
        self._handle.close()
        data = self._frames_path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        with gzip.GzipFile(str(self._dir / "frames.jsonl.gz"), "wb", mtime=0) as gz:
            gz.write(data)
        self._frames_path.unlink()
        if events is not None:
            encoded = b"".join(
                json.dumps(jsonable(event), allow_nan=False).encode("utf-8") + b"\n" for event in events
            )
            if self._policy.events_gzip:
                with gzip.GzipFile(str(self._dir / "events.jsonl.gz"), "wb", mtime=0) as gz:
                    gz.write(encoded)
            else:
                (self._dir / "events.jsonl").write_bytes(encoded)
        with self._lock:
            truncated = self._state == STATE_INCOMPLETE
            index = {
                "trace_schema": TRACE_SCHEMA,
                "tick_count": self._tick_count,
                "t_start": self._t_start,
                "t_end": self._t_end,
                "frames_sha256": digest,
                "truncated": truncated,
            }
            if truncated and self._reason is not None:
                index["incomplete_reason"] = self._reason
        return index
