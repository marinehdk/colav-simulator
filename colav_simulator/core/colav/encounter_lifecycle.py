"""Planner-owned encounter lifecycle and planner-neutral pair geometry."""

from __future__ import annotations

import hashlib
import json
import math
from collections import deque
from collections.abc import Callable
from copy import deepcopy
from dataclasses import asdict, dataclass
from enum import StrEnum

import numpy as np

from colav_simulator.core.tracking.trackers import TrackKey


class ObservationHealth(StrEnum):
    UPDATED = "UPDATED"
    DEGRADED = "DEGRADED"
    COASTING = "COASTING"
    UNUSABLE = "UNUSABLE"


class LifecycleFailure(StrEnum):
    CYCLE_CONFLICT = "CYCLE_CONFLICT"
    TIME_REWIND = "TIME_REWIND"
    TIME_GAP = "TIME_GAP"
    UNUSABLE_OBSERVATION = "UNUSABLE_OBSERVATION"
    CAPACITY_EXCEEDED = "CAPACITY_EXCEEDED"
    MANEUVER_CONFLICT = "MANEUVER_CONFLICT"
    CORE_CAPABILITY_MISMATCH = "CORE_CAPABILITY_MISMATCH"


class LifecycleError(RuntimeError):
    def __init__(self, failure: LifecycleFailure, message: str) -> None:
        super().__init__(message)
        self.failure = failure


class EncounterKind(StrEnum):
    CLEAR = "CLEAR"
    HEAD_ON = "HEAD_ON"
    CROSSING = "CROSSING"
    OVERTAKING = "OVERTAKING"
    UNKNOWN = "UNKNOWN"


class OwnshipRole(StrEnum):
    NONE = "NONE"
    GIVE_WAY = "GIVE_WAY"
    STAND_ON = "STAND_ON"
    OVERTAKING = "OVERTAKING"
    OVERTAKEN = "OVERTAKEN"
    UNKNOWN = "UNKNOWN"


class RiskPhase(StrEnum):
    CLEAR = "CLEAR"
    CANDIDATE = "CANDIDATE"
    ACTIVE = "ACTIVE"
    PAST_CLEAR = "PAST_CLEAR"
    RELEASED = "RELEASED"


class CommitmentPhase(StrEnum):
    NONE = "NONE"
    COMMITTED = "COMMITTED"
    ACHIEVED = "ACHIEVED"


class PassingSide(StrEnum):
    NONE = "NONE"
    PORT = "PORT"
    STARBOARD = "STARBOARD"


class Rule17Stage(StrEnum):
    NONE = "NONE"
    STAND_ON = "STAND_ON"
    MAY_ACT = "MAY_ACT"
    MUST_ACT = "MUST_ACT"


@dataclass(frozen=True)
class Maneuverability:
    turn_rate_rad_s: float
    deceleration_mps2: float
    speed_bounds_mps: tuple[float, float]

    def __post_init__(self) -> None:
        """Validate physical maneuverability bounds."""
        values = (self.turn_rate_rad_s, self.deceleration_mps2, *self.speed_bounds_mps)
        if not np.all(np.isfinite(values)):
            raise ValueError("maneuverability values must be finite")
        if self.turn_rate_rad_s <= 0.0 or self.deceleration_mps2 <= 0.0:
            raise ValueError("turn rate and deceleration must be positive")
        if not 0.0 <= self.speed_bounds_mps[0] < self.speed_bounds_mps[1]:
            raise ValueError("speed bounds must satisfy 0 <= lower < upper")


@dataclass(frozen=True)
class PlannerOddProfile:
    fresh_age_s: float = 1.0
    usable_age_s: float = 5.0
    reacquire_s: float = 5.0
    tombstone_s: float = 10.0
    entry_confirmation_s: float = 5.0
    rule17_window_s: float = 10.0
    release_confirmation_s: float = 10.0
    hard_hull_clearance_m: float = 50.0
    comfortable_hull_clearance_m: float = 150.0
    cog_min_speed_mps: float = 0.25
    covariance_confidence: float = 0.99
    target_action_course_change_rad: float = math.radians(3.0)
    target_clearance_improvement_m: float = 10.0
    corridor_clearance_tie_m: float = 1.0
    max_targets: int = 16
    max_cycle_gap_s: float = 10.0
    primary_switch_confirmation_s: float = 10.0

    def __post_init__(self) -> None:
        """Validate one published Planner ODD profile."""
        values = tuple(value for value in asdict(self).values() if not isinstance(value, int))
        if not np.all(np.isfinite(values)) or min(values) < 0.0:
            raise ValueError("profile values must be finite and non-negative")
        if self.fresh_age_s > self.usable_age_s:
            raise ValueError("fresh age cannot exceed usable age")
        if self.comfortable_hull_clearance_m < self.hard_hull_clearance_m:
            raise ValueError("comfortable clearance cannot be below hard clearance")
        if not 0.0 < self.covariance_confidence < 1.0:
            raise ValueError("covariance confidence must be between zero and one")
        if self.max_targets < 1:
            raise ValueError("max_targets must be positive")

    @property
    def hash(self) -> str:
        return _hash(asdict(self))


@dataclass(frozen=True)
class OwnshipObservation:
    position_ne_m: np.ndarray
    velocity_ne_mps: np.ndarray
    heading_rad: float
    length_m: float
    width_m: float
    maneuverability: Maneuverability

    def __post_init__(self) -> None:
        """Freeze and validate the ownship observation."""
        object.__setattr__(self, "position_ne_m", _readonly(self.position_ne_m, (2,), "ownship position"))
        object.__setattr__(self, "velocity_ne_mps", _readonly(self.velocity_ne_mps, (2,), "ownship velocity"))
        if not math.isfinite(self.heading_rad):
            raise ValueError("ownship heading must be finite")
        if self.length_m <= 0.0 or self.width_m <= 0.0:
            raise ValueError("ownship dimensions must be positive")


@dataclass(frozen=True)
class TargetObservation:
    key: TrackKey
    state_enu: np.ndarray
    covariance: np.ndarray
    length_m: float
    width_m: float
    observed_at_s: float
    generated_at_s: float
    health: ObservationHealth
    source: str

    def __post_init__(self) -> None:
        """Freeze and validate one target observation."""
        object.__setattr__(self, "state_enu", _readonly(self.state_enu, (4,), "target state"))
        covariance = _readonly(self.covariance, (4, 4), "target covariance")
        if not np.allclose(covariance, covariance.T, atol=1.0e-10, rtol=0.0):
            raise ValueError("target covariance must be symmetric")
        if float(np.min(np.linalg.eigvalsh(covariance))) < -1.0e-9:
            raise ValueError("target covariance must be positive semidefinite")
        object.__setattr__(self, "covariance", covariance)
        if self.length_m <= 0.0 or self.width_m <= 0.0:
            raise ValueError("target dimensions must be positive")
        if self.observed_at_s < 0.0 or self.generated_at_s < self.observed_at_s:
            raise ValueError("target observation times are invalid")
        if not self.source:
            raise ValueError("target source is required")

    @property
    def age_s(self) -> float:
        return self.generated_at_s - self.observed_at_s


@dataclass(frozen=True)
class EncounterCycle:
    epoch: str
    sequence: int
    sim_time_s: float
    ownship: OwnshipObservation
    targets: tuple[TargetObservation, ...]
    route_bearing_rad: float
    planned_speed_mps: float
    profile: PlannerOddProfile

    def __post_init__(self) -> None:
        """Validate one immutable lifecycle input cycle."""
        if not self.epoch:
            raise ValueError("cycle epoch is required")
        if self.sequence < 0 or self.sim_time_s < 0.0:
            raise ValueError("cycle sequence and time must be non-negative")
        if not math.isfinite(self.route_bearing_rad) or not math.isfinite(self.planned_speed_mps):
            raise ValueError("route reference must be finite")
        object.__setattr__(self, "targets", tuple(self.targets))
        keys = [target.key for target in self.targets]
        if len(keys) != len(set(keys)):
            raise ValueError("target keys must be unique")

    @property
    def input_hash(self) -> str:
        return _hash(
            {
                "epoch": self.epoch,
                "sequence": self.sequence,
                "sim_time_s": self.sim_time_s,
                "ownship": {
                    "position": self.ownship.position_ne_m.tolist(),
                    "velocity": self.ownship.velocity_ne_mps.tolist(),
                    "heading": self.ownship.heading_rad,
                    "length": self.ownship.length_m,
                    "width": self.ownship.width_m,
                    "maneuverability": asdict(self.ownship.maneuverability),
                },
                "targets": [
                    {
                        "key": asdict(target.key),
                        "state": target.state_enu.tolist(),
                        "covariance": target.covariance.tolist(),
                        "length": target.length_m,
                        "width": target.width_m,
                        "observed_at_s": target.observed_at_s,
                        "generated_at_s": target.generated_at_s,
                        "health": target.health.value,
                        "source": target.source,
                    }
                    for target in self.targets
                ],
                "route_bearing_rad": self.route_bearing_rad,
                "planned_speed_mps": self.planned_speed_mps,
                "profile": asdict(self.profile),
            }
        )


@dataclass(frozen=True)
class TargetDecision:
    key: TrackKey
    episode: int
    encounter: EncounterKind
    role: OwnshipRole
    risk: RiskPhase
    commitment: CommitmentPhase
    passing_side: PassingSide
    rule17: Rule17Stage
    rule17_basis: str
    geometry: PairwiseGeometry
    baseline_course_rad: float | None
    required_course_change_rad: float
    newly_committed: bool
    health: ObservationHealth
    route_recovery_allowed: bool
    recovery_guard_active: bool
    action_achieved: bool


@dataclass(frozen=True)
class LifecycleEvent:
    schema_version: str
    event_id: int
    sim_time_s: float
    source: str
    event_type: str
    target_key: TrackKey | None
    from_state: str | None
    to_state: str
    reason: str | None = None


@dataclass(frozen=True)
class AggregateDirective:
    required_targets: tuple[TrackKey, ...]
    passing_side: PassingSide
    minimum_course_change_rad: float
    speed_bounds_mps: tuple[float, float]
    stop_required: bool = False


@dataclass(frozen=True)
class DecisionSnapshot:
    epoch: str
    sequence: int
    sim_time_s: float
    input_hash: str
    profile_hash: str
    targets: tuple[TargetDecision, ...] = ()
    directive: AggregateDirective = AggregateDirective((), PassingSide.NONE, 0.0, (0.0, 0.0), False)
    primary_target: TrackKey | None = None
    events: tuple[LifecycleEvent, ...] = ()
    evidence_persisted: bool = True


@dataclass
class _TargetState:
    episode: int = 1
    candidate_since_s: float | None = None
    encounter: EncounterKind = EncounterKind.CLEAR
    role: OwnshipRole = OwnshipRole.NONE
    risk: RiskPhase = RiskPhase.CLEAR
    commitment: CommitmentPhase = CommitmentPhase.NONE
    passing_side: PassingSide = PassingSide.NONE
    rule17: Rule17Stage = Rule17Stage.NONE
    rule17_basis: str = "NOT_APPLICABLE"
    baseline_course_rad: float | None = None
    required_course_change_rad: float = 0.0
    standon_since_s: float | None = None
    initial_target_course_rad: float | None = None
    initial_dcpa_m: float | None = None
    target_action_since_s: float | None = None
    release_since_s: float | None = None
    released_at_s: float | None = None
    route_recovery_allowed: bool = False
    recovery_guard_active: bool = False
    recovery_started: bool = False
    action_achieved: bool = False
    last_health: ObservationHealth | None = None
    reacquire_since_s: float | None = None


@dataclass
class _LifecycleState:
    epoch: str | None = None
    sequence: int = -1
    sim_time_s: float = -1.0
    input_hash: str | None = None
    result: DecisionSnapshot | None = None
    targets: dict[TrackKey, _TargetState] | None = None
    primary_target: TrackKey | None = None
    primary_candidate: TrackKey | None = None
    primary_candidate_since_s: float | None = None


class EncounterLifecycle:
    """Atomic state owner for planner encounter decisions."""

    def __init__(
        self,
        *,
        event_capacity: int = 1024,
        event_sink: Callable[[LifecycleEvent], object] | None = None,
    ) -> None:
        if event_capacity < 1:
            raise ValueError("event_capacity must be positive")
        self._state = _LifecycleState()
        self._event_capacity = event_capacity
        self._event_sink = event_sink
        self._live_events: deque[LifecycleEvent] = deque()
        self._event_overflow_count = 0
        self._next_event_id = 1

    @property
    def live_events(self) -> tuple[LifecycleEvent, ...]:
        return tuple(self._live_events)

    @property
    def event_overflow_count(self) -> int:
        return self._event_overflow_count

    def reset(self, *, epoch: str, reason: str, sim_time_s: float) -> LifecycleEvent:
        if not epoch or not reason:
            raise ValueError("reset epoch and reason are required")
        if not math.isfinite(sim_time_s) or sim_time_s < 0.0:
            raise ValueError("reset time must be finite and non-negative")
        previous_epoch = self._state.epoch
        self._state = _LifecycleState()
        self._live_events.clear()
        self._event_overflow_count = 0
        self._next_event_id = 1
        event = LifecycleEvent(
            schema_version="1.0",
            event_id=self._next_event_id,
            sim_time_s=sim_time_s,
            source="planner",
            event_type="RESET",
            target_key=None,
            from_state=previous_epoch,
            to_state=epoch,
            reason=reason,
        )
        self._next_event_id += 1
        self._record_event(event)
        return event

    def step(self, cycle: EncounterCycle) -> DecisionSnapshot:
        current = self._state
        if current.epoch == cycle.epoch and current.sequence == cycle.sequence:
            if current.input_hash != cycle.input_hash:
                raise LifecycleError(
                    LifecycleFailure.CYCLE_CONFLICT,
                    "same lifecycle cycle received with different input",
                )
            if current.result is None:
                raise RuntimeError("lifecycle retry state is incomplete")
            return current.result
        if current.epoch == cycle.epoch and cycle.sim_time_s < current.sim_time_s:
            raise LifecycleError(LifecycleFailure.TIME_REWIND, "lifecycle time moved backwards")
        if (
            current.epoch == cycle.epoch
            and current.sim_time_s >= 0.0
            and cycle.sim_time_s - current.sim_time_s > cycle.profile.max_cycle_gap_s
        ):
            raise LifecycleError(LifecycleFailure.TIME_GAP, "lifecycle cycle gap exceeds profile")

        target_states = deepcopy(current.targets) if current.epoch == cycle.epoch and current.targets else {}
        decisions = tuple(self._advance_target(cycle, target, target_states) for target in cycle.targets)
        primary_target, primary_candidate, primary_candidate_since_s = _advance_primary(
            cycle,
            decisions,
            current.primary_target if current.epoch == cycle.epoch else None,
            current.primary_candidate if current.epoch == cycle.epoch else None,
            current.primary_candidate_since_s if current.epoch == cycle.epoch else None,
        )
        directive = _aggregate(cycle, decisions)
        events = self._transition_events(cycle, decisions, current.result)
        evidence_persisted = all(self._record_event(event) for event in events)
        result = DecisionSnapshot(
            epoch=cycle.epoch,
            sequence=cycle.sequence,
            sim_time_s=cycle.sim_time_s,
            input_hash=cycle.input_hash,
            profile_hash=cycle.profile.hash,
            targets=decisions,
            directive=directive,
            primary_target=primary_target,
            events=events,
            evidence_persisted=evidence_persisted,
        )
        self._state = _LifecycleState(
            epoch=cycle.epoch,
            sequence=cycle.sequence,
            sim_time_s=cycle.sim_time_s,
            input_hash=cycle.input_hash,
            result=result,
            targets=target_states,
            primary_target=primary_target,
            primary_candidate=primary_candidate,
            primary_candidate_since_s=primary_candidate_since_s,
        )
        return result

    def _transition_events(
        self,
        cycle: EncounterCycle,
        decisions: tuple[TargetDecision, ...],
        previous: DecisionSnapshot | None,
    ) -> tuple[LifecycleEvent, ...]:
        previous_by_key = {decision.key: decision for decision in previous.targets} if previous else {}
        events = []
        for decision in decisions:
            prior = previous_by_key.get(decision.key)
            before = None if prior is None else f"{prior.risk.value}/{prior.commitment.value}/{prior.rule17.value}"
            after = f"{decision.risk.value}/{decision.commitment.value}/{decision.rule17.value}"
            if before == after:
                continue
            events.append(
                LifecycleEvent(
                    schema_version="1.0",
                    event_id=self._next_event_id + len(events),
                    sim_time_s=cycle.sim_time_s,
                    source="planner",
                    event_type="TARGET_TRANSITION",
                    target_key=decision.key,
                    from_state=before,
                    to_state=after,
                )
            )
        self._next_event_id += len(events)
        return tuple(events)

    def _record_event(self, event: LifecycleEvent) -> bool:
        if len(self._live_events) == self._event_capacity:
            self._live_events.popleft()
            self._event_overflow_count += 1
        self._live_events.append(event)
        if self._event_sink is None:
            return False
        try:
            self._event_sink(event)
        except Exception:
            return False
        return True

    def _advance_target(
        self,
        cycle: EncounterCycle,
        target: TargetObservation,
        states: dict[TrackKey, _TargetState],
    ) -> TargetDecision:
        if target.health is ObservationHealth.UNUSABLE or target.age_s > cycle.profile.usable_age_s:
            raise LifecycleError(
                LifecycleFailure.UNUSABLE_OBSERVATION,
                f"target {target.key.target_id} observation is unusable",
            )
        state = states.setdefault(target.key, _TargetState())
        effective_health = _advance_observation_health(state, cycle, target)
        geometry = pairwise_geometry(
            cycle.ownship.position_ne_m,
            cycle.ownship.velocity_ne_mps,
            target.state_enu[:2],
            target.state_enu[2:4],
        )
        encounter, role = _classify(cycle, target, geometry)
        if (
            state.commitment is CommitmentPhase.NONE
            and state.risk in {RiskPhase.ACTIVE, RiskPhase.PAST_CLEAR}
            and state.role in {OwnshipRole.STAND_ON, OwnshipRole.OVERTAKEN}
        ):
            encounter, role = state.encounter, state.role
        if state.risk is RiskPhase.RELEASED:
            if _recovery_guard_holds(state, cycle, target):
                return _target_decision(target, state, geometry, effective_health)
            own_radius = 0.5 * math.hypot(cycle.ownship.length_m, cycle.ownship.width_m)
            target_radius = 0.5 * math.hypot(target.length_m, target.width_m)
            rearm_clearance = (
                own_radius
                + target_radius
                + cycle.profile.hard_hull_clearance_m
                + _position_uncertainty_margin(cycle, target)
            )
            actionable = role in {
                OwnshipRole.GIVE_WAY,
                OwnshipRole.OVERTAKING,
                OwnshipRole.STAND_ON,
                OwnshipRole.OVERTAKEN,
            }
            tombstone_elapsed = (
                state.released_at_s is not None and cycle.sim_time_s - state.released_at_s >= cycle.profile.tombstone_s
            )
            if actionable and tombstone_elapsed and geometry.signed_tcpa_s > 0.0 and geometry.dcpa_m < rearm_clearance:
                state = _TargetState(episode=state.episode + 1)
                states[target.key] = state
            else:
                return _target_decision(target, state, geometry, effective_health)
        if state.commitment is CommitmentPhase.COMMITTED:
            side_sign = -1.0 if state.passing_side is PassingSide.PORT else 1.0
            course_delta = _wrap(cycle.ownship.heading_rad - float(state.baseline_course_rad))
            if side_sign * course_delta >= state.required_course_change_rad - 1.0e-9:
                state.action_achieved = True
            if state.action_achieved:
                _advance_release(state, cycle, target, geometry)
        newly_committed = False
        if state.commitment is CommitmentPhase.NONE:
            newly_committed = _advance_uncommitted(
                state,
                cycle,
                target,
                geometry,
                encounter,
                role,
            )
        elif state.role in {OwnshipRole.STAND_ON, OwnshipRole.OVERTAKEN}:
            if geometry.range_m <= _dynamic_clearance_margin(cycle, target):
                state.rule17 = Rule17Stage.MUST_ACT
                state.rule17_basis = "URGENT_CLEARANCE_PROXY"
        return _target_decision(
            target,
            state,
            geometry,
            effective_health,
            newly_committed=newly_committed,
        )


@dataclass(frozen=True)
class PairwiseGeometry:
    """Instantaneous physical geometry without COLREG policy labels."""

    range_m: float
    dcpa_m: float
    signed_tcpa_s: float
    relative_bearing_rad: float
    contact_bearing_rad: float
    course_difference_rad: float


def pairwise_geometry(
    own_position_ne: np.ndarray,
    own_velocity_ne: np.ndarray,
    target_position_ne: np.ndarray,
    target_velocity_ne: np.ndarray,
) -> PairwiseGeometry:
    """Calculate deterministic relative geometry in north/east coordinates."""
    own_position = _vector2(own_position_ne, "own_position_ne")
    own_velocity = _vector2(own_velocity_ne, "own_velocity_ne")
    target_position = _vector2(target_position_ne, "target_position_ne")
    target_velocity = _vector2(target_velocity_ne, "target_velocity_ne")
    relative_position = target_position - own_position
    relative_velocity = target_velocity - own_velocity
    relative_speed_sq = float(relative_velocity @ relative_velocity)
    if relative_speed_sq > 1.0e-12:
        signed_tcpa_s = -float(relative_position @ relative_velocity) / relative_speed_sq
        cpa_position = relative_position + max(0.0, signed_tcpa_s) * relative_velocity
    else:
        signed_tcpa_s = math.inf
        cpa_position = relative_position
    own_course = math.atan2(float(own_velocity[1]), float(own_velocity[0]))
    target_course = math.atan2(float(target_velocity[1]), float(target_velocity[0]))
    absolute_bearing = math.atan2(float(relative_position[1]), float(relative_position[0]))
    return PairwiseGeometry(
        range_m=float(np.linalg.norm(relative_position)),
        dcpa_m=float(np.linalg.norm(cpa_position)),
        signed_tcpa_s=signed_tcpa_s,
        relative_bearing_rad=_wrap(absolute_bearing - own_course),
        contact_bearing_rad=_wrap(absolute_bearing + math.pi - target_course),
        course_difference_rad=abs(_wrap(target_course - own_course)),
    )


def _classify(
    cycle: EncounterCycle,
    target: TargetObservation,
    geometry: PairwiseGeometry,
) -> tuple[EncounterKind, OwnshipRole]:
    own_speed = float(np.linalg.norm(cycle.ownship.velocity_ne_mps))
    target_speed = float(np.linalg.norm(target.state_enu[2:4]))
    if min(own_speed, target_speed) < cycle.profile.cog_min_speed_mps:
        return EncounterKind.UNKNOWN, OwnshipRole.UNKNOWN
    own_radius = 0.5 * math.hypot(cycle.ownship.length_m, cycle.ownship.width_m)
    target_radius = 0.5 * math.hypot(target.length_m, target.width_m)
    hull_clearance = geometry.dcpa_m - own_radius - target_radius
    if geometry.signed_tcpa_s <= 0.0 or hull_clearance >= cycle.profile.comfortable_hull_clearance_m:
        return EncounterKind.CLEAR, OwnshipRole.NONE

    bearing = math.degrees(geometry.relative_bearing_rad)
    contact_bearing = math.degrees(geometry.contact_bearing_rad)
    course_difference = math.degrees(geometry.course_difference_rad)
    if abs(bearing) <= 15.0 and abs(contact_bearing) <= 15.0 and course_difference >= 150.0:
        return EncounterKind.HEAD_ON, OwnshipRole.GIVE_WAY
    if abs(contact_bearing) > 112.5 and abs(bearing) < 45.0 and own_speed > target_speed:
        return EncounterKind.OVERTAKING, OwnshipRole.OVERTAKING
    if abs(bearing) > 112.5 and abs(contact_bearing) < 45.0 and target_speed > own_speed:
        return EncounterKind.OVERTAKING, OwnshipRole.OVERTAKEN
    if 0.0 < bearing <= 112.5 and -112.5 <= contact_bearing < 0.0:
        return EncounterKind.CROSSING, OwnshipRole.GIVE_WAY
    if -112.5 <= bearing < 0.0 and 0.0 < contact_bearing <= 112.5:
        return EncounterKind.CROSSING, OwnshipRole.STAND_ON
    return EncounterKind.UNKNOWN, OwnshipRole.UNKNOWN


def _advance_observation_health(
    state: _TargetState,
    cycle: EncounterCycle,
    target: TargetObservation,
) -> ObservationHealth:
    effective_health = target.health
    if target.health is ObservationHealth.COASTING:
        state.last_health = ObservationHealth.COASTING
        state.reacquire_since_s = None
    elif target.health is ObservationHealth.UPDATED and state.last_health is ObservationHealth.COASTING:
        if state.reacquire_since_s is None:
            state.reacquire_since_s = cycle.sim_time_s
        if cycle.sim_time_s - state.reacquire_since_s < cycle.profile.reacquire_s:
            effective_health = ObservationHealth.DEGRADED
        else:
            state.last_health = ObservationHealth.UPDATED
            state.reacquire_since_s = None
    else:
        state.last_health = target.health
        state.reacquire_since_s = None
    return effective_health


def _advance_uncommitted(
    state: _TargetState,
    cycle: EncounterCycle,
    target: TargetObservation,
    geometry: PairwiseGeometry,
    encounter: EncounterKind,
    role: OwnshipRole,
) -> bool:
    if (state.encounter, state.role) != (encounter, role):
        state.candidate_since_s = None
    state.encounter = encounter
    state.role = role

    if role in {OwnshipRole.GIVE_WAY, OwnshipRole.OVERTAKING}:
        state.rule17 = Rule17Stage.NONE
        state.rule17_basis = "NOT_APPLICABLE"
        state.risk = RiskPhase.CANDIDATE
        state.passing_side = _passing_side(cycle, target, geometry, role)
        if state.candidate_since_s is None:
            state.candidate_since_s = cycle.sim_time_s
        if (
            not _urgent_action_required(cycle, target, geometry)
            and cycle.sim_time_s - state.candidate_since_s < cycle.profile.entry_confirmation_s
        ):
            return False
        _commit(state, cycle, target, geometry)
        return True

    if role in {OwnshipRole.STAND_ON, OwnshipRole.OVERTAKEN}:
        state.risk = RiskPhase.ACTIVE
        state.passing_side = PassingSide.NONE
        state.rule17 = Rule17Stage.STAND_ON
        state.rule17_basis = "MONITORING_TARGET_ACTION"
        if state.standon_since_s is None:
            state.standon_since_s = cycle.sim_time_s
            state.initial_target_course_rad = math.atan2(
                float(target.state_enu[3]),
                float(target.state_enu[2]),
            )
            state.initial_dcpa_m = geometry.dcpa_m
        target_course_rad = math.atan2(float(target.state_enu[3]), float(target.state_enu[2]))
        target_action_adequate = _target_action_adequate(state, cycle, target_course_rad, geometry)
        elapsed_s = cycle.sim_time_s - state.standon_since_s
        if target_action_adequate:
            state.rule17_basis = "TARGET_ACTION_ADEQUATE"
        elif geometry.range_m <= _dynamic_clearance_margin(cycle, target):
            state.rule17 = Rule17Stage.MUST_ACT
            state.rule17_basis = "URGENT_CLEARANCE_PROXY"
        elif elapsed_s >= cycle.profile.rule17_window_s:
            state.rule17 = Rule17Stage.MAY_ACT
            state.rule17_basis = "TARGET_ACTION_INADEQUATE_DYNAMICS_UNKNOWN"
        if state.rule17 in {Rule17Stage.MAY_ACT, Rule17Stage.MUST_ACT}:
            state.passing_side = PassingSide.STARBOARD
            _commit(state, cycle, target, geometry)
            return True
        return False

    if role is OwnshipRole.UNKNOWN and geometry.signed_tcpa_s > 0.0:
        _advance_unknown_role(state, cycle, target, geometry)
        return False

    state.risk = RiskPhase.CLEAR
    state.commitment = CommitmentPhase.NONE
    state.passing_side = PassingSide.NONE
    state.rule17 = Rule17Stage.NONE
    state.rule17_basis = "NOT_APPLICABLE"
    state.candidate_since_s = None
    state.standon_since_s = None
    state.initial_target_course_rad = None
    state.initial_dcpa_m = None
    state.target_action_since_s = None
    return False


def _advance_unknown_role(
    state: _TargetState,
    cycle: EncounterCycle,
    target: TargetObservation,
    geometry: PairwiseGeometry,
) -> None:
    state.risk = RiskPhase.CANDIDATE
    state.commitment = CommitmentPhase.NONE
    state.passing_side = PassingSide.NONE
    state.rule17 = Rule17Stage.NONE
    state.rule17_basis = "UNKNOWN_ROLE_SAFETY_ONLY"
    if state.candidate_since_s is None:
        state.candidate_since_s = cycle.sim_time_s
    if _urgent_action_required(cycle, target, geometry) or (
        cycle.sim_time_s - state.candidate_since_s >= cycle.profile.entry_confirmation_s
    ):
        state.risk = RiskPhase.ACTIVE


def _target_action_adequate(
    state: _TargetState,
    cycle: EncounterCycle,
    target_course_rad: float,
    geometry: PairwiseGeometry,
) -> bool:
    sample_adequate = (
        abs(_wrap(target_course_rad - float(state.initial_target_course_rad)))
        >= cycle.profile.target_action_course_change_rad
        and geometry.dcpa_m - float(state.initial_dcpa_m) >= cycle.profile.target_clearance_improvement_m
    )
    if not sample_adequate:
        state.target_action_since_s = None
        return False
    if state.target_action_since_s is None:
        state.target_action_since_s = cycle.sim_time_s
    return cycle.sim_time_s - state.target_action_since_s >= cycle.profile.entry_confirmation_s


def _commit(
    state: _TargetState,
    cycle: EncounterCycle,
    target: TargetObservation,
    geometry: PairwiseGeometry,
) -> None:
    state.risk = RiskPhase.ACTIVE
    state.commitment = CommitmentPhase.COMMITTED
    state.baseline_course_rad = cycle.ownship.heading_rad
    state.required_course_change_rad = _substantial_course_change(cycle, target, geometry)
    state.route_recovery_allowed = False
    state.recovery_guard_active = False
    state.recovery_started = False
    state.action_achieved = False


def _substantial_course_change(
    cycle: EncounterCycle,
    target: TargetObservation,
    geometry: PairwiseGeometry,
) -> float:
    own_radius = 0.5 * math.hypot(cycle.ownship.length_m, cycle.ownship.width_m)
    target_radius = 0.5 * math.hypot(target.length_m, target.width_m)
    required_center_clearance = cycle.profile.comfortable_hull_clearance_m + own_radius + target_radius
    deficit = max(0.0, required_center_clearance - geometry.dcpa_m)
    geometric_change = math.asin(min(0.95, deficit / max(geometry.range_m, required_center_clearance)))
    relative_speed = float(np.linalg.norm(target.state_enu[2:4] - cycle.ownship.velocity_ne_mps))
    maneuver_change = cycle.ownship.maneuverability.turn_rate_rad_s * min(
        5.0,
        max(1.0, deficit / max(relative_speed, 0.1) / 4.0),
    )
    return min(math.radians(45.0), max(geometric_change, maneuver_change))


def _passing_side(
    cycle: EncounterCycle,
    target: TargetObservation,
    geometry: PairwiseGeometry,
    role: OwnshipRole,
) -> PassingSide:
    if role is OwnshipRole.GIVE_WAY:
        return PassingSide.STARBOARD
    if role is not OwnshipRole.OVERTAKING:
        return PassingSide.NONE
    required_change = _substantial_course_change(cycle, target, geometry)
    own_speed = float(np.linalg.norm(cycle.ownship.velocity_ne_mps))
    candidates = []
    for side, sign in ((PassingSide.PORT, -1.0), (PassingSide.STARBOARD, 1.0)):
        course = cycle.ownship.heading_rad + sign * required_change
        candidate_velocity = own_speed * np.array([math.cos(course), math.sin(course)])
        candidate_geometry = pairwise_geometry(
            cycle.ownship.position_ne_m,
            candidate_velocity,
            target.state_enu[:2],
            target.state_enu[2:4],
        )
        route_deviation = abs(_wrap(course - cycle.route_bearing_rad))
        candidates.append((side, candidate_geometry.dcpa_m, route_deviation))
    port, starboard = candidates
    if abs(port[1] - starboard[1]) > cycle.profile.corridor_clearance_tie_m:
        return port[0] if port[1] > starboard[1] else starboard[0]
    if abs(port[2] - starboard[2]) > 1.0e-9:
        return port[0] if port[2] < starboard[2] else starboard[0]
    return PassingSide.STARBOARD


def _dynamic_clearance_margin(cycle: EncounterCycle, target: TargetObservation) -> float:
    own_radius = 0.5 * math.hypot(cycle.ownship.length_m, cycle.ownship.width_m)
    target_radius = 0.5 * math.hypot(target.length_m, target.width_m)
    relative_speed = float(np.linalg.norm(target.state_enu[2:4] - cycle.ownship.velocity_ne_mps))
    response_time = (math.pi / 2.0) / cycle.ownship.maneuverability.turn_rate_rad_s
    return (
        own_radius
        + target_radius
        + cycle.profile.hard_hull_clearance_m
        + relative_speed * response_time
        + _position_uncertainty_margin(cycle, target)
    )


def _urgent_action_required(
    cycle: EncounterCycle,
    target: TargetObservation,
    geometry: PairwiseGeometry,
) -> bool:
    own_radius = 0.5 * math.hypot(cycle.ownship.length_m, cycle.ownship.width_m)
    target_radius = 0.5 * math.hypot(target.length_m, target.width_m)
    current_hull_clearance = geometry.range_m - own_radius - target_radius
    response_time_s = (math.pi / 2.0) / cycle.ownship.maneuverability.turn_rate_rad_s
    return current_hull_clearance <= cycle.profile.hard_hull_clearance_m or (0.0 < geometry.signed_tcpa_s <= response_time_s)


def _target_decision(
    target: TargetObservation,
    state: _TargetState,
    geometry: PairwiseGeometry,
    health: ObservationHealth,
    *,
    newly_committed: bool = False,
) -> TargetDecision:
    return TargetDecision(
        key=target.key,
        episode=state.episode,
        encounter=state.encounter,
        role=state.role,
        risk=state.risk,
        commitment=state.commitment,
        passing_side=state.passing_side,
        rule17=state.rule17,
        rule17_basis=state.rule17_basis,
        geometry=geometry,
        baseline_course_rad=state.baseline_course_rad,
        required_course_change_rad=state.required_course_change_rad,
        newly_committed=newly_committed,
        health=health,
        route_recovery_allowed=state.route_recovery_allowed,
        recovery_guard_active=state.recovery_guard_active,
        action_achieved=state.action_achieved,
    )


def _advance_release(
    state: _TargetState,
    cycle: EncounterCycle,
    target: TargetObservation,
    geometry: PairwiseGeometry,
) -> bool:
    recovery_guard_clearance = max(
        _dynamic_clearance_margin(cycle, target),
        0.5 * math.hypot(cycle.ownship.length_m, cycle.ownship.width_m)
        + 0.5 * math.hypot(target.length_m, target.width_m)
        + cycle.profile.comfortable_hull_clearance_m
        + _position_uncertainty_margin(cycle, target),
    )
    if state.risk is RiskPhase.PAST_CLEAR:
        guard_clear = geometry.range_m >= recovery_guard_clearance and _recovery_route_clear(cycle, target)
        if not guard_clear:
            state.risk = RiskPhase.ACTIVE
            state.release_since_s = None
            state.route_recovery_allowed = False
            return False
        state.route_recovery_allowed = True
        if (
            state.release_since_s is not None
            and cycle.sim_time_s - state.release_since_s >= cycle.profile.release_confirmation_s
        ):
            state.risk = RiskPhase.RELEASED
            state.released_at_s = cycle.sim_time_s
            state.recovery_guard_active = True
            if state.commitment is CommitmentPhase.COMMITTED:
                state.commitment = CommitmentPhase.ACHIEVED
        return True
    relative_position = target.state_enu[:2] - cycle.ownship.position_ne_m
    relative_velocity = target.state_enu[2:4] - cycle.ownship.velocity_ne_mps
    separating = float(relative_position @ relative_velocity) > 0.0
    past_clear = (
        geometry.signed_tcpa_s <= 0.0
        and separating
        and geometry.range_m >= _dynamic_clearance_margin(cycle, target)
        and _passing_geometry_clear(state, cycle, target)
        and _recovery_route_clear(cycle, target)
    )
    if not past_clear:
        state.release_since_s = None
        state.route_recovery_allowed = False
        return False
    state.release_since_s = cycle.sim_time_s if state.release_since_s is None else state.release_since_s
    state.risk = RiskPhase.PAST_CLEAR
    state.recovery_started = True
    state.route_recovery_allowed = True
    if cycle.sim_time_s - state.release_since_s >= cycle.profile.release_confirmation_s:
        state.risk = RiskPhase.RELEASED
        state.released_at_s = cycle.sim_time_s
        state.recovery_guard_active = True
        if state.commitment is CommitmentPhase.COMMITTED:
            state.commitment = CommitmentPhase.ACHIEVED
    return True


def _position_uncertainty_margin(cycle: EncounterCycle, target: TargetObservation) -> float:
    largest_variance = max(0.0, float(np.max(np.linalg.eigvalsh(target.covariance[:2, :2]))))
    confidence_scale = math.sqrt(-2.0 * math.log(1.0 - cycle.profile.covariance_confidence))
    return math.sqrt(largest_variance) * confidence_scale


def _recovery_geometry(cycle: EncounterCycle, target: TargetObservation) -> PairwiseGeometry:
    recovery_speed = float(
        np.clip(
            cycle.planned_speed_mps,
            *cycle.ownship.maneuverability.speed_bounds_mps,
        )
    )
    recovery_velocity = recovery_speed * np.array([math.cos(cycle.route_bearing_rad), math.sin(cycle.route_bearing_rad)])
    return pairwise_geometry(
        cycle.ownship.position_ne_m,
        recovery_velocity,
        target.state_enu[:2],
        target.state_enu[2:4],
    )


def _recovery_guard_holds(state: _TargetState, cycle: EncounterCycle, target: TargetObservation) -> bool:
    if not state.recovery_guard_active:
        return False
    recovery_geometry = _recovery_geometry(cycle, target)
    course_recovered = (
        abs(_wrap(cycle.ownship.heading_rad - cycle.route_bearing_rad))
        <= cycle.ownship.maneuverability.turn_rate_rad_s * cycle.profile.entry_confirmation_s
    )
    if course_recovered and recovery_geometry.signed_tcpa_s <= 0.0:
        state.recovery_guard_active = False
    return state.recovery_guard_active


def _recovery_route_clear(cycle: EncounterCycle, target: TargetObservation) -> bool:
    recovery_geometry = _recovery_geometry(cycle, target)
    own_radius = 0.5 * math.hypot(cycle.ownship.length_m, cycle.ownship.width_m)
    target_radius = 0.5 * math.hypot(target.length_m, target.width_m)
    recovery_clearance = (
        own_radius + target_radius + cycle.profile.comfortable_hull_clearance_m + _position_uncertainty_margin(cycle, target)
    )
    return recovery_geometry.signed_tcpa_s <= 0.0 or recovery_geometry.dcpa_m >= recovery_clearance


def _passing_geometry_clear(
    state: _TargetState,
    cycle: EncounterCycle,
    target: TargetObservation,
) -> bool:
    if state.role is not OwnshipRole.OVERTAKING:
        return True
    target_course = math.atan2(float(target.state_enu[3]), float(target.state_enu[2]))
    along = np.array([math.cos(target_course), math.sin(target_course)])
    starboard = np.array([-math.sin(target_course), math.cos(target_course)])
    relative_own = cycle.ownship.position_ne_m - target.state_enu[:2]
    longitudinal_clearance = 0.5 * cycle.ownship.length_m + 0.5 * target.length_m + cycle.profile.hard_hull_clearance_m
    lateral_clearance = 0.5 * cycle.ownship.width_m + 0.5 * target.width_m + cycle.profile.hard_hull_clearance_m
    side_sign = 1.0 if state.passing_side is PassingSide.STARBOARD else -1.0
    return (
        float(relative_own @ along) >= longitudinal_clearance
        and side_sign * float(relative_own @ starboard) >= lateral_clearance
    )


def _advance_primary(
    cycle: EncounterCycle,
    decisions: tuple[TargetDecision, ...],
    current: TrackKey | None,
    candidate: TrackKey | None,
    candidate_since_s: float | None,
) -> tuple[TrackKey | None, TrackKey | None, float | None]:
    eligible = tuple(decision for decision in decisions if _primary_rank(decision) > 0)
    if not eligible:
        return None, None, None
    best = min(eligible, key=_primary_sort_key)
    by_key = {decision.key: decision for decision in eligible}
    if current not in by_key:
        return best.key, None, None
    if best.key == current:
        return current, None, None
    if best.rule17 is Rule17Stage.MUST_ACT and by_key[current].rule17 is not Rule17Stage.MUST_ACT:
        return best.key, None, None
    if candidate != best.key:
        return current, best.key, cycle.sim_time_s
    if candidate_since_s is None or cycle.sim_time_s - candidate_since_s < cycle.profile.primary_switch_confirmation_s:
        return current, candidate, candidate_since_s
    return best.key, None, None


def _primary_rank(decision: TargetDecision) -> int:
    if decision.rule17 is Rule17Stage.MUST_ACT:
        return 5
    if decision.commitment is CommitmentPhase.COMMITTED and decision.risk is RiskPhase.ACTIVE:
        return 4
    if decision.rule17 is Rule17Stage.MAY_ACT:
        return 3
    if decision.role is OwnshipRole.UNKNOWN and decision.risk is RiskPhase.ACTIVE:
        return 3
    if decision.risk is RiskPhase.CANDIDATE:
        return 2
    if decision.risk is RiskPhase.PAST_CLEAR or decision.recovery_guard_active:
        return 1
    return 0


def _primary_sort_key(decision: TargetDecision) -> tuple[float, ...]:
    tcpa = decision.geometry.signed_tcpa_s
    approaching_tcpa = tcpa if tcpa >= 0.0 else math.inf
    return (
        -float(_primary_rank(decision)),
        approaching_tcpa,
        decision.geometry.dcpa_m,
        decision.geometry.range_m,
        float(decision.key.target_id),
        float(decision.key.generation),
    )


def _aggregate(cycle: EncounterCycle, decisions: tuple[TargetDecision, ...]) -> AggregateDirective:
    required = tuple(
        decision
        for decision in decisions
        if (decision.commitment is CommitmentPhase.COMMITTED and decision.risk in {RiskPhase.ACTIVE, RiskPhase.PAST_CLEAR})
        or (decision.role is OwnshipRole.UNKNOWN and decision.risk is RiskPhase.ACTIVE)
        or decision.recovery_guard_active
    )
    if len(required) > cycle.profile.max_targets:
        raise LifecycleError(
            LifecycleFailure.CAPACITY_EXCEEDED,
            f"{len(required)} required targets exceed optimizer capacity {cycle.profile.max_targets}",
        )
    sides = {decision.passing_side for decision in required if decision.passing_side is not PassingSide.NONE}
    if len(sides) > 1:
        if cycle.ownship.maneuverability.speed_bounds_mps[0] == 0.0 and _stopping_is_safe(cycle, required):
            return AggregateDirective(
                required_targets=tuple(decision.key for decision in required),
                passing_side=PassingSide.NONE,
                minimum_course_change_rad=0.0,
                speed_bounds_mps=(0.0, float(np.linalg.norm(cycle.ownship.velocity_ne_mps))),
                stop_required=True,
            )
        raise LifecycleError(
            LifecycleFailure.MANEUVER_CONFLICT,
            "required target course corridors do not intersect",
        )
    side = next(iter(sides), PassingSide.NONE)
    minimum_change = max(
        (decision.required_course_change_rad for decision in required if not decision.action_achieved),
        default=0.0,
    )
    speed_bounds = cycle.ownship.maneuverability.speed_bounds_mps
    overtaking_keys = {decision.key for decision in required if decision.role is OwnshipRole.OVERTAKING}
    if overtaking_keys:
        target_speed_floor = max(
            float(np.linalg.norm(target.state_enu[2:4])) + 0.5 for target in cycle.targets if target.key in overtaking_keys
        )
        lower = min(
            speed_bounds[1] - 0.1,
            max(speed_bounds[0], 0.8 * cycle.planned_speed_mps, target_speed_floor),
        )
        speed_bounds = (lower, speed_bounds[1])
    return AggregateDirective(
        required_targets=tuple(decision.key for decision in required),
        passing_side=side,
        minimum_course_change_rad=minimum_change,
        speed_bounds_mps=speed_bounds,
    )


def _stopping_is_safe(cycle: EncounterCycle, required: tuple[TargetDecision, ...]) -> bool:
    target_by_key = {target.key: target for target in cycle.targets}
    own_speed = float(np.linalg.norm(cycle.ownship.velocity_ne_mps))
    stop_time_s = own_speed / cycle.ownship.maneuverability.deceleration_mps2
    times = np.arange(0.0, max(1200.0, stop_time_s + 30.0) + 0.5, 0.5)
    own_distance = np.where(
        times <= stop_time_s,
        own_speed * times - 0.5 * cycle.ownship.maneuverability.deceleration_mps2 * times**2,
        0.5 * own_speed * stop_time_s,
    )
    along = np.array([math.cos(cycle.ownship.heading_rad), math.sin(cycle.ownship.heading_rad)])
    own_positions = cycle.ownship.position_ne_m + own_distance[:, None] * along
    for decision in required:
        target = target_by_key[decision.key]
        target_positions = target.state_enu[:2] + times[:, None] * target.state_enu[2:4]
        center_distance = np.linalg.norm(target_positions - own_positions, axis=1)
        required_center_clearance = (
            0.5 * math.hypot(cycle.ownship.length_m, cycle.ownship.width_m)
            + 0.5 * math.hypot(target.length_m, target.width_m)
            + cycle.profile.hard_hull_clearance_m
            + _position_uncertainty_margin(cycle, target)
        )
        if float(np.min(center_distance)) < required_center_clearance:
            return False
    return True


def _vector2(value: np.ndarray, name: str) -> np.ndarray:
    array = np.asarray(value, dtype=float)
    if array.shape != (2,) or not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must be a finite 2-vector")
    return array


def _readonly(value: np.ndarray, shape: tuple[int, ...], name: str) -> np.ndarray:
    array = np.array(value, dtype=float, copy=True)
    if array.shape != shape or not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must be a finite array with shape {shape}")
    array.setflags(write=False)
    return array


def _hash(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def _wrap(angle: float) -> float:
    return math.atan2(math.sin(angle), math.cos(angle))
