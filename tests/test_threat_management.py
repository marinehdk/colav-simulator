import math
from dataclasses import replace

import numpy as np
import pytest

from colav_simulator.core.colav.encounter_lifecycle import (
    EncounterCycle,
    Maneuverability,
    ObservationHealth,
    OwnshipObservation,
    PhysicalEncounterFacts,
    PlannerOddProfile,
    TargetObservation,
    canonical_physical_facts,
)
from colav_simulator.core.colav.threat_assessment import (
    PredictionBasis,
    ShipDomainProfile,
    ThreatPrediction,
    ThreatScheduleContext,
)
from colav_simulator.core.colav.threat_management import (
    AcceptedPlanReceipt,
    ThreatManagementCoordinator,
)
from colav_simulator.core.tracking.trackers import TrackKey


def _ownship() -> OwnshipObservation:
    return OwnshipObservation(
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


def _domain_profile() -> ShipDomainProfile:
    return ShipDomainProfile(
        profile_id="coordinator-test-domain",
        version="1",
        fore_m=300.0,
        aft_m=100.0,
        port_m=120.0,
        starboard_m=180.0,
        parameter_source="independent-test-fixture",
        assumptions=("metres", "engineering-envelope-only"),
    )


def _cycle(sequence: int, sim_time_s: float, targets: tuple[TargetObservation, ...]) -> EncounterCycle:
    return EncounterCycle(
        epoch="coordinator-session",
        sequence=sequence,
        sim_time_s=sim_time_s,
        ownship=_ownship(),
        targets=targets,
        route_bearing_rad=0.0,
        planned_speed_mps=7.0,
        profile=PlannerOddProfile(),
    )


def _target(key: TrackKey, north_m: float, *, health: ObservationHealth = ObservationHealth.UPDATED) -> TargetObservation:
    return TargetObservation(
        key=key,
        state_enu=np.array([north_m, 0.0, -7.0, 0.0]),
        covariance=np.zeros((4, 4)),
        length_m=30.0,
        width_m=7.0,
        observed_at_s=0.0,
        generated_at_s=0.0,
        health=health,
        source="coordinator-fixture",
    )


def _same_course_target(key: TrackKey, north_m: float) -> TargetObservation:
    return replace(_target(key, north_m), state_enu=np.array([north_m, 0.0, 7.0, 0.0]))


def _entering_prediction(key: TrackKey) -> ThreatPrediction:
    return ThreatPrediction(
        key=key,
        times_s=np.array([0.0, 20.0, 40.0]),
        states_enu=np.array(
            [
                [1500.0, 0.0, 7.0, 0.0],
                [100.0, 0.0, 7.0, 0.0],
                [-200.0, 0.0, 7.0, 0.0],
            ]
        ),
        basis=PredictionBasis.EXPLICIT_TRAJECTORY,
        model="coordinator-fixture",
    )


def test_coordinator_publishes_one_cycle_account_from_shared_physical_facts() -> None:
    targets = (_target(TrackKey(1, 1), 800.0), _target(TrackKey(2, 1), 1200.0))
    coordinator = ThreatManagementCoordinator()

    snapshot = coordinator.cycle(_cycle(0, 0.0, targets), profile=_domain_profile())

    assert snapshot.lifecycle_snapshot is not None
    assert snapshot.schedule is not None
    assert coordinator.lifecycle is not None
    assert snapshot.provenance["physical_facts_count"] == 2
    lifecycle_by_key = {decision.key: decision for decision in snapshot.lifecycle_snapshot.targets}
    vector_by_key = {vector.key: vector for vector in snapshot.vectors}
    for decision in lifecycle_by_key.values():
        assert vector_by_key[decision.key].range_m == decision.geometry.range_m
    assert snapshot.provenance["accepted_plan_applied_sequence"] is None


def test_coordinator_consumes_supplied_canonical_physical_facts_once() -> None:
    targets = (_target(TrackKey(1, 1), 800.0), _target(TrackKey(2, 1), 1200.0))
    cycle = _cycle(0, 0.0, targets)
    facts = canonical_physical_facts(cycle)
    custom_geometry = replace(facts[0].geometry, range_m=100.0, dcpa_m=100.0)
    custom_fact = PhysicalEncounterFacts(
        key=facts[0].key,
        relative_position_ne_m=np.array([100.0, 0.0]),
        relative_velocity_ne_mps=facts[0].relative_velocity_ne_mps,
        geometry=custom_geometry,
        observation_health=facts[0].observation_health,
        age_s=facts[0].age_s,
        hull_clearance_m=facts[0].hull_clearance_m,
    )

    snapshot = ThreatManagementCoordinator().cycle(
        replace(cycle, physical_facts=(custom_fact, facts[1])),
        profile=_domain_profile(),
    )

    assert snapshot.vectors[0].range_m == 100.0


def test_coordinator_primary_uses_domain_lexicographic_reason_without_weighted_score() -> None:
    ordinary = _target(TrackKey(1, 1), 800.0)
    domain_inside = replace(
        _target(TrackKey(2, 1), 200.0),
        state_enu=np.array([200.0, 100.0, -7.0, 0.0]),
    )

    snapshot = ThreatManagementCoordinator().cycle(
        _cycle(0, 0.0, (ordinary, domain_inside)),
        profile=_domain_profile(),
    )

    by_key = {vector.key: vector for vector in snapshot.vectors}
    assert by_key[domain_inside.key].current_domain.state.value == "INSIDE"
    assert snapshot.lifecycle_snapshot is not None
    assert snapshot.lifecycle_snapshot.primary_target == domain_inside.key
    assert by_key[domain_inside.key].priority_reason == "current_domain_violation"


def test_accepted_plan_receipt_is_staged_until_next_cycle() -> None:
    target = _target(TrackKey(1, 1), 800.0)
    coordinator = ThreatManagementCoordinator()
    first = _cycle(0, 0.0, (target,))
    receipt = AcceptedPlanReceipt(
        receipt_hash="receipt-1",
        accepted_sequence=0,
        accepted_at_s=0.0,
        valid_until_s=30.0,
    )

    same_cycle = coordinator.cycle(first, profile=_domain_profile(), accepted_plan=receipt)
    next_cycle = coordinator.cycle(
        replace(first, sequence=1, sim_time_s=5.0),
        profile=_domain_profile(),
    )

    assert same_cycle.provenance["accepted_plan_applied_sequence"] is None
    assert same_cycle.provenance["accepted_plan_staged_sequence"] == 0
    assert next_cycle.provenance["accepted_plan_applied_sequence"] == 1
    assert next_cycle.provenance["accepted_plan_receipt_hash"] == "receipt-1"


def test_schedule_separates_current_concurrent_next_and_monitor_with_typed_unknown() -> None:
    current = _target(TrackKey(1, 1), 500.0)
    concurrent = _target(TrackKey(2, 1), 600.0)
    next_target = _same_course_target(TrackKey(3, 1), 1500.0)
    monitor = _same_course_target(TrackKey(4, 1), 5000.0)
    coordinator = ThreatManagementCoordinator()
    profile = _domain_profile()
    coordinator.cycle(
        _cycle(0, 0.0, (current, concurrent, next_target, monitor)),
        profile=profile,
        predictions=(_entering_prediction(next_target.key),),
    )
    snapshot = coordinator.cycle(
        _cycle(1, 5.0, (replace(current, observed_at_s=5.0, generated_at_s=5.0),
                          replace(concurrent, observed_at_s=5.0, generated_at_s=5.0),
                          replace(next_target, observed_at_s=5.0, generated_at_s=5.0),
                          replace(monitor, observed_at_s=5.0, generated_at_s=5.0))),
        profile=profile,
        predictions=(_entering_prediction(next_target.key),),
    )

    schedule = snapshot.schedule
    assert schedule is not None
    assert schedule.current_primary in {current.key, concurrent.key}
    assert set(schedule.concurrent_required) == {current.key, concurrent.key} - {schedule.current_primary}
    assert schedule.next_threats == (next_target.key,)
    assert schedule.monitor == (monitor.key,)
    assert schedule.released == ()
    assert {entry.key for entry in schedule.entries} == {current.key, concurrent.key, next_target.key, monitor.key}
    next_entry = next(entry for entry in schedule.entries if entry.key == next_target.key)
    monitor_vector = next(vector for vector in snapshot.vectors if vector.key == monitor.key)
    assert next_entry.context is ThreatScheduleContext.NEXT
    assert next_entry.window is not None
    assert next_entry.window.entry_time_s is not None
    assert next_entry.window.entry_time_absolute_s == pytest.approx(5.0 + next_entry.window.entry_time_s)
    assert monitor_vector.window is not None
    assert monitor_vector.window.prediction_basis is PredictionBasis.UNAVAILABLE
    assert monitor_vector.window.unavailable_reason == "PREDICTION_UNAVAILABLE"


def test_schedule_emits_typed_predicted_entry_event_without_claiming_realized_threat() -> None:
    target = _same_course_target(TrackKey(3, 1), 1500.0)
    coordinator = ThreatManagementCoordinator()
    snapshot = coordinator.cycle(
        _cycle(0, 0.0, (target,)),
        profile=_domain_profile(),
        predictions=(_entering_prediction(target.key),),
    )

    assert any(event.event_type == "THREAT_ENTERED" and event.key == target.key for event in snapshot.events)
    event = next(event for event in snapshot.events if event.key == target.key)
    assert event.predicted is True


def test_unusable_observation_stays_typed_unknown_and_is_not_reclassified_as_clear() -> None:
    target = _target(TrackKey(9, 4), 500.0, health=ObservationHealth.UNUSABLE)

    snapshot = ThreatManagementCoordinator().cycle(
        _cycle(0, 0.0, (target,)),
        profile=_domain_profile(),
    )

    vector = snapshot.vectors[0]
    assert vector.observation_health is ObservationHealth.UNUSABLE
    assert vector.predicted_domain.state.value == "UNKNOWN"
    assert "OBSERVATION_UNUSABLE" in {reason.value for reason in vector.unavailable_reasons}
    assert snapshot.schedule is not None
    assert snapshot.schedule.monitor == (target.key,)
    assert snapshot.provenance["lifecycle_omitted_keys"] == ((9, 4),)


def test_stale_observation_is_unknown_even_when_geometry_would_be_inside_domain() -> None:
    target = replace(
        _target(TrackKey(10, 1), 200.0),
        observed_at_s=0.0,
        generated_at_s=10.0,
    )

    snapshot = ThreatManagementCoordinator().cycle(
        _cycle(0, 0.0, (target,)),
        profile=_domain_profile(),
    )

    vector = snapshot.vectors[0]
    assert vector.claim_completeness == "UNKNOWN"
    assert vector.current_domain.state.value == "UNKNOWN"
    assert vector.current_domain.unavailable_reason == "OBSERVATION_STALE"


def test_lifecycle_cycle_rejects_partial_canonical_physical_facts() -> None:
    targets = (_target(TrackKey(1, 1), 800.0), _target(TrackKey(2, 1), 1200.0))
    cycle = _cycle(0, 0.0, targets)
    partial = canonical_physical_facts(cycle)[:1]

    with pytest.raises(ValueError, match="physical facts must cover every target"):
        replace(cycle, physical_facts=partial)
