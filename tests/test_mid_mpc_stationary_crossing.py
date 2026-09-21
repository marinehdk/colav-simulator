"""Replay the T1061.4 stopped-TS2 failure without dropping moving-target duties."""

import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from colav_simulator.core.colav.mid_mpc_acceptance import (
    AcceptanceMode,
    AuthorityTarget,
    MidMpcPlanAcceptance,
    PlanAcceptancePolicy,
)
from colav_simulator.core.tracking.trackers import TrackKey
from colav_simulator.integrations.mid_mpc_ipopt import _execution_target


def _recorded_request(velocity=None, risk="PAST_CLEAR") -> SimpleNamespace:
    path = Path(__file__).parent / "fixtures/original_gnc/mid-mpc-stationary-ts2.json"
    case = json.loads(path.read_text())
    authority = case["authority"]
    authority["key"] = TrackKey(**authority["key"])
    authority["risk"] = risk
    track = case["track"]
    if velocity is not None:
        track["state_enu"][2:] = velocity
    target = _execution_target(SimpleNamespace(**track), 81, 5.0)
    own = case["candidate"]
    return SimpleNamespace(
        candidate=SimpleNamespace(
            north_m=np.array(own["north_m"]),
            east_m=np.array(own["east_m"]),
            course_rad=np.array(own["heading_rad"]),
            times_s=np.arange(81) * 5.0,
            phase_evidence=None,
        ),
        authority=SimpleNamespace(targets=(AuthorityTarget(**authority),)),
        execution=SimpleNamespace(
            targets=(target,),
            sim_time_s=case["sim_time_s"],
            ownship_length_m=44.1,
            ownship_width_m=8.0,
            static_context_required=False,
        ),
        prior=SimpleNamespace(mode=AcceptanceMode.FRESH_CANDIDATE),
        policy=PlanAcceptancePolicy(hard_hull_clearance_m=180.0, advisory_hull_clearance_m=200.0),
    )


@pytest.mark.parametrize("risk", ["ACTIVE", "PAST_CLEAR"])
@pytest.mark.parametrize("velocity", [None, (0.0, 0.0)])
def test_stationary_crossing_prediction_does_not_invent_bow_passing(risk, velocity):
    request = _recorded_request(velocity, risk)
    findings = []
    MidMpcPlanAcceptance._colreg(request, findings)
    assert "COLREG_CROSSING_BOW" not in {finding.code for finding in findings}


@pytest.mark.parametrize("risk", ["ACTIVE", "PAST_CLEAR"])
@pytest.mark.parametrize("velocity,rejected", [((1.0, 0.0), True), ((-1.0, 0.0), False)])
def test_moving_crossing_retains_bow_rejection(risk, velocity, rejected):
    findings = []
    MidMpcPlanAcceptance._colreg(_recorded_request(velocity, risk), findings)
    assert ("COLREG_CROSSING_BOW" in {finding.code for finding in findings}) is rejected


def test_stationary_target_still_has_mandatory_swept_hull_safety():
    request = _recorded_request()
    target = request.execution.targets[0]
    request.execution.targets = (
        replace(
            target,
            north_m=np.full(81, request.candidate.north_m[4]),
            east_m=np.full(81, request.candidate.east_m[4]),
        ),
    )
    findings = []
    MidMpcPlanAcceptance._safety(request, findings)
    assert any(finding.code == "SAFETY_SWEPT_CLEARANCE" and finding.mandatory for finding in findings)


def test_zero_endpoint_displacement_does_not_exempt_a_moving_prediction():
    request = _recorded_request()
    target = request.execution.targets[0]
    north = target.north_m.copy()
    north[1:-1] += 1.0
    request.execution.targets = (replace(target, north_m=north),)
    findings = []
    MidMpcPlanAcceptance._colreg(request, findings)
    assert "COLREG_CROSSING_BOW" in {finding.code for finding in findings}


def test_stationary_target_does_not_waive_locked_action_deadlines():
    request = _recorded_request()
    authority = replace(request.authority.targets[0], action_achieved=False, action_started=False)
    request.authority.targets = (authority,)
    request.candidate.course_rad = np.full(81, authority.baseline_course_rad - 0.2)
    findings = []
    MidMpcPlanAcceptance._colreg(request, findings)
    assert "COLREG_ACTION_DEADLINE" in {finding.code for finding in findings}
