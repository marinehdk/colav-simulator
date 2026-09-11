"""Probe exact original route validity, speed, distance and refresh boundaries."""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Any

from geographiclib.geodesic import Geodesic
from rclpy.serialization import serialize_message
from rosidl_runtime_py.convert import message_to_ordereddict
from run_boundary_reference import EPOCH, EPS, odometry, run
from ship_interfaces.msg import AvoidancePlan, GeoPosition, RoutePlan


def route(identifier: str, revision: int, north: float, east: float = 0.0, kind: str = "nominal") -> RoutePlan:
    """Convert fixed NED geometry using the same declared WGS84 origin."""
    msg = RoutePlan()
    msg.route_id = identifier
    msg.route_revision = revision
    msg.route_type = kind
    for n, e in ((0.0, 0.0), (north, east)):
        point = Geodesic.WGS84.Direct(58.0, 6.0, math.degrees(math.atan2(e, n)), math.hypot(n, e))
        msg.latitude.append(point["lat2"])
        msg.longitude.append(point["lon2"])
    msg.speed_limit_mps = [2.0, 2.0]
    msg.navigation_mode = ["cruise", "cruise"]
    return msg


def stimuli() -> dict[str, list[dict]]:  # noqa: PLR0915
    """Freeze neighboring inputs without relaxing or inferring source acceptance."""
    coordinate = "coordinate_transform_node"
    manager = "active_route_manager_node"
    result = {coordinate: [], manager: []}

    def append(node: str, callback: str, seconds: float, message: Any = None, label: str = "") -> None:
        ns = EPOCH + round(seconds * 1e9)
        if message is not None and hasattr(message, "header"):
            message.header.stamp.sec = ns // 10**9
            message.header.stamp.nanosec = ns % 10**9
        event = {"kind": "call", "function": callback, "time_ns": ns, "coverage_label": label, "input": None}
        if message is not None:
            kind = "/".join((type(message).__module__.split(".")[0], "msg", type(message).__name__))
            event["input"] = {"type": kind, "cdr_hex": serialize_message(message).hex()}
            event["input_fields"] = message_to_ordereddict(message)
        result[node].append(event)

    nominal = route("boundary-mission", 1, 2500.0)
    append(coordinate, "nominal_route_origin_callback", 1.0, nominal, "source-origin")
    append(coordinate, "odom_callback", 1.01, odometry(0.0), "stationary-origin")
    append(coordinate, "route_callback", 1.02, nominal, "initial-nominal")
    append(coordinate, "publish_pending_initial_waypoints", 1.3, label="initial-timer-publication")
    for index, delta in enumerate((-EPS, 0.0, EPS)):
        base = 100.0 * (index + 1)
        anchor = route(f"refresh-anchor-{index}", 1, 2500.0, 50.0 + index * 10.0, "avoidance")
        candidate = route(f"refresh-candidate-{index}", 1, 2500.0, 55.0 + index * 10.0, "avoidance")
        append(coordinate, "route_callback", base, anchor, "refresh-valid-anchor")
        append(coordinate, "route_callback", base + 10.0 + delta, candidate, "10-second-guard-boundary")
        future = route(f"future-{index}", 1, 500.0 + delta, 0.0, "avoidance")
        append(coordinate, "route_callback", base + 30.0, future, "500-metre-future-boundary")
        short = route(f"segment-{index}", 1, 30.0 + delta, 0.0, "avoidance")
        append(coordinate, "route_callback", base + 50.0, short, "30-metre-segment-boundary")
    append(manager, "nominal_route_callback", 1.0, nominal, "nominal-authority")
    position = GeoPosition()
    position.latitude = 58.0
    position.longitude = 6.0
    position.origin_locked = True
    position.origin_lat = 58.0
    position.origin_lon = 6.0
    position.speed_mps = 2.0
    position.surge_mps = 2.0
    append(manager, "ship_state_callback", 1.1, position, "source-position")

    def plan(name: str, seconds: float, speed: float = 2.0, expiry_delta_ns: int = 30_000_000_000) -> AvoidancePlan:
        value = AvoidancePlan()
        geometry = route(name, 1, 2500.0, 80.0, "avoidance")
        value.plan_id = name
        value.parent_route_id = "boundary-mission"
        value.parent_route_revision = 1
        value.behavior_mode = "avoidance"
        value.command_source = "boundary_reference"
        value.latitude = geometry.latitude
        value.longitude = geometry.longitude
        value.command_speed_mps = [speed, speed]
        value.navigation_mode = ["cruise", "cruise"]
        value.require_exact_speed = True
        value.allow_degraded_execution = False
        expiry = EPOCH + round(seconds * 1e9) + expiry_delta_ns
        value.valid_until.sec = expiry // 10**9
        value.valid_until.nanosec = expiry % 10**9
        return value

    for index, delta in enumerate((-1, 0, 1)):
        t = 10.0 + index
        append(
            manager,
            "avoidance_plan_callback",
            t,
            plan(f"expiry-{delta}", t, expiry_delta_ns=delta),
            "expiry-nanosecond-boundary",
        )
        append(manager, "maintenance_callback", t + 1e-8, label="expiry-maintenance")
    for index, delta in enumerate((-EPS, 0.0, EPS)):
        t = 20.0 + index
        append(manager, "avoidance_plan_callback", t, plan(f"speed-{index}", t, speed=8.0 + delta), "8-mps-command-limit")
    for index, change in enumerate(("wrong-parent", "wrong-revision", "missing-validity", "duplicate", "return")):
        t = 30.0 + index
        value = plan("stable-id", t)
        if change == "wrong-parent":
            value.parent_route_id = "different-mission"
        if change == "wrong-revision":
            value.parent_route_revision = 2
        if change == "missing-validity":
            value.valid_until.sec = 0
            value.valid_until.nanosec = 0
        if change == "return":
            value.behavior_mode = "return_to_route"
        append(manager, "avoidance_plan_callback", t, value, change)
    # Reset the reference geometry through the source's real return-route path;
    # each candidate below still uses the ordinary avoidance guard.
    for index, delta in enumerate((-EPS, 0.0, EPS)):
        base = 400.0 + index * 100.0
        straight = route(f"straight-return-{index}", 1, 2500.0, kind="internal_return_to_route")
        append(coordinate, "route_callback", base, straight, "straight-reference-for-projection")
        candidate = route(f"future-aligned-{index}", 1, 500.0 + delta, kind="avoidance")
        append(coordinate, "route_callback", base + 20.0, candidate, "500-metre-aligned-projection-boundary")

    duplicate = plan("byte-identical-plan", 40.0)
    append(manager, "avoidance_plan_callback", 40.0, duplicate, "duplicate-first")
    append(manager, "avoidance_plan_callback", 40.0, duplicate, "duplicate-identical-retransmission")
    for index, delta in enumerate((-EPS, 0.0, EPS)):
        value = plan(f"segment-manager-{index}", 50.0 + index)
        # This is the original manager's declared local feasibility coordinate;
        # the coordinate-transform node uses a separate geodesic projection.
        value.latitude = [58.0, 58.0 + (30.0 + delta) / 111320.0]
        value.longitude = [6.0, 6.0]
        append(manager, "avoidance_plan_callback", 50.0 + index, value, "30-metre-manager-segment-boundary")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("reference", "drivers", "workspace", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--domain", type=int, required=True)
    args = parser.parse_args()
    run(
        args.reference.resolve(),
        args.drivers.resolve(),
        args.workspace.resolve(),
        args.output.resolve(),
        stimuli(),
        domain=args.domain,
    )
