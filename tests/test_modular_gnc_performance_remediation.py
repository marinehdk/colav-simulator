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
