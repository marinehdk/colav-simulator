"""Deterministic busy-water scenario generation and static preflight."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from colav_simulator.evaluation.encounter import classify_geometry, velocity_ne

DEFAULT_SEED = 20250731
ACCEPTANCE_SCENARIO_ID = "romsdal_busy_water_16"
STRESS_SCENARIO_ID = "romsdal_busy_water_80_stress"
DEFAULT_TARGET_COUNT = 15
MAX_TARGET_COUNT = 79
BUSY_WATER_DURATION_S = 1200.0
DEFAULT_ENCOUNTER_MIX = {
    "crossing": 0.60,
    "head_on": 0.20,
    "overtaking": 0.20,
}

_MAP_ORIGIN_NE = (6_955_450.0, 38_500.0)
_MAP_SIZE_NE = (5_000.0, 5_000.0)
_OS_START_NE = np.array([6_956_650.0, 39_800.0])
_OS_SPEED_MPS = 6.0
_OS_COURSE_DEG = 0.0
_SHIP_LENGTH_M = 12.0
_SHIP_WIDTH_M = 4.0


def build_busy_water_document(
    profile: str,
    *,
    seed: int = DEFAULT_SEED,
    target_count: int | None = None,
    encounter_mix: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Build one complete deterministic scenario document."""
    if profile not in {"acceptance", "stress"}:
        raise ValueError(f"unsupported busy-water profile: {profile}")
    default_count = DEFAULT_TARGET_COUNT if profile == "acceptance" else MAX_TARGET_COUNT
    count = default_count if target_count is None else int(target_count)
    if not 0 <= count <= MAX_TARGET_COUNT:
        raise ValueError(f"target_count must be in [0, {MAX_TARGET_COUNT}]")
    mix = normalize_encounter_mix(encounter_mix)
    dt_sim = 0.1 if profile == "acceptance" else 0.5
    scenario_id = ACCEPTANCE_SCENARIO_ID if profile == "acceptance" else STRESS_SCENARIO_ID
    return _build_route_traffic_document(scenario_id, seed, count, mix, dt_sim=dt_sim)


def normalize_single_pass_document(document: dict[str, Any]) -> dict[str, Any]:
    """Normalize busy-water targets to one entry-to-exit transit."""
    normalized = copy.deepcopy(document)
    scenario_end = float(normalized["t_end"])
    for ship in normalized.get("ship_list", [])[1:]:
        start = float(ship.get("t_start", 0.0))
        speed = float(ship["csog_state"][2])
        if speed <= 0.0:
            raise ValueError(f"ship {ship['id']} single-pass speed must be positive")
        waypoints = np.asarray(ship["waypoints"], dtype=float)
        first = waypoints[:, 0]
        second = waypoints[:, -1]
        delta = second - first
        length = float(np.linalg.norm(delta))
        if length <= 1e-9:
            raise ValueError(f"ship {ship['id']} single-pass endpoints must be distinct")
        unit = delta / length
        position = np.asarray(ship["csog_state"][:2], dtype=float)
        velocity = velocity_ne(speed, np.deg2rad(float(ship["csog_state"][3])))
        exit_point = second if float(velocity @ unit) >= 0.0 else first
        remaining = float(np.linalg.norm(exit_point - position))
        end = min(scenario_end, start + remaining / speed)
        if end <= start + 1e-9:
            raise ValueError(f"ship {ship['id']} starts at its single-pass exit")
        ship["t_start"] = start
        ship["t_end"] = end
    return normalized


def write_busy_water_scenario(
    profile: str,
    output: Path,
    *,
    seed: int = DEFAULT_SEED,
    target_count: int | None = None,
    encounter_mix: dict[str, float] | None = None,
) -> Path:
    """Write a generated scenario as stable YAML."""
    document = build_busy_water_document(
        profile,
        seed=seed,
        target_count=target_count,
        encounter_mix=encounter_mix,
    )
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
    event_results = _nominal_encounter_results(document)
    configured_roles = [_configured_encounter_role(ship) for ship in ships[1:]]
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
        "configured_encounter_counts": {
            "crossing": sum(role.startswith("crossing_") for role in configured_roles),
            "head_on": configured_roles.count("head_on"),
            "overtaking": sum(role in {"overtaking", "overtaken"} for role in configured_roles),
        },
        "nearest_nominal_pair": min(
            pair_clearances,
            key=lambda item: item["minimum_center_distance_m"],
            default=None,
        ),
        "planned_events": event_results,
    }


def normalize_encounter_mix(value: dict[str, float] | None) -> dict[str, float]:
    """Validate and normalize crossing, head-on and overtaking weights."""
    mix = dict(DEFAULT_ENCOUNTER_MIX if value is None else value)
    if set(mix) != set(DEFAULT_ENCOUNTER_MIX):
        raise ValueError("encounter_mix must contain crossing, head_on and overtaking")
    if any(not np.isfinite(weight) or weight < 0.0 for weight in mix.values()):
        raise ValueError("encounter mix weights must be finite and non-negative")
    total = float(sum(mix.values()))
    if total <= 0.0:
        raise ValueError("encounter mix weights must have a positive sum")
    return {name: round(float(weight) / total, 12) for name, weight in mix.items()}


def allocate_encounter_counts(target_count: int, encounter_mix: dict[str, float]) -> dict[str, int]:
    """Allocate an exact integer target count using largest remainders."""
    normalized = normalize_encounter_mix(encounter_mix)
    raw = {name: normalized[name] * target_count for name in DEFAULT_ENCOUNTER_MIX}
    output = {name: int(np.floor(value)) for name, value in raw.items()}
    remainder = target_count - sum(output.values())
    priority = {"crossing": 2, "head_on": 1, "overtaking": 0}
    ranked = sorted(raw, key=lambda name: (raw[name] - output[name], priority[name]), reverse=True)
    for name in ranked[:remainder]:
        output[name] += 1
    return output


def _build_route_traffic_document(
    scenario_id: str,
    seed: int,
    target_count: int,
    encounter_mix: dict[str, float],
    *,
    dt_sim: float,
) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    counts = allocate_encounter_counts(target_count, encounter_mix)
    roles = ["head_on"] * counts["head_on"]
    roles.extend("crossing_give_way" if index % 2 == 0 else "crossing_stand_on" for index in range(counts["crossing"]))
    roles.extend("overtaking" if index % 2 == 0 else "overtaken" for index in range(counts["overtaking"]))
    rng.shuffle(roles)

    # Encounters are distributed through the useful part of Ship0's route. A
    # small seeded jitter avoids artificial rows without changing reproducibility.
    event_times = np.linspace(55.0, 505.0, target_count)
    event_times += rng.uniform(-2.0, 2.0, target_count)
    ships = [_ownship_document()]
    for identifier, (role, event_time) in enumerate(zip(roles, event_times, strict=True), start=1):
        for attempt in range(100):
            shifted_time = 55.0 + ((float(event_time) - 55.0 + attempt * 7.3) % 450.0)
            candidate = _route_target_document(identifier, role, shifted_time, rng)
            if _candidate_is_clear(candidate, ships, require_full_transit=target_count <= DEFAULT_TARGET_COUNT):
                ships.append(candidate)
                break
        else:
            raise RuntimeError(f"could not place target ship {identifier} without initial overlap")
    document = _base_document(scenario_id, dt_sim=dt_sim, target_count=target_count)
    document["ship_list"] = ships
    return document


def _candidate_is_clear(
    candidate: dict[str, Any],
    existing_ships: list[dict[str, Any]],
    *,
    require_full_transit: bool,
) -> bool:
    for existing in existing_ships:
        if not _windows_overlap(candidate, existing):
            continue
        start = max(float(candidate["t_start"]), float(existing.get("t_start", 0.0)))
        end = min(float(candidate["t_end"]), float(existing.get("t_end", BUSY_WATER_DURATION_S)))
        times = [start]
        if require_full_transit and int(existing["id"]) != 0:
            times = np.linspace(start, end, max(2, int(np.ceil((end - start) / 2.0)) + 1))
        minimum = min(
            float(np.linalg.norm(_nominal_position(candidate, time_s) - _nominal_position(existing, time_s)))
            for time_s in times
        )
        required = float(np.hypot(_SHIP_LENGTH_M, _SHIP_WIDTH_M) + 5.0)
        if minimum < required:
            return False
    return True


def _route_target_document(
    identifier: int,
    role: str,
    event_time_s: float,
    rng: np.random.Generator,
) -> dict[str, Any]:
    conflict = _OS_START_NE + velocity_ne(_OS_SPEED_MPS, 0.0) * event_time_s
    lane_jitter = float(rng.uniform(-45.0, 45.0))
    north_min = max(_MAP_ORIGIN_NE[0] + 100.0, float(conflict[0] - 500.0))
    north_max = min(_MAP_ORIGIN_NE[0] + _MAP_SIZE_NE[0] - 100.0, float(conflict[0] + 500.0))
    east_min = float(_OS_START_NE[1] - 120.0)
    east_max = float(_OS_START_NE[1] + 180.0)

    if role == "head_on":
        speed = float(rng.uniform(4.5, 6.5))
        east = float(_OS_START_NE[1] + lane_jitter * 0.7)
        first = np.array([north_min, east])
        second = np.array([north_max, east])
        desired_sign = -1
    elif role in {"crossing_give_way", "crossing_stand_on"}:
        speed = float(rng.uniform(3.5, 6.5))
        north = float(conflict[0] + lane_jitter)
        first = np.array([north, east_min])
        second = np.array([north, east_max])
        desired_sign = -1 if role == "crossing_give_way" else 1
    else:
        speed = float(rng.uniform(3.0, 4.5) if role == "overtaking" else rng.uniform(7.0, 8.5))
        east = float(_OS_START_NE[1] + lane_jitter)
        first = np.array([north_min, east])
        second = np.array([north_max, east])
        desired_sign = 1

    conflict_on_segment = np.array(
        [float(np.clip(conflict[0], north_min, north_max)), float(np.clip(conflict[1], east_min, east_max))]
    )
    if role == "head_on" or role in {"overtaking", "overtaken"}:
        conflict_on_segment[1] = first[1]
    else:
        conflict_on_segment[0] = first[0]
    position, direction, t_start, t_end, entry, exit_point = single_pass_state_at_event(
        first,
        second,
        speed,
        event_time_s,
        conflict_on_segment,
        desired_sign,
    )
    course_deg = float(np.rad2deg(np.arctan2(direction[1], direction[0])) % 360.0)
    return _target_ship_document(
        identifier,
        position,
        speed,
        course_deg,
        t_start=t_start,
        t_end=t_end,
        waypoints=(entry, exit_point),
        encounter_role=role,
    )


def single_pass_state_at_event(
    first: np.ndarray,
    second: np.ndarray,
    speed_mps: float,
    event_time_s: float,
    event_position: np.ndarray,
    event_direction_sign: int,
) -> tuple[np.ndarray, np.ndarray, float, float, np.ndarray, np.ndarray]:
    """Build one active window that reaches an event once, then exits."""
    delta = np.asarray(second, dtype=float) - np.asarray(first, dtype=float)
    length = float(np.linalg.norm(delta))
    if length <= 0.0:
        raise ValueError("single-pass route endpoints must be distinct")
    unit = delta / length
    direction = unit if event_direction_sign >= 0 else -unit
    entry = np.asarray(first if event_direction_sign >= 0 else second, dtype=float)
    exit_point = np.asarray(second if event_direction_sign >= 0 else first, dtype=float)
    event_position = np.asarray(event_position, dtype=float)
    entry_to_event = float(np.clip((event_position - entry) @ direction, 0.0, length))
    travel_time = entry_to_event / speed_mps
    if event_time_s >= travel_time:
        t_start = event_time_s - travel_time
        position = entry.copy()
    else:
        t_start = 0.0
        position = event_position - direction * speed_mps * event_time_s
    t_end = min(
        BUSY_WATER_DURATION_S,
        t_start + float(np.linalg.norm(exit_point - position)) / speed_mps,
    )
    return position, direction, t_start, t_end, entry, exit_point


def _base_document(name: str, *, dt_sim: float, target_count: int) -> dict[str, Any]:
    return {
        "name": name,
        "save_scenario": False,
        "t_start": 0.0,
        "t_end": BUSY_WATER_DURATION_S,
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


def _target_ship_document(
    identifier: int,
    position_ne: np.ndarray,
    speed_mps: float,
    course_deg: float,
    *,
    t_start: float,
    t_end: float,
    waypoints: tuple[np.ndarray, np.ndarray] | None = None,
    encounter_role: str | None = None,
) -> dict[str, Any]:
    if waypoints is None:
        velocity = velocity_ne(speed_mps, np.deg2rad(course_deg))
        active_duration = t_end - t_start
        route_start = np.asarray(position_ne, dtype=float)
        route_end = route_start + velocity * active_duration
    else:
        route_start, route_end = (np.asarray(point, dtype=float) for point in waypoints)
    document = {
        "csog_state": [float(position_ne[0]), float(position_ne[1]), speed_mps, course_deg],
        "waypoints": [
            [float(route_start[0]), float(route_end[0])],
            [float(route_start[1]), float(route_end[1])],
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
    if encounter_role is not None:
        document["encounter_role"] = encounter_role
    return document


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
        float(first.get("t_end", BUSY_WATER_DURATION_S)),
        float(second.get("t_end", BUSY_WATER_DURATION_S)),
    )


def _nominal_position(ship: dict[str, Any], sim_time_s: float) -> np.ndarray:
    return _single_pass_position_velocity(ship, sim_time_s)[0]


def _single_pass_position_velocity(ship: dict[str, Any], sim_time_s: float) -> tuple[np.ndarray, np.ndarray]:
    active_time_s = max(0.0, sim_time_s - float(ship.get("t_start", 0.0)))
    speed = float(ship["csog_state"][2])
    waypoints = np.asarray(ship["waypoints"], dtype=float)
    first = waypoints[:, 0]
    second = waypoints[:, -1]
    delta = second - first
    length = float(np.linalg.norm(delta))
    if length <= 1e-9:
        return np.asarray(ship["csog_state"][:2], dtype=float), np.zeros(2)
    unit = delta / length
    initial = np.asarray(ship["csog_state"][:2], dtype=float)
    initial_velocity = velocity_ne(speed, np.deg2rad(float(ship["csog_state"][3])))
    direction_sign = 1.0 if np.dot(initial_velocity, unit) >= 0.0 else -1.0
    initial_s = float(np.clip(np.dot(initial - first, unit), 0.0, length))
    along = float(np.clip(initial_s + direction_sign * speed * active_time_s, 0.0, length))
    direction = direction_sign * unit
    return first + unit * along, direction * speed


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
            sample_times = np.linspace(start, end, max(2, int(np.ceil((end - start) / 2.0)) + 1))
            distances = np.asarray(
                [
                    np.linalg.norm(_nominal_position(first, time_s) - _nominal_position(second, time_s))
                    for time_s in sample_times
                ]
            )
            minimum_index = int(np.argmin(distances))
            minimum_distance = float(distances[minimum_index])
            output.append(
                {
                    "ship_ids": [int(first["id"]), int(second["id"])],
                    "minimum_center_distance_m": minimum_distance,
                    "required_center_distance_m": required,
                    "time_s": float(sample_times[minimum_index]),
                }
            )
    return output


def _nominal_encounter_results(document: dict[str, Any]) -> list[dict[str, Any]]:
    ships = list(document["ship_list"])
    own = ships[0]
    output = []
    scenario_end = float(document["t_end"])
    for target in ships[1:]:
        start = float(target.get("t_start", 0.0))
        end = float(target.get("t_end", scenario_end))
        sample_times = np.linspace(start, end, max(2, int((end - start) / 2.0) + 1))
        distances = np.asarray(
            [np.linalg.norm(_nominal_position(target, time_s) - _nominal_position(own, time_s)) for time_s in sample_times]
        )
        closest_time = float(sample_times[int(np.argmin(distances))])
        probe_time = max(0.0, closest_time - 20.0)
        own_position, own_velocity = _single_pass_position_velocity(own, probe_time)
        target_position, target_velocity = _single_pass_position_velocity(target, probe_time)
        detected, dcpa_m, _, signed_tcpa_s, _ = classify_geometry(
            own_position,
            own_velocity,
            target_position,
            target_velocity,
            _SHIP_LENGTH_M,
            _SHIP_LENGTH_M,
        )
        output.append(
            {
                "target_id": int(target["id"]),
                "time_s": closest_time,
                "configured_encounter": _configured_encounter_role(target),
                "detected_encounter": detected,
                "nominal_dcpa_m": dcpa_m,
                "signed_tcpa_s_at_window_probe": signed_tcpa_s,
            }
        )
    return output


def _configured_encounter_role(ship: dict[str, Any]) -> str:
    if "encounter_role" in ship:
        return str(ship["encounter_role"])
    waypoints = np.asarray(ship["waypoints"], dtype=float)
    route_delta = waypoints[:, -1] - waypoints[:, 0]
    velocity = velocity_ne(float(ship["csog_state"][2]), np.deg2rad(float(ship["csog_state"][3])))
    if abs(route_delta[1]) > abs(route_delta[0]):
        return "crossing_stand_on" if velocity[1] > 0.0 else "crossing_give_way"
    if velocity[0] < 0.0:
        return "head_on"
    return "overtaking" if float(ship["csog_state"][2]) < _OS_SPEED_MPS else "overtaken"
