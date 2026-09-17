"""Measured maneuver completion must stop lateral drift before route handback."""

import math
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest
from conftest import empty_enc
from test_mid_mpc_problem_assembler import _cycle, _planner_input, _request

from colav_simulator.core.colav.custom_mpc_adapter import FactoryContext
from colav_simulator.core.colav.diagnostics import PlanStatus
from colav_simulator.core.colav.encounter_lifecycle import EncounterLifecycle, PassingSide
from colav_simulator.core.colav.horizon_encounter_plan import HorizonEncounterPhase
from colav_simulator.core.colav.mid_mpc.models import MidMpcConfig, MidMpcResult, MidMpcStatus
from colav_simulator.core.colav.mid_mpc.solver import MidMpcIpoptSolver
from colav_simulator.core.colav.mid_mpc_arrival import arrival_references, navigation_capture_error
from colav_simulator.core.colav.mid_mpc_assembler import (
    AssemblySuccess,
    MidMpcProblemAssembler,
    RouteReference,
    _staged_route_references,
)
from colav_simulator.core.colav.retained_route import (
    RetainedRouteConstraint,
    compile_spliced_execution_route,
    degraded_stub_prefix,
)
from colav_simulator.integrations.mid_mpc_ipopt import _handback_mission_document, _recovery_iterate_filter, create


@pytest.mark.parametrize("side", [PassingSide.PORT, PassingSide.STARBOARD])
@pytest.mark.parametrize(
    ("offset", "crossing", "parallel"),
    [(400.0, False, True), (100.0, False, False), (400.0, True, False), (-400.0, False, False)],
)
def test_achieved_maneuver_with_clear_parallel_pass_stops_pressing_outward(side, offset, crossing, parallel):
    original = _planner_input()
    lifecycle = EncounterLifecycle()
    lifecycle.step(_cycle(original, sequence=0, sim_time_s=0.0))
    snapshot = lifecycle.step(_cycle(original, sequence=1, sim_time_s=5.0))
    sign = -1 if side is PassingSide.PORT else 1
    target = replace(snapshot.targets[0], passing_side=side, action_achieved=True, action_started=True)
    snapshot = replace(
        snapshot,
        targets=(target,),
        directive=replace(
            snapshot.directive,
            passing_side=side,
            minimum_course_change_rad=0.0,
        ),
    )
    route = RetainedRouteConstraint(
        "passing",
        ((0.0, sign * offset), (5000.0, sign * offset)),
        (7.0, 7.0),
        ("avoidance", "avoidance"),
        160.0,
        32.0,
        480.0,
    )
    track_state = original.tracks[0].state_enu.copy()
    if crossing:
        track_state[3] = sign * 4.0
    own = replace(
        original,
        execution_route_constraint=route,
        tracks=(replace(original.tracks[0], state_enu=track_state),),
        ownship_state=np.array([0.0, sign * offset, sign * math.radians(20), 7.0, 0.0, 0.0]),
    )
    result = MidMpcProblemAssembler().assemble(_request(own, snapshot))
    assert isinstance(result, AssemblySuccess)
    if parallel:
        assert result.problem.route_bearing_rad == pytest.approx(0.0)
    else:
        assert sign * result.problem.route_bearing_rad > 0.0
    # Parallel passing does not release the encounter or remove its safety rows.
    assert snapshot.targets[0].route_recovery_allowed is False
    assert result.problem.row_schedule.cpa_hard_windows[0].stop_k == 80


def test_released_encounter_does_not_hand_back_from_459_metres_off_route():
    constraint = RetainedRouteConstraint(
        "return",
        ((0.0, 0.0), (5000.0, 0.0)),
        (8.0, 8.0),
        ("avoidance", "avoidance"),
        160.0,
        32.0,
        480.0,
    )
    decisions = (SimpleNamespace(risk=SimpleNamespace(value="RELEASED")),)
    assert (
        _handback_mission_document(
            constraint,
            ((0.0, 0.0), (5000.0, 0.0)),
            (3300.0, -459.0),
            8.0,
            decisions,
        )
        is None
    )


def test_unconfirmed_give_way_does_not_publish_a_turn_opposite_its_observed_side():
    """A candidate HO must not load a port route into the protected GNC prefix."""
    own = _planner_input()
    own = replace(
        own,
        sim_time_s=0.0,
        execution_route_constraint=RetainedRouteConstraint(
            "mission",
            ((0.0, 0.0), (5000.0, 0.0)),
            (7.0, 7.0),
            ("cruise", "cruise"),
            160.0,
            32.0,
            480.0,
        ),
    )
    snapshot = EncounterLifecycle().step(_cycle(own, sequence=0, sim_time_s=0.0))
    assert snapshot.targets[0].risk.value == "CANDIDATE"
    assert snapshot.directive.minimum_course_change_rad == 0.0
    result = MidMpcProblemAssembler().assemble(_request(own, snapshot))
    assert isinstance(result, AssemblySuccess)
    assert max(result.problem.route_objective.heading_reference_rad) >= snapshot.targets[0].required_course_change_rad
    solver = MidMpcIpoptSolver(MidMpcConfig(horizon_steps=80, strict_slack_bounds=True))
    solved = solver.solve(result.problem)
    assert solved.status in {MidMpcStatus.CONVERGED, MidMpcStatus.FEASIBLE_NONOPTIMAL}
    # It may hold or turn to the observed starboard side, but must not
    # publish a port turn that the next confirmation then needs to undo.
    assert min(solved.raw_x[:80]) >= -1e-3


def test_splice_bend_after_retained_endpoint_uses_the_last_segment():
    """The free prediction may extend past the last mirrored GNC waypoint."""
    constraint = RetainedRouteConstraint(
        "short-mirror",
        ((0.0, 0.0), (300.0, 0.0), (600.0, 0.0)),
        (7.0, 7.0, 7.0),
        ("avoidance",) * 3,
        160.0,
        32.0,
        480.0,
    )
    state = np.array([0.0, 0.0, 0.0, 7.0, 0.0, 0.0])
    predicted = np.tile(state[:, None], (1, 81))
    predicted[0] = np.linspace(0.0, 1000.0, 81)
    predicted[1] = np.clip(predicted[0] - 650.0, 0.0, 100.0)
    packet = compile_spliced_execution_route(degraded_stub_prefix(constraint, state), predicted)
    points = np.asarray(packet["points_ne_m"])
    assert np.isfinite(points).all()
    assert np.max(np.abs(points[:, 1])) <= 500.0
    np.testing.assert_allclose(points[-1], constraint.points_ne_m[-1])


def test_accepted_timeout_candidate_keeps_its_compiled_execution_route(monkeypatch):
    real_solve = MidMpcIpoptSolver.solve

    def timeout(self, problem, **kwargs) -> MidMpcResult:
        result = real_solve(self, problem, **kwargs)
        assert result.status in {MidMpcStatus.CONVERGED, MidMpcStatus.FEASIBLE_NONOPTIMAL}
        return replace(
            result, status=MidMpcStatus.TIMEOUT, native_status=MidMpcStatus.TIMEOUT, accepted_by_quality_gate=False
        )

    monkeypatch.setattr(MidMpcIpoptSolver, "solve", timeout)
    adapter = create(context=FactoryContext("mid_mpc_ipopt", 0, scenario_target_count=1))
    route = RetainedRouteConstraint(
        "mission",
        ((0.0, 0.0), (5000.0, 0.0)),
        (7.0, 7.0),
        ("cruise", "cruise"),
        160.0,
        32.0,
        480.0,
    )
    adapter.plan(
        0.0,
        np.array(route.points_ne_m).T,
        np.array(route.speed_mps),
        np.array([0.0, 0.0, 0.0, 7.0, 0.0, 0.0]),
        [],
        empty_enc(),
        os_execution_route_constraint=route,
        dt=0.5,
        os_length=44.1,
        os_width=8.0,
        os_model_name="original_gnc_20260824_v2",
        os_controller_name="original_ship_control_20260824_v2",
        os_max_turn_rate_radps=math.radians(1.2),
        os_max_speed_mps=8.0,
        os_min_steerage_speed_mps=3.0,
        os_course_time_constant_s=87.0,
        os_speed_time_constant_s=24.0,
    )
    authority = adapter.get_route_authority()["planner"]
    assert authority["status"] == PlanStatus.TIMEOUT_FEASIBLE.value
    assert authority["algorithm_details"]["execution_route"] is not None
    assert authority["algorithm_details"]["accepted_plan_receipt"] is not None


def test_handback_capture_filter_checks_the_route_that_will_be_published():
    own = replace(
        _planner_input(),
        tracks=(),
        ownship_state=np.array([600.0, 5.0, 0.0, 4.0, 0.0, 0.0]),
        waypoints_enu_m=np.array([[0.0, 1000.0], [0.0, 0.0]]),
        ownship_length_m=44.1,
        execution_route_constraint=RetainedRouteConstraint(
            "mission", ((0.0, 0.0), (1000.0, 0.0)), (4.0, 4.0), ("avoidance", "avoidance"), 160.0, 32.0, 480.0
        ),
    )
    decisions = (SimpleNamespace(risk=SimpleNamespace(value="RELEASED")),)
    assembly = SimpleNamespace(
        problem=SimpleNamespace(route_objective=SimpleNamespace(terminal_position_m=None), planned_speed_mps=4.0),
        horizon_encounter_plan=SimpleNamespace(recovery_from_k=0, target_windows=()),
        grid=SimpleNamespace(control_intervals=20, dt_s=5.0),
        execution_prefix=degraded_stub_prefix(own.execution_route_constraint, own.ownship_state),
    )
    candidate = np.r_[np.full(20, 0.3), np.full(20, 4.0), 0.0, 0.0]
    document = _handback_mission_document(
        own.execution_route_constraint,
        tuple(map(tuple, own.waypoints_enu_m.T)),
        tuple(own.ownship_state[:2]),
        4.0,
        decisions,
    )
    assert document is not None
    check = _recovery_iterate_filter(own, assembly, decisions=decisions)
    assert check(candidate) is True
    # Without a released handback, the same off-line arrival stays rejected.
    assert _recovery_iterate_filter(own, assembly)(candidate) is False


@pytest.mark.parametrize("measured_speed", [3.0, 7.0])
def test_native_recovery_lookahead_covers_qualified_course_response(measured_speed):
    original = _planner_input()
    snapshot = EncounterLifecycle().step(_cycle(original, sequence=0, sim_time_s=0.0))
    snapshot = replace(
        snapshot,
        targets=(),
        directive=replace(
            snapshot.directive, required_targets=(), passing_side=PassingSide.NONE, minimum_course_change_rad=0.0
        ),
    )
    own = replace(
        original,
        sim_time_s=0.0,
        tracks=(),
        ownship_state=np.array([600.0, 300.0, 0.0, measured_speed, 0.0, 0.0]),
        ownship_course_time_constant_s=87.0,
        execution_route_constraint=RetainedRouteConstraint(
            "mission", ((0.0, 0.0), (5000.0, 0.0)), (7.0, 7.0), ("cruise", "cruise"), 160.0, 32.0, 480.0
        ),
    )
    request = _request(own, snapshot)
    request = replace(request, route=replace(request.route, mission_waypoints_ne_m=((0.0, 0.0), (5000.0, 0.0))))
    assembled = MidMpcProblemAssembler().assemble(request)
    assert isinstance(assembled, AssemblySuccess)
    assert assembled.problem.navigation_recovery_lookahead_m >= 87.0 * request.route.planned_speed_mps


def test_navigation_reference_remains_on_mission_after_arrival_entry():
    mission = ((0.0, 0.0), (5515.0, 0.0))
    origin = np.array([3800.0, 140.0])
    headings, _, speeds, _ = arrival_references(
        mission,
        tuple(origin),
        math.radians(27.0),
        6.2,
        8.0,
        5.0,
        80,
        0.08,
        math.radians(1.2),
        87.0,
        (3800.0, 0.0),
        0.0,
        arrival_radius_m=308.7,
        navigation_lookahead_m=696.0,
    )
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
    assert abs(positions[-1, 1]) <= 20.0


def test_timed_recovery_does_not_repeat_the_current_state_as_first_future_knot():
    course = math.radians(-25.0)
    plan = SimpleNamespace(
        mission_route_bearing_rad=0.0,
        avoidance_corridor_bearing_rad=course,
        phases=(HorizonEncounterPhase.RECOVER,) * 81,
        corridor_reference_rad=(),
    )
    route = RouteReference(
        anchor_ne_m=(0.0, 1500.0),
        bearing_rad=1.5,
        mission_leg_bearing_rad=0.0,
        planned_speed_mps=4.63,
        mission_waypoints_ne_m=((-1800.0, 3600.0), (-1800.0, 1500.0), (1400.0, 1500.0), (1900.0, 2250.0)),
    )
    headings, _ = _staged_route_references(
        plan,
        route,
        ownship_position_ne_m=(0.0, 0.0),
        ownship_heading_rad=course,
        planned_speed_mps=4.63,
        dt_s=5.0,
        rot_max_rad_s=math.radians(1.2),
        heading_window_rad=math.pi / 2,
        recovery_lookahead_m=696.0,
        timed_execution=True,
    )
    assert headings[0] > course
    assert headings[0] - course <= math.radians(6.0) + 1e-12
