"""Single-step simulation session shared by offline and Web execution."""

from __future__ import annotations

import pickle
import time
from dataclasses import dataclass
from typing import Any

import pandas as pd
import seacharts.enc as senc

import colav_simulator.common.miscellaneous_helper_methods as mhm
import colav_simulator.scenario_config as sc
from colav_simulator.core import stochasticity
from colav_simulator.core.colav.threat_management import ThreatManagementCoordinator
from colav_simulator.core.ship import Ship
from colav_simulator.experiment.contracts import SessionState
from colav_simulator.experiment.threat_baseline import baseline_due, build_baseline_cycle_inputs
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
        threat_management_coordinator: ThreatManagementCoordinator | None = None,
    ) -> None:
        self.simulator = simulator
        self.ship_list = ship_list
        self.config = config
        self.enc = enc
        self.disturbance = disturbance
        self.terminate_on_collision_or_grounding = terminate_on_collision_or_grounding
        self.threat_management_coordinator = (
            threat_management_coordinator
            if threat_management_coordinator is not None
            else ThreatManagementCoordinator()
        )
        self.state = SessionState.CREATED
        self.sequence = 0
        self._baseline_threat_sequence = 0
        self.baseline_threat_failure_reason: str | None = None
        self._frames_live: list[dict[str, Any]] = []
        self._frame_blobs: list[bytes] | None = None
        self._frames_decoded: list[dict[str, Any]] | None = None
        self.last_frame: dict[str, Any] | None = None
        self.events: list[dict[str, Any]] = []
        self.step_times_ms: list[float] = []
        self._last_planner_solve_ids: dict[str, int] = {}
        self._seen_active_track_keys: set[tuple[int, int]] = set()
        self.historical_recovery_status: dict[str, Any] = {"status": "NOT_STARTED", "hold_s": 0.0}
        self._historical_recovery_event_emitted = False
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

    def enable_pickle_frames(self) -> None:
        """Retain further frames as pickled bytes.

        Long GUI sessions otherwise accumulate tens of thousands of container
        payloads that the cyclic garbage collector must traverse, and the
        resulting gen-2 pauses land inside solver timing as multi-second
        stalls. Bytes are opaque to the collector, so retention becomes
        GC-inert; ``frames`` still decodes the full evidence list on demand.
        """
        if self._frame_blobs is not None:
            return
        self._frame_blobs = [pickle.dumps(frame) for frame in self._frames_live]
        self._frames_live = []
        self._frames_decoded = None

    @property
    def frames(self) -> list[dict[str, Any]]:
        if self._frame_blobs is None:
            return self._frames_live
        if self._frames_decoded is None:
            self._frames_decoded = [pickle.loads(blob) for blob in self._frame_blobs]
        return self._frames_decoded

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
            self.last_frame = payload
            if self._frame_blobs is None:
                self._frames_live.append(payload)
            else:
                self._frame_blobs.append(pickle.dumps(payload))
                self._frames_decoded = None
            self.sequence += 1
            step_events = self._planner_events(payload)
            step_events.extend(self._advance_baseline_threat_cycle())
            step_events.extend(self._advance_historical_recovery())
            stress_only = self.config.name.startswith("romsdal_busy_water_80_stress")
            collision_evidence = [] if stress_only else self.simulator.detect_ship_collisions(0)
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
            historical_full_window = self.config.name == "historical_lifecycle_counterfactual"
            terminated = (
                (goal_reached and not historical_full_window)
                or (self.terminate_on_collision_or_grounding and (collision or grounding))
            )
            if time_limit:
                if (
                    historical_full_window
                    and getattr(self.ship_list[0], "counterfactual_phase", None) == "HISTORICAL_REFERENCE"
                ):
                    self.historical_recovery_status = {
                        "status": "NOT_EXECUTED",
                        "reason": "HANDOFF_NOT_TRIGGERED",
                    }
                    step_events.append(
                        self._event(
                            "historical_handoff_not_triggered",
                            reason="HANDOFF_NOT_TRIGGERED",
                            counterfactual_avoidance="NOT_EXECUTED",
                        )
                    )
                step_events.append(self._event("time_limit"))
            if terminated or time_limit:
                self.state = SessionState.FINISHED
                self._event("session_finished")
            step_time_ms = (time.perf_counter() - start) * 1000.0
            self.step_times_ms.append(step_time_ms)
            return SessionSnapshot(
                sequence=self.sequence,
                sim_time=sim_time,
                state=self.state,
                step_time_ms=step_time_ms,
                payload=payload,
                events=step_events,
            )
        except Exception as exc:
            self.failure_reason = str(exc)
            self.state = SessionState.FAILED
            self._event("session_failed", reason=str(exc))
            raise

    def _advance_baseline_threat_cycle(self) -> list[dict[str, Any]]:
        """Advance the coordinator once per tick when no adapter cycle ran.

        Failures degrade to a recorded reason — a monitor-grade cycle must not
        fail a run.
        """
        coordinator = self.threat_management_coordinator
        if coordinator is None:
            return []
        sim_time = float(self.simulator.t)
        if not baseline_due(coordinator, sim_time, float(self.simulator.dt)):
            return []
        try:
            self._baseline_threat_sequence += 1
            inputs = build_baseline_cycle_inputs(
                self.ship_list,
                sim_time_s=sim_time,
                sequence=self._baseline_threat_sequence,
            )
            snapshot = coordinator.cycle(
                inputs.cycle,
                predictions=inputs.predictions,
                baseline_prediction=inputs.baseline_prediction,
            )
            active_targets = [
                {
                    "target_id": int(target.key.target_id),
                    "generation": int(target.key.generation),
                }
                for target in snapshot.lifecycle_snapshot.targets
                if str(getattr(target.risk, "value", target.risk)) == "ACTIVE"
            ]
            events = []
            for target in active_targets:
                key = (target["target_id"], target["generation"])
                if key in self._seen_active_track_keys:
                    continue
                self._seen_active_track_keys.add(key)
                events.append(
                    self._event(
                        "threat_lifecycle_active",
                        event_sim_time=sim_time,
                        **target,
                    )
                )
            request_handoff = getattr(self.ship_list[0], "request_lifecycle_handoff", None)
            if request_handoff is None or not request_handoff(sim_time, snapshot.lifecycle_snapshot):
                return events
            events.append(
                self._event(
                    "algorithm_handoff",
                    event_sim_time=sim_time,
                    trigger="LIFECYCLE_ACTIVE",
                    active_targets=active_targets,
                )
            )
            return events
        except Exception as exc:  # noqa: BLE001 - monitor-grade degradation
            self.baseline_threat_failure_reason = str(exc)
            return []

    def _event(self, event_type: str, *, event_sim_time: float | None = None, **details: Any) -> dict[str, Any]:
        event = {
            "sequence": self.sequence,
            "sim_time": float(self.simulator.t if event_sim_time is None else event_sim_time),
            "type": event_type,
            "details": details,
        }
        self.events.append(event)
        return event

    def _advance_historical_recovery(self) -> list[dict[str, Any]]:
        snapshot = None if self.threat_management_coordinator is None else self.threat_management_coordinator.last_snapshot
        update_recovery = getattr(self.ship_list[0], "update_recovery_status", None)
        if snapshot is None or snapshot.lifecycle_snapshot is None or update_recovery is None:
            return []
        events = []
        for target in snapshot.lifecycle_snapshot.targets:
            if str(getattr(target.risk, "value", target.risk)) != "ACTIVE":
                continue
            key = (int(target.key.target_id), int(target.key.generation))
            if key in self._seen_active_track_keys:
                continue
            self._seen_active_track_keys.add(key)
            events.append(
                self._event(
                    "threat_lifecycle_active",
                    target_id=key[0],
                    generation=key[1],
                )
            )
        self.historical_recovery_status = update_recovery(
            snapshot.lifecycle_snapshot,
            set(self._seen_active_track_keys),
            float(self.simulator.dt),
        )
        if (
            self.historical_recovery_status.get("status") == "RECOVERY_COMPLETE"
            and not self._historical_recovery_event_emitted
        ):
            self._historical_recovery_event_emitted = True
            events.append(self._event("historical_recovery_complete", **self.historical_recovery_status))
        return events

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
