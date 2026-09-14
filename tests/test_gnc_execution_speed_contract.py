"""The public VO solve must respect an execution-side hard speed contract."""

import numpy as np
import pytest

from colav_simulator.core.colav.kuwata_vo_alg.kuwata_vo import VO


def test_open_transit_gate_cannot_override_execution_ceiling():
    vo = VO()
    reference = vo.plan(
        0.0,
        np.array([8.0, 0.0]),
        np.array([0.0, 0.0, 0.0, 8.0, 0.0, 0.0]),
        [],
        os_course_time_constant_s=80.0,
        os_speed_time_constant_s=24.0,
        os_max_turn_rate_radps=0.021,
        os_avoidance_speed_cap_mps=3.2,
        os_min_steerage_speed_mps=3.0,
        os_execution_speed_policy={"cruise_cap_mps": 3.2, "ordinary_cap_mps": 3.2, "emergency_cap_mps": 3.2},
    )
    assert 0 < reference[3, 0] <= 3.2 + 1e-9


def test_invalid_execution_ceiling_is_not_ignored():
    vo = VO()
    with pytest.raises(ValueError, match="execution speed policy"):
        vo.plan(
            0.0,
            np.array([8.0, 0.0]),
            np.array([0.0, 0.0, 0.0, 8.0, 0.0, 0.0]),
            [],
            os_execution_speed_policy={"cruise_cap_mps": float("nan"), "ordinary_cap_mps": 8.0, "emergency_cap_mps": 3.2},
        )
