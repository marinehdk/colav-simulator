from __future__ import annotations

import math

from conftest import P1RunHarness

from examples.validate_kuwata_vo import (
    Acceptance,
    _dual_head_on_metrics,
    _project_fixture_session,
    _session_result,
    summarize,
)


def test_head_on_vo_executes_safe_starboard_closed_loop(
    p1_run_harness: P1RunHarness,
) -> None:
    nominal = p1_run_harness.run("head_on", "nominal", "god")
    candidate = p1_run_harness.run("head_on", "vo", "god")
    nominal_summary, _ = summarize(nominal, Acceptance())
    vo_summary, rows = summarize(candidate, Acceptance())

    assert nominal_summary["truth"]["ship0_vs_target"]["continuous_collision"]
    assert not vo_summary["truth"]["ship0_vs_target"]["continuous_collision"]
    assert vo_summary["truth"]["ship0_vs_target"]["minimum_sampled_hull_clearance_m"] >= 50.0
    assert vo_summary["encounter"]["entry_time_s"] is not None
    assert vo_summary["encounter"]["first_action_body_starboard_mps"] > 0.25
    assert vo_summary["encounter"]["rule_released_after_last_active"]
    assert vo_summary["solver"]["fallback_count"] == 0
    assert vo_summary["solver"]["maximum_consecutive_feasible_stop_solves"] == 0
    assert vo_summary["solver"]["selected_hard_constraint_safe"]
    assert vo_summary["finite_state_outputs"]
    active_rows = [row for row in rows if "HO" in row["active_rules"]]
    assert active_rows
    assert active_rows[0]["rule_tcpa_s"] is not None
    assert active_rows[0]["rule_tcpa_s"] >= 0.0
    assert active_rows[0]["preferred_domain_toc_s"] is not None
    assert 0.0 <= active_rows[0]["preferred_domain_toc_s"] <= 120.0
    assert active_rows[0]["rule_dcpa_m"] <= 100.0
    assert all(not row["selected_in_base_vo"] for row in active_rows)
    assert all(not row["selected_in_colregs_v1"] for row in active_rows)
    assert any(
        row["solver_executed"]
        and abs(row["actual_heading_rad"] - row["selected_heading_rad"]) < 0.2
        for row in rows
        if row["selected_heading_rad"] is not None
    )


def test_starboard_crossing_activates_rule_before_safe_closed_loop_maneuver(
    p1_run_harness: P1RunHarness,
) -> None:
    nominal = p1_run_harness.run("crossing_give_way", "nominal", "god")
    candidate = p1_run_harness.run("crossing_give_way", "vo", "god")
    nominal_summary, _ = summarize(nominal, Acceptance())
    vo_summary, rows = summarize(candidate, Acceptance())

    assert nominal_summary["truth"]["ship0_vs_target"]["continuous_collision"]
    assert not vo_summary["truth"]["ship0_vs_target"]["continuous_collision"]
    assert vo_summary["encounter"]["entry_time_s"] is not None
    assert vo_summary["encounter"]["first_action_body_starboard_mps"] > 0.25
    assert vo_summary["encounter"]["rule_released_after_last_active"]
    active_rows = [row for row in rows if "CR_SS" in row["active_rules"]]
    assert active_rows
    assert all(not row["selected_in_base_vo"] for row in active_rows)
    assert all(not row["selected_in_colregs_v1"] for row in active_rows)
    assert all(row["crossing_commitment_active"] for row in active_rows)
    assert not any(row["emergency_rule_relaxation"] for row in rows)
    assert vo_summary["solver"]["active_turn_reversals"] == 0
    released_rows = [
        row
        for row in rows
        if row["time_s"] > active_rows[-1]["time_s"]
    ]
    assert released_rows
    assert not any(row["stand_on_hold_active"] for row in released_rows)
    assert min(abs(row["east_m"] - 40500.0) for row in released_rows) < 5.0
    assert abs(released_rows[-1]["east_m"] - 40500.0) < 15.0
    assert (
        vo_summary["encounter"]["closest_approach_target_stern_plane_clearance_m"]
        > 0.0
    )
    assert vo_summary["accepted"]


def test_port_crossing_stands_on_until_current_velocity_enters_base_vo(
    p1_run_harness: P1RunHarness,
) -> None:
    candidate = p1_run_harness.run("crossing_stand_on", "vo", "god")
    summary, rows = summarize(candidate, Acceptance())
    first_heading = rows[0]["actual_heading_rad"]
    first_speed = rows[0]["actual_speed_mps"]
    before_fallback = []
    for row in rows:
        if row["current_in_base_vo"]:
            break
        before_fallback.append(row)

    assert before_fallback
    assert max(
        abs(
            math.atan2(
                math.sin(row["actual_heading_rad"] - first_heading),
                math.cos(row["actual_heading_rad"] - first_heading),
            )
        )
        for row in before_fallback
    ) <= math.radians(3.0)
    assert max(
        abs(row["actual_speed_mps"] - first_speed) for row in before_fallback
    ) <= 0.2
    assert summary["truth"]["ship0_vs_target"]["continuous_collision"] is False
    assert summary["solver"]["fallback_count"] == 0


def test_overtaking_commits_once_passes_and_returns_to_route(
    p1_run_harness: P1RunHarness,
) -> None:
    candidate = p1_run_harness.run("overtaking", "vo", "god")
    summary, rows = summarize(candidate, Acceptance())
    solve_rows = [row for row in rows if row["solver_executed"]]
    committed = [row for row in solve_rows if row["overtaking_state"] == "COMMITTED"]
    passed = [row for row in solve_rows if row["overtaking_state"] == "PASSED"]

    assert committed
    assert committed[0]["time_s"] <= 1.0
    first_turn = math.atan2(
        math.sin(committed[0]["selected_heading_rad"] - rows[0]["actual_heading_rad"]),
        math.cos(committed[0]["selected_heading_rad"] - rows[0]["actual_heading_rad"]),
    )
    assert first_turn >= math.radians(5.0)
    assert not any(row["overtaking_progress_relaxed"] for row in committed)
    assert not any(row["emergency_rule_relaxation"] for row in committed)
    assert summary["solver"]["active_turn_reversals"] == 0
    assert passed
    assert passed[0]["overtaking_along_track_m"] >= 50.0
    assert passed[0]["center_distance_m"] >= 100.0
    assert passed[0]["overtaking_relative_speed_mps"] > 0.0
    assert passed[0]["rule_tcpa_s"] <= 0.0

    transitions = []
    previous = solve_rows[0]["overtaking_state"]
    for row in solve_rows[1:]:
        current = row["overtaking_state"]
        if current != previous:
            transitions.append((previous, current))
            previous = current
    assert transitions == [("COMMITTED", "PASSED"), ("PASSED", "CLEAR")]

    released = [row for row in solve_rows if row["time_s"] > passed[-1]["time_s"]]
    assert released
    assert any(
        abs(
            math.atan2(
                math.sin(row["actual_heading_rad"] - math.pi / 4.0),
                math.cos(row["actual_heading_rad"] - math.pi / 4.0),
            )
        )
        < math.radians(3.0)
        and abs(row["actual_speed_mps"] - 8.0) < 0.2
        for row in released
    )
    assert summary["truth"]["ship0_vs_target"]["continuous_collision"] is False
    assert summary["truth"]["grounding"]["grounded"] is False
    assert summary["solver"]["fallback_count"] == 0


def test_both_head_on_vessels_execute_starboard_vo_maneuvers() -> None:
    session = _project_fixture_session("head_on_both_vo", "vo")
    session.run_to_completion()
    summary, _ = summarize(
        _session_result(session, "head_on_both_vo", "vo"),
        Acceptance(),
    )
    dual = _dual_head_on_metrics(session)

    assert summary["accepted"], summary
    assert not summary["truth"]["global_all_vessel"]["continuous_collision"]
    assert dual["accepted"]
