"""Record source-only Python policy vectors using real ROS message classes.

This is an independent single-module reference exercise, not a native R0
closed-loop trace. Time injection is explicit and the production extractor is
never imported or used by this reference process.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

import rclpy
import yaml
from rclpy.clock import Clock
from rclpy.time import Time
from rosidl_runtime_py.convert import message_to_ordereddict
from rosidl_runtime_py.set_message import set_message_fields
from rosidl_runtime_py.utilities import get_message

SOURCE = "src/mission/mission_supervisor/mission_supervisor/propulsion_policy_node.py"
CONFIG = "src/mission/mission_supervisor/config/propulsion_policy.yaml"


class ReferenceClock(Clock):
    """Explicit reference test time, recorded at every source read."""

    def now(self) -> Any:
        self.reads.append(self.current_ns)
        return Time(nanoseconds=self.current_ns, clock_type=self.clock_type)


class PublicationRecorder:
    """Observe every original publication while forwarding the real message."""

    def __init__(self, publisher: Any, topic: str, message_type: Any, outputs: Any):
        self.publisher, self.topic, self.message_type, self.outputs = publisher, topic, message_type, outputs

    def publish(self, msg: Any):
        self.outputs.append({"topic": self.topic, "type": self.message_type, "fields": message_to_ordereddict(msg)})
        self.publisher.publish(msg)


def run(source: Path, output: Path) -> dict:
    """Exercise speed hysteresis, stale inputs, fault and DP reverse branches."""
    path = source / SOURCE
    spec = importlib.util.spec_from_file_location("independent_original_propulsion_policy", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    config_path = source / CONFIG
    rclpy.init(args=["--ros-args", "-p", f"config_file:={config_path}"])
    node = module.PropulsionPolicyNode()
    clock = ReferenceClock(clock_type=node.start_time.clock_type)
    epoch = node.start_time.nanoseconds
    clock.current_ns, clock.reads = epoch, []
    node.get_clock = lambda: clock
    emitted = []
    node.policy_pub = PublicationRecorder(node.policy_pub, "/propulsion/policy", "std_msgs/msg/String", emitted)
    node.constraints_pub = PublicationRecorder(
        node.constraints_pub, "/propulsion/constraints", "std_msgs/msg/Float64MultiArray", emitted
    )
    cases = []
    for speed in [0.0, 1.499, 1.5, 1.501, 2.699, 2.7, 2.701, 3.199, 3.2, 3.201, 5.0, 2.8, 2.7, 2.6, 0.0]:
        cases.extend(
            [
                ("_on_mission_status", "std_msgs/msg/String", {"data": json.dumps({"phase": "CRUISE"})}, 0.02),
                ("_on_captain_decision", "std_msgs/msg/String", {"data": json.dumps({"action": "continue"})}, 0.02),
                ("_on_odometry", "nav_msgs/msg/Odometry", {"twist": {"twist": {"linear": {"x": speed, "y": 0.0}}}}, 0.5),
                (
                    "_on_cmd_tau",
                    "geometry_msgs/msg/WrenchStamped",
                    {"wrench": {"force": {"x": -2000.0}, "torque": {"z": 0.0}}},
                    0.02,
                ),
                ("_on_actuator_capability", "std_msgs/msg/Float64MultiArray", {"data": [3.0, 3.0, 0.0]}, 0.02),
                ("_on_dp_hold_active", "std_msgs/msg/Bool", {"data": speed < 1.0}, 0.02),
                ("_tick", None, None, 0.02),
            ]
        )
    cases.extend(
        [
            ("_tick", None, None, 6.0),
            ("_on_actuator_capability", "std_msgs/msg/Float64MultiArray", {"data": [2.0, 3.0, 1.0]}, 0.02),
            ("_on_environment_load", "geometry_msgs/msg/WrenchStamped", {"wrench": {"force": {"x": 1e6, "y": 2e5}}}, 0.02),
            (
                "_on_captain_decision",
                "std_msgs/msg/String",
                {"data": json.dumps({"action": "abort_escape_recommended"})},
                0.02,
            ),
            ("_tick", None, None, 0.02),
        ]
    )
    calls = []
    for callback, message_type, fields, elapsed in cases:
        clock.current_ns += round(elapsed * 1e9)
        clock.reads.clear()
        emitted.clear()
        message = None
        if message_type:
            message = get_message(message_type)()
            set_message_fields(message, fields)
            getattr(node, callback)(message)
        else:
            getattr(node, callback)()
        calls.append(
            {
                "callback": callback,
                "time_ns": clock.current_ns,
                "input": message_to_ordereddict(message) if message is not None else None,
                "clock_reads": list(clock.reads),
                "outputs": list(emitted),
                "state": {
                    "speed_mps": node.speed_mps,
                    "raw_speed_mps": node.raw_speed_mps,
                    "side_thruster_speed_allowed": node.side_thruster_speed_allowed_state,
                },
            }
        )
    result = {
        "schema": "original-gnc.policy-reference.v1",
        "scope": "independent source single-module vectors",
        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
        "config": yaml.safe_load(config_path.read_text()),
        "config_file": str(config_path),
        "scenario_file": "",
        "scenario": {},
        "shadow_mode": True,
        "publish_rate_hz": 2.0,
        "initial_clock_ns": epoch,
        "calls": calls,
    }
    node.destroy_node()
    rclpy.shutdown()
    if output.exists():
        raise FileExistsError(output)
    output.write_text(json.dumps(result, indent=2, allow_nan=False))
    return {
        "calls": len(calls),
        "publications": sum(len(c["outputs"]) for c in calls),
        "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.source, args.output), indent=2))
