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
    assert result.reproduction_status == "functional_reproduction"


def test_no_overlap_is_reported_not_scored() -> None:
    ownship = vessel(0, np.array([0.0, 1.0]), np.array([0.0, 1.0]), 1.0, 0.0)
    target = vessel(1, np.array([5.0, 6.0]), np.array([5.0, 6.0]), 1.0, 0.0)
    target.timestamps = np.array([10.0, 11.0])
    result = Evaluator().evaluate([ownship, target])
    assert result.pair_results == []
    assert "No overlapping samples" in result.warnings[-1]
