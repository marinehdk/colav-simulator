"""Independent original-source observer vectors with explicit test clocks."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import inspect
import json
import sys
from pathlib import Path
from types import MethodType, SimpleNamespace
from typing import Any
from unittest.mock import patch

import rclpy
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from geometry_msgs.msg import WrenchStamped
from nav_msgs.msg import Odometry
from rclpy.clock import Clock, ClockType
from rclpy.context import Context
from rclpy.parameter import Parameter
from rclpy.time import Time
from rosidl_runtime_py.convert import message_to_ordereddict
from ship_interfaces.msg import GeoPosition
from std_msgs.msg import Float64, Float64MultiArray

MODULES = {
    "navigation_mode_observer_node": (
        "src/mission/mission_supervisor/mission_supervisor/navigation_mode_observer_node.py",
        "NavigationModeObserverNode",
        "src/mission/mission_supervisor/config/navigation_mode_policy.yaml",
    ),
    "operational_risk_observer_node": (
        "src/safety/safety_supervisor/safety_supervisor/operational_risk_observer_node.py",
        "OperationalRiskObserverNode",
        "src/safety/safety_supervisor/config/operational_risk_policy.yaml",
    ),
    "operator_command_interpreter": (
        "src/platform/ship_utils/ship_utils/operator_command_interpreter.py",
        "OperatorCommandInterpreter",
        None,
    ),
}


class TestClock(Clock):
    def now(self) -> Any:
        if inspect.currentframe().f_back.f_code.co_filename == self.reference_file:
            self.reads.append(self.current_ns)
        return Time(nanoseconds=self.current_ns, clock_type=ClockType.ROS_TIME)


class Recorder:
    def __init__(self, publisher: Any, topic: str, kind: str, outputs: Any):
        self.publisher, self.topic, self.kind, self.outputs = publisher, topic, kind, outputs

    def publish(self, value: Any):
        self.outputs.append((self.topic, self.kind, value))
        self.publisher.publish(value)


# Keep source contract branches together for audit against the frozen implementation.
def run(source: Path, output: Path) -> Any:  # noqa: C901, PLR0912, PLR0915
    """Record real original observer outputs under explicit reference clocks."""
    if output.exists():
        raise FileExistsError(output)
    epoch = 2_000_000_000_000_000_000
    clocks = {}
    nodes = {}
    vectors = {}
    registrations = {}
    published = {}
    periods = {}
    contexts = []
    for name, (relative, klass, configuration) in MODULES.items():
        path = source / relative
        spec = importlib.util.spec_from_file_location("reference_" + name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        helper_sources = {}
        for class_name, relative_helper in {
            "NavigationModeStateMachine": (
                "src/mission/mission_supervisor/mission_supervisor/navigation_mode_state_machine.py"
            ),
            "OperationalRiskEvaluator": "src/safety/safety_supervisor/safety_supervisor/operational_risk_policy.py",
        }.items():
            helper = getattr(module, class_name, None)
            if helper is not None:
                actual = Path(sys.modules[helper.__module__].__file__)
                digest = hashlib.sha256(actual.read_bytes()).hexdigest()
                if digest != hashlib.sha256((source / relative_helper).read_bytes()).hexdigest():
                    raise ValueError(f"Original observer helper differs: {actual}")
                helper_sources[relative_helper] = digest
        clock = Clock(clock_type=ClockType.ROS_TIME)
        clock.now = MethodType(TestClock.now, clock)
        clock.current_ns = epoch
        clock.reads = []
        clock.steady_reads = []
        clock.reference_file = str(path)
        clocks[name] = clock
        registrations[name] = []
        published[name] = []
        periods[name] = []

        def steady(c: Any = clock) -> Any:
            value = 1_000_000.0 + (c.current_ns - epoch) / 1_000_000_000
            c.steady_reads.append(value)
            return value

        if hasattr(module, "time"):
            module.time = SimpleNamespace(monotonic=steady)
        original = getattr(module, klass)

        # The framework interface fixes these parameter names; execution ownership stays explicit.
        def get_clock(self: Any, c: Any = clock) -> Any:  # noqa: ARG001
            return c

        def subscribe(
            self: Any, msg_type: Any, topic: str, callback: str, qos: Any, *args, _name: Any = name, **kwargs
        ) -> Any:
            kind = msg_type.__module__.split(".")[0] + "/msg/" + msg_type.__name__
            registrations[_name].append((topic, callback.__name__, kind))
            return rclpy.node.Node.create_subscription(self, msg_type, topic, callback, qos, *args, **kwargs)

        def publisher(self: Any, msg_type: Any, topic: str, qos: Any, *args, _name: Any = name, **kwargs) -> Any:
            real = rclpy.node.Node.create_publisher(self, msg_type, topic, qos, *args, **kwargs)
            if topic == "/parameter_events":
                return real
            kind = msg_type.__module__.split(".")[0] + "/msg/" + msg_type.__name__
            return Recorder(real, topic, kind, published[_name])

        def timer(self: Any, period: Any, callback: str, *args, _name: Any = name, **kwargs) -> Any:
            periods[_name].append((round(period * 1e9), callback.__name__))
            return rclpy.node.Node.create_timer(self, period, callback, *args, **kwargs)

        derived = type(
            "Observed" + klass,
            (original,),
            {"get_clock": get_clock, "create_subscription": subscribe, "create_publisher": publisher, "create_timer": timer},
        )
        config_path = str(source / configuration) if configuration else ""
        context = Context()
        rclpy.init(args=[], context=context)
        contexts.append(context)
        original_init = rclpy.node.Node.__init__
        overrides = [Parameter("config_file", value=config_path)] if config_path else []

        def initialize(
            self: Any,
            *args,
            _context: Any = context,
            _overrides: Any = overrides,
            _initialize: Any = original_init,
            **kwargs,
        ):
            _initialize(self, *args, context=_context, parameter_overrides=_overrides, **kwargs)

        with patch.object(rclpy.node.Node, "__init__", initialize):
            node = derived()
        nodes[name] = node
        params = {key: value.value for key, value in node._parameters.items()}
        vectors[name] = {
            "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "parameters": params,
            "helper_sources": helper_sources,
            "configuration_sha256": hashlib.sha256(Path(config_path).read_bytes()).hexdigest() if config_path else None,
            "initial_clock_reads": list(clock.reads),
            "initial_steady_reads": list(clock.steady_reads),
            "calls": [],
        }
    # Original ROS objects above remain data/callback hosts; source vector calls
    # are explicit, without spinning their timers or generating duplicate inputs.
    queue = []

    def invoke(name: str, callback: str, value: Any = None):
        clock = clocks[name]
        clock.reads.clear()
        clock.steady_reads.clear()
        published[name].clear()
        if value is None:
            getattr(nodes[name], callback)()
        else:
            getattr(nodes[name], callback)(value)
        outputs = [
            {"topic": topic, "type": kind, "fields": message_to_ordereddict(msg)} for topic, kind, msg in published[name]
        ]
        vectors[name]["calls"].append(
            {
                "callback": callback,
                "input": message_to_ordereddict(value) if value is not None else None,
                "time_ns": clock.current_ns,
                "clock_reads": list(clock.reads),
                "steady_reads": list(clock.steady_reads),
                "outputs": outputs,
            }
        )
        queue.extend(published[name])

    def deliver(topic: str, kind: str, value: Any):
        queue.append((topic, kind, value))
        while queue:
            t, k, v = queue.pop(0)
            for n, items in registrations.items():
                for expected, callback, message_type in items:
                    if t == expected:
                        if k != message_type:
                            raise ValueError(f"Observer reference port mismatch: {t}")
                        invoke(n, callback, v)

    for tick in range(1, 101):
        for clock in clocks.values():
            clock.current_ns = epoch + tick * 100_000_000
        geo = GeoPosition()
        geo.heading_deg = 0.0
        geo.course_deg = 0.0
        geo.speed_mps = 7.8
        geo.surge_mps = 7.8
        geo.origin_locked = True
        geo.x_ned = tick * 0.78
        geo.cross_track_error_m = 40.0 if 20 <= tick < 60 else 0.0
        geo.roll_deg = 15.0 if 40 <= tick < 60 else 0.0
        deliver("/ship/geo_position", "ship_interfaces/msg/GeoPosition", geo)
        odom = Odometry()
        odom.twist.twist.linear.x = 7.8
        deliver("/ship/odometry", "nav_msgs/msg/Odometry", odom)
        deliver("/control/heading_setpoint", "std_msgs/msg/Float64", Float64(data=0.1 if tick > 50 else 0.0))
        deliver("/control/speed_setpoint", "std_msgs/msg/Float64", Float64(data=7.8))
        deliver(
            "/thruster/commands",
            "std_msgs/msg/Float64MultiArray",
            Float64MultiArray(data=[50000.0, 0.0] * 3 + [0.0, 0.0] * 2 + [0.0, 0.1] * 2),
        )
        status = DiagnosticStatus()
        status.level = bytes([1 if 30 <= tick < 70 else 0])
        status.message = "saturated" if tick >= 30 else "nominal"
        status.values = [
            KeyValue(key="normalized_error", value="0.5" if tick >= 30 else "0.0"),
            KeyValue(key="degradation_level", value="2" if tick >= 30 else "1"),
        ]
        diag = DiagnosticArray()
        diag.status = [status]
        deliver("/allocation/status", "diagnostic_msgs/msg/DiagnosticArray", diag)
        residual = WrenchStamped()
        residual.wrench.force.y = 30000.0 if tick >= 30 else 0.0
        deliver("/allocation/residual_tau", "geometry_msgs/msg/WrenchStamped", residual)
        for n, timers in periods.items():
            for period, callback in timers:
                if tick * 100_000_000 % period == 0:
                    invoke(n, callback)
                    while queue:
                        topic, kind, value = queue.pop(0)
                        deliver(topic, kind, value)
    result = {
        "schema": "original-gnc.observer-vectors.v1",
        "scope": "independent source observer single-module cases",
        "epoch_ns": epoch,
        "modules": vectors,
    }
    output.write_text(json.dumps(result, indent=2))
    for node in nodes.values():
        node.destroy_node()
    for context in contexts:
        context.shutdown()
    return {n: len(v["calls"]) for n, v in vectors.items()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.source, args.output), indent=2))
