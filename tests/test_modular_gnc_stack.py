from __future__ import annotations

import numpy as np

from colav_simulator.modular_gnc.configuration import ShipModulesConfig, normalize_ship_modules
from colav_simulator.modular_gnc.contracts import (
    CommandInput,
    ControlTask,
    DirectReference,
    FailureCode,
    NavigationState,
    TrackedRoute,
)
from colav_simulator.modular_gnc.passthrough_modules import PassThroughModules
from colav_simulator.modular_gnc.stack import ModularShipStack


def _config() -> ShipModulesConfig:
    return normalize_ship_modules(
        {
            "preset": "legacy_equivalent",
            "overrides": {"scheduler": {"controller_period_ticks": 2, "guidance_period_ticks": 4}},
            "modules": {
                "plant": {"identity": "pass_through_plant", "parameters": {}},
                "guidance": {"identity": "pass_through_guidance", "parameters": {}},
                "controller": {"identity": "pass_through_controller", "parameters": {}},
            },
        }
    )


def _initial() -> NavigationState:
    return NavigationState(10.0, 20.0, 0.1, 3.0, 0.0, 0.0)


def _command(tick: int, course: float) -> CommandInput:
    reference = np.zeros(9)
    reference[2] = course
    reference[3] = 4.0
    return CommandInput.direct(tick, DirectReference(reference, tick))


def test_new_instance_reset_restore_and_repeated_seed_are_equivalent() -> None:
    first = ModularShipStack(_config(), PassThroughModules())
    second = ModularShipStack(_config(), PassThroughModules())
    first.reset(_initial(), seed=7)
    second.reset(_initial(), seed=7)

    trace_first = [first.step(_command(tick, 0.2 + tick * 0.01), dt_s=0.2) for tick in range(3)]
    trace_second = [second.step(_command(tick, 0.2 + tick * 0.01), dt_s=0.2) for tick in range(3)]
    assert trace_first == trace_second

    snapshot = first.snapshot()
    expected = first.step(_command(3, 0.4), dt_s=0.2)
    first.restore(snapshot)
    assert first.step(_command(3, 0.4), dt_s=0.2) == expected

    first.reset(_initial(), seed=7)
    replay = [first.step(_command(tick, 0.2 + tick * 0.01), dt_s=0.2) for tick in range(3)]
    assert replay == trace_first


def test_scheduler_runs_only_due_phases_and_holds_direct_reference() -> None:
    modules = PassThroughModules()
    stack = ModularShipStack(_config(), modules)
    stack.reset(_initial(), seed=5)

    stack.step(_command(0, 0.2), dt_s=0.2)
    stack.step(_command(1, 0.3), dt_s=0.2)
    stack.step(CommandInput.none(2), dt_s=0.2)
    stack.step(CommandInput.none(3), dt_s=0.2)
    stack.step(CommandInput.none(4), dt_s=0.2)

    counts = dict(modules.snapshot().phase_counts)
    assert counts == {"environment": 5, "guidance": 2, "controller": 3, "allocator": 3, "actuator": 3, "plant": 5}
    assert modules.plant_state().values[2] == 0.3


def test_command_tick_must_match_stack_tick() -> None:
    for command_tick, expected_code in ((1, FailureCode.OUT_OF_ORDER_INPUT), (2, FailureCode.OUT_OF_ORDER_INPUT)):
        stack = ModularShipStack(_config(), PassThroughModules())
        stack.reset(_initial(), seed=6)
        before = stack.snapshot()

        failed = stack.step(CommandInput.none(command_tick), dt_s=0.2)

        assert failed.failure.code is expected_code
        assert failed.failure.details == {"command_tick": command_tick, "stack_tick": 0}
        assert stack.snapshot() == before

    stack = ModularShipStack(_config(), PassThroughModules())
    stack.reset(_initial(), seed=6)
    stack.step(CommandInput.none(0), dt_s=0.2)
    before = stack.snapshot()

    stale = stack.step(CommandInput.none(0), dt_s=0.2)

    assert stale.failure.code is FailureCode.STALE_INPUT
    assert stale.failure.details == {"command_tick": 0, "stack_tick": 1}
    assert stack.snapshot() == before


def test_tracked_route_is_consumed_only_on_due_guidance_phase() -> None:
    modules = PassThroughModules()
    stack = ModularShipStack(_config(), modules)
    stack.reset(_initial(), seed=6)
    route = TrackedRoute(
        route_id="route",
        revision=1,
        accepted=True,
        valid_from_tick=1,
        valid_until_tick=8,
        waypoints_ne_m=np.array([[0.0, 10.0], [0.0, 1.0]]),
        speed_mps=np.array([2.0, 2.0]),
        task=ControlTask.TRANSIT,
    )

    stack.step(CommandInput.none(0), dt_s=0.2)
    stack.step(CommandInput.route(1, route), dt_s=0.2)
    assert modules.route_consumptions == ()
    stack.step(CommandInput.none(2), dt_s=0.2)
    stack.step(CommandInput.none(3), dt_s=0.2)
    stack.step(CommandInput.none(4), dt_s=0.2)

    assert modules.route_consumptions == ((4, "route", 1),)


def test_expired_held_route_fails_before_due_guidance_consumes_it() -> None:
    modules = PassThroughModules()
    stack = ModularShipStack(_config(), modules)
    stack.reset(_initial(), seed=6)
    route = TrackedRoute(
        route_id="route",
        revision=1,
        accepted=True,
        valid_from_tick=1,
        valid_until_tick=3,
        waypoints_ne_m=np.array([[0.0, 10.0], [0.0, 1.0]]),
        speed_mps=np.array([2.0, 2.0]),
        task=ControlTask.TRANSIT,
    )

    stack.step(CommandInput.none(0), dt_s=0.2)
    stack.step(CommandInput.route(1, route), dt_s=0.2)
    stack.step(CommandInput.none(2), dt_s=0.2)
    stack.step(CommandInput.none(3), dt_s=0.2)
    before = stack.snapshot()

    failed = stack.step(CommandInput.none(4), dt_s=0.2)

    assert failed.failure.code is FailureCode.EXPIRED_ROUTE
    assert failed.failure.details == {"route_id": "route", "valid_until_tick": 3}
    assert modules.route_consumptions == ()
    assert stack.snapshot() == before


def test_invalid_dt_is_structured_and_snapshot_unchanged() -> None:
    stack = ModularShipStack(_config(), PassThroughModules())
    stack.reset(_initial(), seed=10)
    before = stack.snapshot()

    failed = stack.step(_command(0, 0.2), dt_s=0.0)

    assert failed.failure.code is FailureCode.INVALID_INPUT
    assert stack.snapshot() == before


def test_failed_phase_leaves_facade_snapshot_unchanged() -> None:
    modules = PassThroughModules(fail_phase="controller", fail_tick=2)
    stack = ModularShipStack(_config(), modules)
    stack.reset(_initial(), seed=11)
    stack.step(_command(0, 0.2), dt_s=0.2)
    stack.step(_command(1, 0.3), dt_s=0.2)
    before = stack.snapshot()
    failed = stack.step(CommandInput.none(2), dt_s=0.2)

    assert failed.failure.code is FailureCode.MODULE_FAILURE
    assert stack.snapshot() == before


def test_ship_order_and_state_isolation_equivalence() -> None:
    stacks = {ship_id: ModularShipStack(_config(), PassThroughModules()) for ship_id in (1, 2)}
    for ship_id, stack in stacks.items():
        stack.reset(_initial(), seed=ship_id)

    forward = {ship_id: stacks[ship_id].step(_command(0, 0.1 * ship_id), dt_s=0.2) for ship_id in (1, 2)}

    reversed_stacks = {ship_id: ModularShipStack(_config(), PassThroughModules()) for ship_id in (1, 2)}
    for ship_id, stack in reversed_stacks.items():
        stack.reset(_initial(), seed=ship_id)
    reverse = {ship_id: reversed_stacks[ship_id].step(_command(0, 0.1 * ship_id), dt_s=0.2) for ship_id in (2, 1)}

    assert forward == reverse
    assert stacks[1].snapshot() != stacks[2].snapshot()
