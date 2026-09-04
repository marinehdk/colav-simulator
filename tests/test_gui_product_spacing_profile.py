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

from dataclasses import replace

from conftest import PROJECT_ROOT

from colav_simulator.experiment.runner import ExperimentRunner
from gui_server.main import SessionCreateRequest

FCB45_STACK_ID = "fcb45_3dof_plant+pass_through_guidance+fcb45_marine_pid"
MAX_RETURN_XTE_M = 50.0
MAX_ROUTE_CROSSINGS = 2
MIN_ENCOUNTER_CENTER_DISTANCE_M = 180.0


def test_gui_default_head_on_session_returns_to_route(tmp_path) -> None:
    spec = SessionCreateRequest(
        scenario_id="head_on",
        validation_rule_id="rule14",
        algorithm_id="vo",
        tracker_id="god",
        gnc_stack_id=FCB45_STACK_ID,
    ).to_spec()
    spec = replace(spec, output_root=str(tmp_path / "runs"))
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
