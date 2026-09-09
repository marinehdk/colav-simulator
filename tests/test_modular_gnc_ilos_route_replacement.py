"""A new route must never inherit the previous polyline's segment cursor."""

import math

import numpy as np
import pytest

from colav_simulator.modular_gnc.contracts import ControlTask, NavigationState, TrackedRoute
from colav_simulator.modular_gnc.guidance_ilos import ILOSConfig, IntegralLineOfSightGuidance


@pytest.mark.parametrize("replace_identity", [True, False])
def test_replacement_projects_from_new_route_start_on_first_tick(replace_identity):
    guidance = IntegralLineOfSightGuidance()

    def route(route_id, revision) -> TrackedRoute:
        return TrackedRoute(
            route_id=route_id,
            revision=revision,
            accepted=True,
            task=ControlTask.TRANSIT,
            valid_from_tick=0,
            valid_until_tick=100,
            waypoints_ne_m=np.array([[0.0, 100.0, 100.0, 200.0], [0.0, 0.0, 100.0, 100.0]]),
            speed_mps=np.array([2.0, 3.0, 4.0, 4.0]),
        )

    guidance.compute_reference(0, route("old", 0), NavigationState(150.0, 100.0, 0.0, 2.0, 0.0, 0.0), 0.1)
    assert guidance.latest_trace.segment_index == 2
    replacement = route("new" if replace_identity else "old", 0 if replace_identity else 1)
    navigation = NavigationState(20.0, 0.0, 0.0, 2.0, 0.0, 0.0)
    reference = guidance.compute_reference(1, replacement, navigation, 0.1)
    fresh = IntegralLineOfSightGuidance().compute_reference(1, replacement, navigation, 0.1)
    assert guidance.latest_trace.segment_index == 0
    np.testing.assert_array_equal(reference.values, fresh.values)


def test_heading_ilos_matches_published_discrete_update_without_crab_offset():
    """Independent recurrence from MSS ILOSpsi/Borhaug 2008, Delta=50, kappa=.5."""
    guidance = IntegralLineOfSightGuidance(ILOSConfig(integral_law="borhaug2008", integral_gain=0.01))
    route = TrackedRoute(
        "source", 0, True, 0, 1000, np.array([[0.0, 10000.0], [0.0, 0.0]]), np.array([7.8, 7.8]), ControlTask.TRANSIT
    )
    integral = 0.0
    for tick, error in enumerate([20.0, 18.0, 16.0, -5.0, 0.0, 150.0, 5.0]):
        expected = -math.atan((error + 0.5 * integral) / 50.0)
        out = guidance.compute_reference(tick, route, NavigationState(10.0, error, 0.0, 7.8, 0.0, 0.0), 0.1)
        assert out.values[2] == pytest.approx(expected, abs=1e-14)
        assert guidance.latest_trace.heading_reference_rad == out.values[2]
        integral += 0.1 * 50.0 * error / (50.0**2 + (error + 0.5 * integral) ** 2)
        assert guidance.snapshot().integral_cross_track_error_m == pytest.approx(integral, abs=1e-14)


def test_folded_future_plan_does_not_skip_unvisited_segments():
    guidance = IntegralLineOfSightGuidance()
    route = TrackedRoute(
        "folded",
        0,
        True,
        0,
        1000,
        np.array([[0.0, 100.0, 100.0, 0.0, 0.0, 100.0], [0.0, 0.0, 100.0, 100.0, 1.0, 21.0]]),
        np.array([2.0, 3.0, 4.0, 5.0, 6.0, 6.0]),
        ControlTask.TRANSIT,
    )
    guidance.compute_reference(0, route, NavigationState(10.0, 3.0, 0.0, 2.0, 0.0, 0.0), 0.1)
    assert guidance.latest_trace.segment_index == 0
    assert guidance.latest_trace.speed_reference_mps == 2.0
