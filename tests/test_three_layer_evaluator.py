from __future__ import annotations

import numpy as np

from colav_simulator.common.vessel_data import VesselData
from colav_simulator.evaluation import Evaluator
from colav_simulator.evaluation.evaluator import VesselEvaluation, _aggregate, _hard_gate


def vessel(identifier: int, east: np.ndarray, north: np.ndarray, course: float) -> VesselData:
    return VesselData(
        id=identifier,
        mmsi=1000 + identifier,
        length=20.0,
        width=5.0,
        draft=2.0,
        xy=np.vstack((east, north)),
        sog=np.full(east.size, 5.0),
        cog=np.full(east.size, course),
        timestamps=np.arange(east.size, dtype=float),
        first_valid_idx=0,
        last_valid_idx=east.size - 1,
        travel_dist=float(np.hypot(east[-1] - east[0], north[-1] - north[0])),
    )


def test_hard_failure_cannot_be_offset_by_scores() -> None:
    own = vessel(0, np.zeros(3), np.array([0.0, 5.0, 10.0]), 0.0)
    target = vessel(1, np.zeros(3), np.array([10.0, 5.0, 0.0]), np.pi)
    result = Evaluator().evaluate(
        [own, target],
        execution_context={
            "requested_algorithm": "fixture",
            "executed_algorithm": "fixture",
            "fallback_used": False,
            "run_completed": True,
        },
    )
    assert result.hard_gate.outcome == "FAIL"
    assert result.aggregate["collision_count"] == 1
    assert result.pair_results[0].metrics["S_safety"] == 0.0
    assert result.scores["status"] == "COMPLETE"


def test_no_enc_is_soft_not_false_grounding_pass() -> None:
    own = vessel(0, np.zeros(2), np.array([0.0, 1.0]), 0.0)
    target = vessel(1, np.full(2, 100.0), np.array([0.0, 1.0]), 0.0)
    result = Evaluator().evaluate([own, target])
    grounding = next(check for check in result.hard_gate.checks if check.check_id == "physical_grounding")
    assert grounding.outcome == "NOT_EVALUATED"
    assert result.hard_gate.outcome == "SOFT"


def test_fallback_is_independent_hard_failure() -> None:
    own = vessel(0, np.zeros(2), np.array([0.0, 1.0]), 0.0)
    target = vessel(1, np.full(2, 100.0), np.array([0.0, 1.0]), 0.0)
    result = Evaluator().evaluate([own, target], execution_context={"fallback_used": True})
    fallback = next(check for check in result.hard_gate.checks if check.check_id == "fallback_used")
    assert fallback.outcome == "FAIL"
    assert result.hard_gate.outcome == "FAIL"


def test_historical_stateful_api_matches_direct_api(capsys: object) -> None:
    own = vessel(0, np.zeros(2), np.array([0.0, 1.0]), 0.0)
    target = vessel(1, np.full(2, 100.0), np.array([0.0, 1.0]), 0.0)
    evaluator = Evaluator()
    evaluator.set_vessel_data([own, target])
    stateful = evaluator.evaluate()
    direct = Evaluator().evaluate([own, target])
    assert stateful.to_dict() == direct.to_dict()
    evaluator.print_vessel_scores(0)
    assert capsys.readouterr().out


def test_target_grounding_is_reported_without_blame_on_ship0_algorithm() -> None:
    ownship = VesselEvaluation(0, 10.0, False, None, "EVALUATED", 0.5, 1.0, 1.0)
    target = VesselEvaluation(1, 0.0, True, 0.5, "EVALUATED", 0.0, 1.0, 1.0)
    aggregate = _aggregate([], [ownship, target])
    gate = _hard_gate([], [ownship, target], {})
    grounding = next(check for check in gate.checks if check.check_id == "physical_grounding")
    assert aggregate["grounding_count"] == 0
    assert aggregate["global_grounding_count"] == 1
    assert grounding.outcome == "PASS"
    assert grounding.evidence["global_all_vessel_grounding_count"] == 1
