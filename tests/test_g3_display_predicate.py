from __future__ import annotations

import numpy as np
import pytest

from colav_simulator.experiment.g3_gate import PREDICATE_VERSION, evaluate_g3_display


def _manifest(algorithm: str) -> dict:
    return {
        "requested_algorithm": algorithm,
        "executed_algorithm": algorithm,
        "fallback_used": False,
        "state": "FINISHED",
        "failure_status": None,
        "scenario_hash": "scenario",
        "enc_hash": "enc",
        "seeds": {"base": 0, "scenario": 1, "sensor": 2, "tracker": 3, "algorithm": 4},
    }


def _frame(
    time_s: float,
    own_east: float,
    *,
    heading_rad: float = 0.0,
    speed_mps: float = 5.0,
    target_east: float = 18.0,
    solver_executed: bool = False,
) -> dict:
    planner = {
        "solver_executed": solver_executed,
        "predicted_trajectory": np.zeros((9, 2)).tolist() if solver_executed else None,
    }
    return {
        "Ship0": {
            "timestamp": time_s,
            "north": 0.0,
            "east": own_east,
            "psi": heading_rad,
            "u": speed_mps,
            "v": 0.0,
            "active": True,
            "colav": {"planner": planner, "diagnostics": {"fallback_used": False}},
        },
        "Ship1": {
            "timestamp": time_s,
            "north": 0.0,
            "east": target_east,
            "psi": np.pi,
            "u": 5.0,
            "v": 0.0,
            "active": True,
        },
    }


def _evidence() -> dict:
    nominal_frames = [_frame(0.0, 0.0), _frame(1.0, 5.0), _frame(2.0, 10.0)]
    candidate_frames = [
        _frame(0.0, 0.0, solver_executed=True),
        _frame(1.0, 2.0, heading_rad=np.deg2rad(3.0)),
        _frame(2.0, 4.0, heading_rad=np.deg2rad(3.0)),
    ]
    events = [{"type": "time_limit"}, {"type": "session_finished"}]
    return {
        "nominal_frames": nominal_frames,
        "candidate_frames": candidate_frames,
        "nominal_events": events,
        "candidate_events": events,
        "nominal_manifest": _manifest("nominal"),
        "candidate_manifest": _manifest("vo"),
        "ship_info": {
            "Ship0": {"length": 8.0, "width": 4.0},
            "Ship1": {"length": 8.0, "width": 4.0},
        },
        "expected_algorithm": "vo",
        "dt_sim": 1.0,
    }


def test_g3_predicate_accepts_safe_observable_real_solve() -> None:
    result = evaluate_g3_display(**_evidence())

    assert result.passed, result.to_dict()
    assert result.predicate_version == PREDICATE_VERSION
    assert result.metrics["solve_count"] == 1
    assert result.metrics["max_heading_delta_deg"] == pytest.approx(3.0)


@pytest.mark.parametrize(
    ("mutation", "failed_check"),
    (
        ("no_nominal_threat", "nominal_threat"),
        ("fallback", "no_fallback"),
        ("no_solve", "real_solve"),
        ("invalid_shape", "finite_9xn_plans"),
        ("nonfinite_plan", "finite_9xn_plans"),
        ("collision", "no_hard_failure"),
        ("grounding", "no_hard_failure"),
        ("no_action", "observable_action"),
        ("enc_mismatch", "same_run_inputs"),
        ("bad_clock", "clock_valid"),
    ),
)
def test_g3_predicate_rejects_failed_raw_evidence(mutation: str, failed_check: str) -> None:
    evidence = _evidence()
    if mutation == "no_nominal_threat":
        for frame in evidence["nominal_frames"]:
            frame["Ship1"]["east"] = 100.0
    elif mutation == "fallback":
        evidence["candidate_manifest"]["fallback_used"] = True
    elif mutation == "no_solve":
        evidence["candidate_frames"][0]["Ship0"]["colav"]["planner"]["solver_executed"] = False
    elif mutation == "invalid_shape":
        evidence["candidate_frames"][0]["Ship0"]["colav"]["planner"]["predicted_trajectory"] = np.zeros((8, 2))
    elif mutation == "nonfinite_plan":
        prediction = np.zeros((9, 2))
        prediction[0, 0] = np.nan
        evidence["candidate_frames"][0]["Ship0"]["colav"]["planner"]["predicted_trajectory"] = prediction
    elif mutation in {"collision", "grounding"}:
        evidence["candidate_events"].append({"type": mutation})
    elif mutation == "no_action":
        for candidate, nominal in zip(evidence["candidate_frames"], evidence["nominal_frames"], strict=True):
            candidate["Ship0"]["psi"] = nominal["Ship0"]["psi"]
            candidate["Ship0"]["u"] = nominal["Ship0"]["u"]
    elif mutation == "enc_mismatch":
        evidence["candidate_manifest"]["enc_hash"] = "different"
    elif mutation == "bad_clock":
        evidence["candidate_frames"][2]["Ship0"]["timestamp"] = 1.5

    result = evaluate_g3_display(**evidence)

    assert not result.passed
    assert result.checks[failed_check] is False


def test_g3_predicate_rejects_one_unsafe_multiship_target() -> None:
    evidence = _evidence()
    evidence["ship_info"]["Ship2"] = {"length": 8.0, "width": 4.0}
    for frame in evidence["nominal_frames"]:
        frame["Ship2"] = {**frame["Ship1"], "east": 100.0}
    for frame in evidence["candidate_frames"]:
        frame["Ship2"] = {**frame["Ship1"], "east": frame["Ship0"]["east"] + 2.0}

    result = evaluate_g3_display(**evidence)

    assert not result.passed
    assert result.checks["all_targets_observed"]
    assert not result.checks["footprint_clearance"]
