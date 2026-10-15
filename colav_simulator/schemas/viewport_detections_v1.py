"""viewport-detections@1 契约模型(DT 视口 YOLO 检测分流).

方向:mac YOLO 检测服务 → ``POST /api/sessions/{session_id}/viewport-detections``
请求体;后端随遥测 WebSocket 顶层键 ``viewport_detections`` 原样广播给浏览器
(DT 像素流分流帧的像素域检测框,左上原点、y 向下,与 FrameMetadata
width/height 同域)。无数据/过期(>2s)时该键整体缺省.

``received_at`` 由服务器在收到时刻 ``time.time()`` 覆写(客户端可不带或带).
检测框形状与 observations-v1 的 ``PixelDetection`` 逐字段同型(上游
DetectionResult.detections[] 子集),直接复用避免双份冻结契约漂移.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from colav_simulator.schemas.observations_v1 import PixelDetection

#: 契约版本标签(envelope.schema;遥测顶层键 ``viewport_detections`` 同名去版本)。
VIEWPORT_DETECTIONS_SCHEMA_VERSION = "viewport_detections@1"


class _Strict(BaseModel):
    """契约 schema 基类:禁止未知字段(冻结契约按字面量对拍)."""

    model_config = ConfigDict(extra="forbid")


class ViewportDetectionsFrame(_Strict):
    """viewport-detections@1 请求体(一帧分流检测).

    ``box_xyxy`` 像素域 = width×height 分流帧(默认 1280×720);``detections``
    原样透传,可为空数组(权威"没看到").契约键 ``schema`` 撞 pydantic 保留名,
    字段名用 ``schema_version`` + alias 承接(线上 JSON 键仍逐字面为 "schema";
    gui_server 的遥测注入体是手工 dict,同样直写 "schema").
    """

    schema_version: Literal["viewport_detections@1"] = Field(alias="schema")
    pts_s: float
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    source: str
    detections: list[PixelDetection]
    received_at: float | None = None  # 服务器覆写;客户端值不作数
