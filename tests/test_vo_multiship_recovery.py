"""Full GUI three-target OT/CS/HO recovery with the original route and dynamics."""
from __future__ import annotations

import math
from dataclasses import replace

import numpy as np
from conftest import PROJECT_ROOT

from colav_simulator.core.colav.threat_assessment import ThreatManagementSnapshot
from colav_simulator.core.colav.threat_management import ThreatManagementCoordinator
from colav_simulator.experiment.runner import ExperimentRunner
from gui_server.main import SessionCreateRequest


def test_three_target_vo_recovers_forward_and_keeps_head_on_duty(tmp_path, monkeypatch) -> None:  # noqa: PLR0915
    colors = {1: [], 2: [], 3: []}
    original_cycle = ThreatManagementCoordinator.cycle

    def observe(coordinator, cycle, **kwargs) -> ThreatManagementSnapshot:
        snapshot = original_cycle(coordinator, cycle, **kwargs)
        for vector in snapshot.vectors:
            colors[vector.key.target_id].append((cycle.sim_time_s, vector.display_class))
        return snapshot

    monkeypatch.setattr(ThreatManagementCoordinator, "cycle", observe)
    spec = SessionCreateRequest(
        scenario_id="paper_ccta2023_multiship",
        validation_rule_id="multiship",
        algorithm_id="vo",
        tracker_id="god",
        gnc_stack_id="fcb45_3dof_plant+pass_through_guidance+fcb45_marine_pid",
    ).to_spec()
    result = ExperimentRunner(PROJECT_ROOT).run(replace(spec, output_root=str(tmp_path / "runs")))
    ot_colors = colors[1]
    transitions = [color for i, (_, color) in enumerate(ot_colors) if i == 0 or color != ot_colors[i - 1][1]]
    assert transitions == ["LOW", "HIGH", "CLEAR"]
    assert next(t for t, color in ot_colors if color == "HIGH") < 100.0
    assert min(ot_colors, key=lambda item: abs(item[0] - 400.0))[1] == "CLEAR"
    assert all(color != "HIGH" for t, color in colors[2] if t < 600.0)
    assert all(color != "HIGH" for t, color in colors[3] if t < 1000.0)
    events = result.session.events
    event_types = {event["type"] for event in events}
    assert "goal_reached" in event_types
    assert not {"collision", "grounding", "run_failed", "session_failed"} & event_types
    assert not result.manifest.fallback_used
    assert result.evaluation.voyage["encounter"]["min_target_center_distance_m"] >= 180.0

    frames = result.session.frames
    corner = []
    head_on = []
    saw_crossing = False
    for frame in frames:
        own = frame["Ship0"]
        state = own["state"]
        vo = own["colav"]["vo"]
        if 200.0 <= own["timestamp"] and state[0] < 6956400.0:
            corner.append(state)
        if not own["colav"]["planner"]["solver_executed"]:
            continue
        metrics = vo["track_metrics"]
        crossing = metrics.get(2, metrics.get("2", {}))
        saw_crossing |= "CR_SS" in crossing.get("active_rules", ())
        if vo["give_way_rule_locks"].get("3") == "HO":
            head_on.append(frame)
            assert metrics.get(3, metrics.get("3", {}))["active_rules"] == ["HO"]
            assert not vo["stand_on_hold_active"]
        assert not vo["emergency_rule_relaxation"]

    assert corner and saw_crossing and head_on
    # No southwest turn back toward the old leg and no wide overshoot west of
    # the northbound leg. The original 239--365 s WPT2 chase violates both.
    for state in corner:
        turn_from_west = math.atan2(math.sin(state[2] + math.pi / 2), math.cos(state[2] + math.pi / 2))
        assert turn_from_west >= -math.radians(5.0)
        assert state[1] >= 40850.0 - 50.0
    assert min(frame["Ship0"]["state"][3] for frame in head_on) >= 0.75 * 5.65889

    # Both the VO lock and the displayed canonical threat must release only
    # after this encounter's target is abaft the ownship beam.
    last_locked_time = head_on[-1]["Ship0"]["timestamp"]
    first_unlocked = next(
        frame for frame in frames
        if frame["Ship0"]["timestamp"] > last_locked_time
        and frame["Ship0"]["colav"]["vo"]["give_way_rule_locks"].get("3") != "HO"
    )
    releases = [event for event in events if event["type"] == "threat_released"
                and event["details"].get("target_id") == 3]
    assert releases
    displayed_release = min(frames, key=lambda frame: abs(frame["Ship0"]["timestamp"] - releases[-1]["sim_time"]))
    for frame in (first_unlocked, displayed_release):
        own = np.asarray(frame["Ship0"]["state"])
        target = np.asarray(frame["Ship3"]["state"])
        forward = np.array([math.cos(own[2]), math.sin(own[2])])
        assert (target[:2] - own[:2]) @ forward < 0.0
