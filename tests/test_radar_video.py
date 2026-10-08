"""Physical/statistical and evidence tests for the separate radar shadow channel."""

import json
from types import SimpleNamespace

import numpy as np
import pytest
from shapely.geometry import box

from colav_simulator.core.radar_calibration import estimate_bias, inspect_recording
from colav_simulator.core.radar_occlusion import enc_land_grid
from colav_simulator.core.radar_video import ca_cfar, decode_video, encode_video
from colav_simulator.core.sensing import RadarXBand, RadarXParams


def test_cfar_false_alarm_rate_in_homogeneous_exponential_noise():
    noise = np.random.default_rng(31).exponential(size=(2000, 256))
    hits, threshold = ca_cfar(noise)
    tested = np.isfinite(threshold)
    expected = np.sum(tested) * 1e-4
    assert abs(np.sum(hits) - expected) < 5 * np.sqrt(expected)
    noise[5, 100] = 1e4
    assert ca_cfar(noise)[0][5, 100]


def test_binary_grid_integrity_and_decode_size_limits():
    grid = np.arange(4096, dtype=np.uint8).reshape(64, 64)
    document = encode_video(grid)
    np.testing.assert_array_equal(decode_video(document), grid)
    with pytest.raises(ValueError, match="hash"):
        decode_video({**document, "sha256": "bad"})
    with pytest.raises(ValueError, match="shape"):
        decode_video({**document, "shape": [100000, 64]})


def test_initial_shadow_scan_is_valid_empty_evidence():
    sensor = RadarXBand()
    sensor.reset(3)
    sensor.generate_measurements(0, [], np.zeros(4))
    video = sensor.scan_document()["shadow_video"]
    assert video["detections"] == []
    assert video["chunk"]["shape"][0] == 0
    assert np.count_nonzero(decode_video(video["checkpoint"])) == 0


def radar(partition) -> dict:
    sensor = RadarXBand(RadarXParams(range_scale_nm=0.75, shadow_video_range_bins=256))
    sensor.reset(9)
    own = np.zeros(4)
    targets = [(7, np.array([500.0, 800.0, 0, 0]), 25, 6)]
    sensor.generate_measurements(0, targets, own)
    for t in partition:
        sensor.generate_measurements(t, targets, own)
    return sensor.scan_document()


def test_spoke_random_field_is_independent_of_tick_partition_and_truth_labels():
    a = radar([0.5, 1, 1.5, 2, 2.5])
    b = radar(np.arange(0.25, 2.51, 0.25))
    np.testing.assert_array_equal(
        decode_video(a["shadow_video"]["checkpoint"]), decode_video(b["shadow_video"]["checkpoint"])
    )
    assert a["shadow_video"]["profile"]["profile_id"] == "simrad_halo24_milliampere_v1"
    assert a["shadow_video"]["detector"]["production_tracker"] is False
    assert all(item["target_hint"] is None for item in a["shadow_video"]["detections"])


def test_shadow_cfar_detects_a_ship_without_known_identity():
    sensor = RadarXBand(RadarXParams(range_scale_nm=0.75, shadow_video_range_bins=256))
    sensor.reset(2)
    own = np.zeros(4)
    targets = [(7, np.array([500.0, 800.0, 0, 0]), 25, 6)]
    sensor.generate_measurements(0, targets, own)
    sensor.generate_measurements(1, targets, own)
    detections = sensor.scan_document()["shadow_video"]["detections"]
    assert any(np.linalg.norm(np.array([p["north_m"], p["east_m"]]) - targets[0][1][:2]) < 40 for p in detections)


def test_recording_inspection_preserves_synthetic_calibration_boundary(tmp_path):
    packet = radar([0.5])
    manifest = {
        "schema_version": "radar-calibration-input@1",
        "source_kind": "synthetic",
        "provenance": {"generator": "test"},
    }
    path = tmp_path / "recording.jsonl"
    path.write_text(json.dumps(manifest) + "\n" + json.dumps(packet) + "\n")
    report = inspect_recording(path)
    assert report["records"] == 1
    assert report["calibration_status"] == "SYNTHETIC_ONLY_REAL_CALIBRATION_PENDING"


def test_bias_estimator_uses_wrapped_bearing_and_never_applies_runtime_settings():
    pairs = [
        {"range_m": 100 + i + 8, "reference_range_m": 100 + i, "bearing_deg": 1, "reference_bearing_deg": 359}
        for i in range(6)
    ]
    report = estimate_bias(pairs, source_kind="synthetic", provenance={"generator": "test"})
    assert report["range_bias_m"] == 8
    assert report["bearing_bias_deg"] == pytest.approx(2)
    assert report["corrected_bearing_rmse_deg"] < 1e-9
    assert report["runtime_applied"] is False


def test_enc_shadow_land_is_in_the_same_projected_frame():
    enc = SimpleNamespace(bbox=(1000, 2000, 3000, 4000), land=SimpleNamespace(geometry=box(1800, 2500, 2300, 3500)))
    grid = enc_land_grid(enc)
    assert grid.is_land(2000, 3000)
    assert not grid.is_land(1400, 2400)
    sensor = RadarXBand(RadarXParams(range_scale_nm=0.75, shadow_video_range_bins=256))
    sensor.reset(8)
    sensor.set_shadow_terrain(grid)
    own = np.array([2800.0, 1600.0, 0, 0])
    sensor.generate_measurements(0, [], own)
    sensor.generate_measurements(2.5, [], own)
    video = sensor.scan_document()["shadow_video"]
    assert video["terrain_source"] == "ENC_LANDMASK"
    assert 0 < video["terrain_coverage"] < 1
    assert sensor._occlusion_grid is None, "legacy sampling geometry remains independent"
