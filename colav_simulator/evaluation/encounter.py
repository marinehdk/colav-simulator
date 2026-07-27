"""Shared truth-based encounter classification for live monitoring and evaluation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np


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
    """Return DCPA, non-negative TCPA, and signed TCPA."""
    speed_sq = float(np.dot(relative_velocity_ne, relative_velocity_ne))
    if speed_sq < 1e-9:
        distance = float(np.linalg.norm(relative_position_ne))
        return distance, 0.0, 0.0
    signed_tcpa = -float(np.dot(relative_position_ne, relative_velocity_ne)) / speed_sq
    tcpa_s = max(0.0, signed_tcpa)
    dcpa_m = float(np.linalg.norm(relative_position_ne + relative_velocity_ne * tcpa_s))
    return dcpa_m, tcpa_s, signed_tcpa


def classify_geometry(
    own_position_ne: np.ndarray,
    own_velocity_ne: np.ndarray,
    target_position_ne: np.ndarray,
    target_velocity_ne: np.ndarray,
    own_length_m: float,
    target_length_m: float,
) -> tuple[str, float, float, float, float]:
    """Classify one pair and return encounter, DCPA, TCPA, signed TCPA, bearing."""
    relative = np.asarray(target_position_ne, dtype=float) - np.asarray(own_position_ne, dtype=float)
    relative_velocity = np.asarray(target_velocity_ne, dtype=float) - np.asarray(own_velocity_ne, dtype=float)
    dcpa_m, tcpa_s, signed_tcpa_s = cpa(relative, relative_velocity)
    own_course = float(np.arctan2(own_velocity_ne[1], own_velocity_ne[0]))
    target_course = float(np.arctan2(target_velocity_ne[1], target_velocity_ne[0]))
    absolute_bearing = float(np.arctan2(relative[1], relative[0]))
    relative_bearing_deg = float(np.rad2deg(wrap_angle(absolute_bearing - own_course)))
    course_difference_deg = abs(float(np.rad2deg(wrap_angle(target_course - own_course))))
    risk_distance = max(500.0, 10.0 * (own_length_m + target_length_m))
    if signed_tcpa_s <= 0.0 or dcpa_m > risk_distance:
        encounter = "clear"
    elif abs(relative_bearing_deg) <= 15.0 and course_difference_deg >= 150.0:
        encounter = "head_on"
    elif abs(relative_bearing_deg) > 112.5 and np.linalg.norm(own_velocity_ne) > np.linalg.norm(target_velocity_ne):
        encounter = "overtaking"
    elif 0.0 < relative_bearing_deg <= 112.5:
        encounter = "crossing_give_way"
    elif -112.5 <= relative_bearing_deg < 0.0:
        encounter = "crossing_stand_on"
    else:
        encounter = "clear"
    return encounter, dcpa_m, tcpa_s, signed_tcpa_s, relative_bearing_deg


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
    relative_bearing_deg: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


RULE_BY_ENCOUNTER = {
    "overtaking": "rule13",
    "head_on": "rule14",
    "crossing_give_way": "rule15",
    "crossing_stand_on": "rule15",
}


class EncounterMonitor:
    """Incrementally monitor truth geometry without duplicating browser logic."""

    def __init__(self, validation_rule_id: str | None = None) -> None:
        self.validation_rule_id = validation_rule_id
        self._stage_by_pair: dict[tuple[int, int], int] = {}
        self._risk_seen: set[tuple[int, int]] = set()

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
            )
            safety_distance = max(float(own["length"]) + float(target["length"]), 1.0)
            stage = 0
            if distance <= safety_distance * 8.0:
                stage = 1
                self._risk_seen.add(key)
            if distance <= safety_distance * 4.0:
                stage = 2
                self._risk_seen.add(key)
            if key in self._risk_seen and signed_tcpa_s <= 0.0:
                stage = 3
            stage = max(stage, self._stage_by_pair.get(key, 0))
            self._stage_by_pair[key] = stage
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
                    relative_bearing_deg=bearing,
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
