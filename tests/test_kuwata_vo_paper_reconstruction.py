from __future__ import annotations

import time
from types import SimpleNamespace

import numpy as np
import pytest
from shapely.geometry import Polygon, box

from colav_simulator.core.colav.colav_interface import Config, LayerConfig, VOWrapper
from colav_simulator.core.colav.diagnostics import PlanStatus
from colav_simulator.core.colav.kuwata_vo_alg.kuwata_vo import (
    VO,
    VOCOLREGSSituation,
    VOParams,
    compute_minkowski_sum,
    compute_reflection,
    ray_polygon_ttc_grid,
)
from colav_simulator.core.guidances import LOSGuidanceParams
from colav_simulator.integrations.registry import IntegrationRegistry


def _own_state(
    *,
    speed: float = 5.0,
    heading: float = 0.0,
    position: tuple[float, float] = (0.0, 0.0),
) -> np.ndarray:
    return np.array([*position, heading, speed, 0.0, 0.0])


def _track(
    track_id: int,
    position: tuple[float, float],
    velocity: tuple[float, float],
    *,
    length: float = 10.0,
    width: float = 5.0,
) -> tuple[int, np.ndarray, np.ndarray, float, float]:
    state = np.array([*position, *velocity], dtype=float)
    return track_id, state, np.eye(4), length, width


def test_default_grid_matches_published_32_by_128_structure() -> None:
    planner = VO()

    assert planner._speed_set.shape == (32,)
    assert planner._heading_set.shape == (128,)
    assert planner._heading_set[0] == pytest.approx(-np.pi)
    assert planner._heading_set[-1] < np.pi
    assert planner._params.t_max == pytest.approx(120.0)
    assert planner._params.d_min == pytest.approx(100.0)
    assert planner._params.hard_hull_clearance_m == pytest.approx(50.0)
    assert planner._params.preferred_hull_clearance_m == pytest.approx(100.0)


def test_clearance_thresholds_reject_invalid_ordering() -> None:
    with pytest.raises(ValueError, match="preferred_hull_clearance_m"):
        VOParams(hard_hull_clearance_m=100.0, preferred_hull_clearance_m=50.0)


def test_hard_clearance_uses_hull_edge_distance() -> None:
    params = VOParams(
        speed_samples=3,
        heading_samples=8,
        velocity_uncertainty_vertices_mps=[[0.0, 0.0]],
    )
    unsafe = VO(params)
    safe = VO(params)

    unsafe.plan(
        0.0,
        np.array([5.0, 0.0]),
        _own_state(),
        [_track(1, (100.0, 59.0), (0.5, 0.0), width=10.0)],
        os_length=45.0,
        os_width=10.0,
    )
    safe.plan(
        0.0,
        np.array([5.0, 0.0]),
        _own_state(),
        [_track(1, (100.0, 61.0), (0.5, 0.0), width=10.0)],
        os_length=45.0,
        os_width=10.0,
    )

    speed_index = int(np.argmin(abs(unsafe._speed_set - 5.0)))
    heading_index = int(np.argmin(abs(unsafe._heading_set)))
    assert unsafe._hard_constraint_mask[speed_index, heading_index]
    assert not safe._hard_constraint_mask[speed_index, heading_index]


def test_plan_accounts_for_ownship_turn_and_speed_dynamics_in_hard_clearance() -> None:
    planner = VO(VOParams(velocity_uncertainty_vertices_mps=[[0.0, 0.0]]))
    target = _track(3, (300.0, 0.0), (-6.9, 0.0), length=12.0, width=4.0)

    plan = planner.plan(
        0.0,
        np.array([6.9, 0.0]),
        _own_state(speed=6.9),
        [target],
        os_length=45.0,
        os_width=8.0,
        os_course_time_constant_s=3.0,
        os_speed_time_constant_s=5.0,
        os_max_turn_rate_radps=np.deg2rad(4.0),
    )

    position = np.zeros(2)
    heading = 0.0
    speed = 6.9
    minimum_clearance = np.inf
    dt = 0.05
    combined_hull_radius = (
        0.5 * np.hypot(45.0, 8.0) + 0.5 * np.hypot(12.0, 4.0)
    )
    for step in range(round(planner._params.t_max / dt) + 1):
        target_position = np.array([300.0 - 6.9 * step * dt, 0.0])
        minimum_clearance = min(
            minimum_clearance,
            np.linalg.norm(position - target_position) - combined_hull_radius,
        )
        position += speed * np.array([np.cos(heading), np.sin(heading)]) * dt
        course_error = (plan[2, 0] - heading + np.pi) % (2.0 * np.pi) - np.pi
        heading += np.clip(
            course_error / 3.0,
            -np.deg2rad(4.0),
            np.deg2rad(4.0),
        ) * dt
        speed += (plan[3, 0] - speed) / 5.0 * dt

    assert planner.feasible
    assert minimum_clearance >= 50.0


def test_preferred_clearance_penalizes_but_does_not_forbid_safe_candidate() -> None:
    planner = VO(
        VOParams(
            speed_samples=3,
            heading_samples=8,
            velocity_uncertainty_vertices_mps=[[0.0, 0.0]],
        )
    )

    planner.plan(
        0.0,
        np.array([5.0, 0.0]),
        _own_state(),
        [_track(1, (100.0, 80.0), (0.5, 0.0), width=10.0)],
        os_length=45.0,
        os_width=10.0,
    )

    speed_index = int(np.argmin(abs(planner._speed_set - 5.0)))
    heading_index = int(np.argmin(abs(planner._heading_set)))
    assert not planner._hard_constraint_mask[speed_index, heading_index]
    assert planner._preferred_clearance_mask[speed_index, heading_index]


def test_minkowski_sum_expands_rectangular_footprints() -> None:
    target = box(9.0, -1.0, 11.0, 1.0)
    own_shape = box(-2.0, -0.5, 2.0, 0.5)

    expanded = compute_minkowski_sum(target, compute_reflection(own_shape))

    assert expanded.bounds == pytest.approx((7.0, -1.5, 13.0, 1.5))


def test_first_intersection_ttc_uses_relative_ray() -> None:
    obstacle = box(9.0, -1.0, 11.0, 1.0)
    velocities = np.array([[[3.0, 0.0], [-1.0, 0.0]]])

    ttc = ray_polygon_ttc_grid(obstacle, np.zeros(2), velocities)

    assert ttc[0, 0] == pytest.approx(3.0)
    assert np.isinf(ttc[0, 1])


def test_colregs_v1_v2_v3_partition_candidate_velocity_space() -> None:
    candidates = np.array([[[1.0, -1.0], [1.0, 1.0], [-1.0, 0.0]]])

    v1, v2, v3 = VO._colregs_velocity_regions(
        rel_position=np.array([10.0, 0.0]),
        candidates=candidates,
        v_do=np.zeros(2),
        uncertainty=np.zeros((1, 2)),
    )

    np.testing.assert_array_equal(v1, [[True, False, False]])
    np.testing.assert_array_equal(v2, [[False, True, False]])
    np.testing.assert_array_equal(v3, [[False, False, True]])
    np.testing.assert_array_equal(v1 | v2 | v3, np.ones((1, 3), dtype=bool))


@pytest.mark.parametrize(
    ("target_position", "expected"),
    (
        ((60.0, 20.0), True),
        ((60.0, -20.0), True),
        ((60.0, 20.0001), False),
        ((-10.0, 0.0), False),
    ),
)
def test_cpa_gate_includes_published_boundaries_and_rejects_past_cpa(
    target_position: tuple[float, float],
    expected: bool,
) -> None:
    planner = VO(VOParams(t_max=60.0, d_min=20.0))

    result = planner._precollision_check(
        np.zeros(2),
        np.array([1.0, 0.0]),
        np.asarray(target_position),
        np.zeros(2),
    )

    assert result is expected


def test_cpa_gate_has_no_additional_range_cutoff_for_rule_activation() -> None:
    planner = VO()
    target = _track(1, (400.0, 400.0), (0.0, -7.0))

    planner.plan(0.0, np.array([7.0, 0.0]), _own_state(speed=7.0), [target])

    assert planner.get_debug_data()["active_rules"] == {"1": ["CR_SS"]}


def test_rule_cpa_gate_uses_current_velocity_instead_of_los_reference() -> None:
    planner = VO(VOParams(t_max=120.0, d_min=20.0))
    target = _track(1, (100.0, 0.0), (-1.0, 0.0))

    planner.plan(0.0, np.array([0.0, 1.0]), _own_state(speed=1.0), [target])

    debug = planner.get_debug_data()
    assert debug["track_metrics"][1]["rule_dcpa_m"] == pytest.approx(0.0)
    assert debug["active_rules"] == {"1": ["HO"]}


def test_head_on_collision_course_is_not_limited_to_twenty_metre_track_corridor() -> None:
    planner = VO(VOParams(velocity_uncertainty_vertices_mps=[[0.0, 0.0]]))
    target = _track(7, (1000.0, 65.0), (-2.5, 0.0))

    planner.plan(0.0, np.array([6.0, 0.0]), _own_state(speed=6.0), [target])

    debug = planner.get_debug_data()
    assert debug["track_metrics"][7]["rule_dcpa_m"] == pytest.approx(65.0)
    assert debug["track_metrics"][7]["matched_rules"] == ["HO"]
    assert debug["active_rules"] == {"7": ["HO"]}
    assert debug["give_way_rule_locks"] == {"7": "HO"}
    assert debug["selected_heading_rad"] >= 0.0


def test_same_geometry_changes_cpa_gate_when_target_speed_changes() -> None:
    planner = VO(VOParams(t_max=120.0, d_min=50.0))
    own_position = np.zeros(2)
    own_velocity = np.array([5.0, 0.0])
    target_position = np.array([100.0, 100.0])

    assert not planner._precollision_check(
        own_position,
        own_velocity,
        target_position,
        np.array([0.0, -1.0]),
    )
    assert planner._precollision_check(
        own_position,
        own_velocity,
        target_position,
        np.array([0.0, -10.0]),
    )


def test_distant_stand_on_geometry_does_not_hold_a_previous_slow_speed() -> None:
    planner = VO(
        VOParams(
            speed_samples=8,
            heading_samples=32,
            velocity_uncertainty_vertices_mps=[[0.0, 0.0]],
        )
    )
    stand_on_target = _track(1, (1000.0, -1000.0), (0.0, 5.0))
    background_target = _track(2, (-2000.0, 1000.0), (0.0, 0.0))

    planner.plan(
        0.0,
        np.array([6.0, 0.0]),
        _own_state(speed=0.65),
        [stand_on_target, background_target],
    )

    debug = planner.get_debug_data()
    assert debug["track_metrics"][1]["matched_rules"] == ["CR_PS"]
    assert not debug["track_metrics"][1]["cpa_gate_eligible"]
    assert debug["active_rules"] == {}
    assert not debug["stand_on_hold_active"]
    assert debug["selected_speed_mps"] > 5.0


def test_risky_stand_on_encounter_still_holds_current_motion() -> None:
    planner = VO(
        VOParams(
            speed_samples=8,
            heading_samples=32,
            velocity_uncertainty_vertices_mps=[[0.0, 0.0]],
        )
    )
    target = _track(1, (100.0, -100.0), (0.0, 5.0))

    planner.plan(0.0, np.array([6.0, 0.0]), _own_state(speed=0.65), [target])

    debug = planner.get_debug_data()
    assert debug["track_metrics"][1]["cpa_gate_eligible"]
    assert debug["active_rules"] == {"1": ["CR_PS"]}
    assert debug["stand_on_hold_active"]


def test_imminent_stand_on_collision_uses_rule17_emergency_action() -> None:
    planner = VO(
        VOParams(
            speed_samples=8,
            heading_samples=32,
            velocity_uncertainty_vertices_mps=[[0.0, 0.0]],
        )
    )
    target = _track(1, (50.0, -50.0), (0.0, 5.0))

    planner.plan(0.0, np.array([6.0, 0.0]), _own_state(speed=6.0), [target])

    debug = planner.get_debug_data()
    assert debug["track_metrics"][1]["first_toc_s"] < 60.0
    assert debug["driving_target_id"] == 1
    assert debug["driving_rule"] == "CR_PS"
    assert debug["stand_on_emergency_active"]
    assert not debug["stand_on_hold_active"]


def test_imminent_target_preempts_remote_committed_target() -> None:
    planner = VO(
        VOParams(
            speed_samples=8,
            heading_samples=32,
            velocity_uncertainty_vertices_mps=[[0.0, 0.0]],
        )
    )
    remote_head_on = _track(1, (1000.0, 0.0), (-5.0, 0.0))
    imminent_stand_on = _track(2, (50.0, -50.0), (0.0, 5.0))

    planner.plan(
        0.0,
        np.array([6.0, 0.0]),
        _own_state(speed=6.0),
        [remote_head_on, imminent_stand_on],
    )

    debug = planner.get_debug_data()
    assert debug["driving_target_id"] == 2
    assert debug["driving_rule"] == "CR_PS"
    assert debug["stand_on_emergency_active"]


def test_crossing_commitment_blocks_port_candidates_until_rule_releases() -> None:
    planner = VO(
        VOParams(
            speed_samples=8,
            heading_samples=32,
            velocity_uncertainty_vertices_mps=[[0.0, 0.0]],
        )
    )
    target = _track(1, (100.0, 100.0), (0.0, -5.0))

    planner.plan(0.0, np.array([5.0, 0.0]), _own_state(), [target])

    assert planner.get_debug_data()["crossing_commitment_active"]
    assert planner.get_debug_data()["crossing_commitment_state"] == "CR_SS_COMMITTED"
    assert not planner.get_debug_data()["emergency_rule_relaxation"]
    candidates = planner._candidate_velocities()
    port_candidates = candidates[..., 1] < -planner._params.crossing_commitment_deadband_mps
    assert np.all(planner._hard_constraint_mask[port_candidates])
    reverse_candidates = candidates[..., 0] <= 0.0
    assert np.all(planner._hard_constraint_mask[reverse_candidates])

    previous_plan = planner.get_current_plan().copy()
    planner.plan(1.0, np.array([5.0, 0.0]), _own_state(heading=0.2), [target])
    selected_velocity = planner.get_current_plan()[3, 0] * np.array(
        [
            np.cos(planner.get_current_plan()[2, 0]),
            np.sin(planner.get_current_plan()[2, 0]),
        ]
    )
    previous_velocity = previous_plan[3, 0] * np.array(
        [np.cos(previous_plan[2, 0]), np.sin(previous_plan[2, 0])]
    )
    previous_starboard = np.array(
        [-np.sin(previous_plan[2, 0]), np.cos(previous_plan[2, 0])]
    )
    assert (selected_velocity - previous_velocity) @ previous_starboard >= -0.25

    clear_target = _track(1, (100.0, -100.0), (0.0, -5.0))
    for sim_time in (2.0, 3.0, 4.0):
        planner.plan(sim_time, np.array([5.0, 0.0]), _own_state(), [clear_target])
    assert not planner.get_debug_data()["crossing_commitment_active"]
    assert planner.get_debug_data()["crossing_commitment_state"] == "CLEAR"
    assert planner.get_debug_data()["track_metrics"][1]["crossing_release_count"] == 3
    assert not planner.get_debug_data()["track_metrics"][1]["dynamic_hazard_ignored"]

    planner.plan(5.0, np.array([5.0, 0.0]), _own_state(), [target])
    assert "CR_SS" not in planner.get_debug_data()["active_rules"].get("1", [])

    role_flipped_target = _track(1, (100.0, -100.0), (0.0, 5.0))
    planner.plan(6.0, np.array([5.0, 0.0]), _own_state(), [role_flipped_target])
    debug = planner.get_debug_data()
    assert debug["track_metrics"][1]["matched_rules"] == ["CR_PS"]
    assert debug["active_rules"].get("1", []) == []
    assert not debug["stand_on_hold_active"]


@pytest.mark.parametrize(
    ("rule", "target_velocity"),
    (
        (VOCOLREGSSituation.HO, (-5.0, 0.0)),
        (VOCOLREGSSituation.OT_ing, (2.0, 0.0)),
    ),
)
def test_give_way_commitment_survives_ownship_body_frame_corridor_exit(
    rule: VOCOLREGSSituation,
    target_velocity: tuple[float, float],
) -> None:
    planner = VO(
        VOParams(
            speed_samples=16,
            heading_samples=128,
            velocity_uncertainty_vertices_mps=[[0.0, 0.0]],
        )
    )
    target = _track(1, (600.0 if rule is VOCOLREGSSituation.HO else 300.0, 0.0), target_velocity)

    planner.plan(0.0, np.array([5.0, 0.0]), _own_state(), [target])
    first = planner.get_debug_data()
    assert first["give_way_rule_locks"] == (
        {} if rule is VOCOLREGSSituation.OT_ing else {"1": rule.name}
    )
    assert first["give_way_commitment_active"]
    assert first["selected_heading_rad"] >= (
        planner._params.overtaking_min_starboard_rad
        if rule is VOCOLREGSSituation.OT_ing
        else -1e-12
    )

    turned_state = _own_state(heading=np.deg2rad(7.0))
    planner.plan(1.0, np.array([5.0, 0.0]), turned_state, [target])
    debug = planner.get_debug_data()

    assert debug["track_metrics"][1]["matched_rules"] == (
        ["HO"] if rule is VOCOLREGSSituation.HO else []
    )
    assert debug["track_metrics"][1]["active_rules"] == [rule.name]
    assert debug["track_metrics"][1]["committed_rule"] == rule.name
    assert debug["give_way_commitment_active"]
    assert debug["selected_heading_rad"] >= -1e-12
    assert not debug["emergency_rule_relaxation"]


def test_give_way_commitment_preserves_speed_when_route_reference_points_port() -> None:
    planner = VO(
        VOParams(
            speed_samples=32,
            heading_samples=128,
            velocity_uncertainty_vertices_mps=[[0.0, 0.0]],
        )
    )
    target = _track(1, (600.0, 0.0), (-5.0, 0.0))
    planner.plan(0.0, np.array([5.0, 0.0]), _own_state(), [target])
    committed_heading = planner.get_debug_data()["selected_heading_rad"]

    route_return = 5.0 * np.array([np.cos(-0.8), np.sin(-0.8)])
    planner.plan(
        1.0,
        route_return,
        _own_state(heading=committed_heading),
        [_track(1, (590.0, 0.0), (-5.0, 0.0))],
    )

    debug = planner.get_debug_data()
    assert debug["give_way_rule_locks"] == {"1": "HO"}
    assert debug["selected_heading_rad"] >= committed_heading - 1e-12
    assert debug["selected_speed_mps"] >= 4.5


def test_give_way_commitment_releases_only_after_target_passes_clear(
) -> None:
    rule = VOCOLREGSSituation.HO
    target_velocity = (-5.0, 0.0)
    planner = VO(
        VOParams(
            speed_samples=8,
            heading_samples=32,
            velocity_uncertainty_vertices_mps=[[0.0, 0.0]],
            give_way_release_steps=3,
        )
    )
    target = _track(1, (600.0, 0.0), target_velocity)
    planner.plan(0.0, np.array([5.0, 0.0]), _own_state(), [target])

    for sim_time, north in ((1.0, -160.0), (2.0, -170.0), (3.0, -180.0)):
        planner.plan(sim_time, np.array([5.0, 0.0]), _own_state(), [_track(1, (north, 0.0), target_velocity)])
        assert planner.get_debug_data()["give_way_rule_locks"] == {"1": rule.name}

    planner.plan(4.0, np.array([5.0, 0.0]), _own_state(), [_track(1, (-190.0, 0.0), target_velocity)])
    debug = planner.get_debug_data()
    assert debug["give_way_rule_locks"] == {}
    assert not debug["give_way_commitment_active"]
    assert debug["completed_give_way_targets"] == [1]

    for sim_time in (5.0, 6.0, 7.0):
        planner.plan(
            sim_time,
            np.array([5.0, 0.0]),
            _own_state(),
            [_track(1, (-400.0, 0.0), target_velocity)],
        )
    assert planner.get_debug_data()["completed_give_way_targets"] == []

    planner.plan(8.0, np.array([5.0, 0.0]), _own_state(), [target])
    assert planner.get_debug_data()["give_way_rule_locks"] == {"1": rule.name}


def test_give_way_commitment_releases_after_pass_before_range_threshold() -> None:
    planner = VO(
        VOParams(
            speed_samples=8,
            heading_samples=32,
            velocity_uncertainty_vertices_mps=[[0.0, 0.0]],
            give_way_release_steps=3,
        )
    )
    target_velocity = (-5.0, 0.0)
    planner.plan(
        0.0,
        np.array([5.0, 0.0]),
        _own_state(),
        [_track(1, (600.0, 0.0), target_velocity)],
    )

    for sim_time, north in ((1.0, -80.0), (2.0, -90.0), (3.0, -100.0)):
        planner.plan(
            sim_time,
            np.array([5.0, 0.0]),
            _own_state(),
            [_track(1, (north, 0.0), target_velocity)],
        )
        assert planner.get_debug_data()["give_way_rule_locks"] == {"1": "HO"}

    planner.plan(
        4.0,
        np.array([5.0, 0.0]),
        _own_state(),
        [_track(1, (-110.0, 0.0), target_velocity)],
    )
    debug = planner.get_debug_data()
    assert debug["track_metrics"][1]["center_distance_m"] < 150.0
    assert debug["give_way_rule_locks"] == {}
    assert debug["completed_give_way_targets"] == [1]


def test_give_way_commitment_does_not_release_before_pass_on_projected_clearance() -> None:
    planner = VO(
        VOParams(
            speed_samples=8,
            heading_samples=32,
            velocity_uncertainty_vertices_mps=[[0.0, 0.0]],
            give_way_release_steps=3,
        )
    )
    target = _track(1, (600.0, 0.0), (-5.0, 0.0))
    planner.plan(0.0, np.array([5.0, 0.0]), _own_state(), [target])

    turned_state = _own_state(heading=np.deg2rad(40.0))
    safe_target = _track(1, (500.0, 0.0), (-5.0, 0.0))
    for sim_time in (1.0, 2.0):
        planner.plan(sim_time, np.array([5.0, 0.0]), turned_state, [safe_target])
        assert planner.get_debug_data()["give_way_rule_locks"] == {"1": "HO"}

    planner.plan(3.0, np.array([5.0, 0.0]), turned_state, [safe_target])
    debug = planner.get_debug_data()
    assert debug["track_metrics"][1]["rule_dcpa_m"] > 150.0
    assert debug["track_metrics"][1]["rule_tcpa_s"] > 0.0
    assert debug["give_way_rule_locks"] == {"1": "HO"}
    assert debug["completed_give_way_targets"] == []


def test_overtaking_uses_dedicated_240_second_entry_window_and_starboard_commitment() -> None:
    planner = VO(
        VOParams(
            speed_samples=32,
            heading_samples=128,
            velocity_uncertainty_vertices_mps=[[0.0, 0.0]],
        )
    )
    target = _track(1, (707.0, 0.0), (5.0, 0.0))

    planner.plan(0.0, np.array([8.0, 0.0]), _own_state(speed=8.0), [target])
    debug = planner.get_debug_data()

    assert debug["track_metrics"][1]["rule_tcpa_s"] == pytest.approx(707.0 / 3.0)
    assert debug["track_metrics"][1]["cpa_gate_eligible"] is False
    assert debug["overtaking_state"] == "COMMITTED"
    assert debug["overtaking_target_id"] == 1
    assert debug["overtaking_entry_tcpa_s"] == pytest.approx(707.0 / 3.0)
    assert debug["selected_heading_rad"] >= np.deg2rad(5.0)


def test_overtaking_lock_survives_range_growth_cpa_safety_and_role_flip() -> None:
    planner = VO(VOParams(velocity_uncertainty_vertices_mps=[[0.0, 0.0]]))
    planner.plan(
        0.0,
        np.array([8.0, 0.0]),
        _own_state(speed=8.0),
        [_track(1, (707.0, 0.0), (5.0, 0.0))],
    )

    planner.plan(
        1.0,
        np.array([8.0, 0.0]),
        _own_state(speed=2.0),
        [_track(1, (720.0, 0.0), (5.0, 0.0))],
    )
    growing = planner.get_debug_data()
    assert growing["overtaking_state"] == "COMMITTED"
    assert growing["track_metrics"][1]["overtaking_relative_speed_mps"] < 0.0

    planner.plan(
        2.0,
        np.array([8.0, 0.0]),
        _own_state(speed=2.0),
        [_track(1, (100.0, 100.0), (0.0, -5.0))],
    )
    flipped = planner.get_debug_data()
    assert flipped["track_metrics"][1]["matched_rules"] == ["CR_SS"]
    assert flipped["track_metrics"][1]["active_rules"] == ["OT_ing"]
    assert flipped["overtaking_state"] == "COMMITTED"


def test_overtaking_lock_releases_after_confirmed_safe_lateral_separation() -> None:
    planner = VO(VOParams(velocity_uncertainty_vertices_mps=[[0.0, 0.0]]))
    planner.plan(
        0.0,
        np.array([8.0, 0.0]),
        _own_state(speed=8.0),
        [_track(1, (707.0, 0.0), (5.0, 0.0))],
    )
    separated_target = _track(1, (400.0, 400.0), (5.0, 0.0))
    background_target = _track(2, (-1000.0, 1000.0), (0.0, 0.0))

    for sim_time in (1.0, 2.0):
        planner.plan(
            sim_time,
            np.array([8.0, 0.0]),
            _own_state(speed=2.0),
            [separated_target, background_target],
        )
        assert planner.get_debug_data()["overtaking_state"] == "COMMITTED"

    planner.plan(
        3.0,
        np.array([8.0, 0.0]),
        _own_state(speed=2.0),
        [separated_target, background_target],
    )
    debug = planner.get_debug_data()
    assert debug["overtaking_state"] == "CLEAR"
    assert debug["overtaking_release_reason"] == "separated_without_pass"
    assert not debug["give_way_commitment_active"]


def test_overtaking_requires_three_confirmed_passed_solves_then_rearms() -> None:
    planner = VO(VOParams(velocity_uncertainty_vertices_mps=[[0.0, 0.0]]))
    target = _track(1, (707.0, 0.0), (5.0, 0.0))
    planner.plan(0.0, np.array([8.0, 0.0]), _own_state(speed=8.0), [target])

    passed_target = _track(1, (100.0, 0.0), (5.0, 0.0))
    for sim_time in (1.0, 2.0):
        planner.plan(
            sim_time,
            np.array([8.0, 0.0]),
            _own_state(speed=8.0, position=(200.0, 0.0)),
            [passed_target],
        )
        assert planner.get_debug_data()["overtaking_state"] == "COMMITTED"

    planner.plan(
        3.0,
        np.array([8.0, 0.0]),
        _own_state(speed=8.0, position=(200.0, 0.0)),
        [passed_target],
    )
    assert planner.get_debug_data()["overtaking_state"] == "PASSED"
    assert not planner.get_debug_data()["give_way_commitment_active"]

    role_flipped = _track(1, (300.0, 100.0), (0.0, -5.0))
    planner.plan(
        4.0,
        np.array([8.0, 0.0]),
        _own_state(speed=8.0, position=(200.0, 0.0)),
        [role_flipped],
    )
    assert planner.get_debug_data()["track_metrics"][1]["matched_rules"] == ["CR_SS"]
    assert planner.get_debug_data()["track_metrics"][1]["active_rules"] == []

    far_target = _track(1, (-400.0, 0.0), (5.0, 0.0))
    for sim_time in (5.0, 6.0):
        planner.plan(sim_time, np.array([8.0, 0.0]), _own_state(speed=8.0), [far_target])
        assert planner.get_debug_data()["overtaking_state"] == "PASSED"
    planner.plan(7.0, np.array([8.0, 0.0]), _own_state(speed=8.0), [far_target])
    assert planner.get_debug_data()["overtaking_state"] == "CLEAR"


def test_single_pass_target_exit_clears_overtaking_and_driving_state() -> None:
    planner = VO(VOParams(velocity_uncertainty_vertices_mps=[[0.0, 0.0]]))
    planner.plan(
        0.0,
        np.array([8.0, 0.0]),
        _own_state(speed=8.0),
        [_track(1, (707.0, 0.0), (5.0, 0.0))],
    )
    assert planner.get_debug_data()["overtaking_state"] == "COMMITTED"

    planner.plan(1.0, np.array([8.0, 0.0]), _own_state(speed=8.0), [])

    debug = planner.get_debug_data()
    assert debug["expired_target_ids"] == [1]
    assert debug["overtaking_state"] == "CLEAR"
    assert debug["overtaking_target_id"] is None
    assert debug["driving_target_id"] is None
    assert not debug["give_way_commitment_active"]


def test_overtaking_prefers_safe_speed_advantage_and_labels_relaxed_progress() -> None:
    planner = VO(VOParams(velocity_uncertainty_vertices_mps=[[0.0, 0.0]]))
    planner.plan(
        0.0,
        np.array([8.0, 0.0]),
        _own_state(speed=8.0),
        [_track(1, (707.0, 0.0), (5.0, 0.0))],
    )
    debug = planner.get_debug_data()
    target_along_speed = debug["selected_speed_mps"] * np.cos(debug["selected_heading_rad"])
    assert target_along_speed >= 5.5 - 1e-12
    assert not debug["overtaking_progress_relaxed"]

    slow_only = VO(
        VOParams(
            speed_set_limits=[0.0, 5.0],
            speed_samples=8,
            heading_samples=32,
            velocity_uncertainty_vertices_mps=[[0.0, 0.0]],
        )
    )
    slow_only.plan(
        0.0,
        np.array([5.0, 0.0]),
        _own_state(speed=5.0),
        [_track(1, (40.0, 0.0), (4.8, 0.0))],
    )
    slow_debug = slow_only.get_debug_data()
    assert slow_debug["overtaking_state"] == "COMMITTED"
    assert slow_debug["overtaking_progress_relaxed"]
    assert slow_debug["selected_speed_mps"] <= 5.0


def test_decision_space_snapshot_is_dense_finite_json_contract() -> None:
    planner = VO(VOParams(speed_samples=4, heading_samples=8))
    target = _track(1, (100.0, 0.0), (-5.0, 0.0))

    plan = planner.plan(0.0, np.array([5.0, 0.0]), _own_state(), [target])
    snapshot = planner.get_decision_space_snapshot()

    assert snapshot is not None
    assert snapshot["schema"] == "vo_velocity_space.v1"
    assert snapshot["shape"] == [4, 8]
    assert len(snapshot["candidate_state_bits"]) == 32
    assert len(snapshot["total_costs"]) == 32
    assert len(snapshot["minimum_ttc_s"]) == 32
    assert all(value is None or np.isfinite(value) for value in snapshot["total_costs"])
    assert all(value is None or np.isfinite(value) for value in snapshot["minimum_ttc_s"])
    selected = snapshot["selected"]
    assert selected["heading_rad"] == pytest.approx(plan[2, 0])
    assert selected["speed_mps"] == pytest.approx(plan[3, 0])

    held_plan = planner.plan(0.5, np.array([5.0, 0.0]), _own_state(), [target])
    held_snapshot = planner.get_decision_space_snapshot()
    assert not planner.plan_executed
    np.testing.assert_allclose(held_plan, plan)
    assert held_snapshot is not None
    assert held_snapshot["selected"] == snapshot["selected"]
    assert held_snapshot["candidate_state_bits"] == snapshot["candidate_state_bits"]


def test_all_tracks_build_base_vo_even_when_cpa_gate_rejects_colregs() -> None:
    planner = VO(VOParams(speed_samples=3, heading_samples=8))
    ownship = _own_state(speed=-5.0)
    target = _track(1, (100.0, 0.0), (0.0, 0.0))

    planner.plan(0.0, np.array([5.0, 0.0]), ownship, [target])

    speed_index = int(np.argmin(abs(planner._speed_set - 5.0)))
    heading_index = int(np.argmin(abs(planner._heading_set)))
    assert planner._hard_constraint_mask[speed_index, heading_index]
    assert planner.get_debug_data()["active_rules"] == {}


def test_wvo_only_candidate_remains_feasible_with_reduced_ttc_weight() -> None:
    planner = VO(VOParams(speed_samples=2, heading_samples=4))
    planner._speed_set = np.array([1.0])
    planner._heading_set = np.array([0.0])
    planner._ensure_grid_shape()
    obstacle = box(9.0, -1.0, 11.0, 1.0)

    planner._apply_dynamic_hazard(
        obstacle,
        p_os=np.zeros(2),
        p_do=np.array([10.0, 0.0]),
        v_do=np.array([2.0, 0.0]),
        candidates=planner._candidate_velocities(),
        uncertainty=np.array([[-2.0, 0.0], [0.0, 0.0]]),
        rules=set(),
    )

    assert not planner._hard_constraint_mask[0, 0]
    assert planner._wvo_mask[0, 0]
    assert np.isfinite(planner._min_ttc[0, 0])


@pytest.mark.parametrize(
    ("position", "velocity", "expected"),
    (
        ((100.0, 0.0), (-5.0, 0.0), VOCOLREGSSituation.HO),
        ((100.0, 0.0), (2.0, 0.0), VOCOLREGSSituation.OT_ing),
        ((-100.0, 0.0), (5.0, 0.0), VOCOLREGSSituation.OT_en),
        ((0.0, 100.0), (0.0, -5.0), VOCOLREGSSituation.CR_SS),
        ((0.0, -100.0), (0.0, 5.0), VOCOLREGSSituation.CR_PS),
    ),
)
def test_rule_selector_preserves_encounter_roles(
    position: tuple[float, float],
    velocity: tuple[float, float],
    expected: VOCOLREGSSituation,
) -> None:
    planner = VO()

    rules = planner._determine_colregs_rules(
        np.zeros(2),
        0.0,
        np.array([5.0, 0.0]),
        np.asarray(position),
        np.asarray(velocity),
    )

    assert expected in rules


def test_rule_selector_can_activate_multiple_rules_at_boundary() -> None:
    params = VOParams(rule_cross_track_min_m=0.0)
    planner = VO(params)
    target_heading = np.deg2rad(165.0)

    rules = planner._determine_colregs_rules(
        np.zeros(2),
        0.0,
        np.array([5.0, 0.0]),
        np.array([100.0, 0.0]),
        5.0 * np.array([np.cos(target_heading), np.sin(target_heading)]),
    )

    assert {VOCOLREGSSituation.HO, VOCOLREGSSituation.CR_SS} <= rules


def test_hysteresis_releases_only_after_n_consecutive_misses() -> None:
    planner = VO(VOParams(colregs_hysteresis_steps=3))
    rule = VOCOLREGSSituation.HO

    assert rule in planner._update_colregs_rules(7, {rule}, eligible=True)
    assert rule in planner._update_colregs_rules(7, set(), eligible=True)
    assert rule in planner._update_colregs_rules(7, set(), eligible=True)
    assert rule not in planner._update_colregs_rules(7, set(), eligible=True)


def test_past_and_clear_releases_rule_after_hysteresis_window() -> None:
    planner = VO(VOParams(colregs_hysteresis_steps=2))
    rule = VOCOLREGSSituation.HO
    planner._update_colregs_rules(7, {rule}, eligible=True)

    assert rule in planner._update_colregs_rules(7, set(), eligible=False)
    assert rule not in planner._update_colregs_rules(7, set(), eligible=False)


def test_low_speed_target_has_vo_but_no_colregs_direction_constraint() -> None:
    planner = VO(VOParams(speed_samples=4, heading_samples=16))
    target = _track(1, (30.0, 0.0), (0.1, 0.0))

    planner.plan(0.0, np.array([5.0, 0.0]), _own_state(), [target])

    debug = planner.get_debug_data()
    assert debug["hard_constraint_count"] > 0
    assert debug["active_rules"] == {}


def test_target_order_does_not_change_grid_or_selected_command() -> None:
    tracks = [
        _track(9, (80.0, 10.0), (-3.0, 0.0)),
        _track(2, (40.0, -20.0), (0.0, 2.0)),
    ]
    first = VO(VOParams(speed_samples=8, heading_samples=32))
    second = VO(VOParams(speed_samples=8, heading_samples=32))

    plan_first = first.plan(0.0, np.array([5.0, 0.0]), _own_state(), tracks)
    plan_second = second.plan(0.0, np.array([5.0, 0.0]), _own_state(), list(reversed(tracks)))

    np.testing.assert_allclose(plan_first, plan_second)
    np.testing.assert_array_equal(first._hard_constraint_mask, second._hard_constraint_mask)
    np.testing.assert_allclose(first._min_ttc, second._min_ttc)


def test_core_reports_infeasible_and_uses_labeled_stop_fallback() -> None:
    planner = VO(VOParams(speed_samples=4, heading_samples=8))
    overlapping = _track(1, (0.0, 0.0), (0.0, 0.0), length=100.0, width=100.0)

    plan = planner.plan(0.0, np.array([5.0, 0.0]), _own_state(), [overlapping])

    assert not planner.feasible
    assert plan[2, 0] == pytest.approx(0.0)
    assert plan[3, 0] == pytest.approx(0.0)
    assert planner.get_debug_data()["fallback"] == "stop_nonpaper_wrapper"


def test_enc_adapter_includes_only_configured_physical_layers() -> None:
    enc = SimpleNamespace(
        land=SimpleNamespace(geometry=box(95.0, -5.0, 105.0, 5.0)),
        shore=SimpleNamespace(geometry=Polygon()),
        obstrn=SimpleNamespace(geometry=Polygon()),
        uwtroc=SimpleNamespace(geometry=Polygon()),
        seabed={0: SimpleNamespace(geometry=box(-1000.0, -1000.0, 1000.0, 1000.0))},
        unsare=SimpleNamespace(geometry=box(-5.0, 45.0, 5.0, 55.0)),
        soundg=SimpleNamespace(geometry=box(-5.0, 65.0, 5.0, 75.0)),
    )
    planner = VO(VOParams(speed_samples=4, heading_samples=16, static_query_range_m=200.0))

    planner.plan(0.0, np.array([0.0, 5.0]), _own_state(), [], enc)

    debug = planner.get_debug_data()
    assert debug["static_hazard_count"] == 1
    east_heading = int(np.argmin(abs(planner._heading_set - np.pi / 2.0)))
    assert planner._hard_constraint_mask[-1, east_heading]


@pytest.mark.parametrize(
    ("layer_name", "attribute"),
    (
        ("LAND", "land"),
        ("SHORE", "shore"),
        ("OBSTRN", "obstrn"),
        ("UWTROC", "uwtroc"),
    ),
)
def test_each_physical_enc_layer_builds_static_vo(layer_name: str, attribute: str) -> None:
    empty = SimpleNamespace(geometry=Polygon())
    enc = SimpleNamespace(land=empty, shore=empty, obstrn=empty, uwtroc=empty)
    setattr(enc, attribute, SimpleNamespace(geometry=box(95.0, -5.0, 105.0, 5.0)))
    planner = VO(
        VOParams(
            speed_samples=4,
            heading_samples=16,
            static_hazard_layers=(layer_name,),
            static_query_range_m=200.0,
        )
    )

    planner.plan(0.0, np.array([0.0, 5.0]), _own_state(), [], enc)

    assert planner.get_debug_data()["static_hazard_count"] == 1


@pytest.mark.parametrize("excluded_attribute", ("unsare", "soundg", "seabed", "m_qual"))
def test_nonphysical_enc_layers_do_not_build_static_vo(excluded_attribute: str) -> None:
    empty = SimpleNamespace(geometry=Polygon())
    enc = SimpleNamespace(land=empty, shore=empty, obstrn=empty, uwtroc=empty)
    setattr(enc, excluded_attribute, SimpleNamespace(geometry=box(95.0, -5.0, 105.0, 5.0)))
    planner = VO(VOParams(static_query_range_m=200.0))

    planner.plan(0.0, np.array([0.0, 5.0]), _own_state(), [], enc)

    assert planner.get_debug_data()["static_hazard_count"] == 0


def test_removed_penalty_and_spatial_buffer_config_fails_loudly() -> None:
    with pytest.raises(ValueError, match="Removed VO configuration"):
        VOParams.from_dict({"safety_buffer": 15.0, "vo_violation_cost": 1000.0})


def test_registry_applies_vo_algorithm_config() -> None:
    wrapper = IntegrationRegistry().build_algorithm(
        "vo",
        {"speed_samples": 7, "heading_samples": 24, "w_ttc": 3.5},
    )

    assert isinstance(wrapper, VOWrapper)
    assert wrapper._vo._params.speed_samples == 7
    assert wrapper._vo._params.heading_samples == 24
    assert wrapper._vo._params.w_ttc == pytest.approx(3.5)


def test_wrapper_reports_infeasible_status_and_fallback_reason() -> None:
    wrapper = VOWrapper(
        Config(
            layer1=LayerConfig(vo=VOParams(speed_samples=4, heading_samples=8)),
            layer2=LayerConfig(los=LOSGuidanceParams()),
        )
    )
    overlapping = _track(1, (0.0, 0.0), (0.0, 0.0), length=100.0, width=100.0)

    wrapper.plan(
        0.0,
        np.array([[0.0, 100.0], [0.0, 0.0]]),
        np.array([5.0, 5.0]),
        _own_state(),
        [overlapping],
    )

    diagnostics = wrapper.get_diagnostics()
    assert diagnostics.status is PlanStatus.INFEASIBLE
    assert diagnostics.feasible is False
    assert diagnostics.fallback_used
    assert diagnostics.details["fallback"] == "stop_nonpaper_wrapper"


def test_wrapper_forwards_actual_fcb_dimensions_to_vo() -> None:
    wrapper = VOWrapper(
        Config(
            layer1=LayerConfig(vo=VOParams(speed_samples=4, heading_samples=8)),
            layer2=LayerConfig(los=LOSGuidanceParams()),
        )
    )

    wrapper.plan(
        0.0,
        np.array([[0.0, 100.0], [0.0, 0.0]]),
        np.array([5.0, 5.0]),
        _own_state(),
        [],
        os_length=45.0,
        os_width=12.0,
    )

    debug = wrapper._vo.get_debug_data()
    assert debug["ownship_length_m"] == pytest.approx(45.0)
    assert debug["ownship_width_m"] == pytest.approx(12.0)


def test_twenty_target_default_grid_plans_under_one_second() -> None:
    tracks = [
        _track(
            index,
            (
                250.0 * np.cos(2.0 * np.pi * index / 20.0),
                250.0 * np.sin(2.0 * np.pi * index / 20.0),
            ),
            (
                -2.0 * np.cos(2.0 * np.pi * index / 20.0),
                -2.0 * np.sin(2.0 * np.pi * index / 20.0),
            ),
        )
        for index in range(20)
    ]
    planner = VO()

    started = time.perf_counter()
    planner.plan(0.0, np.array([5.0, 0.0]), _own_state(), tracks)
    elapsed = time.perf_counter() - started

    assert elapsed < 1.0


def test_twenty_target_planning_reports_p50_p95_and_max_under_one_second() -> None:
    tracks = [
        _track(
            index,
            (300.0 * np.cos(index), 300.0 * np.sin(index)),
            (-2.0 * np.cos(index), -2.0 * np.sin(index)),
        )
        for index in range(20)
    ]
    timings = []
    for iteration in range(7):
        planner = VO()
        started = time.perf_counter()
        planner.plan(float(iteration), np.array([5.0, 0.0]), _own_state(), tracks)
        timings.append(time.perf_counter() - started)

    assert float(np.percentile(timings, 50)) < 1.0
    assert float(np.percentile(timings, 95)) < 1.0
    assert max(timings) < 1.0
