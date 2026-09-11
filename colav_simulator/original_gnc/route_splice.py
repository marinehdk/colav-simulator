"""Splice geometry mirroring the frozen original route-admission gates.

All quantities are map-frame north/east meters, matching the adapter's route
coordinates. The gate mirrors reproduce the frozen semantics (read-only
sources) that decide admission after active_route_manager forwards a plan:

- coordinate_transform_node.cpp: ``first_geometry_change_index`` (1.0 m),
  ``compute_along_track_progress``, ``compute_max_lateral_delta``,
  ``has_reverse_segment`` (cos < -cos 30 deg, i.e. interior turns > 150 deg)
  and the emergency-avoidance tier (any code-6 waypoint relaxes the dynamic
  update guard to first-change >= 150 m, lateral <= 500 m and skips the
  cadence gate) around lines 478-620 and 784-880.
- active_route_manager_node.cpp: segment length >= 30 m (``min_segment_length_m``)
  and interior kinematic gates; this module enforces the geometric part
  (segments >= 30 m, interior turns < 150 deg) adapter-side.
- ship_guidance_node.cpp lines ~2536-2543 and ~5970-5976: the 3.2 m/s
  avoidance surge cap is leg-scoped - it applies while the tracked target or
  its predecessor waypoint is avoidance-tagged, not route-global - so only
  deviation waypoints carry the "avoidance" tag to minimize cap exposure.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

FIRST_CHANGE_GATE_M = 150.0
FIRST_CHANGE_MARGIN_M = 160.0
MIN_SEGMENT_M = 30.0
# The manager re-projects lat/lon with its own equirectangular approximation, so
# segments built at exactly 30.0 geodesic meters can evaluate below its gate.
SEGMENT_FLOOR_M = MIN_SEGMENT_M + 2.0
MAX_TURN_RAD = math.radians(150.0)
MAX_LATERAL_M = 500.0
LATERAL_ENVELOPE_M = 480.0
AVOIDANCE_MODE = "avoidance"


@dataclass
class ReferencePath:
    """The mirrored last-accepted feedback path with its route contract arrays."""

    points: np.ndarray
    speeds: list[float]
    modes: list[str]
    latitudes: list[float] | None = None
    longitudes: list[float] | None = None


def along_track_progress(point: np.ndarray, path: np.ndarray) -> float:
    """Mirror of coordinate_transform_node.cpp compute_along_track_progress."""
    if path.shape[1] < 2:
        return math.nan
    best_distance = math.inf
    best_along = 0.0
    accumulated = 0.0
    for index in range(path.shape[1] - 1):
        dx = path[0, index + 1] - path[0, index]
        dy = path[1, index + 1] - path[1, index]
        seg_len_sq = dx * dx + dy * dy
        if seg_len_sq < 1e-9:
            continue
        seg_len = math.sqrt(seg_len_sq)
        t = max(0.0, min(1.0, ((point[0] - path[0, index]) * dx + (point[1] - path[1, index]) * dy) / seg_len_sq))
        px = path[0, index] + t * dx
        py = path[1, index] + t * dy
        dist = math.hypot(point[0] - px, point[1] - py)
        if dist < best_distance:
            best_distance = dist
            best_along = accumulated + t * seg_len
        accumulated += seg_len
    return best_along


def max_lateral_delta(points: np.ndarray, reference: np.ndarray) -> float:
    """Mirror of coordinate_transform_node.cpp compute_max_lateral_delta."""
    if points.size == 0 or reference.shape[1] < 2:
        return math.nan
    max_lateral = 0.0
    for column in range(points.shape[1]):
        best = math.inf
        for index in range(reference.shape[1] - 1):
            dx = reference[0, index + 1] - reference[0, index]
            dy = reference[1, index + 1] - reference[1, index]
            seg_len = math.hypot(dx, dy)
            if seg_len < 1e-6:
                continue
            cross = dx * (points[1, column] - reference[1, index]) - dy * (points[0, column] - reference[0, index])
            lateral = abs(cross) / seg_len
            best = min(best, lateral)
        if math.isfinite(best):
            max_lateral = max(max_lateral, best)
    return max_lateral


def first_geometry_change_index(candidate: np.ndarray, reference: np.ndarray, tolerance_m: float = 1.0) -> int:
    """Mirror of coordinate_transform_node.cpp first_geometry_change_index."""
    count = min(candidate.shape[1], reference.shape[1])
    for index in range(count):
        if math.hypot(candidate[0, index] - reference[0, index], candidate[1, index] - reference[1, index]) > tolerance_m:
            return index
    if candidate.shape[1] != reference.shape[1]:
        return count
    return -1


def first_change_distance_ahead(candidate: np.ndarray, reference: np.ndarray, position: np.ndarray) -> float:
    """Along-track distance from the ship to the candidate's first changed waypoint."""
    index = first_geometry_change_index(candidate, reference)
    if index < 0 or index >= candidate.shape[1]:
        return math.nan
    return along_track_progress(candidate[:, index], reference) - along_track_progress(position, reference)


def has_reverse_segment(path: np.ndarray) -> bool:
    """Mirror of coordinate_transform_node.cpp has_reverse_segment (turns > 150 deg)."""
    if path.shape[1] < 3:
        return False
    threshold = -0.8660254037844386
    for index in range(1, path.shape[1] - 1):
        ax = path[0, index] - path[0, index - 1]
        ay = path[1, index] - path[1, index - 1]
        bx = path[0, index + 1] - path[0, index]
        by = path[1, index + 1] - path[1, index]
        al = math.hypot(ax, ay)
        bl = math.hypot(bx, by)
        if al < 1e-6 or bl < 1e-6:
            continue
        if (ax * bx + ay * by) / (al * bl) < threshold:
            return True
    return False


def merge_short_segments(points: np.ndarray, min_segment_m: float = MIN_SEGMENT_M) -> tuple[np.ndarray, list[int]]:
    """Drop interior waypoints closer than min_segment_m to the last kept point."""
    count = points.shape[1]
    if count < 3:
        return points.copy(), list(range(count))
    keep = [0]
    for index in range(1, count - 1):
        if np.linalg.norm(points[:, index] - points[:, keep[-1]]) >= min_segment_m:
            keep.append(index)
    keep.append(count - 1)
    while len(keep) > 2 and np.linalg.norm(points[:, keep[-1]] - points[:, keep[-2]]) < min_segment_m:
        keep.pop(-2)
    return points[:, keep].copy(), keep


def _turn_angle(path: np.ndarray, index: int) -> float:
    incoming = path[:, index] - path[:, index - 1]
    outgoing = path[:, index + 1] - path[:, index]
    norms = np.linalg.norm(incoming) * np.linalg.norm(outgoing)
    if norms < 1e-9:
        return 0.0
    return math.acos(max(-1.0, min(1.0, float(np.dot(incoming, outgoing)) / norms)))


def split_sharp_vertices(
    points: np.ndarray, max_turn: float = MAX_TURN_RAD, min_segment_m: float = MIN_SEGMENT_M
) -> np.ndarray:
    """Replace interior vertices turning >= max_turn with a two-point fillet."""
    result = points.copy()
    for _ in range(4):
        changed = False
        index = 1
        while 0 < index < result.shape[1] - 1:
            if _turn_angle(result, index) < max_turn:
                index += 1
                continue
            vertex = result[:, index]
            incoming = result[:, index] - result[:, index - 1]
            outgoing = result[:, index + 1] - result[:, index]
            len_in = float(np.linalg.norm(incoming))
            len_out = float(np.linalg.norm(outgoing))
            if len_in < 2 * min_segment_m or len_out < 2 * min_segment_m:
                index += 1
                continue
            replacement = None
            for f_in in (0.5, 0.75, 1.0):
                for f_out in (0.5, 0.75, 1.0):
                    s_in = min_segment_m + f_in * (len_in - 2 * min_segment_m)
                    s_out = min_segment_m + f_out * (len_out - 2 * min_segment_m)
                    a = vertex - incoming / len_in * s_in
                    b = vertex + outgoing / len_out * s_out
                    if np.linalg.norm(b - a) >= min_segment_m:
                        replacement = (a, b)
                        break
                if replacement:
                    break
            if replacement is None:
                index += 1
                continue
            result[:, index] = replacement[0]
            result = np.insert(result, index + 1, replacement[1], axis=1)
            changed = True
            index += 2
        if not changed:
            break
    return result


def _ray_segment_distance(point: np.ndarray, direction: np.ndarray, a: np.ndarray, b: np.ndarray) -> float | None:
    """Arc length along the ray where it crosses segment a-b, else None."""
    v = b - a
    denom = direction[0] * v[1] - direction[1] * v[0]
    if abs(denom) < 1e-9:
        return None
    w = a - point
    s = (w[0] * v[1] - w[1] * v[0]) / denom
    t = (w[0] * direction[1] - w[1] * direction[0]) / denom
    if s > 0.0 and 0.0 <= t <= 1.0:
        return s
    return None


def intent_line_deviation(
    position: np.ndarray,
    course_rad: float,
    reference: ReferencePath,
    step_m: float = 5.0,
    max_reach_m: float = 4000.0,
) -> tuple[np.ndarray, dict]:
    """Pattern A deviation: the intent ray's portion at least 160 m ahead along-track.

    The deviation waypoints are collinear with the planner's held course line
    (deviation from planner intent stays within floating-point tolerance),
    start once the line is FIRST_CHANGE_MARGIN_M ahead of the ship along the
    reference, and end at the ray's last reference crossing or at the frozen
    lateral envelope, whichever comes first.
    """
    ref = reference.points
    direction = np.array([math.cos(course_rad), math.sin(course_rad)])
    ship_along = along_track_progress(position, ref)
    s_start = None
    best_s, best_ahead = 0.0, -math.inf
    s = 0.0
    while s <= max_reach_m:
        ahead = along_track_progress(position + s * direction, ref) - ship_along
        if ahead >= FIRST_CHANGE_MARGIN_M:
            s_start = s
            break
        if ahead > best_ahead:
            best_s, best_ahead = s, ahead
        s += step_m
    flagged = False
    if s_start is None:
        s_start, flagged = best_s, True

    crossings = [
        s_cross
        for index in range(ref.shape[1] - 1)
        if (s_cross := _ray_segment_distance(position, direction, ref[:, index], ref[:, index + 1])) is not None
        and s_cross > s_start + MIN_SEGMENT_M
    ]
    s_end = min(crossings) if crossings else None
    envelope_s = None
    max_along = along_track_progress(ref[:, -1], ref)
    prev_ahead = along_track_progress(position + s_start * direction, ref) - ship_along
    probe = s_start + MIN_SEGMENT_M
    while probe <= s_start + max_reach_m:
        point = position + probe * direction
        ahead = along_track_progress(point, ref) - ship_along
        # Stop at the reference's along extent (or once its projection stops
        # advancing) so the rejoin lands forward of the deviation end.
        if ahead >= max_along - SEGMENT_FLOOR_M or ahead <= prev_ahead + 1e-6:
            break
        prev_ahead = ahead
        lateral = min(
            (
                abs(
                    (ref[0, i + 1] - ref[0, i]) * (point[1] - ref[1, i])
                    - (ref[1, i + 1] - ref[1, i]) * (point[0] - ref[0, i])
                )
                / math.hypot(ref[0, i + 1] - ref[0, i], ref[1, i + 1] - ref[1, i])
            )
            for i in range(ref.shape[1] - 1)
            if math.hypot(ref[0, i + 1] - ref[0, i], ref[1, i + 1] - ref[1, i]) >= 1e-6
        )
        if lateral > LATERAL_ENVELOPE_M:
            break
        envelope_s = probe
        probe += step_m
    if envelope_s is not None:
        s_end = envelope_s if s_end is None else min(s_end, envelope_s)
    if s_end is None or s_end - s_start < MIN_SEGMENT_M:
        s_end = s_start + MIN_SEGMENT_M
    total = s_end - s_start
    segments = max(1, int(total // SEGMENT_FLOOR_M))
    spacing = total / segments
    offsets = [s_start + index * spacing for index in range(segments)] + [s_end]
    # Long first/last deviation segments widen the splice junction turns, which
    # lowers the frozen yaw-rate-limited speed cap at the two junction vertices.
    cap = 150.0
    if len(offsets) >= 4 and total >= 2 * cap:
        interior = [o for o in offsets[1:-1] if s_start + cap <= o <= s_end - cap]
        offsets = [s_start] + interior + [s_end]
    points = np.column_stack([position + offset * direction for offset in offsets])
    diagnostics = {
        "first_change_ahead_m": along_track_progress(points[:, 0], ref) - ship_along,
        "start_offset_m": s_start,
        "end_offset_m": s_end,
        "reference_crossing": bool(crossings),
        "no_forward_gain": flagged,
        "spacing_m": spacing,
    }
    return points, diagnostics


def blend_deviation_toward_reference(deviation: np.ndarray, reference: np.ndarray, fraction: float) -> np.ndarray:
    """Move each deviation point toward its nearest reference point by fraction."""
    blended = deviation.copy()
    for column in range(deviation.shape[1]):
        point = deviation[:, column]
        best_point, best_distance = None, math.inf
        for index in range(reference.shape[1] - 1):
            a = reference[:, index]
            b = reference[:, index + 1]
            seg = b - a
            length_sq = float(np.dot(seg, seg))
            if length_sq < 1e-9:
                continue
            t = max(0.0, min(1.0, float(np.dot(point - a, seg)) / length_sq))
            candidate = a + t * seg
            distance = float(np.linalg.norm(point - candidate))
            if distance < best_distance:
                best_point, best_distance = candidate, distance
        if best_point is not None:
            blended[:, column] = point + fraction * (best_point - point)
    return blended


def build_avoidance_route(
    reference: ReferencePath,
    position: np.ndarray,
    deviation: np.ndarray,
    deviation_speeds: list[float] | np.ndarray,
) -> dict:
    """Splice reference[0:k] ++ deviation ++ reference[j:] with mixed navigation modes.

    k is the first reference waypoint at least FIRST_CHANGE_MARGIN_M ahead of
    the ship along-track, so the first changed waypoint clears the frozen
    150 m gate. The rejoin lands exactly on reference waypoint j. Only the
    deviation waypoints carry the "avoidance" mode: the frozen surge cap is
    leg-scoped (ship_guidance_node.cpp ~2536-2543, ~5970-5976), so tagging
    the reference prefix, rejoin landing and tail keeps cap exposure minimal.
    """
    ref = reference.points
    count = ref.shape[1]
    position = np.asarray(position, dtype=float)
    deviation = np.asarray(deviation, dtype=float)
    dev_speeds = [float(value) for value in deviation_speeds]
    ship_along = along_track_progress(position, ref)
    k = next(
        (index for index in range(count) if along_track_progress(ref[:, index], ref) - ship_along >= FIRST_CHANGE_MARGIN_M),
        count - 1,
    )
    deviation, keep = merge_short_segments(deviation, min_segment_m=SEGMENT_FLOOR_M)
    dev_speeds = [dev_speeds[index] for index in keep]
    while deviation.shape[1] > 1 and np.linalg.norm(deviation[:, 0] - ref[:, k - 1]) < SEGMENT_FLOOR_M:
        deviation = deviation[:, 1:]
        dev_speeds = dev_speeds[1:]
    if deviation.shape[1] < 1:
        raise ValueError("Deviation collapses before clearing the 30 m splice segments")
    if deviation.shape[1] > 2:
        filleted = split_sharp_vertices(deviation, min_segment_m=SEGMENT_FLOOR_M)
        if filleted.shape[1] != deviation.shape[1]:
            # Fillet waypoints inherit the speed of their nearest original deviation point.
            dev_speeds = [
                dev_speeds[int(np.argmin(np.linalg.norm(deviation - point[:, None], axis=0)))] for point in filleted.T
            ]
            deviation = filleted
    end_along = along_track_progress(deviation[:, -1], ref)
    j = next(
        (
            index
            for index in range(k, count)
            if along_track_progress(ref[:, index], ref) >= end_along - 1e-9
            and np.linalg.norm(deviation[:, -1] - ref[:, index]) >= SEGMENT_FLOOR_M
        ),
        None,
    )
    if j is None:
        j = next(
            (index for index in range(k, count) if along_track_progress(ref[:, index], ref) >= end_along - 1e-9),
            count - 1,
        )
    points = np.hstack((ref[:, :k], deviation, ref[:, j:]))
    speeds = [*reference.speeds[:k], *dev_speeds, *reference.speeds[j:]]
    modes = [*reference.modes[:k], *([AVOIDANCE_MODE] * deviation.shape[1]), *reference.modes[j:]]
    deviation_end = k + deviation.shape[1]
    interior_turns = [math.degrees(_turn_angle(points, index)) for index in range(1, points.shape[1] - 1)]
    diagnostics = {
        "first_change_ahead_m": first_change_distance_ahead(points, ref, position),
        "max_lateral_delta_m": max_lateral_delta(points, ref),
        "min_interior_turn_deg": min(interior_turns) if interior_turns else 180.0,
        "min_new_segment_m": min(
            np.linalg.norm(points[:, index + 1] - points[:, index])
            for index in range(max(k - 1, 0), min(deviation_end + 1, points.shape[1] - 1))
        ),
        "prefix_length": k,
        "rejoin_index": j,
        "short_reference": k == count - 1,
    }
    return {"points": points, "speeds": speeds, "modes": modes, **diagnostics}
