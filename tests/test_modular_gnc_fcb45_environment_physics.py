"""Conservation, frame and limiting-case checks for FCB45 environmental loads."""

import math
from dataclasses import replace

import numpy as np
import pytest

from colav_simulator.modular_gnc.catalog import _CANONICAL_MODULE_PARAMETERS
from colav_simulator.modular_gnc.contracts import NavigationState, VesselLoad, WaveComponent, WaveFieldSample
from colav_simulator.modular_gnc.environment import AnalyticEnvironmentField
from colav_simulator.modular_gnc.fcb45_environment import (
    BlendermannWindParameters,
    FCB45WaveGeometry,
    IncidentPressureWaveModel,
    WaveDriftProxyParameters,
    blendermann_wind_load,
    mean_drift_proxy,
    relative_current_load,
    wave_number,
)
from colav_simulator.modular_gnc.integrators import rk4_step
from colav_simulator.modular_gnc.plant import GenericRoll4DOFPlant, GenericRoll4DOFPlantParameters


def _plant() -> GenericRoll4DOFPlant:
    params = dict(_CANONICAL_MODULE_PARAMETERS["fcb45_roll_4dof_plant"])
    params.update(k_dot_p_kgm2=-1e7, d_p=1e7, d_pp=5e7)
    return GenericRoll4DOFPlant(GenericRoll4DOFPlantParameters(**params))


@pytest.mark.parametrize("speed", [0.0, 2.0, 7.8])
def test_zero_current_adds_no_duplicate_hull_resistance(speed):
    state = NavigationState(0.0, 0.0, 0.3, speed, 0.2, 0.01)
    assert relative_current_load(_plant(), state, (0.0, 0.0)) == VesselLoad.zero()


def test_unpowered_vessel_translates_with_uniform_water_without_drag():
    plant = _plant()
    state = NavigationState(0.0, 0.0, 0.0, 0.4, -0.2, 0.0)
    load = relative_current_load(plant, state, (0.4, -0.2))
    x = np.array([0.0, 0.0, 0.0, 0.0, 0.4, -0.2, 0.0, 0.0])
    derivative = plant.rhs(0.0, x, VesselLoad.zero(), load)
    np.testing.assert_allclose(derivative[:2], [0.4, -0.2], atol=1e-12)
    np.testing.assert_allclose(derivative[4:], 0.0, atol=1e-12)


def test_wind_directions_mirror_and_moments_follow_ned_cross_product():
    p = BlendermannWindParameters()
    state = NavigationState(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    aft = blendermann_wind_load(p, (10.0, 0.0), state)
    ahead = blendermann_wind_load(p, (-10.0, 0.0), state)
    assert aft.surge_n > 0.0 > ahead.surge_n
    for flow in ((-8.0, 5.0), (5.0, 8.0), (0.0, 10.0)):
        port = blendermann_wind_load(p, flow, state)
        starboard = blendermann_wind_load(p, (flow[0], -flow[1]), state)
        assert port.surge_n == pytest.approx(starboard.surge_n)
        assert port.sway_n == pytest.approx(-starboard.sway_n)
        assert port.yaw_nm == pytest.approx(-starboard.yaw_nm)
        assert port.roll_nm == pytest.approx(-starboard.roll_nm)
        assert port.roll_nm > 0.0  # Force to starboard above CG rolls starboard-down.


@pytest.mark.parametrize("components", [8, 24, 64])
def test_generated_discrete_wave_spectrum_has_requested_variance(components):
    field = AnalyticEnvironmentField(
        0.1,
        11,
        wave_significant_height_m=1.2,
        wave_peak_period_s=7.0,
        wave_num_components=components,
        normalize_wave_energy=True,
    )
    variance = sum(x.amplitude_m**2 for x in field.wave_sample.components) / 2.0
    assert 4.0 * math.sqrt(variance) == pytest.approx(1.2, abs=1e-12)


def test_roll_free_decay_dissipates_energy_with_colleague_parameters():
    plant = _plant()
    state = np.array([0.0, 0.0, 0.0, 0.1, 0.0, 0.0, 0.0, 0.0])

    energies = []
    for tick in range(1500):
        nu = state[4:]
        energies.append(float(0.5 * nu @ plant.mass_matrix @ nu + 0.5 * plant.params.restoring_k_phi * state[3] ** 2))
        state = rk4_step(plant, tick, 0.1, state, VesselLoad.zero())
    assert np.max(np.diff(energies)) <= 1e-8
    assert energies[-1] < energies[0] * 1e-8


def _wave(amplitude=0.5, omega=0.9, direction=0.8, phase=0.4) -> WaveFieldSample:
    return WaveFieldSample(
        significant_height_m=2.0 * amplitude,
        peak_period_s=2.0 * math.pi / omega,
        direction_to_rad=direction,
        components=(WaveComponent(amplitude, omega, phase, direction),),
    )


def _load_vector(load) -> np.ndarray:
    return np.array([load.surge_n, load.sway_n, load.roll_nm, load.yaw_nm])


def test_wave_pressure_obeys_force_and_moment_dimensions_and_linear_amplitude():
    geometry = FCB45WaveGeometry()
    state = NavigationState(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    model = IncidentPressureWaveModel(geometry)
    base = _load_vector(model.calculate(_wave(), state, 0.0))
    twice_amplitude = _load_vector(model.calculate(_wave(amplitude=1.0), state, 0.0))
    np.testing.assert_allclose(twice_amplitude, 2.0 * base, atol=1e-8)
    scaled = replace(
        geometry,
        length_m=2.0 * geometry.length_m,
        beam_m=2.0 * geometry.beam_m,
        draft_m=2.0 * geometry.draft_m,
        kg_m=2.0 * geometry.kg_m,
        displacement_kg=8.0 * geometry.displacement_kg,
        water_depth_m=2.0 * geometry.water_depth_m,
    )
    result = _load_vector(
        IncidentPressureWaveModel(scaled).calculate(_wave(amplitude=1.0, omega=0.9 / math.sqrt(2.0)), state, 0.0)
    )
    np.testing.assert_allclose(result, base * [8.0, 8.0, 16.0, 16.0], rtol=1e-10, atol=1e-7)


def test_wave_phase_depends_on_position_and_time_not_instantaneous_speed():
    model = IncidentPressureWaveModel(FCB45WaveGeometry())
    slow = NavigationState(50.0, 100.0, 0.3, 0.0, 0.0, 0.0)
    fast = NavigationState(50.0, 100.0, 0.3, 8.0, 0.2, 0.02)
    np.testing.assert_array_equal(
        _load_vector(model.calculate(_wave(), slow, 123.0)), _load_vector(model.calculate(_wave(), fast, 123.0))
    )
    k = wave_number(0.9, 30.0, 9.81)
    moved = NavigationState(50.0 + 10.0 * math.cos(0.8), 100.0 + 10.0 * math.sin(0.8), 0.3, 0.0, 0.0, 0.0)
    np.testing.assert_allclose(
        _load_vector(model.calculate(_wave(), moved, 123.0)),
        _load_vector(model.calculate(_wave(phase=0.4 + k * 10.0), slow, 123.0)),
        rtol=1e-10,
        atol=1e-7,
    )


def test_fk_quadrature_converges_for_design_wave_period():
    geometry = FCB45WaveGeometry()
    state = NavigationState(0.0, 0.0, 0.2, 0.0, 0.0, 0.0)
    base = _load_vector(IncidentPressureWaveModel(geometry).calculate(_wave(), state, 3.0))
    fine = _load_vector(
        IncidentPressureWaveModel(replace(geometry, longitudinal_nodes=48, depth_nodes=24)).calculate(_wave(), state, 3.0)
    )
    np.testing.assert_allclose(base, fine, rtol=2e-4, atol=1e-5)


def test_drift_proxy_has_quadratic_amplitude_scaling_and_explicit_uncertainty():
    geometry = FCB45WaveGeometry()
    full = mean_drift_proxy(geometry, WaveDriftProxyParameters(1.0), _wave(), 0.2)
    twice = mean_drift_proxy(geometry, WaveDriftProxyParameters(1.0), _wave(amplitude=1.0, phase=2.0), 0.2)
    half = mean_drift_proxy(geometry, WaveDriftProxyParameters(0.5), _wave(), 0.2)
    off = mean_drift_proxy(geometry, WaveDriftProxyParameters(0.0), _wave(), 0.2)
    np.testing.assert_allclose(_load_vector(twice), 4.0 * _load_vector(full))
    np.testing.assert_allclose(_load_vector(half), 0.5 * _load_vector(full))
    assert off == VesselLoad.zero()
    assert full.yaw_nm == full.roll_nm == 0.0  # No invented drift moment arm.
