from __future__ import annotations

import numpy as np

from colav_simulator.modular_gnc.command_latch import CommandLatch
from colav_simulator.modular_gnc.contracts import (
    CommandInput,
    ControlTask,
    DirectReference,
    FailureCode,
    TrackedRoute,
)


def _reference(tick: int, course: float) -> DirectReference:
    values = np.zeros(9)
    values[2] = course
    values[3] = 4.0
    return DirectReference(values=values, latched_tick=tick)


def _route(*, accepted: bool = True, valid_until_tick: int = 8) -> TrackedRoute:
    return TrackedRoute(
        route_id="r1",
        revision=1,
        accepted=accepted,
        valid_from_tick=2,
        valid_until_tick=valid_until_tick,
        waypoints_ne_m=np.array([[0.0, 10.0], [0.0, 1.0]]),
        speed_mps=np.array([2.0, 2.0]),
        task=ControlTask.TRANSIT,
    )


def test_direct_reference_latches_and_holds_until_controller_due_tick() -> None:
    latch = CommandLatch(controller_period_ticks=5)

    assert latch.consume(CommandInput.direct(0, _reference(0, 0.1))).direct_reference.latched_tick == 0
    assert latch.consume(CommandInput.none(1)).direct_reference.latched_tick == 0
    assert latch.consume(CommandInput.direct(2, _reference(2, 0.4))).direct_reference.latched_tick == 0
    assert latch.consume(CommandInput.none(4)).direct_reference.latched_tick == 0
    applied = latch.consume(CommandInput.none(5))

    assert applied.direct_reference.latched_tick == 2
    assert applied.direct_reference.values[2] == 0.4


def test_duplicate_stale_and_out_of_order_ticks_fail_structurally() -> None:
    latch = CommandLatch(controller_period_ticks=1)
    latch.consume(CommandInput.direct(3, _reference(3, 0.1)))

    duplicate = latch.consume(CommandInput.direct(3, _reference(3, 0.1)))
    stale = latch.consume(CommandInput.direct(4, _reference(2, 0.2)))
    out_of_order = latch.consume(CommandInput.none(2))

    assert duplicate.failure.code is FailureCode.DUPLICATE_INPUT
    assert stale.failure.code is FailureCode.STALE_INPUT
    assert out_of_order.failure.code is FailureCode.OUT_OF_ORDER_INPUT


def test_route_rejection_and_expiry_never_fall_back_to_direct_reference() -> None:
    latch = CommandLatch(controller_period_ticks=1)
    latch.consume(CommandInput.direct(0, _reference(0, 0.1)))

    rejected = latch.consume(CommandInput.route(2, _route(accepted=False)))
    expired = latch.consume(CommandInput.route(9, _route(valid_until_tick=8)))

    assert rejected.failure.code is FailureCode.REJECTED_ROUTE
    assert rejected.direct_reference is None
    assert expired.failure.code is FailureCode.EXPIRED_ROUTE
    assert expired.direct_reference is None
