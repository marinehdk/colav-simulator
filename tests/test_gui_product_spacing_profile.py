"""Product (GUI) sessions must run the Issue #67 validated spacing profiles.

The 8010 UI always sends ``algorithm_config={}``; before the fix the session
then ran the published VOParams() defaults, whose 120 s horizon keeps the
route direction masked ~250 s past CPA, so the FCB45 stacks executed a full
recovery loop (607 m return-window XTE on head_on, reproduced headless
2026-09-04). ``SessionCreateRequest.to_spec`` now injects the validated
spacing profile (unit-pinned in test_gnc_stack_api.py); this file locks the
end-to-end behaviour under the exact shipped-scenario conditions the UI runs
(no scenario override, scenario-default t_end).
"""

from __future__ import annotations

import math
from dataclasses import replace

from conftest import PROJECT_ROOT

from colav_simulator.experiment.contracts import RunSpec
from colav_simulator.experiment.runner import ExperimentRunner
from examples.validate_kuwata_vo import Acceptance, summarize
from gui_server.main import SessionCreateRequest

FCB45_STACK_ID = "fcb45_3dof_plant+pass_through_guidance+fcb45_marine_pid"
MAX_RETURN_XTE_M = 50.0
MAX_ROUTE_CROSSINGS = 2
MIN_ENCOUNTER_CENTER_DISTANCE_M = 180.0
# One full heading circle in the post-CPA recovery window is the circling
# evidence threshold: a clean turn-back sweeps well under 180 degrees.
FULL_CIRCLE_SWEEP_DEG = 360.0


def _gui_default_head_on_spec(tmp_path) -> RunSpec:
    spec = SessionCreateRequest(
        scenario_id="head_on",
        validation_rule_id="rule14",
        algorithm_id="vo",
        tracker_id="god",
        gnc_stack_id=FCB45_STACK_ID,
    ).to_spec()
    return replace(spec, output_root=str(tmp_path / "runs"))


def test_gui_default_head_on_session_returns_to_route(tmp_path) -> None:
    spec = _gui_default_head_on_spec(tmp_path)
    assert spec.t_end is None, "precondition: shipped scenario t_end must apply"

    result = ExperimentRunner(PROJECT_ROOT).run(spec)

    events = {event["type"] for event in result.session.events}
    assert not {"collision", "grounding", "run_failed", "session_failed"} & events, sorted(events)
    voyage = result.evaluation.voyage
    assert voyage["encounter"]["min_target_center_distance_m"] >= MIN_ENCOUNTER_CENTER_DISTANCE_M

    return_voyage = voyage["return_voyage"]
    assert return_voyage is not None
    assert return_voyage["sample_count"] > 0, "600 s must cover CPA + 240 s return window"
    assert return_voyage["max_abs_xte_m"] <= MAX_RETURN_XTE_M, return_voyage
    assert return_voyage["route_crossings"] <= MAX_ROUTE_CROSSINGS, return_voyage


def test_gui_default_head_on_recovery_rotation_stays_below_one_circle(tmp_path) -> None:
    # Regression for the CR_PS stand-on hold circle: with the crossing
    # completion fix the post-CPA recovery is a plain turn-back (sweep well
    # under one full circle); the hold previously froze the selection on the
    # current velocity cell for ~130 s past CPA and the residual turn rate
    # integrated into a 442 deg portward circle.
    spec = _gui_default_head_on_spec(tmp_path)
    result = ExperimentRunner(PROJECT_ROOT).run(spec)

    recovery = result.evaluation.voyage["recovery_voyage"]
    assert recovery is not None
    assert recovery["heading_gross_sweep_deg"] is not None
    assert recovery["heading_gross_sweep_deg"] < FULL_CIRCLE_SWEEP_DEG, recovery


def test_gui_default_overtaking_recovers_without_u_turn_or_repeated_weaving(tmp_path) -> None:
    """Exercise the shipped OT route and GUI stack, including the whole return."""
    spec = SessionCreateRequest(
        scenario_id="overtaking",
        validation_rule_id="rule13",
        algorithm_id="vo",
        tracker_id="god",
        gnc_stack_id=FCB45_STACK_ID,
    ).to_spec()
    result = ExperimentRunner(PROJECT_ROOT).run(replace(spec, output_root=str(tmp_path / "runs")))
    summary, rows = summarize(result, Acceptance())
    assert rows[-1]["time_s"] >= 599.0, "the full 600 s scene must cover the settling window"
    assert not summary["truth"]["ship0_vs_target"]["continuous_collision"]
    assert not summary["truth"]["grounding"]["grounded"]
    assert summary["solver"]["fallback_count"] == 0
    # Preserve the prior OT repair's ~414 m return clearance with a 400 m floor.
    assert result.evaluation.voyage["encounter"]["min_target_center_distance_m"] >= 400.0
    xte = [(row["east_m"] - 39000.0 - (row["north_m"] - 6957000.0)) / math.sqrt(2.0) for row in rows]
    assert min(xte) >= -50.0, "return must not overshoot to the opposite side in a U"
    # Test settled motion as well as position: crossing the line once at 600 s
    # is insufficient when heading still swings tens of degrees either side.
    for row, error in zip(rows, xte, strict=True):
        if row["time_s"] < 570.0:
            continue
        heading_error = math.atan2(
            math.sin(row["actual_heading_rad"] - math.pi / 4.0),
            math.cos(row["actual_heading_rad"] - math.pi / 4.0),
        )
        assert abs(error) <= 10.0
        assert abs(heading_error) <= math.radians(5.0)
