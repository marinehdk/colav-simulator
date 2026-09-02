"""Immutable typed values for modular GNC facade and module seams."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]


def _deep_freeze(value: Any) -> Any:
    """Recursively freeze nested mappings, sequences, and sets."""
    if isinstance(value, Mapping):
        return MappingProxyType({key: _deep_freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_deep_freeze(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_deep_freeze(item) for item in value)
    return value


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
    REFERENCE_CHI_U = "REFERENCE_CHI_U"

    def canonical(self) -> PlantInputSemantics:
        """Return canonical semantics, aliasing legacy KINEMATIC_REFERENCE to REFERENCE_CHI_U."""
        if self is PlantInputSemantics.KINEMATIC_REFERENCE:
            return PlantInputSemantics.REFERENCE_CHI_U
        return self


def canonicalize_plant_input_semantics(semantics: PlantInputSemantics | str) -> PlantInputSemantics:
    """Return canonical plant input semantics, aliasing legacy KINEMATIC_REFERENCE to REFERENCE_CHI_U."""
    return PlantInputSemantics(semantics).canonical()


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


class CurrentReference(str, Enum):
    """Reference depth datum for ocean current velocity."""

    SURFACE = "surface"
    DEPTH_AVERAGED = "depth_averaged"


class EnvironmentStatus(str, Enum):
    """Availability status of environment sources or observations."""

    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"


class AssetTrustLevel(str, Enum):
    """Four-tier trust level for hydrodynamic and environmental assets (TS-23, VR-10)."""

    MOCK = "mock"
    INFERRED = "inferred"
    CALIBRATED = "calibrated"
    VALIDATED_FOR_VESSEL = "validated_for_vessel"


class OutOfDomainError(ValueError):
    """Raised when an environmental or hydrodynamic input is outside asset applicability domain (TS-17, VR-10)."""


class AssetMissingError(RuntimeError):
    """Raised when a required environmental or hydrodynamic asset is missing (TS-17, VR-10)."""


class AssetIntegrityError(ValueError):
    """Raised when an asset content hash verification fails (TS-27, VR-10)."""


class CurrentStrategy(str, Enum):
    """Exclusive strategy for ocean current disturbance handling (spec L105, VR-09)."""

    NONE = "none"
    CURRENT_RELATIVE_DAMPING = "current_relative_damping"
    EXTERNAL_CURRENT_LOAD = "external_current_load"


class WaveLoadMode(str, Enum):
    """Explicit wave load calculation mode (VR-09, VR-10, spec L106)."""

    OFF = "off"
    FIRST_ORDER = "first_order"
    MEAN_DRIFT = "mean_drift"
    BOTH = "both"


class MeanDriftModel(str, Enum):
    """Explicit second-order wave mean-drift model formulation (VR-09, VR-10)."""

    OFF = "off"
    DIAGONAL_AI2 = "diagonal_ai2"
    FULL_PAIR_QTF = "full_pair_qtf"


def _non_empty_str(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def _validate_sha256(name: str, value: Any) -> str:
    if not isinstance(value, str) or len(value) != 64 or not all(c in "0123456789abcdefABCDEF" for c in value):
        raise ValueError(f"{name} must be a 64-character hex string")
    return value.lower()


def _finite_scalar(name: str, value: float) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{name} must be a float, got bool")
    if not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a float, got {type(value).__name__}")
    result = float(value)
    if not np.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _non_bool_int(name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer, got {type(value).__name__}")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return int(value)


@dataclass(frozen=True)
class WindSample:
    """Immutable raw wind field sample in NE world to-direction."""

    velocity_ne: tuple[float, float]
    reference_height_m: float = 10.0
    frame: str = field(default="NE-to", init=False)
    units: str = field(default="m/s,m", init=False)

    def __post_init__(self) -> None:
        """Validate finite components, positive reference height, and freeze."""
        if len(self.velocity_ne) != 2:
            raise ValueError("velocity_ne must have 2 components (vn, ve)")
        vn = _finite_scalar("velocity_ne[0]", self.velocity_ne[0])
        ve = _finite_scalar("velocity_ne[1]", self.velocity_ne[1])
        ref_h = _finite_scalar("reference_height_m", self.reference_height_m)
        if ref_h <= 0.0:
            raise ValueError("reference_height_m must be positive")
        object.__setattr__(self, "velocity_ne", (vn, ve))
        object.__setattr__(self, "reference_height_m", ref_h)

    @property
    def speed_mps(self) -> float:
        """Return wind speed magnitude in m/s."""
        return float(math.hypot(self.velocity_ne[0], self.velocity_ne[1]))

    @property
    def direction_to_rad(self) -> float:
        """Return compass to-direction angle in rad [0, 2*pi)."""
        return float(math.atan2(self.velocity_ne[1], self.velocity_ne[0]) % (2.0 * math.pi))


@dataclass(frozen=True)
class CurrentSample:
    """Immutable raw ocean current field sample in NE world to-direction."""

    velocity_ne: tuple[float, float]
    reference: CurrentReference = CurrentReference.SURFACE
    frame: str = field(default="NE-to", init=False)
    units: str = field(default="m/s", init=False)

    def __post_init__(self) -> None:
        """Validate finite components, coerce reference datum, and freeze."""
        if len(self.velocity_ne) != 2:
            raise ValueError("velocity_ne must have 2 components (vn, ve)")
        vn = _finite_scalar("velocity_ne[0]", self.velocity_ne[0])
        ve = _finite_scalar("velocity_ne[1]", self.velocity_ne[1])
        object.__setattr__(self, "velocity_ne", (vn, ve))
        object.__setattr__(self, "reference", CurrentReference(self.reference))

    @property
    def speed_mps(self) -> float:
        """Return current speed magnitude in m/s."""
        return float(math.hypot(self.velocity_ne[0], self.velocity_ne[1]))

    @property
    def direction_to_rad(self) -> float:
        """Return compass to-direction angle in rad [0, 2*pi)."""
        return float(math.atan2(self.velocity_ne[1], self.velocity_ne[0]) % (2.0 * math.pi))


@dataclass(frozen=True)
class WaveComponent:
    """Immutable regular harmonic wave component."""

    amplitude_m: float
    omega_radps: float
    phase_rad: float
    direction_to_rad: float

    def __post_init__(self) -> None:
        """Validate non-negative amplitude, positive frequency, and finite angles."""
        amp = _finite_scalar("amplitude_m", self.amplitude_m)
        if amp < 0.0:
            raise ValueError("amplitude_m must be non-negative")
        omega = _finite_scalar("omega_radps", self.omega_radps)
        if omega <= 0.0:
            raise ValueError("omega_radps must be positive")
        phase = _finite_scalar("phase_rad", self.phase_rad)
        direction = _finite_scalar("direction_to_rad", self.direction_to_rad)
        object.__setattr__(self, "amplitude_m", amp)
        object.__setattr__(self, "omega_radps", omega)
        object.__setattr__(self, "phase_rad", phase)
        object.__setattr__(self, "direction_to_rad", direction % (2.0 * math.pi))


@dataclass(frozen=True)
class WaveComponentArrays:
    """Contiguous immutable float64 arrays for wave component batches."""

    amplitudes: FloatArray
    omegas: FloatArray
    phases: FloatArray
    directions: FloatArray
    omega_sq: FloatArray
    amp_sq: FloatArray


def build_wave_component_arrays(
    components: tuple[WaveComponent, ...] | Sequence[WaveComponent],
) -> WaveComponentArrays | None:
    """Build contiguous immutable float64 component arrays from sequence of WaveComponent."""
    if not components:
        return None
    n = len(components)
    amps = np.fromiter((c.amplitude_m for c in components), dtype=np.float64, count=n)
    omegas = np.fromiter((c.omega_radps for c in components), dtype=np.float64, count=n)
    phases = np.fromiter((c.phase_rad for c in components), dtype=np.float64, count=n)
    dirs = np.fromiter((c.direction_to_rad for c in components), dtype=np.float64, count=n)
    omega_sq = omegas * omegas
    amp_sq = amps * amps
    amps.flags.writeable = False
    omegas.flags.writeable = False
    phases.flags.writeable = False
    dirs.flags.writeable = False
    omega_sq.flags.writeable = False
    amp_sq.flags.writeable = False
    return WaveComponentArrays(amps, omegas, phases, dirs, omega_sq, amp_sq)


@dataclass(frozen=True)
class WaveFieldSample:
    """Immutable raw wave field description."""

    significant_height_m: float
    peak_period_s: float
    direction_to_rad: float
    components: tuple[WaveComponent, ...] = ()

    def __post_init__(self) -> None:
        """Validate non-negative Hs, positive Tp, and freeze components."""
        hs = _finite_scalar("significant_height_m", self.significant_height_m)
        if hs < 0.0:
            raise ValueError("significant_height_m must be non-negative")
        tp = _finite_scalar("peak_period_s", self.peak_period_s)
        if tp <= 0.0:
            raise ValueError("peak_period_s must be positive")
        dir_rad = _finite_scalar("direction_to_rad", self.direction_to_rad)
        if not isinstance(self.components, (list, tuple)):
            raise TypeError("components must be a sequence of WaveComponent")
        for i, comp in enumerate(self.components):
            if not isinstance(comp, WaveComponent):
                raise TypeError(f"components[{i}] must be WaveComponent, got {type(comp).__name__}")
        object.__setattr__(self, "significant_height_m", hs)
        object.__setattr__(self, "peak_period_s", tp)
        object.__setattr__(self, "direction_to_rad", dir_rad % (2.0 * math.pi))
        object.__setattr__(self, "components", tuple(self.components))

    @property
    def component_arrays(self) -> WaveComponentArrays | None:
        """Return cached or lazily constructed contiguous immutable component arrays."""
        cached = getattr(self, "_cached_component_arrays", None)
        if cached is None and self.components:
            cached = build_wave_component_arrays(self.components)
            try:
                object.__setattr__(self, "_cached_component_arrays", cached)
            except Exception:
                pass
        return cached


@dataclass(frozen=True)
class MeanDriftSourceSample:
    """Immutable vessel-independent wave energy and directional reference for #51 mean-drift load model.

    Explicitly contains NO vessel forces or moments (VR-49-01, ALT-49-01).
    """

    components: tuple[WaveComponent, ...]
    directional_spread_rad: float = 0.0

    def __post_init__(self) -> None:
        """Validate non-negative directional spread and freeze components."""
        spread = _finite_scalar("directional_spread_rad", self.directional_spread_rad)
        if spread < 0.0:
            raise ValueError("directional_spread_rad must be non-negative")
        if not isinstance(self.components, (list, tuple)):
            raise TypeError("components must be a sequence of WaveComponent")
        for i, comp in enumerate(self.components):
            if not isinstance(comp, WaveComponent):
                raise TypeError(f"components[{i}] must be WaveComponent, got {type(comp).__name__}")
        object.__setattr__(self, "components", tuple(self.components))
        object.__setattr__(self, "directional_spread_rad", spread)

    @property
    def component_arrays(self) -> WaveComponentArrays | None:
        """Return cached or lazily constructed contiguous immutable component arrays."""
        cached = getattr(self, "_cached_component_arrays", None)
        if cached is None and self.components:
            cached = build_wave_component_arrays(self.components)
            try:
                object.__setattr__(self, "_cached_component_arrays", cached)
            except Exception:
                pass
        return cached


@dataclass(frozen=True)
class EnvironmentTruth:
    """Complete immutable true environment state at query time and position."""

    wind: WindSample
    current: CurrentSample
    wave: WaveFieldSample
    mean_drift: MeanDriftSourceSample
    time_s: float = 0.0
    tick: int = 0
    stage_offset_s: float = 0.0

    def __post_init__(self) -> None:
        """Validate time, tick, child types, and non-negative stage offset."""
        if not isinstance(self.wind, WindSample):
            raise TypeError(f"wind must be WindSample, got {type(self.wind).__name__}")
        if not isinstance(self.current, CurrentSample):
            raise TypeError(f"current must be CurrentSample, got {type(self.current).__name__}")
        if not isinstance(self.wave, WaveFieldSample):
            raise TypeError(f"wave must be WaveFieldSample, got {type(self.wave).__name__}")
        if not isinstance(self.mean_drift, MeanDriftSourceSample):
            raise TypeError(f"mean_drift must be MeanDriftSourceSample, got {type(self.mean_drift).__name__}")
        object.__setattr__(self, "time_s", _finite_scalar("time_s", self.time_s))
        object.__setattr__(self, "tick", _non_bool_int("tick", self.tick))
        offset = _finite_scalar("stage_offset_s", self.stage_offset_s)
        if offset < 0.0:
            raise ValueError("stage_offset_s must be non-negative")
        object.__setattr__(self, "stage_offset_s", offset)


@dataclass(frozen=True)
class EnvironmentObservation:
    """Immutable observed or estimated environment state for GNC guidance/control."""

    wind: WindSample | None = None
    current: CurrentSample | None = None
    wave: WaveFieldSample | None = None
    mean_drift: MeanDriftSourceSample | None = None
    source: str = "PASS_THROUGH"
    quality: float = 1.0
    age_s: float = 0.0
    status: EnvironmentStatus = EnvironmentStatus.AVAILABLE
    time_s: float = 0.0
    tick: int = 0

    def __post_init__(self) -> None:
        """Validate metadata, child types, coerce status enum, and freeze."""
        if self.wind is not None and not isinstance(self.wind, WindSample):
            raise TypeError(f"wind must be WindSample or None, got {type(self.wind).__name__}")
        if self.current is not None and not isinstance(self.current, CurrentSample):
            raise TypeError(f"current must be CurrentSample or None, got {type(self.current).__name__}")
        if self.wave is not None and not isinstance(self.wave, WaveFieldSample):
            raise TypeError(f"wave must be WaveFieldSample or None, got {type(self.wave).__name__}")
        if self.mean_drift is not None and not isinstance(self.mean_drift, MeanDriftSourceSample):
            raise TypeError(f"mean_drift must be MeanDriftSourceSample or None, got {type(self.mean_drift).__name__}")
        if not isinstance(self.source, str) or not self.source:
            raise ValueError("source must be a non-empty string")
        object.__setattr__(self, "source", self.source)
        object.__setattr__(self, "quality", _finite_scalar("quality", self.quality))
        age = _finite_scalar("age_s", self.age_s)
        if age < 0.0:
            raise ValueError("age_s must be non-negative")
        object.__setattr__(self, "age_s", age)
        object.__setattr__(self, "status", EnvironmentStatus(self.status))
        object.__setattr__(self, "time_s", _finite_scalar("time_s", self.time_s))
        object.__setattr__(self, "tick", _non_bool_int("tick", self.tick))

    @classmethod
    def from_truth(
        cls,
        truth: EnvironmentTruth,
        source: str = "PASS_THROUGH",
        quality: float = 1.0,
    ) -> EnvironmentObservation:
        """Construct explicit pass-through observation from truth with type separation."""
        if not isinstance(truth, EnvironmentTruth):
            raise TypeError(f"truth must be EnvironmentTruth, got {type(truth).__name__}")
        return cls(
            wind=truth.wind,
            current=truth.current,
            wave=truth.wave,
            mean_drift=truth.mean_drift,
            source=source,
            quality=quality,
            age_s=0.0,
            status=EnvironmentStatus.AVAILABLE,
            time_s=truth.time_s,
            tick=truth.tick,
        )

    @classmethod
    def unavailable(
        cls,
        source: str = "UNAVAILABLE",
        tick: int = 0,
        time_s: float = 0.0,
    ) -> EnvironmentObservation:
        """Construct explicit unavailable observation."""
        return cls(
            wind=None,
            current=None,
            wave=None,
            mean_drift=None,
            source=source,
            quality=0.0,
            age_s=0.0,
            status=EnvironmentStatus.UNAVAILABLE,
            time_s=time_s,
            tick=tick,
        )


@dataclass(frozen=True)
class ApplicabilityDomain:
    """Declared validity domain ranges for environmental and hydrodynamic assets (TS-23, VR-10)."""

    heading_range_deg: tuple[float, float] = (0.0, 360.0)
    speed_range_mps: tuple[float, float] = (0.0, 100.0)
    draft_range_m: tuple[float, float] = (0.0, 50.0)
    custom_bounds: Mapping[str, tuple[float, float]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate range bounds and freeze custom bounds."""
        for field_name in ("heading_range_deg", "speed_range_mps", "draft_range_m"):
            val = getattr(self, field_name)
            if not isinstance(val, (tuple, list)) or len(val) != 2:
                raise ValueError(f"{field_name} must be a 2-tuple (min, max)")
            v_min = _finite_scalar(f"{field_name}[0]", val[0])
            v_max = _finite_scalar(f"{field_name}[1]", val[1])
            if v_min > v_max:
                raise ValueError(f"{field_name} min ({v_min}) cannot exceed max ({v_max})")
            object.__setattr__(self, field_name, (v_min, v_max))

        custom: dict[str, tuple[float, float]] = {}
        for k, val in self.custom_bounds.items():
            if not isinstance(val, (tuple, list)) or len(val) != 2:
                raise ValueError(f"custom_bounds[{k}] must be a 2-tuple (min, max)")
            c_min = _finite_scalar(f"custom_bounds[{k}][0]", val[0])
            c_max = _finite_scalar(f"custom_bounds[{k}][1]", val[1])
            if c_min > c_max:
                raise ValueError(f"custom_bounds[{k}] min ({c_min}) cannot exceed max ({c_max})")
            custom[str(k)] = (c_min, c_max)
        object.__setattr__(self, "custom_bounds", MappingProxyType(custom))

    def contains(
        self,
        heading_deg: float | None = None,
        speed_mps: float | None = None,
        draft_m: float | None = None,
        **custom: float,
    ) -> bool:
        """Check if inputs fall strictly within declared domain bounds."""
        if heading_deg is not None:
            if not (self.heading_range_deg[0] <= heading_deg <= self.heading_range_deg[1]):
                return False
        if speed_mps is not None:
            if not (self.speed_range_mps[0] <= speed_mps <= self.speed_range_mps[1]):
                return False
        if draft_m is not None:
            if not (self.draft_range_m[0] <= draft_m <= self.draft_range_m[1]):
                return False
        for k, v in custom.items():
            if k in self.custom_bounds:
                b_min, b_max = self.custom_bounds[k]
                if not (b_min <= v <= b_max):
                    return False
        return True


@dataclass(frozen=True)
class AssetMetadata:
    """Immutable metadata record carrying provenance, trust, hash, license, domain, and uncertainty (TS-23, VR-10)."""

    asset_id: str
    asset_type: str
    trust_level: AssetTrustLevel
    source_type: str
    sha256: str
    license: str
    provenance: Mapping[str, Any] = field(default_factory=dict)
    applicability_domain: ApplicabilityDomain = field(default_factory=ApplicabilityDomain)
    uncertainty: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate non-empty strings, hash format, trust level, and freeze mappings."""
        object.__setattr__(self, "asset_id", _non_empty_str("asset_id", self.asset_id))
        object.__setattr__(self, "asset_type", _non_empty_str("asset_type", self.asset_type))
        trust = AssetTrustLevel(self.trust_level)
        object.__setattr__(self, "trust_level", trust)
        source = _non_empty_str("source_type", self.source_type)
        object.__setattr__(self, "source_type", source)
        object.__setattr__(self, "sha256", _validate_sha256("sha256", self.sha256))
        object.__setattr__(self, "license", _non_empty_str("license", self.license))

        # Structural impossibility of mock/inferred becoming validated (TS-23, VR-10, ALT-25):
        if source.lower() in {"mock", "inferred"} and trust == AssetTrustLevel.VALIDATED_FOR_VESSEL:
            raise ValueError(
                f"Asset {self.asset_id} with source_type '{source}' cannot have "
                f"trust_level '{trust.value}' (mock/inferred assets never become validated per TS-23/VR-10/ALT-25)"
            )
        if not isinstance(self.applicability_domain, ApplicabilityDomain):
            raise TypeError(
                f"applicability_domain must be ApplicabilityDomain, got {type(self.applicability_domain).__name__}"
            )
        object.__setattr__(self, "provenance", _deep_freeze(self.provenance))
        object.__setattr__(self, "uncertainty", _deep_freeze(self.uncertainty))


@dataclass(frozen=True)
class VesselLoad:
    """Immutable body-frame vessel generalized loads in SI units (N, N·m).

    Sign conventions:
    - surge_n: body-x forward positive (N) (TS-03)
    - sway_n: body-y starboard positive (N) (TS-03)
    - yaw_nm: body-z right/clockwise positive (N·m) (TS-04, TS-05)
    - roll_nm: body-x starboard-down positive (N·m) (TS-05)
    """

    surge_n: float = 0.0
    sway_n: float = 0.0
    yaw_nm: float = 0.0
    roll_nm: float = 0.0

    def __post_init__(self) -> None:
        """Validate finite values and freeze."""
        object.__setattr__(self, "surge_n", _finite_scalar("surge_n", self.surge_n))
        object.__setattr__(self, "sway_n", _finite_scalar("sway_n", self.sway_n))
        object.__setattr__(self, "yaw_nm", _finite_scalar("yaw_nm", self.yaw_nm))
        object.__setattr__(self, "roll_nm", _finite_scalar("roll_nm", self.roll_nm))

    @classmethod
    def zero(cls) -> VesselLoad:
        """Construct zero vessel load."""
        return cls(0.0, 0.0, 0.0, 0.0)

    def __add__(self, other: object) -> VesselLoad:
        """Explicit component-wise summation."""
        if not isinstance(other, VesselLoad):
            return NotImplemented
        return VesselLoad(
            surge_n=self.surge_n + other.surge_n,
            sway_n=self.sway_n + other.sway_n,
            yaw_nm=self.yaw_nm + other.yaw_nm,
            roll_nm=self.roll_nm + other.roll_nm,
        )

    def as_array(self, capabilities: frozenset[str] | None = None) -> FloatArray:
        """Export as 3DOF [X, Y, N] or 4DOF [X, Y, K, N] array."""
        if capabilities is not None and "ROLL_4DOF" in capabilities:
            return np.array([self.surge_n, self.sway_n, self.roll_nm, self.yaw_nm], dtype=np.float64)
        return np.array([self.surge_n, self.sway_n, self.yaw_nm], dtype=np.float64)


@dataclass(frozen=True)
class EnvironmentalLoads:
    """Immutable environmental load decomposition and explicit total sum (VR-09, TS-09).

    Components retain separate identities (ALT-23 rejected total-only wrench).
    """

    wind: VesselLoad = field(default_factory=VesselLoad.zero)
    current: VesselLoad = field(default_factory=VesselLoad.zero)
    wave_first_order: VesselLoad = field(default_factory=VesselLoad.zero)
    wave_mean_drift: VesselLoad = field(default_factory=VesselLoad.zero)
    total: VesselLoad = field(default_factory=VesselLoad.zero)
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate component types, verify explicit total sum, and freeze details."""
        if not isinstance(self.wind, VesselLoad):
            raise TypeError(f"wind must be VesselLoad, got {type(self.wind).__name__}")
        if not isinstance(self.current, VesselLoad):
            raise TypeError(f"current must be VesselLoad, got {type(self.current).__name__}")
        if not isinstance(self.wave_first_order, VesselLoad):
            raise TypeError(f"wave_first_order must be VesselLoad, got {type(self.wave_first_order).__name__}")
        if not isinstance(self.wave_mean_drift, VesselLoad):
            raise TypeError(f"wave_mean_drift must be VesselLoad, got {type(self.wave_mean_drift).__name__}")
        if not isinstance(self.total, VesselLoad):
            raise TypeError(f"total must be VesselLoad, got {type(self.total).__name__}")

        expected_total = self.wind + self.current + self.wave_first_order + self.wave_mean_drift
        if not (
            math.isclose(self.total.surge_n, expected_total.surge_n, rel_tol=1e-9, abs_tol=1e-9)
            and math.isclose(self.total.sway_n, expected_total.sway_n, rel_tol=1e-9, abs_tol=1e-9)
            and math.isclose(self.total.yaw_nm, expected_total.yaw_nm, rel_tol=1e-9, abs_tol=1e-9)
            and math.isclose(self.total.roll_nm, expected_total.roll_nm, rel_tol=1e-9, abs_tol=1e-9)
        ):
            raise ValueError(f"total load {self.total} does not match explicit sum of components {expected_total}")
        object.__setattr__(self, "details", _deep_freeze(self.details))

    @classmethod
    def from_components(
        cls,
        wind: VesselLoad | None = None,
        current: VesselLoad | None = None,
        wave_first_order: VesselLoad | None = None,
        wave_mean_drift: VesselLoad | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> EnvironmentalLoads:
        """Construct EnvironmentalLoads by explicitly summing non-None components."""
        w = wind if wind is not None else VesselLoad.zero()
        c = current if current is not None else VesselLoad.zero()
        w1 = wave_first_order if wave_first_order is not None else VesselLoad.zero()
        wmd = wave_mean_drift if wave_mean_drift is not None else VesselLoad.zero()
        tot = w + c + w1 + wmd
        return cls(
            wind=w,
            current=c,
            wave_first_order=w1,
            wave_mean_drift=wmd,
            total=tot,
            details=details or {},
        )


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

    @property
    def north_m(self) -> float:
        """Return north position in meters."""
        return float(self.values[0])

    @property
    def east_m(self) -> float:
        """Return east position in meters."""
        return float(self.values[1])

    @property
    def heading_rad(self) -> float:
        """Return heading / yaw angle in radians."""
        return float(self.values[2])

    @property
    def roll_rad(self) -> float:
        """Return roll angle in radians (0.0 for 3DOF)."""
        return float(self.values[3]) if "ROLL_4DOF" in self.capabilities else 0.0

    @property
    def surge_mps(self) -> float:
        """Return body surge velocity in m/s."""
        return float(self.values[4]) if "ROLL_4DOF" in self.capabilities else float(self.values[3])

    @property
    def sway_mps(self) -> float:
        """Return body sway velocity in m/s."""
        return float(self.values[5]) if "ROLL_4DOF" in self.capabilities else float(self.values[4])

    @property
    def roll_rate_radps(self) -> float:
        """Return roll rate in rad/s (0.0 for 3DOF)."""
        return float(self.values[6]) if "ROLL_4DOF" in self.capabilities else 0.0

    @property
    def yaw_rate_radps(self) -> float:
        """Return yaw rate in rad/s."""
        return float(self.values[7]) if "ROLL_4DOF" in self.capabilities else float(self.values[5])

    def to_navigation_state(self, source: NavigationSource = NavigationSource.TRUTH_PROJECTION) -> NavigationState:
        """Project full physical truth state to 3DOF planar navigation view."""
        return NavigationState(
            north_m=self.north_m,
            east_m=self.east_m,
            heading_rad=self.heading_rad,
            surge_mps=self.surge_mps,
            sway_mps=self.sway_mps,
            yaw_rate_radps=self.yaw_rate_radps,
            source=source,
        )


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
        object.__setattr__(self, "details", _deep_freeze(self.details))


class AchievedLoadStatus(str, Enum):
    """Availability status of achieved load feedback."""

    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class AchievedGeneralizedLoad:
    """Immutable feedback of actual generalized loads achieved by allocator/actuator (TS-20, VR-15).

    Carries achieved 3DOF generalized load [X, Y, N] and optional roll moment K,
    along with saturation flags, availability status, and metadata source.
    """

    surge_n: float = 0.0
    sway_n: float = 0.0
    yaw_nm: float = 0.0
    roll_nm: float = 0.0
    status: AchievedLoadStatus = AchievedLoadStatus.AVAILABLE
    saturated: bool = False
    source: str = "IDEAL_PASSTHROUGH"
    tick: int = 0
    time_s: float = 0.0
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate finite components, types, and freeze details."""
        object.__setattr__(self, "surge_n", _finite_scalar("surge_n", self.surge_n))
        object.__setattr__(self, "sway_n", _finite_scalar("sway_n", self.sway_n))
        object.__setattr__(self, "yaw_nm", _finite_scalar("yaw_nm", self.yaw_nm))
        object.__setattr__(self, "roll_nm", _finite_scalar("roll_nm", self.roll_nm))
        object.__setattr__(self, "status", AchievedLoadStatus(self.status))
        if not isinstance(self.saturated, bool):
            raise TypeError(f"saturated must be a boolean, got {type(self.saturated).__name__}")
        object.__setattr__(self, "source", _non_empty_str("source", self.source))
        object.__setattr__(self, "tick", _non_bool_int("tick", self.tick))
        object.__setattr__(self, "time_s", _finite_scalar("time_s", self.time_s))
        object.__setattr__(self, "details", _deep_freeze(self.details))

    @classmethod
    def from_vessel_load(
        cls,
        load: VesselLoad,
        status: AchievedLoadStatus = AchievedLoadStatus.AVAILABLE,
        saturated: bool = False,
        source: str = "IDEAL_PASSTHROUGH",
        tick: int = 0,
        time_s: float = 0.0,
        details: Mapping[str, Any] | None = None,
    ) -> AchievedGeneralizedLoad:
        """Construct achieved load from VesselLoad."""
        if not isinstance(load, VesselLoad):
            raise TypeError(f"load must be VesselLoad, got {type(load).__name__}")
        return cls(
            surge_n=load.surge_n,
            sway_n=load.sway_n,
            yaw_nm=load.yaw_nm,
            roll_nm=load.roll_nm,
            status=status,
            saturated=saturated,
            source=source,
            tick=tick,
            time_s=time_s,
            details=details or {},
        )

    @classmethod
    def unavailable(
        cls,
        source: str = "UNAVAILABLE",
        tick: int = 0,
        time_s: float = 0.0,
    ) -> AchievedGeneralizedLoad:
        """Construct explicit unavailable achieved load feedback."""
        return cls(
            surge_n=0.0,
            sway_n=0.0,
            yaw_nm=0.0,
            roll_nm=0.0,
            status=AchievedLoadStatus.UNAVAILABLE,
            saturated=False,
            source=source,
            tick=tick,
            time_s=time_s,
        )

    def as_vessel_load(self) -> VesselLoad:
        """Convert to VesselLoad."""
        return VesselLoad(
            surge_n=self.surge_n,
            sway_n=self.sway_n,
            yaw_nm=self.yaw_nm,
            roll_nm=self.roll_nm,
        )


@dataclass(frozen=True)
class MarinePIDTrace:
    """Immutable per-tick trace decomposing marine PID control terms (TS-20, VR-15, VR-18).

    Traces:
    - P, I, D, feedforward components separately
    - raw requested force [X, Y, N]
    - saturated output force [X, Y, N]
    - achieved output force [X, Y, N] or None if unavailable
    - per-channel saturation flags
    - anti-windup back-calculation correction
    - tracking errors [e_u, e_v, e_psi] or [e_x, e_y, e_psi]
    - measured and reference values
    - dt and timestamp
    """

    tick: int
    time_s: float
    dt_s: float
    errors: tuple[float, float, float]
    measurement: tuple[float, float, float]
    reference: tuple[float, float, float]
    p_term: tuple[float, float, float]
    i_term: tuple[float, float, float]
    d_term: tuple[float, float, float]
    feedforward: tuple[float, float, float]
    raw_request: tuple[float, float, float]
    saturated_output: tuple[float, float, float]
    saturation_flags: tuple[bool, bool, bool]
    antiwindup_correction: tuple[float, float, float]
    achieved_output: tuple[float, float, float] | None = None
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate components and freeze."""
        object.__setattr__(self, "tick", _non_bool_int("tick", self.tick))
        object.__setattr__(self, "time_s", _finite_scalar("time_s", self.time_s))
        dt = _finite_scalar("dt_s", self.dt_s)
        if dt <= 0.0:
            raise ValueError(f"dt_s must be positive, got {dt}")
        object.__setattr__(self, "dt_s", dt)

        for field_name in (
            "errors",
            "measurement",
            "reference",
            "p_term",
            "i_term",
            "d_term",
            "feedforward",
            "raw_request",
            "saturated_output",
            "antiwindup_correction",
        ):
            val = getattr(self, field_name)
            if not isinstance(val, (tuple, list)) or len(val) != 3:
                raise ValueError(f"{field_name} must be a 3-tuple, got {val!r}")
            tup = tuple(_finite_scalar(f"{field_name}[{i}]", v) for i, v in enumerate(val))
            object.__setattr__(self, field_name, tup)

        flags = self.saturation_flags
        if not isinstance(flags, (tuple, list)) or len(flags) != 3:
            raise ValueError(f"saturation_flags must be a 3-tuple, got {flags!r}")
        for i, f in enumerate(flags):
            if not isinstance(f, bool):
                raise TypeError(f"saturation_flags[{i}] must be bool, got {type(f).__name__}")
        object.__setattr__(self, "saturation_flags", tuple(bool(f) for f in flags))

        if self.achieved_output is not None:
            ach = self.achieved_output
            if not isinstance(ach, (tuple, list)) or len(ach) != 3:
                raise ValueError(f"achieved_output must be a 3-tuple or None, got {ach!r}")
            object.__setattr__(
                self,
                "achieved_output",
                tuple(_finite_scalar(f"achieved_output[{i}]", v) for i, v in enumerate(ach)),
            )

        object.__setattr__(self, "details", _deep_freeze(self.details))


@dataclass(frozen=True)
class StackOutput:
    """Immutable facade output."""

    tick: int
    navigation: NavigationState
    plant: PlantState
    applied_reference: DirectReference | None
    failure: FacadeFailure | None = None
    environment_observation: EnvironmentObservation | None = None
    environmental_loads: EnvironmentalLoads | None = None
    controller_trace: MarinePIDTrace | None = None
    achieved_load: AchievedGeneralizedLoad | None = None


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
