from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from shapely.geometry import GeometryCollection, Polygon

from colav_simulator.core.colav.custom_mpc_adapter import FactoryContext, PlannerInput, TrackedObstacle
from colav_simulator.core.colav.diagnostics import ColavExecutionError, PlanStatus
from colav_simulator.integrations import IntegrationRegistry
from colav_simulator.integrations.potocnik_mpc import (
    PAPER_COLREG_ZONE_M,
    UPSTREAM_COMMIT,
    PotocnikMPCParams,
    PotocnikSimplifiedMPC,
)


def planner_input(
    *,
    tracks: tuple[TrackedObstacle, ...] = (),
    ownship_state: np.ndarray | None = None,
    enc=None,
) -> PlannerInput:
    return PlannerInput(
        sim_time_s=0.0,
        dt_sim_s=0.5,
        waypoints_enu_m=np.array([[0.0, 10000.0], [0.0, 0.0]]),
        speed_plan_mps=np.array([7.0, 7.0]),
        ownship_state=(
            np.array([0.0, 0.0, 0.0, 7.0, 0.0, 0.0])
            if ownship_state is None
            else ownship_state
        ),
        tracks=tracks,
        enc=enc,
        goal_state=None,
        disturbance=None,
        algorithm_seed=9,
    )


def track(
    *,
    position_ne: tuple[float, float],
    velocity_ne: tuple[float, float] = (0.0, 0.0),
) -> TrackedObstacle:
    return TrackedObstacle(
        target_id=1,
        state_enu=np.array([*position_ne, *velocity_ne]),
        covariance=np.zeros((4, 4)),
        length_m=8.45,
        width_m=3.0,
        observed_at_s=0.0,
        age_s=0.0,
    )


def test_executable_fan_uses_20_by_5_second_profile() -> None:
    params = PotocnikMPCParams()
    solver = PotocnikSimplifiedMPC(params)

    trajectories = solver.generate_candidate_trajectories(planner_input().ownship_state, 7.0)
    port_extreme = trajectories[0]
    center = trajectories[params.candidate_count // 2]

    assert trajectories.shape == (45, 9, 21)
    assert -10.0 < np.rad2deg(port_extreme[2, 1]) < 0.0
    assert np.rad2deg(port_extreme[2, 2]) < np.rad2deg(port_extreme[2, 1])
    assert abs(np.rad2deg(port_extreme[5, 1])) <= params.max_yaw_rate_deg_s
    assert center[0, 1] == pytest.approx(35.0)
    assert center[1, 1] == pytest.approx(0.0)


def test_paper_solver_selects_route_aligned_candidate_without_conflict() -> None:
    solver = PotocnikSimplifiedMPC(PotocnikMPCParams())

    solution = solver.solve(planner_input())

    assert solution.status == PlanStatus.SUCCESS
    assert solution.predicted_trajectory.shape == (9, 21)
    assert solution.control_reference[2, 0] == pytest.approx(0.0)
    assert solution.algorithm_details["selected_candidate_index"] == 22
    assert solution.algorithm_details["upstream_commit"] == UPSTREAM_COMMIT
    assert solution.algorithm_details["selection_mode"] == "initial_heading"
    assert solution.algorithm_details["selection_score_unit"] == "normalized"
    assert solution.algorithm_details["selected_heading_increment_rad"] == pytest.approx(0.0)
    assert solution.algorithm_details["speed_scale"] == pytest.approx(1.0)
    assert solution.algorithm_details["solve_period_s"] == pytest.approx(5.0)
    assert solution.algorithm_details["prediction_steps"] == 20
    assert solution.algorithm_details["prediction_step_s"] == pytest.approx(5.0)
    assert solution.algorithm_details["prediction_distance_m"] == pytest.approx(700.0)
    assert len(solution.algorithm_details["candidate_heading_increments_rad"]) == 45
    assert solution.algorithm_details["candidate_feasible"] == [True] * 45
    assert solution.algorithm_details["candidate_minimum_clearance_m"] == [None] * 45
    assert solution.constraints["dynamic_collision"]["minimum_predicted_clearance_m"] is None
    assert solution.constraints["planning_zone"] == {
        "distance_m": PAPER_COLREG_ZONE_M,
        "semantics": "paper_colreg_zone_reference",
    }


def test_dynamic_conflict_filters_nominal_candidate_and_commands_avoidance() -> None:
    solver = PotocnikSimplifiedMPC(PotocnikMPCParams(collision_distance_m=300.0))
    head_on = track(position_ne=(1300.0, 0.0), velocity_ne=(-7.0, 0.0))

    solution = solver.solve(planner_input(tracks=(head_on,)))

    assert abs(float(solution.control_reference[2, 0])) > np.deg2rad(2.0)
    assert solution.algorithm_details["feasible_candidate_count"] < 45
    assert (
        solution.constraints["dynamic_collision"]["minimum_predicted_clearance_m"]
        >= solution.constraints["dynamic_collision"]["required_clearance_m"]
    )
    assert solution.algorithm_details["nominal_candidate_feasible"] is False
    assert solution.algorithm_details["avoidance_turn_sign"] != 0
    assert solution.algorithm_details["head_on_active"] is True
    assert solution.algorithm_details["selected_heading_increment_rad"] > 0.0
    assert solution.constraints["colreg_maneuver"]["side_constraint_relaxed"] is False
    assert solution.control_trajectory is not None
    assert solution.control_trajectory[2, 0] == pytest.approx(
        solution.control_trajectory[2, 1]
    )
    assert solution.predicted_trajectory[2, 1] < solution.control_trajectory[2, 1]


def test_static_enc_hazard_filters_grounding_candidates() -> None:
    land = Polygon(
        [
            (-40.0, 300.0),
            (40.0, 300.0),
            (40.0, 500.0),
            (-40.0, 500.0),
        ]
    )
    empty = GeometryCollection()
    enc = SimpleNamespace(
        land=SimpleNamespace(geometry=land),
        shore=SimpleNamespace(geometry=empty),
        seabed={
            0: SimpleNamespace(geometry=empty),
            5: SimpleNamespace(geometry=empty),
        },
    )
    solver = PotocnikSimplifiedMPC(PotocnikMPCParams())

    solution = solver.solve(planner_input(enc=enc))

    assert solution.algorithm_details["candidate_static_feasible"][22] is False
    assert solution.algorithm_details["feasible_candidate_count"] < 45
    assert solution.algorithm_details["selected_candidate_index"] != 22
    assert solution.constraints["static_grounding"]["enc_applied"] is True
    assert (
        solution.constraints["static_grounding"]["minimum_predicted_clearance_m"]
        > solution.constraints["static_grounding"]["required_clearance_m"]
    )
    assert solution.constraints["static_grounding"]["required_clearance_m"] == pytest.approx(20.0)


def test_replanning_keeps_avoidance_side_and_limits_command_change() -> None:
    solver = PotocnikSimplifiedMPC(PotocnikMPCParams(collision_distance_m=300.0))
    first = solver.solve(
        planner_input(tracks=(track(position_ne=(1300.0, 40.0), velocity_ne=(-7.0, 0.0)),))
    )
    first_course = float(first.control_reference[2, 0])
    first_sign = int(first.algorithm_details["avoidance_turn_sign"])
    second_state = np.array([35.0, 0.0, first_course * 0.5, 7.0, 0.0, 0.0])

    second = solver.solve(
        planner_input(
            ownship_state=second_state,
            tracks=(track(position_ne=(1230.0, -40.0), velocity_ne=(-7.0, 0.0)),),
        )
    )
    second_course = float(second.control_reference[2, 0])

    assert int(second.algorithm_details["avoidance_turn_sign"]) == first_sign
    assert np.sign(second.algorithm_details["selected_heading_increment_rad"]) == first_sign
    assert abs(float(np.arctan2(np.sin(second_course - first_course), np.cos(second_course - first_course)))) <= (
        np.deg2rad(5.0) + 1e-12
    )
    assert second.constraints["heading_increment"]["rate_limit_relaxed"] is False
    assert second.algorithm_details["reversal_penalty"] == pytest.approx(0.0)
    assert second.algorithm_details["turn_reversal_count"] == 0


def test_no_feasible_fan_is_infeasible_not_fallback() -> None:
    solver = PotocnikSimplifiedMPC(PotocnikMPCParams(collision_distance_m=10000.0))

    with pytest.raises(ColavExecutionError) as error:
        solver.solve(planner_input(tracks=(track(position_ne=(0.0, 0.0)),)))

    assert error.value.status == PlanStatus.INFEASIBLE


def test_registry_loads_paper_plugin_with_complete_identity() -> None:
    config = {
        "factory": "colav_simulator.integrations.potocnik_mpc:create",
        "dependency_lock": str(Path("uv.lock").resolve()),
    }
    adapter = IntegrationRegistry().build_algorithm(
        "potocnik_simplified_mpc",
        config,
        factory_context=FactoryContext("potocnik_simplified_mpc", 7),
    )

    assert adapter is not None
    assert adapter.descriptor.version.endswith(UPSTREAM_COMMIT[:12])
    assert adapter.build_identity.complete is True
    assert adapter.get_diagnostics().fallback_used is False


def test_registry_loads_published_paper_profile_by_stable_id() -> None:
    adapter = IntegrationRegistry().build_algorithm(
        "potocnik_simplified_mpc",
        factory_context=FactoryContext("potocnik_simplified_mpc", 7),
    )

    assert adapter is not None
    assert adapter.descriptor.algorithm_id == "potocnik_simplified_mpc"
    assert adapter.descriptor.horizon_dt == pytest.approx(5.0)
    assert adapter.descriptor.horizon_steps == 21
    assert adapter.descriptor.execution_profile.solve_period_s == pytest.approx(5.0)
    assert adapter.build_identity.complete is True
    assert adapter.get_diagnostics().fallback_used is False
