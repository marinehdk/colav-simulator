"""viewport-tracks@1 契约模型(P3 检测→跟踪层).

方向:gui_server 把 viewport detections 喂进既有 observations/IPDA 管线
(ExternalCameraSensor 记录缓存 + vimmjipda 管理器,confirmed = 管理器存在概率
过确认门),随遥测 WebSocket 顶层键 ``viewport_tracks`` 广播给浏览器。数据块
优先挂 track、track 缺席回退裸检测(TRK/DET 角标)——web 消费端宽松读取,
无数据/过期时该键整体缺省.

真实延迟语义(sitaw 调研 §2.3):``bearing_rad``/``range_m`` 是滤波态在跟踪
时刻的估计(IPDA 收敛为分钟级),不追帧、不对齐当前显示帧;框级锁帧是 web
侧 P0 微跟踪器的职责,两层解耦.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

#: 契约版本标签(envelope.schema;遥测顶层键 ``viewport_tracks`` 同名去版本)。
VIEWPORT_TRACKS_SCHEMA_VERSION = "viewport_tracks@1"


class _Strict(BaseModel):
    """契约 schema 基类:禁止未知字段(冻结契约按字面量对拍)."""

    model_config = ConfigDict(extra="forbid")


class ViewportTrack(_Strict):
    """一条 confirmed 航迹(管理器存在概率 ≥ 确认门才进本契约)."""

    track_id: int
    status: Literal["confirmed"]
    existence_prob: float = Field(ge=0.0, le=1.0)
    bearing_rad: float = Field(ge=0.0, le=2.0 * 3.141592653589793)
    range_m: float = Field(ge=0.0)
    north_m: float  # 绝对场景 NE(web 端经相机位姿投影关联绿框)
    east_m: float


class ViewportTracksDocument(_Strict):
    """viewport-tracks@1 遥测注入体(一次跟踪步的输出快照)."""

    schema_version: Literal["viewport_tracks@1"] = Field(alias="schema")
    t_s: float  # 跟踪步的仿真时刻
    received_at: float  # 服务器墙钟(服务端盖;过期判定用)
    tracks: list[ViewportTrack]
