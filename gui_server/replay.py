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
import logging
import math
import os
import shutil
import uuid
from collections.abc import Callable
from contextlib import contextmanager
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from colav_simulator.decision_replay.bundle import TRACE_SCHEMA, TraceBundle

if TYPE_CHECKING:  # annotation-only: keeps the sealed read path import-clean
    from colav_simulator.decision_replay.sink import TraceSinkPolicy
from gui_server.canonical_threat import canonical_threat_projection

DESCRIPTOR_SCHEMA = "colav.run-replay.descriptor@1"
WINDOW_SCHEMA = "colav.run-replay.window@1"
EVENTS_SCHEMA = "colav.run-replay.events@1"
CONTEXT_SCHEMA = "colav.run-replay.context@1"
STATIC_CONTEXT_SCHEMA = "colav.run-replay.static-context@1"
STATIC_CONTEXT_FILENAME = "static_context.json"
RUNS_ROOT_ENV = "COLAV_RUNS_ROOT"
RETENTION_BUDGET_ENV = "COLAV_REPLAY_RETENTION_BUDGET_BYTES"

# Window/request bounds (#71 §7.1): replay reads are bounded; exceeding a bound
# is a typed rejection, never an unbounded transfer or a silent clamp.
MAX_WINDOW_SPAN_S = 120.0
MAX_WINDOW_FRAMES = 1000
DEFAULT_EVENTS_LIMIT = 2000
MAX_EVENTS_LIMIT = 20000


# Shared capture policy (#70, shared here in #74 so the Historical AIS
# workflow path and the product WebSessionManager path use ONE budget).
DEFAULT_CAPTURE_BUDGET_BYTES = 2 * 1024**3
CAPTURE_BUDGET_ENV = "COLAV_REPLAY_CAPTURE_BUDGET_BYTES"

_log = logging.getLogger(__name__)


def replay_capture_budget_policy() -> TraceSinkPolicy:
    """Per-Run capture byte budget; exceeding it is a typed INCOMPLETE reason.

    The TraceSinkPolicy import is deliberately function-local: gui_server.replay
    is the SEALED READ PATH and must stay free of anything that transitively
    imports simulator/planner runtime (sink -> experiment.contracts ->
    core.colav). Only the capture (write) side calls this (#75 probe-tested).
    """
    from colav_simulator.decision_replay.sink import TraceSinkPolicy  # noqa: PLC0415

    max_bytes = DEFAULT_CAPTURE_BUDGET_BYTES
    raw = os.environ.get(CAPTURE_BUDGET_ENV, "").strip()
    if raw:
        try:
            override = int(raw)
        except ValueError:
            override = 0
        if override > 0:
            max_bytes = override
        else:
            _log.warning(
                "Ignoring invalid %s=%r; using the %d-byte default capture budget",
                CAPTURE_BUDGET_ENV,
                raw,
                DEFAULT_CAPTURE_BUDGET_BYTES,
            )
    # Measured on #70: the raw events.jsonl journal dominates the stored trace
    # for VO runs, so the journal is stored gzipped; readers accept both forms.
    return TraceSinkPolicy(max_total_bytes=max_bytes, events_gzip=True)


class EventCategories:
    """Backend-owned marker categories for the #73 replay timeline.

    Deterministic mapping from the RECORDED event type to one presentation
    category. This is a labeling projection for markers — never a second
    event stream, and recorded identity/order/details are returned untouched.
    """

    RISK_LIFECYCLE = "RISK_LIFECYCLE"
    PLANNER = "PLANNER"
    SAFETY_FAILURE = "SAFETY_FAILURE"
    MISSION = "MISSION"
    HANDOFF = "HANDOFF"
    RUNTIME = "RUNTIME"

    _PATTERNS: tuple[tuple[tuple[str, ...], str], ...] = (
        (("collision", "grounding", "failure", "failed"), SAFETY_FAILURE),
        (("planner", "solve", "mpc", "vo_", "fallback"), PLANNER),
        (("threat", "risk", "encounter", "lifecycle", "avoidance", "primary"), RISK_LIFECYCLE),
        (("goal", "time_limit", "recovery", "mission"), MISSION),
        (("handoff", "algorithm"), HANDOFF),
    )

    def categorize(self, event_type: str) -> str:
        lowered = event_type.lower()
        for patterns, category in self._PATTERNS:
            if any(pattern in lowered for pattern in patterns):
                return category
        return self.RUNTIME


EVENT_CATEGORIES = EventCategories()

# Derived read cache (#71 measurement, Tech Design §5.3): decoded trace buffers
# are derived, rebuildable, in-memory only, and never replace the v1 evidence.
# Two cached Runs bound worst-case memory for a local single-inspector
# server. #75 measured the real full Mid-MPC trace (83 MB gz / ~344 MB raw):
# a 256 MB cap DISABLED the buffer and pushed warm random seeks back to
# ~640 ms median (full gzip re-decompression per seek), so the cap is sized
# to hold the representative full trace (512 MB) — worst case 2x512 MB,
# bounded and LRU-evicted, falling back to streaming beyond that.
MAX_CACHED_BUNDLES = 2
MAX_DECODED_TRACE_BYTES = 512 * 1024 * 1024

# The replay reader is project-root anchored exactly like the writer: the
# runner resolves a relative ``RunSpec.output_root`` against the project root
# (colav_simulator/experiment/runner.py), so discovery must never follow the
# process cwd or it would read a different directory than runs are written to.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Pinned from the #70 measurement (product runs through the new capture path):
# head_on/rule14 VO stores ~2.6 KB/tick and Mid-MPC ~40 KB/tick of decision/
# artifacts; a worst-case ~74 KB/tick multiship trace (measured reference in
# Technical Design section 5.4) at 600 s / 10 Hz stays near 450 MB, so a 4 GiB
# budget holds roughly nine such traces. Override with RETENTION_BUDGET_ENV.
DEFAULT_RETENTION_BUDGET_BYTES = 4 * 1024**3

MAX_LIST_RUNS = 200
MAX_SCAN_DIRS = 5000

log = logging.getLogger(__name__)


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
    """Configurable global budget for decision/ trace directories.

    A valid positive ``RETENTION_BUDGET_ENV`` sets the budget; anything else
    (unparsable, zero, negative) falls back to the documented default so a
    garbage value can never silently disable retention.
    """
    raw = os.environ.get(RETENTION_BUDGET_ENV, "").strip()
    if not raw:
        return DEFAULT_RETENTION_BUDGET_BYTES
    try:
        budget = int(raw)
    except ValueError:
        budget = 0
    if budget <= 0:
        log.warning(
            "Ignoring invalid %s=%r; using the %d-byte default retention budget",
            RETENTION_BUDGET_ENV,
            raw,
            DEFAULT_RETENTION_BUDGET_BYTES,
        )
        return DEFAULT_RETENTION_BUDGET_BYTES
    return budget


def runs_root() -> Path:
    """Configured Run repository root; anchored like the writer (not the cwd).

    Defaults to the project-root ``runs/`` directory the runner writes into
    (matching its relative ``output_root`` resolution); ``RUNS_ROOT_ENV``
    overrides for tests/deployments.
    """
    override = os.environ.get(RUNS_ROOT_ENV, "").strip()
    if override:
        return Path(override).resolve()
    return (PROJECT_ROOT / "runs").resolve()


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
        # Derived, stat-keyed reader cache: keeps TraceBundle instances (and
        # their decoded buffers) alive across requests so random seeks do not
        # re-decompress the whole gzip per frame. Never authoritative.
        self._bundles: dict[str, tuple[tuple[int, int], TraceBundle]] = {}

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

    # -- seekable evidence (ticket #71) --------------------------------------

    def _bundle(self, run_dir: Path) -> TraceBundle:
        frames_path = run_dir / "decision" / "frames.jsonl.gz"
        if not frames_path.is_file():
            frames_path = run_dir / "decision" / "frames.jsonl"
        stat = frames_path.stat()
        key = (stat.st_mtime_ns, stat.st_size)
        cached = self._bundles.get(run_dir.name)
        if cached is not None and cached[0] == key:
            return cached[1]
        bundle = TraceBundle(run_dir)
        if len(self._bundles) >= MAX_CACHED_BUNDLES:
            self._bundles.clear()
        self._bundles[run_dir.name] = (key, bundle)
        return bundle

    def _seekable_run(self, run_id: str) -> tuple[Path, TraceBundle]:
        """Run directory plus reader, gated to truthfully READY evidence."""
        run_dir = self.run_dir(run_id)
        facts = self.classify(run_dir)
        if facts.get("state") != ReplayEvidenceState.READY.value:
            reason = str(facts.get("reason") or ReplayEvidenceReason.TRACE_MISSING)
            raise RunReplayError(409, reason, f"run {run_dir.name} has no seekable replay evidence")
        return run_dir, self._bundle(run_dir)

    @staticmethod
    def _validate_window_range(from_s: float, to_s: float) -> None:
        for name, value in (("from", from_s), ("to", to_s)):
            if not math.isfinite(value):
                raise RunReplayError(422, "REPLAY_RANGE_INVALID", f"replay window {name} must be a finite time")
        if from_s < 0.0:
            raise RunReplayError(422, "REPLAY_RANGE_INVALID", "replay window from must not be negative")
        if to_s < from_s:
            raise RunReplayError(422, "REPLAY_RANGE_INVALID", "replay window to must not precede from")
        if to_s - from_s > MAX_WINDOW_SPAN_S:
            raise RunReplayError(
                422,
                "REPLAY_WINDOW_TOO_LARGE",
                f"replay window span exceeds the frozen {MAX_WINDOW_SPAN_S} s bound",
            )

    def window(self, run_id: str, from_s: float, to_s: float) -> dict[str, Any]:
        """Bounded recorded frame window with explicit predecessor/successor."""
        self._validate_window_range(from_s, to_s)
        run_dir, bundle = self._seekable_run(run_id)
        frames = bundle.window(from_s, to_s)
        if len(frames) > MAX_WINDOW_FRAMES:
            raise RunReplayError(
                422,
                "REPLAY_WINDOW_TOO_LARGE",
                f"replay window exceeds the frozen {MAX_WINDOW_FRAMES}-frame bound",
            )

        def bracket(sequence: int | None) -> dict[str, Any] | None:
            if sequence is None or sequence < 1:
                return None
            candidate = bundle.frame(sequence)
            if candidate.get("sequence") != sequence:
                return None
            return candidate

        if frames:
            before = bracket(int(frames[0]["sequence"]) - 1)
            after_sequence = bundle.seq_at_time(math.nextafter(to_s, math.inf)) + 1
        else:
            last_at_or_before = bundle.seq_at_time(from_s)
            candidate_at_or_before = bracket(last_at_or_before)
            if candidate_at_or_before is not None and float(candidate_at_or_before.get("sim_time", 0.0)) > from_s:
                candidate_at_or_before = None
            before = candidate_at_or_before
            after_sequence = bundle.seq_at_time(math.nextafter(to_s, math.inf)) + 1
        after = bracket(after_sequence)
        if after is not None and float(after.get("sim_time", 0.0)) <= to_s:
            after = None
        return {
            "schema_version": WINDOW_SCHEMA,
            "run_id": run_dir.name,
            "requested": {"from_s": from_s, "to_s": to_s},
            "frames": frames,
            "before": before,
            "after": after,
        }

    def replay_events(self, run_id: str, limit: int) -> dict[str, Any]:
        """Canonical recorded event journal; order/identity/time are evidence.

        ``category`` is a backend-owned presentation label derived
        deterministically from the recorded event type (#73 timeline markers).
        It is additive metadata — identity, sim time, order and details are
        the recorded rows, never rewritten.
        """
        _, bundle = self._seekable_run(run_id)
        rows = bundle.events()
        capped = max(1, min(int(limit), MAX_EVENTS_LIMIT))
        events = []
        for row in rows[:capped]:
            labeled = dict(row)
            labeled["category"] = EVENT_CATEGORIES.categorize(str(row.get("type", "")))
            events.append(labeled)
        present = sorted({event["category"] for event in events})
        return {
            "schema_version": EVENTS_SCHEMA,
            "run_id": run_id,
            "count": len(rows),
            "truncated": len(rows) > capped,
            "categories": present,
            "events": events,
        }

    def run_evidence(self, run_id: str) -> dict[str, Any]:
        """Versioned Evidence/Results document for one recorded Run (#74).

        Backend-owned projection over manifest.json / evaluation.json / the
        replay classification — the browser never parses raw artifacts.
        Original Evaluation facts are surfaced read-only, never rewritten.
        """
        run_dir = self.run_dir(run_id)
        manifest = self._read_json(run_dir / "manifest.json") or {}
        spec = manifest.get("spec") or {}
        descriptor = self.descriptor(run_id)
        evaluation = self._read_json(run_dir / "evaluation.json")
        trajectory_present = (run_dir / "trajectory.parquet").is_file()
        enc_present = (run_dir / "enc.png").is_file()
        artifact_dir = run_dir / "artifacts" / "mid_mpc"
        artifact_count = (
            sum(1 for path in artifact_dir.iterdir() if path.is_file()) if artifact_dir.is_dir() else 0
        )
        events_journal = run_dir / "events.jsonl"
        event_count = (
            sum(1 for _ in events_journal.open(encoding="utf-8")) if events_journal.is_file() else 0
        )
        limitations = []
        replay_state = str(descriptor.get("replay", {}).get("state", "UNAVAILABLE"))
        if replay_state == "REDUCED":
            limitations.append("REDUCED_TRAJECTORY_ONLY")
        if replay_state == "INCOMPLETE":
            limitations.append("TRACE_INCOMPLETE")
        if evaluation is None:
            limitations.append("RESULT_PENDING")
        if manifest.get("failure_status"):
            limitations.append("EXECUTION_FAILURE_RECORDED")
        return {
            "schema_version": "colav.run-replay.evidence@1",
            "run_id": run_dir.name,
            "run": {
                "execution_state": manifest.get("state"),
                "execution_outcome": manifest.get("execution_outcome"),
                "scenario_id": spec.get("scenario_id"),
                "validation_rule_id": manifest.get("validation_rule_id") or spec.get("validation_rule_id"),
                "requested_algorithm": manifest.get("requested_algorithm"),
                "executed_algorithm": manifest.get("executed_algorithm"),
                "requested_tracker": manifest.get("requested_tracker"),
                "executed_tracker": manifest.get("executed_tracker"),
                "created_at_utc": manifest.get("created_at_utc"),
                "capability_profile_id": manifest.get("capability_profile_id"),
                "fallback_used": manifest.get("fallback_used"),
                "replay_of_run_id": manifest.get("replay_of_run_id"),
                "replay_verified": manifest.get("replay_verified"),
                "historical_scenario_id": manifest.get("historical_scenario_id"),
                "failure_status": manifest.get("failure_status"),
                "failure_reason": manifest.get("failure_reason"),
            },
            "result": {
                "result_ready": evaluation is not None,
                "evaluation_status": (evaluation or {}).get("evaluation_status"),
                "hard_gate": (evaluation or {}).get("hard_gate"),
                "evaluator_id": (evaluation or {}).get("evaluator_id") or manifest.get("evaluator_id"),
                "reproduction_status": (evaluation or {}).get("reproduction_status")
                or manifest.get("reproduction_status"),
            },
            "evidence": {
                "replay": descriptor.get("replay"),
                "trajectory_present": trajectory_present,
                "enc_present": enc_present,
                "mid_mpc_artifact_count": artifact_count,
                "event_count": event_count,
                "digests": {
                    key: manifest.get(key)
                    for key in (
                        "spec_hash",
                        "episode_hash",
                        "scenario_hash",
                        "enc_hash",
                        "trajectory_hash",
                        "trajectory_semantic_hash",
                        "trajectory_artifact_hash",
                    )
                    if manifest.get(key) is not None
                },
            },
            "limitations": limitations,
        }

    def static_context(self, run_id: str) -> dict[str, Any]:
        """Immutable chart context the Situation Display needs beyond frames."""
        run_dir = self.run_dir(run_id)
        manifest = self._read_json(run_dir / "manifest.json") or {}
        spec = manifest.get("spec") or {}
        enc_image = run_dir / "enc.png"
        image_url = f"/api/runs/{run_dir.name}/replay/enc.png" if enc_image.is_file() else None
        persisted = self._read_json(run_dir / STATIC_CONTEXT_FILENAME)
        if isinstance(persisted, dict) and persisted.get("schema_version") == STATIC_CONTEXT_SCHEMA:
            enc = persisted.get("enc") or {}
            return {
                "schema_version": CONTEXT_SCHEMA,
                "run_id": run_dir.name,
                "scenario_id": persisted.get("scenario_id") or spec.get("scenario_id"),
                "enc": {
                    "origin_east_m": enc.get("origin_east_m"),
                    "origin_north_m": enc.get("origin_north_m"),
                    "width_m": enc.get("width_m"),
                    "height_m": enc.get("height_m"),
                    "utm_zone": enc.get("utm_zone"),
                    "image_url": image_url,
                },
                "enc_navigation_area": persisted.get("enc_navigation_area"),
                "ships": persisted.get("ships"),
            }
        # Legacy Runs: degrade to episode-derived static facts; anything the
        # episode does not record stays null rather than being inferred.
        episode = self._read_json(run_dir / "episode.json") or {}
        config = episode.get("config") or {}
        origin = config.get("map_origin_enu") or [None, None]
        size = config.get("map_size") or [None, None]
        ships = [
            {"id": ship.get("id"), "mmsi": ship.get("mmsi"), "length_m": None, "width_m": None}
            for ship in config.get("ship_list") or []
            if isinstance(ship, dict)
        ]
        return {
            "schema_version": CONTEXT_SCHEMA,
            "run_id": run_dir.name,
            "scenario_id": spec.get("scenario_id"),
            "enc": {
                "origin_east_m": origin[0],
                "origin_north_m": origin[1],
                "width_m": size[0],
                "height_m": size[1],
                "utm_zone": config.get("utm_zone"),
                "image_url": image_url,
            },
            "enc_navigation_area": None,
            "ships": ships,
        }

    def enc_image(self, run_id: str) -> Path:
        run_dir = self.run_dir(run_id)
        path = run_dir / "enc.png"
        if not path.is_file():
            raise RunReplayError(404, "ENC_IMAGE_MISSING", f"run {run_dir.name} has no persisted ENC raster")
        return path

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


def project_window_threat_documents(document: dict[str, Any]) -> dict[str, Any]:
    """Attach the canonical per-frame threat projection to a window document.

    Same canonical function the live telemetry path applies to the
    adapter-published threat document (one function, no second truth). Window
    frames are request-local JSON, so normalization is identity.
    """

    def project(frame: dict[str, Any] | None) -> dict[str, Any] | None:
        if frame is None:
            return None
        ownship = (frame.get("payload") or {}).get("Ship0") or {}
        colav = ownship.get("colav") or {}
        frame["threat_management"] = canonical_threat_projection(
            colav,
            colav.get("planner") or {},
            normalize=lambda value: value,
        )
        return frame

    for frame in document["frames"]:
        project(frame)
    project(document["before"])
    project(document["after"])
    return document


def build_replay_router(
    store: RunReplayStore,
    *,
    active_replay_status: Callable[[str], dict[str, Any] | None] | None = None,
    default_limit: int = 50,
) -> APIRouter:
    """Read-only Run Replay routes; replay state is never mutated over HTTP."""

    @contextmanager
    def typed_errors():
        try:
            yield
        except RunReplayError as exc:
            raise HTTPException(
                status_code=exc.status,
                detail={"reason": str(exc.reason), "message": str(exc)},
            ) from exc

    def _active(run_id: str) -> dict[str, Any] | None:
        if active_replay_status is None:
            return None
        try:
            return active_replay_status(run_id)
        except Exception:  # noqa: BLE001 - the descriptor must stay read-only even if the hook fails
            return None

    router = APIRouter(prefix="/api")

    router = APIRouter(prefix="/api")

    @router.get("/runs")
    def list_runs(
        replayable: bool | None = Query(default=None),
        limit: int = Query(default=max(1, min(default_limit, MAX_LIST_RUNS)), ge=1, le=MAX_LIST_RUNS),
    ) -> list[dict[str, Any]]:
        return store.list_runs(replayable=replayable, limit=limit)

    @router.get("/runs/{run_id}/replay")
    def descriptor(run_id: str) -> dict[str, Any]:
        with typed_errors():
            return store.descriptor(run_id, active=_active(run_id))

    @router.get("/runs/{run_id}/replay/window")
    def window(
        run_id: str,
        from_s: float = Query(..., alias="from"),
        to_s: float = Query(..., alias="to"),
    ) -> dict[str, Any]:
        with typed_errors():
            return project_window_threat_documents(store.window(run_id, from_s, to_s))

    @router.get("/runs/{run_id}/replay/events")
    def replay_events(
        run_id: str,
        limit: int = Query(default=DEFAULT_EVENTS_LIMIT, ge=1, le=MAX_EVENTS_LIMIT),
    ) -> dict[str, Any]:
        with typed_errors():
            return store.replay_events(run_id, limit)

    @router.get("/runs/{run_id}/replay/evidence")
    def evidence(run_id: str) -> dict[str, Any]:
        with typed_errors():
            return store.run_evidence(run_id)

    @router.get("/runs/{run_id}/replay/context")
    def static_context(run_id: str) -> dict[str, Any]:
        with typed_errors():
            return store.static_context(run_id)

    @router.get("/runs/{run_id}/replay/enc.png")
    def enc_image(run_id: str) -> FileResponse:
        with typed_errors():
            return FileResponse(store.enc_image(run_id), media_type="image/png")

    return router
