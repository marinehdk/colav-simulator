"""Integration tests for Generic3DOFPlant with ModularShipStack and ModularShipAdapter (Issue #52)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from colav_simulator.core.ship import Config
from colav_simulator.modular_gnc.adapter import ModularShipAdapter
from colav_simulator.modular_gnc.configuration import (
    ShipModulesConfig,
    UnsupportedModuleCombinationError,
    normalize_ship_modules,
)
from colav_simulator.modular_gnc.contracts import (
    CommandInput,
    ControlTask,
    DirectReference,
    FailureCode,
    NavigationState,
    PlantInputSemantics,
    PlantState,
    VesselLoad,
)
from colav_simulator.modular_gnc.factory import build_modular_ship_adapter
from colav_simulator.modular_gnc.integrators import rk4_step
from colav_simulator.modular_gnc.passthrough_modules import PassThroughModules
from colav_simulator.modular_gnc.plant import (
    Generic3DOFPlant,
    Generic3DOFPlantParameters,
    GenericRoll4DOFPlant,
    GenericRoll4DOFPlantParameters,
)
from colav_simulator.modular_gnc.stack import ModularShipStack


def _plant_params() -> dict[str, float]:
    return {
        "mass_kg": 1.6e7,
        "i_z_kgm2": 3.0e10,
        "x_g_m": 0.0,
        "x_dot_u_kg": -5.0e6,
        "y_dot_v_kg": -3.5e7,
        "n_dot_r_kgm2": -2.0e10,
        "y_dot_r_kgm": 1.0e6,
        "n_dot_v_kgm": 1.0e6,
        "d_u": 5.0e4,
        "d_uu": 2.0e5,
        "d_v": 3.0e5,
        "d_vv": 1.5e6,
        "d_r": 8.0e7,
        "d_rr": 2.5e9,
    }


def _config_with_generic_plant() -> ShipModulesConfig:
    return normalize_ship_modules(
        {
            "preset": "legacy_equivalent",
            "overrides": {"scheduler": {"plant_period_ticks": 1, "controller_period_ticks": 2}},
            "modules": {
                "plant": {
                    "identity": "generic_3dof_plant",
                    "parameters": _plant_params(),
                },
                "guidance": {"identity": "pass_through_guidance", "parameters": {}},
                "controller": {"identity": "pass_through_controller", "parameters": {}},
            },
        }
    )


def test_stack_from_config_instantiates_generic_plant() -> None:
    cfg = _config_with_generic_plant()
    stack = ModularShipStack.from_config(cfg)
    nav0 = NavigationState(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    stack.reset(nav0, seed=123)

    state = stack.snapshot().module_snapshots[0].state
    assert isinstance(state, PlantState)
    assert "GENERALIZED_FORCE" in state.capabilities
    assert state.input_semantics is PlantInputSemantics.GENERALIZED_FORCE


def test_stack_generic_plant_step_advances_physics_with_rk4() -> None:
    cfg = _config_with_generic_plant()
    stack = ModularShipStack.from_config(cfg)
    nav0 = NavigationState(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    stack.reset(nav0, seed=42)

    # Apply forward thrust: Fx = 2.1e5 N (with mass ~ 2.1e7 kg, accel ~ 0.01 m/s^2)
    # Using MANUAL_LOAD task where values[0..2] = [surge_n, sway_n, yaw_nm]
    ref_vals = np.zeros(9)
    ref_vals[0] = 2.1e5
    cmd = CommandInput.direct(0, DirectReference(ref_vals, latched_tick=0, task=ControlTask.MANUAL_LOAD))

    out = stack.step(cmd, dt_s=1.0)
    assert out.failure is None

    # After 1 second, surge velocity should have increased
    assert out.navigation.surge_mps > 0.0
    assert math.isclose(out.navigation.surge_mps, 0.01, rel_tol=0.05)
    # North position should have moved forward
    assert out.navigation.north_m > 0.0


def test_stack_generic_plant_deterministic_replay_and_snapshot_restore() -> None:
    cfg = _config_with_generic_plant()
    stack1 = ModularShipStack.from_config(cfg)
    stack2 = ModularShipStack.from_config(cfg)
    nav0 = NavigationState(10.0, 20.0, 0.1, 1.0, 0.1, 0.01)

    stack1.reset(nav0, seed=77)
    stack2.reset(nav0, seed=77)

    ref_vals = np.zeros(9)
    ref_vals[0] = 1.0e5
    ref_vals[1] = 2.0e4
    ref_vals[2] = 5.0e4

    trace1 = [
        stack1.step(
            CommandInput.direct(t, DirectReference(ref_vals, latched_tick=t, task=ControlTask.MANUAL_LOAD)),
            dt_s=0.1,
        )
        for t in range(5)
    ]
    trace2 = [
        stack2.step(
            CommandInput.direct(t, DirectReference(ref_vals, latched_tick=t, task=ControlTask.MANUAL_LOAD)),
            dt_s=0.1,
        )
        for t in range(5)
    ]

    for o1, o2 in zip(trace1, trace2, strict=True):
        np.testing.assert_array_equal(o1.plant.values, o2.plant.values)

    # Snapshot and restore
    snap = stack1.snapshot()
    next_cmd = CommandInput.direct(5, DirectReference(ref_vals, latched_tick=5, task=ControlTask.MANUAL_LOAD))
    expected_out = stack1.step(next_cmd, dt_s=0.1)

    stack1.restore(snap)
    restored_out = stack1.step(next_cmd, dt_s=0.1)
    np.testing.assert_array_equal(restored_out.plant.values, expected_out.plant.values)


def test_stack_atomic_rollback_on_plant_failure() -> None:
    cfg = _config_with_generic_plant()
    stack = ModularShipStack.from_config(cfg)
    nav0 = NavigationState(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    stack.reset(nav0, seed=1)

    # Normal step
    ref_vals = np.zeros(9)
    cmd0 = CommandInput.direct(0, DirectReference(ref_vals, latched_tick=0, task=ControlTask.MANUAL_LOAD))
    stack.step(cmd0, dt_s=0.1)

    snap_before = stack.snapshot()

    # Step with non-finite dt_s fails at facade level, restores state
    bad_cmd = CommandInput.direct(1, DirectReference(ref_vals, latched_tick=1, task=ControlTask.MANUAL_LOAD))
    out_failed = stack.step(bad_cmd, dt_s=float("nan"))

    assert out_failed.failure is not None
    assert out_failed.failure.code is FailureCode.NONFINITE_INPUT
    snap_after = stack.snapshot()
    assert snap_after.tick == snap_before.tick
    np.testing.assert_array_equal(
        snap_after.module_snapshots[0].state.values,
        snap_before.module_snapshots[0].state.values,
    )


def test_modular_ship_adapter_with_generic_plant() -> None:
    ship_cfg = Config.from_dict(
        {
            "id": 1,
            "mmsi": 123456789,
            "csog_state": [10.0, 20.0, 3.0, 0.0],
            "ship_modules": {
                "preset": "legacy_equivalent",
                "modules": {
                    "plant": {
                        "identity": "generic_3dof_plant",
                        "parameters": _plant_params(),
                    },
                    "guidance": {"identity": "pass_through_guidance", "parameters": {}},
                    "controller": {"identity": "pass_through_controller", "parameters": {}},
                },
            },
        }
    )

    adapter = build_modular_ship_adapter(ship_cfg)
    assert isinstance(adapter, ModularShipAdapter)

    adapter.reset(seed=42)
    # Set references with forward thrust (index 6 is Fx in legacy 9x1 array)
    ref = np.zeros((9, 1))
    ref[6, 0] = 2.1e5
    adapter.set_references(ref)

    state, _, _ = adapter.forward(dt=0.1)
    # After step, surge velocity has increased
    assert state[3] > 0.0


def test_modular_ship_adapter_with_pass_through_plant_advances_kinematic_position() -> None:
    ship_cfg = Config.from_dict(
        {
            "id": 1,
            "mmsi": 123456789,
            "csog_state": [2500.0, 2500.0, 7.0, 0.0],
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

    adapter = build_modular_ship_adapter(ship_cfg)
    adapter.reset(seed=42)
    reference = np.zeros((9, 1))
    reference[2, 0] = 0.5
    reference[3, 0] = 7.1
    adapter.set_references(reference)

    state, _, _ = adapter.forward(dt=0.5)

    np.testing.assert_allclose(
        state[:2],
        [2500.0 + 0.5 * 7.1 * math.cos(0.5), 2500.0 + 0.5 * 7.1 * math.sin(0.5)],
        atol=1e-12,
    )
    assert state[2] == 0.5
    assert state[3] == 7.1


def test_generic_plant_accepts_period_1_and_rejects_period_greater_than_1() -> None:
    # 1. Period 1 is accepted
    valid_cfg = normalize_ship_modules(
        {
            "preset": "legacy_equivalent",
            "overrides": {"scheduler": {"plant_period_ticks": 1}},
            "modules": {
                "plant": {"identity": "generic_3dof_plant", "parameters": _plant_params()},
                "guidance": {"identity": "pass_through_guidance", "parameters": {}},
                "controller": {"identity": "pass_through_controller", "parameters": {}},
            },
        }
    )
    assert valid_cfg.scheduler["plant_period_ticks"] == 1

    # 2. Period 2 (and >1) rejected at normalization
    with pytest.raises(UnsupportedModuleCombinationError, match="generic_3dof_plant requires plant_period_ticks == 1"):
        normalize_ship_modules(
            {
                "preset": "legacy_equivalent",
                "overrides": {"scheduler": {"plant_period_ticks": 2}},
                "modules": {
                    "plant": {"identity": "generic_3dof_plant", "parameters": _plant_params()},
                    "guidance": {"identity": "pass_through_guidance", "parameters": {}},
                    "controller": {"identity": "pass_through_controller", "parameters": {}},
                },
            }
        )


def test_generic_plant_runtime_defense_rejects_bypass() -> None:
    # Bypass normalization by creating a config with pass-through plant, then manually pairing with generic plant in modules
    base_cfg = normalize_ship_modules(
        {
            "preset": "legacy_equivalent",
            "overrides": {"scheduler": {"plant_period_ticks": 2}},
            "modules": {
                "plant": {"identity": "pass_through_plant", "parameters": {}},
                "guidance": {"identity": "pass_through_guidance", "parameters": {}},
                "controller": {"identity": "pass_through_controller", "parameters": {}},
            },
        }
    )
    assert base_cfg.scheduler["plant_period_ticks"] == 2

    # PassThrough plant permits period 2 (old behavior unchanged)
    pt_modules = PassThroughModules()
    pt_stack = ModularShipStack(base_cfg, pt_modules)
    assert pt_stack is not None

    # But injecting Generic3DOFPlant with period 2 fails at runtime in ModularShipStack.__init__
    gen_plant = Generic3DOFPlant(Generic3DOFPlantParameters(**_plant_params()))
    gen_modules = PassThroughModules(plant=gen_plant)
    with pytest.raises(UnsupportedModuleCombinationError, match="generic_3dof_plant requires plant_period_ticks == 1"):
        ModularShipStack(base_cfg, gen_modules)


def _plant_4dof_params() -> dict[str, float]:
    return {
        "mass_kg": 1.6e7,
        "i_x_kgm2": 1.5e9,
        "i_z_kgm2": 3.0e10,
        "x_g_m": 0.0,
        "z_g_m": 0.0,
        "x_dot_u_kg": -5.0e6,
        "y_dot_v_kg": -3.5e7,
        "k_dot_p_kgm2": -5.0e8,
        "n_dot_r_kgm2": -2.0e10,
        "y_dot_r_kgm": 1.0e6,
        "n_dot_v_kgm": 1.0e6,
        "d_u": 5.0e4,
        "d_uu": 2.0e5,
        "d_v": 3.0e5,
        "d_vv": 1.5e6,
        "d_p": 2.0e7,
        "d_pp": 5.0e7,
        "d_r": 8.0e7,
        "d_rr": 2.5e9,
        "restoring_k_phi": 3.0e8,
    }


def _config_with_roll_4dof_plant() -> ShipModulesConfig:
    return normalize_ship_modules(
        {
            "preset": "legacy_equivalent",
            "overrides": {"scheduler": {"plant_period_ticks": 1, "controller_period_ticks": 2}},
            "modules": {
                "plant": {
                    "identity": "generic_roll_4dof_plant",
                    "parameters": _plant_4dof_params(),
                },
                "guidance": {"identity": "pass_through_guidance", "parameters": {}},
                "controller": {"identity": "pass_through_controller", "parameters": {}},
            },
        }
    )


def test_stack_from_config_instantiates_roll_4dof_plant() -> None:
    cfg = _config_with_roll_4dof_plant()
    stack = ModularShipStack.from_config(cfg)
    nav0 = NavigationState(10.0, 20.0, 0.5, 3.0, 0.0, 0.0)
    stack.reset(nav0, seed=123)

    state = stack.snapshot().module_snapshots[0].state
    assert isinstance(state, PlantState)
    assert "ROLL_4DOF" in state.capabilities
    assert "GENERALIZED_FORCE" in state.capabilities
    assert state.input_semantics is PlantInputSemantics.GENERALIZED_FORCE
    assert len(state.values) == 8
    # Diagnostics preserve phi=0, p=0, navigation fields
    assert state.north_m == 10.0
    assert state.east_m == 20.0
    assert state.heading_rad == 0.5
    assert state.roll_rad == 0.0
    assert state.surge_mps == 3.0
    assert state.sway_mps == 0.0
    assert state.roll_rate_radps == 0.0
    assert state.yaw_rate_radps == 0.0


def test_stack_roll_4dof_plant_step_advances_physics_with_rk4() -> None:
    cfg = _config_with_roll_4dof_plant()
    stack = ModularShipStack.from_config(cfg)
    nav0 = NavigationState(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    stack.reset(nav0, seed=42)

    # Apply forward thrust: Fx = 2.1e5 N (surge accel ~ 0.01 m/s^2)
    ref_vals = np.zeros(9)
    ref_vals[0] = 2.1e5
    cmd = CommandInput.direct(0, DirectReference(ref_vals, latched_tick=0, task=ControlTask.MANUAL_LOAD))

    out = stack.step(cmd, dt_s=1.0)
    assert out.failure is None

    # Surge velocity should have increased
    assert out.navigation.surge_mps > 0.0
    assert math.isclose(out.navigation.surge_mps, 0.01, rel_tol=0.05)
    assert out.navigation.north_m > 0.0
    assert out.plant.values.shape == (8,)


def test_stack_roll_4dof_plant_deterministic_replay_and_snapshot_restore() -> None:
    cfg = _config_with_roll_4dof_plant()
    stack1 = ModularShipStack.from_config(cfg)
    stack2 = ModularShipStack.from_config(cfg)
    nav0 = NavigationState(10.0, 20.0, 0.1, 1.0, 0.1, 0.01)

    stack1.reset(nav0, seed=77)
    stack2.reset(nav0, seed=77)

    ref_vals = np.zeros(9)
    ref_vals[0] = 1.0e5
    ref_vals[1] = 2.0e4
    ref_vals[2] = 5.0e4

    trace1 = [
        stack1.step(
            CommandInput.direct(t, DirectReference(ref_vals, latched_tick=t, task=ControlTask.MANUAL_LOAD)),
            dt_s=0.1,
        )
        for t in range(5)
    ]
    trace2 = [
        stack2.step(
            CommandInput.direct(t, DirectReference(ref_vals, latched_tick=t, task=ControlTask.MANUAL_LOAD)),
            dt_s=0.1,
        )
        for t in range(5)
    ]

    for o1, o2 in zip(trace1, trace2, strict=True):
        np.testing.assert_array_equal(o1.plant.values, o2.plant.values)

    # Snapshot and restore
    snap = stack1.snapshot()
    next_cmd = CommandInput.direct(5, DirectReference(ref_vals, latched_tick=5, task=ControlTask.MANUAL_LOAD))
    expected_out = stack1.step(next_cmd, dt_s=0.1)

    stack1.restore(snap)
    restored_out = stack1.step(next_cmd, dt_s=0.1)
    np.testing.assert_array_equal(restored_out.plant.values, expected_out.plant.values)


def test_modular_ship_adapter_with_roll_4dof_plant() -> None:
    ship_cfg = Config.from_dict(
        {
            "id": 1,
            "mmsi": 123456789,
            "csog_state": [10.0, 20.0, 3.0, 0.0],
            "ship_modules": {
                "preset": "legacy_equivalent",
                "modules": {
                    "plant": {
                        "identity": "generic_roll_4dof_plant",
                        "parameters": _plant_4dof_params(),
                    },
                    "guidance": {"identity": "pass_through_guidance", "parameters": {}},
                    "controller": {"identity": "pass_through_controller", "parameters": {}},
                },
            },
        }
    )

    adapter = build_modular_ship_adapter(ship_cfg)
    assert isinstance(adapter, ModularShipAdapter)

    adapter.reset(seed=42)
    ref = np.zeros((9, 1))
    ref[6, 0] = 2.1e5
    adapter.set_references(ref)

    state, _, _ = adapter.forward(dt=0.1)
    assert state.shape == (6,)  # Legacy navigation projection remains 3DOF (6 elements)
    assert state[3] > 0.0  # Surge velocity increased


def test_roll_4dof_plant_runtime_defense_rejects_bypass() -> None:
    base_cfg = normalize_ship_modules(
        {
            "preset": "legacy_equivalent",
            "overrides": {"scheduler": {"plant_period_ticks": 2}},
            "modules": {
                "plant": {"identity": "pass_through_plant", "parameters": {}},
                "guidance": {"identity": "pass_through_guidance", "parameters": {}},
                "controller": {"identity": "pass_through_controller", "parameters": {}},
            },
        }
    )
    gen_plant = GenericRoll4DOFPlant(GenericRoll4DOFPlantParameters(**_plant_4dof_params()))
    gen_modules = PassThroughModules(plant=gen_plant)
    with pytest.raises(UnsupportedModuleCombinationError, match="generic_roll_4dof_plant requires plant_period_ticks == 1"):
        ModularShipStack(base_cfg, gen_modules)


def test_rk4_step_and_stack_reject_4dof_control_roll_and_atomic_rollback() -> None:
    """Validate that rk4_step and ModularShipStack reject roll control channel and atomically roll back."""
    gen_plant = GenericRoll4DOFPlant(GenericRoll4DOFPlantParameters(**_plant_4dof_params()))
    state0 = np.zeros(8, dtype=np.float64)

    # 1. Direct rk4_step rejects 4-element control load array
    with pytest.raises(ValueError, match="4-channel control input is rejected"):
        rk4_step(gen_plant, tick=0, dt_s=0.1, state=state0, control_load=np.array([1e5, 0.0, 0.0, 0.0]))

    # 2. Direct rk4_step rejects VesselLoad with non-zero roll moment
    with pytest.raises(ValueError, match="roll is unactuated in roll-4DOF plant"):
        rk4_step(gen_plant, tick=0, dt_s=0.1, state=state0, control_load=VesselLoad(surge_n=1e5, roll_nm=100.0))

    # 3. Stack step with roll-4DOF plant captures any module failure and atomically rolls back
    cfg = _config_with_roll_4dof_plant()
    stack = ModularShipStack.from_config(cfg)
    nav0 = NavigationState(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    stack.reset(nav0, seed=1)

    # Good step 0
    ref_vals = np.zeros(9)
    cmd0 = CommandInput.direct(0, DirectReference(ref_vals, latched_tick=0, task=ControlTask.MANUAL_LOAD))
    out0 = stack.step(cmd0, dt_s=0.1)
    assert out0.failure is None
    snap_before = stack.snapshot()

    # Step 1 with non-finite dt_s produces structured failure and rolls back state
    cmd1 = CommandInput.direct(1, DirectReference(ref_vals, latched_tick=1, task=ControlTask.MANUAL_LOAD))
    out1 = stack.step(cmd1, dt_s=float("nan"))
    assert out1.failure is not None
    assert out1.failure.code is FailureCode.NONFINITE_INPUT

    snap_after = stack.snapshot()
    assert snap_after.tick == snap_before.tick
    np.testing.assert_array_equal(
        snap_after.module_snapshots[0].state.values,
        snap_before.module_snapshots[0].state.values,
    )
