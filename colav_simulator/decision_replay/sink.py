"""Reusable per-tick decision trace evidence sink (ticket #70).

Extracted from the debug-only recorder's ``_TraceWriter`` so the normal product
Active Session path (``gui_server``) and the ``decision_replay record`` CLI share
ONE producer-facing writer. Full audit uses ``colav.decision-replay.v1``;
chart capture uses v2 shared display blocks. Both use ``decision/frames.jsonl.gz``,
``decision/events.jsonl[.gz]`` and ``decision/index.json``.

Capture is asynchronous with a bounded queue: the simulation thread serializes
each immutable frame once and a background worker owns file I/O.
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

import orjson

from colav_simulator.decision_replay.bundle import TRACE_SCHEMA
from colav_simulator.decision_replay.chart import (
    CHART_PROFILE,
    CHART_TRACE_SCHEMA,
    chart_events,
    chart_payload,
    pack_chart_record,
)
from colav_simulator.experiment.persistence import jsonable

STATE_CAPTURING = "CAPTURING"
STATE_READY = "READY"
STATE_INCOMPLETE = "INCOMPLETE"

REASON_TRACE_GAP = "TRACE_GAP"
REASON_TRACE_BUDGET_EXCEEDED = "TRACE_BUDGET_EXCEEDED"
REASON_TRACE_WRITE_FAILED = "TRACE_WRITE_FAILED"
REASON_TRACE_SERIALIZE_FAILED = "TRACE_SERIALIZE_FAILED"
REASON_VO_DECISION_CAPTURE_FAILED = "VO_DECISION_CAPTURE_FAILED"

WORKER_POLL_S = 0.05


def vo_decision_space_for_snapshot(snapshot: Any, ships: list[Any]) -> dict[str, Any] | None:
    """Capture the exact VO solve grid only on its executing frame."""
    planner = snapshot.payload.get("Ship0", {}).get("colav", {}).get("planner", {})
    if planner.get("algorithm_id") != "vo" or not planner.get("solver_executed") or not ships:
        return None
    decision = ships[0].get_colav_decision_space()
    if decision is None or decision.get("solve_id") != planner.get("solve_id"):
        raise ValueError("VO decision-space snapshot does not match the executed solve")
    return decision


@dataclass(frozen=True)
class TraceSinkPolicy:
    """Bounded capture policy; exceeding any bound is a typed failure.

    ``max_total_bytes`` counts serialized, uncompressed frame and event
    journal bytes. Compression changes storage size but cannot bypass the
    admission budget.
    """

    max_queue_records: int = 128
    max_total_bytes: int = 512 * 1024 * 1024
    events_gzip: bool = False
    worker: bool = True  # False only exercised by tests to force backpressure
    capture_profile: str = "full"


class TraceSink:
    """Stream one immutable JSONL frame per tick; gzip and index on close."""

    def __init__(self, run_dir: Path, policy: TraceSinkPolicy) -> None:
        if policy.capture_profile not in {"full", "chart"}:
            raise ValueError("unsupported replay capture profile")
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
        self._vo_decision_count = 0
        self._chart_block_ids: set[str] = set()
        self._pending_block_ids: set[str] = set()
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

    def append(self, snapshot: Any, *, vo_decision_space: dict[str, Any] | None = None) -> None:
        """Admit one immutable frame record. Never raises; typed on failure."""
        with self._lock:
            if self._closed or self._state != STATE_CAPTURING:
                return
            record = self._serialize(snapshot, vo_decision_space)
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
            if vo_decision_space is not None:
                self._vo_decision_count += 1
            self._chart_block_ids.update(self._pending_block_ids)

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

    def _serialize(self, snapshot: Any, vo_decision_space: dict[str, Any] | None) -> bytes | None:
        try:
            record = {
                "sequence": snapshot.sequence,
                "sim_time": snapshot.sim_time,
                "step_time_ms": snapshot.step_time_ms,
                "state": snapshot.state.value if hasattr(snapshot.state, "value") else str(snapshot.state),
                "payload": snapshot.payload,
                "events": snapshot.events,
            }
            if vo_decision_space is not None:
                record["vo_decision_space"] = vo_decision_space
            if self._policy.capture_profile == "chart":
                record["payload"] = chart_payload(snapshot.payload)
                record["events"] = chart_events(snapshot.events)
                record["capture_profile"] = CHART_PROFILE
                self._pending_block_ids = pack_chart_record(
                    record,
                    self._chart_block_ids,
                    lambda value: orjson.dumps(value, default=jsonable, option=orjson.OPT_SERIALIZE_NUMPY),
                )
            try:
                return orjson.dumps(
                    record,
                    default=jsonable,
                    option=orjson.OPT_SERIALIZE_NUMPY | orjson.OPT_PASSTHROUGH_DATETIME,
                )
            except TypeError:
                # Preserve the existing conversion for uncommon key/scalar types.
                return json.dumps(jsonable(record), allow_nan=False).encode("utf-8")
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
        except (OSError, TypeError, ValueError):
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
        encoded_events: bytes | None = None
        events_bytes = 0
        events_persisted = False
        if events is not None:
            if self._policy.capture_profile == "chart":
                events = chart_events(events)
            try:
                encoded_events = b"".join(
                    json.dumps(jsonable(event), allow_nan=False).encode("utf-8") + b"\n" for event in events
                )
                events_bytes = len(encoded_events)
            except (TypeError, ValueError):
                with self._lock:
                    self._enter_failure_locked(REASON_TRACE_SERIALIZE_FAILED)
                encoded_events = None
            else:
                with self._lock:
                    if self._produced_bytes + events_bytes > self._policy.max_total_bytes:
                        self._enter_failure_locked(REASON_TRACE_BUDGET_EXCEEDED)
                    else:
                        events_persisted = True

        self._handle.close()
        digest = hashlib.sha256()
        with (
            self._frames_path.open("rb") as source,
            gzip.GzipFile(str(self._dir / "frames.jsonl.gz"), "wb", mtime=0) as gz,
        ):
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
                gz.write(chunk)
        self._frames_path.unlink()
        if events_persisted and encoded_events is not None:
            if self._policy.events_gzip:
                with gzip.GzipFile(str(self._dir / "events.jsonl.gz"), "wb", mtime=0) as gz:
                    gz.write(encoded_events)
            else:
                (self._dir / "events.jsonl").write_bytes(encoded_events)
        with self._lock:
            truncated = self._state == STATE_INCOMPLETE
            index = {
                "trace_schema": CHART_TRACE_SCHEMA if self._policy.capture_profile == "chart" else TRACE_SCHEMA,
                "capture_profile": CHART_PROFILE if self._policy.capture_profile == "chart" else "full",
                "tick_count": self._tick_count,
                "vo_decision_count": self._vo_decision_count,
                "t_start": self._t_start,
                "t_end": self._t_end,
                "frames_sha256": digest.hexdigest(),
                "truncated": truncated,
                "capture_bytes": self._produced_bytes + (events_bytes if events_persisted else 0),
                "events_bytes": events_bytes,
                "events_persisted": events_persisted,
            }
            if truncated and self._reason is not None:
                index["incomplete_reason"] = self._reason
        return index
