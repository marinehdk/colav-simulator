"""Synchronous multi-rate execution of the source GNC's typed data ports.

Every source timer keeps its own period; allocation remains callback driven.
The scheduler orders equal-time events by registration, and dispatches each
publication breadth first before advancing to the next timer. No ROS runtime.
"""

from __future__ import annotations

import copy
import heapq
import math
from collections import defaultdict, deque
from collections.abc import Callable
from pathlib import Path

from colav_simulator.original_gnc.native import NativeModule, OriginalGncError
from colav_simulator.original_gnc.observers import NativeObserver, observer_parameters
from colav_simulator.original_gnc.policy import NativePolicy

# A positive epoch preserves the original zero-stamp sentinel semantics.
DEFAULT_EPOCH_NS = 2_000_000_000_000_000_000
MODULE_ORDER = (
    "wind_engine_node",
    "wave_engine_node",
    "current_engine_node",
    "force_aggregator_node",
    "ship_dynamics_node",
    "active_route_manager_node",
    "coordinate_transform_node",
    "ship_guidance_node",
    "thrust_allocation_node",
    "ship_control_node",
)


class NativeStack:
    """Own one vessel's original kernels, policy, event queue and feedback."""

    def __init__(
        self,
        build: Path,
        parameters: dict[str, dict],
        package_roots: dict[str, str],
        policy_config: dict,
        *,
        enabled_environment: tuple[str, ...] = (),
        asset_paths: dict[str, str] | None = None,
        epoch_ns: int = DEFAULT_EPOCH_NS,
        trace: Callable[[dict], None] | None = None,
    ):
        if isinstance(epoch_ns, bool) or not isinstance(epoch_ns, int) or not 0 < epoch_ns < 2**63:
            raise ValueError("Original GNC epoch must be a positive int64 nanosecond timestamp")
        if not set(enabled_environment) <= {"wind", "wave", "current"}:
            raise ValueError("Unknown original environment engine")
        self.epoch_ns = self.time_ns = epoch_ns
        self.modules: dict[str, NativeModule] = {}
        self.policy: NativePolicy | None = None
        self.observers: dict[str, NativeObserver] = {}
        self._subscribers = defaultdict(list)
        self._events = []
        self._timer_generation = {}
        self._order = 0
        self._pending = deque()
        self.latest: dict[str, dict] = {}
        self.states: dict[str, dict] = {}
        self._trace = trace
        self._closed = False
        initial_outputs = []
        try:
            for name in MODULE_ORDER:
                if name.endswith("_engine_node") and name.removesuffix("_engine_node") not in enabled_environment:
                    continue
                if name == "force_aggregator_node" and not enabled_environment:
                    continue
                module = NativeModule(
                    build,
                    name,
                    copy.deepcopy(parameters[name]),
                    {"time_ns": epoch_ns, "package_roots": package_roots, "asset_paths": asset_paths or {}},
                )
                self.modules[name] = module
                description = module.describe()
                self.states[name] = description["state"]
                for callback, port in description["inputs"].items():
                    self._subscribers[port["topic"]].append((name, callback, port["type"]))
                for timer in description["timer_descriptors"].values():
                    self._update_timer(name, timer)
                initial_outputs.extend(description["initial_outputs"])
            self.policy = NativePolicy(build, copy.deepcopy(policy_config), epoch_ns)
            policy_types = {
                "/mission/status": "std_msgs/msg/String",
                "/captain/decision": "std_msgs/msg/String",
                "/ship/odometry": "nav_msgs/msg/Odometry",
                "/cmd_tau": "geometry_msgs/msg/WrenchStamped",
                "/actuator/capability": "std_msgs/msg/Float64MultiArray",
                "/env/total_load": "geometry_msgs/msg/WrenchStamped",
                "/guidance/dp_hold_active": "std_msgs/msg/Bool",
            }
            for topic, callback in self.policy.callbacks.items():
                self._subscribers[topic].append(("propulsion_policy_node", callback, policy_types[topic]))
            self._update_timer(
                "propulsion_policy_node",
                {
                    "callback": "_tick",
                    "generation": 1,
                    "active": True,
                    "created_ns": epoch_ns,
                    "period_ns": round(self.policy.core.period_s * 1e9),
                },
            )
            for name, settings in observer_parameters(package_roots).items():
                observer = NativeObserver(build, name, settings, epoch_ns)
                self.observers[name] = observer
                for callback, (topic, kind, _) in observer.inputs.items():
                    self._subscribers[topic].append((name, callback, kind))
                for callback, period in observer.timers.items():
                    self._update_timer(
                        name,
                        {"callback": callback, "generation": 1, "active": True, "created_ns": epoch_ns, "period_ns": period},
                    )
            self._pending.extend(initial_outputs)
            self._drain()
        except Exception:
            self.close()
            raise

    @property
    def elapsed_s(self) -> float:
        """Elapsed simulation time, without subtracting floating point epochs."""
        return (self.time_ns - self.epoch_ns) / 1_000_000_000

    def _update_timer(self, name: str, descriptor: dict) -> None:
        key = (name, descriptor["callback"])
        if not descriptor["active"]:
            self._timer_generation.pop(key, None)
            return
        generation = descriptor["generation"]
        self._timer_generation[key] = generation
        period = descriptor["period_ns"]
        self._push_timer(descriptor["created_ns"] + period, name, descriptor["callback"], generation, period)

    def _push_timer(self, due: int, name: str, callback: str, generation: int, period: int) -> None:
        self._order += 1
        heapq.heappush(self._events, (due, self._order, name, callback, generation, period))

    def _invoke(self, name: str, callback: str, fields: dict | None) -> None:
        if self._trace:
            self._trace({"event": "call", "time_ns": self.time_ns, "node": name, "callback": callback, "input": fields})
        if name == "propulsion_policy_node":
            outputs = self.policy.invoke(callback, fields, self.time_ns)
            self.states[name] = self.policy.snapshot()
            self._pending.extend(
                {"node": name, "topic": o["topic"], "message": {"type": o["type"], "fields": o["fields"]}} for o in outputs
            )
        elif name in self.observers:
            outputs = self.observers[name].invoke(callback, fields, self.time_ns)
            self._pending.extend(
                {"node": name, "topic": o["topic"], "message": {"type": o["type"], "fields": o["fields"]}} for o in outputs
            )
        else:
            result = self.modules[name].invoke(callback, fields, self.time_ns)
            self.states[name] = result["state"]
            for timer in result["timer_updates"]:
                self._update_timer(name, timer)
            self._pending.extend(result["outputs"])

    def _drain(self) -> None:
        while self._pending:
            output = self._pending.popleft()
            topic, message = output["topic"], output["message"]
            self.latest[topic] = message["fields"]
            if self._trace:
                self._trace({"event": "publish", "time_ns": self.time_ns, **output})
            for name, callback, expected_type in self._subscribers.get(topic, ()):
                if expected_type != message["type"]:
                    raise OriginalGncError(f"Native port type mismatch on {topic}: {expected_type} != {message['type']}")
                self._invoke(name, callback, message["fields"])

    def publish(self, topic: str, message_type: str, fields: dict) -> None:
        """Deliver external values at current simulation time through source ports."""
        self._ensure_open()
        if topic not in self._subscribers:
            raise OriginalGncError(f"No original input port consumes {topic}")
        self._pending.append(
            {"node": "external", "topic": topic, "message": {"type": message_type, "fields": copy.deepcopy(fields)}}
        )
        try:
            self._drain()
        except Exception:
            self.close()
            raise

    def advance(self, duration_s: float) -> None:
        """Run every due source timer, preserving fractional outer-step remainder."""
        self._ensure_open()
        if not math.isfinite(duration_s) or duration_s < 0:
            raise ValueError("Native GNC step must be finite and nonnegative")
        target = self.time_ns + round(duration_s * 1e9)
        if target >= 2**63:
            raise ValueError("Native GNC timestamp overflow")
        try:
            while self._events and self._events[0][0] <= target:
                due, _, name, callback, generation, period = heapq.heappop(self._events)
                if self._timer_generation.get((name, callback)) != generation:
                    continue
                self.time_ns = due
                self._invoke(name, callback, None)
                self._drain()
                if self._timer_generation.get((name, callback)) == generation:
                    self._push_timer(due + period, name, callback, generation, period)
            self.time_ns = target
        except Exception:
            self.close()
            raise

    def _ensure_open(self) -> None:
        if self._closed:
            raise OriginalGncError("Original GNC stack has been closed")

    def close(self) -> None:
        """Release only this vessel's kernels and scheduled callbacks."""
        for module in self.modules.values():
            module.close()
        self.modules.clear()
        self.observers.clear()
        self.policy = None
        self._subscribers.clear()
        self._timer_generation.clear()
        self._events.clear()
        self._pending.clear()
        self._closed = True

    def __enter__(self) -> NativeStack:
        """Keep native ownership within a deterministic scope."""
        return self

    def __exit__(self, *_: object) -> None:
        """Release kernels even when execution raises."""
        self.close()
