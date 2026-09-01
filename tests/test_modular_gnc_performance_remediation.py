"""Tests for Issue #65 Python performance remediation slices and numerical equivalence."""

from __future__ import annotations

import hashlib
import unittest.mock
import pytest

from colav_simulator.modular_gnc.contracts import (
    AssetIntegrityError,
    AssetMetadata,
    AssetMissingError,
    AssetTrustLevel,
    CurrentStrategy,
    EnvironmentTruth,
    NavigationState,
    VesselLoad,
    WaveComponent,
    WaveFieldSample,
    WaveLoadMode,
    MeanDriftSourceSample,
    WindSample,
    CurrentSample,
)
from colav_simulator.modular_gnc.load_model import (
    DEFAULT_INFERRED_WAVE_DRIFT_ASSET,
    DEFAULT_INFERRED_WAVE_RESPONSE_ASSET,
    EnvironmentalLoadModel,
    FirstOrderWaveLoadModel,
    InferredWaveDriftAsset,
    InferredWaveResponseAsset,
    MeanDriftLoadModel,
    VesselEnvironmentalParameters,
)


@pytest.fixture
def standard_vessel_params() -> VesselEnvironmentalParameters:
    return VesselEnvironmentalParameters(
        length_between_perpendiculars_m=44.1,
        beam_m=8.0,
        draft_m=1.55,
        wind_frontal_area_m2=50.0,
        wind_lateral_area_m2=150.0,
        wind_z_center_m=3.0,
        air_density_kg_m3=1.225,
        water_depth_m=50.0,
        kg_m=2.0,
        water_density_kg_m3=1025.0,
    )


def test_slice1_asset_integrity_cached_and_verified_once(standard_vessel_params: VesselEnvironmentalParameters) -> None:
    """Slice 1: Valid assets are verified once and repeated calculations do not rehash."""
    asset = DEFAULT_INFERRED_WAVE_RESPONSE_ASSET
    assert asset.verify_integrity()

    # Verify that calling verify_integrity again uses cache
    with unittest.mock.patch("hashlib.sha256", wraps=hashlib.sha256) as mock_sha:
        assert asset.verify_integrity()
        assert mock_sha.call_count == 0

    # Test load model construction verifies wave asset
    model = EnvironmentalLoadModel(
        vessel_params=standard_vessel_params,
        wave_mode=WaveLoadMode.BOTH,
        wave_first_order_asset=DEFAULT_INFERRED_WAVE_RESPONSE_ASSET,
        wave_mean_drift_asset=DEFAULT_INFERRED_WAVE_DRIFT_ASSET,
    )
    assert model.wave_first_order_asset is not None

    # Repeated calculate calls do not invoke sha256
    comp = WaveComponent(amplitude_m=1.0, omega_radps=0.7, phase_rad=0.0, direction_to_rad=0.0)
    wave = WaveFieldSample(significant_height_m=2.0, peak_period_s=8.0, direction_to_rad=0.0, components=(comp,))
    truth = EnvironmentTruth(
        wind=WindSample(velocity_ne=(0.0, 0.0)),
        current=CurrentSample(velocity_ne=(0.0, 0.0)),
        wave=wave,
        mean_drift=MeanDriftSourceSample(components=(comp,)),
        time_s=0.0,
        tick=0,
    )
    nav = NavigationState(0.0, 0.0, 0.0, 1.0, 0.0, 0.0)

    with unittest.mock.patch("hashlib.sha256", wraps=hashlib.sha256) as mock_sha:
        for _ in range(10):
            model.compute_loads(truth, nav)
        assert mock_sha.call_count == 0


def test_slice1_corrupted_asset_fails_at_construction(standard_vessel_params: VesselEnvironmentalParameters) -> None:
    """Slice 1: Corrupted wave asset fails closed at EnvironmentalLoadModel construction."""
    tampered_meta = AssetMetadata(
        asset_id="tampered_wave_1st",
        asset_type="wave_response_inferred",
        trust_level=AssetTrustLevel.INFERRED,
        source_type="inferred",
        sha256="0" * 64,
        license="MIT",
    )
    tampered_asset = InferredWaveResponseAsset(metadata=tampered_meta)

    with pytest.raises(AssetIntegrityError, match="Integrity check failed for wave asset"):
        EnvironmentalLoadModel(
            vessel_params=standard_vessel_params,
            wave_mode=WaveLoadMode.FIRST_ORDER,
            wave_first_order_asset=tampered_asset,
        )

    tampered_drift_meta = AssetMetadata(
        asset_id="tampered_wave_drift",
        asset_type="wave_drift_inferred",
        trust_level=AssetTrustLevel.INFERRED,
        source_type="inferred",
        sha256="0" * 64,
        license="MIT",
    )
    tampered_drift = InferredWaveDriftAsset(metadata=tampered_drift_meta)

    with pytest.raises(AssetIntegrityError, match="Integrity check failed for wave drift asset"):
        EnvironmentalLoadModel(
            vessel_params=standard_vessel_params,
            wave_mode=WaveLoadMode.MEAN_DRIFT,
            wave_mean_drift_asset=tampered_drift,
        )


def _assert_load_close(a: VesselLoad, b: VesselLoad, rtol: float = 1e-12, atol: float = 1e-9) -> None:
    import numpy as np
    assert np.isclose(a.surge_n, b.surge_n, rtol=rtol, atol=atol), f"surge diff: {a.surge_n} vs {b.surge_n}"
    assert np.isclose(a.sway_n, b.sway_n, rtol=rtol, atol=atol), f"sway diff: {a.sway_n} vs {b.sway_n}"
    assert np.isclose(a.yaw_nm, b.yaw_nm, rtol=rtol, atol=atol), f"yaw diff: {a.yaw_nm} vs {b.yaw_nm}"
    assert np.isclose(a.roll_nm, b.roll_nm, rtol=rtol, atol=atol), f"roll diff: {a.roll_nm} vs {b.roll_nm}"


@pytest.mark.parametrize("harmonics", [0, 1, 8, 32, 128])
def test_slice2_scalar_vs_vectorized_first_order_equivalence(
    standard_vessel_params: VesselEnvironmentalParameters, harmonics: int
) -> None:
    """Slice 2: First-order vectorized implementation matches scalar reference oracle within strict tolerances."""
    import numpy as np

    rng = np.random.default_rng(12345 + harmonics)
    components = []
    for _ in range(harmonics):
        amp = float(rng.uniform(0.1, 2.5))
        om = float(rng.uniform(0.3, 2.0))
        ph = float(rng.uniform(0.0, 2.0 * np.pi))
        dr = float(rng.uniform(0.0, 2.0 * np.pi))
        components.append(WaveComponent(amplitude_m=amp, omega_radps=om, phase_rad=ph, direction_to_rad=dr))

    wave = WaveFieldSample(significant_height_m=2.0, peak_period_s=8.0, direction_to_rad=0.5, components=tuple(components))

    test_cases = [
        (0.0, 0.0, 0.0, 0.0),
        (np.pi / 4, 5.0, 0.2, 1.5),
        (np.pi / 2, 10.0, -0.5, 10.0),
        (np.pi, -2.0, 0.0, 50.0),
        (3 * np.pi / 2, 0.0, 1.0, 100.0),
    ]

    for heading, u, v, t in test_cases:
        scalar_load = FirstOrderWaveLoadModel._calculate_inferred_scalar(
            wave=wave,
            heading=heading,
            u=u,
            v=v,
            t=t,
            params=standard_vessel_params,
            asset=DEFAULT_INFERRED_WAVE_RESPONSE_ASSET,
        )
        vec_load = FirstOrderWaveLoadModel.calculate(
            wave=wave,
            heading_rad=heading,
            surge_mps=u,
            sway_mps=v,
            stage_time_s=t,
            params=standard_vessel_params,
            asset=DEFAULT_INFERRED_WAVE_RESPONSE_ASSET,
        )
        _assert_load_close(vec_load, scalar_load, rtol=1e-12, atol=1e-9)


@pytest.mark.parametrize("harmonics", [0, 1, 8, 32, 128])
def test_slice2_scalar_vs_vectorized_mean_drift_equivalence(
    standard_vessel_params: VesselEnvironmentalParameters, harmonics: int
) -> None:
    """Slice 2: Mean-drift vectorized implementation matches scalar reference oracle within strict tolerances."""
    import numpy as np

    rng = np.random.default_rng(54321 + harmonics)
    components = []
    for _ in range(harmonics):
        amp = float(rng.uniform(0.1, 2.5))
        om = float(rng.uniform(0.3, 2.0))
        ph = float(rng.uniform(0.0, 2.0 * np.pi))
        dr = float(rng.uniform(0.0, 2.0 * np.pi))
        components.append(WaveComponent(amplitude_m=amp, omega_radps=om, phase_rad=ph, direction_to_rad=dr))

    wave = MeanDriftSourceSample(components=tuple(components))

    test_headings = [0.0, np.pi / 6, np.pi / 4, np.pi / 2, 3 * np.pi / 4, np.pi, 1.5 * np.pi]

    for heading in test_headings:
        scalar_load = MeanDriftLoadModel._calculate_inferred_scalar(
            wave=wave,
            heading=heading,
            params=standard_vessel_params,
            asset=DEFAULT_INFERRED_WAVE_DRIFT_ASSET,
        )
        vec_load = MeanDriftLoadModel.calculate(
            wave=wave,
            heading_rad=heading,
            params=standard_vessel_params,
            asset=DEFAULT_INFERRED_WAVE_DRIFT_ASSET,
        )
        _assert_load_close(vec_load, scalar_load, rtol=1e-12, atol=1e-9)


def test_slice3_batched_domain_bounds_exact_match(standard_vessel_params: VesselEnvironmentalParameters) -> None:
    """Slice 3: Batched domain checking accepts exact boundary values and rejects out-of-domain values."""
    # Boundary frequency: omega in [0.01, 5.0]
    comp_on_bound = WaveComponent(amplitude_m=1.0, omega_radps=5.0, phase_rad=0.0, direction_to_rad=0.0)
    wave_ok = WaveFieldSample(significant_height_m=1.0, peak_period_s=5.0, direction_to_rad=0.0, components=(comp_on_bound,))
    # Should not raise
    FirstOrderWaveLoadModel.calculate(
        wave=wave_ok,
        heading_rad=0.0,
        surge_mps=0.0,
        sway_mps=0.0,
        stage_time_s=0.0,
        params=standard_vessel_params,
        asset=DEFAULT_INFERRED_WAVE_RESPONSE_ASSET,
    )

    # Just above boundary
    comp_over = WaveComponent(amplitude_m=1.0, omega_radps=5.001, phase_rad=0.0, direction_to_rad=0.0)
    wave_bad = WaveFieldSample(significant_height_m=1.0, peak_period_s=5.0, direction_to_rad=0.0, components=(comp_over,))
    with pytest.raises(Exception, match="outside applicability domain"):
        FirstOrderWaveLoadModel.calculate(
            wave=wave_bad,
            heading_rad=0.0,
            surge_mps=0.0,
            sway_mps=0.0,
            stage_time_s=0.0,
            params=standard_vessel_params,
            asset=DEFAULT_INFERRED_WAVE_RESPONSE_ASSET,
        )

