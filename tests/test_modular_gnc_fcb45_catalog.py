"""FCB45 preset seam: registry, catalog listing, recommendation, provenance (Issue #67 slice 5).

The 45 m FCB workboat enters the modular catalog as new module identities
(``fcb45_3dof_plant``, ``fcb45_roll_4dof_plant``, ``fcb45_marine_pid``) pointing
at the same generic implementations with vessel parameters extracted from the
colleague's vendor ``ship_config.yaml``.  DP-10 requires the parameter assets to
carry explicit provenance (calibrated-from-vendor-config, never vessel
validated), and the dynamic-plant recommendations switch to the FCB45
combinations (Issue #67: the previously recommended tier1/2 + marine_pid stacks
are the reported broken combination).
"""

from __future__ import annotations

import json
import math

from colav_simulator.modular_gnc.catalog import list_stack_catalog
from colav_simulator.modular_gnc.configuration import (
    REGISTRY_V1,
    normalize_ship_modules,
)
from colav_simulator.modular_gnc.contracts import ControlTask
from colav_simulator.modular_gnc.plant import (
    Generic3DOFPlant,
    Generic3DOFPlantParameters,
    GenericRoll4DOFPlant,
    GenericRoll4DOFPlantParameters,
)
from colav_simulator.modular_gnc.stack import ModularShipStack

FCB45_3DOF_PLANT_PARAMS = {
    "mass_kg": 220000.0,
    "i_z_kgm2": 2.7e7,
    "x_dot_u_kg": -22000.0,
    "y_dot_v_kg": -160000.0,
    "n_dot_r_kgm2": -9.5e6,
    # Y_r_dot = N_v_dot = -1e6 (SNAME, CG origin): m_23 = m_32 = +1e6 keeps
    # the forward-speed (v, r) linearization yaw-stable.
    "y_dot_r_kgm": -1.0e6,
    "n_dot_v_kgm": -1.0e6,
    # SNAME derivatives -> repo plant damping convention: d = -coefficient for
    # the same physical term, chosen so the coupled damping block stays
    # dissipative (X_u -3500 -> d_u 3500, Y_r +6e4 -> d_vr -6e4, N_v -6e5 ->
    # d_rv +6e5; the (v,r) block determinant stays positive).
    "d_u": 3500.0,
    "d_uu": 280.0,
    # Sway damping linearised at the 7.8 m/s service speed (hull lift scales
    # with u): 5e4*7.8 and 9e3*7.8^2 — deviation-ledgered.
    "d_v": 390000.0,
    "d_vv": 547560.0,
    "d_r": 1.6e6,
    "d_rr": 3.0e6,
    "d_vr": -60000.0,
    "d_rv": 600000.0,
}

FCB45_ROLL_4DOF_PLANT_PARAMS = {
    **FCB45_3DOF_PLANT_PARAMS,
    "i_x_kgm2": 2.0e7,
    # Roll restoring from GM: m * g * GM = 220000 * 9.81 * 1.5 N.m/rad.
    "restoring_k_phi": 220000.0 * 9.81 * 1.5,
}


def _stack_config(plant: str, controller: str) -> dict:
    return {
        "preset": "legacy_equivalent",
        "modules": {
            "plant": {"identity": plant, "parameters": {}},
            "guidance": {"identity": "pass_through_guidance", "parameters": {}},
            "controller": {"identity": controller, "parameters": {}},
        },
    }


def _catalog_entry(stack_id: str) -> dict:
    for entry in list_stack_catalog()["stacks"]:
        if entry["stack_id"] == stack_id:
            return entry
    raise AssertionError(f"stack {stack_id!r} not listed in catalog")


class TestFCB45RegistryAndAssembly:
    def test_registry_entries_exist_with_generic_capabilities(self) -> None:
        for identity, reference in (
            ("fcb45_3dof_plant", "generic_3dof_plant"),
            ("fcb45_roll_4dof_plant", "generic_roll_4dof_plant"),
            ("fcb45_marine_pid", "marine_pid"),
        ):
            assert identity in REGISTRY_V1
            assert REGISTRY_V1[identity].role == REGISTRY_V1[reference].role
            assert REGISTRY_V1[identity].capabilities == REGISTRY_V1[reference].capabilities
            assert REGISTRY_V1[identity].parameter_schema == REGISTRY_V1[reference].parameter_schema
            assert REGISTRY_V1[identity].available is True

    def test_fcb45_tier1_stack_assembles_and_supports_transit(self) -> None:
        cfg = normalize_ship_modules(
            {
                "preset": "legacy_equivalent",
                "modules": {
                    "plant": {"identity": "fcb45_3dof_plant", "parameters": FCB45_3DOF_PLANT_PARAMS},
                    "guidance": {"identity": "pass_through_guidance", "parameters": {}},
                    "controller": {
                        "identity": "fcb45_marine_pid",
                        "parameters": {"kp": [0.0, 0.0, 0.0], "ki": [0.0, 0.0, 0.0], "kd": [0.0, 0.0, 0.0]},
                    },
                },
            }
        )
        stack = ModularShipStack.from_config(cfg)
        assert ControlTask.TRANSIT in stack.modules.supported_tasks

    def test_fcb45_plants_require_base_clock_plant_phase(self) -> None:
        try:
            cfg = normalize_ship_modules(
                {
                    "preset": "legacy_equivalent",
                    "overrides": {"scheduler": {"plant_period_ticks": 2}},
                    "modules": {
                        "plant": {"identity": "fcb45_roll_4dof_plant", "parameters": FCB45_ROLL_4DOF_PLANT_PARAMS},
                        "guidance": {"identity": "pass_through_guidance", "parameters": {}},
                        "controller": {
                            "identity": "fcb45_marine_pid",
                            "parameters": {"kp": [0.0, 0.0, 0.0], "ki": [0.0, 0.0, 0.0], "kd": [0.0, 0.0, 0.0]},
                        },
                    },
                }
            )
            ModularShipStack.from_config(cfg)
        except ValueError as exc:
            assert "plant_period_ticks == 1" in str(exc)
        else:
            raise AssertionError("fcb45 plants must require plant_period_ticks == 1")


class TestFCB45PresetParameters:
    def test_tier1_preset_matches_vendor_extraction_and_is_physical(self) -> None:
        """Tier-1 preset matches the vendor extraction and is physically coherent.

        The catalog preset equals the vendor-extracted table and assembles into
        a plant whose effective yaw inertia is I_z + N_r_dot = 3.65e7 kg.m^2.
        """
        entry = _catalog_entry("fcb45_3dof_plant+pass_through_guidance+fcb45_marine_pid")
        plant_params = entry["config"]["modules"]["plant"]["parameters"]
        for key, value in FCB45_3DOF_PLANT_PARAMS.items():
            assert plant_params[key] == value, key

        plant = Generic3DOFPlant(Generic3DOFPlantParameters(**plant_params))
        assert plant.mass_matrix[2, 2] == 2.7e7 + 9.5e6

    def test_tier2_preset_adds_roll_restoring_from_gm(self) -> None:
        entry = _catalog_entry("fcb45_roll_4dof_plant+pass_through_guidance+fcb45_marine_pid")
        plant_params = entry["config"]["modules"]["plant"]["parameters"]
        for key, value in FCB45_ROLL_4DOF_PLANT_PARAMS.items():
            assert plant_params[key] == value, key

        plant = GenericRoll4DOFPlant(GenericRoll4DOFPlantParameters(**plant_params))
        # Roll natural period from GM-based restoring:
        # T_phi = 2*pi*sqrt(I_x / (m*g*GM)) ~ 15.6 s for the FCB45.
        omega_phi = math.sqrt(plant.params.restoring_k_phi / plant.params.i_x_kgm2)
        assert 2.0 * math.pi / omega_phi == 15.6 or abs(2.0 * math.pi / omega_phi - 15.6) < 0.2


class TestFCB45CatalogListing:
    def test_fcb45_stacks_are_listed_and_reassemble(self) -> None:
        for stack_id in (
            "fcb45_3dof_plant+pass_through_guidance+fcb45_marine_pid",
            "fcb45_roll_4dof_plant+pass_through_guidance+fcb45_marine_pid",
        ):
            entry = _catalog_entry(stack_id)
            config = normalize_ship_modules(entry["config"])
            stack = ModularShipStack.from_config(config)
            assert ControlTask.TRANSIT in stack.modules.supported_tasks

    def test_fcb45_controller_never_pairs_with_generic_or_kinematic_plants(self) -> None:
        for entry in list_stack_catalog()["stacks"]:
            by_role = {module["role"]: module["identity"] for module in entry["modules"]}
            if by_role["controller"] == "fcb45_marine_pid":
                assert by_role["plant"] in {"fcb45_3dof_plant", "fcb45_roll_4dof_plant"}
            if by_role["plant"] in {"fcb45_3dof_plant", "fcb45_roll_4dof_plant"}:
                assert by_role["controller"] == "fcb45_marine_pid"

    def test_dynamic_plant_recommendations_switch_to_fcb45_combinations(self) -> None:
        recommendations = list_stack_catalog()["recommended_stack_ids_by_plant"]
        expected_fcb45 = {
            "fcb45_3dof_plant": "fcb45_3dof_plant+pass_through_guidance+fcb45_marine_pid",
            "fcb45_roll_4dof_plant": "fcb45_roll_4dof_plant+pass_through_guidance+fcb45_marine_pid",
        }
        assert recommendations["generic_3dof_plant"] == expected_fcb45["fcb45_3dof_plant"]
        assert recommendations["generic_roll_4dof_plant"] == expected_fcb45["fcb45_roll_4dof_plant"]
        assert recommendations["fcb45_3dof_plant"] == expected_fcb45["fcb45_3dof_plant"]
        assert recommendations["fcb45_roll_4dof_plant"] == expected_fcb45["fcb45_roll_4dof_plant"]
        # Kinematic scaffold keeps its own recommendation.
        assert recommendations["pass_through_plant"] == (
            "pass_through_plant+pass_through_guidance+pass_through_controller"
        )


class TestFCB45Provenance:
    def test_module_records_carry_parameter_provenance(self) -> None:
        entry = _catalog_entry("fcb45_3dof_plant+pass_through_guidance+fcb45_marine_pid")
        provenance = {
            module["identity"]: module.get("parameter_provenance")
            for module in entry["modules"]
            if module["identity"].startswith("fcb45")
        }
        assert set(provenance) == {"fcb45_3dof_plant", "fcb45_marine_pid"}
        for record in provenance.values():
            assert record is not None
            assert record["level"] == "calibrated_from_vendor_config"
            assert "ship_config.yaml" in record["source"]
            assert record["validated_for_vessel"] is False

    def test_provenance_never_claims_vessel_validation(self) -> None:
        compact = json.dumps(list_stack_catalog()).replace(" ", "")
        assert '"validated_for_vessel":true' not in compact
        for entry in list_stack_catalog()["stacks"]:
            for module in entry["modules"]:
                record = module.get("parameter_provenance")
                if record is not None:
                    assert record["validated_for_vessel"] is False

    def test_module_axes_include_fcb45_tiers_in_ladder_order(self) -> None:
        axes = list_stack_catalog()["module_axes"]
        plant_tiers = [entry["tier"] for entry in axes["plant"]]
        plant_ids = [entry["identity"] for entry in axes["plant"]]
        assert plant_tiers == sorted(plant_tiers)
        assert plant_ids.index("fcb45_3dof_plant") > plant_ids.index("generic_3dof_plant")
        assert plant_ids.index("fcb45_roll_4dof_plant") > plant_ids.index("generic_roll_4dof_plant")

        controller_ids = [entry["identity"] for entry in axes["controller"]]
        controller_tiers = [entry["tier"] for entry in axes["controller"]]
        assert controller_tiers == sorted(controller_tiers)
        assert controller_ids.index("fcb45_marine_pid") > controller_ids.index("marine_pid")

        fcb45_axis_entries = [entry for entry in axes["plant"] if entry["identity"].startswith("fcb45")]
        assert all(entry.get("parameter_provenance") is not None for entry in fcb45_axis_entries)
