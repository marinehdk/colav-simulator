"""Fan recovery across route corners and sequential encounter boundaries."""
from dataclasses import replace

import numpy as np
from test_potocnik_colreg_mpc import planner_input, track

from colav_simulator.integrations.potocnik_colreg_mpc import (
    PotocnikColregFanMPC,
    PotocnikColregParams,
    _route_guidance,
)


def test_recovery_turns_into_outgoing_leg_before_crossing_corner() -> None:
    solver = PotocnikColregFanMPC(PotocnikColregParams())
    solver._maneuver_phase = "RETURN"
    solver._previous_command_course = np.deg2rad(266.0)
    inp = replace(
        planner_input(ownship_state=np.array([290., 300., np.deg2rad(265.), 4.63, 0., 0.])),
        waypoints_enu_m=np.array([[0., 0., 3150.], [2100., 0., 0.]]),
        speed_plan_mps=np.array([6.68, 4.63, 0.]),
    )
    solution = solver.solve(inp)
    delta = solution.control_reference[2, 0] - inp.ownship_state[2]
    assert np.arctan2(np.sin(delta), np.cos(delta)) > 0.0
    assert solution.algorithm_details["goal_ne_m"][0] > inp.ownship_state[0]


def test_final_leg_keeps_departure_speed_until_destination() -> None:
    solver = PotocnikColregFanMPC(PotocnikColregParams())
    inp = replace(planner_input(), speed_plan_mps=np.array([7., 0.]))
    assert solver.solve(inp).control_reference[3, 0] == 7.0


def test_finite_endpoint_capture_respects_command_turn_radius() -> None:
    solver = PotocnikColregFanMPC(PotocnikColregParams(max_command_change_deg=5.0, solve_period_s=5.0))
    inp = replace(planner_input(), waypoints_enu_m=np.array([[0.0, 500.0], [0.0, 0.0]]))
    solution = solver.solve(inp)
    # A pursuit arc can require curvature 2/d. Its speed must fit the
    # command's own turn rate, otherwise a fixed-speed orbit can miss the goal.
    bound = 0.5 * 500.0 * np.deg2rad(5.0) / 5.0
    assert solution.control_reference[3, 0] <= bound


def test_crossing_action_uses_encounter_course_while_recapturing_route() -> None:
    solver = PotocnikColregFanMPC(PotocnikColregParams(collision_distance_m=190.))
    solver._maneuver_phase = "RETURN"
    solver._previous_command_course = 0.0
    inp = replace(
        planner_input(track(position_ne=(2190., 400.), velocity_ne=(-2.36, -1.99))),
        waypoints_enu_m=np.array([[0., 10000.], [405., 405.]]),
    )
    solution = solver.solve(inp)
    assert solution.algorithm_details["active_encounters"] == ["crossing_give_way"]
    assert solution.control_reference[2, 0] >= np.deg2rad(5.) - 1e-10
    assert not solution.constraints["colreg_policy"]["relaxations"]


def test_astern_filter_checks_track_crossing_instead_of_cpa() -> None:
    solver = PotocnikColregFanMPC(PotocnikColregParams())
    # Target travels north; the candidates move east across its track.
    # CPA can occur before the actual crossing, so check the crossing itself.
    candidates = np.zeros((3, 6, 3))
    candidates[:, 0, :] = np.array([[10., 10., 10.], [-10., -10., -10.], [10., 10., 10.]])
    candidates[:, 1, :] = np.array([[-20., -10., 5.], [-20., -10., 5.], [-20., -15., -10.]])
    targets = [{"target_id": 1, "velocity_ne_mps": [1., 0.],
                "north_m": [0., 1., 2.], "east_m": [0., 0., 0.]}]
    assert solver._pass_astern_candidates(candidates, targets, (1,)).tolist() == [False, True, False]


def test_far_safe_geometry_does_not_lock_recovery_course() -> None:
    solver = PotocnikColregFanMPC(PotocnikColregParams())
    inp = planner_input(track(position_ne=(2000., 1400.), velocity_ne=(-2., -2.)))
    policy = solver._encounter_policy(inp)
    assert not policy.give_way_targets


def test_new_encounter_does_not_inherit_previous_action_course() -> None:
    solver = PotocnikColregFanMPC(PotocnikColregParams())
    first = planner_input(track(position_ne=(1000., 0.), velocity_ne=(-7., 0.)))
    solver._encounter_policy(first)
    solver._encounter_policy(planner_input())
    second = planner_input(track(target_id=2, position_ne=(0., 1000.), velocity_ne=(0., -7.)),
                           ownship_state=np.array([0., 0., np.pi / 2, 7., 0., 0.]))
    solver._encounter_policy(second)
    assert solver._give_way_course == np.pi / 2
    solver.reset()
    assert solver._give_way_course is None
    assert solver._route_segment == 0


def test_route_lookahead_continues_across_corner() -> None:
    goal, _, _, _ = _route_guidance(np.array([-100., 0.]),
                                   np.array([[-1000., 0., 0.], [0., 0., 1000.]]), 200.)
    np.testing.assert_allclose(goal, [0., 100.])


def test_anticipated_head_on_uses_intended_leg_and_survives_turn() -> None:
    solver = PotocnikColregFanMPC(PotocnikColregParams(collision_distance_m=190.))
    inp = replace(
        planner_input(track(position_ne=(560., 913.), velocity_ne=(-.773, -1.545)),
                      ownship_state=np.array([0., 0., np.deg2rad(25.), 4.63, 0., 0.])),
        waypoints_enu_m=np.array([[-3000., 10., 510.], [-38., -38., 712.]]),
        speed_plan_mps=np.array([4.63, 5.66, 0.]),
    )
    first = solver._encounter_policy(inp)
    assert first.encounters[0]['detected_geometry'] == 'crossing_give_way'
    assert first.encounters[0]['encounter'] == 'head_on'
    np.testing.assert_allclose(solver._give_way_course, np.arctan2(750., 500.), atol=1e-12)
    solver._previous_command_course = inp.ownship_state[2]
    solution = solver.solve(inp)
    delta = solution.control_reference[2, 0] - inp.ownship_state[2]
    assert np.arctan2(np.sin(delta), np.cos(delta)) > 0.0
    assert not solution.constraints['colreg_policy']['relaxations']
    turned = replace(inp, ownship_state=np.array([10., 5., np.deg2rad(70.), 4.63, 0., 0.]))
    assert solver._encounter_policy(turned).encounters[0]['encounter'] == 'head_on'
