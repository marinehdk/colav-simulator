#!/usr/bin/env python3
"""M9 detection return service (detection-return-v1.md).

Subscribes to the Sango FramePublisher (ZeroMQ PUB on tcp://127.0.0.1:5556),
runs YOLO inference on each frame, and republishes a 2-part multipart message:

    part 1  topic   "sango.detection"
    part 2  JSON    DetectionResult {frame_seq, frame_time_s, source, detections[]}

Schema (frozen): sango/Docs/contracts/detection-result-v1.md. Boxes are filtered
to the COCO "boat" class (id 8); class_name is mapped from the model's own names
table. Every consumed frame produces exactly one result message, including
zero-detection frames (detections=[] is an authoritative "nothing seen").

Usage:
    .venv-detector/bin/python tools/sango_detector_service.py             # Unity → YOLO → Unity
    .venv-detector/bin/python tools/sango_detector_service.py --selftest  # 无 socket：验证依赖 + 权重

No Unity around? Feed frames with tools/sango_detector_replay.py.

P3-S2 (observations-v1.md, spec #90): optional HTTP forward branch. With
``--forward-url`` set, every result is ALSO posted to the backend observations
endpoint (``POST /api/sessions/{id}/observations``, frozen schema §3) — the
same payload shape, zero change to the ZMQ return path (default off).
"""

from __future__ import annotations

import argparse
import json
import math
import signal
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import cv2  # ultralytics 传递依赖
import zmq
from ultralytics import YOLO

REPO_ROOT = Path(__file__).resolve().parent.parent

# COCO "boat"（detection-return-v1.md：演示域只保留船类）
COCO_BOAT_CLASS_ID = 8


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Subscribe sango.frame → YOLO → publish sango.detection.")
    p.add_argument("--model", default=str(REPO_ROOT / "models" / "yolov8n.pt"),
                   help="YOLO weights (default models/yolov8n.pt, auto-downloaded on first run)")
    p.add_argument("--conf", type=float, default=0.25, help="confidence threshold (default 0.25)")
    p.add_argument("--endpoint", default="tcp://127.0.0.1:5556",
                   help="frame source to SUB connect (FramePublisher PUB bind address)")
    p.add_argument("--out", default="tcp://127.0.0.1:5557",
                   help="detection endpoint to PUB bind (Unity consumer connects here)")
    p.add_argument("--topic", default="sango.frame", help="frame topic to subscribe")
    p.add_argument("--out-topic", default="sango.detection", help="detection topic to publish")
    p.add_argument("--source", default="yolo-detector", help="DetectionResult.source identifier")
    p.add_argument("--device", default=None, help="ultralytics device (default: CPU)")
    p.add_argument("--log-every", type=int, default=10, help="log every N processed frames (first frame always logs)")
    p.add_argument("--selftest", action="store_true",
                   help="run inference on one synthetic frame (no sockets) and exit; verifies deps + weights")
    # P3-S2 observations forward branch (observations-v1.md §1/§3; default off — ZMQ path unchanged).
    p.add_argument("--forward-url", default="",
                   help="POST each result to this observations endpoint "
                        "(e.g. http://127.0.0.1:8010/api/sessions/<id>/observations); empty = off")
    p.add_argument("--forward-mount", default="mast_ptz_eo",
                   help="mount_id stamped on forwarded observations (mast camera table vocabulary)")
    p.add_argument("--forward-timeout", type=float, default=2.0,
                   help="per-POST timeout in seconds (failures are logged, never fatal)")
    p.add_argument("--dump-frame", default="",
                   help="save the first received frame as a JPEG at this path (feed-view evidence; off by default)")
    return p.parse_args()


def load_model(args: argparse.Namespace) -> YOLO:
    if args.device in (None, "cpu"):
        import torch
        torch.set_num_threads(2)
    t0 = time.perf_counter()
    model = YOLO(args.model)  # 权重缺失时 ultralytics 自动下载到该路径
    print(f"[detector] model loaded from {args.model} in {time.perf_counter() - t0:.1f}s "
          f"(task={getattr(model, 'task', '?')})")
    return model


def synthetic_frame(width: int = 640, height: int = 480):
    """程序合成测试图：灰度渐变 + 船体色块（selftest 专用，不落盘）。"""
    import numpy as np

    grad = np.linspace(30, 220, height, dtype=np.uint8)[:, None]
    img = np.repeat(grad, width, axis=1)
    img = np.stack([img, img, img], axis=-1)
    img[300:420, 120:460] = (40, 70, 130)    # "hull"
    img[160:280, 220:360] = (210, 225, 240)  # "superstructure"
    return img


def run_inference(model: YOLO, image, conf: float, class_ids: list[int] | None,
                  device: str | None) -> tuple[list[dict], float]:
    """单帧推理 → DetectionResult.detections 形状的 list + 推理耗时 ms（原图像素坐标系）。"""
    t0 = time.perf_counter()
    results = model.predict(image, conf=conf, classes=class_ids or None, device=device, verbose=False)
    infer_ms = (time.perf_counter() - t0) * 1000.0
    result = results[0]
    names = result.names
    detections = []
    for xyxy, cls, cf in zip(result.boxes.xyxy.tolist(), result.boxes.cls.tolist(), result.boxes.conf.tolist()):
        class_id = int(cls)
        detections.append({
            "box_xyxy": [round(float(v), 2) for v in xyxy],
            "class_id": class_id,
            "class_name": names.get(class_id, str(class_id)),
            "confidence": round(float(cf), 4),
        })
    return detections, infer_ms


def result_json(meta: dict, detections: list[dict], source: str) -> str:
    """DetectionResult JSON（detection-return-v1.md §2 线上形状，紧凑分隔符）。"""
    return json.dumps({
        "frame_seq": int(meta.get("frame_seq", 0)),
        "frame_time_s": float(meta.get("frame_time_s", 0.0)),
        "source": source,
        "detections": detections,
    }, separators=(",", ":"))


def observation_payload(meta: dict, detections: list[dict], source: str, mount_id: str) -> dict:
    """observations-v1 §3 request body (frozen schema; DetectionResult field subset, contract §6).

    mount_id prefers the frame metadata stamp (P3-S2 FrameMetadata.mount_id — the
    Unity rig labels its feed) and falls back to the CLI value for legacy senders.
    """
    return {
        "schema_version": "observations@1",
        "frame_seq": int(meta.get("frame_seq", 0)),
        "frame_time_s": float(meta.get("frame_time_s", 0.0)),
        "sensor_id": 2,  # camera_eo (contract §2 vocabulary; the EO feed is the forward camera)
        "mount_id": str(meta.get("mount_id") or mount_id),
        "source": source,
        "detections": detections,
    }


def forward_observation(url: str, payload: dict, timeout_s: float) -> tuple[bool, str]:
    """POST one ObservationFrame; returns (ok, detail). Never raises — the ZMQ
    return path and the inference loop must survive backend downtime (contract
    observations-v1 §6: the two consumer branches are independent)."""
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            body = response.read().decode("utf-8", "replace")[:200]
            return bool(200 <= response.status < 300), f"HTTP {response.status} {body}"
    except urllib.error.HTTPError as error:
        return False, f"HTTP {error.code} {error.read().decode('utf-8', 'replace')[:200]}"
    except Exception as error:  # noqa: BLE001 - any transport failure drops one frame only
        return False, f"{type(error).__name__}: {error}"


def decode_frame(parts: list[bytes], topic: str):
    """Validate the frozen envelope before inference; malformed input stays local to one frame."""
    import numpy as np

    if len(parts) != 3 or parts[0] != topic.encode("utf-8"):
        raise ValueError("invalid frame topic or multipart count")
    try:
        meta = json.loads(parts[1].decode("utf-8"))
        if not isinstance(meta, dict):
            raise ValueError("metadata must be an object")
        for key in ("frame_seq", "width", "height", "jpeg_bytes"):
            if type(meta.get(key)) is not int:
                raise ValueError(f"invalid {key}")
        timestamp = meta.get("frame_time_s")
        if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)) or not math.isfinite(timestamp) or timestamp < 0:
            raise ValueError("invalid frame_time_s")
        if meta["frame_seq"] < 0 or meta["width"] <= 0 or meta["height"] <= 0:
            raise ValueError("invalid sequence or dimensions")
        if not isinstance(meta.get("source"), str) or not meta["source"]:
            raise ValueError("invalid source")
        if meta["jpeg_bytes"] != len(parts[2]):
            raise ValueError("JPEG length mismatch")
        if "confidence_threshold" in meta:
            confidence = meta["confidence_threshold"]
            if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not math.isfinite(confidence) or not 0.01 <= confidence <= 1.0:
                raise ValueError("invalid confidence_threshold")
        image = cv2.imdecode(np.frombuffer(parts[2], dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None or image.shape[:2] != (meta["height"], meta["width"]):
            raise ValueError("JPEG decode or dimensions mismatch")
        return meta, image
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as error:
        raise ValueError("invalid frame metadata") from error


def selftest(args: argparse.Namespace) -> int:
    """对一张程序合成图直接跑模型（零 socket）：验证 pyzmq/ultralytics 依赖 + 权重可用。"""
    image = synthetic_frame()
    model = load_model(args)
    detections, infer_ms = run_inference(model, image, args.conf, [COCO_BOAT_CLASS_ID], args.device)
    raw = model.predict(image, conf=0.05, verbose=False, device=args.device)[0]  # 不过滤，证明权重确实出预测
    print(f"[detector] selftest: synthetic 640x480 infer={infer_ms:.1f}ms conf>={args.conf}")
    print(f"[detector] selftest: boat-filtered detections={len(detections)} raw@conf0.05={len(raw.boxes)}")
    print("[detector] selftest OK (pyzmq + ultralytics deps and weights verified)")
    return 0


def _sigterm_to_interrupt(signum, frame):
    """SIGTERM（pkill/杀进程）转 KeyboardInterrupt：finally 清 socket、打印 rx/tx 总计。"""
    raise KeyboardInterrupt


def serve(args: argparse.Namespace) -> int:
    signal.signal(signal.SIGTERM, _sigterm_to_interrupt)

    model = load_model(args)

    ctx = zmq.Context.instance()
    sub = ctx.socket(zmq.SUB)
    sub.setsockopt(zmq.SUBSCRIBE, args.topic.encode("utf-8"))
    sub.setsockopt(zmq.RCVTIMEO, 500)  # 短 tick，Ctrl-C 可即时生效
    sub.setsockopt(zmq.RCVHWM, 30)
    sub.connect(args.endpoint)
    pub = ctx.socket(zmq.PUB)
    pub.setsockopt(zmq.SNDHWM, 30)  # 与 Unity 发布端对称：消费端掉线不积压
    pub.bind(args.out)
    print(f"[detector] SUB connected {args.endpoint} (topic {args.topic}) -> PUB bound {args.out} (topic {args.out_topic})")
    print(f"[detector] conf={args.conf} boat_class_id={COCO_BOAT_CLASS_ID} source={args.source} device={args.device or 'cpu'}")
    if args.forward_url:
        print(f"[detector] forward branch ON -> {args.forward_url} (mount {args.forward_mount}, timeout {args.forward_timeout}s)")
    else:
        print("[detector] forward branch off (default; ZMQ return path only)")

    rx = tx = forwarded = forward_errors = 0
    try:
        while True:
            try:
                parts = sub.recv_multipart()
            except zmq.Again:
                continue
            # Inference consumes the latest available frame, rather than growing a stale FIFO.
            for _ in range(30):
                try:
                    parts = sub.recv_multipart(zmq.NOBLOCK)
                except zmq.Again:
                    break
            try:
                meta, image = decode_frame(parts, args.topic)
            except ValueError as e:
                print(f"[detector] WARN: {e}; skipped")
                continue

            confidence = float(meta.get("confidence_threshold", args.conf))
            if args.dump_frame and rx % 600 == 0:  # first frame + every ~60 s (10 fps budget) — last dump = latest view
                cv2.imwrite(args.dump_frame, image)
                print(f"[detector] feed frame dumped -> {args.dump_frame} (mount {meta.get('mount_id', '')} seq {meta.get('frame_seq')})")
            detections, infer_ms = run_inference(model, image, confidence, [COCO_BOAT_CLASS_ID], args.device)
            pub.send_multipart([args.out_topic.encode("utf-8"),
                                result_json(meta, detections, args.source).encode("utf-8")])
            rx += 1
            tx += 1
            if args.forward_url:
                ok, detail = forward_observation(
                    args.forward_url,
                    observation_payload(meta, detections, args.source, args.forward_mount),
                    args.forward_timeout,
                )
                if ok:
                    forwarded += 1
                else:
                    forward_errors += 1
                if (forward_errors == 1 and not ok) or rx % args.log_every == 0:
                    print(f"[detector] forward: ok={forwarded} err={forward_errors} last={detail}")
            if rx == 1 or rx % args.log_every == 0:
                print(f"[detector] rx={rx} tx={tx} seq={meta.get('frame_seq')} "
                      f"infer={infer_ms:.1f}ms conf={confidence:.2f} detections={len(detections)}")
    except KeyboardInterrupt:
        print(f"[detector] shutdown: rx={rx} tx={tx} forwarded={forwarded} forward_errors={forward_errors}")
    finally:
        sub.close(0)
        pub.close(0)
        ctx.term()
    return 0


def main() -> int:
    # 重定向到文件时 stdout 默认块缓冲，SIGTERM 会吞日志——服务日志须可 tail，改行缓冲
    sys.stdout.reconfigure(line_buffering=True)
    args = parse_args()
    if args.selftest:
        return selftest(args)
    return serve(args)


if __name__ == "__main__":
    sys.exit(main())
