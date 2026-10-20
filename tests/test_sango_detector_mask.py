"""P1 本船掩膜下沉检测端 + 路线A 逐像素掩膜通道测试(tools/sango_detector_service.py).

P1(多边形回退):FRAME_MARKER 像素行解码移植(web decodeFrameMarker 同源语义:
块均值+歧义窗 fail-closed+魔数/校验)、海灰+轻噪填充与越界角点裁剪、
OwnshipPolygonCache 按 frame_id 精确匹配/未命中/失败退避。

路线A(ownship-mask-v1,主路径):RLE 解码黄金向量(与 C# EncodeRle 对拍,顶行
先行)、契约违约 fail-open、位图应用(NEAREST 缩放/膨胀/海灰填充)、OwnshipMaskCache
环形缓存、ownship_mask_step2 降级链(mask→polygon→none)、drain_ownship_mask_socket
真 ZMQ inproc 往返、viewport_payload 命中态透传。

真实 YOLO 权重推理验证(uv 部署件)在本测试环境无 ultralytics——检测器加载点
已延迟 import,真实推理路径由 a4000 部署侧 selftest 覆盖(见 risks 记录)。
"""

from __future__ import annotations

import importlib.util
import json
import threading
import time
from pathlib import Path

import cv2
import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "sango_detector_service", REPO_ROOT / "tools" / "sango_detector_service.py")
detector = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(detector)

SEA_GRAY_BASE = detector.OWNSHIP_MASK_GRAY  # ≈115 = 0.45×255


def marker_bits(frame_id: int) -> int:
    """TwinSituationMath.MarkerBits 同源:0xD3 魔数 + 16bit frame + 校验."""
    value = frame_id & 0xFFFF
    check = ((value >> 8) ^ value ^ 0x5A) & 0xFF
    return 0xD3000000 | (value << 8) | check


def synthetic_marker_frame(frame_id: int, width: int = 1280, height: int = 720,
                           bits_override: int | None = None) -> np.ndarray:
    """按 Unity EnsureMarker 几何合成:顶部 256×16 条,32 格 × 8px 黑/白."""
    image = np.full((height, width, 3), 60, np.uint8)  # 海面底色
    bits = marker_bits(frame_id) if bits_override is None else bits_override
    for index in range(32):
        on = (bits >> (31 - index)) & 1
        image[0:16, index * 8:(index + 1) * 8] = 255 if on else 0
    return image


# ── FRAME_MARKER 解码移植 ────────────────────────────────────────────────

@pytest.mark.parametrize("frame_id", [0, 1, 1234, 65535])
def test_decode_frame_marker_round_trips_known_frame_ids(frame_id):
    assert detector.decode_frame_marker(synthetic_marker_frame(frame_id)) == frame_id


def test_decode_frame_marker_fail_closed_on_ambiguous_gray():
    image = synthetic_marker_frame(0)
    image[0:16, 0:256] = 128  # 压缩歧义灰:全条不可判读
    assert detector.decode_frame_marker(image) is None


def test_decode_frame_marker_rejects_bad_magic_and_checksum():
    assert detector.decode_frame_marker(synthetic_marker_frame(0, bits_override=0xFFFFFFFF)) is None
    corrupted = marker_bits(7) ^ 1  # 翻转校验位最低位
    assert detector.decode_frame_marker(synthetic_marker_frame(7, bits_override=corrupted)) is None


def test_decode_frame_marker_returns_none_for_small_images():
    assert detector.decode_frame_marker(np.zeros((50, 100, 3), np.uint8)) is None


# ── 海灰填充 ─────────────────────────────────────────────────────────────

def corner(x: float, y: float, in_frame: bool = True) -> dict:
    return {"x": x, "y": y, "depth": 48.5, "in_frame": in_frame}


OWN_BOX = [corner(.25, .5), corner(.55, .5), corner(.55, .9), corner(.25, .9)]


def test_apply_ownship_mask_paints_sea_gray_plus_light_noise_inside_only():
    image = np.full((720, 1280, 3), 200, np.uint8)  # 亮甲板作画布,便于看出填充
    masked = detector.apply_ownship_mask(image, OWN_BOX, rng=np.random.default_rng(7))
    inside = masked[500:600, 400:500].astype(np.float32)  # 多边形内部采样窗
    assert 110 <= inside.mean() <= 120, "海灰 ≈0.45×255"
    assert 1.0 <= inside.std() <= 15.0, "轻噪存在且幅度受控(σ≈5/通道)"
    assert masked[0, 1279].tolist() == [200, 200, 200], "多边形外原样保留"
    assert image[500, 400].tolist() == [200, 200, 200], "原帧不被就地修改"


def test_apply_ownship_mask_skips_degenerate_and_clips_out_of_frame_corners():
    image = np.full((720, 1280, 3), 200, np.uint8)
    assert detector.apply_ownship_mask(image, []) is image, "<3 角点原样返回"
    assert detector.apply_ownship_mask(image, OWN_BOX[:2]) is image
    out_of_frame = [corner(-.2, .4, False), corner(.3, .4, False), corner(.3, .8), corner(-.2, .8)]
    masked = detector.apply_ownship_mask(image, out_of_frame, rng=np.random.default_rng(3))
    assert masked[500:600, 0:100].mean() < 200, "越界角点裁剪到画面,出画侧仍覆盖"
    assert masked[0, 1279].tolist() == [200, 200, 200]


# ── 多边形缓存:frame_id 精确匹配 ────────────────────────────────────────

def make_cache(payload=None, error=None, times=(0.0, 1.0, 2.0, 3.0, 4.0, 5.0)) -> tuple:
    calls = {"pulls": 0}

    def fetch(url: str, timeout_s: float) -> dict:
        calls["pulls"] += 1
        if error is not None:
            raise error
        return payload

    clock = iter(times)
    cache = detector.OwnshipPolygonCache(
        "http://poly.test/api/viewport-ownship-polygon",
        fetch=fetch, clock=lambda: next(clock))
    return cache, calls


def test_cache_exact_frame_match_hit_empty_and_miss():
    payload = {"frames": [{"frame_id": 10, "polygon": OWN_BOX}, {"frame_id": 11, "polygon": []}]}
    cache, calls = make_cache(payload, times=(0.0, 0.1))
    assert cache.maybe_refresh() is True and calls["pulls"] == 1
    assert cache.polygon_for(10) == OWN_BOX, "命中帧返回 4 角点"
    assert cache.polygon_for(11) == [], "空多边形=该帧明确无掩膜(与未命中区分)"
    assert cache.polygon_for(12) is None, "未命中(缓存尚无此帧)"
    assert cache.maybe_refresh() is False, "节流窗内不重复拉取"


def test_cache_failure_keeps_last_snapshot_and_backs_off():
    payload = {"frames": [{"frame_id": 1, "polygon": OWN_BOX}]}
    cache, calls = make_cache(payload, times=(0.0, 0.2, 1.0))
    cache.maybe_refresh()  # t=0.0 成功
    cache._fetch = lambda url, timeout_s: (_ for _ in ()).throw(ConnectionError("down"))
    assert cache.maybe_refresh() is True and cache.errors == 1, "t=0.2 越过节流窗:失败也算一次拉取"
    assert cache.polygon_for(1) == OWN_BOX, "失败保旧缓存"
    assert cache.maybe_refresh() is False, "t=1.0 仍在 2s 退避窗内,不打后端"


def test_cache_replaces_whole_table_not_merges():
    cache, _ = make_cache({"frames": [{"frame_id": 1, "polygon": OWN_BOX}]}, times=(0.0, 5.0))
    cache.maybe_refresh()
    cache._fetch = lambda url, timeout_s: {"frames": [{"frame_id": 2, "polygon": OWN_BOX}]}
    cache.maybe_refresh()
    assert cache.polygon_for(1) is None and cache.polygon_for(2) == OWN_BOX


# ── 掩膜步:合成帧本船区域检出被抑制;缺 polygon 不崩 ────────────────────

def test_fetch_ownship_polygon_over_real_loopback_http():
    """真 HTTP 往返(127.0.0.1 临时端口):GET 方法/路径/JSON 解析/不吃代理."""
    from http.server import BaseHTTPRequestHandler, HTTPServer  # noqa: PLC0415 — 测试内局部服务器

    payload = {"schema": "viewport_ownship_polygon@1",
               "frames": [{"frame_id": 3, "polygon": OWN_BOX}]}
    seen = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            seen.append((self.command, self.path))
            body = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        result = detector.fetch_ownship_polygon(
            f"http://127.0.0.1:{server.server_port}/api/viewport-ownship-polygon", 2.0)
    finally:
        server.shutdown()
        server.server_close()
    assert seen == [("GET", "/api/viewport-ownship-polygon")]
    assert result["frames"][0]["frame_id"] == 3 and result["frames"][0]["polygon"] == OWN_BOX


def bright_blob_centers(image) -> list[tuple[float, float]]:
    """占位检测器:亮块(≥200)连通域中心,与真实检测器同吃亮度对比特征.

    顶部 256×16 marker 条本身是黑白格,不计入(排除 y<20 带).
    """
    gray = image.astype(np.float32).mean(axis=2)
    bright = (gray >= 200).astype(np.uint8)
    bright[:20, :] = 0
    count, _, stats, centroids = cv2.connectedComponentsWithStats(bright)
    return [tuple(np.round(c, 1)) for c in centroids[1:]]  # 0 号=背景


def synthetic_ownship_scene(frame_id: int) -> np.ndarray:
    """海面上两个亮块:本船甲板(OWN_BOX 内)+ 远处目标船(框外)."""
    image = synthetic_marker_frame(frame_id)  # 含 marker 条
    image[520:640, 340:660] = 250   # 本船甲板(OWN_BOX 内,归一化 x∈[.25,.55] y∈[.5,.9])
    image[300:340, 900:1000] = 250  # 目标船(OWN_BOX 外,不得被掩)
    return image


def test_ownship_mask_step_suppresses_ownship_region_and_keeps_target():
    payload = {"frames": [{"frame_id": 4171, "polygon": OWN_BOX}]}
    cache, _ = make_cache(payload)
    image = synthetic_ownship_scene(4171)
    before = bright_blob_centers(image)
    masked, state = detector.ownship_mask_step2(image, None, cache)
    assert state == "polygon"
    after = bright_blob_centers(masked)
    assert len(before) == 2 and len(after) == 1, "本船亮块被海灰掩掉,只剩目标船"
    assert any(abs(cx - 950) < 30 and abs(cy - 320) < 30 for cx, cy in after), "目标船原位保留"
    assert not any(abs(cx - 500) < 80 and abs(cy - 580) < 80 for cx, cy in after), "本船区域不再有可检出亮块"


def test_ownship_mask_step_missing_polygon_or_marker_is_graceful_noop():
    image = synthetic_ownship_scene(4171)
    no_polygon_cache, _ = make_cache({"frames": []})  # 后端从未写入/帧未命中
    out, state = detector.ownship_mask_step2(image, None, no_polygon_cache)
    assert state == "none" and out is image, "缓存空:原帧直通不崩"
    empty_polygon_cache, _ = make_cache({"frames": [{"frame_id": 4171, "polygon": []}]})
    out, state = detector.ownship_mask_step2(image, None, empty_polygon_cache)
    assert state == "none" and out is image, "空多边形(明确无掩膜):原帧直通"
    cache, _ = make_cache({"frames": [{"frame_id": 4171, "polygon": OWN_BOX}]})
    no_marker = image.copy()
    no_marker[0:16, 0:256] = 128  # marker 歧义 → 解码 None
    out, state = detector.ownship_mask_step2(no_marker, None, cache)
    assert state == "none" and out is no_marker, "无 marker:跳过掩膜不崩"


# ── 路线A:RLE 解码(ownship-mask-v1 §3,与 C# EncodeRle 黄金向量对拍)────────

GOLDEN_RLE = bytes([0x04, 0x00, 0x01, 0x00, 0x02, 0x00, 0x01, 0x00, 0x04, 0x00])
GOLDEN_BITMAP = np.array([[0, 0, 0, 0], [0, 1, 1, 0], [0, 0, 0, 0]], dtype=bool)


def test_decode_mask_rle_matches_frozen_golden_vector():
    assert np.array_equal(detector.decode_mask_rle(GOLDEN_RLE, 4, 3), GOLDEN_BITMAP)


def test_decode_mask_rle_all_zero_mask():
    payload = (640).to_bytes(2, "little") * 3  # 3 行全 0
    assert detector.decode_mask_rle(payload, 640, 3) is not None
    assert not detector.decode_mask_rle(payload, 640, 3).any()


def test_decode_mask_rle_leading_zero_run_when_row_starts_white():
    payload = (0).to_bytes(2, "little") + (2).to_bytes(2, "little") + (1).to_bytes(2, "little")
    assert np.array_equal(detector.decode_mask_rle(payload, 3, 1),
                          np.array([[1, 1, 0]], dtype=bool))


@pytest.mark.parametrize("payload,width,height", [
    (b"\x01", 4, 3),          # 奇数字节长度
    (bytes([4, 0]) * 3, 4, 4),  # 行数不足(height 消费不完整)
    (bytes([5, 0]), 4, 1),    # 单游程越行宽
    (bytes([0, 0, 5, 0]), 4, 1),  # 行游程和≠width
    (bytes([4, 0, 1, 0]), 4, 1),  # 游程跨行共享(第二行缺数据)
    (bytes([0, 0, 0, 0]), 0, 1),  # 非法 width
])
def test_decode_mask_rle_fail_open_on_contract_violations(payload, width, height):
    assert detector.decode_mask_rle(payload, width, height) is None


def test_decode_mask_rle_trailing_garbage_rejected():
    assert detector.decode_mask_rle(GOLDEN_RLE + b"\x01\x00", 4, 3) is None


# ── 路线A:位图应用(缩放/膨胀/海灰)────────────────────────────────────────

def bitmap_mask_from_box(height: int, width: int, x0, y0, x1, y1) -> np.ndarray:
    mask = np.zeros((height, width), dtype=bool)
    mask[y0:y1, x0:x1] = True
    return mask


def test_apply_ownship_bitmap_mask_paints_inside_and_dilates_edges():
    image = np.full((720, 1280, 3), 200, np.uint8)
    mask = bitmap_mask_from_box(720, 1280, 400, 300, 600, 400)  # 与图像同域
    masked, applied = detector.apply_ownship_bitmap_mask(image, mask, rng=np.random.default_rng(11))
    assert applied is True
    assert 110 <= masked[320:380, 450:550].astype(np.float32).mean() <= 120, "海灰≈0.45×255"
    assert 1.0 <= masked[320:380, 450:550].astype(np.float32).std() <= 15.0
    assert masked[301, 399].mean() < 200, "膨胀 3px:掩膜边缘外邻域也被覆盖"
    assert masked[100, 100].tolist() == [200, 200, 200], "远处原样保留"
    assert image[320, 450].tolist() == [200, 200, 200], "原帧不被就地修改"


def test_apply_ownship_bitmap_mask_resizes_smaller_truth_mask():
    image = np.full((720, 1280, 3), 200, np.uint8)
    mask = bitmap_mask_from_box(360, 640, 200, 150, 300, 200)  # 640×360 真值 → 1280×720 帧
    masked, applied = detector.apply_ownship_bitmap_mask(image, mask)
    assert applied is True
    assert masked[310:390, 420:580].astype(np.float32).mean() < 200, "2× 缩放后区域覆盖"
    assert masked[100, 100].tolist() == [200, 200, 200]


def test_apply_ownship_bitmap_mask_empty_mask_is_noop():
    image = np.full((720, 1280, 3), 200, np.uint8)
    out, applied = detector.apply_ownship_bitmap_mask(image, np.zeros((360, 640), dtype=bool))
    assert applied is False and out is image, "空掩膜=权威无操作"


# ── 路线A:掩膜环形缓存 + step2 降级链 + ZMQ 排空 ──────────────────────────

def rle_for_box(width: int, height: int, x0, y0, x1, y1) -> bytes:
    out = bytearray()
    for row in range(height):
        runs, value, run = [], 0, 0
        for col in range(width):
            bit = 1 if (y0 <= row < y1 and x0 <= col < x1) else 0
            if bit == value:
                run += 1
            else:
                runs.append(run)
                value, run = bit, 1
        runs.append(run)  # 行尾游程(全 0 行=单游程 width)
        for r in runs:
            out += r.to_bytes(2, "little")
    return bytes(out)


def test_ownship_mask_cache_ring_evicts_oldest_and_overwrites_same_frame():
    cache = detector.OwnshipMaskCache(capacity=4)
    for frame_id in range(6):
        cache.put(frame_id, b"\x04\x00", 4, 1)
    assert cache.entry_for(0) is None and cache.entry_for(1) is None, "超容丢最旧"
    assert cache.entry_for(5) == (b"\x04\x00", 4, 1)
    cache.put(5, b"\x08\x00", 8, 1)
    assert cache.entry_for(5) == (b"\x08\x00", 8, 1), "同 frame_id 后发覆盖"


def test_ownship_mask_step2_mask_hit_beats_polygon_fallback():
    mask_cache = detector.OwnshipMaskCache()
    # 本船甲板亮块区(340:660 × 520:640 → 640×360 真值域减半)掩膜
    mask_cache.put(4171, rle_for_box(640, 360, 170, 260, 330, 320), 640, 360)
    payload = {"frames": [{"frame_id": 4171, "polygon": OWN_BOX}]}
    polygon_cache, _ = make_cache(payload)
    image = synthetic_ownship_scene(4171)
    masked, state = detector.ownship_mask_step2(image, mask_cache, polygon_cache)
    assert state == "mask", "掩膜命中优先于多边形"
    after = bright_blob_centers(masked)
    assert len(after) == 1 and any(abs(cx - 950) < 30 for cx, cy in after), "本船掩掉,目标船保留"


def test_ownship_mask_step2_falls_back_to_polygon_on_mask_miss_or_corruption():
    image = synthetic_ownship_scene(4171)
    payload = {"frames": [{"frame_id": 4171, "polygon": OWN_BOX}]}
    polygon_cache, _ = make_cache(payload)
    empty_mask_cache = detector.OwnshipMaskCache()
    _, state = detector.ownship_mask_step2(image, empty_mask_cache, polygon_cache)
    assert state == "polygon", "掩膜未命中 → 多边形回退"
    corrupt_mask_cache = detector.OwnshipMaskCache()
    corrupt_mask_cache.put(4171, b"\x99\x99", 4, 3)  # 契约违约
    out, state = detector.ownship_mask_step2(image, corrupt_mask_cache, polygon_cache)
    assert state == "polygon", "掩膜损坏 → fail-open 走多边形"


def test_ownship_mask_step2_empty_mask_is_authoritative_no_mask():
    mask_cache = detector.OwnshipMaskCache()
    mask_cache.put(4171, (640).to_bytes(2, "little") * 360, 640, 360)  # 全 0 掩膜
    payload = {"frames": [{"frame_id": 4171, "polygon": OWN_BOX}]}
    polygon_cache, _ = make_cache(payload)
    image = synthetic_ownship_scene(4171)
    out, state = detector.ownship_mask_step2(image, mask_cache, polygon_cache)
    assert state == "none" and out is image, "空掩膜=本船不在画,权威无操作(不走多边形)"


def test_drain_ownship_mask_socket_over_real_zmq_roundtrip():
    import zmq

    ctx = zmq.Context.instance()
    pub = ctx.socket(zmq.PUB)
    port = pub.bind_to_random_port("tcp://127.0.0.1")
    sub = ctx.socket(zmq.SUB)
    sub.setsockopt(zmq.SUBSCRIBE, b"sango.ownship_mask")
    sub.connect(f"tcp://127.0.0.1:{port}")
    time.sleep(0.2)  # PUB/SUB 订阅传播
    good_meta = json.dumps({"schema": "ownship_mask@1", "frame_id": 77, "width": 4,
                            "height": 3, "rle_bytes": len(GOLDEN_RLE)}).encode()
    pub.send_multipart([b"sango.ownship_mask", good_meta, GOLDEN_RLE])
    pub.send_multipart([b"sango.ownship_mask", b"not json", GOLDEN_RLE])  # 坏消息
    pub.send_multipart([b"other.topic", good_meta, GOLDEN_RLE])           # 陌生主题
    time.sleep(0.2)
    cache = detector.OwnshipMaskCache()
    drained = detector.drain_ownship_mask_socket(sub, cache)
    assert drained >= 1
    assert cache.received == 1 and cache.malformed >= 1, "好入环、坏计费丢弃"
    assert cache.entry_for(77) == (GOLDEN_RLE, 4, 3)
    # 空队列排空立即返回
    assert detector.drain_ownship_mask_socket(sub, cache) == 0
    sub.close(0)
    pub.close(0)


def test_viewport_payload_carries_ownship_mask_state():
    payload = detector.viewport_payload({"frame_time_s": 1.5, "width": 1280, "height": 720}, [], "mask")
    assert payload["ownship_mask"] == "mask"
    assert detector.viewport_payload({}, [], "polygon")["ownship_mask"] == "polygon"
    assert detector.viewport_payload({}, [])["ownship_mask"] == "none"


# ── 修复批(20261020 误检根因):gst tap 720p 帧像素 marker 缩放后不可解码──
# (4px 格+JPEG 落歧义窗,实测全量 mask_miss),frame_id 改由 sender 元数据
# 在全分辨率侧解码直供;像素解码降级为 FramePublisher 直连路径后备。

def test_ownship_mask_step2_prefers_metadata_frame_id_over_pixel_decode():
    mask_cache = detector.OwnshipMaskCache()
    mask_cache.put(900, rle_for_box(640, 360, 170, 260, 330, 320), 640, 360)
    image = synthetic_ownship_scene(999)  # 像素 marker=999,与掩膜帧 900 不同
    masked, state = detector.ownship_mask_step2(image, mask_cache, None, frame_id=900)
    assert state == "mask", "sender 元数据 frame_id 直接驱动匹配,不看像素"
    assert len(bright_blob_centers(masked)) == 1, "本船亮块掩掉,目标船保留"


def test_ownship_mask_step2_ignores_invalid_metadata_frame_id():
    mask_cache = detector.OwnshipMaskCache()
    mask_cache.put(900, rle_for_box(640, 360, 170, 260, 330, 320), 640, 360)
    image = synthetic_ownship_scene(900)  # 像素 marker 可解且命中
    for bad in ("garbage", -1, 65536, None):
        out, state = detector.ownship_mask_step2(image, mask_cache, None, frame_id=bad)
        assert state == "mask", f"无效 meta({bad!r})回退像素解码照常命中"


def test_wait_for_mask_picks_up_late_arrival():
    """读回晚到竞态(20261020 race≈12%):等待窗口内补收 → 命中 True。"""
    import zmq

    ctx = zmq.Context.instance()
    pub = ctx.socket(zmq.PUB)
    port = pub.bind_to_random_port("tcp://127.0.0.1")
    sub = ctx.socket(zmq.SUB)
    sub.setsockopt(zmq.SUBSCRIBE, b"sango.ownship_mask")
    sub.connect(f"tcp://127.0.0.1:{port}")
    time.sleep(0.2)
    cache = detector.OwnshipMaskCache()
    late_meta = json.dumps({"schema": "ownship_mask@1", "frame_id": 31, "width": 4,
                            "height": 3, "rle_bytes": len(GOLDEN_RLE)}).encode()
    threading.Timer(0.01, lambda: pub.send_multipart([b"sango.ownship_mask", late_meta, GOLDEN_RLE])).start()
    assert detector.wait_for_mask(sub, cache, 31, budget_s=1.0) is True, "晚到掩膜应被窗口内补收"
    assert cache.entry_for(31) == (GOLDEN_RLE, 4, 3)
    # 真超时:无人再发,快速预算内返回 False
    t0 = time.perf_counter()
    assert detector.wait_for_mask(sub, cache, 32, budget_s=0.02) is False
    assert time.perf_counter() - t0 < 0.5, "超时应立即返回,不悬挂"
    sub.close(0)
    pub.close(0)


def test_ownship_mask_cache_newest_id_tracks_insertion_order():
    """wait_for_mask 门控的输入:插入序末位即最新 id;同 id 重复 put 不挪位(值同无碍)。"""
    cache = detector.OwnshipMaskCache()
    assert cache.newest_id is None, "空环返 None"
    for fid in (10, 11, 12):
        cache.put(fid, GOLDEN_RLE, 4, 3)
    assert cache.newest_id == 12
    cache.put(10, GOLDEN_RLE, 4, 3)  # marker 静止期重复发布:保留原位
    assert cache.newest_id == 12
    cache.put(13, GOLDEN_RLE, 4, 3)
    assert cache.newest_id == 13


def test_wait_for_mask_skips_ids_that_cannot_arrive():
    """三期实锤:tap 视频跑赢掩膜读回 1-2 帧(want 超前 ring 最新);反之想要 id
    已滑到最新之前(环内空洞/滑出环底)则永不再来——必须立即 miss,不吃满预算。"""
    cache = detector.OwnshipMaskCache()
    for fid in (28, 29, 31):  # 30 = 环内空洞;5 = 远古旧 id
        cache.put(fid, GOLDEN_RLE, 4, 3)
    for stale in (30, 5):
        t0 = time.perf_counter()
        assert detector.wait_for_mask(None, cache, stale, budget_s=5.0) is False
        assert time.perf_counter() - t0 < 0.5, f"过时 id({stale})不应空等"


def test_wait_for_mask_waits_only_for_ids_ahead_of_ring():
    """want 超前 newest ≤64 id(读回在路上,u16 环回含此判)才消费等待预算。"""
    import zmq

    ctx = zmq.Context.instance()
    pub = ctx.socket(zmq.PUB)
    port = pub.bind_to_random_port("tcp://127.0.0.1")
    sub = ctx.socket(zmq.SUB)
    sub.setsockopt(zmq.SUBSCRIBE, b"sango.ownship_mask")
    sub.connect(f"tcp://127.0.0.1:{port}")
    cache = detector.OwnshipMaskCache()
    cache.put(31, GOLDEN_RLE, 4, 3)
    t0 = time.perf_counter()
    assert detector.wait_for_mask(sub, cache, 32, budget_s=0.05) is False, "超时返 False"
    assert time.perf_counter() - t0 >= 0.04, "超前 id 应真等(读回竞态)"
    cache.put(65530, GOLDEN_RLE, 4, 3)
    t0 = time.perf_counter()
    assert detector.wait_for_mask(sub, cache, 2, budget_s=0.03) is False
    assert time.perf_counter() - t0 >= 0.02, "u16 环回跨零也算超前(模距 8)"
    sub.close(0)
    pub.close(0)


# ── 船类过滤自适应(20261020 yolov18.pt 单类 'vessel' 接入)────────────────

def test_boat_class_ids_maritime_single_class_vessel():
    assert detector.boat_class_ids({0: "vessel"}) == [0]


def test_boat_class_ids_coco_boat_stays_id8():
    names = {i: n for i, n in enumerate(
        ["person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat"])}
    assert detector.boat_class_ids(names) == [8]


def test_boat_class_ids_collects_multiple_ship_synonyms():
    assert detector.boat_class_ids({0: "ship", 3: "car", 5: "fishing vessel", 7: "Watercraft"}) == [0, 5, 7]


def test_boat_class_ids_no_boat_class_falls_back_to_coco8():
    assert detector.boat_class_ids({0: "car", 1: "person"}) == [detector.COCO_BOAT_CLASS_ID]
    assert detector.boat_class_ids(None) == [detector.COCO_BOAT_CLASS_ID]
