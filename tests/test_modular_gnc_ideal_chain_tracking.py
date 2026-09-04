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

from colav_simulator.core import ship
from colav_simulator.modular_gnc.adapter import ModularShipAdapter
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


def _fcb45_adapter() -> ModularShipAdapter:
    entry = next(item for item in list_stack_catalog()["stacks"] if item["stack_id"] == STACK_ID)
    config = ship.Config.from_dict(
        {
            "id": 0,
            "mmsi": 100,
            "csog_state": [6957500.0, 39500.0, 7.0, 45.0],
            "waypoints": [[6957500.0, 6961500.0], [39500.0, 43500.0]],
            "speed_plan": [7.0, 7.0],
            "guidance": {"los": {}},
            "ship_modules": entry["config"],
        }
    )
    stack = ModularShipStack.from_config(config.ship_modules, episode_seed=0, dt_s=0.5)
    return ModularShipAdapter.from_legacy_config(config, stack)


def test_fcb45_adapter_reports_fcb45_vessel_dimensions() -> None:
    """The injected FCB45 ownship must identify as the 45 m workboat it is.

    The scenario's legacy model params (viknes) stay the planner-side geometry
    source; ship_info and the physical identity properties feed evaluation
    (hull radii) and the simulator's vessel-scale checks (goal-reach radius
    7 x L, grounding buffer L / 2).
    """
    adapter = _fcb45_adapter()
    info = adapter.get_ship_info()

    assert info["length"] == pytest.approx(44.1)
    assert info["width"] == pytest.approx(8.0)
    assert info["draft"] == pytest.approx(2.0)

    assert adapter.length == pytest.approx(44.1)
    assert adapter.width == pytest.approx(8.0)
    assert adapter.draft == pytest.approx(2.0)


def test_legacy_equivalent_adapter_keeps_legacy_vessel_dimensions() -> None:
    from colav_simulator.modular_gnc.factory import legacy_equivalent_profile  # noqa: PLC0415

    config = ship.Config.from_dict(
        {
            "id": 4,
            "mmsi": 44,
            "csog_state": [10.0, 20.0, 3.0, 5.0],
            "waypoints": [[10.0, 100.0], [20.0, 25.0]],
            "speed_plan": [3.0, 3.0],
            "guidance": {"los": {}},
            "ship_modules": legacy_equivalent_profile(),
        }
    )
    stack = ModularShipStack.from_config(config.ship_modules, episode_seed=0, dt_s=0.1)
    adapter = ModularShipAdapter.from_legacy_config(config, stack)
    legacy_info = ship.Ship(
        mmsi=config.mmsi,
        identifier=config.id,
        config=ship.Config.from_dict(
            {
                "id": 4,
                "mmsi": 44,
                "csog_state": [10.0, 20.0, 3.0, 5.0],
                "waypoints": [[10.0, 100.0], [20.0, 25.0]],
                "speed_plan": [3.0, 3.0],
                "guidance": {"los": {}},
            }
        ),
    ).get_ship_info()

    info = adapter.get_ship_info()
    assert info["length"] == legacy_info["length"]
    assert info["width"] == legacy_info["width"]
    assert adapter.length == pytest.approx(legacy_info["length"])
    assert adapter.width == pytest.approx(legacy_info["width"])
