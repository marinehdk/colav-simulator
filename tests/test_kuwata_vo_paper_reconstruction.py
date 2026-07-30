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


def _own_state(*, speed: float = 5.0, heading: float = 0.0) -> np.ndarray:
    return np.array([0.0, 0.0, heading, speed, 0.0, 0.0])


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
