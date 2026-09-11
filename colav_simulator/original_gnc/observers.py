"""Typed value boundaries for the original non-actuating observation modules."""

from __future__ import annotations

import dataclasses
import hashlib
import importlib.util
import json
import math
import re
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

from colav_simulator.original_gnc.native import OriginalGncError, verify_build


def observer_parameters(package_roots: dict[str, str]) -> dict:
    """Resolve the original normal-launch observer configurations locally."""
    path = Path(__file__).with_name("data") / "observer_parameters.json"
    parameters = json.loads(path.read_text())["parameters"]
    for name, package, filename in [
        ("navigation_mode_observer_node", "mission_supervisor", "navigation_mode_policy.yaml"),
        ("operational_risk_observer_node", "safety_supervisor", "operational_risk_policy.yaml"),
    ]:
        config = Path(package_roots[package]) / "config" / filename
        if not config.is_file():
            raise OriginalGncError(f"Original observation config is missing: {config}")
        parameters[name]["config_file"] = str(config)
    return parameters


def portable(value: Any) -> Any:
    """Preserve source nonfinite sentinels explicitly in native JSON records."""
    if dataclasses.is_dataclass(value):
        value = dataclasses.asdict(value)
    if isinstance(value, float) and not math.isfinite(value):
        return {"$nonfinite": "nan" if math.isnan(value) else "+inf" if value > 0 else "-inf"}
    if isinstance(value, dict):
        return {key: portable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [portable(item) for item in value]
    return value


def load_observer_package(folder: Path, identity: str) -> ModuleType:
    """Give each generated package an isolated import identity for helper files."""
    name = "_original_gnc_observers_" + identity
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, folder / "__init__.py", submodule_search_locations=[str(folder)])
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


class ValueOutput:
    """Collect a typed source value; delivery belongs to the explicit scheduler."""

    def __init__(self, destination: list, message_class: type, topic: str):
        self.destination, self.message_class, self.topic = destination, message_class, topic

    def emit(self, value: Any) -> None:
        if not isinstance(value, self.message_class):
            raise OriginalGncError("Original observer emitted an incompatible value type")
        self.destination.append({"topic": self.topic, "type": self.message_class.type_name, "fields": portable(value)})


class MessageValues:
    """Construct plain data values from the frozen message field contracts."""

    def __init__(self, registry: dict):
        self.registry = registry

    @staticmethod
    def output(destination: list, message_class: type, topic: str) -> ValueOutput:
        return ValueOutput(destination, message_class, topic)

    def stamp(self, nanoseconds: int) -> Any:
        return self.registry["builtin_interfaces/msg/Time"](
            sec=nanoseconds // 1_000_000_000, nanosec=nanoseconds % 1_000_000_000
        )

    def message(self, message_type: str, fields: dict) -> Any:
        cls = self.registry[message_type]
        if set(fields) != set(cls.field_types):
            raise OriginalGncError(f"Original observer message field coverage differs: {message_type}")
        result = cls()
        package = message_type.split("/")[0]
        for name, token in cls.field_types.items():
            setattr(result, name, self._value(package, token, fields[name]))
        return result

    def _value(self, package: str, token: str, value: Any) -> Any:
        array = re.fullmatch(r"(.+)\[(\d*)\]", token)
        if array:
            if not isinstance(value, list) or (array[2] and len(value) != int(array[2])):
                raise OriginalGncError(f"Original observer array contract differs: {token}")
            return [self._value(package, array[1], item) for item in value]
        if isinstance(value, dict) and set(value) == {"$nonfinite"}:
            return {"nan": float("nan"), "+inf": float("inf"), "-inf": float("-inf")}[value["$nonfinite"]]
        if token in {"byte", "char"} and isinstance(value, str) and len(value) == 1:
            return ord(value)
        if token in {"bool", "byte", "char", "string"} or token.startswith(("float", "int", "uint")):
            return value
        identity = token if "/" in token else package + "/" + token
        return self.message(identity.replace("/", "/msg/"), value)


class NativeObserver:
    """Own source observer state with explicit simulation and monotonic clocks."""

    def __init__(
        self,
        build: Path,
        name: str,
        parameters: dict,
        time_ns: int,
        *,
        replay_clocks: list[int] | None = None,
        replay_steady: list[float] | None = None,
    ):
        manifest = verify_build(build)
        metadata = json.loads((build / "extraction.json").read_text())["python_observers"][name]
        fingerprints = {key: value for key, value in manifest["source_fingerprints"].items() if key.startswith("observers/")}
        identity = hashlib.sha256(json.dumps(fingerprints, sort_keys=True).encode()).hexdigest()
        package = load_observer_package(build / "observers", identity)
        module = __import__(package.__name__ + "." + name, fromlist=[metadata["class"]])
        values = __import__(package.__name__ + ".message_values", fromlist=["REGISTRY"])
        self.values = MessageValues(values.REGISTRY)
        self.time_ns = self.epoch_ns = time_ns
        self._clocks = iter(replay_clocks) if replay_clocks is not None else None
        self._steady = iter(replay_steady) if replay_steady is not None else None
        self.clock_reads = self.steady_reads = 0
        self.core = getattr(module, metadata["class"])(parameters, self._read_clock, self._read_steady, self.values)
        self.inputs = {callback: (topic, kind, latched) for topic, callback, kind, latched in self.core.inputs}
        self.timers = {callback: round(period * 1e9) for period, callback in self.core.timers}

    def _read_clock(self) -> int:
        self.clock_reads += 1
        return self.time_ns if self._clocks is None else next(self._clocks)

    def _read_steady(self) -> float:
        self.steady_reads += 1
        return 1_000_000.0 + (self.time_ns - self.epoch_ns) / 1_000_000_000 if self._steady is None else next(self._steady)

    def invoke(self, callback: str, fields: dict | None, time_ns: int) -> list[dict]:
        """Apply one source input or periodic observation without control fallback."""
        if callback not in self.inputs and callback not in self.timers:
            raise OriginalGncError(f"Unknown original observer callback: {callback}")
        self.time_ns = time_ns
        self.core.outputs.clear()
        if callback in self.inputs:
            getattr(self.core, callback)(self.values.message(self.inputs[callback][1], fields))
        else:
            getattr(self.core, callback)()
        return list(self.core.outputs)
