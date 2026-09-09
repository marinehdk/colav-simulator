"""Auditable FCB45 environmental mechanisms, separate from legacy S10 assets.

Current: Fossen's relative-velocity equation, expressed as an equivalent load
on the existing absolute-velocity plant. Wind: Blendermann (1994) with explicit
engineering coefficients. Wave excitation is a force model, never a motion RAO.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from scipy.optimize import brentq
from scipy.special import beta as beta_function

from colav_simulator.modular_gnc.contracts import (
    CurrentStrategy,
    EnvironmentalLoads,
    EnvironmentTruth,
    NavigationState,
    PlantState,
    VesselLoad,
    WaveFieldSample,
    WaveLoadMode,
)
from colav_simulator.modular_gnc.load_model import world_ne_to_body_velocity
from colav_simulator.modular_gnc.plant import GenericRoll4DOFPlant


def relative_current_load(
    plant: GenericRoll4DOFPlant, state: NavigationState | PlantState, current_ne: tuple[float, float]
) -> VesselLoad:
    """Equivalent correction for spatially uniform, steady NED current.

    M_RB*nu_dot + C_RB(nu)*nu + M_A*nu_r_dot + C_A(nu_r)*nu_r
    + D(nu_r)*nu_r + g = tau. Only the water-relative terms change;
    rigid-body inertia, absolute position kinematics and hydrostatics stay put.
    No independent OCIMF-style whole-hull current resistance is added.
    """
    uc, vc = world_ne_to_body_velocity(current_ne, state.heading_rad)
    if uc == 0.0 and vc == 0.0:
        return VesselLoad.zero()
    par = plant.params
    mass_rb = np.array(
        [
            [par.mass_kg, 0.0, 0.0, 0.0],
            [0.0, par.mass_kg, -par.mass_kg * par.z_g_m, par.mass_kg * par.x_g_m],
            [0.0, -par.mass_kg * par.z_g_m, par.i_x_kgm2, 0.0],
            [0.0, par.mass_kg * par.x_g_m, 0.0, par.i_z_kgm2],
        ]
    )
    added = plant.mass_matrix - mass_rb
    roll_rate = state.roll_rate_radps if isinstance(state, PlantState) else 0.0
    nu = np.array([state.surge_mps, state.sway_mps, roll_rate, state.yaw_rate_radps])
    nu_r = nu - [uc, vc, 0.0, 0.0]

    def added_coriolis_force(velocity: np.ndarray) -> np.ndarray:
        momentum = added @ velocity
        return np.array(
            [
                -momentum[1] * velocity[3],
                momentum[0] * velocity[3],
                0.0,
                momentum[1] * velocity[0] - momentum[0] * velocity[1],
            ]
        )

    current_derivative = np.array([state.yaw_rate_radps * vc, -state.yaw_rate_radps * uc, 0.0, 0.0])
    correction = (
        added @ current_derivative
        + added_coriolis_force(nu)
        - added_coriolis_force(nu_r)
        + plant.damping_force(nu)
        - plant.damping_force(nu_r)
    )
    return VesselLoad(surge_n=correction[0], sway_n=correction[1], roll_nm=correction[2], yaw_nm=correction[3])


@dataclass(frozen=True)
class BlendermannWindParameters:
    """Speed-boat coefficients from MSS Blendermann row 14; FCB estimates."""

    frontal_area_m2: float = 45.0
    lateral_area_m2: float = 180.0
    length_m: float = 44.1
    center_x_m: float = 0.0
    center_z_body_m: float = -2.8
    cd_transverse: float = 0.90
    cd_longitudinal_bow: float = 0.55
    cd_longitudinal_stern: float = 0.60
    crossflow_delta: float = 0.60
    roll_factor: float = 1.10
    air_density_kg_m3: float = 1.225

    def __post_init__(self) -> None:
        """Validate geometry and empirical coefficient ranges."""
        for name, value in vars(self).items():
            if isinstance(value, bool) or not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
            if name not in {"center_x_m", "center_z_body_m"} and value <= 0.0:
                raise ValueError(f"{name} must be positive")
        if self.crossflow_delta >= 2.0:
            raise ValueError("crossflow_delta must be below two")


def blendermann_wind_load(
    params: BlendermannWindParameters, wind_ne: tuple[float, float], state: NavigationState | PlantState
) -> VesselLoad:
    """Blendermann coefficients with explicit flow-to/body/NED conversion.

    gamma=0 is apparent wind from ahead; +pi/2 pushes to starboard. Port
    angles mirror the published 0..pi half-plane rather than extrapolating it.
    Moments about CG follow r cross F, with positive roll starboard-down.
    """
    wx, wy = world_ne_to_body_velocity(wind_ne, state.heading_rad)
    wx, wy = wx - state.surge_mps, wy - state.sway_mps
    speed2 = wx * wx + wy * wy
    if speed2 == 0.0:
        return VesselLoad.zero()
    gamma = math.atan2(wy, -wx)
    cd_l = params.cd_longitudinal_bow if abs(gamma) <= math.pi / 2 else params.cd_longitudinal_stern
    den = (
        1.0
        - 0.5
        * params.crossflow_delta
        * (1.0 - cd_l * params.frontal_area_m2 / (params.cd_transverse * params.lateral_area_m2))
        * math.sin(2.0 * gamma) ** 2
    )
    q = 0.5 * params.air_density_kg_m3 * speed2
    fx = -q * cd_l * math.cos(gamma) / den * params.frontal_area_m2
    fy = q * params.cd_transverse * math.sin(gamma) / den * params.lateral_area_m2
    yaw_arm = params.center_x_m - 0.18 * params.length_m * (abs(gamma) - math.pi / 2.0)
    return VesselLoad(surge_n=fx, sway_n=fy, yaw_nm=yaw_arm * fy, roll_nm=-params.center_z_body_m * params.roll_factor * fy)


@dataclass(frozen=True)
class FCB45WaveGeometry:
    """A displacement-matched generalized Wigley hull, not the as-built lines.

    Half breadth b(x,z) = B/2*(1-(2x/L)^2)*(1-(z/T)^2)^q, with z measured
    downward from still water. q is solved from displaced volume. This retains
    the design L/B/T and displacement instead of silently borrowing another hull.
    Linear FK pressure is integrated on the mean wetted surface; diffraction,
    radiation memory, slamming and time-varying wetting are outside this model.
    """

    length_m: float = 44.1
    beam_m: float = 8.0
    draft_m: float = 2.0
    displacement_kg: float = 220000.0
    kg_m: float = 2.2
    water_depth_m: float = 30.0
    water_density_kg_m3: float = 1025.0
    gravity_mps2: float = 9.81
    longitudinal_nodes: int = 24
    depth_nodes: int = 12

    def __post_init__(self) -> None:
        """Reject geometry outside the declared approximate hull family."""
        for name, value in vars(self).items():
            if isinstance(value, bool) or not math.isfinite(value) or value <= 0.0:
                raise ValueError(f"{name} must be finite and positive")
        for name in ("longitudinal_nodes", "depth_nodes"):
            if not isinstance(getattr(self, name), int) or getattr(self, name) < 4:
                raise ValueError(f"{name} must be an integer >= 4")
        if self.water_depth_m <= self.draft_m:
            raise ValueError("water depth must exceed draft")
        if not 0.01 < self.block_coefficient < 2.0 / 3.0:
            raise ValueError("displacement outside generalized Wigley hull domain")

    @property
    def block_coefficient(self) -> float:
        return self.displacement_kg / (self.water_density_kg_m3 * self.length_m * self.beam_m * self.draft_m)


@lru_cache(maxsize=256)
def wave_number(omega: float, depth: float, gravity: float) -> float:
    """Positive solution of finite-depth Airy dispersion omega²=g k tanh(kh)."""
    if not all(math.isfinite(x) and x > 0.0 for x in (omega, depth, gravity)):
        raise ValueError("frequency, depth and gravity must be finite and positive")
    lower = 0.0
    upper = max(2.0 * omega**2 / gravity, 2.0 * omega / math.sqrt(gravity * depth))
    while gravity * upper * math.tanh(upper * depth) < omega**2:
        upper *= 2.0
    return brentq(lambda k: gravity * k * math.tanh(k * depth) - omega**2, lower, upper, xtol=1e-14)


class IncidentPressureWaveModel:
    """Airy/Froude-Krylov pressure quadrature in SI, with exact earth phase."""

    def __init__(self, geometry: FCB45WaveGeometry) -> None:
        self.geometry = geometry
        target = 1.5 * geometry.block_coefficient
        self.vertical_exponent = brentq(lambda q: 0.5 * beta_function(0.5, q + 1.0) - target, 0.0, 10000.0)
        x, wx = np.polynomial.legendre.leggauss(geometry.longitudinal_nodes)
        depth, wz = np.polynomial.legendre.leggauss(geometry.depth_nodes)
        x, wx = x * geometry.length_m / 2.0, wx * geometry.length_m / 2.0
        depth, wz = (depth + 1.0) * geometry.draft_m / 2.0, wz * geometry.draft_m / 2.0
        xx, zz = np.meshgrid(x, depth, indexing="ij")
        weights = np.outer(wx, wz)
        xp = 1.0 - (2.0 * xx / geometry.length_m) ** 2
        zp = 1.0 - (zz / geometry.draft_m) ** 2
        breadth = geometry.beam_m / 2.0 * xp * zp**self.vertical_exponent
        bx = -4.0 * geometry.beam_m * xx / geometry.length_m**2 * zp**self.vertical_exponent
        bz = -geometry.beam_m * self.vertical_exponent * xp * zz / geometry.draft_m**2 * zp ** (self.vertical_exponent - 1.0)
        points, load_weights = [], []
        for side in (-1.0, 1.0):
            y = side * breadth
            z_cg = zz + geometry.kg_m - geometry.draft_m
            # Outward normal times dS = (-b_x, side, -b_z) dx dz.
            # Pressure force acts inward; moments use body FRD r cross F.
            fx, fy, fz = bx * weights, -side * weights, bz * weights
            points.append(np.stack((xx, y, zz), axis=-1).reshape(-1, 3))
            load_weights.append(np.stack((fx, fy, y * fz - z_cg * fy, xx * fy - y * fx), axis=-1).reshape(-1, 4))
        self.points = np.concatenate(points)
        self.load_weights = np.concatenate(load_weights)
        self.points.flags.writeable = self.load_weights.flags.writeable = False

    def calculate(self, wave: WaveFieldSample, state: NavigationState | PlantState, time_s: float) -> VesselLoad:
        if not wave.components:
            return VesselLoad.zero()
        g = self.geometry
        amplitudes = np.array([c.amplitude_m for c in wave.components])
        omega = np.array([c.omega_radps for c in wave.components])
        directions = np.array([c.direction_to_rad for c in wave.components])
        phases = np.array([c.phase_rad for c in wave.components])
        k = np.array([wave_number(w, g.water_depth_m, g.gravity_mps2) for w in omega])
        relative = directions - state.heading_rad
        along_center = state.north_m * np.cos(directions) + state.east_m * np.sin(directions)
        along_surface = self.points[:, 0, None] * np.cos(relative) + self.points[:, 1, None] * np.sin(relative)
        phase = k * (along_center + along_surface) - omega * time_s + phases
        # Stable cosh(k(h-z))/cosh(kh), including large kh without overflow.
        depth = self.points[:, 2, None]
        vertical = (np.exp(-k * depth) + np.exp(-k * (2.0 * g.water_depth_m - depth))) / (
            1.0 + np.exp(-2.0 * k * g.water_depth_m)
        )
        pressure = g.water_density_kg_m3 * g.gravity_mps2 * np.sum(amplitudes * vertical * np.cos(phase), axis=1)
        force = pressure @ self.load_weights
        return VesselLoad(surge_n=force[0], sway_n=force[1], roll_nm=force[2], yaw_nm=force[3])


@dataclass(frozen=True)
class WaveDriftProxyParameters:
    """Explicit diagonal reflection approximation, not vessel QTF coefficients.

    Journee/Massie Offshore Hydromechanics, section 6.4: a fully reflecting
    deep-water wall has mean force per unit span E=0.5*rho*g*a². Projecting
    bow/beam spans is an engineering rectangular-envelope approximation.
    Fraction=1 is the wall-reflection case; 0..1 is the declared sensitivity
    interval. This does not assert a universal bound for a moving real hull.
    """

    reflection_energy_fraction: float = 1.0
    center_x_m: float = 0.0
    center_z_body_m: float = 0.0

    def __post_init__(self) -> None:
        """Validate the explicit reflection fraction and moment reference."""
        if not all(not isinstance(x, bool) and math.isfinite(x) for x in vars(self).values()):
            raise ValueError("wave drift parameters must be finite")
        if not 0.0 <= self.reflection_energy_fraction <= 1.0:
            raise ValueError("reflection_energy_fraction must lie in [0,1]")


def mean_drift_proxy(
    geometry: FCB45WaveGeometry, params: WaveDriftProxyParameters, wave: WaveFieldSample, heading: float
) -> VesselLoad:
    """Sum diagonal a_i² mean loads; there is no first-order phase here."""
    fx, fy = 0.0, 0.0
    for component in wave.components:
        energy = 0.5 * geometry.water_density_kg_m3 * geometry.gravity_mps2 * component.amplitude_m**2
        c, s = math.cos(component.direction_to_rad - heading), math.sin(component.direction_to_rad - heading)
        fx += params.reflection_energy_fraction * energy * geometry.beam_m * c * abs(c)
        fy += params.reflection_energy_fraction * energy * geometry.length_m * s * abs(s)
    return VesselLoad(surge_n=fx, sway_n=fy, yaw_nm=params.center_x_m * fy, roll_nm=-params.center_z_body_m * fy)


class FCB45EnvironmentalLoadModel:
    """Composition of explicitly sourced engineering environmental models."""

    current_strategy = CurrentStrategy.CURRENT_RELATIVE_DAMPING

    def __init__(self, plant: GenericRoll4DOFPlant, parameters: Mapping) -> None:
        if not isinstance(plant, GenericRoll4DOFPlant):
            raise ValueError("FCB45 environmental model requires the 4DOF force plant")
        allowed = {
            "wind_parameters",
            "wave_geometry",
            "drift_proxy_parameters",
            "current_strategy",
            "wave_mode",
            "enable_wind",
            "enable_current",
        }
        if set(parameters) - allowed:
            raise ValueError(f"unsupported FCB45 environmental parameters: {set(parameters) - allowed}")
        if parameters.get("current_strategy", "current_relative_damping") != "current_relative_damping":
            raise ValueError("FCB45 physical environment requires current_relative_damping")
        self.plant = plant
        self.wind_parameters = BlendermannWindParameters(**parameters.get("wind_parameters", {}))
        self.wave = IncidentPressureWaveModel(FCB45WaveGeometry(**parameters.get("wave_geometry", {})))
        self.wave_mode = WaveLoadMode(parameters.get("wave_mode", "first_order"))
        self.drift_parameters = WaveDriftProxyParameters(**parameters.get("drift_proxy_parameters", {}))
        if self.wave_mode in {WaveLoadMode.MEAN_DRIFT, WaveLoadMode.BOTH} and "drift_proxy_parameters" not in parameters:
            raise ValueError("mean drift requires explicitly supplied drift_proxy_parameters; no implicit QTF")
        self.enable_wind = parameters.get("enable_wind", True)
        self.enable_current = parameters.get("enable_current", True)
        if not isinstance(self.enable_wind, bool) or not isinstance(self.enable_current, bool):
            raise ValueError("environment enable flags must be boolean")
        if not math.isclose(plant.params.mass_kg, self.wave.geometry.displacement_kg, rel_tol=1e-9):
            raise ValueError("wave proxy displacement must match the selected plant mass")

    def __deepcopy__(self, memo: dict[int, object]) -> FCB45EnvironmentalLoadModel:
        """Share immutable model parameters and quadrature between episode clones."""
        # All model parameters, plant parameters and quadrature arrays are immutable.
        memo[id(self)] = self
        return self

    def compute_loads(self, truth: EnvironmentTruth, vessel_state: NavigationState | PlantState) -> EnvironmentalLoads:
        if not isinstance(truth, EnvironmentTruth):
            raise TypeError("environmental load model requires EnvironmentTruth")
        wind = (
            blendermann_wind_load(self.wind_parameters, truth.wind.velocity_ne, vessel_state)
            if self.enable_wind
            else VesselLoad.zero()
        )
        current = (
            relative_current_load(self.plant, vessel_state, truth.current.velocity_ne)
            if self.enable_current
            else VesselLoad.zero()
        )
        wave = (
            self.wave.calculate(truth.wave, vessel_state, truth.time_s)
            if self.wave_mode in {WaveLoadMode.FIRST_ORDER, WaveLoadMode.BOTH}
            else VesselLoad.zero()
        )
        drift = (
            mean_drift_proxy(self.wave.geometry, self.drift_parameters, truth.wave, vessel_state.heading_rad)
            if self.wave_mode in {WaveLoadMode.MEAN_DRIFT, WaveLoadMode.BOTH}
            else VesselLoad.zero()
        )
        uc, vc = world_ne_to_body_velocity(truth.current.velocity_ne, vessel_state.heading_rad)
        return EnvironmentalLoads.from_components(
            wind=wind,
            current=current,
            wave_first_order=wave,
            wave_mean_drift=drift,
            details={
                "model": "fcb45_physical_environment_v1",
                "current_strategy": "plant_consistent_relative_water_equivalent_load",
                "relative_surge_mps": vessel_state.surge_mps - uc,
                "relative_sway_mps": vessel_state.sway_mps - vc,
                "current_body_derivative_mps2": (vessel_state.yaw_rate_radps * vc, -vessel_state.yaw_rate_radps * uc),
                "wind_model": "blendermann1994_speedboat_prior",
                "wave_model": "linear_airy_froude_krylov_generalized_wigley",
                "wave_hull_vertical_exponent": self.wave.vertical_exponent,
                "wave_phase": "k_dot_position_minus_omega_time",
                "wave_mean_drift": "diagonal_reflection_momentum_flux_proxy_not_qtf",
                "reflection_energy_fraction": self.drift_parameters.reflection_energy_fraction,
                "validated_for_vessel": False,
            },
        )

    def compute_total_load_for_rhs(self, truth: EnvironmentTruth, vessel_state: PlantState) -> VesselLoad:
        return self.compute_loads(truth, vessel_state).total
