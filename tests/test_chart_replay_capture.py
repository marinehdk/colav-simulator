"""Compact capture keeps recorded chart inputs without raw solver/GNC duplication."""

import gzip
import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

from colav_simulator.decision_replay.bundle import TraceBundle
from colav_simulator.decision_replay.chart import CHART_STORAGE_SCHEMA, ChartBlockDecoder, chart_payload
from colav_simulator.decision_replay.sink import TraceSink, TraceSinkPolicy


def test_chart_capture_preserves_each_frame_inputs_with_bounded_size(tmp_path):
    source = json.loads(
        gzip.decompress((Path(__file__).parent / "fixtures/mid_mpc_ipopt/three_ship_frame.json.gz").read_bytes())
    )
    sink = TraceSink.open(tmp_path, policy=TraceSinkPolicy(capture_profile="chart"))
    try:
        encoded = sink._serialize(SimpleNamespace(**source))
        compact = ChartBlockDecoder().decode(json.loads(encoded))
        assert len(encoded) < len(json.dumps(source).encode()) * 0.4
        for name, ship in source["payload"].items():
            for key in ("state", "csog_state", "waypoints", "do_estimates", "do_covariances", "sensor_measurements"):
                if key in ship:
                    assert compact["payload"][name][key] == ship[key]
            assert "original_gnc" not in compact["payload"][name]
            assert "gnc_balance" not in compact["payload"][name]
        original = source["payload"]["Ship0"]["colav"]["planner"]
        chart = compact["payload"]["Ship0"]["colav"]["planner"]
        assert chart["prediction_render"] == original["prediction_render"]
        assert chart["threat_management"] == original["algorithm_details"]["threat_management"]
        assert "evidence_timeline" not in chart
        assert "accepted_plan_receipt" not in chart.get("algorithm_details", {})
    finally:
        sink.close()


def test_shared_blocks_preserve_changed_prediction_and_random_seek(tmp_path):
    source = json.loads(
        gzip.decompress((Path(__file__).parent / "fixtures/mid_mpc_ipopt/three_ship_frame.json.gz").read_bytes())
    )
    sink = TraceSink.open(tmp_path, policy=TraceSinkPolicy(capture_profile="chart", worker=False))
    expected = []
    for i in range(8):
        row = deepcopy(source)
        row.update(sequence=i + 1, sim_time=i * 0.1)
        row["payload"]["Ship0"]["state"][0] += i
        if i >= 4:
            row["payload"]["Ship0"]["colav"]["planner"]["prediction_render"]["ownship"]["north_m"][0] += 12
        expected.append(chart_payload(row["payload"]))
        sink.append(SimpleNamespace(**row))
    index = sink.close(events=[])
    assert index["state"] == "READY"
    raw = [json.loads(line) for line in gzip.decompress((tmp_path / "decision/frames.jsonl.gz").read_bytes()).splitlines()]
    assert raw[0]["chart_blocks"]
    assert not raw[1]["chart_blocks"]
    assert raw[4]["chart_blocks"]
    assert len(json.dumps(raw[1])) < len(json.dumps(expected[1])) * 0.15
    bundle = TraceBundle(tmp_path)
    assert [frame["payload"] for frame in bundle.frames()] == expected
    assert bundle.frame(7)["payload"] == expected[6]
    first = bundle.frame(1)
    first["payload"]["Ship0"]["colav"]["planner"]["prediction_render"]["ownship"]["north_m"][0] = -1
    assert bundle.frame(1)["payload"] == expected[0]
    assert bundle.frame(2)["payload"] == expected[1]


def test_missing_prediction_block_is_not_trusted(tmp_path):
    path = tmp_path / "decision"
    path.mkdir()
    (path / "frames.jsonl").write_text(
        json.dumps(
            {
                "sequence": 1,
                "sim_time": 0,
                "payload": {"bad": {"$chart_block": "absent"}},
                "storage_schema": CHART_STORAGE_SCHEMA,
            }
        )
        + "\n"
    )
    result = TraceBundle(tmp_path).validate()
    assert result["trusted_frame_count"] == 0
    assert not result["valid"]
