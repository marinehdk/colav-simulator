"""Run and observe the frozen original ROS graph in a dedicated DDS domain.

This reference-only tool runs on A4000, never inside the local embedded GNC.
Records are external topic observations, not purported internal callback traces.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Any

import rclpy
import yaml
from diagnostic_msgs.msg import DiagnosticArray
from geographiclib.geodesic import Geodesic
from geometry_msgs.msg import PoseStamped, WrenchStamped
from nav_msgs.msg import Odometry
from nav_msgs.msg import Path as RoutePath
from rcl_interfaces.srv import GetParameters, ListParameters
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from rosidl_runtime_py.convert import message_to_ordereddict
from ship_interfaces.msg import GeoPosition, RouteExecutionStatus, RoutePlan, RoutePlanStatus
from std_msgs.msg import Bool, Float64, Float64MultiArray, String

TOPICS = {
    "/ship/odometry": Odometry,
    "/ship/geo_position": GeoPosition,
    "/cmd_tau": WrenchStamped,
    "/allocation/achieved_tau": WrenchStamped,
    "/allocation/residual_tau": WrenchStamped,
    "/allocation/status": DiagnosticArray,
    "/thruster/commands": Float64MultiArray,
    "/thruster/health_status": Float64MultiArray,
    "/propulsion/constraints": Float64MultiArray,
    "/propulsion/policy": String,
    "/control/speed_setpoint": Float64,
    "/control/heading_setpoint": Float64,
    "/target_pose": PoseStamped,
    "/guidance/dp_hold_active": Bool,
    "/gnc/route_execution_status": RouteExecutionStatus,
    "/route_planning/route_plan_status": RoutePlanStatus,
    "/gnc/active_route": RoutePlan,
    "/gnc/internal_waypoints": RoutePath,
    "/gnc/smoothed_waypoints": RoutePath,
    "/env/total_load": WrenchStamped,
    "/env/wind_load": WrenchStamped,
    "/env/current_load": WrenchStamped,
    "/env/wave_load": WrenchStamped,
}


class Recorder(Node):
    def __init__(self, case: dict, directory: Path):
        super().__init__("original_gnc_reference_recorder")
        self.counts = collections.Counter()
        self.last = {}
        self.parameters = {}
        self.parameter_requests = {}
        self.parameter_clients = []
        self.graph_nodes_seen = set()
        self.started_ns = time.monotonic_ns()
        self.stream = (directory / "topic-observations.jsonl").open("w", buffering=1024 * 1024)
        self.subscriptions_kept = []
        for topic, message_type in TOPICS.items():
            qos = QoSProfile(depth=200, reliability=ReliabilityPolicy.RELIABLE)
            if topic in {
                "/gnc/active_route",
                "/gnc/internal_waypoints",
                "/gnc/smoothed_waypoints",
                "/guidance/dp_hold_active",
            }:
                qos.durability = DurabilityPolicy.TRANSIENT_LOCAL
            self.subscriptions_kept.append(
                self.create_subscription(message_type, topic, lambda msg, name=topic: self.record(name, msg), qos)
            )
        route_qos = QoSProfile(depth=10, durability=DurabilityPolicy.TRANSIENT_LOCAL, reliability=ReliabilityPolicy.RELIABLE)
        self.route_pub = self.create_publisher(RoutePlan, "/route_planning/route_plan", route_qos)
        route = RoutePlan()
        route.header.stamp = self.get_clock().now().to_msg()
        route.route_id = f"original-{case['case_id']}"
        route.route_revision = 1
        route.route_type = "nominal"
        origin = case["origin_wgs84"]
        for point in case["waypoints"]:
            n, e = point["north_m"], point["east_m"]
            geo = Geodesic.WGS84.Direct(
                origin["latitude_deg"], origin["longitude_deg"], math.degrees(math.atan2(e, n)), math.hypot(n, e)
            )
            route.latitude.append(geo["lat2"])
            route.longitude.append(geo["lon2"])
        route.speed_limit_mps = case["speed_limit_mps"]
        route.navigation_mode = case["navigation_mode"]
        (directory / "published-route.json").write_text(json.dumps(message_to_ordereddict(route), indent=2))
        self.route_pub.publish(route)

    def poll_parameters(self):
        """Capture final native parameter values without blocking the recorder."""
        for name, namespace in self.get_node_names_and_namespaces():
            full = f"{namespace.rstrip('/')}/{name}"
            self.graph_nodes_seen.add(full)
            if name == self.get_name() or full in self.parameter_requests or full in self.parameters:
                continue
            client = self.create_client(ListParameters, full + "/list_parameters")
            self.parameter_clients.append(client)
            if client.service_is_ready():
                request = ListParameters.Request()
                self.parameter_requests[full] = ("list", client.call_async(request), None)
        for name, (stage, future, requested_names) in list(self.parameter_requests.items()):
            if not future.done():
                continue
            result = future.result()
            if stage == "list":
                names = result.result.names
                client = self.create_client(GetParameters, name + "/get_parameters")
                self.parameter_clients.append(client)
                request = GetParameters.Request(names=names)
                self.parameter_requests[name] = ("get", client.call_async(request), names)
            else:
                self.parameters[name] = {
                    key: message_to_ordereddict(value) for key, value in zip(requested_names, result.values, strict=True)
                }
                del self.parameter_requests[name]

    def record(self, topic: str, msg: Any):
        self.counts[topic] += 1
        data = message_to_ordereddict(msg)
        self.last[topic] = data
        self.stream.write(
            json.dumps(
                {
                    "record_kind": "external_topic_observation",
                    "topic": topic,
                    "sequence": self.counts[topic],
                    "receipt_monotonic_ns": time.monotonic_ns(),
                    "receipt_ros_time_ns": self.get_clock().now().nanoseconds,
                    "message": data,
                },
                separators=(",", ":"),
            )
            + "\n"
        )


def run(  # noqa: C901, PLR0912, PLR0915
    case_path: Path, workspace: Path, output: Path, duration: float | None, domain: int
) -> dict:
    """Launch only the isolated graph, then terminate its owned process group."""
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite reference evidence: {output}")
    if int(os.environ.get("ROS_DOMAIN_ID", "-1")) != domain or os.environ.get("ROS_LOCALHOST_ONLY") != "1":
        raise RuntimeError("The reference requires an explicit isolated domain and ROS_LOCALHOST_ONLY=1")
    case = json.loads(case_path.read_text())
    output.mkdir(parents=True)
    (output / "case.json").write_bytes(case_path.read_bytes())
    original_config = workspace / "src/platform/ship_bringup/config/generated/ship_config_runtime.yaml"
    config = yaml.safe_load(original_config.read_text())
    initial = case["initial"]
    plant = config["ship_dynamics_node"]["ros__parameters"]
    plant["initial_position"] = {"x": initial["north_m"], "y": initial["east_m"], "yaw": initial["heading_rad"]}
    plant["initial_velocity"] = {"u": initial["surge_mps"], "v": initial["sway_mps"], "r": initial["yaw_rate_radps"]}
    plant["log_dir"] = str(output / "plant-csv")
    plant["water_depth"] = case["water_depth_m"]
    config["coordinate_transform_node"]["ros__parameters"]["feedback_log_dir"] = str(output / "feedback-csv")
    runtime = output / "case-runtime.yaml"
    runtime.write_text(yaml.safe_dump(config, sort_keys=False))
    rclpy.init()
    recorder = Recorder(case, output)
    # Discovery and recorder are established before the native graph starts.
    for _ in range(10):
        rclpy.spin_once(recorder, timeout_sec=0.05)
    unexpected = [
        n for n, ns in recorder.get_node_names_and_namespaces() if n != recorder.get_name() and not n.startswith("_ros2cli")
    ]
    if unexpected:
        recorder.stream.close()
        recorder.destroy_node()
        rclpy.shutdown()
        raise RuntimeError(f"DDS domain is not empty: {unexpected}")
    command = [
        "ros2",
        "launch",
        "ship_bringup",
        "system.launch.py",
        "runtime:=normal",
        f"core_config_file:={runtime}",
        "use_sim_time:=false",
        f"auto_initial_yaw_from_route:={str(case['auto_initial_yaw_from_route']).lower()}",
    ]
    command.extend(
        f"{key}:={str(value).lower() if isinstance(value, bool) else value}"
        for key, value in case["original_launch_environment"].items()
    )
    meta = {
        "schema": "original-gnc.native-run.v1",
        "case_id": case["case_id"],
        "command": command,
        "domain": domain,
        "observation_kind": "external_topics_only",
        "source_staging": json.loads((workspace / "source-staging.json").read_text()),
        "case_sha256": hashlib.sha256(case_path.read_bytes()).hexdigest(),
        "runtime_yaml_sha256": hashlib.sha256(runtime.read_bytes()).hexdigest(),
        "initialization_overrides": initial,
        "duration_override_s": duration,
        "full_case_run": duration is None,
        "executable_sha256": {
            str(path.relative_to(workspace)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (workspace / "install").glob("*/lib/*/*")
            if path.is_file() and os.access(path, os.X_OK)
        },
    }
    instrumentation = workspace / "instrumentation.json"
    if instrumentation.is_file():
        meta["reference_instrumentation"] = {
            "path": str(instrumentation),
            "sha256": hashlib.sha256(instrumentation.read_bytes()).hexdigest(),
            "trace_header_sha256": hashlib.sha256((workspace / "original_reference_trace.hpp").read_bytes()).hexdigest(),
        }
        meta["observation_kind"] = "external_topics_and_internal_callbacks"
    (output / "manifest.json").write_text(json.dumps(meta, indent=2))
    env = {**os.environ, "ROS_LOG_DIR": str(output / "ros-log")}
    if instrumentation.is_file():
        env["ORIGINAL_GNC_TRACE_DIR"] = str(output / "callback-traces")
    started = time.monotonic()
    child = None
    failure = None
    stopped_on = "duration"
    last_parameter_poll = 0.0
    try:
        with (output / "launch.log").open("w") as log:
            child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, env=env, start_new_session=True)
            (output / "process.json").write_text(json.dumps({"pid": child.pid, "process_group": child.pid}))
            while time.monotonic() - started < (case["max_duration_s"] if duration is None else duration):
                rclpy.spin_once(recorder, timeout_sec=0.02)
                elapsed = time.monotonic() - started
                if elapsed > 2.0 and elapsed - last_parameter_poll >= 0.5:
                    recorder.poll_parameters()
                    last_parameter_poll = elapsed
                if child.poll() is not None:
                    raise RuntimeError(f"Original launch exited early: {child.returncode}")
                through = case["observation"]["through_distance_m"]
                odometry = recorder.last.get("/ship/odometry")
                if duration is None and through is not None and odometry is not None:
                    if odometry["pose"]["pose"]["position"]["x"] >= through:
                        stopped_on = "through_distance"
                        break
    except Exception as error:
        failure = str(error)
    finally:
        if child is not None and child.poll() is None:
            os.killpg(child.pid, signal.SIGINT)
            try:
                child.wait(timeout=20)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGTERM)
                child.wait(timeout=10)
        recorder.stream.close()
        result = {
            "elapsed_wall_s": time.monotonic() - started,
            "message_counts": dict(recorder.counts),
            "last_messages": recorder.last,
            "failure": failure,
            "full_case_run": duration is None,
            "internal_callback_parity_verified": False,
            "stopped_on": stopped_on,
            "nodes_seen": sorted(recorder.graph_nodes_seen),
        }
        (output / "effective-parameters.json").write_text(json.dumps(recorder.parameters, indent=2))
        (output / "summary.json").write_text(json.dumps(result, indent=2))
        recorder.destroy_node()
        rclpy.shutdown()
    if failure:
        raise RuntimeError(failure)
    required = {
        "/ship/odometry",
        "/control/speed_setpoint",
        "/control/heading_setpoint",
        "/cmd_tau",
        "/thruster/commands",
        "/gnc/active_route",
    }
    if not required.issubset(result["message_counts"]):
        raise RuntimeError(f"Missing execution evidence: {sorted(required - set(result['message_counts']))}")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--duration", type=float)
    parser.add_argument("--domain", type=int, required=True)
    args = parser.parse_args()
    summary = run(args.case, args.workspace, args.output, args.duration, args.domain)
    print(json.dumps({key: value for key, value in summary.items() if key != "last_messages"}))
