"""Planner constraints and route output for a GNC-owned retained local path."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass

import numpy as np

from colav_simulator.core.colav.mid_mpc_arrival import (
    ROUTE_RECOVERY_TOLERANCE_M,
    navigation_capture_error,
)


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
    trajectory_updates: bool = False
    minimum_turn_radius_m: float = 0.0
    maximum_lateral_acceleration_mps2: float = 0.0

    def __post_init__(self) -> None:
        """Freeze and validate the execution authority supplied by GNC."""
        if not isinstance(self.trajectory_updates, bool):
            raise TypeError("trajectory_updates must identify an advertised GNC contract")
        motion_limits = (self.minimum_turn_radius_m, self.maximum_lateral_acceleration_mps2)
        if not np.isfinite(motion_limits).all() or min(motion_limits) < 0.0:
            raise ValueError("Native turning limits must be finite and non-negative")
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
    pinned_beats: int | None = None
    knot_trim_reason: str | None = None


def compile_planner_trajectory(
    plan: RetainedPrefixPlan, predicted: np.ndarray, *, dt_s: float, generated_at_s: float
) -> dict:
    """Copy the optimized state grid without replacing, thinning or splicing it."""
    if predicted.ndim != 2 or predicted.shape[0] < 5 or predicted.shape[1] < 2:
        raise ValueError("Planner trajectory requires aligned position/course/speed samples")
    if not np.isfinite(predicted).all() or not math.isfinite(dt_s) or dt_s <= 0.0:
        raise ValueError("Planner trajectory and sample interval must be finite")
    if not math.isfinite(generated_at_s) or generated_at_s < 0.0:
        raise ValueError("Planner trajectory requires a finite issue time")
    if np.linalg.norm(predicted[:2, 0] - np.asarray(plan.points_ne_m[0])) > 1e-3:
        raise ValueError("Planner trajectory changed its measured initial position")
    document = {
        "schema_version": "colav.mid-mpc.execution-route@2",
        "reference_hash": plan.constraint.semantic_hash,
        "reference_id": plan.constraint.reference_id,
        "points_ne_m": predicted[:2].T.tolist(),
        "course_rad": predicted[2].tolist(),
        "speed_mps": np.hypot(predicted[3], predicted[4]).tolist(),
        "navigation_modes": ["avoidance"] * predicted.shape[1],
        "retained_point_count": 0,
        "prefix_intervals": 0,
        "trajectory_dt_s": float(dt_s),
        "generated_at_s": float(generated_at_s),
        "prediction_basis": "optimized trajectory, unmodified",
    }
    document["geometry_hash"] = hashlib.sha256(
        json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return document


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
        except _UnreachablePrefix as exc:
            # A fold witness outranks trying further shapes: same
            # degradation exit, but the replay artifact records which
            # structural cause fired.
            if str(exc).startswith("knot_trim"):
                raise
            continue
    raise _UnreachablePrefix("Retained GNC path cannot be reached within the active motion envelope")


class _UnreachablePrefix(ValueError):
    """No sampled interception meets the unchanged source motion envelope."""


def _compile_retained_prefix(  # noqa: PLR0915 - the anchor-enumeration loop is one linear scan
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
        # GNC's terminal schedule can drive the mirrored execution limit
        # below the vessel's steerage floor (F postmortem: 3.11→≤3.0 ×
        # steerage 3.0 emptied the [floor, cap] band at T1050.5 and every
        # shape died as INVALID_INPUT). The forecast consumes the mirrored
        # limit with the physical floor clamped back on; the bridge-side
        # constraint itself is untouched. The clamp keeps a slack above the
        # floor — cap == floor is a zero-width band that dies on the beat
        # grid (v9 T240.5) — while the acceptance floor (forecast_floor)
        # stays untouched.
        forecast_speed_cap = max(
            min_speed_mps + SPLICE_STEERAGE_SLACK_MPS,
            min(max_speed_mps, *constraint.execution_speed_mps[current_segment : segment + 2])
            if constraint.execution_speed_mps is not None
            else max_speed_mps,
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
                # The steerage-floor comparison shares the anchor-bisection
                # precision: a clamped zero-width forecast band (mirror
                # schedule decayed to the floor) lands the tuned anchor at
                # ~1e-6, so 1e-9 here would reject pure float noise.
                and np.min(speed) >= forecast_floor - 1e-6
                and abs(math.atan2(math.sin(course[-1] - target), math.cos(course[-1] - target)))
                <= rot_max_rad_s * dt_s + 1e-9
                and np.max(np.abs(np.diff(np.r_[own_speed, speed]))) <= accel_max_mps2 * dt_s + 1e-9
                and np.max(np.abs(np.diff(np.r_[ownship[2], course]))) <= rot_max_rad_s * dt_s + 1e-9
            ):
                # Knot-trim audit (v15): a forecast whose series carries a
                # fold beyond the rot envelope cannot be pinned partially —
                # the released free beats would start from the
                # avoidance-arc depth against the direction floor (the
                # T264.5 truncation shadow, seed violation 51.1). The whole
                # beat degrades to the assembler's stub exit instead.
                pinned = _knot_trim_audit(course, rot_max_rad_s * dt_s + 1e-6)
                if pinned < len(course):
                    raise _UnreachablePrefix(
                        "knot_trim: mirror fold at the pin seam exceeds the rot envelope"
                    )
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
    # The band guards share the anchor-bisection precision (~1e-6 m): a
    # zero-width clamped band (cap == floor) needs the tuned anchor's
    # required sum to sit on the boundary without being rejected as noise.
    if np.any(lower > upper) or required_sum < lower.sum() - 1e-6 or required_sum > upper.sum() + 1e-6:
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


# GNC dynamic update gate, avoidance tier (coordinate_transform_node.cpp
# 223-227): any avoidance-coded waypoint relaxes the guard to a 500 m
# line-perpendicular envelope with a 150 m first-change lookahead.
SPLICE_AVOIDANCE_LATERAL_LIMIT_M = 500.0
SPLICE_AVOIDANCE_LOOKAHEAD_M = 150.0
# GNC final-DP approach: deceleration begins final_dp_slow_down_dist before
# the terminus (ship_guidance_node.cpp:264, E_ingress_design §2).
SPLICE_FINAL_APPROACH_M = 420.0
# The capture-safe tail rejoins the mission final leg this far outside the
# arrival disk, so no pre-rejoin route segment touches the disk and the
# disk-crossing offsets all sit on the mission line (H postmortem §3:
# prune >=100 m before entry).
SPLICE_CAPTURE_STANDOFF_M = 100.0
# A speed band pinned exactly at the steerage floor is zero-width at the
# forecast beat grid and dies on the break/sum guards (v9 T240.5: mirror
# exec 3.0 x steerage 3.0 -> samples_none for every count). Published bend
# speeds and the forecast cap keep this slack above the floor.
SPLICE_STEERAGE_SLACK_MPS = 0.3


def degraded_stub_prefix(
    constraint: RetainedRouteConstraint,
    ownship_state: np.ndarray,
    *,
    knot_trim_reason: str | None = None,
) -> RetainedPrefixPlan:
    """Transport stub for a beat whose retained compile is unreachable.

    Same exit as the discard guards: the constraint survives as the
    admission substrate (retained corridor from the measured position on),
    the anchor is the measured position, no beat is pinned, and the
    avoidance mode routes the publication through the splice path. The
    caller records the witness; this construction is intentionally
    indistinguishable from a discard stub downstream.
    """
    points = np.asarray(constraint.points_ne_m)
    position = np.asarray(ownship_state[:2], dtype=float)
    along, progress = _projection(points, position)
    local_start = max(0, int(np.searchsorted(progress, along, side="right")) - 2)
    return RetainedPrefixPlan(
        constraint=constraint,
        points_ne_m=(tuple(map(float, ownship_state[:2])),),
        route_speed_mps=constraint.speed_mps[:1],
        navigation_modes=("avoidance",),
        course_rad=(),
        speed_mps=(),
        incoming_course_rad=float(ownship_state[2]),
        retained_point_count=1,
        corridor_points_m=tuple(map(tuple, points[local_start:] - position)),
        knot_trim_reason=knot_trim_reason,
    )


def _max_line_perpendicular_m(points: np.ndarray, reference: np.ndarray) -> float:
    """Nearest infinite-segment line distance, the GNC gate metric.

    Mirrors compute_max_lateral_delta (coordinate_transform_node.cpp 536-566):
    cross product over the segment length with no endpoint clamping, so a
    point past the reference end measures against the extended last segment.
    """
    legs = np.diff(reference, axis=0)
    lengths = np.linalg.norm(legs, axis=1)
    usable = lengths > 1e-9
    legs, lengths = legs[usable], lengths[usable]
    worst_m = 0.0
    for point in np.asarray(points):
        rel = point - reference[:-1][usable]
        perpendicular_m = np.abs(legs[:, 0] * rel[:, 1] - legs[:, 1] * rel[:, 0]) / lengths
        worst_m = max(worst_m, float(perpendicular_m.min()))
    return worst_m


def _lateral_profile(points: np.ndarray, reference: np.ndarray) -> np.ndarray:
    """Nearest-segment distance and signed starboard offset for each point.

    Positive offsets sit on the starboard side of the nearest segment's
    direction (heading chi: starboard unit (-sin chi, cos chi) in NE).
    """
    legs = np.diff(reference, axis=0)
    lengths = np.linalg.norm(legs, axis=1)
    usable = lengths > 1e-9
    starts = reference[:-1][usable]
    legs, lengths = legs[usable], lengths[usable]
    rel = points[:, None, :] - starts[None, :, :]
    fraction = np.clip(np.einsum("psk,sk->ps", rel, legs) / (lengths**2)[None], 0.0, 1.0)
    projected = starts[None, :, :] + fraction[..., None] * legs[None, :, :]
    distances = np.linalg.norm(points[:, None, :] - projected, axis=2)
    nearest = np.argmin(distances, axis=1)
    rows = np.arange(len(points))
    unit = legs[nearest] / lengths[nearest][:, None]
    signed = np.einsum("pk,pk->p", points - projected[rows, nearest], unit)
    return np.column_stack((distances[rows, nearest], signed))


def _avoidance_bulge(
    start: np.ndarray,
    incoming: float,
    side: float,
    depth_m: float,
    advance_m: float,
    step_m: float,
) -> list[tuple[float, float]]:
    """Symmetric out-and-back detour of three tangent arcs on the start line.

    The ``_reference_transition`` technique generalized to a detour: turn
    away delta, unwind through 2*delta, and resume the incoming heading
    exactly on the start course line. Depth and advance follow the caller's
    maneuver evidence — depth 2R(1-cos(delta)), advance 4R sin(delta) — so
    delta = 2 atan(2*depth/advance) invents no excursion; a 2*depth advance
    floor caps delta at 90 deg when the predicted rejoins early.
    """
    delta_rad = 2.0 * math.atan(2.0 * depth_m / advance_m)
    radius_m = depth_m / (2.0 * (1.0 - math.cos(delta_rad)))

    def turn_arc(point: np.ndarray, start_course: float, stop_course: float, turn_side: float) -> list[tuple[float, float]]:
        center = point + turn_side * radius_m * np.array([-math.sin(start_course), math.cos(start_course)])
        steps = max(1, int(math.ceil(radius_m * abs(stop_course - start_course) / step_m)))
        angles = np.linspace(start_course, stop_course, steps + 1)[1:]
        return [
            tuple(center - turn_side * radius_m * np.array([-math.sin(angle), math.cos(angle)])) for angle in angles
        ]

    apex_course = incoming + side * delta_rad
    return_course = incoming - side * delta_rad
    arc = turn_arc(start, incoming, apex_course, side)
    arc += turn_arc(np.asarray(arc[-1]), apex_course, return_course, -side)
    arc += turn_arc(np.asarray(arc[-1]), return_course, incoming, side)
    return arc


def _convergence_speeds(
    start_speed_mps: float,
    points: list[tuple[float, float]],
    *,
    planned_mps: float,
    accel_mps2: float,
    decel_mps2: float,
    rot_max_rad_s: float,
    floor_mps: float,
) -> list[float]:
    """Splice-tail speeds converging to the planned cruise, brake at the end.

    From the maneuver start the profile walks the published points under the
    measured accel/decel envelope toward the planned speed; inside the GNC
    final-approach window the target ramps linearly down to the steerage
    floor and never below it, so the mirrored execution speed the route
    schedules cannot collapse the retained forecast band again (F
    postmortem §4). Legs facing a heading change are capped by the rot
    envelope (curvature speed bound). Returns one speed per input point,
    seeded with the measured speed at the maneuver start.
    """
    speeds: list[float] = [max(start_speed_mps, floor_mps)]
    speed = max(start_speed_mps, floor_mps)
    previous = np.asarray(points[0], dtype=float)
    previous_bearing = 0.0
    total_m = sum(
        float(np.linalg.norm(np.asarray(stop) - np.asarray(start)))
        for start, stop in zip(points[:-1], points[1:], strict=True)
    )
    sailed_m = 0.0
    for point in points[1:]:
        current = np.asarray(point, dtype=float)
        leg_m = float(np.linalg.norm(current - previous))
        sailed_m += leg_m
        remaining_m = max(total_m - sailed_m, 0.0)
        target_mps = (
            planned_mps
            if remaining_m >= SPLICE_FINAL_APPROACH_M
            else max(floor_mps, planned_mps * remaining_m / SPLICE_FINAL_APPROACH_M)
        )
        leg_s = leg_m / max(speed, floor_mps, 0.5)
        speed += min(max(target_mps - speed, -decel_mps2 * leg_s), accel_mps2 * leg_s)
        bearing_rad = math.atan2(current[1] - previous[1], current[0] - previous[0])
        turn_rad = abs(math.atan2(math.sin(bearing_rad - previous_bearing), math.cos(bearing_rad - previous_bearing)))
        if turn_rad > 1e-9:
            # A bend limit pinned at the floor publishes exactly-steerage
            # bend speeds; GNC writes them back into the mirror and the
            # forecast clamp reproduces them — a zero-width speed band (v9
            # T240.5). The slack keeps the published band non-degenerate;
            # the limit only clamps downward, so the final-approach brake
            # still lands on the floor.
            curvature_cap = leg_m * rot_max_rad_s / turn_rad
            speed = min(speed, max(floor_mps + SPLICE_STEERAGE_SLACK_MPS, curvature_cap))
        speeds.append(speed)
        previous_bearing = bearing_rad
        previous = current
    return speeds


def _joined_tail(
    constraint: RetainedRouteConstraint,
    reference: np.ndarray,
    points: list[tuple[float, float]],
    modes: list[str],
    arc_count: int,
    rejoin_k: int | None,
    bend_speed: float,
    tail_stop_k: int,
    terminus_point: np.ndarray | None,
) -> tuple[list[tuple[float, float]], list[str], list[float]]:
    """Rejoin the retained vertices onto the splice, up to the terminus.

    The tail walks the retained vertices verbatim (original modes and
    speeds) up to the effective terminus vertex. When the terminus is the
    arrival-region entry (v11), that entry point is appended as the final,
    L4-authorized capture leg — the route ends at the region boundary
    instead of following the mirrored overshoot.
    """
    fallback_speeds = [bend_speed] * arc_count
    if rejoin_k is not None:
        for vertex in range(rejoin_k, tail_stop_k + 1):
            points.append((float(reference[vertex][0]), float(reference[vertex][1])))
            modes.append(constraint.navigation_modes[vertex])
            fallback_speeds.append(float(constraint.speed_mps[vertex]))
    if terminus_point is not None and float(np.linalg.norm(np.asarray(points[-1]) - terminus_point)) > 1e-6:
        points.append((float(terminus_point[0]), float(terminus_point[1])))
        modes.append(modes[-1])
        fallback_speeds.append(fallback_speeds[-1] if fallback_speeds else bend_speed)
    return points, modes, fallback_speeds


def _bend_and_rejoin(
    constraint: RetainedRouteConstraint,
    reference: np.ndarray,
    along: float,
    progress: np.ndarray,
    lateral: np.ndarray,
    apex_k: int,
    depth_m: float,
    predicted: np.ndarray,
    terminus_along: float,
    has_entry: bool,
) -> tuple[int, float, list[tuple[float, float]], int | None]:
    """Bend vertex, bend speed, avoidance bulge, and rejoin vertex.

    The bend starts at the separated predicted vertex, advanced along the
    reference until the first changed point clears the avoidance lookahead,
    bounded by the effective terminus. The bulge compresses into the run
    that remains before the terminus (depth yields to the arrival semantics;
    the approach leg closes the rest) — a rejoin past the terminus is
    impossible by construction, so the v10 raise is gone. Without an
    arrival entry an unsatisfiable lookahead still raises: mid-encounter
    the maneuver must publish or fail loudly.
    """
    separation_k = int(np.argmax(lateral[:, 0] > constraint.minimum_segment_m))
    separation_along = _projection(reference, predicted[:2, separation_k])[0]
    last_bend = max(0, int(np.searchsorted(progress, terminus_along + 1e-9, side="right")) - 1)
    last_bend = min(last_bend, len(reference) - 2)
    # A free prediction can first separate beyond the mirrored endpoint.
    # The bend names a segment, so it cannot name the terminal vertex.
    bend_k = min(last_bend, max(0, int(np.searchsorted(progress, separation_along, side="right")) - 1))
    while bend_k < last_bend and progress[bend_k] - along < SPLICE_AVOIDANCE_LOOKAHEAD_M:
        bend_k += 1
    if progress[bend_k] - along < SPLICE_AVOIDANCE_LOOKAHEAD_M:
        if has_entry:
            return bend_k, constraint.speed_mps[bend_k], [], bend_k + 1
        raise ValueError("Retained route ends before the avoidance bend satisfies the first-change lookahead")
    returned_k = int(np.argmax(lateral[apex_k:, 0] <= constraint.minimum_segment_m)) + apex_k
    if lateral[returned_k, 0] > constraint.minimum_segment_m:
        returned_k = len(lateral) - 1
    side = math.copysign(1.0, lateral[apex_k, 1])
    terminus_span = max(terminus_along - progress[bend_k], 0.0)
    advance_m = min(
        max(_projection(reference, predicted[:2, returned_k])[0] - progress[bend_k], 2.0 * depth_m),
        terminus_span,
    )
    # The published bulge is the admission substrate, not the maneuver: cap
    # its depth inside the GNC avoidance-tier lateral guard (minus a segment
    # of margin) so the splice self-check can never raise on a deep early
    # avoidance prediction — the solver's own excursion is bounded by the
    # corridor, not by this reference geometry.
    depth_eff = min(
        depth_m,
        advance_m / 2.0,
        SPLICE_AVOIDANCE_LATERAL_LIMIT_M - constraint.minimum_segment_m,
    )
    incoming = math.atan2(*(reference[bend_k + 1] - reference[bend_k])[::-1])
    if depth_eff <= 0.0 or advance_m <= 0.0:
        return bend_k, constraint.speed_mps[bend_k], [], bend_k + 1
    arc = _avoidance_bulge(
        reference[bend_k], incoming, side, depth_eff, advance_m, max(constraint.minimum_segment_m, 1.0)
    )
    rejoin_candidates = [
        vertex
        for vertex in range(bend_k + 1, len(reference))
        if progress[vertex] >= progress[bend_k] + advance_m - constraint.minimum_segment_m
        and progress[vertex] <= terminus_along + 1e-9
    ]
    rejoin_k = (
        min(
            rejoin_candidates,
            key=lambda vertex: float(np.linalg.norm(reference[vertex] - np.asarray(arc[-1]))),
        )
        if rejoin_candidates
        else None
    )
    return bend_k, constraint.speed_mps[bend_k], arc, rejoin_k


def _capture_guard(
    points: list[tuple[float, float]],
    modes: list[str],
    fallback_speeds: list[float],
    mission_arrival: tuple[tuple[float, float], tuple[float, float], float] | None,
) -> bool:
    """Rewrite the tail onto the mission final leg when it enters off-line.

    The acceptance capture check evaluates the mirrored route: any disk
    crossing more than ROUTE_RECOVERY_TOLERANCE_M off the mission final leg
    rejects the beat forever (candidates cannot reshape the mirror), so the
    splice never publishes such geometry. The rewrite prunes the tail
    before the disk standoff, rejoins the mission line outside the disk at
    the point nearest the current path end, and runs the entry along the
    line — the disk-crossing offsets then sit exactly on the line. Returns
    True when the geometry was rewritten; a route that cannot be pruned is
    left for the final self-check to reject loudly.
    """
    if mission_arrival is None:
        return False
    leg_start = np.asarray(mission_arrival[0], dtype=float)
    goal = np.asarray(mission_arrival[1], dtype=float)
    radius_m = float(mission_arrival[2])
    route = np.asarray(points)
    error_m = navigation_capture_error(route[:, 0], route[:, 1], (leg_start, goal), radius_m)
    if error_m <= ROUTE_RECOVERY_TOLERANCE_M:
        return False
    standoff_m = radius_m + SPLICE_CAPTURE_STANDOFF_M
    distances = np.linalg.norm(route - goal, axis=1)
    inside = np.nonzero(distances < standoff_m)[0]
    if inside.size == 0 or inside[0] == 0:
        return False
    direction = goal - leg_start
    leg_length = float(np.linalg.norm(direction))
    if leg_length <= 1e-9:
        return False
    unit = direction / leg_length
    cut = int(inside[0])
    along_leg = float(np.clip((route[cut - 1] - leg_start) @ unit, 0.0, leg_length - radius_m - SPLICE_CAPTURE_STANDOFF_M))
    rejoin = leg_start + along_leg * unit
    del points[cut:]
    del modes[cut:]
    del fallback_speeds[cut:]
    if float(np.linalg.norm(np.asarray(points[-1]) - rejoin)) > 1e-6:
        points.append((float(rejoin[0]), float(rejoin[1])))
        modes.append(modes[-1])
        fallback_speeds.append(fallback_speeds[-1])
    if float(np.linalg.norm(np.asarray(points[-1]) - goal)) > 1e-6:
        points.append((float(goal[0]), float(goal[1])))
        modes.append(modes[-1])
        fallback_speeds.append(fallback_speeds[-1])
    return True


def _splice_terminus(
    reference: np.ndarray,
    progress: np.ndarray,
    predicted: np.ndarray,
    goal: np.ndarray | None,
    arrival_radius_m: float,
) -> tuple[np.ndarray | None, float]:
    """Effective route end: the arrival entry or the mirror end, first wins.

    The predicted trajectory is L4-authorized to enter the shared arrival
    region; when it does so before the mirror ends, the published route ends
    at that entry instead of following the mirror past the goal (v11: the
    mirror overran the goal by ~654 m and no bulge could rejoin beyond it).
    GNC's terminal semantics make this safe — it decelerates from 420 m out
    and stops inside the capture circle, and the simulator's arrival
    condition (goal distance < radius) fires before that matters.
    """
    if goal is not None:
        for k in range(predicted.shape[1]):
            if float(np.linalg.norm(predicted[:2, k] - goal)) <= arrival_radius_m:
                entry_point = np.asarray(predicted[:2, k], dtype=float)
                entry_along = _projection(reference, entry_point)[0]
                if entry_along < progress[-1]:
                    return entry_point, entry_along
                break
    return None, float(progress[-1])


def _benign_geometry(
    constraint: RetainedRouteConstraint,
    progress: np.ndarray,
    terminus_along: float,
    terminus_point: np.ndarray | None,
) -> tuple[list[tuple[float, float]], list[str], list[float], int]:
    """No separated maneuver: the replayed reference is the geometry.

    An identical candidate never trips the GNC update gate. The replay runs
    to the effective terminus (arrival entry or mirror end) and, with the
    capability evidence supplied, the mirrored speed schedule is still
    re-profiled (R1) — its terminal decay is what collapses the next beat's
    forecast band.
    """
    reference = np.asarray(constraint.points_ne_m)
    head_count = min(
        len(reference),
        max(1, int(np.searchsorted(progress, terminus_along + 1e-9, side="right"))),
    )
    points = [tuple(map(float, point)) for point in reference[:head_count]]
    modes = list(constraint.navigation_modes[:head_count])
    fallback_speeds = list(constraint.speed_mps[:head_count])
    if terminus_point is not None and float(np.linalg.norm(np.asarray(points[-1]) - terminus_point)) > 1e-6:
        points.append((float(terminus_point[0]), float(terminus_point[1])))
        modes.append(modes[-1])
        fallback_speeds.append(fallback_speeds[-1])
    return points, modes, fallback_speeds, head_count


def _splice_self_checks(
    assembled: dict,
    reference: np.ndarray,
    mission_arrival: tuple[tuple[float, float], tuple[float, float], float] | None,
    terminus_point: np.ndarray | None,
    rewritten: bool,
    arrival_boundary: tuple[tuple[float, float], float] | None,
) -> None:
    """Run the splice admission gates.

    The 500 m avoidance envelope, the mission-leg capture tolerance, and
    the published terminus.
    """
    deviation_m = _max_line_perpendicular_m(np.asarray(assembled["points_ne_m"]), reference)
    if deviation_m > SPLICE_AVOIDANCE_LATERAL_LIMIT_M:
        raise ValueError(
            f"Spliced route leaves the GNC avoidance envelope: "
            f"{deviation_m:.1f} m line-perpendicular > {SPLICE_AVOIDANCE_LATERAL_LIMIT_M:.0f} m lateral guard"
        )
    if mission_arrival is not None:
        route = np.asarray(assembled["points_ne_m"])
        capture_m = navigation_capture_error(
            route[:, 0], route[:, 1], (mission_arrival[0], mission_arrival[1]), mission_arrival[2]
        )
        if capture_m > ROUTE_RECOVERY_TOLERANCE_M:
            raise ValueError(
                f"Spliced route fails the mission-leg capture check: "
                f"{capture_m:.1f} m off-line inside the arrival disk > "
                f"{ROUTE_RECOVERY_TOLERANCE_M:.0f} m tolerance"
            )
    if rewritten:
        goal = np.asarray(mission_arrival[1], dtype=float)
        expected_end = (float(goal[0]), float(goal[1]))
    elif terminus_point is not None:
        expected_end = (float(terminus_point[0]), float(terminus_point[1]))
    else:
        expected_end = tuple(map(float, reference[-1]))
    if (rewritten or terminus_point is not None or arrival_boundary is None) and np.linalg.norm(
        np.asarray(assembled["points_ne_m"][-1]) - expected_end
    ) > 1e-6:
        raise ValueError("Spliced route must end at the published terminus")


def _knot_trim_audit(course: np.ndarray, rot_step_rad: float) -> int:
    """Last prefix knot whose pin stays within the rot envelope (v13).

    A fold beyond the envelope cannot be split off for the free suffix to
    absorb: releasing beats at the fold makes them start from the
    avoidance-arc depth against the direction floor — a constant violation
    (v13 T1771 pin, v15 T264.5 truncation shadow). Callers therefore treat
    any trailing fold (pinned < len) as a whole-beat degradation instead of
    trimming the pin.
    """
    pinned = len(course)
    while pinned > 1:
        step_rad = abs(
            math.atan2(
                math.sin(course[pinned - 1] - course[pinned - 2]),
                math.cos(course[pinned - 1] - course[pinned - 2]),
            )
        )
        if step_rad > rot_step_rad:
            pinned -= 1
            continue
        break
    return pinned


def compile_spliced_execution_route(
    plan: RetainedPrefixPlan,
    predicted: np.ndarray,
    *,
    arrival_boundary: tuple[tuple[float, float], float] | None = None,
    planned_speed_mps: float | None = None,
    accel_max_mps2: float | None = None,
    decel_max_mps2: float | None = None,
    rot_max_rad_s: float | None = None,
    steerage_speed_mps: float | None = None,
    mission_arrival: tuple[tuple[float, float], tuple[float, float], float] | None = None,
) -> dict:
    """Publish a discard beat's route by splicing the retained reference.

    A discard stub owns no pinned beats, so the measured-position anchor of
    ``compile_execution_route`` would fail the GNC gate unconditionally: the
    dynamic update guard compares the candidate to the mirrored reference
    index by index, and a candidate whose first point is off the reference
    origin reports a first change at index 0 with zero lookahead. The splice
    therefore keeps the frozen reference as the admission substrate — replay
    its vertices verbatim to the bend vertex, insert the avoidance bulge
    shaped by the predicted maneuver's own lateral depth and longitudinal
    span (a symmetric out-and-back of tangent arcs, the
    ``_reference_transition`` technique), then rejoin the reference vertices.
    Head and tail keep the reference modes; the arc declares "avoidance",
    which alone moves the whole route onto the 500 m avoidance guard tier. A
    route whose deepest point leaves that envelope raises instead of
    publishing a rejection that would only surface after the transport round
    trip.

    With the capability evidence supplied, the maneuver and tail speeds are
    re-profiled (R1): the mirrored schedule — decayed by GNC's terminal
    slowdown below steerage — is replaced by a planned-speed convergence
    under the accel/decel envelope with a final-approach brake floored at
    steerage. The splice's effective terminus is the arrival-region entry
    when predicted reaches it before the mirror ends (v11): the route ends
    at that entry — GNC decelerates from 420 m out and stops inside the
    capture circle, and the simulator's arrival condition (goal distance <
    radius) fires before that matters — instead of chasing a mirrored
    endpoint that can lie hundreds of meters past the goal, where no bulge
    rejoin and no approach leg can stay inside the 500 m envelope. With the
    mission arrival supplied, the route is capture-checked against the
    mission final leg before leaving the compile (H-B): a tail that would
    cross the arrival disk off-line is rewritten onto the line, so the GNC
    mirror can never acquire the >20 m disk-crossing offset that deadlocks
    QUALITY_NAVIGATION_CAPTURE (v12).
    """
    constraint = plan.constraint
    trimmed_pin = plan.pinned_beats is not None and plan.pinned_beats < len(plan.course_rad)
    if plan.course_rad and not trimmed_pin:
        raise ValueError("Spliced publication requires a discard stub without pinned beats")
    if not trimmed_pin and np.linalg.norm(predicted[:2, 0] - np.asarray(plan.points_ne_m[-1])) > 1e-3:
        raise ValueError("Optimizer did not preserve the discard stub anchor")
    reference = np.asarray(constraint.points_ne_m)
    goal = np.asarray(arrival_boundary[0], dtype=float) if arrival_boundary is not None else None
    arrival_radius_m = float(arrival_boundary[1]) if arrival_boundary is not None else 0.0
    if mission_arrival is not None:
        # The mission arrival is encounter-independent: the capture check
        # guards every native beat, cleared or not.
        goal = np.asarray(mission_arrival[1], dtype=float)
        arrival_radius_m = float(mission_arrival[2])
    profile_args = (
        {
            "planned_mps": float(planned_speed_mps),
            "accel_mps2": float(accel_max_mps2),
            "decel_mps2": float(decel_max_mps2),
            "rot_max_rad_s": float(rot_max_rad_s),
            "floor_mps": float(steerage_speed_mps or 0.0),
        }
        if planned_speed_mps is not None and None not in (accel_max_mps2, decel_max_mps2, rot_max_rad_s)
        else None
    )
    measured_speed_mps = float(np.hypot(predicted[3, 0], predicted[4, 0]))
    along, progress = _projection(reference, predicted[:2, 0])
    terminus_point, terminus_along = _splice_terminus(reference, progress, predicted, goal, arrival_radius_m)
    lateral = _lateral_profile(np.asarray(predicted[:2]).T, reference)
    apex_k = int(np.argmax(lateral[:, 0]))
    depth_m = float(lateral[apex_k, 0])
    if depth_m <= constraint.minimum_segment_m:
        points, modes, fallback_speeds, retained_count = _benign_geometry(
            constraint, progress, terminus_along, terminus_point
        )
        bend_k = 0
    else:
        bend_k, bend_speed, arc, rejoin_k = _bend_and_rejoin(
            constraint,
            reference,
            along,
            progress,
            lateral,
            apex_k,
            depth_m,
            predicted,
            terminus_along,
            has_entry=terminus_point is not None,
        )
        head_modes = list(constraint.navigation_modes[: bend_k + 1])
        points = [tuple(map(float, point)) for point in reference[: bend_k + 1]] + arc
        modes = head_modes + ["avoidance"] * len(arc)
        tail_stop_k = max(0, int(np.searchsorted(progress, terminus_along + 1e-9, side="right")) - 1)
        points, modes, fallback_speeds = _joined_tail(
            constraint,
            reference,
            points,
            modes,
            arc_count=len(arc),
            rejoin_k=rejoin_k,
            bend_speed=bend_speed,
            tail_stop_k=tail_stop_k,
            terminus_point=terminus_point,
        )
        retained_count = bend_k + 1
    # The profile walks from the bend vertex on: the head before it stays on
    # the mirrored schedule verbatim.
    rewritten = _capture_guard(points, modes, fallback_speeds, mission_arrival)
    if profile_args is not None:
        speeds = list(constraint.speed_mps[:bend_k]) + _convergence_speeds(
            measured_speed_mps, points[bend_k:], **profile_args
        )
    else:
        speeds = list(constraint.speed_mps[: bend_k + 1]) + fallback_speeds
    # The entry/rewritten leg terminates on or inside the arrival region by
    # authorization (L4 capture / mission line), so the encounter-gated
    # boundary truncation only applies to a mirror-terminus route.
    assembled = _spliced_document(
        constraint,
        points,
        speeds,
        modes,
        retained_count,
        None if (rewritten or terminus_point is not None) else arrival_boundary,
    )
    _splice_self_checks(assembled, reference, mission_arrival, terminus_point, rewritten, arrival_boundary)
    return assembled


def _spliced_document(
    constraint: RetainedRouteConstraint,
    points: list[tuple[float, float]],
    speeds: list[float],
    modes: list[str],
    retained_point_count: int,
    arrival_boundary: tuple[tuple[float, float], float] | None,
) -> dict:
    """Truncate at the arrival boundary like the pinned compile, then hash."""
    if arrival_boundary is not None and len(points) > 1:
        goal = np.asarray(arrival_boundary[0], dtype=float)
        kept = points[:1]
        for point in points[1:]:
            if _segment_enters_arrival_region(np.asarray(kept[-1]), np.asarray(point), goal, arrival_boundary[1]):
                break
            kept.append(point)
        points, speeds, modes = kept, speeds[: len(kept)], modes[: len(kept)]
    document = {
        "schema_version": "colav.mid-mpc.execution-route@1",
        "reference_hash": constraint.semantic_hash,
        "reference_id": constraint.reference_id,
        "points_ne_m": points,
        "speed_mps": speeds,
        "navigation_modes": modes,
        "retained_point_count": retained_point_count,
        "prefix_intervals": 0,
        "prediction_basis": "retained-reference splice with predicted-depth avoidance arc",
    }
    document["geometry_hash"] = hashlib.sha256(
        json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return document


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
