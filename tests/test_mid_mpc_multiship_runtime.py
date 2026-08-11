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
SCENARIO_ID = "paper_ccta2023_multiship"
ALGORITHM_CONFIG = _load_algorithm_config(PROJECT_ROOT / "config/mid_mpc_ipopt.yaml")


def _course(state: np.ndarray) -> float:
    return float(state[2] + math.atan2(state[4], state[3]))


def _angle_delta(angle: float, reference: float) -> float:
    return math.atan2(math.sin(angle - reference), math.cos(angle - reference))


def _solve_rows(run: RunResult) -> list[dict]:
    return [event["details"]["planner"] for event in run.session.events if event["type"] == "planner_solved"]


def test_mid_mpc_multiship_closed_loop_is_safe_observable_and_recovers(  # noqa: PLR0915
    p1_run_harness: P1RunHarness,
) -> None:
    display = p1_run_harness.compare(
        SCENARIO_ID,
        ALGORITHM_ID,
        algorithm_config=ALGORITHM_CONFIG,
        solve_period_s=5.0,
    )
    run = p1_run_harness.run(
        SCENARIO_ID,
        ALGORITHM_ID,
        algorithm_config=ALGORITHM_CONFIG,
        solve_period_s=5.0,
    )
    evaluation = run.evaluation.to_dict()
    manifest = run.manifest.to_dict()
    solve_rows = _solve_rows(run)

    assert display.passed, json.dumps(display.to_dict(), indent=2, sort_keys=True)
    assert evaluation["hard_gate"]["outcome"] == "PASS", json.dumps(evaluation, indent=2, sort_keys=True)
    ownship_pairs = {
        f"Ship{pair['target_id'] if pair['ownship_id'] == 0 else pair['ownship_id']}": pair
        for pair in evaluation["pair_results"]
        if pair["ownship_id"] == 0 or pair["target_id"] == 0
    }
    assert set(ownship_pairs) == {"Ship1", "Ship2", "Ship3"}
    assert all(not pair["collision"] for pair in ownship_pairs.values())
    assert all(pair["minimum_hull_clearance_m"] >= 50.0 for pair in ownship_pairs.values()), ownship_pairs

    # Mid-MPC controls Ship0 only. Preserve global accounting for the three
    # target-target contacts instead of presenting the Ship0 hard gate as all-vessel safety.
    assert evaluation["aggregate"]["ownship_collision_count"] == 0
    assert evaluation["aggregate"]["global_collision_count"] == 3
    assert evaluation["aggregate"]["ownship_grounding_count"] == 0
    assert evaluation["aggregate"]["global_grounding_count"] == 0
    assert evaluation["aggregate"]["global_grounding_not_evaluated_count"] == 0

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

    assert len(solve_rows) == 100
    assert any(len(row["algorithm_details"]["selected_target_ids"]) >= 2 for row in solve_rows)
    assert {row["algorithm_details"]["decision_intent"] for row in solve_rows} == {"GIVE_WAY", "HOLD"}
    assert all(row["algorithm_id"] == ALGORITHM_ID for row in solve_rows)
    assert all(row["solver_executed"] is True for row in solve_rows)
    assert all(row["status"] == "SUCCESS" and row["feasible"] is True for row in solve_rows)
    assert all(row["iterations"] > 0 for row in solve_rows)
    assert all(math.isfinite(row["objective"]) for row in solve_rows)
    assert all(row["algorithm_details"]["solver_backend"] == "ipopt" for row in solve_rows)
    assert all(
        (
            row["algorithm_details"]["ipopt_return_status"],
            row["algorithm_details"]["normalized_solver_status"],
        )
        in {
            ("Solve_Succeeded", "Converged"),
            ("Solved_To_Acceptable_Level", "FeasibleNonOptimal"),
            ("User_Requested_Stop", "FeasibleNonOptimal"),
        }
        for row in solve_rows
    )
    assert all(0.0 < row["algorithm_details"]["solver_elapsed_ms"] < 20_000.0 for row in solve_rows)
    assert all(row["constraints"]["max_constraint_violation"] <= 1.0e-3 for row in solve_rows)
    assert all(row["constraints"]["cpa_slack"] >= 0.0 for row in solve_rows)
    assert all(row["constraints"]["direction_slack"] >= 0.0 for row in solve_rows)
    assert all(row["constraints"]["slack_bounds_mode"] == "fixed_zero" for row in solve_rows)
    assert all(row["constraints"]["slack_bounds"]["cpa"] == [0.0, 0.0] for row in solve_rows)
    assert all(row["constraints"]["slack_bounds"]["direction"] == [0.0, 0.0] for row in solve_rows)
    json.dumps(run.session.events, allow_nan=False)

    initial = np.asarray(run.session.frames[0]["Ship0"]["state"], dtype=float)
    courses = np.asarray(
        [_course(np.asarray(frame["Ship0"]["state"], dtype=float)) for frame in run.session.frames],
        dtype=float,
    )
    final = np.asarray(run.session.frames[-1]["Ship0"]["state"], dtype=float)
    assert np.max(np.abs(np.unwrap(courses) - courses[0])) >= math.radians(5.0)
    assert solve_rows[-1]["algorithm_details"]["decision_intent"] == "HOLD"
    assert abs(_angle_delta(_course(final), _course(initial))) < math.radians(5.0)
    assert abs(float(np.hypot(final[3], final[4]) - np.hypot(initial[3], initial[4]))) < 0.1
