"""Clean ILOS guidance module: separable mathematics, route lifecycle, stack flow (Issue #57)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from colav_simulator.modular_gnc.configuration import UnsupportedModuleCombinationError, normalize_ship_modules
from colav_simulator.modular_gnc.contracts import (
    CommandInput,
    ControlTask,
    DirectReference,
    FailureCode,
    NavigationState,
    TrackedRoute,
)
from colav_simulator.modular_gnc.guidance_ilos import ILOSConfig, IntegralLineOfSightGuidance
from colav_simulator.modular_gnc.stack import ModularShipStack

_UNIT_CONFIG = ILOSConfig(
    lookahead_distance_m=50.0,
    integral_gain=0.001,
    max_integral_cross_track_error_m=30.0,
    integral_error_threshold_m=50.0,
    max_speed_mps=10.0,
)

_STRAIGHT_WAYPOINTS = [[0.0, 1000.0], [0.0, 0.0]]
_TURN_WAYPOINTS = [[0.0, 300.0, 300.0], [0.0, 0.0, 200.0]]


def _route(
    waypoints: list[list[float]],
    speeds: list[float],
    route_id: str = "route-a",
    revision: int = 0,
    valid_from_tick: int = 0,
    valid_until_tick: int = 10000,
    task: ControlTask = ControlTask.TRANSIT,
) -> TrackedRoute:
    return TrackedRoute(
        route_id=route_id,
        revision=revision,
        accepted=True,
        valid_from_tick=valid_from_tick,
        valid_until_tick=valid_until_tick,
        waypoints_ne_m=np.array(waypoints, dtype=np.float64),
        speed_mps=np.array(speeds, dtype=np.float64),
        task=task,
    )


def _navigation(north: float, east: float, heading: float = 0.0, surge: float = 2.0) -> NavigationState:
    return NavigationState(north, east, heading, surge, 0.0, 0.0)


def _unit_guidance() -> IntegralLineOfSightGuidance:
    return IntegralLineOfSightGuidance(_UNIT_CONFIG)


# --- Module-level mathematics: projection, progress, cross-track, lookahead law ---


class TestILOSModuleMath:
    def test_on_path_vessel_zero_cross_track_full_progress_course_along_path(self) -> None:
        guidance = _unit_guidance()
        route = _route(_STRAIGHT_WAYPOINTS, [2.0, 2.0])

        reference = guidance.compute_reference(0, route, _navigation(100.0, 0.0), dt_s=0.1)

        trace = guidance.latest_trace
        assert trace is not None
        assert trace.segment_index == 0
        assert math.isclose(trace.progress_m, 100.0)
        assert math.isclose(trace.cross_track_error_m, 0.0)
        assert math.isclose(trace.course_reference_rad, 0.0, abs_tol=1e-12)
        assert math.isclose(trace.speed_reference_mps, 2.0)
        assert trace.route_state_reset is False
        assert reference.values[2] == pytest.approx(0.0, abs=1e-12)
        assert reference.values[3] == pytest.approx(2.0)
        assert reference.latched_tick == 0
        assert reference.task is ControlTask.TRANSIT

    def test_vessel_right_of_path_positive_cross_track_and_lookahead_correction(self) -> None:
        guidance = _unit_guidance()
        route = _route(_STRAIGHT_WAYPOINTS, [2.0, 2.0])

        guidance.compute_reference(0, route, _navigation(0.0, 50.0), dt_s=0.1)

        trace = guidance.latest_trace
        assert trace is not None
        assert math.isclose(trace.cross_track_error_m, 50.0)
        # chi_d = alpha + chi_r = 0 - atan((1/Delta)*e) = -45 deg for e = Delta = 50 m.
        assert trace.course_reference_rad == pytest.approx(-math.pi / 4.0)

    def test_vessel_left_of_path_negative_cross_track_symmetric_correction(self) -> None:
        guidance = _unit_guidance()
        route = _route(_STRAIGHT_WAYPOINTS, [2.0, 2.0])

        guidance.compute_reference(0, route, _navigation(0.0, -50.0), dt_s=0.1)

        trace = guidance.latest_trace
        assert trace is not None
        assert math.isclose(trace.cross_track_error_m, -50.0)
        assert trace.course_reference_rad == pytest.approx(math.pi / 4.0)

    def test_beyond_final_waypoint_progress_saturates_at_terminal_waypoint(self) -> None:
        guidance = _unit_guidance()
        route = _route(_STRAIGHT_WAYPOINTS, [2.0, 2.0])

        guidance.compute_reference(0, route, _navigation(1100.0, 30.0), dt_s=0.1)

        trace = guidance.latest_trace
        assert trace is not None
        assert math.isclose(trace.progress_m, 1000.0)
        assert math.isclose(trace.cross_track_error_m, 30.0)
        assert trace.course_reference_rad == pytest.approx(-math.atan(30.0 / 50.0))

    def test_turn_route_projection_selects_nearest_segment(self) -> None:
        guidance = _unit_guidance()
        route = _route([[0.0, 800.0, 800.0], [0.0, 0.0, 600.0]], [2.0, 2.0, 2.0])

        guidance.compute_reference(0, route, _navigation(700.0, 50.0), dt_s=0.1)
        trace = guidance.latest_trace
        assert trace is not None
        assert trace.segment_index == 0
        assert math.isclose(trace.progress_m, 700.0)
        assert math.isclose(trace.cross_track_error_m, 50.0)

        guidance.reset()
        guidance.compute_reference(0, route, _navigation(700.0, 300.0), dt_s=0.1)
        trace = guidance.latest_trace
        assert trace is not None
        assert trace.segment_index == 1
        # progress = leg 1 length (800) + 300 along leg 2; alpha = pi/2, e = +100.
        assert math.isclose(trace.progress_m, 1100.0)
        assert math.isclose(trace.cross_track_error_m, 100.0)
        assert trace.course_reference_rad == pytest.approx(math.pi / 2.0 - math.atan(100.0 / 50.0))

    def test_route_speed_taken_at_active_segment_start_waypoint(self) -> None:
        guidance = _unit_guidance()
        route = _route([[0.0, 800.0, 800.0], [0.0, 0.0, 600.0]], [2.0, 5.0, 5.0])

        guidance.compute_reference(0, route, _navigation(700.0, 300.0), dt_s=0.1)

        trace = guidance.latest_trace
        assert trace is not None
        assert trace.segment_index == 1
        assert math.isclose(trace.route_speed_mps, 5.0)
        assert math.isclose(trace.speed_reference_mps, 5.0)


# --- Integral state: accumulation, threshold gate, saturation ---


class TestILOSIntegralState:
    def test_integral_accumulates_over_elapsed_time_and_saturates_at_limit(self) -> None:
        guidance = _unit_guidance()
        route = _route(_STRAIGHT_WAYPOINTS, [2.0, 2.0])
        nav = _navigation(0.0, 10.0)  # e = +10, inside threshold

        expected = [0.0, 10.0, 20.0, 30.0, 30.0]
        for call, want in enumerate(expected):
            guidance.compute_reference(call, route, nav, dt_s=1.0)
            trace = guidance.latest_trace
            assert trace is not None
            assert trace.integral_cross_track_error_m == pytest.approx(want)
            assert trace.integral_updated is (want > 0.0)

    def test_integral_gate_blocks_large_cross_track_error(self) -> None:
        guidance = _unit_guidance()
        route = _route(_STRAIGHT_WAYPOINTS, [2.0, 2.0])
        nav = _navigation(0.0, 200.0)  # e = 200 > threshold 50

        for tick in range(5):
            guidance.compute_reference(tick, route, nav, dt_s=1.0)
            trace = guidance.latest_trace
            assert trace is not None
            assert trace.integral_cross_track_error_m == 0.0
            assert trace.integral_updated is False

    def test_integral_uses_elapsed_ticks_between_guidance_calls(self) -> None:
        guidance = _unit_guidance()
        route = _route(_STRAIGHT_WAYPOINTS, [2.0, 2.0])
        nav = _navigation(0.0, 10.0)

        guidance.compute_reference(0, route, nav, dt_s=0.1)
        guidance.compute_reference(10, route, nav, dt_s=0.1)

        trace = guidance.latest_trace
        assert trace is not None
        # elapsed = 10 ticks * 0.1 s = 1.0 s of integration at e = 10.
        assert math.isclose(trace.integration_dt_s, 1.0)
        assert trace.integral_cross_track_error_m == pytest.approx(10.0)


# --- Speed ceiling ---


class TestILOSSpeedCeiling:
    def test_speed_ceiling_caps_route_speed_reference(self) -> None:
        guidance = IntegralLineOfSightGuidance(ILOSConfig(max_speed_mps=3.0))
        route = _route(_TURN_WAYPOINTS, [2.0, 5.0, 5.0])

        guidance.compute_reference(0, route, _navigation(700.0, 300.0), dt_s=0.1)

        trace = guidance.latest_trace
        assert trace is not None
        assert math.isclose(trace.route_speed_mps, 5.0)
        assert math.isclose(trace.speed_reference_mps, 3.0)
        assert trace.speed_ceiling_applied is True
        assert guidance.latest_trace is not None
        assert guidance.latest_trace.speed_ceiling_mps == pytest.approx(3.0)

    def test_speed_below_ceiling_passes_route_speed_through(self) -> None:
        guidance = IntegralLineOfSightGuidance(ILOSConfig(max_speed_mps=8.0))
        route = _route(_STRAIGHT_WAYPOINTS, [2.0, 2.0])

        guidance.compute_reference(0, route, _navigation(100.0, 0.0), dt_s=0.1)

        trace = guidance.latest_trace
        assert trace is not None
        assert math.isclose(trace.speed_reference_mps, 2.0)
        assert trace.speed_ceiling_applied is False


# --- Route lifecycle: switch, revision, identity continuity ---


class TestILOSRouteLifecycle:
    def test_route_switch_rejects_discontinuity_by_resetting_integral(self) -> None:
        guidance = _unit_guidance()
        route_a = _route(_STRAIGHT_WAYPOINTS, [2.0, 2.0], route_id="route-a")
        nav_a = _navigation(0.0, 10.0)
        for tick in range(4):
            guidance.compute_reference(tick, route_a, nav_a, dt_s=1.0)
        assert guidance.latest_trace is not None
        assert guidance.latest_trace.integral_cross_track_error_m == pytest.approx(30.0)

        # Discontinuous switch: geometrically far route under a new identity.
        route_b = _route([[0.0, 1000.0], [500.0, 500.0]], [2.0, 2.0], route_id="route-b")
        nav_b = _navigation(30.0, 10.0)

        guidance.compute_reference(4, route_b, nav_b, dt_s=1.0)

        trace = guidance.latest_trace
        assert trace is not None
        assert trace.route_state_reset is True
        assert trace.route_id == "route-b"
        # e = (10 - 500) = -490, outside threshold: carried-over integral is rejected.
        assert trace.integral_cross_track_error_m == 0.0
        assert math.isclose(trace.cross_track_error_m, -490.0)

    def test_revision_bump_rejects_discontinuity_by_resetting_integral(self) -> None:
        guidance = _unit_guidance()
        route_v0 = _route(_STRAIGHT_WAYPOINTS, [2.0, 2.0], route_id="route-a", revision=0)
        for tick in range(4):
            guidance.compute_reference(tick, route_v0, _navigation(0.0, 10.0), dt_s=1.0)
        assert guidance.latest_trace is not None
        assert guidance.latest_trace.integral_cross_track_error_m == pytest.approx(30.0)

        route_v1 = _route([[0.0, 1000.0], [500.0, 500.0]], [2.0, 2.0], route_id="route-a", revision=1)

        guidance.compute_reference(4, route_v1, _navigation(30.0, 10.0), dt_s=1.0)

        trace = guidance.latest_trace
        assert trace is not None
        assert trace.route_state_reset is True
        assert trace.integral_cross_track_error_m == 0.0

    def test_same_route_identity_keeps_integral_state(self) -> None:
        guidance = _unit_guidance()
        route = _route(_STRAIGHT_WAYPOINTS, [2.0, 2.0])
        nav = _navigation(0.0, 10.0)

        guidance.compute_reference(0, route, nav, dt_s=1.0)
        guidance.compute_reference(1, route, nav, dt_s=1.0)

        trace = guidance.latest_trace
        assert trace is not None
        assert trace.route_state_reset is False
        assert trace.integral_cross_track_error_m == pytest.approx(10.0)


# --- Reset, snapshot, capability declaration ---


class TestILOSResetAndSnapshot:
    def test_reset_clears_integral_identity_and_trace(self) -> None:
        guidance = _unit_guidance()
        route = _route(_STRAIGHT_WAYPOINTS, [2.0, 2.0])
        nav = _navigation(0.0, 10.0)
        for tick in range(3):
            guidance.compute_reference(tick, route, nav, dt_s=1.0)

        guidance.reset()

        assert guidance.latest_trace is None
        guidance.compute_reference(0, route, nav, dt_s=1.0)
        trace = guidance.latest_trace
        assert trace is not None
        assert trace.integral_cross_track_error_m == 0.0
        assert trace.route_state_reset is False

    def test_snapshot_restore_roundtrip_is_bit_exact(self) -> None:
        route = _route(_STRAIGHT_WAYPOINTS, [2.0, 2.0])
        nav = _navigation(0.0, 10.0)

        first = _unit_guidance()
        for tick in range(2):
            first.compute_reference(tick, route, nav, dt_s=1.0)
        snapshot = first.snapshot()
        expected_reference = first.compute_reference(2, route, nav, dt_s=1.0)
        expected_state = first.snapshot()

        second = _unit_guidance()
        second.compute_reference(0, route, nav, dt_s=1.0)
        second.restore(snapshot)
        replayed_reference = second.compute_reference(2, route, nav, dt_s=1.0)

        assert replayed_reference == expected_reference
        assert second.snapshot() == expected_state

    def test_supported_tasks_declares_transit_only(self) -> None:
        assert _unit_guidance().supported_tasks == frozenset({ControlTask.TRANSIT})


# --- Configuration and registry ---


class TestILOSConfig:
    def test_config_validation_rejects_invalid_parameters(self) -> None:
        with pytest.raises(ValueError, match="lookahead_distance_m"):
            ILOSConfig(lookahead_distance_m=0.0)
        with pytest.raises(ValueError, match="lookahead_distance_m"):
            ILOSConfig(lookahead_distance_m=-1.0)
        with pytest.raises(ValueError, match="integral_gain"):
            ILOSConfig(integral_gain=-1e-6)
        with pytest.raises(ValueError, match="max_integral_cross_track_error_m"):
            ILOSConfig(max_integral_cross_track_error_m=0.0)
        with pytest.raises(ValueError, match="integral_error_threshold_m"):
            ILOSConfig(integral_error_threshold_m=-1.0)
        with pytest.raises(ValueError, match="max_speed_mps"):
            ILOSConfig(max_speed_mps=0.0)

    def test_config_from_params_maps_all_registry_parameters(self) -> None:
        config = ILOSConfig.from_params(
            {
                "lookahead_distance_m": 25.0,
                "integral_gain": 0.002,
                "max_integral_cross_track_error_m": 500.0,
                "integral_error_threshold_m": 40.0,
                "max_speed_mps": 6.0,
            }
        )

        assert config.lookahead_distance_m == 25.0
        assert config.integral_gain == 0.002
        assert config.max_integral_cross_track_error_m == 500.0
        assert config.integral_error_threshold_m == 40.0
        assert config.max_speed_mps == 6.0

    def test_config_has_deterministic_defaults(self) -> None:
        config = ILOSConfig()
        assert config.lookahead_distance_m == 50.0
        assert config.integral_gain == 0.0001
        assert config.max_integral_cross_track_error_m == 1000.0
        assert config.integral_error_threshold_m == 50.0
        assert config.max_speed_mps == 10.0

    def test_registry_accepts_ilos_identity_and_rejects_unknown_parameters(self) -> None:
        base = {
            "preset": "legacy_equivalent",
            "modules": {
                "plant": {"identity": "pass_through_plant", "parameters": {}},
                "guidance": {"identity": "integral_line_of_sight", "parameters": {}},
                "controller": {"identity": "pass_through_controller", "parameters": {}},
            },
        }
        default_config = normalize_ship_modules(base)
        tuned = normalize_ship_modules({**base, "modules": {**base["modules"], "guidance": {
            "identity": "integral_line_of_sight",
            "parameters": {"lookahead_distance_m": 25.0},
        }}})
        assert default_config.config_hash != tuned.config_hash

        unknown = {**base, "modules": {**base["modules"], "guidance": {
            "identity": "integral_line_of_sight",
            "parameters": {"nav_bias": 1.0},
        }}}
        with pytest.raises(UnsupportedModuleCombinationError, match="nav_bias"):
            normalize_ship_modules(unknown)
        wrong_type = {**base, "modules": {**base["modules"], "guidance": {
            "identity": "integral_line_of_sight",
            "parameters": {"lookahead_distance_m": "far"},
        }}}
        with pytest.raises(UnsupportedModuleCombinationError, match="lookahead_distance_m"):
            normalize_ship_modules(wrong_type)

    def test_from_config_builds_stack_with_ilos_guidance_snapshot(self) -> None:
        config = normalize_ship_modules(
            {
                "preset": "legacy_equivalent",
                "modules": {
                    "plant": {"identity": "pass_through_plant", "parameters": {}},
                    "guidance": {"identity": "integral_line_of_sight", "parameters": {}},
                    "controller": {"identity": "pass_through_controller", "parameters": {}},
                },
            }
        )
        stack = ModularShipStack.from_config(config, episode_seed=0, dt_s=0.1)
        stack.reset(NavigationState(0.0, 30.0, 0.0, 0.0, 0.0, 0.0), seed=3)

        snapshot = stack.modules.snapshot()
        assert snapshot.guidance_snapshot is not None
        assert snapshot.guidance_snapshot.latest_trace is None
        assert snapshot.held_guidance_reference is None
        assert stack.modules.supported_tasks == frozenset({ControlTask.TRANSIT})


# --- Stack guidance flow: authority routing, cadence, lifecycle rejection ---


def _kinematic_ilos_config(guidance_params: dict | None = None, guidance_period: int = 1) -> dict:
    return {
        "preset": "legacy_equivalent",
        "overrides": {
            "scheduler": {
                "plant_period_ticks": 1,
                "controller_period_ticks": 1,
                "guidance_period_ticks": guidance_period,
            }
        },
        "modules": {
            "plant": {"identity": "pass_through_plant", "parameters": {}},
            "guidance": {"identity": "integral_line_of_sight", "parameters": guidance_params or {}},
            "controller": {"identity": "pass_through_controller", "parameters": {}},
        },
    }


def _kinematic_ilos_stack(guidance_params: dict | None = None, guidance_period: int = 1) -> ModularShipStack:
    stack = ModularShipStack.from_config(
        normalize_ship_modules(_kinematic_ilos_config(guidance_params, guidance_period)), episode_seed=0, dt_s=0.1
    )
    stack.reset(NavigationState(0.0, 30.0, 0.0, 0.0, 0.0, 0.0), seed=5)
    return stack


def _north_route(valid_until_tick: int = 10000, **kwargs: object) -> TrackedRoute:
    return _route(_STRAIGHT_WAYPOINTS, [2.0, 2.0], valid_until_tick=valid_until_tick, **kwargs)


class TestILOSStackGuidanceFlow:
    def test_route_authority_flows_reference_to_kinematic_plant(self) -> None:
        stack = _kinematic_ilos_stack()

        output = stack.step(CommandInput.route(0, _north_route()), dt_s=0.1)

        assert output.failure is None
        trace = stack.modules.guidance_trace()
        assert trace is not None
        assert stack.modules.plant_state().values[2] == pytest.approx(trace.course_reference_rad)
        assert stack.modules.plant_state().values[3] == pytest.approx(trace.speed_reference_mps)
        assert output.applied_reference is None

    def test_direct_authority_bypasses_ilos_guidance(self) -> None:
        stack = _kinematic_ilos_stack()
        values = np.zeros(9)
        values[2] = 0.3
        values[3] = 4.0

        output = stack.step(CommandInput.direct(0, DirectReference(values, latched_tick=0)), dt_s=0.1)

        assert output.failure is None
        assert stack.modules.guidance_trace() is None
        assert stack.modules.route_consumptions == ()
        assert stack.modules.plant_state().values[2] == pytest.approx(0.3)
        assert stack.modules.plant_state().values[3] == pytest.approx(4.0)

    def test_guidance_consumes_route_only_on_due_ticks_and_holds_reference(self) -> None:
        stack = _kinematic_ilos_stack(guidance_period=5)
        route = _north_route()

        for tick in range(12):
            output = stack.step(CommandInput.route(tick, route), dt_s=0.1)
            assert output.failure is None

        assert stack.modules.route_consumptions == ((0, "route-a", 0), (5, "route-a", 0), (10, "route-a", 0))
        trace = stack.modules.guidance_trace()
        assert trace is not None
        assert trace.tick == 10

    def test_terminal_task_route_rejected_before_guidance_executes(self) -> None:
        stack = _kinematic_ilos_stack()
        before = stack.snapshot()

        for task in (ControlTask.POSE_HOLD, ControlTask.CONTROLLED_STOP):
            output = stack.step(CommandInput.route(0, _north_route(task=task)), dt_s=0.1)

            assert output.failure is not None
            assert output.failure.code is FailureCode.CAPABILITY_MISMATCH
            assert stack.modules.guidance_trace() is None
            assert stack.modules.route_consumptions == ()
        assert stack.snapshot() == before

    def test_route_expiry_freezes_guidance_state_with_structured_failure(self) -> None:
        stack = _kinematic_ilos_stack()
        route = _north_route(valid_until_tick=30)
        for tick in range(31):
            output = stack.step(CommandInput.route(tick, route), dt_s=0.1)
            assert output.failure is None
        before = stack.snapshot()
        last_trace = stack.modules.guidance_trace()
        assert last_trace is not None

        failed = stack.step(CommandInput.none(31), dt_s=0.1)

        assert failed.failure is not None
        assert failed.failure.code is FailureCode.EXPIRED_ROUTE
        assert failed.failure.details == {"route_id": "route-a", "valid_until_tick": 30}
        assert stack.modules.guidance_trace() == last_trace
        assert stack.snapshot() == before


# --- Closed-loop stack runs with force plant + marine PID ---


_PLANT_PARAMS = {
    "mass_kg": 1.6e7,
    "i_z_kgm2": 3.0e10,
    "x_g_m": 0.0,
    "x_dot_u_kg": -5.0e6,
    "y_dot_v_kg": -3.5e7,
    "n_dot_r_kgm2": -2.0e10,
    "y_dot_r_kgm": 1.0e6,
    "n_dot_v_kgm": 1.0e6,
    "d_u": 5.0e4,
    "d_uu": 2.0e5,
    "d_v": 3.0e5,
    "d_vv": 1.5e6,
    "d_r": 8.0e7,
    "d_rr": 2.5e9,
}

_MARINE_PID_PARAMS = {
    "kp": [1.5e6, 1.0e6, 5.0e9],
    "ki": [3.0e5, 1.0e5, 0.0],
    "kd": [0.0, 0.0, 4.0e10],
    "tau_d": [0.1, 0.1, 0.1],
    "antiwindup_gain": [1.0, 1.0, 1.0],
    "min_output": [-3.0e6, -1.5e6, -5.0e9],
    "max_output": [3.0e6, 1.5e6, 5.0e9],
    "integral_limit": [1.0e6, 5.0e5, 0.0],
    "allow_ideal_passthrough": True,
}


def _force_ilos_config(environment: bool = False) -> dict:
    if environment:
        # Integral sized to reject the small current-induced course bias; the
        # disturbance itself enters only through the environment/load seams.
        guidance_params = {
            "lookahead_distance_m": 150.0,
            "integral_gain": 0.001,
            "max_integral_cross_track_error_m": 400.0,
            "integral_error_threshold_m": 60.0,
        }
    else:
        # Lookahead separates guidance bandwidth from heading response so the
        # closed loop converges monotonically; tight gate keeps the integral
        # out of the large initial transient.
        guidance_params = {"lookahead_distance_m": 150.0, "integral_error_threshold_m": 10.0}
    modules = {
        "plant": {"identity": "generic_3dof_plant", "parameters": dict(_PLANT_PARAMS)},
        "guidance": {"identity": "integral_line_of_sight", "parameters": guidance_params},
        "controller": {"identity": "marine_pid", "parameters": dict(_MARINE_PID_PARAMS)},
    }
    if environment:
        modules["environment"] = {
            "identity": "analytic_environment_field",
            "parameters": {
                "wind_velocity_ne": [0.0, 0.0],
                "wind_reference_height_m": 10.0,
                "wind_perturbation_std": [0.0, 0.0],
                "current_velocity_ne": [0.15, -0.2],
                "current_reference": "surface",
                "current_perturbation_std": [0.0, 0.0],
                "wave_significant_height_m": 0.0,
                "wave_peak_period_s": 7.5,
                "wave_direction_to_rad": 0.4,
                "wave_num_components": 2,
                "wave_directional_spread_rad": 0.0,
            },
        }
        modules["load_model"] = {
            "identity": "standard_environmental_load",
            "parameters": {
                "enable_wind": False,
                "enable_current": True,
                "current_strategy": "external_current_load",
                "wave_mode": "off",
            },
        }
    return {
        "preset": "legacy_equivalent",
        "overrides": {
            "scheduler": {"plant_period_ticks": 1, "controller_period_ticks": 1, "guidance_period_ticks": 1}
        },
        "modules": modules,
    }


def _run_route(stack: ModularShipStack, route: TrackedRoute, ticks: int, dt_s: float = 0.1) -> list:
    outputs = []
    for tick in range(ticks):
        output = stack.step(CommandInput.route(tick, route), dt_s=dt_s)
        assert output.failure is None
        outputs.append(output)
    return outputs


class TestILOSStackClosedLoop:
    def test_straight_route_cross_track_convergence(self) -> None:
        stack = ModularShipStack.from_config(normalize_ship_modules(_force_ilos_config()), episode_seed=0, dt_s=0.1)
        stack.reset(NavigationState(0.0, 30.0, 0.0, 0.0, 0.0, 0.0), seed=11)

        _run_route(stack, _north_route(), ticks=4000)

        trace = stack.modules.guidance_trace()
        assert trace is not None
        assert abs(trace.cross_track_error_m) < 1.0
        assert trace.progress_m > 100.0

    def test_turn_route_tracks_around_corner(self) -> None:
        stack = ModularShipStack.from_config(normalize_ship_modules(_force_ilos_config()), episode_seed=0, dt_s=0.1)
        stack.reset(NavigationState(0.0, 5.0, 0.0, 0.0, 0.0, 0.0), seed=11)

        # Long second leg so the run ends mid-tracking, not at the route end.
        _run_route(stack, _route([[0.0, 300.0, 300.0], [0.0, 0.0, 2000.0]], [2.0, 2.0, 2.0]), ticks=6000)

        trace = stack.modules.guidance_trace()
        assert trace is not None
        assert trace.segment_index == 1
        assert trace.progress_m > 500.0
        assert abs(trace.cross_track_error_m) < 3.0

    def test_large_initial_error_recovers_without_immediate_integral_windup(self) -> None:
        stack = ModularShipStack.from_config(normalize_ship_modules(_force_ilos_config()), episode_seed=0, dt_s=0.1)
        stack.reset(NavigationState(0.0, 200.0, 0.0, 0.0, 0.0, 0.0), seed=11)
        route = _north_route()

        early_trace = None
        for tick in range(4000):
            output = stack.step(CommandInput.route(tick, route), dt_s=0.1)
            assert output.failure is None
            if tick == 100:
                early_trace = stack.modules.guidance_trace()

        assert early_trace is not None
        assert early_trace.integral_cross_track_error_m == 0.0
        trace = stack.modules.guidance_trace()
        assert trace is not None
        assert abs(trace.cross_track_error_m) < 5.0

    def test_current_disturbance_enters_via_environment_seam_and_loop_converges(self) -> None:
        stack = ModularShipStack.from_config(
            normalize_ship_modules(_force_ilos_config(environment=True)), episode_seed=7, dt_s=0.1
        )
        stack.reset(NavigationState(0.0, 0.0, 0.0, 0.0, 0.0, 0.0), seed=11)

        outputs = _run_route(stack, _north_route(), ticks=3000)

        assert outputs[-1].environment_observation is not None
        loads = outputs[-1].environmental_loads
        assert loads is not None
        assert math.hypot(loads.current.surge_n, loads.current.sway_n) > 0.0
        trace = stack.modules.guidance_trace()
        assert trace is not None
        assert abs(trace.cross_track_error_m) < 2.0


class TestILOSStackLifecycle:
    def test_route_switch_resets_integral_at_stack_level(self) -> None:
        stack = _kinematic_ilos_stack()
        route_a = _north_route()

        for tick in range(10):
            stack.step(CommandInput.route(tick, route_a), dt_s=0.1)
        before_switch = stack.modules.guidance_trace()
        assert before_switch is not None
        assert before_switch.integral_cross_track_error_m > 0.0

        route_b = _route([[0.0, 1000.0], [0.0, 500.0]], [2.0, 2.0], route_id="route-b")
        output = stack.step(CommandInput.route(10, route_b), dt_s=0.1)

        assert output.failure is None
        switched = stack.modules.guidance_trace()
        assert switched is not None
        assert switched.route_state_reset is True
        assert switched.integral_cross_track_error_m == 0.0

        stack.step(CommandInput.route(11, route_b), dt_s=0.1)
        after = stack.modules.guidance_trace()
        assert after is not None
        assert after.route_state_reset is False
        assert after.integral_cross_track_error_m > 0.0

    def test_snapshot_restore_bit_exact_with_guidance_state(self) -> None:
        stack = ModularShipStack.from_config(normalize_ship_modules(_force_ilos_config()), episode_seed=0, dt_s=0.1)
        stack.reset(NavigationState(0.0, 30.0, 0.0, 0.0, 0.0, 0.0), seed=11)
        route = _north_route()
        for tick in range(40):
            stack.step(CommandInput.route(tick, route), dt_s=0.1)

        snapshot = stack.snapshot()
        expected = [stack.step(CommandInput.route(t, route), dt_s=0.1) for t in range(40, 45)]
        expected_trace = stack.modules.guidance_trace()

        stack.restore(snapshot)
        replayed = [stack.step(CommandInput.route(t, route), dt_s=0.1) for t in range(40, 45)]

        assert replayed == expected
        assert stack.modules.guidance_trace() == expected_trace

    def test_reset_replay_determinism_with_guidance_state(self) -> None:
        stack = ModularShipStack.from_config(normalize_ship_modules(_force_ilos_config()), episode_seed=0, dt_s=0.1)
        route = _north_route()

        stack.reset(NavigationState(0.0, 30.0, 0.0, 0.0, 0.0, 0.0), seed=11)
        first = [stack.step(CommandInput.route(t, route), dt_s=0.1) for t in range(30)]
        first_traces = stack.modules.guidance_trace()

        stack.reset(NavigationState(0.0, 30.0, 0.0, 0.0, 0.0, 0.0), seed=11)
        second = [stack.step(CommandInput.route(t, route), dt_s=0.1) for t in range(30)]

        assert second == first
        assert stack.modules.guidance_trace() == first_traces
