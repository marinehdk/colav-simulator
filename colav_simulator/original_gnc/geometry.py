"""Explicit original WGS84/local-NED boundary for simulator route coordinates."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from geographiclib.geodesic import Geodesic


@dataclass(frozen=True)
class RouteFrame:
    """Map the first nominal waypoint to the original GNC's locked origin."""

    north_m: float
    east_m: float
    latitude_deg: float = 58.0
    longitude_deg: float = 6.0

    def geographic(self, waypoints: np.ndarray) -> tuple[list[float], list[float]]:
        """Convert framework north/east to the original geodesic route contract."""
        points = np.asarray(waypoints, dtype=float)
        if points.ndim != 2 or points.shape[0] != 2 or not np.isfinite(points).all():
            raise ValueError("Route coordinates must be a finite 2xN north/east array")
        latitudes = []
        longitudes = []
        for n, e in points.T:
            north, east = float(n) - self.north_m, float(e) - self.east_m
            point = Geodesic.WGS84.Direct(
                self.latitude_deg, self.longitude_deg, math.degrees(math.atan2(east, north)), math.hypot(north, east)
            )
            latitudes.append(point["lat2"])
            longitudes.append(point["lon2"])
        return latitudes, longitudes

    def source_position(self, north_m: float, east_m: float) -> tuple[float, float]:
        """Remove the fixed frame origin only at initialization or input conversion."""
        return north_m - self.north_m, east_m - self.east_m


def stamp(time_ns: int) -> dict:
    """Build exact integer seconds/nanoseconds without float epoch arithmetic."""
    return {"sec": time_ns // 1_000_000_000, "nanosec": time_ns % 1_000_000_000}


def nominal_route(
    frame: RouteFrame, waypoints: np.ndarray, speeds: np.ndarray, route_id: str, revision: int, time_ns: int
) -> dict:
    """Keep the mission geometry and its original per-waypoint speed limits."""
    if len(speeds) != waypoints.shape[1] or len(speeds) < 2 or not np.isfinite(speeds).all() or np.any(speeds < 0):
        raise ValueError("Nominal route requires corresponding finite nonnegative speeds")
    latitudes, longitudes = frame.geographic(waypoints)
    return {
        "header": {"stamp": stamp(time_ns), "frame_id": "map"},
        "latitude": latitudes,
        "longitude": longitudes,
        "speed_limit_mps": np.asarray(speeds, dtype=float).tolist(),
        "navigation_mode": ["cruise"] * len(speeds),
        "route_id": route_id,
        "route_revision": revision,
        "route_type": "nominal",
    }
