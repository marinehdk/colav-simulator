from __future__ import annotations

import json

import pytest
from conftest import PROJECT_ROOT, P1RunHarness

from colav_simulator.cli import _load_algorithm_config

SCENARIOS = (
    "head_on",
    "overtaking",
    "overtaken",
    "crossing_give_way",
    "crossing_stand_on",
    "paper_ccta2023_multiship",
)
ALGORITHMS = ("vo", "sbmpc", "potocnik_simplified_mpc")
POTOCNIK_CONFIG = _load_algorithm_config(PROJECT_ROOT / "config/potocnik_simplified_mpc.yaml")


@pytest.mark.parametrize("scenario_id", SCENARIOS)
@pytest.mark.parametrize("algorithm_id", ALGORITHMS)
def test_phase3_matrix_produces_traceable_three_layer_evaluation(
    p1_run_harness: P1RunHarness,
    scenario_id: str,
    algorithm_id: str,
) -> None:
    result = p1_run_harness.run(
        scenario_id,
        algorithm_id,
        algorithm_config=POTOCNIK_CONFIG if algorithm_id == "potocnik_simplified_mpc" else None,
        solve_period_s=5.0 if algorithm_id == "potocnik_simplified_mpc" else None,
    )
    evaluation = result.evaluation
    assert result.manifest.requested_algorithm == result.manifest.executed_algorithm == algorithm_id
    assert result.manifest.fallback_used is False
    assert evaluation.evaluator_profile_id == "ccta_2023_demo-v1"
    assert evaluation.collision_oracle_id == "c2a-rect2d-v1"
    assert evaluation.evaluation_status == "COMPLETE"
    if algorithm_id == "potocnik_simplified_mpc" and scenario_id == "crossing_give_way":
        assert evaluation.hard_gate.outcome == "FAIL"
        assert evaluation.aggregate["ownship_grounding_count"] > 0
        return
    assert evaluation.hard_gate.outcome == "PASS", json.dumps(evaluation.to_dict(), indent=2, default=str)
    assert evaluation.pair_results
    for pair in evaluation.pair_results:
        if 0 in {pair.ownship_id, pair.target_id}:
            assert pair.collision is False
        assert pair.initial_cpa["method"] == "instantaneous_constant_velocity"
        assert pair.actual_cpa["method"] == "synchronized_trajectory"
        assert pair.metric_evidence["S_safety"]["formula_id"] == "oe2023-eq2"
        if pair.encounter != "clear":
            assert pair.fsm_transitions
