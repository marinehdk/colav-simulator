from __future__ import annotations

from dataclasses import replace

import numpy as np

from colav_simulator.core.colav.mid_mpc_acceptance import (
    AcceptanceMode,
    AcceptanceOutcome,
    AcceptanceProfile,
    AcceptanceRequest,
    AuthorityEvidence,
    AuthorityTarget,
    CandidateEvidence,
    ExecutionEvidence,
    ExecutionTarget,
    MidMpcPlanAcceptance,
    NumericalEvidence,
    PlanAcceptancePolicy,
    PlantCapabilityEvidence,
    PriorEvidence,
)
from colav_simulator.core.colav.prediction_evidence import EvidenceTrackKey, PredictionPhaseEvidence
from colav_simulator.core.tracking.trackers import TrackKey


def _numerical(*, raw_x: np.ndarray | None = None) -> NumericalEvidence:
    values = np.array([0.0, 0.0, 4.0, 4.0, 0.0, 0.0]) if raw_x is None else raw_x
    return NumericalEvidence(
        normalized_status="Converged",
        return_status="Solve_Succeeded",
        objective_total=12.0,
        raw_f=12.0,
        raw_x=values,
        raw_g=np.zeros(4),
        lbx=np.array([-1.0, -1.0, 0.0, 0.0, 0.0, 0.0]),
        ubx=np.array([1.0, 1.0, 8.0, 8.0, 0.0, 0.0]),
        lbg=np.full(4, -1.0),
        ubg=np.full(4, 1.0),
        heading_count=2,
        speed_count=2,
        cpa_row_indices=(),
        strict_slack_bounds=True,
        cpa_slack=0.0,
        direction_slack=0.0,
        preparation_profile="COLAV_STRICT",
        preparation_hash="p" * 64,
        solver_hash="s" * 64,
        preparation_parent_problem_hash="q" * 64,
        solver_parent_preparation_hash="p" * 64,
    )


def _request(
    *,
    north: np.ndarray | None = None,
    east: np.ndarray | None = None,
    course: np.ndarray | None = None,
    targets: tuple[ExecutionTarget, ...] = (),
    authority_targets: tuple[AuthorityTarget, ...] = (),
    numerical: NumericalEvidence | None = None,
    profile: AcceptanceProfile = AcceptanceProfile.COLAV_STRICT,
    capability: PlantCapabilityEvidence | None = None,
    phase_evidence: PredictionPhaseEvidence | None = None,
) -> AcceptanceRequest:
    times = np.array([0.0, 15.0, 30.0])
    if authority_targets and not targets:
        targets = tuple(
            ExecutionTarget(
                key=authority.key,
                length_m=10.0,
                width_m=4.0,
                north_m=np.full(3, 1000.0),
                east_m=np.full(3, 500.0),
                uncertainty_m=np.zeros(3),
            )
            for authority in authority_targets
        )
    if targets and not authority_targets:
        authority_targets = tuple(
            AuthorityTarget(
                key=target.key,
                encounter="CLEAR",
                role="NONE",
                risk="CLEAR",
                commitment="NONE",
                passing_side="NONE",
                baseline_course_rad=None,
                required_course_change_rad=0.0,
                action_achieved=False,
                route_recovery_allowed=False,
                reachability_verified=True,
            )
            for target in targets
        )
    if phase_evidence is None:
        maneuver_targets = tuple(
            target
            for target in authority_targets
            if target.role in {"GIVE_WAY", "OVERTAKING"} and target.risk in {"CANDIDATE", "ACTIVE", "PAST_CLEAR"}
        )
        phase_evidence = PredictionPhaseEvidence(
            times_s=times,
            phases=("ALTER", "PASS", "PASS") if maneuver_targets else ("MISSION",) * 3,
            mission_bearing_rad=0.0,
            avoidance_corridor_bearing_rad=0.0,
            recovery_from_k=None,
            target_keys=tuple(EvidenceTrackKey(target.key.target_id, target.key.generation) for target in maneuver_targets),
            solver_consumed=True,
        )
    return AcceptanceRequest(
        schema_version="colav.mid_mpc.acceptance.request@1",
        candidate=CandidateEvidence(
            profile=profile,
            times_s=times,
            north_m=np.array([0.0, 60.0, 120.0]) if north is None else north,
            east_m=np.zeros(3) if east is None else east,
            course_rad=np.zeros(3) if course is None else course,
            speed_mps=np.full(3, 4.0),
            numerical=_numerical() if numerical is None else numerical,
            parent_problem_hash="q" * 64,
            phase_evidence=phase_evidence,
        ),
        authority=AuthorityEvidence(
            epoch="test-1",
            sequence=1,
            sim_time_s=0.0,
            profile_hash="l" * 64,
            targets=authority_targets,
        ),
        execution=ExecutionEvidence(
            sim_time_s=0.0,
            ownship_length_m=15.0,
            ownship_width_m=4.0,
            targets=targets,
            capability=capability
            or PlantCapabilityEvidence(
                plant="Viknes",
                controller="FLSC",
                valid_at_s=0.0,
                heading_window_rad=np.deg2rad(45.0),
                speed_bounds_mps=(0.0, 8.0),
                rot_max_rad_s=np.deg2rad(3.0),
                accel_max_mps2=0.3,
                decel_max_mps2=0.3,
                exact_tuple="single-encounter:viknes:flsc",
            ),
            tracker_id="god",
        ),
        prior=PriorEvidence(mode=AcceptanceMode.FRESH_CANDIDATE),
        policy=PlanAcceptancePolicy(
            control_intervals=2,
            state_samples=3,
            horizon_dt_s=15.0,
            hard_hull_clearance_m=50.0,
            max_relevant_targets=16,
            allowed_capability_tuples=("single-encounter:viknes:flsc",),
        ),
    )


def test_acceptance_is_deterministic_and_accepts_strict_route_candidate() -> None:
    checker = MidMpcPlanAcceptance()
    request = _request()

    first = checker.evaluate(request)
    second = checker.evaluate(request)

    assert first.accepted is True
    assert first.aggregate is AcceptanceOutcome.PASS
    assert first.request_hash == second.request_hash
    assert first.acceptance_hash == second.acceptance_hash
    assert [layer.layer.value for layer in first.layers] == [
        "integrity",
        "numerical",
        "safety",
        "COLREG",
        "trackability",
        "quality",
        "evidence",
    ]


def test_target_permutation_preserves_semantic_hash() -> None:
    targets = tuple(
        ExecutionTarget(
            key=TrackKey(target_id, 1),
            length_m=10.0,
            width_m=4.0,
            north_m=np.full(3, north_m),
            east_m=np.full(3, 500.0),
            uncertainty_m=np.zeros(3),
        )
        for target_id, north_m in ((1, 1000.0), (2, 1500.0))
    )

    first = MidMpcPlanAcceptance().evaluate(_request(targets=targets))
    second = MidMpcPlanAcceptance().evaluate(_request(targets=tuple(reversed(targets))))

    assert first.request_hash == second.request_hash
    assert first.acceptance_hash == second.acceptance_hash


def test_safety_checks_every_execution_track_even_when_not_selected_by_solver() -> None:
    target = ExecutionTarget(
        key=TrackKey(9, 1),
        length_m=10.0,
        width_m=4.0,
        north_m=np.array([0.0, 60.0, 120.0]),
        east_m=np.zeros(3),
        uncertainty_m=np.zeros(3),
    )

    result = MidMpcPlanAcceptance().evaluate(_request(targets=(target,)))

    assert result.accepted is False
    assert "SAFETY_SWEPT_CLEARANCE" in {finding.code for finding in result.findings}


def test_stand_on_safety_is_mandatory_through_action_deadline_then_forecast() -> None:
    key = TrackKey(8, 1)
    target = ExecutionTarget(
        key=key,
        length_m=10.0,
        width_m=4.0,
        north_m=np.array([1000.0, 1000.0, 120.0]),
        east_m=np.zeros(3),
        uncertainty_m=np.zeros(3),
    )
    authority = AuthorityTarget(
        key=key,
        encounter="CROSSING",
        role="STAND_ON",
        risk="ACTIVE",
        commitment="NONE",
        passing_side="NONE",
        baseline_course_rad=0.0,
        required_course_change_rad=0.0,
        action_achieved=False,
        route_recovery_allowed=False,
        reachability_verified=True,
        action_start_deadline_s=15.0,
        rule17="STAND_ON",
    )

    held = MidMpcPlanAcceptance().evaluate(_request(targets=(target,), authority_targets=(authority,)))
    may_act = MidMpcPlanAcceptance().evaluate(
        _request(targets=(target,), authority_targets=(replace(authority, rule17="MAY_ACT"),))
    )

    assert held.accepted is True
    assert "SAFETY_RULE17_FUTURE_CONFLICT" in {finding.code for finding in held.findings}
    assert may_act.accepted is False
    assert "SAFETY_SWEPT_CLEARANCE" in {finding.code for finding in may_act.findings}


def test_stand_on_candidate_rejects_course_drift_before_rule17() -> None:
    authority = AuthorityTarget(
        key=TrackKey(7, 1),
        encounter="CROSSING",
        role="STAND_ON",
        risk="ACTIVE",
        commitment="NONE",
        passing_side="NONE",
        baseline_course_rad=0.0,
        required_course_change_rad=0.0,
        action_achieved=False,
        route_recovery_allowed=False,
        reachability_verified=True,
    )

    result = MidMpcPlanAcceptance().evaluate(
        _request(course=np.deg2rad(np.array([0.0, 0.0, 20.0])), authority_targets=(authority,))
    )

    assert result.accepted is False
    assert "COLREG_STAND_ON_DRIFT" in {finding.code for finding in result.findings}


def test_original_bound_violation_rejects_even_with_success_status() -> None:
    numerical = _numerical(raw_x=np.array([1.01, 0.0, 4.0, 4.0, 0.0, 0.0]))

    result = MidMpcPlanAcceptance().evaluate(_request(numerical=numerical))

    assert result.accepted is False
    assert result.aggregate is AcceptanceOutcome.FAIL
    assert "NUMERICAL_ORIGINAL_BOUNDS" in {finding.code for finding in result.findings}


def test_parent_hash_substitution_rejects_replay_chain() -> None:
    numerical = replace(_numerical(), solver_parent_preparation_hash="x" * 64)

    result = MidMpcPlanAcceptance().evaluate(_request(numerical=numerical))

    assert result.accepted is False
    assert "EVIDENCE_HASH_CHAIN" in {finding.code for finding in result.findings}


def test_native_ipopt_status_must_match_normalized_eligible_termination() -> None:
    numerical = replace(_numerical(), return_status="Infeasible_Problem_Detected")

    result = MidMpcPlanAcceptance().evaluate(_request(numerical=numerical))

    assert result.accepted is False
    assert "NUMERICAL_TERMINATION_MISMATCH" in {finding.code for finding in result.findings}


def test_trackability_tolerance_matches_solver_primal_tolerance() -> None:
    course = np.array([0.0, np.deg2rad(45.0) + 5.0e-4, np.deg2rad(45.0) + 5.0e-4])

    result = MidMpcPlanAcceptance().evaluate(_request(course=course))

    assert "TRACKABILITY_ROT" not in {finding.code for finding in result.findings}


def test_swept_hull_clearance_rejects_between_knot_collision() -> None:
    key = TrackKey(7, 1)
    target = ExecutionTarget(
        key=key,
        length_m=10.0,
        width_m=4.0,
        north_m=np.array([30.0, 30.0, 30.0]),
        east_m=np.array([-100.0, 100.0, 300.0]),
        uncertainty_m=np.zeros(3),
    )

    result = MidMpcPlanAcceptance().evaluate(_request(targets=(target,)))

    assert result.accepted is False
    witness = result.target_safety[0]
    assert witness.key == key
    assert witness.interval_index == 0
    assert witness.clearance_lower_bound_m < 0.0
    assert "SAFETY_SWEPT_CLEARANCE" in {finding.code for finding in result.findings}


def test_locked_starboard_commitment_rejects_port_candidate() -> None:
    key = TrackKey(3, 1)
    authority = AuthorityTarget(
        key=key,
        encounter="OVERTAKING",
        role="OVERTAKING",
        risk="ACTIVE",
        commitment="COMMITTED",
        passing_side="STARBOARD",
        baseline_course_rad=0.0,
        required_course_change_rad=np.deg2rad(5.0),
        action_achieved=False,
        route_recovery_allowed=False,
        reachability_verified=True,
        committed_at_s=0.0,
        action_start_deadline_s=15.0,
        action_achievement_deadline_s=30.0,
        actual_course_change_rad=0.0,
    )

    rejected = MidMpcPlanAcceptance().evaluate(
        _request(authority_targets=(authority,), course=-np.deg2rad(np.array([0.0, 6.0, 6.0])))
    )
    accepted = MidMpcPlanAcceptance().evaluate(
        _request(authority_targets=(authority,), course=np.deg2rad(np.array([0.0, 6.0, 6.0])))
    )

    assert rejected.accepted is False
    assert "COLREG_LOCKED_SIDE" in {finding.code for finding in rejected.findings}
    assert accepted.accepted is True


def test_overdue_give_way_action_accepts_first_executable_recovery_command() -> None:
    authority = AuthorityTarget(
        key=TrackKey(34, 1),
        encounter="CROSSING",
        role="GIVE_WAY",
        risk="ACTIVE",
        commitment="COMMITTED",
        passing_side="STARBOARD",
        baseline_course_rad=0.0,
        required_course_change_rad=np.deg2rad(5.0),
        action_achieved=False,
        route_recovery_allowed=False,
        reachability_verified=True,
        committed_at_s=0.0,
        action_start_deadline_s=5.0,
        action_achievement_deadline_s=10.0,
        actual_course_change_rad=np.deg2rad(2.0),
    )
    request = _request(
        authority_targets=(authority,),
        course=np.deg2rad(np.array([2.0, 6.0, 6.0])),
    )
    request = replace(
        request,
        authority=replace(request.authority, sim_time_s=20.0),
        execution=replace(
            request.execution,
            sim_time_s=20.0,
            capability=replace(request.execution.capability, valid_at_s=20.0),
        ),
    )

    result = MidMpcPlanAcceptance().evaluate(request)
    codes = {finding.code for finding in result.findings}

    assert result.accepted is True
    assert "COLREG_ACTION_DEADLINE" not in codes
    assert "COLREG_ACTION_DEADLINE_MISSED" in codes


def test_locked_starboard_candidate_is_checked_before_commitment() -> None:
    authority = AuthorityTarget(
        key=TrackKey(33, 1),
        encounter="OVERTAKING",
        role="OVERTAKING",
        risk="CANDIDATE",
        commitment="NONE",
        passing_side="STARBOARD",
        baseline_course_rad=0.0,
        required_course_change_rad=np.deg2rad(5.0),
        action_achieved=False,
        route_recovery_allowed=False,
        reachability_verified=True,
    )

    result = MidMpcPlanAcceptance().evaluate(
        _request(authority_targets=(authority,), course=-np.deg2rad(np.array([0.0, 6.0, 6.0])))
    )

    assert result.accepted is False
    assert "COLREG_LOCKED_SIDE" in {finding.code for finding in result.findings}


def test_held_candidate_checks_only_currently_executable_course() -> None:
    authority = AuthorityTarget(
        key=TrackKey(33, 1),
        encounter="OVERTAKING",
        role="OVERTAKING",
        risk="CANDIDATE",
        commitment="NONE",
        passing_side="STARBOARD",
        baseline_course_rad=0.0,
        required_course_change_rad=np.deg2rad(5.0),
        action_achieved=False,
        route_recovery_allowed=False,
        reachability_verified=True,
    )
    request = _request(
        authority_targets=(authority,),
        course=-np.deg2rad(np.array([0.0, 0.1, 6.0])),
    )
    request = replace(
        request,
        prior=PriorEvidence(
            mode=AcceptanceMode.HELD_ACCEPTED_PLAN,
            previous_acceptance_hash="a" * 64,
            previous_course_rad=np.zeros(3),
        ),
    )

    result = MidMpcPlanAcceptance().evaluate(request)

    assert result.accepted is True
    assert "COLREG_LOCKED_SIDE" not in {finding.code for finding in result.findings}


def test_locked_side_ignores_solver_scale_course_noise() -> None:
    authority = AuthorityTarget(
        key=TrackKey(4, 1),
        encounter="CROSSING",
        role="GIVE_WAY",
        risk="CANDIDATE",
        commitment="NONE",
        passing_side="STARBOARD",
        baseline_course_rad=0.0,
        required_course_change_rad=np.deg2rad(5.0),
        action_achieved=False,
        route_recovery_allowed=False,
        reachability_verified=True,
        committed_at_s=None,
        action_start_deadline_s=None,
        action_achievement_deadline_s=None,
        actual_course_change_rad=None,
    )

    result = MidMpcPlanAcceptance().evaluate(
        _request(
            authority_targets=(authority,),
            course=np.array([0.0, -1.0e-4, 1.0e-4]),
        )
    )

    assert "COLREG_LOCKED_SIDE" not in {finding.code for finding in result.findings}


def test_achieved_commitment_allows_route_recovery_against_locked_side() -> None:
    authority = AuthorityTarget(
        key=TrackKey(4, 1),
        encounter="HEAD_ON",
        role="GIVE_WAY",
        risk="PAST_CLEAR",
        commitment="COMMITTED",
        passing_side="STARBOARD",
        baseline_course_rad=0.0,
        required_course_change_rad=np.deg2rad(5.0),
        action_achieved=True,
        route_recovery_allowed=True,
        reachability_verified=True,
        committed_at_s=0.0,
        action_start_deadline_s=15.0,
        action_achievement_deadline_s=30.0,
        actual_course_change_rad=np.deg2rad(5.0),
    )

    result = MidMpcPlanAcceptance().evaluate(
        _request(authority_targets=(authority,), course=-np.deg2rad(np.array([0.0, 2.0, 6.0])))
    )

    assert result.accepted is True


def test_active_prediction_requires_avoidance_peak_and_post_cpa_recovery() -> None:
    key = TrackKey(41, 1)
    authority = AuthorityTarget(
        key=key,
        encounter="OVERTAKING",
        role="GIVE_WAY",
        risk="ACTIVE",
        commitment="COMMITTED",
        passing_side="STARBOARD",
        baseline_course_rad=0.0,
        required_course_change_rad=np.deg2rad(5.0),
        action_achieved=False,
        route_recovery_allowed=False,
        reachability_verified=True,
        committed_at_s=0.0,
        action_start_deadline_s=15.0,
        action_achievement_deadline_s=15.0,
        actual_course_change_rad=0.0,
    )
    target = ExecutionTarget(
        key=key,
        length_m=10.0,
        width_m=4.0,
        north_m=np.array([1000.0, 60.0, 1000.0]),
        east_m=np.full(3, 500.0),
        uncertainty_m=np.zeros(3),
    )
    phase_evidence = PredictionPhaseEvidence(
        times_s=np.array([0.0, 15.0, 30.0]),
        phases=("ALTER", "PASS", "RECOVER"),
        mission_bearing_rad=0.0,
        avoidance_corridor_bearing_rad=np.deg2rad(6.0),
        recovery_from_k=2,
        target_keys=(EvidenceTrackKey(41, 1),),
        solver_consumed=True,
    )

    complete = MidMpcPlanAcceptance().evaluate(
        _request(
            targets=(target,),
            authority_targets=(authority,),
            course=np.deg2rad(np.array([0.0, 6.0, 0.0])),
            phase_evidence=phase_evidence,
        )
    )
    straight_request = replace(
        _request(
            targets=(target,),
            authority_targets=(authority,),
            course=np.zeros(3),
            phase_evidence=phase_evidence,
        ),
        prior=PriorEvidence(
            mode=AcceptanceMode.FRESH_CANDIDATE,
            previous_acceptance_hash="b" * 64,
            previous_course_rad=np.zeros(3),
        ),
    )
    straight = MidMpcPlanAcceptance().evaluate(straight_request)

    assert complete.accepted is True
    assert "QUALITY_PHASE_COMPLETE" in {finding.code for finding in complete.findings}
    assert straight.accepted is False
    assert "QUALITY_AVOIDANCE_PEAK" in {finding.code for finding in straight.findings}


def test_rule17_may_act_future_cpa_remains_advisory() -> None:
    key = TrackKey(46, 1)
    authority = AuthorityTarget(
        key=key,
        encounter="CROSSING",
        role="STAND_ON",
        risk="ACTIVE",
        commitment="COMMITTED",
        passing_side="STARBOARD",
        baseline_course_rad=0.0,
        required_course_change_rad=0.0,
        action_achieved=True,
        route_recovery_allowed=False,
        reachability_verified=True,
        committed_at_s=0.0,
        action_start_deadline_s=15.0,
        action_achievement_deadline_s=30.0,
        actual_course_change_rad=0.0,
        rule17="MAY_ACT",
    )
    target = ExecutionTarget(
        key=key,
        length_m=10.0,
        width_m=4.0,
        north_m=np.array([1000.0, 500.0, 200.0]),
        east_m=np.full(3, 500.0),
        uncertainty_m=np.zeros(3),
    )
    phase_evidence = PredictionPhaseEvidence(
        times_s=np.array([0.0, 15.0, 30.0]),
        phases=("PASS", "RECOVER", "RECOVER"),
        mission_bearing_rad=0.0,
        avoidance_corridor_bearing_rad=np.deg2rad(6.0),
        recovery_from_k=1,
        target_keys=(EvidenceTrackKey(46, 1),),
        solver_consumed=True,
    )

    result = MidMpcPlanAcceptance().evaluate(
        _request(
            targets=(target,),
            authority_targets=(authority,),
            course=np.deg2rad(np.array([6.0, 2.0, 0.0])),
            phase_evidence=phase_evidence,
        )
    )

    assert result.accepted is True
    assert "QUALITY_RULE17_CPA_PENDING" in {finding.code for finding in result.findings}


def test_recovery_suffix_may_cross_locked_side_only_after_cpa() -> None:
    key = TrackKey(42, 1)
    authority = AuthorityTarget(
        key=key,
        encounter="OVERTAKING",
        role="OVERTAKING",
        risk="ACTIVE",
        commitment="COMMITTED",
        passing_side="STARBOARD",
        baseline_course_rad=0.0,
        required_course_change_rad=np.deg2rad(5.0),
        action_achieved=False,
        route_recovery_allowed=False,
        reachability_verified=True,
        committed_at_s=0.0,
        action_start_deadline_s=15.0,
        action_achievement_deadline_s=15.0,
        actual_course_change_rad=0.0,
    )
    target = ExecutionTarget(
        key=key,
        length_m=10.0,
        width_m=4.0,
        north_m=np.array([1000.0, 60.0, 1000.0]),
        east_m=np.full(3, 500.0),
        uncertainty_m=np.zeros(3),
    )
    phase_evidence = PredictionPhaseEvidence(
        times_s=np.array([0.0, 15.0, 30.0]),
        phases=("ALTER", "PASS", "RECOVER"),
        mission_bearing_rad=np.deg2rad(-1.0),
        avoidance_corridor_bearing_rad=np.deg2rad(6.0),
        recovery_from_k=2,
        target_keys=(EvidenceTrackKey(42, 1),),
        solver_consumed=True,
    )

    result = MidMpcPlanAcceptance().evaluate(
        _request(
            targets=(target,),
            authority_targets=(authority,),
            course=np.deg2rad(np.array([0.0, 6.0, -1.0])),
            phase_evidence=phase_evidence,
        )
    )

    assert result.accepted is True
    assert "COLREG_LOCKED_SIDE" not in {finding.code for finding in result.findings}


def test_recovery_quality_accepts_solver_anticipation_after_cpa() -> None:
    key = TrackKey(44, 1)
    authority = AuthorityTarget(
        key=key,
        encounter="OVERTAKING",
        role="OVERTAKING",
        risk="ACTIVE",
        commitment="COMMITTED",
        passing_side="PORT",
        baseline_course_rad=np.deg2rad(10.0),
        required_course_change_rad=np.deg2rad(5.0),
        action_achieved=True,
        route_recovery_allowed=False,
        reachability_verified=True,
        committed_at_s=0.0,
        action_start_deadline_s=15.0,
        action_achievement_deadline_s=30.0,
        actual_course_change_rad=np.deg2rad(6.0),
    )
    target = ExecutionTarget(
        key=key,
        length_m=10.0,
        width_m=4.0,
        north_m=np.array([500.0, 1000.0, 1500.0]),
        east_m=np.full(3, 500.0),
        uncertainty_m=np.zeros(3),
    )
    phase_evidence = PredictionPhaseEvidence(
        times_s=np.array([0.0, 15.0, 30.0]),
        phases=("PASS", "PASS", "RECOVER"),
        mission_bearing_rad=0.0,
        avoidance_corridor_bearing_rad=np.deg2rad(10.0),
        recovery_from_k=2,
        target_keys=(EvidenceTrackKey(44, 1),),
        solver_consumed=True,
    )

    result = MidMpcPlanAcceptance().evaluate(
        _request(
            targets=(target,),
            authority_targets=(authority,),
            course=np.deg2rad(np.array([10.0, 0.0, 0.0])),
            phase_evidence=phase_evidence,
        )
    )

    assert result.accepted is True
    assert "QUALITY_PHASE_COMPLETE" in {finding.code for finding in result.findings}


def test_recovery_uses_released_encounter_cpa_not_later_safe_reapproach() -> None:
    key = TrackKey(45, 1)
    authority = AuthorityTarget(
        key=key,
        encounter="OVERTAKING",
        role="OVERTAKING",
        risk="ACTIVE",
        commitment="COMMITTED",
        passing_side="STARBOARD",
        baseline_course_rad=0.0,
        required_course_change_rad=np.deg2rad(5.0),
        action_achieved=True,
        route_recovery_allowed=False,
        reachability_verified=True,
        committed_at_s=0.0,
        action_start_deadline_s=15.0,
        action_achievement_deadline_s=30.0,
        actual_course_change_rad=np.deg2rad(6.0),
    )
    base = _request(authority_targets=(authority,))
    times = np.arange(5, dtype=float) * 15.0
    own_north = np.arange(5, dtype=float) * 60.0
    separation = np.array([300.0, 200.0, 400.0, 500.0, 190.0])
    target = ExecutionTarget(
        key=key,
        length_m=10.0,
        width_m=4.0,
        north_m=own_north + separation,
        east_m=np.zeros(5),
        uncertainty_m=np.zeros(5),
    )
    phase_evidence = PredictionPhaseEvidence(
        times_s=times,
        phases=("PASS", "PASS", "PASS", "RECOVER", "RECOVER"),
        mission_bearing_rad=0.0,
        avoidance_corridor_bearing_rad=np.deg2rad(10.0),
        recovery_from_k=3,
        target_keys=(EvidenceTrackKey(45, 1),),
        solver_consumed=True,
    )
    request = replace(
        base,
        candidate=replace(
            base.candidate,
            times_s=times,
            north_m=own_north,
            east_m=np.zeros(5),
            course_rad=np.deg2rad(np.array([10.0, 10.0, 10.0, 5.0, 0.0])),
            speed_mps=np.full(5, 4.0),
            numerical=replace(
                base.candidate.numerical,
                raw_x=np.concatenate((np.deg2rad([10.0, 10.0, 5.0, 0.0]), np.full(4, 4.0), [0.0, 0.0])),
                lbx=np.array([-1.0] * 4 + [0.0] * 4 + [0.0, 0.0]),
                ubx=np.array([1.0] * 4 + [8.0] * 4 + [0.0, 0.0]),
                heading_count=4,
                speed_count=4,
            ),
            phase_evidence=phase_evidence,
        ),
        execution=replace(base.execution, targets=(target,)),
        policy=replace(base.policy, control_intervals=4, state_samples=5),
    )

    result = MidMpcPlanAcceptance().evaluate(request)

    assert result.accepted is True
    quality = next(finding for finding in result.findings if finding.code == "QUALITY_PHASE_COMPLETE")
    assert quality.witness["target_45_cpa_k"] == 1


def test_recovery_may_start_before_a_later_advisory_clear_reapproach() -> None:
    key = TrackKey(47, 1)
    authority = AuthorityTarget(
        key=key,
        encounter="OVERTAKING",
        role="OVERTAKING",
        risk="ACTIVE",
        commitment="COMMITTED",
        passing_side="STARBOARD",
        baseline_course_rad=0.0,
        required_course_change_rad=np.deg2rad(5.0),
        action_achieved=True,
        route_recovery_allowed=False,
        reachability_verified=True,
        committed_at_s=0.0,
        action_start_deadline_s=15.0,
        action_achievement_deadline_s=30.0,
        actual_course_change_rad=np.deg2rad(6.0),
    )
    base = _request(authority_targets=(authority,))
    times = np.arange(5, dtype=float) * 15.0
    own_north = np.arange(5, dtype=float) * 60.0
    separation = np.array([500.0, 300.0, 200.0, 300.0, 500.0])
    target = ExecutionTarget(
        key=key,
        length_m=10.0,
        width_m=4.0,
        north_m=own_north + separation,
        east_m=np.zeros(5),
        uncertainty_m=np.zeros(5),
    )
    phase_evidence = PredictionPhaseEvidence(
        times_s=times,
        phases=("RECOVER",) * 5,
        mission_bearing_rad=0.0,
        avoidance_corridor_bearing_rad=np.deg2rad(10.0),
        recovery_from_k=0,
        target_keys=(EvidenceTrackKey(47, 1),),
        solver_consumed=True,
    )
    request = replace(
        base,
        candidate=replace(
            base.candidate,
            times_s=times,
            north_m=own_north,
            east_m=np.zeros(5),
            course_rad=np.deg2rad(np.array([6.0, 4.0, 2.0, 1.0, 0.0])),
            speed_mps=np.full(5, 4.0),
            numerical=replace(
                base.candidate.numerical,
                raw_x=np.concatenate((np.deg2rad([6.0, 4.0, 2.0, 1.0]), np.full(4, 4.0), [0.0, 0.0])),
                lbx=np.array([-1.0] * 4 + [0.0] * 4 + [0.0, 0.0]),
                ubx=np.array([1.0] * 4 + [8.0] * 4 + [0.0, 0.0]),
                heading_count=4,
                speed_count=4,
            ),
            phase_evidence=phase_evidence,
        ),
        execution=replace(base.execution, targets=(target,)),
        policy=replace(base.policy, control_intervals=4, state_samples=5),
    )

    result = MidMpcPlanAcceptance().evaluate(request)
    advisory_conflict = MidMpcPlanAcceptance().evaluate(
        replace(
            request,
            execution=replace(
                request.execution,
                targets=(
                    replace(
                        target,
                        north_m=own_north + np.array([500.0, 200.0, 70.0, 200.0, 500.0]),
                    ),
                ),
            ),
        )
    )

    assert result.accepted is True
    assert "QUALITY_CPA_RELEASE" not in {finding.code for finding in result.findings}
    assert advisory_conflict.accepted is False
    assert "QUALITY_CPA_RELEASE" in {finding.code for finding in advisory_conflict.findings}


def test_held_accepted_recovery_suffix_keeps_prior_phase_proof() -> None:
    key = TrackKey(43, 1)
    authority = AuthorityTarget(
        key=key,
        encounter="HEAD_ON",
        role="GIVE_WAY",
        risk="PAST_CLEAR",
        commitment="COMMITTED",
        passing_side="STARBOARD",
        baseline_course_rad=0.0,
        required_course_change_rad=np.deg2rad(5.0),
        action_achieved=True,
        route_recovery_allowed=True,
        reachability_verified=True,
        committed_at_s=0.0,
        action_start_deadline_s=15.0,
        action_achievement_deadline_s=30.0,
        actual_course_change_rad=np.deg2rad(6.0),
    )
    phase_evidence = PredictionPhaseEvidence(
        times_s=np.array([0.0, 15.0, 30.0]),
        phases=("RECOVER", "RECOVER", "RECOVER"),
        mission_bearing_rad=0.0,
        avoidance_corridor_bearing_rad=np.deg2rad(6.0),
        recovery_from_k=0,
        target_keys=(EvidenceTrackKey(43, 1),),
        solver_consumed=True,
    )
    request = _request(authority_targets=(authority,), phase_evidence=phase_evidence)
    request = replace(
        request,
        prior=PriorEvidence(
            mode=AcceptanceMode.HELD_ACCEPTED_PLAN,
            previous_acceptance_hash="a" * 64,
            previous_course_rad=np.deg2rad(np.array([6.0, 4.0, 2.0])),
        ),
    )

    result = MidMpcPlanAcceptance().evaluate(request)

    assert result.accepted is True
    assert "QUALITY_HELD_PHASE_PROOF" in {finding.code for finding in result.findings}


def test_capability_is_bound_to_exact_runtime_tuple() -> None:
    mismatched = PlantCapabilityEvidence(
        plant="KinematicCSOG",
        controller="PassThroughCS",
        valid_at_s=0.0,
        heading_window_rad=np.deg2rad(45.0),
        speed_bounds_mps=(0.0, 8.0),
        rot_max_rad_s=np.deg2rad(3.0),
        accel_max_mps2=0.3,
        decel_max_mps2=0.3,
        exact_tuple="multiship:kinematic_csog:pass_through_cs",
    )

    rejected = MidMpcPlanAcceptance().evaluate(_request(capability=mismatched))
    multiship = replace(
        _request(capability=mismatched),
        policy=replace(
            _request().policy,
            allowed_capability_tuples=("multiship:kinematic_csog:pass_through_cs",),
        ),
    )

    assert rejected.accepted is False
    assert "TRACKABILITY_CAPABILITY_TUPLE" in {finding.code for finding in rejected.findings}
    assert MidMpcPlanAcceptance().evaluate(multiship).accepted is True


def test_mass_parity_is_diagnostic_only() -> None:
    result = MidMpcPlanAcceptance().evaluate(_request(profile=AcceptanceProfile.MASS_PARITY))

    assert result.accepted is False
    assert result.aggregate is AcceptanceOutcome.NOT_EVALUATED
    assert "PROFILE_DIAGNOSTIC_ONLY" in {finding.code for finding in result.findings}


def test_horizon_end_cpa_downgrades_recovery_suffix_to_pending() -> None:
    key = TrackKey(51, 1)
    authority = AuthorityTarget(
        key=key,
        encounter="OVERTAKING",
        role="OVERTAKING",
        risk="ACTIVE",
        commitment="COMMITTED",
        passing_side="STARBOARD",
        baseline_course_rad=0.0,
        required_course_change_rad=np.deg2rad(5.0),
        action_achieved=True,
        route_recovery_allowed=False,
        reachability_verified=True,
        committed_at_s=0.0,
        action_start_deadline_s=15.0,
        action_achievement_deadline_s=30.0,
        actual_course_change_rad=np.deg2rad(10.0),
    )
    base = _request(authority_targets=(authority,))
    times = np.arange(5, dtype=float) * 15.0
    own_north = np.arange(5, dtype=float) * 60.0
    separation = np.array([700.0, 600.0, 500.0, 400.0, 300.0])
    target = ExecutionTarget(
        key=key,
        length_m=10.0,
        width_m=4.0,
        north_m=own_north + separation,
        east_m=np.zeros(5),
        uncertainty_m=np.zeros(5),
    )
    phase_evidence = PredictionPhaseEvidence(
        times_s=times,
        phases=("ALTER", "PASS", "PASS", "RECOVER", "RECOVER"),
        mission_bearing_rad=0.0,
        avoidance_corridor_bearing_rad=np.deg2rad(10.0),
        recovery_from_k=3,
        target_keys=(EvidenceTrackKey(51, 1),),
        solver_consumed=True,
    )
    request = replace(
        base,
        candidate=replace(
            base.candidate,
            times_s=times,
            north_m=own_north,
            east_m=np.zeros(5),
            course_rad=np.deg2rad(np.array([10.0, 10.0, 10.0, 8.0, 8.0])),
            speed_mps=np.full(5, 4.0),
            numerical=replace(
                base.candidate.numerical,
                raw_x=np.concatenate((np.deg2rad([10.0, 10.0, 10.0, 8.0, 8.0]), np.full(5, 4.0), [0.0, 0.0])),
                lbx=np.array([-1.0] * 5 + [0.0] * 5 + [0.0, 0.0]),
                ubx=np.array([1.0] * 5 + [8.0] * 5 + [0.0, 0.0]),
                heading_count=5,
                speed_count=5,
            ),
            phase_evidence=phase_evidence,
        ),
        execution=replace(base.execution, targets=(target,)),
        policy=replace(base.policy, control_intervals=4, state_samples=5),
    )

    result = MidMpcPlanAcceptance().evaluate(request)

    assert result.accepted is True
    pending = next(finding for finding in result.findings if finding.code == "QUALITY_RECOVERY_PENDING")
    assert pending.outcome is AcceptanceOutcome.WARN
    assert pending.mandatory is False
    assert pending.witness["target_51_cpa_k"] == 4


def test_released_cpa_without_return_suffix_still_fails() -> None:
    key = TrackKey(52, 1)
    authority = AuthorityTarget(
        key=key,
        encounter="OVERTAKING",
        role="OVERTAKING",
        risk="ACTIVE",
        commitment="COMMITTED",
        passing_side="STARBOARD",
        baseline_course_rad=0.0,
        required_course_change_rad=np.deg2rad(5.0),
        action_achieved=True,
        route_recovery_allowed=False,
        reachability_verified=True,
        committed_at_s=0.0,
        action_start_deadline_s=15.0,
        action_achievement_deadline_s=30.0,
        actual_course_change_rad=np.deg2rad(10.0),
    )
    base = _request(authority_targets=(authority,))
    times = np.arange(5, dtype=float) * 15.0
    own_north = np.arange(5, dtype=float) * 60.0
    separation = np.array([500.0, 200.0, 400.0, 500.0, 600.0])
    target = ExecutionTarget(
        key=key,
        length_m=10.0,
        width_m=4.0,
        north_m=own_north + separation,
        east_m=np.zeros(5),
        uncertainty_m=np.zeros(5),
    )
    phase_evidence = PredictionPhaseEvidence(
        times_s=times,
        phases=("ALTER", "PASS", "PASS", "RECOVER", "RECOVER"),
        mission_bearing_rad=0.0,
        avoidance_corridor_bearing_rad=np.deg2rad(10.0),
        recovery_from_k=3,
        target_keys=(EvidenceTrackKey(52, 1),),
        solver_consumed=True,
    )
    request = replace(
        base,
        candidate=replace(
            base.candidate,
            times_s=times,
            north_m=own_north,
            east_m=np.zeros(5),
            course_rad=np.deg2rad(np.array([10.0, 5.0, 10.0, 8.0, 10.0])),
            speed_mps=np.full(5, 4.0),
            numerical=replace(
                base.candidate.numerical,
                raw_x=np.concatenate((np.deg2rad([10.0, 5.0, 10.0, 8.0, 10.0]), np.full(5, 4.0), [0.0, 0.0])),
                lbx=np.array([-1.0] * 5 + [0.0] * 5 + [0.0, 0.0]),
                ubx=np.array([1.0] * 5 + [8.0] * 5 + [0.0, 0.0]),
                heading_count=5,
                speed_count=5,
            ),
            phase_evidence=phase_evidence,
        ),
        execution=replace(base.execution, targets=(target,)),
        policy=replace(base.policy, control_intervals=4, state_samples=5),
    )

    result = MidMpcPlanAcceptance().evaluate(request)

    assert result.accepted is False
    assert "QUALITY_RECOVERY_SUFFIX" in {finding.code for finding in result.findings}
