"""Resolved actuator dynamics and separate fidelity profile (Issue #59, S6.2).

Covers per-actuator rate limiting and transport delay as one discrete-phase
owner (TS-14, TS-22), deterministic reset/snapshot/restore (TS-15), explicit
rate/delay evidence in traces (no hidden clipping), force-limit contract
enforcement against allocator-owned limits, fidelity identity separation
(ideal vs resolved, AC1), configuration duplicate-assembly rejection (AC4),
achieved-load anti-windup feedback through the resolved profile (AC2), and
ideal-vs-resolved stack behavior across layouts (G5, G9).
"""

from __future__ import annotations

import numpy as np
import pytest

from colav_simulator.modular_gnc.actuator_dynamics import (
    ResolvedActuatorDynamics,
    ResolvedActuatorDynamicsConfig,
    ResolvedActuatorDynamicsSnapshot,
)
from colav_simulator.modular_gnc.allocator import (
    KNOWN_ACTUATOR_LAYOUT_ASSETS,
    DataDrivenAllocator,
)
from colav_simulator.modular_gnc.configuration import (
    REGISTRY_V1,
    CapabilityMismatchError,
    UnsupportedModuleCombinationError,
    normalize_ship_modules,
)
from colav_simulator.modular_gnc.contracts import (
    CommandInput,
    ControlTask,
    DirectReference,
    FailureCode,
    NavigationState,
    VesselLoad,
)
from colav_simulator.modular_gnc.passthrough_modules import PassThroughModules
from colav_simulator.modular_gnc.plant import Generic3DOFPlant, Generic3DOFPlantParameters
from colav_simulator.modular_gnc.stack import ModularShipStack

_TRIPLE_LAYOUT = "default_triple_actuator_layout_v1"
_QUAD_LAYOUT = "quad_diagonal_actuator_layout_v1"
_MAIN_ONLY_LAYOUT = "main_only_actuator_layout_v1"
_TRIPLE_IDS = KNOWN_ACTUATOR_LAYOUT_ASSETS[_TRIPLE_LAYOUT].actuator_ids()

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


def _rate_map(main: float = 1.0e9, bow: float = 1.0e9, stern: float = 1.0e9) -> dict[str, float]:
    return {"main_thruster": main, "bow_tunnel_thruster": bow, "stern_tunnel_thruster": stern}


def _delay_map(main: int = 0, bow: int = 0, stern: int = 0) -> dict[str, int]:
    return {"main_thruster": main, "bow_tunnel_thruster": bow, "stern_tunnel_thruster": stern}


def _resolved_params(
    layout_id: str = _TRIPLE_LAYOUT,
    rate_limit_n_per_s: dict[str, float] | None = None,
    delay_ticks: dict[str, int] | None = None,
) -> dict:
    """Build full-coverage actuator dynamics parameters for a known layout."""
    layout = KNOWN_ACTUATOR_LAYOUT_ASSETS.get(layout_id)
    ids = layout.actuator_ids() if layout is not None else _TRIPLE_IDS
    return {
        "layout_asset_id": layout_id,
        "rate_limit_n_per_s": dict(rate_limit_n_per_s) if rate_limit_n_per_s is not None else dict.fromkeys(ids, 1.0e9),
        "delay_ticks": dict(delay_ticks) if delay_ticks is not None else dict.fromkeys(ids, 0),
    }


def _module(
    layout_id: str = _TRIPLE_LAYOUT,
    rate_limit_n_per_s: dict[str, float] | None = None,
    delay_ticks: dict[str, int] | None = None,
) -> ResolvedActuatorDynamics:
    config = ResolvedActuatorDynamicsConfig.from_params(
        _resolved_params(layout_id, rate_limit_n_per_s, delay_ticks)
    )
    return ResolvedActuatorDynamics(config)


def _commands(**forces: float) -> dict[str, float]:
    """Build a full-coverage command mapping defaulting every actuator to zero."""
    values = dict.fromkeys(_TRIPLE_IDS, 0.0)
    values.update(forces)
    return values


def _healthy() -> dict[str, float]:
    return dict.fromkeys(_TRIPLE_IDS, 1.0)


class TestResolvedActuatorDynamicsConfig:
    """Actuator dynamics parameters are full-coverage, validated, content-hashed (TS-22, TS-27)."""

    def test_from_params_builds_content_hashed_config(self) -> None:
        config = ResolvedActuatorDynamicsConfig.from_params(_resolved_params())
        again = ResolvedActuatorDynamicsConfig.from_params(_resolved_params())
        changed = ResolvedActuatorDynamicsConfig.from_params(_resolved_params(rate_limit_n_per_s=_rate_map(1.0e5)))

        assert config.layout_asset_id == _TRIPLE_LAYOUT
        assert len(config.config_hash) == 64
        assert all(c in "0123456789abcdef" for c in config.config_hash)
        assert config.config_hash == again.config_hash
        assert config.config_hash != changed.config_hash

    def test_from_params_requires_full_actuator_coverage(self) -> None:
        missing = _resolved_params()
        del missing["rate_limit_n_per_s"]["main_thruster"]
        with pytest.raises(ValueError, match="main_thruster"):
            ResolvedActuatorDynamicsConfig.from_params(missing)

        extra = _resolved_params()
        extra["rate_limit_n_per_s"]["phantom_thruster"] = 1.0e5
        with pytest.raises(ValueError, match="phantom_thruster"):
            ResolvedActuatorDynamicsConfig.from_params(extra)

    def test_from_params_rejects_unknown_layout_asset(self) -> None:
        with pytest.raises(ValueError, match="unknown actuator layout asset id"):
            ResolvedActuatorDynamicsConfig.from_params(_resolved_params(layout_id="not_a_layout"))

    @pytest.mark.parametrize("bad_rate", [0.0, -1.0e5, float("nan"), float("inf"), True])
    def test_from_params_rejects_invalid_rate_limits(self, bad_rate: float) -> None:
        params = _resolved_params()
        params["rate_limit_n_per_s"]["main_thruster"] = bad_rate
        with pytest.raises((ValueError, TypeError)):
            ResolvedActuatorDynamicsConfig.from_params(params)

    @pytest.mark.parametrize("bad_delay", [-1, 1.5, True])
    def test_from_params_rejects_invalid_delay_ticks(self, bad_delay: int) -> None:
        params = _resolved_params()
        params["delay_ticks"]["main_thruster"] = bad_delay
        with pytest.raises((ValueError, TypeError)):
            ResolvedActuatorDynamicsConfig.from_params(params)

    def test_from_params_rejects_unknown_and_missing_param_keys(self) -> None:
        with pytest.raises(ValueError, match="saturation_gain"):
            ResolvedActuatorDynamicsConfig.from_params({**_resolved_params(), "saturation_gain": 1.0})
        with pytest.raises(ValueError, match="layout_asset_id"):
            ResolvedActuatorDynamicsConfig.from_params({"rate_limit_n_per_s": {}, "delay_ticks": {}})


class TestResolvedActuatorDynamicsRate:
    """Per-actuator force rate limiting is explicit, single-owner, and limit-respecting."""

    def test_constant_command_ramps_at_declared_rate_then_releases(self) -> None:
        module = _module(rate_limit_n_per_s=_rate_map(1.0e5))

        trace_0 = module.apply(_commands(main_thruster=2.1e5), _healthy(), tick=0, time_s=0.0, dt_s=1.0)
        trace_1 = module.apply(_commands(main_thruster=2.1e5), _healthy(), tick=1, time_s=1.0, dt_s=1.0)
        trace_2 = module.apply(_commands(main_thruster=2.1e5), _healthy(), tick=2, time_s=2.0, dt_s=1.0)

        assert trace_0.actuator_outputs_n["main_thruster"] == pytest.approx(1.0e5)
        assert trace_1.actuator_outputs_n["main_thruster"] == pytest.approx(2.0e5)
        assert trace_2.actuator_outputs_n["main_thruster"] == pytest.approx(2.1e5)
        assert trace_0.rate_limited_actuators == ("main_thruster",)
        assert trace_1.rate_limited_actuators == ("main_thruster",)
        assert trace_2.rate_limited_actuators == ()

    def test_dt_scales_the_rate_step(self) -> None:
        module = _module(rate_limit_n_per_s=_rate_map(1.0e5))

        trace = module.apply(_commands(main_thruster=5.0e5), _healthy(), tick=0, time_s=0.0, dt_s=0.5)

        assert trace.actuator_outputs_n["main_thruster"] == pytest.approx(0.5e5)

    def test_outputs_never_violate_declared_force_limits(self) -> None:
        module = _module(rate_limit_n_per_s=_rate_map(3.0e5))
        layout = KNOWN_ACTUATOR_LAYOUT_ASSETS[_TRIPLE_LAYOUT]
        limits = {spec.actuator_id: (spec.min_force_n, spec.max_force_n) for spec in layout.actuators}

        for tick, surge in enumerate([4.0e5, -6.0e5, 8.0e5, -8.0e5, 0.0]):
            trace = module.apply(_commands(main_thruster=surge), _healthy(), tick=tick, time_s=float(tick), dt_s=1.0)
            for actuator_id, force_n in trace.actuator_outputs_n.items():
                low, high = limits[actuator_id]
                assert low <= force_n <= high

    def test_apply_rejects_command_violating_allocator_owned_limits(self) -> None:
        module = _module()

        with pytest.raises(ValueError, match="allocator-owned force limits"):
            module.apply(_commands(main_thruster=9.0e5), _healthy(), tick=0, time_s=0.0, dt_s=1.0)

    def test_apply_rejects_unknown_actuator_nonfinite_command_and_bad_dt(self) -> None:
        module = _module()

        with pytest.raises(ValueError, match="phantom"):
            module.apply(_commands(phantom=1.0), _healthy(), tick=0, time_s=0.0, dt_s=1.0)
        with pytest.raises(ValueError, match="finite"):
            module.apply(_commands(main_thruster=float("nan")), _healthy(), tick=0, time_s=0.0, dt_s=1.0)
        with pytest.raises(ValueError, match="dt_s"):
            module.apply(_commands(), _healthy(), tick=0, time_s=0.0, dt_s=0.0)
        with pytest.raises(ValueError, match="tick"):
            module.apply(_commands(), _healthy(), tick=-1, time_s=0.0, dt_s=1.0)
        with pytest.raises(ValueError, match="actuator_health"):
            module.apply(_commands(), {"main_thruster": 1.0}, tick=0, time_s=0.0, dt_s=1.0)


class TestResolvedActuatorDynamicsDelay:
    """Per-actuator transport delay holds delivery for exactly delay_ticks (explicit pending evidence)."""

    def test_delay_ticks_hold_output_until_elapsed(self) -> None:
        module = _module(delay_ticks=_delay_map(main=2))

        trace_0 = module.apply(_commands(main_thruster=2.0e5), _healthy(), tick=0, time_s=0.0, dt_s=1.0)
        trace_1 = module.apply(_commands(main_thruster=2.0e5), _healthy(), tick=1, time_s=1.0, dt_s=1.0)
        trace_2 = module.apply(_commands(main_thruster=2.0e5), _healthy(), tick=2, time_s=2.0, dt_s=1.0)
        trace_3 = module.apply(_commands(main_thruster=2.0e5), _healthy(), tick=3, time_s=3.0, dt_s=1.0)

        assert trace_0.actuator_outputs_n["main_thruster"] == 0.0
        assert trace_1.actuator_outputs_n["main_thruster"] == 0.0
        assert trace_2.actuator_outputs_n["main_thruster"] == pytest.approx(2.0e5)
        assert trace_3.actuator_outputs_n["main_thruster"] == pytest.approx(2.0e5)
        assert trace_0.pending_delay_ticks["main_thruster"] == 1
        assert trace_1.pending_delay_ticks["main_thruster"] == 2
        assert trace_2.pending_delay_ticks["main_thruster"] == 2
        assert trace_0.pending_delay_ticks["bow_tunnel_thruster"] == 0

    def test_zero_delay_delivers_immediately(self) -> None:
        module = _module()

        trace = module.apply(_commands(main_thruster=3.0e5), _healthy(), tick=0, time_s=0.0, dt_s=1.0)

        assert trace.actuator_outputs_n["main_thruster"] == pytest.approx(3.0e5)
        assert trace.pending_delay_ticks["main_thruster"] == 0

    def test_rate_and_delay_compose_without_cross_talk(self) -> None:
        module = _module(rate_limit_n_per_s=_rate_map(1.0e5), delay_ticks=_delay_map(main=1))

        outputs = [
            module.apply(_commands(main_thruster=2.1e5), _healthy(), tick=t, time_s=float(t), dt_s=1.0)
            .actuator_outputs_n["main_thruster"]
            for t in range(4)
        ]

        assert outputs == [pytest.approx(v) for v in (0.0, 1.0e5, 2.0e5, 2.1e5)]


class TestResolvedActuatorDynamicsLifecycle:
    """Deterministic reset, snapshot/restore, and trace identity (TS-15, TS-22, AC1)."""

    def test_reset_restores_zero_force_and_empty_delay_lines(self) -> None:
        module = _module(rate_limit_n_per_s=_rate_map(1.0e5), delay_ticks=_delay_map(main=2))
        module.apply(_commands(main_thruster=2.1e5), _healthy(), tick=0, time_s=0.0, dt_s=1.0)
        module.apply(_commands(main_thruster=2.1e5), _healthy(), tick=1, time_s=1.0, dt_s=1.0)

        module.reset()
        trace_0 = module.apply(_commands(main_thruster=2.1e5), _healthy(), tick=0, time_s=0.0, dt_s=1.0)
        trace_1 = module.apply(_commands(main_thruster=2.1e5), _healthy(), tick=1, time_s=1.0, dt_s=1.0)
        trace_2 = module.apply(_commands(main_thruster=2.1e5), _healthy(), tick=2, time_s=2.0, dt_s=1.0)

        assert trace_0.actuator_outputs_n["main_thruster"] == 0.0
        assert trace_0.pending_delay_ticks["main_thruster"] == 1
        assert trace_1.actuator_outputs_n["main_thruster"] == 0.0
        assert trace_1.pending_delay_ticks["main_thruster"] == 2
        assert trace_2.actuator_outputs_n["main_thruster"] == pytest.approx(1.0e5)

    def test_reset_is_idempotent(self) -> None:
        module = _module()
        module.apply(_commands(main_thruster=2.1e5), _healthy(), tick=0, time_s=0.0, dt_s=1.0)

        module.reset()
        module.reset()
        first = module.apply(_commands(main_thruster=1.0e5), _healthy(), tick=0, time_s=0.0, dt_s=1.0)
        module.reset()
        second = module.apply(_commands(main_thruster=1.0e5), _healthy(), tick=0, time_s=0.0, dt_s=1.0)

        assert first.actuator_outputs_n == second.actuator_outputs_n

    def test_snapshot_restore_roundtrip_is_deterministic(self) -> None:
        rate = _rate_map(2.0e5)
        delay = _delay_map(main=1, bow=1)
        module = _module(rate_limit_n_per_s=rate, delay_ticks=delay)
        commands = _commands(main_thruster=5.0e5, bow_tunnel_thruster=-3.0e5)
        for tick in range(3):
            module.apply(commands, _healthy(), tick=tick, time_s=float(tick), dt_s=1.0)
        snapshot = module.snapshot()

        continued = [
            module.apply(commands, _healthy(), tick=tick, time_s=float(tick), dt_s=1.0).actuator_outputs_n
            for tick in (3, 4)
        ]

        restored = _module(rate_limit_n_per_s=rate, delay_ticks=delay)
        restored.restore(snapshot)
        replayed = [
            restored.apply(commands, _healthy(), tick=tick, time_s=float(tick), dt_s=1.0).actuator_outputs_n
            for tick in (3, 4)
        ]

        for continued_outputs, replayed_outputs in zip(continued, replayed, strict=True):
            for actuator_id in continued_outputs:
                assert continued_outputs[actuator_id] == pytest.approx(replayed_outputs[actuator_id])

    def test_snapshot_is_immutable_and_restore_validates_actuator_ids(self) -> None:
        module = _module()
        module.apply(_commands(main_thruster=1.0e5), _healthy(), tick=0, time_s=0.0, dt_s=1.0)
        snapshot = module.snapshot()

        assert isinstance(snapshot, ResolvedActuatorDynamicsSnapshot)
        with pytest.raises((TypeError, ValueError)):
            snapshot.current_force_n["main_thruster"] = 0.0

        quad_module = _module(layout_id=_QUAD_LAYOUT)
        with pytest.raises(ValueError, match="actuator ids"):
            quad_module.restore(snapshot)

    def test_trace_carries_resolved_identity_and_hash_evidence(self) -> None:
        config = ResolvedActuatorDynamicsConfig.from_params(_resolved_params())
        module = ResolvedActuatorDynamics(config)

        trace = module.apply(_commands(main_thruster=1.0e5), _healthy(), tick=4, time_s=0.4, dt_s=0.1)

        assert trace.fidelity_profile == "resolved"
        assert trace.actuator_identity == "resolved_actuator_dynamics"
        assert trace.config_hash == config.config_hash
        assert trace.tick == 4
        assert trace.time_s == pytest.approx(0.4)
        assert trace.dt_s == pytest.approx(0.1)

    def test_trace_achieved_load_projects_outputs_through_nominal_geometry(self) -> None:
        module = _module()

        trace = module.apply(_commands(main_thruster=2.0e5), _healthy(), tick=0, time_s=0.0, dt_s=1.0)

        achieved = trace.achieved_vessel_load()
        assert isinstance(achieved, VesselLoad)
        assert achieved.surge_n == pytest.approx(2.0e5)
        assert achieved.sway_n == pytest.approx(0.0, abs=1e-9)
        assert achieved.yaw_nm == pytest.approx(0.0, abs=1e-9)
        assert achieved.roll_nm == 0.0
        assert trace.achieved_load[0] == pytest.approx(2.0e5)

    def test_health_scales_achieved_projection_but_not_delivered_forces(self) -> None:
        module = _module()
        degraded = dict.fromkeys(_TRIPLE_IDS, 1.0)
        degraded["main_thruster"] = 0.5

        trace = module.apply(_commands(main_thruster=2.0e5), degraded, tick=0, time_s=0.0, dt_s=1.0)

        assert trace.actuator_outputs_n["main_thruster"] == pytest.approx(2.0e5)
        assert trace.achieved_load[0] == pytest.approx(1.0e5)

    def test_multiple_layouts_build_and_apply(self) -> None:
        for layout_id in (_TRIPLE_LAYOUT, _QUAD_LAYOUT, _MAIN_ONLY_LAYOUT):
            module = _module(layout_id=layout_id)
            ids = KNOWN_ACTUATOR_LAYOUT_ASSETS[layout_id].actuator_ids()

            trace = module.apply(
                dict.fromkeys(ids, 100000.0),
                dict.fromkeys(ids, 1.0),
                tick=0,
                time_s=0.0,
                dt_s=1.0,
            )

            assert set(trace.actuator_outputs_n) == set(ids)
            assert all(force_n == pytest.approx(1.0e5) for force_n in trace.actuator_outputs_n.values())


class TestActuatorFidelityConfiguration:
    """The resolved profile is an explicit opt-in module with duplicate-assembly guards (AC1, AC4)."""

    @staticmethod
    def _ship_config(
        layout_id: str = _TRIPLE_LAYOUT,
        plant_identity: str = "generic_3dof_plant",
        with_allocator: bool = True,
        with_actuator: bool = True,
        controller_period_ticks: int | None = 1,
    ) -> dict:
        modules: dict[str, dict] = {
            "plant": {
                "identity": plant_identity,
                "parameters": {} if plant_identity == "pass_through_plant" else dict(_PLANT_PARAMS),
            },
            "guidance": {"identity": "pass_through_guidance", "parameters": {}},
            "controller": {"identity": "pass_through_controller", "parameters": {}},
        }
        if with_allocator:
            modules["allocator"] = {"identity": "data_driven_allocator", "parameters": {"layout_asset_id": layout_id}}
        if with_actuator:
            modules["actuator"] = {
                "identity": "resolved_actuator_dynamics",
                "parameters": _resolved_params(layout_id),
            }
        config: dict = {"preset": "legacy_equivalent", "modules": modules}
        if controller_period_ticks is not None:
            config["overrides"] = {"scheduler": {"controller_period_ticks": controller_period_ticks}}
        return config

    def test_registry_declares_resolved_actuator_dynamics(self) -> None:
        entry = REGISTRY_V1["resolved_actuator_dynamics"]

        assert entry.role == "actuator"
        assert entry.available is True
        assert "GENERALIZED_FORCE" in entry.capabilities
        assert "ACTUATOR_DYNAMICS_TRACE" in entry.capabilities
        assert entry.parameter_schema == {
            "layout_asset_id": {"type": "string"},
            "rate_limit_n_per_s": {"type": "object"},
            "delay_ticks": {"type": "object"},
        }

    def test_normalize_accepts_resolved_actuator_profile(self) -> None:
        config = normalize_ship_modules(self._ship_config())

        assert config.modules["actuator"].identity == "resolved_actuator_dynamics"
        assert config.fidelity_profile == "resolved"

    def test_fidelity_profile_and_config_hash_separate_ideal_and_resolved(self) -> None:
        resolved = normalize_ship_modules(self._ship_config())
        ideal = normalize_ship_modules(self._ship_config(with_actuator=False))

        assert ideal.fidelity_profile == "ideal"
        assert resolved.fidelity_profile == "resolved"
        assert ideal.config_hash != resolved.config_hash

    def test_normalize_rejects_actuator_without_allocator(self) -> None:
        with pytest.raises(UnsupportedModuleCombinationError, match="allocator"):
            normalize_ship_modules(self._ship_config(with_allocator=False))

    def test_normalize_rejects_layout_mismatch_between_allocator_and_actuator(self) -> None:
        config = self._ship_config()
        config["modules"]["allocator"]["parameters"]["layout_asset_id"] = _TRIPLE_LAYOUT
        config["modules"]["actuator"]["parameters"]["layout_asset_id"] = _QUAD_LAYOUT

        with pytest.raises(UnsupportedModuleCombinationError, match="layout"):
            normalize_ship_modules(config)

    def test_normalize_rejects_actuator_with_kinematic_plant(self) -> None:
        with pytest.raises(CapabilityMismatchError, match="GENERALIZED_FORCE"):
            normalize_ship_modules(self._ship_config(plant_identity="pass_through_plant"))

    def test_normalize_rejects_actuator_with_multi_tick_controller_cadence(self) -> None:
        with pytest.raises(UnsupportedModuleCombinationError, match="controller_period_ticks"):
            normalize_ship_modules(self._ship_config(controller_period_ticks=5))

    def test_normalize_rejects_invalid_actuator_parameters(self) -> None:
        config = self._ship_config()
        config["modules"]["actuator"]["parameters"]["rate_limit_n_per_s"]["main_thruster"] = 0.0

        with pytest.raises(UnsupportedModuleCombinationError, match="rate_limit_n_per_s"):
            normalize_ship_modules(config)


def _manual_load_command(tick: int, surge: float, sway: float, yaw: float) -> CommandInput:
    values = np.zeros(9)
    values[0] = surge
    values[1] = sway
    values[2] = yaw
    return CommandInput.direct(tick, DirectReference(values, latched_tick=tick, task=ControlTask.MANUAL_LOAD))


def _build_stack(config: dict) -> ModularShipStack:
    stack = ModularShipStack.from_config(normalize_ship_modules(config))
    stack.reset(NavigationState(0.0, 0.0, 0.0, 0.0, 0.0, 0.0), seed=7)
    return stack


def _build_explicit_stack(
    rate_limit_n_per_s: dict[str, float] | None = None,
    delay_ticks: dict[str, int] | None = None,
    **module_kwargs,
) -> tuple[ModularShipStack, DataDrivenAllocator, ResolvedActuatorDynamics]:
    """Build a resolved-profile stack from explicit modules, returning module handles."""
    allocator = DataDrivenAllocator(KNOWN_ACTUATOR_LAYOUT_ASSETS[_TRIPLE_LAYOUT])
    actuator = _module(rate_limit_n_per_s=rate_limit_n_per_s, delay_ticks=delay_ticks)
    modules = PassThroughModules(
        plant=Generic3DOFPlant(Generic3DOFPlantParameters(**_PLANT_PARAMS)),
        allocator=allocator,
        actuator=actuator,
        **module_kwargs,
    )
    config = {
        "preset": "legacy_equivalent",
        "modules": {
            "plant": {"identity": "generic_3dof_plant", "parameters": dict(_PLANT_PARAMS)},
            "guidance": {"identity": "pass_through_guidance", "parameters": {}},
            "controller": {"identity": "pass_through_controller", "parameters": {}},
            "allocator": {"identity": "data_driven_allocator", "parameters": {"layout_asset_id": _TRIPLE_LAYOUT}},
            "actuator": {
                "identity": "resolved_actuator_dynamics",
                "parameters": _resolved_params(_TRIPLE_LAYOUT, rate_limit_n_per_s, delay_ticks),
            },
        },
        "overrides": {"scheduler": {"controller_period_ticks": 1}},
    }
    stack = ModularShipStack(normalize_ship_modules(config), modules)
    stack.reset(NavigationState(0.0, 0.0, 0.0, 0.0, 0.0, 0.0), seed=7)
    return stack, allocator, actuator


class TestActuatorFidelityStackIntegration:
    """The resolved profile feeds rate/delayed loads to the plant and anti-windup feedback (AC2, G5, G9)."""

    def test_resolved_stack_applies_rate_limited_load_to_plant(self) -> None:
        resolved = _build_stack(self._integration_config(rate_limit_n_per_s=_rate_map(1.0e5)))
        ideal = _build_stack(self._integration_config(with_actuator=False))

        for tick in range(4):
            command = _manual_load_command(tick, 2.1e5, 0.0, 0.0)
            resolved_output = resolved.step(command, dt_s=1.0)
            ideal_output = ideal.step(command, dt_s=1.0)
            assert resolved_output.failure is None
            assert ideal_output.failure is None
            assert resolved_output.actuator_trace is not None
            assert resolved_output.achieved_load.surge_n == pytest.approx(
                resolved_output.actuator_trace.actuator_outputs_n["main_thruster"]
            )
            if tick < 3:
                assert resolved_output.navigation.surge_mps < ideal_output.navigation.surge_mps

    @staticmethod
    def _integration_config(
        rate_limit_n_per_s: dict[str, float] | None = None,
        delay_ticks: dict[str, int] | None = None,
        with_actuator: bool = True,
        controller: str = "pass_through_controller",
        controller_params: dict | None = None,
        layout_id: str = _TRIPLE_LAYOUT,
    ) -> dict:
        modules: dict[str, dict] = {
            "plant": {"identity": "generic_3dof_plant", "parameters": dict(_PLANT_PARAMS)},
            "guidance": {"identity": "pass_through_guidance", "parameters": {}},
            "controller": {"identity": controller, "parameters": dict(controller_params or {})},
            "allocator": {"identity": "data_driven_allocator", "parameters": {"layout_asset_id": layout_id}},
        }
        if with_actuator:
            modules["actuator"] = {
                "identity": "resolved_actuator_dynamics",
                "parameters": _resolved_params(layout_id, rate_limit_n_per_s, delay_ticks),
            }
        return {
            "preset": "legacy_equivalent",
            "modules": modules,
            "overrides": {"scheduler": {"controller_period_ticks": 1}},
        }

    def test_stack_output_carries_resolved_trace_and_achieved_provenance(self) -> None:
        stack = _build_stack(self._integration_config())

        output = stack.step(_manual_load_command(0, 2.1e5, 5.0e4, 1.0e5), dt_s=1.0)

        assert output.failure is None
        assert output.actuator_trace is not None
        assert output.actuator_trace.fidelity_profile == "resolved"
        assert output.achieved_load is not None
        assert output.achieved_load.source == "RESOLVED_ACTUATOR_DYNAMICS"
        assert output.achieved_load.surge_n == pytest.approx(2.1e5)
        assert output.achieved_load.roll_nm == 0.0
        details = output.achieved_load.details
        assert details["actuator_identity"] == "resolved_actuator_dynamics"
        assert details["actuator_config_hash"] == output.actuator_trace.config_hash
        assert details["rate_limited_actuators"] == ()
        assert details["pending_delay_ticks"]["main_thruster"] == 0

    def test_ideal_path_unchanged_without_actuator_module(self) -> None:
        stack = _build_stack(self._integration_config(with_actuator=False))

        output = stack.step(_manual_load_command(0, 2.1e5, 5.0e4, 1.0e5), dt_s=1.0)

        assert output.failure is None
        assert output.actuator_trace is None
        assert stack.modules.actuator_trace() is None
        assert output.achieved_load.source == "DATA_DRIVEN_ALLOCATOR"

    def test_saturation_then_release_cycle_is_explicit(self) -> None:
        stack, allocator, _ = _build_explicit_stack(rate_limit_n_per_s=_rate_map(4.0e5))

        out_0 = stack.step(_manual_load_command(0, 5.0e7, 0.0, 0.0), dt_s=1.0)
        saturated_solution = stack.modules.allocator_solution()
        out_1 = stack.step(_manual_load_command(1, 5.0e7, 0.0, 0.0), dt_s=1.0)
        out_2 = stack.step(_manual_load_command(2, 2.1e5, 0.0, 0.0), dt_s=1.0)
        out_3 = stack.step(_manual_load_command(3, 2.1e5, 0.0, 0.0), dt_s=1.0)
        released_solution = stack.modules.allocator_solution()

        assert allocator.allocate(VesselLoad(surge_n=5.0e7), tick=0).saturated is True
        assert saturated_solution.saturated is True
        assert saturated_solution.active_constraints == (("main_thruster", "max_force_n"),)
        assert out_0.actuator_trace.actuator_outputs_n["main_thruster"] == pytest.approx(4.0e5)
        assert out_1.actuator_trace.actuator_outputs_n["main_thruster"] == pytest.approx(8.0e5)
        assert out_0.actuator_trace.rate_limited_actuators == ("main_thruster",)
        assert out_2.actuator_trace.actuator_outputs_n["main_thruster"] == pytest.approx(4.0e5)
        assert out_2.actuator_trace.rate_limited_actuators == ("main_thruster",)
        assert out_3.actuator_trace.rate_limited_actuators == ()
        assert out_3.actuator_trace.actuator_outputs_n["main_thruster"] == pytest.approx(2.1e5)
        assert released_solution.saturated is False
        assert out_3.achieved_load.saturated is False
        assert out_3.achieved_load.surge_n == pytest.approx(2.1e5)

    def test_actuator_failure_zeroes_failed_channel_contribution(self) -> None:
        stack, allocator, _ = _build_explicit_stack()

        healthy = stack.step(_manual_load_command(0, 2.1e5, 0.0, 0.0), dt_s=1.0)
        allocator.set_actuator_health("main_thruster", 0.0)
        failed = stack.step(_manual_load_command(1, 2.1e5, 0.0, 0.0), dt_s=1.0)

        assert healthy.failure is None and failed.failure is None
        assert allocator.actuator_health()["main_thruster"] == 0.0
        solution = stack.modules.allocator_solution()
        assert solution.degraded is True
        assert "main_thruster" in solution.degraded_actuators
        assert failed.actuator_trace.actuator_outputs_n["main_thruster"] == pytest.approx(0.0)
        assert failed.achieved_load.surge_n == pytest.approx(0.0, abs=1e-6)
        assert healthy.achieved_load.surge_n == pytest.approx(2.1e5)

    def test_degraded_control_stays_deterministic_within_limits(self) -> None:
        stack, allocator, _ = _build_explicit_stack(rate_limit_n_per_s=_rate_map(2.0e5))
        allocator.set_actuator_health("main_thruster", 0.5)

        first = stack.step(_manual_load_command(0, 2.1e5, 0.0, 0.0), dt_s=1.0)
        second = stack.step(_manual_load_command(1, 2.1e5, 0.0, 0.0), dt_s=1.0)
        third = stack.step(_manual_load_command(2, 2.1e5, 0.0, 0.0), dt_s=1.0)

        assert first.failure is None and second.failure is None and third.failure is None
        solution = stack.modules.allocator_solution()
        assert solution.degraded is True
        assert solution.actuator_commands_n["main_thruster"] == pytest.approx(4.2e5)
        assert first.actuator_trace.actuator_outputs_n["main_thruster"] == pytest.approx(2.0e5)
        assert second.actuator_trace.actuator_outputs_n["main_thruster"] == pytest.approx(4.0e5)
        assert third.actuator_trace.actuator_outputs_n["main_thruster"] == pytest.approx(4.2e5)
        assert third.actuator_trace.achieved_load[0] == pytest.approx(2.1e5)

        reference, reference_allocator, _ = _build_explicit_stack(rate_limit_n_per_s=_rate_map(2.0e5))
        reference_allocator.set_actuator_health("main_thruster", 0.5)
        replay = [
            reference.step(_manual_load_command(tick, 2.1e5, 0.0, 0.0), dt_s=1.0).actuator_trace.actuator_outputs_n
            for tick in range(3)
        ]
        assert replay[0]["main_thruster"] == pytest.approx(first.actuator_trace.actuator_outputs_n["main_thruster"])
        assert replay[1]["main_thruster"] == pytest.approx(second.actuator_trace.actuator_outputs_n["main_thruster"])
        assert replay[2]["main_thruster"] == pytest.approx(third.actuator_trace.actuator_outputs_n["main_thruster"])

    def test_marine_pid_antiwindup_uses_previous_tick_actuator_feedback(self) -> None:
        config = self._integration_config(
            rate_limit_n_per_s=_rate_map(1.0e5),
            controller="marine_pid",
            controller_params={
                "kp": [1.0e5, 1.0e5, 1.0e6],
                "ki": [0.0, 0.0, 0.0],
                "kd": [0.0, 0.0, 0.0],
                "antiwindup_gain": [0.8, 0.8, 0.8],
                "min_output": [-1.0e12, -1.0e12, -1.0e12],
                "max_output": [1.0e12, 1.0e12, 1.0e12],
            },
        )
        stack = _build_stack(config)

        values = np.zeros(9)
        values[3] = 2.0
        controller_traces = []
        actuator_achieved = []
        for tick in range(3):
            output = stack.step(CommandInput.direct(tick, DirectReference(values, latched_tick=tick)), dt_s=1.0)
            assert output.failure is None
            controller_traces.append(output.controller_trace)
            actuator_achieved.append(output.actuator_trace.achieved_load)

        for tick in (1, 2):
            for channel in range(3):
                expected = 0.8 * (actuator_achieved[tick - 1][channel] - controller_traces[tick].raw_request[channel])
                assert controller_traces[tick].antiwindup_correction[channel] == pytest.approx(expected, rel=1e-9, abs=1e-6)

    def test_multiple_layouts_resolved_through_configuration(self) -> None:
        for layout_id in (_TRIPLE_LAYOUT, _QUAD_LAYOUT, _MAIN_ONLY_LAYOUT):
            stack = _build_stack(self._integration_config(layout_id=layout_id))
            ids = KNOWN_ACTUATOR_LAYOUT_ASSETS[layout_id].actuator_ids()

            output = stack.step(_manual_load_command(0, 1.0e5, 0.0, 0.0), dt_s=1.0)

            assert output.failure is None
            assert output.actuator_trace is not None
            assert set(output.actuator_trace.actuator_outputs_n) == set(ids)

    def test_resolved_stack_snapshot_restore_is_deterministic(self) -> None:
        rate = _rate_map(2.0e5)
        delay = _delay_map(main=1, bow=1)
        stack, _, _ = _build_explicit_stack(rate_limit_n_per_s=rate, delay_ticks=delay)
        for tick in range(2):
            assert stack.step(_manual_load_command(tick, 5.0e5, -3.0e5, 0.0), dt_s=1.0).failure is None
        before = stack.snapshot()

        advanced = [
            stack.step(_manual_load_command(tick, 5.0e5, -3.0e5, 0.0), dt_s=1.0) for tick in (2, 3)
        ]

        reference, _, _ = _build_explicit_stack(rate_limit_n_per_s=rate, delay_ticks=delay)
        reference_outputs = [
            reference.step(_manual_load_command(tick, 5.0e5, -3.0e5, 0.0), dt_s=1.0) for tick in range(4)
        ]

        stack.restore(before)
        replayed = [
            stack.step(_manual_load_command(tick, 5.0e5, -3.0e5, 0.0), dt_s=1.0) for tick in (2, 3)
        ]

        for advanced_output, reference_output, replayed_output in zip(
            advanced, reference_outputs[2:], replayed, strict=True
        ):
            np.testing.assert_allclose(advanced_output.plant.values, reference_output.plant.values)
            np.testing.assert_allclose(replayed_output.plant.values, reference_output.plant.values)
            assert replayed_output.actuator_trace == reference_output.actuator_trace
            assert replayed_output.achieved_load == reference_output.achieved_load

    def test_actuator_phase_failure_is_structured_and_atomic(self) -> None:
        stack, _, _ = _build_explicit_stack(fail_phase="actuator", fail_tick=1)
        assert stack.step(_manual_load_command(0, 2.1e5, 0.0, 0.0), dt_s=1.0).failure is None
        before = stack.snapshot()

        output = stack.step(CommandInput.none(1), dt_s=1.0)

        assert output.failure is not None
        assert output.failure.code is FailureCode.MODULE_FAILURE
        assert output.failure.phase == "actuator"
        assert stack.tick == 1
        assert stack.snapshot() == before

    def test_supported_tasks_with_resolved_actuator_is_module_intersection(self) -> None:
        stack = _build_stack(self._integration_config())

        assert stack.modules.supported_tasks == frozenset({ControlTask.TRANSIT, ControlTask.MANUAL_LOAD})
        assert stack.config.fidelity_profile == "resolved"
