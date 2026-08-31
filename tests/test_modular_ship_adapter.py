from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from colav_simulator.core import ship
from colav_simulator.modular_gnc.adapter import FailurePolicy, ModularShipAbort, ModularShipAdapter
from colav_simulator.modular_gnc.contracts import FacadeFailure, FailureCode
from colav_simulator.modular_gnc.passthrough_modules import PassThroughModules
from colav_simulator.modular_gnc.stack import ModularShipStack


def _config() -> ship.Config:
    config = ship.Config.from_dict(
        {
            "id": 4,
            "mmsi": 44,
            "csog_state": [10.0, 20.0, 3.0, 5.0],
            "waypoints": [[10.0, 100.0], [20.0, 25.0]],
            "speed_plan": [3.0, 3.0],
            "guidance": {"los": {}},
            "ship_modules": {
                "preset": "legacy_equivalent",
                "modules": {
                    "plant": {"identity": "pass_through_plant", "parameters": {}},
                    "guidance": {"identity": "pass_through_guidance", "parameters": {}},
                    "controller": {"identity": "pass_through_controller", "parameters": {}},
                },
            },
        }
    )
    return config


def _adapter(*, fail_phase: str | None = None, fail_tick: int | None = None) -> ModularShipAdapter:
    config = _config()
    modules = PassThroughModules(fail_phase=fail_phase, fail_tick=fail_tick)
    stack = ModularShipStack(config.ship_modules, modules)
    return ModularShipAdapter.from_legacy_config(config, stack)


def test_adapter_is_independent_iship_and_preserves_raw_sim_data_shape() -> None:
    adapter = _adapter()

    assert isinstance(adapter, ship.IShip)
    assert not isinstance(adapter, ship.Ship)
    adapter.reset(seed=3)
    references = np.zeros((9, 1))
    references[2, 0] = 0.4
    references[3, 0] = 4.0
    adapter.set_references(references)
    before = adapter.get_sim_data(t=0.0, timestamp_0=0)
    state, inputs, applied = adapter.forward(0.2)

    assert before["state"][2] == pytest.approx(np.deg2rad(5.0))
    assert state.shape == (6,)
    assert inputs.shape == (3,)
    assert applied.shape == (9,)
    assert set(before) >= {
        "id",
        "mmsi",
        "csog_state",
        "state",
        "turn_rate",
        "input",
        "waypoints",
        "speed_plan",
        "references",
        "goal_state",
        "do_estimates",
        "do_covariances",
        "do_NISes",
        "do_labels",
        "do_generations",
        "active",
    }
    assert before["do_estimates"] == []
    assert before["do_NISes"] == []


def test_adapter_telemetry_is_pre_forward_and_ais_playback_bypasses_stack() -> None:
    adapter = _adapter(fail_phase="plant", fail_tick=0)
    adapter.reset(seed=1)
    adapter.set_references(np.zeros(9))
    telemetry = adapter.get_sim_data(t=0.0, timestamp_0=0)
    adapter.transfer_vessel_ais_data(
        SimpleNamespace(
            xy=np.array([[3.0, 4.0], [1.0, 2.0]]),
            sog=np.array([5.0, 6.0]),
            cog=np.array([0.1, 0.2]),
            timestamps=np.array([0.0, 1.0]),
            first_valid_idx=0,
            last_valid_idx=1,
            mmsi=44,
            length=10.0,
            width=3.0,
            draft=0.5,
        )
    )

    state, _, _ = adapter.forward(0.2)

    assert telemetry["state"][0] == 10.0
    np.testing.assert_array_equal(state, np.array([1.0, 3.0, 0.1, 5.0, 0.0, 0.0]))


def test_invalid_adapter_input_maps_to_structured_abort() -> None:
    adapter = _adapter()
    adapter.reset(seed=4)
    adapter._legacy._references = np.full((9, 1), np.nan)

    with pytest.raises(ModularShipAbort, match="INVALID_INPUT"):
        adapter.forward(0.2)


def test_failure_policy_maps_all_codes_and_unmapped_aborts() -> None:
    for code in FailureCode:
        assert FailurePolicy().action_for(code) == "abort_episode"

    adapter = _adapter(fail_phase="controller", fail_tick=0)
    adapter.reset(seed=2)
    adapter.set_references(np.zeros(9))
    with pytest.raises(ModularShipAbort):
        adapter.forward(0.2)

    with pytest.raises(ModularShipAbort):
        FailurePolicy().apply(
            FacadeFailure(FailureCode.MODULE_FAILURE, "boom", "controller", 0),
            override="unknown_action",
        )
