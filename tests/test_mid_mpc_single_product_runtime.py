"""Single-target product runs with the user's real GNC and clearance profile."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from shapely.geometry import LineString, Point

from colav_simulator.cli import _load_algorithm_config
from colav_simulator.common.map_functions import extract_typed_grounding_hazards, find_minimum_depth
from colav_simulator.core.colav.threat_management import MID_MPC_VALIDATION_DOMAIN_PROFILE
from colav_simulator.experiment.runner import ExperimentRunner
from gui_server.main import SessionCreateRequest


@pytest.mark.parametrize(
    ("scenario", "rule"), [("overtaking", "rule13"), ("head_on", "rule14"), ("crossing_give_way", "rule15")]
)
def test_single_target_product_run_remains_safe(  # noqa: PLR0915 - one complete runtime evidence gate
    tmp_path: Path, scenario: str, rule: str
) -> None:
    root = Path(__file__).resolve().parents[1]
    config = _load_algorithm_config(root / "config/mid_mpc_ipopt.yaml")
    config["kwargs"].update(cpa_safe_m=200.0, cpa_hard_m=180.0)
    spec = SessionCreateRequest(
        scenario_id=scenario,
        validation_rule_id=rule,
        algorithm_id="mid_mpc_ipopt",
        tracker_id="god",
        gnc_stack_id="fcb45_3dof_plant+pass_through_guidance+fcb45_marine_pid",
        algorithm_config=config,
        domain_profile=MID_MPC_VALIDATION_DOMAIN_PROFILE.to_dict(),
    ).to_spec()
    prepared = ExperimentRunner(root).prepare(replace(spec, output_root=str(tmp_path)))
    session = prepared.session
    hazards = extract_typed_grounding_hazards(
        find_minimum_depth(session.simulator.ownship.draft, session.simulator.enc), session.simulator.enc
    ).combined_geometry
    radius = 0.5 * np.hypot(session.simulator.ownship.length, session.simulator.ownship.width)
    if scenario in {"head_on", "overtaking"}:
        endpoint = Point(42900.0, 6960900.0)
        assert endpoint.distance(hazards) > 150.0
        start = (39500.0, 6957500.0) if scenario == "head_on" else (39000.0, 6957000.0)
        assert LineString([start, (endpoint.x, endpoint.y)]).distance(hazards) > radius
    session.enable_pickle_frames()
    session.start()
    times = []
    rejoined_at = None
    saw_avoidance = False
    route = session.simulator.ownship.waypoints
    tangent = route[:, -1] - route[:, -2]
    tangent = tangent / np.linalg.norm(tangent)
    normal = np.array([-tangent[1], tangent[0]])
    minimum = np.inf
    try:
        while session.state.value == "RUNNING":
            frame = session.advance().payload
            own = frame["Ship0"]["state"]
            minimum = min(minimum, float(np.linalg.norm(own[:2] - frame["Ship1"]["state"][:2])))
            assert Point(own[1], own[0]).distance(hazards) > radius
            decisions = session.threat_management_coordinator.last_snapshot.lifecycle_snapshot.targets
            saw_avoidance |= any(d.risk.value == "ACTIVE" for d in decisions)
            course_error = np.arctan2(
                np.sin(own[2] - np.arctan2(tangent[1], tangent[0])), np.cos(own[2] - np.arctan2(tangent[1], tangent[0]))
            )
            if (
                saw_avoidance
                and rejoined_at is None
                and all(d.route_recovery_allowed for d in decisions)
                and abs(float((own[:2] - route[:, -2]) @ normal)) <= 20.0
                and abs(course_error) <= np.deg2rad(8.0)
                and np.linalg.norm(own[:2] - route[:, -1]) > 200.0
            ):
                rejoined_at = session.simulator.t
            planner = frame["Ship0"]["colav"]["planner"]
            assert planner["feasible"]
            if planner["solver_executed"]:
                times.append((session.simulator.t, planner["elapsed_ms"]))
            session._frame_blobs.clear()
        assert session.failure_reason is None
        assert not {"collision", "grounding", "session_failed"} & {e["type"] for e in session.events}
        assert minimum > 180.0
        assert rejoined_at is not None, "did not rejoin the mission leg before final approach"
        assert prepared.manifest.fallback_used is False
        assert session.state.value == "FINISHED"
        assert session.simulator.determine_ship_goal_reached(0)
        assert float(np.linalg.norm(session.simulator.ownship.state[3:5])) <= 0.05
        assert float(np.linalg.norm(session.simulator.ownship.state[:2] - session.simulator.ownship.waypoints[:, -1])) <= 5.0
        (tmp_path / "metrics.json").write_text(
            json.dumps(
                {
                    "scenario": scenario,
                    "end_time": session.simulator.t,
                    "goal_reached": bool(session.simulator.determine_ship_goal_reached(0)),
                    "minimum_center_distance_m": minimum,
                    "rejoined_at_s": rejoined_at,
                    "final_speed_mps": float(np.linalg.norm(session.simulator.ownship.state[3:5])),
                    "final_goal_distance_m": float(
                        np.linalg.norm(session.simulator.ownship.state[:2] - session.simulator.ownship.waypoints[:, -1])
                    ),
                    "solve_times_ms": times,
                },
                indent=2,
            )
        )
    finally:
        prepared.artifact_sink.close(timeout_s=2.0)
