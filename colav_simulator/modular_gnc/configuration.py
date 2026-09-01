"""Strict opt-in modular ship configuration and minimal registry v1."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from colav_simulator.modular_gnc.contracts import WaveLoadMode


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


class CapabilityMismatchError(UnsupportedModuleCombinationError):
    """Raised when plant input semantics and controller output capabilities are incompatible (RA-13, TS-17)."""


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
            frozenset({"PLANAR_3DOF", "KINEMATIC_REFERENCE", "REFERENCE_CHI_U"}),
            {"current_relative_damping": {"type": "boolean"}},
        ),
        "generic_3dof_plant": RegistryEntry(
            "generic_3dof_plant",
            "plant",
            "1.0.0",
            "plant.v1",
            frozenset({"PLANAR_3DOF", "GENERALIZED_FORCE"}),
            {
                "mass_kg": {"type": "number"},
                "i_z_kgm2": {"type": "number"},
                "x_g_m": {"type": "number"},
                "x_dot_u_kg": {"type": "number"},
                "y_dot_v_kg": {"type": "number"},
                "n_dot_r_kgm2": {"type": "number"},
                "y_dot_r_kgm": {"type": "number"},
                "n_dot_v_kgm": {"type": "number"},
                "d_u": {"type": "number"},
                "d_uu": {"type": "number"},
                "d_v": {"type": "number"},
                "d_vv": {"type": "number"},
                "d_r": {"type": "number"},
                "d_rr": {"type": "number"},
                "d_vr": {"type": "number"},
                "d_rv": {"type": "number"},
                "restoring_k_n": {"type": "number"},
                "restoring_k_e": {"type": "number"},
                "restoring_k_psi": {"type": "number"},
                "mass_symmetry_tolerance": {"type": "number"},
                "min_mass_eigenvalue": {"type": "number"},
                "damping_tolerance": {"type": "number"},
            },
        ),
        "generic_roll_4dof_plant": RegistryEntry(
            "generic_roll_4dof_plant",
            "plant",
            "1.0.0",
            "plant.v1",
            frozenset({"ROLL_4DOF", "GENERALIZED_FORCE"}),
            {
                "mass_kg": {"type": "number"},
                "i_x_kgm2": {"type": "number"},
                "i_z_kgm2": {"type": "number"},
                "x_g_m": {"type": "number"},
                "z_g_m": {"type": "number"},
                "x_dot_u_kg": {"type": "number"},
                "y_dot_v_kg": {"type": "number"},
                "k_dot_p_kgm2": {"type": "number"},
                "n_dot_r_kgm2": {"type": "number"},
                "y_dot_r_kgm": {"type": "number"},
                "n_dot_v_kgm": {"type": "number"},
                "y_dot_p_kgm": {"type": "number"},
                "k_dot_v_kgm": {"type": "number"},
                "k_dot_r_kgm2": {"type": "number"},
                "n_dot_p_kgm2": {"type": "number"},
                "d_u": {"type": "number"},
                "d_uu": {"type": "number"},
                "d_v": {"type": "number"},
                "d_vv": {"type": "number"},
                "d_p": {"type": "number"},
                "d_pp": {"type": "number"},
                "d_r": {"type": "number"},
                "d_rr": {"type": "number"},
                "d_vr": {"type": "number"},
                "d_rv": {"type": "number"},
                "d_vp": {"type": "number"},
                "d_pv": {"type": "number"},
                "d_pr": {"type": "number"},
                "d_rp": {"type": "number"},
                "restoring_k_phi": {"type": "number"},
                "restoring_k_n": {"type": "number"},
                "restoring_k_e": {"type": "number"},
                "restoring_k_psi": {"type": "number"},
                "mass_symmetry_tolerance": {"type": "number"},
                "min_mass_eigenvalue": {"type": "number"},
                "damping_tolerance": {"type": "number"},
            },
        ),
        "pass_through_guidance": RegistryEntry(
            "pass_through_guidance", "guidance", "1.0.0", "guidance.v1", frozenset({"DIRECT_REFERENCE"}), {}
        ),
        "pass_through_controller": RegistryEntry(
            "pass_through_controller",
            "controller",
            "1.0.0",
            "controller.v1",
            frozenset({"TRANSIT"}),
            {},
        ),
        "marine_pid": RegistryEntry(
            "marine_pid",
            "controller",
            "1.0.0",
            "controller.v1",
            frozenset({"TRANSIT", "GENERALIZED_FORCE"}),
            {},
            available=False,
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
                "wave_first_order_asset_id": {"type": "string"},
                "wave_mean_drift_asset_id": {"type": "string"},
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


def _validate_selection(role: str, selection: ModuleSelection, check_availability: bool = True) -> None:
    entry = REGISTRY_V1.get(selection.identity)
    if entry is None:
        raise UnsupportedModuleCombinationError(f"unsupported module identity: {selection.identity}")
    if entry.role != role:
        raise UnsupportedModuleCombinationError(
            f"module {selection.identity} is registered for role {entry.role}, not {role}"
        )
    if check_availability and not entry.available:
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


KNOWN_WAVE_FIRST_ORDER_ASSET_IDS: frozenset[str] = frozenset({"default_inferred_wave_response_v1"})
KNOWN_WAVE_MEAN_DRIFT_ASSET_IDS: frozenset[str] = frozenset({"default_inferred_diagonal_drift_v1"})


def _validate_wave_asset_ids_presence(
    wave_mode: WaveLoadMode,
    w1_id: str | None,
    wmd_id: str | None,
) -> None:
    """Validate required vs forbidden wave asset IDs per mode (VR-09, VR-10)."""
    if wave_mode == WaveLoadMode.OFF:
        if w1_id is not None or wmd_id is not None:
            raise UnsupportedModuleCombinationError(
                "wave_first_order_asset_id and wave_mean_drift_asset_id are not allowed when wave_mode is 'off'"
            )
    elif wave_mode == WaveLoadMode.FIRST_ORDER:
        if w1_id is None:
            raise UnsupportedModuleCombinationError("wave_first_order_asset_id is required when wave_mode is 'first_order'")
        if wmd_id is not None:
            raise UnsupportedModuleCombinationError(
                "wave_mean_drift_asset_id is not allowed when wave_mode is 'first_order'"
            )
    elif wave_mode == WaveLoadMode.MEAN_DRIFT:
        if wmd_id is None:
            raise UnsupportedModuleCombinationError("wave_mean_drift_asset_id is required when wave_mode is 'mean_drift'")
        if w1_id is not None:
            raise UnsupportedModuleCombinationError(
                "wave_first_order_asset_id is not allowed when wave_mode is 'mean_drift'"
            )
    elif wave_mode == WaveLoadMode.BOTH and (w1_id is None or wmd_id is None):
        raise UnsupportedModuleCombinationError(
            "both wave_first_order_asset_id and wave_mean_drift_asset_id are required when wave_mode is 'both'"
        )


def _validate_plant_controller_compatibility(modules: Mapping[str, ModuleSelection]) -> None:
    """Validate input-domain and capability compatibility between plant and controller (RA-13, TS-17)."""
    if "plant" not in modules or "controller" not in modules:
        return

    plant_entry = REGISTRY_V1.get(modules["plant"].identity)
    ctrl_entry = REGISTRY_V1.get(modules["controller"].identity)

    if plant_entry is None or ctrl_entry is None:
        return

    plant_caps = plant_entry.capabilities
    ctrl_caps = ctrl_entry.capabilities

    # 1. Plant input semantics declaration
    has_force_input = "GENERALIZED_FORCE" in plant_caps
    has_ref_input = "KINEMATIC_REFERENCE" in plant_caps or "REFERENCE_CHI_U" in plant_caps

    if not has_force_input and not has_ref_input:
        raise CapabilityMismatchError(
            f"plant {plant_entry.identity} does not declare valid input semantics "
            "(must declare GENERALIZED_FORCE or REFERENCE_CHI_U / KINEMATIC_REFERENCE)"
        )

    # 2. Controller output semantics declaration
    has_force_output = "GENERALIZED_FORCE" in ctrl_caps
    has_ref_output = "KINEMATIC_REFERENCE" in ctrl_caps or "REFERENCE_CHI_U" in ctrl_caps

    if not has_force_output and not has_ref_output and "TRANSIT" not in ctrl_caps:
        raise CapabilityMismatchError(f"controller {ctrl_entry.identity} missing required output semantics capability")

    # 3. Specific semantic incompatibility: controller produces GENERALIZED_FORCE but plant is kinematic-reference
    if has_force_output and not has_force_input:
        raise CapabilityMismatchError(
            f"incompatible module tuple: controller {ctrl_entry.identity} produces GENERALIZED_FORCE "
            f"but plant {plant_entry.identity} accepts only kinematic reference [chi_d, U_d] (RA-13)"
        )

    # 4. Controller produces pure kinematic reference but plant accepts only GENERALIZED_FORCE
    if has_ref_output and not has_ref_input and not has_force_output:
        raise CapabilityMismatchError(
            f"incompatible module tuple: controller {ctrl_entry.identity} produces kinematic reference "
            f"but plant {plant_entry.identity} accepts only GENERALIZED_FORCE (RA-13)"
        )


def _validate_wave_mode(modules: Mapping[str, ModuleSelection]) -> None:
    """Validate explicit wave load mode and required asset IDs (VR-09, VR-10, spec L106)."""
    if "load_model" not in modules:
        return
    lm_params = modules["load_model"].parameters
    wave_mode_raw = lm_params.get("wave_mode", "off")
    if not isinstance(wave_mode_raw, str):
        raise UnsupportedModuleCombinationError(
            f"parameter wave_mode for load_model must be a string, got {type(wave_mode_raw).__name__}"
        )
    valid_modes = {"off", "first_order", "mean_drift", "both"}
    if wave_mode_raw.lower() not in valid_modes:
        raise UnsupportedModuleCombinationError(f"unknown wave_mode: {wave_mode_raw} (must be one of {sorted(valid_modes)})")
    wave_mode = WaveLoadMode(wave_mode_raw.lower())

    w1_id = lm_params.get("wave_first_order_asset_id")
    wmd_id = lm_params.get("wave_mean_drift_asset_id")

    if w1_id is not None and w1_id not in KNOWN_WAVE_FIRST_ORDER_ASSET_IDS:
        raise UnsupportedModuleCombinationError(
            f"unknown wave_first_order_asset_id: {w1_id} (known: {sorted(KNOWN_WAVE_FIRST_ORDER_ASSET_IDS)})"
        )

    if wmd_id is not None and wmd_id not in KNOWN_WAVE_MEAN_DRIFT_ASSET_IDS:
        raise UnsupportedModuleCombinationError(
            f"unknown wave_mean_drift_asset_id: {wmd_id} (known: {sorted(KNOWN_WAVE_MEAN_DRIFT_ASSET_IDS)})"
        )

    _validate_wave_asset_ids_presence(wave_mode, w1_id, wmd_id)


def _parse_modules_mapping(raw_modules: Mapping[str, Any]) -> dict[str, ModuleSelection]:
    """Parse and validate structural presence of module selections."""
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
    return modules


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

    modules = _parse_modules_mapping(source.get("modules", {}))

    for role, selection in modules.items():
        _validate_selection(role, selection, check_availability=False)

    _validate_plant_controller_compatibility(modules)

    for selection in modules.values():
        entry = REGISTRY_V1[selection.identity]
        if not entry.available:
            raise DependencyUnavailableError(f"dependency unavailable for module: {selection.identity}")

    _validate_current_strategy_deduplication(modules)
    _validate_wave_mode(modules)

    scheduler = normalized["scheduler"]
    if any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in scheduler.values()):
        raise UnsupportedModuleCombinationError("scheduler periods must be positive integer ticks")

    if (
        "plant" in modules
        and modules["plant"].identity in ("generic_3dof_plant", "generic_roll_4dof_plant")
        and scheduler.get("plant_period_ticks") != 1
    ):
        plant_id = modules["plant"].identity
        raise UnsupportedModuleCombinationError(
            f"{plant_id} requires plant_period_ticks == 1 (base-clock cadence only; "
            f"got {scheduler.get('plant_period_ticks')})"
        )

    canonical = {
        "preset": preset,
        "modules": {
            role: {"identity": value.identity, "parameters": _deep_thaw(value.parameters)} for role, value in modules.items()
        },
        "scheduler": scheduler,
    }
    config_hash = hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return ShipModulesConfig(preset, modules, scheduler, config_hash, source)
