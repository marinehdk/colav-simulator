"""Planner-side envelope handling for the original GNC backend (P2 planner track).

Measured original response: course tau 86.78 s, speed tau 24.07 s, manager yaw
cap 1.2 deg/s, guidance avoidance surge cap 3.2 m/s, steerage floor 3.0 m/s.
"""

from __future__ import annotations

import numpy as np
import pytest

from colav_simulator.core.colav.custom_mpc_adapter import (
    PlannerInput,
    TrackedObstacle,
    _sample_trajectory,
)
from colav_simulator.core.colav.custom_mpc_adapter import _wrap_angle as adapter_wrap
from colav_simulator.core.colav.kuwata_vo_alg.kuwata_vo import (
    VO,
    OwnshipEnvelope,
    VOParams,
    _wrap_angle_array,
)
from colav_simulator.integrations.potocnik_colreg_mpc import (
    PotocnikColregFanMPC,
    PotocnikColregParams,
    _route_contract_wrap,
)

ORIGINAL = {
    "os_course_time_constant_s": 86.7839162612874,
    "os_speed_time_constant_s": 24.07,
    "os_max_turn_rate_radps": np.deg2rad(1.2),
    "os_avoidance_speed_cap_mps": 3.2,
    "os_min_steerage_speed_mps": 3.0,
}


def original_envelope() -> OwnshipEnvelope:
    return OwnshipEnvelope(
        course_time_constant_s=ORIGINAL["os_course_time_constant_s"],
        speed_time_constant_s=ORIGINAL["os_speed_time_constant_s"],
        max_turn_rate_radps=ORIGINAL["os_max_turn_rate_radps"],
        avoidance_speed_cap_mps=ORIGINAL["os_avoidance_speed_cap_mps"],
        min_steerage_speed_mps=ORIGINAL["os_min_steerage_speed_mps"],
    )


def head_on_target(range_m: float, *, target_id: int = 1) -> tuple:
    return (target_id, np.array([range_m, 0.0, -7.0, 0.0]), np.zeros((4, 4)), 45.0, 8.0)


def tracked_target(x: float, y: float, vx: float, vy: float, *, target_id: int = 1) -> tuple:
    return (target_id, np.array([x, y, vx, vy]), np.zeros((4, 4)), 45.0, 8.0)


def cleared_target(*, target_id: int = 1) -> tuple:
    """Abaft, diverging geometry: no COLREG geometry matches, CPA is in the past."""
    return tracked_target(-600.0, -800.0, 2.0, -4.0, target_id=target_id)


# --- VO envelope math -----------------------------------------------------------------


def test_speed_window_keeps_only_executable_avoidance_speeds_on_default_grid() -> None:
    speed_set = np.linspace(0.0, 10.0, 32)
    excluded = original_envelope().speed_exclusion_mask(speed_set)

    kept = speed_set[~excluded]
    assert kept.tolist() == pytest.approx([10.0 * 9 / 31])  # 2.903 m/s: nearest sample inside [steerage, cap]
    assert excluded[0], "zero speed reads as maximum command speed at the frozen route manager"
    step = 10.0 / 31
    outside = speed_set[excluded & (speed_set > 0.0)]
    assert np.all((outside > 3.2) | (outside < 3.0 - 0.5 * step))


def test_speed_window_never_empties_the_grid() -> None:
    envelope = OwnshipEnvelope(86.78, 24.07, np.deg2rad(1.2), avoidance_speed_cap_mps=0.1, min_steerage_speed_mps=0.05)
    excluded = envelope.speed_exclusion_mask(np.linspace(0.0, 10.0, 32))

    assert np.count_nonzero(~excluded) == 1
    assert np.flatnonzero(~excluded).tolist() == [0]


def test_reachable_course_arc_is_rate_and_horizon_limited() -> None:
    heading_set = np.linspace(-np.pi, np.pi, 128, endpoint=False)
    envelope = original_envelope()

    assert not envelope.course_exclusion_mask(heading_set, 0.3, envelope.horizon_s(120.0)).any()
    slow = OwnshipEnvelope(86.78, 24.07, np.deg2rad(0.1), 3.2, 3.0)
    excluded = slow.course_exclusion_mask(heading_set, 0.0, 100.0)
    assert np.all(np.abs(heading_set[~excluded]) <= np.deg2rad(10.0) + 1e-12)
    assert np.all(np.abs(heading_set[excluded]) > np.deg2rad(10.0))


def test_horizon_extends_by_the_course_time_constant() -> None:
    assert original_envelope().horizon_s(120.0) == pytest.approx(120.0 + 86.7839162612874)


def test_envelope_rejects_incomplete_or_non_positive_values() -> None:
    with pytest.raises(ValueError):
        OwnshipEnvelope(86.78, 24.07, np.deg2rad(1.2), 0.0, 3.0)
    with pytest.raises(ValueError, match="both the avoidance cap"):
        VO(VOParams()).plan(0.0, np.array([7.0, 0.0]), np.zeros(6), [], os_avoidance_speed_cap_mps=3.2)
    with pytest.raises(ValueError, match="full response model"):
        VO(VOParams()).plan(
            0.0, np.array([7.0, 0.0]), np.zeros(6), [], os_avoidance_speed_cap_mps=3.2, os_min_steerage_speed_mps=3.0
        )


# --- VO planner integration ----------------------------------------------------------


def test_envelope_bounds_selection_without_touching_hard_constraint_evidence() -> None:
    """Without an active encounter the nominal transit band stays executable."""
    vo = VO(VOParams())
    state = np.array([0.0, 0.0, 0.0, 7.0, 0.0, 0.0])

    vo.plan(0.0, np.array([7.0, 0.0]), state, [], **ORIGINAL)
    debug = vo.get_debug_data()

    assert vo.feasible
    assert debug["selected_speed_mps"] == pytest.approx(7.0)  # anchored exact mission-speed row
    assert debug["hard_constraint_count"] == 0, "envelope exclusions must not read as avoidance constraints"
    assert debug["avoidance_speed_window_active"] is False
    assert debug["envelope_excluded_count"] == 10 * 128, (
        "zero-speed sentinel plus the 9 transit rows above the mission speed"
    )
    assert debug["reachable_candidate_count"] == (vo._speed_set.size - 10) * 128
    assert debug["planning_horizon_s"] == pytest.approx(120.0 + ORIGINAL["os_course_time_constant_s"])
    assert debug["ownship_envelope"]["avoidance_speed_cap_mps"] == 3.2


def test_avoidance_window_grid_gains_anchored_executable_rows() -> None:
    """The [steerage, cap] window must carry anchored rows, not one coarse sample."""
    vo = VO(VOParams())
    state = np.array([0.0, 0.0, 0.0, 7.0, 0.0, 0.0])

    vo.plan(0.0, np.array([7.0, 0.0]), state, [], **ORIGINAL)
    debug = vo.get_debug_data()

    assert debug["avoidance_speed_window_rows"] >= 5
    window_rows = vo._speed_set[(vo._speed_set >= 3.0 - 1e-9) & (vo._speed_set <= 3.2 + 1e-9)]
    assert window_rows.size >= 5
    assert window_rows.min() == pytest.approx(3.0)
    assert window_rows.max() == pytest.approx(3.2)


def test_active_encounter_selects_inside_the_capped_avoidance_window() -> None:
    vo = VO(VOParams())
    state = np.array([0.0, 0.0, 0.0, 7.0, 0.0, 0.0])
    target = head_on_target(14.0 * 160.0)

    vo.plan(0.0, np.array([7.0, 0.0]), state, [target], **ORIGINAL)
    debug = vo.get_debug_data()

    assert debug["avoidance_speed_window_active"] is True
    assert 3.0 - 1e-9 <= debug["selected_speed_mps"] <= 3.2 + 1e-9


def test_window_releases_and_transit_speed_restores_when_encounter_clears() -> None:
    vo = VO(VOParams())
    state = np.array([0.0, 0.0, 0.0, 7.0, 0.0, 0.0])
    target = head_on_target(14.0 * 160.0)

    vo.plan(0.0, np.array([7.0, 0.0]), state, [target], **ORIGINAL)
    assert vo.get_debug_data()["avoidance_speed_window_active"] is True

    vo.plan(1.0, np.array([7.0, 0.0]), state, [], **ORIGINAL)
    debug = vo.get_debug_data()
    assert debug["avoidance_speed_window_active"] is False
    assert debug["selected_speed_mps"] == pytest.approx(7.0)


def test_window_releases_while_a_cleared_target_stays_tracked() -> None:
    """P5 campaign regression: an empty per-target rule set must not gate the window.

    After 2862e6ff the gate read dict truthiness, and _update_colregs_rules keeps
    the target key with an EMPTY set once its rules hysteresis-clear, so the
    [steerage, cap] window stayed active for the whole episode (vo-CS cells
    crawled at the 3.2 m/s cap long after CPA and missed the goal radius).
    """
    vo = VO(VOParams())
    state = np.array([0.0, 0.0, 0.0, 7.0, 0.0, 0.0])

    vo.plan(0.0, np.array([7.0, 0.0]), state, [head_on_target(14.0 * 160.0)], **ORIGINAL)
    assert vo.get_debug_data()["avoidance_speed_window_active"] is True

    for step in range(1, 6):
        vo.plan(float(step), np.array([7.0, 0.0]), state, [cleared_target()], **ORIGINAL)
    debug = vo.get_debug_data()

    assert vo._active_rules.keys() == {1}, "target must stay tracked with its rules cleared"
    assert not any(vo._active_rules.values())
    assert debug["avoidance_speed_window_active"] is False, (
        "cleared rule evidence must reopen the nominal transit band"
    )
    assert debug["selected_speed_mps"] > 5.0, "transit speed must restore past the avoidance cap"


def test_transit_band_never_exceeds_the_mission_speed() -> None:
    """Reopened transit candidates stop at the reference speed, not at the grid top."""
    vo = VO(VOParams())
    state = np.array([0.0, 0.0, 0.0, 7.0, 0.0, 0.0])

    vo.plan(0.0, np.array([5.0, 0.0]), state, [], **ORIGINAL)
    assert vo.get_debug_data()["selected_speed_mps"] <= 5.0 + 0.5 * (10.0 / 31) + 1e-9


def test_cruise_rows_are_anchored_denser_near_the_mission_speed() -> None:
    """F5a: the transit band must resolve the mission speed, not a 0.32 m/s lattice.

    The coarse 32-sample grid forced post-encounter transit onto 7.097 m/s for a
    7.0 m/s mission reference (or 2.903 m/s commands that guidance executes at
    steerage). Anchored cruise rows give the selection an exact mission-speed row
    and a band that tightens toward cruise.
    """
    vo = VO(VOParams())
    state = np.array([0.0, 0.0, 0.0, 7.0, 0.0, 0.0])

    vo.plan(0.0, np.array([7.0, 0.0]), state, [], **ORIGINAL)

    band = vo._speed_set[(vo._speed_set > ORIGINAL["os_avoidance_speed_cap_mps"] + 1e-9)]
    base_step = 10.0 / 31
    anchored = band[(band > 3.2 + 0.5 * base_step - 1e-9) & (band < 7.0 - 1e-9)]
    assert anchored.size >= 3, "cruise band must carry anchored rows, not base-grid samples only"
    assert vo._speed_set.max() >= 7.0
    assert np.any(np.isclose(vo._speed_set, 7.0, atol=1e-9)), "exact mission-speed row must exist"
    rows = np.sort(band[band <= 7.0 + 1e-9])
    assert rows[-1] == pytest.approx(7.0)
    assert np.min(np.diff(rows)) < 0.5 * base_step, "rows must tighten toward cruise"


def test_transit_selection_lands_on_the_exact_mission_speed_row() -> None:
    vo = VO(VOParams())
    state = np.array([0.0, 0.0, 0.0, 7.0, 0.0, 0.0])

    vo.plan(0.0, np.array([7.0, 0.0]), state, [], **ORIGINAL)

    assert vo.get_debug_data()["selected_speed_mps"] == pytest.approx(7.0)


def test_give_way_prefers_the_course_alteration_family() -> None:
    """F6b policy: an active give-way must resolve to the course-alteration family.

    Crossing episodes flipped between "big speed reduction, near-nominal course"
    and "starboard turn" across seed variants because near-equal candidate costs
    fell to environment noise. Standard give-way practice is to alter course to
    starboard while keeping way, so the selection must express that preference
    deterministically whenever an admissible course-alteration candidate sits
    within the family preference margin of the cost optimum.
    """
    vo = VO(VOParams())
    state = np.array([0.0, 0.0, 0.0, 7.0, 0.0, 0.0])

    vo.plan(0.0, np.array([7.0, 0.0]), state, [head_on_target(14.0 * 160.0)], **ORIGINAL)
    debug = vo.get_debug_data()

    assert debug["avoidance_speed_window_active"] is True
    assert debug["give_way_family_selected"] == "course"
    heading_delta = abs(adapter_wrap(debug["selected_heading_rad"] - 0.0))
    assert heading_delta >= vo._params.give_way_course_family_min_rad


def test_give_way_keeps_speed_reduction_when_course_family_infeasible() -> None:
    """F6b policy fallback: no admissible course alteration means keep-way slowdown."""
    vo = VO(VOParams())
    state = np.array([0.0, 0.0, 0.0, 7.0, 0.0, 0.0])

    vo.plan(0.0, np.array([7.0, 0.0]), state, [head_on_target(14.0 * 160.0)], **ORIGINAL)
    vo._total_costs[
        :, np.abs(_wrap_angle_array(vo._heading_set)) >= vo._params.give_way_course_family_min_rad
    ] = np.inf

    minimum = float(np.min(vo._total_costs))
    assert vo._give_way_family_selection(minimum, np.array([7.0, 0.0])) is None
    i_speed, _i_heading = np.unravel_index(int(np.argmin(vo._total_costs)), vo._total_costs.shape)

    assert vo._speed_set[i_speed] <= 3.2 + 1e-9, "fallback must be a speed reduction below cruise"


def test_planner_input_carries_backend_speed_envelope() -> None:
    """PlannerInput must be able to carry the backend avoidance cap and steerage floor."""
    enriched = fan_input(
        ownship_avoidance_speed_cap_mps=3.2,
        ownship_min_steerage_speed_mps=3.0,
    )
    assert enriched.ownship_avoidance_speed_cap_mps == 3.2
    assert enriched.ownship_min_steerage_speed_mps == 3.0
    assert fan_input().ownship_avoidance_speed_cap_mps is None

    with pytest.raises(ValueError, match="speed envelope"):
        PlannerInput(
            sim_time_s=0.0,
            dt_sim_s=0.5,
            waypoints_enu_m=np.array([[0.0, 10000.0], [0.0, 0.0]]),
            speed_plan_mps=np.array([7.0, 7.0]),
            ownship_state=np.array([0.0, 0.0, 0.0, 7.0, 0.0, 0.0]),
            tracks=(),
            enc=None,
            goal_state=None,
            disturbance=None,
            algorithm_seed=0,
            ownship_avoidance_speed_cap_mps=0.0,
        )


def test_envelope_horizon_activates_head_on_avoidance_earlier() -> None:
    state = np.array([0.0, 0.0, 0.0, 7.0, 0.0, 0.0])
    # 14 m/s closing: inside the extended horizon (~207 s) but outside the paper horizon (120 s).
    target = head_on_target(14.0 * 160.0)

    paper = VO(VOParams())
    paper.plan(0.0, np.array([7.0, 0.0]), state, [target])
    enveloped = VO(VOParams())
    enveloped.plan(0.0, np.array([7.0, 0.0]), state, [target], **ORIGINAL)

    assert paper.get_debug_data()["hard_constraint_count"] == 0
    assert enveloped.get_debug_data()["hard_constraint_count"] > 0
    assert enveloped.feasible


def test_selection_hysteresis_holds_near_equal_cells_and_releases_large_changes() -> None:
    vo = VO(VOParams())
    state = np.array([0.0, 0.0, 0.0, 7.0, 0.0, 0.0])

    vo.plan(0.0, np.array([7.0, 0.0]), state, [], **ORIGINAL)
    first = vo.get_debug_data()["selected_heading_rad"]
    assert vo.get_debug_data()["selection_held"] is False

    nudged = 7.0 * np.array([np.cos(np.deg2rad(0.5)), np.sin(np.deg2rad(0.5))])  # under half a heading cell
    vo.plan(1.0, nudged, state, [], **ORIGINAL)
    assert vo.get_debug_data()["selection_held"] is True
    assert vo.get_debug_data()["selected_heading_rad"] == first

    vo.plan(2.0, np.array([0.0, 7.0]), state, [], **ORIGINAL)
    assert vo.get_debug_data()["selection_held"] is False
    assert vo.get_debug_data()["selected_heading_rad"] == pytest.approx(np.pi / 2.0, abs=np.pi / 128)


def test_hysteresis_is_inactive_without_an_envelope() -> None:
    vo = VO(VOParams())
    state = np.array([0.0, 0.0, 0.0, 7.0, 0.0, 0.0])
    vo.plan(0.0, np.array([7.0, 0.0]), state, [])
    vo.plan(1.0, 7.0 * np.array([np.cos(np.deg2rad(2.0)), np.sin(np.deg2rad(2.0))]), state, [])

    assert vo.get_debug_data()["selection_held"] is False
    assert vo.get_debug_data()["planning_horizon_s"] == 120.0
    assert vo.get_debug_data()["envelope_excluded_count"] == 0


# --- Fan MPC ownship response --------------------------------------------------------


def fan_input(**dynamics) -> PlannerInput:
    return PlannerInput(
        sim_time_s=0.0,
        dt_sim_s=0.5,
        waypoints_enu_m=np.array([[0.0, 10000.0], [0.0, 0.0]]),
        speed_plan_mps=np.array([7.0, 7.0]),
        ownship_state=np.array([0.0, 0.0, np.deg2rad(50.0), 7.0, 0.0, 0.0]),
        tracks=(
            TrackedObstacle(
                target_id=1,
                state_enu=np.array([2000.0, 2000.0, -5.0, -5.0]),
                covariance=np.zeros((4, 4)),
                length_m=45.0,
                width_m=8.0,
                observed_at_s=0.0,
                age_s=0.0,
            ),
        ),
        enc=None,
        goal_state=None,
        disturbance=None,
        algorithm_seed=0,
        ownship_length_m=45.0,
        ownship_width_m=8.0,
        ownship_draft_m=2.0,
        **dynamics,
    )


def test_fan_response_is_never_nimbler_than_the_reported_backend() -> None:
    fan = PotocnikColregFanMPC(PotocnikColregParams())

    slow = fan._ownship_response(
        fan_input(
            ownship_course_time_constant_s=86.78,
            ownship_speed_time_constant_s=24.07,
            ownship_max_turn_rate_rad_s=np.deg2rad(1.2),
        )
    )
    assert (slow.course_time_constant_s, slow.speed_time_constant_s) == (86.78, 24.07)
    assert slow.max_yaw_rate_deg_s == pytest.approx(1.2)
    assert slow.source == "planner_input"

    nimble = fan._ownship_response(
        fan_input(
            ownship_course_time_constant_s=2.0,
            ownship_speed_time_constant_s=2.0,
            ownship_max_turn_rate_rad_s=np.deg2rad(10.0),
        )
    )
    assert (nimble.course_time_constant_s, nimble.speed_time_constant_s, nimble.max_yaw_rate_deg_s) == (8.0, 10.0, 3.0)
    assert nimble.source == "profile"

    assert fan._ownship_response(fan_input()).source == "profile"


def test_fan_solution_reports_the_response_model_and_slows_rollouts() -> None:
    params = PotocnikColregParams()
    fan = PotocnikColregFanMPC(params)
    slow_input = fan_input(
        ownship_course_time_constant_s=86.78,
        ownship_speed_time_constant_s=24.07,
        ownship_max_turn_rate_rad_s=np.deg2rad(1.2),
    )
    solution = PotocnikColregFanMPC(params).solve(slow_input)
    assert solution.algorithm_details["ownship_response_model"]["course_time_constant_s"] == 86.78
    assert solution.algorithm_details["ownship_response_model"]["source"] == "planner_input"

    ownship = slow_input.ownship_state
    nimble, _ = fan._generate_candidate_bundle(ownship, 7.0, 0.5, response=fan._ownship_response(fan_input()))
    slow, _ = fan._generate_candidate_bundle(ownship, 7.0, 0.5, response=fan._ownship_response(slow_input))
    # The same extreme command ramp turns the sluggish hull far less over the horizon.
    nimble_turn = abs(adapter_wrap(float(nimble[0, 2, -1] - nimble[0, 2, 0])))
    slow_turn = abs(adapter_wrap(float(slow[0, 2, -1] - slow[0, 2, 0])))
    assert 0.0 < slow_turn < 0.5 * nimble_turn
    assert slow_turn <= np.deg2rad(1.2) * params.prediction_steps * params.horizon_dt_s + 1e-9


def test_held_course_samples_are_bit_identical_to_the_solve_command() -> None:
    """Regression: a 1-ULP held/solve mismatch re-spliced the original route every tick."""
    params = PotocnikColregParams()
    fan = PotocnikColregFanMPC(params)
    solution = fan.solve(fan_input())
    controls = solution.control_trajectory
    assert controls is not None
    command = float(solution.control_reference[2, 0])
    assert command == float(controls[2, 0])
    assert command == _route_contract_wrap(command) == adapter_wrap(command)
    assert np.array_equal(_route_contract_wrap(controls[2]), controls[2])

    # The nominal (zero-increment) candidate holds one course for the whole horizon:
    # every held sample the adapter publishes must equal the solve-tick value.
    ownship = np.array([0.0, 0.0, np.deg2rad(45.0), 7.0, 0.0, 0.0])
    _, bundle = fan._generate_candidate_bundle(ownship, 7.0, 0.5, command_course_center=np.deg2rad(50.0))
    nominal = bundle[params.candidate_count // 2]
    assert np.all(nominal[2] == nominal[2, 0])
    for elapsed_s in (0.5, 1.0, 2.5, 4.5, 7.5):
        assert float(_sample_trajectory(nominal, params.horizon_dt_s, elapsed_s)[2, 0]) == float(nominal[2, 0])
