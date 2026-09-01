from __future__ import annotations

import math
from dataclasses import FrozenInstanceError

import numpy as np
import pytest

from colav_simulator.modular_gnc.contracts import (
    CurrentReference,
    CurrentSample,
    EnvironmentObservation,
    EnvironmentStatus,
    EnvironmentTruth,
    MeanDriftSourceSample,
    WaveComponent,
    WaveFieldSample,
    WindSample,
)
from colav_simulator.modular_gnc.environment import AnalyticEnvironmentField


def test_wind_sample_pins_frame_units_to_direction_and_speed() -> None:
    wind = WindSample(velocity_ne=(3.0, 4.0), reference_height_m=10.0)

    assert wind.velocity_ne == (3.0, 4.0)
    assert wind.reference_height_m == 10.0
    assert wind.frame == "NE-to"
    assert wind.units == "m/s,m"
    assert math.isclose(wind.speed_mps, 5.0)
    assert math.isclose(wind.direction_to_rad, math.atan2(4.0, 3.0))

    with pytest.raises(FrozenInstanceError):
        wind.reference_height_m = 12.0


def test_wind_sample_rejects_nonfinite_and_nonpositive_height() -> None:
    with pytest.raises(ValueError, match="finite"):
        WindSample(velocity_ne=(np.nan, 0.0), reference_height_m=10.0)
    with pytest.raises(ValueError, match="positive"):
        WindSample(velocity_ne=(0.0, 0.0), reference_height_m=0.0)
    with pytest.raises(ValueError, match="positive"):
        WindSample(velocity_ne=(0.0, 0.0), reference_height_m=-5.0)


def test_current_sample_pins_reference_enum_and_to_direction() -> None:
    current_surf = CurrentSample(velocity_ne=(0.0, 1.5), reference=CurrentReference.SURFACE)
    assert current_surf.reference is CurrentReference.SURFACE
    assert math.isclose(current_surf.speed_mps, 1.5)
    assert math.isclose(current_surf.direction_to_rad, math.pi / 2.0)

    current_avg = CurrentSample(velocity_ne=(-1.0, 0.0), reference="depth_averaged")
    assert current_avg.reference is CurrentReference.DEPTH_AVERAGED
    assert math.isclose(current_avg.speed_mps, 1.0)
    assert math.isclose(current_avg.direction_to_rad, math.pi)

    with pytest.raises(ValueError, match="CurrentReference"):
        CurrentSample(velocity_ne=(0.0, 0.0), reference="bogus_ref")


def test_wave_component_and_field_sample_pin_properties() -> None:
    comp1 = WaveComponent(amplitude_m=1.2, omega_radps=0.6, phase_rad=0.1, direction_to_rad=0.0)
    comp2 = WaveComponent(amplitude_m=0.8, omega_radps=0.9, phase_rad=0.5, direction_to_rad=math.pi / 4.0)

    with pytest.raises(ValueError, match="amplitude_m must be non-negative"):
        WaveComponent(amplitude_m=-0.1, omega_radps=0.6, phase_rad=0.0, direction_to_rad=0.0)
    with pytest.raises(ValueError, match="omega_radps must be positive"):
        WaveComponent(amplitude_m=1.0, omega_radps=0.0, phase_rad=0.0, direction_to_rad=0.0)

    wave_field = WaveFieldSample(
        significant_height_m=2.5,
        peak_period_s=8.0,
        direction_to_rad=0.2,
        components=(comp1, comp2),
    )
    assert wave_field.significant_height_m == 2.5
    assert wave_field.peak_period_s == 8.0
    assert len(wave_field.components) == 2
    assert wave_field.components[0] == comp1


def test_mean_drift_source_sample_contains_no_vessel_force_or_load() -> None:
    comp = WaveComponent(amplitude_m=1.0, omega_radps=0.7, phase_rad=0.0, direction_to_rad=0.0)
    drift = MeanDriftSourceSample(components=(comp,), directional_spread_rad=0.3)

    assert drift.components == (comp,)
    assert drift.directional_spread_rad == 0.3
    # Verify VR-49-01 / ALT-49-01: no force_ne, no moment, no load attributes
    assert not hasattr(drift, "force_ne")
    assert not hasattr(drift, "load")
    assert not hasattr(drift, "moment")
    assert not hasattr(drift, "vessel_params")


def test_environment_truth_and_observation_type_separation() -> None:
    wind = WindSample(velocity_ne=(5.0, 0.0), reference_height_m=10.0)
    current = CurrentSample(velocity_ne=(0.5, 0.0), reference=CurrentReference.SURFACE)
    comp = WaveComponent(amplitude_m=1.0, omega_radps=0.7, phase_rad=0.0, direction_to_rad=0.0)
    wave = WaveFieldSample(significant_height_m=2.0, peak_period_s=7.0, direction_to_rad=0.0, components=(comp,))
    drift = MeanDriftSourceSample(components=(comp,), directional_spread_rad=0.0)

    truth = EnvironmentTruth(
        wind=wind,
        current=current,
        wave=wave,
        mean_drift=drift,
        time_s=1.0,
        tick=5,
        stage_offset_s=0.0,
    )

    obs = EnvironmentObservation.from_truth(truth, source="PASS_THROUGH", quality=1.0)
    assert obs.status is EnvironmentStatus.AVAILABLE
    assert obs.wind == wind
    assert obs.current == current
    assert obs.wave == wave
    assert obs.mean_drift == drift
    assert obs.source == "PASS_THROUGH"
    assert obs.quality == 1.0
    assert obs.age_s == 0.0

    unavailable_obs = EnvironmentObservation.unavailable(source="RADAR_FAIL", tick=5, time_s=1.0)
    assert unavailable_obs.status is EnvironmentStatus.UNAVAILABLE
    assert unavailable_obs.wind is None
    assert unavailable_obs.quality == 0.0

    # Type separation via constructor rejections (RA-05)
    with pytest.raises(TypeError, match="wind must be WindSample, got EnvironmentObservation"):
        EnvironmentTruth(wind=obs, current=current, wave=wave, mean_drift=drift, tick=0)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="wind must be WindSample or None, got EnvironmentTruth"):
        EnvironmentObservation(wind=truth)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="truth must be EnvironmentTruth"):
        EnvironmentObservation.from_truth(obs)  # type: ignore[arg-type]

    # Real public field API returns strictly separated types
    field = AnalyticEnvironmentField(dt_s=0.1, field_seed=42, wind_velocity_ne=(5.0, 0.0))
    truth_sample = field.sample_at(0, 0.0)
    obs_sample = field.sample_observation(0, 0.0)

    assert isinstance(truth_sample, EnvironmentTruth)
    assert not isinstance(truth_sample, EnvironmentObservation)
    assert isinstance(obs_sample, EnvironmentObservation)
    assert not isinstance(obs_sample, EnvironmentTruth)


def test_environment_contracts_negative_types_and_ticks() -> None:
    wind = WindSample(velocity_ne=(1.0, 1.0), reference_height_m=10.0)
    current = CurrentSample(velocity_ne=(0.2, 0.2))
    comp = WaveComponent(amplitude_m=0.5, omega_radps=1.0, phase_rad=0.0, direction_to_rad=0.0)
    wave = WaveFieldSample(significant_height_m=1.0, peak_period_s=5.0, direction_to_rad=0.0, components=(comp,))
    drift = MeanDriftSourceSample(components=(comp,))

    # Reject bool for tick
    with pytest.raises(TypeError, match="tick must be an integer, got bool"):
        EnvironmentTruth(wind=wind, current=current, wave=wave, mean_drift=drift, tick=True)
    with pytest.raises(TypeError, match="tick must be an integer, got bool"):
        EnvironmentObservation(tick=False)

    # Reject float or non-int for tick
    with pytest.raises(TypeError, match="tick must be an integer"):
        EnvironmentTruth(wind=wind, current=current, wave=wave, mean_drift=drift, tick=2.5)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="tick must be an integer"):
        EnvironmentObservation(tick="not-an-int")  # type: ignore[arg-type]

    # Reject negative ticks
    with pytest.raises(ValueError, match="tick must be non-negative"):
        EnvironmentTruth(wind=wind, current=current, wave=wave, mean_drift=drift, tick=-1)
    with pytest.raises(ValueError, match="tick must be non-negative"):
        EnvironmentObservation(tick=-5)

    # Reject non-WaveComponent items in components
    with pytest.raises(TypeError, match="must be WaveComponent"):
        WaveFieldSample(1.0, 5.0, 0.0, components=(123,))  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="must be WaveComponent"):
        MeanDriftSourceSample(components=[wind])  # type: ignore[list-item]

    # Reject non-sequence for components
    with pytest.raises(TypeError, match="must be a sequence of WaveComponent"):
        WaveFieldSample(1.0, 5.0, 0.0, components=123)  # type: ignore[arg-type]

    # Reject empty string source
    with pytest.raises(ValueError, match="source must be a non-empty string"):
        EnvironmentObservation(source="")
