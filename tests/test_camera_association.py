"""P1-1a review-fix tests: external camera simulation-level association (spec #90).

The terminal review required the YOLO/camera measurement leg to reach the KF
chain through explicit scene assembly (``external_cameras:`` ship sensor key,
radar_x precedent; default off) with radar-generation-fidelity association:

1. camera-only KF scenario: assembled sensor + injected records -> the tracker
   establishes/updates the track; without records it stalls (causality);
2. association gate boundary (inside / outside, parameterized);
3. do_idx semantics: in-gate = associated truth index (absolute NE frame,
   placeholder replaced so the KF association cannot hit the NaN twin),
   out-of-gate = -1 clutter slot;
4. existing scenes unaffected: the key is absent by default and no camera
   sensor is constructed without it.
"""

from __future__ import annotations

import numpy as np
import pytest

from colav_simulator.core.sensing import (
    Config,
    ExternalCameraParams,
    ExternalCameraSensor,
    SensorSuiteBuilder,
)
from colav_simulator.core.tracking.trackers import KF, KFParams, TrackStatus

OWN = np.array([0.0, 0.0, 5.0, 0.0])
TARGET_0 = (0, np.array([500.0, 120.0, 0.0, 0.0]), 20.0, 6.0)
TARGET_1 = (1, np.array([300.0, -80.0, 0.0, 0.0]), 15.0, 5.0)


def record(north: float, east: float, t_s: float = 1.0, confidence: float = 0.8) -> dict:
    return {
        "position_ne_m": [north, east],
        "position_cov_ne_m2": [[36.0, 0.0], [0.0, 121.0]],
        "confidence": confidence,
        "class_name": "boat",
        "t_s": t_s,
    }


def build_camera_only_sensor(gate_m: float = 50.0) -> ExternalCameraSensor:
    """Assemble the camera-only sensor suite exactly as the scene key would."""
    config = Config.from_dict([{"external_cameras": {"association_gate_m": gate_m}}])
    sensors = SensorSuiteBuilder.construct_sensors(config)
    assert len(sensors) == 1 and isinstance(sensors[0], ExternalCameraSensor)
    return sensors[0]


def run_two_cycles(sensor: ExternalCameraSensor, truth: list, records: list[dict]) -> list:
    """Slot-creation cycle, then the fed cycle (the KF creates before updating)."""
    tracker = KF(sensor_list=[sensor], params=KFParams())
    tracker.track(0.5, 0.5, truth, OWN)
    if records:
        sensor.submit(records, frame_seq=1)
    tracks, measurements = tracker.track(1.0, 0.5, truth, OWN)
    return tracks, measurements, tracker


# ── 1. camera-only KF scenario: feed in -> track updated; feed off -> stalled ─


def test_camera_feed_establishes_and_updates_the_kf_track() -> None:
    sensor = build_camera_only_sensor()
    # In-gate record for target 0 (2 m off truth): track updates through the
    # camera channel alone — the assembled sensor is the only measurement souce.
    tracks, measurements, tracker = run_two_cycles(sensor, [TARGET_0], [record(501.0, 119.0)])
    snapshot = tracks[0]
    assert snapshot.status is TrackStatus.UPDATED
    assert any(source.sensor_id == 2 for source in snapshot.sources), "camera_eo channel credited"
    assert np.isfinite(tracker._NIS[0]), "KF innovation computed on the camera measurement"
    assert snapshot.existence_prob > KFParams().p_exist_init, "association confirms existence"
    associated = [z for do_idx, z in measurements[0] if do_idx == 0]
    assert len(associated) == 1 and np.allclose(associated[0], [501.0, 119.0])


def test_camera_sensor_only_kf_causality_no_feed_no_update() -> None:
    sensor = build_camera_only_sensor()
    # No records at all: the label slot exists (GT within the sensor envelope —
    # the KF's god-labelled slot convention) but never updates: coasting, no
    # camera source, existence decays strictly. No camera measurement -> no
    # camera-sourced track.
    tracker = KF(sensor_list=[sensor], params=KFParams())
    tracker.track(0.5, 0.5, [TARGET_0], OWN)
    existence = None
    for cycle in range(2, 8):
        tracks, _measurements = tracker.track(0.5 + cycle * 0.5, 0.5, [TARGET_0], OWN)
        snapshot = tracks[0]
        assert snapshot.status is TrackStatus.COASTING
        assert not snapshot.sources, "no camera contribution without records"
        assert all(np.isnan(nis) or not np.isfinite(nis) for nis in tracker._NIS)
        existence = snapshot.existence_prob if existence is None else existence
        assert snapshot.existence_prob < existence or existence == snapshot.existence_prob
        existence = min(existence, snapshot.existence_prob)
    assert existence < KFParams().p_exist_init, "existence decays without the feed"


def test_sensor_is_not_bypass_fusion_and_enters_the_measurement_loop() -> None:
    sensor = build_camera_only_sensor()
    assert sensor.bypass_fusion is False, "camera_eo/ir fuse (contract §2)"
    tracker = KF(sensor_list=[sensor], params=KFParams())
    tracker.track(0.5, 0.5, [TARGET_0], OWN)
    assert len(tracker._recent_sensor_measurements) == 1, "camera-only suite: one measurement group"


# ── 2. association gate boundary (inside / outside; parameterized) ────────────


@pytest.mark.parametrize("gate_m", [50.0, 12.0])
def test_sensor_association_gate_boundary(gate_m: float) -> None:
    sensor = build_camera_only_sensor(gate_m=gate_m)
    inside = gate_m - 1.0  # clearly in
    outside = gate_m + 1.0  # clearly out
    truth_ne = np.asarray(TARGET_0[1])[:2]
    tracks, measurements, _tracker = run_two_cycles(
        sensor,
        [TARGET_0],
        [record(*(truth_ne + np.array([inside, 0.0]))), record(*(truth_ne + np.array([0.0, outside])))],
    )
    groups = measurements[0]
    in_gate = [z for do_idx, z in groups if do_idx == 0 and not np.isnan(z).any()]
    clutter = [z for do_idx, z in groups if do_idx == -1]
    assert len(in_gate) == 1, "inside-gate record associated"
    assert np.allclose(in_gate[0], truth_ne + np.array([inside, 0.0]))
    assert len(clutter) == 1 and np.allclose(clutter[0], truth_ne + np.array([0.0, outside])), (
        "outside-gate record kept the clutter slot"
    )
    assert tracks[0].status is TrackStatus.UPDATED


def test_sensor_gate_disabled_puts_everything_in_the_clutter_slot() -> None:
    sensor = build_camera_only_sensor(gate_m=0.0)
    _tracks, measurements, _tracker = run_two_cycles(sensor, [TARGET_0], [record(500.0, 120.0)])
    assert all(do_idx == 0 and np.isnan(z).any() for do_idx, z in measurements[0] if do_idx == 0)
    assert any(do_idx == -1 and np.allclose(z, [500.0, 120.0]) for do_idx, z in measurements[0]), (
        "gate <= 0 disables association entirely (legacy clutter behaviour)"
    )


# ── 3. do_idx semantics: nearest truth, absolute frame, non-shadowing ─────────


def test_sensor_do_idx_semantics_nearest_truth_absolute_frame() -> None:
    sensor = build_camera_only_sensor(gate_m=50.0)
    # Record near target 1 (do_idx=1), not target 0: the association must pick
    # the nearest truth and emit on ITS index; the z is absolute NE (ownship at
    # the origin here, so relative == absolute — a second record set with a
    # displaced ownship verifies the frame below).
    tracks, measurements, _tracker = run_two_cycles(
        sensor, [TARGET_0, TARGET_1], [record(302.0, -78.0)]
    )
    groups = measurements[0]
    slot_1 = [z for do_idx, z in groups if do_idx == 1 and not np.isnan(z).any()]
    slot_0 = [z for do_idx, z in groups if do_idx == 0]
    assert len(slot_1) == 1 and np.allclose(slot_1[0], [302.0, -78.0]), "associated onto do_idx=1"
    assert len(slot_0) == 1 and np.isnan(slot_0[0]).any(), "unassociated target keeps its NaN placeholder"
    assert tracks[0].status is TrackStatus.UPDATED


def test_sensor_associated_z_is_absolute_ne_not_ownship_relative() -> None:
    sensor = build_camera_only_sensor(gate_m=50.0)
    displaced_own = np.array([10_000.0, -5_000.0, 5.0, 0.0])
    target = (0, displaced_own + np.array([500.0, 120.0, 0.0, 0.0]), 20.0, 6.0)
    tracker = KF(sensor_list=[sensor], params=KFParams())
    tracker.track(0.5, 0.5, [target], displaced_own)
    sensor.submit([record(500.0, 120.0)], frame_seq=7)
    _tracks, measurements = tracker.track(1.0, 0.5, [target], displaced_own)
    slot_0 = [z for do_idx, z in measurements[0] if do_idx == 0 and not np.isnan(z).any()]
    assert slot_0 and np.allclose(slot_0[0], [10_500.0, -4_880.0]), (
        "z = ownship + relative georef NE (radar absolute-frame convention)"
    )


def test_sensor_two_records_on_one_target_replace_not_shadow() -> None:
    sensor = build_camera_only_sensor(gate_m=50.0)
    _tracks, measurements, _tracker = run_two_cycles(
        sensor, [TARGET_0], [record(499.0, 121.0), record(503.0, 117.0)]
    )
    slot_0 = [z for do_idx, z in measurements[0] if do_idx == 0 and not np.isnan(z).any()]
    assert len(slot_0) == 1, "the do_idx slot holds exactly one finite measurement"


# ── 4. default-off discipline: no scene key, no camera sensor ─────────────────


def test_scene_key_absent_by_default_no_camera_sensor_built() -> None:
    config = Config.from_dict([{"radar_x": {}}])
    sensors = SensorSuiteBuilder.construct_sensors(config)
    assert not any(isinstance(sensor, ExternalCameraSensor) for sensor in sensors), (
        "existing scenes assemble no camera sensor (default tracker behaviour untouched)"
    )


def test_external_camera_sensor_scene_key_round_trip() -> None:
    config = Config.from_dict(
        [{"external_cameras": {"sensor_id": 3, "max_range_m": 1500.0, "association_gate_m": 42.0}}]
    )
    params = config.sensor_list[0]
    assert isinstance(params, ExternalCameraParams)
    assert params.sensor_id == 3 and params.max_range_m == 1500.0 and params.association_gate_m == 42.0
    round_trip = Config.from_dict(config.to_dict_list())
    assert round_trip.sensor_list[0] == params, "to_dict_list/from_dict round trip preserves the key"
