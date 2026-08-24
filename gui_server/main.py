"""FastAPI control surface backed by the real COLAV simulation session."""
# ruff: noqa: D103

from __future__ import annotations

import matplotlib as mpl

mpl.use("Agg")

import asyncio
import json
import logging
import re
import threading
import time
from collections import deque
from contextlib import asynccontextmanager, suppress
from dataclasses import replace
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import yaml
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from shapely.geometry import Point

from colav_simulator.common import map_functions as mapf
from colav_simulator.core.colav.diagnostics import ColavExecutionError, PlanStatus
from colav_simulator.experiment.busy_water import (
    ACCEPTANCE_SCENARIO_ID,
    DEFAULT_SEED,
    STRESS_SCENARIO_ID,
    build_busy_water_document,
    normalize_encounter_mix,
    normalize_single_pass_document,
    preflight_document,
)
from colav_simulator.experiment.contracts import RunSpec, SessionState
from colav_simulator.experiment.persistence import jsonable
from colav_simulator.experiment.runner import ExperimentRunError, ExperimentRunner, PreparedRun, RunResult
from gui_server.historical_api import router as historical_api_router

log = logging.getLogger("gui_server")
logging.basicConfig(level=logging.INFO)

BASE_DIR = Path(__file__).resolve().parent.parent
GUI_DIR = BASE_DIR / "web_gui"
DRAFT_DIR = BASE_DIR / "runs" / "scenario_drafts"
BUSY_WATER_SCENARIOS = {ACCEPTANCE_SCENARIO_ID, STRESS_SCENARIO_ID}
THREAT_PROJECTION_SCHEMA = "colav.threat-management.projection@1"
TELEMETRY_PUBLISH_INTERVAL_S = 0.1
TELEMETRY_TRAIL_HISTORY_POINTS = 500
TELEMETRY_MAX_TRAIL_POINTS = 120


def _sample_display_trail(trail: list[list[float]]) -> list[list[float]]:
    if len(trail) <= TELEMETRY_MAX_TRAIL_POINTS:
        return list(trail)
    indices = np.linspace(0, len(trail) - 1, TELEMETRY_MAX_TRAIL_POINTS, dtype=int)
    return [trail[int(index)] for index in indices]


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


def _select_primary_encounter(_encounters: list[dict[str, Any]]) -> None:
    """Deprecated compatibility symbol; Primary belongs to canonical backend facts."""
    return None


def _canonical_threat_projection(colav_data: dict[str, Any], planner: dict[str, Any]) -> dict[str, Any]:
    """Project only a canonical backend threat document for REST/WS consumers."""
    candidate = (
        planner.get("threat_management")
        or planner.get("algorithm_details", {}).get("threat_management")
        or colav_data.get("threat_management")
    )
    if not isinstance(candidate, dict):
        return {
            "schema_version": THREAT_PROJECTION_SCHEMA,
            "status": "UNAVAILABLE",
            "snapshot": None,
            "vectors": [],
            "schedule": None,
            "conflicts": None,
            "conflict_graph": None,
            "unavailable_reason": "THREAT_SNAPSHOT_UNAVAILABLE",
        }
    snapshot = candidate.get("snapshot")
    if snapshot is None and "vectors" in candidate:
        snapshot = candidate
    vectors = snapshot.get("vectors", []) if isinstance(snapshot, dict) else []
    schedule = candidate.get("schedule")
    if schedule is None and isinstance(snapshot, dict):
        schedule = snapshot.get("schedule")
    conflicts = candidate.get("conflicts", candidate.get("conflict_graph"))
    if conflicts is None and isinstance(snapshot, dict):
        conflicts = snapshot.get("conflicts", snapshot.get("conflict_graph"))
    available = candidate.get("status") == "AVAILABLE" or isinstance(snapshot, dict)
    graph = jsonable(conflicts) if isinstance(conflicts, (dict, list)) else None
    return {
        "schema_version": THREAT_PROJECTION_SCHEMA,
        "status": "AVAILABLE" if available else "UNAVAILABLE",
        "snapshot": jsonable(snapshot) if isinstance(snapshot, dict) else None,
        "vectors": jsonable(vectors) if isinstance(vectors, list) else [],
        "schedule": jsonable(schedule) if isinstance(schedule, dict) else None,
        "conflicts": graph,
        "conflict_graph": graph,
        "unavailable_reason": None if available else candidate.get("unavailable_reason", "THREAT_SNAPSHOT_UNAVAILABLE"),
    }


class SessionCreateRequest(BaseModel):
    scenario_id: str = "head_on"
    validation_rule_id: str | None = None
    algorithm_id: str = "vo"
    tracker_id: str = "god"
    seed: int = Field(default=0, ge=0)
    episode_index: int = Field(default=0, ge=0)
    dt: float | None = Field(default=None, gt=0)
    t_end: float | None = Field(default=None, gt=0)
    strict_no_fallback: bool = True
    evaluator_profile_id: str = "ccta_2023_demo-v1"
    algorithm_config: dict[str, Any] = Field(default_factory=dict)
    tracker_config: dict[str, Any] = Field(default_factory=dict)
    domain_profile: Any | None = None
    scenario_override: dict[str, Any] | None = None

    def to_spec(self) -> RunSpec:
        if self.validation_rule_id is None:
            raise ColavExecutionError(
                PlanStatus.INVALID_INPUT,
                "Product session create requires an explicit validation_rule_id and exact capability tuple",
            )
        payload = self.model_dump()
        override = payload.get("scenario_override")
        if override is not None:
            if self.scenario_id not in BUSY_WATER_SCENARIOS:
                raise ValueError("scenario_override is supported only for busy-water scenarios")
            override = normalize_single_pass_document(override)
            override["name"] = self.scenario_id
            preflight_document(override, seed=self.seed)
            payload["scenario_override"] = override
        return RunSpec(**payload, output_root="runs")


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


def _draw_geometry(ax: plt.Axes, geometry: Any, color: str, alpha: float = 1.0) -> None:
    if geometry is None or geometry.is_empty:
        return
    polygons = geometry.geoms if hasattr(geometry, "geoms") else [geometry]
    for polygon in polygons:
        if not hasattr(polygon, "exterior"):
            continue
        xy = np.asarray(polygon.exterior.coords)
        ax.fill(xy[:, 0], xy[:, 1], color=color, alpha=alpha, linewidth=0)


def _local_polygon_coordinates(geometry: Any, origin_e: float, origin_n: float) -> list[list[list[list[float]]]]:
    """Serialize ENC polygons as local [north, east] rings for the Web canvas."""
    if geometry is None or geometry.is_empty:
        return []
    polygons = geometry.geoms if hasattr(geometry, "geoms") else [geometry]
    output = []
    for polygon in polygons:
        if not hasattr(polygon, "exterior"):
            continue
        rings = [polygon.exterior, *polygon.interiors]
        output.append([[[float(north - origin_n), float(east - origin_e)] for east, north in ring.coords] for ring in rings])
    return output


def _enc_depth_bin_at(enc: Any, *, east: float, north: float) -> float | None:
    """Return the deepest charted minimum-depth bin covering a UTM position."""
    point = Point(float(east), float(north))
    for depth in sorted(enc.seabed, key=float, reverse=True):
        geometry = enc.seabed[depth].geometry
        if geometry is not None and not geometry.is_empty and geometry.covers(point):
            return float(depth)
    return None


def render_enc(prepared: PreparedRun) -> Path:
    """Render the exact ENC object used by the active simulation."""
    enc = prepared.session.enc
    width, height = enc.size
    figure_width = 8.0
    figure_height = max(3.0, figure_width * height / max(width, 1.0))
    figure, axis = plt.subplots(figsize=(figure_width, figure_height), dpi=128)
    axis.set_facecolor("#9fc7cf")
    palette = {
        0: "#8ebbc5",
        1: "#99c5cb",
        2: "#a6cfd2",
        5: "#b6d9d7",
        10: "#c6e0da",
        20: "#d7e8df",
    }
    for depth in sorted(enc.seabed.keys(), reverse=True):
        _draw_geometry(axis, enc.seabed[depth].geometry, palette.get(depth, "#dceae3"))
    _draw_geometry(axis, enc.shore.geometry, "#9ca68a")
    _draw_geometry(axis, enc.land.geometry, "#69745f")
    e_min, n_min, e_max, n_max = enc.bbox
    axis.set_xlim(e_min, e_max)
    axis.set_ylim(n_min, n_max)
    axis.set_aspect("equal", adjustable="box")
    axis.axis("off")
    figure.subplots_adjust(0, 0, 1, 1)
    path = prepared.run_dir / "enc.png"
    figure.savefig(path, transparent=False, pad_inches=0)
    plt.close(figure)
    return path


class WebSessionManager:
    """Single active research session with background execution."""

    def __init__(self) -> None:
        self.runner = ExperimentRunner(BASE_DIR)
        self.prepared: PreparedRun | None = None
        self.result: RunResult | None = None
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
        self.active_planner_plan: dict[str, Any] = {}
        self.latest_planner_attempt: dict[str, Any] = {}
        self.enc_navigation_area: dict[str, Any] = {}
        self._telemetry_trails: dict[int, deque[list[float]]] = {}
        self._telemetry_published_at = 0.0
        self._latest_stream_document = ""
        self._latest_compact_stream_document = ""
        self._latest_compact_static_stream_document = ""
        self.lock = threading.RLock()

    @property
    def session_id(self) -> str | None:
        return self.prepared.manifest.run_id if self.prepared else None

    def create(self, spec: RunSpec) -> dict[str, Any]:
        with self.lock:
            if self.prepared and self.prepared.session.state == SessionState.RUNNING:
                raise RuntimeError("Pause the active session before replacing it")
            replacement = self.runner.prepare(spec)
            replacement.session.enable_pickle_frames()
            if self.prepared is not None:
                self.prepared.artifact_sink.close(timeout_s=2.0)
            self.prepared = replacement
            self.result = None
            self.replay_expected = None
            self.previous_prediction_horizon = []
            self.current_prediction_horizon = []
            self.last_solve_id = None
            self.latest_planner_solve = {}
            self.active_planner_plan = {}
            self.latest_planner_attempt = {}
            self._telemetry_trails = {}
            self._telemetry_published_at = 0.0
            self._latest_stream_document = ""
            self._latest_compact_stream_document = ""
            self._latest_compact_static_stream_document = ""
            self.speed_multiplier = 1.0
            self.speed_revision += 1
            self.effective_speed_multiplier = None
            self.scheduler_lag_ms = 0.0
            self.realtime_limited = False
            self.enc_navigation_area = self._enc_navigation_area()
            render_enc(self.prepared)
            self._publish_telemetry(None)
            return self.describe()

    def describe(self) -> dict[str, Any]:
        if not self.prepared:
            return {"active": False}
        return {
            "active": True,
            "session_id": self.session_id,
            "state": self.prepared.session.state.value,
            "spec": self.prepared.spec.to_dict(),
            "run_dir": str(self.prepared.run_dir),
            "sequence": self.prepared.session.sequence,
            "sim_time": float(self.prepared.session.simulator.t),
            "failure_reason": self.prepared.session.failure_reason,
            "playback": self._playback_status(),
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
        self._latest_compact_stream_document = ""
        self._latest_compact_static_stream_document = ""

    def _cache_stream_document(self) -> None:
        self._latest_stream_document = json.dumps(
            jsonable(self.latest),
            ensure_ascii=False,
            separators=(",", ":"),
        )

    def stream_document(self, *, compact: bool = False, include_static: bool = True) -> str:
        with self.lock:
            if not self.latest:
                self.latest = self._telemetry(None)
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
        for index in range(len(self.prepared.session.ship_list)):
            raw = frame.get(f"Ship{index}", {})
            if not raw:
                continue
            state = np.asarray(raw["state"], dtype=float)
            trail = self._telemetry_trails.setdefault(
                index,
                deque(maxlen=TELEMETRY_TRAIL_HISTORY_POINTS),
            )
            trail.append([float(state[0] - origin_n), float(state[1] - origin_e)])

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
            try:
                snapshot = prepared.session.step_once()
                self._record_telemetry_trails(snapshot.payload)
                if prepared.session.state == SessionState.FINISHED:
                    self._finalize(prepared)
                self._publish_telemetry(snapshot)
                return self.latest
            except Exception as exc:
                self._persist_failure(prepared, exc)
                raise

    def reset(self, session_id: str) -> dict[str, Any]:
        with self.lock:
            prepared = self._require(session_id)
            if prepared.session.state == SessionState.RUNNING:
                prepared.session.pause()
            return self.create(replace(prepared.spec))

    def tick(self) -> float | None:
        with self.lock:
            if not self.prepared or self.prepared.session.state != SessionState.RUNNING:
                return None
            try:
                snapshot = self.prepared.session.advance()
                self._record_telemetry_trails(snapshot.payload)
                if self.prepared.session.state == SessionState.FINISHED:
                    self._finalize(self.prepared)
                if self._telemetry_refresh_due(snapshot, now=time.monotonic()):
                    self._publish_telemetry(snapshot)
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
            description = self.create(replace(prepared.spec, replay_of_run_id=prepared.manifest.run_id))
            self.replay_expected = expected
            return description

    def _finalize(self, prepared: PreparedRun) -> None:
        self.result = self.runner.finalize(prepared)
        if self.replay_expected:
            episode_hash, trajectory_hash = self.replay_expected
            prepared.manifest.replay_verified = (
                prepared.manifest.episode_hash == episode_hash and prepared.manifest.trajectory_hash == trajectory_hash
            )
            prepared.writer.write_manifest(prepared.manifest)
            if not prepared.manifest.replay_verified:
                raise RuntimeError("Web replay trajectory mismatch")

    def _persist_failure(self, prepared: PreparedRun, exc: Exception) -> None:
        prepared.session.state = SessionState.FAILED
        prepared.session.failure_reason = str(exc)
        prepared.artifact_sink.close(timeout_s=2.0)
        self.runner.persist_failure(
            prepared.manifest,
            prepared.writer,
            exc,
            prepared.session.frames,
            prepared.session.events,
        )

    def result_document(self, session_id: str) -> dict[str, Any]:
        self._require(session_id)
        if not self.result:
            raise RuntimeError("Result is available only after the session finishes")
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
        if not self.prepared:
            return {"ready": False}
        enc = self.prepared.session.enc
        return {
            "ready": True,
            "origin_e": float(enc.origin[0]),
            "origin_n": float(enc.origin[1]),
            "width": float(enc.size[0]),
            "height": float(enc.size[1]),
            "utm_zone": int(enc.utm_zone),
            "tile_url": "/api/enc_tile",
            "navigation_area_url": f"/api/sessions/{self.session_id}/navigation-area",
            "run_id": self.session_id,
        }

    def navigation_area(self, session_id: str) -> dict[str, Any]:
        self._require(session_id)
        return self.enc_navigation_area

    def planner_decision_space(self, session_id: str, solve_id: int) -> dict[str, Any] | None:
        with self.lock:
            prepared = self._require(session_id)
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
        if not self.prepared or not self.prepared.session.ship_list:
            return {}
        session = self.prepared.session
        enc = session.enc
        origin_e, origin_n = enc.origin
        draft = float(session.ship_list[0].draft)
        minimum_depth = mapf.find_minimum_depth(draft, enc)
        safe_water = mapf.extract_safe_sea_area(
            minimum_depth,
            mapf.bbox_to_polygon(enc.bbox),
            enc,
            show_plots=False,
        )
        return {
            "schema_version": "1.0",
            "coordinate_frame": "local_north_east_m",
            "utm_zone": int(enc.utm_zone),
            "vessel_draft_m": draft,
            "minimum_depth_m": float(minimum_depth),
            "safe_water": {
                "type": "MultiPolygon",
                "polygons": _local_polygon_coordinates(safe_water, float(origin_e), float(origin_n)),
            },
        }

    def _require(self, session_id: str) -> PreparedRun:
        if not self.prepared or session_id != self.session_id:
            raise KeyError(session_id)
        return self.prepared

    def _telemetry(self, snapshot: Any) -> dict[str, Any]:  # noqa: C901, PLR0912, PLR0915
        if not self.prepared:
            return {
                "schema_version": "1.0",
                "run_id": None,
                "seq": 0,
                "sim_time": 0.0,
                "state": SessionState.CREATED.value,
                "events": [],
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
                    "r": float(state[5]),
                    "sog": float(csog[2]),
                    "cog": float(csog[3]),
                    "trajectory": trail,
                    "active": bool(raw.get("active", True)),
                    "measurements": jsonable(raw.get("sensor_measurements")),
                    "tracks": self._local_tracks(raw, origin_n, origin_e),
                    "colav": jsonable(raw.get("colav", {})),
                }
            )
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
        colav_data = own_raw.get("colav", {}) if own_raw else {}
        planner = colav_data.get("planner", {})
        threat_management = _canonical_threat_projection(colav_data, planner)
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
                self.latest_planner_solve = jsonable(planner)
                self.last_solve_id = solve_id
            self.active_planner_plan = jsonable(planner) if executable else {}
            self.latest_planner_attempt = jsonable(planner)
            rejected_prediction_horizon = prediction_horizon if prediction_render.get("style") == "REJECTED" else []
        elif planner.get("solver_executed") and solve_id != self.last_solve_id:
            self.previous_prediction_horizon = self.current_prediction_horizon
            self.current_prediction_horizon = prediction_horizon
            self.last_solve_id = solve_id
            self.latest_planner_solve = jsonable(planner)
            self.active_planner_plan = jsonable(planner)
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
            self.latest_planner_attempt = jsonable(planner)
        references = np.asarray(own_raw.get("references", np.zeros(9)), dtype=float)
        execution = {
            "solve_id": solve_id,
            "applied_course_ref_rad": float(references[2]) if references.size > 2 else None,
            "applied_speed_ref_mps": float(references[3]) if references.size > 3 else None,
            "selected_command": planner.get("selected_command", {}),
        }
        sim_time = float(snapshot.sim_time) if snapshot is not None else float(session.simulator.t)
        events = snapshot.events if snapshot is not None else []
        step_ms = float(snapshot.step_time_ms) if snapshot is not None else 0.0
        return {
            "schema_version": "1.0",
            "run_id": self.session_id,
            "scenario_id": self.prepared.spec.scenario_id,
            "seq": session.sequence,
            "sim_time": sim_time,
            "state": session.state.value,
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
            "planner": jsonable(planner),
            "latest_planner_solve": self.latest_planner_solve,
            "active_planner_plan": self.active_planner_plan,
            "latest_planner_attempt": self.latest_planner_attempt,
            "execution": jsonable(execution),
            "events": jsonable(events),
            "step": session.sequence,
            "scenario_time": sim_time,
            "running": session.state == SessionState.RUNNING,
            "os": own,
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
            "step_time_ms": step_ms,
            "playback": self._playback_status(),
            "failure_reason": session.failure_reason,
            "reproduction_status": self.result.manifest.reproduction_status if self.result else "running",
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
        return jsonable(
            {
                "labels": raw.get("do_labels", []),
                "generations": raw.get("do_generations", []),
                "states": states,
                "covariances": raw.get("do_covariances", []),
                "nis": raw.get("do_NISes", []),
            }
        )


def _bounded_playback_deadline(
    previous_deadline: float,
    now: float,
    interval: float,
    *,
    max_catch_up_steps: int = 8,
) -> tuple[float, float]:
    deadline = previous_deadline + interval
    deadline = max(deadline, now - interval * max_catch_up_steps)
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


@app.get("/api/algorithms")
def api_algorithms() -> list[dict[str, Any]]:
    """Expose the active product algorithms, not the retained integration registry."""
    policy = manager.runner.capabilities.policy
    statuses = manager.runner.registry.statuses()
    return [
        {
            **statuses[identifier].to_dict(),
            "active": True,
            "available": bool(statuses[identifier].available),
            "selectable": bool(statuses[identifier].available),
            "constraints": policy.constraints(identifier),
        }
        for identifier in policy.algorithm_ids
        if identifier in statuses
    ]


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
    target_count: int = 15,
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
        return manager.create(request.to_spec())
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
def api_enc_tile() -> FileResponse:
    if not manager.prepared:
        raise HTTPException(status_code=503, detail="No active session")
    return FileResponse(manager.prepared.run_dir / "enc.png", media_type="image/png")


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


async def _stream(websocket: WebSocket, session_id: str | None = None, *, compact: bool = False) -> None:
    await websocket.accept()
    include_static = True
    try:
        while True:
            if session_id and manager.session_id != session_id:
                await websocket.send_json({"error": "session_not_found"})
                return
            await websocket.send_text(manager.stream_document(compact=compact, include_static=include_static))
            include_static = False
            await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        return


@app.websocket("/ws/sessions/{session_id}")
async def websocket_session(websocket: WebSocket, session_id: str) -> None:
    await _stream(websocket, session_id, compact=websocket.query_params.get("transport") == "compact-v1")


@app.websocket("/ws")
async def websocket_legacy(websocket: WebSocket) -> None:
    await _stream(websocket)
