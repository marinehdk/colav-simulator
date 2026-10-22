"""评审 Q1/Q2 修复:权威位姿历史环 + 采集时刻插值(gui_server/pose_history.py).

覆盖:
- OwnshipPoseRing:tick 采样 → at_wall 插值 (sim 时刻, 6 态);n/e/u/v 线性、
  psi 最短角(跨 0/2π);跨度修剪;
- CameraPoseRing:P1 中继 camera_pose 采样 → at_wall 插值(web poseAtCapture
  同语义:east/north/height/fov 线性、yaw/pitch 最短角);
- 越窗防护即运行时偏差检测(Q2):容差外返 None(调用方回退收包位姿 = 修复前
  行为)、容差内 clamp 最近端——两者都限频 WARNING(caplog 断言)。
"""

from __future__ import annotations

import logging
import math

import numpy as np
import pytest

from gui_server.pose_history import (
    POSE_RING_SKEW_TOLERANCE_S,
    CameraPoseRing,
    OwnshipPoseRing,
)


class TestOwnshipPoseRing:
    def test_interpolates_position_and_sim_time_linearly(self) -> None:
        ring = OwnshipPoseRing()
        ring.sample(100.0, 10.0, [0.0, 0.0, 0.0, 2.0, 0.0, 0.0])
        ring.sample(100.2, 10.2, [20.0, 4.0, 0.0, 2.0, 0.0, 0.0])
        sim_t, state = ring.at_wall(100.1)
        assert sim_t == pytest.approx(10.1)
        assert state[0] == pytest.approx(10.0)  # north 半程
        assert state[1] == pytest.approx(2.0)  # east 半程
        assert state[3] == pytest.approx(2.0)

    def test_yaw_interpolates_through_the_shortest_arc(self) -> None:
        ring = OwnshipPoseRing()
        ring.sample(0.0, 0.0, [0.0, 0.0, 350.0 * math.pi / 180.0, 0.0, 0.0, 0.0])
        ring.sample(0.1, 0.1, [0.0, 0.0, 10.0 * math.pi / 180.0, 0.0, 0.0, 0.0])
        _sim_t, state = ring.at_wall(0.05)
        # 350°→10° 跨 0:短弧 20°,中点 0°——不是数值线性(会绕远 180°)。
        assert state[2] == pytest.approx(0.0, abs=1e-9)

    def test_span_prune_drops_samples_beyond_the_window(self) -> None:
        ring = OwnshipPoseRing(span_s=1.0)
        ring.sample(0.0, 0.0, np.zeros(6))
        ring.sample(1.0, 1.0, np.zeros(6))
        ring.sample(5.0, 5.0, np.zeros(6))
        # 跨度外的旧样本逐出,但保留 ≥2 条(clamp/插值仍可括住请求)。
        assert len(ring) == 2

    def test_skew_beyond_tolerance_drops_instead_of_clamping(self, caplog) -> None:
        ring = OwnshipPoseRing()
        ring.sample(100.0, 10.0, np.zeros(6))
        ring.sample(100.1, 10.1, np.zeros(6))
        with caplog.at_level(logging.WARNING, logger="gui_server"):
            assert ring.at_wall(100.1 + POSE_RING_SKEW_TOLERANCE_S + 0.5) is None
        assert any("outside pose ring span" in record.message for record in caplog.records), "Q2:越窗必须留运行时告警"

    def test_within_tolerance_clamps_to_the_nearest_edge_and_warns(self, caplog) -> None:
        ring = OwnshipPoseRing()
        ring.sample(100.0, 10.0, [1.0, 2.0, 0.0, 0.0, 0.0, 0.0])
        ring.sample(100.1, 10.1, [3.0, 4.0, 0.0, 0.0, 0.0, 0.0])
        with caplog.at_level(logging.WARNING, logger="gui_server"):
            sim_t, state = ring.at_wall(100.1 + 0.3)  # 容差内越新端
        assert sim_t == pytest.approx(10.1)
        assert state[0] == pytest.approx(3.0)
        assert any("clamped to pose ring edge" in record.message for record in caplog.records)

    def test_empty_ring_returns_none(self) -> None:
        assert OwnshipPoseRing().at_wall(1.0) is None


class TestCameraPoseRing:
    def test_interpolates_linear_fields_and_wraps_angles(self) -> None:
        ring = CameraPoseRing()
        ring.sample(50.0, {"east": 0.0, "north": 0.0, "height_m": 10.0, "yaw_deg": -5.0, "pitch_deg": 0.0, "fov_deg": 60.0})
        ring.sample(50.4, {"east": 8.0, "north": 4.0, "height_m": 14.0, "yaw_deg": 5.0, "pitch_deg": -2.0, "fov_deg": 68.0})
        pose = ring.at_wall(50.2)
        assert pose is not None
        assert pose["east"] == pytest.approx(4.0)
        assert pose["north"] == pytest.approx(2.0)
        assert pose["height_m"] == pytest.approx(12.0)
        assert pose["fov_deg"] == pytest.approx(64.0)
        assert pose["yaw_deg"] == pytest.approx(0.0)  # -5→5 线性中点
        assert pose["pitch_deg"] == pytest.approx(-1.0)

    def test_yaw_wraps_through_360(self) -> None:
        ring = CameraPoseRing()
        ring.sample(0.0, {"east": 0, "north": 0, "height_m": 0, "yaw_deg": 350.0, "pitch_deg": 0, "fov_deg": 60})
        ring.sample(0.2, {"east": 0, "north": 0, "height_m": 0, "yaw_deg": 10.0, "pitch_deg": 0, "fov_deg": 60})
        # 数值可落在 360(web poseAtCapture 同样不归一);消费端 sin/cos 域 360≡0。
        assert ring.at_wall(0.1)["yaw_deg"] % 360 == pytest.approx(0.0, abs=1e-9)

    def test_stale_request_beyond_tolerance_is_dropped(self, caplog) -> None:
        ring = CameraPoseRing()
        ring.sample(10.0, {"east": 0, "north": 0, "height_m": 0, "yaw_deg": 0, "pitch_deg": 0, "fov_deg": 60})
        with caplog.at_level(logging.WARNING, logger="gui_server"):
            assert ring.at_wall(10.0 + POSE_RING_SKEW_TOLERANCE_S + 1.0) is None
        assert any("outside pose ring span" in record.message for record in caplog.records)
