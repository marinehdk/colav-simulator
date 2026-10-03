"""Spec #91 item 1: vimmjipda multi-source fusion wiring (radar_x + camera).

The external tracker interface previously filtered its measurement loop on
``isinstance(sensor, cs_sensing.Radar)``, so RadarXBand / ExternalCameraSensor
assembled sessions fed the vimmjipda manager nothing. The external repo
(local commit 58e4903, additive) now accepts sensors through a capability
check — legacy Radar path unchanged, plus any sensor declaring the
``provides_ne_position_measurements`` flag (set on RadarXBand and
ExternalCameraSensor in core/sensing.py).

Integration proofs (tracker-level, simulator guidance/controller out of the
loop, same harness shape as tests/test_simulator_vimmjipda.py):

1. radar_x leg: seeded RadarXBand -> non-zero accepted measurement count and
   a manager track gating on the truth (clutter-born extra tracks are the
   JPDA's own business, not gated here);
2. camera leg: ExternalCameraSensor fed synthetic georeferenced observations
   (the ``external_cameras:`` assembly product) -> associated measurement
   count > 0 and a confirmed track on the truth path;
3. mixed leg: radar_x + camera credited as channels (1, 2) on snapshots;
4. legacy Radar leg unchanged: radar-only sessions keep sensor_id=1 credit
   (the pre-wiring contract pinned by tests/test_simulator_vimmjipda.py).
"""

from __future__ import annotations

import numpy as np
import pytest

from colav_simulator.core.sensing import ExternalCameraSensor, Radar, RadarParams, RadarXBand
from colav_simulator.integrations.registry import IntegrationRegistry

TRUTH_0 = np.array([600.0, 100.0, -2.0, 0.4])
OWN = np.zeros(4)
GATE_M = 120.0


@pytest.fixture(scope="module")
def fusion_available() -> bool:
    status = IntegrationRegistry().statuses()["vimmjipda"]
    if not status.available:
        pytest.skip("vimmjipda external repo unavailable")
    return True


def camera_record(north: float, east: float, t_s: float) -> dict:
    """One georeferenced observations-endpoint record (ownship-relative NE)."""
    return {
        "position_ne_m": [north, east],
        "position_cov_ne_m2": [[36.0, 0.0], [0.0, 121.0]],
        "confidence": 0.9,
        "class_name": "boat",
        "t_s": t_s,
    }


def run_leg(tracker, sensor, *, steps: int = 40, feed_camera: bool = False) -> tuple[int, list]:
    """Drive one tracker-level leg; returns (accepted meas count, final tracks)."""
    tracker.set_sensor_list([sensor])
    accepted = 0
    tracks = []
    for step in range(1, steps + 1):
        t = step * 0.5
        truth = TRUTH_0.copy()
        truth[:2] += truth[2:] * t
        if feed_camera and step > 1:
            sensor.submit([camera_record(truth[0], truth[1], t)], frame_seq=step)
        tracks, sensor_measurements = tracker.track(t, 0.5, [(7, truth, 30.0, 7.0)], OWN)
        accepted += sum(
            1
            for frame in sensor_measurements
            for meas_tup in frame
            if meas_tup[0] >= 0 and not np.any(np.isnan(meas_tup[1]))
        )
    return accepted, tracks


def gating_tracks(tracks, truth: np.ndarray, gate_m: float = GATE_M) -> list:
    return [track for track in tracks if np.linalg.norm(track.state[:2] - truth[:2]) <= gate_m]


def test_vimmjipda_radar_x_leg_reaches_the_manager(fusion_available: bool) -> None:
    """radar_x measurements enter the external manager: meas count > 0 and a track gates on truth."""
    tracker = IntegrationRegistry().build_tracker("vimmjipda")
    radar_x = RadarXBand()
    radar_x.seed(5)
    accepted, tracks = run_leg(tracker, radar_x)
    truth = TRUTH_0[:2] + TRUTH_0[2:] * 20.0
    assert accepted > 0, "radar_x measurements never reached the vimmjipda step chain"
    assert gating_tracks(tracks, truth), "no manager track near the radar_x-tracked truth"
    # Sensor-model-v1 credit: the radar_x channel (id 1) is the wired source.
    assert all(source.sensor_id == 1 for track in gating_tracks(tracks, truth) for source in track.sources)
    tracker.reset()


def test_vimmjipda_camera_leg_reaches_the_manager(fusion_available: bool) -> None:
    """Synthetic observation records through the assembled camera: meas count > 0 and a confirmed track."""
    tracker = IntegrationRegistry().build_tracker("vimmjipda")
    camera = ExternalCameraSensor()
    accepted, tracks = run_leg(tracker, camera, feed_camera=True)
    truth = TRUTH_0[:2] + TRUTH_0[2:] * 20.0
    assert accepted > 0, "camera observation records never reached the vimmjipda step chain"
    gated = gating_tracks(tracks, truth)
    assert gated, "no manager track near the camera-tracked truth"
    assert any(track.existence_prob > 0.9 for track in gated), "camera-fed track never confirmed"
    # The camera channel (sensor_id=2) is credited on the fused snapshots.
    assert all(source.sensor_id == 2 for track in gated for source in track.sources)
    tracker.reset()


def test_vimmjipda_mixed_leg_credits_both_channels(fusion_available: bool) -> None:
    """radar_x + camera assemblies are credited as channels (1, 2) on the snapshots."""
    tracker = IntegrationRegistry().build_tracker("vimmjipda")

    class _Both:
        sensors = [RadarXBand(), ExternalCameraSensor()]

    radar_x, camera = _Both.sensors
    radar_x.seed(5)
    tracker.set_sensor_list(_Both.sensors)
    credited = tracker._credited_sensor_ids()
    assert credited == (1, 2), "mixed radar_x + camera assembly must credit both channels"


def test_vimmjipda_legacy_radar_leg_unchanged(fusion_available: bool) -> None:
    """Radar-only sessions keep the exact pre-wiring behaviour (radar_id=1 credit, tracking works)."""
    tracker = IntegrationRegistry().build_tracker("vimmjipda")
    radar = Radar(RadarParams(max_range=2000.0, generate_clutter=False))
    radar.seed(11)
    accepted, tracks = run_leg(tracker, radar, steps=20)
    truth = TRUTH_0[:2] + TRUTH_0[2:] * 10.0
    assert accepted > 0
    assert gating_tracks(tracks, truth)
    assert all(source.sensor_id == 1 for track in gating_tracks(tracks, truth) for source in track.sources)
    tracker.reset()
