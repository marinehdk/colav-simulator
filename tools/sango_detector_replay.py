#!/usr/bin/env python3
"""M9 frame-source stand-in (detection-return-v1.md §6) — 无 Unity 联调用.

Replays one JPEG as a FramePublisher-shaped stream so the detector service can
be exercised end to end without Unity. Binds the PUB endpoint FramePublisher
would own (default tcp://127.0.0.1:5556) and emits 3-part multipart messages:

    part 1  topic   "sango.frame"
    part 2  JSON    FrameMetadata {frame_seq, frame_time_s, width, height, jpeg_bytes, source}
    part 3  bytes   the JPEG, verbatim

width/height/jpeg_bytes come from the actual file (SOF marker parse); frame_seq
counts from 0; frame_time_s is monotonic seconds since replay start — NOT Unity
Time.timeAsDouble, so Unity-consumer freshness gating (age ≤ 0.5s, same clock
domain) does not apply to this source. Python-side pipeline bring-up only.

互斥：与 FramePublisher 抢同一端点 bind，二者不可同时跑。

Usage:
    .venv-detector/bin/python tools/sango_detector_replay.py --image /tmp/frame.jpg --count 10
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import zmq


def jpeg_dimensions(data: bytes) -> tuple[int, int]:
    """从 SOF 段解析宽高（0xFFC0-CF，跳过 DHT=0xC4 / JPG=0xC8 / DAC=0xCC）。"""
    if not data.startswith(b"\xff\xd8"):
        raise ValueError("not a JPEG (SOI 0xFFD8 missing)")
    i = 2
    while i + 9 < len(data):
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker == 0x01 or 0xD0 <= marker <= 0xD9:  # 独立标记，无长度域
            i += 2
            continue
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            height = int.from_bytes(data[i + 5:i + 7], "big")
            width = int.from_bytes(data[i + 7:i + 9], "big")
            return width, height
        seg_len = int.from_bytes(data[i + 2:i + 4], "big")  # 跳过非 SOF 段
        i += 2 + seg_len
    raise ValueError("SOF marker not found (truncated or unsupported JPEG)")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Replay a JPEG on the FramePublisher endpoint (PUB bind).")
    p.add_argument("--image", required=True, help="JPEG file to replay")
    p.add_argument("--fps", type=float, default=5.0, help="send rate (default 5 fps)")
    p.add_argument("--count", type=int, default=0, help="frames to send before exit; 0 = until Ctrl-C")
    p.add_argument("--endpoint", default="tcp://127.0.0.1:5556", help="PUB bind address")
    p.add_argument("--topic", default="sango.frame", help="topic (part 1)")
    p.add_argument("--source", default="replay", help="FrameMetadata.source identifier")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if args.fps <= 0:
        print("[replay] FAIL: --fps must be > 0")
        return 1
    jpeg = Path(args.image).read_bytes()
    width, height = jpeg_dimensions(jpeg)

    ctx = zmq.Context()
    pub = ctx.socket(zmq.PUB)
    pub.setsockopt(zmq.SNDHWM, 30)
    pub.bind(args.endpoint)
    print(f"[replay] PUB bound {args.endpoint} (topic {args.topic}); image {width}x{height} "
          f"{len(jpeg)}B; fps={args.fps} count={args.count if args.count > 0 else 'until Ctrl-C'}")
    time.sleep(0.5)  # PUB 慢加入语义：给服务端 SUB 留出 connect 窗口，首帧不白发

    interval = 1.0 / args.fps
    seq = 0
    t0 = time.monotonic()
    next_t = t0
    try:
        while args.count <= 0 or seq < args.count:
            frame_time_s = time.monotonic() - t0
            meta = {
                "frame_seq": seq,
                "frame_time_s": round(frame_time_s, 3),
                "width": width,
                "height": height,
                "jpeg_bytes": len(jpeg),
                "source": args.source,
            }
            pub.send_multipart([
                args.topic.encode("utf-8"),
                json.dumps(meta, separators=(",", ":")).encode("utf-8"),
                jpeg,
            ])
            print(f"[replay] frame seq={seq} {width}x{height} {len(jpeg)}B t={frame_time_s:.3f}s")
            seq += 1
            next_t += interval
            sleep = next_t - time.monotonic()
            if sleep > 0:
                time.sleep(sleep)
            else:
                next_t = time.monotonic()  # 已落后节奏则重锚定，不突发追赶
    except KeyboardInterrupt:
        pass
    finally:
        pub.close(0)
        ctx.term()
    print(f"[replay] OK: sent {seq} frames in {time.monotonic() - t0:.1f}s at {args.fps} fps")
    return 0


if __name__ == "__main__":
    sys.exit(main())
