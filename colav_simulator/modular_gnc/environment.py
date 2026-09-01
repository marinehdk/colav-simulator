"""Deterministic immutable environment field and keyed PRF generation."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping, Sequence
from typing import Any, Protocol, runtime_checkable

from colav_simulator.modular_gnc.contracts import (
    CurrentReference,
    CurrentSample,
    EnvironmentObservation,
    EnvironmentTruth,
    FloatArray,
    MeanDriftSourceSample,
    WaveComponent,
    WaveFieldSample,
    WindSample,
    _finite_scalar,
)


def derive_prf_seed(master_seed: int, domain: str) -> int:
    """Derive deterministic non-negative 64-bit integer seed for a named domain."""
    h = hashlib.sha256(f"{int(master_seed)}:{str(domain)}".encode()).digest()
    return int.from_bytes(h[:8], byteorder="big", signed=False)


def prf_uniform(seed: int, tick: int, channel: str) -> float:
    """Generate stateless uniform float in [0.0, 1.0) using keyed PRF."""
    h = hashlib.sha256(f"{int(seed)}:{str(channel)}:{int(tick)}".encode()).digest()
    val = int.from_bytes(h[:8], byteorder="big", signed=False) >> 11
    return float(val / (1 << 53))


def prf_gaussian(seed: int, tick: int, channel: str) -> float:
    """Generate stateless standard normal float using Box-Muller transform on keyed PRF."""
    u1 = max(1e-15, prf_uniform(seed, tick, f"{channel}:u1"))
    u2 = prf_uniform(seed, tick, f"{channel}:u2")
    return float(math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2))


def _generate_wave_components(
    significant_height_m: float,
    peak_period_s: float,
    direction_to_rad: float,
    num_components: int,
    directional_spread_rad: float,
    field_seed: int,
) -> tuple[WaveComponent, ...]:
    """Generate pre-computed harmonic wave components deterministically at construction time."""
    if num_components <= 0 or significant_height_m <= 0.0:
        return ()

    omega_p = 2.0 * math.pi / peak_period_s
    omega_min = 0.5 * omega_p
    omega_max = 3.0 * omega_p
    d_omega = (omega_max - omega_min) / float(num_components)

    components: list[WaveComponent] = []
    for i in range(num_components):
        omega = omega_min + (i + 0.5) * d_omega
        sigma = 0.07 if omega <= omega_p else 0.09
        r = math.exp(-((omega - omega_p) ** 2) / (2.0 * (sigma**2) * (omega_p**2)))
        gamma = 3.3
        gamma_factor = gamma**r
        s_pm = (
            (5.0 / 16.0)
            * (significant_height_m**2)
            * (omega_p**4)
            * (omega**-5)
            * math.exp(-1.25 * ((omega_p / omega) ** 4))
        )
        s_jonswap = s_pm * gamma_factor * 0.65
        amp = math.sqrt(max(0.0, 2.0 * s_jonswap * d_omega))

        phase = prf_uniform(field_seed, i, "wave_phase") * 2.0 * math.pi
        if directional_spread_rad > 0.0 and num_components > 1:
            spread_offset = (prf_uniform(field_seed, i, "wave_direction") - 0.5) * 2.0 * directional_spread_rad
        else:
            spread_offset = 0.0
        direction = (direction_to_rad + spread_offset) % (2.0 * math.pi)

        components.append(
            WaveComponent(
                amplitude_m=amp,
                omega_radps=omega,
                phase_rad=phase,
                direction_to_rad=direction,
            )
        )
    return tuple(components)


@runtime_checkable
class EnvironmentField(Protocol):
    """Abstract pure environment field interface."""

    @property
    def dt_s(self) -> float:
        """Return simulation tick step size in seconds."""
        ...

    def sample_at(
        self,
        tick: int,
        stage_offset_s: float = 0.0,
        position_ne: tuple[float, float] | FloatArray = (0.0, 0.0),
    ) -> EnvironmentTruth:
        """Pure query returning immutable EnvironmentTruth at (tick*dt_s + stage_offset_s, position_ne)."""
        ...

    def sample_observation(
        self,
        tick: int,
        stage_offset_s: float = 0.0,
        position_ne: tuple[float, float] | FloatArray = (0.0, 0.0),
    ) -> EnvironmentObservation:
        """Return immutable EnvironmentObservation at (tick*dt_s + stage_offset_s, position_ne)."""
        ...


class AnalyticEnvironmentField:
    """Immutable, deterministic analytic environment field driven by keyed PRF."""

    def __init__(
        self,
        dt_s: float,
        field_seed: int,
        wind_velocity_ne: tuple[float, float] = (0.0, 0.0),
        wind_reference_height_m: float = 10.0,
        wind_perturbation_std: tuple[float, float] = (0.0, 0.0),
        current_velocity_ne: tuple[float, float] = (0.0, 0.0),
        current_reference: CurrentReference | str = CurrentReference.SURFACE,
        current_perturbation_std: tuple[float, float] = (0.0, 0.0),
        wave_significant_height_m: float = 0.0,
        wave_peak_period_s: float = 8.0,
        wave_direction_to_rad: float = 0.0,
        wave_num_components: int = 0,
        wave_directional_spread_rad: float = 0.0,
        available: bool = True,
        components: Sequence[WaveComponent] = (),
    ) -> None:
        if not math.isfinite(dt_s) or dt_s <= 0.0:
            raise ValueError("dt_s must be positive and finite")
        self._dt_s = float(dt_s)
        self._field_seed = int(field_seed)

        self._wind_base_ne = (
            _finite_scalar("wind_velocity_ne[0]", wind_velocity_ne[0]),
            _finite_scalar("wind_velocity_ne[1]", wind_velocity_ne[1]),
        )
        self._wind_ref_h = _finite_scalar("wind_reference_height_m", wind_reference_height_m)
        self._wind_pert_std = (
            _finite_scalar("wind_perturbation_std[0]", wind_perturbation_std[0]),
            _finite_scalar("wind_perturbation_std[1]", wind_perturbation_std[1]),
        )

        self._current_base_ne = (
            _finite_scalar("current_velocity_ne[0]", current_velocity_ne[0]),
            _finite_scalar("current_velocity_ne[1]", current_velocity_ne[1]),
        )
        self._current_ref = CurrentReference(current_reference)
        self._current_pert_std = (
            _finite_scalar("current_perturbation_std[0]", current_perturbation_std[0]),
            _finite_scalar("current_perturbation_std[1]", current_perturbation_std[1]),
        )

        self._wave_hs = _finite_scalar("wave_significant_height_m", wave_significant_height_m)
        self._wave_tp = _finite_scalar("wave_peak_period_s", wave_peak_period_s)
        self._wave_dir = _finite_scalar("wave_direction_to_rad", wave_direction_to_rad) % (2.0 * math.pi)
        self._wave_spread = _finite_scalar("wave_directional_spread_rad", wave_directional_spread_rad)
        self._available = bool(available)

        if components:
            self._wave_components = tuple(components)
        else:
            self._wave_components = _generate_wave_components(
                self._wave_hs,
                self._wave_tp,
                self._wave_dir,
                int(wave_num_components),
                self._wave_spread,
                self._field_seed,
            )

    @classmethod
    def from_params(
        cls,
        params: Mapping[str, Any],
        dt_s: float,
        episode_seed: int,
    ) -> AnalyticEnvironmentField:
        """Construct deterministic field from frozen parameter mapping and master seed."""
        field_seed = derive_prf_seed(episode_seed, "environment_field")
        wind_vel = tuple(params.get("wind_velocity_ne", (0.0, 0.0)))
        wind_pert = tuple(params.get("wind_perturbation_std", (0.0, 0.0)))
        current_vel = tuple(params.get("current_velocity_ne", (0.0, 0.0)))
        current_pert = tuple(params.get("current_perturbation_std", (0.0, 0.0)))

        return cls(
            dt_s=dt_s,
            field_seed=field_seed,
            wind_velocity_ne=(float(wind_vel[0]), float(wind_vel[1])),
            wind_reference_height_m=float(params.get("wind_reference_height_m", 10.0)),
            wind_perturbation_std=(float(wind_pert[0]), float(wind_pert[1])),
            current_velocity_ne=(float(current_vel[0]), float(current_vel[1])),
            current_reference=params.get("current_reference", CurrentReference.SURFACE),
            current_perturbation_std=(float(current_pert[0]), float(current_pert[1])),
            wave_significant_height_m=float(params.get("wave_significant_height_m", 0.0)),
            wave_peak_period_s=float(params.get("wave_peak_period_s", 8.0)),
            wave_direction_to_rad=float(params.get("wave_direction_to_rad", 0.0)),
            wave_num_components=int(params.get("wave_num_components", 0)),
            wave_directional_spread_rad=float(params.get("wave_directional_spread_rad", 0.0)),
            available=bool(params.get("available", True)),
        )

    @property
    def dt_s(self) -> float:
        """Return simulation tick step size in seconds."""
        return self._dt_s

    @property
    def field_seed(self) -> int:
        """Return derived field seed."""
        return self._field_seed

    @property
    def available(self) -> bool:
        """Return availability flag."""
        return self._available

    def sample_at(
        self,
        tick: int,
        stage_offset_s: float = 0.0,
        position_ne: tuple[float, float] | FloatArray = (0.0, 0.0),  # noqa: ARG002
    ) -> EnvironmentTruth:
        """Pure query returning immutable EnvironmentTruth at exact simulation time."""
        if tick < 0:
            raise ValueError("tick must be non-negative")
        if not (0.0 <= stage_offset_s < self._dt_s):
            raise ValueError(f"stage_offset_s must be in [0, {self._dt_s}), got {stage_offset_s}")

        time_s = tick * self._dt_s + stage_offset_s

        # Stateless PRF perturbations per tick
        wind_n_pert = (
            prf_gaussian(self._field_seed, tick, "wind_n") * self._wind_pert_std[0] if self._wind_pert_std[0] > 0.0 else 0.0
        )
        wind_e_pert = (
            prf_gaussian(self._field_seed, tick, "wind_e") * self._wind_pert_std[1] if self._wind_pert_std[1] > 0.0 else 0.0
        )
        wind_sample = WindSample(
            velocity_ne=(self._wind_base_ne[0] + wind_n_pert, self._wind_base_ne[1] + wind_e_pert),
            reference_height_m=self._wind_ref_h,
        )

        curr_n_pert = (
            prf_gaussian(self._field_seed, tick, "curr_n") * self._current_pert_std[0]
            if self._current_pert_std[0] > 0.0
            else 0.0
        )
        curr_e_pert = (
            prf_gaussian(self._field_seed, tick, "curr_e") * self._current_pert_std[1]
            if self._current_pert_std[1] > 0.0
            else 0.0
        )
        current_sample = CurrentSample(
            velocity_ne=(self._current_base_ne[0] + curr_n_pert, self._current_base_ne[1] + curr_e_pert),
            reference=self._current_ref,
        )

        wave_sample = WaveFieldSample(
            significant_height_m=self._wave_hs,
            peak_period_s=self._wave_tp,
            direction_to_rad=self._wave_dir,
            components=self._wave_components,
        )

        drift_sample = MeanDriftSourceSample(
            components=self._wave_components,
            directional_spread_rad=self._wave_spread,
        )

        return EnvironmentTruth(
            wind=wind_sample,
            current=current_sample,
            wave=wave_sample,
            mean_drift=drift_sample,
            time_s=time_s,
            tick=tick,
            stage_offset_s=stage_offset_s,
        )

    def sample_observation(
        self,
        tick: int,
        stage_offset_s: float = 0.0,
        position_ne: tuple[float, float] | FloatArray = (0.0, 0.0),
    ) -> EnvironmentObservation:
        """Return immutable EnvironmentObservation at exact simulation time."""
        if not self._available:
            time_s = tick * self._dt_s + stage_offset_s
            return EnvironmentObservation.unavailable(source="ANALYTIC_FIELD", tick=tick, time_s=time_s)
        truth = self.sample_at(tick, stage_offset_s, position_ne)
        return EnvironmentObservation.from_truth(truth, source="ANALYTIC_FIELD", quality=1.0)
