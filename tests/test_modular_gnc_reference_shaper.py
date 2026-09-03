"""Third-order heading reference shaper inside the marine_pid chain (Issue #67 slice 2).

Fossen Handbook 2nd ed. SS15.2/SS12.1.1 reference model: an integrator chain
(psi_d, r_d, rdot_d) with rate and acceleration saturation turns a heading step
into a three-phase S-curve (ROT acceleration / constant ROT / ROT braking), so
the PID never sees a step.

All behaviour is asserted through the public ``MarinePID.compute_control``
seam against independently hand-derived quantities:
- rate/acceleration of the shaped trajectory never exceed the configured caps;
- the initial ramp is exactly r_d[k] = k * accel * dt while braking is inactive;
- the rate plateau reaches the configured rate limit;
- the approach is monotone and converges to the commanded heading;
- angle wrapping takes the shortest path (350 deg -> 10 deg travels +20 deg).
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from colav_simulator.modular_gnc.contracts import DirectReference, NavigationState
from colav_simulator.modular_gnc.controller import MarinePID, MarinePIDConfig

RATE_LIMIT = 0.05  # rad/s (~2.9 deg/s)
ACCEL_LIMIT = 0.02  # rad/s^2
DT = 0.1  # s


def _shaped_config(**overrides: float) -> MarinePIDConfig:
    params: dict[str, object] = {
        "kp": (0.0, 0.0, 0.0),
        "ki": (0.0, 0.0, 0.0),
        "kd": (0.0, 0.0, 0.0),
        "min_output": (-1e9, -1e9, -1e9),
        "max_output": (1e9, 1e9, 1e9),
        "reference_shaper_enable": True,
        "heading_rate_limit_rad_s": RATE_LIMIT,
        "heading_accel_limit_rad_s2": ACCEL_LIMIT,
    }
    params.update(overrides)
    return MarinePIDConfig.from_params(params)


def _measurement(heading: float = 0.0, yaw_rate: float = 0.0) -> NavigationState:
    return NavigationState(0.0, 0.0, heading, 0.0, 0.0, yaw_rate)


def _reference(heading: float, tick: int) -> DirectReference:
    values = np.zeros(9)
    values[2] = heading
    return DirectReference(values, tick)


def _run_shaper(
    target_heading: float,
    measurement: NavigationState,
    ticks: int,
    config: MarinePIDConfig | None = None,
) -> list[tuple[float, float, float]]:
    """Drive the controller for ``ticks`` invocations; return the shaped (psi_d, r_d, rdot_d) chain."""
    pid = MarinePID(config or _shaped_config())
    pid.reset()
    chain = []
    for tick in range(ticks):
        _, trace = pid.compute_control(
            measurement=measurement,
            reference=_reference(target_heading, tick),
            dt_s=DT,
            tick=tick,
            time_s=tick * DT,
        )
        shaper = trace.details.get("reference_shaper")
        assert shaper is not None, "shaped chain must be exposed in the trace details"
        chain.append((shaper["psi_d_rad"], shaper["r_d_rad_s"], shaper["rdot_d_rad_s2"]))
    return chain


def _wrap(angle: float) -> float:
    return (angle + math.pi) % (2.0 * math.pi) - math.pi


class TestShaperLimits:
    def test_step_reference_never_exceeds_rate_or_accel_caps(self) -> None:
        chain = _run_shaper(math.pi / 2, _measurement(), ticks=400)

        for i in range(1, len(chain)):
            prev, cur = chain[i - 1], chain[i]
            dpsi = _wrap(cur[0] - prev[0])
            assert abs(dpsi) / DT <= RATE_LIMIT * (1.0 + 1e-9)
            assert abs(cur[1] - prev[1]) / DT <= ACCEL_LIMIT * (1.0 + 1e-9)

    def test_initial_acceleration_ramp_matches_hand_value(self) -> None:
        """Independent numeric check: while braking is inactive r_d[k] = k*accel*dt."""
        chain = _run_shaper(math.pi / 2, _measurement(), ticks=10)
        for k, (_, r_d, rdot_d) in enumerate(chain):
            assert r_d == pytest.approx(min((k + 1) * ACCEL_LIMIT * DT, RATE_LIMIT))
            assert rdot_d == pytest.approx(ACCEL_LIMIT, rel=1e-9)

    def test_rate_plateau_reaches_configured_limit(self) -> None:
        chain = _run_shaper(math.pi / 2, _measurement(), ticks=400)
        assert max(abs(r_d) for _, r_d, _ in chain) == pytest.approx(RATE_LIMIT, rel=1e-9)


class TestShaperConvergence:
    def test_monotone_convergence_to_commanded_heading(self) -> None:
        chain = _run_shaper(math.pi / 2, _measurement(), ticks=600)
        terminal_band = ACCEL_LIMIT * DT * DT
        for i in range(1, len(chain)):
            step = _wrap(chain[i][0] - chain[i - 1][0])
            if step < 0.0:
                # Reversals are allowed only as terminal-band chatter, bounded by
                # two derived deadbeat-band scales (accel*dt^2 each: one for the
                # rate clamp, one for the preceding residual), and only beside
                # the target.
                assert step >= -2.0 * terminal_band
                assert abs(_wrap(math.pi / 2 - chain[i - 1][0])) <= 10.0 * terminal_band

        final_error = _wrap(math.pi / 2 - chain[-1][0])
        assert abs(final_error) < 1e-3
        assert abs(chain[-1][1]) < 1e-3

    def test_travel_never_overshoots_the_commanded_heading(self) -> None:
        chain = _run_shaper(math.pi / 2, _measurement(), ticks=600)
        for psi_d, _, _ in chain:
            assert _wrap(psi_d) <= math.pi / 2 + 1e-3


class TestShaperWrap:
    def test_shortest_path_across_wrap_boundary(self) -> None:
        """350 deg -> 10 deg must travel +20 deg, never the -340 deg long way."""
        chain = _run_shaper(math.radians(10.0), _measurement(heading=math.radians(-10.0)), ticks=400)

        total_travel = sum(_wrap(chain[i][0] - chain[i - 1][0]) for i in range(1, len(chain)))
        assert total_travel == pytest.approx(math.radians(20.0), abs=1e-3)

        for psi_d, _r_d, _ in chain:
            wrapped = _wrap(psi_d)
            assert math.radians(-10.0) - 1e-3 <= wrapped <= math.radians(10.0) + 1e-3
        assert _wrap(chain[-1][0]) == pytest.approx(math.radians(10.0), abs=1e-3)


class TestShaperLifecycle:
    def test_default_off_uses_raw_reference_and_hides_chain(self) -> None:
        config = MarinePIDConfig.from_params(
            {
                "kp": (1.0, 1.0, 1.0),
                "ki": (0.0, 0.0, 0.0),
                "kd": (0.0, 0.0, 0.0),
            }
        )
        assert config.reference_shaper_enable is False

        pid = MarinePID(config)
        pid.reset()
        _, trace = pid.compute_control(
            measurement=_measurement(),
            reference=_reference(0.3, 0),
            dt_s=DT,
        )
        assert "reference_shaper" not in trace.details
        assert trace.errors[2] == pytest.approx(0.3)  # raw reference used directly

    def test_reset_is_idempotent_and_reproduces_identical_chains(self) -> None:
        pid = MarinePID(_shaped_config())
        pid.reset()
        first = []
        for tick in range(50):
            _, trace = pid.compute_control(_measurement(), _reference(math.pi / 2, tick), dt_s=DT, tick=tick)
            first.append(trace.details["reference_shaper"])

        pid.reset()
        pid.reset()
        second = []
        for tick in range(50):
            _, trace = pid.compute_control(_measurement(), _reference(math.pi / 2, tick), dt_s=DT, tick=tick)
            second.append(trace.details["reference_shaper"])

        assert first == second

    def test_snapshot_restore_continues_shaped_chain_identically(self) -> None:
        pid = MarinePID(_shaped_config())
        pid.reset()
        for tick in range(20):
            pid.compute_control(_measurement(), _reference(math.pi / 2, tick), dt_s=DT, tick=tick)
        snap = pid.snapshot()

        continued = [
            pid.compute_control(_measurement(), _reference(math.pi / 2, tick), dt_s=DT, tick=tick)[1].details[
                "reference_shaper"
            ]
            for tick in range(20, 30)
        ]

        restored_pid = MarinePID(_shaped_config())
        restored_pid.reset()
        restored_pid.restore(snap)
        replay = [
            restored_pid.compute_control(_measurement(), _reference(math.pi / 2, tick), dt_s=DT, tick=tick)[1].details[
                "reference_shaper"
            ]
            for tick in range(20, 30)
        ]
        assert continued == replay


class TestShaperConfigValidation:
    def test_enabled_shaper_requires_positive_limits(self) -> None:
        with pytest.raises(ValueError, match="heading_rate_limit_rad_s"):
            MarinePIDConfig.from_params(
                {
                    "kp": (0.0, 0.0, 0.0),
                    "ki": (0.0, 0.0, 0.0),
                    "kd": (0.0, 0.0, 0.0),
                    "reference_shaper_enable": True,
                }
            )
        with pytest.raises(ValueError, match="heading_accel_limit_rad_s2"):
            MarinePIDConfig.from_params(
                {
                    "kp": (0.0, 0.0, 0.0),
                    "ki": (0.0, 0.0, 0.0),
                    "kd": (0.0, 0.0, 0.0),
                    "reference_shaper_enable": True,
                    "heading_rate_limit_rad_s": 0.05,
                }
            )

    def test_rejects_negative_or_nonfinite_limits(self) -> None:
        with pytest.raises(ValueError):
            MarinePIDConfig.from_params(
                {
                    "kp": (0.0, 0.0, 0.0),
                    "ki": (0.0, 0.0, 0.0),
                    "kd": (0.0, 0.0, 0.0),
                    "heading_rate_limit_rad_s": -0.05,
                }
            )
        with pytest.raises(ValueError):
            MarinePIDConfig.from_params(
                {
                    "kp": (0.0, 0.0, 0.0),
                    "ki": (0.0, 0.0, 0.0),
                    "kd": (0.0, 0.0, 0.0),
                    "heading_accel_limit_rad_s2": float("nan"),
                }
            )

    def test_shaper_params_roundtrip_through_dict_and_hash(self) -> None:
        config = _shaped_config()
        as_dict = config.to_dict()
        assert as_dict["reference_shaper_enable"] is True
        assert as_dict["heading_rate_limit_rad_s"] == RATE_LIMIT
        assert as_dict["heading_accel_limit_rad_s2"] == ACCEL_LIMIT
        rebuilt = MarinePIDConfig.from_params(as_dict)
        assert rebuilt.config_hash == config.config_hash
