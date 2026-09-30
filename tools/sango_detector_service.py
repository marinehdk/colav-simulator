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
"""

from __future__ import annotations

import argparse
import json
import signal
import sys
import time
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
    return p.parse_args()


def load_model(args: argparse.Namespace) -> YOLO:
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
    """DetectionResult JSON（detection-result-v1.md §2 线上形状，紧凑分隔符）。"""
    return json.dumps({
        "frame_seq": int(meta.get("frame_seq", 0)),
        "frame_time_s": float(meta.get("frame_time_s", 0.0)),
        "source": source,
        "detections": detections,
    }, separators=(",", ":"))


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
    import numpy as np

    signal.signal(signal.SIGTERM, _sigterm_to_interrupt)

    model = load_model(args)

    ctx = zmq.Context.instance()
    sub = ctx.socket(zmq.SUB)
    sub.setsockopt(zmq.SUBSCRIBE, args.topic.encode("utf-8"))
    sub.setsockopt(zmq.RCVTIMEO, 500)  # 短 tick，Ctrl-C 可即时生效
    sub.connect(args.endpoint)
    pub = ctx.socket(zmq.PUB)
    pub.setsockopt(zmq.SNDHWM, 30)  # 与 Unity 发布端对称：消费端掉线不积压
    pub.bind(args.out)
    print(f"[detector] SUB connected {args.endpoint} (topic {args.topic}) -> PUB bound {args.out} (topic {args.out_topic})")
    print(f"[detector] conf={args.conf} boat_class_id={COCO_BOAT_CLASS_ID} source={args.source} device={args.device or 'cpu'}")

    rx = tx = 0
    try:
        while True:
            try:
                parts = sub.recv_multipart()
            except zmq.Again:
                continue
            if len(parts) != 3:
                print(f"[detector] WARN: expected 3-part frame message, got {len(parts)} part(s); skipped")
                continue
            _, meta_raw, jpeg = parts
            try:
                meta = json.loads(meta_raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as e:
                print(f"[detector] WARN: metadata JSON parse error: {e}; skipped")
                continue
            image = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
            if image is None:
                print(f"[detector] WARN: seq={meta.get('frame_seq')} JPEG decode failed; skipped")
                continue
            meta_w, meta_h = int(meta.get("width", 0)), int(meta.get("height", 0))
            img_h, img_w = image.shape[:2]
            if (meta_w and img_w != meta_w) or (meta_h and img_h != meta_h):
                print(f"[detector] WARN: seq={meta.get('frame_seq')} metadata {meta_w}x{meta_h} != decoded {img_w}x{img_h}")

            detections, infer_ms = run_inference(model, image, args.conf, [COCO_BOAT_CLASS_ID], args.device)
            pub.send_multipart([args.out_topic.encode("utf-8"),
                                result_json(meta, detections, args.source).encode("utf-8")])
            rx += 1
            tx += 1
            if rx == 1 or rx % args.log_every == 0:
                print(f"[detector] rx={rx} tx={tx} seq={meta.get('frame_seq')} "
                      f"infer={infer_ms:.1f}ms detections={len(detections)}")
    except KeyboardInterrupt:
        print(f"[detector] shutdown: rx={rx} tx={tx}")
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
