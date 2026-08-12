import math
from dataclasses import replace

import numpy as np
import pytest

from colav_simulator.core.colav.encounter_lifecycle import (
    AggregateDirective,
    CommitmentPhase,
    EncounterCycle,
    EncounterKind,
    EncounterLifecycle,
    LifecycleError,
    LifecycleEvent,
    LifecycleFailure,
    Maneuverability,
    ObservationHealth,
    OwnshipObservation,
    OwnshipRole,
    PairwiseGeometry,
    PassingSide,
    PlannerOddProfile,
    RiskPhase,
    Rule17Stage,
    TargetObservation,
    pairwise_geometry,
)
from colav_simulator.core.tracking.trackers import TrackKey


def test_pairwise_geometry_uses_north_zero_clockwise_enu_convention() -> None:
    geometry = pairwise_geometry(
        own_position_ne=np.array([0.0, 0.0]),
        own_velocity_ne=np.array([5.0, 0.0]),
        target_position_ne=np.array([100.0, 100.0]),
        target_velocity_ne=np.array([0.0, -5.0]),
    )

    assert isinstance(geometry, PairwiseGeometry)
    assert geometry.range_m == pytest.approx(math.sqrt(20_000.0))
    assert geometry.relative_bearing_rad == pytest.approx(math.pi / 4.0)
    assert geometry.signed_tcpa_s == pytest.approx(20.0)
    assert geometry.dcpa_m == pytest.approx(0.0, abs=1e-9)


def test_encounter_cycle_is_immutable_and_has_canonical_input_hash() -> None:
    ownship = OwnshipObservation(
        position_ne_m=np.array([0.0, 0.0]),
        velocity_ne_mps=np.array([7.0, 0.0]),
        heading_rad=0.0,
        length_m=15.0,
        width_m=4.0,
        maneuverability=Maneuverability(
            turn_rate_rad_s=math.radians(3.0),
            deceleration_mps2=0.3,
            speed_bounds_mps=(0.0, 8.0),
        ),
    )
    target = TargetObservation(
        key=TrackKey(3, 1),
        state_enu=np.array([500.0, 0.0, -7.0, 0.0]),
        covariance=np.zeros((4, 4)),
        length_m=30.0,
        width_m=7.0,
        observed_at_s=10.0,
        generated_at_s=10.0,
        health=ObservationHealth.UPDATED,
        source="god",
    )
    cycle = EncounterCycle(
        epoch="session-1",
        sequence=2,
        sim_time_s=10.0,
        ownship=ownship,
        targets=(target,),
        route_bearing_rad=0.0,
        planned_speed_mps=7.0,
        profile=PlannerOddProfile(),
    )
    equivalent = EncounterCycle(
        epoch="session-1",
        sequence=2,
        sim_time_s=10.0,
        ownship=ownship,
        targets=(target,),
        route_bearing_rad=0.0,
        planned_speed_mps=7.0,
        profile=PlannerOddProfile(),
    )

    assert cycle.input_hash == equivalent.input_hash
    assert cycle.targets[0].state_enu.flags.writeable is False
    with pytest.raises(ValueError):
        cycle.targets[0].state_enu[0] = 1.0


def test_lifecycle_retry_is_idempotent_and_conflicting_retry_fails() -> None:
    cycle = _head_on_cycle(sequence=0, sim_time_s=0.0)
    lifecycle = EncounterLifecycle()

    first = lifecycle.step(cycle)
    retry = lifecycle.step(cycle)

    assert retry is first
    conflicting = replace(cycle, planned_speed_mps=6.0)
    with pytest.raises(LifecycleError) as error:
        lifecycle.step(conflicting)
    assert error.value.failure is LifecycleFailure.CYCLE_CONFLICT


def test_reset_emits_and_persists_typed_epoch_event() -> None:
    persisted: list[LifecycleEvent] = []
    lifecycle = EncounterLifecycle(event_sink=persisted.append)
    lifecycle.step(_head_on_cycle(sequence=0, sim_time_s=0.0))

    event = lifecycle.reset(epoch="session-2", reason="adapter_reset", sim_time_s=5.0)

    assert event.event_type == "RESET"
    assert event.target_key is None
    assert event.from_state == "session-1"
    assert event.to_state == "session-2"
    assert event.reason == "adapter_reset"
    assert persisted[-1] is event
    assert lifecycle.live_events == (event,)
    assert lifecycle.event_overflow_count == 0


def test_head_on_risk_requires_physical_time_confirmation_then_locks_commitment() -> None:
    lifecycle = EncounterLifecycle()

    candidate = lifecycle.step(_head_on_cycle(sequence=0, sim_time_s=0.0)).targets[0]
    committed = lifecycle.step(_head_on_cycle(sequence=1, sim_time_s=5.0)).targets[0]
    persisted = lifecycle.step(_head_on_cycle(sequence=2, sim_time_s=10.0)).targets[0]

    assert candidate.encounter is EncounterKind.HEAD_ON
    assert candidate.role is OwnshipRole.GIVE_WAY
    assert candidate.risk is RiskPhase.CANDIDATE
    assert candidate.commitment is CommitmentPhase.NONE
    assert committed.risk is RiskPhase.ACTIVE
    assert committed.commitment is CommitmentPhase.COMMITTED
    assert committed.baseline_course_rad == pytest.approx(0.0)
    assert committed.required_course_change_rad > math.radians(5.0)
    assert persisted.baseline_course_rad == committed.baseline_course_rad
    assert persisted.required_course_change_rad == committed.required_course_change_rad


def test_committed_action_achievement_is_cumulative_after_course_recovers() -> None:
    lifecycle = EncounterLifecycle()
    lifecycle.step(_head_on_cycle(sequence=0, sim_time_s=0.0))
    committed = lifecycle.step(_head_on_cycle(sequence=1, sim_time_s=5.0)).targets[0]
    achieved_cycle = _head_on_cycle(sequence=2, sim_time_s=10.0)
    achieved_heading = committed.required_course_change_rad
    achieved = lifecycle.step(
        replace(
            achieved_cycle,
            ownship=replace(
                achieved_cycle.ownship,
                heading_rad=achieved_heading,
                velocity_ne_mps=7.0 * np.array([math.cos(achieved_heading), math.sin(achieved_heading)]),
            ),
        )
    ).targets[0]
    recovered_cycle = _head_on_cycle(sequence=3, sim_time_s=15.0)
    recovered = lifecycle.step(recovered_cycle).targets[0]

    assert achieved.action_achieved is True
    assert recovered.action_achieved is True
    assert recovered.actual_course_change_rad == pytest.approx(achieved.actual_course_change_rad)


def test_urgent_head_on_bypasses_entry_confirmation() -> None:
    lifecycle = EncounterLifecycle()
    cycle = _head_on_cycle(sequence=0, sim_time_s=0.0)
    urgent = replace(
        cycle,
        targets=(replace(cycle.targets[0], state_enu=np.array([200.0, 0.0, -7.0, 0.0])),),
    )

    decision = lifecycle.step(urgent).targets[0]

    assert decision.risk is RiskPhase.ACTIVE
    assert decision.commitment is CommitmentPhase.COMMITTED
    assert decision.newly_committed is True


@pytest.mark.parametrize(
    ("east_offset_m", "expected_side"),
    [(-50.0, PassingSide.PORT), (50.0, PassingSide.STARBOARD), (0.0, PassingSide.STARBOARD)],
)
def test_overtaking_selects_reachable_mirrored_corridor_and_locks_it(
    east_offset_m: float,
    expected_side: PassingSide,
) -> None:
    lifecycle = EncounterLifecycle()
    lifecycle.step(_overtaking_cycle(0, 0.0, east_offset_m))
    committed = lifecycle.step(_overtaking_cycle(1, 5.0, east_offset_m)).targets[0]
    moved_across_center = lifecycle.step(_overtaking_cycle(2, 10.0, -east_offset_m)).targets[0]

    assert committed.encounter is EncounterKind.OVERTAKING
    assert committed.role is OwnshipRole.OVERTAKING
    assert committed.passing_side is expected_side
    assert committed.required_course_change_rad > math.radians(5.0)
    assert moved_across_center.passing_side is expected_side


def test_overtaking_corridor_uses_route_deviation_after_clearance_tie() -> None:
    lifecycle = EncounterLifecycle()
    port_route = replace(_overtaking_cycle(0, 0.0, 0.0), route_bearing_rad=-0.3)
    lifecycle.step(port_route)
    committed = lifecycle.step(replace(port_route, sequence=1, sim_time_s=5.0)).targets[0]

    assert committed.passing_side is PassingSide.PORT


def test_noncooperative_stand_on_escalates_from_rule17_may_to_must() -> None:
    lifecycle = EncounterLifecycle()

    initial = lifecycle.step(_stand_on_cycle(0, 0.0, range_scale=1.0)).targets[0]
    may_act = lifecycle.step(_stand_on_cycle(1, 10.0, range_scale=1.0)).targets[0]
    must_act = lifecycle.step(_stand_on_cycle(2, 15.0, range_scale=0.4)).targets[0]

    assert initial.rule17 is Rule17Stage.STAND_ON
    assert initial.commitment is CommitmentPhase.NONE
    assert may_act.rule17 is Rule17Stage.MAY_ACT
    assert may_act.rule17_basis == "TARGET_ACTION_INADEQUATE_DYNAMICS_UNKNOWN"
    assert may_act.commitment is CommitmentPhase.COMMITTED
    assert must_act.rule17 is Rule17Stage.MUST_ACT
    assert must_act.rule17_basis == "URGENT_CLEARANCE_PROXY"
    assert must_act.passing_side is PassingSide.STARBOARD


def test_cooperative_give_way_action_keeps_stand_on_vessel_in_rule17_stand_on() -> None:
    lifecycle = EncounterLifecycle()
    lifecycle.step(_stand_on_cycle(0, 0.0, range_scale=1.0))
    decisions = []
    for sequence, sim_time_s in ((1, 5.0), (2, 10.0)):
        cooperative_cycle = _stand_on_cycle(sequence, sim_time_s, range_scale=1.0)
        cooperative_target = replace(
            cooperative_cycle.targets[0],
            state_enu=np.array(
                [
                    500.0,
                    -500.0,
                    7.0 * math.cos(math.radians(80.0)),
                    7.0 * math.sin(math.radians(80.0)),
                ]
            ),
        )
        decisions.append(lifecycle.step(replace(cooperative_cycle, targets=(cooperative_target,))).targets[0])

    assert decisions[0].rule17_basis == "MONITORING_TARGET_ACTION"
    decision = decisions[1]
    assert decision.rule17 is Rule17Stage.STAND_ON
    assert decision.rule17_basis == "TARGET_ACTION_ADEQUATE"
    assert decision.commitment is CommitmentPhase.NONE


def test_overtaken_role_stays_locked_until_target_is_past_and_clear() -> None:
    lifecycle = EncounterLifecycle()
    initial = _head_on_cycle(sequence=0, sim_time_s=0.0)
    overtaken_target = replace(
        initial.targets[0],
        state_enu=np.array([-500.0, 0.0, 10.0, 0.0]),
    )
    first = lifecycle.step(replace(initial, targets=(overtaken_target,))).targets[0]
    changed_geometry = _stand_on_cycle(1, 5.0, range_scale=0.2)
    retained = lifecycle.step(changed_geometry).targets[0]

    assert first.role is OwnshipRole.OVERTAKEN
    assert first.risk is RiskPhase.ACTIVE
    assert retained.role is OwnshipRole.OVERTAKEN
    assert retained.encounter is EncounterKind.OVERTAKING
    assert retained.rule17 is Rule17Stage.MUST_ACT


def test_noncooperative_overtaking_vessel_triggers_rule17_action_for_overtaken_ownship() -> None:
    lifecycle = EncounterLifecycle()
    decisions = []
    for sequence, sim_time_s in enumerate((0.0, 5.0, 10.0)):
        cycle = _head_on_cycle(sequence=sequence, sim_time_s=sim_time_s)
        target = replace(
            cycle.targets[0],
            state_enu=np.array([-500.0 + 3.0 * sim_time_s, 0.0, 10.0, 0.0]),
        )
        decisions.append(lifecycle.step(replace(cycle, targets=(target,))).targets[0])

    assert decisions[0].role is OwnshipRole.OVERTAKEN
    assert decisions[0].rule17 is Rule17Stage.STAND_ON
    assert decisions[1].commitment is CommitmentPhase.NONE
    assert decisions[2].rule17 is Rule17Stage.MAY_ACT
    assert decisions[2].commitment is CommitmentPhase.COMMITTED


def test_all_targets_are_processed_before_capacity_and_conflict_failures() -> None:
    lifecycle = EncounterLifecycle()
    base = _head_on_cycle(sequence=0, sim_time_s=0.0)
    seventeen = tuple(
        replace(base.targets[0], key=TrackKey(target_id, 1), state_enu=np.array([1000.0 + target_id, 0.0, -7.0, 0.0]))
        for target_id in range(1, 18)
    )
    lifecycle.step(replace(base, targets=seventeen))
    with pytest.raises(LifecycleError) as capacity:
        lifecycle.step(replace(base, sequence=1, sim_time_s=5.0, targets=seventeen))
    assert capacity.value.failure is LifecycleFailure.CAPACITY_EXCEEDED

    lifecycle.reset(epoch="session-2", reason="test_reset", sim_time_s=5.0)
    port = replace(base.targets[0], key=TrackKey(1, 1), state_enu=np.array([500.0, 50.0, 4.0, 0.0]))
    starboard = replace(base.targets[0], key=TrackKey(2, 1), state_enu=np.array([500.0, -50.0, 4.0, 0.0]))
    lifecycle.step(replace(base, targets=(port, starboard)))
    stopped = lifecycle.step(replace(base, sequence=1, sim_time_s=5.0, targets=(port, starboard)))
    assert stopped.directive.stop_required is True
    assert stopped.directive.speed_bounds_mps == pytest.approx((0.0, 7.0))

    lifecycle.reset(epoch="session-3", reason="test_reset", sim_time_s=5.0)
    head_on = replace(base.targets[0], key=TrackKey(3, 1), state_enu=np.array([300.0, 0.0, -4.0, 0.0]))
    lifecycle.step(replace(base, targets=(port, starboard, head_on)))
    with pytest.raises(LifecycleError) as conflict:
        lifecycle.step(replace(base, sequence=1, sim_time_s=5.0, targets=(port, starboard, head_on)))
    assert conflict.value.failure is LifecycleFailure.MANEUVER_CONFLICT


def test_unknown_role_contact_remains_an_optimizer_safety_target() -> None:
    lifecycle = EncounterLifecycle()
    base = _head_on_cycle(sequence=0, sim_time_s=0.0)
    low_speed = replace(base.targets[0], state_enu=np.array([500.0, 0.0, 0.1, 0.0]))
    first = lifecycle.step(replace(base, targets=(low_speed,))).targets[0]
    second_cycle = _head_on_cycle(sequence=1, sim_time_s=5.0)
    second_target = replace(
        low_speed,
        observed_at_s=5.0,
        generated_at_s=5.0,
    )
    confirmed = lifecycle.step(replace(second_cycle, targets=(second_target,)))

    assert first.role is OwnshipRole.UNKNOWN
    assert first.risk is RiskPhase.CANDIDATE
    assert confirmed.targets[0].risk is RiskPhase.ACTIVE
    assert confirmed.targets[0].commitment is CommitmentPhase.NONE
    assert confirmed.directive.required_targets == (TrackKey(1, 1),)
    assert confirmed.directive.passing_side is PassingSide.NONE


def test_compatible_commitments_produce_one_aggregate_directive() -> None:
    lifecycle = EncounterLifecycle()
    lifecycle.step(_head_on_cycle(sequence=0, sim_time_s=0.0))
    snapshot = lifecycle.step(_head_on_cycle(sequence=1, sim_time_s=5.0))

    assert isinstance(snapshot.directive, AggregateDirective)
    assert snapshot.directive.required_targets == (TrackKey(1, 1),)
    assert snapshot.directive.passing_side is PassingSide.STARBOARD
    assert snapshot.directive.minimum_course_change_rad == pytest.approx(snapshot.targets[0].required_course_change_rad)


def test_primary_target_switch_uses_physical_time_hysteresis_without_resetting_targets() -> None:
    lifecycle = EncounterLifecycle()
    base = _head_on_cycle(sequence=0, sim_time_s=0.0)
    first = replace(base.targets[0], key=TrackKey(1, 1), state_enu=np.array([800.0, 0.0, -7.0, 0.0]))
    second = replace(base.targets[0], key=TrackKey(2, 1), state_enu=np.array([1200.0, 0.0, -7.0, 0.0]))
    initial = lifecycle.step(replace(base, targets=(first, second)))
    assert initial.primary_target == TrackKey(1, 1)

    snapshots = []
    for sequence, sim_time_s in ((1, 5.0), (2, 10.0), (3, 15.0)):
        cycle = _head_on_cycle(sequence=sequence, sim_time_s=sim_time_s)
        farther_first = replace(
            first,
            state_enu=np.array([1300.0, 0.0, -7.0, 0.0]),
            observed_at_s=sim_time_s,
            generated_at_s=sim_time_s,
        )
        nearer_second = replace(
            second,
            state_enu=np.array([700.0, 0.0, -7.0, 0.0]),
            observed_at_s=sim_time_s,
            generated_at_s=sim_time_s,
        )
        snapshots.append(lifecycle.step(replace(cycle, targets=(farther_first, nearer_second))))

    assert [snapshot.primary_target for snapshot in snapshots] == [
        TrackKey(1, 1),
        TrackKey(1, 1),
        TrackKey(2, 1),
    ]
    assert all(tuple(decision.episode for decision in snapshot.targets) == (1, 1) for snapshot in snapshots)


def test_overtaking_directive_preserves_positive_speed_advantage() -> None:
    lifecycle = EncounterLifecycle()
    lifecycle.step(_overtaking_cycle(0, 0.0, 50.0))
    snapshot = lifecycle.step(_overtaking_cycle(1, 5.0, 50.0))

    assert snapshot.directive.speed_bounds_mps == pytest.approx((5.6, 8.0))


def test_release_requires_dynamic_clearance_and_sustained_separation_then_rearms() -> None:
    lifecycle = EncounterLifecycle()
    lifecycle.step(_head_on_cycle(sequence=0, sim_time_s=0.0))
    committed = lifecycle.step(_head_on_cycle(sequence=1, sim_time_s=5.0)).targets[0]
    altered_ownship = replace(
        _head_on_cycle(sequence=2, sim_time_s=15.0).ownship,
        position_ne_m=np.array([2000.0, 0.0]),
        heading_rad=committed.required_course_change_rad,
        velocity_ne_mps=np.array(
            [
                7.0 * math.cos(committed.required_course_change_rad),
                7.0 * math.sin(committed.required_course_change_rad),
            ]
        ),
    )
    clear_target = replace(
        _head_on_cycle(sequence=2, sim_time_s=15.0).targets[0],
        state_enu=np.array([0.0, 0.0, -7.0, 0.0]),
    )
    first_clear = lifecycle.step(
        replace(
            _head_on_cycle(sequence=2, sim_time_s=15.0),
            ownship=altered_ownship,
            targets=(clear_target,),
        )
    ).targets[0]
    transient_recovery_ownship = replace(
        altered_ownship,
        heading_rad=math.pi,
        velocity_ne_mps=np.array([-7.0, 0.0]),
    )
    released_snapshot = lifecycle.step(
        replace(
            _head_on_cycle(sequence=3, sim_time_s=25.0),
            ownship=transient_recovery_ownship,
            targets=(replace(clear_target, observed_at_s=25.0, generated_at_s=25.0),),
        )
    )
    released = released_snapshot.targets[0]

    assert first_clear.risk is RiskPhase.PAST_CLEAR
    assert first_clear.route_recovery_allowed is True
    assert released.risk is RiskPhase.RELEASED
    assert released.recovery_guard_active is True
    assert released_snapshot.directive.required_targets == (TrackKey(1, 1),)

    recovered_snapshot = lifecycle.step(
        replace(
            _head_on_cycle(sequence=4, sim_time_s=30.0),
            ownship=replace(altered_ownship, heading_rad=0.0, velocity_ne_mps=np.array([7.0, 0.0])),
            targets=(replace(clear_target, observed_at_s=30.0, generated_at_s=30.0),),
        )
    )
    recovered = recovered_snapshot.targets[0]
    assert recovered.recovery_guard_active is False
    assert recovered_snapshot.directive.required_targets == ()

    reappearing = lifecycle.step(_head_on_cycle(sequence=5, sim_time_s=40.0)).targets[0]
    assert recovered.risk is RiskPhase.RELEASED
    assert reappearing.episode == 2
    assert reappearing.risk is RiskPhase.CANDIDATE
    assert reappearing.commitment is CommitmentPhase.NONE


def test_lifecycle_events_are_versioned_bounded_and_incrementally_persisted() -> None:
    persisted: list[LifecycleEvent] = []
    lifecycle = EncounterLifecycle(event_capacity=2, event_sink=persisted.append)

    lifecycle.step(_stand_on_cycle(0, 0.0, range_scale=1.0))
    snapshot = lifecycle.step(_stand_on_cycle(1, 10.0, range_scale=1.0))
    lifecycle.step(_stand_on_cycle(2, 15.0, range_scale=0.4))

    assert persisted
    assert all(event.schema_version == "1.0" and event.source == "planner" for event in persisted)
    assert len(lifecycle.live_events) == 2
    assert lifecycle.event_overflow_count >= 1
    assert snapshot.events

    without_sink = EncounterLifecycle().step(_head_on_cycle(sequence=0, sim_time_s=0.0))
    assert without_sink.evidence_persisted is False


def test_time_gap_rolls_back_and_coast_reacquisition_requires_confirmation() -> None:
    lifecycle = EncounterLifecycle()
    lifecycle.step(_head_on_cycle(sequence=0, sim_time_s=0.0))
    with pytest.raises(LifecycleError) as gap:
        lifecycle.step(_head_on_cycle(sequence=1, sim_time_s=11.0))
    assert gap.value.failure is LifecycleFailure.TIME_GAP

    coasting_cycle = _head_on_cycle(sequence=1, sim_time_s=5.0)
    coasting_target = replace(
        coasting_cycle.targets[0],
        observed_at_s=0.0,
        generated_at_s=5.0,
        health=ObservationHealth.COASTING,
    )
    coasting = lifecycle.step(replace(coasting_cycle, targets=(coasting_target,))).targets[0]
    reacquired_cycle = _head_on_cycle(sequence=2, sim_time_s=10.0)
    reacquired = lifecycle.step(reacquired_cycle).targets[0]
    confirmed = lifecycle.step(_head_on_cycle(sequence=3, sim_time_s=15.0)).targets[0]

    assert coasting.health is ObservationHealth.COASTING
    assert reacquired.health is ObservationHealth.DEGRADED
    assert confirmed.health is ObservationHealth.UPDATED


def _head_on_cycle(*, sequence: int, sim_time_s: float) -> EncounterCycle:
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
            maneuverability=Maneuverability(math.radians(3.0), 0.3, (0.0, 8.0)),
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
                source="god",
            ),
        ),
        route_bearing_rad=0.0,
        planned_speed_mps=7.0,
        profile=PlannerOddProfile(),
    )


def _overtaking_cycle(sequence: int, sim_time_s: float, east_offset_m: float) -> EncounterCycle:
    cycle = _head_on_cycle(sequence=sequence, sim_time_s=sim_time_s)
    return replace(
        cycle,
        ownship=replace(
            cycle.ownship,
            position_ne_m=np.array([0.0, east_offset_m]),
            velocity_ne_mps=np.array([7.0, 0.0]),
        ),
        targets=(
            replace(
                cycle.targets[0],
                state_enu=np.array([500.0, 0.0, 4.0, 0.0]),
            ),
        ),
    )


def _stand_on_cycle(sequence: int, sim_time_s: float, *, range_scale: float) -> EncounterCycle:
    cycle = _head_on_cycle(sequence=sequence, sim_time_s=sim_time_s)
    return replace(
        cycle,
        targets=(
            replace(
                cycle.targets[0],
                state_enu=np.array([500.0 * range_scale, -500.0 * range_scale, 0.0, 7.0]),
            ),
        ),
    )
