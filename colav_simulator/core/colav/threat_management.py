"""Session-level online threat authority for one own ship."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import StrEnum
from itertools import combinations
from typing import Any

import numpy as np

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
    ConflictCluster,
    ConflictEdge,
    ConflictEdgeType,
    ConflictGraph,
    ConflictGraphProfile,
    ConflictPredictionBasis,
    ConflictUnavailableReason,
    ConflictWitness,
    DomainState,
    OwnshipThreatPrediction,
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
    normalized_domain_scale,
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
    accepted_prediction: OwnshipThreatPrediction | None = None
    plan_target: TrackKey | None = None
    target_keys: tuple[TrackKey, ...] = ()
    prediction_hash: str | None = None
    acceptance_hash: str | None = None
    domain_profile_hash: str | None = None
    evidence_semantic_hash: str | None = None

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
        accepted_prediction = value.get("accepted_prediction", value.get("ownship_prediction"))
        if accepted_prediction is not None and not isinstance(accepted_prediction, OwnshipThreatPrediction):
            accepted_prediction = OwnshipThreatPrediction(
                times_s=accepted_prediction["times_s"],
                states_enu=accepted_prediction["states_enu"],
                basis=str(accepted_prediction.get("basis", "ACCEPTED_PLAN")),
                model=str(accepted_prediction.get("model", "accepted_plan")),
                source=str(accepted_prediction.get("source", "L4_ACCEPTED_RECEIPT")),
                target_keys=tuple(_track_key_from_value(item) for item in accepted_prediction.get("target_keys", ())),
                reference_time_s=float(accepted_prediction.get("reference_time_s", accepted_at_s)),
                coordinate_frame=str(accepted_prediction.get("coordinate_frame", "ENU")),
                linear_unit=str(accepted_prediction.get("linear_unit", "m")),
                angle_unit=str(accepted_prediction.get("angle_unit", "rad")),
                evidence_semantic_hash=(
                    str(accepted_prediction["evidence_semantic_hash"])
                    if accepted_prediction.get("evidence_semantic_hash") is not None
                    else None
                ),
                prediction_hash=str(accepted_prediction.get("prediction_hash", "")),
            )
        plan_target_value = value.get("plan_target", value.get("target_key"))
        plan_target = _track_key_from_value(plan_target_value) if plan_target_value is not None else None
        target_keys = tuple(_track_key_from_value(item) for item in value.get("target_keys", ()))
        if "candidate_hash" in value and not (
            value.get("parent_acceptance_hash") or value.get("semantic_acceptance_hash")
        ):
            raise ValueError("raw solver candidate cannot be accepted as a plan receipt")
        return cls(
            receipt_hash=receipt_hash,
            accepted_sequence=int(accepted_sequence),
            accepted_at_s=float(accepted_at_s),
            valid_until_s=float(valid_until_s),
            plan_id=str(value.get("plan_id", "")),
            accepted_prediction=accepted_prediction,
            plan_target=plan_target,
            target_keys=target_keys,
            prediction_hash=(
                str(value["prediction_hash"])
                if value.get("prediction_hash") is not None
                else (accepted_prediction.prediction_hash if accepted_prediction is not None else None)
            ),
            acceptance_hash=(
                str(value.get("semantic_acceptance_hash", value.get("parent_acceptance_hash")))
                if value.get("semantic_acceptance_hash", value.get("parent_acceptance_hash")) is not None
                else None
            ),
            domain_profile_hash=(
                str(value["domain_profile_hash"]) if value.get("domain_profile_hash") is not None else None
            ),
            evidence_semantic_hash=(
                str(value["evidence_semantic_hash"])
                if value.get("evidence_semantic_hash") is not None
                else (
                    accepted_prediction.evidence_semantic_hash
                    if accepted_prediction is not None
                    else None
                )
            ),
        )

    def __post_init__(self) -> None:
        """Validate receipt identity and its finite validity interval."""
        if not self.receipt_hash.strip() or self.accepted_sequence < 0:
            raise ValueError("accepted plan receipt identity is required")
        if not math.isfinite(self.accepted_at_s) or not math.isfinite(self.valid_until_s):
            raise ValueError("accepted plan receipt times must be finite")
        if self.accepted_at_s < 0.0 or self.valid_until_s < self.accepted_at_s:
            raise ValueError("accepted plan receipt interval is invalid")
        keys = tuple(sorted(self.target_keys, key=_track_key_sort))
        if len(keys) != len(set(keys)) or any(not isinstance(key, TrackKey) for key in keys):
            raise ValueError("accepted plan target keys must be unique TrackKeys")
        object.__setattr__(self, "target_keys", keys)
        if self.plan_target is not None and not isinstance(self.plan_target, TrackKey):
            raise TypeError("accepted plan target must be TrackKey")
        if self.accepted_prediction is not None and not isinstance(self.accepted_prediction, OwnshipThreatPrediction):
            raise TypeError("accepted prediction must be OwnshipThreatPrediction")
        if self.prediction_hash is not None and not self.prediction_hash.strip():
            raise ValueError("prediction_hash cannot be empty")
        if self.acceptance_hash is not None and not self.acceptance_hash.strip():
            raise ValueError("acceptance_hash cannot be empty")
        if self.evidence_semantic_hash is not None and not self.evidence_semantic_hash.strip():
            raise ValueError("evidence semantic hash cannot be empty")
        if (
            self.accepted_prediction is not None
            and self.prediction_hash is not None
            and self.prediction_hash != self.accepted_prediction.semantic_hash
        ):
            raise ValueError("accepted plan prediction hash does not match artifact")
        if (
            self.accepted_prediction is not None
            and self.evidence_semantic_hash is not None
            and self.evidence_semantic_hash != self.accepted_prediction.evidence_semantic_hash
        ):
            raise ValueError("accepted plan evidence hash does not match artifact")
        if (
            self.accepted_prediction is not None
            and not math.isclose(
                self.accepted_at_s,
                self.accepted_prediction.reference_time_s,
                rel_tol=0.0,
                abs_tol=1.0e-9,
            )
        ):
            raise ValueError("accepted plan artifact reference time does not match receipt")


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
        self._staged_plan_unavailable_reason: ConflictUnavailableReason | None = None
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
        self._staged_plan_unavailable_reason = None
        self._last_snapshot = None

    def publish_accepted_plan(self, receipt: AcceptedPlanReceipt) -> None:
        """Stage an independently accepted receipt for the next cycle."""
        if isinstance(receipt, Mapping):
            receipt = AcceptedPlanReceipt.from_mapping(receipt)
        if not isinstance(receipt, AcceptedPlanReceipt):
            raise TypeError("accepted plan must be AcceptedPlanReceipt")
        self._staged_plan = receipt
        self._staged_plan_unavailable_reason = None

    def cycle(
        self,
        cycle: EncounterCycle,
        *,
        profile: ShipDomainProfile | None = None,
        domain_profile: ShipDomainProfile | None = None,
        predictions: tuple[ThreatPrediction, ...] = (),
        accepted_plan: AcceptedPlanReceipt | None = None,
        baseline_prediction: OwnshipThreatPrediction | None = None,
        conflict_profile: ConflictGraphProfile | None = None,
    ) -> ThreatManagementSnapshot:
        """Freeze facts, advance Lifecycle, then publish one immutable account."""
        if not isinstance(cycle, EncounterCycle):
            raise TypeError("cycle must be EncounterCycle")
        domain = profile if profile is not None else domain_profile
        if domain is None:
            domain = self._domain_profile
        if not isinstance(domain, ShipDomainProfile):
            raise TypeError("profile must be ShipDomainProfile")
        receipt_unavailable_reason = self._staged_plan_unavailable_reason
        if accepted_plan is not None:
            try:
                self.publish_accepted_plan(accepted_plan)
            except (TypeError, ValueError):
                self._staged_plan = None
                self._staged_plan_unavailable_reason = ConflictUnavailableReason.ACCEPTED_PLAN_RECEIPT_INVALID
                receipt_unavailable_reason = self._staged_plan_unavailable_reason

        staged = self._staged_plan
        applied = None
        expired = False
        if staged is not None and staged.accepted_sequence < cycle.sequence:
            if cycle.sim_time_s <= staged.valid_until_s + 1.0e-9:
                applied = staged
            else:
                expired = True
            self._staged_plan = None
            self._staged_plan_unavailable_reason = None

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
        graph_unavailable_reasons = []
        if receipt_unavailable_reason is not None:
            graph_unavailable_reasons.append(receipt_unavailable_reason)
        if expired:
            graph_unavailable_reasons.append(ConflictUnavailableReason.ACCEPTED_PLAN_EXPIRED)
        graph = ConflictGraphBuilder.build(
            vectors,
            predictions=tuple(predictions),
            profile=conflict_profile or ConflictGraphProfile(),
            domain_profile=domain,
            input_hash=assessment_request.input_hash,
            baseline_prediction=baseline_prediction,
            accepted_plan=applied,
            lifecycle_snapshot=lifecycle_snapshot,
            previous=None if self._last_snapshot is None else self._last_snapshot.conflict_graph,
            unavailable_reasons=tuple(graph_unavailable_reasons),
            sim_time_s=cycle.sim_time_s,
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
            "conflict_graph_hash": graph.semantic_hash,
            "conflict_edge_count": len(graph.edges),
            "conflict_cluster_count": len(graph.clusters),
        }
        snapshot = replace(
            assessed,
            vectors=vectors,
            lifecycle_snapshot=lifecycle_snapshot,
            schedule=schedule,
            events=schedule.events,
            accepted_plan_receipt=applied,
            conflict_graph=graph,
            provenance=provenance,
        )
        self._staged_plan_unavailable_reason = None
        self._last_snapshot = snapshot
        return snapshot


class ConflictGraphBuilder:
    """Build typed conflict edges and deterministic connected components."""

    @staticmethod
    def build(  # noqa: C901, PLR0912, PLR0915
        vectors: tuple[Any, ...],
        *,
        predictions: tuple[ThreatPrediction, ...],
        profile: ConflictGraphProfile,
        domain_profile: ShipDomainProfile,
        input_hash: str,
        baseline_prediction: OwnshipThreatPrediction | None,
        accepted_plan: AcceptedPlanReceipt | None,
        lifecycle_snapshot: Any | None,
        previous: ConflictGraph | None,
        unavailable_reasons: tuple[ConflictUnavailableReason | str, ...] = (),
        sim_time_s: float = 0.0,
    ) -> ConflictGraph:
        if not isinstance(profile, ConflictGraphProfile):
            raise TypeError("profile must be ConflictGraphProfile")
        if not isinstance(domain_profile, ShipDomainProfile):
            raise TypeError("domain_profile must be ShipDomainProfile")
        ordered_vectors = tuple(sorted(vectors, key=lambda vector: _track_key_sort(vector.key)))
        nodes = tuple(vector.key for vector in ordered_vectors)
        edges: list[ConflictEdge] = []
        vector_by_key = {vector.key: vector for vector in ordered_vectors}
        for left, right in combinations(ordered_vectors, 2):
            overlap = _window_overlap(left.window, right.window, profile.window_overlap_gap_s)
            if overlap is None:
                continue
            witness = ConflictWitness(
                {
                    "left_window": _window_document(left.window),
                    "right_window": _window_document(right.window),
                    "overlap_start_s": overlap[0],
                    "overlap_end_s": overlap[1],
                    "overlap_duration_s": overlap[1] - overlap[0],
                    "gap_tolerance_s": profile.window_overlap_gap_s,
                }
            )
            edges.append(
                _make_edge(
                    ConflictEdgeType.DIRECT_WINDOW_OVERLAP,
                    (left.key, right.key),
                    ConflictPredictionBasis.THREAT_WINDOW,
                    witness,
                    input_hash,
                )
            )

        plan_reasons = [ConflictUnavailableReason(reason) for reason in unavailable_reasons]
        prediction_by_key = {prediction.key: prediction for prediction in predictions}
        if baseline_prediction is None:
            plan_reasons.append(ConflictUnavailableReason.BASELINE_UNAVAILABLE)
        if accepted_plan is None:
            plan_reasons.append(ConflictUnavailableReason.ACCEPTED_PLAN_UNAVAILABLE)
        elif accepted_plan.accepted_prediction is None:
            plan_reasons.append(ConflictUnavailableReason.ACCEPTED_PLAN_PREDICTION_UNAVAILABLE)
        elif accepted_plan.valid_until_s + 1.0e-9 < sim_time_s:
            plan_reasons.append(ConflictUnavailableReason.ACCEPTED_PLAN_EXPIRED)
        else:
            target_keys = set(prediction_by_key)
            if (
                baseline_prediction is not None
                and (
                    not baseline_prediction.target_keys
                    or set(baseline_prediction.target_keys) != target_keys
                )
            ):
                plan_reasons.append(ConflictUnavailableReason.TARGET_PREDICTION_IDENTITY_MISMATCH)
            accepted_prediction = accepted_plan.accepted_prediction
            if not accepted_plan.target_keys or set(accepted_plan.target_keys) != target_keys:
                plan_reasons.append(ConflictUnavailableReason.PLAN_PREDICTION_IDENTITY_MISMATCH)
            if (
                accepted_prediction is not None
                and (
                    not accepted_prediction.target_keys
                    or set(accepted_prediction.target_keys) != target_keys
                )
            ):
                plan_reasons.append(ConflictUnavailableReason.PLAN_PREDICTION_IDENTITY_MISMATCH)
            if (
                accepted_plan.prediction_hash is not None
                and accepted_prediction is not None
                and accepted_plan.prediction_hash != accepted_prediction.semantic_hash
            ):
                plan_reasons.append(ConflictUnavailableReason.PLAN_PREDICTION_IDENTITY_MISMATCH)
            if (
                accepted_plan.domain_profile_hash is not None
                and accepted_plan.domain_profile_hash != domain_profile.profile_hash
            ):
                plan_reasons.append(ConflictUnavailableReason.PLAN_PROFILE_MISMATCH)
            driver_key = accepted_plan.plan_target
            if driver_key is None and lifecycle_snapshot is not None:
                driver_key = getattr(lifecycle_snapshot, "primary_target", None)
            if driver_key is None or driver_key not in vector_by_key:
                plan_reasons.append(ConflictUnavailableReason.PLAN_TARGET_UNAVAILABLE)
            elif not plan_reasons:
                for target_key, prediction in sorted(
                    prediction_by_key.items(),
                    key=lambda item: _track_key_sort(item[0]),
                ):
                    if target_key == driver_key:
                        continue
                    vector = vector_by_key.get(target_key)
                    if vector is None or vector.uncertainty_radius_m is None:
                        plan_reasons.append(ConflictUnavailableReason.TARGET_PREDICTION_UNAVAILABLE)
                        continue
                    baseline_trace = _ownship_domain_trace(
                        baseline_prediction,
                        prediction,
                        vector.uncertainty_radius_m,
                        domain_profile,
                        comparison_time_s=sim_time_s,
                    )
                    accepted_trace = _ownship_domain_trace(
                        accepted_prediction,
                        prediction,
                        vector.uncertainty_radius_m,
                        domain_profile,
                        comparison_time_s=sim_time_s,
                    )
                    if baseline_trace is None or accepted_trace is None:
                        plan_reasons.append(ConflictUnavailableReason.TARGET_PREDICTION_UNAVAILABLE)
                        continue
                    material = _material_plan_worsening(baseline_trace, accepted_trace, profile)
                    if material is None:
                        continue
                    witness = ConflictWitness(
                        {
                            "driver_target": _key_document(driver_key),
                            "affected_target": _key_document(target_key),
                            "baseline": baseline_trace,
                            "accepted": accepted_trace,
                            "materiality": material,
                            "baseline_prediction_hash": baseline_prediction.semantic_hash,
                            "accepted_prediction_hash": accepted_prediction.semantic_hash,
                            "accepted_evidence_semantic_hash": accepted_plan.evidence_semantic_hash,
                            "plan_receipt_hash": accepted_plan.receipt_hash,
                        }
                    )
                    edges.append(
                        _make_edge(
                            ConflictEdgeType.PLAN_INDUCED_CONFLICT,
                            (driver_key, target_key),
                            ConflictPredictionBasis.BASELINE_VS_ACCEPTED_PLAN,
                            witness,
                            input_hash,
                            plan_receipt_hash=accepted_plan.receipt_hash,
                        )
                    )
        clusters = _connected_clusters(edges, profile.profile_hash, previous)
        return ConflictGraph(
            nodes=nodes,
            edges=tuple(edges),
            clusters=clusters,
            unavailable_reasons=tuple(plan_reasons),
            profile_hash=profile.profile_hash,
            input_hash=input_hash,
        )


def _make_edge(
    edge_type: ConflictEdgeType,
    members: tuple[TrackKey, ...],
    prediction_basis: ConflictPredictionBasis,
    witness: ConflictWitness,
    input_hash: str,
    *,
    plan_receipt_hash: str | None = None,
) -> ConflictEdge:
    identity = {
        "edge_type": edge_type.value,
        "members": [_key_document(key) for key in sorted(members, key=_track_key_sort)],
        "prediction_basis": prediction_basis.value,
        "witness": witness.to_dict(),
        "input_hash": input_hash,
        "plan_receipt_hash": plan_receipt_hash,
    }
    edge_id = f"conflict-edge-v1:{_sha256_json(identity)}"
    return ConflictEdge(
        edge_id=edge_id,
        edge_type=edge_type,
        members=members,
        prediction_basis=prediction_basis,
        witness=witness,
        input_hash=input_hash,
        plan_receipt_hash=plan_receipt_hash,
    )


def _connected_clusters(
    edges: list[ConflictEdge],
    profile_hash: str,
    previous: ConflictGraph | None,
) -> tuple[ConflictCluster, ...]:
    parent: dict[TrackKey, TrackKey] = {}

    def find(key: TrackKey) -> TrackKey:
        parent.setdefault(key, key)
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    def union(left: TrackKey, right: TrackKey) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[max(left_root, right_root, key=_track_key_sort)] = min(
                left_root,
                right_root,
                key=_track_key_sort,
            )

    for edge in edges:
        for member in edge.members:
            find(member)
        for member in edge.members[1:]:
            union(edge.members[0], member)
    members_by_root: dict[TrackKey, set[TrackKey]] = {}
    for member in parent:
        members_by_root.setdefault(find(member), set()).add(member)
    previous_clusters = () if previous is None else previous.clusters
    clusters: list[ConflictCluster] = []
    for members in members_by_root.values():
        if len(members) < 2:
            continue
        member_set = set(members)
        edge_ids = tuple(sorted(edge.edge_id for edge in edges if member_set.intersection(edge.members)))
        identity = {
            "schema_version": "colav.conflict-cluster@1",
            "members": [_key_document(key) for key in sorted(member_set, key=_track_key_sort)],
            "edge_ids": list(edge_ids),
            "profile_hash": profile_hash,
        }
        cluster_id = f"conflict-cluster-v1:{_sha256_json(identity)}"
        parents = tuple(
            cluster.cluster_id
            for cluster in previous_clusters
            if member_set.intersection(cluster.members)
        )
        clusters.append(
            ConflictCluster(
                cluster_id=cluster_id,
                members=tuple(member_set),
                edge_ids=edge_ids,
                parent_cluster_ids=parents,
            )
        )
    return tuple(sorted(clusters, key=lambda cluster: cluster.cluster_id))


def _window_overlap(
    left: ThreatWindow | None,
    right: ThreatWindow | None,
    gap_s: float,
) -> tuple[float, float] | None:
    left_interval = _window_interval(left)
    right_interval = _window_interval(right)
    if left_interval is None or right_interval is None:
        return None
    start = max(left_interval[0], right_interval[0])
    end = min(left_interval[1], right_interval[1])
    if end + gap_s < start:
        return None
    return start, end


def _window_interval(window: ThreatWindow | None) -> tuple[float, float] | None:
    if window is None or window.prediction_basis is PredictionBasis.UNAVAILABLE:
        return None
    if window.completeness != "FULL":
        return None
    if window.entry_time_s is None:
        return None
    end = window.exit_time_s if window.exit_time_s is not None else window.horizon_end_s
    if end is None or end < window.entry_time_s:
        return None
    return float(window.entry_time_s), float(end)


def _window_document(window: ThreatWindow | None) -> object:
    if window is None:
        return None
    return {
        "entry_time_s": window.entry_time_s,
        "peak_time_s": window.peak_time_s,
        "exit_time_s": window.exit_time_s,
        "horizon_end_s": window.horizon_end_s,
        "prediction_basis": window.prediction_basis.value,
        "completeness": window.completeness,
    }


def _ownship_domain_trace(
    ownship: OwnshipThreatPrediction | None,
    target: ThreatPrediction,
    uncertainty_radius_m: float,
    profile: ShipDomainProfile,
    *,
    comparison_time_s: float,
) -> dict[str, object] | None:
    if ownship is None or not profile.qualified:
        return None
    target_absolute_times = comparison_time_s + np.asarray(target.times_s, dtype=float)
    ownship_absolute_times = ownship.reference_time_s + ownship.times_s
    if (
        target_absolute_times[0] < ownship_absolute_times[0] - 1.0e-9
        or target_absolute_times[-1] > ownship_absolute_times[-1] + 1.0e-9
    ):
        return None
    query = np.asarray(target.times_s, dtype=float)
    own_north = np.interp(target_absolute_times, ownship_absolute_times, ownship.states_enu[:, 0])
    own_east = np.interp(target_absolute_times, ownship_absolute_times, ownship.states_enu[:, 1])
    own_velocity_north = np.interp(target_absolute_times, ownship_absolute_times, ownship.states_enu[:, 2])
    own_velocity_east = np.interp(target_absolute_times, ownship_absolute_times, ownship.states_enu[:, 3])
    if np.any(np.hypot(own_velocity_north, own_velocity_east) <= 1.0e-12):
        return None
    scales: list[float] = []
    for index, state in enumerate(target.states_enu):
        heading = math.atan2(float(own_velocity_east[index]), float(own_velocity_north[index]))
        forward = np.array([math.cos(heading), math.sin(heading)])
        starboard = np.array([math.sin(heading), -math.cos(heading)])
        relative = np.array([state[0] - own_north[index], state[1] - own_east[index]])
        scales.append(
            normalized_domain_scale(
                float(relative @ forward),
                float(relative @ starboard),
                profile,
                uncertainty_radius_m,
            )
        )
    scale_array = np.asarray(scales, dtype=float)
    entry = _first_scale_entry(query, scale_array)
    exit_time = _first_scale_exit(query, scale_array, entry)
    return {
        "times_s": query.tolist(),
        "scales": scale_array.tolist(),
        "min_scale": float(np.min(scale_array)),
        "tdv_s": entry,
        "tde_s": exit_time,
        "domain_violation": bool(np.any(scale_array < 1.0 - 1.0e-9)),
    }


def _first_scale_entry(times: np.ndarray, scales: np.ndarray) -> float | None:
    if scales[0] < 1.0 - 1.0e-9:
        return float(times[0])
    for index in range(1, scales.size):
        if scales[index] < 1.0 - 1.0e-9:
            return _linear_crossing(
                float(times[index - 1]),
                float(times[index]),
                float(scales[index - 1]),
                float(scales[index]),
            )
    return None


def _first_scale_exit(times: np.ndarray, scales: np.ndarray, entry: float | None) -> float | None:
    if entry is None:
        return None
    start = max(1, int(np.searchsorted(times, entry, side="left")))
    for index in range(start, scales.size):
        if scales[index] > 1.0 + 1.0e-9:
            return _linear_crossing(
                float(times[index - 1]),
                float(times[index]),
                float(scales[index - 1]),
                float(scales[index]),
            )
    return None


def _linear_crossing(t0: float, t1: float, scale0: float, scale1: float) -> float:
    if math.isclose(scale0, scale1, abs_tol=1.0e-12):
        return t1
    fraction = (1.0 - scale0) / (scale1 - scale0)
    return t0 + min(max(fraction, 0.0), 1.0) * (t1 - t0)


def _material_plan_worsening(
    baseline: dict[str, object],
    accepted: dict[str, object],
    profile: ConflictGraphProfile,
) -> dict[str, object] | None:
    baseline_violation = bool(baseline["domain_violation"])
    accepted_violation = bool(accepted["domain_violation"])
    baseline_tdv = baseline["tdv_s"]
    accepted_tdv = accepted["tdv_s"]
    new_violation = accepted_violation and not baseline_violation
    earlier_entry = (
        isinstance(baseline_tdv, (int, float))
        and isinstance(accepted_tdv, (int, float))
        and float(baseline_tdv) - float(accepted_tdv) >= profile.material_tdv_advance_s
    )
    scale_delta = float(baseline["min_scale"]) - float(accepted["min_scale"])
    scale_worsening = scale_delta >= profile.material_scale_worsening
    if not (new_violation or earlier_entry or scale_worsening):
        return None
    return {
        "new_domain_violation": new_violation,
        "materially_earlier_tdv": earlier_entry,
        "material_scale_worsening": scale_worsening,
        "baseline_tdv_s": baseline_tdv,
        "accepted_tdv_s": accepted_tdv,
        "baseline_min_scale": baseline["min_scale"],
        "accepted_min_scale": accepted["min_scale"],
        "scale_delta": scale_delta,
    }


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


def _track_key_from_value(value: Any) -> TrackKey:
    if isinstance(value, TrackKey):
        return value
    if isinstance(value, Mapping):
        return TrackKey(int(value["target_id"]), int(value["generation"]))
    if isinstance(value, (tuple, list)) and len(value) == 2:
        return TrackKey(int(value[0]), int(value[1]))
    raise TypeError("track key must be TrackKey or [target_id, generation]")


def _track_key_sort(key: TrackKey) -> tuple[int, int]:
    return key.target_id, key.generation


def _key_document(key: TrackKey) -> list[int]:
    return [key.target_id, key.generation]


def _sha256_json(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()
