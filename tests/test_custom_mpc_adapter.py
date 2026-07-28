from pathlib import Path

import numpy as np
import pytest

from colav_simulator.core.colav.custom_mpc_adapter import (
    CustomMPCAdapter,
    FactoryContext,
    MPCSolution,
    PlannerInput,
)
from colav_simulator.core.colav.diagnostics import ColavExecutionError, PlanStatus
from colav_simulator.integrations import IntegrationRegistry


def plugin_config() -> dict:
    return {
        "factory": "examples.custom_mpc_plugin:create",
        "dependency_lock": str(Path("uv.lock").resolve()),
        "kwargs": {
            "horizon_steps": 5,
            "horizon_dt_s": 0.5,
            "solve_period_s": 1.0,
        },
    }


def plan(adapter: CustomMPCAdapter, t: float) -> np.ndarray:
    return adapter.plan(
        t,
        np.array([[0.0, 100.0], [0.0, 0.0]]),
        np.array([4.0, 4.0]),
        np.array([0.0, 0.0, 0.0, 4.0, 0.0, 0.0]),
        [],
        dt=0.5,
    )


def test_registry_loads_strict_adapter_and_records_complete_identity() -> None:
    context = FactoryContext("custom_mpc_example", algorithm_seed=22)
    adapter = IntegrationRegistry().build_algorithm(
        "custom_mpc_example",
        plugin_config(),
        factory_context=context,
    )

    assert isinstance(adapter, CustomMPCAdapter)
    assert adapter.descriptor.algorithm_id == "custom_mpc_example"
    assert adapter.build_identity.complete is True
    assert adapter.get_diagnostics().fallback_used is False
    plan(adapter, 0.0)
    assert adapter.get_current_plan().shape == (9, 5)


def test_adapter_solves_at_t0_and_holds_without_incrementing_solve_id() -> None:
    adapter = IntegrationRegistry().build_algorithm(
        "custom_mpc_example",
        plugin_config(),
        factory_context=FactoryContext("custom_mpc_example", 22),
    )
    assert isinstance(adapter, CustomMPCAdapter)

    first = plan(adapter, 0.0)
    first_trace = adapter.get_colav_data()["planner"]
    held = plan(adapter, 0.5)
    held_trace = adapter.get_colav_data()["planner"]
    second = plan(adapter, 1.0)
    second_trace = adapter.get_colav_data()["planner"]

    assert first.shape == held.shape == second.shape == (9, 1)
    assert (first_trace["solve_id"], first_trace["solver_executed"]) == (1, True)
    assert (held_trace["solve_id"], held_trace["solver_executed"]) == (1, False)
    assert (second_trace["solve_id"], second_trace["solver_executed"]) == (2, True)
    assert held_trace["algorithm_details"]["solve_time_s"] == 0.0


def test_adapter_reset_restores_cold_start_solve_id() -> None:
    adapter = IntegrationRegistry().build_algorithm(
        "custom_mpc_example",
        plugin_config(),
        factory_context=FactoryContext("custom_mpc_example", 22),
    )
    assert isinstance(adapter, CustomMPCAdapter)
    plan(adapter, 0.0)
    adapter.reset()
    plan(adapter, 0.0)
    assert adapter.get_colav_data()["planner"]["solve_id"] == 1


def test_registry_rejects_missing_dependency_and_non_adapter_factory() -> None:
    config = plugin_config()
    config["dependency_lock"] = "missing.lock"
    with pytest.raises(ColavExecutionError) as missing:
        IntegrationRegistry().build_algorithm(
            "custom_mpc_example",
            config,
            factory_context=FactoryContext("custom_mpc_example", 0),
        )
    assert missing.value.status == PlanStatus.INVALID_INPUT

    with pytest.raises(ColavExecutionError) as invalid:
        IntegrationRegistry().build_algorithm(
            "custom_mpc_example",
            {"factory": "pathlib:Path", "kwargs": {"pathsegments": []}},
            factory_context=FactoryContext("custom_mpc_example", 0),
        )
    assert invalid.value.status == PlanStatus.INVALID_INPUT


def test_registry_maps_missing_plugin_module_to_dependency_unavailable() -> None:
    with pytest.raises(ColavExecutionError) as error:
        IntegrationRegistry().build_algorithm(
            "missing_mpc",
            {"factory": "not_installed_mpc:create"},
            factory_context=FactoryContext("missing_mpc", 0),
        )
    assert error.value.status == PlanStatus.DEPENDENCY_UNAVAILABLE


def test_adapter_rejects_non_integer_solve_period_ratio() -> None:
    config = plugin_config()
    config["kwargs"]["solve_period_s"] = 0.75
    adapter = IntegrationRegistry().build_algorithm(
        "custom_mpc_example",
        config,
        factory_context=FactoryContext("custom_mpc_example", 0),
    )
    assert isinstance(adapter, CustomMPCAdapter)
    with pytest.raises(ColavExecutionError) as error:
        plan(adapter, 0.0)
    assert error.value.status == PlanStatus.INVALID_INPUT


def test_adapter_marks_track_quality_and_rejects_stale_tracks() -> None:
    captured = []
    adapter = IntegrationRegistry().build_algorithm(
        "custom_mpc_example",
        plugin_config(),
        factory_context=FactoryContext("custom_mpc_example", 0),
    )
    assert isinstance(adapter, CustomMPCAdapter)
    original_solve = adapter._solve

    def capture(value: PlannerInput) -> MPCSolution:
        captured.append(value)
        return original_solve(value)

    adapter._solve = capture
    track = (4, np.zeros(4), np.eye(4), 8.0, 3.0)
    adapter.plan(
        2.0,
        np.array([[0.0, 100.0], [0.0, 0.0]]),
        np.array([4.0, 4.0]),
        np.array([0.0, 0.0, 0.0, 4.0, 0.0, 0.0]),
        [track],
        dt=0.5,
        track_ages_s={4: 2.0},
    )
    assert captured[0].tracks[0].degraded is True
    assert captured[0].tracks[0].observed_at_s == 0.0

    adapter.reset()
    with pytest.raises(ColavExecutionError, match="exceeds profile maximum") as error:
        adapter.plan(
            6.0,
            np.array([[0.0, 100.0], [0.0, 0.0]]),
            np.array([4.0, 4.0]),
            np.array([0.0, 0.0, 0.0, 4.0, 0.0, 0.0]),
            [track],
            dt=0.5,
            track_ages_s={4: 6.0},
        )
    assert error.value.status == PlanStatus.INVALID_INPUT
