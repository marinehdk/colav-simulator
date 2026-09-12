import math
from dataclasses import replace

import numpy as np
import pytest

from colav_simulator.core.colav.horizon_encounter_plan import (
    HorizonEncounterPhase,
    HorizonEncounterPlanRequest,
    HorizonTargetIntent,
    TargetPrediction,
    _recovery_paths,
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


def test_response_lag_stages_recovery_on_the_executed_turn_back_envelope() -> None:
    """Staging must run on the qualified first-order course response, not on
    the raw max-rate envelope: the lagged envelope chases the corridor command
    slower, therefore predicts the executed (closer) pass, and the staged
    RECOVER knot keeps the same post-CPA guard semantics on that envelope.

    Overtaking geometry: the target sits on the route ahead and the corridor
    turns aside, so a lagged vessel keeps closing past the max-rate envelope's
    predicted CPA (overtaking-E0 released ~9 knots before the executed CPA).
    """
    corridor_bearing = -math.radians(20.0)
    legacy_request = _request((_overtaking_intent(),), avoidance_corridor_bearing_rad=corridor_bearing)
    lagged_request = _request(
        (_overtaking_intent(),),
        course_time_constant_s=86.78,
        avoidance_corridor_bearing_rad=corridor_bearing,
    )

    legacy = compile_horizon_encounter_plan(legacy_request)
    lagged = compile_horizon_encounter_plan(lagged_request)

    # The lagged envelope chases the corridor command slower: over the first
    # corridor leg (before the earliest recovery row) every knot is less
    # turned than the rate-only envelope.
    legacy_paths = _recovery_paths(
        legacy_request.times_s,
        own_heading_rad=legacy_request.own_heading_rad,
        own_speed_mps=legacy_request.own_speed_mps,
        mission_bearing_rad=legacy_request.mission_route_bearing_rad,
        corridor_bearing_rad=corridor_bearing,
        route_origin_ne_m=(0.0, 0.0),
        rot_max_rad_s=legacy_request.rot_max_rad_s,
        heading_window_rad=legacy_request.heading_window_rad,
    )
    lagged_paths = _recovery_paths(
        lagged_request.times_s,
        own_heading_rad=lagged_request.own_heading_rad,
        own_speed_mps=lagged_request.own_speed_mps,
        mission_bearing_rad=lagged_request.mission_route_bearing_rad,
        corridor_bearing_rad=corridor_bearing,
        route_origin_ne_m=(0.0, 0.0),
        rot_max_rad_s=lagged_request.rot_max_rad_s,
        heading_window_rad=lagged_request.heading_window_rad,
        course_time_constant_s=86.78,
    )
    corridor_leg = slice(1, 11)
    # east mission route: cross-track is the sine (north) component, index 1
    assert np.all(np.abs(lagged_paths[10, corridor_leg, 1]) <= np.abs(legacy_paths[10, corridor_leg, 1]))
    assert np.all(np.abs(legacy_paths[10, corridor_leg, 1]) > 0.0)

    # The executed pass is closer under the lag: at the same staging row the
    # lagged envelope stays nearer the on-route target through abeam, so
    # staging is clearance conservative, never optimistic about the plant.
    times_s = legacy_request.times_s
    target_north_m = 600.0 + 3.0 * times_s
    row = 40

    def row_clearance(paths: np.ndarray) -> float:
        north_m = paths[row, :, 0]
        east_m = paths[row, :, 1]
        return float(np.min(np.hypot(target_north_m - north_m, east_m - east_m)))

    assert row_clearance(lagged_paths) < row_clearance(legacy_paths)

    assert legacy.recovery_from_k is not None
    assert lagged.recovery_from_k is not None
    assert lagged.phases[lagged.recovery_from_k] is HorizonEncounterPhase.RECOVER
    assert lagged.target_windows[0].recovery_from_k == lagged.recovery_from_k


def test_recovery_release_waits_for_the_avoidance_course_cpa() -> None:
    """RECOVER must not stage before the closest approach of the avoidance
    course itself.

    Regression from crossing_give_way-E4 at 39.0 s (p5): the qualified lag
    envelope drifts off the corridor gently, so the turn-back path's own
    closest approach lay knots ahead of the CPA of the corridor course the
    executed candidate keeps flying until release (staged RECOVER at knot 18
    against a corridor CPA at knot 20); the L4 suffix measured from the
    executed CPA then found no measurable mission-course return. The staged
    release knot must respect the later of both closest approaches plus the
    execution guard.
    """
    request = _crossing_give_way_request()

    plan = compile_horizon_encounter_plan(request)

    target = request.targets[0].prediction
    corridor_bearing = request.avoidance_corridor_bearing_rad
    press_north = request.own_speed_mps * math.cos(corridor_bearing) * request.times_s
    press_east = request.own_speed_mps * math.sin(corridor_bearing) * request.times_s
    press_distance = np.hypot(target.north_m - press_north, target.east_m - press_east)
    corridor_cpa_k = int(np.argmin(press_distance))
    guard = max(1, math.ceil(15.0 / 5.0)) + 1

    assert plan.recovery_from_k is not None
    assert plan.recovery_from_k >= corridor_cpa_k + guard


def test_scheduled_release_waits_for_the_per_target_corridor_cpa() -> None:
    intent = replace(_crossing_give_way_intent(), corridor_bearing_rad=-0.23384220361258054, action_start_s=10.0)
    request = _crossing_give_way_request(intent)

    plan = compile_horizon_encounter_plan(request)

    target = request.targets[0].prediction
    corridor_bearing = intent.corridor_bearing_rad
    press_north = request.own_speed_mps * math.cos(corridor_bearing) * request.times_s
    press_east = request.own_speed_mps * math.sin(corridor_bearing) * request.times_s
    press_distance = np.hypot(target.north_m - press_north, target.east_m - press_east)
    corridor_cpa_k = int(np.argmin(press_distance))
    guard = max(1, math.ceil(15.0 / 5.0)) + 1

    window = plan.target_windows[0]
    assert window.recovery_from_k is not None
    assert window.recovery_from_k >= corridor_cpa_k + guard


def test_unset_course_time_constant_keeps_legacy_rate_only_staging() -> None:
    intent = _head_on_intent()

    default_plan = compile_horizon_encounter_plan(_request((intent,)))
    explicit_plan = compile_horizon_encounter_plan(_request((intent,), course_time_constant_s=0.0))

    assert default_plan.recovery_from_k == explicit_plan.recovery_from_k
    assert default_plan.phases == explicit_plan.phases


def test_request_rejects_negative_course_time_constant() -> None:
    with pytest.raises(ValueError):
        _request((_head_on_intent(),), course_time_constant_s=-1.0)


def test_prediction_and_plan_time_grids_are_immutable() -> None:
    intent = _head_on_intent()
    plan = compile_horizon_encounter_plan(_request((intent,)))

    with pytest.raises(ValueError):
        intent.prediction.north_m[0] = 1.0
    with pytest.raises(ValueError):
        plan.times_s[0] = 1.0


def _request(
    intents: tuple[HorizonTargetIntent, ...],
    *,
    course_time_constant_s: float = 0.0,
    avoidance_corridor_bearing_rad: float = math.radians(20.0),
) -> HorizonEncounterPlanRequest:
    return HorizonEncounterPlanRequest(
        reference_time_s=5.0,
        times_s=np.arange(81, dtype=float) * 5.0,
        own_position_ne_m=(0.0, 0.0),
        mission_route_anchor_ne_m=(0.0, 0.0),
        own_heading_rad=0.0,
        own_speed_mps=7.0,
        mission_route_bearing_rad=0.0,
        avoidance_corridor_bearing_rad=avoidance_corridor_bearing_rad,
        rot_max_rad_s=math.radians(3.0),
        heading_window_rad=math.radians(45.0),
        course_time_constant_s=course_time_constant_s,
        targets=intents,
    )


def _overtaking_intent(
    *,
    target_id: int = 9,
    recovery_clearance_m: float = 150.0,
) -> HorizonTargetIntent:
    """Slow target ahead on the route line; the avoidance corridor turns aside."""
    times = np.arange(81, dtype=float) * 5.0
    key = TrackKey(target_id, 1)
    return HorizonTargetIntent(
        key=key,
        required_course_change_rad=math.radians(20.0),
        recovery_clearance_m=recovery_clearance_m,
        action_achieved=False,
        route_recovery_allowed=False,
        prediction=TargetPrediction(
            key=key,
            reference_time_s=5.0,
            velocity_ne_mps=(3.0, 0.0),
            times_s=times,
            north_m=600.0 + 3.0 * times,
            east_m=np.zeros_like(times),
            position_uncertainty_m=np.zeros_like(times),
        ),
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


def _crossing_give_way_intent() -> HorizonTargetIntent:
    """Southbound crossing target relative to own at the p5 crossing_give_way-E4
    failure (sim_time 39.0 s), in own-centred mission frame."""
    times = np.arange(81, dtype=float) * 5.0
    key = TrackKey(1, 1)
    return HorizonTargetIntent(
        key=key,
        required_course_change_rad=0.0,
        recovery_clearance_m=176.8468391075723,
        action_achieved=True,
        route_recovery_allowed=False,
        prediction=TargetPrediction(
            key=key,
            reference_time_s=39.0,
            velocity_ne_mps=(4.286263797015736e-16, -7.0),
            times_s=times,
            north_m=830.29006032801 + 4.286263797015736e-16 * times,
            east_m=719.96755552699 - 7.0 * times,
            position_uncertainty_m=np.zeros_like(times),
        ),
    )


def _crossing_give_way_request(intent: HorizonTargetIntent | None = None) -> HorizonEncounterPlanRequest:
    """Own state, route, and avoidance corridor from the p5 crossing_give_way-E4
    failure cycle (qualified first-order lag, rot from the capability gate)."""
    return HorizonEncounterPlanRequest(
        reference_time_s=39.0,
        times_s=np.arange(81, dtype=float) * 5.0,
        own_position_ne_m=(0.0, 0.0),
        mission_route_anchor_ne_m=(0.0, -7.03244447301),
        own_heading_rad=1.3864622469419678,
        own_speed_mps=7.0,
        mission_route_bearing_rad=0.0,
        avoidance_corridor_bearing_rad=0.23384220361258054,
        rot_max_rad_s=0.020943951023931952,
        heading_window_rad=0.7853981633974483,
        course_time_constant_s=86.7839162612874,
        targets=(intent if intent is not None else _crossing_give_way_intent(),),
    )
