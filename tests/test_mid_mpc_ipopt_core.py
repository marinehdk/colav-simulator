from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from colav_simulator.core.colav.mid_mpc import (
    MidMpcConfig,
    MidMpcHardWindow,
    MidMpcIpoptSolver,
    MidMpcOwnShip,
    MidMpcPrimalWarmStart,
    MidMpcProblem,
    MidMpcRouteFrame,
    MidMpcRouteObjective,
    MidMpcRowSchedule,
    MidMpcStatus,
    MidMpcTarget,
)
from colav_simulator.core.colav.mid_mpc import solver as solver_module
from colav_simulator.core.colav.mid_mpc.solver import (
    _IterationCallback,
    _optimization_quality_passed,
    _target_free_required_improvement,
)
from colav_simulator.mid_mpc_parity import (
    MidMpcParityFixture,
    load_mid_mpc_parity_corpus,
)

CORPUS_PATH = Path(__file__).parent / "fixtures" / "mid_mpc_ipopt" / "v1.jsonl"


@pytest.fixture(scope="module")
def parity_corpus() -> dict[str, MidMpcParityFixture]:
    return {fixture.fixture_id: fixture for fixture in load_mid_mpc_parity_corpus(CORPUS_PATH)}


def _number(value: object) -> float:
    if value == "Infinity":
        return np.inf
    if value == "-Infinity":
        return -np.inf
    return float(value)


def _config(fixture: MidMpcParityFixture) -> MidMpcConfig:
    config = fixture.input["config"]
    return MidMpcConfig(
        horizon_steps=config["N"],
        dt_s=config["dt"],
        w_colreg=config["w_colreg"],
        w_dist=config["w_dist"],
        w_vel=config["w_vel"],
        w_route=config["w_route"],
        w_slack_l1=config["w_slack_l1"],
        w_slack_l2=config["w_slack_l2"],
        w_dir_slack_l1=config["w_dir_slack_l1"],
        w_dir_slack_l2=config["w_dir_slack_l2"],
        zeta=config["zeta"],
        pwt_outer_m=config["pwt_outer_m"],
        t_discount_s=config["t_discount_s"],
        cpa_slack_enabled=config["cpa_slack_enabled"],
        dir_slack_enabled=config["dir_slack_enabled"],
        continuous_cpa_enabled=config["continuous_cpa_enabled"],
    )


def _problem(fixture: MidMpcParityFixture) -> MidMpcProblem:
    problem = fixture.input["problem"]
    own_ship = problem["own_ship"]
    route_frame = problem["route_frame"]
    normalized = problem["normalized"]
    schedule = normalized["row_schedule"]
    return MidMpcProblem(
        own_ship=MidMpcOwnShip(
            psi_rad=own_ship["psi_rad"],
            u_mps=own_ship["u_mps"],
        ),
        route_bearing_rad=problem["route_bearing_rad"],
        planned_speed_mps=problem["planned_speed_mps"],
        heading_bounds_rad=tuple(problem["heading_bounds_rad"]),
        speed_bounds_mps=tuple(problem["speed_bounds_mps"]),
        cpa_safe_m=problem["cpa_safe_m"],
        cpa_hard_m=problem["cpa_hard_m"],
        rot_max_rad_s=problem["rot_max_rad_s"],
        decel_max_mps2=problem["decel_max_mps2"],
        lateral_active=normalized["lateral_active"],
        preferred_side=normalized["preferred_side"],
        starboard_asymmetry_active=normalized["starboard_asymmetry_active"],
        min_alteration_rad=problem["min_alteration_rad"],
        prefix_active_k=problem["prefix_active_k"],
        prefix_psi_rad=tuple(problem["prefix_psi_rad"]),
        prefix_u_mps=tuple(problem["prefix_u_mps"]),
        route_frame=MidMpcRouteFrame(
            origin_m=tuple(route_frame["origin_m"]),
            normal=tuple(route_frame["normal"]),
            bearing_rad=route_frame["bearing_rad"],
            lateral_scale_m=route_frame["lateral_scale_m"],
            weight=route_frame["weight"],
        ),
        row_schedule=MidMpcRowSchedule(
            prefix_softening=schedule["prefix_softening"],
            cpa_hard_from_k=schedule["cpa_hard_from_k"],
            direction_hard_from_k=schedule["direction_hard_from_k"],
            min_alt_hard_from_k=schedule["min_alt_hard_from_k"],
            terminal_rows_enabled=schedule["terminal_rows_enabled"],
        ),
        audit_row_count=normalized["audit_row_count"],
        targets=tuple(
            MidMpcTarget(
                x_m=target["x_m"],
                y_m=target["y_m"],
                cog_rad=target["cog_rad"],
                sog_mps=target["sog_mps"],
            )
            for target in problem["targets"]
        ),
    )


def _assert_parity(fixture: MidMpcParityFixture) -> None:
    result = MidMpcIpoptSolver(_config(fixture)).solve(_problem(fixture))
    expected = fixture.output
    objective_tolerance = fixture.tolerances["objective_abs"]
    trajectory_tolerance = fixture.tolerances["trajectory_abs"]
    diagnostic_tolerance = fixture.tolerances["diagnostic_abs"]

    assert result.status.value == expected["status"]
    assert result.ipopt_return_status == expected["ipopt_return_status"]
    assert result.ipopt_iterations == expected["ipopt_iterations"]
    assert result.objective_total == pytest.approx(expected["objective_total"], abs=objective_tolerance)
    for name, value in vars(result.objective_components).items():
        assert value == pytest.approx(expected["objective_components"].get(name, 0.0), abs=objective_tolerance)
    assert result.elapsed_ms >= 0.0
    assert result.cpa_slack == pytest.approx(expected["cpa_slack"], abs=diagnostic_tolerance)
    assert result.raw_f == pytest.approx(expected["raw"]["f"], abs=objective_tolerance)
    assert result.raw_cpa_slack == pytest.approx(expected["raw"]["cpa_slack"], abs=diagnostic_tolerance)
    assert result.raw_dir_slack == pytest.approx(expected["raw"]["dir_slack"], abs=diagnostic_tolerance)
    assert result.continuous_cpa_min_m == pytest.approx(_number(expected["continuous_cpa_min_m"]), abs=diagnostic_tolerance)
    assert result.continuous_cpa_violated is expected["continuous_cpa_violated"]

    prepared = expected["prepared"]
    np.testing.assert_allclose(result.prepared.p, prepared["p"], atol=0.0, rtol=0.0)
    np.testing.assert_allclose(result.prepared.x0, prepared["x0"], atol=0.0, rtol=0.0)
    np.testing.assert_allclose(
        result.prepared.lbx,
        [_number(value) for value in prepared["lbx"]],
        atol=0.0,
        rtol=0.0,
    )
    np.testing.assert_allclose(
        result.prepared.ubx,
        [_number(value) for value in prepared["ubx"]],
        atol=0.0,
        rtol=0.0,
    )
    np.testing.assert_allclose(
        result.prepared.lbg,
        [_number(value) for value in prepared["lbg"]],
        atol=0.0,
        rtol=0.0,
    )
    np.testing.assert_allclose(
        result.prepared.ubg,
        [_number(value) for value in prepared["ubg"]],
        atol=0.0,
        rtol=0.0,
    )
    expected_active_rows = tuple(
        index
        for index, (lower, upper) in enumerate(zip(prepared["lbg"], prepared["ubg"], strict=True))
        if lower != "-Infinity" or upper != "Infinity"
    )
    assert result.active_row_indices == expected_active_rows
    assert result.max_constraint_violation <= 1.0e-3
    np.testing.assert_allclose(result.raw_x, expected["raw"]["x"], atol=diagnostic_tolerance, rtol=0.0)
    np.testing.assert_allclose(
        result.raw_g,
        expected["raw"]["g"],
        atol=diagnostic_tolerance,
        rtol=diagnostic_tolerance,
    )
    np.testing.assert_allclose(
        [(point.x_m, point.y_m, point.psi_rad, point.u_mps, point.t_s) for point in result.trajectory],
        [
            (
                point["x_m"],
                point["y_m"],
                point["psi_rad"],
                point["u_mps"],
                point["t_s"],
            )
            for point in expected["trajectory"]
        ],
        atol=trajectory_tolerance,
        rtol=0.0,
    )
    assert result.row_layout.to_dict() == expected["row_layout"]


def test_route_speed_cold_matches_frozen_cpp_oracle(
    parity_corpus: dict[str, MidMpcParityFixture],
) -> None:
    _assert_parity(parity_corpus["route_speed_cold"])


def test_repeated_same_structure_solves_reuse_graph_without_stale_target_data(
    parity_corpus: dict[str, MidMpcParityFixture],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = parity_corpus["head_on_starboard"]
    config = _config(fixture)
    first_problem = _problem(fixture)
    moved_target = replace(first_problem.targets[0], x_m=first_problem.targets[0].x_m + 25.0)
    second_problem = replace(first_problem, targets=(moved_target,))
    build_calls = 0
    original_build_graph = solver_module._build_graph

    def counted_build_graph(
        config: MidMpcConfig,
        problem: MidMpcProblem,
    ) -> solver_module._Graph:
        nonlocal build_calls
        build_calls += 1
        return original_build_graph(config, problem)

    monkeypatch.setattr(solver_module, "_build_graph", counted_build_graph)
    reused_solver = MidMpcIpoptSolver(config)
    reused_solver.solve(first_problem)
    reused_result = reused_solver.solve(second_problem)
    fresh_result = MidMpcIpoptSolver(config).solve(second_problem)

    assert build_calls == 2
    np.testing.assert_allclose(reused_result.raw_x, fresh_result.raw_x, atol=1.0e-8, rtol=0.0)
    np.testing.assert_allclose(reused_result.raw_g, fresh_result.raw_g, atol=1.0e-6, rtol=1.0e-12)


def test_colav_strict_staged_route_objective_alters_then_returns_to_mission(
    parity_corpus: dict[str, MidMpcParityFixture],
) -> None:
    fixture = parity_corpus["route_speed_cold"]
    config = replace(_config(fixture), strict_slack_bounds=True)
    source = _problem(fixture)
    mission = source.route_bearing_rad
    corridor = mission + 0.2
    avoidance_until_k = max(2, config.horizon_steps // 2)
    references = (corridor,) * avoidance_until_k + (mission,) * (config.horizon_steps - avoidance_until_k)
    problem = replace(
        source,
        route_bearing_rad=corridor,
        route_objective=MidMpcRouteObjective(
            mission_bearing_rad=mission,
            avoidance_corridor_bearing_rad=corridor,
            heading_reference_rad=references,
            lateral_reference_m=(0.0,) * config.horizon_steps,
            avoidance_active_until_k=avoidance_until_k,
        ),
    )

    result = MidMpcIpoptSolver(config).solve(problem)

    headings = result.raw_x[: config.horizon_steps]
    assert result.prepared.p.size == (
        len(fixture.output["prepared"]["p"]) + 5 * config.horizon_steps + 2 + 2 * config.max_targets
    )
    assert np.mean(headings[:avoidance_until_k]) > np.mean(headings[avoidance_until_k:]) + 0.05
    assert headings[-1] == pytest.approx(mission, abs=0.02)


def test_staged_route_recovery_masks_legacy_give_way_objective(
    parity_corpus: dict[str, MidMpcParityFixture],
) -> None:
    fixture = parity_corpus["route_speed_cold"]
    config = replace(_config(fixture), strict_slack_bounds=True)
    source = _problem(fixture)
    mission = source.route_bearing_rad
    corridor = mission + 0.2
    avoidance_until_k = max(2, config.horizon_steps // 2)
    references = (corridor,) * avoidance_until_k + (mission,) * (config.horizon_steps - avoidance_until_k)
    problem = replace(
        source,
        route_bearing_rad=corridor,
        lateral_active=True,
        preferred_side=1,
        starboard_asymmetry_active=True,
        min_alteration_rad=0.1,
        route_objective=MidMpcRouteObjective(
            mission_bearing_rad=mission,
            avoidance_corridor_bearing_rad=corridor,
            heading_reference_rad=references,
            lateral_reference_m=(0.0,) * config.horizon_steps,
            avoidance_active_until_k=avoidance_until_k,
        ),
        row_schedule=MidMpcRowSchedule(
            direction_hard_window=MidMpcHardWindow(0, avoidance_until_k),
            min_alt_hard_window=MidMpcHardWindow(0, avoidance_until_k),
        ),
    )

    result = MidMpcIpoptSolver(config).solve(problem)

    headings = result.raw_x[: config.horizon_steps]
    assert np.mean(headings[:avoidance_until_k]) > mission + 0.08
    assert headings[-1] == pytest.approx(mission, abs=0.03)


def test_staged_route_profiles_reuse_one_fixed_graph(
    parity_corpus: dict[str, MidMpcParityFixture],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = parity_corpus["route_speed_cold"]
    config = replace(_config(fixture), strict_slack_bounds=True)
    source = _problem(fixture)
    build_calls = 0
    original_build_graph = solver_module._build_graph

    def counted_build_graph(config: MidMpcConfig, problem: MidMpcProblem) -> solver_module._Graph:
        nonlocal build_calls
        build_calls += 1
        return original_build_graph(config, problem)

    monkeypatch.setattr(solver_module, "_build_graph", counted_build_graph)
    solver = MidMpcIpoptSolver(config)
    for avoidance_until_k in (2, 4):
        corridor = source.route_bearing_rad + 0.2
        solver.solve(
            replace(
                source,
                route_bearing_rad=corridor,
                route_objective=MidMpcRouteObjective(
                    mission_bearing_rad=source.route_bearing_rad,
                    avoidance_corridor_bearing_rad=corridor,
                    heading_reference_rad=(corridor,) * avoidance_until_k
                    + (source.route_bearing_rad,) * (config.horizon_steps - avoidance_until_k),
                    lateral_reference_m=(25.0 * avoidance_until_k,) * config.horizon_steps,
                    avoidance_active_until_k=avoidance_until_k,
                ),
            )
        )

    assert build_calls == 1


def test_colav_strict_continuity_reference_changes_parameters_without_rebuilding_graph(
    parity_corpus: dict[str, MidMpcParityFixture],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = parity_corpus["route_speed_cold"]
    config = replace(_config(fixture), strict_slack_bounds=True)
    source = _problem(fixture)
    n = config.horizon_steps
    route = MidMpcRouteObjective(
        mission_bearing_rad=source.route_bearing_rad,
        avoidance_corridor_bearing_rad=source.route_bearing_rad,
        heading_reference_rad=(source.route_bearing_rad,) * n,
        lateral_reference_m=(0.0,) * n,
        avoidance_active_until_k=0,
    )
    active = replace(
        route,
        continuity_heading_reference_rad=(source.route_bearing_rad + 0.1,) * n,
        continuity_speed_reference_mps=(source.planned_speed_mps,) * n,
        continuity_weight=(40.0,) * n,
    )
    build_calls = 0
    original_build_graph = solver_module._build_graph

    def counted_build_graph(config: MidMpcConfig, problem: MidMpcProblem) -> solver_module._Graph:
        nonlocal build_calls
        build_calls += 1
        return original_build_graph(config, problem)

    monkeypatch.setattr(solver_module, "_build_graph", counted_build_graph)
    solver = MidMpcIpoptSolver(config)
    inactive_result = solver.solve(replace(source, route_objective=route))
    active_result = solver.solve(replace(source, route_objective=active))

    assert build_calls == 1
    assert inactive_result.objective_components.continuity == pytest.approx(0.0)
    assert active_result.objective_components.continuity > 0.0
    assert np.mean(active_result.raw_x[:n]) > np.mean(inactive_result.raw_x[:n])


def test_colav_strict_hard_windows_update_bounds_without_rebuilding_graph(
    parity_corpus: dict[str, MidMpcParityFixture],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = parity_corpus["multi_target_row_order"]
    config = replace(_config(fixture), strict_slack_bounds=True)
    source = replace(_problem(fixture), lateral_active=False)
    n = config.horizon_steps
    first_schedule = MidMpcRowSchedule(
        cpa_hard_windows=(MidMpcHardWindow(1, n - 1), MidMpcHardWindow(2, n)),
        direction_hard_window=MidMpcHardWindow(1, n - 1),
        min_alt_hard_window=MidMpcHardWindow(2, n - 1),
    )
    second_schedule = replace(
        first_schedule,
        cpa_hard_windows=(MidMpcHardWindow(0, n), MidMpcHardWindow(1, n - 1)),
    )
    build_calls = 0
    original_build_graph = solver_module._build_graph

    def counted_build_graph(config: MidMpcConfig, problem: MidMpcProblem) -> solver_module._Graph:
        nonlocal build_calls
        build_calls += 1
        return original_build_graph(config, problem)

    monkeypatch.setattr(solver_module, "_build_graph", counted_build_graph)
    solver = MidMpcIpoptSolver(config)
    first = solver.solve(replace(source, row_schedule=first_schedule))
    solver.solve(replace(source, row_schedule=second_schedule))

    assert build_calls == 1
    target_count = len(source.targets)
    for k in range(n):
        for target_index, window in enumerate(first_schedule.cpa_hard_windows):
            row = first.row_layout.cpa.start + k * target_count + target_index
            assert bool(np.isfinite(first.prepared.lbg[row])) is (window.start_k <= k < window.stop_k)
    for span, window in (
        (first.row_layout.direction, first_schedule.direction_hard_window),
        (first.row_layout.min_alt, first_schedule.min_alt_hard_window),
    ):
        assert window is not None
        active = np.isfinite(first.prepared.lbg[span.start : span.start + span.count])
        assert active.tolist() == [window.start_k <= k < window.stop_k for k in range(n)]


def test_colav_strict_release_reuses_single_encounter_graph(
    parity_corpus: dict[str, MidMpcParityFixture],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = parity_corpus["head_on_starboard"]
    config = replace(_config(fixture), strict_slack_bounds=True)
    source = _problem(fixture)
    n = config.horizon_steps
    route = MidMpcRouteObjective(
        mission_bearing_rad=source.route_bearing_rad,
        avoidance_corridor_bearing_rad=source.route_bearing_rad + 0.2,
        heading_reference_rad=(source.route_bearing_rad + 0.2,) * (n // 2) + (source.route_bearing_rad,) * (n - n // 2),
        lateral_reference_m=(0.0,) * n,
        avoidance_active_until_k=n // 2,
    )
    active = replace(source, route_objective=route)
    released = replace(
        active,
        cpa_hard_m=50.0,
        audit_row_count=0,
        prefix_active_k=1,
        prefix_psi_rad=(source.own_ship.psi_rad,),
        prefix_u_mps=(source.own_ship.u_mps,),
        targets=(),
        row_schedule=MidMpcRowSchedule(),
    )
    build_calls = 0
    original_build_graph = solver_module._build_graph

    def counted_build_graph(config: MidMpcConfig, problem: MidMpcProblem) -> solver_module._Graph:
        nonlocal build_calls
        build_calls += 1
        return original_build_graph(config, problem)

    monkeypatch.setattr(solver_module, "_build_graph", counted_build_graph)
    solver = MidMpcIpoptSolver(config)
    active_result = solver.solve(active)
    released_result = solver.solve(released)

    assert build_calls == 1
    assert active_result.graph_cache_hit is False
    assert active_result.graph_build_elapsed_ms > 0.0
    assert released_result.graph_cache_hit is True
    assert released_result.graph_build_elapsed_ms == 0.0
    assert released_result.preparation_elapsed_ms >= 0.0
    assert released_result.ipopt_elapsed_ms > 0.0
    assert released_result.elapsed_ms >= released_result.ipopt_elapsed_ms


def test_colav_strict_route_only_solve_uses_feasible_quality_stop(
    parity_corpus: dict[str, MidMpcParityFixture],
) -> None:
    fixture = parity_corpus["route_speed_cold"]
    config = replace(_config(fixture), strict_slack_bounds=True)
    source = _problem(fixture)
    n = config.horizon_steps
    problem = replace(
        source,
        route_objective=MidMpcRouteObjective(
            mission_bearing_rad=source.route_bearing_rad,
            avoidance_corridor_bearing_rad=source.route_bearing_rad,
            heading_reference_rad=(source.route_bearing_rad,) * n,
            lateral_reference_m=(0.0,) * n,
            avoidance_active_until_k=0,
        ),
    )

    result = MidMpcIpoptSolver(config).solve(problem)

    assert result.status is MidMpcStatus.FEASIBLE_NONOPTIMAL
    assert result.accepted_by_quality_gate is True
    assert result.optimization_quality_passed is True
    assert result.objective_improvement >= abs(result.seed_objective_total) * 0.01


def test_colav_strict_profile_keeps_frozen_slack_variables_but_fixes_them_to_zero(
    parity_corpus: dict[str, MidMpcParityFixture],
) -> None:
    fixture = parity_corpus["route_speed_cold"]
    config = replace(_config(fixture), strict_slack_bounds=True)

    result = MidMpcIpoptSolver(config).solve(_problem(fixture))

    assert result.prepared.lbx[-2:].tolist() == [0.0, 0.0]
    assert result.prepared.ubx[-2:].tolist() == [0.0, 0.0]
    assert result.raw_x.shape == (2 * config.horizon_steps + 2,)
    assert result.max_decision_bound_violation <= 1.0e-7
    assert result.raw_cpa_slack == pytest.approx(0.0, abs=1.0e-7)
    assert result.raw_dir_slack == pytest.approx(0.0, abs=1.0e-7)
    assert result.optimization_quality_passed is True
    assert result.ipopt_iterations >= 2
    assert result.objective_total < result.seed_objective_total
    assert result.objective_improvement == pytest.approx(
        result.seed_objective_total - result.objective_total,
    )


def test_colav_strict_profile_does_not_accept_a_primal_infeasible_restoration_point(
    parity_corpus: dict[str, MidMpcParityFixture],
) -> None:
    fixture = parity_corpus["close_target_cpa_slack"]
    config = replace(_config(fixture), strict_slack_bounds=True)

    result = MidMpcIpoptSolver(config).solve(_problem(fixture))

    assert result.status.value == "Infeasible"
    assert result.max_constraint_violation > 1.0


def test_colav_strict_cold_seed_tracks_the_committed_reference_within_rate_bounds(
    parity_corpus: dict[str, MidMpcParityFixture],
) -> None:
    fixture = parity_corpus["head_on_starboard"]
    config = replace(_config(fixture), strict_slack_bounds=True)
    source_problem = _problem(fixture)
    problem = replace(
        source_problem,
        route_bearing_rad=source_problem.own_ship.psi_rad + 0.2,
    )

    result = MidMpcIpoptSolver(config).solve(problem)

    heading_seed = result.prepared.x0[: config.horizon_steps]
    assert abs(heading_seed[0] - problem.own_ship.psi_rad) >= abs(problem.route_bearing_rad - problem.own_ship.psi_rad)
    assert np.max(np.abs(np.diff(np.r_[problem.own_ship.psi_rad, heading_seed]))) <= (
        problem.rot_max_rad_s * config.dt_s + 1.0e-12
    )
    if result.accepted_by_quality_gate:
        assert result.objective_improvement > max(1.0e-6, abs(result.seed_objective_total) * 1.0e-8)


def test_colav_strict_overtaking_seed_starts_inside_minimum_alteration_boundary(
    parity_corpus: dict[str, MidMpcParityFixture],
) -> None:
    fixture = parity_corpus["overtaking_port"]
    config = replace(_config(fixture), strict_slack_bounds=True)
    problem = _problem(fixture)

    result = MidMpcIpoptSolver(config).solve(problem)

    first_change = abs(result.prepared.x0[0] - problem.own_ship.psi_rad)
    assert first_change > problem.min_alteration_rad + math.radians(1.0)


@pytest.mark.parametrize(
    "fixture_id",
    (
        "head_on_starboard",
        "crossing_starboard",
        "stand_on_hold",
        "overtaking_port",
    ),
)
def test_direction_hold_and_overtaking_match_frozen_cpp_oracle(
    parity_corpus: dict[str, MidMpcParityFixture], fixture_id: str
) -> None:
    _assert_parity(parity_corpus[fixture_id])


def test_cpa_slack_matches_frozen_cpp_oracle(
    parity_corpus: dict[str, MidMpcParityFixture],
) -> None:
    _assert_parity(parity_corpus["close_target_cpa_slack"])


def test_active_prefix_matches_frozen_cpp_oracle(
    parity_corpus: dict[str, MidMpcParityFixture],
) -> None:
    _assert_parity(parity_corpus["active_prefix_k2"])


def test_multitarget_row_order_matches_frozen_cpp_oracle(
    parity_corpus: dict[str, MidMpcParityFixture],
) -> None:
    _assert_parity(parity_corpus["multi_target_row_order"])


def test_result_arrays_cannot_be_made_writeable(
    parity_corpus: dict[str, MidMpcParityFixture],
) -> None:
    fixture = parity_corpus["route_speed_cold"]
    result = MidMpcIpoptSolver(_config(fixture)).solve(_problem(fixture))

    with pytest.raises(ValueError):
        result.raw_x.setflags(write=True)
    with pytest.raises(ValueError):
        result.prepared.p.setflags(write=True)


def test_accepted_primal_warm_start_resamples_and_keeps_strict_slacks_zero(
    parity_corpus: dict[str, MidMpcParityFixture],
) -> None:
    fixture = parity_corpus["route_speed_cold"]
    config = replace(_config(fixture), strict_slack_bounds=True)
    problem = _problem(fixture)
    cold = MidMpcIpoptSolver(config).solve(problem)
    n = config.horizon_steps
    warm = MidMpcPrimalWarmStart(
        accepted_at_s=0.0,
        current_time_s=config.dt_s / 2.0,
        dt_s=config.dt_s,
        course_rad=np.linspace(0.1, 0.2, n),
        speed_mps=np.linspace(3.0, 4.0, n),
    )

    result = MidMpcIpoptSolver(config).solve(problem, primal_warm_start=warm)

    assert result.prepared.x0[-2:].tolist() == [0.0, 0.0]
    assert result.prepared.x0[0] != pytest.approx(cold.prepared.x0[0], abs=1e-12)
    assert np.isfinite(result.prepared.x0).all()


def test_staged_recovery_seed_is_not_replaced_by_prior_avoidance_plan(
    parity_corpus: dict[str, MidMpcParityFixture],
) -> None:
    fixture = parity_corpus["route_speed_cold"]
    config = replace(_config(fixture), strict_slack_bounds=True)
    source = _problem(fixture)
    n = config.horizon_steps
    recovery_from_k = n // 2
    mission = source.route_bearing_rad
    corridor = mission + 0.2
    problem = replace(
        source,
        route_bearing_rad=corridor,
        route_objective=MidMpcRouteObjective(
            mission_bearing_rad=mission,
            avoidance_corridor_bearing_rad=corridor,
            heading_reference_rad=(corridor,) * recovery_from_k + (mission,) * (n - recovery_from_k),
            lateral_reference_m=(0.0,) * n,
            avoidance_active_until_k=recovery_from_k,
        ),
    )
    warm = MidMpcPrimalWarmStart(
        accepted_at_s=0.0,
        current_time_s=config.dt_s / 2.0,
        dt_s=config.dt_s,
        course_rad=np.full(n, corridor),
        speed_mps=np.full(n, source.planned_speed_mps),
    )

    result = MidMpcIpoptSolver(config).solve(problem, primal_warm_start=warm)

    assert result.prepared.x0[recovery_from_k] == pytest.approx(mission)
    assert result.raw_x[n - 1] == pytest.approx(mission, abs=0.03)


def test_rejects_more_than_frozen_target_capacity(
    parity_corpus: dict[str, MidMpcParityFixture],
) -> None:
    fixture = parity_corpus["multi_target_row_order"]
    problem = _problem(fixture)
    overflow = replace(problem, targets=(problem.targets[0],) * 17)

    with pytest.raises(ValueError, match="at most 16 targets"):
        MidMpcIpoptSolver(_config(fixture)).solve(overflow)


def test_iteration_callback_aborts_after_frozen_wall_clock_limit() -> None:
    now = [100.0]
    callback = _IterationCallback(
        1,
        1,
        1,
        clock=lambda: now[0],
        max_wall_time_s=20.0,
    )

    callback.arm()
    assert float(callback.eval([])[0]) == 0.0

    now[0] = 120.001
    assert float(callback.eval([])[0]) == 1.0


def test_iteration_callback_stops_only_after_feasible_objective_improvement() -> None:
    callback = _IterationCallback(1, 1, 1, max_wall_time_s=20.0)
    callback.arm(
        quality_seed_objective=10.0,
        quality_lbx=np.array([0.0]),
        quality_ubx=np.array([2.0]),
        quality_lbg=np.array([0.0]),
        quality_ubg=np.array([2.0]),
    )

    assert float(callback.eval([np.array([1.0]), np.array([11.0]), np.array([1.0])])[0]) == 0.0
    assert float(callback.eval([np.array([1.0]), np.array([9.0]), np.array([-1.0])])[0]) == 0.0
    assert float(callback.eval([np.array([1.0]), np.array([9.0]), np.array([1.0])])[0]) == 1.0
    assert callback.quality_stop_requested is True


def test_iteration_callback_stops_at_first_feasible_iterate_from_infeasible_seed() -> None:
    callback = _IterationCallback(1, 1, 1, max_wall_time_s=20.0)
    callback.arm(
        quality_seed_objective=10.0,
        quality_stop_on_feasible=True,
        quality_lbx=np.array([0.0]),
        quality_ubx=np.array([2.0]),
        quality_lbg=np.array([0.0]),
        quality_ubg=np.array([2.0]),
    )

    assert float(callback.eval([np.array([1.0]), np.array([20.0]), np.array([-1.0])])[0]) == 0.0
    assert float(callback.eval([np.array([1.0]), np.array([20.0]), np.array([1.0])])[0]) == 1.0
    assert callback.quality_stop_requested is True


def test_iteration_callback_uses_acceptance_tolerance_for_controlled_exit() -> None:
    callback = _IterationCallback(1, 1, 1, max_wall_time_s=20.0)
    callback.arm(
        quality_seed_objective=10.0,
        quality_stop_on_feasible=True,
        quality_lbx=np.array([0.0]),
        quality_ubx=np.array([2.0]),
        quality_lbg=np.array([0.0]),
        quality_ubg=np.array([2.0]),
        quality_tolerances=(np.array([1.0e-6]), np.array([1.0e-6])),
    )

    assert float(callback.eval([np.array([1.0]), np.array([20.0]), np.array([-1.0e-5])])[0]) == 0.0
    assert float(callback.eval([np.array([1.0]), np.array([20.0]), np.array([-1.0e-7])])[0]) == 1.0
    assert callback.quality_stop_requested is True


def test_iteration_callback_accepts_bounded_nonregression_without_targets() -> None:
    callback = _IterationCallback(1, 1, 1, max_wall_time_s=20.0)
    callback.arm(
        quality_seed_objective=10.0,
        quality_required_improvement=-0.1,
        quality_lbx=np.array([0.0]),
        quality_ubx=np.array([2.0]),
        quality_lbg=np.array([0.0]),
        quality_ubg=np.array([2.0]),
    )

    assert float(callback.eval([np.array([1.0]), np.array([10.05]), np.array([1.0])])[0]) == 0.0
    assert float(callback.eval([np.array([1.0]), np.array([10.05]), np.array([1.0])])[0]) == 1.0
    assert callback.quality_stop_requested is True


def test_strict_rule_row_matches_crossing_bow_geometry(
    parity_corpus: dict[str, MidMpcParityFixture],
) -> None:
    fixture = parity_corpus["route_speed_cold"]
    config = replace(_config(fixture), strict_slack_bounds=True)
    source = _problem(fixture)
    n = config.horizon_steps
    target = MidMpcTarget(
        x_m=60.0,
        y_m=100.0,
        cog_rad=-math.pi / 2.0,
        sog_mps=4.0,
        crossing_astern_required=True,
    )
    problem = replace(
        source,
        audit_row_count=1,
        targets=(target,),
        row_schedule=MidMpcRowSchedule(
            cpa_hard_windows=(MidMpcHardWindow(n, n),),
        ),
    )
    graph = solver_module._build_graph(config, problem)
    prepared = solver_module._prepare(config, problem, graph.row_layout)

    constraints = np.asarray(graph.constraints(prepared.x0, prepared.p)).reshape(-1)

    assert constraints[graph.row_layout.rule.start] < 0.0


def test_strict_speed_rate_row_rejects_acceleration_above_active_limit(
    parity_corpus: dict[str, MidMpcParityFixture],
) -> None:
    fixture = parity_corpus["route_speed_cold"]
    config = replace(_config(fixture), strict_slack_bounds=True)
    problem = _problem(fixture)
    graph = solver_module._build_graph(config, problem)
    prepared = solver_module._prepare(config, problem, graph.row_layout)
    candidate = prepared.x0.copy()
    candidate[config.horizon_steps] = problem.own_ship.u_mps + problem.decel_max_mps2 * config.dt_s + 0.1

    constraints = np.asarray(graph.constraints(candidate, prepared.p)).reshape(-1)

    assert constraints[graph.row_layout.speed_rate.start] < 0.0


def test_strict_active_prefix_is_encoded_as_original_decision_bounds(
    parity_corpus: dict[str, MidMpcParityFixture],
) -> None:
    fixture = parity_corpus["route_speed_cold"]
    config = replace(_config(fixture), strict_slack_bounds=True)
    source = _problem(fixture)
    problem = replace(
        source,
        targets=(),
        audit_row_count=0,
        row_schedule=replace(source.row_schedule, cpa_hard_windows=()),
        prefix_active_k=1,
        prefix_psi_rad=(source.own_ship.psi_rad,),
        prefix_u_mps=(source.own_ship.u_mps,),
    )
    graph = solver_module._build_graph(config, problem)
    prepared = solver_module._prepare(config, problem, graph.row_layout)

    assert prepared.lbx[0] == prepared.ubx[0] == source.own_ship.psi_rad
    assert prepared.lbx[config.horizon_steps] == prepared.ubx[config.horizon_steps] == source.own_ship.u_mps


def test_nonoptimal_exit_requires_native_acceptable_status_and_objective_improvement() -> None:
    assert not _optimization_quality_passed(
        strict=True,
        return_status="User_Requested_Stop",
        iterations=2,
        seed_objective=249.0,
        final_objective=251.0,
        seed_primal_feasible=True,
        final_primal_feasible=True,
        decision_change_norm=0.3,
        controlled_quality_stop=True,
        accepted_iteration=1,
    )


def test_controlled_feasible_exit_does_not_compare_objective_to_infeasible_seed() -> None:
    assert _optimization_quality_passed(
        strict=True,
        return_status="User_Requested_Stop",
        iterations=2,
        seed_objective=10.0,
        final_objective=20.0,
        seed_primal_feasible=False,
        final_primal_feasible=True,
        decision_change_norm=0.3,
        controlled_quality_stop=True,
        accepted_iteration=1,
    )


def test_controlled_target_free_exit_allows_bounded_objective_nonregression() -> None:
    assert _optimization_quality_passed(
        strict=True,
        return_status="User_Requested_Stop",
        iterations=2,
        seed_objective=10.0,
        final_objective=10.05,
        seed_primal_feasible=True,
        final_primal_feasible=True,
        decision_change_norm=0.3,
        controlled_quality_stop=True,
        accepted_iteration=1,
        required_improvement=-0.1,
    )


def test_controlled_target_free_exit_accepts_exact_nominal_seed() -> None:
    assert _optimization_quality_passed(
        strict=True,
        return_status="User_Requested_Stop",
        iterations=1,
        seed_objective=0.0,
        final_objective=0.0,
        seed_primal_feasible=True,
        final_primal_feasible=True,
        decision_change_norm=0.0,
        controlled_quality_stop=True,
        accepted_iteration=1,
        required_improvement=-0.03,
    )


def test_target_free_quality_ceiling_covers_ipopt_barrier_entry() -> None:
    assert _target_free_required_improvement(0.0015) == pytest.approx(-0.0285)
    assert _target_free_required_improvement(1.0) == pytest.approx(-0.05)
