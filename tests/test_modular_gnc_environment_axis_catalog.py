"""S10 environment-axis catalog and additive snapshot regression tests."""

from __future__ import annotations

import json
from pathlib import Path

from colav_simulator.modular_gnc.catalog import list_stack_catalog

TARGET_STACK_ID = (
    "fcb45_roll_4dof_plant+integral_line_of_sight+fcb45_marine_pid+"
    "analytic_environment_field+standard_environmental_load+"
    "data_driven_allocator[fcb45_main_rudder_actuator_layout_v1]+"
    "resolved_actuator_dynamics[fcb45_main_rudder_actuator_layout_v1]"
)
SNAPSHOT = Path(__file__).parent / "fixtures" / "stack_catalog_pre_s10.json"


def test_environment_axis_has_calm_and_analytic_tiers_with_copy_and_provenance() -> None:
    environment = list_stack_catalog()["module_axes"]["environment"]
    assert [entry["tier"] for entry in environment] == [0, 1]
    assert environment[0]["identity"] is None
    assert environment[0]["display_name"] == "Calm water (default)"
    assert environment[0]["models"]
    assert environment[0]["expected_effect"]
    assert environment[1]["identity"] == "analytic_environment_field"
    assert "standard_environmental_load" in environment[1]["expected_effect"]
    assert "wave" in environment[1]["expected_effect"].lower()
    provenance = environment[1]["parameter_provenance"]
    assert provenance["validated_for_vessel"] is False
    assert provenance["level"] in {"scenario_assumption", "calibrated_from_vendor_config"}
    assert "OCIMF" in provenance["applicability"]


def test_target_environment_stack_is_listed_with_explicit_external_current_and_both_waves() -> None:
    catalog = list_stack_catalog()
    stack = next(entry for entry in catalog["stacks"] if entry["stack_id"] == TARGET_STACK_ID)
    by_role = {module["role"]: module for module in stack["modules"]}
    assert by_role["environment"]["identity"] == "analytic_environment_field"
    assert by_role["load_model"]["identity"] == "standard_environmental_load"
    load_params = stack["config"]["modules"]["load_model"]["parameters"]
    assert load_params["current_strategy"] == "external_current_load"
    assert load_params["current_asset_id"] == "current_inferred_fcb45_v1"
    assert load_params["wave_mode"] == "both"


def test_catalog_stack_ids_are_unique_and_pre_s10_ids_and_hashes_are_unchanged() -> None:
    catalog = list_stack_catalog()
    stacks = {entry["stack_id"]: entry for entry in catalog["stacks"]}
    assert len(stacks) == len(catalog["stacks"])
    snapshot = json.loads(SNAPSHOT.read_text())
    assert set(snapshot["stack_ids"]).issubset(stacks)
    for stack_id in snapshot["stack_ids"]:
        assert stacks[stack_id]["config_hash"] == snapshot["config_hashes"][stack_id]


def test_environment_parameters_are_cataloged_with_required_values() -> None:
    catalog = list_stack_catalog()
    field_entry = next(entry for entry in catalog["stacks"] if any(
        module["identity"] == "analytic_environment_field" for module in entry["modules"]
    ))
    field = field_entry["config"]["modules"]["environment"]["parameters"]
    assert field["wind_velocity_ne"] == [6.0, 2.0]
    assert field["wind_perturbation_std"] == [0.5, 0.5]
    assert field["current_velocity_ne"] == [0.4, -0.2]
    assert field["current_perturbation_std"] == [0.1, 0.1]
    assert field["wave_significant_height_m"] == 1.0
    assert field["wave_peak_period_s"] == 7.0
    assert field["wave_num_components"] == 24
    assert field["wave_directional_spread_rad"] == 0.3

    load = field_entry["config"]["modules"]["load_model"]["parameters"]
    assert load["length_between_perpendiculars_m"] == 44.1
    assert load["beam_m"] == 8.0
    assert load["draft_m"] == 2.0
    assert load["wind_frontal_area_m2"] == 45.0
    assert load["wind_lateral_area_m2"] == 180.0
    assert load["displacement_ton"] == 220.0
    assert load["gm_t_m"] == 1.5
    assert load["kg_m"] == 2.2
