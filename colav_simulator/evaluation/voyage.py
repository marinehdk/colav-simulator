"""Ownship voyage acceptance metrics: encounter clearance and return-voyage XTE.

Issue #67 slice 1. Two behaviours:

- Encounter clearance: the continuous minimum ownship-to-target centre
  distance over the whole run. Unlike the sampled per-pair minimum in
  ``PairEvaluation.minimum_distance_m``, segment-interpolated minima catch the
  true closest approach between samples.
- Return-voyage cross-track error (XTE): after the controlling encounter CPA
  plus a fixed recovery buffer, the ownship must re-acquire the mission route:
  maximum |XTE| against the original route polyline and the number of full
  crossings of the route line (hysteresis-banded sign changes of the signed
  XTE; dithering inside the band is not a crossing).

The window buffer is sized for the acceptance scenario family: with a
nominal speed of 7 m/s, a rate-of-turn at or below 3 deg/s, and avoidance
offsets of order 200 m, re-acquiring the route corridor needs roughly
90-110 s (turn + lateral closure at 7*sin(20 deg) ~ 2.4 m/s); 120 s gives
margin without hiding late S-shaped wandering.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

from colav_simulator.common.vessel_data import VesselData

if TYPE_CHECKING:
    from colav_simulator.evaluation.evaluator import PairEvaluation

RETURN_WINDOW_BUFFER_S = 120.0
"""Default recovery buffer appended to the controlling CPA time."""

ROUTE_CROSSING_HYSTERESIS_M = 5.0
"""Band around the route line that sample dithering must not count as a crossing."""

OWNSHIP_ID = 0


def signed_cross_track_errors_m(positions_ne: np.ndarray, route_ne: np.ndarray) -> np.ndarray:
    """Return the signed XTE of each position against the route polyline.

    Args:
        positions_ne: (n, 2) array of [north, east] samples.
        route_ne: (m, 2) array of [north, east] route waypoints, m >= 2.

    Returns:
        (n,) signed distances in metres; positive is starboard (right) of the
        route travel direction. Samples before the first / after the last
        waypoint measure against the nearest endpoint.
    """
    positions = np.atleast_2d(np.asarray(positions_ne, dtype=float))
    route = np.atleast_2d(np.asarray(route_ne, dtype=float))
    if route.shape[0] < 2:
        raise ValueError("route_ne requires at least two waypoints")
    segment_starts = route[:-1]
    segment_vectors = np.diff(route, axis=0)
    segment_lengths = np.linalg.norm(segment_vectors, axis=1)
    if np.any(segment_lengths <= 0.0):
        raise ValueError("route_ne contains a zero-length segment")

    # (n, m-1) foot-of-perpendicular fractions along each segment.
    offsets = positions[:, None, :] - segment_starts[None, :, :]
    fractions = np.einsum("nsd,sd->ns", offsets, segment_vectors) / (segment_lengths**2)[None, :]
    clipped = np.clip(fractions, 0.0, 1.0)
    feet = segment_starts[None, :, :] + clipped[:, :, None] * segment_vectors[None, :, :]
    residuals = positions[:, None, :] - feet
    distances = np.linalg.norm(residuals, axis=2)
    nearest = np.argmin(distances, axis=1)

    index = np.arange(positions.shape[0])
    residual_ne = residuals[index, nearest[index]]
    direction = segment_vectors[nearest] / segment_lengths[nearest, None]
    # Starboard of the travel direction: project the residual onto the
    # direction's right-hand normal (north heading -> east side is positive).
    normal_projection = direction[:, 0] * residual_ne[:, 1] - direction[:, 1] * residual_ne[:, 0]
    # Off-route samples (perpendicular foot clipped to a segment endpoint)
    # report the full endpoint distance, signed by the normal projection.
    off_route = np.abs(fractions[index, nearest] - clipped[index, nearest]) > 0.0
    signed = normal_projection.copy()
    signed[off_route] = np.sign(normal_projection[off_route]) * distances[index, nearest][off_route]
    return signed


def route_line_crossings(signed_xte: np.ndarray, hysteresis_m: float = ROUTE_CROSSING_HYSTERESIS_M) -> int:
    """Count full crossings of the route line with a hysteresis band.

    A crossing is committed only when the signed XTE moves from beyond +band
    to beyond -band (or vice versa); excursions that stay inside the band or
    on one side never count.
    """
    values = np.asarray(signed_xte, dtype=float)
    state = 0  # -1 port, 0 inside band, +1 starboard
    crossings = 0
    for value in values:
        if not np.isfinite(value):
            continue
        if value > hysteresis_m:
            current = 1
        elif value < -hysteresis_m:
            current = -1
        else:
            current = 0
        if state != 0 and current not in (0, state):
            crossings += 1
        if current != 0:
            state = current
    return crossings


def min_encounter_center_distance(vessels: list[VesselData]) -> dict[str, float | int | None]:
    """Continuous minimum centre distance between the ownship and every target."""
    ownship = next((vessel for vessel in vessels if vessel.id == OWNSHIP_ID), None)
    if ownship is None:
        return {"min_target_center_distance_m": None, "controlling_target_id": None}
    best: float | None = None
    controlling: int | None = None
    for target in vessels:
        if target.id == OWNSHIP_ID:
            continue
        distance = _pair_continuous_minimum(ownship, target)
        if distance is not None and (best is None or distance < best):
            best = distance
            controlling = target.id
    return {"min_target_center_distance_m": best, "controlling_target_id": controlling}


def _pair_continuous_minimum(ownship: VesselData, target: VesselData) -> float | None:
    common, own_indices, target_indices = np.intersect1d(
        np.asarray(ownship.timestamps, dtype=float),
        np.asarray(target.timestamps, dtype=float),
        assume_unique=False,
        return_indices=True,
    )
    if common.size == 0:
        return None
    relative = target.xy[:, target_indices] - ownship.xy[:, own_indices]
    finite = np.all(np.isfinite(relative), axis=0)
    relative = relative[:, finite]
    if relative.shape[1] == 0:
        return None
    if relative.shape[1] == 1:
        return float(np.linalg.norm(relative[:, 0]))
    starts = relative[:, :-1].T
    deltas = np.diff(relative, axis=1).T
    lengths_squared = np.einsum("ij,ij->i", deltas, deltas)
    fractions = np.divide(
        -np.einsum("ij,ij->i", starts, deltas),
        lengths_squared,
        out=np.zeros_like(lengths_squared),
        where=lengths_squared > 0.0,
    )
    closest = starts + np.clip(fractions, 0.0, 1.0)[:, None] * deltas
    return float(np.min(np.linalg.norm(closest, axis=1)))


def return_voyage_metrics(
    ownship: VesselData,
    route_ne: np.ndarray,
    *,
    cpa_time_s: float | None,
    buffer_s: float = RETURN_WINDOW_BUFFER_S,
    hysteresis_m: float = ROUTE_CROSSING_HYSTERESIS_M,
) -> dict[str, Any] | None:
    """Return the CPA-anchored return-voyage XTE block, or None without samples."""
    route = np.atleast_2d(np.asarray(route_ne, dtype=float))
    if route.shape[0] < 2:
        return None
    anchor = cpa_time_s if cpa_time_s is not None else float(ownship.timestamps[ownship.first_valid_idx])
    window_start = float(anchor + buffer_s)
    timestamps = np.asarray(ownship.timestamps, dtype=float)
    valid = np.isfinite(timestamps) & np.all(np.isfinite(ownship.xy), axis=0)
    in_window = valid & (timestamps >= window_start)
    sample_count = int(np.count_nonzero(in_window))
    document: dict[str, Any] = {
        "window_start_s": window_start,
        "cpa_time_s": float(cpa_time_s) if cpa_time_s is not None else None,
        "buffer_s": float(buffer_s),
        "max_abs_xte_m": None,
        "route_crossings": None,
        "sample_count": sample_count,
    }
    if sample_count == 0:
        return document
    positions_ne = np.vstack((ownship.xy[1, in_window], ownship.xy[0, in_window])).T
    signed = signed_cross_track_errors_m(positions_ne, route)
    document["max_abs_xte_m"] = float(np.max(np.abs(signed[np.isfinite(signed)]))) if np.isfinite(signed).any() else None
    document["route_crossings"] = route_line_crossings(signed, hysteresis_m)
    return document


def voyage_metrics_section(
    vessels: list[VesselData],
    pair_results: list[PairEvaluation],
    context: dict[str, Any],
) -> dict[str, Any]:
    """Assemble the evaluator report's voyage section from run evidence."""
    encounter = min_encounter_center_distance(vessels)
    ownship_pairs = [
        result for result in pair_results if OWNSHIP_ID in {result.ownship_id, result.target_id}
    ]
    cpa_time_s = max((result.cpa_time_s for result in ownship_pairs), default=None)
    return_voyage = None
    route = _route_from_context(context.get("ownship_route_waypoints_ne"))
    if route is not None:
        ownship = next((vessel for vessel in vessels if vessel.id == OWNSHIP_ID), None)
        if ownship is not None:
            return_voyage = return_voyage_metrics(
                ownship,
                route,
                cpa_time_s=cpa_time_s,
                buffer_s=float(context.get("return_window_buffer_s", RETURN_WINDOW_BUFFER_S)),
            )
    return {"encounter": encounter, "return_voyage": return_voyage}


def _route_from_context(value: Any) -> np.ndarray | None:
    """Decode the per-waypoint route rows [north, east] carried by the context.

    Callers owning a scenario-layout ``[[north...], [east...]]`` array transpose
    it before injecting; the contract here is unambiguous (m, 2) rows.
    """
    if value is None:
        return None
    route = np.asarray(value, dtype=float)
    if route.ndim != 2 or route.shape[0] < 2 or route.shape[1] != 2:
        return None
    return route
