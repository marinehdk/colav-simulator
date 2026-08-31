from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from colav_simulator.modular_gnc.contracts import DirectReference, NavigationState, PlantState


@dataclass(frozen=True)
class PassThroughSnapshot:
    """Deterministic test-module state."""

    state: PlantState
    phase_counts: tuple[tuple[str, int], ...]


class PassThroughModules:
    """Deterministic contracts-only modules; no physics or environment kernels."""

    phase_order = ("environment", "guidance", "controller", "allocator", "actuator", "plant")

    def __init__(self, fail_phase: str | None = None, fail_tick: int | None = None) -> None:
        self._fail_phase = fail_phase
        self._fail_tick = fail_tick
        self._state = PlantState(np.zeros(6), frozenset({"PLANAR_3DOF"}))
        self._phase_counts = dict.fromkeys(self.phase_order, 0)

    def reset(self, navigation: NavigationState, seed: int) -> None:  # noqa: ARG002
        """Reset deterministic state from navigation truth projection."""
        self._state = PlantState(navigation.as_array(), frozenset({"PLANAR_3DOF"}))
        self._phase_counts = dict.fromkeys(self.phase_order, 0)

    def run_phase(self, phase: str, tick: int, reference: DirectReference | None, dt_s: float) -> None:  # noqa: ARG002
        """Record fixed phase order and apply direct-reference pass-through at plant phase."""
        if phase == self._fail_phase and tick == self._fail_tick:
            raise RuntimeError(f"test module failure in {phase}")
        self._phase_counts[phase] += 1
        if phase == "plant" and reference is not None:
            values = self._state.values.copy()
            values[2] = reference.values[2]
            values[3] = reference.values[3]
            self._state = PlantState(values, self._state.capabilities)

    def navigation(self) -> NavigationState:
        """Project complete pass-through state to navigation view."""
        return NavigationState(*self._state.values)

    def plant_state(self) -> PlantState:
        """Return immutable plant state."""
        return self._state

    def snapshot(self) -> PassThroughSnapshot:
        """Capture complete test-module state."""
        return PassThroughSnapshot(self._state, tuple(sorted(self._phase_counts.items())))

    def restore(self, snapshot: PassThroughSnapshot) -> None:
        """Restore complete test-module state."""
        self._state = snapshot.state
        self._phase_counts = dict(snapshot.phase_counts)
