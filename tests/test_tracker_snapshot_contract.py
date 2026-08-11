import numpy as np

from colav_simulator.core.tracking.trackers import GodTracker, TrackKey, TrackSnapshot, TrackStatus


def _target(target_id: int, north_m: float) -> tuple[int, np.ndarray, float, float]:
    return target_id, np.array([north_m, 0.0, 2.0, 0.0]), 30.0, 7.0


def test_god_tracker_owns_generation_and_observation_provenance() -> None:
    tracker = GodTracker([])
    ownship = np.zeros(4)

    initial, _ = tracker.track(0.0, 0.1, [_target(7, 100.0)], ownship)
    assert len(initial) == 1
    first = initial[0]
    assert isinstance(first, TrackSnapshot)
    assert first.key == TrackKey(target_id=7, generation=1)
    assert first.status is TrackStatus.UPDATED
    assert first.observed_at_s == 0.0
    assert first.generated_at_s == 0.0
    assert first.age_s == 0.0
    assert first.source == "god"

    tracker.track(1.0, 0.1, [], ownship)
    recreated, _ = tracker.track(2.0, 0.1, [_target(7, 120.0)], ownship)
    assert recreated[0].key == TrackKey(target_id=7, generation=2)
    assert recreated[0].observed_at_s == 2.0

    # Existing tuple consumers remain valid during the contract migration.
    target_id, state, covariance, length_m, width_m = recreated[0]
    assert target_id == 7
    np.testing.assert_array_equal(state, _target(7, 120.0)[1])
    np.testing.assert_array_equal(covariance, np.zeros((4, 4)))
    assert (length_m, width_m) == (30.0, 7.0)
