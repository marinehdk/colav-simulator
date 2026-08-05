"""Traceable three-layer COLREG and safety evaluator."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from itertools import combinations
from typing import Any

import numpy as np
import seacharts.enc as senc

import colav_simulator.common.map_functions as mapf
from colav_simulator.common.vessel_data import VesselData
from colav_simulator.core.collision import (
    C2A_ORACLE_ID,
    TOCResult,
    VesselPose,
    c2a_first_contact,
    c2a_grounding_first_contact,
    rectangular_footprint,
)
from colav_simulator.evaluation.colreg_fsm import EncounterObservation, PairwiseColregFSM
from colav_simulator.evaluation.encounter import (
    classify_geometry,
    instantaneous_cpa,
    paper_stage_timeline,
    trajectory_cpa,
    velocity_ne,
    wrap_angle,
)
from colav_simulator.evaluation.profiles import (
    DEFAULT_EVALUATOR_PROFILE_ID,
    FORMULA_SET_ID,
    EvaluatorProfile,
    load_evaluator_profile,
)
from colav_simulator.evaluation.scoring import MetricEvidence, score_pair

EVALUATOR_ID = "behavior-compatible-evaluator-v2"
EVALUATION_SCHEMA_VERSION = "2.0"


class GateOutcome(StrEnum):
    PASS = "PASS"
    SOFT = "SOFT"
    FAIL = "FAIL"


class CheckOutcome(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_EVALUATED = "NOT_EVALUATED"


@dataclass(frozen=True)
class HardGateCheck:
    check_id: str
    outcome: CheckOutcome
    reason: str
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class HardGateLayer:
    outcome: GateOutcome
    checks: list[HardGateCheck]


@dataclass
class PairEvaluation:
    ownship_id: int
    target_id: int
    encounter: str
    target_encounter: str
    initial_dcpa_m: float
    initial_tcpa_s: float
    initial_signed_tcpa_s: float
    minimum_distance_m: float
    minimum_hull_clearance_m: float
    cpa_time_s: float
    collision: bool
    collision_toc_s: float | None
    collision_bracket_s: tuple[float, float] | None
    collision_oracle_id: str
    stages: list[dict[str, Any]]
    fsm_transitions: list[dict[str, Any]]
    metrics: dict[str, float | None]
    target_metrics: dict[str, float | None]
    metric_evidence: dict[str, dict[str, Any]]
    target_metric_evidence: dict[str, dict[str, Any]]
    initial_cpa: dict[str, Any]
    actual_cpa: dict[str, Any]
    warnings: list[str] = field(default_factory=list)


@dataclass
class VesselEvaluation:
    vessel_id: int
    grounding_distance_m: float | None
    grounded: bool | None
    grounding_toc_s: float | None
    grounding_status: str
    grounding_clearance_score: float | None
    travel_distance_m: float
    duration_s: float
    grounding_evidence: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


@dataclass
class EvaluatorResult:
    evaluator_id: str
    evaluator_profile_id: str
    evaluator_profile_hash: str
    formula_set_id: str
    formula_set_hash: str
    collision_oracle_id: str
    numerical_reproduction_confirmed: bool
    reproduction_status: str
    evaluation_status: str
    hard_gate: HardGateLayer
    scores: dict[str, Any]
    diagnostics: dict[str, Any]
    evidence: dict[str, Any]
    pair_results: list[PairEvaluation]
    vessel_results: list[VesselEvaluation]
    aggregate: dict[str, float | int | None]
    warnings: list[str]
    schema_version: str = EVALUATION_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Evaluator:
    """Behavior-compatible façade with explicit profile and evidence identity."""

    evaluator_id = EVALUATOR_ID

    def __init__(self, profile: str | EvaluatorProfile = DEFAULT_EVALUATOR_PROFILE_ID) -> None:
        self.profile = load_evaluator_profile(profile) if isinstance(profile, str) else profile
        self._enc: senc.ENC | None = None
        self._vessels: list[VesselData] | None = None
        self._last_result: EvaluatorResult | None = None

    def set_enc(self, enc: senc.ENC | None) -> None:
        self._enc = enc

    def set_vessel_data(self, vessels: list[VesselData]) -> None:
        self._vessels = vessels

    def evaluate(
        self,
        vessels: list[VesselData] | None = None,
        enc: senc.ENC | None = None,
        *,
        execution_context: dict[str, Any] | None = None,
    ) -> EvaluatorResult:
        vessels = vessels if vessels is not None else self._vessels
        enc = enc if enc is not None else self._enc
        if vessels is None:
            raise ValueError("Evaluator requires vessel data")
        self._vessels = vessels
        self._enc = enc
        context = execution_context or {}
        warnings = [
            "Original evaluator source unavailable; this is a behavior-compatible reconstruction.",
            "Only cells with complete published inputs may be marked numerically verified.",
        ]
        warnings.extend(self.profile.reconstruction_assumptions)
        vessel_pairs = list(combinations(vessels, 2))
        if context.get("stress_only"):
            vessel_pairs = _stress_pair_candidates(vessel_pairs)
            warnings.append(
                "Stress-only evaluation uses a conservative center-distance broad phase; "
                "full pair scoring remains NOT_EVALUATED.",
            )
        pair_results: list[PairEvaluation] = []
        for ownship, target in vessel_pairs:
            pair = self._evaluate_pair(ownship, target)
            if pair is None:
                warnings.append(f"No synchronized finite samples for vessels {ownship.id} and {target.id}")
            else:
                pair_results.append(pair)
        vessel_results = [self._evaluate_vessel(vessel, enc) for vessel in vessels]
        for vessel_result in vessel_results:
            warnings.extend(vessel_result.warnings)
        aggregate = _aggregate(pair_results, vessel_results)
        hard_gate = _hard_gate(pair_results, vessel_results, context)
        evaluated_pairs = len(pair_results)
        expected_pairs = len(vessels) * (len(vessels) - 1) // 2
        evaluation_status = "COMPLETE" if evaluated_pairs == expected_pairs else "PARTIAL"
        score_layer = {
            "status": evaluation_status,
            "profile_id": self.profile.profile_id,
            "profile_hash": self.profile.profile_hash,
            "formula_set_id": FORMULA_SET_ID,
            "pair_count": evaluated_pairs,
            "aggregate": aggregate,
        }
        diagnostics = {
            "task": {
                "pair_count": evaluated_pairs,
                "collision_count": aggregate["collision_count"],
                "grounding_count": aggregate["grounding_count"],
            },
            "execution": {
                "requested_algorithm": context.get("requested_algorithm"),
                "executed_algorithm": context.get("executed_algorithm"),
                "fallback_used": bool(context.get("fallback_used", False)),
                "run_completed": bool(context.get("run_completed", True)),
            },
            "solver": context.get("solver", {"status": "NOT_AVAILABLE"}),
        }
        result = EvaluatorResult(
            evaluator_id=self.evaluator_id,
            evaluator_profile_id=self.profile.profile_id,
            evaluator_profile_hash=self.profile.profile_hash,
            formula_set_id=FORMULA_SET_ID,
            formula_set_hash=hashlib.sha256(FORMULA_SET_ID.encode("utf-8")).hexdigest(),
            collision_oracle_id=C2A_ORACLE_ID,
            numerical_reproduction_confirmed=False,
            reproduction_status="behavior_compatible_reconstruction",
            evaluation_status=evaluation_status,
            hard_gate=hard_gate,
            scores=score_layer,
            diagnostics=diagnostics,
            evidence={
                "source_refs": list(self.profile.source_refs),
                "reconstruction_assumptions": list(self.profile.reconstruction_assumptions),
                "grounding_policy_id": "chart-geometric-footprint-v1",
                "grounding_compensation_status": "NOT_EVALUATED",
                "operational_ukc_status": "NOT_EVALUATED",
            },
            pair_results=pair_results,
            vessel_results=vessel_results,
            aggregate=aggregate,
            warnings=warnings,
        )
        self._last_result = result
        return result

    def print_vessel_scores(self, vessel_id: int = 0) -> None:
        if self._last_result is None:
            raise RuntimeError("evaluate() must be called before print_vessel_scores()")
        for pair in self._last_result.pair_results:
            if pair.ownship_id == vessel_id:
                print(f"{pair.ownship_id}->{pair.target_id}: {pair.metrics}")
            elif pair.target_id == vessel_id:
                print(f"{pair.target_id}->{pair.ownship_id}: {pair.target_metrics}")

    def _evaluate_pair(self, ownship: VesselData, target: VesselData) -> PairEvaluation | None:
        times, own_indices, target_indices = _aligned(ownship, target)
        if times.size == 0:
            return None
        own_positions_en = ownship.xy[:, own_indices]
        target_positions_en = target.xy[:, target_indices]
        finite = (
            np.isfinite(times)
            & np.all(np.isfinite(own_positions_en), axis=0)
            & np.all(np.isfinite(target_positions_en), axis=0)
            & np.isfinite(ownship.sog[own_indices])
            & np.isfinite(target.sog[target_indices])
            & np.isfinite(ownship.cog[own_indices])
            & np.isfinite(target.cog[target_indices])
        )
        if not finite.any():
            return None
        times = times[finite]
        own_indices = own_indices[finite]
        target_indices = target_indices[finite]
        own_positions_en = own_positions_en[:, finite]
        target_positions_en = target_positions_en[:, finite]
        own_positions_ne = own_positions_en[::-1]
        target_positions_ne = target_positions_en[::-1]
        relative_ne = target_positions_ne - own_positions_ne
        distance = np.linalg.norm(relative_ne, axis=0)
        minimum_hull_clearance = (
            _minimum_continuous_distance(relative_ne)
            - _circumscribed_radius(ownship)
            - _circumscribed_radius(target)
        )
        actual_cpa = trajectory_cpa(own_positions_ne, target_positions_ne, times)
        cpa_index = int(np.argmin(distance))
        own_velocities = _velocities(ownship, own_indices)
        target_velocities = _velocities(target, target_indices)
        initial_cpa = instantaneous_cpa(relative_ne[:, 0], target_velocities[:, 0] - own_velocities[:, 0])
        signed_tcpa = np.array(
            [
                instantaneous_cpa(
                    relative_ne[:, index],
                    target_velocities[:, index] - own_velocities[:, index],
                ).tcpa_signed_s
                for index in range(times.size)
            ],
            dtype=float,
        )
        stage_values = _paper_stage_values(distance, signed_tcpa, self.profile)
        stages = paper_stage_timeline(times, distance, signed_tcpa, self.profile)
        entry_candidates = np.flatnonzero(stage_values >= 2)
        entry_index = int(entry_candidates[0]) if entry_candidates.size else 0
        encounter = _classify_at(ownship, target, own_indices, target_indices, entry_index, self.profile)
        target_encounter = _classify_at(target, ownship, target_indices, own_indices, entry_index, self.profile)
        own_fsm = _run_fsm(
            ownship,
            target,
            times,
            own_indices,
            target_indices,
            distance,
            signed_tcpa,
            stage_values,
            self.profile,
        )
        target_fsm = _run_fsm(
            target,
            ownship,
            times,
            target_indices,
            own_indices,
            distance,
            signed_tcpa,
            stage_values,
            self.profile,
        )
        own_alpha, own_beta = _pose_angles(
            own_positions_ne[:, cpa_index],
            target_positions_ne[:, cpa_index],
            float(ownship.cog[own_indices[cpa_index]]),
            float(target.cog[target_indices[cpa_index]]),
        )
        target_alpha, target_beta = _pose_angles(
            target_positions_ne[:, cpa_index],
            own_positions_ne[:, cpa_index],
            float(target.cog[target_indices[cpa_index]]),
            float(ownship.cog[own_indices[cpa_index]]),
        )
        metrics, evidence = score_pair(
            encounter=encounter,
            courses_rad=ownship.cog[own_indices],
            speeds_mps=ownship.sog[own_indices],
            distances_m=distance,
            stages=stage_values,
            cpa_index=cpa_index,
            contact_angle_rad=own_alpha,
            relative_bearing_rad=own_beta,
            profile=self.profile,
            ownship_length_m=ownship.length,
        )
        target_metrics, target_evidence = score_pair(
            encounter=target_encounter,
            courses_rad=target.cog[target_indices],
            speeds_mps=target.sog[target_indices],
            distances_m=distance,
            stages=stage_values,
            cpa_index=cpa_index,
            contact_angle_rad=target_alpha,
            relative_bearing_rad=target_beta,
            profile=self.profile,
            ownship_length_m=target.length,
        )
        collision = _pair_first_contact(ownship, target, times, own_indices, target_indices)
        transitions = [item.to_dict() for item in own_fsm.transitions]
        transitions.extend(
            {"perspective": "target", **item.to_dict()}
            for item in target_fsm.transitions
        )
        return PairEvaluation(
            ownship_id=ownship.id,
            target_id=target.id,
            encounter=encounter,
            target_encounter=target_encounter,
            initial_dcpa_m=initial_cpa.dcpa_m,
            initial_tcpa_s=initial_cpa.tcpa_forward_s,
            initial_signed_tcpa_s=initial_cpa.tcpa_signed_s,
            minimum_distance_m=float(distance[cpa_index]),
            minimum_hull_clearance_m=minimum_hull_clearance,
            cpa_time_s=float(times[cpa_index]),
            collision=collision.collided,
            collision_toc_s=collision.toc_s,
            collision_bracket_s=collision.bracket_s,
            collision_oracle_id=collision.oracle_id,
            stages=stages,
            fsm_transitions=transitions,
            metrics=metrics,
            target_metrics=target_metrics,
            metric_evidence=_evidence_dict(evidence),
            target_metric_evidence=_evidence_dict(target_evidence),
            initial_cpa=initial_cpa.to_dict(),
            actual_cpa=actual_cpa.to_dict(),
        )

    @staticmethod
    def _evaluate_vessel(vessel: VesselData, enc: senc.ENC | None) -> VesselEvaluation:
        duration = (
            float(vessel.timestamps[vessel.last_valid_idx] - vessel.timestamps[vessel.first_valid_idx])
            if len(vessel.timestamps) and vessel.first_valid_idx >= 0
            else 0.0
        )
        if enc is None:
            return VesselEvaluation(
                vessel_id=vessel.id,
                grounding_distance_m=None,
                grounded=None,
                grounding_toc_s=None,
                grounding_status="NOT_EVALUATED_NO_ENC",
                grounding_clearance_score=None,
                travel_distance_m=float(vessel.travel_dist),
                duration_s=duration,
                grounding_evidence={"enc_status": "NOT_PROVIDED"},
            )
        try:
            vessel.min_depth = mapf.find_minimum_depth(vessel.draft, enc)
            hazard_set = mapf.extract_typed_grounding_hazards(vessel.min_depth, enc)
            hazard = hazard_set.combined_geometry
            if hazard.is_empty:
                raise ValueError("ENC produced no physical grounding hazard geometry")
            valid = np.flatnonzero(
                np.all(np.isfinite(vessel.xy), axis=0)
                & np.isfinite(vessel.cog)
                & np.isfinite(vessel.timestamps)
            )
            if valid.size == 0:
                raise ValueError("vessel has no finite grounding samples")
            minimum_distance = float("inf")
            first_contact: TOCResult | None = None
            for index in valid:
                pose = _vessel_pose(vessel, int(index))
                minimum_distance = min(minimum_distance, rectangular_footprint(pose).distance(hazard))
            for left, right in zip(valid[:-1], valid[1:], strict=True):
                contact = c2a_grounding_first_contact(
                    _vessel_pose(vessel, int(left)),
                    _vessel_pose(vessel, int(right)),
                    hazard,
                    interval_start_s=float(vessel.timestamps[left]),
                    interval_end_s=float(vessel.timestamps[right]),
                )
                if contact.collided:
                    first_contact = contact
                    break
            if valid.size == 1 and rectangular_footprint(_vessel_pose(vessel, int(valid[0]))).intersects(hazard):
                first_contact = c2a_grounding_first_contact(
                    _vessel_pose(vessel, int(valid[0])),
                    _vessel_pose(vessel, int(valid[0])),
                    hazard,
                    interval_start_s=float(vessel.timestamps[valid[0]]),
                    interval_end_s=float(vessel.timestamps[valid[0]]) + 1e-6,
                )
            grounded = first_contact is not None and first_contact.collided
            return VesselEvaluation(
                vessel_id=vessel.id,
                grounding_distance_m=minimum_distance,
                grounded=grounded,
                grounding_toc_s=first_contact.toc_s if first_contact else None,
                grounding_status="EVALUATED",
                grounding_clearance_score=float(np.clip(minimum_distance / max(vessel.length, 1.0), 0.0, 1.0)),
                travel_distance_m=float(vessel.travel_dist),
                duration_s=duration,
                grounding_evidence=hazard_set.evidence(),
            )
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            return VesselEvaluation(
                vessel_id=vessel.id,
                grounding_distance_m=None,
                grounded=None,
                grounding_toc_s=None,
                grounding_status="NOT_EVALUATED_INVALID_ENC",
                grounding_clearance_score=None,
                travel_distance_m=float(vessel.travel_dist),
                duration_s=duration,
                grounding_evidence={"error": str(exc)},
                warnings=[f"Grounding evaluation unavailable for vessel {vessel.id}: {exc}"],
            )


def _aligned(vessel_a: VesselData, vessel_b: VesselData) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    common, idx_a, idx_b = np.intersect1d(
        vessel_a.timestamps,
        vessel_b.timestamps,
        assume_unique=False,
        return_indices=True,
    )
    return common, idx_a, idx_b


def _velocities(vessel: VesselData, indices: np.ndarray) -> np.ndarray:
    return np.vstack(
        (
            vessel.sog[indices] * np.cos(vessel.cog[indices]),
            vessel.sog[indices] * np.sin(vessel.cog[indices]),
        )
    )


def _classify_at(
    ownship: VesselData,
    target: VesselData,
    own_indices: np.ndarray,
    target_indices: np.ndarray,
    index: int,
    profile: EvaluatorProfile,
) -> str:
    encounter, _, _, _, _ = classify_geometry(
        ownship.xy[::-1, own_indices[index]],
        velocity_ne(float(ownship.sog[own_indices[index]]), float(ownship.cog[own_indices[index]])),
        target.xy[::-1, target_indices[index]],
        velocity_ne(float(target.sog[target_indices[index]]), float(target.cog[target_indices[index]])),
        ownship.length,
        target.length,
        profile=profile,
    )
    return encounter


def _paper_stage_values(distance: np.ndarray, signed_tcpa: np.ndarray, profile: EvaluatorProfile) -> np.ndarray:
    stages = np.ones(distance.size, dtype=int)
    approaching = signed_tcpa > 0.0
    stages[approaching & (distance <= profile.stages.stage2_entry_m)] = 2
    stages[approaching & (distance <= profile.stages.stage3_entry_m)] = 3
    stages[approaching & (distance <= profile.stages.stage4_entry_m)] = 4
    return stages


def _run_fsm(
    ownship: VesselData,
    target: VesselData,
    times: np.ndarray,
    own_indices: np.ndarray,
    target_indices: np.ndarray,
    distance: np.ndarray,
    signed_tcpa: np.ndarray,
    stages: np.ndarray,
    profile: EvaluatorProfile,
) -> PairwiseColregFSM:
    fsm = PairwiseColregFSM(profile)
    for index, time_s in enumerate(times):
        encounter, dcpa_m, _, _, bearing = classify_geometry(
            ownship.xy[::-1, own_indices[index]],
            velocity_ne(float(ownship.sog[own_indices[index]]), float(ownship.cog[own_indices[index]])),
            target.xy[::-1, target_indices[index]],
            velocity_ne(float(target.sog[target_indices[index]]), float(target.cog[target_indices[index]])),
            ownship.length,
            target.length,
            profile=profile,
        )
        alpha, _ = _pose_angles(
            ownship.xy[::-1, own_indices[index]],
            target.xy[::-1, target_indices[index]],
            float(ownship.cog[own_indices[index]]),
            float(target.cog[target_indices[index]]),
        )
        fsm.update(
            EncounterObservation(
                time_s=float(time_s),
                encounter=encounter,
                stage=int(stages[index]),
                range_m=float(distance[index]),
                dcpa_m=dcpa_m,
                signed_tcpa_s=float(signed_tcpa[index]),
                relative_bearing_deg=bearing,
                contact_angle_deg=float(np.rad2deg(alpha)),
            )
        )
    return fsm


def _pose_angles(
    own_position_ne: np.ndarray,
    target_position_ne: np.ndarray,
    own_course_rad: float,
    target_course_rad: float,
) -> tuple[float, float]:
    relative = np.asarray(target_position_ne) - np.asarray(own_position_ne)
    los_own_to_target = float(np.arctan2(relative[1], relative[0]))
    los_target_to_own = float(wrap_angle(los_own_to_target + np.pi))
    contact_angle = float(wrap_angle(los_target_to_own - target_course_rad))
    relative_bearing = float((los_own_to_target - own_course_rad) % (2.0 * np.pi))
    return contact_angle, relative_bearing


def _pair_first_contact(
    ownship: VesselData,
    target: VesselData,
    times: np.ndarray,
    own_indices: np.ndarray,
    target_indices: np.ndarray,
) -> TOCResult:
    if times.size == 1:
        own_pose = _vessel_pose(ownship, int(own_indices[0]))
        target_pose = _vessel_pose(target, int(target_indices[0]))
        return c2a_first_contact(
            own_pose,
            own_pose,
            target_pose,
            target_pose,
            interval_start_s=float(times[0]),
            interval_end_s=float(times[0]) + 1e-6,
        )
    last_result: TOCResult | None = None
    for index in range(times.size - 1):
        result = c2a_first_contact(
            _vessel_pose(ownship, int(own_indices[index])),
            _vessel_pose(ownship, int(own_indices[index + 1])),
            _vessel_pose(target, int(target_indices[index])),
            _vessel_pose(target, int(target_indices[index + 1])),
            interval_start_s=float(times[index]),
            interval_end_s=float(times[index + 1]),
        )
        last_result = result
        if result.collided:
            return result
    if last_result is None:
        raise RuntimeError("C2A pair evaluation produced no interval result")
    return last_result


def _vessel_pose(vessel: VesselData, index: int) -> VesselPose:
    return VesselPose(
        north_m=float(vessel.xy[1, index]),
        east_m=float(vessel.xy[0, index]),
        heading_rad=float(vessel.cog[index]),
        length_m=float(vessel.length),
        width_m=float(vessel.width),
    )


def _evidence_dict(evidence: dict[str, MetricEvidence]) -> dict[str, dict[str, Any]]:
    return {name: value.to_dict() for name, value in evidence.items()}


def _stress_pair_candidates(
    vessel_pairs: list[tuple[VesselData, VesselData]],
) -> list[tuple[VesselData, VesselData]]:
    candidates: list[tuple[VesselData, VesselData]] = []
    nearest_pair: tuple[VesselData, VesselData] | None = None
    nearest_distance = np.inf
    for ownship, target in vessel_pairs:
        _, own_indices, target_indices = _aligned(ownship, target)
        if own_indices.size == 0:
            continue
        own_positions = ownship.xy[:, own_indices]
        target_positions = target.xy[:, target_indices]
        finite = np.all(np.isfinite(own_positions), axis=0) & np.all(np.isfinite(target_positions), axis=0)
        if not finite.any():
            continue
        own_positions = own_positions[:, finite]
        target_positions = target_positions[:, finite]
        minimum_distance = float(np.min(np.linalg.norm(target_positions - own_positions, axis=0)))
        if minimum_distance < nearest_distance:
            nearest_distance = minimum_distance
            nearest_pair = (ownship, target)

        own_step = (
            float(np.max(np.linalg.norm(np.diff(own_positions, axis=1), axis=0)))
            if own_positions.shape[1] > 1
            else 0.0
        )
        target_step = (
            float(np.max(np.linalg.norm(np.diff(target_positions, axis=1), axis=0)))
            if target_positions.shape[1] > 1
            else 0.0
        )
        footprint_radius = 0.5 * (
            float(np.hypot(ownship.length, ownship.width))
            + float(np.hypot(target.length, target.width))
        )
        if minimum_distance <= footprint_radius + own_step + target_step:
            candidates.append((ownship, target))
    if nearest_pair is not None and not any(
        ownship is nearest_pair[0] and target is nearest_pair[1] for ownship, target in candidates
    ):
        candidates.append(nearest_pair)
    return candidates


def _aggregate(
    pair_results: list[PairEvaluation],
    vessel_results: list[VesselEvaluation],
) -> dict[str, float | int | None]:
    metric_values: dict[str, list[float]] = {}
    for result in pair_results:
        for values in (result.metrics, result.target_metrics):
            for name, value in values.items():
                if value is not None and np.isfinite(value):
                    metric_values.setdefault(name, []).append(float(value))
    ownship_collisions = sum(
        result.collision and 0 in {result.ownship_id, result.target_id}
        for result in pair_results
    )
    global_collisions = sum(result.collision for result in pair_results)
    ownship_groundings = sum(result.grounded is True and result.vessel_id == 0 for result in vessel_results)
    global_groundings = sum(result.grounded is True for result in vessel_results)
    ownship_grounding_unknown = sum(
        result.grounded is None and result.vessel_id == 0 for result in vessel_results
    )
    aggregate: dict[str, float | int | None] = {
        "pair_count": len(pair_results),
        "collision_count": ownship_collisions,
        "ownship_collision_count": ownship_collisions,
        "global_collision_count": global_collisions,
        "grounding_count": ownship_groundings,
        "ownship_grounding_count": ownship_groundings,
        "global_grounding_count": global_groundings,
        "grounding_not_evaluated_count": ownship_grounding_unknown,
        "global_grounding_not_evaluated_count": sum(
            result.grounded is None for result in vessel_results
        ),
        "minimum_distance_m": min((result.minimum_distance_m for result in pair_results), default=None),
        "grounding_clearance_score": _mean_optional(
            result.grounding_clearance_score for result in vessel_results
        ),
    }
    aggregate.update({name: float(np.mean(values)) for name, values in metric_values.items()})
    return aggregate


def _hard_gate(
    pair_results: list[PairEvaluation],
    vessel_results: list[VesselEvaluation],
    context: dict[str, Any],
) -> HardGateLayer:
    collision_count = sum(
        result.collision and 0 in {result.ownship_id, result.target_id}
        for result in pair_results
    )
    global_collision_count = sum(result.collision for result in pair_results)
    grounded_count = sum(
        result.grounded is True and result.vessel_id == 0 for result in vessel_results
    )
    grounding_unknown = sum(
        result.grounded is None and result.vessel_id == 0 for result in vessel_results
    )
    global_grounded_count = sum(result.grounded is True for result in vessel_results)
    global_grounding_unknown = sum(result.grounded is None for result in vessel_results)
    ownship_pairs = [
        result for result in pair_results if 0 in {result.ownship_id, result.target_id}
    ]
    clearance_violations = [
        result for result in ownship_pairs if result.minimum_hull_clearance_m < 50.0
    ]
    fallback = bool(context.get("fallback_used", False))
    completed = bool(context.get("run_completed", True))
    checks = [
        HardGateCheck(
            "physical_collision",
            CheckOutcome.FAIL if collision_count else CheckOutcome.PASS,
            f"{collision_count} Ship0-vs-target physical footprint contacts",
            {
                "oracle_id": C2A_ORACLE_ID,
                "scope": "ship0_vs_target",
                "global_all_vessel_collision_count": global_collision_count,
            },
        ),
        HardGateCheck(
            "minimum_hull_clearance",
            CheckOutcome.FAIL
            if clearance_violations
            else CheckOutcome.PASS
            if ownship_pairs
            else CheckOutcome.NOT_EVALUATED,
            f"{len(clearance_violations)} Ship0-vs-target clearances below 50.0 m",
            {
                "scope": "ship0_vs_target",
                "required_clearance_m": 50.0,
                "minimum_hull_clearance_m": min(
                    (result.minimum_hull_clearance_m for result in ownship_pairs),
                    default=None,
                ),
            },
        ),
        HardGateCheck(
            "physical_grounding",
            CheckOutcome.FAIL
            if grounded_count
            else CheckOutcome.NOT_EVALUATED
            if grounding_unknown
            else CheckOutcome.PASS,
            f"{grounded_count} Ship0 groundings; {grounding_unknown} Ship0 evaluations unavailable",
            {
                "policy_id": "chart-geometric-footprint-v1",
                "scope": "ship0",
                "global_all_vessel_grounding_count": global_grounded_count,
                "global_all_vessel_grounding_not_evaluated_count": global_grounding_unknown,
            },
        ),
        HardGateCheck(
            "fallback_used",
            CheckOutcome.FAIL if fallback else CheckOutcome.PASS,
            "fallback detected" if fallback else "no fallback",
        ),
        HardGateCheck(
            "run_completion",
            CheckOutcome.PASS if completed else CheckOutcome.FAIL,
            "run completed" if completed else "run incomplete",
        ),
    ]
    if any(check.outcome == CheckOutcome.FAIL for check in checks):
        outcome = GateOutcome.FAIL
    elif any(check.outcome == CheckOutcome.NOT_EVALUATED for check in checks):
        outcome = GateOutcome.SOFT
    else:
        outcome = GateOutcome.PASS
    return HardGateLayer(outcome, checks)


def _circumscribed_radius(vessel: VesselData) -> float:
    return 0.5 * float(np.hypot(vessel.length, vessel.width))


def _minimum_continuous_distance(relative_positions: np.ndarray) -> float:
    if relative_positions.shape[1] == 1:
        return float(np.linalg.norm(relative_positions[:, 0]))
    starts = relative_positions[:, :-1].T
    deltas = np.diff(relative_positions, axis=1).T
    lengths_squared = np.einsum("ij,ij->i", deltas, deltas)
    fractions = np.divide(
        -np.einsum("ij,ij->i", starts, deltas),
        lengths_squared,
        out=np.zeros_like(lengths_squared),
        where=lengths_squared > 0.0,
    )
    closest = starts + np.clip(fractions, 0.0, 1.0)[:, None] * deltas
    return float(np.min(np.linalg.norm(closest, axis=1)))


def _mean_optional(values: Any) -> float | None:
    finite = [float(value) for value in values if value is not None and np.isfinite(value)]
    return float(np.mean(finite)) if finite else None
