"""FCB45 engineering actuation: bounded allocation and actual rudder angles.

Propulsion commands are in N; rudder commands have explicit mechanical angles.
Predicted normal forces remain in the force trace; only delivered loads reach the plant.
Design estimates come from the colleague ship_config.yaml, not sea trials.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass, replace
from types import MappingProxyType
from typing import Any

import numpy as np
from scipy.optimize import least_squares

from colav_simulator.modular_gnc.actuator_dynamics import ResolvedActuatorDynamics
from colav_simulator.modular_gnc.allocator import (
    FCB45_MAIN_RUDDER_BOW_ACTUATOR_LAYOUT_V2,
    ActuatorSpec,
    AllocatorSolution,
    DataDrivenAllocator,
    DataDrivenAllocatorSnapshot,
)
from colav_simulator.modular_gnc.contracts import (
    AchievedGeneralizedLoad,
    ActuatorDynamicsTrace,
    ControlTask,
    NavigationState,
    VesselLoad,
)
from colav_simulator.modular_gnc.load_model import world_ne_to_body_velocity

LAYOUT_ID = "fcb45_main_rudder_bow_actuator_layout_v2"


@dataclass(frozen=True)
class FCB45ActuationParameters:
    """Explicit SI design estimates and engineering model assumptions."""

    water_density_kg_m3: float = 1025.0
    rudder_area_m2: float = 3.5
    rudder_lift_slope_per_rad: float = 2.8
    rudder_angle_limit_rad: float = 0.6109
    rudder_rate_rad_s: float = 0.1
    rudder_stall_angle_rad: float = math.radians(35.0)
    propeller_diameter_m: float = 1.8
    propeller_wash_fraction: float = 0.55
    main_rate_n_s: float = 200000.0
    bow_rate_n_s: float = 50000.0
    bow_derate_start_mps: float = 1.5
    bow_unlock_mps: float = 2.7
    bow_lockout_mps: float = 3.2
    allocator_max_evaluations: int = 700
    allocator_gradient_tolerance: float = 1.0e-6

    def __post_init__(self) -> None:
        """Validate the finite physical parameter envelope."""
        for name, value in asdict(self).items():
            if isinstance(value, bool) or not math.isfinite(value) or value <= 0.0:
                raise ValueError(f"{name} must be finite and positive")
        if not self.bow_derate_start_mps < self.bow_unlock_mps < self.bow_lockout_mps:
            raise ValueError("bow thresholds must satisfy derate < unlock < lockout")
        if self.rudder_angle_limit_rad >= math.pi / 2 or self.rudder_stall_angle_rad >= math.pi / 2:
            raise ValueError("rudder angle and stall angle must be below pi/2")
        if self.propeller_wash_fraction > 1.0:
            raise ValueError("propeller_wash_fraction must be at most one")
        if not isinstance(self.allocator_max_evaluations, int):
            raise ValueError("allocator_max_evaluations must be an integer")


def _bow_authority(speed: float, enabled: bool, params: FCB45ActuationParameters) -> tuple[bool, float]:
    enabled = speed < (params.bow_lockout_mps if enabled else params.bow_unlock_mps)
    if not enabled:
        return False, 0.0
    x = float(
        np.clip((speed - params.bow_derate_start_mps) / (params.bow_lockout_mps - params.bow_derate_start_mps), 0.0, 1.0)
    )
    return True, 1.0 - x * x * (3.0 - 2.0 * x)


def rudder_inflow(
    params: FCB45ActuationParameters,
    surge_relative_mps: float,
    sway_relative_mps: float,
    yaw_rate_rad_s: float,
    x_m: float,
    delivered_propeller_thrust_n: float,
) -> tuple[float, float]:
    """Return normal-force slope and local inflow angle.

    Actuator-disc axial acceleration is blended by a wash fraction. This uses
    the paired main's delivered ahead thrust, without a hard-coded speed floor
    or mandated minimum thrust. No unsupported astern-rudder map is invented.
    """
    incoming = abs(surge_relative_mps)
    disk_area = math.pi * (params.propeller_diameter_m / 2.0) ** 2
    accelerated = math.sqrt(
        incoming * incoming + 2.0 * max(delivered_propeller_thrust_n, 0.0) / (params.water_density_kg_m3 * disk_area)
    )
    axial = max(0.0, surge_relative_mps + params.propeller_wash_fraction * (accelerated - incoming))
    lateral = sway_relative_mps + x_m * yaw_rate_rad_s
    beta = math.atan2(lateral, axial) if axial > 0.0 else 0.0
    # Axial dynamic pressure avoids a lateral-speed-squared positive feedback
    # outside the ahead-flow model's domain. No arbitrary forward-speed cap.
    slope = 0.5 * params.water_density_kg_m3 * params.rudder_area_m2 * params.rudder_lift_slope_per_rad * axial**2
    return slope, beta


def rudder_force_and_load(
    params: FCB45ActuationParameters,
    spec: ActuatorSpec,
    surge_relative: float,
    sway_relative: float,
    yaw_rate: float,
    propeller_thrust: float,
    angle: float,
) -> tuple[float, np.ndarray]:
    """One shared normal-force, induced-drag and moment model for both stages."""
    slope, beta = rudder_inflow(params, surge_relative, sway_relative, yaw_rate, spec.position_body_m[0], propeller_thrust)
    alpha = min(params.rudder_stall_angle_rad, max(-params.rudder_stall_angle_rad, angle + beta))
    normal = min(spec.max_force_n, max(spec.min_force_n, slope * math.sin(alpha)))
    fx, fy = -normal * math.sin(angle), -normal * math.cos(angle)
    return normal, np.array([fx, fy, spec.position_body_m[0] * fy - spec.position_body_m[1] * fx])


@dataclass(frozen=True)
class FCB45AllocatorSnapshot(DataDrivenAllocatorSnapshot):
    bow_enabled: bool
    optimization_seed: tuple[float, ...] = ()


@dataclass(frozen=True)
class FCB45AllocatorSolution(AllocatorSolution):
    rudder_angles_rad: Mapping[str, float]
    allocation_evaluations: int
    allocation_optimality: float

    def __post_init__(self) -> None:
        """Freeze force and mechanical-angle commands together."""
        super().__post_init__()
        object.__setattr__(self, "rudder_angles_rad", MappingProxyType(dict(self.rudder_angles_rad)))


class FCB45Allocator(DataDrivenAllocator):
    """Bounded transit allocation with speed-dependent actuator feasibility."""

    def __init__(self, parameters: Mapping[str, Any]) -> None:
        super().__init__(FCB45_MAIN_RUDDER_BOW_ACTUATOR_LAYOUT_V2)
        self.parameters = FCB45ActuationParameters(**parameters)
        self._bow_enabled = False
        self.bow_authority = 0.0
        self._navigation: NavigationState | None = None
        self._current_ne = (0.0, 0.0)
        self._optimization_seed = np.zeros(len(self._ids))

    @property
    def supported_tasks(self) -> frozenset[ControlTask]:
        return frozenset({ControlTask.TRANSIT, ControlTask.MANUAL_LOAD})

    def reset(self) -> None:
        super().reset()
        self._bow_enabled = False
        self.bow_authority = 0.0
        self._navigation = None
        self._optimization_seed = np.zeros(len(self._ids))

    def snapshot(self) -> FCB45AllocatorSnapshot:
        return FCB45AllocatorSnapshot(dict(self._health), self._bow_enabled, tuple(self._optimization_seed))

    def restore(self, snapshot: FCB45AllocatorSnapshot) -> None:
        if not isinstance(snapshot, FCB45AllocatorSnapshot):
            raise TypeError("expected FCB45AllocatorSnapshot")
        super().restore(snapshot)
        self._bow_enabled = snapshot.bow_enabled
        self._navigation = None
        self._optimization_seed = np.array(snapshot.optimization_seed or (0.0,) * len(self._ids))

    def set_operating_point(self, navigation: NavigationState, current_ne: tuple[float, float]) -> None:
        self._navigation = navigation
        self._current_ne = current_ne

    def allocate(self, requested: VesselLoad, tick: int = 0, time_s: float = 0.0) -> AllocatorSolution:
        if requested.roll_nm != 0.0:
            raise ValueError("roll is not an independently allocated control axis")
        if self._navigation is None:
            raise ValueError("FCB45 allocator requires a navigation operating point")
        nav = self._navigation
        current = world_ne_to_body_velocity(self._current_ne, nav.heading_rad)
        u, v = nav.surge_mps - current[0], nav.sway_mps - current[1]
        self._bow_enabled, self.bow_authority = _bow_authority(math.hypot(u, v), self._bow_enabled, self.parameters)
        low, high = -np.ones(len(self._ids)), np.ones(len(self._ids))
        constraints = []
        for i, spec in enumerate(self._asset.actuators):
            if spec.kind == "tunnel_thruster":
                low[i], high[i] = -self.bow_authority, self.bow_authority
                if self.bow_authority == 0.0:
                    constraints.append((spec.actuator_id, "speed_lockout"))
        tau = np.array([requested.surge_n, requested.sway_n, requested.yaw_nm])
        weights = np.array([1.0 / 200000.0, self.bow_authority / 40000.0, 1.0 / 960000.0])
        free = high - low > 1e-8
        fixed_values = low.copy()

        def loads(z: np.ndarray) -> tuple[np.ndarray, dict[str, float], dict[str, float]]:
            forces = {
                spec.actuator_id: float(z[i] * spec.max_force_n)
                for i, spec in enumerate(self._asset.actuators)
                if spec.kind != "rudder"
            }
            angles = {}
            achieved = np.zeros(3)
            for i, spec in enumerate(self._asset.actuators):
                key = spec.actuator_id
                if spec.kind == "rudder":
                    angle = float(z[i] * self.parameters.rudder_angle_limit_rad)
                    prop = "main_thruster_port" if key == "rudder_port" else "main_thruster_starboard"
                    normal, contribution = rudder_force_and_load(
                        self.parameters,
                        spec,
                        u,
                        v,
                        nav.yaw_rate_radps,
                        forces[prop] * self._health[prop],
                        angle,
                    )
                    forces[key], angles[key] = normal, angle
                else:
                    fx = forces[key] * math.cos(spec.orientation_body_rad)
                    fy = forces[key] * math.sin(spec.orientation_body_rad)
                    contribution = np.array([fx, fy, spec.position_body_m[0] * fy - spec.position_body_m[1] * fx])
                achieved += contribution * self._health[key]
            return achieved, forces, angles

        def residual_for(free_values: np.ndarray) -> np.ndarray:
            z = fixed_values.copy()
            z[free] = free_values
            # Regularize command increments, not absolute power. This keeps
            # redundant propeller/rudder solutions continuous through zero
            # inflow instead of chasing a different wash allocation each tick.
            return np.r_[(loads(z)[0] - tau) * weights, 1e-3 * (z - seed)]

        seed = np.clip(self._optimization_seed, low, high)
        solved = least_squares(
            residual_for,
            seed[free],
            bounds=(low[free], high[free]),
            method="dogbox",
            ftol=1e-8,
            xtol=1e-8,
            gtol=self.parameters.allocator_gradient_tolerance,
            max_nfev=self.parameters.allocator_max_evaluations,
        )
        if not solved.success or not np.isfinite(solved.x).all():
            raise RuntimeError(f"FCB45 coupled allocation failed: {solved.message}")
        z = fixed_values.copy()
        z[free] = solved.x
        self._optimization_seed = z
        achieved, commands, angles = loads(z)
        for i, key in enumerate(self._ids):
            if free[i] and min(abs(z[i] - low[i]), abs(z[i] - high[i])) < 1e-6:
                constraints.append((key, "physical_command_bound"))
        residual = tau - achieved
        degraded = tuple(key for key in self._ids if self._health[key] < 1.0)
        return FCB45AllocatorSolution(
            requested,
            VesselLoad(surge_n=achieved[0], sway_n=achieved[1], yaw_nm=achieved[2]),
            VesselLoad(surge_n=residual[0], sway_n=residual[1], yaw_nm=residual[2]),
            commands,
            dict(self._health),
            tuple(constraints),
            bool(constraints),
            bool(degraded),
            degraded,
            self.asset_id,
            tick,
            time_s,
            angles,
            int(solved.nfev),
            float(solved.optimality),
        )


@dataclass(frozen=True)
class FCB45ActuatorSnapshot:
    forces: Mapping[str, float]
    angles: Mapping[str, float]

    def __post_init__(self) -> None:
        """Freeze the delivered forces and mechanical angles."""
        object.__setattr__(self, "forces", MappingProxyType(dict(self.forces)))
        object.__setattr__(self, "angles", MappingProxyType(dict(self.angles)))


@dataclass(frozen=True)
class FCB45ActuatorTrace(ActuatorDynamicsTrace):
    rudder_angles_rad: Mapping[str, float]
    rudder_requested_angles_rad: Mapping[str, float]
    bow_authority: float

    def __post_init__(self) -> None:
        """Validate the base trace and freeze angle evidence."""
        super().__post_init__()
        object.__setattr__(self, "rudder_angles_rad", MappingProxyType(dict(self.rudder_angles_rad)))
        object.__setattr__(self, "rudder_requested_angles_rad", MappingProxyType(dict(self.rudder_requested_angles_rad)))

    def to_achieved_generalized_load(self) -> AchievedGeneralizedLoad:
        base = super().to_achieved_generalized_load()
        return replace(
            base,
            details={
                **base.details,
                "rudder_angles_rad": dict(self.rudder_angles_rad),
                "rudder_requested_angles_rad": dict(self.rudder_requested_angles_rad),
                "bow_authority": self.bow_authority,
            },
        )


class FCB45ActuatorDynamics:
    """Single owner of propulsion force slew and physical rudder angle slew."""

    identity = "resolved_actuator_dynamics"
    fidelity_profile = "resolved"
    asset_id = LAYOUT_ID
    supported_tasks = frozenset({ControlTask.TRANSIT, ControlTask.MANUAL_LOAD})

    def __init__(self, parameters: Mapping[str, Any]) -> None:
        self.parameters = FCB45ActuationParameters(**parameters)
        self._asset = FCB45_MAIN_RUDDER_BOW_ACTUATOR_LAYOUT_V2
        self._ids = self._asset.actuator_ids()
        content = {"model": "fcb45_rudder_inflow_v2", "layout": LAYOUT_ID, "parameters": asdict(self.parameters)}
        self.config_hash = hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()
        self.reset()

    def reset(self) -> None:
        self._forces = dict.fromkeys(self._ids, 0.0)
        self._angles = {spec.actuator_id: 0.0 for spec in self._asset.actuators if spec.kind == "rudder"}
        self._latest_trace = None

    def snapshot(self) -> FCB45ActuatorSnapshot:
        return FCB45ActuatorSnapshot(self._forces, self._angles)

    def restore(self, snapshot: FCB45ActuatorSnapshot) -> None:
        if not isinstance(snapshot, FCB45ActuatorSnapshot) or set(snapshot.forces) != set(self._ids):
            raise ValueError("FCB45 actuator snapshot/layout mismatch")
        if set(snapshot.angles) != set(self._angles):
            raise ValueError("FCB45 rudder angle snapshot mismatch")
        self._forces, self._angles = dict(snapshot.forces), dict(snapshot.angles)
        self._latest_trace = None

    def latest_trace(self) -> FCB45ActuatorTrace | None:
        return self._latest_trace

    def apply(
        self,
        commands_n: Mapping[str, float],
        actuator_health: Mapping[str, float],
        tick: int,
        time_s: float,
        dt_s: float,
        *,
        navigation: NavigationState,
        current_ne: tuple[float, float],
        bow_authority: float,
        rudder_angles_rad: Mapping[str, float],
    ) -> FCB45ActuatorTrace:
        ResolvedActuatorDynamics._validate_health(actuator_health, self._ids)
        if set(commands_n) != set(self._ids) or not math.isfinite(dt_s) or dt_s <= 0.0:
            raise ValueError("invalid actuator command coverage or dt")
        for spec in self._asset.actuators:
            value = commands_n[spec.actuator_id]
            if not math.isfinite(value) or not spec.min_force_n <= value <= spec.max_force_n:
                raise ValueError("actuator command outside physical envelope")
        params = self.parameters
        if set(rudder_angles_rad) != set(self._angles) or any(
            not math.isfinite(angle) or abs(angle) > params.rudder_angle_limit_rad for angle in rudder_angles_rad.values()
        ):
            raise ValueError("rudder commands must cover both physical angles within their limits")
        current = world_ne_to_body_velocity(current_ne, navigation.heading_rad)
        u, v = navigation.surge_mps - current[0], navigation.sway_mps - current[1]
        # The physical execution guard uses actual through-water speed too.
        if math.hypot(u, v) >= params.bow_lockout_mps:
            bow_authority = 0.0
        limited = []
        requested_angles = {}
        achieved = np.zeros(3)
        for spec in self._asset.actuators:
            if spec.kind == "rudder":
                continue
            key = spec.actuator_id
            rate = params.main_rate_n_s if spec.kind == "main" else params.bow_rate_n_s
            value = self._forces[key] + float(np.clip(commands_n[key] - self._forces[key], -rate * dt_s, rate * dt_s))
            if spec.kind == "tunnel_thruster":
                value = float(np.clip(value, spec.min_force_n * bow_authority, spec.max_force_n * bow_authority))
            if abs(value - commands_n[key]) > 1e-8:
                limited.append(key)
            self._forces[key] = value
            force = value * actuator_health[key]
            fx, fy = force * math.cos(spec.orientation_body_rad), force * math.sin(spec.orientation_body_rad)
            achieved += [fx, fy, spec.position_body_m[0] * fy - spec.position_body_m[1] * fx]
        for spec in self._asset.actuators:
            if spec.kind != "rudder":
                continue
            key = spec.actuator_id
            prop = "main_thruster_port" if key == "rudder_port" else "main_thruster_starboard"
            desired = float(rudder_angles_rad[key])
            requested_angles[key] = desired
            angle = self._angles[key] + float(
                np.clip(desired - self._angles[key], -params.rudder_rate_rad_s * dt_s, params.rudder_rate_rad_s * dt_s)
            )
            if abs(angle - desired) > 1e-10:
                limited.append(key)
            self._angles[key] = angle
            normal, contribution = rudder_force_and_load(
                params,
                spec,
                u,
                v,
                navigation.yaw_rate_radps,
                self._forces[prop] * actuator_health[prop],
                angle,
            )
            self._forces[key] = normal
            achieved += contribution * actuator_health[key]
        self._latest_trace = FCB45ActuatorTrace(
            "resolved",
            self.identity,
            self.config_hash,
            tick,
            time_s,
            dt_s,
            commands_n,
            self._forces,
            tuple(limited),
            dict.fromkeys(self._ids, 0),
            tuple(achieved),
            self._angles,
            requested_angles,
            bow_authority,
        )
        return self._latest_trace
