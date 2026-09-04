"""Valid modular stack catalog with separated evidence labels (Issue #60).

The catalog is the single Python-side source of stack validity: a candidate is
listed only when normalize_ship_modules accepts it, ModularShipStack.from_config
assembles it, and the supported_tasks intersection is non-empty.  UI consumers
only render the result.
"""

from __future__ import annotations

import json

import pytest

from colav_simulator.modular_gnc.catalog import (
    ACCEPTANCE_CEILING_LEVEL,
    STACK_CATALOG_SCHEMA_VERSION,
    STACK_EVIDENCE_SCHEMA_VERSION,
    list_stack_catalog,
    stack_evidence_document,
)
from colav_simulator.modular_gnc.configuration import normalize_ship_modules
from colav_simulator.modular_gnc.stack import ModularShipStack


def _config_for(module_identities: dict[str, str]) -> dict:
    return {
        "preset": "legacy_equivalent",
        "modules": {role: {"identity": identity} for role, identity in module_identities.items()},
    }


def _ilos_marine_pid_3dof_resolved_config() -> dict:
    layout_id = "default_triple_actuator_layout_v1"
    actuator_ids = ("main_thruster", "bow_tunnel_thruster", "stern_tunnel_thruster")
    return {
        "preset": "legacy_equivalent",
        "modules": {
            "plant": {
                "identity": "generic_3dof_plant",
                "parameters": {"mass_kg": 1.6e7, "i_z_kgm2": 3.0e10},
            },
            "guidance": {"identity": "integral_line_of_sight"},
            "controller": {
                "identity": "marine_pid",
                "parameters": {
                    "kp": [1000.0, 500.0, 2000.0],
                    "ki": [100.0, 50.0, 200.0],
                    "kd": [200.0, 100.0, 400.0],
                },
            },
            "allocator": {
                "identity": "data_driven_allocator",
                "parameters": {"layout_asset_id": layout_id},
            },
            "actuator": {
                "identity": "resolved_actuator_dynamics",
                "parameters": {
                    "layout_asset_id": layout_id,
                    "rate_limit_n_per_s": dict.fromkeys(actuator_ids, 1000000000.0),
                    "delay_ticks": dict.fromkeys(actuator_ids, 0),
                },
            },
        },
        "overrides": {"scheduler": {"controller_period_ticks": 1}},
    }


class TestStackCatalogDocument:
    def test_document_schema_and_header(self) -> None:
        document = list_stack_catalog()

        assert document["schema_version"] == STACK_CATALOG_SCHEMA_VERSION
        assert document["acceptance_ceiling"]["level"] == ACCEPTANCE_CEILING_LEVEL == "A3"
        assert document["acceptance_ceiling"]["label"] == "Generalized Simulation"
        assert document["stacks"]
        assert document["default_stack_id"] in {entry["stack_id"] for entry in document["stacks"]}

    def test_every_listed_stack_reassembles_with_non_empty_supported_tasks(self) -> None:
        for entry in list_stack_catalog()["stacks"]:
            config = normalize_ship_modules(entry["config"])
            stack = ModularShipStack.from_config(config)
            assert config.config_hash == entry["config_hash"]
            assert stack.modules.supported_tasks
            assert entry["supported_tasks"] == sorted(task.value for task in stack.modules.supported_tasks)

    def test_legacy_equivalent_stack_is_default_with_ideal_fidelity(self) -> None:
        document = list_stack_catalog()

        default = next(
            entry for entry in document["stacks"] if entry["stack_id"] == document["default_stack_id"]
        )
        identities = {module["role"]: module["identity"] for module in default["modules"]}
        assert identities == {
            "plant": "pass_through_plant",
            "guidance": "pass_through_guidance",
            "controller": "pass_through_controller",
        }
        assert default["fidelity_profile"] == "ideal"
        assert default["supported_tasks"] == ["TRANSIT"]
        assert default["asset_trust"] == []

    def test_recommended_stack_is_exposed_for_each_plant_option(self) -> None:
        document = list_stack_catalog()
        recommendations = document["recommended_stack_ids_by_plant"]
        # Issue #67 slice 5: dynamic-plant options recommend the FCB45 preset
        # combination of their tier (the plain generic+marine_pid stacks are the
        # reported broken combination); the kinematic scaffold keeps its own.
        expected = {
            "pass_through_plant": "pass_through_plant+pass_through_guidance+pass_through_controller",
            "generic_3dof_plant": "fcb45_3dof_plant+pass_through_guidance+fcb45_marine_pid",
            "generic_roll_4dof_plant": "fcb45_roll_4dof_plant+pass_through_guidance+fcb45_marine_pid",
            "fcb45_3dof_plant": "fcb45_3dof_plant+pass_through_guidance+fcb45_marine_pid",
            "fcb45_roll_4dof_plant": "fcb45_roll_4dof_plant+pass_through_guidance+fcb45_marine_pid",
        }

        assert recommendations == expected
        assert all(
            not any(module["role"] == "allocator" for module in entry["modules"])
            for entry in document["stacks"]
            if entry["stack_id"] in recommendations.values()
        )

    def test_transit_catalog_excludes_force_plants_with_pass_through_controller(self) -> None:
        for entry in list_stack_catalog()["stacks"]:
            identities = {module["role"]: module["identity"] for module in entry["modules"]}
            assert not (
                identities.get("plant") in {"generic_3dof_plant", "generic_roll_4dof_plant"}
                and identities.get("controller") == "pass_through_controller"
            )

    def test_capability_incompatible_tuple_is_not_listed(self) -> None:
        incompatible = _config_for(
            {
                "plant": "pass_through_plant",
                "guidance": "pass_through_guidance",
                "controller": "marine_pid",
            }
        )
        with pytest.raises(ValueError, match="GENERALIZED_FORCE"):
            normalize_ship_modules(incompatible)

        for entry in list_stack_catalog()["stacks"]:
            identities = {module["role"]: module["identity"] for module in entry["modules"]}
            assert not (
                identities.get("plant") == "pass_through_plant"
                and identities.get("controller") == "marine_pid"
            )

    def test_dependency_unavailable_module_is_never_listed(self) -> None:
        for entry in list_stack_catalog()["stacks"]:
            for module in entry["modules"]:
                assert module["identity"] != "optional_native_controller"
                assert module["available"] is True

    def test_resolved_stack_exposes_mock_trust_and_resolved_fidelity(self) -> None:
        resolved = [
            entry
            for entry in list_stack_catalog()["stacks"]
            if entry["fidelity_profile"] == "resolved"
        ]
        assert resolved
        triple = next(
            entry
            for entry in resolved
            if any(
                asset["asset_id"] == "default_triple_actuator_layout_v1"
                for asset in entry["asset_trust"]
            )
        )
        identities = {module["role"]: module["identity"] for module in triple["modules"]}
        assert identities["allocator"] == "data_driven_allocator"
        assert identities["actuator"] == "resolved_actuator_dynamics"
        assert triple["asset_trust"] == [
            {
                "asset_id": "default_triple_actuator_layout_v1",
                "asset_type": "actuator_layout",
                "trust_level": "mock",
            }
        ]

    def test_catalog_is_deterministic(self) -> None:
        assert list_stack_catalog() == list_stack_catalog()


class TestModuleAxes:
    """Config step 04: per-axis fidelity ladder document (array order = tier order)."""

    def test_module_axes_present_with_required_fields(self) -> None:
        axes = list_stack_catalog()["module_axes"]

        for axis in ("plant", "guidance", "controller"):
            entries = axes[axis]
            assert entries, f"{axis} axis must list options"
            for entry in entries:
                assert entry["identity"]
                assert entry["display_name"]
                assert isinstance(entry["tier"], int)
                assert entry["models"]
                assert entry["expected_effect"]

    def test_axis_arrays_are_non_decreasing_by_tier(self) -> None:
        axes = list_stack_catalog()["module_axes"]

        for axis in ("plant", "guidance", "controller"):
            tiers = [entry["tier"] for entry in axes[axis]]
            assert tiers == sorted(tiers), f"{axis} ladder must be ordered simple → fidelity"
        actuation = axes["actuation"]
        assert actuation["none"]["tier"] == 0
        layout_tiers = [entry["tier"] for entry in actuation["layouts"]]
        assert layout_tiers == sorted(layout_tiers)
        assert actuation["none"]["tier"] < layout_tiers[0] < actuation["resolved"]["tier"]

    def test_allocator_layouts_declare_drive_nature(self) -> None:
        layouts = list_stack_catalog()["module_axes"]["actuation"]["layouts"]

        natures = {entry["layout_asset_id"]: entry["drive_nature"] for entry in layouts}
        assert natures == {
            "main_only_actuator_layout_v1": "underactuated",
            "default_triple_actuator_layout_v1": "fully actuated",
            "quad_diagonal_actuator_layout_v1": "overactuated",
            "fcb45_actuator_layout_v1": "fully actuated",
        }
        assert all(entry["identity"] == "data_driven_allocator" for entry in layouts)

    def test_module_axes_cover_every_listed_stack_module(self) -> None:
        axes = list_stack_catalog()["module_axes"]
        plant_ids = {entry["identity"] for entry in axes["plant"]}
        guidance_ids = {entry["identity"] for entry in axes["guidance"]}
        controller_ids = {entry["identity"] for entry in axes["controller"]}
        layout_ids = {entry["layout_asset_id"] for entry in axes["actuation"]["layouts"]}
        resolved_identity = axes["actuation"]["resolved"]["identity"]

        for entry in list_stack_catalog()["stacks"]:
            by_role = {module["role"]: module["identity"] for module in entry["modules"]}
            assert by_role["plant"] in plant_ids
            assert by_role["guidance"] in guidance_ids
            assert by_role["controller"] in controller_ids
            if "allocator" in by_role:
                bound = {asset["asset_id"] for asset in entry["asset_trust"]}
                assert bound & layout_ids, "allocator layout must appear in the actuation axis"
            assert ("actuator" in by_role) == (by_role.get("actuator") == resolved_identity)

    def test_module_axes_make_no_claim_beyond_accepted_evidence(self) -> None:
        forbidden = ["A4", "A5", "A6", "A7", "vessel-validated", "vessel_validated", "SIL", "sea-trial", "sea trial"]

        rendered = json.dumps(list_stack_catalog()["module_axes"])
        for token in forbidden:
            assert token not in rendered

    def test_catalog_schema_version_is_unchanged_by_module_axes(self) -> None:
        # additive document key only; consumers key off the same schema string
        assert list_stack_catalog()["schema_version"] == STACK_CATALOG_SCHEMA_VERSION


class TestSeparatedEvidenceFields:
    """AC2: maturity, fidelity, asset trust, and acceptance stay separate fields."""

    def test_evidence_fields_are_distinct(self) -> None:
        for entry in list_stack_catalog()["stacks"]:
            assert isinstance(entry["fidelity_profile"], str)
            assert isinstance(entry["asset_trust"], list)
            assert isinstance(entry["acceptance_level"], str)
            for module in entry["modules"]:
                assert module["interface_version"]  # maturity field
                assert module["acceptance_evidence"]  # acceptance field
            # maturity is never merged into the acceptance level
            assert entry["acceptance_level"] not in {module["interface_version"] for module in entry["modules"]}

    def test_acceptance_vocabulary_never_implies_more_than_accepted(self) -> None:
        allowed = {
            "interface_contract",
            "controller_contract",
            "module_closed_loop_contract",
            "candidate_a2_migration_parity",
        }
        document = list_stack_catalog()
        for entry in document["stacks"]:
            assert entry["acceptance_level"] in allowed
            for module in entry["modules"]:
                assert module["acceptance_evidence"] in allowed

    def test_no_a4_or_higher_and_no_vessel_validation_claims(self) -> None:
        forbidden = ["A4", "A5", "A6", "A7", "vessel_validated", "vessel-validated", "SIL", "sea-trial"]
        document = list_stack_catalog()
        rendered = document["acceptance_ceiling"]["level"] + document["acceptance_ceiling"]["label"]
        rendered += "".join(
            entry["acceptance_level"]
            + "".join(module["acceptance_evidence"] for module in entry["modules"])
            + "".join(asset["trust_level"] for asset in entry["asset_trust"])
            for entry in document["stacks"]
        )
        for token in forbidden:
            assert token not in rendered


class TestStackEvidenceDocument:
    def test_document_matches_catalog_entry_for_same_stack(self) -> None:
        entry = next(
            item
            for item in list_stack_catalog()["stacks"]
            if item["fidelity_profile"] == "resolved"
            and any(module["identity"] == "marine_pid" for module in item["modules"])
        )

        # Telemetry path: a consumer receives the entry config dict, normalizes
        # it, and rebuilds the evidence document; it must match the catalog.
        config = normalize_ship_modules(entry["config"])
        stack = ModularShipStack.from_config(config)
        document = stack_evidence_document(config, supported_tasks=stack.modules.supported_tasks)

        assert document["schema_version"] == STACK_EVIDENCE_SCHEMA_VERSION
        for key in (
            "stack_id",
            "display_name",
            "config_hash",
            "fidelity_profile",
            "supported_tasks",
            "modules",
            "asset_trust",
            "acceptance_level",
        ):
            assert document[key] == entry[key]
        assert document["fidelity_profile"] == "resolved"

    def test_document_reports_module_maturity_and_acceptance_per_role(self) -> None:
        config = normalize_ship_modules(_ilos_marine_pid_3dof_resolved_config())
        stack = ModularShipStack.from_config(config)

        document = stack_evidence_document(config, supported_tasks=stack.modules.supported_tasks)

        by_role = {module["role"]: module for module in document["modules"]}
        assert by_role["controller"]["identity"] == "marine_pid"
        assert by_role["controller"]["acceptance_evidence"] == "controller_contract"
        assert by_role["controller"]["interface_version"] == "controller.v1"
        assert by_role["plant"]["acceptance_evidence"] == "candidate_a2_migration_parity"
        assert by_role["allocator"]["acceptance_evidence"] == "module_closed_loop_contract"
        assert by_role["actuator"]["acceptance_evidence"] == "module_closed_loop_contract"
        assert document["acceptance_level"] in {
            "controller_contract",
            "module_closed_loop_contract",
        }

    def test_document_covers_ideal_stack_without_assets(self) -> None:
        config = normalize_ship_modules(
            _config_for(
                {
                    "plant": "pass_through_plant",
                    "guidance": "pass_through_guidance",
                    "controller": "pass_through_controller",
                }
            )
        )
        stack = ModularShipStack.from_config(config)

        document = stack_evidence_document(config, supported_tasks=stack.modules.supported_tasks)

        assert document["fidelity_profile"] == "ideal"
        assert document["asset_trust"] == []
        assert document["acceptance_level"] == "interface_contract"
        assert document["supported_tasks"] == ["TRANSIT"]

    def test_document_is_json_safe(self) -> None:
        config = normalize_ship_modules(_ilos_marine_pid_3dof_resolved_config())
        stack = ModularShipStack.from_config(config)

        document = stack_evidence_document(config, supported_tasks=stack.modules.supported_tasks)

        assert json.loads(json.dumps(document)) == document
