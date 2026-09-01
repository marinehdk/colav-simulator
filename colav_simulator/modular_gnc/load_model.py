"""Vessel environmental loads, asset validation, and current de-duplication (TS-01..07, VR-09, VR-10)."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np

from colav_simulator.modular_gnc.contracts import (
    ApplicabilityDomain,
    AssetIntegrityError,
    AssetMetadata,
    AssetMissingError,
    AssetTrustLevel,
    CurrentSample,
    CurrentStrategy,
    EnvironmentalLoads,
    EnvironmentTruth,
    FloatArray,
    MeanDriftModel,
    MeanDriftSourceSample,
    NavigationState,
    OutOfDomainError,
    PlantState,
    VesselLoad,
    WaveComponentArrays,
    WaveFieldSample,
    WaveLoadMode,
    WindSample,
    _finite_scalar,
)


def _normalize_degrees(angle_deg: float) -> float:
    """Normalize finite angle to [0.0, 360.0)."""
    if isinstance(angle_deg, bool) or not isinstance(angle_deg, (int, float)):
        raise TypeError(f"angle_deg must be a float, got {type(angle_deg).__name__}")
    if not math.isfinite(angle_deg):
        raise ValueError(f"angle_deg must be finite, got {angle_deg}")
    val = float(angle_deg) % 360.0
    if val < 0.0:
        val += 360.0
    return float(val)


def world_ne_to_body_velocity(velocity_ne: tuple[float, float], heading_rad: float) -> tuple[float, float]:
    """Convert world North-East velocity vector to body-frame (forward, starboard) (TS-01, TS-03, TS-07).

    Args:
        velocity_ne: (vn, ve) in m/s world frame.
        heading_rad: Vessel heading in radians (0=North, clockwise/right-positive per TS-04).

    Returns:
        (vx_body, vy_body) in m/s body frame (forward, starboard).
    """
    vn = _finite_scalar("velocity_ne[0]", velocity_ne[0])
    ve = _finite_scalar("velocity_ne[1]", velocity_ne[1])
    psi = _finite_scalar("heading_rad", heading_rad)

    cos_psi = math.cos(psi)
    sin_psi = math.sin(psi)

    vx_b = vn * cos_psi + ve * sin_psi
    vy_b = -vn * sin_psi + ve * cos_psi
    return float(vx_b), float(vy_b)


@dataclass(frozen=True)
class WindCoeffEntry:
    """Single wind coefficient entry for a relative wind angle."""

    angle_deg: float
    cx: float
    cy: float
    cn: float

    def __post_init__(self) -> None:
        """Validate finite coefficients."""
        object.__setattr__(self, "angle_deg", _normalize_degrees(self.angle_deg))
        object.__setattr__(self, "cx", _finite_scalar("cx", self.cx))
        object.__setattr__(self, "cy", _finite_scalar("cy", self.cy))
        object.__setattr__(self, "cn", _finite_scalar("cn", self.cn))


@dataclass(frozen=True)
class WindCoeffTableAsset:
    """Immutable wind coefficient table asset with provenance and integrity verification (TS-23, TS-27)."""

    metadata: AssetMetadata
    table: tuple[WindCoeffEntry, ...]

    def __post_init__(self) -> None:
        """Validate non-empty table, strictly increasing angles without duplicates, and freeze."""
        if not self.table:
            raise ValueError("Wind coefficient table cannot be empty")
        for i, entry in enumerate(self.table):
            if not isinstance(entry, WindCoeffEntry):
                raise TypeError(f"table[{i}] must be WindCoeffEntry, got {type(entry).__name__}")
        for i in range(len(self.table) - 1):
            if self.table[i + 1].angle_deg <= self.table[i].angle_deg:
                raise ValueError(
                    f"Wind table angles must be strictly increasing; "
                    f"table[{i}].angle_deg ({self.table[i].angle_deg}) >= "
                    f"table[{i + 1}].angle_deg ({self.table[i + 1].angle_deg})"
                )
        object.__setattr__(self, "table", tuple(self.table))

    def verify_integrity(self) -> bool:
        """Verify table content SHA-256 against metadata hash."""
        cached = getattr(self, "_integrity_verified", None)
        if cached is not None:
            return cached
        raw_rows = [(entry.angle_deg, entry.cx, entry.cy, entry.cn) for entry in self.table]
        payload = json.dumps(raw_rows, separators=(",", ":")).encode("utf-8")
        calc_sha = hashlib.sha256(payload).hexdigest()
        valid = calc_sha == self.metadata.sha256
        object.__setattr__(self, "_integrity_verified", valid)
        return valid

    def interpolate(self, angle_deg: float) -> tuple[float, float, float]:
        """Linearly interpolate (cx, cy, cn) at relative angle [0, 360)."""
        angle = _normalize_degrees(angle_deg)
        n = len(self.table)
        if n == 1:
            return self.table[0].cx, self.table[0].cy, self.table[0].cn

        last = self.table[-1]
        first = self.table[0]

        if angle >= last.angle_deg:
            t = (angle - last.angle_deg) / (360.0 - last.angle_deg)
            return (
                last.cx + t * (first.cx - last.cx),
                last.cy + t * (first.cy - last.cy),
                last.cn + t * (first.cn - last.cn),
            )

        for i in range(n - 1):
            if self.table[i].angle_deg <= angle < self.table[i + 1].angle_deg:
                span = self.table[i + 1].angle_deg - self.table[i].angle_deg
                t = (angle - self.table[i].angle_deg) / span
                return (
                    self.table[i].cx + t * (self.table[i + 1].cx - self.table[i].cx),
                    self.table[i].cy + t * (self.table[i + 1].cy - self.table[i].cy),
                    self.table[i].cn + t * (self.table[i + 1].cn - self.table[i].cn),
                )
        return first.cx, first.cy, first.cn


@dataclass(frozen=True)
class CurrentCoeffEntry:
    """Single current coefficient entry for a relative current angle."""

    heading_deg: float
    ccx: float
    ccy: float
    cmz: float
    cmx: float = 0.0

    def __post_init__(self) -> None:
        """Validate finite coefficients."""
        object.__setattr__(self, "heading_deg", _normalize_degrees(self.heading_deg))
        object.__setattr__(self, "ccx", _finite_scalar("ccx", self.ccx))
        object.__setattr__(self, "ccy", _finite_scalar("ccy", self.ccy))
        object.__setattr__(self, "cmz", _finite_scalar("cmz", self.cmz))
        object.__setattr__(self, "cmx", _finite_scalar("cmx", self.cmx))


@dataclass(frozen=True)
class CurrentCoeffTableAsset:
    """Immutable tabular current load coefficient asset with verification (TS-23, TS-27)."""

    metadata: AssetMetadata
    table: tuple[CurrentCoeffEntry, ...]

    def __post_init__(self) -> None:
        """Validate non-empty table, strictly increasing headings without duplicates, and freeze."""
        if not self.table:
            raise ValueError("Current coefficient table cannot be empty")
        for i, entry in enumerate(self.table):
            if not isinstance(entry, CurrentCoeffEntry):
                raise TypeError(f"table[{i}] must be CurrentCoeffEntry, got {type(entry).__name__}")
        for i in range(len(self.table) - 1):
            if self.table[i + 1].heading_deg <= self.table[i].heading_deg:
                raise ValueError(
                    f"Current table headings must be strictly increasing; "
                    f"table[{i}].heading_deg ({self.table[i].heading_deg}) >= "
                    f"table[{i + 1}].heading_deg ({self.table[i + 1].heading_deg})"
                )
        object.__setattr__(self, "table", tuple(self.table))

    def verify_integrity(self) -> bool:
        """Verify table content SHA-256 against metadata hash."""
        cached = getattr(self, "_integrity_verified", None)
        if cached is not None:
            return cached
        raw_rows = [(entry.heading_deg, entry.ccx, entry.ccy, entry.cmz, entry.cmx) for entry in self.table]
        payload = json.dumps(raw_rows, separators=(",", ":")).encode("utf-8")
        calc_sha = hashlib.sha256(payload).hexdigest()
        valid = calc_sha == self.metadata.sha256
        object.__setattr__(self, "_integrity_verified", valid)
        return valid

    def interpolate(self, angle_deg: float) -> tuple[float, float, float, float]:
        """Linearly interpolate (ccx, ccy, cmz, cmx) at relative angle [0, 360)."""
        angle = _normalize_degrees(angle_deg)
        n = len(self.table)
        if n == 1:
            return self.table[0].ccx, self.table[0].ccy, self.table[0].cmz, self.table[0].cmx

        last = self.table[-1]
        first = self.table[0]

        if angle >= last.heading_deg:
            t = (angle - last.heading_deg) / (360.0 - last.heading_deg)
            return (
                last.ccx + t * (first.ccx - last.ccx),
                last.ccy + t * (first.ccy - last.ccy),
                last.cmz + t * (first.cmz - last.cmz),
                last.cmx + t * (first.cmx - last.cmx),
            )

        for i in range(n - 1):
            if self.table[i].heading_deg <= angle < self.table[i + 1].heading_deg:
                span = self.table[i + 1].heading_deg - self.table[i].heading_deg
                t = (angle - self.table[i].heading_deg) / span
                return (
                    self.table[i].ccx + t * (self.table[i + 1].ccx - self.table[i].ccx),
                    self.table[i].ccy + t * (self.table[i + 1].ccy - self.table[i].ccy),
                    self.table[i].cmz + t * (self.table[i + 1].cmz - self.table[i].cmz),
                    self.table[i].cmx + t * (self.table[i + 1].cmx - self.table[i].cmx),
                )
        return first.ccx, first.ccy, first.cmz, first.cmx


@dataclass(frozen=True)
class InferredCurrentAsset:
    """Inferred crossflow current coefficient model asset (Fossen-style) (TS-23, VR-10)."""

    metadata: AssetMetadata

    def __post_init__(self) -> None:
        """Validate that inferred asset cannot be marked validated (TS-23, ALT-25)."""
        if self.metadata.trust_level == AssetTrustLevel.VALIDATED_FOR_VESSEL:
            raise ValueError("Inferred current asset cannot have VALIDATED_FOR_VESSEL trust level")

    def verify_integrity(self) -> bool:
        """Verify metadata consistency."""
        cached = getattr(self, "_integrity_verified", None)
        if cached is not None:
            return cached
        payload = b"inferred_crossflow_v1"
        valid = self.metadata.sha256 == hashlib.sha256(payload).hexdigest()
        object.__setattr__(self, "_integrity_verified", valid)
        return valid

    def evaluate(self, gamma_rad: float) -> tuple[float, float, float, float]:
        """Evaluate (ccx, ccy, cmz, cmx) analytically from relative flow angle."""
        gamma = _finite_scalar("gamma_rad", gamma_rad)
        c = math.cos(gamma)
        s = math.sin(gamma)
        ccx = 0.15 * c
        ccy = 0.70 * s * abs(s)
        cmz = 0.010 * s
        cmx = 0.0
        return float(ccx), float(ccy), float(cmz), float(cmx)


@dataclass(frozen=True)
class InferredWaveResponseAsset:
    """Inferred Froude-Krylov and analytical RAO wave response model asset (TS-23, VR-10)."""

    metadata: AssetMetadata
    fk_scale_factor: float = 0.1
    rao_cutoff_surge: float = 0.25
    rao_cutoff_sway: float = 0.30
    rao_cutoff_yaw: float = 0.20
    rao_scale_max: float = 3.0
    rao_scale_max_roll: float = 5.0
    rao_damping_heave: float = 0.10
    rao_damping_roll: float = 0.15
    rao_surge_scale: float = 1.0
    rao_sway_scale: float = 1.0
    rao_roll_scale: float = 1.0
    rao_yaw_scale: float = 1.0

    def __post_init__(self) -> None:
        """Validate parameters and ensure inferred asset cannot be marked validated."""
        if self.metadata.trust_level == AssetTrustLevel.VALIDATED_FOR_VESSEL:
            raise ValueError("Inferred wave response asset cannot have VALIDATED_FOR_VESSEL trust level")
        for f in (
            "fk_scale_factor",
            "rao_cutoff_surge",
            "rao_cutoff_sway",
            "rao_cutoff_yaw",
            "rao_scale_max",
            "rao_scale_max_roll",
            "rao_damping_heave",
            "rao_damping_roll",
            "rao_surge_scale",
            "rao_sway_scale",
            "rao_roll_scale",
            "rao_yaw_scale",
        ):
            val = _finite_scalar(f, getattr(self, f))
            if val < 0.0:
                raise ValueError(f"{f} must be non-negative")
            object.__setattr__(self, f, val)

    def verify_integrity(self) -> bool:
        """Verify asset integrity hash against metadata."""
        cached = getattr(self, "_integrity_verified", None)
        if cached is not None:
            return cached
        d = {
            "asset_id": self.metadata.asset_id,
            "fk_scale_factor": self.fk_scale_factor,
            "rao_cutoff_surge": self.rao_cutoff_surge,
            "rao_cutoff_sway": self.rao_cutoff_sway,
            "rao_cutoff_yaw": self.rao_cutoff_yaw,
            "rao_scale_max": self.rao_scale_max,
            "rao_scale_max_roll": self.rao_scale_max_roll,
            "rao_damping_heave": self.rao_damping_heave,
            "rao_damping_roll": self.rao_damping_roll,
            "rao_surge_scale": self.rao_surge_scale,
            "rao_sway_scale": self.rao_sway_scale,
            "rao_roll_scale": self.rao_roll_scale,
            "rao_yaw_scale": self.rao_yaw_scale,
        }
        payload = json.dumps(d, sort_keys=True, separators=(",", ":")).encode("utf-8")
        valid = self.metadata.sha256 == hashlib.sha256(payload).hexdigest()
        object.__setattr__(self, "_integrity_verified", valid)
        return valid


@dataclass(frozen=True)
class WaveRaoEntry:
    """Single tabular RAO entry for a frequency and relative heading."""

    omega_radps: float
    heading_deg: float
    surge_amp_n_per_m: float
    surge_phase_rad: float
    sway_amp_n_per_m: float
    sway_phase_rad: float
    roll_amp_nm_per_m: float
    roll_phase_rad: float
    yaw_amp_nm_per_m: float
    yaw_phase_rad: float

    def __post_init__(self) -> None:
        """Validate finite values."""
        omega = _finite_scalar("omega_radps", self.omega_radps)
        if omega <= 0.0:
            raise ValueError("omega_radps must be positive")
        object.__setattr__(self, "omega_radps", omega)
        object.__setattr__(self, "heading_deg", _normalize_degrees(self.heading_deg))
        for field_name in (
            "surge_amp_n_per_m",
            "surge_phase_rad",
            "sway_amp_n_per_m",
            "sway_phase_rad",
            "roll_amp_nm_per_m",
            "roll_phase_rad",
            "yaw_amp_nm_per_m",
            "yaw_phase_rad",
        ):
            object.__setattr__(self, field_name, _finite_scalar(field_name, getattr(self, field_name)))


@dataclass(frozen=True)
class WaveRaoTableAsset:
    """Immutable tabular RAO asset with verification (TS-23, TS-27)."""

    metadata: AssetMetadata
    table: tuple[WaveRaoEntry, ...]

    def __post_init__(self) -> None:
        """Validate non-empty table and freeze."""
        if not self.table:
            raise ValueError("Wave RAO table cannot be empty")
        for i, entry in enumerate(self.table):
            if not isinstance(entry, WaveRaoEntry):
                raise TypeError(f"table[{i}] must be WaveRaoEntry, got {type(entry).__name__}")
        object.__setattr__(self, "table", tuple(self.table))

    def verify_integrity(self) -> bool:
        """Verify table content SHA-256 against metadata hash."""
        cached = getattr(self, "_integrity_verified", None)
        if cached is not None:
            return cached
        raw_rows = [
            (
                entry.omega_radps,
                entry.heading_deg,
                entry.surge_amp_n_per_m,
                entry.surge_phase_rad,
                entry.sway_amp_n_per_m,
                entry.sway_phase_rad,
                entry.roll_amp_nm_per_m,
                entry.roll_phase_rad,
                entry.yaw_amp_nm_per_m,
                entry.yaw_phase_rad,
            )
            for entry in self.table
        ]
        payload = json.dumps(raw_rows, separators=(",", ":")).encode("utf-8")
        valid = hashlib.sha256(payload).hexdigest() == self.metadata.sha256
        object.__setattr__(self, "_integrity_verified", valid)
        return valid

    def interpolate(
        self, omega_radps: float, heading_deg: float
    ) -> tuple[float, float, float, float, float, float, float, float]:
        """Interpolate RAO amplitudes and phases at (omega, heading_deg)."""
        norm_heading = _normalize_degrees(heading_deg)
        if len(self.table) == 1:
            e = self.table[0]
            return (
                e.surge_amp_n_per_m,
                e.surge_phase_rad,
                e.sway_amp_n_per_m,
                e.sway_phase_rad,
                e.roll_amp_nm_per_m,
                e.roll_phase_rad,
                e.yaw_amp_nm_per_m,
                e.yaw_phase_rad,
            )
        for e in self.table:
            if math.isclose(e.omega_radps, omega_radps, abs_tol=1e-6) and math.isclose(
                e.heading_deg, norm_heading, abs_tol=1e-4
            ):
                return (
                    e.surge_amp_n_per_m,
                    e.surge_phase_rad,
                    e.sway_amp_n_per_m,
                    e.sway_phase_rad,
                    e.roll_amp_nm_per_m,
                    e.roll_phase_rad,
                    e.yaw_amp_nm_per_m,
                    e.yaw_phase_rad,
                )
        dists = []
        for e in self.table:
            d_head = min(abs(e.heading_deg - norm_heading), 360.0 - abs(e.heading_deg - norm_heading)) / 180.0
            d_om = abs(e.omega_radps - omega_radps) / max(omega_radps, 0.1)
            dist = math.hypot(d_om, d_head)
            dists.append((dist, e))
        dists.sort(key=lambda x: x[0])
        if dists[0][0] < 1e-9:
            e = dists[0][1]
            return (
                e.surge_amp_n_per_m,
                e.surge_phase_rad,
                e.sway_amp_n_per_m,
                e.sway_phase_rad,
                e.roll_amp_nm_per_m,
                e.roll_phase_rad,
                e.yaw_amp_nm_per_m,
                e.yaw_phase_rad,
            )
        top_k = dists[: min(4, len(dists))]
        weights = [1.0 / (d[0] ** 2) for d in top_k]
        tot_w = sum(weights)
        norm_w = [w / tot_w for w in weights]
        res = [0.0] * 8
        for w, (_, e) in zip(norm_w, top_k, strict=True):
            vals = (
                e.surge_amp_n_per_m,
                e.surge_phase_rad,
                e.sway_amp_n_per_m,
                e.sway_phase_rad,
                e.roll_amp_nm_per_m,
                e.roll_phase_rad,
                e.yaw_amp_nm_per_m,
                e.yaw_phase_rad,
            )
            for idx, val in enumerate(vals):
                res[idx] += w * val
        return (res[0], res[1], res[2], res[3], res[4], res[5], res[6], res[7])


@dataclass(frozen=True)
class InferredWaveDriftAsset:
    """Inferred second-order wave mean-drift load asset using diagonal A_i^2 reflection (TS-23, VR-10)."""

    metadata: AssetMetadata
    inferred_surge_scale: float = 0.75
    inferred_sway_scale: float = 0.35
    inferred_yaw_lever_scale: float = 0.12
    inferred_roll_lever_scale: float = 0.45
    max_force_n: float | None = 2.0e6
    max_moment_nm: float | None = 5.0e7
    model_type: MeanDriftModel = MeanDriftModel.DIAGONAL_AI2

    def __post_init__(self) -> None:
        """Validate parameters and ensure inferred asset cannot be marked validated."""
        if self.metadata.trust_level == AssetTrustLevel.VALIDATED_FOR_VESSEL:
            raise ValueError("Inferred wave drift asset cannot have VALIDATED_FOR_VESSEL trust level")
        for f in (
            "inferred_surge_scale",
            "inferred_sway_scale",
            "inferred_yaw_lever_scale",
            "inferred_roll_lever_scale",
        ):
            val = _finite_scalar(f, getattr(self, f))
            if val < 0.0:
                raise ValueError(f"{f} must be non-negative")
            object.__setattr__(self, f, val)
        if self.max_force_n is not None:
            object.__setattr__(self, "max_force_n", _finite_scalar("max_force_n", self.max_force_n))
        if self.max_moment_nm is not None:
            object.__setattr__(self, "max_moment_nm", _finite_scalar("max_moment_nm", self.max_moment_nm))
        object.__setattr__(self, "model_type", MeanDriftModel(self.model_type))

    def verify_integrity(self) -> bool:
        """Verify asset integrity hash against metadata."""
        cached = getattr(self, "_integrity_verified", None)
        if cached is not None:
            return cached
        d = {
            "asset_id": self.metadata.asset_id,
            "inferred_roll_lever_scale": self.inferred_roll_lever_scale,
            "inferred_surge_scale": self.inferred_surge_scale,
            "inferred_sway_scale": self.inferred_sway_scale,
            "inferred_yaw_lever_scale": self.inferred_yaw_lever_scale,
            "max_force_n": self.max_force_n,
            "max_moment_nm": self.max_moment_nm,
        }
        payload = json.dumps(d, sort_keys=True, separators=(",", ":")).encode("utf-8")
        valid = self.metadata.sha256 == hashlib.sha256(payload).hexdigest()
        object.__setattr__(self, "_integrity_verified", valid)
        return valid


@dataclass(frozen=True)
class WaveDriftEntry:
    """Single tabular second-order drift coefficient entry."""

    omega_radps: float
    heading_deg: float
    c_dx_n_per_m2: float
    c_dy_n_per_m2: float
    c_dn_nm_per_m2: float
    c_dk_nm_per_m2: float = 0.0

    def __post_init__(self) -> None:
        """Validate finite coefficients."""
        omega = _finite_scalar("omega_radps", self.omega_radps)
        if omega <= 0.0:
            raise ValueError("omega_radps must be positive")
        object.__setattr__(self, "omega_radps", omega)
        object.__setattr__(self, "heading_deg", _normalize_degrees(self.heading_deg))
        object.__setattr__(self, "c_dx_n_per_m2", _finite_scalar("c_dx_n_per_m2", self.c_dx_n_per_m2))
        object.__setattr__(self, "c_dy_n_per_m2", _finite_scalar("c_dy_n_per_m2", self.c_dy_n_per_m2))
        object.__setattr__(self, "c_dn_nm_per_m2", _finite_scalar("c_dn_nm_per_m2", self.c_dn_nm_per_m2))
        object.__setattr__(self, "c_dk_nm_per_m2", _finite_scalar("c_dk_nm_per_m2", self.c_dk_nm_per_m2))


@dataclass(frozen=True)
class WaveDriftTableAsset:
    """Immutable tabular mean drift coefficient asset (TS-23, TS-27)."""

    metadata: AssetMetadata
    table: tuple[WaveDriftEntry, ...]
    model_type: MeanDriftModel = MeanDriftModel.DIAGONAL_AI2

    def __post_init__(self) -> None:
        """Validate non-empty table and freeze."""
        if not self.table:
            raise ValueError("Wave drift table cannot be empty")
        for i, entry in enumerate(self.table):
            if not isinstance(entry, WaveDriftEntry):
                raise TypeError(f"table[{i}] must be WaveDriftEntry, got {type(entry).__name__}")
        object.__setattr__(self, "table", tuple(self.table))
        object.__setattr__(self, "model_type", MeanDriftModel(self.model_type))

    def verify_integrity(self) -> bool:
        """Verify table content SHA-256 against metadata hash."""
        cached = getattr(self, "_integrity_verified", None)
        if cached is not None:
            return cached
        raw_rows = [
            (
                entry.omega_radps,
                entry.heading_deg,
                entry.c_dx_n_per_m2,
                entry.c_dy_n_per_m2,
                entry.c_dn_nm_per_m2,
                entry.c_dk_nm_per_m2,
            )
            for entry in self.table
        ]
        payload = json.dumps(raw_rows, separators=(",", ":")).encode("utf-8")
        valid = hashlib.sha256(payload).hexdigest() == self.metadata.sha256
        object.__setattr__(self, "_integrity_verified", valid)
        return valid

    def interpolate(self, omega_radps: float, heading_deg: float) -> tuple[float, float, float, float]:
        """Interpolate drift coefficients (cdx, cdy, cdn, cdk) at (omega, heading_deg)."""
        norm_heading = _normalize_degrees(heading_deg)
        if len(self.table) == 1:
            e = self.table[0]
            return e.c_dx_n_per_m2, e.c_dy_n_per_m2, e.c_dn_nm_per_m2, e.c_dk_nm_per_m2
        for e in self.table:
            if math.isclose(e.omega_radps, omega_radps, abs_tol=1e-6) and math.isclose(
                e.heading_deg, norm_heading, abs_tol=1e-4
            ):
                return e.c_dx_n_per_m2, e.c_dy_n_per_m2, e.c_dn_nm_per_m2, e.c_dk_nm_per_m2
        dists = []
        for e in self.table:
            d_head = min(abs(e.heading_deg - norm_heading), 360.0 - abs(e.heading_deg - norm_heading)) / 180.0
            d_om = abs(e.omega_radps - omega_radps) / max(omega_radps, 0.1)
            dist = math.hypot(d_om, d_head)
            dists.append((dist, e))
        dists.sort(key=lambda x: x[0])
        if dists[0][0] < 1e-9:
            e = dists[0][1]
            return e.c_dx_n_per_m2, e.c_dy_n_per_m2, e.c_dn_nm_per_m2, e.c_dk_nm_per_m2
        top_k = dists[: min(4, len(dists))]
        weights = [1.0 / (d[0] ** 2) for d in top_k]
        tot_w = sum(weights)
        norm_w = [w / tot_w for w in weights]
        res = [0.0] * 4
        for w, (_, e) in zip(norm_w, top_k, strict=True):
            vals = (e.c_dx_n_per_m2, e.c_dy_n_per_m2, e.c_dn_nm_per_m2, e.c_dk_nm_per_m2)
            for idx, val in enumerate(vals):
                res[idx] += w * val
        return (res[0], res[1], res[2], res[3])


@dataclass(frozen=True)
class VesselEnvironmentalParameters:
    """Vessel hydrodynamic and aerodynamic geometry parameters (SI units)."""

    length_between_perpendiculars_m: float
    beam_m: float
    draft_m: float
    wind_frontal_area_m2: float
    wind_lateral_area_m2: float
    wind_z_center_m: float = 0.0
    wind_roll_moment_arm_m: float | None = None
    air_density_kg_m3: float = 1.225
    water_depth_m: float = 100.0
    kg_m: float = 0.0
    current_roll_moment_arm_m: float | None = None
    water_density_kg_m3: float = 1025.0
    displacement_ton: float = 50000.0
    gm_t_m: float = 1.5
    bow_angle_rad: float = 0.6
    c_wl_aft: float = 0.95
    gravity_mps2: float = 9.81
    wave_roll_moment_arm_m: float | None = None

    def __post_init__(self) -> None:
        """Validate positive physical parameters."""
        positive_fields = (
            "length_between_perpendiculars_m",
            "beam_m",
            "draft_m",
            "wind_frontal_area_m2",
            "wind_lateral_area_m2",
            "air_density_kg_m3",
            "water_density_kg_m3",
            "water_depth_m",
            "displacement_ton",
            "gm_t_m",
            "c_wl_aft",
            "gravity_mps2",
        )
        for name in positive_fields:
            val = _finite_scalar(name, getattr(self, name))
            if val <= 0.0:
                raise ValueError(f"{name} must be positive")
            object.__setattr__(self, name, val)

        for name in ("wind_z_center_m", "kg_m", "bow_angle_rad"):
            object.__setattr__(self, name, _finite_scalar(name, getattr(self, name)))

        for arm_name in ("wind_roll_moment_arm_m", "current_roll_moment_arm_m", "wave_roll_moment_arm_m"):
            raw_arm = getattr(self, arm_name)
            if raw_arm is not None:
                object.__setattr__(self, arm_name, _finite_scalar(arm_name, raw_arm))


# ---------------------------------------------------------------------------
# Bundled Assets (Verified Content & Hashes)
# ---------------------------------------------------------------------------

_OCIMF_ROWS = (
    (0.0, -0.60, 0.00, 0.000),
    (10.0, -0.58, 0.06, 0.010),
    (20.0, -0.50, 0.18, 0.030),
    (30.0, -0.40, 0.30, 0.040),
    (40.0, -0.28, 0.42, 0.055),
    (50.0, -0.14, 0.54, 0.065),
    (60.0, 0.00, 0.65, 0.070),
    (70.0, 0.10, 0.72, 0.068),
    (80.0, 0.17, 0.77, 0.040),
    (90.0, 0.20, 0.80, 0.000),
    (100.0, 0.17, 0.77, -0.040),
    (110.0, 0.10, 0.72, -0.068),
    (120.0, 0.00, 0.65, -0.070),
    (130.0, -0.14, 0.54, -0.065),
    (140.0, -0.28, 0.42, -0.055),
    (150.0, -0.40, 0.30, -0.040),
    (160.0, -0.50, 0.18, -0.030),
    (170.0, -0.58, 0.06, -0.010),
    (180.0, -0.50, 0.00, 0.000),
    (190.0, -0.42, -0.06, -0.010),
    (200.0, -0.32, -0.18, -0.030),
    (210.0, -0.25, -0.30, -0.040),
    (220.0, -0.14, -0.42, -0.055),
    (230.0, 0.00, -0.54, -0.065),
    (240.0, 0.14, -0.65, -0.070),
    (250.0, 0.22, -0.72, -0.068),
    (260.0, 0.28, -0.77, -0.040),
    (270.0, 0.35, -0.80, 0.000),
    (280.0, 0.28, -0.77, 0.040),
    (290.0, 0.22, -0.72, 0.068),
    (300.0, 0.14, -0.65, 0.070),
    (310.0, 0.00, -0.54, 0.065),
    (320.0, -0.14, -0.42, 0.055),
    (330.0, -0.25, -0.30, 0.040),
    (340.0, -0.32, -0.18, 0.030),
    (350.0, -0.45, -0.06, 0.010),
)

_CURRENT_TABLE_ROWS = (
    (0.0, 0.15, 0.0, 0.0),
    (22.5, 0.14, 0.05, 0.003),
    (45.0, 0.10, 0.10, 0.006),
    (67.5, 0.05, 0.15, 0.008),
    (90.0, 0.0, 0.20, 0.010),
    (112.5, -0.05, 0.15, 0.008),
    (135.0, -0.10, 0.10, 0.006),
    (157.5, -0.14, 0.05, 0.003),
    (180.0, -0.15, 0.0, 0.0),
    (202.5, -0.14, -0.05, -0.003),
    (225.0, -0.10, -0.10, -0.006),
    (247.5, -0.05, -0.15, -0.008),
    (270.0, 0.0, -0.20, -0.010),
    (292.5, 0.05, -0.15, -0.008),
    (315.0, 0.10, -0.10, -0.006),
    (337.5, 0.14, -0.05, -0.003),
)

DEFAULT_OCIMF_WIND_ASSET = WindCoeffTableAsset(
    metadata=AssetMetadata(
        asset_id="wind_ocimf_table_v1",
        asset_type="wind_coeff_table",
        trust_level=AssetTrustLevel.MOCK,
        source_type="mock",
        sha256="384e3dedbca2aa60b98d717439ea41cb8cfbb20321438b078bf370b59fdf5a25",
        license="CC-BY-4.0",
        applicability_domain=ApplicabilityDomain(
            heading_range_deg=(0.0, 360.0),
            speed_range_mps=(0.0, 60.0),
        ),
        provenance={"standard_basis": "OCIMF 1994 / Isherwood blend", "created_by": "modular_gnc"},
        uncertainty={"cx_std": 0.05, "cy_std": 0.05, "cn_std": 0.01},
    ),
    table=tuple(WindCoeffEntry(*row) for row in _OCIMF_ROWS),
)

DEFAULT_TABLE_CURRENT_ASSET = CurrentCoeffTableAsset(
    metadata=AssetMetadata(
        asset_id="current_coeffs_table_v1",
        asset_type="current_coeff_table",
        trust_level=AssetTrustLevel.MOCK,
        source_type="mock",
        sha256="d4cb5edccda7f56fea0b4904a62068422c68b6cde1827a2614a3791ed39aeea9",
        license="MIT",
        applicability_domain=ApplicabilityDomain(
            heading_range_deg=(0.0, 360.0),
            speed_range_mps=(0.0, 5.0),
            draft_range_m=(0.5, 30.0),
        ),
        provenance={"standard_basis": "Fossen-style tabular crossflow drag", "created_by": "modular_gnc"},
        uncertainty={"table_std": 0.05},
    ),
    table=tuple(CurrentCoeffEntry(*row) for row in _CURRENT_TABLE_ROWS),
)

DEFAULT_INFERRED_CURRENT_ASSET = InferredCurrentAsset(
    metadata=AssetMetadata(
        asset_id="current_inferred_v1",
        asset_type="current_inferred_crossflow",
        trust_level=AssetTrustLevel.INFERRED,
        source_type="inferred",
        sha256="fca4c77bda27a37668602b81ca77611a6b66e3ac04f5062ef144c867115e03f0",  # sha256("inferred_crossflow_v1")
        license="MIT",
        applicability_domain=ApplicabilityDomain(
            heading_range_deg=(0.0, 360.0),
            speed_range_mps=(0.0, 5.0),
            draft_range_m=(0.5, 30.0),
        ),
        provenance={"standard_basis": "Fossen relative cross-flow formulation", "created_by": "modular_gnc"},
        uncertainty={"crossflow_cd_std": 0.1},
    )
)

DEFAULT_INFERRED_WAVE_RESPONSE_ASSET = InferredWaveResponseAsset(
    metadata=AssetMetadata(
        asset_id="default_inferred_wave_response_v1",
        asset_type="wave_response_inferred",
        trust_level=AssetTrustLevel.INFERRED,
        source_type="inferred",
        sha256="ded3ba8a98fd4ca190bc433fdf3691b2cacb9693bcc56be114fac7664585c55a",
        license="MIT",
        applicability_domain=ApplicabilityDomain(
            heading_range_deg=(0.0, 360.0),
            speed_range_mps=(0.0, 30.0),
            draft_range_m=(0.5, 30.0),
            custom_bounds={"omega_radps": (0.01, 5.0), "wave_height_m": (0.0, 30.0)},
        ),
        provenance={"standard_basis": "Froude-Krylov + analytical RAO scaffold", "created_by": "modular_gnc"},
        uncertainty={"rao_std": 0.1},
    )
)

DEFAULT_INFERRED_WAVE_DRIFT_ASSET = InferredWaveDriftAsset(
    metadata=AssetMetadata(
        asset_id="default_inferred_diagonal_drift_v1",
        asset_type="wave_drift_inferred",
        trust_level=AssetTrustLevel.INFERRED,
        source_type="inferred",
        sha256="6be6b12ff69b44f32f8d7f3465af8d1c7cb5a6d1d3a2249e05ffccbb97178b68",
        license="MIT",
        applicability_domain=ApplicabilityDomain(
            heading_range_deg=(0.0, 360.0),
            speed_range_mps=(0.0, 30.0),
            draft_range_m=(0.5, 30.0),
            custom_bounds={"omega_radps": (0.01, 5.0), "wave_height_m": (0.0, 30.0)},
        ),
        provenance={"standard_basis": "Diagonal mean-drift reflection scaffold (A_i^2)", "created_by": "modular_gnc"},
        uncertainty={"drift_std": 0.15},
    ),
    model_type=MeanDriftModel.DIAGONAL_AI2,
)

KNOWN_WAVE_FIRST_ORDER_ASSETS: Mapping[str, InferredWaveResponseAsset | WaveRaoTableAsset] = {
    "default_inferred_wave_response_v1": DEFAULT_INFERRED_WAVE_RESPONSE_ASSET,
}

KNOWN_WAVE_MEAN_DRIFT_ASSETS: Mapping[str, InferredWaveDriftAsset | WaveDriftTableAsset] = {
    "default_inferred_diagonal_drift_v1": DEFAULT_INFERRED_WAVE_DRIFT_ASSET,
}


# ---------------------------------------------------------------------------
# Load Calculation Kernels
# ---------------------------------------------------------------------------


class WindLoadModel:
    """Pure calculation of aerodynamic wind loads on vessel hull and superstructure (SI: N, N·m)."""

    @classmethod
    def calculate(
        cls,
        wind: WindSample,
        heading_rad: float,
        surge_mps: float,
        sway_mps: float,
        params: VesselEnvironmentalParameters,
        asset: WindCoeffTableAsset | None = None,
    ) -> VesselLoad:
        """Calculate wind load vector in vessel body frame.

        Args:
            wind: Raw wind field sample in world NE-to frame.
            heading_rad: Vessel heading in radians (0=North, clockwise positive).
            surge_mps: Vessel forward speed u in m/s.
            sway_mps: Vessel starboard speed v in m/s.
            params: Vessel geometry and environmental parameters.
            asset: Wind coefficient asset (must be provided and valid).

        Returns:
            VesselLoad in body frame (surge_n, sway_n, yaw_nm, roll_nm).
        """
        if asset is None:
            raise AssetMissingError("Wind coefficient asset is required for WindLoadModel")
        if not asset.verify_integrity():
            raise AssetIntegrityError(f"Integrity check failed for wind asset: {asset.metadata.asset_id}")

        # World to body wind velocity
        vx_b, vy_b = world_ne_to_body_velocity(wind.velocity_ne, heading_rad)

        # Relative fluid velocity to ship
        rel_u = vx_b - _finite_scalar("surge_mps", surge_mps)
        rel_v = vy_b - _finite_scalar("sway_mps", sway_mps)

        apparent_speed = math.hypot(rel_u, rel_v)
        if apparent_speed < 1e-9:
            return VesselLoad.zero()

        apparent_dir_rad = math.atan2(rel_v, rel_u)
        apparent_dir_deg = _normalize_degrees(math.degrees(apparent_dir_rad))

        # Check domain validity
        if not asset.metadata.applicability_domain.contains(heading_deg=apparent_dir_deg, speed_mps=apparent_speed):
            raise OutOfDomainError(
                f"Apparent wind (dir={apparent_dir_deg:.1f} deg, speed={apparent_speed:.2f} m/s) "
                f"outside applicability domain of asset {asset.metadata.asset_id}"
            )

        cx, cy, cn = asset.interpolate(apparent_dir_deg)

        # Dynamic pressure: q = 0.5 * rho * V^2
        q = 0.5 * params.air_density_kg_m3 * apparent_speed * apparent_speed

        force_x = q * cx * params.wind_frontal_area_m2
        force_y = q * cy * params.wind_lateral_area_m2

        roll_arm = params.wind_roll_moment_arm_m if params.wind_roll_moment_arm_m is not None else params.wind_z_center_m
        torque_x = -force_y * roll_arm
        torque_z = q * cn * params.wind_lateral_area_m2 * params.length_between_perpendiculars_m

        return VesselLoad(
            surge_n=float(force_x),
            sway_n=float(force_y),
            yaw_nm=float(torque_z),
            roll_nm=float(torque_x),
        )


class CurrentLoadModel:
    """Pure calculation of hydrodynamic current loads on vessel hull (SI: N, N·m)."""

    @classmethod
    def calculate(
        cls,
        current: CurrentSample,
        heading_rad: float,
        surge_mps: float,
        sway_mps: float,
        params: VesselEnvironmentalParameters,
        strategy: CurrentStrategy,
        asset: CurrentCoeffTableAsset | InferredCurrentAsset | None = None,
    ) -> VesselLoad:
        """Calculate current load vector in vessel body frame.

        Strategy de-duplication:
        - CURRENT_RELATIVE_DAMPING: current handled via plant damping; load is strictly ZERO.
        - EXTERNAL_CURRENT_LOAD: explicit hydrodynamic load is calculated.
        - NONE: current load is zero.
        """
        strat = CurrentStrategy(strategy)
        if strat in (CurrentStrategy.NONE, CurrentStrategy.CURRENT_RELATIVE_DAMPING):
            return VesselLoad.zero()

        if strat != CurrentStrategy.EXTERNAL_CURRENT_LOAD:
            raise ValueError(f"Unknown current strategy: {strategy}")

        if asset is None:
            raise AssetMissingError("Current asset is required when strategy is EXTERNAL_CURRENT_LOAD")
        if not asset.verify_integrity():
            raise AssetIntegrityError(f"Integrity check failed for current asset: {asset.metadata.asset_id}")

        # World to body current velocity
        cx_b, cy_b = world_ne_to_body_velocity(current.velocity_ne, heading_rad)

        # Relative fluid velocity to ship
        rel_u = cx_b - _finite_scalar("surge_mps", surge_mps)
        rel_v = cy_b - _finite_scalar("sway_mps", sway_mps)

        apparent_speed = math.hypot(rel_u, rel_v)
        if apparent_speed < 1e-9:
            return VesselLoad.zero()

        apparent_dir_rad = math.atan2(rel_v, rel_u)
        apparent_dir_deg = _normalize_degrees(math.degrees(apparent_dir_rad))

        safe_t = min(params.draft_m, params.water_depth_m * 0.95)
        if safe_t <= 0.0:
            return VesselLoad.zero()

        # Check domain validity
        if not asset.metadata.applicability_domain.contains(
            heading_deg=apparent_dir_deg,
            speed_mps=apparent_speed,
            draft_m=safe_t,
        ):
            raise OutOfDomainError(
                f"Apparent current (dir={apparent_dir_deg:.1f} deg, speed={apparent_speed:.2f} m/s, draft={safe_t:.2f} m) "
                f"outside applicability domain of asset {asset.metadata.asset_id}"
            )

        if isinstance(asset, InferredCurrentAsset):
            ccx, ccy, cmz, cmx = asset.evaluate(apparent_dir_rad)
            has_cmx = False
        elif isinstance(asset, CurrentCoeffTableAsset):
            ccx, ccy, cmz, cmx = asset.interpolate(apparent_dir_deg)
            has_cmx = abs(cmx) > 1e-12
        else:
            raise TypeError(f"Unsupported current asset type: {type(asset).__name__}")

        s_long = params.beam_m * safe_t
        s_trans = params.length_between_perpendiculars_m * safe_t
        v2 = apparent_speed * apparent_speed
        half_rho = 0.5 * params.water_density_kg_m3

        force_x = half_rho * ccx * s_long * v2
        force_y = half_rho * ccy * s_trans * v2
        torque_z = half_rho * cmz * s_trans * params.length_between_perpendiculars_m * v2

        if has_cmx:
            torque_x = half_rho * cmx * s_trans * params.length_between_perpendiculars_m * v2
        else:
            auto_arm = params.kg_m - safe_t / 3.0
            z_arm = params.current_roll_moment_arm_m if params.current_roll_moment_arm_m is not None else auto_arm
            torque_x = force_y * z_arm

        return VesselLoad(
            surge_n=float(force_x),
            sway_n=float(force_y),
            yaw_nm=float(torque_z),
            roll_nm=float(torque_x),
        )


def _extract_wave_component_arrays(wave: WaveFieldSample | MeanDriftSourceSample) -> WaveComponentArrays | None:
    """Extract or retrieve cached contiguous immutable float64 component arrays."""
    return wave.component_arrays


def _check_wave_domain_batch(
    asset_id: str,
    domain: ApplicabilityDomain,
    gamma_deg: FloatArray,
    omegas: FloatArray,
    amplitudes: FloatArray,
) -> None:
    """Perform batched applicability domain checks and raise OutOfDomainError on violation."""
    h_min, h_max = domain.heading_range_deg
    heading_mask = (gamma_deg >= h_min) & (gamma_deg <= h_max)
    if not np.all(heading_mask):
        idx = int(np.where(~heading_mask)[0][0])
        raise OutOfDomainError(
            f"Wave component (omega={omegas[idx]:.2f} rad/s, gamma={gamma_deg[idx]:.1f} deg, "
            f"amp={amplitudes[idx]:.2f} m) outside applicability domain of asset {asset_id}"
        )

    if "omega_radps" in domain.custom_bounds:
        om_min, om_max = domain.custom_bounds["omega_radps"]
        om_mask = (omegas >= om_min) & (omegas <= om_max)
        if not np.all(om_mask):
            idx = int(np.where(~om_mask)[0][0])
            raise OutOfDomainError(
                f"Wave component (omega={omegas[idx]:.2f} rad/s, gamma={gamma_deg[idx]:.1f} deg, "
                f"amp={amplitudes[idx]:.2f} m) outside applicability domain of asset {asset_id}"
            )

    if "wave_height_m" in domain.custom_bounds:
        wh_min, wh_max = domain.custom_bounds["wave_height_m"]
        heights = 2.0 * amplitudes
        h_mask = (heights >= wh_min) & (heights <= wh_max)
        if not np.all(h_mask):
            idx = int(np.where(~h_mask)[0][0])
            raise OutOfDomainError(
                f"Wave component (omega={omegas[idx]:.2f} rad/s, gamma={gamma_deg[idx]:.1f} deg, "
                f"amp={amplitudes[idx]:.2f} m) outside applicability domain of asset {asset_id}"
            )


class FirstOrderWaveLoadModel:
    """Pure calculation of first-order wave excitation loads on vessel hull (SI: N, N·m)."""

    @classmethod
    def _calculate_inferred_scalar(
        cls,
        wave: WaveFieldSample,
        heading: float,
        u: float,
        v: float,
        t: float,
        params: VesselEnvironmentalParameters,
        asset: InferredWaveResponseAsset,
    ) -> VesselLoad:
        """Scalar reference implementation kept as private test oracle."""
        c_kxx = 0.4
        k_xx = c_kxx * params.beam_m
        if k_xx < 1.0e-3 or params.gm_t_m < 1.0e-4:
            roll_nat_freq = 0.4
        else:
            roll_nat_freq = math.sqrt(params.gravity_mps2 * params.gm_t_m / (k_xx * k_xx))

        total_fx = 0.0
        total_fy = 0.0
        total_mx = 0.0
        total_mz = 0.0

        for comp in wave.components:
            gamma_dir = comp.direction_to_rad - heading
            gamma_deg = _normalize_degrees(math.degrees(gamma_dir))

            if not asset.metadata.applicability_domain.contains(
                heading_deg=gamma_deg,
                omega_radps=comp.omega_radps,
                wave_height_m=2.0 * comp.amplitude_m,
            ):
                raise OutOfDomainError(
                    f"Wave component (omega={comp.omega_radps:.2f} rad/s, gamma={gamma_deg:.1f} deg, "
                    f"amp={comp.amplitude_m:.2f} m) outside applicability domain of asset {asset.metadata.asset_id}"
                )

            if comp.amplitude_m <= 0.0:
                continue

            k = (comp.omega_radps * comp.omega_radps) / params.gravity_mps2
            vel_along_wave = u * math.cos(gamma_dir) + v * math.sin(gamma_dir)
            omega_e = comp.omega_radps - k * vel_along_wave
            omega_rao = max(abs(omega_e), 1.0e-4)

            h_surge = math.cos(gamma_dir)
            h_sway = math.sin(gamma_dir)
            h_roll = math.sin(gamma_dir)
            h_yaw = math.sin(2.0 * gamma_dir)

            e_half = math.exp(-k * params.draft_m / 2.0)
            f_fk_sway = (
                comp.amplitude_m
                * params.water_density_kg_m3
                * params.gravity_mps2
                * params.beam_m
                * params.length_between_perpendiculars_m
                * k
                * e_half
            )

            i_depth_roll = (1.0 - math.exp(-k * params.draft_m)) / max(k, 1.0e-8)
            f_fk_roll_raw = (
                comp.amplitude_m
                * params.water_density_kg_m3
                * params.gravity_mps2
                * (params.beam_m * params.beam_m / 4.0)
                * params.length_between_perpendiculars_m
                * i_depth_roll
            )
            f_fk_roll = f_fk_roll_raw * 0.03

            r_surge = omega_rao / max(asset.rao_cutoff_surge, 1.0e-4)
            rao_surge = min(1.0 / math.sqrt(1.0 + r_surge * r_surge), asset.rao_scale_max)

            r_sway = omega_rao / max(asset.rao_cutoff_sway, 1.0e-4)
            rao_sway = min(1.0 / math.sqrt(1.0 + r_sway * r_sway), asset.rao_scale_max)

            r_yaw = omega_rao / max(asset.rao_cutoff_yaw, 1.0e-4)
            rao_yaw = min(1.0 / math.sqrt(1.0 + r_yaw * r_yaw), asset.rao_scale_max)

            r_roll = omega_rao / max(roll_nat_freq, 1.0e-4)
            if r_roll < 0.5:
                rao_roll = 1.0
            elif r_roll <= 2.0:
                d_roll = math.sqrt((1.0 - r_roll * r_roll) ** 2 + 4.0 * (asset.rao_damping_roll**2) * (r_roll**2))
                rao_roll = min(1.0 / max(d_roll, 1.0e-6), asset.rao_scale_max_roll)
            else:
                rao_roll = min(2.0 / (r_roll * r_roll), asset.rao_scale_max_roll)

            phase_t = omega_e * t + comp.phase_rad

            total_fx += asset.rao_surge_scale * asset.fk_scale_factor * f_fk_sway * h_surge * math.cos(phase_t) * rao_surge
            total_fy += asset.rao_sway_scale * asset.fk_scale_factor * f_fk_sway * h_sway * math.cos(phase_t) * rao_sway
            total_mx += asset.rao_roll_scale * f_fk_roll * h_roll * math.cos(phase_t) * rao_roll
            total_mz += (
                asset.rao_yaw_scale
                * asset.fk_scale_factor
                * f_fk_sway
                * params.length_between_perpendiculars_m
                * 0.5
                * h_yaw
                * math.sin(phase_t)
                * rao_yaw
            )

        return VesselLoad(
            surge_n=float(total_fx),
            sway_n=float(total_fy),
            yaw_nm=float(total_mz),
            roll_nm=float(total_mx),
        )

    @classmethod
    def _calculate_inferred(
        cls,
        wave: WaveFieldSample,
        heading: float,
        u: float,
        v: float,
        t: float,
        params: VesselEnvironmentalParameters,
        asset: InferredWaveResponseAsset,
    ) -> VesselLoad:
        arrays = _extract_wave_component_arrays(wave)
        if arrays is None or len(arrays.amplitudes) == 0:
            return VesselLoad.zero()

        amps = arrays.amplitudes
        omegas = arrays.omegas
        phases = arrays.phases
        dirs = arrays.directions

        gamma_dir = dirs - heading
        gamma_deg = np.degrees(gamma_dir) % 360.0

        _check_wave_domain_batch(asset.metadata.asset_id, asset.metadata.applicability_domain, gamma_deg, omegas, amps)

        c_kxx = 0.4
        k_xx = c_kxx * params.beam_m
        if k_xx < 1.0e-3 or params.gm_t_m < 1.0e-4:
            roll_nat_freq = 0.4
        else:
            roll_nat_freq = math.sqrt(params.gravity_mps2 * params.gm_t_m / (k_xx * k_xx))

        cos_gamma = np.cos(gamma_dir)
        sin_gamma = np.sin(gamma_dir)
        sin_2gamma = np.sin(2.0 * gamma_dir)

        k = arrays.omega_sq / params.gravity_mps2
        vel_along_wave = u * cos_gamma + v * sin_gamma
        omega_e = omegas - k * vel_along_wave
        omega_rao = np.maximum(np.abs(omega_e), 1.0e-4)

        e_half = np.exp(-k * (params.draft_m * 0.5))
        sway_geom = (
            params.water_density_kg_m3
            * params.gravity_mps2
            * params.beam_m
            * params.length_between_perpendiculars_m
        )
        f_fk_sway = amps * (sway_geom * k * e_half)

        k_denom = np.maximum(k, 1.0e-8)
        i_depth_roll = (1.0 - np.exp(-k * params.draft_m)) / k_denom
        roll_geom = (
            params.water_density_kg_m3
            * params.gravity_mps2
            * (params.beam_m * params.beam_m * 0.25)
            * params.length_between_perpendiculars_m
            * 0.03
        )
        f_fk_roll = amps * (roll_geom * i_depth_roll)

        r_surge = omega_rao / max(asset.rao_cutoff_surge, 1.0e-4)
        rao_surge = np.minimum(1.0 / np.sqrt(1.0 + r_surge * r_surge), asset.rao_scale_max)

        r_sway = omega_rao / max(asset.rao_cutoff_sway, 1.0e-4)
        rao_sway = np.minimum(1.0 / np.sqrt(1.0 + r_sway * r_sway), asset.rao_scale_max)

        r_yaw = omega_rao / max(asset.rao_cutoff_yaw, 1.0e-4)
        rao_yaw = np.minimum(1.0 / np.sqrt(1.0 + r_yaw * r_yaw), asset.rao_scale_max)

        r_roll = omega_rao / max(roll_nat_freq, 1.0e-4)
        r_roll_sq = r_roll * r_roll
        d_roll = np.sqrt((1.0 - r_roll_sq) ** 2 + 4.0 * (asset.rao_damping_roll**2) * r_roll_sq)
        mid_val = np.minimum(1.0 / np.maximum(d_roll, 1.0e-6), asset.rao_scale_max_roll)
        high_val = np.minimum(2.0 / r_roll_sq, asset.rao_scale_max_roll)
        rao_roll = np.where(r_roll < 0.5, 1.0, np.where(r_roll <= 2.0, mid_val, high_val))

        phase_t = omega_e * t + phases
        cos_phase = np.cos(phase_t)
        sin_phase = np.sin(phase_t)

        fx_comp = (asset.rao_surge_scale * asset.fk_scale_factor) * (f_fk_sway * cos_gamma * cos_phase * rao_surge)
        fy_comp = (asset.rao_sway_scale * asset.fk_scale_factor) * (f_fk_sway * sin_gamma * cos_phase * rao_sway)
        mx_comp = asset.rao_roll_scale * (f_fk_roll * sin_gamma * cos_phase * rao_roll)
        mz_comp = (asset.rao_yaw_scale * asset.fk_scale_factor * params.length_between_perpendiculars_m * 0.5) * (
            f_fk_sway * sin_2gamma * sin_phase * rao_yaw
        )

        if np.any(amps <= 0.0):
            mask = amps > 0.0
            total_fx = float(np.sum(fx_comp[mask]))
            total_fy = float(np.sum(fy_comp[mask]))
            total_mx = float(np.sum(mx_comp[mask]))
            total_mz = float(np.sum(mz_comp[mask]))
        else:
            total_fx = float(np.sum(fx_comp))
            total_fy = float(np.sum(fy_comp))
            total_mx = float(np.sum(mx_comp))
            total_mz = float(np.sum(mz_comp))

        return VesselLoad(
            surge_n=total_fx,
            sway_n=total_fy,
            yaw_nm=total_mz,
            roll_nm=total_mx,
        )

    @classmethod
    def _calculate_tabular(
        cls,
        wave: WaveFieldSample,
        heading: float,
        u: float,
        v: float,
        t: float,
        params: VesselEnvironmentalParameters,
        asset: WaveRaoTableAsset,
    ) -> VesselLoad:
        total_fx = 0.0
        total_fy = 0.0
        total_mx = 0.0
        total_mz = 0.0

        for comp in wave.components:
            gamma_dir = comp.direction_to_rad - heading
            gamma_deg = _normalize_degrees(math.degrees(gamma_dir))

            if not asset.metadata.applicability_domain.contains(
                heading_deg=gamma_deg,
                omega_radps=comp.omega_radps,
                wave_height_m=2.0 * comp.amplitude_m,
            ):
                raise OutOfDomainError(
                    f"Wave component (omega={comp.omega_radps:.2f} rad/s, gamma={gamma_deg:.1f} deg, "
                    f"amp={comp.amplitude_m:.2f} m) outside applicability domain of asset {asset.metadata.asset_id}"
                )

            if comp.amplitude_m <= 0.0:
                continue

            k = (comp.omega_radps * comp.omega_radps) / params.gravity_mps2
            vel_along_wave = u * math.cos(gamma_dir) + v * math.sin(gamma_dir)
            omega_e = comp.omega_radps - k * vel_along_wave

            amp_x, ph_x, amp_y, ph_y, amp_k, ph_k, amp_n, ph_n = asset.interpolate(comp.omega_radps, gamma_deg)
            phase_base = omega_e * t + comp.phase_rad

            total_fx += comp.amplitude_m * amp_x * math.cos(phase_base + ph_x)
            total_fy += comp.amplitude_m * amp_y * math.cos(phase_base + ph_y)
            total_mx += comp.amplitude_m * amp_k * math.cos(phase_base + ph_k)
            total_mz += comp.amplitude_m * amp_n * math.sin(phase_base + ph_n)

        return VesselLoad(
            surge_n=float(total_fx),
            sway_n=float(total_fy),
            yaw_nm=float(total_mz),
            roll_nm=float(total_mx),
        )

    @classmethod
    def calculate(
        cls,
        wave: WaveFieldSample,
        heading_rad: float,
        surge_mps: float,
        sway_mps: float,
        stage_time_s: float,
        params: VesselEnvironmentalParameters,
        asset: InferredWaveResponseAsset | WaveRaoTableAsset | None = None,
    ) -> VesselLoad:
        """Calculate first-order wave excitation load in vessel body frame.

        Args:
            wave: WaveFieldSample containing harmonic wave components.
            heading_rad: Vessel heading in radians (0=North, clockwise positive).
            surge_mps: Vessel forward speed u in m/s.
            sway_mps: Vessel starboard speed v in m/s.
            stage_time_s: Exact stage time t = tick * dt_s + stage_offset_s.
            params: Vessel geometry and fluid parameters.
            asset: Wave response asset (InferredWaveResponseAsset or WaveRaoTableAsset).

        Returns:
            VesselLoad in body frame (surge_n, sway_n, yaw_nm, roll_nm).
        """
        if asset is None:
            raise AssetMissingError("Wave response asset is required for FirstOrderWaveLoadModel")
        if not asset.verify_integrity():
            raise AssetIntegrityError(f"Integrity check failed for wave asset: {asset.metadata.asset_id}")

        if not wave.components:
            return VesselLoad.zero()

        heading = _finite_scalar("heading_rad", heading_rad)
        u = _finite_scalar("surge_mps", surge_mps)
        v = _finite_scalar("sway_mps", sway_mps)
        t = _finite_scalar("stage_time_s", stage_time_s)
        speed = math.hypot(u, v)

        if not asset.metadata.applicability_domain.contains(speed_mps=speed, draft_m=params.draft_m):
            raise OutOfDomainError(
                f"Vessel state (speed={speed:.2f} m/s, draft={params.draft_m:.2f} m) "
                f"outside applicability domain of asset {asset.metadata.asset_id}"
            )

        if isinstance(asset, InferredWaveResponseAsset):
            return cls._calculate_inferred(wave, heading, u, v, t, params, asset)
        if isinstance(asset, WaveRaoTableAsset):
            return cls._calculate_tabular(wave, heading, u, v, t, params, asset)
        raise TypeError(f"Unsupported wave response asset type: {type(asset).__name__}")


class MeanDriftLoadModel:
    """Pure calculation of second-order wave mean-drift loads on vessel hull (SI: N, N·m)."""

    @staticmethod
    def _eval_inferred_drift_coeffs(
        comp: Any,
        heading: float,
        params: VesselEnvironmentalParameters,
        asset: InferredWaveDriftAsset,
    ) -> tuple[float, float, float, float]:
        gamma_dir = comp.direction_to_rad - heading
        gamma_deg = _normalize_degrees(math.degrees(gamma_dir))

        if not asset.metadata.applicability_domain.contains(
            heading_deg=gamma_deg,
            omega_radps=comp.omega_radps,
            wave_height_m=2.0 * comp.amplitude_m,
        ):
            raise OutOfDomainError(
                f"Wave component (omega={comp.omega_radps:.2f} rad/s, gamma={gamma_deg:.1f} deg, "
                f"amp={comp.amplitude_m:.2f} m) outside applicability domain of asset {asset.metadata.asset_id}"
            )

        if comp.amplitude_m <= 0.0:
            return 0.0, 0.0, 0.0, 0.0

        l_val = max(params.length_between_perpendiculars_m, 0.1)
        b_val = max(params.beam_m, 0.1)
        t_val = max(params.draft_m, 0.1)
        kg_val = max(params.kg_m, t_val)

        k = max((comp.omega_radps * comp.omega_radps) / params.gravity_mps2, 1.0e-8)
        kl = min(max(k * l_val, 0.0), 60.0)
        kb = min(max(k * b_val, 0.0), 60.0)
        kt = min(max(k * t_val, 0.0), 60.0)

        long_wave_build_up = (kl * kl) / (1.0 + kl * kl)
        short_wave_decay = 1.0 / math.sqrt(1.0 + (kl / 8.0) ** 4.0)
        draft_participation = math.sqrt(max(0.0, 1.0 - math.exp(-2.0 * kt)))
        finite_beam_reflection = 1.0 - math.exp(-2.0 * kb)

        freq_shape = min(
            max(long_wave_build_up * short_wave_decay * max(0.25, draft_participation), 0.0),
            1.5,
        )
        head_eff = min(
            max(asset.inferred_surge_scale * finite_beam_reflection * freq_shape, 0.0),
            1.0,
        )
        beam_eff = min(
            max(asset.inferred_sway_scale * finite_beam_reflection * freq_shape, 0.0),
            1.0,
        )

        c = math.cos(gamma_dir)
        s = math.sin(gamma_dir)
        c_abs = abs(c)
        s_abs = abs(s)

        surge_per_amp2 = params.water_density_kg_m3 * params.gravity_mps2 * b_val * head_eff
        sway_per_amp2 = params.water_density_kg_m3 * params.gravity_mps2 * l_val * beam_eff
        yaw_lever = asset.inferred_yaw_lever_scale * l_val
        roll_lever = asset.inferred_roll_lever_scale * max(0.1, kg_val - 0.33 * t_val)

        cfx = surge_per_amp2 * c * c_abs
        cfy = sway_per_amp2 * s * s_abs
        cmz = sway_per_amp2 * yaw_lever * c * s
        cmx = sway_per_amp2 * roll_lever * s * s_abs
        return cfx, cfy, cmz, cmx

    @classmethod
    def _calculate_inferred_scalar(
        cls,
        wave: WaveFieldSample | MeanDriftSourceSample,
        heading: float,
        params: VesselEnvironmentalParameters,
        asset: InferredWaveDriftAsset,
    ) -> VesselLoad:
        """Scalar reference implementation kept as private test oracle."""
        total_fx = 0.0
        total_fy = 0.0
        total_mx = 0.0
        total_mz = 0.0

        for comp in wave.components:
            cfx, cfy, cmz, cmx = cls._eval_inferred_drift_coeffs(comp, heading, params, asset)
            amp_sq = comp.amplitude_m * comp.amplitude_m
            total_fx += cfx * amp_sq
            total_fy += cfy * amp_sq
            total_mz += cmz * amp_sq
            total_mx += cmx * amp_sq

        if asset.max_force_n is not None and asset.max_force_n > 0.0:
            fnorm = math.hypot(total_fx, total_fy)
            if fnorm > asset.max_force_n:
                scale = asset.max_force_n / fnorm
                total_fx *= scale
                total_fy *= scale
        if asset.max_moment_nm is not None and asset.max_moment_nm > 0.0:
            total_mx = math.copysign(min(abs(total_mx), asset.max_moment_nm), total_mx)
            total_mz = math.copysign(min(abs(total_mz), asset.max_moment_nm), total_mz)

        return VesselLoad(
            surge_n=float(total_fx),
            sway_n=float(total_fy),
            yaw_nm=float(total_mz),
            roll_nm=float(total_mx),
        )

    @classmethod
    def _calculate_inferred(
        cls,
        wave: WaveFieldSample | MeanDriftSourceSample,
        heading: float,
        params: VesselEnvironmentalParameters,
        asset: InferredWaveDriftAsset,
    ) -> VesselLoad:
        arrays = _extract_wave_component_arrays(wave)
        if arrays is None or len(arrays.amplitudes) == 0:
            return VesselLoad.zero()

        amps = arrays.amplitudes
        omegas = arrays.omegas
        dirs = arrays.directions

        gamma_dir = dirs - heading
        gamma_deg = np.degrees(gamma_dir) % 360.0

        _check_wave_domain_batch(asset.metadata.asset_id, asset.metadata.applicability_domain, gamma_deg, omegas, amps)

        l_val = max(params.length_between_perpendiculars_m, 0.1)
        b_val = max(params.beam_m, 0.1)
        t_val = max(params.draft_m, 0.1)
        kg_val = max(params.kg_m, t_val)

        k = np.maximum(arrays.omega_sq / params.gravity_mps2, 1.0e-8)
        kl = np.clip(k * l_val, 0.0, 60.0)
        kb = np.clip(k * b_val, 0.0, 60.0)
        kt = np.clip(k * t_val, 0.0, 60.0)

        long_wave_build_up = (kl * kl) / (1.0 + kl * kl)
        short_wave_decay = 1.0 / np.sqrt(1.0 + (kl / 8.0) ** 4.0)
        draft_participation = np.sqrt(np.maximum(0.0, 1.0 - np.exp(-2.0 * kt)))
        finite_beam_reflection = 1.0 - np.exp(-2.0 * kb)

        freq_shape = np.clip(
            long_wave_build_up * short_wave_decay * np.maximum(0.25, draft_participation),
            0.0,
            1.5,
        )
        head_eff = np.clip(
            asset.inferred_surge_scale * finite_beam_reflection * freq_shape,
            0.0,
            1.0,
        )
        beam_eff = np.clip(
            asset.inferred_sway_scale * finite_beam_reflection * freq_shape,
            0.0,
            1.0,
        )

        c = np.cos(gamma_dir)
        s = np.sin(gamma_dir)
        c_abs = np.abs(c)
        s_abs = np.abs(s)

        surge_per_amp2 = (params.water_density_kg_m3 * params.gravity_mps2 * b_val) * head_eff
        sway_per_amp2 = (params.water_density_kg_m3 * params.gravity_mps2 * l_val) * beam_eff
        yaw_lever = asset.inferred_yaw_lever_scale * l_val
        roll_lever = asset.inferred_roll_lever_scale * max(0.1, kg_val - 0.33 * t_val)

        amp_sq = arrays.amp_sq

        cfx = surge_per_amp2 * c * c_abs
        cfy = sway_per_amp2 * s * s_abs
        cmz = sway_per_amp2 * (yaw_lever * c * s)
        cmx = sway_per_amp2 * (roll_lever * s * s_abs)

        if np.any(amps <= 0.0):
            mask = amps > 0.0
            total_fx = float(np.sum((cfx * amp_sq)[mask]))
            total_fy = float(np.sum((cfy * amp_sq)[mask]))
            total_mz = float(np.sum((cmz * amp_sq)[mask]))
            total_mx = float(np.sum((cmx * amp_sq)[mask]))
        else:
            total_fx = float(np.sum(cfx * amp_sq))
            total_fy = float(np.sum(cfy * amp_sq))
            total_mz = float(np.sum(cmz * amp_sq))
            total_mx = float(np.sum(cmx * amp_sq))

        if asset.max_force_n is not None and asset.max_force_n > 0.0:
            fnorm = math.hypot(total_fx, total_fy)
            if fnorm > asset.max_force_n:
                scale = asset.max_force_n / fnorm
                total_fx *= scale
                total_fy *= scale
        if asset.max_moment_nm is not None and asset.max_moment_nm > 0.0:
            total_mx = math.copysign(min(abs(total_mx), asset.max_moment_nm), total_mx)
            total_mz = math.copysign(min(abs(total_mz), asset.max_moment_nm), total_mz)

        return VesselLoad(
            surge_n=total_fx,
            sway_n=total_fy,
            yaw_nm=total_mz,
            roll_nm=total_mx,
        )

    @classmethod
    def _calculate_tabular(
        cls,
        wave: WaveFieldSample | MeanDriftSourceSample,
        heading: float,
        asset: WaveDriftTableAsset,
    ) -> VesselLoad:
        total_fx = 0.0
        total_fy = 0.0
        total_mx = 0.0
        total_mz = 0.0

        for comp in wave.components:
            gamma_dir = comp.direction_to_rad - heading
            gamma_deg = _normalize_degrees(math.degrees(gamma_dir))

            if not asset.metadata.applicability_domain.contains(
                heading_deg=gamma_deg,
                omega_radps=comp.omega_radps,
                wave_height_m=2.0 * comp.amplitude_m,
            ):
                raise OutOfDomainError(
                    f"Wave component (omega={comp.omega_radps:.2f} rad/s, gamma={gamma_deg:.1f} deg, "
                    f"amp={comp.amplitude_m:.2f} m) outside applicability domain of asset {asset.metadata.asset_id}"
                )

            if comp.amplitude_m <= 0.0:
                continue

            cdx, cdy, cdn, cdk = asset.interpolate(comp.omega_radps, gamma_deg)
            amp_sq = comp.amplitude_m * comp.amplitude_m
            total_fx += cdx * amp_sq
            total_fy += cdy * amp_sq
            total_mz += cdn * amp_sq
            total_mx += cdk * amp_sq

        return VesselLoad(
            surge_n=float(total_fx),
            sway_n=float(total_fy),
            yaw_nm=float(total_mz),
            roll_nm=float(total_mx),
        )

    @classmethod
    def calculate(
        cls,
        wave: WaveFieldSample | MeanDriftSourceSample,
        heading_rad: float,
        params: VesselEnvironmentalParameters,
        asset: InferredWaveDriftAsset | WaveDriftTableAsset | None = None,
        drift_model: MeanDriftModel | str = MeanDriftModel.DIAGONAL_AI2,
    ) -> VesselLoad:
        """Calculate second-order wave mean-drift load in vessel body frame.

        Args:
            wave: WaveFieldSample or MeanDriftSourceSample with wave components.
            heading_rad: Vessel heading in radians (0=North, clockwise positive).
            params: Vessel geometry and fluid parameters.
            asset: Wave drift asset (InferredWaveDriftAsset or WaveDriftTableAsset).
            drift_model: Formulation to calculate (only DIAGONAL_AI2 supported; FULL_PAIR_QTF rejected).

        Returns:
            VesselLoad in body frame (surge_n, sway_n, yaw_nm, roll_nm).
        """
        model = MeanDriftModel(drift_model)
        if model == MeanDriftModel.FULL_PAIR_QTF:
            raise NotImplementedError(
                "Full component-pair QTF mean-drift calculation is unsupported/deferred; "
                "only diagonal_ai2 drift coefficient formulation is supported."
            )
        if model != MeanDriftModel.DIAGONAL_AI2:
            raise ValueError(f"Unsupported mean drift model: {model}")

        if asset is None:
            raise AssetMissingError("Wave drift asset is required for MeanDriftLoadModel")
        if not asset.verify_integrity():
            raise AssetIntegrityError(f"Integrity check failed for wave drift asset: {asset.metadata.asset_id}")

        if asset.model_type == MeanDriftModel.FULL_PAIR_QTF:
            raise NotImplementedError(
                "Full component-pair QTF asset is unsupported/deferred; "
                "only diagonal_ai2 drift coefficient formulation is supported."
            )
        if asset.model_type != MeanDriftModel.DIAGONAL_AI2:
            raise ValueError(f"Unsupported asset model_type: {asset.model_type}")

        if not wave.components:
            return VesselLoad.zero()

        heading = _finite_scalar("heading_rad", heading_rad)

        if not asset.metadata.applicability_domain.contains(draft_m=params.draft_m):
            raise OutOfDomainError(
                f"Vessel draft ({params.draft_m:.2f} m) outside applicability domain of asset {asset.metadata.asset_id}"
            )

        if isinstance(asset, InferredWaveDriftAsset):
            return cls._calculate_inferred(wave, heading, params, asset)
        if isinstance(asset, WaveDriftTableAsset):
            return cls._calculate_tabular(wave, heading, asset)
        raise TypeError(f"Unsupported wave drift asset type: {type(asset).__name__}")


def _resolve_current_strategy(params: dict[str, Any] | Mapping[str, Any]) -> CurrentStrategy:
    """Resolve and validate current strategy from normalized parameter mapping."""
    if "current_relative_damping" in params:
        raw_crd = params["current_relative_damping"]
        if not isinstance(raw_crd, bool):
            raise TypeError(f"current_relative_damping must be an exact bool, got {type(raw_crd).__name__}")
        has_crd = raw_crd
    else:
        has_crd = False

    if "external_current_load" in params:
        raw_ecl = params["external_current_load"]
        if not isinstance(raw_ecl, bool):
            raise TypeError(f"external_current_load must be an exact bool, got {type(raw_ecl).__name__}")
        has_ecl = raw_ecl
    else:
        has_ecl = False

    if has_crd and has_ecl:
        raise ValueError(
            "current_relative_damping and external_current_load are mutually exclusive (de-duplication VR-09/L105)"
        )

    strat_str = params.get("current_strategy")
    if strat_str is not None:
        if not isinstance(strat_str, str):
            raise TypeError(f"current_strategy must be a string, got {type(strat_str).__name__}")
        if strat_str in ("both", "duplicate", "all"):
            raise ValueError(
                f"unsupported current_strategy '{strat_str}': current_relative_damping and "
                "external_current_load are mutually exclusive"
            )
        return CurrentStrategy(strat_str)
    if has_ecl:
        return CurrentStrategy.EXTERNAL_CURRENT_LOAD
    return CurrentStrategy.CURRENT_RELATIVE_DAMPING


def _build_vessel_parameters(params: dict[str, Any] | Mapping[str, Any]) -> VesselEnvironmentalParameters:
    """Construct VesselEnvironmentalParameters from parameter mapping."""
    return VesselEnvironmentalParameters(
        length_between_perpendiculars_m=params.get("length_between_perpendiculars_m", 44.1),
        beam_m=params.get("beam_m", 8.0),
        draft_m=params.get("draft_m", 1.55),
        wind_frontal_area_m2=params.get("wind_frontal_area_m2", 50.0),
        wind_lateral_area_m2=params.get("wind_lateral_area_m2", 150.0),
        wind_z_center_m=params.get("wind_z_center_m", 3.0),
        wind_roll_moment_arm_m=params.get("wind_roll_moment_arm_m"),
        air_density_kg_m3=params.get("air_density_kg_m3", 1.225),
        water_depth_m=params.get("water_depth_m", 50.0),
        kg_m=params.get("kg_m", 2.0),
        current_roll_moment_arm_m=params.get("current_roll_moment_arm_m"),
        water_density_kg_m3=params.get("water_density_kg_m3", 1025.0),
        displacement_ton=params.get("displacement_ton", 50000.0),
        gm_t_m=params.get("gm_t_m", 1.5),
        bow_angle_rad=params.get("bow_angle_rad", 0.6),
        c_wl_aft=params.get("c_wl_aft", 0.95),
        gravity_mps2=params.get("gravity_mps2", 9.81),
        wave_roll_moment_arm_m=params.get("wave_roll_moment_arm_m"),
    )


def _resolve_single_wave_mode_assets(
    wave_mode: WaveLoadMode,
    w1_id: str | None,
    wmd_id: str | None,
) -> tuple[InferredWaveResponseAsset | WaveRaoTableAsset | None, InferredWaveDriftAsset | WaveDriftTableAsset | None]:
    """Resolve wave assets for OFF, FIRST_ORDER, and MEAN_DRIFT modes."""
    if wave_mode == WaveLoadMode.OFF:
        if w1_id is not None or wmd_id is not None:
            raise ValueError("wave asset IDs must not be provided when wave_mode is OFF")
        return None, None
    if wave_mode == WaveLoadMode.FIRST_ORDER:
        if w1_id is None:
            raise AssetMissingError("wave_first_order_asset_id is required when wave_mode is 'first_order'")
        if wmd_id is not None:
            raise ValueError("wave_mean_drift_asset_id is not allowed when wave_mode is 'first_order'")
        if w1_id not in KNOWN_WAVE_FIRST_ORDER_ASSETS:
            raise AssetMissingError(f"Unknown wave_first_order_asset_id: {w1_id}")
        return KNOWN_WAVE_FIRST_ORDER_ASSETS[w1_id], None

    # MEAN_DRIFT
    if wmd_id is None:
        raise AssetMissingError("wave_mean_drift_asset_id is required when wave_mode is 'mean_drift'")
    if w1_id is not None:
        raise ValueError("wave_first_order_asset_id is not allowed when wave_mode is 'mean_drift'")
    if wmd_id not in KNOWN_WAVE_MEAN_DRIFT_ASSETS:
        raise AssetMissingError(f"Unknown wave_mean_drift_asset_id: {wmd_id}")
    return None, KNOWN_WAVE_MEAN_DRIFT_ASSETS[wmd_id]


def _resolve_wave_assets_from_params(
    wave_mode: WaveLoadMode,
    w1_id: str | None,
    wmd_id: str | None,
) -> tuple[InferredWaveResponseAsset | WaveRaoTableAsset | None, InferredWaveDriftAsset | WaveDriftTableAsset | None]:
    """Resolve explicit wave assets from IDs with strict mode validation and zero defaults."""
    if wave_mode in (WaveLoadMode.OFF, WaveLoadMode.FIRST_ORDER, WaveLoadMode.MEAN_DRIFT):
        return _resolve_single_wave_mode_assets(wave_mode, w1_id, wmd_id)

    # BOTH
    if w1_id is None or wmd_id is None:
        raise AssetMissingError(
            "Both wave_first_order_asset_id and wave_mean_drift_asset_id are required when wave_mode is 'both'"
        )
    if w1_id not in KNOWN_WAVE_FIRST_ORDER_ASSETS:
        raise AssetMissingError(f"Unknown wave_first_order_asset_id: {w1_id}")
    if wmd_id not in KNOWN_WAVE_MEAN_DRIFT_ASSETS:
        raise AssetMissingError(f"Unknown wave_mean_drift_asset_id: {wmd_id}")
    return KNOWN_WAVE_FIRST_ORDER_ASSETS[w1_id], KNOWN_WAVE_MEAN_DRIFT_ASSETS[wmd_id]


def _validate_load_model_wave_assets(
    wave_mode: WaveLoadMode,
    wave_first_order_asset: InferredWaveResponseAsset | WaveRaoTableAsset | None,
    wave_mean_drift_asset: InferredWaveDriftAsset | WaveDriftTableAsset | None,
) -> None:
    """Validate presence or absence of wave assets against declared wave mode."""
    if wave_mode in (WaveLoadMode.FIRST_ORDER, WaveLoadMode.BOTH):
        if wave_first_order_asset is None:
            raise AssetMissingError(f"First-order wave response asset is required when wave_mode is '{wave_mode.value}'")
    elif wave_first_order_asset is not None:
        raise ValueError(f"wave_first_order_asset must not be provided when wave_mode is '{wave_mode.value}'")

    if wave_mode in (WaveLoadMode.MEAN_DRIFT, WaveLoadMode.BOTH):
        if wave_mean_drift_asset is None:
            raise AssetMissingError(f"Wave mean-drift asset is required when wave_mode is '{wave_mode.value}'")
    elif wave_mean_drift_asset is not None:
        raise ValueError(f"wave_mean_drift_asset must not be provided when wave_mode is '{wave_mode.value}'")


class EnvironmentalLoadModel:
    """Plant-side environmental load model with explicit component summation and current de-duplication (VR-09, VR-10)."""

    def __init__(
        self,
        vessel_params: VesselEnvironmentalParameters,
        current_strategy: CurrentStrategy | str = CurrentStrategy.CURRENT_RELATIVE_DAMPING,
        wave_mode: WaveLoadMode | str = WaveLoadMode.OFF,
        wind_asset: WindCoeffTableAsset | None = DEFAULT_OCIMF_WIND_ASSET,
        current_asset: CurrentCoeffTableAsset | InferredCurrentAsset | None = DEFAULT_INFERRED_CURRENT_ASSET,
        wave_first_order_asset: InferredWaveResponseAsset | WaveRaoTableAsset | None = None,
        wave_mean_drift_asset: InferredWaveDriftAsset | WaveDriftTableAsset | None = None,
        enable_wind: bool = True,
        enable_current: bool = True,
    ) -> None:
        """Initialize environmental load model.

        Args:
            vessel_params: Immutable vessel dimensions and fluid parameters.
            current_strategy: Declared strategy for ocean current (spec L105).
            wave_mode: Declared mode for wave loads (OFF, FIRST_ORDER, MEAN_DRIFT, BOTH).
            wind_asset: Wind coefficient asset.
            current_asset: Current coefficient asset.
            wave_first_order_asset: First-order wave response asset (required if wave_mode in FIRST_ORDER, BOTH).
            wave_mean_drift_asset: Second-order wave mean-drift asset (required if wave_mode in MEAN_DRIFT, BOTH).
            enable_wind: Whether to calculate wind loads.
            enable_current: Whether to calculate current loads.
        """
        if not isinstance(vessel_params, VesselEnvironmentalParameters):
            raise TypeError(f"vessel_params must be VesselEnvironmentalParameters, got {type(vessel_params).__name__}")
        self._vessel_params = vessel_params
        self._current_strategy = CurrentStrategy(current_strategy)
        self._wave_mode = WaveLoadMode(wave_mode)
        self._wind_asset = wind_asset
        self._current_asset = current_asset

        _validate_load_model_wave_assets(self._wave_mode, wave_first_order_asset, wave_mean_drift_asset)

        if wind_asset is not None and not wind_asset.verify_integrity():
            raise AssetIntegrityError(f"Integrity check failed for wind asset: {wind_asset.metadata.asset_id}")
        if current_asset is not None and not current_asset.verify_integrity():
            raise AssetIntegrityError(f"Integrity check failed for current asset: {current_asset.metadata.asset_id}")
        if wave_first_order_asset is not None and not wave_first_order_asset.verify_integrity():
            raise AssetIntegrityError(f"Integrity check failed for wave asset: {wave_first_order_asset.metadata.asset_id}")
        if wave_mean_drift_asset is not None and not wave_mean_drift_asset.verify_integrity():
            raise AssetIntegrityError(f"Integrity check failed for wave drift asset: {wave_mean_drift_asset.metadata.asset_id}")

        self._wave_first_order_asset = wave_first_order_asset
        self._wave_mean_drift_asset = wave_mean_drift_asset

        if not isinstance(enable_wind, bool):
            raise TypeError(f"enable_wind must be an exact bool, got {type(enable_wind).__name__}")
        if not isinstance(enable_current, bool):
            raise TypeError(f"enable_current must be an exact bool, got {type(enable_current).__name__}")
        self._enable_wind = enable_wind
        self._enable_current = enable_current

    @property
    def vessel_params(self) -> VesselEnvironmentalParameters:
        """Return immutable vessel environmental parameters."""
        return self._vessel_params

    @property
    def current_strategy(self) -> CurrentStrategy:
        """Return declared current strategy."""
        return self._current_strategy

    @property
    def wave_mode(self) -> WaveLoadMode:
        """Return declared wave load mode."""
        return self._wave_mode

    @property
    def wind_asset(self) -> WindCoeffTableAsset | None:
        """Return wind asset."""
        return self._wind_asset

    @property
    def current_asset(self) -> CurrentCoeffTableAsset | InferredCurrentAsset | None:
        """Return current asset."""
        return self._current_asset

    @property
    def wave_first_order_asset(self) -> InferredWaveResponseAsset | WaveRaoTableAsset | None:
        """Return first-order wave response asset."""
        return self._wave_first_order_asset

    @property
    def wave_mean_drift_asset(self) -> InferredWaveDriftAsset | WaveDriftTableAsset | None:
        """Return wave mean-drift asset."""
        return self._wave_mean_drift_asset

    def compute_loads(
        self,
        truth: EnvironmentTruth,
        vessel_state: NavigationState | PlantState,
    ) -> EnvironmentalLoads:
        """Compute separate component loads and explicitly sum into EnvironmentalLoads (TS-21, VR-09).

        Args:
            truth: EnvironmentTruth sample from EnvironmentField.
            vessel_state: Vessel state (NavigationState or PlantState).

        Returns:
            Immutable EnvironmentalLoads with explicit summation.
        """
        if not isinstance(truth, EnvironmentTruth):
            raise TypeError(f"truth must be EnvironmentTruth, got {type(truth).__name__}")

        if isinstance(vessel_state, NavigationState):
            heading_rad = vessel_state.heading_rad
            surge_mps = vessel_state.surge_mps
            sway_mps = vessel_state.sway_mps
        elif isinstance(vessel_state, PlantState):
            heading_rad = vessel_state.heading_rad
            surge_mps = vessel_state.surge_mps
            sway_mps = vessel_state.sway_mps
        else:
            raise TypeError(f"vessel_state must be NavigationState or PlantState, got {type(vessel_state).__name__}")

        # 1. Wind load
        if self._enable_wind:
            wind_load = WindLoadModel.calculate(
                wind=truth.wind,
                heading_rad=heading_rad,
                surge_mps=surge_mps,
                sway_mps=sway_mps,
                params=self._vessel_params,
                asset=self._wind_asset,
            )
        else:
            wind_load = VesselLoad.zero()

        # 2. Current load
        if self._enable_current:
            current_load = CurrentLoadModel.calculate(
                current=truth.current,
                heading_rad=heading_rad,
                surge_mps=surge_mps,
                sway_mps=sway_mps,
                params=self._vessel_params,
                strategy=self._current_strategy,
                asset=self._current_asset,
            )
        else:
            current_load = VesselLoad.zero()

        # 3. Wave first-order load
        if self._wave_mode in (WaveLoadMode.FIRST_ORDER, WaveLoadMode.BOTH):
            wave_1st = FirstOrderWaveLoadModel.calculate(
                wave=truth.wave,
                heading_rad=heading_rad,
                surge_mps=surge_mps,
                sway_mps=sway_mps,
                stage_time_s=truth.time_s,
                params=self._vessel_params,
                asset=self._wave_first_order_asset,
            )
        else:
            wave_1st = VesselLoad.zero()

        # 4. Wave mean-drift load
        if self._wave_mode in (WaveLoadMode.MEAN_DRIFT, WaveLoadMode.BOTH):
            wave_drift = MeanDriftLoadModel.calculate(
                wave=truth.mean_drift,
                heading_rad=heading_rad,
                params=self._vessel_params,
                asset=self._wave_mean_drift_asset,
            )
        else:
            wave_drift = VesselLoad.zero()

        return EnvironmentalLoads.from_components(
            wind=wind_load,
            current=current_load,
            wave_first_order=wave_1st,
            wave_mean_drift=wave_drift,
            details={
                "current_strategy": self._current_strategy.value,
                "enable_wind": self._enable_wind,
                "enable_current": self._enable_current,
                "wave_mode": self._wave_mode.value,
                "mean_drift_model": (
                    MeanDriftModel.DIAGONAL_AI2.value
                    if self._wave_mode in (WaveLoadMode.MEAN_DRIFT, WaveLoadMode.BOTH)
                    else "off"
                ),
                "first_order_components_count": (
                    len(truth.wave.components) if self._wave_mode in (WaveLoadMode.FIRST_ORDER, WaveLoadMode.BOTH) else 0
                ),
                "mean_drift_components_count": (
                    len(truth.mean_drift.components)
                    if self._wave_mode in (WaveLoadMode.MEAN_DRIFT, WaveLoadMode.BOTH)
                    else 0
                ),
                "wave_first_order_asset_id": (
                    self._wave_first_order_asset.metadata.asset_id if self._wave_first_order_asset is not None else None
                ),
                "wave_first_order_asset_trust": (
                    self._wave_first_order_asset.metadata.trust_level.value
                    if self._wave_first_order_asset is not None
                    else None
                ),
                "wave_mean_drift_asset_id": (
                    self._wave_mean_drift_asset.metadata.asset_id if self._wave_mean_drift_asset is not None else None
                ),
                "wave_mean_drift_asset_trust": (
                    self._wave_mean_drift_asset.metadata.trust_level.value
                    if self._wave_mean_drift_asset is not None
                    else None
                ),
            },
        )

    def compute_total_load_for_rhs(
        self,
        truth: EnvironmentTruth,
        vessel_state: NavigationState | PlantState,
    ) -> VesselLoad:
        """Internal fast path computing only the total VesselLoad for integrator stages (Slice 4)."""
        if not isinstance(truth, EnvironmentTruth):
            raise TypeError(f"truth must be EnvironmentTruth, got {type(truth).__name__}")

        if isinstance(vessel_state, (NavigationState, PlantState)):
            heading_rad = vessel_state.heading_rad
            surge_mps = vessel_state.surge_mps
            sway_mps = vessel_state.sway_mps
        else:
            raise TypeError(f"vessel_state must be NavigationState or PlantState, got {type(vessel_state).__name__}")

        # 1. Wind load
        if self._enable_wind:
            wind_load = WindLoadModel.calculate(
                wind=truth.wind,
                heading_rad=heading_rad,
                surge_mps=surge_mps,
                sway_mps=sway_mps,
                params=self._vessel_params,
                asset=self._wind_asset,
            )
        else:
            wind_load = VesselLoad.zero()

        # 2. Current load
        if self._enable_current:
            current_load = CurrentLoadModel.calculate(
                current=truth.current,
                heading_rad=heading_rad,
                surge_mps=surge_mps,
                sway_mps=sway_mps,
                params=self._vessel_params,
                strategy=self._current_strategy,
                asset=self._current_asset,
            )
        else:
            current_load = VesselLoad.zero()

        # 3. Wave first-order load
        if self._wave_mode in (WaveLoadMode.FIRST_ORDER, WaveLoadMode.BOTH):
            wave_1st = FirstOrderWaveLoadModel.calculate(
                wave=truth.wave,
                heading_rad=heading_rad,
                surge_mps=surge_mps,
                sway_mps=sway_mps,
                stage_time_s=truth.time_s,
                params=self._vessel_params,
                asset=self._wave_first_order_asset,
            )
        else:
            wave_1st = VesselLoad.zero()

        # 4. Wave mean-drift load
        if self._wave_mode in (WaveLoadMode.MEAN_DRIFT, WaveLoadMode.BOTH):
            wave_drift = MeanDriftLoadModel.calculate(
                wave=truth.mean_drift,
                heading_rad=heading_rad,
                params=self._vessel_params,
                asset=self._wave_mean_drift_asset,
            )
        else:
            wave_drift = VesselLoad.zero()

        return wind_load + current_load + wave_1st + wave_drift

    @classmethod
    def from_params(cls, params: dict[str, Any] | Mapping[str, Any]) -> EnvironmentalLoadModel:
        """Construct EnvironmentalLoadModel from normalized parameter dictionary."""
        strategy = _resolve_current_strategy(params)

        enable_wind = params.get("enable_wind", True)
        if not isinstance(enable_wind, bool):
            raise TypeError(f"enable_wind must be an exact bool, got {type(enable_wind).__name__}")
        enable_current = params.get("enable_current", True)
        if not isinstance(enable_current, bool):
            raise TypeError(f"enable_current must be an exact bool, got {type(enable_current).__name__}")

        wave_mode_raw = params.get("wave_mode", "off")
        wave_mode = WaveLoadMode(wave_mode_raw)

        w1_id = params.get("wave_first_order_asset_id")
        wmd_id = params.get("wave_mean_drift_asset_id")

        wave_1st_asset, wave_drift_asset = _resolve_wave_assets_from_params(wave_mode, w1_id, wmd_id)

        v_params = _build_vessel_parameters(params)

        return cls(
            vessel_params=v_params,
            current_strategy=strategy,
            wave_mode=wave_mode,
            wind_asset=DEFAULT_OCIMF_WIND_ASSET if enable_wind else None,
            current_asset=(
                DEFAULT_INFERRED_CURRENT_ASSET
                if (enable_current and strategy == CurrentStrategy.EXTERNAL_CURRENT_LOAD)
                else None
            ),
            wave_first_order_asset=wave_1st_asset,
            wave_mean_drift_asset=wave_drift_asset,
            enable_wind=enable_wind,
            enable_current=enable_current,
        )
