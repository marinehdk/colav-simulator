from __future__ import annotations

import numpy as np
import pytest
from shapely.geometry import box

from colav_simulator.core.collision import (
    VesselPose,
    c2a_first_contact,
    c2a_grounding_first_contact,
)


def pose(north: float, east: float, heading: float = 0.0, length: float = 2.0, width: float = 2.0) -> VesselPose:
    return VesselPose(north, east, heading, length, width)


def test_c2a_reports_analytic_first_contact_for_linear_head_on_motion() -> None:
    result = c2a_first_contact(
        pose(-10.0, 0.0),
        pose(10.0, 0.0),
        pose(0.0, 0.0),
        pose(0.0, 0.0),
        interval_start_s=0.0,
        interval_end_s=10.0,
        time_tolerance_s=1e-4,
    )
    assert result.collided is True
    assert result.oracle_id == "c2a-rect2d-v1"
    assert result.toc_s == pytest.approx(4.0, abs=2e-3)
    assert result.bracket_s is not None
    assert result.bracket_s[1] - result.bracket_s[0] <= 1e-4


def test_c2a_rejects_synchronized_sweep_false_positive() -> None:
    result = c2a_first_contact(
        pose(-10.0, 0.0),
        pose(10.0, 0.0),
        pose(10.0, 0.0),
        pose(30.0, 0.0),
    )
    assert result.collided is False
    assert result.toc_s is None


def test_c2a_detects_rotation_contact_between_endpoints() -> None:
    result = c2a_first_contact(
        pose(0.0, 0.0, 0.0, 10.0, 1.0),
        pose(0.0, 0.0, np.pi / 2.0, 10.0, 1.0),
        pose(3.5, 3.5, 0.0, 1.0, 1.0),
        pose(3.5, 3.5, 0.0, 1.0, 1.0),
    )
    assert result.collided is True
    assert 0.0 < result.toc_s < 1.0


def test_grounding_oracle_uses_full_footprint_not_center_point() -> None:
    hazard = box(-1.0, 4.0, 1.0, 6.0)
    result = c2a_grounding_first_contact(
        pose(0.0, 0.0, 0.0, length=8.0, width=2.0),
        pose(4.0, 0.0, 0.0, length=8.0, width=2.0),
        hazard,
        interval_start_s=20.0,
        interval_end_s=24.0,
    )
    assert result.collided is True
    assert result.toc_s == pytest.approx(20.0)


def test_iteration_limit_is_conservative_not_a_false_negative() -> None:
    result = c2a_first_contact(
        pose(-100.0, 0.0),
        pose(100.0, 0.0),
        pose(0.0, -100.0, np.pi / 2.0),
        pose(0.0, 100.0, np.pi / 2.0),
        max_iterations=1,
    )
    assert result.collided is True
    assert result.status == "ITERATION_LIMIT_CONSERVATIVE_CONTACT"
    assert result.bracket_s is not None
