"""Typed, replayable prediction evidence for Mid-MPC."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, fields, is_dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any

import numpy as np

EVIDENCE_SCHEMA = "colav.mid_mpc.prediction-evidence@1"
EVENT_SCHEMA = "colav.prediction-evidence.event@1"
CANONICALIZER_ID = "colav.python-json@1"
INLINE_SCHEMA = "colav.mid_mpc.prediction-evidence.inline@1"


class PredictionPurpose(StrEnum):
    NLP = "NLP"
    L4_SAFETY = "L4_SAFETY"


class EvidenceEventType(StrEnum):
    CYCLE_STARTED = "CYCLE_STARTED"
    INPUT_VALIDATED = "INPUT_VALIDATED"
    SOLVE_ATTEMPTED = "SOLVE_ATTEMPTED"
    CANDIDATE_PRODUCED = "CANDIDATE_PRODUCED"
    L4_EVALUATED = "L4_EVALUATED"
    REPLAN_REQUESTED = "REPLAN_REQUESTED"
    PLAN_COMMITTED = "PLAN_COMMITTED"
    PLAN_HELD = "PLAN_HELD"
    PLAN_REJECTED = "PLAN_REJECTED"
    PLAN_FAILED = "PLAN_FAILED"
    COMMAND_APPLIED = "COMMAND_APPLIED"
    ARTIFACT_QUEUED = "ARTIFACT_QUEUED"
    ARTIFACT_COMPLETE = "ARTIFACT_COMPLETE"
    ARTIFACT_INCOMPLETE = "ARTIFACT_INCOMPLETE"
    ARTIFACT_BACKPRESSURE = "ARTIFACT_BACKPRESSURE"
    RESET = "RESET"


class TerminalOutcome(StrEnum):
    COMMITTED = "COMMITTED"
    HELD = "HELD"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class ArtifactState(StrEnum):
    NONE = "NONE"
    QUEUED = "QUEUED"
    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"
    BACKPRESSURE = "BACKPRESSURE"


class EvidenceVerificationLevel(StrEnum):
    NONE = "NONE"
    BYTES_DIGEST = "V0_BYTES_DIGEST"
    SCHEMA = "V1_SCHEMA"
    LINEAGE = "V2_LINEAGE"
    NUMERICAL = "V3_NUMERICAL"
    L4 = "V4_L4"
    PROJECTION = "V5_PROJECTION"
    RUNTIME_AUTHORITY = "V6_RUNTIME_AUTHORITY"


@dataclass(frozen=True)
class OccurrenceId:
    run_id: str
    epoch: int
    event_seq: int

    def __post_init__(self) -> None:
        """Validate one run-local occurrence identity."""
        if not self.run_id.strip():
            raise ValueError("run_id must be non-empty")
        if self.epoch < 0 or self.event_seq < 0:
            raise ValueError("epoch and event_seq must be non-negative")

    def to_dict(self) -> dict[str, object]:
        return {"run_id": self.run_id, "epoch": self.epoch, "event_seq": self.event_seq}


@dataclass(frozen=True)
class PredictionGrid:
    intervals: int = 80
    dt_s: float = 15.0

    def __post_init__(self) -> None:
        """Validate the prediction grid dimensions."""
        if self.intervals < 1:
            raise ValueError("intervals must be positive")
        if not math.isfinite(self.dt_s) or self.dt_s <= 0.0:
            raise ValueError("dt_s must be finite and positive")

    @property
    def state_samples(self) -> int:
        return self.intervals + 1

    @property
    def duration_s(self) -> float:
        return self.intervals * self.dt_s

    @property
    def times_s(self) -> tuple[float, ...]:
        return tuple(index * self.dt_s for index in range(self.state_samples))

    def to_dict(self) -> dict[str, object]:
        return {
            "intervals": self.intervals,
            "state_samples": self.state_samples,
            "dt_s": self.dt_s,
            "duration_s": self.duration_s,
        }


@dataclass(frozen=True)
class OptimizationIntervalReference:
    interval_index: int
    start_s: float
    end_s: float
    heading_rad: float
    speed_mps: float
    heading_raw_index: int
    speed_raw_index: int

    def __post_init__(self) -> None:
        """Validate one raw-primal interval reference."""
        if self.interval_index < 0 or min(self.heading_raw_index, self.speed_raw_index) < 0:
            raise ValueError("interval and raw indices must be non-negative")
        _require_finite(self.start_s, self.end_s, self.heading_rad, self.speed_mps)
        if self.start_s < 0.0 or self.end_s <= self.start_s:
            raise ValueError("interval times must be ordered and non-negative")


@dataclass(frozen=True)
class RuntimeAppliedReference:
    policy: str
    elapsed_s: float
    interval_index: int
    interpolation_fraction: float
    heading_rad: float
    speed_mps: float

    def __post_init__(self) -> None:
        """Validate one runtime interpolation result."""
        if self.policy != "LINEAR_INTERPOLATION":
            raise ValueError("runtime applied reference policy must preserve LINEAR_INTERPOLATION")
        if self.interval_index < 0:
            raise ValueError("interval_index must be non-negative")
        _require_finite(
            self.elapsed_s,
            self.interpolation_fraction,
            self.heading_rad,
            self.speed_mps,
        )
        if self.elapsed_s < 0.0 or not 0.0 <= self.interpolation_fraction <= 1.0:
            raise ValueError("runtime interpolation coordinates are outside the trajectory")

    @classmethod
    def linear(
        cls,
        *,
        elapsed_s: float,
        dt_s: float,
        heading_rad: Sequence[float],
        speed_mps: Sequence[float],
    ) -> RuntimeAppliedReference:
        if not math.isfinite(dt_s) or dt_s <= 0.0:
            raise ValueError("dt_s must be finite and positive")
        heading = np.asarray(heading_rad, dtype=float)
        speed = np.asarray(speed_mps, dtype=float)
        if heading.ndim != 1 or speed.ndim != 1 or heading.size != speed.size or heading.size < 1:
            raise ValueError("runtime reference vectors must be aligned and non-empty")
        if not np.isfinite(heading).all() or not np.isfinite(speed).all() or not math.isfinite(elapsed_s):
            raise ValueError("runtime reference inputs must be finite")
        coordinate = max(0.0, elapsed_s) / dt_s
        lower = min(int(math.floor(coordinate)), heading.size - 1)
        upper = min(lower + 1, heading.size - 1)
        fraction = min(max(coordinate - lower, 0.0), 1.0) if upper > lower else 0.0
        heading_delta = float(heading[upper] - heading[lower])
        delta = math.atan2(math.sin(heading_delta), math.cos(heading_delta))
        return cls(
            policy="LINEAR_INTERPOLATION",
            elapsed_s=max(0.0, float(elapsed_s)),
            interval_index=lower,
            interpolation_fraction=fraction,
            heading_rad=float(heading[lower] + fraction * delta),
            speed_mps=float(speed[lower] + fraction * (speed[upper] - speed[lower])),
        )


@dataclass(frozen=True)
class OwnshipPrediction:
    grid: PredictionGrid
    north_m: np.ndarray
    east_m: np.ndarray
    heading_rad: np.ndarray
    speed_mps: np.ndarray
    state_sources: tuple[str, ...]
    interval_references: tuple[OptimizationIntervalReference, ...]

    def __post_init__(self) -> None:
        """Freeze and align ownship knots and interval references."""
        if not isinstance(self.grid, PredictionGrid):
            raise TypeError("grid must be PredictionGrid")
        for name in ("north_m", "east_m", "heading_rad", "speed_mps"):
            array = _readonly_vector(getattr(self, name), name)
            if array.size != self.grid.state_samples:
                raise ValueError(f"{name} must contain one value per state sample")
            object.__setattr__(self, name, array)
        sources = tuple(str(value) for value in self.state_sources)
        if len(sources) != self.grid.state_samples or not all(sources):
            raise ValueError("state_sources must contain one non-empty source per state sample")
        references = tuple(self.interval_references)
        if len(references) != self.grid.intervals:
            raise ValueError("interval references must contain exactly one value per interval")
        for index, reference in enumerate(references):
            if not isinstance(reference, OptimizationIntervalReference):
                raise TypeError("interval_references must contain OptimizationIntervalReference values")
            if reference.interval_index != index:
                raise ValueError("interval references must be ordered by interval_index")
            if not math.isclose(reference.start_s, index * self.grid.dt_s, abs_tol=1.0e-9):
                raise ValueError("interval reference start differs from prediction grid")
            if not math.isclose(reference.end_s, (index + 1) * self.grid.dt_s, abs_tol=1.0e-9):
                raise ValueError("interval reference end differs from prediction grid")
        object.__setattr__(self, "state_sources", sources)
        object.__setattr__(self, "interval_references", references)

    def to_dict(self) -> dict[str, object]:
        provenance: list[dict[str, object]] = [
            {
                "knot_index": 0,
                "source": self.state_sources[0],
                "generating_interval": None,
                "heading_raw_index": None,
                "speed_raw_index": None,
            }
        ]
        provenance.extend(
            {
                "knot_index": index + 1,
                "source": self.state_sources[index + 1],
                "generating_interval": reference.interval_index,
                "heading_raw_index": reference.heading_raw_index,
                "speed_raw_index": reference.speed_raw_index,
            }
            for index, reference in enumerate(self.interval_references)
        )
        return {
            "grid": self.grid.to_dict(),
            "north_m": self.north_m.tolist(),
            "east_m": self.east_m.tolist(),
            "heading_rad": self.heading_rad.tolist(),
            "speed_mps": self.speed_mps.tolist(),
            "state_sources": list(self.state_sources),
            "state_provenance": provenance,
            "interval_references": [_json_value(value) for value in self.interval_references],
            "control_reference_count": len(self.interval_references),
            "terminal_knot_control_reference": None,
        }


@dataclass(frozen=True, order=True)
class EvidenceTrackKey:
    target_id: int
    generation: int

    def __post_init__(self) -> None:
        """Validate tracker-owned target identity."""
        if self.target_id < 0 or self.generation < 1:
            raise ValueError("target_id must be non-negative and generation positive")


@dataclass(frozen=True)
class PredictionPhaseEvidence:
    """Solver-consumed encounter phases aligned with one ownship prediction."""

    times_s: np.ndarray
    phases: tuple[str, ...]
    mission_bearing_rad: float
    avoidance_corridor_bearing_rad: float
    recovery_from_k: int | None
    target_keys: tuple[EvidenceTrackKey, ...]
    solver_consumed: bool

    def __post_init__(self) -> None:
        """Freeze phase evidence and reject ambiguous horizon semantics."""
        times = _readonly_vector(self.times_s, "times_s")
        phases = tuple(str(value) for value in self.phases)
        allowed = {"MISSION", "ALTER", "PASS", "RECOVER"}
        if len(phases) != times.size or any(value not in allowed for value in phases):
            raise ValueError("phases must contain one recognized value per state sample")
        if self.recovery_from_k is not None:
            if not 0 <= self.recovery_from_k < times.size:
                raise ValueError("recovery_from_k must fall inside the prediction grid")
            if any(value != "RECOVER" for value in phases[self.recovery_from_k :]):
                raise ValueError("recovery_from_k must begin a RECOVER suffix")
        elif "RECOVER" in phases:
            raise ValueError("RECOVER phases require recovery_from_k")
        if not np.isfinite((self.mission_bearing_rad, self.avoidance_corridor_bearing_rad)).all():
            raise ValueError("phase bearings must be finite")
        keys = tuple(sorted(self.target_keys))
        if len(set(keys)) != len(keys):
            raise ValueError("phase target keys must be unique")
        object.__setattr__(self, "times_s", times)
        object.__setattr__(self, "phases", phases)
        object.__setattr__(self, "target_keys", keys)


@dataclass(frozen=True)
class TargetPredictionEvidence:
    key: EvidenceTrackKey
    purpose: PredictionPurpose
    reference_time_s: float
    model: str
    north_m: np.ndarray
    east_m: np.ndarray
    admitted_to_nlp: bool
    solver_slot: int | None = None
    admission_disposition: str = "SELECTED"
    observation_time_s: float | None = None
    generated_at_s: float | None = None
    health: str = "UNKNOWN"
    source: str = "UNKNOWN"
    state_enu: np.ndarray | None = None
    covariance: np.ndarray | None = None
    length_m: float | None = None
    width_m: float | None = None
    lifecycle: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Freeze one purpose-specific target prediction."""
        if not isinstance(self.key, EvidenceTrackKey):
            raise TypeError("key must be EvidenceTrackKey")
        object.__setattr__(self, "purpose", PredictionPurpose(self.purpose))
        _require_finite(self.reference_time_s)
        if not self.model.strip() or not self.admission_disposition.strip():
            raise ValueError("prediction model and admission disposition are required")
        north = _readonly_vector(self.north_m, "north_m")
        east = _readonly_vector(self.east_m, "east_m")
        if north.size != east.size:
            raise ValueError("target prediction north/east vectors must align")
        if self.solver_slot is not None and self.solver_slot < 0:
            raise ValueError("solver_slot must be non-negative when present")
        timestamps = (self.observation_time_s, self.generated_at_s)
        if any(value is not None and (not math.isfinite(value) or value < 0.0) for value in timestamps):
            raise ValueError("target evidence timestamps must be finite and non-negative")
        if not self.health.strip() or not self.source.strip():
            raise ValueError("target evidence health and source are required")
        if self.state_enu is not None:
            state = _readonly_vector(self.state_enu, "state_enu")
            if state.size != 4:
                raise ValueError("state_enu must contain north, east, v_north, v_east")
            object.__setattr__(self, "state_enu", state)
        if self.covariance is not None:
            covariance = np.array(self.covariance, dtype=float, copy=True)
            if covariance.shape != (4, 4) or not np.isfinite(covariance).all():
                raise ValueError("covariance must be a finite 4x4 matrix")
            covariance.setflags(write=False)
            object.__setattr__(self, "covariance", covariance)
        geometry = (self.length_m, self.width_m)
        if any(value is not None and (not math.isfinite(value) or value <= 0.0) for value in geometry):
            raise ValueError("target evidence geometry must be finite and positive")
        object.__setattr__(self, "lifecycle", _freeze_json(self.lifecycle))
        object.__setattr__(self, "north_m", north)
        object.__setattr__(self, "east_m", east)


@dataclass(frozen=True)
class PredictionEvidenceRecord:
    algorithm_id: str
    candidate_hash: str
    acceptance_hash: str
    ownship: OwnshipPrediction
    target_predictions: tuple[TargetPredictionEvidence, ...]
    acceptance: Mapping[str, object]
    solver: Mapping[str, object]
    schema_version: str = EVIDENCE_SCHEMA
    canonicalizer_id: str = CANONICALIZER_ID
    _semantic_hash: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        """Freeze one stable Mid-MPC semantic record."""
        if not self.algorithm_id.strip() or not self.candidate_hash.strip() or not self.acceptance_hash.strip():
            raise ValueError("algorithm and semantic parent hashes are required")
        if not isinstance(self.ownship, OwnshipPrediction):
            raise TypeError("ownship must be OwnshipPrediction")
        targets = tuple(self.target_predictions)
        if not all(isinstance(value, TargetPredictionEvidence) for value in targets):
            raise TypeError("target_predictions must contain TargetPredictionEvidence values")
        identities = [(value.key, value.purpose) for value in targets]
        if len(set(identities)) != len(identities):
            raise ValueError("target prediction TrackKey/purpose identities must be unique")
        by_key: dict[EvidenceTrackKey, list[TargetPredictionEvidence]] = {}
        for target in targets:
            if target.north_m.size != self.ownship.grid.state_samples:
                raise ValueError("target prediction grid must align with ownship state samples")
            by_key.setdefault(target.key, []).append(target)
        for predictions in by_key.values():
            nlp = next((value for value in predictions if value.purpose is PredictionPurpose.NLP), None)
            safety = next((value for value in predictions if value.purpose is PredictionPurpose.L4_SAFETY), None)
            if nlp is not None and safety is None:
                raise ValueError("every NLP target requires an L4_SAFETY prediction")
            if (
                nlp is not None
                and safety is not None
                and nlp.model == safety.model
                and math.isclose(nlp.reference_time_s, safety.reference_time_s, abs_tol=1.0e-9)
                and (not np.array_equal(nlp.north_m, safety.north_m) or not np.array_equal(nlp.east_m, safety.east_m))
            ):
                raise ValueError("target prediction reconciliation mismatch")
        object.__setattr__(self, "target_predictions", tuple(sorted(targets, key=lambda item: (item.key, item.purpose))))
        object.__setattr__(self, "acceptance", _freeze_json(self.acceptance))
        object.__setattr__(self, "solver", _freeze_json(self.solver))
        semantic_hash = hashlib.sha256(canonical_bytes(self.to_dict(include_hash=False))).hexdigest()
        object.__setattr__(self, "_semantic_hash", semantic_hash)

    @property
    def semantic_hash(self) -> str:
        return self._semantic_hash

    def to_dict(self, *, include_hash: bool = True) -> dict[str, object]:
        value: dict[str, object] = {
            "schema_version": self.schema_version,
            "canonicalizer_id": self.canonicalizer_id,
            "algorithm_id": self.algorithm_id,
            "candidate_hash": self.candidate_hash,
            "acceptance_hash": self.acceptance_hash,
            "ownship": self.ownship.to_dict(),
            "target_predictions": [_json_value(item) for item in self.target_predictions],
            "acceptance": _json_value(self.acceptance),
            "solver": _json_value(self.solver),
        }
        if include_hash:
            value["semantic_hash"] = self.semantic_hash
        return value


@dataclass(frozen=True)
class EvidenceEnvelope:
    semantic_record: PredictionEvidenceRecord
    initial_events: tuple[EvidenceEvent, ...] = ()
    schema_version: str = "colav.prediction-evidence.envelope@1"

    def __post_init__(self) -> None:
        """Validate the generic solution-to-Adapter envelope."""
        if not isinstance(self.semantic_record, PredictionEvidenceRecord):
            raise TypeError("semantic_record must be PredictionEvidenceRecord")
        events = tuple(self.initial_events)
        if not all(isinstance(value, EvidenceEvent) for value in events):
            raise TypeError("initial_events must contain EvidenceEvent values")
        object.__setattr__(self, "initial_events", events)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "semantic_record": self.semantic_record.to_dict(),
            "initial_events": [event.to_dict() for event in self.initial_events],
        }

    def to_inline_dict(
        self,
        *,
        capacity_bytes: int = 8192,
        artifact_reference: Mapping[str, object] | None = None,
        authority: Mapping[str, object] | None = None,
    ) -> dict[str, object]:
        """Return the bounded realtime envelope without full trajectory vectors."""
        artifact = _json_value(artifact_reference) if artifact_reference is not None else None
        authority_document = _json_value(authority) if authority is not None else None
        fixed = {
            "schema_version": self.schema_version,
            "artifact_reference": artifact,
            "authority": authority_document,
        }
        inline_capacity = capacity_bytes - len(canonical_bytes(fixed)) - 32
        if inline_capacity < 256:
            authority_document = _externalize_inline_accepted_prediction(
                authority_document,
                artifact_reference=artifact,
            )
            fixed["authority"] = authority_document
            inline_capacity = capacity_bytes - len(canonical_bytes(fixed)) - 32
        if inline_capacity < 256:
            raise ValueError("INLINE_CAPACITY_EXCEEDED: accepted prediction requires external artifact capacity")
        value = {
            **fixed,
            "inline": inline_projection(self.semantic_record, capacity_bytes=inline_capacity),
        }
        if len(canonical_bytes(value)) > capacity_bytes:
            raise ValueError("INLINE_CAPACITY_EXCEEDED: envelope exceeds capacity")
        return value


@dataclass(frozen=True)
class EvidenceEvent:
    occurrence_id: OccurrenceId
    event_type: EvidenceEventType
    sim_time_s: float
    semantic_hash: str | None = None
    terminal_outcome: TerminalOutcome | None = None
    caused_by: OccurrenceId | None = None
    derived_from: tuple[str, ...] = ()
    payload: Mapping[str, object] = field(default_factory=dict)
    schema_version: str = EVENT_SCHEMA

    def __post_init__(self) -> None:
        """Freeze one runtime occurrence event."""
        if not isinstance(self.occurrence_id, OccurrenceId):
            raise TypeError("occurrence_id must be OccurrenceId")
        object.__setattr__(self, "event_type", EvidenceEventType(self.event_type))
        if self.terminal_outcome is not None:
            object.__setattr__(self, "terminal_outcome", TerminalOutcome(self.terminal_outcome))
        if self.caused_by is not None and not isinstance(self.caused_by, OccurrenceId):
            raise TypeError("caused_by must be OccurrenceId when present")
        parents = tuple(str(value) for value in self.derived_from)
        if any(not value for value in parents):
            raise ValueError("derived_from hashes must be non-empty")
        object.__setattr__(self, "derived_from", parents)
        _require_finite(self.sim_time_s)
        if self.sim_time_s < 0.0:
            raise ValueError("sim_time_s must be non-negative")
        object.__setattr__(self, "payload", _freeze_json(self.payload))

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "occurrence_id": self.occurrence_id.to_dict(),
            "event_type": self.event_type.value,
            "sim_time_s": self.sim_time_s,
            "semantic_hash": self.semantic_hash,
            "terminal_outcome": self.terminal_outcome.value if self.terminal_outcome is not None else None,
            "caused_by": self.caused_by.to_dict() if self.caused_by is not None else None,
            "derived_from": list(self.derived_from),
            "payload": _json_value(self.payload),
        }


@dataclass(frozen=True)
class EvidenceTimeline:
    latest_occurrence: OccurrenceId | None
    latest_terminal_outcome: TerminalOutcome | None
    active_semantic_hash: str | None
    active_receipt_hash: str | None
    last_committed_semantic_hash: str | None
    last_committed_executable: bool
    artifact_state: ArtifactState
    events: tuple[EvidenceEvent, ...]

    def to_dict(self) -> dict[str, object]:
        return _json_value(self)


@dataclass(frozen=True)
class EvidenceVerificationResult:
    valid: bool
    highest_verified_level: EvidenceVerificationLevel
    failures: tuple[str, ...]
    semantic_hash: str

    def to_dict(self) -> dict[str, object]:
        return _json_value(self)


def canonical_bytes(value: object) -> bytes:
    """Encode finite JSON using the versioned Colav Python canonicalizer."""
    normalized = _json_value(value)
    return json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _externalize_inline_accepted_prediction(
    authority: object,
    *,
    artifact_reference: object,
) -> object:
    """Replace oversized accepted-plan knots with a typed artifact reference.

    Full accepted prediction remains in the sealed semantic/artifact record.
    Realtime authority carries identity and the external reference only; it
    never truncates or silently drops a legal prediction.
    """
    if not isinstance(authority, dict):
        return authority
    receipt = authority.get("receipt")
    if not isinstance(receipt, dict) or not isinstance(receipt.get("accepted_prediction"), dict):
        return authority
    compact_authority = dict(authority)
    compact_receipt = dict(receipt)
    accepted_prediction = dict(compact_receipt.pop("accepted_prediction"))
    pending_artifact = artifact_reference is None
    reference = artifact_reference or {
        "status": "PENDING",
        "semantic_hash": accepted_prediction.get("evidence_semantic_hash"),
        "reason": "POST_COMMIT_ARTIFACT_PENDING",
    }
    compact_receipt["accepted_prediction"] = None
    compact_receipt["accepted_prediction_reference"] = {
        "artifact_reference": reference,
        "prediction_hash": accepted_prediction.get("prediction_hash"),
        "evidence_semantic_hash": accepted_prediction.get("evidence_semantic_hash"),
        "reference_time_s": accepted_prediction.get("reference_time_s"),
        "target_keys": accepted_prediction.get("target_keys", []),
        "basis": accepted_prediction.get("basis"),
        "model": accepted_prediction.get("model"),
        "source": accepted_prediction.get("source"),
    }
    compact_receipt["accepted_prediction_unavailable_reason"] = (
        "INLINE_CAPACITY_EXTERNAL_ARTIFACT_PENDING" if pending_artifact else "INLINE_CAPACITY_EXTERNAL_ARTIFACT"
    )
    compact_authority["receipt"] = compact_receipt
    return compact_authority


def reduce_evidence(events: Sequence[EvidenceEvent]) -> EvidenceTimeline:  # noqa: C901, PLR0912, PLR0915
    """Reduce one run/epoch event sequence into its only authority read model."""
    ordered = tuple(events)
    if not ordered:
        return EvidenceTimeline(None, None, None, None, None, False, ArtifactState.NONE, ())
    run_epoch = (ordered[0].occurrence_id.run_id, ordered[0].occurrence_id.epoch)
    previous_seq = -1
    seen_occurrences: set[OccurrenceId] = set()
    active_semantic_hash: str | None = None
    active_receipt_hash: str | None = None
    last_committed_semantic_hash: str | None = None
    last_committed_executable = False
    latest_candidate_semantic_hash: str | None = None
    latest_terminal: TerminalOutcome | None = None
    artifact_states: dict[str, ArtifactState] = {}
    cycle_terminal_seen = False
    cycle_started = False
    cycle_terminal: TerminalOutcome | None = None
    cycle_command_applied = False
    for event in ordered:
        occurrence = event.occurrence_id
        if (occurrence.run_id, occurrence.epoch) != run_epoch:
            raise ValueError("evidence events must belong to one run and epoch")
        if occurrence.event_seq <= previous_seq:
            raise ValueError("event_seq must be strictly increasing")
        if event.caused_by is not None and event.caused_by not in seen_occurrences:
            raise ValueError("causal parent must precede the derived event")
        previous_seq = occurrence.event_seq
        seen_occurrences.add(occurrence)
        if event.event_type is EvidenceEventType.CYCLE_STARTED:
            if cycle_started:
                _validate_completed_cycle(cycle_terminal, cycle_command_applied)
            cycle_started = True
            cycle_terminal_seen = False
            cycle_terminal = None
            cycle_command_applied = False
        if event.event_type is EvidenceEventType.CANDIDATE_PRODUCED:
            if event.semantic_hash is None:
                raise ValueError("CANDIDATE_PRODUCED requires semantic_hash")
            latest_candidate_semantic_hash = event.semantic_hash
        if event.terminal_outcome is not None:
            expected_event = {
                TerminalOutcome.COMMITTED: EvidenceEventType.PLAN_COMMITTED,
                TerminalOutcome.HELD: EvidenceEventType.PLAN_HELD,
                TerminalOutcome.REJECTED: EvidenceEventType.PLAN_REJECTED,
                TerminalOutcome.FAILED: EvidenceEventType.PLAN_FAILED,
            }[event.terminal_outcome]
            if not cycle_started or event.event_type is not expected_event:
                raise ValueError("terminal outcome must match an open planning cycle")
            if cycle_terminal_seen:
                raise ValueError("each planning cycle may contain only one terminal control outcome")
            cycle_terminal_seen = True
            latest_terminal = event.terminal_outcome
            cycle_terminal = event.terminal_outcome
            if event.terminal_outcome is TerminalOutcome.COMMITTED:
                if event.semantic_hash is None:
                    raise ValueError("committed event requires semantic_hash")
                receipt_hash = event.payload.get("receipt_hash")
                if not isinstance(receipt_hash, str) or not receipt_hash:
                    raise ValueError("committed event requires receipt_hash")
                active_semantic_hash = event.semantic_hash
                active_receipt_hash = receipt_hash
                last_committed_semantic_hash = event.semantic_hash
                last_committed_executable = True
            elif event.terminal_outcome is TerminalOutcome.HELD:
                if active_semantic_hash is None:
                    raise ValueError("held event requires an active committed plan")
            else:
                active_semantic_hash = None
                active_receipt_hash = None
                last_committed_executable = False
        if event.event_type is EvidenceEventType.COMMAND_APPLIED:
            if active_semantic_hash is None:
                raise ValueError("COMMAND_APPLIED requires an active committed plan")
            if event.semantic_hash != active_semantic_hash:
                raise ValueError("COMMAND_APPLIED semantic_hash must match the active plan")
            if cycle_command_applied:
                raise ValueError("each committed or held cycle may apply only one command")
            cycle_command_applied = True
        artifact_by_event = {
            EvidenceEventType.ARTIFACT_QUEUED: ArtifactState.QUEUED,
            EvidenceEventType.ARTIFACT_COMPLETE: ArtifactState.COMPLETE,
            EvidenceEventType.ARTIFACT_INCOMPLETE: ArtifactState.INCOMPLETE,
            EvidenceEventType.ARTIFACT_BACKPRESSURE: ArtifactState.BACKPRESSURE,
        }
        if event.event_type in artifact_by_event:
            if event.semantic_hash is None:
                raise ValueError("artifact status event requires semantic_hash")
            artifact_states[event.semantic_hash] = artifact_by_event[event.event_type]
    if cycle_started:
        _validate_completed_cycle(cycle_terminal, cycle_command_applied)
    relevant_semantic_hash = latest_candidate_semantic_hash or active_semantic_hash or last_committed_semantic_hash
    return EvidenceTimeline(
        latest_occurrence=ordered[-1].occurrence_id,
        latest_terminal_outcome=latest_terminal,
        active_semantic_hash=active_semantic_hash,
        active_receipt_hash=active_receipt_hash,
        last_committed_semantic_hash=last_committed_semantic_hash,
        last_committed_executable=last_committed_executable,
        artifact_state=artifact_states.get(relevant_semantic_hash, ArtifactState.NONE),
        events=ordered,
    )


def _validate_completed_cycle(terminal: TerminalOutcome | None, command_applied: bool) -> None:
    if terminal is None:
        raise ValueError("planning cycle requires one terminal control outcome")
    if terminal in {TerminalOutcome.COMMITTED, TerminalOutcome.HELD} and not command_applied:
        raise ValueError("committed or held cycle requires COMMAND_APPLIED")


def inline_projection(record: PredictionEvidenceRecord, *, capacity_bytes: int = 8192) -> dict[str, object]:
    """Produce the deterministic bounded evidence summary used by realtime APIs."""
    if capacity_bytes < 256:
        raise ValueError("capacity_bytes is too small for the mandatory evidence envelope")
    acceptance = _json_value(record.acceptance)
    failures = acceptance.get("mandatory_failures", []) if isinstance(acceptance, dict) else []
    accepted = acceptance.get("accepted") if isinstance(acceptance, dict) else None
    tier0: dict[str, object] = {
        "schema_version": INLINE_SCHEMA,
        "semantic_hash": record.semantic_hash,
        "algorithm_id": record.algorithm_id,
        "candidate_hash": record.candidate_hash,
        "acceptance_hash": record.acceptance_hash,
        "accepted": accepted,
        "mandatory_failures": failures,
        "truncated": False,
        "truncated_sections": [],
    }
    optional = {
        "worst_safety": acceptance.get("worst_safety") if isinstance(acceptance, dict) else None,
        "advisory": acceptance.get("advisory", []) if isinstance(acceptance, dict) else [],
        "solver": _json_value(record.solver),
        "grid": record.ownship.grid.to_dict(),
    }
    projection = {**tier0, **optional}
    if len(canonical_bytes(projection)) <= capacity_bytes:
        return projection
    for section in ("advisory", "solver", "grid", "worst_safety"):
        projection.pop(section, None)
        projection["truncated"] = True
        cast_sections = projection["truncated_sections"]
        if not isinstance(cast_sections, list):
            raise TypeError("truncated_sections must remain a list")
        cast_sections.append(section)
        if len(canonical_bytes(projection)) <= capacity_bytes:
            return projection
    if len(canonical_bytes(projection)) > capacity_bytes:
        raise ValueError("INLINE_CAPACITY_EXCEEDED: Tier0 and mandatory failures exceed capacity")
    return projection


def render_snapshot(
    record: PredictionEvidenceRecord,
    timeline: EvidenceTimeline,
    *,
    runtime_reference: RuntimeAppliedReference | None = None,
) -> dict[str, object]:
    """Build the only typed projection consumed by realtime prediction UIs."""
    ownship = record.ownship
    start_index = 0
    north = ownship.north_m.tolist()
    east = ownship.east_m.tolist()
    heading = ownship.heading_rad.tolist()
    speed = ownship.speed_mps.tolist()
    time_s = list(ownship.grid.times_s)
    if runtime_reference is not None:
        start_index = min(runtime_reference.interval_index, ownship.grid.state_samples - 1)
        upper = min(start_index + 1, ownship.grid.state_samples - 1)
        fraction = runtime_reference.interpolation_fraction
        first_north = float(
            ownship.north_m[start_index] + fraction * (ownship.north_m[upper] - ownship.north_m[start_index])
        )
        first_east = float(ownship.east_m[start_index] + fraction * (ownship.east_m[upper] - ownship.east_m[start_index]))
        north = [first_north, *ownship.north_m[upper:].tolist()]
        east = [first_east, *ownship.east_m[upper:].tolist()]
        heading = [runtime_reference.heading_rad, *ownship.heading_rad[upper:].tolist()]
        speed = [runtime_reference.speed_mps, *ownship.speed_mps[upper:].tolist()]
        time_s = [runtime_reference.elapsed_s, *list(ownship.grid.times_s[upper:])]
    active = timeline.active_semantic_hash == record.semantic_hash
    if active:
        style = "ACTIVE"
    elif timeline.latest_terminal_outcome is TerminalOutcome.REJECTED:
        style = "REJECTED"
    else:
        style = "INVALID_HISTORY"
    lateral = np.asarray(east, dtype=float)
    north_array = np.asarray(north, dtype=float)
    if len(north) > 1:
        chord = np.array([north_array[-1] - north_array[0], lateral[-1] - lateral[0]])
        chord_norm = float(np.linalg.norm(chord))
        if chord_norm > 1.0e-12:
            offsets = np.column_stack((north_array - north_array[0], lateral - lateral[0]))
            lateral_deviation = float(np.max(np.abs(offsets[:, 0] * chord[1] - offsets[:, 1] * chord[0])) / chord_norm)
        else:
            lateral_deviation = 0.0
    else:
        lateral_deviation = 0.0
    return {
        "schema_version": "colav.mid_mpc.prediction-render@1",
        "semantic_hash": record.semantic_hash,
        "frame": "ENU",
        "trajectory_source": "IPOPT_PRIMAL",
        "style": style,
        "executable": active,
        "grid": ownship.grid.to_dict(),
        "ownship": {
            "time_s": time_s,
            "north_m": north,
            "east_m": east,
            "heading_rad": heading,
            "speed_mps": speed,
            "start_knot_index": start_index,
        },
        "targets": [_json_value(item) for item in record.target_predictions],
        "runtime_applied_reference": (_json_value(runtime_reference) if runtime_reference is not None else None),
        "quality": {
            "course_span_rad": float(np.ptp(np.unwrap(np.asarray(heading, dtype=float)))) if heading else 0.0,
            "speed_span_mps": float(np.ptp(np.asarray(speed, dtype=float))) if speed else 0.0,
            "lateral_deviation_m": lateral_deviation,
        },
        "planner_l4": _json_value(record.acceptance),
        "authority": {
            "latest_terminal_outcome": (
                timeline.latest_terminal_outcome.value if timeline.latest_terminal_outcome is not None else None
            ),
            "active_semantic_hash": timeline.active_semantic_hash,
            "active_receipt_hash": timeline.active_receipt_hash,
            "last_committed_semantic_hash": timeline.last_committed_semantic_hash,
            "last_committed_executable": timeline.last_committed_executable,
            "artifact_state": timeline.artifact_state.value,
        },
        "evaluator_g3": None,
    }


def verify_evidence(  # noqa: PLR0911, PLR0912
    record: PredictionEvidenceRecord,
    events: Sequence[EvidenceEvent],
    *,
    expected_semantic_hash: str | None = None,
    require_runtime_authority: bool = True,
) -> EvidenceVerificationResult:
    """Verify deterministic V0-V6 evidence without re-running IPOPT."""
    failures: list[str] = []
    semantic_hash = record.semantic_hash
    expected = semantic_hash if expected_semantic_hash is None else expected_semantic_hash
    if semantic_hash != expected:
        failures.append("SEMANTIC_HASH_MISMATCH")
        return EvidenceVerificationResult(False, EvidenceVerificationLevel.NONE, tuple(failures), semantic_hash)
    level = EvidenceVerificationLevel.BYTES_DIGEST
    if record.schema_version != EVIDENCE_SCHEMA or record.canonicalizer_id != CANONICALIZER_ID:
        failures.append("UNSUPPORTED_SCHEMA")
        return EvidenceVerificationResult(False, level, tuple(failures), semantic_hash)
    level = EvidenceVerificationLevel.SCHEMA
    try:
        timeline = reduce_evidence(events)
    except ValueError:
        failures.append("LINEAGE_INVALID")
        return EvidenceVerificationResult(False, level, tuple(failures), semantic_hash)
    candidates = [
        event.semantic_hash for event in timeline.events if event.event_type is EvidenceEventType.CANDIDATE_PRODUCED
    ]
    if candidates and candidates[-1] != semantic_hash:
        failures.append("EVENT_SEMANTIC_HASH_MISMATCH")
        return EvidenceVerificationResult(False, level, tuple(failures), semantic_hash)
    if timeline.latest_terminal_outcome in {TerminalOutcome.COMMITTED, TerminalOutcome.HELD} and (
        timeline.active_semantic_hash != semantic_hash
    ):
        failures.append("EVENT_SEMANTIC_HASH_MISMATCH")
        return EvidenceVerificationResult(False, level, tuple(failures), semantic_hash)
    level = EvidenceVerificationLevel.LINEAGE
    ownship = record.ownship
    expected_north = [float(ownship.north_m[0])]
    expected_east = [float(ownship.east_m[0])]
    for reference in ownship.interval_references:
        expected_north.append(expected_north[-1] + reference.speed_mps * math.cos(reference.heading_rad) * ownship.grid.dt_s)
        expected_east.append(expected_east[-1] + reference.speed_mps * math.sin(reference.heading_rad) * ownship.grid.dt_s)
    if not np.allclose(ownship.north_m, expected_north, rtol=0.0, atol=1.0e-6) or not np.allclose(
        ownship.east_m,
        expected_east,
        rtol=0.0,
        atol=1.0e-6,
    ):
        failures.append("NUMERICAL_REPLAY_MISMATCH")
        return EvidenceVerificationResult(False, level, tuple(failures), semantic_hash)
    level = EvidenceVerificationLevel.NUMERICAL
    accepted = record.acceptance.get("accepted")
    mandatory_failures = record.acceptance.get("mandatory_failures")
    if not isinstance(accepted, bool):
        failures.append("L4_ACCEPTANCE_MISSING")
        return EvidenceVerificationResult(False, level, tuple(failures), semantic_hash)
    if not isinstance(mandatory_failures, tuple) or accepted == bool(mandatory_failures):
        failures.append("L4_VERDICT_INCONSISTENT")
        return EvidenceVerificationResult(False, level, tuple(failures), semantic_hash)
    level = EvidenceVerificationLevel.L4
    try:
        inline_projection(record)
    except ValueError:
        failures.append("PROJECTION_INVALID")
        return EvidenceVerificationResult(False, level, tuple(failures), semantic_hash)
    level = EvidenceVerificationLevel.PROJECTION
    if not require_runtime_authority:
        return EvidenceVerificationResult(True, level, (), semantic_hash)
    if timeline.latest_terminal_outcome is None:
        failures.append("RUNTIME_TERMINAL_MISSING")
        return EvidenceVerificationResult(False, level, tuple(failures), semantic_hash)
    level = EvidenceVerificationLevel.RUNTIME_AUTHORITY
    return EvidenceVerificationResult(True, level, (), semantic_hash)


def prediction_evidence_from_dict(value: Mapping[str, object]) -> PredictionEvidenceRecord:
    """Parse a semantic record through the same strict public constructors."""
    ownship_value = _mapping(value.get("ownship"), "ownship")
    grid_value = _mapping(ownship_value.get("grid"), "ownship.grid")
    grid = PredictionGrid(
        intervals=int(grid_value["intervals"]),
        dt_s=float(grid_value["dt_s"]),
    )
    references = tuple(
        OptimizationIntervalReference(
            interval_index=int(item["interval_index"]),
            start_s=float(item["start_s"]),
            end_s=float(item["end_s"]),
            heading_rad=float(item["heading_rad"]),
            speed_mps=float(item["speed_mps"]),
            heading_raw_index=int(item["heading_raw_index"]),
            speed_raw_index=int(item["speed_raw_index"]),
        )
        for raw_item in _sequence(ownship_value.get("interval_references"), "ownship.interval_references")
        for item in [_mapping(raw_item, "interval_reference")]
    )
    ownship = OwnshipPrediction(
        grid=grid,
        north_m=ownship_value["north_m"],
        east_m=ownship_value["east_m"],
        heading_rad=ownship_value["heading_rad"],
        speed_mps=ownship_value["speed_mps"],
        state_sources=tuple(str(item) for item in _sequence(ownship_value.get("state_sources"), "state_sources")),
        interval_references=references,
    )
    targets: list[TargetPredictionEvidence] = []
    for raw_target in _sequence(value.get("target_predictions", ()), "target_predictions"):
        target = _mapping(raw_target, "target_prediction")
        key = _mapping(target.get("key"), "target_prediction.key")
        targets.append(
            TargetPredictionEvidence(
                key=EvidenceTrackKey(int(key["target_id"]), int(key["generation"])),
                purpose=PredictionPurpose(str(target["purpose"])),
                reference_time_s=float(target["reference_time_s"]),
                model=str(target["model"]),
                north_m=target["north_m"],
                east_m=target["east_m"],
                admitted_to_nlp=bool(target["admitted_to_nlp"]),
                solver_slot=int(target["solver_slot"]) if target.get("solver_slot") is not None else None,
                admission_disposition=str(target["admission_disposition"]),
                observation_time_s=(
                    float(target["observation_time_s"]) if target.get("observation_time_s") is not None else None
                ),
                generated_at_s=float(target["generated_at_s"]) if target.get("generated_at_s") is not None else None,
                health=str(target.get("health", "UNKNOWN")),
                source=str(target.get("source", "UNKNOWN")),
                state_enu=target.get("state_enu"),
                covariance=target.get("covariance"),
                length_m=float(target["length_m"]) if target.get("length_m") is not None else None,
                width_m=float(target["width_m"]) if target.get("width_m") is not None else None,
                lifecycle=_mapping(target.get("lifecycle", {}), "target_prediction.lifecycle"),
            )
        )
    return PredictionEvidenceRecord(
        algorithm_id=str(value["algorithm_id"]),
        candidate_hash=str(value["candidate_hash"]),
        acceptance_hash=str(value["acceptance_hash"]),
        ownship=ownship,
        target_predictions=tuple(targets),
        acceptance=_mapping(value.get("acceptance"), "acceptance"),
        solver=_mapping(value.get("solver"), "solver"),
        schema_version=str(value.get("schema_version", "")),
        canonicalizer_id=str(value.get("canonicalizer_id", "")),
    )


def evidence_event_from_dict(value: Mapping[str, object]) -> EvidenceEvent:
    """Parse one occurrence event from a persisted trace."""
    occurrence_value = _mapping(value.get("occurrence_id"), "occurrence_id")
    caused_by_value = value.get("caused_by")
    caused_by_mapping = _mapping(caused_by_value, "caused_by") if caused_by_value is not None else None
    return EvidenceEvent(
        occurrence_id=OccurrenceId(
            str(occurrence_value["run_id"]),
            int(occurrence_value["epoch"]),
            int(occurrence_value["event_seq"]),
        ),
        event_type=EvidenceEventType(str(value["event_type"])),
        sim_time_s=float(value["sim_time_s"]),
        semantic_hash=str(value["semantic_hash"]) if value.get("semantic_hash") is not None else None,
        terminal_outcome=(
            TerminalOutcome(str(value["terminal_outcome"])) if value.get("terminal_outcome") is not None else None
        ),
        caused_by=(
            OccurrenceId(
                str(caused_by_mapping["run_id"]),
                int(caused_by_mapping["epoch"]),
                int(caused_by_mapping["event_seq"]),
            )
            if caused_by_mapping is not None
            else None
        ),
        derived_from=tuple(str(item) for item in _sequence(value.get("derived_from", ()), "derived_from")),
        payload=_mapping(value.get("payload", {}), "payload"),
        schema_version=str(value.get("schema_version", "")),
    )


def verify_evidence_document(value: Mapping[str, object]) -> EvidenceVerificationResult:
    """Verify one artifact or trace document through the public V0-V6 entrypoint."""
    raw_record = _mapping(value.get("prediction_evidence"), "prediction_evidence")
    declared_hash = raw_record.get("semantic_hash")
    record = prediction_evidence_from_dict(raw_record)
    raw_events = _sequence(value.get("prediction_evidence_events", ()), "prediction_evidence_events")
    events = tuple(evidence_event_from_dict(_mapping(item, "prediction_evidence_event")) for item in raw_events)
    return verify_evidence(
        record,
        events,
        expected_semantic_hash=str(declared_hash) if declared_hash is not None else "",
        require_runtime_authority="prediction_evidence_events" in value,
    )


def _readonly_vector(value: object, name: str) -> np.ndarray:
    array = np.array(value, dtype=float, copy=True)
    if array.ndim != 1 or not np.isfinite(array).all():
        raise ValueError(f"{name} must be a finite one-dimensional vector")
    array.setflags(write=False)
    return array


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be a mapping")
    return value


def _sequence(value: object, name: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError(f"{name} must be a sequence")
    return value


def _require_finite(*values: float) -> None:
    if not all(math.isfinite(float(value)) for value in values):
        raise ValueError("values must be finite")


def _freeze_json(value: object) -> Any:
    normalized = _json_value(value)
    if isinstance(normalized, dict):
        return MappingProxyType({str(key): _freeze_json(item) for key, item in normalized.items()})
    if isinstance(normalized, list):
        return tuple(_freeze_json(item) for item in normalized)
    return normalized


def _json_value(value: object) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    if is_dataclass(value) and not isinstance(value, type):
        return {item.name: _json_value(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, float) and value == 0.0:
        return 0.0
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("canonical evidence values must be finite")
    return value
