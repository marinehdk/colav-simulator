"""A monitored give-way obligation must constrain a conflicting recovery reference."""

import math
from types import SimpleNamespace

import numpy as np
import pytest

from colav_simulator.core.colav.kuwata_vo_alg.kuwata_vo import VO, VOCOLREGSSituation, VOParams


@pytest.mark.parametrize("encounter, rule", [("CROSSING", "CR_SS"), ("HEAD_ON", "HO")])
def test_monitored_duty_activates_on_reference_conflict_before_current_collision_course(encounter, rule):
    # Current course is safe; the return reference heads into a crossing target.
    vo = VO(VOParams(t_max=60, hard_hull_clearance_m=182, preferred_hull_clearance_m=190))
    snapshot = SimpleNamespace(
        sim_time_s=9.9,
        targets=(
            SimpleNamespace(
                key=SimpleNamespace(target_id=3, generation=1),
                risk="ACTIVE",
                role="GIVE_WAY",
                encounter=encounter,
                commitment="COMMITTED",
            ),
        ),
    )
    own = np.array([0.0, 0.0, 0.0, 5.0, 0.0, 0.0])
    target = (3, np.array([0.0, 500.0, 0.0, -4.0]), np.zeros((4, 4)), 12.0, 4.0)
    vo.plan(
        10.0,
        np.array([0.0, 5.0]),
        own,
        [target],
        encounter_snapshot=snapshot,
        os_course_time_constant_s=39.0,
        os_speed_time_constant_s=12.0,
        os_max_turn_rate_radps=math.radians(1.2),
    )
    metrics = vo.get_debug_data()["track_metrics"][3]
    assert metrics["preferred_domain_toc_s"] is None
    assert metrics["reference_preferred_domain_toc_s"] < 99
    assert rule in metrics["active_rules"]
    assert metrics["matched_rules"] == ["CR_SS"]  # measured geometry stays distinct from the monitored duty
    assert metrics["rule_activation_basis"] == "MONITORED_REFERENCE_CONFLICT"


def test_monitoring_alone_does_not_force_a_maneuver_without_reference_conflict():
    vo = VO(VOParams(t_max=60, hard_hull_clearance_m=182, preferred_hull_clearance_m=190))
    snapshot = SimpleNamespace(
        sim_time_s=9.9,
        targets=(
            SimpleNamespace(
                key=SimpleNamespace(target_id=3, generation=1),
                risk="ACTIVE",
                role="GIVE_WAY",
                encounter="CROSSING",
                commitment="COMMITTED",
            ),
        ),
    )
    vo.plan(
        10.0,
        np.array([5.0, 0.0]),
        np.array([0.0, 0.0, 0.0, 5.0, 0.0, 0.0]),
        [(3, np.array([0.0, 500.0, 0.0, 4.0]), np.zeros((4, 4)), 12.0, 4.0)],
        encounter_snapshot=snapshot,
    )
    assert not vo.get_debug_data()["track_metrics"][3]["active_rules"]


def test_released_monitor_does_not_rearm_return_rule():
    vo = VO(VOParams(t_max=60, hard_hull_clearance_m=182, preferred_hull_clearance_m=190))
    snapshot = SimpleNamespace(
        sim_time_s=9.9,
        targets=(
            SimpleNamespace(
                key=SimpleNamespace(target_id=3, generation=1),
                risk="RELEASED",
                role="GIVE_WAY",
                encounter="CROSSING",
                commitment="ACHIEVED",
            ),
        ),
    )
    vo.plan(
        10.0,
        np.array([0.0, 5.0]),
        np.array([0.0, 0.0, 0.0, 5.0, 0.0, 0.0]),
        [(3, np.array([0.0, 500.0, 0.0, -4.0]), np.zeros((4, 4)), 12.0, 4.0)],
        encounter_snapshot=snapshot,
    )
    assert not vo.get_debug_data()["track_metrics"][3]["active_rules"]


def test_committed_monitor_does_not_activate_before_short_horizon_conflict():
    vo = VO(VOParams(t_max=60, hard_hull_clearance_m=182, preferred_hull_clearance_m=190))
    snapshot = SimpleNamespace(
        sim_time_s=9.9,
        targets=(
            SimpleNamespace(
                key=SimpleNamespace(target_id=3, generation=1),
                risk="ACTIVE",
                role="GIVE_WAY",
                encounter="CROSSING",
                commitment="COMMITTED",
                route_recovery_allowed=False,
            ),
        ),
    )
    vo.plan(
        10.0,
        np.array([5.0, 0.0]),
        np.array([0.0, 0.0, 0.0, 5.0, 0.0, 0.0]),
        [(3, np.array([0.0, 2700.0, 0.0, -4.0]), np.zeros((4, 4)), 12.0, 4.0)],
        encounter_snapshot=snapshot,
    )
    metrics = vo.get_debug_data()["track_metrics"][3]
    assert metrics["reference_preferred_domain_toc_s"] is None
    assert metrics["active_rules"] == []
    assert metrics["rule_activation_basis"] == "CURRENT_MOTION"
    assert not vo.give_way_commitment_active


def test_monitor_from_an_old_track_generation_cannot_assign_a_duty():
    class Track(tuple):
        pass

    target = Track((3, np.array([0.0, 500.0, 0.0, -4.0]), np.zeros((4, 4)), 12.0, 4.0))
    target.key = SimpleNamespace(target_id=3, generation=2)
    snapshot = SimpleNamespace(
        sim_time_s=9.9,
        targets=(
            SimpleNamespace(
                key=SimpleNamespace(target_id=3, generation=1),
                risk="ACTIVE",
                role="GIVE_WAY",
                encounter="CROSSING",
                commitment="COMMITTED",
                route_recovery_allowed=False,
            ),
        ),
    )
    vo = VO(VOParams(t_max=60, hard_hull_clearance_m=182, preferred_hull_clearance_m=190))
    vo.plan(10.0, np.array([0.0, 5.0]), np.array([0.0, 0.0, 0.0, 5.0, 0.0, 0.0]), [target], encounter_snapshot=snapshot)
    assert not vo.get_debug_data()["track_metrics"][3]["active_rules"]


def test_native_stop_remains_available_while_a_give_way_duty_blocks_recovery():
    vo = VO(VOParams(t_max=60, hard_hull_clearance_m=182, preferred_hull_clearance_m=190))
    snapshot = SimpleNamespace(
        sim_time_s=9.9,
        targets=(
            SimpleNamespace(
                key=SimpleNamespace(target_id=3, generation=1),
                risk="ACTIVE",
                role="GIVE_WAY",
                encounter="CROSSING",
                commitment="COMMITTED",
                route_recovery_allowed=False,
            ),
        ),
    )
    result = vo.plan(
        10.0,
        np.array([0.0, 0.0]),
        np.array([0.0, 0.0, 0.0, 5.0, 0.0, 0.0]),
        [(3, np.array([0.0, 1000.0, 0.0, 4.0]), np.zeros((4, 4)), 12.0, 4.0)],
        encounter_snapshot=snapshot,
        os_course_time_constant_s=39.0,
        os_speed_time_constant_s=12.0,
        os_max_turn_rate_radps=math.radians(1.2),
        os_avoidance_speed_cap_mps=8.0,
        os_min_steerage_speed_mps=3.0,
        os_execution_speed_policy={
            "cruise_cap_mps": 8.0,
            "ordinary_cap_mps": 8.0,
            "emergency_cap_mps": 3.2,
            "supports_stop": True,
        },
    )
    assert vo.feasible
    assert result[3, 0] == 0.0


def test_vo_local_release_cannot_override_the_monitor_recovery_guard():
    vo = VO(VOParams(t_max=60, hard_hull_clearance_m=182, preferred_hull_clearance_m=190))
    # Establish an actual conflict first; monitoring alone must never start a turn.
    vo.plan(
        9.0, np.array([0.0, 5.0]), np.array([0.0, 0.0, 0.0, 5.0, 0.0, 0.0]),
        [(3, np.array([0.0, 500.0, 0.0, -4.0]), np.zeros((4, 4)), 12.0, 4.0)],
        encounter_snapshot=SimpleNamespace(sim_time_s=8.9, targets=(SimpleNamespace(
            key=SimpleNamespace(target_id=3, generation=1), risk="ACTIVE", role="GIVE_WAY",
            encounter="CROSSING", commitment="COMMITTED", route_recovery_allowed=False,
        ),)),
    )
    assert "CR_SS" in vo.get_debug_data()["track_metrics"][3]["active_rules"]
    for tick in range(8):
        snapshot = SimpleNamespace(
            sim_time_s=9.9 + tick,
            targets=(
                SimpleNamespace(
                    key=SimpleNamespace(target_id=3, generation=1),
                    risk="ACTIVE",
                    role="GIVE_WAY",
                    encounter="CROSSING",
                    commitment="COMMITTED",
                    route_recovery_allowed=False,
                ),
            ),
        )
        vo.plan(
            10.0 + tick,
            np.array([5.0, 0.0]),
            np.array([tick * 5.0, 0.0, 0.0, 5.0, 0.0, 0.0]),
            [(3, np.array([0.0, 1000.0 + tick * 4.0, 0.0, 4.0]), np.zeros((4, 4)), 12.0, 4.0)],
            encounter_snapshot=snapshot,
        )
        assert "CR_SS" in vo.get_debug_data()["track_metrics"][3]["active_rules"]
    for tick in range(8, 16):
        snapshot = SimpleNamespace(
            sim_time_s=9.9 + tick,
            targets=(
                SimpleNamespace(
                    key=SimpleNamespace(target_id=3, generation=1),
                    risk="RELEASED",
                    role="GIVE_WAY",
                    encounter="CROSSING",
                    commitment="ACHIEVED",
                    route_recovery_allowed=True,
                ),
            ),
        )
        vo.plan(
            10.0 + tick,
            np.array([5.0, 0.0]),
            np.array([tick * 5.0, 0.0, 0.0, 5.0, 0.0, 0.0]),
            [(3, np.array([0.0, 1000.0 + tick * 4.0, 0.0, 4.0]), np.zeros((4, 4)), 12.0, 4.0)],
            encounter_snapshot=snapshot,
        )
    assert not vo.get_debug_data()["track_metrics"][3]["active_rules"]


@pytest.mark.parametrize("encounter, rule", [("CROSSING", "CR_SS"), ("HEAD_ON", "HO")])
def test_distant_monitored_conflict_tracks_normally_then_activates_inside_window(encounter, rule):
    params = VOParams(t_max=60, hard_hull_clearance_m=182, preferred_hull_clearance_m=190)
    monitored, unmonitored = VO(params), VO(params)
    own = np.array([0.0, 0.0, 0.0, 5.0, 0.0, 0.0])
    reference = np.array([0.0, 5.0])
    for tick, distance in enumerate([2700.0, 2690.0, 2680.0, 500.0]):
        snapshot = SimpleNamespace(sim_time_s=9.9 + tick, targets=(SimpleNamespace(
            key=SimpleNamespace(target_id=3, generation=1), risk="ACTIVE", role="GIVE_WAY",
            encounter=encounter, commitment="COMMITTED", route_recovery_allowed=False,
        ),))
        targets = [(3, np.array([0.0, distance, 0.0, -4.0]), np.zeros((4, 4)), 12.0, 4.0)]
        execution = {"os_course_time_constant_s": 39., "os_speed_time_constant_s": 12.,
                     "os_max_turn_rate_radps": math.radians(1.2),
                     "os_avoidance_speed_cap_mps": 8., "os_min_steerage_speed_mps": 3.}
        actual = monitored.plan(10.0 + tick, reference, own, targets, encounter_snapshot=snapshot, **execution)
        baseline = unmonitored.plan(10.0 + tick, reference, own, targets, **execution)
        metrics = monitored.get_debug_data()["track_metrics"][3]
        if distance > 500.0:
            assert metrics["reference_preferred_domain_toc_s"] > 60.0
            assert not metrics["active_rules"]
            assert not monitored.give_way_commitment_active
            np.testing.assert_allclose(actual, baseline)
        else:
            assert metrics["reference_preferred_domain_toc_s"] < 60.0
            assert rule in metrics["active_rules"]
            assert metrics["rule_activation_basis"] == "MONITORED_REFERENCE_CONFLICT"



def test_crossing_can_reduce_a_starboard_alteration_without_crossing_entry_course():
    vo = VO(VOParams())
    vo._speed_set = np.array([5.0])
    vo._heading_set = np.deg2rad([20.0, 45.0, 60.0])
    vo._ensure_grid_shape()
    vo._active_rules = {2: {VOCOLREGSSituation.CR_SS}}
    vo._give_way_commitment_active = True
    vo._crossing_commitment_frame_heading = 0.0
    vo._selected_heading = math.radians(45.0)
    candidates = 5.0 * np.stack((np.cos(vo._heading_set), np.sin(vo._heading_set)), axis=-1)[None, ...]
    vo._apply_give_way_commitment(candidates, math.radians(45.0))
    # 20 degrees is still starboard of the encounter-entry course. Other
    # collision/COLREG masks decide whether it is safe; progress alone cannot ban it.
    assert not vo._hard_constraint_mask[0, 0]


def test_monitor_admits_near_bow_crossing_even_without_clearance_intrusion():
    vo = VO(VOParams(t_max=60, hard_hull_clearance_m=182, preferred_hull_clearance_m=190))
    snapshot = SimpleNamespace(sim_time_s=9.9, targets=(SimpleNamespace(
        key=SimpleNamespace(target_id=3, generation=1), risk="ACTIVE", role="GIVE_WAY",
        encounter="CROSSING", commitment="COMMITTED", route_recovery_allowed=False,
    ),))
    vo.plan(10.0, np.array([5.0, 0.0]), np.array([0., 0., 0., 5., 0., 0.]),
            [(3, np.array([0., 500., 0., -4.]), np.zeros((4, 4)), 12., 4.)],
            encounter_snapshot=snapshot)
    metrics = vo.get_debug_data()["track_metrics"][3]
    assert metrics["reference_preferred_domain_toc_s"] is None
    assert 0 < metrics["reference_rule_conflict_tcpa_s"] < 60
    assert metrics["active_rules"] == ["CR_SS"]


@pytest.mark.parametrize("turn_rate_deg_s, admitted", [(1.2, True), (90.0, False)])
def test_reference_admission_accounts_for_available_turn_rate(turn_rate_deg_s, admitted):
    vo = VO(VOParams(t_max=60, hard_hull_clearance_m=182, preferred_hull_clearance_m=190))
    snapshot = SimpleNamespace(sim_time_s=9.9, targets=(SimpleNamespace(
        key=SimpleNamespace(target_id=3, generation=1), risk="ACTIVE", role="GIVE_WAY",
        encounter="CROSSING", commitment="COMMITTED", route_recovery_allowed=False,
    ),))
    vo.plan(10.0, np.array([5., 0.]), np.array([0., 0., -math.pi/2, 5., 0., 0.]),
            [(3, np.array([0., 1300., 0., -4.]), np.zeros((4, 4)), 12., 4.)],
            encounter_snapshot=snapshot, os_course_time_constant_s=39.,
            os_speed_time_constant_s=12., os_max_turn_rate_radps=math.radians(turn_rate_deg_s),
            os_avoidance_speed_cap_mps=8., os_min_steerage_speed_mps=3.)
    metrics = vo.get_debug_data()["track_metrics"][3]
    assert metrics["reference_preferred_domain_toc_s"] is None
    assert (metrics["reference_rule_conflict_tcpa_s"] <= metrics["reference_admission_horizon_s"]) == admitted
    assert bool(metrics["active_rules"]) == admitted


@pytest.mark.parametrize("turn_rate_deg_s, admitted", [(1.2, True), (90.0, False)])
def test_aligned_conflicting_reference_still_needs_avoidance_turn_lead(turn_rate_deg_s, admitted):
    vo = VO(VOParams(t_max=60, hard_hull_clearance_m=182, preferred_hull_clearance_m=190))
    snapshot = SimpleNamespace(sim_time_s=9.9, targets=(SimpleNamespace(
        key=SimpleNamespace(target_id=3, generation=1), risk="ACTIVE", role="GIVE_WAY",
        encounter="CROSSING", commitment="COMMITTED", route_recovery_allowed=False,
    ),))
    vo.plan(10.0, np.array([5., 0.]), np.array([0., 0., 0., 5., 0., 0.]),
            [(3, np.array([450., 1300., -.77, -1.544]), np.zeros((4, 4)), 12., 4.)],
            encounter_snapshot=snapshot, os_course_time_constant_s=39.,
            os_speed_time_constant_s=12., os_max_turn_rate_radps=math.radians(turn_rate_deg_s),
            os_avoidance_speed_cap_mps=8., os_min_steerage_speed_mps=3.)
    metrics = vo.get_debug_data()["track_metrics"][3]
    assert metrics["reference_preferred_domain_toc_s"] is None
    assert metrics["reference_rule_conflict_tcpa_s"] > 99.
    assert (metrics["reference_rule_conflict_tcpa_s"] <= metrics["reference_admission_horizon_s"]) == admitted
    assert bool(metrics["active_rules"]) == admitted
