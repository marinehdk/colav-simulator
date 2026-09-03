"""Deterministic contracts-only ModularShipStack facade."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from colav_simulator.modular_gnc.command_latch import CommandLatch
from colav_simulator.modular_gnc.configuration import (
    ShipModulesConfig,
    UnsupportedModuleCombinationError,
)
from colav_simulator.modular_gnc.contracts import (
    CommandInput,
    ControlTask,
    FacadeFailure,
    FailureCode,
    NavigationState,
    OutOfDomainError,
    PlantState,
    StackOutput,
    StackSnapshot,
)
from colav_simulator.modular_gnc.environment import (
    AnalyticEnvironmentField,
    PassThroughEnvironmentField,
)
from colav_simulator.modular_gnc.load_model import EnvironmentalLoadModel
from colav_simulator.modular_gnc.passthrough_modules import PassThroughModules
from colav_simulator.modular_gnc.plant import (
    Generic3DOFPlant,
    Generic3DOFPlantParameters,
    GenericRoll4DOFPlant,
    GenericRoll4DOFPlantParameters,
)


def _build_guidance(selection: Any) -> Any:
    """Build the registered guidance implementation for a module selection."""
    if selection.identity == "integral_line_of_sight":
        from colav_simulator.modular_gnc.guidance_ilos import IntegralLineOfSightGuidance  # noqa: PLC0415

        return IntegralLineOfSightGuidance.from_params(selection.parameters)
    return None


def _build_allocator(selection: Any) -> Any:
    """Build the registered allocator implementation for a module selection."""
    if selection.identity == "data_driven_allocator":
        from colav_simulator.modular_gnc.allocator import DataDrivenAllocator  # noqa: PLC0415

        return DataDrivenAllocator.from_params(selection.parameters)
    return None


def _build_actuator(selection: Any) -> Any:
    """Build the registered actuator dynamics implementation for a module selection."""
    if selection.identity == "resolved_actuator_dynamics":
        from colav_simulator.modular_gnc.actuator_dynamics import ResolvedActuatorDynamics  # noqa: PLC0415

        return ResolvedActuatorDynamics.from_params(selection.parameters)
    return None


class ModularShipStack:
    """Contracts-only deterministic facade; atomicity is facade-local."""

    snapshot_schema_version = "modular-ship-stack.snapshot.v1"

    def __init__(self, config: ShipModulesConfig, modules: PassThroughModules) -> None:
        if (
            "plant" in config.modules
            and config.modules["plant"].identity in ("generic_3dof_plant", "generic_roll_4dof_plant")
            and config.scheduler.get("plant_period_ticks") != 1
        ):
            plant_id = config.modules["plant"].identity
            raise UnsupportedModuleCombinationError(
                f"{plant_id} requires plant_period_ticks == 1 (base-clock cadence only; "
                f"got {config.scheduler.get('plant_period_ticks')})"
            )
        if getattr(modules, "_plant", None) is not None and config.scheduler.get("plant_period_ticks") != 1:
            plant_id = (
                "generic_roll_4dof_plant"
                if "ROLL_4DOF" in getattr(modules._plant, "capabilities", ())
                else "generic_3dof_plant"
            )
            raise UnsupportedModuleCombinationError(
                f"{plant_id} requires plant_period_ticks == 1 (base-clock cadence only; "
                f"got {config.scheduler.get('plant_period_ticks')})"
            )
        if (
            "actuator" in config.modules or getattr(modules, "_actuator", None) is not None
        ) and config.scheduler.get("controller_period_ticks") != 1:
            raise UnsupportedModuleCombinationError(
                "resolved_actuator_dynamics requires controller_period_ticks == 1 (base-clock cadence only; "
                f"got {config.scheduler.get('controller_period_ticks')})"
            )
        self._config = config
        self._modules = modules
        self._latch = CommandLatch(config.scheduler["controller_period_ticks"])
        self._tick = 0
        self._seed = 0
        self._initialized = False

    @classmethod
    def from_config(  # noqa: PLR0912
        cls,
        config: ShipModulesConfig | Mapping[str, Any],
        episode_seed: int = 0,
        dt_s: float = 0.1,
    ) -> ModularShipStack:
        """Build registered modular implementation."""
        from colav_simulator.modular_gnc.configuration import normalize_ship_modules  # noqa: PLC0415

        cfg = config if isinstance(config, ShipModulesConfig) else normalize_ship_modules(config)
        env_field = None
        if "environment" in cfg.modules:
            env_sel = cfg.modules["environment"]
            if env_sel.identity == "analytic_environment_field":
                env_field = AnalyticEnvironmentField.from_params(
                    env_sel.parameters,
                    dt_s=dt_s,
                    episode_seed=episode_seed,
                )
            elif env_sel.identity == "pass_through_environment":
                env_field = PassThroughEnvironmentField(dt_s=dt_s)

        load_model = None
        if "load_model" in cfg.modules:
            lm_sel = cfg.modules["load_model"]
            if lm_sel.identity == "standard_environmental_load":
                load_model = EnvironmentalLoadModel.from_params(lm_sel.parameters)
            elif lm_sel.identity == "pass_through_load_model":
                load_model = None

        plant = None
        if "plant" in cfg.modules:
            plant_sel = cfg.modules["plant"]
            if plant_sel.identity == "generic_3dof_plant":
                plant_params = Generic3DOFPlantParameters(**plant_sel.parameters)
                plant = Generic3DOFPlant(plant_params)
            elif plant_sel.identity == "generic_roll_4dof_plant":
                plant_params_4dof = GenericRoll4DOFPlantParameters(**plant_sel.parameters)
                plant = GenericRoll4DOFPlant(plant_params_4dof)
            elif plant_sel.identity == "pass_through_plant":
                plant = None

        controller = None
        if "controller" in cfg.modules:
            ctrl_sel = cfg.modules["controller"]
            if ctrl_sel.identity == "marine_pid":
                from colav_simulator.modular_gnc.controller import MarinePID, MarinePIDConfig  # noqa: PLC0415

                ctrl_cfg = MarinePIDConfig.from_params(ctrl_sel.parameters)
                controller = MarinePID(ctrl_cfg)

        guidance = _build_guidance(cfg.modules["guidance"]) if "guidance" in cfg.modules else None

        allocator = _build_allocator(cfg.modules["allocator"]) if "allocator" in cfg.modules else None

        actuator = _build_actuator(cfg.modules["actuator"]) if "actuator" in cfg.modules else None

        modules = PassThroughModules(
            environment_field=env_field,
            load_model=load_model,
            plant=plant,
            controller=controller,
            guidance=guidance,
            allocator=allocator,
            actuator=actuator,
        )
        return cls(cfg, modules)

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
        command_task = self._command_task(command)
        if command_task is not None and command_task not in self._modules.supported_tasks:
            return self._failure_output(
                before,
                FacadeFailure(
                    FailureCode.CAPABILITY_MISMATCH,
                    f"control task {command_task.value} is not supported by the assembled modules "
                    f"(Issue #56 AC1: unsupported tasks are rejected before execution)",
                    "facade",
                    self._tick,
                    details={
                        "task": command_task.value,
                        "supported_tasks": sorted(task.value for task in self._modules.supported_tasks),
                    },
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
                    phase_dt_s=dt_s * self._phase_period_ticks(phase),
                )
        except OutOfDomainError as exc:
            failure = FacadeFailure(
                code=FailureCode.OUT_OF_DOMAIN,
                message=str(exc),
                phase=phase,
                tick=self._tick,
                details={"exception_type": type(exc).__name__},
            )
            return self._failure_output(before, failure)
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
            environmental_loads=getattr(self._modules, "environmental_loads", lambda: None)(),
            controller_trace=getattr(self._modules, "controller_trace", lambda: None)(),
            achieved_load=getattr(self._modules, "achieved_load", lambda: None)(),
            actuator_trace=getattr(self._modules, "actuator_trace", lambda: None)(),
        )
        self._tick += 1
        return output

    _PHASE_PERIOD_KEYS: Mapping[str, str] = {
        "guidance": "guidance_period_ticks",
        "controller": "controller_period_ticks",
        "allocator": "controller_period_ticks",
        "actuator": "controller_period_ticks",
        "environment": "plant_period_ticks",
        "plant": "plant_period_ticks",
    }

    def _phase_period_ticks(self, phase: str) -> int:
        """Return the scheduler period in ticks for one phase."""
        return self._config.scheduler[self._PHASE_PERIOD_KEYS[phase]]

    def _phase_due(self, phase: str) -> bool:
        return self._tick % self._phase_period_ticks(phase) == 0

    @staticmethod
    def _command_task(command: CommandInput) -> ControlTask | None:
        """Return the control task carried by the command, if any."""
        if command.direct_reference is not None:
            return command.direct_reference.task
        if command.tracked_route is not None:
            return command.tracked_route.task
        return None

    def _failure_output(self, before: StackSnapshot, failure: FacadeFailure) -> StackOutput:
        self.restore(before)
        return StackOutput(
            tick=self._tick,
            navigation=self._modules.navigation(),
            plant=self._modules.plant_state(),
            applied_reference=None,
            failure=failure,
            environment_observation=getattr(self._modules, "environment_observation", lambda: None)(),
            environmental_loads=getattr(self._modules, "environmental_loads", lambda: None)(),
            controller_trace=getattr(self._modules, "controller_trace", lambda: None)(),
            achieved_load=getattr(self._modules, "achieved_load", lambda: None)(),
            actuator_trace=getattr(self._modules, "actuator_trace", lambda: None)(),
        )

    def _uninitialized_failure(self, message: str) -> StackOutput:
        zero = NavigationState(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        return StackOutput(
            tick=self._tick,
            navigation=zero,
            plant=PlantState(zero.as_array(), frozenset({"PLANAR_3DOF"})),
            applied_reference=None,
            failure=FacadeFailure(FailureCode.INVALID_INPUT, message, "facade", self._tick),
            environmental_loads=None,
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
