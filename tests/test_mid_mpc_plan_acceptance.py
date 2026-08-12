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
) -> AcceptanceRequest:
    times = np.array([0.0, 15.0, 30.0])
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


def test_original_bound_violation_rejects_even_with_success_status() -> None:
    numerical = _numerical(raw_x=np.array([1.01, 0.0, 4.0, 4.0, 0.0, 0.0]))

    result = MidMpcPlanAcceptance().evaluate(_request(numerical=numerical))

    assert result.accepted is False
    assert result.aggregate is AcceptanceOutcome.FAIL
    assert "NUMERICAL_ORIGINAL_BOUNDS" in {finding.code for finding in result.findings}


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
