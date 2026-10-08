"""HALO24-anchored statistical radar video and shadow CA-CFAR.

Hardware beam widths are public specifications. RCS, range PSF, clutter,
weather attenuation and receiver calibration are engineering approximations.
This channel never supplies the production tracker or consumes its RNG.
"""

from __future__ import annotations

import base64
import hashlib
import math
import zlib
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
from scipy.ndimage import find_objects, label


@dataclass(frozen=True)
class Halo24Profile:
    """Versioned hardware anchor plus explicitly uncalibrated model choices."""

    profile_id: str = "simrad_halo24_milliampere_v1"
    frequency_ghz: tuple[float, float] = (9.4, 9.5)
    peak_power_w: float = 25.0
    horizontal_beamwidth_deg: float = 3.9
    vertical_beamwidth_deg: float = 22.0
    minimum_range_m: float = 6.0
    range_psf_fwhm_m: float = 20.0
    pfa: float = 1e-4
    range_bins: int = 1024
    guard_cells: int = 3
    training_cells_per_side: int = 12
    rain_mm_h: float = 0.0
    source_url: str = "https://www.simrad-yachting.com/en-sg/simrad/type/radar/halo24-simrad-radar/"
    calibration_status: str = "UNCALIBRATED_ENGINEERING_MODEL"

    def __post_init__(self):
        """Validate the bounded engineering profile."""
        if not 64 <= self.range_bins <= 4096:
            raise ValueError("radar range bins must be in [64, 4096]")
        if not 0 < self.pfa < 1 or self.range_psf_fwhm_m <= 0 or self.rain_mm_h < 0:
            raise ValueError("invalid radar video profile")


def ca_cfar(power: np.ndarray, *, pfa: float = 1e-4, guard: int = 3, training: int = 12) -> tuple[np.ndarray, np.ndarray]:
    """Two-sided range CA-CFAR on linear power; edges have no threshold claim."""
    if power.ndim != 2 or not 0 < pfa < 1 or guard < 0 or training < 1:
        raise ValueError("invalid CA-CFAR input")
    width = power.shape[1]
    noise = np.zeros_like(power, dtype=np.float64)
    threshold = np.full_like(power, np.inf, dtype=np.float64)
    margin = guard + training
    if width <= 2 * margin:
        return power > threshold, threshold
    sums = np.pad(np.cumsum(power, axis=1, dtype=np.float64), ((0, 0), (1, 0)))
    indices = np.arange(margin, width - margin)
    left = sums[:, indices - guard] - sums[:, indices - guard - training]
    right = sums[:, indices + guard + training + 1] - sums[:, indices + guard + 1]
    noise[:, indices] = (left + right) / (2 * training)
    alpha = 2 * training * (pfa ** (-1 / (2 * training)) - 1)
    threshold[:, indices] = alpha * noise[:, indices]
    return power > threshold, threshold


def encode_video(array: np.ndarray) -> dict:
    """Bounded binary grid in a deflate envelope, not a float JSON matrix."""
    raw = np.ascontiguousarray(array, dtype=np.uint8).tobytes()
    return {
        "encoding": "deflate-base64-u8",
        "shape": list(array.shape),
        "data": base64.b64encode(zlib.compress(raw, 1)).decode("ascii"),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def decode_video(document: dict) -> np.ndarray:
    """Calibration/replay decoder with explicit shape and content validation."""
    rows, cols = document["shape"]
    if not (0 <= rows <= 8192 and 0 < cols <= 4096) or document["encoding"] != "deflate-base64-u8":
        raise ValueError("invalid radar video shape/encoding")
    size = rows * cols
    inflater = zlib.decompressobj()
    raw = inflater.decompress(base64.b64decode(document["data"], validate=True), size + 1)
    if len(raw) != size or not inflater.eof or inflater.unused_data or inflater.unconsumed_tail:
        raise ValueError("invalid radar video length")
    if hashlib.sha256(raw).hexdigest() != document["sha256"]:
        raise ValueError("radar video hash mismatch")
    return np.frombuffer(raw, dtype=np.uint8).reshape(rows, cols)


class RadarVideo:
    """Incremental spoke stream, with a checkpoint each revolution for seeks."""

    def __init__(self, spokes: int, profile: Halo24Profile, seed: int | None):
        if not 64 <= spokes <= 8192:
            raise ValueError("radar spokes must be in [64, 8192]")
        self.spokes = spokes
        self.profile = profile
        self.seed = int(seed or 0) & 0xFFFFFFFF
        self.grid = np.zeros((spokes, profile.range_bins), dtype=np.uint8)
        self.row_times = np.full(spokes, -1.0)
        self.row_origins = np.zeros((spokes, 2))
        self.row_bearings = np.arange(spokes) * (2 * np.pi / spokes)
        self.previous_spoke = 0
        self.previous_revolution = -1
        self.checkpoint = None

    def step(self, sensor: Any, t: float, targets: list, own: np.ndarray, yaw: float) -> dict:
        profile = self.profile
        end = int(math.floor(t / sensor.scan_period_s * self.spokes))
        if end < self.previous_spoke or end - self.previous_spoke > self.spokes * 2:
            raise ValueError("radar video gap requires reset or a smaller simulation step")
        absolute = np.arange(self.previous_spoke, end)
        rows = absolute % self.spokes
        times = (absolute + 1) * sensor.scan_period_s / self.spokes
        # Gyro-referenced north-stabilized output spokes; pose is retained per row.
        angles = rows * (2 * np.pi / self.spokes)
        own_positions = own[:2] + (times - t)[:, None] * own[2:4]
        own_positions += sensor.params.shadow_video_mount_forward_m * np.array([np.cos(yaw), np.sin(yaw)])
        own_positions += sensor.params.shadow_video_mount_starboard_m * np.array([-np.sin(yaw), np.cos(yaw)])
        ranges = (np.arange(profile.range_bins) + 0.5) * sensor.active_range_m / profile.range_bins
        power, terrain_coverage = self._background(sensor, absolute, times, angles, own_positions, ranges)
        self._target_echoes(sensor, t, targets, own, yaw, times, angles, own_positions, ranges, power)
        detections, count = self._detections(
            power, own_positions, angles, times, ranges, sensor.params.max_measurements_per_scan
        )
        video = np.clip((10 * np.log10(np.maximum(power, 1e-12)) + 10) * (255 / 70), 0, 255).astype(np.uint8)
        self.grid[rows] = video
        self.row_times[rows] = times
        self.row_origins[rows] = own_positions
        self.row_bearings[rows] = angles
        revolution = end // self.spokes
        if revolution != self.previous_revolution:
            self.checkpoint = {
                **encode_video(self.grid),
                "row_times_s": self.row_times.tolist(),
                "row_origins_ne_m": self.row_origins.tolist(),
                "row_bearings_rad": self.row_bearings.tolist(),
                "t_s": float(t),
            }
            self.previous_revolution = revolution
        self.previous_spoke = end
        return {
            "schema_version": "radar-video@1",
            "mode": "SHADOW",
            "profile": asdict(profile),
            "detector": {"id": "range_ca_cfar@1", "pfa": profile.pfa, "input": "linear_power", "production_tracker": False},
            "range_m": sensor.active_range_m,
            "spokes": self.spokes,
            "range_cell_pitch_m": sensor.active_range_m / profile.range_bins,
            "spoke_seq_start": int(absolute[0]) if len(rows) else end,
            "spoke_seq_end": end,
            "rows": rows.tolist(),
            "row_times_s": times.tolist(),
            "row_origins_ne_m": own_positions.tolist(),
            "row_bearings_rad": angles.tolist(),
            "chunk": encode_video(video),
            "checkpoint": self.checkpoint,
            "detections": detections,
            "terrain_coverage": terrain_coverage,
            "detections_truncated": count > len(detections),
            "mount_attitude_deg": [sensor.params.shadow_video_pitch_deg, sensor.params.shadow_video_roll_deg],
            "pose_provenance": "planar_ship_pose_with_configured_mount_attitude",
            "terrain_source": "ENC_LANDMASK"
            if sensor._shadow_terrain_grid is not None
            else ("DEM" if sensor._occlusion_grid is not None else "NONE"),
        }

    def _background(
        self,
        sensor: Any,
        absolute: np.ndarray,
        times: np.ndarray,
        angles: np.ndarray,
        own_positions: np.ndarray,
        ranges: np.ndarray,
    ) -> tuple[np.ndarray, float | None]:
        profile = self.profile
        rows = absolute % self.spokes
        indices = absolute[:, None].astype(np.uint64) * np.uint64(profile.range_bins) + np.arange(
            profile.range_bins, dtype=np.uint64
        )
        # Addressed random field: partitioning a scan into ticks does not change noise.
        with np.errstate(over="ignore"):
            bits = indices + np.uint64(self.seed) + np.uint64(0x9E3779B97F4A7C15)
            bits = (bits ^ (bits >> 30)) * np.uint64(0xBF58476D1CE4E5B9)
            bits = (bits ^ (bits >> 27)) * np.uint64(0x94D049BB133111EB)
            bits ^= bits >> 31
        uniform = ((bits >> 11).astype(float) + 0.5) / 2**53
        speckle = -np.log(uniform)
        sea_factor = 10 ** (0.1 * sensor.params.clutter_db_per_beaufort * (sensor.params.sea_state_beaufort - 3))
        texture = np.exp(0.5 * np.sin(angles[:, None] * 3 + ranges[None, :] / 700 + times[:, None] / 4))
        sea_mean = sea_factor * np.minimum(20.0, (800 / np.maximum(ranges, 40)) ** 2)
        power = speckle * (1 + texture * sea_mean + profile.rain_mm_h * 0.1)
        terrain_coverage = None
        grid = sensor._shadow_terrain_grid or sensor._occlusion_grid
        if grid is not None and len(rows):
            north = own_positions[:, 0, None] + np.cos(angles)[:, None] * ranges
            east = own_positions[:, 1, None] + np.sin(angles)[:, None] * ranges
            rr = np.floor((grid.origin_n - north) / grid.cell_size).astype(int)
            cc = np.floor((east - grid.origin_e) / grid.cell_size).astype(int)
            covered = (rr >= 0) & (cc >= 0) & (rr < grid.elevation.shape[0]) & (cc < grid.elevation.shape[1])
            height = grid.elevation[np.clip(rr, 0, grid.elevation.shape[0] - 1), np.clip(cc, 0, grid.elevation.shape[1] - 1)]
            land = covered & (height > 0)
            behind = np.cumsum(land, axis=1) > 0
            shoreline = land & (np.cumsum(land, axis=1) <= 3)
            power[behind] = 0
            power[shoreline] += 1e3
            terrain_coverage = float(np.mean(covered))
        return power, terrain_coverage

    def _target_echoes(
        self,
        sensor: Any,
        t: float,
        targets: list,
        own: np.ndarray,
        yaw: float,
        times: np.ndarray,
        angles: np.ndarray,
        own_positions: np.ndarray,
        ranges: np.ndarray,
        power: np.ndarray,
    ) -> None:
        profile = self.profile
        for _, state_values, length, width in targets:
            state = np.asarray(state_values, dtype=float)
            if not np.isfinite(state[:4]).all():
                continue
            delta = state[:2] - own[:2]
            distance = float(np.linalg.norm(delta))
            height = float(np.clip(length * sensor.params.target_height_per_length, 2, 35))
            bearing = float(np.arctan2(delta[1], delta[0]))
            if distance > min(sensor.active_range_m, sensor.horizon_range_m(height)) or distance < profile.minimum_range_m:
                continue
            terrain = sensor._shadow_terrain_grid
            shadow_blocked = terrain is not None and terrain.line_of_sight_blocked(
                antenna_e=float(own[1]),
                antenna_n=float(own[0]),
                target_e=float(state[1]),
                target_n=float(state[0]),
                antenna_height_m=sensor.params.antenna_height_m,
                target_height_m=height,
            )
            if sensor._bearing_blind(bearing, yaw) or shadow_blocked or sensor._occluded(own[:2], state[:2], height):
                continue
            velocity = state[2:4]
            heading = float(np.arctan2(velocity[1], velocity[0])) if np.linalg.norm(velocity) > 0.1 else 0.0
            aspect = 0.25 + 0.75 * abs(np.sin(heading - bearing))
            for fraction in (-0.3, 0.0, 0.3):
                center = state[:2] + length * fraction * np.array([np.cos(heading), np.sin(heading)])
                relative = center + (times - t)[:, None] * velocity - own_positions
                rr = np.linalg.norm(relative, axis=1)
                bb = np.arctan2(relative[:, 1], relative[:, 0])
                angle_delta = (bb - angles + np.pi) % (2 * np.pi) - np.pi
                beam_power = np.exp(-8 * np.log(2) * (angle_delta / np.radians(profile.horizontal_beamwidth_deg)) ** 2)
                elevation = np.arctan2(height - sensor.params.antenna_height_m, np.maximum(rr, 1))
                relative_bearing = bb - yaw
                elevation -= np.radians(sensor.params.shadow_video_pitch_deg) * np.cos(relative_bearing)
                elevation -= np.radians(sensor.params.shadow_video_roll_deg) * np.sin(relative_bearing)
                vertical = np.exp(-8 * np.log(2) * (elevation / np.radians(profile.vertical_beamwidth_deg)) ** 2)
                snr = np.array([sensor.snr_db(r, sensor.rcs_m2(length, width) * aspect / 3) for r in rr])
                # Weather loss is an engineering attenuation model, not HALO firmware.
                amplitude = 10 ** (np.clip(snr - profile.rain_mm_h * rr / 100000, -30, 70) / 10)
                radial = np.exp(-4 * np.log(2) * ((ranges[None, :] - rr[:, None]) / profile.range_psf_fwhm_m) ** 2)
                power += amplitude[:, None] * beam_power[:, None] * vertical[:, None] * radial

    def _detections(
        self,
        power: np.ndarray,
        own_positions: np.ndarray,
        angles: np.ndarray,
        times: np.ndarray,
        ranges: np.ndarray,
        limit: int,
    ) -> tuple[list[dict], int]:
        profile = self.profile
        if power.size == 0:
            return [], 0
        blind = ranges < profile.minimum_range_m
        power[:, blind] = 0
        mask, threshold = ca_cfar(
            power, pfa=profile.pfa, guard=profile.guard_cells, training=profile.training_cells_per_side
        )
        mask[:, blind] = False
        detections = []
        groups, count = label(mask)
        for group, region in enumerate(find_objects(groups), start=1):
            if region is None:
                continue
            rr, cc = np.nonzero(groups[region] == group)
            rr += region[0].start
            cc += region[1].start
            if not len(rr):
                continue
            weight = power[rr, cc]
            xy = own_positions[rr] + ranges[cc, None] * np.column_stack((np.cos(angles[rr]), np.sin(angles[rr])))
            centroid = np.average(xy, axis=0, weights=weight)
            detections.append(
                {
                    "north_m": float(centroid[0]),
                    "east_m": float(centroid[1]),
                    "t_s": float(np.max(times[rr])),
                    "source": "RADAR_X_SHADOW_CFAR",
                    "threshold_excess_db": float(10 * np.log10(np.max(weight) / max(1e-9, np.mean(threshold[rr, cc])))),
                    "cell_count": int(len(rr)),
                    "target_hint": None,
                }
            )
            if len(detections) >= limit:
                break
        return detections, count
