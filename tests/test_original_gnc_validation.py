"""False-positive guards for the original-vs-embedded acceptance comparator."""

import gzip
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pytest

from colav_simulator.original_gnc.output_comparison import compare_outputs
from colav_simulator.original_gnc.state_comparison import compare_state
from colav_simulator.original_gnc.validation import FIELD_RULES, compare_trace
from tools.original_gnc.compare_navigation import compare, performance

BASE = {
    "event": "plant",
    "tick": 1,
    "north_m": 100.0,
    "east_m": 4.0,
    "heading_rad": math.pi - 1e-10,
    "surge_n": 20000.0,
    "mode": "TRANSIT",
}
RULES = {name: FIELD_RULES[name] for name in BASE if name not in {"event", "tick"}}


@pytest.mark.parametrize(
    "update,kind",
    [
        ({"north_m": 4.0, "east_m": 100.0}, "numerical_difference"),
        ({"surge_n": 20.0}, "numerical_difference"),
        ({"heading_rad": 180.0}, "numerical_difference"),
        ({"tick": 2}, "event_identity"),
        ({"mode": "DP"}, "discrete_difference"),
        ({"east_m": None}, "missing_field"),
        ({"surge_n": float("nan")}, "nonfinite_or_nonnumeric"),
    ],
)
def test_comparator_rejects_semantic_corruption(update, kind):
    result = compare_trace([BASE], [{**BASE, **update}], RULES)
    assert not result["passed"]
    assert result["first_difference"]["kind"] == kind


def test_empty_missing_and_truncated_traces_never_pass():
    for left, right in (([], []), ([BASE], []), ([BASE], [{"event": "plant", "tick": 1}])):
        assert not compare_trace(left, right, RULES)["passed"]


def test_circular_angle_crossing_and_small_roundoff_pass():
    actual = {**BASE, "heading_rad": -math.pi - 1e-10, "north_m": 100.0 + 1e-7}
    assert compare_trace([BASE], [actual], RULES)["passed"]


def test_discrete_booleans_cannot_be_replaced_by_numeric_one():
    left = {"event": "route", "tick": 0, "accepted": True}
    right = {**left, "accepted": 1}
    assert not compare_trace([left], [right], {"accepted": FIELD_RULES["accepted"]})["passed"]


@pytest.mark.parametrize(
    "expected,actual",
    [
        ({"actuators": []}, {}),
        ({"actuators": []}, {"actuators": {}}),
        ({"actuators": [{}]}, {"actuators": []}),
        ({"a.b": 1, "a": {"b": 2}}, {"a.b": 2, "a": {"b": 2}}),
    ],
)
def test_state_comparison_rejects_structure_loss(expected, actual):
    assert not compare_state("ship_dynamics_node", expected, actual)["passed"]


def test_state_comparison_preserves_identical_empty_collection():
    assert compare_state("ship_dynamics_node", {"actuators": []}, {"actuators": []})["passed"]
    assert not compare_state("ship_dynamics_node", {}, {})["passed"]


def test_matching_nulls_cannot_masquerade_as_finite_physical_state():
    assert not compare_state("ship_dynamics_node", {"eta": [None]}, {"eta": [None]})["passed"]


def test_matching_null_message_fields_cannot_pass():
    message = {"port": "speed_pub_", "message": {"type": "std_msgs/msg/Float64", "fields": {"data": None}}}
    assert not compare_outputs([message], [message])["passed"]


@pytest.mark.parametrize("corruption", [None, "position", "missing_sample", "nan", "waypoint", "route_event"])
def test_common_schedule_gate_rejects_missing_or_changed_navigation(tmp_path, corruption):
    """A passing aggregate must preserve all samples and source mode evidence."""
    epoch = 2_000_000_000_000_000_000
    times = np.array([epoch + 20_000_000, epoch + 40_000_000], dtype=np.int64)
    case = {"case_id": "comparator-contract", "waypoints": [{"north_m": 0, "east_m": 0}, {"north_m": 20, "east_m": 0}]}
    for name in ("source", "embedded"):
        directory = tmp_path / name
        directory.mkdir()
        data = {
            "epoch_ns": np.asarray(epoch, dtype=np.int64),
            "navigation": np.array([[0.02, 0, 0, 1, 0, 0, 0], [0.04, 0, 0, 1, 0, 0, 0]]),
            "commands": np.zeros((2, 14)),
            "allocation": np.zeros((2, 3)),
            "dp_hold": np.zeros((2, 1)),
            "guidance": np.array([[1.0, 0, 0], [1.0, 0, 0]]),
        }
        for key in tuple(data):
            if key != "epoch_ns":
                data[key + "_time_ns"] = times.copy()
        events = [{"time_ns": epoch, "topic": "/gnc/route_execution_status", "message": {"accepted": True}}]
        if name == "embedded":
            if corruption == "position":
                data["navigation"][1, 0] += 0.2
            elif corruption == "missing_sample":
                data["navigation"] = data["navigation"][1:]
                data["navigation_time_ns"] = times[1:]
            elif corruption == "nan":
                data["navigation"][1, 0] = np.nan
            elif corruption == "waypoint":
                data["guidance"][1, 0] = 2
            elif corruption == "route_event":
                events = []
        np.savez_compressed(directory / "samples.npz", **data)
        manifest = {
            "kind": "original_source_coupled" if name == "source" else "embedded",
            "route_events": events,
            "samples_sha256": hashlib.sha256((directory / "samples.npz").read_bytes()).hexdigest(),
        }
        (directory / "manifest.json").write_text(json.dumps(manifest))
        (directory / "case.json").write_text(json.dumps(case))
    result = compare(tmp_path / "source", tmp_path / "embedded", tmp_path / "result", common_schedule=True)
    assert result["passed"] is (corruption is None)


def test_original_route_boundary_vectors_reach_the_intended_guards():
    """Require observed source branch coverage, not only labels on inputs."""
    root = Path(__file__).parent / "fixtures/original_gnc/reference_route_boundary_vectors_v2"
    vectors = {
        node: json.loads(gzip.decompress((root / f"{node}.json.gz").read_bytes()))
        for node in ("coordinate_transform_node", "active_route_manager_node")
    }
    statuses = {}
    for vector in vectors.values():
        for call in vector["calls"]:
            for output in call["outputs"]:
                fields = output["message"]["fields"]
                if "accepted" in fields:
                    statuses.setdefault(fields.get("route_id", fields.get("plan_id")), []).append(fields)
    below, above = statuses["future-aligned-0"][0], statuses["future-aligned-2"][0]
    assert below["first_changed_distance_ahead_m"] < 500.0 < above["first_changed_distance_ahead_m"]
    assert below["accepted"] is False
    assert below["reason"] == "first changed waypoint is too close to current ship position"
    assert above["accepted"] is True
    short = statuses["segment-manager-0"][0]
    assert short["accepted"] is False and short["reason"] == "segment_too_short"
    assert short["available_decel_distance_m"] < 30.0
    assert statuses["segment-manager-2"][0]["accepted"] is True
    duplicates = statuses["byte-identical-plan"]
    assert len(duplicates) == 2 and all(status["accepted"] for status in duplicates)
    calls = vectors["active_route_manager_node"]["calls"]
    duplicate_inputs = [call["input"] for call in calls if (call["input"] or {}).get("plan_id") == "byte-identical-plan"]
    assert len(duplicate_inputs) == 2 and duplicate_inputs[0] == duplicate_inputs[1]


def test_allocation_occupancy_uses_its_own_observed_interval():
    """A later allocation publication is valid; a reversed allocation clock is not."""
    data = {
        "epoch_ns": np.asarray(0, dtype=np.int64),
        "navigation": np.array([[0.02, 0, 0, 1, 0, 0, 0], [0.04, 0, 0, 1, 0, 0, 0]]),
        "navigation_time_ns": np.array([20_000_000, 40_000_000]),
        "commands": np.zeros((2, 14)),
        "allocation": np.array([[2, 0, 1], [3, 0, 1]]),
        "allocation_time_ns": np.array([10_000_000, 50_000_000]),
        "dp_hold": np.zeros((2, 1)),
        "dp_hold_time_ns": np.array([20_000_000, 40_000_000]),
    }
    case = {"waypoints": [{"north_m": 0, "east_m": 0}, {"north_m": 20, "east_m": 0}]}
    result = performance(data, case)
    assert result["allocation_observed_span_s"] == pytest.approx(0.04)
    assert result["allocation_last_sample_minus_navigation_last_s"] == pytest.approx(0.01)
    assert result["allocation_level2_fraction"] == 1.0
    assert result["allocation_level3_fraction"] == 0.0
    data["allocation_time_ns"] = data["allocation_time_ns"][::-1]
    with pytest.raises(ValueError, match="Nonmonotonic allocation clock"):
        performance(data, case)
