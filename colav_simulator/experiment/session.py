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

OPERATIONAL_EVENT_CAP = 1000
_OPERATIONAL_HIDDEN_EVENT_TYPES = frozenset({"planner_solved", "threat_lifecycle_active"})


def _enum_text(value: Any) -> str | None:
    if value is None:
        return None
    return str(getattr(value, "value", value))


def _track_identity(key: Any) -> tuple[int, int] | None:
    if key is None:
        return None
    target_id = getattr(key, "target_id", None)
    generation = getattr(key, "generation", None)
    if target_id is None or generation is None:
        return None
    return int(target_id), int(generation)


def _track_details(key: Any) -> dict[str, int]:
    identity = _track_identity(key)
    return {} if identity is None else {"target_id": identity[0], "generation": identity[1]}


def _vector_event_details(vector: Any) -> dict[str, Any]:
    lifecycle = getattr(vector, "lifecycle", None)
    return {
        **_track_details(getattr(vector, "key", None)),
        "display_class": _enum_text(getattr(vector, "display_class", None)),
        "priority_class": _enum_text(getattr(vector, "priority_class", None)),
        "observation_health": _enum_text(getattr(vector, "observation_health", None)),
        "encounter": _enum_text(getattr(lifecycle, "encounter", None)),
        "role": _enum_text(getattr(lifecycle, "role", None)),
        "risk": _enum_text(getattr(lifecycle, "risk", None)),
        "commitment": _enum_text(getattr(lifecycle, "commitment", None)),
        "dcpa_m": getattr(vector, "dcpa_m", None),
        "tcpa_s": getattr(vector, "tcpa_forward_s", None),
        "range_m": getattr(vector, "range_m", None),
        "avoidance_action_active": getattr(vector, "avoidance_action_active", None),
    }


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
        self._planner_success_by_ship: dict[str, bool] = {}
        self._seen_active_track_keys: set[tuple[int, int]] = set()
        self._seen_threat_event_keys: set[tuple[Any, ...]] = set()
        self._avoidance_action_by_track: dict[tuple[int, int], bool] = {}
        self._reported_emergency_tracks: set[tuple[int, int]] = set()
        self._display_class_by_track: dict[tuple[int, int], str | None] = {}
        self._encounter_role_by_track: dict[tuple[int, int], tuple[str | None, str | None]] = {}
        self._observation_health_by_track: dict[tuple[int, int], str | None] = {}
        self._last_primary_track_key: tuple[int, int] | None = None
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

    @property
    def operational_events(self) -> list[dict[str, Any]]:
        """Bounded operator-facing history; raw solver cadence stays in ``events``."""
        visible = [event for event in self.events if event["type"] not in _OPERATIONAL_HIDDEN_EVENT_TYPES]
        return visible[-OPERATIONAL_EVENT_CAP:]

    def start(self) -> None:
        if self.state in {SessionState.FINISHED, SessionState.FAILED}:
            raise RuntimeError(f"Cannot start a {self.state.value} session")
        previous = self.state
        self.state = SessionState.RUNNING
        self._event("session_resumed" if previous is SessionState.PAUSED else "session_started")

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
            step_events.extend(self._record_threat_management_events())
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

    def _record_threat_management_events(self) -> list[dict[str, Any]]:
        """Copy canonical Risk/Lifecycle transitions into the Session event journal."""
        coordinator = self.threat_management_coordinator
        snapshot = None if coordinator is None else coordinator.last_snapshot
        if snapshot is None:
            return []
        epoch = str(getattr(snapshot, "epoch", "session"))
        sequence = int(getattr(snapshot, "sequence", self.sequence))
        vectors_by_key = {
            identity: vector
            for vector in tuple(getattr(snapshot, "vectors", ()))
            if (identity := _track_identity(getattr(vector, "key", None))) is not None
        }
        recorded = self._record_schedule_events(snapshot, epoch, sequence, vectors_by_key)
        recorded.extend(self._record_lifecycle_events(snapshot, epoch, sequence, vectors_by_key))
        event_time = float(getattr(snapshot, "sim_time_s", self.simulator.t))
        for identity, vector in vectors_by_key.items():
            recorded.extend(self._record_vector_transitions(identity, vector, event_time))
        schedule = getattr(snapshot, "schedule", None)
        self._last_primary_track_key = _track_identity(getattr(schedule, "current_primary", None))
        return recorded

    def _record_schedule_events(
        self,
        snapshot: Any,
        epoch: str,
        sequence: int,
        vectors_by_key: dict[tuple[int, int], Any],
    ) -> list[dict[str, Any]]:
        recorded = []
        canonical_events = tuple(getattr(snapshot, "events", ()))
        primary_switched = any(
            str(getattr(event, "event_type", "")).upper() == "PRIMARY_SWITCHED"
            for event in canonical_events
        )
        for canonical in canonical_events:
            event_key = ("schedule", epoch, sequence, int(getattr(canonical, "event_id", 0)))
            if event_key in self._seen_threat_event_keys:
                continue
            self._seen_threat_event_keys.add(event_key)
            key = getattr(canonical, "key", None)
            identity = _track_identity(key)
            details = {
                "canonical_event_id": int(getattr(canonical, "event_id", 0)),
                "snapshot_sequence": sequence,
                **_track_details(key),
                "reason": getattr(canonical, "reason", None),
                "from_context": _enum_text(getattr(canonical, "from_context", None)),
                "to_context": _enum_text(getattr(canonical, "to_context", None)),
                "predicted": bool(getattr(canonical, "predicted", False)),
            }
            if identity is not None and identity in vectors_by_key:
                details.update(_vector_event_details(vectors_by_key[identity]))
            event_type = str(getattr(canonical, "event_type", "THREAT_EVENT")).lower()
            if (
                event_type == "schedule_reorder"
                and primary_switched
                and "CURRENT_PRIMARY" in {details["from_context"], details["to_context"]}
            ):
                continue
            same_context = details["from_context"] == details["to_context"]
            if event_type == "threat_escalated" and same_context:
                emergency = details.get("priority_class") == "RESPONSE_TIME_EMERGENCY"
                if not emergency or identity is None or identity in self._reported_emergency_tracks:
                    continue
                self._reported_emergency_tracks.add(identity)
            if event_type in {"threat_clearing", "threat_released"} and identity is not None:
                self._reported_emergency_tracks.discard(identity)
            if event_type == "primary_switched":
                self._enrich_primary_switch(details, identity)
            recorded.append(
                self._event(
                    event_type,
                    event_sim_time=float(getattr(canonical, "sim_time_s", self.simulator.t)),
                    **details,
                )
            )
        return recorded

    def _enrich_primary_switch(self, details: dict[str, Any], identity: tuple[int, int] | None) -> None:
        if self._last_primary_track_key is not None:
            details["from_target_id"] = self._last_primary_track_key[0]
            details["from_generation"] = self._last_primary_track_key[1]
        if identity is not None:
            details["to_target_id"] = identity[0]
            details["to_generation"] = identity[1]

    def _record_lifecycle_events(
        self,
        snapshot: Any,
        epoch: str,
        sequence: int,
        vectors_by_key: dict[tuple[int, int], Any],
    ) -> list[dict[str, Any]]:
        recorded = []
        lifecycle_snapshot = getattr(snapshot, "lifecycle_snapshot", None)
        for canonical in tuple(getattr(lifecycle_snapshot, "events", ())):
            event_key = ("lifecycle", epoch, int(getattr(canonical, "event_id", 0)))
            if event_key in self._seen_threat_event_keys:
                continue
            self._seen_threat_event_keys.add(event_key)
            key = getattr(canonical, "target_key", None)
            identity = _track_identity(key)
            details = {
                "canonical_event_id": int(getattr(canonical, "event_id", 0)),
                "snapshot_sequence": sequence,
                **_track_details(key),
                "from_state": getattr(canonical, "from_state", None),
                "to_state": getattr(canonical, "to_state", None),
                "reason": getattr(canonical, "reason", None),
            }
            if identity is not None and identity in vectors_by_key:
                details.update(_vector_event_details(vectors_by_key[identity]))
            recorded.append(
                self._event(
                    str(getattr(canonical, "event_type", "TARGET_TRANSITION")).lower(),
                    event_sim_time=float(getattr(canonical, "sim_time_s", self.simulator.t)),
                    **details,
                )
            )
        return recorded

    def _record_vector_transitions(
        self,
        identity: tuple[int, int],
        vector: Any,
        event_time: float,
    ) -> list[dict[str, Any]]:
        recorded = []
        details = _vector_event_details(vector)
        active = getattr(vector, "avoidance_action_active", None)
        if isinstance(active, bool):
            previous = self._avoidance_action_by_track.get(identity)
            if active and previous is not True:
                recorded.append(self._event("avoidance_action_started", event_sim_time=event_time, **details))
            elif not active and previous is True:
                recorded.append(self._event("avoidance_action_ended", event_sim_time=event_time, **details))
            self._avoidance_action_by_track[identity] = active

        display_class = details["display_class"]
        previous_display_class = self._display_class_by_track.get(identity)
        if previous_display_class is not None and display_class != previous_display_class:
            recorded.append(
                self._event(
                    "risk_level_changed",
                    event_sim_time=event_time,
                    **details,
                    from_display_class=previous_display_class,
                    to_display_class=display_class,
                )
            )
        self._display_class_by_track[identity] = display_class

        encounter_role = (details["encounter"], details["role"])
        previous_encounter_role = self._encounter_role_by_track.get(identity)
        if previous_encounter_role is not None and encounter_role != previous_encounter_role:
            recorded.append(
                self._event(
                    "colregs_changed",
                    event_sim_time=event_time,
                    **details,
                    from_encounter=previous_encounter_role[0],
                    from_role=previous_encounter_role[1],
                    to_encounter=encounter_role[0],
                    to_role=encounter_role[1],
                )
            )
        self._encounter_role_by_track[identity] = encounter_role

        observation_health = details["observation_health"]
        previous_health = self._observation_health_by_track.get(identity)
        if previous_health is not None and observation_health != previous_health:
            recovered = observation_health == "UPDATED"
            recorded.append(
                self._event(
                    "observation_recovered" if recovered else "observation_degraded",
                    event_sim_time=event_time,
                    **details,
                    from_health=previous_health,
                    to_health=observation_health,
                )
            )
        self._observation_health_by_track[identity] = observation_health
        return recorded

    def _event(self, event_type: str, *, event_sim_time: float | None = None, **details: Any) -> dict[str, Any]:
        event = {
            "event_id": len(self.events) + 1,
            "sequence": self.sequence,
            "sim_time": float(self.simulator.t if event_sim_time is None else event_sim_time),
            "type": event_type,
            "details": details,
        }
        self.events.append(event)
        return event

    def record_event(self, event_type: str, **details: Any) -> dict[str, Any]:
        """Record a Session event coordinated by the Web lifecycle boundary."""
        return self._event(event_type, **details)

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
            ship_id = int(ship_data["id"])
            event_time = float(planner["sim_time"])
            events.append(
                self._event("planner_solved", event_sim_time=event_time, ship_id=ship_id, planner=planner)
            )
            algorithm_details = planner.get("algorithm_details") or {}
            failure_code = algorithm_details.get("failure_code")
            succeeded = planner.get("feasible") is True and not failure_code
            previous_success = self._planner_success_by_ship.get(ship_key)
            if not succeeded and previous_success is not False:
                events.append(
                    self._event(
                        "planner_failed",
                        event_sim_time=event_time,
                        ship_id=ship_id,
                        solve_id=solve_id,
                        status=planner.get("status"),
                        feasible=planner.get("feasible"),
                        failure_code=failure_code,
                        reason=algorithm_details.get("reason"),
                    )
                )
            elif succeeded and previous_success is False:
                events.append(
                    self._event(
                        "planner_recovered",
                        event_sim_time=event_time,
                        ship_id=ship_id,
                        solve_id=solve_id,
                        status=planner.get("status"),
                    )
                )
            self._planner_success_by_ship[ship_key] = succeeded
        return events

    def simulation_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame(self.frames)

    def vessel_data(self) -> list:
        return mhm.convert_simulation_data_to_vessel_data(
            self.simulation_dataframe(),
            self.ship_info,
            self.config.utm_zone,
        )
