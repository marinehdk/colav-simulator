"""Test-only adapters around independently compiled C++ nodes and actual original Python nodes."""

from __future__ import annotations

import importlib.util
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path
from types import MethodType, SimpleNamespace
from typing import Any
from unittest.mock import patch

import yaml
from rclpy.clock import Clock, ClockType
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.serialization import deserialize_message, serialize_message
from rclpy.time import Time
from rosidl_runtime_py.convert import message_to_ordereddict
from rosidl_runtime_py.utilities import get_message

SETTINGS = {}
CPP_INSTANCES = []
PY_INSTANCES = []


def portable(value: Any) -> Any:
    """Use explicit nonfinite sentinels at the typed test-transport boundary."""
    if isinstance(value, float) and not math.isfinite(value):
        return {"$nonfinite": "nan" if math.isnan(value) else "+inf" if value > 0 else "-inf"}
    if isinstance(value, dict):
        return {k: portable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [portable(v) for v in value]
    return value


def restored(value: Any) -> Any:
    """Restore source optional float sentinels before real ROS deserialization."""
    if isinstance(value, dict):
        if set(value) == {"$nonfinite"}:
            return {"nan": math.nan, "+inf": math.inf, "-inf": -math.inf}[value["$nonfinite"]]
        return {k: restored(v) for k, v in value.items()}
    if isinstance(value, list):
        return [restored(v) for v in value]
    return value


def fields(message: Any) -> dict:
    """Normalize only ROS scalar-byte representation, keeping all actual values."""
    result = message_to_ordereddict(message)

    def bytes_in(obj: Any, data: dict) -> None:
        for key in obj.get_fields_and_field_types():
            value = getattr(obj, key)
            if isinstance(value, bytes):
                data[key] = value[0] if len(value) == 1 else list(value)
            elif hasattr(value, "get_fields_and_field_types"):
                bytes_in(value, data[key])
            elif isinstance(value, (list, tuple)):
                for item, converted in zip(value, data[key], strict=True):
                    if hasattr(item, "get_fields_and_field_types"):
                        bytes_in(item, converted)

    bytes_in(message, result)
    return portable(result)


def message(kind: str, value: dict) -> Any:
    """Build a real ROS message for an original callback."""

    def assign(obj: Any, data: dict) -> Any:
        specifications = obj.get_fields_and_field_types()
        for key, original_item in data.items():
            item = original_item
            current = getattr(obj, key)
            spec = specifications[key]
            if hasattr(current, "get_fields_and_field_types"):
                item = assign(current, item)
            elif isinstance(current, bytes):
                item = (
                    item.encode("latin1")
                    if isinstance(item, str)
                    else bytes([item])
                    if isinstance(item, int)
                    else bytes(item)
                )
            elif isinstance(item, list) and item and isinstance(item[0], dict):
                token = re.search(r"<([^,>]+)", spec)
                identity = token[1] if token else spec.split("[")[0]
                if "/msg/" not in identity:
                    identity = identity.replace("/", "/msg/")
                item = [assign(get_message(identity)(), fields) for fields in item]
            elif spec in ("float", "double", "float32", "float64") and isinstance(item, int):
                item = float(item)
            setattr(obj, key, item)
        return obj

    return assign(get_message(kind)(), restored(value))


class CppSourceKernel:
    """Invoke only a separately compiled original ROS node; no native DLL load."""

    def __init__(self, build: Path, name: str, parameters: dict, options: dict):  # noqa: ARG002
        self.name = name
        self.parameters = parameters
        folder = SETTINGS["output"] / name
        folder.mkdir(parents=True)
        config = folder / "parameters.yaml"
        actual = json.loads(json.dumps(parameters))
        for key in ("log_dir", "feedback_log_dir"):
            if key in actual:
                actual[key]["value"] = str(folder / "source-logs")
        config.write_text(
            yaml.safe_dump({name: {"ros__parameters": {k: v["value"] for k, v in actual.items() if v["value"] != []}}})
        )
        Path(str(config) + ".typed.json").write_text(json.dumps(actual))
        self.log = (folder / "process.log").open("w")
        env = {
            **os.environ,
            "ORIGINAL_GNC_PROTOCOL": "1",
            "ROS_DOMAIN_ID": str(SETTINGS["domain"]),
            "ROS_LOCALHOST_ONLY": "1",
            "ROS_LOG_DIR": str(folder / "ros-log"),
        }
        for key in ("ORIGINAL_GNC_REPLAY_FILE", "ORIGINAL_GNC_TRACE_DIR"):
            env.pop(key, None)
        self.process = subprocess.Popen(
            [str(SETTINGS["drivers"] / f"{name}_replay"), name, str(config)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=self.log,
            text=True,
            bufsize=1,
            env=env,
        )
        CPP_INSTANCES.append(self)
        self.description = self._receive("ORIGINAL_READY ")
        self.description["initial_outputs"] = self._outputs(self.description["initial_outputs"])
        self.description["parameters"] = parameters
        self.description["timers"] = {
            key: value["period_ns"] for key, value in self.description["timer_descriptors"].items()
        }

    def _receive(self, prefix: str) -> dict:
        for line in self.process.stdout:
            if line.startswith(prefix):
                return json.loads(line[len(prefix) :])
            self.log.write(line)
        raise RuntimeError(f"Original source kernel exited: {self.name}; see {self.log.name}")

    def _outputs(self, records: list[dict]) -> list[dict]:
        result = []
        for record in records:
            raw = record["message"]
            obj = deserialize_message(bytes.fromhex(raw["cdr_hex"]), get_message(raw["type"]))
            result.append(
                {
                    "node": self.name,
                    "topic": record["topic"],
                    "port": record["port"],
                    "message": {"type": raw["type"], "fields": fields(obj)},
                }
            )
        return result

    def describe(self) -> dict:
        """Expose actual observed source subscriptions and timer periods."""
        return self.description

    def invoke(self, callback: str, value: dict | None, time_ns: int) -> dict:
        """Drive one original callback at its explicitly supplied test time."""
        encoded = None
        if value is not None:
            kind = self.description["inputs"][callback]["type"]
            obj = message(kind, value)
            encoded = {"type": kind, "cdr_hex": serialize_message(obj).hex()}
        self.process.stdin.write(json.dumps({"function": callback, "input": encoded, "time_ns": time_ns}) + "\n")
        self.process.stdin.flush()
        result = self._receive("ORIGINAL_RESULT ")
        result["outputs"] = self._outputs(result["outputs"])
        return result

    def close(self) -> None:
        """Terminate only this source test process and preserve its log."""
        if self.process.poll() is None:
            self.process.stdin.close()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                self.process.wait(timeout=5)
        self.log.close()


PYTHON_NODES = {
    "propulsion_policy_node": (
        "src/mission/mission_supervisor/mission_supervisor/propulsion_policy_node.py",
        "PropulsionPolicyNode",
    ),
    "navigation_mode_observer_node": (
        "src/mission/mission_supervisor/mission_supervisor/navigation_mode_observer_node.py",
        "NavigationModeObserverNode",
    ),
    "operational_risk_observer_node": (
        "src/safety/safety_supervisor/safety_supervisor/operational_risk_observer_node.py",
        "OperationalRiskObserverNode",
    ),
    "operator_command_interpreter": (
        "src/platform/ship_utils/ship_utils/operator_command_interpreter.py",
        "OperatorCommandInterpreter",
    ),
}


class PythonSourceNode:
    """Retain actual source Node logic, intercepting only clocks and typed ports."""

    def __init__(self, name: str, parameters: dict, time_ns: int):
        self.time_ns = self.epoch_ns = time_ns
        self.outputs = []
        self.inputs = {}
        self.timers = {}
        self.functions = {}
        path, klass = PYTHON_NODES[name]
        source = SETTINGS["source"] / path
        spec = importlib.util.spec_from_file_location("coupled_source_" + name, source)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        if hasattr(module, "time"):
            module.time = SimpleNamespace(monotonic=lambda: 1_000_000.0 + (self.time_ns - self.epoch_ns) / 1e9)
        clock = Clock(clock_type=ClockType.ROS_TIME)
        clock.now = MethodType(lambda _clock: Time(nanoseconds=self.time_ns, clock_type=ClockType.ROS_TIME), clock)

        def subscribe(node: Any, kind: Any, topic: str, callback: Any, qos: Any, **kwargs: Any) -> Any:
            label = callback.__name__
            self.functions[label] = callback
            self.inputs[label] = (topic, kind.__module__.split(".")[0] + "/msg/" + kind.__name__, False)
            return Node.create_subscription(node, kind, topic, callback, qos, **kwargs)

        def publisher(node: Any, kind: Any, topic: str, qos: Any, **kwargs: Any) -> Any:
            real = Node.create_publisher(node, kind, topic, qos, **kwargs)
            parent = self

            class Capture:
                def publish(self, msg: Any) -> None:
                    parent.outputs.append(
                        {
                            "topic": topic,
                            "type": kind.__module__.split(".")[0] + "/msg/" + kind.__name__,
                            "fields": fields(msg),
                        }
                    )

                def __getattr__(self, key: str) -> Any:
                    return getattr(real, key)

            return Capture()

        def timer(node: Any, period: float, callback: Any, **kwargs: Any) -> Any:
            label = callback.__name__
            self.functions[label] = callback
            self.timers[label] = round(period * 1e9)
            return Node.create_timer(node, period, callback, **kwargs)

        derived = type(
            "Coupled" + klass,
            (getattr(module, klass),),
            {
                "get_clock": lambda _node: clock,
                "create_subscription": subscribe,
                "create_publisher": publisher,
                "create_timer": timer,
            },
        )
        initialize = Node.__init__
        overrides = [Parameter(k, value=v) for k, v in parameters.items()]

        def init(node: Any, *args: Any, **kwargs: Any) -> None:
            initialize(node, *args, parameter_overrides=overrides, **kwargs)

        with patch.object(Node, "__init__", init):
            self.core = derived()
        self.source_file = source
        PY_INSTANCES.append(self)

    def invoke(self, callback: str, value: dict | None, time_ns: int) -> list[dict]:
        """Call original Python methods using real ROS messages."""
        self.time_ns = time_ns
        self.outputs = []
        if value is None:
            self.functions[callback]()
        else:
            self.functions[callback](message(self.inputs[callback][1], value))
        return self.outputs

    def close(self) -> None:
        """Release only this source observation node."""
        self.core.destroy_node()


class SourcePolicy(PythonSourceNode):
    """Match the scheduler's policy interface with the actual original node."""

    def __init__(self, build: Path, config: dict, time_ns: int):  # noqa: ARG002
        super().__init__(
            "propulsion_policy_node",
            {
                "config_file": str(SETTINGS["source"] / "src/mission/mission_supervisor/config/propulsion_policy.yaml"),
                "scenario_file": "",
                "shadow_mode": True,
                "publish_rate_hz": 2.0,
            },
            time_ns,
        )
        self.callbacks = {topic: callback for callback, (topic, _, _) in self.inputs.items()}

    def snapshot(self) -> dict:
        """Read original policy state without changing its filter or gates."""
        return {
            "speed_mps": self.core.speed_mps,
            "raw_speed_mps": self.core.raw_speed_mps,
            "side_thruster_speed_allowed": self.core.side_thruster_speed_allowed_state,
        }


class SourceObserver(PythonSourceNode):
    """Match the scheduler's observer interface with an actual original node."""

    def __init__(self, build: Path, name: str, parameters: dict, time_ns: int):  # noqa: ARG002
        super().__init__(name, parameters, time_ns)
