"""Historical AIS reconstruction and replay contracts.

The reconstruction layer turns the immutable raw/normalized observations from
``historical_ais`` into a world definition.  It deliberately does not expose
the complete trajectory through the planner interface: runtime integration
asks the actor for the state at the current simulation time only.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
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

if TYPE_CHECKING:
    from colav_simulator.experiment.session import SimulationSession

RECONSTRUCTION_SCHEMA_VERSION = "historical-actor-reconstruction.v1"


class HistoricalActorSampleKind(StrEnum):
    """Provenance of one world-truth sample."""

    OBSERVED = "observed"
    INTERPOLATED = "interpolated"


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
        *,
        simulation_length_m: float = 20.0,
        simulation_width_m: float = 5.0,
    ) -> None:
        config = ShipConfig(id=actor.actor_id, mmsi=actor.mmsi)
        super().__init__(mmsi=actor.mmsi, identifier=actor.actor_id, config=config)
        self._historical_actor = actor
        self._historical_profile = profile
        self._historical_time_s: float | None = None
        self._historical_sample: HistoricalActorWorldSample | None = None
        self._references = np.zeros((9, 1), dtype=float)
        self._historical_simulation_length_m = float(actor.length_m or simulation_length_m)
        self._historical_simulation_width_m = float(actor.width_m or simulation_width_m)
        if self._historical_simulation_length_m <= 0 or self._historical_simulation_width_m <= 0:
            raise ValueError("simulation dimensions must be positive")
        self._model.params.length = self._historical_simulation_length_m
        self._model.params.width = self._historical_simulation_width_m
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
            "provenance": self._historical_actor.dimensions_provenance,
            "simulation_length_m": self._historical_simulation_length_m,
            "simulation_width_m": self._historical_simulation_width_m,
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
    for point in sorted(points, key=lambda item: (item.time_s, item.source_observation_refs)):
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


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=_json_default).encode()
    ).hexdigest()


def _json_default(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, Mapping):
        return dict(value)
    raise TypeError(type(value).__name__)


# Compatibility aliases use the same vocabulary as the parent issue and keep
# the public seam discoverable without introducing another implementation.
HistoricalAISActorReconstructor = HistoricalAISReconstructor
HistoricalActorReconstructionProfile = HistoricalAISReconstructionProfile


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

    def __post_init__(self) -> None:
        """Validate that evidence describes replay rather than counterfactual control."""
        if self.mode != "HISTORICAL_REPLAY":
            raise ValueError("Historical Replay evidence mode is HISTORICAL_REPLAY")
        if self.counterfactual:
            raise ValueError("Historical Replay cannot be a counterfactual run")
        object.__setattr__(self, "actor_digests", tuple(sorted(self.actor_digests)))
        object.__setattr__(self, "coverage_limitations", tuple(self.coverage_limitations))
        if self.time_origin_utc.tzinfo is None:
            raise ValueError("time_origin_utc must be timezone-aware")
        object.__setattr__(self, "time_origin_utc", self.time_origin_utc.astimezone(UTC))

    @property
    def digest(self) -> str:
        return _sha256_json(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "counterfactual": self.counterfactual,
            "dataset_digest": self.dataset_digest,
            "selection_digest": self.selection_digest,
            "reconstruction_profile_digest": self.reconstruction_profile_digest,
            "time_origin_utc": self.time_origin_utc.isoformat(),
            "actor_digests": [[actor_id, digest] for actor_id, digest in self.actor_digests],
            "source_snapshot_digest": self.source_snapshot_digest,
            "provider": self.provider,
            "attribution": self.attribution,
            "coverage_limitations": list(self.coverage_limitations),
        }


@dataclass(frozen=True)
class HistoricalReplayRequest:
    """Inputs for creating a normal simulator/session Historical Replay."""

    actor_set: HistoricalActorSet
    ownship_actor_id: int = 0
    dt_sim: float | None = None
    t_end_s: float | None = None
    scenario_name: str = "historical_replay"
    utm_zone: int = 33
    simulation_length_m: float = 20.0
    simulation_width_m: float = 5.0

    def __post_init__(self) -> None:
        """Validate actor ownership and simulation bounds."""
        if not self.scenario_name.strip():
            raise ValueError("scenario_name is required")
        self.actor_set.actor(self.ownship_actor_id)
        if self.dt_sim is not None and (not math.isfinite(self.dt_sim) or self.dt_sim <= 0):
            raise ValueError("dt_sim must be finite and positive")
        if self.t_end_s is not None and (not math.isfinite(self.t_end_s) or self.t_end_s <= 0):
            raise ValueError("t_end_s must be finite and positive")
        if self.utm_zone not in {32, 33}:
            raise ValueError("utm_zone must be 32 or 33")

    @property
    def evidence(self) -> HistoricalReplayEvidence:
        return HistoricalReplayEvidence(
            dataset_digest=self.actor_set.dataset_digest,
            selection_digest=self.actor_set.selection_digest,
            reconstruction_profile_digest=self.actor_set.profile.digest,
            time_origin_utc=self.actor_set.time_origin_utc,
            actor_digests=tuple((actor.actor_id, actor.actor_digest) for actor in self.actor_set.actors),
            source_snapshot_digest=self.actor_set.semantic_digest,
            provider=self.actor_set.provider,
            attribution=self.actor_set.attribution,
            coverage_limitations=self.actor_set.coverage_limitations,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "actor_set": self.actor_set.to_dict(),
            "ownship_actor_id": self.ownship_actor_id,
            "dt_sim": self.dt_sim,
            "t_end_s": self.t_end_s,
            "scenario_name": self.scenario_name,
            "utm_zone": self.utm_zone,
            "simulation_length_m": self.simulation_length_m,
            "simulation_width_m": self.simulation_width_m,
            "evidence": self.evidence.to_dict(),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> HistoricalReplayRequest:
        return cls(
            actor_set=HistoricalActorSet.from_dict(value["actor_set"]),
            ownship_actor_id=int(value.get("ownship_actor_id", 0)),
            dt_sim=value.get("dt_sim"),
            t_end_s=value.get("t_end_s"),
            scenario_name=str(value.get("scenario_name", "historical_replay")),
            utm_zone=int(value.get("utm_zone", 33)),
            simulation_length_m=float(value.get("simulation_length_m", 20.0)),
            simulation_width_m=float(value.get("simulation_width_m", 5.0)),
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

        dt_sim = float(request.dt_sim or request.actor_set.profile.time_step_s)
        max_time = max(actor.last_time_s for actor in request.actor_set.actors) + dt_sim
        t_end = float(request.t_end_s if request.t_end_s is not None else max_time)
        config = scenario_config.ScenarioConfig(
            name=request.scenario_name,
            save_scenario=False,
            t_start=0.0,
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
        ships = tuple(
            HistoricalActorShip(
                actor,
                request.actor_set.profile,
                simulation_length_m=request.simulation_length_m,
                simulation_width_m=request.simulation_width_m,
            )
            for actor in request.actor_set.actors
        )
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
    "HistoricalReplayRequest",
    "HistoricalActorShip",
]
