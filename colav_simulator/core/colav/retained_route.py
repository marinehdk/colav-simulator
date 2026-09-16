"""Planner constraints and route output for a GNC-owned retained local path."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass

import numpy as np


@dataclass(frozen=True)
class RetainedRouteConstraint:
    reference_id: str
    points_ne_m: tuple[tuple[float, float], ...]
    speed_mps: tuple[float, ...]
    navigation_modes: tuple[str, ...]
    minimum_update_distance_m: float
    minimum_segment_m: float
    lateral_limit_m: float
    execution_speed_mps: tuple[float, ...] | None = None

    def __post_init__(self) -> None:
        """Freeze and validate the execution authority supplied by GNC."""
        points = tuple(tuple(map(float, p)) for p in self.points_ne_m)
        speeds = tuple(map(float, self.speed_mps))
        modes = tuple(self.navigation_modes)
        if not self.reference_id or len(points) < 2 or any(len(p) != 2 for p in points):
            raise ValueError("Retained route requires an identified finite polyline")
        if len(speeds) != len(points) or len(modes) != len(points):
            raise ValueError("Retained route metadata must align with geometry")
        if not np.isfinite(points).all() or not np.isfinite(speeds).all() or min(speeds) < 0:
            raise ValueError("Retained route coordinates and speeds must be finite")
        limits = (self.minimum_update_distance_m, self.minimum_segment_m, self.lateral_limit_m)
        if not np.isfinite(limits).all() or min(limits) <= 0:
            raise ValueError("GNC route limits must be finite and positive")
        object.__setattr__(self, "points_ne_m", points)
        object.__setattr__(self, "speed_mps", speeds)
        object.__setattr__(self, "navigation_modes", modes)
        if self.execution_speed_mps is not None:
            admitted = tuple(map(float, self.execution_speed_mps))
            if len(admitted) != len(points) or not np.isfinite(admitted).all() or min(admitted) < 0:
                raise ValueError("GNC execution speeds must be finite and align with the retained route")
            object.__setattr__(self, "execution_speed_mps", admitted)

    @property
    def semantic_hash(self) -> str:
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class RetainedPrefixPlan:
    constraint: RetainedRouteConstraint
    points_ne_m: tuple[tuple[float, float], ...]
    route_speed_mps: tuple[float, ...]
    navigation_modes: tuple[str, ...]
    course_rad: tuple[float, ...]
    speed_mps: tuple[float, ...]
    incoming_course_rad: float
    retained_point_count: int
    corridor_points_m: tuple[tuple[float, float], ...]


def _projection(points: np.ndarray, position: np.ndarray) -> tuple[float, np.ndarray]:
    legs = np.diff(points, axis=0)
    lengths = np.linalg.norm(legs, axis=1)
    progress = np.r_[0.0, np.cumsum(lengths)]
    fractions = np.clip(np.sum((position - points[:-1]) * legs, axis=1) / np.maximum(lengths**2, 1e-12), 0, 1)
    projected = points[:-1] + fractions[:, None] * legs
    index = int(np.argmin(np.linalg.norm(projected - position, axis=1)))
    return float(progress[index] + fractions[index] * lengths[index]), progress


def _reference_transition(
    anchor: np.ndarray,
    incoming: float,
    delta: float,
    constraint: RetainedRouteConstraint,
    max_speed_mps: float,
    rot_max_rad_s: float,
) -> list[tuple[float, float]]:
    """Plan a tangent-continuous arc within the GNC yaw-rate radius."""
    if abs(delta) < 1e-8:
        return []
    # The unchanged prefix already satisfies the update-distance gate. The
    # new arc needs the yaw-rate radius and a valid segment, not a second
    # entire update-distance reservation that postpones near-shore turning.
    radius = max(2 * max_speed_mps / rot_max_rad_s, constraint.minimum_segment_m / abs(delta))
    steps = max(1, int(radius * abs(delta) / constraint.minimum_segment_m))
    sign = math.copysign(1.0, delta)
    return [
        tuple(
            anchor + radius / sign * np.array([math.sin(angle) - math.sin(incoming), math.cos(incoming) - math.cos(angle)])
        )
        for angle in np.linspace(incoming, incoming + delta, steps + 1)[1:]
    ]


def compile_retained_prefix(
    constraint: RetainedRouteConstraint,
    ownship: np.ndarray,
    *,
    horizon_steps: int,
    dt_s: float,
    max_speed_mps: float,
    rot_max_rad_s: float,
    accel_max_mps2: float,
    min_speed_mps: float = 0.0,
    target_course_rad: float | None = None,
    navigation_mode: str = "avoidance",
) -> RetainedPrefixPlan:
    """Compile a reachable prefix without relaxing the source motion envelope."""
    shapes = ((1.0, 1.0, 2.0), (1.5, 1.0, 3.0), (0.5, 1.0, 3.0), (1.0, 1.5, 3.0))
    if min_speed_mps <= 0.0:
        shapes = shapes[:1]
    for shape in shapes:
        try:
            return _compile_retained_prefix(
                constraint, ownship, horizon_steps=horizon_steps, dt_s=dt_s,
                max_speed_mps=max_speed_mps, rot_max_rad_s=rot_max_rad_s,
                accel_max_mps2=accel_max_mps2, min_speed_mps=min_speed_mps,
                target_course_rad=target_course_rad, navigation_mode=navigation_mode, shape=shape,
            )
        except _UnreachablePrefix:
            continue
    raise _UnreachablePrefix("Retained GNC path cannot be reached within the active motion envelope")


class _UnreachablePrefix(ValueError):
    """No sampled interception meets the unchanged source motion envelope."""


def _compile_retained_prefix(
    constraint: RetainedRouteConstraint,
    ownship: np.ndarray,
    *,
    horizon_steps: int,
    dt_s: float,
    max_speed_mps: float,
    rot_max_rad_s: float,
    accel_max_mps2: float,
    min_speed_mps: float = 0.0,
    target_course_rad: float | None = None,
    navigation_mode: str = "avoidance",
    shape: tuple[float, float, float] = (1.0, 1.0, 2.0),
) -> RetainedPrefixPlan:
    """Fix a feasible interception forecast before optimizing the free suffix.

    The reference geometry itself stays verbatim. The fixed kinematic forecast
    joins measured position/course to its future anchor; it is not a second GNC
    controller or a claim of a native plant rollout.
    """
    points = np.asarray(constraint.points_ne_m)
    along, progress = _projection(points, ownship[:2])
    local_start = max(0, int(np.searchsorted(progress, along, side="right")) - 2)
    corridor_points = tuple(map(tuple, points[local_start:] - ownship[:2]))
    own_speed = float(np.hypot(ownship[3], ownship[4]))
    if not math.isfinite(min_speed_mps) or not 0.0 <= min_speed_mps <= max_speed_mps:
        raise ValueError("Retained-route minimum speed must lie within the vessel envelope")
    # Preserve measured under-speed transients, but never invent additional
    # braking below the source's steerage floor just to fit a tight curve.
    forecast_floor = min(own_speed, min_speed_mps)
    minimum_anchor_along = min(along + constraint.minimum_update_distance_m, float(progress[-1]))
    # A route can be geometrically admissible to GNC while the measured vessel
    # is just outside the first 160 m interception chord.  Extend the retained
    # anchor in route order, preserving the original near segment, until the
    # planner can produce a rate-feasible prefix.  This is still planner-owned
    # geometry; the GNC admission limits and route itself are unchanged.
    extension_step = max(constraint.minimum_segment_m, 1.0)
    anchor_candidates = list(
        dict.fromkeys(
            min(minimum_anchor_along + extension * extension_step, float(progress[-1]))
            for extension in range(min(16, max(1, horizon_steps - 3)))
        )
    )
    current_segment = max(0, int(np.searchsorted(progress, along, side="right")) - 1)
    refined_segments: set[int] = set()
    for candidate_along in anchor_candidates:
        segment = min(int(np.searchsorted(progress, candidate_along, side="right")) - 1, len(points) - 2)
        segment = max(segment, 0)
        # Avoid creating a sub-floor leg at an inserted anchor.
        anchor_along = (
            min(float(progress[segment] + constraint.minimum_segment_m), float(progress[segment + 1]))
            if candidate_along - progress[segment] < constraint.minimum_segment_m else candidate_along
        )
        fraction = (anchor_along - progress[segment]) / max(progress[segment + 1] - progress[segment], 1e-12)
        anchor = points[segment] + fraction * (points[segment + 1] - points[segment])
        incoming = math.atan2(*(points[segment + 1] - points[segment])[::-1])
        retained = [tuple(p) for p in points[: segment + 1]]
        retained.append(tuple(anchor))
        anchor_speed = constraint.speed_mps[segment + 1]
        if constraint.navigation_modes[segment + 1] == "dp_hold" and fraction < 1.0:
            anchor_speed = constraint.speed_mps[segment]
        route_speeds = list(constraint.speed_mps[: segment + 1]) + [anchor_speed]
        modes = list(constraint.navigation_modes[: segment + 1]) + [navigation_mode]
        target = incoming if target_course_rad is None else target_course_rad
        delta = math.atan2(math.sin(target - incoming), math.cos(target - incoming))
        transition = _reference_transition(anchor, incoming, delta, constraint, max_speed_mps, rot_max_rad_s)
        retained.extend(transition)
        route_speeds.extend([anchor_speed if abs(delta) < 1e-8 else max_speed_mps] * len(transition))
        modes.extend([navigation_mode] * len(transition))
        join = np.asarray(retained[-1])
        forecast_speed_cap = (
            min(max_speed_mps, *constraint.execution_speed_mps[current_segment : segment + 2])
            if constraint.execution_speed_mps is not None else max_speed_mps
        )
        curve = _interception_curve(ownship, join, target, shape)
        distances = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(curve, axis=0), axis=1))]
        for count in range(2, horizon_steps - 1):
            if distances[-1] < forecast_floor * count * dt_s - 1e-9:
                break
            kinematics = _prefix_kinematics(
                curve,
                distances,
                count,
                ownship,
                max_speed_mps,
                accel_max_mps2,
                dt_s,
                forecast_speed_cap,
            )
            if kinematics is None:
                continue
            course, speed = kinematics
            # A sampled interception must also join the retained route tangent;
            # position alone permits a sharp corner absent from the forecast.
            if (
                np.max(speed) <= max_speed_mps + 1e-9
                and np.min(speed) >= forecast_floor - 1e-9
                and abs(math.atan2(math.sin(course[-1] - target), math.cos(course[-1] - target)))
                <= rot_max_rad_s * dt_s + 1e-9
                and np.max(np.abs(np.diff(np.r_[own_speed, speed]))) <= accel_max_mps2 * dt_s + 1e-9
                and np.max(np.abs(np.diff(np.r_[ownship[2], course]))) <= rot_max_rad_s * dt_s + 1e-9
            ):
                return RetainedPrefixPlan(
                    constraint,
                    tuple(retained),
                    tuple(route_speeds),
                    tuple(modes),
                    tuple(course),
                    tuple(speed),
                    incoming,
                    segment + 2,
                    corridor_points,
                )
        if forecast_floor > 0 and segment not in refined_segments:
            refined_segments.add(segment)
            anchor_candidates.extend(
                _timed_anchor_candidates(
                    constraint,
                    ownship,
                    segment,
                    join - anchor,
                    target,
                    horizon_steps=horizon_steps,
                    dt_s=dt_s,
                    max_speed=max_speed_mps,
                    acceleration=accel_max_mps2,
                    floor=forecast_floor,
                    cap=forecast_speed_cap,
                    shape=shape,
                )
            )
    raise _UnreachablePrefix("Retained GNC path cannot be reached within the active motion envelope")


def _timed_anchor_candidates(
    constraint: RetainedRouteConstraint,
    ownship: np.ndarray,
    segment: int,
    endpoint_offset: np.ndarray,
    target: float,
    *,
    horizon_steps: int,
    dt_s: float,
    max_speed: float,
    acceleration: float,
    floor: float,
    cap: float,
    shape: tuple[float, float, float],
) -> list[float]:
    """Refine a retained join to fit whole time intervals in a narrow speed band."""
    points = np.asarray(constraint.points_ne_m)
    along, progress = _projection(points, ownship[:2])
    lower_anchor = max(along + constraint.minimum_update_distance_m, progress[segment] + constraint.minimum_segment_m)
    upper_anchor = progress[segment + 1]
    if upper_anchor <= lower_anchor + 1e-9 or cap < floor:
        return []

    def distance_at(value: float) -> float:
        ratio = (value - progress[segment]) / max(progress[segment + 1] - progress[segment], 1e-12)
        endpoint = points[segment] + ratio * (points[segment + 1] - points[segment]) + endpoint_offset
        trial = _interception_curve(ownship, endpoint, target, shape)
        return float(np.linalg.norm(np.diff(trial, axis=0), axis=1).sum())

    lower_distance, upper_distance = distance_at(lower_anchor), distance_at(upper_anchor)
    own_speed = float(np.hypot(ownship[3], ownship[4]))
    anchors = []
    for count in range(2, horizon_steps - 1):
        steps = np.arange(1, count + 1)
        lower_speed = np.maximum(floor, own_speed - acceleration * dt_s * steps)
        upper_speed = np.minimum(max_speed, np.maximum(cap, lower_speed))
        upper_speed = np.minimum(upper_speed, own_speed + acceleration * dt_s * steps)
        desired_distance = float(0.5 * (lower_speed + upper_speed).sum() * dt_s)
        if not lower_distance < desired_distance < upper_distance:
            continue
        low, high = float(lower_anchor), float(upper_anchor)
        for _ in range(32):
            midpoint = 0.5 * (low + high)
            if distance_at(midpoint) < desired_distance:
                low = midpoint
            else:
                high = midpoint
        anchors.append(0.5 * (low + high))
    return anchors


def _interception_curve(
    ownship: np.ndarray, join: np.ndarray, target: float,
    shape: tuple[float, float, float] = (1.0, 1.0, 2.0),
) -> np.ndarray:
    """Build a local Hermite curve with no spurious initial counter-turn."""
    chord = float(np.linalg.norm(join - ownship[:2]))
    # Chord-length endpoint derivatives avoid artificial curvature spikes
    # caused by shrinking both handles during ordinary route recovery.
    start_tangent = shape[0] * chord * np.array([math.cos(ownship[2]), math.sin(ownship[2])])
    end_length = shape[1] * chord
    normal = np.array([-math.sin(ownship[2]), math.cos(ownship[2])])
    lateral = float((join - ownship[:2]) @ normal)
    end_lateral = math.sin(target - ownship[2])
    if lateral * end_lateral > 0.0:
        # The initial lateral derivative is zero in the measured-course frame.
        # Three times displacement is the cubic control-polygon bound for
        # no initial counter-turn. The default uses two for earlier onset.
        end_length = min(end_length, shape[2] * abs(lateral / end_lateral))
    end_tangent = end_length * np.array([math.cos(target), math.sin(target)])
    t = np.linspace(0.0, 1.0, 501)[:, None]
    return (
        (t**3 - 2 * t**2 + t) * start_tangent + (-2 * t**3 + 3 * t**2) * (join - ownship[:2]) + (t**3 - t**2) * end_tangent
    )


def _prefix_kinematics(
    curve: np.ndarray,
    distances: np.ndarray,
    count: int,
    ownship: np.ndarray,
    max_speed: float,
    acceleration: float,
    dt_s: float,
    forecast_speed_cap: float,
) -> tuple[np.ndarray, np.ndarray] | None:
    """Reserve sampled arc/chord error without changing the physical limits."""
    initial_speed = float(np.hypot(ownship[3], ownship[4]))
    sampling_acceleration = acceleration
    for _ in range(3):
        samples = _prefix_distance_samples(
            float(distances[-1]),
            count,
            initial_speed,
            max_speed,
            sampling_acceleration,
            dt_s,
            forecast_speed_cap,
        )
        if samples is None:
            return None
        points = np.column_stack([np.interp(samples, distances, curve[:, axis]) for axis in range(2)])
        legs = np.diff(points, axis=0)
        speed = np.linalg.norm(legs, axis=1) / dt_s
        course = np.unwrap(np.r_[ownship[2], np.arctan2(legs[:, 1], legs[:, 0])])[1:]
        if np.max(np.abs(np.diff(np.r_[initial_speed, speed]))) <= acceleration * dt_s + 1e-9:
            return course, speed
        # Each segment speed differs from its arc-speed sample by at most D;
        # adjacent differences therefore need a conservative 2*D reserve.
        deficit = float(np.max(np.abs(np.diff(samples) / dt_s - speed)))
        sampling_acceleration = min(sampling_acceleration, max(0.0, acceleration - (2.0 * deficit + 1e-8) / dt_s))
    return None


def _prefix_distance_samples(
    distance_m: float,
    count: int,
    initial_speed: float,
    max_speed: float,
    acceleration: float,
    dt_s: float,
    forecast_speed_cap: float,
) -> np.ndarray | None:
    """Reach the anchor with a rate-bounded ramp instead of uniform speed.

    Uniform spacing has artificial feasibility gaps: 161 m takes over four
    5-second intervals at 8 m/s, but a uniform five-interval speed would demand
    excessive first-step braking. A short ramp reaches the same anchor.
    """
    steps = np.arange(1, count + 1)
    lower = np.maximum(0.0, initial_speed - acceleration * dt_s * steps)
    upper = np.minimum(max_speed, np.maximum(forecast_speed_cap, lower))
    upper = np.minimum(upper, initial_speed + acceleration * dt_s * steps)
    required_sum = distance_m / dt_s
    if np.any(lower > upper) or required_sum < lower.sum() - 1e-9 or required_sum > upper.sum() + 1e-9:
        return None
    low, high = 0.0, max_speed
    for _ in range(50):
        target = (low + high) / 2.0
        if np.clip(target, lower, upper).sum() < required_sum:
            low = target
        else:
            high = target
    samples = np.r_[0.0, np.cumsum(np.clip((low + high) / 2.0, lower, upper)) * dt_s]
    samples[-1] = distance_m
    return samples


def _segment_enters_arrival_region(a: np.ndarray, b: np.ndarray, goal: np.ndarray, radius_m: float) -> bool:
    """True when segment a-b passes within the goal's arrival region."""
    span = b - a
    length2 = float(span @ span)
    fraction = 0.0 if length2 <= 0.0 else float(np.clip((goal - a) @ span / length2, 0.0, 1.0))
    return float(np.linalg.norm(a + fraction * span - goal)) <= radius_m


def compile_execution_route(
    plan: RetainedPrefixPlan,
    predicted: np.ndarray,
    *,
    arrival_boundary: tuple[tuple[float, float], float] | None = None,
) -> dict:
    """Emit the planner-owned native route; transport must not reshape it.

    While ``arrival_boundary`` (goal position, radius) is set, the optimized
    suffix stops before the first segment that would cross into the shared
    arrival region. Arrival-region entry is authorized only by plans whose
    arrival references have captured the mission leg (the L4 navigation
    capture gate); an encounter tail that merely passes over the goal must
    not promise the GNC an off-leg arrival.
    """
    count = len(plan.course_rad)
    anchor = np.asarray(plan.points_ne_m[-1])
    if np.linalg.norm(predicted[:2, count] - anchor) > 1e-3:
        raise ValueError("Optimizer did not preserve the compiled route anchor")
    goal = np.asarray(arrival_boundary[0], dtype=float) if arrival_boundary is not None else None
    arrival_radius = float(arrival_boundary[1]) if arrival_boundary is not None else None
    points = list(plan.points_ne_m)
    speeds = list(plan.route_speed_mps)
    modes = list(plan.navigation_modes)
    for index in range(count + 1, predicted.shape[1]):
        point = predicted[:2, index]
        if np.linalg.norm(point - np.asarray(points[-1])) >= plan.constraint.minimum_segment_m:
            if goal is not None and _segment_enters_arrival_region(
                np.asarray(points[-1]), point, goal, arrival_radius
            ):
                break
            points.append(tuple(point))
            speeds.append(float(np.hypot(predicted[3, index], predicted[4, index])))
            modes.append(plan.navigation_modes[-1])
    if len(points) <= len(plan.points_ne_m):
        raise ValueError("Optimized suffix has no GNC-admissible segment")
    document = {
        "schema_version": "colav.mid-mpc.execution-route@1",
        "reference_hash": plan.constraint.semantic_hash,
        "reference_id": plan.constraint.reference_id,
        "points_ne_m": points,
        "speed_mps": speeds,
        "navigation_modes": modes,
        "retained_point_count": plan.retained_point_count,
        "prefix_intervals": count,
        "prediction_basis": "kinematic retained-route interception and optimized suffix",
    }
    document["geometry_hash"] = hashlib.sha256(
        json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return document


def course_speed_state(body_state: np.ndarray) -> np.ndarray:
    """Express body-frame ground velocity as COG/SOG without changing motion."""
    state = np.asarray(body_state, dtype=float).copy()
    state[2] += math.atan2(float(state[4]), float(state[3]))
    state[3] = math.hypot(float(state[3]), float(state[4]))
    state[4] = 0.0
    return state
