"""Tests for generic 3DOF plant parameters, pure RHS, and physics invariants (Issue #52)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from colav_simulator.modular_gnc.contracts import (
    NavigationState,
    PlantState,
    VesselLoad,
)
from colav_simulator.modular_gnc.plant import (
    Generic3DOFPlant,
    Generic3DOFPlantParameters,
    GenericRoll4DOFPlant,
    GenericRoll4DOFPlantParameters,
)


@pytest.fixture
def valid_params() -> Generic3DOFPlantParameters:
    """Representative valid 3DOF vessel parameters."""
    return Generic3DOFPlantParameters(
        mass_kg=1.6e7,
        i_z_kgm2=3.0e10,
        x_g_m=0.0,
        x_dot_u_kg=-5.0e6,
        y_dot_v_kg=-3.5e7,
        n_dot_r_kgm2=-2.0e10,
        y_dot_r_kgm=1.0e6,
        n_dot_v_kgm=1.0e6,
        d_u=5.0e4,
        d_uu=2.0e5,
        d_v=3.0e5,
        d_vv=1.5e6,
        d_r=8.0e7,
        d_rr=2.5e9,
        d_vr=1.0e5,
        d_rv=1.0e5,
    )


@pytest.fixture
def valid_4dof_params() -> GenericRoll4DOFPlantParameters:
    """Representative valid restoring-dominated roll-4DOF vessel parameters."""
    return GenericRoll4DOFPlantParameters(
        mass_kg=1.6e7,
        i_x_kgm2=1.5e9,
        i_z_kgm2=3.0e10,
        x_g_m=0.0,
        z_g_m=0.0,
        x_dot_u_kg=-5.0e6,
        y_dot_v_kg=-3.5e7,
        k_dot_p_kgm2=-5.0e8,
        n_dot_r_kgm2=-2.0e10,
        y_dot_r_kgm=1.0e6,
        n_dot_v_kgm=1.0e6,
        y_dot_p_kgm=0.0,
        k_dot_v_kgm=0.0,
        k_dot_r_kgm2=0.0,
        n_dot_p_kgm2=0.0,
        d_u=5.0e4,
        d_uu=2.0e5,
        d_v=3.0e5,
        d_vv=1.5e6,
        d_p=2.0e7,
        d_pp=5.0e7,
        d_r=8.0e7,
        d_rr=2.5e9,
        d_vr=1.0e5,
        d_rv=1.0e5,
        d_vp=0.0,
        d_pv=0.0,
        d_pr=0.0,
        d_rp=0.0,
        restoring_k_phi=3.0e8,
    )


# ---------------------------------------------------------------------------
# 1. Parameter Validation & Invariants (TDD Seam 1)
# ---------------------------------------------------------------------------


def test_plant_parameters_validates_types_and_rejection_of_bools(valid_params: Generic3DOFPlantParameters) -> None:
    assert valid_params.mass_kg == 1.6e7
    assert valid_params.i_z_kgm2 == 3.0e10

    with pytest.raises(TypeError, match="must be a float, got bool"):
        Generic3DOFPlantParameters(
            mass_kg=True,  # type: ignore[arg-type]
            i_z_kgm2=3.0e10,
        )

    with pytest.raises(TypeError, match="must be a float, got bool"):
        Generic3DOFPlantParameters(
            mass_kg=1.6e7,
            i_z_kgm2=False,  # type: ignore[arg-type]
        )


def test_plant_parameters_rejects_nonfinite_and_negative_mass() -> None:
    with pytest.raises(ValueError, match="mass_kg must be positive"):
        Generic3DOFPlantParameters(mass_kg=0.0, i_z_kgm2=1.0e9)

    with pytest.raises(ValueError, match="mass_kg must be positive"):
        Generic3DOFPlantParameters(mass_kg=-100.0, i_z_kgm2=1.0e9)

    with pytest.raises(ValueError, match="i_z_kgm2 must be positive"):
        Generic3DOFPlantParameters(mass_kg=1.0e6, i_z_kgm2=-1.0)

    with pytest.raises(ValueError, match="must be finite"):
        Generic3DOFPlantParameters(mass_kg=float("nan"), i_z_kgm2=1.0e9)

    with pytest.raises(ValueError, match="must be finite"):
        Generic3DOFPlantParameters(mass_kg=1.0e6, i_z_kgm2=float("inf"))


def test_plant_parameters_rejects_asymmetric_mass_matrix() -> None:
    # m_23 = m*x_g - Y_dot_r, m_32 = m*x_g - N_dot_v
    # If Y_dot_r != N_dot_v with x_g=0, matrix is asymmetric
    with pytest.raises(ValueError, match="mass matrix symmetry"):
        Generic3DOFPlantParameters(
            mass_kg=1.6e7,
            i_z_kgm2=3.0e10,
            x_g_m=0.0,
            y_dot_r_kgm=1.0e6,
            n_dot_v_kgm=2.0e6,  # Asymmetric!
        )


def test_plant_parameters_rejects_non_spd_mass_matrix() -> None:
    # If added mass makes effective mass <= 0
    with pytest.raises(ValueError, match="mass matrix positive definite"):
        Generic3DOFPlantParameters(
            mass_kg=100.0,
            i_z_kgm2=1000.0,
            x_dot_u_kg=200.0,  # m - X_dot_u = 100 - 200 = -100 <= 0
        )


def test_plant_parameters_rejects_non_dissipative_damping() -> None:
    # Negative drag coefficient violates energy dissipativity
    with pytest.raises(ValueError, match="damping"):
        Generic3DOFPlantParameters(
            mass_kg=1.6e7,
            i_z_kgm2=3.0e10,
            d_u=-1000.0,
        )

    with pytest.raises(ValueError, match="damping"):
        Generic3DOFPlantParameters(
            mass_kg=1.6e7,
            i_z_kgm2=3.0e10,
            d_uu=-500.0,
        )

    # Strongly non-dissipative coupled linear cross-terms: d_v * d_r < ((d_vr + d_rv)/2)^2
    with pytest.raises(ValueError, match="damping"):
        Generic3DOFPlantParameters(
            mass_kg=1.6e7,
            i_z_kgm2=3.0e10,
            d_v=1.0,
            d_r=1.0,
            d_vr=1.0e6,
            d_rv=1.0e6,
        )


# ---------------------------------------------------------------------------
# 2. Pure RHS & Equilibrium (TDD Seam 2)
# ---------------------------------------------------------------------------


def test_plant_pure_rhs_equilibrium(valid_params: Generic3DOFPlantParameters) -> None:
    plant = Generic3DOFPlant(valid_params)
    state = np.zeros(6, dtype=np.float64)
    ctrl = VesselLoad.zero()
    env = VesselLoad.zero()

    deriv = plant.rhs(time_s=0.0, state=state, control_load=ctrl, env_load=env)

    assert isinstance(deriv, np.ndarray)
    assert deriv.shape == (6,)
    assert deriv.dtype == np.float64
    np.testing.assert_allclose(deriv, np.zeros(6), atol=1e-12)


def test_plant_pure_rhs_kinematics(valid_params: Generic3DOFPlantParameters) -> None:
    plant = Generic3DOFPlant(valid_params)
    ctrl = VesselLoad.zero()
    env = VesselLoad.zero()

    # Heading North (psi=0), forward surge u=3.0
    state_north = np.array([10.0, 20.0, 0.0, 3.0, 0.0, 0.0])
    deriv_north = plant.rhs(0.0, state_north, ctrl, env)
    assert math.isclose(deriv_north[0], 3.0, abs_tol=1e-12)  # dN/dt = 3.0
    assert math.isclose(deriv_north[1], 0.0, abs_tol=1e-12)  # dE/dt = 0.0
    assert math.isclose(deriv_north[2], 0.0, abs_tol=1e-12)  # dpsi/dt = 0.0

    # Heading East (psi = pi/2), forward surge u=3.0
    state_east = np.array([10.0, 20.0, math.pi / 2.0, 3.0, 0.0, 0.0])
    deriv_east = plant.rhs(0.0, state_east, ctrl, env)
    assert math.isclose(deriv_east[0], 0.0, abs_tol=1e-12)  # dN/dt = 0.0
    assert math.isclose(deriv_east[1], 3.0, abs_tol=1e-12)  # dE/dt = 3.0
    assert math.isclose(deriv_east[2], 0.0, abs_tol=1e-12)  # dpsi/dt = 0.0

    # Heading North (psi=0), starboard sway v=2.0
    state_sway = np.array([10.0, 20.0, 0.0, 0.0, 2.0, 0.0])
    deriv_sway = plant.rhs(0.0, state_sway, ctrl, env)
    assert math.isclose(deriv_sway[0], 0.0, abs_tol=1e-12)  # dN/dt = 0.0
    assert math.isclose(deriv_sway[1], 2.0, abs_tol=1e-12)  # dE/dt = 2.0 (starboard is East)

    # Heading North, yaw rate r=0.1 rad/s
    state_yaw = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.1])
    deriv_yaw = plant.rhs(0.0, state_yaw, ctrl, env)
    assert math.isclose(deriv_yaw[2], 0.1, abs_tol=1e-12)


def test_plant_pure_rhs_dynamics_decomposition(valid_params: Generic3DOFPlantParameters) -> None:
    plant = Generic3DOFPlant(valid_params)
    M = plant.mass_matrix
    state = np.array([0.0, 0.0, 0.5, 2.0, 0.3, -0.05])
    nu = state[3:6]
    ctrl = VesselLoad(surge_n=1.0e5, sway_n=-2.0e4, yaw_nm=5.0e5)
    env = VesselLoad(surge_n=1.0e4, sway_n=5.0e3, yaw_nm=-1.0e4)

    deriv = plant.rhs(0.0, state, ctrl, env)
    nu_dot = deriv[3:6]

    # M * nu_dot must equal tau_ctrl + tau_env - C(nu)*nu - D(nu)*nu - g(eta)
    tau_total = np.array([ctrl.surge_n + env.surge_n, ctrl.sway_n + env.sway_n, ctrl.yaw_nm + env.yaw_nm])
    C_mat = plant.coriolis_matrix(nu)
    D_vec = plant.damping_force(nu)
    g_vec = plant.restoring_force(state[0:3])

    expected_accel = np.linalg.solve(M, tau_total - C_mat @ nu - D_vec - g_vec)
    np.testing.assert_allclose(nu_dot, expected_accel, rtol=1e-12, atol=1e-12)


# ---------------------------------------------------------------------------
# 3. Physics Invariants: Coriolis Power Neutrality, Damping Dissipativity, Mirror Parity (TDD Seam 3)
# ---------------------------------------------------------------------------


def test_plant_coriolis_power_neutrality(valid_params: Generic3DOFPlantParameters) -> None:
    plant = Generic3DOFPlant(valid_params)
    rng = np.random.default_rng(20260901)

    for _ in range(50):
        nu = rng.uniform(-10.0, 10.0, size=3)
        C = plant.coriolis_matrix(nu)

        # Skew-symmetry: C + C.T == 0
        np.testing.assert_allclose(C + C.T, np.zeros((3, 3)), atol=1e-14)

        # Power neutrality: nu.T @ C @ nu ≈ 0 (relative to magnitude of C and nu)
        power = float(nu @ C @ nu)
        scale = max(1.0, float(np.linalg.norm(nu) ** 2 * np.linalg.norm(C)))
        assert abs(power) / scale < 1e-14
        assert abs(power) < 1e-5


def test_plant_damping_dissipativity(valid_params: Generic3DOFPlantParameters) -> None:
    plant = Generic3DOFPlant(valid_params)
    rng = np.random.default_rng(20260901)

    for _ in range(50):
        nu = rng.uniform(-5.0, 5.0, size=3)
        d_vec = plant.damping_force(nu)

        # Dissipativity: nu.T @ D(nu) >= 0
        power_dissipated = float(nu @ d_vec)
        assert power_dissipated >= 0.0


def test_plant_port_starboard_mirror_invariance(valid_params: Generic3DOFPlantParameters) -> None:
    plant = Generic3DOFPlant(valid_params)
    state = np.array([10.0, 20.0, 0.2, 4.0, 0.5, 0.02])
    state_mirror = np.array([10.0, 20.0, -0.2, 4.0, -0.5, -0.02])

    ctrl = VesselLoad(surge_n=5.0e4, sway_n=1.0e4, yaw_nm=2.0e5)
    ctrl_mirror = VesselLoad(surge_n=5.0e4, sway_n=-1.0e4, yaw_nm=-2.0e5)

    deriv = plant.rhs(0.0, state, ctrl, VesselLoad.zero())
    deriv_mirror = plant.rhs(0.0, state_mirror, ctrl_mirror, VesselLoad.zero())

    # Surge accel unchanged
    assert math.isclose(deriv[3], deriv_mirror[3], rel_tol=1e-10)
    # Sway accel negated
    assert math.isclose(deriv[4], -deriv_mirror[4], rel_tol=1e-10)
    # Yaw accel negated
    assert math.isclose(deriv[5], -deriv_mirror[5], rel_tol=1e-10)


def test_plant_pure_rhs_does_not_mutate_or_clip(valid_params: Generic3DOFPlantParameters) -> None:
    plant = Generic3DOFPlant(valid_params)
    state = np.array([1.0, 2.0, 0.3, 20.0, 10.0, 1.5])  # High speeds
    state_copy = state.copy()
    ctrl = VesselLoad(surge_n=1e8, sway_n=1e8, yaw_nm=1e9)

    deriv1 = plant.rhs(0.0, state, ctrl)
    deriv2 = plant.rhs(0.0, state, ctrl)

    np.testing.assert_array_equal(state, state_copy)
    np.testing.assert_array_equal(deriv1, deriv2)
    # No clipping: acceleration is proportional to massive force
    assert deriv1[3] > 1.0


def test_plant_pure_rhs_rejects_nonfinite_inputs(valid_params: Generic3DOFPlantParameters) -> None:
    plant = Generic3DOFPlant(valid_params)
    good_ctrl = VesselLoad.zero()

    # NaN in state
    bad_state = np.array([0.0, np.nan, 0.0, 0.0, 0.0, 0.0])
    with pytest.raises(ValueError, match="finite"):
        plant.rhs(0.0, bad_state, good_ctrl)

    # Inf in state
    bad_state_inf = np.array([0.0, 0.0, 0.0, float("inf"), 0.0, 0.0])
    with pytest.raises(ValueError, match="finite"):
        plant.rhs(0.0, bad_state_inf, good_ctrl)

    # Wrong state shape
    with pytest.raises(ValueError, match="shape"):
        plant.rhs(0.0, np.zeros(5), good_ctrl)

    # Accepts PlantState object
    ps = PlantState(values=np.zeros(6), capabilities=frozenset({"PLANAR_3DOF"}))
    deriv_ps = plant.rhs(0.0, ps, good_ctrl)
    assert deriv_ps.shape == (6,)


# ---------------------------------------------------------------------------
# 4. Generic Roll-4DOF Plant Parameters & Physics Invariants (Issue #53)
# ---------------------------------------------------------------------------


def test_roll_4dof_parameters_validates_types_and_rejection_of_bools(
    valid_4dof_params: GenericRoll4DOFPlantParameters,
) -> None:
    assert valid_4dof_params.mass_kg == 1.6e7
    assert valid_4dof_params.i_x_kgm2 == 1.5e9
    assert valid_4dof_params.i_z_kgm2 == 3.0e10
    assert valid_4dof_params.restoring_k_phi == 3.0e8

    with pytest.raises(TypeError, match="must be a float, got bool"):
        GenericRoll4DOFPlantParameters(
            mass_kg=True,  # type: ignore[arg-type]
            i_x_kgm2=1.5e9,
            i_z_kgm2=3.0e10,
        )

    with pytest.raises(TypeError, match="must be a float, got bool"):
        GenericRoll4DOFPlantParameters(
            mass_kg=1.6e7,
            i_x_kgm2=False,  # type: ignore[arg-type]
            i_z_kgm2=3.0e10,
        )


def test_roll_4dof_parameters_rejects_nonfinite_and_negative_inertia() -> None:
    with pytest.raises(ValueError, match="i_x_kgm2 must be positive"):
        GenericRoll4DOFPlantParameters(mass_kg=1.6e7, i_x_kgm2=0.0, i_z_kgm2=3.0e10)

    with pytest.raises(ValueError, match="i_x_kgm2 must be positive"):
        GenericRoll4DOFPlantParameters(mass_kg=1.6e7, i_x_kgm2=-1e6, i_z_kgm2=3.0e10)

    with pytest.raises(ValueError, match="must be finite"):
        GenericRoll4DOFPlantParameters(mass_kg=1.6e7, i_x_kgm2=float("nan"), i_z_kgm2=3.0e10)

    with pytest.raises(ValueError, match="restoring_k_phi must be non-negative"):
        GenericRoll4DOFPlantParameters(mass_kg=1.6e7, i_x_kgm2=1.5e9, i_z_kgm2=3.0e10, restoring_k_phi=-100.0)


def test_roll_4dof_parameters_rejects_asymmetric_mass_matrix() -> None:
    # m_23 = -m*z_g - Y_dot_p, m_32 = -m*z_g - K_dot_v
    with pytest.raises(ValueError, match="mass matrix symmetry"):
        GenericRoll4DOFPlantParameters(
            mass_kg=1.6e7,
            i_x_kgm2=1.5e9,
            i_z_kgm2=3.0e10,
            y_dot_p_kgm=1.0e5,
            k_dot_v_kgm=5.0e5,  # Asymmetric!
        )


def test_roll_4dof_parameters_rejects_non_spd_mass_matrix() -> None:
    # If added mass makes effective roll inertia <= 0
    with pytest.raises(ValueError, match="mass matrix positive definite"):
        GenericRoll4DOFPlantParameters(
            mass_kg=100.0,
            i_x_kgm2=100.0,
            i_z_kgm2=1000.0,
            k_dot_p_kgm2=200.0,  # I_x - K_dot_p = 100 - 200 = -100 <= 0
        )


def test_roll_4dof_parameters_rejects_non_dissipative_damping() -> None:
    # Negative roll damping violates energy dissipativity
    with pytest.raises(ValueError, match="damping"):
        GenericRoll4DOFPlantParameters(
            mass_kg=1.6e7,
            i_x_kgm2=1.5e9,
            i_z_kgm2=3.0e10,
            d_p=-1000.0,
        )

    with pytest.raises(ValueError, match="damping"):
        GenericRoll4DOFPlantParameters(
            mass_kg=1.6e7,
            i_x_kgm2=1.5e9,
            i_z_kgm2=3.0e10,
            d_pp=-500.0,
        )


# ---------------------------------------------------------------------------
# 5. Generic Roll-4DOF Pure RHS, Kinematics & Restoring Stability (Issue #53)
# ---------------------------------------------------------------------------


def test_roll_4dof_pure_rhs_equilibrium(valid_4dof_params: GenericRoll4DOFPlantParameters) -> None:
    plant = GenericRoll4DOFPlant(valid_4dof_params)
    state = np.zeros(8, dtype=np.float64)
    ctrl = VesselLoad.zero()
    env = VesselLoad.zero()

    deriv = plant.rhs(time_s=0.0, state=state, control_load=ctrl, env_load=env)

    assert isinstance(deriv, np.ndarray)
    assert deriv.shape == (8,)
    assert deriv.dtype == np.float64
    np.testing.assert_allclose(deriv, np.zeros(8), atol=1e-12)


def test_roll_4dof_pure_rhs_kinematics(valid_4dof_params: GenericRoll4DOFPlantParameters) -> None:
    plant = GenericRoll4DOFPlant(valid_4dof_params)
    ctrl = VesselLoad.zero()
    env = VesselLoad.zero()

    # Roll rate p=0.05 rad/s: dphi/dt = p = 0.05
    state_roll = np.array([0.0, 0.0, 0.0, 0.1, 0.0, 0.0, 0.05, 0.0])
    deriv_roll = plant.rhs(0.0, state_roll, ctrl, env)
    assert math.isclose(deriv_roll[3], 0.05, abs_tol=1e-12)  # dphi/dt = p
    assert math.isclose(deriv_roll[2], 0.0, abs_tol=1e-12)  # dpsi/dt = 0.0

    # Heading North (psi=0), forward surge u=4.0
    state_surge = np.array([10.0, 20.0, 0.0, 0.0, 4.0, 0.0, 0.0, 0.0])
    deriv_surge = plant.rhs(0.0, state_surge, ctrl, env)
    assert math.isclose(deriv_surge[0], 4.0, abs_tol=1e-12)  # dN/dt = 4.0
    assert math.isclose(deriv_surge[1], 0.0, abs_tol=1e-12)  # dE/dt = 0.0


def test_roll_4dof_restoring_dominated_stability_and_equilibrium(
    valid_4dof_params: GenericRoll4DOFPlantParameters,
) -> None:
    plant = GenericRoll4DOFPlant(valid_4dof_params)
    M = plant.mass_matrix
    m_33 = M[2, 2]  # I_x - K_dot_p = 1.5e9 - (-5e8) = 2.0e9 kg*m^2
    k_phi = valid_4dof_params.restoring_k_phi  # 3.0e8 N*m/rad

    # Perturbed roll angle phi = 0.1 rad (~5.7 deg), zero velocities
    state_pert = np.array([0.0, 0.0, 0.0, 0.1, 0.0, 0.0, 0.0, 0.0])
    deriv_pert = plant.rhs(0.0, state_pert, VesselLoad.zero(), VesselLoad.zero())

    # Restoring moment = -k_phi * phi = -3.0e8 * 0.1 = -3.0e7 N*m
    # Acceleration p_dot = -3.0e7 / 2.0e9 = -0.015 rad/s^2 (restores towards 0)
    p_dot = deriv_pert[6]
    expected_p_dot = -k_phi * 0.1 / m_33
    assert math.isclose(p_dot, expected_p_dot, rel_tol=1e-6)
    assert p_dot < 0.0  # Stable negative feedback restoring towards zero

    # Natural frequency: omega_n = sqrt(k_phi / m_33)
    omega_n = math.sqrt(k_phi / m_33)
    assert math.isclose(omega_n, math.sqrt(3.0e8 / 2.0e9), rel_tol=1e-6)


def test_roll_4dof_unactuated_roll_actuator_channel(valid_4dof_params: GenericRoll4DOFPlantParameters) -> None:
    """Prove control actuator input has strictly NO roll moment channel (RA-12)."""
    plant = GenericRoll4DOFPlant(valid_4dof_params)
    state = np.zeros(8, dtype=np.float64)

    # Control input providing surge, sway, yaw, and an attempted roll moment
    ctrl_attempt = VesselLoad(surge_n=1e5, sway_n=2e4, yaw_nm=5e5, roll_nm=1e7)
    ctrl_zero_roll = VesselLoad(surge_n=1e5, sway_n=2e4, yaw_nm=5e5, roll_nm=0.0)

    deriv1 = plant.rhs(0.0, state, ctrl_attempt)
    deriv2 = plant.rhs(0.0, state, ctrl_zero_roll)

    # Roll acceleration p_dot (deriv[6]) must be identical (roll is unactuated by control)
    np.testing.assert_array_equal(deriv1, deriv2)
    assert deriv1[6] == 0.0


def test_roll_4dof_environmental_roll_moment_affects_dynamics(
    valid_4dof_params: GenericRoll4DOFPlantParameters,
) -> None:
    """Prove environmental physical roll moment does actuate roll dynamics (TS-05)."""
    plant = GenericRoll4DOFPlant(valid_4dof_params)
    state = np.zeros(8, dtype=np.float64)
    ctrl = VesselLoad.zero()

    # Environmental load with roll moment (e.g. beam wind or wave roll moment)
    env_with_roll = VesselLoad(surge_n=0.0, sway_n=0.0, yaw_nm=0.0, roll_nm=4.0e6)
    deriv = plant.rhs(0.0, state, ctrl, env_with_roll)

    # Environmental roll moment produces positive roll acceleration
    p_dot = deriv[6]
    m_33 = plant.mass_matrix[2, 2]
    expected_p_dot = 4.0e6 / m_33
    assert math.isclose(p_dot, expected_p_dot, rel_tol=1e-6)
    assert p_dot > 0.0


def test_roll_4dof_coriolis_power_neutrality(valid_4dof_params: GenericRoll4DOFPlantParameters) -> None:
    plant = GenericRoll4DOFPlant(valid_4dof_params)
    rng = np.random.default_rng(20260901)

    for _ in range(50):
        nu = rng.uniform(-10.0, 10.0, size=4)
        C = plant.coriolis_matrix(nu)

        # Skew-symmetry: C + C.T == 0
        np.testing.assert_allclose(C + C.T, np.zeros((4, 4)), atol=1e-14)

        # Power neutrality: nu.T @ C @ nu == 0
        power = float(nu @ C @ nu)
        scale = max(1.0, float(np.linalg.norm(nu) ** 2 * np.linalg.norm(C)))
        assert abs(power) / scale < 1e-14


def test_roll_4dof_damping_dissipativity(valid_4dof_params: GenericRoll4DOFPlantParameters) -> None:
    plant = GenericRoll4DOFPlant(valid_4dof_params)
    rng = np.random.default_rng(20260901)

    for _ in range(50):
        nu = rng.uniform(-5.0, 5.0, size=4)
        d_vec = plant.damping_force(nu)

        # Dissipativity: nu.T @ D(nu) >= 0
        power_dissipated = float(nu @ d_vec)
        assert power_dissipated >= 0.0


def test_roll_4dof_port_starboard_mirror_invariance(valid_4dof_params: GenericRoll4DOFPlantParameters) -> None:
    plant = GenericRoll4DOFPlant(valid_4dof_params)
    # State: [N, E, psi, phi, u, v, p, r]
    state = np.array([10.0, 20.0, 0.2, 0.05, 4.0, 0.5, 0.01, 0.02])
    state_mirror = np.array([10.0, 20.0, -0.2, -0.05, 4.0, -0.5, -0.01, -0.02])

    ctrl = VesselLoad(surge_n=5.0e4, sway_n=1.0e4, yaw_nm=2.0e5)
    ctrl_mirror = VesselLoad(surge_n=5.0e4, sway_n=-1.0e4, yaw_nm=-2.0e5)

    deriv = plant.rhs(0.0, state, ctrl, VesselLoad.zero())
    deriv_mirror = plant.rhs(0.0, state_mirror, ctrl_mirror, VesselLoad.zero())

    # Surge accel unchanged
    assert math.isclose(deriv[4], deriv_mirror[4], rel_tol=1e-10)
    # Sway accel negated
    assert math.isclose(deriv[5], -deriv_mirror[5], rel_tol=1e-10)
    # Roll accel negated
    assert math.isclose(deriv[6], -deriv_mirror[6], rel_tol=1e-10)
    # Yaw accel negated
    assert math.isclose(deriv[7], -deriv_mirror[7], rel_tol=1e-10)


def test_roll_4dof_pure_rhs_rejects_nonfinite_inputs(valid_4dof_params: GenericRoll4DOFPlantParameters) -> None:
    plant = GenericRoll4DOFPlant(valid_4dof_params)
    good_ctrl = VesselLoad.zero()

    # NaN in state
    bad_state = np.array([0.0, np.nan, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    with pytest.raises(ValueError, match="finite"):
        plant.rhs(0.0, bad_state, good_ctrl)

    # Wrong shape
    with pytest.raises(ValueError, match="shape"):
        plant.rhs(0.0, np.zeros(6), good_ctrl)

    # Accepts PlantState object
    ps = PlantState(values=np.zeros(8), capabilities=frozenset({"ROLL_4DOF"}))
    deriv_ps = plant.rhs(0.0, ps, good_ctrl)
    assert deriv_ps.shape == (8,)


def test_roll_4dof_plant_state_diagnostics_and_navigation_projection() -> None:
    """Verify full roll-4DOF truth state in PlantState and 3DOF NavigationState projection."""
    # 8-element state: [N=10, E=20, psi=0.5, phi=0.08, u=3.0, v=0.2, p=0.01, r=0.04]
    values = np.array([10.0, 20.0, 0.5, 0.08, 3.0, 0.2, 0.01, 0.04])
    ps = PlantState(values=values, capabilities=frozenset({"ROLL_4DOF", "GENERALIZED_FORCE"}))

    # Diagnostics accessors preserve full 4DOF state
    assert ps.north_m == 10.0
    assert ps.east_m == 20.0
    assert ps.heading_rad == 0.5
    assert ps.roll_rad == 0.08
    assert ps.surge_mps == 3.0
    assert ps.sway_mps == 0.2
    assert ps.roll_rate_radps == 0.01
    assert ps.yaw_rate_radps == 0.04

    # NavigationState projection is strictly 3DOF (6 elements: N, E, heading, u, v, r)
    nav = ps.to_navigation_state()
    assert isinstance(nav, NavigationState)
    assert nav.north_m == 10.0
    assert nav.east_m == 20.0
    assert nav.heading_rad == 0.5
    assert nav.surge_mps == 3.0
    assert nav.sway_mps == 0.2
    assert nav.yaw_rate_radps == 0.04
    # Ensure no roll angle or roll rate in navigation schema
    assert not hasattr(nav, "roll_rad")
    assert not hasattr(nav, "roll_rate_radps")
    assert nav.as_array().shape == (6,)
