"""Frozen low-speed mixed rudder/bow load must converge without a budget increase."""

import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from colav_simulator.modular_gnc.contracts import NavigationState, VesselLoad
from colav_simulator.modular_gnc.fcb45_actuation import FCB45ActuatorDynamics, FCB45Allocator, FCB45AllocatorSnapshot


@pytest.mark.parametrize("name", ["low_speed_1170.json", "low_speed_1174.json", "low_speed_1181.json"])
def test_low_speed_stall_boundary_allocation_converges_with_original_budget(name: str) -> None:
    case = json.loads((Path(__file__).parent / "fixtures/fcb45_allocator" / name).read_text())
    allocator = FCB45Allocator(case["parameters"])
    allocator.restore(FCB45AllocatorSnapshot(**case["snapshot"]))
    allocator.set_operating_point(NavigationState(**case["navigation"]), tuple(case["current_ne"]))
    result = allocator.allocate(VesselLoad(**case["requested"]), case["tick"], case["time_s"])
    assert np.isfinite(result.allocation_optimality)
    assert result.allocation_evaluations < case["parameters"]["allocator_max_evaluations"]
    residual = np.array(
        [result.residual.surge_n / 200000.0, result.residual.sway_n / 40000.0, result.residual.yaw_nm / 960000.0]
    )
    delta = np.array(allocator.snapshot().optimization_seed) - np.array(case["snapshot"]["optimization_seed"])
    cost = 0.5 * (residual @ residual + 1e-6 * (delta @ delta))
    assert cost <= case["reference_exhausted_cost"]
    main = [value for key, value in result.actuator_commands_n.items() if key.startswith("main_")]
    assert not min(main) < 0.0 < max(main)


def test_projected_thrust_roundoff_stays_inside_exact_actuator_bounds() -> None:
    case = json.loads((Path(__file__).parent / "fixtures/fcb45_allocator/force_roundoff.json").read_text())
    allocator = FCB45Allocator({})
    allocator.restore(replace(allocator.snapshot(), optimization_seed=tuple(case["seed"])))
    navigation = NavigationState(*case["navigation"])
    allocator.set_operating_point(navigation, (0.4, -0.2))
    result = allocator.allocate(VesselLoad(**case["requested"]))
    FCB45ActuatorDynamics({}).apply(
        result.actuator_commands_n,
        result.actuator_health,
        0,
        0.0,
        0.1,
        navigation=navigation,
        current_ne=(0.4, -0.2),
        bow_authority=allocator.bow_authority,
        rudder_angles_rad=result.rudder_angles_rad,
    )


@pytest.mark.parametrize("mirror", [False, True])
def test_net_braking_demand_does_not_force_main_propellers_astern(mirror: bool) -> None:
    """Captured braking/turn request is achievable with coherent ahead thrust and rudder drag."""
    case = json.loads((Path(__file__).parent / "fixtures/fcb45_allocator/low_speed_1181.json").read_text())
    allocator = FCB45Allocator(case["parameters"])
    snapshot = FCB45AllocatorSnapshot(**case["snapshot"])
    navigation = NavigationState(**case["navigation"])
    current = tuple(case["current_ne"])
    request = VesselLoad(**case["requested"])
    if mirror:
        seed = snapshot.optimization_seed
        snapshot = replace(snapshot, optimization_seed=(seed[2], seed[1], seed[0], -seed[4], -seed[3], -seed[5], -seed[6]))
        navigation = replace(
            navigation,
            east_m=-navigation.east_m,
            heading_rad=-navigation.heading_rad,
            sway_mps=-navigation.sway_mps,
            yaw_rate_radps=-navigation.yaw_rate_radps,
        )
        current = (current[0], -current[1])
        request = replace(request, sway_n=-request.sway_n, yaw_nm=-request.yaw_nm)
    allocator.restore(snapshot)
    allocator.set_operating_point(navigation, current)
    result = allocator.allocate(request, case["tick"], case["time_s"])
    assert result.requested.surge_n < 0.0
    # These absolute residuals are independently achieved by the frozen ahead-domain probe.
    assert abs(result.residual.surge_n) < 10.0
    assert abs(result.residual.sway_n) < 10.0
    assert abs(result.residual.yaw_nm) < 10.0
    assert all(value >= 0.0 for key, value in result.actuator_commands_n.items() if key.startswith("main_"))
    assert result.allocation_evaluations <= case["parameters"]["allocator_max_evaluations"]
    actuator = FCB45ActuatorDynamics(case["parameters"])
    for tick in range(70):
        actual = actuator.apply(
            result.actuator_commands_n,
            result.actuator_health,
            tick,
            tick * 0.1,
            0.1,
            navigation=navigation,
            current_ne=current,
            bow_authority=allocator.bow_authority,
            rudder_angles_rad=result.rudder_angles_rad,
        )
    np.testing.assert_allclose(
        actual.achieved_load,
        (result.achieved.surge_n, result.achieved.sway_n, result.achieved.yaw_nm),
        atol=1e-6,
        rtol=0.0,
    )
