"""Generate closed-loop Kuwata VO evidence from real Simulator runs."""

from __future__ import annotations

import argparse
import copy
import csv
import json
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from shapely.geometry import box

import colav_simulator.common.config_parsing as cp
from colav_simulator import scenario_config
from colav_simulator.common import paths
from colav_simulator.core.collision import (
    VesselPose,
    continuous_footprint_collision,
    rectangular_footprint,
)
from colav_simulator.core.tracking.trackers import GodTracker
from colav_simulator.experiment.contracts import RunSpec
from colav_simulator.experiment.runner import ExperimentRunner, RunResult
from colav_simulator.experiment.session import SimulationSession
from colav_simulator.integrations import IntegrationRegistry
from colav_simulator.scenario_generator import ScenarioGenerator
from colav_simulator.simulator import Config as SimulatorConfig
from colav_simulator.simulator import Simulator

RECONSTRUCTION_LABEL = "kuwata_2011_behavior_compatible_reconstruction"
STANDARD_SCENARIOS = (
    "head_on",
    "crossing_give_way",
    "crossing_stand_on",
    "overtaking",
    "overtaken",
    "paper_ccta2023_multiship",
)


@dataclass(frozen=True)
class Acceptance:
    """Project acceptance thresholds, not Kuwata paper parameters."""

    minimum_hull_clearance_m: float = 1.0
    baseline_causal_clearance_m: float = 5.0
    significant_lateral_command_mps: float = 0.25
    stop_speed_mps: float = 0.3
    maximum_consecutive_feasible_stop_solves: int = 5
    maximum_course_tracking_error_rad: float = float(np.deg2rad(45.0))
    maximum_consecutive_course_tracking_violations: int = 10
    significant_heading_change_rad: float = float(np.deg2rad(2.5))
    maximum_active_turn_reversals: int = 20

    def to_dict(self) -> dict[str, Any]:
        return {
            "provenance": "project_acceptance",
            "minimum_hull_clearance_m": self.minimum_hull_clearance_m,
            "baseline_causal_clearance_m": self.baseline_causal_clearance_m,
            "significant_lateral_command_mps": self.significant_lateral_command_mps,
            "stop_speed_mps": self.stop_speed_mps,
            "maximum_consecutive_feasible_stop_solves": self.maximum_consecutive_feasible_stop_solves,
            "maximum_course_tracking_error_rad": self.maximum_course_tracking_error_rad,
            "maximum_consecutive_course_tracking_violations": (
                self.maximum_consecutive_course_tracking_violations
            ),
            "significant_heading_change_rad": self.significant_heading_change_rad,
            "maximum_active_turn_reversals": self.maximum_active_turn_reversals,
        }


def _wrap_angle(value: float) -> float:
    return float((value + np.pi) % (2.0 * np.pi) - np.pi)


def _pose(ship: dict[str, Any], info: dict[str, Any]) -> VesselPose:
    state = np.asarray(ship["state"], dtype=float)
    return VesselPose(
        north_m=float(state[0]),
        east_m=float(state[1]),
        heading_rad=float(state[2]),
        length_m=float(info["length"]),
        width_m=float(info["width"]),
    )


def _continuous_truth(result: RunResult) -> dict[str, Any]:
    frames = result.session.frames
    info = result.session.ship_info
    ownship_collisions: list[dict[str, Any]] = []
    global_collisions: list[dict[str, Any]] = []
    ownship_clearance = np.inf
    global_clearance = np.inf
    for index, (current, following) in enumerate(zip(frames, frames[1:], strict=False)):
        ship_keys = sorted(key for key in current if key.startswith("Ship") and current[key])
        for first_index, first_key in enumerate(ship_keys):
            for second_key in ship_keys[first_index + 1 :]:
                if not following.get(first_key) or not following.get(second_key):
                    continue
                first_start = _pose(current[first_key], info[first_key])
                first_end = _pose(following[first_key], info[first_key])
                second_start = _pose(current[second_key], info[second_key])
                second_end = _pose(following[second_key], info[second_key])
                interval = continuous_footprint_collision(
                    first_start,
                    first_end,
                    second_start,
                    second_end,
                    step_tolerance_m=result.session.simulator.config.ccd_step_tolerance_m,
                )
                clearance = rectangular_footprint(first_start).distance(
                    rectangular_footprint(second_start)
                )
                global_clearance = min(global_clearance, clearance)
                if first_key == "Ship0":
                    ownship_clearance = min(ownship_clearance, clearance)
                if interval is None:
                    continue
                evidence = {
                    "step": index,
                    "time_s": float(current[first_key]["timestamp"]),
                    "pair": [first_key, second_key],
                    "tau": [interval.tau_start, interval.tau_end],
                    "oracle_id": interval.oracle_id,
                }
                global_collisions.append(evidence)
                if first_key == "Ship0":
                    ownship_collisions.append(evidence)
    return {
        "collision_oracle": "continuous_footprint_collision",
        "grounding": {
            "grounded": any(event["type"] == "grounding" for event in result.session.events),
            "event_times_s": [
                float(event["sim_time"])
                for event in result.session.events
                if event["type"] == "grounding"
            ],
        },
        "ship0_vs_target": {
            "continuous_collision": bool(ownship_collisions),
            "collision_evidence": ownship_collisions,
            "minimum_sampled_hull_clearance_m": None
            if np.isinf(ownship_clearance)
            else float(ownship_clearance),
        },
        "global_all_vessel": {
            "continuous_collision": bool(global_collisions),
            "collision_evidence": global_collisions,
            "minimum_sampled_hull_clearance_m": None
            if np.isinf(global_clearance)
            else float(global_clearance),
        },
    }


def _rows(result: RunResult) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for frame in result.session.frames:
        ship = frame.get("Ship0")
        if not ship:
            continue
        state = np.asarray(ship["state"], dtype=float)
        colav = ship.get("colav", {})
        planner = colav.get("planner", {})
        vo = colav.get("vo", {})
        diagnostics = colav.get("diagnostics", {})
        selected = planner.get("selected_command", {})
        selected_course = selected.get("course_rad")
        selected_speed = selected.get("speed_mps")
        actual_velocity = np.asarray(
            [
                state[3] * np.cos(state[2]) - state[4] * np.sin(state[2]),
                state[3] * np.sin(state[2]) + state[4] * np.cos(state[2]),
            ]
        )
        selected_velocity = (
            np.asarray(
                [
                    selected_speed * np.cos(selected_course),
                    selected_speed * np.sin(selected_course),
                ]
            )
            if selected_course is not None and selected_speed is not None
            else actual_velocity
        )
        starboard = np.asarray([-np.sin(state[2]), np.cos(state[2])])
        track_metrics = vo.get("track_metrics", {})
        first_track = next(iter(track_metrics.values()), {})
        ownship_footprint = rectangular_footprint(_pose(ship, result.session.ship_info["Ship0"]))
        hull_clearances = [
            ownship_footprint.distance(
                rectangular_footprint(_pose(frame[key], result.session.ship_info[key]))
            )
            for key in sorted(result.session.ship_info)
            if key != "Ship0" and frame.get(key)
        ]
        details = diagnostics.get("details", {})
        output.append(
            {
                "time_s": float(ship["timestamp"]),
                "north_m": float(state[0]),
                "east_m": float(state[1]),
                "actual_heading_rad": float(state[2]),
                "actual_speed_mps": float(np.linalg.norm(actual_velocity)),
                "selected_heading_rad": selected_course,
                "selected_speed_mps": selected_speed,
                "body_starboard_command_mps": float(starboard @ selected_velocity),
                "course_tracking_error_rad": None
                if selected_course is None
                else abs(_wrap_angle(float(selected_course) - float(state[2]))),
                "speed_tracking_error_mps": None
                if selected_speed is None
                else abs(float(selected_speed) - float(np.linalg.norm(actual_velocity))),
                "status": diagnostics.get("status", planner.get("status")),
                "feasible": diagnostics.get("feasible", planner.get("feasible")),
                "fallback": diagnostics.get("fallback_used", False),
                "fallback_reason": details.get("fallback_reason", diagnostics.get("reason")),
                "solver_executed": planner.get("solver_executed", False),
                "solve_id": planner.get("solve_id", 0),
                "elapsed_ms": planner.get("elapsed_ms", 0.0),
                "dynamic_hazard_count": vo.get("dynamic_hazard_count", 0),
                "static_hazard_count": vo.get("static_hazard_count", 0),
                "active_rules": json.dumps(vo.get("active_rules", {}), sort_keys=True),
                "base_vo_count": vo.get("base_vo_count", 0),
                "colregs_v1_count": vo.get("colregs_v1_count", 0),
                "wvo_only_count": vo.get("wvo_only_count", 0),
                "feasible_candidate_count": vo.get("feasible_candidate_count", 0),
                "crossing_commitment_active": vo.get("crossing_commitment_active", False),
                "emergency_rule_relaxation": vo.get("emergency_rule_relaxation", False),
                "overtaking_state": vo.get("overtaking_state", "CLEAR"),
                "overtaking_target_id": vo.get("overtaking_target_id"),
                "overtaking_along_track_m": vo.get("overtaking_along_track_m"),
                "overtaking_cross_track_m": vo.get("overtaking_cross_track_m"),
                "overtaking_relative_speed_mps": vo.get("overtaking_relative_speed_mps"),
                "overtaking_progress_relaxed": vo.get("overtaking_progress_relaxed", False),
                "overtaking_release_count": vo.get("overtaking_release_count", 0),
                "overtaking_entry_tcpa_s": vo.get("overtaking_entry_tcpa_s"),
                "selected_in_base_vo": vo.get("selected_in_base_vo", False),
                "current_in_base_vo": vo.get("current_in_base_vo", False),
                "stand_on_hold_active": vo.get("stand_on_hold_active", False),
                "selected_in_colregs_v1": vo.get("selected_in_colregs_v1", False),
                "selected_ttc_s": vo.get("selected_ttc_s"),
                "minimum_feasible_ttc_s": vo.get("minimum_feasible_ttc_s"),
                "reference_velocity_error_mps": vo.get("reference_velocity_error_mps"),
                "tcpa_s": first_track.get("tcpa_s"),
                "dcpa_m": first_track.get("dcpa_m"),
                "rule_tcpa_s": first_track.get("rule_tcpa_s"),
                "rule_dcpa_m": first_track.get("rule_dcpa_m"),
                "center_distance_m": first_track.get("center_distance_m"),
                "true_hull_clearance_m": min(hull_clearances, default=None),
                "objective": planner.get("objective"),
            }
        )
    return output


def _maximum_run(values: list[bool]) -> int:
    longest = current = 0
    for value in values:
        current = current + 1 if value else 0
        longest = max(longest, current)
    return longest


def _turn_reversals(rows: list[dict[str, Any]], threshold_rad: float) -> int:
    headings = [
        float(row["selected_heading_rad"])
        for row in rows
        if row["selected_heading_rad"] is not None
    ]
    changes = [
        _wrap_angle(following - current)
        for current, following in zip(headings, headings[1:], strict=False)
    ]
    signs = [int(np.sign(change)) for change in changes if abs(change) >= threshold_rad]
    return sum(current != following for current, following in zip(signs, signs[1:], strict=False))


def _target_stern_plane_clearance(result: RunResult) -> float | None:
    target_key = next(
        (key for key in sorted(result.session.ship_info) if key != "Ship0"),
        None,
    )
    if target_key is None:
        return None
    closest_distance = np.inf
    closest_stern_clearance = None
    target_length = float(result.session.ship_info[target_key]["length"])
    for frame in result.session.frames:
        ownship = frame.get("Ship0")
        target = frame.get(target_key)
        if not ownship or not target:
            continue
        ownship_state = np.asarray(ownship["state"], dtype=float)
        target_state = np.asarray(target["state"], dtype=float)
        relative = ownship_state[:2] - target_state[:2]
        distance = float(np.linalg.norm(relative))
        if distance >= closest_distance:
            continue
        target_forward = np.array(
            [np.cos(target_state[2]), np.sin(target_state[2])]
        )
        along_target = float(relative @ target_forward)
        closest_distance = distance
        closest_stern_clearance = -0.5 * target_length - along_target
    return closest_stern_clearance


def summarize(result: RunResult, acceptance: Acceptance) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Build machine-readable safety, COLREG, controller, and solver evidence."""
    rows = _rows(result)
    solved = [row for row in rows if row["solver_executed"]]
    active = [row for row in solved if row["active_rules"] != "{}"]
    first_active = active[0] if active else None
    last_active = active[-1] if active else None
    stop_flags = [
        bool(
            row["feasible"]
            and row["feasible_candidate_count"] > 0
            and row["selected_speed_mps"] is not None
            and row["selected_speed_mps"] <= acceptance.stop_speed_mps
        )
        for row in solved
    ]
    course_tracking_flags = [
        bool(
            row["course_tracking_error_rad"] is not None
            and row["course_tracking_error_rad"] > acceptance.maximum_course_tracking_error_rad
        )
        for row in rows
    ]
    active_turn_reversals = _turn_reversals(active, acceptance.significant_heading_change_rad)
    elapsed = np.asarray([row["elapsed_ms"] for row in solved], dtype=float)
    truth = _continuous_truth(result)
    selected_safe = all(
        not row["selected_in_base_vo"] and not row["selected_in_colregs_v1"] for row in solved
    )
    finite = all(
        np.isfinite(value)
        for row in rows
        for value in (
            row["north_m"],
            row["east_m"],
            row["actual_heading_rad"],
            row["actual_speed_mps"],
        )
    )
    ownship_truth = truth["ship0_vs_target"]
    clearance = ownship_truth["minimum_sampled_hull_clearance_m"]
    acceptance_checks = {
        "continuous_collision_false": not ownship_truth["continuous_collision"],
        "grounding_false": not truth["grounding"]["grounded"],
        "minimum_hull_clearance": clearance is None
        or clearance > acceptance.minimum_hull_clearance_m,
        "selected_hard_constraint_safe": selected_safe,
        "no_fallback": not any(bool(row["fallback"]) for row in rows),
        "finite_state_outputs": finite,
        "no_persistent_feasible_stop": _maximum_run(stop_flags)
        <= acceptance.maximum_consecutive_feasible_stop_solves,
        "no_sustained_course_tracking_failure": _maximum_run(course_tracking_flags)
        <= acceptance.maximum_consecutive_course_tracking_violations,
        "no_excessive_active_oscillation": active_turn_reversals
        <= acceptance.maximum_active_turn_reversals,
        "planner_safe_and_execution_collision_free": selected_safe
        and not ownship_truth["continuous_collision"],
        "planning_under_one_second": not elapsed.size or float(np.max(elapsed)) < 1000.0,
    }
    return (
        {
            "reconstruction_label": RECONSTRUCTION_LABEL,
            "scenario_id": result.manifest.spec["scenario_id"],
            "algorithm_id": result.manifest.requested_algorithm,
            "truth": truth,
            "solver": {
                "solve_count": len(solved),
                "elapsed_ms_p50": float(np.percentile(elapsed, 50)) if elapsed.size else None,
                "elapsed_ms_p95": float(np.percentile(elapsed, 95)) if elapsed.size else None,
                "elapsed_ms_max": float(np.max(elapsed)) if elapsed.size else None,
                "selected_hard_constraint_safe": selected_safe,
                "fallback_count": sum(bool(row["fallback"]) for row in rows),
                "emergency_rule_relaxation_count": sum(
                    bool(row["emergency_rule_relaxation"]) for row in rows
                ),
                "maximum_consecutive_feasible_stop_solves": _maximum_run(stop_flags),
                "active_turn_reversals": active_turn_reversals,
            },
            "encounter": {
                "entry_time_s": None if first_active is None else first_active["time_s"],
                "first_action_time_s": None if first_active is None else first_active["time_s"],
                "first_action_body_starboard_mps": None
                if first_active is None
                else first_active["body_starboard_command_mps"],
                "last_active_time_s": None if last_active is None else last_active["time_s"],
                "rule_released_after_last_active": bool(
                    last_active
                    and any(
                        row["time_s"] > last_active["time_s"] and row["active_rules"] == "{}"
                        for row in solved
                    )
                ),
                "closest_approach_target_stern_plane_clearance_m": (
                    _target_stern_plane_clearance(result)
                ),
            },
            "controller": {
                "maximum_course_tracking_error_rad": max(
                    (
                        row["course_tracking_error_rad"]
                        for row in rows
                        if row["course_tracking_error_rad"] is not None
                    ),
                    default=None,
                ),
                "maximum_speed_tracking_error_mps": max(
                    (
                        row["speed_tracking_error_mps"]
                        for row in rows
                        if row["speed_tracking_error_mps"] is not None
                    ),
                    default=None,
                ),
                "maximum_consecutive_course_tracking_violations": _maximum_run(
                    course_tracking_flags
                ),
            },
            "finite_state_outputs": finite,
            "acceptance": acceptance.to_dict(),
            "acceptance_checks": acceptance_checks,
            "accepted": all(acceptance_checks.values()),
        },
        rows,
    )


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _plot(path: Path, result: RunResult, rows: list[dict[str, Any]]) -> None:
    time_s = np.asarray([row["time_s"] for row in rows])
    figure, axes = plt.subplots(3, 2, figsize=(14, 13), constrained_layout=True)
    for ship_key in sorted(result.session.ship_info):
        north = [frame[ship_key]["state"][0] for frame in result.session.frames if frame.get(ship_key)]
        east = [frame[ship_key]["state"][1] for frame in result.session.frames if frame.get(ship_key)]
        axes[0, 0].plot(east, north, label=ship_key)
    axes[0, 0].set(title="North-East trajectories", xlabel="East [m]", ylabel="North [m]")
    axes[0, 0].axis("equal")
    axes[0, 0].legend()

    axes[0, 1].plot(time_s, [row["actual_heading_rad"] for row in rows], label="actual")
    axes[0, 1].plot(time_s, [row["selected_heading_rad"] for row in rows], label="VO reference")
    axes[0, 1].set(title="Heading response", xlabel="Time [s]", ylabel="Heading [rad]")
    axes[0, 1].legend()

    axes[1, 0].plot(time_s, [row["actual_speed_mps"] for row in rows], label="actual")
    axes[1, 0].plot(time_s, [row["selected_speed_mps"] for row in rows], label="VO reference")
    axes[1, 0].set(title="Speed response", xlabel="Time [s]", ylabel="Speed [m/s]")
    axes[1, 0].legend()

    axes[1, 1].plot(time_s, [row["center_distance_m"] for row in rows], label="center distance")
    axes[1, 1].plot(
        time_s,
        [row["true_hull_clearance_m"] for row in rows],
        label="true hull clearance",
    )
    axes[1, 1].plot(time_s, [row["dcpa_m"] for row in rows], label="DCPA")
    axes[1, 1].plot(time_s, [row["tcpa_s"] for row in rows], label="TCPA")
    axes[1, 1].plot(time_s, [row["selected_ttc_s"] for row in rows], label="selected TTC")
    axes[1, 1].set(title="Encounter geometry", xlabel="Time [s]")
    axes[1, 1].legend()

    axes[2, 0].plot(time_s, [row["base_vo_count"] for row in rows], label="base VO")
    axes[2, 0].plot(time_s, [row["colregs_v1_count"] for row in rows], label="COLREG V1")
    axes[2, 0].plot(time_s, [row["wvo_only_count"] for row in rows], label="WVO-only")
    axes[2, 0].plot(time_s, [row["feasible_candidate_count"] for row in rows], label="feasible")
    axes[2, 0].set(title="Velocity-grid constraints", xlabel="Time [s]", ylabel="Candidates")
    axes[2, 0].legend()

    status = [1 if row["status"] == "SUCCESS" else 0 for row in rows]
    active = [1 if row["active_rules"] != "{}" else 0 for row in rows]
    fallback = [1 if row["fallback"] else 0 for row in rows]
    axes[2, 1].step(time_s, status, label="SUCCESS")
    axes[2, 1].step(time_s, active, label="rule active")
    axes[2, 1].step(time_s, fallback, label="fallback")
    axes[2, 1].set(title="Planner and rule timeline", xlabel="Time [s]", yticks=(0, 1))
    axes[2, 1].legend()
    figure.savefig(path, dpi=160)
    plt.close(figure)


def write_artifacts(
    output_dir: Path,
    result: RunResult,
    acceptance: Acceptance,
) -> dict[str, Any]:
    """Write one run's JSON, CSV, and diagnostic plot."""
    output_dir.mkdir(parents=True, exist_ok=True)
    summary, rows = summarize(result, acceptance)
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    _write_csv(output_dir / "timeline.csv", rows)
    _plot(output_dir / "closed_loop_diagnostics.png", result, rows)
    return summary


def _simulator_config() -> SimulatorConfig:
    config = SimulatorConfig.from_file(paths.simulator_config)
    config.verbose = False
    config.visualizer.show_liveplot = False
    config.visualizer.show_results = False
    config.visualizer.save_result_figures = False
    config.visualizer.save_liveplot_animation = False
    config.visualizer.matplotlib_backend = "Agg"
    return config


def _generated_head_on(t_end: float) -> tuple[Any, Any]:
    scenario_path = Path.cwd() / "scenarios" / "head_on.yaml"
    config = cp.extract(scenario_config.ScenarioConfig, scenario_path, paths.scenario_schema)
    config.t_end = t_end
    episodes, enc = ScenarioGenerator(seed=0).generate(
        config=config,
        n_episodes=1,
        show_plots=False,
        save_scenario=False,
    )
    return episodes[0], enc


def _project_fixture_session(kind: str, algorithm_id: str) -> SimulationSession:
    if kind == "twenty_targets":
        t_end = 30.0
    elif kind == "head_on_both_vo":
        t_end = 300.0
    else:
        t_end = 80.0
    episode, enc = _generated_head_on(t_end)
    ships = episode["ship_list"]
    if kind in {"local_island", "blocked"}:
        north, east, _speed, course = ships[0].csog_state
        if kind == "blocked":
            added_land = box(east - 50.0, north - 50.0, east + 50.0, north + 50.0)
        else:
            center_north = north + 250.0 * np.cos(course) - 20.0 * np.sin(course)
            center_east = east + 250.0 * np.sin(course) + 20.0 * np.cos(course)
            added_land = box(
                center_east - 25.0,
                center_north - 25.0,
                center_east + 25.0,
                center_north + 25.0,
            )
        enc.land.geometry = enc.land.geometry.union(added_land)
    elif kind == "twenty_targets":
        ownship, template = ships
        origin = ownship.csog_state[0:2]
        targets = []
        for index in range(20):
            angle = 2.0 * np.pi * index / 20.0
            tangent = angle + np.pi / 2.0
            position = origin + 300.0 * np.array([np.cos(angle), np.sin(angle)])
            goal = position + 500.0 * np.array([np.cos(tangent), np.sin(tangent)])
            target = copy.deepcopy(template)
            target.set_id(index + 1)
            target.set_initial_state(np.array([position[0], position[1], 3.0, tangent]))
            target.set_goal_state(np.array([goal[0], goal[1], 3.0, tangent]))
            target.set_nominal_plan(np.column_stack((position, goal)), np.array([3.0, 3.0]))
            targets.append(target)
        ships = [ownship, *targets]
    algorithm_config = (
        {
            "w_ttc": 100.0,
            "velocity_uncertainty_vertices_mps": [
                [-1.0, -1.0],
                [-1.0, 1.0],
                [1.0, 1.0],
                [1.0, -1.0],
            ],
        }
        if algorithm_id == "vo" and kind == "local_island"
        else None
    )
    algorithm = IntegrationRegistry().build_algorithm(algorithm_id, algorithm_config)
    colav_systems = [(0, algorithm)] if algorithm is not None else None
    trackers = [(0, GodTracker())]
    if kind == "head_on_both_vo" and algorithm_id == "vo":
        dual_config = {
            "t_max": 60.0,
            "d_min": 20.0,
            "w_ttc": 1000.0,
            "wvo_ttc_scale": 1.0,
            "velocity_uncertainty_vertices_mps": [
                [-2.0, -2.0],
                [-2.0, 2.0],
                [2.0, 2.0],
                [2.0, -2.0],
            ],
        }
        colav_systems = [
            (0, IntegrationRegistry().build_algorithm("vo", dual_config)),
            (1, IntegrationRegistry().build_algorithm("vo", dual_config)),
        ]
        trackers.append((1, GodTracker()))
    simulator_config = _simulator_config()
    if kind == "head_on_both_vo":
        simulator_config.tracking_from_ownship_only = False
    return SimulationSession(
        simulator=Simulator(config=simulator_config),
        ship_list=ships,
        config=episode["config"],
        enc=enc,
        disturbance=episode["disturbance"],
        colav_systems=colav_systems,
        trackers=trackers,
        seed=0,
        terminate_on_collision_or_grounding=False,
    )


def _dual_head_on_metrics(session: SimulationSession) -> dict[str, Any]:
    vessels: dict[str, Any] = {}
    for ship_key in ("Ship0", "Ship1"):
        first_state = np.asarray(session.frames[0][ship_key]["state"], dtype=float)
        initial_position = first_state[:2]
        initial_starboard = np.array([-np.sin(first_state[2]), np.cos(first_state[2])])
        active_rows: list[tuple[dict[str, Any], dict[str, Any]]] = []
        for frame in session.frames:
            ship = frame.get(ship_key)
            if not ship:
                continue
            planner = ship.get("colav", {}).get("planner", {})
            vo = ship.get("colav", {}).get("vo", {})
            if planner.get("solver_executed") and "HO" in json.dumps(vo.get("active_rules", {})):
                active_rows.append((ship, planner))
        first_command = active_rows[0][1].get("selected_command", {}) if active_rows else {}
        first_course = first_command.get("course_rad")
        first_speed = first_command.get("speed_mps")
        first_ship = active_rows[0][0] if active_rows else None
        first_starboard_command = None
        if first_ship is not None and first_course is not None and first_speed is not None:
            state = np.asarray(first_ship["state"], dtype=float)
            starboard = np.array([-np.sin(state[2]), np.cos(state[2])])
            velocity = float(first_speed) * np.array(
                [np.cos(float(first_course)), np.sin(float(first_course))]
            )
            first_starboard_command = float(starboard @ velocity)
        last_active_time = float(active_rows[-1][0]["timestamp"]) if active_rows else None
        released = bool(
            last_active_time is not None
            and any(
                float(frame[ship_key]["timestamp"]) > last_active_time
                and "HO"
                not in json.dumps(
                    frame[ship_key].get("colav", {}).get("vo", {}).get("active_rules", {})
                )
                for frame in session.frames
                if frame.get(ship_key)
                and frame[ship_key].get("colav", {}).get("planner", {}).get("solver_executed")
            )
        )
        excursion = max(
            float(
                initial_starboard
                @ (np.asarray(frame[ship_key]["state"], dtype=float)[:2] - initial_position)
            )
            for frame in session.frames
            if frame.get(ship_key)
        )
        vessels[ship_key] = {
            "ho_entry_time_s": (
                None if first_ship is None else float(first_ship["timestamp"])
            ),
            "first_command_body_starboard_mps": first_starboard_command,
            "maximum_actual_body_starboard_excursion_m": excursion,
            "rule_released": released,
        }
    checks = {
        "both_ho_rules_activated": all(
            vessel["ho_entry_time_s"] is not None for vessel in vessels.values()
        ),
        "both_first_commands_starboard": all(
            vessel["first_command_body_starboard_mps"] is not None
            and vessel["first_command_body_starboard_mps"] > 0.25
            for vessel in vessels.values()
        ),
        "both_actual_trajectories_move_starboard": all(
            vessel["maximum_actual_body_starboard_excursion_m"] > 1.0
            for vessel in vessels.values()
        ),
        "both_rules_released": all(vessel["rule_released"] for vessel in vessels.values()),
    }
    return {"vessels": vessels, "acceptance_checks": checks, "accepted": all(checks.values())}


def _session_result(session: SimulationSession, scenario_id: str, algorithm_id: str) -> Any:
    return SimpleNamespace(
        session=session,
        manifest=SimpleNamespace(
            spec={"scenario_id": scenario_id},
            requested_algorithm=algorithm_id,
        ),
    )


def main() -> None:
    """Run nominal/VO scenario pairs and write a capability matrix."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=Path("runs/kuwata_vo_validation"))
    parser.add_argument("--scenario", action="append", choices=STANDARD_SCENARIOS)
    parser.add_argument("--include-project-fixtures", action="store_true")
    args = parser.parse_args()
    acceptance = Acceptance()
    runner = ExperimentRunner(Path.cwd())
    scenarios = tuple(args.scenario or STANDARD_SCENARIOS)
    matrix: list[dict[str, Any]] = []
    for scenario_id in scenarios:
        pair: dict[str, Any] = {"scenario_id": scenario_id}
        for algorithm_id in ("nominal", "vo"):
            result = runner.run(
                RunSpec(
                    scenario_id=scenario_id,
                    algorithm_id=algorithm_id,
                    tracker_id="god",
                    seed=0,
                    terminate_on_collision_or_grounding=False,
                    strict_no_fallback=algorithm_id == "vo",
                    output_root=str(args.output_root / "raw" / scenario_id / algorithm_id),
                )
            )
            pair[algorithm_id] = write_artifacts(
                args.output_root / scenario_id / algorithm_id,
                result,
                acceptance,
            )
        nominal_truth = pair["nominal"]["truth"]
        nominal_clearance = nominal_truth["ship0_vs_target"]["minimum_sampled_hull_clearance_m"]
        pair["causal_baseline_confirmed"] = bool(
            nominal_truth["ship0_vs_target"]["continuous_collision"]
            or nominal_truth["grounding"]["grounded"]
            or (
                nominal_clearance is not None
                and nominal_clearance < acceptance.baseline_causal_clearance_m
            )
        )
        matrix.append(pair)
    if args.include_project_fixtures:
        for fixture_id in ("local_island", "twenty_targets"):
            pair = {
                "scenario_id": fixture_id,
                "scenario_role": (
                    "local_static_and_dynamic_avoidance"
                    if fixture_id == "local_island"
                    else "twenty_target_performance"
                ),
            }
            if fixture_id == "local_island":
                pair["algorithm_profile"] = {
                    "w_ttc": 100.0,
                    "velocity_uncertainty_bound_mps": 1.0,
                    "provenance": "inferred_reconstruction",
                }
            for algorithm_id in ("nominal", "vo"):
                session = _project_fixture_session(fixture_id, algorithm_id)
                session.run_to_completion()
                result = _session_result(session, fixture_id, algorithm_id)
                pair[algorithm_id] = write_artifacts(
                    args.output_root / fixture_id / algorithm_id,
                    result,
                    acceptance,
                )
            nominal_truth = pair["nominal"]["truth"]
            nominal_clearance = nominal_truth["ship0_vs_target"]["minimum_sampled_hull_clearance_m"]
            pair["causal_baseline_confirmed"] = bool(
                nominal_truth["ship0_vs_target"]["continuous_collision"]
                or nominal_truth["grounding"]["grounded"]
                or (
                    nominal_clearance is not None
                    and nominal_clearance < acceptance.baseline_causal_clearance_m
                )
            )
            matrix.append(pair)
        both_vo = _project_fixture_session("head_on_both_vo", "vo")
        both_vo.run_to_completion()
        both_vo_summary = write_artifacts(
            args.output_root / "head_on_both_vo" / "vo",
            _session_result(both_vo, "head_on_both_vo", "vo"),
            acceptance,
        )
        dual_metrics = _dual_head_on_metrics(both_vo)
        matrix.append(
            {
                "scenario_id": "head_on_both_vo",
                "scenario_role": "dual_vessel_colreg_execution",
                "causal_baseline_reference": "head_on/nominal",
                "algorithm_profile": {
                    "w_ttc": 1000.0,
                    "wvo_ttc_scale": 1.0,
                    "velocity_uncertainty_bound_mps": 2.0,
                    "provenance": "inferred_reconstruction",
                },
                "vo": both_vo_summary,
                "dual_vessel_colreg": dual_metrics,
                "accepted": bool(both_vo_summary["accepted"] and dual_metrics["accepted"]),
            }
        )
        blocked = _project_fixture_session("blocked", "vo")
        blocked.step_once()
        matrix.append(
            {
                "scenario_id": "blocked",
                "scenario_role": "expected_infeasible_static_blockage",
                "vo": write_artifacts(
                    args.output_root / "blocked" / "vo",
                    _session_result(blocked, "blocked", "vo"),
                    acceptance,
                ),
            }
        )
    (args.output_root / "capability_matrix.json").write_text(
        json.dumps(
            {
                "reconstruction_label": RECONSTRUCTION_LABEL,
                "acceptance": acceptance.to_dict(),
                "scenarios": matrix,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
