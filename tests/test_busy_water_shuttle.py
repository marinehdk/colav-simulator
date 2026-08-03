import numpy as np
import pytest

from colav_simulator.simulator import advance_scripted_shuttle


class ShuttleShip:
    def __init__(self, position: float, course_rad: float = 0.0) -> None:
        self.id = 1
        self.t_start = 0.0
        self.waypoints = np.array([[0.0, 100.0], [0.0, 0.0]])
        self._state = np.array([position, 0.0, 10.0, course_rad])

    @property
    def csog_state(self) -> np.ndarray:
        return self._state.copy()

    def set_initial_state(self, state: np.ndarray, *, t_start: float) -> None:
        self._state = np.asarray(state, dtype=float).copy()


def test_shuttle_reflects_overshoot_and_reverses_course() -> None:
    ship = ShuttleShip(95.0)

    advance_scripted_shuttle(ship, 1.0)

    assert ship.csog_state[0] == pytest.approx(95.0)
    assert abs(ship.csog_state[3]) == pytest.approx(np.pi)
    assert ship.csog_state[2] == pytest.approx(10.0)


def test_shuttle_handles_multiple_reflections_without_speed_drift() -> None:
    ship = ShuttleShip(25.0)

    advance_scripted_shuttle(ship, 47.5)

    assert ship.csog_state[0] == pytest.approx(100.0)
    assert ship.csog_state[2] == pytest.approx(10.0)
