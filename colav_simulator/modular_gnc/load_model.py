"""Vessel environmental loads, asset validation, and current de-duplication (TS-01..07, VR-09, VR-10)."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

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
    NavigationState,
    OutOfDomainError,
    PlantState,
    VesselLoad,
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
        """Validate non-empty table and freeze."""
        if not self.table:
            raise ValueError("Wind coefficient table cannot be empty")
        for i, entry in enumerate(self.table):
            if not isinstance(entry, WindCoeffEntry):
                raise TypeError(f"table[{i}] must be WindCoeffEntry, got {type(entry).__name__}")
        object.__setattr__(self, "table", tuple(self.table))

    def verify_integrity(self) -> bool:
        """Verify table content SHA-256 against metadata hash."""
        raw_rows = [(entry.angle_deg, entry.cx, entry.cy, entry.cn) for entry in self.table]
        payload = json.dumps(raw_rows, separators=(",", ":")).encode("utf-8")
        calc_sha = hashlib.sha256(payload).hexdigest()
        return calc_sha == self.metadata.sha256

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
        """Validate non-empty table and freeze."""
        if not self.table:
            raise ValueError("Current coefficient table cannot be empty")
        for i, entry in enumerate(self.table):
            if not isinstance(entry, CurrentCoeffEntry):
                raise TypeError(f"table[{i}] must be CurrentCoeffEntry, got {type(entry).__name__}")
        object.__setattr__(self, "table", tuple(self.table))

    def verify_integrity(self) -> bool:
        """Verify table content SHA-256 against metadata hash."""
        raw_rows = [(entry.heading_deg, entry.ccx, entry.ccy, entry.cmz) for entry in self.table]
        payload = json.dumps(raw_rows, separators=(",", ":")).encode("utf-8")
        calc_sha = hashlib.sha256(payload).hexdigest()
        return calc_sha == self.metadata.sha256

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
        return first.ccx, first.cy, first.cmz, first.cmx


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
        payload = b"inferred_crossflow_v1"
        return self.metadata.sha256 == hashlib.sha256(payload).hexdigest()

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

    def __post_init__(self) -> None:
        """Validate positive physical parameters."""
        lpp = _finite_scalar("length_between_perpendiculars_m", self.length_between_perpendiculars_m)
        if lpp <= 0.0:
            raise ValueError("length_between_perpendiculars_m must be positive")
        beam = _finite_scalar("beam_m", self.beam_m)
        if beam <= 0.0:
            raise ValueError("beam_m must be positive")
        draft = _finite_scalar("draft_m", self.draft_m)
        if draft <= 0.0:
            raise ValueError("draft_m must be positive")
        fa = _finite_scalar("wind_frontal_area_m2", self.wind_frontal_area_m2)
        if fa <= 0.0:
            raise ValueError("wind_frontal_area_m2 must be positive")
        la = _finite_scalar("wind_lateral_area_m2", self.wind_lateral_area_m2)
        if la <= 0.0:
            raise ValueError("wind_lateral_area_m2 must be positive")
        air_rho = _finite_scalar("air_density_kg_m3", self.air_density_kg_m3)
        if air_rho <= 0.0:
            raise ValueError("air_density_kg_m3 must be positive")
        water_rho = _finite_scalar("water_density_kg_m3", self.water_density_kg_m3)
        if water_rho <= 0.0:
            raise ValueError("water_density_kg_m3 must be positive")
        depth = _finite_scalar("water_depth_m", self.water_depth_m)
        if depth <= 0.0:
            raise ValueError("water_depth_m must be positive")
        z_c = _finite_scalar("wind_z_center_m", self.wind_z_center_m)
        kg = _finite_scalar("kg_m", self.kg_m)

        object.__setattr__(self, "length_between_perpendiculars_m", lpp)
        object.__setattr__(self, "beam_m", beam)
        object.__setattr__(self, "draft_m", draft)
        object.__setattr__(self, "wind_frontal_area_m2", fa)
        object.__setattr__(self, "wind_lateral_area_m2", la)
        object.__setattr__(self, "air_density_kg_m3", air_rho)
        object.__setattr__(self, "water_density_kg_m3", water_rho)
        object.__setattr__(self, "water_depth_m", depth)
        object.__setattr__(self, "wind_z_center_m", z_c)
        object.__setattr__(self, "kg_m", kg)

        if self.wind_roll_moment_arm_m is not None:
            object.__setattr__(
                self,
                "wind_roll_moment_arm_m",
                _finite_scalar("wind_roll_moment_arm_m", self.wind_roll_moment_arm_m),
            )
        if self.current_roll_moment_arm_m is not None:
            object.__setattr__(
                self,
                "current_roll_moment_arm_m",
                _finite_scalar("current_roll_moment_arm_m", self.current_roll_moment_arm_m),
            )


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
        sha256="6c3391daa24862632e5c423b9d95cda66f15162b034830a839a18e762e4f1226",
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


class EnvironmentalLoadModel:
    """Plant-side environmental load model with explicit component summation and current de-duplication (VR-09, VR-10)."""

    def __init__(
        self,
        vessel_params: VesselEnvironmentalParameters,
        current_strategy: CurrentStrategy | str = CurrentStrategy.CURRENT_RELATIVE_DAMPING,
        wind_asset: WindCoeffTableAsset | None = DEFAULT_OCIMF_WIND_ASSET,
        current_asset: CurrentCoeffTableAsset | InferredCurrentAsset | None = DEFAULT_INFERRED_CURRENT_ASSET,
        enable_wind: bool = True,
        enable_current: bool = True,
    ) -> None:
        """Initialize environmental load model.

        Args:
            vessel_params: Immutable vessel dimensions and fluid parameters.
            current_strategy: Declared strategy for ocean current (spec L105).
            wind_asset: Wind coefficient asset.
            current_asset: Current coefficient asset.
            enable_wind: Whether to calculate wind loads.
            enable_current: Whether to calculate current loads.
        """
        if not isinstance(vessel_params, VesselEnvironmentalParameters):
            raise TypeError(f"vessel_params must be VesselEnvironmentalParameters, got {type(vessel_params).__name__}")
        self._vessel_params = vessel_params
        self._current_strategy = CurrentStrategy(current_strategy)
        self._wind_asset = wind_asset
        self._current_asset = current_asset
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
    def wind_asset(self) -> WindCoeffTableAsset | None:
        """Return wind asset."""
        return self._wind_asset

    @property
    def current_asset(self) -> CurrentCoeffTableAsset | InferredCurrentAsset | None:
        """Return current asset."""
        return self._current_asset

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
            heading_rad = float(vessel_state.values[2])
            surge_mps = float(vessel_state.values[3])
            sway_mps = float(vessel_state.values[4])
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

        # Wave loads are zero for Issue #50 (delivered in #51 with RAO/QTF)
        wave_1st = VesselLoad.zero()
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
            },
        )

    @classmethod
    def from_params(cls, params: dict[str, Any] | Mapping[str, Any]) -> EnvironmentalLoadModel:
        """Construct EnvironmentalLoadModel from normalized parameter dictionary."""
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
            strategy = CurrentStrategy(strat_str)
        elif has_ecl:
            strategy = CurrentStrategy.EXTERNAL_CURRENT_LOAD
        elif has_crd:
            strategy = CurrentStrategy.CURRENT_RELATIVE_DAMPING
        else:
            strategy = CurrentStrategy.CURRENT_RELATIVE_DAMPING

        enable_wind = params.get("enable_wind", True)
        if not isinstance(enable_wind, bool):
            raise TypeError(f"enable_wind must be an exact bool, got {type(enable_wind).__name__}")
        enable_current = params.get("enable_current", True)
        if not isinstance(enable_current, bool):
            raise TypeError(f"enable_current must be an exact bool, got {type(enable_current).__name__}")

        v_params = VesselEnvironmentalParameters(
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
        )

        return cls(
            vessel_params=v_params,
            current_strategy=strategy,
            enable_wind=enable_wind,
            enable_current=enable_current,
        )
