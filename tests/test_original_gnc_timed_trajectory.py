"""Authoritative C++ admission and geometry preservation for timed Mid-MPC plans."""

import copy
import math

import numpy as np
import pytest
from test_original_gnc_planner_speed_gate import _odometry

from colav_simulator.core.ship import Config, build_ship
from colav_simulator.original_gnc.configuration import OriginalGncConfig
from colav_simulator.original_gnc.geometry import RouteFrame, nominal_route, stamp
from colav_simulator.original_gnc.native import NativeModule
from colav_simulator.original_gnc.stack import NativeStack


@pytest.fixture
def runtime(request):
    config = OriginalGncConfig.from_dict({})
    roots, assets, policy = config.source_assets()
    parameters = config.parameters()
    for name, value in {
        "initial_position.x": getattr(request, "param", (0.0, 0.0))[0],
        "initial_position.y": getattr(request, "param", (0.0, 0.0))[1],
        "initial_position.yaw": 0.0,
        "initial_velocity.u": 4.0,
        "initial_velocity.v": 0.0,
        "initial_velocity.r": 0.0,
    }.items():
        parameters["ship_dynamics_node"][name]["value"] = value
    with NativeStack(config.build_directory, parameters, roots, policy, asset_paths=assets) as stack:
        frame = RouteFrame(1000.0, 2000.0)
        route = nominal_route(
            frame, np.array([[1000.0, 11000.0], [2000.0, 2000.0]]), np.array([4.0, 4.0]), "mission", 1, stack.time_ns
        )
        stack.publish("/route_planning/route_plan", "ship_interfaces/msg/RoutePlan", route)
        stack.advance(11.0)
        yield stack, frame


def _plan(stack) -> dict:
    state = stack.latest["/ship/geo_position"]
    speed = state["speed_mps"]
    course = math.radians(state["course_deg"])
    times = np.arange(21) * 5.0
    north = times * speed * math.cos(course)
    east = times * speed * math.sin(course)
    frame = RouteFrame(0.0, 0.0, state["origin_lat"], state["origin_lon"])
    latitudes, longitudes = frame.geographic(np.array([state["x_ned"] + north, state["y_ned"] + east]))
    return {
        "header": {"stamp": stamp(stack.time_ns), "frame_id": "map"},
        "plan_id": "timed-mid-1",
        "parent_route_id": "mission",
        "parent_route_revision": 1,
        "behavior_mode": "planner_trajectory_v1",
        "command_source": "mid_mpc_ipopt",
        "latitude": latitudes,
        "longitude": longitudes,
        "command_speed_mps": [speed] * 21,
        "command_heading_deg": [state["course_deg"]] * 21,
        "navigation_mode": ["avoidance"] * 21,
        "valid_until": stamp(stack.time_ns + 10_000_000_000),
        "require_exact_heading": False,
        "require_exact_speed": True,
        "allow_degraded_execution": False,
        "has_return_to_route_point": False,
        "return_latitude": 0.0,
        "return_longitude": 0.0,
        "trajectory_dt_s": 5.0,
        "trajectory_reference_id": stack.latest["/gnc/active_route"]["route_id"],
    }


@pytest.mark.parametrize("runtime", [(0.0, 0.0), (5000.0, 3000.0)], indirect=True)
def test_current_state_anchored_trajectory_is_admitted_without_rewriting(runtime):
    stack, _ = runtime
    plan = _plan(stack)
    state = stack.latest["/ship/geo_position"]
    stack.publish("/colav/avoidance_plan", "ship_interfaces/msg/AvoidancePlan", plan)
    status = stack.latest["/gnc/route_execution_status"]
    assert status["accepted"], status
    assert not status["degraded"]
    route = stack.latest["/gnc/active_route"]
    assert route["latitude"] == plan["latitude"]
    assert route["longitude"] == plan["longitude"]
    assert route["speed_limit_mps"] == plan["command_speed_mps"]
    points = stack.latest["/gnc/smoothed_waypoints"]["poses"]
    assert len(points) == len(plan["latitude"])
    expected_north = state["x_ned"] + np.arange(21) * 5.0 * state["vel_north_mps"]
    expected_east = state["y_ned"] + np.arange(21) * 5.0 * state["vel_east_mps"]
    np.testing.assert_allclose([point["pose"]["position"]["x"] for point in points], expected_north, atol=1e-6)
    np.testing.assert_allclose([point["pose"]["position"]["y"] for point in points], expected_east, atol=1e-6)


@pytest.mark.parametrize(
    "defect", ["initial_position", "yaw_rate", "speed_rate", "geometry", "stale", "expired", "source", "grid"]
)
def test_native_trajectory_contract_rejects_invalid_plan(runtime, defect):
    stack, _ = runtime
    plan = _plan(stack)
    if defect == "initial_position":
        plan["latitude"][0] += 1.0 / 111320.0
    elif defect == "yaw_rate":
        plan["command_heading_deg"][1] += 12.0
    elif defect == "speed_rate":
        plan["command_speed_mps"][1] += 1.0
    elif defect == "geometry":
        plan["latitude"][2] += 1.0 / 111320.0
    elif defect == "stale":
        plan["trajectory_reference_id"] = "stale-route"
    elif defect == "expired":
        plan["valid_until"] = stamp(stack.time_ns)
    elif defect == "source":
        plan["command_source"] = "operator"
    else:
        plan["trajectory_dt_s"] = 0.0
    stack.publish("/colav/avoidance_plan", "ship_interfaces/msg/AvoidancePlan", plan)
    status = stack.latest["/gnc/route_execution_status"]
    assert status["rejected"], status
    assert stack.latest["/gnc/active_route"]["route_id"] == "mission"


def test_renewal_keeps_frozen_geometry_and_original_time_origin(runtime):
    stack, _ = runtime
    plan = _plan(stack)
    stack.publish("/colav/avoidance_plan", "ship_interfaces/msg/AvoidancePlan", plan)
    assert stack.latest["/gnc/route_execution_status"]["accepted"]
    stack.advance(1.0)
    plan["valid_until"] = stamp(stack.time_ns + 10_000_000_000)
    stack.publish("/colav/avoidance_plan", "ship_interfaces/msg/AvoidancePlan", plan)
    assert stack.latest["/gnc/route_execution_status"]["accepted"]
    changed = copy.deepcopy(plan)
    changed["command_speed_mps"][1] += 0.01
    stack.publish("/colav/avoidance_plan", "ship_interfaces/msg/AvoidancePlan", changed)
    assert stack.latest["/gnc/route_execution_status"]["reason"] == "trajectory_identity_changed"


def test_operator_route_still_obeys_first_change_lookahead(runtime):
    stack, frame = runtime
    state = stack.latest["/ship/geo_position"]
    north = 1000.0 + state["x_ned"]
    route = nominal_route(
        frame, np.array([[north, north + 5000.0], [2000.0, 2000.0]]), np.array([4.0, 4.0]), "mission", 2, stack.time_ns
    )
    stack.publish("/route_planning/route_plan", "ship_interfaces/msg/RoutePlan", route)
    status = stack.latest["/route_planning/route_plan_status"]
    assert not status["accepted"], status
    assert "first changed waypoint" in status["reason"]


def _timed_path(start, speeds, issue_ns) -> dict:
    positions = np.r_[start, start + np.cumsum(np.asarray(speeds[1:]) * 5.0)]
    return {
        "header": {"stamp": stamp(issue_ns), "frame_id": "odom"},
        "poses": [
            {
                "header": {"stamp": stamp(issue_ns + index * 5_000_000_000), "frame_id": "odom"},
                "pose": {
                    "position": {"x": float(position), "y": 0.0, "z": 10.0},
                    "orientation": {"x": 0.0, "y": 1.0, "z": float(speed), "w": 2.0},
                },
            }
            for index, (position, speed) in enumerate(zip(positions, speeds, strict=True))
        ],
    }


def _published_speed(result) -> float:
    return [
        item["message"]["fields"]["data"] for item in result["outputs"] if item.get("topic") == "/control/speed_setpoint"
    ][-1]


def test_timed_speed_profile_does_not_apply_future_braking_early():
    config = OriginalGncConfig.from_dict({})
    epoch = 2_000_000_000_000_000_000
    header = {"stamp": stamp(epoch), "frame_id": "odom"}
    speeds = np.r_[np.arange(4.0, -0.1, -0.4), np.zeros(10)]
    with NativeModule(config.build_directory, "ship_guidance_node", config.parameters()["ship_guidance_node"]) as module:
        odometry = _odometry(header, 0.0, 0.0, 0.0)
        odometry["twist"]["twist"]["linear"]["x"] = 4.0
        module.invoke("odom_callback", odometry, epoch)
        module.invoke("path_callback", _timed_path(0.0, speeds, epoch), epoch)
        first = module.invoke("control_loop", None, epoch + 500_000_000)
        assert _published_speed(first) == pytest.approx(3.6, abs=1e-6)
        stopped = module.invoke("control_loop", None, epoch + 60_000_000_000)
        assert _published_speed(stopped) == 0.0


def test_equivalent_reanchored_line_keeps_guidance_speed_recovery():
    config = OriginalGncConfig.from_dict({})
    epoch = 2_000_000_000_000_000_000
    header = {"stamp": stamp(epoch), "frame_id": "odom"}
    speeds = np.r_[np.arange(5.0, 8.0, 0.4), np.full(73, 8.0)]
    with NativeModule(config.build_directory, "ship_guidance_node", config.parameters()["ship_guidance_node"]) as module:
        module.invoke("odom_callback", _odometry(header, 300.0, 0.0, 0.0), epoch)
        module.invoke("path_callback", _timed_path(300.0, speeds, epoch), epoch)
        for second in range(1, 101):
            now = epoch + second * 1_000_000_000
            module.invoke("odom_callback", _odometry(header, 300.0 + 5.0 * second, 0.0, 0.0), now)
            before = module.invoke("control_loop", None, now)
        cap_before = before["state"]["cruise_speed_cap_mps"]
        assert cap_before > 6.5
        after = module.invoke("path_callback", _timed_path(800.0, speeds, now), now)
        assert after["state"]["cruise_speed_cap_mps"] == cap_before
        assert after["state"]["cruise_recovery_gate_cleared"] == before["state"]["cruise_recovery_gate_cleared"]


def test_timed_ground_speed_is_projected_to_body_surge():
    config = OriginalGncConfig.from_dict({})
    epoch = 2_000_000_000_000_000_000
    header = {"stamp": stamp(epoch), "frame_id": "odom"}
    ground_speed = math.hypot(4.0, 0.8)
    odometry = _odometry(header, 0.0, 0.0, -math.atan2(0.8, 4.0))
    odometry["twist"]["twist"]["linear"].update(x=4.0, y=0.8)
    with NativeModule(config.build_directory, "ship_guidance_node", config.parameters()["ship_guidance_node"]) as module:
        module.invoke("odom_callback", odometry, epoch)
        module.invoke("path_callback", _timed_path(0.0, np.full(81, ground_speed), epoch), epoch)
        result = module.invoke("control_loop", None, epoch + 500_000_000)
        assert _published_speed(result) == pytest.approx(4.0, abs=1e-6)


def test_adapter_publishes_initial_native_state_before_first_plan():
    config = Config(
        id=0,
        mmsi=123456789,
        csog_state=np.array([1000.0, 2000.0, 7.8, 0.3]),
        waypoints=np.array([[1000.0, 3500.0], [2000.0, 2000.0]]),
        speed_plan=np.array([7.8, 7.8]),
        original_gnc=OriginalGncConfig.from_dict({}),
    )
    ship = build_ship(config, dt_s=0.1)
    try:
        assert ship.stack.elapsed_s == 0.0
        state = ship.stack.latest.get("/ship/geo_position")
        assert state is not None
        assert state["origin_locked"]
        assert state["speed_mps"] == pytest.approx(7.8)
        assert state["course_deg"] == pytest.approx(math.degrees(0.3))
        assert state["x_ned"] == pytest.approx(0.0)
        assert state["y_ned"] == pytest.approx(0.0)
        assert ship.stack.states["ship_dynamics_node"]["nu"][0] == 7.8
    finally:
        ship.close()
