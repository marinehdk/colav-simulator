"""Synthetic-encounter tests for the Woerner-style COLREG compliance scorer."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from tools.original_gnc.colreg_scoring import (
    CROSSING_GIVE_WAY,
    CROSSING_STAND_ON,
    HEAD_ON,
    OVERTAKING,
    ScoringThresholds,
    Track,
    classify_from_events,
    parse_nominal_route,
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
