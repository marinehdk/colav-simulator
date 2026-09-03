"""FCB45 pole-placement seed gains for the fcb45_marine_pid preset (Issue #67 slice 6).

Derivation (independent of the implementation, Fossen Handbook 2nd ed. Alg-15.1
logic lifted to moment scale with an explicit third pole):

- Yaw channel linearisation: I_eff = I_z + N_r_dot = 2.7e7 + 9.5e6 = 3.65e7
  kg.m^2 (the plant forms m_33 = i_z - n_dot_r with SNAME n_dot_r = -9.5e6),
  d_eff = d_r = 1.6e6 N.m.s (d_rr*|r| dropped in linearisation).
- Nomoto equivalents at moment scale: T = I_eff/d_eff = 22.8125 s, open-loop
  bandwidth 1/T = 0.0438 rad/s.
- Closed loop: zeta = 0.9, omega_n inside the mandated band
  [2/T/5, 2/T/3] = [0.01753, 0.02922] -> omega_n = 0.025 rad/s; third pole
  a = 3*omega_n (non-dominant).
- Matching (s^2 + 2*zeta*omega_n*s + omega_n^2)(s + a) against
  I_eff*s^3 + (d_eff + kd)*s^2 + kp*s + ki gives
  kd = I_eff*(2*zeta*omega_n + a) - d_eff,
  kp = I_eff*(omega_n^2 + 2*zeta*omega_n*a),
  ki = I_eff*omega_n^2*a.
- Ki ~ Kp/10 (Fossen thumb) would need omega_n >= 0.056 rad/s to pass Routh
  here (2*zeta*omega_n > 0.1), i.e. 64% of the open-loop bandwidth, outside the
  band; the placed ki (~kp/85) is therefore deliberately below that ceiling.
- Feedforward: Nomoto inverse tau_FF = I_eff*rdot_d + d_eff*r_d.
- Surge/sway: first-order plants, P+I pole placement at 0.08 / 0.15 rad/s with
  surge damping linearised at the 7.8 m/s service speed.
"""

from __future__ import annotations

import pytest

from colav_simulator.modular_gnc.catalog import list_stack_catalog

I_Z = 2.7e7
N_R_DOT = 9.5e6
I_EFF = I_Z + N_R_DOT
D_EFF = 1.6e6
T_NOMOTO = I_EFF / D_EFF
ZETA = 0.9
OMEGA_N = 0.025
THIRD_POLE = 3.0 * OMEGA_N

M_11 = 220000.0 + 22000.0  # m - X_u_dot
M_22 = 220000.0 + 160000.0  # m - Y_v_dot
D_U_AT_SERVICE = 3500.0 + 2.0 * 280.0 * 7.8  # linearised at 7.8 m/s
D_V = 50000.0

EXPECTED_KP_YAW = I_EFF * (OMEGA_N**2 + 2.0 * ZETA * OMEGA_N * THIRD_POLE)
EXPECTED_KI_YAW = I_EFF * OMEGA_N**2 * THIRD_POLE
EXPECTED_KD_YAW = I_EFF * (2.0 * ZETA * OMEGA_N + THIRD_POLE) - D_EFF

EXPECTED_KP_SURGE = M_11 * 0.08 - D_U_AT_SERVICE
EXPECTED_KI_SURGE = EXPECTED_KP_SURGE / 10.0
EXPECTED_KP_SWAY = M_22 * 0.15 - D_V
EXPECTED_KI_SWAY = EXPECTED_KP_SWAY / 10.0


def _preset_pid_params() -> dict:
    entry = None
    for candidate in list_stack_catalog()["stacks"]:
        if candidate["stack_id"] == "fcb45_3dof_plant+pass_through_guidance+fcb45_marine_pid":
            entry = candidate
            break
    assert entry is not None, "fcb45 tier1 stack must be listed"
    return entry["config"]["modules"]["controller"]["parameters"]


def test_omega_n_band_precondition() -> None:
    """The chosen closed-loop bandwidth sits in the mandated 2/T window."""
    assert 2.0 / T_NOMOTO / 5.0 <= OMEGA_N <= 2.0 / T_NOMOTO / 3.0


class TestFCB45YawSeedGains:
    def test_yaw_gains_match_pole_placement(self) -> None:
        params = _preset_pid_params()
        assert params["kp"][2] == pytest.approx(EXPECTED_KP_YAW, rel=1e-9)
        assert params["ki"][2] == pytest.approx(EXPECTED_KI_YAW, rel=1e-9)
        assert params["kd"][2] == pytest.approx(EXPECTED_KD_YAW, rel=1e-9)

    def test_integral_action_stays_below_the_kp_over_10_ceiling(self) -> None:
        params = _preset_pid_params()
        assert params["ki"][2] < params["kp"][2] / 10.0

    def test_nomoto_feedforward_gains_equal_effective_inertia_and_damping(self) -> None:
        params = _preset_pid_params()
        assert params["yaw_accel_ff_gain"] == pytest.approx(I_EFF, rel=1e-12)
        assert params["yaw_rate_ff_gain"] == pytest.approx(D_EFF, rel=1e-12)


class TestFCB45ShaperAndCapEnablement:
    def test_reference_shaper_enabled_with_workboat_limits(self) -> None:
        params = _preset_pid_params()
        assert params["reference_shaper_enable"] is True
        assert params["heading_rate_limit_rad_s"] == pytest.approx(0.05, rel=1e-12)
        assert params["heading_accel_limit_rad_s2"] == pytest.approx(0.02, rel=1e-12)

    def test_speed_adaptive_moment_cap_uses_vendor_mz_curve(self) -> None:
        params = _preset_pid_params()
        assert params["yaw_limit_base_nm"] == pytest.approx(3.6e5, rel=1e-12)
        assert params["yaw_limit_speed_coeff"] == pytest.approx(2500.0, rel=1e-12)
        assert params["yaw_limit_cap_nm"] == pytest.approx(9.6e5, rel=1e-12)


class TestFCB45SurgeSwaySeedGains:
    def test_surge_gains_match_first_order_pole_placement(self) -> None:
        params = _preset_pid_params()
        assert params["kp"][0] == pytest.approx(EXPECTED_KP_SURGE, rel=1e-6)
        assert params["ki"][0] == pytest.approx(EXPECTED_KI_SURGE, rel=1e-6)
        assert params["kd"][0] == 0.0

    def test_sway_gains_match_first_order_pole_placement(self) -> None:
        params = _preset_pid_params()
        assert params["kp"][1] == pytest.approx(EXPECTED_KP_SWAY, rel=1e-6)
        assert params["ki"][1] == pytest.approx(EXPECTED_KI_SWAY, rel=1e-6)
        assert params["kd"][1] == 0.0


class TestFCB45OutputLimits:
    def test_output_limits_match_vendor_actuation_envelopes(self) -> None:
        """Static output limits match the vendor actuation envelopes.

        Surge within 3x135 kN bollard, sway within 2x20 kN thrusters, yaw at
        the vendor Mz cap (the adaptive cap then tightens it with speed).
        """
        params = _preset_pid_params()
        assert params["min_output"][0] == -2.0e5
        assert params["max_output"][0] == 2.0e5
        assert params["min_output"][1] == -4.0e4
        assert params["max_output"][1] == 4.0e4
        assert params["min_output"][2] == -9.6e5
        assert params["max_output"][2] == 9.6e5
