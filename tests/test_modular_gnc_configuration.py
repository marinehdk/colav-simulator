from __future__ import annotations

import builtins
from typing import Any

import pytest

from colav_simulator.core import ship
from colav_simulator.modular_gnc.configuration import (
    REGISTRY_V1,
    DependencyUnavailableError,
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


def test_wave_mode_configuration_validation_and_hash() -> None:
    for mode in ("off", "first_order", "mean_drift", "both"):
        cfg = _modular_config()
        cfg["modules"]["load_model"] = {
            "identity": "standard_environmental_load",
            "parameters": {"wave_mode": mode},
        }
        norm = normalize_ship_modules(cfg)
        assert norm.modules["load_model"].parameters["wave_mode"] == mode

    # Invalid wave mode rejected
    bad_cfg = _modular_config()
    bad_cfg["modules"]["load_model"] = {
        "identity": "standard_environmental_load",
        "parameters": {"wave_mode": "invalid_wave_mode"},
    }
    with pytest.raises(UnsupportedModuleCombinationError, match="unknown wave_mode"):
        normalize_ship_modules(bad_cfg)

    # Different wave mode changes config hash
    cfg_off = _modular_config()
    cfg_off["modules"]["load_model"] = {
        "identity": "standard_environmental_load",
        "parameters": {"wave_mode": "off"},
    }
    cfg_both = _modular_config()
    cfg_both["modules"]["load_model"] = {
        "identity": "standard_environmental_load",
        "parameters": {"wave_mode": "both"},
    }
    norm_off = normalize_ship_modules(cfg_off)
    norm_both = normalize_ship_modules(cfg_both)
    assert norm_off.config_hash != norm_both.config_hash
