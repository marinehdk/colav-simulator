"""Product Tier2 trajectory regression for anticipatory encounter sequencing."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import numpy as np
from shapely.geometry import LineString, Point

from colav_simulator.cli import _load_algorithm_config
from colav_simulator.common.map_functions import extract_typed_grounding_hazards, find_minimum_depth
from colav_simulator.core.colav.threat_management import MID_MPC_VALIDATION_DOMAIN_PROFILE
from colav_simulator.experiment.runner import ExperimentRunner
from gui_server.main import SessionCreateRequest


def test_three_target_anticipatory_run_reaches_goal_and_sequences_actions(tmp_path: Path) -> None:  # noqa: PLR0915
    root = Path(__file__).resolve().parents[1]
    config = _load_algorithm_config(root / "config/mid_mpc_ipopt.yaml")
    config["kwargs"].update(cpa_safe_m=200.0, cpa_hard_m=180.0)
    spec = SessionCreateRequest(
        scenario_id="paper_ccta2023_multiship",
        validation_rule_id="multiship",
        algorithm_id="mid_mpc_ipopt",
        tracker_id="god",
        gnc_stack_id="fcb45_3dof_plant+pass_through_guidance+fcb45_marine_pid",
        algorithm_config=config,
        domain_profile=MID_MPC_VALIDATION_DOMAIN_PROFILE.to_dict(),
    ).to_spec()
    prepared = ExperimentRunner(root).prepare(replace(spec, output_root=str(tmp_path)))
    session = prepared.session
    session.enable_pickle_frames()
    session.start()
    pending = set()
    active_order = []
    minimum_ranges = np.full(3, np.inf)
    maximum_solver_ms = 0.0
    slowest_solve = {}
    radius = 0.5 * np.hypot(session.simulator.ownship.length, session.simulator.ownship.width)
    hazards = extract_typed_grounding_hazards(
        find_minimum_depth(session.simulator.ownship.draft, session.simulator.enc),
        session.simulator.enc,
    ).combined_geometry
    minimum_static_prediction_m = np.inf
    minimum_static_actual_m = np.inf
    try:
        while session.state.value == "RUNNING":
            frame = session.advance().payload
            own = frame["Ship0"]["state"]
            actual_clearance = Point(own[1], own[0]).distance(hazards) - radius
            minimum_static_actual_m = min(minimum_static_actual_m, actual_clearance)
            assert actual_clearance > 0
            assert own[3] > 0.0, "ownship must not reverse"
            for i in range(1, 4):
                minimum_ranges[i - 1] = min(minimum_ranges[i - 1], np.linalg.norm(own[:2] - frame[f"Ship{i}"]["state"][:2]))
            planner = frame["Ship0"]["colav"]["planner"]
            if planner["solver_executed"]:
                assert planner["feasible"]
                if planner["algorithm_details"].get("candidate_rejected", False):
                    assert planner["algorithm_details"]["hold_acceptance"]["accepted"] is True
                    assert planner["algorithm_details"]["plan_acceptance"]["accepted"] is True
                if planner["elapsed_ms"] > maximum_solver_ms:
                    maximum_solver_ms = planner["elapsed_ms"]
                    slowest_solve = {
                        "sim_time_s": session.simulator.t,
                        "elapsed_ms": planner["elapsed_ms"],
                        "candidate_rejected": planner["algorithm_details"].get("candidate_rejected", False),
                        "graph_build_ms": planner["algorithm_details"].get("graph_build_elapsed_ms"),
                        "ipopt_ms": planner["algorithm_details"].get("ipopt_elapsed_ms"),
                    }
                prediction = np.asarray(planner["predicted_trajectory"])
                clearance = LineString(prediction[[1, 0]].T).distance(hazards) - radius
                minimum_static_prediction_m = min(minimum_static_prediction_m, clearance)
                assert clearance >= 1.0
            snapshot = session.threat_management_coordinator.last_snapshot
            for d in snapshot.lifecycle_snapshot.targets:
                if (
                    d.risk.value == "CANDIDATE"
                    and d.planned_action_at_s is not None
                    and d.planned_action_at_s > snapshot.sim_time_s
                ):
                    pending.add(d.key.target_id)
                    assert snapshot.lifecycle_snapshot.primary_target != d.key
                if d.risk.value == "ACTIVE" and d.key.target_id not in active_order:
                    active_order.append(d.key.target_id)
            # Every emitted frame is checked before discarding this test's raw
            # history. Production frame retention and durable solve audit are unchanged.
            session._frame_blobs.clear()
        assert session.failure_reason is None
        assert session.simulator.determine_ship_goal_reached(0)
        assert not {"collision", "grounding", "session_failed"} & {e["type"] for e in session.events}
        assert active_order == [1, 2, 3]
        assert pending >= {1, 2, 3}
        assert np.min(minimum_ranges) > 250.0
        assert all(d.risk.value == "RELEASED" for d in snapshot.lifecycle_snapshot.targets)
        assert prepared.manifest.fallback_used is False
        (tmp_path / "static_acceptance_metrics.json").write_text(
            json.dumps(
                {
                    "final_time_s": snapshot.sim_time_s,
                    "minimum_target_ranges_m": minimum_ranges.tolist(),
                    "minimum_static_prediction_clearance_m": minimum_static_prediction_m,
                    "minimum_static_actual_clearance_m": minimum_static_actual_m,
                    "maximum_solver_ms": maximum_solver_ms,
                    "slowest_solve": slowest_solve,
                    "planned_target_ids": sorted(pending),
                    "active_target_order": active_order,
                    "final_target_risks": {d.key.target_id: d.risk.value for d in snapshot.lifecycle_snapshot.targets},
                    "fallback_used": prepared.manifest.fallback_used,
                },
                indent=2,
            )
        )
        assert maximum_solver_ms < 2000.0, slowest_solve
    finally:
        prepared.artifact_sink.close(timeout_s=2.0)
