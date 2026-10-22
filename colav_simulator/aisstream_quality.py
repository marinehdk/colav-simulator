"""Auditable coverage statistics for a sealed AISStream recording.

These statistics qualify data availability, never collision-avoidance safety.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from shapely.geometry import Point, shape

POSITION_TYPES = {"PositionReport", "StandardClassBPositionReport", "ExtendedClassBPositionReport"}


def file_digest(path: Path) -> str:
    """Hash a capture without loading an entire recording into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _timestamp(value: str) -> datetime:
    timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if timestamp.tzinfo is None:
        raise ValueError("capture timestamps require a UTC offset")
    return timestamp


def _number(value: Any, minimum: float, maximum: float) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and minimum <= number <= maximum else None


def summarize_capture(directory: Path, *, coverage_path: Path | None = None) -> dict[str, Any]:  # noqa: C901, PLR0912, PLR0915
    """Verify sealed evidence and report position continuity inside chart coverage."""
    manifest = json.loads((directory / "manifest.json").read_text())
    if manifest.get("schema_version") != "aisstream-capture.v1" or manifest.get("state") == "RECORDING":
        raise ValueError("a sealed aisstream-capture.v1 recording is required")
    coverage = None
    if coverage_path is not None:
        document = json.loads(coverage_path.read_text())
        coverage = shape(document["geometry"] if document.get("type") == "Feature" else document)
        if coverage.is_empty or not coverage.is_valid:
            raise ValueError("chart coverage must be nonempty and valid")
    files = manifest.get("files", [])
    names = {item["name"] for item in files}
    if names != {path.name for path in directory.glob("*.jsonl")} or len(names) != len(files):
        raise ValueError("capture file inventory mismatch")
    for item in files:
        name = item["name"]
        if Path(name).name != name or name in {".", ".."}:
            raise ValueError("invalid capture filename")
        path = directory / name
        if path.stat().st_size != item["bytes"] or file_digest(path) != item["sha256"]:
            raise ValueError(f"capture content mismatch: {name}")
    events = [json.loads(line) for line in (directory / "events.jsonl").read_text().splitlines()]
    types: Counter[str] = Counter()
    findings: Counter[str] = Counter()
    vessels: dict[int, list[tuple[float, float | None]]] = defaultdict(list)
    outside_mmsi: set[int] = set()
    static_mmsi: set[int] = set()
    raw_hashes: set[str] = set()
    sequence = 0
    for path in sorted(directory.glob("raw-*.jsonl")):
        with path.open() as stream:
            for line in stream:
                envelope = json.loads(line)
                sequence += 1
                if envelope["sequence"] != sequence:
                    raise ValueError("capture record sequence is not contiguous")
                stamp = _timestamp(envelope["received_at_utc"]).timestamp()
                raw = envelope["raw_json"]
                digest = hashlib.sha256(raw.encode()).hexdigest()
                if digest in raw_hashes:
                    findings["duplicate_raw_frames"] += 1
                raw_hashes.add(digest)
                message = json.loads(raw)
                kind = str(message.get("MessageType", "UNKNOWN"))
                types[kind] += 1
                body = message.get("Message", {}).get(kind, {})
                mmsi = body.get("UserID", message.get("MetaData", {}).get("MMSI"))
                try:
                    mmsi = int(mmsi)
                except (ValueError, TypeError):
                    if kind != "SubscriptionConfirmation":
                        findings["invalid_mmsi"] += 1
                    continue
                if not 100000000 <= mmsi <= 999999999:
                    findings["invalid_mmsi"] += 1
                    continue
                if kind in {"ShipStaticData", "StaticDataReport"}:
                    static_mmsi.add(mmsi)
                if kind not in POSITION_TYPES:
                    continue
                lon = _number(body.get("Longitude"), -180, 180)
                lat = _number(body.get("Latitude"), -90, 90)
                if body.get("Valid") is not True or lon is None or lat is None:
                    findings["invalid_dynamic_position"] += 1
                    continue
                if coverage is not None and not coverage.covers(Point(lon, lat)):
                    findings["outside_chart_coverage"] += 1
                    outside_mmsi.add(mmsi)
                    continue
                speed = _number(body.get("Sog"), 0, 102.2)
                if speed is None:
                    findings["unavailable_sog"] += 1
                if _number(body.get("Cog"), 0, 359.999999) is None:
                    findings["unavailable_cog"] += 1
                vessels[mmsi].append((stamp, speed))
    if sequence != manifest["messages"] or dict(types) != manifest["message_counts"]:
        raise ValueError("capture message totals mismatch")
    summaries = []
    for mmsi, points in sorted(vessels.items()):
        timestamps = [point[0] for point in points]
        if timestamps != sorted(timestamps):
            findings["recorder_clock_reversal"] += 1
        timestamps = sorted(set(timestamps))
        gaps = sorted(b - a for a, b in zip(timestamps, timestamps[1:], strict=False))
        summaries.append(
            {
                "mmsi": mmsi,
                "positions": len(points),
                "span_s": timestamps[-1] - timestamps[0],
                "interval_p50_s": gaps[(len(gaps) - 1) // 2] if gaps else None,
                "interval_p95_s": gaps[max(0, math.ceil(len(gaps) * 0.95) - 1)] if gaps else None,
                "max_gap_s": max(gaps) if gaps else None,
                "gaps_over_300s": sum(gap > 300 for gap in gaps),
                "moving_observed": any(speed is not None and speed > 0.5 for _, speed in points),
                "static_message_received": mmsi in static_mmsi,
            }
        )
    status = "POSITIONS_RECEIVED" if vessels else "NO_USABLE_POSITIONS_IN_REGION"
    return {
        "schema_version": "aisstream-quality.v1",
        "capture": str(directory.resolve()),
        "capture_manifest_sha256": file_digest(directory / "manifest.json"),
        "integrity": "PASS",
        "capture_state": manifest["state"],
        "started_at_utc": manifest["started_at_utc"],
        "ended_at_utc": manifest["ended_at_utc"],
        "elapsed_s": (_timestamp(manifest["ended_at_utc"]) - _timestamp(manifest["started_at_utc"])).total_seconds(),
        "requested_duration_s": manifest["requested_duration_s"],
        "bbox_wgs84": manifest["bbox_wgs84"],
        "coverage_sha256": file_digest(coverage_path) if coverage_path else None,
        "timestamp_basis": manifest["timestamp_basis"],
        "subscription_confirmations": sum(event["event"] == "subscription_confirmed" for event in events),
        "compression_confirmed": any(event.get("compression_enabled") is True for event in events),
        "connection_failures": sum(event["event"] in {"disconnected", "connection_failed"} for event in events),
        "messages": sequence,
        "message_counts": dict(types),
        "data_status": status,
        "vessels_in_region": len(vessels),
        "moving_vessels_in_region": sum(vessel["moving_observed"] for vessel in summaries),
        "vessels_with_multiple_positions": sum(vessel["positions"] >= 2 for vessel in summaries),
        "vessels_outside_region": len(outside_mmsi),
        "vessels": summaries,
        "findings": dict(findings),
        "limitations": [
            "A short probe does not establish complete or long-term regional coverage.",
            "Replay clock is recorder reception time, not a guaranteed source observation timestamp.",
            "Moving means at least one reported SOG > 0.5 knots; it is a descriptive statistic.",
            "ENC coverage geometry does not establish navigability or current chart correctness.",
            "This report contains no algorithm execution or collision-avoidance acceptance evidence.",
        ],
    }


def main() -> None:
    """Write a JSON quality report without modifying the sealed capture."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("--coverage", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = summarize_capture(args.capture, coverage_path=args.coverage)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({key: result[key] for key in ("data_status", "messages", "vessels_in_region", "elapsed_s")}))


if __name__ == "__main__":
    main()
