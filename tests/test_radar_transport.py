"""Radar checkpoints stay bounded and nested chart blocks decode without runtime."""

import base64
import hashlib
import json
import zlib
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi.testclient import TestClient

import gui_server.main as gui_main
from colav_simulator.core.radar_video import decode_video
from colav_simulator.core.sensing import RadarXBand, RadarXParams
from colav_simulator.decision_replay.chart import ChartBlockDecoder, pack_chart_record
from gui_server.radar_transport import (
    LIVE_CHECKPOINTS,
    RadarCheckpointCache,
    project_compact_scans,
    project_radar_window,
    project_scans,
)


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


# ── Unity direct radar spoke channel contracts (00-REPORT §2.2, 2026-10-21) ──
# The Unity twin consumes the same envelope as the web PPI: live WS compact-v1
# frames plus content-addressed checkpoint REST pulls. Producer form below is
# simulator.py:_radar_evidence's {**scan_document(), "vessel_id"} — inline
# per-tick `chunk` plus an inline full-revolution `checkpoint` (encode_video).
# 256 range bins keep the fixture light; spokes stay at the real 2048.
@pytest.fixture(scope="module")
def produced_scans() -> list:
    # Target-free revolution: transport contracts depend on the shadow-video
    # container (shape/encoding/checkpoint), not on target detection physics,
    # which is under parallel refinement in sensing.py.
    sensor = RadarXBand(RadarXParams(range_scale_nm=0.75, shadow_video_range_bins=256))
    sensor.reset(11)
    own = np.zeros(4)
    sensor.generate_measurements(0, [], own)
    for t in (0.5, 1.0, 1.5, 2.0, 2.5):  # one full 24 rpm revolution -> real checkpoint
        sensor.generate_measurements(t, [], own)
    document = sensor.scan_document()
    assert document is not None
    return [{**document, "vessel_id": 0}]


def test_compact_scans_projection_strips_inline_raster(produced_scans):
    """Contract 1a (transport layer): the compact projection is reference-only.

    project_compact_scans keeps the scan metadata, swaps the inline
    full-revolution checkpoint for its content-addressed REST reference and
    drops the per-tick chunk raster, without mutating the producer scans.
    """
    projected = project_compact_scans(produced_scans, LIVE_CHECKPOINTS.reference)
    video = projected[0]["shadow_video"]
    assert video["checkpoint"]["url"].startswith("/api/radar/checkpoints/")
    assert "data" not in video["checkpoint"], "full-revolution raster is content-addressed, never inline"
    assert "chunk" not in video, "per-tick raster stays out of the compact frame"
    assert len(json.dumps(projected).encode()) < 128 * 1024, "radar_scans stay far below the 1 MiB WS frame cap"
    assert len(json.dumps(projected).encode()) * 8 < len(json.dumps(produced_scans).encode())
    assert "chunk" in produced_scans[0]["shadow_video"], "producer scans are not mutated"
    assert "data" in produced_scans[0]["shadow_video"]["checkpoint"]


def test_compact_v1_frame_keeps_radar_scans_as_checkpoint_reference(produced_scans):
    """Contract 1b (envelope wiring): compact-v1 frames carry radar_scans.

    GAP, currently red: main.py:274 pops radar_scans from compact entirely
    (added in a814b48f, before Unity had a radar consumer). Minimal fix, once
    main.py ownership allows: replace the ``compact.pop("radar_scans", None)``
    line with ``compact["radar_scans"] = project_compact_scans(payload["radar_scans"],
    LIVE_CHECKPOINTS.reference)`` (empty scans stay absent).
    """
    payload = {"sim_time": 2.5, "truth": [], "radar_scans": produced_scans}
    compact = gui_main._compact_stream_payload(payload, include_static=True)
    assert "radar_scans" in compact, "compact-v1 must carry radar_scans for the Unity spoke channel"
    assert compact["radar_scans"] == project_compact_scans(produced_scans, LIVE_CHECKPOINTS.reference)
    assert len(json.dumps(compact).encode()) < 128 * 1024, "compact frames stay far below the 1 MiB WS cap"


def test_checkpoint_rest_fetch_matches_encode_video_payload_bytes(produced_scans):
    """Contract 2: encode -> reference -> REST fetch is a byte-exact closed loop.

    GET /api/radar/checkpoints/{key} (main.py:2589, thin cache read) must return
    the exact encode_video payload: deflate-base64-u8 bytes whose sha256 pins
    the zlib-decompressed grid, decodable back to the producer checkpoint.
    """
    projected = project_scans(produced_scans, LIVE_CHECKPOINTS.reference)
    producer_video = produced_scans[0]["shadow_video"]
    reference = projected[0]["shadow_video"]["checkpoint"]
    assert reference["url"] == f"/api/radar/checkpoints/{reference['checkpoint_key']}"
    assert "data" not in reference

    http = TestClient(gui_main.app)
    response = http.get(reference["url"])
    assert response.status_code == 200
    fetched = response.json()

    assert fetched["encoding"] == producer_video["checkpoint"]["encoding"] == "deflate-base64-u8"
    assert fetched["data"] == producer_video["checkpoint"]["data"], "fetched bytes equal the producer encode"
    assert fetched["shape"] == producer_video["checkpoint"]["shape"]
    assert fetched["shape"][0] == 2048, "spoke dimension anchors the web/Unity PPI parity check"
    raw = zlib.decompress(base64.b64decode(fetched["data"], validate=True))
    assert hashlib.sha256(raw).hexdigest() == fetched["sha256"] == producer_video["checkpoint"]["sha256"]
    np.testing.assert_array_equal(decode_video(fetched), decode_video(producer_video["checkpoint"]))

    missing = http.get(f"/api/radar/checkpoints/{'0' * 64}")
    assert missing.status_code == 404
    assert missing.json()["detail"] == "RADAR_CHECKPOINT_UNAVAILABLE"


def test_radar_ppi_descriptor_carries_unity_presentation_fields():
    """Contract 3: radar_ppi descriptor feeds the Unity presentation layer.

    Unity needs (nothing missing today; if a field is ever dropped, the uses
    below say what breaks): scan_period_s — sweep phase = sim_time/scan_period
    (same formula as web radar-ppi.js sweepAzimuthRad); spokes — polar render
    texture azimuth dim; range_scales_nm/range_scale_nm — range rings and the
    scale ladder; blind_sectors_deg — stern blind-sector mask (P1 backfills the
    measured width through this same field); blind_ring_m — near blank ring;
    seed — same-seed clutter regeneration for the dual-screen parity (§7.5).
    """
    sensor = RadarXBand(RadarXParams(blind_sectors_deg=((180.0, 5.0),)))
    sensor.reset(3)
    descriptor = sensor.ppi_descriptor()
    assert descriptor["schema_version"] == "radar-ppi@1"
    assert descriptor["scan_period_s"] == pytest.approx(2.5)  # 24 rpm default
    assert descriptor["spokes"] == 2048
    assert descriptor["range_scales_nm"] == [0.75, 1.5, 3.0, 6.0, 12.0, 24.0]
    assert descriptor["range_scale_nm"] in descriptor["range_scales_nm"]
    assert descriptor["blind_sectors_deg"] == [[180.0, 5.0]]
    assert 54.0 <= descriptor["blind_ring_m"] <= 68.0
    assert isinstance(descriptor["seed"], int)

    # Envelope wiring: the duck-typed seam behind main.py:2105, and the
    # radar_ppi top-level key survives the compact-v1 strip list.
    prepared = SimpleNamespace(session=SimpleNamespace(ship_list=[SimpleNamespace(sensors=[sensor])]))
    assert gui_main._radar_ppi_descriptor(prepared) == descriptor
    compact = gui_main._compact_stream_payload({"truth": [], "radar_ppi": descriptor}, include_static=False)
    assert compact["radar_ppi"] == descriptor
