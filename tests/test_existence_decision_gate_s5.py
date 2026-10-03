"""P3-S5 (spec #90) decision-consumption tests for the IPDA existence gate.

Breakpoint ③ of the existence-probability chain: the encounter lifecycle reads
``TargetObservation.existence_prob`` and holds escalation (no ACTIVE phase, no
maneuver commitment) while the value sits below the profile threshold — the
milliAmpere/ECC19 gating precedent (research report 07 §2.2). The additive
default of 1.0 must keep every legacy construction path unchanged.
"""

import numpy as np
import pytest
from dataclasses import replace

from colav_simulator.core.colav.encounter_lifecycle import (
    CommitmentPhase,
    EncounterCycle,
    EncounterLifecycle,
    ObservationHealth,
    OwnshipObservation,
    OwnshipRole,
    PlannerOddProfile,
    RiskPhase,
    TargetObservation,
)
from colav_simulator.core.colav.encounter_lifecycle import Maneuverability
from colav_simulator.core.colav.custom_mpc_adapter import TrackedObstacle
from colav_simulator.core.tracking.trackers import TrackKey


def _head_on_cycle(*, sequence: int, sim_time_s: float, existence_prob: float = 1.0) -> EncounterCycle:
    return EncounterCycle(
        epoch="session-1",
        sequence=sequence,
        sim_time_s=sim_time_s,
        ownship=OwnshipObservation(
            position_ne_m=np.array([0.0, 0.0]),
            velocity_ne_mps=np.array([7.0, 0.0]),
            heading_rad=0.0,
            length_m=15.0,
            width_m=4.0,
            maneuverability=Maneuverability(np.radians(3.0), 0.3, (0.0, 8.0)),
        ),
        targets=(
            TargetObservation(
                key=TrackKey(1, 1),
                state_enu=np.array([1000.0, 0.0, -7.0, 0.0]),
                covariance=np.zeros((4, 4)),
                length_m=30.0,
                width_m=7.0,
                observed_at_s=sim_time_s,
                generated_at_s=sim_time_s,
                health=ObservationHealth.UPDATED,
                source="kf",
                existence_prob=existence_prob,
            ),
        ),
        route_bearing_rad=0.0,
        planned_speed_mps=7.0,
        profile=PlannerOddProfile(),
    )


def test_low_existence_holds_escalation_while_confirmed_target_commits() -> None:
    confirmed = EncounterLifecycle()
    gated = EncounterLifecycle()

    confirmed.step(_head_on_cycle(sequence=0, sim_time_s=0.0))
    gated.step(_head_on_cycle(sequence=0, sim_time_s=0.0))

    # t=5 s is the documented head-on commitment point (profile windows).
    committed = confirmed.step(_head_on_cycle(sequence=1, sim_time_s=5.0)).targets[0]
    held = gated.step(_head_on_cycle(sequence=1, sim_time_s=5.0, existence_prob=0.2)).targets[0]
    still_held = gated.step(_head_on_cycle(sequence=2, sim_time_s=10.0, existence_prob=0.2)).targets[0]

    assert committed.risk is RiskPhase.ACTIVE
    assert committed.commitment is CommitmentPhase.COMMITTED

    assert held.encounter is committed.encounter
    assert held.role is OwnshipRole.GIVE_WAY
    assert held.risk is RiskPhase.CANDIDATE
    assert held.commitment is CommitmentPhase.NONE
    assert still_held.risk is RiskPhase.CANDIDATE
    assert still_held.commitment is CommitmentPhase.NONE


def test_existence_gate_recovers_once_the_track_confirms() -> None:
    lifecycle = EncounterLifecycle()
    lifecycle.step(_head_on_cycle(sequence=0, sim_time_s=0.0, existence_prob=0.2))
    held = lifecycle.step(_head_on_cycle(sequence=1, sim_time_s=5.0, existence_prob=0.2)).targets[0]
    released = lifecycle.step(_head_on_cycle(sequence=2, sim_time_s=10.0, existence_prob=1.0)).targets[0]

    assert held.commitment is CommitmentPhase.NONE
    assert released.risk is RiskPhase.ACTIVE
    assert released.commitment is CommitmentPhase.COMMITTED


def test_target_observation_defaults_to_certain_existence_for_legacy_paths() -> None:
    target = TargetObservation(
        key=TrackKey(1, 1),
        state_enu=np.array([1000.0, 0.0, -7.0, 0.0]),
        covariance=np.zeros((4, 4)),
        length_m=30.0,
        width_m=7.0,
        observed_at_s=0.0,
        generated_at_s=0.0,
        health=ObservationHealth.UPDATED,
        source="god",
    )
    assert target.existence_prob == 1.0
    lifecycle = EncounterLifecycle()
    # The default path escalates exactly as before the gate existed.
    lifecycle.step(_head_on_cycle(sequence=0, sim_time_s=0.0))
    committed = lifecycle.step(_head_on_cycle(sequence=1, sim_time_s=5.0)).targets[0]
    assert committed.commitment is CommitmentPhase.COMMITTED
    with pytest.raises(ValueError):
        replace(target, existence_prob=1.5)


def test_tracked_obstacle_carries_the_existence_gate_additively() -> None:
    legacy = TrackedObstacle(
        target_id=1,
        state_enu=np.array([1000.0, 0.0, -7.0, 0.0]),
        covariance=np.zeros((4, 4)),
        length_m=30.0,
        width_m=7.0,
        observed_at_s=0.0,
        age_s=0.0,
    )
    assert legacy.existence_prob == 1.0
    gated = replace(legacy, existence_prob=0.42)
    assert gated.existence_prob == pytest.approx(0.42)
    with pytest.raises(ValueError):
        replace(legacy, existence_prob=-0.1)
