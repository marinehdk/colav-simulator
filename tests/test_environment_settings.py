import copy
import json

import pytest

from colav_simulator.environment_settings import modular_environment, normalize_settings, original_parameters
from colav_simulator.experiment.contracts import RunSpec
from colav_simulator.modular_gnc.catalog import list_stack_catalog
from colav_simulator.original_gnc.configuration import OriginalGncConfig
from gui_server.replay import RunReplayStore


def test_session_environment_is_validated_and_serialized():
    spec = RunSpec("head_on", environment_settings={"wind_speed_mps": 12, "wave_hs_m": 2, "rain_enabled": True})
    assert spec.to_dict()["environment_settings"]["wind_speed_mps"] == 12
    assert spec.environment_settings["rain_enabled"] is True
    assert spec.environment_settings["time_of_day_hours"] == 12


@pytest.mark.parametrize(
    "settings",
    [
        {"wind_speed_mps": float("nan")},
        {"wave_period_s": 0},
        {"wind_from_deg": 361},
        {"rain_enabled": "yes"},
        {"unknown": 1},
        {"cloud_cover": True},
    ],
)
def test_invalid_environment_is_rejected(settings):
    with pytest.raises(ValueError):
        normalize_settings(settings)


def test_native_environment_initialization_changes_only_environment_parameters():
    c = OriginalGncConfig.from_dict({"environment": True})
    baseline = c.parameters()
    original = copy.deepcopy(baseline)
    changed = original_parameters(
        baseline, {"wind_speed_mps": 12, "wave_hs_m": 2, "wave_period_s": 8, "current_speed_mps": 0.8}
    )
    assert baseline == original
    assert changed["wind_engine_node"]["u10"]["value"] == 12
    assert changed["wave_engine_node"]["Hs"]["value"] == 2
    assert changed["wave_engine_node"]["Tz"]["value"] == 8
    assert changed["current_engine_node"]["v_tide_surf"]["value"] == 0.8
    for key in baseline:
        if key not in {"wind_engine_node", "wave_engine_node", "current_engine_node"}:
            assert changed[key] == baseline[key]
    assert (
        OriginalGncConfig.from_dict({"environment": False, "environment_settings": {"wind_speed_mps": 12}}).parameters()
        == baseline
    )


def test_modular_field_uses_correct_from_bearing_and_does_not_mutate_preset():
    cfg = next(s["config"] for s in list_stack_catalog()["stacks"] if "environment" in s["config"].get("modules", {}))
    original = copy.deepcopy(cfg)
    changed = modular_environment(
        cfg, {"wind_speed_mps": 10, "wind_from_deg": 0, "current_speed_mps": 1, "current_from_deg": 90}
    )
    p = changed["modules"]["environment"]["parameters"]
    assert p["wind_velocity_ne"] == [-10, 0]
    assert p["current_velocity_ne"][1] == -1
    assert abs(p["current_velocity_ne"][0]) < 1e-10
    assert cfg == original


def test_replay_environment_comes_from_sealed_spec_and_config(tmp_path):
    directory = tmp_path / "runs" / "00000000-0000-0000-0000-000000000001"
    directory.mkdir(parents=True)
    (directory / "manifest.json").write_text(
        json.dumps(
            {"spec": {"scenario_id": "head_on", "environment_settings": {"time_of_day_hours": 23, "wind_speed_mps": 12}}}
        )
    )
    (directory / "episode.json").write_text(
        json.dumps({"config": {"ship_list": [{"id": 0, "original_gnc": {"environment": True}}]}})
    )
    context = RunReplayStore(tmp_path / "runs").static_context("00000000-0000-0000-0000-000000000001")
    assert context["environment"]["enabled"] is True
    assert context["environment"]["time_of_day_hours"] == 23
    assert context["environment"]["wind_speed_mps"] == 12
