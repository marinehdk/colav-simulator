"""viewport_tracks.py — DT 视口检测 → 既有 observations/IPDA 管线(P3).

装配既有件,不新造跟踪器:
- 像素→NE: :func:`colav_simulator.core.mast_cameras.georeference_box`(同一
  pinhole/水线先验/径向协方差链),机位 = P1 中继的最新 ``camera_pose``
  (viewport-ownship-polygon@1 回显;free camera,非桅杆机位表);
- 记录缓存: :class:`colav_simulator.core.sensing.ExternalCameraSensor`(线程
  安全 inbox;本通道记录 ``position_ne_m`` 为**绝对场景 NE**——显示层跟踪
  不做真值关联,全部走杂波槽语义,由 IPDA 自己关联,与主链 mast 通道的
  ownship-相对记录约定并行,见 :func:`georeference_viewport_frame` 注释);
- IPDA: ``IntegrationRegistry().build_tracker("vimmjipda")``(管理器存在概率
  ≥ 确认门 → confirmed;``VIMMJIPDAExistenceAdapter`` 把存在概率抬到快照).

输出: :data:`viewport_tracks@1 <colav_simulator.schemas.viewport_tracks_v1>`
遥测顶层键文档(confirmed 状态 + existence 概率 + 滤波后 brg/rng)。brg/rng
在跟踪步冻结(滤波态分钟级收敛,不追显示帧;sitaw 调研 §2.3)。
"""

from __future__ import annotations

import math
import threading
import time
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from colav_simulator.core.mast_cameras import (
    SENSOR_ID_EO,
    MastMount,
    georeference_box,
)
from colav_simulator.core.sensing import ExternalCameraSensor
from colav_simulator.schemas.viewport_tracks_v1 import (
    VIEWPORT_TRACKS_SCHEMA_VERSION,
    ViewportTrack,
    ViewportTracksDocument,
)

#: 视口通道的合成机位 id(诊断字段;不在桅杆机位表内)。
VIEWPORT_MOUNT_ID = "viewport"


def viewport_hfov_deg(fov_deg: float, width_px: float, height_px: float) -> float:
    """垂直 FOV(视口族约定:fov=垂直向度)→ 水平 FOV(square-pixel pinhole)."""
    aspect = float(width_px) / float(height_px)
    return math.degrees(2.0 * math.atan(aspect * math.tan(math.radians(float(fov_deg)) / 2.0)))


def viewport_mount(camera_pose: Mapping[str, Any], width_px: int, height_px: int) -> MastMount:
    """P1 中继 camera_pose → 合成 MastMount(georeference_box 单一入口复用).

    yaw 北向东顺时针(TwinBridgeCameraPose 语义)= MastMount 方位角 +
    ``own_yaw_rad=0`` 的合成;高度/前移量仅作记录(georef 链不消费)。
    """
    return MastMount(
        mount_id=VIEWPORT_MOUNT_ID,
        sensor_id=SENSOR_ID_EO,
        channel="camera_eo",
        azimuth_deg=float(camera_pose["yaw_deg"]),
        hfov_deg=viewport_hfov_deg(float(camera_pose["fov_deg"]), width_px, height_px),
        reference_width_px=int(width_px),
        reference_height_px=int(height_px),
        height_m=float(camera_pose.get("height_m", 0.0)),
        forward_offset_m=0.0,
    )


def camera_pose_valid(camera_pose: Mapping[str, Any] | None) -> bool:
    """中继位姿六字段齐全且有限(缺一即弃,检测显示不受影响)."""
    if not isinstance(camera_pose, Mapping):
        return False
    return all(
        isinstance(camera_pose.get(key), (int, float)) and math.isfinite(float(camera_pose[key]))
        for key in ("east", "north", "height_m", "yaw_deg", "pitch_deg", "fov_deg")
    )


def georeference_viewport_frame(
    camera_pose: Mapping[str, Any],
    width_px: int,
    height_px: int,
    detections: Sequence[Mapping[str, Any]],
    t_s: float,
) -> list[dict[str, Any]]:
    """一帧视口检测 → 绝对场景 NE 记录(ExternalCameraSensor.submit 形状).

    与 mast 通道 ``ingest_observations`` 的差别:锚 = 相机绝对位姿(free
    camera 可离本船任意远,记录须绝对 NE 才能进绝对域 IPDA),且不做真值
    关联——本通道所有记录以杂波槽语义被 ``generate_measurements`` 原样送入
    管理器,关联是 IPDA 自己的事(真实传感器语义,显示层不碰真值)。
    """
    mount = viewport_mount(camera_pose, width_px, height_px)
    camera_north = float(camera_pose["north"])
    camera_east = float(camera_pose["east"])
    records: list[dict[str, Any]] = []
    for detection in detections:
        georef = georeference_box(
            mount,
            tuple(float(value) for value in detection["box_xyxy"]),  # type: ignore[arg-type]
            int(width_px),
            int(height_px),
            camera_north,
            camera_east,
            own_yaw_rad=0.0,
            class_name=str(detection.get("class_name")),
        )
        records.append(
            {
                # 绝对场景 NE(见模块 docstring:本通道记录不做 ownship-相对换算)。
                "position_ne_m": [float(georef.north_m), float(georef.east_m)],
                "position_cov_ne_m2": [list(row) for row in georef.cov_ne_m2],
                "confidence": float(detection.get("confidence", 0.0)),
                "class_name": str(detection.get("class_name", "")),
                "t_s": float(t_s),
                "mount_id": VIEWPORT_MOUNT_ID,
                "bearing_rad": float(georef.bearing_rad),
                "range_m": float(georef.range_m),
            }
        )
    return records


class ViewportTrackService:
    """会话级视口跟踪服务:记录缓存 + vimmjipda 步进 + viewport_tracks@1 文档.

    线程模型:FastAPI 线程调 :meth:`feed`/内置步进;``_lock`` 只护本服务状态
    (记录缓存自带锁;vimmjipda 管理器仅被本服务串行步进)。
    """

    def __init__(self, sensor: ExternalCameraSensor | None = None, tracker: Any = None) -> None:
        self._sensor = sensor if sensor is not None else ExternalCameraSensor()
        self._tracker = tracker
        self._tracker_ready = tracker is not None
        self._lock = threading.Lock()
        self._last_t: float | None = None
        self._records: list[dict[str, Any]] = []
        self._t_s: float = 0.0
        self._received_at: float = 0.0
        self._own_ne: tuple[float, float] = (0.0, 0.0)

    # ------------------------------------------------------------------ tracker
    @property
    def available(self) -> bool:
        """Vimmjipda 外部仓可用(不可用时服务惰性,键整体缺省)."""
        with self._lock:
            if not self._tracker_ready:
                self._ensure_tracker()
            return self._tracker is not None

    def _ensure_tracker(self) -> None:
        """惰性装配(导入外部仓重;首次 feed 才发生). 失败保持 None(不重试)."""
        try:
            # 重依赖(外部仓导入),惰性导入是本方法的存在理由。
            from colav_simulator.integrations.registry import IntegrationRegistry  # noqa: PLC0415

            tracker = IntegrationRegistry().build_tracker("vimmjipda")
        except Exception:  # noqa: BLE001 (依赖缺失 = 服务不可用,非会话错误)
            tracker = None
        if tracker is not None:
            tracker.set_sensor_list([self._sensor])
        self._tracker = tracker
        self._tracker_ready = True

    def reset(self) -> None:
        with self._lock:
            self._sensor.reset(None)
            if self._tracker is not None:
                self._tracker.reset()
            self._last_t = None
            self._records = []
            self._t_s = 0.0
            self._received_at = 0.0

    # ------------------------------------------------------------------ feed/step
    def feed(
        self,
        camera_pose: Mapping[str, Any],
        width_px: int,
        height_px: int,
        detections: Sequence[Mapping[str, Any]],
        t_s: float,
        ownship_state: np.ndarray,
    ) -> int:
        """Georeference 一帧并步进跟踪器(t_s 不前进时只入队,步进跳过)."""
        records = georeference_viewport_frame(camera_pose, width_px, height_px, detections, t_s)
        self._sensor.submit(records)
        self.step(t_s, ownship_state)
        return len(records)

    def step(self, t: float, ownship_state: np.ndarray) -> None:
        """步进 IPDA 并冻结本步 confirmed 航迹记录(brg/rng 在跟踪时刻取值)."""
        if not self.available:
            return
        with self._lock:
            last = self._last_t
            if last is not None and t <= last:
                return
            self._last_t = t
        snapshots, _measurements = self._tracker.track(t, (t - last) if last is not None else 0.0, [], ownship_state)
        own_ne = np.asarray(ownship_state, dtype=float)[:2]
        records: list[dict[str, Any]] = []
        for snapshot in snapshots:
            state = np.asarray(snapshot.state, dtype=float)
            delta = state[:2] - own_ne
            range_m = float(np.linalg.norm(delta))
            bearing = float(math.atan2(delta[1], delta[0])) % (2.0 * math.pi)
            records.append(
                {
                    "track_id": int(snapshot.target_id),
                    "status": "confirmed",
                    "existence_prob": float(snapshot.existence_prob),
                    "bearing_rad": bearing,
                    "range_m": range_m,
                    "north_m": float(state[0]),
                    "east_m": float(state[1]),
                }
            )
        with self._lock:
            self._records = records
            self._t_s = float(t)
            self._received_at = time.time()
            self._own_ne = (float(own_ne[0]), float(own_ne[1]))

    # ------------------------------------------------------------------ output
    def document(self) -> dict[str, Any] | None:
        """viewport_tracks@1 文档(pydantic 契约校验后 dump;无步进过 = None)."""
        with self._lock:
            records = [dict(record) for record in self._records]
            t_s, received_at = self._t_s, self._received_at
        if not received_at:
            return None
        envelope = ViewportTracksDocument(
            schema=VIEWPORT_TRACKS_SCHEMA_VERSION,
            t_s=t_s,
            received_at=received_at,
            tracks=[ViewportTrack(**record) for record in records],
        )
        return envelope.model_dump(by_alias=True)
