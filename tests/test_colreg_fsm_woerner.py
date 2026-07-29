from __future__ import annotations

from colav_simulator.evaluation.colreg_fsm import (
    EncounterObservation,
    EncounterState,
    PairwiseColregFSM,
)
from colav_simulator.evaluation.profiles import load_evaluator_profile


def observation(
    time_s: float,
    encounter: str,
    stage: int,
    range_m: float,
    signed_tcpa_s: float,
) -> EncounterObservation:
    return EncounterObservation(
        time_s=time_s,
        encounter=encounter,
        stage=stage,
        range_m=range_m,
        dcpa_m=20.0,
        signed_tcpa_s=signed_tcpa_s,
        relative_bearing_deg=2.0,
        contact_angle_deg=-2.0,
    )


def test_rule_locks_at_stage2_and_does_not_drift_at_boundary() -> None:
    profile = load_evaluator_profile()
    fsm = PairwiseColregFSM(profile)
    assert fsm.update(observation(0.0, "head_on", 2, 2000.0, 200.0)) == EncounterState.HO
    assert fsm.update(observation(1.0, "crossing_give_way", 2, 1900.0, 190.0)) == EncounterState.HO
    assert len(fsm.transitions) == 1
    assert fsm.transitions[0].reason == "stage2_entry_and_positive_tcpa"


def test_emergency_entry_only_from_give_way_or_head_on_with_positive_tcpa() -> None:
    profile = load_evaluator_profile()
    head_on = PairwiseColregFSM(profile)
    head_on.update(observation(0.0, "head_on", 2, 1000.0, 100.0))
    assert head_on.update(observation(1.0, "head_on", 4, 100.0, 50.0)) == EncounterState.EM

    post_cpa = PairwiseColregFSM(profile)
    post_cpa.update(observation(0.0, "crossing_give_way", 2, 1000.0, 100.0))
    assert post_cpa.update(observation(1.0, "crossing_give_way", 4, 100.0, -1.0)) == EncounterState.GW

    stand_on = PairwiseColregFSM(profile)
    stand_on.update(observation(0.0, "crossing_stand_on", 2, 1000.0, 100.0))
    assert stand_on.update(observation(1.0, "crossing_stand_on", 4, 100.0, 10.0)) == EncounterState.SO


def test_safe_exit_uses_hysteresis_and_clears_lock() -> None:
    profile = load_evaluator_profile()
    fsm = PairwiseColregFSM(profile)
    fsm.update(observation(0.0, "overtaking", 2, 2000.0, 100.0))
    assert fsm.update(observation(1.0, "clear", 1, 2700.0, -10.0)) == EncounterState.SF
    assert fsm.locked_state is None
