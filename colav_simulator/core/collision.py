"""Conservative continuous-segment vessel footprint collision checks."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from shapely import affinity
from shapely.geometry import Polygon, box
from shapely.geometry.base import BaseGeometry

COLLISION_ORACLE_ID = "footprint-adaptive-v1"
C2A_ORACLE_ID = "c2a-rect2d-v1"


@dataclass(frozen=True)
class VesselPose:
    """Rectangular vessel pose in the simulator North/East frame."""

    north_m: float
    east_m: float
    heading_rad: float
    length_m: float
    width_m: float

    def __post_init__(self) -> None:
        """Validate finite pose geometry."""
        values = np.array(
            [self.north_m, self.east_m, self.heading_rad, self.length_m, self.width_m],
            dtype=float,
        )
        if not np.isfinite(values).all():
            raise ValueError("vessel pose values must be finite")
        if self.length_m <= 0.0 or self.width_m <= 0.0:
            raise ValueError("vessel length and width must be positive")

    @property
    def corner_radius_m(self) -> float:
        return 0.5 * float(np.hypot(self.length_m, self.width_m))


@dataclass(frozen=True)
class CollisionInterval:
    """Conservative interval containing a physical footprint contact."""

    tau_start: float
    tau_end: float
    oracle_id: str = COLLISION_ORACLE_ID


@dataclass(frozen=True)
class TOCResult:
    """First time-of-contact result with a bounded numerical interval."""

    collided: bool
    toc_s: float | None
    bracket_s: tuple[float, float] | None
    status: str
    iterations: int
    distance_tolerance_m: float
    time_tolerance_s: float
    oracle_id: str = C2A_ORACLE_ID


def rectangular_footprint(pose: VesselPose) -> Polygon:
    """Create a centered L x W rectangle in Shapely East/North axes."""
    polygon = box(
        -pose.width_m / 2.0,
        -pose.length_m / 2.0,
        pose.width_m / 2.0,
        pose.length_m / 2.0,
    )
    polygon = affinity.rotate(polygon, -pose.heading_rad, origin=(0.0, 0.0), use_radians=True)
    return affinity.translate(polygon, xoff=pose.east_m, yoff=pose.north_m)


def continuous_footprint_collision(
    own_start: VesselPose,
    own_end: VesselPose,
    target_start: VesselPose,
    target_end: VesselPose,
    *,
    step_tolerance_m: float = 0.25,
    max_depth: int = 24,
) -> CollisionInterval | None:
    """Return a conservative synchronized collision interval, or None."""
    if step_tolerance_m <= 0.0:
        raise ValueError("step_tolerance_m must be positive")
    if max_depth < 1:
        raise ValueError("max_depth must be positive")
    return _subdivide(
        own_start,
        own_end,
        target_start,
        target_end,
        0.0,
        1.0,
        step_tolerance_m,
        max_depth,
    )


def c2a_first_contact(
    own_start: VesselPose,
    own_end: VesselPose,
    target_start: VesselPose,
    target_end: VesselPose,
    *,
    interval_start_s: float = 0.0,
    interval_end_s: float = 1.0,
    distance_tolerance_m: float = 1e-4,
    time_tolerance_s: float = 1e-5,
    max_iterations: int = 128,
) -> TOCResult:
    """Find synchronized rectangle first contact by controlled conservative advancement."""
    if interval_end_s <= interval_start_s:
        raise ValueError("contact interval end must be after start")
    return _controlled_advancement(
        lambda tau: rectangular_footprint(interpolate_pose(own_start, own_end, tau)),
        lambda tau: rectangular_footprint(interpolate_pose(target_start, target_end, tau)),
        _relative_motion_bound(own_start, own_end, target_start, target_end),
        interval_start_s,
        interval_end_s,
        distance_tolerance_m,
        time_tolerance_s,
        max_iterations,
    )


def c2a_grounding_first_contact(
    vessel_start: VesselPose,
    vessel_end: VesselPose,
    hazard: BaseGeometry,
    *,
    interval_start_s: float = 0.0,
    interval_end_s: float = 1.0,
    distance_tolerance_m: float = 1e-4,
    time_tolerance_s: float = 1e-5,
    max_iterations: int = 128,
) -> TOCResult:
    """Find first physical footprint contact with a static chart hazard."""
    if hazard is None or hazard.is_empty:
        return TOCResult(
            collided=False,
            toc_s=None,
            bracket_s=None,
            status="NO_HAZARD",
            iterations=0,
            distance_tolerance_m=distance_tolerance_m,
            time_tolerance_s=time_tolerance_s,
        )
    if interval_end_s <= interval_start_s:
        raise ValueError("contact interval end must be after start")
    return _controlled_advancement(
        lambda tau: rectangular_footprint(interpolate_pose(vessel_start, vessel_end, tau)),
        lambda _tau: hazard,
        _pose_motion_bound(vessel_start, vessel_end),
        interval_start_s,
        interval_end_s,
        distance_tolerance_m,
        time_tolerance_s,
        max_iterations,
    )


def interpolate_pose(start: VesselPose, end: VesselPose, fraction: float) -> VesselPose:
    """Interpolate one pose using linear translation and shortest-angle heading."""
    fraction = float(np.clip(fraction, 0.0, 1.0))
    heading_delta = _wrap_angle(end.heading_rad - start.heading_rad)
    return VesselPose(
        north_m=(1.0 - fraction) * start.north_m + fraction * end.north_m,
        east_m=(1.0 - fraction) * start.east_m + fraction * end.east_m,
        heading_rad=_wrap_angle(start.heading_rad + fraction * heading_delta),
        length_m=start.length_m,
        width_m=start.width_m,
    )


def _subdivide(
    own_start: VesselPose,
    own_end: VesselPose,
    target_start: VesselPose,
    target_end: VesselPose,
    tau_start: float,
    tau_end: float,
    tolerance: float,
    depth: int,
) -> CollisionInterval | None:
    own_mid = interpolate_pose(own_start, own_end, 0.5)
    target_mid = interpolate_pose(target_start, target_end, 0.5)
    own_polygons = (
        rectangular_footprint(own_start),
        rectangular_footprint(own_mid),
        rectangular_footprint(own_end),
    )
    target_polygons = (
        rectangular_footprint(target_start),
        rectangular_footprint(target_mid),
        rectangular_footprint(target_end),
    )
    if any(own.intersects(target) for own, target in zip(own_polygons, target_polygons, strict=True)):
        return CollisionInterval(tau_start, tau_end)

    own_bound = _half_interval_corner_motion(own_start, own_end)
    target_bound = _half_interval_corner_motion(target_start, target_end)
    separation = own_polygons[1].distance(target_polygons[1])
    if separation > own_bound + target_bound:
        return None

    relative_corner_motion = 2.0 * (own_bound + target_bound)
    if relative_corner_motion <= tolerance or depth <= 1:
        # Exact first contact is intentionally deferred to P3 C2A. Conservatively
        # resolving an uncertain leaf prevents timestamp tunneling false negatives.
        return CollisionInterval(tau_start, tau_end)

    tau_mid = 0.5 * (tau_start + tau_end)
    first = _subdivide(
        own_start,
        own_mid,
        target_start,
        target_mid,
        tau_start,
        tau_mid,
        tolerance,
        depth - 1,
    )
    if first is not None:
        return first
    return _subdivide(
        own_mid,
        own_end,
        target_mid,
        target_end,
        tau_mid,
        tau_end,
        tolerance,
        depth - 1,
    )


def _half_interval_corner_motion(start: VesselPose, end: VesselPose) -> float:
    translation = 0.5 * float(np.hypot(end.north_m - start.north_m, end.east_m - start.east_m))
    rotation = 0.5 * abs(_wrap_angle(end.heading_rad - start.heading_rad))
    radius = max(start.corner_radius_m, end.corner_radius_m)
    return translation + rotation * radius


def _controlled_advancement(
    first_geometry: object,
    second_geometry: object,
    motion_bound_per_tau: float,
    interval_start_s: float,
    interval_end_s: float,
    distance_tolerance_m: float,
    time_tolerance_s: float,
    max_iterations: int,
) -> TOCResult:
    if distance_tolerance_m <= 0.0 or time_tolerance_s <= 0.0:
        raise ValueError("C2A tolerances must be positive")
    if max_iterations < 1:
        raise ValueError("max_iterations must be positive")
    duration = interval_end_s - interval_start_s
    tau_time_tolerance = min(1.0, time_tolerance_s / duration)
    tau = 0.0
    previous_tau = 0.0
    iterations = 0
    first = first_geometry(tau)  # type: ignore[operator]
    second = second_geometry(tau)  # type: ignore[operator]
    if first.intersects(second):
        return _toc_result(
            0.0,
            0.0,
            interval_start_s,
            duration,
            "CONTACT_AT_START",
            1,
            distance_tolerance_m,
            time_tolerance_s,
        )
    if motion_bound_per_tau <= 1e-15:
        return TOCResult(False, None, None, "SEPARATED_STATIC", 1, distance_tolerance_m, time_tolerance_s)

    while tau < 1.0 and iterations < max_iterations:
        iterations += 1
        first = first_geometry(tau)  # type: ignore[operator]
        second = second_geometry(tau)  # type: ignore[operator]
        distance = float(first.distance(second))
        if first.intersects(second) or distance <= distance_tolerance_m:
            return _bisect_contact(
                first_geometry,
                second_geometry,
                previous_tau,
                tau,
                interval_start_s,
                duration,
                distance_tolerance_m,
                time_tolerance_s,
                max_iterations - iterations,
                iterations,
            )
        conservative_step = max(0.9 * distance / motion_bound_per_tau, tau_time_tolerance)
        previous_tau = tau
        tau = min(1.0, tau + conservative_step)

    if iterations >= max_iterations and tau < 1.0:
        lower_s = interval_start_s + tau * duration
        return TOCResult(
            collided=True,
            toc_s=interval_end_s,
            bracket_s=(lower_s, interval_end_s),
            status="ITERATION_LIMIT_CONSERVATIVE_CONTACT",
            iterations=iterations,
            distance_tolerance_m=distance_tolerance_m,
            time_tolerance_s=time_tolerance_s,
        )

    end_first = first_geometry(1.0)  # type: ignore[operator]
    end_second = second_geometry(1.0)  # type: ignore[operator]
    if end_first.intersects(end_second) or end_first.distance(end_second) <= distance_tolerance_m:
        return _bisect_contact(
            first_geometry,
            second_geometry,
            previous_tau,
            1.0,
            interval_start_s,
            duration,
            distance_tolerance_m,
            time_tolerance_s,
            max_iterations - iterations,
            iterations,
        )
    return TOCResult(False, None, None, "SEPARATED", iterations, distance_tolerance_m, time_tolerance_s)


def _bisect_contact(
    first_geometry: object,
    second_geometry: object,
    lower: float,
    upper: float,
    interval_start_s: float,
    duration: float,
    distance_tolerance_m: float,
    time_tolerance_s: float,
    remaining_iterations: int,
    iterations: int,
) -> TOCResult:
    lower = max(0.0, lower)
    upper = min(1.0, upper)
    for _ in range(max(1, remaining_iterations)):
        iterations += 1
        if (upper - lower) * duration <= time_tolerance_s:
            break
        middle = 0.5 * (lower + upper)
        first = first_geometry(middle)  # type: ignore[operator]
        second = second_geometry(middle)  # type: ignore[operator]
        if first.intersects(second) or first.distance(second) <= distance_tolerance_m:
            upper = middle
        else:
            lower = middle
    return _toc_result(
        lower,
        upper,
        interval_start_s,
        duration,
        "CONTACT_BRACKETED",
        iterations,
        distance_tolerance_m,
        time_tolerance_s,
    )


def _toc_result(
    lower_tau: float,
    upper_tau: float,
    interval_start_s: float,
    duration: float,
    status: str,
    iterations: int,
    distance_tolerance_m: float,
    time_tolerance_s: float,
) -> TOCResult:
    lower_s = interval_start_s + lower_tau * duration
    upper_s = interval_start_s + upper_tau * duration
    return TOCResult(
        collided=True,
        toc_s=upper_s,
        bracket_s=(lower_s, upper_s),
        status=status,
        iterations=iterations,
        distance_tolerance_m=distance_tolerance_m,
        time_tolerance_s=time_tolerance_s,
    )


def _pose_motion_bound(start: VesselPose, end: VesselPose) -> float:
    translation = float(np.hypot(end.north_m - start.north_m, end.east_m - start.east_m))
    rotation = abs(_wrap_angle(end.heading_rad - start.heading_rad))
    return translation + rotation * max(start.corner_radius_m, end.corner_radius_m)


def _relative_motion_bound(
    own_start: VesselPose,
    own_end: VesselPose,
    target_start: VesselPose,
    target_end: VesselPose,
) -> float:
    return _pose_motion_bound(own_start, own_end) + _pose_motion_bound(target_start, target_end)


def _wrap_angle(value: float) -> float:
    return float((value + np.pi) % (2.0 * np.pi) - np.pi)
