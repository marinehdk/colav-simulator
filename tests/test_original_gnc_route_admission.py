"""P1 integration: avoidance plans admitted by the unchanged original route contract."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from colav_simulator.core.colav.diagnostics import ColavExecutionError
from colav_simulator.core.ship import Config, build_ship
from colav_simulator.modular_gnc.contracts import ControlTask, TrackedRoute
from colav_simulator.modular_gnc.route_bridge import RouteDecision
from colav_simulator.original_gnc.configuration import OriginalGncConfig
from colav_simulator.original_gnc.native import OriginalGncError
from colav_simulator.original_gnc.plan_bridge import OriginalPlanBridge


@pytest.fixture
def original_ship():
    configuration = OriginalGncConfig.from_dict({})
    if not (configuration.build_directory / "build-manifest.json").exists():
        pytest.skip("Optional original GNC is not built")
    config = Config(
        id=0,
        mmsi=123456789,
        csog_state=np.array([1000.0, 2000.0, 7.8, 0.0]),
        waypoints=np.array([[1000.0, 3500.0], [2000.0, 2000.0]]),
        speed_plan=np.array([7.8, 7.8]),
        original_gnc=configuration,
    )
    ship = build_ship(config, dt_s=0.1)
    yield ship
    ship.close()


def _vo_intent(course_rad: float = 0.2, speed: float = 7.8, solve_period: float = 1.0, solve_id: int = 1) -> dict:
    return {
        "planner": {
            "algorithm_id": "vo",
            "solver_executed": True,
            "solve_id": solve_id,
            "feasible": True,
            "selected_command": {"course_rad": course_rad, "speed_mps": speed},
            "algorithm_details": {
                "hard_constraint_count": 1,
                "active_rules": {"1": ["HO"]},
                "give_way_commitment_active": True,
                "stand_on_hold_active": False,
                "static_hazard_count": 0,
                "solve_period_s": solve_period,
            },
        }
    }


def _mount(ship, data: dict) -> OriginalPlanBridge:
    ship._legacy._colav = SimpleNamespace(
        get_route_authority=lambda: data,
        get_colav_data=lambda: data,
        get_diagnostics=lambda: SimpleNamespace(to_dict=lambda: {}),
    )
    ship._planner_time_origin = 0
    bridge = OriginalPlanBridge(ship, 0.1)
    ship._plan_bridge = bridge
    return bridge


def _coordinate_feedback(bridge) -> dict:
    return next(f for f in bridge.last_outcome["feedback"] if f.get("topic") == "/route_planning/route_plan_status")


def test_vo_velocity_intent_is_admitted_without_a_synthetic_route(original_ship):
    ship = original_ship
    ship.forward(11)
    bridge = _mount(ship, _vo_intent())
    bridge.submit(11)
    row = ship.requested_plans[-1]
    request = row["message"]
    assert row["kind"] == "velocity_intent"
    assert "latitude" not in request and "longitude" not in request
    assert request["course_rad"] == 0.2 and request["speed_mps"] == 7.8
    assert request["valid_until"] == {"sec": 2_000_000_012, "nanosec": 0}
    assert bridge.last_outcome["accepted"] and not bridge.last_outcome["rejected"]
    assert ship.stack.latest["/gnc/active_route"]["route_type"] == "nominal"


def test_velocity_update_has_no_synthetic_route_distance_gate(original_ship):
    ship = original_ship
    ship.forward(11)
    data = _vo_intent()
    bridge = _mount(ship, data)
    bridge.submit(11)
    ship.forward(0.1)
    data["planner"]["selected_command"]["course_rad"] = 0.35
    data["planner"]["solve_id"] = 2
    bridge.submit(11.1)
    assert ship.requested_plans[-1]["message"]["course_rad"] == 0.35
    assert bridge.admission_metrics["accepted"] == 2
    assert bridge.admission_metrics["coordinate_accepted"] == 0


def test_held_velocity_does_not_extend_its_original_validity(original_ship):
    ship = original_ship
    ship.forward(11)
    data = _vo_intent(solve_period=12.0)
    bridge = _mount(ship, data)
    bridge.submit(11)
    count = len(ship.requested_plans)
    data["planner"]["solver_executed"] = False
    ship.forward(10.0)
    bridge.submit(21.0)
    assert len(ship.requested_plans) == count
    assert ship.requested_plans[-1]["message"]["valid_until"] == {"sec": 2_000_000_023, "nanosec": 0}


def test_expired_held_velocity_is_never_extended(original_ship):
    ship = original_ship
    ship.forward(11)
    data = _vo_intent()
    bridge = _mount(ship, data)
    bridge.submit(11)
    data["planner"]["solver_executed"] = False
    ship.forward(2.0)
    with pytest.raises(OriginalGncError, match="Expired"):
        bridge.submit(13.0)


def test_clear_constraints_keep_velocity_authority(original_ship):
    ship = original_ship
    ship.forward(11)
    data = _vo_intent()
    bridge = _mount(ship, data)
    bridge.submit(11)
    data["planner"]["algorithm_details"].update(hard_constraint_count=0, active_rules={}, give_way_commitment_active=False)
    ship.forward(0.5)
    bridge.submit(11.5)
    assert ship.stack.states["active_route_manager_node"]["active_velocity_intent"]
    assert ship.requested_plans[-1]["message"]["behavior_mode"] == "cruise"


def test_source_velocity_rejection_is_not_silently_treated_as_execution(original_ship):
    ship = original_ship
    ship.forward(11)
    bridge = _mount(ship, _vo_intent())
    ship._nominal_revision += 1
    with pytest.raises(ColavExecutionError, match="rejected"):
        bridge.submit(11)
    assert bridge.last_outcome["rejected"]
    assert not ship.stack.states["active_route_manager_node"]["active_velocity_intent"]


def _mid_planner_data(sequence: int, receipt_hash: str) -> dict:
    return {
        "planner": {
            "algorithm_id": "mid_mpc_ipopt",
            "solver_executed": True,
            "feasible": True,
            "selected_command": {"course_rad": 0.1, "speed_mps": 6.0},
            "algorithm_details": {
                "accepted_plan_receipt": {"receipt_hash": receipt_hash, "accepted_sequence": sequence},
            },
        }
    }


def _mid_decision(tick: int, waypoints: np.ndarray, speeds: np.ndarray, until_tick: int, revision: int = 0) -> RouteDecision:
    route = TrackedRoute(
        route_id="mid-mpc-0123456789abcdef",
        revision=revision,
        accepted=True,
        valid_from_tick=tick,
        valid_until_tick=until_tick,
        waypoints_ne_m=waypoints,
        speed_mps=speeds,
        task=ControlTask.TRANSIT,
    )
    return RouteDecision(tick=tick, route=route)


def test_mid_receipt_becomes_route_contract_with_segments_and_speeds(original_ship):
    ship = original_ship
    ship.stack.advance(11)
    ship._sync_state()
    data = _mid_planner_data(1, "a" * 64)
    bridge = _mount(ship, data)
    origin = np.array([[1086.0], [2000.0]])
    raw = np.hstack([origin + np.array([[20.0 * i], [3.0 * i]]) for i in range(40)])  # 20 m spacing
    decision = _mid_decision(110, raw, np.full(raw.shape[1], 6.0), 400)
    bridge._mid = SimpleNamespace(current_route=lambda tick, planner_data: decision)
    bridge.submit(11)
    request = ship.requested_plans[-1]["message"]
    assert request["plan_id"] == "mid-mpc-" + "a" * 24
    speeds = np.asarray(request["command_speed_mps"])
    assert len(speeds) == len(request["latitude"])
    points = ship.frame.northeast(request["latitude"], request["longitude"])
    new = points[:, 1:]
    gaps = np.linalg.norm(np.diff(new, axis=1), axis=0)
    assert gaps.min() >= 30.0
    assert request["require_exact_speed"] is False
    assert request["allow_degraded_execution"] is True
    assert request["command_heading_deg"] == []
    assert request["valid_until"] == {"sec": 2_000_000_040, "nanosec": 0}  # valid_until_tick * dt, never extended
    assert "avoidance" in request["navigation_mode"]
    assert request["navigation_mode"][0] == "cruise"
    coordinate = _coordinate_feedback(bridge)
    assert coordinate["accepted"] is True
    # CONTINUITY_PRESERVED receipts keep identity; discontinuities start a new generation.
    bridge._mid = SimpleNamespace(
        current_route=lambda tick, planner_data: _mid_decision(111, raw[:, :-1], np.full(raw.shape[1] - 1, 6.0), 401)
    )
    bridge.submit(11.1)
    assert ship.requested_plans[-1]["message"]["plan_id"] == "mid-mpc-" + "a" * 24
    bridge._mid = SimpleNamespace(
        current_route=lambda tick, planner_data: _mid_decision(
            112, raw[:, :-3], np.full(raw.shape[1] - 3, 6.0), 402, revision=1
        )
    )
    data["planner"]["algorithm_details"]["accepted_plan_receipt"]["receipt_hash"] = "b" * 64
    bridge.submit(11.2)
    assert ship.requested_plans[-1]["message"]["plan_id"] == "mid-mpc-" + "b" * 24


def test_mid_receipt_schema_sequence_key_is_read_tolerantly(original_ship):
    """The bridge reads the mid receipt authority cycle tolerantly.

    colav.mid_mpc.receipt@1 names the authority cycle "sequence"; the
    canonical accepted-plan-receipt schema names it "accepted_sequence". The
    bridge must accept both, as threat management already does.
    """
    ship = original_ship
    ship.stack.advance(11)
    ship._sync_state()
    data = _mid_planner_data(1, "a" * 64)
    receipt = data["planner"]["algorithm_details"]["accepted_plan_receipt"]
    receipt["sequence"] = receipt.pop("accepted_sequence")
    bridge = _mount(ship, data)
    origin = np.array([[1086.0], [2000.0]])
    raw = np.hstack([origin + np.array([[20.0 * i], [3.0 * i]]) for i in range(40)])  # 20 m spacing
    decision = _mid_decision(110, raw, np.full(raw.shape[1], 6.0), 400)
    bridge._mid = SimpleNamespace(current_route=lambda tick, planner_data: decision)
    bridge.submit(11)
    request = ship.requested_plans[-1]["message"]
    assert request["plan_id"] == "mid-mpc-" + "a" * 24
    coordinate = _coordinate_feedback(bridge)
    assert coordinate["accepted"] is True


def test_mid_route_short_of_splice_margin_holds_instead_of_raising(original_ship):
    """Hold the active route when the plan stays short of the splice margin.

    An accepted Mid plan whose geometry never reaches the 160 m splice margin
    (give-way standby or flee geometry) cannot become a new avoidance route;
    the frozen manager would reject it as a sub-margin dynamic update. The
    bridge must hold the active route for that tick instead of aborting the
    run (seam-01 crossing_give_way died raising at t=51 s).
    """
    ship = original_ship
    ship.stack.advance(11)
    ship._sync_state()
    data = _mid_planner_data(1, "a" * 64)
    bridge = _mount(ship, data)
    origin = np.array([[1086.0], [2000.0]])
    raw = np.hstack([origin + np.array([[20.0 * i], [3.0 * i]]) for i in range(40)])
    decision = _mid_decision(110, raw, np.full(raw.shape[1], 6.0), 400)
    bridge._mid = SimpleNamespace(current_route=lambda tick, planner_data: decision)
    bridge.submit(11)
    # Sideways stub: along-track progress on the reference never gains 160 m.
    perpendicular = np.array([[3.0], [2.0]])
    perpendicular = perpendicular / np.linalg.norm(perpendicular)
    stub = np.hstack([origin + 5.0 * i * perpendicular for i in range(40)])
    held = _mid_decision(110, stub, np.full(stub.shape[1], 6.0), 400)
    bridge._mid = SimpleNamespace(current_route=lambda tick, planner_data: held)
    submissions = len(ship.requested_plans)
    bridge.submit(11.5)
    assert len(ship.requested_plans) == submissions  # held: no submission, no rejection storm
    # The hold is recoverable: a route that reaches the margin admits.
    revised = _mid_decision(112, raw, np.full(raw.shape[1], 6.0), 402, revision=1)
    bridge._mid = SimpleNamespace(current_route=lambda tick, planner_data: revised)
    data["planner"]["algorithm_details"]["accepted_plan_receipt"]["receipt_hash"] = "c" * 64
    bridge.submit(12.0)
    request = ship.requested_plans[-1]["message"]
    assert request["plan_id"] == "mid-mpc-" + "c" * 24
    assert _coordinate_feedback(bridge)["accepted"] is True


def _vo_static_only_intent(
    course_rad: float = 0.2, speed: float = 7.8, solve_period: float = 1.0, solve_id: int = 1
) -> dict:
    """Constraint evidence with no dynamic encounter: static hazard grid only."""
    intent = _vo_intent(course_rad, speed, solve_period, solve_id)
    intent["planner"]["algorithm_details"].update(
        hard_constraint_count=3,
        active_rules={},
        give_way_commitment_active=False,
        stand_on_hold_active=False,
        static_hazard_count=2,
    )
    return intent


def _avoidance_requests(ship) -> list[dict]:
    return [row for row in ship.requested_plans if row["kind"] == "avoidance"]


def test_held_velocity_keeps_its_solve_identity(original_ship):
    ship = original_ship
    ship.forward(11)
    data = _vo_intent()
    bridge = _mount(ship, data)
    bridge.submit(11)
    identifier = ship.requested_plans[-1]["message"]["intent_id"]
    data["planner"]["solver_executed"] = False
    data["planner"]["selected_command"]["course_rad"] += 1e-15
    ship.forward(0.1)
    bridge.submit(11.1)
    assert ship.requested_plans[-1]["message"]["intent_id"] == identifier
    assert ship.requested_plans[-1]["message"]["valid_until"] == {"sec": 2_000_000_012, "nanosec": 0}


def test_velocity_speed_update_reaches_native_guidance(original_ship):
    ship = original_ship
    ship.forward(11)
    data = _vo_intent()
    bridge = _mount(ship, data)
    bridge.submit(11)
    ship.forward(0.1)
    data["planner"]["selected_command"]["speed_mps"] = 6.2
    data["planner"]["solve_id"] = 2
    bridge.submit(11.1)
    ship.forward(0.5)
    status = ship.stack.latest["/gnc/velocity_execution_status"]
    assert status["requested_speed_mps"] == 6.2
    assert 0 < status["applied_speed_mps"] <= 6.2


def test_velocity_can_resume_avoidance_without_switching_input_kind(original_ship):
    ship = original_ship
    ship.forward(11)
    data = _vo_intent()
    bridge = _mount(ship, data)
    bridge.submit(11)
    data["planner"]["algorithm_details"].update(hard_constraint_count=0, active_rules={}, give_way_commitment_active=False)
    ship.forward(0.1)
    bridge.submit(11.1)
    data["planner"]["algorithm_details"].update(
        hard_constraint_count=1, active_rules={"1": ["HO"]}, give_way_commitment_active=True
    )
    data["planner"]["solve_id"] = 2
    ship.forward(0.1)
    bridge.submit(11.2)
    assert bridge.last_outcome["accepted"]
    assert ship.requested_plans[-1]["kind"] == "velocity_intent"


def test_invalid_velocity_cannot_reach_native_execution(original_ship):
    ship = original_ship
    ship.forward(11)
    data = _vo_intent()
    data["planner"]["selected_command"]["speed_mps"] = float("nan")
    bridge = _mount(ship, data)
    before = len(ship.requested_plans)
    with pytest.raises(OriginalGncError, match="finite"):
        bridge.submit(11)
    assert len(ship.requested_plans) == before


def test_static_only_velocity_uses_ordinary_mode(original_ship):
    ship = original_ship
    ship.forward(11)
    bridge = _mount(ship, _vo_static_only_intent())
    bridge.submit(11)
    request = ship.requested_plans[-1]["message"]
    assert request["behavior_mode"] == "avoidance"
    assert "navigation_mode" not in request
    assert bridge.last_outcome["accepted"]


def _deviation_speeds(request: dict) -> list[float]:
    """Published speeds of the avoidance-tagged deviation slice of one plan."""
    modes = request["navigation_mode"]
    first = modes.index("avoidance")
    last = len(modes) - 1 - modes[::-1].index("avoidance")
    return request["command_speed_mps"][first : last + 1]


def test_explicit_emergency_velocity_preserves_the_emergency_policy(original_ship):
    ship = original_ship
    ship.forward(11)
    data = _vo_intent(speed=3.2)
    data["planner"]["algorithm_details"]["execution_mode"] = "emergency_avoidance"
    bridge = _mount(ship, data)
    bridge.submit(11)
    ship.forward(0.5)
    assert ship.requested_plans[-1]["message"]["behavior_mode"] == "emergency_avoidance"
    assert ship.stack.latest["/gnc/velocity_execution_status"]["mode_speed_cap_mps"] == 3.2


def test_planner_envelope_speed_cap_comes_from_executing_source(original_ship):
    ship = original_ship
    native = ship.stack.states["ship_guidance_node"]["speed_policy"]
    assert ship.planner_avoidance_speed_cap == native["ordinary_cap_mps"]
    assert ship.execution_speed_policy["emergency_cap_mps"] == native["emergency_cap_mps"]
    assert native["emergency_cap_mps"] < native["ordinary_cap_mps"]
    # Diagnostic manifest annotations must not grant execution authority.
    for proposals in ([{"id": "P-C1"}], [{"id": "P-C2"}], []):
        ship._build_identity["colleague_proposal"] = {"proposals": proposals}
        assert ship.planner_avoidance_speed_cap == native["ordinary_cap_mps"]
