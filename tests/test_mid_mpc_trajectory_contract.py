"""One optimized trajectory must remain authoritative through native publication."""

from dataclasses import replace

import numpy as np
from test_mid_mpc_problem_assembler import _cycle, _planner_input, _request

from colav_simulator.core.colav.encounter_lifecycle import EncounterLifecycle, PassingSide
from colav_simulator.core.colav.mid_mpc.models import MidMpcConfig, MidMpcRouteObjective
from colav_simulator.core.colav.mid_mpc.solver import _build_graph, _prepare, _row_layout
from colav_simulator.core.colav.mid_mpc_assembler import AssemblySuccess, MidMpcProblemAssembler
from colav_simulator.core.colav.retained_route import RetainedRouteConstraint, degraded_stub_prefix
from colav_simulator.integrations.mid_mpc_ipopt import _published_execution_route


def _constraint() -> RetainedRouteConstraint:
    return RetainedRouteConstraint(
        "native",
        ((0.0, 0.0), (100.0, 0.0)),
        (4.0, 4.0),
        ("cruise", "cruise"),
        160.0,
        32.0,
        480.0,
        trajectory_updates=True,
    )


def test_direct_publication_preserves_every_optimized_sample_and_speed():
    state = np.array([50.0, 0.0, 0.0, 4.0, 0.0, 0.0])
    predicted = np.zeros((9, 6))
    predicted[:6, 0] = state
    predicted[3] = np.array([4.0, 4.0, 3.6, 3.2, 3.0, 3.0])
    predicted[2] = np.array([0.0, 0.0, 0.03, 0.06, 0.09, 0.12])
    predicted[:2, 0] = state[:2]
    predicted[0, 1:] = state[0] + np.cumsum(predicted[3, 1:] * np.cos(predicted[2, 1:]) * 5.0)
    predicted[1, 1:] = np.cumsum(predicted[3, 1:] * np.sin(predicted[2, 1:]) * 5.0)
    packet = _published_execution_route(
        degraded_stub_prefix(_constraint(), state),
        predicted,
        arrival_boundary=None,
        planned_speed_mps=4.0,
        accel_max_mps2=0.08,
        decel_max_mps2=0.08,
        rot_max_rad_s=0.02,
        steerage_speed_mps=3.0,
        mission_arrival=((0.0, 0.0), (2000.0, 0.0), 308.7),
        mission_waypoints=((0.0, 0.0), (2000.0, 0.0)),
        ownship_position=(50.0, 0.0),
        decisions=(),
    )
    assert packet["schema_version"] == "colav.mid-mpc.execution-route@2"
    np.testing.assert_array_equal(packet["points_ne_m"], predicted[:2].T)
    np.testing.assert_array_equal(packet["speed_mps"], predicted[3])
    np.testing.assert_array_equal(packet["course_rad"], predicted[2])
    assert packet["prefix_intervals"] == 0
    assert packet["retained_point_count"] == 0


def test_direct_native_contract_does_not_pin_or_splice_the_old_route():
    original = _planner_input()
    own = replace(original, sim_time_s=0.0, execution_route_constraint=_constraint())
    snapshot = EncounterLifecycle().step(_cycle(own, sequence=0, sim_time_s=0.0))
    assembled = MidMpcProblemAssembler().assemble(_request(own, snapshot))
    assert isinstance(assembled, AssemblySuccess)
    assert assembled.problem.prefix_active_k == 0
    assert assembled.problem.route_constraint_limit_m is None
    assert assembled.problem.cpa_hard_m > 0.0
    assert assembled.problem.row_schedule.cpa_hard_windows[0].stop_k == 80


def test_timed_native_arrival_has_a_finite_braking_tail():
    original = _planner_input()
    snapshot = EncounterLifecycle().step(_cycle(original, sequence=0, sim_time_s=0.0))
    snapshot = replace(
        snapshot,
        targets=(),
        directive=replace(
            snapshot.directive,
            required_targets=(),
            passing_side=PassingSide.NONE,
            minimum_course_change_rad=0.0,
            speed_bounds_mps=(6.4, 8.0),
        ),
    )
    own = replace(
        original,
        tracks=(),
        sim_time_s=0.0,
        ownship_state=np.array([0.0, 0.0, 0.0, 8.0, 0.0, 0.0]),
        ownship_speed_time_constant_s=24.0,
        execution_route_constraint=_constraint(),
    )
    request = _request(own, snapshot)
    request = replace(
        request,
        route=replace(
            request.route,
            anchor_ne_m=(0.0, 0.0),
            mission_leg_bearing_rad=0.0,
            mission_waypoints_ne_m=((0.0, 0.0), (500.0, 0.0)),
            planned_speed_mps=8.0,
        ),
        capability=replace(request.capability, decel_max_mps2=0.08),
    )
    assembled = MidMpcProblemAssembler().assemble(request)
    assert isinstance(assembled, AssemblySuccess)
    problem = assembled.problem
    objective = problem.route_objective
    assert objective.terminal_position_m is not None
    assert problem.navigation_recovery_lookahead_m == 0.0
    speeds = np.asarray(objective.speed_reference_mps)
    assert speeds[-1] < 0.1
    assert np.max(np.abs(np.diff(np.r_[8.0, speeds]))) <= 0.08 * 5.0 + 1e-9
    positions = np.cumsum(
        5.0
        * speeds[:, None]
        * np.column_stack(
            (
                np.cos(objective.heading_reference_rad),
                np.sin(objective.heading_reference_rad),
            )
        ),
        axis=0,
    )
    assert np.max(positions[:, 0]) <= 505.0
    config = MidMpcConfig(horizon_steps=80, dt_s=5.0, strict_slack_bounds=True)
    prepared = _prepare(config, problem, _row_layout(config, 1, 1))
    assert prepared.lbx[80] == 6.4
    assert prepared.lbx[159] <= speeds[-1]
    assert np.all(prepared.x0 >= prepared.lbx)
    assert np.all(prepared.x0 <= prepared.ubx)


def test_low_speed_turn_respects_native_radius_without_changing_row_layout():
    own = replace(
        _planner_input(),
        tracks=(),
        sim_time_s=0.0,
        ownship_state=np.array([0.0, 0.0, 0.0, 0.4, 0.0, 0.0]),
        execution_route_constraint=replace(
            _constraint(), minimum_turn_radius_m=80.0, maximum_lateral_acceleration_mps2=0.25
        ),
    )
    snapshot = EncounterLifecycle().step(_cycle(_planner_input(), sequence=0, sim_time_s=0.0))
    snapshot = replace(
        snapshot,
        targets=(),
        directive=replace(
            snapshot.directive, required_targets=(), passing_side=PassingSide.NONE, minimum_course_change_rad=0.0
        ),
    )
    assembled = MidMpcProblemAssembler().assemble(_request(own, snapshot))
    assert isinstance(assembled, AssemblySuccess)
    problem = replace(
        assembled.problem,
        speed_bounds_mps=(0.0, 8.0),
        route_objective=MidMpcRouteObjective(
            mission_bearing_rad=0.0,
            avoidance_corridor_bearing_rad=0.0,
            heading_reference_rad=(0.0,) * 80,
            lateral_reference_m=(0.0,) * 80,
            avoidance_active_until_k=0,
        ),
    )
    assert problem.minimum_turn_radius_m == 80.0
    assert problem.maximum_lateral_acceleration_mps2 == 0.25
    config = MidMpcConfig(horizon_steps=80, dt_s=5.0, strict_slack_bounds=True)
    graph = _build_graph(config, problem)
    prepared = _prepare(config, problem, graph.row_layout)
    candidate = prepared.x0.copy()
    candidate[80:160] = 0.4
    candidate[:80] = 0.1
    rows = np.asarray(graph.constraints(candidate, prepared.p)).ravel()
    assert rows[0] < 0.0  # 20 m radius, although below the standalone ROT cap.
    candidate[:80] = 0.02
    rows = np.asarray(graph.constraints(candidate, prepared.p)).ravel()
    assert np.min(rows[:160]) >= 0.0  # 100 m radius.
    assert graph.row_layout.rot.count == 160
