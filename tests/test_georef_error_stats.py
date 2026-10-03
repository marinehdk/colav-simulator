"""P2-2 review-fix: georef numeric error artifact (spec #90, PLAN §2 P3-S2 row).

The S2 acceptance carried the anchor "georef 误差 <= 船长级（~45 m）存证" without a
numeric artifact. This test produces it: a known ground-truth target (absolute
NE) + ownship pose + the mount intrinsics are forward-projected into a synthetic
pixel box (the exact inverse of ``georeference_box``'s pinhole model), the box is
quantized to 1 px (YOLO's pixel precision — the honest error source of the pure
function chain), georeferenced back, and the position error statistics over
multiple distances / bearings / ownship yaws are written to
``output/sango-twin-s2/georef-error-stats.json`` (README-documented).

Pure function layer — no live rig required. The assertions pin sanity
properties (finite errors, error growth with range, the ship-length anchor
within the YOLO-detectable envelope), not the raw 2 nm tail where a 2.5 m
target is sub-pixel and the box-height ranging is information-starved by
design (the artifact records that tail honestly).
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import pytest

from colav_simulator.core.mast_cameras import (
    CLASS_HEIGHT_PRIOR_M,
    FEED_HEIGHT_PX,
    FEED_MOUNT_ID,
    FEED_WIDTH_PX,
    MAST_MOUNTS_BY_ID,
    focal_px,
    georeference_box,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
ARTIFACT_PATH = REPO_ROOT / "output" / "sango-twin-s2" / "georef-error-stats.json"

#: Multi-distance / multi-bearing / multi-yaw sample grid (contract §5 georef domain).
DISTANCES_M = [20.0, 50.0, 100.0, 150.0, 200.0, 300.0, 500.0, 800.0, 1200.0, 1852.0, 3704.0]
BEARING_OFFSETS_DEG = [-25.0, -15.0, -10.0, 0.0, 10.0, 15.0, 25.0]  # within the 60 deg HFOV
OWN_YAW_DEG = [0.0, 90.0, 180.0]
TARGET_HEIGHT_M = CLASS_HEIGHT_PRIOR_M["boat"]  # 2.5 m COCO boat prior (georef default)
DETECTABLE_MIN_BOX_HEIGHT_PX = 4.0  # YOLO does not emit boxes below a few px


def project_box(mount, range_m: float, bearing_offset_deg: float, yaw_rad: float) -> tuple[float, float, float, float]:
    """Forward-project a known target into the georef pixel domain (exact inverse).

    Mirrors ``georeference_box``: bearing from the box centre column through the
    pinhole model, range from the box pixel height against the height prior.
    """
    fx = focal_px(mount.hfov_deg, mount.frame_width_px)
    u_center = mount.frame_width_px / 2.0 + fx * math.tan(math.radians(bearing_offset_deg))
    box_height_px = fx * TARGET_HEIGHT_M / range_m
    half_width = 2.0  # box width is irrelevant to the model (centre column only)
    return (
        u_center - half_width,
        mount.frame_height_px - box_height_px,
        u_center + half_width,
        float(mount.frame_height_px),
    )


def _quantize(box: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    """1 px quantization — YOLO boxes land on the sensor raster grid."""
    return tuple(float(round(value)) for value in box)  # type: ignore[return-value]


def _sample_grid() -> list[dict]:
    mount = MAST_MOUNTS_BY_ID[FEED_MOUNT_ID]
    fx = focal_px(mount.hfov_deg, mount.frame_width_px)
    samples = []
    for distance_m in DISTANCES_M:
        for bearing_offset_deg in BEARING_OFFSETS_DEG:
            for yaw_deg in OWN_YAW_DEG:
                yaw_rad = math.radians(yaw_deg)
                box = _quantize(project_box(mount, distance_m, bearing_offset_deg, yaw_rad))
                georef = georeference_box(
                    mount,
                    box,
                    mount.frame_width_px,
                    mount.frame_height_px,
                    own_north=0.0,
                    own_east=0.0,
                    own_yaw_rad=yaw_rad,
                    target_height_m=TARGET_HEIGHT_M,
                )
                bearing = yaw_rad + math.radians(mount.azimuth_deg + bearing_offset_deg)
                truth_north = distance_m * math.cos(bearing)
                truth_east = distance_m * math.sin(bearing)
                error_m = math.hypot(georef.north_m - truth_north, georef.east_m - truth_east)
                samples.append(
                    {
                        "distance_m": distance_m,
                        "bearing_offset_deg": bearing_offset_deg,
                        "own_yaw_deg": yaw_deg,
                        "box_height_px": fx * TARGET_HEIGHT_M / distance_m,
                        "error_m": error_m,
                    }
                )
    return samples


def _distance_stats(samples: list[dict], distance_m: float) -> dict:
    rows = [row for row in samples if row["distance_m"] == distance_m]
    errors = [row["error_m"] for row in rows]
    worst = max(rows, key=lambda row: row["error_m"])
    return {
        "distance_m": distance_m,
        "mean_box_height_px": round(sum(row["box_height_px"] for row in rows) / len(rows), 3),
        "mean_error_m": round(sum(errors) / len(errors), 3),
        "rms_error_m": round(math.sqrt(sum(error**2 for error in errors) / len(errors)), 3),
        "max_error_m": round(max(errors), 3),
        "max_error_at": {"bearing_offset_deg": worst["bearing_offset_deg"], "own_yaw_deg": worst["own_yaw_deg"]},
    }


def test_georef_error_stats_artifact() -> None:
    samples = _sample_grid()
    assert all(math.isfinite(row["error_m"]) for row in samples), "georef back-projection stays finite"

    per_distance = [_distance_stats(samples, distance_m) for distance_m in DISTANCES_M]
    errors = [row["error_m"] for row in samples]
    detectable = [row for row in samples if row["box_height_px"] >= DETECTABLE_MIN_BOX_HEIGHT_PX]
    assert detectable, "the sample grid must cover the YOLO-detectable envelope"
    detectable_max = max(row["error_m"] for row in detectable)

    artifact = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mount_id": FEED_MOUNT_ID,
        "frame": {"width_px": FEED_WIDTH_PX, "height_px": FEED_HEIGHT_PX},
        "target_height_prior_m": TARGET_HEIGHT_M,
        "error_model": (
            "known truth forward-projected through the georef pinhole inverse, "
            "box quantized to 1 px (YOLO raster precision), georeferenced back; "
            "error = ||georef NE - truth NE||"
        ),
        "grid": {
            "distances_m": DISTANCES_M,
            "bearing_offsets_deg": BEARING_OFFSETS_DEG,
            "own_yaw_deg": OWN_YAW_DEG,
            "samples": len(samples),
        },
        "per_distance": per_distance,
        "yolo_detectable_envelope": {
            "min_box_height_px": DETECTABLE_MIN_BOX_HEIGHT_PX,
            "max_distance_m": max(row["distance_m"] for row in detectable),
            "max_error_m": round(detectable_max, 3),
        },
        "overall": {
            "max_error_m": round(max(errors), 3),
            "rms_error_m": round(math.sqrt(sum(error**2 for error in errors) / len(errors)), 3),
        },
        "plan_r2_anchor": (
            "S2 acceptance anchor: georef error <= ship length (~45 m). Holds within "
            "the YOLO-detectable envelope (boxes >= 4 px tall); beyond it a 2.5 m "
            "target is sub-pixel and the box-height ranging is information-starved "
            "(the raw tail is recorded honestly above)."
        ),
    }
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")

    # Sanity pins (not the raw 2 nm tail — see plan_r2_anchor).
    assert detectable_max <= 45.0, (
        f"ship-length anchor broken inside the YOLO-detectable envelope: {detectable_max:.1f} m"
    )
    near = next(row for row in per_distance if row["distance_m"] == 200.0)
    far = next(row for row in per_distance if row["distance_m"] == 1852.0)
    assert far["rms_error_m"] > near["rms_error_m"], "pixel-quantization error must grow with range"
    tail = next(row for row in per_distance if row["distance_m"] == 3704.0)
    assert tail["max_error_m"] > 1000.0, "sub-pixel tail stays honest (2.5 m target at 2 nm)"
    assert ARTIFACT_PATH.is_file()
    assert json.loads(ARTIFACT_PATH.read_text(encoding="utf-8"))["grid"]["samples"] == len(samples)


@pytest.mark.parametrize(
    "distance_m", [50.0, 200.0], ids=["close", "mid"]
)
def test_georef_back_projection_consistency_small_at_detectable_ranges(distance_m: float) -> None:
    """No-quantization inversion is exact at in-envelope ranges (model sanity)."""
    mount = MAST_MOUNTS_BY_ID[FEED_MOUNT_ID]
    box = project_box(mount, distance_m, 12.0, math.radians(30.0))
    georef = georeference_box(
        mount,
        box,
        mount.frame_width_px,
        mount.frame_height_px,
        own_north=0.0,
        own_east=0.0,
        own_yaw_rad=math.radians(30.0),
        target_height_m=TARGET_HEIGHT_M,
    )
    bearing = math.radians(30.0 + mount.azimuth_deg + 12.0)
    assert math.hypot(georef.north_m - distance_m * math.cos(bearing), georef.east_m - distance_m * math.sin(bearing)) < 1e-6
