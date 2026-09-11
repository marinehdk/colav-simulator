"""Read-only Run Replay evidence store, descriptor and discovery (ticket #70).

This module is the Sealed Run Replay read path. It deliberately imports ONLY
the standard library and :mod:`colav_simulator.decision_replay.bundle` (which
itself is stdlib-only): the replay reader must never import the simulator,
planner, tracker, or evaluator runtime, so "no re-execution" is structural.

Everything here is read-only: Run identity addressing, path confinement under
the configured runs root, truthful evidence classification
(CAPTURING/READY/REDUCED/INCOMPLETE/UNAVAILABLE with typed reasons), run
discovery over ``runs/*/manifest.json``, and LRU retention pruning of
``decision/`` trace directories only.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import shutil
import uuid
from collections.abc import Callable
from enum import StrEnum
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from colav_simulator.decision_replay.bundle import TRACE_SCHEMA, TraceBundle

DESCRIPTOR_SCHEMA = "colav.run-replay.descriptor@1"
RUNS_ROOT_ENV = "COLAV_RUNS_ROOT"
RETENTION_BUDGET_ENV = "COLAV_REPLAY_RETENTION_BUDGET_BYTES"

# Pinned from the #70 measurement (product runs through the new capture path):
# head_on/rule14 VO stores ~2.6 KB/tick and Mid-MPC ~40 KB/tick of decision/
# artifacts; a worst-case ~74 KB/tick multiship trace (measured reference in
# Technical Design section 5.4) at 600 s / 10 Hz stays near 450 MB, so a 4 GiB
# budget holds roughly nine such traces. Override with RETENTION_BUDGET_ENV.
DEFAULT_RETENTION_BUDGET_BYTES = 4 * 1024**3

MAX_LIST_RUNS = 200
MAX_SCAN_DIRS = 5000


class ReplayEvidenceState(StrEnum):
    CAPTURING = "CAPTURING"
    READY = "READY"
    REDUCED = "REDUCED"
    INCOMPLETE = "INCOMPLETE"
    UNAVAILABLE = "UNAVAILABLE"


class ReplayEvidenceReason(StrEnum):
    RUN_NOT_FOUND = "RUN_NOT_FOUND"
    RUN_ID_INVALID = "RUN_ID_INVALID"
    TRACE_MISSING = "TRACE_MISSING"
    TRACE_SCHEMA_UNSUPPORTED = "TRACE_SCHEMA_UNSUPPORTED"
    TRACE_DIGEST_MISMATCH = "TRACE_DIGEST_MISMATCH"
    TRACE_TRUNCATED = "TRACE_TRUNCATED"
    TRACE_INDEX_CORRUPT = "TRACE_INDEX_CORRUPT"
    REDUCED_TRAJECTORY_ONLY = "REDUCED_TRAJECTORY_ONLY"
    TRACE_CAPTURE_DISABLED = "TRACE_CAPTURE_DISABLED"
    TRACE_GAP = "TRACE_GAP"
    TRACE_BUDGET_EXCEEDED = "TRACE_BUDGET_EXCEEDED"
    TRACE_WRITE_FAILED = "TRACE_WRITE_FAILED"
    TRACE_SERIALIZE_FAILED = "TRACE_SERIALIZE_FAILED"


class RunReplayError(Exception):
    """Typed read-path failure mapped to an HTTP status by the router."""

    def __init__(self, status: int, reason: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.reason = reason


def replay_retention_budget_bytes() -> int:
    """Configurable global budget for decision/ trace directories."""
    raw = os.environ.get(RETENTION_BUDGET_ENV, "").strip()
    if raw:
        try:
            return int(raw)
        except ValueError:
            return 0
    return DEFAULT_RETENTION_BUDGET_BYTES


def runs_root() -> Path:
    """Configured Run repository root (overridable for tests/deployments)."""
    return Path(os.environ.get(RUNS_ROOT_ENV, "runs")).resolve()


def _iter_frames(path: Path) -> list[dict[str, Any]]:
    opener = gzip.open if path.suffix == ".gz" else open
    rows = []
    with opener(path, "rt", encoding="utf-8") as stream:  # type: ignore[operator]
        for line in stream:
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    break  # torn final line from a crash: trustworthy prefix only
    return rows


class RunReplayStore:
    """Read-only classification and description of recorded Run evidence."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()
        self._integrity_cache: dict[tuple[str, int, int], dict[str, Any]] = {}

    # -- identity / confinement -------------------------------------------

    def validate_run_id(self, run_id: str) -> str:
        text = str(run_id).strip()
        if "/" in text or "\\" in text or text in {".", ".."}:
            raise RunReplayError(404, ReplayEvidenceReason.RUN_ID_INVALID, "run id is not a valid run identity")
        try:
            parsed = uuid.UUID(text)
        except (ValueError, AttributeError, TypeError):
            raise RunReplayError(404, ReplayEvidenceReason.RUN_ID_INVALID, "run id is not a valid run identity") from None
        if str(parsed) != text.lower():
            raise RunReplayError(404, ReplayEvidenceReason.RUN_ID_INVALID, "run id is not a valid run identity")
        return str(parsed)

    def run_dir(self, run_id: str) -> Path:
        normalized = self.validate_run_id(run_id)
        candidate = (self.root / normalized).resolve()
        if candidate.parent != self.root:
            raise RunReplayError(404, ReplayEvidenceReason.RUN_ID_INVALID, "run id escapes the run repository")
        if not (candidate / "manifest.json").is_file():
            raise RunReplayError(404, ReplayEvidenceReason.RUN_NOT_FOUND, f"run {normalized} not found")
        return candidate

    # -- classification -----------------------------------------------------

    def classify(self, run_dir: Path, *, verify_integrity: bool = True) -> dict[str, Any]:
        """Truthful replay evidence state for one run directory."""
        decision = run_dir / "decision"
        gz = decision / "frames.jsonl.gz"
        plain = decision / "frames.jsonl"
        index_path = decision / "index.json"

        base: dict[str, Any] = {
            "state": ReplayEvidenceState.UNAVAILABLE,
            "evidence_level": None,
            "reason": ReplayEvidenceReason.TRACE_MISSING,
            "trace_schema": None,
            "frame_count": 0,
            "t_start": None,
            "t_end": None,
            "trusted_t_end": None,
            "frames_sha256": None,
            "truncated": None,
        }

        if gz.is_file() and index_path.is_file():
            return self._classify_finalized(run_dir, gz, index_path, verify=verify_integrity, base=base)
        if plain.is_file() or (gz.is_file() and not index_path.is_file()):
            path = plain if plain.is_file() else gz
            frames = _iter_frames(path)
            times = [float(frame.get("sim_time", 0.0)) for frame in frames]
            base.update(
                state=ReplayEvidenceState.INCOMPLETE,
                evidence_level="full",
                reason=ReplayEvidenceReason.TRACE_TRUNCATED,
                trace_schema=TRACE_SCHEMA,
                frame_count=len(frames),
                t_start=times[0] if times else None,
                t_end=times[-1] if times else None,
                trusted_t_end=times[-1] if times else None,
                truncated=True,
            )
            return base

        if (run_dir / "trajectory.parquet").is_file():
            base.update(
                state=ReplayEvidenceState.REDUCED,
                evidence_level="reduced",
                reason=ReplayEvidenceReason.REDUCED_TRAJECTORY_ONLY,
            )
            return base
        base["reason"] = ReplayEvidenceReason.TRACE_MISSING
        return base

    def _classify_finalized(
        self,
        run_dir: Path,
        gz: Path,
        index_path: Path,
        *,
        verify: bool,
        base: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            index = json.loads(index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            base.update(
                state=ReplayEvidenceState.INCOMPLETE,
                evidence_level="full",
                reason=ReplayEvidenceReason.TRACE_INDEX_CORRUPT,
                trace_schema=TRACE_SCHEMA,
                truncated=True,
            )
            return base
        schema = index.get("trace_schema")
        base.update(
            trace_schema=schema,
            frame_count=int(index.get("tick_count") or 0),
            t_start=index.get("t_start"),
            t_end=index.get("t_end"),
            trusted_t_end=index.get("t_end"),
            frames_sha256=index.get("frames_sha256"),
            truncated=bool(index.get("truncated")),
            evidence_level="full",
        )
        if schema != TRACE_SCHEMA:
            base.update(state=ReplayEvidenceState.UNAVAILABLE, reason=ReplayEvidenceReason.TRACE_SCHEMA_UNSUPPORTED)
            return base
        if index.get("truncated"):
            base.update(
                state=ReplayEvidenceState.INCOMPLETE,
                reason=index.get("incomplete_reason", ReplayEvidenceReason.TRACE_TRUNCATED),
            )
            return base
        if verify and not self._integrity_ok(run_dir.name, gz, index):
            base.update(
                state=ReplayEvidenceState.INCOMPLETE,
                reason=ReplayEvidenceReason.TRACE_DIGEST_MISMATCH,
                trusted_t_end=None,
            )
            return base
        base.update(state=ReplayEvidenceState.READY, reason=None)
        return base

    def _integrity_ok(self, run_id: str, gz: Path, index: dict[str, Any]) -> bool:
        stat = gz.stat()
        cache_key = (run_id, stat.st_mtime_ns, stat.st_size)
        cached = self._integrity_cache.get(cache_key)
        if cached is None:
            try:
                digest = hashlib.sha256(gzip.decompress(gz.read_bytes())).hexdigest()
            except (OSError, EOFError):
                return False
            cached = {"digest": digest}
            self._integrity_cache[cache_key] = cached
            if len(self._integrity_cache) > 64:
                self._integrity_cache.clear()
        return cached["digest"] == index.get("frames_sha256")

    # -- descriptor ----------------------------------------------------------

    def descriptor(self, run_id: str, *, active: dict[str, Any] | None = None) -> dict[str, Any]:
        run_dir = self.run_dir(run_id)
        manifest = self._read_json(run_dir / "manifest.json") or {}
        spec = manifest.get("spec") or {}
        facts = self.classify(run_dir)
        if active is not None and active.get("state") == ReplayEvidenceState.CAPTURING.value:
            # The active manager owns capture truth while the disk only has a
            # partial prefix; its state overrides the naive disk classification.
            facts = {
                **facts,
                "state": ReplayEvidenceState.CAPTURING,
                "evidence_level": "full",
                "reason": active.get("reason"),
                "frame_count": active.get("frame_count", facts.get("frame_count", 0)),
                "trace_schema": TRACE_SCHEMA,
            }
        elif active is not None:
            facts = {**facts, **{key: value for key, value in active.items() if value is not None}}
        state = ReplayEvidenceState(facts["state"]) if facts.get("state") else ReplayEvidenceState.UNAVAILABLE
        full = state is ReplayEvidenceState.READY
        capturing = state is ReplayEvidenceState.CAPTURING
        bundle = TraceBundle(run_dir)
        events = bundle.events()
        categories = sorted({str(event.get("type", "?")) for event in events})
        return {
            "schema_version": DESCRIPTOR_SCHEMA,
            "run_id": run_dir.name,
            "run": {
                "execution_state": manifest.get("state"),
                "scenario_id": spec.get("scenario_id") or manifest.get("scenario_id"),
                "requested_algorithm": manifest.get("requested_algorithm"),
                "executed_algorithm": manifest.get("executed_algorithm"),
                "requested_tracker": manifest.get("requested_tracker"),
                "executed_tracker": manifest.get("executed_tracker"),
                "validation_rule_id": manifest.get("validation_rule_id"),
                "created_at_utc": manifest.get("created_at_utc"),
                "result_ready": (run_dir / "evaluation.json").is_file(),
            },
            "replay": {
                "state": state.value,
                "evidence_level": facts.get("evidence_level"),
                "reason": facts.get("reason"),
                "trace_schema": facts.get("trace_schema"),
                "frame_count": facts.get("frame_count", 0),
                "t_start": facts.get("t_start"),
                "t_end": facts.get("t_end"),
                "trusted_t_end": facts.get("trusted_t_end"),
                "frames_sha256": facts.get("frames_sha256"),
                "truncated": facts.get("truncated"),
            },
            "events": {
                "count": len(events),
                "categories": categories,
            },
            "capabilities": {
                "full_frame": bool(full or capturing),
                "planner_detail": bool(full),
                "risk_detail": bool(full),
                "continuous_interpolation": bool(full),
            },
        }

    # -- discovery -----------------------------------------------------------

    def list_runs(self, *, replayable: bool | None = None, limit: int = 50) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), MAX_LIST_RUNS))
        entries: list[dict[str, Any]] = []
        if not self.root.is_dir():
            return []
        scanned = 0
        for child in self.root.iterdir():
            scanned += 1
            if scanned > MAX_SCAN_DIRS:
                break
            manifest_path = child / "manifest.json"
            if not child.is_dir() or not manifest_path.is_file():
                continue
            manifest = self._read_json(manifest_path) or {}
            spec = manifest.get("spec") or {}
            facts = self.classify(child, verify_integrity=False)
            entries.append(
                {
                    "run_id": child.name,
                    "created_at_utc": manifest.get("created_at_utc"),
                    "scenario_id": spec.get("scenario_id"),
                    "requested_algorithm": manifest.get("requested_algorithm"),
                    "executed_algorithm": manifest.get("executed_algorithm"),
                    "executed_tracker": manifest.get("executed_tracker"),
                    "execution_state": manifest.get("state"),
                    "replay": {
                        "state": facts["state"],
                        "evidence_level": facts["evidence_level"],
                        "reason": facts["reason"],
                        "frame_count": facts["frame_count"],
                        "t_start": facts["t_start"],
                        "t_end": facts["t_end"],
                    },
                }
            )
        entries.sort(key=lambda entry: entry.get("created_at_utc") or "", reverse=True)
        if replayable:
            entries = [entry for entry in entries if entry["replay"]["state"] == ReplayEvidenceState.READY.value]
        return entries[:limit]

    # -- retention -----------------------------------------------------------

    def prune_traces(
        self,
        *,
        budget_bytes: int,
        keep_run_ids: frozenset[str] = frozenset(),
        log_event: Callable[[Path, dict[str, Any]], None] | None = None,
    ) -> list[str]:
        """LRU-prune oldest finalized decision/ dirs until within budget.

        Only replay evidence directories are removed; manifests, trajectories,
        reports and artifacts are never touched, and directories without a
        finalized index.json (still capturing, or crashed) are never pruned.
        """
        pruned: list[str] = []
        if budget_bytes <= 0 or not self.root.is_dir():
            return pruned
        candidates: list[tuple[float, str, Path, int]] = []
        scanned = 0
        for child in self.root.iterdir():
            scanned += 1
            if scanned > MAX_SCAN_DIRS:
                break
            index_path = child / "decision" / "index.json"
            if not child.is_dir() or not index_path.is_file() or child.name in keep_run_ids:
                continue
            decision = child / "decision"
            size = sum(path.stat().st_size for path in decision.rglob("*") if path.is_file())
            candidates.append((index_path.stat().st_mtime, child.name, decision, size))
        total = sum(size for _, _, _, size in candidates)
        candidates.sort(key=lambda entry: entry[0])
        for _, run_id, decision, size in candidates:
            if total <= budget_bytes:
                break
            shutil.rmtree(decision, ignore_errors=False)
            total -= size
            pruned.append(run_id)
            if log_event is not None:
                log_event(
                    self.root / run_id,
                    {
                        "type": "replay_trace_pruned",
                        "schema_version": "replay-retention.v1",
                        "run_id": run_id,
                        "bytes_freed": size,
                        "budget_bytes": budget_bytes,
                    },
                )
        return pruned

    def _read_json(self, path: Path) -> dict[str, Any] | None:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None


def build_replay_router(
    store: RunReplayStore,
    *,
    active_replay_status: Callable[[str], dict[str, Any] | None] | None = None,
    default_limit: int = 50,
) -> APIRouter:
    """Read-only Run Replay routes; replay state is never mutated over HTTP."""

    def _active(run_id: str) -> dict[str, Any] | None:
        if active_replay_status is None:
            return None
        try:
            return active_replay_status(run_id)
        except Exception:  # noqa: BLE001 - the descriptor must stay read-only even if the hook fails
            return None

    router = APIRouter(prefix="/api")

    @router.get("/runs")
    def list_runs(
        replayable: bool | None = Query(default=None),
        limit: int = Query(default=max(1, min(default_limit, MAX_LIST_RUNS)), ge=1, le=MAX_LIST_RUNS),
    ) -> list[dict[str, Any]]:
        return store.list_runs(replayable=replayable, limit=limit)

    @router.get("/runs/{run_id}/replay")
    def descriptor(run_id: str) -> dict[str, Any]:
        try:
            return store.descriptor(run_id, active=_active(run_id))
        except RunReplayError as exc:
            raise HTTPException(
                status_code=exc.status,
                detail={"reason": str(exc.reason), "message": str(exc)},
            ) from exc

    return router
