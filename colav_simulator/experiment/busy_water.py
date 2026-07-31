"""Deterministic busy-water scenario generation and static preflight."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from colav_simulator.evaluation.encounter import classify_geometry, velocity_ne

DEFAULT_SEED = 20250731
ACCEPTANCE_SCENARIO_ID = "romsdal_busy_water_16"
STRESS_SCENARIO_ID = "romsdal_busy_water_80_stress"

_MAP_ORIGIN_NE = (6_955_450.0, 38_500.0)
_MAP_SIZE_NE = (5_000.0, 5_000.0)
_OS_START_NE = np.array([6_956_650.0, 39_800.0])
_OS_SPEED_MPS = 6.0
_OS_COURSE_DEG = 0.0
_SHIP_LENGTH_M = 12.0
_SHIP_WIDTH_M = 4.0


@dataclass(frozen=True)
class EncounterEvent:
    """One planned nominal Ship0 encounter."""

    target_id: int
    time_s: float
    encounter: str
    target_speed_mps: float
    target_course_deg: float
    cpa_offset_ne_m: tuple[float, float] = (0.0, 0.0)
    active_before_s: float = 30.0
    active_after_s: float = 20.0


ACCEPTANCE_EVENTS = (
    EncounterEvent(1, 70.0, "head_on", 6.0, 180.0),
    EncounterEvent(2, 140.0, "crossing_give_way", 6.0, 270.0),
    EncounterEvent(3, 210.0, "crossing_stand_on", 6.0, 90.0, cpa_offset_ne_m=(-100.0, -250.0)),
    EncounterEvent(4, 285.0, "overtaking", 3.5, 0.0, active_before_s=70.0, active_after_s=8.0),
    EncounterEvent(5, 350.0, "overtaken", 8.0, 0.0, active_before_s=80.0),
    EncounterEvent(6, 420.0, "head_on", 5.0, 180.0),
    EncounterEvent(7, 430.0, "crossing_give_way", 5.0, 270.0),
    EncounterEvent(
        8,
        440.0,
        "crossing_stand_on",
        5.0,
        90.0,
        cpa_offset_ne_m=(300.0, 75.0),
        active_before_s=30.0,
    ),
)


def build_busy_water_document(profile: str, *, seed: int = DEFAULT_SEED) -> dict[str, Any]:
    """Build one complete deterministic scenario document."""
    if profile == "acceptance":
        return _build_acceptance_document(seed)
    if profile == "stress":
        return _build_stress_document(seed)
    raise ValueError(f"unsupported busy-water profile: {profile}")


def write_busy_water_scenario(profile: str, output: Path, *, seed: int = DEFAULT_SEED) -> Path:
    """Write a generated scenario as stable YAML."""
    document = build_busy_water_document(profile, seed=seed)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        yaml.safe_dump(document, sort_keys=False, allow_unicode=True, width=120),
        encoding="utf-8",
    )
    return output


def preflight_document(document: dict[str, Any], *, seed: int = DEFAULT_SEED) -> dict[str, Any]:
    """Validate deterministic geometry without loading an ENC."""
    ships = list(document.get("ship_list", ()))
    if not ships:
        raise ValueError("scenario has no ships")
    ids = [int(ship["id"]) for ship in ships]
    if len(ids) != len(set(ids)):
        raise ValueError("ship IDs must be unique")
    if int(document.get("n_random_ships", -1)) != len(ships) - 1:
        raise ValueError("n_random_ships must equal ship_list target count")

    t_end = float(document["t_end"])
    for ship in ships:
        start = float(ship.get("t_start", 0.0))
        end = float(ship.get("t_end", t_end))
        if not 0.0 <= start < end <= t_end:
            raise ValueError(f"invalid active window for ship {ship['id']}: {start}..{end}")
        _require_route_inside_map(document, ship)
    _require_initial_separation(ships)
    pair_clearances = _trajectory_pair_clearances(ships, t_end)
    target_collisions = [
        item
        for item in pair_clearances
        if 0 not in item["ship_ids"] and item["minimum_center_distance_m"] <= item["required_center_distance_m"]
    ]
    if document["name"] == ACCEPTANCE_SCENARIO_ID and target_collisions:
        raise ValueError(f"nominal target-target collision: {target_collisions}")

    event_results = _acceptance_event_results(document) if document["name"] == ACCEPTANCE_SCENARIO_ID else []
    mismatches = [item for item in event_results if item["detected_encounter"] != item["expected_encounter"]]
    if mismatches:
        raise ValueError(f"planned encounter mismatch: {mismatches}")
    return {
        "scenario_id": document["name"],
        "seed": int(seed),
        "ship_count": len(ships),
        "target_count": len(ships) - 1,
        "id_unique": True,
        "active_windows_valid": True,
        "routes_inside_map": True,
        "initial_footprints_separated": True,
        "nominal_target_collision_count": len(target_collisions),
        "nearest_nominal_pair": min(
            pair_clearances,
            key=lambda item: item["minimum_center_distance_m"],
            default=None,
        ),
        "planned_events": event_results,
    }


def _build_acceptance_document(seed: int) -> dict[str, Any]:
    ships = [_ownship_document()]
    ships.extend(_event_ship_document(event) for event in ACCEPTANCE_EVENTS)
    ships.extend(_background_ship_documents())
    np.random.SeedSequence(seed)
    document = _base_document(ACCEPTANCE_SCENARIO_ID, dt_sim=0.1, target_count=15)
    document["ship_list"] = ships
    return document


def _build_stress_document(seed: int) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    ships = [_ownship_document(speed_mps=4.0)]
    north_offsets = np.linspace(300.0, 3_300.0, 12)
    lane_eastings = (39_600.0, 40_000.0, 40_200.0, 40_400.0, 40_600.0, 40_800.0, 41_000.0)
    identifier = 1
    for lane_index, east in enumerate(lane_eastings):
        for north_offset in north_offsets:
            if identifier > 79:
                break
            jitter = float(rng.uniform(-18.0, 18.0))
            north = _MAP_ORIGIN_NE[0] + north_offset + jitter
            speed = 2.0 + 0.02 * lane_index
            ships.append(
                _target_ship_document(
                    identifier,
                    np.array([north, east]),
                    speed,
                    0.0,
                    t_start=0.0,
                    t_end=600.0,
                )
            )
            identifier += 1
    document = _base_document(STRESS_SCENARIO_ID, dt_sim=0.5, target_count=79)
    document["ship_list"] = ships
    return document


def _base_document(name: str, *, dt_sim: float, target_count: int) -> dict[str, Any]:
    return {
        "name": name,
        "save_scenario": False,
        "t_start": 0.0,
        "t_end": 600.0,
        "dt_sim": dt_sim,
        "utm_zone": 33,
        "map_size": [_MAP_SIZE_NE[1], _MAP_SIZE_NE[0]],
        "map_origin_enu": [_MAP_ORIGIN_NE[1], _MAP_ORIGIN_NE[0]],
        "map_data_files": ["More_og_Romsdal_utm33.gdb"],
        "new_load_of_map_data": True,
        "type": "MS",
        "n_episodes": 1,
        "n_random_ships": target_count,
    }


def _ownship_document(*, speed_mps: float = _OS_SPEED_MPS) -> dict[str, Any]:
    return {
        "csog_state": [float(_OS_START_NE[0]), float(_OS_START_NE[1]), speed_mps, _OS_COURSE_DEG],
        "waypoints": [
            [float(_OS_START_NE[0]), _MAP_ORIGIN_NE[0] + _MAP_SIZE_NE[0] - 150.0],
            [float(_OS_START_NE[1]), float(_OS_START_NE[1])],
        ],
        "speed_plan": [speed_mps, speed_mps],
        "id": 0,
        "mmsi": 100,
        "guidance": _guidance_document(),
        "controller": {"pass_through_cs": ""},
        "model": {"csog": _model_document()},
    }


def _event_ship_document(event: EncounterEvent) -> dict[str, Any]:
    t_start = max(0.0, event.time_s - event.active_before_s)
    t_end = min(600.0, event.time_s + event.active_after_s)
    own_at_event = _OS_START_NE + velocity_ne(_OS_SPEED_MPS, np.deg2rad(_OS_COURSE_DEG)) * event.time_s
    target_at_event = own_at_event + np.asarray(event.cpa_offset_ne_m)
    velocity = velocity_ne(event.target_speed_mps, np.deg2rad(event.target_course_deg))
    initial = target_at_event - velocity * (event.time_s - t_start)
    return _target_ship_document(
        event.target_id,
        initial,
        event.target_speed_mps,
        event.target_course_deg,
        t_start=t_start,
        t_end=t_end,
    )


def _background_ship_documents() -> list[dict[str, Any]]:
    specs = (
        (9, 6_955_650.0, 39_600.0, 6.0, 0.0),
        (10, 6_955_850.0, 40_000.0, 6.0, 0.0),
        (11, 6_956_050.0, 40_200.0, 6.0, 0.0),
        (12, 6_956_250.0, 40_400.0, 6.0, 0.0),
        (13, 6_956_450.0, 40_600.0, 6.0, 0.0),
        (14, 6_956_650.0, 40_800.0, 6.0, 0.0),
        (15, 6_956_850.0, 41_000.0, 6.0, 0.0),
    )
    return [
        _target_ship_document(
            identifier,
            np.array([north, east]),
            speed,
            course,
            t_start=0.0,
            t_end=30.0,
        )
        for identifier, north, east, speed, course in specs
    ]


def _target_ship_document(
    identifier: int,
    position_ne: np.ndarray,
    speed_mps: float,
    course_deg: float,
    *,
    t_start: float,
    t_end: float,
) -> dict[str, Any]:
    velocity = velocity_ne(speed_mps, np.deg2rad(course_deg))
    active_duration = t_end - t_start
    endpoint = position_ne + velocity * active_duration
    return {
        "csog_state": [float(position_ne[0]), float(position_ne[1]), speed_mps, course_deg],
        "waypoints": [
            [float(position_ne[0]), float(endpoint[0])],
            [float(position_ne[1]), float(endpoint[1])],
        ],
        "speed_plan": [speed_mps, speed_mps],
        "id": identifier,
        "mmsi": 100 + identifier,
        "t_start": t_start,
        "t_end": t_end,
        "guidance": _guidance_document(),
        "controller": {"pass_through_cs": ""},
        "model": {"csog": _model_document()},
    }


def _guidance_document() -> dict[str, Any]:
    return {
        "los": {
            "pass_angle_threshold": 80.0,
            "R_a": 40.0,
            "K_p": 0.015,
            "K_i": 0.0,
            "max_cross_track_error_int": 200.0,
            "cross_track_error_int_threshold": 30.0,
        }
    }


def _model_document() -> dict[str, Any]:
    return {
        "draft": 3.0,
        "length": _SHIP_LENGTH_M,
        "width": _SHIP_WIDTH_M,
        "T_chi": 3.0,
        "T_U": 5.0,
        "r_max": 4.0,
        "U_min": 0.0,
        "U_max": 15.0,
    }


def _require_route_inside_map(document: dict[str, Any], ship: dict[str, Any]) -> None:
    east_min, north_min = map(float, document["map_origin_enu"])
    east_size, north_size = map(float, document["map_size"])
    north = np.asarray(ship["waypoints"][0], dtype=float)
    east = np.asarray(ship["waypoints"][1], dtype=float)
    if np.any(north < north_min) or np.any(north > north_min + north_size):
        raise ValueError(f"ship {ship['id']} route leaves map north bounds")
    if np.any(east < east_min) or np.any(east > east_min + east_size):
        raise ValueError(f"ship {ship['id']} route leaves map east bounds")


def _require_initial_separation(ships: list[dict[str, Any]]) -> None:
    required = float(np.hypot(_SHIP_LENGTH_M, _SHIP_WIDTH_M) + 5.0)
    for index, ship in enumerate(ships):
        for target in ships[index + 1 :]:
            if not _windows_overlap(ship, target):
                continue
            overlap_start = max(float(ship.get("t_start", 0.0)), float(target.get("t_start", 0.0)))
            position = _nominal_position(ship, overlap_start)
            target_position = _nominal_position(target, overlap_start)
            if np.linalg.norm(position - target_position) < required:
                raise ValueError(f"ships {ship['id']} and {target['id']} initially overlap")


def _windows_overlap(first: dict[str, Any], second: dict[str, Any]) -> bool:
    return max(float(first.get("t_start", 0.0)), float(second.get("t_start", 0.0))) < min(
        float(first.get("t_end", 600.0)),
        float(second.get("t_end", 600.0)),
    )


def _nominal_position(ship: dict[str, Any], sim_time_s: float) -> np.ndarray:
    active_time_s = max(0.0, sim_time_s - float(ship.get("t_start", 0.0)))
    velocity = velocity_ne(
        float(ship["csog_state"][2]),
        np.deg2rad(float(ship["csog_state"][3])),
    )
    return np.asarray(ship["csog_state"][:2], dtype=float) + velocity * active_time_s


def _trajectory_pair_clearances(ships: list[dict[str, Any]], scenario_end_s: float) -> list[dict[str, Any]]:
    output = []
    required = float(np.hypot(_SHIP_LENGTH_M, _SHIP_WIDTH_M))
    for index, first in enumerate(ships):
        for second in ships[index + 1 :]:
            start = max(float(first.get("t_start", 0.0)), float(second.get("t_start", 0.0)))
            end = min(
                float(first.get("t_end", scenario_end_s)),
                float(second.get("t_end", scenario_end_s)),
            )
            if start >= end:
                continue
            first_velocity = velocity_ne(
                float(first["csog_state"][2]),
                np.deg2rad(float(first["csog_state"][3])),
            )
            second_velocity = velocity_ne(
                float(second["csog_state"][2]),
                np.deg2rad(float(second["csog_state"][3])),
            )
            first_position = np.asarray(first["csog_state"][:2], dtype=float) + first_velocity * (
                start - float(first.get("t_start", 0.0))
            )
            second_position = np.asarray(second["csog_state"][:2], dtype=float) + second_velocity * (
                start - float(second.get("t_start", 0.0))
            )
            relative = second_position - first_position
            relative_velocity = second_velocity - first_velocity
            denominator = float(np.dot(relative_velocity, relative_velocity))
            tcpa = 0.0 if denominator <= 1e-12 else -float(np.dot(relative, relative_velocity)) / denominator
            tcpa = float(np.clip(tcpa, 0.0, end - start))
            minimum_distance = float(np.linalg.norm(relative + relative_velocity * tcpa))
            output.append(
                {
                    "ship_ids": [int(first["id"]), int(second["id"])],
                    "minimum_center_distance_m": minimum_distance,
                    "required_center_distance_m": required,
                    "time_s": start + tcpa,
                }
            )
    return output


def _acceptance_event_results(document: dict[str, Any]) -> list[dict[str, Any]]:
    ships = {int(ship["id"]): ship for ship in document["ship_list"]}
    own = ships[0]
    output = []
    for event in ACCEPTANCE_EVENTS:
        target = ships[event.target_id]
        own_position = np.asarray(own["csog_state"][:2], dtype=float) + velocity_ne(
            float(own["csog_state"][2]),
            np.deg2rad(float(own["csog_state"][3])),
        ) * event.time_s
        active_duration = event.time_s - float(target.get("t_start", 0.0))
        target_position = np.asarray(target["csog_state"][:2], dtype=float) + velocity_ne(
            float(target["csog_state"][2]),
            np.deg2rad(float(target["csog_state"][3])),
        ) * active_duration
        detected, dcpa_m, _, signed_tcpa_s, _ = classify_geometry(
            own_position - velocity_ne(_OS_SPEED_MPS, 0.0) * 20.0,
            velocity_ne(_OS_SPEED_MPS, 0.0),
            target_position - velocity_ne(event.target_speed_mps, np.deg2rad(event.target_course_deg)) * 20.0,
            velocity_ne(event.target_speed_mps, np.deg2rad(event.target_course_deg)),
            _SHIP_LENGTH_M,
            _SHIP_LENGTH_M,
        )
        output.append(
            {
                "target_id": event.target_id,
                "time_s": event.time_s,
                "expected_encounter": event.encounter,
                "detected_encounter": detected,
                "nominal_dcpa_m": dcpa_m,
                "signed_tcpa_s_at_window_probe": signed_tcpa_s,
            }
        )
    return output
