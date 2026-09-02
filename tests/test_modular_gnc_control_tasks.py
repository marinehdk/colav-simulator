"""Explicit ControlTask modeling and execution-time capability rejection (Issue #56, AC1/AC2)."""

from __future__ import annotations

import numpy as np
import pytest

from colav_simulator.modular_gnc.configuration import normalize_ship_modules
from colav_simulator.modular_gnc.contracts import (
    CommandInput,
    ControlTask,
    DirectReference,
    FailureCode,
    NavigationState,
    TrackedRoute,
)
from colav_simulator.modular_gnc.stack import ModularShipStack

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
    "kp": [1000.0, 500.0, 2000.0],
    "ki": [100.0, 50.0, 200.0],
    "kd": [200.0, 100.0, 400.0],
    "tau_d": [0.1, 0.1, 0.1],
    "antiwindup_gain": [1.0, 1.0, 1.0],
    "min_output": [-10000.0, -5000.0, -20000.0],
    "max_output": [10000.0, 5000.0, 20000.0],
    "feedforward_gain": [0.0, 0.0, 0.0],
    "allow_ideal_passthrough": True,
}


def _legacy_equivalent_config() -> dict:
    return {
        "preset": "legacy_equivalent",
        "modules": {
            "plant": {"identity": "pass_through_plant", "parameters": {}},
            "guidance": {"identity": "pass_through_guidance", "parameters": {}},
            "controller": {"identity": "pass_through_controller", "parameters": {}},
        },
    }


def _generic_plant_passthrough_config() -> dict:
    return {
        "preset": "legacy_equivalent",
        "modules": {
            "plant": {"identity": "generic_3dof_plant", "parameters": dict(_PLANT_PARAMS)},
            "guidance": {"identity": "pass_through_guidance", "parameters": {}},
            "controller": {"identity": "pass_through_controller", "parameters": {}},
        },
    }


def _generic_plant_marine_pid_config(*, position_mode: bool = False) -> dict:
    params = dict(_MARINE_PID_PARAMS)
    params["position_mode"] = position_mode
    return {
        "preset": "legacy_equivalent",
        "modules": {
            "plant": {"identity": "generic_3dof_plant", "parameters": dict(_PLANT_PARAMS)},
            "guidance": {"identity": "pass_through_guidance", "parameters": {}},
            "controller": {"identity": "marine_pid", "parameters": params},
        },
    }


def _transit_reference(tick: int, task: ControlTask = ControlTask.TRANSIT) -> CommandInput:
    values = np.zeros(9)
    values[2] = 0.3
    values[3] = 2.0
    return CommandInput.direct(tick, DirectReference(values, latched_tick=tick, task=task))


def _build_stack(config: dict) -> ModularShipStack:
    stack = ModularShipStack.from_config(normalize_ship_modules(config))
    stack.reset(NavigationState(0.0, 0.0, 0.0, 0.0, 0.0, 0.0), seed=7)
    return stack


def _position_mode_stack() -> ModularShipStack:
    """Force plant + position-mode marine_pid: both TRANSIT and POSE_HOLD executable."""
    config = _generic_plant_marine_pid_config(position_mode=True)
    config["overrides"] = {"scheduler": {"plant_period_ticks": 1, "controller_period_ticks": 1}}
    return _build_stack(config)


def _pose_reference(tick: int, north: float, east: float, heading: float, task: ControlTask) -> CommandInput:
    values = np.zeros(9)
    values[0] = north
    values[1] = east
    values[2] = heading
    return CommandInput.direct(tick, DirectReference(values, latched_tick=tick, task=task))


class TestExecutionTimeTaskRejection:
    """Unsupported tasks are rejected before any phase executes (AC1)."""

    def test_pose_hold_rejected_before_execution_on_legacy_equivalent_profile(self) -> None:
        stack = _build_stack(_legacy_equivalent_config())
        stack.step(_transit_reference(0), dt_s=0.1)
        before = stack.snapshot()

        output = stack.step(_transit_reference(1, task=ControlTask.POSE_HOLD), dt_s=0.1)

        assert output.failure is not None
        assert output.failure.code is FailureCode.CAPABILITY_MISMATCH
        assert output.failure.phase == "facade"
        assert "POSE_HOLD" in output.failure.message
        after = stack.snapshot()
        assert after.tick == before.tick
        assert after == before

    @pytest.mark.parametrize(
        "config",
        [
            _legacy_equivalent_config(),
            _generic_plant_passthrough_config(),
            _generic_plant_marine_pid_config(),
        ],
    )
    def test_controlled_stop_rejected_on_every_current_module_tuple(self, config: dict) -> None:
        stack = _build_stack(config)

        output = stack.step(_transit_reference(0, task=ControlTask.CONTROLLED_STOP), dt_s=0.1)

        assert output.failure is not None
        assert output.failure.code is FailureCode.CAPABILITY_MISMATCH
        assert stack.tick == 0

    def test_manual_load_rejected_when_controller_cannot_execute_it(self) -> None:
        stack = _build_stack(_generic_plant_marine_pid_config())
        values = np.zeros(9)
        values[0] = 1.0e5
        command = CommandInput.direct(
            0, DirectReference(values, latched_tick=0, task=ControlTask.MANUAL_LOAD)
        )

        output = stack.step(command, dt_s=0.1)

        assert output.failure is not None
        assert output.failure.code is FailureCode.CAPABILITY_MISMATCH
        assert stack.tick == 0

    def test_manual_load_executes_on_force_plant_with_pass_through_controller(self) -> None:
        stack = _build_stack(_generic_plant_passthrough_config())
        values = np.zeros(9)
        values[0] = 2.1e5
        command = CommandInput.direct(
            0, DirectReference(values, latched_tick=0, task=ControlTask.MANUAL_LOAD)
        )

        output = stack.step(command, dt_s=1.0)

        assert output.failure is None
        assert output.navigation.surge_mps > 0.0

    def test_pose_hold_executes_with_position_mode_marine_pid(self) -> None:
        stack = _build_stack(_generic_plant_marine_pid_config(position_mode=True))
        values = np.zeros(9)
        values[0] = 5.0
        values[1] = -5.0
        values[2] = 0.2
        command = CommandInput.direct(
            0, DirectReference(values, latched_tick=0, task=ControlTask.POSE_HOLD)
        )

        output = stack.step(command, dt_s=0.1)

        assert output.failure is None
        assert output.controller_trace is not None

    def test_unsupported_tracked_route_task_rejected_before_guidance(self) -> None:
        stack = _build_stack(_legacy_equivalent_config())
        route = TrackedRoute(
            route_id="r1",
            revision=0,
            accepted=True,
            valid_from_tick=0,
            valid_until_tick=10,
            waypoints_ne_m=np.array([[0.0, 10.0], [0.0, 20.0]]),
            speed_mps=np.array([2.0, 2.0]),
            task=ControlTask.POSE_HOLD,
        )

        output = stack.step(CommandInput.route(0, route), dt_s=0.1)

        assert output.failure is not None
        assert output.failure.code is FailureCode.CAPABILITY_MISMATCH
        assert stack.tick == 0


class TestBumplessTransitPoseHoldTransfer:
    """Deterministic bumpless transfer contract for TRANSIT <-> POSE_HOLD (Issue #56, AC2).

    Derived from existing controller/stack semantics:
    - marine_pid computes derivative on measurement and never consults the task label,
      so a task transition must not reset or rebase any controller internal state
      (integral, previous measurement, filtered derivative).
    - Therefore a pure task relabel with identical reference values must produce a
      bit-identical trajectory, and the integral recursion must continue across the
      transition boundary without discontinuity.
    """

    @staticmethod
    def _run_transit_then_task(tick_of_transfer: int, transfer_task: ControlTask) -> list:
        stack = _position_mode_stack()
        outputs = []
        for tick in range(6):
            if tick < tick_of_transfer:
                command = _pose_reference(tick, 5.0, -5.0, 0.2, ControlTask.TRANSIT)
            elif tick == tick_of_transfer:
                command = _pose_reference(tick, 5.0, -5.0, 0.2, transfer_task)
            else:
                command = _pose_reference(tick, 5.0, -5.0, 0.2, transfer_task)
            output = stack.step(command, dt_s=0.1)
            assert output.failure is None
            outputs.append(output)
        return outputs

    def test_task_relabel_with_identical_values_is_bit_identical(self) -> None:
        transit_run = self._run_transit_then_task(3, ControlTask.TRANSIT)
        pose_hold_run = self._run_transit_then_task(3, ControlTask.POSE_HOLD)

        for transit_out, pose_out in zip(transit_run, pose_hold_run, strict=True):
            assert transit_out.plant == pose_out.plant
            assert transit_out.controller_trace == pose_out.controller_trace

    def test_control_output_continuous_at_transfer_tick(self) -> None:
        transit_run = self._run_transit_then_task(3, ControlTask.TRANSIT)
        pose_hold_run = self._run_transit_then_task(3, ControlTask.POSE_HOLD)

        transit_trace = transit_run[3].controller_trace
        pose_trace = pose_hold_run[3].controller_trace
        assert transit_trace is not None and pose_trace is not None
        assert transit_trace.saturated_output == pose_trace.saturated_output
        assert transit_trace.raw_request == pose_trace.raw_request

    def test_integral_recursion_continues_across_transfer_boundary(self) -> None:
        outputs = self._run_transit_then_task(3, ControlTask.POSE_HOLD)
        dt = 0.1
        ki = np.array([100.0, 50.0, 200.0])
        aw = np.array([1.0, 1.0, 1.0])

        for before, after in zip(outputs[:-1], outputs[1:], strict=True):
            trace_before = before.controller_trace
            trace_after = after.controller_trace
            assert trace_before is not None and trace_after is not None
            delta = dt * (
                ki * np.array(trace_before.errors, dtype=np.float64)
                + aw * np.array(trace_before.antiwindup_correction, dtype=np.float64)
            )
            expected = np.array(trace_before.i_term, dtype=np.float64) + delta
            np.testing.assert_array_equal(np.array(trace_after.i_term, dtype=np.float64), expected)

    def test_derivative_term_invariant_under_reference_jump(self) -> None:
        from colav_simulator.modular_gnc.controller import MarinePID, MarinePIDConfig

        params = dict(_MARINE_PID_PARAMS)
        params["position_mode"] = True
        controller = MarinePID(MarinePIDConfig.from_params(params))
        dt = 0.1
        measurements = [
            NavigationState(0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
            NavigationState(0.01, -0.01, 0.001, 0.1, 0.0, 0.01),
            NavigationState(0.03, -0.02, 0.003, 0.2, 0.0, 0.01),
            NavigationState(0.06, -0.04, 0.006, 0.3, 0.0, 0.01),
        ]

        def run(reference_values: list[np.ndarray]) -> list:
            controller.reset(seed=0)
            traces = []
            for tick, measurement in enumerate(measurements):
                _, trace = controller.compute_control(
                    measurement=measurement,
                    reference=DirectReference(reference_values[tick], latched_tick=tick),
                    dt_s=dt,
                    tick=tick,
                )
                traces.append(trace)
            return traces

        constant = [np.array([1.0, 1.0, 0.1] + [0.0] * 6) for _ in range(4)]
        jumped = [np.array([1.0, 1.0, 0.1] + [0.0] * 6) for _ in range(2)]
        jumped.append(np.array([4.0, -2.0, 0.5] + [0.0] * 6))
        jumped.append(np.array([4.0, -2.0, 0.5] + [0.0] * 6))

        constant_traces = run(constant)
        jumped_traces = run(jumped)

        assert constant_traces[2].d_term == jumped_traces[2].d_term
        assert constant_traces[2].measurement == jumped_traces[2].measurement

    def test_transfer_command_leaves_stack_state_untouched_before_execution(self) -> None:
        stack = _position_mode_stack()
        for tick in range(3):
            stack.step(_pose_reference(tick, 5.0, -5.0, 0.2, ControlTask.TRANSIT), dt_s=0.1)
        before = stack.snapshot()

        rejected = stack.step(_pose_reference(3, 5.0, -5.0, 0.2, ControlTask.CONTROLLED_STOP), dt_s=0.1)

        assert rejected.failure is not None
        assert stack.snapshot() == before


class TestTaskCapabilityDeclarations:
    """Supported task sets follow module capability declarations (AC1)."""

    def test_pass_through_plant_declares_transit_only(self) -> None:
        from colav_simulator.modular_gnc.passthrough_modules import (
            PASS_THROUGH_ALLOCATOR_TASKS,
            PASS_THROUGH_ACTUATOR_TASKS,
            PASS_THROUGH_CONTROLLER_TASKS,
            PASS_THROUGH_PLANT_TASKS,
        )

        assert PASS_THROUGH_PLANT_TASKS == frozenset({ControlTask.TRANSIT})
        assert PASS_THROUGH_CONTROLLER_TASKS == frozenset({ControlTask.TRANSIT, ControlTask.MANUAL_LOAD})
        assert PASS_THROUGH_ALLOCATOR_TASKS == frozenset(ControlTask)
        assert PASS_THROUGH_ACTUATOR_TASKS == frozenset(ControlTask)

    def test_generic_plants_declare_load_executable_tasks(self) -> None:
        from colav_simulator.modular_gnc.plant import Generic3DOFPlant, GenericRoll4DOFPlant

        expected = frozenset({ControlTask.TRANSIT, ControlTask.POSE_HOLD, ControlTask.MANUAL_LOAD})
        assert Generic3DOFPlant.supported_tasks == expected
        assert GenericRoll4DOFPlant.supported_tasks == expected

    def test_marine_pid_declares_pose_hold_only_in_position_mode(self) -> None:
        from colav_simulator.modular_gnc.controller import MarinePID, MarinePIDConfig

        velocity_mode = MarinePID(MarinePIDConfig.from_params(_MARINE_PID_PARAMS))
        position_params = dict(_MARINE_PID_PARAMS)
        position_params["position_mode"] = True
        position_mode = MarinePID(MarinePIDConfig.from_params(position_params))

        assert velocity_mode.supported_tasks == frozenset({ControlTask.TRANSIT})
        assert position_mode.supported_tasks == frozenset({ControlTask.TRANSIT, ControlTask.POSE_HOLD})

    @pytest.mark.parametrize(
        ("config", "expected"),
        [
            (_legacy_equivalent_config(), {ControlTask.TRANSIT}),
            (_generic_plant_passthrough_config(), {ControlTask.TRANSIT, ControlTask.MANUAL_LOAD}),
            (_generic_plant_marine_pid_config(), {ControlTask.TRANSIT}),
            (_generic_plant_marine_pid_config(position_mode=True), {ControlTask.TRANSIT, ControlTask.POSE_HOLD}),
        ],
    )
    def test_stack_supported_tasks_is_module_capability_intersection(self, config: dict, expected: set) -> None:
        stack = _build_stack(config)

        assert stack.modules.supported_tasks == frozenset(expected)


class TestTaskContractCoercion:
    """DirectReference and TrackedRoute coerce and validate task identity (AC1)."""

    def test_direct_reference_coerces_string_task(self) -> None:
        reference = DirectReference(np.zeros(9), latched_tick=0, task="POSE_HOLD")

        assert reference.task is ControlTask.POSE_HOLD

    def test_direct_reference_rejects_unknown_task(self) -> None:
        with pytest.raises(ValueError, match="CONTROLLED_DRIFT"):
            DirectReference(np.zeros(9), latched_tick=0, task="CONTROLLED_DRIFT")

    def test_tracked_route_coerces_string_task(self) -> None:
        route = TrackedRoute(
            route_id="r1",
            revision=0,
            accepted=True,
            valid_from_tick=0,
            valid_until_tick=5,
            waypoints_ne_m=np.array([[0.0, 1.0], [0.0, 2.0]]),
            speed_mps=np.array([1.0, 1.0]),
            task="TRANSIT",
        )

        assert route.task is ControlTask.TRANSIT
