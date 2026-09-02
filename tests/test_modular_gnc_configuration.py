from __future__ import annotations

import builtins
from typing import Any

import pytest

from colav_simulator.core import ship
from colav_simulator.modular_gnc.configuration import (
    REGISTRY_V1,
    CapabilityMismatchError,
    DependencyUnavailableError,
    RegistryEntry,
    UnsupportedModuleCombinationError,
    normalize_ship_modules,
)


def _modular_config() -> dict:
    return {
        "preset": "legacy_equivalent",
        "overrides": {"scheduler": {"controller_period_ticks": 5}},
        "modules": {
            "plant": {"identity": "pass_through_plant", "parameters": {}},
            "guidance": {"identity": "pass_through_guidance", "parameters": {}},
            "controller": {"identity": "pass_through_controller", "parameters": {}},
        },
    }


def test_legacy_config_does_not_import_modular_package(monkeypatch: pytest.MonkeyPatch) -> None:
    original_import = builtins.__import__

    def guarded_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name.startswith("colav_simulator.modular_gnc"):
            raise AssertionError("legacy config imported modular package")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    config = ship.Config.from_dict({"id": 1, "guidance": {"los": {}}})

    assert config.ship_modules is None
    assert isinstance(ship.build_ship(config), ship.Ship)


def test_ship_modules_parse_normalize_hash_and_round_trip() -> None:
    config_dict = {
        "id": 4,
        "mmsi": 44,
        "guidance": {"los": {}},
        "ship_modules": _modular_config(),
    }

    config = ship.Config.from_dict(config_dict)
    normalized = config.ship_modules

    assert normalized is not None
    assert normalized.preset == "legacy_equivalent"
    assert normalized.config_hash == normalized.with_overrides({}).config_hash
    assert config.to_dict()["ship_modules"] == config_dict["ship_modules"]


def test_normalized_config_is_isolated_from_nested_source_mutation() -> None:
    source = _modular_config()
    normalized = normalize_ship_modules(source)
    expected = normalized.to_dict()
    expected_hash = normalized.config_hash

    source["overrides"]["scheduler"]["controller_period_ticks"] = 99
    source["modules"]["plant"]["parameters"]["nested"] = ["mutated"]

    assert normalized.to_dict() == expected
    assert normalized.config_hash == expected_hash


def test_normalized_config_nested_data_cannot_stale_hash_or_round_trip() -> None:
    normalized = normalize_ship_modules(_modular_config())
    expected = normalized.to_dict()
    expected_hash = normalized.config_hash

    with pytest.raises(TypeError):
        normalized.source["overrides"]["scheduler"]["controller_period_ticks"] = 99
    with pytest.raises(TypeError):
        normalized.source["modules"]["plant"]["parameters"]["nested"] = [1, 2]
    with pytest.raises(TypeError):
        normalized.modules["plant"].parameters["nested"] = {"values": [1, 2]}

    exported = normalized.to_dict()
    exported["overrides"]["scheduler"]["controller_period_ticks"] = 99

    assert normalized.to_dict() == expected
    assert normalized.config_hash == expected_hash


def test_scheduler_periods_reject_bool_during_normalization() -> None:
    for period in ("plant_period_ticks", "guidance_period_ticks", "controller_period_ticks"):
        config = _modular_config()
        config["overrides"]["scheduler"][period] = True

        with pytest.raises(UnsupportedModuleCombinationError, match="positive integer ticks"):
            normalize_ship_modules(config)


def test_configuration_rejects_unknown_keys_and_wrong_module_roles() -> None:
    typo = _modular_config()
    typo["overides"] = typo.pop("overrides")
    with pytest.raises(UnsupportedModuleCombinationError, match="unknown ship_modules keys"):
        normalize_ship_modules(typo)

    bad_module_key = _modular_config()
    bad_module_key["modules"]["plant"]["identitty"] = bad_module_key["modules"]["plant"].pop("identity")
    with pytest.raises(UnsupportedModuleCombinationError, match="unknown selection keys"):
        normalize_ship_modules(bad_module_key)

    wrong_role = _modular_config()
    wrong_role["modules"]["plant"]["identity"] = "pass_through_controller"
    with pytest.raises(UnsupportedModuleCombinationError, match="registered for role controller"):
        normalize_ship_modules(wrong_role)


def test_registry_rejects_unsupported_tuple_separately_from_dependency_unavailable() -> None:
    unsupported = _modular_config()
    unsupported["modules"]["plant"]["identity"] = "missing_plant"
    with pytest.raises(UnsupportedModuleCombinationError):
        normalize_ship_modules(unsupported)

    unavailable = _modular_config()
    unavailable["modules"]["controller"]["identity"] = "optional_native_controller"
    with pytest.raises(DependencyUnavailableError):
        normalize_ship_modules(unavailable)


@pytest.mark.parametrize("bad_val", ["yes", "0", 0, 1, None])
def test_configuration_rejects_lossy_coercion_for_booleans(bad_val: Any) -> None:
    """Validate that booleans in load_model parameters strictly reject strings/ints/None."""
    cfg = _modular_config()
    cfg["modules"]["load_model"] = {
        "identity": "standard_environmental_load",
        "parameters": {"enable_wind": bad_val},
    }
    with pytest.raises(UnsupportedModuleCombinationError, match="must be an exact boolean"):
        normalize_ship_modules(cfg)


@pytest.mark.parametrize("bad_num", ["44.1", float("nan"), float("inf"), float("-inf")])
def test_configuration_rejects_invalid_numeric_parameters(bad_num: Any) -> None:
    """Validate that numeric fields reject strings and non-finite values."""
    cfg = _modular_config()
    cfg["modules"]["load_model"] = {
        "identity": "standard_environmental_load",
        "parameters": {"length_between_perpendiculars_m": bad_num},
    }
    with pytest.raises(UnsupportedModuleCombinationError, match="must be a finite number"):
        normalize_ship_modules(cfg)


def test_environment_module_selection_normalization_and_validation() -> None:
    cfg = _modular_config()
    cfg["modules"]["environment"] = {
        "identity": "analytic_environment_field",
        "parameters": {
            "wind_velocity_ne": [3.0, 4.0],
            "wave_significant_height_m": 1.2,
            "wave_peak_period_s": 6.5,
        },
    }
    normalized = normalize_ship_modules(cfg)
    assert "environment" in normalized.modules
    assert normalized.modules["environment"].identity == "analytic_environment_field"
    assert normalized.modules["environment"].parameters["wind_velocity_ne"] == (3.0, 4.0)

    # Unknown environment parameter rejected
    bad_param_cfg = _modular_config()
    bad_param_cfg["modules"]["environment"] = {
        "identity": "analytic_environment_field",
        "parameters": {"unknown_field": 123},
    }
    with pytest.raises(UnsupportedModuleCombinationError, match="unsupported parameters"):
        normalize_ship_modules(bad_param_cfg)

    # Role mismatch for environment rejected
    role_mismatch_cfg = _modular_config()
    role_mismatch_cfg["modules"]["environment"] = {
        "identity": "pass_through_plant",
        "parameters": {},
    }
    with pytest.raises(UnsupportedModuleCombinationError, match="registered for role plant, not environment"):
        normalize_ship_modules(role_mismatch_cfg)


def test_registry_parameter_schema_nested_is_deep_frozen() -> None:
    entry = REGISTRY_V1["analytic_environment_field"]
    with pytest.raises(TypeError):
        entry.parameter_schema["wind_velocity_ne"]["type"] = "string"


def test_environment_parameters_change_config_hash() -> None:
    cfg1 = _modular_config()
    cfg1["modules"]["environment"] = {
        "identity": "analytic_environment_field",
        "parameters": {"wind_velocity_ne": [3.0, 4.0]},
    }
    cfg2 = _modular_config()
    cfg2["modules"]["environment"] = {
        "identity": "analytic_environment_field",
        "parameters": {"wind_velocity_ne": [3.0, 4.1]},
    }

    norm1 = normalize_ship_modules(cfg1)
    norm2 = normalize_ship_modules(cfg2)
    assert norm1.config_hash != norm2.config_hash


def test_wave_mode_configuration_valid_modes_and_hash() -> None:
    # 1. Mode off (default and explicit): no wave asset IDs
    cfg_default = _modular_config()
    cfg_default["modules"]["load_model"] = {
        "identity": "standard_environmental_load",
        "parameters": {},
    }
    norm_default = normalize_ship_modules(cfg_default)
    assert "wave_mode" not in norm_default.modules["load_model"].parameters

    cfg_off = _modular_config()
    cfg_off["modules"]["load_model"] = {
        "identity": "standard_environmental_load",
        "parameters": {"wave_mode": "off"},
    }
    norm_off = normalize_ship_modules(cfg_off)
    assert norm_off.modules["load_model"].parameters["wave_mode"] == "off"

    # 2. Mode first_order: requires wave_first_order_asset_id
    cfg_1st = _modular_config()
    cfg_1st["modules"]["load_model"] = {
        "identity": "standard_environmental_load",
        "parameters": {
            "wave_mode": "first_order",
            "wave_first_order_asset_id": "default_inferred_wave_response_v1",
        },
    }
    norm_1st = normalize_ship_modules(cfg_1st)
    assert norm_1st.modules["load_model"].parameters["wave_first_order_asset_id"] == "default_inferred_wave_response_v1"

    # 3. Mode mean_drift: requires wave_mean_drift_asset_id
    cfg_drift = _modular_config()
    cfg_drift["modules"]["load_model"] = {
        "identity": "standard_environmental_load",
        "parameters": {
            "wave_mode": "mean_drift",
            "wave_mean_drift_asset_id": "default_inferred_diagonal_drift_v1",
        },
    }
    norm_drift = normalize_ship_modules(cfg_drift)
    assert norm_drift.modules["load_model"].parameters["wave_mean_drift_asset_id"] == "default_inferred_diagonal_drift_v1"

    # 4. Mode both: requires both asset IDs
    cfg_both = _modular_config()
    cfg_both["modules"]["load_model"] = {
        "identity": "standard_environmental_load",
        "parameters": {
            "wave_mode": "both",
            "wave_first_order_asset_id": "default_inferred_wave_response_v1",
            "wave_mean_drift_asset_id": "default_inferred_diagonal_drift_v1",
        },
    }
    norm_both = normalize_ship_modules(cfg_both)
    assert norm_both.modules["load_model"].parameters["wave_mode"] == "both"

    # Different wave mode / asset parameters change config hash
    assert norm_off.config_hash != norm_1st.config_hash
    assert norm_1st.config_hash != norm_drift.config_hash
    assert norm_drift.config_hash != norm_both.config_hash


def test_wave_mode_configuration_invalid_modes_and_assets() -> None:
    # 5. Invalid wave mode rejected
    bad_cfg = _modular_config()
    bad_cfg["modules"]["load_model"] = {
        "identity": "standard_environmental_load",
        "parameters": {"wave_mode": "invalid_wave_mode"},
    }
    with pytest.raises(UnsupportedModuleCombinationError, match="unknown wave_mode"):
        normalize_ship_modules(bad_cfg)

    # 6. Mode off rejecting irrelevant asset IDs
    bad_off = _modular_config()
    bad_off["modules"]["load_model"] = {
        "identity": "standard_environmental_load",
        "parameters": {"wave_mode": "off", "wave_first_order_asset_id": "default_inferred_wave_response_v1"},
    }
    with pytest.raises(UnsupportedModuleCombinationError, match="not allowed when wave_mode is 'off'"):
        normalize_ship_modules(bad_off)

    # 7. Mode first_order missing first_order asset ID or supplying drift asset ID
    bad_1st_missing = _modular_config()
    bad_1st_missing["modules"]["load_model"] = {
        "identity": "standard_environmental_load",
        "parameters": {"wave_mode": "first_order"},
    }
    with pytest.raises(UnsupportedModuleCombinationError, match="wave_first_order_asset_id is required"):
        normalize_ship_modules(bad_1st_missing)

    bad_1st_extra = _modular_config()
    bad_1st_extra["modules"]["load_model"] = {
        "identity": "standard_environmental_load",
        "parameters": {
            "wave_mode": "first_order",
            "wave_first_order_asset_id": "default_inferred_wave_response_v1",
            "wave_mean_drift_asset_id": "default_inferred_diagonal_drift_v1",
        },
    }
    with pytest.raises(UnsupportedModuleCombinationError, match="wave_mean_drift_asset_id is not allowed"):
        normalize_ship_modules(bad_1st_extra)

    # 8. Mode mean_drift missing drift asset ID or supplying first_order asset ID
    bad_drift_missing = _modular_config()
    bad_drift_missing["modules"]["load_model"] = {
        "identity": "standard_environmental_load",
        "parameters": {"wave_mode": "mean_drift"},
    }
    with pytest.raises(UnsupportedModuleCombinationError, match="wave_mean_drift_asset_id is required"):
        normalize_ship_modules(bad_drift_missing)

    bad_drift_extra = _modular_config()
    bad_drift_extra["modules"]["load_model"] = {
        "identity": "standard_environmental_load",
        "parameters": {
            "wave_mode": "mean_drift",
            "wave_first_order_asset_id": "default_inferred_wave_response_v1",
            "wave_mean_drift_asset_id": "default_inferred_diagonal_drift_v1",
        },
    }
    with pytest.raises(UnsupportedModuleCombinationError, match="wave_first_order_asset_id is not allowed"):
        normalize_ship_modules(bad_drift_extra)

    # 9. Mode both missing one asset ID
    bad_both_missing = _modular_config()
    bad_both_missing["modules"]["load_model"] = {
        "identity": "standard_environmental_load",
        "parameters": {
            "wave_mode": "both",
            "wave_first_order_asset_id": "default_inferred_wave_response_v1",
        },
    }
    match_msg = "both wave_first_order_asset_id and wave_mean_drift_asset_id are required"
    with pytest.raises(UnsupportedModuleCombinationError, match=match_msg):
        normalize_ship_modules(bad_both_missing)

    # 10. Unknown asset ID rejected
    bad_unknown_id = _modular_config()
    bad_unknown_id["modules"]["load_model"] = {
        "identity": "standard_environmental_load",
        "parameters": {
            "wave_mode": "first_order",
            "wave_first_order_asset_id": "unknown_rao_asset_v999",
        },
    }
    with pytest.raises(UnsupportedModuleCombinationError, match="unknown wave_first_order_asset_id"):
        normalize_ship_modules(bad_unknown_id)


def _plant_4dof_params() -> dict[str, float]:
    return {
        "mass_kg": 1.6e7,
        "i_x_kgm2": 1.5e9,
        "i_z_kgm2": 3.0e10,
        "x_g_m": 0.0,
        "z_g_m": 0.0,
        "x_dot_u_kg": -5.0e6,
        "y_dot_v_kg": -3.5e7,
        "k_dot_p_kgm2": -5.0e8,
        "n_dot_r_kgm2": -2.0e10,
        "y_dot_r_kgm": 1.0e6,
        "n_dot_v_kgm": 1.0e6,
        "d_u": 5.0e4,
        "d_uu": 2.0e5,
        "d_v": 3.0e5,
        "d_vv": 1.5e6,
        "d_p": 2.0e7,
        "d_pp": 5.0e7,
        "d_r": 8.0e7,
        "d_rr": 2.5e9,
        "restoring_k_phi": 3.0e8,
    }


def _plant_3dof_params() -> dict[str, float]:
    return {
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


def test_input_domain_capability_marine_pid_rejects_kinematic_plant() -> None:
    """Validate that marine_pid (force output) is rejected when paired with kinematic plant (RA-13)."""
    cfg = {
        "preset": "legacy_equivalent",
        "modules": {
            "plant": {"identity": "pass_through_plant", "parameters": {}},
            "guidance": {"identity": "pass_through_guidance", "parameters": {}},
            "controller": {"identity": "marine_pid", "parameters": {}},
        },
    }
    with pytest.raises(CapabilityMismatchError, match="controller marine_pid produces GENERALIZED_FORCE"):
        normalize_ship_modules(cfg)


def _marine_pid_params() -> dict[str, Any]:
    return {
        "kp": [1000.0, 500.0, 2000.0],
        "ki": [100.0, 50.0, 200.0],
        "kd": [200.0, 100.0, 400.0],
        "tau_d": [0.1, 0.1, 0.1],
        "antiwindup_gain": [1.0, 1.0, 1.0],
        "min_output": [-10000.0, -5000.0, -20000.0],
        "max_output": [10000.0, 5000.0, 20000.0],
        "feedforward_gain": [0.0, 0.0, 0.0],
        "allow_ideal_passthrough": True,
    }


def test_input_domain_capability_marine_pid_with_force_plants_passes_capability_check() -> None:
    """Validate that marine_pid tuple with force plants passes capability check and normalizes successfully."""
    for plant_id, params in (
        ("generic_3dof_plant", _plant_3dof_params()),
        ("generic_roll_4dof_plant", _plant_4dof_params()),
    ):
        cfg = {
            "preset": "legacy_equivalent",
            "overrides": {"scheduler": {"plant_period_ticks": 1}},
            "modules": {
                "plant": {"identity": plant_id, "parameters": params},
                "guidance": {"identity": "pass_through_guidance", "parameters": {}},
                "controller": {"identity": "marine_pid", "parameters": _marine_pid_params()},
            },
        }
        normalized = normalize_ship_modules(cfg)
        assert normalized.modules["controller"].identity == "marine_pid"
        assert normalized.modules["plant"].identity == plant_id


def test_marine_pid_configuration_strict_validation_rejects_bad_params() -> None:
    """Validate that invalid parameters in marine_pid raise UnsupportedModuleCombinationError."""
    # Negative gain
    bad_params = _marine_pid_params()
    bad_params["kp"] = [-1.0, 1.0, 1.0]
    cfg = {
        "preset": "legacy_equivalent",
        "overrides": {"scheduler": {"plant_period_ticks": 1}},
        "modules": {
            "plant": {"identity": "generic_3dof_plant", "parameters": _plant_3dof_params()},
            "guidance": {"identity": "pass_through_guidance", "parameters": {}},
            "controller": {"identity": "marine_pid", "parameters": bad_params},
        },
    }
    with pytest.raises(UnsupportedModuleCombinationError, match="invalid marine_pid parameters"):
        normalize_ship_modules(cfg)

    # Inverted limits
    bad_params2 = _marine_pid_params()
    bad_params2["min_output"] = [1000.0, 0.0, 0.0]
    bad_params2["max_output"] = [500.0, 0.0, 0.0]
    cfg["modules"]["controller"]["parameters"] = bad_params2
    with pytest.raises(UnsupportedModuleCombinationError, match="cannot exceed max_output"):
        normalize_ship_modules(cfg)


def test_input_domain_capability_compatibility_matrix(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test full compatibility matrix between plant input semantics and controller output capabilities."""
    custom_registry = dict(REGISTRY_V1)
    custom_registry["fake_force_controller"] = RegistryEntry(
        "fake_force_controller",
        "controller",
        "1.0.0",
        "controller.v1",
        frozenset({"TRANSIT", "GENERALIZED_FORCE"}),
        {},
        available=True,
    )
    custom_registry["fake_kinematic_controller"] = RegistryEntry(
        "fake_kinematic_controller",
        "controller",
        "1.0.0",
        "controller.v1",
        frozenset({"TRANSIT", "KINEMATIC_REFERENCE"}),
        {},
        available=True,
    )
    custom_registry["fake_unknown_controller"] = RegistryEntry(
        "fake_unknown_controller",
        "controller",
        "1.0.0",
        "controller.v1",
        frozenset({"CUSTOM_UNKNOWN_CAP"}),
        {},
        available=True,
    )
    monkeypatch.setattr("colav_simulator.modular_gnc.configuration.REGISTRY_V1", custom_registry)

    # 1. Force controller with kinematic plant -> REJECT
    cfg_force_kinematic = {
        "preset": "legacy_equivalent",
        "modules": {
            "plant": {"identity": "pass_through_plant", "parameters": {}},
            "guidance": {"identity": "pass_through_guidance", "parameters": {}},
            "controller": {"identity": "fake_force_controller", "parameters": {}},
        },
    }
    with pytest.raises(CapabilityMismatchError, match="produces GENERALIZED_FORCE"):
        normalize_ship_modules(cfg_force_kinematic)

    # 2. Force controller with generic 3DOF plant -> ACCEPT
    cfg_force_3dof = {
        "preset": "legacy_equivalent",
        "overrides": {"scheduler": {"plant_period_ticks": 1}},
        "modules": {
            "plant": {"identity": "generic_3dof_plant", "parameters": _plant_3dof_params()},
            "guidance": {"identity": "pass_through_guidance", "parameters": {}},
            "controller": {"identity": "fake_force_controller", "parameters": {}},
        },
    }
    norm_3dof = normalize_ship_modules(cfg_force_3dof)
    assert norm_3dof.modules["controller"].identity == "fake_force_controller"

    # 3. Force controller with generic roll 4DOF plant -> ACCEPT
    cfg_force_4dof = {
        "preset": "legacy_equivalent",
        "overrides": {"scheduler": {"plant_period_ticks": 1}},
        "modules": {
            "plant": {"identity": "generic_roll_4dof_plant", "parameters": _plant_4dof_params()},
            "guidance": {"identity": "pass_through_guidance", "parameters": {}},
            "controller": {"identity": "fake_force_controller", "parameters": {}},
        },
    }
    norm_4dof = normalize_ship_modules(cfg_force_4dof)
    assert norm_4dof.modules["controller"].identity == "fake_force_controller"

    # 4. Kinematic controller with kinematic plant -> ACCEPT
    cfg_kin_kin = {
        "preset": "legacy_equivalent",
        "modules": {
            "plant": {"identity": "pass_through_plant", "parameters": {}},
            "guidance": {"identity": "pass_through_guidance", "parameters": {}},
            "controller": {"identity": "fake_kinematic_controller", "parameters": {}},
        },
    }
    norm_kin = normalize_ship_modules(cfg_kin_kin)
    assert norm_kin.modules["controller"].identity == "fake_kinematic_controller"

    # 5. Kinematic controller with force plant -> REJECT
    cfg_kin_force = {
        "preset": "legacy_equivalent",
        "overrides": {"scheduler": {"plant_period_ticks": 1}},
        "modules": {
            "plant": {"identity": "generic_3dof_plant", "parameters": _plant_3dof_params()},
            "guidance": {"identity": "pass_through_guidance", "parameters": {}},
            "controller": {"identity": "fake_kinematic_controller", "parameters": {}},
        },
    }
    with pytest.raises(CapabilityMismatchError, match="produces kinematic reference"):
        normalize_ship_modules(cfg_kin_force)

    # 6. Unknown controller capability -> REJECT
    cfg_unknown = {
        "preset": "legacy_equivalent",
        "modules": {
            "plant": {"identity": "pass_through_plant", "parameters": {}},
            "guidance": {"identity": "pass_through_guidance", "parameters": {}},
            "controller": {"identity": "fake_unknown_controller", "parameters": {}},
        },
    }
    with pytest.raises(CapabilityMismatchError, match="missing required output semantics capability"):
        normalize_ship_modules(cfg_unknown)


def test_generic_roll_4dof_plant_configuration_normalization_and_hash() -> None:
    cfg = {
        "preset": "legacy_equivalent",
        "overrides": {"scheduler": {"plant_period_ticks": 1}},
        "modules": {
            "plant": {"identity": "generic_roll_4dof_plant", "parameters": _plant_4dof_params()},
            "guidance": {"identity": "pass_through_guidance", "parameters": {}},
            "controller": {"identity": "pass_through_controller", "parameters": {}},
        },
    }
    norm = normalize_ship_modules(cfg)
    assert norm.modules["plant"].identity == "generic_roll_4dof_plant"
    assert norm.modules["plant"].parameters["restoring_k_phi"] == 3.0e8

    # Changing restoring_k_phi alters config hash
    cfg2 = dict(cfg)
    cfg2_params = dict(_plant_4dof_params())
    cfg2_params["restoring_k_phi"] = 3.5e8
    cfg2["modules"] = {
        "plant": {"identity": "generic_roll_4dof_plant", "parameters": cfg2_params},
        "guidance": {"identity": "pass_through_guidance", "parameters": {}},
        "controller": {"identity": "pass_through_controller", "parameters": {}},
    }
    norm2 = normalize_ship_modules(cfg2)
    assert norm.config_hash != norm2.config_hash


def test_generic_roll_4dof_plant_requires_base_cadence() -> None:
    cfg = {
        "preset": "legacy_equivalent",
        "overrides": {"scheduler": {"plant_period_ticks": 2}},
        "modules": {
            "plant": {"identity": "generic_roll_4dof_plant", "parameters": _plant_4dof_params()},
            "guidance": {"identity": "pass_through_guidance", "parameters": {}},
            "controller": {"identity": "pass_through_controller", "parameters": {}},
        },
    }
    with pytest.raises(UnsupportedModuleCombinationError, match="requires plant_period_ticks == 1"):
        normalize_ship_modules(cfg)
