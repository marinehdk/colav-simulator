from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from colav_simulator.core.colav.diagnostics import ColavExecutionError, PlannerTrace, PlanStatus
from colav_simulator.experiment.contracts import InternalExecutionPurpose, RunSpec
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


def test_evaluator_baseline_rejects_unregistered_scenario_with_typed_error(tmp_path: Path) -> None:
    runner = ExperimentRunner(Path.cwd())
    with pytest.raises(ColavExecutionError, match="No internal capability tuple") as raised:
        runner.prepare_internal(
            RunSpec(
                scenario_id="head_on_sbmpc",
                validation_rule_id="rule14",
                algorithm_id="nominal",
                tracker_id="god",
                output_root=str(tmp_path),
            ),
            purpose=InternalExecutionPurpose.EVALUATOR_BASELINE,
        )
    assert raised.value.status is PlanStatus.INVALID_INPUT
