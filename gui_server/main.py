"""FastAPI control surface backed by the real COLAV simulation session."""
# ruff: noqa: D103

from __future__ import annotations

import matplotlib as mpl

mpl.use("Agg")

import asyncio
import logging
import threading
from contextlib import asynccontextmanager, suppress
from dataclasses import replace
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from colav_simulator.common import map_functions as mapf
from colav_simulator.core.colav.diagnostics import ColavExecutionError, PlanStatus
from colav_simulator.evaluation import EncounterMonitor
from colav_simulator.experiment.contracts import RunSpec, SessionState
from colav_simulator.experiment.persistence import jsonable
from colav_simulator.experiment.runner import ExperimentRunError, ExperimentRunner, PreparedRun, RunResult

log = logging.getLogger("gui_server")
logging.basicConfig(level=logging.INFO)

BASE_DIR = Path(__file__).resolve().parent.parent
GUI_DIR = BASE_DIR / "web_gui"


class SessionCreateRequest(BaseModel):
    scenario_id: str = "head_on"
    validation_rule_id: str | None = None
    algorithm_id: str = "nominal"
    tracker_id: str = "god"
    seed: int = Field(default=0, ge=0)
    episode_index: int = Field(default=0, ge=0)
    dt: float | None = Field(default=None, gt=0)
    t_end: float | None = Field(default=None, gt=0)
    strict_no_fallback: bool = True
    evaluator_profile_id: str = "ccta_2023_demo-v1"
    algorithm_config: dict[str, Any] = Field(default_factory=dict)
    tracker_config: dict[str, Any] = Field(default_factory=dict)

    def to_spec(self) -> RunSpec:
        return RunSpec(**self.model_dump(), output_root="runs")


LEGACY_SCENARIOS = {
    "Crossing": "crossing_give_way",
    "Head-on": "paper_ccta2023_head_on",
    "Overtaking": "overtaking",
    "Multi-Obstacle": "paper_ccta2023_multiship",
}
LEGACY_ALGORITHMS = {
    "Nominal": "nominal",
    "CustomMPC": "custom_mpc",
    "PSBMPC": "psbmpc",
    "RLMPC": "rlmpc",
    "RRT-Star": "rrt",
}


def _execution_error_detail(exc: Exception) -> dict[str, str]:
    if isinstance(exc, ColavExecutionError):
        status = exc.status
    elif isinstance(exc, ExperimentRunError) and exc.manifest.failure_status:
        status = PlanStatus(exc.manifest.failure_status)
    else:
        status = PlanStatus.INVALID_INPUT
    return {"status": status.value, "reason": str(exc)}


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
        output.append(
            [
                [[float(north - origin_n), float(east - origin_e)] for east, north in ring.coords]
                for ring in rings
            ]
        )
    return output


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
        self.encounter_monitor = EncounterMonitor()
        self.previous_prediction_horizon: list[list[float]] = []
        self.current_prediction_horizon: list[list[float]] = []
        self.last_solve_id: int | None = None
        self.latest_planner_solve: dict[str, Any] = {}
        self.enc_navigation_area: dict[str, Any] = {}
        self.lock = threading.RLock()

    @property
    def session_id(self) -> str | None:
        return self.prepared.manifest.run_id if self.prepared else None

    def create(self, spec: RunSpec) -> dict[str, Any]:
        with self.lock:
            if self.prepared and self.prepared.session.state == SessionState.RUNNING:
                raise RuntimeError("Pause the active session before replacing it")
            self.prepared = self.runner.prepare(spec)
            self.result = None
            self.replay_expected = None
            self.encounter_monitor = EncounterMonitor(
                spec.validation_rule_id,
                spec.evaluator_profile_id,
            )
            self.previous_prediction_horizon = []
            self.current_prediction_horizon = []
            self.last_solve_id = None
            self.latest_planner_solve = {}
            self.speed_multiplier = 1.0
            self.speed_revision += 1
            self.effective_speed_multiplier = None
            self.scheduler_lag_ms = 0.0
            self.realtime_limited = False
            self.enc_navigation_area = self._enc_navigation_area()
            render_enc(self.prepared)
            self.latest = self._telemetry(None)
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
            self._publish_playback_status()

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

    def start(self, session_id: str) -> dict[str, Any]:
        with self.lock:
            prepared = self._require(session_id)
            prepared.session.start()
            self.latest = self._telemetry(None)
            return self.describe()

    def pause(self, session_id: str) -> dict[str, Any]:
        with self.lock:
            prepared = self._require(session_id)
            prepared.session.pause()
            self.latest = self._telemetry(None)
            return self.describe()

    def step(self, session_id: str) -> dict[str, Any]:
        with self.lock:
            prepared = self._require(session_id)
            try:
                snapshot = prepared.session.step_once()
                self.latest = self._telemetry(snapshot)
                if prepared.session.state == SessionState.FINISHED:
                    self._finalize(prepared)
                    self.latest = self._telemetry(snapshot)
                return self.latest
            except Exception as exc:
                self._persist_failure(prepared, exc)
                raise

    def reset(self, session_id: str) -> dict[str, Any]:
        with self.lock:
            prepared = self._require(session_id)
            return self.create(replace(prepared.spec))

    def tick(self) -> float | None:
        with self.lock:
            if not self.prepared or self.prepared.session.state != SessionState.RUNNING:
                return None
            try:
                snapshot = self.prepared.session.advance()
                self.latest = self._telemetry(snapshot)
                if self.prepared.session.state == SessionState.FINISHED:
                    self._finalize(self.prepared)
                    self.latest = self._telemetry(snapshot)
                return float(self.prepared.session.simulator.t)
            except Exception as exc:
                self._persist_failure(self.prepared, exc)
                self.latest = self._telemetry(None)
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
                raise RuntimeError(
                    f"Decision-space solve {solve_id} is stale; latest solve is {current_solve_id}"
                )
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

    def _telemetry(self, snapshot: Any) -> dict[str, Any]:  # noqa: PLR0912, PLR0915
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
        frame = snapshot.payload if snapshot is not None else (session.frames[-1] if session.frames else {})
        origin_e, origin_n = session.enc.origin
        ships = []
        for index in range(len(session.ship_list)):
            raw = frame.get(f"Ship{index}", {})
            if not raw:
                continue
            state = np.asarray(raw["state"], dtype=float)
            csog = np.asarray(raw["csog_state"], dtype=float)
            trail = []
            for historic in session.frames[-500:]:
                historic_ship = historic.get(f"Ship{index}", {})
                if historic_ship:
                    historic_state = np.asarray(historic_ship["state"], dtype=float)
                    trail.append([float(historic_state[0] - origin_n), float(historic_state[1] - origin_e)])
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
        obstacles = ships[1:]
        encounters = [item.to_dict() for item in self.encounter_monitor.update(ships)]
        primary_encounter = next(
            (item for item in encounters if item["validation_rule_id"] == self.prepared.spec.validation_rule_id),
            encounters[0] if encounters else None,
        )
        dcpa = float(primary_encounter["dcpa_m"]) if primary_encounter else float("inf")
        tcpa = float(primary_encounter["tcpa_s"]) if primary_encounter else float("inf")
        encounter = primary_encounter["encounter"] if primary_encounter else "clear"
        own_raw = frame.get("Ship0", {})
        waypoints = np.asarray(own_raw.get("waypoints", np.zeros((2, 0))), dtype=float)
        if waypoints.ndim == 2 and waypoints.size:
            local_waypoints = np.vstack((waypoints[0] - origin_n, waypoints[1] - origin_e)).tolist()
        else:
            local_waypoints = [[], []]
        colav_data = own_raw.get("colav", {}) if own_raw else {}
        planner = colav_data.get("planner", {})
        solve_id = int(planner.get("solve_id", 0))
        predicted = np.asarray(planner.get("predicted_trajectory", np.zeros((0, 0))), dtype=float)
        has_prediction = (
            predicted.ndim == 2
            and predicted.shape[0] >= 2
            and predicted.shape[1] > 0
            and (solve_id > 0 or planner.get("algorithm_id") in {"nominal", "vo"})
        )
        if has_prediction:
            prediction_horizon = np.column_stack((predicted[0] - origin_n, predicted[1] - origin_e)).tolist()
        else:
            prediction_horizon = []
        target_prediction_horizons = []
        for target in planner.get("target_predictions", []):
            target_north = np.asarray(target.get("x", []), dtype=float)
            target_east = np.asarray(target.get("y", []), dtype=float)
            if target_north.ndim != 1 or target_east.ndim != 1 or target_north.size != target_east.size:
                continue
            target_prediction_horizons.append(np.column_stack((target_north - origin_n, target_east - origin_e)).tolist())
        if planner.get("solver_executed") and solve_id != self.last_solve_id:
            self.previous_prediction_horizon = self.current_prediction_horizon
            self.current_prediction_horizon = prediction_horizon
            self.last_solve_id = solve_id
            self.latest_planner_solve = jsonable(planner)
        elif prediction_horizon and not self.current_prediction_horizon:
            self.current_prediction_horizon = prediction_horizon
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
                "target_prediction_horizons": target_prediction_horizons,
            },
            "enc_navigation_area": self.enc_navigation_area,
            "encounters": encounters,
            "planner": jsonable(planner),
            "latest_planner_solve": self.latest_planner_solve,
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
            "dcpa": dcpa,
            "tcpa": tcpa,
            "colregs": encounter,
            "safety_margin": 150.0,
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
        realtime_limited = (
            effective_multiplier is not None
            and effective_multiplier < clock["multiplier"] * 0.9
        )
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
    return [status.to_dict() for status in manager.runner.registry.statuses().values()]


@app.post("/api/sessions")
def api_create_session(request: SessionCreateRequest) -> dict[str, Any]:
    try:
        return manager.create(request.to_spec())
    except Exception as exc:
        raise HTTPException(status_code=422, detail=_execution_error_detail(exc)) from exc


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
    statuses = manager.runner.registry.statuses()
    legacy = {
        "Nominal": statuses["nominal"].available,
        "CustomMPC": False,
        "PSBMPC": statuses["psbmpc"].available,
        "RLMPC": statuses["rlmpc"].available,
        "RRT-Star": statuses["rrt"].available,
    }
    return JSONResponse(legacy)


def _ensure_legacy_session(scenario: str | None = None, algorithm: str | None = None) -> str:
    if manager.prepared:
        return manager.session_id
    spec = RunSpec(
        scenario_id=LEGACY_SCENARIOS.get(scenario or "Head-on", scenario or "paper_ccta2023_head_on"),
        algorithm_id=LEGACY_ALGORITHMS.get(algorithm or "Nominal", algorithm or "nominal"),
    )
    manager.create(spec)
    return manager.session_id


@app.post("/api/start")
def api_start() -> dict[str, Any]:
    session_id = _ensure_legacy_session()
    return manager.start(session_id)


@app.post("/api/pause")
def api_pause() -> dict[str, Any]:
    session_id = _ensure_legacy_session()
    return manager.pause(session_id)


@app.post("/api/reset")
def api_reset(scenario: str = "Head-on") -> dict[str, Any]:
    algorithm = manager.prepared.spec.algorithm_id if manager.prepared else "nominal"
    scenario_id = LEGACY_SCENARIOS.get(scenario, scenario)
    return manager.create(RunSpec(scenario_id=scenario_id, algorithm_id=algorithm))


@app.post("/api/select_algorithm")
def api_select_algorithm(algorithm: str = "CustomMPC") -> dict[str, Any]:
    scenario = manager.prepared.spec.scenario_id if manager.prepared else "paper_ccta2023_head_on"
    algorithm_id = LEGACY_ALGORITHMS.get(algorithm, algorithm.lower())
    try:
        description = manager.create(RunSpec(scenario_id=scenario, algorithm_id=algorithm_id))
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
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


async def _stream(websocket: WebSocket, session_id: str | None = None) -> None:
    await websocket.accept()
    try:
        while True:
            if session_id and manager.session_id != session_id:
                await websocket.send_json({"error": "session_not_found"})
                return
            await websocket.send_json(jsonable(manager.latest or manager._telemetry(None)))
            await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        return


@app.websocket("/ws/sessions/{session_id}")
async def websocket_session(websocket: WebSocket, session_id: str) -> None:
    await _stream(websocket, session_id)


@app.websocket("/ws")
async def websocket_legacy(websocket: WebSocket) -> None:
    await _stream(websocket)
