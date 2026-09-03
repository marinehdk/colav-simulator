"""Issue #67 stack B: ideal-chain (no allocator/actuator) closed-loop tracking.

The acceptance matrix drives the FCB45 ownship stack
(plant + pass-through guidance + fcb45_marine_pid, ideal actuator) with
COLAV planner course/speed references. Without an allocator or actuator
module there is no genuine achieved-load feedback; feeding the controller
its own previous output as "achieved" injects a fictitious saturation error
into the anti-windup path and the surge integrator rails between its limits
(observed: constant 8 m/s reference converges to ~4.5 m/s with the integral
slamming between +/-200 kN). The ideal chain must instead let MarinePID use
its own current saturated output (allow_ideal_passthrough).
"""

from __future__ import annotations

import numpy as np
import pytest

from colav_simulator.modular_gnc.catalog import list_stack_catalog
from colav_simulator.modular_gnc.configuration import normalize_ship_modules
from colav_simulator.modular_gnc.contracts import CommandInput, DirectReference, NavigationState
from colav_simulator.modular_gnc.stack import ModularShipStack

STACK_ID = "fcb45_3dof_plant+pass_through_guidance+fcb45_marine_pid"


def _stack() -> ModularShipStack:
    entry = next(item for item in list_stack_catalog()["stacks"] if item["stack_id"] == STACK_ID)
    config = normalize_ship_modules(entry["config"])
    stack = ModularShipStack.from_config(config, episode_seed=0, dt_s=0.5)
    stack.reset(NavigationState(6957000.0, 39000.0, np.deg2rad(45.0), 0.0, 0.0, 0.0), 0)
    return stack


def test_ideal_chain_tracks_constant_speed_reference_without_integrator_railing() -> None:
    stack = _stack()
    reference = np.zeros(9)
    reference[2] = np.deg2rad(45.0)
    reference[3] = 8.0

    surges = []
    for tick in range(400):
        output = stack.step(CommandInput.direct(tick, DirectReference(reference, tick)), 0.5)
        assert output.failure is None
        surges.append(output.navigation.surge_mps)

    # Steady-state surge must settle on the reference (isolated run before the
    # fix stalled at ~4.47 m/s with the integral railing between +/-200 kN).
    assert float(np.mean(surges[-80:])) > 7.5
    assert abs(surges[-1] - 8.0) < 0.5
    # And the anti-windup must not be fighting itself: the integral stays
    # bounded well inside its +/-200 kN limit.
    integral = stack._modules._held_controller_trace.i_term[0]
    assert abs(integral) < 100000.0


def test_ideal_chain_reports_current_output_as_achieved_load() -> None:
    stack = _stack()
    reference = np.zeros(9)
    reference[2] = np.deg2rad(45.0)
    reference[3] = 8.0

    for tick in range(20):
        output = stack.step(CommandInput.direct(tick, DirectReference(reference, tick)), 0.5)

    achieved = output.achieved_load
    assert achieved is not None
    assert achieved.source == "IDEAL_PASSTHROUGH"
    assert achieved.surge_n == pytest.approx(output.controller_trace.saturated_output[0])
