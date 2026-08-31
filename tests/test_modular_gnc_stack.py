from __future__ import annotations

import numpy as np

from colav_simulator.modular_gnc.configuration import ShipModulesConfig, normalize_ship_modules
from colav_simulator.modular_gnc.contracts import CommandInput, DirectReference, FailureCode, NavigationState
from colav_simulator.modular_gnc.stack import ModularShipStack
from colav_simulator.modular_gnc.test_modules import PassThroughModules


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


def test_failed_phase_leaves_facade_snapshot_unchanged() -> None:
    modules = PassThroughModules(fail_phase="controller", fail_tick=1)
    stack = ModularShipStack(_config(), modules)
    stack.reset(_initial(), seed=11)
    stack.step(_command(0, 0.2), dt_s=0.2)
    before = stack.snapshot()

    failed = stack.step(_command(1, 0.3), dt_s=0.2)

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
