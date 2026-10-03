"""FastAPI control surface backed by the real COLAV simulation session."""
# ruff: noqa: D103

from __future__ import annotations

import matplotlib as mpl

mpl.use("Agg")

import asyncio
import copy
import json
import logging
import math
import os
import re
import shutil
import threading
import time
from collections import OrderedDict, deque
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager, suppress
from dataclasses import replace
from datetime import datetime, timedelta
from functools import cache
from pathlib import Path
from typing import Any

import numpy as np
import orjson
import yaml
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from colav_simulator.cli import _load_algorithm_config
from colav_simulator.common import map_functions as mapf
from colav_simulator.core.colav.diagnostics import ColavExecutionError, PlanStatus

# P3-S2 observations endpoint (spec #90 whitelist: new routes + calibration
# table + measurement hookup). ExternalCameraSensor is the session-scoped
# measurement cache the accepted frames feed (sensor-model-v1 sensor_id 2|3).
from colav_simulator.core.ais_display import AisReportClock, ais_target_state
from colav_simulator.core.mast_cameras import MAST_MOUNTS_BY_ID, georeference_box
from colav_simulator.core.sensing import ExternalCameraSensor
from colav_simulator.decision_replay.sink import (
    REASON_GNC_BALANCE_CAPTURE_FAILED,
    REASON_THREAT_CAPTURE_FAILED,
    REASON_VO_DECISION_CAPTURE_FAILED,
    STATE_CAPTURING,
    STATE_INCOMPLETE,
    TraceSink,
    TraceSinkPolicy,
    vo_decision_space_for_snapshot,
)
from colav_simulator.experiment.busy_water import (
    ACCEPTANCE_SCENARIO_ID,
    DEFAULT_SEED,
    DEFAULT_TARGET_COUNT,
    STRESS_SCENARIO_ID,
    build_busy_water_document,
    normalize_encounter_mix,
    normalize_single_pass_document,
    preflight_document,
)
from colav_simulator.experiment.contracts import RunSpec, SessionState
from colav_simulator.experiment.persistence import jsonable
from colav_simulator.experiment.runner import ExperimentRunError, ExperimentRunner, PreparedRun, RunResult
from colav_simulator.historical_scenario_assembly import HistoricalAISSceneAssembler
from colav_simulator.historical_scenario_catalog import HistoricalAISScenarioCatalog
from colav_simulator.modular_gnc.catalog import list_stack_catalog
from colav_simulator.schemas.observations_v1 import ObservationFrame
from colav_simulator.schemas.sensor_model_v1 import (
    CONFIRMED_TRACKS_DEFAULT_THRESHOLD,
    ConfirmedTrack,
    ConfirmedTrackList,
    TrackSourceContribution,
)
from colav_simulator.core.tracking.trackers import sensor_channel_id
from gui_server import canonical_threat as _canonical_threat
from gui_server.gnc_balance import balance_telemetry
from gui_server.historical_api import router as historical_api_router
from gui_server.replay import (
    RunReplayStore,
    build_replay_router,
    replay_capture_budget_policy,
    replay_retention_budget_bytes,
    runs_root,
)
from gui_server.replay_artifacts import (
    _enc_depth_bin_at,
    build_enc_navigation_area,
    ensure_navigation_profile,
    persist_navigation_profile,
    persist_static_context,
    render_enc,
)

log = logging.getLogger("gui_server")
logging.basicConfig(level=logging.INFO)

BASE_DIR = Path(__file__).resolve().parent.parent
GUI_DIR = BASE_DIR / "web_gui"
DRAFT_DIR = BASE_DIR / "runs" / "scenario_drafts"
BUSY_WATER_SCENARIOS = {ACCEPTANCE_SCENARIO_ID, STRESS_SCENARIO_ID}
THREAT_PROJECTION_SCHEMA = "colav.threat-management.projection@1"
TELEMETRY_PUBLISH_INTERVAL_S = 0.1
TELEMETRY_TRAIL_HISTORY_SECONDS = 300.0
TELEMETRY_MAX_TRAIL_POINTS = 120
TELEMETRY_EVIDENCE_RECENT_EVENTS = 32
VO_DECISION_HISTORY_LIMIT = 64

REPLAY_STATE_UNAVAILABLE = "UNAVAILABLE"
REPLAY_REASON_TRACE_CAPTURE_DISABLED = "TRACE_CAPTURE_DISABLED"
REPLAY_REASON_CAPTURE_OPEN_FAILED = "CAPTURE_OPEN_FAILED"
REPLAY_REASON_CAPTURE_FINALIZE_FAILED = "CAPTURE_FINALIZE_FAILED"
REPLAY_REASON_SESSION_REPLACED = "SESSION_REPLACED"
REPLAY_REASON_EXECUTION_FAILED = "EXECUTION_FAILED"
CAPTURE_BUDGET_ENV = "COLAV_REPLAY_CAPTURE_BUDGET_BYTES"
# Measured on #70 (head_on/rule14 product runs through this capture path,
# 16 ticks): VO admits ~13 KB/tick raw, Mid-MPC ~148 KB/tick raw; stored
# (gzipped) frames are ~0.7 KB/tick (VO) and ~35 KB/tick (Mid-MPC). A 600 s
# 10 Hz Mid-MPC run therefore admits well under 1 GiB raw. The budget counts
# admitted uncompressed record bytes (an upper bound on disk use).
DEFAULT_CAPTURE_BUDGET_BYTES = 2 * 1024**3


def capture_budget_policy() -> TraceSinkPolicy:
    """Shared per-Run capture byte budget (see gui_server.replay, #74)."""
    return replay_capture_budget_policy()


# Issue #67 validated COLAV spacing profiles, run by product (GUI) sessions
# when the client sends no algorithm config. With the bare published defaults
# the VO horizon masks the route direction for ~250 s after CPA and the FCB45
# stacks execute a full recovery loop (607 m return-window XTE, reproduced
# headless 2026-09-04); these profiles are the tuned fix pinned against the
# published shipped values by tests/test_acceptance_spacing_profiles.py.
# Research entry points (runner/CLI without a config file) keep the published
# defaults unchanged.
PRODUCT_SPACING_PROFILES = {
    "vo": BASE_DIR / "config" / "acceptance_issue67_vo.yaml",
    "potocnik_colreg_fan_mpc": BASE_DIR / "config" / "acceptance_issue67_fan_mpc.yaml",
    "mid_mpc_ipopt": BASE_DIR / "config" / "acceptance_issue67_mid_mpc.yaml",
}


@cache
def _product_spacing_profile(algorithm_id: str) -> dict[str, Any] | None:
    path = PRODUCT_SPACING_PROFILES.get(algorithm_id)
    if path is None:
        return None
    return _load_algorithm_config(path)


def _sample_display_trail(trail: list[list[float]]) -> list[list[float]]:
    if len(trail) <= TELEMETRY_MAX_TRAIL_POINTS:
        return list(trail)
    indices = np.linspace(0, len(trail) - 1, TELEMETRY_MAX_TRAIL_POINTS, dtype=int)
    return [trail[int(index)] for index in indices]


def _telemetry_colav(colav: dict[str, Any]) -> dict[str, Any]:
    """Project a bounded live timeline; raw frames retain the complete audit."""
    planner = colav.get("planner", {})
    timeline = planner.get("evidence_timeline") if isinstance(planner, dict) else None
    if isinstance(timeline, dict) and isinstance(timeline.get("events"), list):
        events = timeline["events"]
        timeline = {
            **timeline,
            "events": events[-TELEMETRY_EVIDENCE_RECENT_EVENTS:],
            "events_total": len(events),
            "events_truncated": len(events) > TELEMETRY_EVIDENCE_RECENT_EVENTS,
        }
        colav = {**colav, "planner": {**planner, "evidence_timeline": timeline}}
    # Normalize once, after bounding history. The detached result is reused by
    # current-plan aliases rather than traversing the same evidence repeatedly.
    return jsonable(colav)


def _radar_ppi_descriptor(prepared: PreparedRun | None) -> dict[str, Any] | None:
    """Ownship sensor PPI parameterization for the web radar-ppi panel (P3-S1, spec #90).

    Additive duck-typed seam: any ownship sensor exposing ``ppi_descriptor()``
    (currently sensing.RadarXBand, sensor-model-v1 sensor_id=1) contributes the
    envelope-level ``radar_ppi`` field. Null keeps the payload shape for sessions
    without an X-band model, so the legacy web consumers stay untouched.
    """
    if prepared is None:
        return None
    ships = getattr(getattr(prepared, "session", None), "ship_list", None) or []
    if not ships:
        return None
    for sensor in getattr(ships[0], "sensors", None) or []:
        descriptor = getattr(sensor, "ppi_descriptor", None)
        if callable(descriptor):
            try:
                return jsonable(descriptor())
            except Exception:  # noqa: BLE001 (descriptor defects must never break telemetry)
                return None
    return None


def _compact_stream_payload(payload: dict[str, Any], *, include_static: bool) -> dict[str, Any]:
    repeated_prediction_fields = {
        "evidence_timeline",
        "predicted_trajectory",
        "prediction_render",
        "target_predictions",
    }
    compact = dict(payload)
    compact["transport"] = {
        "schema_version": "colav.telemetry.compact@1",
        "static_included": include_static,
    }
    compact["truth"] = [
        {key: value for key, value in ship.items() if key not in {"measurements", "tracks", "colav"}}
        for ship in payload.get("truth", [])
    ]
    compact.pop("os", None)
    compact.pop("obstacles", None)
    for field in ("planner", "latest_planner_solve"):
        compact[field] = {
            key: value for key, value in payload.get(field, {}).items() if key not in repeated_prediction_fields
        }
    compact.pop("active_planner_plan", None)
    compact.pop("latest_planner_attempt", None)
    if not include_static:
        compact.pop("enc_navigation_area", None)
    return compact


def _static_once_stream_payload(payload: dict[str, Any], *, include_static: bool) -> dict[str, Any]:
    streamed = dict(payload)
    streamed["transport"] = {
        "schema_version": "colav.telemetry.static-once@1",
        "static_included": include_static,
    }
    if not include_static:
        streamed.pop("enc_navigation_area", None)
    return streamed


def _shared_planner_stream_payload(payload: dict[str, Any], *, include_static: bool) -> dict[str, Any]:
    """Transmit identical planner aliases once; the client restores the envelope."""
    streamed = _static_once_stream_payload(payload, include_static=include_static)
    planner = payload.get("planner")
    aliases = [name for name in ("latest_planner_solve", "active_planner_plan", "latest_planner_attempt")
               if planner is not None and payload.get(name) is planner]
    for name in aliases:
        streamed.pop(name, None)
    ships = payload.get("truth", [])
    ship_aliases = []
    streamed["truth"] = []
    for index, ship in enumerate(ships):
        projected_ship = ship
        colav = ship.get("colav", {})
        if planner is not None and colav.get("planner") is planner:
            ship_aliases.append(index)
            projected_ship = {**ship, "colav": {key: value for key, value in colav.items() if key != "planner"}}
        streamed["truth"].append(projected_ship)
    ownship_alias = bool(ships) and payload.get("os") is ships[0]
    obstacles = payload.get("obstacles")
    obstacle_alias = isinstance(obstacles, list) and len(obstacles) == max(0, len(ships) - 1) and all(
        target is ship for target, ship in zip(obstacles, ships[1:], strict=False)
    )
    if ownship_alias:
        streamed.pop("os", None)
    if obstacle_alias:
        streamed.pop("obstacles", None)
    streamed["transport"] = {
        "schema_version": "colav.telemetry.shared-planner@1",
        "static_included": include_static,
        "planner_aliases": aliases,
        "ship_planner_aliases": ship_aliases,
        "ownship_from_truth": ownship_alias,
        "obstacles_from_truth": obstacle_alias,
    }
    return streamed


def _modular_gnc_telemetry_metadata(session: Any) -> dict[str, Any] | None:
    """Return additive modular GNC evidence metadata for the ownship (Issue #60 AC4).

    The envelope ``schema_version`` stays ``1.0``; this key is additive only.
    Legacy (non-modular) ownships carry ``None`` — no invented facts, no
    inflated claims. Evidence labels come from the Python-side stack evidence
    document, never from client-side interpretation.
    """
    ships = getattr(session, "ship_list", ()) or ()
    if not ships:
        return None
    config = getattr(ships[0], "modular_stack_config", None)
    if config is None:
        return None
    from colav_simulator.modular_gnc.catalog import stack_evidence_document  # noqa: PLC0415

    return stack_evidence_document(
        config,
        supported_tasks=getattr(ships[0], "modular_stack_supported_tasks", None) or None,
    )


def _original_gnc_telemetry_metadata(session: Any) -> dict[str, Any] | None:
    """Keep original-source runtime identity separate from modular qualifications."""
    ships = getattr(session, "ship_list", ()) or ()
    reader = getattr(ships[0], "original_gnc_evidence", None) if ships else None
    return reader() if callable(reader) else None


def _select_primary_encounter(_encounters: list[dict[str, Any]]) -> None:
    """Deprecated compatibility symbol; Primary belongs to canonical backend facts."""
    return None


def _canonical_threat_projection(colav_data: dict[str, Any], planner: dict[str, Any]) -> dict[str, Any]:
    """Project only a canonical backend threat document for REST/WS consumers.

    Live telemetry and the sealed replay read path share ONE canonical
    projection (gui_server.canonical_threat, ticket #71); the live path keeps
    its jsonable detachment of runtime dataclasses via the normalize hook.
    """
    return _canonical_threat.canonical_threat_projection(colav_data, planner, normalize=jsonable)


def _threat_unavailable(reason: str = "THREAT_SNAPSHOT_UNAVAILABLE") -> dict[str, Any]:
    return _canonical_threat.threat_unavailable(reason, normalize=jsonable)


def _session_threat_projection(session: Any) -> dict[str, Any]:
    """Project the session-owned canonical snapshot when no adapter published one."""
    coordinator = getattr(session, "threat_management_coordinator", None)
    snapshot = coordinator.last_snapshot if coordinator is not None else None
    if snapshot is None:
        return _threat_unavailable()
    document = snapshot.to_dict()
    return {
        "schema_version": THREAT_PROJECTION_SCHEMA,
        "status": "AVAILABLE",
        "snapshot": jsonable(document),
        "vectors": jsonable(document.get("vectors", [])),
        "schedule": jsonable(document.get("schedule")),
        # The legacy alias deliberately mirrors the typed conflict_graph field.
        "conflicts": jsonable(document.get("conflict_graph")),
        "conflict_graph": jsonable(document.get("conflict_graph")),
        "unavailable_reason": None,
    }


class SessionCreateRequest(BaseModel):
    scenario_id: str = "head_on"
    validation_rule_id: str | None = None
    algorithm_id: str = "vo"
    # P3-S6 default tracker flip (spec #90): new UI sessions answer on the
    # vimmjipda fusion chain; god remains explicitly selectable (fallback
    # channel, 00-PLAN R3).
    tracker_id: str = "vimmjipda"
    gnc_stack_id: str | None = None
    seed: int = Field(default=0, ge=0)
    episode_index: int = Field(default=0, ge=0)
    dt: float | None = Field(default=None, gt=0)
    t_end: float | None = Field(default=None, gt=0)
    solve_period_s: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    strict_no_fallback: bool = True
    evaluator_profile_id: str = "ccta_2023_demo-v1"
    algorithm_config: dict[str, Any] = Field(default_factory=dict)
    tracker_config: dict[str, Any] = Field(default_factory=dict)
    domain_profile: Any | None = None
    scenario_override: dict[str, Any] | None = None
    record_replay_trace: bool = True

    def to_spec(self) -> RunSpec:
        if self.validation_rule_id is None:
            raise ColavExecutionError(
                PlanStatus.INVALID_INPUT,
                "Product session create requires an explicit validation_rule_id and exact capability tuple",
            )
        payload = self.model_dump()
        payload.pop("record_replay_trace", None)  # capture policy lives outside the RunSpec identity
        payload["ownship_gnc_stack_id"] = payload.pop("gnc_stack_id")
        if not payload["algorithm_config"]:
            spacing_profile = _product_spacing_profile(self.algorithm_id)
            if spacing_profile is not None:
                payload["algorithm_config"] = copy.deepcopy(spacing_profile)
        override = payload.get("scenario_override")
        if override is not None:
            if self.scenario_id not in BUSY_WATER_SCENARIOS:
                raise ValueError("scenario_override is supported only for busy-water scenarios")
            override = normalize_single_pass_document(override)
            override["name"] = self.scenario_id
            preflight_document(override, seed=self.seed)
            payload["scenario_override"] = override
        return RunSpec(**payload, output_root="runs")


def _historical_session_spec(request: SessionCreateRequest) -> RunSpec | None:
    """Build the Counterfactual RunSpec when the selection names a Historical AIS scene."""
    try:
        descriptor = HistoricalAISScenarioCatalog().get(request.scenario_id)
    except KeyError:
        return None
    if not request.strict_no_fallback:
        raise ColavExecutionError(
            PlanStatus.INVALID_INPUT,
            "Historical AIS sessions require strict_no_fallback=true",
        )
    if request.validation_rule_id is None:
        raise ColavExecutionError(
            PlanStatus.INVALID_INPUT,
            "Product session create requires an explicit validation_rule_id and exact capability tuple",
        )
    if request.gnc_stack_id is not None:
        # Historical scenes bind their own runtime actors; a stack binding must
        # be rejected instead of silently ignored.
        raise ColavExecutionError(
            PlanStatus.INVALID_INPUT,
            "GNC stack binding is not supported for Historical AIS scenarios",
        )
    if request.algorithm_id == "mid_mpc_ipopt":
        from colav_simulator.core.colav.mid_mpc.models import MidMpcConfig  # noqa: PLC0415

        target_count = int(descriptor.current_window["target_count"])
        capacity = MidMpcConfig().max_targets
        if target_count > capacity:
            raise ColavExecutionError(
                PlanStatus.INVALID_INPUT,
                f"TARGET_CAPACITY_EXCEEDED: {target_count} > {capacity}",
            )
    manager.runner.capabilities.validate(
        request.validation_rule_id,
        request.scenario_id,
        request.algorithm_id,
        request.tracker_id,
    )
    cached = manager.historical_spec_cache.get(request.scenario_id)
    if (
        cached is not None
        and request.dt is None
        and request.t_end is None
        and request.solve_period_s is None
        and request.domain_profile is None
    ):
        capability = dict(cached.algorithm_capability_evidence or {})
        exact_tuple = list(capability.get("exact_tuple", ()))
        if len(exact_tuple) == 4:
            exact_tuple[0] = request.validation_rule_id
            exact_tuple[2] = request.algorithm_id
            exact_tuple[3] = request.tracker_id
            capability["exact_tuple"] = exact_tuple
        return replace(
            cached,
            validation_rule_id=request.validation_rule_id,
            algorithm_id=request.algorithm_id,
            tracker_id=request.tracker_id,
            seed=request.seed,
            episode_index=request.episode_index,
            strict_no_fallback=request.strict_no_fallback,
            evaluator_profile_id=request.evaluator_profile_id,
            algorithm_config=request.algorithm_config,
            tracker_config=request.tracker_config,
            algorithm_capability_evidence=capability,
        )
    overrides: dict[str, Any] = {
        "algorithm_id": request.algorithm_id,
        "algorithm_config": request.algorithm_config,
        "tracker_config": request.tracker_config,
        "evaluator_profile_id": request.evaluator_profile_id,
    }
    if request.dt is not None:
        overrides["dt"] = request.dt
    if request.t_end is not None:
        overrides["t_end"] = request.t_end
    if request.domain_profile is not None:
        overrides["domain_profile"] = request.domain_profile
    lifecycle_spec = HistoricalAISSceneAssembler(
        capability_catalog=manager.runner.capabilities,
    ).bind_lifecycle_counterfactual(
        descriptor,
        run_spec_overrides=overrides,
    )
    return replace(
        lifecycle_spec,
        validation_rule_id=request.validation_rule_id,
        seed=request.seed,
        strict_no_fallback=request.strict_no_fallback,
        solve_period_s=request.solve_period_s,
    )


class BusyWaterDraftRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    base_scenario_id: str
    seed: int = Field(default=DEFAULT_SEED, ge=0)
    encounter_mix: dict[str, float] = Field(default_factory=lambda: {"crossing": 0.6, "head_on": 0.2, "overtaking": 0.2})
    document: dict[str, Any]


def _execution_error_detail(exc: Exception) -> dict[str, str]:
    if isinstance(exc, ColavExecutionError):
        status = exc.status
    elif isinstance(exc, ExperimentRunError) and exc.manifest.failure_status:
        status = PlanStatus(exc.manifest.failure_status)
    else:
        status = PlanStatus.INVALID_INPUT
    return {"status": status.value, "reason": str(exc)}


def _draft_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip()).strip("-_").lower()
    if not slug:
        raise ValueError("draft name must contain a letter or number")
    return slug[:64]


def _validate_busy_water_document(document: dict[str, Any], base_scenario_id: str, seed: int) -> dict[str, Any]:
    if base_scenario_id not in BUSY_WATER_SCENARIOS:
        raise ValueError(f"unsupported busy-water base scenario: {base_scenario_id}")
    normalized = normalize_single_pass_document(document)
    normalized["name"] = base_scenario_id
    result = preflight_document(normalized, seed=seed)
    return {"document": normalized, "preflight": result}


def save_busy_water_draft(request: BusyWaterDraftRequest) -> dict[str, Any]:
    validated = _validate_busy_water_document(request.document, request.base_scenario_id, request.seed)
    encounter_mix = normalize_encounter_mix(request.encounter_mix)
    slug = _draft_slug(request.name)
    DRAFT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "busy_water_draft.v1",
        "id": slug,
        "name": request.name.strip(),
        "base_scenario_id": request.base_scenario_id,
        "seed": request.seed,
        "target_count": len(validated["document"]["ship_list"]) - 1,
        "encounter_mix": encounter_mix,
        **validated,
    }
    (DRAFT_DIR / f"{slug}.yaml").write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, width=120),
        encoding="utf-8",
    )
    return payload


def load_busy_water_draft(identifier: str) -> dict[str, Any]:
    slug = _draft_slug(identifier)
    path = DRAFT_DIR / f"{slug}.yaml"
    if not path.is_file():
        raise FileNotFoundError(identifier)
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    validated = _validate_busy_water_document(
        payload["document"],
        payload["base_scenario_id"],
        int(payload.get("seed", DEFAULT_SEED)),
    )
    return {**payload, **validated}


def list_busy_water_drafts() -> list[dict[str, Any]]:
    if not DRAFT_DIR.is_dir():
        return []
    output = []
    for path in sorted(DRAFT_DIR.glob("*.yaml")):
        try:
            payload = load_busy_water_draft(path.stem)
        except (KeyError, TypeError, ValueError, yaml.YAMLError):
            continue
        output.append(
            {
                "id": payload["id"],
                "name": payload["name"],
                "base_scenario_id": payload["base_scenario_id"],
                "seed": payload["seed"],
                "target_count": payload["target_count"],
                "encounter_mix": payload["encounter_mix"],
            }
        )
    return output


class SessionNotAcceptingError(RuntimeError):
    """observations-v1 §4: session state outside {CREATED, RUNNING} (409)."""

    def __init__(self, state: str) -> None:
        super().__init__("SESSION_NOT_ACCEPTING")
        self.state = state


class FrameSeqRegressionError(RuntimeError):
    """observations-v1 §4: frame_seq not strictly increasing (409)."""

    def __init__(self, last_seq: int) -> None:
        super().__init__("FRAME_SEQ_REGRESSION")
        self.last_seq = last_seq


class WebSessionManager:
    """Single active research session with background execution."""
    def __init__(self) -> None:
        self.runner = ExperimentRunner(BASE_DIR)
        self.historical_spec_cache: dict[str, RunSpec] = {}
        self.prepared: PreparedRun | None = None
        self.result: RunResult | None = None
        self._result_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="colav-results")
        self.latest: dict[str, Any] = {}
        self.replay_expected: tuple[str, str] | None = None
        self.speed_multiplier = 1.0
        self.speed_revision = 0
        self.effective_speed_multiplier: float | None = None
        self.scheduler_lag_ms = 0.0
        self.realtime_limited = False
        self.previous_prediction_horizon: list[list[float]] = []
        self.current_prediction_horizon: list[list[float]] = []
        self.last_solve_id: int | None = None
        self.latest_planner_solve: dict[str, Any] = {}
        self._vo_decision_history: OrderedDict[int, dict[str, Any]] = OrderedDict()
        self.active_planner_plan: dict[str, Any] = {}
        self.latest_planner_attempt: dict[str, Any] = {}
        self.enc_navigation_area: dict[str, Any] = {}
        self._telemetry_trails: dict[int, deque[list[float]]] = {}
        # P3-S4 AIS display layer (spec #90): per-target AIS report clocks +
        # last report ages; the additive truth[].ais field is derived from it.
        self._ais_report_clocks: dict[int, AisReportClock] = {}
        self._ais_report_ages: dict[int, float] = {}
        self._shadow_max_deviation_m = 0.0
        self._last_shadow_ownship: dict[str, Any] | None = None
        self._last_shadow_comparison: dict[str, Any] | None = None
        self._telemetry_published_at = 0.0
        self._latest_stream_document = ""
        self._latest_shared_stream_documents: dict[bool, str] = {}
        self._latest_static_once_stream_document = ""
        self._latest_static_once_dynamic_stream_document = ""
        self._latest_compact_stream_document = ""
        self._latest_compact_static_stream_document = ""
        self._trace_captures: dict[str, TraceSink] = {}
        self._capture_finalize_errors: dict[str, str] = {}
        self._record_replay_trace = True
        # P3-S2 observations endpoint state (spec #90): session-scoped external
        # camera measurement cache + per-(sensor, mount) frame_seq monotonic gate.
        self.observation_sensor: ExternalCameraSensor | None = None
        self._observation_seq_gate: dict[tuple[int, str], int] = {}
        self._observation_totals: dict[tuple[int, str], dict[str, int]] = {}
        self.lock = threading.RLock()

    @property
    def session_id(self) -> str | None:
        return self.prepared.manifest.run_id if self.prepared else None

    def create(self, spec: RunSpec, *, record_replay_trace: bool | None = None) -> dict[str, Any]:
        with self.lock:
            if self.prepared and self.prepared.session.state == SessionState.RUNNING:
                raise RuntimeError("Pause the active session before replacing it")
            replacement = self.runner.prepare(spec)
            return self._activate(replacement, record_replay_trace=record_replay_trace)

    def _activate(
        self,
        replacement: PreparedRun,
        *,
        enc_image_source: Path | None = None,
        record_replay_trace: bool | None = None,
    ) -> dict[str, Any]:
        if record_replay_trace is not None:
            self._record_replay_trace = record_replay_trace
        previous = self.prepared
        previous_capture: TraceSink | None = None
        if previous is not None:
            previous.artifact_sink.close(timeout_s=2.0)
            previous_capture = self._trace_captures.pop(previous.manifest.run_id, None)
            self._capture_finalize_errors.pop(previous.manifest.run_id, None)
            if previous_capture is not None and not previous_capture.finalized:
                if previous_capture.state == STATE_CAPTURING:
                    previous_capture.fail(REPLAY_REASON_SESSION_REPLACED)
        replacement.session.enable_pickle_frames()
        self.prepared = replacement
        self.result = None
        self.replay_expected = None
        # P3-S2 (spec #90): a new session gets a fresh observation cache; the
        # previous session's sensor (and its seq gate) is dropped here — the
        # session-end cleanup owns no state beyond this object.
        self.observation_sensor = ExternalCameraSensor()
        self._observation_seq_gate = {}
        self._observation_totals = {}
        self.previous_prediction_horizon = []
        self.current_prediction_horizon = []
        self.last_solve_id = None
        self.latest_planner_solve = {}
        self._vo_decision_history.clear()
        self.active_planner_plan = {}
        self.latest_planner_attempt = {}
        self._telemetry_trails = {}
        self._ais_report_clocks = {}
        self._ais_report_ages = {}
        self._shadow_max_deviation_m = 0.0
        self._last_shadow_ownship = None
        self._last_shadow_comparison = None
        self._telemetry_published_at = 0.0
        self._latest_stream_document = ""
        self._latest_shared_stream_documents: dict[bool, str] = {}
        self._latest_compact_stream_document = ""
        self._latest_compact_static_stream_document = ""
        self.speed_multiplier = 1.0
        self.speed_revision += 1
        self.effective_speed_multiplier = None
        self.scheduler_lag_ms = 0.0
        self.realtime_limited = False
        self.enc_navigation_area = self._enc_navigation_area()
        if enc_image_source is not None and enc_image_source.is_file():
            shutil.copyfile(enc_image_source, self.prepared.run_dir / "enc.png")
        else:
            render_enc(self.prepared)
        if previous_capture is not None and not previous_capture.finalized:
            self._result_executor.submit(self._finalize_replaced_capture, previous_capture, previous.session.events)
        self._open_trace_capture(replacement)
        self._persist_static_context(replacement)
        self._publish_telemetry(None)
        return self.describe()

    # -- full Decision Trace capture (ticket #70) ---------------------------

    def _open_trace_capture(self, prepared: PreparedRun) -> None:
        if not self._record_replay_trace:
            return
        try:
            self._trace_captures[prepared.manifest.run_id] = TraceSink.open(prepared.run_dir, policy=capture_budget_policy())
        except OSError:
            log.exception("Replay trace capture could not be opened for run %s", prepared.manifest.run_id)
            self._capture_finalize_errors[prepared.manifest.run_id] = REPLAY_REASON_CAPTURE_OPEN_FAILED

    def _persist_static_context(self, prepared: PreparedRun) -> None:
        """Persist immutable chart context for the sealed replay read path (#71 §7.2).

        ENC navigation area, chart extent and ship dimensions exist only in the
        live session; the replay read path must never import simulator runtime,
        so the capture side freezes them once per Run. Best-effort: a failure
        must never affect execution, and the context endpoint degrades to
        episode-derived facts for Runs without the file.
        """
        persist_static_context(prepared, self.enc_navigation_area)

    def _capture_for(self, prepared: Any) -> TraceSink | None:
        """Tolerant capture lookup: result publication must never depend on it."""
        manifest = getattr(prepared, "manifest", None)
        run_id = getattr(manifest, "run_id", None)
        return self._trace_captures.get(run_id) if run_id else None

    def _append_trace_capture(self, snapshot: Any) -> None:
        if not self._trace_captures or self.prepared is None:
            return
        capture = self._capture_for(self.prepared)
        if capture is not None:
            try:
                decision = vo_decision_space_for_snapshot(snapshot, self.prepared.session.ship_list)
            except Exception:
                capture.fail(REASON_VO_DECISION_CAPTURE_FAILED)
                log.exception("VO decision-space replay capture failed")
                return
            try:
                threat = _session_threat_projection(self.prepared.session)
            except Exception:
                capture.fail(REASON_THREAT_CAPTURE_FAILED)
                log.exception("Threat snapshot replay capture failed")
                return
            try:
                balance = balance_telemetry(self.prepared.session, frame=snapshot.payload)
            except Exception:
                capture.fail(REASON_GNC_BALANCE_CAPTURE_FAILED)
                log.exception("GNC balance replay capture failed")
                return
            capture.append(snapshot, vo_decision_space=decision, threat_management=threat, gnc_balance=balance)

    def replay_status_for(self, run_id: str | None) -> dict[str, Any] | None:
        """Read capture state without waiting for an unrelated active solver.

        Capture references are published atomically in the registry, and each
        TraceSink property owns its lock. The session lock must not couple
        historical reads to the duration of the current simulation step.
        """
        if run_id is None:
            return None
        finalize_error = self._capture_finalize_errors.get(run_id)
        if finalize_error is not None:
            return {"state": STATE_INCOMPLETE, "reason": finalize_error}
        capture = self._trace_captures.get(run_id)
        if capture is None:
            return None
        return {"state": capture.state, "reason": capture.reason, "frame_count": capture.tick_count}

    def _active_replay_status(self) -> dict[str, Any]:
        status = self.replay_status_for(self.session_id)
        if status is not None:
            return status
        reason = None if self._record_replay_trace else REPLAY_REASON_TRACE_CAPTURE_DISABLED
        return {"state": REPLAY_STATE_UNAVAILABLE, "reason": reason}

    def _finalize_replay_capture(self, prepared: PreparedRun) -> None:
        """Publish replay readiness before expensive evaluation work (§4.4)."""
        capture = self._capture_for(prepared)
        if capture is None:
            return
        try:
            capture.close(events=prepared.session.events)
        except Exception:
            log.exception("Replay trace finalization failed for run %s", prepared.manifest.run_id)
            self._capture_finalize_errors[prepared.manifest.run_id] = REPLAY_REASON_CAPTURE_FINALIZE_FAILED
            return
        try:
            persist_navigation_profile(prepared.run_dir, prepared.session.enc, prepared.manifest.enc_hash)
        except (OSError, TypeError, ValueError, KeyError):
            log.exception("Replay depth profile unavailable for run %s", prepared.manifest.run_id)
        self._enforce_replay_retention(prepared)

    @staticmethod
    def _finalize_replaced_capture(capture: TraceSink, events: list[dict[str, Any]]) -> None:
        try:
            capture.close(events=events)
        except Exception:
            log.exception("Replaced session trace finalization failed")

    def _enforce_replay_retention(self, prepared: PreparedRun) -> None:
        budget = replay_retention_budget_bytes()
        if budget <= 0:
            return
        try:
            store = RunReplayStore(prepared.run_dir.parent)
            store.prune_traces(
                budget_bytes=budget,
                keep_run_ids=frozenset({prepared.manifest.run_id}),
                log_event=self._append_retention_event,
            )
        except Exception:
            log.exception("Replay trace retention pruning failed")

    @staticmethod
    def _append_retention_event(run_dir: Path, document: dict[str, Any]) -> None:
        try:
            with (run_dir / "lifecycle_events.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(document) + "\n")
        except OSError:
            log.warning("Could not record replay retention event for %s", run_dir)

    def describe(self) -> dict[str, Any]:
        if not self.prepared:
            return {"active": False}
        source_time = float(self.prepared.session.simulator.t)
        runtime_time = self._runtime_time_document(source_time)
        replay_status = self._active_replay_status()
        return {
            "active": True,
            "session_id": self.session_id,
            "state": self.prepared.session.state.value,
            "spec": self.prepared.spec.to_dict(),
            "run_dir": str(self.prepared.run_dir),
            "sequence": self.prepared.session.sequence,
            **runtime_time,
            "failure_reason": self.prepared.session.failure_reason,
            "result_ready": self.result is not None,
            "replay_status": replay_status["state"],
            "replay_reason": replay_status["reason"],
            "playback": self._playback_status(),
        }

    def _runtime_time_document(self, source_time_s: float) -> dict[str, Any]:
        historical = None if self.prepared is None else self.prepared.spec.historical_replay
        if not isinstance(historical, dict):
            return {"sim_time": float(source_time_s), "source_time_s": float(source_time_s), "ais_utc": None}
        origin_s = float(historical.get("t_start_s", 0.0))
        actor_set = historical.get("actor_set", {})
        raw_origin = actor_set.get("time_origin_utc") if isinstance(actor_set, dict) else None
        ais_utc = None
        if raw_origin:
            ais_utc = (datetime.fromisoformat(str(raw_origin)) + timedelta(seconds=float(source_time_s))).isoformat()
        return {
            "sim_time": max(0.0, float(source_time_s) - origin_s),
            "source_time_s": float(source_time_s),
            "ais_utc": ais_utc,
        }

    def set_speed(self, session_id: str, multiplier: float) -> dict[str, Any]:
        with self.lock:
            self._require(session_id)
            self.speed_multiplier = max(0.1, min(10.0, float(multiplier)))
            self.speed_revision += 1
            self.effective_speed_multiplier = None
            self.scheduler_lag_ms = 0.0
            self.realtime_limited = False
            self._publish_playback_status()
            return self._playback_status()

    def playback_clock(self) -> dict[str, Any]:
        with self.lock:
            if not self.prepared:
                return {
                    "session_id": None,
                    "running": False,
                    "revision": self.speed_revision,
                    "multiplier": self.speed_multiplier,
                    "sim_time": 0.0,
                    "dt": 0.1,
                }
            session = self.prepared.session
            return {
                "session_id": self.session_id,
                "running": session.state == SessionState.RUNNING,
                "revision": self.speed_revision,
                "multiplier": self.speed_multiplier,
                "sim_time": float(session.simulator.t),
                "dt": float(session.config.dt_sim),
            }

    def update_playback_metrics(
        self,
        *,
        effective_multiplier: float | None,
        scheduler_lag_ms: float,
        realtime_limited: bool,
    ) -> None:
        with self.lock:
            self.effective_speed_multiplier = effective_multiplier
            self.scheduler_lag_ms = max(0.0, float(scheduler_lag_ms))
            self.realtime_limited = bool(realtime_limited)

    def _playback_status(self) -> dict[str, Any]:
        return {
            "requested_multiplier": self.speed_multiplier,
            "effective_multiplier": self.effective_speed_multiplier,
            "realtime_limited": self.realtime_limited,
            "scheduler_lag_ms": self.scheduler_lag_ms,
        }

    def _publish_playback_status(self) -> None:
        if self.latest:
            self.latest["playback"] = self._playback_status()
            self._invalidate_stream_documents()

    def _invalidate_stream_documents(self) -> None:
        self._latest_stream_document = ""
        self._latest_shared_stream_documents: dict[bool, str] = {}
        self._latest_static_once_stream_document = ""
        self._latest_static_once_dynamic_stream_document = ""
        self._latest_compact_stream_document = ""
        self._latest_compact_static_stream_document = ""

    def _cache_stream_document(self) -> None:
        self._latest_stream_document = json.dumps(
            jsonable(self.latest),
            ensure_ascii=False,
            separators=(",", ":"),
        )

    def stream_document(
        self,
        *,
        compact: bool = False,
        static_once: bool = False,
        shared_planner: bool = False,
        include_static: bool = True,
    ) -> str:
        with self.lock:
            if not self.latest:
                self.latest = self._telemetry(None)
            if shared_planner:
                documents = self._latest_shared_stream_documents
                if include_static not in documents:
                    documents[include_static] = orjson.dumps(
                        _shared_planner_stream_payload(self.latest, include_static=include_static),
                        default=jsonable,
                        option=orjson.OPT_SERIALIZE_NUMPY | orjson.OPT_PASSTHROUGH_DATETIME,
                    ).decode("utf-8")
                return documents[include_static]
            if static_once:
                attribute = (
                    "_latest_static_once_stream_document"
                    if include_static
                    else "_latest_static_once_dynamic_stream_document"
                )
                document = getattr(self, attribute)
                if not document:
                    document = json.dumps(
                        jsonable(_static_once_stream_payload(self.latest, include_static=include_static)),
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                    setattr(self, attribute, document)
                return document
            if not compact:
                if not self._latest_stream_document:
                    self._cache_stream_document()
                return self._latest_stream_document
            attribute = "_latest_compact_static_stream_document" if include_static else "_latest_compact_stream_document"
            document = getattr(self, attribute)
            if not document:
                document = json.dumps(
                    jsonable(_compact_stream_payload(self.latest, include_static=include_static)),
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                setattr(self, attribute, document)
            return document

    def _publish_telemetry(self, snapshot: Any) -> None:
        self.latest = self._telemetry(snapshot)
        self._remember_vo_decision_space()
        self._telemetry_published_at = time.monotonic()
        self._invalidate_stream_documents()

    def _telemetry_refresh_due(self, snapshot: Any, *, now: float) -> bool:
        if snapshot.state != SessionState.RUNNING:
            return True
        if any(event.get("type") == "planner_solved" for event in snapshot.events):
            return True
        return now - self._telemetry_published_at >= TELEMETRY_PUBLISH_INTERVAL_S - 1e-9

    def _record_telemetry_trails(self, frame: dict[str, Any]) -> None:
        if not self.prepared:
            return
        origin_e, origin_n = self.prepared.session.enc.origin
        history_points = int(np.ceil(TELEMETRY_TRAIL_HISTORY_SECONDS / self.prepared.session.simulator.dt)) + 1
        for index in range(len(self.prepared.session.ship_list)):
            raw = frame.get(f"Ship{index}", {})
            if not raw:
                continue
            state = np.asarray(raw["state"], dtype=float)
            trail = self._telemetry_trails.setdefault(
                index,
                deque(maxlen=history_points),
            )
            trail.append([float(state[0] - origin_n), float(state[1] - origin_e)])

    def _record_ais_reports(self, frame: dict[str, Any]) -> None:
        """P3-S4 AIS display layer (spec #90): advance per-target report clocks.

        Mirrors the ``_record_telemetry_trails`` lifecycle (step/tick only,
        cleared on session activation). Real AIS reports arrive on the
        ITU-R M.1371 cadence, not every simulation frame; the clock keeps the
        display age honest. Historical-replay actors inside a data gap
        (``historical_actor_truth.sample_kind == "inactive"``) receive no
        report, so their age grows across the gap and crosses the lost
        threshold after ``AIS_LOST_AGE_FACTOR`` expected intervals. Targets
        without a recorded age yet read as a fresh report (age 0).
        """
        if not self.prepared:
            return
        t = float(self.prepared.session.simulator.t)
        for index in range(len(self.prepared.session.ship_list)):
            raw = frame.get(f"Ship{index}", {})
            if not raw:
                continue
            csog = np.asarray(raw.get("csog_state", ()), dtype=float)
            sog = float(csog[2]) if csog.size > 2 else 0.0
            clock = self._ais_report_clocks.setdefault(index, AisReportClock())
            sample_kind = str(raw.get("historical_actor_truth", {}).get("sample_kind", "")).lower()
            if sample_kind == "inactive":
                self._ais_report_ages[index] = clock.age(t)
            else:
                self._ais_report_ages[index] = clock.advance(t, sog)

    def start(self, session_id: str) -> dict[str, Any]:
        with self.lock:
            prepared = self._require(session_id)
            prepared.session.start()
            self._publish_telemetry(None)
            return self.describe()

    def pause(self, session_id: str) -> dict[str, Any]:
        with self.lock:
            prepared = self._require(session_id)
            prepared.session.pause()
            self._publish_telemetry(None)
            return self.describe()

    def step(self, session_id: str) -> dict[str, Any]:
        with self.lock:
            prepared = self._require(session_id)
            if prepared.session.state in {SessionState.FINISHED, SessionState.FAILED}:
                raise RuntimeError(f"Cannot step a {prepared.session.state.value} session")
            try:
                snapshot = prepared.session.step_once()
                self._record_telemetry_trails(snapshot.payload)
                self._record_ais_reports(snapshot.payload)
                self._append_trace_capture(snapshot)
                self._publish_telemetry(snapshot)
                if prepared.session.state == SessionState.FINISHED:
                    self._result_executor.submit(self._finalize, prepared, self.replay_expected)
                return self.latest
            except Exception as exc:
                self._persist_failure(prepared, exc)
                self._publish_telemetry(None)
                raise

    def reset(self, session_id: str) -> dict[str, Any]:
        with self.lock:
            prepared = self._require(session_id)
            if prepared.session.state == SessionState.RUNNING:
                prepared.session.pause()
            previous_session_id = prepared.manifest.run_id
            replacement = self.runner.prepare_reset(prepared)
            enc_image_source = None if prepared.spec.reload_enc else prepared.run_dir / "enc.png"
            self._activate(replacement, enc_image_source=enc_image_source)
            self.prepared.session.record_event("session_reset", previous_session_id=previous_session_id)
            self._publish_telemetry(None)
            return self.describe()

    def tick(self) -> float | None:
        with self.lock:
            if not self.prepared or self.prepared.session.state != SessionState.RUNNING:
                return None
            try:
                snapshot = self.prepared.session.advance()
                self._record_telemetry_trails(snapshot.payload)
                self._record_ais_reports(snapshot.payload)
                self._append_trace_capture(snapshot)
                finished = self.prepared.session.state == SessionState.FINISHED
                if finished or self._telemetry_refresh_due(snapshot, now=time.monotonic()):
                    self._publish_telemetry(snapshot)
                if finished:
                    self._result_executor.submit(self._finalize, self.prepared, self.replay_expected)
                return float(self.prepared.session.simulator.t)
            except Exception as exc:
                self._persist_failure(self.prepared, exc)
                self._publish_telemetry(None)
                log.exception("Simulation session failed")
                return None

    def replay(self, session_id: str) -> dict[str, Any]:
        with self.lock:
            prepared = self._require(session_id)
            if self.result is None:
                raise RuntimeError("Replay is available only after the source session finishes")
            expected = (prepared.manifest.episode_hash, prepared.manifest.trajectory_hash)
            previous_session_id = prepared.manifest.run_id
            self.create(replace(prepared.spec, replay_of_run_id=prepared.manifest.run_id))
            self.replay_expected = expected
            self.prepared.session.record_event("session_replayed", previous_session_id=previous_session_id)
            self._publish_telemetry(None)
            return self.describe()

    def _finalize(self, prepared: PreparedRun, replay_expected: tuple[str, str] | None = None) -> None:
        # Physical execution is already FINISHED and published. Trace
        # finalization publishes replay readiness first; Evaluation and
        # artifact serialization must not hold the control/telemetry lock.
        try:
            self._finalize_replay_capture(prepared)
            result = self.runner.finalize(prepared)
            if replay_expected:
                episode_hash, trajectory_hash = replay_expected
                prepared.manifest.replay_verified = (
                    prepared.manifest.episode_hash == episode_hash and prepared.manifest.trajectory_hash == trajectory_hash
                )
                prepared.writer.write_manifest(prepared.manifest)
                if not prepared.manifest.replay_verified:
                    raise RuntimeError("Web replay trajectory mismatch")
            with self.lock:
                if self.prepared is prepared:
                    self.result = result
                    self._publish_telemetry(None)
        except Exception as exc:
            self._persist_failure(prepared, exc)
            with self.lock:
                if self.prepared is prepared:
                    self._publish_telemetry(None)
            log.exception("Simulation result generation failed")

    def _persist_failure(self, prepared: PreparedRun, exc: Exception) -> None:
        """Publish failure state immediately; archive frozen evidence off the control path."""
        prepared.session.state = SessionState.FAILED
        prepared.session.failure_reason = str(exc)
        self._result_executor.submit(self._write_failure_evidence, prepared, exc)

    def _write_failure_evidence(self, prepared: PreparedRun, exc: Exception) -> None:
        try:
            prepared.artifact_sink.close(timeout_s=2.0)
            capture = self._capture_for(prepared)
            if capture is not None and not capture.finalized:
                capture.fail(REPLAY_REASON_EXECUTION_FAILED)
                capture.close(events=prepared.session.events)
            self.runner.persist_original_gnc(prepared)
            self.runner.persist_failure(
                prepared.manifest,
                prepared.writer,
                exc,
                prepared.session.frame_view,
                prepared.session.events,
            )
        except Exception:
            log.exception("Failed to archive simulation failure evidence")

    def result_document(self, session_id: str) -> dict[str, Any]:
        self._require(session_id)
        if not self.result:
            raise RuntimeError("Result is still being generated or the session has not finished")
        return {
            "manifest": self.result.manifest.to_dict(),
            "evaluation": self.result.evaluation.to_dict(),
        }

    def artifacts(self, session_id: str) -> list[dict[str, Any]]:
        prepared = self._require(session_id)
        return [
            {"name": path.name, "size": path.stat().st_size, "url": f"/api/sessions/{session_id}/artifacts/{path.name}"}
            for path in sorted(prepared.run_dir.iterdir())
            if path.is_file() and not path.name.startswith(".")
        ]

    def artifact(self, session_id: str, name: str) -> Path:
        prepared = self._require(session_id)
        path = (prepared.run_dir / name).resolve()
        if path.parent != prepared.run_dir.resolve() or not path.is_file():
            raise FileNotFoundError(name)
        return path

    def enc_info(self) -> dict[str, Any]:
        prepared = self.prepared
        if not prepared:
            return {"ready": False}
        enc = prepared.session.enc
        run_id = prepared.manifest.run_id
        return {
            "ready": True,
            "origin_e": float(enc.origin[0]),
            "origin_n": float(enc.origin[1]),
            "width": float(enc.size[0]),
            "height": float(enc.size[1]),
            "utm_zone": int(enc.utm_zone),
            # Horizontal part of the existing ETRS89 / UTM + NN54 compound CRS.
            "horizontal_crs": f"EPSG:{25800 + int(enc.utm_zone)}" if int(enc.utm_zone) in (32, 33) else None,
            "hemisphere": "north" if int(enc.utm_zone) in (32, 33) else None,
            "display_height_reference": "ellipsoid-zero-visual-only",
            "tile_url": "/api/enc_tile",
            "navigation_area_url": f"/api/sessions/{run_id}/navigation-area",
            "run_id": run_id,
        }

    def navigation_area(self, session_id: str) -> dict[str, Any]:
        self._require(session_id)
        return self.enc_navigation_area

    def _remember_vo_decision_space(self) -> None:
        """Retain published solves for delayed presentation without bloating telemetry."""
        planner = self.latest.get("latest_planner_solve") or self.latest.get("planner") or {}
        solve_id = planner.get("solve_id")
        if planner.get("algorithm_id") != "vo" or not solve_id or solve_id in self._vo_decision_history:
            return
        if self.prepared is None or not self.prepared.session.ship_list:
            return
        snapshot = self.prepared.session.ship_list[0].get_colav_decision_space()
        if snapshot is None or snapshot.get("solve_id") != solve_id:
            return
        self._vo_decision_history[solve_id] = jsonable(snapshot)
        while len(self._vo_decision_history) > VO_DECISION_HISTORY_LIMIT:
            self._vo_decision_history.popitem(last=False)

    def planner_decision_space(self, session_id: str, solve_id: int) -> dict[str, Any] | None:
        with self.lock:
            prepared = self._require(session_id)
            if solve_id in self._vo_decision_history:
                return self._vo_decision_history[solve_id]
            if not prepared.session.ship_list:
                return None
            snapshot = prepared.session.ship_list[0].get_colav_decision_space()
            if snapshot is None:
                return None
            current_solve_id = int(snapshot.get("solve_id", 0))
            if solve_id != current_solve_id:
                raise RuntimeError(f"Decision-space solve {solve_id} is stale; latest solve is {current_solve_id}")
            return jsonable(snapshot)

    def _enc_navigation_area(self) -> dict[str, Any]:
        return build_enc_navigation_area(self.prepared)

    def _require(self, session_id: str) -> PreparedRun:
        if not self.prepared or session_id != self.session_id:
            raise KeyError(session_id)
        return self.prepared

    # -- P3-S2 observations endpoint (spec #90; contract observations-v1.md) --

    def _camera_sensor_for(self, prepared: PreparedRun) -> ExternalCameraSensor:
        """Observation cache target for one session (P1-1a review fix, spec #90).

        A scene that explicitly assembles the ``external_cameras:`` ship sensor
        key owns an ExternalCameraSensor inside ``ship_list[0].sensors`` — the
        endpoint feeds THAT instance, so the assembled sensor's records reach
        the ship tracker's measurement loop (trackers.py iterates self.sensors
        only). Unassembled scenes keep the session-scoped cache (default-off
        discipline: the default tracker behaviour is untouched).
        """
        ship_sensors = getattr(prepared.session.ship_list[0], "sensors", None) or []
        for sensor in ship_sensors:
            if isinstance(sensor, ExternalCameraSensor):
                return sensor
        if self.observation_sensor is None:
            self.observation_sensor = ExternalCameraSensor()
        return self.observation_sensor

    def ingest_observations(self, session_id: str, frame: ObservationFrame) -> dict[str, Any]:
        """Validates, georeferences and caches one camera observation frame.

        Gates (contract §1/§4): session must exist (404) and accept frames
        (CREATED/RUNNING only, 409 SESSION_NOT_ACCEPTING); ``frame_seq`` is
        strictly monotonic per (sensor_id, mount_id) (409 FRAME_SEQ_REGRESSION);
        schema violations are rejected by the pydantic body model (422).
        Georef uses the authoritative ownship state at receipt (contract §5:
        same-host loop latency is sub-second, far below the ship-length accuracy
        budget; ``frame_time_s`` stays a Unity-domain reference stamp).
        """
        if frame.mount_id not in MAST_MOUNTS_BY_ID:
            raise ValueError(f"unknown mount_id {frame.mount_id!r}")
        with self.lock:
            prepared = self._require(session_id)
            if prepared.session.state not in (SessionState.CREATED, SessionState.RUNNING):
                raise SessionNotAcceptingError(prepared.session.state.value)
            gate_key = (frame.sensor_id, frame.mount_id)
            last_seq = self._observation_seq_gate.get(gate_key)
            if last_seq is not None and frame.frame_seq <= last_seq:
                raise FrameSeqRegressionError(last_seq)

            ship_state = np.asarray(prepared.session.ship_list[0].state, dtype=float)
            own_north, own_east, own_yaw = float(ship_state[0]), float(ship_state[1]), float(ship_state[2])
            mount = MAST_MOUNTS_BY_ID[frame.mount_id]
            sensor = self._camera_sensor_for(prepared)
            records = []
            for detection in frame.detections:
                georef = georeference_box(
                    mount,
                    tuple(detection.box_xyxy),
                    mount.frame_width_px,
                    mount.frame_height_px,
                    own_north=own_north,
                    own_east=own_east,
                    own_yaw_rad=own_yaw,
                    class_name=detection.class_name,
                )
                records.append(
                    {
                        "sensor_id": frame.sensor_id,
                        "position_ne_m": [georef.north_m - own_north, georef.east_m - own_east],
                        "position_cov_ne_m2": [list(row) for row in georef.cov_ne_m2],
                        "confidence": float(detection.confidence),
                        "class_name": detection.class_name,
                        "class_confidence": float(detection.confidence),
                        "t_s": float(prepared.session.simulator.t),
                        "mount_id": frame.mount_id,
                        "frame_seq": int(frame.frame_seq),
                        "frame_time_s": float(frame.frame_time_s),
                    }
                )
            sensor.submit(records, frame_seq=frame.frame_seq)
            self._observation_seq_gate[gate_key] = frame.frame_seq
            totals = self._observation_totals.setdefault(
                gate_key, {"frames": 0, "detections": 0}
            )
            totals["frames"] += 1
            totals["detections"] += len(records)
            return {"accepted": True, "frame_seq": frame.frame_seq, "detections_accepted": len(records)}

    def observation_status(self, session_id: str) -> dict[str, Any]:
        """Status/test hook for the E2E probe.

        Accepted frame counters per (sensor, mount) plus the pending
        georeferenced measurements with their sensor_id (the S5 fusion cache
        reads the same records).
        """
        with self.lock:
            prepared = self._require(session_id)
            channels = [
                {
                    "sensor_id": sensor_id,
                    "mount_id": mount_id,
                    "frames": totals["frames"],
                    "detections": totals["detections"],
                    "last_frame_seq": self._observation_seq_gate.get((sensor_id, mount_id)),
                }
                for (sensor_id, mount_id), totals in sorted(self._observation_totals.items())
            ]
            sensor = self._camera_sensor_for(prepared)
            pending = sensor.pending_records()
            return {
                "accepted_frames_total": sensor.accepted_frames,
                "channels": channels,
                "pending_measurements": jsonable(pending),
            }

    def confirmed_tracks(self, session_id: str, min_existence_prob: float = CONFIRMED_TRACKS_DEFAULT_THRESHOLD) -> dict[str, Any]:
        """P3-S5 (spec #90) high-confidence track data product (sensor-model-v1 §5).

        Filters the ownship's latest tracker snapshot set by the existence-prob
        gate and returns the frozen ``sensor-model@1/tracks`` envelope. God
        truth tracks carry no measurement-derived sources (empty ``sources[]``);
        the frozen schema requires >=1 entry, so the ownship's primary ranging
        channel (radar_x=1) is reported with unknown age for those — a
        data-product boundary convention, not a measurement claim.
        """
        if not math.isfinite(min_existence_prob) or not 0.0 <= min_existence_prob <= 1.0:
            raise ValueError("min_existence_prob must be a finite value in [0, 1]")
        with self.lock:
            prepared = self._require(session_id)
            session = prepared.session
            frame = getattr(session, "last_frame", None) or {}
            raw = frame.get("Ship0", {}) if isinstance(frame, dict) else {}
            origin_e, origin_n = session.enc.origin
            labels = raw.get("do_labels", [])
            generations = raw.get("do_generations", [])
            states = raw.get("do_estimates", [])
            covariances = raw.get("do_covariances", [])
            existence = raw.get("do_existence_probabilities", [])
            qualities = raw.get("do_qualities", [])
            sources = raw.get("do_sources", [])
            own_sensors = getattr(session.ship_list[0], "sensors", None) or []
            primary_channel = next(
                (sensor_channel_id(sensor) for sensor in own_sensors if not sensor.bypass_fusion),
                1,
            )
            tracks: list[ConfirmedTrack] = []
            for index, label in enumerate(labels):
                existence_prob = float(existence[index]) if index < len(existence) else 1.0
                if existence_prob < min_existence_prob:
                    continue
                state = np.asarray(states[index], dtype=float)
                covariance = np.asarray(covariances[index], dtype=float)[:2, :2]
                # Fusion covariances can lose exact symmetry through the E↔N
                # permutation round-trip; the frozen schema requires a symmetric
                # 2x2, so the data-product boundary normalizes (documented).
                covariance = (covariance + covariance.T) / 2.0
                velocity = state[2:4]
                speed = float(np.linalg.norm(velocity))
                heading_rad = float(np.arctan2(velocity[1], velocity[0])) if speed > 1.0e-6 else 0.0
                track_sources = sources[index] if index < len(sources) else []
                source_entries = [
                    TrackSourceContribution(
                        sensor_id=int(source.get("sensor_id", primary_channel)),
                        last_seen_age_s=source.get("last_seen_age_s"),
                    )
                    for source in (track_sources or [])
                    if isinstance(source, dict)
                ] or [TrackSourceContribution(sensor_id=primary_channel, last_seen_age_s=None)]
                tracks.append(
                    ConfirmedTrack(
                        track_key=f"{int(label)}:{int(generations[index]) if index < len(generations) and generations[index] else 1}",
                        target_id=int(label),
                        generation=int(generations[index]) if index < len(generations) and generations[index] else 1,
                        existence_prob=existence_prob,
                        quality=float(qualities[index]) if index < len(qualities) else 1.0,
                        sources=source_entries,
                        position_ne_m=[float(state[0] - origin_n), float(state[1] - origin_e)],
                        velocity_ne_mps=[float(velocity[0]), float(velocity[1])],
                        heading_rad=heading_rad,
                        position_cov_ne_m2=[[float(covariance[0][0]), float(covariance[0][1])], [float(covariance[1][0]), float(covariance[1][1])]],
                        class_name=None,
                        class_confidence=None,
                    )
                )
            t_s = float(raw.get("timestamp", session.simulator.t))
            envelope = ConfirmedTrackList(schema_version="sensor-model@1/tracks", t_s=t_s, tracks=tracks)
            return jsonable(envelope.model_dump(mode="json"))

    def _telemetry(self, snapshot: Any) -> dict[str, Any]:  # noqa: C901, PLR0912, PLR0915
        if not self.prepared:
            return {
                "schema_version": "1.0",
                "run_id": None,
                "seq": 0,
                "sim_time": 0.0,
                "state": SessionState.CREATED.value,
                "events": [],
                "modular_gnc": None,
            }
        session = self.prepared.session
        frame = snapshot.payload if snapshot is not None else (session.last_frame or {})
        if not frame:
            frame = {
                f"Ship{index}": {
                    "id": ship.id,
                    "mmsi": ship.mmsi,
                    "csog_state": ship.csog_state,
                    "state": ship.state,
                    "waypoints": ship.waypoints,
                    "speed_plan": ship.speed_plan,
                    "references": np.zeros(9),
                    "turn_rate": ship.turn_rate,
                    "active": bool(ship.t_start <= session.simulator.t < ship.t_end),
                }
                for index, ship in enumerate(session.ship_list)
            }
        origin_e, origin_n = session.enc.origin
        ships = []
        for index in range(len(session.ship_list)):
            raw = frame.get(f"Ship{index}", {})
            if not raw:
                continue
            state = np.asarray(raw["state"], dtype=float)
            csog = np.asarray(raw["csog_state"], dtype=float)
            trail = _sample_display_trail(list(self._telemetry_trails.get(index, ())))
            if not trail:
                trail = [[float(state[0] - origin_n), float(state[1] - origin_e)]]
            ships.append(
                {
                    "id": int(raw["id"]),
                    "mmsi": int(raw["mmsi"]),
                    "length": float(session.ship_list[index].length),
                    "width": float(session.ship_list[index].width),
                    "x": float(state[0] - origin_n),
                    "y": float(state[1] - origin_e),
                    "north": float(state[0]),
                    "east": float(state[1]),
                    "psi": float(state[2]),
                    "u": float(state[3]),
                    "v": float(state[4]),
                    "r": float(raw.get("turn_rate", state[5])),
                    "sog": float(csog[2]),
                    "cog": float(csog[3]),
                    "trajectory": trail,
                    "active": bool(raw.get("active", True)),
                    "historical_sample_kind": str(
                        raw.get("historical_actor_truth", {}).get("sample_kind", "")
                    ).upper() or None,
                    "dimensions_provenance": raw.get("historical_actor_dimensions", {}).get("provenance"),
                    "measurements": jsonable(raw.get("sensor_measurements")),
                    "tracks": self._local_tracks(raw, origin_n, origin_e),
                    "colav": _telemetry_colav(raw.get("colav", {})),
                }
            )
            if index >= 1:
                # P3-S4 additive AIS display field (spec #90): obstacles only
                # (ownship carries no AIS object). Backend-authoritative
                # state judgment; compact-v1 strip list stays untouched.
                age_s = float(self._ais_report_ages.get(index, 0.0))
                ships[-1]["ais"] = {
                    "age_s": age_s,
                    "state": ais_target_state(float(ships[-1]["sog"]), age_s),
                }
        own = ships[0] if ships else {"x": 0.0, "y": 0.0, "psi": 0.0, "u": 0.0, "v": 0.0, "r": 0.0, "trajectory": []}
        if ships:
            latitude, longitude = mapf.local2latlon(own["east"], own["north"], session.enc.utm_zone)
            own["latitude"] = float(latitude)
            own["longitude"] = float(longitude)
            own["floor_depth_m"] = _enc_depth_bin_at(session.enc, east=own["east"], north=own["north"])
            own["floor_depth_source"] = (
                "ENC_DEPTH_BIN_LOWER_BOUND" if own["floor_depth_m"] is not None else "ENC_DEPTH_BIN_UNAVAILABLE"
            )
        obstacles = ships[1:]
        target_routes = []
        for target in session.ship_list[1:]:
            route = np.asarray(target.waypoints, dtype=float)
            if route.ndim != 2 or route.shape[0] != 2:
                continue
            target_routes.append(
                {
                    "target_id": int(target.id),
                    "waypoints": np.vstack((route[0] - origin_n, route[1] - origin_e)).tolist(),
                    "speed_mps": float(target.csog_state[2]),
                }
            )
        own_raw = frame.get("Ship0", {})
        waypoints = np.asarray(own_raw.get("waypoints", np.zeros((2, 0))), dtype=float)
        if waypoints.ndim == 2 and waypoints.size:
            local_waypoints = np.vstack((waypoints[0] - origin_n, waypoints[1] - origin_e)).tolist()
        else:
            local_waypoints = [[], []]
        colav_data = ships[0]["colav"] if ships else {}
        planner = colav_data.get("planner", {})
        threat_management = _canonical_threat_projection(colav_data, planner)
        adapter_published_threat = bool(
            planner.get("threat_management")
            or planner.get("algorithm_details", {}).get("threat_management")
            or colav_data.get("threat_management")
        )
        coordinator = getattr(session, "threat_management_coordinator", None)
        if getattr(coordinator, "last_snapshot", None) is not None or not adapter_published_threat:
            # Plan evidence stays frozen at acceptance. Cards use the current
            # runtime authority even while a rejected revision retains that plan.
            threat_management = _session_threat_projection(session)
        # Legacy aliases remain present for old clients, but never carry a
        # browser/server-local risk interpretation.
        encounters = []
        primary_encounter = None
        dcpa = None
        tcpa = None
        encounter = None
        solve_id = int(planner.get("solve_id", 0))
        algorithm_details = planner.get("algorithm_details", {})
        prediction_render = planner.get("prediction_render", {})
        typed_render = prediction_render.get("schema_version") == "colav.mid_mpc.prediction-render@1"
        if typed_render:
            prediction_render = dict(prediction_render)
            prediction_render["evaluator_g3"] = self.result.evaluation.to_dict() if self.result is not None else None
        render_projection = prediction_render if typed_render else algorithm_details.get("render_projection", {})
        projected_ownship = render_projection.get("ownship", {})
        projected_north = np.asarray(projected_ownship.get("north_m", []), dtype=float)
        projected_east = np.asarray(projected_ownship.get("east_m", []), dtype=float)
        if (
            render_projection.get("frame") == "ENU"
            and projected_north.ndim == 1
            and projected_east.ndim == 1
            and projected_north.size == projected_east.size
            and projected_north.size > 0
        ):
            predicted = np.vstack((projected_north, projected_east))
        else:
            predicted = np.asarray(planner.get("predicted_trajectory", np.zeros((0, 0))), dtype=float)
        has_prediction = (
            predicted.ndim == 2
            and predicted.shape[0] >= 2
            and predicted.shape[1] > 0
            and (typed_render or solve_id > 0 or planner.get("algorithm_id") in {"nominal", "vo"})
        )
        if has_prediction:
            prediction_horizon = np.column_stack((predicted[0] - origin_n, predicted[1] - origin_e)).tolist()
        else:
            prediction_horizon = []
        target_prediction_horizons = []
        rendered_targets = prediction_render.get("targets", []) if typed_render else planner.get("target_predictions", [])
        for target in rendered_targets:
            if typed_render and target.get("purpose") != "L4_SAFETY":
                continue
            target_north = np.asarray(target.get("north_m", target.get("x", [])), dtype=float)
            target_east = np.asarray(target.get("east_m", target.get("y", [])), dtype=float)
            if target_north.ndim != 1 or target_east.ndim != 1 or target_north.size != target_east.size:
                continue
            target_prediction_horizons.append(np.column_stack((target_north - origin_n, target_east - origin_e)).tolist())
        rejected_target_prediction_horizons = []
        if typed_render and prediction_render.get("style") != "ACTIVE":
            if prediction_render.get("style") == "REJECTED":
                rejected_target_prediction_horizons = target_prediction_horizons
            target_prediction_horizons = []
        if typed_render:
            executable = prediction_render.get("executable") is True
            self.current_prediction_horizon = prediction_horizon if executable else []
            history_ownship = (prediction_render.get("history") or {}).get("ownship", {})
            history_north = np.asarray(history_ownship.get("north_m", []), dtype=float)
            history_east = np.asarray(history_ownship.get("east_m", []), dtype=float)
            if (
                history_north.ndim == 1
                and history_east.ndim == 1
                and history_north.size == history_east.size
                and history_north.size > 0
            ):
                self.previous_prediction_horizon = np.column_stack(
                    (history_north - origin_n, history_east - origin_e)
                ).tolist()
            elif prediction_render.get("style") == "INVALID_HISTORY":
                self.previous_prediction_horizon = prediction_horizon
            else:
                self.previous_prediction_horizon = []
            if planner.get("solver_executed"):
                self.latest_planner_solve = planner
                self.last_solve_id = solve_id
            self.active_planner_plan = planner if executable else {}
            self.latest_planner_attempt = planner
            rejected_prediction_horizon = prediction_horizon if prediction_render.get("style") == "REJECTED" else []
        elif planner.get("solver_executed") and solve_id != self.last_solve_id:
            self.previous_prediction_horizon = self.current_prediction_horizon
            self.current_prediction_horizon = prediction_horizon
            self.last_solve_id = solve_id
            self.latest_planner_solve = planner
            self.active_planner_plan = planner
        elif planner.get("algorithm_details", {}).get("failure_code") and not planner.get("algorithm_details", {}).get(
            "cached_plan_used", False
        ):
            self.active_planner_plan = {}
            self.current_prediction_horizon = []
        elif prediction_horizon and not self.current_prediction_horizon:
            self.current_prediction_horizon = prediction_horizon
        if not typed_render:
            rejected_prediction_horizon = []
        if planner and (
            planner.get("solver_executed")
            or planner.get("algorithm_details", {}).get("failure_code")
            or planner.get("algorithm_details", {}).get("hold_acceptance")
            or not self.latest_planner_attempt
        ):
            self.latest_planner_attempt = planner
        references = np.asarray(own_raw.get("references", np.zeros(9)), dtype=float)
        execution = {
            "solve_id": solve_id,
            "applied_course_ref_rad": float(references[2]) if references.size > 2 else None,
            "applied_speed_ref_mps": float(references[3]) if references.size > 3 else None,
            "selected_command": planner.get("selected_command", {}),
        }
        source_time = float(snapshot.sim_time) if snapshot is not None else float(session.simulator.t)
        if session.state is SessionState.FINISHED and session.simulator.t >= session.simulator.t_end:
            source_time = float(session.simulator.t)
        runtime_time = self._runtime_time_document(source_time)
        events = list(snapshot.events if snapshot is not None else [])
        operational_events = list(session.operational_events)
        historical_spec = self.prepared.spec.historical_replay
        if isinstance(historical_spec, dict):
            event_origin_s = float(historical_spec.get("t_start_s", 0.0))
            def project_event_time(event: dict[str, Any]) -> dict[str, Any]:
                source_event_time = float(event.get("sim_time", 0.0))
                return {
                    **event,
                    "source_time_s": source_event_time,
                    "sim_time": max(0.0, source_event_time - event_origin_s),
                }

            events = [project_event_time(event) for event in events]
            operational_events = [project_event_time(event) for event in operational_events]
        step_ms = float(snapshot.step_time_ms) if snapshot is not None else 0.0
        historical_context = None
        if isinstance(self.prepared.spec.historical_replay, dict):
            context_states = []
            for ship in session.ship_list:
                sample_at = getattr(getattr(ship, "historical_actor", None), "sample_at", None)
                sample = None if sample_at is None else sample_at(source_time)
                context_states.append(
                    {
                        "actor_id": int(ship.id),
                        "mmsi": int(ship.mmsi),
                        "status": "INACTIVE / DATA GAP" if sample is None else sample.kind.value.upper(),
                        "dimensions_provenance": getattr(
                            getattr(ship, "historical_actor", None),
                            "dimensions_provenance",
                            None,
                        ),
                    }
                )
            historical_context = {
                "total_actor_count": len(context_states),
                "active_actor_count": sum(item["status"] != "INACTIVE / DATA GAP" for item in context_states),
                "inactive_actor_count": sum(item["status"] == "INACTIVE / DATA GAP" for item in context_states),
                "actors": context_states,
            }
        shadow_ownship = None
        shadow_comparison = {"status": "NOT_AVAILABLE"}
        ownship_object = session.ship_list[0]
        shadow_sample_at = getattr(ownship_object, "shadow_sample_at", None)
        handoff_source_s = getattr(ownship_object, "counterfactual_t0_s", None)
        if shadow_sample_at is not None and handoff_source_s is not None and source_time >= float(handoff_source_s):
            shadow_sample = shadow_sample_at(source_time)
            if shadow_sample is not None:
                north, east, velocity_north, velocity_east = shadow_sample.state_vxvy
                speed = float(np.hypot(velocity_north, velocity_east))
                course = float(np.arctan2(velocity_east, velocity_north)) if speed > 1e-12 else 0.0
                local_north = float(north - origin_n)
                local_east = float(east - origin_e)
                deviation = float(np.hypot(float(own.get("x", 0.0)) - local_north, float(own.get("y", 0.0)) - local_east))
                self._shadow_max_deviation_m = max(self._shadow_max_deviation_m, deviation)
                course_delta = float(
                    np.arctan2(
                        np.sin(float(own.get("cog", 0.0)) - course),
                        np.cos(float(own.get("cog", 0.0)) - course),
                    )
                )
                actor = getattr(ownship_object, "historical_actor", None)
                trail = []
                if actor is not None:
                    trail = [
                        [float(sample.state_vxvy[0] - origin_n), float(sample.state_vxvy[1] - origin_e)]
                        for sample in actor.samples
                        if float(handoff_source_s) <= sample.time_s <= source_time
                    ]
                shadow_ownship = {
                    "id": "shadow-ownship",
                    "label": "AIS SHADOW",
                    "mmsi": int(getattr(ownship_object, "mmsi", 0)),
                    "x": local_north,
                    "y": local_east,
                    "north": float(north),
                    "east": float(east),
                    "psi": course,
                    "cog": course,
                    "sog": speed,
                    "trajectory": trail,
                    "sample_kind": shadow_sample.kind.value.upper(),
                    "comparison_only": True,
                }
                shadow_comparison = {
                    "status": "AVAILABLE",
                    "handoff_sim_time_s": float(handoff_source_s)
                    - float(self.prepared.spec.historical_replay.get("t_start_s", 0.0)),
                    "handoff_source_time_s": float(handoff_source_s),
                    "deviation_m": deviation,
                    "maximum_deviation_m": self._shadow_max_deviation_m,
                    "delta_cog_rad": course_delta,
                    "delta_sog_mps": float(own.get("sog", 0.0)) - speed,
                    "comparison_only": True,
                    "recovery": jsonable(session.historical_recovery_status),
                }
                self._last_shadow_ownship = dict(shadow_ownship)
                self._last_shadow_comparison = dict(shadow_comparison)
        if (
            handoff_source_s is not None
            and shadow_ownship is None
            and self._last_shadow_ownship is not None
            and self._last_shadow_comparison is not None
        ):
            shadow_ownship = {
                **self._last_shadow_ownship,
                "sample_kind": "INACTIVE / DATA GAP",
                "active": False,
            }
            shadow_comparison = {
                **self._last_shadow_comparison,
                "status": "INACTIVE / DATA GAP",
                "recovery": jsonable(session.historical_recovery_status),
            }
        return {
            "schema_version": "1.0",
            "run_id": self.session_id,
            "scenario_id": self.prepared.spec.scenario_id,
            "seq": session.sequence,
            **runtime_time,
            "state": session.state.value,
            "result_ready": self.result is not None,
            "truth": ships,
            "measurements": [ship["measurements"] for ship in ships],
            "tracks": [ship["tracks"] for ship in ships],
            "plans": {
                "waypoints": local_waypoints,
                "prediction_horizon": self.current_prediction_horizon,
                "previous_prediction_horizon": self.previous_prediction_horizon,
                "rejected_prediction_horizon": rejected_prediction_horizon,
                "target_prediction_horizons": target_prediction_horizons,
                "rejected_target_prediction_horizons": rejected_target_prediction_horizons,
                "target_routes": target_routes,
                "prediction_render": jsonable(prediction_render) if typed_render else None,
            },
            "enc_navigation_area": self.enc_navigation_area,
            "encounters": encounters,
            "primary_encounter": primary_encounter,
            "threat_management": threat_management,
            "planner": planner,
            "latest_planner_solve": self.latest_planner_solve,
            "active_planner_plan": self.active_planner_plan,
            "latest_planner_attempt": self.latest_planner_attempt,
            "execution": jsonable(execution),
            "events": jsonable(events),
            "operational_events": jsonable(operational_events),
            "step": session.sequence,
            "scenario_time": runtime_time["sim_time"],
            "running": session.state == SessionState.RUNNING,
            "os": own,
            "shadow_ownship": shadow_ownship,
            "shadow_comparison": shadow_comparison,
            "historical_context": historical_context,
            "obstacles": obstacles,
            "waypoints": local_waypoints,
            "prediction_horizon": self.current_prediction_horizon,
            "previous_prediction_horizon": self.previous_prediction_horizon,
            "target_routes": target_routes,
            "dcpa": dcpa,
            "tcpa": tcpa,
            "colregs": encounter,
            "safety_margin": None,
            "selected_algorithm": self.prepared.manifest.executed_algorithm,
            "requested_algorithm": self.prepared.manifest.requested_algorithm,
            "executed_algorithm": self.prepared.manifest.executed_algorithm,
            "requested_tracker": self.prepared.manifest.requested_tracker,
            "executed_tracker": self.prepared.manifest.executed_tracker,
            "selected_rule": self.prepared.spec.validation_rule_id,
            "selected_scenario": self.prepared.spec.scenario_id,
            "modular_gnc": _modular_gnc_telemetry_metadata(session),
            "original_gnc": _original_gnc_telemetry_metadata(session),
            "gnc_balance": balance_telemetry(session, frame=frame),
            "step_time_ms": step_ms,
            "playback": self._playback_status(),
            "failure_reason": session.failure_reason,
            "baseline_threat_failure_reason": session.baseline_threat_failure_reason,
            "reproduction_status": self.result.manifest.reproduction_status if self.result else "running",
            # P3-S1 additive field (spec #90): radar_x PPI parameterization for the
            # web PPI panel. Null when no sensor exposes a ppi_descriptor. Top-level
            # envelope key survives all transports (_compact_stream_payload only
            # strips truth[]-level keys); web consumes leniently.
            "radar_ppi": _radar_ppi_descriptor(self.prepared),
        }

    @staticmethod
    def _local_tracks(raw: dict[str, Any], origin_n: float, origin_e: float) -> dict[str, Any]:
        states = []
        for state in raw.get("do_estimates", []):
            local = list(np.asarray(state, dtype=float))
            if len(local) >= 2:
                local[0] -= origin_n
                local[1] -= origin_e
            states.append(local)
        # P3-S5 (spec #90): sensor-model-v1 §6 additive confidence arrays.
        # Parallel to labels[]; missing frame keys fall back to None (= legacy
        # publisher shape), which TracksSnapshotV1 treats as optional.
        existence = [float(value) for value in raw.get("do_existence_probabilities", [])]
        qualities = [float(value) for value in raw.get("do_qualities", [])]
        sources = []
        for track_sources in raw.get("do_sources", []):
            entries = []
            for source in track_sources if isinstance(track_sources, list) else ():
                if isinstance(source, dict):
                    entries.append(
                        {
                            "sensor_id": int(source.get("sensor_id", 1)),
                            "last_seen_age_s": source.get("last_seen_age_s"),
                        }
                    )
            sources.append(entries)
        return jsonable(
            {
                "labels": raw.get("do_labels", []),
                "generations": raw.get("do_generations", []),
                "states": states,
                "covariances": raw.get("do_covariances", []),
                "nis": raw.get("do_NISes", []),
                "existence_prob": existence or None,
                "quality": qualities or None,
                "sources": sources or None,
            }
        )


def _bounded_playback_deadline(
    previous_deadline: float,
    now: float,
    interval: float,
    *,
    max_catch_up_s: float = 3.0,
) -> tuple[float, float]:
    # Preserve recoverable solver gaps across rates. A step-count limit loses
    # wall-clock debt at 5x even when subsequent full steps can catch up.
    deadline = previous_deadline + interval
    deadline = max(deadline, now - max_catch_up_s)
    return deadline, max(0.0, now - deadline)


async def _simulation_loop() -> None:
    active_key: tuple[str | None, int, bool] | None = None
    next_deadline = 0.0
    sample_wall = 0.0
    sample_sim: float | None = None
    effective_multiplier: float | None = None
    while True:
        loop = asyncio.get_running_loop()
        clock = manager.playback_clock()
        key = (clock["session_id"], clock["revision"], clock["running"])
        now = loop.time()
        if key != active_key:
            active_key = key
            next_deadline = now
            sample_wall = now
            sample_sim = None
            effective_multiplier = None
            if clock["running"]:
                manager.update_playback_metrics(
                    effective_multiplier=None,
                    scheduler_lag_ms=0.0,
                    realtime_limited=False,
                )

        if not clock["running"]:
            await asyncio.sleep(0.05)
            continue

        sim_time = await asyncio.to_thread(manager.tick)
        if sim_time is None:
            await asyncio.sleep(0)
            continue

        now = loop.time()
        interval = max(0.001, clock["dt"] / max(clock["multiplier"], 0.1))
        next_deadline, lag = _bounded_playback_deadline(next_deadline, now, interval)
        if sample_sim is None:
            sample_wall = now
            sample_sim = sim_time
        sample_elapsed = now - sample_wall
        if sample_elapsed >= 0.5 and sample_sim is not None:
            effective_multiplier = max(0.0, (sim_time - sample_sim) / sample_elapsed)
        realtime_limited = effective_multiplier is not None and effective_multiplier < clock["multiplier"] * 0.9
        manager.update_playback_metrics(
            effective_multiplier=effective_multiplier,
            scheduler_lag_ms=lag * 1000.0,
            realtime_limited=realtime_limited,
        )
        await asyncio.sleep(max(0.0, next_deadline - loop.time()))


@asynccontextmanager
async def lifespan(_: FastAPI):
    if os.environ.get("COLAV_HAIS_PREWARM_ON_STARTUP", "").strip() == "1":
        started = time.perf_counter()
        log.info("Preloading Historical AIS ENC before accepting sessions")
        try:
            request = SessionCreateRequest(
                validation_rule_id="multiship",
                scenario_id="hais_romsdal_20260701_120007_121007",
                algorithm_id="vo",
                tracker_id="vimmjipda",
            )
            spec = _historical_session_spec(request)
            if spec is not None:
                await asyncio.to_thread(manager.runner.preload_historical_enc, spec)
                manager.historical_spec_cache[request.scenario_id] = spec
            log.info("Historical AIS ENC ready in %.1fs", time.perf_counter() - started)
        except Exception:  # noqa: BLE001 - optional startup acceleration
            log.exception("Historical AIS ENC preload failed; Create will retry synchronously")
    task = asyncio.create_task(_simulation_loop())
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


manager = WebSessionManager()
app = FastAPI(title="COLAV Simulator Research Control", version="1.0", lifespan=lifespan)
app.include_router(historical_api_router)
# Sealed Run Replay discovery, inspection and deletion. The store
# root resolves exactly like the writer (project-root anchored runs/), so
# discovery can never diverge from where runs are written.
replay_store = RunReplayStore(runs_root())
app.include_router(
    build_replay_router(
        replay_store, active_replay_status=manager.replay_status_for, active_run_id=lambda: manager.session_id
    )
)


@app.get("/api/runs/{run_id}/replay/navigation-profile")
def api_replay_navigation_profile(run_id: str) -> dict[str, str]:
    """Materialize optional chart-depth readouts without changing sealed frames."""
    try:
        run_dir = replay_store.run_dir(run_id)
        ensure_navigation_profile(run_dir)
    except Exception as exc:
        log.warning("Replay chart-depth derivation unavailable for %s: %s", run_id, exc)
        raise HTTPException(status_code=409, detail="Matching recorded ENC depth is unavailable") from exc
    return {"run_id": run_id, "status": "READY"}
if GUI_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(GUI_DIR)), name="static")


@app.get("/", response_model=None)
def root() -> FileResponse | HTMLResponse:
    index = GUI_DIR / "index.html"
    return FileResponse(index) if index.exists() else HTMLResponse("<h1>COLAV Simulator</h1>")


@app.get("/api/scenarios")
def api_scenarios() -> list[dict[str, Any]]:
    return manager.runner.list_scenarios()


@app.get("/api/capabilities")
def api_capabilities(validation_rule_id: str | None = None) -> dict[str, Any]:
    try:
        return manager.runner.list_capabilities(validation_rule_id)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=_execution_error_detail(exc)) from exc


@app.get("/api/gnc/stacks")
def api_gnc_stacks() -> dict[str, Any]:
    """Expose only modular stacks the backend validated (Issue #60, AC1/AC3)."""
    return list_stack_catalog()


@app.get("/api/algorithms")
def api_algorithms() -> list[dict[str, Any]]:
    return [status.to_dict() for status in manager.runner.registry.statuses().values()]


@app.get("/api/integrations")
def api_integrations() -> dict[str, Any]:
    """Expose product integrations without presenting retained legacy builders as selectable."""
    catalog = manager.runner.list_capabilities()
    policy = manager.runner.capabilities.policy
    entries = [*catalog["algorithms"], *catalog["trackers"]]
    product_ids = set(policy.algorithm_ids) | set(policy.tracker_ids)
    product = [
        {
            **entry,
            "availability_scope": "product",
            "available": bool(entry.get("dependency_available")),
            "selectable": bool(entry.get("selectable")),
        }
        for entry in entries
        if entry["id"] in product_ids
    ]
    internal_legacy = [
        {
            "id": entry["id"],
            "kind": entry["kind"],
            "availability_scope": "internal_legacy",
            "available": False,
            "dependency_available": False,
            "selectable": False,
            "incompatibility_reason": "Retained for internal replay/evaluator compatibility only.",
        }
        for entry in entries
        if entry["id"] not in product_ids
    ]
    return {
        "schema_version": "integration-catalog.v1",
        "product_capability_policy": policy.to_dict(),
        "product": product,
        "internal_legacy": internal_legacy,
    }


@app.get("/api/busy-water/generate")
def api_busy_water_generate(
    profile: str = "acceptance",
    target_count: int = DEFAULT_TARGET_COUNT,
    seed: int = DEFAULT_SEED,
    crossing_ratio: float = 0.6,
    head_on_ratio: float = 0.2,
    overtaking_ratio: float = 0.2,
) -> dict[str, Any]:
    try:
        if not 0 <= target_count <= 40:
            raise ValueError("target_count must be an integer in [0, 40]")
        encounter_mix = normalize_encounter_mix(
            {
                "crossing": crossing_ratio,
                "head_on": head_on_ratio,
                "overtaking": overtaking_ratio,
            }
        )
        document = build_busy_water_document(
            profile,
            seed=seed,
            target_count=target_count,
            encounter_mix=encounter_mix,
        )
        return {
            "profile": profile,
            "seed": seed,
            "encounter_mix": encounter_mix,
            "document": document,
            "preflight": preflight_document(document, seed=seed),
        }
    except Exception as exc:
        raise HTTPException(status_code=422, detail=_execution_error_detail(exc)) from exc


@app.get("/api/coordinates/to-wgs84")
def api_coordinates_to_wgs84(north: float, east: float, utm_zone: int = 33) -> dict[str, float]:
    try:
        latitude, longitude = mapf.local2latlon(east, north, utm_zone)
        return {"latitude": float(latitude), "longitude": float(longitude)}
    except Exception as exc:
        raise HTTPException(status_code=422, detail=_execution_error_detail(exc)) from exc


@app.get("/api/coordinates/to-utm")
def api_coordinates_to_utm(latitude: float, longitude: float, utm_zone: int = 33) -> dict[str, float]:
    try:
        east, north = mapf.latlon2local(latitude, longitude, utm_zone)
        return {"north": float(north), "east": float(east)}
    except Exception as exc:
        raise HTTPException(status_code=422, detail=_execution_error_detail(exc)) from exc


@app.get("/api/busy-water/drafts")
def api_busy_water_drafts() -> list[dict[str, Any]]:
    return list_busy_water_drafts()


@app.get("/api/busy-water/drafts/{identifier}")
def api_busy_water_draft(identifier: str) -> dict[str, Any]:
    try:
        return load_busy_water_draft(identifier)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Busy-water draft not found") from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail=_execution_error_detail(exc)) from exc


@app.post("/api/busy-water/drafts")
def api_save_busy_water_draft(request: BusyWaterDraftRequest) -> dict[str, Any]:
    try:
        return save_busy_water_draft(request)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=_execution_error_detail(exc)) from exc


@app.post("/api/sessions")
def api_create_session(request: SessionCreateRequest) -> dict[str, Any]:
    try:
        spec = _historical_session_spec(request) or request.to_spec()
        return manager.create(spec, record_replay_trace=request.record_replay_trace)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=_execution_error_detail(exc)) from exc


@app.get("/api/sessions/current")
def api_current_session() -> dict[str, Any]:
    with manager.lock:
        description = manager.describe()
    if not description["active"]:
        raise HTTPException(status_code=404, detail="No active session")
    return description


@app.get("/api/sessions/{session_id}")
def api_session(session_id: str) -> dict[str, Any]:
    try:
        manager._require(session_id)
        return manager.describe()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc


# P3-S2 observations injection (spec #90; contract sango/Docs/contracts/observations-v1.md).
# Error body = the frozen code string in `detail` (§4 table; schema violations keep the
# FastAPI/pydantic default 422 shape, which the contract sanctions).
@app.post("/api/sessions/{session_id}/observations")
def api_session_observations(session_id: str, frame: ObservationFrame) -> dict[str, Any]:
    try:
        return manager.ingest_observations(session_id, frame)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="SESSION_NOT_FOUND") from exc
    except SessionNotAcceptingError as exc:
        raise HTTPException(status_code=409, detail="SESSION_NOT_ACCEPTING") from exc
    except FrameSeqRegressionError as exc:
        raise HTTPException(status_code=409, detail="FRAME_SEQ_REGRESSION") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="VALIDATION_ERROR") from exc


@app.get("/api/sessions/{session_id}/observations")
def api_session_observations_status(session_id: str) -> dict[str, Any]:
    """E2E/test hook for the observation measurement cache.

    Accepted-frame counters + pending georeferenced measurements
    (sensor_id 2|3) held in the session measurement cache.
    """
    try:
        return manager.observation_status(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="SESSION_NOT_FOUND") from exc


# P3-S5 (spec #90) high-confidence track data product: the ownship's latest
# tracker snapshot set gated by existence probability, in the frozen
# sensor-model-v1 §5 envelope. Whitelist-additive route; compact-v1 untouched.
@app.get("/api/sessions/{session_id}/confirmed-tracks")
def api_session_confirmed_tracks(
    session_id: str,
    min_existence_prob: float = CONFIRMED_TRACKS_DEFAULT_THRESHOLD,
) -> dict[str, Any]:
    try:
        return manager.confirmed_tracks(session_id, min_existence_prob)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="SESSION_NOT_FOUND") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="VALIDATION_ERROR") from exc


@app.post("/api/sessions/{session_id}/start")
def api_session_start(session_id: str) -> dict[str, Any]:
    try:
        return manager.start(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/sessions/{session_id}/pause")
def api_session_pause(session_id: str) -> dict[str, Any]:
    try:
        return manager.pause(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc


@app.post("/api/sessions/{session_id}/speed")
def api_session_speed(session_id: str, multiplier: float = 1.0) -> dict[str, Any]:
    try:
        return manager.set_speed(session_id, multiplier)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc


@app.post("/api/sessions/{session_id}/step")
def api_session_step(session_id: str) -> dict[str, Any]:
    try:
        return manager.step(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/sessions/{session_id}/reset")
def api_session_reset(session_id: str) -> dict[str, Any]:
    try:
        return manager.reset(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/sessions/{session_id}/replay")
def api_session_replay(session_id: str) -> dict[str, Any]:
    try:
        return manager.replay(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/sessions/{session_id}/result")
def api_session_result(session_id: str) -> dict[str, Any]:
    try:
        return manager.result_document(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/sessions/{session_id}/artifacts")
def api_session_artifacts(session_id: str) -> list[dict[str, Any]]:
    try:
        return manager.artifacts(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc


@app.get("/api/sessions/{session_id}/artifacts/{name}", response_model=None)
def api_session_artifact(session_id: str, name: str) -> FileResponse:
    try:
        return FileResponse(manager.artifact(session_id, name), filename=name)
    except (KeyError, FileNotFoundError) as exc:
        raise HTTPException(status_code=404, detail="Artifact not found") from exc


@app.get("/api/enc_info")
def api_enc_info() -> JSONResponse:
    return JSONResponse(manager.enc_info())


@app.get("/api/sessions/{session_id}/navigation-area")
def api_navigation_area(session_id: str) -> dict[str, Any]:
    try:
        return manager.navigation_area(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc


@app.get("/api/sessions/{session_id}/planner/decision-space", response_model=None)
def api_planner_decision_space(
    session_id: str,
    solve_id: int,
) -> JSONResponse | Response:
    try:
        snapshot = manager.planner_decision_space(session_id, solve_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if snapshot is None:
        return Response(status_code=204)
    return JSONResponse(snapshot)


@app.get("/api/enc_tile", response_model=None)
def api_enc_tile(run_id: str | None = None) -> FileResponse:
    prepared = manager.prepared
    if not prepared:
        raise HTTPException(status_code=503, detail="No active session")
    if run_id is not None and run_id != prepared.manifest.run_id:
        raise HTTPException(status_code=409, detail="ENC session changed")
    return FileResponse(prepared.run_dir / "enc.png", media_type="image/png")


@app.get("/api/algo_status")
def api_algo_status() -> JSONResponse:
    """Expose only product-active integrations and their selection constraints."""
    policy = manager.runner.capabilities.policy
    statuses = manager.runner.registry.statuses()
    product_ids = set(policy.algorithm_ids) | set(policy.tracker_ids)
    product = []
    for identifier in (*policy.algorithm_ids, *policy.tracker_ids):
        status = statuses.get(identifier)
        if status is None:
            continue
        product.append(
            {
                **status.to_dict(),
                "active": True,
                "available": bool(status.available),
                "selectable": bool(status.available),
                "constraints": policy.constraints(identifier)
                if identifier in policy.algorithm_ids
                else {"requires_explicit_tracker_id": True},
            }
        )
    internal_legacy = [
        {
            "integration_id": identifier,
            "kind": status.kind,
            "active": False,
            "available": False,
            "selectable": False,
            "reason": "Retained for internal replay/evaluator compatibility only.",
        }
        for identifier, status in sorted(statuses.items())
        if identifier not in product_ids
    ]
    return JSONResponse(
        {
            "schema_version": "product-algorithm-status.v1",
            "product": product,
            "algorithms": [item for item in product if item["kind"] == "algorithm"],
            "trackers": [item for item in product if item["kind"] == "tracker"],
            "constraints": policy.to_dict()["constraints"],
            "internal_legacy": internal_legacy,
        }
    )


@app.post("/api/start")
def api_start() -> dict[str, Any]:
    raise HTTPException(
        status_code=410,
        detail={
            "status": "DEPRECATED_ENDPOINT",
            "endpoint": "/api/start",
            "replacement": "/api/sessions/{session_id}/start",
        },
    )


@app.post("/api/pause")
def api_pause() -> dict[str, Any]:
    raise HTTPException(
        status_code=410,
        detail={
            "status": "DEPRECATED_ENDPOINT",
            "endpoint": "/api/pause",
            "replacement": "/api/sessions/{session_id}/pause",
        },
    )


@app.post("/api/reset")
def api_reset(scenario: str = "Head-on") -> dict[str, Any]:
    raise HTTPException(
        status_code=410,
        detail={
            "status": "DEPRECATED_ENDPOINT",
            "endpoint": "/api/reset",
            "replacement": "/api/sessions/{session_id}/reset",
            "legacy_scenario": scenario,
        },
    )


@app.post("/api/select_algorithm")
def api_select_algorithm(algorithm: str = "vo") -> dict[str, Any]:
    """Deprecated selector constrained to the current product exact tuple."""
    algorithm_id = algorithm.strip().lower()
    try:
        current = manager.prepared.spec if manager.prepared is not None else None
        if current is None:
            raise ColavExecutionError(
                PlanStatus.INVALID_INPUT,
                "Deprecated algorithm selector requires an active product session",
            )
        if (
            current.validation_rule_id is None
            or current.historical_replay is not None
            or current.historical_scenario_id is not None
        ):
            raise ColavExecutionError(
                PlanStatus.INVALID_INPUT,
                "Deprecated algorithm selector requires an active product exact tuple",
            )
        manager.runner.capabilities.policy.validate(
            current.validation_rule_id,
            current.scenario_id,
            algorithm_id,
            current.tracker_id,
        )
        description = manager.create(replace(current, algorithm_id=algorithm_id))
    except Exception as exc:
        raise HTTPException(status_code=422, detail=_execution_error_detail(exc)) from exc
    return {"status": "ok", "algorithm": algorithm_id, **description}


@app.post("/api/set_speed")
def api_set_speed(multiplier: float = 1.0) -> dict[str, Any]:
    if manager.session_id is None:
        raise HTTPException(status_code=409, detail="No active session")
    playback = manager.set_speed(manager.session_id, multiplier)
    return {
        "status": "ok",
        "speed_multiplier": playback["requested_multiplier"],
        "playback": playback,
    }


async def _stream(
    websocket: WebSocket,
    session_id: str | None = None,
    *,
    compact: bool = False,
    static_once: bool = False,
    shared_planner: bool = False,
) -> None:
    await websocket.accept()
    include_static = True
    receive_task = asyncio.create_task(websocket.receive())
    try:
        while True:
            if session_id and manager.session_id != session_id:
                await websocket.send_json({"error": "session_not_found"})
                return
            await websocket.send_text(
                await asyncio.to_thread(
                    manager.stream_document,
                    compact=compact,
                    static_once=static_once,
                    shared_planner=shared_planner,
                    include_static=include_static,
                )
            )
            include_static = False
            try:
                message = await asyncio.wait_for(asyncio.shield(receive_task), timeout=0.1)
            except asyncio.TimeoutError:
                continue
            if message.get("type") == "websocket.disconnect":
                return
            receive_task = asyncio.create_task(websocket.receive())
    except (WebSocketDisconnect, ConnectionError, OSError):
        return
    except RuntimeError as exc:
        # Uvicorn's websockets-sansio implementation reports a peer-close race
        # as RuntimeError instead of OSError/WebSocketDisconnect.
        error_text = str(exc)
        if "websocket.send" not in error_text or "websocket.close" not in error_text:
            raise
        return
    finally:
        receive_task.cancel()
        with suppress(asyncio.CancelledError, WebSocketDisconnect, ConnectionError, OSError):
            await receive_task


@app.websocket("/ws/sessions/{session_id}")
async def websocket_session(websocket: WebSocket, session_id: str) -> None:
    transport = websocket.query_params.get("transport")
    await _stream(
        websocket,
        session_id,
        compact=transport == "compact-v1",
        static_once=transport == "static-once-v1",
        shared_planner=transport == "shared-planner-v1",
    )


@app.websocket("/ws")
async def websocket_legacy(websocket: WebSocket) -> None:
    await _stream(websocket)
