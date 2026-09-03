"""Speed-adaptive yaw moment cap in marine_pid (Issue #67 slice 4).

Rudder/thruster yaw authority grows with the square of the advance speed, so a
static moment cap is unphysically generous at low speed and the previously
hard-coded +-6e8 N.m ceiling (Issue #67 root cause 4) was two orders of
magnitude beyond a 45 m workboat.  When ``yaw_limit_cap_nm`` > 0 the yaw channel
limits become +-min(cap, base + coeff * u^2) with u the measured surge;
otherwise the static min/max_output limits apply unchanged.

Expected limits are hand-computed from the piecewise definition; the saturated
output is asserted through the public ``MarinePID.compute_control`` seam with a
known P-term raw request (kp * error).
"""

from __future__ import annotations

import numpy as np
import pytest

from colav_simulator.modular_gnc.contracts import DirectReference, NavigationState
from colav_simulator.modular_gnc.controller import MarinePID, MarinePIDConfig

BASE_NM = 3.6e5
COEFF_NM_PER_MPS2 = 2500.0
CAP_NM = 9.6e5
KP_YAW = 1.0e6  # raw request = KP_YAW * heading error


def _config(**extra: float) -> MarinePIDConfig:
    params: dict[str, object] = {
        "kp": (0.0, 0.0, KP_YAW),
        "ki": (0.0, 0.0, 0.0),
        "kd": (0.0, 0.0, 0.0),
        "min_output": (-1e9, -1e9, -1e9),
        "max_output": (1e9, 1e9, 1e9),
    }
    params.update(extra)
    return MarinePIDConfig.from_params(params)


def _saturated_yaw(config: MarinePIDConfig, surge: float, heading_error: float) -> tuple[float, dict]:
    """Return (saturated yaw moment, trace details) for one invocation."""
    pid = MarinePID(config)
    pid.reset()
    values = np.zeros(9)
    values[2] = heading_error  # measurement heading is zero -> e_yaw = heading_error
    load, trace = pid.compute_control(
        measurement=NavigationState(0.0, 0.0, 0.0, surge, 0.0, 0.0),
        reference=DirectReference(values, 0),
        dt_s=0.1,
    )
    return load.yaw_nm, dict(trace.details)


class TestAdaptiveCap:
    def test_service_speed_limit_is_base_plus_coeff_u2(self) -> None:
        """U = 7.8 m/s: max_N = 3.6e5 + 2500*7.8^2 = 512100 N.m."""
        config = _config(
            yaw_limit_base_nm=BASE_NM,
            yaw_limit_speed_coeff=COEFF_NM_PER_MPS2,
            yaw_limit_cap_nm=CAP_NM,
        )
        yaw, details = _saturated_yaw(config, surge=7.8, heading_error=1.0)
        assert yaw == pytest.approx(3.6e5 + 2500.0 * 7.8**2, rel=1e-12)
        assert details["yaw_limit"]["max_nm"] == pytest.approx(3.6e5 + 2500.0 * 7.8**2, rel=1e-12)
        assert details["yaw_limit"]["surge_mps"] == pytest.approx(7.8)

    def test_zero_speed_limit_is_the_base(self) -> None:
        config = _config(
            yaw_limit_base_nm=BASE_NM,
            yaw_limit_speed_coeff=COEFF_NM_PER_MPS2,
            yaw_limit_cap_nm=CAP_NM,
        )
        yaw, details = _saturated_yaw(config, surge=0.0, heading_error=1.0)
        assert yaw == pytest.approx(BASE_NM, rel=1e-12)
        assert details["yaw_limit"]["max_nm"] == pytest.approx(BASE_NM, rel=1e-12)

    def test_piecewise_boundary_clamps_at_the_cap(self) -> None:
        """Piecewise boundary: base + coeff*u^2 reaches the cap and stays there.

        The crossover is u = sqrt((9.6e5 - 3.6e5)/2500) ~ 15.49 m/s; beyond it
        the limit stays the cap.
        """
        config = _config(
            yaw_limit_base_nm=BASE_NM,
            yaw_limit_speed_coeff=COEFF_NM_PER_MPS2,
            yaw_limit_cap_nm=CAP_NM,
        )
        boundary = ((CAP_NM - BASE_NM) / COEFF_NM_PER_MPS2) ** 0.5

        yaw_at_boundary, details_at = _saturated_yaw(config, surge=boundary, heading_error=1.0)
        assert details_at["yaw_limit"]["max_nm"] == pytest.approx(CAP_NM, rel=1e-9)

        yaw_beyond, details_beyond = _saturated_yaw(config, surge=20.0, heading_error=1.0)
        assert yaw_beyond == pytest.approx(CAP_NM, rel=1e-12)
        assert details_beyond["yaw_limit"]["max_nm"] == pytest.approx(CAP_NM, rel=1e-12)

    def test_cap_applies_symmetrically_to_both_signs(self) -> None:
        config = _config(
            yaw_limit_base_nm=BASE_NM,
            yaw_limit_speed_coeff=COEFF_NM_PER_MPS2,
            yaw_limit_cap_nm=CAP_NM,
        )
        yaw_positive, _ = _saturated_yaw(config, surge=7.8, heading_error=1.0)
        yaw_negative, _ = _saturated_yaw(config, surge=7.8, heading_error=-1.0)
        limit = 3.6e5 + 2500.0 * 7.8**2
        assert yaw_positive == pytest.approx(limit, rel=1e-12)
        assert yaw_negative == pytest.approx(-limit, rel=1e-12)


class TestCapDisabled:
    def test_default_off_keeps_static_min_max_output(self) -> None:
        config = _config(min_output=(-1e9, -1e9, -7.0e5), max_output=(1e9, 1e9, 7.0e5))
        yaw, details = _saturated_yaw(config, surge=7.8, heading_error=1.0)
        assert yaw == pytest.approx(7.0e5, rel=1e-12)
        assert "yaw_limit" not in details

    def test_zero_params_do_not_activate_the_cap(self) -> None:
        config = _config(yaw_limit_base_nm=0.0, yaw_limit_speed_coeff=0.0, yaw_limit_cap_nm=0.0)
        yaw, _ = _saturated_yaw(config, surge=7.8, heading_error=1.0)
        assert yaw == pytest.approx(KP_YAW, rel=1e-12)  # unlimited besides +-1e9 static


class TestCapValidation:
    def test_rejects_negative_and_nonfinite_cap_parameters(self) -> None:
        with pytest.raises(ValueError):
            _config(yaw_limit_base_nm=-1.0, yaw_limit_speed_coeff=0.0, yaw_limit_cap_nm=1.0)
        with pytest.raises(ValueError):
            _config(yaw_limit_base_nm=0.0, yaw_limit_speed_coeff=-1.0, yaw_limit_cap_nm=1.0)
        with pytest.raises(ValueError):
            _config(yaw_limit_base_nm=0.0, yaw_limit_speed_coeff=0.0, yaw_limit_cap_nm=-1.0)
        with pytest.raises(ValueError):
            _config(yaw_limit_cap_nm=float("nan"))

    def test_cap_parameters_roundtrip_through_dict_and_hash(self) -> None:
        config = _config(
            yaw_limit_base_nm=BASE_NM,
            yaw_limit_speed_coeff=COEFF_NM_PER_MPS2,
            yaw_limit_cap_nm=CAP_NM,
        )
        rebuilt = MarinePIDConfig.from_params(config.to_dict())
        assert rebuilt.config_hash == config.config_hash
