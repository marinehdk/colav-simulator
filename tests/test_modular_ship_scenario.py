from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from colav_simulator.common import config_parsing, paths
from colav_simulator.modular_gnc.adapter import ModularShipAdapter
from colav_simulator.scenario_config import ScenarioConfig
from colav_simulator.scenario_generator import ScenarioGenerator


def test_load_episode_selects_independent_modular_adapter_and_preserves_raw_telemetry(tmp_path: Path) -> None:
    scenario = {
        "name": "modular_adapter_scenario",
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
        "ship_list": [
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
        ],
    }
    path = tmp_path / "scenario.yaml"
    path.write_text(yaml.safe_dump(scenario), encoding="utf-8")

    ships, disturbance, config = ScenarioGenerator(config_file=None).load_episode(path)

    assert disturbance is None
    assert config.ship_list[0].ship_modules is not None
    assert isinstance(ships[0], ModularShipAdapter)
    ships[0].reset(seed=1)
    assert ships[0].get_sim_data(0.0, 0)["csog_state"].shape == (4,)


def test_full_yaml_schema_rejects_misspelled_modular_keys(tmp_path: Path) -> None:
    scenario = yaml.safe_load((paths.scenarios / "head_on.yaml").read_text(encoding="utf-8"))
    scenario["ship_list"][0]["ship_modules"] = {
        "preset": "legacy_equivalent",
        "modules": {
            "plant": {"identitty": "pass_through_plant", "parameters": {}},
            "guidance": {"identity": "pass_through_guidance", "parameters": {}},
            "controller": {"identity": "pass_through_controller", "parameters": {}},
        },
    }
    path = tmp_path / "invalid.yaml"
    path.write_text(yaml.safe_dump(scenario), encoding="utf-8")

    with pytest.raises(ValueError, match="identitty"):
        config_parsing.extract(ScenarioConfig, path, paths.scenario_schema)
