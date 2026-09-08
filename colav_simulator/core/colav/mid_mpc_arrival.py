"""Finite-route arrival references and the matching measured arrival criterion."""

from __future__ import annotations

import math

import numpy as np

GOAL_POSITION_TOLERANCE_M = 5.0
GOAL_SPEED_TOLERANCE_MPS = 0.05


def goal_reached(state: np.ndarray, waypoints: np.ndarray) -> bool | None:
    """Require measured proximity and near-zero speed at the final waypoint."""
    if waypoints.ndim != 2 or waypoints.shape[1] < 2:
        return None
    return bool(
        np.linalg.norm(state[:2] - waypoints[:2, -1]) <= GOAL_POSITION_TOLERANCE_M
        and np.linalg.norm(state[3:5]) <= GOAL_SPEED_TOLERANCE_MPS
    )


def arrival_references(
    waypoints: tuple[tuple[float, float], ...],
    position: tuple[float, float],
    heading: float,
    speed: float,
    cruise: float,
    dt: float,
    count: int,
    deceleration: float,
    turn_rate: float,
    response_s: float,
    route_anchor: tuple[float, float],
    route_bearing: float,
) -> tuple[tuple[float, ...], tuple[float, ...], tuple[float, ...], tuple[float, float]] | None:
    """Build a reachable braking reference on the final mission leg."""
    if len(waypoints) < 2 or cruise <= 0.0:
        return None
    points = np.asarray(waypoints, dtype=float)
    origin = np.asarray(position, dtype=float)
    starts, legs = points[:-1], np.diff(points, axis=0)
    lengths2 = np.sum(legs * legs, axis=1)
    fractions = np.clip(np.sum((origin - starts) * legs, axis=1) / np.maximum(lengths2, 1e-9), 0.0, 1.0)
    distances = np.linalg.norm(starts + fractions[:, None] * legs - origin, axis=1)
    if int(np.argmin(distances)) != len(legs) - 1:
        return None
    goal = points[-1]
    if np.linalg.norm(goal - origin) > cruise * dt * count:
        return None
    location = origin.copy()
    normal = np.array([-math.sin(route_bearing), math.cos(route_bearing)])
    brake = max(0.5 * deceleration, 1e-3)
    reaction = brake * response_s
    headings, lateral, speeds = [], [], []
    for _ in range(count):
        error = goal - location
        distance = float(np.linalg.norm(error))
        remaining = max(0.0, distance - 0.5 * GOAL_POSITION_TOLERANCE_M)
        requested_speed = min(cruise, math.sqrt(reaction * reaction + 2.0 * brake * remaining) - reaction)
        speed = float(np.clip(requested_speed, max(0.0, speed - deceleration * dt), speed + deceleration * dt))
        desired = math.atan2(error[1], error[0]) if distance > GOAL_POSITION_TOLERANCE_M else heading
        delta = math.atan2(math.sin(desired - heading), math.cos(desired - heading))
        heading += float(np.clip(delta, -turn_rate * dt, turn_rate * dt))
        headings.append(heading)
        lateral.append(float((location - np.asarray(route_anchor)) @ normal))
        speeds.append(speed)
        location += speed * dt * np.array([math.cos(heading), math.sin(heading)])
    return tuple(headings), tuple(lateral), tuple(speeds), tuple(float(v) for v in goal - origin)
