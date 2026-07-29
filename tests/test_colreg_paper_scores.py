from __future__ import annotations

import numpy as np
import pytest

from colav_simulator.evaluation.profiles import load_evaluator_profile
from colav_simulator.evaluation.scoring import (
    non_apparent_penalty,
    pose_score,
    range_safety_score,
    score_pair,
    total_safety_score,
)


def test_paper_range_score_is_continuous_at_all_breakpoints() -> None:
    profile = load_evaluator_profile("oe2023_simulated-v1")
    expected = {
        200.0: 1.0,
        100.0: 0.8,
        50.0: 0.5,
        35.0: 0.0,
        20.0: 0.0,
    }
    for distance, value in expected.items():
        assert range_safety_score(distance, profile) == pytest.approx(value)
    epsilon = 1e-7
    for boundary in (200.0, 100.0, 50.0, 35.0):
        left = range_safety_score(boundary - epsilon, profile)
        right = range_safety_score(boundary + epsilon, profile)
        assert left == pytest.approx(right, abs=1e-6)


def test_safety_score_obeys_paper_collision_and_preferred_boundaries() -> None:
    assert total_safety_score(0.0, 1.0) == 0.0
    assert total_safety_score(1.0, 0.0) == 1.0
    assert total_safety_score(0.5, 0.2) == pytest.approx(0.6)


def test_pose_and_apparent_scores_are_bounded_and_direction_sensitive() -> None:
    profile = load_evaluator_profile("oe2023_simulated-v1")
    poor = pose_score(0.0, 0.0, profile)
    good = pose_score(np.pi / 2.0, np.pi, profile)
    assert 0.0 <= poor < good <= 1.0
    assert non_apparent_penalty(0.0, np.deg2rad(2.0), np.deg2rad(30.0)) == 1.0
    assert non_apparent_penalty(np.deg2rad(30.0), np.deg2rad(2.0), np.deg2rad(30.0)) == 0.0


def test_pair_score_exposes_formula_evidence_and_rule_specific_metrics() -> None:
    profile = load_evaluator_profile("oe2023_simulated-v1")
    metrics, evidence = score_pair(
        encounter="head_on",
        courses_rad=np.deg2rad(np.array([0.0, 5.0, 20.0, 35.0])),
        speeds_mps=np.full(4, 7.0),
        distances_m=np.array([1900.0, 900.0, 400.0, 200.0]),
        stages=np.array([2, 2, 3, 4]),
        cpa_index=3,
        contact_angle_rad=np.pi / 2.0,
        relative_bearing_rad=np.pi,
        profile=profile,
    )
    assert metrics["S14"] is not None
    assert metrics["S13"] is None
    assert evidence["S14"].formula_id == "oe2023-eq27"
    assert evidence["S13"].status == "NOT_APPLICABLE"
    assert all(value is None or 0.0 <= value <= 1.0 for value in metrics.values())
