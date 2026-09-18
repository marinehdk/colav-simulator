"""Lazy offline reader for one recorded decision trace."""

from __future__ import annotations

import bisect
import gzip
import json
import math
import mmap
import re
import tempfile
import threading
import zlib
from bisect import bisect_right
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from colav_simulator.decision_replay.chart import ChartBlockDecoder

TRACE_SCHEMA = "colav.decision-replay.v1"

# Derived read index (Technical Design §5.3, ticket #71): a rebuildable,
# in-memory decoded buffer so frequent UI scrubbing does not re-decompress the
# gzip from the start for every random frame seek. It is a cache only — the
# v1 artifacts remain the sole evidence and every code path falls back to the
# streaming reader when the cache is unavailable.
# #75 measured the real full Mid-MPC trace at 309 MB raw (83 MB gz): a 256 MiB
# cap silently disabled the buffer and degraded warm random seeks to ~650 ms
# median (full re-decompression per seek). 512 MiB holds the representative
# full trace; larger traces spill to an anonymous disk-backed mapping.
MAX_DECODED_TRACE_BYTES = 512 * 1024 * 1024
_SIM_TIME_PATTERN = re.compile(rb'"sim_time":\s*(-?[0-9][0-9.eE+-]*)')


class TraceBundle:
    """Read-only view over ``runs/<run_id>``; no simulator imports needed.

    ``full`` evidence level means ``decision/frames.jsonl.gz`` exists (recorded
    by :mod:`colav_simulator.decision_replay.recorder`). Legacy run directories
    degrade to ``reduced``: only the persisted event journal is available.
    """

    def __init__(self, run_dir: Path) -> None:
        self.run_dir = Path(run_dir)
        self.trace_dir = self.run_dir / "decision"
        self._frames_path = self.trace_dir / "frames.jsonl.gz"
        if not self._frames_path.is_file():
            self._frames_path = self.trace_dir / "frames.jsonl"
        self._offsets: list[int] = []
        self._times: list[float] = []
        self._positions: list[dict[str, Any]] = []
        self._scanned = False
        self._events_cache: list[dict[str, Any]] | None = None
        self._decoded: bytes | mmap.mmap | None = None
        self._decoded_file = None
        self._decode_lock = threading.Lock()
        self._decoded_unavailable = False
        self._chart_decoder = ChartBlockDecoder()
        self._chart_blocks_loaded = False
        self._validation: tuple[tuple[Any, ...], dict[str, Any]] | None = None

    @property
    def evidence_level(self) -> str:
        return "full" if self._frames_path.is_file() else "reduced"

    @property
    def run_id(self) -> str:
        return self.run_dir.name

    def manifest(self) -> dict[str, Any]:
        path = self.run_dir / "manifest.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}

    def episode(self) -> dict[str, Any]:
        path = self.run_dir / "episode.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}

    def index(self) -> dict[str, Any]:
        path = self.trace_dir / "index.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}

    def _decoded_bytes(self) -> bytes | mmap.mmap | None:
        """Decode once, spilling large traces to an anonymous disk seek cache."""
        with self._decode_lock:
            if self._decoded is not None or self._decoded_unavailable:
                return self._decoded
            if not self._frames_path.is_file():
                self._decoded_unavailable = True
                return None
            opener = gzip.open if self._frames_path.suffix == ".gz" else open
            cache = None
            try:
                with opener(self._frames_path, "rb") as stream:
                    data = stream.read(MAX_DECODED_TRACE_BYTES + 1)
                    if len(data) <= MAX_DECODED_TRACE_BYTES:
                        self._decoded = data
                    else:
                        cache = tempfile.TemporaryFile()
                        cache.write(data)
                        del data
                        while chunk := stream.read(1024 * 1024):
                            cache.write(chunk)
                        cache.flush()
                        self._decoded = mmap.mmap(cache.fileno(), 0, access=mmap.ACCESS_READ)
                        self._decoded_file = cache
            except (OSError, EOFError, zlib.error):
                if cache is not None:
                    cache.close()
                self._decoded_unavailable = True
            return self._decoded

    def _scan(self) -> None:
        if self._scanned:
            return
        decoded = self._decoded_bytes()
        if decoded is not None:
            offset = 0
            while offset < len(decoded):
                end = decoded.find(b"\n", offset)
                end = len(decoded) if end == -1 else end
                if decoded[offset:end].strip():
                    self._offsets.append(offset)
                offset = end + 1
            self._scanned = True
            return
        if not self._frames_path.is_file():
            self._scanned = True
            return
        opener = gzip.open if self._frames_path.suffix == ".gz" else open
        try:
            with opener(self._frames_path, "rt", encoding="utf-8") as stream:  # type: ignore[operator]
                offset = 0
                for line in stream:
                    if line.strip():
                        self._offsets.append(offset)
                    offset += len(line.encode("utf-8"))
        except (OSError, EOFError, UnicodeDecodeError, zlib.error):
            # A controlled crash or torn gzip trailer may still leave a
            # readable prefix. Validation determines its trusted boundary;
            # indexing stops at the bytes the stream could actually read.
            pass
        self._scanned = True

    def _load_times(self) -> None:
        self._scan()
        if self._times or not self._offsets:
            return
        decoded = self._decoded_bytes()
        if decoded is not None:
            for offset in self._offsets:
                end = decoded.find(b"\n", offset)
                line = decoded[offset:] if end == -1 else decoded[offset:end]
                match = _SIM_TIME_PATTERN.search(line)
                self._times.append(float(match.group(1)) if match else 0.0)
            return
        for record in self.frames():
            self._times.append(float(record.get("sim_time", 0.0)))

    @property
    def tick_count(self) -> int:
        self._scan()
        return len(self._offsets)

    def frames(self) -> Iterator[dict[str, Any]]:
        """Lazy iterate every recorded tick: {sequence, sim_time, payload, events, ...}."""
        if not self._frames_path.is_file():
            return
        opener = gzip.open if self._frames_path.suffix == ".gz" else open
        decoder = ChartBlockDecoder()
        with opener(self._frames_path, "rt", encoding="utf-8") as stream:  # type: ignore[operator]
            for line in stream:
                if line.strip():
                    yield decoder.decode(json.loads(line))

    def validate(  # noqa: PLR0915 - keep prefix trust and chart decoding in one pass
        self,
        *,
        expected_count: int | None = None,
        expected_t_start: float | None = None,
        expected_t_end: float | None = None,
    ) -> dict[str, Any]:
        """Validate the recorded prefix and optional finalized index facts.

        The trace is a seek index only when frame sequence starts at one and
        remains contiguous, simulation time is finite and strictly increasing,
        and the supplied index count/bounds agree with the records.  A caller
        may still use ``trusted_frame_count`` and ``trusted_t_end`` when the
        first invalid record leaves a verifiable prefix.  This method does not
        validate the digest; the replay store owns that artifact-level check.
        """
        validation_key = (expected_count, expected_t_start, expected_t_end)
        if self._validation is not None and self._validation[0] == validation_key:
            return self._validation[1]

        self._positions = []
        parsed_count = 0
        trusted_count = 0
        first_time: float | None = None
        last_time: float | None = None
        trusted_end: float | None = None
        reason: str | None = None
        expected_sequence = 1
        populate_times = not self._times
        self._chart_decoder = ChartBlockDecoder()

        if not self._frames_path.is_file():
            result = {
                "valid": False,
                "reason": "TRACE_MISSING",
                "frame_count": 0,
                "trusted_frame_count": 0,
                "t_start": None,
                "t_end": None,
                "trusted_t_end": None,
            }
            self._validation = (validation_key, result)
            return result

        opener = gzip.open if self._frames_path.suffix == ".gz" else open
        try:
            with opener(self._frames_path, "rt", encoding="utf-8") as stream:  # type: ignore[operator]
                for line in stream:
                    if not line.strip():
                        continue
                    try:
                        record = self._chart_decoder.decode(json.loads(line))
                    except (TypeError, ValueError):
                        reason = reason or "TRACE_FRAME_INVALID"
                        break
                    parsed_count += 1
                    sim_time = self._finite_sim_time(record)
                    if populate_times:
                        self._times.append(sim_time if sim_time is not None else math.nan)
                    if sim_time is not None:
                        if first_time is None:
                            first_time = sim_time
                        last_time = sim_time
                    if reason is not None:
                        continue
                    frame_reason, validated_time = self._validate_frame(
                        record,
                        expected_sequence=expected_sequence,
                        previous_time=trusted_end,
                    )
                    if frame_reason is not None:
                        reason = frame_reason
                        continue
                    self._positions.append(
                        {
                            "sequence": record["sequence"],
                            "sim_time": sim_time,
                            "payload": {
                                key: {"id": ship.get("id"), "state": ship["state"][:2]}
                                for key, ship in (record.get("payload") or {}).items()
                                if isinstance(ship, dict) and isinstance(ship.get("state"), list) and len(ship["state"]) >= 2
                            },
                        }
                    )
                    trusted_count += 1
                    expected_sequence += 1
                    trusted_end = validated_time
        except (OSError, EOFError, UnicodeDecodeError, zlib.error):
            reason = reason or "TRACE_FRAME_READ_FAILED"

        # Index metadata is only meaningful after the records themselves are
        # structurally sound. A mismatching summary downgrades readiness, but
        # the parsed frame prefix remains independently verifiable.
        if reason is None:
            reason = self._index_mismatch(
                expected_count=expected_count,
                expected_t_start=expected_t_start,
                expected_t_end=expected_t_end,
                frame_count=parsed_count,
                t_start=first_time,
                t_end=last_time,
            )

        result = {
            "valid": reason is None,
            "reason": reason,
            "frame_count": parsed_count,
            "trusted_frame_count": trusted_count,
            "t_start": first_time,
            "t_end": last_time,
            "trusted_t_end": trusted_end,
        }
        self._validation = (validation_key, result)
        self._chart_blocks_loaded = True
        return result

    @staticmethod
    def _finite_sim_time(record: Any) -> float | None:
        if not isinstance(record, dict):
            return None
        raw_time = record.get("sim_time")
        if isinstance(raw_time, bool) or not isinstance(raw_time, (int, float)):
            return None
        try:
            value = float(raw_time)
        except (OverflowError, TypeError, ValueError):
            return None
        return value if math.isfinite(value) else None

    @staticmethod
    def _validate_frame(
        record: Any,
        *,
        expected_sequence: int,
        previous_time: float | None,
    ) -> tuple[str | None, float | None]:
        if not isinstance(record, dict):
            return "TRACE_FRAME_INVALID", None
        sequence = record.get("sequence")
        if isinstance(sequence, bool) or not isinstance(sequence, int):
            return "TRACE_SEQUENCE_INVALID", None
        if sequence != expected_sequence:
            return "TRACE_SEQUENCE_GAP", None
        raw_time = record.get("sim_time")
        if isinstance(raw_time, bool) or not isinstance(raw_time, (int, float)):
            return "TRACE_TIME_INVALID", None
        try:
            sim_time = float(raw_time)
        except (OverflowError, TypeError, ValueError):
            return "TRACE_TIME_INVALID", None
        if not math.isfinite(sim_time) or sim_time < 0.0:
            return "TRACE_TIME_INVALID", None
        if previous_time is not None and sim_time <= previous_time:
            return "TRACE_TIME_REGRESSION", None
        return None, sim_time

    @staticmethod
    def _index_mismatch(
        *,
        expected_count: int | None,
        expected_t_start: float | None,
        expected_t_end: float | None,
        frame_count: int,
        t_start: float | None,
        t_end: float | None,
    ) -> str | None:
        if expected_count is not None and expected_count != frame_count:
            return "TRACE_INDEX_MISMATCH"
        try:
            start_finite = expected_t_start is None or math.isfinite(float(expected_t_start))
            end_finite = expected_t_end is None or math.isfinite(float(expected_t_end))
        except (OverflowError, TypeError, ValueError):
            return "TRACE_INDEX_MISMATCH"
        if not start_finite or not end_finite:
            return "TRACE_INDEX_MISMATCH"
        if expected_t_start is not None and (t_start is None or expected_t_start != t_start):
            return "TRACE_INDEX_MISMATCH"
        if expected_t_end is not None and (t_end is None or expected_t_end != t_end):
            return "TRACE_INDEX_MISMATCH"
        return None

    def position_history(self, before_sequence: int, *, limit: int = 120) -> list[dict[str, Any]]:
        """Compact trusted positions preceding a window; populated during validation."""
        end = max(0, min(before_sequence - 1, len(self._positions)))
        return self._positions[max(0, end - limit) : end]

    def frame(self, sequence: int) -> dict[str, Any]:
        """One tick record by 1-based frame sequence (the recorder's first tick is 1)."""
        self._scan()
        if not self._offsets:
            raise IndexError(f"no recorded frames in {self.run_dir}")
        position = max(0, min(sequence - 1, len(self._offsets) - 1))
        return self._frame_at(self._offsets[position])

    def _frame_at(self, offset: int) -> dict[str, Any]:
        decoded = self._decoded_bytes()
        if decoded is not None:
            end = decoded.find(b"\n", offset)
            line = decoded[offset:] if end == -1 else decoded[offset:end]
            return self._expand_chart_frame(json.loads(line))
        opener = gzip.open if self._frames_path.suffix == ".gz" else open
        with opener(self._frames_path, "rt", encoding="utf-8") as stream:  # type: ignore[operator]
            stream.seek(offset)
            return self._expand_chart_frame(json.loads(stream.readline()))

    def _expand_chart_frame(self, record: dict[str, Any]) -> dict[str, Any]:
        if "storage_schema" not in record:
            return record
        if not self._chart_blocks_loaded:
            self.validate()
        return self._chart_decoder.decode(record)

    def seq_at_time(self, sim_time: float, *, max_sequence: int | None = None) -> int:
        """Frame sequence at or before ``sim_time`` (1-based; 0 when before start)."""
        self._load_times()
        limit = len(self._times) if max_sequence is None else max(0, min(max_sequence, len(self._times)))
        if limit == 0:
            return 0
        return max(1, min(limit, bisect_right(self._times[:limit], sim_time)))

    def window(self, t0: float, t1: float, *, max_sequence: int | None = None) -> list[dict[str, Any]]:
        self._load_times()
        limit = len(self._times) if max_sequence is None else max(0, min(max_sequence, len(self._times)))
        if limit == 0:
            return []
        times = self._times[:limit]
        start = bisect.bisect_left(times, t0)
        stop = bisect.bisect_right(times, t1)
        return [self._frame_at(self._offsets[i]) for i in range(start, max(start, stop))]

    def events(self) -> list[dict[str, Any]]:
        """Merged event journal: recorded mirror first (plain or gz), legacy run events as fallback."""
        if self._events_cache is not None:
            return self._events_cache
        for candidate in (
            self.trace_dir / "events.jsonl",
            self.trace_dir / "events.jsonl.gz",
            self.run_dir / "events.jsonl",
        ):
            if candidate.is_file():
                opener = gzip.open if candidate.suffix == ".gz" else open
                rows = []
                with opener(candidate, "rt", encoding="utf-8") as stream:  # type: ignore[operator]
                    for line in stream:
                        if line.strip():
                            rows.append(json.loads(line))
                self._events_cache = rows
                return rows
        self._events_cache = []
        return self._events_cache

    def summary(self) -> dict[str, Any]:
        manifest = self.manifest()
        index = self.index()
        event_counts: dict[str, int] = {}
        for event in self.events():
            event_counts[event.get("type", "?")] = event_counts.get(event.get("type", "?"), 0) + 1
        return {
            "run_id": self.run_id,
            "run_dir": str(self.run_dir),
            "evidence_level": self.evidence_level,
            "tick_count": self.tick_count,
            "t_start": index.get("t_start"),
            "t_end": index.get("t_end"),
            "truncated": index.get("truncated"),
            "scenario": manifest.get("scenario_id"),
            "algorithm": manifest.get("executed_algorithm"),
            "tracker": manifest.get("executed_tracker_id"),
            "state": manifest.get("state"),
            "event_counts": event_counts,
        }
