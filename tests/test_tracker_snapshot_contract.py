import numpy as np
import pytest

from colav_simulator.core.tracking.trackers import (
    GodTracker,
    KF,
    KFParams,
    TrackKey,
    TrackSnapshot,
    TrackSource,
    TrackStatus,
    track_key_sort,
    track_quality,
)


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


def test_track_key_sort_keeps_target_then_generation_ordering_golden() -> None:
    keys = (TrackKey(8, 2), TrackKey(3, 4), TrackKey(8, 1), TrackKey(3, 1))

    assert tuple(sorted(keys, key=track_key_sort)) == (
        TrackKey(3, 1),
        TrackKey(3, 4),
        TrackKey(8, 1),
        TrackKey(8, 2),
    )


# ══ P3-S5 (spec #90): existence probability as an interface first-class citizen ══


def test_god_tracker_pins_certain_existence_on_interface_and_snapshots() -> None:
    """Breakpoint ①: get_track_information carries existence via TrackSnapshot."""
    tracker = GodTracker([])
    ownship = np.zeros(4)
    tracker.track(0.0, 0.1, [_target(7, 100.0)], ownship)

    snapshots, nises = tracker.get_track_information(ownship)
    assert len(snapshots) == 1 and len(nises) == 1
    # Truth = certain existence (semantic pin; the GodTracker copies truth).
    assert snapshots[0].existence_prob == 1.0
    assert snapshots[0].quality == 1.0
    assert snapshots[0].sources == ()


def test_kf_existence_recursion_recovers_on_update_and_decays_on_coast() -> None:
    class _StaticSensor:
        type = "radar"
        bypass_fusion = False
        max_range = 2000.0

        @staticmethod
        def R(xs):
            return np.diag([25.0, 25.0])

        @staticmethod
        def H(xs):
            return np.array([[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]])

        @staticmethod
        def h(xs):
            return xs[:2]

        @staticmethod
        def generate_measurements(t, true_do_states, ownship_state):
            return [(do_idx, do_state[:2].copy()) for do_idx, do_state, _, _ in true_do_states]

    sensor = _StaticSensor()
    tracker = KF([sensor], KFParams(p_survival=0.98, p_detection=0.9, p_exist_init=0.5))
    ownship = np.zeros(4)
    target = (7, np.array([300.0, 0.0, -2.0, 0.0]), 30.0, 7.0)

    first, _ = tracker.track(0.0, 1.0, [target], ownship)
    # New track seeds at p_exist_init before any update.
    assert first[0].existence_prob == pytest.approx(0.5)

    updated, _ = tracker.track(1.0, 1.0, [target], ownship)
    assert updated[0].existence_prob == pytest.approx(0.5 + 0.9 * 0.5)
    assert updated[0].status is TrackStatus.UPDATED
    assert updated[0].sources == (TrackSource(sensor_id=1, last_seen_age_s=0.0),)

    coasted = updated
    for step in range(2, 6):
        coasted, _ = tracker.track(float(step), 1.0, [], ownship)
    expected = 0.98**4 * (0.5 + 0.9 * 0.5)
    assert coasted[0].existence_prob == pytest.approx(expected)
    assert coasted[0].status is TrackStatus.COASTING
    # Sources persist with a growing age after the contributing update.
    assert coasted[0].sources[0].sensor_id == 1
    assert coasted[0].sources[0].last_seen_age_s == pytest.approx(4.0)


def test_kf_params_roundtrip_keeps_legacy_documents_loadable() -> None:
    legacy = KFParams.from_dict({"P_0": [49.0, 49.0, 0.5, 0.5], "q": 0.4})
    assert legacy.p_survival == 0.98 and legacy.p_detection == 0.9 and legacy.p_exist_init == 0.5
    restored = KFParams.from_dict(KFParams().to_dict())
    assert np.array_equal(restored.P_0, KFParams().P_0)
    assert (restored.q, restored.p_survival, restored.p_detection, restored.p_exist_init) == (0.4, 0.98, 0.9, 0.5)
    with pytest.raises(ValueError):
        KFParams(p_survival=1.5)


def test_track_snapshot_confidence_fields_validate_and_roundtrip() -> None:
    """Breakpoint ②: additive fields validate and to_dict/from_dict round-trips."""
    snapshot = TrackSnapshot(
        key=TrackKey(7, 1),
        state=np.array([100.0, 0.0, 2.0, 0.0]),
        covariance=np.diag([49.0, 49.0, 0.5, 0.5]),
        length_m=30.0,
        width_m=7.0,
        observed_at_s=1.0,
        generated_at_s=2.0,
        status=TrackStatus.UPDATED,
        source="kf",
        existence_prob=0.97,
        quality=0.86,
        sources=(TrackSource(sensor_id=1, last_seen_age_s=0.5), {"sensor_id": 5, "last_seen_age_s": 1.5}),
    )
    assert snapshot.sources[1] == TrackSource(sensor_id=5, last_seen_age_s=1.5)

    restored = TrackSnapshot.from_dict(snapshot.to_dict())
    assert restored.target_id == 7
    assert restored.existence_prob == pytest.approx(0.97)
    assert restored.quality == pytest.approx(0.86)
    assert restored.sources == snapshot.sources
    np.testing.assert_array_equal(restored.state, snapshot.state)
    np.testing.assert_array_equal(restored.covariance, snapshot.covariance)

    for bad_value in (float("nan"), -0.1, 1.1):
        with pytest.raises(ValueError):
            TrackSnapshot(
                key=TrackKey(7, 1),
                state=np.array([100.0, 0.0, 2.0, 0.0]),
                covariance=np.diag([49.0, 49.0, 0.5, 0.5]),
                length_m=30.0,
                width_m=7.0,
                observed_at_s=1.0,
                generated_at_s=2.0,
                status=TrackStatus.UPDATED,
                source="kf",
                existence_prob=bad_value,
            )
    with pytest.raises(ValueError):
        TrackSnapshot(
            key=TrackKey(7, 1),
            state=np.array([100.0, 0.0, 2.0, 0.0]),
            covariance=np.diag([49.0, 49.0, 0.5, 0.5]),
            length_m=30.0,
            width_m=7.0,
            observed_at_s=1.0,
            generated_at_s=2.0,
            status=TrackStatus.UPDATED,
            source="kf",
            sources=(TrackSource(sensor_id=9),),
        )


def test_track_quality_composite_matches_documented_weights() -> None:
    import math

    # track_quality pins to 6 decimals (stable JSON products).
    assert track_quality(status=TrackStatus.UPDATED, age_s=0.0, source_count=1) == 0.9
    assert track_quality(status=TrackStatus.UPDATED, age_s=0.0, source_count=2) == 1.0
    assert track_quality(status=TrackStatus.COASTING, age_s=5.0, source_count=0) == round(
        0.4 * math.exp(-1.0), 6
    )
