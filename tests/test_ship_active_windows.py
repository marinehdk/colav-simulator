from types import SimpleNamespace

import numpy as np

from colav_simulator.common.miscellaneous_helper_methods import (
    extract_do_states_from_ship_list,
    ship_is_active,
)


def _ship(identifier: int, start: float, end: float) -> SimpleNamespace:
    return SimpleNamespace(
        id=identifier,
        t_start=start,
        t_end=end,
        csog_state=np.array([100.0 * identifier, 0.0, 4.0, 0.0]),
        length=12.0,
        width=4.0,
    )


def test_ship_active_window_is_half_open() -> None:
    ship = _ship(1, 10.0, 20.0)

    assert ship_is_active(ship, 9.9) is False
    assert ship_is_active(ship, 10.0) is True
    assert ship_is_active(ship, 19.9) is True
    assert ship_is_active(ship, 20.0) is False


def test_expired_ship_is_removed_from_truth_tracks() -> None:
    ships = [_ship(0, 0.0, 100.0), _ship(1, 10.0, 20.0)]

    assert [item[0] for item in extract_do_states_from_ship_list(15.0, ships)] == [0, 1]
    assert [item[0] for item in extract_do_states_from_ship_list(20.0, ships)] == [0]
