"""Optional ROS 2 adapter and simulation-time SIL harness (Issue #64).

All adapter semantics are exercised through the deterministic in-memory
``ScriptedCommandTransport`` behind the transport seam; the real rclpy binding
is only exercised when rclpy is importable and skips cleanly otherwise
(no ROS 2 installation on this machine is itself the AC4 test condition).
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from unittest import mock

import numpy as np
import pytest

from colav_simulator.modular_gnc.a3_demo import GateResult
from colav_simulator.modular_gnc.contracts import (
    CommandInput,
    ControlTask,
    FailureCode,
    NavigationState,
)
from colav_simulator.modular_gnc.factory import legacy_equivalent_profile
from colav_simulator.modular_gnc.ros_adapter import (
    DirectReferencePayload,
    G10SilReport,
    QosDurability,
    QosReliability,
    Ros2CommandTransport,
    RosCommandAdapter,
    RosTransportUnavailableError,
    RouteCommandPayload,
    ScriptedCommandTransport,
    SilHarness,
    SilHarnessSnapshot,
    TransportFailureCode,
    TransportMessage,
    TransportQos,
    is_qos_compatible,
    ros2_transport_status,
    run_g10_gate,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _offered_qos() -> TransportQos:
    return TransportQos(
        reliability=QosReliability.RELIABLE,
        durability=QosDurability.TRANSIENT_LOCAL,
        depth=8,
    )


def _route_message(tick: int, *, valid_until_tick: int = 64, route_id: str = "ros-route") -> TransportMessage:
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


def _reference_message(tick: int, *, course: float = 0.2, speed: float = 3.0) -> TransportMessage:
    return TransportMessage(
        tick=tick,
        payload=DirectReferencePayload(values=(0.0, 0.0, course, speed, 0.0, 0.0, 0.0, 0.0, 0.0)),
    )


def _transport(
    script: dict[int, list[TransportMessage]],
    *,
    offered_qos: TransportQos | None = None,
    process_lost_from_tick: int | None = None,
    peer_reset_from_tick: int | None = None,
) -> ScriptedCommandTransport:
    return ScriptedCommandTransport(
        offered_qos=offered_qos if offered_qos is not None else _offered_qos(),
        script=script,
        process_lost_from_tick=process_lost_from_tick,
        peer_reset_from_tick=peer_reset_from_tick,
    )


def _adapter(
    transport: ScriptedCommandTransport,
    *,
    requested_qos: TransportQos | None = None,
    freshness_horizon_ticks: int = 3,
) -> RosCommandAdapter:
    return RosCommandAdapter(
        transport,
        requested_qos=requested_qos if requested_qos is not None else _offered_qos(),
        freshness_horizon_ticks=freshness_horizon_ticks,
    )


def _stack() -> Any:
    from colav_simulator.modular_gnc.configuration import normalize_ship_modules  # noqa: PLC0415
    from colav_simulator.modular_gnc.stack import ModularShipStack  # noqa: PLC0415

    stack = ModularShipStack.from_config(normalize_ship_modules(legacy_equivalent_profile()))
    stack.reset(NavigationState(0.0, 0.0, 0.0, 0.0, 0.0, 0.0), seed=7)
    return stack


def _harness(
    transport: ScriptedCommandTransport,
    *,
    requested_qos: TransportQos | None = None,
    freshness_horizon_ticks: int = 3,
    dt_s: float = 0.2,
) -> SilHarness:
    return SilHarness(
        _stack(),
        _adapter(
            transport,
            requested_qos=requested_qos,
            freshness_horizon_ticks=freshness_horizon_ticks,
        ),
        dt_s=dt_s,
    )


# ---------------------------------------------------------------------------
# QoS description and compatibility
# ---------------------------------------------------------------------------


def test_transport_qos_validates_depth_and_members() -> None:
    with pytest.raises(ValueError, match="depth"):
        TransportQos(QosReliability.RELIABLE, QosDurability.VOLATILE, depth=0)
    with pytest.raises(ValueError):
        TransportQos("NOT_A_POLICY", QosDurability.VOLATILE, depth=1)


def test_qos_compatibility_follows_request_offered_monotonicity() -> None:
    reliable_transient = TransportQos(QosReliability.RELIABLE, QosDurability.TRANSIENT_LOCAL, depth=1)
    best_effort_volatile = TransportQos(QosReliability.BEST_EFFORT, QosDurability.VOLATILE, depth=1)
    best_effort_transient = TransportQos(QosReliability.BEST_EFFORT, QosDurability.TRANSIENT_LOCAL, depth=1)
    reliable_volatile = TransportQos(QosReliability.RELIABLE, QosDurability.VOLATILE, depth=1)

    assert is_qos_compatible(reliable_transient, reliable_transient)
    assert is_qos_compatible(best_effort_volatile, reliable_transient)
    assert is_qos_compatible(best_effort_transient, reliable_transient)
    assert not is_qos_compatible(reliable_transient, best_effort_volatile)
    assert not is_qos_compatible(reliable_volatile, best_effort_transient)
    assert not is_qos_compatible(reliable_transient, reliable_volatile)


# ---------------------------------------------------------------------------
# Typed transport messages
# ---------------------------------------------------------------------------


def test_transport_message_and_payloads_validate_typed_content() -> None:
    with pytest.raises(ValueError):
        TransportMessage(tick=-1, payload=_reference_message(0).payload)
    with pytest.raises(ValueError):
        DirectReferencePayload(values=(0.0, 0.0, 0.1))
    with pytest.raises(ValueError):
        DirectReferencePayload(values=tuple([float("nan")] * 9))
    with pytest.raises(ValueError):
        RouteCommandPayload(
            route_id="r",
            revision=0,
            waypoints_ne_m=((0.0, 0.0),),
            speed_mps=(2.0,),
            task=ControlTask.TRANSIT,
            valid_until_tick=1,
        )
    with pytest.raises(ValueError):
        RouteCommandPayload(
            route_id="r",
            revision=0,
            waypoints_ne_m=((0.0, 0.0), (1.0, 1.0)),
            speed_mps=(2.0,),
            task=ControlTask.TRANSIT,
            valid_until_tick=1,
        )


def test_scripted_transport_polls_script_in_order_and_supports_rewind() -> None:
    transport = _transport({0: [_route_message(0)], 2: [_reference_message(2), _route_message(2)]})

    assert transport.qos == _offered_qos()
    assert not transport.peer_process_lost
    assert not transport.peer_reset_reported
    assert transport.poll(0) == _route_message(0)
    assert transport.poll(0) is None
    assert transport.poll(1) is None
    assert transport.poll(2) == _reference_message(2)
    assert transport.poll(2) == _route_message(2)
    assert transport.poll(2) is None

    transport.reset()
    assert transport.poll(0) == _route_message(0)


def test_scripted_transport_reports_process_loss_and_peer_reset_from_ticks() -> None:
    lost = _transport({}, process_lost_from_tick=4)
    assert not lost.peer_process_lost
    lost.poll(3)
    assert not lost.peer_process_lost
    lost.poll(4)
    assert lost.peer_process_lost

    reset = _transport({}, peer_reset_from_tick=2)
    reset.poll(1)
    assert not reset.peer_reset_reported
    reset.poll(2)
    assert reset.peer_reset_reported


# ---------------------------------------------------------------------------
# Adapter materialization: one structured failure class per transport fault
# ---------------------------------------------------------------------------


def test_materializes_route_payload_into_tick_indexed_command() -> None:
    adapter = _adapter(_transport({0: [_route_message(0)]}))

    materialization = adapter.materialize(0)

    assert materialization.failure is None
    assert materialization.command is not None
    assert materialization.command.tick == 0
    assert materialization.command.authority == "TRACKED_ROUTE"
    route = materialization.command.tracked_route
    assert route is not None
    assert route.route_id == "ros-route"
    assert route.accepted
    assert route.valid_from_tick == 0
    assert route.valid_until_tick == 64
    assert np.array_equal(route.waypoints_ne_m, np.array([[0.0, 800.0], [0.0, 0.0]]))
    assert np.array_equal(route.speed_mps, np.array([2.0, 2.0]))


def test_materializes_direct_reference_payload_with_latched_tick_binding() -> None:
    adapter = _adapter(_transport({1: [_reference_message(1, course=0.4, speed=2.5)]}))

    materialization = adapter.materialize(1)

    assert materialization.command is not None
    assert materialization.command.authority == "DIRECT_REFERENCE"
    reference = materialization.command.direct_reference
    assert reference is not None
    assert reference.latched_tick == 1
    assert reference.values[2] == 0.4
    assert reference.values[3] == 2.5


def test_emits_explicit_none_hold_between_messages_within_freshness() -> None:
    adapter = _adapter(_transport({0: [_route_message(0)]}), freshness_horizon_ticks=2)

    first = adapter.materialize(0)
    hold = adapter.materialize(1)

    assert first.command is not None
    assert hold.failure is None
    assert hold.command is not None
    assert hold.command.authority == "NONE"
    assert hold.command.tick == 1


def test_duplicate_delivery_fails_structurally() -> None:
    adapter = _adapter(_transport({2: [_route_message(2), _route_message(2)]}))

    materialization = adapter.materialize(2)

    assert materialization.command is None
    assert materialization.failure is not None
    assert materialization.failure.code is TransportFailureCode.DUPLICATE_INPUT
    assert materialization.failure.tick == 2


def test_out_of_order_regression_fails_structurally() -> None:
    adapter = _adapter(_transport({3: [_route_message(3)], 5: [_route_message(1)]}), freshness_horizon_ticks=16)
    assert adapter.materialize(0).failure is None
    assert adapter.materialize(3).command is not None

    materialization = adapter.materialize(5)

    assert materialization.failure is not None
    assert materialization.failure.code is TransportFailureCode.OUT_OF_ORDER_INPUT
    assert materialization.failure.details["last_accepted_tick"] == 3


def test_late_delivery_fails_stale() -> None:
    adapter = _adapter(_transport({3: [_route_message(3)], 5: [_route_message(4)]}), freshness_horizon_ticks=16)
    assert adapter.materialize(3).command is not None

    materialization = adapter.materialize(5)

    assert materialization.failure is not None
    assert materialization.failure.code is TransportFailureCode.STALE_INPUT
    assert materialization.failure.details["message_tick"] == 4


def test_future_dated_message_fails_invalid_against_simulation_tick() -> None:
    adapter = _adapter(_transport({1: [_route_message(4)]}))

    materialization = adapter.materialize(1)

    assert materialization.failure is not None
    assert materialization.failure.code is TransportFailureCode.INVALID_INPUT
    assert materialization.failure.details["simulation_tick"] == 1


def test_stream_silence_beyond_freshness_horizon_fails_freshness() -> None:
    adapter = _adapter(_transport({0: [_route_message(0)]}), freshness_horizon_ticks=2)
    assert adapter.materialize(0).command is not None
    assert adapter.materialize(1).failure is None
    assert adapter.materialize(2).failure is None

    expired = adapter.materialize(3)

    assert expired.command is None
    assert expired.failure is not None
    assert expired.failure.code is TransportFailureCode.FRESHNESS_EXPIRED
    assert expired.failure.details["last_accepted_tick"] == 0


def test_never_fresh_stream_fails_freshness_after_horizon() -> None:
    adapter = _adapter(_transport({}), freshness_horizon_ticks=1)
    assert adapter.materialize(0).failure is None

    expired = adapter.materialize(2)

    assert expired.failure is not None
    assert expired.failure.code is TransportFailureCode.FRESHNESS_EXPIRED


def test_qos_incompatibility_fails_without_advancing_or_consuming() -> None:
    transport = _transport({0: [_route_message(0)]}, offered_qos=TransportQos(
        QosReliability.BEST_EFFORT, QosDurability.VOLATILE, depth=4
    ))
    adapter = _adapter(transport)

    first = adapter.materialize(0)
    second = adapter.materialize(1)

    assert first.failure is not None
    assert first.failure.code is TransportFailureCode.QOS_INCOMPATIBLE
    assert second.failure is not None
    assert second.failure.code is TransportFailureCode.QOS_INCOMPATIBLE
    assert transport.poll(9) == _route_message(0)


def test_transport_exception_during_poll_fails_invalid_input() -> None:
    class BrokenTransport:
        qos = _offered_qos()
        peer_process_lost = False
        peer_reset_reported = False

        def poll(self, tick: int) -> TransportMessage | None:
            raise ValueError("malformed wire payload")

    adapter = _adapter(BrokenTransport())  # type: ignore[arg-type]

    materialization = adapter.materialize(0)

    assert materialization.failure is not None
    assert materialization.failure.code is TransportFailureCode.INVALID_INPUT


def test_peer_process_loss_fails_structurally_after_last_good_tick() -> None:
    adapter = _adapter(
        _transport({0: [_route_message(0)], 1: [_route_message(1)]}, process_lost_from_tick=2),
        freshness_horizon_ticks=16,
    )
    assert adapter.materialize(0).command is not None
    assert adapter.materialize(1).command is not None

    materialization = adapter.materialize(2)

    assert materialization.command is None
    assert materialization.failure is not None
    assert materialization.failure.code is TransportFailureCode.PEER_PROCESS_LOST


def test_peer_reset_fails_structurally() -> None:
    adapter = _adapter(_transport({0: [_route_message(0)]}, peer_reset_from_tick=1), freshness_horizon_ticks=16)
    assert adapter.materialize(0).command is not None

    materialization = adapter.materialize(1)

    assert materialization.failure is not None
    assert materialization.failure.code is TransportFailureCode.PEER_RESET


def test_adapter_reset_is_idempotent_and_replays_first_tick() -> None:
    transport = _transport({0: [_route_message(0)]})
    adapter = _adapter(transport, freshness_horizon_ticks=16)
    assert adapter.materialize(0).command is not None

    adapter.reset()
    adapter.reset()
    transport.reset()

    replayed = adapter.materialize(0)
    assert replayed.failure is None
    assert replayed.command is not None
    assert replayed.command.tick == 0


def test_adapter_snapshot_restore_preserves_stream_order_state() -> None:
    transport = _transport({0: [_route_message(0)], 2: [_route_message(2)]})
    adapter = _adapter(transport, freshness_horizon_ticks=16)
    assert adapter.materialize(0).command is not None
    snapshot = adapter.snapshot()

    assert adapter.materialize(2).command is not None
    adapter.restore(snapshot)
    transport.reset()
    transport.poll(0)

    replayed = adapter.materialize(2)
    assert replayed.failure is None
    assert replayed.command is not None
    assert replayed.command.tick == 2


# ---------------------------------------------------------------------------
# SIL harness: simulation-time ownership and deterministic replay
# ---------------------------------------------------------------------------


def test_harness_clean_run_is_deterministic_and_sensitive_to_script() -> None:
    def build() -> SilHarness:
        transport = _transport({0: [_route_message(0)], 2: [_reference_message(2, course=0.3, speed=2.0)]})
        return _harness(transport, freshness_horizon_ticks=16)

    harness_a = build()
    result_a = harness_a.run(7)
    result_b = build().run(7)

    assert result_a.terminated_by is None
    assert result_a.ticks_completed == 7
    assert result_a.digest == result_b.digest
    empty = harness_a.run(0)
    assert empty.terminated_by is None
    assert empty.ticks_completed == 0
    assert result_a.digest != empty.digest
    # Legacy-equivalent scheduler ZOH: reference@2 is materialized at tick 2 but
    # only promoted to the held controller reference at controller-due tick 5.
    assert result_a.records[2].navigation[2] == 0.0
    assert result_a.records[5].navigation[2] == 0.3
    assert result_a.records[5].navigation[3] == 2.0
    assert result_a.records[6].navigation[2] == 0.3


def test_harness_terminates_on_transport_failure_without_advancing_core() -> None:
    harness = _harness(
        _transport({0: [_route_message(0)], 1: [_route_message(1)]}, process_lost_from_tick=2),
        freshness_horizon_ticks=16,
    )

    result = harness.run(6)

    assert result.terminated_by == "transport_failure"
    assert result.ticks_completed == 2
    assert len(result.transport_failures) == 1
    assert result.transport_failures[0].code is TransportFailureCode.PEER_PROCESS_LOST
    assert result.facade_failures == ()
    assert result.records[-1].tick == 1
    with pytest.raises(RuntimeError, match="terminated"):
        harness.run(1)


def test_harness_terminates_on_facade_failure_without_advancing_core() -> None:
    harness = _harness(
        _transport({0: [_route_message(0, valid_until_tick=1)]}),
        freshness_horizon_ticks=16,
    )

    result = harness.run(6)

    assert result.terminated_by == "facade_failure"
    assert result.ticks_completed == 2
    assert len(result.facade_failures) == 1
    assert result.facade_failures[0].code is FailureCode.EXPIRED_ROUTE
    assert result.transport_failures == ()


def test_harness_snapshot_restore_replay_matches_straight_through_run() -> None:
    script = {
        0: [_route_message(0)],
        3: [_reference_message(3, course=0.5)],
        6: [_route_message(6, route_id="ros-route-3")],
    }

    straight = _harness(_transport(script), freshness_horizon_ticks=16).run(9)

    prefix_harness = _harness(_transport(script), freshness_horizon_ticks=16)
    prefix = prefix_harness.run(4)
    assert prefix.terminated_by is None
    snapshot = prefix_harness.snapshot()
    assert isinstance(snapshot, SilHarnessSnapshot)

    resumed_transport = _transport(script)
    resumed_harness = _harness(resumed_transport, freshness_horizon_ticks=16)
    resumed_harness.restore(snapshot)
    for tick in range(4):  # replay the transport deliveries already consumed before the snapshot
        while resumed_transport.poll(tick) is not None:
            pass
    resumed = resumed_harness.run(5)

    combined = prefix.records + resumed.records
    assert len(combined) == len(straight.records)
    for replayed_record, straight_record in zip(combined, straight.records, strict=True):
        assert replayed_record == straight_record


def test_core_advances_only_from_simulation_ticks_with_wall_clock_excluded() -> None:
    transport = _transport({tick: [_route_message(tick)] for tick in range(5)})
    harness = _harness(transport, freshness_horizon_ticks=16)

    def _forbidden(*_args: object, **_kwargs: object) -> float:
        raise AssertionError("wall clock must not drive simulation-time SIL")

    with (
        mock.patch.object(time, "time", _forbidden),
        mock.patch.object(time, "monotonic", _forbidden),
        mock.patch.object(time, "perf_counter", _forbidden),
    ):
        result = harness.run(5)

    assert result.terminated_by is None
    assert result.ticks_completed == 5


def test_adapter_is_peripheral_and_holds_no_core_reference() -> None:
    adapter = _adapter(_transport({}))

    assert not hasattr(adapter, "step")
    assert not hasattr(adapter, "advance")
    assert "stack" not in vars(adapter)
    materialization = adapter.materialize(0)
    assert materialization.command is not None
    assert isinstance(materialization.command, CommandInput)


def test_harness_reset_restarts_episode_deterministically() -> None:
    transport = _transport({0: [_route_message(0)], 1: [_reference_message(1)]})
    harness = _harness(transport, freshness_horizon_ticks=16)
    first = harness.run(4)
    assert first.terminated_by is None

    harness.reset(NavigationState(0.0, 0.0, 0.0, 0.0, 0.0, 0.0), seed=7)
    transport.reset()
    second = harness.run(4)

    assert second.terminated_by is None
    assert second.digest == first.digest


# ---------------------------------------------------------------------------
# Optional dependency discipline (AC4): module import never requires rclpy
# ---------------------------------------------------------------------------


def test_legacy_core_and_adapter_import_without_ros() -> None:
    code = (
        "import sys;"
        "import colav_simulator.core.ship;"
        "import colav_simulator.modular_gnc.stack;"
        "import colav_simulator.modular_gnc.ros_adapter;"
        "ros_modules = [m for m in sys.modules if m == 'rclpy' or m.startswith('rclpy.')];"
        "sys.exit(f'ros modules imported: {ros_modules}' if ros_modules else 0)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=_PROJECT_ROOT,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.skipif(ros2_transport_status().available, reason="rclpy installed; unavailable path not applicable")
def test_ros2_status_reports_structured_dependency_unavailable() -> None:
    status = ros2_transport_status()

    assert not status.available
    assert status.failure_code is TransportFailureCode.DEPENDENCY_UNAVAILABLE
    assert status.detail


@pytest.mark.skipif(ros2_transport_status().available, reason="rclpy installed; unavailable path not applicable")
def test_real_transport_raises_structured_unavailable_without_crash() -> None:
    with pytest.raises(RosTransportUnavailableError) as error:
        Ros2CommandTransport(
            node=None,
            topic="/colav/command",
            msg_type=None,
            message_adapter=lambda msg: msg,
            offered_qos=_offered_qos(),
        )

    assert error.value.status.failure_code is TransportFailureCode.DEPENDENCY_UNAVAILABLE


@pytest.mark.skipif(not ros2_transport_status().available, reason="rclpy not installed")
def test_real_rclpy_transport_roundtrip() -> None:
    import rclpy  # noqa: PLC0415
    from std_msgs.msg import Float64  # noqa: PLC0415

    from colav_simulator.modular_gnc.ros_adapter import _rclpy_qos_profile  # noqa: PLC0415

    context = rclpy.init()
    try:
        node = rclpy.create_node("gnc_ros_adapter_test")
        transport = Ros2CommandTransport(
            node=node,
            topic="/colav/gnc/test_command",
            msg_type=Float64,
            message_adapter=lambda msg: _reference_message(int(msg.data)),
            offered_qos=_offered_qos(),
        )
        publisher = node.create_publisher(Float64, "/colav/gnc/test_command", _rclpy_qos_profile(_offered_qos()))
        message = Float64()
        message.data = 3.0
        publisher.publish(message)
        rclpy.spin_once(node, timeout_sec=1.0)

        message_observed = transport.poll(3)
        assert message_observed is not None
        assert message_observed.tick == 3
        assert transport.poll(3) is None
        node.destroy_node()
    finally:
        rclpy.shutdown(context=context)


# ---------------------------------------------------------------------------
# G10 gate: three-state, separately reported, explicitly not an A6 claim
# ---------------------------------------------------------------------------


def test_g10_gate_reports_passed_three_state_with_explicit_non_claims() -> None:
    report = run_g10_gate()

    assert isinstance(report, G10SilReport)
    assert report.schema_version == "modular-gnc.g10-sil-report.v1"
    assert report.claim_ceiling == "A3"
    gate = report.gate
    assert isinstance(gate, GateResult)
    assert gate.gate_id == "G10"
    assert gate.status in {"passed", "failed", "not run"}
    assert gate.status == "passed"
    assert gate.evidence_class == "system"
    assert gate.checks
    assert all(check.passed for check in gate.checks)
    non_claims = " ".join(report.non_claims)
    assert "A6" in non_claims
    assert "HIL" in non_claims or "hardware" in non_claims.lower()
    encoded = json.dumps(report.to_dict(), allow_nan=False)
    assert "G10" in encoded
