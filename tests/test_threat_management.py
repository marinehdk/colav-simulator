import copy
import math
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from colav_simulator.core.colav.encounter_lifecycle import (
    EncounterCycle,
    Maneuverability,
    ObservationHealth,
    OwnshipObservation,
    PhysicalEncounterFacts,
    PlannerOddProfile,
    RiskPhase,
    TargetObservation,
    canonical_physical_facts,
)
from colav_simulator.core.colav.threat_assessment import (
    ConflictEdgeType,
    ConflictGraph,
    ConflictGraphProfile,
    ConflictUnavailableReason,
    DomainFacts,
    DomainState,
    OwnshipThreatPrediction,
    PredictionBasis,
    ShipDomainProfile,
    ThreatEvidenceReferences,
    ThreatPrediction,
    ThreatScheduleContext,
    ThreatVector,
    ThreatWindow,
)
from colav_simulator.core.colav.threat_management import (
    AcceptedPlanReceipt,
    ConflictGraphBuilder,
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


def _vector_for_graph(key: TrackKey) -> ThreatVector:
    outside = DomainFacts(state=DomainState.OUTSIDE, normalized_scale=2.0, uncertainty_radius_m=0.0)
    return ThreatVector(
        key=key,
        observation_health=ObservationHealth.UPDATED,
        range_m=1_000.0,
        closing_speed_mps=0.0,
        dcpa_m=1_000.0,
        tcpa_signed_s=None,
        tcpa_forward_s=None,
        hull_clearance_m=900.0,
        current_domain=outside,
        predicted_domain=outside,
        uncertainty_radius_m=0.0,
        claim_completeness="FULL",
        prediction_basis=PredictionBasis.EXPLICIT_TRAJECTORY,
        evidence_references=ThreatEvidenceReferences(
            track_key=key,
            track_hash="0" * 64,
            prediction_key=key,
            prediction_hash="1" * 64,
            domain_hash="2" * 64,
            profile_hash="3" * 64,
            physical_facts_key=key,
            physical_facts_hash="4" * 64,
        ),
    )


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
        vector = vector_by_key[decision.key]
        assert vector.range_m == decision.geometry.range_m
        assert vector.lifecycle_role is decision.role
        assert vector.lifecycle_risk is decision.risk
        assert vector.lifecycle_commitment is decision.commitment
        references = vector.evidence_references
        assert isinstance(references, ThreatEvidenceReferences)
        assert references.track_key == decision.key
        assert references.physical_facts_key == decision.key
        assert references.track_hash
        assert references.domain_hash
        assert references.profile_hash == snapshot.profile_hash
        assert references.physical_facts_hash
    serialized = snapshot.to_dict()["vectors"][0]
    serialized_decision = lifecycle_by_key[snapshot.vectors[0].key]
    assert serialized["lifecycle_role"] == serialized_decision.role.value
    assert serialized["lifecycle_risk"] == serialized_decision.risk.value
    assert serialized["lifecycle_commitment"] == serialized_decision.commitment.value
    assert serialized["evidence_references"]["track_key"] == {
        "target_id": snapshot.vectors[0].key.target_id,
        "generation": snapshot.vectors[0].key.generation,
    }
    with pytest.raises(ValueError):
        replace(snapshot.vectors[0], lifecycle_role="CAPTAIN")
    assert snapshot.provenance["accepted_plan_applied_sequence"] is None
    assert snapshot.provenance["physical_facts_hash"] == (
        "e14d4c4ae2b40459cad8db524f3d850ce736f50cf75e86b184648b6b0cf9420d"
    )


def test_threat_hashing_uses_one_canonical_helper() -> None:
    source = Path(__file__).resolve().parents[1] / "colav_simulator/core/colav/threat_management.py"
    assert "hashlib.sha256(json.dumps" not in source.read_text(encoding="utf-8")


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
    receipt = AcceptedPlanReceipt.issue(
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
    assert next_cycle.provenance["accepted_plan_receipt_hash"] == receipt.receipt_hash


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
        _cycle(
            1,
            5.0,
            (
                replace(current, observed_at_s=5.0, generated_at_s=5.0),
                replace(concurrent, observed_at_s=5.0, generated_at_s=5.0),
                replace(next_target, observed_at_s=5.0, generated_at_s=5.0),
                replace(monitor, observed_at_s=5.0, generated_at_s=5.0),
            ),
        ),
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
    assert next_entry.window.peak_time_s == 20.0
    assert next_entry.window.peak_time_s != next_entry.window.entry_time_s
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


def test_released_recovery_guard_target_has_one_schedule_membership() -> None:
    key = TrackKey(1, 1)
    coordinator = ThreatManagementCoordinator()
    target = _target(key, 800.0)
    coordinator.cycle(_cycle(0, 0.0, (target,)), profile=_domain_profile())
    committed_snapshot = coordinator.cycle(
        _cycle(1, 5.0, (replace(target, observed_at_s=5.0, generated_at_s=5.0),)),
        profile=_domain_profile(),
    )
    committed = committed_snapshot.lifecycle_snapshot.targets[0]
    altered_ownship = replace(
        _ownship(),
        position_ne_m=np.array([2_000.0, 0.0]),
        heading_rad=committed.required_course_change_rad,
        velocity_ne_mps=np.array(
            [
                7.0 * math.cos(committed.required_course_change_rad),
                7.0 * math.sin(committed.required_course_change_rad),
            ]
        ),
    )
    clear_target = replace(
        target,
        state_enu=np.array([0.0, 0.0, -7.0, 0.0]),
        observed_at_s=15.0,
        generated_at_s=15.0,
    )
    coordinator.cycle(
        replace(_cycle(2, 15.0, (clear_target,)), ownship=altered_ownship),
        profile=_domain_profile(),
    )
    released_snapshot = coordinator.cycle(
        replace(
            _cycle(
                3,
                25.0,
                (replace(clear_target, observed_at_s=25.0, generated_at_s=25.0),),
            ),
            ownship=replace(altered_ownship, heading_rad=math.pi, velocity_ne_mps=np.array([-7.0, 0.0])),
        ),
        profile=_domain_profile(),
    )

    lifecycle = released_snapshot.lifecycle_snapshot
    assert lifecycle.targets[0].risk is RiskPhase.RELEASED
    assert lifecycle.directive.required_targets == (key,)
    schedule = released_snapshot.schedule
    memberships = (
        *((schedule.current_primary,) if schedule.current_primary is not None else ()),
        *schedule.concurrent_required,
        *schedule.next_threats,
        *schedule.monitor,
        *schedule.released,
    )
    assert memberships.count(key) == 1
    assert key in set(schedule.concurrent_required) | ({schedule.current_primary} if schedule.current_primary else set())


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


def test_conflict_graph_empty_cycle_is_typed_and_deterministic() -> None:
    snapshot = ThreatManagementCoordinator().cycle(_cycle(0, 0.0, ()), profile=_domain_profile())

    assert snapshot.conflict_graph is not None
    assert snapshot.conflict_graph.nodes == ()
    assert snapshot.conflict_graph.edges == ()
    assert snapshot.conflict_graph.clusters == ()
    assert snapshot.conflict_graph.to_dict() == snapshot.conflict_graph.to_dict()
    assert snapshot.to_dict()["conflict_graph"]["semantic_hash"] == snapshot.conflict_graph.semantic_hash
    reasons = {reason.value for reason in snapshot.conflict_graph.unavailable_reasons}
    assert "BASELINE_UNAVAILABLE" in reasons
    assert "MISSING_ACCEPTED_PLAN_RECEIPT" in reasons


@pytest.mark.parametrize("target_count", (0, 1, 16, 17))
def test_conflict_graph_preserves_all_target_cardinalities(target_count: int) -> None:
    vectors = tuple(_vector_for_graph(TrackKey(index, 1)) for index in range(target_count))

    graph = ConflictGraphBuilder.build(
        vectors,
        predictions=(),
        profile=ConflictGraphProfile(),
        domain_profile=_domain_profile(),
        input_hash="cycle-hash",
        baseline_prediction=None,
        accepted_plan=None,
        lifecycle_snapshot=None,
        previous=None,
    )

    assert len(graph.nodes) == target_count
    assert graph.edges == ()
    assert graph.clusters == ()


def test_direct_window_overlap_forms_input_order_independent_transitive_cluster() -> None:
    profile = _domain_profile()
    graph_profile = ConflictGraphProfile(window_overlap_gap_s=0.0)
    windows = {
        TrackKey(1, 1): ThreatWindow(
            key=TrackKey(1, 1),
            entry_time_s=0.0,
            exit_time_s=10.0,
            horizon_end_s=10.0,
            prediction_basis=PredictionBasis.EXPLICIT_TRAJECTORY,
            completeness="FULL",
        ),
        TrackKey(2, 1): ThreatWindow(
            key=TrackKey(2, 1),
            entry_time_s=5.0,
            exit_time_s=15.0,
            horizon_end_s=15.0,
            prediction_basis=PredictionBasis.EXPLICIT_TRAJECTORY,
            completeness="FULL",
        ),
        TrackKey(3, 1): ThreatWindow(
            key=TrackKey(3, 1),
            entry_time_s=10.0,
            exit_time_s=20.0,
            horizon_end_s=20.0,
            prediction_basis=PredictionBasis.EXPLICIT_TRAJECTORY,
            completeness="FULL",
        ),
        TrackKey(4, 1): ThreatWindow(
            key=TrackKey(4, 1),
            entry_time_s=40.0,
            exit_time_s=50.0,
            horizon_end_s=50.0,
            prediction_basis=PredictionBasis.EXPLICIT_TRAJECTORY,
            completeness="FULL",
        ),
    }
    vectors = tuple(
        replace(
            _vector_for_graph(key),
            window=window,
        )
        for key, window in windows.items()
    )

    first = ConflictGraphBuilder.build(
        vectors,
        predictions=(),
        profile=graph_profile,
        domain_profile=profile,
        input_hash="cycle-hash",
        baseline_prediction=None,
        accepted_plan=None,
        lifecycle_snapshot=None,
        previous=None,
    )
    second = ConflictGraphBuilder.build(
        tuple(reversed(vectors)),
        predictions=(),
        profile=graph_profile,
        domain_profile=profile,
        input_hash="cycle-hash",
        baseline_prediction=None,
        accepted_plan=None,
        lifecycle_snapshot=None,
        previous=None,
    )

    assert [edge.edge_type for edge in first.edges] == [ConflictEdgeType.DIRECT_WINDOW_OVERLAP] * 3
    assert len(first.clusters) == 1
    assert first.clusters[0].members == tuple(windows)[:3]
    assert first.semantic_hash == second.semantic_hash

    split = ConflictGraphBuilder.build(
        vectors[:2],
        predictions=(),
        profile=graph_profile,
        domain_profile=profile,
        input_hash="cycle-hash-2",
        baseline_prediction=None,
        accepted_plan=None,
        lifecycle_snapshot=None,
        previous=first,
    )
    assert split.clusters[0].cluster_id != first.clusters[0].cluster_id
    assert first.clusters[0].cluster_id in split.clusters[0].parent_cluster_ids


def test_accepted_plan_creates_plan_induced_edge_only_with_material_before_after_witness() -> None:
    driver = TrackKey(1, 1)
    affected = TrackKey(2, 1)
    target_prediction = ThreatPrediction(
        key=affected,
        times_s=np.array([0.0, 10.0, 20.0]),
        states_enu=np.array(
            [
                [500.0, 0.0, 0.0, 0.0],
                [500.0, 0.0, 0.0, 0.0],
                [500.0, 0.0, 0.0, 0.0],
            ]
        ),
        basis=PredictionBasis.EXPLICIT_TRAJECTORY,
        model="graph-fixture",
    )
    baseline = OwnshipThreatPrediction(
        times_s=np.array([0.0, 10.0, 20.0]),
        states_enu=np.array([[0.0, 0.0, 7.0, 0.0], [70.0, 0.0, 7.0, 0.0], [140.0, 0.0, 7.0, 0.0]]),
        source="declared-baseline",
        target_keys=(affected,),
        reference_time_s=5.0,
    )
    accepted_prediction = OwnshipThreatPrediction(
        times_s=np.array([0.0, 10.0, 20.0]),
        states_enu=np.array([[0.0, 0.0, 7.0, 0.0], [175.0, 0.0, 17.5, 0.0], [350.0, 0.0, 17.5, 0.0]]),
        basis="ACCEPTED_PLAN",
        source="l4-receipt",
        target_keys=(affected,),
        reference_time_s=5.0,
        evidence_semantic_hash="accepted-evidence",
    )
    receipt = AcceptedPlanReceipt.issue(
        accepted_sequence=0,
        accepted_at_s=5.0,
        valid_until_s=30.0,
        accepted_prediction=accepted_prediction,
        plan_target=driver,
        target_keys=(affected,),
        prediction_hash=accepted_prediction.semantic_hash,
        acceptance_hash="l4-acceptance",
        domain_profile_hash=_domain_profile().profile_hash,
        evidence_semantic_hash="accepted-evidence",
    )
    vectors = (_vector_for_graph(driver), _vector_for_graph(affected))

    graph = ConflictGraphBuilder.build(
        vectors,
        predictions=(target_prediction,),
        profile=ConflictGraphProfile(material_tdv_advance_s=1.0, material_scale_worsening=0.05),
        domain_profile=_domain_profile(),
        input_hash="cycle-hash",
        baseline_prediction=baseline,
        accepted_plan=receipt,
        lifecycle_snapshot=SimpleNamespace(primary_target=driver),
        previous=None,
        sim_time_s=5.0,
    )

    plan_edges = [edge for edge in graph.edges if edge.edge_type is ConflictEdgeType.PLAN_INDUCED_CONFLICT]
    assert len(plan_edges) == 1
    assert plan_edges[0].members == (driver, affected)
    assert plan_edges[0].plan_receipt_hash == receipt.receipt_hash
    assert plan_edges[0].witness.to_dict()["materiality"]["new_domain_violation"] is True

    incomplete_receipt = AcceptedPlanReceipt.issue(
        accepted_sequence=receipt.accepted_sequence,
        accepted_at_s=receipt.accepted_at_s,
        valid_until_s=receipt.valid_until_s,
        accepted_prediction=accepted_prediction,
        plan_target=driver,
        target_keys=(affected,),
        prediction_hash=accepted_prediction.semantic_hash,
        acceptance_hash="l4-acceptance",
        domain_profile_hash=None,
        evidence_semantic_hash="accepted-evidence",
    )
    incomplete_graph = ConflictGraphBuilder.build(
        vectors,
        predictions=(target_prediction,),
        profile=ConflictGraphProfile(material_tdv_advance_s=1.0, material_scale_worsening=0.05),
        domain_profile=_domain_profile(),
        input_hash="cycle-hash",
        baseline_prediction=baseline,
        accepted_plan=incomplete_receipt,
        lifecycle_snapshot=SimpleNamespace(primary_target=driver),
        previous=None,
        sim_time_s=5.0,
    )
    assert not any(edge.edge_type is ConflictEdgeType.PLAN_INDUCED_CONFLICT for edge in incomplete_graph.edges)
    assert ConflictUnavailableReason.ACCEPTED_PLAN_RECEIPT_INVALID in incomplete_graph.unavailable_reasons

    benign_prediction = OwnshipThreatPrediction(
        times_s=baseline.times_s,
        states_enu=baseline.states_enu,
        basis="ACCEPTED_PLAN",
        source="l4-receipt",
        target_keys=(affected,),
        reference_time_s=5.0,
        evidence_semantic_hash="accepted-evidence",
    )
    benign_receipt = AcceptedPlanReceipt.issue(
        accepted_sequence=receipt.accepted_sequence,
        accepted_at_s=receipt.accepted_at_s,
        valid_until_s=receipt.valid_until_s,
        accepted_prediction=benign_prediction,
        plan_target=driver,
        target_keys=(affected,),
        prediction_hash=benign_prediction.semantic_hash,
        acceptance_hash="l4-acceptance",
        domain_profile_hash=_domain_profile().profile_hash,
        evidence_semantic_hash="accepted-evidence",
    )
    benign_graph = ConflictGraphBuilder.build(
        vectors,
        predictions=(target_prediction,),
        profile=ConflictGraphProfile(material_tdv_advance_s=1.0, material_scale_worsening=0.05),
        domain_profile=_domain_profile(),
        input_hash="cycle-hash",
        baseline_prediction=baseline,
        accepted_plan=benign_receipt,
        lifecycle_snapshot=SimpleNamespace(primary_target=driver),
        previous=None,
        sim_time_s=5.0,
    )
    assert not any(edge.edge_type is ConflictEdgeType.PLAN_INDUCED_CONFLICT for edge in benign_graph.edges)
    assert benign_graph.unavailable_reasons == ()


def test_conflict_graph_semantics_are_stable_across_accepted_receipt_envelopes() -> None:
    driver = TrackKey(1, 1)
    affected = TrackKey(2, 1)
    target_prediction = ThreatPrediction(
        key=affected,
        times_s=np.array([0.0, 10.0, 20.0]),
        states_enu=np.array([[500.0, 0.0, 0.0, 0.0]] * 3),
        basis=PredictionBasis.EXPLICIT_TRAJECTORY,
        model="semantic-envelope-fixture",
    )
    baseline = OwnshipThreatPrediction(
        times_s=np.array([0.0, 10.0, 20.0]),
        states_enu=np.array([[0.0, 0.0, 7.0, 0.0], [70.0, 0.0, 7.0, 0.0], [140.0, 0.0, 7.0, 0.0]]),
        source="declared-baseline",
        target_keys=(affected,),
        reference_time_s=5.0,
    )
    def receipt(acceptance_hash: str, evidence_hash: str) -> AcceptedPlanReceipt:
        accepted_prediction = OwnshipThreatPrediction(
            times_s=np.array([0.0, 10.0, 20.0]),
            states_enu=np.array(
                [[0.0, 0.0, 7.0, 0.0], [175.0, 0.0, 17.5, 0.0], [350.0, 0.0, 17.5, 0.0]]
            ),
            basis="ACCEPTED_PLAN",
            source="l4-receipt",
            target_keys=(affected,),
            reference_time_s=5.0,
            evidence_semantic_hash=evidence_hash,
        )
        return AcceptedPlanReceipt.issue(
            accepted_sequence=0,
            accepted_at_s=5.0,
            valid_until_s=30.0,
            accepted_prediction=accepted_prediction,
            plan_target=driver,
            target_keys=(affected,),
            prediction_hash=accepted_prediction.semantic_hash,
            acceptance_hash=acceptance_hash,
            domain_profile_hash=_domain_profile().profile_hash,
            evidence_semantic_hash=evidence_hash,
        )

    def graph(
        receipt_value: AcceptedPlanReceipt,
        previous: ConflictGraph | None = None,
    ) -> ConflictGraph:
        return ConflictGraphBuilder.build(
            (_vector_for_graph(driver), _vector_for_graph(affected)),
            predictions=(target_prediction,),
            profile=ConflictGraphProfile(material_tdv_advance_s=1.0, material_scale_worsening=0.05),
            domain_profile=_domain_profile(),
            input_hash="stable-cycle-input",
            baseline_prediction=baseline,
            accepted_plan=receipt_value,
            lifecycle_snapshot=SimpleNamespace(primary_target=driver),
            previous=previous,
            sim_time_s=5.0,
        )

    first_receipt = receipt("run-envelope-a", "evidence-envelope-a")
    second_receipt = receipt("run-envelope-b", "evidence-envelope-b")
    previous_a = graph(first_receipt)
    previous_b = graph(second_receipt)
    current_a = graph(first_receipt, previous_a)
    current_b = graph(second_receipt, previous_b)

    assert first_receipt.receipt_hash != second_receipt.receipt_hash
    assert first_receipt.semantic_lineage_hash == second_receipt.semantic_lineage_hash
    assert current_a.semantic_hash == current_b.semantic_hash
    assert current_a.evidence_hash != current_b.evidence_hash
    assert current_a.edges[0].edge_id == current_b.edges[0].edge_id
    assert current_a.edges[0].plan_receipt_hash != current_b.edges[0].plan_receipt_hash
    assert current_a.edges[0].accepted_plan_semantic_hash == current_b.edges[0].accepted_plan_semantic_hash
    assert current_a.clusters[0].cluster_id == current_b.clusters[0].cluster_id
    assert current_a.clusters[0].parent_cluster_ids == current_b.clusters[0].parent_cluster_ids
    assert current_a.to_dict()["edges"] != current_b.to_dict()["edges"]


def test_unaccepted_candidate_and_same_cycle_receipt_cannot_authorize_plan_induced_edge() -> None:
    target = _target(TrackKey(2, 1), 1_000.0)
    driver = _target(TrackKey(1, 1), 1_200.0)
    target_prediction = ThreatPrediction(
        key=target.key,
        times_s=np.array([0.0, 5.0, 10.0]),
        states_enu=np.array([[500.0, 0.0, 0.0, 0.0]] * 3),
        basis=PredictionBasis.EXPLICIT_TRAJECTORY,
        model="graph-fixture",
    )
    baseline = OwnshipThreatPrediction(
        times_s=np.array([0.0, 5.0, 10.0, 15.0]),
        states_enu=np.array([[0.0, 0.0, 7.0, 0.0], [70.0, 0.0, 7.0, 0.0], [140.0, 0.0, 7.0, 0.0], [210.0, 0.0, 7.0, 0.0]]),
        source="declared-baseline",
        target_keys=(target.key,),
        reference_time_s=5.0,
    )
    accepted_prediction = OwnshipThreatPrediction(
        times_s=np.array([0.0, 5.0, 10.0, 15.0]),
        states_enu=np.array(
            [
                [0.0, 0.0, 7.0, 0.0],
                [175.0, 0.0, 17.5, 0.0],
                [350.0, 0.0, 17.5, 0.0],
                [525.0, 0.0, 17.5, 0.0],
            ]
        ),
        basis="ACCEPTED_PLAN",
        source="l4-receipt",
        target_keys=(target.key,),
        reference_time_s=5.0,
        evidence_semantic_hash="accepted-evidence",
    )
    unaccepted_candidate = {
        "receipt_hash": "unaccepted-candidate",
        "sequence": 0,
        "accepted_at_s": 0.0,
        "valid_until_s": 30.0,
        "candidate_hash": "solver-candidate-only",
        "accepted_prediction": accepted_prediction.to_dict(),
        "target_key": [driver.key.target_id, driver.key.generation],
    }
    with pytest.raises(ValueError, match="unaccepted candidate"):
        AcceptedPlanReceipt.from_mapping(unaccepted_candidate)
    coordinator = ThreatManagementCoordinator()
    first = coordinator.cycle(
        _cycle(0, 0.0, (driver, target)),
        profile=_domain_profile(),
        predictions=(target_prediction,),
        baseline_prediction=baseline,
        accepted_plan=unaccepted_candidate,
    )

    assert first.conflict_graph is not None
    assert not any(edge.edge_type is ConflictEdgeType.PLAN_INDUCED_CONFLICT for edge in first.conflict_graph.edges)
    assert "ACCEPTED_PLAN_RECEIPT_INVALID" in {reason.value for reason in first.conflict_graph.unavailable_reasons}

    accepted = AcceptedPlanReceipt.issue(
        accepted_sequence=1,
        accepted_at_s=5.0,
        valid_until_s=30.0,
        accepted_prediction=accepted_prediction,
        plan_target=driver.key,
        target_keys=(target.key,),
        prediction_hash=accepted_prediction.semantic_hash,
        acceptance_hash="l4-acceptance",
        domain_profile_hash=_domain_profile().profile_hash,
        evidence_semantic_hash="accepted-evidence",
    )
    same_cycle = coordinator.cycle(
        _cycle(1, 5.0, (driver, target)),
        profile=_domain_profile(),
        predictions=(target_prediction,),
        baseline_prediction=baseline,
        accepted_plan=accepted,
    )
    assert same_cycle.provenance["accepted_plan_applied_sequence"] is None
    assert same_cycle.conflict_graph is not None
    assert not any(edge.edge_type is ConflictEdgeType.PLAN_INDUCED_CONFLICT for edge in same_cycle.conflict_graph.edges)
    next_cycle = coordinator.cycle(
        _cycle(2, 10.0, (driver, target)),
        profile=_domain_profile(),
        predictions=(target_prediction,),
        baseline_prediction=baseline,
    )
    assert next_cycle.provenance["accepted_plan_applied_sequence"] == 2
    assert next_cycle.conflict_graph is not None
    assert any(edge.edge_type is ConflictEdgeType.PLAN_INDUCED_CONFLICT for edge in next_cycle.conflict_graph.edges)


def test_mismatched_accepted_prediction_digest_is_rejected_before_staging() -> None:
    prediction = OwnshipThreatPrediction(
        times_s=np.array([0.0, 1.0]),
        states_enu=np.array([[0.0, 0.0, 1.0, 0.0], [1.0, 0.0, 1.0, 0.0]]),
        basis="ACCEPTED_PLAN",
        source="l4-receipt",
    )

    with pytest.raises(ValueError, match="prediction hash"):
        AcceptedPlanReceipt(
            receipt_hash="receipt",
            accepted_sequence=0,
            accepted_at_s=0.0,
            valid_until_s=1.0,
            accepted_prediction=prediction,
            prediction_hash="tampered",
        )


@pytest.mark.parametrize(
    ("path", "tampered"),
    (
        (("receipt_hash",), "not-the-canonical-hash"),
        (("prediction_hash",), "tampered-prediction-hash"),
        (("acceptance_hash",), "tampered-acceptance-hash"),
        (("evidence_semantic_hash",), "tampered-evidence-hash"),
        (("domain_profile_hash",), "tampered-profile-hash"),
        (("accepted_at_s",), 1.0),
        (("valid_until_s",), 6.0),
        (("plan_target",), [8, 1]),
        (("target_keys",), []),
        (("accepted_prediction", "states_enu", 1, 0), 999.0),
    ),
)
def test_tampered_accepted_plan_receipt_is_typed_unavailable(
    path: tuple[object, ...],
    tampered: object,
) -> None:
    key = TrackKey(9, 1)
    prediction = OwnshipThreatPrediction(
        times_s=np.array([0.0, 5.0]),
        states_enu=np.array([[0.0, 0.0, 4.0, 0.0], [20.0, 0.0, 4.0, 0.0]]),
        basis="ACCEPTED_PLAN",
        source="l4-accepted-fixture",
        target_keys=(key,),
        reference_time_s=0.0,
        evidence_semantic_hash="evidence-hash",
    )
    receipt = AcceptedPlanReceipt.issue(
        accepted_sequence=0,
        accepted_at_s=0.0,
        valid_until_s=5.0,
        accepted_prediction=prediction,
        plan_target=key,
        target_keys=(key,),
        prediction_hash=prediction.semantic_hash,
        acceptance_hash="acceptance-hash",
        domain_profile_hash=_domain_profile().profile_hash,
        evidence_semantic_hash="evidence-hash",
    )
    assert AcceptedPlanReceipt.from_mapping(receipt.to_dict()).receipt_hash == receipt.receipt_hash
    document = copy.deepcopy(receipt.to_dict())
    target: object = document
    for segment in path[:-1]:
        target = target[segment]
    target[path[-1]] = tampered

    snapshot = ThreatManagementCoordinator().cycle(
        _cycle(0, 0.0, (_target(key, 800.0),)),
        profile=_domain_profile(),
        accepted_plan=document,
    )

    assert ConflictUnavailableReason.ACCEPTED_PLAN_RECEIPT_INVALID in snapshot.conflict_graph.unavailable_reasons


def test_unaccepted_candidate_uses_context_vocabulary() -> None:
    with pytest.raises(ValueError, match="unaccepted candidate"):
        AcceptedPlanReceipt.from_mapping(
            {
                "receipt_hash": "candidate",
                "sequence": 0,
                "accepted_at_s": 0.0,
                "valid_until_s": 1.0,
                "candidate_hash": "not-accepted",
            }
        )
