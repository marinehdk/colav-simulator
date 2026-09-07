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


def test_baseline_uses_target_bound_vo_execution_intent() -> None:
    tracks = [TrackSnapshot(key=TrackKey(i, 1), state=np.array([800.0, 0.0, 2.5, 0.0]),
                            covariance=np.zeros((4, 4)), length_m=12.0, width_m=4.0,
                            observed_at_s=0.0, generated_at_s=0.0, status=TrackStatus.UPDATED, source="god")
              for i in range(1, 5)]
    ship = SimpleNamespace(
        state=np.array([0.0, 0.0, 0.0, 7.0, 0.0, 0.0]), length=45.0, width=8.0,
        get_do_track_information=lambda: (tracks, []),
        get_colav_data=lambda: {"vo": {"track_metrics": {
            "1": {"active_rules": ["OT_ing"]}, "2": {"active_rules": []},
            "3": {"active_rules": ["CR_PS"], "stand_on_emergency": False},
            "4": {"active_rules": ["CR_PS"], "stand_on_emergency": True},
        }}},
    )
    cycle = build_baseline_cycle_inputs([ship], sim_time_s=0.0, sequence=0).cycle
    assert cycle.avoidance_intent_keys == (TrackKey(1, 1), TrackKey(4, 1))


def test_passive_role_maneuver_is_recognized_when_vo_departs_from_nominal() -> None:
    track = TrackSnapshot(key=TrackKey(1, 1), state=np.array([-500.0, 10.0, 8.0, 0.0]),
                          covariance=np.zeros((4, 4)), length_m=12.0, width_m=4.0,
                          observed_at_s=0.0, generated_at_s=0.0, status=TrackStatus.UPDATED, source="god")
    debug = {"driving_target_id": 1, "reference_velocity_error_mps": 0.0,
             "track_metrics": {1: {"active_rules": [], "effective_matched_rules": ["OT_en"]}}}
    ship = SimpleNamespace(state=np.array([0.0, 0.0, 0.0, 5.0, 0.0, 0.0]), length=45.0, width=8.0,
                           get_do_track_information=lambda: ([track], []), get_colav_data=lambda: {"vo": debug})
    assert build_baseline_cycle_inputs([ship], sim_time_s=0.0, sequence=0).cycle.avoidance_intent_keys == ()
    debug["reference_velocity_error_mps"] = 1.0
    assert build_baseline_cycle_inputs([ship], sim_time_s=0.0, sequence=1).cycle.avoidance_intent_keys == ()
    debug["planning_horizon_s"] = 60.0
    debug["track_metrics"][1]["reference_preferred_domain_toc_s"] = 40.0
    assert build_baseline_cycle_inputs([ship], sim_time_s=0.0, sequence=2).cycle.avoidance_intent_keys == (track.key,)
    debug["track_metrics"][1]["reference_preferred_domain_toc_s"] = 400.0
    assert build_baseline_cycle_inputs([ship], sim_time_s=0.0, sequence=3).cycle.avoidance_intent_keys == ()
    debug["track_metrics"][1]["reference_preferred_domain_toc_s"] = 40.0
    debug["track_metrics"][1]["effective_matched_rules"] = ["CR_PS"]
    assert build_baseline_cycle_inputs([ship], sim_time_s=0.0, sequence=2).cycle.avoidance_intent_keys == (track.key,)


def test_recovery_guard_uses_nominal_route_reference_not_current_avoidance_motion() -> None:
    ship = SimpleNamespace(state=np.array([0.0, 0.0, 0.0, 5.0, 0.0, 0.0]), length=45.0, width=8.0,
                           get_do_track_information=lambda: ([], []),
                           get_colav_data=lambda: {"vo": {"reference_velocity_ne_mps": [0.0, 4.0]}})
    cycle = build_baseline_cycle_inputs([ship], sim_time_s=0.0, sequence=0).cycle
    assert cycle.route_bearing_rad == np.pi / 2.0
    assert cycle.planned_speed_mps == 4.0
    np.testing.assert_array_equal(cycle.ownship.velocity_ne_mps, [5.0, 0.0])
