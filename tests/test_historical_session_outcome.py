from __future__ import annotations

from types import SimpleNamespace

from colav_simulator.experiment.contracts import SessionState
from colav_simulator.experiment.session import SimulationSession


class _OneStepSimulator:
    def __init__(self) -> None:
        self.t = 0.0
        self.t_end = 1.0

    def initialize_scenario_episode(self, **_kwargs) -> None:
        return None

    def step(self) -> dict:
        self.t = self.t_end
        return {}

    def detect_ship_collisions(self, _ship_id: int) -> list:
        return []

    def determine_ship_grounding(self, _ship_id: int) -> bool:
        return False

    def determine_ship_goal_reached(self, _ship_id: int) -> bool:
        return False


class _HistoricalReferenceShip:
    id = 0
    counterfactual_phase = "HISTORICAL_REFERENCE"

    def get_ship_info(self) -> dict:
        return {"id": self.id}


def test_full_historical_window_reports_handoff_not_triggered() -> None:
    session = SimulationSession(
        simulator=_OneStepSimulator(),
        ship_list=[_HistoricalReferenceShip()],
        config=SimpleNamespace(name="historical_lifecycle_counterfactual", dt_sim=1.0),
        enc=SimpleNamespace(),
        threat_management_coordinator=object(),
    )
    session.threat_management_coordinator = None

    session.start()
    snapshot = session.advance()

    event = next(item for item in snapshot.events if item["type"] == "historical_handoff_not_triggered")
    assert event["details"] == {
        "reason": "HANDOFF_NOT_TRIGGERED",
        "counterfactual_avoidance": "NOT_EXECUTED",
    }
    assert snapshot.state is SessionState.FINISHED


def test_operational_events_keep_session_history_without_successful_solves() -> None:
    session = SimulationSession(
        simulator=_OneStepSimulator(),
        ship_list=[_HistoricalReferenceShip()],
        config=SimpleNamespace(name="head_on", dt_sim=1.0),
        enc=SimpleNamespace(),
        threat_management_coordinator=None,
    )

    session.start()
    session._event(
        "planner_solved",
        ship_id=0,
        planner={"solve_id": 1, "status": "SUCCESS", "feasible": True},
    )
    session._event("threat_lifecycle_active", target_id=1, generation=0)
    session.pause()
    session.start()

    assert [event["type"] for event in session.operational_events] == [
        "session_started",
        "session_paused",
        "session_resumed",
    ]
    assert [event["event_id"] for event in session.operational_events] == [1, 4, 5]


def test_canonical_threat_events_and_avoidance_actions_enter_operational_history_once() -> None:
    session = SimulationSession(
        simulator=_OneStepSimulator(),
        ship_list=[_HistoricalReferenceShip()],
        config=SimpleNamespace(name="head_on", dt_sim=1.0),
        enc=SimpleNamespace(),
        threat_management_coordinator=None,
    )
    key = SimpleNamespace(target_id=2, generation=3)
    schedule_event = SimpleNamespace(
        event_id=1,
        sim_time_s=5.0,
        event_type="THREAT_ENTERED",
        key=key,
        reason="current_required_obligation",
        from_context=None,
        to_context=SimpleNamespace(value="CURRENT_PRIMARY"),
        predicted=False,
    )
    lifecycle_event = SimpleNamespace(
        event_id=7,
        sim_time_s=5.0,
        event_type="TARGET_TRANSITION",
        target_key=key,
        from_state="MONITORING/NONE/NONE",
        to_state="ACTIVE/COMMITTED/NONE",
        reason=None,
    )
    vector = SimpleNamespace(
        key=key,
        avoidance_action_active=True,
        display_class=SimpleNamespace(value="HIGH"),
        dcpa_m=42.0,
        tcpa_forward_s=18.0,
        range_m=320.0,
        lifecycle=SimpleNamespace(
            encounter=SimpleNamespace(value="HEAD_ON"),
            role=SimpleNamespace(value="GIVE_WAY"),
            risk=SimpleNamespace(value="ACTIVE"),
            commitment=SimpleNamespace(value="COMMITTED"),
        ),
    )
    snapshot = SimpleNamespace(
        epoch="run-1",
        sequence=5,
        events=(schedule_event,),
        lifecycle_snapshot=SimpleNamespace(events=(lifecycle_event,)),
        vectors=(vector,),
        schedule=SimpleNamespace(current_primary=key),
    )
    session.threat_management_coordinator = SimpleNamespace(last_snapshot=snapshot)

    first = session._record_threat_management_events()
    repeated = session._record_threat_management_events()

    assert [event["type"] for event in first] == [
        "threat_entered",
        "target_transition",
        "avoidance_action_started",
    ]
    assert repeated == []
    assert session.operational_events == first


def test_planner_failures_and_recovery_are_operational_transitions_not_solve_spam() -> None:
    session = SimulationSession(
        simulator=_OneStepSimulator(),
        ship_list=[_HistoricalReferenceShip()],
        config=SimpleNamespace(name="head_on", dt_sim=1.0),
        enc=SimpleNamespace(),
        threat_management_coordinator=None,
    )

    def payload(solve_id: int, *, feasible: bool) -> dict:
        return {
            "Ship0": {
                "id": 0,
                "colav": {
                    "planner": {
                        "solver_executed": True,
                        "solve_id": solve_id,
                        "sim_time": float(solve_id),
                        "status": "SUCCESS" if feasible else "FAILED",
                        "feasible": feasible,
                        "algorithm_details": {},
                    }
                },
            }
        }

    session._planner_events(payload(1, feasible=False))
    session._planner_events(payload(2, feasible=False))
    session._planner_events(payload(3, feasible=True))
    session._planner_events(payload(4, feasible=True))

    assert [event["type"] for event in session.operational_events] == [
        "planner_failed",
        "planner_recovered",
    ]


def test_same_context_priority_churn_is_suppressed_and_emergency_is_latched() -> None:
    session = SimulationSession(
        simulator=_OneStepSimulator(),
        ship_list=[_HistoricalReferenceShip()],
        config=SimpleNamespace(name="head_on", dt_sim=1.0),
        enc=SimpleNamespace(),
        threat_management_coordinator=None,
    )
    key = SimpleNamespace(target_id=1, generation=0)
    vector = SimpleNamespace(
        key=key,
        avoidance_action_active=False,
        display_class=SimpleNamespace(value="LOW"),
        priority_class=SimpleNamespace(value="UNKNOWN"),
        dcpa_m=50.0,
        tcpa_forward_s=20.0,
        range_m=300.0,
        lifecycle=None,
    )

    def record(sequence: int, reason: str, priority: str) -> list[dict]:
        vector.priority_class = SimpleNamespace(value=priority)
        event = SimpleNamespace(
            event_id=1,
            sim_time_s=float(sequence),
            event_type="THREAT_ESCALATED",
            key=key,
            reason=reason,
            from_context=SimpleNamespace(value="CURRENT_PRIMARY"),
            to_context=SimpleNamespace(value="CURRENT_PRIMARY"),
            predicted=True,
        )
        session.threat_management_coordinator = SimpleNamespace(
            last_snapshot=SimpleNamespace(
                epoch="run-1",
                sequence=sequence,
                events=(event,),
                lifecycle_snapshot=SimpleNamespace(events=()),
                vectors=(vector,),
                schedule=SimpleNamespace(current_primary=key),
            )
        )
        return session._record_threat_management_events()

    assert record(1, "threat_evidence_unknown", "UNKNOWN") == []
    assert [event["type"] for event in record(2, "response_time_emergency", "RESPONSE_TIME_EMERGENCY")] == [
        "threat_escalated"
    ]
    assert record(3, "threat_evidence_unknown", "UNKNOWN") == []
    assert record(4, "response_time_emergency", "RESPONSE_TIME_EMERGENCY") == []


def test_canonical_risk_colregs_and_observation_transitions_are_recorded() -> None:
    session = SimulationSession(
        simulator=_OneStepSimulator(),
        ship_list=[_HistoricalReferenceShip()],
        config=SimpleNamespace(name="head_on", dt_sim=1.0),
        enc=SimpleNamespace(),
        threat_management_coordinator=None,
    )
    key = SimpleNamespace(target_id=4, generation=1)
    lifecycle = SimpleNamespace(
        encounter=SimpleNamespace(value="HEAD_ON"),
        role=SimpleNamespace(value="GIVE_WAY"),
        risk=SimpleNamespace(value="MONITORING"),
        commitment=SimpleNamespace(value="NONE"),
    )
    vector = SimpleNamespace(
        key=key,
        avoidance_action_active=False,
        display_class=SimpleNamespace(value="LOW"),
        priority_class=SimpleNamespace(value="MONITOR"),
        observation_health=SimpleNamespace(value="UPDATED"),
        dcpa_m=80.0,
        tcpa_forward_s=30.0,
        range_m=500.0,
        lifecycle=lifecycle,
    )

    def record(sequence: int) -> list[dict]:
        session.threat_management_coordinator = SimpleNamespace(
            last_snapshot=SimpleNamespace(
                epoch="run-1",
                sequence=sequence,
                events=(),
                lifecycle_snapshot=SimpleNamespace(events=()),
                vectors=(vector,),
                schedule=SimpleNamespace(current_primary=key),
            )
        )
        return session._record_threat_management_events()

    assert record(1) == []
    vector.display_class = SimpleNamespace(value="HIGH")
    vector.observation_health = SimpleNamespace(value="DEGRADED")
    lifecycle.encounter = SimpleNamespace(value="CROSSING_GIVE_WAY")
    lifecycle.role = SimpleNamespace(value="GIVE_WAY")
    assert [event["type"] for event in record(2)] == [
        "risk_level_changed",
        "colregs_changed",
        "observation_degraded",
    ]
    vector.observation_health = SimpleNamespace(value="UPDATED")
    assert [event["type"] for event in record(3)] == ["observation_recovered"]


def test_primary_switch_coalesces_its_primary_context_reorder_events() -> None:
    session = SimulationSession(
        simulator=_OneStepSimulator(),
        ship_list=[_HistoricalReferenceShip()],
        config=SimpleNamespace(name="head_on", dt_sim=1.0),
        enc=SimpleNamespace(),
        threat_management_coordinator=None,
    )
    old_key = SimpleNamespace(target_id=1, generation=0)
    new_key = SimpleNamespace(target_id=2, generation=0)
    session._last_primary_track_key = (1, 0)

    def schedule_event(
        event_id: int,
        key: object,
        from_context: str | None,
        to_context: str | None,
        event_type: str,
    ) -> SimpleNamespace:
        return SimpleNamespace(
            event_id=event_id,
            sim_time_s=5.0,
            event_type=event_type,
            key=key,
            reason="primary_changed",
            from_context=None if from_context is None else SimpleNamespace(value=from_context),
            to_context=None if to_context is None else SimpleNamespace(value=to_context),
            predicted=False,
        )

    session.threat_management_coordinator = SimpleNamespace(
        last_snapshot=SimpleNamespace(
            epoch="run-1",
            sequence=5,
            events=(
                schedule_event(1, old_key, "CURRENT_PRIMARY", "CONCURRENT_REQUIRED", "SCHEDULE_REORDER"),
                schedule_event(2, new_key, "CONCURRENT_REQUIRED", "CURRENT_PRIMARY", "SCHEDULE_REORDER"),
                schedule_event(3, new_key, None, None, "PRIMARY_SWITCHED"),
            ),
            lifecycle_snapshot=SimpleNamespace(events=()),
            vectors=(),
            schedule=SimpleNamespace(current_primary=new_key),
        )
    )

    recorded = session._record_threat_management_events()

    assert [event["type"] for event in recorded] == ["primary_switched"]
    assert recorded[0]["details"]["from_target_id"] == 1
    assert recorded[0]["details"]["to_target_id"] == 2
