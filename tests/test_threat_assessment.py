import math
from dataclasses import replace

import numpy as np
import pytest

from colav_simulator.core.colav import ThreatAssessment as ExportedThreatAssessment
from colav_simulator.core.colav.encounter_lifecycle import (
    Maneuverability,
    OwnshipObservation,
    PairwiseGeometry,
    PhysicalEncounterFacts,
)
from colav_simulator.core.colav.threat_assessment import (
    DomainQualification,
    DomainState,
    PredictionBasis,
    ShipDomainProfile,
    ThreatAssessment,
    ThreatAssessmentRequest,
    ThreatPrediction,
    ThreatTargetObservation,
    ThreatUnavailableReason,
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


def _profile() -> ShipDomainProfile:
    return ShipDomainProfile(
        profile_id="test-domain",
        version="1",
        fore_m=300.0,
        aft_m=100.0,
        port_m=120.0,
        starboard_m=180.0,
        parameter_source="independent-test-fixture",
        assumptions=("metres", "engineering-envelope-only"),
    )


def test_empty_assessment_is_versioned_immutable_and_deterministic() -> None:
    request = ThreatAssessmentRequest(
        epoch="run-1",
        sequence=0,
        sim_time_s=10.0,
        ownship=_ownship(),
        targets=(),
        profile=_profile(),
    )

    first = ThreatAssessment().evaluate(request)
    second = ThreatAssessment().evaluate(request)
    class_call = ThreatAssessment.evaluate(request)

    assert first.schema_version == "colav.threat-management.snapshot@1"
    assert first.vectors == ()
    assert first.profile_hash == second.profile_hash
    assert first.profile.to_dict() == _profile().to_dict()
    assert first.semantic_hash == second.semantic_hash
    assert first.to_dict() == second.to_dict()
    assert class_call.to_dict() == first.to_dict()
    assert isinstance(first.vectors, tuple)
    assert ExportedThreatAssessment is ThreatAssessment


def test_current_domain_fact_is_independent_from_hull_clearance_and_missing_prediction_is_typed() -> None:
    target = ThreatTargetObservation(
        key=TrackKey(4, 1),
        state_enu=np.array([50.0, 0.0, 7.0, 0.0]),
        covariance=np.zeros((4, 4)),
        length_m=30.0,
        width_m=7.0,
        observed_at_s=10.0,
        generated_at_s=10.0,
        health="UPDATED",
        source="independent-fixture",
    )
    request = ThreatAssessmentRequest(
        epoch="run-1",
        sequence=1,
        sim_time_s=10.0,
        ownship=replace(_ownship(), velocity_ne_mps=np.array([0.0, 0.0])),
        targets=(target,),
        profile=_profile(),
    )

    vector = ThreatAssessment().evaluate(request).vectors[0]

    # Profile center is 100 m forward, semi-axes are 200 m and 150 m.
    expected_scale = math.sqrt(((-50.0) / 200.0) ** 2)
    assert vector.range_m == 50.0
    assert vector.current_domain.state is DomainState.INSIDE
    assert vector.current_domain.normalized_scale == expected_scale
    assert vector.hull_clearance_m is not None
    assert vector.predicted_domain.state is DomainState.UNKNOWN
    assert vector.predicted_domain.unavailable_reason == "PREDICTION_UNAVAILABLE"
    assert vector.predicted_domain.unavailable_reason is ThreatUnavailableReason.PREDICTION_UNAVAILABLE


def test_prediction_facts_report_domain_entry_minimum_and_exit_without_using_cpa_oracle() -> None:
    target = ThreatTargetObservation(
        key=TrackKey(5, 1),
        state_enu=np.array([500.0, 0.0, 0.0, 0.0]),
        covariance=np.zeros((4, 4)),
        length_m=30.0,
        width_m=7.0,
        observed_at_s=10.0,
        generated_at_s=10.0,
        health="UPDATED",
        source="independent-fixture",
    )
    prediction = ThreatPrediction(
        key=target.key,
        times_s=np.array([0.0, 20.0, 40.0]),
        states_enu=np.array(
            [
                [500.0, 0.0, 0.0, 0.0],
                [100.0, 0.0, 0.0, 0.0],
                [-200.0, 0.0, 0.0, 0.0],
            ]
        ),
        basis=PredictionBasis.EXPLICIT_TRAJECTORY,
        model="independent-linear-fixture",
    )
    request = ThreatAssessmentRequest(
        epoch="run-1",
        sequence=2,
        sim_time_s=10.0,
        ownship=replace(_ownship(), velocity_ne_mps=np.array([0.0, 0.0])),
        targets=(target,),
        predictions=(prediction,),
        profile=_profile(),
    )

    vector = ThreatAssessment().evaluate(request).vectors[0]

    assert vector.prediction_basis is PredictionBasis.EXPLICIT_TRAJECTORY
    assert vector.predicted_domain.state is DomainState.INSIDE
    assert vector.predicted_domain.horizon_min_scale == 0.0
    assert vector.predicted_domain.tdv_s == 10.0
    assert vector.predicted_domain.tde_s == (20.0 + (1.0 / 1.5) * 20.0)


def test_uncertainty_inflates_domain_and_unqualified_or_missing_facts_stay_typed() -> None:
    target = ThreatTargetObservation(
        key=TrackKey(6, 3),
        state_enu=np.array([500.0, 0.0, 7.0, 0.0]),
        covariance=np.diag([10_000.0, 0.0, 0.0, 0.0]),
        length_m=None,
        width_m=None,
        observed_at_s=10.0,
        generated_at_s=10.0,
        health="COASTING",
        source="independent-fixture",
    )
    request = ThreatAssessmentRequest(
        epoch="run-1",
        sequence=3,
        sim_time_s=10.0,
        ownship=_ownship(),
        targets=(target,),
        profile=_profile(),
    )

    vector = ThreatAssessment().evaluate(request).vectors[0]
    unqualified = ThreatAssessment().evaluate(
        replace(request, profile=replace(_profile(), qualification=DomainQualification.UNQUALIFIED))
    ).vectors[0]

    assert vector.uncertainty_radius_m == 200.0
    assert vector.current_domain.normalized_scale == 1.0
    assert vector.current_domain.state is DomainState.TANGENT
    assert vector.current_domain.hard_safety_gate is False
    assert vector.hull_clearance_m is None
    assert "TARGET_DIMENSIONS_UNAVAILABLE" in vector.unavailable_reasons
    assert vector.claim_completeness == "DEGRADED"
    assert unqualified.current_domain.state is DomainState.UNQUALIFIED
    assert unqualified.current_domain.normalized_scale is None
    assert unqualified.current_domain.hard_safety_gate is False
    assert "PROFILE_UNQUALIFIED" in unqualified.unavailable_reasons


def test_physical_cpa_facts_keep_receding_and_low_speed_cases_explicit() -> None:
    approaching = ThreatTargetObservation(
        key=TrackKey(7, 1),
        state_enu=np.array([500.0, 0.0, 0.0, 0.0]),
        covariance=np.zeros((4, 4)),
        length_m=30.0,
        width_m=7.0,
        observed_at_s=10.0,
        generated_at_s=10.0,
        health="UPDATED",
        source="independent-fixture",
    )
    receding = replace(approaching, key=TrackKey(8, 1), state_enu=np.array([100.0, 0.0, 14.0, 0.0]))
    stationary = replace(approaching, key=TrackKey(9, 1), state_enu=np.array([100.0, 0.0, 7.0, 0.0]))
    request = ThreatAssessmentRequest(
        epoch="run-1",
        sequence=4,
        sim_time_s=10.0,
        ownship=_ownship(),
        targets=(approaching, receding, stationary),
        profile=_profile(),
    )

    vectors = ThreatAssessment().evaluate(request).vectors
    by_key = {vector.key: vector for vector in vectors}

    assert by_key[TrackKey(7, 1)].closing_speed_mps == 7.0
    assert by_key[TrackKey(7, 1)].tcpa_signed_s == (500.0 / 7.0)
    assert by_key[TrackKey(7, 1)].tcpa_forward_s == (500.0 / 7.0)
    assert by_key[TrackKey(7, 1)].dcpa_m == 0.0
    assert by_key[TrackKey(8, 1)].closing_speed_mps < 0.0
    assert by_key[TrackKey(8, 1)].tcpa_signed_s < 0.0
    assert by_key[TrackKey(8, 1)].tcpa_forward_s == 0.0
    assert by_key[TrackKey(8, 1)].dcpa_m == 100.0
    assert by_key[TrackKey(9, 1)].tcpa_signed_s is None
    assert by_key[TrackKey(9, 1)].tcpa_forward_s is None
    assert "RELATIVE_MOTION_UNDEFINED" in by_key[TrackKey(9, 1)].unavailable_reasons


def test_assessment_uses_canonical_relative_vectors_for_closing_speed() -> None:
    target = ThreatTargetObservation(
        key=TrackKey(11, 1),
        state_enu=np.array([500.0, 0.0, 0.0, 0.0]),
        covariance=np.zeros((4, 4)),
        length_m=30.0,
        width_m=7.0,
        observed_at_s=10.0,
        generated_at_s=10.0,
        health="UPDATED",
        source="canonical-facts-fixture",
    )
    fact = PhysicalEncounterFacts(
        key=target.key,
        relative_position_ne_m=np.array([100.0, 0.0]),
        relative_velocity_ne_mps=np.array([-2.0, 0.0]),
        geometry=PairwiseGeometry(
            range_m=100.0,
            dcpa_m=0.0,
            signed_tcpa_s=50.0,
            relative_bearing_rad=0.0,
            contact_bearing_rad=0.0,
            course_difference_rad=0.0,
        ),
        observation_health="UPDATED",
        age_s=0.0,
        hull_clearance_m=0.0,
    )

    vector = ThreatAssessment().evaluate(
        ThreatAssessmentRequest(
            epoch="run-1",
            sequence=6,
            sim_time_s=10.0,
            ownship=_ownship(),
            targets=(target,),
            profile=_profile(),
            physical_facts=(fact,),
        )
    ).vectors[0]

    assert vector.range_m == 100.0
    assert vector.closing_speed_mps == 2.0
    assert vector.tcpa_signed_s == 50.0
    assert vector.current_domain.state is DomainState.INSIDE


def test_assessment_request_rejects_partial_canonical_physical_facts() -> None:
    first = ThreatTargetObservation(
        key=TrackKey(12, 1),
        state_enu=np.array([500.0, 0.0, 0.0, 0.0]),
        covariance=np.zeros((4, 4)),
        length_m=30.0,
        width_m=7.0,
        observed_at_s=10.0,
        generated_at_s=10.0,
        health="UPDATED",
        source="canonical-facts-fixture",
    )
    second = replace(first, key=TrackKey(13, 1), state_enu=np.array([600.0, 0.0, 0.0, 0.0]))
    fact = PhysicalEncounterFacts(
        key=first.key,
        relative_position_ne_m=np.array([500.0, 0.0]),
        relative_velocity_ne_mps=np.array([-7.0, 0.0]),
        geometry=PairwiseGeometry(500.0, 0.0, 71.0, 0.0, 0.0, 0.0),
        observation_health="UPDATED",
        age_s=0.0,
        hull_clearance_m=0.0,
    )

    with pytest.raises(ValueError, match="physical_facts must cover every target"):
        ThreatAssessmentRequest(
            epoch="run-1",
            sequence=7,
            sim_time_s=10.0,
            ownship=_ownship(),
            targets=(first, second),
            profile=_profile(),
            physical_facts=(fact,),
        )


def test_generation_is_part_of_semantic_identity_and_no_intersection_is_not_clear_claim() -> None:
    target = ThreatTargetObservation(
        key=TrackKey(10, 1),
        state_enu=np.array([500.0, 0.0, 0.0, 0.0]),
        covariance=np.zeros((4, 4)),
        length_m=30.0,
        width_m=7.0,
        observed_at_s=10.0,
        generated_at_s=10.0,
        health="UPDATED",
        source="independent-fixture",
    )
    prediction = ThreatPrediction(
        key=target.key,
        times_s=np.array([0.0, 10.0]),
        states_enu=np.array([[500.0, 0.0, 0.0, 0.0], [400.0, 0.0, 0.0, 0.0]]),
        basis=PredictionBasis.CONSTANT_VELOCITY,
        model="independent-linear-fixture",
    )
    first_request = ThreatAssessmentRequest(
        epoch="run-1",
        sequence=5,
        sim_time_s=10.0,
        ownship=_ownship(),
        targets=(target,),
        predictions=(prediction,),
        profile=_profile(),
    )
    next_generation = replace(target, key=TrackKey(10, 2))
    second_request = replace(
        first_request,
        sequence=6,
        targets=(next_generation,),
        predictions=(replace(prediction, key=next_generation.key),),
    )

    first = ThreatAssessment().evaluate(first_request)
    second = ThreatAssessment().evaluate(second_request)

    assert first.vectors[0].key == TrackKey(10, 1)
    assert second.vectors[0].key == TrackKey(10, 2)
    assert first.input_hash != second.input_hash
    assert first.semantic_hash != second.semantic_hash
    assert first.vectors[0].predicted_domain.state is DomainState.NO_INTERSECTION
    assert first.vectors[0].predicted_domain.tdv_s is None
    assert first.vectors[0].claim_completeness == "FULL"


def test_missing_uncertainty_is_unknown_and_tangent_horizon_has_no_domain_entry() -> None:
    missing_covariance = ThreatTargetObservation(
        key=TrackKey(11, 1),
        state_enu=np.array([500.0, 0.0, 0.0, 0.0]),
        covariance=None,
        length_m=30.0,
        width_m=7.0,
        observed_at_s=10.0,
        generated_at_s=10.0,
        health="UPDATED",
        source="independent-fixture",
    )
    tangent = replace(
        missing_covariance,
        key=TrackKey(12, 1),
        state_enu=np.array([300.0, 0.0, 0.0, 0.0]),
        covariance=np.zeros((4, 4)),
    )
    prediction = ThreatPrediction(
        key=tangent.key,
        times_s=np.array([0.0, 20.0]),
        states_enu=np.array([[300.0, 0.0, 0.0, 0.0], [300.0, 0.0, 0.0, 0.0]]),
        basis=PredictionBasis.EXPLICIT_TRAJECTORY,
        model="independent-linear-fixture",
    )
    request = ThreatAssessmentRequest(
        epoch="run-1",
        sequence=7,
        sim_time_s=10.0,
        ownship=replace(_ownship(), velocity_ne_mps=np.array([0.0, 0.0])),
        targets=(missing_covariance, tangent),
        predictions=(prediction,),
        profile=_profile(),
    )

    vectors = {vector.key: vector for vector in ThreatAssessment().evaluate(request).vectors}

    assert vectors[missing_covariance.key].current_domain.state is DomainState.UNKNOWN
    assert (
        vectors[missing_covariance.key].current_domain.unavailable_reason
        is ThreatUnavailableReason.UNCERTAINTY_UNAVAILABLE
    )
    assert vectors[tangent.key].predicted_domain.state is DomainState.TANGENT
    assert vectors[tangent.key].predicted_domain.tdv_s is None
