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
