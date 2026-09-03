"""Data-driven actuator layout assets and generalized-load allocator (Issue #58, S6.1).

Layout, geometry, response curves, limits, effectiveness, and health are derived
exclusively from immutable data assets following the modular_gnc asset pattern
(TS-23, VR-10). The allocator task space is strictly 3DOF [X, Y, N]: the
roll-moment channel is never exposed, allocated, or reported, matching the
strictly unactuated roll channel of the plants (RA-12, VR-16, TS-22).

No hardcoded actuator ordering exists anywhere: actuator identity is the string
id, allocation outputs are id-keyed mappings, and layout permutation changes
only the declaration order of equivalent data.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

import numpy as np
from numpy.typing import NDArray

from colav_simulator.modular_gnc.contracts import (
    AchievedGeneralizedLoad,
    AchievedLoadStatus,
    ApplicabilityDomain,
    AssetIntegrityError,
    AssetMetadata,
    AssetTrustLevel,
    ControlTask,
    VesselLoad,
)

FloatArray = NDArray[np.float64]

_SUPPORTED_RESPONSE_CURVES: frozenset[str] = frozenset({"linear"})


def _non_empty_str(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def _finite_scalar(name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a float, got {type(value).__name__}")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


@dataclass(frozen=True)
class ActuatorSpec:
    """Immutable per-actuator data record; every field is asset-declared (AC1).

    Geometry is body-frame (x forward, y starboard); orientation is the body-frame
    force direction in radians; yaw moment arms follow the right-positive
    convention N = x*Fy - y*Fx (TS-04, TS-05).
    """

    actuator_id: str
    kind: str
    position_body_m: tuple[float, float]
    orientation_body_rad: float
    min_force_n: float
    max_force_n: float
    effectiveness: float = 1.0
    response_curve: str = "linear"
    initial_health: float = 1.0

    def __post_init__(self) -> None:
        """Validate identifiers, geometry, limits, curve type, and health."""
        object.__setattr__(self, "actuator_id", _non_empty_str("actuator_id", self.actuator_id))
        object.__setattr__(self, "kind", _non_empty_str("kind", self.kind))
        pos = self.position_body_m
        if not isinstance(pos, (tuple, list)) or len(pos) != 2:
            raise ValueError("position_body_m must be a 2-tuple (x, y)")
        object.__setattr__(
            self,
            "position_body_m",
            (_finite_scalar("position_body_m[0]", pos[0]), _finite_scalar("position_body_m[1]", pos[1])),
        )
        object.__setattr__(self, "orientation_body_rad", _finite_scalar("orientation_body_rad", self.orientation_body_rad))
        min_force = _finite_scalar("min_force_n", self.min_force_n)
        max_force = _finite_scalar("max_force_n", self.max_force_n)
        if min_force > 0.0 or max_force < 0.0 or min_force > max_force:
            raise ValueError(
                f"force limits must bracket zero (min_force_n={min_force}, max_force_n={max_force})"
            )
        object.__setattr__(self, "min_force_n", min_force)
        object.__setattr__(self, "max_force_n", max_force)
        effectiveness = _finite_scalar("effectiveness", self.effectiveness)
        if effectiveness < 0.0:
            raise ValueError("effectiveness must be non-negative")
        object.__setattr__(self, "effectiveness", effectiveness)
        curve = _non_empty_str("response_curve", self.response_curve)
        if curve not in _SUPPORTED_RESPONSE_CURVES:
            raise ValueError(
                f"unsupported response_curve '{curve}' (supported: {sorted(_SUPPORTED_RESPONSE_CURVES)})"
            )
        object.__setattr__(self, "response_curve", curve)
        health = _finite_scalar("initial_health", self.initial_health)
        if not 0.0 <= health <= 1.0:
            raise ValueError(f"initial_health must be within [0, 1], got {health}")
        object.__setattr__(self, "initial_health", health)


def actuator_layout_content_sha256(actuators: tuple[ActuatorSpec, ...]) -> str:
    """Return canonical content SHA-256 for an actuator tuple (TS-23, TS-27)."""
    rows = [
        {
            "actuator_id": spec.actuator_id,
            "kind": spec.kind,
            "position_body_m": list(spec.position_body_m),
            "orientation_body_rad": spec.orientation_body_rad,
            "min_force_n": spec.min_force_n,
            "max_force_n": spec.max_force_n,
            "effectiveness": spec.effectiveness,
            "response_curve": spec.response_curve,
            "initial_health": spec.initial_health,
        }
        for spec in actuators
    ]
    payload = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class ActuatorLayoutAsset:
    """Immutable actuator layout data asset with provenance and integrity verification (TS-23, TS-27).

    The effectiveness matrix is derived from declared geometry and is strictly
    (3, n): rows are body [X, Y, N]; no roll-moment row exists (RA-12, VR-16).
    """

    metadata: AssetMetadata
    actuators: tuple[ActuatorSpec, ...]

    def __deepcopy__(self, memo: dict[int, Any]) -> ActuatorLayoutAsset:
        """Reuse the immutable content-addressed asset during episode cloning."""
        memo[id(self)] = self
        return self

    def __post_init__(self) -> None:
        """Validate actuator uniqueness and precompute the geometry matrix."""
        if not isinstance(self.metadata, AssetMetadata):
            raise TypeError(f"metadata must be AssetMetadata, got {type(self.metadata).__name__}")
        if not self.actuators:
            raise ValueError("actuator layout cannot be empty")
        for i, spec in enumerate(self.actuators):
            if not isinstance(spec, ActuatorSpec):
                raise TypeError(f"actuators[{i}] must be ActuatorSpec, got {type(spec).__name__}")
        ids = [spec.actuator_id for spec in self.actuators]
        if len(set(ids)) != len(ids):
            raise ValueError(f"actuator ids must be unique, got {ids}")
        object.__setattr__(self, "actuators", tuple(self.actuators))

        n = len(self.actuators)
        matrix = np.zeros((3, n), dtype=np.float64)
        for i, spec in enumerate(self.actuators):
            cos_t = math.cos(spec.orientation_body_rad)
            sin_t = math.sin(spec.orientation_body_rad)
            x_m, y_m = spec.position_body_m
            matrix[0, i] = spec.effectiveness * cos_t
            matrix[1, i] = spec.effectiveness * sin_t
            matrix[2, i] = spec.effectiveness * (x_m * sin_t - y_m * cos_t)
        matrix.flags.writeable = False
        object.__setattr__(self, "_effectiveness_matrix", matrix)

    def actuator_ids(self) -> tuple[str, ...]:
        """Return actuator ids in declaration order (no semantic meaning)."""
        return tuple(spec.actuator_id for spec in self.actuators)

    def effectiveness_matrix(self) -> FloatArray:
        """Return the read-only (3, n) body [X, Y, N] effectiveness matrix."""
        return self._effectiveness_matrix

    def verify_integrity(self) -> bool:
        """Verify layout content SHA-256 against metadata hash."""
        cached = getattr(self, "_integrity_verified", None)
        if cached is not None:
            return cached
        valid = actuator_layout_content_sha256(self.actuators) == self.metadata.sha256
        object.__setattr__(self, "_integrity_verified", valid)
        return valid


@dataclass(frozen=True)
class AllocatorSolution:
    """Immutable per-tick allocator output with visible feasibility (AC2).

    requested/achieved/residual are strictly 3DOF body loads [X, Y, N]; the
    roll-moment channel is never present (RA-12, VR-16).
    """

    requested: VesselLoad
    achieved: VesselLoad
    residual: VesselLoad
    actuator_commands_n: Mapping[str, float]
    actuator_health: Mapping[str, float]
    active_constraints: tuple[tuple[str, str], ...]
    saturated: bool
    degraded: bool
    degraded_actuators: tuple[str, ...]
    layout_asset_id: str
    tick: int
    time_s: float

    def __post_init__(self) -> None:
        """Freeze id-keyed mappings and constraint records."""
        object.__setattr__(self, "actuator_commands_n", MappingProxyType(dict(self.actuator_commands_n)))
        object.__setattr__(self, "actuator_health", MappingProxyType(dict(self.actuator_health)))
        object.__setattr__(self, "active_constraints", tuple(self.active_constraints))
        object.__setattr__(self, "degraded_actuators", tuple(self.degraded_actuators))

    def to_achieved_generalized_load(self, source: str = "DATA_DRIVEN_ALLOCATOR") -> AchievedGeneralizedLoad:
        """Project the solution into the achieved-load diagnostic contract (TS-20, VR-15)."""
        return AchievedGeneralizedLoad.from_vessel_load(
            self.achieved,
            status=AchievedLoadStatus.AVAILABLE,
            saturated=self.saturated,
            source=source,
            tick=self.tick,
            time_s=self.time_s,
            details={
                "layout_asset_id": self.layout_asset_id,
                "requested": {
                    "surge_n": self.requested.surge_n,
                    "sway_n": self.requested.sway_n,
                    "yaw_nm": self.requested.yaw_nm,
                },
                "residual": {
                    "surge_n": self.residual.surge_n,
                    "sway_n": self.residual.sway_n,
                    "yaw_nm": self.residual.yaw_nm,
                },
                "actuator_commands_n": dict(self.actuator_commands_n),
                "actuator_health": dict(self.actuator_health),
                "active_constraints": self.active_constraints,
                "saturated": self.saturated,
                "degraded": self.degraded,
                "degraded_actuators": self.degraded_actuators,
            },
        )


@dataclass(frozen=True)
class DataDrivenAllocatorSnapshot:
    """Immutable allocator state: per-actuator health keyed by actuator id."""

    health: Mapping[str, float]

    def __post_init__(self) -> None:
        """Freeze the health mapping."""
        object.__setattr__(self, "health", MappingProxyType(dict(self.health)))


class DataDrivenAllocator:
    """Deterministic pseudo-inverse allocator bound to one actuator layout asset.

    Allocates a strictly 3DOF [X, Y, N] generalized-load request through the
    asset-derived effectiveness matrix scaled by current per-actuator health,
    clips commands to asset-declared per-actuator limits, and reports requested,
    achieved, residual, active constraints, saturation, and degraded status
    explicitly (no hidden clipping). Minimum-norm least squares is used, so the
    result depends only on the id-keyed layout data, never on declaration order.
    """

    def __init__(self, asset: ActuatorLayoutAsset) -> None:
        """Bind and integrity-verify one actuator layout asset."""
        if not isinstance(asset, ActuatorLayoutAsset):
            raise TypeError(f"asset must be ActuatorLayoutAsset, got {type(asset).__name__}")
        if not asset.verify_integrity():
            raise AssetIntegrityError(f"Integrity check failed for actuator layout asset: {asset.metadata.asset_id}")
        self._asset = asset
        self._ids = asset.actuator_ids()
        self._matrix = asset.effectiveness_matrix()
        self._min_limits = np.fromiter(
            (spec.min_force_n for spec in asset.actuators), dtype=np.float64, count=len(asset.actuators)
        )
        self._max_limits = np.fromiter(
            (spec.max_force_n for spec in asset.actuators), dtype=np.float64, count=len(asset.actuators)
        )
        self._health: dict[str, float] = {spec.actuator_id: spec.initial_health for spec in asset.actuators}

    @property
    def asset_id(self) -> str:
        """Return the bound layout asset id."""
        return self._asset.metadata.asset_id

    @property
    def supported_tasks(self) -> frozenset[ControlTask]:
        """Return allocator task capability: every generalized-load request is resolvable."""
        return frozenset(ControlTask)

    def reset(self) -> None:
        """Restore health to asset-declared initial values (deterministic)."""
        self._health = {spec.actuator_id: spec.initial_health for spec in self._asset.actuators}

    def actuator_health(self) -> Mapping[str, float]:
        """Return current per-actuator health keyed by actuator id."""
        return MappingProxyType(dict(self._health))

    def set_actuator_health(self, actuator_id: str, health: float) -> None:
        """Explicitly set one actuator's health scale in [0, 1] (fault injection seam)."""
        if actuator_id not in self._health:
            raise ValueError(f"unknown actuator id '{actuator_id}' for layout {self.asset_id}")
        if isinstance(health, bool) or not isinstance(health, (int, float)) or not math.isfinite(health):
            raise TypeError(f"health must be a finite float, got {type(health).__name__}")
        value = float(health)
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"health must be within [0, 1], got {value}")
        self._health[actuator_id] = value

    def snapshot(self) -> DataDrivenAllocatorSnapshot:
        """Capture allocator-owned state."""
        return DataDrivenAllocatorSnapshot(health=dict(self._health))

    def restore(self, snapshot: DataDrivenAllocatorSnapshot) -> None:
        """Restore allocator-owned state for the same bound layout."""
        if set(snapshot.health) != set(self._health):
            raise ValueError(
                f"allocator snapshot actuator ids mismatch for layout {self.asset_id}"
            )
        self._health = {actuator_id: float(snapshot.health[actuator_id]) for actuator_id in self._ids}

    @classmethod
    def from_params(cls, params: Mapping[str, Any]) -> DataDrivenAllocator:
        """Construct a DataDrivenAllocator from normalized module parameters."""
        layout_id = params.get("layout_asset_id")
        if not isinstance(layout_id, str) or not layout_id:
            raise ValueError("layout_asset_id is required for data_driven_allocator")
        if layout_id not in KNOWN_ACTUATOR_LAYOUT_ASSETS:
            raise ValueError(
                f"unknown actuator layout asset id: {layout_id} (known: {sorted(KNOWN_ACTUATOR_LAYOUT_ASSETS)})"
            )
        return cls(KNOWN_ACTUATOR_LAYOUT_ASSETS[layout_id])

    def allocate(self, requested: VesselLoad, tick: int = 0, time_s: float = 0.0) -> AllocatorSolution:
        """Allocate a 3DOF generalized-load request; feasibility is fully visible in the output."""
        if not isinstance(requested, VesselLoad):
            raise TypeError(f"requested must be VesselLoad, got {type(requested).__name__}")
        if requested.roll_nm != 0.0:
            raise ValueError(
                f"roll is unactuated; allocator task space is strictly [X, Y, N]; requested roll_nm "
                f"({requested.roll_nm}) is forbidden (RA-12, VR-16)"
            )
        tau = np.array([requested.surge_n, requested.sway_n, requested.yaw_nm], dtype=np.float64)
        health_vector = np.fromiter(
            (self._health[actuator_id] for actuator_id in self._ids), dtype=np.float64, count=len(self._ids)
        )
        effective_matrix = self._matrix * health_vector
        raw_commands, _, _, _ = np.linalg.lstsq(effective_matrix, tau, rcond=None)
        clipped_commands = np.clip(raw_commands, self._min_limits, self._max_limits)

        active_constraints: list[tuple[str, str]] = []
        for i, actuator_id in enumerate(self._ids):
            if raw_commands[i] > self._max_limits[i]:
                active_constraints.append((actuator_id, "max_force_n"))
            elif raw_commands[i] < self._min_limits[i]:
                active_constraints.append((actuator_id, "min_force_n"))
        achieved_vector = effective_matrix @ clipped_commands
        residual_vector = tau - achieved_vector

        degraded_actuators = tuple(
            sorted(actuator_id for actuator_id, value in self._health.items() if value < 1.0)
        )
        return AllocatorSolution(
            requested=requested,
            achieved=VesselLoad(
                surge_n=float(achieved_vector[0]),
                sway_n=float(achieved_vector[1]),
                yaw_nm=float(achieved_vector[2]),
                roll_nm=0.0,
            ),
            residual=VesselLoad(
                surge_n=float(residual_vector[0]),
                sway_n=float(residual_vector[1]),
                yaw_nm=float(residual_vector[2]),
                roll_nm=0.0,
            ),
            actuator_commands_n={actuator_id: float(clipped_commands[i]) for i, actuator_id in enumerate(self._ids)},
            actuator_health=dict(self._health),
            active_constraints=tuple(sorted(active_constraints)),
            saturated=bool(active_constraints),
            degraded=bool(degraded_actuators),
            degraded_actuators=degraded_actuators,
            layout_asset_id=self.asset_id,
            tick=tick,
            time_s=time_s,
        )


_TRIPLE_ACTUATORS: tuple[ActuatorSpec, ...] = (
    ActuatorSpec(
        actuator_id="main_thruster",
        kind="main",
        position_body_m=(0.0, 0.0),
        orientation_body_rad=0.0,
        min_force_n=-8.0e5,
        max_force_n=8.0e5,
    ),
    ActuatorSpec(
        actuator_id="bow_tunnel_thruster",
        kind="tunnel_thruster",
        position_body_m=(40.0, 0.0),
        orientation_body_rad=0.5 * math.pi,
        min_force_n=-6.0e5,
        max_force_n=6.0e5,
    ),
    ActuatorSpec(
        actuator_id="stern_tunnel_thruster",
        kind="tunnel_thruster",
        position_body_m=(-10.0, 0.0),
        orientation_body_rad=0.5 * math.pi,
        min_force_n=-6.0e5,
        max_force_n=6.0e5,
    ),
)

_QUAD_DIAGONAL_ACTUATORS: tuple[ActuatorSpec, ...] = (
    ActuatorSpec(
        actuator_id="bow_port_diagonal",
        kind="fixed_azimuth",
        position_body_m=(30.0, 3.0),
        orientation_body_rad=0.25 * math.pi,
        min_force_n=-8.0e5,
        max_force_n=8.0e5,
    ),
    ActuatorSpec(
        actuator_id="bow_starboard_diagonal",
        kind="fixed_azimuth",
        position_body_m=(30.0, -3.0),
        orientation_body_rad=0.75 * math.pi,
        min_force_n=-8.0e5,
        max_force_n=8.0e5,
    ),
    ActuatorSpec(
        actuator_id="stern_starboard_diagonal",
        kind="fixed_azimuth",
        position_body_m=(-30.0, -3.0),
        orientation_body_rad=1.25 * math.pi,
        min_force_n=-8.0e5,
        max_force_n=8.0e5,
    ),
    ActuatorSpec(
        actuator_id="stern_port_diagonal",
        kind="fixed_azimuth",
        position_body_m=(-30.0, 3.0),
        orientation_body_rad=1.75 * math.pi,
        min_force_n=-8.0e5,
        max_force_n=8.0e5,
    ),
)

_MAIN_ONLY_ACTUATORS: tuple[ActuatorSpec, ...] = (
    ActuatorSpec(
        actuator_id="main_thruster",
        kind="main",
        position_body_m=(0.0, 0.0),
        orientation_body_rad=0.0,
        min_force_n=-8.0e5,
        max_force_n=8.0e5,
    ),
)


def _layout_asset(asset_id: str, actuators: tuple[ActuatorSpec, ...], basis: str) -> ActuatorLayoutAsset:
    """Construct a mock-trust layout asset with content-derived integrity hash."""
    return ActuatorLayoutAsset(
        metadata=AssetMetadata(
            asset_id=asset_id,
            asset_type="actuator_layout",
            trust_level=AssetTrustLevel.MOCK,
            source_type="mock",
            sha256=actuator_layout_content_sha256(actuators),
            license="MIT",
            applicability_domain=ApplicabilityDomain(),
            provenance={"standard_basis": basis, "created_by": "modular_gnc"},
            uncertainty={},
        ),
        actuators=actuators,
    )


DEFAULT_TRIPLE_ACTUATOR_LAYOUT_V1: ActuatorLayoutAsset = _layout_asset(
    "default_triple_actuator_layout_v1",
    _TRIPLE_ACTUATORS,
    "Synthetic main + bow/stern tunnel thruster layout scaffold",
)
QUAD_DIAGONAL_ACTUATOR_LAYOUT_V1: ActuatorLayoutAsset = _layout_asset(
    "quad_diagonal_actuator_layout_v1",
    _QUAD_DIAGONAL_ACTUATORS,
    "Synthetic four fixed-diagonal actuator layout scaffold",
)
MAIN_ONLY_ACTUATOR_LAYOUT_V1: ActuatorLayoutAsset = _layout_asset(
    "main_only_actuator_layout_v1",
    _MAIN_ONLY_ACTUATORS,
    "Synthetic single main thruster underactuated layout scaffold",
)

KNOWN_ACTUATOR_LAYOUT_ASSETS: Mapping[str, ActuatorLayoutAsset] = MappingProxyType(
    {
        "default_triple_actuator_layout_v1": DEFAULT_TRIPLE_ACTUATOR_LAYOUT_V1,
        "quad_diagonal_actuator_layout_v1": QUAD_DIAGONAL_ACTUATOR_LAYOUT_V1,
        "main_only_actuator_layout_v1": MAIN_ONLY_ACTUATOR_LAYOUT_V1,
    }
)
