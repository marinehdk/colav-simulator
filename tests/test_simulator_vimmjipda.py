import numpy as np
import pytest

from colav_simulator.core.sensing import Radar, RadarParams
from colav_simulator.core.tracking.trackers import TrackSnapshot
from colav_simulator.integrations import IntegrationRegistry


def test_vimmjipda_config_is_project_resolved_when_available() -> None:
    registry = IntegrationRegistry()
    status = registry.statuses()["vimmjipda"]
    if not status.available:
        assert status.reason
        return
    tracker = registry.build_tracker("vimmjipda")
    assert tracker is not None
    assert hasattr(tracker, "track")
    assert hasattr(tracker, "reset")


def test_vimmjipda_snapshots_carry_existence_probability_when_available() -> None:
    """P3-S5 breakpoint ①: the external IPDA existence recursion surfaces on TrackSnapshot."""
    registry = IntegrationRegistry()
    status = registry.statuses()["vimmjipda"]
    if not status.available:
        pytest.skip("vimmjipda external repo unavailable")
    tracker = registry.build_tracker("vimmjipda")
    radar = Radar(RadarParams(max_range=2000.0, generate_clutter=False))
    radar.seed(11)
    tracker.set_sensor_list([radar])

    ownship = np.zeros(4)
    target = (7, np.array([800.0, 0.0, -2.0, 0.0]), 30.0, 7.0)
    tracks = []
    for step in range(20):
        tracks, _ = tracker.track(step * 0.5, 0.5, [target], ownship)

    assert tracks
    for track in tracks:
        assert isinstance(track, TrackSnapshot)
        assert track.source == "vimmjipda"
        assert 0.0 <= track.existence_prob <= 1.0
        assert track.sources and track.sources[0].sensor_id == 1
    # The wrapped external manager holds the same existence value.
    manager_tracks = getattr(tracker.inner._manager, "tracks", ())
    manager_track = next(iter(manager_tracks), None)
    if manager_track is not None:
        assert tracks[0].existence_prob == pytest.approx(float(manager_track.existence_probability))

    snapshots, nises = tracker.get_track_information(ownship)
    assert all(isinstance(snapshot, TrackSnapshot) for snapshot in snapshots)
    assert len(nises) == len(snapshots)

    tracker.reset()
    assert tracker.get_track_information(ownship)[0] == []
