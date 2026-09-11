"""Finite-route arrival references and the matching measured arrival criterion."""

from __future__ import annotations

import math

import numpy as np

GOAL_POSITION_TOLERANCE_M = 5.0
GOAL_SPEED_TOLERANCE_MPS = 0.05


def terminal_weight(distance: float, cruise: float, horizon_s: float, response_s: float, deceleration: float) -> float:
    """Introduce the terminal objective continuously over the braking reserve."""
    reserve = cruise * response_s + cruise * cruise / max(deceleration, 1e-9)
    fraction = float(np.clip((cruise * horizon_s - distance) / max(reserve, 1.0), 0.0, 1.0))
    return fraction * fraction * (3.0 - 2.0 * fraction)


def on_final_leg(waypoints: np.ndarray, position: np.ndarray) -> bool:
    """Identify the nearest finite mission leg using NE waypoint rows."""
    if len(waypoints) < 2:
        return False
    starts, legs = waypoints[:-1], np.diff(waypoints, axis=0)
    lengths2 = np.sum(legs * legs, axis=1)
    fractions = np.clip(np.sum((position - starts) * legs, axis=1) / np.maximum(lengths2, 1e-9), 0.0, 1.0)
    distances = np.linalg.norm(starts + fractions[:, None] * legs - position, axis=1)
    return int(np.argmin(distances)) == len(legs) - 1


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
    lag_s: float = 0.0,
) -> tuple[tuple[float, ...], tuple[float, ...], tuple[float, ...], tuple[float, float] | None] | None:
    """Build a reachable braking reference on the final mission leg."""
    if len(waypoints) < 2 or cruise <= 0.0:
        return None
    points = np.asarray(waypoints, dtype=float)
    origin = np.asarray(position, dtype=float)
    starts, legs = points[:-1], np.diff(points, axis=0)
    if not on_final_leg(points, origin):
        return None
    goal = points[-1]
    terminal_in_window = np.linalg.norm(goal - origin) <= cruise * dt * count
    location = origin.copy()
    normal = np.array([-math.sin(route_bearing), math.cos(route_bearing)])
    brake = max(0.5 * deceleration, 1e-3)
    reaction = brake * response_s
    # The approach reserve above intentionally over-brakes from far out, but
    # its tail decays like remaining/response_s: with the padded response
    # reserve (~4 * speed-loop lag) that asymptote drops below the executed
    # command band tens of metres out and the hull stalls short of the goal
    # (crossing-E4: stopped 13.5 m short at 0.01 m/s under a 0.13 m/s
    # reference). Model the terminal stop with the first-order speed-loop lag
    # instead: a commanded speed v still covers v * lag + v^2 / (2 * brake)
    # before it dies, so that coast distance - not the padded reserve - is
    # what must fit inside the goal tolerance.
    lag = max(float(lag_s), dt)

    def coast_distance(commanded: float) -> float:
        return commanded * lag + commanded * commanded / (2.0 * brake)

    def coast_inverse(distance: float) -> float:
        if distance <= 0.0:
            return 0.0
        return -brake * lag + math.sqrt((brake * lag) ** 2 + 2.0 * brake * distance)

    # Hold the approach at the slowest clearly-executed command whose model
    # stop fits inside twice the goal tolerance, and cap the tail by the
    # command whose stop lands half a tolerance short of the goal.
    hold_speed = coast_inverse(2.0 * GOAL_POSITION_TOLERANCE_M)
    tail_cap_limit = GOAL_POSITION_TOLERANCE_M
    tangent = legs[-1] / max(float(np.linalg.norm(legs[-1])), 1e-9)
    leg_normal = np.array([-tangent[1], tangent[0]])
    leg_bearing = math.atan2(tangent[1], tangent[0])
    cross = float((origin - starts[-1]) @ leg_normal)
    heading_error = math.atan2(math.sin(heading - leg_bearing), math.cos(heading - leg_bearing))
    join_length, join_weight = _rejoin_geometry(
        cross, heading_error, float((goal - origin) @ tangent), cruise, turn_rate, brake, response_s, dt
    )
    headings, lateral, speeds = [], [], []
    for _ in range(count):
        error = goal - location
        distance = float(np.linalg.norm(error))
        position_epsilon = 0.05 * GOAL_POSITION_TOLERANCE_M
        remaining = max(0.0, distance - position_epsilon)
        requested_speed = min(cruise, math.sqrt(reaction * reaction + 2.0 * brake * remaining) - reaction)
        if remaining > tail_cap_limit:
            executable = min(hold_speed, coast_inverse(remaining - 0.5 * GOAL_POSITION_TOLERANCE_M))
            requested_speed = min(cruise, max(requested_speed, executable))
        speed = float(np.clip(requested_speed, max(0.0, speed - deceleration * dt), speed + deceleration * dt))
        desired = math.atan2(error[1], error[0]) if distance > position_epsilon else heading
        if join_weight > 0.0 and distance > GOAL_POSITION_TOLERANCE_M:
            progress = max(0.0, float((location - origin) @ tangent))
            preview = min(
                float((goal - origin) @ tangent), progress + max(2.0 * speed * dt, speed / max(2.0 * turn_rate, 1e-9), 5.0)
            )
            q = min(1.0, preview / join_length)
            curve_y, _, _ = _join_curve(q, cross, math.tan(heading_error), join_length)
            capture_point = origin - cross * leg_normal + preview * tangent + curve_y * leg_normal
            capture = math.atan2(capture_point[1] - location[1], capture_point[0] - location[0])
            desired += join_weight * math.atan2(math.sin(capture - desired), math.cos(capture - desired))
        delta = math.atan2(math.sin(desired - heading), math.cos(desired - heading))
        heading += float(np.clip(delta, -turn_rate * dt, turn_rate * dt))
        headings.append(heading)
        lateral.append(float((location - np.asarray(route_anchor)) @ normal))
        speeds.append(speed)
        location += speed * dt * np.array([math.cos(heading), math.sin(heading)])
    terminal = None
    if terminal_in_window:
        # Do not force an early shortcut just to reach the goal at horizon end.
        # Track the reachable rejoin/braking suffix until stopping fits inside it.
        endpoint = goal if np.linalg.norm(goal - location) <= GOAL_POSITION_TOLERANCE_M else location
        terminal = tuple(float(v) for v in endpoint - origin)
    return tuple(headings), tuple(lateral), tuple(speeds), terminal


def _join_curve(
    q: float | np.ndarray, cross: float, slope: float, length: float
) -> tuple[float | np.ndarray, float | np.ndarray, float | np.ndarray]:
    """Quintic lateral capture with matched entry tangent and zero exit curvature."""
    y = cross * (1 - 10 * q**3 + 15 * q**4 - 6 * q**5) + slope * length * (q - 6 * q**3 + 8 * q**4 - 3 * q**5)
    dy = cross / length * (-30 * q**2 + 60 * q**3 - 30 * q**4) + slope * (1 - 18 * q**2 + 32 * q**3 - 15 * q**4)
    ddy = cross / length**2 * (-60 * q + 180 * q**2 - 120 * q**3) + slope / length * (-36 * q + 96 * q**2 - 60 * q**3)
    return y, dy, ddy


def _rejoin_geometry(
    cross: float,
    heading_error: float,
    remaining: float,
    cruise: float,
    turn_rate: float,
    brake: float,
    response_s: float,
    dt: float,
) -> tuple[float, float]:
    """Reserve braking room and check capture curvature before choosing a rejoin."""
    if abs(cross) <= GOAL_POSITION_TOLERANCE_M or abs(heading_error) >= math.radians(75):
        return 1.0, 0.0
    radius = cruise / max(turn_rate, 1e-9)
    available = remaining - cruise * response_s - cruise**2 / (2.0 * brake)
    length = max(abs(cross), 2.0 * radius, 2.0 * cruise * dt)
    preferred_length = max(2.0 * abs(cross), 2.0 * radius, 2.0 * cruise * dt)
    q = np.linspace(0.0, 1.0, 65)
    while length < available:
        _, slope, second = _join_curve(q, cross, math.tan(heading_error), length)
        if float(np.max(np.abs(second) / (1.0 + slope * slope) ** 1.5)) <= 1.0 / radius:
            length = max(length, min(preferred_length, available - max(radius, cruise * dt)))
            fraction = float(np.clip((available - length) / max(radius, cruise * dt), 0.0, 1.0))
            return length, fraction * fraction * (3.0 - 2.0 * fraction)
        length *= 1.1
    return 1.0, 0.0
