"""Pure generic 3DOF vessel maneuvering plant and physics contracts (VR-08, VR-11, VR-12, TS-01..06, TS-13)."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from colav_simulator.modular_gnc.contracts import (
    FloatArray,
    PlantInputSemantics,
    PlantState,
    VesselLoad,
    _finite_scalar,
)


@dataclass(frozen=True)
class Generic3DOFPlantParameters:
    """Immutable, typed hydrodynamic parameters for generic 3DOF maneuvering plant (SI units).

    Dynamics decomposition:
        M ν_dot = τ_control + τ_environment - C(ν)ν - D(ν)ν - g(η)

    All fields are strictly validated:
    - Mass and moment of inertia must be strictly positive.
    - Added mass and damping coefficients are strictly finite.
    - Mass matrix M is verified symmetric and positive definite (SPD).
    - Damping is verified energy-dissipative (νᵀ D(ν)ν >= 0).
    """

    mass_kg: float
    i_z_kgm2: float
    x_g_m: float = 0.0
    x_dot_u_kg: float = 0.0
    y_dot_v_kg: float = 0.0
    n_dot_r_kgm2: float = 0.0
    y_dot_r_kgm: float = 0.0
    n_dot_v_kgm: float = 0.0
    d_u: float = 0.0
    d_uu: float = 0.0
    d_v: float = 0.0
    d_vv: float = 0.0
    d_r: float = 0.0
    d_rr: float = 0.0
    d_vr: float = 0.0
    d_rv: float = 0.0
    restoring_k_n: float = 0.0
    restoring_k_e: float = 0.0
    restoring_k_psi: float = 0.0
    mass_symmetry_tolerance: float = 1e-6
    min_mass_eigenvalue: float = 1e-4
    damping_tolerance: float = 1e-9

    def __post_init__(self) -> None:
        """Validate parameter types, ranges, mass SPD, and damping dissipativity."""
        # 1. Strict positive scalars
        m = _finite_scalar("mass_kg", self.mass_kg)
        if m <= 0.0:
            raise ValueError(f"mass_kg must be positive, got {m}")
        object.__setattr__(self, "mass_kg", m)

        iz = _finite_scalar("i_z_kgm2", self.i_z_kgm2)
        if iz <= 0.0:
            raise ValueError(f"i_z_kgm2 must be positive, got {iz}")
        object.__setattr__(self, "i_z_kgm2", iz)

        # 2. Strict finite scalars for remaining fields
        scalar_fields = (
            "x_g_m",
            "x_dot_u_kg",
            "y_dot_v_kg",
            "n_dot_r_kgm2",
            "y_dot_r_kgm",
            "n_dot_v_kgm",
            "d_u",
            "d_uu",
            "d_v",
            "d_vv",
            "d_r",
            "d_rr",
            "d_vr",
            "d_rv",
            "restoring_k_n",
            "restoring_k_e",
            "restoring_k_psi",
            "mass_symmetry_tolerance",
            "min_mass_eigenvalue",
            "damping_tolerance",
        )
        for name in scalar_fields:
            val = _finite_scalar(name, getattr(self, name))
            object.__setattr__(self, name, val)

        # 3. Damping non-negativity for self terms
        for d_name in ("d_u", "d_uu", "d_v", "d_vv", "d_r", "d_rr"):
            d_val = getattr(self, d_name)
            if d_val < -self.damping_tolerance:
                raise ValueError(f"damping parameter {d_name} must be non-negative, got {d_val}")

        # 4. Construct and validate Mass Matrix M (3x3)
        # M = M_RB + M_A
        # m_11 = m - X_dot_u
        # m_22 = m - Y_dot_v
        # m_33 = I_z - N_dot_r
        # m_23 = m * x_g - Y_dot_r
        # m_32 = m * x_g - N_dot_v
        m_11 = m - self.x_dot_u_kg
        m_22 = m - self.y_dot_v_kg
        m_33 = iz - self.n_dot_r_kgm2
        m_23 = m * self.x_g_m - self.y_dot_r_kgm
        m_32 = m * self.x_g_m - self.n_dot_v_kgm

        # Symmetry check
        sym_error = abs(m_23 - m_32)
        if sym_error > self.mass_symmetry_tolerance:
            raise ValueError(
                f"mass matrix symmetry contract failed: |m_23 - m_32| = {sym_error:.6e} > "
                f"tolerance {self.mass_symmetry_tolerance:.6e}"
            )

        # Symmetric matrix for eigenvalue check
        m_mat = np.array(
            [
                [m_11, 0.0, 0.0],
                [0.0, m_22, 0.5 * (m_23 + m_32)],
                [0.0, 0.5 * (m_23 + m_32), m_33],
            ],
            dtype=np.float64,
        )
        eigenvalues = np.linalg.eigvalsh(m_mat)
        min_eig = float(eigenvalues.min())
        if min_eig <= self.min_mass_eigenvalue:
            raise ValueError(
                f"mass matrix positive definite contract failed: min eigenvalue {min_eig:.6e} <= "
                f"tolerance {self.min_mass_eigenvalue:.6e}"
            )

        # 5. Validate Damping Dissipativity
        # Linear part: [d_v, (d_vr + d_rv)/2; (d_vr + d_rv)/2, d_r] must be PSD
        sym_cross = 0.5 * (self.d_vr + self.d_rv)
        d_coupled = np.array(
            [[self.d_v, sym_cross], [sym_cross, self.d_r]],
            dtype=np.float64,
        )
        d_eigs = np.linalg.eigvalsh(d_coupled)
        if d_eigs.min() < -self.damping_tolerance:
            raise ValueError(
                f"damping linear coupled part is not dissipative: min eigenvalue {d_eigs.min():.6e} < "
                f"-{self.damping_tolerance:.6e}"
            )


def _extract_state_vector(state: PlantState | FloatArray | tuple[float, ...]) -> FloatArray:
    """Extract and strictly validate 6-element plant state vector."""
    if isinstance(state, PlantState):
        x = state.values
    else:
        x = np.asarray(state, dtype=np.float64)
    if x.shape != (6,):
        raise ValueError(f"state must have shape (6,), got {x.shape}")
    if not np.isfinite(x).all():
        raise ValueError(f"state contains non-finite values: {x}")
    return x


def _extract_3dof_load(
    load: VesselLoad | FloatArray | tuple[float, ...] | None,
    name: str,
) -> FloatArray:
    """Extract and strictly validate 3-element generalized load vector."""
    if load is None:
        return np.zeros(3, dtype=np.float64)
    if isinstance(load, VesselLoad):
        return np.array([load.surge_n, load.sway_n, load.yaw_nm], dtype=np.float64)
    arr = np.asarray(load, dtype=np.float64)
    if arr.shape != (3,):
        raise ValueError(f"{name} must have shape (3,), got {arr.shape}")
    if not np.isfinite(arr).all():
        raise ValueError(f"{name} contains non-finite values: {arr}")
    return arr


class Generic3DOFPlant:
    """Generic 3DOF vessel maneuvering plant exposing pure RHS derivative (VR-08, VR-11, VR-12).

    Kinematics:
        dN/dt = u*cos(psi) - v*sin(psi)
        dE/dt = u*sin(psi) + v*cos(psi)
        dpsi/dt = r

    Dynamics:
        M ν_dot = τ_ctrl + τ_env - C(ν)ν - D(ν)ν - g(η)

    Guarantees:
    - Pure RHS with zero internal state mutation.
    - Never internally integrates, clips, or silently repairs NaN.
    - Coriolis power neutrality: νᵀ C(ν)ν = 0.
    - Energy dissipativity: νᵀ D(ν)ν >= 0.
    """

    capabilities = frozenset({"PLANAR_3DOF", "GENERALIZED_FORCE"})
    input_semantics = PlantInputSemantics.GENERALIZED_FORCE

    def __init__(self, params: Generic3DOFPlantParameters) -> None:
        if not isinstance(params, Generic3DOFPlantParameters):
            raise TypeError(f"params must be Generic3DOFPlantParameters, got {type(params).__name__}")
        self._params = params

        # Precompute 3x3 Mass Matrix and its inverse
        m = params.mass_kg
        iz = params.i_z_kgm2
        m_11 = m - params.x_dot_u_kg
        m_22 = m - params.y_dot_v_kg
        m_33 = iz - params.n_dot_r_kgm2
        m_23 = m * params.x_g_m - params.y_dot_r_kgm

        self._m_mat = np.array(
            [
                [m_11, 0.0, 0.0],
                [0.0, m_22, m_23],
                [0.0, m_23, m_33],
            ],
            dtype=np.float64,
        )
        self._m_mat.flags.writeable = False

        self._inv_m_mat = np.linalg.inv(self._m_mat)
        self._inv_m_mat.flags.writeable = False

    @property
    def params(self) -> Generic3DOFPlantParameters:
        """Return immutable plant parameters."""
        return self._params

    @property
    def mass_matrix(self) -> FloatArray:
        """Return 3x3 mass matrix M = M_RB + M_A."""
        return self._m_mat

    @property
    def inv_mass_matrix(self) -> FloatArray:
        """Return 3x3 inverted mass matrix M⁻¹."""
        return self._inv_m_mat

    def coriolis_matrix(self, nu: FloatArray | tuple[float, float, float]) -> FloatArray:
        """Compute skew-symmetric 3DOF Coriolis matrix C(ν) guaranteeing νᵀ C(ν)ν = 0 (TS-01..06, VR-08).

        For symmetric M = [m11, 0, 0; 0, m22, m23; 0, m23, m33]:
            c13 = m22 * v + m23 * r
            c23 = m11 * u
            C(ν) = [ 0,    0,   -c13;
                     0,    0,    c23;
                    c13, -c23,    0  ]
        """
        u = float(nu[0])
        v = float(nu[1])
        r = float(nu[2])

        c13 = self._m_mat[1, 1] * v + self._m_mat[1, 2] * r
        c23 = self._m_mat[0, 0] * u

        return np.array(
            [
                [0.0, 0.0, -c13],
                [0.0, 0.0, c23],
                [c13, -c23, 0.0],
            ],
            dtype=np.float64,
        )

    def damping_force(self, nu: FloatArray | tuple[float, float, float]) -> FloatArray:
        """Compute hydrodynamic drag damping force vector D(ν)ν (N, N, N·m)."""
        u = float(nu[0])
        v = float(nu[1])
        r = float(nu[2])
        p = self._params

        fx = (p.d_u + p.d_uu * abs(u)) * u
        fy = (p.d_v + p.d_vv * abs(v)) * v + p.d_vr * r
        mz = (p.d_r + p.d_rr * abs(r)) * r + p.d_rv * v

        return np.array([fx, fy, mz], dtype=np.float64)

    def restoring_force(self, eta: FloatArray | tuple[float, float, float]) -> FloatArray:
        """Compute planar restoring force vector g(η) (normally zero)."""
        p = self._params
        return np.array(
            [
                p.restoring_k_n * float(eta[0]),
                p.restoring_k_e * float(eta[1]),
                p.restoring_k_psi * float(eta[2]),
            ],
            dtype=np.float64,
        )

    def rhs(
        self,
        time_s: float,  # noqa: ARG002
        state: PlantState | FloatArray | tuple[float, ...],
        control_load: VesselLoad | FloatArray | tuple[float, ...],
        env_load: VesselLoad | FloatArray | tuple[float, ...] | None = None,
    ) -> FloatArray:
        """Evaluate continuous 3DOF right-hand side derivative vector [dN/dt, dE/dt, dpsi/dt, du/dt, dv/dt, dr/dt].

        Args:
            time_s: Current continuous physical stage time in seconds.
            state: 6-element plant state [N, E, psi, u, v, r].
            control_load: Body-frame control forces/moment (surge_n, sway_n, yaw_nm).
            env_load: Body-frame environmental load forces/moment (or None for zero load).

        Returns:
            6-element float64 array of time derivatives.
        """
        x = _extract_state_vector(state)
        tau_ctrl = _extract_3dof_load(control_load, "control_load")
        tau_env = _extract_3dof_load(env_load, "env_load")

        north = float(x[0])
        east = float(x[1])
        psi = float(x[2])
        u = float(x[3])
        v = float(x[4])
        r = float(x[5])

        # Kinematics (NE world frame)
        cos_psi = math.cos(psi)
        sin_psi = math.sin(psi)
        d_north = u * cos_psi - v * sin_psi
        d_east = u * sin_psi + v * cos_psi
        d_psi = r

        # Dynamics (Body FRD frame)
        nu = np.array([u, v, r], dtype=np.float64)
        c_mat = self.coriolis_matrix(nu)
        c_force = c_mat @ nu
        d_force = self.damping_force(nu)
        g_force = self.restoring_force((north, east, psi))

        tau_total = tau_ctrl + tau_env
        net_force = tau_total - c_force - d_force - g_force

        nu_dot = self._inv_m_mat @ net_force

        return np.array(
            [d_north, d_east, d_psi, float(nu_dot[0]), float(nu_dot[1]), float(nu_dot[2])],
            dtype=np.float64,
        )
