from __future__ import annotations

import numpy as np
import pytest

from colav_simulator.core.colav.rolling_plan import (
    PlanRevisionReason,
    RollingPlan,
    RollingPlanAssessment,
    RollingPlanIdentity,
)


def _identity(**changes: str) -> RollingPlanIdentity:
    values: dict[str, object] = {
        "route_hash": "route-a",
        "target_keys": ((1, 1),),
        "capability_hash": "capability-a",
        "authority_hash": "authority-a",
    }
    values.update(changes)
    return RollingPlanIdentity(**values)  # type: ignore[arg-type]


def _commit(plan: RollingPlan, recovery_at_s: float = 230.0) -> None:
    times = np.arange(81, dtype=float) * 5.0
    course = np.radians(40.0 + 0.05 * times)
    speed = np.full(81, 7.0)
    plan.commit(
        accepted_at_s=10.0,
        dt_s=5.0,
        north_m=7.0 * times,
        east_m=0.2 * times,
        course_rad=course,
        speed_mps=speed,
        identity=_identity(),
        passing_side="STARBOARD",
        recovery_at_s=recovery_at_s,
    )


def _assess_recovery(plan: RollingPlan, current_time_s: float, recovery_at_s: float) -> RollingPlanAssessment:
    """Assess one smooth on-plan candidate whose recovery moment differs."""
    reference = plan.reference(
        current_time_s=current_time_s,
        horizon_steps=80,
        dt_s=5.0,
        identity=_identity(),
        prior_plan_safe=True,
    )
    state_times = current_time_s + np.arange(81, dtype=float) * 5.0
    baseline_times = 10.0 + np.arange(81, dtype=float) * 5.0
    north = np.interp(state_times, baseline_times, 7.0 * np.arange(81) * 5.0)
    east = np.interp(state_times, baseline_times, 0.2 * np.arange(81) * 5.0)
    course = np.interp(state_times, baseline_times, np.radians(40.0 + 0.25 * np.arange(81)))
    return plan.assess(
        reference,
        north_m=north,
        east_m=east,
        course_rad=course,
        passing_side="STARBOARD",
        recovery_at_s=recovery_at_s,
        prior_plan_safe=True,
    )


def test_reference_aligns_accepted_plan_on_absolute_time_and_weights_three_bands() -> None:
    plan = RollingPlan()
    _commit(plan)

    reference = plan.reference(
        current_time_s=15.0,
        horizon_steps=80,
        dt_s=5.0,
        identity=_identity(),
        prior_plan_safe=True,
    )

    assert reference.active is True
    assert reference.revision_reason is PlanRevisionReason.CONTINUITY_PRESERVED
    assert reference.recovery_at_s == 230.0
    assert reference.overlap_intervals == 79
    assert np.degrees(reference.heading_reference_rad[0]) == pytest.approx(40.5)
    assert reference.objective_weight[:6] == (200.0,) * 6
    assert reference.objective_weight[6:24] == (120.0,) * 18
    assert reference.objective_weight[24:79] == (100.0,) * 55
    assert reference.objective_weight[-1] == 0.0


def test_completed_recovery_does_not_reject_a_later_mission_plan() -> None:
    plan = RollingPlan()
    _commit(plan)
    reference = plan.reference(
        current_time_s=240.0,
        horizon_steps=80,
        dt_s=5.0,
        identity=_identity(),
        prior_plan_safe=True,
    )
    state_times = 240.0 + np.arange(81, dtype=float) * 5.0
    baseline_times = 10.0 + np.arange(81, dtype=float) * 5.0
    north = np.interp(state_times, baseline_times, 7.0 * np.arange(81) * 5.0)
    east = np.interp(state_times, baseline_times, 0.2 * np.arange(81) * 5.0)
    course = np.interp(state_times, baseline_times, np.radians(40.0 + 0.25 * np.arange(81)))

    assessment = plan.assess(
        reference,
        north_m=north,
        east_m=east,
        course_rad=course,
        passing_side="STARBOARD",
        recovery_at_s=240.0,
        prior_plan_safe=True,
    )

    assert assessment.accepted is True
    assert assessment.revision_reason is PlanRevisionReason.CONTINUITY_PRESERVED
    assert assessment.recovery_time_drift_s == 0.0


def test_prefix_churn_is_rejected_while_tail_churn_remains_advisory() -> None:
    plan = RollingPlan()
    _commit(plan)
    reference = plan.reference(
        current_time_s=15.0,
        horizon_steps=80,
        dt_s=5.0,
        identity=_identity(),
        prior_plan_safe=True,
    )
    state_times = 15.0 + np.arange(81, dtype=float) * 5.0
    baseline_times = 10.0 + np.arange(81, dtype=float) * 5.0
    north = np.interp(state_times, baseline_times, 7.0 * np.arange(81) * 5.0)
    east = np.interp(state_times, baseline_times, 0.2 * np.arange(81) * 5.0)
    course = np.interp(state_times, baseline_times, np.radians(40.0 + 0.25 * np.arange(81)))
    tail = state_times > 135.0
    course[tail] += np.radians(25.0)
    north[tail] += 300.0

    advisory = plan.assess(
        reference,
        north_m=north,
        east_m=east,
        course_rad=course,
        passing_side="STARBOARD",
        recovery_at_s=230.0,
        prior_plan_safe=True,
    )

    assert advisory.accepted is True
    assert advisory.prefix.within_policy is True
    assert advisory.advisory.within_policy is False

    course[:7] += np.radians(12.0)
    rejected = plan.assess(
        reference,
        north_m=north,
        east_m=east,
        course_rad=course,
        passing_side="STARBOARD",
        recovery_at_s=230.0,
        prior_plan_safe=True,
    )

    assert rejected.accepted is False
    assert rejected.revision_reason is PlanRevisionReason.PREFIX_CONTINUITY_EXCEEDED
    assert rejected.prefix.heading_max_deg == pytest.approx(12.0)


@pytest.mark.parametrize(
    ("identity", "prior_safe", "reason"),
    [
        (_identity(route_hash="route-b"), True, PlanRevisionReason.MISSION_ROUTE_CHANGED),
        (
            RollingPlanIdentity("route-a", ((1, 2),), "capability-a", "authority-a"),
            True,
            PlanRevisionReason.TARGET_GENERATION_CHANGED,
        ),
        (_identity(capability_hash="capability-b"), True, PlanRevisionReason.CAPABILITY_CHANGED),
        (_identity(authority_hash="authority-b"), True, PlanRevisionReason.COLREG_AUTHORITY_CHANGED),
        (_identity(), False, PlanRevisionReason.PRIOR_PLAN_UNSAFE),
    ],
)
def test_invalidated_or_unsafe_baseline_authorizes_typed_revision(
    identity: RollingPlanIdentity,
    prior_safe: bool,
    reason: PlanRevisionReason,
) -> None:
    plan = RollingPlan()
    _commit(plan)

    reference = plan.reference(
        current_time_s=15.0,
        horizon_steps=80,
        dt_s=5.0,
        identity=identity,
        prior_plan_safe=prior_safe,
    )

    assert reference.active is False
    assert reference.revision_reason is reason
    assert set(reference.objective_weight) == {0.0}


def test_sustained_recovery_disagreement_rebaselines_after_policy_strikes() -> None:
    """L4-passing candidates that persistently disagree must not deadlock planning.

    Regression for the 2026-09-04 overtaking symptom: one committed plan kept
    rejecting every fresh candidate for 250 s because their (stable) recovery
    moments sat outside the 5 s band, and only a lucky COLREG authority change
    ended the freeze.
    """
    plan = RollingPlan()
    _commit(plan, recovery_at_s=230.0)

    for _ in range(2):
        assessment = _assess_recovery(plan, current_time_s=15.0, recovery_at_s=250.0)
        assert assessment.accepted is False
        assert assessment.revision_reason is PlanRevisionReason.RECOVERY_TIME_CHANGED

    rebaselined = _assess_recovery(plan, current_time_s=15.0, recovery_at_s=250.0)
    assert rebaselined.accepted is True
    assert rebaselined.revision_reason is PlanRevisionReason.CONTINUITY_REBASELINED
    assert rebaselined.recovery_time_drift_s == 20.0
    assert rebaselined.prefix.within_policy is True


def test_single_recovery_disagreement_stays_rejected_and_acceptance_rearms_strikes() -> None:
    plan = RollingPlan()
    _commit(plan, recovery_at_s=230.0)

    first = _assess_recovery(plan, current_time_s=15.0, recovery_at_s=250.0)
    assert first.accepted is False
    assert first.revision_reason is PlanRevisionReason.RECOVERY_TIME_CHANGED

    consistent = _assess_recovery(plan, current_time_s=15.0, recovery_at_s=230.0)
    assert consistent.accepted is True
    assert consistent.revision_reason is PlanRevisionReason.CONTINUITY_PRESERVED

    # The accepted assessment re-arms the strike counter: two fresh
    # disagreements are rejected again before the breaker fires.
    for _ in range(2):
        rejected = _assess_recovery(plan, current_time_s=15.0, recovery_at_s=250.0)
        assert rejected.accepted is False
    third = _assess_recovery(plan, current_time_s=15.0, recovery_at_s=250.0)
    assert third.accepted is True
    assert third.revision_reason is PlanRevisionReason.CONTINUITY_REBASELINED


def test_commit_rearms_the_strike_counter() -> None:
    plan = RollingPlan()
    _commit(plan, recovery_at_s=230.0)
    for _ in range(2):
        assert _assess_recovery(plan, current_time_s=15.0, recovery_at_s=250.0).accepted is False

    _commit(plan, recovery_at_s=230.0)
    rejected = _assess_recovery(plan, current_time_s=15.0, recovery_at_s=250.0)
    assert rejected.accepted is False
    assert rejected.revision_reason is PlanRevisionReason.RECOVERY_TIME_CHANGED


@pytest.mark.parametrize("safe", [False, True])
def test_recovery_transition_can_use_only_a_safe_soft_prefix(safe: bool) -> None:
    plan = RollingPlan()
    _commit(plan)
    reference = plan.reference(
        current_time_s=15.0,
        horizon_steps=80,
        dt_s=5.0,
        identity=_identity(authority_hash="released"),
        prior_plan_safe=safe,
        allow_authority_transition_reference=True,
    )
    assert reference.active is False
    assert reference.revision_reason is PlanRevisionReason.COLREG_AUTHORITY_CHANGED
    assert bool(max(reference.objective_weight)) is safe
    assert not any(reference.objective_weight[6:])
