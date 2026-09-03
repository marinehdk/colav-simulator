"""Issue #67 slice 1: ownship encounter clearance and return-voyage XTE metrics.

Expected values are hand-computed from independent geometry (no reuse of the
implementation's math): perpendicular offsets against axis-aligned routes and
straight-line relative motion.
"""

from __future__ import annotations

import numpy as np
import pytest

from colav_simulator.common.vessel_data import VesselData
from colav_simulator.evaluation import Evaluator
from colav_simulator.evaluation.voyage import (
    route_line_crossings,
    signed_cross_track_errors_m,
)


def vessel(
    identifier: int,
    east: np.ndarray,
    north: np.ndarray,
    speed: float,
    course: float,
    *,
    timestamps: np.ndarray | None = None,
) -> VesselData:
    samples = east.size
    times = timestamps if timestamps is not None else np.arange(samples, dtype=float)
    return VesselData(
        id=identifier,
        mmsi=100 + identifier,
        length=20.0,
        width=5.0,
        draft=2.0,
        xy=np.vstack((east, north)),
        sog=np.full(samples, speed),
        cog=np.full(samples, course),
        timestamps=times,
        first_valid_idx=0,
        last_valid_idx=samples - 1,
        travel_dist=float(np.linalg.norm([east[-1] - east[0], north[-1] - north[0]])),
    )


# ---------------------------------------------------------------------------
# Module-level geometry: signed cross-track error against the mission route.
# ---------------------------------------------------------------------------


def test_signed_xte_matches_hand_computed_offsets_on_north_route() -> None:
    # Route travels north along east = 0 from N=0 to N=1000. Positive XTE is
    # starboard (east) of the route travel direction.
    route_ne = np.array([[0.0, 0.0], [1000.0, 0.0]])
    positions_ne = np.array(
        [
            [500.0, 30.0],    # starboard of the route: +30
            [500.0, -30.0],   # port: -30
            [0.0, 0.0],       # on the route: 0
            [-50.0, 0.0],     # before the first waypoint: 0
            [1100.0, 50.0],   # past the last waypoint: sqrt(100^2+50^2)
        ]
    )

    xte = signed_cross_track_errors_m(positions_ne, route_ne)

    assert xte[0] == pytest.approx(30.0, abs=1e-9)
    assert xte[1] == pytest.approx(-30.0, abs=1e-9)
    assert xte[2] == pytest.approx(0.0, abs=1e-9)
    assert xte[3] == pytest.approx(0.0, abs=1e-9)
    assert xte[4] == pytest.approx(np.hypot(100.0, 50.0), abs=1e-9)


def test_signed_xte_uses_nearest_segment_on_bent_route() -> None:
    # L-shaped route: north to (0, 0)->(1000, 0) then east to (1000, 500).
    route_ne = np.array([[0.0, 0.0], [1000.0, 0.0], [1000.0, 500.0]])
    positions_ne = np.array(
        [
            [900.0, 25.0],    # on the first leg: +25 (starboard while going north)
            [950.0, 75.0],    # nearest segment is the second (east-going) leg: starboard +50
        ]
    )

    xte = signed_cross_track_errors_m(positions_ne, route_ne)

    assert xte[0] == pytest.approx(25.0, abs=1e-9)
    # Travelling east (090), starboard is south: N=950 south of the leg is +50.
    assert xte[1] == pytest.approx(50.0, abs=1e-9)


def test_route_line_crossings_counts_full_sign_flips_with_hysteresis() -> None:
    # + -> - -> + with amplitudes far beyond the 5 m band: two crossings.
    assert route_line_crossings(np.array([30.0, 30.0, -30.0, -30.0, 30.0]), 5.0) == 2
    # Stays on the starboard side: no crossing.
    assert route_line_crossings(np.array([30.0, 10.0, 30.0]), 5.0) == 0
    # Touches the band but only commits once to each side: one crossing.
    assert route_line_crossings(np.array([30.0, 0.0, -30.0]), 5.0) == 1
    # Dither inside the hysteresis band: never a crossing.
    assert route_line_crossings(np.array([4.0, -4.0, 4.0, -4.0]), 5.0) == 0


# ---------------------------------------------------------------------------
# Evaluator report section.
# ---------------------------------------------------------------------------


def test_voyage_section_reports_continuous_encounter_minimum() -> None:
    # Target sweeps south along east = 100 but only samples at north +60/-60:
    # the sampled minimum is sqrt(100^2 + 60^2) = 116.62 m while the true
    # continuous minimum (relative motion is a straight segment) is 100.0 m.
    ownship = vessel(0, np.array([0.0, 0.0]), np.array([0.0, 0.0]), 0.0, 0.0)
    target = vessel(1, np.array([100.0, 100.0]), np.array([60.0, -60.0]), 120.0, -np.pi / 2.0)

    result = Evaluator().evaluate([ownship, target])

    assert result.voyage["encounter"]["min_target_center_distance_m"] == pytest.approx(100.0, abs=1e-9)
    assert result.voyage["encounter"]["controlling_target_id"] == 1
    assert result.pair_results[0].minimum_distance_m > 100.0  # sampled minimum differs


def test_voyage_section_takes_minimum_over_all_targets() -> None:
    times = np.arange(3.0)
    ownship = vessel(0, np.zeros(3), np.zeros(3), 0.0, 0.0, timestamps=times)
    near = vessel(1, np.array([80.0, 80.0, 80.0]), times * 10.0, 10.0, np.pi / 2.0, timestamps=times)
    far = vessel(2, np.array([500.0, 500.0, 500.0]), times * 10.0, 10.0, np.pi / 2.0, timestamps=times)

    result = Evaluator().evaluate([ownship, near, far])

    assert result.voyage["encounter"]["min_target_center_distance_m"] == pytest.approx(80.0, abs=1e-9)
    assert result.voyage["encounter"]["controlling_target_id"] == 1


def test_voyage_section_without_ownship_pairs_reports_no_encounter_minimum() -> None:
    ownship = vessel(0, np.array([0.0]), np.array([0.0]), 0.0, 0.0, timestamps=np.array([0.0]))
    target = vessel(1, np.array([5.0]), np.array([5.0]), 1.0, 0.0, timestamps=np.array([10.0]))

    result = Evaluator().evaluate([ownship, target])

    assert result.voyage["encounter"]["min_target_center_distance_m"] is None
    assert result.voyage["encounter"]["controlling_target_id"] is None
    assert result.voyage["return_voyage"] is None


def test_voyage_section_return_xte_uses_cpa_anchored_window() -> None:
    # Ownship follows north along east = 0 (route N 0..800). It carries a
    # 500 m deviation before the encounter, passes a fixed target abeam at
    # sample t=3 (sampled CPA), then converges back onto the route.
    # Sampled centre-distance minimum against the fixed target at
    # (N=200, E=310) is at t=3 by direct evaluation of the five-point table.
    times = np.arange(9.0) * 10.0
    east = np.array([500.0, 500.0, 10.0, 200.0, 60.0, 30.0, 10.0, 5.0, 0.0])
    north = np.arange(9.0) * 100.0
    ownship = vessel(0, east, north, 10.0, 0.0, timestamps=times)
    target = vessel(
        1,
        np.full(9, 310.0),
        np.full(9, 200.0),
        0.0,
        0.0,
        timestamps=times,
    )
    route_ne = np.array([[0.0, 0.0], [800.0, 0.0]])

    result = Evaluator().evaluate(
        [ownship, target],
        execution_context={
            "ownship_route_waypoints_ne": route_ne.tolist(),
            "return_window_buffer_s": 20.0,
        },
    )

    return_voyage = result.voyage["return_voyage"]
    assert return_voyage is not None
    # Sampled CPA is at t=3 (time 30 s); window starts at 30 + 20 = 50 s.
    assert return_voyage["cpa_time_s"] == pytest.approx(30.0)
    assert return_voyage["window_start_s"] == pytest.approx(50.0)
    assert return_voyage["buffer_s"] == pytest.approx(20.0)
    # Window covers samples t >= 5: east offsets [30, 10, 5, 0] -> max 30, all
    # on the starboard side -> no line crossings.
    assert return_voyage["max_abs_xte_m"] == pytest.approx(30.0, abs=1e-9)
    assert return_voyage["route_crossings"] == 0
    assert return_voyage["sample_count"] == 4


def test_voyage_section_return_xte_counts_post_window_line_crossings() -> None:
    # After the CPA-anchored window start the ownship weaves +60/-60/+60
    # around the route: max |XTE| 60 and two full line crossings.
    times = np.arange(7.0) * 10.0
    east = np.array([200.0, 200.0, 60.0, -60.0, 60.0, 10.0, 0.0])
    north = np.arange(7.0) * 100.0
    ownship = vessel(0, east, north, 10.0, 0.0, timestamps=times)
    target = vessel(
        1,
        np.full(7, 310.0),
        np.full(7, 200.0),
        0.0,
        0.0,
        timestamps=times,
    )
    route_ne = np.array([[0.0, 0.0], [600.0, 0.0]])

    result = Evaluator().evaluate(
        [ownship, target],
        execution_context={
            "ownship_route_waypoints_ne": route_ne.tolist(),
            "return_window_buffer_s": 10.0,
        },
    )

    return_voyage = result.voyage["return_voyage"]
    assert return_voyage is not None
    assert return_voyage["max_abs_xte_m"] == pytest.approx(60.0, abs=1e-9)
    assert return_voyage["route_crossings"] == 2


def test_voyage_section_absent_return_block_without_route_context() -> None:
    times = np.arange(3.0)
    ownship = vessel(0, np.zeros(3), times * 10.0, 10.0, 0.0, timestamps=times)
    target = vessel(1, np.array([80.0, 80.0, 80.0]), times * 10.0, 10.0, np.pi / 2.0, timestamps=times)

    result = Evaluator().evaluate([ownship, target])

    assert result.voyage["encounter"]["min_target_center_distance_m"] == pytest.approx(80.0, abs=1e-9)
    assert result.voyage["return_voyage"] is None


def test_voyage_section_serializes_through_result_dict() -> None:
    times = np.arange(3.0)
    ownship = vessel(0, np.zeros(3), times * 10.0, 10.0, 0.0, timestamps=times)
    target = vessel(1, np.array([80.0, 80.0, 80.0]), times * 10.0, 10.0, np.pi / 2.0, timestamps=times)
    route_ne = np.array([[0.0, 0.0], [600.0, 0.0]])

    result = Evaluator().evaluate(
        [ownship, target],
        execution_context={"ownship_route_waypoints_ne": route_ne.tolist()},
    )

    document = result.to_dict()
    assert document["voyage"]["encounter"]["min_target_center_distance_m"] == pytest.approx(80.0, abs=1e-9)
    assert document["voyage"]["return_voyage"] is not None
