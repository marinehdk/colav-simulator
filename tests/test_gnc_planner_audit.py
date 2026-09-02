"""S7.0 planner route-output audit (Issue #62): characterization of every registered COLAV planner.

These tests pin observed output-shape, direct-reference, lifecycle and
prediction/execution-boundary facts for each planner registered in
``IntegrationRegistry`` (colav_simulator/integrations/registry.py). They are
characterization pins, not red-green behavior tests: each assertion records a
value observed on the baseline (HEAD ac765d6) before the tracked-route
integration slice (#63). No planner behavior is modified by this audit.

Facts pinned here are the executable evidence behind
``docs/evaluation/s7-planner-route-output-audit.md``. Any assertion failure
means planner output semantics drifted and the audit must be re-run.

All scenarios are deterministic and local: no RNG, no wall-clock dependence
(deadline enforcement is disabled for adapter planners), no network.
"""

from __future__ import annotations

import numpy as np
import pytest

from colav_simulator.core.colav.custom_mpc_adapter import (
    CustomMPCAdapter,
    DeadlineMode,
    FactoryContext,
)
from colav_simulator.core.colav.diagnostics import ColavExecutionError, PlanStatus
from colav_simulator.core.tracking.trackers import TrackKey, TrackSnapshot, TrackStatus
from colav_simulator.integrations.psbmpc import PSBMPCColav
from colav_simulator.integrations.registry import IntegrationRegistry
from colav_simulator.integrations.rrt import RRTStarColav

# The registered planner (algorithm-kind) set at the audit baseline. Tracker
# registrations (scenario_default/god/kf/vimmjipda) are out of scope.
REGISTERED_ALGORITHM_IDS = frozenset(
    {
        "nominal",
        "vo",
        "sbmpc",
        "mid_mpc_ipopt",
        "potocnik_simplified_mpc",
        "potocnik_colreg_fan_mpc",
        "psbmpc",
        "sbmpc_reference",
        "rrt",
        "rlmpc",
    }
)

# Lifecycle fields that only an accepted-route authority may carry. Every
# non-Mid-MPC planner output stays on the direct-reference path and must not
# grow these fields without a new audit (AC: prediction is never a route).
ROUTE_LIFECYCLE_FIELDS = (
    "rolling_plan",
    "accepted_plan_receipt",
    "route_id",
    "valid_until_s",
    "revision_reason",
)

_MID_MPC_PLUGIN = {
    "factory": "colav_simulator.integrations.mid_mpc_ipopt:create",
    "kwargs": {
        "horizon_steps": 4,
        "horizon_dt_s": 5.0,
        "solve_period_s": 5.0,
        "deadline_s": 20.0,
    },
}


def _head_on_snapshot(t: float, *, north_m: float = 2000.0, speed_mps: float = 7.0) -> TrackSnapshot:
    """Deterministic head-on target: southbound at bearing 0 from ownship."""
    return TrackSnapshot(
        key=TrackKey(1, 1),
        state=np.array([north_m, 0.0, -speed_mps, 0.0]),
        covariance=np.zeros((4, 4)),
        length_m=8.45,
        width_m=3.0,
        observed_at_s=t,
        generated_at_s=t,
        status=TrackStatus.UPDATED,
        source="planner-audit",
    )


def _legacy_head_on(north_m: float, speed_mps: float = 7.0) -> tuple:
    """Same target as a legacy do_list tuple for the pre-adapter wrappers."""
    return (1, np.array([north_m, 0.0, -speed_mps, 0.0]), np.zeros((4, 4)), 8.45, 3.0)


def _mid_mpc_plan(
    adapter: CustomMPCAdapter,
    t: float,
    *,
    waypoints: np.ndarray | None = None,
    ownship: np.ndarray | None = None,
    target_north_m: float = 2000.0,
) -> np.ndarray:
    return adapter.plan(
        t,
        np.array([[0.0, 500.0], [0.0, 0.0]]) if waypoints is None else waypoints,
        np.array([4.0, 4.0]),
        np.array([0.0, 0.0, 0.0, 4.0, 0.0, 0.0]) if ownship is None else ownship,
        [_head_on_snapshot(t, north_m=target_north_m)],
        dt=1.0,
        os_length=15.0,
        os_model_name="Viknes",
        os_controller_name="FLSC",
        os_max_turn_rate_radps=np.deg2rad(3.0),
    )


@pytest.fixture(scope="module")
def registry() -> IntegrationRegistry:
    return IntegrationRegistry()


def _adapter(registry: IntegrationRegistry, algorithm_id: str) -> CustomMPCAdapter:
    factories = {
        "potocnik_simplified_mpc": "colav_simulator.integrations.potocnik_mpc:create",
        "potocnik_colreg_fan_mpc": "colav_simulator.integrations.potocnik_colreg_mpc:create",
        "mid_mpc_ipopt": _MID_MPC_PLUGIN["factory"],
    }
    kwargs: dict[str, object] = {"solve_period_s": 5.0, "deadline_s": 20.0}
    if algorithm_id == "mid_mpc_ipopt":
        kwargs.update(_MID_MPC_PLUGIN["kwargs"])
    return registry.build_algorithm(
        algorithm_id,
        {"factory": factories[algorithm_id], "kwargs": kwargs},
        factory_context=FactoryContext(
            algorithm_id,
            0,
            scenario_id="planner_audit",
            tracker_id="god",
            deadline_mode=DeadlineMode.OFF,
        ),
    )


def _assert_no_route_lifecycle_fields(details: dict) -> None:
    present = {key for key in ROUTE_LIFECYCLE_FIELDS if key in details}
    assert not present, f"direct-reference planner grew route-lifecycle fields: {sorted(present)}"


def _assert_sha256(value: object) -> None:
    assert isinstance(value, str) and len(value) == 64 and set(value) <= set("0123456789abcdef")


# ---------------------------------------------------------------------------
# Registry enumeration (audit scope)
# ---------------------------------------------------------------------------


def test_registry_algorithm_ids_are_exactly_the_audited_set(registry: IntegrationRegistry) -> None:
    algorithm_ids = {
        identifier for identifier, status in registry.statuses().items() if status.kind == "algorithm"
    }
    assert algorithm_ids == REGISTERED_ALGORITHM_IDS


def test_builtin_planners_are_always_available(registry: IntegrationRegistry) -> None:
    for identifier in ("nominal", "vo", "sbmpc", "mid_mpc_ipopt", "potocnik_simplified_mpc", "potocnik_colreg_fan_mpc"):
        assert registry.statuses()[identifier].available is True, identifier


def test_nominal_registers_no_colav_authority(registry: IntegrationRegistry) -> None:
    assert registry.build_algorithm("nominal") is None


# ---------------------------------------------------------------------------
# vo (Kuwata VO + LOS) — reactive command, no route
# ---------------------------------------------------------------------------


def test_vo_emits_single_column_course_speed_reference(registry: IntegrationRegistry) -> None:
    planner = registry.build_algorithm("vo")
    plan = planner.plan(
        0.0,
        np.array([[0.0, 10000.0], [0.0, 0.0]]),
        np.array([7.0, 7.0]),
        np.array([0.0, 0.0, 0.0, 7.0, 0.0, 0.0]),
        [],
    )

    assert plan.shape == (9, 1)
    assert plan[0:2, 0] == pytest.approx(0.0, abs=1e-9)  # no position reference
    assert plan[2, 0] == pytest.approx(0.0, abs=1e-9)  # nominal course along route
    assert plan[3, 0] == pytest.approx(7.0968, abs=1e-3)  # LOS speed reference
    assert np.all(plan[4:9, 0] == 0.0)
    current = planner.get_current_plan()
    assert current.shape == (9, 1)
    assert np.array_equal(current, plan)
    diagnostics = planner.get_diagnostics()
    assert diagnostics.status is PlanStatus.SUCCESS
    assert diagnostics.feasible is True
    assert diagnostics.fallback_used is False
    _assert_no_route_lifecycle_fields(diagnostics.details)


def test_vo_trace_prediction_is_ownship_anchored_command_not_a_route(registry: IntegrationRegistry) -> None:
    planner = registry.build_algorithm("vo")
    ownship = np.array([7.0, 0.0, 0.0, 7.0, 0.0, 0.0])
    plan = planner.plan(
        1.0,
        np.array([[0.0, 10000.0], [0.0, 0.0]]),
        np.array([7.0, 7.0]),
        ownship,
        [_legacy_head_on(2000.0)],
    )

    assert plan.shape == (9, 1)
    trace = planner.get_colav_data()["planner"]
    assert trace["algorithm_id"] == "vo"
    prediction = np.asarray(trace["predicted_trajectory"])
    assert prediction.shape == (9, 1)
    # The VO "predicted trajectory" is the command reference with the ownship
    # position written into rows 0..1 of column 0: a reactive command, not a
    # trajectory over a horizon and never an accepted route.
    assert prediction[0:2, 0] == pytest.approx(ownship[0:2], abs=1e-9)
    assert prediction[2, 0] == pytest.approx(plan[2, 0], abs=1e-12)
    assert prediction[3, 0] == pytest.approx(plan[3, 0], abs=1e-12)
    assert set(trace["selected_command"]) == {"course_rad", "speed_mps"}
    diagnostics = planner.get_diagnostics()
    assert {"solver_executed", "solve_id"} <= set(diagnostics.details)
    _assert_no_route_lifecycle_fields(diagnostics.details)


# ---------------------------------------------------------------------------
# sbmpc (built-in SB-MPC wrapper) — LOS reference offsets on column 0
# ---------------------------------------------------------------------------


def test_sbmpc_holds_nominal_reference_until_solve_period(registry: IntegrationRegistry) -> None:
    planner = registry.build_algorithm("sbmpc")
    waypoints = np.array([[0.0, 10000.0], [0.0, 0.0]])

    plan = planner.plan(0.0, waypoints, np.array([7.0, 7.0]), np.array([0.0, 0.0, 0.0, 7.0, 0.0, 0.0]), [])

    assert plan.shape == (9, 1)
    assert plan[2, 0] == pytest.approx(0.0, abs=1e-9)
    assert plan[3, 0] == pytest.approx(7.0, abs=1e-9)
    details = planner.get_diagnostics().details
    assert details["solver_executed"] is False  # activation gate: first run only after 5 s
    assert details["solve_id"] == 0
    _assert_no_route_lifecycle_fields(details)

    plan_t5 = planner.plan(
        5.0,
        waypoints,
        np.array([7.0, 7.0]),
        np.array([35.0, 0.0, 0.0, 7.0, 0.0, 0.0]),
        [_legacy_head_on(800.0)],  # inside the D_INIT_=1000 m activation range
    )

    details_t5 = planner.get_diagnostics().details
    assert details_t5["solver_executed"] is True
    assert details_t5["solve_id"] == 1
    assert details_t5["course_offset_rad"] == pytest.approx(0.2617993877991494, abs=1e-9)  # +15 deg
    assert plan_t5[2, 0] == pytest.approx(0.2617993877991494, abs=1e-6)
    assert plan_t5[3, 0] == pytest.approx(7.0, abs=1e-6)
    assert planner.get_diagnostics().status is PlanStatus.SUCCESS


def test_sbmpc_current_plan_is_prediction_grid_not_the_command(registry: IntegrationRegistry) -> None:
    planner = registry.build_algorithm("sbmpc")
    waypoints = np.array([[0.0, 10000.0], [0.0, 0.0]])
    planner.plan(0.0, waypoints, np.array([7.0, 7.0]), np.array([0.0, 0.0, 0.0, 7.0, 0.0, 0.0]), [])
    planner.plan(
        5.0,
        waypoints,
        np.array([7.0, 7.0]),
        np.array([35.0, 0.0, 0.0, 7.0, 0.0, 0.0]),
        [_legacy_head_on(800.0)],
    )

    current = planner.get_current_plan()
    assert current.shape == (9, 60)  # T_=150 s horizon at DT_=2.5 s
    trace = planner.get_colav_data()["planner"]
    assert trace["horizon_dt_s"] == pytest.approx(2.5)
    # get_current_plan returns the SB-MPC *prediction*, anchored at the
    # solve-time ownship state — it is not the 9x1 command the ship consumed
    # at plan() and must never be treated as an accepted route.
    assert current[0, 0] == pytest.approx(35.0, abs=1e-9)
    assert current[1, 0] == pytest.approx(0.0, abs=1e-9)
    assert current.shape != (9, 1)


# ---------------------------------------------------------------------------
# potocnik_simplified_mpc — adapter planner, command column + fan prediction
# ---------------------------------------------------------------------------


def _potocnik_simplified(registry: IntegrationRegistry) -> CustomMPCAdapter:
    return _adapter(registry, "potocnik_simplified_mpc")


def test_potocnik_simplified_emits_command_column_and_fan_prediction(registry: IntegrationRegistry) -> None:
    planner = _potocnik_simplified(registry)
    plan = planner.plan(
        0.0,
        np.array([[0.0, 10000.0], [0.0, 0.0]]),
        np.array([7.0, 7.0]),
        np.array([0.0, 0.0, 0.0, 7.0, 0.0, 0.0]),
        [_head_on_snapshot(0.0)],
        dt=0.5,
    )

    assert isinstance(planner, CustomMPCAdapter)
    assert plan.shape == (9, 1)
    assert plan[2, 0] == pytest.approx(-0.17453292519943295, abs=1e-6)  # -10 deg fan candidate
    assert plan[3, 0] == pytest.approx(7.0, abs=1e-9)
    solution = planner._solution
    assert solution.predicted_trajectory.shape == (9, 21)  # 20 prediction steps + 1
    assert solution.control_trajectory is None  # hold path samples the prediction grid
    assert solution.iterations == 45  # exhaustive fan size
    assert set(solution.constraints) == {"dynamic_collision", "heading_increment", "planning_zone"}
    _assert_no_route_lifecycle_fields(solution.algorithm_details)


def test_potocnik_simplified_hold_samples_prediction_grid_until_next_period(
    registry: IntegrationRegistry,
) -> None:
    planner = _potocnik_simplified(registry)
    waypoints = np.array([[0.0, 10000.0], [0.0, 0.0]])
    planner.plan(
        0.0, waypoints, np.array([7.0, 7.0]), np.array([0.0, 0.0, 0.0, 7.0, 0.0, 0.0]),
        [_head_on_snapshot(0.0)], dt=0.5,
    )

    hold = planner.plan(
        2.0, waypoints, np.array([7.0, 7.0]), np.array([14.0, 0.0, 0.0, 7.0, 0.0, 0.0]),
        [_head_on_snapshot(2.0, north_m=1986.0)], dt=0.5,
    )

    details = planner.get_diagnostics().details
    assert hold.shape == (9, 1)
    assert details["solver_executed"] is False
    assert details["trajectory_source"] == "held_plan"
    assert details["held_elapsed_s"] == pytest.approx(2.0)
    assert hold[3, 0] == pytest.approx(7.0, abs=1e-9)  # constant fan speed

    solve_again = planner.plan(
        5.0, waypoints, np.array([7.0, 7.0]), np.array([35.0, 0.0, 0.0, 7.0, 0.0, 0.0]),
        [_head_on_snapshot(5.0, north_m=1965.0)], dt=0.5,
    )
    assert planner.get_diagnostics().details["solver_executed"] is True
    assert solve_again.shape == (9, 1)


def test_potocnik_simplified_infeasible_fan_rejects_and_resets_cached_plan(
    registry: IntegrationRegistry,
) -> None:
    planner = _potocnik_simplified(registry)
    with pytest.raises(ColavExecutionError) as error:
        planner.plan(
            0.0,
            np.array([[0.0, 10000.0], [0.0, 0.0]]),
            np.array([7.0, 7.0]),
            np.array([0.0, 0.0, 0.0, 7.0, 0.0, 0.0]),
            [_head_on_snapshot(0.0, north_m=40.0)],  # no collision-free fan candidate
            dt=0.5,
        )

    assert error.value.status is PlanStatus.INFEASIBLE
    diagnostics = planner.get_diagnostics()
    assert diagnostics.status is PlanStatus.INFEASIBLE
    assert diagnostics.details["solver_executed"] is False
    assert np.array_equal(planner.get_current_plan(), np.zeros((9, 1)))


# ---------------------------------------------------------------------------
# potocnik_colreg_fan_mpc — adapter planner with explicit control trajectory
# ---------------------------------------------------------------------------


def test_potocnik_colreg_emits_command_with_control_trajectory_hold(
    registry: IntegrationRegistry,
) -> None:
    planner = _adapter(registry, "potocnik_colreg_fan_mpc")
    waypoints = np.array([[0.0, 10000.0], [0.0, 0.0]])
    plan = planner.plan(
        0.0, waypoints, np.array([7.0, 7.0]), np.array([0.0, 0.0, 0.0, 7.0, 0.0, 0.0]),
        [_head_on_snapshot(0.0)], dt=0.5,
    )

    assert isinstance(planner, CustomMPCAdapter)
    assert plan.shape == (9, 1)
    assert plan[2, 0] == pytest.approx(np.deg2rad(5.0), abs=1e-3)  # early substantial starboard action
    solution = planner._solution
    assert solution.predicted_trajectory.shape == (9, 21)
    assert solution.control_trajectory.shape == (9, 21)
    assert solution.algorithm_details["control_trajectory_semantics"] == "held_course_speed_reference"
    assert solution.algorithm_details["active_encounters"] == ["head_on"]
    _assert_no_route_lifecycle_fields(solution.algorithm_details)

    planner.plan(
        2.0, waypoints, np.array([7.0, 7.0]), np.array([14.0, 0.0, 0.0, 7.0, 0.0, 0.0]),
        [_head_on_snapshot(2.0, north_m=1986.0)], dt=0.5,
    )
    details = planner.get_diagnostics().details
    assert details["solver_executed"] is False
    assert details["trajectory_source"] == "held_plan"
    assert details["held_elapsed_s"] == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# mid_mpc_ipopt — the only planner with an accepted-plan lifecycle
# ---------------------------------------------------------------------------


def _mid_mpc_adapter(registry: IntegrationRegistry) -> CustomMPCAdapter:
    adapter = _adapter(registry, "mid_mpc_ipopt")
    assert isinstance(adapter, CustomMPCAdapter)
    return adapter


def test_mid_mpc_command_column_is_distinct_from_prediction_grid(registry: IntegrationRegistry) -> None:
    planner = _mid_mpc_adapter(registry)
    assert planner.descriptor.state_samples == 5  # reduced audit horizon: 4 steps + 1
    assert planner.descriptor.horizon_dt == pytest.approx(5.0)

    plan = _mid_mpc_plan(planner, 0.0)

    assert plan.shape == (9, 1)  # single executed command column
    solution = planner._solution
    assert solution.predicted_trajectory.shape == (9, 5)  # NLP prediction grid
    assert solution.control_trajectory.shape == (9, 4)  # held course/speed knots
    assert planner.get_current_plan().shape == (9, 5)
    # The adapter's current-plan accessor returns the *prediction grid*, not
    # the executed command column: prediction and executable reference are
    # distinct artifacts at this seam.
    assert planner.get_current_plan().shape != plan.shape


def test_mid_mpc_rolling_plan_lifecycle_receipt_and_hash_chain(registry: IntegrationRegistry) -> None:
    planner = _mid_mpc_adapter(registry)
    _mid_mpc_plan(planner, 0.0)

    details = planner.get_diagnostics().details
    receipt = details["accepted_plan_receipt"]
    assert receipt["accepted_at_s"] == pytest.approx(0.0)
    assert receipt["valid_until_s"] == pytest.approx(5.0)  # decision period expiry
    assert receipt["target_keys"] == [{"target_id": 1, "generation": 1}]
    _assert_sha256(receipt["receipt_hash"])
    assembly = details["assembly"]
    for stage in ("request_hash", "problem_hash", "prepared_hash", "solver_hash", "acceptance_hash", "receipt_hash"):
        _assert_sha256(assembly[stage])
    rolling = details["rolling_plan"]
    assert rolling["assessment"]["revision_reason"] == "INITIAL_PLAN"
    assert rolling["reference"]["active"] is False

    _mid_mpc_plan(planner, 5.0, ownship=np.array([20.0, 0.0, 0.0, 4.0, 0.0, 0.0]), target_north_m=1965.0)

    rolling_t5 = planner.get_diagnostics().details["rolling_plan"]
    # Same route and target keys, but the canonical COLREG authority hash
    # changed, so continuity is refused for the next solve: the rolling
    # reference stays inactive even though the candidate is accepted.
    assert rolling_t5["assessment"]["revision_reason"] == "COLREG_AUTHORITY_CHANGED"
    assert rolling_t5["assessment"]["accepted"] is True
    assert rolling_t5["reference"]["active"] is False
    assert rolling_t5["reference"]["accepted_at_s"] == pytest.approx(0.0)


def test_mid_mpc_hold_between_solves_samples_held_control_trajectory(registry: IntegrationRegistry) -> None:
    planner = _mid_mpc_adapter(registry)
    _mid_mpc_plan(planner, 0.0)

    hold = _mid_mpc_plan(planner, 2.0, ownship=np.array([8.0, 0.0, 0.0, 4.0, 0.0, 0.0]), target_north_m=1986.0)

    details = planner.get_diagnostics().details
    assert hold.shape == (9, 1)
    assert details["solver_executed"] is False
    assert details["trajectory_source"] == "held_plan"
    assert details["held_elapsed_s"] == pytest.approx(2.0)
    assert details["solve_id"] == 1  # no new solve, no new receipt


def test_mid_mpc_preserves_accepted_plan_when_candidate_is_rejected(registry: IntegrationRegistry) -> None:
    planner = _mid_mpc_adapter(registry)
    _mid_mpc_plan(planner, 0.0)
    _mid_mpc_plan(planner, 5.0, ownship=np.array([20.0, 0.0, 0.0, 4.0, 0.0, 0.0]), target_north_m=1965.0)

    # Change the mission route mid-encounter; at the reduced audit horizon the
    # optimizer returns an unresolved candidate and the adapter preserves the
    # accepted plan instead of committing the rejected revision.
    continuation = _mid_mpc_plan(
        planner,
        10.0,
        ownship=np.array([40.0, 0.0, 0.0, 4.0, 0.0, 0.0]),
        waypoints=np.array([[0.0, 500.0], [30.0, 500.0]]),
        target_north_m=1930.0,
    )

    details = planner.get_diagnostics().details
    assert planner.get_diagnostics().status is PlanStatus.SUCCESS
    assert details["solver_executed"] is True
    assert details["candidate_rejected"] is True
    assert details["candidate_committed"] is False
    assert details["revision_reason"] == "OPTIMIZER_UNRESOLVED"
    assert details["hold_acceptance"]["mode"] == "ROLLING_PLAN_CONTINUATION"
    assert details["trajectory_source"] == "held_plan"
    assert continuation.shape == (9, 1)


# ---------------------------------------------------------------------------
# External planners: dependency gates, ENC boundaries, direct-reference only
# ---------------------------------------------------------------------------


def test_psbmpc_requires_enc_and_starts_without_a_plan(registry: IntegrationRegistry) -> None:
    if not registry.statuses()["psbmpc"].available:
        pytest.skip("psbmpc dependency unavailable on this machine")
    planner = registry.build_algorithm("psbmpc")
    assert isinstance(planner, PSBMPCColav)

    with pytest.raises(ColavExecutionError) as error:
        planner.plan(
            0.0,
            np.array([[0.0, 500.0], [0.0, 0.0]]),
            np.array([4.0, 4.0]),
            np.array([0.0, 0.0, 0.0, 4.0, 0.0, 0.0]),
            [],
            enc=None,
        )
    assert error.value.status is PlanStatus.INVALID_INPUT
    assert "requires an ENC" in str(error.value)
    assert np.array_equal(planner.get_current_plan(), np.zeros((9, 1)))
    assert set(planner.get_colav_data()) == {"predicted_trajectory", "diagnostics"}


def test_rrt_requires_enc_and_starts_without_a_plan(registry: IntegrationRegistry) -> None:
    if not registry.statuses()["rrt"].available:
        pytest.skip("rrt dependency unavailable on this machine")
    planner = registry.build_algorithm("rrt")
    assert isinstance(planner, RRTStarColav)

    with pytest.raises(ColavExecutionError) as error:
        planner.plan(
            0.0,
            np.array([[0.0, 500.0], [0.0, 0.0]]),
            np.array([4.0, 4.0]),
            np.array([0.0, 0.0, 0.0, 4.0, 0.0, 0.0]),
            [],
            enc=None,
        )
    assert error.value.status is PlanStatus.INVALID_INPUT
    assert "requires an ENC" in str(error.value)
    assert np.array_equal(planner.get_current_plan(), np.zeros((9, 1)))


def test_sbmpc_reference_solves_without_enc_and_holds_offsets_between_periods(
    registry: IntegrationRegistry,
) -> None:
    if not registry.statuses()["sbmpc_reference"].available:
        pytest.skip("sbmpc_reference dependency unavailable on this machine")
    planner = registry.build_algorithm("sbmpc_reference")

    plan = planner.plan(
        0.0,
        np.array([[0.0, 500.0], [0.0, 0.0]]),
        np.array([4.0, 4.0]),
        np.array([0.0, 0.0, 0.0, 4.0, 0.0, 0.0]),
        [],
        enc=None,  # unlike pspbmpc/rrt, the official SB-MPC tolerates ENC-less runs
        dt=1.0,
        os_length=15.0,
        os_width=4.0,
        os_draft=0.5,
    )

    assert plan.shape == (9, 1)
    assert plan[2, 0] == pytest.approx(0.0, abs=1e-9)
    assert plan[3, 0] == pytest.approx(4.0, abs=1e-9)
    assert planner.get_current_plan().shape == (9, 1)
    trace = planner.get_colav_data()["planner"]
    assert trace["solver_executed"] is True
    assert trace["solve_id"] == 1
    assert np.asarray(trace["predicted_trajectory"]).shape[1] > 1  # native prediction grid exists
    assert set(trace["selected_command"]) == {
        "course_rad",
        "speed_mps",
        "course_offset_rad",
        "speed_scale",
    }

    hold = planner.plan(
        2.0,
        np.array([[0.0, 500.0], [0.0, 0.0]]),
        np.array([4.0, 4.0]),
        np.array([8.0, 0.0, 0.0, 4.0, 0.0, 0.0]),
        [],
        enc=None,
        dt=1.0,
        os_length=15.0,
        os_width=4.0,
        os_draft=0.5,
    )

    trace_t2 = planner.get_colav_data()["planner"]
    assert trace_t2["solver_executed"] is False
    assert trace_t2["solve_id"] == 1  # offset zero-order hold, no re-solve
    assert trace_t2["selected_command"] == trace["selected_command"]
    assert hold[2, 0] == pytest.approx(trace["selected_command"]["course_rad"], abs=1e-12)


def test_rlmpc_is_registered_but_builds_only_when_its_dependency_exists(registry: IntegrationRegistry) -> None:
    status = registry.statuses()["rlmpc"]
    if status.available:
        assert registry.build_algorithm("rlmpc") is not None
        return
    assert "No module named" in str(status.reason)
    with pytest.raises(ColavExecutionError) as error:
        registry.build_algorithm("rlmpc")
    assert error.value.status is PlanStatus.DEPENDENCY_UNAVAILABLE


# ---------------------------------------------------------------------------
# Cross-planner boundary: only Mid-MPC carries route-lifecycle fields
# ---------------------------------------------------------------------------


def test_only_mid_mpc_output_details_carry_route_lifecycle_fields(registry: IntegrationRegistry) -> None:
    vo = registry.build_algorithm("vo")
    vo.plan(
        0.0,
        np.array([[0.0, 10000.0], [0.0, 0.0]]),
        np.array([7.0, 7.0]),
        np.array([0.0, 0.0, 0.0, 7.0, 0.0, 0.0]),
        [_legacy_head_on(800.0)],
    )
    _assert_no_route_lifecycle_fields(vo.get_diagnostics().details)

    sbmpc = registry.build_algorithm("sbmpc")
    sbmpc.plan(
        0.0,
        np.array([[0.0, 10000.0], [0.0, 0.0]]),
        np.array([7.0, 7.0]),
        np.array([0.0, 0.0, 0.0, 7.0, 0.0, 0.0]),
        [],
    )
    _assert_no_route_lifecycle_fields(sbmpc.get_diagnostics().details)

    simplified = _potocnik_simplified(registry)
    simplified.plan(
        0.0,
        np.array([[0.0, 10000.0], [0.0, 0.0]]),
        np.array([7.0, 7.0]),
        np.array([0.0, 0.0, 0.0, 7.0, 0.0, 0.0]),
        [_head_on_snapshot(0.0)],
        dt=0.5,
    )
    _assert_no_route_lifecycle_fields(simplified.get_diagnostics().details)

    colreg = _adapter(registry, "potocnik_colreg_fan_mpc")
    colreg.plan(
        0.0,
        np.array([[0.0, 10000.0], [0.0, 0.0]]),
        np.array([7.0, 7.0]),
        np.array([0.0, 0.0, 0.0, 7.0, 0.0, 0.0]),
        [_head_on_snapshot(0.0)],
        dt=0.5,
    )
    _assert_no_route_lifecycle_fields(colreg.get_diagnostics().details)

    mid_mpc = _mid_mpc_adapter(registry)
    _mid_mpc_plan(mid_mpc, 0.0)
    details = mid_mpc.get_diagnostics().details
    assert "rolling_plan" in details  # the sole accepted-plan lifecycle carrier
    assert "accepted_plan_receipt" in details
