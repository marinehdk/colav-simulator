"""P1 integration: avoidance plans admitted by the unchanged original route contract."""

from __future__ import annotations

import math
from types import SimpleNamespace

import numpy as np
import pytest

from colav_simulator.core.ship import Config, build_ship
from colav_simulator.modular_gnc.contracts import ControlTask, TrackedRoute
from colav_simulator.modular_gnc.route_bridge import RouteDecision
from colav_simulator.original_gnc import plan_bridge as plan_bridge_module
from colav_simulator.original_gnc.configuration import OriginalGncConfig
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
    ship._legacy._colav = SimpleNamespace(get_route_authority=lambda: data)
    ship._planner_time_origin = 0
    bridge = OriginalPlanBridge(ship, 0.1)
    ship._plan_bridge = bridge
    return bridge


def _coordinate_feedback(bridge) -> dict:
    return next(f for f in bridge.last_outcome["feedback"] if f.get("topic") == "/route_planning/route_plan_status")


def test_spliced_vo_intent_is_admitted_with_mixed_modes(original_ship):
    ship = original_ship
    ship.stack.advance(11)
    ship._sync_state()
    bridge = _mount(ship, _vo_intent())
    bridge.submit(11)
    request = ship.requested_plans[-1]["message"]
    modes = request["navigation_mode"]
    assert modes[0] == "cruise" and modes[-1] == "dp_hold" and "avoidance" in modes
    assert request["command_heading_deg"] == []
    assert request["require_exact_speed"] is False
    assert request["allow_degraded_execution"] is True
    assert request["require_exact_heading"] is False
    assert request["valid_until"] == {"sec": 2_000_000_016, "nanosec": 0}  # 11 s solve + max(1, 5) widening
    coordinate = _coordinate_feedback(bridge)
    assert coordinate["accepted"] is True
    assert bridge.last_outcome["rejected"] is False
    assert bridge.admission_metrics["submitted"] == 1
    assert bridge.admission_metrics["rejected_addressable"] == 0
    telemetry = ship.original_balance_telemetry()["route_admission"]
    assert telemetry["status"] in {"Accepted", "Limited"}


def test_second_generation_stays_admitted_and_respects_first_change_gate(original_ship):
    ship = original_ship
    ship.stack.advance(11)
    ship._sync_state()
    data = _vo_intent()
    bridge = _mount(ship, data)
    bridge.submit(11)
    ship.stack.advance(2.0)
    ship._sync_state()
    data["planner"]["selected_command"]["course_rad"] = 0.35
    data["planner"]["solve_id"] = 2
    bridge.submit(13.1)
    coordinate = _coordinate_feedback(bridge)
    assert coordinate["accepted"] is True
    ahead = coordinate.get("first_changed_distance_ahead_m")
    assert ahead is not None and (not np.isfinite(ahead) or ahead >= 150.0)
    assert bridge.admission_metrics["coordinate_accepted"] == 2
    assert bridge.admission_metrics["rejected_addressable"] == 0


def test_cadence_latch_suppresses_identical_submissions_until_timeout(original_ship):
    ship = original_ship
    ship.stack.advance(11)
    ship._sync_state()
    data = _vo_intent(solve_period=12.0)
    bridge = _mount(ship, data)
    bridge.submit(11)
    count = len(ship.requested_plans)
    data["planner"]["solver_executed"] = False
    ship.stack.advance(0.1)
    ship._sync_state()
    bridge.submit(11.1)
    assert len(ship.requested_plans) == count  # same geometry/signature inside the 10 s window
    ship.stack.advance(10.0)
    ship._sync_state()
    bridge.submit(21.2)
    assert len(ship.requested_plans) == count + 1  # >=10 s resubmission refreshes manager validity
    assert ship.requested_plans[-1]["message"]["valid_until"] == {"sec": 2_000_000_023, "nanosec": 0}


def test_expired_held_intent_is_never_extended(original_ship):
    ship = original_ship
    ship.stack.advance(11)
    ship._sync_state()
    data = _vo_intent()
    bridge = _mount(ship, data)
    bridge.submit(11)
    data["planner"]["solver_executed"] = False
    ship.stack.advance(5.0)
    ship._sync_state()
    with pytest.raises(Exception, match="expired"):
        bridge.submit(16.1)


def test_internal_return_rotates_reference_for_next_splice(original_ship):
    ship = original_ship
    ship.stack.advance(11)
    ship._sync_state()
    data = _vo_intent()
    bridge = _mount(ship, data)
    bridge.submit(11)
    data["planner"]["algorithm_details"].update(hard_constraint_count=0, active_rules={}, give_way_commitment_active=False)
    ship.stack.advance(0.1)
    ship._sync_state()
    bridge.submit(11.2)  # publishes return_to_route; manager generates internal return; coordinate accepts it
    assert ship.stack.states["active_route_manager_node"]["active_avoidance"] is False
    data["planner"]["algorithm_details"].update(
        hard_constraint_count=1, active_rules={"1": ["HO"]}, give_way_commitment_active=True
    )
    data["planner"]["solver_executed"] = True
    data["planner"]["solve_id"] = 2
    bridge.submit(11.3)
    request = ship.requested_plans[-1]["message"]
    internal = [
        event["message"]["fields"]
        for event in ship._events
        if event.get("event") == "publish"
        and event.get("topic") == "/gnc/active_route"
        and event["message"]["fields"].get("route_type") == "internal_return_to_route"
    ]
    assert internal, "expected the manager's internal return route"
    assert request["latitude"][:1] == internal[-1]["latitude"][:1]  # verbatim mirror prefix
    assert "avoidance" in request["navigation_mode"]
    coordinate = _coordinate_feedback(bridge)
    assert coordinate["accepted"] is True


def test_unadmittable_splices_are_held_not_published(original_ship, monkeypatch):
    """Splices that would fail the frozen gates are never published or latched."""
    ship = original_ship
    ship.stack.advance(11)
    ship._sync_state()
    data = _vo_intent()
    bridge = _mount(ship, data)
    real_build = plan_bridge_module.build_avoidance_route

    def unadmittable_build(*args: object, **kwargs: object) -> dict:
        return {**real_build(*args, **kwargs), "gate_clean": False}

    monkeypatch.setattr(plan_bridge_module, "build_avoidance_route", unadmittable_build)
    bridge.submit(11)  # first build unadmittable: nothing is published or latched
    assert not [row for row in ship.requested_plans if row["kind"] == "avoidance"]
    assert bridge.admission_metrics["submitted"] == 0

    monkeypatch.setattr(plan_bridge_module, "build_avoidance_route", real_build)
    bridge.submit(11)
    held_id = ship.requested_plans[-1]["message"]["plan_id"]
    assert _coordinate_feedback(bridge)["accepted"] is True

    monkeypatch.setattr(plan_bridge_module, "build_avoidance_route", unadmittable_build)
    data["planner"]["selected_command"]["course_rad"] = 0.5
    data["planner"]["solve_id"] = 2
    ship.stack.advance(0.1)
    ship._sync_state()
    bridge.submit(11.2)  # unadmittable rebuild: the held splice keeps flying
    assert ship.requested_plans[-1]["message"]["plan_id"] == held_id
    assert bridge.admission_metrics["rejected_addressable"] == 0


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
    """colav.mid_mpc.receipt@1 names the authority cycle "sequence"; the canonical
    accepted-plan-receipt schema names it "accepted_sequence". The bridge must
    accept both, as threat management already does.
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


def test_held_intent_sampling_noise_does_not_spawn_generations(original_ship):
    """Held-tick course sampling differs from the solve by ULP-level wrap noise.

    Exact-equality intent comparison declared a new intent every tick
    (fan-HO-E4: 22 splice generations in 50 s, 49 in one cell). Held intents
    must keep one geometry generation across wrap-stable sampling noise.
    """
    ship = original_ship
    ship.stack.advance(11)
    ship._sync_state()
    data = _vo_intent()
    bridge = _mount(ship, data)
    bridge.submit(11)
    first = _avoidance_requests(ship)[-1]["message"]
    data["planner"]["solver_executed"] = False  # held ticks: no fresh solve, validity untouched
    for index, offset in enumerate((1e-9, -1e-9, 2 * math.pi - 1e-12)):
        data["planner"]["selected_command"]["course_rad"] = 0.2 + offset
        ship.stack.advance(0.1)
        ship._sync_state()
        bridge.submit(11.2 + index * 0.1)
    assert bridge._candidate_generation == 1
    assert bridge._intent_generation == 1
    assert _avoidance_requests(ship)[-1]["message"]["plan_id"] == first["plan_id"] == "vo-held-intent-1"
    assert len(_avoidance_requests(ship)) == 1


def test_speed_command_updates_reach_the_route_without_new_geometry(original_ship):
    """Planner speed changes ride the latched splice; geometry generations do not.

    With sampling noise eliminated, exact geometry rebuilds no longer carry
    speed updates by accident: a held line with a new commanded speed must be
    republished with the new deviation speeds under the same generation.
    """
    ship = original_ship
    ship.stack.advance(11)
    ship._sync_state()
    data = _vo_intent()
    bridge = _mount(ship, data)
    bridge.submit(11)
    data["planner"]["selected_command"]["speed_mps"] = 6.0
    data["planner"]["solve_id"] = 2
    ship.stack.advance(0.1)
    ship._sync_state()
    bridge.submit(11.2)
    request = _avoidance_requests(ship)[-1]["message"]
    assert bridge._candidate_generation == 1
    modes = request["navigation_mode"]
    first_avoidance = modes.index("avoidance")
    last_avoidance = len(modes) - 1 - modes[::-1].index("avoidance")
    deviation_speeds = [round(value, 6) for value in request["command_speed_mps"][first_avoidance : last_avoidance + 1]]
    assert set(deviation_speeds) == {6.0}
    assert _coordinate_feedback(bridge)["accepted"] is True


def test_internal_return_reference_is_sanitized_and_recovery_is_admitted(original_ship):
    """After an internal return, later intents must splice past the sub-floor leg.

    vo-OT-E0 t=273: the manager's internal return route opened with a 5.5 m leg;
    every later splice inherited it, gate_clean stayed False and every further
    VO intent was dropped silently until the planner went infeasible.
    """
    ship = original_ship
    ship.stack.advance(11)
    ship._sync_state()
    data = _vo_intent()
    bridge = _mount(ship, data)
    bridge.submit(11)
    data["planner"]["algorithm_details"].update(hard_constraint_count=0, active_rules={}, give_way_commitment_active=False)
    ship.stack.advance(0.1)
    ship._sync_state()
    bridge.submit(11.2)  # constraints clear: return_to_route; manager publishes its internal return
    assert ship.stack.states["active_route_manager_node"]["active_avoidance"] is False
    internal = [
        event["message"]["fields"]
        for event in ship._events
        if event.get("event") == "publish"
        and event.get("topic") == "/gnc/active_route"
        and event["message"]["fields"].get("route_type") == "internal_return_to_route"
    ]
    assert internal
    data["planner"]["algorithm_details"].update(
        hard_constraint_count=1, active_rules={"1": ["HO"]}, give_way_commitment_active=True
    )
    data["planner"]["solver_executed"] = True
    data["planner"]["solve_id"] = 2
    ship.stack.advance(0.1)
    ship._sync_state()
    bridge.submit(11.3)
    request = _avoidance_requests(ship)[-1]["message"]
    points = ship.frame.northeast(request["latitude"], request["longitude"])
    gaps = np.linalg.norm(np.diff(points, axis=1), axis=0)
    assert gaps.min() >= 30.0  # the 5.5 m internal-return head leg never reaches a submission
    assert _coordinate_feedback(bridge)["accepted"] is True
    assert bridge.admission_metrics["holds"] == 0


def test_unadmittable_intents_are_telemetered_not_dropped_silently(original_ship, monkeypatch):
    """Every held intent the bridge cannot admit leaves a hold record with a reason."""
    ship = original_ship
    ship.stack.advance(11)
    ship._sync_state()
    data = _vo_intent()
    bridge = _mount(ship, data)
    real_build = plan_bridge_module.build_avoidance_route

    def unadmittable_build(*args: object, **kwargs: object) -> dict:
        return {**real_build(*args, **kwargs), "gate_clean": False}

    monkeypatch.setattr(plan_bridge_module, "build_avoidance_route", unadmittable_build)
    bridge.submit(11)
    assert not _avoidance_requests(ship)
    assert bridge.admission_metrics["holds"] == 1
    holds = [event for event in ship._events if event.get("event") == "bridge_hold"]
    assert len(holds) == 1 and holds[0]["reason"]


def test_static_only_evidence_keeps_nominal_cruise_on_deviation_legs(original_ship):
    """Static-hazard-only deviations tag only the entry leg avoidance.

    vo-HO-E0 t=296-924: static hazard grid cells kept the deviation tagged
    avoidance with no dynamic target risk, so the frozen 3.2 m/s guidance cap
    applied for 600 s of pure transit and the goal was missed at the time limit.
    """
    ship = original_ship
    ship.stack.advance(11)
    ship._sync_state()
    data = _vo_static_only_intent()
    bridge = _mount(ship, data)
    bridge.submit(11)
    request = _avoidance_requests(ship)[-1]["message"]
    modes = request["navigation_mode"]
    first_avoidance = modes.index("avoidance")
    assert modes[0] == "cruise" and modes[-1] == "dp_hold"
    assert modes.count("avoidance") == 1  # entry leg only: admission tier, no cap exposure
    assert first_avoidance == bridge._candidate["prefix_length"]  # the tag is the deviation entry waypoint
    assert _coordinate_feedback(bridge)["accepted"] is True
