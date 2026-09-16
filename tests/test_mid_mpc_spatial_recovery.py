"""Native recovery heading errors follow candidate position, not an old clock."""

import casadi as ca
import numpy as np
import pytest

from colav_simulator.core.colav.mid_mpc.solver import _P, _navigation_recovery_errors


def test_slow_off_route_candidate_keeps_capture_error_after_timed_reference_straightens():
    parameters = ca.DM.zeros(26)
    parameters[_P.Y0] = 100.0
    parameters[_P.ROUTE_NORMAL_Y] = 1.0
    errors = _navigation_recovery_errors(
        ca.DM.zeros(4),
        ca.DM.ones(4),
        parameters,
        5.0,
        ca.DM.zeros(4),
        ca.DM(2),
        ca.DM(100),
    )
    values = np.array(errors).ravel()
    np.testing.assert_array_equal(values[:2], [0.0, 0.0])  # Active maneuver references remain authoritative.
    np.testing.assert_allclose(values[2:], np.pi / 4)  # Slow motion still has 100m XTE.
    parameters[_P.Y0] = 0.0
    aligned = _navigation_recovery_errors(
        ca.DM.zeros(4),
        ca.DM.ones(4),
        parameters,
        5.0,
        ca.DM.zeros(4),
        ca.DM(0),
        ca.DM(100),
    )
    assert np.max(np.abs(aligned)) == pytest.approx(0.0)
