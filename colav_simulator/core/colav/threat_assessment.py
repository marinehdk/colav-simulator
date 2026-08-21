"""Canonical, planner-agnostic threat facts for one assessment cycle."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass, field, is_dataclass
from types import MappingProxyType
from typing import Any

import numpy as np

from colav_simulator.common.string_enum import StringEnum
from colav_simulator.core.colav.encounter_lifecycle import (
    ObservationHealth,
    OwnshipObservation,
    PhysicalFactValidity,
)
from colav_simulator.core.tracking.trackers import TrackKey

THREAT_SCHEMA_VERSION = "colav.threat-management.snapshot@1"
THREAT_CANONICALIZER_ID = "colav.python-json@1"


class DomainQualification(StringEnum):
    """Qualification state for engineering Ship Domain parameters."""

    QUALIFIED = "QUALIFIED"
    UNQUALIFIED = "UNQUALIFIED"


class DomainState(StringEnum):
    """Typed current or predicted relationship to the Ship Domain."""

    OUTSIDE = "OUTSIDE"
    INSIDE = "INSIDE"
    TANGENT = "TANGENT"
    NO_INTERSECTION = "NO_INTERSECTION"
    UNKNOWN = "UNKNOWN"
    UNQUALIFIED = "UNQUALIFIED"


class PredictionBasis(StringEnum):
    """Provenance of the target trajectory used for domain projection."""

    EXPLICIT_TRAJECTORY = "EXPLICIT_TRAJECTORY"
    CONSTANT_VELOCITY = "CONSTANT_VELOCITY"
    UNAVAILABLE = "UNAVAILABLE"


class ThreatUnavailableReason(StringEnum):
    """Typed reasons for facts that cannot be claimed by this snapshot."""

    PREDICTION_UNAVAILABLE = "PREDICTION_UNAVAILABLE"
    PROFILE_UNQUALIFIED = "PROFILE_UNQUALIFIED"
    OBSERVATION_UNUSABLE = "OBSERVATION_UNUSABLE"
    TARGET_DIMENSIONS_UNAVAILABLE = "TARGET_DIMENSIONS_UNAVAILABLE"
    RELATIVE_MOTION_UNDEFINED = "RELATIVE_MOTION_UNDEFINED"
    UNCERTAINTY_UNAVAILABLE = "UNCERTAINTY_UNAVAILABLE"
    PHYSICAL_FACT_UNAVAILABLE = "PHYSICAL_FACT_UNAVAILABLE"
    OBSERVATION_STALE = "OBSERVATION_STALE"


class ThreatPriorityClass(StringEnum):
    """Versioned lexicographic priority classes, not a scalar safety score."""

    RESPONSE_TIME_EMERGENCY = "RESPONSE_TIME_EMERGENCY"
    RULE17_MUST_ACT = "RULE17_MUST_ACT"
    COMMITTED_ACTIVE = "COMMITTED_ACTIVE"
    CURRENT_DOMAIN_VIOLATION = "CURRENT_DOMAIN_VIOLATION"
    PREDICTED_DOMAIN_VIOLATION = "PREDICTED_DOMAIN_VIOLATION"
    FUTURE_SEVERITY = "FUTURE_SEVERITY"
    UNKNOWN = "UNKNOWN"
    MONITOR = "MONITOR"


class ThreatCompleteness(StringEnum):
    """Typed completeness of a published threat claim."""

    FULL = "FULL"
    PARTIAL = "PARTIAL"
    DEGRADED = "DEGRADED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ThreatWindow:
    """A rolling, typed prediction window; never an executable maneuver script."""

    key: TrackKey
    entry_time_s: float | None = None
    peak_time_s: float | None = None
    exit_time_s: float | None = None
    reference_time_s: float | None = None
    horizon_end_s: float | None = None
    prediction_basis: PredictionBasis | str = PredictionBasis.UNAVAILABLE
    source: str = "ThreatAssessment"
    completeness: ThreatCompleteness | str = ThreatCompleteness.UNKNOWN
    unavailable_reason: ThreatUnavailableReason | str | None = None
    entry_time_absolute_s: float | None = None
    peak_time_absolute_s: float | None = None
    exit_time_absolute_s: float | None = None

    def __post_init__(self) -> None:
        """Validate relative/absolute time identity and typed unknown bounds."""
        if not isinstance(self.key, TrackKey):
            raise TypeError("threat window key must be TrackKey")
        for value, name in (
            (self.entry_time_s, "entry_time_s"),
            (self.peak_time_s, "peak_time_s"),
            (self.exit_time_s, "exit_time_s"),
            (self.reference_time_s, "reference_time_s"),
            (self.horizon_end_s, "horizon_end_s"),
            (self.entry_time_absolute_s, "entry_time_absolute_s"),
            (self.peak_time_absolute_s, "peak_time_absolute_s"),
            (self.exit_time_absolute_s, "exit_time_absolute_s"),
        ):
            if value is not None and (not math.isfinite(value) or value < 0.0):
                raise ValueError(f"{name} must be finite and non-negative")
        if self.entry_time_s is not None and self.peak_time_s is not None and self.peak_time_s < self.entry_time_s:
            raise ValueError("peak time cannot precede entry")
        if self.peak_time_s is not None and self.exit_time_s is not None and self.exit_time_s < self.peak_time_s:
            raise ValueError("exit time cannot precede peak")
        if self.reference_time_s is not None and self.horizon_end_s is not None and self.horizon_end_s < 0.0:
            raise ValueError("horizon end must be non-negative")
        object.__setattr__(self, "prediction_basis", PredictionBasis(self.prediction_basis))
        object.__setattr__(self, "completeness", ThreatCompleteness(self.completeness))
        if self.unavailable_reason is not None:
            object.__setattr__(self, "unavailable_reason", ThreatUnavailableReason(self.unavailable_reason))

    @property
    def tdv_s(self) -> float | None:
        return self.entry_time_s

    @property
    def tde_s(self) -> float | None:
        return self.exit_time_s

    @property
    def relative_entry_time_s(self) -> float | None:
        return self.entry_time_s

    @property
    def relative_peak_time_s(self) -> float | None:
        return self.peak_time_s

    @property
    def relative_exit_time_s(self) -> float | None:
        return self.exit_time_s


class ThreatScheduleContext(StringEnum):
    """Mutually exclusive semantic membership of one target in a snapshot."""

    CURRENT_PRIMARY = "CURRENT_PRIMARY"
    CONCURRENT_REQUIRED = "CONCURRENT_REQUIRED"
    NEXT = "NEXT"
    MONITOR = "MONITOR"
    RELEASED = "RELEASED"
    HISTORICAL = "HISTORICAL"


@dataclass(frozen=True)
class ThreatScheduleEntry:
    """One target's explainable rolling schedule membership."""

    key: TrackKey
    context: ThreatScheduleContext | str
    window: ThreatWindow | None = None
    priority_class: ThreatPriorityClass | str = ThreatPriorityClass.MONITOR
    priority_reason: str = ""
    unavailable_reason: ThreatUnavailableReason | str | None = None
    handoff_expectation: str | None = None

    def __post_init__(self) -> None:
        """Normalize enum fields and retain typed unavailable bounds."""
        if not isinstance(self.key, TrackKey):
            raise TypeError("schedule entry key must be TrackKey")
        object.__setattr__(self, "context", ThreatScheduleContext(self.context))
        object.__setattr__(self, "priority_class", ThreatPriorityClass(self.priority_class))
        if self.unavailable_reason is not None:
            object.__setattr__(self, "unavailable_reason", ThreatUnavailableReason(self.unavailable_reason))

    @property
    def membership(self) -> ThreatScheduleContext:
        return self.context


@dataclass(frozen=True)
class ThreatScheduleEvent:
    """Typed schedule transition that does not turn prediction into history."""

    event_id: int
    sim_time_s: float
    event_type: str
    key: TrackKey | None
    reason: str
    from_context: ThreatScheduleContext | str | None = None
    to_context: ThreatScheduleContext | str | None = None
    predicted: bool = True
    schema_version: str = "colav.threat-schedule.event@1"

    def __post_init__(self) -> None:
        """Normalize event context fields before immutable publication."""
        if self.event_id < 1 or not math.isfinite(self.sim_time_s) or self.sim_time_s < 0.0:
            raise ValueError("schedule event identity/time is invalid")
        if self.key is not None and not isinstance(self.key, TrackKey):
            raise TypeError("schedule event key must be TrackKey")
        if self.from_context is not None:
            object.__setattr__(self, "from_context", ThreatScheduleContext(self.from_context))
        if self.to_context is not None:
            object.__setattr__(self, "to_context", ThreatScheduleContext(self.to_context))


@dataclass(frozen=True)
class ThreatSchedule:
    """Rolling Current/Concurrent/Next/Monitor projection."""

    current_primary: TrackKey | None = None
    concurrent_required: tuple[TrackKey, ...] = ()
    next_threats: tuple[TrackKey, ...] = ()
    monitor: tuple[TrackKey, ...] = ()
    released: tuple[TrackKey, ...] = ()
    entries: tuple[ThreatScheduleEntry, ...] = ()
    events: tuple[ThreatScheduleEvent, ...] = ()
    horizon_start_s: float = 0.0
    horizon_end_s: float | None = None
    generated_at_s: float = 0.0
    input_hash: str = ""
    profile_hash: str = ""
    schema_version: str = "colav.threat-schedule@1"

    def __post_init__(self) -> None:
        """Freeze membership and reject duplicate semantic placement."""
        for name in ("concurrent_required", "next_threats", "monitor", "released", "entries", "events"):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        if self.current_primary is not None and not isinstance(self.current_primary, TrackKey):
            raise TypeError("current primary must be TrackKey")
        groups = [
            (self.current_primary,) if self.current_primary is not None else (),
            self.concurrent_required,
            self.next_threats,
            self.monitor,
            self.released,
        ]
        keys = [key for group in groups for key in group]
        if len(keys) != len(set(keys)):
            raise ValueError("one TrackKey cannot occupy multiple schedule contexts")
        entry_keys = tuple(entry.key for entry in self.entries)
        if len(entry_keys) != len(set(entry_keys)):
            raise ValueError("schedule entries must have unique TrackKeys")
        if set(entry_keys) != set(keys):
            raise ValueError("schedule entries must cover every membership")

    @property
    def current(self) -> TrackKey | None:
        return self.current_primary

    @property
    def concurrent(self) -> tuple[TrackKey, ...]:
        return self.concurrent_required

    @property
    def next(self) -> tuple[TrackKey, ...]:
        return self.next_threats


class ConflictEdgeType(StringEnum):
    """Typed relationship represented in the online conflict graph."""

    DIRECT_WINDOW_OVERLAP = "DIRECT_WINDOW_OVERLAP"
    PLAN_INDUCED_CONFLICT = "PLAN_INDUCED_CONFLICT"


class ConflictPredictionBasis(StringEnum):
    """Prediction provenance attached to one immutable graph edge."""

    THREAT_WINDOW = "THREAT_WINDOW"
    BASELINE_VS_ACCEPTED_PLAN = "BASELINE_VS_ACCEPTED_PLAN"
    MIXED = "MIXED"
    UNAVAILABLE = "UNAVAILABLE"


class ConflictUnavailableReason(StringEnum):
    """Typed reasons why optional plan-induced evidence is unavailable."""

    BASELINE_UNAVAILABLE = "BASELINE_UNAVAILABLE"
    ACCEPTED_PLAN_UNAVAILABLE = "ACCEPTED_PLAN_UNAVAILABLE"
    ACCEPTED_PLAN_PREDICTION_UNAVAILABLE = "ACCEPTED_PLAN_PREDICTION_UNAVAILABLE"
    ACCEPTED_PLAN_RECEIPT_INVALID = "ACCEPTED_PLAN_RECEIPT_INVALID"
    ACCEPTED_PLAN_EXPIRED = "ACCEPTED_PLAN_EXPIRED"
    TARGET_PREDICTION_UNAVAILABLE = "TARGET_PREDICTION_UNAVAILABLE"
    TARGET_PREDICTION_IDENTITY_MISMATCH = "TARGET_PREDICTION_IDENTITY_MISMATCH"
    PLAN_PREDICTION_IDENTITY_MISMATCH = "PLAN_PREDICTION_IDENTITY_MISMATCH"
    PLAN_PROFILE_MISMATCH = "PLAN_PROFILE_MISMATCH"
    PLAN_TARGET_UNAVAILABLE = "PLAN_TARGET_UNAVAILABLE"


@dataclass(frozen=True)
class ConflictGraphProfile:
    """Versioned deterministic overlap and materiality policy."""

    profile_id: str = "colav.conflict-graph.v1"
    version: str = "1"
    window_overlap_gap_s: float = 0.0
    material_tdv_advance_s: float = 5.0
    material_scale_worsening: float = 0.1

    def __post_init__(self) -> None:
        """Validate graph thresholds without coupling them to L4 safety."""
        if not self.profile_id.strip() or not self.version.strip():
            raise ValueError("conflict graph profile identity is required")
        values = (
            self.window_overlap_gap_s,
            self.material_tdv_advance_s,
            self.material_scale_worsening,
        )
        if not np.isfinite(values).all() or min(values) < 0.0:
            raise ValueError("conflict graph thresholds must be finite and non-negative")

    @property
    def profile_hash(self) -> str:
        return _sha256(self.to_dict())

    def to_dict(self) -> dict[str, object]:
        return {
            "profile_id": self.profile_id,
            "version": self.version,
            "window_overlap_gap_s": self.window_overlap_gap_s,
            "material_tdv_advance_s": self.material_tdv_advance_s,
            "material_scale_worsening": self.material_scale_worsening,
        }


@dataclass(frozen=True)
class OwnshipThreatPrediction:
    """Explicit ownship path used only for plan-conflict comparison."""

    times_s: np.ndarray
    states_enu: np.ndarray
    basis: str = "EXPLICIT_TRAJECTORY"
    model: str = "ownship_prediction"
    source: str = "UNKNOWN"
    target_keys: tuple[TrackKey, ...] = ()
    reference_time_s: float = 0.0
    coordinate_frame: str = "ENU"
    linear_unit: str = "m"
    angle_unit: str = "rad"
    evidence_semantic_hash: str | None = None
    prediction_hash: str = ""

    def __post_init__(self) -> None:
        """Freeze one finite ownship prediction and its target identity set."""
        times = np.array(self.times_s, dtype=float, copy=True)
        states = np.array(self.states_enu, dtype=float, copy=True)
        if times.ndim != 1 or times.size < 2 or not np.isfinite(times).all():
            raise ValueError("ownship prediction times must be finite and contain at least two samples")
        if times[0] < 0.0 or np.any(np.diff(times) <= 0.0):
            raise ValueError("ownship prediction times must be strictly increasing and non-negative")
        if states.shape != (times.size, 4) or not np.isfinite(states).all():
            raise ValueError("ownship prediction states must have shape (N, 4) and be finite")
        keys = tuple(sorted(self.target_keys, key=_track_key_sort))
        if len(keys) != len(set(keys)) or any(not isinstance(key, TrackKey) for key in keys):
            raise ValueError("ownship prediction target keys must be unique TrackKeys")
        if not self.basis.strip() or not self.model.strip() or not self.source.strip():
            raise ValueError("ownship prediction provenance is required")
        if not math.isfinite(self.reference_time_s) or self.reference_time_s < 0.0:
            raise ValueError("ownship prediction reference time must be finite and non-negative")
        if (self.coordinate_frame, self.linear_unit, self.angle_unit) != ("ENU", "m", "rad"):
            raise ValueError("ownship prediction requires ENU/m/rad units")
        if self.evidence_semantic_hash is not None and not self.evidence_semantic_hash.strip():
            raise ValueError("evidence semantic hash cannot be empty")
        times.setflags(write=False)
        states.setflags(write=False)
        object.__setattr__(self, "times_s", times)
        object.__setattr__(self, "states_enu", states)
        object.__setattr__(self, "target_keys", keys)
        computed_hash = _sha256(self.to_dict(include_hash=False))
        if self.prediction_hash and self.prediction_hash != computed_hash:
            raise ValueError("ownship prediction hash does not match prediction content")
        object.__setattr__(self, "prediction_hash", computed_hash)

    @classmethod
    def from_prediction_evidence(
        cls,
        record: Any,
        *,
        reference_time_s: float,
        target_keys: tuple[TrackKey, ...] = (),
    ) -> OwnshipThreatPrediction:
        """Derive the accepted ownship artifact from one immutable evidence record."""
        ownship = record.ownship
        heading = np.asarray(ownship.heading_rad, dtype=float)
        speed = np.asarray(ownship.speed_mps, dtype=float)
        states = np.column_stack(
            (
                ownship.north_m,
                ownship.east_m,
                speed * np.cos(heading),
                speed * np.sin(heading),
            )
        )
        return cls(
            times_s=np.asarray(ownship.grid.times_s, dtype=float),
            states_enu=states,
            basis="ACCEPTED_PLAN",
            model="mid_mpc_prediction_evidence",
            source="L4_ACCEPTED_PLAN",
            target_keys=target_keys,
            reference_time_s=reference_time_s,
            evidence_semantic_hash=str(record.semantic_hash),
        )

    @property
    def semantic_hash(self) -> str:
        return self.prediction_hash

    def to_dict(self, *, include_hash: bool = True) -> dict[str, object]:
        value: dict[str, object] = {
            "times_s": self.times_s.tolist(),
            "states_enu": self.states_enu.tolist(),
            "basis": self.basis,
            "model": self.model,
            "source": self.source,
            "target_keys": [_json_value(key) for key in self.target_keys],
            "reference_time_s": self.reference_time_s,
            "coordinate_frame": self.coordinate_frame,
            "linear_unit": self.linear_unit,
            "angle_unit": self.angle_unit,
            "evidence_semantic_hash": self.evidence_semantic_hash,
        }
        if include_hash:
            value["prediction_hash"] = self.prediction_hash
        return value


@dataclass(frozen=True)
class ConflictWitness:
    """Immutable before/after or overlap evidence attached to an edge."""

    values: Mapping[str, object]

    def __post_init__(self) -> None:
        """Freeze nested witness values for deterministic serialization."""
        object.__setattr__(self, "values", _freeze_mapping(self.values))

    def to_dict(self) -> dict[str, object]:
        return _json_value(self.values)


@dataclass(frozen=True)
class ConflictEdge:
    """One typed undirected relationship between target identities."""

    edge_id: str
    edge_type: ConflictEdgeType | str
    members: tuple[TrackKey, ...]
    prediction_basis: ConflictPredictionBasis | str
    witness: ConflictWitness
    input_hash: str
    plan_receipt_hash: str | None = None

    def __post_init__(self) -> None:
        """Validate typed members and normalize deterministic ordering."""
        if not self.edge_id.strip() or not self.input_hash.strip():
            raise ValueError("conflict edge identity and input hash are required")
        members = tuple(sorted(self.members, key=_track_key_sort))
        if len(members) < 2 or len(members) != len(set(members)) or any(
            not isinstance(key, TrackKey) for key in members
        ):
            raise ValueError("conflict edge must contain at least two unique TrackKeys")
        object.__setattr__(self, "members", members)
        object.__setattr__(self, "edge_type", ConflictEdgeType(self.edge_type))
        object.__setattr__(self, "prediction_basis", ConflictPredictionBasis(self.prediction_basis))
        if self.plan_receipt_hash is not None and not self.plan_receipt_hash.strip():
            raise ValueError("plan receipt hash cannot be empty")

    def to_dict(self) -> dict[str, object]:
        return {
            "edge_id": self.edge_id,
            "edge_type": self.edge_type.value,
            "members": [_json_value(key) for key in self.members],
            "prediction_basis": self.prediction_basis.value,
            "witness": self.witness.to_dict(),
            "input_hash": self.input_hash,
            "plan_receipt_hash": self.plan_receipt_hash,
        }


@dataclass(frozen=True)
class ConflictCluster:
    """Deterministic connected component and immutable lineage."""

    cluster_id: str
    members: tuple[TrackKey, ...]
    edge_ids: tuple[str, ...]
    parent_cluster_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Validate component membership and freeze lineage identifiers."""
        if not self.cluster_id.strip():
            raise ValueError("conflict cluster identity is required")
        members = tuple(sorted(self.members, key=_track_key_sort))
        if len(members) < 2 or len(members) != len(set(members)):
            raise ValueError("conflict cluster must contain at least two unique members")
        object.__setattr__(self, "members", members)
        object.__setattr__(self, "edge_ids", tuple(sorted(set(self.edge_ids))))
        object.__setattr__(self, "parent_cluster_ids", tuple(sorted(set(self.parent_cluster_ids))))

    def to_dict(self) -> dict[str, object]:
        return {
            "cluster_id": self.cluster_id,
            "members": [_json_value(key) for key in self.members],
            "edge_ids": list(self.edge_ids),
            "parent_cluster_ids": list(self.parent_cluster_ids),
        }


@dataclass(frozen=True)
class ConflictGraph:
    """Canonical graph and connected components for one Threat cycle."""

    nodes: tuple[TrackKey, ...] = ()
    edges: tuple[ConflictEdge, ...] = ()
    clusters: tuple[ConflictCluster, ...] = ()
    unavailable_reasons: tuple[ConflictUnavailableReason | str, ...] = ()
    profile_hash: str = ""
    input_hash: str = ""
    schema_version: str = "colav.conflict-graph@1"
    _semantic_hash: str = field(default="", init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        """Freeze graph collections and calculate the semantic identity."""
        nodes = tuple(sorted(self.nodes, key=_track_key_sort))
        if len(nodes) != len(set(nodes)) or any(not isinstance(key, TrackKey) for key in nodes):
            raise ValueError("conflict graph nodes must be unique TrackKeys")
        edges = tuple(sorted(self.edges, key=lambda edge: edge.edge_id))
        clusters = tuple(sorted(self.clusters, key=lambda cluster: cluster.cluster_id))
        if len({edge.edge_id for edge in edges}) != len(edges):
            raise ValueError("conflict edge IDs must be unique")
        if any(not set(edge.members).issubset(nodes) for edge in edges):
            raise ValueError("conflict edges must reference graph nodes")
        object.__setattr__(self, "nodes", nodes)
        object.__setattr__(self, "edges", edges)
        object.__setattr__(self, "clusters", clusters)
        object.__setattr__(
            self,
            "unavailable_reasons",
            tuple(
                sorted(
                    {ConflictUnavailableReason(reason) for reason in self.unavailable_reasons},
                    key=lambda value: value.value,
                )
            ),
        )
        if not self.profile_hash.strip() or not self.input_hash.strip():
            raise ValueError("conflict graph profile and input hashes are required")
        object.__setattr__(self, "_semantic_hash", _sha256(self.to_dict(include_hash=False)))

    @property
    def semantic_hash(self) -> str:
        return self._semantic_hash

    def to_dict(self, *, include_hash: bool = True) -> dict[str, object]:
        value: dict[str, object] = {
            "schema_version": self.schema_version,
            "nodes": [_json_value(key) for key in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
            "clusters": [cluster.to_dict() for cluster in self.clusters],
            "unavailable_reasons": [reason.value for reason in self.unavailable_reasons],
            "profile_hash": self.profile_hash,
            "input_hash": self.input_hash,
        }
        if include_hash:
            value["semantic_hash"] = self.semantic_hash
        return value


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
    peak_time_s: float | None = None
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
            (self.peak_time_s, "peak_time_s"),
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
    claim_completeness: ThreatCompleteness | str
    prediction_basis: PredictionBasis
    unavailable_reasons: tuple[ThreatUnavailableReason | str, ...] = ()
    priority_class: ThreatPriorityClass | str = ThreatPriorityClass.MONITOR
    priority_reason: str = ""
    priority_key: tuple[float, ...] = ()
    window: ThreatWindow | None = None
    lifecycle_role: str | None = None
    lifecycle_risk: str | None = None
    lifecycle_commitment: str | None = None

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
        object.__setattr__(self, "claim_completeness", ThreatCompleteness(self.claim_completeness))
        object.__setattr__(self, "observation_health", ObservationHealth(self.observation_health))
        object.__setattr__(self, "prediction_basis", PredictionBasis(self.prediction_basis))
        object.__setattr__(self, "priority_class", ThreatPriorityClass(self.priority_class))
        if not isinstance(self.priority_reason, str):
            raise TypeError("priority reason must be a string")
        object.__setattr__(self, "priority_key", tuple(float(value) for value in self.priority_key))
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

    @property
    def threat_window(self) -> ThreatWindow | None:
        return self.window

    @property
    def current_domain_violation(self) -> bool:
        return self.current_domain.state is DomainState.INSIDE

    @property
    def predicted_domain_violation(self) -> bool:
        return self.predicted_domain.state is DomainState.INSIDE


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
    physical_facts: tuple[Any, ...] = ()

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
        facts = self.physical_facts.values() if isinstance(self.physical_facts, Mapping) else self.physical_facts
        facts = tuple(facts)
        fact_keys = tuple(getattr(value, "key", None) for value in facts)
        if any(key is None for key in fact_keys) or len(fact_keys) != len(set(fact_keys)):
            raise TypeError("physical_facts must contain unique keyed facts")
        if any(key not in keys for key in fact_keys):
            raise ValueError("physical_facts must reference an assessment target")
        if facts and set(fact_keys) != set(keys):
            raise ValueError("physical_facts must cover every target")
        object.__setattr__(self, "physical_facts", facts)

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
            "physical_facts": [
                _json_value(value)
                for value in sorted(self.physical_facts, key=lambda value: _track_key_sort(value.key))
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
    lifecycle_snapshot: Any | None = None
    schedule: ThreatSchedule | None = None
    events: tuple[ThreatScheduleEvent, ...] = ()
    accepted_plan_receipt: Any | None = None
    conflict_graph: ConflictGraph | None = None

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
        object.__setattr__(self, "events", tuple(self.events))
        object.__setattr__(self, "provenance", _freeze_mapping(self.provenance))
        semantic_hash = _sha256(self.to_dict(include_hash=False))
        object.__setattr__(self, "_semantic_hash", semantic_hash)

    @property
    def semantic_hash(self) -> str:
        return self._semantic_hash

    @property
    def lifecycle(self) -> Any | None:
        return self.lifecycle_snapshot

    @property
    def threat_schedule(self) -> ThreatSchedule | None:
        return self.schedule

    @property
    def graph(self) -> ConflictGraph | None:
        return self.conflict_graph

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
            "lifecycle_snapshot": _json_value(self.lifecycle_snapshot),
            "schedule": _json_value(self.schedule),
            "events": [_json_value(event) for event in self.events],
            "accepted_plan_receipt": _json_value(self.accepted_plan_receipt),
            "conflict_graph": (
                self.conflict_graph.to_dict()
                if self.conflict_graph is not None
                else None
            ),
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
        physical_facts = {fact.key: fact for fact in request.physical_facts}
        vectors = tuple(
            _assess_target(
                request.ownship,
                _coerce_target(target),
                request.profile,
                {prediction.key: prediction for prediction in request.predictions}.get(target.key),
                physical_facts.get(target.key),
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


def _assess_target(  # noqa: PLR0912, PLR0915 - explicit typed evidence branches
    ownship: OwnshipObservation,
    target: ThreatTargetObservation,
    profile: ShipDomainProfile,
    prediction: ThreatPrediction | None,
    physical_fact: Any | None = None,
) -> ThreatVector:
    relative_position = target.state_enu[:2] - ownship.position_ne_m
    relative_velocity = target.state_enu[2:4] - ownship.velocity_ne_mps
    if physical_fact is not None:
        relative_position = np.asarray(physical_fact.relative_position_ne_m, dtype=float)
        relative_velocity = np.asarray(physical_fact.relative_velocity_ne_mps, dtype=float)
    canonical_geometry = getattr(physical_fact, "geometry", None)
    range_m = (
        float(canonical_geometry.range_m)
        if canonical_geometry is not None
        else float(np.linalg.norm(relative_position))
    )
    if range_m > 1.0e-12:
        closing_speed_mps = -float(relative_position @ relative_velocity) / range_m
    else:
        closing_speed_mps = None
    relative_speed_sq = float(relative_velocity @ relative_velocity)
    unavailable: list[str] = []
    if canonical_geometry is not None and math.isfinite(canonical_geometry.signed_tcpa_s):
        tcpa_signed_s = float(canonical_geometry.signed_tcpa_s)
        tcpa_forward_s = max(0.0, tcpa_signed_s)
        dcpa_m = float(canonical_geometry.dcpa_m)
    elif relative_speed_sq > 1.0e-12:
        tcpa_signed_s = -float(relative_position @ relative_velocity) / relative_speed_sq
        tcpa_forward_s = max(0.0, tcpa_signed_s)
        dcpa_m = float(np.linalg.norm(relative_position + tcpa_forward_s * relative_velocity))
    else:
        tcpa_signed_s = None
        tcpa_forward_s = None
        dcpa_m = range_m
        unavailable.append("RELATIVE_MOTION_UNDEFINED")
    hull_clearance_m = getattr(physical_fact, "hull_clearance_m", None)
    if target.length_m is None or target.width_m is None:
        unavailable.append("TARGET_DIMENSIONS_UNAVAILABLE")
    elif hull_clearance_m is None and dcpa_m is not None:
        own_radius = 0.5 * math.hypot(ownship.length_m, ownship.width_m)
        target_radius = 0.5 * math.hypot(target.length_m, target.width_m)
        hull_clearance_m = dcpa_m - own_radius - target_radius

    if getattr(physical_fact, "validity", PhysicalFactValidity.VALID) is not PhysicalFactValidity.VALID:
        unavailable.append(getattr(physical_fact, "unavailable_reason", None) or "PHYSICAL_FACT_UNAVAILABLE")

    uncertainty_radius_m = _uncertainty_radius(target, profile)
    if uncertainty_radius_m is None:
        unavailable.append(ThreatUnavailableReason.UNCERTAINTY_UNAVAILABLE)
    physical_unavailable_reason = getattr(physical_fact, "unavailable_reason", None)
    physical_unavailable = (
        getattr(physical_fact, "validity", PhysicalFactValidity.VALID) is not PhysicalFactValidity.VALID
    )
    if physical_unavailable and physical_unavailable_reason:
        current_domain = DomainFacts(
            state=DomainState.UNKNOWN,
            normalized_scale=None,
            unavailable_reason=physical_unavailable_reason,
            uncertainty_radius_m=uncertainty_radius_m,
        )
        predicted_domain = DomainFacts(
            state=DomainState.UNKNOWN,
            normalized_scale=None,
            unavailable_reason=physical_unavailable_reason,
            uncertainty_radius_m=uncertainty_radius_m,
        )
    else:
        current_domain = _current_domain_facts(
            ownship,
            target,
            profile,
            uncertainty_radius_m,
            relative_position_ne_m=relative_position,
        )
        predicted_domain = _predicted_domain_facts(ownship, target, profile, uncertainty_radius_m, prediction)
    if predicted_domain.unavailable_reason is not None:
        unavailable.append(predicted_domain.unavailable_reason)
    completeness = (
        ThreatCompleteness.UNKNOWN
        if target.health is ObservationHealth.UNUSABLE or physical_unavailable
        else ThreatCompleteness.FULL
    )
    if target.health in {ObservationHealth.COASTING, ObservationHealth.DEGRADED}:
        completeness = ThreatCompleteness.DEGRADED
    if unavailable and completeness is ThreatCompleteness.FULL:
        completeness = ThreatCompleteness.PARTIAL
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
    *,
    relative_position_ne_m: np.ndarray | None = None,
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
    relative = (
        target.state_enu[:2] - ownship.position_ne_m
        if relative_position_ne_m is None
        else relative_position_ne_m
    )
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
    peak_time_s = float(prediction.times_s[int(np.argmin(scales))])
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
        peak_time_s=peak_time_s,
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


def normalized_domain_scale(
    forward_m: float,
    starboard_m: float,
    profile: ShipDomainProfile,
    uncertainty_radius_m: float | None,
) -> float:
    """Expose the canonical profile-bound scale for plan-conflict witnesses."""
    return _normalized_domain_scale(forward_m, starboard_m, profile, uncertainty_radius_m)


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
    if isinstance(value, StringEnum):
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
        numeric = value.item()
        return numeric if not isinstance(numeric, float) or math.isfinite(numeric) else None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _sha256(value: object) -> str:
    encoded = json.dumps(_json_value(value), sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
