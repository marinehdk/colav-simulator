"""Session-level baseline Threat Management cycles (monitor grade).

ADR-0002 keeps the sole online Threat Management authority in the session
runtime.  An integration that owns richer cycle inputs (Mid-MPC predictions and
accepted-plan receipts) advances the shared coordinator inside its adapter;
every other session runs this baseline cycle so Web and Evidence consumers
always read one canonical account instead of a typed UNAVAILABLE placeholder.

Facts basis: the Product Capability Policy admits only the God tracker, but the
baseline still freezes its typed ``TrackSnapshot`` output so target generation,
observation health, covariance and provenance retain their Tracker identity.
``baseline_due`` keeps adapter-owned lifecycles (any non-baseline snapshot
epoch) permanently exempt.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

from colav_simulator.core.colav.encounter_lifecycle import (
    EncounterCycle,
    Maneuverability,
    ObservationHealth,
    OwnshipObservation,
    PlannerOddProfile,
    TargetObservation,
)
from colav_simulator.core.colav.threat_assessment import (
    OwnshipThreatPrediction,
    PredictionBasis,
    ThreatPrediction,
)
from colav_simulator.core.tracking.trackers import TrackSnapshot, TrackStatus

BASELINE_PROFILE = PlannerOddProfile()
BASELINE_MANEUVERABILITY = Maneuverability(
    turn_rate_rad_s=math.radians(3.0),
    deceleration_mps2=0.3,
    speed_bounds_mps=(0.0, 8.0),
)
BASELINE_PREDICTION_DT_S = 2.0
BASELINE_PREDICTION_STEPS = 60
BASELINE_EPOCH = "session-baseline"


@dataclass(frozen=True)
class BaselineCycleInputs:
    cycle: EncounterCycle
    predictions: tuple[ThreatPrediction, ...]
    baseline_prediction: OwnshipThreatPrediction


def build_baseline_cycle_inputs(
    ship_list: list[Any],
    *,
    sim_time_s: float,
    sequence: int,
    ownship_index: int = 0,
) -> BaselineCycleInputs:
    """Freeze monitor-grade facts from the live ship list at one time."""
    ownship_ship = ship_list[ownship_index]
    state = np.asarray(ownship_ship.state, dtype=float).reshape(-1)
    heading = float(state[2])
    surge, sway = float(state[3]), float(state[4])
    velocity_ne = np.array(
        [surge * math.cos(heading) - sway * math.sin(heading),
         surge * math.sin(heading) + sway * math.cos(heading)]
    )
    speed = float(np.hypot(velocity_ne[0], velocity_ne[1]))
    course = math.atan2(velocity_ne[1], velocity_ne[0]) if speed > 1.0e-9 else heading
    ownship = OwnshipObservation(
        position_ne_m=state[:2].copy(),
        velocity_ne_mps=velocity_ne,
        heading_rad=heading,
        length_m=float(ownship_ship.length),
        width_m=float(ownship_ship.width),
        maneuverability=BASELINE_MANEUVERABILITY,
    )
    tracks, _ = ownship_ship.get_do_track_information()
    targets = tuple(_target_observation(track) for track in tracks)
    cycle = EncounterCycle(
        epoch=BASELINE_EPOCH,
        sequence=sequence,
        sim_time_s=sim_time_s,
        ownship=ownship,
        targets=targets,
        route_bearing_rad=course,
        planned_speed_mps=speed,
        profile=BASELINE_PROFILE,
    )
    times = np.arange(BASELINE_PREDICTION_STEPS + 1, dtype=float) * BASELINE_PREDICTION_DT_S
    predictions = tuple(
        ThreatPrediction(
            key=observation.key,
            times_s=times,
            states_enu=_constant_velocity_states(observation.state_enu, times),
            basis=PredictionBasis.CONSTANT_VELOCITY,
            model="session_baseline_constant_velocity_targets",
        )
        for observation in targets
    )
    baseline_prediction = OwnshipThreatPrediction(
        times_s=times,
        states_enu=_constant_velocity_states(
            np.concatenate((ownship.position_ne_m, ownship.velocity_ne_mps)),
            times,
        ),
        basis="CURRENT_MOTION_BASELINE",
        model="session_baseline_current_motion",
        source="SESSION_SHIP_LIST",
        target_keys=tuple(observation.key for observation in targets),
        reference_time_s=sim_time_s,
    )
    return BaselineCycleInputs(
        cycle=cycle,
        predictions=predictions,
        baseline_prediction=baseline_prediction,
    )


def baseline_due(coordinator: Any, sim_time_s: float, dt_s: float) -> bool:
    """Return whether a baseline cycle is owed at the post-step clock.

    Ownership is decided by the last snapshot's epoch: once any adapter has
    advanced the coordinator (Mid-MPC solves on its own period, so HOLD ticks
    leave the snapshot intentionally stale), the baseline must never interleave
    its own cycles into that lifecycle.  Time freshness only orders baseline
    cycles against each other.
    """
    last = coordinator.last_snapshot
    if last is None:
        return True
    if last.epoch != BASELINE_EPOCH:
        return False
    return last.sim_time_s < sim_time_s - dt_s - 1.0e-9


def _target_observation(track: TrackSnapshot) -> TargetObservation:
    if not isinstance(track, TrackSnapshot):
        raise TypeError("baseline Threat Management requires typed TrackSnapshot input")
    health = {
        TrackStatus.UPDATED: ObservationHealth.UPDATED,
        TrackStatus.COASTING: ObservationHealth.COASTING,
        TrackStatus.TERMINATED: ObservationHealth.UNUSABLE,
    }[track.status]
    return TargetObservation(
        key=track.key,
        state_enu=track.state,
        covariance=track.covariance,
        length_m=track.length_m,
        width_m=track.width_m,
        observed_at_s=track.observed_at_s,
        generated_at_s=track.generated_at_s,
        health=health,
        source=track.source,
    )


def _constant_velocity_states(state_enu: np.ndarray, times_s: np.ndarray) -> np.ndarray:
    state = np.asarray(state_enu, dtype=float).reshape(4)
    positions = state[:2] + times_s[:, None] * state[2:4]
    velocities = np.repeat(state[2:4][None, :], times_s.size, axis=0)
    return np.column_stack((positions, velocities))


__all__ = [
    "BASELINE_EPOCH",
    "BASELINE_PROFILE",
    "BaselineCycleInputs",
    "baseline_due",
    "build_baseline_cycle_inputs",
]
