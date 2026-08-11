import math
from dataclasses import replace

import numpy as np
import pytest

from colav_simulator.core.colav.custom_mpc_adapter import PlannerInput, TrackedObstacle
from colav_simulator.core.colav.encounter_lifecycle import (
    EncounterCycle,
    EncounterLifecycle,
    LifecycleError,
    LifecycleFailure,
    Maneuverability,
    ObservationHealth,
    OwnshipObservation,
    PassingSide,
    PlannerOddProfile,
    TargetObservation,
)
from colav_simulator.core.colav.mid_mpc_assembler import (
    MidMpcAssemblyConfig,
    assemble_mid_mpc_problem,
)
from colav_simulator.core.tracking.trackers import TrackKey


def test_assembler_maps_persistent_lifecycle_commitment_without_business_state() -> None:
    planner_input = _planner_input()
    lifecycle = EncounterLifecycle()
    lifecycle.step(_cycle(planner_input, sequence=0, sim_time_s=0.0))
    snapshot = lifecycle.step(_cycle(planner_input, sequence=1, sim_time_s=5.0))
    assembly = assemble_mid_mpc_problem(
        planner_input,
        snapshot,
        route_bearing_rad=0.0,
        planned_speed_mps=7.0,
        config=MidMpcAssemblyConfig(),
    )

    assert len(assembly.problem.targets) == 1
    assert assembly.problem.lateral_active is True
    assert assembly.problem.preferred_side == 1
    assert assembly.problem.min_alteration_rad == snapshot.targets[0].required_course_change_rad
    assert assembly.problem.row_schedule.direction_hard_from_k == 0
    assert assembly.problem.speed_bounds_mps == snapshot.directive.speed_bounds_mps
    assert assembly.selected_target_keys == (TrackKey(1, 1),)


def test_assembler_retains_committed_corridor_after_first_alteration_is_achieved() -> None:
    planner_input = _planner_input()
    lifecycle = EncounterLifecycle()
    lifecycle.step(_cycle(planner_input, sequence=0, sim_time_s=0.0))
    committed = lifecycle.step(_cycle(planner_input, sequence=1, sim_time_s=5.0))
    required_change = committed.targets[0].required_course_change_rad
    achieved_cycle = _cycle(planner_input, sequence=2, sim_time_s=10.0)
    achieved_cycle = replace(
        achieved_cycle,
        ownship=replace(
            achieved_cycle.ownship,
            velocity_ne_mps=np.array([7.0 * math.cos(required_change), 7.0 * math.sin(required_change)]),
            heading_rad=required_change,
        ),
    )
    snapshot = lifecycle.step(achieved_cycle)

    assembly = assemble_mid_mpc_problem(
        planner_input,
        snapshot,
        route_bearing_rad=0.0,
        planned_speed_mps=7.0,
        config=MidMpcAssemblyConfig(),
    )

    assert snapshot.targets[0].action_achieved is True
    assert assembly.problem.lateral_active is False
    assert assembly.problem.route_bearing_rad == required_change


def test_assembler_rejects_direction_facts_the_frozen_core_cannot_represent() -> None:
    planner_input = _planner_input()
    lifecycle = EncounterLifecycle()
    lifecycle.step(_cycle(planner_input, sequence=0, sim_time_s=0.0))
    snapshot = lifecycle.step(_cycle(planner_input, sequence=1, sim_time_s=5.0))
    inconsistent = replace(
        snapshot,
        directive=replace(snapshot.directive, passing_side=PassingSide.NONE),
    )

    with pytest.raises(LifecycleError) as error:
        assemble_mid_mpc_problem(
            planner_input,
            inconsistent,
            route_bearing_rad=0.0,
            planned_speed_mps=7.0,
            config=MidMpcAssemblyConfig(),
        )

    assert error.value.failure is LifecycleFailure.CORE_CAPABILITY_MISMATCH


def test_assembler_maps_stop_directive_to_zero_speed_reference() -> None:
    planner_input = _planner_input()
    lifecycle = EncounterLifecycle()
    lifecycle.step(_cycle(planner_input, sequence=0, sim_time_s=0.0))
    snapshot = lifecycle.step(_cycle(planner_input, sequence=1, sim_time_s=5.0))
    stopped = replace(
        snapshot,
        directive=replace(
            snapshot.directive,
            passing_side=PassingSide.NONE,
            minimum_course_change_rad=0.0,
            speed_bounds_mps=(0.0, 7.0),
            stop_required=True,
        ),
    )

    assembly = assemble_mid_mpc_problem(
        planner_input,
        stopped,
        route_bearing_rad=0.0,
        planned_speed_mps=7.0,
        config=MidMpcAssemblyConfig(),
    )

    assert assembly.problem.planned_speed_mps == 0.0
    assert assembly.problem.speed_bounds_mps == (0.0, 7.0)
    assert assembly.problem.lateral_active is False


def _planner_input() -> PlannerInput:
    return PlannerInput(
        sim_time_s=5.0,
        dt_sim_s=0.5,
        waypoints_enu_m=np.array([[0.0, 5000.0], [0.0, 0.0]]),
        speed_plan_mps=np.array([7.0, 7.0]),
        ownship_state=np.array([0.0, 0.0, 0.0, 7.0, 0.0, 0.0]),
        tracks=(
            TrackedObstacle(
                target_id=1,
                state_enu=np.array([1000.0, 0.0, -7.0, 0.0]),
                covariance=np.zeros((4, 4)),
                length_m=30.0,
                width_m=7.0,
                observed_at_s=5.0,
                age_s=0.0,
                generation=1,
                status="updated",
                source="god",
                generated_at_s=5.0,
            ),
        ),
        enc=None,
        goal_state=None,
        disturbance=None,
        algorithm_seed=0,
        ownship_length_m=15.0,
        ownship_width_m=4.0,
    )


def _cycle(planner_input: PlannerInput, *, sequence: int, sim_time_s: float) -> EncounterCycle:
    track = planner_input.tracks[0]
    return EncounterCycle(
        epoch="test",
        sequence=sequence,
        sim_time_s=sim_time_s,
        ownship=OwnshipObservation(
            position_ne_m=planner_input.ownship_state[:2],
            velocity_ne_mps=np.array([7.0, 0.0]),
            heading_rad=0.0,
            length_m=15.0,
            width_m=4.0,
            maneuverability=Maneuverability(math.radians(3.0), 0.3, (0.0, 8.0)),
        ),
        targets=(
            TargetObservation(
                key=TrackKey(1, 1),
                state_enu=track.state_enu,
                covariance=track.covariance,
                length_m=track.length_m,
                width_m=track.width_m,
                observed_at_s=sim_time_s,
                generated_at_s=sim_time_s,
                health=ObservationHealth.UPDATED,
                source="god",
            ),
        ),
        route_bearing_rad=0.0,
        planned_speed_mps=7.0,
        profile=PlannerOddProfile(),
    )
