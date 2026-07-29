from __future__ import annotations

import numpy as np
import pytest

from colav_simulator.evaluation.encounter import (
    CPAStatus,
    cpa,
    instantaneous_cpa,
    trajectory_cpa,
)


def test_instantaneous_cpa_preserves_post_cpa_sign() -> None:
    result = instantaneous_cpa(np.array([-100.0, 0.0]), np.array([-10.0, 0.0]))
    assert result.dcpa_m == 100.0
    assert result.tcpa_signed_s == -10.0
    assert result.tcpa_forward_s == 0.0
    assert cpa(np.array([-100.0, 0.0]), np.array([-10.0, 0.0])) == (100.0, 0.0, -10.0)


def test_stationary_relative_geometry_is_explicit() -> None:
    result = instantaneous_cpa(np.array([3.0, 4.0]), np.zeros(2))
    assert result.status == CPAStatus.STATIONARY_RELATIVE
    assert result.dcpa_m == 5.0
    assert result.relative_position_at_cpa_ne_m == (3.0, 4.0)


def test_trajectory_cpa_uses_executed_synchronized_positions() -> None:
    times = np.array([10.0, 12.0, 14.0])
    own = np.array([[0.0, 10.0, 20.0], [0.0, 0.0, 0.0]])
    target = np.array([[12.0, 12.0, 12.0], [3.0, 1.0, 4.0]])
    result = trajectory_cpa(own, target, times)
    assert result.method == "synchronized_trajectory"
    assert result.dcpa_m == pytest.approx(np.sqrt(5.0))
    assert result.tcpa_signed_s == 2.0


def test_cpa_rejects_nonfinite_or_misaligned_inputs() -> None:
    with pytest.raises(ValueError, match="finite"):
        instantaneous_cpa(np.array([np.nan, 0.0]), np.zeros(2))
    with pytest.raises(ValueError, match="timestamps"):
        trajectory_cpa(np.zeros((2, 2)), np.zeros((2, 2)), np.zeros(3))
