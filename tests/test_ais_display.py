"""P3-S4 AIS display-layer tests (spec #90).

Covers the backend-authoritative AIS target display state
(``colav_simulator/core/ais_display.py``, IMO SN.1/Circ.243/Rev.1 semantics):
the ITU-R M.1371 reporting-interval table (parity with the tracker AIS sensor
documentation in ``sensing.py``), the speed/age state judgment thresholds
(active / sleeping / lost), the per-target report clock cadence, and the
additive ``truth[].ais = {age_s, state}`` transport field wiring in
``gui_server/main.py`` (obstacles only; compact-v1 strip list untouched).
"""

import numpy as np
import pytest
from types import SimpleNamespace

from colav_simulator.core.ais_display import (
    AIS_ACTIVE_SOG_MPS,
    AIS_LOST_AGE_FACTOR,
    AisReportClock,
    ais_lost_age_s,
    ais_reporting_interval_s,
    ais_target_state,
)
from colav_simulator.experiment.contracts import SessionState
from gui_server import main as gui_main

MPS_PER_KNOT = 1852.0 / 3600.0


class TestReportingIntervals:
    def test_class_a_table_matches_the_sensing_ais_rate_documentation(self) -> None:
        # sensing.py AIS._measurement_rate table (ITU-R M.1371): anchored 180 s,
        # 0-14 kn 10 s, 14-23 kn 6 s, >23 kn 2 s.
        assert ais_reporting_interval_s(0.0) == 180.0
        assert ais_reporting_interval_s(0.001 * MPS_PER_KNOT) == 180.0
        assert ais_reporting_interval_s(5.0 * MPS_PER_KNOT) == 10.0
        assert ais_reporting_interval_s(14.0 * MPS_PER_KNOT) == 10.0
        assert ais_reporting_interval_s(14.5 * MPS_PER_KNOT) == 6.0
        assert ais_reporting_interval_s(23.0 * MPS_PER_KNOT) == 6.0
        assert ais_reporting_interval_s(24.0 * MPS_PER_KNOT) == 2.0

    def test_class_b_table_uses_the_two_knot_boundary(self) -> None:
        assert ais_reporting_interval_s(1.0 * MPS_PER_KNOT, ais_class="B") == 180.0
        assert ais_reporting_interval_s(2.0 * MPS_PER_KNOT, ais_class="B") == 180.0
        assert ais_reporting_interval_s(3.0 * MPS_PER_KNOT, ais_class="B") == 30.0

    def test_unknown_class_falls_back_to_class_a(self) -> None:
        assert ais_reporting_interval_s(5.0 * MPS_PER_KNOT, ais_class="X") == 10.0


class TestTargetState:
    def test_underway_targets_are_active(self) -> None:
        assert ais_target_state(6.0, 0.0) == "active"
        assert ais_target_state(AIS_ACTIVE_SOG_MPS, 4.0) == "active"

    def test_stationary_targets_are_sleeping(self) -> None:
        assert ais_target_state(0.0, 0.0) == "sleeping"
        assert ais_target_state(AIS_ACTIVE_SOG_MPS - 1e-6, 9.0) == "sleeping"

    def test_lost_after_three_expected_reporting_intervals(self) -> None:
        # 5 m/s target: interval 10 s -> lost beyond 30 s.
        assert ais_target_state(5.0, 30.0) == "active"
        assert ais_lost_age_s(5.0) == pytest.approx(AIS_LOST_AGE_FACTOR * 10.0)
        assert ais_target_state(5.0, 30.0 + 1e-9) == "lost"
        # Moored target: interval 180 s -> much later lost threshold, and the
        # speed gate keeps it sleeping until then.
        assert ais_target_state(0.0, 540.0) == "sleeping"
        assert ais_target_state(0.0, 540.0 + 1e-9) == "lost"
        # Class B slow mover (0.3 m/s ≈ 0.6 kn < 2 kn and below the active
        # speed gate): 180 s interval -> 540 s lost threshold.
        assert ais_target_state(0.3, 540.0, ais_class="B") == "sleeping"
        assert ais_target_state(0.3, 540.0 + 1e-9, ais_class="B") == "lost"
        # Class B above 2 kn: 30 s interval -> 90 s lost threshold.
        assert ais_target_state(1.5, 90.0, ais_class="B") == "active"
        assert ais_target_state(1.5, 90.0 + 1e-9, ais_class="B") == "lost"

    def test_negative_and_non_finite_inputs_count_as_fresh_or_lost(self) -> None:
        assert ais_target_state(6.0, -0.5) == "active"
        assert ais_target_state(float("nan"), 0.0) == "lost"
        assert ais_target_state(6.0, float("nan")) == "lost"


class TestReportClock:
    def test_age_sawtooths_across_the_reporting_interval(self) -> None:
        clock = AisReportClock()
        ages = [clock.advance(k * 2.5, 5.0) for k in range(1, 9)]  # 10 s interval
        assert ages == pytest.approx([0.0, 2.5, 5.0, 7.5, 0.0, 2.5, 5.0, 7.5])

    def test_first_call_is_a_fresh_report(self) -> None:
        clock = AisReportClock()
        assert clock.advance(712.0, 0.0) == 0.0

    def test_time_regression_treats_the_frame_as_a_new_report(self) -> None:
        clock = AisReportClock()
        clock.advance(100.0, 5.0)
        assert clock.advance(99.5, 5.0) == 0.0
        assert clock.advance(100.0, 5.0) == 0.5

    def test_cadence_follows_speed_changes(self) -> None:
        clock = AisReportClock()
        clock.advance(0.0, 5.0)
        # Accelerate past 23 kn -> 2 s interval -> new report due sooner.
        assert clock.advance(1.5, 24.0 * MPS_PER_KNOT) == 1.5
        assert clock.advance(2.0, 24.0 * MPS_PER_KNOT) == 0.0

    def test_reset_restores_initial_state(self) -> None:
        clock = AisReportClock()
        clock.advance(50.0, 5.0)
        clock.reset()
        assert clock.advance(50.5, 5.0) == 0.0

    def test_age_peeks_without_emitting_a_report(self) -> None:
        clock = AisReportClock()
        assert clock.age(100.0) == 0.0  # no report yet
        clock.advance(100.0, 5.0)
        assert clock.age(112.0) == 12.0
        # The peek did not emit: the next advance is still due against 100 s
        # (at t=109 the elapsed 9 s is below the interval -> age keeps growing).
        assert clock.advance(109.0, 5.0) == 9.0


def _transport_manager(monkeypatch=None) -> tuple[gui_main.WebSessionManager, dict]:
    """Minimal manager fixture: ownship + one obstacle, no planner evidence."""
    if monkeypatch is not None:
        monkeypatch.setattr(gui_main, "_enc_depth_bin_at", lambda *args, **kwargs: None)
    own_raw = {
        "id": 0, "mmsi": 1, "state": np.array([6955700.0, 42950.0, 0.0, 6.0, 0.0, 0.0]),
        "csog_state": np.array([6955700.0, 42950.0, 6.0, 0.0]), "references": np.zeros(9),
        "colav": {"planner": {}, "threat_management": {"status": "UNAVAILABLE"}},
    }
    target_raw = {
        "id": 1, "mmsi": 257041500,
        "state": np.array([6956100.0, 43200.0, 1.2, 4.0, 0.0, 0.0]),
        "csog_state": np.array([6956100.0, 43200.0, 4.0, 1.2]), "references": np.zeros(9),
        "turn_rate": 0.0, "active": True,
        "colav": {"planner": {}, "threat_management": {"status": "UNAVAILABLE"}},
    }
    session = SimpleNamespace(
        last_frame={"Ship0": own_raw, "Ship1": target_raw},
        ship_list=[
            SimpleNamespace(id=0, length=44.0, width=8.0, waypoints=np.zeros((2, 0)), csog_state=np.zeros(4)),
            SimpleNamespace(id=1, length=20.0, width=6.0, waypoints=np.zeros((2, 0)), csog_state=np.zeros(4)),
        ],
        enc=SimpleNamespace(origin=(42950.0, 6955700.0), utm_zone=32),
        state=SessionState.RUNNING,
        simulator=SimpleNamespace(t=70.0, t_end=1800.0),
        sequence=700, operational_events=[],
        baseline_threat_failure_reason=None, failure_reason=None,
    )
    manager = gui_main.WebSessionManager()
    manager.prepared = SimpleNamespace(
        session=session,
        spec=SimpleNamespace(scenario_id="paper_ccta2023_multiship", historical_replay=None,
                             validation_rule_id="multiship"),
        manifest=SimpleNamespace(run_id="test", executed_algorithm="mid_mpc_ipopt",
                                 requested_algorithm="mid_mpc_ipopt", requested_tracker="god",
                                 executed_tracker="god"),
    )
    return manager, target_raw


class TestTransportAisField:
    def test_record_advances_clocks_only_for_frame_ships(self, monkeypatch) -> None:
        manager, _ = _transport_manager(monkeypatch)
        manager._record_ais_reports(manager.prepared.session.last_frame)
        assert manager._ais_report_ages == {0: 0.0, 1: 0.0}
        # Repeating the same frame time is idempotent (no report due yet).
        manager._record_ais_reports(manager.prepared.session.last_frame)
        assert manager._ais_report_ages[1] == 0.0

    def test_obstacle_carries_ais_field_and_ownship_does_not(self, monkeypatch) -> None:
        manager, target_raw = _transport_manager(monkeypatch)
        manager._record_ais_reports(manager.prepared.session.last_frame)
        manager._publish_telemetry(None)
        obstacle = manager.latest["obstacles"][0]
        assert set(obstacle["ais"]) == {"age_s", "state"}
        assert obstacle["ais"]["age_s"] == pytest.approx(0.0)
        # 4 m/s (~7.8 kn) underway -> active.
        assert obstacle["ais"]["state"] == "active"
        assert "ais" not in manager.latest["os"]

    def test_state_follows_the_authoritative_judgment_at_publish_time(self, monkeypatch) -> None:
        manager, target_raw = _transport_manager(monkeypatch)
        # Park the target: sleeping while the report is fresh.
        target_raw["csog_state"] = np.array([6956100.0, 43200.0, 0.0, 1.2])
        manager._record_ais_reports(manager.prepared.session.last_frame)
        manager._publish_telemetry(None)
        assert manager.latest["obstacles"][0]["ais"]["state"] == "sleeping"
        # Simulate a stale clock (backdoor, mirrors step/tick state): 5 m/s
        # threshold is 30 s -> lost beyond it.
        target_raw["csog_state"] = np.array([6956100.0, 43200.0, 5.0, 1.2])
        manager._ais_report_ages[1] = 31.0
        manager._publish_telemetry(None)
        assert manager.latest["obstacles"][0]["ais"] == {"age_s": pytest.approx(31.0), "state": "lost"}

    def test_missing_clock_history_reads_as_a_fresh_report(self, monkeypatch) -> None:
        manager, _ = _transport_manager(monkeypatch)
        manager._publish_telemetry(None)
        assert manager.latest["obstacles"][0]["ais"] == {"age_s": pytest.approx(0.0), "state": "active"}

    def test_additive_field_survives_the_compact_strip_list_untouched(self, monkeypatch) -> None:
        manager, _ = _transport_manager(monkeypatch)
        manager._record_ais_reports(manager.prepared.session.last_frame)
        manager._publish_telemetry(None)
        payload = gui_main._compact_stream_payload(manager.latest, include_static=True)
        assert "ais" in payload["truth"][1]
        assert not ({"measurements", "tracks", "colav"} & set(payload["truth"][1].keys()))

    def test_record_without_prepared_session_is_a_noop(self) -> None:
        manager, _ = _transport_manager()
        manager.prepared = None
        manager._record_ais_reports({"Ship0": {}})
        assert manager._ais_report_ages == {}

    def test_historical_data_gap_grows_the_age_instead_of_reporting(self, monkeypatch) -> None:
        manager, target_raw = _transport_manager(monkeypatch)
        manager._record_ais_reports(manager.prepared.session.last_frame)
        assert manager._ais_report_ages[1] == 0.0
        # Data gap (historical replay INACTIVE actor): the transponder stays
        # silent, the clock holds and the age crosses the lost threshold
        # (5 m/s -> 30 s) without ever emitting a fresh report.
        for offset in (10.0, 20.0, 30.5):
            manager.prepared.session.simulator.t += offset
            target_raw["historical_actor_truth"] = {"sample_kind": "inactive"}
            manager._record_ais_reports(manager.prepared.session.last_frame)
        # Gap total 60.5 s since the last report at t=70 — well past the 30 s
        # lost threshold for a 5 m/s target.
        assert manager._ais_report_ages[1] == pytest.approx(60.5)
        manager._publish_telemetry(None)
        assert manager.latest["obstacles"][0]["ais"]["state"] == "lost"
