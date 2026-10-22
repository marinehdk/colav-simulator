"""Coverage reports must distinguish empty transport from usable AIS tracks."""

import json
from pathlib import Path

import pytest

from colav_simulator.aisstream_quality import file_digest, summarize_capture


def sealed_capture(tmp_path, reports) -> Path:
    directory = tmp_path / "capture"
    directory.mkdir()
    raw = directory / "raw-2026-10-16T00.jsonl"
    rows = []
    counts = {}
    for index, (second, message) in enumerate(reports, 1):
        counts[message["MessageType"]] = counts.get(message["MessageType"], 0) + 1
        rows.append(
            json.dumps(
                {
                    "sequence": index,
                    "connection": 1,
                    "received_at_utc": f"2026-10-16T00:00:{second:02d}Z",
                    "raw_json": json.dumps(message),
                }
            )
        )
    raw.write_text("\n".join(rows) + ("\n" if rows else ""))
    events = directory / "events.jsonl"
    events.write_text(json.dumps({"event": "subscription_confirmed", "compression_enabled": True}) + "\n")
    manifest = {
        "schema_version": "aisstream-capture.v1",
        "state": "COMPLETED",
        "messages": len(rows),
        "message_counts": counts,
        "started_at_utc": "2026-10-16T00:00:00Z",
        "ended_at_utc": "2026-10-16T00:03:00Z",
        "requested_duration_s": 180,
        "bbox_wgs84": [120, 35, 121, 37],
        "timestamp_basis": "recorder_received_at_utc",
        "files": [{"name": path.name, "bytes": path.stat().st_size, "sha256": file_digest(path)} for path in (raw, events)],
    }
    (directory / "manifest.json").write_text(json.dumps(manifest))
    return directory


def position(kind="PositionReport", **overrides) -> dict:
    return {
        "MessageType": kind,
        "Message": {
            kind: {
                "Valid": True,
                "UserID": 123456789,
                "Longitude": 120.3,
                "Latitude": 36.0,
                "Sog": 5,
                "Cog": 45,
                **overrides,
            }
        },
    }


def test_no_positions_is_not_coverage_success(tmp_path):
    directory = sealed_capture(
        tmp_path, [(0, {"MessageType": "SubscriptionConfirmation", "Message": {"CompressionEnabled": True}})]
    )
    report = summarize_capture(directory)
    assert report["compression_confirmed"] is True
    assert report["data_status"] == "NO_USABLE_POSITIONS_IN_REGION"
    assert report["vessels_in_region"] == 0
    assert report["elapsed_s"] == 180


def test_class_b_continuity_and_unavailable_speed(tmp_path):
    directory = sealed_capture(
        tmp_path,
        [
            (1, position()),
            (11, position("StandardClassBPositionReport")),
            (41, position("ExtendedClassBPositionReport", Sog=102.3)),
        ],
    )
    report = summarize_capture(directory)
    assert report["vessels_in_region"] == 1
    assert report["vessels_with_multiple_positions"] == 1
    assert report["vessels"][0]["max_gap_s"] == 30
    assert report["vessels"][0]["interval_p50_s"] == 10
    assert report["findings"]["unavailable_sog"] == 1


def test_coverage_uses_report_coordinates_not_metadata(tmp_path):
    message = position(Longitude=121.0)
    message["MetaData"] = {"Longitude": 120.3, "Latitude": 36.0}
    directory = sealed_capture(tmp_path, [(1, message), (2, position(Valid=False))])
    coverage = tmp_path / "coverage.json"
    coverage.write_text(
        json.dumps({"type": "Polygon", "coordinates": [[[120, 35], [120.5, 35], [120.5, 37], [120, 37], [120, 35]]]})
    )
    report = summarize_capture(directory, coverage_path=coverage)
    assert report["vessels_in_region"] == 0
    assert report["findings"]["outside_chart_coverage"] == 1
    assert report["findings"]["invalid_dynamic_position"] == 1


def test_tampered_capture_rejected(tmp_path):
    directory = sealed_capture(tmp_path, [(1, position())])
    next(directory.glob("raw-*.jsonl")).write_text("{}\n")
    with pytest.raises(ValueError, match="content mismatch"):
        summarize_capture(directory)


def test_unsealed_recording_cannot_claim_quality(tmp_path):
    directory = sealed_capture(tmp_path, [])
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["state"] = "RECORDING"
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="sealed"):
        summarize_capture(directory)
