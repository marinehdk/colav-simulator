"""Anticipatory planning must not turn all future encounters into current actions."""

from dataclasses import replace

import numpy as np

from colav_simulator.core.colav.custom_mpc_adapter import FactoryContext, PlannerInput, TrackedObstacle
from colav_simulator.core.colav.encounter_lifecycle import RiskPhase
from colav_simulator.core.colav.horizon_encounter_plan import (
    HorizonEncounterPlanRequest,
    HorizonTargetIntent,
    TargetPrediction,
    compile_horizon_encounter_plan,
)
from colav_simulator.core.colav.threat_management import ThreatManagementCoordinator
from colav_simulator.core.tracking.trackers import TrackKey
from colav_simulator.integrations.mid_mpc_ipopt import create


def _input(time_s: float) -> PlannerInput:
    return PlannerInput(
        sim_time_s=time_s,
        dt_sim_s=0.1,
        waypoints_enu_m=np.array([[0.0, 10000.0], [0.0, 0.0]]),
        speed_plan_mps=np.array([6.0, 6.0]),
        ownship_state=np.array([6 * time_s, 0.0, 0.0, 6.0, 0.0, 0.0]),
        tracks=tuple(
            TrackedObstacle(
                target_id=i,
                generation=1,
                state_enu=np.array([distance - 6 * time_s, 0.0, -6.0, 0.0]),
                covariance=np.zeros((4, 4)),
                length_m=30.0,
                width_m=7.0,
                observed_at_s=time_s,
                generated_at_s=time_s,
                age_s=0.0,
                status="updated",
                source="god",
            )
            for i, distance in [(1, 1000.0), (2, 6500.0)]
        ),
        enc=None,
        goal_state=None,
        disturbance=None,
        algorithm_seed=0,
        ownship_model="KinematicCSOG",
        ownship_controller="PassThroughCS",
    )


def test_future_contact_is_planned_without_immediate_commitment() -> None:
    coordinator = ThreatManagementCoordinator()
    adapter = create(
        context=FactoryContext(
            requested_algorithm="mid_mpc_ipopt",
            algorithm_seed=0,
            scenario_id="anticipation",
            tracker_id="god",
            threat_management_coordinator=coordinator,
        )
    )
    facade = adapter._solve.__self__
    for index, time_s in enumerate([0.0, 10.0]):
        cycle = facade._encounter_cycle(_input(time_s), route_bearing_rad=0.0, planned_speed_mps=6.0)
        cycle = replace(cycle, sequence=index)
        snapshot = coordinator.cycle(cycle)
    by_id = {d.key.target_id: d for d in snapshot.lifecycle_snapshot.targets}
    assert by_id[1].risk is RiskPhase.ACTIVE
    assert by_id[2].risk is RiskPhase.CANDIDATE
    assert snapshot.lifecycle_snapshot.primary_target.target_id == 1


def test_horizon_has_a_later_action_and_a_nominal_prefix() -> None:
    times = np.arange(81) * 5.0
    key = TrackKey(2, 1)
    prediction = TargetPrediction(
        key=key,
        reference_time_s=0.0,
        times_s=times,
        north_m=3000.0 - 6 * times,
        east_m=np.zeros(81),
        velocity_ne_mps=(-6.0, 0.0),
        position_uncertainty_m=np.zeros(81),
    )
    plan = compile_horizon_encounter_plan(
        HorizonEncounterPlanRequest(
            reference_time_s=0.0,
            times_s=times,
            own_position_ne_m=(0.0, 0.0),
            mission_route_anchor_ne_m=(0.0, 0.0),
            own_heading_rad=0.0,
            own_speed_mps=6.0,
            mission_route_bearing_rad=0.0,
            avoidance_corridor_bearing_rad=0.3,
            rot_max_rad_s=0.05,
            heading_window_rad=0.8,
            targets=(
                HorizonTargetIntent(
                    key=key,
                    required_course_change_rad=0.3,
                    recovery_clearance_m=200.0,
                    action_achieved=False,
                    route_recovery_allowed=False,
                    prediction=prediction,
                    action_start_s=100.0,
                    corridor_bearing_rad=0.3,
                    passing_side=1,
                ),
            ),
        )
    )
    assert all(p.value == "MISSION" for p in plan.phases[:20])
    assert plan.phases[20].value == "ALTER"
    assert plan.corridor_reference_rad[20] == 0.3


def test_mpc_optimizes_future_turns_while_current_command_remains_nominal() -> None:
    coordinator = ThreatManagementCoordinator()
    adapter = create(
        context=FactoryContext(
            requested_algorithm="mid_mpc_ipopt",
            algorithm_seed=0,
            scenario_id="anticipation",
            tracker_id="god",
            threat_management_coordinator=coordinator,
        )
    )
    data = _input(0.0)
    data = replace(data, tracks=(replace(data.tracks[0], state_enu=np.array([3000.0, 0.0, -6.0, 0.0])), data.tracks[1]))
    solution = adapter._solve.__self__.solve(data)
    assert solution.feasible
    assert abs(solution.control_reference[2, 0]) < np.deg2rad(3.0)
    assert np.max(solution.predicted_trajectory[2]) > np.deg2rad(10.0)
    decisions = coordinator.last_snapshot.lifecycle_snapshot
    assert decisions.primary_target is None
    assert all(d.risk is RiskPhase.CANDIDATE for d in decisions.targets)
    assert {k.target_id for k in coordinator.last_snapshot.schedule.next_threats} == {1, 2}


def test_imminent_contact_preempts_a_future_schedule() -> None:
    coordinator = ThreatManagementCoordinator()
    adapter = create(
        context=FactoryContext(
            requested_algorithm="mid_mpc_ipopt",
            algorithm_seed=0,
            scenario_id="anticipation",
            tracker_id="god",
            threat_management_coordinator=coordinator,
        )
    )
    facade = adapter._solve.__self__
    data = _input(0.0)
    data = replace(data, tracks=(replace(data.tracks[0], state_enu=np.array([3000.0, 0.0, -6.0, 0.0])), data.tracks[1]))
    first = coordinator.cycle(facade._encounter_cycle(data, route_bearing_rad=0.0, planned_speed_mps=6.0))
    assert first.lifecycle_snapshot.primary_target is None
    data = _input(10.0)
    data = replace(
        data,
        tracks=(
            replace(data.tracks[0], state_enu=np.array([2940.0, 0.0, -6.0, 0.0])),
            replace(data.tracks[1], state_enu=np.array([200.0, 0.0, -6.0, 0.0])),
        ),
    )
    cycle = replace(facade._encounter_cycle(data, route_bearing_rad=0.0, planned_speed_mps=6.0), sequence=1)
    urgent = coordinator.cycle(cycle)
    assert urgent.lifecycle_snapshot.primary_target.target_id == 2
    target = next(d for d in urgent.lifecycle_snapshot.targets if d.key.target_id == 2)
    assert target.risk is RiskPhase.ACTIVE
    assert target.planned_action_at_s <= 10.0
