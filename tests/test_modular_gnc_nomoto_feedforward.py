"""Nomoto inverse yaw feedforward in marine_pid (Issue #67 slice 3).

Fossen Handbook 2nd ed. SS15.2 model-feedforward structure: with the first-order
Nomoto equivalent I_eff*rdot + d_eff*r = N, the moment that "should" be applied
for a shaped reference is tau_FF = I_eff*rdot_d + d_eff*r_d, so the PID feedback
only suppresses residual error.  Here the feedforward is parameterised as
``yaw_accel_ff_gain * rdot_d + yaw_rate_ff_gain * r_d`` (defaults 0 = off) and
is added to the yaw channel before output limiting, keeping the DP-15
decomposition identity raw = p + i + d + feedforward.

The feedforward sources r_d/rdot_d from the reference shaper chain when the
shaper is enabled, otherwise from DirectReference values[5]/values[8].

Expected values are hand-derived independently of the implementation.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from colav_simulator.modular_gnc.contracts import DirectReference, NavigationState
from colav_simulator.modular_gnc.controller import MarinePID, MarinePIDConfig

RATE_LIMIT = 0.05
ACCEL_LIMIT = 0.02
DT = 0.1


def _pid(config: MarinePIDConfig) -> MarinePID:
    pid = MarinePID(config)
    pid.reset()
    return pid


def _ramp_reference(r_d: float, rdot_d: float, tick: int) -> DirectReference:
    values = np.zeros(9)
    values[2] = 0.5  # arbitrary heading target
    values[5] = r_d
    values[8] = rdot_d
    return DirectReference(values, tick)


class TestFeedforwardOnRampReference:
    def test_pure_ramp_reference_yields_hand_computed_feedforward(self) -> None:
        """Shaper off, ramp reference r_d=0.02, rdot_d=0.005.

        tau_FF must be 3.65e7*0.005 + 1.6e6*0.02 = 182500 + 32000 = 214500 N.m
        exactly.
        """
        config = MarinePIDConfig.from_params(
            {
                "kp": (0.0, 0.0, 0.0),
                "ki": (0.0, 0.0, 0.0),
                "kd": (0.0, 0.0, 0.0),
                "min_output": (-1e9, -1e9, -1e9),
                "max_output": (1e9, 1e9, 1e9),
                "yaw_rate_ff_gain": 1.6e6,
                "yaw_accel_ff_gain": 3.65e7,
            }
        )
        pid = _pid(config)
        load, trace = pid.compute_control(
            measurement=NavigationState(0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
            reference=_ramp_reference(0.02, 0.005, 0),
            dt_s=DT,
        )
        expected_ff = 3.65e7 * 0.005 + 1.6e6 * 0.02
        assert trace.feedforward[2] == pytest.approx(expected_ff, rel=1e-12)
        assert trace.raw_request[2] == pytest.approx(expected_ff, rel=1e-12)
        assert load.yaw_nm == pytest.approx(expected_ff, rel=1e-12)
        assert trace.feedforward[0] == 0.0
        assert trace.feedforward[1] == 0.0

        ff_detail = trace.details["nomoto_feedforward"]
        assert ff_detail["yaw_nm"] == pytest.approx(expected_ff, rel=1e-12)
        assert ff_detail["r_d_rad_s"] == pytest.approx(0.02)
        assert ff_detail["rdot_d_rad_s2"] == pytest.approx(0.005)

    def test_rate_plateau_with_shaper_sources_feedforward_from_chain(self) -> None:
        """Shaper on: on the constant-ROT plateau rdot_d=0 and r_d=rate limit.

        tau_FF is then yaw_rate_ff_gain * 0.05 exactly at the plateau
        invocation.
        """
        config = MarinePIDConfig.from_params(
            {
                "kp": (0.0, 0.0, 0.0),
                "ki": (0.0, 0.0, 0.0),
                "kd": (0.0, 0.0, 0.0),
                "min_output": (-1e9, -1e9, -1e9),
                "max_output": (1e9, 1e9, 1e9),
                "reference_shaper_enable": True,
                "heading_rate_limit_rad_s": RATE_LIMIT,
                "heading_accel_limit_rad_s2": ACCEL_LIMIT,
                "yaw_rate_ff_gain": 1.6e6,
                "yaw_accel_ff_gain": 3.65e7,
            }
        )
        pid = _pid(config)
        values = np.zeros(9)
        values[2] = math.pi / 2
        measurement = NavigationState(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        # Invocation 100 (t=10 s) is inside the constant-ROT phase: the
        # acceleration phase ends at t = rate/accel = 2.5 s and braking starts
        # below ~29 s, so the chain must sit on the rate plateau.
        trace = None
        for tick in range(101):
            _, trace = pid.compute_control(
                measurement=measurement,
                reference=DirectReference(values, tick),
                dt_s=DT,
                tick=tick,
                time_s=tick * DT,
            )
        assert trace is not None
        shaper = trace.details["reference_shaper"]
        assert shaper["r_d_rad_s"] == pytest.approx(RATE_LIMIT, rel=1e-9)
        assert shaper["rdot_d_rad_s2"] == pytest.approx(0.0, abs=1e-12)
        assert trace.feedforward[2] == pytest.approx(1.6e6 * RATE_LIMIT, rel=1e-9)

    def test_feedforward_is_limited_with_the_yaw_output(self) -> None:
        """tau_FF enters before output saturation: a capped output clamps it."""
        config = MarinePIDConfig.from_params(
            {
                "kp": (0.0, 0.0, 0.0),
                "ki": (0.0, 0.0, 0.0),
                "kd": (0.0, 0.0, 0.0),
                "min_output": (-1e9, -1e9, -1.0e5),
                "max_output": (1e9, 1e9, 1.0e5),
                "yaw_rate_ff_gain": 1.6e6,
                "yaw_accel_ff_gain": 3.65e7,
            }
        )
        pid = _pid(config)
        load, trace = pid.compute_control(
            measurement=NavigationState(0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
            reference=_ramp_reference(0.02, 0.005, 0),
            dt_s=DT,
        )
        assert trace.feedforward[2] == pytest.approx(2.145e5, rel=1e-12)
        assert trace.saturated_output[2] == pytest.approx(1.0e5, rel=1e-12)
        assert load.yaw_nm == pytest.approx(1.0e5, rel=1e-12)


class TestFeedforwardDefaultsAndValidation:
    def test_default_zero_gains_leave_output_untouched(self) -> None:
        config = MarinePIDConfig.from_params({"kp": (1.0, 1.0, 1.0), "ki": (0.0, 0.0, 0.0), "kd": (0.0, 0.0, 0.0)})
        assert config.yaw_rate_ff_gain == 0.0
        assert config.yaw_accel_ff_gain == 0.0

        pid = _pid(config)
        _, trace = pid.compute_control(
            measurement=NavigationState(0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
            reference=_ramp_reference(0.02, 0.005, 0),
            dt_s=DT,
        )
        assert trace.feedforward == (0.0, 0.0, 0.0)
        assert "nomoto_feedforward" not in trace.details

    def test_rejects_negative_and_nonfinite_gains(self) -> None:
        with pytest.raises(ValueError):
            MarinePIDConfig.from_params(
                {"kp": (0.0, 0.0, 0.0), "ki": (0.0, 0.0, 0.0), "kd": (0.0, 0.0, 0.0), "yaw_rate_ff_gain": -1.0}
            )
        with pytest.raises(ValueError):
            MarinePIDConfig.from_params(
                {"kp": (0.0, 0.0, 0.0), "ki": (0.0, 0.0, 0.0), "kd": (0.0, 0.0, 0.0), "yaw_accel_ff_gain": float("inf")}
            )

    def test_gains_roundtrip_through_dict_and_hash(self) -> None:
        config = MarinePIDConfig.from_params(
            {
                "kp": (0.0, 0.0, 0.0),
                "ki": (0.0, 0.0, 0.0),
                "kd": (0.0, 0.0, 0.0),
                "yaw_rate_ff_gain": 1.6e6,
                "yaw_accel_ff_gain": 3.65e7,
            }
        )
        rebuilt = MarinePIDConfig.from_params(config.to_dict())
        assert rebuilt.config_hash == config.config_hash
