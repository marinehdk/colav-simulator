from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

import numpy as np

from colav_simulator.core import stochasticity
from colav_simulator.core.ship import Config, IShip, Ship
from colav_simulator.modular_gnc.contracts import (
    CommandInput,
    DirectReference,
    FacadeFailure,
    FailureCode,
    NavigationState,
)
from colav_simulator.modular_gnc.stack import ModularShipStack


class ModularShipAbort(RuntimeError):
    """Abort current episode after structured modular facade failure."""


@dataclass(frozen=True)
class FailurePolicy:
    """Map every facade code to explicit simulator behavior."""

    overrides: dict[FailureCode, str] | None = None

    def action_for(self, code: FailureCode) -> str:
        """Return configured action; default all mapped codes to abort."""
        action = (self.overrides or {}).get(code, "abort_episode")
        if action not in {"abort_episode", "skip_ship", "degraded_continue"}:
            return "abort_episode"
        return action

    def apply(self, failure: FacadeFailure, override: str | None = None) -> str:
        """Validate action and raise for default or unmapped behavior."""
        action = override if override is not None else self.action_for(failure.code)
        if action not in {"abort_episode", "skip_ship", "degraded_continue"}:
            raise ModularShipAbort(f"unmapped modular failure action {action}: {failure.code.value}")
        if action == "abort_episode":
            raise ModularShipAbort(f"{failure.code.value} at {failure.phase} tick {failure.tick}: {failure.message}")
        return action


class ModularShipAdapter(IShip):
    """Independent IShip bridge around ModularShipStack and legacy-side services."""

    def __init__(
        self,
        legacy_services: Ship,
        stack: ModularShipStack,
        failure_policy: FailurePolicy | None = None,
    ) -> None:
        self._legacy = legacy_services
        self._stack = stack
        self._failure_policy = failure_policy or FailurePolicy()
        self._next_tick = 0
        self._last_failure: FacadeFailure | None = None

    @classmethod
    def from_legacy_config(cls, config: Config, stack: ModularShipStack) -> ModularShipAdapter:
        """Build legacy planner/tracker/telemetry services without subclassing Ship."""
        legacy_config = copy.copy(config)
        legacy_config.ship_modules = None
        legacy_services = Ship(mmsi=config.mmsi, identifier=config.id, config=legacy_config)
        if legacy_services._references.size == 0:
            legacy_services._references = np.zeros((9, 1), dtype=np.float64)
        return cls(legacy_services, stack)

    def _navigation(self) -> NavigationState:
        state = self._legacy.state
        return NavigationState(*np.asarray(state, dtype=np.float64))

    def _sync_stack_state(self, navigation: NavigationState) -> None:
        self._legacy._state = navigation.as_array()

    def forward(
        self, dt: float, w: stochasticity.DisturbanceData | None = None  # noqa: ARG002
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Advance modular stack, except historical trajectory playback bypasses it."""
        if self._legacy._trajectory.size > 0:
            return self._legacy.forward(dt, w)
        if dt <= 0.0:
            return self.state, np.empty(3), np.empty(9)
        references = self._legacy._references[:, 0]
        command = CommandInput.direct(self._next_tick, DirectReference(references, self._next_tick))
        output = self._stack.step(command, dt)
        if output.failure is not None:
            self._last_failure = output.failure
            action = self._failure_policy.apply(output.failure)
            if action == "skip_ship":
                return self.state, np.empty(3), references
            if action == "degraded_continue":
                return self.state, np.zeros(3), references
        self._sync_stack_state(output.navigation)
        self._next_tick += 1
        self._legacy._input = np.zeros(3, dtype=np.float64)
        return self.state, self._legacy._input, references

    def track_obstacles(self, t: float, dt: float, true_do_states: list) -> tuple[list, list]:
        """Delegate sensors and tracker unchanged."""
        return self._legacy.track_obstacles(t, dt, true_do_states)

    def plan(self, t: float, dt: float, do_list: list, enc: Any = None, w: Any = None) -> np.ndarray:
        """Delegate existing guidance/COLAV authority outside facade."""
        return self._legacy.plan(t, dt, do_list, enc, w)

    def reset(self, seed: int | None) -> None:
        """Reset legacy-side services and modular facade."""
        self._legacy.reset(seed)
        self._stack.reset(self._navigation(), 0 if seed is None else seed)
        self._next_tick = 0
        self._last_failure = None

    def set_id(self, identifier: int) -> None:
        self._legacy.set_id(identifier)

    def set_initial_state(self, csog_state: np.ndarray, t_start: float | None = None) -> None:
        self._legacy.set_initial_state(csog_state, t_start)

    def set_goal_state(self, csog_state: np.ndarray) -> None:
        self._legacy.set_goal_state(csog_state)

    def set_nominal_plan(self, waypoints: np.ndarray, speed_plan: np.ndarray) -> None:
        self._legacy.set_nominal_plan(waypoints, speed_plan)

    def set_remote_actor_predicted_trajectory(self, predicted_trajectory: np.ndarray) -> None:
        self._legacy.set_remote_actor_predicted_trajectory(predicted_trajectory)

    def set_references(self, references: np.ndarray) -> None:
        """Convert legacy 9x1 references at adapter boundary."""
        array = np.asarray(references, dtype=np.float64)
        if array.size != 9:
            raise ValueError("references must contain exactly 9 values")
        self._legacy.set_references(array)

    def set_tracker(self, tracker: Any) -> None:
        self._legacy.set_tracker(tracker)

    def set_colav_system(self, colav: Any) -> None:
        self._legacy.set_colav_system(colav)

    def set_controller(self, controller: Any) -> None:
        self._legacy.set_controller(controller)

    def get_colav_data(self) -> dict:
        return self._legacy.get_colav_data()

    def get_colav_decision_space(self) -> dict | None:
        return self._legacy.get_colav_decision_space()

    def set_colav_data(self, colav_data: dict) -> None:
        self._legacy.set_colav_data(colav_data)

    def get_sim_data(self, t: float, timestamp_0: int) -> dict:
        """Return raw legacy telemetry dictionary without schema translation."""
        return self._legacy.get_sim_data(t, timestamp_0)

    def get_ship_info(self) -> dict:
        return self._legacy.get_ship_info()

    def get_do_track_information(self) -> tuple[list, list]:
        return self._legacy.get_do_track_information()

    def plot_colav_results(self, ax_map: Any, enc: Any, plt_handles: dict, remote_actor: bool = False, **kwargs) -> dict:
        return self._legacy.plot_colav_results(ax_map, enc, plt_handles, remote_actor, **kwargs)

    def transfer_vessel_ais_data(
        self,
        vessel: Any,
        use_ais_trajectory: bool = True,
        t_start: float | None = None,
        t_end: float | None = None,
    ) -> None:
        self._legacy.transfer_vessel_ais_data(vessel, use_ais_trajectory, t_start, t_end)

    def __getattr__(self, name: str) -> Any:
        """Expose de-facto read properties consumed across simulator ecosystem."""
        return getattr(self._legacy, name)

    @property
    def state(self) -> np.ndarray:
        return self._legacy.state

    @property
    def csog_state(self) -> np.ndarray:
        return self._legacy.csog_state

    @property
    def trajectory(self) -> np.ndarray:
        return self._legacy.trajectory

    @property
    def stack(self) -> ModularShipStack:
        """Return facade for snapshot/replay integration."""
        return self._stack
