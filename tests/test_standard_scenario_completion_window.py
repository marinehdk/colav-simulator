from pathlib import Path

import numpy as np
import pytest

from colav_simulator import scenario_config
from colav_simulator.common import config_parsing as cp
from colav_simulator.common import paths

STANDARD_ENCOUNTER_SCENARIOS = (
    "head_on",
    "crossing_give_way",
    "crossing_stand_on",
    "overtaking",
    "overtaken",
)


@pytest.mark.parametrize("scenario_id", STANDARD_ENCOUNTER_SCENARIOS)
def test_standard_encounter_has_six_hundred_second_completion_window(
    scenario_id: str,
) -> None:
    config = cp.extract(
        scenario_config.ScenarioConfig,
        Path("scenarios") / f"{scenario_id}.yaml",
        paths.scenario_schema,
    )

    assert config.t_end == 600.0


@pytest.mark.parametrize("scenario_id", STANDARD_ENCOUNTER_SCENARIOS)
def test_standard_encounter_routes_extend_beyond_the_avoidance_and_return(
    scenario_id: str,
) -> None:
    config = cp.extract(
        scenario_config.ScenarioConfig,
        Path("scenarios") / f"{scenario_id}.yaml",
        paths.scenario_schema,
    )

    route_lengths = [
        float(np.linalg.norm(ship.waypoints[:, -1] - ship.waypoints[:, 0]))
        for ship in config.ship_list
    ]
    minimum_length = 2000.0 if scenario_id.startswith("crossing_") else 5500.0
    assert min(route_lengths) >= minimum_length
