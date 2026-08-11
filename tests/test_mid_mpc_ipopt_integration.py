from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

import numpy as np

from colav_simulator.core.colav.custom_mpc_adapter import CustomMPCAdapter, DeadlineMode, FactoryContext
from colav_simulator.core.colav.diagnostics import ColavExecutionError, FailureSource, PlanStatus
from colav_simulator.core.tracking.trackers import TrackKey, TrackSnapshot, TrackStatus
from colav_simulator.experiment.capabilities import ALGORITHMS, VERIFIED_COMBINATIONS
from colav_simulator.experiment.persistence import EvidenceWriter
from colav_simulator.integrations.registry import IntegrationRegistry

ALGORITHM_ID = "mid_mpc_ipopt"


def _fast_adapter() -> CustomMPCAdapter:
    return IntegrationRegistry().build_algorithm(
        ALGORITHM_ID,
        {
            "factory": "colav_simulator.integrations.mid_mpc_ipopt:create",
            "kwargs": {
                "horizon_steps": 4,
                "horizon_dt_s": 5.0,
                "solve_period_s": 5.0,
                "deadline_s": 20.0,
            },
        },
        factory_context=FactoryContext(ALGORITHM_ID, 0, deadline_mode=DeadlineMode.OFF),
    )


def _plan(
    adapter: CustomMPCAdapter,
    t: float,
    targets: list[tuple] | None = None,
    ownship: np.ndarray | None = None,
) -> np.ndarray:
    snapshots = [
        TrackSnapshot(
            key=TrackKey(target_id, 1),
            state=state,
            covariance=covariance,
            length_m=length,
            width_m=width,
            observed_at_s=t,
            generated_at_s=t,
            status=TrackStatus.UPDATED,
            source="test",
        )
        for target_id, state, covariance, length, width in (targets or [])
    ]
    return adapter.plan(
        t,
        np.array([[0.0, 500.0], [0.0, 0.0]]),
        np.array([4.0, 4.0]),
        ownship if ownship is not None else np.array([0.0, 0.0, 0.0, 4.0, 0.0, 0.0]),
        snapshots,
        dt=1.0,
        os_length=15.0,
    )


def test_registry_exposes_published_mid_mpc_profile_and_truthful_descriptor() -> None:
    registry = IntegrationRegistry()

    assert registry.statuses()[ALGORITHM_ID].available is True
    adapter = registry.build_algorithm(
        ALGORITHM_ID,
        factory_context=FactoryContext(ALGORITHM_ID, 7, deadline_mode=DeadlineMode.OFF),
    )

    assert isinstance(adapter, CustomMPCAdapter)
    descriptor = adapter.descriptor_document()
    assert descriptor["descriptor"]["algorithm_id"] == ALGORITHM_ID
    assert descriptor["descriptor"]["solver"] == "casadi-3.7.2-ipopt"
    assert descriptor["descriptor"]["horizon_steps"] == 80
    assert descriptor["descriptor"]["state_samples"] == 81
    assert descriptor["fallback_policy"] == "forbidden"
    assert descriptor["build_identity"]["config_sha256"] != "UNKNOWN"
    assert ALGORITHMS[ALGORITHM_ID].readiness_grade == "G3"
    assert {key[:2] for key in VERIFIED_COMBINATIONS if key[2:] == (ALGORITHM_ID, "god")} == {
        ("multiship", "paper_ccta2023_multiship"),
        ("rule13", "overtaken"),
        ("rule13", "overtaking"),
        ("rule14", "head_on"),
        ("rule15", "crossing_give_way"),
        ("rule15", "crossing_stand_on"),
    }


def test_no_target_route_executes_ipopt_and_returns_native_plan() -> None:
    adapter = IntegrationRegistry().build_algorithm(
        ALGORITHM_ID,
        factory_context=FactoryContext(ALGORITHM_ID, 0, deadline_mode=DeadlineMode.OFF),
    )

    command = adapter.plan(
        0.0,
        np.array([[0.0, 500.0], [0.0, 0.0]]),
        np.array([4.0, 4.0]),
        np.array([0.0, 0.0, 0.0, 4.0, 0.0, 0.0]),
        [],
        dt=1.0,
        os_length=15.0,
    )

    plan = adapter.get_current_plan()
    diagnostics = adapter.get_diagnostics()
    trace = adapter.get_colav_data()["planner"]
    assert command.shape == (9, 1)
    assert plan.shape == (9, 81)
    np.testing.assert_allclose(plan[:6, 0], [0.0, 0.0, 0.0, 4.0, 0.0, 0.0], atol=1e-9)
    assert np.linalg.norm(plan[:2, 1] - plan[:2, 0]) > 50.0
    assert np.linalg.norm(plan[:2, -1] - plan[:2, 0]) > 4_000.0
    assert diagnostics.fallback_used is False
    assert diagnostics.details["solver_executed"] is True
    assert diagnostics.details["solver_backend"] == "ipopt"
    assert diagnostics.details["ipopt_return_status"] == "Solve_Succeeded"
    assert trace["solver_executed"] is True
    assert trace["solve_id"] == 1
    assert trace["algorithm_details"]["formulation"] == "mass-l3-mid-mpc-ipopt-frozen"
    assert trace["algorithm_details"]["control_intervals"] == 80
    assert trace["algorithm_details"]["state_samples"] == 81
    assert trace["algorithm_details"]["horizon_duration_s"] == 1200.0
    assembly = trace["algorithm_details"]["assembly"]
    assert assembly["schema_version"] == "1.0"
    assert assembly["profile"] == "COLAV_STRICT"
    assert len(assembly["request_hash"]) == 64
    assert len(assembly["problem_hash"]) == 64
    assert trace["constraints"]["slack_bounds_mode"] == "fixed_zero"
    assert trace["constraints"]["slack_bounds"] == {
        "cpa": [0.0, 0.0],
        "direction": [0.0, 0.0],
    }
    assert np.asarray(trace["predicted_trajectory"]).shape == (9, 81)


def test_adapter_publishes_hash_linked_replay_artifact_without_inlining_vectors(tmp_path: Path) -> None:
    writer = EvidenceWriter(tmp_path / "run")
    adapter = IntegrationRegistry().build_algorithm(
        ALGORITHM_ID,
        {
            "factory": "colav_simulator.integrations.mid_mpc_ipopt:create",
            "kwargs": {"horizon_steps": 4, "horizon_dt_s": 5.0},
        },
        factory_context=FactoryContext(
            ALGORITHM_ID,
            0,
            deadline_mode=DeadlineMode.OFF,
            artifact_sink=writer.write_mid_mpc_artifact,
        ),
    )

    _plan(adapter, 0.0)

    trace = adapter.get_colav_data()["planner"]
    assembly = trace["algorithm_details"]["assembly"]
    reference = assembly["artifact"]
    artifact_path = writer.run_dir / reference["relative_path"]
    payload = gzip.decompress(artifact_path.read_bytes())
    assert hashlib.sha256(payload).hexdigest() == reference["sha256"]
    document = json.loads(payload)
    assert document["assembly"]["problem_hash"] == assembly["problem_hash"]
    assert document["solver"]["prepared"]["x0"]
    assert document["solver"]["raw"]["x"]
    assert len(json.dumps(trace["algorithm_details"]["assembly"])) < 8_192


def test_dynamic_tracks_use_shared_geometry_and_direct_optimizer_intents() -> None:
    adapter = _fast_adapter()
    covariance = np.eye(4)

    _plan(
        adapter,
        0.0,
        [
            (11, np.array([3000.0, 0.0, -4.0, 0.0]), covariance, 15.0, 4.0),
            (12, np.array([1000.0, -1000.0, 0.0, 4.0]), covariance, 15.0, 4.0),
            (13, np.array([1000.0, 1000.0, 0.0, -4.0]), covariance, 15.0, 4.0),
            (14, np.array([-100.0, -100.0, 2.0, 4.0]), covariance, 15.0, 4.0),
        ],
    )

    trace = adapter.get_colav_data()["planner"]
    targets = {item["target_id"]: item for item in trace["target_predictions"]}
    assert targets[11]["encounter"] == "head_on"
    assert targets[11]["optimizer_intent"] == "HOLD"
    assert targets[12]["encounter"] == "crossing_stand_on"
    assert targets[12]["optimizer_intent"] == "HOLD"
    assert targets[13]["encounter"] == "crossing_give_way"
    assert targets[13]["optimizer_intent"] == "HOLD"
    assert targets[14]["encounter"] == "overtaken"
    assert targets[14]["optimizer_intent"] == "GIVE_WAY"
    assert all(item["prediction_model"] == "constant_velocity" for item in targets.values())
    details = trace["algorithm_details"]
    assert details["decision_intent"] == "GIVE_WAY"
    assert details["preferred_side"] == "starboard"
    assert details["starboard_asymmetry_active"] is False
    assert details["selected_target_ids"] == [14]
    lifecycle_targets = {item["target_id"]: item for item in details["lifecycle"]["targets"]}
    assert lifecycle_targets[11]["role"] == "GIVE_WAY"
    assert lifecycle_targets[11]["risk"] == "CANDIDATE"
    assert trace["constraints"]["row_schedule"]["terminal_rows_enabled"] is False
    trajectory = np.asarray(trace["predicted_trajectory"])
    np.testing.assert_allclose(trajectory[8], trajectory[5], atol=1e-12)


def test_legacy_track_without_tracker_generation_fails_before_solver() -> None:
    adapter = _fast_adapter()
    legacy_target = (7, np.array([500.0, 0.0, -4.0, 0.0]), np.eye(4), 15.0, 4.0)

    with np.testing.assert_raises(ColavExecutionError) as error:
        adapter.plan(
            0.0,
            np.array([[0.0, 500.0], [0.0, 0.0]]),
            np.array([4.0, 4.0]),
            np.array([0.0, 0.0, 0.0, 4.0, 0.0, 0.0]),
            [legacy_target],
            dt=1.0,
            os_length=15.0,
        )

    assert error.exception.details["failure_code"] == "UNUSABLE_OBSERVATION"
    trace = adapter.get_colav_data()["planner"]
    assert trace["solver_executed"] is False
    assert trace["algorithm_details"]["cached_plan_used"] is False


def test_terminated_track_is_not_reinterpreted_as_fresh() -> None:
    adapter = _fast_adapter()
    terminated = TrackSnapshot(
        key=TrackKey(7, 2),
        state=np.array([500.0, 0.0, -4.0, 0.0]),
        covariance=np.eye(4),
        length_m=15.0,
        width_m=4.0,
        observed_at_s=0.0,
        generated_at_s=0.0,
        status=TrackStatus.TERMINATED,
        source="test",
    )

    with np.testing.assert_raises(ColavExecutionError) as error:
        adapter.plan(
            0.0,
            np.array([[0.0, 500.0], [0.0, 0.0]]),
            np.array([4.0, 4.0]),
            np.array([0.0, 0.0, 0.0, 4.0, 0.0, 0.0]),
            [terminated],
            dt=1.0,
            os_length=15.0,
        )

    assert error.exception.details["failure_code"] == "UNUSABLE_OBSERVATION"
    assert adapter.get_colav_data()["planner"]["solver_executed"] is False


def test_lifecycle_transition_sink_is_incremental_and_reflected_in_trace() -> None:
    persisted = []
    adapter = IntegrationRegistry().build_algorithm(
        ALGORITHM_ID,
        {
            "factory": "colav_simulator.integrations.mid_mpc_ipopt:create",
            "kwargs": {
                "horizon_steps": 4,
                "horizon_dt_s": 5.0,
                "solve_period_s": 5.0,
            },
        },
        factory_context=FactoryContext(
            ALGORITHM_ID,
            0,
            deadline_mode=DeadlineMode.OFF,
            event_sink=persisted.append,
        ),
    )

    _plan(
        adapter,
        0.0,
        [(61, np.array([3000.0, 0.0, -4.0, 0.0]), np.eye(4), 15.0, 4.0)],
    )

    assert persisted
    lifecycle = adapter.get_colav_data()["planner"]["algorithm_details"]["lifecycle"]
    assert lifecycle["evidence_persisted"] is True

    adapter.reset()

    reset_event = persisted[-1]
    assert reset_event.event_type == "RESET"
    assert reset_event.target_key is None
    assert reset_event.from_state == "mid-mpc-1"
    assert reset_event.to_state == "mid-mpc-2"
    assert reset_event.reason == "adapter_reset"


def test_sway_velocity_and_overtaking_side_reach_the_optimizer() -> None:
    covariance = np.eye(4)
    sway_adapter = _fast_adapter()
    _plan(
        sway_adapter,
        0.0,
        [(21, np.array([500.0, 0.0, -4.0, 2.0]), covariance, 15.0, 4.0)],
        ownship=np.array([0.0, 0.0, 0.0, 4.0, 2.0, 0.0]),
    )
    sway_target = sway_adapter.get_colav_data()["planner"]["target_predictions"][0]
    assert sway_target["encounter"] == "crossing_stand_on"
    assert sway_target["optimizer_intent"] == "HOLD"

    overtaking_adapter = _fast_adapter()
    _plan(
        overtaking_adapter,
        0.0,
        [(22, np.array([100.0, 20.0, 2.0, 0.0]), covariance, 15.0, 4.0)],
    )
    overtaking = overtaking_adapter.get_colav_data()["planner"]
    assert overtaking["target_predictions"][0]["encounter"] == "overtaking"
    assert overtaking["target_predictions"][0]["preferred_side"] == "port"


def test_conflicting_overtaking_sides_fail_stop_after_commitment_confirmation() -> None:
    adapter = _fast_adapter()
    covariance = np.eye(4)

    _plan(
        adapter,
        0.0,
        [
            (31, np.array([100.0, 20.0, 2.0, 0.0]), covariance, 15.0, 4.0),
            (32, np.array([100.0, -20.0, 2.0, 0.0]), covariance, 15.0, 4.0),
            (33, np.array([300.0, 0.0, -4.0, 0.0]), covariance, 15.0, 4.0),
        ],
    )

    trace = adapter.get_colav_data()["planner"]
    targets = {item["target_id"]: item for item in trace["target_predictions"]}
    assert targets[31]["encounter"] == "overtaking"
    assert targets[31]["preferred_side"] == "port"
    assert targets[32]["encounter"] == "overtaking"
    assert targets[32]["preferred_side"] == "starboard"
    assert targets[33]["encounter"] == "head_on"
    assert trace["algorithm_details"]["preferred_side"] == "none"
    with np.testing.assert_raises(ColavExecutionError) as error:
        _plan(
            adapter,
            5.0,
            [
                (31, np.array([100.0, 20.0, 2.0, 0.0]), covariance, 15.0, 4.0),
                (32, np.array([100.0, -20.0, 2.0, 0.0]), covariance, 15.0, 4.0),
                (33, np.array([300.0, 0.0, -4.0, 0.0]), covariance, 15.0, 4.0),
            ],
        )
    assert "MANEUVER_CONFLICT" in str(error.exception)
    assert error.exception.source is FailureSource.ALGORITHM
    failure = adapter.get_colav_data()["planner"]
    assert failure["solver_executed"] is False
    assert failure["status"] == PlanStatus.INVALID_INPUT.value
    assert failure["algorithm_details"]["failure_code"] == "MANEUVER_CONFLICT"
    assert adapter.get_diagnostics().details["cached_plan_used"] is False


def test_seventeenth_required_target_fails_before_solver_without_truncation() -> None:
    adapter = _fast_adapter()
    targets = [
        (target_id, np.array([1000.0 + target_id, 0.0, -4.0, 0.0]), np.eye(4), 15.0, 4.0) for target_id in range(1, 18)
    ]
    _plan(adapter, 0.0, targets)

    with np.testing.assert_raises(ColavExecutionError) as error:
        _plan(adapter, 5.0, targets)

    assert "CAPACITY_EXCEEDED" in str(error.exception)
    trace = adapter.get_colav_data()["planner"]
    assert trace["solver_executed"] is False
    assert trace["solve_id"] == 1
    assert trace["algorithm_details"]["failure_code"] == "CAPACITY_EXCEEDED"
    assert adapter.get_diagnostics().details["cached_plan_used"] is False


def test_adapter_owns_hold_schedule_and_reset_state() -> None:
    adapter = _fast_adapter()

    first = _plan(adapter, 0.0)
    held = _plan(adapter, 2.0)

    trace = adapter.get_colav_data()["planner"]
    assert trace["solve_id"] == 1
    assert trace["solver_executed"] is False
    assert trace["algorithm_details"]["trajectory_source"] == "held_plan"
    assert trace["algorithm_details"]["held_elapsed_s"] == 2.0
    assert adapter.get_diagnostics().details["solver_executed"] is False
    assert np.isfinite(first).all() and np.isfinite(held).all()

    _plan(adapter, 5.0)
    assert adapter.get_diagnostics().details["los_guidance_dt_s"] == 5.0

    adapter.reset()
    reset_trace = adapter.get_colav_data()["planner"]
    assert reset_trace["solve_id"] == 0
    assert reset_trace["solver_executed"] is False
    repeated = _plan(adapter, 0.0)
    assert adapter.get_colav_data()["planner"]["solve_id"] == 1
    np.testing.assert_allclose(repeated, first, atol=1e-7)


def test_reset_clears_encounter_commitment() -> None:
    adapter = _fast_adapter()
    target = [(41, np.array([1000.0, 0.0, -4.0, 0.0]), np.eye(4), 15.0, 4.0)]

    _plan(adapter, 0.0, target)
    assert adapter.get_diagnostics().details["minimum_alteration_active"] is False
    _plan(adapter, 5.0, target)
    assert adapter.get_diagnostics().details["minimum_alteration_active"] is True
    _plan(adapter, 10.0, target)
    assert adapter.get_diagnostics().details["minimum_alteration_active"] is True

    adapter.reset()
    _plan(adapter, 0.0, target)
    assert adapter.get_diagnostics().details["minimum_alteration_active"] is False


def test_schedule_error_fails_stop_and_ipopt_evidence_is_json_safe() -> None:
    adapter = _fast_adapter()
    _plan(adapter, 0.0)

    diagnostics = adapter.get_diagnostics()
    trace = adapter.get_colav_data()["planner"]
    assert diagnostics.status is PlanStatus.SUCCESS
    assert diagnostics.fallback_used is False
    assert diagnostics.details["normalized_solver_status"] == "Converged"
    assert diagnostics.details["objective_components"].keys() == {
        "colreg",
        "heading",
        "speed",
        "route",
        "asymmetry",
        "terminal",
        "cpa_slack",
        "direction_slack",
    }
    assert trace["constraints"]["max_constraint_violation"] <= 1e-3
    json.dumps(adapter.get_colav_data(), allow_nan=False)

    with np.testing.assert_raises(ColavExecutionError) as error:
        _plan(adapter, -1.0)
    assert error.exception.status is PlanStatus.INVALID_INPUT
    assert error.exception.source is FailureSource.SCENARIO


def test_infeasible_ipopt_problem_has_no_fallback_plan() -> None:
    adapter = IntegrationRegistry().build_algorithm(
        ALGORITHM_ID,
        {
            "factory": "colav_simulator.integrations.mid_mpc_ipopt:create",
            "kwargs": {
                "horizon_steps": 4,
                "horizon_dt_s": 5.0,
                "solve_period_s": 5.0,
                "deadline_s": 20.0,
                "speed_min_mps": 0.25,
                "speed_max_mps": 1.0,
                "decel_max_mps2": 0.05,
            },
        },
        factory_context=FactoryContext(ALGORITHM_ID, 0, deadline_mode=DeadlineMode.OFF),
    )

    with np.testing.assert_raises(ColavExecutionError) as error:
        _plan(adapter, 0.0)

    assert error.exception.status is PlanStatus.INFEASIBLE
    assert error.exception.source is FailureSource.ALGORITHM
    assert adapter.get_diagnostics().fallback_used is False
    assert adapter.get_colav_data()["planner"]["solve_id"] == 0


def test_real_ipopt_deadline_maps_to_timeout_feasible_without_fallback() -> None:
    adapter = IntegrationRegistry().build_algorithm(
        ALGORITHM_ID,
        {
            "factory": "colav_simulator.integrations.mid_mpc_ipopt:create",
            "kwargs": {
                "horizon_steps": 4,
                "horizon_dt_s": 5.0,
                "solve_period_s": 5.0,
                "deadline_s": 1e-9,
            },
        },
        factory_context=FactoryContext(ALGORITHM_ID, 0, deadline_mode=DeadlineMode.ENFORCE),
    )

    _plan(adapter, 0.0)

    diagnostics = adapter.get_diagnostics()
    trace = adapter.get_colav_data()["planner"]
    assert diagnostics.status is PlanStatus.TIMEOUT_FEASIBLE
    assert diagnostics.fallback_used is False
    assert trace["status"] == PlanStatus.TIMEOUT_FEASIBLE.value
    assert trace["solver_executed"] is True
