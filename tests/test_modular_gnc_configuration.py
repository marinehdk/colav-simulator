from __future__ import annotations

import builtins
from typing import Any

import pytest

from colav_simulator.core import ship
from colav_simulator.modular_gnc.configuration import (
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
