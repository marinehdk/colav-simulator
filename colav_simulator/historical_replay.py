"""Historical AIS reconstruction and replay contracts.

The reconstruction layer turns the immutable raw/normalized observations from
``historical_ais`` into a world definition.  It deliberately does not expose
the complete trajectory through the planner interface: runtime integration
asks the actor for the state at the current simulation time only.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any

import numpy as np
from pyproj import Transformer

from colav_simulator import scenario_config
from colav_simulator.core.colav.diagnostics import PlannerTrace
from colav_simulator.core.ship import Config as ShipConfig
from colav_simulator.core.ship import Ship
from colav_simulator.historical_ais import (
    HistoricalAISNormalizedFact,
    HistoricalAISObservation,
    HistoricalAISReadResult,
)
from colav_simulator.historical_serialization import angle_delta as _angle_delta
from colav_simulator.historical_serialization import semantic_hash as _sha256_json

if TYPE_CHECKING:
    from colav_simulator.experiment.session import SimulationSession

RECONSTRUCTION_SCHEMA_VERSION = "historical-actor-reconstruction.v1"
COUNTERFACTUAL_ROUTE_EXTENSION_M = 10_000.0


UTC = timezone.utc


class HistoricalActorSampleKind(str, Enum):
    """Provenance of one world-truth sample."""

    OBSERVED = "observed"
    INTERPOLATED = "interpolated"


class HistoricalReplayQualificationStatus(str, Enum):
    DIMENSIONS_UNAVAILABLE = "DIMENSIONS_UNAVAILABLE"
    QUALITY_INCOMPLETE = "QUALITY_INCOMPLETE"


class HistoricalReplayQualificationError(ValueError):
    """Typed fail-closed boundary before normal Ship/Session construction."""

    def __init__(self, status: HistoricalReplayQualificationStatus, message: str) -> None:
        super().__init__(message)
        self.status = HistoricalReplayQualificationStatus(status)


@dataclass(frozen=True)
class HistoricalAISReconstructionProfile:
    """Versioned, deterministic policy for converting AIS observations to actors."""

    profile_id: str = RECONSTRUCTION_SCHEMA_VERSION
    time_step_s: float = 1.0
    max_interpolation_gap_s: float = 300.0
    projection_crs: str = "EPSG:32633"
    source_crs: str = "EPSG:4326"
    coordinate_axis_order: str = "longitude_latitude"
    gap_policy: str = "terminate_without_ghost_extrapolation"

    def __post_init__(self) -> None:
        """Reject reconstruction policies that could produce unbounded ghosts."""
        if not self.profile_id.strip():
            raise ValueError("profile_id is required")
        for name in ("time_step_s", "max_interpolation_gap_s"):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value <= 0.0:
                raise ValueError(f"{name} must be finite and positive")
            object.__setattr__(self, name, value)
        if self.max_interpolation_gap_s < self.time_step_s:
            raise ValueError("max_interpolation_gap_s must be at least time_step_s")
        if self.coordinate_axis_order != "longitude_latitude":
            raise ValueError("coordinate_axis_order must be longitude_latitude")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": RECONSTRUCTION_SCHEMA_VERSION,
            "profile_id": self.profile_id,
            "time_step_s": self.time_step_s,
            "max_interpolation_gap_s": self.max_interpolation_gap_s,
            "projection_crs": self.projection_crs,
            "source_crs": self.source_crs,
            "coordinate_axis_order": self.coordinate_axis_order,
            "gap_policy": self.gap_policy,
        }

    @property
    def digest(self) -> str:
        return _sha256_json(self.to_dict())


@dataclass(frozen=True)
class HistoricalAISSourceObservationRef:
    """Stable reference to one raw AIS observation."""

    entry_name: str
    source_row_index: int
    row_sha256: str
    duplicate_version: int = 0

    @classmethod
    def from_observation(cls, observation: HistoricalAISObservation) -> HistoricalAISSourceObservationRef:
        raw = observation.raw
        return cls(raw.entry_name, raw.source_row_index, raw.row_sha256, raw.duplicate_version)

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_name": self.entry_name,
            "source_row_index": self.source_row_index,
            "row_sha256": self.row_sha256,
            "duplicate_version": self.duplicate_version,
        }


@dataclass(frozen=True)
class HistoricalActorWorldSample:
    """One immutable world-truth sample, never a tracker observation."""

    time_s: float
    timestamp_utc: datetime
    state_vxvy: tuple[float, float, float, float]
    kind: HistoricalActorSampleKind
    source_observation_refs: tuple[HistoricalAISSourceObservationRef, ...] = ()

    def __post_init__(self) -> None:
        """Freeze normalized state and source references."""
        state = tuple(float(value) for value in self.state_vxvy)
        if len(state) != 4 or not all(math.isfinite(value) for value in state):
            raise ValueError("Historical Actor state must be four finite values")
        if not math.isfinite(float(self.time_s)):
            raise ValueError("Historical Actor sample time must be finite")
        timestamp = self.timestamp_utc
        if timestamp.tzinfo is None:
            raise ValueError("Historical Actor sample timestamp must be timezone-aware")
        object.__setattr__(self, "state_vxvy", state)
        object.__setattr__(self, "kind", HistoricalActorSampleKind(self.kind))
        object.__setattr__(self, "source_observation_refs", tuple(self.source_observation_refs))
        object.__setattr__(self, "timestamp_utc", timestamp.astimezone(UTC))

    @property
    def observed(self) -> bool:
        return self.kind is HistoricalActorSampleKind.OBSERVED

    def to_dict(self) -> dict[str, Any]:
        return {
            "time_s": self.time_s,
            "timestamp_utc": self.timestamp_utc.isoformat(),
            "state_vxvy": list(self.state_vxvy),
            "kind": self.kind.value,
            "source_observation_refs": [ref.to_dict() for ref in self.source_observation_refs],
        }


@dataclass(frozen=True)
class HistoricalActor:
    """Reconstructed vessel world truth with explicit source provenance."""

    actor_id: int
    mmsi: int
    samples: tuple[HistoricalActorWorldSample, ...]
    observed_source_points: int
    derived_world_samples: int
    length_m: float | None
    width_m: float | None
    dimensions_provenance: str
    source_observation_digest: str
    draft_m: float | None = None
    actor_digest: str = ""
    _sample_times: tuple[float, ...] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        """Validate and freeze the actor sample sequence."""
        samples = tuple(sorted(self.samples, key=lambda sample: (sample.time_s, sample.kind.value)))
        if not samples:
            raise ValueError("Historical Actor requires at least one world sample")
        if self.actor_id < 0 or self.mmsi < 0:
            raise ValueError("Historical Actor identifiers must be non-negative")
        if self.observed_source_points < 1:
            raise ValueError("Historical Actor requires an observed source point")
        if self.derived_world_samples < 0:
            raise ValueError("derived_world_samples must be non-negative")
        if self.length_m is not None and (not math.isfinite(self.length_m) or self.length_m <= 0):
            raise ValueError("length_m must be positive when provided")
        if self.width_m is not None and (not math.isfinite(self.width_m) or self.width_m <= 0):
            raise ValueError("width_m must be positive when provided")
        if self.draft_m is not None and (not math.isfinite(self.draft_m) or self.draft_m <= 0):
            raise ValueError("draft_m must be positive when provided")
        object.__setattr__(self, "samples", samples)
        object.__setattr__(self, "_sample_times", tuple(sample.time_s for sample in samples))
        if not self.actor_digest:
            object.__setattr__(self, "actor_digest", _sha256_json(self._identity_dict()))

    @property
    def first_time_s(self) -> float:
        return self.samples[0].time_s

    @property
    def last_time_s(self) -> float:
        return self.samples[-1].time_s

    @property
    def dimensions_known(self) -> bool:
        return self.length_m is not None and self.width_m is not None

    @property
    def active_intervals(self) -> tuple[tuple[float, float], ...]:
        """Return intervals connected by permitted interpolation gaps."""
        intervals: list[tuple[float, float]] = []
        start = self.samples[0].time_s
        end = start
        for previous, current in zip(self.samples, self.samples[1:], strict=False):
            if current.time_s - previous.time_s <= self._max_gap_s:
                end = current.time_s
            else:
                intervals.append((start, end))
                start = current.time_s
                end = current.time_s
        intervals.append((start, end))
        return tuple(intervals)

    @property
    def _max_gap_s(self) -> float:
        # Persisted actor samples carry the profile's allowed gaps in their
        # source metadata through the private attribute attached by the builder.
        return float(getattr(self, "_configured_max_gap_s", 0.0)) or self._infer_max_gap()

    def _infer_max_gap(self) -> float:
        # The constructor is also useful for deserialized samples.  A sample
        # sequence with derived points has no need for a wider gap than the
        # largest adjacent interval; long gaps are represented as singletons.
        derived_times = [sample.time_s for sample in self.samples if sample.kind is HistoricalActorSampleKind.INTERPOLATED]
        if not derived_times:
            return 0.0
        return max(
            (current - previous for previous, current in zip(self._sample_times, self._sample_times[1:], strict=False)),
            default=0.0,
        )

    def sample_at(self, time_s: float) -> HistoricalActorWorldSample | None:
        """Return only the current world state; never a future trajectory view."""
        query = float(time_s)
        if not math.isfinite(query):
            raise ValueError("time_s must be finite")
        samples = self.samples
        for sample in samples:
            if math.isclose(sample.time_s, query, rel_tol=0.0, abs_tol=1e-9):
                return sample
        if query < samples[0].time_s or query > samples[-1].time_s:
            return None
        upper = next((index for index, sample in enumerate(samples) if sample.time_s > query), None)
        if upper is None or upper == 0:
            return None
        lower_sample = samples[upper - 1]
        upper_sample = samples[upper]
        delta = upper_sample.time_s - lower_sample.time_s
        if delta <= 0.0 or delta > self._max_gap_s:
            return None
        fraction = (query - lower_sample.time_s) / delta
        state = tuple(
            lower_sample.state_vxvy[index] + fraction * (upper_sample.state_vxvy[index] - lower_sample.state_vxvy[index])
            for index in range(4)
        )
        timestamp = lower_sample.timestamp_utc + timedelta(seconds=query - lower_sample.time_s)
        return HistoricalActorWorldSample(
            time_s=query,
            timestamp_utc=timestamp,
            state_vxvy=state,
            kind=HistoricalActorSampleKind.INTERPOLATED,
            source_observation_refs=(
                *lower_sample.source_observation_refs,
                *upper_sample.source_observation_refs,
            ),
        )

    def _identity_dict(self) -> dict[str, Any]:
        return {
            "actor_id": self.actor_id,
            "mmsi": self.mmsi,
            "samples": [sample.to_dict() for sample in self.samples],
            "observed_source_points": self.observed_source_points,
            "derived_world_samples": self.derived_world_samples,
            "length_m": self.length_m,
            "width_m": self.width_m,
            "dimensions_provenance": self.dimensions_provenance,
            "draft_m": self.draft_m,
            "source_observation_digest": self.source_observation_digest,
        }

    def to_dict(self) -> dict[str, Any]:
        output = self._identity_dict()
        output["actor_digest"] = self.actor_digest
        output["active_intervals"] = [list(interval) for interval in self.active_intervals]
        return output


@dataclass(frozen=True)
class HistoricalActorState:
    """Current actor state exposed to the normal sensor/tracker chain."""

    actor_id: int
    mmsi: int
    sample: HistoricalActorWorldSample
    length_m: float | None
    width_m: float | None


@dataclass(frozen=True)
class HistoricalActorSet:
    """Immutable reconstructed environment and its lineage."""

    dataset_digest: str
    selection_digest: str
    profile: HistoricalAISReconstructionProfile
    time_origin_utc: datetime
    actors: tuple[HistoricalActor, ...]
    semantic_digest: str = ""
    provider: str = "unknown"
    attribution: str = ""
    coverage_limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Freeze actor ordering and establish the semantic identity."""
        actors = tuple(sorted(self.actors, key=lambda actor: (actor.actor_id, actor.mmsi)))
        if self.time_origin_utc.tzinfo is None:
            raise ValueError("time_origin_utc must be timezone-aware")
        object.__setattr__(self, "actors", actors)
        object.__setattr__(self, "time_origin_utc", self.time_origin_utc.astimezone(UTC))
        object.__setattr__(self, "coverage_limitations", tuple(self.coverage_limitations))
        if not self.semantic_digest:
            object.__setattr__(self, "semantic_digest", _sha256_json(self._identity_dict()))

    def actor(self, actor_id: int) -> HistoricalActor:
        for actor in self.actors:
            if actor.actor_id == actor_id:
                return actor
        raise KeyError(actor_id)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> HistoricalActorSet:
        """Restore a sealed actor set without reopening the raw archive."""
        profile_document = dict(value["profile"])
        profile_document.pop("schema_version", None)
        profile = HistoricalAISReconstructionProfile(**profile_document)
        actors = []
        for actor_document in value["actors"]:
            samples = tuple(
                HistoricalActorWorldSample(
                    time_s=float(sample["time_s"]),
                    timestamp_utc=datetime.fromisoformat(sample["timestamp_utc"]).astimezone(UTC),
                    state_vxvy=tuple(sample["state_vxvy"]),
                    kind=HistoricalActorSampleKind(sample["kind"]),
                    source_observation_refs=tuple(
                        HistoricalAISSourceObservationRef(**dict(reference))
                        for reference in sample.get("source_observation_refs", ())
                    ),
                )
                for sample in actor_document["samples"]
            )
            actor = HistoricalActor(
                actor_id=int(actor_document["actor_id"]),
                mmsi=int(actor_document["mmsi"]),
                samples=samples,
                observed_source_points=int(actor_document["observed_source_points"]),
                derived_world_samples=int(actor_document["derived_world_samples"]),
                length_m=actor_document.get("length_m"),
                width_m=actor_document.get("width_m"),
                dimensions_provenance=str(actor_document["dimensions_provenance"]),
                source_observation_digest=str(actor_document["source_observation_digest"]),
                draft_m=actor_document.get("draft_m"),
                actor_digest=str(actor_document.get("actor_digest", "")),
            )
            object.__setattr__(actor, "_configured_max_gap_s", profile.max_interpolation_gap_s)
            actors.append(actor)
        return cls(
            dataset_digest=str(value["dataset_digest"]),
            selection_digest=str(value["selection_digest"]),
            profile=profile,
            time_origin_utc=datetime.fromisoformat(value["time_origin_utc"]).astimezone(UTC),
            actors=tuple(actors),
            semantic_digest=str(value.get("semantic_digest", "")),
            provider=str(value.get("provider", "unknown")),
            attribution=str(value.get("attribution", "")),
            coverage_limitations=tuple(value.get("coverage_limitations", ())),
        )

    def world_states_at(self, time_s: float) -> tuple[HistoricalActorState, ...]:
        states = []
        for actor in self.actors:
            sample = actor.sample_at(time_s)
            if sample is not None:
                states.append(HistoricalActorState(actor.actor_id, actor.mmsi, sample, actor.length_m, actor.width_m))
        return tuple(states)

    def current_observations_at(
        self,
        time_s: float,
        *,
        knowledge_cutoff_s: float | None = None,
        include_future: bool = False,
    ) -> tuple[HistoricalActorState, ...]:
        """Expose only current states and reject a caller asking for future facts."""
        if include_future:
            raise ValueError("future Historical Actor samples are not available to runtime observations")
        if knowledge_cutoff_s is not None and float(knowledge_cutoff_s) > float(time_s):
            raise ValueError("future runtime knowledge cutoff is not allowed")
        return self.world_states_at(time_s)

    def _identity_dict(self) -> dict[str, Any]:
        return {
            "dataset_digest": self.dataset_digest,
            "selection_digest": self.selection_digest,
            "profile": self.profile.to_dict(),
            "time_origin_utc": self.time_origin_utc.isoformat(),
            "actors": [actor.to_dict() for actor in self.actors],
            "provider": self.provider,
            "attribution": self.attribution,
            "coverage_limitations": list(self.coverage_limitations),
        }

    def to_dict(self) -> dict[str, Any]:
        output = self._identity_dict()
        output["semantic_digest"] = self.semantic_digest
        return output


def _require_actor_dimensions(actor: HistoricalActor) -> None:
    if not actor.dimensions_known:
        raise HistoricalReplayQualificationError(
            HistoricalReplayQualificationStatus.DIMENSIONS_UNAVAILABLE,
            f"MMSI {actor.mmsi} has no source-provenanced length/beam",
        )
    provenance = actor.dimensions_provenance.strip().lower()
    if not provenance or "unavailable" in provenance or "default" in provenance:
        raise HistoricalReplayQualificationError(
            HistoricalReplayQualificationStatus.QUALITY_INCOMPLETE,
            f"MMSI {actor.mmsi} dimension provenance is incomplete",
        )


class HistoricalActorShip(Ship):
    """A normal :class:`Ship` whose world motion is supplied by one actor.

    Sensors, tracker, session and simulator still call the regular Ship
    interfaces.  Only ``forward`` and ``plan`` are replaced so the immutable
    actor world definition controls this non-counterfactual replay vessel.
    """

    def __init__(
        self,
        actor: HistoricalActor,
        profile: HistoricalAISReconstructionProfile,
    ) -> None:
        _require_actor_dimensions(actor)
        config = ShipConfig(id=actor.actor_id, mmsi=actor.mmsi)
        super().__init__(mmsi=actor.mmsi, identifier=actor.actor_id, config=config)
        self._historical_actor = actor
        self._historical_profile = profile
        self._historical_time_s: float | None = None
        self._historical_sample: HistoricalActorWorldSample | None = None
        self._references = np.zeros((9, 1), dtype=float)
        self._historical_simulation_length_m = float(actor.length_m)
        self._historical_simulation_width_m = float(actor.width_m)
        self._model.params.length = self._historical_simulation_length_m
        self._model.params.width = self._historical_simulation_width_m
        if actor.draft_m is not None:
            self._model.params.draft = float(actor.draft_m)
        self.t_start = actor.first_time_s
        self.t_end = actor.last_time_s + profile.time_step_s
        self.prepare_at_time(actor.first_time_s)

    @property
    def historical_actor(self) -> HistoricalActor:
        return self._historical_actor

    @property
    def historical_sample(self) -> HistoricalActorWorldSample | None:
        return self._historical_sample

    @property
    def dimensions_known(self) -> bool:
        return self._historical_actor.dimensions_known

    def historical_is_active_at(self, time_s: float) -> bool:
        """Return whether actor has a valid current sample at simulation time."""
        sample = self._historical_actor.sample_at(float(time_s))
        return sample is not None

    def prepare_at_time(self, time_s: float) -> None:
        """Load one current sample before normal sensing starts for a step."""
        query = float(time_s)
        sample = self._historical_actor.sample_at(query)
        self._historical_time_s = query
        self._historical_sample = sample
        if sample is None:
            return
        x_north, y_east, velocity_north, velocity_east = sample.state_vxvy
        speed = math.hypot(velocity_north, velocity_east)
        course = (
            math.atan2(velocity_east, velocity_north)
            if speed > 1e-12
            else float(self._state[2])
            if self._state.size
            else 0.0
        )
        self._state = np.array([x_north, y_east, course, speed, 0.0, 0.0], dtype=float)

    def plan(self, t: float, dt: float, do_list: list, enc: Any = None, w: Any = None) -> np.ndarray:  # noqa: ARG002
        """Keep replay actors outside planner/control authority."""
        self._references = np.zeros((9, 1), dtype=float)
        if self._state.size >= 4:
            self._references[0, 0] = self._state[0]
            self._references[1, 0] = self._state[1]
            self._references[2, 0] = self._state[2]
            self._references[3, 0] = self._state[3]
        return self._references

    def forward(self, dt: float, w: Any = None) -> tuple[np.ndarray, np.ndarray, np.ndarray]:  # noqa: ARG002
        """Advance to the next current sample without extrapolating gaps."""
        if self._historical_time_s is None:
            raise RuntimeError("Historical Actor Ship has not been prepared")
        self.prepare_at_time(self._historical_time_s + float(dt))
        return self._state, np.empty(3), self._references[:, 0]

    def reset(self, seed: int | None) -> None:
        super().reset(seed)
        self._historical_time_s = None
        self._historical_sample = None
        self.prepare_at_time(self._historical_actor.first_time_s)

    def get_colav_data(self) -> dict[str, Any]:
        sample = self._historical_sample
        return {
            "planner": PlannerTrace(
                algorithm_id="historical_replay",
                solve_id=0,
                sim_time=float(self._historical_time_s or 0.0),
                solver_executed=False,
                predicted_trajectory=np.asarray(self._references, dtype=float),
                selected_command={
                    "course_rad": float(self._state[2]) if self._state.size else 0.0,
                    "speed_mps": float(self._state[3]) if self._state.size else 0.0,
                },
                algorithm_details={
                    "planner_kind": "historical_actor_playback",
                    "actor_id": self.id,
                    "mmsi": self.mmsi,
                    "sample_kind": sample.kind.value if sample is not None else "inactive",
                    "trajectory_digest": self._historical_actor.actor_digest,
                },
            ).to_dict()
        }

    def get_sim_data(self, t: float, timestamp_0: int) -> dict[str, Any]:
        payload = super().get_sim_data(t, timestamp_0)
        sample = self._historical_sample
        payload["historical_actor_truth"] = {
            "actor_id": self.id,
            "mmsi": self.mmsi,
            "sample_kind": sample.kind.value if sample is not None else "inactive",
            "trajectory_digest": self._historical_actor.actor_digest,
            "state_vxvy": list(sample.state_vxvy) if sample is not None else None,
        }
        payload["historical_actor_dimensions"] = {
            "length_m": self._historical_actor.length_m,
            "width_m": self._historical_actor.width_m,
            "draft_m": self._historical_actor.draft_m,
            "provenance": self._historical_actor.dimensions_provenance,
            "simulation_length_m": self._historical_simulation_length_m,
            "simulation_width_m": self._historical_simulation_width_m,
        }
        return payload


def _three_point_reference_route(
    actor: HistoricalActor,
    *,
    start_s: float,
    end_s: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Seal start, dominant turn, and final observed point from factual Ownship AIS."""
    start = actor.sample_at(float(start_s))
    observed = [
        sample
        for sample in actor.samples
        if sample.kind is HistoricalActorSampleKind.OBSERVED
        and float(start_s) < sample.time_s <= float(end_s)
    ]
    if start is None or len(observed) < 2:
        raise ValueError("Historical Reference Route requires start, turn, and final AIS points")
    end = observed[-1]
    interior = [sample for sample in observed[:-1] if sample.time_s > start.time_s]
    if not interior:
        raise ValueError("Historical Reference Route lacks an observed interior turn point")
    start_position = np.asarray(start.state_vxvy[:2], dtype=float)
    end_position = np.asarray(end.state_vxvy[:2], dtype=float)
    chord = end_position - start_position
    chord_length_sq = float(chord @ chord)
    if chord_length_sq <= 1e-9:
        raise ValueError("Historical Reference Route endpoints have no displacement")

    def chord_deviation(sample: HistoricalActorWorldSample) -> float:
        position = np.asarray(sample.state_vxvy[:2], dtype=float)
        fraction = float(np.clip(((position - start_position) @ chord) / chord_length_sq, 0.0, 1.0))
        return float(np.linalg.norm(position - (start_position + fraction * chord)))

    turn = max(interior, key=chord_deviation)
    route_samples = (start, turn, end)
    route = np.asarray([sample.state_vxvy[:2] for sample in route_samples], dtype=float).T
    speeds = np.asarray(
        [math.hypot(sample.state_vxvy[2], sample.state_vxvy[3]) for sample in route_samples],
        dtype=float,
    )
    return route, speeds


def _nearest_route_segment_error(route: np.ndarray, position: np.ndarray) -> tuple[float, float] | None:
    """Return cross-track distance and course for the nearest nonzero route leg."""
    best: tuple[float, float] | None = None
    for index in range(route.shape[1] - 1):
        start = route[:, index]
        delta = route[:, index + 1] - start
        length_sq = float(delta @ delta)
        if length_sq <= 1e-9:
            continue
        fraction = float(np.clip(((position - start) @ delta) / length_sq, 0.0, 1.0))
        distance = float(np.linalg.norm(position - (start + fraction * delta)))
        course = float(math.atan2(delta[1], delta[0]))
        if best is None or distance < best[0]:
            best = (distance, course)
    return best


class HistoricalCounterfactualActorShip(HistoricalActorShip):
    """Historical actor that hands off once, atomically, to normal Ship dynamics."""

    def __init__(
        self,
        actor: HistoricalActor,
        profile: HistoricalAISReconstructionProfile,
        *,
        t0_s: float | None,
        nominal_intent: Mapping[str, Any] | None,
        handoff_trigger: str = "FIXED_T0",
        handoff_tolerance_m: float = 1e-6,
        handoff_tolerance_mps: float = 1e-6,
        handoff_tolerance_rad: float = 1e-6,
        simulation_end_s: float | None = None,
        reference_route_start_s: float | None = None,
    ) -> None:
        super().__init__(actor, profile)
        self._handoff_trigger = str(handoff_trigger).strip().upper()
        if self._handoff_trigger not in {"FIXED_T0", "LIFECYCLE_ACTIVE"}:
            raise ValueError("handoff_trigger must be FIXED_T0 or LIFECYCLE_ACTIVE")
        self._counterfactual_t0_s = None if t0_s is None else float(t0_s)
        self._handoff_tolerance_m = float(handoff_tolerance_m)
        self._handoff_tolerance_mps = float(handoff_tolerance_mps)
        self._handoff_tolerance_rad = float(handoff_tolerance_rad)
        if self._handoff_trigger == "FIXED_T0":
            if (
                self._counterfactual_t0_s is None
                or not math.isfinite(self._counterfactual_t0_s)
                or self._counterfactual_t0_s < actor.first_time_s
            ):
                raise ValueError("counterfactual T0 must be finite and within Reference Vessel history")
            if nominal_intent is None:
                raise ValueError("counterfactual Nominal Intent is required")
            self._set_fixed_nominal_intent(nominal_intent)
        elif self._counterfactual_t0_s is not None or nominal_intent is not None:
            raise ValueError("Lifecycle-triggered handoff derives T0 and Mission Route at runtime")
        self._simulation_end_s = None if simulation_end_s is None else float(simulation_end_s)
        self._reference_route_start_s = (
            None if reference_route_start_s is None else float(reference_route_start_s)
        )
        if simulation_end_s is not None:
            lower_bound = actor.first_time_s if self._counterfactual_t0_s is None else self._counterfactual_t0_s
            if not math.isfinite(float(simulation_end_s)) or float(simulation_end_s) <= lower_bound:
                raise ValueError("simulation_end_s must be later than Historical playback/handoff")
            self.t_end = self._simulation_end_s
        self._sealed_reference_route: np.ndarray | None = None
        self._sealed_reference_speeds: np.ndarray | None = None
        if self._handoff_trigger == "LIFECYCLE_ACTIVE":
            if self._reference_route_start_s is None or self._simulation_end_s is None:
                raise ValueError("Lifecycle handoff requires sealed Historical Reference Route bounds")
            self._sealed_reference_route, self._sealed_reference_speeds = _three_point_reference_route(
                actor,
                start_s=self._reference_route_start_s,
                end_s=self._simulation_end_s,
            )
        self._counterfactual_phase = "HISTORICAL_REFERENCE"
        self._counterfactual_handoff_state: np.ndarray | None = None
        self._recovery_hold_s = 0.0
        self._recovery_complete = False

    def _set_fixed_nominal_intent(self, nominal_intent: Mapping[str, Any]) -> None:
        route_points = tuple(tuple(float(item) for item in point) for point in nominal_intent.get("route_points_vxvy", ()))
        if len(route_points) < 2:
            raise ValueError("counterfactual Nominal Intent requires at least two route points")
        first_point = np.asarray(route_points[0], dtype=float)
        last_point = np.asarray(route_points[-1], dtype=float)
        route_delta = last_point - first_point
        route_length = float(np.linalg.norm(route_delta))
        if route_length <= 1e-9:
            raise ValueError("counterfactual Nominal Intent route must have non-zero travel")
        route_points = (
            *route_points,
            tuple((last_point + route_delta / route_length * COUNTERFACTUAL_ROUTE_EXTENSION_M).tolist()),
        )
        self.set_nominal_plan(
            np.asarray(route_points, dtype=float).T,
            np.full(len(route_points), float(nominal_intent.get("speed_mps", 0.0)), dtype=float),
        )

    @property
    def counterfactual_phase(self) -> str:
        return self._counterfactual_phase

    @property
    def counterfactual_t0_s(self) -> float | None:
        return self._counterfactual_t0_s

    @property
    def handoff_state(self) -> np.ndarray | None:
        return None if self._counterfactual_handoff_state is None else self._counterfactual_handoff_state.copy()

    def historical_is_active_at(self, time_s: float) -> bool:
        """Keep the Reference Vessel active after T0 under normal Ship dynamics."""
        query = float(time_s)
        if self._counterfactual_phase == "HISTORICAL_REFERENCE":
            return super().historical_is_active_at(query)
        return True

    def prepare_at_time(self, time_s: float) -> None:
        """Stop factual playback from overwriting Counterfactual state after handoff."""
        if getattr(self, "_counterfactual_phase", "HISTORICAL_REFERENCE") == "COUNTERFACTUAL_REALIZED":
            return
        super().prepare_at_time(time_s)

    def shadow_sample_at(self, time_s: float) -> HistoricalActorWorldSample | None:
        """Return immutable factual continuation for comparison-only projection."""
        return self._historical_actor.sample_at(float(time_s))

    def request_lifecycle_handoff(self, time_s: float, lifecycle_snapshot: Any) -> bool:
        """Branch once when canonical Lifecycle first reports ACTIVE."""
        if self._handoff_trigger != "LIFECYCLE_ACTIVE" or self._counterfactual_phase != "HISTORICAL_REFERENCE":
            return False
        targets = tuple(getattr(lifecycle_snapshot, "targets", ()) or ())
        if not any(
            str(getattr(getattr(target, "risk", None), "value", getattr(target, "risk", ""))) == "ACTIVE"
            for target in targets
        ):
            return False
        handoff_time = float(time_s)
        self.prepare_at_time(handoff_time)
        if self._sealed_reference_route is None or self._sealed_reference_speeds is None:
            raise ValueError("HANDOFF_NOT_TRIGGERED: Historical Reference Route is unavailable")
        self.set_nominal_plan(self._sealed_reference_route.copy(), self._sealed_reference_speeds.copy())
        self._counterfactual_t0_s = handoff_time
        self._activate_counterfactual()
        return True

    def update_recovery_status(
        self,
        lifecycle_snapshot: Any,
        relevant_track_keys: set[tuple[int, int]],
        dt_s: float,
    ) -> dict[str, Any]:
        """Evaluate the frozen 30s/100m/5deg recovery contract."""
        if self._counterfactual_phase != "COUNTERFACTUAL_REALIZED":
            return {"status": "NOT_STARTED", "hold_s": 0.0}
        decisions = {
            (int(target.key.target_id), int(target.key.generation)): target
            for target in tuple(getattr(lifecycle_snapshot, "targets", ()) or ())
        }
        all_released = bool(relevant_track_keys) and all(
            key in decisions and str(getattr(decisions[key].risk, "value", decisions[key].risk)) == "RELEASED"
            for key in relevant_track_keys
        )
        route = np.asarray(self.waypoints, dtype=float)
        route_error = _nearest_route_segment_error(route, self._state[:2])
        if route_error is None:
            return {"status": "RECOVERY_INCOMPLETE", "hold_s": 0.0, "reason": "MISSION_ROUTE_INVALID"}
        cross_track_m, route_course = route_error
        course_error_rad = abs(float(_angle_delta(float(self._state[2]), route_course)))
        within_corridor = cross_track_m <= 100.0 and course_error_rad <= math.radians(5.0)
        self._recovery_hold_s = self._recovery_hold_s + float(dt_s) if all_released and within_corridor else 0.0
        self._recovery_complete = self._recovery_complete or self._recovery_hold_s >= 30.0
        return {
            "status": "RECOVERY_COMPLETE" if self._recovery_complete else "RECOVERY_INCOMPLETE",
            "all_relevant_targets_released": all_released,
            "cross_track_error_m": cross_track_m,
            "course_error_rad": course_error_rad,
            "hold_s": self._recovery_hold_s,
        }

    def _activate_counterfactual(self) -> None:
        if self._counterfactual_phase == "COUNTERFACTUAL_REALIZED":
            return
        if self._counterfactual_t0_s is None:
            raise ValueError("REFERENCE_STATE_MISMATCH: handoff time is unavailable")
        expected = self._historical_actor.sample_at(self._counterfactual_t0_s)
        if expected is None:
            raise ValueError("REFERENCE_STATE_MISMATCH: no reconstructed state at T0")
        expected_speed = math.hypot(expected.state_vxvy[2], expected.state_vxvy[3])
        expected_course = math.atan2(expected.state_vxvy[3], expected.state_vxvy[2])
        if (
            np.linalg.norm(self._state[:2] - np.asarray(expected.state_vxvy[:2])) > self._handoff_tolerance_m
            or abs(float(self._state[3]) - expected_speed) > self._handoff_tolerance_mps
            or abs(_angle_delta(float(self._state[2]), expected_course)) > self._handoff_tolerance_rad
        ):
            raise ValueError("REFERENCE_STATE_MISMATCH: runtime state differs from frozen historical T0 state")
        self._counterfactual_handoff_state = self._state.copy()
        self._counterfactual_phase = "COUNTERFACTUAL_REALIZED"

    def plan(self, t: float, dt: float, do_list: list, enc: Any = None, w: Any = None) -> np.ndarray:
        if self._counterfactual_phase == "HISTORICAL_REFERENCE" and (
            self._handoff_trigger == "LIFECYCLE_ACTIVE"
            or self._counterfactual_t0_s is None
            or float(t) < self._counterfactual_t0_s
        ):
            self._references = np.zeros((9, 1), dtype=float)
            if self._state.size >= 4:
                self._references[0, 0] = self._state[0]
                self._references[1, 0] = self._state[1]
                self._references[2, 0] = self._state[2]
                self._references[3, 0] = self._state[3]
            return self._references
        self._activate_counterfactual()
        return Ship.plan(self, t, dt, do_list, enc, w)

    def forward(self, dt: float, w: Any = None) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        if self._counterfactual_phase == "HISTORICAL_REFERENCE":
            if self._handoff_trigger == "LIFECYCLE_ACTIVE" or self._counterfactual_t0_s is None:
                return super().forward(dt, w)
            current_time = float(self._historical_time_s or 0.0)
            next_time = current_time + float(dt)
            if next_time <= self._counterfactual_t0_s + 1e-9:
                return super().forward(dt, w)
            super().prepare_at_time(self._counterfactual_t0_s)
            self._activate_counterfactual()
            return Ship.forward(self, max(0.0, next_time - self._counterfactual_t0_s), w)
        return Ship.forward(self, dt, w)

    def reset(self, seed: int | None) -> None:
        self._counterfactual_phase = "HISTORICAL_REFERENCE"
        self._counterfactual_handoff_state = None
        self._recovery_hold_s = 0.0
        self._recovery_complete = False
        super().reset(seed)

    def get_colav_data(self) -> dict[str, Any]:
        if self._counterfactual_phase == "HISTORICAL_REFERENCE":
            data = super().get_colav_data()
        else:
            data = Ship.get_colav_data(self)
        planner = data.setdefault("planner", {})
        details = planner.setdefault("algorithm_details", {})
        details["counterfactual_mode"] = self._counterfactual_phase
        details["mission_route_source"] = "SEALED_FULL_HISTORICAL_OWN_SHIP_AIS"
        details["counterfactual_t0_s"] = self._counterfactual_t0_s
        details["handoff_trigger"] = self._handoff_trigger
        details["human_reference_in_runtime"] = False
        return data

    def get_sim_data(self, t: float, timestamp_0: int) -> dict[str, Any]:
        if self._counterfactual_phase == "HISTORICAL_REFERENCE":
            return super().get_sim_data(t, timestamp_0)
        payload = Ship.get_sim_data(self, t, timestamp_0)
        payload["historical_counterfactual"] = {
            "mode": "COUNTERFACTUAL_REALIZED",
            "t0_s": self._counterfactual_t0_s,
            "human_reference_in_runtime": False,
        }
        return payload


class HistoricalAISReconstructor:
    """Build deterministic Historical Actors from a dataset read result."""

    def reconstruct(
        self,
        dataset: HistoricalAISReadResult,
        profile: HistoricalAISReconstructionProfile | None = None,
    ) -> HistoricalActorSet:
        profile = profile or HistoricalAISReconstructionProfile()
        observations = [
            observation
            for observation in dataset.observations
            if (
                observation.normalized.timestamp_utc is not None
                and observation.normalized.mmsi is not None
                and observation.normalized.longitude_deg is not None
                and observation.normalized.latitude_deg is not None
            )
        ]
        if not observations:
            raise ValueError("dataset has no reconstructable AIS observations")
        origin = min(
            observation.normalized.timestamp_utc for observation in observations if observation.normalized.timestamp_utc
        )
        transformer = Transformer.from_crs(profile.source_crs, profile.projection_crs, always_xy=True)
        actors: list[HistoricalActor] = []
        for actor_id, mmsi in enumerate(
            sorted({observation.normalized.mmsi for observation in observations if observation.normalized.mmsi is not None})
        ):
            actor_observations = [observation for observation in observations if observation.normalized.mmsi == mmsi]
            actor = self._reconstruct_actor(actor_id, int(mmsi), actor_observations, origin, profile, transformer)
            actors.append(actor)
        return HistoricalActorSet(
            dataset_digest=dataset.descriptor.descriptor_sha256,
            selection_digest=dataset.descriptor.selection_sha256,
            profile=profile,
            time_origin_utc=origin,
            actors=tuple(actors),
            provider=dataset.descriptor.provider,
            attribution=dataset.descriptor.attribution.attribution,
            coverage_limitations=dataset.descriptor.coverage_limitations,
        )

    def _reconstruct_actor(
        self,
        actor_id: int,
        mmsi: int,
        observations: Sequence[HistoricalAISObservation],
        origin: datetime,
        profile: HistoricalAISReconstructionProfile,
        transformer: Transformer,
    ) -> HistoricalActor:
        ordered = sorted(
            observations,
            key=lambda observation: (
                observation.normalized.timestamp_utc,
                observation.raw.row_sha256,
                observation.raw.entry_name,
                observation.raw.source_row_index,
            ),
        )
        # A conflicting duplicate is retained in source provenance, while one
        # canonical row supplies the physical point for the world timeline.
        points: list[HistoricalActorWorldSample] = []
        for observation in ordered:
            normalized = observation.normalized
            timestamp = normalized.timestamp_utc
            if timestamp is None:
                continue
            time_s = (timestamp - origin).total_seconds()
            east, north = transformer.transform(normalized.longitude_deg, normalized.latitude_deg)
            velocity = _velocity_from_normalized(normalized)
            points.append(
                HistoricalActorWorldSample(
                    time_s=time_s,
                    timestamp_utc=timestamp,
                    state_vxvy=(north, east, velocity[0], velocity[1]),
                    kind=HistoricalActorSampleKind.OBSERVED,
                    source_observation_refs=(HistoricalAISSourceObservationRef.from_observation(observation),),
                )
            )
        canonical = _canonical_points(points)
        samples = _with_interpolated_samples(canonical, profile)
        first_with_length = next(
            (
                observation.normalized
                for observation in ordered
                if observation.normalized.length_m and observation.normalized.width_m
            ),
            None,
        )
        length_m = first_with_length.length_m if first_with_length is not None else None
        width_m = first_with_length.width_m if first_with_length is not None else None
        source_digest = _sha256_json([point.to_dict() for point in canonical])
        actor = HistoricalActor(
            actor_id=actor_id,
            mmsi=mmsi,
            samples=tuple(samples),
            observed_source_points=len(canonical),
            derived_world_samples=sum(sample.kind is HistoricalActorSampleKind.INTERPOLATED for sample in samples),
            length_m=length_m,
            width_m=width_m,
            dimensions_provenance="source_observed"
            if length_m is not None and width_m is not None
            else "source_unavailable",
            source_observation_digest=source_digest,
        )
        object.__setattr__(actor, "_configured_max_gap_s", profile.max_interpolation_gap_s)
        object.__setattr__(actor, "actor_digest", _sha256_json(actor._identity_dict()))
        return actor


def _canonical_points(points: Sequence[HistoricalActorWorldSample]) -> list[HistoricalActorWorldSample]:
    output: list[HistoricalActorWorldSample] = []
    for point in sorted(
        points,
        key=lambda item: (
            item.time_s,
            tuple(
                (ref.entry_name, ref.source_row_index, ref.row_sha256, ref.duplicate_version)
                for ref in item.source_observation_refs
            ),
        ),
    ):
        if output and math.isclose(output[-1].time_s, point.time_s, rel_tol=0.0, abs_tol=1e-9):
            refs = (*output[-1].source_observation_refs, *point.source_observation_refs)
            output[-1] = HistoricalActorWorldSample(
                time_s=output[-1].time_s,
                timestamp_utc=output[-1].timestamp_utc,
                state_vxvy=output[-1].state_vxvy,
                kind=output[-1].kind,
                source_observation_refs=tuple(
                    sorted(refs, key=lambda ref: (ref.row_sha256, ref.entry_name, ref.source_row_index))
                ),
            )
            continue
        output.append(point)
    return output


def _with_interpolated_samples(
    points: Sequence[HistoricalActorWorldSample], profile: HistoricalAISReconstructionProfile
) -> list[HistoricalActorWorldSample]:
    output: list[HistoricalActorWorldSample] = []
    for index, point in enumerate(points):
        output.append(point)
        if index == len(points) - 1:
            continue
        next_point = points[index + 1]
        delta = next_point.time_s - point.time_s
        if delta <= profile.time_step_s or delta > profile.max_interpolation_gap_s:
            continue
        cursor = point.time_s + profile.time_step_s
        while cursor < next_point.time_s - 1e-9:
            fraction = (cursor - point.time_s) / delta
            state = tuple(
                point.state_vxvy[component] + fraction * (next_point.state_vxvy[component] - point.state_vxvy[component])
                for component in range(4)
            )
            output.append(
                HistoricalActorWorldSample(
                    time_s=cursor,
                    timestamp_utc=point.timestamp_utc + timedelta(seconds=cursor - point.time_s),
                    state_vxvy=state,
                    kind=HistoricalActorSampleKind.INTERPOLATED,
                    source_observation_refs=(*point.source_observation_refs, *next_point.source_observation_refs),
                )
            )
            cursor += profile.time_step_s
    return output


def _velocity_from_normalized(normalized: HistoricalAISNormalizedFact) -> tuple[float, float]:
    if normalized.sog_mps is None or normalized.cog_rad is None:
        return 0.0, 0.0
    return (
        normalized.sog_mps * math.cos(normalized.cog_rad),
        normalized.sog_mps * math.sin(normalized.cog_rad),
    )


# Compatibility aliases use the same vocabulary as the parent issue and keep
# the public seam discoverable without introducing another implementation.
HistoricalAISActorReconstructor = HistoricalAISReconstructor
HistoricalActorReconstructionProfile = HistoricalAISReconstructionProfile


class ENCPreflightEvidenceErrorCode(str, Enum):
    """Machine-readable failure boundary for Replay ENC evidence."""

    ENC_UNQUALIFIED = "ENC_UNQUALIFIED"
    PREFLIGHT_FAILED = "PREFLIGHT_FAILED"
    OUTSIDE_COVERAGE = "OUTSIDE_COVERAGE"
    QUALITY_INCOMPLETE = "QUALITY_INCOMPLETE"


class ENCPreflightEvidenceError(ValueError):
    """Typed validation error consumed directly by API classification."""

    def __init__(self, code: ENCPreflightEvidenceErrorCode | str, message: str) -> None:
        super().__init__(message)
        self.code = ENCPreflightEvidenceErrorCode(code)


@dataclass(frozen=True)
class ENCPreflightEvidence:
    """Authenticated qualified-ENC/preflight contract for Historical runtime."""

    profile_id: str
    qualification_state: str
    supported_extent_projected: tuple[float, float, float, float]
    profile_digest: str
    cache_digest: str
    source_digest: str
    preflight_status: str
    all_positions_contained: bool
    evidence_digest: str = ""

    def __post_init__(self) -> None:
        """Validate qualification, coverage extent and semantic identity."""
        try:
            extent = tuple(float(value) for value in self.supported_extent_projected)
        except (TypeError, ValueError) as exc:
            raise ENCPreflightEvidenceError(
                ENCPreflightEvidenceErrorCode.QUALITY_INCOMPLETE,
                "qualified ENC projected extent must contain four finite values",
            ) from exc
        if len(extent) != 4 or not all(math.isfinite(value) for value in extent):
            raise ENCPreflightEvidenceError(
                ENCPreflightEvidenceErrorCode.QUALITY_INCOMPLETE,
                "qualified ENC projected extent must contain four finite values",
            )
        min_x, min_y, max_x, max_y = extent
        if min_x > max_x or min_y > max_y:
            raise ENCPreflightEvidenceError(
                ENCPreflightEvidenceErrorCode.QUALITY_INCOMPLETE,
                "qualified ENC projected extent must be ordered",
            )
        identities = (self.profile_id, self.profile_digest, self.cache_digest, self.source_digest)
        if not all(str(value).strip() for value in identities):
            raise ENCPreflightEvidenceError(
                ENCPreflightEvidenceErrorCode.QUALITY_INCOMPLETE,
                "qualified ENC profile/cache/source identity is required",
            )
        if self.qualification_state != "QUALIFIED":
            raise ENCPreflightEvidenceError(
                ENCPreflightEvidenceErrorCode.ENC_UNQUALIFIED,
                "ENC qualification state must be QUALIFIED",
            )
        if self.all_positions_contained is not True or self.preflight_status == "OUTSIDE_COVERAGE":
            raise ENCPreflightEvidenceError(
                ENCPreflightEvidenceErrorCode.OUTSIDE_COVERAGE,
                "ENC preflight does not contain all Replay positions",
            )
        if self.preflight_status != "PASS":
            raise ENCPreflightEvidenceError(
                ENCPreflightEvidenceErrorCode.PREFLIGHT_FAILED,
                f"ENC preflight status is {self.preflight_status}",
            )
        object.__setattr__(self, "supported_extent_projected", extent)
        digest = _sha256_json(self._identity_dict())
        if self.evidence_digest and self.evidence_digest != digest:
            raise ENCPreflightEvidenceError(
                ENCPreflightEvidenceErrorCode.QUALITY_INCOMPLETE,
                "ENC preflight evidence digest mismatch",
            )
        object.__setattr__(self, "evidence_digest", digest)

    def _identity_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "qualification_state": self.qualification_state,
            "supported_extent_projected": list(self.supported_extent_projected),
            "profile_digest": self.profile_digest,
            "cache_digest": self.cache_digest,
            "source_digest": self.source_digest,
            "preflight_status": self.preflight_status,
            "all_positions_contained": self.all_positions_contained,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._identity_dict(), "evidence_digest": self.evidence_digest}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> ENCPreflightEvidence:
        try:
            return cls(
                profile_id=str(value.get("profile_id", "")),
                qualification_state=str(value.get("qualification_state", "")),
                supported_extent_projected=tuple(value.get("supported_extent_projected", ())),
                profile_digest=str(value.get("profile_digest", "")),
                cache_digest=str(value.get("cache_digest", "")),
                source_digest=str(value.get("source_digest", "")),
                preflight_status=str(value.get("preflight_status", "")),
                all_positions_contained=value.get("all_positions_contained") is True,
                evidence_digest=str(value.get("evidence_digest", "")),
            )
        except ENCPreflightEvidenceError:
            raise
        except (TypeError, ValueError) as exc:
            raise ENCPreflightEvidenceError(
                ENCPreflightEvidenceErrorCode.QUALITY_INCOMPLETE,
                "ENC preflight evidence has an invalid field shape",
            ) from exc


@dataclass(frozen=True)
class HistoricalReplayEvidence:
    """Lineage bound to a normal Historical Replay session."""

    dataset_digest: str
    selection_digest: str
    reconstruction_profile_digest: str
    time_origin_utc: datetime
    actor_digests: tuple[tuple[int, str], ...]
    source_snapshot_digest: str
    provider: str = "unknown"
    attribution: str = ""
    coverage_limitations: tuple[str, ...] = ()
    mode: str = "HISTORICAL_REPLAY"
    counterfactual: bool = False
    case_digest: str | None = None
    t0_s: float | None = None
    nominal_intent_digest: str | None = None
    enc_preflight_evidence: ENCPreflightEvidence | None = None
    dimension_registry_digest: str | None = None
    dimension_effective_at_utc: str | None = None
    dimension_record_digests: tuple[tuple[int, str], ...] = ()
    handoff_trigger: str = "FIXED_T0"

    def __post_init__(self) -> None:
        """Validate the typed historical execution mode and lineage."""
        if self.mode not in {"HISTORICAL_REPLAY", "COUNTERFACTUAL"}:
            raise ValueError("Historical evidence mode must be HISTORICAL_REPLAY or COUNTERFACTUAL")
        if self.counterfactual != (self.mode == "COUNTERFACTUAL"):
            raise ValueError("Historical evidence mode/counterfactual flag mismatch")
        object.__setattr__(self, "handoff_trigger", str(self.handoff_trigger).strip().upper())
        if self.handoff_trigger not in {"FIXED_T0", "LIFECYCLE_ACTIVE"}:
            raise ValueError("unsupported Historical handoff trigger")
        if self.counterfactual and self.case_digest is None:
            raise ValueError("Counterfactual evidence requires Case identity")
        if self.counterfactual and self.handoff_trigger == "FIXED_T0" and (
            self.t0_s is None or self.nominal_intent_digest is None
        ):
            raise ValueError("Fixed-T0 Counterfactual evidence requires T0 and Nominal Intent identity")
        if self.handoff_trigger == "LIFECYCLE_ACTIVE" and (
            self.t0_s is not None or self.nominal_intent_digest is not None
        ):
            raise ValueError("Lifecycle Counterfactual evidence cannot seal fixed T0 or future intent")
        object.__setattr__(self, "actor_digests", tuple(sorted(self.actor_digests)))
        object.__setattr__(self, "coverage_limitations", tuple(self.coverage_limitations))
        object.__setattr__(self, "dimension_record_digests", tuple(sorted(self.dimension_record_digests)))
        if self.time_origin_utc.tzinfo is None:
            raise ValueError("time_origin_utc must be timezone-aware")
        object.__setattr__(self, "time_origin_utc", self.time_origin_utc.astimezone(UTC))

    @property
    def digest(self) -> str:
        return _sha256_json(self.to_dict())

    @property
    def dataset_descriptor_digest(self) -> str:
        return self.dataset_digest

    @property
    def runtime_actor_set_digest(self) -> str:
        return self.source_snapshot_digest

    @property
    def case_runtime_digest(self) -> str | None:
        return self.case_digest

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "counterfactual": self.counterfactual,
            "case_digest": self.case_digest,
            "case_runtime_digest": self.case_runtime_digest,
            "t0_s": self.t0_s,
            "nominal_intent_digest": self.nominal_intent_digest,
            "handoff_trigger": self.handoff_trigger,
            "enc_preflight_evidence": (
                None if self.enc_preflight_evidence is None else self.enc_preflight_evidence.to_dict()
            ),
            "dataset_digest": self.dataset_digest,
            "dataset_descriptor_digest": self.dataset_descriptor_digest,
            "runtime_actor_set_digest": self.runtime_actor_set_digest,
            "selection_digest": self.selection_digest,
            "reconstruction_profile_digest": self.reconstruction_profile_digest,
            "time_origin_utc": self.time_origin_utc.isoformat(),
            "actor_digests": [[actor_id, digest] for actor_id, digest in self.actor_digests],
            "source_snapshot_digest": self.source_snapshot_digest,
            "provider": self.provider,
            "attribution": self.attribution,
            "coverage_limitations": list(self.coverage_limitations),
            "dimension_registry_digest": self.dimension_registry_digest,
            "dimension_effective_at_utc": self.dimension_effective_at_utc,
            "dimension_record_digests": [list(item) for item in self.dimension_record_digests],
        }


@dataclass(frozen=True)
class HistoricalReplayRequest:
    """Inputs for creating a normal simulator/session Historical Replay."""

    actor_set: HistoricalActorSet
    ownship_actor_id: int = 0
    dt_sim: float | None = None
    t_start_s: float = 0.0
    t_end_s: float | None = None
    scenario_name: str = "historical_replay"
    utm_zone: int = 33
    mode: str = "HISTORICAL_REPLAY"
    handoff_trigger: str = "FIXED_T0"
    counterfactual_t0_s: float | None = None
    nominal_intent: Mapping[str, Any] | None = None
    case_digest: str | None = None
    dataset_digest: str | None = None
    dataset_descriptor_digest: str | None = None
    runtime_actor_set_digest: str | None = None
    case_runtime_digest: str | None = None
    selection_digest: str | None = None
    reconstruction_profile_digest: str | None = None
    enc_preflight_evidence: ENCPreflightEvidence | Mapping[str, Any] | None = None
    handoff_tolerance_m: float = 1e-6
    handoff_tolerance_mps: float = 1e-6
    handoff_tolerance_rad: float = 1e-6
    dimension_registry_digest: str | None = None
    dimension_effective_at_utc: str | None = None
    dimension_record_digests: tuple[tuple[int, str], ...] = ()

    def __post_init__(self) -> None:  # noqa: C901, PLR0912
        """Validate actor ownership and simulation bounds."""
        if not self.scenario_name.strip():
            raise ValueError("scenario_name is required")
        object.__setattr__(self, "mode", str(self.mode).upper())
        object.__setattr__(self, "handoff_trigger", str(self.handoff_trigger).strip().upper())
        if self.mode not in {"HISTORICAL_REPLAY", "COUNTERFACTUAL"}:
            raise ValueError("mode must be HISTORICAL_REPLAY or COUNTERFACTUAL")
        if self.handoff_trigger not in {"FIXED_T0", "LIFECYCLE_ACTIVE"}:
            raise ValueError("handoff_trigger must be FIXED_T0 or LIFECYCLE_ACTIVE")
        if self.mode == "COUNTERFACTUAL":
            if self.case_digest is None:
                raise ValueError("Counterfactual request requires Case identity")
            if self.handoff_trigger == "FIXED_T0":
                if self.counterfactual_t0_s is None or self.nominal_intent is None:
                    raise ValueError("Fixed-T0 Counterfactual requires T0 and Nominal Intent")
                t0_s = float(self.counterfactual_t0_s)
                if not math.isfinite(t0_s) or t0_s < 0.0:
                    raise ValueError("counterfactual_t0_s must be finite and non-negative")
                object.__setattr__(self, "counterfactual_t0_s", t0_s)
            elif self.counterfactual_t0_s is not None or self.nominal_intent is not None:
                raise ValueError("Lifecycle Counterfactual derives T0 and Mission Route at runtime")
            for name in ("handoff_tolerance_m", "handoff_tolerance_mps", "handoff_tolerance_rad"):
                tolerance = float(getattr(self, name))
                if not math.isfinite(tolerance) or tolerance < 0.0:
                    raise ValueError(f"{name} must be finite and non-negative")
                object.__setattr__(self, name, tolerance)
            if self.case_runtime_digest not in {None, self.case_digest}:
                raise ValueError("case runtime digest lineage mismatch")
            if self.dataset_descriptor_digest not in {None, self.dataset_digest, self.actor_set.dataset_digest}:
                raise ValueError("dataset descriptor digest lineage mismatch")
            if self.runtime_actor_set_digest not in {None, self.actor_set.semantic_digest}:
                raise ValueError("runtime actor-set digest lineage mismatch")
        self.actor_set.actor(self.ownship_actor_id)
        if not math.isfinite(self.t_start_s) or self.t_start_s < 0:
            raise ValueError("t_start_s must be finite and non-negative")
        object.__setattr__(self, "t_start_s", float(self.t_start_s))
        if self.dt_sim is not None and (not math.isfinite(self.dt_sim) or self.dt_sim <= 0):
            raise ValueError("dt_sim must be finite and positive")
        if self.t_end_s is not None and (not math.isfinite(self.t_end_s) or self.t_end_s <= 0):
            raise ValueError("t_end_s must be finite and positive")
        if self.t_end_s is not None and self.t_end_s <= self.t_start_s:
            raise ValueError("t_end_s must be later than t_start_s")
        if self.utm_zone not in {32, 33}:
            raise ValueError("utm_zone must be 32 or 33")
        if self.enc_preflight_evidence is not None and not isinstance(self.enc_preflight_evidence, ENCPreflightEvidence):
            object.__setattr__(self, "enc_preflight_evidence", ENCPreflightEvidence.from_dict(self.enc_preflight_evidence))
        if self.mode == "HISTORICAL_REPLAY" and self.enc_preflight_evidence is None:
            raise ValueError("Historical Replay requires qualified ENC preflight evidence")
        if self.enc_preflight_evidence is not None:
            _validate_actor_positions_in_enc(self.actor_set, self.enc_preflight_evidence)
        object.__setattr__(self, "dimension_record_digests", tuple(sorted(self.dimension_record_digests)))

    @property
    def evidence(self) -> HistoricalReplayEvidence:
        return HistoricalReplayEvidence(
            dataset_digest=self.dataset_descriptor_digest or self.dataset_digest or self.actor_set.dataset_digest,
            selection_digest=self.actor_set.selection_digest,
            reconstruction_profile_digest=self.actor_set.profile.digest,
            time_origin_utc=self.actor_set.time_origin_utc,
            actor_digests=tuple((actor.actor_id, actor.actor_digest) for actor in self.actor_set.actors),
            source_snapshot_digest=self.runtime_actor_set_digest or self.actor_set.semantic_digest,
            provider=self.actor_set.provider,
            attribution=self.actor_set.attribution,
            coverage_limitations=self.actor_set.coverage_limitations,
            mode=self.mode,
            counterfactual=self.mode == "COUNTERFACTUAL",
            case_digest=self.case_runtime_digest or self.case_digest,
            t0_s=self.counterfactual_t0_s,
            nominal_intent_digest=(
                str(self.nominal_intent.get("intent_digest"))
                if self.nominal_intent is not None and self.nominal_intent.get("intent_digest") is not None
                else None
            ),
            enc_preflight_evidence=self.enc_preflight_evidence,
            dimension_registry_digest=self.dimension_registry_digest,
            dimension_effective_at_utc=self.dimension_effective_at_utc,
            dimension_record_digests=self.dimension_record_digests,
            handoff_trigger=self.handoff_trigger,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "actor_set": self.actor_set.to_dict(),
            "ownship_actor_id": self.ownship_actor_id,
            "dt_sim": self.dt_sim,
            "t_start_s": self.t_start_s,
            "t_end_s": self.t_end_s,
            "scenario_name": self.scenario_name,
            "utm_zone": self.utm_zone,
            "mode": self.mode,
            "handoff_trigger": self.handoff_trigger,
            "counterfactual_t0_s": self.counterfactual_t0_s,
            "nominal_intent": dict(self.nominal_intent) if self.nominal_intent is not None else None,
            "case_digest": self.case_digest,
            "dataset_digest": self.dataset_digest,
            "dataset_descriptor_digest": self.dataset_descriptor_digest,
            "runtime_actor_set_digest": self.runtime_actor_set_digest,
            "case_runtime_digest": self.case_runtime_digest,
            "selection_digest": self.selection_digest,
            "reconstruction_profile_digest": self.reconstruction_profile_digest,
            "enc_preflight_evidence": (
                None if self.enc_preflight_evidence is None else self.enc_preflight_evidence.to_dict()
            ),
            "handoff_tolerance_m": self.handoff_tolerance_m,
            "handoff_tolerance_mps": self.handoff_tolerance_mps,
            "handoff_tolerance_rad": self.handoff_tolerance_rad,
            "dimension_registry_digest": self.dimension_registry_digest,
            "dimension_effective_at_utc": self.dimension_effective_at_utc,
            "dimension_record_digests": [list(item) for item in self.dimension_record_digests],
            "evidence": self.evidence.to_dict(),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> HistoricalReplayRequest:
        return cls(
            actor_set=HistoricalActorSet.from_dict(value["actor_set"]),
            ownship_actor_id=int(value.get("ownship_actor_id", 0)),
            dt_sim=value.get("dt_sim"),
            t_start_s=float(value.get("t_start_s", 0.0)),
            t_end_s=value.get("t_end_s"),
            scenario_name=str(value.get("scenario_name", "historical_replay")),
            utm_zone=int(value.get("utm_zone", 33)),
            mode=str(value.get("mode", "HISTORICAL_REPLAY")),
            handoff_trigger=str(value.get("handoff_trigger", "FIXED_T0")),
            counterfactual_t0_s=value.get("counterfactual_t0_s"),
            nominal_intent=value.get("nominal_intent"),
            case_digest=value.get("case_digest"),
            dataset_digest=value.get("dataset_digest"),
            dataset_descriptor_digest=value.get("dataset_descriptor_digest"),
            runtime_actor_set_digest=value.get("runtime_actor_set_digest"),
            case_runtime_digest=value.get("case_runtime_digest"),
            selection_digest=value.get("selection_digest"),
            reconstruction_profile_digest=value.get("reconstruction_profile_digest"),
            enc_preflight_evidence=value.get("enc_preflight_evidence"),
            handoff_tolerance_m=float(value.get("handoff_tolerance_m", 1e-6)),
            handoff_tolerance_mps=float(value.get("handoff_tolerance_mps", 1e-6)),
            handoff_tolerance_rad=float(value.get("handoff_tolerance_rad", 1e-6)),
            dimension_registry_digest=value.get("dimension_registry_digest"),
            dimension_effective_at_utc=value.get("dimension_effective_at_utc"),
            dimension_record_digests=tuple(
                (int(item[0]), str(item[1])) for item in value.get("dimension_record_digests", ())
            ),
        )


def _validate_actor_positions_in_enc(
    actor_set: HistoricalActorSet,
    evidence: ENCPreflightEvidence,
) -> None:
    min_east, min_north, max_east, max_north = evidence.supported_extent_projected
    outside = [
        (actor.mmsi, sample.time_s)
        for actor in actor_set.actors
        for sample in actor.samples
        if not (
            min_east <= sample.state_vxvy[1] <= max_east
            and min_north <= sample.state_vxvy[0] <= max_north
        )
    ]
    if outside:
        raise ENCPreflightEvidenceError(
            ENCPreflightEvidenceErrorCode.OUTSIDE_COVERAGE,
            "Historical Replay actor positions are outside qualified ENC coverage",
        )


@dataclass(frozen=True)
class HistoricalReplayPreparation:
    """Prepared standard session and its immutable replay evidence."""

    session: SimulationSession
    evidence: HistoricalReplayEvidence
    ships: tuple[HistoricalActorShip, ...]


class HistoricalReplayFactory:
    """Create a :class:`SimulationSession` over regular Simulator machinery."""

    @staticmethod
    def prepare(
        request: HistoricalReplayRequest,
        *,
        enc: Any,
        simulator: Any,
        sensor_seed: int = 0,
        trackers: list | None = None,
        colav_systems: list | None = None,
        terminate_on_collision_or_grounding: bool = False,
    ) -> HistoricalReplayPreparation:
        """Prepare a normal session; no actor-specific simulation loop exists."""
        from colav_simulator.experiment.session import SimulationSession  # noqa: PLC0415

        for actor in request.actor_set.actors:
            _require_actor_dimensions(actor)
        explicit_mmsi = tuple(
            actor.mmsi for actor in request.actor_set.actors if actor.dimensions_provenance.startswith("explicit:")
        )
        if explicit_mmsi and (
            not request.dimension_registry_digest
            or not request.dimension_effective_at_utc
            or {mmsi for mmsi, _digest in request.dimension_record_digests} != set(explicit_mmsi)
        ):
            raise HistoricalReplayQualificationError(
                HistoricalReplayQualificationStatus.QUALITY_INCOMPLETE,
                "explicit Replay dimensions lack complete registry/effective/source-digest lineage",
            )
        dt_sim = float(request.dt_sim or request.actor_set.profile.time_step_s)
        max_time = max(actor.last_time_s for actor in request.actor_set.actors) + dt_sim
        t_end = float(request.t_end_s if request.t_end_s is not None else max_time)
        config = scenario_config.ScenarioConfig(
            name=request.scenario_name,
            save_scenario=False,
            t_start=request.t_start_s,
            t_end=t_end,
            dt_sim=dt_sim,
            type=scenario_config.ScenarioType.MS,
            utm_zone=request.utm_zone,
            map_data_files=[],
            new_load_of_map_data=False,
            map_size=None,
            map_origin_enu=None,
            map_tolerance=0,
            map_buffer=0,
            ais_data_file=None,
            ship_data_file=None,
            allowed_nav_statuses=None,
            n_random_ships=None,
            n_random_ships_range=None,
            ship_list=[],
        )
        ships = tuple(HistoricalActorShip(actor, request.actor_set.profile) for actor in request.actor_set.actors)
        if ships[0].id != request.ownship_actor_id:
            raise ValueError("ownship_actor_id must be the first actor ID for normal Simulator ownership")
        session = SimulationSession(
            simulator=simulator,
            ship_list=list(ships),
            config=config,
            enc=enc,
            colav_systems=colav_systems,
            trackers=trackers,
            seed=sensor_seed,
            terminate_on_collision_or_grounding=terminate_on_collision_or_grounding,
        )
        return HistoricalReplayPreparation(session=session, evidence=request.evidence, ships=ships)


# The longer class name reads naturally at call sites while preserving one
# implementation and one replay authority.
HistoricalAISReplayFactory = HistoricalReplayFactory


__all__ = [
    "ENCPreflightEvidence",
    "ENCPreflightEvidenceError",
    "ENCPreflightEvidenceErrorCode",
    "HistoricalAISActorReconstructor",
    "HistoricalAISReconstructionProfile",
    "HistoricalAISReconstructor",
    "HistoricalActor",
    "HistoricalActorReconstructionProfile",
    "HistoricalActorSampleKind",
    "HistoricalActorSet",
    "HistoricalActorState",
    "HistoricalActorWorldSample",
    "HistoricalAISSourceObservationRef",
    "HistoricalReplayEvidence",
    "HistoricalReplayFactory",
    "HistoricalAISReplayFactory",
    "HistoricalReplayPreparation",
    "HistoricalReplayQualificationError",
    "HistoricalReplayQualificationStatus",
    "HistoricalReplayRequest",
    "HistoricalActorShip",
    "HistoricalCounterfactualActorShip",
]
