"""observations-v1 契约模型（P3-S0，spec #90）。

契约文档：``sango/Docs/contracts/observations-v1.md``（已冻结）。本模块是该契约的
Python 侧权威形状（pydantic v2）：``POST /api/sessions/{session_id}/observations``
请求体 —— 像素检测框 + 当帧相机位姿快照引用；georef 由后端完成（契约 §5 裁决）。

边界：仅 schema 冻结；端点路由实现属 S2（gui_server 不加路由，本段零运行时行为变化）。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

#: 契约版本标签（envelope.schema_version；与契约文档同名）。
OBSERVATIONS_SCHEMA_VERSION = "observations@1"

#: 本端点接受的 sensorID 词汇（契约 §2：仅相机链；雷达/AIS/LiDAR 走 SFD 生成器，不经此端点）。
OBSERVATION_SENSOR_IDS = (2, 3)


class _Strict(BaseModel):
    """契约 schema 基类：禁止未知字段（冻结契约按字面量对拍）。"""

    model_config = ConfigDict(extra="forbid")


class PixelDetection(_Strict):
    """单条像素检测框（契约 §3；坐标系沿 detection-result-v1 §1：左上原点、y 向下、
    与来源帧 FrameMetadata width/height 同域）。字段面 = DetectionResult.detections[]
    逐字段子集，上游 payload 无需改形即可转发。"""

    box_xyxy: list[float] = Field(min_length=4, max_length=4)
    class_id: int = Field(ge=0)
    class_name: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _validate_box(self) -> "PixelDetection":
        x0, y0, x1, y1 = self.box_xyxy
        for value in (x0, y0, x1, y1):
            if value < 0.0:
                raise ValueError("box_xyxy coordinates must be non-negative (pixel domain)")
        if x1 <= x0 or y1 <= y0:
            raise ValueError("box_xyxy must have positive area (x1 > x0, y1 > y0)")
        return self


class ObservationFrame(_Strict):
    """observations-v1 请求体（契约 §3）。

    相机位姿快照引用 = ``(mount_id, frame_seq, frame_time_s)`` 三元组：后端按
    ``mount_id`` 查桅杆机位标定、按 ``frame_time_s`` 取权威 ownship 状态还原当帧
    相机位姿并完成像素→NE georef（契约 §5 裁决：sender 不做 georef、不内嵌位姿）。
    """

    schema_version: Literal["observations@1"]
    frame_seq: int = Field(ge=0)
    frame_time_s: float
    sensor_id: Literal[2, 3]  # camera_eo | camera_ir（契约 §2 冻结）
    mount_id: str = Field(min_length=1)
    source: str = "yolo-detector"
    detections: list[PixelDetection]

    @model_validator(mode="after")
    def _validate_vocabulary(self) -> "ObservationFrame":
        if self.sensor_id not in OBSERVATION_SENSOR_IDS:
            raise ValueError(f"sensor_id must be one of {OBSERVATION_SENSOR_IDS}")
        return self


class ObservationAccepted(_Strict):
    """observations-v1 成功响应体（契约 §4；200）。``detections_accepted`` = 通过
    置信/校验闸进入 georef 队列的框数（v1 = len(detections)，闸策略为 S2 实现面）。"""

    accepted: Literal[True]
    frame_seq: int
    detections_accepted: int = Field(ge=0)
