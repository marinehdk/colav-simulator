"""P3 检测→跟踪层:viewport detections → observations/IPDA → viewport_tracks@1.

覆盖(契约 colav_simulator/schemas/viewport_tracks_v1.py;遥测顶层键
``viewport_tracks``,无跟踪步/过期 >2s 时键整体缺省):
- 合成机位几何:垂直 FOV → 水平 FOV(方像素 pinhole)、yaw → 方位角;
- 视口帧 georef:绝对场景 NE 锚在相机位姿、bearing 偏移、径向协方差;
- 核心晋升链:合成检测序列(P1 中继位姿同形)→ ExternalCameraSensor 记录缓存
  → vimmjipda IPDA 步进 → 存在概率过确认门晋升 confirmed → viewport_tracks@1
  文档形状 + 滤波后 brg/rng 对拍真值(vimmjipda 外部仓缺席时整段 skip);
- gui_server 接线:POST viewport-detections 跟踪腿喂料/PAUSED 只显示、无中继
  位姿不建服务、遥测注入体形状与过期丢键、compact transport 顶层键存活。
"""

from __future__ import annotations

import logging
import math
import threading
import time
from collections import deque
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import yaml
from fastapi.testclient import TestClient

import gui_server.main as gui_main
from colav_simulator.core.mast_cameras import focal_px
from colav_simulator.core.viewport_tracks import (
    ViewportTrackService,
    camera_pose_valid,
    georeference_viewport_frame,
    viewport_hfov_deg,
    viewport_mount,
)
from colav_simulator.experiment.contracts import SessionState
from colav_simulator.integrations.registry import IntegrationRegistry
from colav_simulator.schemas.observations_v1 import ObservationFrame

WIDTH, HEIGHT = 1280, 720
#: 与 TwinBridgeCameraPose / P1 中继回显同形(免会话单槽的 camera_pose 字段)。
POSE = {"east": 0.0, "north": 0.0, "height_m": 12.0, "yaw_deg": 0.0, "pitch_deg": -3.0, "fov_deg": 60.0}
OWN = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0])


def viewport_fusion_available() -> bool:
    return IntegrationRegistry().statuses()["vimmjipda"].available


def pixel_box_for(pose: dict, north: float, east: float, prior_m: float = 2.5) -> list[float]:
    """真值 NE → 视口像素框(georeference_box 的逆:u 心由 bearing、框高由距离)."""
    mount = viewport_mount(pose, WIDTH, HEIGHT)
    fx = focal_px(mount.hfov_deg, WIDTH)
    rng = math.hypot(north - float(pose["north"]), east - float(pose["east"]))
    bearing_offset = math.atan2(east - float(pose["east"]), north - float(pose["north"])) - math.radians(
        float(pose["yaw_deg"])
    )
    u = WIDTH / 2 + fx * math.tan(bearing_offset)
    height_px = max(fx * prior_m / rng, 2.0)
    return [u - 15.0, 300.0, u + 15.0, 300.0 + height_px]


def synthetic_frame(pose: dict, north: float, east: float) -> list[dict]:
    return [
        {
            "box_xyxy": pixel_box_for(pose, north, east),
            "class_id": 8,
            "class_name": "boat",
            "confidence": 0.9,
        }
    ]


# ── 合成机位几何 ───────────────────────────────────────────────────────────────


class TestViewportMount:
    def test_vertical_fov_expands_to_horizontal_via_aspect(self) -> None:
        # 方像素 pinhole:tan(hfov/2) = aspect·tan(vfov/2);60° 垂直 + 16:9。
        expected = math.degrees(2.0 * math.atan(16 / 9 * math.tan(math.radians(30.0))))
        assert viewport_hfov_deg(60.0, 1280, 720) == pytest.approx(expected)
        assert viewport_hfov_deg(60.0, 1280, 720) == pytest.approx(91.49, abs=0.01)

    def test_mount_carries_camera_yaw_as_azimuth(self) -> None:
        mount = viewport_mount({**POSE, "yaw_deg": 90.0}, WIDTH, HEIGHT)
        assert mount.azimuth_deg == pytest.approx(90.0)
        assert mount.mount_id == "viewport" and mount.channel == "camera_eo"
        assert mount.frame_width_px == WIDTH and mount.frame_height_px == HEIGHT


# ── 视口帧 georef(绝对 NE 锚在相机) ──────────────────────────────────────────


class TestGeoreferenceViewportFrame:
    def test_pose_validity_gate(self) -> None:
        assert camera_pose_valid(POSE)
        assert not camera_pose_valid(None)
        assert not camera_pose_valid({k: v for k, v in POSE.items() if k != "fov_deg"})
        assert not camera_pose_valid({**POSE, "north": float("nan")})

    def test_records_anchor_at_the_camera_in_absolute_ne(self) -> None:
        pose = {**POSE, "east": 500.0, "north": 6955000.0, "yaw_deg": 0.0}
        records = georeference_viewport_frame(pose, WIDTH, HEIGHT, synthetic_frame(pose, 6955400.0, 500.0), 1.0)
        assert len(records) == 1
        north, east = records[0]["position_ne_m"]
        # 目标在相机正北 400 m:绝对 NE = 相机 + 400 m 北向;非 ownship-相对域。
        assert north == pytest.approx(6955400.0, rel=1e-6)
        assert east == pytest.approx(500.0, abs=1e-6)
        assert records[0]["mount_id"] == "viewport" and records[0]["t_s"] == 1.0

    def test_bearing_offset_and_radial_covariance(self) -> None:
        records = georeference_viewport_frame(POSE, WIDTH, HEIGHT, synthetic_frame(POSE, 400.0, 30.0), 0.5)
        record = records[0]
        bearing = math.atan2(30.0, 400.0)
        assert record["bearing_rad"] == pytest.approx(bearing, abs=1e-9)
        assert record["range_m"] == pytest.approx(math.hypot(400.0, 30.0), rel=1e-6)
        cov = np.array(record["position_cov_ne_m2"])
        assert cov[0][0] > 1.5 * cov[1][1], "bearing 0 附近径向方差 > 横向(契约 §3 E5 同形)"


# ── 核心晋升链:合成序列 → IPDA confirmed → 文档形状 ─────────────────────────


class TestViewportTrackServicePromotion:
    @pytest.fixture(autouse=True)
    def _require_vimmjipda(self) -> None:
        if not viewport_fusion_available():
            pytest.skip("vimmjipda external repo unavailable")

    def feed_sequence(self, steps: int) -> ViewportTrackService:
        """目标以 2 m/s 北向远离、固定 30 m 东偏;0.1s 节拍(视口检测 10Hz)."""
        service = ViewportTrackService()
        for k in range(1, steps + 1):
            t = k * 0.1
            accepted = service.feed(POSE, WIDTH, HEIGHT, synthetic_frame(POSE, 400.0 + 2.0 * t, 30.0), t, OWN)
            assert accepted == 1
        return service

    def test_early_frames_have_no_confirmed_track(self) -> None:
        service = self.feed_sequence(5)
        document = service.document()
        assert document is not None and document["tracks"] == [], "晋升前(存在概率未过确认门)不产 confirmed 航迹"

    def test_sequence_promotes_to_confirmed_with_filtered_state(self) -> None:
        service = self.feed_sequence(60)
        document = service.document()
        assert document is not None
        assert document["schema"] == "viewport_tracks@1"
        assert document["t_s"] == pytest.approx(6.0)
        assert set(document) == {"schema", "t_s", "received_at", "tracks"}
        assert len(document["tracks"]) == 1
        track = document["tracks"][0]
        assert set(track) == {"track_id", "status", "existence_prob", "bearing_rad", "range_m", "north_m", "east_m"}
        assert track["status"] == "confirmed"
        assert track["existence_prob"] > 0.9, "IPDA 存在概率 0.2→0.9 晋升语义(camcolav 锚点)"
        # 滤波后 brg/rng 对拍真值(t=6:北 412 m、东 30 m,ownship 在原点)。
        assert track["north_m"] == pytest.approx(412.0, abs=15.0)
        assert track["east_m"] == pytest.approx(30.0, abs=5.0)
        assert track["range_m"] == pytest.approx(math.hypot(412.0, 30.0), rel=0.05)
        assert track["bearing_rad"] == pytest.approx(math.atan2(30.0, 412.0), abs=1e-2)

    def test_unavailable_tracker_keeps_the_service_inert(self) -> None:
        service = ViewportTrackService(tracker=None)
        service._tracker_ready = True  # 惰性装配已试过且失败(vimmjipda 缺席)
        service.feed(POSE, WIDTH, HEIGHT, synthetic_frame(POSE, 400.0, 30.0), 0.1, OWN)
        assert service.document() is None


# ── gui_server 接线(POST viewport-detections → 遥测注入体) ──────────────────


class _Clock:
    """会话仿真钟替身:每个 POST 前推进 0.1s(检测 10Hz 节拍)."""

    def __init__(self) -> None:
        self.t = 0.0


def fake_manager(state: SessionState = SessionState.CREATED) -> tuple[SimpleNamespace, _Clock]:
    clock = _Clock()
    manager = gui_main.WebSessionManager.__new__(gui_main.WebSessionManager)
    manager.lock = threading.RLock()
    manager._viewport_detection = None
    manager._viewport_track_service = None
    session = SimpleNamespace(
        state=state,
        ship_list=[SimpleNamespace(state=list(OWN))],
        simulator=SimpleNamespace(t=0.0),
    )
    manager.prepared = SimpleNamespace(session=session, manifest=SimpleNamespace(run_id="s1"))
    return manager, clock


def relay_pose(monkeypatch, pose: dict | None) -> None:
    if pose is None:
        monkeypatch.setattr(gui_main, "_ownship_polygon_meta", {})
    else:
        # updated_at = 服务器墙钟(_ingest_ownship_polygon 的真实行为;Q2 龄期门读它)。
        monkeypatch.setattr(gui_main, "_ownship_polygon_meta", {"camera_pose": pose, "updated_at": time.time()})


@pytest.fixture()
def client(monkeypatch) -> tuple[TestClient, SimpleNamespace, _Clock]:
    manager, clock = fake_manager()
    relay_pose(monkeypatch, POSE)
    gui_main._camera_pose_ring.reset()  # 模块级环不跨用例泄漏(同进程测试隔离)
    gui_main._rate_limit_state["last_warn_s"] = 0.0
    monkeypatch.setattr(gui_main, "manager", manager)
    return TestClient(gui_main.app), manager, clock


def post_detection(http: TestClient, north: float, east: float, seq: int) -> None:
    body = {
        "schema": "viewport_detections@1",
        "pts_s": float(seq),
        "width": WIDTH,
        "height": HEIGHT,
        "source": "twin-viewport",
        "detections": synthetic_frame(POSE, north, east),
    }
    assert http.post("/api/sessions/s1/viewport-detections", json=body).status_code == 200


class TestGuiServerWiring:
    @pytest.fixture(autouse=True)
    def _require_vimmjipda(self) -> None:
        if not viewport_fusion_available():
            pytest.skip("vimmjipda external repo unavailable")

    def test_http_sequence_promotes_and_shapes_the_ws_key(self, client) -> None:
        http, manager, clock = client
        for seq in range(1, 61):
            clock.t = seq * 0.1
            manager.prepared.session.simulator.t = clock.t
            post_detection(http, 400.0 + 2.0 * clock.t, 30.0, seq)
        envelope = manager._viewport_tracks_envelope()
        assert set(envelope) == {"viewport_tracks"}
        document = envelope["viewport_tracks"]
        assert document["schema"] == "viewport_tracks@1"
        assert 0.0 <= document["age_s"] <= gui_main.VIEWPORT_TRACKS_MAX_AGE_S
        (track,) = document["tracks"]
        assert track["status"] == "confirmed" and track["existence_prob"] > 0.9
        assert track["range_m"] == pytest.approx(math.hypot(412.0, 30.0), rel=0.05)

    def test_paused_session_displays_but_never_feeds_the_tracker(self, client, monkeypatch) -> None:
        http, manager, _clock = client
        manager.prepared.session.state = SessionState.PAUSED
        post_detection(http, 400.0, 30.0, 1)
        assert manager._viewport_detection is not None, "PAUSED 显示帧照存(绿框必须在)"
        assert manager._viewport_track_service is None, "sim 钟冻结,跟踪腿不喂(记录会积压)"

    def test_missing_relay_pose_skips_the_tracking_leg(self, client, monkeypatch) -> None:
        http, manager, clock = client
        relay_pose(monkeypatch, None)  # P1 中继从未写入
        clock.t = 0.1
        manager.prepared.session.simulator.t = 0.1
        post_detection(http, 400.0, 30.0, 1)
        assert (
            http.post(
                "/api/sessions/s1/viewport-detections",
                json={
                    "schema": "viewport_detections@1",
                    "pts_s": 2.0,
                    "width": WIDTH,
                    "height": HEIGHT,
                    "source": "twin-viewport",
                    "detections": [],
                },
            ).status_code
            == 200
        )
        assert manager._viewport_detection is not None, "显示分流不受跟踪腿影响"
        assert manager._viewport_track_service is None

    def test_stale_document_drops_the_key_entirely(self, client) -> None:
        http, manager, clock = client
        clock.t = 0.1
        manager.prepared.session.simulator.t = 0.1
        post_detection(http, 400.0, 30.0, 1)
        assert manager._viewport_tracks_envelope() != {}, "新鲜跟踪步注入"
        service = manager._viewport_track_service
        service._received_at = time.time() - (gui_main.VIEWPORT_TRACKS_MAX_AGE_S + 0.1)
        assert manager._viewport_tracks_envelope() == {}, "过期(检测断流)键整体缺省 → web 回退 DET"

    def test_no_service_means_no_key(self) -> None:
        manager, _clock = fake_manager()
        assert manager._viewport_tracks_envelope() == {}

    def test_compact_transport_keeps_the_top_level_key(self) -> None:
        payload = {
            "truth": [{"measurements": [1], "tracks": [2]}],
            "viewport_tracks": {"schema": "viewport_tracks@1", "tracks": []},
        }
        compact = gui_main._compact_stream_payload(payload, include_static=True)
        assert compact["viewport_tracks"] == payload["viewport_tracks"]


# ── 评审 Q1-Q4 修复覆盖 ────────────────────────────────────────────────────────


def observations_fake_manager() -> SimpleNamespace:
    """Mast 观测端点替身(test_observations_endpoint 同款 + 位姿环)."""
    manager = gui_main.WebSessionManager.__new__(gui_main.WebSessionManager)
    manager.lock = threading.RLock()
    manager.observation_sensor = None
    manager._observation_seq_gate = {}
    manager._observation_totals = {}
    manager._observation_display_cache = deque(maxlen=512)
    manager._observation_display_lock = threading.Lock()
    manager._ownship_pose_ring = gui_main.OwnshipPoseRing()
    # 收包时刻权威位姿:艏向 90°(东)——与环上采集时刻位姿(艏向 0°/北)故意相左,
    # 用于断言 georef 取的是采集位姿而非收包位姿(评审 Q1 的抹扫场景)。
    manager.prepared = SimpleNamespace(
        session=SimpleNamespace(
            state=SessionState.CREATED,
            ship_list=[SimpleNamespace(state=[6955000.0, 37000.0, math.pi / 2, 0.0, 0.0, 0.0])],
            simulator=SimpleNamespace(t=10.0),
        ),
        manifest=SimpleNamespace(run_id="s1"),
    )
    return manager


MAST_FRAME = {
    "schema_version": "observations@1",
    "frame_seq": 41,
    "frame_time_s": 9.4,  # Unity 域参考戳:维持落库不消费(契约 §5.4 实现偏差,文档化)
    "sensor_id": 2,
    "mount_id": "mast_ptz_eo",
    "source": "yolo-detector",
    "detections": [{"box_xyxy": [280.0, 200.0, 360.0, 280.0], "class_id": 8, "class_name": "boat", "confidence": 0.87}],
}


class TestCaptureTimeGeoref:
    """Q1:georef 用采集时刻位姿(位姿环插值),不再用收包时刻."""

    def test_mast_bearing_uses_capture_pose_and_sim_time(self) -> None:
        manager = observations_fake_manager()
        now = time.time()
        straight = [6955000.0, 37000.0, 0.0, 0.0, 0.0, 0.0]  # 艏向 0°(北),直线
        manager._ownship_pose_ring.sample(now - 0.25, 9.75, straight)
        manager._ownship_pose_ring.sample(now - 0.02, 9.98, straight)
        manager.ingest_observations("s1", ObservationFrame(**MAST_FRAME))
        records = manager.observation_sensor.pending_records()
        assert len(records) == 1
        north_rel, east_rel = records[0]["position_ne_m"]
        # 框居中 → bearing = 采集时刻艏向 0°(北);554.26px 焦距 × 2.5m 先验 / 80px 框高 ≈ 17.3m。
        assert north_rel == pytest.approx(17.32, rel=1e-3), "目标在本船正北(采集位姿)"
        assert abs(east_rel) < 1.0e-6, "若误用收包位姿(90°/东),东向分量会等于距离——正是 Q1 抹扫"
        # 记录 t_s = 采集时刻的 sim 钟(插值),不再是收包 simulator.t=10.0。
        assert 9.75 < records[0]["t_s"] < 9.98

    def test_empty_ring_falls_back_to_receipt_pose(self) -> None:
        manager = observations_fake_manager()  # 环空(未 tick)
        manager.ingest_observations("s1", ObservationFrame(**MAST_FRAME))
        records = manager.observation_sensor.pending_records()
        _north_rel, east_rel = records[0]["position_ne_m"]
        assert east_rel == pytest.approx(17.32, rel=1e-3), "环空回退收包位姿(90°/东)= 修复前行为,有界降级"
        assert records[0]["t_s"] == pytest.approx(10.0)

    def test_capture_latency_constant_mirrors_the_web_side(self) -> None:
        # 与 twin-situation.js DETECTION_CAPTURE_INFERENCE_MS(80)+TAP_MS(50) 同源;
        # 两侧字面量需一起改(双侧注释互相指向)。
        assert gui_main.DETECTION_CAPTURE_LATENCY_S == pytest.approx((80.0 + 50.0) / 1000.0)

    def test_viewport_feed_uses_capture_poses_and_sim_time(self, monkeypatch) -> None:
        manager, clock = fake_manager()
        manager._ownship_pose_ring = gui_main.OwnshipPoseRing()
        now = time.time()
        manager._ownship_pose_ring.sample(now - 0.25, 4.9, list(OWN))
        manager._ownship_pose_ring.sample(now - 0.02, 5.0, list(OWN))
        clock.t = 5.0
        manager.prepared.session.simulator.t = 5.0
        relay_pose(monkeypatch, POSE)
        gui_main._camera_pose_ring.reset()
        gui_main._camera_pose_ring.sample(now - 0.25, {**POSE, "yaw_deg": 0.0})
        gui_main._camera_pose_ring.sample(now - 0.02, {**POSE, "yaw_deg": 0.0})
        monkeypatch.setattr(gui_main, "manager", manager)
        captured: list[dict] = []
        original_feed = gui_main.ViewportTrackService.feed

        def spy_feed(self, camera_pose, *args, **kwargs):  # noqa: ANN001, ANN202
            captured.append(dict(camera_pose))
            return original_feed(self, camera_pose, *args, **kwargs)

        monkeypatch.setattr(gui_main.ViewportTrackService, "feed", spy_feed)
        http = TestClient(gui_main.app)
        post_detection(http, 400.0, 0.0, 1)
        assert captured, "跟踪腿被喂料"
        assert captured[0]["yaw_deg"] == pytest.approx(0.0), "相机位姿取采集时刻环插值(0°),非中继最新回显"
        document = manager._viewport_track_service.document()
        if viewport_fusion_available():
            assert document is not None and 4.9 < document["t_s"] < 5.0, "跟踪步时刻 = 采集时刻 sim 钟(<收包 5.0)"
        else:
            # 喂料/采集位姿断言不依赖跟踪器(上面已过);vimmjipda 缺席时服务惰性
            # 不产文档(test_unavailable_tracker_keeps_the_service_inert 的 HTTP 路径同义)。
            assert document is None, "vimmjipda 缺席:跟踪腿惰性,不得伪造文档"


class TestRelayStalenessGate:
    """Q2:中继 camera_pose 龄期门 = Unity 桥断流的运行时检测(限频告警 + 弃喂)."""

    def test_stale_relay_skips_the_tracking_leg_with_warning(self, client, monkeypatch, caplog) -> None:
        http, manager, clock = client
        relay_pose(monkeypatch, POSE)
        monkeypatch.setattr(gui_main, "_ownship_polygon_meta", {"camera_pose": POSE, "updated_at": time.time() - 5.0})
        gui_main._rate_limit_state["last_warn_s"] = 0.0  # 限频窗复位,确保本用例能出告警
        clock.t = 0.1
        manager.prepared.session.simulator.t = 0.1
        with caplog.at_level(logging.WARNING, logger="gui_server"):
            post_detection(http, 400.0, 30.0, 1)
        assert manager._viewport_detection is not None, "显示分流不受影响"
        assert manager._viewport_track_service is None, "陈旧位姿宁缺毋滥:弃跟踪腿"
        assert any("camera pose relay stale" in record.message for record in caplog.records), "Q2 运行时告警留痕"


class TestPerFrameStepping:
    """Q3:viewport 通道逐帧步进(t 前进即步进,不攒批)."""

    @pytest.fixture(autouse=True)
    def _require_vimmjipda(self) -> None:
        if not viewport_fusion_available():
            pytest.skip("vimmjipda external repo unavailable")

    def test_each_advancing_feed_steps_immediately(self) -> None:
        service = ViewportTrackService()
        for k, t in enumerate((0.1, 0.2, 0.3), start=1):
            service.feed(POSE, WIDTH, HEIGHT, synthetic_frame(POSE, 400.0 + 2.0 * t, 30.0), t, OWN)
            document = service.document()
            assert document is not None and document["t_s"] == pytest.approx(t), f"第 {k} 帧即时步进(不攒批)"
            assert service._sensor.pending_records() == [], "每帧各自 drain,无跨帧批量"

    def test_frozen_t_queues_until_time_advances(self) -> None:
        service = ViewportTrackService()
        service.feed(POSE, WIDTH, HEIGHT, synthetic_frame(POSE, 400.0, 30.0), 0.1, OWN)
        service.feed(POSE, WIDTH, HEIGHT, synthetic_frame(POSE, 402.0, 30.0), 0.1, OWN)  # t 不前进 → 只入队
        assert len(service._sensor.pending_records()) == 1, "冻结时刻的帧积压待步进(暂停/回放边界)"
        service.feed(POSE, WIDTH, HEIGHT, synthetic_frame(POSE, 404.0, 30.0), 0.2, OWN)
        assert service._sensor.pending_records() == []
        assert service.document()["t_s"] == pytest.approx(0.2)


class TestScenarioCadenceAlignment:
    """Q3:head_on_camera(唯一装配 external_cameras 的场景)dt_sim 与 10Hz 检测链对齐."""

    def test_head_on_camera_dt_sim_matches_detector_rate(self) -> None:
        scenario_path = Path(__file__).resolve().parents[1] / "scenarios" / "head_on_camera.yaml"
        document = yaml.safe_load(scenario_path.read_text())
        assert document["dt_sim"] == pytest.approx(0.1), "2Hz tick 会每 tick 攒 ~5 帧批量 drain(评审 Q3)"
