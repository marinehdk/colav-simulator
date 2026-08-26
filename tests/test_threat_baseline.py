from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from colav_simulator.core.colav.encounter_lifecycle import ObservationHealth
from colav_simulator.core.tracking.trackers import TrackKey, TrackSnapshot, TrackStatus
from colav_simulator.experiment.threat_baseline import build_baseline_cycle_inputs


def test_baseline_cycle_freezes_tracker_snapshots_not_world_ship_list() -> None:
    track = TrackSnapshot(
        key=TrackKey(target_id=7, generation=3),
        state=np.array([100.0, 200.0, -1.0, -2.0]),
        covariance=np.diag([4.0, 4.0, 0.2, 0.2]),
        length_m=85.0,
        width_m=16.0,
        observed_at_s=9.0,
        generated_at_s=10.0,
        status=TrackStatus.COASTING,
        source="god",
    )
    ownship = SimpleNamespace(
        state=np.array([0.0, 0.0, 0.0, 5.0, 0.0, 0.0]),
        length=45.0,
        width=8.0,
        get_do_track_information=lambda: ([track], [0.0]),
    )

    inputs = build_baseline_cycle_inputs([ownship], sim_time_s=10.0, sequence=1)

    (target,) = inputs.cycle.targets
    assert target.key == TrackKey(target_id=7, generation=3)
    np.testing.assert_array_equal(target.state_enu, track.state)
    np.testing.assert_array_equal(target.covariance, track.covariance)
    assert target.observed_at_s == 9.0
    assert target.generated_at_s == 10.0
    assert target.health is ObservationHealth.COASTING
    assert target.source == "god"
