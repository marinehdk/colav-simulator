from __future__ import annotations

import gzip
import hashlib
import json
import math
import time
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from colav_simulator.core.colav.custom_mpc_adapter import CustomMPCAdapter, DeadlineMode, FactoryContext
from colav_simulator.core.colav.diagnostics import ColavExecutionError, FailureSource, PlanStatus
from colav_simulator.core.tracking.trackers import TrackKey, TrackSnapshot, TrackStatus
from colav_simulator.experiment.capabilities import ALGORITHMS, VERIFIED_COMBINATIONS
from colav_simulator.experiment.persistence import BoundedArtifactSink, EvidenceWriter
from colav_simulator.integrations import mid_mpc_ipopt as mid_mpc_module
from colav_simulator.integrations.mid_mpc_ipopt import _execution_control_knots, _held_target_prediction_error
from colav_simulator.integrations.registry import IntegrationRegistry

ALGORITHM_ID = "mid_mpc_ipopt"


def test_execution_control_knots_hold_each_interval_command() -> None:
    controls = np.array(
        [
            [1.0, 2.0, 3.0],
            [10.0, 20.0, 30.0],
        ]
    )

    knots = _execution_control_knots(controls)

    assert np.array_equal(knots, np.array([[1.0, 1.0, 2.0], [10.0, 10.0, 20.0]]))
    assert not np.shares_memory(knots, controls)


def test_released_target_prediction_drift_does_not_force_early_replan() -> None:
    planner_input = SimpleNamespace(
        tracks=(
            SimpleNamespace(
                target_id=1,
                generation=1,
                state_enu=np.array([20.0, 0.0, 0.0, 4.0]),
            ),
        )
    )
    solution = SimpleNamespace(
        target_predictions=(
            {
                "target_id": 1,
                "generation": 1,
                "north_m": [0.0],
                "east_m": [0.0],
                "velocity_ne_mps": [4.0, 0.0],
                "route_recovery_allowed": True,
            },
        )
    )

    assert _held_target_prediction_error(planner_input, solution, elapsed_s=5.0) == (0.0, 0.0)
    solution.target_predictions[0]["route_recovery_allowed"] = False
    position_error, velocity_error = _held_target_prediction_error(planner_input, solution, elapsed_s=5.0)
    assert position_error == 0.0
    assert velocity_error > 0.1


def _fast_adapter(*, scenario_id: str = "head_on", solve_period_s: float = 5.0) -> CustomMPCAdapter:
    return IntegrationRegistry().build_algorithm(
        ALGORITHM_ID,
        {
            "factory": "colav_simulator.integrations.mid_mpc_ipopt:create",
            "kwargs": {
                "horizon_steps": 4,
                "horizon_dt_s": 5.0,
                "solve_period_s": solve_period_s,
                "deadline_s": 20.0,
            },
        },
        factory_context=FactoryContext(
            ALGORITHM_ID,
            0,
            scenario_id=scenario_id,
            tracker_id="god",
            deadline_mode=DeadlineMode.OFF,
        ),
    )


def _canonical_hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _plan(
    adapter: CustomMPCAdapter,
    t: float,
    targets: list[tuple] | None = None,
    ownship: np.ndarray | None = None,
    model_name: str = "Viknes",
    controller_name: str = "FLSC",
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
        os_model_name=model_name,
        os_controller_name=controller_name,
        os_max_turn_rate_radps=np.deg2rad(3.0),
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
    assert descriptor["descriptor"]["horizon_dt"] == 5.0
    assert descriptor["descriptor"]["execution_profile"]["solve_period_s"] == 10.0
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
        factory_context=FactoryContext(
            ALGORITHM_ID,
            0,
            scenario_id="route",
            tracker_id="god",
            deadline_mode=DeadlineMode.OFF,
        ),
    )

    command = adapter.plan(
        0.0,
        np.array([[0.0, 500.0], [0.0, 0.0]]),
        np.array([4.0, 4.0]),
        np.array([0.0, 0.0, 0.0, 4.0, 0.0, 0.0]),
        [],
        dt=1.0,
        os_length=15.0,
        os_model_name="Viknes",
        os_controller_name="FLSC",
        os_max_turn_rate_radps=np.deg2rad(3.0),
    )

    plan = adapter.get_current_plan()
    diagnostics = adapter.get_diagnostics()
    trace = adapter.get_colav_data()["planner"]
    assert command.shape == (9, 1)
    assert plan.shape == (9, 81)
    np.testing.assert_allclose(plan[:6, 0], [0.0, 0.0, 0.0, 4.0, 0.0, 0.0], atol=1e-9)
    assert np.linalg.norm(plan[:2, 1] - plan[:2, 0]) > 15.0
    assert np.linalg.norm(plan[:2, -1] - plan[:2, 0]) > 1_000.0
    assert diagnostics.fallback_used is False
    assert diagnostics.details["solver_executed"] is True
    assert diagnostics.details["solver_backend"] == "ipopt"
    assert (
        diagnostics.details["ipopt_return_status"],
        diagnostics.details["normalized_solver_status"],
    ) in {
        ("Solve_Succeeded", "Converged"),
        ("Solved_To_Acceptable_Level", "FeasibleNonOptimal"),
        ("User_Requested_Stop", "FeasibleNonOptimal"),
    }
    assert trace["solver_executed"] is True
    assert trace["solve_id"] == 1
    assert trace["algorithm_details"]["formulation"] == "mass-l3-mid-mpc-ipopt-frozen"
    assert trace["algorithm_details"]["control_intervals"] == 80
    assert trace["algorithm_details"]["state_samples"] == 81
    assert trace["algorithm_details"]["horizon_duration_s"] == 400.0
    acceptance = trace["algorithm_details"]["plan_acceptance"]
    assert acceptance["accepted"] is True
    assert acceptance["aggregate"] == "PASS"
    assert acceptance["profile"] == "COLAV_STRICT"
    assert len(acceptance["request_hash"]) == 64
    assert len(acceptance["acceptance_hash"]) == 64
    receipt = trace["algorithm_details"]["accepted_plan_receipt"]
    assert receipt["parent_acceptance_hash"] == trace["algorithm_details"]["assembly"]["acceptance_hash"]
    assert receipt["semantic_acceptance_hash"] == acceptance["acceptance_hash"]
    assert receipt["profile"] == "COLAV_STRICT"
    assert receipt["warm_start_eligible"] is True
    assert len(receipt["receipt_hash"]) == 64
    assert [layer["layer"] for layer in acceptance["layers"]] == [
        "integrity",
        "numerical",
        "safety",
        "COLREG",
        "trackability",
        "quality",
        "evidence",
    ]
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
    timing = trace["algorithm_details"]
    assert timing["graph_cache_hit"] is True
    assert timing["graph_build_elapsed_ms"] == 0.0
    assert timing["solver_preparation_elapsed_ms"] >= 0.0
    assert timing["ipopt_elapsed_ms"] > 0.0
    assert timing["ipopt_iterations"] >= 1
    assert timing["optimizer_total_elapsed_ms"] >= timing["ipopt_elapsed_ms"]
    assert np.asarray(trace["predicted_trajectory"]).shape == (9, 81)


def test_no_target_off_route_prediction_rejoins_straight_mission_leg() -> None:
    adapter = IntegrationRegistry().build_algorithm(
        ALGORITHM_ID,
        factory_context=FactoryContext(
            ALGORITHM_ID,
            0,
            scenario_id="route_rejoin_regression",
            tracker_id="god",
            deadline_mode=DeadlineMode.OFF,
        ),
    )
    initial_cross_track_m = 137.0

    adapter.plan(
        0.0,
        np.array([[0.0, 2_000.0], [0.0, 0.0]]),
        np.array([7.0, 7.0]),
        np.array([1_140.0, initial_cross_track_m, np.deg2rad(-63.386679), 7.0, 0.0, 0.0]),
        [],
        dt=0.5,
        os_length=8.45,
        os_model_name="Viknes",
        os_controller_name="FLSC",
        os_max_turn_rate_radps=np.deg2rad(3.0),
    )

    cross_track_m = np.abs(adapter.get_current_plan()[1])
    assert cross_track_m[24] < initial_cross_track_m
    assert cross_track_m[-1] < 20.0


def test_mid_mpc_trace_exposes_typed_prediction_evidence_and_authority_timeline() -> None:
    adapter = _fast_adapter(scenario_id="route")

    _plan(adapter, 0.0)
    fresh = adapter.get_colav_data()["planner"]
    _plan(adapter, 1.0)
    held = adapter.get_colav_data()["planner"]

    assert fresh["schema_version"] == "1.1"
    assert fresh["evidence"]["schema_version"] == "colav.prediction-evidence.envelope@1"
    assert len(json.dumps(fresh["evidence"], separators=(",", ":")).encode()) <= 8_192
    inline = fresh["evidence"]["inline"]
    assert fresh["evidence"]["artifact_reference"]["status"] == "NOT_CONFIGURED"
    assert (
        fresh["evidence"]["authority"]["active_receipt_hash"]
        == fresh["algorithm_details"]["accepted_plan_receipt"]["receipt_hash"]
    )
    assert fresh["evidence"]["authority"]["receipt"] == fresh["algorithm_details"]["accepted_plan_receipt"]
    render = fresh["prediction_render"]
    assert render["grid"] == {
        "intervals": 4,
        "state_samples": 5,
        "dt_s": 5.0,
        "duration_s": 20.0,
    }
    assert render["trajectory_source"] == "IPOPT_PRIMAL"
    assert len(render["ownship"]["north_m"]) == 5
    assert "x" not in render["ownship"]
    assert fresh["evidence_timeline"]["latest_terminal_outcome"] == "COMMITTED"
    assert fresh["evidence_timeline"]["active_semantic_hash"] == inline["semantic_hash"]
    assert [event["event_type"] for event in fresh["evidence_timeline"]["events"]] == [
        "CYCLE_STARTED",
        "INPUT_VALIDATED",
        "SOLVE_ATTEMPTED",
        "CANDIDATE_PRODUCED",
        "L4_EVALUATED",
        "PLAN_COMMITTED",
        "COMMAND_APPLIED",
        "ARTIFACT_INCOMPLETE",
    ]
    assert held["evidence_timeline"]["latest_terminal_outcome"] == "HELD"
    assert held["evidence_timeline"]["active_semantic_hash"] == inline["semantic_hash"]
    assert held["prediction_render"]["runtime_applied_reference"]["policy"] == "LINEAR_INTERPOLATION"
    assert held["prediction_render"]["runtime_applied_reference"]["elapsed_s"] == 1.0


def test_adapter_reduces_immutable_artifact_completion_on_runner_thread(tmp_path: Path) -> None:
    writer = EvidenceWriter(tmp_path / "run")
    sink = BoundedArtifactSink(writer)
    adapter = IntegrationRegistry().build_algorithm(
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
        factory_context=FactoryContext(
            ALGORITHM_ID,
            0,
            scenario_id="route",
            tracker_id="god",
            deadline_mode=DeadlineMode.OFF,
            artifact_sink=sink,
        ),
    )

    _plan(adapter, 0.0)
    submitted = adapter.get_colav_data()["planner"]["algorithm_details"]["assembly"]["artifact"]
    deadline = time.monotonic() + 2.0
    artifact_path = writer.run_dir / str(submitted["relative_path"])
    while not artifact_path.exists() and time.monotonic() < deadline:
        time.sleep(0.01)
    _plan(adapter, 1.0)
    trace = adapter.get_colav_data()["planner"]
    sink.close(timeout_s=2.0)

    assert submitted["status"] == "QUEUED"
    assert trace["evidence_timeline"]["artifact_state"] == "COMPLETE"


def test_artifact_backpressure_does_not_revoke_committed_mid_mpc_command(tmp_path: Path) -> None:
    writer = EvidenceWriter(tmp_path / "run")
    sink = BoundedArtifactSink(writer, max_items=1, start_worker=False)
    queued = sink({"occupies": "queue"})
    adapter = IntegrationRegistry().build_algorithm(
        ALGORITHM_ID,
        {
            "factory": "colav_simulator.integrations.mid_mpc_ipopt:create",
            "kwargs": {"horizon_steps": 4, "horizon_dt_s": 5.0},
        },
        factory_context=FactoryContext(
            ALGORITHM_ID,
            0,
            scenario_id="route",
            tracker_id="god",
            deadline_mode=DeadlineMode.OFF,
            artifact_sink=sink,
        ),
    )

    command = _plan(adapter, 0.0)
    trace = adapter.get_colav_data()["planner"]
    sink.close(timeout_s=0.0)

    assert queued["status"] == "QUEUED"
    assert np.count_nonzero(command) > 0
    assert trace["evidence_timeline"]["latest_terminal_outcome"] == "COMMITTED"
    assert trace["evidence_timeline"]["artifact_state"] == "BACKPRESSURE"
    assert trace["algorithm_details"]["assembly"]["artifact"]["reason"] == "ITEM_CAPACITY"


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
            scenario_id="route",
            tracker_id="god",
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
    tampered = bytearray(payload)
    tampered[-2] ^= 1
    assert hashlib.sha256(tampered).hexdigest() != reference["sha256"]
    document = json.loads(payload)
    assert document["prediction_evidence_hash"] == trace["evidence"]["inline"]["semantic_hash"]
    assert document["prediction_evidence"]["semantic_hash"] == document["prediction_evidence_hash"]
    assert document["prediction_evidence"]["ownship"]["grid"] == {
        "intervals": 4,
        "state_samples": 5,
        "dt_s": 5.0,
        "duration_s": 20.0,
    }
    assert document["assembly"]["problem_hash"] == assembly["problem_hash"]
    assert document["solver"]["prepared"]["x0"]
    assert document["solver"]["raw"]["x"]
    assert document["hashes"] == {
        "request": assembly["request_hash"],
        "problem": assembly["problem_hash"],
        "prepared": assembly["prepared_hash"],
        "solver": assembly["solver_hash"],
        "acceptance": assembly["acceptance_hash"],
        "receipt": assembly["receipt_hash"],
    }
    chain = document["hash_chain"]
    assert chain["request"]["hash"] == _canonical_hash(document["request_stage"])
    assert chain["problem"]["parent_hash"] == chain["request"]["hash"]
    assert chain["prepared"]["parent_hash"] == chain["problem"]["hash"]
    assert chain["solver"]["parent_hash"] == chain["prepared"]["hash"]
    assert chain["acceptance"]["parent_hash"] == chain["solver"]["hash"]
    assert chain["receipt"]["parent_hash"] == chain["acceptance"]["hash"]
    assert chain["problem"]["hash"] == _canonical_hash(document["problem_stage"])
    assert chain["prepared"]["hash"] == _canonical_hash(document["prepared_stage"])
    assert chain["solver"]["hash"] == _canonical_hash(document["solver_stage"])
    assert chain["acceptance"]["hash"] == _canonical_hash(document["acceptance_stage"])
    assert chain["receipt"]["hash"] == _canonical_hash(document["receipt_stage"])
    substituted_request = dict(document["request_stage"])
    substituted_request["frame"] = "NED"
    assert _canonical_hash(substituted_request) != chain["request"]["hash"]
    substituted_solver = dict(document["solver_stage"])
    substituted_solver["parent_prepared_hash"] = "0" * 64
    assert _canonical_hash(substituted_solver) != chain["solver"]["hash"]
    projection = trace["algorithm_details"]["render_projection"]
    assert projection["frame"] == "ENU"
    assert projection["axis_order"] == ["sample"]
    assert set(projection["ownship"]) == {
        "north_m",
        "east_m",
        "heading_rad",
        "speed_mps",
    }
    assert len(projection["ownship"]["north_m"]) == 5
    np.testing.assert_allclose(
        projection["ownship"]["north_m"],
        np.asarray(trace["predicted_trajectory"])[0],
    )
    np.testing.assert_allclose(
        projection["ownship"]["east_m"],
        np.asarray(trace["predicted_trajectory"])[1],
    )
    assert len(json.dumps(trace["algorithm_details"]["assembly"])) < 8_192


def test_dynamic_tracks_use_shared_geometry_and_direct_optimizer_intents() -> None:
    adapter = _fast_adapter(scenario_id="paper_ccta2023_multiship")
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
        model_name="KinematicCSOG",
        controller_name="PassThroughCS",
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
    assert details["selected_target_ids"] == [14, 12, 13, 11]
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
    assert trace["schema_version"] == "1.1"
    assert trace["evidence"] is None
    assert trace["evidence_timeline"]["latest_terminal_outcome"] == "FAILED"
    assert trace["evidence_timeline"]["active_semantic_hash"] is None


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
            scenario_id="head_on",
            tracker_id="god",
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
        [(22, np.array([1000.0, 100.0, 2.0, 0.0]), covariance, 15.0, 4.0)],
    )
    overtaking = overtaking_adapter.get_colav_data()["planner"]
    assert overtaking["target_predictions"][0]["encounter"] == "overtaking"
    assert overtaking["target_predictions"][0]["preferred_side"] == "port"


def test_conflicting_overtaking_sides_fail_l4_before_first_command() -> None:
    adapter = _fast_adapter(scenario_id="paper_ccta2023_multiship")
    covariance = np.eye(4)

    with np.testing.assert_raises(ColavExecutionError) as error:
        _plan(
            adapter,
            0.0,
            [
                (31, np.array([1000.0, 100.0, 2.0, 0.0]), covariance, 15.0, 4.0),
                (32, np.array([1000.0, -100.0, 2.0, 0.0]), covariance, 15.0, 4.0),
            ],
            model_name="KinematicCSOG",
            controller_name="PassThroughCS",
        )
    assert "COLREG_CONFLICTING_LOCKED_SIDES" in str(error.exception)
    assert error.exception.source is FailureSource.ALGORITHM
    failure = adapter.get_colav_data()["planner"]
    assert failure["solver_executed"] is False
    assert failure["solve_id"] == 0
    assert failure["status"] == PlanStatus.INFEASIBLE.value
    assert failure["algorithm_details"]["failure_code"] == "L4_PLAN_REJECTED"
    assert failure["schema_version"] == "1.1"
    assert failure["evidence_timeline"]["latest_terminal_outcome"] == "REJECTED"
    assert failure["evidence_timeline"]["active_semantic_hash"] is None
    assert failure["evidence_timeline"]["artifact_state"] == "INCOMPLETE"
    assert failure["prediction_render"]["style"] == "REJECTED"
    assert failure["prediction_render"]["executable"] is False
    assert failure["evidence"]["inline"]["accepted"] is False
    assert adapter.get_diagnostics().details["cached_plan_used"] is False


def test_rejected_candidate_keeps_last_committed_plan_as_invalid_history() -> None:
    adapter = _fast_adapter(scenario_id="paper_ccta2023_multiship")
    covariance = np.eye(4)

    _plan(adapter, 0.0)
    preserved = _plan(
        adapter,
        5.0,
        [
            (31, np.array([1000.0, 100.0, 2.0, 0.0]), covariance, 15.0, 4.0),
            (32, np.array([1000.0, -100.0, 2.0, 0.0]), covariance, 15.0, 4.0),
        ],
        model_name="KinematicCSOG",
        controller_name="PassThroughCS",
    )

    assert preserved.shape == (9, 1)
    trace = adapter.get_colav_data()["planner"]
    details = trace["algorithm_details"]
    assert details["candidate_rejected"] is True
    assert details["revision_reason"] == "L4_PLAN_REJECTED"
    assert details["trajectory_source"] == "held_plan"
    assert np.count_nonzero(adapter.get_current_plan()) > 0


def test_seventeenth_required_target_fails_before_solver_without_truncation() -> None:
    adapter = _fast_adapter()
    targets = [
        (target_id, np.array([1000.0 + target_id, 0.0, -4.0, 0.0]), np.eye(4), 15.0, 4.0) for target_id in range(1, 18)
    ]
    with np.testing.assert_raises(ColavExecutionError) as error:
        _plan(adapter, 0.0, targets)

    assert "CAPACITY_EXCEEDED" in str(error.exception)
    trace = adapter.get_colav_data()["planner"]
    assert trace["solver_executed"] is False
    assert trace["solve_id"] == 0
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
    assert trace["algorithm_details"]["hold_acceptance"]["accepted"] is True
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


def test_sequential_head_on_solves_preserve_absolute_time_prefix_continuity() -> None:
    adapter = _fast_adapter()
    ownship = np.array([0.0, 0.0, 0.0, 4.0, 0.0, 0.0])

    for sim_time_s in (0.0, 5.0, 10.0, 15.0):
        target = [
            (
                41,
                np.array([1000.0 - 4.0 * sim_time_s, 0.0, -4.0, 0.0]),
                np.eye(4),
                15.0,
                4.0,
            )
        ]
        _plan(adapter, sim_time_s, target, ownship=ownship)
        ownship = np.asarray(adapter.get_colav_data()["planner"]["predicted_trajectory"])[:6, 1].copy()

    rolling = adapter.get_diagnostics().details["rolling_plan"]
    assert rolling["reference"]["active"] is True
    assert rolling["assessment"]["revision_reason"] == "CONTINUITY_PRESERVED"
    assert rolling["assessment"]["accepted"] is True
    assert rolling["assessment"]["prefix"]["heading_rms_deg"] <= 3.0
    assert rolling["assessment"]["prefix"]["heading_max_deg"] <= 10.0
    assert rolling["assessment"]["prefix"]["position_max_m"] <= 10.0


def test_stale_held_plan_replans_once_before_command_visibility() -> None:
    adapter = _fast_adapter()
    _plan(adapter, 0.0)

    shifted = np.array([100.0, 0.0, 0.0, 4.0, 0.0, 0.0])
    command = _plan(adapter, 2.0, ownship=shifted)

    trace = adapter.get_colav_data()["planner"]
    assert trace["solver_executed"] is True
    assert trace["solve_id"] == 2
    assert trace["algorithm_details"]["hold_replan_reason"] == "OWN_STATE_DEVIATION"
    assert trace["algorithm_details"]["trajectory_source"] == "fresh_ipopt_solve"
    assert np.isfinite(command).all()
    np.testing.assert_allclose(adapter.get_current_plan()[:2, 0], shifted[:2], atol=1e-9)


def test_one_prediction_interval_heading_lag_does_not_bypass_solve_period() -> None:
    adapter = _fast_adapter(solve_period_s=10.0)
    _plan(adapter, 0.0)

    lagging = np.array([8.0, 0.0, np.deg2rad(16.0), 4.0, 0.0, 0.0])
    _plan(adapter, 2.0, ownship=lagging)

    trace = adapter.get_colav_data()["planner"]
    assert trace["solver_executed"] is False
    assert trace["solve_id"] == 1
    assert trace["algorithm_details"]["trajectory_source"] == "held_plan"


def test_compatible_dynamic_target_reuses_held_plan_with_full_l4_revalidation() -> None:
    adapter = _fast_adapter()
    covariance = np.zeros((4, 4))
    _plan(
        adapter,
        0.0,
        [(51, np.array([1000.0, 0.0, -4.0, 0.0]), covariance, 15.0, 4.0)],
    )

    _plan(
        adapter,
        2.0,
        [(51, np.array([992.0, 0.0, -4.0, 0.0]), covariance, 15.0, 4.0)],
    )

    trace = adapter.get_colav_data()["planner"]
    assert trace["solver_executed"] is False
    assert trace["solve_id"] == 1
    assert trace["algorithm_details"]["hold_acceptance"]["accepted"] is True


def test_capability_tuple_does_not_branch_on_scenario_id() -> None:
    adapter = _fast_adapter(scenario_id="unlisted_but_same_runtime_tuple")

    command = _plan(adapter, 0.0)

    assert np.isfinite(command).all()
    assert adapter.get_diagnostics().status is PlanStatus.SUCCESS


def test_only_accepted_receipt_can_seed_next_ipopt_solve() -> None:
    adapter = _fast_adapter()
    _plan(adapter, 0.0)
    assert adapter.get_diagnostics().details["warm_start_used"] is False

    _plan(adapter, 5.0)

    details = adapter.get_diagnostics().details
    assert details["warm_start_used"] is True
    assert details["accepted_plan_receipt"]["dual_warm_start"] is False
    assert details["accepted_plan_receipt"]["warm_start_eligible"] is True


def test_route_correction_does_not_discard_accepted_primal_warm_start() -> None:
    adapter = _fast_adapter(scenario_id="route")
    _plan(
        adapter,
        0.0,
        ownship=np.array([0.0, 20.0, 0.0, 4.0, 0.0, 0.0]),
    )
    tracked_state = adapter.get_current_plan()[:6, 1]

    _plan(
        adapter,
        5.0,
        ownship=tracked_state,
    )

    details = adapter.get_diagnostics().details
    assert details["warm_start_used"] is True
    assert details["accepted_plan_receipt"]["warm_start_eligible"] is True


def test_semantically_compatible_accepted_primal_is_not_discarded() -> None:
    adapter = _fast_adapter()
    facade = adapter._solve.__self__  # type: ignore[attr-defined]
    facade._accepted_primal = (
        0.0,
        np.zeros(4),
        np.full(4, 4.0),
        "single-encounter:viknes:flsc",
        "stable-token",
    )

    warm_start = facade._primal_warm_start(
        SimpleNamespace(sim_time_s=5.0),
        SimpleNamespace(exact_tuple="single-encounter:viknes:flsc"),
        "stable-token",
    )

    assert warm_start is not None


def test_runtime_evidence_timeline_is_bounded_to_latest_committed_cycle() -> None:
    adapter = _fast_adapter(scenario_id="route")
    _plan(adapter, 0.0)
    for sim_time_s in (1.0, 2.0, 3.0, 4.0):
        _plan(adapter, sim_time_s)
    _plan(adapter, 5.0)
    for sim_time_s in (6.0, 7.0, 8.0, 9.0):
        _plan(adapter, sim_time_s)

    timeline = adapter.get_colav_data()["planner"]["evidence_timeline"]
    events = timeline["events"]

    assert len(events) < 30
    assert events[0]["event_type"] == "CYCLE_STARTED"
    assert events[0]["caused_by"] is None
    assert events[0]["occurrence_id"]["event_seq"] > 0
    assert [event["event_type"] for event in events].count("PLAN_COMMITTED") == 1
    assert timeline["latest_terminal_outcome"] == "HELD"


def test_reset_clears_encounter_commitment() -> None:
    adapter = _fast_adapter()
    target = [(41, np.array([1000.0, 0.0, -4.0, 0.0]), np.eye(4), 15.0, 4.0)]

    _plan(adapter, 0.0, target)
    assert adapter.get_diagnostics().details["minimum_alteration_active"] is False
    _plan(adapter, 5.0, target)
    assert adapter.get_diagnostics().details["minimum_alteration_active"] is True
    _plan(adapter, 10.0, target, ownship=np.array([35.0, 0.0, math.radians(5.0), 4.0, 0.0, 0.0]))
    assert adapter.get_diagnostics().details["minimum_alteration_active"] is True

    adapter.reset()
    _plan(adapter, 0.0, target)
    assert adapter.get_diagnostics().details["minimum_alteration_active"] is False
    reset_events = adapter.get_colav_data()["planner"]["evidence_timeline"]["events"]
    assert reset_events[0]["event_type"] == "RESET"
    assert reset_events[0]["occurrence_id"]["epoch"] == 1


def test_schedule_error_fails_stop_and_ipopt_evidence_is_json_safe() -> None:
    adapter = _fast_adapter()
    _plan(adapter, 0.0)

    diagnostics = adapter.get_diagnostics()
    trace = adapter.get_colav_data()["planner"]
    assert diagnostics.status is PlanStatus.SUCCESS
    assert diagnostics.fallback_used is False
    assert (
        diagnostics.details["ipopt_return_status"],
        diagnostics.details["normalized_solver_status"],
    ) in {
        ("Solve_Succeeded", "Converged"),
        ("Solved_To_Acceptable_Level", "FeasibleNonOptimal"),
        ("User_Requested_Stop", "FeasibleNonOptimal"),
    }
    assert diagnostics.details["objective_components"].keys() == {
        "colreg",
        "heading",
        "speed",
        "route",
        "asymmetry",
        "terminal",
        "cpa_slack",
        "direction_slack",
        "continuity",
    }
    assert trace["constraints"]["max_constraint_violation"] <= 1e-3
    json.dumps(adapter.get_colav_data(), allow_nan=False)

    with np.testing.assert_raises(ColavExecutionError) as error:
        _plan(adapter, -1.0)
    assert error.exception.status is PlanStatus.INVALID_INPUT
    assert error.exception.source is FailureSource.SCENARIO
    failed = adapter.get_colav_data()["planner"]
    assert failed["evidence_timeline"]["latest_terminal_outcome"] == "FAILED"
    assert failed["evidence_timeline"]["active_semantic_hash"] is None
    assert failed["evidence_timeline"]["last_committed_executable"] is False
    assert adapter.get_current_plan().shape == (9, 1)
    assert np.count_nonzero(adapter.get_current_plan()) == 0


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
        factory_context=FactoryContext(
            ALGORITHM_ID,
            0,
            scenario_id="route",
            tracker_id="god",
            deadline_mode=DeadlineMode.OFF,
        ),
    )

    with np.testing.assert_raises(ColavExecutionError) as error:
        _plan(adapter, 0.0)

    assert error.exception.status is PlanStatus.INFEASIBLE
    assert error.exception.source is FailureSource.ALGORITHM
    assert adapter.get_diagnostics().fallback_used is False
    assert adapter.get_colav_data()["planner"]["solve_id"] == 0


def test_mid_mpc_rejects_deadline_without_frozen_acceptance_reservation() -> None:
    with np.testing.assert_raises(ColavExecutionError) as error:
        IntegrationRegistry().build_algorithm(
            ALGORITHM_ID,
            {
                "factory": "colav_simulator.integrations.mid_mpc_ipopt:create",
                "kwargs": {
                    "horizon_steps": 4,
                    "horizon_dt_s": 5.0,
                    "solve_period_s": 5.0,
                    "deadline_s": 5.0,
                },
            },
            factory_context=FactoryContext(ALGORITHM_ID, 0, deadline_mode=DeadlineMode.ENFORCE),
        )
    assert error.exception.status is PlanStatus.INVALID_INPUT


def test_adapter_rejection_before_commit_cannot_publish_warm_start(monkeypatch) -> None:
    adapter = _fast_adapter()
    facade = adapter._solve.__self__  # type: ignore[attr-defined]

    def reject_solution(_solution, _planner_input) -> None:
        raise ColavExecutionError(PlanStatus.INVALID_INPUT, "injected validation rejection")

    monkeypatch.setattr(adapter, "_validate_solution", reject_solution)

    with np.testing.assert_raises(ColavExecutionError):
        _plan(adapter, 0.0)

    assert facade._accepted_primal is None


def test_total_deadline_failure_keeps_candidate_evidence_without_command() -> None:
    adapter = _fast_adapter(scenario_id="route")
    adapter.context = replace(adapter.context, deadline_mode=DeadlineMode.ENFORCE)
    adapter.descriptor = replace(
        adapter.descriptor,
        execution_profile=replace(adapter.descriptor.execution_profile, deadline_s=1.0e-9),
    )

    with np.testing.assert_raises(ColavExecutionError) as error:
        _plan(adapter, 0.0)

    assert error.exception.details["failure_code"] == "TOTAL_DEADLINE_EXCEEDED"
    trace = adapter.get_colav_data()["planner"]
    event_types = [event["event_type"] for event in trace["evidence_timeline"]["events"]]
    assert "CANDIDATE_PRODUCED" in event_types
    assert "L4_EVALUATED" in event_types
    assert "PLAN_COMMITTED" not in event_types
    assert "COMMAND_APPLIED" not in event_types
    assert trace["evidence_timeline"]["latest_terminal_outcome"] == "FAILED"
    assert trace["evidence_timeline"]["active_semantic_hash"] is None
    assert trace["evidence"]["authority"]["receipt"] is None
    assert trace["prediction_render"]["style"] == "INVALID_HISTORY"
    assert np.count_nonzero(adapter.get_current_plan()) == 0


def test_multiship_capability_accepts_single_target_and_target_free_ticks() -> None:
    adapter = _fast_adapter(scenario_id="paper_ccta2023_multiship")
    covariance = np.eye(4)

    mission_only = _plan(
        adapter,
        0.0,
        model_name="KinematicCSOG",
        controller_name="PassThroughCS",
    )
    single_target = _plan(
        adapter,
        1.0,
        [
            (21, np.array([500.0, 0.0, -4.0, 0.0]), covariance, 15.0, 4.0),
        ],
        model_name="KinematicCSOG",
        controller_name="PassThroughCS",
    )

    assert mission_only.shape == (9, 1)
    assert single_target.shape == (9, 1)
    assert adapter.get_current_plan().shape == (9, 5)
    trace = adapter.get_colav_data()["planner"]
    assert trace["algorithm_details"]["decision_intent"] in {"HOLD", "GIVE_WAY"}


def test_optimizer_unresolved_preserves_held_plan_for_one_period(monkeypatch) -> None:
    adapter = _fast_adapter(scenario_id="paper_ccta2023_multiship")
    covariance = np.eye(4)
    first = _plan(
        adapter,
        0.0,
        [(21, np.array([800.0, 0.0, -4.0, 0.0]), covariance, 15.0, 4.0)],
        model_name="KinematicCSOG",
        controller_name="PassThroughCS",
    )
    assert first.shape == (9, 1)

    def unresolved(status: object, max_violation: object) -> tuple[object, bool]:
        return PlanStatus.NUMERICAL_FAILURE, False

    monkeypatch.setattr(mid_mpc_module, "_plan_status", unresolved)
    preserved = _plan(
        adapter,
        5.0,
        [(21, np.array([700.0, 0.0, -4.0, 0.0]), covariance, 15.0, 4.0)],
        model_name="KinematicCSOG",
        controller_name="PassThroughCS",
    )
    assert preserved.shape == (9, 1)
    held = _plan(
        adapter,
        6.0,
        [(21, np.array([680.0, 0.0, -4.0, 0.0]), covariance, 15.0, 4.0)],
        model_name="KinematicCSOG",
        controller_name="PassThroughCS",
    )
    details = adapter.get_colav_data()["planner"]["algorithm_details"]
    assert held.shape == (9, 1)
    assert details["candidate_rejected"] is True
    assert details["revision_reason"] == "OPTIMIZER_UNRESOLVED"
    assert details["trajectory_source"] == "held_plan"
