"""Arrival-circle entry cannot stand in for native mission-leg recovery."""
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
from test_mid_mpc_static_hazards import _enc, _input
from shapely.geometry import GeometryCollection

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
