"""Private, bounded AISStream recording; credentials never enter capture evidence.

Run ``python -m colav_simulator.aisstream_capture --help`` for the local recorder.
The recorder's UTC reception time is the replay clock, not AIS's seconds field.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import os
import random
import subprocess
import time
from collections import Counter
from datetime import datetime, timezone
from getpass import getpass
from pathlib import Path
from typing import Any

from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, InvalidHandshake

ENDPOINT = "wss://stream.aisstream.io/v0/stream"
MESSAGE_TYPES = (
    "PositionReport",
    "StandardClassBPositionReport",
    "ExtendedClassBPositionReport",
    "ShipStaticData",
    "StaticDataReport",
)
# User-selected red chart frame: S-57 cell CN436123 (Qingdao Port).
# WGS84 west/south/east/north from M_COVR; not a navigable-water polygon.
JIAOZHOU_BBOX = (120.175, 35.92, 120.5541667, 36.1333333)


def utc_now() -> str:
    """Return an absolute UTC recorder timestamp."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def subscription(api_key: str, bbox: tuple[float, float, float, float]) -> dict[str, Any]:
    """Accept WGS84 west/south/east/north; serialize AISStream lat/lon corners."""
    west, south, east, north = bbox
    if not all(math.isfinite(value) for value in bbox) or not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise ValueError("bbox must be finite west,south,east,north WGS84 bounds")
    if not api_key or not api_key.strip():
        raise ValueError("AISStream key is required")
    return {
        "APIKey": api_key,
        "BoundingBoxes": [[[south, west], [north, east]]],
        "FilterMessageTypes": list(MESSAGE_TYPES),
    }


def _private_json(path: Path, value: Any) -> None:
    with path.open("w", encoding="utf-8") as stream:
        os.chmod(path, 0o600)
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


async def record(  # noqa: C901, PLR0912, PLR0915
    output: Path,
    *,
    api_key: str,
    duration_s: float,
    bbox: tuple[float, float, float, float] = JIAOZHOU_BBOX,
) -> dict[str, Any]:
    """Record a new directory, preserving raw frames and connection evidence.

    Cancellation seals an INTERRUPTED capture. No source message is backfilled;
    reconnection intervals remain explicit in events.jsonl. Authentication or
    subscription errors stop the capture instead of repeatedly sending a key.
    """
    request = subscription(api_key, bbox)
    if not math.isfinite(duration_s) or duration_s <= 0:
        raise ValueError("duration_s must be finite and positive")
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    started = utc_now()
    deadline = time.monotonic() + duration_s
    counts: Counter[str] = Counter()
    sequence, connections, retries = 0, 0, 0
    raw_stream, current_hour = None, None
    events = (output / "events.jsonl").open("x", encoding="utf-8", buffering=1)
    os.chmod(output / "events.jsonl", 0o600)
    state = "RECORDING"
    manifest: dict[str, Any] = {
        "schema_version": "aisstream-capture.v1",
        "provider": "AISStream",
        "endpoint": ENDPOINT,
        "bbox_wgs84": list(bbox),
        "bbox_axis_order": "west_south_east_north",
        "message_types": list(MESSAGE_TYPES),
        "started_at_utc": started,
        "requested_duration_s": duration_s,
        "timestamp_basis": "recorder_received_at_utc",
        "coverage_exhaustive": False,
        "state": state,
    }
    _private_json(output / "manifest.json", manifest)

    def event(kind: str, **details: Any) -> None:
        events.write(json.dumps({"at_utc": utc_now(), "event": kind, **details}) + "\n")

    event("capture_started")
    try:
        while time.monotonic() < deadline:
            try:
                async with asyncio.timeout(max(0.001, deadline - time.monotonic())):
                    async with connect(
                        ENDPOINT,
                        compression="deflate",
                        open_timeout=15,
                        close_timeout=3,
                        ping_interval=20,
                        ping_timeout=20,
                        max_size=2**20,
                    ) as socket:
                        connections += 1
                        event("connected", connection=connections)
                        await socket.send(json.dumps(request))
                        event("subscription_sent", connection=connections)
                        while True:
                            frame = await socket.recv()
                            # Service errors can echo a subscription. Redact before
                            # parsing or persisting, including unexpected envelopes.
                            raw = (frame.decode("utf-8") if isinstance(frame, bytes) else frame).replace(
                                api_key, "[REDACTED]"
                            )
                            received_at = utc_now()
                            try:
                                message = json.loads(raw)
                            except (ValueError, TypeError):
                                event("invalid_json", connection=connections)
                                continue
                            if not isinstance(message, dict):
                                event("invalid_envelope", connection=connections)
                                continue
                            if "error" in message or "Error" in message:
                                event("subscription_rejected", connection=connections)
                                state = "REJECTED"
                                return manifest
                            kind = str(message.get("MessageType", "UNKNOWN"))
                            if kind == "SubscriptionConfirmation":
                                compression = message.get("Message", {}).get("CompressionEnabled")
                                event("subscription_confirmed", connection=connections, compression_enabled=compression)
                            hour = received_at[:13].replace(":", "-")
                            if hour != current_hour:
                                if raw_stream is not None:
                                    raw_stream.close()
                                raw_path = output / f"raw-{hour}.jsonl"
                                raw_stream = raw_path.open("a", encoding="utf-8", buffering=1)
                                os.chmod(raw_path, 0o600)
                                current_hour = hour
                            sequence += 1
                            counts[kind] += 1
                            envelope = {
                                "sequence": sequence,
                                "connection": connections,
                                "received_at_utc": received_at,
                                "raw_json": raw,
                            }
                            raw_stream.write(json.dumps(envelope, ensure_ascii=False) + "\n")
                            retries = 0
            except TimeoutError:
                if time.monotonic() >= deadline:
                    break
                event("connection_failed", error_type="TimeoutError")
            except (OSError, ConnectionClosed, InvalidHandshake, UnicodeError) as exc:
                # Exception text can carry arbitrary server content; retain type only.
                event("disconnected", connection=connections, error_type=type(exc).__name__)
            remaining = deadline - time.monotonic()
            if remaining > 0:
                retries += 1
                backoff = min(60.0, 2 ** min(retries, 6)) * random.uniform(0.8, 1.2)
                event("reconnect_wait", seconds=min(backoff, remaining))
                await asyncio.sleep(min(backoff, remaining))
        state = "COMPLETED"
    except asyncio.CancelledError:
        state = "INTERRUPTED"
        raise
    except BaseException:
        state = "FAILED"
        raise
    finally:
        if raw_stream is not None:
            raw_stream.close()
        event("capture_stopped", state=state)
        events.close()
        files = []
        for path in sorted(output.glob("*.jsonl")):
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
            files.append({"name": path.name, "bytes": path.stat().st_size, "sha256": digest.hexdigest()})
        manifest.update(
            state=state,
            ended_at_utc=utc_now(),
            messages=sequence,
            message_counts=dict(counts),
            connections=connections,
            files=files,
        )
        _private_json(output / "manifest.json", manifest)
    return manifest


def read_key(*, native_prompt: bool = False) -> str:
    """Read one secret into process memory, without shell arguments or files."""
    if native_prompt:
        script = (
            'text returned of (display dialog "请输入 AISStream API Key。仅用于后端录制；'
            '不会写入日志、场景或数据文件。" default answer "" with hidden answer '
            'buttons {"取消", "开始录制"} default button "开始录制" with title "AISStream · 胶州湾")'
        )
        result = subprocess.run(["/usr/bin/osascript", "-e", script], capture_output=True, text=True, check=False)
        if result.returncode:
            raise ValueError("Key input cancelled")
        return result.stdout.strip()
    return os.environ.get("AISSTREAM_API_KEY", "").strip() or getpass("AISStream API key: ").strip()


def main() -> None:
    """Run the private recorder from the command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New private capture directory")
    parser.add_argument("--duration", type=float, default=1800, help="Recording duration in seconds")
    parser.add_argument("--bbox", type=float, nargs=4, default=JIAOZHOU_BBOX, metavar=("W", "S", "E", "N"))
    parser.add_argument("--prompt-key", action="store_true", help="Use a native macOS hidden-input dialog")
    args = parser.parse_args()
    key = read_key(native_prompt=args.prompt_key)
    result = asyncio.run(record(args.output, api_key=key, duration_s=args.duration, bbox=tuple(args.bbox)))
    print(json.dumps({"output": str(args.output.resolve()), **result}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
