"""Generate frozen finite boundary stimuli and run independent original C++ modules."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import time
from pathlib import Path
from typing import Any

import rclpy
import yaml
from geometry_msgs.msg import PoseStamped, WrenchStamped
from nav_msgs.msg import Odometry
from nav_msgs.msg import Path as RosPath
from rclpy.serialization import serialize_message
from replay_native_trace import VALUE_KEYS
from rosidl_runtime_py.convert import message_to_ordereddict
from std_msgs.msg import Float64, Float64MultiArray, Int32

EPOCH = 2_000_000_000_000_000_000
EPS = 1e-6
NODES = ("ship_dynamics_node", "ship_control_node", "ship_guidance_node", "thrust_allocation_node")


def odometry(speed: float, heading: float = 0.0, sway: float = 0.0, yaw_rate: float = 0.0) -> Odometry:
    """Use NED/body-frame values, preserving the source quaternion contract."""
    msg = Odometry()
    msg.pose.pose.orientation.z = math.sin(heading / 2)
    msg.pose.pose.orientation.w = math.cos(heading / 2)
    msg.twist.twist.linear.x = speed
    msg.twist.twist.linear.y = sway
    msg.twist.twist.angular.z = yaw_rate
    return msg


def wrench(x: float = 0.0, y: float = 0.0, n: float = 0.0) -> WrenchStamped:
    """Construct applied force in N and yaw moment in N m."""
    msg = WrenchStamped()
    msg.wrench.force.x = x
    msg.wrench.force.y = y
    msg.wrench.torque.z = n
    return msg


# Keep predeclared source threshold sequences contiguous for review.
def stimuli() -> dict[str, list[dict]]:  # noqa: C901, PLR0912, PLR0915
    """Predeclare threshold triples, angle wrap, saturation and failure/recovery inputs."""
    result = {node: [] for node in NODES}
    clock = dict.fromkeys(NODES, EPOCH)

    def append(node: str, callback: str, message: Any = None, label: str = "") -> None:
        clock[node] += 20_000_000
        if message is not None and hasattr(message, "header"):
            message.header.stamp.sec = clock[node] // 10**9
            message.header.stamp.nanosec = clock[node] % 10**9
        record = {"kind": "call", "function": callback, "time_ns": clock[node], "coverage_label": label, "input": None}
        if message is not None:
            kind = "/".join((type(message).__module__.split(".")[0], "msg", type(message).__name__))
            record["input"] = {"type": kind, "cdr_hex": serialize_message(message).hex()}
            record["input_fields"] = message_to_ordereddict(message)
        result[node].append(record)

    plant = "ship_dynamics_node"
    append(plant, "initial_route_yaw_callback", Float64(data=math.pi - EPS), "angle-wrap-initial")
    for depth in (0.1 - EPS, 0.1, 0.1 + EPS, 2.2 - EPS, 2.2, 2.2 + EPS, 4.4, 1000.0):
        append(plant, "water_depth_callback", Float64(data=depth), f"water-depth-{depth}")
        append(plant, "update_dynamics", label="depth-update")
    for direction in (-1.0, 1.0):
        for angle in (0.6109 - EPS, 0.6109, 0.6109 + EPS, math.pi - EPS, math.pi, math.pi + EPS):
            command = [
                direction * 135000.0,
                0.0,
                0.0,
                0.0,
                direction * 135000.0,
                0.0,
                20000.0,
                1.5708,
                20000.0,
                1.5708,
                0.0,
                direction * angle,
                0.0,
                direction * angle,
            ]
            append(plant, "thruster_cmd_callback", Float64MultiArray(data=command), "thrust-rudder-boundary")
            append(
                plant,
                "env_force_callback",
                wrench(direction * 50000.0, direction * 20000.0, direction * 100000.0),
                "signed-environment-load",
            )
            for _ in range(5):
                append(plant, "update_dynamics", label="actuator-response")
    for fault in (0, 1, 2, 3, 4, 5, 6, -1, -2, -3, -4, -5, -6, 7, -7):
        append(plant, "inject_fault_callback", Int32(data=fault), f"fault-{fault}")
        append(plant, "update_dynamics", label="fault-observation")
    speeds = [-2.0, 0.0, 0.3] + [threshold + delta for threshold in (1.5, 2.7, 3.2) for delta in (-EPS, 0.0, EPS)] + [7.8]
    headings = [-math.pi - EPS, -math.pi, -math.pi + EPS, 0.0, math.pi - EPS, math.pi, math.pi + EPS]
    controller = "ship_control_node"
    for speed in speeds:
        for heading in headings:
            append(controller, "odom_callback", odometry(speed, heading, 0.2, -0.01), "signed-velocity-angle-wrap")
            append(controller, "heading_callback", Float64(data=-heading), "opposed-heading-reference")
            append(controller, "target_speed_callback", Float64(data=7.8 if speed < 3.2 else 0.0), "speed-step")
            target = PoseStamped()
            target.pose.position.x = 100.0
            target.pose.position.y = -15.0
            target.pose.orientation.w = 1.0
            append(controller, "target_callback", target, "position-error")
            append(controller, "current_load_callback", wrench(10000.0, -10000.0, 50000.0), "current-compensation")
            for _ in range(5):
                append(controller, "control_loop", label="saturation-entry-and-memory")
    allocator = "thrust_allocation_node"
    append(allocator, "on_health_update", Float64MultiArray(data=[1.0] * 7), "all-healthy")
    for speed in speeds + list(reversed(speeds)):
        append(allocator, "on_odom_callback", odometry(speed), "speed-gate-hysteresis")
        for x, y, n in ((0.0, 0.0, 0.0), (270000.0, 40000.0, 500000.0), (-100000.0, -40000.0, -500000.0), (1e6, 1e6, 1e8)):
            append(allocator, "on_tau_callback", wrench(x, y, n), "zero-reachable-unreachable-load")
    for health in (0.5 - EPS, 0.5, 0.5 + EPS, 0.0, 1.0):
        for index in range(7):
            values = [1.0] * 7
            values[index] = health
            append(allocator, "on_health_update", Float64MultiArray(data=values), "health-0.5-boundary")
            append(allocator, "on_tau_callback", wrench(100000.0, 20000.0, 100000.0), "degraded-allocation")
    guidance = "ship_guidance_node"
    # A live path is separately covered by full recorded route vectors. These
    # one cold-start callback tests no-path protection before a normal source path.
    path = RosPath()
    path.header.frame_id = "odom"
    for index, (north, east) in enumerate(((0.0, 0.0), (1000.0, 0.0), (1000.0, 1000.0))):
        pose = PoseStamped()
        pose.pose.position.x = north
        pose.pose.position.y = east
        pose.pose.position.z = 5.0 if index == 2 else 1.0
        pose.pose.orientation.y = 1.0
        pose.pose.orientation.z = 7.8
        pose.pose.orientation.w = 1.0
        path.poses.append(pose)
    append(guidance, "control_loop", label="initial-no-path-guard")
    append(guidance, "path_callback", path, "original-encoded-route")
    for speed in speeds:
        for heading in headings:
            append(guidance, "odom_callback", odometry(speed, heading, 0.2, 0.01), "cold-start-velocity-wrap")
            append(guidance, "current_load_callback", wrench(1000.0, -2000.0, 3000.0), "current-input")
            append(guidance, "env_load_callback", wrench(-1000.0, 2000.0, -3000.0), "environment-input")
            append(guidance, "control_loop", label="guidance-error-response")
    return result


def run(
    reference: Path,
    drivers: Path,
    workspace: Path,
    output: Path,
    module_stimuli: dict | None = None,
    *,
    domain: int,
) -> None:
    """Record expected values from the independent original source, never local kernels."""
    if output.exists():
        raise FileExistsError(output)
    os.environ.update(ROS_DOMAIN_ID=str(domain), ROS_LOCALHOST_ONLY="1")
    rclpy.init()
    probe = rclpy.create_node("original_boundary_isolation_probe")
    try:
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            rclpy.spin_once(probe, timeout_sec=0.1)
        unexpected = [name for name in probe.get_node_names() if name != probe.get_name()]
        if unexpected:
            raise RuntimeError(f"Boundary DDS domain is occupied: {unexpected}")
    finally:
        probe.destroy_node()
        rclpy.shutdown()
    output.mkdir(parents=True)
    parameters = json.loads((reference / "effective-parameters.json").read_text())
    manifest = json.loads((reference / "manifest.json").read_text())
    manifest["source_staging"]["workspace"] = str(workspace)
    manifest["scope"] = "original-source isolated-module boundary stimuli; not ROS closed-loop campaign"
    manifest["domain"] = domain
    manifest["reference_parameters_from"] = str(reference)
    manifest["case_id"] = output.name
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2))
    generated = stimuli() if module_stimuli is None else module_stimuli
    identities = {}
    for name, events in generated.items():
        target = output / f"{name}-stimuli.jsonl"
        target.write_text("".join(json.dumps(e, separators=(",", ":")) + "\n" for e in events))
        identities[name] = {"calls": len(events), "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}
        original = parameters["/" + name]
        values = {key: value[VALUE_KEYS[value["type"]]] for key, value in original.items() if value["type"] != 0}
        for key in ("log_dir", "feedback_log_dir"):
            if key in values:
                values[key] = str(output / f"{name}-logs")
                original[key][VALUE_KEYS[original[key]["type"]]] = values[key]
        config = output / f"{name}-parameters.yaml"
        config.write_text(yaml.safe_dump({name: {"ros__parameters": {k: v for k, v in values.items() if v != []}}}))
        Path(str(config) + ".typed.json").write_text(
            json.dumps({k: {"type": original[k]["type"], "value": v} for k, v in values.items()})
        )
        env = {
            **os.environ,
            "ROS_DOMAIN_ID": str(domain),
            "ROS_LOCALHOST_ONLY": "1",
            "ROS_LOG_DIR": str(output / "ros-log"),
            "ORIGINAL_GNC_STIMULI": str(target),
            "ORIGINAL_GNC_TRACE_DIR": str(output / "callback-traces"),
            "ORIGINAL_GNC_STATE_FILE": str(output / f"{name}-states.jsonl"),
        }
        env.pop("ORIGINAL_GNC_REPLAY_FILE", None)
        with (output / f"{name}.log").open("w") as log:
            subprocess.run(
                [str(drivers / f"{name}_replay"), name, str(config)],
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                check=True,
                timeout=180,
            )
    (output / "effective-parameters.json").write_text(json.dumps(parameters, indent=2))
    (output / "stimulus-manifest.json").write_text(
        json.dumps({"epsilon": EPS, "epoch_ns": EPOCH, "modules": identities}, indent=2)
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("reference", "drivers", "workspace", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--domain", type=int, required=True)
    args = parser.parse_args()
    run(
        args.reference.resolve(), args.drivers.resolve(), args.workspace.resolve(), args.output.resolve(), domain=args.domain
    )
