"""Synthetic-encounter tests for the Woerner-style COLREG compliance scorer."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from tools.original_gnc.colreg_scoring import (
    CROSSING_GIVE_WAY,
    CROSSING_STAND_ON,
    HEAD_ON,
    OVERTAKING,
    SCORER_V1,
    SCORER_V2,
    STATIC_HAZARD,
    ScoringThresholds,
    Track,
    classify_from_events,
    command_course_signal,
    first_alteration,
    main,
    parse_nominal_route,
    score_bundle,
    score_cell,
    score_encounter,
    score_run_dir,
    wrap_angle,
)

DT = 0.5


def _integrate(p0: tuple[float, float], t_end: float, heading_fn, speed: float, dt: float = DT) -> Track:
    """Straight/ramped-heading kinematic track in the compass frame (psi: 0=N)."""
    times = np.arange(0.0, t_end + dt / 2.0, dt)
    east = np.empty_like(times)
    north = np.empty_like(times)
    psi = np.array([heading_fn(float(t)) for t in times])
    east[0], north[0] = p0
    for i in range(1, len(times)):
        east[i] = east[i - 1] + speed * math.sin(psi[i - 1]) * dt
        north[i] = north[i - 1] + speed * math.cos(psi[i - 1]) * dt
    return Track(
        ship_id=0,
        times_s=times,
        east_m=east,
        north_m=north,
        sog_mps=np.full_like(times, speed),
        psi_rad=psi,
    )


def _slowing(p0, t_end, heading, base_speed, slow_speed, slow_start, t_end_slow) -> Track:
    """Constant-heading track that reduces speed for one interval (give-way by speed)."""
    track = _integrate(p0, t_end, lambda _t: heading, base_speed)
    mask = (track.times_s >= slow_start) & (track.times_s <= t_end_slow)
    sog = track.sog_mps.copy()
    sog[mask] = slow_speed
    east = np.empty_like(sog)
    north = np.empty_like(sog)
    east[0], north[0] = p0
    for i in range(1, len(sog)):
        east[i] = east[i - 1] + sog[i - 1] * math.sin(heading) * dt_step(track.times_s, i)
        north[i] = north[i - 1] + sog[i - 1] * math.cos(heading) * dt_step(track.times_s, i)
    return Track(
        ship_id=0,
        times_s=track.times_s,
        east_m=east,
        north_m=north,
        sog_mps=sog,
        psi_rad=track.psi_rad,
    )


def dt_step(times_s: np.ndarray, index: int) -> float:
    return float(times_s[index] - times_s[index - 1])


def _straight(p0: tuple[float, float], heading: float, speed: float, t_end: float, dt: float = DT) -> Track:
    return _integrate(p0, t_end, lambda _t: heading, speed, dt)


def _turning(p0, t_end, speed, h0, t_start, t_stop, h1) -> Track:
    def heading_fn(t: float) -> float:
        if t <= t_start:
            return h0
        if t >= t_stop:
            return h1
        return h0 + (h1 - h0) * (t - t_start) / (t_stop - t_start)

    return _integrate(p0, t_end, heading_fn, speed)


def _target(track: Track, ship_id: int) -> Track:
    return Track(
        ship_id=ship_id,
        times_s=track.times_s,
        east_m=track.east_m,
        north_m=track.north_m,
        sog_mps=track.sog_mps,
        psi_rad=track.psi_rad,
    )


def test_wrap_angle_maps_into_half_open_circle():
    assert wrap_angle(math.pi) == math.pi
    assert math.isclose(wrap_angle(3.0 * math.pi), math.pi)
    assert math.isclose(wrap_angle(-3.0 * math.pi), math.pi)
    assert math.isclose(wrap_angle(math.pi / 2.0), math.pi / 2.0)


def test_parse_nominal_route_bundle_convention():
    route = parse_nominal_route("[[6957500.0,6960900.0],[39500.0,42900.0]]")
    assert route is not None
    assert route.tolist() == [[39500.0, 6957500.0], [42900.0, 6960900.0]]
    multi = parse_nominal_route("[[0.0,10.0,20.0],[0.0,0.0,10.0]]")
    assert multi is not None
    # Tied magnitudes: the first list is read as eastings, (east, north) pairs.
    assert multi.tolist() == [[0.0, 0.0], [10.0, 0.0], [20.0, 10.0]]
    assert parse_nominal_route(None) is None
    assert parse_nominal_route("[[1,2]]") is None


def test_classify_from_events_reuses_vo_and_potocnik_labels():
    events = [
        {"type": "threat_entered", "sim_time": 0.5, "details": {"target_id": 1}},
        {
            "type": "planner_solved",
            "sim_time": 1.0,
            "details": {"planner": {"algorithm_details": {"active_rules": {"1": ["CR_SS"]}}}},
        },
        {
            "type": "planner_solved",
            "sim_time": 1.5,
            "details": {
                "planner": {
                    "algorithm_details": {
                        "encounter_records": [{"target_id": 2, "encounter": "overtaking"}],
                    }
                }
            },
        },
    ]
    classified, detection = classify_from_events(events)
    assert classified[1] == (CROSSING_GIVE_WAY, "planner_events")
    assert classified[2] == (OVERTAKING, "planner_events")
    assert detection[1] == 0.5


def test_head_on_starboard_alteration_is_compliant():
    """COLREG Rule 14: each vessel alters to starboard for a port-to-port pass."""
    own = _turning((0.0, 0.0), 450.0, 5.0, math.pi / 2.0, 40.0, 50.0, math.pi / 2.0 + 0.6)
    target = _target(_straight((1200.0, 0.0), -math.pi / 2.0, 5.0, 450.0), 1)
    record = score_encounter(own, target, HEAD_ON, "planner_events", None, None, ScoringThresholds())
    assert record.first_alteration_direction == "starboard"
    assert record.collision_avoidance_ok is True
    assert record.verdict == "COMPLIANT"
    assert "port-to-port" in record.reason


def test_head_on_port_alteration_is_non_compliant():
    own = _turning((0.0, 0.0), 450.0, 5.0, math.pi / 2.0, 40.0, 50.0, math.pi / 2.0 - 0.6)
    target = _target(_straight((1200.0, 0.0), -math.pi / 2.0, 5.0, 450.0), 1)
    record = score_encounter(own, target, HEAD_ON, "planner_events", None, None, ScoringThresholds())
    assert record.first_alteration_direction == "port"
    assert record.verdict == "NON_COMPLIANT"
    assert "Rule 14" in record.reason


def test_crossing_give_way_starboard_passes_astern():
    own = _turning((0.0, 0.0), 400.0, 5.0, 0.0, 40.0, 50.0, 0.6)
    target = _target(_straight((800.0, 600.0), -math.pi / 2.0, 5.0, 400.0), 1)
    record = score_encounter(own, target, CROSSING_GIVE_WAY, "planner_events", None, None, ScoringThresholds())
    assert record.dcpa_at_detection_m < 1000.0
    assert record.first_alteration_direction == "starboard"
    assert record.collision_avoidance_ok is True
    assert record.astern_pass is True
    assert record.verdict == "COMPLIANT"


def test_crossing_give_way_speed_reduction_is_compliant():
    """Rule 16 admits speed reduction; a post-CPA course change is recovery."""
    own = _slowing((0.0, 0.0), 400.0, 0.0, 5.0, 0.5, 60.0, 320.0)
    target = _target(_straight((800.0, 600.0), -math.pi / 2.0, 5.0, 400.0), 1)
    record = score_encounter(own, target, CROSSING_GIVE_WAY, "planner_events", None, None, ScoringThresholds())
    assert record.collision_avoidance_ok is True
    assert record.speed_reduction_fraction > 0.10
    assert record.astern_pass is True
    assert record.verdict == "COMPLIANT"
    assert "speed reduction" in record.reason


def test_crossing_give_way_port_alteration_is_non_compliant():
    own = _turning((0.0, 0.0), 400.0, 5.0, 0.0, 40.0, 50.0, -0.6)
    target = _target(_straight((800.0, 600.0), -math.pi / 2.0, 5.0, 400.0), 1)
    record = score_encounter(own, target, CROSSING_GIVE_WAY, "planner_events", None, None, ScoringThresholds())
    assert record.first_alteration_direction == "port"
    assert record.verdict == "NON_COMPLIANT"
    assert "Rule 15" in record.reason


def test_crossing_stand_on_hold_is_compliant():
    own = _straight((0.0, 0.0), 0.0, 5.0, 400.0)
    target = _target(_straight((1000.0, 500.0), -math.pi / 2.0, 5.0, 400.0), 1)
    record = score_encounter(own, target, CROSSING_STAND_ON, "planner_events", None, None, ScoringThresholds())
    assert record.first_alteration_index is None
    assert record.collision_avoidance_ok is True
    assert record.verdict == "COMPLIANT"
    assert record.role == "stand_on"
    assert "held" in record.reason


def test_crossing_stand_on_early_alteration_is_non_compliant():
    own = _turning((0.0, 0.0), 400.0, 5.0, 0.0, 10.0, 20.0, 0.6)
    target = _target(_straight((1000.0, 500.0), -math.pi / 2.0, 5.0, 400.0), 1)
    record = score_encounter(own, target, CROSSING_STAND_ON, "planner_events", None, None, ScoringThresholds())
    assert record.first_alteration_index is not None
    assert record.verdict == "NON_COMPLIANT"
    assert "before in-extremis" in record.reason


def test_overtaking_completed_pass_is_compliant():
    own = _straight((0.0, 0.0), math.pi / 2.0, 8.0, 600.0)
    target = _target(_straight((1200.0, 80.0), math.pi / 2.0, 5.0, 600.0), 1)
    record = score_encounter(own, target, OVERTAKING, "planner_events", None, None, ScoringThresholds())
    assert record.collision_avoidance_ok is True
    assert record.pass_completed is True
    assert record.verdict == "COMPLIANT"
    assert record.min_distance_m >= 50.0


def test_overtaking_truncated_run_is_not_evaluable():
    own = _straight((0.0, 0.0), math.pi / 2.0, 8.0, 300.0)
    target = _target(_straight((1200.0, 80.0), math.pi / 2.0, 5.0, 300.0), 1)
    record = score_encounter(own, target, OVERTAKING, "planner_events", None, None, ScoringThresholds())
    assert record.incomplete is True
    assert record.verdict == "NOT_EVALUABLE"


def test_score_cell_single_target_falls_back_to_scenario_class():
    own = _turning((0.0, 0.0), 450.0, 5.0, math.pi / 2.0, 40.0, 50.0, math.pi / 2.0 + 0.6)
    target = _target(_straight((1200.0, 0.0), -math.pi / 2.0, 5.0, 450.0), 1)
    result = score_cell(
        own,
        {1: target},
        scenario_id="head_on",
        validation_rule_id="rule14",
        events=[],
        waypoints_json="[[0.0,0.0],[0.0,2000.0]]",
    )
    encounter = result["encounters"][0]
    assert encounter.encounter_class == HEAD_ON
    assert encounter.classification_source == "scenario_fallback"
    summary = result["summary"]
    assert summary["encounter_count"] == 1
    assert summary["safety_score"] == 1.0
    assert summary["rule_score"] == 1.0
    assert 0.0 <= summary["composite_score"] <= 1.0
    assert result["path"]["path_ratio"] > 1.0  # the avoidance loop stretches the path


def test_score_cell_multiship_filters_distant_targets_geometrically():
    own = _straight((0.0, 0.0), 0.0, 5.0, 400.0)
    near = _target(_straight((1000.0, 500.0), -math.pi / 2.0, 5.0, 400.0), 1)
    far = _target(_straight((5000.0, 5000.0), -math.pi / 2.0, 5.0, 400.0), 2)
    result = score_cell(own, {1: near, 2: far}, scenario_id=None, validation_rule_id=None, events=[])
    assert [enc.target_id for enc in result["encounters"]] == [1]
    assert result["encounters"][0].classification_source == "geometry"


def _write_run_dir(run_dir: Path) -> None:
    own = _turning((0.0, 0.0), 450.0, 5.0, math.pi / 2.0, 40.0, 50.0, math.pi / 2.0 + 0.6)
    target = _straight((1200.0, 0.0), -math.pi / 2.0, 5.0, 450.0)
    run_dir.mkdir(parents=True)
    table = pa.table(
        {
            "ship_id": pa.array([0] * len(own.times_s) + [1] * len(target.times_s), pa.int64()),
            "sim_time": pa.array(list(own.times_s) + list(target.times_s), pa.float64()),
            "east_m": pa.array(list(own.east_m) + list(target.east_m), pa.float64()),
            "north_m": pa.array(list(own.north_m) + list(target.north_m), pa.float64()),
            "sog_mps": pa.array(list(own.sog_mps) + list(target.sog_mps), pa.float64()),
            "psi_rad": pa.array(list(own.psi_rad) + list(target.psi_rad), pa.float64()),
            "waypoints_json": ["[[0.0, 0.0], [0.0, 6000.0]]"] * len(own.times_s) + ["[]"] * len(target.times_s),
        }
    )
    pq.write_table(table, run_dir / "trajectory.parquet")
    events = [
        {"type": "threat_entered", "sim_time": 0.5, "details": {"target_id": 1}},
        {
            "type": "planner_solved",
            "sim_time": 1.0,
            "details": {"planner": {"algorithm_details": {"active_rules": {"1": ["HO"]}}}},
        },
    ]
    with (run_dir / "events.jsonl").open("w") as handle:
        for event in events:
            handle.write(json.dumps(event) + "\n")
    with (run_dir / "lifecycle_events.jsonl").open("w") as handle:
        handle.write(
            json.dumps(
                {
                    "event_type": "TARGET_TRANSITION",
                    "sim_time_s": 401.0,
                    "to_state": "RELEASED/ACHIEVED/NONE",
                    "target_key": {"target_id": 1, "generation": 1},
                }
            )
            + "\n"
        )
    (run_dir / "manifest.json").write_text(
        json.dumps(
            {
                "run_id": "synthetic-run",
                "state": "FINISHED",
                "execution_outcome": "COMPLETED",
                "failure_reason": None,
                "spec": {"scenario_id": "head_on", "validation_rule_id": "rule14", "algorithm_id": "vo"},
            }
        )
    )
    (run_dir / "evaluation.json").write_text(
        json.dumps({"hard_gate": {"outcome": "PASS"}, "aggregate": {"minimum_distance_m": 123.4}})
    )


def test_score_run_dir_round_trip(tmp_path: Path):
    run_dir = tmp_path / "run"
    _write_run_dir(run_dir)
    record = score_run_dir(
        run_dir,
        {"case_id": "synthetic-head-on-E0", "algorithm_id": "vo"},
    )
    assert record["case_id"] == "synthetic-head-on-E0"
    assert record["scenario_id"] == "head_on"
    assert record["evaluation_gate"] == "PASS"
    assert record["summary"]["encounter_count"] == 1
    encounter = record["encounters"][0]
    assert encounter["encounter_class"] == HEAD_ON
    assert encounter["classification_source"] == "planner_events"
    assert encounter["verdict"] == "COMPLIANT"
    assert encounter["first_alteration_direction"] == "starboard"
    assert encounter["detection_index"] is not None
    assert encounter["min_distance_index"] is not None
    assert record["path"]["path_ratio"] is not None

# ---------------------------------------------------------------------------
# v2 (R11 attribution corrections) -- see
# docs/research/2026-09-12-original-gnc-r11-attribution.md. The four fixtures
# at the bottom reduce the flagged p4 multiship encounters to their mechanism.
# ---------------------------------------------------------------------------


def _commanded(
    p0: tuple[float, float],
    t_end: float,
    speed_fn,
    psi_fn,
    course_ref_fn=None,
    ship_id: int = 0,
    dt: float = DT,
) -> Track:
    """Track integrated on the heading profile, with optional command reference."""
    times = np.arange(0.0, t_end + dt / 2.0, dt)
    psi = np.array([psi_fn(float(t)) for t in times])
    sog = np.array([speed_fn(float(t)) for t in times])
    east = np.empty_like(times)
    north = np.empty_like(times)
    east[0], north[0] = p0
    for i in range(1, len(times)):
        east[i] = east[i - 1] + sog[i - 1] * math.sin(psi[i - 1]) * dt
        north[i] = north[i - 1] + sog[i - 1] * math.cos(psi[i - 1]) * dt
    return Track(
        ship_id=ship_id,
        times_s=times,
        east_m=east,
        north_m=north,
        sog_mps=sog,
        psi_rad=psi,
        course_ref_rad=np.array([course_ref_fn(float(t)) for t in times]) if course_ref_fn else None,
    )


def _anchoring(
    p0: tuple[float, float], heading: float, speed: float, t_anchor: float, t_end: float, ship_id: int = 1, dt: float = DT
) -> Track:
    """Target that runs at constant heading, then stops (scene anchor leg)."""
    times = np.arange(0.0, t_end + dt / 2.0, dt)
    east = np.empty_like(times)
    north = np.empty_like(times)
    sog = np.where(times < t_anchor, speed, 0.0)
    east[0], north[0] = p0
    for i in range(1, len(times)):
        if times[i - 1] < t_anchor:
            east[i] = east[i - 1] + speed * math.sin(heading) * dt
            north[i] = north[i - 1] + speed * math.cos(heading) * dt
        else:
            east[i] = east[i - 1]
            north[i] = north[i - 1]
    return Track(
        ship_id=ship_id,
        times_s=times,
        east_m=east,
        north_m=north,
        sog_mps=sog,
        psi_rad=np.full_like(times, heading),
    )


def _encounter_events(labels: dict[int, str]) -> list[dict]:
    """threat_entered + planner encounter labels (Potocnik records)."""
    events = [{"type": "threat_entered", "sim_time": 0.5, "details": {"target_id": tid}} for tid in labels]
    events.append(
        {
            "type": "planner_solved",
            "sim_time": 1.0,
            "details": {
                "planner": {
                    "algorithm_details": {
                        "encounter_records": [{"target_id": tid, "encounter": label} for tid, label in labels.items()]
                    }
                }
            },
        }
    )
    return events


def _timeline_events(entries: list[tuple[float, int, str]]) -> list[dict]:
    """primary_switched / avoidance_action_started chain events."""
    return [{"type": etype, "sim_time": t, "details": {"target_id": tid}} for t, tid, etype in entries]


def test_first_alteration_v2_reads_command_signal_not_heading_wobble():
    """R11 #1: heading wobble around a steady course command is not an alteration.

    The v1 heading signal still reports it.
    """
    def wobble(t: float) -> float:
        return -0.192 if 100.0 <= t <= 102.5 else 0.0  # ~-11 deg, sustained

    own = _commanded((0.0, 0.0), 200.0, lambda _t: 6.0, wobble, lambda _t: 0.0)
    v2 = first_alteration(own, 1, ScoringThresholds(), signal=own.course_ref_rad, baseline_mode="pre_detect")
    assert v2["index"] is None
    v1 = first_alteration(own, 1, ScoringThresholds())
    assert v1["index"] is not None
    assert v1["direction"] == "port"


def test_first_alteration_v2_pre_detection_baseline_sees_immediate_action():
    """R11 #1: a command step at detection time stays visible in v2.

    The pre-detection baseline sees it; the post-detection window would swallow
    it.
    """
    def step(t: float) -> float:
        return 0.0 if t < 1.0 else 0.6  # immediate starboard answer

    own = _commanded((0.0, 0.0), 200.0, lambda _t: 6.0, step, step)
    v2 = first_alteration(own, 1, ScoringThresholds(), signal=own.course_ref_rad, baseline_mode="pre_detect")
    assert v2["index"] is not None
    assert v2["direction"] == "starboard"
    v1 = first_alteration(own, 1, ScoringThresholds())
    assert v1["index"] is None  # post-detection baseline already contains the step


def test_command_course_signal_reference_varies_vs_planner_commands():
    """R11 #1: the command layer is the varying applied reference.

    A reference pinned to the route is replaced by planner_solved
    selected_command.
    """
    own = _commanded((0.0, 0.0), 100.0, lambda _t: 5.0, lambda t: t / 100.0, lambda t: t / 100.0)
    assert command_course_signal(own, []) is own.course_ref_rad

    pinned = _commanded((0.0, 0.0), 100.0, lambda _t: 5.0, lambda _t: 0.7, lambda _t: 0.7)
    events = [
        {
            "type": "planner_solved",
            "sim_time": sim_time,
            "details": {"planner": {"selected_command": {"course_rad": course}}},
        }
        for sim_time, course in ((2.0, 1.1), (4.0, -1.2))
    ]
    signal = command_course_signal(pinned, events)
    i2 = int(np.searchsorted(pinned.times_s, 2.0))
    assert math.isclose(float(signal[0]), 0.7)  # seeded with the route reference
    assert math.isclose(float(signal[i2]), 1.1)
    assert math.isclose(float(signal[-1]), -1.2)  # forward-filled last command


def test_alteration_charged_to_primary_target_from_event_chain():
    """R11 #2: an alteration is charged to the primary target only.

    A genuine commanded port alteration is booked to the target the planner was
    acting on (primary timeline), not to the nearest target at CPA.
    """
    def step(t: float) -> float:
        return 0.0 if t < 100.0 else -0.349  # commanded port step at t=100

    own = _commanded((0.0, 0.0), 400.0, lambda _t: 6.0, step, step)
    benign = _target(_straight((1500.0, 1200.0), -math.pi / 2.0, 2.0, 400.0), 2)
    far = _target(_straight((6000.0, 6000.0), -math.pi / 2.0, 2.0, 400.0), 1)
    events = _encounter_events({2: "crossing_give_way"}) + _timeline_events([(5.0, 1, "avoidance_action_started")])
    result = score_cell(
        own,
        {1: far, 2: benign},
        scenario_id=None,
        validation_rule_id=None,
        events=events,
    )
    record = next(enc for enc in result["encounters"] if enc.target_id == 2)
    # Risk threshold never met -> no action required; but the alteration is NOT
    # booked against t2: primary at t=100 is target 1.
    assert record.first_alteration_index is None
    assert record.verdict == "COMPLIANT"
    assert "attributed to target 1" in record.reason


def test_commanded_port_alteration_still_rejected_when_charged():
    """R11 #2+#4: commanded-port rejection survives on the command signal.

    The event chain links the alteration to this target, so Rule 15 still
    rejects it.
    """
    def step(t: float) -> float:
        return 0.0 if t < 100.0 else -0.349

    own = _commanded((0.0, 0.0), 400.0, lambda _t: 6.0, step, step)
    closer = _target(_straight((300.0, 1500.0), -math.pi / 2.0, 4.0, 400.0), 2)
    far = _target(_straight((6000.0, 6000.0), -math.pi / 2.0, 2.0, 400.0), 1)
    events = _encounter_events({2: "crossing_give_way"}) + _timeline_events(
        [(5.0, 1, "avoidance_action_started"), (50.0, 2, "primary_switched")]
    )
    result = score_cell(own, {1: far, 2: closer}, scenario_id=None, validation_rule_id=None, events=events)
    record = next(enc for enc in result["encounters"] if enc.target_id == 2)
    assert record.first_alteration_index is not None
    assert record.first_alteration_direction == "port"
    assert record.verdict == "NON_COMPLIANT"
    assert "Rule 15" in record.reason


def test_unlinked_alteration_not_charged_without_event_evidence():
    """R11 #2: multi-target cell with no primary evidence -> no charge."""
    def step(t: float) -> float:
        return 0.0 if t < 100.0 else -0.349

    own = _commanded((0.0, 0.0), 400.0, lambda _t: 6.0, step, step)
    benign = _target(_straight((1500.0, 1200.0), -math.pi / 2.0, 2.0, 400.0), 2)
    far = _target(_straight((6000.0, 6000.0), -math.pi / 2.0, 2.0, 400.0), 1)
    events = _encounter_events({2: "crossing_give_way"})  # classification only, no primary chain
    result = score_cell(own, {1: far, 2: benign}, scenario_id=None, validation_rule_id=None, events=events)
    record = result["encounters"][0]
    assert record.first_alteration_index is None
    assert "no event-chain evidence" in record.reason


def test_anchored_target_reclassified_static_hazard():
    """R11 #3: SOG ~0 at CPA means clearance-only scoring.

    No Rule 15 direction obligation applies; the same geometry underway stays a
    give-way encounter.
    """
    own = _commanded((0.0, 0.0), 400.0, lambda _t: 6.0, lambda _t: 0.0, lambda _t: 0.0)
    anchored = _anchoring((300.0, 1500.0), -math.pi / 2.0, 4.0, 0.0, 400.0)
    record = score_encounter(
        own, anchored, CROSSING_GIVE_WAY, "planner_events", 0.5, None, ScoringThresholds()
    )
    assert record.encounter_class == STATIC_HAZARD
    assert record.role == "static_hazard"
    assert record.verdict == "COMPLIANT"
    assert record.min_distance_m < 1000.0  # risk met, still clearance-compliant

    underway = _target(_straight((300.0, 1500.0), -math.pi / 2.0, 4.0, 400.0), 1)
    record = score_encounter(own, underway, CROSSING_GIVE_WAY, "planner_events", 0.5, None, ScoringThresholds())
    assert record.encounter_class == CROSSING_GIVE_WAY
    assert record.verdict == "NON_COMPLIANT"  # no admissible action for a real give-way


# ---------------------------------------------------------------------------
# R11 case fixtures: the four p4 NON_COMPLIANT encounters, reduced.
# ---------------------------------------------------------------------------


def _multiship_context(extra_events: list[dict], t_end: float = 400.0) -> tuple[Track, dict[int, Track], list[dict]]:
    """Far overtaking primary t1 (unlabeled, filtered by range) + events."""
    far = _target(_straight((6000.0, 6000.0), -math.pi / 2.0, 2.0, t_end), 1)
    events = _timeline_events([(5.0, 1, "avoidance_action_started")]) + extra_events
    return far, events


def test_r11_fan_ms_e0_t2_wobble_misread_on_anchored_ts2():
    """fan-MS-E0 t2 fixture: heading wobble, steady course command, anchored TS2.

    v1 read a 179.7 deg port alteration that never existed on the command layer
    and CPA was against anchored TS2. v2: no alteration, static-hazard
    clearance -> COMPLIANT (v1: NON_COMPLIANT).
    """
    base = -1.4835  # -85 deg course command, constant
    def psi_fn(t: float) -> float:
        return base - 0.192 if 100.0 <= t <= 102.5 else base

    own = _commanded((0.0, 0.0), 400.0, lambda _t: 6.0, psi_fn, lambda _t: base)
    ts2 = _anchoring((-1300.0, -100.0), math.pi / 2.0, 3.0, 0.0, 400.0, ship_id=2)
    far, events = _multiship_context(_encounter_events({2: "crossing_give_way"}))
    v2 = score_cell(own, {1: far, 2: ts2}, scenario_id=None, validation_rule_id=None, events=events)
    record = next(enc for enc in v2["encounters"] if enc.target_id == 2)
    assert record.first_alteration_index is None
    assert record.encounter_class == STATIC_HAZARD
    assert record.verdict == "COMPLIANT"
    v1 = score_cell(
        own, {1: far, 2: ts2}, scenario_id=None, validation_rule_id=None, events=events, scorer_version=SCORER_V1
    )
    record1 = next(enc for enc in v1["encounters"] if enc.target_id == 2)
    assert record1.encounter_class == CROSSING_GIVE_WAY
    assert record1.first_alteration_direction == "port"
    assert record1.verdict == "NON_COMPLIANT"


def test_r11_fan_ms_e0_t3_recovery_ramp_attributed_to_primary():
    """fan-MS-E0 t3 fixture: port recovery ramp attributed to the primary.

    The ramp toward the leg-2 recovery course started before detection and
    belongs to the primary (t1) ledger; CPA is against anchored TS3. v2:
    uncharged + static hazard -> COMPLIANT.
    """
    def ramp(t: float) -> float:
        if t <= 150.0:
            return 0.5550  # 31.8 deg
        if t >= 180.0:
            return 0.0559  # 3.2 deg
        return 0.5550 + (0.0559 - 0.5550) * (t - 150.0) / 30.0

    own = _commanded((0.0, 0.0), 400.0, lambda _t: 6.0, ramp, ramp)
    ts3 = _anchoring((700.0, 2000.0), -math.pi / 2.0, 3.0, 0.0, 400.0, ship_id=3)
    far, events = _multiship_context(_encounter_events({3: "crossing_give_way"}))
    events = [event for event in events if event.get("type") != "threat_entered"]
    events.append({"type": "threat_entered", "sim_time": 160.0, "details": {"target_id": 3}})
    v2 = score_cell(own, {1: far, 3: ts3}, scenario_id=None, validation_rule_id=None, events=events)
    record = next(enc for enc in v2["encounters"] if enc.target_id == 3)
    assert record.first_alteration_index is None  # ramp charged to primary t1
    assert "attributed to target 1" in record.reason
    assert record.encounter_class == STATIC_HAZARD
    assert record.verdict == "COMPLIANT"
    v1 = score_cell(
        own, {1: far, 3: ts3}, scenario_id=None, validation_rule_id=None, events=events, scorer_version=SCORER_V1
    )
    record1 = next(enc for enc in v1["encounters"] if enc.target_id == 3)
    assert record1.first_alteration_direction == "port"
    assert record1.verdict == "NON_COMPLIANT"


def test_r11_fan_ms_e4_t2_incomplete_cpa_stays_compliant_static():
    """fan-MS-E4 t2 fixture: wobble mechanism with CPA at run end.

    Min distance (990 m) is unresolved at window end. v2 static-hazard
    clearance stays COMPLIANT without the unresolved-encounter PARTIAL
    downgrade (v1: NON_COMPLIANT port).
    """
    base = -1.4835
    def psi_fn(t: float) -> float:
        return base - 0.192 if 100.0 <= t <= 102.5 else base

    own = _commanded((0.0, 0.0), 200.0, lambda _t: 6.0, psi_fn, lambda _t: base)
    ts2 = _anchoring((-1400.0, -800.0), math.pi / 2.0, 3.0, 0.0, 200.0, ship_id=2)
    far, events = _multiship_context(_encounter_events({2: "crossing_give_way"}), t_end=200.0)
    v2 = score_cell(own, {1: far, 2: ts2}, scenario_id=None, validation_rule_id=None, events=events)
    record = next(enc for enc in v2["encounters"] if enc.target_id == 2)
    assert record.encounter_class == STATIC_HAZARD
    assert record.incomplete is True
    assert record.verdict == "COMPLIANT"  # not downgraded: anchored target, no direction duty
    assert record.min_distance_m >= 50.0
    v1 = score_cell(
        own, {1: far, 2: ts2}, scenario_id=None, validation_rule_id=None, events=events, scorer_version=SCORER_V1
    )
    record1 = next(enc for enc in v1["encounters"] if enc.target_id == 2)
    assert record1.verdict == "NON_COMPLIANT"


def test_r11_vo_ms_e4_t2_speed_reduction_not_vetoed_by_heading_port():
    """vo-MS-E4 t2 fixture: heading port lag must not veto speed reduction.

    The port 'alteration' was tracked-heading lag behind a steady applied
    reference; the ~67% Rule 16 speed reduction was vetoed by that reading in
    v1. v2: heading no longer vetoes -> COMPLIANT via speed reduction.
    """
    def psi_fn(t: float) -> float:
        return -0.2094 if 100.0 <= t <= 102.5 else 0.0  # -12 deg lag excursion

    def speed_fn(t: float) -> float:
        return 6.0 if t < 60.0 else 2.0  # ~67% reduction under a steady command

    own = _commanded((0.0, 0.0), 400.0, speed_fn, psi_fn, lambda _t: 0.0)
    mover = _target(_straight((600.0, 800.0), -math.pi / 2.0, 3.0, 400.0), 2)
    events = _encounter_events({2: "crossing_give_way"})
    v2 = score_cell(own, {2: mover}, scenario_id=None, validation_rule_id=None, events=events)
    record = v2["encounters"][0]
    assert record.first_alteration_index is None
    assert record.encounter_class == CROSSING_GIVE_WAY  # target underway: no static reclass
    assert record.speed_reduction_fraction > 0.5
    assert record.verdict == "COMPLIANT"
    assert "speed reduction" in record.reason
    v1 = score_cell(
        own, {2: mover}, scenario_id=None, validation_rule_id=None, events=events, scorer_version=SCORER_V1
    )
    record1 = v1["encounters"][0]
    assert record1.verdict == "NON_COMPLIANT"
    assert "Rule 15" in record1.reason


def test_scorer_version_fields_and_flag(tmp_path: Path):
    """R11 #5: outputs are versioned; v1 stays reproducible behind the flag."""
    run_dir = tmp_path / "run"
    _write_run_dir(run_dir)
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "cell.json").write_text(json.dumps({"run_dir": str(run_dir), "case_id": "synthetic"}))
    v2 = score_bundle(bundle)
    assert v2["version"] == SCORER_V2
    assert all(cell["scorer_version"] == SCORER_V2 for cell in v2["cells"])
    v1 = score_bundle(bundle, scorer_version=SCORER_V1)
    assert v1["version"] == SCORER_V1
    assert v1["cells"][0]["scorer_version"] == SCORER_V1
    out_dir = tmp_path / "out"
    assert main([str(bundle), "--out", str(out_dir), "--scorer", SCORER_V1]) == 0
    payload = json.loads((out_dir / "bundle.json").read_text())
    assert payload["version"] == SCORER_V1


def test_vo_style_pinned_reference_with_immediate_command_scores_starboard():
    """R11 #1: a pinned route reference with an immediate planner answer.

    The command stream is already post-step at detection; the pre-detection
    baseline falls back to the route reference so the starboard alteration is
    still read.
    """
    own = _commanded((0.0, 0.0), 300.0, lambda _t: 6.0, lambda t: 0.0 if t < 1.0 else 0.6, lambda _t: 0.0)
    incoming = _target(_straight((1200.0, 0.0), -math.pi / 2.0, 5.0, 300.0), 1)
    events = _encounter_events({1: "head_on"}) + [
        {"type": "planner_solved", "sim_time": 0.0, "details": {"planner": {"selected_command": {"course_rad": 0.6}}}}
    ]
    result = score_cell(own, {1: incoming}, scenario_id=None, validation_rule_id=None, events=events)
    record = result["encounters"][0]
    assert record.first_alteration_direction == "starboard"
    assert record.verdict == "COMPLIANT"



def test_first_alteration_at_series_start_uses_first_command_as_baseline() -> None:
    """Detection at t=0.5 with no command history must not score alignment.

    p6c: vo-crossing_give_way cells emit the (starboard) avoidance command from
    the first solve while the applied reference still carries the route ramp,
    so the pre-detection command window was a single route-reference sample and
    the initial route alignment read as a 104 deg port alteration. With no
    pre-detection command history the baseline must fall back to the first
    commanded value instead of the route reference.
    """
    command = np.array([0.8836 if t == 0.0 else 0.1963 for t in np.arange(0.0, 3.5, DT)])
    track = _commanded(
        (0.0, 0.0),
        3.0,
        lambda _t: 7.0,
        lambda _t: 0.0,
        course_ref_fn=lambda t: 0.8836 if t == 0.0 else 0.1963,
    )

    result = first_alteration(
        track,
        index_detect=1,
        thresholds=ScoringThresholds(),
        signal=command,
        baseline_mode="pre_detect",
    )

    # Relative to the pre-encounter heading (psi 0), the starboard command is
    # a starboard alteration — NOT the 104 deg port artifact the route-referenced
    # baseline produced.
    assert result["sustained"] is True
    assert result["direction"] == "starboard"
    assert result["baseline_rad"] == pytest.approx(0.0, abs=1e-6)
