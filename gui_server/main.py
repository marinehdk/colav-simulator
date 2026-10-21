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
import signal
import subprocess
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
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from colav_simulator.cli import _load_algorithm_config
from colav_simulator.common import map_functions as mapf

# P3-S2 observations endpoint (spec #90 whitelist: new routes + calibration
# table + measurement hookup). ExternalCameraSensor is the session-scoped
# measurement cache the accepted frames feed (sensor-model-v1 sensor_id 2|3).
from colav_simulator.core.ais_display import AisReportClock, ais_target_state
from colav_simulator.core.colav.diagnostics import ColavExecutionError, PlanStatus
from colav_simulator.core.mast_cameras import MAST_MOUNTS_BY_ID, georeference_box
from colav_simulator.core.sensing import ExternalCameraSensor
from colav_simulator.core.tracking.trackers import sensor_channel_id
from colav_simulator.core.viewport_tracks import (
    ViewportTrackService,
    camera_pose_valid,
)
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
from colav_simulator.environment_settings import normalize_settings
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
from colav_simulator.schemas.viewport_detections_v1 import ViewportDetectionsFrame
from colav_simulator.schemas.viewport_ownship_polygon_v1 import (
    VIEWPORT_OWNSHIP_POLYGON_SCHEMA_VERSION,
    ViewportOwnshipPolygonReport,
)
from gui_server import canonical_threat as _canonical_threat
from gui_server.gnc_balance import balance_telemetry
from gui_server.historical_api import router as historical_api_router
from gui_server.pose_history import CameraPoseRing, OwnshipPoseRing
from gui_server.radar_transport import LIVE_CHECKPOINTS, project_compact_scans, project_scans
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
from gui_server.static_scene import descriptor as static_scene_descriptor
from gui_server.static_scene import router as static_scene_router
from gui_server.twin_runtime import TwinRuntime, TwinRuntimeError

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
# DT 视口 YOLO 检测分流:telemetry 顶层键 viewport_detections 的过期上界(秒)。
# received_at 距广播构建时刻超过该值即不再注入(键整体缺省)。
VIEWPORT_DETECTION_MAX_AGE_S = 2.0
# P3 viewport_tracks@1:confirmed 航迹文档与 viewport_detections 同生命周期
# (检测停 → 两键一起缺省 → web 回退 DET 不悬挂);跟踪步 received_at 判过期。
VIEWPORT_TRACKS_MAX_AGE_S = VIEWPORT_DETECTION_MAX_AGE_S
# 评审 Q1/Q2:检测采集→收包延迟常量(后端镜像 web twin-situation.js 的
# DETECTION_CAPTURE_INFERENCE_MS=80 + DETECTION_CAPTURE_TAP_MS=50;两侧字面量
# 需一起改)。采集时刻 = 收包墙钟 − 该值,在位姿环上插值。
DETECTION_CAPTURE_LATENCY_S = (80.0 + 50.0) / 1000.0
# 评审 Q2 运行时检测:P1 中继 camera_pose 龄期门——Unity 桥断流超过该值即弃
# 跟踪腿(陈旧位姿 georef 会系统性抹 bearing),限频告警留痕。
VIEWPORT_TRACKS_RELAY_MAX_AGE_S = 2.0
# 通用限频告警窗(秒):Q2 各运行时偏差检测共用,不刷日志。
_WARN_RATE_LIMIT_S = 10.0
_rate_limit_state: dict[str, float] = {"last_warn_s": 0.0}  # 可变单例,免 global 重绑


def _warn_rate_limited(message: str, *args: Any) -> None:
    """限频 WARNING(同窗多源合并;时钟轴/中继断流类检测用,不刷日志)."""
    now = time.monotonic()
    if now - _rate_limit_state["last_warn_s"] >= _WARN_RATE_LIMIT_S:
        _rate_limit_state["last_warn_s"] = now
        log.warning(message, *args)
# DT 视口 YOLO 检测引擎:勾选"YOLO 检测"图层即拉起/停掉检测器进程(detached,
# 后端重启不连坐;pidfile 与 deploy/twin/detectctl 共管)。检测器免会话——
# POST /api/viewport-detections 由后端路由进当前活动会话,会话换新零重接线。
VIEWPORT_DETECTOR_PY = BASE_DIR / ".venv-detector" / "bin" / "python"
VIEWPORT_DETECTOR_SCRIPT = BASE_DIR / "tools" / "sango_detector_service.py"
VIEWPORT_DETECTOR_PIDFILE = BASE_DIR / "deploy" / "twin" / "logs" / "detector.pid"
VIEWPORT_DETECTOR_LOG = BASE_DIR / "deploy" / "twin" / "logs" / "detector.log"
VIEWPORT_DETECTOR_FORWARD_URL = os.environ.get(
    "VIEWPORT_ENGINE_FORWARD_URL", "http://127.0.0.1:8010/api/viewport-detections"
)
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
    if payload.get("radar_scans"):
        compact["radar_scans"] = project_compact_scans(payload["radar_scans"], LIVE_CHECKPOINTS.reference)
    compact.pop("ais_reports", None)
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
    if payload.get("radar_scans"):
        streamed["radar_scans"] = project_scans(payload["radar_scans"], LIVE_CHECKPOINTS.reference)
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
    environment_settings: dict[str, Any] | None = None
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
        self.twin_runtime = TwinRuntime(BASE_DIR)
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
        # dt-sensor-overlay (2026-10-11 contract §2.1): display-only ring cache of
        # georeferenced detections in absolute scene NE. Independent of the sensor
        # inbox (drained by the tracker measurement loop); leaf-locked so ingest
        # (under self.lock) and the telemetry tick thread can share it safely.
        self._observation_display_cache: deque[dict[str, Any]] = deque(maxlen=512)
        self._observation_display_lock = threading.Lock()
        # DT 视口 YOLO 检测分流:会话级最新一帧(display-only,遥测注入体;
        # 只留最新——旧帧被新 POST 覆写,过期由 _viewport_detections_envelope 判)。
        self._viewport_detection: dict[str, Any] | None = None
        # 到达即推版本号(SSE):ingest 每次 +1;检测文档不搭仿真步节拍的全量文档车
        self._viewport_detection_version = 0
        # P3 检测→跟踪层:viewport detections → observations/IPDA 装配(vimmjipda
        # 惰性装配;会话级,换会话即弃)。getattr 容错:测试替身绕过 __init__。
        self._viewport_track_service: ViewportTrackService | None = None
        # 评审 Q1:权威本船位姿环(tick 采样;采集时刻插值 georef 用;会话级)。
        self._ownship_pose_ring = OwnshipPoseRing()
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
            self.twin_runtime.release(previous.manifest.run_id)
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
        with self._observation_display_lock:
            self._observation_display_cache.clear()
        # 新会话清空上一会话的检测分流帧(reset 即清);P3:航迹不跨会话延续
        # (与 web 端 run 切换清场对齐;跟踪器随服务重建)。链式赋值保持语句数。
        self._viewport_detection = self._viewport_track_service = None
        self._ownship_pose_ring.reset()  # 位姿环随会话重置(评审 Q1;不跨 run 外推)
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

    def start_twin(self, session_id: str) -> dict[str, Any]:
        with self.lock:
            prepared = self._require(session_id)
            if prepared.session.state in {SessionState.FINISHED, SessionState.FAILED}:
                raise RuntimeError("The active session has ended")
            startup = self.twin_runtime.start(session_id)
        result = startup.result()
        with self.lock:
            prepared = self._require(session_id)
            if prepared.session.state in {SessionState.FINISHED, SessionState.FAILED}:
                raise RuntimeError("The active session has ended")
        return result

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
                    self.twin_runtime.release(prepared.manifest.run_id)
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
                # 评审 Q1:tick 级权威位姿采样(墙钟+sim 钟+ownship 6 态),
                # 供观测/视口 georef 在采集时刻插值(pose_history 环)。
                self._ownship_pose_ring.sample(
                    time.time(),
                    float(self.prepared.session.simulator.t),
                    np.asarray(self.prepared.session.ship_list[0].state, dtype=float),
                )
                self._record_telemetry_trails(snapshot.payload)
                self._record_ais_reports(snapshot.payload)
                self._append_trace_capture(snapshot)
                finished = self.prepared.session.state == SessionState.FINISHED
                if finished or self._telemetry_refresh_due(snapshot, now=time.monotonic()):
                    self._publish_telemetry(snapshot)
                if finished:
                    self.twin_runtime.release(self.prepared.manifest.run_id)
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
        self.twin_runtime.release(prepared.manifest.run_id)
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
        zone = int(enc.utm_zone)
        if zone in (32, 33):
            # Horizontal part of the existing ETRS89 / UTM + NN54 compound CRS.
            horizontal_crs: str | None = f"EPSG:{25800 + zone}"
        elif 1 <= zone <= 60:
            horizontal_crs = f"EPSG:{32600 + zone}"
        else:
            horizontal_crs = None
        return {
            "ready": True,
            "origin_e": float(enc.origin[0]),
            "origin_n": float(enc.origin[1]),
            "width": float(enc.size[0]),
            "height": float(enc.size[1]),
            "utm_zone": zone,
            "horizontal_crs": horizontal_crs,
            "hemisphere": "north" if 1 <= zone <= 60 else None,
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

        Georef pose = 采集时刻的权威本船位姿(评审 Q1 修复):收包墙钟 −
        ``DETECTION_CAPTURE_LATENCY_S`` 在 tick 采样位姿环(pose_history)上插值,
        回转 bearing 抹扫从 yaw_rate×(0.13-0.5s) 收到插值误差级;环空/越窗
        (双钟轴偏差,环限频告警,Q2)回退收包时刻位姿(修复前行为,有界)。
        契约 §5.4 名义上的 frame_time_s 是 Unity 域参考戳——服务端无 Unity→
        墙钟/仿真钟桥,维持落库不消费(实现偏差如实记录于此);记录 ``t_s``
        用插值出的采集时刻 sim 钟。
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

            capture = None
            ring = getattr(self, "_ownship_pose_ring", None)
            if ring is not None:
                capture = ring.at_wall(time.time() - DETECTION_CAPTURE_LATENCY_S)
            if capture is not None:
                sim_t, ship_state = capture
            else:
                sim_t = float(prepared.session.simulator.t)
                ship_state = np.asarray(prepared.session.ship_list[0].state, dtype=float)
            own_north, own_east, own_yaw = float(ship_state[0]), float(ship_state[1]), float(ship_state[2])
            mount = MAST_MOUNTS_BY_ID[frame.mount_id]
            sensor = self._camera_sensor_for(prepared)
            records = []
            display_records = []
            for ordinal, detection in enumerate(frame.detections):
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
                        "t_s": sim_t,
                        "mount_id": frame.mount_id,
                        "frame_seq": int(frame.frame_seq),
                        "frame_time_s": float(frame.frame_time_s),
                    }
                )
                # dt-sensor-overlay contract §2.1: display copy in absolute scene NE
                # (the sensor record above stays ownship-relative for the tracker);
                # local-frame projection + display-only association happen in
                # _display_observations on the telemetry side.
                display_records.append(
                    {
                        "north_abs": float(georef.north_m),
                        "east_abs": float(georef.east_m),
                        "confidence": float(detection.confidence),
                        "class_name": detection.class_name,
                        "sensor_id": int(frame.sensor_id),
                        "t_s": sim_t,
                        "frame_seq": int(frame.frame_seq),
                        "det_id": f"{frame.sensor_id}:{frame.frame_seq}:{ordinal}",
                    }
                )
            sensor.submit(records, frame_seq=frame.frame_seq)
            with self._observation_display_lock:
                self._observation_display_cache.extend(display_records)
            self._observation_seq_gate[gate_key] = frame.frame_seq
            totals = self._observation_totals.setdefault(
                gate_key, {"frames": 0, "detections": 0}
            )
            totals["frames"] += 1
            totals["detections"] += len(records)
            return {"accepted": True, "frame_seq": frame.frame_seq, "detections_accepted": len(records)}

    def ingest_viewport_detections(self, session_id: str, frame: ViewportDetectionsFrame) -> dict[str, Any]:
        """DT 视口 YOLO 检测分流:存会话级最新一帧供遥测注入(display-only).

        Gates mirror ``ingest_observations`` **except** PAUSED is accepted:
        sim 暂停时 Unity 画面与 tap 帧照发(渲染钟独立),检测框属显示层,
        暂停看画面时绿框必须在——session must exist (404);CREATED/RUNNING/PAUSED
        accept,其余 409 SESSION_NOT_ACCEPTING;schema violations are rejected
        by the pydantic body model (422). Only the latest frame is kept — each
        POST overwrites the envelope and stamps ``received_at`` (server wall
        clock; a client value is never trusted).

        P3 跟踪腿(仅 CREATED/RUNNING):同一帧经 P1 中继 camera_pose georef
        进 observations/IPDA 装配 → viewport_tracks@1(见 _feed_viewport_tracks;
        PAUSED 只显示不喂——sim 钟冻结,记录会在缓存里积压到恢复)。
        """
        with self.lock:
            prepared = self._require(session_id)
            if prepared.session.state not in (SessionState.CREATED, SessionState.RUNNING, SessionState.PAUSED):
                raise SessionNotAcceptingError(prepared.session.state.value)
            self._viewport_detection = {
                "schema": "viewport_detections@1",
                "pts_s": float(frame.pts_s),
                "width": int(frame.width),
                "height": int(frame.height),
                "source": str(frame.source),
                "detections": [detection.model_dump() for detection in frame.detections],
                # 本船抑制命中态透传(ownship-mask-v1 §5;旧发送端 None 原样保留)
                "ownship_mask": frame.ownship_mask,
                "received_at": time.time(),
            }
            # getattr 容错:测试替身绕过 __init__(同 _viewport_track_service 注)
            self._viewport_detection_version = getattr(self, "_viewport_detection_version", 0) + 1
            if prepared.session.state in (SessionState.CREATED, SessionState.RUNNING):
                self._feed_viewport_tracks(prepared, frame)
            return {"accepted": True, "detections": len(frame.detections)}

    def _feed_viewport_tracks(self, prepared: PreparedRun, frame: ViewportDetectionsFrame) -> None:
        """P3:一帧视口检测 → (采集时刻位姿 georef)→ ExternalCameraSensor + IPDA.

        位姿 = 采集时刻(收包墙钟 − ``DETECTION_CAPTURE_LATENCY_S``)的双环插值
        (评审 Q1/Q2 修复):camera_pose 取 P1 中继位姿环(viewport-ownship-polygon@
        1 每批 POST 采样,web poseAtCapture 同语义);ownship 6 态 + sim 时刻取
        tick 位姿环。环空/越窗回退各自最新值(修复前行为,环已限频告警)。
        中继龄期超过 ``VIEWPORT_TRACKS_RELAY_MAX_AGE_S``(Q2 运行时检测:Unity 桥
        断流)则跳过跟踪腿并限频告警——陈旧位姿 georef 会系统性抹 bearing,宁缺
        毋错;显示帧照常存,绝不 4xx。
        跟踪步时刻 = 采集时刻的 sim 钟(评审 Q3:逐帧步进,10Hz 帧各入各步,不随
        sim tick 批量 drain)。
        """
        with _ownship_polygon_lock:
            relay_meta = dict(_ownship_polygon_meta)
        relay_pose = relay_meta.get("camera_pose") or {}
        if not camera_pose_valid(relay_pose):
            return
        updated_at = relay_meta.get("updated_at")
        relay_age_s = time.time() - float(updated_at) if isinstance(updated_at, (int, float)) else None
        if relay_age_s is None or relay_age_s > VIEWPORT_TRACKS_RELAY_MAX_AGE_S:
            _warn_rate_limited(
                "viewport track feed skipped: camera pose relay stale (>%.1fs)", VIEWPORT_TRACKS_RELAY_MAX_AGE_S
            )
            return
        capture_wall = time.time() - DETECTION_CAPTURE_LATENCY_S
        camera_pose = _camera_pose_ring.at_wall(capture_wall) or dict(relay_pose)
        capture = None
        ownship_ring = getattr(self, "_ownship_pose_ring", None)
        if ownship_ring is not None:
            capture = ownship_ring.at_wall(capture_wall)
        if capture is not None:
            sim_t, own_state = capture
        else:
            session = prepared.session
            sim_t = float(session.simulator.t)
            own_state = np.asarray(session.ship_list[0].state, dtype=float)
        service = getattr(self, "_viewport_track_service", None)  # 测试替身可绕过 __init__
        if service is None:
            service = self._viewport_track_service = ViewportTrackService()
        try:
            service.feed(
                camera_pose,
                int(frame.width),
                int(frame.height),
                [detection.model_dump() for detection in frame.detections],
                sim_t,
                own_state,
            )
        except Exception:  # noqa: BLE001 (跟踪腿失败不连坐显示分流;下帧重试)
            log.exception("viewport track feed failed; frame skipped")

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
        balance_snapshot = balance_telemetry(session, frame=frame)
        if ships and balance_snapshot is not None and balance_snapshot.get("roll_deg") is not None:
            ships[0]["has_roll"] = True
            ships[0]["roll_rad"] = math.radians(balance_snapshot["roll_deg"])
        twin_environment = normalize_settings(self.prepared.spec.environment_settings)
        observed_environment = (balance_snapshot or {}).get("environment", {})
        twin_environment["enabled"] = observed_environment.get("status") in {"AVAILABLE", "WAITING"}
        # 20261015 用户裁决:视觉水面按会话配置定档,不再用执行场观测值逐帧覆写——
        # 风浪流的真实演化由后端水动力权威计算,Unity 展示不了风/流;而观测值逐消息
        # 漂移会让 HDRP 谱参数任何 ULP 变化都触发整场频谱重建(=水面拉扯根因)。
        # 浪按配置 Hs/周期/浪向拟合一次,风/流仅作视觉常量;方向键注册表为 from 约定,
        # 原观测侧 to→from 换算一并取消。enabled 状态位保留(执行场可用性)。
        if not twin_environment.get("wave_from_deg"):
            twin_environment["wave_from_deg"] = twin_environment["wind_from_deg"]
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
            "gnc_balance": balance_snapshot,
            "environment": twin_environment,
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
            # dt-sensor-overlay (2026-10-11 contract §2): georeferenced camera
            # detections for the DT overlay (local-frame NE + display-only track
            # association). Key survives all stream transports; [] without camera
            # observations, so consumers never have to guess.
            "observations": self._display_observations(session, ships, origin_n, origin_e),
            # DT 视口 YOLO 检测分流(viewport-detections@1):用户所见帧的最新像素域
            # 检测框。无数据/过期(>2s,见 _viewport_detections_envelope)时键整体缺省;
            # 顶层键存活于全部 transports(_compact_stream_payload 只裁 truth 内部键),
            # web 消费端宽松读取。
            **self._viewport_detections_envelope(),
            # P3 viewport_tracks@1:视口检测经 observations/IPDA 装配的 confirmed
            # 航迹(confirmed 状态+existence 概率+滤波后 brg/rng;跟踪时刻冻结,
            # 不追显示帧)。无跟踪步/过期(>VIEWPORT_TRACKS_MAX_AGE_S)时键整体
            # 缺省,web 回退裸检测(DET);顶层键存活于全部 transports(同上)。
            **self._viewport_tracks_envelope(),
            "radar_scans": jsonable(own_raw.get("radar_scans", [])),
            "ais_reports": jsonable(own_raw.get("ais_reports", [])),
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

    def _display_observations(
        self,
        session: Any,
        ships: list[dict[str, Any]],
        origin_n: float,
        origin_e: float,
    ) -> list[dict[str, Any]]:
        """dt-sensor-overlay (2026-10-11 contract §2): the ``observations`` array.

        Display-only projection of recently georeferenced camera detections:
        local-frame NE (same domain as tracks states / ownship x,y), nearest-track
        association within the 50 m display gate (never written back to any sensor
        or tracker), and truth/default box dimensions. Detections older than 5 s
        are dropped; the key itself is always present at the caller.
        """
        with self._observation_display_lock:
            cached = list(self._observation_display_cache)
        if not cached:
            return []
        now = float(session.simulator.t)
        tracks = (ships[0].get("tracks") if ships else {}) or {}
        states = tracks.get("states") or []
        labels = tracks.get("labels") or []
        generations = tracks.get("generations") or []
        dimensions = {
            int(ship["id"]): (float(ship["length"]), float(ship["width"]))
            for ship in ships[1:]
        }
        run_id = self.session_id or ""
        observations: list[dict[str, Any]] = []
        for record in cached:
            age_s = now - float(record["t_s"])
            if age_s > 5.0:
                continue
            north = float(record["north_abs"]) - origin_n
            east = float(record["east_abs"]) - origin_e
            best_index = -1
            best_distance = float("inf")
            for index, state in enumerate(states):
                if len(state) < 2:
                    continue
                distance = math.hypot(float(state[0]) - north, float(state[1]) - east)
                if distance < best_distance:
                    best_distance = distance
                    best_index = index
            track_key = ""
            size = None
            if best_index >= 0 and best_distance <= 50.0:
                label = labels[best_index] if best_index < len(labels) else best_index + 1
                generation = generations[best_index] if best_index < len(generations) else None
                # Contract §1: character-for-character with the frozen web
                # targetKey `${runId}:${id}:${generation ?? 'none'}` — the §1
                # Python snippet drops the label/generation colon (typo; it
                # would emit "run:50" for label 5 gen 0 and never match the
                # web-side key). "none" only for a missing entry, never for 0.
                track_key = f"{run_id}:{label}:{'none' if generation is None else generation}"
                size = dimensions.get(int(label))
            # Contract §2.3: track label misses the truth table -> class default;
            # boat and every unknown class share the same 12 x 5 fallback.
            length, width = size if size is not None else (12.0, 5.0)
            observations.append(
                {
                    "north": north,
                    "east": east,
                    "length_m": length,
                    "width_m": width,
                    "confidence": float(record["confidence"]),
                    "class_name": str(record["class_name"]),
                    "sensor_id": int(record["sensor_id"]),
                    "age_s": max(0.0, age_s),
                    "det_id": str(record["det_id"]),
                    "track_key": track_key,
                }
            )
        return observations

    def _viewport_detections_envelope(self) -> dict[str, Any]:
        """DT 视口检测的遥测注入体(spread 用):无数据或过期时返回 {}(键整体缺省).

        age_s 按注入构建时刻的墙钟计算;_telemetry 在运行会话每个 tick 重建,
        缓存窗口 ≤ 一个发布周期(0.1s),过期键随之消失.
        """
        frame = self._viewport_detection
        if frame is None:
            return {}
        age_s = time.time() - float(frame["received_at"])
        if age_s > VIEWPORT_DETECTION_MAX_AGE_S:
            return {}
        return {"viewport_detections": {**frame, "age_s": max(0.0, age_s)}}

    def viewport_detection_event(self, last_version: int) -> tuple[int, dict[str, Any] | None]:
        """SSE 到达即推(20261020 记录仪裁决:检测文档此前搭全量文档车随仿真步
        ~2Hz 重建,PAUSED 冻结——检测属显示层,独立通道按版本变化即时下发)."""
        version = getattr(self, "_viewport_detection_version", 0)
        if version == last_version:
            return version, None
        return version, self._viewport_detections_envelope().get("viewport_detections")

    def _viewport_tracks_envelope(self) -> dict[str, Any]:
        """P3 viewport_tracks@1 注入体:无跟踪步/服务惰性/过期时 {}(键缺省).

        过期语义与 viewport_detections 同生命周期:检测断流 → 两键一起缺省,
        web 端 TRK→DET 回退即时生效(不悬挂旧航迹)。
        """
        service = getattr(self, "_viewport_track_service", None)
        if service is None:
            return {}
        document = service.document()
        if document is None:
            return {}
        age_s = time.time() - float(document["received_at"])
        if age_s > VIEWPORT_TRACKS_MAX_AGE_S:
            return {}
        return {"viewport_tracks": {**document, "age_s": max(0.0, age_s)}}


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
        cleanup = manager.twin_runtime.stop()
        if cleanup is not None:
            await asyncio.wrap_future(cleanup)


manager = WebSessionManager()
app = FastAPI(title="COLAV Simulator Research Control", version="1.0", lifespan=lifespan)
app.include_router(historical_api_router)
app.include_router(static_scene_router)


def _require_static_inspection_available() -> None:
    if manager.prepared and manager.prepared.session.state == SessionState.RUNNING:
        raise HTTPException(status_code=409, detail="Pause the active session before opening static inspection")


@app.post("/api/geography/qingdao/create")
def api_create_qingdao_static() -> dict[str, Any]:
    with manager.lock:
        _require_static_inspection_available()
        return static_scene_descriptor()


@app.post("/api/geography/qingdao/twin/start")
def api_start_qingdao_static_twin() -> dict[str, Any]:
    with manager.lock:
        _require_static_inspection_available()
        startup = manager.twin_runtime.start("geography-qingdao")
    return startup.result()

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


@app.get("/api/radar/checkpoints/{key}")
def api_radar_checkpoint(key: str) -> dict[str, Any]:
    """Read a bounded cached radar video checkpoint without sensor execution."""
    document = LIVE_CHECKPOINTS.get(key)
    if document is None:
        raise HTTPException(status_code=404, detail="RADAR_CHECKPOINT_UNAVAILABLE")
    return document


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


# DT 视口 YOLO 检测分流(viewport-detections@1):detector --viewport-forward-url 的
# 落点。校验行为照 observations 端点(404 / 409 SESSION_NOT_ACCEPTING);422 交 pydantic。
@app.post("/api/sessions/{session_id}/viewport-detections")
def api_session_viewport_detections(session_id: str, frame: ViewportDetectionsFrame) -> dict[str, Any]:
    try:
        return manager.ingest_viewport_detections(session_id, frame)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="SESSION_NOT_FOUND") from exc
    except SessionNotAcceptingError as exc:
        raise HTTPException(status_code=409, detail="SESSION_NOT_ACCEPTING") from exc


# DT 视口 YOLO 检测引擎(web 勾选驱动的免会话通路)。
# 20261015 用户裁决:检测器部署 a4000 GPU(GPU1 推理,Unity 渲染占 GPU0)。
# TWIN_VIEWPORT_DETECTOR_REMOTE 非空(如 "a4000")= ssh 远程托管:venv ~/twin-detector-venv、
# 脚本目录 ~/twin-detector;检测结果经 remote_control 常驻 -R 反向隧道 18010 回本端;
# 空串 = 本地 mac CPU 模式(原行为)。远程启动同时停本地实例,防双推理双 POST。
VIEWPORT_DETECTOR_REMOTE = os.environ.get("TWIN_VIEWPORT_DETECTOR_REMOTE", "").strip()
VIEWPORT_DETECTOR_REMOTE_DIR = "~/twin-detector"
# P1 本船掩膜:检测器拉多边形缓存的端点(默认从转发 URL 同源推导;可环境变量覆盖)。
VIEWPORT_DETECTOR_POLYGON_URL = os.environ.get(
    "TWIN_VIEWPORT_POLYGON_URL",
    VIEWPORT_DETECTOR_FORWARD_URL.replace("/api/viewport-detections",
                                          "/api/viewport-ownship-polygon")).strip()
# 探活走远端 pidfile(serve --pidfile 自写):pgrep -f 会同时命中 ssh/bash 包装进程
_REMOTE_DETECT_PGID = "pid=$(cat ~/twin-detector/detector.pid 2>/dev/null) && kill -0 $pid 2>/dev/null && echo $pid"
_REMOTE_DETECT_CMD = (
    "mkdir -p ~/twin-detector/logs && cd ~/twin-detector && "
    "CUDA_VISIBLE_DEVICES=1 nohup ~/twin-detector-venv/bin/python sango_detector_service.py "
    "--endpoint tcp://127.0.0.1:5556 --out tcp://127.0.0.1:5557 "
    "--viewport-forward-url http://127.0.0.1:18010/api/viewport-detections "
    "--ownship-polygon-url http://127.0.0.1:18010/api/viewport-ownship-polygon "
    "--device cuda:0 --model yolov8s.pt --slice-size 640 --pidfile detector.pid "
    "--dump-frame /tmp/owmask-dump.jpg --ownship-diag-dir /tmp/owmask-diag "
    # </dev/null:后台进程不持有 ssh 会话 fd,否则 ssh 等管道关闭直至超时
    ">> logs/detector.log 2>&1 < /dev/null & echo $!"
)


def _ssh_remote(command: str, timeout: float = 10.0) -> str:
    try:
        result = subprocess.run(  # noqa: S603 — host/命令均来自本文件常量
            ["ssh", VIEWPORT_DETECTOR_REMOTE, command],
            capture_output=True, text=True, timeout=timeout, check=False,
        )
    except subprocess.TimeoutExpired:
        return ""  # 命令可能已生效(如 nohup spawn);由调用方 pgrep 复核
    return result.stdout.strip() if result.returncode == 0 else ""


def _local_detector_pid() -> int | None:
    try:
        pid = int(VIEWPORT_DETECTOR_PIDFILE.read_text().strip())
    except (OSError, ValueError):
        return None
    try:
        os.kill(pid, 0)  # 存活探测;ESRCH → ProcessLookupError
    except ProcessLookupError:
        return None
    except PermissionError:
        return pid  # 活着但非本用户(理论不可达,保守视为在跑)
    return pid


def _detector_pid() -> int | None:
    if VIEWPORT_DETECTOR_REMOTE:
        pid = _ssh_remote(_REMOTE_DETECT_PGID)
        return int(pid) if pid.isdigit() else None
    return _local_detector_pid()


def _detector_start() -> dict[str, Any]:
    if VIEWPORT_DETECTOR_REMOTE:
        if _detector_pid() is not None:
            return {"started": False, "reason": "already-running", "mode": "remote",
                    "host": VIEWPORT_DETECTOR_REMOTE}
        if _local_detector_pid() is not None:
            _detector_stop_local()  # 本地实例残留先停,防双推理双 POST
        _ssh_remote(_REMOTE_DETECT_CMD)
        pid = _detector_pid()
        if pid is None:
            return {"started": False, "reason": "remote-spawn-failed", "mode": "remote",
                    "host": VIEWPORT_DETECTOR_REMOTE}
        return {"started": True, "pid": pid, "mode": "remote", "host": VIEWPORT_DETECTOR_REMOTE}
    pid = _local_detector_pid()
    if pid is not None:
        return {"started": False, "pid": pid, "reason": "already-running"}
    VIEWPORT_DETECTOR_PIDFILE.parent.mkdir(parents=True, exist_ok=True)
    VIEWPORT_DETECTOR_LOG.parent.mkdir(parents=True, exist_ok=True)
    command = [
        str(VIEWPORT_DETECTOR_PY), str(VIEWPORT_DETECTOR_SCRIPT),
        "--endpoint", "tcp://127.0.0.1:15556",  # remote_control gst 路由隧道(a4000 sender tap)
        "--out", "tcp://127.0.0.1:15557",
        "--viewport-forward-url", VIEWPORT_DETECTOR_FORWARD_URL,
        "--ownship-polygon-url", VIEWPORT_DETECTOR_POLYGON_URL,
        # 小目标召回:远距小船在 720p→640 letterbox 下只剩十余像素;1280 推理输入
        # 换召回,CPU 代价 ~3x(检测器主循环排空取最新帧,慢推理不积压延迟)。
        "--imgsz", "1280",
    ]
    with VIEWPORT_DETECTOR_LOG.open("a") as log:
        process = subprocess.Popen(  # noqa: S603 — 常量命令,无用户输入
            command, cwd=str(BASE_DIR), stdin=subprocess.DEVNULL,
            stdout=log, stderr=subprocess.STDOUT, start_new_session=True,  # detached:后端重启不连坐
        )
    VIEWPORT_DETECTOR_PIDFILE.write_text(f"{process.pid}\n")
    return {"started": True, "pid": process.pid}


def _detector_stop_local() -> dict[str, Any]:
    pid = _local_detector_pid()
    if pid is None:
        VIEWPORT_DETECTOR_PIDFILE.unlink(missing_ok=True)
        return {"stopped": False, "reason": "not-running"}
    try:
        os.kill(pid, signal.SIGTERM)
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            try:
                os.waitpid(pid, os.WNOHANG)  # 收尸(自有子进程);他人子进程抛 ChildProcessError
            except (ChildProcessError, PermissionError):
                pass
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
            time.sleep(0.1)
        else:
            os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    VIEWPORT_DETECTOR_PIDFILE.unlink(missing_ok=True)
    return {"stopped": True, "pid": pid}


def _detector_stop() -> dict[str, Any]:
    if VIEWPORT_DETECTOR_REMOTE:
        pid = _detector_pid()
        # SIGTERM 走 pidfile;pkill 兜底收残留(字符类防自匹配)
        _ssh_remote("kill $(cat ~/twin-detector/detector.pid) 2>/dev/null; "
                    "pkill -f '[s]ango_detector_service.py'; rm -f ~/twin-detector/detector.pid")
        _detector_stop_local()  # 远程模式下本地也可能有残留,一并收口
        return {"stopped": pid is not None, "pid": pid, "mode": "remote",
                "host": VIEWPORT_DETECTOR_REMOTE}
    return _detector_stop_local()


class EngineEnableRequest(BaseModel):
    enabled: bool


@app.post("/api/viewport-detections")
def api_viewport_detections_sessionless(frame: ViewportDetectionsFrame) -> dict[str, Any]:
    """检测器免会话入口:路由进当前活动会话(勾选驱动的引擎默认落点)."""
    with manager.lock:
        description = manager.describe()
    if not description["active"]:
        raise HTTPException(status_code=404, detail="NO_ACTIVE_SESSION")
    try:
        return manager.ingest_viewport_detections(description["session_id"], frame)
    except SessionNotAcceptingError as exc:
        raise HTTPException(status_code=409, detail="SESSION_NOT_ACCEPTING") from exc


# 检测框观测记录仪(验收诊断用):web 渲染层逐帧采样 POST 到这里,追加 JSONL 供
# 离线逐帧分析(guard 抖动/track churn/闪动归因)。只追加文件,不进遥测不进会话。
VIEWPORT_BOX_LOG_PATH = os.environ.get("TWIN_VIEWPORT_BOX_LOG", "/tmp/viewport-boxes.jsonl")
_box_log_lock = threading.Lock()


@app.get("/api/viewport-detections/stream")
async def viewport_detections_sse(request: Request) -> StreamingResponse:
    """检测文档 SSE(到达即推):50ms 轮版本,变化即发;15s 注释心跳防中间层断连."""
    async def generate():
        last_version = -1
        idle = 0.0
        while True:
            if await request.is_disconnected():
                return
            version, doc = manager.viewport_detection_event(last_version)
            if doc is not None:
                last_version = version
                yield f"data: {json.dumps(doc)}\n\n"
                idle = 0.0
            else:
                idle += 0.05
                if idle >= 15.0:
                    idle = 0.0
                    yield ": ping\n\n"
            await asyncio.sleep(0.05)

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache"})


@app.post("/api/viewport-box-log")
def api_viewport_box_log(payload: dict[str, Any]) -> dict[str, Any]:
    lines = payload.get("lines") if isinstance(payload, dict) else None
    if not isinstance(lines, list):
        raise HTTPException(status_code=422, detail="LINES_REQUIRED")
    if len(lines) > 2000:
        raise HTTPException(status_code=413, detail="TOO_MANY_LINES")
    with _box_log_lock:
        with open(VIEWPORT_BOX_LOG_PATH, "a", encoding="utf-8") as fh:
            client = payload.get("client")
            if isinstance(client, dict):
                fh.write(json.dumps({"client": client}, ensure_ascii=False) + "\n")
            for line in lines:
                if isinstance(line, dict):
                    fh.write(json.dumps(line, ensure_ascii=False) + "\n")
    return {"appended": len(lines)}


# P1 本船掩膜中继(viewport-ownship-polygon@1):situation_frame 只走桥 DataChannel
# 到浏览器,后端不可见——Unity 桥服务在数据面同一 backend_base 上 ≤10Hz 批量
# POST 最近渲染帧的 (frame_id → 本船水线多边形);检测器 GET 拉环形缓存按解码
# frame_id 精确匹配,推理前掩掉本船。免会话单槽(末位写者胜,run_id 仅诊断):
# 检测链本身免会话(POST /api/viewport-detections 同哲学),会话换新零重接线。
_OWNSHIP_POLYGON_RING = 512  # ≥17s@30fps 渲染帧,覆盖 tap 采样+中继滞后
_ownship_polygon_lock = threading.Lock()
_ownship_polygon_frames: OrderedDict[int, dict[str, Any]] = OrderedDict()
_ownship_polygon_meta: dict[str, Any] = {}  # 空 = 从未写入(可变单例,免 global 重绑)
# 评审 Q1/Q2:P1 中继 camera_pose 环(每批 POST 采样,免会话)——视口跟踪腿在
# 采集时刻插值当帧相机位姿(web poseAtCapture 后端镜像),环空/越窗回退最新回显。
_camera_pose_ring = CameraPoseRing()


def _ingest_ownship_polygon(report: ViewportOwnshipPolygonReport) -> dict[str, Any]:
    """缓存一批 (frame_id → polygon) 记录;同 frame_id 覆写,超环长逐出最旧."""
    stored = 0
    with _ownship_polygon_lock:
        for entry in report.frames:
            _ownship_polygon_frames[entry.frame_id] = {
                "frame_id": entry.frame_id,
                "polygon": [corner.model_dump() for corner in entry.polygon],
            }
            stored += 1
        while len(_ownship_polygon_frames) > _OWNSHIP_POLYGON_RING:
            _ownship_polygon_frames.popitem(last=False)
        _ownship_polygon_meta.clear()
        _ownship_polygon_meta.update({
            "run_id": report.run_id,
            "sim_time": report.sim_time,
            "camera_pose": report.camera_pose.model_dump(),
            "updated_at": time.time(),
        })
    _camera_pose_ring.sample(time.time(), report.camera_pose.model_dump())
    return {"stored": stored, "cached_frames": len(_ownship_polygon_frames)}


@app.post("/api/viewport-ownship-polygon")
def api_viewport_ownship_polygon_post(report: ViewportOwnshipPolygonReport) -> dict[str, Any]:
    """Unity 桥服务中继写入(≤10Hz 批量;失败由客户端静默丢批,服务端零状态可重入)."""
    return _ingest_ownship_polygon(report)


@app.get("/api/viewport-ownship-polygon")
def api_viewport_ownship_polygon_get() -> dict[str, Any]:
    """检测器拉取:最新相机位姿+时间戳+最近帧环形缓存(frames 升序,末位最新).

    从未写入时 frames=[](检测端按"无 polygon 优雅跳过"消费,不 404)。
    """
    with _ownship_polygon_lock:
        meta = dict(_ownship_polygon_meta)
        frames = [dict(entry) for entry in _ownship_polygon_frames.values()]
    if not meta:
        return {"schema": VIEWPORT_OWNSHIP_POLYGON_SCHEMA_VERSION,
                "run_id": None, "sim_time": 0.0, "camera_pose": None,
                "updated_at": None, "frames": []}
    return {"schema": VIEWPORT_OWNSHIP_POLYGON_SCHEMA_VERSION, **meta, "frames": frames}


@app.get("/api/viewport-detection-engine")
def api_engine_status() -> dict[str, Any]:
    return {"running": _detector_pid() is not None, "pid": _detector_pid(),
            "forward_url": VIEWPORT_DETECTOR_FORWARD_URL,
            "mode": "remote:" + VIEWPORT_DETECTOR_REMOTE if VIEWPORT_DETECTOR_REMOTE else "local"}


@app.post("/api/viewport-detection-engine")
def api_engine_toggle(request: EngineEnableRequest) -> dict[str, Any]:
    return _detector_start() if request.enabled else _detector_stop()


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


@app.post("/api/sessions/{session_id}/twin/start")
def api_session_twin_start(session_id: str) -> dict[str, Any]:
    try:
        return manager.start_twin(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc
    except TwinRuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


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
        replacement = replace(current, algorithm_id=algorithm_id)
        if algorithm_id != current.algorithm_id:
            # The deprecated selector swaps the algorithm identity, so the
            # previous algorithm's spacing/product profile (filled by
            # CreateSessionRequest.to_spec) must not ride along: a foreign
            # non-empty algorithm_config masks the new algorithm's published
            # profile (registry build_algorithm treats a non-empty config as
            # authoritative and the potocnik factory key lives only there —
            # stale VO config surfaced as "Unsupported algorithm:
            # potocnik_colreg_fan_mpc"). Re-derive the product profile for the
            # new id exactly as the create path would.
            spacing_profile = _product_spacing_profile(algorithm_id)
            replacement.algorithm_config = copy.deepcopy(spacing_profile) if spacing_profile is not None else {}
        description = manager.create(replacement)
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
