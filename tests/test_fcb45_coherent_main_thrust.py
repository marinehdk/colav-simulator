"""Three main propellers share direction, including rate-limited reversals."""

from dataclasses import replace

import pytest

from colav_simulator.modular_gnc.contracts import NavigationState, VesselLoad
from colav_simulator.modular_gnc.fcb45_actuation import FCB45ActuatorDynamics, FCB45Allocator

MAINS = ("main_thruster_port", "main_thruster_center", "main_thruster_starboard")
NAVIGATION = NavigationState(0.0, 0.0, 0.0, 6.0, 0.0, 0.0)


def test_previous_opposing_allocation_cannot_persist_in_straight_transit() -> None:
    allocator = FCB45Allocator({})
    # Real t=401 s command state, normalized by the executing asset bounds.
    seed = (0.4404741417787716, -0.4117277451134753, 0.3555319567597014, -0.10633298110199732, 0.15746221348305717, 0.0, 0.0)
    allocator.restore(replace(allocator.snapshot(), optimization_seed=seed))
    allocator.set_operating_point(NAVIGATION, (0.0, 0.0))
    for tick in range(20):
        result = allocator.allocate(VesselLoad(surge_n=20000.0), tick=tick, time_s=tick * 0.1)
        assert all(result.actuator_commands_n[key] >= 0.0 for key in MAINS)
        assert abs(result.residual.surge_n) < 1.0
        assert abs(result.residual.yaw_nm) < 1.0


@pytest.mark.parametrize("speed", [0.0, 1.0, 8.0])
@pytest.mark.parametrize("surge", [-60000.0, 0.0, 60000.0])
def test_common_direction_holds_with_rudder_and_bow_yaw_requests(speed: float, surge: float) -> None:
    allocator = FCB45Allocator({})
    allocator.set_operating_point(NavigationState(0.0, 0.0, 0.0, speed, 0.0, 0.0), (0.0, 0.0))
    result = allocator.allocate(VesselLoad(surge_n=surge, sway_n=10000.0, yaw_nm=300000.0))
    main = [result.actuator_commands_n[key] for key in MAINS]
    assert not min(main) < 0.0 < max(main)


@pytest.mark.parametrize("direction", [-1.0, 1.0])
def test_reversal_passes_all_mains_through_zero_without_breaking_force_rates(direction: float) -> None:
    actuator = FCB45ActuatorDynamics({})
    commands = dict.fromkeys(actuator.snapshot().forces, 0.0)
    commands.update(dict(zip(MAINS, (direction * 100000.0, direction * 20000.0, direction * 50000.0), strict=True)))
    kwargs = {
        "navigation": NAVIGATION,
        "current_ne": (0.0, 0.0),
        "bow_authority": 0.0,
        "rudder_angles_rad": {"rudder_port": 0.0, "rudder_starboard": 0.0},
    }
    health = dict.fromkeys(commands, 1.0)
    trace = actuator.apply(commands, health, 0, 0.0, 1.0, **kwargs)
    previous = [trace.actuator_outputs_n[key] for key in MAINS]
    commands.update(dict.fromkeys(MAINS, -direction * 100000.0))
    passed_zero = False
    for tick in range(1, 13):
        snapshot = actuator.snapshot()
        trace = actuator.apply(commands, health, tick, tick * 0.1, 0.1, **kwargs)
        if tick == 3:
            replay = FCB45ActuatorDynamics({})
            replay.restore(snapshot)
            assert replay.apply(commands, health, tick, tick * 0.1, 0.1, **kwargs) == trace
        actual = [trace.actuator_outputs_n[key] for key in MAINS]
        assert not (min(actual) < 0.0 < max(actual))
        assert all(abs(a - b) <= 20000.0 + 1e-8 for a, b in zip(actual, previous, strict=True))
        if all(value == 0.0 for value in actual):
            passed_zero = True
        if any(value * direction < 0.0 for value in actual):
            assert passed_zero
        previous = actual
    assert all(value * direction < 0.0 for value in actual)


def test_actuator_rejects_mixed_main_commands() -> None:
    actuator = FCB45ActuatorDynamics({})
    commands = dict.fromkeys(actuator.snapshot().forces, 0.0)
    commands.update({MAINS[0]: 1000.0, MAINS[1]: -1000.0})
    with pytest.raises(ValueError, match="direction"):
        actuator.apply(
            commands,
            dict.fromkeys(commands, 1.0),
            0,
            0.0,
            0.1,
            navigation=NAVIGATION,
            current_ne=(0.0, 0.0),
            bow_authority=0.0,
            rudder_angles_rad={"rudder_port": 0.0, "rudder_starboard": 0.0},
        )
