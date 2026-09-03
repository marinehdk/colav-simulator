"""Unit tests for transparent 3DOF Marine PID controller (Issue #55, VR-13..15/19, TS-19..21, G3..G5, A1-A2)."""

from __future__ import annotations

import math
from dataclasses import FrozenInstanceError

import numpy as np
import pytest

from colav_simulator.modular_gnc.configuration import normalize_ship_modules
from colav_simulator.modular_gnc.contracts import (
    AchievedGeneralizedLoad,
    AchievedLoadStatus,
    CommandInput,
    DirectReference,
    NavigationState,
)
from colav_simulator.modular_gnc.controller import (
    MarinePID,
    MarinePIDConfig,
    wrap_to_pi,
)
from colav_simulator.modular_gnc.stack import ModularShipStack


def _make_nav(
    north: float = 0.0,
    east: float = 0.0,
    heading: float = 0.0,
    surge: float = 0.0,
    sway: float = 0.0,
    yaw_rate: float = 0.0,
) -> NavigationState:
    """Helper to create a valid NavigationState."""
    return NavigationState(
        north_m=north,
        east_m=east,
        heading_rad=heading,
        surge_mps=surge,
        sway_mps=sway,
        yaw_rate_radps=yaw_rate,
    )


def _make_ref(
    north_d: float = 0.0,
    east_d: float = 0.0,
    psi_d: float = 0.0,
    u_d: float = 0.0,
    v_d: float = 0.0,
    r_d: float = 0.0,
    ax_d: float = 0.0,
    ay_d: float = 0.0,
    rdot_d: float = 0.0,
    latched_tick: int = 0,
) -> DirectReference:
    """Helper to create a valid DirectReference."""
    return DirectReference(
        values=np.array([north_d, east_d, psi_d, u_d, v_d, r_d, ax_d, ay_d, rdot_d], dtype=np.float64),
        latched_tick=latched_tick,
    )


# ---------------------------------------------------------------------------
# 1. Strict Configuration Validation Tests
# ---------------------------------------------------------------------------


def test_marine_pid_config_valid_and_immutable() -> None:
    """MarinePIDConfig constructs cleanly, validates all fields, and is frozen."""
    config = MarinePIDConfig(
        kp=(1000.0, 500.0, 2000.0),
        ki=(100.0, 50.0, 200.0),
        kd=(200.0, 100.0, 400.0),
        tau_d=(0.05, 0.05, 0.1),
        antiwindup_gain=(2.0, 2.0, 2.0),
        min_output=(-10000.0, -5000.0, -20000.0),
        max_output=(10000.0, 5000.0, 20000.0),
        feedforward_gain=(1.0, 0.0, 1.0),
        integral_limit=(5000.0, 2500.0, 10000.0),
        allow_ideal_passthrough=True,
    )
    assert config.kp == (1000.0, 500.0, 2000.0)
    assert config.ki == (100.0, 50.0, 200.0)
    assert config.kd == (200.0, 100.0, 400.0)
    assert len(config.config_hash) == 64

    # Frozen immutability
    with pytest.raises(FrozenInstanceError):
        config.kp = (0.0, 0.0, 0.0)  # type: ignore[misc]


def test_marine_pid_config_rejects_bools_and_nonfinite() -> None:
    """Config rejects bools masquerading as floats, NaNs, infinities, and negatives."""
    # Bools in gain tuples
    with pytest.raises(TypeError, match="bool"):
        MarinePIDConfig(
            kp=(True, 1.0, 1.0),  # type: ignore[arg-type]
            ki=(1.0, 1.0, 1.0),
            kd=(1.0, 1.0, 1.0),
        )

    # Negative gains
    with pytest.raises(ValueError, match="non-negative"):
        MarinePIDConfig(
            kp=(-1.0, 1.0, 1.0),
            ki=(1.0, 1.0, 1.0),
            kd=(1.0, 1.0, 1.0),
        )

    # Non-finite values
    with pytest.raises(ValueError, match="finite"):
        MarinePIDConfig(
            kp=(float("nan"), 1.0, 1.0),
            ki=(1.0, 1.0, 1.0),
            kd=(1.0, 1.0, 1.0),
        )

    # Inverted output limits (min > max)
    with pytest.raises(ValueError, match="cannot exceed max_output"):
        MarinePIDConfig(
            kp=(1.0, 1.0, 1.0),
            ki=(1.0, 1.0, 1.0),
            kd=(1.0, 1.0, 1.0),
            min_output=(100.0, 0.0, 0.0),
            max_output=(50.0, 0.0, 0.0),
        )

    # Wrong shape
    with pytest.raises(ValueError, match="3-element sequence"):
        MarinePIDConfig(
            kp=(1.0, 1.0),  # type: ignore[arg-type]
            ki=(1.0, 1.0, 1.0),
            kd=(1.0, 1.0, 1.0),
        )


def test_marine_pid_config_serialization_roundtrip_and_hash() -> None:
    """Config converts to/from dictionary and produces deterministic config_hash."""
    config = MarinePIDConfig(
        kp=(100.0, 200.0, 300.0),
        ki=(10.0, 20.0, 30.0),
        kd=(5.0, 10.0, 15.0),
    )
    d = config.to_dict()
    assert d["kp"] == [100.0, 200.0, 300.0]
    assert d["config_hash"] == config.config_hash

    config2 = MarinePIDConfig.from_params(d)
    assert config2.config_hash == config.config_hash
    assert config2.kp == config.kp


# ---------------------------------------------------------------------------
# 2. Derivative on Measurement & Reference Jump Tests (No Kick)
# ---------------------------------------------------------------------------


def test_derivative_on_measurement_no_kick_on_reference_jump() -> None:
    """A step jump in reference setpoint produces NO derivative kick (VR-15, TS-20)."""
    config = MarinePIDConfig(
        kp=(100.0, 0.0, 500.0),
        ki=(0.0, 0.0, 0.0),
        kd=(50.0, 0.0, 200.0),
        tau_d=(0.0, 0.0, 0.0),  # instantaneous derivative for clean test
    )
    ctrl = MarinePID(config)
    ctrl.reset()

    nav = _make_nav(surge=2.0, heading=0.0)
    ref_initial = _make_ref(u_d=2.0, psi_d=0.0)

    # Tick 0: Steady state
    _, trace0 = ctrl.compute_control(nav, ref_initial, dt_s=0.1, tick=0)
    assert trace0.d_term == (0.0, 0.0, 0.0)

    # Tick 1: Setpoint jump: u_d jumps from 2.0 to 10.0, psi_d jumps from 0.0 to pi/4
    # But ship measurement has NOT changed (surge=2.0, heading=0.0).
    ref_jump = _make_ref(u_d=10.0, psi_d=math.pi / 4.0)
    _, trace1 = ctrl.compute_control(nav, ref_jump, dt_s=0.1, tick=1)

    # D-term must remain EXACTLY 0.0 because derivative is on measurement, not error!
    assert trace1.d_term[0] == pytest.approx(0.0, abs=1e-12)
    assert trace1.d_term[2] == pytest.approx(0.0, abs=1e-12)

    # P-term responds to error jump immediately
    assert trace1.p_term[0] == pytest.approx(100.0 * (10.0 - 2.0))
    assert trace1.p_term[2] == pytest.approx(500.0 * (math.pi / 4.0))


def test_derivative_on_measurement_damping_action() -> None:
    """Physical motion in measurement produces negative D-term (opposing motion)."""
    config = MarinePIDConfig(
        kp=(0.0, 0.0, 0.0),
        ki=(0.0, 0.0, 0.0),
        kd=(50.0, 0.0, 200.0),
        tau_d=(0.0, 0.0, 0.0),
    )
    ctrl = MarinePID(config)
    ctrl.reset()

    ref = _make_ref(u_d=5.0, psi_d=0.0)

    # Step 0: surge = 2.0
    nav0 = _make_nav(surge=2.0, heading=0.0)
    ctrl.compute_control(nav0, ref, dt_s=0.1, tick=0)

    # Step 1: surge accelerates from 2.0 to 3.0 (delta = +1.0 m/s in 0.1s -> rate = +10.0 m/s^2)
    nav1 = _make_nav(surge=3.0, heading=0.0)
    _, trace1 = ctrl.compute_control(nav1, ref, dt_s=0.1, tick=1)

    # D-term = - Kd * d_meas = -50.0 * 10.0 = -500.0 N
    assert trace1.d_term[0] == pytest.approx(-500.0, rel=1e-6)


# ---------------------------------------------------------------------------
# 3. Heading Wrap Tests in Error and Derivative
# ---------------------------------------------------------------------------


def test_heading_wrap_error_and_derivative() -> None:
    """Heading errors and measurement derivatives wrap seamlessly across [-pi, pi] (TS-04, VR-20)."""
    config = MarinePIDConfig(
        kp=(0.0, 0.0, 100.0),
        ki=(0.0, 0.0, 0.0),
        kd=(0.0, 0.0, 50.0),
        tau_d=(0.0, 0.0, 0.0),
    )
    ctrl = MarinePID(config)
    ctrl.reset()

    # Case A: Error across pi boundary: ship at +170 deg (2.967 rad), target at -170 deg (-2.967 rad)
    # Shortest path is turning right by +20 deg (0.349 rad)
    heading_meas = math.radians(170.0)
    heading_target = math.radians(-170.0)
    nav0 = _make_nav(heading=heading_meas)
    ref = _make_ref(psi_d=heading_target)

    _, trace0 = ctrl.compute_control(nav0, ref, dt_s=0.1, tick=0)
    expected_error = wrap_to_pi(heading_target - heading_meas)  # +20 deg in radians
    assert trace0.errors[2] == pytest.approx(expected_error, abs=1e-6)
    assert trace0.p_term[2] == pytest.approx(100.0 * expected_error, abs=1e-6)

    # Case B: Turning right across +pi/-pi boundary
    # Measurement moves from +179 deg to -179 deg (clockwise turn of +2 deg = 0.0349 rad)
    nav1 = _make_nav(heading=math.radians(-179.0))
    _, trace1 = ctrl.compute_control(nav1, ref, dt_s=0.1, tick=1)

    # Wrapped delta = +2 deg in 0.1s -> rate = +20 deg/s = 0.349 rad/s
    expected_rate = wrap_to_pi(math.radians(-179.0) - math.radians(170.0)) / 0.1
    assert expected_rate == pytest.approx(math.radians(11.0) / 0.1, rel=1e-6)
    assert trace1.d_term[2] == pytest.approx(-50.0 * expected_rate, rel=1e-6)


# ---------------------------------------------------------------------------
# 4. dt-Aware Derivative Filter Response
# ---------------------------------------------------------------------------


def test_dt_aware_derivative_filter_for_different_dt() -> None:
    """Filter coefficient alpha adapts to dt: alpha = dt / (tau_d + dt) (TS-20, VR-15)."""
    tau_d = 0.2
    config = MarinePIDConfig(
        kp=(0.0, 0.0, 0.0),
        ki=(0.0, 0.0, 0.0),
        kd=(10.0, 0.0, 0.0),
        tau_d=(tau_d, 0.1, 0.1),
    )

    # Test dt = 0.05s
    ctrl1 = MarinePID(config)
    ctrl1.reset()
    nav_init = _make_nav(surge=0.0)
    ref = _make_ref(u_d=5.0)
    ctrl1.compute_control(nav_init, ref, dt_s=0.05, tick=0)

    nav_step1 = _make_nav(surge=1.0)
    _, trace_dt1 = ctrl1.compute_control(nav_step1, ref, dt_s=0.05, tick=1)
    alpha1 = 0.05 / (tau_d + 0.05)  # 0.05 / 0.25 = 0.20
    d_raw1 = 1.0 / 0.05  # 20.0 m/s^2
    expected_d_filt1 = alpha1 * d_raw1  # 4.0
    assert trace_dt1.d_term[0] == pytest.approx(-10.0 * expected_d_filt1, rel=1e-6)

    # Test dt = 0.1s
    ctrl2 = MarinePID(config)
    ctrl2.reset()
    ctrl2.compute_control(nav_init, ref, dt_s=0.1, tick=0)

    nav_step2 = _make_nav(surge=1.0)
    _, trace_dt2 = ctrl2.compute_control(nav_step2, ref, dt_s=0.1, tick=1)
    alpha2 = 0.1 / (tau_d + 0.1)  # 0.1 / 0.3 = 0.333333
    d_raw2 = 1.0 / 0.1  # 10.0 m/s^2
    expected_d_filt2 = alpha2 * d_raw2  # 3.333333
    assert trace_dt2.d_term[0] == pytest.approx(-10.0 * expected_d_filt2, rel=1e-6)


# ---------------------------------------------------------------------------
# 5. Term Decomposition (P, I, D, Feedforward, Raw Request)
# ---------------------------------------------------------------------------


def test_pid_decomposition_and_raw_request_algebraic_identity() -> None:
    """raw_request == P + I + D + FF holds identically every tick (TS-20, VR-18)."""
    config = MarinePIDConfig(
        kp=(100.0, 50.0, 200.0),
        ki=(10.0, 5.0, 20.0),
        kd=(20.0, 10.0, 40.0),
        feedforward_gain=(1.0, 1.0, 1.0),
        tau_d=(0.1, 0.1, 0.1),
    )
    ctrl = MarinePID(config)
    ctrl.reset()

    nav = _make_nav(surge=2.0, sway=0.1, heading=0.2)
    ref = _make_ref(u_d=3.0, v_d=0.0, psi_d=0.5, ax_d=0.5, ay_d=0.1, rdot_d=0.02)

    for tick in range(5):
        _, trace = ctrl.compute_control(nav, ref, dt_s=0.1, tick=tick, time_s=tick * 0.1)
        for ch in range(3):
            expected_raw = trace.p_term[ch] + trace.i_term[ch] + trace.d_term[ch] + trace.feedforward[ch]
            assert trace.raw_request[ch] == pytest.approx(expected_raw, abs=1e-10)


# ---------------------------------------------------------------------------
# 6. Saturation and Single Tracking Anti-Windup Path
# ---------------------------------------------------------------------------


def test_saturation_and_tracking_antiwindup_prevents_windup() -> None:
    """Positive/negative saturation triggers back-calculation anti-windup to prevent integral windup (VR-15, TS-20)."""
    max_force = 1000.0
    kp = 100.0
    ki = 50.0
    kaw = 1.0  # Back-calculation gain
    config = MarinePIDConfig(
        kp=(kp, 0.0, 0.0),
        ki=(ki, 0.0, 0.0),
        kd=(0.0, 0.0, 0.0),
        antiwindup_gain=(kaw, 1.0, 1.0),
        min_output=(-max_force, -1000.0, -1000.0),
        max_output=(max_force, 1000.0, 1000.0),
    )
    ctrl = MarinePID(config)
    ctrl.reset()

    # Apply large constant error: u_d = 20.0, u = 0.0 -> error = 20.0
    # P-term alone is 100 * 20 = 2000.0 > max_force (1000.0) -> saturated!
    nav = _make_nav(surge=0.0)
    ref = _make_ref(u_d=20.0)

    # Step through 50 ticks (5 seconds)
    for tick in range(50):
        load, trace = ctrl.compute_control(nav, ref, dt_s=0.1, tick=tick)
        assert load.surge_n == pytest.approx(max_force)
        assert trace.saturation_flags[0] is True
        # Anti-windup correction must be negative (opposing windup)
        assert trace.antiwindup_correction[0] < 0.0

    # Under tracking anti-windup:
    # Equilibrium for integrator: Ki * e + Kaw * (achieved - raw) = 0
    # raw = P + I = 2000 + I. achieved = 1000.
    # 50 * 20 + 1.0 * (1000 - 2000 - I) = 0 => 1000 - 1000 - I = 0 => I_eq = 0!
    # Integral does NOT wind up to huge values!
    assert trace.i_term[0] == pytest.approx(0.0, abs=10.0)


def test_saturation_release_and_instant_integrator_recovery() -> None:
    """When error reverses, controller releases saturation and recovers immediately without latency."""
    max_force = 500.0
    config = MarinePIDConfig(
        kp=(100.0, 0.0, 0.0),
        ki=(20.0, 0.0, 0.0),
        kd=(0.0, 0.0, 0.0),
        antiwindup_gain=(1.0, 1.0, 1.0),
        min_output=(-max_force, -500.0, -500.0),
        max_output=(max_force, 500.0, 500.0),
    )
    ctrl = MarinePID(config)
    ctrl.reset()

    nav = _make_nav(surge=0.0)
    ref_pos = _make_ref(u_d=10.0)

    # Saturated for 20 ticks
    for tick in range(20):
        ctrl.compute_control(nav, ref_pos, dt_s=0.1, tick=tick)

    # Error reverses: target speed drops to -2.0 m/s
    ref_rev = _make_ref(u_d=-2.0)
    load, trace = ctrl.compute_control(nav, ref_rev, dt_s=0.1, tick=20)

    # Output immediately flips to negative force without remaining stuck at +max_force
    assert load.surge_n < 0.0
    assert trace.raw_request[0] < 0.0


# ---------------------------------------------------------------------------
# 7. Achieved Load Feedback Contract Tests
# ---------------------------------------------------------------------------


def test_achieved_load_explicit_feedback_and_missing_error() -> None:
    """Explicit feedback is used when available; missing feedback raises error if passthrough disabled (TS-20, VR-19)."""
    config = MarinePIDConfig(
        kp=(10.0, 0.0, 0.0),
        ki=(5.0, 0.0, 0.0),
        kd=(0.0, 0.0, 0.0),
        antiwindup_gain=(1.0, 1.0, 1.0),
        allow_ideal_passthrough=False,  # Require explicit achieved load
    )
    ctrl = MarinePID(config)
    ctrl.reset()

    nav = _make_nav(surge=0.0)
    ref = _make_ref(u_d=10.0)

    # Without achieved load -> raises RuntimeError
    with pytest.raises(RuntimeError, match="AchievedGeneralizedLoad feedback is unavailable"):
        ctrl.compute_control(nav, ref, dt_s=0.1, tick=0, achieved_load=None)

    # With explicit AchievedGeneralizedLoad -> succeeds
    achieved = AchievedGeneralizedLoad(
        surge_n=80.0,  # External actuator achieved only 80 N
        sway_n=0.0,
        yaw_nm=0.0,
        status=AchievedLoadStatus.AVAILABLE,
    )
    load, trace = ctrl.compute_control(nav, ref, dt_s=0.1, tick=0, achieved_load=achieved)
    assert trace.achieved_output == (80.0, 0.0, 0.0)


# ---------------------------------------------------------------------------
# 8. Reset, Snapshot, and Deterministic Restore Tests
# ---------------------------------------------------------------------------


def test_marine_pid_reset_is_idempotent() -> None:
    """Reset cleanly zeroes all integrators, filter states, and traces idempotently."""
    config = MarinePIDConfig(
        kp=(100.0, 100.0, 100.0),
        ki=(10.0, 10.0, 10.0),
        kd=(10.0, 10.0, 10.0),
    )
    ctrl = MarinePID(config)
    ctrl.reset()

    nav = _make_nav(surge=1.0)
    ref = _make_ref(u_d=5.0)

    for tick in range(10):
        ctrl.compute_control(nav, ref, dt_s=0.1, tick=tick)

    # Controller has non-zero internal state
    snap_before = ctrl.snapshot()
    assert any(abs(v) > 0.0 for v in snap_before.integral)

    # Reset
    ctrl.reset()
    snap_after = ctrl.snapshot()
    assert snap_after.integral == (0.0, 0.0, 0.0)
    assert snap_after.prev_measurement is None
    assert snap_after.filtered_derivative == (0.0, 0.0, 0.0)
    assert ctrl.latest_trace is None


def test_marine_pid_snapshot_restore_deterministic_replay() -> None:
    """Snapshot and restore produces exact identical output trace across branches (VR-06, VR-21)."""
    config = MarinePIDConfig(
        kp=(100.0, 50.0, 200.0),
        ki=(10.0, 5.0, 20.0),
        kd=(20.0, 10.0, 40.0),
        tau_d=(0.1, 0.1, 0.1),
        antiwindup_gain=(1.5, 1.5, 1.5),
        feedforward_gain=(0.5, 0.5, 0.5),
    )
    ctrl1 = MarinePID(config)
    ctrl1.reset()

    navs = [_make_nav(surge=1.0 + 0.1 * i, sway=0.05 * i, heading=0.02 * i) for i in range(10)]
    refs = [_make_ref(u_d=3.0, v_d=0.0, psi_d=0.3, ax_d=0.1) for _ in range(10)]

    # Advance ctrl1 5 steps
    for i in range(5):
        ctrl1.compute_control(navs[i], refs[i], dt_s=0.1, tick=i)

    # Snapshot at tick 5
    snapshot = ctrl1.snapshot()

    # Continue ctrl1 for steps 5..9
    traces1 = []
    for i in range(5, 10):
        _, trace = ctrl1.compute_control(navs[i], refs[i], dt_s=0.1, tick=i)
        traces1.append(trace)

    # Create second controller, restore snapshot, and run steps 5..9
    ctrl2 = MarinePID(config)
    ctrl2.restore(snapshot)
    traces2 = []
    for i in range(5, 10):
        _, trace = ctrl2.compute_control(navs[i], refs[i], dt_s=0.1, tick=i)
        traces2.append(trace)

    # Verify bit-for-bit identical traces
    for t1, t2 in zip(traces1, traces2, strict=True):
        assert t1.tick == t2.tick
        assert t1.raw_request == t2.raw_request
        assert t1.p_term == t2.p_term
        assert t1.i_term == t2.i_term
        assert t1.d_term == t2.d_term
        assert t1.saturated_output == t2.saturated_output


# ---------------------------------------------------------------------------
# 9. Fail-Closed Error Handling Tests
# ---------------------------------------------------------------------------


def test_marine_pid_fail_closed_on_invalid_inputs() -> None:
    """Invalid dt_s (<=0 or non-finite) or non-finite states fail closed (TS-17, VR-04)."""
    config = MarinePIDConfig(kp=(1.0, 1.0, 1.0), ki=(0.0, 0.0, 0.0), kd=(0.0, 0.0, 0.0))
    ctrl = MarinePID(config)
    ctrl.reset()

    nav = _make_nav(surge=1.0)
    ref = _make_ref(u_d=2.0)

    with pytest.raises(ValueError, match="dt_s must be positive"):
        ctrl.compute_control(nav, ref, dt_s=-0.1)

    with pytest.raises(ValueError, match="dt_s must be positive"):
        ctrl.compute_control(nav, ref, dt_s=0.0)

    with pytest.raises(ValueError, match="finite"):
        ctrl.compute_control(nav, ref, dt_s=float("nan"))


# ---------------------------------------------------------------------------
# 10. Position Mode (Body-Frame Pose Tracking)
# ---------------------------------------------------------------------------


def test_marine_pid_position_mode_body_frame_rotation() -> None:
    """In position_mode=True, errors are transformed from world NE to body frame (TS-03, TS-20)."""
    config = MarinePIDConfig(
        kp=(10.0, 10.0, 50.0),
        ki=(0.0, 0.0, 0.0),
        kd=(0.0, 0.0, 0.0),
        position_mode=True,
    )
    ctrl = MarinePID(config)
    ctrl.reset()

    # Ship at North=0, East=0, Heading = 90 deg (facing East)
    # Target at North=10, East=0 (to the port side of the ship, i.e., -10m sway)
    nav = _make_nav(north=0.0, east=0.0, heading=math.pi / 2.0)
    ref = _make_ref(north_d=10.0, east_d=0.0, psi_d=math.pi / 2.0)

    load, trace = ctrl.compute_control(nav, ref, dt_s=0.1, tick=0)

    # In body frame when facing East:
    # North is port side (-y in body FRD), so e_surge = 0, e_sway = -10
    assert trace.errors[0] == pytest.approx(0.0, abs=1e-6)
    assert trace.errors[1] == pytest.approx(-10.0, abs=1e-6)
    assert load.sway_n == pytest.approx(-100.0, abs=1e-6)


# ---------------------------------------------------------------------------
# 11. Stack Integration & Closed-Loop Tests
# ---------------------------------------------------------------------------


def test_modular_ship_stack_with_marine_pid_and_generic_3dof_plant() -> None:
    """Full ModularShipStack end-to-end simulation with MarinePID and Generic3DOFPlant."""
    plant_params = {
        "mass_kg": 1.6e7,
        "i_z_kgm2": 3.0e10,
        "x_g_m": 0.0,
        "x_dot_u_kg": -5.0e6,
        "y_dot_v_kg": -3.5e7,
        "n_dot_r_kgm2": -2.0e10,
        "y_dot_r_kgm": 1.0e6,
        "n_dot_v_kgm": 1.0e6,
        "d_u": 5.0e4,
        "d_uu": 2.0e5,
        "d_v": 3.0e5,
        "d_vv": 1.5e6,
        "d_r": 8.0e7,
        "d_rr": 2.5e9,
    }
    pid_params = {
        "kp": [2.0e6, 1.0e6, 5.0e9],
        "ki": [1.0e5, 5.0e4, 2.0e8],
        "kd": [5.0e6, 2.0e6, 1.0e10],
        "tau_d": [0.1, 0.1, 0.1],
        "antiwindup_gain": [1.0, 1.0, 1.0],
        "min_output": [-5.0e6, -2.0e6, -1.0e9],
        "max_output": [5.0e6, 2.0e6, 1.0e9],
        "feedforward_gain": [0.0, 0.0, 0.0],
        "allow_ideal_passthrough": True,
    }

    cfg = normalize_ship_modules(
        {
            "preset": "legacy_equivalent",
            "overrides": {"scheduler": {"plant_period_ticks": 1, "controller_period_ticks": 1}},
            "modules": {
                "plant": {"identity": "generic_3dof_plant", "parameters": plant_params},
                "guidance": {"identity": "pass_through_guidance", "parameters": {}},
                "controller": {"identity": "marine_pid", "parameters": pid_params},
            },
        }
    )

    stack = ModularShipStack.from_config(cfg, dt_s=0.1)
    init_nav = _make_nav(north=0.0, east=0.0, heading=0.0, surge=0.0, sway=0.0, yaw_rate=0.0)
    stack.reset(init_nav, seed=42)

    # Commanded surge velocity = 5.0 m/s, heading = 0.2 rad
    target_ref = np.zeros(9)
    target_ref[2] = 0.2
    target_ref[3] = 5.0

    # Step through 20 ticks (2.0 seconds)
    for tick in range(20):
        cmd = CommandInput.direct(tick, DirectReference(target_ref, tick))
        out = stack.step(cmd, dt_s=0.1)

        assert out.failure is None
        assert out.controller_trace is not None
        assert out.achieved_load is not None
        assert out.controller_trace.tick == tick
        assert out.achieved_load.surge_n == pytest.approx(out.controller_trace.saturated_output[0])

    # After 20 ticks, vessel has accelerated in surge and turned toward heading 0.2 rad
    final_nav = out.navigation
    assert final_nav.surge_mps > 0.0
    assert final_nav.heading_rad > 0.0


def test_modular_ship_stack_marine_pid_snapshot_restore_determinism() -> None:
    """Snapshot and restore on ModularShipStack with MarinePID produces bit-identical traces."""
    plant_params = {
        "mass_kg": 1.6e7,
        "i_z_kgm2": 3.0e10,
        "x_g_m": 0.0,
        "x_dot_u_kg": -5.0e6,
        "y_dot_v_kg": -3.5e7,
        "n_dot_r_kgm2": -2.0e10,
        "d_u": 5.0e4,
        "d_uu": 2.0e5,
        "d_v": 3.0e5,
        "d_vv": 1.5e6,
        "d_r": 8.0e7,
        "d_rr": 2.5e9,
    }
    pid_params = {
        "kp": [1.0e6, 5.0e5, 2.0e9],
        "ki": [5.0e4, 2.0e4, 1.0e8],
        "kd": [2.0e6, 1.0e6, 5.0e9],
        "tau_d": [0.1, 0.1, 0.1],
        "antiwindup_gain": [1.0, 1.0, 1.0],
        "min_output": [-3.0e6, -1.0e6, -5.0e8],
        "max_output": [3.0e6, 1.0e6, 5.0e8],
        "allow_ideal_passthrough": True,
    }

    cfg = normalize_ship_modules(
        {
            "preset": "legacy_equivalent",
            "overrides": {"scheduler": {"plant_period_ticks": 1, "controller_period_ticks": 1}},
            "modules": {
                "plant": {"identity": "generic_3dof_plant", "parameters": plant_params},
                "guidance": {"identity": "pass_through_guidance", "parameters": {}},
                "controller": {"identity": "marine_pid", "parameters": pid_params},
            },
        }
    )

    stack1 = ModularShipStack.from_config(cfg, dt_s=0.1)
    init_nav = _make_nav(surge=1.0)
    stack1.reset(init_nav, seed=99)

    target_ref = np.zeros(9)
    target_ref[2] = 0.1
    target_ref[3] = 4.0

    # Step 5 ticks on stack1
    for tick in range(5):
        stack1.step(CommandInput.direct(tick, DirectReference(target_ref, tick)), dt_s=0.1)

    snap = stack1.snapshot()

    # Step 5 more ticks on stack1
    out1_list = []
    for tick in range(5, 10):
        out = stack1.step(CommandInput.direct(tick, DirectReference(target_ref, tick)), dt_s=0.1)
        out1_list.append(out)

    # Restore snapshot to stack2 and step 5..9
    stack2 = ModularShipStack.from_config(cfg, dt_s=0.1)
    stack2.reset(init_nav, seed=99)
    stack2.restore(snap)

    out2_list = []
    for tick in range(5, 10):
        out = stack2.step(CommandInput.direct(tick, DirectReference(target_ref, tick)), dt_s=0.1)
        out2_list.append(out)

    # Compare exact state equality
    for o1, o2 in zip(out1_list, out2_list, strict=True):
        assert o1.tick == o2.tick
        np.testing.assert_array_equal(o1.navigation.as_array(), o2.navigation.as_array())
        np.testing.assert_array_equal(o1.plant.values, o2.plant.values)
        assert o1.controller_trace == o2.controller_trace
