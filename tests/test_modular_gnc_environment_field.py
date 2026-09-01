from __future__ import annotations

import math
import time

import pytest

from colav_simulator.modular_gnc.contracts import (
    CurrentReference,
    EnvironmentObservation,
    EnvironmentStatus,
    EnvironmentTruth,
    MeanDriftSourceSample,
    WaveFieldSample,
    WindSample,
)
from colav_simulator.modular_gnc.environment import (
    AnalyticEnvironmentField,
    derive_prf_seed,
    prf_gaussian,
    prf_uniform,
)


def test_derive_prf_seed_is_deterministic_and_isolated() -> None:
    seed1 = derive_prf_seed(42, "environment_field")
    seed2 = derive_prf_seed(42, "environment_field")
    seed3 = derive_prf_seed(42, "other_domain")
    seed4 = derive_prf_seed(43, "environment_field")

    assert seed1 == seed2
    assert seed1 != seed3
    assert seed1 != seed4
    assert isinstance(seed1, int)
    assert seed1 >= 0


def test_prf_uniform_and_gaussian_are_stateless_and_reproducible() -> None:
    u1 = prf_uniform(12345, tick=10, channel="wind_n")
    u2 = prf_uniform(12345, tick=10, channel="wind_n")
    u3 = prf_uniform(12345, tick=11, channel="wind_n")

    assert u1 == u2
    assert u1 != u3
    assert 0.0 <= u1 < 1.0

    g1 = prf_gaussian(12345, tick=10, channel="wind_n")
    g2 = prf_gaussian(12345, tick=10, channel="wind_n")
    g3 = prf_gaussian(12345, tick=11, channel="wind_n")

    assert g1 == g2
    assert g1 != g3
    assert math.isfinite(g1)


def test_analytic_environment_field_sample_at_exact_time_and_stage_offset() -> None:
    field = AnalyticEnvironmentField(
        dt_s=0.1,
        field_seed=777,
        wind_velocity_ne=(5.0, 2.0),
        wind_reference_height_m=10.0,
        wind_perturbation_std=(0.5, 0.5),
        current_velocity_ne=(0.3, 0.4),
        current_reference=CurrentReference.SURFACE,
        current_perturbation_std=(0.1, 0.1),
        wave_significant_height_m=1.5,
        wave_peak_period_s=6.0,
        wave_direction_to_rad=0.5,
        wave_num_components=8,
        wave_directional_spread_rad=0.2,
    )

    truth = field.sample_at(tick=10, stage_offset_s=0.05, position_ne=(100.0, 200.0))

    assert isinstance(truth, EnvironmentTruth)
    assert truth.tick == 10
    assert truth.stage_offset_s == 0.05
    assert math.isclose(truth.time_s, 1.05)

    assert isinstance(truth.wind, WindSample)
    assert isinstance(truth.wave, WaveFieldSample)
    assert len(truth.wave.components) == 8
    assert isinstance(truth.mean_drift, MeanDriftSourceSample)
    assert truth.mean_drift.components == truth.wave.components
    assert truth.mean_drift.directional_spread_rad == 0.2

    # Querying out-of-order must yield identical results (statelessness)
    truth_prior = field.sample_at(tick=5, stage_offset_s=0.0)
    truth_again = field.sample_at(tick=10, stage_offset_s=0.05, position_ne=(100.0, 200.0))
    assert truth == truth_again
    assert truth_prior.tick == 5


def test_analytic_environment_field_validates_stage_offset_and_ticks() -> None:
    field = AnalyticEnvironmentField(dt_s=0.1, field_seed=123)

    with pytest.raises(ValueError, match="tick must be non-negative"):
        field.sample_at(tick=-1, stage_offset_s=0.0)

    with pytest.raises(ValueError, match="stage_offset_s must be in"):
        field.sample_at(tick=0, stage_offset_s=-0.01)

    with pytest.raises(ValueError, match="stage_offset_s must be in"):
        field.sample_at(tick=0, stage_offset_s=0.1)

    with pytest.raises(ValueError, match="stage_offset_s must be in"):
        field.sample_at(tick=0, stage_offset_s=0.15)


def test_analytic_environment_field_observation_and_unavailability() -> None:
    field_avail = AnalyticEnvironmentField(dt_s=0.2, field_seed=42, wind_velocity_ne=(4.0, 0.0), available=True)
    obs_avail = field_avail.sample_observation(tick=2, stage_offset_s=0.0)

    assert isinstance(obs_avail, EnvironmentObservation)
    assert obs_avail.status is EnvironmentStatus.AVAILABLE
    assert obs_avail.wind is not None
    assert math.isclose(obs_avail.wind.speed_mps, 4.0)

    field_unavail = AnalyticEnvironmentField(dt_s=0.2, field_seed=42, available=False)
    obs_unavail = field_unavail.sample_observation(tick=2, stage_offset_s=0.0)

    assert isinstance(obs_unavail, EnvironmentObservation)
    assert obs_unavail.status is EnvironmentStatus.UNAVAILABLE
    assert obs_unavail.wind is None
    assert obs_unavail.quality == 0.0


def test_multi_ship_order_independent_field_queries() -> None:
    field = AnalyticEnvironmentField(
        dt_s=0.05,
        field_seed=9999,
        wind_velocity_ne=(10.0, 0.0),
        wind_perturbation_std=(1.0, 1.0),
    )

    # Order 1: Ship A (tick 0, 1, 2) then Ship B (tick 0, 1, 2)
    res_a_0 = field.sample_at(tick=0, stage_offset_s=0.0, position_ne=(0.0, 0.0))
    res_a_1 = field.sample_at(tick=1, stage_offset_s=0.0, position_ne=(10.0, 0.0))
    res_b_0 = field.sample_at(tick=0, stage_offset_s=0.0, position_ne=(50.0, 50.0))
    res_b_1 = field.sample_at(tick=1, stage_offset_s=0.0, position_ne=(60.0, 50.0))

    # Order 2: Reverse order on a fresh field constructed with same seed
    field_rebuilt = AnalyticEnvironmentField(
        dt_s=0.05,
        field_seed=9999,
        wind_velocity_ne=(10.0, 0.0),
        wind_perturbation_std=(1.0, 1.0),
    )
    res_b_1_rev = field_rebuilt.sample_at(tick=1, stage_offset_s=0.0, position_ne=(60.0, 50.0))
    res_a_0_rev = field_rebuilt.sample_at(tick=0, stage_offset_s=0.0, position_ne=(0.0, 0.0))
    res_b_0_rev = field_rebuilt.sample_at(tick=0, stage_offset_s=0.0, position_ne=(50.0, 50.0))
    res_a_1_rev = field_rebuilt.sample_at(tick=1, stage_offset_s=0.0, position_ne=(10.0, 0.0))

    assert res_a_0 == res_a_0_rev
    assert res_a_1 == res_a_1_rev
    assert res_b_0 == res_b_0_rev
    assert res_b_1 == res_b_1_rev


def test_zero_wall_clock_or_random_device_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden_time() -> float:
        raise AssertionError("wall-clock time accessed during environment query")

    monkeypatch.setattr(time, "time", forbidden_time)
    monkeypatch.setattr(time, "monotonic", forbidden_time)

    field = AnalyticEnvironmentField.from_params(
        params={
            "wind_velocity_ne": [6.0, -2.0],
            "wind_perturbation_std": [0.2, 0.2],
            "current_velocity_ne": [0.5, 0.1],
            "wave_significant_height_m": 2.0,
            "wave_peak_period_s": 7.0,
            "wave_num_components": 10,
        },
        dt_s=0.1,
        episode_seed=12345,
    )

    sample = field.sample_at(tick=4, stage_offset_s=0.02, position_ne=(10.0, 20.0))
    assert math.isclose(sample.time_s, 0.42)
