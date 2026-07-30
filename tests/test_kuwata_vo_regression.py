from __future__ import annotations

import numpy as np
import pytest
from shapely.geometry import box

from colav_simulator.common.miscellaneous_helper_methods import check_if_vessel_is_passed_by
from colav_simulator.core.colav.kuwata_vo_alg.kuwata_vo import (
    VO,
    VOCOLREGSSituation,
    VOParams,
)


def test_candidate_velocity_grid_uses_absolute_speed_in_both_axes() -> None:
    planner = VO(VOParams(Q=np.eye(2)))
    planner._speed_set = np.array([4.0, 6.0])
    planner._heading_set = np.array([0.0, np.pi / 2.0])
    planner._violation_costs = np.zeros((2, 2))
    planner._total_costs = np.zeros((2, 2))

    heading, speed = planner._compute_optimal_controls(
        v_ref=np.array([0.0, 6.0]),
        psi_os=0.0,
    )

    assert heading == pytest.approx(np.pi / 2.0)
    assert speed == pytest.approx(6.0)
    assert planner._total_costs[1, 1] == pytest.approx(0.0)


def test_pre_collision_check_rejects_past_cpa() -> None:
    planner = VO(VOParams(t_max=60.0, d_min=20.0))

    assert not planner._precollision_check(
        p_os=np.array([0.0, 0.0]),
        v_os=np.array([5.0, 0.0]),
        p_do=np.array([-10.0, 0.0]),
        v_do=np.array([0.0, 0.0]),
    )


def test_passed_by_requires_clearance_for_both_heading_branches() -> None:
    assert not check_if_vessel_is_passed_by(
        p_os=np.array([0.0, 0.0]),
        v_os=np.array([5.0, 0.0]),
        p_do=np.array([-10.0, 0.0]),
        v_do=np.array([0.0, 0.0]),
        threshold_distance=50.0,
    )


def test_moving_target_vo_ray_uses_relative_velocity() -> None:
    planner = VO()
    planner._speed_set = np.array([0.0])
    planner._heading_set = np.array([0.0])
    planner._violation_costs = np.zeros((1, 1))
    planner._total_costs = np.zeros((1, 1))
    obstacle = box(9.0, -1.0, 11.0, 1.0)

    planner._update_violation_costs(
        VOCOLREGSSituation.CR_PS,
        obstacle,
        obstacle,
        p_do=np.array([10.0, 0.0]),
        v_do=np.array([5.0, 0.0]),
        p_os=np.array([0.0, 0.0]),
        v_os=np.array([5.0, 0.0]),
        psi_os=0.0,
    )

    assert planner._violation_costs[0, 0] == 0.0


def test_later_target_cannot_reduce_existing_collision_penalty() -> None:
    planner = VO()
    planner._speed_set = np.array([5.0])
    planner._heading_set = np.array([0.0])
    planner._violation_costs = np.zeros((1, 1))
    planner._total_costs = np.zeros((1, 1))

    collision = box(9.0, -1.0, 11.0, 1.0)
    planner._update_violation_costs(
        VOCOLREGSSituation.CR_PS,
        collision,
        collision,
        p_do=np.array([10.0, 0.0]),
        v_do=np.zeros(2),
        p_os=np.zeros(2),
        v_os=np.array([5.0, 0.0]),
        psi_os=0.0,
    )
    assert np.isinf(planner._violation_costs[0, 0])

    no_collision = box(100.0, 100.0, 101.0, 101.0)
    planner._update_violation_costs(
        VOCOLREGSSituation.HO,
        no_collision,
        no_collision,
        p_do=np.array([0.0, 10.0]),
        v_do=np.zeros(2),
        p_os=np.zeros(2),
        v_os=np.array([5.0, 0.0]),
        psi_os=0.0,
    )

    assert np.isinf(planner._violation_costs[0, 0])


@pytest.mark.parametrize(
    ("own_position", "own_heading", "target_position", "target_heading", "expected"),
    (
        (
            np.array([0.0, 0.0]),
            0.0,
            np.array([100.0, 0.0]),
            np.pi,
            VOCOLREGSSituation.HO,
        ),
        (
            np.array([0.0, 0.0]),
            0.0,
            np.array([100.0, 0.0]),
            0.0,
            VOCOLREGSSituation.OT_ing,
        ),
        (
            np.array([0.0, 0.0]),
            0.0,
            np.array([-100.0, 0.0]),
            0.0,
            VOCOLREGSSituation.OT_en,
        ),
        (
            np.array([0.0, 0.0]),
            0.0,
            np.array([0.0, 100.0]),
            -np.pi / 2.0,
            VOCOLREGSSituation.CR_SS,
        ),
        (
            np.array([0.0, 0.0]),
            0.0,
            np.array([0.0, -100.0]),
            np.pi / 2.0,
            VOCOLREGSSituation.CR_PS,
        ),
    ),
)
def test_vo_colreg_situation_keeps_standard_roles(
    own_position: np.ndarray,
    own_heading: float,
    target_position: np.ndarray,
    target_heading: float,
    expected: VOCOLREGSSituation,
) -> None:
    planner = VO()

    result = planner._determine_colregs_situation(
        own_position,
        own_heading,
        target_position,
        target_heading,
    )

    assert result == expected
