"""Shared truth-based encounter classification for live monitoring and evaluation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any

import numpy as np

from colav_simulator.evaluation.colreg_fsm import EncounterObservation, PairwiseColregFSM
from colav_simulator.evaluation.profiles import (
    DEFAULT_EVALUATOR_PROFILE_ID,
    EvaluatorProfile,
    load_evaluator_profile,
)


class CPAStatus(StrEnum):
    VALID = "VALID"
    STATIONARY_RELATIVE = "STATIONARY_RELATIVE"
    TRAJECTORY = "TRAJECTORY"


@dataclass(frozen=True)
class CPAResult:
    """CPA output with one signed-time convention across live and evaluation."""

    dcpa_m: float
    tcpa_signed_s: float
    tcpa_forward_s: float
    relative_position_at_cpa_ne_m: tuple[float, float]
    method: str
    status: CPAStatus

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def wrap_angle(angle: float | np.ndarray) -> float | np.ndarray:
    """Wrap radians to the closed interval around zero."""
    return np.arctan2(np.sin(angle), np.cos(angle))


def velocity_ne(speed: float, course_rad: float) -> np.ndarray:
    """Return north/east velocity from maritime course and speed."""
    return np.array([speed * np.cos(course_rad), speed * np.sin(course_rad)], dtype=float)


def cpa(
    relative_position_ne: np.ndarray,
    relative_velocity_ne: np.ndarray,
) -> tuple[float, float, float]:
    """Compatibility wrapper returning DCPA, forward TCPA, and signed TCPA."""
    result = instantaneous_cpa(relative_position_ne, relative_velocity_ne)
    return result.dcpa_m, result.tcpa_forward_s, result.tcpa_signed_s


def instantaneous_cpa(
    relative_position_ne: np.ndarray,
    relative_velocity_ne: np.ndarray,
) -> CPAResult:
    """Return constant-velocity CPA without discarding post-CPA sign."""
    relative_position = np.asarray(relative_position_ne, dtype=float)
    relative_velocity = np.asarray(relative_velocity_ne, dtype=float)
    if relative_position.shape != (2,) or relative_velocity.shape != (2,):
        raise ValueError("CPA inputs must be North/East vectors with shape (2,)")
    if not np.isfinite(relative_position).all() or not np.isfinite(relative_velocity).all():
        raise ValueError("CPA inputs must be finite")
    speed_sq = float(np.dot(relative_velocity_ne, relative_velocity_ne))
    if speed_sq < 1e-9:
        distance = float(np.linalg.norm(relative_position))
        return CPAResult(
            dcpa_m=distance,
            tcpa_signed_s=0.0,
            tcpa_forward_s=0.0,
            relative_position_at_cpa_ne_m=(float(relative_position[0]), float(relative_position[1])),
            method="instantaneous_constant_velocity",
            status=CPAStatus.STATIONARY_RELATIVE,
        )
    signed_tcpa = -float(np.dot(relative_position, relative_velocity)) / speed_sq
    forward_tcpa = max(0.0, signed_tcpa)
    relative_at_cpa = relative_position + relative_velocity * forward_tcpa
    return CPAResult(
        dcpa_m=float(np.linalg.norm(relative_at_cpa)),
        tcpa_signed_s=signed_tcpa,
        tcpa_forward_s=forward_tcpa,
        relative_position_at_cpa_ne_m=(float(relative_at_cpa[0]), float(relative_at_cpa[1])),
        method="instantaneous_constant_velocity",
        status=CPAStatus.VALID,
    )


def trajectory_cpa(
    own_positions_ne: np.ndarray,
    target_positions_ne: np.ndarray,
    times_s: np.ndarray,
) -> CPAResult:
    """Return actual synchronized sampled-trajectory CPA for retrospective scoring."""
    own = np.asarray(own_positions_ne, dtype=float)
    target = np.asarray(target_positions_ne, dtype=float)
    times = np.asarray(times_s, dtype=float)
    if own.shape != target.shape or own.ndim != 2 or own.shape[0] != 2:
        raise ValueError("trajectory CPA positions must share shape (2,N)")
    if times.shape != (own.shape[1],):
        raise ValueError("trajectory CPA timestamps must have shape (N,)")
    finite = np.isfinite(times) & np.all(np.isfinite(own), axis=0) & np.all(np.isfinite(target), axis=0)
    if not finite.any():
        raise ValueError("trajectory CPA requires at least one finite synchronized sample")
    relative = target[:, finite] - own[:, finite]
    finite_times = times[finite]
    index = int(np.argmin(np.linalg.norm(relative, axis=0)))
    relative_at_cpa = relative[:, index]
    time_from_start = float(finite_times[index] - finite_times[0])
    return CPAResult(
        dcpa_m=float(np.linalg.norm(relative_at_cpa)),
        tcpa_signed_s=time_from_start,
        tcpa_forward_s=max(0.0, time_from_start),
        relative_position_at_cpa_ne_m=(float(relative_at_cpa[0]), float(relative_at_cpa[1])),
        method="synchronized_trajectory",
        status=CPAStatus.TRAJECTORY,
    )


def classify_geometry(
    own_position_ne: np.ndarray,
    own_velocity_ne: np.ndarray,
    target_position_ne: np.ndarray,
    target_velocity_ne: np.ndarray,
    own_length_m: float,
    target_length_m: float,
    *,
    profile: EvaluatorProfile | None = None,
) -> tuple[str, float, float, float, float]:
    """Classify one pair and return encounter, DCPA, TCPA, signed TCPA, bearing."""
    relative = np.asarray(target_position_ne, dtype=float) - np.asarray(own_position_ne, dtype=float)
    relative_velocity = np.asarray(target_velocity_ne, dtype=float) - np.asarray(own_velocity_ne, dtype=float)
    cpa_result = instantaneous_cpa(relative, relative_velocity)
    dcpa_m = cpa_result.dcpa_m
    tcpa_s = cpa_result.tcpa_forward_s
    signed_tcpa_s = cpa_result.tcpa_signed_s
    own_course = float(np.arctan2(own_velocity_ne[1], own_velocity_ne[0]))
    target_course = float(np.arctan2(target_velocity_ne[1], target_velocity_ne[0]))
    absolute_bearing = float(np.arctan2(relative[1], relative[0]))
    relative_bearing_deg = float(np.rad2deg(wrap_angle(absolute_bearing - own_course)))
    contact_bearing_deg = float(np.rad2deg(wrap_angle(absolute_bearing + np.pi - target_course)))
    course_difference_deg = abs(float(np.rad2deg(wrap_angle(target_course - own_course))))
    own_speed = float(np.linalg.norm(own_velocity_ne))
    target_speed = float(np.linalg.norm(target_velocity_ne))
    head_on_angle = profile.encounter.alpha_crit_14_deg if profile else 15.0
    crossing_angle = profile.encounter.alpha_crit_15_deg if profile else 0.0
    overtaking_contact_angle = profile.encounter.alpha_crit_13_deg if profile else 45.0
    overtaking_angle = profile.encounter.overtaking_min_deg if profile else 112.5
    risk_distance = profile.stages.stage2_entry_m if profile else max(500.0, 10.0 * (own_length_m + target_length_m))
    if signed_tcpa_s <= 0.0 or dcpa_m > risk_distance:
        encounter = "clear"
    elif (
        abs(relative_bearing_deg) <= head_on_angle
        and abs(contact_bearing_deg) <= head_on_angle
        and course_difference_deg >= 180.0 - 2.0 * head_on_angle
    ):
        encounter = "head_on"
    elif (
        abs(contact_bearing_deg) > overtaking_angle
        and abs(relative_bearing_deg) < overtaking_contact_angle
        and own_speed > target_speed
    ):
        encounter = "overtaking"
    elif (
        abs(relative_bearing_deg) > overtaking_angle
        and abs(contact_bearing_deg) < overtaking_contact_angle
        and target_speed > own_speed
    ):
        encounter = "overtaken"
    elif (
        crossing_angle < relative_bearing_deg <= overtaking_angle
        and -overtaking_angle <= contact_bearing_deg < -crossing_angle
    ):
        encounter = "crossing_give_way"
    elif (
        -overtaking_angle <= relative_bearing_deg < -crossing_angle
        and crossing_angle < contact_bearing_deg <= overtaking_angle
    ):
        encounter = "crossing_stand_on"
    else:
        encounter = "clear"
    return encounter, dcpa_m, tcpa_s, signed_tcpa_s, relative_bearing_deg


def paper_stage_timeline(
    times: np.ndarray,
    distance: np.ndarray,
    signed_tcpa: np.ndarray,
    profile: EvaluatorProfile,
) -> list[dict[str, Any]]:
    """Build paper Stage 1-4 transitions from range and signed risk state."""
    times = np.asarray(times, dtype=float)
    distance = np.asarray(distance, dtype=float)
    signed_tcpa = np.asarray(signed_tcpa, dtype=float)
    if not (times.shape == distance.shape == signed_tcpa.shape):
        raise ValueError("stage timeline arrays must share shape")
    stages = np.ones(times.size, dtype=int)
    approaching = signed_tcpa > 0.0
    stages[approaching & (distance <= profile.stages.stage2_entry_m)] = 2
    stages[approaching & (distance <= profile.stages.stage3_entry_m)] = 3
    stages[approaching & (distance <= profile.stages.stage4_entry_m)] = 4
    transitions: list[dict[str, Any]] = []
    previous = None
    for index, stage in enumerate(stages):
        current = int(stage)
        if previous != current:
            transitions.append(
                {
                    "time_s": float(times[index]),
                    "stage": current,
                    "distance_m": float(distance[index]),
                    "signed_tcpa_s": float(signed_tcpa[index]),
                }
            )
            previous = current
    return transitions


def stage_timeline(
    times: np.ndarray,
    distance: np.ndarray,
    cpa_index: int,
    safety_distance: float,
) -> list[dict[str, Any]]:
    """Build the evaluator stage timeline using the live monitor thresholds."""
    stages = np.zeros(times.size, dtype=int)
    stages[distance <= safety_distance * 8.0] = 1
    stages[distance <= safety_distance * 4.0] = 2
    if cpa_index + 1 < stages.size:
        stages[cpa_index + 1 :] = np.maximum(stages[cpa_index + 1 :], 3)
    transitions: list[dict[str, Any]] = []
    previous = None
    for index, stage in enumerate(stages):
        if previous != int(stage):
            transitions.append({"time_s": float(times[index]), "stage": int(stage)})
            previous = int(stage)
    return transitions


@dataclass
class EncounterSnapshot:
    ownship_id: int
    target_id: int
    encounter: str
    validation_rule_id: str | None
    stage: int
    distance_m: float
    dcpa_m: float
    tcpa_s: float
    signed_tcpa_s: float
    relative_bearing_deg: float
    fsm_state: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


RULE_BY_ENCOUNTER = {
    "overtaking": "rule13",
    "overtaken": "rule13",
    "head_on": "rule14",
    "crossing_give_way": "rule15",
    "crossing_stand_on": "rule15",
}


class EncounterMonitor:
    """Incrementally monitor truth geometry without duplicating browser logic."""

    def __init__(
        self,
        validation_rule_id: str | None = None,
        profile: str | EvaluatorProfile = DEFAULT_EVALUATOR_PROFILE_ID,
    ) -> None:
        self.validation_rule_id = validation_rule_id
        self.profile = load_evaluator_profile(profile) if isinstance(profile, str) else profile
        self._fsm_by_pair: dict[tuple[int, int], PairwiseColregFSM] = {}

    def update(self, ships: list[dict[str, Any]]) -> list[EncounterSnapshot]:
        if not ships:
            return []
        own = ships[0]
        output = []
        for target in ships[1:]:
            key = (int(own["id"]), int(target["id"]))
            own_velocity = _ship_velocity(own)
            target_velocity = _ship_velocity(target)
            relative = np.array([target["north"] - own["north"], target["east"] - own["east"]], dtype=float)
            distance = float(np.linalg.norm(relative))
            encounter, dcpa_m, tcpa_s, signed_tcpa_s, bearing = classify_geometry(
                np.array([own["north"], own["east"]], dtype=float),
                own_velocity,
                np.array([target["north"], target["east"]], dtype=float),
                target_velocity,
                float(own["length"]),
                float(target["length"]),
                profile=self.profile,
            )
            stage = 1
            if signed_tcpa_s > 0.0 and distance <= self.profile.stages.stage2_entry_m:
                stage = 2
            if signed_tcpa_s > 0.0 and distance <= self.profile.stages.stage3_entry_m:
                stage = 3
            if signed_tcpa_s > 0.0 and distance <= self.profile.stages.stage4_entry_m:
                stage = 4
            target_course = float(np.arctan2(target_velocity[1], target_velocity[0]))
            absolute_bearing = float(np.arctan2(relative[1], relative[0]))
            contact_angle = float(np.rad2deg(wrap_angle(absolute_bearing + np.pi - target_course)))
            fsm = self._fsm_by_pair.setdefault(key, PairwiseColregFSM(self.profile))
            fsm_state = fsm.update(
                EncounterObservation(
                    time_s=float(own.get("timestamp", 0.0)),
                    encounter=encounter,
                    stage=stage,
                    range_m=distance,
                    dcpa_m=dcpa_m,
                    signed_tcpa_s=signed_tcpa_s,
                    relative_bearing_deg=bearing,
                    contact_angle_deg=contact_angle,
                )
            )
            output.append(
                EncounterSnapshot(
                    ownship_id=key[0],
                    target_id=key[1],
                    encounter=encounter,
                    validation_rule_id=RULE_BY_ENCOUNTER.get(encounter),
                    stage=stage,
                    distance_m=distance,
                    dcpa_m=dcpa_m,
                    tcpa_s=tcpa_s,
                    signed_tcpa_s=signed_tcpa_s,
                    relative_bearing_deg=bearing,
                    fsm_state=fsm_state.value,
                )
            )
        return output


def _ship_velocity(ship: dict[str, Any]) -> np.ndarray:
    psi = float(ship["psi"])
    surge = float(ship["u"])
    sway = float(ship.get("v", 0.0))
    return np.array(
        [
            surge * np.cos(psi) - sway * np.sin(psi),
            surge * np.sin(psi) + sway * np.cos(psi),
        ],
        dtype=float,
    )
