"""Recorder transport, privacy and interrupted-evidence contracts."""

import asyncio
import hashlib
import json

import pytest

from colav_simulator import aisstream_capture as capture


def test_subscription_uses_latitude_first_and_all_ship_classes():
    document = capture.subscription("secret", (120.05, 35.9, 120.5, 36.35))
    assert document["BoundingBoxes"] == [[[35.9, 120.05], [36.35, 120.5]]]
    assert "FiltersShipMMSI" not in document
    assert set(document["FilterMessageTypes"]) >= {
        "PositionReport",
        "StandardClassBPositionReport",
        "ExtendedClassBPositionReport",
        "ShipStaticData",
        "StaticDataReport",
    }


@pytest.mark.parametrize("bbox", [(120, 36, 119, 37), (120, 36, 121, 95), (120, 36, float("nan"), 37)])
def test_invalid_bounds_fail_before_output(bbox, tmp_path):
    with pytest.raises(ValueError, match="bbox"):
        asyncio.run(capture.record(tmp_path / "invalid", api_key="secret", duration_s=1, bbox=bbox))
    assert not (tmp_path / "invalid").exists()


class FakeSocket:
    def __init__(self, messages):
        self.messages = iter(messages)
        self.requests = []

    async def __aenter__(self) -> "FakeSocket":
        """Enter the fake transport."""
        return self

    async def __aexit__(self, *args) -> bool:
        """Preserve cancellation and errors."""
        return False

    async def send(self, message):
        self.requests.append(json.loads(message))

    async def recv(self) -> bytes:
        message = next(self.messages, None)
        if message is None:
            await asyncio.Future()
        return json.dumps(message).encode()


def test_record_seals_binary_frames_compression_and_hashes(tmp_path, monkeypatch):
    socket = FakeSocket(
        [
            {"MessageType": "SubscriptionConfirmation", "Message": {"CompressionEnabled": True}},
            {"MessageType": "PositionReport", "Message": {"PositionReport": {"UserID": 123456789}}},
        ]
    )
    options = {}

    def connect(endpoint, **kwargs) -> FakeSocket:
        assert endpoint == capture.ENDPOINT
        options.update(kwargs)
        return socket

    monkeypatch.setattr(capture, "connect", connect)
    output = tmp_path / "capture"
    result = asyncio.run(capture.record(output, api_key="private-key", duration_s=0.03))
    assert result["state"] == "COMPLETED"
    assert result["messages"] == 2
    assert result["coverage_exhaustive"] is False
    assert options["compression"] == "deflate"
    assert socket.requests[0]["APIKey"] == "private-key"
    for item in result["files"]:
        path = output / item["name"]
        assert item["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
        assert "private-key" not in path.read_text()
        assert path.stat().st_mode & 0o077 == 0
    raw = [json.loads(line) for path in output.glob("raw-*.jsonl") for line in path.read_text().splitlines()]
    assert [row["sequence"] for row in raw] == [1, 2]
    assert all(row["received_at_utc"].endswith("Z") for row in raw)
    assert json.loads((output / "manifest.json").read_text()) == result
    assert "subscription_confirmed" in (output / "events.jsonl").read_text()


def test_rejection_never_persists_echoed_secret_or_retries(tmp_path, monkeypatch):
    monkeypatch.setattr(capture, "connect", lambda *args, **kwargs: FakeSocket([{"error": "bad private-key"}]))
    output = tmp_path / "rejected"
    result = asyncio.run(capture.record(output, api_key="private-key", duration_s=10))
    assert result["state"] == "REJECTED"
    assert result["connections"] == 1
    assert all("private-key" not in path.read_text() for path in output.iterdir())


def test_cancellation_seals_interrupted_evidence(tmp_path, monkeypatch):
    monkeypatch.setattr(capture, "connect", lambda *args, **kwargs: FakeSocket([]))
    output = tmp_path / "interrupted"

    async def cancel():
        task = asyncio.create_task(capture.record(output, api_key="key", duration_s=30))
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(cancel())
    assert json.loads((output / "manifest.json").read_text())["state"] == "INTERRUPTED"


def test_connection_failure_has_bounded_retry_and_no_exception_secret(tmp_path, monkeypatch):
    def fail(*args, **kwargs):
        raise OSError("private-key must not appear in artifacts")

    monkeypatch.setattr(capture, "connect", fail)
    output = tmp_path / "failure"
    result = asyncio.run(capture.record(output, api_key="private-key", duration_s=0.02))
    assert result["messages"] == 0
    events = (output / "events.jsonl").read_text()
    assert "disconnected" in events and "reconnect_wait" in events
    assert "private-key" not in events


def test_existing_capture_never_overwritten(tmp_path):
    with pytest.raises(FileExistsError):
        asyncio.run(capture.record(tmp_path, api_key="key", duration_s=1))
