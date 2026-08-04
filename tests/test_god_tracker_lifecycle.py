import numpy as np

from colav_simulator.core.tracking.trackers import GodTracker


def _target(target_id: int, north: float) -> tuple[int, np.ndarray, float, float]:
    return target_id, np.array([north, 0.0, 2.0, 0.0]), 30.0, 7.0


def _by_id(tracks: list[tuple]) -> dict[int, np.ndarray]:
    return {track[0]: track[1] for track in tracks}


def test_god_tracker_removes_inactive_target_without_reassigning_ids() -> None:
    tracker = GodTracker([])
    ownship = np.zeros(4)

    initial, _ = tracker.track(0.0, 0.1, [_target(1, 100.0), _target(2, 200.0), _target(3, 300.0)], ownship)
    assert set(_by_id(initial)) == {1, 2, 3}

    active, _ = tracker.track(1.0, 0.1, [_target(2, 210.0), _target(3, 310.0)], ownship)
    active_by_id = _by_id(active)
    assert set(active_by_id) == {2, 3}
    np.testing.assert_array_equal(active_by_id[2], _target(2, 210.0)[1])
    np.testing.assert_array_equal(active_by_id[3], _target(3, 310.0)[1])

    snapshot, _ = tracker.get_track_information(ownship)
    assert set(_by_id(snapshot)) == {2, 3}


def test_god_tracker_active_count_only_decreases_when_targets_expire() -> None:
    tracker = GodTracker([])
    ownship = np.zeros(4)
    snapshots = (
        (0.0, [_target(1, 100.0), _target(2, 200.0), _target(3, 300.0)]),
        (1.0, [_target(2, 210.0), _target(3, 310.0)]),
        (2.0, [_target(3, 320.0)]),
        (3.0, []),
    )

    counts = []
    labels = []
    for t, targets in snapshots:
        tracks, _ = tracker.track(t, 0.1, targets, ownship)
        counts.append(len(tracks))
        labels.append([track[0] for track in tracks])

    assert counts == [3, 2, 1, 0]
    assert labels == [[1, 2, 3], [2, 3], [3], []]
    assert tracker.get_track_information(ownship)[0] == []
