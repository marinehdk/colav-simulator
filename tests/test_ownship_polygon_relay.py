"""P1 viewport-ownship-polygon@1 中继契约测试.

三段契约的第 2 段:Unity 桥服务(situation_frame 对 8010 不可见,DataChannel 只达
浏览器)以 ≤10Hz 批量 POST 最近渲染帧的 (frame_id → 本船水线多边形);检测器
GET 拉环形缓存。覆盖:POST/GET 往返、frame_id 覆写、环形逐出、免会话单槽、
冻结契约拒绝未知字段、GET 空态(frames=[],不 404——检测端"无 polygon 优雅
跳过"依赖此语义)。
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import gui_server.main as gui_main
from colav_simulator.schemas.viewport_ownship_polygon_v1 import (
    VIEWPORT_OWNSHIP_POLYGON_SCHEMA_VERSION,
)

CORNER = {"x": 0.25, "y": 0.75, "depth": 48.5, "in_frame": True}


def _report(frames, run_id="run-relay", sim_time=12.5) -> dict:
    return {
        "schema": VIEWPORT_OWNSHIP_POLYGON_SCHEMA_VERSION,
        "run_id": run_id,
        "sim_time": sim_time,
        "camera_pose": {"east": 40500.0, "north": 6958000.0, "height_m": 12.0,
                        "yaw_deg": 15.0, "pitch_deg": -8.5, "fov_deg": 60.0},
        "frames": frames,
    }


def _entry(frame_id, corners=None) -> dict:
    return {"frame_id": frame_id, "polygon": corners if corners is not None else [CORNER] * 4}


@pytest.fixture()
def client():
    with TestClient(gui_main.app) as test_client:
        with gui_main._ownship_polygon_lock:
            gui_main._ownship_polygon_frames.clear()
            gui_main._ownship_polygon_meta.clear()
        yield test_client
        with gui_main._ownship_polygon_lock:
            gui_main._ownship_polygon_frames.clear()
            gui_main._ownship_polygon_meta.clear()


def test_get_before_any_post_returns_empty_frames_not_404(client):
    response = client.get("/api/viewport-ownship-polygon")
    assert response.status_code == 200
    body = response.json()
    assert body["schema"] == VIEWPORT_OWNSHIP_POLYGON_SCHEMA_VERSION
    assert body["frames"] == []
    assert body["camera_pose"] is None and body["updated_at"] is None


def test_post_then_get_round_trips_frames_pose_and_timestamp(client):
    frames = [_entry(100), _entry(101, corners=[])]
    assert client.post("/api/viewport-ownship-polygon", json=_report(frames)).status_code == 200
    body = client.get("/api/viewport-ownship-polygon").json()
    assert body["run_id"] == "run-relay" and body["sim_time"] == 12.5
    assert body["camera_pose"]["fov_deg"] == 60.0
    assert body["updated_at"] is not None
    assert [entry["frame_id"] for entry in body["frames"]] == [100, 101]  # 升序,末位最新
    assert body["frames"][0]["polygon"] == [CORNER] * 4
    assert body["frames"][1]["polygon"] == []  # 空多边形(无掩膜帧)原样保留


def test_same_frame_id_overwrites_in_place_and_ring_evicts_oldest(client):
    ring = gui_main._OWNSHIP_POLYGON_RING
    fill = [_entry(i, corners=[]) for i in range(ring)]  # 恰满环,不逐出
    assert client.post("/api/viewport-ownship-polygon", json=_report(fill)).status_code == 200
    # 覆写既存 frame_id=5:原位更新(不挪到队尾),多边形换新值
    assert client.post("/api/viewport-ownship-polygon",
                       json=_report([_entry(5)])).status_code == 200
    # 新 frame_id=ring 触发逐出最旧(frame_id=0)
    assert client.post("/api/viewport-ownship-polygon",
                       json=_report([_entry(ring)])).status_code == 200
    body = client.get("/api/viewport-ownship-polygon").json()
    ids = [entry["frame_id"] for entry in body["frames"]]
    assert len(ids) == ring
    assert ids[0] == 1 and ids[-1] == ring  # 0 被逐出;新键追加队尾
    assert ids.index(5) == 4  # 覆写未挪位(原 frame_id=5,逐出 0 后整体前移一格)
    assert body["frames"][4]["polygon"] == [CORNER] * 4  # 覆写值生效


def test_last_writer_wins_for_meta(client):
    client.post("/api/viewport-ownship-polygon", json=_report([_entry(1)], run_id="run-a", sim_time=1.0))
    client.post("/api/viewport-ownship-polygon", json=_report([_entry(2)], run_id="run-b", sim_time=2.0))
    body = client.get("/api/viewport-ownship-polygon").json()
    assert body["run_id"] == "run-b" and body["sim_time"] == 2.0


def test_frozen_contract_rejects_unknown_fields_and_bad_ranges(client):
    bad = _report([_entry(0)])
    bad["frames"][0]["extra"] = 1
    assert client.post("/api/viewport-ownship-polygon", json=bad).status_code == 422
    out_of_range = _report([_entry(65536)])
    assert client.post("/api/viewport-ownship-polygon", json=out_of_range).status_code == 422
    too_many_corners = _report([_entry(0, corners=[CORNER] * 5)])
    assert client.post("/api/viewport-ownship-polygon", json=too_many_corners).status_code == 422
