from pathlib import Path

import numpy as np
import pytest

from colav_simulator.core.colav.custom_mpc_adapter import FactoryContext, PlannerInput, TrackedObstacle
from colav_simulator.core.colav.diagnostics import ColavExecutionError, PlanStatus
from colav_simulator.integrations import IntegrationRegistry
from colav_simulator.integrations.potocnik_mpc import (
    PAPER_COLREG_ZONE_M,
    UPSTREAM_COMMIT,
    PotocnikMPCParams,
    PotocnikSimplifiedMPC,
)


def planner_input(*, tracks: tuple[TrackedObstacle, ...] = ()) -> PlannerInput:
    return PlannerInput(
        sim_time_s=0.0,
        dt_sim_s=0.5,
        waypoints_enu_m=np.array([[0.0, 10000.0], [0.0, 0.0]]),
        speed_plan_mps=np.array([7.0, 7.0]),
        ownship_state=np.array([0.0, 0.0, 0.0, 7.0, 0.0, 0.0]),
        tracks=tracks,
        enc=None,
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


def test_paper_fan_matches_matlab_heading_decay_and_kinematics() -> None:
    params = PotocnikMPCParams()
    solver = PotocnikSimplifiedMPC(params)

    trajectories = solver.generate_candidate_trajectories(planner_input().ownship_state, 7.0)
    port_extreme = trajectories[0]
    center = trajectories[params.candidate_count // 2]

    assert trajectories.shape == (45, 9, 17)
    assert np.rad2deg(port_extreme[2, 1]) == pytest.approx(-20.0)
    assert np.rad2deg(port_extreme[2, 2]) == pytest.approx(-39.0)
    assert center[0, 1] == pytest.approx(350.0)
    assert center[1, 1] == pytest.approx(0.0)


def test_paper_solver_selects_route_aligned_candidate_without_conflict() -> None:
    solver = PotocnikSimplifiedMPC(PotocnikMPCParams())

    solution = solver.solve(planner_input())

    assert solution.status == PlanStatus.SUCCESS
    assert solution.predicted_trajectory.shape == (9, 17)
    assert solution.control_reference[2, 0] == pytest.approx(0.0)
    assert solution.algorithm_details["selected_candidate_index"] == 22
    assert solution.algorithm_details["upstream_commit"] == UPSTREAM_COMMIT
    assert solution.algorithm_details["selection_mode"] == "initial_heading"
    assert solution.algorithm_details["selection_score_unit"] == "rad"
    assert solution.algorithm_details["selected_heading_increment_rad"] == pytest.approx(0.0)
    assert solution.algorithm_details["speed_scale"] == pytest.approx(1.0)
    assert solution.algorithm_details["solve_period_s"] == pytest.approx(0.5)
    assert solution.algorithm_details["prediction_steps"] == 16
    assert solution.algorithm_details["prediction_distance_m"] == pytest.approx(5600.0)
    assert len(solution.algorithm_details["candidate_heading_increments_rad"]) == 45
    assert solution.algorithm_details["candidate_feasible"] == [True] * 45
    assert solution.constraints["dynamic_collision"]["minimum_predicted_clearance_m"] is None
    assert solution.constraints["planning_zone"] == {
        "distance_m": PAPER_COLREG_ZONE_M,
        "semantics": "paper_colreg_zone_reference",
    }


def test_dynamic_conflict_filters_nominal_candidate_and_commands_avoidance() -> None:
    solver = PotocnikSimplifiedMPC(PotocnikMPCParams())
    head_on = track(position_ne=(3000.0, 0.0), velocity_ne=(-7.0, 0.0))

    solution = solver.solve(planner_input(tracks=(head_on,)))

    assert abs(float(solution.control_reference[2, 0])) > np.deg2rad(2.0)
    assert solution.algorithm_details["feasible_candidate_count"] < 45
    assert (
        solution.constraints["dynamic_collision"]["minimum_predicted_clearance_m"]
        >= solution.constraints["dynamic_collision"]["required_clearance_m"]
    )


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
    assert adapter.build_identity.complete is True
    assert adapter.get_diagnostics().fallback_used is False
