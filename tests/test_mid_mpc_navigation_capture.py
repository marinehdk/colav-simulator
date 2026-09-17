"""Arrival-circle entry cannot stand in for native mission-leg recovery."""
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
from test_mid_mpc_plan_acceptance import _request
from test_mid_mpc_static_hazards import _enc, _input
from shapely.geometry import GeometryCollection

from colav_simulator.core.colav.mid_mpc_acceptance import MidMpcPlanAcceptance
from colav_simulator.core.colav.retained_route import RetainedRouteConstraint
from colav_simulator.integrations.mid_mpc_ipopt import _recovery_iterate_filter


def test_native_clear_candidate_still_checks_off_route_goal_entry():
    data = replace(_input(_enc(GeometryCollection())),
        ownship_state=np.array([600.,100.,0.,4.,0.,0.]),
        waypoints_enu_m=np.array([[0.,1000.],[0.,0.]]),ownship_length_m=44.1,
        execution_route_constraint=RetainedRouteConstraint(
            'mission',((0.,0.),(1000.,0.)),(4.,4.),('cruise','cruise'),160.,32.,480.),
    )
    assembly = SimpleNamespace(problem=SimpleNamespace(route_objective=SimpleNamespace(terminal_position_m=None)),
        horizon_encounter_plan=SimpleNamespace(recovery_from_k=0,target_windows=()),
        grid=SimpleNamespace(control_intervals=20,dt_s=5.))
    check = _recovery_iterate_filter(data,assembly)
    assert check is not None
    assert check(np.r_[np.zeros(20),np.full(20,4.),0.,0.]) is False
    aligned = replace(data,ownship_state=np.array([600.,0.,0.,4.,0.,0.]))
    assert _recovery_iterate_filter(aligned,assembly)(np.r_[np.zeros(20),np.full(20,4.),0.,0.]) is True


def test_capture_checks_between_knots_even_when_both_are_outside_arrival_disk():
    from colav_simulator.core.colav.mid_mpc_arrival import navigation_capture_error

    assert navigation_capture_error(
        np.array([600.,1400.]),np.array([50.,50.]),((0.,0.),(1000.,0.)),100.,
    ) == 50.0


def test_l4_checks_executable_route_even_when_prediction_stays_outside_goal():
    from test_mid_mpc_plan_acceptance import _request
    from colav_simulator.core.colav.mid_mpc_acceptance import MidMpcPlanAcceptance

    request = _request()
    request = replace(request,execution=replace(
        request.execution,capability=replace(request.execution.capability,plant='original_gnc_20260824_v2'),
        ownship_length_m=44.1,mission_waypoints_ne_m=((0.,0.),(1000.,0.)),
        navigation_route_points_ne_m=((600.,100.),(1400.,100.)),
    ))
    findings=[]
    MidMpcPlanAcceptance._quality(request,findings,())
    assert 'QUALITY_NAVIGATION_CAPTURE' in {finding.code for finding in findings}


def test_navigation_arrival_reference_closes_cross_track_before_disk_entry():
    """Arrival references must rejoin the leg before entering the arrival disk.

    ot_extturn_e0 (2026-09-16) failed L4 QUALITY_NAVIGATION_CAPTURE: the plan
    entered the 308.7 m arrival region 36.9 m off the mission leg because the
    recovery lead could put the leg intercept inside the disk. The reference
    kinematics themselves must satisfy the 20 m capture gate whenever the
    approach leaves room to turn.
    """
    import math

    import numpy as np
    from colav_simulator.core.colav.mid_mpc_arrival import _navigation_arrival_references

    for cross, heading_deg, along in ((-36.7, 50.0, 2700.0), (-500.0, 45.0, 2000.0), (-1000.0, 60.0, 1500.0)):
        headings, _lateral, speeds, _terminal = _navigation_arrival_references(
            ((0.0, 0.0), (3000.0, 0.0)),
            (along, cross),
            math.radians(heading_deg),
            8.0,
            8.0,
            5.0,
            80,
            0.3,
            0.020943951023931952,
            (0.0, 0.0),
            0.0,
            308.7,
        )
        location = np.array([float(along), float(cross)])
        entry_cross = None
        for heading, speed in zip(headings, speeds):
            location = location + speed * 5.0 * np.array([math.cos(heading), math.sin(heading)])
            if math.hypot(location[0] - 3000.0, location[1]) <= 308.7:
                entry_cross = abs(location[1])
                break
        assert entry_cross is not None and entry_cross <= 20.0, (cross, heading_deg, entry_cross)


def test_execution_route_stops_at_arrival_boundary_while_encounter_uncleared():
    """An uncleared encounter must not publish a tail into the arrival region.

    ot_extturn_e0 (2026-09-16): with the external-turn speed gate fixed, every
    plan after ~t=500 reached the goal inside its horizon while the OT target
    was still active; the speculative tail crossed into the 308.7 m arrival
    region 36.9 m off the mission leg and L4 rejected the route. The compiled
    route must stop at the arrival-region boundary instead.
    """
    from types import SimpleNamespace

    import numpy as np

    from colav_simulator.core.colav.retained_route import (
        compile_execution_route,
        _segment_enters_arrival_region,
    )

    assert _segment_enters_arrival_region(
        np.array([0.0, 0.0]), np.array([1000.0, 0.0]), np.array([500.0, 0.0]), 100.0
    )
    assert not _segment_enters_arrival_region(
        np.array([0.0, 0.0]), np.array([300.0, 0.0]), np.array([500.0, 0.0]), 100.0
    )

    plan = SimpleNamespace(
        course_rad=(0.0,) * 4,
        points_ne_m=((0.0, 0.0), (40.0, 0.0), (80.0, 0.0), (120.0, 0.0), (160.0, 0.0)),
        route_speed_mps=(8.0,) * 5,
        navigation_modes=("cruise",) * 5,
        retained_point_count=5,
        constraint=SimpleNamespace(minimum_segment_m=32.0, semantic_hash="test-constraint", reference_id="test"),
    )
    # Suffix knots march to 460 m; a 100 m arrival disk at 500 m truncates the
    # route before the final segment crosses the boundary.
    knots = 81
    predicted = np.zeros((5, knots))
    predicted[0, :] = np.minimum(160.0 + np.maximum(np.arange(knots) - 4, 0) * 40.0, 460.0)
    predicted[1, :] = 0.0
    predicted[3, :] = 8.0
    truncated = compile_execution_route(plan, predicted, arrival_boundary=((500.0, 0.0), 100.0))
    distances = [np.hypot(n - 500.0, e) for n, e in truncated["points_ne_m"]]
    assert min(distances) > 100.0
    assert len(truncated["points_ne_m"]) < len(plan.points_ne_m) + knots

    full = compile_execution_route(plan, predicted)
    assert len(full["points_ne_m"]) > len(truncated["points_ne_m"])


def test_declared_native_arrival_cannot_pass_by_missing_the_goal_disk():
    data = replace(
        _input(_enc(GeometryCollection())),
        ownship_state=np.array([600.0, 400.0, 0.0, 4.0, 0.0, 0.0]),
        waypoints_enu_m=np.array([[0.0, 1000.0], [0.0, 0.0]]),
        ownship_length_m=44.1,
        execution_route_constraint=RetainedRouteConstraint(
            "mission",
            ((0.0, 0.0), (1000.0, 0.0)),
            (4.0, 4.0),
            ("cruise", "cruise"),
            160.0,
            32.0,
            480.0,
            trajectory_updates=True,
        ),
    )
    assembly = SimpleNamespace(
        problem=SimpleNamespace(route_objective=SimpleNamespace(terminal_position_m=(400.0, -400.0))),
        horizon_encounter_plan=SimpleNamespace(recovery_from_k=0, target_windows=()),
        grid=SimpleNamespace(control_intervals=20, dt_s=5.0),
    )
    candidate = np.r_[np.zeros(20), np.full(20, 4.0), 0.0, 0.0]
    assert _recovery_iterate_filter(data, assembly)(candidate) is False


def test_l4_requires_goal_entry_when_native_reference_declares_arrival():

    request = _request()
    request = replace(
        request,
        execution=replace(
            request.execution,
            capability=replace(request.execution.capability, plant="original_gnc_20260824_v2"),
            ownship_length_m=44.1,
            mission_waypoints_ne_m=((0.0, 0.0), (1000.0, 0.0)),
            navigation_route_points_ne_m=((600.0, 400.0), (1000.0, 400.0)),
            navigation_arrival_expected=True,
        ),
    )
    findings = []
    MidMpcPlanAcceptance._quality(request, findings, ())
    assert "QUALITY_NAVIGATION_ARRIVAL_MISSING" in {finding.code for finding in findings}
