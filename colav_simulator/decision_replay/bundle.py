"""Lazy offline reader for one recorded decision trace."""

from __future__ import annotations

import bisect
import gzip
import json
from bisect import bisect_right
from collections.abc import Iterator
from pathlib import Path
from typing import Any


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
        self._scanned = False
        self._events_cache: list[dict[str, Any]] | None = None

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

    def _scan(self) -> None:
        if self._scanned:
            return
        if not self._frames_path.is_file():
            self._scanned = True
            return
        opener = gzip.open if self._frames_path.suffix == ".gz" else open
        with opener(self._frames_path, "rt", encoding="utf-8") as stream:  # type: ignore[operator]
            offset = 0
            for line in stream:
                if line.strip():
                    self._offsets.append(offset)
                offset += len(line.encode("utf-8"))
        self._scanned = True

    def _load_times(self) -> None:
        self._scan()
        if self._times or not self._offsets:
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
        with opener(self._frames_path, "rt", encoding="utf-8") as stream:  # type: ignore[operator]
            for line in stream:
                if line.strip():
                    yield json.loads(line)

    def frame(self, sequence: int) -> dict[str, Any]:
        """One tick record by 1-based frame sequence (the recorder's first tick is 1)."""
        self._scan()
        if not self._offsets:
            raise IndexError(f"no recorded frames in {self.run_dir}")
        position = max(0, min(sequence - 1, len(self._offsets) - 1))
        return self._frame_at(self._offsets[position])

    def _frame_at(self, offset: int) -> dict[str, Any]:
        opener = gzip.open if self._frames_path.suffix == ".gz" else open
        with opener(self._frames_path, "rt", encoding="utf-8") as stream:  # type: ignore[operator]
            stream.seek(offset)
            return json.loads(stream.readline())

    def seq_at_time(self, sim_time: float) -> int:
        """Frame sequence at or before ``sim_time`` (1-based; 0 when before start)."""
        self._load_times()
        if not self._times:
            return 0
        return max(1, bisect_right(self._times, sim_time))

    def window(self, t0: float, t1: float) -> list[dict[str, Any]]:
        self._load_times()
        if not self._times:
            return []
        start = bisect.bisect_left(self._times, t0)
        stop = bisect.bisect_right(self._times, t1)
        return [self._frame_at(self._offsets[i]) for i in range(start, max(start, stop))]

    def events(self) -> list[dict[str, Any]]:
        """Merged event journal: recorded mirror first, legacy run events as fallback."""
        if self._events_cache is not None:
            return self._events_cache
        for candidate in (self.trace_dir / "events.jsonl", self.run_dir / "events.jsonl"):
            if candidate.is_file():
                rows = []
                for line in candidate.read_text(encoding="utf-8").splitlines():
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
