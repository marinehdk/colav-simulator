"""Radar checkpoints stay bounded and nested chart blocks decode without runtime."""

import json

import pytest

from colav_simulator.decision_replay.chart import ChartBlockDecoder, pack_chart_record
from gui_server.radar_transport import RadarCheckpointCache, project_radar_window


def test_live_checkpoint_cache_is_bounded_and_ref_has_no_float_grid():
    cache = RadarCheckpointCache()
    references = [cache.reference({"data": str(i), "sha256": str(i)}) for i in range(17)]
    assert cache.get(references[0]["checkpoint_key"]) is None
    assert cache.get(references[-1]["checkpoint_key"])["data"] == "16"
    assert "data" not in references[-1]


def test_sealed_window_deduplicates_checkpoints_without_mutating_source():
    scan = {"shadow_video": {"checkpoint": {"data": "encoded", "sha256": "hash"}}}
    frames = [{"payload": {"Ship0": {"radar_scans": [scan]}}} for _ in range(3)]
    document = {"frames": frames}
    projected = project_radar_window(document)
    assert len(projected["radar_checkpoints"]) == 1
    assert scan["shadow_video"]["checkpoint"]["data"] == "encoded"
    assert "$radar_checkpoint" in projected["frames"][0]["payload"]["Ship0"]["radar_scans"][0]["shadow_video"]["checkpoint"]


def test_chart_capture_expands_nested_radar_checkpoint_references():
    checkpoint = {"data": "binary", "sha256": "hash"}
    record = {
        "payload": {"Ship0": {"colav": {"planner": {}}, "radar_scans": [{"shadow_video": {"checkpoint": checkpoint}}]}}
    }
    pack_chart_record(record, set(), lambda data: json.dumps(data, sort_keys=True).encode())
    decoded = ChartBlockDecoder().decode(record)
    assert decoded["payload"]["Ship0"]["radar_scans"][0]["shadow_video"]["checkpoint"] == checkpoint


def test_cyclic_chart_blocks_are_rejected():
    decoder = ChartBlockDecoder()
    document = {
        "storage_schema": "colav.chart-blocks.v1",
        "chart_blocks": {"x": {"$chart_block": "x"}},
        "value": {"$chart_block": "x"},
    }
    with pytest.raises(ValueError, match="cyclic"):
        decoder.decode(document)
