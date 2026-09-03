"""Fixed-step classical Runge-Kutta 4th order (RK4) integrator primitive (VR-11, TS-13, TS-14)."""

from __future__ import annotations

import math
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
    """Private typed stage evaluator bound at rk4_step entry for Generic3DOFPlant (Slice 3B/3C)."""

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

    def evaluate_stage_raw(
        self,
        tick: int,
        stage_offset_s: float,
        north: float,
        east: float,
        psi: float,
        u: float,
        v: float,
        r: float,
    ) -> tuple[float, float, float, float, float, float]:
        """Evaluate one RK stage returning raw 6-tuple with zero intermediate allocations (Slice 3C)."""
        if not (0.0 <= stage_offset_s < self._dt_s):
            raise ValueError(f"stage_offset_s must be in [0, {self._dt_s}), got {stage_offset_s}")
        if not (
            math.isfinite(north)
            and math.isfinite(east)
            and math.isfinite(psi)
            and math.isfinite(u)
            and math.isfinite(v)
            and math.isfinite(r)
        ):
            raise ValueError(f"stage state contains non-finite values: [{north}, {east}, {psi}, {u}, {v}, {r}]")

        if self._field is None or self._load_model is None:
            tau_env = (0.0, 0.0, 0.0)
        else:
            tau_env = self._load_model.compute_stage_load_3dof_raw(
                field=self._field,
                tick=tick,
                stage_offset_s=stage_offset_s,
                psi=psi,
                u=u,
                v=v,
            )

        return self._plant.rhs_numeric_3dof_raw(north, east, psi, u, v, r, self._tau_ctrl, tau_env)

    def evaluate_stage(self, tick: int, stage_offset_s: float, state_vector: FloatArray) -> FloatArray:
        """Evaluate one RK stage with zero public dataclass reconstruction."""
        res = self.evaluate_stage_raw(
            tick,
            stage_offset_s,
            float(state_vector[0]),
            float(state_vector[1]),
            float(state_vector[2]),
            float(state_vector[3]),
            float(state_vector[4]),
            float(state_vector[5]),
        )
        return np.array(res, dtype=np.float64)


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

        x0_0 = float(x0[0])
        x0_1 = float(x0[1])
        x0_2 = float(x0[2])
        x0_3 = float(x0[3])
        x0_4 = float(x0[4])
        x0_5 = float(x0[5])

        # --- Stage 1 (k1) at t0, stage_offset=0.0 ---
        stage_start_ns = time.perf_counter_ns() if stage_timing_sink is not None else 0
        k1_0, k1_1, k1_2, k1_3, k1_4, k1_5 = evaluator.evaluate_stage_raw(
            valid_tick, 0.0, x0_0, x0_1, x0_2, x0_3, x0_4, x0_5
        )
        if stage_timing_sink is not None:
            stage_timing_sink(1, time.perf_counter_ns() - stage_start_ns)

        # --- Stage 2 (k2) at t0 + dt/2, stage_offset=dt/2 ---
        x1_0 = x0_0 + half_dt * k1_0
        x1_1 = x0_1 + half_dt * k1_1
        x1_2 = x0_2 + half_dt * k1_2
        x1_3 = x0_3 + half_dt * k1_3
        x1_4 = x0_4 + half_dt * k1_4
        x1_5 = x0_5 + half_dt * k1_5

        stage_start_ns = time.perf_counter_ns() if stage_timing_sink is not None else 0
        k2_0, k2_1, k2_2, k2_3, k2_4, k2_5 = evaluator.evaluate_stage_raw(
            valid_tick, half_dt, x1_0, x1_1, x1_2, x1_3, x1_4, x1_5
        )
        if stage_timing_sink is not None:
            stage_timing_sink(2, time.perf_counter_ns() - stage_start_ns)

        # --- Stage 3 (k3) at t0 + dt/2, stage_offset=dt/2 ---
        x2_0 = x0_0 + half_dt * k2_0
        x2_1 = x0_1 + half_dt * k2_1
        x2_2 = x0_2 + half_dt * k2_2
        x2_3 = x0_3 + half_dt * k2_3
        x2_4 = x0_4 + half_dt * k2_4
        x2_5 = x0_5 + half_dt * k2_5

        stage_start_ns = time.perf_counter_ns() if stage_timing_sink is not None else 0
        k3_0, k3_1, k3_2, k3_3, k3_4, k3_5 = evaluator.evaluate_stage_raw(
            valid_tick, half_dt, x2_0, x2_1, x2_2, x2_3, x2_4, x2_5
        )
        if stage_timing_sink is not None:
            stage_timing_sink(3, time.perf_counter_ns() - stage_start_ns)

        # --- Stage 4 (k4) at t0 + dt, stage coordinate (tick+1, stage_offset=0.0) ---
        x3_0 = x0_0 + valid_dt * k3_0
        x3_1 = x0_1 + valid_dt * k3_1
        x3_2 = x0_2 + valid_dt * k3_2
        x3_3 = x0_3 + valid_dt * k3_3
        x3_4 = x0_4 + valid_dt * k3_4
        x3_5 = x0_5 + valid_dt * k3_5

        stage_start_ns = time.perf_counter_ns() if stage_timing_sink is not None else 0
        k4_0, k4_1, k4_2, k4_3, k4_4, k4_5 = evaluator.evaluate_stage_raw(
            valid_tick + 1, 0.0, x3_0, x3_1, x3_2, x3_3, x3_4, x3_5
        )
        if stage_timing_sink is not None:
            stage_timing_sink(4, time.perf_counter_ns() - stage_start_ns)

        # --- RK4 Combination ---
        dt_6 = valid_dt / 6.0
        x_next_0 = x0_0 + dt_6 * (k1_0 + 2.0 * k2_0 + 2.0 * k3_0 + k4_0)
        x_next_1 = x0_1 + dt_6 * (k1_1 + 2.0 * k2_1 + 2.0 * k3_1 + k4_1)
        x_next_2 = x0_2 + dt_6 * (k1_2 + 2.0 * k2_2 + 2.0 * k3_2 + k4_2)
        x_next_3 = x0_3 + dt_6 * (k1_3 + 2.0 * k2_3 + 2.0 * k3_3 + k4_3)
        x_next_4 = x0_4 + dt_6 * (k1_4 + 2.0 * k2_4 + 2.0 * k3_4 + k4_4)
        x_next_5 = x0_5 + dt_6 * (k1_5 + 2.0 * k2_5 + 2.0 * k3_5 + k4_5)

        if not (
            math.isfinite(x_next_0)
            and math.isfinite(x_next_1)
            and math.isfinite(x_next_2)
            and math.isfinite(x_next_3)
            and math.isfinite(x_next_4)
            and math.isfinite(x_next_5)
        ):
            raise ValueError(
                f"integrated state contains non-finite values: "
                f"[{x_next_0}, {x_next_1}, {x_next_2}, {x_next_3}, {x_next_4}, {x_next_5}]"
            )

        return np.array(
            [x_next_0, x_next_1, x_next_2, x_next_3, x_next_4, x_next_5],
            dtype=np.float64,
        )

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
