"""Offline radar evidence validation and bias estimation, never runtime tuning."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from colav_simulator.core.radar_video import decode_video


def inspect_recording(path: Path) -> dict:
    """Read normalized spoke JSONL and verify bytes before reporting evidence."""
    digest = hashlib.sha256()
    count = byte_count = 0
    previous = -1.0
    first = last = None
    with path.open("rb") as handle:
        first_line = handle.readline()
        digest.update(first_line)
        manifest = json.loads(first_line)
        if manifest.get("schema_version") != "radar-calibration-input@1":
            raise ValueError("normalized radar recording manifest required")
        if manifest.get("source_kind") not in {"measured", "synthetic"}:
            raise ValueError("recording must declare measured or synthetic source")
        if not manifest.get("provenance"):
            raise ValueError("recording provenance required")
        for raw in handle:
            digest.update(raw)
            record = json.loads(raw)
            t = float(record["t_s"])
            if not np.isfinite(t) or t <= previous:
                raise ValueError("radar recording time must increase")
            video = record["shadow_video"]
            for key in ("chunk", "checkpoint"):
                byte_count += decode_video(video[key]).nbytes
            count += 1
            first = t if first is None else first
            last = previous = t
    if not count:
        raise ValueError("empty radar recording")
    return {
        "schema_version": "radar-calibration-report@1",
        "source_kind": manifest["source_kind"],
        "profile_id": manifest.get("profile_id"),
        "provenance": manifest["provenance"],
        "recording_sha256": digest.hexdigest(),
        "records": count,
        "verified_video_bytes": byte_count,
        "t_start_s": first,
        "t_end_s": last,
        "calibration_status": "MEASURED_DATA_REVIEW_REQUIRED"
        if manifest["source_kind"] == "measured"
        else "SYNTHETIC_ONLY_REAL_CALIBRATION_PENDING",
    }


def estimate_bias(pairs: list[dict], *, source_kind: str, provenance: dict) -> dict:
    """Estimate corrections from externally paired observations and references.

    Reference associations are audit annotations, never radar target identities.
    A declared measured file is not automatically qualified ground truth.
    """
    if source_kind not in {"measured", "synthetic"} or not provenance or len(pairs) < 5:
        raise ValueError("at least five paired references and explicit provenance are required")
    data = np.array(
        [[p[key] for key in ("range_m", "bearing_deg", "reference_range_m", "reference_bearing_deg")] for p in pairs],
        dtype=float,
    )
    if not np.isfinite(data).all() or np.any(data[:, (0, 2)] < 0):
        raise ValueError("finite, non-negative reference ranges required")
    errors_r = data[:, 0] - data[:, 2]
    errors_b = (data[:, 1] - data[:, 3] + 180) % 360 - 180
    bearing_bias = np.degrees(np.arctan2(np.mean(np.sin(np.radians(errors_b))), np.mean(np.cos(np.radians(errors_b)))))
    range_bias = float(np.mean(errors_r))
    corrected_b = (errors_b - bearing_bias + 180) % 360 - 180
    return {
        "schema_version": "radar-bias-estimate@1",
        "source_kind": source_kind,
        "provenance": provenance,
        "pairs": len(pairs),
        "range_bias_m": range_bias,
        "bearing_bias_deg": float(bearing_bias),
        "range_rmse_m": float(np.sqrt(np.mean(errors_r**2))),
        "bearing_rmse_deg": float(np.sqrt(np.mean(errors_b**2))),
        "corrected_range_rmse_m": float(np.sqrt(np.mean((errors_r - range_bias) ** 2))),
        "corrected_bearing_rmse_deg": float(np.sqrt(np.mean(corrected_b**2))),
        "runtime_applied": False,
        "calibration_status": "MEASURED_DATA_REVIEW_REQUIRED"
        if source_kind == "measured"
        else "SYNTHETIC_ONLY_REAL_CALIBRATION_PENDING",
    }
