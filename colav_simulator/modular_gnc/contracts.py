"""Immutable typed values for modular GNC facade and module seams."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]


class NavigationSource(str, Enum):
    """Origin of navigation state consumed by modular GNC."""

    TRUTH_PROJECTION = "TRUTH_PROJECTION"
    ESTIMATE = "ESTIMATE"


class ControlTask(str, Enum):
    """Explicit motion-control task."""

    TRANSIT = "TRANSIT"
    POSE_HOLD = "POSE_HOLD"
    CONTROLLED_STOP = "CONTROLLED_STOP"
    MANUAL_LOAD = "MANUAL_LOAD"


class PlantInputSemantics(str, Enum):
    """Input domain accepted by a vessel plant."""

    GENERALIZED_FORCE = "GENERALIZED_FORCE"
    KINEMATIC_REFERENCE = "KINEMATIC_REFERENCE"


class FailureCode(str, Enum):
    """Stable facade failure codes."""

    INVALID_INPUT = "INVALID_INPUT"
    NONFINITE_INPUT = "NONFINITE_INPUT"
    DUPLICATE_INPUT = "DUPLICATE_INPUT"
    STALE_INPUT = "STALE_INPUT"
    OUT_OF_ORDER_INPUT = "OUT_OF_ORDER_INPUT"
    EXPIRED_ROUTE = "EXPIRED_ROUTE"
    REJECTED_ROUTE = "REJECTED_ROUTE"
    CAPABILITY_MISMATCH = "CAPABILITY_MISMATCH"
    DEPENDENCY_UNAVAILABLE = "DEPENDENCY_UNAVAILABLE"
    MODULE_FAILURE = "MODULE_FAILURE"
    OUT_OF_DOMAIN = "OUT_OF_DOMAIN"


def _finite_scalar(name: str, value: float) -> float:
    result = float(value)
    if not np.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def immutable_float64_array(name: str, values: Any, shape: tuple[int, ...]) -> FloatArray:
    """Validate strict shape and return owned read-only float64 array."""
    array = np.array(values, dtype=np.float64, copy=True)
    if array.shape != shape:
        raise ValueError(f"{name} must have shape {shape}, got {array.shape}")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} must contain only finite values")
    array.flags.writeable = False
    return array


@dataclass(frozen=True)
class NavigationState:
    """Stable planar navigation view in NE/body FRD, SI, right-positive signs."""

    north_m: float
    east_m: float
    heading_rad: float
    surge_mps: float
    sway_mps: float
    yaw_rate_radps: float
    source: NavigationSource = NavigationSource.TRUTH_PROJECTION
    frame: str = field(default="NE/body-forward-starboard-down", init=False)
    units: str = field(default="m,rad,m/s,rad/s", init=False)
    heading_positive: str = field(default="right", init=False)

    def __post_init__(self) -> None:
        """Validate finite scalar fields and coerce navigation source."""
        for name in ("north_m", "east_m", "heading_rad", "surge_mps", "sway_mps", "yaw_rate_radps"):
            object.__setattr__(self, name, _finite_scalar(name, getattr(self, name)))
        object.__setattr__(self, "source", NavigationSource(self.source))

    def as_array(self) -> FloatArray:
        """Return six-element legacy-compatible state copy."""
        return np.array(
            [self.north_m, self.east_m, self.heading_rad, self.surge_mps, self.sway_mps, self.yaw_rate_radps],
            dtype=np.float64,
        )

    @property
    def course_rad(self) -> float:
        """Return course over ground, preserving heading at near-zero speed."""
        if abs(self.surge_mps) < 1e-12 and abs(self.sway_mps) < 1e-12:
            return self.heading_rad
        return float(self.heading_rad + np.arctan2(self.sway_mps, self.surge_mps))

    @property
    def speed_mps(self) -> float:
        """Return speed over ground."""
        return float(np.hypot(self.surge_mps, self.sway_mps))


@dataclass(frozen=True, eq=False)
class PlantState:
    """Complete immutable plant truth state for declared capabilities."""

    values: FloatArray
    capabilities: frozenset[str]
    input_semantics: PlantInputSemantics = PlantInputSemantics.GENERALIZED_FORCE

    def __post_init__(self) -> None:
        """Validate state against declared plant capability."""
        expected_shape = (8,) if "ROLL_4DOF" in self.capabilities else (6,)
        object.__setattr__(self, "values", immutable_float64_array("PlantState.values", self.values, expected_shape))
        object.__setattr__(self, "capabilities", frozenset(self.capabilities))

    def __eq__(self, other: object) -> bool:
        """Compare state values and capabilities."""
        return (
            isinstance(other, PlantState)
            and self.capabilities == other.capabilities
            and self.input_semantics is other.input_semantics
            and np.array_equal(self.values, other.values)
        )

    __hash__ = None


@dataclass(frozen=True, eq=False)
class DirectReference:
    """Legacy nine-element controller reference latched at one simulation tick."""

    values: FloatArray
    latched_tick: int
    task: ControlTask = ControlTask.TRANSIT

    def __post_init__(self) -> None:
        """Validate tick and strict legacy reference shape."""
        if self.latched_tick < 0:
            raise ValueError("latched_tick must be non-negative")
        object.__setattr__(self, "values", immutable_float64_array("DirectReference.values", self.values, (9,)))

    def __eq__(self, other: object) -> bool:
        """Compare reference values, tick, and task."""
        return (
            isinstance(other, DirectReference)
            and self.latched_tick == other.latched_tick
            and self.task is other.task
            and np.array_equal(self.values, other.values)
        )

    __hash__ = None


@dataclass(frozen=True, eq=False)
class TrackedRoute:
    """Accepted, revisioned route with explicit validity interval."""

    route_id: str
    revision: int
    accepted: bool
    valid_from_tick: int
    valid_until_tick: int
    waypoints_ne_m: FloatArray
    speed_mps: FloatArray
    task: ControlTask

    def __post_init__(self) -> None:
        """Validate route identity, validity, geometry, and speed profile."""
        if not self.route_id:
            raise ValueError("route_id must not be empty")
        if self.revision < 0 or self.valid_from_tick < 0 or self.valid_until_tick < self.valid_from_tick:
            raise ValueError("route revision and validity ticks are invalid")
        waypoints = np.array(self.waypoints_ne_m, dtype=np.float64, copy=True)
        if waypoints.ndim != 2 or waypoints.shape[0] != 2 or waypoints.shape[1] < 2:
            raise ValueError("waypoints_ne_m must have shape (2, N), N >= 2")
        if not np.isfinite(waypoints).all():
            raise ValueError("waypoints_ne_m must contain only finite values")
        speeds = immutable_float64_array("speed_mps", self.speed_mps, (waypoints.shape[1],))
        waypoints.flags.writeable = False
        object.__setattr__(self, "waypoints_ne_m", waypoints)
        object.__setattr__(self, "speed_mps", speeds)

    def __eq__(self, other: object) -> bool:
        """Compare complete route contract."""
        return (
            isinstance(other, TrackedRoute)
            and self.route_id == other.route_id
            and self.revision == other.revision
            and self.accepted is other.accepted
            and self.valid_from_tick == other.valid_from_tick
            and self.valid_until_tick == other.valid_until_tick
            and self.task is other.task
            and np.array_equal(self.waypoints_ne_m, other.waypoints_ne_m)
            and np.array_equal(self.speed_mps, other.speed_mps)
        )

    __hash__ = None


@dataclass(frozen=True)
class CommandInput:
    """Per-tick discriminated command union: route, direct reference, or none."""

    tick: int
    direct_reference: DirectReference | None = None
    tracked_route: TrackedRoute | None = None

    def __post_init__(self) -> None:
        """Validate tick and exclusive command authority."""
        if self.tick < 0:
            raise ValueError("tick must be non-negative")
        if self.direct_reference is not None and self.tracked_route is not None:
            raise ValueError("direct reference and tracked route are mutually exclusive")

    @classmethod
    def none(cls, tick: int) -> CommandInput:
        """Construct no-new-authority command for tick."""
        return cls(tick=tick)

    @classmethod
    def direct(cls, tick: int, reference: DirectReference) -> CommandInput:
        """Construct direct-reference command for tick."""
        return cls(tick=tick, direct_reference=reference)

    @classmethod
    def route(cls, tick: int, route: TrackedRoute) -> CommandInput:
        """Construct tracked-route command for tick."""
        return cls(tick=tick, tracked_route=route)

    @property
    def authority(self) -> str:
        """Return discriminant string."""
        if self.direct_reference is not None:
            return "DIRECT_REFERENCE"
        if self.tracked_route is not None:
            return "TRACKED_ROUTE"
        return "NONE"


@dataclass(frozen=True)
class FacadeFailure:
    """Structured modular facade failure."""

    code: FailureCode
    message: str
    phase: str
    tick: int
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate failure tick and freeze details."""
        if self.tick < 0:
            raise ValueError("tick must be non-negative")
        object.__setattr__(self, "details", MappingProxyType(dict(self.details)))


@dataclass(frozen=True)
class StackOutput:
    """Immutable facade output."""

    tick: int
    navigation: NavigationState
    plant: PlantState
    applied_reference: DirectReference | None
    failure: FacadeFailure | None = None


@dataclass(frozen=True)
class StackSnapshot:
    """Complete facade-local restoration value."""

    schema_version: str
    config_hash: str
    tick: int
    seed: int
    module_snapshots: tuple[Any, ...]
    held_command: DirectReference | TrackedRoute | None

    def __post_init__(self) -> None:
        """Validate pinned snapshot schema and identity."""
        if self.schema_version != "modular-ship-stack.snapshot.v1":
            raise ValueError("unsupported snapshot schema_version")
        if len(self.config_hash) != 64:
            raise ValueError("config_hash must be SHA-256 hex")
        if self.tick < 0:
            raise ValueError("tick must be non-negative")
        object.__setattr__(self, "module_snapshots", tuple(self.module_snapshots))
