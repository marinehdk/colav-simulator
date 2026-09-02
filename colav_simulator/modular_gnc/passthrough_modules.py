"""Deterministic pass-through modules for contracts-only slice one."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np

from colav_simulator.modular_gnc.actuator_dynamics import ResolvedActuatorDynamics
from colav_simulator.modular_gnc.allocator import AllocatorSolution, DataDrivenAllocator
from colav_simulator.modular_gnc.contracts import (
    AchievedGeneralizedLoad,
    AchievedLoadStatus,
    ActuatorDynamicsTrace,
    ControlTask,
    DirectReference,
    EnvironmentalLoads,
    EnvironmentObservation,
    EnvironmentTruth,
    MarinePIDTrace,
    NavigationSource,
    NavigationState,
    PlantState,
    TrackedRoute,
    VesselLoad,
)
from colav_simulator.modular_gnc.guidance_ilos import ILOSGuidanceTrace, IntegralLineOfSightGuidance
from colav_simulator.modular_gnc.integrators import rk4_step

if TYPE_CHECKING:
    from colav_simulator.modular_gnc.controller import MarinePID
    from colav_simulator.modular_gnc.environment import EnvironmentField
    from colav_simulator.modular_gnc.load_model import EnvironmentalLoadModel
    from colav_simulator.modular_gnc.plant import Generic3DOFPlant, GenericRoll4DOFPlant

# Explicit per-role control-task capability declarations (Issue #56, AC1).
# The kinematic pass-through plant executes transit-style course/speed references only;
# it has no force input channel, so MANUAL_LOAD is not executable through it.
PASS_THROUGH_PLANT_TASKS: frozenset[ControlTask] = frozenset({ControlTask.TRANSIT})
# The pass-through controller is an identity map: it forwards transit references and
# executes manual generalized loads verbatim (existing tested MANUAL_LOAD semantics).
PASS_THROUGH_CONTROLLER_TASKS: frozenset[ControlTask] = frozenset({ControlTask.TRANSIT, ControlTask.MANUAL_LOAD})
# Ideal pass-through allocator/actuator apply every resolved load without reinterpretation.
PASS_THROUGH_ALLOCATOR_TASKS: frozenset[ControlTask] = frozenset(ControlTask)
PASS_THROUGH_ACTUATOR_TASKS: frozenset[ControlTask] = frozenset(ControlTask)


@dataclass(frozen=True)
class PassThroughSnapshot:
    """Deterministic contracts-only pass-through state."""

    state: PlantState
    phase_counts: tuple[tuple[str, int], ...]
    route_consumptions: tuple[tuple[int, str, int], ...]
    navigation_source: NavigationSource = NavigationSource.TRUTH_PROJECTION
    held_truth: EnvironmentTruth | None = None
    held_observation: EnvironmentObservation | None = None
    held_loads: EnvironmentalLoads | None = None
    held_control_load: VesselLoad | None = None
    held_controller_trace: MarinePIDTrace | None = None
    held_achieved_load: AchievedGeneralizedLoad | None = None
    controller_snapshot: Any = None
    guidance_snapshot: Any = None
    held_guidance_reference: DirectReference | None = None
    held_guidance_trace: ILOSGuidanceTrace | None = None
    allocator_snapshot: Any = None
    held_allocator_solution: AllocatorSolution | None = None
    actuator_snapshot: Any = None
    held_actuator_trace: ActuatorDynamicsTrace | None = None
    held_actuator_load: VesselLoad | None = None


class PassThroughModules:
    """Deterministic contracts-only modules; no physics or environment kernels."""

    phase_order = ("environment", "guidance", "controller", "allocator", "actuator", "plant")

    def __init__(
        self,
        fail_phase: str | None = None,
        fail_tick: int | None = None,
        environment_field: EnvironmentField | None = None,
        load_model: EnvironmentalLoadModel | None = None,
        plant: Generic3DOFPlant | GenericRoll4DOFPlant | None = None,
        controller: MarinePID | None = None,
        guidance: IntegralLineOfSightGuidance | None = None,
        allocator: DataDrivenAllocator | None = None,
        actuator: ResolvedActuatorDynamics | None = None,
    ) -> None:
        self._fail_phase = fail_phase
        self._fail_tick = fail_tick
        self._environment_field = environment_field
        self._load_model = load_model
        self._plant = plant
        self._controller = controller
        self._guidance = guidance
        self._allocator = allocator
        self._actuator = actuator
        capabilities = frozenset({"PLANAR_3DOF"}) if plant is None else plant.capabilities
        input_semantics = (
            PlantState.__dataclass_fields__["input_semantics"].default if plant is None else plant.input_semantics
        )
        init_dim = 8 if "ROLL_4DOF" in capabilities else 6
        self._state = PlantState(np.zeros(init_dim), capabilities, input_semantics=input_semantics)
        self._navigation_source = NavigationSource.TRUTH_PROJECTION
        self._phase_counts = dict.fromkeys(self.phase_order, 0)
        self._route_consumptions: list[tuple[int, str, int]] = []
        self._held_truth: EnvironmentTruth | None = None
        self._held_observation: EnvironmentObservation | None = None
        self._held_loads: EnvironmentalLoads | None = None
        self._held_control_load: VesselLoad | None = None
        self._held_controller_trace: MarinePIDTrace | None = None
        self._held_achieved_load: AchievedGeneralizedLoad | None = None
        self._held_guidance_reference: DirectReference | None = None
        self._held_guidance_trace: ILOSGuidanceTrace | None = None
        self._held_allocator_solution: AllocatorSolution | None = None
        self._held_actuator_trace: ActuatorDynamicsTrace | None = None
        self._held_actuator_load: VesselLoad | None = None

    def reset(self, navigation: NavigationState, seed: int) -> None:  # noqa: ARG002
        """Reset deterministic state from navigation truth projection."""
        capabilities = frozenset({"PLANAR_3DOF"}) if self._plant is None else self._plant.capabilities
        input_semantics = (
            PlantState.__dataclass_fields__["input_semantics"].default
            if self._plant is None
            else self._plant.input_semantics
        )
        if "ROLL_4DOF" in capabilities:
            values = np.array(
                [
                    navigation.north_m,
                    navigation.east_m,
                    navigation.heading_rad,
                    0.0,
                    navigation.surge_mps,
                    navigation.sway_mps,
                    0.0,
                    navigation.yaw_rate_radps,
                ],
                dtype=np.float64,
            )
        else:
            values = navigation.as_array()
        self._state = PlantState(values, capabilities, input_semantics=input_semantics)
        self._navigation_source = navigation.source
        self._phase_counts = dict.fromkeys(self.phase_order, 0)
        self._route_consumptions: list[tuple[int, str, int]] = []
        if self._controller is not None:
            self._controller.reset(seed)
        if self._guidance is not None:
            self._guidance.reset()
        if self._allocator is not None:
            self._allocator.reset()
        if self._actuator is not None:
            self._actuator.reset()
        self._held_control_load = None
        self._held_controller_trace = None
        self._held_achieved_load = None
        self._held_guidance_reference = None
        self._held_guidance_trace = None
        self._held_allocator_solution = None
        self._held_actuator_trace = None
        self._held_actuator_load = None

        if self._environment_field is not None:
            pos = (navigation.north_m, navigation.east_m)
            self._held_truth = self._environment_field.sample_at(0, 0.0, pos)
            self._held_observation = self._environment_field.sample_observation(0, 0.0, pos)
        else:
            self._held_truth = None
            self._held_observation = None

        if self._load_model is not None and self._held_truth is not None:
            self._held_loads = self._load_model.compute_loads(self._held_truth, navigation)
        else:
            self._held_loads = None

    def _resolve_requested_control_load(self, reference: DirectReference | None) -> VesselLoad:
        """Resolve the requested control load from controller output or reference fallback."""
        if self._held_control_load is not None:
            return self._held_control_load
        if reference is None:
            return VesselLoad.zero()
        if reference.task == ControlTask.MANUAL_LOAD:
            return VesselLoad(
                surge_n=float(reference.values[0]),
                sway_n=float(reference.values[1]),
                yaw_nm=float(reference.values[2]),
            )
        if abs(reference.values[6]) > 0.0 or abs(reference.values[7]) > 0.0 or abs(reference.values[8]) > 0.0:
            return VesselLoad(
                surge_n=float(reference.values[6]),
                sway_n=float(reference.values[7]),
                yaw_nm=float(reference.values[8]),
            )
        return VesselLoad(
            surge_n=float(reference.values[0]),
            sway_n=float(reference.values[1]),
            yaw_nm=float(reference.values[2]),
        )

    def _resolve_plant_control_load(self, reference: DirectReference | None) -> VesselLoad:
        """Resolve the control load applied by the plant (actuator output, then allocator achieved)."""
        if self._held_actuator_load is not None:
            return self._held_actuator_load
        if self._held_allocator_solution is not None:
            return self._held_allocator_solution.achieved
        return self._resolve_requested_control_load(reference)

    def run_phase(
        self,
        phase: str,
        tick: int,
        reference: DirectReference | None,
        route: TrackedRoute | None,
        dt_s: float,
    ) -> None:
        """Record fixed phase order and consume due direct/route authority."""
        if phase == self._fail_phase and tick == self._fail_tick:
            raise RuntimeError(f"pass-through module failure in {phase}")
        self._phase_counts[phase] += 1
        if phase == "environment" and self._environment_field is not None:
            pos = (self._state.values[0], self._state.values[1])
            self._held_truth = self._environment_field.sample_at(tick, 0.0, pos)
            self._held_observation = self._environment_field.sample_observation(tick, 0.0, pos)
            if self._load_model is not None and self._held_truth is not None:
                self._held_loads = self._load_model.compute_loads(self._held_truth, self.navigation())
        if phase == "guidance":
            if route is not None:
                self._route_consumptions.append((tick, route.route_id, route.revision))
                if self._guidance is not None:
                    self._held_guidance_reference = self._guidance.compute_reference(
                        tick, route, self.navigation(), dt_s
                    )
                    self._held_guidance_trace = self._guidance.latest_trace
        effective_reference = reference if reference is not None else self._held_guidance_reference
        if phase == "controller" and self._controller is not None and effective_reference is not None:
            vessel_load, trace = self._controller.compute_control(
                measurement=self.navigation(),
                reference=effective_reference,
                dt_s=dt_s,
                tick=tick,
                time_s=tick * dt_s,
                achieved_load=self._held_achieved_load,
            )
            self._held_control_load = vessel_load
            self._held_controller_trace = trace
            self._held_achieved_load = AchievedGeneralizedLoad.from_vessel_load(
                vessel_load,
                status=AchievedLoadStatus.AVAILABLE,
                saturated=any(trace.saturation_flags),
                source="IDEAL_PASSTHROUGH",
                tick=tick,
                time_s=tick * dt_s,
            )
        if phase == "allocator" and self._allocator is not None:
            requested = self._resolve_requested_control_load(effective_reference)
            solution = self._allocator.allocate(requested, tick=tick, time_s=tick * dt_s)
            self._held_allocator_solution = solution
            self._held_achieved_load = solution.to_achieved_generalized_load()
        if phase == "actuator" and self._actuator is not None:
            self._run_actuator_phase(tick, dt_s)
        if phase == "plant":
            if self._plant is not None:
                ctrl_load = self._resolve_plant_control_load(effective_reference)
                new_values = rk4_step(
                    plant=self._plant,
                    tick=tick,
                    dt_s=dt_s,
                    state=self._state.values,
                    control_load=ctrl_load,
                    environment_field=self._environment_field,
                    load_model=self._load_model,
                )
                self._state = PlantState(new_values, self._plant.capabilities, input_semantics=self._plant.input_semantics)
            elif effective_reference is not None:
                values = self._state.values.copy()
                values[2] = effective_reference.values[2]
                values[3] = effective_reference.values[3]
                self._state = PlantState(values, self._state.capabilities)

    def _run_actuator_phase(self, tick: int, dt_s: float) -> None:
        """Apply the resolved fidelity profile: one discrete-phase owner of rate and delay dynamics.

        The allocator's clipped commands and current health are the single source of
        limits/saturation/effectiveness/failures (Issue #59 AC4, TS-14, TS-22).
        """
        if self._held_allocator_solution is None:
            raise RuntimeError(
                "resolved actuator dynamics requires an allocator solution earlier in the same tick"
            )
        trace = self._actuator.apply(
            self._held_allocator_solution.actuator_commands_n,
            self._held_allocator_solution.actuator_health,
            tick=tick,
            time_s=tick * dt_s,
            dt_s=dt_s,
        )
        self._held_actuator_trace = trace
        self._held_actuator_load = trace.achieved_vessel_load()
        self._held_achieved_load = trace.to_achieved_generalized_load()

    def navigation(self) -> NavigationState:
        """Project complete pass-through state to navigation view."""
        return self._state.to_navigation_state(source=self._navigation_source)

    def plant_state(self) -> PlantState:
        """Return immutable plant state."""
        return self._state

    def environment_truth(self) -> EnvironmentTruth | None:
        """Return currently held environment truth sample."""
        return self._held_truth

    def environment_observation(self) -> EnvironmentObservation | None:
        """Return currently held environment observation sample."""
        return self._held_observation

    def environmental_loads(self) -> EnvironmentalLoads | None:
        """Return currently held environmental loads."""
        return self._held_loads

    def controller_trace(self) -> MarinePIDTrace | None:
        """Return currently held controller trace."""
        return self._held_controller_trace

    def guidance_trace(self) -> ILOSGuidanceTrace | None:
        """Return currently held ILOS guidance trace."""
        return self._held_guidance_trace

    def achieved_load(self) -> AchievedGeneralizedLoad | None:
        """Return currently held achieved load."""
        return self._held_achieved_load

    def allocator_solution(self) -> AllocatorSolution | None:
        """Return currently held allocator solution."""
        return self._held_allocator_solution

    def actuator_trace(self) -> ActuatorDynamicsTrace | None:
        """Return currently held resolved actuator dynamics trace (None under ideal fidelity)."""
        return self._held_actuator_trace

    def actuator_load(self) -> VesselLoad | None:
        """Return currently held post-actuator-dynamics control load."""
        return self._held_actuator_load

    def control_load(self) -> VesselLoad | None:
        """Return currently held control load."""
        return self._held_control_load

    def snapshot(self) -> PassThroughSnapshot:
        """Capture complete pass-through module state."""
        return PassThroughSnapshot(
            self._state,
            tuple(sorted(self._phase_counts.items())),
            tuple(self._route_consumptions),
            self._navigation_source,
            self._held_truth,
            self._held_observation,
            self._held_loads,
            self._held_control_load,
            self._held_controller_trace,
            self._held_achieved_load,
            self._controller.snapshot() if self._controller is not None else None,
            self._guidance.snapshot() if self._guidance is not None else None,
            self._held_guidance_reference,
            self._held_guidance_trace,
            self._allocator.snapshot() if self._allocator is not None else None,
            self._held_allocator_solution,
            self._actuator.snapshot() if self._actuator is not None else None,
            self._held_actuator_trace,
            self._held_actuator_load,
        )

    def restore(self, snapshot: PassThroughSnapshot) -> None:
        """Restore complete pass-through module state."""
        self._state = snapshot.state
        self._phase_counts = dict(snapshot.phase_counts)
        self._route_consumptions = list(snapshot.route_consumptions)
        self._navigation_source = snapshot.navigation_source
        self._held_truth = snapshot.held_truth
        self._held_observation = snapshot.held_observation
        self._held_loads = snapshot.held_loads
        self._held_control_load = snapshot.held_control_load
        self._held_controller_trace = snapshot.held_controller_trace
        self._held_achieved_load = snapshot.held_achieved_load
        if self._controller is not None and snapshot.controller_snapshot is not None:
            self._controller.restore(snapshot.controller_snapshot)
        if self._guidance is not None and snapshot.guidance_snapshot is not None:
            self._guidance.restore(snapshot.guidance_snapshot)
        if self._allocator is not None and snapshot.allocator_snapshot is not None:
            self._allocator.restore(snapshot.allocator_snapshot)
        if self._actuator is not None and snapshot.actuator_snapshot is not None:
            self._actuator.restore(snapshot.actuator_snapshot)
        self._held_guidance_reference = snapshot.held_guidance_reference
        self._held_guidance_trace = snapshot.held_guidance_trace
        self._held_allocator_solution = snapshot.held_allocator_solution
        self._held_actuator_trace = snapshot.held_actuator_trace
        self._held_actuator_load = snapshot.held_actuator_load
        self._navigation_source = snapshot.navigation_source
        self._phase_counts = dict(snapshot.phase_counts)
        self._route_consumptions = list(snapshot.route_consumptions)
        self._held_truth = snapshot.held_truth
        self._held_observation = snapshot.held_observation
        self._held_loads = snapshot.held_loads

    @property
    def supported_tasks(self) -> frozenset[ControlTask]:
        """Return intersection of guidance/controller/plant/allocator/actuator task capabilities (Issue #56, AC1)."""
        tasks = PASS_THROUGH_ACTUATOR_TASKS
        tasks &= self._actuator.supported_tasks if self._actuator is not None else frozenset(ControlTask)
        tasks &= self._allocator.supported_tasks if self._allocator is not None else PASS_THROUGH_ALLOCATOR_TASKS
        tasks &= self._plant.supported_tasks if self._plant is not None else PASS_THROUGH_PLANT_TASKS
        tasks &= self._controller.supported_tasks if self._controller is not None else PASS_THROUGH_CONTROLLER_TASKS
        if self._guidance is not None:
            tasks &= self._guidance.supported_tasks
        return frozenset(tasks)

    @property
    def route_consumptions(self) -> tuple[tuple[int, str, int], ...]:
        """Return route consumptions observed at guidance phases."""
        return tuple(self._route_consumptions)
