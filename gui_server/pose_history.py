"""pose_history.py — 权威位姿历史环 + 采集时刻插值(评审 Q1/Q2 修复).

问题(评审 2026-10-19 P3):观测 georef 此前用**收包时刻**的本船/相机位姿,
检测采集→收包 ≈0.13-0.5s,回转时 bearing 系统性抹扫 ≈ yaw_rate×滞后;且双钟轴
(后端墙钟 vs Unity/浏览器钟)只有注释声明、无运行时偏差检测。

修法(与 web P0 位姿历史插值同哲学,后端镜像):
- ``OwnshipPoseRing``:每个 sim tick 采样 (墙钟, sim 时刻, ownship 6 态),
  ``at_wall`` 在采集时刻(收包 − 采集延迟常量)插值出当帧位姿 + 对应 sim 时刻;
- ``CameraPoseRing``:P1 中继(viewport-ownship-polygon@1)每批 POST 的
  camera_pose 采样,``at_wall`` 同法插值(web poseAtCapture 同语义:
  east/north/height/fov 线性,yaw/pitch 最短角);
- 越窗防护 + **运行时偏差告警**:请求时刻落在环跨度外超过容差(镜像 web
  POSE_HISTORY_MAX_SKEW_S=1s)→ 限频 WARNING 并返 None(调用方回退收包位姿,
  行为=修复前);容差内 clamp 最近端(同样限频告警)——双钟轴偏差从此有
  运行时检测,不再只活在注释里。

线程模型:sample 来自会话 tick 线程 / 中继 POST 线程,at_wall 来自 FastAPI
线程;叶级锁,不嵌套 manager.lock。
"""

from __future__ import annotations

import logging
import math
import threading
import time
from collections import deque
from typing import Any

import numpy as np

log = logging.getLogger("gui_server")

#: 默认跨度(秒):覆盖采集回看(≤0.63s)+ tick 采样间隔 + 余量;超环长逐出最旧。
POSE_RING_SPAN_S = 5.0
#: 越窗容差(秒):镜像 web POSE_HISTORY_MAX_SKEW_S——跨机无 NTP 时采集时刻落出
#: 历史窗,超过该容差弃插值(返 None),不静默 clamp 到错误位姿。
POSE_RING_SKEW_TOLERANCE_S = 1.0
#: 告警限频(秒):同一环的越窗/clamp 告警最多每该时长一条,不刷日志。
POSE_RING_WARN_PERIOD_S = 10.0


def _wrap_angle_delta(radians: float) -> float:
    """角差归一到 (−π, π](跨 0/2π 插值用)."""
    return (radians + math.pi) % (2.0 * math.pi) - math.pi


class _BasePoseRing:
    """时间键插值环的公共骨架(采样/修剪/越窗判定/限频告警)."""

    def __init__(
        self,
        span_s: float = POSE_RING_SPAN_S,
        skew_tolerance_s: float = POSE_RING_SKEW_TOLERANCE_S,
        warn_period_s: float = POSE_RING_WARN_PERIOD_S,
    ) -> None:
        self._samples: deque[tuple[float, Any]] = deque()
        self._lock = threading.Lock()
        self._span_s = float(span_s)
        self._skew_tolerance_s = float(skew_tolerance_s)
        self._warn_period_s = float(warn_period_s)
        self._last_warn_s = 0.0

    def __len__(self) -> int:
        with self._lock:
            return len(self._samples)

    def reset(self) -> None:
        with self._lock:
            self._samples.clear()

    def _prune(self, now_s: float) -> None:
        cutoff = now_s - self._span_s
        while len(self._samples) > 2 and self._samples[0][0] < cutoff:
            self._samples.popleft()

    def _warn(self, message: str) -> None:
        now = time.monotonic()
        if now - self._last_warn_s >= self._warn_period_s:
            self._last_warn_s = now
            log.warning("pose_history: %s", message)

    def _bracket(self, wall_s: float) -> tuple[Any, Any, float] | None:
        """返回 (前样本, 后样本, 插值系数);不足两端样本返 None(越窗已告警)."""
        with self._lock:
            samples = list(self._samples)
        if not samples:
            return None
        oldest, newest = samples[0][0], samples[-1][0]
        if wall_s < oldest - self._skew_tolerance_s or wall_s > newest + self._skew_tolerance_s:
            self._warn(
                f"capture time {wall_s:.3f} outside pose ring span [{oldest:.3f}, {newest:.3f}] "
                f"beyond {self._skew_tolerance_s:.1f}s tolerance (clock-axis skew?); interpolation dropped"
            )
            return None
        if wall_s <= oldest or wall_s >= newest:
            # 容差内越界:clamp 最近端(照 web poseAtCapture 语义),限频告警留痕。
            self._warn(
                f"capture time {wall_s:.3f} clamped to pose ring edge [{oldest:.3f}, {newest:.3f}] "
                f"(within {self._skew_tolerance_s:.1f}s tolerance)"
            )
            edge = samples[0] if wall_s <= oldest else samples[-1]
            return edge[1], edge[1], 0.0
        upper = 1
        while samples[upper][0] < wall_s:
            upper += 1
        before, after = samples[upper - 1], samples[upper]
        fraction = (wall_s - before[0]) / (after[0] - before[0])
        return before[1], after[1], fraction


class OwnshipPoseRing(_BasePoseRing):
    """会话 ownship 位姿环:tick 采样,at_wall 插值 (sim 时刻, 6 态).

    6 态 = [north, east, psi, u, v, r];n/e/u/v 线性,psi 最短角(r 平凡线性)。
    """

    def sample(self, wall_s: float, sim_s: float, state: Any) -> None:
        record = (float(sim_s), tuple(float(value) for value in state))
        with self._lock:
            self._samples.append((float(wall_s), record))
            self._prune(float(wall_s))

    def at_wall(self, wall_s: float) -> tuple[float, np.ndarray] | None:
        bracket = self._bracket(wall_s)
        if bracket is None:
            return None
        (sim_a, state_a), (sim_b, state_b), k = bracket
        blend = lambda a, b: a + (b - a) * k  # noqa: E731 (局部插值闭包)
        psi = state_a[2] + _wrap_angle_delta(state_b[2] - state_a[2]) * k
        state = [
            blend(state_a[0], state_b[0]),
            blend(state_a[1], state_b[1]),
            psi % (2.0 * math.pi),
            blend(state_a[3], state_b[3]),
            blend(state_a[4], state_b[4]),
            blend(state_a[5], state_b[5]),
        ]
        return blend(sim_a, sim_b), np.asarray(state, dtype=float)


class CameraPoseRing(_BasePoseRing):
    """P1 中继 camera_pose 环:每批 POST 采样,at_wall 插值位姿 dict.

    插值域与 web poseAtCapture 同:east/north/height_m/fov_deg 线性,
    yaw_deg/pitch_deg 最短角(web wrapDegDelta 的度制同款)。
    """

    def sample(self, wall_s: float, pose: dict[str, float]) -> None:
        record = {key: float(pose[key]) for key in ("east", "north", "height_m", "yaw_deg", "pitch_deg", "fov_deg")}
        with self._lock:
            self._samples.append((float(wall_s), record))
            self._prune(float(wall_s))

    def at_wall(self, wall_s: float) -> dict[str, float] | None:
        bracket = self._bracket(wall_s)
        if bracket is None:
            return None
        pose_a, pose_b, k = bracket
        wrap_deg = lambda delta: ((delta + 180.0) % 360.0 + 360.0) % 360.0 - 180.0  # noqa: E731
        return {
            "east": pose_a["east"] + (pose_b["east"] - pose_a["east"]) * k,
            "north": pose_a["north"] + (pose_b["north"] - pose_a["north"]) * k,
            "height_m": pose_a["height_m"] + (pose_b["height_m"] - pose_a["height_m"]) * k,
            "fov_deg": pose_a["fov_deg"] + (pose_b["fov_deg"] - pose_a["fov_deg"]) * k,
            "yaw_deg": pose_a["yaw_deg"] + wrap_deg(pose_b["yaw_deg"] - pose_a["yaw_deg"]) * k,
            "pitch_deg": pose_a["pitch_deg"] + wrap_deg(pose_b["pitch_deg"] - pose_a["pitch_deg"]) * k,
        }
