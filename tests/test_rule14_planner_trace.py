from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from colav_simulator.core.colav.diagnostics import ColavExecutionError, PlannerTrace
from colav_simulator.experiment.contracts import RunSpec, SessionState
from colav_simulator.experiment.runner import ExperimentRunner


def test_planner_trace_requires_finite_9xn() -> None:
    trace = PlannerTrace(
        algorithm_id="test",
        solve_id=1,
        sim_time=0.0,
        solver_executed=True,
        predicted_trajectory=np.zeros((9, 3)),
    )
    assert np.asarray(trace.to_dict()["predicted_trajectory"]).shape == (9, 3)

    with pytest.raises(ColavExecutionError, match="shape"):
        PlannerTrace(
            algorithm_id="test",
            solve_id=1,
            sim_time=0.0,
            solver_executed=True,
            predicted_trajectory=np.zeros((8, 3)),
        ).to_dict()

    invalid = np.zeros((9, 3))
    invalid[0, 0] = np.nan
    with pytest.raises(ColavExecutionError, match="non-finite"):
        PlannerTrace(
            algorithm_id="test",
            solve_id=1,
            sim_time=0.0,
            solver_executed=True,
            predicted_trajectory=invalid,
        ).to_dict()


def test_nominal_rejects_scenario_embedded_colav(tmp_path: Path) -> None:
    runner = ExperimentRunner(Path.cwd())
    with pytest.raises(ColavExecutionError, match="embeds an onboard COLAV"):
        runner.prepare(
            RunSpec(
                scenario_id="head_on_sbmpc",
                algorithm_id="nominal",
                tracker_id="god",
                output_root=str(tmp_path),
            )
        )


def test_sbmpc_real_solve_and_hold_last_evidence(tmp_path: Path) -> None:
    runner = ExperimentRunner(Path.cwd())
    prepared = runner.prepare(
        RunSpec(
            scenario_id="head_on",
            validation_rule_id="rule14",
            algorithm_id="sbmpc",
            tracker_id="god",
            seed=0,
            t_end=6.0,
            terminate_on_collision_or_grounding=False,
            output_root=str(tmp_path),
        )
    )

    traces = []
    while prepared.session.state not in {SessionState.FINISHED, SessionState.FAILED}:
        snapshot = prepared.session.step_once()
        traces.append(snapshot.payload["Ship0"]["colav"]["planner"])

    solved = [trace for trace in traces if trace["solver_executed"]]
    assert len(solved) == 1
    assert solved[0]["solve_id"] == 1
    prediction = np.asarray(solved[0]["predicted_trajectory"])
    assert prediction.shape == (9, 60)
    assert np.allclose(prediction[2, 1:], solved[0]["selected_command"]["course_rad"])
    assert np.allclose(prediction[3, 1:], solved[0]["selected_command"]["speed_mps"])
    assert solved[0]["algorithm_details"]["candidate_costs"]
    assert traces[-1]["solver_executed"] is False
    assert traces[-1]["solve_id"] == solved[0]["solve_id"]

    result = runner.finalize(prepared)
    assert result.manifest.requested_algorithm == result.manifest.executed_algorithm == "sbmpc"
    assert result.manifest.requested_tracker == result.manifest.executed_tracker == "god"
    assert result.manifest.fallback_used is False
    assert result.manifest.capability_profile_id == "rule14:head_on:sbmpc:god"

    events = [json.loads(line) for line in (result.run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    planner_events = [event for event in events if event["type"] == "planner_solved"]
    assert len(planner_events) == 1
    assert planner_events[0]["sim_time"] == solved[0]["sim_time"]
    assert np.asarray(planner_events[0]["details"]["planner"]["predicted_trajectory"]).shape == (9, 60)

    script = """
import json
import pandas as pd
import sys

trajectory = pd.read_parquet(sys.argv[1])
ownship = trajectory[trajectory["ship_id"] == 0]
print(json.dumps({
    "max_solve_id": int(ownship["planner_solve_id"].max()),
    "solve_count": int(ownship["planner_solver_executed"].sum()),
    "last_colav": json.loads(ownship.iloc[-1]["colav_json"]),
}))
"""
    completed = subprocess.run(
        [sys.executable, "-c", script, str(result.run_dir / "trajectory.parquet")],
        check=True,
        capture_output=True,
        text=True,
    )
    trajectory_summary = json.loads(completed.stdout)
    assert trajectory_summary["max_solve_id"] == 1
    assert trajectory_summary["solve_count"] == 1
    assert "predicted_trajectory" not in trajectory_summary["last_colav"]["planner"]
