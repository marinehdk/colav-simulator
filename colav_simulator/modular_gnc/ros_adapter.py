"""Optional peripheral ROS 2 adapter and simulation-time SIL harness (Issue #64).

The adapter is strictly peripheral (VR-02, VR-03, SC-09): core stack, planner,
and plant code never imports this module, and the adapter itself never advances
core state.  Its single job is to materialize tick-indexed typed inputs
(``CommandInput``) for the ``ModularShipStack`` facade from a transport stream,
exposing transport faults as structured failure classes (TS-17): QoS
incompatibility, input-stream freshness, duplicate, stale, and out-of-order
deliveries, peer reset, and peer process loss.

Simulation-time ownership is the hard contract (TS-08, VR-05): every failure
classification is computed from integer simulation ticks only.  Wall-clock time
never enters the adapter or the ``SilHarness``; core state is advanced solely by
the harness caller stepping the stack once per integer tick.  The adapter holds
no reference to the stack, so it structurally cannot advance the core.

ROS 2 stays an optional dependency (VR-02, TS-25, VR-29): this module imports
without rclpy installed.  rclpy is lazy-imported only when a real
``Ros2CommandTransport`` is constructed; without it the dependency status is a
structured ``DEPENDENCY_UNAVAILABLE`` value, never a crash and never a silent
fallback.  All adapter semantics are exercised against the in-memory
``ScriptedCommandTransport`` behind the same seam.

Claim ceiling: A3 (Generalized Simulation, TS-29/VR-25).  The G10 gate produced
by :func:`run_g10_gate` is reported separately (VR-24) with the honest
three-state verdict pattern and explicitly makes no A6 (ROS 2/SIL/HIL) claim.
"""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
import time
from collections import deque
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import numpy as np

from colav_simulator.modular_gnc.a3_demo import GateCheck, GateResult
from colav_simulator.modular_gnc.contracts import (
    CommandInput,
    ControlTask,
    DirectReference,
    FacadeFailure,
    NavigationState,
    StackSnapshot,
    TrackedRoute,
    _deep_freeze,
    _finite_scalar,
    _non_bool_int,
    _non_empty_str,
)
from colav_simulator.modular_gnc.stack import ModularShipStack

G10_REPORT_SCHEMA_VERSION = "modular-gnc.g10-sil-report.v1"
G10_CLAIM_CEILING = "A3"
G10_CLAIM_CEILING_LABEL = "Generalized Simulation"

G10_NON_CLAIMS: tuple[str, ...] = (
    "No A6 (ROS 2/SIL/HIL) acceptance is claimed: every adapter semantic is exercised "
    "through an in-memory scripted transport at simulation time only.",
    "No hardware-in-the-loop, real DDS discovery, or ROS 2 runtime behavior is exercised "
    "or claimed by this gate.",
    "G10 evidence is reported separately (VR-24) and implies no other gate's acceptance.",
)

_ADAPTER_SNAPSHOT_SCHEMA_VERSION = "ros-command-adapter.snapshot.v1"
_HARNESS_TERMINATED_MESSAGE = "harness terminated; reset() before a new run"


class QosReliability(str, Enum):
    """DDS-style reliability policy offered or requested on a transport channel."""

    RELIABLE = "RELIABLE"
    BEST_EFFORT = "BEST_EFFORT"


class QosDurability(str, Enum):
    """DDS-style durability policy offered or requested on a transport channel."""

    VOLATILE = "VOLATILE"
    TRANSIENT_LOCAL = "TRANSIENT_LOCAL"


@dataclass(frozen=True)
class TransportQos:
    """Immutable QoS description of a transport channel (offered or requested)."""

    reliability: QosReliability
    durability: QosDurability
    depth: int

    def __post_init__(self) -> None:
        """Coerce policy members and validate positive history depth."""
        object.__setattr__(self, "reliability", QosReliability(self.reliability))
        object.__setattr__(self, "durability", QosDurability(self.durability))
        depth = _non_bool_int("depth", self.depth)
        if depth < 1:
            raise ValueError(f"depth must be at least 1, got {depth}")
        object.__setattr__(self, "depth", depth)


def is_qos_compatible(requested: TransportQos, offered: TransportQos) -> bool:
    """Return whether a requested QoS is satisfiable by an offered QoS (request <= offered).

    DDS monotonicity: a RELIABLE request requires a RELIABLE offer, and a
    TRANSIENT_LOCAL request requires a TRANSIENT_LOCAL offer.  History depth is
    per-endpoint configuration and deliberately not part of compatibility.
    """
    if requested.reliability is QosReliability.RELIABLE and offered.reliability is not QosReliability.RELIABLE:
        return False
    if requested.durability is QosDurability.TRANSIENT_LOCAL and offered.durability is not QosDurability.TRANSIENT_LOCAL:
        return False
    return True


@dataclass(frozen=True)
class DirectReferencePayload:
    """Typed wire payload materializing a legacy nine-element direct reference."""

    values: tuple[float, ...]

    def __post_init__(self) -> None:
        """Validate the strict nine-element finite payload and freeze."""
        if not isinstance(self.values, (tuple, list)) or len(self.values) != 9:
            raise ValueError(f"values must contain exactly 9 finite elements, got {self.values!r}")
        object.__setattr__(
            self, "values", tuple(_finite_scalar(f"values[{index}]", value) for index, value in enumerate(self.values))
        )


@dataclass(frozen=True)
class RouteCommandPayload:
    """Typed wire payload materializing an accepted tracked route."""

    route_id: str
    revision: int
    waypoints_ne_m: tuple[tuple[float, float], ...]
    speed_mps: tuple[float, ...]
    task: ControlTask
    valid_until_tick: int

    def __post_init__(self) -> None:
        """Validate route identity, geometry, speed profile, task, and validity."""
        object.__setattr__(self, "route_id", _non_empty_str("route_id", self.route_id))
        object.__setattr__(self, "revision", _non_bool_int("revision", self.revision))
        object.__setattr__(self, "task", ControlTask(self.task))
        object.__setattr__(self, "valid_until_tick", _non_bool_int("valid_until_tick", self.valid_until_tick))
        if not isinstance(self.waypoints_ne_m, (tuple, list)) or len(self.waypoints_ne_m) < 2:
            raise ValueError("waypoints_ne_m must contain at least 2 (north, east) pairs")
        waypoints: list[tuple[float, float]] = []
        for index, waypoint in enumerate(self.waypoints_ne_m):
            if not isinstance(waypoint, (tuple, list)) or len(waypoint) != 2:
                raise ValueError(f"waypoints_ne_m[{index}] must be a (north, east) pair")
            waypoints.append(
                (
                    _finite_scalar(f"waypoints_ne_m[{index}][0]", waypoint[0]),
                    _finite_scalar(f"waypoints_ne_m[{index}][1]", waypoint[1]),
                )
            )
        object.__setattr__(self, "waypoints_ne_m", tuple(waypoints))
        if not isinstance(self.speed_mps, (tuple, list)) or len(self.speed_mps) != len(waypoints):
            raise ValueError(
                f"speed_mps must contain one speed per waypoint ({len(waypoints)}), "
                f"got {len(self.speed_mps) if isinstance(self.speed_mps, (tuple, list)) else self.speed_mps!r}"
            )
        speeds = tuple(_finite_scalar(f"speed_mps[{index}]", value) for index, value in enumerate(self.speed_mps))
        object.__setattr__(self, "speed_mps", speeds)


@dataclass(frozen=True)
class TransportMessage:
    """One typed transport message bound to the simulation tick it belongs to."""

    tick: int
    payload: DirectReferencePayload | RouteCommandPayload

    def __post_init__(self) -> None:
        """Validate the binding tick and payload type."""
        object.__setattr__(self, "tick", _non_bool_int("tick", self.tick))
        if not isinstance(self.payload, (DirectReferencePayload, RouteCommandPayload)):
            raise TypeError(
                f"payload must be DirectReferencePayload or RouteCommandPayload, got {type(self.payload).__name__}"
            )


class TransportFailureCode(str, Enum):
    """Structured transport failure classes (Issue #64 AC2, SC-09, TS-17).

    Values mirror the shared facade ``FailureCode`` spellings where a fault can
    be cross-referenced; transport-only faults carry adapter-local spellings.
    """

    QOS_INCOMPATIBLE = "QOS_INCOMPATIBLE"
    FRESHNESS_EXPIRED = "FRESHNESS_EXPIRED"
    DUPLICATE_INPUT = "DUPLICATE_INPUT"
    STALE_INPUT = "STALE_INPUT"
    OUT_OF_ORDER_INPUT = "OUT_OF_ORDER_INPUT"
    PEER_RESET = "PEER_RESET"
    PEER_PROCESS_LOST = "PEER_PROCESS_LOST"
    INVALID_INPUT = "INVALID_INPUT"
    DEPENDENCY_UNAVAILABLE = "DEPENDENCY_UNAVAILABLE"


@dataclass(frozen=True)
class TransportFailure:
    """Structured transport failure with tick provenance and frozen details."""

    code: TransportFailureCode
    message: str
    tick: int
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate the failure tick and freeze details."""
        object.__setattr__(self, "tick", _non_bool_int("tick", self.tick))
        object.__setattr__(self, "details", _deep_freeze(self.details))


@dataclass(frozen=True)
class TickMaterialization:
    """One simulation tick's adapter outcome: a materialized command or a failure."""

    tick: int
    command: CommandInput | None = None
    failure: TransportFailure | None = None

    def __post_init__(self) -> None:
        """Require exactly one of command or failure and validate the tick."""
        object.__setattr__(self, "tick", _non_bool_int("tick", self.tick))
        if (self.command is None) == (self.failure is None):
            raise ValueError("materialization must carry exactly one of command or failure")


@runtime_checkable
class CommandTransport(Protocol):
    """Minimal transport seam: typed tick-indexed messages plus QoS and liveness."""

    @property
    def qos(self) -> TransportQos:
        """Return the QoS offered by the transport endpoint."""
        ...

    def poll(self, tick: int) -> TransportMessage | None:
        """Return the next message deliverable at simulation tick, or None."""
        ...

    @property
    def peer_process_lost(self) -> bool:
        """Return whether the publishing peer reported process loss."""
        ...

    @property
    def peer_reset_reported(self) -> bool:
        """Return whether the publishing peer reported a mid-stream reset."""
        ...


class ScriptedCommandTransport:
    """Deterministic in-memory scripted transport (the SIL surface of the seam).

    Events fire strictly when simulation time reaches them: ``poll(tick)``
    delivers the next scripted message whose delivery tick is at or before
    ``tick``, in script order.  Peer signals become observable from the tick
    they are scripted for and stay latched until :meth:`reset`.
    """

    def __init__(
        self,
        *,
        offered_qos: TransportQos,
        script: Mapping[int, Sequence[TransportMessage]],
        process_lost_from_tick: int | None = None,
        peer_reset_from_tick: int | None = None,
    ) -> None:
        """Freeze a delivery-ordered event list from the per-tick script."""
        self._offered_qos = offered_qos
        events: list[tuple[int, TransportMessage]] = []
        for delivery_tick in sorted(script):
            events.extend(
                (_non_bool_int("script delivery tick", delivery_tick), message) for message in script[delivery_tick]
            )
        self._events: tuple[tuple[int, TransportMessage], ...] = tuple(events)
        self._process_lost_from_tick = process_lost_from_tick
        self._peer_reset_from_tick = peer_reset_from_tick
        self._cursor = 0
        self._last_polled_tick = -1

    @property
    def qos(self) -> TransportQos:
        """Return the scripted offered QoS."""
        return self._offered_qos

    @property
    def peer_process_lost(self) -> bool:
        """Return whether simulation time has reached the scripted process-loss tick."""
        return self._process_lost_from_tick is not None and self._last_polled_tick >= self._process_lost_from_tick

    @property
    def peer_reset_reported(self) -> bool:
        """Return whether simulation time has reached the scripted peer-reset tick."""
        return self._peer_reset_from_tick is not None and self._last_polled_tick >= self._peer_reset_from_tick

    def poll(self, tick: int) -> TransportMessage | None:
        """Deliver the next event whose delivery tick is at or before the simulation tick."""
        polled = _non_bool_int("tick", tick)
        self._last_polled_tick = polled
        if self._cursor < len(self._events):
            delivery_tick, message = self._events[self._cursor]
            if delivery_tick <= polled:
                self._cursor += 1
                return message
        return None

    def reset(self) -> None:
        """Rewind the script and clear observed peer signals (episode restart)."""
        self._cursor = 0
        self._last_polled_tick = -1


def _ordering_violation(
    message_tick: int,
    last_accepted_tick: int | None,
    simulation_tick: int,
) -> TransportFailureCode | None:
    """Classify stream-order and simulation-time violations for one message."""
    if last_accepted_tick is not None:
        if message_tick == last_accepted_tick:
            return TransportFailureCode.DUPLICATE_INPUT
        if message_tick < last_accepted_tick:
            return TransportFailureCode.OUT_OF_ORDER_INPUT
    if message_tick < simulation_tick:
        return TransportFailureCode.STALE_INPUT
    if message_tick > simulation_tick:
        return TransportFailureCode.INVALID_INPUT
    return None


def _ordering_details(
    code: TransportFailureCode,
    message_tick: int,
    last_accepted_tick: int | None,
    simulation_tick: int,
) -> dict[str, int]:
    """Build the structured detail payload for one ordering violation."""
    if code is TransportFailureCode.DUPLICATE_INPUT:
        return {"duplicate_tick": message_tick}
    if code is TransportFailureCode.OUT_OF_ORDER_INPUT:
        return {"message_tick": message_tick, "last_accepted_tick": int(last_accepted_tick)}
    if code is TransportFailureCode.STALE_INPUT:
        return {"message_tick": message_tick, "simulation_tick": simulation_tick}
    return {"message_tick": message_tick, "simulation_tick": simulation_tick}


def _command_from_message(message: TransportMessage) -> CommandInput:
    """Materialize one typed message into a tick-indexed facade command."""
    payload = message.payload
    if isinstance(payload, RouteCommandPayload):
        route = TrackedRoute(
            route_id=payload.route_id,
            revision=payload.revision,
            accepted=True,
            valid_from_tick=message.tick,
            valid_until_tick=payload.valid_until_tick,
            waypoints_ne_m=np.array(payload.waypoints_ne_m, dtype=np.float64).T,
            speed_mps=np.array(payload.speed_mps, dtype=np.float64),
            task=ControlTask(payload.task),
        )
        return CommandInput.route(message.tick, route)
    reference = DirectReference(
        np.array(payload.values, dtype=np.float64),
        latched_tick=message.tick,
    )
    return CommandInput.direct(message.tick, reference)


@dataclass(frozen=True)
class RosCommandAdapterSnapshot:
    """Deterministic adapter-local translation state."""

    schema_version: str
    last_accepted_tick: int | None

    def __post_init__(self) -> None:
        """Validate the pinned snapshot schema."""
        if self.schema_version != _ADAPTER_SNAPSHOT_SCHEMA_VERSION:
            raise ValueError(f"unsupported snapshot schema_version: {self.schema_version}")


class RosCommandAdapter:
    """Materialize transport messages into tick-indexed typed facade inputs.

    The adapter holds no core reference: it cannot advance the stack.  Per tick
    it returns exactly one ``CommandInput`` or one structured ``TransportFailure``
    and never mutates state on a failing tick (atomic per-tick commit).
    """

    def __init__(
        self,
        transport: CommandTransport,
        *,
        requested_qos: TransportQos,
        freshness_horizon_ticks: int,
    ) -> None:
        """Bind a transport, record the QoS verdict, and validate the freshness window."""
        self._transport = transport
        self._freshness_horizon_ticks = _non_bool_int("freshness_horizon_ticks", freshness_horizon_ticks)
        if not is_qos_compatible(requested_qos, transport.qos):
            self._qos_failure = TransportFailure(
                code=TransportFailureCode.QOS_INCOMPATIBLE,
                message="requested QoS is not compatible with the offered transport QoS",
                tick=0,
                details={"requested": _qos_dict(requested_qos), "offered": _qos_dict(transport.qos)},
            )
        else:
            self._qos_failure = None
        self._last_accepted_tick: int | None = None

    def materialize(self, tick: int) -> TickMaterialization:
        """Drain deliverable messages for one simulation tick into a command or failure."""
        simulation_tick = _non_bool_int("tick", tick)
        if self._qos_failure is not None:
            return TickMaterialization(tick=simulation_tick, failure=self._qos_failure)

        accepted_command: CommandInput | None = None
        accepted_tick = self._last_accepted_tick
        failure: TransportFailure | None = None
        while failure is None:
            try:
                message = self._transport.poll(simulation_tick)
            except (TypeError, ValueError, AttributeError) as exc:
                failure = TransportFailure(
                    code=TransportFailureCode.INVALID_INPUT,
                    message=f"transport raised during poll: {exc}",
                    tick=simulation_tick,
                )
                break
            if self._transport.peer_process_lost:
                failure = TransportFailure(
                    code=TransportFailureCode.PEER_PROCESS_LOST,
                    message="transport peer process loss reported",
                    tick=simulation_tick,
                )
                break
            if self._transport.peer_reset_reported:
                failure = TransportFailure(
                    code=TransportFailureCode.PEER_RESET,
                    message="transport peer reported a mid-stream reset",
                    tick=simulation_tick,
                )
                break
            if message is None:
                break
            violation = _ordering_violation(message.tick, accepted_tick, simulation_tick)
            if violation is not None:
                failure = TransportFailure(
                    code=violation,
                    message=_ORDERING_MESSAGES[violation],
                    tick=simulation_tick,
                    details=_ordering_details(violation, message.tick, accepted_tick, simulation_tick),
                )
                break
            try:
                accepted_command = _command_from_message(message)
            except (TypeError, ValueError) as exc:
                failure = TransportFailure(
                    code=TransportFailureCode.INVALID_INPUT,
                    message=f"message payload failed typed materialization: {exc}",
                    tick=simulation_tick,
                    details={"message_tick": message.tick},
                )
                break
            accepted_tick = message.tick

        if failure is None and accepted_command is None:
            failure = self._freshness_failure(simulation_tick, accepted_tick)
        if failure is not None:
            return TickMaterialization(tick=simulation_tick, failure=failure)
        self._last_accepted_tick = accepted_tick
        if accepted_command is None:
            accepted_command = CommandInput.none(simulation_tick)
        return TickMaterialization(tick=simulation_tick, command=accepted_command)

    def _freshness_failure(self, simulation_tick: int, last_accepted_tick: int | None) -> TransportFailure | None:
        """Return the freshness failure for a silent stream, or None within the window."""
        if last_accepted_tick is None:
            if simulation_tick > self._freshness_horizon_ticks:
                return TransportFailure(
                    code=TransportFailureCode.FRESHNESS_EXPIRED,
                    message="no input ever accepted and the freshness window is exhausted",
                    tick=simulation_tick,
                    details={"freshness_horizon_ticks": self._freshness_horizon_ticks},
                )
            return None
        age = simulation_tick - last_accepted_tick
        if age > self._freshness_horizon_ticks:
            return TransportFailure(
                code=TransportFailureCode.FRESHNESS_EXPIRED,
                message="input stream silent beyond the freshness horizon",
                tick=simulation_tick,
                details={
                    "last_accepted_tick": last_accepted_tick,
                    "freshness_horizon_ticks": self._freshness_horizon_ticks,
                },
            )
        return None

    def reset(self) -> None:
        """Idempotently clear adapter stream state for a new episode."""
        self._last_accepted_tick = None

    def snapshot(self) -> RosCommandAdapterSnapshot:
        """Capture the complete adapter stream state."""
        return RosCommandAdapterSnapshot(
            schema_version=_ADAPTER_SNAPSHOT_SCHEMA_VERSION,
            last_accepted_tick=self._last_accepted_tick,
        )

    def restore(self, snapshot: RosCommandAdapterSnapshot) -> None:
        """Restore exact adapter stream state from a snapshot."""
        if not isinstance(snapshot, RosCommandAdapterSnapshot):
            raise TypeError(f"snapshot must be RosCommandAdapterSnapshot, got {type(snapshot).__name__}")
        if snapshot.schema_version != _ADAPTER_SNAPSHOT_SCHEMA_VERSION:
            raise ValueError(f"unsupported snapshot schema_version: {snapshot.schema_version}")
        self._last_accepted_tick = snapshot.last_accepted_tick


def _qos_dict(qos: TransportQos) -> dict[str, str | int]:
    """Return a JSON-safe QoS description."""
    return {"reliability": qos.reliability.value, "durability": qos.durability.value, "depth": qos.depth}


_ORDERING_MESSAGES: dict[TransportFailureCode, str] = {
    TransportFailureCode.DUPLICATE_INPUT: "duplicate simulation tick delivery",
    TransportFailureCode.OUT_OF_ORDER_INPUT: "message tick regressed below the last accepted tick",
    TransportFailureCode.STALE_INPUT: "message delivered after its simulation tick passed",
    TransportFailureCode.INVALID_INPUT: "message tick is ahead of the simulation tick",
}


@dataclass(frozen=True)
class SilTickRecord:
    """Per-tick harness evidence: tick, materialized authority, and navigation view."""

    tick: int
    authority: str
    navigation: tuple[float, ...]


@dataclass(frozen=True)
class SilRunResult:
    """Deterministic outcome of one harness run over a tick count.

    ``ticks_completed`` counts successful core steps; the failing tick of a
    terminated run is never counted, so the core never advances past it.
    """

    ticks_requested: int
    ticks_completed: int
    terminated_by: str | None
    transport_failures: tuple[TransportFailure, ...]
    facade_failures: tuple[FacadeFailure, ...]
    records: tuple[SilTickRecord, ...]
    digest: str

    def __post_init__(self) -> None:
        """Validate the termination discriminant."""
        if self.terminated_by not in {None, "transport_failure", "facade_failure"}:
            raise ValueError(f"invalid terminated_by value: {self.terminated_by!r}")


@dataclass(frozen=True)
class SilHarnessSnapshot:
    """Harness restoration bundle: facade snapshot plus adapter snapshot."""

    stack_snapshot: StackSnapshot
    adapter_snapshot: RosCommandAdapterSnapshot


def _records_digest(records: Sequence[SilTickRecord]) -> str:
    """Hash the per-tick records into one deterministic digest."""
    payload = {
        "records": [
            {"tick": record.tick, "authority": record.authority, "navigation": list(record.navigation)}
            for record in records
        ]
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class SilHarness:
    """Simulation-time SIL loop: the single caller that advances the core.

    Each run iteration reads the stack's integer tick (the only simulation-time
    authority), materializes the adapter input for that tick, and steps the
    stack exactly once.  Transport or facade failures terminate the run without
    advancing the core past the failing tick; a terminated harness requires an
    explicit :meth:`reset` before another run.
    """

    def __init__(self, stack: ModularShipStack, adapter: RosCommandAdapter, *, dt_s: float) -> None:
        """Bind the facade and adapter and validate the fixed tick period."""
        self._stack = stack
        self._adapter = adapter
        dt = float(dt_s)
        if not math.isfinite(dt) or dt <= 0.0:
            raise ValueError("dt_s must be finite and positive")
        self._dt_s = dt
        self._terminated = False

    def run(self, ticks: int) -> SilRunResult:
        """Advance at most ``ticks`` simulation ticks, terminating on the first failure."""
        if self._terminated:
            raise RuntimeError(_HARNESS_TERMINATED_MESSAGE)
        requested = _non_bool_int("ticks", ticks)
        records: list[SilTickRecord] = []
        transport_failures: list[TransportFailure] = []
        facade_failures: list[FacadeFailure] = []
        terminated_by: str | None = None
        for _ in range(requested):
            tick = self._stack.tick
            materialization = self._adapter.materialize(tick)
            if materialization.failure is not None:
                transport_failures.append(materialization.failure)
                terminated_by = "transport_failure"
                break
            output = self._stack.step(materialization.command, self._dt_s)
            if output.failure is not None:
                facade_failures.append(output.failure)
                terminated_by = "facade_failure"
                break
            navigation = output.navigation
            records.append(
                SilTickRecord(
                    tick=tick,
                    authority=materialization.command.authority,
                    navigation=(
                        navigation.north_m,
                        navigation.east_m,
                        navigation.heading_rad,
                        navigation.surge_mps,
                        navigation.sway_mps,
                        navigation.yaw_rate_radps,
                    ),
                )
            )
        if terminated_by is not None:
            self._terminated = True
        return SilRunResult(
            ticks_requested=requested,
            ticks_completed=len(records),
            terminated_by=terminated_by,
            transport_failures=tuple(transport_failures),
            facade_failures=tuple(facade_failures),
            records=tuple(records),
            digest=_records_digest(records),
        )

    def reset(self, navigation: NavigationState, seed: int) -> None:
        """Idempotently restart the episode: facade, adapter, and termination latch."""
        self._stack.reset(navigation, int(seed))
        self._adapter.reset()
        self._terminated = False

    def snapshot(self) -> SilHarnessSnapshot:
        """Capture the complete harness-owned restoration bundle."""
        return SilHarnessSnapshot(
            stack_snapshot=self._stack.snapshot(),
            adapter_snapshot=self._adapter.snapshot(),
        )

    def restore(self, snapshot: SilHarnessSnapshot) -> None:
        """Restore facade and adapter state from a harness snapshot."""
        if not isinstance(snapshot, SilHarnessSnapshot):
            raise TypeError(f"snapshot must be SilHarnessSnapshot, got {type(snapshot).__name__}")
        self._stack.restore(snapshot.stack_snapshot)
        self._adapter.restore(snapshot.adapter_snapshot)
        self._terminated = False


@dataclass(frozen=True)
class RosTransportAvailability:
    """Structured availability status of the real rclpy transport dependency."""

    available: bool
    failure_code: TransportFailureCode | None
    detail: str | None


class RosTransportUnavailableError(RuntimeError):
    """Raised when the real ROS 2 transport is constructed without rclpy installed."""

    def __init__(self, status: RosTransportAvailability) -> None:
        """Carry the structured availability status on the exception."""
        super().__init__(status.detail or "rclpy is not available")
        self.status = status


def ros2_transport_status() -> RosTransportAvailability:
    """Probe rclpy availability without importing it into the module namespace."""
    try:
        import rclpy  # noqa: F401, PLC0415
    except ImportError as exc:
        return RosTransportAvailability(
            available=False,
            failure_code=TransportFailureCode.DEPENDENCY_UNAVAILABLE,
            detail=f"rclpy import failed: {exc}",
        )
    return RosTransportAvailability(available=True, failure_code=None, detail=None)


def _rclpy_qos_profile(qos: TransportQos) -> Any:
    """Translate a typed TransportQos into an rclpy QoSProfile (rclpy-present only)."""
    from rclpy.qos import QoSDurabilityPolicy, QoSProfile, QoSReliabilityPolicy  # noqa: PLC0415

    reliability = (
        QoSReliabilityPolicy.RELIABLE
        if qos.reliability is QosReliability.RELIABLE
        else QoSReliabilityPolicy.BEST_EFFORT
    )
    durability = (
        QoSDurabilityPolicy.TRANSIENT_LOCAL
        if qos.durability is QosDurability.TRANSIENT_LOCAL
        else QoSDurabilityPolicy.VOLATILE
    )
    return QoSProfile(reliability=reliability, durability=durability, depth=qos.depth)


class Ros2CommandTransport:
    """Real rclpy binding of the transport seam (peripheral, optional dependency).

    The caller owns the rclpy context and node lifecycle; this class only
    creates the subscription and converts delivered messages through the
    caller-supplied ``message_adapter`` into typed tick-indexed messages.
    Constructing without rclpy installed raises the structured
    :class:`RosTransportUnavailableError` (never a crash, never a fallback).
    DDS liveness reporting (peer process loss and peer reset) is deferred; the
    SIL semantics for those classes are exercised via ``ScriptedCommandTransport``
    behind the same seam.
    """

    def __init__(
        self,
        *,
        node: Any,
        topic: str,
        msg_type: Any,
        message_adapter: Callable[[Any], TransportMessage],
        offered_qos: TransportQos,
    ) -> None:
        """Gate on rclpy availability, then create the subscription on the caller node."""
        status = ros2_transport_status()
        if not status.available:
            raise RosTransportUnavailableError(status)
        if node is None:
            raise ValueError("node must be a constructed rclpy node owned by the caller")
        if msg_type is None:
            raise ValueError("msg_type must be a ROS 2 message class supplied by the integrator")
        if not callable(message_adapter):
            raise TypeError("message_adapter must convert delivered ROS messages into TransportMessage")
        self._topic = _non_empty_str("topic", topic)
        self._offered_qos = offered_qos
        self._message_adapter = message_adapter
        self._pending: deque[TransportMessage] = deque()
        # Retained on the instance: an unreferenced subscription is garbage-collected by rclpy.
        self._subscription = node.create_subscription(msg_type, topic, self._on_message, _rclpy_qos_profile(offered_qos))

    def _on_message(self, message: Any) -> None:
        """Queue one converted transport message (subscription callback)."""
        self._pending.append(self._message_adapter(message))

    @property
    def qos(self) -> TransportQos:
        """Return the offered QoS of this transport endpoint."""
        return self._offered_qos

    @property
    def peer_process_lost(self) -> bool:
        """Return False: DDS liveness reporting is deferred to a ROS-present slice."""
        return False

    @property
    def peer_reset_reported(self) -> bool:
        """Return False: DDS liveness reporting is deferred to a ROS-present slice."""
        return False

    def poll(self, tick: int) -> TransportMessage | None:  # noqa: ARG002
        """Return the oldest queued message, or None when nothing has been delivered."""
        return self._pending.popleft() if self._pending else None


def _sil_stack() -> ModularShipStack:
    """Build a reset pass-through legacy-equivalent stack for gate checks."""
    from colav_simulator.modular_gnc.configuration import normalize_ship_modules  # noqa: PLC0415
    from colav_simulator.modular_gnc.factory import legacy_equivalent_profile  # noqa: PLC0415

    stack = ModularShipStack.from_config(normalize_ship_modules(legacy_equivalent_profile()))
    stack.reset(NavigationState(0.0, 0.0, 0.0, 0.0, 0.0, 0.0), seed=7)
    return stack


def _gate_qos() -> TransportQos:
    """Return the standard compatible offered/requested QoS used by gate checks."""
    return TransportQos(reliability=QosReliability.RELIABLE, durability=QosDurability.TRANSIENT_LOCAL, depth=8)


def _gate_transport(
    script: Mapping[int, Sequence[TransportMessage]],
    *,
    process_lost_from_tick: int | None = None,
    peer_reset_from_tick: int | None = None,
) -> ScriptedCommandTransport:
    """Build the standard scripted transport used by gate checks."""
    return ScriptedCommandTransport(
        offered_qos=_gate_qos(),
        script=script,
        process_lost_from_tick=process_lost_from_tick,
        peer_reset_from_tick=peer_reset_from_tick,
    )


def _gate_adapter(
    transport: ScriptedCommandTransport,
    *,
    freshness_horizon_ticks: int = 16,
) -> RosCommandAdapter:
    """Build the standard adapter used by gate checks."""
    return RosCommandAdapter(
        transport,
        requested_qos=_gate_qos(),
        freshness_horizon_ticks=freshness_horizon_ticks,
    )


def _gate_harness(
    script: Mapping[int, Sequence[TransportMessage]],
    *,
    freshness_horizon_ticks: int = 16,
    process_lost_from_tick: int | None = None,
    peer_reset_from_tick: int | None = None,
) -> SilHarness:
    """Build a harness over a scripted transport for one gate check."""
    transport = _gate_transport(
        script,
        process_lost_from_tick=process_lost_from_tick,
        peer_reset_from_tick=peer_reset_from_tick,
    )
    return SilHarness(_sil_stack(), _gate_adapter(transport, freshness_horizon_ticks=freshness_horizon_ticks), dt_s=0.2)


def _gate_route_message(tick: int, *, valid_until_tick: int = 64, route_id: str = "g10-route") -> TransportMessage:
    """Build a deterministic route message for gate scripts."""
    return TransportMessage(
        tick=tick,
        payload=RouteCommandPayload(
            route_id=route_id,
            revision=0,
            waypoints_ne_m=((0.0, 0.0), (800.0, 0.0)),
            speed_mps=(2.0, 2.0),
            task=ControlTask.TRANSIT,
            valid_until_tick=valid_until_tick,
        ),
    )


def _gate_reference_message(tick: int, *, course: float) -> TransportMessage:
    """Build a deterministic direct-reference message for gate scripts."""
    return TransportMessage(
        tick=tick,
        payload=DirectReferencePayload(values=(0.0, 0.0, course, 3.0, 0.0, 0.0, 0.0, 0.0, 0.0)),
    )


_GATE_SCRIPT: dict[int, list[TransportMessage]] = {
    0: [_gate_route_message(0)],
    3: [_gate_reference_message(3, course=0.5)],
    6: [_gate_route_message(6, route_id="g10-route-2")],
}


def _g10_determinism_check() -> GateCheck:
    """Check: the scripted SIL run is deterministic across identical builds."""
    first = _gate_harness(_GATE_SCRIPT).run(9)
    second = _gate_harness(_GATE_SCRIPT).run(9)
    passed = (
        first.terminated_by is None
        and second.terminated_by is None
        and first.ticks_completed == 9
        and first.digest == second.digest
    )
    return GateCheck(
        name="scripted simulation-time SIL run completes with a deterministic digest",
        passed=passed,
        observed={"digest": first.digest[:16], "ticks_completed": first.ticks_completed},
    )


def _g10_failure_class_check(
    check_name: str,
    expected_code: TransportFailureCode,
    *,
    script: Mapping[int, Sequence[TransportMessage]],
    expected_completed: int,
    freshness_horizon_ticks: int = 16,
    process_lost_from_tick: int | None = None,
    peer_reset_from_tick: int | None = None,
) -> GateCheck:
    """Check: one scripted transport fault surfaces as exactly its failure class."""
    harness = _gate_harness(
        script,
        freshness_horizon_ticks=freshness_horizon_ticks,
        process_lost_from_tick=process_lost_from_tick,
        peer_reset_from_tick=peer_reset_from_tick,
    )
    result = harness.run(6)
    passed = (
        result.terminated_by == "transport_failure"
        and result.ticks_completed == expected_completed
        and len(result.transport_failures) == 1
        and result.transport_failures[0].code is expected_code
        and result.facade_failures == ()
    )
    return GateCheck(
        name=check_name,
        passed=passed,
        observed={
            "expected_code": expected_code.value,
            "observed_code": (
                result.transport_failures[0].code.value if result.transport_failures else None
            ),
            "ticks_completed": result.ticks_completed,
        },
    )


def _g10_qos_incompatibility_check() -> GateCheck:
    """Check: QoS incompatibility surfaces without advancing or consuming the core."""
    transport = ScriptedCommandTransport(
        offered_qos=TransportQos(reliability=QosReliability.BEST_EFFORT, durability=QosDurability.VOLATILE, depth=4),
        script={0: [_gate_route_message(0)]},
    )
    adapter = RosCommandAdapter(
        transport,
        requested_qos=_gate_qos(),
        freshness_horizon_ticks=16,
    )
    harness = SilHarness(_sil_stack(), adapter, dt_s=0.2)
    result = harness.run(3)
    passed = (
        result.terminated_by == "transport_failure"
        and result.ticks_completed == 0
        and len(result.transport_failures) == 1
        and result.transport_failures[0].code is TransportFailureCode.QOS_INCOMPATIBLE
    )
    return GateCheck(
        name="QoS incompatibility surfaces without advancing the core",
        passed=passed,
        observed={"ticks_completed": result.ticks_completed},
    )


def _g10_snapshot_replay_check() -> GateCheck:
    """Check: snapshot/restore continuation reproduces the straight-through records."""
    straight = _gate_harness(_GATE_SCRIPT).run(9)
    prefix_harness = _gate_harness(_GATE_SCRIPT)
    prefix = prefix_harness.run(4)
    snapshot = prefix_harness.snapshot()

    resumed_transport = _gate_transport(_GATE_SCRIPT)
    resumed_harness = SilHarness(_sil_stack(), _gate_adapter(resumed_transport), dt_s=0.2)
    resumed_harness.restore(snapshot)
    for tick in range(4):
        while resumed_transport.poll(tick) is not None:
            pass
    resumed = resumed_harness.run(5)

    combined = prefix.records + resumed.records
    passed = (
        prefix.terminated_by is None
        and resumed.terminated_by is None
        and len(combined) == len(straight.records)
        and all(a == b for a, b in zip(combined, straight.records, strict=True))
    )
    return GateCheck(
        name="snapshot/restore replay reproduces the straight-through tick records",
        passed=passed,
        observed={"records": len(combined), "straight_records": len(straight.records)},
    )


def _g10_wall_clock_exclusion_check() -> GateCheck:
    """Check: the harness advances the core only from simulation ticks, never wall time."""
    from unittest import mock  # noqa: PLC0415

    script = {tick: [_gate_route_message(tick)] for tick in range(5)}
    adapter = _gate_adapter(_gate_transport(script))

    def _forbidden(*_args: object, **_kwargs: object) -> float:
        raise AssertionError("wall clock must not drive simulation-time SIL")

    with (
        mock.patch.object(time, "time", _forbidden),
        mock.patch.object(time, "monotonic", _forbidden),
        mock.patch.object(time, "perf_counter", _forbidden),
    ):
        result = SilHarness(_sil_stack(), adapter, dt_s=0.2).run(5)
    peripheral = not hasattr(adapter, "step") and not hasattr(adapter, "advance")
    passed = result.terminated_by is None and result.ticks_completed == 5 and peripheral
    return GateCheck(
        name="core advances only from simulation ticks with wall clock excluded",
        passed=passed,
        observed={"ticks_completed": result.ticks_completed, "peripheral_audit": peripheral},
    )


def _g10_import_hygiene_check() -> GateCheck:
    """Check: legacy, core, and adapter modules import without pulling in rclpy."""
    code = (
        "import sys;"
        "import colav_simulator.core.ship;"
        "import colav_simulator.modular_gnc.stack;"
        "import colav_simulator.modular_gnc.ros_adapter;"
        "ros_modules = [m for m in sys.modules if m == 'rclpy' or m.startswith('rclpy.')];"
        "sys.exit(f'ros modules imported: {ros_modules}' if ros_modules else 0)"
    )
    try:
        completed = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            cwd=Path(__file__).resolve().parents[2],
            timeout=120,
            check=False,
        )
        passed = completed.returncode == 0
        observed: str | int = completed.stdout + completed.stderr if not passed else "clean"
    except (OSError, subprocess.SubprocessError) as exc:
        passed = False
        observed = str(exc)
    return GateCheck(
        name="legacy, core, and adapter import without ROS modules installed",
        passed=passed,
        observed=observed,
    )


def _g10_dependency_status_check() -> GateCheck:
    """Check: the rclpy dependency status is a structured value in any environment."""
    status = ros2_transport_status()
    if status.available:
        structured = status.failure_code is None
    else:
        structured = (
            status.failure_code is TransportFailureCode.DEPENDENCY_UNAVAILABLE and bool(status.detail)
        )
    return GateCheck(
        name="ROS 2 transport dependency status is structured, never a silent fallback",
        passed=structured,
        observed={
            "available": status.available,
            "failure_code": status.failure_code.value if status.failure_code is not None else None,
        },
    )


def run_g10_gate() -> G10SilReport:
    """Run the local G10 checks and return the three-state, separately-reported gate."""
    checks = (
        _g10_determinism_check(),
        _g10_qos_incompatibility_check(),
        _g10_failure_class_check(
            "duplicate tick delivery surfaces DUPLICATE_INPUT",
            TransportFailureCode.DUPLICATE_INPUT,
            script={2: [_gate_route_message(2), _gate_route_message(2)]},
            expected_completed=2,
        ),
        _g10_failure_class_check(
            "tick regression surfaces OUT_OF_ORDER_INPUT",
            TransportFailureCode.OUT_OF_ORDER_INPUT,
            script={3: [_gate_route_message(3)], 5: [_gate_route_message(1)]},
            expected_completed=5,
        ),
        _g10_failure_class_check(
            "late delivery surfaces STALE_INPUT",
            TransportFailureCode.STALE_INPUT,
            script={3: [_gate_route_message(3)], 5: [_gate_route_message(4)]},
            expected_completed=5,
        ),
        _g10_failure_class_check(
            "input-stream silence beyond the freshness horizon surfaces FRESHNESS_EXPIRED",
            TransportFailureCode.FRESHNESS_EXPIRED,
            script={0: [_gate_route_message(0)]},
            expected_completed=3,
            freshness_horizon_ticks=2,
        ),
        _g10_failure_class_check(
            "peer process loss surfaces PEER_PROCESS_LOST and halts core advance",
            TransportFailureCode.PEER_PROCESS_LOST,
            script={0: [_gate_route_message(0)], 1: [_gate_route_message(1)]},
            expected_completed=2,
            process_lost_from_tick=2,
        ),
        _g10_failure_class_check(
            "peer reset surfaces PEER_RESET",
            TransportFailureCode.PEER_RESET,
            script={0: [_gate_route_message(0)]},
            expected_completed=1,
            peer_reset_from_tick=1,
        ),
        _g10_snapshot_replay_check(),
        _g10_wall_clock_exclusion_check(),
        _g10_import_hygiene_check(),
        _g10_dependency_status_check(),
    )
    gate = GateResult(
        gate_id="G10",
        name="external platform adapter integration (simulation-time SIL)",
        status="passed" if all(check.passed for check in checks) else "failed",
        evidence_class="system",
        checks=checks,
    )
    return G10SilReport(
        schema_version=G10_REPORT_SCHEMA_VERSION,
        claim_ceiling=G10_CLAIM_CEILING,
        claim_ceiling_label=G10_CLAIM_CEILING_LABEL,
        gate=gate,
        availability=ros2_transport_status(),
        non_claims=G10_NON_CLAIMS,
    )


@dataclass(frozen=True)
class G10SilReport:
    """Separately-reported G10 gate verdict with explicit non-claims (VR-24, TS-29)."""

    schema_version: str
    claim_ceiling: str
    claim_ceiling_label: str
    gate: GateResult
    availability: RosTransportAvailability
    non_claims: tuple[str, ...]

    def __post_init__(self) -> None:
        """Validate the pinned report schema and claim ceiling."""
        if self.schema_version != G10_REPORT_SCHEMA_VERSION:
            raise ValueError(f"unsupported report schema_version: {self.schema_version}")
        if self.claim_ceiling != "A3":
            raise ValueError("G10 SIL evidence stays at the A3 claim ceiling; no A6 claim is permitted")

    def to_dict(self) -> dict[str, Any]:
        """Convert the report to a JSON-serializable dictionary."""
        return {
            "schema_version": self.schema_version,
            "claim_ceiling": self.claim_ceiling,
            "claim_ceiling_label": self.claim_ceiling_label,
            "gate": self.gate.to_dict(),
            "availability": {
                "available": self.availability.available,
                "failure_code": (
                    self.availability.failure_code.value if self.availability.failure_code is not None else None
                ),
                "detail": self.availability.detail,
            },
            "non_claims": list(self.non_claims),
        }
