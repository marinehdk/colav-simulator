"""Immutable radar evidence. No truth identities or simulation runtime imports."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class RadarReturn:
    """One observed position, shared with the legacy tracker measurement."""

    north_m: float
    east_m: float
    t_s: float
    snr_db: float | None
    confidence: float
    covariance_ne_m2: tuple[tuple[float, float], tuple[float, float]]


@dataclass(frozen=True)
class RadarScanPacket:
    """One sampling interval; revolution_seq and sample_seq are separate clocks."""

    sensor_instance_id: str
    sample_seq: int
    revolution_seq: int
    t_start_s: float
    t_s: float
    ownship_ne_m: tuple[float, float]
    yaw_rad: float
    descriptor_json: str
    returns: tuple[RadarReturn, ...]
    display_returns: tuple[RadarReturn, ...]
    status: str = "VALID"

    def to_dict(self) -> dict:
        """Create an independent, JSON-safe public projection with a content hash."""
        document = asdict(self)
        document["schema_version"] = "radar-scan@1"
        document["sensor_id"] = 1
        document["sensor_label"] = "radar_x"
        document["frame_id"] = "absolute_ne"
        document["source"] = "RADAR_X"
        document["measurement_mode"] = "legacy_points"
        document["descriptor"] = json.loads(document.pop("descriptor_json"))
        encoded = json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        document["packet_hash"] = hashlib.sha256(encoded).hexdigest()
        return document
