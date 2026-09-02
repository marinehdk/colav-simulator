"""Fixed-step classical Runge-Kutta 4th order (RK4) integrator primitive (VR-11, TS-13, TS-14)."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import numpy as np

from colav_simulator.modular_gnc.contracts import (
    FloatArray,
    PlantState,
    VesselLoad,
    _finite_scalar,
    _non_bool_int,
)
from colav_simulator.modular_gnc.environment import AnalyticEnvironmentField
from colav_simulator.modular_gnc.load_model import EnvironmentalLoadModel
from colav_simulator.modular_gnc.plant import Generic3DOFPlant

if TYPE_CHECKING:
    from colav_simulator.modular_gnc.environment import EnvironmentField


class _Generic3DOFStageEvaluator:
    """Private typed stage evaluator bound at rk4_step entry for Generic3DOFPlant (Slice B/C)."""

    def __init__(
        self,
        plant: Generic3DOFPlant,
        environment_field: AnalyticEnvironmentField | None,
        load_model: EnvironmentalLoadModel | None,
        dt_s: float,
        tau_ctrl: tuple[float, float, float],
    ) -> None:
        self._plant = plant
        self._field = environment_field
        self._load_model = load_model
        self._dt_s = dt_s
        self._tau_ctrl = tau_ctrl

    def evaluate_stage(self, tick: int, stage_offset_s: float, state_vector: FloatArray) -> FloatArray:
        """Evaluate one RK stage with zero public dataclass reconstruction."""
        if not (0.0 <= stage_offset_s < self._dt_s):
            raise ValueError(f"stage_offset_s must be in [0, {self._dt_s}), got {stage_offset_s}")
        if not np.isfinite(state_vector).all():
            raise ValueError(f"stage state contains non-finite values: {state_vector}")

        if self._field is None or self._load_model is None:
            tau_env = (0.0, 0.0, 0.0)
        else:
            tau_env = self._load_model.compute_stage_load_3dof(
                field=self._field,
                tick=tick,
                stage_offset_s=stage_offset_s,
                state_vector=state_vector,
            )

        return self._plant.rhs_numeric_3dof(state_vector, self._tau_ctrl, tau_env)


def _query_env_load(
    environment_field: EnvironmentField | None,
    load_model: EnvironmentalLoadModel | None,
    tick: int,
    stage_offset_s: float,
    state_vector: FloatArray,
    capabilities: frozenset[str] | None = None,
) -> VesselLoad:
    """Evaluate environmental truth and vessel load at exact stage coordinate."""
    if environment_field is None or load_model is None:
        return VesselLoad.zero()
    pos = (float(state_vector[0]), float(state_vector[1]))
    truth = environment_field.sample_at(tick=tick, stage_offset_s=stage_offset_s, position_ne=pos)
    caps = (
        capabilities
        if capabilities is not None
        else (frozenset({"ROLL_4DOF"}) if len(state_vector) == 8 else frozenset({"PLANAR_3DOF"}))
    )
    vessel_state = PlantState(state_vector, caps)
    fast_compute = getattr(load_model, "compute_total_load_for_rhs", None)
    if fast_compute is not None and callable(fast_compute):
        return fast_compute(truth, vessel_state)
    env_loads = load_model.compute_loads(truth, vessel_state)
    return env_loads.total


def rk4_step(  # noqa: C901, PLR0912, PLR0915
    plant: Any,
    tick: int,
    dt_s: float,
    state: FloatArray | tuple[float, ...],
    control_load: VesselLoad | FloatArray | tuple[float, ...],
    environment_field: EnvironmentField | None = None,
    load_model: EnvironmentalLoadModel | None = None,
    stage_timing_sink: Callable[[int, int], None] | None = None,
) -> FloatArray:
    """Advance continuous plant state across one fixed simulation step dt_s using classical RK4.

    Evaluates 4 stages at exact physical coordinates:
        k1 = f(t, x_0, tau_ctrl, tau_env(t))
        k2 = f(t + dt/2, x_0 + 0.5*dt*k1, tau_ctrl, tau_env(t + dt/2))
        k3 = f(t + dt/2, x_0 + 0.5*dt*k2, tau_ctrl, tau_env(t + dt/2))
        k4 = f(t + dt, x_0 + dt*k3, tau_ctrl, tau_env(t + dt))
        x_next = x_0 + (dt / 6) * (k1 + 2*k2 + 2*k3 + k4)

    Intermediate stages:
    - Stage 4 evaluates at (tick+1, stage_offset=0.0) satisfying 0 <= stage_offset < dt.
    - Zero internal state mutation; discrete modules are not touched during intermediate stages.
    """
    valid_tick = _non_bool_int("tick", tick)
    valid_dt = _finite_scalar("dt_s", dt_s)
    if valid_dt <= 0.0:
        raise ValueError(f"dt_s must be positive, got {valid_dt}")

    x0 = np.asarray(state, dtype=np.float64)
    if x0.shape not in ((6,), (8,)):
        raise ValueError(f"state must have shape (6,) or (8,), got {x0.shape}")
    if not np.isfinite(x0).all():
        raise ValueError(f"initial state contains non-finite values: {x0}")

    state_shape = x0.shape
    half_dt = 0.5 * valid_dt

    use_fast_stage = (
        isinstance(plant, Generic3DOFPlant)
        and (environment_field is None or isinstance(environment_field, AnalyticEnvironmentField))
        and (load_model is None or isinstance(load_model, EnvironmentalLoadModel))
        and state_shape == (6,)
    )

    if use_fast_stage:
        if isinstance(control_load, VesselLoad):
            tau_ctrl = (float(control_load.surge_n), float(control_load.sway_n), float(control_load.yaw_nm))
        else:
            ctrl_arr = np.asarray(control_load, dtype=np.float64)
            if ctrl_arr.shape != (3,):
                raise ValueError(f"control_load must have shape (3,), got {ctrl_arr.shape}")
            if not np.isfinite(ctrl_arr).all():
                raise ValueError(f"control_load contains non-finite values: {ctrl_arr}")
            tau_ctrl = (float(ctrl_arr[0]), float(ctrl_arr[1]), float(ctrl_arr[2]))

        evaluator = _Generic3DOFStageEvaluator(
            plant=plant,
            environment_field=environment_field if isinstance(environment_field, AnalyticEnvironmentField) else None,
            load_model=load_model if isinstance(load_model, EnvironmentalLoadModel) else None,
            dt_s=valid_dt,
            tau_ctrl=tau_ctrl,
        )

        # --- Stage 1 (k1) at t0, stage_offset=0.0 ---
        stage_start_ns = time.perf_counter_ns() if stage_timing_sink is not None else 0
        k1 = evaluator.evaluate_stage(valid_tick, 0.0, x0)
        if stage_timing_sink is not None:
            stage_timing_sink(1, time.perf_counter_ns() - stage_start_ns)
        if k1.shape != state_shape or not np.isfinite(k1).all():
            raise ValueError(f"stage 1 derivative (k1) contains non-finite values: {k1}")

        # --- Stage 2 (k2) at t0 + dt/2, stage_offset=dt/2 ---
        x1 = x0 + half_dt * k1
        stage_start_ns = time.perf_counter_ns() if stage_timing_sink is not None else 0
        k2 = evaluator.evaluate_stage(valid_tick, half_dt, x1)
        if stage_timing_sink is not None:
            stage_timing_sink(2, time.perf_counter_ns() - stage_start_ns)
        if k2.shape != state_shape or not np.isfinite(k2).all():
            raise ValueError(f"stage 2 derivative (k2) contains non-finite values: {k2}")

        # --- Stage 3 (k3) at t0 + dt/2, stage_offset=dt/2 ---
        x2 = x0 + half_dt * k2
        stage_start_ns = time.perf_counter_ns() if stage_timing_sink is not None else 0
        k3 = evaluator.evaluate_stage(valid_tick, half_dt, x2)
        if stage_timing_sink is not None:
            stage_timing_sink(3, time.perf_counter_ns() - stage_start_ns)
        if k3.shape != state_shape or not np.isfinite(k3).all():
            raise ValueError(f"stage 3 derivative (k3) contains non-finite values: {k3}")

        # --- Stage 4 (k4) at t0 + dt, stage coordinate (tick+1, stage_offset=0.0) ---
        x3 = x0 + valid_dt * k3
        stage_start_ns = time.perf_counter_ns() if stage_timing_sink is not None else 0
        k4 = evaluator.evaluate_stage(valid_tick + 1, 0.0, x3)
        if stage_timing_sink is not None:
            stage_timing_sink(4, time.perf_counter_ns() - stage_start_ns)
        if k4.shape != state_shape or not np.isfinite(k4).all():
            raise ValueError(f"stage 4 derivative (k4) contains non-finite values: {k4}")

        # --- RK4 Combination ---
        x_next = x0 + (valid_dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
        if not np.isfinite(x_next).all():
            raise ValueError(f"integrated state contains non-finite values: {x_next}")

        return x_next

    # Fallback / Public path for non-AnalyticEnvironmentField or non-Generic3DOFPlant or non-EnvironmentalLoadModel
    caps = getattr(plant, "capabilities", None)
    t0 = valid_tick * valid_dt

    # --- Stage 1 (k1) at t0, stage_offset=0.0 ---
    stage_start_ns = time.perf_counter_ns() if stage_timing_sink is not None else 0
    env_load_1 = _query_env_load(environment_field, load_model, valid_tick, 0.0, x0, caps)
    k1 = np.asarray(plant.rhs(t0, x0, control_load, env_load_1), dtype=np.float64)
    if stage_timing_sink is not None:
        stage_timing_sink(1, time.perf_counter_ns() - stage_start_ns)
    if k1.shape != state_shape or not np.isfinite(k1).all():
        raise ValueError(f"stage 1 derivative (k1) contains non-finite values: {k1}")

    # --- Stage 2 (k2) at t0 + dt/2, stage_offset=dt/2 ---
    x1 = x0 + half_dt * k1
    stage_start_ns = time.perf_counter_ns() if stage_timing_sink is not None else 0
    env_load_2 = _query_env_load(environment_field, load_model, valid_tick, half_dt, x1, caps)
    k2 = np.asarray(plant.rhs(t0 + half_dt, x1, control_load, env_load_2), dtype=np.float64)
    if stage_timing_sink is not None:
        stage_timing_sink(2, time.perf_counter_ns() - stage_start_ns)
    if k2.shape != state_shape or not np.isfinite(k2).all():
        raise ValueError(f"stage 2 derivative (k2) contains non-finite values: {k2}")

    # --- Stage 3 (k3) at t0 + dt/2, stage_offset=dt/2 ---
    x2 = x0 + half_dt * k2
    stage_start_ns = time.perf_counter_ns() if stage_timing_sink is not None else 0
    env_load_3 = _query_env_load(environment_field, load_model, valid_tick, half_dt, x2, caps)
    k3 = np.asarray(plant.rhs(t0 + half_dt, x2, control_load, env_load_3), dtype=np.float64)
    if stage_timing_sink is not None:
        stage_timing_sink(3, time.perf_counter_ns() - stage_start_ns)
    if k3.shape != state_shape or not np.isfinite(k3).all():
        raise ValueError(f"stage 3 derivative (k3) contains non-finite values: {k3}")

    # --- Stage 4 (k4) at t0 + dt, stage coordinate (tick+1, stage_offset=0.0) ---
    x3 = x0 + valid_dt * k3
    stage_start_ns = time.perf_counter_ns() if stage_timing_sink is not None else 0
    env_load_4 = _query_env_load(environment_field, load_model, valid_tick + 1, 0.0, x3, caps)
    k4 = np.asarray(plant.rhs(t0 + valid_dt, x3, control_load, env_load_4), dtype=np.float64)
    if stage_timing_sink is not None:
        stage_timing_sink(4, time.perf_counter_ns() - stage_start_ns)
    if k4.shape != state_shape or not np.isfinite(k4).all():
        raise ValueError(f"stage 4 derivative (k4) contains non-finite values: {k4}")

    # --- RK4 Combination ---
    x_next = x0 + (valid_dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
    if not np.isfinite(x_next).all():
        raise ValueError(f"integrated state contains non-finite values: {x_next}")

    return x_next
