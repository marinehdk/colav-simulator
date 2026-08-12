from __future__ import annotations

import json
import math
from typing import TYPE_CHECKING

import numpy as np
from conftest import PROJECT_ROOT, P1RunHarness

from colav_simulator.cli import _load_algorithm_config

if TYPE_CHECKING:
    from colav_simulator.experiment.runner import RunResult

ALGORITHM_ID = "mid_mpc_ipopt"
ALGORITHM_CONFIG = _load_algorithm_config(PROJECT_ROOT / "config/mid_mpc_ipopt.yaml")


def _run_and_assert_common(p1_run_harness: P1RunHarness, scenario_id: str) -> RunResult:
    result = p1_run_harness.compare(
        scenario_id,
        ALGORITHM_ID,
        algorithm_config=ALGORITHM_CONFIG,
        solve_period_s=5.0,
    )
    run = p1_run_harness.run(
        scenario_id,
        ALGORITHM_ID,
        algorithm_config=ALGORITHM_CONFIG,
        solve_period_s=5.0,
    )
    evaluation = run.evaluation.to_dict()
    manifest = run.manifest.to_dict()
    solve_rows = _solve_rows(run)

    assert result.passed, json.dumps(result.to_dict(), indent=2, sort_keys=True)
    assert evaluation["hard_gate"]["outcome"] == "PASS", json.dumps(evaluation, indent=2, sort_keys=True)
    clearance = next(check for check in evaluation["hard_gate"]["checks"] if check["check_id"] == "minimum_hull_clearance")[
        "evidence"
    ]
    assert clearance["minimum_hull_clearance_m"] >= clearance["required_clearance_m"]
    assert evaluation["aggregate"]["ownship_collision_count"] == 0
    assert evaluation["aggregate"]["global_collision_count"] == 0
    assert evaluation["aggregate"]["ownship_grounding_count"] == 0
    assert evaluation["aggregate"]["global_grounding_not_evaluated_count"] == 0
    assert not {"collision", "grounding"} & {event["type"] for event in run.session.events}

    assert manifest["requested_algorithm"] == ALGORITHM_ID
    assert manifest["executed_algorithm"] == ALGORITHM_ID
    assert manifest["requested_tracker"] == "god"
    assert manifest["executed_tracker"] == "god"
    assert manifest["fallback_used"] is False
    assert manifest["state"] == "FINISHED"
    assert manifest["execution_outcome"] == "COMPLETED"
    assert manifest["spec"]["seed"] == 0
    assert manifest["spec"]["deadline_mode"] == "ENFORCE"
    assert manifest["spec"]["strict_no_fallback"] is True

    assert solve_rows
    for row in solve_rows:
        details = row["algorithm_details"]
        constraints = row["constraints"]
        assert row["algorithm_id"] == ALGORITHM_ID
        assert row["solver_executed"] is True
        assert row["status"] == "SUCCESS"
        assert row["feasible"] is True
        assert row["iterations"] > 0
        assert math.isfinite(row["objective"])
        assert details["deadline_mode"] == "ENFORCE"
        assert details["solver_backend"] == "ipopt"
        assert details["ipopt_return_status"] == "Solve_Succeeded"
        assert details["normalized_solver_status"] == "Converged"
        assert 0.0 < details["solver_elapsed_ms"] < 20_000.0
        assert constraints["max_constraint_violation"] <= 1.0e-3
        assert math.isfinite(constraints["cpa_slack"])
        assert constraints["cpa_slack"] >= 0.0
        assert math.isfinite(constraints["direction_slack"])
        assert constraints["direction_slack"] >= 0.0
    json.dumps(run.session.events, allow_nan=False)

    initial = np.asarray(run.session.frames[0]["Ship0"]["state"], dtype=float)
    final = np.asarray(run.session.frames[-1]["Ship0"]["state"], dtype=float)
    assert abs(_angle_delta(_course(final), _course(initial))) < math.radians(5.0)
    assert abs(float(np.hypot(final[3], final[4]) - np.hypot(initial[3], initial[4]))) < 0.1
    return run


def _solve_rows(run: RunResult) -> list[dict]:
    return [event["details"]["planner"] for event in run.session.events if event["type"] == "planner_solved"]


def _course(state: np.ndarray) -> float:
    return float(state[2] + math.atan2(state[4], state[3]))


def _angle_delta(angle: float, reference: float) -> float:
    return math.atan2(math.sin(angle - reference), math.cos(angle - reference))


def _first_command_delta(run: RunResult) -> float:
    initial_course = _course(np.asarray(run.session.frames[0]["Ship0"]["state"], dtype=float))
    selected_course = float(_solve_rows(run)[0]["selected_command"]["course_rad"])
    return _angle_delta(selected_course, initial_course)


def _actual_cpa_relative_ne(run: RunResult) -> np.ndarray:
    return np.asarray(run.evaluation.to_dict()["pair_results"][0]["actual_cpa"]["relative_position_at_cpa_ne_m"])


def _initial_target_velocity_ne(run: RunResult) -> np.ndarray:
    first = np.asarray(run.session.frames[0]["Ship1"]["state"][:2], dtype=float)
    second = np.asarray(run.session.frames[1]["Ship1"]["state"][:2], dtype=float)
    return (second - first) / run.session.config.dt_sim


def _assert_delayed_hold_then_selection(run: RunResult, expected_encounter: str) -> None:
    rows = _solve_rows(run)
    first = rows[0]
    assert first["algorithm_details"]["decision_intent"] == "HOLD"
    assert first["algorithm_details"]["preferred_side"] == "none"
    assert first["target_predictions"][0]["encounter"] == expected_encounter
    assert first["algorithm_details"]["selected_target_ids"] == []
    assert abs(_first_command_delta(run)) < math.radians(1.0)
    assert all(row["algorithm_details"]["decision_intent"] == "HOLD" for row in rows)
    first_selected = next(row for row in rows if row["algorithm_details"]["selected_target_ids"])
    assert first_selected["sim_time"] > 0.0
    assert 0.0 < first_selected["target_predictions"][0]["signed_tcpa_s"] <= 90.0


def test_mid_mpc_head_on_closed_loop_turns_starboard_passes_port_and_recovers(
    p1_run_harness: P1RunHarness,
) -> None:
    run = _run_and_assert_common(p1_run_harness, "head_on")
    first = _solve_rows(run)[0]
    initial_course = _course(np.asarray(run.session.frames[0]["Ship0"]["state"], dtype=float))
    starboard_normal = np.array([-math.sin(initial_course), math.cos(initial_course)])

    assert first["sim_time"] == 0.0
    assert first["algorithm_details"]["decision_intent"] == "GIVE_WAY"
    assert first["algorithm_details"]["preferred_side"] == "starboard"
    assert _first_command_delta(run) >= math.radians(5.0)
    assert float(_actual_cpa_relative_ne(run) @ starboard_normal) < 0.0
    assert _solve_rows(run)[-1]["algorithm_details"]["decision_intent"] == "HOLD"


def test_mid_mpc_crossing_give_way_turns_starboard_passes_astern_and_recovers(
    p1_run_harness: P1RunHarness,
) -> None:
    run = _run_and_assert_common(p1_run_harness, "crossing_give_way")
    first = _solve_rows(run)[0]

    assert first["sim_time"] == 0.0
    assert first["algorithm_details"]["decision_intent"] == "GIVE_WAY"
    assert first["algorithm_details"]["preferred_side"] == "starboard"
    assert _first_command_delta(run) >= math.radians(5.0)
    assert float(_actual_cpa_relative_ne(run) @ _initial_target_velocity_ne(run)) > 0.0
    assert _solve_rows(run)[-1]["algorithm_details"]["decision_intent"] == "HOLD"


def test_mid_mpc_crossing_stand_on_holds_then_acts_inside_horizon_and_recovers(
    p1_run_harness: P1RunHarness,
) -> None:
    run = _run_and_assert_common(p1_run_harness, "crossing_stand_on")

    _assert_delayed_hold_then_selection(run, "crossing_stand_on")
    assert float(_actual_cpa_relative_ne(run) @ _initial_target_velocity_ne(run)) < 0.0


def test_mid_mpc_overtaking_commits_starboard_passes_target_and_recovers(
    p1_run_harness: P1RunHarness,
) -> None:
    run = _run_and_assert_common(p1_run_harness, "overtaking")
    first = _solve_rows(run)[0]
    initial_course = _course(np.asarray(run.session.frames[0]["Ship0"]["state"], dtype=float))
    along_route = np.array([math.cos(initial_course), math.sin(initial_course)])
    starboard_normal = np.array([-math.sin(initial_course), math.cos(initial_course)])
    relative_at_cpa = _actual_cpa_relative_ne(run)
    final_own = np.asarray(run.session.frames[-1]["Ship0"]["state"][:2], dtype=float)
    final_target = np.asarray(run.session.frames[-1]["Ship1"]["state"][:2], dtype=float)

    assert first["sim_time"] == 0.0
    assert first["algorithm_details"]["decision_intent"] == "GIVE_WAY"
    assert first["algorithm_details"]["preferred_side"] == "starboard"
    assert first["algorithm_details"]["route_reference_mode"] == "give_way_commitment"
    assert _first_command_delta(run) >= math.radians(4.0)
    assert float(relative_at_cpa @ starboard_normal) < 0.0
    assert float((final_own - final_target) @ along_route) >= 190.0
    assert _solve_rows(run)[-1]["algorithm_details"]["decision_intent"] == "HOLD"


def test_mid_mpc_overtaken_holds_then_acts_inside_horizon_and_recovers(
    p1_run_harness: P1RunHarness,
) -> None:
    run = _run_and_assert_common(p1_run_harness, "overtaken")

    _assert_delayed_hold_then_selection(run, "overtaken")
