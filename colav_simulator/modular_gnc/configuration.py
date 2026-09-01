"""Strict opt-in modular ship configuration and minimal registry v1."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any


def _deep_freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _deep_freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_deep_freeze(item) for item in value)
    return value


def _deep_thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _deep_thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_deep_thaw(item) for item in value]
    return value


class UnsupportedModuleCombinationError(ValueError):
    """Raised when selected module identity or tuple is unsupported."""


class DependencyUnavailableError(RuntimeError):
    """Raised when supported module dependency is unavailable."""


@dataclass(frozen=True)
class RegistryEntry:
    """Minimal registry v1 metadata."""

    identity: str
    role: str
    implementation_version: str
    interface_version: str
    capabilities: frozenset[str]
    parameter_schema: Mapping[str, Any]
    available: bool = True

    def __post_init__(self) -> None:
        """Freeze capabilities and parameter schema."""
        object.__setattr__(self, "capabilities", frozenset(self.capabilities))
        object.__setattr__(self, "parameter_schema", _deep_freeze(self.parameter_schema))


REGISTRY_V1 = MappingProxyType(
    {
        "pass_through_plant": RegistryEntry(
            "pass_through_plant",
            "plant",
            "1.0.0",
            "plant.v1",
            frozenset({"PLANAR_3DOF", "KINEMATIC_REFERENCE"}),
            {"current_relative_damping": {"type": "boolean"}},
        ),
        "pass_through_guidance": RegistryEntry(
            "pass_through_guidance", "guidance", "1.0.0", "guidance.v1", frozenset({"DIRECT_REFERENCE"}), {}
        ),
        "pass_through_controller": RegistryEntry(
            "pass_through_controller", "controller", "1.0.0", "controller.v1", frozenset({"TRANSIT"}), {}
        ),
        "optional_native_controller": RegistryEntry(
            "optional_native_controller",
            "controller",
            "1.0.0",
            "controller.v1",
            frozenset({"TRANSIT"}),
            {},
            available=False,
        ),
        "analytic_environment_field": RegistryEntry(
            "analytic_environment_field",
            "environment",
            "1.0.0",
            "environment.v1",
            frozenset({"WIND", "CURRENT", "WAVE_FIELD", "MEAN_DRIFT"}),
            {
                "wind_velocity_ne": {"type": "array"},
                "wind_reference_height_m": {"type": "number"},
                "wind_perturbation_std": {"type": "array"},
                "current_velocity_ne": {"type": "array"},
                "current_reference": {"type": "string"},
                "current_perturbation_std": {"type": "array"},
                "wave_significant_height_m": {"type": "number"},
                "wave_peak_period_s": {"type": "number"},
                "wave_direction_to_rad": {"type": "number"},
                "wave_num_components": {"type": "integer"},
                "wave_directional_spread_rad": {"type": "number"},
                "available": {"type": "boolean"},
            },
        ),
        "pass_through_environment": RegistryEntry(
            "pass_through_environment",
            "environment",
            "1.0.0",
            "environment.v1",
            frozenset({"PASS_THROUGH"}),
            {},
        ),
        "standard_environmental_load": RegistryEntry(
            "standard_environmental_load",
            "load_model",
            "1.0.0",
            "load_model.v1",
            frozenset({"WIND_LOAD", "CURRENT_LOAD", "WAVE_FIRST_ORDER_LOAD", "WAVE_MEAN_DRIFT_LOAD"}),
            {
                "length_between_perpendiculars_m": {"type": "number"},
                "beam_m": {"type": "number"},
                "draft_m": {"type": "number"},
                "wind_frontal_area_m2": {"type": "number"},
                "wind_lateral_area_m2": {"type": "number"},
                "wind_z_center_m": {"type": "number"},
                "wind_roll_moment_arm_m": {"type": "number"},
                "air_density_kg_m3": {"type": "number"},
                "water_depth_m": {"type": "number"},
                "kg_m": {"type": "number"},
                "current_roll_moment_arm_m": {"type": "number"},
                "water_density_kg_m3": {"type": "number"},
                "displacement_ton": {"type": "number"},
                "gm_t_m": {"type": "number"},
                "bow_angle_rad": {"type": "number"},
                "c_wl_aft": {"type": "number"},
                "gravity_mps2": {"type": "number"},
                "current_strategy": {"type": "string"},
                "wave_mode": {"type": "string"},
                "enable_wind": {"type": "boolean"},
                "enable_current": {"type": "boolean"},
                "current_relative_damping": {"type": "boolean"},
                "external_current_load": {"type": "boolean"},
            },
        ),
        "pass_through_load_model": RegistryEntry(
            "pass_through_load_model",
            "load_model",
            "1.0.0",
            "load_model.v1",
            frozenset({"ZERO_LOAD"}),
            {},
        ),
    }
)

_PRESETS: dict[str, dict[str, Any]] = {
    "legacy_equivalent": {
        "scheduler": {"plant_period_ticks": 1, "guidance_period_ticks": 25, "controller_period_ticks": 5},
    }
}


@dataclass(frozen=True)
class ModuleSelection:
    """Frozen module identity and parameters."""

    identity: str
    parameters: Mapping[str, Any]

    def __post_init__(self) -> None:
        """Freeze module parameters."""
        object.__setattr__(self, "parameters", _deep_freeze(self.parameters))

    def __deepcopy__(self, memo: dict[int, Any]) -> ModuleSelection:
        """Reuse immutable selection during episode template cloning."""
        memo[id(self)] = self
        return self


@dataclass(frozen=True)
class ShipModulesConfig:
    """Normalized, frozen, content-addressed modular ship configuration."""

    preset: str
    modules: Mapping[str, ModuleSelection]
    scheduler: Mapping[str, int]
    config_hash: str
    source: Mapping[str, Any]

    def __post_init__(self) -> None:
        """Freeze nested normalized mappings."""
        object.__setattr__(self, "modules", MappingProxyType(dict(self.modules)))
        object.__setattr__(self, "scheduler", _deep_freeze(self.scheduler))
        object.__setattr__(self, "source", _deep_freeze(self.source))

    def with_overrides(self, overrides: Mapping[str, Any]) -> ShipModulesConfig:
        """Re-normalize with controlled scenario overrides."""
        source = _deep_thaw(self.source)
        source["overrides"] = _deep_merge(dict(source.get("overrides", {})), dict(overrides))
        return normalize_ship_modules(source)

    def to_dict(self) -> dict[str, Any]:
        """Return original opt-in configuration shape."""
        return _deep_thaw(self.source)

    def __deepcopy__(self, memo: dict[int, Any]) -> ShipModulesConfig:
        """Reuse immutable configuration during episode template cloning."""
        memo[id(self)] = self
        return self


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _validate_parameter_type(identity: str, param_name: str, raw_val: Any, spec: Mapping[str, Any]) -> None:
    expected_type = spec.get("type")
    if expected_type == "boolean":
        if not isinstance(raw_val, bool):
            raise UnsupportedModuleCombinationError(
                f"parameter {param_name} for {identity} must be an exact boolean, got {type(raw_val).__name__}"
            )
    elif expected_type == "number":
        if isinstance(raw_val, bool) or not isinstance(raw_val, (int, float)) or not math.isfinite(raw_val):
            raise UnsupportedModuleCombinationError(
                f"parameter {param_name} for {identity} must be a finite number, got {raw_val!r}"
            )
    elif expected_type == "integer":
        if isinstance(raw_val, bool) or not isinstance(raw_val, int):
            raise UnsupportedModuleCombinationError(
                f"parameter {param_name} for {identity} must be an integer, got {raw_val!r}"
            )
    elif expected_type == "string":
        if not isinstance(raw_val, str):
            raise UnsupportedModuleCombinationError(
                f"parameter {param_name} for {identity} must be a string, got {raw_val!r}"
            )
    elif expected_type == "array":
        if not isinstance(raw_val, (list, tuple)):
            raise UnsupportedModuleCombinationError(
                f"parameter {param_name} for {identity} must be an array, got {raw_val!r}"
            )


def _validate_selection(role: str, selection: ModuleSelection) -> None:
    entry = REGISTRY_V1.get(selection.identity)
    if entry is None:
        raise UnsupportedModuleCombinationError(f"unsupported module identity: {selection.identity}")
    if entry.role != role:
        raise UnsupportedModuleCombinationError(
            f"module {selection.identity} is registered for role {entry.role}, not {role}"
        )
    if not entry.available:
        raise DependencyUnavailableError(f"dependency unavailable for module: {selection.identity}")
    unknown = set(selection.parameters) - set(entry.parameter_schema)
    if unknown:
        raise UnsupportedModuleCombinationError(f"unsupported parameters for {selection.identity}: {sorted(unknown)}")
    for param_name, raw_val in selection.parameters.items():
        _validate_parameter_type(selection.identity, param_name, raw_val, entry.parameter_schema[param_name])


def _validate_current_strategy_deduplication(modules: Mapping[str, ModuleSelection]) -> None:
    """Validate exclusive current strategy contract (spec L105, VR-09)."""
    if "load_model" in modules:
        lm_params = modules["load_model"].parameters
        c_strat = lm_params.get("current_strategy")
        has_crd = lm_params.get("current_relative_damping", False)
        has_ecl = lm_params.get("external_current_load", False)

        if has_crd and has_ecl:
            raise UnsupportedModuleCombinationError(
                "current_relative_damping and external_current_load are mutually exclusive (de-duplication VR-09/L105)"
            )
        if c_strat is not None:
            if str(c_strat) in ("both", "duplicate", "all"):
                raise UnsupportedModuleCombinationError(
                    f"unsupported current_strategy '{c_strat}': current_relative_damping and "
                    "external_current_load are mutually exclusive"
                )
            if str(c_strat) not in ("none", "current_relative_damping", "external_current_load"):
                raise UnsupportedModuleCombinationError(f"unknown current_strategy: {c_strat}")
            if (str(c_strat) == "current_relative_damping" and has_ecl) or (
                str(c_strat) == "external_current_load" and has_crd
            ):
                raise UnsupportedModuleCombinationError(
                    "current_relative_damping and external_current_load are mutually exclusive"
                )

    if "plant" in modules and "load_model" in modules:
        plant_params = modules["plant"].parameters
        lm_params = modules["load_model"].parameters
        plant_crd = plant_params.get("current_relative_damping", False)
        lm_ecl = lm_params.get("current_strategy") == "external_current_load" or lm_params.get(
            "external_current_load", False
        )
        if plant_crd and lm_ecl:
            raise UnsupportedModuleCombinationError(
                "cannot combine plant current_relative_damping with load_model external_current_load (VR-09/L105)"
            )


def _validate_wave_mode(modules: Mapping[str, ModuleSelection]) -> None:
    """Validate explicit wave load mode (VR-09, VR-10, spec L106)."""
    if "load_model" in modules:
        lm_params = modules["load_model"].parameters
        wave_mode = lm_params.get("wave_mode")
        if wave_mode is not None:
            if not isinstance(wave_mode, str):
                raise UnsupportedModuleCombinationError(
                    f"parameter wave_mode for load_model must be a string, got {type(wave_mode).__name__}"
                )
            valid_modes = {"off", "first_order", "mean_drift", "both"}
            if wave_mode.lower() not in valid_modes:
                raise UnsupportedModuleCombinationError(
                    f"unknown wave_mode: {wave_mode} (must be one of {sorted(valid_modes)})"
                )


def normalize_ship_modules(config: Mapping[str, Any]) -> ShipModulesConfig:
    """Apply defaults, preset, then controlled overrides and validate registry tuple."""
    source = json.loads(json.dumps(config))
    unknown_top = set(source) - {"preset", "overrides", "modules"}
    if unknown_top:
        raise UnsupportedModuleCombinationError(f"unknown ship_modules keys: {sorted(unknown_top)}")
    preset = str(source.get("preset", "legacy_equivalent"))
    if preset not in _PRESETS:
        raise UnsupportedModuleCombinationError(f"unsupported preset: {preset}")
    normalized = _deep_merge({}, _PRESETS[preset])
    overrides = dict(source.get("overrides", {}))
    if set(overrides) - {"scheduler"}:
        raise UnsupportedModuleCombinationError("overrides may contain only scheduler")
    if set(overrides.get("scheduler", {})) - set(_PRESETS[preset]["scheduler"]):
        raise UnsupportedModuleCombinationError("unknown scheduler override keys")
    normalized = _deep_merge(normalized, overrides)
    raw_modules = source.get("modules", {})
    required_roles = {"plant", "guidance", "controller"}
    allowed_roles = {"plant", "guidance", "controller", "environment", "load_model"}
    if not (required_roles.issubset(raw_modules) and set(raw_modules).issubset(allowed_roles)):
        raise UnsupportedModuleCombinationError(
            "modules must select plant, guidance, and controller (optional: environment, load_model)"
        )
    modules = {}
    for role, raw in raw_modules.items():
        unknown_selection = set(raw) - {"identity", "parameters"}
        if unknown_selection:
            raise UnsupportedModuleCombinationError(f"unknown selection keys for {role}: {sorted(unknown_selection)}")
        if "identity" not in raw:
            raise UnsupportedModuleCombinationError(f"missing module identity for {role}")
        modules[role] = ModuleSelection(str(raw["identity"]), raw.get("parameters", {}))
    for role, selection in modules.items():
        _validate_selection(role, selection)

    _validate_current_strategy_deduplication(modules)
    _validate_wave_mode(modules)

    scheduler = normalized["scheduler"]
    if any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in scheduler.values()):
        raise UnsupportedModuleCombinationError("scheduler periods must be positive integer ticks")
    canonical = {
        "preset": preset,
        "modules": {
            role: {"identity": value.identity, "parameters": _deep_thaw(value.parameters)} for role, value in modules.items()
        },
        "scheduler": scheduler,
    }
    config_hash = hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return ShipModulesConfig(preset, modules, scheduler, config_hash, source)
