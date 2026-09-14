"""Native velocity intents are arbitrated by GNC, not written by the adapter."""

import copy
from types import SimpleNamespace

import numpy as np
import pytest

from colav_simulator.original_gnc.configuration import OriginalGncConfig
from colav_simulator.original_gnc.geometry import RouteFrame, nominal_route, stamp
from colav_simulator.original_gnc.stack import NativeStack


@pytest.fixture
def ship():
    config = OriginalGncConfig.from_dict({})
    roots, assets, policy = config.source_assets()
    parameters = config.parameters()
    for key, value in {
        "initial_position.x": 0.0,
        "initial_position.y": 0.0,
        "initial_position.yaw": 0.0,
        "initial_velocity.u": 8.0,
        "initial_velocity.v": 0.0,
        "initial_velocity.r": 0.0,
    }.items():
        parameters["ship_dynamics_node"][key]["value"] = value
    with NativeStack(config.build_directory, parameters, roots, policy, asset_paths=assets) as stack:
        stack.publish(
            "/route_planning/route_plan",
            "ship_interfaces/msg/RoutePlan",
            nominal_route(
                RouteFrame(1000, 2000),
                np.array([[1000.0, 6000.0], [2000.0, 2000.0]]),
                np.array([8.0, 8.0]),
                "mission",
                1,
                stack.time_ns,
            ),
        )
        stack.advance(11.0)
        yield SimpleNamespace(stack=stack, forward=stack.advance, _nominal_id="mission", _nominal_revision=1)


def intent(ship, mode="avoidance", speed=8.0, duration=10.0) -> dict:
    return {
        "header": {"stamp": stamp(ship.stack.time_ns), "frame_id": "map"},
        "intent_id": "velocity-test",
        "parent_route_id": ship._nominal_id,
        "parent_route_revision": ship._nominal_revision,
        "behavior_mode": mode,
        "command_source": "vo",
        "course_rad": 0.0,
        "speed_mps": speed,
        "speed_reference": "SOG",
        "valid_until": stamp(ship.stack.time_ns + round(duration * 1e9)),
    }


def publish(ship, message):
    ship.stack.publish("/colav/velocity_intent", "ship_interfaces/msg/VelocityIntent", message)


@pytest.mark.parametrize("mode,expected", [("avoidance", 8.0), ("emergency_avoidance", 3.2)])
def test_native_velocity_intent_preserves_policy_and_mission(ship, mode, expected):
    mission = copy.deepcopy(ship.stack.latest["/gnc/active_route"])
    publish(ship, intent(ship, mode))
    assert ship.stack.latest["/gnc/route_execution_status"]["rejected"] is False
    ship.forward(0.5)
    assert ship.stack.latest["/control/speed_setpoint"]["data"] == pytest.approx(expected)
    assert ship.stack.latest["/gnc/active_route"] == mission
    assert ship.stack.latest["/gnc/velocity_execution_status"]["intent_id"] == "velocity-test"


def test_expired_intent_stops_until_explicit_return(ship):
    publish(ship, intent(ship, duration=1.0))
    ship.forward(2.0)
    assert ship.stack.latest["/gnc/velocity_execution_status"]["state"] == "EXPIRED"
    assert ship.stack.latest["/control/speed_setpoint"]["data"] == 0.0
    publish(ship, intent(ship, mode="return_to_route"))
    ship.forward(1.0)
    assert ship.stack.latest["/control/speed_setpoint"]["data"] > 0.0


def test_wrong_parent_cannot_activate_velocity_intent(ship):
    msg = intent(ship)
    msg["parent_route_revision"] += 1
    publish(ship, msg)
    assert ship.stack.latest["/gnc/route_execution_status"]["rejected"] is True
    assert "/gnc/velocity_intent" not in ship.stack.latest


def test_native_cruise_velocity_is_supported_without_a_route_switch(ship):
    publish(ship, intent(ship, mode="cruise"))
    assert ship.stack.latest["/gnc/route_execution_status"]["rejected"] is False
    ship.forward(0.5)
    assert ship.stack.latest["/gnc/velocity_execution_status"]["behavior_mode"] == "cruise"
