from __future__ import annotations

from typing import Any

from colav_simulator.modular_gnc.command_latch import CommandLatch
from colav_simulator.modular_gnc.configuration import ShipModulesConfig
from colav_simulator.modular_gnc.contracts import (
    CommandInput,
    FacadeFailure,
    FailureCode,
    NavigationState,
    StackOutput,
    StackSnapshot,
)
from colav_simulator.modular_gnc.test_modules import PassThroughModules


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
    def from_config(cls, config: ShipModulesConfig) -> ModularShipStack:
        """Build registered contracts-only implementation."""
        return cls(config, PassThroughModules())

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
            raise RuntimeError("stack must be reset before step")
        if dt_s <= 0.0:
            raise ValueError("dt_s must be positive")
        before = self.snapshot()
        latched = self._latch.consume(command)
        if latched.failure is not None:
            self.restore(before)
            return StackOutput(
                tick=self._tick,
                navigation=self._modules.navigation(),
                plant=self._modules.plant_state(),
                applied_reference=None,
                failure=latched.failure,
            )
        try:
            for phase in self._modules.phase_order:
                self._modules.run_phase(phase, self._tick, latched.direct_reference, dt_s)
        except Exception as exc:  # noqa: BLE001
            self.restore(before)
            failure = FacadeFailure(
                code=FailureCode.MODULE_FAILURE,
                message=str(exc),
                phase=phase,
                tick=self._tick,
                details={"exception_type": type(exc).__name__},
            )
            return StackOutput(
                tick=self._tick,
                navigation=self._modules.navigation(),
                plant=self._modules.plant_state(),
                applied_reference=None,
                failure=failure,
            )
        output = StackOutput(
            tick=self._tick,
            navigation=self._modules.navigation(),
            plant=self._modules.plant_state(),
            applied_reference=latched.direct_reference,
        )
        self._tick += 1
        return output

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
