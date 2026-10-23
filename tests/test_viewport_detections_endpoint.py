"""DT 视口 YOLO 检测分流端点 + 遥测注入测试(viewport-detections@1).

覆盖(契约:colav_simulator/schemas/viewport_detections_v1.py;遥测顶层键
``viewport_detections``,无数据/过期 >2s 时键整体缺省):
- POST /api/sessions/{id}/viewport-detections 的 404 / 409 SESSION_NOT_ACCEPTING /
  422 闸(照 observations 端点同款,fake manager 替身);
- 合法 payload 存会话级最新一帧(旧帧被覆写),遥测注入体含契约全字段 +
  detections 原样透传 + 服务器填的 received_at/age_s;
- received_at 过期帧不再注入(键整体缺省);
- _compact_stream_payload 不裁顶层 viewport_detections 键(compact-v1 存活)。
"""

from __future__ import annotations

import os
import signal
import sys
import threading
import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import gui_server.main as gui_main
from colav_simulator.experiment.contracts import SessionState

FRAME_SAMPLE = {
    "schema": "viewport_detections@1",
    "pts_s": 123.456,
    "width": 1280,
    "height": 720,
    "source": "twin-viewport",
    "detections": [
        {"box_xyxy": [100.0, 120.0, 340.0, 260.0], "class_id": 8, "class_name": "boat", "confidence": 0.89}
    ],
}


def fake_manager(state: SessionState = SessionState.CREATED) -> SimpleNamespace:
    manager = gui_main.WebSessionManager.__new__(gui_main.WebSessionManager)
    manager.lock = threading.RLock()
    # twin-viewport 分流存储 attr(此 fake 绕过 __init__,同 test_observations_endpoint)
    manager._viewport_detection = None
    session = SimpleNamespace(state=state)
    manager.prepared = SimpleNamespace(session=session, manifest=SimpleNamespace(run_id="s1"))
    return manager


@pytest.fixture()
def client(monkeypatch) -> tuple[TestClient, SimpleNamespace]:
    manager = fake_manager()
    monkeypatch.setattr(gui_main, "manager", manager)
    return TestClient(gui_main.app), manager


class TestViewportDetectionsEndpoint:
    def test_unknown_session_is_404(self, client) -> None:
        http, _manager = client
        response = http.post("/api/sessions/does-not-exist/viewport-detections", json=FRAME_SAMPLE)
        assert response.status_code == 404
        assert response.json()["detail"] == "SESSION_NOT_FOUND"

    def test_created_session_accepts(self, client) -> None:
        http, _manager = client
        response = http.post("/api/sessions/s1/viewport-detections", json=FRAME_SAMPLE)
        assert response.status_code == 200
        assert response.json() == {"accepted": True, "detections": 1}

    def test_paused_session_accepts_display_only_frames(self, client) -> None:
        """PAUSED 接受(20261015 修订):渲染钟独立,暂停时画面/tap 帧照发,绿框属显示层."""
        http, manager = client
        manager.prepared.session.state = SessionState.PAUSED
        response = http.post("/api/sessions/s1/viewport-detections", json=FRAME_SAMPLE)
        assert response.status_code == 200
        assert response.json() == {"accepted": True, "detections": 1}

    @pytest.mark.parametrize(
        "mutate",
        [
            {"schema": "viewport_detections@2"},
            {"extra_key": True},  # extra=forbid
            {"pts_s": "not-a-number"},
            {"width": 0},
            {"height": -720},
            {"detections": [{"box_xyxy": [1.0, 2.0, 3.0], "class_id": 8, "class_name": "boat", "confidence": 0.5}]},
            {"detections": [{"box_xyxy": [10.0, 10.0, 5.0, 20.0], "class_id": 8, "class_name": "boat", "confidence": 0.5}]},
            {"detections": [{"box_xyxy": [-1.0, 10.0, 30.0, 20.0], "class_id": 8, "class_name": "boat", "confidence": 0.5}]},
            {"detections": [{"box_xyxy": [10.0, 10.0, 30.0, 20.0], "class_id": 8, "class_name": "boat", "confidence": 1.5}]},
        ],
    )
    def test_schema_violations_are_422(self, client, mutate: dict) -> None:
        http, _manager = client
        response = http.post("/api/sessions/s1/viewport-detections", json={**FRAME_SAMPLE, **mutate})
        assert response.status_code == 422

    def test_empty_detections_is_an_authoritative_no_seeing(self, client) -> None:
        http, manager = client
        body = {**FRAME_SAMPLE, "detections": []}
        assert http.post("/api/sessions/s1/viewport-detections", json=body).status_code == 200
        assert manager._viewport_detection["detections"] == []

    def test_only_the_latest_frame_is_kept(self, client) -> None:
        http, manager = client
        assert http.post("/api/sessions/s1/viewport-detections", json={**FRAME_SAMPLE, "pts_s": 1.0}).status_code == 200
        second = {**FRAME_SAMPLE, "pts_s": 2.0, "detections": []}
        assert http.post("/api/sessions/s1/viewport-detections", json=second).status_code == 200
        assert manager._viewport_detection["pts_s"] == 2.0
        assert manager._viewport_detection["detections"] == []

    def test_client_received_at_is_overwritten(self, client) -> None:
        http, manager = client
        before = time.time()
        body = {**FRAME_SAMPLE, "received_at": 1.0}  # 客户端值不作数
        assert http.post("/api/sessions/s1/viewport-detections", json=body).status_code == 200
        assert manager._viewport_detection["received_at"] >= before


class TestTelemetryInjection:
    def test_envelope_matches_contract_and_passes_detections_through(self, client) -> None:
        http, manager = client
        before = time.time()
        assert http.post("/api/sessions/s1/viewport-detections", json=FRAME_SAMPLE).status_code == 200
        envelope = manager._viewport_detections_envelope()
        assert set(envelope) == {"viewport_detections"}
        frame = envelope["viewport_detections"]
        assert frame["schema"] == "viewport_detections@1"
        assert frame["pts_s"] == 123.456
        assert frame["width"] == 1280
        assert frame["height"] == 720
        assert frame["source"] == "twin-viewport"
        assert frame["detections"] == FRAME_SAMPLE["detections"]  # 原样透传
        assert before <= frame["received_at"] <= time.time()  # 服务器收到时刻
        assert 0.0 <= frame["age_s"] <= gui_main.VIEWPORT_DETECTION_MAX_AGE_S

    def test_stale_frame_drops_the_key_entirely(self, client) -> None:
        http, manager = client
        assert http.post("/api/sessions/s1/viewport-detections", json=FRAME_SAMPLE).status_code == 200
        manager._viewport_detection["received_at"] = time.time() - (gui_main.VIEWPORT_DETECTION_MAX_AGE_S + 0.1)
        assert manager._viewport_detections_envelope() == {}

    def test_no_data_means_no_key(self) -> None:
        manager = fake_manager()
        assert manager._viewport_detections_envelope() == {}

    def test_compact_transport_keeps_the_top_level_key(self) -> None:
        # compact-v1 只裁 truth 内部键;viewport_detections 顶层键必须存活(契约注释同款)。
        payload = {
            "truth": [{"measurements": [1], "tracks": [2]}],
            "viewport_detections": {"schema": "viewport_detections@1", "detections": []},
        }
        compact = gui_main._compact_stream_payload(payload, include_static=True)
        assert compact["viewport_detections"] == payload["viewport_detections"]


class TestSessionlessIngestAndEngine:
    """免会话入口 + 检测引擎启停(web 勾选驱动的常规通路)."""

    def test_sessionless_routes_into_active_session(self, client) -> None:
        http, manager = client
        manager.describe = lambda: {"active": True, "session_id": "s1"}  # fake.manifest.run_id == "s1"
        response = http.post("/api/viewport-detections", json=FRAME_SAMPLE)
        assert response.status_code == 200
        assert response.json() == {"accepted": True, "detections": 1}
        assert manager._viewport_detection["detections"] == FRAME_SAMPLE["detections"]

    def test_sessionless_without_active_session_is_404(self, client) -> None:
        http, manager = client
        manager.describe = lambda: {"active": False}
        assert http.post("/api/viewport-detections", json=FRAME_SAMPLE).status_code == 404
        assert http.post("/api/viewport-detections", json=FRAME_SAMPLE).json()["detail"] == "NO_ACTIVE_SESSION"

    def test_engine_enable_starts_detector_once(self, monkeypatch) -> None:
        calls = []
        monkeypatch.setattr(gui_main, "_detector_start", lambda: calls.append("start") or {"started": True, "pid": 11})
        http = TestClient(gui_main.app)
        assert http.post("/api/viewport-detection-engine", json={"enabled": True}).json() == {"started": True, "pid": 11}
        assert calls == ["start"]

    def test_engine_disable_stops_detector(self, monkeypatch) -> None:
        calls = []
        monkeypatch.setattr(gui_main, "_detector_stop", lambda: calls.append("stop") or {"stopped": True, "pid": 11})
        http = TestClient(gui_main.app)
        assert http.post("/api/viewport-detection-engine", json={"enabled": False}).json() == {"stopped": True, "pid": 11}
        assert calls == ["stop"]

    def test_engine_status_reports_pidfile_liveness(self, monkeypatch, tmp_path) -> None:
        pidfile = tmp_path / "detector.pid"
        monkeypatch.setattr(gui_main, "VIEWPORT_DETECTOR_PIDFILE", pidfile)
        http = TestClient(gui_main.app)
        assert http.get("/api/viewport-detection-engine").json()["running"] is False
        pidfile.write_text("999999\n")  # 不存在的 pid → 死档视为未运行
        assert http.get("/api/viewport-detection-engine").json() == {
            "running": False, "pid": None, "mode": "local",
            "forward_url": gui_main.VIEWPORT_DETECTOR_FORWARD_URL}

    def test_engine_remote_mode_spawns_over_ssh_and_stops_local_leftover(self, monkeypatch, tmp_path) -> None:
        """TWIN_VIEWPORT_DETECTOR_REMOTE=a4000:启停走 ssh;启动前先收口本地残留(防双 POST)."""
        pidfile = tmp_path / "detector.pid"
        pidfile.write_text("999999\n")  # 本地死档,不应误判为"本地在跑"
        ssh_calls: list[str] = []

        spawned = {"done": False}

        def fake_ssh(command: str, timeout: float = 10.0) -> str:
            ssh_calls.append(command)
            if "kill -0" in command:  # pidfile 探活
                return "4242" if spawned["done"] else ""
            if "nohup" in command:
                spawned["done"] = True
            return ""

        monkeypatch.setattr(gui_main, "VIEWPORT_DETECTOR_REMOTE", "a4000")
        monkeypatch.setattr(gui_main, "VIEWPORT_DETECTOR_PIDFILE", pidfile)
        monkeypatch.setattr(gui_main, "_ssh_remote", fake_ssh)
        local_stops: list[str] = []
        monkeypatch.setattr(gui_main, "_detector_stop_local",
                            lambda: local_stops.append("local") or {"stopped": False})
        monkeypatch.setattr(gui_main, "_local_detector_pid", lambda: 111)  # 本地残留活进程
        http = TestClient(gui_main.app)
        assert http.post("/api/viewport-detection-engine", json={"enabled": True}).json() == {
            "started": True, "pid": 4242, "mode": "remote", "host": "a4000"}
        # 20261023 GPU 分工批:UUID 写法钉 GPU1(序号写法因 CUDA 枚举序≠nvidia-smi 序而落空)
        assert any("nohup" in c and "CUDA_VISIBLE_DEVICES=GPU-f662e578-6888-2504-158f-681d3a3c2b13" in c
                   for c in ssh_calls), "GPU1(UUID) + venv 启动命令"
        assert local_stops == ["local"], "远程启动前收口本地残留"
        assert http.get("/api/viewport-detection-engine").json()["mode"] == "remote:a4000"
        stop = http.post("/api/viewport-detection-engine", json={"enabled": False}).json()
        assert stop == {"stopped": True, "pid": 4242, "mode": "remote", "host": "a4000"}
        assert any("pkill" in c for c in ssh_calls)

    def test_detector_pidfile_roundtrip_start_stop(self, monkeypatch, tmp_path) -> None:
        """引擎拉起真实子进程(睡眠桩替身)并停掉:pidfile 生命周期 + 进程真死."""
        monkeypatch.setattr(gui_main, "VIEWPORT_DETECTOR_PIDFILE", tmp_path / "detector.pid")
        monkeypatch.setattr(gui_main, "VIEWPORT_DETECTOR_LOG", tmp_path / "detector.log")
        monkeypatch.setattr(gui_main, "VIEWPORT_DETECTOR_PY", sys.executable)
        monkeypatch.setattr(
            gui_main, "VIEWPORT_DETECTOR_SCRIPT", tmp_path / "stub.py")
        (tmp_path / "stub.py").write_text("import time\ntime.sleep(60)\n")
        monkeypatch.setattr(gui_main, "VIEWPORT_DETECTOR_FORWARD_URL", "http://127.0.0.1:9/none")
        result = gui_main._detector_start()
        assert result["started"] is True
        pid = result["pid"]
        assert gui_main._detector_pid() == pid
        # 幂等:再次 start 不重复拉
        assert gui_main._detector_start() == {"started": False, "pid": pid, "reason": "already-running"}
        stopped = gui_main._detector_stop()
        assert stopped == {"stopped": True, "pid": pid}
        time.sleep(0.2)
        try:
            os.kill(pid, signal.SIGTERM)  # 已死则抛 ProcessLookupError = 预期
            raise AssertionError("stub process survived engine stop")
        except ProcessLookupError:
            pass
