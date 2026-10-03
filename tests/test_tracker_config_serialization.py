"""Tracker Config serialization symmetry (P3-S6 D3 fix, spec #90).

The GodTracker retirement audit (docs/research/2026-10-02-phase3-sensor-fusion/
godtracker-retirement-audit.md D3) flagged a to_dict/from_dict asymmetry: the
dump wrote the ``god_tracker`` key for both True and False while the loader
treats key-presence as True, so any False/absent default resurrected
GodTracker on every scenario dump -> load round-trip. These tests pin the
three round-trip states the flip relies on.
"""

from colav_simulator.core.tracking.trackers import Config, GodTracker, KF, KFParams, TrackerBuilder


def test_round_trip_explicit_god_stays_god() -> None:
    """Explicit god_tracker=True dumps the marker key and reloads as God."""
    config = Config(god_tracker=True)
    dumped = config.to_dict()
    assert dumped == {"god_tracker": ""}
    loaded = Config.from_dict(dumped)
    assert loaded.god_tracker is True
    assert loaded.kf is None
    assert isinstance(TrackerBuilder.construct_tracker([], loaded), GodTracker)


def test_round_trip_explicit_false_does_not_resurrect_god() -> None:
    """Explicit god_tracker=False must not come back as God after a round-trip."""
    config = Config(god_tracker=False)
    dumped = config.to_dict()
    assert "god_tracker" not in dumped
    loaded = Config.from_dict(dumped)
    assert loaded.god_tracker is False


def test_round_trip_default_absent_key_keeps_default() -> None:
    """A default Config dumps no tracker key and reloads to the same default."""
    config = Config()
    dumped = config.to_dict()
    assert "god_tracker" not in dumped
    assert "kf" not in dumped
    loaded = Config.from_dict(dumped)
    assert loaded.god_tracker == Config().god_tracker
    assert loaded.kf is None


def test_round_trip_kf_config_stays_kf() -> None:
    """An explicit kf section round-trips as kf with god_tracker disarmed."""
    config = Config(god_tracker=None, kf=KFParams())
    dumped = config.to_dict()
    assert "kf" in dumped
    assert "god_tracker" not in dumped
    loaded = Config.from_dict(dumped)
    assert loaded.god_tracker is None
    assert loaded.kf is not None
