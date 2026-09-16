"""Planner-owned GNC prefix and spatial update constraints."""

import gzip
import json
import math
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from test_mid_mpc_ipopt_core import _slow_hull_problem
from test_mid_mpc_problem_assembler import _cycle, _planner_input, _request

from colav_simulator.core.colav.custom_mpc_adapter import CustomMPCAdapter, FactoryContext, MPCSolution
from colav_simulator.core.colav.encounter_lifecycle import EncounterLifecycle, RiskPhase
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
from colav_simulator.core.colav.mid_mpc.solver import MidMpcIpoptSolver, _prepare, _row_layout
from colav_simulator.core.colav.mid_mpc_assembler import AssemblySuccess, MidMpcProblemAssembler
from colav_simulator.core.colav.retained_route import (
    RetainedRouteConstraint,
    compile_execution_route,
    compile_retained_prefix,
)
from colav_simulator.integrations.mid_mpc_ipopt import _gnc_course_input, _native_trajectories, create


def test_prefix_reaches_unchanged_route_with_rate_feasible_controls():
    constraint = RetainedRouteConstraint(
        reference_id="mission",
        points_ne_m=((0.0, 0.0), (5000.0, 0.0)),
        speed_mps=(8.0, 8.0),
        navigation_modes=("cruise", "dp_hold"),
        minimum_update_distance_m=160.0,
        minimum_segment_m=32.0,
        lateral_limit_m=480.0,
    )
    state = np.array([35.0, 2.0, math.radians(-2.0), 7.0, 0.0, 0.0])
    plan = compile_retained_prefix(
        constraint, state, horizon_steps=80, dt_s=5.0, max_speed_mps=8.0, rot_max_rad_s=math.radians(1.2), accel_max_mps2=0.3
    )
    course = np.array(plan.course_rad)
    speed = np.array(plan.speed_mps)
    end = state[:2] + np.array([np.sum(speed * np.cos(course) * 5), np.sum(speed * np.sin(course) * 5)])
    np.testing.assert_allclose(end, plan.points_ne_m[-1], atol=1e-7)
    assert plan.points_ne_m[0] == (0.0, 0.0)
    assert plan.points_ne_m[-1][0] - state[0] >= 160
    assert np.max(np.abs(np.diff(np.r_[state[2], course]))) <= math.radians(1.2) * 5 + 1e-9
    assert np.max(np.abs(np.diff(np.r_[7.0, speed]))) <= 0.3 * 5 + 1e-9
    assert max(speed) <= 8.0
    assert abs(course[-1]) < math.radians(1)


def test_assembler_and_ipopt_consume_gnc_prefix_and_corridor():
    original = _planner_input()
    route = RetainedRouteConstraint(
        "accepted", ((0.0, 0.0), (5000.0, 0.0)), (7.0, 7.0), ("cruise", "cruise"), 160.0, 32.0, 480.0
    )
    own = replace(original, execution_route_constraint=route)
    lifecycle = EncounterLifecycle()
    lifecycle.step(_cycle(own, sequence=0, sim_time_s=0.0))
    snapshot = lifecycle.step(_cycle(own, sequence=1, sim_time_s=5.0))
    request = _request(own, snapshot)
    assembled = MidMpcProblemAssembler().assemble(request)
    assert isinstance(assembled, AssemblySuccess)
    assert assembled.execution_prefix is not None
    assert assembled.problem.prefix_active_k > 1
    assert assembled.problem.route_constraint_limit_m == 480
    solver = MidMpcIpoptSolver(MidMpcConfig(horizon_steps=80, strict_slack_bounds=True, max_wall_time_s=15))
    result = solver.solve(assembled.problem)
    assert result.status in {MidMpcStatus.CONVERGED, MidMpcStatus.FEASIBLE_NONOPTIMAL}
    assert result.max_constraint_violation < 1e-3
    predicted, _ = _native_trajectories(result.trajectory, own.ownship_state, 5)
    packet = compile_execution_route(assembled.execution_prefix, predicted)
    assert packet["points_ne_m"][: packet["retained_point_count"]] == list(
        assembled.execution_prefix.points_ne_m[: packet["retained_point_count"]]
    )
    assert all(abs(point[1]) <= 480 + 1e-3 for point in packet["points_ne_m"])


def test_released_contact_stays_in_physical_constraints_when_reachable():
    original = _planner_input()
    own = replace(original, tracks=(replace(original.tracks[0], state_enu=np.array([1200.0, 1200.0, 2.5, 0.0])),))
    lifecycle = EncounterLifecycle()
    snapshot = lifecycle.step(_cycle(own, sequence=0, sim_time_s=5.0))
    target = replace(snapshot.targets[0], risk=RiskPhase.RELEASED, recovery_guard_active=False, route_recovery_allowed=True)
    snapshot = replace(snapshot, targets=(target,), directive=replace(snapshot.directive, required_targets=()))
    result = MidMpcProblemAssembler().assemble(_request(own, snapshot))
    assert isinstance(result, AssemblySuccess)
    assert result.selected_target_keys == (target.key,)
    assert result.problem.row_schedule.cpa_hard_windows[0].stop_k == 80


def test_native_route_planner_uses_ground_course_without_changing_world_velocity():
    route = RetainedRouteConstraint(
        "mission", ((0.0, 0.0), (5000.0, 0.0)), (8.0, 8.0), ("cruise", "cruise"), 160.0, 32.0, 480.0
    )
    raw = np.array([0.0, 0.0, math.radians(33.3), 4.23, -0.24, 0.005])
    original = replace(_planner_input(), ownship_state=raw, execution_route_constraint=route)
    normalized = _gnc_course_input(original)
    expected = raw[2] + math.atan2(raw[4], raw[3])
    assert normalized.ownship_state[2] == expected
    assert normalized.ownship_state[4] == 0
    original_velocity = np.array(
        [math.cos(raw[2]) * raw[3] - math.sin(raw[2]) * raw[4], math.sin(raw[2]) * raw[3] + math.cos(raw[2]) * raw[4]]
    )
    normalized_velocity = normalized.ownship_state[3] * np.array([math.cos(expected), math.sin(expected)])
    np.testing.assert_allclose(normalized_velocity, original_velocity, atol=1e-12)
    np.testing.assert_array_equal(original.ownship_state, raw)


def test_adapter_normalizes_before_strict_initial_state_validation():
    adapter = create(context=FactoryContext("mid_mpc_ipopt", 0, scenario_target_count=1))
    route = RetainedRouteConstraint(
        "mission", ((0.0, 0.0), (5000.0, 0.0)), (8.0, 8.0), ("cruise", "cruise"), 160.0, 32.0, 480.0
    )
    raw = np.array([0.0, 0.0, math.radians(33.3), 4.23, -0.24, 0.005])
    value = adapter._planner_input(
        5.0,
        np.array(route.points_ne_m).T,
        np.array(route.speed_mps),
        raw,
        [],
        object(),
        None,
        None,
        {"dt": 0.5, "os_execution_route_constraint": route},
    )
    expected = raw[2] + math.atan2(raw[4], raw[3])
    assert value.ownship_state[2] == expected
    predicted = np.zeros((9, 81))
    predicted[:6] = value.ownship_state[:, None]
    solution = MPCSolution(predicted[:, :1], predicted, horizon_dt_s=5.0)
    validator = SimpleNamespace(_capture_evidence=False, descriptor=adapter.descriptor)
    CustomMPCAdapter._validate_solution(validator, solution, value)
    bad = predicted.copy()
    bad[2, 0] = raw[2]
    with pytest.raises(ValueError, match="heading error"):
        CustomMPCAdapter._validate_solution(validator, MPCSolution(bad[:, :1], bad, horizon_dt_s=5.0), value)


def test_recovery_prefix_continues_the_admitted_path_instead_of_restarting_return():
    own = replace(
        _planner_input(),
        tracks=(),
        ownship_state=np.array([500.0, 500.0, math.pi / 4, 7.0, 0.0, 0.0]),
        execution_route_constraint=RetainedRouteConstraint(
            "admitted-return", ((0.0, 0.0), (5000.0, 5000.0)), (7.0, 7.0), ("avoidance", "avoidance"), 160.0, 32.0, 480.0
        ),
    )
    lifecycle = EncounterLifecycle()
    cycle = _cycle(replace(own, tracks=_planner_input().tracks), sequence=0, sim_time_s=5.0)
    snapshot = lifecycle.step(replace(cycle, targets=()))
    result = MidMpcProblemAssembler().assemble(_request(own, snapshot))
    assert isinstance(result, AssemblySuccess)
    assert result.execution_prefix is not None
    np.testing.assert_allclose(result.execution_prefix.course_rad, math.pi / 4, atol=1e-9)


@pytest.mark.parametrize("mirror", [False, True])
def test_recorded_starboard_activation_prefix_has_no_initial_counter_turn(mirror):
    case = json.loads((Path(__file__).parent / "fixtures/original_gnc/mid-e0-activation-prefix.json").read_text())
    state = np.array(case["state"])
    if mirror:
        points = np.array(case["constraint"]["points_ne_m"])
        case["constraint"]["points_ne_m"] = (state[:2] + (points - state[:2])[:, ::-1]).tolist()
        case["target_course_rad"] = 2 * state[2] - case["target_course_rad"]
    prefix = compile_retained_prefix(
        RetainedRouteConstraint(**case["constraint"]),
        state,
        horizon_steps=80,
        dt_s=5.0,
        max_speed_mps=8.0,
        rot_max_rad_s=math.radians(1.2),
        accel_max_mps2=0.3,
        target_course_rad=case["target_course_rad"],
    )
    assert (max(prefix.course_rad) <= state[2] + 1e-9) if mirror else (min(prefix.course_rad) >= state[2] - 1e-9)


def test_retained_narrow_corridor_seeds_braking_without_relaxing_safety():
    problem = MidMpcProblem(
        own_ship=MidMpcOwnShip(0.0, 8.0),
        route_bearing_rad=0.0,
        planned_speed_mps=8.0,
        heading_bounds_rad=(-math.pi / 2, math.pi / 2),
        speed_bounds_mps=(0.0, 8.0),
        cpa_safe_m=250.0,
        cpa_hard_m=240.0,
        rot_max_rad_s=math.radians(1.2),
        decel_max_mps2=0.3,
        lateral_active=False,
        preferred_side=0,
        starboard_asymmetry_active=False,
        min_alteration_rad=0.0,
        route_frame=MidMpcRouteFrame((0.0, 0.0), (0.0, 1.0), 0.0, 1000.0, 1.0),
        row_schedule=MidMpcRowSchedule(cpa_hard_windows=(MidMpcHardWindow(0, 80),)),
        prefix_active_k=5,
        prefix_psi_rad=(0.0,) * 5,
        prefix_u_mps=(8.0,) * 5,
        targets=(MidMpcTarget(1400.0, 0.0, 0.0, 2.5),),
        route_constraint_points_m=((0.0, 0.0), (5000.0, 0.0)),
        route_constraint_limit_m=200.0,
    )
    result = MidMpcIpoptSolver(MidMpcConfig(horizon_steps=80, strict_slack_bounds=True, max_wall_time_s=15)).solve(problem)
    assert result.seed_max_constraint_violation < 1e-6
    assert result.status in {MidMpcStatus.CONVERGED, MidMpcStatus.FEASIBLE_NONOPTIMAL}
    assert result.max_constraint_violation < 1e-3
    np.testing.assert_allclose(result.prepared.x0[80:85], 8.0)
    assert np.min(result.prepared.x0[85:160]) < 6.0


def test_native_guidance_target_accounts_for_measured_response_without_changing_lifecycle():
    route = RetainedRouteConstraint(
        "accepted", ((0.0, 0.0), (5000.0, 0.0)), (7.0, 7.0), ("cruise", "cruise"), 160.0, 32.0, 480.0
    )
    original = replace(_planner_input(), execution_route_constraint=route)
    lifecycle = EncounterLifecycle()
    for sequence, time_s in enumerate((0.0, 5.0)):
        cycle = _cycle(original, sequence=sequence, sim_time_s=time_s)
        cycle = replace(
            cycle,
            ownship=replace(
                cycle.ownship,
                maneuverability=replace(cycle.ownship.maneuverability, course_time_constant_s=86.7839162612874),
            ),
        )
        snapshot = lifecycle.step(cycle)
    plain = MidMpcProblemAssembler().assemble(_request(original, snapshot))
    modeled = MidMpcProblemAssembler().assemble(
        _request(replace(original, ownship_course_time_constant_s=86.7839162612874), snapshot)
    )
    assert isinstance(plain, AssemblySuccess)
    assert isinstance(modeled, AssemblySuccess)
    target = snapshot.targets[0]
    assert abs(modeled.problem.route_bearing_rad - target.baseline_course_rad) > abs(
        plain.problem.route_bearing_rad - target.baseline_course_rad
    )
    assert modeled.problem.row_schedule.course_bounds_rad == plain.problem.row_schedule.course_bounds_rad
    assert modeled.problem.min_alteration_rad == plain.problem.min_alteration_rad


def test_native_recovery_waits_for_measured_speed_instead_of_assuming_cruise():
    original = _planner_input()
    original = replace(
        original,
        tracks=(replace(original.tracks[0], state_enu=np.array([600.0, 0.0, 2.5, 0.0])),),
        execution_route_constraint=RetainedRouteConstraint(
            "accepted", ((0.0, 0.0), (5000.0, 0.0)), (7.0, 7.0), ("cruise", "cruise"), 160.0, 32.0, 480.0
        ),
    )
    lifecycle = EncounterLifecycle()
    lifecycle.step(_cycle(original, sequence=0, sim_time_s=0.0))
    snapshot = lifecycle.step(_cycle(original, sequence=1, sim_time_s=5.0))
    cruise = MidMpcProblemAssembler().assemble(_request(original, snapshot))
    slow_state = original.ownship_state.copy()
    slow_state[3] = 4.0
    slow = MidMpcProblemAssembler().assemble(_request(replace(original, ownship_state=slow_state), snapshot))
    assert isinstance(cruise, AssemblySuccess)
    assert isinstance(slow, AssemblySuccess)
    assert slow.horizon_encounter_plan.recovery_from_k > cruise.horizon_encounter_plan.recovery_from_k
    assert slow.problem.cpa_hard_m == cruise.problem.cpa_hard_m
    assert slow.problem.row_schedule.cpa_hard_windows[0].stop_k == 80


@pytest.mark.parametrize(
    ("bounds", "measured", "prefix", "expected_first"),
    [((6.5, 8.0), 3.2, (4.5,) * 15, 6.0), ((0.0, 3.0), 8.0, (7.0,) + (6.0,) * 14, 4.5)],
)
def test_retained_prefix_speed_boundary_remains_reachable(bounds, measured, prefix, expected_first):
    problem = replace(
        _slow_hull_problem(speed_bounds=bounds, u_mps=measured),
        decel_max_mps2=0.3,
        prefix_active_k=len(prefix),
        prefix_psi_rad=(0.0,) * len(prefix),
        prefix_u_mps=prefix,
        route_constraint_points_m=((0.0, 0.0), (5000.0, 0.0)),
        route_constraint_limit_m=480.0,
    )
    config = MidMpcConfig(horizon_steps=80, strict_slack_bounds=True, max_wall_time_s=15)
    result = MidMpcIpoptSolver(config).solve(problem)
    assert result.status in {MidMpcStatus.CONVERGED, MidMpcStatus.FEASIBLE_NONOPTIMAL}
    assert result.max_constraint_violation < 1e-4
    speeds = result.raw_x[80:160]
    np.testing.assert_allclose(speeds[:15], prefix, atol=1e-5)
    assert np.max(np.abs(np.diff(np.r_[measured, speeds]))) <= 1.5 + 1e-5
    bound = result.prepared.lbx if bounds[0] else result.prepared.ubx
    assert bound[95] == pytest.approx(expected_first)


def test_retained_prefix_does_not_invent_a_uniform_speed_feasibility_gap():
    state = np.array([6957000.0, 39000.0, math.pi / 4, 8.0, 0.0, 0.0])
    constraint = RetainedRouteConstraint(
        "mission", ((6957000.0, 39000.0), (6960900.0, 42900.0)), (8.0, 8.0), ("cruise", "cruise"), 161.0, 32.0, 480.0
    )
    prefix = compile_retained_prefix(
        constraint, state, horizon_steps=80, dt_s=5.0, max_speed_mps=8.0, rot_max_rad_s=math.radians(1.2), accel_max_mps2=0.3
    )
    assert max(prefix.speed_mps) <= 8.0 + 1e-9
    assert np.max(np.abs(np.diff(np.r_[8.0, prefix.speed_mps]))) <= 1.5 + 1e-9
    end = state[:2] + 5 * np.array(
        [
            np.sum(np.array(prefix.speed_mps) * np.cos(prefix.course_rad)),
            np.sum(np.array(prefix.speed_mps) * np.sin(prefix.course_rad)),
        ]
    )
    np.testing.assert_allclose(end, prefix.points_ne_m[-1], atol=1e-7)
    assert np.linalg.norm(end - state[:2]) == pytest.approx(161.0)


def test_recorded_near_shore_recovery_keeps_only_the_required_prefix():
    path = Path(__file__).parent / "fixtures/original_gnc/mid-e4-recovery-prefix.json.gz"
    case = json.loads(gzip.decompress(path.read_bytes()))
    values = case["problem"]
    schedule = values.pop("row_schedule")
    schedule["cpa_hard_windows"] = tuple(MidMpcHardWindow(**window) for window in schedule["cpa_hard_windows"])
    for key in ("direction_hard_window", "min_alt_hard_window"):
        if schedule[key] is not None:
            schedule[key] = MidMpcHardWindow(**schedule[key])
    for key, constructor in (
        ("own_ship", MidMpcOwnShip),
        ("route_frame", MidMpcRouteFrame),
        ("route_objective", MidMpcRouteObjective),
        ("static_field", MidMpcStaticField),
    ):
        if values[key] is not None:
            values[key] = constructor(**values[key])
    values["targets"] = tuple(MidMpcTarget(**target) for target in values["targets"])
    values["row_schedule"] = MidMpcRowSchedule(**schedule)
    problem = MidMpcProblem(**values)
    prefix = compile_retained_prefix(
        RetainedRouteConstraint(**case["constraint"]),
        np.array(case["state"]),
        horizon_steps=80,
        dt_s=5.0,
        max_speed_mps=8.0,
        rot_max_rad_s=problem.rot_max_rad_s,
        accel_max_mps2=problem.decel_max_mps2,
    )
    assert prefix.retained_point_count == len(prefix.points_ne_m)
    problem = replace(
        problem, prefix_active_k=len(prefix.course_rad), prefix_psi_rad=prefix.course_rad, prefix_u_mps=prefix.speed_mps
    )
    result = MidMpcIpoptSolver(MidMpcConfig(horizon_steps=80, strict_slack_bounds=True, max_wall_time_s=15)).solve(problem)
    assert case["original_max_violation"] > 0.4
    assert result.status in {MidMpcStatus.CONVERGED, MidMpcStatus.FEASIBLE_NONOPTIMAL}
    assert result.max_constraint_violation < 1e-4


def test_unconfirmed_overtaking_does_not_publish_an_arbitrary_passing_side():
    original = _planner_input()
    own = replace(
        original,
        sim_time_s=0.0,
        tracks=(
            replace(original.tracks[0], state_enu=np.array([1200.0, 0.0, 2.5, 0.0]), observed_at_s=0.0, generated_at_s=0.0),
        ),
        execution_route_constraint=RetainedRouteConstraint(
            "mission", ((0.0, 0.0), (5000.0, 0.0)), (7.0, 7.0), ("cruise", "cruise"), 160.0, 32.0, 480.0
        ),
    )
    snapshot = EncounterLifecycle().step(_cycle(own, sequence=0, sim_time_s=0.0))
    assert snapshot.targets[0].risk is RiskPhase.CANDIDATE
    assembled = MidMpcProblemAssembler().assemble(_request(own, snapshot))
    assert isinstance(assembled, AssemblySuccess)
    result = MidMpcIpoptSolver(MidMpcConfig(horizon_steps=80, strict_slack_bounds=True, max_wall_time_s=15)).solve(
        assembled.problem
    )
    assert result.status in {MidMpcStatus.CONVERGED, MidMpcStatus.FEASIBLE_NONOPTIMAL}
    assert result.max_constraint_violation < 1e-4
    np.testing.assert_allclose(result.raw_x[:80], 0.0, atol=1e-6)
    assert min(result.raw_x[80:160]) < 7.0
    assert assembled.problem.route_constraint_limit_m == 480.0


@pytest.mark.parametrize("case_index", [0, 1, 2, 3])
def test_recorded_recovery_interception_has_a_rate_feasible_prefix(case_index):
    cases = json.loads((Path(__file__).parent / "fixtures/original_gnc/mid-recovery-interceptions.json").read_text())
    case = cases[case_index]
    state = np.array(case["state"])
    prefix = compile_retained_prefix(
        RetainedRouteConstraint(**case["constraint"]),
        state,
        horizon_steps=80,
        dt_s=5.0,
        max_speed_mps=8.0,
        rot_max_rad_s=math.radians(1.2),
        accel_max_mps2=0.3,
        target_course_rad=case.get("target_course_rad"),
    )
    if case.get("target_course_rad") is None:
        assert prefix.retained_point_count == len(prefix.points_ne_m)
    speed = np.array(prefix.speed_mps)
    course = np.array(prefix.course_rad)
    assert np.max(np.abs(np.diff(np.r_[state[3], speed]))) <= 1.5 + 1e-9
    assert np.max(np.abs(np.diff(np.r_[state[2], course]))) <= math.radians(1.2) * 5.0 + 1e-9
    end = state[:2] + 5.0 * np.array([np.sum(speed * np.cos(course)), np.sum(speed * np.sin(course))])
    np.testing.assert_allclose(end, prefix.points_ne_m[-1], atol=1e-6)
    if "onset_offset_s" in case:
        actual_course = np.interp(case["onset_offset_s"], np.arange(len(course) + 1) * 5.0, np.r_[state[2], course])
        assert actual_course - case["baseline_course_rad"] >= math.radians(1.0)


def test_native_cpa_braking_preserves_published_steerage_floor():
    problem = replace(
        _slow_hull_problem(speed_bounds=(6.4, 8.0), u_mps=4.0),
        row_schedule=MidMpcRowSchedule(cpa_hard_windows=(MidMpcHardWindow(0, 80),)),
        cpa_braking_floor_mps=3.0,
    )
    config = MidMpcConfig(horizon_steps=80, strict_slack_bounds=True)
    prepared = _prepare(config, problem, _row_layout(config, 1, 0))
    np.testing.assert_allclose(prepared.lbx[80:160], 3.0)
    legacy = _prepare(config, replace(problem, cpa_braking_floor_mps=0.0), _row_layout(config, 1, 0))
    np.testing.assert_allclose(legacy.lbx[80:160], 0.0)


def test_transit_problem_requires_an_admissible_free_suffix():
    problem = replace(
        _slow_hull_problem(speed_bounds=(0.0, 8.0), u_mps=1.0),
        planned_speed_mps=0.0,
        prefix_active_k=5,
        prefix_psi_rad=(0.0,) * 5,
        prefix_u_mps=(1.0,) * 5,
        route_constraint_points_m=((0.0, 0.0), (5000.0, 0.0)),
        route_constraint_limit_m=480.0,
        route_suffix_min_extent_m=32.0,
    )
    result = MidMpcIpoptSolver(MidMpcConfig(horizon_steps=80, strict_slack_bounds=True, max_wall_time_s=15)).solve(problem)
    assert result.status in {MidMpcStatus.CONVERGED, MidMpcStatus.FEASIBLE_NONOPTIMAL}
    assert result.max_constraint_violation < 1e-4
    x = np.cumsum(result.raw_x[80:160] * np.cos(result.raw_x[:80]) * 5.0)
    y = np.cumsum(result.raw_x[80:160] * np.sin(result.raw_x[:80]) * 5.0)
    assert np.max(np.hypot(x[5:] - 25.0, y[5:])) >= 32.0


def test_route_update_envelope_allows_longitudinal_extension():
    # GNC measures lateral distance to supporting lines, not distance to the
    # finite reference endpoint. A straight extension has zero lateral change.
    problem = replace(
        _slow_hull_problem(speed_bounds=(3.0, 8.0), u_mps=4.0),
        planned_speed_mps=4.0,
        route_constraint_points_m=((0.0, 0.0), (100.0, 0.0)),
        route_constraint_limit_m=480.0,
        route_suffix_min_extent_m=32.0,
    )
    result = MidMpcIpoptSolver(MidMpcConfig(horizon_steps=80, strict_slack_bounds=True, max_wall_time_s=15)).solve(problem)
    assert result.status in {MidMpcStatus.CONVERGED, MidMpcStatus.FEASIBLE_NONOPTIMAL}
    assert result.seed_max_constraint_violation < 1e-6
    assert result.max_constraint_violation < 1e-4
    lateral = replace(problem, route_constraint_points_m=((0.0, 1000.0), (100.0, 1000.0)))
    rejected = MidMpcIpoptSolver(MidMpcConfig(horizon_steps=80, strict_slack_bounds=True, max_wall_time_s=2)).solve(lateral)
    assert rejected.max_constraint_violation > 100.0  # padding must not create a fictitious zero-distance line


def test_recorded_active_shore_transition_does_not_duplicate_update_distance():
    path = Path(__file__).parent / "fixtures/original_gnc/mid-active-shore-transition.json.gz"
    case = json.loads(gzip.decompress(path.read_bytes()))
    values = case["problem"]
    schedule = values.pop("row_schedule")
    schedule["cpa_hard_windows"] = tuple(MidMpcHardWindow(**window) for window in schedule["cpa_hard_windows"])
    for key in ("direction_hard_window", "min_alt_hard_window"):
        if schedule[key] is not None:
            schedule[key] = MidMpcHardWindow(**schedule[key])
    for key, constructor in (
        ("own_ship", MidMpcOwnShip),
        ("route_frame", MidMpcRouteFrame),
        ("route_objective", MidMpcRouteObjective),
        ("static_field", MidMpcStaticField),
    ):
        if values[key] is not None:
            values[key] = constructor(**values[key])
    values["targets"] = tuple(MidMpcTarget(**target) for target in values["targets"])
    values["row_schedule"] = MidMpcRowSchedule(**schedule)
    problem = MidMpcProblem(**values)
    prefix = compile_retained_prefix(
        RetainedRouteConstraint(**case["constraint"]),
        np.array(case["state"]),
        horizon_steps=80,
        dt_s=5.0,
        max_speed_mps=8.0,
        rot_max_rad_s=problem.rot_max_rad_s,
        accel_max_mps2=problem.decel_max_mps2,
        target_course_rad=case["target_course_rad"],
    )
    assert prefix.retained_point_count < len(prefix.points_ne_m)
    problem = replace(
        problem, prefix_active_k=len(prefix.course_rad), prefix_psi_rad=prefix.course_rad, prefix_u_mps=prefix.speed_mps
    )
    solver = MidMpcIpoptSolver(MidMpcConfig(horizon_steps=80, strict_slack_bounds=True, max_wall_time_s=15))
    solver.prewarm_capacity(1, static_field=problem.static_field, retained_route=True)
    result = solver.solve(problem)
    assert result.graph_cache_hit
    assert result.graph_build_elapsed_ms == 0.0
    assert case["original_max_violation"] > 0.1
    assert result.status in {MidMpcStatus.CONVERGED, MidMpcStatus.FEASIBLE_NONOPTIMAL}
    assert result.max_constraint_violation < 1e-4



def test_retained_interception_cannot_invent_sub_steerage_motion():
    path = Path(__file__).parent / "fixtures/original_gnc/retained-steerage-floor.json.gz"
    case = json.loads(gzip.decompress(path.read_bytes()))
    state = np.array(case["state"])
    prefix = compile_retained_prefix(
        RetainedRouteConstraint(**case["constraint"]), state,
        horizon_steps=80, dt_s=5.0, max_speed_mps=8.0,
        rot_max_rad_s=math.radians(1.2), accel_max_mps2=0.3, min_speed_mps=3.0,
    )
    assert min(prefix.speed_mps) >= min(3.0, np.linalg.norm(state[3:5])) - 1e-9


def test_retained_anchor_refines_integer_grid_without_relaxing_steerage():
    path = Path(__file__).parent / "fixtures/original_gnc/retained-anchor-timing.json.gz"
    case = json.loads(gzip.decompress(path.read_bytes()))
    state = np.array(case["state"])
    prefix = compile_retained_prefix(
        RetainedRouteConstraint(**case["constraint"]), state,
        horizon_steps=80, dt_s=5.0, max_speed_mps=8.0,
        rot_max_rad_s=math.radians(1.2), accel_max_mps2=0.3, min_speed_mps=3.0,
    )
    assert min(prefix.speed_mps) >= min(3.0, np.linalg.norm(state[3:5])) - 1e-9


def test_native_acknowledged_route_owns_continuity_instead_of_old_time_projection(monkeypatch):
    from colav_simulator.core.colav.rolling_plan import PlanRevisionReason, RollingPlanReference
    from colav_simulator.integrations.mid_mpc_ipopt import _active_capability

    base = _planner_input()
    data = replace(base, execution_route_constraint=RetainedRouteConstraint(
        'mission',((0.,0.),(5000.,0.)),(8.,8.),('cruise','cruise'),160.,32.,480.))
    lifecycle = EncounterLifecycle()
    snapshot = lifecycle.step(_cycle(data,sequence=0,sim_time_s=0.))
    facade = create(context=FactoryContext('mid_mpc_ipopt',0))._solve.__self__
    reference = RollingPlanReference(True,PlanRevisionReason.CONTINUITY_PRESERVED,0.,5.,None,
        (0.,)*80,(8.,)*80,(100.,)*80,80)
    monkeypatch.setattr(facade._rolling_plan,'reference',lambda **kwargs: reference)
    _, native, _, _ = facade._rolling_reference(data,snapshot,_active_capability(data,facade._config))
    assert not native.active
    assert native.revision_reason.value == 'NATIVE_RETAINED_ROUTE'
    assert not any(native.objective_weight)
    _, ordinary, _, _ = facade._rolling_reference(base,snapshot,_active_capability(base,facade._config))
    assert ordinary is reference


def test_retained_prefix_matches_the_route_heading_at_the_spatial_join():
    case_path = Path(__file__).parent / "fixtures/original_gnc/retained-heading-join.json.gz"
    with gzip.open(case_path, "rt") as stream:
        case = json.load(stream)
    turn_limit = math.radians(1.2) * 5.0
    prefix = compile_retained_prefix(
        RetainedRouteConstraint(**case["constraint"]),
        np.array(case["state"]),
        horizon_steps=80,
        dt_s=5.0,
        max_speed_mps=8.0,
        rot_max_rad_s=math.radians(1.2),
        accel_max_mps2=0.3,
        min_speed_mps=3.0,
    )
    difference = prefix.course_rad[-1] - prefix.incoming_course_rad
    assert abs(math.atan2(math.sin(difference), math.cos(difference))) <= turn_limit + 1e-9
    assert min(prefix.speed_mps) >= 3.0
