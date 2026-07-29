"""Ocean Engineering 2023 compatible COLREG score components."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any

import numpy as np

from colav_simulator.evaluation.encounter import wrap_angle
from colav_simulator.evaluation.profiles import EvaluatorProfile


class MetricStatus(StrEnum):
    EVALUATED = "EVALUATED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NOT_EVALUATED = "NOT_EVALUATED"


@dataclass(frozen=True)
class MetricEvidence:
    metric_id: str
    value: float | None
    status: MetricStatus
    formula_id: str
    raw_components: dict[str, float | str | None]
    assumptions: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        output = asdict(self)
        output["status"] = self.status.value
        return output


def range_safety_score(distance_m: float, profile: EvaluatorProfile) -> float:
    """Paper Eq. (3), piecewise range score."""
    ranges = profile.safety
    weights = profile.weights
    if distance_m >= ranges.preferred_m:
        return 1.0
    if distance_m >= ranges.minimum_m:
        fraction = (ranges.preferred_m - distance_m) / (ranges.preferred_m - ranges.minimum_m)
        return float(1.0 - weights.range_minimum * fraction)
    if distance_m >= ranges.near_miss_m:
        fraction = (ranges.minimum_m - distance_m) / (ranges.minimum_m - ranges.near_miss_m)
        return float(1.0 - weights.range_minimum - weights.range_near_miss * fraction)
    if distance_m >= ranges.collision_m:
        fraction = (ranges.near_miss_m - distance_m) / (ranges.near_miss_m - ranges.collision_m)
        return float(
            1.0
            - weights.range_minimum
            - weights.range_near_miss
            - weights.range_collision * fraction
        )
    return 0.0


def pose_score(contact_angle_rad: float, relative_bearing_rad: float, profile: EvaluatorProfile) -> float:
    """Paper Eqs. (4)-(6), pose score at actual CPA."""
    alpha_cut = np.deg2rad(90.0)
    beta_min = np.deg2rad(90.0)
    beta_max = np.deg2rad(270.0)
    alpha = abs(float(wrap_angle(contact_angle_rad)))
    beta = float(relative_bearing_rad % (2.0 * np.pi))
    contact = (1.0 - np.cos(alpha)) / (1.0 - np.cos(alpha_cut)) if alpha < alpha_cut else 1.0
    if beta < beta_min:
        relative = (1.0 - np.cos(beta)) / (1.0 - np.cos(beta_min))
    elif beta > beta_max:
        relative = (1.0 - np.cos(beta)) / (1.0 - np.cos(beta_max))
    else:
        relative = 1.0
    return _unit(profile.weights.pose_contact * contact + profile.weights.pose_relative_bearing * relative)


def total_safety_score(range_score: float, vessel_pose_score: float) -> float:
    """Paper Eq. (2), coupling range and pose without masking collision."""
    if range_score <= 0.0:
        return 0.0
    if range_score >= 1.0:
        return 1.0
    return _unit((1.0 - range_score) * vessel_pose_score + range_score)


def safety_domain_score(
    distance_m: float,
    relative_bearing_rad: float,
    vessel_length_m: float,
    profile: EvaluatorProfile,
) -> float | None:
    """Ownship-centered Fujii ellipse clearance ratio, capped to [0, 1]."""
    domain = profile.safety_domain
    if domain.model == "disabled":
        return None
    if vessel_length_m <= 0.0:
        raise ValueError("ship-length-scaled profile requires a positive vessel length")
    longitudinal = domain.longitudinal_length_factor * vessel_length_m
    transverse = domain.transverse_length_factor * vessel_length_m
    bearing = float(wrap_angle(relative_bearing_rad))
    boundary = longitudinal * transverse / np.sqrt(
        (transverse * np.cos(bearing)) ** 2 + (longitudinal * np.sin(bearing)) ** 2
    )
    return _unit(distance_m / boundary)


def non_apparent_penalty(value: float, detectable: float, apparent: float) -> float:
    """Penalty of one for imperceptible action, zero for readily apparent action."""
    value = abs(float(value))
    if value <= detectable:
        return 1.0
    if value >= apparent:
        return 0.0
    ratio = (value - detectable) / (apparent - detectable)
    return _unit(1.0 - ratio**2)


def action_penalty(value: float, detectable: float, apparent: float) -> float:
    """Stand-on action penalty: zero below detection, one at apparent action."""
    value = abs(float(value))
    if value <= detectable:
        return 0.0
    return _unit((value - detectable) / (apparent - detectable))


def score_pair(
    *,
    encounter: str,
    courses_rad: np.ndarray,
    speeds_mps: np.ndarray,
    distances_m: np.ndarray,
    stages: np.ndarray,
    cpa_index: int,
    contact_angle_rad: float,
    relative_bearing_rad: float,
    profile: EvaluatorProfile,
    ownship_length_m: float | None = None,
) -> tuple[dict[str, float | None], dict[str, MetricEvidence]]:
    """Evaluate one vessel's behavior toward one target."""
    courses = np.asarray(courses_rad, dtype=float)
    speeds = np.asarray(speeds_mps, dtype=float)
    distances = np.asarray(distances_m, dtype=float)
    stages = np.asarray(stages, dtype=int)
    if not (courses.shape == speeds.shape == distances.shape == stages.shape):
        raise ValueError("pair scoring arrays must share shape")
    if courses.size == 0 or not 0 <= cpa_index < courses.size:
        raise ValueError("pair scoring requires a valid CPA index")
    course_delta = np.asarray(wrap_angle(courses[: cpa_index + 1] - courses[0]), dtype=float)
    max_course_change = float(np.max(np.abs(course_delta)))
    starboard_change = max(0.0, float(np.max(course_delta)))
    initial_speed = max(float(speeds[0]), 1e-9)
    relative_speed_reduction = max(0.0, float(np.max(initial_speed - speeds[: cpa_index + 1]))) / initial_speed
    range_score = range_safety_score(float(distances[cpa_index]), profile)
    vessel_pose_score = pose_score(contact_angle_rad, relative_bearing_rad, profile)
    safety_score = total_safety_score(range_score, vessel_pose_score)
    domain_score = safety_domain_score(
        float(distances[cpa_index]),
        relative_bearing_rad,
        float(ownship_length_m or 0.0),
        profile,
    )
    p_course = non_apparent_penalty(
        max_course_change,
        np.deg2rad(profile.maneuver.detectable_turn_deg),
        np.deg2rad(profile.maneuver.apparent_turn_deg),
    )
    p_speed = non_apparent_penalty(
        relative_speed_reduction,
        profile.maneuver.detectable_relative_speed,
        profile.maneuver.apparent_relative_speed,
    )
    apparent_score = _unit(
        1.0
        - profile.weights.apparent_course * p_course
        - profile.weights.apparent_speed * p_speed
    )
    p_delay = _delay_penalty(
        course_delta,
        speeds[: cpa_index + 1],
        distances[: cpa_index + 1],
        profile,
    )
    s16 = _unit(safety_score * apparent_score * (1.0 - p_delay))
    p_sts = _starboard_to_starboard_penalty(contact_angle_rad, relative_bearing_rad)
    p_nsb = _non_starboard_penalty(starboard_change, profile)
    s14 = _unit(
        (
            1.0
            - profile.weights.head_on_non_starboard * p_nsb
            - profile.weights.head_on_starboard_to_starboard * p_sts
        )
        * (1.0 - p_course)
        * (1.0 - p_delay)
    )
    s17, p_stage2, p_stage3, p_port_turn = _stand_on_score(
        courses,
        speeds,
        stages,
        cpa_index,
        safety_score,
        contact_angle_rad,
        relative_bearing_rad,
        profile,
    )
    p_ahead_overtaking = float(abs(np.rad2deg(wrap_angle(contact_angle_rad))) < 45.0)
    alpha_deg = float(np.rad2deg(wrap_angle(contact_angle_rad)))
    p_ahead_crossing = float(-25.0 < alpha_deg < 165.0)
    role_give_way = encounter in {"head_on", "crossing_give_way", "overtaking"}

    metrics: dict[str, float | None] = {
        "S8": _unit(apparent_score * (1.0 - p_delay)) if role_give_way else None,
        "S13": (
            _unit(s16 - profile.weights.ahead_overtaking * p_ahead_overtaking)
            if encounter == "overtaking"
            else s17
            if encounter == "overtaken"
            else None
        ),
        "S14": s14 if encounter == "head_on" else None,
        "S15": (
            _unit(s16 - profile.weights.ahead_crossing * p_ahead_crossing)
            if encounter == "crossing_give_way"
            else s17
            if encounter == "crossing_stand_on"
            else None
        ),
        "S16": s16 if role_give_way else None,
        "S17": s17 if encounter in {"crossing_stand_on", "overtaken"} else None,
        "S_safety": safety_score,
        "S_theta": vessel_pose_score,
        "S_r": range_score,
        "S_domain": domain_score,
        "S_apparent": apparent_score if role_give_way else None,
        "P_delay": p_delay if role_give_way else None,
        "P_course_non_apparent": p_course if role_give_way else None,
        "P_speed_non_apparent": p_speed if role_give_way else None,
        "P_sts": p_sts if encounter == "head_on" else None,
        "P_nsb": p_nsb if encounter == "head_on" else None,
        "P_stage2": p_stage2 if encounter in {"crossing_stand_on", "overtaken"} else None,
        "P_stage3": p_stage3 if encounter in {"crossing_stand_on", "overtaken"} else None,
        "P_pt": p_port_turn if encounter in {"crossing_stand_on", "overtaken"} else None,
        "P_ahead13": p_ahead_overtaking if encounter == "overtaking" else None,
        "P_ahead15": p_ahead_crossing if encounter == "crossing_give_way" else None,
    }
    formula_ids = {
        "S_r": "oe2023-eq3",
        "S_domain": "fujii-1971-4L-1.6L-domain",
        "S_theta": "oe2023-eq4-6",
        "S_safety": "oe2023-eq2",
        "S16": "oe2023-eq7",
        "P_delay": "oe2023-eq8",
        "S_apparent": "oe2023-eq9",
        "P_course_non_apparent": "oe2023-eq10-11",
        "P_speed_non_apparent": "oe2023-eq12-14",
        "S17": "oe2023-eq15",
        "P_pt": "oe2023-eq16",
        "P_stage2": "oe2023-eq17-24",
        "P_stage3": "oe2023-eq17-24",
        "S13": "oe2023-eq25",
        "P_ahead13": "oe2023-eq26",
        "S14": "oe2023-eq27",
        "P_sts": "oe2023-eq28",
        "P_nsb": "oe2023-eq29-30",
        "S15": "oe2023-eq31",
        "P_ahead15": "oe2023-eq32",
        "S8": "oe2023-rule8-derived",
    }
    raw = {
        "minimum_distance_m": float(distances[cpa_index]),
        "contact_angle_rad": float(contact_angle_rad),
        "relative_bearing_rad": float(relative_bearing_rad),
        "max_course_change_rad": max_course_change,
        "starboard_change_rad": starboard_change,
        "relative_speed_reduction": relative_speed_reduction,
    }
    evidence = {
        name: MetricEvidence(
            metric_id=name,
            value=value,
            status=MetricStatus.EVALUATED if value is not None else MetricStatus.NOT_APPLICABLE,
            formula_id=formula_ids.get(name, "oe2023-derived"),
            raw_components=raw,
        )
        for name, value in metrics.items()
    }
    return metrics, evidence


def _delay_penalty(
    course_delta: np.ndarray,
    speeds: np.ndarray,
    distances: np.ndarray,
    profile: EvaluatorProfile,
) -> float:
    relative_speed = np.abs(speeds - speeds[0]) / max(float(speeds[0]), 1e-9)
    maneuver = (np.abs(course_delta) >= np.deg2rad(profile.maneuver.detectable_turn_deg)) | (
        relative_speed >= profile.maneuver.detectable_relative_speed
    )
    maneuver_index = int(np.argmax(maneuver)) if maneuver.any() else len(distances) - 1
    maneuver_range = float(distances[maneuver_index])
    if maneuver_range > profile.stages.stage3_entry_m:
        return 0.0
    entry_range = max(float(distances[0]), 1e-9)
    return _unit((entry_range - maneuver_range) / entry_range)


def _non_starboard_penalty(starboard_change_rad: float, profile: EvaluatorProfile) -> float:
    minimum = np.deg2rad(profile.maneuver.starboard_turn_min_deg)
    apparent = np.deg2rad(profile.maneuver.apparent_turn_deg)
    if starboard_change_rad < minimum:
        return 1.0
    if starboard_change_rad > apparent:
        return 0.0
    ratio = (starboard_change_rad - minimum) / (apparent - minimum)
    return _unit(1.0 - ratio**2)


def _starboard_to_starboard_penalty(contact_angle_rad: float, relative_bearing_rad: float) -> float:
    first = ((np.sin(contact_angle_rad) - 1.0) / 2.0) ** 2
    second = ((np.sin(relative_bearing_rad) - 1.0) / 2.0) ** 2
    return _unit(1.0 - first * second)


def _stand_on_score(
    courses: np.ndarray,
    speeds: np.ndarray,
    stages: np.ndarray,
    cpa_index: int,
    safety_score: float,
    contact_angle_rad: float,
    relative_bearing_rad: float,
    profile: EvaluatorProfile,
) -> tuple[float, float, float, float]:
    penalties = []
    for stage in (2, 3):
        indices = np.flatnonzero((stages == stage) & (np.arange(stages.size) <= cpa_index))
        if indices.size == 0:
            penalties.append(0.0)
            continue
        initial = int(indices[0])
        course_change = float(np.max(np.abs(wrap_angle(courses[indices] - courses[initial]))))
        speed_change = float(np.max(np.abs(speeds[indices] - speeds[initial]))) / max(float(speeds[initial]), 1e-9)
        course_penalty = action_penalty(
            course_change,
            np.deg2rad(profile.maneuver.detectable_turn_deg),
            np.deg2rad(profile.maneuver.apparent_turn_deg),
        )
        speed_penalty = action_penalty(
            speed_change,
            profile.maneuver.detectable_relative_speed,
            profile.maneuver.apparent_relative_speed,
        )
        penalties.append(_unit(0.5 * course_penalty + 0.5 * speed_penalty))
    stage4 = np.flatnonzero((stages == 4) & (np.arange(stages.size) <= cpa_index))
    p_port_turn = 0.0
    if stage4.size and contact_angle_rad < 0.0 and relative_bearing_rad % (2.0 * np.pi) < np.pi:
        initial = int(stage4[0])
        port_change = max(0.0, -float(np.min(wrap_angle(courses[stage4] - courses[initial]))))
        p_port_turn = float(port_change >= np.deg2rad(profile.maneuver.detectable_turn_deg))
    score = _unit(safety_score * (1.0 - penalties[0]) * (1.0 - penalties[1]) * (1.0 - p_port_turn))
    return score, penalties[0], penalties[1], p_port_turn


def _unit(value: float) -> float:
    return float(np.clip(value, 0.0, 1.0))
