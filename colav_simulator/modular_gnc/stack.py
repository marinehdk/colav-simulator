"""Deterministic contracts-only ModularShipStack facade."""

from __future__ import annotations

import math
from typing import Any

from colav_simulator.modular_gnc.command_latch import CommandLatch
from colav_simulator.modular_gnc.configuration import ShipModulesConfig
from colav_simulator.modular_gnc.contracts import (
    CommandInput,
    FacadeFailure,
    FailureCode,
    NavigationState,
    PlantState,
    StackOutput,
    StackSnapshot,
)
from colav_simulator.modular_gnc.environment import AnalyticEnvironmentField
from colav_simulator.modular_gnc.passthrough_modules import PassThroughModules


class ModularShipStack:
    """Contracts-only deterministic facade; atomicity is facade-local."""

    snapshot_schema_version = "modular-ship-stack.snapshot.v1"

    def __init__(self, config: ShipModulesConfig, modules: PassThroughModules) -> None:
        self._config = config
        self._modules = modules
        self._latch = CommandLatch(config.scheduler["controller_period_ticks"])
        self._tick = 0
        self._seed = 0
        self._initialized = False

    @classmethod
    def from_config(
        cls,
        config: ShipModulesConfig,
        episode_seed: int = 0,
        dt_s: float = 0.1,
    ) -> ModularShipStack:
        """Build registered modular implementation."""
        env_field = None
        if "environment" in config.modules:
            env_sel = config.modules["environment"]
            if env_sel.identity == "analytic_environment_field":
                env_field = AnalyticEnvironmentField.from_params(
                    env_sel.parameters,
                    dt_s=dt_s,
                    episode_seed=episode_seed,
                )
        modules = PassThroughModules(environment_field=env_field)
        return cls(config, modules)

    def reset(self, navigation: NavigationState, seed: int) -> None:
        """Idempotently reset all facade-owned state."""
        self._tick = 0
        self._seed = int(seed)
        self._latch = CommandLatch(self._config.scheduler["controller_period_ticks"])
        self._modules.reset(navigation, self._seed)
        self._initialized = True

    def snapshot(self) -> StackSnapshot:
        """Capture complete facade-owned state for deterministic restoration."""
        if not self._initialized:
            raise RuntimeError("stack must be reset before snapshot")
        return StackSnapshot(
            schema_version=self.snapshot_schema_version,
            config_hash=self._config.config_hash,
            tick=self._tick,
            seed=self._seed,
            module_snapshots=(self._modules.snapshot(), self._latch.snapshot()),
            held_command=None,
        )

    def restore(self, snapshot: StackSnapshot) -> None:
        """Restore snapshot bound to same configuration hash."""
        if snapshot.config_hash != self._config.config_hash:
            raise ValueError("snapshot config_hash mismatch")
        module_snapshot, latch_snapshot = snapshot.module_snapshots
        self._modules.restore(module_snapshot)
        self._latch.restore(latch_snapshot)
        self._tick = snapshot.tick
        self._seed = snapshot.seed
        self._initialized = True

    def step(self, command: CommandInput, dt_s: float) -> StackOutput:
        """Advance one integer simulation tick with fixed phase order and local atomic commit."""
        if not self._initialized:
            return self._uninitialized_failure("stack must be reset before step")
        before = self.snapshot()
        if not math.isfinite(dt_s):
            return self._failure_output(
                before,
                FacadeFailure(FailureCode.NONFINITE_INPUT, "dt_s must be finite", "facade", self._tick),
            )
        if dt_s <= 0.0:
            return self._failure_output(
                before,
                FacadeFailure(FailureCode.INVALID_INPUT, "dt_s must be positive", "facade", self._tick),
            )
        if command.tick != self._tick:
            code = FailureCode.STALE_INPUT if command.tick < self._tick else FailureCode.OUT_OF_ORDER_INPUT
            return self._failure_output(
                before,
                FacadeFailure(
                    code,
                    "command tick must equal stack tick",
                    "facade",
                    self._tick,
                    details={"command_tick": command.tick, "stack_tick": self._tick},
                ),
            )
        latched = self._latch.consume(command)
        if latched.failure is not None:
            return self._failure_output(before, latched.failure)
        try:
            for phase in self._modules.phase_order:
                if phase == "guidance" and latched.tracked_route is None:
                    continue
                if not self._phase_due(phase):
                    continue
                self._modules.run_phase(
                    phase,
                    self._tick,
                    latched.direct_reference,
                    latched.tracked_route,
                    dt_s,
                )
        except Exception as exc:  # noqa: BLE001
            failure = FacadeFailure(
                code=FailureCode.MODULE_FAILURE,
                message=str(exc),
                phase=phase,
                tick=self._tick,
                details={"exception_type": type(exc).__name__},
            )
            return self._failure_output(before, failure)
        output = StackOutput(
            tick=self._tick,
            navigation=self._modules.navigation(),
            plant=self._modules.plant_state(),
            applied_reference=latched.direct_reference,
            environment_observation=getattr(self._modules, "environment_observation", lambda: None)(),
        )
        self._tick += 1
        return output

    def _phase_due(self, phase: str) -> bool:
        period_key = {
            "guidance": "guidance_period_ticks",
            "controller": "controller_period_ticks",
            "allocator": "controller_period_ticks",
            "actuator": "controller_period_ticks",
            "environment": "plant_period_ticks",
            "plant": "plant_period_ticks",
        }[phase]
        return self._tick % self._config.scheduler[period_key] == 0

    def _failure_output(self, before: StackSnapshot, failure: FacadeFailure) -> StackOutput:
        self.restore(before)
        return StackOutput(
            tick=self._tick,
            navigation=self._modules.navigation(),
            plant=self._modules.plant_state(),
            applied_reference=None,
            failure=failure,
        )

    def _uninitialized_failure(self, message: str) -> StackOutput:
        zero = NavigationState(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        return StackOutput(
            tick=self._tick,
            navigation=zero,
            plant=PlantState(zero.as_array(), frozenset({"PLANAR_3DOF"})),
            applied_reference=None,
            failure=FacadeFailure(FailureCode.INVALID_INPUT, message, "facade", self._tick),
        )

    @property
    def tick(self) -> int:
        """Return next integer simulation tick."""
        return self._tick

    @property
    def config(self) -> ShipModulesConfig:
        """Return frozen normalized configuration."""
        return self._config

    @property
    def modules(self) -> Any:
        """Return stable private module-seam object for characterization tests."""
        return self._modules
