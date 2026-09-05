"""Issue #68 S10 facade anchors for the FCB45 guided 4DOF full stack."""

from __future__ import annotations

import copy
import math

import numpy as np

from colav_simulator.modular_gnc.catalog import list_stack_catalog
from colav_simulator.modular_gnc.configuration import normalize_ship_modules
from colav_simulator.modular_gnc.contracts import CommandInput, DirectReference, NavigationState
from colav_simulator.modular_gnc.stack import ModularShipStack

TARGET_STACK_ID = (
    "fcb45_roll_4dof_plant+integral_line_of_sight+fcb45_marine_pid+"
    "analytic_environment_field+standard_environmental_load+"
    "data_driven_allocator[fcb45_main_rudder_actuator_layout_v1]+"
    "resolved_actuator_dynamics[fcb45_main_rudder_actuator_layout_v1]"
)
SERVICE_SPEED_MPS = 7.8
DT_S = 0.1
ROUTE_LENGTH_M = 3000.0


def _entry() -> dict:
    return next(entry for entry in list_stack_catalog()["stacks"] if entry["stack_id"] == TARGET_STACK_ID)


def _stack(environment: bool) -> ModularShipStack:
    config = copy.deepcopy(_entry()["config"])
    if not environment:
        config["modules"].pop("environment")
        config["modules"].pop("load_model")
    return ModularShipStack.from_config(normalize_ship_modules(config), episode_seed=11, dt_s=DT_S)


def _direct_straight(stack: ModularShipStack) -> dict[str, float]:
    stack.reset(NavigationState(0.0, 0.0, 0.0, SERVICE_SPEED_MPS, 0.0, 0.0), seed=11)
    values = np.zeros(9)
    values[3] = SERVICE_SPEED_MPS
    max_xte = 0.0
    min_surge = SERVICE_SPEED_MPS
    max_roll = 0.0
    for tick in range(5000):
        out = stack.step(CommandInput.direct(tick, DirectReference(values, tick)), dt_s=DT_S)
        assert out.failure is None, out.failure
        max_xte = max(max_xte, abs(out.navigation.east_m))
        min_surge = min(min_surge, out.navigation.surge_mps)
        max_roll = max(max_roll, abs(stack.modules.plant_state().roll_rad))
        if out.navigation.north_m >= ROUTE_LENGTH_M:
            return {"max_xte": max_xte, "min_surge": min_surge, "max_roll": max_roll}
    raise AssertionError("target stack did not cover 3000 m")


def test_target_stack_calm_and_environment_straight_routes_stay_within_xte_and_move() -> None:
    calm = _direct_straight(_stack(False))
    env = _direct_straight(_stack(True))
    assert calm["max_xte"] <= 10.0
    assert env["max_xte"] <= 10.0
    assert calm["min_surge"] >= 5.0
    assert env["min_surge"] >= 5.0
    assert env["max_roll"] > 0.0


def test_target_stack_environment_load_components_are_nonzero() -> None:
    stack = _stack(True)
    stack.reset(NavigationState(0.0, 0.0, 0.0, SERVICE_SPEED_MPS, 0.0, 0.0), seed=11)
    nonzero = {"wind": False, "current": False, "wave_first_order": False, "wave_mean_drift": False}
    max_roll = 0.0
    for tick in range(2000):
        out = stack.step(CommandInput.none(tick), dt_s=DT_S)
        assert out.failure is None, out.failure
        loads = stack.modules.environmental_loads()
        assert loads is not None
        for name in nonzero:
            load = getattr(loads, name)
            nonzero[name] |= any(abs(value) > 1e-9 for value in (load.surge_n, load.sway_n, load.roll_nm, load.yaw_nm))
        max_roll = max(max_roll, abs(stack.modules.plant_state().roll_rad))
    assert all(nonzero.values()), nonzero
    assert max_roll > 0.0


def test_target_stack_10_10_zigzag_first_overshoot_is_bounded() -> None:
    stack = _stack(False)
    stack.reset(NavigationState(0.0, 0.0, 0.0, SERVICE_SPEED_MPS, 0.0, 0.0), seed=11)
    values = np.zeros(9)
    values[3] = SERVICE_SPEED_MPS
    for tick in range(1000):
        out = stack.step(CommandInput.direct(tick, DirectReference(values, tick)), dt_s=DT_S)
    assert abs(out.navigation.heading_rad) < math.radians(1.0)
    delta = math.radians(10.0)
    target = delta
    last = out.navigation.heading_rad
    overshoots: list[float] = []
    directions: list[int] = []
    for tick in range(1000, 13000):
        values[2] = target
        out = stack.step(CommandInput.direct(tick, DirectReference(values, tick)), dt_s=DT_S)
        heading = out.navigation.heading_rad
        if target == delta and heading >= delta and last < delta:
            overshoots.append(0.0)
            directions.append(1)
            target = -delta
        elif target == -delta and heading <= -delta and last > -delta:
            overshoots.append(0.0)
            directions.append(-1)
            target = delta
        elif overshoots:
            k = len(overshoots) - 1
            overshoots[k] = max(overshoots[k], (heading - delta) if directions[k] > 0 else (-delta - heading))
        last = heading
        if len(overshoots) >= 2:
            break
    assert len(overshoots) >= 2
    assert math.degrees(overshoots[0]) <= 10.0
