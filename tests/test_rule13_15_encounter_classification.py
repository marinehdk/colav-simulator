import numpy as np
import pytest

from colav_simulator.evaluation.encounter import (
    RULE_BY_ENCOUNTER,
    EncounterMonitor,
    classify_geometry,
    stage_timeline,
    velocity_ne,
)


@pytest.mark.parametrize(
    ("own_position", "own_speed", "own_course_deg", "target_position", "target_speed", "target_course_deg", "expected"),
    (
        ((0.0, 0.0), 7.0, 0.0, (1000.0, 0.0), 7.0, 180.0, "head_on"),
        ((0.0, 0.0), 8.0, 0.0, (500.0, 0.0), 5.0, 0.0, "overtaking"),
        ((0.0, 0.0), 5.0, 0.0, (-500.0, 0.0), 8.0, 0.0, "overtaken"),
        ((0.0, 0.0), 7.0, 0.0, (500.0, 500.0), 7.0, 270.0, "crossing_give_way"),
        ((0.0, 0.0), 7.0, 0.0, (500.0, -500.0), 7.0, 90.0, "crossing_stand_on"),
    ),
)
def test_p1_profile_classifies_standard_roles(
    own_position: tuple[float, float],
    own_speed: float,
    own_course_deg: float,
    target_position: tuple[float, float],
    target_speed: float,
    target_course_deg: float,
    expected: str,
) -> None:
    encounter, dcpa_m, tcpa_s, signed_tcpa_s, _ = classify_geometry(
        np.asarray(own_position),
        velocity_ne(own_speed, np.deg2rad(own_course_deg)),
        np.asarray(target_position),
        velocity_ne(target_speed, np.deg2rad(target_course_deg)),
        8.45,
        8.45,
    )

    assert encounter == expected
    assert dcpa_m <= 1.0
    assert tcpa_s == signed_tcpa_s > 0.0
    assert RULE_BY_ENCOUNTER[encounter] in {"rule13", "rule14", "rule15"}


def test_p1_profile_clears_post_cpa_geometry() -> None:
    encounter, _, tcpa_s, signed_tcpa_s, _ = classify_geometry(
        np.array([0.0, 0.0]),
        velocity_ne(7.0, 0.0),
        np.array([-100.0, 0.0]),
        velocity_ne(7.0, np.pi),
        8.45,
        8.45,
    )

    assert encounter == "clear"
    assert tcpa_s == 0.0
    assert signed_tcpa_s < 0.0


def test_p1_stage_timeline_and_monitor_reach_post_cpa_stage() -> None:
    timeline = stage_timeline(
        times=np.array([0.0, 1.0, 2.0, 3.0]),
        distance=np.array([100.0, 20.0, 10.0, 30.0]),
        cpa_index=2,
        safety_distance=10.0,
    )
    assert timeline[-1] == {"time_s": 3.0, "stage": 3}

    monitor = EncounterMonitor("rule13")
    before = monitor.update(
        [
            {"id": 0, "north": 0.0, "east": 0.0, "psi": 0.0, "u": 8.0, "v": 0.0, "length": 8.45},
            {"id": 1, "north": 20.0, "east": 0.0, "psi": 0.0, "u": 5.0, "v": 0.0, "length": 8.45},
        ]
    )
    after = monitor.update(
        [
            {"id": 0, "north": 30.0, "east": 0.0, "psi": 0.0, "u": 8.0, "v": 0.0, "length": 8.45},
            {"id": 1, "north": 20.0, "east": 0.0, "psi": 0.0, "u": 5.0, "v": 0.0, "length": 8.45},
        ]
    )

    assert before[0].stage >= 1
    assert after[0].stage == 3
