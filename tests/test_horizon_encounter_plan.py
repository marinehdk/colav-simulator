import math

import numpy as np
import pytest

from colav_simulator.core.colav.horizon_encounter_plan import (
    HorizonEncounterPhase,
    HorizonEncounterPlanRequest,
    HorizonTargetIntent,
    TargetPrediction,
    compile_horizon_encounter_plan,
)
from colav_simulator.core.tracking.trackers import TrackKey


def test_active_encounter_compiles_alter_pass_recover_phases() -> None:
    request = _request((_head_on_intent(),))

    plan = compile_horizon_encounter_plan(request)

    assert plan.solver_consumed is False
    assert plan.phases[0] is HorizonEncounterPhase.ALTER
    assert HorizonEncounterPhase.PASS in plan.phases
    assert HorizonEncounterPhase.RECOVER in plan.phases
    assert plan.recovery_from_k is not None
    assert plan.recovery_from_k < 80
    assert plan.target_windows[0].recovery_from_k == plan.recovery_from_k
    assert tuple(dict.fromkeys(plan.phases)) == (
        HorizonEncounterPhase.ALTER,
        HorizonEncounterPhase.PASS,
        HorizonEncounterPhase.RECOVER,
    )


def test_unresolved_target_keeps_pass_phase_through_horizon() -> None:
    request = _request((_head_on_intent(initial_north_m=10_000.0, recovery_clearance_m=10_000.0),))

    plan = compile_horizon_encounter_plan(request)

    assert plan.recovery_from_k is None
    assert plan.phases[-1] is HorizonEncounterPhase.PASS
    assert HorizonEncounterPhase.RECOVER not in plan.phases


def test_multi_target_plan_uses_latest_safe_recovery_window() -> None:
    first = _head_on_intent(target_id=1, initial_north_m=800.0)
    second = _head_on_intent(target_id=2, initial_north_m=1200.0)

    plan = compile_horizon_encounter_plan(_request((first, second)))

    recovery_indices = tuple(window.recovery_from_k for window in plan.target_windows)
    assert all(index is not None for index in recovery_indices)
    assert recovery_indices[0] < recovery_indices[1]
    assert plan.recovery_from_k == max(recovery_indices)
    assert plan.phases[plan.recovery_from_k] is HorizonEncounterPhase.RECOVER


def test_clear_horizon_remains_on_mission_route() -> None:
    plan = compile_horizon_encounter_plan(_request(()))

    assert plan.recovery_from_k == 0
    assert set(plan.phases) == {HorizonEncounterPhase.MISSION}
    assert plan.target_windows == ()


def test_released_target_keeps_finite_recovery_evidence() -> None:
    intent = _head_on_intent(route_recovery_allowed=True)

    plan = compile_horizon_encounter_plan(_request((intent,)))

    assert plan.target_windows[0].route_recovery_allowed_at_start is True
    assert math.isfinite(plan.target_windows[0].minimum_predicted_route_dcpa_m)


def test_prediction_and_plan_time_grids_are_immutable() -> None:
    intent = _head_on_intent()
    plan = compile_horizon_encounter_plan(_request((intent,)))

    with pytest.raises(ValueError):
        intent.prediction.north_m[0] = 1.0
    with pytest.raises(ValueError):
        plan.times_s[0] = 1.0


def _request(intents: tuple[HorizonTargetIntent, ...]) -> HorizonEncounterPlanRequest:
    return HorizonEncounterPlanRequest(
        reference_time_s=5.0,
        times_s=np.arange(81, dtype=float) * 5.0,
        own_position_ne_m=(0.0, 0.0),
        mission_route_anchor_ne_m=(0.0, 0.0),
        own_heading_rad=0.0,
        own_speed_mps=7.0,
        mission_route_bearing_rad=0.0,
        avoidance_corridor_bearing_rad=math.radians(20.0),
        rot_max_rad_s=math.radians(3.0),
        heading_window_rad=math.radians(45.0),
        targets=intents,
    )


def _head_on_intent(
    *,
    target_id: int = 1,
    initial_north_m: float = 1000.0,
    recovery_clearance_m: float = 150.0,
    route_recovery_allowed: bool = False,
) -> HorizonTargetIntent:
    times = np.arange(81, dtype=float) * 5.0
    key = TrackKey(target_id, 1)
    return HorizonTargetIntent(
        key=key,
        required_course_change_rad=math.radians(20.0),
        recovery_clearance_m=recovery_clearance_m,
        action_achieved=False,
        route_recovery_allowed=route_recovery_allowed,
        prediction=TargetPrediction(
            key=key,
            reference_time_s=5.0,
            velocity_ne_mps=(-7.0, 0.0),
            times_s=times,
            north_m=initial_north_m - 7.0 * times,
            east_m=np.zeros_like(times),
            position_uncertainty_m=np.zeros_like(times),
        ),
    )
