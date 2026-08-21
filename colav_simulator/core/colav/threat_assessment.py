"""Canonical, planner-agnostic threat facts for one assessment cycle."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass, field, is_dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any

import numpy as np

from colav_simulator.core.colav.encounter_lifecycle import ObservationHealth, OwnshipObservation
from colav_simulator.core.tracking.trackers import TrackKey

THREAT_SCHEMA_VERSION = "colav.threat-management.snapshot@1"
THREAT_CANONICALIZER_ID = "colav.python-json@1"


class DomainQualification(StrEnum):
    """Qualification state for engineering Ship Domain parameters."""

    QUALIFIED = "QUALIFIED"
    UNQUALIFIED = "UNQUALIFIED"


class DomainState(StrEnum):
    """Typed current or predicted relationship to the Ship Domain."""

    OUTSIDE = "OUTSIDE"
    INSIDE = "INSIDE"
    TANGENT = "TANGENT"
    NO_INTERSECTION = "NO_INTERSECTION"
    UNKNOWN = "UNKNOWN"
    UNQUALIFIED = "UNQUALIFIED"


class PredictionBasis(StrEnum):
    """Provenance of the target trajectory used for domain projection."""

    EXPLICIT_TRAJECTORY = "EXPLICIT_TRAJECTORY"
    CONSTANT_VELOCITY = "CONSTANT_VELOCITY"
    UNAVAILABLE = "UNAVAILABLE"


class ThreatUnavailableReason(StrEnum):
    """Typed reasons for facts that cannot be claimed by this snapshot."""

    PREDICTION_UNAVAILABLE = "PREDICTION_UNAVAILABLE"
    PROFILE_UNQUALIFIED = "PROFILE_UNQUALIFIED"
    OBSERVATION_UNUSABLE = "OBSERVATION_UNUSABLE"
    TARGET_DIMENSIONS_UNAVAILABLE = "TARGET_DIMENSIONS_UNAVAILABLE"
    RELATIVE_MOTION_UNDEFINED = "RELATIVE_MOTION_UNDEFINED"
    UNCERTAINTY_UNAVAILABLE = "UNCERTAINTY_UNAVAILABLE"


@dataclass(frozen=True)
class ThreatPrediction:
    """Immutable target trajectory on an explicit relative-time horizon."""

    key: TrackKey
    times_s: np.ndarray
    states_enu: np.ndarray
    basis: PredictionBasis | str
    model: str

    def __post_init__(self) -> None:
        """Validate ordered prediction samples and provenance."""
        if not isinstance(self.key, TrackKey):
            raise TypeError("prediction key must be TrackKey")
        times = np.array(self.times_s, dtype=float, copy=True)
        states = np.array(self.states_enu, dtype=float, copy=True)
        if times.ndim != 1 or times.size == 0 or not np.isfinite(times).all():
            raise ValueError("prediction times must be finite and non-empty")
        if states.shape != (times.size, 4) or not np.isfinite(states).all():
            raise ValueError("prediction states must have shape (N, 4) and be finite")
        if times[0] < 0.0 or np.any(np.diff(times) <= 0.0):
            raise ValueError("prediction times must be strictly increasing and non-negative")
        if not self.model.strip():
            raise ValueError("prediction model is required")
        basis = PredictionBasis(self.basis)
        if basis is PredictionBasis.UNAVAILABLE:
            raise ValueError("unavailable predictions must be omitted, not represented as a trajectory")
        times.setflags(write=False)
        states.setflags(write=False)
        object.__setattr__(self, "times_s", times)
        object.__setattr__(self, "states_enu", states)
        object.__setattr__(self, "basis", basis)


@dataclass(frozen=True)
class ThreatTargetObservation:
    """Tracker observation accepted by Threat Assessment.

    Vessel dimensions are optional because missing dimensions must remain
    explicit; they are never replaced with a default for hull clearance.
    """

    key: TrackKey
    state_enu: np.ndarray
    covariance: np.ndarray | None
    length_m: float | None
    width_m: float | None
    observed_at_s: float
    generated_at_s: float
    health: ObservationHealth | str
    source: str

    def __post_init__(self) -> None:
        """Validate and freeze target evidence without inventing dimensions."""
        if not isinstance(self.key, TrackKey):
            raise TypeError("target key must be TrackKey")
        state = np.array(self.state_enu, dtype=float, copy=True)
        if state.shape != (4,) or not np.isfinite(state).all():
            raise ValueError("target state must be finite with shape (4,)")
        state.setflags(write=False)
        object.__setattr__(self, "state_enu", state)
        if self.covariance is not None:
            covariance = np.array(self.covariance, dtype=float, copy=True)
            if covariance.shape != (4, 4) or not np.isfinite(covariance).all():
                raise ValueError("target covariance must be finite with shape (4, 4)")
            if not np.allclose(covariance, covariance.T, atol=1.0e-10, rtol=0.0):
                raise ValueError("target covariance must be symmetric")
            if float(np.min(np.linalg.eigvalsh(covariance))) < -1.0e-9:
                raise ValueError("target covariance must be positive semidefinite")
            covariance.setflags(write=False)
            object.__setattr__(self, "covariance", covariance)
        for value, name in ((self.length_m, "length_m"), (self.width_m, "width_m")):
            if value is not None and (not math.isfinite(value) or value <= 0.0):
                raise ValueError(f"{name} must be positive when present")
        if not math.isfinite(self.observed_at_s) or not math.isfinite(self.generated_at_s):
            raise ValueError("target observation times must be finite")
        if self.observed_at_s < 0.0 or self.generated_at_s < self.observed_at_s:
            raise ValueError("target observation times are invalid")
        if not self.source.strip():
            raise ValueError("target source is required")
        object.__setattr__(self, "health", ObservationHealth(self.health))

    @property
    def age_s(self) -> float:
        return self.generated_at_s - self.observed_at_s


@dataclass(frozen=True)
class DomainFacts:
    """Domain state and normalized scale for one time interpretation."""

    state: DomainState
    normalized_scale: float | None
    unavailable_reason: ThreatUnavailableReason | str | None = None
    uncertainty_radius_m: float | None = None
    tdv_s: float | None = None
    tde_s: float | None = None
    horizon_min_scale: float | None = None

    def __post_init__(self) -> None:
        """Validate typed availability and normalized-scale convention."""
        object.__setattr__(self, "state", DomainState(self.state))
        if self.unavailable_reason is not None:
            object.__setattr__(self, "unavailable_reason", ThreatUnavailableReason(self.unavailable_reason))
        for value, name in (
            (self.normalized_scale, "normalized_scale"),
            (self.uncertainty_radius_m, "uncertainty_radius_m"),
            (self.tdv_s, "tdv_s"),
            (self.tde_s, "tde_s"),
            (self.horizon_min_scale, "horizon_min_scale"),
        ):
            if value is not None and (not math.isfinite(value) or (name.endswith("_s") and value < 0.0)):
                raise ValueError(f"{name} must be finite")
        if self.uncertainty_radius_m is not None and self.uncertainty_radius_m < 0.0:
            raise ValueError("uncertainty_radius_m must be non-negative")
        if self.normalized_scale is not None and self.normalized_scale < 0.0:
            raise ValueError("normalized_scale must be non-negative")
        if self.horizon_min_scale is not None and self.horizon_min_scale < 0.0:
            raise ValueError("horizon_min_scale must be non-negative")
        if self.tdv_s is not None and self.tde_s is not None and self.tde_s < self.tdv_s:
            raise ValueError("tde_s cannot precede tdv_s")
        if self.state in {DomainState.UNKNOWN, DomainState.UNQUALIFIED} and self.normalized_scale is not None:
            raise ValueError("unknown or unqualified domain state cannot expose a scale")

    @property
    def hard_safety_gate(self) -> bool:
        """Ship Domain facts are anticipatory evidence, never a hard gate."""
        return False


@dataclass(frozen=True)
class ThreatVector:
    """Canonical independent threat facts for one TrackKey target."""

    key: TrackKey
    observation_health: ObservationHealth
    range_m: float | None
    closing_speed_mps: float | None
    dcpa_m: float | None
    tcpa_signed_s: float | None
    tcpa_forward_s: float | None
    hull_clearance_m: float | None
    current_domain: DomainFacts
    predicted_domain: DomainFacts
    uncertainty_radius_m: float | None
    claim_completeness: str
    prediction_basis: PredictionBasis
    unavailable_reasons: tuple[ThreatUnavailableReason | str, ...] = ()

    def __post_init__(self) -> None:
        """Validate immutable physical and domain fact boundaries."""
        if not isinstance(self.key, TrackKey):
            raise TypeError("threat vector key must be TrackKey")
        if self.range_m is not None and (not math.isfinite(self.range_m) or self.range_m < 0.0):
            raise ValueError("range must be finite and non-negative")
        for value, name in (
            (self.closing_speed_mps, "closing_speed_mps"),
            (self.dcpa_m, "dcpa_m"),
            (self.tcpa_signed_s, "tcpa_signed_s"),
            (self.tcpa_forward_s, "tcpa_forward_s"),
            (self.hull_clearance_m, "hull_clearance_m"),
            (self.uncertainty_radius_m, "uncertainty_radius_m"),
        ):
            if value is not None and not math.isfinite(value):
                raise ValueError(f"{name} must be finite when present")
        if not self.claim_completeness.strip():
            raise ValueError("claim_completeness is required")
        object.__setattr__(self, "observation_health", ObservationHealth(self.observation_health))
        object.__setattr__(self, "prediction_basis", PredictionBasis(self.prediction_basis))
        reasons = tuple(
            sorted(
                {ThreatUnavailableReason(reason) for reason in self.unavailable_reasons},
                key=lambda value: value.value,
            )
        )
        object.__setattr__(self, "unavailable_reasons", reasons)

    @property
    def normalized_domain_scale(self) -> float | None:
        """Compatibility alias for the current effective domain scale."""
        return self.current_domain.normalized_scale

    @property
    def domain_scale(self) -> float | None:
        return self.current_domain.normalized_scale

    @property
    def tdv_s(self) -> float | None:
        return self.predicted_domain.tdv_s

    @property
    def time_to_domain_violation_s(self) -> float | None:
        return self.predicted_domain.tdv_s

    @property
    def tde_s(self) -> float | None:
        return self.predicted_domain.tde_s

    @property
    def time_to_domain_exit_s(self) -> float | None:
        return self.predicted_domain.tde_s

    @property
    def horizon_min_scale(self) -> float | None:
        return self.predicted_domain.horizon_min_scale

    @property
    def horizon_min_domain_scale(self) -> float | None:
        return self.predicted_domain.horizon_min_scale


@dataclass(frozen=True)
class ShipDomainProfile:
    """Versioned off-centred elliptic engineering domain parameters.

    The four extents are measured from the ownship reference point.  They are
    engineering assumptions in metres and are not COLREG statutory distances.
    """

    profile_id: str
    version: str
    fore_m: float
    aft_m: float
    port_m: float
    starboard_m: float
    parameter_source: str
    assumptions: tuple[str, ...]
    qualification: DomainQualification = DomainQualification.QUALIFIED
    uncertainty_multiplier: float = 2.0
    units: str = "m"

    def __post_init__(self) -> None:
        """Validate and freeze one explicitly identified profile."""
        if not self.profile_id.strip() or not self.version.strip():
            raise ValueError("ShipDomainProfile identity is required")
        if self.units != "m":
            raise ValueError("ShipDomainProfile units must be metres")
        if not self.parameter_source.strip():
            raise ValueError("ShipDomainProfile parameter_source is required")
        assumptions = tuple(str(value) for value in self.assumptions)
        if not assumptions or any(not value.strip() for value in assumptions):
            raise ValueError("ShipDomainProfile assumptions are required")
        geometry = (self.fore_m, self.aft_m, self.port_m, self.starboard_m)
        if not np.isfinite(geometry).all() or min(geometry) <= 0.0:
            raise ValueError("ShipDomainProfile geometry must be positive and finite")
        if not math.isfinite(self.uncertainty_multiplier) or self.uncertainty_multiplier < 0.0:
            raise ValueError("ShipDomainProfile uncertainty multiplier must be finite and non-negative")
        object.__setattr__(self, "qualification", DomainQualification(self.qualification))
        object.__setattr__(self, "assumptions", assumptions)

    @property
    def profile_hash(self) -> str:
        """Return the deterministic identity of the published profile."""
        return _sha256(self.to_dict())

    @property
    def qualified(self) -> bool:
        return self.qualification is DomainQualification.QUALIFIED

    def to_dict(self) -> dict[str, object]:
        return {
            "profile_id": self.profile_id,
            "version": self.version,
            "model": "OFF_CENTRED_ELLIPSE",
            "fore_m": self.fore_m,
            "aft_m": self.aft_m,
            "port_m": self.port_m,
            "starboard_m": self.starboard_m,
            "parameter_source": self.parameter_source,
            "assumptions": list(self.assumptions),
            "qualification": self.qualification.value,
            "uncertainty_multiplier": self.uncertainty_multiplier,
            "units": self.units,
        }


@dataclass(frozen=True)
class ThreatAssessmentRequest:
    """Immutable public input to one pure Threat Assessment operation."""

    epoch: str
    sequence: int
    sim_time_s: float
    ownship: OwnshipObservation
    targets: tuple[Any, ...]
    profile: ShipDomainProfile
    predictions: tuple[ThreatPrediction, ...] = ()

    def __post_init__(self) -> None:
        """Validate cycle identity and freeze target collection."""
        if not self.epoch.strip():
            raise ValueError("assessment epoch is required")
        if self.sequence < 0 or not math.isfinite(self.sim_time_s) or self.sim_time_s < 0.0:
            raise ValueError("assessment sequence and time must be non-negative")
        if not isinstance(self.ownship, OwnshipObservation):
            raise TypeError("ownship must be OwnshipObservation")
        if not isinstance(self.profile, ShipDomainProfile):
            raise TypeError("profile must be ShipDomainProfile")
        targets = tuple(self.targets)
        keys = tuple(getattr(target, "key", None) for target in targets)
        if any(key is None for key in keys):
            raise TypeError("assessment targets must expose a TrackKey key")
        if len(keys) != len(set(keys)):
            raise ValueError("assessment target keys must be unique")
        predictions = tuple(self.predictions)
        if not all(isinstance(value, ThreatPrediction) for value in predictions):
            raise TypeError("predictions must contain ThreatPrediction values")
        prediction_keys = tuple(value.key for value in predictions)
        if len(prediction_keys) != len(set(prediction_keys)):
            raise ValueError("assessment prediction keys must be unique")
        if any(key not in keys for key in prediction_keys):
            raise ValueError("predictions must reference an assessment target")
        object.__setattr__(self, "targets", targets)
        object.__setattr__(self, "predictions", predictions)

    @property
    def input_hash(self) -> str:
        """Return the canonical identity of the assessment input."""
        return _sha256(self.to_dict())

    def to_dict(self) -> dict[str, object]:
        return {
            "epoch": self.epoch,
            "sequence": self.sequence,
            "sim_time_s": self.sim_time_s,
            "ownship": _json_value(self.ownship),
            "targets": [
                _json_value(target)
                for target in sorted(self.targets, key=lambda value: _track_key_sort(value.key))
            ],
            "profile": self.profile.to_dict(),
            "predictions": [
                _json_value(value)
                for value in sorted(self.predictions, key=lambda value: _track_key_sort(value.key))
            ],
        }


@dataclass(frozen=True)
class ThreatManagementSnapshot:
    """Immutable semantic result shared by evidence and projections."""

    epoch: str
    sequence: int
    sim_time_s: float
    input_hash: str
    profile_hash: str
    profile: ShipDomainProfile
    vectors: tuple[Any, ...] = ()
    schema_version: str = THREAT_SCHEMA_VERSION
    canonicalizer_id: str = THREAT_CANONICALIZER_ID
    provenance: Mapping[str, object] = field(default_factory=lambda: MappingProxyType({}))
    _semantic_hash: str = ""

    def __post_init__(self) -> None:
        """Freeze result collections and compute its semantic identity."""
        if not self.epoch.strip() or not self.input_hash.strip() or not self.profile_hash.strip():
            raise ValueError("snapshot identity fields are required")
        if not isinstance(self.profile, ShipDomainProfile):
            raise TypeError("snapshot profile must be ShipDomainProfile")
        if self.profile.profile_hash != self.profile_hash:
            raise ValueError("snapshot profile hash does not match profile")
        if self.sequence < 0 or not math.isfinite(self.sim_time_s) or self.sim_time_s < 0.0:
            raise ValueError("snapshot sequence and time must be non-negative")
        vectors = tuple(self.vectors)
        keys = tuple(getattr(value, "key", None) for value in vectors)
        if any(key is None for key in keys):
            raise TypeError("snapshot vectors must expose a TrackKey key")
        if keys != tuple(sorted(keys, key=_track_key_sort)):
            raise ValueError("snapshot vectors must be sorted by TrackKey")
        if len(keys) != len(set(keys)):
            raise ValueError("snapshot vector keys must be unique")
        object.__setattr__(self, "vectors", vectors)
        object.__setattr__(self, "provenance", _freeze_mapping(self.provenance))
        semantic_hash = _sha256(self.to_dict(include_hash=False))
        object.__setattr__(self, "_semantic_hash", semantic_hash)

    @property
    def semantic_hash(self) -> str:
        return self._semantic_hash

    def to_dict(self, *, include_hash: bool = True) -> dict[str, object]:
        value: dict[str, object] = {
            "schema_version": self.schema_version,
            "canonicalizer_id": self.canonicalizer_id,
            "epoch": self.epoch,
            "sequence": self.sequence,
            "sim_time_s": self.sim_time_s,
            "input_hash": self.input_hash,
            "profile_hash": self.profile_hash,
            "profile": self.profile.to_dict(),
            "vectors": [_json_value(vector) for vector in self.vectors],
            "provenance": _json_value(self.provenance),
        }
        if include_hash:
            value["semantic_hash"] = self.semantic_hash
        return value


class ThreatAssessment:
    """Pure evaluator of current and predicted per-target threat facts."""

    @staticmethod
    def evaluate(request: ThreatAssessmentRequest) -> ThreatManagementSnapshot:
        """Return one deterministic snapshot for the supplied immutable request."""
        if not isinstance(request, ThreatAssessmentRequest):
            raise TypeError("request must be ThreatAssessmentRequest")
        vectors = tuple(
            _assess_target(
                request.ownship,
                _coerce_target(target),
                request.profile,
                {prediction.key: prediction for prediction in request.predictions}.get(target.key),
            )
            for target in sorted(request.targets, key=lambda value: _track_key_sort(value.key))
        )
        return ThreatManagementSnapshot(
            epoch=request.epoch,
            sequence=request.sequence,
            sim_time_s=request.sim_time_s,
            input_hash=request.input_hash,
            profile_hash=request.profile.profile_hash,
            profile=request.profile,
            vectors=vectors,
            provenance={
                "assessment": "ThreatAssessment",
                "profile_id": request.profile.profile_id,
                "profile_version": request.profile.version,
            },
        )


def _coerce_target(target: Any) -> ThreatTargetObservation:
    if isinstance(target, ThreatTargetObservation):
        return target
    # Keep the existing lifecycle observation contract accepted at this seam
    # without making lifecycle own any Threat Assessment state.
    required = (
        "key",
        "state_enu",
        "covariance",
        "length_m",
        "width_m",
        "observed_at_s",
        "generated_at_s",
        "health",
        "source",
    )
    if all(hasattr(target, name) for name in required):
        return ThreatTargetObservation(
            key=target.key,
            state_enu=target.state_enu,
            covariance=target.covariance,
            length_m=target.length_m,
            width_m=target.width_m,
            observed_at_s=target.observed_at_s,
            generated_at_s=target.generated_at_s,
            health=target.health,
            source=target.source,
        )
    raise TypeError("assessment targets must be ThreatTargetObservation-compatible")


def _assess_target(
    ownship: OwnshipObservation,
    target: ThreatTargetObservation,
    profile: ShipDomainProfile,
    prediction: ThreatPrediction | None,
) -> ThreatVector:
    relative_position = target.state_enu[:2] - ownship.position_ne_m
    relative_velocity = target.state_enu[2:4] - ownship.velocity_ne_mps
    range_m = float(np.linalg.norm(relative_position))
    if range_m > 1.0e-12:
        closing_speed_mps = -float(relative_position @ relative_velocity) / range_m
    else:
        closing_speed_mps = None
    relative_speed_sq = float(relative_velocity @ relative_velocity)
    unavailable: list[str] = []
    if relative_speed_sq > 1.0e-12:
        tcpa_signed_s = -float(relative_position @ relative_velocity) / relative_speed_sq
        tcpa_forward_s = max(0.0, tcpa_signed_s)
        dcpa_m = float(np.linalg.norm(relative_position + tcpa_forward_s * relative_velocity))
    else:
        tcpa_signed_s = None
        tcpa_forward_s = None
        dcpa_m = range_m
        unavailable.append("RELATIVE_MOTION_UNDEFINED")
    hull_clearance_m = None
    if target.length_m is None or target.width_m is None:
        unavailable.append("TARGET_DIMENSIONS_UNAVAILABLE")
    elif dcpa_m is not None:
        own_radius = 0.5 * math.hypot(ownship.length_m, ownship.width_m)
        target_radius = 0.5 * math.hypot(target.length_m, target.width_m)
        hull_clearance_m = dcpa_m - own_radius - target_radius

    uncertainty_radius_m = _uncertainty_radius(target, profile)
    if uncertainty_radius_m is None:
        unavailable.append(ThreatUnavailableReason.UNCERTAINTY_UNAVAILABLE)
    current_domain = _current_domain_facts(ownship, target, profile, uncertainty_radius_m)
    predicted_domain = _predicted_domain_facts(ownship, target, profile, uncertainty_radius_m, prediction)
    if predicted_domain.unavailable_reason is not None:
        unavailable.append(predicted_domain.unavailable_reason)
    completeness = "UNKNOWN" if target.health is ObservationHealth.UNUSABLE else "FULL"
    if target.health in {ObservationHealth.COASTING, ObservationHealth.DEGRADED}:
        completeness = "DEGRADED"
    if unavailable and completeness == "FULL":
        completeness = "PARTIAL"
    return ThreatVector(
        key=target.key,
        observation_health=target.health,
        range_m=range_m,
        closing_speed_mps=closing_speed_mps,
        dcpa_m=dcpa_m,
        tcpa_signed_s=tcpa_signed_s,
        tcpa_forward_s=tcpa_forward_s,
        hull_clearance_m=hull_clearance_m,
        current_domain=current_domain,
        predicted_domain=predicted_domain,
        uncertainty_radius_m=uncertainty_radius_m,
        claim_completeness=completeness,
        prediction_basis=prediction.basis if prediction is not None else PredictionBasis.UNAVAILABLE,
        unavailable_reasons=tuple(unavailable),
    )


def _uncertainty_radius(target: ThreatTargetObservation, profile: ShipDomainProfile) -> float | None:
    if target.covariance is None:
        return None
    positional = target.covariance[:2, :2]
    largest_variance = max(0.0, float(np.max(np.linalg.eigvalsh(positional))))
    return profile.uncertainty_multiplier * math.sqrt(largest_variance)


def _current_domain_facts(
    ownship: OwnshipObservation,
    target: ThreatTargetObservation,
    profile: ShipDomainProfile,
    uncertainty_radius_m: float | None,
) -> DomainFacts:
    if not profile.qualified:
        return DomainFacts(
            state=DomainState.UNQUALIFIED,
            normalized_scale=None,
            unavailable_reason="PROFILE_UNQUALIFIED",
            uncertainty_radius_m=uncertainty_radius_m,
        )
    if target.health is ObservationHealth.UNUSABLE:
        return DomainFacts(
            state=DomainState.UNKNOWN,
            normalized_scale=None,
            unavailable_reason="OBSERVATION_UNUSABLE",
            uncertainty_radius_m=uncertainty_radius_m,
        )
    if uncertainty_radius_m is None:
        return DomainFacts(
            state=DomainState.UNKNOWN,
            normalized_scale=None,
            unavailable_reason="UNCERTAINTY_UNAVAILABLE",
            uncertainty_radius_m=None,
        )
    forward = np.array([math.cos(ownship.heading_rad), math.sin(ownship.heading_rad)])
    starboard = np.array([math.sin(ownship.heading_rad), -math.cos(ownship.heading_rad)])
    relative = target.state_enu[:2] - ownship.position_ne_m
    x = float(relative @ forward)
    y = float(relative @ starboard)
    scale = _normalized_domain_scale(x, y, profile, uncertainty_radius_m)
    return DomainFacts(
        state=_domain_state(scale),
        normalized_scale=scale,
        uncertainty_radius_m=uncertainty_radius_m,
    )


def _predicted_domain_facts(
    ownship: OwnshipObservation,
    target: ThreatTargetObservation,
    profile: ShipDomainProfile,
    uncertainty_radius_m: float | None,
    prediction: ThreatPrediction | None,
) -> DomainFacts:
    if not profile.qualified:
        return DomainFacts(
            state=DomainState.UNQUALIFIED,
            normalized_scale=None,
            unavailable_reason="PROFILE_UNQUALIFIED",
            uncertainty_radius_m=uncertainty_radius_m,
        )
    if target.health is ObservationHealth.UNUSABLE:
        return DomainFacts(
            state=DomainState.UNKNOWN,
            normalized_scale=None,
            unavailable_reason="OBSERVATION_UNUSABLE",
            uncertainty_radius_m=uncertainty_radius_m,
        )
    if uncertainty_radius_m is None:
        return DomainFacts(
            state=DomainState.UNKNOWN,
            normalized_scale=None,
            unavailable_reason="UNCERTAINTY_UNAVAILABLE",
            uncertainty_radius_m=None,
        )
    if prediction is None:
        return DomainFacts(
            state=DomainState.UNKNOWN,
            normalized_scale=None,
            unavailable_reason="PREDICTION_UNAVAILABLE",
            uncertainty_radius_m=uncertainty_radius_m,
        )
    forward = np.array([math.cos(ownship.heading_rad), math.sin(ownship.heading_rad)])
    starboard = np.array([math.sin(ownship.heading_rad), -math.cos(ownship.heading_rad)])
    own_positions = ownship.position_ne_m + prediction.times_s[:, None] * ownship.velocity_ne_mps
    relative = prediction.states_enu[:, :2] - own_positions
    forward_m = relative @ forward
    starboard_m = relative @ starboard
    scales = np.array(
        [
            _normalized_domain_scale(float(x), float(y), profile, uncertainty_radius_m)
            for x, y in zip(forward_m, starboard_m, strict=True)
        ],
        dtype=float,
    )
    minimum = float(np.min(scales))
    inside = np.flatnonzero(scales < 1.0 - 1.0e-9)
    tangent = np.flatnonzero(np.isclose(scales, 1.0, rtol=0.0, atol=1.0e-9))
    if inside.size:
        state = DomainState.INSIDE
    elif tangent.size:
        state = DomainState.TANGENT
    else:
        state = DomainState.NO_INTERSECTION
    tdv_s = _first_domain_entry(prediction.times_s, scales)
    tde_s = _first_domain_exit(prediction.times_s, scales, tdv_s, bool(inside.size))
    return DomainFacts(
        state=state,
        normalized_scale=minimum,
        uncertainty_radius_m=uncertainty_radius_m,
        tdv_s=tdv_s,
        tde_s=tde_s,
        horizon_min_scale=minimum,
    )


def _first_domain_entry(times: np.ndarray, scales: np.ndarray) -> float | None:
    if scales[0] < 1.0 - 1.0e-9:
        return float(times[0])
    for index in range(1, scales.size):
        previous = float(scales[index - 1])
        current = float(scales[index])
        if current < 1.0 - 1.0e-9:
            return _crossing_time(times[index - 1], times[index], previous, current)
    return None


def _first_domain_exit(
    times: np.ndarray,
    scales: np.ndarray,
    entry_time_s: float | None,
    entered: bool,
) -> float | None:
    if not entered or entry_time_s is None:
        return None
    entry_index = max(0, int(np.searchsorted(times, entry_time_s, side="left")) - 1)
    for index in range(max(1, entry_index + 1), scales.size):
        previous = float(scales[index - 1])
        current = float(scales[index])
        if current > 1.0 + 1.0e-9:
            return _crossing_time(times[index - 1], times[index], previous, current)
    return None


def _crossing_time(t0: float, t1: float, scale0: float, scale1: float) -> float:
    if math.isclose(scale1, scale0, rel_tol=0.0, abs_tol=1.0e-12):
        return float(t1)
    fraction = (1.0 - scale0) / (scale1 - scale0)
    return float(t0 + min(max(fraction, 0.0), 1.0) * (t1 - t0))


def _normalized_domain_scale(
    forward_m: float,
    starboard_m: float,
    profile: ShipDomainProfile,
    uncertainty_radius_m: float | None,
) -> float:
    semi_major = 0.5 * (profile.fore_m + profile.aft_m) + float(uncertainty_radius_m or 0.0)
    semi_minor = 0.5 * (profile.port_m + profile.starboard_m) + float(uncertainty_radius_m or 0.0)
    center_offset = 0.5 * (profile.fore_m - profile.aft_m)
    return math.sqrt(((forward_m - center_offset) / semi_major) ** 2 + (starboard_m / semi_minor) ** 2)


def _domain_state(scale: float) -> DomainState:
    if math.isclose(scale, 1.0, rel_tol=0.0, abs_tol=1.0e-9):
        return DomainState.TANGENT
    return DomainState.INSIDE if scale < 1.0 else DomainState.OUTSIDE


def _freeze_mapping(value: Mapping[str, object]) -> MappingProxyType:
    return MappingProxyType({str(key): _freeze_value(item) for key, item in sorted(value.items())})


def _track_key_sort(key: TrackKey) -> tuple[int, int]:
    return key.target_id, key.generation


def _freeze_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _freeze_mapping(value)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_value(item) for item in value)
    return value


def _json_value(value: Any) -> Any:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, np.ndarray):
        return [_json_value(item) for item in value.tolist()]
    if is_dataclass(value):
        return {
            field: _json_value(getattr(value, field))
            for field in value.__dataclass_fields__
            if not field.startswith("_")
        }
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return _json_value(value.to_dict())
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    return value


def _sha256(value: object) -> str:
    encoded = json.dumps(_json_value(value), sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
