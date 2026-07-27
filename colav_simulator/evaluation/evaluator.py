"""Transparent fallback evaluator for COLREG and safety experiments.

This implementation provides the complete data flow and named metrics required
by the simulator. It is intentionally identified as reconstructed and is not
claimed to reproduce the unpublished official evaluator numerically.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from itertools import combinations
from typing import Any

import numpy as np
import seacharts.enc as senc

import colav_simulator.common.map_functions as mapf
from colav_simulator.common.vessel_data import VesselData
from colav_simulator.evaluation.encounter import classify_geometry, stage_timeline, velocity_ne

EVALUATOR_ID = "reconstructed-evaluator-v1"


@dataclass
class PairEvaluation:
    ownship_id: int
    target_id: int
    encounter: str
    initial_dcpa_m: float
    initial_tcpa_s: float
    minimum_distance_m: float
    cpa_time_s: float
    collision: bool
    stages: list[dict[str, Any]]
    metrics: dict[str, float | None]
    warnings: list[str] = field(default_factory=list)


@dataclass
class VesselEvaluation:
    vessel_id: int
    grounding_distance_m: float | None
    grounded: bool | None
    grounding_clearance_score: float | None
    travel_distance_m: float
    duration_s: float


@dataclass
class EvaluatorResult:
    evaluator_id: str
    numerical_reproduction_confirmed: bool
    reproduction_status: str
    pair_results: list[PairEvaluation]
    vessel_results: list[VesselEvaluation]
    aggregate: dict[str, float | int | None]
    warnings: list[str]
    schema_version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _wrap(angle: np.ndarray | float) -> np.ndarray | float:
    return np.arctan2(np.sin(angle), np.cos(angle))


def _velocity(vessel: VesselData) -> np.ndarray:
    return np.vstack((vessel.sog * np.cos(vessel.cog), vessel.sog * np.sin(vessel.cog)))


def _aligned(vessel_a: VesselData, vessel_b: VesselData) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    common, idx_a, idx_b = np.intersect1d(
        vessel_a.timestamps,
        vessel_b.timestamps,
        assume_unique=False,
        return_indices=True,
    )
    return common, idx_a, idx_b


def _initial_cpa(relative_position: np.ndarray, relative_velocity: np.ndarray) -> tuple[float, float]:
    speed_sq = float(np.dot(relative_velocity, relative_velocity))
    if speed_sq < 1e-9:
        return float(np.linalg.norm(relative_position)), 0.0
    tcpa = max(0.0, -float(np.dot(relative_position, relative_velocity)) / speed_sq)
    dcpa = float(np.linalg.norm(relative_position + relative_velocity * tcpa))
    return dcpa, tcpa


def classify_encounter(
    ownship: VesselData,
    target: VesselData,
    own_idx: int,
    target_idx: int,
    initial_dcpa: float,  # noqa: ARG001
    initial_tcpa: float,  # noqa: ARG001
) -> str:
    """Classify one vessel pair using initial CPA and relative geometry."""
    own_position_ne = ownship.xy[::-1, own_idx]
    target_position_ne = target.xy[::-1, target_idx]
    encounter, _, _, _, _ = classify_geometry(
        own_position_ne,
        velocity_ne(float(ownship.sog[own_idx]), float(ownship.cog[own_idx])),
        target_position_ne,
        velocity_ne(float(target.sog[target_idx]), float(target.cog[target_idx])),
        ownship.length,
        target.length,
    )
    return encounter


def _metric_values(
    encounter: str,
    ownship: VesselData,
    indices: np.ndarray,
    times: np.ndarray,
    minimum_distance: float,
    safety_distance: float,
    cpa_index: int,
    initial_tcpa: float,
) -> dict[str, float | None]:
    metrics: dict[str, float | None] = {
        "S8": None,
        "S13": None,
        "S14": None,
        "S15": None,
        "S16": None,
        "S17": None,
        "S_safety": float(np.clip(minimum_distance / safety_distance, 0.0, 1.0)),
        "S_theta": None,
        "S_r": float(np.clip(minimum_distance / (3.0 * safety_distance), 0.0, 1.0)),
        "P_delay": None,
        "P_sts": None,
        "P_nsb": None,
        "P_pt": None,
        "C_x_gw": None,
    }
    course = ownship.cog[indices]
    speed = ownship.sog[indices]
    valid = np.isfinite(course) & np.isfinite(speed)
    if not valid.any():
        return metrics
    course = course[valid]
    speed = speed[valid]
    valid_times = times[valid]
    initial_course = float(course[0])
    course_change = np.asarray(_wrap(course - initial_course))
    starboard_change = max(0.0, float(np.nanmax(course_change)))
    port_change = max(0.0, -float(np.nanmin(course_change)))
    course_step = np.abs(np.asarray(_wrap(np.diff(course)))) if course.size > 1 else np.zeros(1)
    metrics["S_theta"] = float(np.clip(1.0 - np.nanpercentile(course_step, 95) / np.deg2rad(10.0), 0.0, 1.0))
    nominal_speed = max(float(speed[0]), 1e-6)
    metrics["P_delay"] = float(np.clip(1.0 - np.nanmean(speed) / nominal_speed, 0.0, 1.0))
    maneuver_mask = (np.abs(course_change) >= np.deg2rad(5.0)) | (np.abs(speed - speed[0]) >= 0.1 * nominal_speed)
    maneuver_time = float(valid_times[np.argmax(maneuver_mask)]) if maneuver_mask.any() else None
    early_score = (
        float(np.clip(1.0 - maneuver_time / max(initial_tcpa, 1.0), 0.0, 1.0)) if maneuver_time is not None else 0.0
    )
    substantial = float(np.clip(starboard_change / np.deg2rad(15.0), 0.0, 1.0))
    substantial_any = float(np.clip(max(starboard_change, port_change) / np.deg2rad(15.0), 0.0, 1.0))
    if encounter in {"head_on", "crossing_give_way", "overtaking"}:
        metrics["S8"] = float(np.sqrt(substantial_any * early_score))
    if encounter == "head_on":
        metrics["S14"] = substantial
        metrics["S16"] = early_score
        metrics["P_sts"] = float(np.clip(port_change / np.deg2rad(15.0), 0.0, 1.0))
        metrics["P_nsb"] = 1.0 if max(starboard_change, port_change) < np.deg2rad(5.0) else 0.0
    elif encounter == "crossing_give_way":
        metrics["S15"] = substantial
        metrics["S16"] = early_score
        metrics["P_nsb"] = 1.0 if max(starboard_change, port_change) < np.deg2rad(5.0) else 0.0
        metrics["C_x_gw"] = float(np.clip(port_change / np.deg2rad(15.0), 0.0, 1.0))
    elif encounter == "crossing_stand_on":
        pre_cpa = course_change[: max(cpa_index, 1)]
        early_change = float(np.nanmax(np.abs(pre_cpa))) if pre_cpa.size else 0.0
        metrics["S15"] = 1.0
        metrics["S17"] = float(np.clip(1.0 - early_change / np.deg2rad(10.0), 0.0, 1.0))
        metrics["P_pt"] = float(np.clip(early_change / np.deg2rad(15.0), 0.0, 1.0))
    elif encounter == "overtaking":
        metrics["S13"] = max(substantial_any, early_score)
        metrics["S16"] = early_score
    return metrics


class Evaluator:
    """Evaluate vessel trajectories through a stable public interface."""

    evaluator_id = EVALUATOR_ID

    def evaluate(self, vessels: list[VesselData], enc: senc.ENC | None = None) -> EvaluatorResult:
        warnings = [
            "Official evaluator source was unavailable; metrics are reconstructed.",
            "Numerical reproduction of paper tables is not confirmed.",
        ]
        pair_results: list[PairEvaluation] = []
        for ownship, target in combinations(vessels, 2):
            times, own_indices, target_indices = _aligned(ownship, target)
            if times.size == 0:
                warnings.append(f"No overlapping samples for vessels {ownship.id} and {target.id}")
                continue
            own_positions = ownship.xy[:, own_indices]
            target_positions = target.xy[:, target_indices]
            finite = np.all(np.isfinite(own_positions), axis=0) & np.all(np.isfinite(target_positions), axis=0)
            if not finite.any():
                warnings.append(f"No finite positions for vessels {ownship.id} and {target.id}")
                continue
            times = times[finite]
            own_indices = own_indices[finite]
            target_indices = target_indices[finite]
            relative = target_positions[:, finite] - own_positions[:, finite]
            distance = np.linalg.norm(relative, axis=0)
            cpa_index = int(np.nanargmin(distance))
            own_velocity = _velocity(ownship)[:, own_indices[0]]
            target_velocity = _velocity(target)[:, target_indices[0]]
            initial_dcpa, initial_tcpa = _initial_cpa(relative[::-1, 0], target_velocity - own_velocity)
            encounter = classify_encounter(
                ownship,
                target,
                int(own_indices[0]),
                int(target_indices[0]),
                initial_dcpa,
                initial_tcpa,
            )
            safety_distance = max(ownship.length + target.length, 1.0)
            minimum_distance = float(distance[cpa_index])
            metrics = _metric_values(
                encounter,
                ownship,
                own_indices,
                times,
                minimum_distance,
                safety_distance,
                cpa_index,
                initial_tcpa,
            )
            pair_results.append(
                PairEvaluation(
                    ownship_id=ownship.id,
                    target_id=target.id,
                    encounter=encounter,
                    initial_dcpa_m=initial_dcpa,
                    initial_tcpa_s=initial_tcpa,
                    minimum_distance_m=minimum_distance,
                    cpa_time_s=float(times[cpa_index]),
                    collision=minimum_distance <= 0.5 * (ownship.length + target.length),
                    stages=stage_timeline(times, distance, cpa_index, safety_distance),
                    metrics=metrics,
                )
            )

        vessel_results = [self._evaluate_vessel(vessel, enc) for vessel in vessels]
        metric_values: dict[str, list[float]] = {}
        for result in pair_results:
            for name, value in result.metrics.items():
                if value is not None and np.isfinite(value):
                    metric_values.setdefault(name, []).append(float(value))
        aggregate: dict[str, float | int | None] = {
            "pair_count": len(pair_results),
            "collision_count": sum(result.collision for result in pair_results),
            "grounding_count": sum(result.grounded is True for result in vessel_results),
            "grounding_clearance_score": _mean_optional(result.grounding_clearance_score for result in vessel_results),
        }
        aggregate.update({name: float(np.mean(values)) for name, values in metric_values.items()})
        return EvaluatorResult(
            evaluator_id=self.evaluator_id,
            numerical_reproduction_confirmed=False,
            reproduction_status="functional_reproduction",
            pair_results=pair_results,
            vessel_results=vessel_results,
            aggregate=aggregate,
            warnings=warnings,
        )

    @staticmethod
    def _evaluate_vessel(vessel: VesselData, enc: senc.ENC | None) -> VesselEvaluation:
        duration = (
            float(vessel.timestamps[vessel.last_valid_idx] - vessel.timestamps[vessel.first_valid_idx])
            if len(vessel.timestamps) and vessel.first_valid_idx >= 0
            else 0.0
        )
        grounding_distance: float | None = None
        grounded: bool | None = None
        grounding_clearance_score: float | None = None
        if enc is not None and vessel.xy.size and vessel.first_valid_idx >= 0:
            try:
                vessel.min_depth = mapf.find_minimum_depth(vessel.draft, enc)
                vessel.compute_closest_grounding_dist(enc)
                grounding_distance = float(vessel.grounding_dist)
                grounded = grounding_distance <= vessel.length / 2.0
                grounding_clearance_score = float(np.clip(grounding_distance / max(vessel.length, 1.0), 0.0, 1.0))
            except Exception:
                grounding_distance = None
                grounded = None
                grounding_clearance_score = None
        return VesselEvaluation(
            vessel_id=vessel.id,
            grounding_distance_m=grounding_distance,
            grounded=grounded,
            grounding_clearance_score=grounding_clearance_score,
            travel_distance_m=float(vessel.travel_dist),
            duration_s=duration,
        )


def _mean_optional(values: Any) -> float | None:
    finite = [float(value) for value in values if value is not None and np.isfinite(value)]
    return float(np.mean(finite)) if finite else None
