"""Physical mechanism checks independent of encounter geometry and PID tuning."""

import math

import numpy as np

from colav_simulator.modular_gnc.contracts import NavigationState, VesselLoad
from colav_simulator.modular_gnc.fcb45_actuation import (
    FCB45ActuationParameters,
    FCB45ActuatorDynamics,
    FCB45Allocator,
    rudder_inflow,
)


def _navigation(speed) -> NavigationState:
    return NavigationState(0.0, 0.0, 0.0, speed, 0.0, 0.0)


def test_rudder_has_no_bollard_authority_without_propeller_wash():
    params = FCB45ActuationParameters()
    zero, _ = rudder_inflow(params, 0.0, 0.0, 0.0, -19.594, 0.0)
    slow, _ = rudder_inflow(params, 2.0, 0.0, 0.0, -19.594, 0.0)
    fast, _ = rudder_inflow(params, 4.0, 0.0, 0.0, -19.594, 0.0)
    wash, _ = rudder_inflow(params, 0.0, 0.0, 0.0, -19.594, 20000.0)
    reverse, _ = rudder_inflow(params, -4.0, 0.0, 0.0, -19.594, -20000.0)
    assert zero == reverse == 0.0
    assert fast == 4.0 * slow
    assert wash > 0.0


def test_bow_hysteresis_and_high_speed_zero_command():
    allocator = FCB45Allocator({})
    authority = []
    for speed in (0.0, 2.9, 3.2, 2.9, 2.6, 7.8):
        allocator.set_operating_point(_navigation(speed), (0.0, 0.0))
        result = allocator.allocate(VesselLoad(sway_n=10000.0, yaw_nm=200000.0))
        authority.append(allocator.bow_authority)
        if speed >= 3.2:
            assert all(value == 0.0 for key, value in result.actuator_commands_n.items() if "bow_" in key)
    assert authority[0] == 1.0
    assert authority[1] > 0.0
    assert authority[2] == authority[3] == authority[5] == 0.0
    assert authority[4] > 0.0


def test_rudder_angle_and_propulsion_rates_apply_to_delivered_load():
    actuator = FCB45ActuatorDynamics({})
    ids = actuator.snapshot().forces
    commands = {
        key: 100000.0 if key.startswith("main_") else 80000.0 if key.startswith("rudder_") else 20000.0 for key in ids
    }
    trace = actuator.apply(
        commands,
        dict.fromkeys(ids, 1.0),
        0,
        0.0,
        0.1,
        navigation=_navigation(7.8),
        current_ne=(0.0, 0.0),
        bow_authority=0.0,
        rudder_angles_rad={"rudder_port": 0.3, "rudder_starboard": 0.3},
    )
    assert all(abs(a) <= 0.01 + 1e-12 for a in trace.rudder_angles_rad.values())
    assert trace.actuator_outputs_n["main_thruster_port"] == 20000.0
    assert trace.actuator_outputs_n["bow_tunnel_thruster_aft"] == 0.0
    assert trace.achieved_load[2] > 0.0  # Right rudder produces starboard yaw.
    assert trace.achieved_load[0] < 60000.0  # Physical rudder drag is actually consumed.
    assert trace.to_achieved_generalized_load().details["rudder_angles_rad"] == trace.rudder_angles_rad
    snapshot = actuator.snapshot()
    replay = actuator.apply(
        commands,
        dict.fromkeys(ids, 1.0),
        1,
        0.1,
        0.1,
        navigation=_navigation(7.8),
        current_ne=(0.0, 0.0),
        bow_authority=0.0,
        rudder_angles_rad={"rudder_port": 0.3, "rudder_starboard": 0.3},
    )
    actuator.restore(snapshot)
    restored = actuator.apply(
        commands,
        dict.fromkeys(ids, 1.0),
        1,
        0.1,
        0.1,
        navigation=_navigation(7.8),
        current_ne=(0.0, 0.0),
        bow_authority=0.0,
        rudder_angles_rad={"rudder_port": 0.3, "rudder_starboard": 0.3},
    )
    assert replay == restored


def test_cruise_allocation_uses_rudders_and_reports_unactuated_sway_residual():
    allocator = FCB45Allocator({})
    allocator.set_operating_point(_navigation(7.8), (0.0, 0.0))
    result = allocator.allocate(VesselLoad(surge_n=60000.0, yaw_nm=400000.0))
    assert result.actuator_commands_n["rudder_port"] > 0.0
    assert abs(result.residual.yaw_nm) < 100.0
    assert abs(result.residual.surge_n) < 100.0
    assert result.achieved.sway_n < 0.0
    assert np.isfinite(list(result.actuator_commands_n.values())).all()
    assert math.isclose(result.requested.sway_n - result.achieved.sway_n, result.residual.sway_n)


def test_low_speed_allocator_and_actuator_agree_on_wash_and_rudder_drag():
    allocator = FCB45Allocator({})
    actuator = FCB45ActuatorDynamics({})
    navigation = _navigation(1.0)
    allocator.set_operating_point(navigation, (0.4, -0.2))
    solution = allocator.allocate(VesselLoad(surge_n=10000.0, sway_n=10000.0, yaw_nm=100000.0))
    for tick in range(100):
        trace = actuator.apply(
            solution.actuator_commands_n,
            solution.actuator_health,
            tick,
            tick * 0.1,
            0.1,
            navigation=navigation,
            current_ne=(0.4, -0.2),
            bow_authority=allocator.bow_authority,
            rudder_angles_rad=solution.rudder_angles_rad,
        )
    expected = [solution.achieved.surge_n, solution.achieved.sway_n, solution.achieved.yaw_nm]
    np.testing.assert_allclose(trace.achieved_load, expected, rtol=1e-10, atol=1e-7)
    np.testing.assert_allclose(expected, [10000.0, 10000.0, 100000.0], rtol=1e-4, atol=1.0)
