"""Single-step simulation session shared by offline and Web execution."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import pandas as pd
import seacharts.enc as senc

import colav_simulator.common.miscellaneous_helper_methods as mhm
import colav_simulator.scenario_config as sc
from colav_simulator.core import stochasticity
from colav_simulator.core.ship import Ship
from colav_simulator.experiment.contracts import SessionState
from colav_simulator.simulator import Simulator


@dataclass
class SessionSnapshot:
    """One versioned Web/offline telemetry frame."""

    sequence: int
    sim_time: float
    state: SessionState
    step_time_ms: float
    payload: dict[str, Any]
    events: list[dict[str, Any]]


class SimulationSession:
    """Own one initialized episode and advance it exactly one step at a time."""

    def __init__(
        self,
        simulator: Simulator,
        ship_list: list[Ship],
        config: sc.ScenarioConfig,
        enc: senc.ENC,
        disturbance: stochasticity.Disturbance | None = None,
        colav_systems: list | None = None,
        trackers: list | None = None,
        seed: int = 0,
        terminate_on_collision_or_grounding: bool = True,
    ) -> None:
        self.simulator = simulator
        self.ship_list = ship_list
        self.config = config
        self.enc = enc
        self.disturbance = disturbance
        self.terminate_on_collision_or_grounding = terminate_on_collision_or_grounding
        self.state = SessionState.CREATED
        self.sequence = 0
        self.frames: list[dict[str, Any]] = []
        self.events: list[dict[str, Any]] = []
        self._last_planner_solve_ids: dict[str, int] = {}
        self.failure_reason: str | None = None
        self.ship_info = {f"Ship{i}": ship.get_ship_info() for i, ship in enumerate(ship_list)}
        self.simulator.initialize_scenario_episode(
            ship_list=ship_list,
            sconfig=config,
            enc=enc,
            disturbance=disturbance,
            colav_systems=colav_systems,
            trackers=trackers,
            seed=seed,
        )

    def start(self) -> None:
        if self.state in {SessionState.FINISHED, SessionState.FAILED}:
            raise RuntimeError(f"Cannot start a {self.state.value} session")
        self.state = SessionState.RUNNING
        self._event("session_started")

    def pause(self) -> None:
        if self.state == SessionState.RUNNING:
            self.state = SessionState.PAUSED
            self._event("session_paused")

    def advance(self) -> SessionSnapshot:
        if self.state != SessionState.RUNNING:
            raise RuntimeError(f"advance requires RUNNING state, got {self.state.value}")
        return self._advance()

    def step_once(self) -> SessionSnapshot:
        if self.state in {SessionState.FINISHED, SessionState.FAILED}:
            raise RuntimeError(f"Cannot step a {self.state.value} session")
        previous = self.state
        self.state = SessionState.RUNNING
        snapshot = self._advance()
        if self.state == SessionState.RUNNING:
            self.state = SessionState.PAUSED if previous != SessionState.RUNNING else SessionState.RUNNING
            snapshot.state = self.state
        return snapshot

    def run_to_completion(self) -> None:
        self.start()
        while self.state == SessionState.RUNNING:
            self.advance()

    def _advance(self) -> SessionSnapshot:
        start = time.perf_counter()
        try:
            sim_time = float(self.simulator.t)
            payload = self.simulator.step()
            self.frames.append(payload)
            self.sequence += 1
            step_events = self._planner_events(payload)
            collision_evidence = self.simulator.detect_ship_collisions(0)
            collision = bool(collision_evidence)
            grounding = self.simulator.determine_ship_grounding(0)
            goal_reached = self.simulator.determine_ship_goal_reached(0)
            time_limit = self.simulator.t >= self.simulator.t_end
            for evidence in collision_evidence:
                step_events.append(self._event("collision", **evidence))
            if grounding:
                step_events.append(self._event("grounding", ship_id=self.ship_list[0].id))
            if goal_reached:
                step_events.append(self._event("goal_reached", ship_id=self.ship_list[0].id))
            terminated = goal_reached or (self.terminate_on_collision_or_grounding and (collision or grounding))
            if time_limit:
                step_events.append(self._event("time_limit"))
            if terminated or time_limit:
                self.state = SessionState.FINISHED
                self._event("session_finished")
            return SessionSnapshot(
                sequence=self.sequence,
                sim_time=sim_time,
                state=self.state,
                step_time_ms=(time.perf_counter() - start) * 1000.0,
                payload=payload,
                events=step_events,
            )
        except Exception as exc:
            self.failure_reason = str(exc)
            self.state = SessionState.FAILED
            self._event("session_failed", reason=str(exc))
            raise

    def _event(self, event_type: str, *, event_sim_time: float | None = None, **details: Any) -> dict[str, Any]:
        event = {
            "sequence": self.sequence,
            "sim_time": float(self.simulator.t if event_sim_time is None else event_sim_time),
            "type": event_type,
            "details": details,
        }
        self.events.append(event)
        return event

    def _planner_events(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        events = []
        for ship_key, ship_data in payload.items():
            if not ship_key.startswith("Ship") or not ship_data:
                continue
            planner = ship_data.get("colav", {}).get("planner")
            if not planner or not planner.get("solver_executed"):
                continue
            solve_id = int(planner["solve_id"])
            if self._last_planner_solve_ids.get(ship_key) == solve_id:
                continue
            self._last_planner_solve_ids[ship_key] = solve_id
            events.append(
                self._event(
                    "planner_solved",
                    event_sim_time=float(planner["sim_time"]),
                    ship_id=int(ship_data["id"]),
                    planner=planner,
                )
            )
        return events

    def simulation_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame(self.frames)

    def vessel_data(self) -> list:
        return mhm.convert_simulation_data_to_vessel_data(
            self.simulation_dataframe(),
            self.ship_info,
            self.config.utm_zone,
        )
