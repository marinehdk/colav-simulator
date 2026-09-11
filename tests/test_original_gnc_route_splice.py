"""P1 route-admission seam: pure splice geometry and gate-mirror contracts."""

from __future__ import annotations

import math
from types import SimpleNamespace

import numpy as np
import pytest

from colav_simulator.original_gnc.geometry import RouteFrame
from colav_simulator.original_gnc.plan_bridge import ReferenceMirror, classify_rejection
from colav_simulator.original_gnc.route_splice import (
    FIRST_CHANGE_GATE_M,
    ReferencePath,
    along_track_progress,
    build_avoidance_route,
    first_change_distance_ahead,
    first_geometry_change_index,
    has_reverse_segment,
    intent_line_deviation,
    max_lateral_delta,
    merge_short_segments,
    split_sharp_vertices,
)


def _line_reference(spacing: float, count: int, speed: float = 7.8) -> ReferencePath:
    points = np.vstack((np.zeros(count), np.arange(count) * spacing))
    return ReferencePath(points=points, speeds=[speed] * count, modes=["cruise"] * count)


def _publish(topic: str, fields: dict) -> dict:
    return {"event": "publish", "topic": topic, "message": {"type": "test", "fields": fields}}


def _route_plan(route_id: str, points: np.ndarray, modes: list[str], route_type: str = "avoidance") -> dict:
    return {
        "route_id": route_id,
        "route_type": route_type,
        "latitude": [58.0 + p[0] * 9e-6 for p in points.T],
        "longitude": [6.0 + p[1] * 1.6e-5 for p in points.T],
        "speed_limit_mps": [7.8] * points.shape[1],
        "navigation_mode": modes,
    }


def test_gate_mirrors_reproduce_frozen_semantics():
    reference = np.vstack((np.zeros(4), np.array([0.0, 100.0, 200.0, 300.0])))
    assert first_geometry_change_index(reference, reference) == -1
    candidate = reference.copy()
    candidate[1, 2] += 1.001
    assert first_geometry_change_index(candidate, reference) == 2
    candidate2 = np.hstack((reference, np.vstack(([400.0], [400.0]))))
    assert first_geometry_change_index(candidate2, reference) == 4
    assert first_geometry_change_index(reference[:, :2], reference) == 2  # frozen returns n when lengths differ
    assert along_track_progress(reference[:, 1], reference) == pytest.approx(100.0)
    turn_ok = np.vstack(([0.0, 100.0, 199.9], [0.0, 0.0, 17.4]))
    turn_reversed = np.vstack(([0.0, 100.0, 0.1], [0.0, 0.0, 0.0]))
    assert has_reverse_segment(turn_ok) is False
    assert has_reverse_segment(turn_reversed) is True
    offset = np.vstack(([50.0], [30.0]))
    assert max_lateral_delta(offset, reference) == pytest.approx(50.0)  # north offset from the east-running line


def test_first_change_gate_boundary_pushes_deviations_past_150m():
    reference = _line_reference(100.0, 8)
    ship = np.array([10.0, 0.0])
    course = math.radians(60.0)
    deviation, diagnostics = intent_line_deviation(ship, course, reference)
    candidate = build_avoidance_route(reference, ship, deviation, [7.8] * deviation.shape[1])
    ahead = first_change_distance_ahead(candidate["points"], reference.points, ship)
    # The frozen gate rejects first changed waypoints closer than 150 m; the
    # adapter margin target is 160 m, so 149.99 m placements never leave here.
    assert diagnostics["first_change_ahead_m"] == pytest.approx(160.0, abs=1.0)
    assert ahead >= FIRST_CHANGE_GATE_M
    near = np.hstack((reference.points[:, :2], np.vstack(([0.0], [151.99]))))
    assert first_change_distance_ahead(near, reference.points, np.array([0.0, 2.0])) == pytest.approx(149.99, abs=0.01)


def test_splice_geometry_segments_turns_and_rejoin():
    reference = _line_reference(500.0, 10)
    ship = np.array([40.0, 0.0])
    course = math.radians(45.0)
    deviation, _ = intent_line_deviation(ship, course, reference)
    speeds = [6.5] * deviation.shape[1]
    candidate = build_avoidance_route(reference, ship, deviation, speeds)
    points, modes = candidate["points"], candidate["modes"]
    k, j = candidate["prefix_length"], candidate["rejoin_index"]
    deviation_end = points.shape[1] - (reference.points.shape[1] - j)  # first tail index in the candidate
    assert k == 1  # first reference waypoint at least 160 m ahead of the ship
    assert j == 1  # first waypoint past the deviation end with a 30 m rejoin segment
    assert np.allclose(points[:, :k], reference.points[:, :k])
    assert np.allclose(points[:, deviation_end:], reference.points[:, j:])
    new = points[:, k:deviation_end]
    gaps = np.linalg.norm(np.diff(new, axis=1), axis=0)
    assert gaps.min() >= 30.0
    for index in range(k, deviation_end):
        incoming = points[:, index] - points[:, index - 1]
        outgoing = points[:, index + 1] - points[:, index]
        angle = math.acos(np.clip(np.dot(incoming, outgoing) / (np.linalg.norm(incoming) * np.linalg.norm(outgoing)), -1, 1))
        assert angle < math.radians(150.0)
    assert modes[:k] == ["cruise"]
    assert set(modes[k:deviation_end]) == {"avoidance"}
    assert modes[deviation_end:] == ["cruise"] * (reference.points.shape[1] - j)
    assert candidate["speeds"][:k] == [7.8]
    assert candidate["speeds"][k:deviation_end] == [6.5] * (deviation_end - k)
    assert candidate["speeds"][deviation_end:] == [7.8] * (reference.points.shape[1] - j)
    segment = points[:, k:deviation_end]
    directions = np.diff(segment, axis=1) / np.linalg.norm(np.diff(segment, axis=1), axis=0)
    expected = np.array([[math.cos(course)], [math.sin(course)]])
    assert np.allclose(directions.T @ expected, 1.0, atol=1e-9)
    offsets = points[:, k:deviation_end] - ship[:, None]
    perpendicular = np.abs(offsets[0] * math.sin(course) - offsets[1] * math.cos(course))
    assert perpendicular.max() <= 1.0  # deviation waypoints stay on the planner intent line


def test_merge_and_fillet_helpers():
    points = np.array([[0.0, 5.0, 40.0, 100.0], [0.0, 5.0, 1.0, 0.0]])
    merged, keep = merge_short_segments(points)
    assert keep == [0, 2, 3]
    gaps = np.linalg.norm(np.diff(merged, axis=1), axis=0)
    assert gaps.min() >= 30.0
    assert merged[:, 0].tolist() == [0.0, 0.0]
    sharp = np.array([[0.0, 100.0, 9.4], [0.0, 0.0, -42.3]])  # 155 degree interior turn
    assert has_reverse_segment(sharp) is True
    fillet = split_sharp_vertices(sharp)
    assert has_reverse_segment(fillet) is False
    gaps = np.linalg.norm(np.diff(fillet, axis=1), axis=0)
    assert gaps.min() >= 30.0


def _assert_gate_clean(candidate: dict, reference: ReferencePath, ship: np.ndarray) -> None:
    points = candidate["points"]
    assert has_reverse_segment(points) is False
    gaps = np.linalg.norm(np.diff(points, axis=1), axis=0)
    assert gaps.min() >= 30.0
    ahead = first_change_distance_ahead(points, reference.points, ship)
    assert not np.isfinite(ahead) or ahead >= FIRST_CHANGE_GATE_M
    assert candidate["min_interior_turn_deg"] < 150.0
    assert candidate["gate_clean"] is True


def test_splice_trims_start_junction_reversal_seen_in_admission_smoke():
    """Replay of the vo-paper_ccta2023_multiship-E0 held-intent-36 reverse reject.

    The mirror was the accepted held-intent-34 route; the held intent line
    starts 105 m off the ship and its first deviation point sits north-east of
    the reference splice waypoint while the route travels south, so the
    ref[k-1] junction measured 153.1 deg and the frozen transform rejected the
    publication with "reverse segment detected" (99 resubmissions).
    """
    reference = ReferencePath(
        points=np.array(
            [
                [308.168, 308.384, 336.744, 353.196, 356.487, 359.778, 363.068, 366.359, 382.812, 3150.0, 3650.0, 4350.0],
                [
                    -1472.552,
                    -1633.463,
                    -1606.669,
                    -1773.717,
                    -1807.127,
                    -1840.537,
                    -1873.947,
                    -1907.356,
                    -2074.405,
                    -2100.0,
                    -1350.0,
                    -50.0,
                ],
            ]
        ),
        speeds=[7.8] * 12,
        modes=["cruise"] * 12,
    )
    deviation = np.array(
        [
            [330.72, 346.729, 349.931, 353.133, 356.335, 359.537, 362.739],
            [-1589.348, -1751.895, -1784.405, -1816.914, -1849.423, -1881.933, -1914.442],
        ]
    )
    ship = np.array([320.43, -1484.85])
    candidate = build_avoidance_route(reference, ship, deviation, [7.8] * deviation.shape[1])
    _assert_gate_clean(candidate, reference, ship)
    # Trimmed deviation columns stay on the held intent line.
    tail = reference.points.shape[1] - candidate["rejoin_index"]
    submitted = candidate["points"][:, candidate["prefix_length"] : candidate["points"].shape[1] - tail]
    ray = deviation[:, 1] - deviation[:, 0]
    ray = ray / np.linalg.norm(ray)
    offsets = submitted - deviation[:, 0][:, None]
    perpendicular = np.abs(offsets[0] * ray[1] - offsets[1] * ray[0])
    assert perpendicular.max() <= 1.0


def test_splice_trims_reverse_closing_leg_into_rejoin():
    """A deviation end that closes onto the rejoin in reverse must be trimmed.

    Fan-MPC cells produced 155-173 deg turns at the last deviation vertex when
    the intent ray ran past the reference end and the closing leg pointed back
    at the rejoin waypoint; the frozen transform answers with "reverse segment
    detected".
    """
    reference = _line_reference(400.0, 6)
    ship = np.array([60.0, 0.0])
    deviation = np.array(
        [
            [80.0, 95.0, 105.0, 115.0, 125.0],
            [500.0, 900.0, 1300.0, 1700.0, 2400.0],
        ]
    )
    candidate = build_avoidance_route(reference, ship, deviation, [7.8] * deviation.shape[1])
    _assert_gate_clean(candidate, reference, ship)


def test_mirror_rotates_on_accepted_routes_including_internal_returns():
    frame = RouteFrame(1000.0, 2000.0)
    events: list[dict] = []
    ship = SimpleNamespace(_events=events, frame=frame)
    mirror = ReferenceMirror(ship)
    assert mirror.path is None
    nominal = _route_plan("nominal-1", np.array([[0.0, 2500.0], [0.0, 0.0]]), ["cruise", "cruise"], "nominal")
    events.append(_publish("/gnc/active_route", nominal))
    events.append(_publish("/route_planning/route_plan_status", {"route_id": "nominal-1", "status": "ACCEPTED"}))
    mirror.refresh()
    assert mirror.path is not None and mirror.path.points.shape == (2, 2)
    rejected = _route_plan("avoidance-x", np.array([[0.0, 100.0], [500.0, 500.0]]), ["avoidance", "avoidance"])
    events.append(_publish("/gnc/active_route", rejected))
    events.append(
        _publish("/route_planning/route_plan_status", {"route_id": "avoidance-x", "status": "REJECTED", "reason": "x"})
    )
    mirror.refresh()
    assert mirror.path.points.shape == (2, 2)
    internal = _route_plan(
        "return-1", np.array([[10.0, 500.0, 2500.0], [0.0, 0.0, 0.0]]), ["cruise"] * 3, "internal_return_to_route"
    )
    events.append(_publish("/gnc/active_route", internal))
    events.append(_publish("/route_planning/route_plan_status", {"route_id": "return-1", "status": "ACCEPTED"}))
    mirror.refresh()
    assert mirror.route_type == "internal_return_to_route"
    assert mirror.path.points.shape == (2, 3)
    events.append(_publish("/gnc/active_route", internal))
    events.append(_publish("/route_planning/route_plan_status", {"route_id": "return-1", "status": "IGNORED_DUPLICATE"}))
    mirror.refresh()
    assert mirror.path.points.shape == (2, 3)


def test_rejection_classification_splits_addressable_from_dynamic():
    assert (
        classify_rejection({"topic": "/route_planning/route_plan_status", "reason": "route update too frequent"})["class"]
        == "ADDRESSABLE"
    )
    assert (
        classify_rejection(
            {"topic": "/route_planning/route_plan_status", "reason": "first changed waypoint is too close to ship"}
        )["class"]
        == "ADDRESSABLE"
    )
    assert (
        classify_rejection(
            {"topic": "/route_planning/route_plan_status", "reason": "dynamic route lateral offset exceeds limit"}
        )["class"]
        == "ADDRESSABLE"
    )
    assert (
        classify_rejection({"topic": "/route_planning/route_plan_status", "reason": "reverse segment detected"})["class"]
        == "ADDRESSABLE"
    )
    for reason in (
        "segment_too_short",
        "speed_exceeds_vessel_limit",
        "turn_radius_too_small",
        "yaw_rate_too_high",
        "decel_distance_not_enough",
        "heading_path_conflict",
        "avoidance_parent_route_version_mismatch",
        "plan_expired",
    ):
        classified = classify_rejection({"topic": "/gnc/route_execution_status", "reason": reason})
        assert classified["class"] == "DYNAMIC", reason
    assert classify_rejection({"topic": "/gnc/route_execution_status", "reason": "mystery"})["class"] == "DYNAMIC"
    assert classify_rejection({"topic": "/route_planning/route_plan_status", "reason": "mystery"})["class"] == "ADDRESSABLE"


def _nominal_line(spacing: float, count: int, speed: float = 7.8) -> ReferencePath:
    """Mission route along east with mission speeds, mirroring a forwarded nominal."""
    points = np.vstack((np.zeros(count), np.arange(count) * spacing))
    return ReferencePath(points=points, speeds=[speed] * count, modes=["cruise"] * count)


def test_rejoin_against_nominal_reference_decompounds_splice():
    """Rejoin and tail must come from the mission route, not the rotated splice.

    A second splice built against the previous splice inherits its deviation
    geometry: the closing leg hooks onto the previous rejoin and old deviation
    vertices persist kilometres behind the ship, where the frozen manager still
    degrades the whole route speed for them. Computing the rejoin against the
    nominal mission reference keeps every generation's tail verbatim nominal.
    """
    nominal = _nominal_line(500.0, 10)
    kinked = np.array(
        [
            [0.0, 90.0, 95.0],
            [600.0, 604.0, 640.0],
        ]
    )  # previous deviation remnant with a sharp 84 deg vertex near the route
    reference = ReferencePath(
        points=np.hstack((nominal.points[:, :1], kinked, nominal.points[:, 3:])),
        speeds=[*nominal.speeds[:1], *([2.0] * 3), *nominal.speeds[3:]],
        modes=["cruise", "avoidance", "avoidance", "avoidance", *(["cruise"] * 7)],
    )
    ship = np.array([40.0, 0.0])
    course = math.radians(45.0)
    deviation, _ = intent_line_deviation(ship, course, reference)
    candidate = build_avoidance_route(reference, ship, deviation, [6.5] * deviation.shape[1], rejoin_reference=nominal)
    j = candidate["rejoin_index"]
    tail_start = candidate["points"].shape[1] - (nominal.points.shape[1] - j)
    tail = candidate["points"][:, tail_start:]
    for column in range(tail.shape[1]):  # every tail waypoint is a nominal mission waypoint
        assert np.linalg.norm(tail[:, column] - nominal.points[:, j + column]) == pytest.approx(0.0, abs=1e-6)
    assert candidate["modes"][tail_start:] == nominal.modes[j:]
    assert candidate["speeds"][tail_start:] == nominal.speeds[j:]
    assert set(candidate["modes"][candidate["prefix_length"] : tail_start]) == {"avoidance"}
    _assert_gate_clean(candidate, reference, ship)


def test_deviation_mode_policy_can_limit_cap_exposure_to_the_entry_leg():
    """Static-hazard-only deviations carry code-6 on the first deviation waypoint.

    The frozen guidance caps avoidance-tagged legs to 3.2 m/s (leg-scoped on the
    tracked target), while coordinate_transform's relaxed update tier needs one
    code-6 waypoint anywhere in the route. Tagging only the deviation entry
    keeps admission and preserves raw geometry (whole-route smoothing bypass)
    while the remaining deviation legs transit at the planner-commanded speed.
    """
    reference = _line_reference(500.0, 10)
    ship = np.array([40.0, 0.0])
    deviation, _ = intent_line_deviation(ship, math.radians(45.0), reference)
    policy = lambda count: ["avoidance"] + ["cruise"] * (count - 1)  # noqa: E731 - static-only tagging
    candidate = build_avoidance_route(
        reference,
        ship,
        deviation,
        [6.5] * deviation.shape[1],
        deviation_mode_policy=policy,
    )
    k = candidate["prefix_length"]
    tail = reference.points.shape[1] - candidate["rejoin_index"]
    modes = candidate["modes"][k : candidate["points"].shape[1] - tail]
    assert modes[0] == "avoidance"
    assert set(modes[1:]) == {"cruise"}
    _assert_gate_clean(candidate, reference, ship)


def test_mirror_sanitizes_sub_floor_legs_but_keeps_frozen_geometry():
    """Internal-return references are re-anchored past their sub-floor head leg.

    The frozen manager's internal return route starts with a waypoint 1.5-5.5 m
    from its head; the manager then rejects every later splice that inherits
    that leg (segment_too_short, 30 m floor) and the bridge drops all further
    intents. The splice reference therefore merges sub-floor legs, while the
    verbatim accepted geometry stays available for the frozen first-changed
    admission math.
    """
    frame = RouteFrame(1000.0, 2000.0)
    events: list[dict] = []
    ship = SimpleNamespace(_events=events, frame=frame)
    mirror = ReferenceMirror(ship)
    internal = _route_plan(
        "original-gnc-mission-0:return:1",
        np.array([[0.0, 5.5, 300.0, 2500.0], [0.0, 0.0, 0.0, 0.0]]),
        ["cruise"] * 4,
        "internal_return_to_route",
    )
    events.append(_publish("/gnc/active_route", internal))
    events.append(
        _publish("/route_planning/route_plan_status", {"route_id": "original-gnc-mission-0:return:1", "status": "ACCEPTED"})
    )
    mirror.refresh()
    points = mirror.path.points
    gaps = np.linalg.norm(np.diff(points, axis=1), axis=0)
    assert gaps.min() >= 30.0
    assert points.shape[1] == 3  # 5.5 m leg re-anchored onto the first >=30 m waypoint
    assert mirror.frozen_points.shape[1] == 4  # verbatim geometry stays for admission math


def test_mirror_keeps_planner_speeds_when_manager_degrades():
    """Manager-degraded executed speeds never enter the reference mirror.

    apply_speed_degradation clamps every published speed_limit_mps (turn radius,
    yaw rate); absorbing the clamped array made each next splice inherit the cap
    and ratcheted route speeds down to 0.59 m/s. Degradation is execution-time
    only: the reference keeps the speeds the bridge submitted.
    """
    frame = RouteFrame(1000.0, 2000.0)
    events: list[dict] = []
    ship = SimpleNamespace(_events=events, frame=frame, _requested_plans=[])
    mirror = ReferenceMirror(ship)
    route = _route_plan("vo-held-intent-1", np.array([[0.0, 200.0, 400.0], [0.0, 0.0, 0.0]]), ["avoidance"] * 3)
    route["speed_limit_mps"] = [0.59, 0.59, 0.59]
    ship._requested_plans.append(
        {
            "kind": "avoidance",
            "time_ns": 0,
            "identity": {},
            "message": {"plan_id": "vo-held-intent-1", "command_speed_mps": [7.8, 2.9, 2.9]},
        }
    )
    events.append(_publish("/gnc/active_route", route))
    events.append(
        _publish(
            "/gnc/route_execution_status",
            {"plan_id": "vo-held-intent-1", "accepted": True, "degraded": True, "reason": "yaw_rate_limited"},
        )
    )
    events.append(
        _publish("/route_planning/route_plan_status", {"route_id": "vo-held-intent-1", "status": "ACCEPTED"})
    )
    mirror.refresh()
    assert [round(value, 6) for value in mirror.path.speeds] == [7.8, 2.9, 2.9]
    mirror_healthy = ReferenceMirror(ship)
    events.append(_publish("/gnc/active_route", {**route, "speed_limit_mps": [7.8, 2.9, 2.9]}))
    events.append(
        _publish(
            "/gnc/route_execution_status",
            {"plan_id": "vo-held-intent-1", "accepted": True, "degraded": False, "reason": "feasible"},
        )
    )
    events.append(
        _publish("/route_planning/route_plan_status", {"route_id": "vo-held-intent-1", "status": "ACCEPTED"})
    )
    mirror_healthy.refresh()
    assert mirror_healthy.path.speeds == [7.8, 2.9, 2.9]
