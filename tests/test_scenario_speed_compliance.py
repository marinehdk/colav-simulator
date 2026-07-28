from pathlib import Path

import numpy as np
import pytest

import colav_simulator.common.config_parsing as cp
from colav_simulator.common import paths
from colav_simulator.core.models import ModelBuilder
from colav_simulator.evaluation.encounter import classify_geometry, velocity_ne
from colav_simulator.scenario_config import ScenarioConfig

STANDARD_SCENARIOS = (
    "head_on",
    "crossing_give_way",
    "crossing_stand_on",
    "overtaking",
    "overtaken",
    "paper_ccta2023_multiship",
)

EXPECTED_ENCOUNTERS = {
    "head_on": "head_on",
    "crossing_give_way": "crossing_give_way",
    "crossing_stand_on": "crossing_stand_on",
    "overtaking": "overtaking",
    "overtaken": "overtaken",
}


def _load_scenario(name: str) -> ScenarioConfig:
    return cp.extract(ScenarioConfig, Path("scenarios") / f"{name}.yaml", paths.scenario_schema)


@pytest.mark.parametrize("scenario_name", STANDARD_SCENARIOS)
def test_standard_scenario_speeds_respect_each_ship_model(scenario_name: str) -> None:
    config = _load_scenario(scenario_name)

    for ship_config in config.ship_list:
        model = ModelBuilder.construct_model(ship_config.model)
        assert ship_config.csog_state is not None
        assert ship_config.speed_plan is not None
        assert model.params.U_min <= ship_config.csog_state[2] <= model.params.U_max
        assert np.all(ship_config.speed_plan >= model.params.U_min)
        assert np.all(ship_config.speed_plan <= model.params.U_max)


@pytest.mark.parametrize(("scenario_name", "expected"), EXPECTED_ENCOUNTERS.items())
def test_normalized_standard_scenario_keeps_initial_encounter(
    scenario_name: str,
    expected: str,
) -> None:
    config = _load_scenario(scenario_name)
    ownship, target = config.ship_list[:2]
    own_model = ModelBuilder.construct_model(ownship.model)
    target_model = ModelBuilder.construct_model(target.model)

    encounter, dcpa_m, tcpa_s, signed_tcpa_s, _ = classify_geometry(
        ownship.csog_state[:2],
        velocity_ne(ownship.csog_state[2], ownship.csog_state[3]),
        target.csog_state[:2],
        velocity_ne(target.csog_state[2], target.csog_state[3]),
        own_model.params.length,
        target_model.params.length,
    )
    required_clearance = 0.5 * np.hypot(own_model.params.length, own_model.params.width) + 0.5 * np.hypot(
        target_model.params.length,
        target_model.params.width,
    )

    assert encounter == expected
    assert dcpa_m <= required_clearance
    assert 0.0 < tcpa_s == signed_tcpa_s < config.t_end


def test_overtaking_role_speed_order_is_preserved() -> None:
    overtaking = _load_scenario("overtaking")
    overtaken = _load_scenario("overtaken")

    assert overtaking.ship_list[0].csog_state[2] > overtaking.ship_list[1].csog_state[2]
    assert overtaken.ship_list[0].csog_state[2] < overtaken.ship_list[1].csog_state[2]


def test_multiship_contains_at_least_one_nominal_threat() -> None:
    config = _load_scenario("paper_ccta2023_multiship")
    ownship = config.ship_list[0]
    own_model = ModelBuilder.construct_model(ownship.model)
    threatened = False

    for target in config.ship_list[1:]:
        target_model = ModelBuilder.construct_model(target.model)
        _, dcpa_m, _, signed_tcpa_s, _ = classify_geometry(
            ownship.csog_state[:2],
            velocity_ne(ownship.csog_state[2], ownship.csog_state[3]),
            target.csog_state[:2],
            velocity_ne(target.csog_state[2], target.csog_state[3]),
            own_model.params.length,
            target_model.params.length,
        )
        required_clearance = 0.5 * np.hypot(own_model.params.length, own_model.params.width) + 0.5 * np.hypot(
            target_model.params.length,
            target_model.params.width,
        )
        threatened = threatened or (signed_tcpa_s > 0.0 and dcpa_m <= required_clearance)

    assert threatened
