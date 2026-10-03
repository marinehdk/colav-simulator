"""sensor-model-v1 契约模型（P3-S0，spec #90）。

契约文档：``sango/Docs/contracts/sensor-model-v1.md``（已冻结）。本模块是该契约的
Python 侧权威形状（pydantic v2）——量测流消息、融合生成器退化参数（VIMM 标定锚定）、
确认航迹输出、以及 WS 全量 1.0 transport ``truth[].tracks`` 的 P3 加性置信度字段
（契约 §6；gui_server ``_local_tracks`` 形状）。

边界（契约 §1）：Unity/C# 不消费 SFD——本模块仅后端与量测流生成器使用。
端点实现属 S2；本模块只冻结 schema（零运行时行为变化）。
"""

from __future__ import annotations

import math
from enum import IntEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

#: 契约版本标签（envelope.schema_version；与契约文档同名）。
SENSOR_MODEL_SCHEMA_VERSION = "sensor-model@1"

#: WS 全量 1.0 transport ``truth[].tracks`` 的 P3 置信度加性字段名（契约 §6）。
TRACK_ADDITIVE_FIELDS = ("existence_prob", "quality", "sources")


class SensorId(IntEnum):
    """SFD sensorID 词汇（契约 §2 冻结；Autoferry SFD 原序的刻意重排，理由见契约 §2 注）。"""

    RADAR_X = 1
    CAMERA_EO = 2
    CAMERA_IR = 3
    LIDAR = 4  # 旁路：视景 + 近距接触点，不进 IPDA（00-PLAN §3 铁律 3）
    AIS = 5  # 旁路：显示通道，v1 不进融合器（报告 04 开放问题 5 保守解）


#: sensorID → 稳定字符串标签（sensor_label 必须与之一致，契约 §2）。
SENSOR_LABELS: dict[int, str] = {
    SensorId.RADAR_X: "radar_x",
    SensorId.CAMERA_EO: "camera_eo",
    SensorId.CAMERA_IR: "camera_ir",
    SensorId.LIDAR: "lidar",
    SensorId.AIS: "ais",
}

#: 进融合器的 sensorID（旁路通道 4/5 不在此列，契约 §2）。
FUSION_SENSOR_IDS = frozenset({SensorId.RADAR_X, SensorId.CAMERA_EO, SensorId.CAMERA_IR})


class _Strict(BaseModel):
    """契约 schema 基类：禁止未知字段（冻结契约按字面量对拍，宽松消费是 twin-bridge 的条款）。"""

    model_config = ConfigDict(extra="forbid")


class OwnshipPose(_Strict):
    """量测时刻 ownship 位姿（契约 §3；world = UTM 48N NE 米制，yaw 自北向东为正）。"""

    p_n: float
    p_e: float
    yaw: float
    pitch: float = 0.0
    roll: float = 0.0


class SfdMeasurement(_Strict):
    """单条量测记录（契约 §3：NE + 协方差 + 类别 + 置信 + 时戳 + sensor 元数据）。

    所有量测已同构到 ownship-NED 水平面 NE 米——EO/IR 原始方位量测与像素框的
    georef 由量测流生成器/后端完成（契约 §3 注；observations-v1 §5）。
    """

    sensor_id: SensorId
    target_hint: int | None = None
    position_ne_m: list[float] = Field(min_length=2, max_length=2)
    position_cov_ne_m2: list[list[float]] = Field(min_length=2, max_length=2)
    t_s: float
    confidence: float = Field(ge=0.0, le=1.0)
    class_name: str | None = None
    class_confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _validate_covariance(self) -> "SfdMeasurement":
        cov = self.position_cov_ne_m2
        for row in cov:
            if len(row) != 2:
                raise ValueError("position_cov_ne_m2 must be 2x2")
            for value in row:
                if not math.isfinite(value):
                    raise ValueError("position_cov_ne_m2 entries must be finite")
        if cov[0][1] != cov[1][0]:
            raise ValueError("position_cov_ne_m2 must be symmetric")
        if cov[0][0] < 0.0 or cov[1][1] < 0.0:
            raise ValueError("position_cov_ne_m2 diagonal must be non-negative")
        if self.class_name is None and self.class_confidence is not None:
            raise ValueError("class_confidence requires class_name")
        return self


class SfdMeasurementFrame(_Strict):
    """SFD 量测流逐条消息（契约 §3 冻结；sensorID 见 §2，字段面见 §3 表）。"""

    schema_version: Literal["sensor-model@1"]
    frame_id: Literal["ownship_ned"]
    t_s: float
    sensor_id: SensorId
    sensor_label: str
    mount_id: str = Field(min_length=1)
    measurements: list[SfdMeasurement]
    ownship_pose_at_measurement: OwnshipPose
    epoch_unix_ns: int | None = None

    @model_validator(mode="after")
    def _validate_vocabulary(self) -> "SfdMeasurementFrame":
        if self.sensor_label != SENSOR_LABELS[self.sensor_id]:
            raise ValueError(f"sensor_label must be {SENSOR_LABELS[self.sensor_id]!r} for sensor_id={self.sensor_id}")
        for measurement in self.measurements:
            if measurement.sensor_id != self.sensor_id:
                raise ValueError("measurement.sensor_id must match the frame sensor_id")
        return self


class VimmNoiseCalibration(_Strict):
    """VIMM 标定量测噪声（契约 §4；milliampere-ch5 §6，04 报告 §2.5；σ 经雅可比投影 E5 形态）。"""

    lidar_sigma_c_m: float = Field(default=6.6, gt=0.0)
    radar_sigma_r_m: float = Field(default=8.0, gt=0.0)
    radar_sigma_theta_rad: float = Field(default=math.radians(1.0), gt=0.0, le=math.pi)


class VisibilityChain(_Strict):
    """逐类可见性 Markov 链 + 全局检测概率（契约 §4；VIMM 标定值）。"""

    w11: float = Field(default=0.90, ge=0.0, le=1.0)
    w01: float = Field(default=0.52, ge=0.0, le=1.0)
    global_pd: float = Field(default=0.92, ge=0.0, le=1.0)
    fov_outside_pd: float = Field(default=0.0, ge=0.0, le=1.0)


class ClutterModel(_Strict):
    """单位面积泊松杂波/新目标强度（契约 §4；VIMM 标定值）。"""

    poisson_rate_per_m2: float = Field(default=5e-7, ge=0.0)
    new_target_rate_per_m2: float = Field(default=1e-7, ge=0.0)


class AsyncJitter(_Strict):
    """雷达异步扫描节拍 + 概率漏检（契约 §4；量程档联动 24/60 rpm）。"""

    radar_scan_period_s: Literal[2.5, 1.0] = 2.5
    drop_probability: float = Field(default=0.0, ge=0.0, le=1.0)


class TrackManagement(_Strict):
    """IPDA 航迹管理阈值（契约 §4；确认/终止 Tc=99.9%/Td=1%/6 拍）。"""

    confirm_threshold: float = Field(default=0.999, ge=0.0, le=1.0)
    delete_threshold: float = Field(default=0.01, ge=0.0, le=1.0)
    terminate_after: int = Field(default=6, ge=1)


#: P3-S5 confirmed-tracks 数据产品默认存在概率门限（锚定契约 §4 confirm_threshold；
#: milliAmpere 语义 = 确认航迹才进运动规划，报告 07 §2.2）。
CONFIRMED_TRACKS_DEFAULT_THRESHOLD = TrackManagement().confirm_threshold


class SfdGeneratorConfig(_Strict):
    """量测流生成器退化参数包（契约 §4；全部默认值 = VIMM 标定锚）。"""

    noise: VimmNoiseCalibration = Field(default_factory=VimmNoiseCalibration)
    visibility: VisibilityChain = Field(default_factory=VisibilityChain)
    clutter: ClutterModel = Field(default_factory=ClutterModel)
    async_jitter: AsyncJitter = Field(default_factory=AsyncJitter)
    track_mgmt: TrackManagement = Field(default_factory=TrackManagement)


class TrackSourceContribution(_Strict):
    """确认航迹的单传感器贡献（契约 §5 sources[] 条目）。"""

    sensor_id: SensorId
    last_seen_age_s: float | None = None


class ConfirmedTrack(_Strict):
    """融合器确认航迹（契约 §5：存在概率 + quality + sources[] + 类别）。

    ``existence_prob`` 语义 = 虚警预算标定出的**门控量**（报告 07 §2.2）；
    决策侧禁止读成目标存在概率真值（encounter_lifecycle 消费为 S5 面）。
    """

    track_key: str = Field(min_length=1)
    target_id: int = Field(ge=0)
    generation: int = Field(ge=1)
    existence_prob: float = Field(ge=0.0, le=1.0)
    quality: float = Field(ge=0.0, le=1.0)
    sources: list[TrackSourceContribution] = Field(min_length=1)
    position_ne_m: list[float] = Field(min_length=2, max_length=2)
    velocity_ne_mps: list[float] = Field(min_length=2, max_length=2)
    heading_rad: float
    position_cov_ne_m2: list[list[float]] = Field(min_length=2, max_length=2)
    class_name: str | None = None
    class_confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _validate_shapes(self) -> "ConfirmedTrack":
        cov = self.position_cov_ne_m2
        for row in cov:
            if len(row) != 2:
                raise ValueError("position_cov_ne_m2 must be 2x2")
        if cov[0][1] != cov[1][0]:
            raise ValueError("position_cov_ne_m2 must be symmetric")
        if self.class_name is None and self.class_confidence is not None:
            raise ValueError("class_confidence requires class_name")
        return self


class ConfirmedTrackList(_Strict):
    """融合器输出信封（契约 §5）：确认航迹列表。"""

    schema_version: Literal["sensor-model@1/tracks"]
    t_s: float
    tracks: list[ConfirmedTrack]


class TrackSourceRef(_Strict):
    """WS tracks ``sources[]`` 平行数组的单条引用（契约 §6；精简自 TrackSourceContribution）。"""

    sensor_id: SensorId
    last_seen_age_s: float | None = None


class TracksSnapshotV1(_Strict):
    """gui_server 全量 1.0 transport ``truth[].tracks`` 形状 + P3 加性置信度字段（契约 §6）。

    基线平行数组（labels/generations/states/covariances/nis）零改动；三个 P3 字段
    （``existence_prob``/``quality``/``sources``）只加不删，缺省 = 旧发布端（零破坏，
    web 宽松消费）。compact-v1 剥除策略不动（``main.py:179`` 名单不感知本字段）。
    """

    labels: list[int] = Field(default_factory=list)
    generations: list[int] = Field(default_factory=list)
    states: list[list[float]] = Field(default_factory=list)
    covariances: list[list[list[float]]] = Field(default_factory=list)
    nis: list[float | None] = Field(default_factory=list)
    existence_prob: list[float] | None = None
    quality: list[float] | None = None
    sources: list[list[TrackSourceRef]] | None = None

    @model_validator(mode="after")
    def _validate_parallel_arrays(self) -> "TracksSnapshotV1":
        count = len(self.labels)
        for name in ("generations", "states", "covariances", "nis"):
            if len(getattr(self, name)) != count:
                raise ValueError(f"{name} must be a parallel array of length {count}")
        for name in TRACK_ADDITIVE_FIELDS:
            value = getattr(self, name)
            if value is not None and len(value) != count:
                raise ValueError(f"{name} must be a parallel array of length {count}")
        return self
