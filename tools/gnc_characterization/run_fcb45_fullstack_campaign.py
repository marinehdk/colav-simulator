"""Run one product scenario through the physical FCB45 stack and retain evidence.

Invoke once per cell so native solver graphs do not accumulate across cells.
No scenario geometry, solver safety constraints or endpoint tolerances change.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import math
import subprocess
import time
from dataclasses import replace
from pathlib import Path

import numpy as np
from shapely.geometry import LineString, Point

from colav_simulator.cli import _load_algorithm_config
from colav_simulator.common.map_functions import extract_typed_grounding_hazards, find_minimum_depth
from colav_simulator.core.colav.threat_management import MID_MPC_VALIDATION_DOMAIN_PROFILE
from colav_simulator.experiment.runner import ExperimentRunner
from colav_simulator.modular_gnc.catalog import list_stack_catalog
from gui_server.main import SessionCreateRequest

SCENARIOS = {
    "overtaking": "rule13",
    "head_on": "rule14",
    "crossing_give_way": "rule15",
    "paper_ccta2023_multiship": "multiship",
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def run_cell(root: Path, output: Path, scenario: str, algorithm: str) -> dict:  # noqa: PLR0915
    """Execute one cell and write both success and failure evidence."""
    output.mkdir(parents=True, exist_ok=True)
    sources = sorted(
        {
            *root.glob("colav_simulator/modular_gnc/*.py"),
            *root.glob("colav_simulator/core/colav/*.py"),
            *root.glob("colav_simulator/core/colav/mid_mpc/*.py"),
            root / "colav_simulator/integrations/mid_mpc_ipopt.py",
            root / "colav_simulator/integrations/potocnik_colreg_mpc.py",
        }
    )
    fingerprint = {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sources}
    (output / "source_fingerprint.json").write_text(json.dumps(fingerprint, indent=2))
    stack_entry = next(x for x in list_stack_catalog()["stacks"] if "fcb45_environmental_load" in x["stack_id"])
    config = {}
    domain = None
    if algorithm == "mid_mpc_ipopt":
        config = _load_algorithm_config(root / "config/mid_mpc_ipopt.yaml")
        config["kwargs"].update(cpa_safe_m=200.0, cpa_hard_m=180.0)
        domain = MID_MPC_VALIDATION_DOMAIN_PROFILE.to_dict()
    spec = SessionCreateRequest(
        scenario_id=scenario,
        validation_rule_id=SCENARIOS[scenario],
        algorithm_id=algorithm,
        tracker_id="god",
        gnc_stack_id=stack_entry["stack_id"],
        algorithm_config=config,
        domain_profile=domain,
    ).to_spec()
    # Seacharts regenerates a process-shared on-disk shapefile cache. Serialize
    # preparation across campaign cells; the in-memory simulations can overlap.
    lock_path = root / "tmp" / "fcb45_fullstack_enc_prepare.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("w") as cache_lock:
        fcntl.flock(cache_lock, fcntl.LOCK_EX)
        prepared = ExperimentRunner(root).prepare(replace(spec, output_root=str(output / "run")))
    session = prepared.session
    ownship = session.simulator.ownship
    stack = ownship.stack
    mission_route = LineString(ownship.waypoints.T)
    hazards = extract_typed_grounding_hazards(
        find_minimum_depth(ownship.draft, session.simulator.enc), session.simulator.enc
    ).combined_geometry
    radius = 0.5 * math.hypot(ownship.length, ownship.width)
    target_count = len(session.ship_list) - 1
    minima = np.full(target_count, np.inf)
    metrics = {
        "scenario": scenario,
        "algorithm": algorithm,
        "stack_id": stack_entry["stack_id"],
        "config_hash": stack_entry["config_hash"],
        "mission_waypoints_ne_m": ownship.waypoints.T.tolist(),
        "max_mission_cross_track_m": 0.0,
        "min_static_hull_clearance_m": math.inf,
        "max_roll_deg": 0.0,
        "max_rudder_angle_deg": 0.0,
        "max_bow_force_at_cruise_n": 0.0,
        "guidance_calls": 0,
        "solver_calls": 0,
        "max_solver_ms": 0.0,
        "failures": [],
        "source_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
        "source_fingerprint_hash": hashlib.sha256(json.dumps(fingerprint, sort_keys=True).encode()).hexdigest(),
    }
    (output / "stack_evidence.json").write_text(json.dumps(stack_entry, indent=2))
    session.enable_pickle_frames()
    session.start()
    started = time.monotonic()
    last_report = -math.inf
    previous_positions = np.array([vessel.state[:2].copy() for vessel in session.ship_list])
    try:
        with (output / "trace.jsonl").open("w") as trace_file:
            while session.state.value == "RUNNING":
                frame = session.advance().payload
                # The transport frame can describe the start of this interval;
                # inspect the completed physical step, including the final one.
                own = np.asarray(ownship.state).copy()
                targets = [np.asarray(vessel.state).copy() for vessel in session.ship_list[1:]]
                ranges = np.array([np.linalg.norm(own[:2] - target[:2]) for target in targets])
                mission_xte = Point(own[:2]).distance(mission_route)
                metrics["max_mission_cross_track_m"] = max(metrics["max_mission_cross_track_m"], mission_xte)
                clearance = Point(own[1], own[0]).distance(hazards) - radius
                positions = np.array([own[:2], *(target[:2] for target in targets)])
                if previous_positions is not None:
                    relative = previous_positions[0] - previous_positions[1:]
                    change = positions[0] - positions[1:] - relative
                    norm2 = np.sum(change**2, axis=1)
                    fraction = np.clip(-np.sum(relative * change, axis=1) / np.maximum(norm2, 1e-20), 0.0, 1.0)
                    ranges = np.minimum(ranges, np.linalg.norm(relative + fraction[:, None] * change, axis=1))
                    clearance = min(
                        clearance,
                        LineString(previous_positions[[0], ::-1].tolist() + positions[[0], ::-1].tolist()).distance(hazards)
                        - radius,
                    )
                previous_positions = positions
                minima = np.minimum(minima, ranges)
                metrics["min_static_hull_clearance_m"] = min(metrics["min_static_hull_clearance_m"], clearance)
                actuator = stack.modules.actuator_trace()
                guidance = stack.modules.guidance_trace()
                loads = stack.modules.environmental_loads()
                _require(actuator is not None and guidance is not None and loads is not None, "physical GNC trace missing")
                _require(guidance.tick == stack.tick - 1, "ILOS did not run on the latest physical tick")
                metrics["guidance_calls"] += 1
                metrics["max_roll_deg"] = max(
                    metrics["max_roll_deg"], abs(math.degrees(stack.modules.plant_state().roll_rad))
                )
                metrics["max_rudder_angle_deg"] = max(
                    metrics["max_rudder_angle_deg"], *(abs(math.degrees(v)) for v in actuator.rudder_angles_rad.values())
                )
                relative_speed = math.hypot(loads.details["relative_surge_mps"], loads.details["relative_sway_mps"])
                if relative_speed >= 3.2:
                    metrics["max_bow_force_at_cruise_n"] = max(
                        metrics["max_bow_force_at_cruise_n"],
                        *(abs(v) for k, v in actuator.actuator_outputs_n.items() if k.startswith("bow_")),
                    )
                planner = frame["Ship0"]["colav"]["planner"]
                allocation = stack.modules.allocator_solution()
                if planner["solver_executed"]:
                    metrics["solver_calls"] += 1
                    metrics["max_solver_ms"] = max(metrics["max_solver_ms"], planner["elapsed_ms"])
                row = {
                    "time_s": session.simulator.t,
                    "own": own.tolist(),
                    "targets": [t.tolist() for t in targets],
                    "ranges_m": ranges.tolist(),
                    "static_clearance_m": clearance,
                    "roll_rad": stack.modules.plant_state().roll_rad,
                    "xte_m": guidance.cross_track_error_m,
                    "mission_cross_track_m": mission_xte,
                    "route_id": guidance.route_id,
                    "heading_reference_rad": guidance.heading_reference_rad,
                    "speed_reference_mps": guidance.speed_reference_mps,
                    "controller_reference": list(stack.modules.controller_trace().reference),
                    "controller_request": list(stack.modules.controller_trace().raw_request),
                    "controller_achieved": list(actuator.achieved_load),
                    "planner_mode": {
                        key: planner.get("algorithm_details", {}).get(key)
                        for key in (
                            "maneuver_phase",
                            "active_encounters",
                            "goal_ne_m",
                            "route_reference_mode",
                        )
                    },
                    "rudder_angles_rad": dict(actuator.rudder_angles_rad),
                    "allocator_evaluations": allocation.allocation_evaluations,
                    "allocator_optimality": allocation.allocation_optimality,
                    "actuator_forces_n": dict(actuator.actuator_outputs_n),
                    "bow_authority": actuator.bow_authority,
                    "environment": {
                        name: [
                            getattr(loads, name).surge_n,
                            getattr(loads, name).sway_n,
                            getattr(loads, name).roll_nm,
                            getattr(loads, name).yaw_nm,
                        ]
                        for name in ("wind", "current", "wave_first_order", "wave_mean_drift")
                    },
                    "solver_executed": planner["solver_executed"],
                    "feasible": planner["feasible"],
                }
                trace_file.write(json.dumps(row) + "\n")
                if session.simulator.t - last_report >= 100.0:
                    print(scenario, algorithm, f"t={session.simulator.t:.1f}", "min_ranges", minima.tolist(), flush=True)
                    last_report = session.simulator.t
                _require(clearance > 0.0, "actual hull intersects chart hazard")
                _require(np.min(ranges) > 180.0, "ownship-target clearance below existing 180 m gate")
                _require(planner["feasible"], "planner is infeasible")
                _require(metrics["max_bow_force_at_cruise_n"] == 0.0, "bow thruster used above lockout")
                session._frame_blobs.clear()
        if session.failure_reason:
            metrics["failures"].append(session.failure_reason)
    except Exception as exc:
        metrics["failures"].append(f"{type(exc).__name__}: {exc}")
        (output / "failure_diagnostics.json").write_text(
            json.dumps(
                {
                    "exception_details": getattr(exc, "details", {}),
                    "planner": ownship.get_colav_data(),
                },
                default=lambda value: value.tolist() if isinstance(value, np.ndarray) else str(value),
                indent=2,
            )
        )
    finally:
        prepared.artifact_sink.close(timeout_s=2.0)
        metrics.update(
            {
                "state": session.state.value,
                "end_time_s": session.simulator.t,
                "goal_reached": bool(session.simulator.determine_ship_goal_reached(0)),
                "minimum_center_distances_m": minima.tolist(),
                "final_goal_distance_m": float(np.linalg.norm(ownship.state[:2] - ownship.waypoints[:, -1])),
                "final_mission_cross_track_m": Point(ownship.state[:2]).distance(mission_route),
                "final_speed_mps": float(np.linalg.norm(ownship.state[3:5])),
                "events": session.events,
                "fallback_used": prepared.manifest.fallback_used,
                "wall_time_s": time.monotonic() - started,
            }
        )
        if not metrics["goal_reached"]:
            metrics["failures"].append("mission goal not reached")
            (output / "last_planner.json").write_text(
                json.dumps(
                    ownship.get_colav_data(),
                    default=lambda value: value.tolist() if isinstance(value, np.ndarray) else str(value),
                    indent=2,
                )
            )
        if metrics["fallback_used"]:
            metrics["failures"].append("fallback used")
        if {"collision", "grounding", "session_failed"} & {e["type"] for e in session.events}:
            metrics["failures"].append("collision, grounding or session failure event")
        (output / "metrics.json").write_text(json.dumps(metrics, indent=2))
    return metrics


def main() -> int:
    """Run an isolated campaign cell from the command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=tuple(SCENARIOS), required=True)
    parser.add_argument("--algorithm", choices=("vo", "potocnik_colreg_fan_mpc", "mid_mpc_ipopt"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run_cell(Path(__file__).resolve().parents[2], args.output, args.scenario, args.algorithm)
    print(json.dumps(result, indent=2))
    return int(bool(result["failures"]))


if __name__ == "__main__":
    raise SystemExit(main())
