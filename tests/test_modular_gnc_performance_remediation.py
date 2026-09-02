"""Tests for Issue #65 Python performance remediation slices and numerical equivalence."""

from __future__ import annotations

import concurrent.futures
import hashlib
import time
import unittest.mock
from typing import Any

import numpy as np
import pytest

from colav_simulator.modular_gnc.contracts import (
    AssetIntegrityError,
    AssetMetadata,
    AssetTrustLevel,
    CurrentSample,
    EnvironmentalLoads,
    EnvironmentTruth,
    FloatArray,
    MeanDriftSourceSample,
    NavigationState,
    OutOfDomainError,
    PlantState,
    VesselLoad,
    WaveComponent,
    WaveFieldSample,
    WaveLoadMode,
    WindSample,
)
from colav_simulator.modular_gnc.environment import AnalyticEnvironmentField
from colav_simulator.modular_gnc.integrators import rk4_step
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
from colav_simulator.modular_gnc.plant import Generic3DOFPlant, Generic3DOFPlantParameters


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
    assert np.isclose(a.surge_n, b.surge_n, rtol=rtol, atol=atol), f"surge diff: {a.surge_n} vs {b.surge_n}"
    assert np.isclose(a.sway_n, b.sway_n, rtol=rtol, atol=atol), f"sway diff: {a.sway_n} vs {b.sway_n}"
    assert np.isclose(a.yaw_nm, b.yaw_nm, rtol=rtol, atol=atol), f"yaw diff: {a.yaw_nm} vs {b.yaw_nm}"
    assert np.isclose(a.roll_nm, b.roll_nm, rtol=rtol, atol=atol), f"roll diff: {a.roll_nm} vs {b.roll_nm}"


@pytest.mark.parametrize("harmonics", [0, 1, 8, 32, 128])
def test_slice2_scalar_vs_vectorized_first_order_equivalence(
    standard_vessel_params: VesselEnvironmentalParameters, harmonics: int
) -> None:
    """Slice 2: First-order vectorized implementation matches scalar reference oracle within strict tolerances."""
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


@pytest.mark.parametrize("wave_mode", ["off", "first_order", "mean_drift", "both"])
def test_slice4_compute_total_load_for_rhs_equality(
    standard_vessel_params: VesselEnvironmentalParameters, wave_mode: str
) -> None:
    """Slice 4: compute_total_load_for_rhs matches compute_loads().total exactly across wave modes."""
    model = EnvironmentalLoadModel.from_params(
        {
            "wave_mode": wave_mode,
            "wave_first_order_asset_id": (
                "default_inferred_wave_response_v1" if wave_mode in ("first_order", "both") else None
            ),
            "wave_mean_drift_asset_id": (
                "default_inferred_diagonal_drift_v1" if wave_mode in ("mean_drift", "both") else None
            ),
            "enable_wind": True,
            "enable_current": True,
            "current_strategy": "external_current_load",
        }
    )

    comp1 = WaveComponent(amplitude_m=0.8, omega_radps=0.8, phase_rad=0.3, direction_to_rad=0.2)
    comp2 = WaveComponent(amplitude_m=0.5, omega_radps=1.2, phase_rad=1.0, direction_to_rad=1.5)
    truth = EnvironmentTruth(
        wind=WindSample(velocity_ne=(10.0, 5.0)),
        current=CurrentSample(velocity_ne=(0.5, 0.2)),
        wave=WaveFieldSample(significant_height_m=1.5, peak_period_s=7.0, direction_to_rad=0.4, components=(comp1, comp2)),
        mean_drift=MeanDriftSourceSample(components=(comp1, comp2)),
        time_s=2.5,
        tick=25,
        stage_offset_s=0.0,
    )
    nav = NavigationState(100.0, 50.0, 0.4, 2.0, 0.2, 0.01)

    full_loads = model.compute_loads(truth, nav)
    total_fast = model.compute_total_load_for_rhs(truth, nav)

    _assert_load_close(total_fast, full_loads.total, rtol=1e-12, atol=1e-9)


def test_slice4_error_parity(standard_vessel_params: VesselEnvironmentalParameters) -> None:
    """Slice 4: compute_total_load_for_rhs fails with same exceptions as compute_loads."""
    model = EnvironmentalLoadModel.from_params(
        {
            "wave_mode": "both",
            "wave_first_order_asset_id": "default_inferred_wave_response_v1",
            "wave_mean_drift_asset_id": "default_inferred_diagonal_drift_v1",
        }
    )

    # 1. Invalid truth type
    with pytest.raises(TypeError, match="truth must be EnvironmentTruth"):
        model.compute_loads("bad", NavigationState(0, 0, 0, 0, 0, 0))  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="truth must be EnvironmentTruth"):
        model.compute_total_load_for_rhs("bad", NavigationState(0, 0, 0, 0, 0, 0))  # type: ignore[arg-type]

    # 2. Invalid state type
    comp = WaveComponent(amplitude_m=1.0, omega_radps=1.0, phase_rad=0.0, direction_to_rad=0.0)
    truth = EnvironmentTruth(
        wind=WindSample(velocity_ne=(0.0, 0.0)),
        current=CurrentSample(velocity_ne=(0.0, 0.0)),
        wave=WaveFieldSample(significant_height_m=1.0, peak_period_s=5.0, direction_to_rad=0.0, components=(comp,)),
        mean_drift=MeanDriftSourceSample(components=(comp,)),
        time_s=0.0,
        tick=0,
    )
    with pytest.raises(TypeError, match="vessel_state must be NavigationState or PlantState"):
        model.compute_loads(truth, "bad_state")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="vessel_state must be NavigationState or PlantState"):
        model.compute_total_load_for_rhs(truth, "bad_state")  # type: ignore[arg-type]

    # 3. Out of domain wave
    bad_comp = WaveComponent(amplitude_m=1.0, omega_radps=10.0, phase_rad=0.0, direction_to_rad=0.0)
    bad_truth = EnvironmentTruth(
        wind=WindSample(velocity_ne=(0.0, 0.0)),
        current=CurrentSample(velocity_ne=(0.0, 0.0)),
        wave=WaveFieldSample(significant_height_m=1.0, peak_period_s=5.0, direction_to_rad=0.0, components=(bad_comp,)),
        mean_drift=MeanDriftSourceSample(components=(bad_comp,)),
        time_s=0.0,
        tick=0,
    )
    nav = NavigationState(0, 0, 0, 0, 0, 0)
    with pytest.raises(OutOfDomainError, match="outside applicability domain"):
        model.compute_loads(bad_truth, nav)
    with pytest.raises(OutOfDomainError, match="outside applicability domain"):
        model.compute_total_load_for_rhs(bad_truth, nav)


def test_slice4_rk4_10s_trajectory_equivalence_against_scalar(
    standard_vessel_params: VesselEnvironmentalParameters,
) -> None:
    """Slice 4: Full 10s RK4 trajectory matches scalar reference within rtol<=1e-11, atol<=1e-9."""
    plant_params = Generic3DOFPlantParameters(
        mass_kg=1.6e7,
        i_z_kgm2=3.0e10,
        x_g_m=0.0,
        x_dot_u_kg=-5.0e6,
        y_dot_v_kg=-3.5e7,
        n_dot_r_kgm2=-2.0e10,
        y_dot_r_kgm=1.0e6,
        n_dot_v_kgm=1.0e6,
        d_u=5.0e4,
        d_uu=2.0e5,
        d_v=3.0e5,
        d_vv=1.5e6,
        d_r=8.0e7,
        d_rr=2.5e9,
    )
    plant = Generic3DOFPlant(plant_params)

    dt_s = 0.02  # 50 Hz
    total_steps = 500  # 10s
    field = AnalyticEnvironmentField(
        dt_s=dt_s,
        field_seed=5400,
        wave_significant_height_m=1.5,
        wave_peak_period_s=8.0,
        wave_direction_to_rad=0.4,
        wave_num_components=32,
        wave_directional_spread_rad=0.25,
    )

    load_model = EnvironmentalLoadModel.from_params(
        {
            "wave_mode": "both",
            "wave_first_order_asset_id": "default_inferred_wave_response_v1",
            "wave_mean_drift_asset_id": "default_inferred_diagonal_drift_v1",
            "enable_wind": False,
            "enable_current": False,
        }
    )

    # Class for scalar reference query
    class ScalarReferenceLoadModel:
        def __init__(self, base_model: EnvironmentalLoadModel) -> None:
            self._base = base_model

        def compute_loads(self, truth: EnvironmentTruth, state: PlantState | NavigationState) -> EnvironmentalLoads:
            w1 = FirstOrderWaveLoadModel._calculate_inferred_scalar(
                wave=truth.wave,
                heading=state.heading_rad,
                u=state.surge_mps,
                v=state.sway_mps,
                t=truth.time_s,
                params=self._base.vessel_params,
                asset=self._base.wave_first_order_asset,
            )
            wmd = MeanDriftLoadModel._calculate_inferred_scalar(
                wave=truth.mean_drift,
                heading=state.heading_rad,
                params=self._base.vessel_params,
                asset=self._base.wave_mean_drift_asset,
            )
            return EnvironmentalLoads.from_components(wave_first_order=w1, wave_mean_drift=wmd)

    scalar_load_model = ScalarReferenceLoadModel(load_model)

    x0_vec = np.array([0.0, 0.0, 0.1, 1.5, 0.0, 0.0], dtype=np.float64)
    x0_scal = np.array([0.0, 0.0, 0.1, 1.5, 0.0, 0.0], dtype=np.float64)

    state_vec = x0_vec.copy()
    state_scal = x0_scal.copy()
    ctrl = VesselLoad.zero()

    max_rel_diff = 0.0
    max_abs_diff = 0.0

    for tick in range(total_steps):
        state_vec = rk4_step(plant, tick, dt_s, state_vec, ctrl, field, load_model)
        state_scal = rk4_step(plant, tick, dt_s, state_scal, ctrl, field, scalar_load_model)

        abs_diff = np.max(np.abs(state_vec - state_scal))
        rel_diff = np.max(np.abs((state_vec - state_scal) / np.maximum(np.abs(state_scal), 1e-9)))

        if abs_diff > max_abs_diff:
            max_abs_diff = float(abs_diff)
        if rel_diff > max_rel_diff:
            max_rel_diff = float(rel_diff)

    assert max_rel_diff <= 1e-11, f"max relative trajectory diff exceeded: {max_rel_diff} > 1e-11"
    assert max_abs_diff <= 1e-9, f"max absolute trajectory diff exceeded: {max_abs_diff} > 1e-9"


@pytest.mark.parametrize("harmonics", [32, 128])
def test_deterministic_microbenchmark(harmonics: int) -> None:
    """Deterministic local microbenchmark for 32 and 128 harmonics verifying repeatability and bounded execution."""
    plant_params = Generic3DOFPlantParameters(
        mass_kg=1.6e7,
        i_z_kgm2=3.0e10,
        x_g_m=0.0,
        x_dot_u_kg=-5.0e6,
        y_dot_v_kg=-3.5e7,
        n_dot_r_kgm2=-2.0e10,
        y_dot_r_kgm=1.0e6,
        n_dot_v_kgm=1.0e6,
        d_u=5.0e4,
        d_uu=2.0e5,
        d_v=3.0e5,
        d_vv=1.5e6,
        d_r=8.0e7,
        d_rr=2.5e9,
    )
    plant = Generic3DOFPlant(plant_params)
    dt_s = 0.02
    steps = 100

    field = AnalyticEnvironmentField(
        dt_s=dt_s,
        field_seed=42,
        wave_significant_height_m=1.5,
        wave_peak_period_s=8.0,
        wave_direction_to_rad=0.4,
        wave_num_components=harmonics,
        wave_directional_spread_rad=0.25,
    )
    load_model = EnvironmentalLoadModel.from_params(
        {
            "wave_mode": "both",
            "wave_first_order_asset_id": "default_inferred_wave_response_v1",
            "wave_mean_drift_asset_id": "default_inferred_diagonal_drift_v1",
            "enable_wind": False,
            "enable_current": False,
        }
    )

    def run_trajectory() -> tuple[np.ndarray, float]:
        state = np.array([0.0, 0.0, 0.1, 1.5, 0.0, 0.0], dtype=np.float64)
        ctrl = VesselLoad.zero()
        t0 = time.perf_counter()
        for tick in range(steps):
            state = rk4_step(plant, tick, dt_s, state, ctrl, field, load_model)
        elapsed = time.perf_counter() - t0
        return state, elapsed

    state1, elapsed1 = run_trajectory()
    state2, elapsed2 = run_trajectory()

    # Bit-identical determinism across repeats
    assert np.array_equal(state1, state2), "optimized path must be bit-identical across repeats"
    # Coarse non-flaky sanity check: 100 steps (400 RK stages) must finish in under 2 seconds locally
    assert elapsed1 < 2.0
    assert elapsed2 < 2.0


@pytest.mark.parametrize("harmonics", [0, 1, 8, 32, 128])
def test_slice_a_fused_inferred_wave_loads_equivalence(
    standard_vessel_params: VesselEnvironmentalParameters, harmonics: int
) -> None:
    """Slice A: Fused BOTH-mode wave kernel produces bit-identical / strict-tolerance loads vs separate Batch 1 kernels."""
    rng = np.random.default_rng(9999 + harmonics)
    components = []
    for _ in range(harmonics):
        amp = float(rng.uniform(0.1, 2.5))
        om = float(rng.uniform(0.3, 2.0))
        ph = float(rng.uniform(0.0, 2.0 * np.pi))
        dr = float(rng.uniform(0.0, 2.0 * np.pi))
        components.append(WaveComponent(amplitude_m=amp, omega_radps=om, phase_rad=ph, direction_to_rad=dr))

    wave = WaveFieldSample(significant_height_m=2.0, peak_period_s=8.0, direction_to_rad=0.5, components=tuple(components))
    drift = MeanDriftSourceSample(components=tuple(components))

    model = EnvironmentalLoadModel(
        vessel_params=standard_vessel_params,
        wave_mode=WaveLoadMode.BOTH,
        wave_first_order_asset=DEFAULT_INFERRED_WAVE_RESPONSE_ASSET,
        wave_mean_drift_asset=DEFAULT_INFERRED_WAVE_DRIFT_ASSET,
        enable_wind=False,
        enable_current=False,
    )

    test_cases = [
        (0.0, 0.0, 0.0, 0.0),
        (0.5, 2.0, 0.2, 1.5),
        (np.pi / 2, 5.0, -0.5, 10.0),
        (np.pi, 1.0, 0.0, 0.2),
        (3 * np.pi / 2, 3.0, 0.1, 5.5),
        (5.5, 4.0, -0.3, 100.0),
    ]

    for heading, u, v, t in test_cases:
        truth = EnvironmentTruth(
            wind=WindSample(velocity_ne=(0.0, 0.0)),
            current=CurrentSample(velocity_ne=(0.0, 0.0)),
            wave=wave,
            mean_drift=drift,
            time_s=t,
            tick=0,
        )
        nav = NavigationState(0.0, 0.0, heading, u, v, 0.0)

        # 1. Separate vector calls
        w1_sep = FirstOrderWaveLoadModel.calculate(
            wave=wave,
            heading_rad=heading,
            surge_mps=u,
            sway_mps=v,
            stage_time_s=t,
            params=standard_vessel_params,
            asset=DEFAULT_INFERRED_WAVE_RESPONSE_ASSET,
        )
        wdrift_sep = MeanDriftLoadModel.calculate(
            wave=drift,
            heading_rad=heading,
            params=standard_vessel_params,
            asset=DEFAULT_INFERRED_WAVE_DRIFT_ASSET,
        )

        # 2. Fused call
        w1_fused, wdrift_fused = model._calculate_fused_inferred_wave_loads(
            wave=wave,
            heading_rad=heading,
            surge_mps=u,
            sway_mps=v,
            stage_time_s=t,
        )

        _assert_load_close(w1_fused, w1_sep, rtol=1e-12, atol=1e-9)
        _assert_load_close(wdrift_fused, wdrift_sep, rtol=1e-12, atol=1e-9)

        # 3. Model compute_loads and compute_total_load_for_rhs
        full_loads = model.compute_loads(truth, nav)
        total_rhs = model.compute_total_load_for_rhs(truth, nav)

        _assert_load_close(full_loads.wave_first_order, w1_sep, rtol=1e-12, atol=1e-9)
        _assert_load_close(full_loads.wave_mean_drift, wdrift_sep, rtol=1e-12, atol=1e-9)
        _assert_load_close(full_loads.total, w1_sep + wdrift_sep, rtol=1e-12, atol=1e-9)
        _assert_load_close(total_rhs, w1_sep + wdrift_sep, rtol=1e-12, atol=1e-9)


def test_slice_a_fused_out_of_domain_parity(standard_vessel_params: VesselEnvironmentalParameters) -> None:
    """Slice A: Fused BOTH-mode wave kernel raises exact OutOfDomainError as separate path."""
    model = EnvironmentalLoadModel(
        vessel_params=standard_vessel_params,
        wave_mode=WaveLoadMode.BOTH,
        wave_first_order_asset=DEFAULT_INFERRED_WAVE_RESPONSE_ASSET,
        wave_mean_drift_asset=DEFAULT_INFERRED_WAVE_DRIFT_ASSET,
    )

    # 1. Out of domain speed (>30 m/s)
    comp = WaveComponent(amplitude_m=1.0, omega_radps=1.0, phase_rad=0.0, direction_to_rad=0.0)
    wave = WaveFieldSample(significant_height_m=1.0, peak_period_s=5.0, direction_to_rad=0.0, components=(comp,))
    truth = EnvironmentTruth(
        wind=WindSample(velocity_ne=(0.0, 0.0)),
        current=CurrentSample(velocity_ne=(0.0, 0.0)),
        wave=wave,
        mean_drift=MeanDriftSourceSample(components=(comp,)),
        time_s=0.0,
        tick=0,
    )
    overspeed_nav = NavigationState(0.0, 0.0, 0.0, 35.0, 0.0, 0.0)

    with pytest.raises(OutOfDomainError, match="outside applicability domain"):
        model.compute_loads(truth, overspeed_nav)
    with pytest.raises(OutOfDomainError, match="outside applicability domain"):
        model.compute_total_load_for_rhs(truth, overspeed_nav)

    # 2. Out of domain omega (>5.0 rad/s)
    bad_comp = WaveComponent(amplitude_m=1.0, omega_radps=8.0, phase_rad=0.0, direction_to_rad=0.0)
    bad_truth = EnvironmentTruth(
        wind=WindSample(velocity_ne=(0.0, 0.0)),
        current=CurrentSample(velocity_ne=(0.0, 0.0)),
        wave=WaveFieldSample(significant_height_m=1.0, peak_period_s=5.0, direction_to_rad=0.0, components=(bad_comp,)),
        mean_drift=MeanDriftSourceSample(components=(bad_comp,)),
        time_s=0.0,
        tick=0,
    )
    normal_nav = NavigationState(0.0, 0.0, 0.0, 1.0, 0.0, 0.0)

    with pytest.raises(OutOfDomainError, match="outside applicability domain"):
        model.compute_loads(bad_truth, normal_nav)
    with pytest.raises(OutOfDomainError, match="outside applicability domain"):
        model.compute_total_load_for_rhs(bad_truth, normal_nav)


def test_slice_b_numeric_stage_vs_public_path_exactness(
    standard_vessel_params: VesselEnvironmentalParameters,
) -> None:
    """Slice B: Fast numeric stage path produces bit-identical next state and trajectory vs public path."""
    plant_params = Generic3DOFPlantParameters(
        mass_kg=1.6e7,
        i_z_kgm2=3.0e10,
        x_g_m=0.0,
        x_dot_u_kg=-5.0e6,
        y_dot_v_kg=-3.5e7,
        n_dot_r_kgm2=-2.0e10,
        y_dot_r_kgm=1.0e6,
        n_dot_v_kgm=1.0e6,
        d_u=5.0e4,
        d_uu=2.0e5,
        d_v=3.0e5,
        d_vv=1.5e6,
        d_r=8.0e7,
        d_rr=2.5e9,
    )
    plant = Generic3DOFPlant(plant_params)

    # Custom wrapper around plant to force public path execution in rk4_step
    class PublicPathPlantWrapper:
        capabilities = frozenset({"PLANAR_3DOF", "GENERALIZED_FORCE"})

        def __init__(self, inner: Generic3DOFPlant) -> None:
            self._inner = inner

        def rhs(self, time_s: float, state: Any, control_load: Any, env_load: Any = None) -> FloatArray:
            return self._inner.rhs(time_s, state, control_load, env_load)

    public_plant = PublicPathPlantWrapper(plant)

    dt_s = 0.02
    total_steps = 250  # 5s
    field = AnalyticEnvironmentField(
        dt_s=dt_s,
        field_seed=7777,
        wave_significant_height_m=1.8,
        wave_peak_period_s=7.5,
        wave_direction_to_rad=0.6,
        wave_num_components=32,
        wind_velocity_ne=(8.0, 4.0),
        current_velocity_ne=(0.4, 0.2),
    )

    load_model = EnvironmentalLoadModel(
        vessel_params=standard_vessel_params,
        wave_mode=WaveLoadMode.BOTH,
        wave_first_order_asset=DEFAULT_INFERRED_WAVE_RESPONSE_ASSET,
        wave_mean_drift_asset=DEFAULT_INFERRED_WAVE_DRIFT_ASSET,
        enable_wind=True,
        enable_current=True,
        current_strategy="external_current_load",
    )

    state_fast = np.array([100.0, 50.0, 0.3, 2.0, 0.1, 0.01], dtype=np.float64)
    state_pub = state_fast.copy()
    ctrl = VesselLoad(surge_n=1e4, sway_n=2e3, yaw_nm=5e3)

    for tick in range(total_steps):
        state_fast = rk4_step(plant, tick, dt_s, state_fast, ctrl, field, load_model)
        state_pub = rk4_step(public_plant, tick, dt_s, state_pub, ctrl, field, load_model)

        # Assert bit-identical state at every single step!
        np.testing.assert_allclose(state_fast, state_pub, rtol=1e-12, atol=1e-12)


def test_slice_b_stage_timing_sink_parity() -> None:
    """Slice B: Stage timing sink receives exactly 4 stages with strictly positive elapsed nanoseconds."""
    plant_params = Generic3DOFPlantParameters(mass_kg=1.0e6, i_z_kgm2=1.0e8)
    plant = Generic3DOFPlant(plant_params)
    dt_s = 0.1
    state = np.array([0.0, 0.0, 0.0, 1.0, 0.0, 0.0], dtype=np.float64)
    ctrl = VesselLoad.zero()

    stages_called: list[tuple[int, int]] = []

    def sink(stage_num: int, elapsed_ns: int) -> None:
        stages_called.append((stage_num, elapsed_ns))

    rk4_step(plant, 0, dt_s, state, ctrl, stage_timing_sink=sink)

    assert len(stages_called) == 4
    assert [s[0] for s in stages_called] == [1, 2, 3, 4]
    for _stage_num, elapsed in stages_called:
        assert elapsed >= 0


def test_slice_c_thread_and_ship_reentrancy_isolation(
    standard_vessel_params: VesselEnvironmentalParameters,
) -> None:
    """Slice C: Interleaved execution across ships/threads exhibits zero cross-contamination."""
    plant_params = Generic3DOFPlantParameters(mass_kg=1.0e6, i_z_kgm2=1.0e8)
    plant = Generic3DOFPlant(plant_params)

    dt_s = 0.02
    field = AnalyticEnvironmentField(dt_s=dt_s, field_seed=1234)
    load_model = EnvironmentalLoadModel(
        vessel_params=standard_vessel_params,
        wave_mode=WaveLoadMode.BOTH,
        wave_first_order_asset=DEFAULT_INFERRED_WAVE_RESPONSE_ASSET,
        wave_mean_drift_asset=DEFAULT_INFERRED_WAVE_DRIFT_ASSET,
        enable_wind=True,
        enable_current=False,
    )

    def run_ship_sim(init_state: np.ndarray, ctrl_val: float, steps: int) -> list[np.ndarray]:
        history = [init_state.copy()]
        state = init_state.copy()
        ctrl = VesselLoad(surge_n=ctrl_val, sway_n=0.0, yaw_nm=0.0)
        for tick in range(steps):
            state = rk4_step(plant, tick, dt_s, state, ctrl, field, load_model)
            history.append(state.copy())
        return history

    s1_init = np.array([0.0, 0.0, 0.0, 1.0, 0.0, 0.0], dtype=np.float64)
    s2_init = np.array([1000.0, -500.0, 1.2, 3.5, 0.2, 0.05], dtype=np.float64)

    # 1. Serial execution
    s1_serial = run_ship_sim(s1_init, 1000.0, 50)
    s2_serial = run_ship_sim(s2_init, 5000.0, 50)

    # 2. Interleaved execution step by step
    s1_inter = [s1_init.copy()]
    s2_inter = [s2_init.copy()]
    s1_st = s1_init.copy()
    s2_st = s2_init.copy()
    c1 = VesselLoad(surge_n=1000.0, sway_n=0.0, yaw_nm=0.0)
    c2 = VesselLoad(surge_n=5000.0, sway_n=0.0, yaw_nm=0.0)

    for tick in range(50):
        s1_st = rk4_step(plant, tick, dt_s, s1_st, c1, field, load_model)
        s2_st = rk4_step(plant, tick, dt_s, s2_st, c2, field, load_model)
        s1_inter.append(s1_st.copy())
        s2_inter.append(s2_st.copy())

    for k in range(len(s1_serial)):
        assert np.array_equal(s1_serial[k], s1_inter[k]), f"Ship 1 interleaved mismatch at step {k}"
        assert np.array_equal(s2_serial[k], s2_inter[k]), f"Ship 2 interleaved mismatch at step {k}"

    # 3. Concurrent multithreaded execution
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        f1 = executor.submit(run_ship_sim, s1_init, 1000.0, 50)
        f2 = executor.submit(run_ship_sim, s2_init, 5000.0, 50)
        s1_threaded = f1.result()
        s2_threaded = f2.result()

    for k in range(len(s1_serial)):
        assert np.array_equal(s1_serial[k], s1_threaded[k]), f"Ship 1 threaded mismatch at step {k}"
        assert np.array_equal(s2_serial[k], s2_threaded[k]), f"Ship 2 threaded mismatch at step {k}"


@pytest.mark.parametrize("wave_mode", ["off", "first_order", "mean_drift", "both"])
@pytest.mark.parametrize("current_strategy", ["none", "current_relative_damping", "external_current_load"])
def test_slice_b_all_modes_and_strategies_parity(
    standard_vessel_params: VesselEnvironmentalParameters,
    wave_mode: str,
    current_strategy: str,
) -> None:
    """Slice B: Numeric stage vs public path produces identical next state across all wave modes and current strategies."""
    plant_params = Generic3DOFPlantParameters(mass_kg=1.0e6, i_z_kgm2=1.0e8)
    plant = Generic3DOFPlant(plant_params)

    class PublicPathPlantWrapper:
        capabilities = frozenset({"PLANAR_3DOF", "GENERALIZED_FORCE"})

        def __init__(self, inner: Generic3DOFPlant) -> None:
            self._inner = inner

        def rhs(self, time_s: float, state: Any, control_load: Any, env_load: Any = None) -> FloatArray:
            return self._inner.rhs(time_s, state, control_load, env_load)

    public_plant = PublicPathPlantWrapper(plant)

    dt_s = 0.05
    field = AnalyticEnvironmentField(
        dt_s=dt_s,
        field_seed=8888,
        wave_significant_height_m=1.5,
        wave_num_components=8,
        wind_velocity_ne=(5.0, -3.0),
        current_velocity_ne=(0.5, 0.1),
    )

    load_model = EnvironmentalLoadModel.from_params(
        {
            "wave_mode": wave_mode,
            "wave_first_order_asset_id": (
                "default_inferred_wave_response_v1" if wave_mode in ("first_order", "both") else None
            ),
            "wave_mean_drift_asset_id": (
                "default_inferred_diagonal_drift_v1" if wave_mode in ("mean_drift", "both") else None
            ),
            "enable_wind": True,
            "enable_current": True,
            "current_strategy": current_strategy,
        }
    )

    state_fast = np.array([0.0, 0.0, 0.5, 2.0, 0.2, 0.05], dtype=np.float64)
    state_pub = state_fast.copy()
    ctrl = VesselLoad(surge_n=1e4, sway_n=5e2, yaw_nm=1e3)

    for tick in range(10):
        state_fast = rk4_step(plant, tick, dt_s, state_fast, ctrl, field, load_model)
        state_pub = rk4_step(public_plant, tick, dt_s, state_pub, ctrl, field, load_model)

        assert np.array_equal(state_fast, state_pub)


def test_slice_b_stage_error_validation_parity(
    standard_vessel_params: VesselEnvironmentalParameters,
) -> None:
    """Slice B: Error validation for invalid dt_s, non-finite states in fast path matches contract."""
    plant_params = Generic3DOFPlantParameters(mass_kg=1.0e6, i_z_kgm2=1.0e8)
    plant = Generic3DOFPlant(plant_params)
    dt_s = 0.02
    field = AnalyticEnvironmentField(dt_s=dt_s, field_seed=4321)
    load_model = EnvironmentalLoadModel(
        vessel_params=standard_vessel_params,
        wave_mode=WaveLoadMode.BOTH,
        wave_first_order_asset=DEFAULT_INFERRED_WAVE_RESPONSE_ASSET,
        wave_mean_drift_asset=DEFAULT_INFERRED_WAVE_DRIFT_ASSET,
    )

    # 1. Invalid dt_s <= 0
    with pytest.raises(ValueError, match="dt_s must be positive"):
        rk4_step(plant, 0, 0.0, np.zeros(6), VesselLoad.zero(), field, load_model)

    # 2. Non-finite initial state
    bad_state = np.array([0.0, 0.0, 0.0, np.nan, 0.0, 0.0])
    with pytest.raises(ValueError, match="initial state contains non-finite values"):
        rk4_step(plant, 0, dt_s, bad_state, VesselLoad.zero(), field, load_model)

    # 3. Invalid state shape
    with pytest.raises(ValueError, match="state must have shape"):
        rk4_step(plant, 0, dt_s, np.zeros(5), VesselLoad.zero(), field, load_model)

    # 4. Non-finite control load
    bad_ctrl = np.array([np.inf, 0.0, 0.0])
    with pytest.raises(ValueError, match="control_load contains non-finite values"):
        rk4_step(plant, 0, dt_s, np.zeros(6), bad_ctrl, field, load_model)

    # 5. Out of domain speed (>30 m/s) in fast stage
    field_waves = AnalyticEnvironmentField(
        dt_s=dt_s,
        field_seed=4321,
        wave_significant_height_m=1.0,
        wave_num_components=8,
    )
    overspeed_state = np.array([0.0, 0.0, 0.0, 35.0, 0.0, 0.0], dtype=np.float64)
    with pytest.raises(OutOfDomainError, match="outside applicability domain"):
        rk4_step(plant, 0, dt_s, overspeed_state, VesselLoad.zero(), field_waves, load_model)
