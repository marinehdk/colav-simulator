"""Planner-owned avoidance routes keep their admitted speeds as speed authority.

The operator-leg external turn speed preview re-derives a slower envelope from
cumulative segment-delta angles. On a dense trajectory-style Mid-MPC route it
must not override the per-waypoint speeds that route admission already made
dynamically feasible; operator legs keep the legacy preview.
"""

import pytest

from colav_simulator.original_gnc.configuration import OriginalGncConfig
from colav_simulator.original_gnc.native import NativeModule

STAMP = 2_000_000_000_000_000_000


def _woven_path(header: dict) -> dict:
    """A dense avoidance-style route: straight, one distant bend, long straight."""
    poses = []
    x = 0.0
    y = 0.0
    heading = 0.0
    for _ in range(28):  # 0..675 m straight; bend starts 400 m past the ship
        poses.append(_pose(header, x, y))
        x += 25.0
    for _ in range(10):  # 30 deg cumulative bend, 3 deg per 25 m point
        heading += 0.05235987755982988
        x += 25.0 * __import__("math").cos(heading)
        y += 25.0 * __import__("math").sin(heading)
        poses.append(_pose(header, x, y))
    for _ in range(80):  # long outgoing straight
        poses.append(_pose(header, x, y))
        x += 25.0 * __import__("math").cos(heading)
        y += 25.0 * __import__("math").sin(heading)
    return {"header": header, "poses": poses}


def _pose(header: dict, x: float, y: float) -> dict:
    return {
        "header": header,
        "pose": {
            "position": {"x": x, "y": y, "z": 10.0},
            "orientation": {"x": 0.0, "y": 1.0, "z": 8.0, "w": 1.0},
        },
    }


def _odometry(header: dict, x: float = 300.0) -> dict:
    zero = {"x": 0.0, "y": 0.0, "z": 0.0}
    return {
        "header": header,
        "child_frame_id": "base_link",
        "pose": {"covariance": [0.0] * 36, "pose": {"position": {**zero, "x": x}, "orientation": {**zero, "w": 1.0}}},
        "twist": {"covariance": [0.0] * 36, "twist": {"linear": {**zero, "x": 5.0}, "angular": zero}},
    }


def _route_status(header: dict, command_source: str) -> dict:
    return {
        "header": header,
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


def _speed_setpoint(config: OriginalGncConfig, command_source: str, skip_planner_routes: bool = True) -> float:
    parameters = dict(config.parameters()["ship_guidance_node"])
    parameters["external_route_turn_skip_planner_routes"] = {"type": 1, "value": bool(skip_planner_routes)}
    header = {"frame_id": "odom", "stamp": {"sec": 2_000_000_000, "nanosec": 0}}
    with NativeModule(config.build_directory, "ship_guidance_node", parameters) as module:
        module.invoke("odom_callback", _odometry(header), STAMP)
        module.invoke("path_callback", _woven_path(header), STAMP)
        if command_source is not None:
            module.invoke("route_status_callback", _route_status(header, command_source), STAMP)
        module.invoke("control_loop", None, STAMP + 500_000_000)
        outputs = module.invoke("control_loop", None, STAMP + 1_000_000_000)["outputs"]
    speeds = [out["message"]["fields"]["data"] for out in outputs if out.get("topic") == "/control/speed_setpoint"]
    assert speeds, "guidance published no speed setpoint"
    return float(speeds[-1])


def test_planner_route_keeps_admitted_speeds_over_external_preview():
    config = OriginalGncConfig.from_dict({})
    if not (config.build_directory / "build-manifest.json").exists():
        pytest.skip("Native build required")
    # Cruise recovery starts at the 6.0 m/s base cap; the external preview
    # would cap this geometry near 4.78 m/s instead.
    assert _speed_setpoint(config, "mid_mpc_ipopt") == pytest.approx(6.0, abs=0.3)


def test_operator_route_keeps_legacy_external_preview():
    config = OriginalGncConfig.from_dict({})
    if not (config.build_directory / "build-manifest.json").exists():
        pytest.skip("Native build required")
    assert _speed_setpoint(config, "route_planner") < 4.9


def test_planner_gate_rollback_switch_restores_legacy_preview():
    config = OriginalGncConfig.from_dict({})
    if not (config.build_directory / "build-manifest.json").exists():
        pytest.skip("Native build required")
    assert _speed_setpoint(config, "mid_mpc_ipopt", skip_planner_routes=False) < 4.9


def test_absent_status_keeps_legacy_preview():
    config = OriginalGncConfig.from_dict({})
    if not (config.build_directory / "build-manifest.json").exists():
        pytest.skip("Native build required")
    assert _speed_setpoint(config, None) < 4.9
