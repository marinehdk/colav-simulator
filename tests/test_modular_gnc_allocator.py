"""Data-driven actuator allocator and achieved-load diagnostics (Issue #58, S6.1).

Covers layout/geometry/limits/effectiveness/health derivation from data assets,
allocation feasibility visibility (requested/achieved/residual/constraints/
saturation/degradation), layout permutation invariance, multiple layouts,
underactuation, and strict roll-channel exclusion (RA-12, VR-16).
"""

from __future__ import annotations

import numpy as np
import pytest

from colav_simulator.modular_gnc.allocator import (
    DEFAULT_TRIPLE_ACTUATOR_LAYOUT_V1,
    KNOWN_ACTUATOR_LAYOUT_ASSETS,
    MAIN_ONLY_ACTUATOR_LAYOUT_V1,
    QUAD_DIAGONAL_ACTUATOR_LAYOUT_V1,
    ActuatorLayoutAsset,
    ActuatorSpec,
    DataDrivenAllocator,
    actuator_layout_content_sha256,
)
from colav_simulator.modular_gnc.configuration import REGISTRY_V1, normalize_ship_modules
from colav_simulator.modular_gnc.contracts import (
    AchievedLoadStatus,
    AssetIntegrityError,
    AssetMetadata,
    AssetTrustLevel,
    CommandInput,
    ControlTask,
    DirectReference,
    FailureCode,
    NavigationState,
    VesselLoad,
)
from colav_simulator.modular_gnc.passthrough_modules import PassThroughModules
from colav_simulator.modular_gnc.plant import Generic3DOFPlant, Generic3DOFPlantParameters
from colav_simulator.modular_gnc.stack import ModularShipStack

_TRIPLE_REQUEST = VesselLoad(surge_n=2.1e5, sway_n=5.0e4, yaw_nm=1.0e5)

_PLANT_PARAMS = {
    "mass_kg": 1.6e7,
    "i_z_kgm2": 3.0e10,
    "x_g_m": 0.0,
    "x_dot_u_kg": -5.0e6,
    "y_dot_v_kg": -3.5e7,
    "n_dot_r_kgm2": -2.0e10,
    "y_dot_r_kgm": 1.0e6,
    "n_dot_v_kgm": 1.0e6,
    "d_u": 5.0e4,
    "d_uu": 2.0e5,
    "d_v": 3.0e5,
    "d_vv": 1.5e6,
    "d_r": 8.0e7,
    "d_rr": 2.5e9,
}

_PLANT_4DOF_PARAMS = {
    "mass_kg": 1.6e7,
    "i_x_kgm2": 1.5e9,
    "i_z_kgm2": 3.0e10,
    "x_g_m": 0.0,
    "z_g_m": 0.0,
    "x_dot_u_kg": -5.0e6,
    "y_dot_v_kg": -3.5e7,
    "k_dot_p_kgm2": -5.0e8,
    "n_dot_r_kgm2": -2.0e10,
    "y_dot_r_kgm": 1.0e6,
    "n_dot_v_kgm": 1.0e6,
    "d_u": 5.0e4,
    "d_uu": 2.0e5,
    "d_v": 3.0e5,
    "d_vv": 1.5e6,
    "d_p": 2.0e7,
    "d_pp": 5.0e7,
    "d_r": 8.0e7,
    "d_rr": 2.5e9,
    "restoring_k_phi": 3.0e8,
}


def _allocator_module(layout_id: str = "default_triple_actuator_layout_v1") -> dict:
    return {"identity": "data_driven_allocator", "parameters": {"layout_asset_id": layout_id}}


def _config_with_allocator(
    layout_id: str = "default_triple_actuator_layout_v1",
    plant_identity: str = "generic_3dof_plant",
    controller_period_ticks: int | None = None,
) -> dict:
    plant_params = _PLANT_4DOF_PARAMS if plant_identity == "generic_roll_4dof_plant" else _PLANT_PARAMS
    config = {
        "preset": "legacy_equivalent",
        "modules": {
            "plant": {"identity": plant_identity, "parameters": dict(plant_params)},
            "guidance": {"identity": "pass_through_guidance", "parameters": {}},
            "controller": {"identity": "pass_through_controller", "parameters": {}},
            "allocator": _allocator_module(layout_id),
        },
    }
    if controller_period_ticks is not None:
        config["overrides"] = {"scheduler": {"controller_period_ticks": controller_period_ticks}}
    return config


def _layout_metadata(actuators: tuple[ActuatorSpec, ...], asset_id: str) -> AssetMetadata:
    return AssetMetadata(
        asset_id=asset_id,
        asset_type="actuator_layout",
        trust_level=AssetTrustLevel.MOCK,
        source_type="mock",
        sha256=actuator_layout_content_sha256(actuators),
        license="MIT",
    )


def _permuted_triple_layout() -> ActuatorLayoutAsset:
    """Same actuators as the default triple layout, reversed declaration order."""
    actuators = tuple(reversed(DEFAULT_TRIPLE_ACTUATOR_LAYOUT_V1.actuators))
    return ActuatorLayoutAsset(metadata=_layout_metadata(actuators, "permuted_triple"), actuators=actuators)


class TestActuatorLayoutAsset:
    """Layout assets derive geometry, effectiveness, and limits from data (AC1)."""

    def test_effectiveness_matrix_is_derived_from_geometry(self) -> None:
        matrix = DEFAULT_TRIPLE_ACTUATOR_LAYOUT_V1.effectiveness_matrix()

        assert matrix.shape == (3, 3)
        assert not matrix.flags.writeable
        # Worked example from the r x F moment convention (right-positive yaw):
        # main at (0, 0) deg 0 -> [1, 0, 0]; bow tunnel at (40, 0) deg 90 -> [0, 1, 40];
        # stern tunnel at (-10, 0) deg 90 -> [0, 1, -10].
        np.testing.assert_allclose(matrix[:, 0], [1.0, 0.0, 0.0], atol=1e-12)
        np.testing.assert_allclose(matrix[:, 1], [0.0, 1.0, 40.0], atol=1e-12)
        np.testing.assert_allclose(matrix[:, 2], [0.0, 1.0, -10.0], atol=1e-12)

    def test_effectiveness_matrix_never_has_roll_row(self) -> None:
        for asset in KNOWN_ACTUATOR_LAYOUT_ASSETS.values():
            assert asset.effectiveness_matrix().shape[0] == 3

    def test_rejects_duplicate_actuator_ids(self) -> None:
        duplicated = DEFAULT_TRIPLE_ACTUATOR_LAYOUT_V1.actuators[:1] * 2
        with pytest.raises(ValueError, match="unique"):
            ActuatorLayoutAsset(metadata=_layout_metadata(duplicated, "dup"), actuators=duplicated)

    def test_rejects_empty_layout(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            ActuatorLayoutAsset(metadata=_layout_metadata((), "empty"), actuators=())

    def test_rejects_unknown_response_curve(self) -> None:
        with pytest.raises(ValueError, match="response_curve"):
            ActuatorSpec(
                actuator_id="a",
                kind="main",
                position_body_m=(0.0, 0.0),
                orientation_body_rad=0.0,
                min_force_n=-1.0,
                max_force_n=1.0,
                response_curve="quadratic",
            )

    def test_rejects_limits_not_bracketing_zero(self) -> None:
        with pytest.raises(ValueError, match="bracket"):
            ActuatorSpec(
                actuator_id="a",
                kind="main",
                position_body_m=(0.0, 0.0),
                orientation_body_rad=0.0,
                min_force_n=100.0,
                max_force_n=200.0,
            )

    def test_rejects_out_of_range_initial_health(self) -> None:
        with pytest.raises(ValueError, match="initial_health"):
            ActuatorSpec(
                actuator_id="a",
                kind="main",
                position_body_m=(0.0, 0.0),
                orientation_body_rad=0.0,
                min_force_n=-1.0,
                max_force_n=1.0,
                initial_health=1.5,
            )

    def test_verify_integrity_accepts_builtins_and_rejects_tampering(self) -> None:
        for asset in KNOWN_ACTUATOR_LAYOUT_ASSETS.values():
            assert asset.verify_integrity()

        original = DEFAULT_TRIPLE_ACTUATOR_LAYOUT_V1
        tampered_spec = ActuatorSpec(
            actuator_id=original.actuators[0].actuator_id,
            kind=original.actuators[0].kind,
            position_body_m=original.actuators[0].position_body_m,
            orientation_body_rad=original.actuators[0].orientation_body_rad,
            min_force_n=original.actuators[0].min_force_n,
            max_force_n=original.actuators[0].max_force_n + 1.0,
            effectiveness=original.actuators[0].effectiveness,
            response_curve=original.actuators[0].response_curve,
            initial_health=original.actuators[0].initial_health,
        )
        tampered = ActuatorLayoutAsset(metadata=original.metadata, actuators=(tampered_spec,))

        assert not tampered.verify_integrity()


class TestDataDrivenAllocatorUnit:
    """Allocation through data-driven layouts with visible feasibility (AC2)."""

    @staticmethod
    def _allocator() -> DataDrivenAllocator:
        return DataDrivenAllocator(DEFAULT_TRIPLE_ACTUATOR_LAYOUT_V1)

    def test_from_params_resolves_known_layout_and_rejects_unknown(self) -> None:
        allocator = DataDrivenAllocator.from_params({"layout_asset_id": "default_triple_actuator_layout_v1"})
        assert allocator.asset_id == "default_triple_actuator_layout_v1"

        with pytest.raises(ValueError, match="layout_asset_id"):
            DataDrivenAllocator.from_params({})
        with pytest.raises(ValueError, match="unknown_actuator_layout_v1"):
            DataDrivenAllocator.from_params({"layout_asset_id": "unknown_actuator_layout_v1"})

    def test_init_rejects_asset_with_failed_integrity(self) -> None:
        original = DEFAULT_TRIPLE_ACTUATOR_LAYOUT_V1
        tampered_spec = ActuatorSpec(
            actuator_id=original.actuators[0].actuator_id,
            kind=original.actuators[0].kind,
            position_body_m=original.actuators[0].position_body_m,
            orientation_body_rad=original.actuators[0].orientation_body_rad,
            min_force_n=original.actuators[0].min_force_n,
            max_force_n=original.actuators[0].max_force_n + 1.0,
        )
        tampered = ActuatorLayoutAsset(metadata=original.metadata, actuators=(tampered_spec,))

        with pytest.raises(AssetIntegrityError):
            DataDrivenAllocator(tampered)

    def test_feasible_request_achieved_with_zero_residual(self) -> None:
        # Hand-worked solution of B u = tau with the default triple layout:
        # u_main = 2.1e5; bow + stern = 5e4; 40*bow - 10*stern = 1e5
        # -> bow = 1.2e4, stern = 3.8e4 (independent source of truth).
        allocator = self._allocator()

        solution = allocator.allocate(_TRIPLE_REQUEST, tick=3, time_s=0.3)

        assert solution.requested == _TRIPLE_REQUEST
        assert solution.achieved.surge_n == pytest.approx(_TRIPLE_REQUEST.surge_n)
        assert solution.achieved.sway_n == pytest.approx(_TRIPLE_REQUEST.sway_n)
        assert solution.achieved.yaw_nm == pytest.approx(_TRIPLE_REQUEST.yaw_nm)
        assert solution.residual.surge_n == pytest.approx(0.0, abs=1e-6)
        assert solution.residual.sway_n == pytest.approx(0.0, abs=1e-6)
        assert solution.residual.yaw_nm == pytest.approx(0.0, abs=1e-6)
        assert solution.actuator_commands_n["main_thruster"] == pytest.approx(2.1e5)
        assert solution.actuator_commands_n["bow_tunnel_thruster"] == pytest.approx(1.2e4)
        assert solution.actuator_commands_n["stern_tunnel_thruster"] == pytest.approx(3.8e4)
        assert solution.active_constraints == ()
        assert solution.saturated is False
        assert solution.degraded is False
        assert solution.degraded_actuators == ()
        assert solution.tick == 3
        assert solution.time_s == pytest.approx(0.3)

    def test_invariant_under_layout_permutation(self) -> None:
        canonical = DataDrivenAllocator(DEFAULT_TRIPLE_ACTUATOR_LAYOUT_V1).allocate(_TRIPLE_REQUEST)
        permuted = DataDrivenAllocator(_permuted_triple_layout()).allocate(_TRIPLE_REQUEST)

        assert permuted.actuator_commands_n.keys() == canonical.actuator_commands_n.keys()
        for actuator_id, command in canonical.actuator_commands_n.items():
            assert permuted.actuator_commands_n[actuator_id] == pytest.approx(command)
        assert permuted.achieved.surge_n == pytest.approx(canonical.achieved.surge_n)
        assert permuted.achieved.sway_n == pytest.approx(canonical.achieved.sway_n)
        assert permuted.achieved.yaw_nm == pytest.approx(canonical.achieved.yaw_nm)
        assert permuted.active_constraints == canonical.active_constraints
        assert permuted.saturated is canonical.saturated

    def test_multiple_layouts_allocate_with_distinct_command_splits(self) -> None:
        request = VesselLoad(surge_n=1.0e5, sway_n=2.0e4, yaw_nm=5.0e4)
        triple = DataDrivenAllocator(DEFAULT_TRIPLE_ACTUATOR_LAYOUT_V1).allocate(request)
        quad = DataDrivenAllocator(QUAD_DIAGONAL_ACTUATOR_LAYOUT_V1).allocate(request)

        assert triple.residual.surge_n == pytest.approx(0.0, abs=1e-6)
        assert triple.residual.sway_n == pytest.approx(0.0, abs=1e-6)
        assert triple.residual.yaw_nm == pytest.approx(0.0, abs=1e-6)
        assert quad.residual.surge_n == pytest.approx(0.0, abs=1e-6)
        assert quad.residual.sway_n == pytest.approx(0.0, abs=1e-6)
        assert quad.residual.yaw_nm == pytest.approx(0.0, abs=1e-6)
        assert set(triple.actuator_commands_n) != set(quad.actuator_commands_n)

    def test_infeasible_request_reports_saturation_and_residual(self) -> None:
        allocator = self._allocator()

        solution = allocator.allocate(VesselLoad(surge_n=1.0e7), tick=0, time_s=0.0)

        # Hand-worked: exact solve is u = [1e7, 0, 0]; only the main thruster
        # contributes surge, so it clips at its 8e5 N ceiling.
        assert solution.saturated is True
        assert solution.active_constraints == (("main_thruster", "max_force_n"),)
        assert solution.actuator_commands_n["main_thruster"] == pytest.approx(8.0e5)
        assert solution.achieved.surge_n == pytest.approx(8.0e5)
        assert solution.achieved.sway_n == pytest.approx(0.0, abs=1e-6)
        assert solution.achieved.yaw_nm == pytest.approx(0.0, abs=1e-6)
        assert solution.residual.surge_n == pytest.approx(1.0e7 - 8.0e5)
        assert solution.degraded is False

    def test_underactuated_layout_leaves_unachievable_channels_in_residual(self) -> None:
        allocator = DataDrivenAllocator(MAIN_ONLY_ACTUATOR_LAYOUT_V1)

        solution = allocator.allocate(VesselLoad(surge_n=1.0e5, sway_n=5.0e4, yaw_nm=1.0e4))

        assert solution.achieved.surge_n == pytest.approx(1.0e5)
        assert solution.achieved.sway_n == pytest.approx(0.0, abs=1e-6)
        assert solution.achieved.yaw_nm == pytest.approx(0.0, abs=1e-6)
        assert solution.residual.surge_n == pytest.approx(0.0, abs=1e-6)
        assert solution.residual.sway_n == pytest.approx(5.0e4)
        assert solution.residual.yaw_nm == pytest.approx(1.0e4)
        assert solution.saturated is False

    def test_failed_actuator_degrades_and_reroutes_commands(self) -> None:
        allocator = self._allocator()
        allocator.set_actuator_health("bow_tunnel_thruster", 0.0)

        # Hand-worked achievable request in span{main, stern}: the stern tunnel
        # at (-10, 0) with force f delivers [0, f, -10*f], so f = 1e5 gives
        # sway 1e5 and yaw -1e6 exactly once the bow is dead.
        solution = allocator.allocate(VesselLoad(surge_n=2.0e5, sway_n=1.0e5, yaw_nm=-1.0e6))

        assert solution.degraded is True
        assert solution.degraded_actuators == ("bow_tunnel_thruster",)
        assert solution.actuator_commands_n["bow_tunnel_thruster"] == pytest.approx(0.0, abs=1e-6)
        assert solution.actuator_commands_n["stern_tunnel_thruster"] == pytest.approx(1.0e5)
        assert solution.achieved.surge_n == pytest.approx(2.0e5)
        assert solution.achieved.sway_n == pytest.approx(1.0e5)
        assert solution.achieved.yaw_nm == pytest.approx(-1.0e6)
        assert solution.residual.surge_n == pytest.approx(0.0, abs=1e-6)
        assert solution.residual.sway_n == pytest.approx(0.0, abs=1e-6)
        assert solution.residual.yaw_nm == pytest.approx(0.0, abs=1e-6)

    def test_partial_health_degradation_still_tracks_request_within_capacity(self) -> None:
        allocator = self._allocator()
        allocator.set_actuator_health("bow_tunnel_thruster", 0.5)

        solution = allocator.allocate(VesselLoad(surge_n=1.0e5, sway_n=1.0e4, yaw_nm=1.0e5))

        assert solution.degraded is True
        assert solution.achieved.surge_n == pytest.approx(1.0e5)
        assert solution.achieved.sway_n == pytest.approx(1.0e4)
        assert solution.achieved.yaw_nm == pytest.approx(1.0e5)

    def test_rejects_nonzero_roll_request(self) -> None:
        allocator = self._allocator()

        with pytest.raises(ValueError, match="roll"):
            allocator.allocate(VesselLoad(surge_n=1.0, roll_nm=1e-12))

    def test_set_actuator_health_validates_id_and_range(self) -> None:
        allocator = self._allocator()

        with pytest.raises(ValueError, match="unknown actuator"):
            allocator.set_actuator_health("no_such_thruster", 0.5)
        with pytest.raises(ValueError, match="health"):
            allocator.set_actuator_health("main_thruster", 1.5)

    def test_reset_restores_asset_declared_initial_health(self) -> None:
        spec = ActuatorSpec(
            actuator_id="weary_thruster",
            kind="main",
            position_body_m=(0.0, 0.0),
            orientation_body_rad=0.0,
            min_force_n=-1.0e5,
            max_force_n=1.0e5,
            initial_health=0.5,
        )
        asset = ActuatorLayoutAsset(metadata=_layout_metadata((spec,), "weary"), actuators=(spec,))
        allocator = DataDrivenAllocator(asset)

        assert allocator.actuator_health()["weary_thruster"] == pytest.approx(0.5)
        allocator.set_actuator_health("weary_thruster", 1.0)
        allocator.reset()

        assert allocator.actuator_health()["weary_thruster"] == pytest.approx(0.5)

    def test_snapshot_restore_roundtrip_preserves_health_and_allocation(self) -> None:
        allocator = self._allocator()
        allocator.set_actuator_health("bow_tunnel_thruster", 0.25)
        snapshot = allocator.snapshot()

        allocator.reset()
        assert allocator.actuator_health()["bow_tunnel_thruster"] == pytest.approx(1.0)

        allocator.restore(snapshot)

        assert allocator.actuator_health()["bow_tunnel_thruster"] == pytest.approx(0.25)
        solution = allocator.allocate(_TRIPLE_REQUEST)
        reference = DataDrivenAllocator(DEFAULT_TRIPLE_ACTUATOR_LAYOUT_V1)
        reference.set_actuator_health("bow_tunnel_thruster", 0.25)
        expected = reference.allocate(_TRIPLE_REQUEST)
        assert solution.actuator_commands_n == pytest.approx(expected.actuator_commands_n)

    def test_solution_to_achieved_generalized_load_carries_diagnostics(self) -> None:
        allocator = self._allocator()
        allocator.set_actuator_health("bow_tunnel_thruster", 0.0)

        solution = allocator.allocate(_TRIPLE_REQUEST, tick=7, time_s=0.7)
        achieved = solution.to_achieved_generalized_load()

        assert achieved.source == "DATA_DRIVEN_ALLOCATOR"
        assert achieved.status is AchievedLoadStatus.AVAILABLE
        assert achieved.tick == 7
        assert achieved.time_s == pytest.approx(0.7)
        assert achieved.surge_n == pytest.approx(solution.achieved.surge_n)
        assert achieved.sway_n == pytest.approx(solution.achieved.sway_n)
        assert achieved.yaw_nm == pytest.approx(solution.achieved.yaw_nm)
        assert achieved.roll_nm == 0.0
        assert achieved.details["layout_asset_id"] == "default_triple_actuator_layout_v1"
        assert achieved.details["degraded"] is True
        assert achieved.details["degraded_actuators"] == ("bow_tunnel_thruster",)
        assert achieved.details["active_constraints"] == ()
        assert achieved.details["residual"]["surge_n"] == pytest.approx(solution.residual.surge_n)
        assert achieved.details["actuator_health"]["bow_tunnel_thruster"] == 0.0
        assert achieved.details["actuator_commands_n"]["main_thruster"] == pytest.approx(
            solution.actuator_commands_n["main_thruster"]
        )


class TestAllocatorConfiguration:
    """Allocator module selection follows the registry and asset-id contract (AC1)."""

    def test_registry_declares_data_driven_allocator(self) -> None:
        entry = REGISTRY_V1["data_driven_allocator"]

        assert entry.role == "allocator"
        assert entry.available is True
        assert "GENERALIZED_FORCE" in entry.capabilities
        assert entry.parameter_schema == {"layout_asset_id": {"type": "string"}}

    def test_normalize_accepts_allocator_module(self) -> None:
        config = normalize_ship_modules(_config_with_allocator())

        assert config.modules["allocator"].identity == "data_driven_allocator"
        assert config.modules["allocator"].parameters["layout_asset_id"] == "default_triple_actuator_layout_v1"

    def test_allocator_requires_known_layout_asset_id(self) -> None:
        missing = _config_with_allocator()
        del missing["modules"]["allocator"]["parameters"]["layout_asset_id"]
        with pytest.raises(Exception, match="layout_asset_id is required"):
            normalize_ship_modules(missing)

        unknown = _config_with_allocator(layout_id="not_a_layout")
        with pytest.raises(Exception, match="unknown actuator layout asset id"):
            normalize_ship_modules(unknown)

    def test_allocator_identity_rejected_under_wrong_role(self) -> None:
        config = _config_with_allocator()
        config["modules"]["plant"] = config["modules"].pop("allocator")
        with pytest.raises(Exception, match="role"):
            normalize_ship_modules(config)

    def test_config_hash_reflects_allocator_selection(self) -> None:
        with_allocator = normalize_ship_modules(_config_with_allocator())
        without_allocator = normalize_ship_modules(
            {
                "preset": "legacy_equivalent",
                "modules": {
                    "plant": {"identity": "generic_3dof_plant", "parameters": dict(_PLANT_PARAMS)},
                    "guidance": {"identity": "pass_through_guidance", "parameters": {}},
                    "controller": {"identity": "pass_through_controller", "parameters": {}},
                },
            }
        )

        assert with_allocator.config_hash != without_allocator.config_hash


def _manual_load_command(tick: int, surge: float, sway: float, yaw: float) -> CommandInput:
    values = np.zeros(9)
    values[0] = surge
    values[1] = sway
    values[2] = yaw
    return CommandInput.direct(tick, DirectReference(values, latched_tick=tick, task=ControlTask.MANUAL_LOAD))


def _build_stack(config: dict) -> ModularShipStack:
    stack = ModularShipStack.from_config(normalize_ship_modules(config))
    stack.reset(NavigationState(0.0, 0.0, 0.0, 0.0, 0.0, 0.0), seed=7)
    return stack


def _build_stack_with_allocator(
    controller_period_ticks: int = 1,
    **module_kwargs,
) -> tuple[ModularShipStack, DataDrivenAllocator]:
    """Build a stack from explicit modules, returning the allocator handle."""
    allocator = DataDrivenAllocator(DEFAULT_TRIPLE_ACTUATOR_LAYOUT_V1)
    modules = PassThroughModules(
        plant=Generic3DOFPlant(Generic3DOFPlantParameters(**_PLANT_PARAMS)),
        allocator=allocator,
        **module_kwargs,
    )
    config = normalize_ship_modules(_config_with_allocator(controller_period_ticks=controller_period_ticks))
    stack = ModularShipStack(config, modules)
    stack.reset(NavigationState(0.0, 0.0, 0.0, 0.0, 0.0, 0.0), seed=7)
    return stack, allocator


class TestAllocatorStackIntegration:
    """Allocator resolves stack generalized-load requests through layout data (AC2, AC4)."""

    def test_allocated_stack_resolves_manual_load_through_layout(self) -> None:
        stack = _build_stack(_config_with_allocator())

        output = stack.step(_manual_load_command(0, 2.1e5, 5.0e4, 1.0e5), dt_s=1.0)

        assert output.failure is None
        assert output.achieved_load is not None
        assert output.achieved_load.source == "DATA_DRIVEN_ALLOCATOR"
        assert output.achieved_load.surge_n == pytest.approx(2.1e5)
        assert output.achieved_load.sway_n == pytest.approx(5.0e4)
        assert output.achieved_load.yaw_nm == pytest.approx(1.0e5)
        assert output.achieved_load.roll_nm == 0.0
        details = output.achieved_load.details
        assert details["layout_asset_id"] == "default_triple_actuator_layout_v1"
        assert details["residual"]["surge_n"] == pytest.approx(0.0, abs=1e-6)
        assert details["active_constraints"] == ()
        assert details["degraded"] is False
        assert details["actuator_commands_n"]["main_thruster"] == pytest.approx(2.1e5)
        assert output.navigation.surge_mps > 0.0
        assert stack.modules.allocator_solution() is not None

    def test_feasible_allocation_matches_unallocated_trajectory(self) -> None:
        allocated = _build_stack(_config_with_allocator())
        unallocated = _build_stack(
            {
                "preset": "legacy_equivalent",
                "modules": {
                    "plant": {"identity": "generic_3dof_plant", "parameters": dict(_PLANT_PARAMS)},
                    "guidance": {"identity": "pass_through_guidance", "parameters": {}},
                    "controller": {"identity": "pass_through_controller", "parameters": {}},
                },
            }
        )

        for tick in range(6):
            command = _manual_load_command(tick, 2.1e5, 5.0e4, 1.0e5)
            allocated_output = allocated.step(command, dt_s=0.2)
            unallocated_output = unallocated.step(command, dt_s=0.2)
            assert allocated_output.failure is None
            assert unallocated_output.failure is None
            assert unallocated_output.achieved_load is None
            np.testing.assert_allclose(
                allocated_output.plant.values, unallocated_output.plant.values, rtol=1e-9, atol=1e-9
            )

    def test_default_path_without_allocator_keeps_passthrough_diagnostics(self) -> None:
        stack = _build_stack(
            {
                "preset": "legacy_equivalent",
                "modules": {
                    "plant": {"identity": "generic_3dof_plant", "parameters": dict(_PLANT_PARAMS)},
                    "guidance": {"identity": "pass_through_guidance", "parameters": {}},
                    "controller": {"identity": "pass_through_controller", "parameters": {}},
                },
            }
        )

        output = stack.step(_manual_load_command(0, 2.1e5, 0.0, 0.0), dt_s=1.0)

        assert output.failure is None
        assert output.achieved_load is None
        assert stack.modules.allocator_solution() is None

    def test_allocator_phase_failure_is_structured_and_atomic(self) -> None:
        stack, _ = _build_stack_with_allocator(fail_phase="allocator", fail_tick=1)
        assert stack.step(_manual_load_command(0, 2.1e5, 0.0, 0.0), dt_s=1.0).failure is None
        before = stack.snapshot()

        output = stack.step(CommandInput.none(1), dt_s=1.0)

        assert output.failure is not None
        assert output.failure.code is FailureCode.MODULE_FAILURE
        assert output.failure.phase == "allocator"
        assert stack.tick == 1
        assert stack.snapshot() == before

    def test_allocator_health_snapshot_restore_is_deterministic(self) -> None:
        stack, allocator = _build_stack_with_allocator()
        assert stack.step(_manual_load_command(0, 2.1e5, 0.0, 0.0), dt_s=1.0).failure is None
        before = stack.snapshot()

        allocator.set_actuator_health("bow_tunnel_thruster", 0.0)
        degraded_output = stack.step(CommandInput.none(1), dt_s=1.0)
        assert degraded_output.achieved_load is not None
        assert degraded_output.achieved_load.details["degraded"] is True

        stack.restore(before)
        assert allocator.actuator_health()["bow_tunnel_thruster"] == pytest.approx(1.0)

        reference, _ = _build_stack_with_allocator()
        assert reference.step(_manual_load_command(0, 2.1e5, 0.0, 0.0), dt_s=1.0).failure is None
        reference_output = reference.step(CommandInput.none(1), dt_s=1.0)

        restored_output = stack.step(CommandInput.none(1), dt_s=1.0)

        assert restored_output.achieved_load is not None
        assert restored_output.achieved_load.details["degraded"] is False
        np.testing.assert_allclose(restored_output.plant.values, reference_output.plant.values)

    def test_roll_4dof_stack_never_exposes_roll_channel(self) -> None:
        stack = _build_stack(_config_with_allocator(plant_identity="generic_roll_4dof_plant"))

        output = stack.step(_manual_load_command(0, 2.1e5, 5.0e4, 1.0e5), dt_s=0.2)

        assert output.failure is None
        assert output.plant.values.shape == (8,)
        assert output.achieved_load is not None
        assert output.achieved_load.roll_nm == 0.0
        details = output.achieved_load.details
        assert "roll" not in details["requested"]
        assert "roll" not in details["residual"]
        assert output.plant.roll_rad == 0.0
        assert output.navigation.surge_mps > 0.0

    def test_supported_tasks_with_allocator_is_module_intersection(self) -> None:
        stack = _build_stack(_config_with_allocator())

        assert stack.modules.supported_tasks == frozenset({ControlTask.TRANSIT, ControlTask.MANUAL_LOAD})
