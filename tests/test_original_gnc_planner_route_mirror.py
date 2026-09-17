"""Planner-owned routes stay point-for-point through the GNC route chain.

The ho_extturn17 evidence chain showed the route mirror collapsing at
T=191.0: the 86-point Mid-MPC stitch plan was rejected by
evaluate_avoidance_plan with segment_too_short (one boundary leg at
29.949 m against the 30.0 m hand-route floor), and the expired plan
collapsed into the 3-point internal_return_to_route, which became the
frozen mirror and starved the next splice. Separately, the guidance
turn-arc rewrite (as-run external-route parameters) replaces mirrored
points of any >=40-point route with Chaikin/arc geometry and overrides
their admission-validated speeds.

For planner-owned routes (command source mid_mpc_ipopt) both rewrites are
waived: admission tolerates sub-floor segments (every other gate still
applies, emergency keeps its 15 m floor), and guidance keeps the mirrored
per-point geometry. Operator and collision_avoidance routes keep the
legacy behavior, and both rollback parameters restore it.
"""

import math

import pytest

from colav_simulator.original_gnc.configuration import OriginalGncConfig
from colav_simulator.original_gnc.native import NativeModule

STAMP = 2_000_000_000_000_000_000
HEADER = {"frame_id": "map", "stamp": {"sec": 2_000_000_000, "nanosec": 0}}
BASE_NOMINAL = {
    "header": HEADER,
    "route_id": "original-gnc-mission-0",
    "route_revision": 1,
    "route_type": "nominal",
    "latitude": [58.00000000000001, 58.030513695341625],
    "longitude": [6.0, 6.05754660552896],
    "navigation_mode": ["cruise", "dp_hold"],
    "speed_limit_mps": [7.0, 7.0],
}


def _guidance_pose(x: float, y: float) -> dict:
    """Mirror coordinate_transform's Path encoding of a route point."""
    return {
        "header": HEADER,
        "pose": {
            "position": {"x": x, "y": y, "z": 1.0},
            "orientation": {"x": 0.0, "y": 1.0, "z": 8.0, "w": 1.0},
        },
    }


def _bend_path(points: int = 45, step_m: float = 601.0, bend_deg: float = 25.0) -> dict:
    """A >=40-point route with one bend that qualifies for the arc rewrite.

    Both legs of the 25 deg bend are 601 m, so the external-route gates
    (min 40 points, min 20 deg, min 600 m legs) all fire for the legacy
    behavior.
    """
    poses = []
    x = y = 0.0
    heading = 0.0
    bend_index = points // 2
    for index in range(points):
        poses.append(_guidance_pose(x, y))
        if index == bend_index:
            heading += math.radians(bend_deg)
        x += step_m * math.cos(heading)
        y += step_m * math.sin(heading)
    return {"header": HEADER, "poses": poses}


def _route_status(command_source: str) -> dict:
    return {
        "header": HEADER,
        "plan_id": "mid-mpc-probe",
        "active_route_id": "mid-mpc-probe",
        "active_route_revision": 1,
        "command_source": command_source,
        "accepted": True,
        "executing": True,
        "degraded": False,
        "rejected": False,
        "execution_state": "ACCEPTED",
        "reason": "",
        "suggested_action": "",
        "requested_speed_mps": 8.0,
        "applied_speed_mps": 8.0,
        "requested_heading_deg": 0.0,
        "applied_heading_deg": 0.0,
        "current_latitude": 0.0,
        "current_longitude": 0.0,
        "current_heading_deg": 0.0,
        "current_course_deg": 0.0,
        "current_speed_mps": 5.0,
        "cross_track_error_m": 0.0,
        "stage_snapshot_valid": False,
        "current_segment_index": 0,
        "current_target_waypoint_index": 1,
        "current_navigation_mode": "cruise",
        "current_speed_limit_mps": 8.0,
        "required_turn_radius_m": 0.0,
        "estimated_available_turn_radius_m": 0.0,
        "required_decel_distance_m": 0.0,
        "available_decel_distance_m": 0.0,
        "suggested_max_speed_mps": 8.0,
        "suggested_min_distance_m": 0.0,
    }


def _odometry() -> dict:
    zero = {"x": 0.0, "y": 0.0, "z": 0.0}
    return {
        "header": HEADER,
        "child_frame_id": "base_link",
        "pose": {
            "covariance": [0.0] * 36,
            "pose": {"position": zero, "orientation": {**zero, "w": 1.0}},
        },
        "twist": {
            "covariance": [0.0] * 36,
            "twist": {"linear": {**zero, "x": 5.0}, "angular": zero},
        },
    }


def _smoothed_waypoints(config: OriginalGncConfig, command_source: str, *, skip: bool | None = None) -> list[dict]:
    parameters = dict(config.parameters()["ship_guidance_node"])
    if skip is not None:
        parameters["planner_route_arc_smoothing_skip"] = {"type": 1, "value": bool(skip)}
    path = _bend_path()
    with NativeModule(config.build_directory, "ship_guidance_node", parameters) as module:
        module.invoke("odom_callback", _odometry(), STAMP)
        module.invoke("route_status_callback", _route_status(command_source), STAMP + 100_000_000)
        outputs = module.invoke("path_callback", path, STAMP + 200_000_000)["outputs"]
    published = [out for out in outputs if out.get("topic") == "/gnc/smoothed_waypoints"]
    assert published, "guidance published no smoothed waypoints"
    poses = published[-1]["message"]["fields"]["poses"]
    assert len(path["poses"]) == 45
    return [{**pose["pose"]["position"], "z_code": pose["pose"]["position"]["z"]} for pose in poses]


def _avoidance_plan(command_source: str, *, points: int = 60, boundary_m: float = 29.95) -> dict:
    """A dense stitch plan whose first boundary leg is marginally sub-floor."""
    lat0 = 58.004
    lon0 = 6.0108
    meters_per_deg_lat = 1.0 / 111320.0
    meters_per_deg_lon = 1.0 / (111320.0 * math.cos(math.radians(lat0)))
    lats = []
    lons = []
    along = 0.0
    for index in range(points):
        along += boundary_m if index == 0 else 30.0
        lats.append(lat0 + along * meters_per_deg_lat)
        lons.append(lon0)
    return {
        "header": HEADER,
        "plan_id": "mid-mpc-probe",
        "parent_route_id": "original-gnc-mission-0",
        "parent_route_revision": 1,
        "behavior_mode": "avoidance",
        "command_source": command_source,
        "latitude": lats,
        "longitude": lons,
        "command_speed_mps": [],
        "command_heading_deg": [],
        "navigation_mode": [],
        "valid_until": {"sec": 2_000_000_120, "nanosec": 0},
        "require_exact_heading": False,
        "require_exact_speed": False,
        "allow_degraded_execution": True,
        "has_return_to_route_point": False,
        "return_latitude": 0.0,
        "return_longitude": 0.0,
    }


def _submit_avoidance_plan(
    config: OriginalGncConfig,
    command_source: str,
    *,
    skip: bool | None = None,
    points: int = 60,
    boundary_m: float = 29.95,
) -> tuple[dict | None, dict]:
    parameters = dict(config.parameters()["active_route_manager_node"])
    if skip is not None:
        parameters["planner_route_min_segment_skip"] = {"type": 1, "value": bool(skip)}
    with NativeModule(config.build_directory, "active_route_manager_node", parameters) as module:
        module.invoke("nominal_route_callback", BASE_NOMINAL, STAMP)
        outputs = module.invoke(
            "avoidance_plan_callback",
            _avoidance_plan(command_source, points=points, boundary_m=boundary_m),
            STAMP + 500_000_000,
        )["outputs"]
    routes = [out for out in outputs if out.get("topic") == "/gnc/active_route"]
    statuses = [out for out in outputs if out.get("topic") == "/gnc/route_execution_status"]
    route = routes[-1]["message"]["fields"] if routes else None
    status = statuses[-1]["message"]["fields"] if statuses else {}
    return route, status


def test_planner_route_keeps_points_through_guidance_smoothing():
    """A planner-owned route must reach guidance point-for-point."""
    config = OriginalGncConfig.from_dict({})
    if not (config.build_directory / "build-manifest.json").exists():
        pytest.skip("Native build required")
    path = _bend_path()
    kept = _smoothed_waypoints(config, "mid_mpc_ipopt")
    assert len(kept) == len(path["poses"])
    for published, original in zip(kept, path["poses"], strict=True):
        assert published["x"] == pytest.approx(original["pose"]["position"]["x"], abs=1e-9)
        assert published["y"] == pytest.approx(original["pose"]["position"]["y"], abs=1e-9)


def test_operator_route_still_smoothed():
    """The same geometry from an operator route keeps the arc rewrite."""
    config = OriginalGncConfig.from_dict({})
    if not (config.build_directory / "build-manifest.json").exists():
        pytest.skip("Native build required")
    assert len(_smoothed_waypoints(config, "route_planner")) == 49


def test_guidance_rollback_switch_restores_smoothing():
    config = OriginalGncConfig.from_dict({})
    if not (config.build_directory / "build-manifest.json").exists():
        pytest.skip("Native build required")
    assert len(_smoothed_waypoints(config, "mid_mpc_ipopt", skip=False)) == 49


def test_planner_plan_with_short_stitch_segment_is_admitted_point_for_point():
    """A 29.95 m boundary leg must not reject the planner stitch plan."""
    config = OriginalGncConfig.from_dict({})
    if not (config.build_directory / "build-manifest.json").exists():
        pytest.skip("Native build required")
    route, status = _submit_avoidance_plan(config, "mid_mpc_ipopt")
    assert status["execution_state"] == "ACCEPTED"
    assert route is not None
    plan = _avoidance_plan("mid_mpc_ipopt")
    assert len(route["latitude"]) == len(plan["latitude"])
    assert route["latitude"] == pytest.approx(plan["latitude"], abs=1e-12)


def test_collision_avoidance_plan_still_rejected_on_short_segment():
    config = OriginalGncConfig.from_dict({})
    if not (config.build_directory / "build-manifest.json").exists():
        pytest.skip("Native build required")
    route, status = _submit_avoidance_plan(config, "collision_avoidance")
    assert status["execution_state"] == "REJECTED"
    assert status["reason"] == "segment_too_short"
    assert route is None


def test_admission_rollback_switch_restores_reject():
    config = OriginalGncConfig.from_dict({})
    if not (config.build_directory / "build-manifest.json").exists():
        pytest.skip("Native build required")
    route, status = _submit_avoidance_plan(config, "mid_mpc_ipopt", skip=False)
    assert status["execution_state"] == "REJECTED"
    assert status["reason"] == "segment_too_short"
    assert route is None
