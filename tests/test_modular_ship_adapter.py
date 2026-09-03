from __future__ import annotations

import copy
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


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_adapter_reference_maps_to_structured_abort(value: float) -> None:
    adapter = _adapter()
    adapter.reset(seed=4)
    adapter._legacy._references = np.full((9, 1), value)

    with pytest.raises(ModularShipAbort, match="NONFINITE_INPUT"):
        adapter.forward(0.2)


def test_generated_episode_initial_state_initializes_stack_before_reset() -> None:
    config = _config()
    config.csog_state = None
    adapter = ModularShipAdapter.from_legacy_config(
        config,
        ModularShipStack(config.ship_modules, PassThroughModules()),
    )
    requested = np.array([100.0, 200.0, 6.0, 0.7])

    adapter.set_initial_state(requested, t_start=3.0)
    snapshot = adapter.stack.snapshot()

    np.testing.assert_array_equal(adapter.csog_state, requested)
    np.testing.assert_array_equal(snapshot.module_snapshots[0].state.values, adapter.state)
    assert snapshot.tick == 0
    state, _, _ = adapter.forward(0.2)
    np.testing.assert_array_equal(state, adapter.state)
    assert adapter.stack.tick == 1


def test_invalid_initial_state_reassignment_preserves_adapter_and_stack() -> None:
    adapter = _adapter()
    adapter.reset(seed=4)
    before_state = adapter.state.copy()
    before_start = adapter.t_start
    before_stack = adapter.stack.snapshot()

    with pytest.raises(ValueError, match="finite"):
        adapter.set_initial_state(np.array([100.0, 200.0, 6.0, np.nan]), t_start=3.0)

    np.testing.assert_array_equal(adapter.state, before_state)
    assert adapter.t_start == before_start
    assert adapter.stack.snapshot() == before_stack


def test_scripted_target_state_reassignment_atomically_reinitializes_stack() -> None:
    template = _adapter()
    template.reset(seed=4)
    template.set_references(np.zeros(9))
    template.forward(0.2)
    requested = np.array([100.0, 200.0, 6.0, 0.7])

    scripted_target = copy.deepcopy(template)
    scripted_target.set_initial_state(requested, t_start=3.0)
    snapshot = scripted_target.stack.snapshot()

    np.testing.assert_array_equal(scripted_target.csog_state, requested)
    np.testing.assert_array_equal(snapshot.module_snapshots[0].state.values, scripted_target.state)
    assert snapshot.tick == 0
    assert scripted_target.stack.tick == 0
    assert scripted_target.t_start == 3.0
    state, _, _ = scripted_target.forward(0.2)
    np.testing.assert_array_equal(state, scripted_target.state)
    assert scripted_target.stack.tick == 1


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
