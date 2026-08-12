import time

import numpy as np
import pytest

from colav_simulator.core.colav.custom_mpc_adapter import (
    AlgorithmDescriptor,
    CustomMPCAdapter,
    DeadlineMode,
    ExecutionProfile,
    FactoryContext,
    MPCSolution,
    PlannerInput,
)
from colav_simulator.core.colav.diagnostics import ColavExecutionError, PlanStatus


def descriptor(**profile_overrides) -> AlgorithmDescriptor:
    profile = {
        "solve_period_s": 1.0,
        "deadline_s": 1.0,
        "max_consecutive_timeout": 2,
    }
    profile.update(profile_overrides)
    return AlgorithmDescriptor(
        algorithm_id="schedule_mpc",
        version="1",
        control_form="course_speed_reference",
        state_layout=("x", "y", "psi", "u", "v", "r", "x_ddot", "y_ddot", "psi_dot"),
        predictor_model="fixture",
        horizon_dt=0.5,
        horizon_steps=4,
        objective_terms=("tracking",),
        constraint_terms=("dynamics",),
        solver="fixture",
        seed_policy="deterministic",
        execution_profile=ExecutionProfile(**profile),
    )


def solution(
    planner_input,
    *,
    sleep_s: float = 0.0,
    wrap_heading: bool = False,
    strict_total_deadline: bool = False,
) -> MPCSolution:
    time.sleep(sleep_s)
    trajectory = np.zeros((9, 4))
    trajectory[:6, 0] = planner_input.ownship_state
    trajectory[3, :] = planner_input.ownship_state[3]
    for index in range(1, 4):
        trajectory[0, index] = planner_input.ownship_state[0] + 2.0 * index
        trajectory[2, index] = planner_input.ownship_state[2]
    if wrap_heading:
        trajectory[2] = [np.deg2rad(179.0), np.deg2rad(-179.0), np.deg2rad(-177.0), np.deg2rad(-175.0)]
    return MPCSolution(
        control_reference=trajectory[:, 1].reshape(9, 1),
        predicted_trajectory=trajectory,
        horizon_dt_s=0.5,
        algorithm_details={"strict_total_deadline": strict_total_deadline},
    )


def plan(adapter: CustomMPCAdapter, t: float, heading: float = 0.0) -> np.ndarray:
    return adapter.plan(
        t,
        np.array([[0.0, 100.0], [0.0, 0.0]]),
        np.array([4.0, 4.0]),
        np.array([0.0, 0.0, heading, 4.0, 0.0, 0.0]),
        [],
        dt=0.5,
    )


def test_hold_samples_shortest_angle_without_new_solve() -> None:
    adapter = CustomMPCAdapter(
        descriptor=descriptor(),
        solve=lambda value: solution(value, wrap_heading=True),
        context=FactoryContext("schedule_mpc", 0),
    )

    plan(adapter, 0.0, np.deg2rad(179.0))
    held = plan(adapter, 0.25, np.deg2rad(179.0))

    assert np.rad2deg(held[2, 0]) == pytest.approx(-180.0, abs=1e-6)
    assert adapter.get_colav_data()["planner"]["solve_id"] == 1
    assert adapter.get_colav_data()["planner"]["solver_executed"] is False


def test_hold_uses_explicit_executable_control_trajectory() -> None:
    def solve(value: PlannerInput) -> MPCSolution:
        candidate = solution(value)
        controls = candidate.predicted_trajectory.copy()
        controls[2, :] = np.deg2rad(10.0)
        return MPCSolution(
            control_reference=controls[:, 0].reshape(9, 1),
            predicted_trajectory=candidate.predicted_trajectory,
            control_trajectory=controls,
            horizon_dt_s=candidate.horizon_dt_s,
        )

    adapter = CustomMPCAdapter(
        descriptor=descriptor(),
        solve=solve,
        context=FactoryContext("schedule_mpc", 0),
    )

    first = plan(adapter, 0.0)
    held = plan(adapter, 0.25)

    assert np.rad2deg(first[2, 0]) == pytest.approx(10.0)
    assert np.rad2deg(held[2, 0]) == pytest.approx(10.0)


def test_deadline_timeout_feasible_is_executable_and_visible_on_hold() -> None:
    adapter = CustomMPCAdapter(
        descriptor=descriptor(deadline_s=0.0001),
        solve=lambda value: solution(value, sleep_s=0.002),
        context=FactoryContext("schedule_mpc", 0),
    )

    first = plan(adapter, 0.0)
    held = plan(adapter, 0.5)

    assert first.shape == held.shape == (9, 1)
    assert adapter.get_diagnostics().status == PlanStatus.TIMEOUT_FEASIBLE
    assert adapter.get_colav_data()["planner"]["status"] == PlanStatus.TIMEOUT_FEASIBLE.value


def test_deadline_off_keeps_success_but_declares_mode() -> None:
    adapter = CustomMPCAdapter(
        descriptor=descriptor(deadline_s=0.0001),
        solve=lambda value: solution(value, sleep_s=0.002),
        context=FactoryContext("schedule_mpc", 0, deadline_mode=DeadlineMode.OFF),
    )

    plan(adapter, 0.0)

    assert adapter.get_diagnostics().status == PlanStatus.SUCCESS
    assert adapter.get_diagnostics().details["deadline_mode"] == DeadlineMode.OFF.value


def test_strict_total_deadline_rejects_candidate_instead_of_downgrading_to_timeout() -> None:
    adapter = CustomMPCAdapter(
        descriptor=descriptor(deadline_s=0.0001),
        solve=lambda value: solution(value, sleep_s=0.002, strict_total_deadline=True),
        context=FactoryContext("schedule_mpc", 0),
    )

    with pytest.raises(ColavExecutionError, match="total commit deadline") as error:
        plan(adapter, 0.0)

    assert error.value.status is PlanStatus.NUMERICAL_FAILURE
    assert adapter.get_diagnostics().details["failure_code"] == "TOTAL_DEADLINE_EXCEEDED"
    assert adapter.get_current_plan().shape == (9, 1)
    assert np.count_nonzero(adapter.get_current_plan()) == 0


def test_schedule_rejects_backwards_time_and_insufficient_horizon() -> None:
    adapter = CustomMPCAdapter(
        descriptor=descriptor(),
        solve=solution,
        context=FactoryContext("schedule_mpc", 0),
    )
    plan(adapter, 0.0)
    plan(adapter, 0.5)
    with pytest.raises(ColavExecutionError, match="backwards"):
        plan(adapter, 0.25)

    short = CustomMPCAdapter(
        descriptor=descriptor(solve_period_s=2.0),
        solve=solution,
        context=FactoryContext("schedule_mpc", 0),
    )
    with pytest.raises(ColavExecutionError, match="does not cover"):
        plan(short, 0.0)


@pytest.mark.parametrize("status", (PlanStatus.INFEASIBLE, PlanStatus.NUMERICAL_FAILURE))
def test_non_success_solution_statuses_fail_stop(status: PlanStatus) -> None:
    def solve(value: PlannerInput) -> MPCSolution:
        candidate = solution(value)
        return MPCSolution(
            control_reference=candidate.control_reference,
            predicted_trajectory=candidate.predicted_trajectory,
            status=status,
            horizon_dt_s=candidate.horizon_dt_s,
            feasible=False,
        )

    adapter = CustomMPCAdapter(
        descriptor=descriptor(),
        solve=solve,
        context=FactoryContext("schedule_mpc", 0),
    )
    with pytest.raises(ColavExecutionError) as error:
        plan(adapter, 0.0)
    assert error.value.status == status


def test_solver_exception_and_invalid_output_remain_distinct() -> None:
    failed = CustomMPCAdapter(
        descriptor=descriptor(),
        solve=lambda _value: (_ for _ in ()).throw(RuntimeError("solver failed")),
        context=FactoryContext("schedule_mpc", 0),
    )
    with pytest.raises(ColavExecutionError) as numerical:
        plan(failed, 0.0)
    assert numerical.value.status == PlanStatus.NUMERICAL_FAILURE

    invalid = CustomMPCAdapter(
        descriptor=descriptor(),
        solve=lambda _value: np.zeros((9, 4)),
        context=FactoryContext("schedule_mpc", 0),
    )
    with pytest.raises(ColavExecutionError) as bad_contract:
        plan(invalid, 0.0)
    assert bad_contract.value.status == PlanStatus.INVALID_INPUT
