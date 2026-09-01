from __future__ import annotations

import math

from colav_simulator.modular_gnc.configuration import ShipModulesConfig, normalize_ship_modules
from colav_simulator.modular_gnc.contracts import (
    CommandInput,
    EnvironmentObservation,
    EnvironmentStatus,
    EnvironmentTruth,
    NavigationState,
)
from colav_simulator.modular_gnc.stack import ModularShipStack


def _env_config(plant_period: int = 1, available: bool = True) -> ShipModulesConfig:
    return normalize_ship_modules(
        {
            "preset": "legacy_equivalent",
            "overrides": {"scheduler": {"plant_period_ticks": plant_period, "controller_period_ticks": 5}},
            "modules": {
                "plant": {"identity": "pass_through_plant", "parameters": {}},
                "guidance": {"identity": "pass_through_guidance", "parameters": {}},
                "controller": {"identity": "pass_through_controller", "parameters": {}},
                "environment": {
                    "identity": "analytic_environment_field",
                    "parameters": {
                        "wind_velocity_ne": [4.0, 3.0],
                        "wind_reference_height_m": 10.0,
                        "wind_perturbation_std": [0.2, 0.2],
                        "current_velocity_ne": [0.3, -0.4],
                        "current_reference": "surface",
                        "current_perturbation_std": [0.05, 0.05],
                        "wave_significant_height_m": 1.8,
                        "wave_peak_period_s": 7.5,
                        "wave_direction_to_rad": 0.4,
                        "wave_num_components": 12,
                        "wave_directional_spread_rad": 0.1,
                        "available": available,
                    },
                },
            },
        }
    )


def _initial() -> NavigationState:
    return NavigationState(50.0, 100.0, 0.2, 5.0, 0.0, 0.0)


def test_stack_environment_lifecycle_reset_snapshot_restore() -> None:
    config = _env_config()
    stack = ModularShipStack.from_config(config, episode_seed=42, dt_s=0.1)

    # Initial reset
    stack.reset(_initial(), seed=10)
    truth_0 = stack.modules.environment_truth()
    obs_0 = stack.modules.environment_observation()

    assert isinstance(truth_0, EnvironmentTruth)
    assert isinstance(obs_0, EnvironmentObservation)
    assert obs_0.status is EnvironmentStatus.AVAILABLE
    assert math.isclose(obs_0.wind.reference_height_m, 10.0)

    # Step forward 3 ticks
    out_0 = stack.step(CommandInput.none(0), dt_s=0.1)
    out_1 = stack.step(CommandInput.none(1), dt_s=0.1)
    out_2 = stack.step(CommandInput.none(2), dt_s=0.1)

    assert out_0.environment_observation is not None
    assert out_1.environment_observation is not None
    assert out_2.environment_observation is not None
    assert out_2.environment_observation.tick == 2

    # Snapshot and step to tick 3
    snapshot = stack.snapshot()
    out_3 = stack.step(CommandInput.none(3), dt_s=0.1)

    # Restore snapshot and verify step 3 replay matches bitwise
    stack.restore(snapshot)
    out_3_replay = stack.step(CommandInput.none(3), dt_s=0.1)
    assert out_3.environment_observation == out_3_replay.environment_observation
    assert out_3.navigation == out_3_replay.navigation

    # Reset idempotence
    stack.reset(_initial(), seed=10)
    assert stack.modules.environment_truth() == truth_0
    assert stack.modules.environment_observation() == obs_0


def test_stack_environment_cadence_due_phase_zoh() -> None:
    # Environment phase due every 2 ticks
    config = _env_config(plant_period=2)
    stack = ModularShipStack.from_config(config, episode_seed=99, dt_s=0.1)
    stack.reset(_initial(), seed=1)

    out_0 = stack.step(CommandInput.none(0), dt_s=0.1)
    assert dict(stack.modules.snapshot().phase_counts)["environment"] == 1
    obs_tick_0 = out_0.environment_observation

    out_1 = stack.step(CommandInput.none(1), dt_s=0.1)
    # At tick 1 (not due), phase count remains 1, held observation is retained via ZOH
    assert dict(stack.modules.snapshot().phase_counts)["environment"] == 1
    assert out_1.environment_observation == obs_tick_0

    out_2 = stack.step(CommandInput.none(2), dt_s=0.1)
    # At tick 2 (due), phase count increments to 2, new observation sampled
    assert dict(stack.modules.snapshot().phase_counts)["environment"] == 2
    assert out_2.environment_observation is not None
    assert out_2.environment_observation.tick == 2


def test_multi_ship_permutation_invariance_and_seed_isolation() -> None:
    config = _env_config()
    episode_seed = 12345

    # Instantiate two ships with identical episode seed and config, different ship seeds
    ship1_a = ModularShipStack.from_config(config, episode_seed=episode_seed, dt_s=0.1)
    ship2_a = ModularShipStack.from_config(config, episode_seed=episode_seed, dt_s=0.1)
    ship1_a.reset(NavigationState(0.0, 0.0, 0.0, 2.0, 0.0, 0.0), seed=101)
    ship2_a.reset(NavigationState(100.0, 200.0, 0.5, 3.0, 0.0, 0.0), seed=102)

    # Order A: Ship 1 steps 0, 1; Ship 2 steps 0, 1
    s1_trace = [ship1_a.step(CommandInput.none(t), dt_s=0.1) for t in range(3)]
    s2_trace = [ship2_a.step(CommandInput.none(t), dt_s=0.1) for t in range(3)]

    # Order B: Reverse execution order on new instances
    ship1_b = ModularShipStack.from_config(config, episode_seed=episode_seed, dt_s=0.1)
    ship2_b = ModularShipStack.from_config(config, episode_seed=episode_seed, dt_s=0.1)
    ship2_b.reset(NavigationState(100.0, 200.0, 0.5, 3.0, 0.0, 0.0), seed=102)
    ship1_b.reset(NavigationState(0.0, 0.0, 0.0, 2.0, 0.0, 0.0), seed=101)

    s2_trace_rev = [ship2_b.step(CommandInput.none(t), dt_s=0.1) for t in range(3)]
    s1_trace_rev = [ship1_b.step(CommandInput.none(t), dt_s=0.1) for t in range(3)]

    assert s1_trace == s1_trace_rev
    assert s2_trace == s2_trace_rev


def test_unavailable_environment_reports_structured_unavailable_observation() -> None:
    config = _env_config(available=False)
    stack = ModularShipStack.from_config(config, episode_seed=42, dt_s=0.1)
    stack.reset(_initial(), seed=1)

    out = stack.step(CommandInput.none(0), dt_s=0.1)
    obs = out.environment_observation

    assert obs is not None
    assert obs.status is EnvironmentStatus.UNAVAILABLE
    assert obs.wind is None
    assert obs.current is None
    assert obs.wave is None
    assert obs.quality == 0.0


def test_backward_compatible_passthrough_when_no_environment_configured() -> None:
    config = normalize_ship_modules(
        {
            "preset": "legacy_equivalent",
            "modules": {
                "plant": {"identity": "pass_through_plant", "parameters": {}},
                "guidance": {"identity": "pass_through_guidance", "parameters": {}},
                "controller": {"identity": "pass_through_controller", "parameters": {}},
            },
        }
    )
    stack = ModularShipStack.from_config(config)
    stack.reset(_initial(), seed=1)

    out = stack.step(CommandInput.none(0), dt_s=0.1)
    assert out.environment_observation is None
    assert stack.modules.environment_truth() is None
    assert stack.modules.environment_observation() is None
