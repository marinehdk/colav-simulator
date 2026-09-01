from __future__ import annotations

from dataclasses import FrozenInstanceError

import numpy as np
import pytest

from colav_simulator.modular_gnc.contracts import (
    CommandInput,
    ControlTask,
    DirectReference,
    FacadeFailure,
    FailureCode,
    NavigationSource,
    NavigationState,
    PlantInputSemantics,
    PlantState,
    StackOutput,
    StackSnapshot,
    TrackedRoute,
    canonicalize_plant_input_semantics,
)


def test_navigation_state_pins_frames_units_signs_and_truth_source() -> None:
    navigation = NavigationState(
        north_m=1.0,
        east_m=2.0,
        heading_rad=np.pi / 2.0,
        surge_mps=3.0,
        sway_mps=0.5,
        yaw_rate_radps=0.1,
        source=NavigationSource.TRUTH_PROJECTION,
    )

    np.testing.assert_array_equal(
        navigation.as_array(),
        np.array([1.0, 2.0, np.pi / 2.0, 3.0, 0.5, 0.1], dtype=np.float64),
    )
    assert navigation.frame == "NE/body-forward-starboard-down"
    assert navigation.units == "m,rad,m/s,rad/s"
    assert navigation.heading_positive == "right"
    with pytest.raises(FrozenInstanceError):
        navigation.north_m = 3.0


def test_navigation_state_coerces_valid_source_and_rejects_bogus_values() -> None:
    navigation = NavigationState(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, source="ESTIMATE")

    assert navigation.source is NavigationSource.ESTIMATE
    with pytest.raises(ValueError, match="NavigationSource"):
        NavigationState(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, source="BOGUS")


def test_contracts_reject_nonfinite_and_wrong_shapes() -> None:
    with pytest.raises(ValueError, match="finite"):
        NavigationState(0.0, 0.0, 0.0, np.nan, 0.0, 0.0)
    with pytest.raises(ValueError, match="shape"):
        PlantState(values=np.zeros(5), capabilities=frozenset({"PLANAR_3DOF"}))
    with pytest.raises(ValueError, match="shape"):
        DirectReference(values=np.zeros(8), latched_tick=0)


def test_plant_state_is_float64_immutable_and_capability_aware() -> None:
    values = np.arange(6, dtype=np.float32)
    state = PlantState(values=values, capabilities=frozenset({"PLANAR_3DOF"}))

    assert state.values.dtype == np.float64
    assert state.values.flags.writeable is False
    values[0] = 99.0
    assert state.values[0] == 0.0
    assert state.input_semantics is PlantInputSemantics.GENERALIZED_FORCE

    # 4DOF PlantState requires 8 values and supports property getters
    values_4dof = np.array([1.0, 2.0, 0.3, 0.04, 3.0, 0.1, 0.005, 0.02])
    state_4dof = PlantState(
        values=values_4dof,
        capabilities=frozenset({"ROLL_4DOF", "GENERALIZED_FORCE"}),
        input_semantics=PlantInputSemantics.GENERALIZED_FORCE,
    )
    assert state_4dof.values.shape == (8,)
    assert state_4dof.north_m == 1.0
    assert state_4dof.east_m == 2.0
    assert state_4dof.heading_rad == 0.3
    assert state_4dof.roll_rad == 0.04
    assert state_4dof.surge_mps == 3.0
    assert state_4dof.sway_mps == 0.1
    assert state_4dof.roll_rate_radps == 0.005
    assert state_4dof.yaw_rate_radps == 0.02

    # Projection to 3DOF NavigationState
    nav_proj = state_4dof.to_navigation_state()
    assert nav_proj.as_array().shape == (6,)
    assert nav_proj.north_m == 1.0
    assert nav_proj.east_m == 2.0
    assert nav_proj.heading_rad == 0.3
    assert nav_proj.surge_mps == 3.0
    assert nav_proj.sway_mps == 0.1
    assert nav_proj.yaw_rate_radps == 0.02


def test_command_input_is_discriminated_and_authority_is_mutually_exclusive() -> None:
    direct = DirectReference(values=np.arange(9), latched_tick=4)
    route = TrackedRoute(
        route_id="route-1",
        revision=2,
        accepted=True,
        valid_from_tick=4,
        valid_until_tick=10,
        waypoints_ne_m=np.array([[0.0, 10.0], [0.0, 5.0]]),
        speed_mps=np.array([2.0, 3.0]),
        task=ControlTask.TRANSIT,
    )

    assert CommandInput.none(tick=3).authority == "NONE"
    assert CommandInput.direct(tick=4, reference=direct).authority == "DIRECT_REFERENCE"
    assert CommandInput.route(tick=4, route=route).authority == "TRACKED_ROUTE"
    with pytest.raises(ValueError, match="mutually exclusive"):
        CommandInput(tick=4, direct_reference=direct, tracked_route=route)


def test_snapshot_output_and_failure_pin_schema() -> None:
    navigation = NavigationState(0.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    plant = PlantState(np.zeros(6), frozenset({"PLANAR_3DOF"}))
    failure = FacadeFailure(
        code=FailureCode.STALE_INPUT,
        message="stale command",
        phase="guidance",
        tick=2,
        details={"received_tick": 1},
    )
    output = StackOutput(tick=2, navigation=navigation, plant=plant, applied_reference=None, failure=failure)
    snapshot = StackSnapshot(
        schema_version="modular-ship-stack.snapshot.v1",
        config_hash="a" * 64,
        tick=2,
        seed=9,
        module_snapshots=(plant,),
        held_command=None,
    )

    assert output.failure.code is FailureCode.STALE_INPUT
    assert snapshot.schema_version == "modular-ship-stack.snapshot.v1"
    assert snapshot.module_snapshots[0] == plant


def test_plant_input_semantics_canonicalization_and_compatibility_aliases() -> None:
    """Validate canonicalization of REFERENCE_CHI_U while accepting KINEMATIC_REFERENCE alias."""
    assert PlantInputSemantics.REFERENCE_CHI_U.canonical() is PlantInputSemantics.REFERENCE_CHI_U
    assert PlantInputSemantics.GENERALIZED_FORCE.canonical() is PlantInputSemantics.GENERALIZED_FORCE
    # Legacy KINEMATIC_REFERENCE aliases to REFERENCE_CHI_U
    assert PlantInputSemantics.KINEMATIC_REFERENCE.canonical() is PlantInputSemantics.REFERENCE_CHI_U

    # Helper function accepts strings and enum members
    assert canonicalize_plant_input_semantics("REFERENCE_CHI_U") is PlantInputSemantics.REFERENCE_CHI_U
    assert canonicalize_plant_input_semantics("KINEMATIC_REFERENCE") is PlantInputSemantics.REFERENCE_CHI_U
    assert canonicalize_plant_input_semantics("GENERALIZED_FORCE") is PlantInputSemantics.GENERALIZED_FORCE
    assert canonicalize_plant_input_semantics(PlantInputSemantics.KINEMATIC_REFERENCE) is PlantInputSemantics.REFERENCE_CHI_U
