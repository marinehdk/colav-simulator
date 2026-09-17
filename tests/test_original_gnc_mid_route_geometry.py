"""Native transport preserves the route compiled and authorized by Mid."""

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from colav_simulator.core.colav.custom_mpc_adapter import CustomMPCAdapter
from colav_simulator.core.colav.diagnostics import PlanStatus
from colav_simulator.core.colav.retained_route import (
    RetainedRouteConstraint,
    compile_planner_trajectory,
    degraded_stub_prefix,
)
from colav_simulator.original_gnc.geometry import RouteFrame
from colav_simulator.original_gnc.native import OriginalGncError
from colav_simulator.original_gnc.plan_bridge import OriginalPlanBridge


def test_mid_transport_never_reshapes_a_planner_compiled_route():
    case = json.loads((Path(__file__).parent / "fixtures/original_gnc/mid-overtaking-route-5s.json").read_text())
    frame = RouteFrame(**case["frame"])
    active = case["active"]
    constraint = RetainedRouteConstraint(
        "active",
        tuple(map(tuple, frame.northeast(active["latitude"], active["longitude"]).T)),
        tuple(active["command_speed_mps"]),
        tuple(active["navigation_mode"]),
        160.0,
        32.0,
        480.0,
        trajectory_updates=True,
    )
    state = np.array(case["state"])
    prefix = degraded_stub_prefix(constraint, state)
    course = np.full(20, state[2])
    speed = np.full(20, np.hypot(state[3], state[4]))
    predicted = np.zeros((9, len(course) + 1))
    predicted[:6, 0] = state
    predicted[0, 1:] = state[0] + np.cumsum(speed * np.cos(course) * 5)
    predicted[1, 1:] = state[1] + np.cumsum(speed * np.sin(course) * 5)
    predicted[2, 1:] = course
    predicted[3, 1:] = speed
    packet = compile_planner_trajectory(prefix, predicted, dt_s=5.0, generated_at_s=5.0)
    epoch = 2_000_000_000_000_000_000
    ship = SimpleNamespace(
        _legacy=SimpleNamespace(_colav=SimpleNamespace(get_route_authority=lambda: case["planner_data"])),
        state=state,
        frame=frame,
        _events=[],
        stack=SimpleNamespace(time_ns=epoch + 5_000_000_000, epoch_ns=epoch),
        _nominal_id="mission",
        _nominal_revision=1,
        _planner_time_origin=0,
    )
    bridge = OriginalPlanBridge(ship, 0.5)
    bridge.planning_constraint = lambda: constraint
    published = []

    def deliver(request, identity):
        published.append((request, identity))
        bridge.last_outcome = {"outcome": "ADMITTED", "rejected": False}

    bridge._deliver = deliver
    with pytest.raises(OriginalGncError, match="planner-compiled"):
        bridge.submit(5.0)
    details = case["planner_data"]["planner"]["algorithm_details"]
    details["execution_route"] = packet
    bridge.submit(5.0)
    assert len(published) == 1
    request, identity = published[0]
    np.testing.assert_allclose(
        frame.northeast(request["latitude"], request["longitude"]).T, packet["points_ne_m"], atol=1e-6
    )
    assert request["command_speed_mps"] == packet["speed_mps"]
    assert request["navigation_mode"] == packet["navigation_modes"]
    assert identity["geometry_modified_by_adapter"] is False
    bridge.submit(5.5)
    assert len(published) == 1
    details["hold_acceptance"] = {
        "accepted": True,
        "mode": "ROLLING_PLAN_CONTINUATION",
        "checked_at_s": 14.5,
        "valid_until_s": 20.0,
    }
    bridge.submit(14.5)
    assert len(published) == 2
    assert published[-1][0]["latitude"] == request["latitude"]
    assert published[-1][0]["valid_until"]["sec"] == 2_000_000_020
    with pytest.raises(OriginalGncError, match="expired"):
        bridge.submit(20.0)
    packet["points_ne_m"] = list(packet["points_ne_m"])
    packet["points_ne_m"][-1] = (0.0, 0.0)
    with pytest.raises(OriginalGncError, match="hash"):
        bridge.submit(15.0)


def test_route_authority_carries_compiled_geometry_outside_display_cache():
    packet = {"schema_version": "colav.mid-mpc.execution-route@1", "geometry_hash": "frozen"}
    trace = SimpleNamespace(
        algorithm_id="mid_mpc_ipopt",
        solve_id=1,
        sim_time=5.0,
        feasible=True,
        solver_executed=True,
        status=PlanStatus.SUCCESS,
        reason="",
        selected_command={},
        algorithm_details={"execution_route": packet},
    )
    authority = CustomMPCAdapter.get_route_authority(SimpleNamespace(_planner_trace=trace))
    assert authority["planner"]["algorithm_details"]["execution_route"] == packet
