from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from colav_simulator.core.models import ModelBuilder
from colav_simulator.evaluation.encounter import classify_geometry, velocity_ne, wrap_angle
from colav_simulator.scenario_generator import Config, ScenarioGenerator

WITNESS_SEEDS = {
    "overtaking": 13,
    "overtaken": 17,
    "crossing_give_way": 19,
    "crossing_stand_on": 23,
}


@pytest.mark.parametrize(
    ("scenario_name", "expected"),
    (
        ("overtaking", "overtaking"),
        ("overtaken", "overtaken"),
        ("crossing_give_way", "crossing_give_way"),
        ("crossing_stand_on", "crossing_stand_on"),
    ),
)
def test_configured_generator_produces_rule13_15_interior_witness(
    scenario_name: str,
    expected: str,
) -> None:
    runtime_config = Config.from_file(Path("config/scenario_generator.yaml"))
    generator = ScenarioGenerator(config=runtime_config, seed=WITNESS_SEEDS[scenario_name])
    episodes, _ = generator.generate(
        config_file=Path("scenarios") / f"{scenario_name}.yaml",
        new_load_of_map_data=False,
        n_episodes=1,
        show_plots=False,
        save_scenario=False,
    )

    assert len(episodes) == 1
    ownship, target = episodes[0]["ship_list"][:2]
    own_model = ModelBuilder.construct_model(episodes[0]["config"].ship_list[0].model)
    target_model = ModelBuilder.construct_model(episodes[0]["config"].ship_list[1].model)
    encounter, dcpa_m, _, signed_tcpa_s, relative_bearing_deg = classify_geometry(
        ownship.csog_state[:2],
        velocity_ne(ownship.csog_state[2], ownship.csog_state[3]),
        target.csog_state[:2],
        velocity_ne(target.csog_state[2], target.csog_state[3]),
        own_model.params.length,
        target_model.params.length,
    )

    assert encounter == expected
    assert own_model.params.U_min <= ownship.csog_state[2] <= own_model.params.U_max
    assert target_model.params.U_min <= target.csog_state[2] <= target_model.params.U_max
    assert signed_tcpa_s > 0.0
    assert dcpa_m <= runtime_config.d_cpa_threshold
    assert _classification_guard_band_deg(
        expected,
        ownship.csog_state,
        target.csog_state,
        relative_bearing_deg,
    ) >= 5.0


def test_runtime_config_ranges_are_loaded_separately_from_class_defaults() -> None:
    runtime = Config.from_file(Path("config/scenario_generator.yaml"))
    defaults = Config()

    assert runtime.cr_bearing_range == [10.1, 90.5]
    assert defaults.cr_bearing_range == [15.1, 112.5]
    assert runtime.cr_bearing_range != defaults.cr_bearing_range


def _classification_guard_band_deg(
    encounter: str,
    own_state: np.ndarray,
    target_state: np.ndarray,
    relative_bearing_deg: float,
) -> float:
    if encounter in {"crossing_give_way", "crossing_stand_on"}:
        return min(abs(relative_bearing_deg), 112.5 - abs(relative_bearing_deg))
    target_course = float(target_state[3])
    relative = np.asarray(own_state[:2]) - np.asarray(target_state[:2])
    contact_bearing = float(np.rad2deg(wrap_angle(np.arctan2(relative[1], relative[0]) - target_course)))
    bearing = contact_bearing if encounter == "overtaking" else relative_bearing_deg
    return abs(bearing) - 112.5
