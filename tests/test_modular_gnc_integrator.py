"""Scheduler-owned fixed-step RK4 and stage environment evaluation (Issue #52, VR-11, TS-13, TS-14)."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pytest

from colav_simulator.modular_gnc.contracts import (
    VesselLoad,
    WaveComponent,
)
from colav_simulator.modular_gnc.environment import AnalyticEnvironmentField
from colav_simulator.modular_gnc.integrators import rk4_step
from colav_simulator.modular_gnc.load_model import (
    DEFAULT_INFERRED_WAVE_RESPONSE_ASSET,
    EnvironmentalLoadModel,
    VesselEnvironmentalParameters,
    WaveLoadMode,
)
from colav_simulator.modular_gnc.plant import (
    Generic3DOFPlant,
    Generic3DOFPlantParameters,
)


@pytest.fixture
def plant() -> Generic3DOFPlant:
    params = Generic3DOFPlantParameters(
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
    return Generic3DOFPlant(params)


# ---------------------------------------------------------------------------
# 1. Classical RK4 Accuracy and Convergence (TDD Seam 4)
# ---------------------------------------------------------------------------


def test_rk4_exact_on_constant_and_linear_motion(plant: Generic3DOFPlant) -> None:
    # Pure constant velocity kinematic motion (no acceleration)
    # Forward velocity u = 2.0 m/s, heading North (psi=0)
    # After dt = 1.0s, north should advance by exactly 2.0m
    state = np.array([0.0, 0.0, 0.0, 2.0, 0.0, 0.0])

    class PureKinematicPlant:
        def rhs(self, time_s: float, state: np.ndarray, ctrl: Any, env: Any = None) -> np.ndarray:
            return np.array([state[3], 0.0, 0.0, 0.0, 0.0, 0.0])

    next_state = rk4_step(
        PureKinematicPlant(),
        tick=0,
        dt_s=1.0,
        state=state,
        control_load=VesselLoad.zero(),
    )
    assert math.isclose(next_state[0], 2.0, abs_tol=1e-12)
    assert math.isclose(next_state[1], 0.0, abs_tol=1e-12)


def test_rk4_fourth_order_convergence_ratio() -> None:
    # Test dy/dt = -y^2, y(0) = 1. Analytical solution: y(t) = 1 / (1 + t).
    # At t = 1.0, exact y(1) = 0.5.
    class ScalarNonlinearODE:
        def rhs(self, time_s: float, state: np.ndarray, ctrl: Any, env: Any = None) -> np.ndarray:
            y = state[0]
            return np.array([-y * y, 0.0, 0.0, 0.0, 0.0, 0.0])

    exact = 0.5

    # Step with dt1 = 0.2 (5 steps)
    state1 = np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    dt1 = 0.2
    for tick in range(5):
        state1 = rk4_step(ScalarNonlinearODE(), tick=tick, dt_s=dt1, state=state1, control_load=VesselLoad.zero())
    error1 = abs(state1[0] - exact)

    # Step with dt2 = 0.1 (10 steps)
    state2 = np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    dt2 = 0.1
    for tick in range(10):
        state2 = rk4_step(ScalarNonlinearODE(), tick=tick, dt_s=dt2, state=state2, control_load=VesselLoad.zero())
    error2 = abs(state2[0] - exact)

    # For 4th-order method, halving dt should reduce error by ~ 2^4 = 16
    convergence_ratio = error1 / error2
    assert 14.0 < convergence_ratio < 18.0


# ---------------------------------------------------------------------------
# 2. Stage Times & Exact Physical Identities (TDD Seam 5)
# ---------------------------------------------------------------------------


def test_rk4_stage_times_and_states_exact(plant: Generic3DOFPlant) -> None:
    recorded_times: list[float] = []
    recorded_states: list[np.ndarray] = []

    class StageProbePlant:
        def rhs(self, time_s: float, state: np.ndarray, ctrl: Any, env: Any = None) -> np.ndarray:
            recorded_times.append(time_s)
            recorded_states.append(state.copy())
            return np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0])

    initial_state = np.zeros(6)
    tick = 10
    dt_s = 0.2
    base_time = tick * dt_s  # 2.0s

    next_state = rk4_step(
        StageProbePlant(),
        tick=tick,
        dt_s=dt_s,
        state=initial_state,
        control_load=VesselLoad.zero(),
    )

    # 4 distinct stage evaluations
    assert len(recorded_times) == 4
    # Exact stage times: t0, t0 + dt/2, t0 + dt/2, t0 + dt
    expected_times = [base_time, base_time + 0.1, base_time + 0.1, base_time + 0.2]
    np.testing.assert_allclose(recorded_times, expected_times, atol=1e-12)

    # Final position is advanced by exactly dt * 1.0 = 0.2m
    assert math.isclose(next_state[0], 0.2, abs_tol=1e-12)


def test_rk4_queries_environment_at_every_stage_not_zoh(plant: Generic3DOFPlant) -> None:
    # Analytic environment field with wave components that vary at stage-time frequency
    wave_comp = WaveComponent(
        amplitude_m=0.5,
        omega_radps=1.5,  # Within domain (0.01, 5.0)
        phase_rad=0.0,
        direction_to_rad=0.5,  # Non-zero angle to heading
    )
    env_field = AnalyticEnvironmentField(
        dt_s=0.1,
        field_seed=42,
        components=[wave_comp],
    )
    vessel_params = VesselEnvironmentalParameters(44.1, 8.0, 1.55, 50.0, 150.0)
    load_model = EnvironmentalLoadModel(
        vessel_params=vessel_params,
        wave_mode=WaveLoadMode.FIRST_ORDER,
        wave_first_order_asset=DEFAULT_INFERRED_WAVE_RESPONSE_ASSET,
        enable_wind=False,
        enable_current=False,
    )

    recorded_env_loads: list[VesselLoad] = []

    class StageEnvRecorderPlant:
        def rhs(self, time_s: float, state: np.ndarray, ctrl: Any, env: Any = None) -> np.ndarray:
            if isinstance(env, VesselLoad):
                recorded_env_loads.append(env)
            return np.zeros(6)

    initial_state = np.zeros(6)
    rk4_step(
        StageEnvRecorderPlant(),
        tick=0,
        dt_s=0.1,
        state=initial_state,
        control_load=VesselLoad.zero(),
        environment_field=env_field,
        load_model=load_model,
    )

    assert len(recorded_env_loads) == 4
    # Stage 1 (t=0.0) and Stage 2 (t=0.05) must see distinct wave forces (NOT ZOH!)
    load_k1 = recorded_env_loads[0]
    load_k2 = recorded_env_loads[1]
    load_k4 = recorded_env_loads[3]

    # Waves vary with time, so stage loads differ
    assert not math.isclose(load_k1.sway_n, load_k2.sway_n, abs_tol=1.0)
    assert not math.isclose(load_k2.sway_n, load_k4.sway_n, abs_tol=1.0)


def test_rk4_endpoint_stage_satisfies_exact_time_identity() -> None:
    # Test that tick+1 with offset 0.0 matches physical time t + dt
    env_field = AnalyticEnvironmentField(dt_s=0.1, field_seed=99)
    # Stage 4 query identity: sample_at(tick=1, stage_offset_s=0.0)
    truth_stage4 = env_field.sample_at(tick=1, stage_offset_s=0.0)
    assert truth_stage4.tick == 1
    assert truth_stage4.stage_offset_s == 0.0
    assert math.isclose(truth_stage4.time_s, 0.1)


def test_rk4_direct_stage_timing_callback_has_four_independent_samples(plant: Generic3DOFPlant) -> None:
    timings: list[tuple[int, int]] = []
    state = np.array([0.0, 0.0, 0.0, 1.0, 0.0, 0.0])

    timed = rk4_step(
        plant,
        tick=0,
        dt_s=0.1,
        state=state,
        control_load=VesselLoad.zero(),
        stage_timing_sink=lambda stage, elapsed: timings.append((stage, elapsed)),
    )
    untimed = rk4_step(plant, tick=0, dt_s=0.1, state=state, control_load=VesselLoad.zero())

    assert [stage for stage, _ in timings] == [1, 2, 3, 4]
    assert len(timings) == 4
    assert all(elapsed >= 0 for _, elapsed in timings)
    np.testing.assert_array_equal(timed, untimed)


def test_rk4_rejects_nonfinite_during_stages(plant: Generic3DOFPlant) -> None:
    class FailingStagePlant:
        def __init__(self) -> None:
            self.call_count = 0

        def rhs(self, time_s: float, state: np.ndarray, ctrl: Any, env: Any = None) -> np.ndarray:
            self.call_count += 1
            if self.call_count == 3:  # Fails on stage 3 (k3)
                return np.array([0.0, float("nan"), 0.0, 0.0, 0.0, 0.0])
            return np.zeros(6)

    with pytest.raises(ValueError, match="non-finite"):
        rk4_step(
            FailingStagePlant(),
            tick=0,
            dt_s=0.1,
            state=np.zeros(6),
            control_load=VesselLoad.zero(),
        )
