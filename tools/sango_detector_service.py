#!/usr/bin/env python3
"""M9 detection return service (detection-return-v1.md).

Subscribes to the Sango FramePublisher (ZeroMQ PUB on tcp://127.0.0.1:5556),
runs YOLO inference on each frame, and republishes a 2-part multipart message:

    part 1  topic   "sango.detection"
    part 2  JSON    DetectionResult {frame_seq, frame_time_s, source, detections[]}

Schema (frozen): sango/Docs/contracts/detection-result-v1.md. Boxes are filtered
to the model's vessel/boat/ship classes (auto-detected from the weights' names
table — COCO weights keep "boat" id 8; single-class maritime weights map to
their own id); class_name is mapped from the model's own names
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

DT 视口分流(2026-10-15):``--viewport-forward-url`` 把每条结果(含空检测帧)
另按 viewport-detections@1 契约 POST 到后端
``POST /api/sessions/{id}/viewport-detections``,随遥测 WS 广播绿框;与
--forward-url 互不干扰可同开,同样零改 :5557 既有 PUB 契约(默认关)。

P1 本船掩膜下沉检测端(2026-10-19,viewport-ownship-polygon@1):
``--ownship-polygon-url`` 开启后,服务循环在 decode 后、SAHI 切片前把本船水线
多边形区域 cv2.fillPoly 填成海灰(约 0.45 亮度+轻噪)——本船自身不再进推理。
帧-多边形对齐 = 分流帧顶部 256×16 FRAME_MARKER 像素条(twin-bridge-v1
situation display 契约,web decodeFrameMarker 同源)移植解码出 frame_id,与
后端 GET /api/viewport-ownship-polygon 环形缓存按 frame_id 精确匹配;无
marker(压缩歧义/画面太小)、无 polygon(缓存未命中/空多边形)一律优雅跳过,
掩膜关闭(--ownship-polygon-url 空)时零行为变化(默认关)。

路线A 本船逐像素掩膜通道(2026-10-20,ownship-mask-v1.md):``--ownship-mask-endpoint``
(默认 tcp://127.0.0.1:5558,空串=关)开启后,SUB 直连播放器 TwinOwnshipMaskPublisher,
逐帧 1bit RLE 掩膜入环形缓存;服务循环 decode 后、SAHI 前按 FRAME_MARKER
frame_id 精确匹配,命中即把本船像素(膨胀 3px 抗 TAA 边缘)填海灰+轻噪——
任意视角像素级根治,替代 P1 多边形几何源;掩膜缺失/损坏回退 P1 多边形
(--ownship-polygon-url 开启时),再缺原帧直推(fail-open)。逐帧掩膜命中态
("mask"/"polygon"/"none")随 viewport-detections 转发透传供记录仪复演。
"""

from __future__ import annotations

import argparse
import json
import math
import os
import signal
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING

import cv2  # ultralytics 传递依赖
import zmq

if TYPE_CHECKING:  # 运行时延迟到 load_model(纯函数单测无 torch 也可导入本模块)
    from ultralytics import YOLO

REPO_ROOT = Path(__file__).resolve().parent.parent

# COCO "boat"（detection-return-v1.md：演示域只保留船类）。yolov8n/s 出货即 COCO 80 类，
# 船类过滤默认落它；海事定制权重（如 20261020 接入的 yolov18.pt = 单类 'vessel'）类别表
# 不同，运行时按模型 names 自动选船类（boat_class_ids），无船类才退 COCO 8。
COCO_BOAT_CLASS_ID = 8
BOAT_CLASS_NAME_KEYS = ("vessel", "boat", "ship", "watercraft")


def boat_class_ids(names) -> list[int]:
    """模型类别表 → 船类 id 列表（名字含 vessel/boat/ship/watercraft）。

    纯函数（单测锚）：海事单类权重 {0:'vessel'} → [0]；COCO 表 → [8]；
    没有船类（异常权重）→ [COCO_BOAT_CLASS_ID] 兜底——宁可放非船框也不断流。
    """
    if not isinstance(names, dict):
        return [COCO_BOAT_CLASS_ID]
    hits = [int(cid) for cid, label in names.items()
            if any(key in str(label).lower() for key in BOAT_CLASS_NAME_KEYS)]
    return hits or [COCO_BOAT_CLASS_ID]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Subscribe sango.frame → YOLO → publish sango.detection.")
    p.add_argument("--model", default=str(REPO_ROOT / "models" / "yolov8n.pt"),
                   help="YOLO weights (default models/yolov8n.pt COCO; boat-class filter "
                        "auto-adapts to the weights' names table — e.g. maritime single-class "
                        "'vessel' weights map to their own id)")
    p.add_argument("--conf", type=float, default=0.25, help="confidence threshold (default 0.25)")
    p.add_argument("--imgsz", type=int, default=640,
                   help="inference input size (default 640; raise to 1280 for distant small hulls, CPU cost ~3-4x)")
    p.add_argument("--slice-size", type=int, default=0,
                   help="SAHI sliced inference tile size (default 0=off; 640 = 720p→3x2 tiles, "
                        "small-target recall per SAHI paper ~+17%%; needs `pip install sahi`")
    p.add_argument("--endpoint", default="tcp://127.0.0.1:5556",
                   help="frame source to SUB connect (FramePublisher PUB bind address)")
    p.add_argument("--out", default="tcp://127.0.0.1:5557",
                   help="detection endpoint to PUB bind (Unity consumer connects here)")
    p.add_argument("--topic", default="sango.frame", help="frame topic to subscribe")
    p.add_argument("--out-topic", default="sango.detection", help="detection topic to publish")
    p.add_argument("--source", default="yolo-detector", help="DetectionResult.source identifier")
    p.add_argument("--device", default=None, help="ultralytics device (default: CPU)")
    p.add_argument("--log-every", type=int, default=10, help="log every N processed frames (first frame always logs)")
    p.add_argument("--pidfile", default="", help="serve mode writes its pid here on start (engine liveness probe)")
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
    # DT 视口分流转发分支(viewport-detections@1;默认关,:5557 ZMQ 返回路径不变)。
    p.add_argument("--viewport-forward-url", default="",
                   help="POST each result to this viewport-detections endpoint "
                        "(e.g. http://127.0.0.1:8010/api/sessions/<id>/viewport-detections); empty = off")
    p.add_argument("--ownship-polygon-url", default="",
                   help="GET own-ship waterline polygon cache before inference "
                        "(viewport-ownship-polygon@1, e.g. http://127.0.0.1:8010/api/viewport-ownship-polygon); "
                        "empty = own-ship mask off (default)")
    p.add_argument("--ownship-mask-endpoint", default="tcp://127.0.0.1:5558",
                   help="SUB connect endpoint of the twin own-ship pixel mask channel "
                        "(ownship-mask-v1, player PUB tcp://127.0.0.1:5558); "
                        "mask miss falls back to --ownship-polygon-url; empty = off")
    p.add_argument("--dump-frame", default="",
                   help="save the first received frame as a JPEG at this path (feed-view evidence; off by default)")
    p.add_argument("--ownship-diag-dir", default="",
                   help="own-ship mask diagnostics dir: classify every mask_state=none cause "
                        "(stamp/race/empty/bad), dump leak-suspect frames (none + boat det) "
                        "and periodic applied-mask frames; off by default")
    return p.parse_args()


def load_model(args: argparse.Namespace) -> YOLO:
    import torch
    from ultralytics import YOLO  # 延迟到加载点:纯函数(mask/marker 解码)单测无需 torch

    if args.device in (None, "cpu"):
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
                  device: str | None, imgsz: int = 640) -> tuple[list[dict], float]:
    """单帧推理 → DetectionResult.detections 形状的 list + 推理耗时 ms（原图像素坐标系）。"""
    t0 = time.perf_counter()
    results = model.predict(image, conf=conf, classes=class_ids or None, device=device,
                            imgsz=imgsz, verbose=False)
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


def run_sliced_inference(sahi_model, image) -> tuple[list[dict], float]:
    """SAHI 切片推理（--slice-size 开启）：720p 切 tile+重叠 → 逐片推理 → 跨片 NMS
    合并，坐标回原图像素域。远距小目标召回 ~+17%（SAHI 原论文）。conf 沿用模型
    构造时的 threshold（引擎链路不做 per-frame 覆盖）。"""
    try:
        from sahi import get_sliced_prediction  # sahi ≤0.11 顶层导出
    except ImportError:  # sahi 0.12+ 挪到 sahi.predict
        from sahi.predict import get_sliced_prediction
    t0 = time.perf_counter()
    result = get_sliced_prediction(
        image, sahi_model,
        slice_height=sahi_model.slice_size, slice_width=sahi_model.slice_size,
        overlap_height_ratio=0.2, overlap_width_ratio=0.2, verbose=0,
    )
    infer_ms = (time.perf_counter() - t0) * 1000.0
    detections = []
    for pred in result.object_prediction_list:
        det_class = pred.category
        detections.append({
            "box_xyxy": [round(float(v), 2) for v in pred.bbox.to_xyxy()],
            "class_id": int(det_class.id),
            "class_name": str(det_class.name),
            "confidence": round(float(pred.score.value), 4),
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


_MOUNT_SENSOR_IDS: dict[str, int] = {}


def mount_sensor_id(mount_id: str) -> int:
    """mount_id -> observation sensor_id via the backend mast camera table (P3-7).

    Minimal implementation (P3-7 review fix, spec #90): ``colav_simulator.core
    .mast_cameras`` is the backend-authoritative, stdlib-only calibration table,
    so the repo copy is imported directly (verified importable from the
    .venv-detector interpreter). An unknown mount_id fails loudly instead of
    silently masquerading as the EO channel.
    """
    if not _MOUNT_SENSOR_IDS:
        sys.path.insert(0, str(REPO_ROOT))
        from colav_simulator.core.mast_cameras import MAST_MOUNTS_BY_ID

        _MOUNT_SENSOR_IDS.update({name: int(mount.sensor_id) for name, mount in MAST_MOUNTS_BY_ID.items()})
    if mount_id not in _MOUNT_SENSOR_IDS:
        raise ValueError(f"unknown forward mount_id {mount_id!r} (mast camera table vocabulary)")
    return _MOUNT_SENSOR_IDS[mount_id]


def observation_payload(meta: dict, detections: list[dict], source: str, mount_id: str) -> dict:
    """observations-v1 §3 request body (frozen schema; DetectionResult field subset, contract §6).

    mount_id prefers the frame metadata stamp (P3-S2 FrameMetadata.mount_id — the
    Unity rig labels its feed) and falls back to the CLI value for legacy senders;
    sensor_id follows the EFFECTIVE mount through the calibration table (P3-7:
    no longer hardcoded to camera_eo — an IR feed stamps sensor_id=3).
    """
    effective_mount = str(meta.get("mount_id") or mount_id)
    return {
        "schema_version": "observations@1",
        "frame_seq": int(meta.get("frame_seq", 0)),
        "frame_time_s": float(meta.get("frame_time_s", 0.0)),
        "sensor_id": mount_sensor_id(effective_mount),
        "mount_id": effective_mount,
        "source": source,
        "detections": detections,
    }


def viewport_payload(meta: dict, detections: list[dict], ownship_mask: str = "none") -> dict:
    """viewport-detections@1 request body(DT 视口分流帧;received_at 由服务器覆写).

    width/height 取当帧 FrameMetadata(处理循环现场留存;不改 :5557 既有
    DetectionResult PUB payload 契约),source 固定 "twin-viewport"。
    ownship_mask = 当帧本船抑制命中态(ownship-mask-v1 §5:"mask"/"polygon"/
    "none",旧发送端缺省 none)——记录仪复演与泄漏归因用。
    """
    return {
        "schema": "viewport_detections@1",
        "pts_s": float(meta.get("frame_time_s", 0.0)),
        "width": int(meta.get("width", 0)),
        "height": int(meta.get("height", 0)),
        "source": "twin-viewport",
        "ownship_mask": ownship_mask,
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
        # 目标恒为本机/隧道回环端点(8010/18010),不吃部署机 http_proxy 环境变量
        # (a4000 shell 带代理时 urllib 默认走 proxy → 127.0.0.1 POST 超时)
        direct_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with direct_opener.open(request, timeout=timeout_s) as response:
            body = response.read().decode("utf-8", "replace")[:200]
            return bool(200 <= response.status < 300), f"HTTP {response.status} {body}"
    except urllib.error.HTTPError as error:
        return False, f"HTTP {error.code} {error.read().decode('utf-8', 'replace')[:200]}"
    except Exception as error:  # noqa: BLE001 - any transport failure drops one frame only
        return False, f"{type(error).__name__}: {error}"


def forward_branch(args: argparse.Namespace, url: str, payload: dict, rx: int, stats: list[int],
                   label: str) -> None:
    """One HTTP forward branch step shared by the observations/viewport branches.

    ``stats`` = [forwarded, errors], mutated in place; the first error and every
    ``--log-every``-th frame log a line. Transport failures drop one frame only
    (never fatal) — see forward_observation.
    """
    try:
        ok, detail = forward_observation(url, payload, args.forward_timeout)
    except Exception as error:  # noqa: BLE001 - one frame dropped
        ok, detail = False, f"{type(error).__name__}: {error}"
    if ok:
        stats[0] += 1
    else:
        stats[1] += 1
    if (stats[1] == 1 and not ok) or rx % args.log_every == 0:
        print(f"[detector] {label}: ok={stats[0]} err={stats[1]} last={detail}")


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


# ── P1 本船掩膜:FRAME_MARKER 解码 + 海灰填充 + 多边形缓存 ──────────────────
# 采样几何与阈值逐字移植 web_gui/modules/twin-situation.js decodeFrameMarker
# (web: drawImage(video, 0, 8, 256, 1, → 32×1) + gst sender._capture_frame_marker
# 同款双证):顶部 256×16 标记条第 8 行,32 格 × 8px 块均值;灰度落 (80,175)
# 歧义窗 = 压缩糊帧 fail-closed;魔数 0xD3 + 校验 (hi^lo^0x5A)。
FRAME_MARKER_ROW = 8
FRAME_MARKER_CELLS = 32
FRAME_MARKER_CELL_PX = 8


def decode_frame_marker(image) -> int | None:
    """解码分流帧顶部的 frame identity 标记条;不可解码(歧义/损坏/画面太小)返 None。"""
    import numpy as np

    height, width = image.shape[:2]
    if width < FRAME_MARKER_CELL_PX * FRAME_MARKER_CELLS or height <= FRAME_MARKER_ROW:
        return None
    row = image[FRAME_MARKER_ROW, :FRAME_MARKER_CELL_PX * FRAME_MARKER_CELLS, :3]
    cells = row.astype(np.float32).reshape(FRAME_MARKER_CELLS, FRAME_MARKER_CELL_PX, 3).mean(axis=(1, 2))
    bits = 0
    for level in cells:
        if 80 < level < 175:
            return None
        bits = (bits << 1) | int(level >= 175)
    if (bits >> 24) != 0xD3:
        return None
    frame = (bits >> 8) & 0xFFFF
    if (bits & 0xFF) != (((frame >> 8) ^ frame ^ 0x5A) & 0xFF):
        return None
    return frame


# 海灰 ≈ 0.45×255(EO 海面观感);轻噪 σ=5/通道,只生成于多边形包围盒内。
OWNSHIP_MASK_GRAY = 115
OWNSHIP_MASK_NOISE_SIGMA = 5.0


def apply_ownship_mask(image, corners, rng=None):
    """推理前把本船水线多边形区域填成海灰+轻噪;返回新图,原帧不动。

    corners = 归一化视口坐标角点({x,y,depth,in_frame},x/y 可越界——部分出画
    仍给全多边形,cv2.fillPoly 自行按画面裁剪);<3 角点原样返回(契约:
    polygon=[] = 无掩膜)。噪声音逐通道独立,包在多边形包围盒内生成。
    """
    import numpy as np

    if corners is None or len(corners) < 3:
        return image
    height, width = image.shape[:2]
    points = np.array(
        [[float(corner["x"]) * width, float(corner["y"]) * height] for corner in corners],
        dtype=np.int32)
    x0 = max(0, int(points[:, 0].min()))
    x1 = min(width, int(points[:, 0].max()) + 1)
    y0 = max(0, int(points[:, 1].min()))
    y1 = min(height, int(points[:, 1].max()) + 1)
    if x1 <= x0 or y1 <= y0:
        return image
    region_mask = np.zeros((y1 - y0, x1 - x0), dtype=np.uint8)
    cv2.fillPoly(region_mask, [points - [x0, y0]], 255)
    noise = (rng or np.random.default_rng()).normal(
        OWNSHIP_MASK_GRAY, OWNSHIP_MASK_NOISE_SIGMA,
        (y1 - y0, x1 - x0, 3)).clip(0, 255).astype(np.uint8)
    masked = image.copy()
    region = masked[y0:y1, x0:x1]
    region[region_mask > 0] = noise[region_mask > 0]
    return masked


def fetch_ownship_polygon(url: str, timeout_s: float) -> dict:
    """GET viewport-ownship-polygon@1 缓存快照;传输/解析异常向上抛(调用方退避)。"""
    request = urllib.request.Request(url, method="GET")
    # 与 forward_observation 同款:回环端点不吃 http_proxy 环境变量
    direct_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with direct_opener.open(request, timeout=timeout_s) as response:
        return json.loads(response.read().decode("utf-8"))


class OwnshipPolygonCache:
    """循环内拉取/缓存 (frame_id → 本船多边形);按 frame_id 精确匹配。

    pull 节流 min_interval_s,失败保旧缓存并退避 failure_backoff_s(后端停机
    不拖垮推理节拍);frames 整表换新(服务端环形缓存已逐出老帧,保留旧键
    只会陈旧误配)。fetch 可注入(单测离线)。
    """

    def __init__(self, url: str, timeout_s: float = 0.25, min_interval_s: float = 0.15,
                 failure_backoff_s: float = 2.0, fetch=None, clock=time.monotonic):
        self.url = url
        self.timeout_s = timeout_s
        self.min_interval_s = min_interval_s
        self.failure_backoff_s = failure_backoff_s
        self._fetch = fetch or fetch_ownship_polygon
        self._clock = clock
        self._frames: dict[int, list] = {}
        self._next_pull = 0.0
        self.pulled = 0
        self.errors = 0

    def maybe_refresh(self) -> bool:
        """按节流/退避节拍拉一次;返回是否实际拉取(成功与否都算)。"""
        now = self._clock()
        if now < self._next_pull:
            return False
        self._next_pull = now + self.min_interval_s
        try:
            payload = self._fetch(self.url, self.timeout_s)
            frames = payload.get("frames") if isinstance(payload, dict) else None
            if isinstance(frames, list):
                self._frames = {int(entry["frame_id"]): list(entry.get("polygon") or [])
                                for entry in frames
                                if isinstance(entry, dict) and "frame_id" in entry}
                self.pulled += 1
        except Exception:  # noqa: BLE001 - 传输/解析失败:保旧缓存,退避重试
            self.errors += 1
            self._next_pull = now + self.failure_backoff_s
        return True

    def polygon_for(self, frame_id: int) -> list | None:
        """该帧的本船多边形;未命中(缓存尚无此帧)返 None,命中可为 [](无掩膜)。"""
        return self._frames.get(frame_id)


# ── 路线A 本船逐像素掩膜通道(ownship-mask-v1.md,2026-10-20)──────────────────
# 播放器 TwinOwnshipMaskPublisher PUB :5558 直供逐帧 1bit RLE 掩膜(替代 P1
# 多边形的几何源);检测端环形缓存按 FRAME_MARKER frame_id 精确匹配,SAHI 前应用。
OWNSHIP_MASK_DILATE_PX = 3  # 膨胀半径:抗 TAA/缩放边缘错位(survey §4.2 建议 2-4px)


def decode_mask_rle(payload: bytes, width: int, height: int):
    """ownship-mask-v1 §3 RLE → 顶行先行 bool 掩膜;任何契约违背返 None(fail-open)。

    逐行独立:交替 0/1 游程 uint16 LE、恒以 0 游程开头、行游程和==width、行间
    不共享游程;与 C# EncodeRle 用同一黄金向量对拍(顶行先行)。
    """
    import numpy as np

    if len(payload) % 2 or width <= 0 or height <= 0:
        return None
    runs = np.frombuffer(payload, dtype="<u2")
    mask = np.zeros(width * height, dtype=bool)
    index = 0
    for row in range(height):
        base = row * width
        consumed = 0
        value = 0
        while consumed < width:
            if index >= len(runs):
                return None
            run = int(runs[index])
            index += 1
            # 行首 0 游程可合法为 0(行首像素即 1);其余 0 长度游程=契约违约
            if run < 0 or consumed + run > width or (run == 0 and not (consumed == 0 and value == 0)):
                return None
            if value:
                mask[base + consumed:base + consumed + run] = True
            consumed += run
            value ^= 1
    if index != len(runs):
        return None
    return mask.reshape(height, width)


def apply_ownship_bitmap_mask(image, mask, rng=None, dilate_px: int = OWNSHIP_MASK_DILATE_PX):
    """推理前把本船逐像素掩膜区域填海灰+轻噪;返回 (新图, 是否有像素被填)。

    掩膜域≠帧域时 NEAREST 缩放(640×360 真值 → 1280×720 分流帧);膨胀抗边缘
    错位;噪声音只生成于掩膜包围盒内(与 apply_ownship_mask 同观感同纪律)。
    """
    import numpy as np

    height, width = image.shape[:2]
    if mask.shape != (height, width):
        mask = cv2.resize(mask.astype(np.uint8), (width, height), interpolation=cv2.INTER_NEAREST).astype(bool)
    if dilate_px > 0:
        mask = cv2.dilate(mask.astype(np.uint8),
                          np.ones((dilate_px * 2 + 1, dilate_px * 2 + 1), np.uint8)).astype(bool)
    rows, cols = np.nonzero(mask)
    if rows.size == 0:
        return image, False
    y0, y1 = int(rows.min()), int(rows.max()) + 1
    x0, x1 = int(cols.min()), int(cols.max()) + 1
    sub = mask[y0:y1, x0:x1]
    noise = (rng or np.random.default_rng()).normal(
        OWNSHIP_MASK_GRAY, OWNSHIP_MASK_NOISE_SIGMA,
        (y1 - y0, x1 - x0, 3)).clip(0, 255).astype(np.uint8)
    masked = image.copy()
    region = masked[y0:y1, x0:x1]
    region[sub] = noise[sub]
    return masked, True


class OwnshipMaskCache:
    """(frame_id → RLE 掩膜) 环形缓存:PUB 帧率(≤60Hz)高于分流帧(≤10Hz),
    容量 600 帧 ≈ 60fps 下 10s,覆盖 sender 编码管线 100-300ms 滞后绰绰有余;
    同 frame_id 重复到达 = 后发覆盖(marker 静止期相机仍在动,发布器持续重发)。"""

    def __init__(self, capacity: int = 600):
        from collections import OrderedDict
        self._frames: "OrderedDict[int, tuple[bytes, int, int]]" = OrderedDict()
        self.capacity = capacity
        self.received = 0
        self.malformed = 0

    def put(self, frame_id: int, rle: bytes, width: int, height: int) -> None:
        self._frames[frame_id] = (rle, width, height)
        while len(self._frames) > self.capacity:
            self._frames.popitem(last=False)

    def entry_for(self, frame_id: int):
        return self._frames.get(frame_id)

    @property
    def newest_id(self) -> "int | None":
        """环内最新 frame_id(插入序末位;同 id 重复 put 保留原位,值不变无碍);
        空环返 None。wait_for_mask 用它判"想要 id 是否还在路上"。"""
        return next(reversed(self._frames)) if self._frames else None


def drain_ownship_mask_socket(socket, cache: OwnshipMaskCache) -> int:
    """非阻塞排空掩膜 SUB → 入环;格式违约计费丢弃,绝不向上抛。"""
    drained = 0
    while True:
        try:
            parts = socket.recv_multipart(zmq.NOBLOCK)
        except zmq.Again:
            return drained
        drained += 1
        try:
            if len(parts) != 3 or parts[0] != b"sango.ownship_mask":
                raise ValueError("invalid mask topic or multipart count")
            meta = json.loads(parts[1].decode("utf-8"))
            frame_id = meta["frame_id"]
            width, height = meta["width"], meta["height"]
            if (meta.get("schema") != "ownship_mask@1" or type(frame_id) is not int
                    or type(width) is not int or type(height) is not int
                    or meta.get("rle_bytes") != len(parts[2])):
                raise ValueError("invalid mask metadata")
            cache.put(frame_id, bytes(parts[2]), width, height)
            cache.received += 1
        except (KeyError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
            cache.malformed += 1


def wait_for_mask(socket, cache: OwnshipMaskCache, frame_id: int, budget_s: float = 0.12) -> bool:
    """frame_id 精确匹配未命中时的短自旋等待。**只等"还在路上"的 id**(20261020
    三期实锤:tap 视频链延迟≈0,会跑赢掩膜 AsyncGPUReadback 1-2 个渲染帧,
    `want=19097 cache max=19095`;旧 30ms 预算 < 1 帧周期 33ms 盖不住):想要的
    id 模 u16 距环内最新 ≤64(≈2s 帧量)才等,滑出环底/不可能再来的 id 直接
    miss 不空等;空环(会话刚起,首帧掩膜未到)按在路上处理。窗口内排空补收
    把竞态转命中;命中 True / 超时 False。sleep 2ms 让出,只在新数据到达时重查。"""
    newest = cache.newest_id
    if newest is not None and (frame_id - newest) % 65536 > 64:
        return False  # 模 u16 距最新 >64 id:滑出环底或离群旧 id,永不再来不空等
    deadline = time.perf_counter() + budget_s
    while cache.entry_for(frame_id) is None:
        if time.perf_counter() >= deadline:
            return False
        time.sleep(0.002)
        drain_ownship_mask_socket(socket, cache)
    return True


def meta_frame_id(meta: dict) -> int | None:
    """FrameMetadata.frame_id(sender gst tap 支路全分辨率侧解码直供;缩放后像素
    marker 不可靠)→ 合法 u16 或 None;非法/缺省返 None 交调用方回退像素解码。"""
    value = meta.get("frame_id") if isinstance(meta, dict) else None
    return value if type(value) is int and 0 <= value <= 65535 else None


def ownship_mask_step2(image, mask_cache, polygon_cache, frame_id=None):
    """服务循环单帧掩膜步(路线A 主路径 + P1 多边形回退,fail-open)。

    frame_id 优先取 sender 元数据(gst tap 720p 帧像素 marker 缩放+JPEG 后落
    歧义窗不可解码——20261020 生产实测 100% miss 的根因),None 时回退像素条
    解码(FramePublisher 直连/离线回放路径)。返回 (图像, 命中态):"mask" =
    逐像素掩膜已应用;"polygon" = 掩膜缺/坏 → P1 多边形回退已应用;"none" =
    两通道都无(原帧直推)。空掩膜(本船不在画)= 权威无操作,同 "none" 观感
    但语义来自掩膜通道——记录仪靠检测日志计数区分。
    """
    if not (type(frame_id) is int and 0 <= frame_id <= 65535):
        frame_id = None  # 缺省/非法元数据:回退像素条解码(调用方失误也 fail-open)
    if frame_id is None:
        frame_id = decode_frame_marker(image)
    if frame_id is not None and mask_cache is not None:
        entry = mask_cache.entry_for(frame_id)
        if entry is not None:
            rle, width, height = entry
            mask = decode_mask_rle(rle, width, height)
            if mask is not None:
                masked, applied = apply_ownship_bitmap_mask(image, mask)
                if applied:
                    return masked, "mask"
                return image, "none"
    if polygon_cache is not None and frame_id is not None:
        polygon_cache.maybe_refresh()
        corners = polygon_cache.polygon_for(frame_id)
        if corners:
            return apply_ownship_mask(image, corners), "polygon"
    return image, "none"


def classify_mask_none(image, meta: dict, mask_cache):
    """mask_state=none 归因(20261020 掩膜泄漏二轮排查):step2 的 "none" 混四种
    境况,聚合计数 mask_miss 无法区分——泄漏帧到底卡在哪一环靠这里分类。

    stamp  = sender 元数据无 frame_id 且像素条解码也失败(分流链未盖戳)
    race   = frame_id 合法但缓存未命中(掩膜 AsyncGPUReadback 晚于图像到达)
    badrle = 命中但 RLE 解码失败(契约违约,应≈0)
    empty  = 命中且掩膜全零(本船不在画=合法无操作;若泄漏帧落此类且画中有
             本船 → 发布器渲染器覆盖缺口,特定视角漏检的形状)
    """
    fid = meta_frame_id(meta)
    if fid is None:
        fid = decode_frame_marker(image)
    if fid is None:
        return "stamp", None
    if mask_cache is None:
        return "nocache", fid
    entry = mask_cache.entry_for(fid)
    if entry is None:
        ids = list(mask_cache._frames.keys())
        window = f"{min(ids)}..{max(ids)}/n{len(ids)}" if ids else "empty"
        return f"race(want={fid} cache={window})", fid
    mask = decode_mask_rle(entry[0], entry[1], entry[2])
    if mask is None:
        return "badrle", fid
    return "empty" if not mask.any() else "MASKED-BUT-LEAKED", fid


def selftest(args: argparse.Namespace) -> int:
    """对一张程序合成图直接跑模型（零 socket）：验证 pyzmq/ultralytics 依赖 + 权重可用。"""
    image = synthetic_frame()
    model = load_model(args)
    class_ids = boat_class_ids(getattr(model, "names", {}))
    detections, infer_ms = run_inference(model, image, args.conf, class_ids, args.device)
    raw = model.predict(image, conf=0.05, verbose=False, device=args.device)[0]  # 不过滤，证明权重确实出预测
    print(f"[detector] selftest: synthetic 640x480 infer={infer_ms:.1f}ms conf>={args.conf} boat_classes={class_ids}")
    print(f"[detector] selftest: boat-filtered detections={len(detections)} raw@conf0.05={len(raw.boxes)}")
    print("[detector] selftest OK (pyzmq + ultralytics deps and weights verified)")
    return 0


def _sigterm_to_interrupt(signum, frame):
    """SIGTERM（pkill/杀进程）转 KeyboardInterrupt：finally 清 socket、打印 rx/tx 总计。"""
    raise KeyboardInterrupt


def serve(args: argparse.Namespace) -> int:
    signal.signal(signal.SIGTERM, _sigterm_to_interrupt)

    if args.pidfile:
        Path(args.pidfile).write_text(f"{os.getpid()}\n")  # 引擎探活(engine 端点远程模式)

    model = load_model(args)
    # 船类过滤按权重类别表自适应（yolov18 单类 'vessel'→[0]；COCO 系→[8]）。
    boat_ids = boat_class_ids(getattr(model, "names", {}))
    sahi_model = None
    if args.slice_size:
        from sahi import AutoDetectionModel  # GPU 部署件:SAHI 切片小目标召回
        sahi_model = AutoDetectionModel.from_pretrained(
            model_type="yolov8", model_path=args.model,
            confidence_threshold=args.conf, device=args.device or "cpu",
        )
        sahi_model.slice_size = args.slice_size

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
    print(f"[detector] conf={args.conf} imgsz={args.imgsz} slice={args.slice_size or 'off'} "
          f"boat_classes={boat_ids}({getattr(model, 'names', {}).get(boat_ids[0], '?')}) "
          f"source={args.source} device={args.device or 'cpu'}")
    if args.forward_url:
        print(f"[detector] forward branch ON -> {args.forward_url} (mount {args.forward_mount}, timeout {args.forward_timeout}s)")
    else:
        print("[detector] forward branch off (default; ZMQ return path only)")
    if args.viewport_forward_url:
        print(f"[detector] viewport-forward branch ON -> {args.viewport_forward_url} (timeout {args.forward_timeout}s)")
    else:
        print("[detector] viewport-forward branch off (default)")

    rx = tx = 0
    forward_stats = [0, 0]  # observations branch [forwarded, errors]
    viewport_stats = [0, 0]  # DT 视口分流 branch [forwarded, errors]
    ownship_cache = OwnshipPolygonCache(args.ownship_polygon_url) if args.ownship_polygon_url else None
    mask_cache = OwnshipMaskCache() if args.ownship_mask_endpoint else None
    mask_sub = None
    if mask_cache is not None:
        mask_sub = ctx.socket(zmq.SUB)
        mask_sub.setsockopt(zmq.SUBSCRIBE, b"sango.ownship_mask")
        mask_sub.setsockopt(zmq.RCVHWM, 120)  # 与发布端 SNDHWM 60 对称:丢旧不积压
        mask_sub.connect(args.ownship_mask_endpoint)
    mask_stats = [0, 0, 0]  # [bitmap, polygon_fallback, none](ownship-mask-v1 §5 降级链)
    if ownship_cache is not None:
        print(f"[detector] ownship polygon fallback ON -> {args.ownship_polygon_url} "
              f"(gray~{OWNSHIP_MASK_GRAY}+noise{OWNSHIP_MASK_NOISE_SIGMA:g}, before SAHI)")
    else:
        print("[detector] ownship polygon fallback off (default; --ownship-polygon-url to enable)")
    if mask_cache is not None:
        print(f"[detector] ownship pixel mask ON -> {args.ownship_mask_endpoint} "
              f"(topic sango.ownship_mask, dilate {OWNSHIP_MASK_DILATE_PX}px, before SAHI)")
    else:
        print("[detector] ownship pixel mask off (--ownship-mask-endpoint '' to disable)")
    diag_dir = Path(args.ownship_diag_dir) if args.ownship_diag_dir else None
    diag_causes: dict = {}
    diag_last_dump = 0.0
    if diag_dir is not None:
        diag_dir.mkdir(parents=True, exist_ok=True)
        print(f"[detector] ownship diag ON -> {diag_dir} (none-cause classify + leak/apply dumps)")
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
            # 本船抑制(路线A 主路径 + P1 回退):decode 后、SAHI 切片前。帧对齐 =
            # 像素条解出 frame_id 与掩膜/多边形缓存精确匹配;两通道都缺原帧直推。
            mask_state = "none"
            if mask_cache is not None or ownship_cache is not None:
                if mask_sub is not None:
                    drain_ownship_mask_socket(mask_sub, mask_cache)
                mask_fid = meta_frame_id(meta)
                if (mask_sub is not None and mask_cache is not None and mask_fid is not None
                        and mask_cache.entry_for(mask_fid) is None):
                    wait_for_mask(mask_sub, mask_cache, mask_fid)  # tap 视频跑赢读回(1-2 帧):只等还在路上的 id
                image, mask_state = ownship_mask_step2(
                    image, mask_cache, ownship_cache, mask_fid)
                mask_stats[{"mask": 0, "polygon": 1, "none": 2}[mask_state]] += 1
                if diag_dir is not None and mask_state == "mask" and rx % 60 == 0:
                    cv2.imwrite(str(diag_dir / "apply.jpg"), image)  # 填充落位证据(垂直镜像/覆盖缺口目检)
            if args.dump_frame and rx % 600 == 0:  # first frame + every ~60 s (10 fps budget) — last dump = latest view
                cv2.imwrite(args.dump_frame, image)
                print(f"[detector] feed frame dumped -> {args.dump_frame} (mount {meta.get('mount_id', '')} seq {meta.get('frame_seq')})")
            if sahi_model is not None:
                # SAHI 无 classes 参数：船类在输出侧过滤；conf 用构造阈值
                detections, infer_ms = run_sliced_inference(sahi_model, image)
                detections = [d for d in detections if d["class_id"] in boat_ids]
            else:
                detections, infer_ms = run_inference(model, image, confidence, boat_ids, args.device, args.imgsz)
            if diag_dir is not None and mask_state == "none" and detections:
                cause, fid = classify_mask_none(image, meta, mask_cache)
                key = cause.split("(")[0]
                diag_causes[key] = diag_causes.get(key, 0) + 1
                now = time.time()
                if now - diag_last_dump >= 5.0:
                    diag_last_dump = now
                    cv2.imwrite(str(diag_dir / "leak-suspect.jpg"), image)
                    print(f"[detector] LEAK-SUSPECT rx={rx} fid={fid} cause={cause} det={len(detections)}"
                          f" causes={diag_causes}")
            pub.send_multipart([args.out_topic.encode("utf-8"),
                                result_json(meta, detections, args.source).encode("utf-8")])
            rx += 1
            tx += 1
            if args.forward_url:
                # P3-S2 observations forward branch (default off; payload mount
                # lookup can raise — forward_branch catches it, one frame dropped).
                forward_branch(args, args.forward_url,
                               observation_payload(meta, detections, args.source, args.forward_mount),
                               rx, forward_stats, "forward")
            if args.viewport_forward_url:
                # DT 视口分流(默认关):含空检测帧逐条 POST,失败丢帧不致命。
                forward_branch(args, args.viewport_forward_url,
                               viewport_payload(meta, detections, mask_state),
                               rx, viewport_stats, "viewport-forward")
            if rx == 1 or rx % args.log_every == 0:
                mask_line = (f" masked={mask_stats[0]} mask_fb_poly={mask_stats[1]} mask_miss={mask_stats[2]}"
                             + (f" mask_rx={mask_cache.received} mask_bad={mask_cache.malformed}"
                                if mask_cache is not None else "")
                             + (f" poly_pulls={ownship_cache.pulled} poly_errors={ownship_cache.errors}"
                                if ownship_cache is not None else "")
                             + (f" none_causes={diag_causes}" if diag_dir is not None else "")) if (mask_cache or ownship_cache) else ""
                print(f"[detector] rx={rx} tx={tx} seq={meta.get('frame_seq')} "
                      f"infer={infer_ms:.1f}ms conf={confidence:.2f} detections={len(detections)}{mask_line}")
    except KeyboardInterrupt:
        print(f"[detector] shutdown: rx={rx} tx={tx} forwarded={forward_stats[0]} "
              f"forward_errors={forward_stats[1]} viewport_forwarded={viewport_stats[0]} "
              f"viewport_forward_errors={viewport_stats[1]} masked={mask_stats[0]} "
              f"mask_fb_poly={mask_stats[1]} mask_miss={mask_stats[2]}")
    finally:
        sub.close(0)
        if mask_sub is not None:
            mask_sub.close(0)
        pub.close(0)
        ctx.term()
        if args.pidfile:
            Path(args.pidfile).unlink(missing_ok=True)
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
