"""Response-aware nominal guidance anticipates lateral drift during recovery."""
import math

import numpy as np

from colav_simulator.core.colav.kuwata_vo_alg.kuwata_vo import VO, VOParams
from colav_simulator.core.guidances import LOSGuidance, LOSGuidanceParams


def test_recovery_brakes_lateral_motion_before_crossing_route():
    guidance = LOSGuidance(LOSGuidanceParams(K_p=0.005, K_i=0.0))
    route = np.array([[0.0, 10000.0], [0.0, 0.0]])
    # Still on starboard side but crossing towards port at 4 m/s.
    state = np.array([1000.0, 50.0, -math.pi / 6, 8.0, 0.0, 0.0])
    reference = guidance.compute_references(
        route, np.array([8.0, 8.0]), None, state, 0.5, course_response_time_constant_s=40.0
    )
    assert reference[2, 0] > 0.0  # start braking before crossing, not after


def test_delayed_course_recovery_converges_without_growing_oscillation():
    guidance = LOSGuidance(LOSGuidanceParams(K_p=0.005, K_i=0.0))
    state = np.array([0.0, 300.0, 0.0, 8.0, 0.0, 0.0])
    errors = []
    for _ in range(800):
        reference = guidance.compute_references(
            np.array([[0.0, 10000.0], [0.0, 0.0]]), np.array([8.0, 8.0]), None, state, 0.5,
            course_response_time_constant_s=40.0,
        )
        state[2] += (1 - math.exp(-0.5 / 40)) * math.remainder(reference[2, 0] - state[2], 2 * math.pi)
        state[0] += 8 * math.cos(state[2]) * 0.5
        state[1] += 8 * math.sin(state[2]) * 0.5
        errors.append(state[1])
    assert min(errors) > -30
    assert abs(errors[-1]) < 5


def test_receding_cleared_target_does_not_force_another_starboard_maneuver():
    planner = VO(VOParams(t_max=60.0, d_min=190.0, hard_hull_clearance_m=182.0, preferred_hull_clearance_m=190.0))
    own = np.array([0.0, 0.0, 0.0, 8.0, 0.0, 0.0])
    target = (1, np.array([-1000.0, -200.0, 2.5, 0.0]), np.eye(4), 12.0, 4.0)
    result = planner.plan(
        0.0, np.array([8.0, 0.0]), own, [target], os_length=44.1, os_width=8.0,
        os_course_time_constant_s=39.425571, os_speed_time_constant_s=12.5,
        os_max_turn_rate_radps=math.radians(1.2),
    )
    assert not planner.get_debug_data()["active_rules"]
    assert abs(result[2, 0]) <= math.radians(2.8125)


def test_terminal_reference_does_not_project_cruise_beyond_final_waypoint():
    guidance = LOSGuidance(LOSGuidanceParams(K_p=0.005, K_i=0.0))
    route = np.array([[0.0, 2000.0], [0.0, 0.0]])
    state = np.array([1600.0, 0.0, 0.0, 8.0, 0.0, 0.0])
    reference = guidance.compute_references(
        route, np.array([8.0, 8.0]), None, state, 0.5, terminal_time_horizon_s=100.0
    )
    assert 0 < reference[3, 0] <= 4.0
    assert reference[2, 0] == 0.0


def test_terminal_braking_does_not_slow_an_interior_leg():
    guidance = LOSGuidance(LOSGuidanceParams(K_p=0.005, K_i=0.0))
    route = np.array([[0.0, 2000.0, 4000.0], [0.0, 0.0, 0.0]])
    state = np.array([1600.0, 0.0, 0.0, 8.0, 0.0, 0.0])
    reference = guidance.compute_references(
        route, np.array([8.0, 8.0, 8.0]), None, state, 0.5, terminal_time_horizon_s=100.0
    )
    assert reference[3, 0] == 8.0
