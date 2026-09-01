"""Deterministic pass-through modules for contracts-only slice one."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from colav_simulator.modular_gnc.contracts import (
    ControlTask,
    DirectReference,
    EnvironmentalLoads,
    EnvironmentObservation,
    EnvironmentTruth,
    NavigationSource,
    NavigationState,
    PlantState,
    TrackedRoute,
    VesselLoad,
)
from colav_simulator.modular_gnc.integrators import rk4_step

if TYPE_CHECKING:
    from colav_simulator.modular_gnc.environment import EnvironmentField
    from colav_simulator.modular_gnc.load_model import EnvironmentalLoadModel
    from colav_simulator.modular_gnc.plant import Generic3DOFPlant, GenericRoll4DOFPlant


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
    ) -> None:
        self._fail_phase = fail_phase
        self._fail_tick = fail_tick
        self._environment_field = environment_field
        self._load_model = load_model
        self._plant = plant
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

    def run_phase(
        self,
        phase: str,
        tick: int,
        reference: DirectReference | None,
        route: TrackedRoute | None,
        dt_s: float,  # noqa: ARG002
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
        if phase == "guidance" and route is not None:
            self._route_consumptions.append((tick, route.route_id, route.revision))
        if phase == "plant":
            if self._plant is not None:
                if reference is not None:
                    if reference.task == ControlTask.MANUAL_LOAD:
                        ctrl_load = VesselLoad(
                            surge_n=float(reference.values[0]),
                            sway_n=float(reference.values[1]),
                            yaw_nm=float(reference.values[2]),
                        )
                    elif abs(reference.values[6]) > 0.0 or abs(reference.values[7]) > 0.0 or abs(reference.values[8]) > 0.0:
                        ctrl_load = VesselLoad(
                            surge_n=float(reference.values[6]),
                            sway_n=float(reference.values[7]),
                            yaw_nm=float(reference.values[8]),
                        )
                    else:
                        ctrl_load = VesselLoad(
                            surge_n=float(reference.values[0]),
                            sway_n=float(reference.values[1]),
                            yaw_nm=float(reference.values[2]),
                        )
                else:
                    ctrl_load = VesselLoad.zero()

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
            elif reference is not None:
                values = self._state.values.copy()
                values[2] = reference.values[2]
                values[3] = reference.values[3]
                self._state = PlantState(values, self._state.capabilities)

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
        )

    def restore(self, snapshot: PassThroughSnapshot) -> None:
        """Restore complete pass-through module state."""
        self._state = snapshot.state
        self._navigation_source = snapshot.navigation_source
        self._phase_counts = dict(snapshot.phase_counts)
        self._route_consumptions = list(snapshot.route_consumptions)
        self._held_truth = snapshot.held_truth
        self._held_observation = snapshot.held_observation
        self._held_loads = snapshot.held_loads

    @property
    def route_consumptions(self) -> tuple[tuple[int, str, int], ...]:
        """Return route consumptions observed at guidance phases."""
        return tuple(self._route_consumptions)
