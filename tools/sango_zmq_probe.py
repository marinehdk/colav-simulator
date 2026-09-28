#!/usr/bin/env python3
"""M3 acceptance probe (spec #86 / PHASE1-PLAN §5 M3 验收 2).

Subscribes to the Sango FramePublisher (ZeroMQ PUB, default tcp://127.0.0.1:5556)
and counts received frames. Each frame is a 3-part multipart message:

    part 1  topic   "sango.frame"
    part 2  JSON    FrameMetadata {frame_seq, frame_time_s, width, height, jpeg_bytes, source}
    part 3  bytes   JPEG image (must start with SOI 0xFFD8 and match jpeg_bytes)

Exit 0 once --count valid frames are received, 1 on timeout or protocol violation.

Usage (publisher must be enabled first — see sango/Docs/contracts/frame-publisher-v1.md):
    python3 tools/sango_zmq_probe.py --count 30
"""

from __future__ import annotations

import argparse
import json
import sys
import time

import zmq

TOPIC = b"sango.frame"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Subscribe to Sango FramePublisher and count valid JPEG frames.")
    p.add_argument("--count", type=int, default=30, help="number of frames to accept before success (default 30)")
    p.add_argument("--endpoint", default="tcp://127.0.0.1:5556", help="publisher endpoint to connect (PUB bind address)")
    p.add_argument("--timeout", type=float, default=120.0, help="seconds to wait for the full count before failing")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    ctx = zmq.Context()
    sub = ctx.socket(zmq.SUB)
    sub.setsockopt(zmq.SUBSCRIBE, TOPIC)
    sub.setsockopt(zmq.RCVTIMEO, 2000)  # short ticks so the deadline stays enforceable
    sub.connect(args.endpoint)
    print(f"[probe] SUB connected to {args.endpoint}, expecting {args.count} frames on topic {TOPIC.decode()}")

    seen: set[int] = set()
    last_meta: dict | None = None
    started = time.monotonic()
    try:
        while len(seen) < args.count:
            if time.monotonic() - started > args.timeout:
                print(f"[probe] FAIL: timeout after {args.timeout:.0f}s with {len(seen)}/{args.count} frames")
                return 1
            try:
                parts = sub.recv_multipart()
            except zmq.Again:
                continue
            if len(parts) != 3:
                print(f"[probe] FAIL: expected 3-part message, got {len(parts)} part(s)")
                return 1
            topic, meta_raw, jpeg = parts
            if topic != TOPIC:
                print(f"[probe] FAIL: unexpected topic {topic!r}")
                return 1
            try:
                meta = json.loads(meta_raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as e:
                print(f"[probe] FAIL: metadata JSON parse error: {e}")
                return 1
            for key in ("frame_seq", "frame_time_s", "width", "height", "jpeg_bytes", "source"):
                if key not in meta:
                    print(f"[probe] FAIL: metadata missing key {key!r}: {meta}")
                    return 1
            if not jpeg.startswith(b"\xff\xd8"):
                print(f"[probe] FAIL: part 3 is not JPEG (SOI 0xFFD8 missing), first bytes {jpeg[:4].hex()}")
                return 1
            if len(jpeg) != meta["jpeg_bytes"]:
                print(f"[probe] FAIL: jpeg_bytes={meta['jpeg_bytes']} but received {len(jpeg)} bytes")
                return 1
            seq = int(meta["frame_seq"])
            seen.add(seq)
            last_meta = meta
            print(
                f"[probe] frame {len(seen):3d}/{args.count} seq={seq} "
                f"{meta['width']}x{meta['height']} jpeg={len(jpeg)}B t={meta['frame_time_s']:.2f}s"
            )
    except KeyboardInterrupt:
        print("[probe] FAIL: interrupted")
        return 1
    finally:
        sub.close(0)
        ctx.term()

    if last_meta is not None:
        print(
            f"[probe] OK: received {len(seen)} valid frames "
            f"(last seq={last_meta['frame_seq']}, source={last_meta['source']}) in {time.monotonic() - started:.1f}s"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
