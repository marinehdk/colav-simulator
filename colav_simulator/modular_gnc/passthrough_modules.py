"""Deterministic pass-through modules for contracts-only slice one."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from colav_simulator.modular_gnc.contracts import (
    DirectReference,
    NavigationSource,
    NavigationState,
    PlantState,
    TrackedRoute,
)


@dataclass(frozen=True)
class PassThroughSnapshot:
    """Deterministic contracts-only pass-through state."""

    state: PlantState
    phase_counts: tuple[tuple[str, int], ...]
    route_consumptions: tuple[tuple[int, str, int], ...]
    navigation_source: NavigationSource = NavigationSource.TRUTH_PROJECTION


class PassThroughModules:
    """Deterministic contracts-only modules; no physics or environment kernels."""

    phase_order = ("environment", "guidance", "controller", "allocator", "actuator", "plant")

    def __init__(self, fail_phase: str | None = None, fail_tick: int | None = None) -> None:
        self._fail_phase = fail_phase
        self._fail_tick = fail_tick
        self._state = PlantState(np.zeros(6), frozenset({"PLANAR_3DOF"}))
        self._navigation_source = NavigationSource.TRUTH_PROJECTION
        self._phase_counts = dict.fromkeys(self.phase_order, 0)
        self._route_consumptions: list[tuple[int, str, int]] = []

    def reset(self, navigation: NavigationState, seed: int) -> None:  # noqa: ARG002
        """Reset deterministic state from navigation truth projection."""
        self._state = PlantState(navigation.as_array(), frozenset({"PLANAR_3DOF"}))
        self._navigation_source = navigation.source
        self._phase_counts = dict.fromkeys(self.phase_order, 0)
        self._route_consumptions: list[tuple[int, str, int]] = []

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
        if phase == "guidance" and route is not None:
            self._route_consumptions.append((tick, route.route_id, route.revision))
        if phase == "plant" and reference is not None:
            values = self._state.values.copy()
            values[2] = reference.values[2]
            values[3] = reference.values[3]
            self._state = PlantState(values, self._state.capabilities)

    def navigation(self) -> NavigationState:
        """Project complete pass-through state to navigation view."""
        return NavigationState(*self._state.values, source=self._navigation_source)

    def plant_state(self) -> PlantState:
        """Return immutable plant state."""
        return self._state

    def snapshot(self) -> PassThroughSnapshot:
        """Capture complete pass-through module state."""
        return PassThroughSnapshot(
            self._state,
            tuple(sorted(self._phase_counts.items())),
            tuple(self._route_consumptions),
            self._navigation_source,
        )

    def restore(self, snapshot: PassThroughSnapshot) -> None:
        """Restore complete pass-through module state."""
        self._state = snapshot.state
        self._navigation_source = snapshot.navigation_source
        self._phase_counts = dict(snapshot.phase_counts)
        self._route_consumptions = list(snapshot.route_consumptions)

    @property
    def route_consumptions(self) -> tuple[tuple[int, str, int], ...]:
        """Return route consumptions observed at guidance phases."""
        return tuple(self._route_consumptions)
