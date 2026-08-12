from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from shapely.geometry import box

from colav_simulator.core.colav.custom_mpc_adapter import FactoryContext, PlannerInput, TrackedObstacle
from colav_simulator.integrations import IntegrationRegistry, potocnik_colreg_mpc
from colav_simulator.integrations.potocnik_colreg_mpc import (
    PotocnikColregFanMPC,
    PotocnikColregParams,
    _continuous_minimum_distance,
    _Policy,
)


def track(
    *,
    target_id: int = 1,
    position_ne: tuple[float, float],
    velocity_ne: tuple[float, float],
) -> TrackedObstacle:
    return TrackedObstacle(
        target_id=target_id,
        state_enu=np.array([*position_ne, *velocity_ne]),
        covariance=np.zeros((4, 4)),
        length_m=8.45,
        width_m=3.0,
        observed_at_s=0.0,
        age_s=0.0,
    )


def planner_input(
    target: TrackedObstacle | None = None,
    *,
    enc=None,
    ownship_state: np.ndarray | None = None,
) -> PlannerInput:
    return PlannerInput(
        sim_time_s=0.0,
        dt_sim_s=0.5,
        waypoints_enu_m=np.array([[0.0, 10000.0], [0.0, 0.0]]),
        speed_plan_mps=np.array([7.0, 7.0]),
        ownship_state=(np.array([0.0, 0.0, 0.0, 7.0, 0.0, 0.0]) if ownship_state is None else ownship_state),
        tracks=() if target is None else (target,),
        enc=enc,
        goal_state=None,
        disturbance=None,
        algorithm_seed=9,
        ownship_length_m=8.45,
        ownship_width_m=3.0,
        ownship_draft_m=0.5,
    )


def solver() -> PotocnikColregFanMPC:
    return PotocnikColregFanMPC(PotocnikColregParams(collision_distance_m=150.0))


def test_head_on_commands_substantial_starboard_action() -> None:
    solution = solver().solve(planner_input(track(position_ne=(1000.0, 0.0), velocity_ne=(-7.0, 0.0))))

    assert solution.algorithm_details["active_encounters"] == ["head_on"]
    assert np.rad2deg(solution.control_reference[2, 0]) >= 5.0
    assert solution.control_trajectory is not None
    assert solution.control_trajectory[2, 0] == pytest.approx(solution.control_reference[2, 0])
    assert solution.constraints["colreg_policy"]["starboard_required"] is True
    assert solution.constraints["colreg_policy"]["relaxations"] == []


def test_overtaking_commands_substantial_starboard_action() -> None:
    solution = solver().solve(
        planner_input(track(position_ne=(1000.0, 0.0), velocity_ne=(5.0, 0.0)))
    )

    assert solution.algorithm_details["active_encounters"] == ["overtaking"]
    assert np.rad2deg(solution.control_reference[2, 0]) >= 5.0
    assert solution.constraints["colreg_policy"]["starboard_required"] is True
    assert solution.constraints["colreg_policy"]["relaxations"] == []


def test_replan_holds_starboard_command_instead_of_accumulating_turn() -> None:
    colreg_solver = solver()
    head_on = track(position_ne=(2000.0, 0.0), velocity_ne=(-7.0, 0.0))
    first = colreg_solver.solve(planner_input(head_on))
    second_input = planner_input(
        track(position_ne=(1930.0, 0.0), velocity_ne=(-7.0, 0.0)),
        ownship_state=np.array([35.0, 2.0, np.deg2rad(7.0), 7.0, 0.0, 0.0]),
    )

    second = colreg_solver.solve(second_input)

    assert np.rad2deg(first.control_reference[2, 0]) == pytest.approx(5.0)
    assert 5.0 <= np.rad2deg(second.control_reference[2, 0]) <= 5.5


def test_replan_keeps_early_selected_path_close_to_shifted_previous_plan() -> None:
    colreg_solver = solver()
    first = colreg_solver.solve(planner_input(track(position_ne=(2000.0, 0.0), velocity_ne=(-7.0, 0.0))))
    second = colreg_solver.solve(
        planner_input(
            track(position_ne=(1965.0, 0.0), velocity_ne=(-7.0, 0.0)),
            ownship_state=first.predicted_trajectory[:6, 1].copy(),
        )
    )

    early_plan_deviation = np.mean(
        np.linalg.norm(
            second.predicted_trajectory[:2, :4] - first.predicted_trajectory[:2, 1:5],
            axis=0,
        )
    )
    assert early_plan_deviation < 2.0
    assert second.algorithm_details["trajectory_continuity_score"] < 0.01


def test_clear_encounter_enters_return_then_recaptures_route() -> None:
    colreg_solver = solver()
    avoidance = colreg_solver.solve(planner_input(track(position_ne=(1000.0, 0.0), velocity_ne=(-7.0, 0.0))))
    returning = colreg_solver.solve(
        planner_input(
            ownship_state=np.array([35.0, 3.0, np.deg2rad(5.0), 7.0, 0.0, 0.0]),
        )
    )
    recaptured = colreg_solver.solve(
        planner_input(
            ownship_state=np.array([70.0, 5.0, np.deg2rad(2.0), 7.0, 0.0, 0.0]),
        )
    )

    assert avoidance.algorithm_details["maneuver_phase"] == "AVOID"
    assert returning.algorithm_details["maneuver_phase"] == "RETURN"
    assert abs(returning.control_reference[2, 0]) < abs(avoidance.control_reference[2, 0])
    assert recaptured.algorithm_details["maneuver_phase"] == "TRACK"


def test_nominal_speed_recovers_after_slowdown() -> None:
    solution = solver().solve(planner_input(ownship_state=np.array([0.0, 0.0, 0.0, 3.0, 0.0, 0.0])))

    assert solution.control_reference[3, 0] == pytest.approx(7.0)
    assert solution.algorithm_details["selected_speed_scale"] == pytest.approx(1.0)


def test_crossing_give_way_turns_starboard_and_passes_astern() -> None:
    solution = solver().solve(planner_input(track(position_ne=(500.0, 500.0), velocity_ne=(0.0, -7.0))))

    policy = solution.constraints["colreg_policy"]
    assert solution.algorithm_details["active_encounters"] == ["crossing_give_way"]
    assert np.rad2deg(solution.control_reference[2, 0]) >= 5.0
    assert policy["selected_passes_astern"] is True
    assert policy["relaxations"] == []


def test_crossing_stand_on_holds_course_and_speed_while_nominal_is_safe() -> None:
    solution = solver().solve(planner_input(track(position_ne=(500.0, -800.0), velocity_ne=(0.0, 7.0))))

    assert solution.algorithm_details["active_encounters"] == ["crossing_stand_on"]
    assert solution.algorithm_details["nominal_candidate_feasible"] is True
    assert solution.control_reference[2, 0] == pytest.approx(0.0)
    assert solution.control_reference[3, 0] == pytest.approx(7.0)
    assert solution.constraints["colreg_policy"]["relaxations"] == []


def test_stand_on_replan_corrects_back_to_locked_course() -> None:
    colreg_solver = solver()
    first = colreg_solver.solve(planner_input(track(position_ne=(500.0, -1000.0), velocity_ne=(0.0, 7.0))))
    second = colreg_solver.solve(
        planner_input(
            track(position_ne=(500.0, -965.0), velocity_ne=(0.0, 7.0)),
            ownship_state=np.array([35.0, 0.0, np.deg2rad(3.0), 7.0, 0.0, 0.0]),
        )
    )

    assert first.control_reference[2, 0] == pytest.approx(0.0)
    assert abs(np.rad2deg(second.control_reference[2, 0])) <= 0.25


def test_stand_on_course_is_captured_before_simultaneous_give_way_maneuver(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    classifications = iter(
        (
            ("crossing_stand_on", 100.0, 100.0, 100.0, -45.0),
            ("crossing_give_way", 100.0, 100.0, 100.0, 45.0),
            ("clear", 1000.0, 60.0, 60.0, -45.0),
            ("crossing_stand_on", 100.0, 50.0, 50.0, -45.0),
        )
    )
    monkeypatch.setattr(
        potocnik_colreg_mpc,
        "classify_geometry",
        lambda *_args: next(classifications),
    )
    colreg_solver = solver()
    initial = replace(
        planner_input(),
        tracks=(
            track(target_id=1, position_ne=(500.0, -500.0), velocity_ne=(0.0, 7.0)),
            track(target_id=2, position_ne=(500.0, 500.0), velocity_ne=(0.0, -7.0)),
        ),
    )

    colreg_solver._encounter_policy(initial)
    colreg_solver._maneuver_phase = "AVOID"
    colreg_solver._encounter_policy(
        planner_input(
            track(position_ne=(700.0, -700.0), velocity_ne=(0.0, 7.0)),
            ownship_state=np.array([50.0, 50.0, np.deg2rad(30.0), 7.0, 0.0, 0.0]),
        )
    )
    after_avoidance = planner_input(
        track(position_ne=(500.0, -500.0), velocity_ne=(0.0, 7.0)),
        ownship_state=np.array([100.0, 100.0, np.deg2rad(45.0), 7.0, 0.0, 0.0]),
    )
    colreg_solver._encounter_policy(after_avoidance)

    assert colreg_solver._stand_on_course == pytest.approx(0.0)


def test_return_moves_toward_pre_maneuver_stand_on_course_with_rate_limit() -> None:
    colreg_solver = solver()
    colreg_solver._stand_on_course = 0.0
    colreg_solver._previous_command_course = np.deg2rad(45.0)
    colreg_solver._maneuver_phase = "RETURN"
    candidates, controls = colreg_solver._generate_candidate_bundle(
        np.array([0.0, 0.0, np.deg2rad(45.0), 7.0, 0.0, 0.0]),
        7.0,
        0.5,
        command_course_center=colreg_solver._previous_command_course,
    )
    count = colreg_solver.params.candidate_count
    policy = _Policy(
        encounters=(),
        give_way_targets=(),
        crossing_give_way_targets=(),
        stand_on_targets=(1,),
        starboard_required=False,
    )

    selection = colreg_solver._select_candidate(
        controls=controls,
        speed_scales=np.ones(count),
        feasible_indices=np.arange(count),
        minimum_clearance=np.full(count, np.inf),
        minimum_static_clearance=np.full(count, np.inf),
        pass_astern=np.ones(count, dtype=bool),
        policy=policy,
        ownship_course=np.deg2rad(45.0),
        target_course=np.deg2rad(-80.0),
        nominal_feasible=True,
        candidates=candidates,
        sim_time_s=5.0,
        route_speed_mps=7.0,
    )

    selected_course_deg = np.rad2deg(controls[selection.index, 2, 0])
    assert selected_course_deg == pytest.approx(40.0)


def test_return_prioritizes_route_recapture_within_hard_safe_candidates() -> None:
    colreg_solver = solver()
    colreg_solver._previous_command_course = np.deg2rad(45.0)
    colreg_solver._maneuver_phase = "RETURN"
    candidates, controls = colreg_solver._generate_candidate_bundle(
        np.array([0.0, 0.0, np.deg2rad(45.0), 7.0, 0.0, 0.0]),
        7.0,
        0.5,
        command_course_center=colreg_solver._previous_command_course,
    )
    route_candidate = 11
    away_candidate = 33
    minimum_clearance = np.full(colreg_solver.params.candidate_count, np.inf)
    minimum_clearance[route_candidate] = 160.0
    policy = _Policy(
        encounters=(),
        give_way_targets=(),
        crossing_give_way_targets=(),
        stand_on_targets=(),
        starboard_required=False,
    )

    selection = colreg_solver._select_candidate(
        controls=controls,
        speed_scales=np.ones(colreg_solver.params.candidate_count),
        feasible_indices=np.array([route_candidate, away_candidate]),
        minimum_clearance=minimum_clearance,
        minimum_static_clearance=np.full(colreg_solver.params.candidate_count, np.inf),
        pass_astern=np.ones(colreg_solver.params.candidate_count, dtype=bool),
        policy=policy,
        ownship_course=np.deg2rad(45.0),
        target_course=np.deg2rad(-80.0),
        nominal_feasible=True,
        candidates=candidates,
        sim_time_s=5.0,
        route_speed_mps=7.0,
    )

    assert selection.index == route_candidate
    assert np.rad2deg(controls[selection.index, 2, 0]) == pytest.approx(40.0)


def test_stand_on_uses_documented_emergency_override_when_nominal_is_unsafe() -> None:
    solution = solver().solve(planner_input(track(position_ne=(500.0, -500.0), velocity_ne=(0.0, 7.0))))

    assert solution.algorithm_details["active_encounters"] == ["crossing_stand_on"]
    assert solution.algorithm_details["nominal_candidate_feasible"] is False
    assert "stand_on_emergency_override" in solution.constraints["colreg_policy"]["relaxations"]


def test_stand_on_emergency_minimizes_course_change_before_speed() -> None:
    colreg_solver = solver()
    colreg_solver._stand_on_course = 0.0
    colreg_solver._previous_command_course = np.deg2rad(45.0)
    colreg_solver._maneuver_phase = "RETURN"
    candidates, controls = colreg_solver._generate_candidate_bundle(
        np.array([0.0, 0.0, np.deg2rad(45.0), 7.0, 0.0, 0.0]),
        7.0,
        0.5,
        command_course_center=colreg_solver._previous_command_course,
    )
    toward_locked_course = 11
    full_speed_away = 22
    speed_scales = np.ones(colreg_solver.params.candidate_count)
    speed_scales[toward_locked_course] = 0.75
    policy = _Policy(
        encounters=(),
        give_way_targets=(),
        crossing_give_way_targets=(),
        stand_on_targets=(1,),
        starboard_required=False,
    )

    selection = colreg_solver._select_candidate(
        controls=controls,
        speed_scales=speed_scales,
        feasible_indices=np.array([toward_locked_course, full_speed_away]),
        minimum_clearance=np.full(colreg_solver.params.candidate_count, np.inf),
        minimum_static_clearance=np.full(colreg_solver.params.candidate_count, np.inf),
        pass_astern=np.ones(colreg_solver.params.candidate_count, dtype=bool),
        policy=policy,
        ownship_course=np.deg2rad(45.0),
        target_course=np.deg2rad(-80.0),
        nominal_feasible=False,
        candidates=candidates,
        sim_time_s=5.0,
        route_speed_mps=7.0,
    )

    assert selection.index == toward_locked_course
    assert np.rad2deg(controls[selection.index, 2, 0]) == pytest.approx(40.0)


def test_policy_releases_stale_give_way_after_safe_dcpa(monkeypatch: pytest.MonkeyPatch) -> None:
    classifications = iter(
        (
            ("crossing_give_way", 100.0, 100.0, 100.0, 45.0),
            ("clear", 1000.0, 50.0, 50.0, 45.0),
        )
    )
    monkeypatch.setattr(
        potocnik_colreg_mpc,
        "classify_geometry",
        lambda *_args: next(classifications),
    )
    colreg_solver = solver()
    target = track(position_ne=(1000.0, 0.0), velocity_ne=(5.0, 0.0))

    active = colreg_solver._encounter_policy(planner_input(target))
    released = colreg_solver._encounter_policy(planner_input(target))

    assert active.give_way_targets == (1,)
    assert released.encounters[0]["detected_geometry"] == "clear"
    assert released.encounters[0]["encounter"] == "clear"
    assert released.give_way_targets == ()


def test_policy_retains_give_way_while_dcpa_is_inside_safety_buffer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    classifications = iter(
        (
            ("crossing_give_way", 100.0, 100.0, 100.0, 45.0),
            ("clear", 100.0, 50.0, 50.0, 45.0),
        )
    )
    monkeypatch.setattr(
        potocnik_colreg_mpc,
        "classify_geometry",
        lambda *_args: next(classifications),
    )
    colreg_solver = solver()
    target = track(position_ne=(1000.0, 0.0), velocity_ne=(5.0, 0.0))

    colreg_solver._encounter_policy(planner_input(target))
    retained = colreg_solver._encounter_policy(planner_input(target))

    assert retained.encounters[0]["detected_geometry"] == "clear"
    assert retained.encounters[0]["encounter"] == "crossing_give_way"
    assert retained.give_way_targets == (1,)


def test_continuous_clearance_detects_between_sample_tunneling() -> None:
    own = np.array([[[0.0, 10.0], [0.0, 0.0]]])
    target = np.array([[5.0, 5.0], [-5.0, 5.0]])

    minimum = _continuous_minimum_distance(own, target)

    assert minimum[0] == pytest.approx(0.0)


def test_enc_hazard_filters_continuous_centerline(monkeypatch: pytest.MonkeyPatch) -> None:
    colreg_solver = solver()
    candidates, _ = colreg_solver._generate_candidate_bundle(
        planner_input().ownship_state,
        7.0,
        0.5,
    )
    hazard = box(-5.0, 20.0, 5.0, 60.0)
    monkeypatch.setattr(colreg_solver, "_grounding_hazard", lambda _input: hazard)

    feasible, clearance, active = colreg_solver._static_feasibility(
        candidates,
        planner_input(enc=object()),
    )

    nominal = colreg_solver.params.candidate_count // 2
    assert active is True
    assert not feasible[nominal]
    assert clearance[nominal] == pytest.approx(0.0)


def test_registry_loads_enhanced_profile_under_separate_identity() -> None:
    adapter = IntegrationRegistry().build_algorithm(
        "potocnik_colreg_fan_mpc",
        factory_context=FactoryContext("potocnik_colreg_fan_mpc", 7),
    )

    assert adapter is not None
    assert adapter.descriptor.algorithm_id == "potocnik_colreg_fan_mpc"
    assert adapter.descriptor.predictor_model == "bounded_course_speed_response_fan"
    assert adapter.build_identity.complete is True
    assert Path("config/potocnik_colreg_fan_mpc.yaml").is_file()
