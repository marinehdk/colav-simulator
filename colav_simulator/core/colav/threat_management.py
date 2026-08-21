"""Session-level online threat authority for one own ship."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any

from colav_simulator.core.colav.encounter_lifecycle import (
    CommitmentPhase,
    EncounterCycle,
    EncounterLifecycle,
    ObservationHealth,
    PhysicalEncounterFacts,
    PrimaryPriorityFact,
    RiskPhase,
    Rule17Stage,
    canonical_physical_facts,
)
from colav_simulator.core.colav.threat_assessment import (
    DomainState,
    PredictionBasis,
    ShipDomainProfile,
    ThreatAssessment,
    ThreatAssessmentRequest,
    ThreatManagementSnapshot,
    ThreatPrediction,
    ThreatPriorityClass,
    ThreatSchedule,
    ThreatScheduleContext,
    ThreatScheduleEntry,
    ThreatScheduleEvent,
    ThreatWindow,
)
from colav_simulator.core.tracking.trackers import TrackKey


class AcceptedPlanState(StrEnum):
    STAGED = "STAGED"
    APPLIED = "APPLIED"
    EXPIRED = "EXPIRED"


DEFAULT_SHIP_DOMAIN_PROFILE = ShipDomainProfile(
    profile_id="colav.ship-domain.v1",
    version="1",
    fore_m=300.0,
    aft_m=100.0,
    port_m=120.0,
    starboard_m=180.0,
    parameter_source="colav-simulator-unqualified-default",
    assumptions=(
        "off-centred elliptical engineering envelope",
        "metres",
        "not a COLREG statutory distance",
    ),
    qualification="UNQUALIFIED",
)


@dataclass(frozen=True)
class AcceptedPlanReceipt:
    """Minimal accepted-plan identity crossing the one-cycle authority boundary."""

    receipt_hash: str
    accepted_sequence: int
    accepted_at_s: float
    valid_until_s: float
    plan_id: str = ""

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> AcceptedPlanReceipt:
        """Normalize an L4 receipt mapping without accepting an untyped candidate."""
        if not isinstance(value, Mapping):
            raise TypeError("accepted plan receipt must be a mapping")
        accepted_sequence = value.get("accepted_sequence", value.get("sequence"))
        accepted_at_s = value.get("accepted_at_s", value.get("accepted_time_s"))
        valid_until_s = value.get("valid_until_s")
        receipt_hash = value.get("receipt_hash")
        if not isinstance(receipt_hash, str) or accepted_sequence is None or accepted_at_s is None or valid_until_s is None:
            raise ValueError("accepted plan mapping lacks typed receipt identity/time")
        return cls(
            receipt_hash=receipt_hash,
            accepted_sequence=int(accepted_sequence),
            accepted_at_s=float(accepted_at_s),
            valid_until_s=float(valid_until_s),
            plan_id=str(value.get("plan_id", "")),
        )

    def __post_init__(self) -> None:
        """Validate receipt identity and its finite validity interval."""
        if not self.receipt_hash.strip() or self.accepted_sequence < 0:
            raise ValueError("accepted plan receipt identity is required")
        if not math.isfinite(self.accepted_at_s) or not math.isfinite(self.valid_until_s):
            raise ValueError("accepted plan receipt times must be finite")
        if self.accepted_at_s < 0.0 or self.valid_until_s < self.accepted_at_s:
            raise ValueError("accepted plan receipt interval is invalid")


class ThreatManagementCoordinator:
    """Own exactly one online EncounterLifecycle and one threat account."""

    def __init__(
        self,
        lifecycle: EncounterLifecycle | None = None,
        *,
        domain_profile: ShipDomainProfile | None = None,
    ) -> None:
        self._lifecycle = lifecycle if lifecycle is not None else EncounterLifecycle()
        self._domain_profile = domain_profile if domain_profile is not None else DEFAULT_SHIP_DOMAIN_PROFILE
        if not isinstance(self._domain_profile, ShipDomainProfile):
            raise TypeError("domain_profile must be ShipDomainProfile")
        self._staged_plan: AcceptedPlanReceipt | None = None
        self._last_snapshot: ThreatManagementSnapshot | None = None

    @property
    def lifecycle(self) -> EncounterLifecycle:
        """Return the sole Lifecycle owned by this coordinator."""
        return self._lifecycle

    @property
    def domain_profile(self) -> ShipDomainProfile:
        """Return the versioned profile used when a cycle omits one."""
        return self._domain_profile

    @property
    def last_snapshot(self) -> ThreatManagementSnapshot | None:
        return self._last_snapshot

    def reset(self, *, epoch: str, reason: str, sim_time_s: float) -> None:
        """Reset lifecycle and staged evidence at Session Replacement."""
        self._lifecycle.reset(epoch=epoch, reason=reason, sim_time_s=sim_time_s)
        self._staged_plan = None
        self._last_snapshot = None

    def publish_accepted_plan(self, receipt: AcceptedPlanReceipt) -> None:
        """Stage an independently accepted receipt for the next cycle."""
        if isinstance(receipt, Mapping):
            receipt = AcceptedPlanReceipt.from_mapping(receipt)
        if not isinstance(receipt, AcceptedPlanReceipt):
            raise TypeError("accepted plan must be AcceptedPlanReceipt")
        self._staged_plan = receipt

    def cycle(
        self,
        cycle: EncounterCycle,
        *,
        profile: ShipDomainProfile | None = None,
        domain_profile: ShipDomainProfile | None = None,
        predictions: tuple[ThreatPrediction, ...] = (),
        accepted_plan: AcceptedPlanReceipt | None = None,
    ) -> ThreatManagementSnapshot:
        """Freeze facts, advance Lifecycle, then publish one immutable account."""
        if not isinstance(cycle, EncounterCycle):
            raise TypeError("cycle must be EncounterCycle")
        domain = profile if profile is not None else domain_profile
        if domain is None:
            domain = self._domain_profile
        if not isinstance(domain, ShipDomainProfile):
            raise TypeError("profile must be ShipDomainProfile")
        if accepted_plan is not None:
            self.publish_accepted_plan(accepted_plan)

        staged = self._staged_plan
        applied = None
        if staged is not None and staged.accepted_sequence < cycle.sequence:
            if cycle.sim_time_s <= staged.valid_until_s + 1.0e-9:
                applied = staged
            else:
                staged = replace(staged)
            self._staged_plan = None

        facts = tuple(cycle.physical_facts) if cycle.physical_facts else tuple(canonical_physical_facts(cycle))
        assessment_request = ThreatAssessmentRequest(
            epoch=cycle.epoch,
            sequence=cycle.sequence,
            sim_time_s=cycle.sim_time_s,
            ownship=cycle.ownship,
            targets=cycle.targets,
            profile=domain,
            predictions=tuple(predictions),
            physical_facts=facts,
        )
        assessed = ThreatAssessment.evaluate(assessment_request)
        priority_facts = tuple(
            _priority_fact(vector, cycle) for vector in assessed.vectors
        )
        lifecycle_targets = tuple(
            target
            for target in cycle.targets
            if target.health.value != "UNUSABLE" and target.age_s <= cycle.profile.usable_age_s
        )
        lifecycle_keys = {target.key for target in lifecycle_targets}
        lifecycle_cycle = replace(
            cycle,
            targets=lifecycle_targets,
            physical_facts=tuple(fact for fact in facts if fact.key in lifecycle_keys),
            primary_priority_facts=tuple(fact for fact in priority_facts if fact.key in lifecycle_keys),
        )
        lifecycle_snapshot = self._lifecycle.cycle(lifecycle_cycle)
        vectors = _attach_lifecycle_and_priority(
            assessed.vectors,
            lifecycle_snapshot,
            predictions=tuple(predictions),
            sim_time_s=cycle.sim_time_s,
        )
        schedule = _build_schedule(
            vectors,
            lifecycle_snapshot,
            cycle_input_hash=assessment_request.input_hash,
            profile_hash=domain.profile_hash,
            sim_time_s=cycle.sim_time_s,
            predictions=tuple(predictions),
        )
        schedule = replace(
            schedule,
            events=_schedule_events(
                schedule,
                previous=None if self._last_snapshot is None else self._last_snapshot.schedule,
                lifecycle_snapshot=lifecycle_snapshot,
                sim_time_s=cycle.sim_time_s,
            ),
        )
        provenance = {
            "authority": "ThreatManagementCoordinator",
            "physical_facts_count": len(facts),
            "physical_facts_hash": _facts_hash(facts),
            "lifecycle_input_hash": lifecycle_cycle.input_hash,
            "lifecycle_omitted_keys": tuple(
                (key.target_id, key.generation)
                for key in sorted(
                    ({vector.key for vector in assessed.vectors} - lifecycle_keys),
                    key=lambda value: (value.target_id, value.generation),
                )
            ),
            "accepted_plan_applied_sequence": cycle.sequence if applied is not None else None,
            "accepted_plan_staged_sequence": (
                staged.accepted_sequence if staged is not None and staged.accepted_sequence >= cycle.sequence else None
            ),
            "accepted_plan_receipt_hash": applied.receipt_hash if applied is not None else None,
        }
        snapshot = replace(
            assessed,
            vectors=vectors,
            lifecycle_snapshot=lifecycle_snapshot,
            schedule=schedule,
            events=schedule.events,
            accepted_plan_receipt=applied,
            provenance=provenance,
        )
        self._last_snapshot = snapshot
        return snapshot


def _priority_fact(vector: Any, cycle: EncounterCycle) -> PrimaryPriorityFact:
    if vector.claim_completeness == "UNKNOWN":
        return PrimaryPriorityFact(key=vector.key, reason="threat_evidence_unknown")
    current_violation = vector.current_domain.state is DomainState.INSIDE
    predicted_violation = vector.predicted_domain.state is DomainState.INSIDE
    response_emergency = bool(
        vector.hull_clearance_m is not None and vector.hull_clearance_m <= 0.0
    ) or bool(
        current_violation
        and vector.tcpa_forward_s is not None
        and vector.tcpa_forward_s <= cycle.profile.action_start_window_s
    )
    reason = ""
    if response_emergency:
        reason = "response_time_emergency"
    elif current_violation:
        reason = "current_domain_violation"
    elif predicted_violation:
        reason = "predicted_domain_violation"
    elif vector.claim_completeness == "FULL":
        reason = "future_severity"
    return PrimaryPriorityFact(
        key=vector.key,
        hard_emergency=response_emergency,
        current_domain_violation=current_violation,
        predicted_domain_violation=predicted_violation,
        future_severity=1 if current_violation or predicted_violation else 0,
        completeness=1 if vector.claim_completeness == "FULL" else 0,
        reason=reason,
    )


def _attach_lifecycle_and_priority(
    vectors: tuple[Any, ...],
    lifecycle_snapshot: Any,
    *,
    predictions: tuple[ThreatPrediction, ...],
    sim_time_s: float,
) -> tuple[Any, ...]:
    decisions = {decision.key: decision for decision in lifecycle_snapshot.targets}
    prediction_by_key = {prediction.key: prediction for prediction in predictions}
    result = []
    for vector in vectors:
        decision = decisions.get(vector.key)
        priority_class, reason, priority_key = _resolved_priority(vector, decision)
        window = _window(vector, prediction_by_key.get(vector.key), sim_time_s)
        result.append(
            replace(
                vector,
                priority_class=priority_class,
                priority_reason=reason,
                priority_key=priority_key,
                window=window,
                lifecycle_role=decision.role.value if decision is not None else None,
                lifecycle_risk=decision.risk.value if decision is not None else None,
                lifecycle_commitment=decision.commitment.value if decision is not None else None,
            )
        )
    return tuple(result)


def _resolved_priority(vector: Any, decision: Any) -> tuple[ThreatPriorityClass, str, tuple[float, ...]]:
    if vector.observation_health is ObservationHealth.UNUSABLE or vector.claim_completeness == "UNKNOWN":
        return ThreatPriorityClass.UNKNOWN, "observation_unusable", (7.0,)
    if vector.hull_clearance_m is not None and vector.hull_clearance_m <= 0.0:
        return ThreatPriorityClass.RESPONSE_TIME_EMERGENCY, "response_time_emergency", (0.0,)
    if decision is not None and decision.rule17 is Rule17Stage.MUST_ACT:
        return ThreatPriorityClass.RULE17_MUST_ACT, "rule17_must_act", (1.0,)
    if (
        decision is not None
        and decision.commitment is CommitmentPhase.COMMITTED
        and decision.risk is RiskPhase.ACTIVE
    ):
        return ThreatPriorityClass.COMMITTED_ACTIVE, "committed_active", (2.0,)
    if vector.current_domain.state is DomainState.INSIDE:
        return ThreatPriorityClass.CURRENT_DOMAIN_VIOLATION, "current_domain_violation", (3.0,)
    if vector.predicted_domain.state is DomainState.INSIDE:
        return ThreatPriorityClass.PREDICTED_DOMAIN_VIOLATION, "predicted_domain_violation", (4.0,)
    if vector.claim_completeness == "FULL":
        return ThreatPriorityClass.FUTURE_SEVERITY, "future_severity", (5.0,)
    return ThreatPriorityClass.UNKNOWN, "threat_evidence_unknown", (6.0,)


def _window(vector: Any, prediction: ThreatPrediction | None, sim_time_s: float) -> ThreatWindow:
    if prediction is None:
        return ThreatWindow(
            key=vector.key,
            reference_time_s=sim_time_s,
            prediction_basis=PredictionBasis.UNAVAILABLE,
            completeness="UNKNOWN",
            unavailable_reason="PREDICTION_UNAVAILABLE",
        )
    domain = vector.predicted_domain
    entry = domain.tdv_s
    exit_time = domain.tde_s
    peak = domain.tdv_s if domain.horizon_min_scale is not None else None
    horizon_end = float(prediction.times_s[-1])
    return ThreatWindow(
        key=vector.key,
        entry_time_s=entry,
        peak_time_s=peak,
        exit_time_s=exit_time,
        reference_time_s=sim_time_s,
        horizon_end_s=horizon_end,
        prediction_basis=prediction.basis,
        completeness=vector.claim_completeness,
        unavailable_reason=(
            domain.unavailable_reason
            if domain.state in {DomainState.UNKNOWN, DomainState.UNQUALIFIED}
            else None
        ),
        entry_time_absolute_s=None if entry is None else sim_time_s + entry,
        peak_time_absolute_s=None if peak is None else sim_time_s + peak,
        exit_time_absolute_s=None if exit_time is None else sim_time_s + exit_time,
    )


def _build_schedule(
    vectors: tuple[Any, ...],
    lifecycle_snapshot: Any,
    *,
    cycle_input_hash: str,
    profile_hash: str,
    sim_time_s: float,
    predictions: tuple[ThreatPrediction, ...],
) -> ThreatSchedule:
    vector_by_key = {vector.key: vector for vector in vectors}
    required = set(lifecycle_snapshot.directive.required_targets)
    current = lifecycle_snapshot.primary_target
    contexts: dict[TrackKey, ThreatScheduleContext] = {}
    for vector in vectors:
        decision = next((item for item in lifecycle_snapshot.targets if item.key == vector.key), None)
        if decision is not None and decision.risk is RiskPhase.RELEASED:
            context = ThreatScheduleContext.RELEASED
        elif vector.key == current:
            context = ThreatScheduleContext.CURRENT_PRIMARY
        elif vector.key in required:
            context = ThreatScheduleContext.CONCURRENT_REQUIRED
        elif vector.predicted_domain.state is DomainState.INSIDE or vector.current_domain.state is DomainState.INSIDE:
            context = ThreatScheduleContext.NEXT
        else:
            context = ThreatScheduleContext.MONITOR
        contexts[vector.key] = context

    entries = tuple(
        ThreatScheduleEntry(
            key=key,
            context=contexts[key],
            window=vector_by_key[key].window,
            priority_class=vector_by_key[key].priority_class,
            priority_reason=vector_by_key[key].priority_reason,
            unavailable_reason=(
                vector_by_key[key].predicted_domain.unavailable_reason
                if vector_by_key[key].predicted_domain.state in {DomainState.UNKNOWN, DomainState.UNQUALIFIED}
                else None
            ),
            handoff_expectation=(
                "hysteresis_pending"
                if lifecycle_snapshot.primary_challenger == key
                else None
            ),
        )
        for key in sorted(contexts, key=lambda value: (value.target_id, value.generation))
    )
    ordered = sorted(
        (vector for vector in vectors if contexts[vector.key] is ThreatScheduleContext.NEXT),
        key=lambda vector: (vector.priority_key, vector.key.target_id, vector.key.generation),
    )
    return ThreatSchedule(
        current_primary=current,
        concurrent_required=tuple(
            sorted(
                required - ({current} if current is not None else set()),
                key=lambda key: (key.target_id, key.generation),
            )
        ),
        next_threats=tuple(vector.key for vector in ordered),
        monitor=tuple(
            sorted(
                (key for key, context in contexts.items() if context is ThreatScheduleContext.MONITOR),
                key=lambda key: (key.target_id, key.generation),
            )
        ),
        released=tuple(
            sorted(
                (key for key, context in contexts.items() if context is ThreatScheduleContext.RELEASED),
                key=lambda key: (key.target_id, key.generation),
            )
        ),
        entries=entries,
        events=(),
        horizon_start_s=sim_time_s,
        horizon_end_s=(max((float(prediction.times_s[-1]) for prediction in predictions), default=None)),
        generated_at_s=sim_time_s,
        input_hash=cycle_input_hash,
        profile_hash=profile_hash,
    )


def _schedule_events(
    schedule: ThreatSchedule,
    *,
    previous: ThreatSchedule | None,
    lifecycle_snapshot: Any,
    sim_time_s: float,
) -> tuple[ThreatScheduleEvent, ...]:
    """Derive typed rolling transitions from adjacent immutable schedules."""
    events: list[ThreatScheduleEvent] = []
    previous_by_key = {} if previous is None else {entry.key: entry for entry in previous.entries}
    for entry in schedule.entries:
        prior = previous_by_key.get(entry.key)
        predicted = entry.window is not None and entry.window.prediction_basis is not PredictionBasis.UNAVAILABLE
        if prior is None and entry.context in {
            ThreatScheduleContext.CURRENT_PRIMARY,
            ThreatScheduleContext.CONCURRENT_REQUIRED,
            ThreatScheduleContext.NEXT,
        }:
            events.append(
                ThreatScheduleEvent(
                    event_id=len(events) + 1,
                    sim_time_s=sim_time_s,
                    event_type="THREAT_ENTERED",
                    key=entry.key,
                    reason="predicted_window_entered" if predicted else "current_required_obligation",
                    to_context=entry.context,
                    predicted=predicted,
                )
            )
        elif prior is not None and prior.context is not entry.context:
            if entry.context is ThreatScheduleContext.RELEASED:
                event_type = "THREAT_RELEASED"
            elif (
                entry.context is ThreatScheduleContext.MONITOR
                and prior.context
                in {
                    ThreatScheduleContext.CURRENT_PRIMARY,
                    ThreatScheduleContext.CONCURRENT_REQUIRED,
                    ThreatScheduleContext.NEXT,
                }
            ):
                event_type = "THREAT_CLEARING"
            elif prior.context is ThreatScheduleContext.MONITOR and entry.context is ThreatScheduleContext.NEXT:
                event_type = "THREAT_ESCALATED"
            else:
                event_type = "SCHEDULE_REORDER"
            events.append(
                ThreatScheduleEvent(
                    event_id=len(events) + 1,
                    sim_time_s=sim_time_s,
                    event_type=event_type,
                    key=entry.key,
                    reason=entry.priority_reason or "schedule_context_changed",
                    from_context=prior.context,
                    to_context=entry.context,
                    predicted=predicted,
                )
            )
        elif prior is not None and prior.priority_class is not entry.priority_class:
            events.append(
                ThreatScheduleEvent(
                    event_id=len(events) + 1,
                    sim_time_s=sim_time_s,
                    event_type="THREAT_ESCALATED",
                    key=entry.key,
                    reason=entry.priority_reason or "priority_class_changed",
                    from_context=prior.context,
                    to_context=entry.context,
                    predicted=predicted,
                )
            )

    if lifecycle_snapshot.primary_challenger is not None:
        events.append(
            ThreatScheduleEvent(
                event_id=len(events) + 1,
                sim_time_s=sim_time_s,
                event_type="PRIMARY_CHALLENGER",
                key=lifecycle_snapshot.primary_challenger,
                reason=lifecycle_snapshot.primary_switch_reason or "hysteresis_pending",
                predicted=True,
            )
        )
    if previous is not None and previous.current_primary != schedule.current_primary:
        events.append(
            ThreatScheduleEvent(
                event_id=len(events) + 1,
                sim_time_s=sim_time_s,
                event_type="PRIMARY_SWITCHED",
                key=schedule.current_primary,
                reason=lifecycle_snapshot.primary_switch_reason or "primary_changed",
                predicted=False,
            )
        )
    previous_order = () if previous is None else tuple(entry.key for entry in previous.entries)
    current_order = tuple(entry.key for entry in schedule.entries)
    if previous is not None and previous_order != current_order:
        events.append(
            ThreatScheduleEvent(
                event_id=len(events) + 1,
                sim_time_s=sim_time_s,
                event_type="SCHEDULE_REORDER",
                key=None,
                reason="deterministic_track_key_order_changed",
                predicted=True,
            )
        )
    return tuple(events)


def _facts_hash(facts: tuple[PhysicalEncounterFacts, ...]) -> str:
    payload = [
        {
            "key": [fact.key.target_id, fact.key.generation],
            "range_m": fact.geometry.range_m,
            "dcpa_m": fact.geometry.dcpa_m,
            "signed_tcpa_s": (
                fact.geometry.signed_tcpa_s
                if math.isfinite(fact.geometry.signed_tcpa_s)
                else None
            ),
            "validity": fact.validity,
            "unavailable_reason": fact.unavailable_reason,
        }
        for fact in facts
    ]
    return hashlib.sha256(json.dumps(payload, sort_keys=True, allow_nan=False, separators=(",", ":")).encode()).hexdigest()
