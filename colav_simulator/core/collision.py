"""Conservative continuous-segment vessel footprint collision checks."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from shapely import affinity
from shapely.geometry import Polygon, box

COLLISION_ORACLE_ID = "footprint-adaptive-v1"


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


def _wrap_angle(value: float) -> float:
    return float((value + np.pi) % (2.0 * np.pi) - np.pi)
