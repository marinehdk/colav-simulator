"""Transparent Marine PID motion controller under ideal generalized-load fidelity (Issue #55, VR-13..15/19, TS-19..21)."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from colav_simulator.modular_gnc.contracts import (
    AchievedGeneralizedLoad,
    AchievedLoadStatus,
    ControlTask,
    DirectReference,
    MarinePIDTrace,
    NavigationState,
    VesselLoad,
    _finite_scalar,
    _non_bool_int,
)


def wrap_to_pi(angle: float) -> float:
    """Wrap angle to [-pi, pi] in radians (TS-04, VR-20)."""
    wrapped = (angle + math.pi) % (2.0 * math.pi) - math.pi
    if wrapped == -math.pi and angle > 0:
        return math.pi
    return float(wrapped)


def _validate_3tuple_non_negative(name: str, values: Any) -> tuple[float, float, float]:
    """Validate 3-element tuple of finite non-negative numbers without bool coercion."""
    if not isinstance(values, (tuple, list)) or len(values) != 3:
        raise ValueError(f"{name} must be a 3-element sequence, got {values!r}")
    result = []
    for i, v in enumerate(values):
        val = _finite_scalar(f"{name}[{i}]", v)
        if val < 0.0:
            raise ValueError(f"{name}[{i}] must be non-negative, got {val}")
        result.append(val)
    return (result[0], result[1], result[2])


def _validate_3tuple_finite(name: str, values: Any) -> tuple[float, float, float]:
    """Validate 3-element tuple of finite numbers without bool coercion."""
    if not isinstance(values, (tuple, list)) or len(values) != 3:
        raise ValueError(f"{name} must be a 3-element sequence, got {values!r}")
    result = [_finite_scalar(f"{name}[{i}]", v) for i, v in enumerate(values)]
    return (result[0], result[1], result[2])


@dataclass(frozen=True)
class MarinePIDConfig:
    """Immutable, strictly validated configuration for 3DOF Marine PID controller.

    Channel assignments (3DOF generalized load, SI units):
    - Channel 0: Surge force X (N)
    - Channel 1: Sway force Y (N)
    - Channel 2: Yaw moment N (N·m)

    Key design rules:
    - Derivative on measurement (no derivative kick on reference jump).
    - Time-step aware low-pass derivative filter: alpha = dt / (tau_d + dt).
    - Exactly one tracking anti-windup path using back-calculation from achieved-vs-requested force.
    - No hidden NDO, SMC, gain scheduling, vessel names, or scenario policies.
    """

    kp: tuple[float, float, float]
    ki: tuple[float, float, float]
    kd: tuple[float, float, float]
    tau_d: tuple[float, float, float] = (0.1, 0.1, 0.1)
    antiwindup_gain: tuple[float, float, float] = (1.0, 1.0, 1.0)
    min_output: tuple[float, float, float] = (-1e6, -1e6, -1e6)
    max_output: tuple[float, float, float] = (1e6, 1e6, 1e6)
    feedforward_gain: tuple[float, float, float] = (0.0, 0.0, 0.0)
    integral_limit: tuple[float, float, float] | None = None
    allow_ideal_passthrough: bool = True
    position_mode: bool = False
    reference_shaper_enable: bool = False
    heading_rate_limit_rad_s: float = 0.0
    heading_accel_limit_rad_s2: float = 0.0
    yaw_rate_ff_gain: float = 0.0
    yaw_accel_ff_gain: float = 0.0
    config_hash: str = field(init=False)

    def __post_init__(self) -> None:
        """Validate parameter types, ranges, limits consistency, and compute SHA-256 hash."""
        kp_val = _validate_3tuple_non_negative("kp", self.kp)
        ki_val = _validate_3tuple_non_negative("ki", self.ki)
        kd_val = _validate_3tuple_non_negative("kd", self.kd)
        tau_d_val = _validate_3tuple_non_negative("tau_d", self.tau_d)
        aw_val = _validate_3tuple_non_negative("antiwindup_gain", self.antiwindup_gain)
        min_out_val = _validate_3tuple_finite("min_output", self.min_output)
        max_out_val = _validate_3tuple_finite("max_output", self.max_output)
        ff_val = _validate_3tuple_non_negative("feedforward_gain", self.feedforward_gain)

        for i in range(3):
            if min_out_val[i] > max_out_val[i]:
                raise ValueError(f"min_output[{i}] ({min_out_val[i]}) cannot exceed max_output[{i}] ({max_out_val[i]})")

        int_lim_val = None
        if self.integral_limit is not None:
            int_lim_val = _validate_3tuple_non_negative("integral_limit", self.integral_limit)

        if not isinstance(self.allow_ideal_passthrough, bool):
            raise TypeError(f"allow_ideal_passthrough must be bool, got {type(self.allow_ideal_passthrough).__name__}")
        if not isinstance(self.position_mode, bool):
            raise TypeError(f"position_mode must be bool, got {type(self.position_mode).__name__}")
        if not isinstance(self.reference_shaper_enable, bool):
            raise TypeError(
                f"reference_shaper_enable must be bool, got {type(self.reference_shaper_enable).__name__}"
            )

        rate_lim = _finite_scalar("heading_rate_limit_rad_s", self.heading_rate_limit_rad_s)
        accel_lim = _finite_scalar("heading_accel_limit_rad_s2", self.heading_accel_limit_rad_s2)
        if rate_lim < 0.0:
            raise ValueError(f"heading_rate_limit_rad_s must be non-negative, got {rate_lim}")
        if accel_lim < 0.0:
            raise ValueError(f"heading_accel_limit_rad_s2 must be non-negative, got {accel_lim}")
        if self.reference_shaper_enable and (rate_lim <= 0.0 or accel_lim <= 0.0):
            raise ValueError(
                "reference_shaper_enable requires strictly positive heading_rate_limit_rad_s and "
                f"heading_accel_limit_rad_s2 (got {rate_lim}, {accel_lim})"
            )

        rate_ff = _finite_scalar("yaw_rate_ff_gain", self.yaw_rate_ff_gain)
        accel_ff = _finite_scalar("yaw_accel_ff_gain", self.yaw_accel_ff_gain)
        if rate_ff < 0.0:
            raise ValueError(f"yaw_rate_ff_gain must be non-negative, got {rate_ff}")
        if accel_ff < 0.0:
            raise ValueError(f"yaw_accel_ff_gain must be non-negative, got {accel_ff}")

        object.__setattr__(self, "kp", kp_val)
        object.__setattr__(self, "ki", ki_val)
        object.__setattr__(self, "kd", kd_val)
        object.__setattr__(self, "tau_d", tau_d_val)
        object.__setattr__(self, "antiwindup_gain", aw_val)
        object.__setattr__(self, "min_output", min_out_val)
        object.__setattr__(self, "max_output", max_out_val)
        object.__setattr__(self, "feedforward_gain", ff_val)
        object.__setattr__(self, "integral_limit", int_lim_val)
        object.__setattr__(self, "heading_rate_limit_rad_s", rate_lim)
        object.__setattr__(self, "heading_accel_limit_rad_s2", accel_lim)
        object.__setattr__(self, "yaw_rate_ff_gain", rate_ff)
        object.__setattr__(self, "yaw_accel_ff_gain", accel_ff)

        # Content-addressed hash for reproducibility (TS-27)
        canonical = {
            "kp": list(kp_val),
            "ki": list(ki_val),
            "kd": list(kd_val),
            "tau_d": list(tau_d_val),
            "antiwindup_gain": list(aw_val),
            "min_output": list(min_out_val),
            "max_output": list(max_out_val),
            "feedforward_gain": list(ff_val),
            "integral_limit": list(int_lim_val) if int_lim_val is not None else None,
            "allow_ideal_passthrough": self.allow_ideal_passthrough,
            "position_mode": self.position_mode,
            "reference_shaper_enable": self.reference_shaper_enable,
            "heading_rate_limit_rad_s": rate_lim,
            "heading_accel_limit_rad_s2": accel_lim,
            "yaw_rate_ff_gain": rate_ff,
            "yaw_accel_ff_gain": accel_ff,
        }
        raw_json = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
        object.__setattr__(self, "config_hash", hashlib.sha256(raw_json.encode("utf-8")).hexdigest())

    @classmethod
    def from_params(cls, params: Mapping[str, Any]) -> MarinePIDConfig:
        """Construct MarinePIDConfig from dictionary or parameter mapping."""
        kwargs: dict[str, Any] = {}
        for key in (
            "kp",
            "ki",
            "kd",
            "tau_d",
            "antiwindup_gain",
            "min_output",
            "max_output",
            "feedforward_gain",
            "integral_limit",
            "allow_ideal_passthrough",
            "position_mode",
            "reference_shaper_enable",
            "heading_rate_limit_rad_s",
            "heading_accel_limit_rad_s2",
            "yaw_rate_ff_gain",
            "yaw_accel_ff_gain",
        ):
            if key in params:
                kwargs[key] = params[key]
        return cls(**kwargs)

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary representation."""
        return {
            "kp": list(self.kp),
            "ki": list(self.ki),
            "kd": list(self.kd),
            "tau_d": list(self.tau_d),
            "antiwindup_gain": list(self.antiwindup_gain),
            "min_output": list(self.min_output),
            "max_output": list(self.max_output),
            "feedforward_gain": list(self.feedforward_gain),
            "integral_limit": list(self.integral_limit) if self.integral_limit is not None else None,
            "allow_ideal_passthrough": self.allow_ideal_passthrough,
            "position_mode": self.position_mode,
            "reference_shaper_enable": self.reference_shaper_enable,
            "heading_rate_limit_rad_s": self.heading_rate_limit_rad_s,
            "heading_accel_limit_rad_s2": self.heading_accel_limit_rad_s2,
            "yaw_rate_ff_gain": self.yaw_rate_ff_gain,
            "yaw_accel_ff_gain": self.yaw_accel_ff_gain,
            "config_hash": self.config_hash,
        }


@dataclass(frozen=True)
class MarinePIDSnapshot:
    """Deterministic snapshot of internal MarinePID state for pause/resume and replay."""

    schema_version: str
    integral: tuple[float, float, float]
    prev_measurement: tuple[float, float, float] | None
    filtered_derivative: tuple[float, float, float]
    initialized: bool
    last_trace: MarinePIDTrace | None = None
    shaper_state: tuple[float, float, float] | None = None

    def __post_init__(self) -> None:
        """Validate snapshot schema version and components."""
        if self.schema_version != "marine-pid.snapshot.v1":
            raise ValueError(f"unsupported snapshot schema_version: {self.schema_version}")
        object.__setattr__(self, "integral", _validate_3tuple_finite("integral", self.integral))
        if self.prev_measurement is not None:
            object.__setattr__(
                self,
                "prev_measurement",
                _validate_3tuple_finite("prev_measurement", self.prev_measurement),
            )
        object.__setattr__(
            self,
            "filtered_derivative",
            _validate_3tuple_finite("filtered_derivative", self.filtered_derivative),
        )
        if self.shaper_state is not None:
            shaper = _validate_3tuple_finite("shaper_state", self.shaper_state)
            object.__setattr__(self, "shaper_state", shaper)


class MarinePID:
    """Transparent 3DOF marine PID motion controller.

    Outputs 3DOF generalized forces [X, Y, N] with:
    - Derivative on measurement (no derivative kick on setpoint step).
    - Time-step aware derivative filter alpha = dt / (tau_d + dt).
    - Single tracking anti-windup path (back-calculation from achieved force).
    - Achieved load feedback contract with explicit ideal pass-through option.
    - Term-level trace decomposition for attribution and diagnostics.
    """

    capabilities: frozenset[str] = frozenset({"TRANSIT", "GENERALIZED_FORCE", "CONTROLLER_TRACE"})

    def __init__(self, config: MarinePIDConfig) -> None:
        """Initialize controller with immutable configuration."""
        if not isinstance(config, MarinePIDConfig):
            raise TypeError(f"config must be MarinePIDConfig, got {type(config).__name__}")
        self._config = config
        self._integral = np.zeros(3, dtype=np.float64)
        self._prev_measurement: np.ndarray | None = None
        self._filtered_derivative = np.zeros(3, dtype=np.float64)
        self._initialized = False
        self._latest_trace: MarinePIDTrace | None = None
        self._shaper_state: tuple[float, float, float] | None = None

    @property
    def supported_tasks(self) -> frozenset[ControlTask]:
        """Declare executable control tasks from configuration (Issue #56, AC1).

        Velocity mode tracks transit references only; position mode regulates body-frame
        pose errors and therefore additionally executes POSE_HOLD.
        """
        if self._config.position_mode:
            return frozenset({ControlTask.TRANSIT, ControlTask.POSE_HOLD})
        return frozenset({ControlTask.TRANSIT})

    @property
    def config(self) -> MarinePIDConfig:
        """Return controller configuration."""
        return self._config

    @property
    def latest_trace(self) -> MarinePIDTrace | None:
        """Return latest per-tick trace."""
        return self._latest_trace

    def reset(self, seed: int = 0) -> None:  # noqa: ARG002
        """Idempotently reset all internal integrator and filter states."""
        self._integral = np.zeros(3, dtype=np.float64)
        self._prev_measurement = None
        self._filtered_derivative = np.zeros(3, dtype=np.float64)
        self._initialized = True
        self._latest_trace = None
        self._shaper_state = None

    def snapshot(self) -> MarinePIDSnapshot:
        """Capture deterministic internal state for replay."""
        return MarinePIDSnapshot(
            schema_version="marine-pid.snapshot.v1",
            integral=(float(self._integral[0]), float(self._integral[1]), float(self._integral[2])),
            prev_measurement=(
                (
                    float(self._prev_measurement[0]),
                    float(self._prev_measurement[1]),
                    float(self._prev_measurement[2]),
                )
                if self._prev_measurement is not None
                else None
            ),
            filtered_derivative=(
                float(self._filtered_derivative[0]),
                float(self._filtered_derivative[1]),
                float(self._filtered_derivative[2]),
            ),
            initialized=self._initialized,
            last_trace=self._latest_trace,
            shaper_state=self._shaper_state,
        )

    def restore(self, snapshot: MarinePIDSnapshot) -> None:
        """Restore exact internal state from snapshot."""
        if not isinstance(snapshot, MarinePIDSnapshot):
            raise TypeError(f"snapshot must be MarinePIDSnapshot, got {type(snapshot).__name__}")
        self._integral = np.array(snapshot.integral, dtype=np.float64)
        self._prev_measurement = (
            np.array(snapshot.prev_measurement, dtype=np.float64) if snapshot.prev_measurement is not None else None
        )
        self._filtered_derivative = np.array(snapshot.filtered_derivative, dtype=np.float64)
        self._initialized = snapshot.initialized
        self._latest_trace = snapshot.last_trace
        self._shaper_state = snapshot.shaper_state

    def _shape_heading_reference(
        self,
        measurement: NavigationState,
        raw_heading: float,
        dt: float,
    ) -> tuple[float, float, float]:
        """Advance the third-order (psi_d, r_d, rdot_d) reference chain one control step.

        Fossen Handbook 2nd ed. SS15.2/SS12.1.1 reference model with rate and
        acceleration saturation (Issue #67): the commanded heading is tracked by
        an integrator chain whose braking rate follows the double-integrator
        energy law r* = sqrt(2 * a_max * |e|) (capped at the rate limit), and
        whose rate can only change within the acceleration limit.  The chain is
        bumplessly initialised from the measured heading and yaw rate on first
        use after reset.  Angle errors take the shortest wrapped path.
        """
        if self._shaper_state is None:
            self._shaper_state = (float(measurement.heading_rad), float(measurement.yaw_rate_radps), 0.0)

        psi_d, r_d, _rdot_d = self._shaper_state
        error = wrap_to_pi(raw_heading - psi_d)
        rate_cap = self._config.heading_rate_limit_rad_s
        accel_cap = self._config.heading_accel_limit_rad_s2

        # Braking law evaluated on the look-ahead error: the distance that will
        # remain after this step's advance at the current rate.  Commanding
        # r* <= sqrt(2*a*look_ahead) keeps the invariant r <= sqrt(2*a*|e|)
        # after every discrete step, so the chain brakes to the target instead
        # of the discrete sqrt-law limit cycle.
        abs_error = abs(error)
        advance_now = abs(r_d) * dt
        terminal_band = accel_cap * dt * dt
        if abs_error <= terminal_band + advance_now:
            # Terminal band: deadbeat rate that lands exactly on the target.
            r_star = error / dt
        else:
            look_ahead = abs_error - advance_now
            r_star = math.copysign(min(rate_cap, math.sqrt(2.0 * accel_cap * look_ahead)), error)
        # Acceleration-limited (deadbeat-clamped) tracking of the braking rate.
        rdot = max(-accel_cap, min(accel_cap, (r_star - r_d) / dt))
        r_d_new = max(-rate_cap, min(rate_cap, r_d + rdot * dt))
        psi_d_new = wrap_to_pi(psi_d + r_d_new * dt)

        self._shaper_state = (psi_d_new, r_d_new, rdot)
        return self._shaper_state

    def _extract_signals(
        self, measurement: NavigationState, reference: DirectReference
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Extract measurement vector, reference vector, and tracking errors."""
        if self._config.position_mode:
            e_n = reference.values[0] - measurement.north_m
            e_e = reference.values[1] - measurement.east_m
            cos_psi = math.cos(measurement.heading_rad)
            sin_psi = math.sin(measurement.heading_rad)
            e_surge = cos_psi * e_n + sin_psi * e_e
            e_sway = -sin_psi * e_n + cos_psi * e_e
            meas_vec = np.array(
                [
                    cos_psi * measurement.north_m + sin_psi * measurement.east_m,
                    -sin_psi * measurement.north_m + cos_psi * measurement.east_m,
                    measurement.heading_rad,
                ],
                dtype=np.float64,
            )
            ref_vec = np.array(
                [
                    cos_psi * reference.values[0] + sin_psi * reference.values[1],
                    -sin_psi * reference.values[0] + cos_psi * reference.values[1],
                    reference.values[2],
                ],
                dtype=np.float64,
            )
        else:
            e_surge = reference.values[3] - measurement.surge_mps
            e_sway = reference.values[4] - measurement.sway_mps
            meas_vec = np.array(
                [measurement.surge_mps, measurement.sway_mps, measurement.heading_rad],
                dtype=np.float64,
            )
            ref_vec = np.array([reference.values[3], reference.values[4], reference.values[2]], dtype=np.float64)

        e_yaw = wrap_to_pi(reference.values[2] - measurement.heading_rad)
        errors = np.array([e_surge, e_sway, e_yaw], dtype=np.float64)
        return meas_vec, ref_vec, errors

    def _update_derivative(self, meas_vec: np.ndarray, dt: float) -> np.ndarray:
        """Update filtered derivative on measurement and return D-term."""
        d_raw = np.zeros(3, dtype=np.float64)
        if self._prev_measurement is not None:
            d_raw[0] = (meas_vec[0] - self._prev_measurement[0]) / dt
            d_raw[1] = (meas_vec[1] - self._prev_measurement[1]) / dt
            d_raw[2] = wrap_to_pi(meas_vec[2] - self._prev_measurement[2]) / dt

        d_filt = np.zeros(3, dtype=np.float64)
        for i in range(3):
            tau = self._config.tau_d[i]
            if tau > 0.0:
                alpha = dt / (tau + dt)
                d_filt[i] = (1.0 - alpha) * self._filtered_derivative[i] + alpha * d_raw[i]
            else:
                d_filt[i] = d_raw[i]

        self._filtered_derivative = d_filt.copy()
        self._prev_measurement = meas_vec.copy()
        return -np.array(self._config.kd, dtype=np.float64) * d_filt

    def _resolve_achieved_load(
        self,
        achieved_load: AchievedGeneralizedLoad | None,
        sat_output: np.ndarray,
    ) -> np.ndarray:
        """Resolve achieved generalized load feedback or ideal pass-through."""
        if achieved_load is not None and achieved_load.status == AchievedLoadStatus.AVAILABLE:
            return np.array(
                [achieved_load.surge_n, achieved_load.sway_n, achieved_load.yaw_nm],
                dtype=np.float64,
            )
        if self._config.allow_ideal_passthrough:
            return sat_output.copy()
        raise RuntimeError(
            "AchievedGeneralizedLoad feedback is unavailable and allow_ideal_passthrough is False "
            "(TS-20, VR-15, VR-19: no truth leakage without explicit ideal pass-through)"
        )

    def _condition_reference(
        self,
        measurement: NavigationState,
        reference: DirectReference,
        dt: float,
    ) -> tuple[DirectReference, dict[str, Any], float, float]:
        """Apply pre-PID reference conditioning and report its trace details.

        Currently one stage: the third-order heading reference shaper (when
        enabled).  Returns the conditioned reference, trace details, and the
        reference yaw rate/acceleration pair that feedforward stages consume
        (shaper chain when enabled, otherwise DirectReference values[5]/[8]).
        """
        details: dict[str, Any] = {}
        ff_r_d = float(reference.values[5])
        ff_rdot_d = float(reference.values[8])
        if self._config.reference_shaper_enable:
            psi_d, r_d, rdot_d = self._shape_heading_reference(measurement, float(reference.values[2]), dt)
            shaped_values = np.array(reference.values, dtype=np.float64)
            shaped_values[2] = psi_d
            reference = DirectReference(shaped_values, reference.latched_tick, reference.task)
            ff_r_d = r_d
            ff_rdot_d = rdot_d
            details["reference_shaper"] = {
                "psi_d_rad": psi_d,
                "r_d_rad_s": r_d,
                "rdot_d_rad_s2": rdot_d,
            }
        return reference, details, ff_r_d, ff_rdot_d

    def compute_control(
        self,
        measurement: NavigationState,
        reference: DirectReference,
        dt_s: float,
        tick: int = 0,
        time_s: float = 0.0,
        achieved_load: AchievedGeneralizedLoad | None = None,
    ) -> tuple[VesselLoad, MarinePIDTrace]:
        """Compute 3DOF generalized control loads and term decomposition trace."""
        if not self._initialized:
            self.reset()

        if not isinstance(measurement, NavigationState):
            raise TypeError(f"measurement must be NavigationState, got {type(measurement).__name__}")
        if not isinstance(reference, DirectReference):
            raise TypeError(f"reference must be DirectReference, got {type(reference).__name__}")

        dt = _finite_scalar("dt_s", dt_s)
        if dt <= 0.0:
            raise ValueError(f"dt_s must be positive, got {dt}")
        tick_int = _non_bool_int("tick", tick)
        time_float = _finite_scalar("time_s", time_s)

        reference, details, ff_r_d, ff_rdot_d = self._condition_reference(measurement, reference, dt)

        meas_vec, ref_vec, errors = self._extract_signals(measurement, reference)
        d_term = self._update_derivative(meas_vec, dt)
        p_term = np.array(self._config.kp, dtype=np.float64) * errors

        ref_ff = np.array([reference.values[6], reference.values[7], reference.values[8]], dtype=np.float64)
        ff_term = np.array(self._config.feedforward_gain, dtype=np.float64) * ref_ff

        # Nomoto inverse feedforward (Issue #67 slice 3): the yaw moment the
        # first-order Nomoto equivalent needs for the (shaped or raw) reference
        # rate/acceleration, tau_FF = I_eff*rdot_d + d_eff*r_d.  It is folded
        # into the yaw feedforward term so the DP-15 decomposition identity
        # raw = p + i + d + feedforward keeps holding and saturation/anti-windup
        # see one explainable chain.
        if self._config.yaw_accel_ff_gain > 0.0 or self._config.yaw_rate_ff_gain > 0.0:
            nomoto_ff_yaw = self._config.yaw_accel_ff_gain * ff_rdot_d + self._config.yaw_rate_ff_gain * ff_r_d
            ff_term[2] += nomoto_ff_yaw
            details["nomoto_feedforward"] = {
                "yaw_nm": float(nomoto_ff_yaw),
                "r_d_rad_s": ff_r_d,
                "rdot_d_rad_s2": ff_rdot_d,
            }

        i_term = self._integral.copy()
        raw_request = p_term + i_term + d_term + ff_term

        min_out = np.array(self._config.min_output, dtype=np.float64)
        max_out = np.array(self._config.max_output, dtype=np.float64)
        sat_output = np.clip(raw_request, min_out, max_out)

        sat_flags = (
            bool(raw_request[0] > max_out[0] or raw_request[0] < min_out[0]),
            bool(raw_request[1] > max_out[1] or raw_request[1] < min_out[1]),
            bool(raw_request[2] > max_out[2] or raw_request[2] < min_out[2]),
        )

        achieved_out = self._resolve_achieved_load(achieved_load, sat_output)
        aw_gain = np.array(self._config.antiwindup_gain, dtype=np.float64)
        e_sat = achieved_out - raw_request
        aw_correction = aw_gain * e_sat

        ki = np.array(self._config.ki, dtype=np.float64)
        delta_i = dt * (ki * errors + aw_correction)
        next_integral = self._integral + delta_i

        if self._config.integral_limit is not None:
            lim = np.array(self._config.integral_limit, dtype=np.float64)
            next_integral = np.clip(next_integral, -lim, lim)

        self._integral = next_integral

        trace = MarinePIDTrace(
            tick=tick_int,
            time_s=time_float,
            dt_s=dt,
            errors=(float(errors[0]), float(errors[1]), float(errors[2])),
            measurement=(float(meas_vec[0]), float(meas_vec[1]), float(meas_vec[2])),
            reference=(float(ref_vec[0]), float(ref_vec[1]), float(ref_vec[2])),
            p_term=(float(p_term[0]), float(p_term[1]), float(p_term[2])),
            i_term=(float(i_term[0]), float(i_term[1]), float(i_term[2])),
            d_term=(float(d_term[0]), float(d_term[1]), float(d_term[2])),
            feedforward=(float(ff_term[0]), float(ff_term[1]), float(ff_term[2])),
            raw_request=(float(raw_request[0]), float(raw_request[1]), float(raw_request[2])),
            saturated_output=(float(sat_output[0]), float(sat_output[1]), float(sat_output[2])),
            saturation_flags=sat_flags,
            antiwindup_correction=(float(aw_correction[0]), float(aw_correction[1]), float(aw_correction[2])),
            achieved_output=(float(achieved_out[0]), float(achieved_out[1]), float(achieved_out[2])),
            details=details,
        )
        self._latest_trace = trace

        vessel_load = VesselLoad(
            surge_n=float(sat_output[0]),
            sway_n=float(sat_output[1]),
            yaw_nm=float(sat_output[2]),
            roll_nm=0.0,
        )
        return vessel_load, trace
