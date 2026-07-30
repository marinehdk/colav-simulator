from __future__ import annotations

import copy
from pathlib import Path

import numpy as np
from shapely.geometry import box

import colav_simulator.common.config_parsing as cp
from colav_simulator import scenario_config
from colav_simulator.common import paths
from colav_simulator.core.tracking.trackers import GodTracker
from colav_simulator.experiment.session import SimulationSession
from colav_simulator.integrations import IntegrationRegistry
from colav_simulator.scenario_generator import ScenarioGenerator
from colav_simulator.simulator import Config as SimulatorConfig
from colav_simulator.simulator import Simulator


def _session_with_added_land(
    *,
    algorithm_id: str,
    blocked: bool,
) -> SimulationSession:
    scenario_path = Path.cwd() / "scenarios" / "head_on.yaml"
    config = cp.extract(scenario_config.ScenarioConfig, scenario_path, paths.scenario_schema)
    config.t_end = 80.0
    episodes, enc = ScenarioGenerator(seed=0).generate(
        config=config,
        n_episodes=1,
        show_plots=False,
        save_scenario=False,
    )
    episode = episodes[0]
    ownship = episode["ship_list"][0]
    north, east, _speed, course = ownship.csog_state
    if blocked:
        half_extent = 50.0
        added_land = box(
            east - half_extent,
            north - half_extent,
            east + half_extent,
            north + half_extent,
        )
    else:
        center_north = north + 250.0 * np.cos(course)
        center_east = east + 250.0 * np.sin(course)
        center_north += 20.0 * -np.sin(course)
        center_east += 20.0 * np.cos(course)
        added_land = box(
            center_east - 25.0,
            center_north - 25.0,
            center_east + 25.0,
            center_north + 25.0,
        )
    enc.land.geometry = enc.land.geometry.union(added_land)

    simulator_config = SimulatorConfig.from_file(paths.simulator_config)
    simulator_config.verbose = False
    simulator_config.visualizer.show_liveplot = False
    simulator_config.visualizer.show_results = False
    simulator_config.visualizer.save_result_figures = False
    simulator_config.visualizer.save_liveplot_animation = False
    simulator_config.visualizer.matplotlib_backend = "Agg"
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
        if algorithm_id == "vo" and not blocked
        else None
    )
    algorithm = IntegrationRegistry().build_algorithm(algorithm_id, algorithm_config)
    return SimulationSession(
        simulator=Simulator(config=simulator_config),
        ship_list=episode["ship_list"],
        config=episode["config"],
        enc=enc,
        disturbance=episode["disturbance"],
        colav_systems=[(0, algorithm)] if algorithm is not None else None,
        trackers=[(0, GodTracker())],
        seed=0,
        terminate_on_collision_or_grounding=False,
    )


def test_dynamic_target_and_local_island_are_avoided_in_same_closed_loop() -> None:
    nominal = _session_with_added_land(algorithm_id="nominal", blocked=False)
    candidate = _session_with_added_land(algorithm_id="vo", blocked=False)
    nominal.run_to_completion()
    candidate.run_to_completion()

    assert any(event["type"] == "grounding" for event in nominal.events)
    assert not any(event["type"] == "grounding" for event in candidate.events)
    solved = [
        frame["Ship0"]["colav"]["vo"]
        for frame in candidate.frames
        if frame["Ship0"]["colav"]["planner"]["solver_executed"]
    ]
    assert any(item["dynamic_hazard_count"] > 0 for item in solved)
    assert any(item["static_hazard_count"] > 0 for item in solved)
    assert any(item["base_vo_count"] > 0 for item in solved)
    assert all(not item["selected_in_base_vo"] for item in solved)


def test_static_blockage_reports_infeasible_stop_fallback() -> None:
    session = _session_with_added_land(algorithm_id="vo", blocked=True)

    session.step_once()

    colav = session.frames[0]["Ship0"]["colav"]
    diagnostics = colav["diagnostics"]
    assert diagnostics["status"] == "INFEASIBLE"
    assert diagnostics["fallback_used"]
    assert diagnostics["details"]["fallback"] == "stop_nonpaper_wrapper"
    assert diagnostics["details"]["fallback_reason"] == "all_velocity_grid_candidates_inadmissible"
    assert colav["planner"]["selected_command"]["speed_mps"] == 0.0


def test_twenty_dynamic_targets_run_through_tracker_vo_controller_and_ship_model() -> None:
    scenario_path = Path.cwd() / "scenarios" / "head_on.yaml"
    config = cp.extract(scenario_config.ScenarioConfig, scenario_path, paths.scenario_schema)
    config.t_end = 30.0
    episodes, enc = ScenarioGenerator(seed=0).generate(
        config=config,
        n_episodes=1,
        show_plots=False,
        save_scenario=False,
    )
    episode = episodes[0]
    ownship, template = episode["ship_list"]
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

    simulator_config = SimulatorConfig.from_file(paths.simulator_config)
    simulator_config.verbose = False
    simulator_config.visualizer.show_liveplot = False
    simulator_config.visualizer.show_results = False
    simulator_config.visualizer.save_result_figures = False
    simulator_config.visualizer.save_liveplot_animation = False
    simulator_config.visualizer.matplotlib_backend = "Agg"
    session = SimulationSession(
        simulator=Simulator(config=simulator_config),
        ship_list=ships,
        config=episode["config"],
        enc=enc,
        disturbance=episode["disturbance"],
        colav_systems=[(0, IntegrationRegistry().build_algorithm("vo"))],
        trackers=[(0, GodTracker())],
        seed=0,
        terminate_on_collision_or_grounding=False,
    )

    session.run_to_completion()

    solved = [
        frame["Ship0"]["colav"]
        for frame in session.frames
        if frame["Ship0"]["colav"]["planner"]["solver_executed"]
    ]
    assert solved
    assert all(item["vo"]["dynamic_hazard_count"] == 20 for item in solved)
    assert all(item["planner"]["elapsed_ms"] < 1000.0 for item in solved)
    assert all(np.isfinite(frame["Ship0"]["state"]).all() for frame in session.frames)
    assert any(
        abs(frame["Ship0"]["state"][2] - session.frames[0]["Ship0"]["state"][2]) > 1e-3
        for frame in session.frames[1:]
    )
