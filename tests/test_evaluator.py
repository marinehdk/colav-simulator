from __future__ import annotations

import numpy as np
import pytest

from colav_simulator.common.vessel_data import VesselData
from colav_simulator.evaluation import Evaluator


def vessel(
    identifier: int,
    east: np.ndarray,
    north: np.ndarray,
    speed: float,
    course: float,
) -> VesselData:
    samples = east.size
    return VesselData(
        id=identifier,
        mmsi=100 + identifier,
        length=20.0,
        width=5.0,
        draft=2.0,
        xy=np.vstack((east, north)),
        sog=np.full(samples, speed),
        cog=np.full(samples, course),
        timestamps=np.arange(samples, dtype=float),
        first_valid_idx=0,
        last_valid_idx=samples - 1,
        travel_dist=float(np.linalg.norm([east[-1] - east[0], north[-1] - north[0]])),
    )


def test_head_on_classification_and_metrics() -> None:
    times = np.arange(0.0, 101.0)
    ownship = vessel(0, np.zeros(times.size), times * 5.0, 5.0, 0.0)
    target = vessel(1, np.zeros(times.size), 1000.0 - times * 5.0, 5.0, np.pi)
    result = Evaluator().evaluate([ownship, target])
    pair = result.pair_results[0]
    assert pair.encounter == "head_on"
    assert pair.initial_dcpa_m == pytest.approx(0.0, abs=1e-9)
    assert pair.initial_tcpa_s == pytest.approx(100.0)
    assert pair.minimum_distance_m == 0.0
    assert pair.metrics["S8"] == 0.0
    assert pair.metrics["S14"] == 0.0
    assert result.numerical_reproduction_confirmed is False
    assert result.reproduction_status == "behavior_compatible_reconstruction"
    assert result.schema_version == "2.0"
    assert result.hard_gate.outcome == "FAIL"
    assert pair.collision_oracle_id == "c2a-rect2d-v1"
    assert pair.metric_evidence["S14"]["formula_id"] == "oe2023-eq27"


def test_no_overlap_is_reported_not_scored() -> None:
    ownship = vessel(0, np.array([0.0, 1.0]), np.array([0.0, 1.0]), 1.0, 0.0)
    target = vessel(1, np.array([5.0, 6.0]), np.array([5.0, 6.0]), 1.0, 0.0)
    target.timestamps = np.array([10.0, 11.0])
    result = Evaluator().evaluate([ownship, target])
    assert result.pair_results == []
    assert "No synchronized finite samples" in result.warnings[-1]


def test_stress_only_evaluation_scores_nearest_and_potential_contact_pairs() -> None:
    times = np.arange(0.0, 11.0)
    ownship = vessel(0, np.zeros(times.size), times * 5.0, 5.0, 0.0)
    near = vessel(1, np.full(times.size, 30.0), times * 5.0, 5.0, 0.0)
    far = vessel(2, np.full(times.size, 1000.0), times * 5.0, 5.0, 0.0)

    result = Evaluator().evaluate(
        [ownship, near, far],
        execution_context={"stress_only": True},
    )

    assert result.evaluation_status == "PARTIAL"
    assert {(item.ownship_id, item.target_id) for item in result.pair_results} == {(0, 1)}
    assert any("Stress-only evaluation" in warning for warning in result.warnings)
