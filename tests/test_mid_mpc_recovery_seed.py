"""The OT T885.5 seed must satisfy capture as well as the unchanged NLP rows."""

import gzip
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from colav_simulator.core.colav.mid_mpc.models import (
    MidMpcConfig,
    MidMpcHardWindow,
    MidMpcOwnShip,
    MidMpcProblem,
    MidMpcRouteFrame,
    MidMpcRouteObjective,
    MidMpcRowSchedule,
    MidMpcStaticField,
    MidMpcStatus,
    MidMpcTarget,
)
from colav_simulator.core.colav.mid_mpc.solver import MidMpcIpoptSolver, _build_graph, _max_row_violation, _prepare
from colav_simulator.core.colav.mid_mpc_arrival import arrival_references, navigation_capture_error
from colav_simulator.core.colav.retained_route import RetainedRouteConstraint, degraded_stub_prefix
from colav_simulator.core.tracking.trackers import TrackKey
from colav_simulator.integrations.mid_mpc_ipopt import _recovery_iterate_filter


def _problem(document: dict) -> MidMpcProblem:
    values = dict(document)
    values["own_ship"] = MidMpcOwnShip(**values["own_ship"])
    values["route_frame"] = MidMpcRouteFrame(**values["route_frame"])
    values["route_objective"] = MidMpcRouteObjective(**values["route_objective"])
    values["targets"] = tuple(MidMpcTarget(**target) for target in values["targets"])
    values["static_field"] = MidMpcStaticField(**values["static_field"])
    schedule = values["row_schedule"]
    schedule["cpa_hard_windows"] = tuple(MidMpcHardWindow(**window) for window in schedule["cpa_hard_windows"])
    for name in ("direction_hard_window", "min_alt_hard_window"):
        if schedule[name] is not None:
            schedule[name] = MidMpcHardWindow(**schedule[name])
    values["row_schedule"] = MidMpcRowSchedule(**schedule)
    return MidMpcProblem(**values)


def test_recorded_ot_recovery_produces_a_capture_admissible_optimizer_candidate():
    with gzip.open(Path(__file__).parent / "fixtures/original_gnc/mid-ot-recovery-capture.json.gz", "rt") as stream:
        case = json.load(stream)
    problem = _problem(case["problem"])
    state = np.array(case["ownship"]["state"])
    constraint = RetainedRouteConstraint(**case["ownship"]["execution_route_constraint"])
    planner_input = SimpleNamespace(
        ownship_state=state,
        execution_route_constraint=constraint,
        ownship_length_m=case["ownship"]["length_m"],
        waypoints_enu_m=np.array(case["mission"]).T,
        tracks=tuple(SimpleNamespace(**track) for track in case["tracks"]),
    )
    assembly = SimpleNamespace(
        problem=problem,
        execution_prefix=degraded_stub_prefix(constraint, state),
        grid=SimpleNamespace(control_intervals=80, dt_s=5.0),
        horizon_encounter_plan=SimpleNamespace(
            recovery_from_k=case["horizon"]["recovery_from_k"],
            target_windows=tuple(
                SimpleNamespace(key=TrackKey(**window["key"])) for window in case["horizon"]["target_windows"]
            ),
        ),
    )
    check = _recovery_iterate_filter(planner_input, assembly)
    solver = MidMpcIpoptSolver(MidMpcConfig(horizon_steps=80, strict_slack_bounds=True, max_wall_time_s=30.0))
    solver.solve(problem, wall_time_s=0.0, iterate_filter=check)  # Build the exact production graph first.
    result = solver.solve(problem, wall_time_s=20.0, iterate_filter=check)
    assert result.status in {MidMpcStatus.CONVERGED, MidMpcStatus.FEASIBLE_NONOPTIMAL}
    assert check(result.raw_x)
    assert result.ipopt_iterations > 0
    assert result.max_constraint_violation <= 1e-3
    assert result.max_decision_bound_violation <= 1e-7
    assert result.raw_cpa_slack == 0.0
    assert result.raw_dir_slack == 0.0


def test_recorded_timed_recovery_brakes_before_the_chart_boundary():
    with gzip.open(Path(__file__).parent / "fixtures/original_gnc/mid-ot-timed-terminal.json.gz", "rt") as stream:
        case = json.load(stream)
    problem = _problem(case["problem"])
    config = MidMpcConfig(horizon_steps=80, dt_s=5.0, strict_slack_bounds=True)
    graph = _build_graph(config, problem)
    original = _prepare(config, problem, graph.row_layout)
    assert _max_row_violation(graph, original.x0, original) > 800.0
    own, route = case["ownship"], case["route"]
    state = own["state"]
    mission = tuple(map(tuple, route["mission_waypoints_ne_m"]))
    headings, lateral, speeds, terminal = arrival_references(
        mission,
        tuple(state[:2]),
        state[2],
        problem.own_ship.u_mps,
        8.0,
        5.0,
        80,
        0.08,
        problem.rot_max_rad_s,
        15.0 + 4.0 * own["speed_time_constant_s"],
        tuple(route["anchor_ne_m"]),
        route["mission_leg_bearing_rad"],
        own["speed_time_constant_s"],
    )
    problem = replace(
        problem,
        route_objective=replace(
            problem.route_objective,
            heading_reference_rad=headings,
            lateral_reference_m=lateral,
            speed_reference_mps=speeds,
            terminal_position_m=terminal,
            continuity_speed_reference_mps=speeds,
        ),
    )
    prepared = _prepare(config, problem, graph.row_layout)
    assert _max_row_violation(graph, prepared.x0, prepared) < 1e-9
    assert np.all(prepared.x0 >= prepared.lbx)
    assert np.all(prepared.x0 <= prepared.ubx)
    origin = np.asarray(state[:2])

    def captured(values) -> bool:
        course, speed = values[:80], values[80:160]
        positions = np.vstack(
            (
                origin,
                origin
                + np.cumsum(
                    5.0 * speed[:, None] * np.column_stack((np.cos(course), np.sin(course))),
                    axis=0,
                ),
            )
        )
        return navigation_capture_error(positions[:, 0], positions[:, 1], mission, 308.7) <= 20.0

    solver = MidMpcIpoptSolver(config)
    solver.solve(problem, wall_time_s=0.0, iterate_filter=captured)
    result = solver.solve(problem, wall_time_s=20.0, iterate_filter=captured)
    assert result.status in {MidMpcStatus.CONVERGED, MidMpcStatus.FEASIBLE_NONOPTIMAL}
    assert result.ipopt_iterations > 0
    assert result.max_constraint_violation <= 1e-3
    assert captured(result.raw_x)


def test_recorded_multileg_prediction_brakes_on_its_future_final_leg():
    with gzip.open(Path(__file__).parent / "fixtures/original_gnc/mid-multiship-future-arrival.json.gz", "rt") as stream:
        case = json.load(stream)
    route, state = case["route"], case["state"]
    mission = tuple(map(tuple, route["mission_waypoints_ne_m"]))
    origin = np.asarray(state[:2])
    old = np.asarray(case["raw_x"])
    old_positions = np.vstack(
        (
            origin,
            origin
            + np.cumsum(
                5.0 * old[80:160, None] * np.column_stack((np.cos(old[:80]), np.sin(old[:80]))),
                axis=0,
            ),
        )
    )
    assert navigation_capture_error(old_positions[:, 0], old_positions[:, 1], mission, 308.7) > 80.0
    result = arrival_references(
        mission,
        tuple(origin),
        state[2],
        state[3],
        route["planned_speed_mps"],
        5.0,
        80,
        case["deceleration"],
        case["turn_rate"],
        15.0 + 4.0 * case["speed_time_constant_s"],
        tuple(route["anchor_ne_m"]),
        route["mission_leg_bearing_rad"],
        case["speed_time_constant_s"],
        approach_heading_reference_rad=tuple(case["headings"]),
    )
    assert result is not None
    headings, _, speeds, terminal = result
    assert terminal is not None
    assert len(headings) == len(speeds) == 80
    assert np.max(np.abs(np.diff(np.r_[state[3], speeds]))) <= case["deceleration"] * 5 + 1e-9
    positions = np.vstack(
        (
            origin,
            origin
            + np.cumsum(
                5.0 * np.asarray(speeds)[:, None] * np.column_stack((np.cos(headings), np.sin(headings))),
                axis=0,
            ),
        )
    )
    assert navigation_capture_error(positions[:, 0], positions[:, 1], mission, 308.7) <= 20.0
    assert np.linalg.norm(positions[-1] - mission[-1]) < 308.7


def test_native_capture_and_stopping_share_one_reference_geometry():
    with gzip.open(Path(__file__).parent / "fixtures/original_gnc/mid-multiship-capture-stop.json.gz", "rt") as stream:
        case = json.load(stream)
    route, state = case["route"], case["state"]
    mission = tuple(map(tuple, route["mission_waypoints_ne_m"]))
    origin = np.asarray(state[:2])
    headings, _, speeds, terminal = arrival_references(
        mission,
        tuple(origin),
        state[2],
        state[3],
        route["planned_speed_mps"],
        5.0,
        80,
        case["deceleration"],
        case["turn_rate"],
        15.0 + 4.0 * case["speed_time_constant_s"],
        tuple(route["anchor_ne_m"]),
        route["mission_leg_bearing_rad"],
        case["speed_time_constant_s"],
        arrival_radius_m=308.7,
        navigation_lookahead_m=case["lookahead_m"],
        finite_navigation_tail=True,
    )
    assert terminal is not None
    assert speeds[-1] < 0.05
    assert np.max(np.abs(np.diff(np.r_[state[3], speeds]))) <= case["deceleration"] * 5.0 + 1e-9
    positions = np.vstack(
        (
            origin,
            origin
            + np.cumsum(
                5.0 * np.asarray(speeds)[:, None] * np.column_stack((np.cos(headings), np.sin(headings))),
                axis=0,
            ),
        )
    )
    assert navigation_capture_error(positions[:, 0], positions[:, 1], mission, 308.7) <= 20.0
    assert np.linalg.norm(positions[-1] - mission[-1]) <= 5.0


def test_recorded_multiship_capture_has_a_real_admissible_optimizer_iterate():
    with gzip.open(Path(__file__).parent / "fixtures/original_gnc/mid-multiship-capture-stop.json.gz", "rt") as stream:
        case = json.load(stream)
    state, route = np.asarray(case["state"]), case["route"]
    headings, lateral, speeds, terminal = arrival_references(
        tuple(map(tuple, route["mission_waypoints_ne_m"])),
        tuple(state[:2]),
        state[2],
        state[3],
        route["planned_speed_mps"],
        5.0,
        80,
        case["deceleration"],
        case["turn_rate"],
        15.0 + 4.0 * case["speed_time_constant_s"],
        tuple(route["anchor_ne_m"]),
        route["mission_leg_bearing_rad"],
        case["speed_time_constant_s"],
        arrival_radius_m=308.7,
        navigation_lookahead_m=case["lookahead_m"],
        finite_navigation_tail=True,
    )
    problem = _problem(case["problem"])
    problem = replace(
        problem,
        navigation_recovery_lookahead_m=0.0,
        route_objective=replace(
            problem.route_objective,
            heading_reference_rad=headings,
            lateral_reference_m=lateral,
            speed_reference_mps=speeds,
            continuity_speed_reference_mps=speeds,
            terminal_position_m=terminal,
        ),
    )
    constraint = RetainedRouteConstraint(**case["execution_route_constraint"])
    data = SimpleNamespace(
        ownship_state=state,
        execution_route_constraint=constraint,
        ownship_length_m=case["ownship_length_m"],
        waypoints_enu_m=np.asarray(route["mission_waypoints_ne_m"]).T,
        tracks=(),
    )
    assembly = SimpleNamespace(
        problem=problem,
        grid=SimpleNamespace(control_intervals=80, dt_s=5.0),
        execution_prefix=degraded_stub_prefix(constraint, state),
        horizon_encounter_plan=SimpleNamespace(recovery_from_k=0, target_windows=()),
    )
    check = _recovery_iterate_filter(data, assembly)
    solver = MidMpcIpoptSolver(MidMpcConfig(horizon_steps=80, strict_slack_bounds=True))
    solver.solve(problem, wall_time_s=0.0, iterate_filter=check)
    result = solver.solve(problem, wall_time_s=20.0, iterate_filter=check)
    assert result.status in {MidMpcStatus.CONVERGED, MidMpcStatus.FEASIBLE_NONOPTIMAL}
    assert result.ipopt_iterations >= 1
    assert result.accepted_candidate_source != "PRIMAL_SEED"
    assert result.max_constraint_violation <= 1e-3
    assert check(result.raw_x)
