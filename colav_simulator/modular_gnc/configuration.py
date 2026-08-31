"""Strict opt-in modular ship configuration and minimal registry v1."""

from __future__ import annotations

import hashlib
import json
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
        object.__setattr__(self, "parameter_schema", MappingProxyType(dict(self.parameter_schema)))


REGISTRY_V1 = MappingProxyType(
    {
        "pass_through_plant": RegistryEntry(
            "pass_through_plant",
            "plant",
            "1.0.0",
            "plant.v1",
            frozenset({"PLANAR_3DOF", "KINEMATIC_REFERENCE"}),
            {},
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
    if set(raw_modules) != required_roles:
        raise UnsupportedModuleCombinationError("modules must select plant, guidance, and controller")
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
