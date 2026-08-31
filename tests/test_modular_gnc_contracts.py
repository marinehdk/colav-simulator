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
