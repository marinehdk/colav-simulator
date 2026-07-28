import pytest

from colav_simulator.core.colav.diagnostics import ColavExecutionError, PlanStatus
from colav_simulator.integrations import IntegrationRegistry


def test_registry_reports_all_ecosystem_dependencies_truthfully() -> None:
    statuses = IntegrationRegistry().statuses()
    assert {"vimmjipda", "psbmpc", "sbmpc_reference", "rrt", "rlmpc"}.issubset(statuses)
    for identifier in ("vimmjipda", "psbmpc", "sbmpc_reference", "rrt", "rlmpc"):
        status = statuses[identifier]
        assert status.integration_id == identifier
        if status.available:
            assert status.source
        else:
            assert status.reason


def test_unavailable_algorithm_never_falls_back() -> None:
    registry = IntegrationRegistry()
    unavailable = next(
        (
            name
            for name in ("psbmpc", "sbmpc_reference", "rrt", "rlmpc")
            if not registry.statuses()[name].available
        ),
        None,
    )
    if unavailable is None:
        assert all(
            registry.statuses()[name].available
            for name in ("psbmpc", "sbmpc_reference", "rrt", "rlmpc")
        )
        return
    with pytest.raises(ColavExecutionError) as error:
        registry.build_algorithm(unavailable)
    assert error.value.status == PlanStatus.DEPENDENCY_UNAVAILABLE
