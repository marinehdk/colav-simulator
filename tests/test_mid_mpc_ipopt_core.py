from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from colav_simulator.core.colav.mid_mpc import (
    MidMpcConfig,
    MidMpcIpoptSolver,
    MidMpcOwnShip,
    MidMpcProblem,
    MidMpcRouteFrame,
    MidMpcRowSchedule,
    MidMpcTarget,
)
from colav_simulator.mid_mpc_parity import (
    MidMpcParityFixture,
    load_mid_mpc_parity_corpus,
)

CORPUS_PATH = Path(__file__).parent / "fixtures" / "mid_mpc_ipopt" / "v1.jsonl"
NORMALIZED_INTENT_BY_FIXTURE = {
    "route_speed_cold": (False, 0, False, 0, 0),
    "head_on_starboard": (True, 1, True, 7, 1),
    "crossing_starboard": (True, 1, True, 7, 1),
    "stand_on_hold": (False, 0, True, 0, 1),
    "overtaking_port": (True, -1, False, 7, 1),
    "close_target_cpa_slack": (False, 0, False, 0, 0),
    "active_prefix_k2": (False, 0, False, 0, 0),
    "multi_target_row_order": (False, 0, False, 0, 0),
}


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
    lateral_active, preferred_side, asymmetry_active, cpa_hard_from_k, audit_rows = NORMALIZED_INTENT_BY_FIXTURE[
        fixture.fixture_id
    ]
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
        lateral_active=lateral_active,
        preferred_side=preferred_side,
        starboard_asymmetry_active=asymmetry_active,
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
            prefix_softening=problem["prefix_active_k"] > 0,
            cpa_hard_from_k=cpa_hard_from_k,
        ),
        audit_row_count=audit_rows,
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
    assert result.objective_components.total == pytest.approx(expected["objective_total"], abs=objective_tolerance)
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


def test_rejects_more_than_frozen_target_capacity(
    parity_corpus: dict[str, MidMpcParityFixture],
) -> None:
    fixture = parity_corpus["multi_target_row_order"]
    problem = _problem(fixture)
    overflow = replace(problem, targets=(problem.targets[0],) * 17)

    with pytest.raises(ValueError, match="at most 16 targets"):
        MidMpcIpoptSolver(_config(fixture)).solve(overflow)
