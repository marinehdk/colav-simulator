"""Factory dt/seed threading into ModularShipStack.from_config (Config step 04).

The stack clock must equal the simulation clock: the scenario dt_sim and the
scenario seed reach ``from_config`` through ``build_ship``.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from colav_simulator.common import paths
from colav_simulator.core import ship
from colav_simulator.modular_gnc.adapter import ModularShipAdapter
from colav_simulator.modular_gnc.stack import ModularShipStack
from colav_simulator.scenario_generator import ScenarioGenerator


def _ship_config() -> ship.Config:
    return ship.Config.from_dict(
        {
            "id": 0,
            "mmsi": 1,
            "csog_state": [0.0, 0.0, 3.0, 0.0],
            "waypoints": [[0.0, 100.0], [0.0, 0.0]],
            "speed_plan": [3.0, 3.0],
            "guidance": {"los": {}},
            "ship_modules": {
                "preset": "legacy_equivalent",
                "modules": {
                    "plant": {"identity": "pass_through_plant", "parameters": {}},
                    "guidance": {"identity": "pass_through_guidance", "parameters": {}},
                    "controller": {"identity": "pass_through_controller", "parameters": {}},
                },
            },
        }
    )


class _FromConfigSpy:
    """Capture from_config calls while delegating to the real constructor."""

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self._real = ModularShipStack.from_config

    def __call__(self, config, episode_seed: int = 0, dt_s: float = 0.1) -> ModularShipStack:
        self.calls.append({"config": config, "episode_seed": episode_seed, "dt_s": dt_s})
        return self._real(config, episode_seed=episode_seed, dt_s=dt_s)

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(ModularShipStack, "from_config", classmethod(lambda cls, *args, **kwargs: self(*args, **kwargs)))


def test_build_ship_forwards_dt_and_seed_to_from_config(monkeypatch: pytest.MonkeyPatch) -> None:
    spy = _FromConfigSpy()
    spy.install(monkeypatch)

    adapter = ship.build_ship(_ship_config(), dt_s=0.25, episode_seed=11)

    assert isinstance(adapter, ModularShipAdapter)
    assert spy.calls == [{"config": adapter.modular_stack_config, "episode_seed": 11, "dt_s": 0.25}]


def test_build_ship_without_kwargs_keeps_from_config_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    spy = _FromConfigSpy()
    spy.install(monkeypatch)

    ship.build_ship(_ship_config())

    assert spy.calls[0]["episode_seed"] == 0
    assert spy.calls[0]["dt_s"] == 0.1


def test_scenario_generator_load_episode_passes_dt_and_seed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scenario = {
        "name": "modular_clock_scenario",
        "save_scenario": False,
        "t_start": 0.0,
        "t_end": 1.0,
        "dt_sim": 0.2,
        "type": "HO",
        "utm_zone": 33,
        "map_data_files": [str(paths.enc_data / "Rogaland_utm33.gdb")],
        "map_size": [1000.0, 1000.0],
        "map_origin_enu": [0.0, 0.0],
        "new_load_of_map_data": False,
        "n_random_ships": 0,
        "ship_list": [],
    }
    scenario["ship_list"].append(
        {
            "id": 0,
            "mmsi": 1,
            "csog_state": [0.0, 0.0, 3.0, 0.0],
            "waypoints": [[0.0, 100.0], [0.0, 0.0]],
            "speed_plan": [3.0, 3.0],
            "guidance": {
                "los": {
                    "pass_angle_threshold": 90.0,
                    "R_a": 25.0,
                    "K_p": 0.02,
                    "K_i": 0.0001,
                    "max_cross_track_error_int": 100.0,
                    "cross_track_error_int_threshold": 50.0,
                }
            },
            "ship_modules": {
                "preset": "legacy_equivalent",
                "modules": {
                    "plant": {"identity": "pass_through_plant", "parameters": {}},
                    "guidance": {"identity": "pass_through_guidance", "parameters": {}},
                    "controller": {"identity": "pass_through_controller", "parameters": {}},
                },
            },
        }
    )
    path = tmp_path / "scenario.yaml"
    path.write_text(yaml.safe_dump(scenario), encoding="utf-8")

    spy = _FromConfigSpy()
    spy.install(monkeypatch)
    generator = ScenarioGenerator(config_file=None, seed=4242)
    generator.load_episode(path)

    assert spy.calls, "load_episode must build the modular ownship through from_config"
    assert spy.calls[0]["dt_s"] == 0.2
    assert spy.calls[0]["episode_seed"] == 4242


def test_scenario_generator_partially_defined_ships_pass_dt_and_seed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spy = _FromConfigSpy()
    spy.install(monkeypatch)
    generator = ScenarioGenerator(config_file=None, seed=77)
    scenario_config = SimpleNamespace(n_random_ships=0, ship_list=[_ship_config()], dt_sim=0.4)

    ship_list, _ = generator._create_partially_defined_ships(scenario_config)

    assert isinstance(ship_list[0], ModularShipAdapter)
    assert spy.calls[0]["dt_s"] == 0.4
    assert spy.calls[0]["episode_seed"] == 77
