"""viewport-ownship-polygon@1 契约模型(P1 本船掩膜下沉检测端).

方向 A(写入):Unity sango 桥服务 → ``POST /api/viewport-ownship-polygon``。
situation_frame 只走桥 DataChannel 到浏览器,8010 后端不可见(实测通路:
URS/gst webrtcbin DataChannel,无 web→后端回投),故 Unity 在同一后端 HTTP
通路(TwinRest 所连 backend_base)上按 ≤10Hz 批量捎带 POST 最近渲染帧的
(frame_id → 本船水线多边形)记录,几百字节~1KB/条,失败静默丢批不致命。

方向 B(读取):YOLO 检测器(tools/sango_detector_service.py) →
``GET /api/viewport-ownship-polygon`` 拉取环形缓存,把分流帧像素行 FRAME_MARKER
(twin-bridge-v1 §situation display,web decodeFrameMarker 同源)解出的
frame_id 与缓存精确匹配,推理前 cv2.fillPoly 海灰掩掉本船区域。

坐标域:角点 x/y = 归一化视口坐标,左上原点、y 向下(与 situation_frame 的
TwinScreenPoint.x/y 同域);depth = 视空间距离(米);in_frame = 角点在画面内
(部分出画仍给全多边形,出画角点仅标 in_frame=false)。polygon = 0 或 4 角点:
[] = 无掩膜(本船不可解析/相机身后),消费端必须优雅跳过。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

#: 契约版本标签(envelope.schema;GET 响应同名)。
VIEWPORT_OWNSHIP_POLYGON_SCHEMA_VERSION = "viewport_ownship_polygon@1"


class _Strict(BaseModel):
    """契约 schema 基类:禁止未知字段(冻结契约按字面量对拍)."""

    model_config = ConfigDict(extra="forbid")


class OwnshipPolygonCorner(_Strict):
    """本船水线角点(situation_frame.ownship_polygon 元素同形)."""

    x: float
    y: float
    depth: float = Field(ge=0)
    in_frame: bool


class OwnshipPolygonFrameEntry(_Strict):
    """一帧的 (frame_id → 多边形) 记录;polygon=[] = 该帧无掩膜."""

    frame_id: int = Field(ge=0, le=65535)
    polygon: list[OwnshipPolygonCorner] = Field(max_length=4)


class OwnshipCameraPose(_Strict):
    """最新相机位姿回显(TwinBridgeCameraPose 同形;camera_free 语义同源)."""

    east: float
    north: float
    height_m: float
    yaw_deg: float
    pitch_deg: float
    fov_deg: float


class ViewportOwnshipPolygonReport(_Strict):
    """POST /api/viewport-ownship-polygon 请求体(一批最近渲染帧)."""

    schema_version: Literal["viewport_ownship_polygon@1"] = Field(alias="schema")
    run_id: str
    sim_time: float
    camera_pose: OwnshipCameraPose
    frames: list[OwnshipPolygonFrameEntry]
