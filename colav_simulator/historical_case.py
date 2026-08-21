"""Historical AIS discovery and immutable Case Builder contracts.

The builder is a discovery/evidence boundary.  Its encounter labels describe
how a selected historical window was found; they are never runtime COLREG or
Planner truth.  Historical Replay and Counterfactual execution remain owned by
the normal simulator/session path.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from colav_simulator.historical_ais import (
    HistoricalAISDatasetDescriptor,
    HistoricalAISReadResult,
    HistoricalAISSelection,
)
from colav_simulator.historical_enc import (
    ENCPreflightRequest,
    ENCPreflightResult,
    ENCRegionProfile,
)
from colav_simulator.historical_replay import (
    HistoricalActor,
    HistoricalActorSampleKind,
    HistoricalActorSet,
    HistoricalActorWorldSample,
    HistoricalAISReconstructionProfile,
    HistoricalAISReconstructor,
    HistoricalAISSourceObservationRef,
)
from colav_simulator.historical_serialization import angle_delta as _angle_delta
from colav_simulator.historical_serialization import jsonable as _jsonable
from colav_simulator.historical_serialization import semantic_hash as _sha256_json

if TYPE_CHECKING:
    from colav_simulator.experiment.capabilities import CapabilityCatalog

CASE_SCHEMA_VERSION = "historical-ais-case.v1"
DISCOVERY_SCHEMA_VERSION = "historical-ais-discovery.v1"
T0_SCHEMA_VERSION = "historical-ais-t0.v1"
INTENT_SCHEMA_VERSION = "historical-ais-nominal-intent.v1"


UTC = timezone.utc


class HistoricalAISCaseBuildStatus(str, Enum):
    """Typed result of one immutable Historical AIS Case build attempt."""

    SUCCESS = "SUCCESS"
    INVALID_REQUEST = "INVALID_REQUEST"
    NO_ENCOUNTER = "NO_ENCOUNTER"
    REFERENCE_VESSEL_UNAVAILABLE = "REFERENCE_VESSEL_UNAVAILABLE"
    DIMENSIONS_UNAVAILABLE = "DIMENSIONS_UNAVAILABLE"
    ENC_UNQUALIFIED = "ENC_UNQUALIFIED"
    INITIAL_SEPARATION_INVALID = "INITIAL_SEPARATION_INVALID"
    TIME_COVERAGE_INSUFFICIENT = "TIME_COVERAGE_INSUFFICIENT"
    INTENT_NOT_ESTABLISHED = "INTENT_NOT_ESTABLISHED"
    SOURCE_QUALITY_UNAVAILABLE = "SOURCE_QUALITY_UNAVAILABLE"
    BINDINGS_UNAVAILABLE = "BINDINGS_UNAVAILABLE"


class HistoricalAISDiscoveryType(str, Enum):
    """Discovery-only encounter label; never a runtime Lifecycle role."""

    HEAD_ON = "HEAD_ON"
    CROSSING = "CROSSING"
    OVERTAKING = "OVERTAKING"


@dataclass(frozen=True)
class HistoricalAISDiscoveryProfile:
    """Versioned thresholds for deterministic historical candidate discovery."""

    profile_id: str = DISCOVERY_SCHEMA_VERSION
    profile_version: str = "1.0.0"
    max_encounter_range_m: float = 10_000.0
    min_duration_s: float = 1.0
    min_track_distance_m: float = 0.0
    min_closing_speed_mps: float = 0.05
    stationary_speed_mps: float = 0.25
    include_stationary: bool = False
    head_on_angle_deg: float = 30.0
    crossing_min_angle_deg: float = 30.0
    crossing_max_angle_deg: float = 150.0
    overtaking_angle_deg: float = 30.0
    min_initial_separation_m: float = 1.0
    min_pre_t0_samples: int = 2
    min_pre_t0_duration_s: float = 1.0
    max_quality_errors: int = 0
    source_provenance: str = "Colav-Simulator deterministic discovery profile"
    stationary_policy: str = "exclude_stationary_unless_include_stationary"

    def __post_init__(self) -> None:
        """Validate versioned discovery thresholds and freeze numeric fields."""
        if not self.profile_id.strip() or not self.profile_version.strip():
            raise ValueError("discovery profile identity is required")
        positive = (
            "max_encounter_range_m",
            "min_duration_s",
            "min_track_distance_m",
            "min_closing_speed_mps",
            "stationary_speed_mps",
            "min_initial_separation_m",
            "min_pre_t0_duration_s",
        )
        for name in positive:
            value = float(getattr(self, name))
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and non-negative")
            object.__setattr__(self, name, value)
        for name in (
            "head_on_angle_deg",
            "crossing_min_angle_deg",
            "crossing_max_angle_deg",
            "overtaking_angle_deg",
        ):
            value = float(getattr(self, name))
            if not math.isfinite(value) or not 0.0 <= value <= 180.0:
                raise ValueError(f"{name} must be in [0, 180]")
            object.__setattr__(self, name, value)
        if self.crossing_min_angle_deg > self.crossing_max_angle_deg:
            raise ValueError("crossing angle bounds are inverted")
        if int(self.min_pre_t0_samples) < 1:
            raise ValueError("min_pre_t0_samples must be positive")
        if int(self.max_quality_errors) < 0:
            raise ValueError("max_quality_errors must be non-negative")
        object.__setattr__(self, "min_pre_t0_samples", int(self.min_pre_t0_samples))
        object.__setattr__(self, "max_quality_errors", int(self.max_quality_errors))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": DISCOVERY_SCHEMA_VERSION,
            "profile_id": self.profile_id,
            "profile_version": self.profile_version,
            "max_encounter_range_m": self.max_encounter_range_m,
            "min_duration_s": self.min_duration_s,
            "min_track_distance_m": self.min_track_distance_m,
            "min_closing_speed_mps": self.min_closing_speed_mps,
            "stationary_speed_mps": self.stationary_speed_mps,
            "include_stationary": self.include_stationary,
            "head_on_angle_deg": self.head_on_angle_deg,
            "crossing_min_angle_deg": self.crossing_min_angle_deg,
            "crossing_max_angle_deg": self.crossing_max_angle_deg,
            "overtaking_angle_deg": self.overtaking_angle_deg,
            "min_initial_separation_m": self.min_initial_separation_m,
            "min_pre_t0_samples": self.min_pre_t0_samples,
            "min_pre_t0_duration_s": self.min_pre_t0_duration_s,
            "max_quality_errors": self.max_quality_errors,
            "source_provenance": self.source_provenance,
            "stationary_policy": self.stationary_policy,
        }

    @property
    def digest(self) -> str:
        return _sha256_json(self.to_dict())


@dataclass(frozen=True)
class HistoricalAISManeuverDetectionProfile:
    """Versioned, reviewable policy used to propose a maneuver handoff T0."""

    profile_id: str = T0_SCHEMA_VERSION
    profile_version: str = "1.0.0"
    heading_change_deg: float = 10.0
    speed_change_mps: float = 0.5
    min_pre_samples: int = 2
    min_post_samples: int = 1
    source_provenance: str = "Colav-Simulator deterministic maneuver detector"

    def __post_init__(self) -> None:
        """Validate the reviewable maneuver-detection policy."""
        if not self.profile_id.strip() or not self.profile_version.strip():
            raise ValueError("maneuver profile identity is required")
        for name in ("heading_change_deg", "speed_change_mps"):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and non-negative")
            object.__setattr__(self, name, value)
        for name in ("min_pre_samples", "min_post_samples"):
            value = int(getattr(self, name))
            if value < 1:
                raise ValueError(f"{name} must be positive")
            object.__setattr__(self, name, value)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": T0_SCHEMA_VERSION,
            "profile_id": self.profile_id,
            "profile_version": self.profile_version,
            "heading_change_deg": self.heading_change_deg,
            "speed_change_mps": self.speed_change_mps,
            "min_pre_samples": self.min_pre_samples,
            "min_post_samples": self.min_post_samples,
            "source_provenance": self.source_provenance,
        }

    @property
    def digest(self) -> str:
        return _sha256_json(self.to_dict())


@dataclass(frozen=True)
class HistoricalAISDiscoveryRequest:
    """Optional deterministic filters applied to discovery candidates."""

    reference_mmsi: int | None = None
    target_mmsi: tuple[int, ...] = ()
    encounter_types: tuple[str, ...] = ()
    max_candidates: int | None = None
    include_stationary: bool | None = None
    vessel_types: tuple[str, ...] = ()
    ais_classes: tuple[str, ...] = ()
    status_values: tuple[str, ...] = ()
    max_closest_approach_m: float | None = None
    max_signed_tcpa_s: float | None = None

    def __post_init__(self) -> None:
        """Normalize discovery filters into deterministic immutable values."""
        if self.reference_mmsi is not None and int(self.reference_mmsi) < 0:
            raise ValueError("reference_mmsi must be non-negative")
        object.__setattr__(self, "reference_mmsi", int(self.reference_mmsi) if self.reference_mmsi is not None else None)
        object.__setattr__(self, "target_mmsi", tuple(sorted({int(value) for value in self.target_mmsi})))
        types = tuple(sorted({HistoricalAISDiscoveryType(value).value for value in self.encounter_types}))
        object.__setattr__(self, "encounter_types", types)
        for name in ("vessel_types", "ais_classes", "status_values"):
            object.__setattr__(self, name, tuple(sorted({str(value) for value in getattr(self, name)})))
        for name in ("max_closest_approach_m", "max_signed_tcpa_s"):
            value = getattr(self, name)
            if value is not None:
                value = float(value)
                if not math.isfinite(value) or value < 0.0:
                    raise ValueError(f"{name} must be finite and non-negative")
                object.__setattr__(self, name, value)
        if self.max_candidates is not None:
            value = int(self.max_candidates)
            if value < 1:
                raise ValueError("max_candidates must be positive")
            object.__setattr__(self, "max_candidates", value)

    def to_dict(self) -> dict[str, Any]:
        return {
            "reference_mmsi": self.reference_mmsi,
            "target_mmsi": list(self.target_mmsi),
            "encounter_types": list(self.encounter_types),
            "max_candidates": self.max_candidates,
            "include_stationary": self.include_stationary,
            "vessel_types": list(self.vessel_types),
            "ais_classes": list(self.ais_classes),
            "status_values": list(self.status_values),
            "max_closest_approach_m": self.max_closest_approach_m,
            "max_signed_tcpa_s": self.max_signed_tcpa_s,
        }

    @property
    def digest(self) -> str:
        return _sha256_json(self.to_dict())


@dataclass(frozen=True)
class HistoricalAISDiscoveryCandidate:
    """One discovery-only pair candidate with deterministic evidence."""

    reference_mmsi: int
    target_mmsi: int
    encounter_type: HistoricalAISDiscoveryType
    candidate_time_utc: datetime
    common_duration_s: float
    initial_range_m: float
    closest_approach_m: float
    signed_tcpa_s: float | None
    max_closing_speed_mps: float
    reference_track_distance_m: float
    target_track_distance_m: float
    source: str = "DISCOVERY"
    multi_ship: bool = False
    concurrent_target_count: int = 1
    quality_notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Normalize enum, timestamps and evidence values."""
        if self.candidate_time_utc.tzinfo is None:
            raise ValueError("candidate_time_utc must be timezone-aware")
        object.__setattr__(self, "candidate_time_utc", self.candidate_time_utc.astimezone(UTC))
        object.__setattr__(self, "encounter_type", HistoricalAISDiscoveryType(self.encounter_type))
        for name in (
            "common_duration_s",
            "initial_range_m",
            "closest_approach_m",
            "max_closing_speed_mps",
            "reference_track_distance_m",
            "target_track_distance_m",
        ):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and non-negative")
            object.__setattr__(self, name, value)
        if self.signed_tcpa_s is not None:
            value = float(self.signed_tcpa_s)
            if not math.isfinite(value):
                raise ValueError("signed_tcpa_s must be finite")
            object.__setattr__(self, "signed_tcpa_s", value)
        object.__setattr__(self, "quality_notes", tuple(self.quality_notes))

    @property
    def discovery_only(self) -> bool:
        return self.source == "DISCOVERY"

    @property
    def label(self) -> str:
        return self.encounter_type.value

    def to_dict(self) -> dict[str, Any]:
        return {
            "reference_mmsi": self.reference_mmsi,
            "target_mmsi": self.target_mmsi,
            "encounter_type": self.encounter_type.value,
            "candidate_time_utc": self.candidate_time_utc.isoformat(),
            "common_duration_s": self.common_duration_s,
            "initial_range_m": self.initial_range_m,
            "closest_approach_m": self.closest_approach_m,
            "signed_tcpa_s": self.signed_tcpa_s,
            "max_closing_speed_mps": self.max_closing_speed_mps,
            "reference_track_distance_m": self.reference_track_distance_m,
            "target_track_distance_m": self.target_track_distance_m,
            "source": self.source,
            "discovery_only": self.discovery_only,
            "multi_ship": self.multi_ship,
            "concurrent_target_count": self.concurrent_target_count,
            "quality_notes": list(self.quality_notes),
        }


@dataclass(frozen=True)
class HistoricalAISDiscoveryResult:
    """Immutable collection of discovery metadata, separate from Lifecycle."""

    reference_mmsi: int
    profile: HistoricalAISDiscoveryProfile
    request: HistoricalAISDiscoveryRequest
    candidates: tuple[HistoricalAISDiscoveryCandidate, ...]
    source: str = "DISCOVERY"
    discovery_digest: str = ""

    def __post_init__(self) -> None:
        """Freeze candidate ordering and establish the discovery identity."""
        candidates = tuple(
            sorted(
                self.candidates,
                key=lambda item: (
                    item.candidate_time_utc,
                    item.closest_approach_m,
                    item.target_mmsi,
                    item.encounter_type.value,
                ),
            )
        )
        object.__setattr__(self, "candidates", candidates)
        if not self.discovery_digest:
            object.__setattr__(self, "discovery_digest", _sha256_json(self._identity_dict()))

    @property
    def candidate_count(self) -> int:
        return len(self.candidates)

    @property
    def digest(self) -> str:
        return self.discovery_digest

    @property
    def encounter_types(self) -> tuple[str, ...]:
        return tuple(sorted({item.encounter_type.value for item in self.candidates}))

    @property
    def multi_ship(self) -> bool:
        return self.candidate_count > 1

    def _identity_dict(self) -> dict[str, Any]:
        return {
            "schema_version": DISCOVERY_SCHEMA_VERSION,
            "reference_mmsi": self.reference_mmsi,
            "profile": self.profile.to_dict(),
            "request": self.request.to_dict(),
            "candidates": [item.to_dict() for item in self.candidates],
            "source": self.source,
        }

    def to_dict(self) -> dict[str, Any]:
        result = self._identity_dict()
        result["discovery_digest"] = self.discovery_digest
        result["candidate_count"] = self.candidate_count
        result["encounter_types"] = list(self.encounter_types)
        result["multi_ship"] = self.multi_ship
        return result


@dataclass(frozen=True)
class HistoricalAIST0Candidate:
    """Reviewable maneuver handoff proposal, not a counterfactual command."""

    reference_mmsi: int
    candidate_time_utc: datetime
    time_s: float
    detection_kind: str
    detection_profile_digest: str
    evidence_source_refs: tuple[HistoricalAISSourceObservationRef, ...] = ()
    heading_change_deg: float | None = None
    speed_change_mps: float | None = None

    def __post_init__(self) -> None:
        """Validate the proposed handoff timestamp and source evidence."""
        if self.candidate_time_utc.tzinfo is None:
            raise ValueError("candidate_time_utc must be timezone-aware")
        object.__setattr__(self, "candidate_time_utc", self.candidate_time_utc.astimezone(UTC))
        if not math.isfinite(float(self.time_s)):
            raise ValueError("T0 time_s must be finite")
        object.__setattr__(self, "evidence_source_refs", tuple(self.evidence_source_refs))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": T0_SCHEMA_VERSION,
            "reference_mmsi": self.reference_mmsi,
            "candidate_time_utc": self.candidate_time_utc.isoformat(),
            "time_s": self.time_s,
            "detection_kind": self.detection_kind,
            "detection_profile_digest": self.detection_profile_digest,
            "evidence_source_refs": [item.to_dict() for item in self.evidence_source_refs],
            "heading_change_deg": self.heading_change_deg,
            "speed_change_mps": self.speed_change_mps,
        }

    @property
    def digest(self) -> str:
        return _sha256_json(self.to_dict())


@dataclass(frozen=True)
class HistoricalAISNominalIntent:
    """Constant pre-T0 intent fit with an explicit future-leakage boundary."""

    reference_mmsi: int
    t0_utc: datetime
    t0_s: float
    course_rad: float
    speed_mps: float
    fit_error_m: float
    source_sample_count: int
    source_timestamps_utc: tuple[datetime, ...]
    source_observation_refs: tuple[HistoricalAISSourceObservationRef, ...]
    route_points_vxvy: tuple[tuple[float, float], ...]
    strict_pre_t0_only: bool = True
    intent_digest: str = ""

    def __post_init__(self) -> None:
        """Enforce strict pre-T0 source timestamps and freeze the intent fit."""
        if self.t0_utc.tzinfo is None:
            raise ValueError("t0_utc must be timezone-aware")
        object.__setattr__(self, "t0_utc", self.t0_utc.astimezone(UTC))
        if (
            not math.isfinite(float(self.t0_s))
            or self.t0_s < 0.0
            or not math.isfinite(float(self.course_rad))
            or not math.isfinite(float(self.speed_mps))
            or self.speed_mps < 0.0
            or not math.isfinite(float(self.fit_error_m))
            or self.fit_error_m < 0.0
        ):
            raise ValueError("intent fit values must be finite and non-negative")
        object.__setattr__(self, "source_timestamps_utc", tuple(item.astimezone(UTC) for item in self.source_timestamps_utc))
        object.__setattr__(self, "source_observation_refs", tuple(self.source_observation_refs))
        object.__setattr__(self, "route_points_vxvy", tuple(tuple(map(float, point)) for point in self.route_points_vxvy))
        if not all(math.isfinite(value) for point in self.route_points_vxvy for value in point):
            raise ValueError("intent route points must be finite")
        if not self.strict_pre_t0_only:
            raise ValueError("Historical Nominal Intent must be strict pre-T0-only")
        if any(timestamp >= self.t0_utc for timestamp in self.source_timestamps_utc):
            raise ValueError("Nominal Intent source timestamps must be strictly earlier than T0")
        if self.source_sample_count != len(self.source_timestamps_utc):
            raise ValueError("source_sample_count does not match source timestamps")
        if not self.intent_digest:
            object.__setattr__(self, "intent_digest", _sha256_json(self._identity_dict()))

    @property
    def max_source_timestamp_utc(self) -> datetime | None:
        return max(self.source_timestamps_utc, default=None)

    def _identity_dict(self) -> dict[str, Any]:
        return {
            "schema_version": INTENT_SCHEMA_VERSION,
            "reference_mmsi": self.reference_mmsi,
            "t0_utc": self.t0_utc.isoformat(),
            "t0_s": self.t0_s,
            "course_rad": self.course_rad,
            "speed_mps": self.speed_mps,
            "fit_error_m": self.fit_error_m,
            "source_sample_count": self.source_sample_count,
            "source_timestamps_utc": [item.isoformat() for item in self.source_timestamps_utc],
            "source_observation_refs": [item.to_dict() for item in self.source_observation_refs],
            "route_points_vxvy": [list(item) for item in self.route_points_vxvy],
            "strict_pre_t0_only": self.strict_pre_t0_only,
        }

    def to_dict(self) -> dict[str, Any]:
        result = self._identity_dict()
        result["intent_digest"] = self.intent_digest
        result["max_source_timestamp_utc"] = (
            self.max_source_timestamp_utc.isoformat() if self.max_source_timestamp_utc is not None else None
        )
        return result


@dataclass(frozen=True)
class HistoricalAISHumanReferenceBinding:
    """Sealed comparison-only identity for post-T0 Human Reference evidence."""

    artifact_digest: str | None = None
    sample_count: int = 0
    comparison_only: bool = True

    def __post_init__(self) -> None:
        """Validate comparison-only binding identity."""
        digest = self.artifact_digest.strip() if self.artifact_digest is not None else None
        count = int(self.sample_count)
        if count < 0:
            raise ValueError("Human Reference sample_count must be non-negative")
        if count and not digest:
            raise ValueError("Human Reference samples require an artifact digest")
        if not self.comparison_only:
            raise ValueError("Human Reference binding must remain comparison-only")
        object.__setattr__(self, "artifact_digest", digest or None)
        object.__setattr__(self, "sample_count", count)

    def to_dict(self) -> dict[str, object]:
        return {
            "artifact_digest": self.artifact_digest,
            "sample_count": self.sample_count,
            "comparison_only": self.comparison_only,
        }

    @property
    def bound(self) -> bool:
        return self.artifact_digest is not None


@dataclass(frozen=True)
class HistoricalAISCapabilityReceipt:
    """CapabilityCatalog-issued evidence for one exact execution tuple."""

    validation_rule_id: str
    scenario_id: str
    algorithm_id: str
    tracker_id: str
    catalog_schema_version: str
    evidence_hash: str
    evidence: Mapping[str, object]

    def __post_init__(self) -> None:
        """Freeze and verify exact-tuple capability evidence."""
        object.__setattr__(self, "evidence", MappingProxyType(dict(self.evidence)))
        if not all(
            value.strip()
            for value in (
                self.validation_rule_id,
                self.scenario_id,
                self.algorithm_id,
                self.tracker_id,
                self.catalog_schema_version,
                self.evidence_hash,
            )
        ):
            raise ValueError("capability receipt identity is required")
        if self.evidence_hash != _sha256_json(dict(self.evidence)):
            raise ValueError("capability receipt evidence hash mismatch")

    @classmethod
    def from_catalog(
        cls,
        catalog: CapabilityCatalog,
        validation_rule_id: str,
        scenario_id: str,
        algorithm_id: str,
        tracker_id: str,
    ) -> HistoricalAISCapabilityReceipt:
        """Validate and seal one exact tuple from the live CapabilityCatalog."""
        from colav_simulator.experiment.capabilities import CAPABILITY_SCHEMA_VERSION  # noqa: PLC0415

        catalog.validate(validation_rule_id, scenario_id, algorithm_id, tracker_id)
        document = catalog.document([], validation_rule_id)
        exact = next(
            item
            for item in document["selectable_combinations"]
            if (
                item["validation_rule_id"],
                item["scenario_id"],
                item["algorithm_id"],
                item["tracker_id"],
            )
            == (validation_rule_id, scenario_id, algorithm_id, tracker_id)
        )
        return cls(
            validation_rule_id,
            scenario_id,
            algorithm_id,
            tracker_id,
            CAPABILITY_SCHEMA_VERSION,
            _sha256_json(exact),
            exact,
        )

    @property
    def exact_tuple(self) -> tuple[str, str, str, str]:
        return (self.validation_rule_id, self.scenario_id, self.algorithm_id, self.tracker_id)

    def to_dict(self) -> dict[str, object]:
        return {
            "exact_tuple": list(self.exact_tuple),
            "catalog_schema_version": self.catalog_schema_version,
            "evidence_hash": self.evidence_hash,
            "evidence": dict(self.evidence),
        }


@dataclass(frozen=True)
class HistoricalAISAlgorithmBinding:
    """Frozen requested algorithm/configuration identity for the Case."""

    algorithm_id: str = "UNBOUND"
    configuration_digest: str | None = None
    capability_evidence_digest: str | None = None
    capability_receipt: HistoricalAISCapabilityReceipt | None = None

    def __post_init__(self) -> None:
        """Validate frozen algorithm identity."""
        if not self.algorithm_id.strip():
            raise ValueError("algorithm_id is required")

    def to_dict(self) -> dict[str, object]:
        return {
            "algorithm_id": self.algorithm_id,
            "configuration_digest": self.configuration_digest,
            "capability_evidence_digest": self.capability_evidence_digest,
            "capability_receipt": self.capability_receipt.to_dict() if self.capability_receipt else None,
        }

    @property
    def bound(self) -> bool:
        return (
            self.algorithm_id != "UNBOUND"
            and self.configuration_digest is not None
            and self.capability_receipt is not None
            and self.capability_receipt.algorithm_id == self.algorithm_id
            and self.capability_evidence_digest == self.capability_receipt.evidence_hash
        )


@dataclass(frozen=True)
class HistoricalAISEvaluationBinding:
    """Frozen Independent Evaluator identity for the Case."""

    evaluator_id: str = "UNBOUND"
    profile_id: str = "UNBOUND"
    profile_digest: str | None = None

    def __post_init__(self) -> None:
        """Validate frozen Evaluator identity."""
        if not self.evaluator_id.strip() or not self.profile_id.strip():
            raise ValueError("Evaluator identity and profile are required")

    def to_dict(self) -> dict[str, object]:
        return {
            "evaluator_id": self.evaluator_id,
            "profile_id": self.profile_id,
            "profile_digest": self.profile_digest,
        }

    @property
    def bound(self) -> bool:
        return self.evaluator_id != "UNBOUND" and self.profile_id != "UNBOUND" and self.profile_digest is not None


@dataclass(frozen=True)
class HistoricalAISCompareBinding:
    """Frozen comparison contract/alignment identity for the Case."""

    contract_id: str = "historical-benchmark-compare.v1"
    alignment_profile: Mapping[str, object] = field(default_factory=dict)
    alignment_profile_digest: str | None = None

    def __post_init__(self) -> None:
        """Validate frozen comparison identity."""
        if not self.contract_id.strip():
            raise ValueError("comparison contract_id is required")
        object.__setattr__(self, "alignment_profile", MappingProxyType(dict(self.alignment_profile)))
        if self.alignment_profile and self.alignment_profile_digest != _sha256_json(dict(self.alignment_profile)):
            raise ValueError("comparison alignment profile digest mismatch")

    def to_dict(self) -> dict[str, object]:
        return {
            "contract_id": self.contract_id,
            "alignment_profile": dict(self.alignment_profile),
            "alignment_profile_digest": self.alignment_profile_digest,
        }

    @property
    def bound(self) -> bool:
        return bool(self.alignment_profile) and self.alignment_profile_digest is not None


@dataclass(frozen=True)
class HistoricalAISCaseBuildRequest:
    """Inputs for the public Historical AIS Case Builder seam."""

    dataset: HistoricalAISReadResult
    enc_profile: ENCRegionProfile | None = None
    selection: HistoricalAISSelection | None = None
    reconstruction_profile: HistoricalAISReconstructionProfile = field(default_factory=HistoricalAISReconstructionProfile)
    discovery_profile: HistoricalAISDiscoveryProfile = field(default_factory=HistoricalAISDiscoveryProfile)
    discovery_request: HistoricalAISDiscoveryRequest = field(default_factory=HistoricalAISDiscoveryRequest)
    maneuver_detection_profile: HistoricalAISManeuverDetectionProfile = field(
        default_factory=HistoricalAISManeuverDetectionProfile
    )
    reference_mmsi: int | None = None
    reference_vessel_mmsi: int | None = None
    t0_utc: datetime | str | None = None
    require_intent: bool = True
    published: bool | None = None
    dimension_overrides: Mapping[int, Mapping[str, Any]] = field(default_factory=dict)
    human_reference_binding: HistoricalAISHumanReferenceBinding = field(default_factory=HistoricalAISHumanReferenceBinding)
    algorithm_binding: HistoricalAISAlgorithmBinding = field(default_factory=HistoricalAISAlgorithmBinding)
    evaluation_binding: HistoricalAISEvaluationBinding = field(default_factory=HistoricalAISEvaluationBinding)
    compare_binding: HistoricalAISCompareBinding = field(default_factory=HistoricalAISCompareBinding)

    def __post_init__(self) -> None:
        """Normalize request aliases and reject ambiguous Reference Vessel IDs."""
        if self.selection is not None and not isinstance(self.selection, HistoricalAISSelection):
            raise TypeError("selection must be HistoricalAISSelection")
        if self.t0_utc is not None:
            object.__setattr__(self, "t0_utc", _coerce_utc(self.t0_utc))
        if self.published is not None:
            object.__setattr__(self, "require_intent", bool(self.published))
        object.__setattr__(
            self,
            "dimension_overrides",
            MappingProxyType({int(key): MappingProxyType(dict(value)) for key, value in self.dimension_overrides.items()}),
        )
        if (
            self.reference_mmsi is not None
            and self.reference_vessel_mmsi is not None
            and int(self.reference_mmsi) != int(self.reference_vessel_mmsi)
        ):
            raise ValueError("reference_mmsi and reference_vessel_mmsi disagree")
        requested = self.reference_mmsi
        if requested is None:
            requested = self.reference_vessel_mmsi
        if requested is None:
            requested = self.discovery_request.reference_mmsi
        if requested is not None:
            requested = int(requested)
            if requested < 0:
                raise ValueError("reference_mmsi must be non-negative")
        object.__setattr__(self, "reference_mmsi", requested)
        object.__setattr__(self, "reference_vessel_mmsi", requested)

    @property
    def dataset_descriptor(self) -> HistoricalAISDatasetDescriptor:
        return self.dataset.descriptor

    @property
    def reconstruction_digest(self) -> str:
        return self.reconstruction_profile.digest


@dataclass(frozen=True)
class HistoricalAISCase:
    """Published immutable Dataset → Case evidence binding."""

    dataset_descriptor: HistoricalAISDatasetDescriptor
    selection: HistoricalAISSelection
    reconstruction_profile: HistoricalAISReconstructionProfile
    actor_set: HistoricalActorSet
    reference_actor_id: int
    reference_mmsi: int
    traffic_actor_ids: tuple[int, ...]
    discovery_profile: HistoricalAISDiscoveryProfile
    discovery_request: HistoricalAISDiscoveryRequest
    discovery: HistoricalAISDiscoveryResult
    enc_profile: ENCRegionProfile
    enc_preflight: ENCPreflightResult
    maneuver_detection_profile: HistoricalAISManeuverDetectionProfile
    t0_candidate: HistoricalAIST0Candidate | None
    nominal_intent: HistoricalAISNominalIntent | None
    source_quality_findings: tuple[Mapping[str, Any], ...]
    human_reference_binding: HistoricalAISHumanReferenceBinding = field(default_factory=HistoricalAISHumanReferenceBinding)
    algorithm_binding: HistoricalAISAlgorithmBinding = field(default_factory=HistoricalAISAlgorithmBinding)
    evaluation_binding: HistoricalAISEvaluationBinding = field(default_factory=HistoricalAISEvaluationBinding)
    compare_binding: HistoricalAISCompareBinding = field(default_factory=HistoricalAISCompareBinding)
    dimension_overrides: tuple[Mapping[str, Any], ...] = ()
    published: bool = True
    build_digest: str = ""
    runtime_digest: str = ""
    schema_version: str = CASE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        """Freeze selected actor IDs, quality mappings and the Case digest."""
        object.__setattr__(self, "traffic_actor_ids", tuple(sorted(set(self.traffic_actor_ids))))
        object.__setattr__(
            self,
            "source_quality_findings",
            tuple(MappingProxyType(dict(item)) for item in self.source_quality_findings),
        )
        object.__setattr__(
            self,
            "dimension_overrides",
            tuple(MappingProxyType(dict(item)) for item in self.dimension_overrides),
        )
        if not self.build_digest:
            object.__setattr__(self, "build_digest", _sha256_json(self._identity_dict()))
        if not self.runtime_digest:
            object.__setattr__(self, "runtime_digest", _sha256_json(self._runtime_identity_dict()))

    @property
    def dataset(self) -> HistoricalAISDatasetDescriptor:
        return self.dataset_descriptor

    @property
    def reference_actor(self) -> HistoricalActor:
        return self.actor_set.actor(self.reference_actor_id)

    @property
    def reference_vessel(self) -> HistoricalActor:
        return self.reference_actor

    @property
    def is_draft(self) -> bool:
        return not self.published

    @property
    def traffic_actors(self) -> tuple[HistoricalActor, ...]:
        return tuple(self.actor_set.actor(actor_id) for actor_id in self.traffic_actor_ids)

    @property
    def traffic_actor_mmsis(self) -> tuple[int, ...]:
        return tuple(actor.mmsi for actor in self.traffic_actors)

    @property
    def dataset_digest(self) -> str:
        return self.dataset_descriptor.descriptor_sha256

    @property
    def dataset_descriptor_digest(self) -> str:
        return self.dataset_digest

    @property
    def case_digest(self) -> str:
        return self.runtime_digest

    @property
    def case_runtime_digest(self) -> str:
        return self.runtime_digest

    @property
    def runtime_actor_set_digest(self) -> str:
        return self.runtime_actor_set().semantic_digest

    @property
    def reference_vessel_mmsi(self) -> int:
        return self.reference_mmsi

    @property
    def t0_utc(self) -> datetime | None:
        return self.t0_candidate.candidate_time_utc if self.t0_candidate is not None else None

    @property
    def intent(self) -> HistoricalAISNominalIntent | None:
        return self.nominal_intent

    @property
    def discovery_metadata(self) -> HistoricalAISDiscoveryResult:
        return self.discovery

    @property
    def t0_evidence(self) -> HistoricalAIST0Candidate | None:
        return self.t0_candidate

    @property
    def reconstruction_digest(self) -> str:
        return self.reconstruction_profile.digest

    @property
    def enc_profile_digest(self) -> str:
        return self.enc_profile.profile_digest

    def runtime_actor_set(self) -> HistoricalActorSet:
        """Return runtime world facts with Reference history sealed at T0."""
        if self.t0_candidate is None:
            return self.actor_set
        ordered = (self.reference_actor, *self.traffic_actors)
        actors = tuple(
            _runtime_actor(actor, actor_id, self.t0_candidate.time_s, actor.mmsi == self.reference_mmsi)
            for actor_id, actor in enumerate(ordered)
        )
        return HistoricalActorSet(
            dataset_digest=self.dataset_digest,
            selection_digest=self.selection.digest,
            profile=self.reconstruction_profile,
            time_origin_utc=self.actor_set.time_origin_utc,
            actors=actors,
            provider=self.actor_set.provider,
            attribution=self.actor_set.attribution,
            coverage_limitations=self.actor_set.coverage_limitations,
        )

    def _runtime_identity_dict(self) -> dict[str, Any]:
        """Semantic runtime identity; excludes Human Reference/post-T0 source evidence."""
        return {
            "schema_version": self.schema_version,
            "selection": self.selection.to_dict(),
            "reconstruction_profile": self.reconstruction_profile.to_dict(),
            "actor_set": self.runtime_actor_set().to_dict(),
            "reference_actor_id": 0,
            "reference_mmsi": self.reference_mmsi,
            "traffic_actor_count": len(self.traffic_actor_ids),
            "discovery_profile": self.discovery_profile.to_dict(),
            "discovery_request": self.discovery_request.to_dict(),
            "enc_profile": self.enc_profile.to_dict(),
            "maneuver_detection_profile": self.maneuver_detection_profile.to_dict(),
            "t0_candidate": self.t0_candidate.to_dict() if self.t0_candidate is not None else None,
            "nominal_intent": self.nominal_intent.to_dict() if self.nominal_intent is not None else None,
            "algorithm_binding": self.algorithm_binding.to_dict(),
            "evaluation_binding": self.evaluation_binding.to_dict(),
            "compare_binding": self.compare_binding.to_dict(),
            "dimension_overrides": [dict(item) for item in self.dimension_overrides],
            "published": self.published,
        }

    def _identity_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "dataset": self.dataset_descriptor.to_dict(),
            "selection": self.selection.to_dict(),
            "reconstruction_profile": self.reconstruction_profile.to_dict(),
            "actor_set": self.actor_set.to_dict(),
            "reference_actor_id": self.reference_actor_id,
            "reference_mmsi": self.reference_mmsi,
            "traffic_actor_ids": list(self.traffic_actor_ids),
            "discovery_profile": self.discovery_profile.to_dict(),
            "discovery_request": self.discovery_request.to_dict(),
            "discovery": self.discovery.to_dict(),
            "enc_profile": self.enc_profile.to_dict(),
            "enc_preflight": self.enc_preflight.to_dict(),
            "maneuver_detection_profile": self.maneuver_detection_profile.to_dict(),
            "t0_candidate": self.t0_candidate.to_dict() if self.t0_candidate is not None else None,
            "nominal_intent": self.nominal_intent.to_dict() if self.nominal_intent is not None else None,
            "source_quality_findings": [dict(item) for item in self.source_quality_findings],
            "human_reference_binding": self.human_reference_binding.to_dict(),
            "algorithm_binding": self.algorithm_binding.to_dict(),
            "evaluation_binding": self.evaluation_binding.to_dict(),
            "compare_binding": self.compare_binding.to_dict(),
            "dimension_overrides": [dict(item) for item in self.dimension_overrides],
            "published": self.published,
        }

    def to_dict(self) -> dict[str, Any]:
        result = self._identity_dict()
        result["build_digest"] = self.build_digest
        result["runtime_digest"] = self.runtime_digest
        return result


@dataclass(frozen=True)
class HistoricalAISCaseBuildOutcome:
    """Immutable typed success/failure result returned by ``build``."""

    status: HistoricalAISCaseBuildStatus
    case: HistoricalAISCase | None = None
    message: str = ""
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate that typed success and failure carry the right payload."""
        object.__setattr__(self, "status", HistoricalAISCaseBuildStatus(self.status))
        object.__setattr__(self, "details", MappingProxyType(dict(self.details)))
        if self.status is HistoricalAISCaseBuildStatus.SUCCESS and self.case is None:
            raise ValueError("successful Case build requires a case")
        if self.status is not HistoricalAISCaseBuildStatus.SUCCESS and self.case is not None:
            raise ValueError("failed Case build cannot expose a case")

    @property
    def success(self) -> bool:
        return self.status is HistoricalAISCaseBuildStatus.SUCCESS

    @property
    def failure_code(self) -> str | None:
        return None if self.success else self.status.value

    @property
    def reason(self) -> str:
        return self.message or self.status.value

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "success": self.success,
            "failure_code": self.failure_code,
            "message": self.message,
            "details": _jsonable(dict(self.details)),
            "case": self.case.to_dict() if self.case is not None else None,
        }


class HistoricalAISCaseBuilder:
    """Build deterministic discovery metadata and a qualified Historical Case."""

    def build(  # noqa: C901, PLR0911, PLR0912
        self, request: HistoricalAISCaseBuildRequest
    ) -> HistoricalAISCaseBuildOutcome:
        """Build one immutable Case through the public contract seam."""
        try:
            if not isinstance(request, HistoricalAISCaseBuildRequest):
                return self._failure(HistoricalAISCaseBuildStatus.INVALID_REQUEST, "request type is invalid")
            if not isinstance(request.dataset, HistoricalAISReadResult):
                return self._failure(HistoricalAISCaseBuildStatus.INVALID_REQUEST, "dataset read result is required")
            selection = request.selection or HistoricalAISSelection()
            if selection.digest != request.dataset.descriptor.selection_sha256:
                return self._failure(
                    HistoricalAISCaseBuildStatus.INVALID_REQUEST,
                    "Case selection does not match the Dataset Descriptor selection digest",
                    selection_digest=selection.digest,
                    dataset_selection_digest=request.dataset.descriptor.selection_sha256,
                )
            actor_set = HistoricalAISReconstructor().reconstruct(request.dataset, request.reconstruction_profile)
            actor_set = apply_dimension_overrides(actor_set, request.dimension_overrides)
        except (TypeError, ValueError, KeyError) as exc:
            return self._failure(HistoricalAISCaseBuildStatus.INVALID_REQUEST, str(exc))

        reference_mmsi = self._select_reference_mmsi(request, actor_set)
        if reference_mmsi is None:
            return self._failure(
                HistoricalAISCaseBuildStatus.REFERENCE_VESSEL_UNAVAILABLE,
                "Reference Vessel is not present in reconstructed actors",
            )
        reference_actor = next((actor for actor in actor_set.actors if actor.mmsi == reference_mmsi), None)
        if reference_actor is None:
            return self._failure(
                HistoricalAISCaseBuildStatus.REFERENCE_VESSEL_UNAVAILABLE,
                f"Reference Vessel MMSI {reference_mmsi} is unavailable",
                reference_mmsi=reference_mmsi,
            )

        eligible_mmsis = self._eligible_mmsis(request.dataset, request.discovery_request)
        candidates = self._discover_candidates(
            actor_set,
            reference_actor,
            request.discovery_profile,
            request.discovery_request,
            eligible_mmsis,
        )
        if not candidates:
            if self._has_insufficient_time_coverage(
                actor_set,
                reference_actor,
                request.discovery_profile,
                request.discovery_request,
                eligible_mmsis,
            ):
                return self._failure(
                    HistoricalAISCaseBuildStatus.TIME_COVERAGE_INSUFFICIENT,
                    "A near-vessel candidate does not meet the minimum common time coverage",
                    reference_mmsi=reference_mmsi,
                    minimum_duration_s=request.discovery_profile.min_duration_s,
                )
            return self._failure(
                HistoricalAISCaseBuildStatus.NO_ENCOUNTER,
                "No discovery encounter candidate matched the selected window",
                reference_mmsi=reference_mmsi,
            )
        invalid_initial_separation = tuple(
            candidate.target_mmsi
            for candidate in candidates
            if candidate.initial_range_m < request.discovery_profile.min_initial_separation_m
        )
        if invalid_initial_separation:
            return self._failure(
                HistoricalAISCaseBuildStatus.INITIAL_SEPARATION_INVALID,
                "Selected actors overlap at the first common historical sample",
                target_mmsi=invalid_initial_separation,
                minimum_initial_separation_m=request.discovery_profile.min_initial_separation_m,
            )
        discovery = HistoricalAISDiscoveryResult(
            reference_mmsi=reference_mmsi,
            profile=request.discovery_profile,
            request=request.discovery_request,
            candidates=candidates,
        )
        target_mmsis = tuple(sorted({candidate.target_mmsi for candidate in candidates}))
        selected_mmsis = (reference_mmsi, *target_mmsis)

        missing_dimensions = tuple(
            actor.mmsi for actor in actor_set.actors if actor.mmsi in selected_mmsis and not actor.dimensions_known
        )
        if missing_dimensions:
            return self._failure(
                HistoricalAISCaseBuildStatus.DIMENSIONS_UNAVAILABLE,
                "Selected actors lack proven source dimensions",
                missing_mmsi=missing_dimensions,
                discovery_candidate_count=len(candidates),
                discovery_target_mmsi=target_mmsis,
                discovery_labels=tuple(sorted({candidate.label for candidate in candidates})),
                discovery_multi_ship=len(candidates) > 1,
            )

        if request.enc_profile is None:
            return self._failure(
                HistoricalAISCaseBuildStatus.ENC_UNQUALIFIED,
                "An ENCRegionProfile is required for a Published HistoricalAISCase",
            )
        enc_result = self._preflight_enc(request.dataset, selected_mmsis, request.enc_profile)
        if not enc_result.qualified:
            return self._failure(
                HistoricalAISCaseBuildStatus.ENC_UNQUALIFIED,
                f"ENC preflight status is {enc_result.status.value}",
                enc_preflight=enc_result.to_dict(),
            )

        t0_candidate = self._detect_t0(
            request.dataset,
            actor_set,
            reference_actor,
            request.maneuver_detection_profile,
            request.t0_utc,
        )
        nominal_intent = None
        if request.require_intent:
            if t0_candidate is None:
                return self._failure(
                    HistoricalAISCaseBuildStatus.INTENT_NOT_ESTABLISHED,
                    "No reviewable T0 candidate was established",
                    reference_mmsi=reference_mmsi,
                )
            nominal_intent = self._fit_nominal_intent(
                reference_actor,
                t0_candidate,
                request.discovery_profile,
            )
            if nominal_intent is None:
                return self._failure(
                    HistoricalAISCaseBuildStatus.INTENT_NOT_ESTABLISHED,
                    "Insufficient strictly pre-T0 Reference Vessel evidence",
                    reference_mmsi=reference_mmsi,
                    t0_utc=t0_candidate.candidate_time_utc.isoformat(),
                )

        source_quality = tuple(
            finding.to_dict()
            for finding in request.dataset.descriptor.quality_findings
            if finding.mmsi is None or finding.mmsi in selected_mmsis
        )
        error_findings = tuple(item for item in source_quality if item.get("severity") == "ERROR")
        if len(error_findings) > request.discovery_profile.max_quality_errors:
            return self._failure(
                HistoricalAISCaseBuildStatus.SOURCE_QUALITY_UNAVAILABLE,
                "Selected actors exceed the discovery profile quality-error budget",
                quality_error_count=len(error_findings),
            )

        published = request.published if request.published is not None else request.require_intent
        if published:
            bindings = {
                "human_reference": request.human_reference_binding.bound,
                "algorithm": request.algorithm_binding.bound,
                "evaluation": request.evaluation_binding.bound,
                "compare": request.compare_binding.bound,
            }
            unbound = tuple(sorted(name for name, bound in bindings.items() if not bound))
            if unbound:
                return self._failure(
                    HistoricalAISCaseBuildStatus.BINDINGS_UNAVAILABLE,
                    "Published HistoricalAISCase requires frozen benchmark bindings",
                    unbound_bindings=unbound,
                )

        traffic_actor_ids = tuple(sorted(actor.actor_id for actor in actor_set.actors if actor.mmsi in target_mmsis))
        case = HistoricalAISCase(
            dataset_descriptor=request.dataset.descriptor,
            selection=selection,
            reconstruction_profile=request.reconstruction_profile,
            actor_set=actor_set,
            reference_actor_id=reference_actor.actor_id,
            reference_mmsi=reference_mmsi,
            traffic_actor_ids=traffic_actor_ids,
            discovery_profile=request.discovery_profile,
            discovery_request=request.discovery_request,
            discovery=discovery,
            enc_profile=request.enc_profile,
            enc_preflight=enc_result,
            maneuver_detection_profile=request.maneuver_detection_profile,
            t0_candidate=t0_candidate,
            nominal_intent=nominal_intent,
            source_quality_findings=source_quality,
            human_reference_binding=request.human_reference_binding,
            algorithm_binding=request.algorithm_binding,
            evaluation_binding=request.evaluation_binding,
            compare_binding=request.compare_binding,
            dimension_overrides=tuple(dict(value) for value in request.dimension_overrides.values()),
            published=published,
        )
        return HistoricalAISCaseBuildOutcome(HistoricalAISCaseBuildStatus.SUCCESS, case=case)

    @staticmethod
    def _failure(status: HistoricalAISCaseBuildStatus, message: str, **details: Any) -> HistoricalAISCaseBuildOutcome:
        return HistoricalAISCaseBuildOutcome(status=status, message=message, details=details)

    @staticmethod
    def _select_reference_mmsi(request: HistoricalAISCaseBuildRequest, actor_set: HistoricalActorSet) -> int | None:
        requested = request.reference_mmsi or request.discovery_request.reference_mmsi
        if requested is not None:
            return requested if any(actor.mmsi == requested for actor in actor_set.actors) else None
        actor = min(actor_set.actors, key=lambda item: (-item.observed_source_points, item.mmsi))
        return actor.mmsi if actor_set.actors else None

    @staticmethod
    def _has_insufficient_time_coverage(
        actor_set: HistoricalActorSet,
        reference_actor: HistoricalActor,
        profile: HistoricalAISDiscoveryProfile,
        request: HistoricalAISDiscoveryRequest,
        eligible_mmsis: set[int] | None = None,
    ) -> bool:
        allowed_targets = set(request.target_mmsi)
        for target in actor_set.actors:
            if target.mmsi == reference_actor.mmsi or (allowed_targets and target.mmsi not in allowed_targets):
                continue
            if eligible_mmsis is not None and target.mmsi not in eligible_mmsis:
                continue
            statistics = _pair_statistics(reference_actor, target)
            if statistics is None:
                continue
            if (
                statistics["closest_approach_m"] <= profile.max_encounter_range_m
                and statistics["max_closing_speed_mps"] >= profile.min_closing_speed_mps
                and statistics["duration_s"] < profile.min_duration_s
            ):
                return True
        return False

    def _discover_candidates(  # noqa: PLR0912
        self,
        actor_set: HistoricalActorSet,
        reference_actor: HistoricalActor,
        profile: HistoricalAISDiscoveryProfile,
        request: HistoricalAISDiscoveryRequest,
        eligible_mmsis: set[int] | None = None,
    ) -> tuple[HistoricalAISDiscoveryCandidate, ...]:
        allowed_targets = set(request.target_mmsi)
        allowed_types = set(request.encounter_types)
        include_stationary = profile.include_stationary if request.include_stationary is None else request.include_stationary
        candidates: list[HistoricalAISDiscoveryCandidate] = []
        for target in actor_set.actors:
            if target.mmsi == reference_actor.mmsi or (allowed_targets and target.mmsi not in allowed_targets):
                continue
            if eligible_mmsis is not None and target.mmsi not in eligible_mmsis:
                continue
            statistics = _pair_statistics(reference_actor, target)
            if statistics is None:
                continue
            if statistics["duration_s"] < profile.min_duration_s:
                continue
            if (
                statistics["reference_track_distance_m"] < profile.min_track_distance_m
                or statistics["target_track_distance_m"] < profile.min_track_distance_m
            ):
                continue
            if not include_stationary and (
                statistics["reference_speed_mps"] < profile.stationary_speed_mps
                or statistics["target_speed_mps"] < profile.stationary_speed_mps
            ):
                continue
            if statistics["max_closing_speed_mps"] < profile.min_closing_speed_mps:
                continue
            if statistics["closest_approach_m"] > profile.max_encounter_range_m:
                continue
            if (
                request.max_closest_approach_m is not None
                and statistics["closest_approach_m"] > request.max_closest_approach_m
            ):
                continue
            if request.max_signed_tcpa_s is not None and (
                statistics["signed_tcpa_s"] is None or statistics["signed_tcpa_s"] > request.max_signed_tcpa_s
            ):
                continue
            encounter_type = _classify_discovery(statistics, profile)
            if encounter_type is None or (allowed_types and encounter_type.value not in allowed_types):
                continue
            candidates.append(
                HistoricalAISDiscoveryCandidate(
                    reference_mmsi=reference_actor.mmsi,
                    target_mmsi=target.mmsi,
                    encounter_type=encounter_type,
                    candidate_time_utc=actor_set.time_origin_utc + timedelta(seconds=statistics["candidate_time_s"]),
                    common_duration_s=statistics["duration_s"],
                    initial_range_m=statistics["initial_range_m"],
                    closest_approach_m=statistics["closest_approach_m"],
                    signed_tcpa_s=statistics["signed_tcpa_s"],
                    max_closing_speed_mps=statistics["max_closing_speed_mps"],
                    reference_track_distance_m=statistics["reference_track_distance_m"],
                    target_track_distance_m=statistics["target_track_distance_m"],
                )
            )
        candidates.sort(key=lambda item: (item.candidate_time_utc, item.closest_approach_m, item.target_mmsi))
        if request.max_candidates is not None:
            candidates = candidates[: request.max_candidates]
        count = len(candidates)
        return tuple(replace(candidate, multi_ship=count > 1, concurrent_target_count=count) for candidate in candidates)

    @staticmethod
    def _eligible_mmsis(dataset: HistoricalAISReadResult, request: HistoricalAISDiscoveryRequest) -> set[int] | None:
        filters = request.vessel_types or request.ais_classes or request.status_values
        if not filters:
            return None
        allowed: set[int] = set()
        for observation in dataset.observations:
            mmsi = observation.normalized.mmsi
            if mmsi is None:
                continue
            raw = {str(key).lower(): value for key, value in observation.raw.values.items()}
            matches = True
            if request.vessel_types:
                value = raw.get("vessel_type", raw.get("type"))
                matches = matches and value is not None and str(value) in request.vessel_types
            if request.ais_classes:
                matches = matches and str(raw.get("ais_class")) in request.ais_classes
            if request.status_values:
                matches = matches and str(raw.get("status")) in request.status_values
            if matches:
                allowed.add(mmsi)
        return allowed

    @staticmethod
    def _preflight_enc(
        dataset: HistoricalAISReadResult, selected_mmsis: Sequence[int], profile: ENCRegionProfile
    ) -> ENCPreflightResult:
        positions = tuple(
            (
                f"{observation.raw.entry_name}:{observation.raw.source_row_index}",
                float(observation.normalized.longitude_deg),
                float(observation.normalized.latitude_deg),
            )
            for observation in dataset.observations
            if observation.normalized.mmsi in selected_mmsis
            and observation.normalized.longitude_deg is not None
            and observation.normalized.latitude_deg is not None
        )
        return profile.preflight(ENCPreflightRequest(positions=positions, input_crs=dataset.descriptor.normalized_crs))

    @staticmethod
    def _detect_t0(
        dataset: HistoricalAISReadResult,
        actor_set: HistoricalActorSet,
        reference_actor: HistoricalActor,
        profile: HistoricalAISManeuverDetectionProfile,
        explicit_t0: datetime | None,
    ) -> HistoricalAIST0Candidate | None:
        if explicit_t0 is not None:
            observed_timestamps = tuple(
                sample.timestamp_utc
                for sample in reference_actor.samples
                if sample.kind is HistoricalActorSampleKind.OBSERVED
            )
            if (
                not observed_timestamps
                or explicit_t0 < min(observed_timestamps)
                or explicit_t0 > max(observed_timestamps)
                or sum(timestamp < explicit_t0 for timestamp in observed_timestamps) < profile.min_pre_samples
                or sum(timestamp > explicit_t0 for timestamp in observed_timestamps) < profile.min_post_samples
            ):
                return None
            time_s = (explicit_t0 - actor_set.time_origin_utc).total_seconds()
            refs = tuple(
                HistoricalAISSourceObservationRef.from_observation(observation)
                for observation in dataset.observations
                if observation.normalized.mmsi == reference_actor.mmsi
                and observation.normalized.timestamp_utc is not None
                and observation.normalized.timestamp_utc == explicit_t0
            )
            return HistoricalAIST0Candidate(
                reference_mmsi=reference_actor.mmsi,
                candidate_time_utc=explicit_t0,
                time_s=time_s,
                detection_kind="EXPLICIT_REVIEW_CANDIDATE",
                detection_profile_digest=profile.digest,
                evidence_source_refs=refs,
            )
        observed = tuple(sample for sample in reference_actor.samples if sample.kind is HistoricalActorSampleKind.OBSERVED)
        for index in range(max(1, profile.min_pre_samples), len(observed)):
            if len(observed) - index - 1 < profile.min_post_samples:
                break
            before = observed[index - profile.min_pre_samples]
            current = observed[index]
            if current.timestamp_utc <= before.timestamp_utc:
                continue
            before_course = math.atan2(before.state_vxvy[3], before.state_vxvy[2])
            current_course = math.atan2(current.state_vxvy[3], current.state_vxvy[2])
            heading_change = abs(math.degrees(_angle_delta(current_course, before_course)))
            before_speed = math.hypot(before.state_vxvy[2], before.state_vxvy[3])
            current_speed = math.hypot(current.state_vxvy[2], current.state_vxvy[3])
            speed_change = abs(current_speed - before_speed)
            if heading_change < profile.heading_change_deg and speed_change < profile.speed_change_mps:
                continue
            refs = tuple(ref for sample in (before, current) for ref in sample.source_observation_refs)
            return HistoricalAIST0Candidate(
                reference_mmsi=reference_actor.mmsi,
                candidate_time_utc=current.timestamp_utc,
                time_s=current.time_s,
                detection_kind="MANEUVER_CHANGE",
                detection_profile_digest=profile.digest,
                evidence_source_refs=refs,
                heading_change_deg=heading_change,
                speed_change_mps=speed_change,
            )
        return None

    @staticmethod
    def _fit_nominal_intent(
        reference_actor: HistoricalActor,
        t0: HistoricalAIST0Candidate,
        profile: HistoricalAISDiscoveryProfile,
    ) -> HistoricalAISNominalIntent | None:
        samples = tuple(
            sample
            for sample in reference_actor.samples
            if sample.kind is HistoricalActorSampleKind.OBSERVED and sample.timestamp_utc < t0.candidate_time_utc
        )
        if len(samples) < profile.min_pre_t0_samples:
            return None
        duration = (samples[-1].timestamp_utc - samples[0].timestamp_utc).total_seconds()
        if duration < profile.min_pre_t0_duration_s:
            return None
        first = samples[0]
        last = samples[-1]
        north_delta = last.state_vxvy[0] - first.state_vxvy[0]
        east_delta = last.state_vxvy[1] - first.state_vxvy[1]
        distance = math.hypot(north_delta, east_delta)
        speed = distance / duration if duration > 0.0 else 0.0
        course = math.atan2(east_delta, north_delta) if distance > 1e-9 else 0.0
        fit_error = _constant_velocity_fit_error(samples, speed, course)
        return HistoricalAISNominalIntent(
            reference_mmsi=reference_actor.mmsi,
            t0_utc=t0.candidate_time_utc,
            t0_s=t0.time_s,
            course_rad=course,
            speed_mps=speed,
            fit_error_m=fit_error,
            source_sample_count=len(samples),
            source_timestamps_utc=tuple(sample.timestamp_utc for sample in samples),
            source_observation_refs=tuple(ref for sample in samples for ref in sample.source_observation_refs),
            route_points_vxvy=((first.state_vxvy[0], first.state_vxvy[1]), (last.state_vxvy[0], last.state_vxvy[1])),
        )


def _pair_statistics(reference: HistoricalActor, target: HistoricalActor) -> dict[str, float] | None:
    samples: list[tuple[float, tuple[float, float, float, float], tuple[float, float, float, float]]] = []
    for reference_sample in reference.samples:
        target_sample = target.sample_at(reference_sample.time_s)
        if target_sample is not None:
            samples.append((reference_sample.time_s, reference_sample.state_vxvy, target_sample.state_vxvy))
    if len(samples) < 2:
        return None
    first_time = samples[0][0]
    last_time = samples[-1][0]
    duration = last_time - first_time
    if duration < 0.0:
        return None
    first_ref = samples[0][1]
    first_target = samples[0][2]
    initial_range = math.hypot(first_target[0] - first_ref[0], first_target[1] - first_ref[1])
    closest = None
    max_closing = 0.0
    ref_distance = 0.0
    target_distance = 0.0
    previous = None
    for time_s, ref_state, target_state in samples:
        if previous is not None:
            ref_distance += math.hypot(ref_state[0] - previous[1][0], ref_state[1] - previous[1][1])
            target_distance += math.hypot(target_state[0] - previous[2][0], target_state[1] - previous[2][1])
        previous = (time_s, ref_state, target_state)
        rel_north = target_state[0] - ref_state[0]
        rel_east = target_state[1] - ref_state[1]
        rel_v_north = target_state[2] - ref_state[2]
        rel_v_east = target_state[3] - ref_state[3]
        range_m = math.hypot(rel_north, rel_east)
        if range_m > 1e-9:
            closing = -(rel_north * rel_v_north + rel_east * rel_v_east) / range_m
            max_closing = max(max_closing, closing)
        rel_speed_sq = rel_v_north * rel_v_north + rel_v_east * rel_v_east
        signed_tcpa = -(rel_north * rel_v_north + rel_east * rel_v_east) / rel_speed_sq if rel_speed_sq > 1e-12 else None
        predicted = (
            math.hypot(
                rel_north + rel_v_north * max(0.0, signed_tcpa or 0.0),
                rel_east + rel_v_east * max(0.0, signed_tcpa or 0.0),
            )
            if signed_tcpa is not None
            else range_m
        )
        value = min(range_m, predicted)
        if closest is None or value < closest[0]:
            closest = (value, time_s, signed_tcpa, ref_state, target_state)
    if closest is None:
        return None
    _closest_range, candidate_time_s, signed_tcpa_s, ref_state, target_state = closest
    ref_speed = math.hypot(ref_state[2], ref_state[3])
    target_speed = math.hypot(target_state[2], target_state[3])
    ref_course = math.atan2(ref_state[3], ref_state[2])
    target_course = math.atan2(target_state[3], target_state[2])
    target_ahead = (target_state[0] - ref_state[0]) * math.cos(ref_course) + (target_state[1] - ref_state[1]) * math.sin(
        ref_course
    )
    return {
        "duration_s": duration,
        "initial_range_m": initial_range,
        "closest_approach_m": closest[0],
        "candidate_time_s": candidate_time_s,
        "signed_tcpa_s": signed_tcpa_s if signed_tcpa_s is None else float(signed_tcpa_s),
        "max_closing_speed_mps": max_closing,
        "reference_track_distance_m": ref_distance,
        "target_track_distance_m": target_distance,
        "reference_speed_mps": ref_speed,
        "target_speed_mps": target_speed,
        "course_delta_deg": abs(math.degrees(_angle_delta(target_course, ref_course))),
        "target_ahead_m": target_ahead,
    }


def _classify_discovery(
    statistics: Mapping[str, float], profile: HistoricalAISDiscoveryProfile
) -> HistoricalAISDiscoveryType | None:
    angle = float(statistics["course_delta_deg"])
    if angle >= 180.0 - profile.head_on_angle_deg:
        return HistoricalAISDiscoveryType.HEAD_ON
    if angle <= profile.overtaking_angle_deg and statistics["target_ahead_m"] > 0.0:
        if statistics["reference_speed_mps"] >= statistics["target_speed_mps"]:
            return HistoricalAISDiscoveryType.OVERTAKING
    if profile.crossing_min_angle_deg <= angle <= profile.crossing_max_angle_deg:
        return HistoricalAISDiscoveryType.CROSSING
    return None


def _constant_velocity_fit_error(samples: Sequence[Any], speed: float, course: float) -> float:
    first = samples[0]
    vx = speed * math.cos(course)
    vy = speed * math.sin(course)
    errors = []
    for sample in samples:
        delta = sample.time_s - first.time_s
        expected_north = first.state_vxvy[0] + vx * delta
        expected_east = first.state_vxvy[1] + vy * delta
        errors.append(math.hypot(sample.state_vxvy[0] - expected_north, sample.state_vxvy[1] - expected_east))
    return math.sqrt(sum(error * error for error in errors) / len(errors)) if errors else 0.0


def apply_dimension_overrides(
    actor_set: HistoricalActorSet, overrides: Mapping[int, Mapping[str, Any]]
) -> HistoricalActorSet:
    """Apply only explicit source-provenanced per-MMSI dimension records."""
    if not overrides:
        return actor_set
    actors: list[HistoricalActor] = []
    for actor in actor_set.actors:
        document = overrides.get(actor.mmsi)
        if document is None:
            actors.append(actor)
            continue
        length = float(document.get("length_m"))
        width = float(document.get("width_m", document.get("beam_m")))
        provenance = str(document.get("provenance") or document.get("measurement_source") or "").strip()
        source_digest = str(document.get("source_digest") or "").strip()
        if (
            not math.isfinite(length)
            or length <= 0.0
            or not math.isfinite(width)
            or width <= 0.0
            or not provenance
            or not source_digest
        ):
            raise ValueError(f"dimension override for MMSI {actor.mmsi} lacks typed source provenance")
        if actor.dimensions_known:
            if not math.isclose(actor.length_m or 0.0, length, rel_tol=0.0, abs_tol=1e-9) or not math.isclose(
                actor.width_m or 0.0, width, rel_tol=0.0, abs_tol=1e-9
            ):
                raise ValueError(f"dimension override conflicts with source dimensions for MMSI {actor.mmsi}")
            actors.append(actor)
            continue
        actors.append(
            HistoricalActor(
                actor_id=actor.actor_id,
                mmsi=actor.mmsi,
                samples=actor.samples,
                observed_source_points=actor.observed_source_points,
                derived_world_samples=actor.derived_world_samples,
                length_m=length,
                width_m=width,
                dimensions_provenance=f"explicit:{provenance}",
                source_observation_digest=actor.source_observation_digest,
            )
        )
    return HistoricalActorSet(
        dataset_digest=actor_set.dataset_digest,
        selection_digest=actor_set.selection_digest,
        profile=actor_set.profile,
        time_origin_utc=actor_set.time_origin_utc,
        actors=tuple(actors),
        provider=actor_set.provider,
        attribution=actor_set.attribution,
        coverage_limitations=actor_set.coverage_limitations,
    )


def _runtime_actor(actor: HistoricalActor, actor_id: int, t0_s: float, truncate_reference: bool) -> HistoricalActor:
    if not truncate_reference:
        return replace(actor, actor_id=actor_id, actor_digest="")
    samples = [sample for sample in actor.samples if sample.time_s < t0_s]
    handoff = actor.sample_at(t0_s)
    if handoff is None or not samples:
        raise ValueError("Reference Vessel has no reconstructed state at T0")
    samples.append(
        HistoricalActorWorldSample(
            time_s=t0_s,
            timestamp_utc=handoff.timestamp_utc,
            state_vxvy=handoff.state_vxvy,
            kind=handoff.kind,
            source_observation_refs=(),
        )
    )
    source_refs = [reference.to_dict() for sample in samples for reference in sample.source_observation_refs]
    return replace(
        actor,
        actor_id=actor_id,
        samples=tuple(samples),
        observed_source_points=sum(sample.kind is HistoricalActorSampleKind.OBSERVED for sample in samples),
        derived_world_samples=sum(sample.kind is HistoricalActorSampleKind.INTERPOLATED for sample in samples),
        source_observation_digest=_sha256_json(source_refs),
        actor_digest="",
    )


def _coerce_utc(value: datetime | str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    if parsed.tzinfo is None:
        raise ValueError("UTC datetime must be timezone-aware")
    return parsed.astimezone(UTC)


# Vocabulary aliases keep the seam discoverable for callers using concise names.
HistoricalAISCaseBuildResult = HistoricalAISCaseBuildOutcome
HistoricalAISCaseBuildFailureCode = HistoricalAISCaseBuildStatus
HistoricalAISCaseStatus = HistoricalAISCaseBuildStatus
HistoricalAISDiscoveryMetadata = HistoricalAISDiscoveryResult
HistoricalAISReferenceVessel = HistoricalActor


__all__ = [
    "CASE_SCHEMA_VERSION",
    "DISCOVERY_SCHEMA_VERSION",
    "INTENT_SCHEMA_VERSION",
    "T0_SCHEMA_VERSION",
    "HistoricalAISCase",
    "HistoricalAISAlgorithmBinding",
    "HistoricalAISCaseBuildOutcome",
    "HistoricalAISCaseBuildFailureCode",
    "HistoricalAISCaseBuildRequest",
    "HistoricalAISCaseBuildResult",
    "HistoricalAISCaseBuildStatus",
    "HistoricalAISCapabilityReceipt",
    "HistoricalAISCaseStatus",
    "HistoricalAISCaseBuilder",
    "HistoricalAISDiscoveryCandidate",
    "HistoricalAISDiscoveryMetadata",
    "HistoricalAISDiscoveryProfile",
    "HistoricalAISDiscoveryRequest",
    "HistoricalAISDiscoveryResult",
    "HistoricalAISDiscoveryType",
    "HistoricalAISCompareBinding",
    "HistoricalAISEvaluationBinding",
    "HistoricalAISHumanReferenceBinding",
    "HistoricalAISManeuverDetectionProfile",
    "HistoricalAISNominalIntent",
    "HistoricalAISReferenceVessel",
    "HistoricalAIST0Candidate",
    "apply_dimension_overrides",
]
