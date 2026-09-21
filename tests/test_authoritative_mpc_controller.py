"""Authoritative MPC controller lane: build identity, external-reference tracking, allocation feedback."""

import json
import math

import numpy as np
import pytest

from colav_simulator.authoritative_mpc.catalog import mpc_catalog
from colav_simulator.authoritative_mpc.configuration import MPC_SOURCE_MANIFEST_SHA256, AuthoritativeMpcConfig
from colav_simulator.original_gnc.geometry import RouteFrame, nominal_route, stamp
from colav_simulator.original_gnc.stack import NativeStack


@pytest.fixture
def runtime():
    config = AuthoritativeMpcConfig.from_dict({})
    roots, assets, policy = config.source_assets()
    parameters = config.parameters()
    for name, value in {
        "initial_position.x": 0.0,
        "initial_position.y": 0.0,
        "initial_position.yaw": 0.0,
        "initial_velocity.u": 4.0,
        "initial_velocity.v": 0.0,
        "initial_velocity.r": 0.0,
    }.items():
        parameters["ship_dynamics_node"][name]["value"] = value
    with NativeStack(
        config.build_directory,
        parameters,
        roots,
        policy,
        asset_paths=assets,
        approved_manifest_sha256=MPC_SOURCE_MANIFEST_SHA256,
    ) as stack:
        frame = RouteFrame(1000.0, 2000.0)
        route = nominal_route(
            frame,
            np.array([[1000.0, 11000.0], [2000.0, 2000.0]]),
            np.array([4.0, 4.0]),
            "mission",
            1,
            stack.time_ns,
        )
        stack.publish("/route_planning/route_plan", "ship_interfaces/msg/RoutePlan", route)
        stack.advance(31.0)
        yield stack, frame


def test_build_lane_is_bound_to_mpc_controller_extraction():
    config = AuthoritativeMpcConfig.from_dict({})
    manifest = json.loads((config.build_directory / "build-manifest.json").read_text())
    assert manifest["controller_package"] == "gnc/mpc_control"
    assert manifest["source_manifest_sha256"] == MPC_SOURCE_MANIFEST_SHA256
    extraction = json.loads((config.build_directory / "extraction.json").read_text())
    assert extraction["modules"]["ship_control_node"]["class"] == "ShipControllerNode"
    assert extraction["files"], "extraction ledger must not be empty"


def test_mpc_runs_in_external_reference_mode():
    config = AuthoritativeMpcConfig.from_dict({})
    assert config.parameters()["ship_control_node"]["mpc.enable"]["value"] is True
    assert config.parameters()["ship_control_node"]["mpc.integrated_guidance_enable"]["value"] is False


def test_guidance_references_flow_through_mpc_controller(runtime):
    stack, _ = runtime
    heading = stack.latest.get("/control/heading_setpoint")
    speed = stack.latest.get("/control/speed_setpoint")
    assert heading is not None, "external heading reference must be published by the frozen guidance chain"
    assert speed is not None, "external speed reference must be published by the frozen guidance chain"
    assert math.isfinite(heading["data"]) and math.isfinite(speed["data"])
    assert speed["data"] > 0.0


def test_mpc_publishes_finite_bounded_tau_and_vessel_tracks_route(runtime):
    stack, _ = runtime
    command = stack.latest.get("/cmd_tau")
    assert command is not None, "the MPC controller must publish generalized-force commands"
    wrench = command["wrench"]
    values = [wrench["force"]["x"], wrench["force"]["y"], wrench["torque"]["z"]]
    assert all(math.isfinite(value) for value in values)
    parameters = AuthoritativeMpcConfig.from_dict({}).parameters()["ship_control_node"]
    assert abs(values[0]) <= parameters["max_force_x"]["value"] + 1.0
    assert abs(values[1]) <= parameters["max_force_y"]["value"] + 1.0
    assert abs(values[2]) <= parameters["max_torque_z"]["value"] + 1.0
    state = stack.states["ship_dynamics_node"]
    speed = math.hypot(state["nu"][0], state["nu"][1])
    assert speed > 1.0, "the vessel must make way under the MPC lane"
    controller = stack.states["ship_control_node"]
    assert controller["mode"] == 1, "MPC node must cruise in HEADING_SPEED_AUTOPILOT under external references"
    assert controller["tau_last"] == pytest.approx(values, abs=1e-6)


def test_allocation_feedback_reaches_mpc_controller_inputs(runtime):
    stack, _ = runtime
    achieved = stack.latest.get("/allocation/achieved_tau")
    residual = stack.latest.get("/allocation/residual_tau")
    assert achieved is not None, "the retained PGD allocator must publish achieved tau"
    assert residual is not None, "the retained PGD allocator must publish residual tau"
    subscribers = {
        topic: [name for name, _, _ in callbacks]
        for topic, callbacks in stack._subscribers.items()
    }
    assert "ship_control_node" in subscribers.get("/allocation/achieved_tau", [])
    assert "ship_control_node" in subscribers.get("/env/total_load", [])


def test_mid_timed_trajectory_contract_still_admitted_on_mpc_lane(runtime):
    stack, frame = runtime
    state = stack.latest["/ship/geo_position"]
    speed = state["speed_mps"]
    course = math.radians(state["course_deg"])
    times = np.arange(21) * 5.0
    north = times * speed * np.cos(course)
    east = times * speed * np.sin(course)
    anchored = RouteFrame(0.0, 0.0, state["origin_lat"], state["origin_lon"])
    latitudes, longitudes = anchored.geographic(np.array([state["x_ned"] + north, state["y_ned"] + east]))
    plan = {
        "header": {"stamp": stamp(stack.time_ns), "frame_id": "map"},
        "plan_id": "timed-mid-mpc-1",
        "parent_route_id": "mission",
        "parent_route_revision": 1,
        "behavior_mode": "planner_trajectory_v1",
        "command_source": "mid_mpc_ipopt",
        "latitude": latitudes,
        "longitude": longitudes,
        "command_speed_mps": [speed] * 21,
        "command_heading_deg": [state["course_deg"]] * 21,
        "navigation_mode": ["avoidance"] * 21,
        "valid_until": stamp(stack.time_ns + 10_000_000_000),
        "require_exact_heading": False,
        "require_exact_speed": True,
        "allow_degraded_execution": False,
        "has_return_to_route_point": False,
        "return_latitude": 0.0,
        "return_longitude": 0.0,
        "trajectory_dt_s": 5.0,
        "trajectory_reference_id": stack.latest["/gnc/active_route"]["route_id"],
    }
    stack.publish("/colav/avoidance_plan", "ship_interfaces/msg/AvoidancePlan", plan)
    stack.advance(2.0)
    status = stack.latest.get("/gnc/route_execution_status")
    assert status is not None
    active = stack.latest.get("/gnc/active_route")
    assert active is not None and active["route_id"], "admitted timed trajectory must drive the active route"


def test_catalog_exposes_executable_mpc_card():
    entries, preset = mpc_catalog()
    assert preset["display_name"] == "Authoritative MPC · 2026-09-21"
    assert preset["available"] is True
    assert {entry["available"] for entry in entries} == {True}
    assert preset["variants"] == {
        "off": "authoritative-mpc-20260921-v1-env-off",
        "on": "authoritative-mpc-20260921-v1-env-on",
    }
    assert all(entry["backend_kind"] == "authoritative_mpc" for entry in entries)
    assert preset["build_identity"]["controller_package"] == "gnc/mpc_control"


def test_catalog_reports_mpc_lane_build_identity():
    config = AuthoritativeMpcConfig.from_dict({})
    manifest = json.loads((config.build_directory / "build-manifest.json").read_text())
    expected = {
        "execution_lane": "mpc_controller",
        "candidate": "gnc/mpc_control",
        "proposal_ids": [],
        "controller_package": "gnc/mpc_control",
        "source_manifest_sha256": manifest["source_manifest_sha256"],
        "library_sha256": manifest["library_sha256"],
    }
    entries, preset = mpc_catalog()
    assert all(entry["build_identity"] == expected for entry in entries)
    assert preset["build_identity"] == expected
    assert "response qualification is pending" in preset["note"]


def test_velocity_intent_support_is_reported_from_guidance_policy(runtime):
    stack, _ = runtime
    policy = stack.states["ship_guidance_node"]["speed_policy"]
    assert policy["ordinary_cap_mps"] >= policy["emergency_cap_mps"] > 0.0
