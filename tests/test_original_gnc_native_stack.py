"""Optional native-library lifecycle and source-scheduler integration guards."""

from __future__ import annotations

import copy
import json
from collections import Counter

import pytest

from colav_simulator.original_gnc.configuration import OriginalGncConfig
from colav_simulator.original_gnc.native import OriginalGncError, verify_build
from colav_simulator.original_gnc.stack import NativeStack


@pytest.fixture
def original_config() -> OriginalGncConfig:
    config = OriginalGncConfig.from_dict({})
    if not (config.build_directory / "build-manifest.json").exists():
        pytest.skip("Optional original GNC native library is not built")
    return config


def stack_for(config, trace=None, enabled_environment=()) -> NativeStack:
    roots, assets, policy = config.source_assets()
    return NativeStack(
        config.build_directory,
        config.parameters(),
        roots,
        policy,
        asset_paths=assets,
        trace=trace,
        enabled_environment=enabled_environment,
    )


def test_original_periods_and_fractional_outer_steps(original_config):
    calls = []
    with stack_for(original_config, calls.append) as stack:
        stack.advance(0.13)
        stack.advance(0.17)
        stack.advance(0.7)
        counts = Counter((e["node"], e["callback"]) for e in calls if e["event"] == "call")
        assert counts["ship_dynamics_node", "update_dynamics"] == 50
        assert counts["ship_control_node", "control_loop"] == 10
        assert counts["ship_guidance_node", "control_loop"] == 2
        assert counts["propulsion_policy_node", "_tick"] == 2
        assert stack.elapsed_s == 1.0
        assert "thrust_allocation_node" in stack.modules
        assert stack.modules["thrust_allocation_node"].describe()["timers"] == {}


@pytest.mark.parametrize("engines", [(), ("wind", "current", "wave")])
def test_interleaved_vessels_and_step_partition_preserve_independent_state(original_config, engines):
    with (
        stack_for(original_config, enabled_environment=engines) as first,
        stack_for(original_config, enabled_environment=engines) as second,
    ):
        first.advance(0.51)
        untouched = copy.deepcopy(second.states)
        first.advance(0.49)
        assert second.states == untouched
        second.advance(1.0)
        assert first.states == second.states
        assert first.latest == second.latest
    with stack_for(original_config, enabled_environment=engines) as fresh:
        fresh.advance(1.0)
        assert fresh.states == first.states


def test_closed_native_stack_cannot_run_or_publish(original_config):
    stack = stack_for(original_config)
    stack.close()
    with pytest.raises(OriginalGncError, match="closed"):
        stack.advance(0.1)
    with pytest.raises(OriginalGncError, match="closed"):
        stack.publish("/route_planning/route_plan", "ship_interfaces/msg/RoutePlan", {})


def test_changed_extraction_is_rejected_before_dynamic_loading(tmp_path):
    (tmp_path / "extraction.json").write_text("{}")
    (tmp_path / "build-manifest.json").write_text(json.dumps({"extraction_sha256": "wrong"}))
    with pytest.raises(OriginalGncError, match="extraction changed"):
        verify_build(tmp_path)


def test_native_failure_does_not_run_another_stack(original_config):
    with stack_for(original_config) as stack:
        module = stack.modules["ship_dynamics_node"]
        with pytest.raises(OriginalGncError, match="Unknown original callback"):
            module.invoke("unknown_callback", None, stack.time_ns)
        with pytest.raises(OriginalGncError, match="No original input port"):
            stack.publish("/nonexistent", "std_msgs/msg/String", {"data": "test"})


def test_callback_exception_closes_partial_state_and_allows_fresh_episode(original_config, monkeypatch):
    stack = stack_for(original_config)

    def fail(*_args):
        raise OriginalGncError("injected native callback failure")

    monkeypatch.setattr(stack.modules["ship_dynamics_node"], "invoke", fail)
    with pytest.raises(OriginalGncError, match="injected native"):
        stack.advance(0.1)
    assert stack.modules == {}
    assert stack.policy is None
    with pytest.raises(OriginalGncError, match="closed"):
        stack.advance(0.1)
    with stack_for(original_config) as fresh:
        fresh.advance(0.1)
        assert fresh.elapsed_s == 0.1


def test_default_observers_do_not_change_executing_core(original_config, monkeypatch):
    with stack_for(original_config) as observed:
        observed.advance(5.0)
        expected = copy.deepcopy(observed.states)
        expected_outputs = {
            key: copy.deepcopy(observed.latest[key])
            for key in ("/ship/odometry", "/cmd_tau", "/thruster/commands", "/propulsion/constraints")
        }
    monkeypatch.setattr("colav_simulator.original_gnc.stack.observer_parameters", lambda _roots: {})
    with stack_for(original_config) as core:
        core.advance(5.0)
        assert core.states == expected
        assert {key: core.latest[key] for key in expected_outputs} == expected_outputs
