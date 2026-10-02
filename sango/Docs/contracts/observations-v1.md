# observations-v1 — 相机观测注入端点契约（P3-S0，spec #90）

状态：**已冻结**（2026-10-02，P3-S0）。方向：**检测宿主（YOLO 服务/web 转发）→ 后端融合链**。
Python 权威形状：`colav_simulator/schemas/observations_v1.py`（pydantic v2，extra=forbid）；
契约测试：`tests/test_observations_v1_contract.py`（§7 样例字面量同源对拍）。

**边界：本段只冻结 schema 与语义，端点路由属 S2 实现**（gui_server 本段零改动——不加路由）。
雷达/AIS/LiDAR 不经本端点：它们在后端量测流生成器内仿真，直接产出 sensor-model-v1 消息（契约 §2）。

## 1. 端点

```
POST /api/sessions/{session_id}/observations
Content-Type: application/json
```

- 路径先例：PHASE1-PLAN 预留（`docs/research/2026-09-22-sango-prototype/PHASE1-PLAN.md:253/:255`）。
- 鉴权语义：v1 沿 gui_server 既有面——**无 token**（服务 loopback 绑定，物理面即授权边界）；
  会话校验 = `session_id` 必须存在。token 化若未来需要，走统一 gui_server 演进，不单端点加。
- 会话状态闸：**仅 `CREATED`/`RUNNING` 接受**（`SessionState`，`colav_simulator/experiment/contracts.py:25`）；
  `PAUSED`/`FINISHED`/`FAILED` → 409 `SESSION_NOT_ACCEPTING`。
- 节流/去重：`(session_id, sensor_id, mount_id)` 维度 `frame_seq` **严格单调递增**。
  `frame_seq` ≤ 已接受最大值（重复/乱序/回退）→ 409 `FRAME_SEQ_REGRESSION`（幂等拒绝，不部分接受）。
  v1 不设服务端额外限速——上游 ZMQ 帧节奏即天然节流（detection-return-v1 §3 逐帧排空语义）。
- 未知 `session_id` → 404 `SESSION_NOT_FOUND`。

## 2. 传感器词汇（冻结）

| sensor_id | 通道 | 说明 |
|---|---|---|
| 2 | camera_eo | 白光相机检测（YOLO） |
| 3 | camera_ir | 红外相机检测（灰度域 YOLO 同管线） |

仅 2|3。与 sensor-model-v1 §2 同表（1=radar_x 等不经此端点，见 §1 边界）。

## 3. 请求体 schema（冻结）

```json
{"schema_version":"observations@1","frame_seq":41,"frame_time_s":12.402,"sensor_id":2,"mount_id":"mast_eo_bow","source":"yolo-detector","detections":[{"box_xyxy":[100.0,120.0,340.0,260.0],"class_id":8,"class_name":"boat","confidence":0.87}]}
```

```json
{"schema_version":"observations@1","frame_seq":42,"frame_time_s":13.502,"sensor_id":3,"mount_id":"mast_ir_bow","detections":[]}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `schema_version` | string | 是 | 恒 `"observations@1"` |
| `frame_seq` | int ≥0 | 是 | 来源帧号（FrameMetadata.frame_seq，frame-publisher-v1 §2）；单调闸见 §1 |
| `frame_time_s` | float | 是 | 来源帧发布时刻（秒，Unity `Time.timeAsDouble` 域） |
| `sensor_id` | int | 是 | 2\|3（§2） |
| `mount_id` | string | 是 | 桅杆机位标识（sensor-model-v1 §3 同词汇，如 `mast_eo_bow`/`mast_ir_bow`） |
| `source` | string | 是（默认 `yolo-detector`） | 检测源标识（沿 detection-result-v1 §2 `source` 语义） |
| `detections` | array | 是（可为空数组） | 像素检测框；`[]` = YOLO 权威"没看到"（沿 detection-return-v1 §2 语义） |
| `detections[].box_xyxy` | float[4] | 是 | `[x0,y0,x1,y1]` 像素，左上原点 y 向下，正面积（x1>x0, y1>y0），与来源帧 FrameMetadata width/height 同域 |
| `detections[].class_id` | int ≥0 | 是 | 类别索引 |
| `detections[].class_name` | string | 是 | 类别名（COCO `boat`…） |
| `detections[].confidence` | float 0-1 | 是 | 检测置信 |

未知字段一律拒绝（pydantic `extra=forbid`）——与 twin-bridge 宽松消费相反：本端点是后端受控
新增面（00-PLAN §3 白名单），严格校验在边界即拒绝脏数据，错误在 422 可见。

## 4. 响应（冻结）

成功（`200`）：

```json
{"accepted":true,"frame_seq":41,"detections_accepted":1}
```

`detections_accepted` = 通过校验闸进入 georef 队列的框数（v1 恒 = `len(detections)`；置信阈值闸为 S2 实现面）。

错误码表（冻结）：

| HTTP | code | 触发 |
|---|---|---|
| 404 | `SESSION_NOT_FOUND` | session_id 不存在或已删除 |
| 409 | `SESSION_NOT_ACCEPTING` | 会话状态 ∉ {CREATED, RUNNING} |
| 409 | `FRAME_SEQ_REGRESSION` | frame_seq 非严格递增（重复/乱序/回退） |
| 422 | `VALIDATION_ERROR` | schema 违约（FastAPI/pydantic 默认形态） |

## 5. 坐标方案裁决：像素框 + 位姿快照引用，georef 归后端（写档）

两种候选：**(a)** 像素框 + 当帧相机位姿快照引用，后端做 georef；**(b)** 发送方预 georef 的 NE 框 +
georef 元数据（相机内外参/投影矩阵）随框。**冻结 (a)**。理由：

1. **权威在后端**（00-PLAN §1 铁律 1）：ownship 位姿、ENC 原点（`session.enc.origin`，`main.py:1202`）、
   量测时序全部在后端；发送方（YOLO 宿主/web 转发）无权威时钟也无 NE 原点知识，预 georef 必然引入
   第二个坐标系真相源。
2. **标定单点**：桅杆机位内外参（FBX 锚点 milliampere-ch5 §4.2 + 相机标定）只存后端一份；方案 (b) 会把
   标定数据复制到发送方，漂移/失配无单点修复处。
3. **载荷最小**：像素框即上游 `DetectionResult.detections[]` 原样（§3 字段面 = 其逐字段子集），
   ZMQ payload 无需改形即可转发——链路两端（Unity 叠加、后端融合）消费同一检测结果。
4. **位姿快照引用的形态**：`(mount_id, frame_seq, frame_time_s)` 三元组即引用——后端按 `mount_id` 查
   机位标定、按 `frame_time_s` 取权威 ownship 状态还原当帧相机位姿，像素→NE 三角化在生成器边界内完成
   （sensor-model-v1 §3 注）。georef 误差验收（≤ 船长级 @2nm）属 S2 存证项。

## 6. 与 detection-result-v1 的关系（链路图）

```
Unity sango ──ZMQ 5556 sango.frame（frame-publisher-v1）──► YOLO 服务（tools/sango_detector_service.py）
   ▲                                                          │
   │ ZMQ 5557 sango.detection（detection-return-v1）           │ 同一 payload 转发（零改形，§5.3）
   │                                                          ▼
Unity DetectionOverlay（叠加显示，M9 既有）          POST /api/sessions/{id}/observations（本契约，S2 落地）
                                                              │ 后端 georef（§5）+ SFD 同构
                                                              ▼
                                              sensor-model-v1 量测流 → 融合跟踪器（S5 贯通）
```

- detection-result-v1（M3/M9）：检测结果 **→ Unity 叠加**，止步渲染；
  observations-v1：同一检测结果 **→ 后端融合**——两条消费支路共享上游 payload，互不阻塞
  （Unity 消费失败/回退 GT 不影响 observations 支路，反之亦然）。
- 后端唯一受控新增面（00-PLAN §3 白名单）：本端点 + sensing 模型 + tracks 加性字段；既有 REST/WS 契约零改动。

## 7. 验收钩子与冻结样例

- 契约测试：`tests/test_observations_v1_contract.py` —— §3/§4 样例反序列化 + 违约拒绝
  （sensorID 越界/负坐标/退化框/缺字段/未知字段/空 mount_id）+ detection-result-v1 payload 子集嵌入对拍。
- 端点 E2E（S2）：CREATED/RUNNING 收、PAUSED 409、frame_seq 回退 409、404——以本契约为准。

## 8. 演进记录（只加条款）

| 日期 | 段 | 变更 | 溯源 |
|---|---|---|---|
| 2026-10-02 | P3-S0 | 契约冻结（§1-§7）；坐标方案 (a) 裁决写档 | spec #90 |
| 2026-10-02 | P3-S2 | 端点落地（`gui_server/main.py` 新路由 POST/GET + 标定表 + 量测接入）：§1 全套错误码按表实现（错误 body = `detail` 为冻结码字符串）；未知 `mount_id` 归 422 `VALIDATION_ERROR`（词汇表 = 标定表 `colav_simulator/core/mast_cameras.py`，与 Unity `MastCameraTable.cs` 双侧同源）。**georef 方案写档**（§5 落地形态）：方位 = 框中心列经 pinhole（fx 由实际帧宽 + HFOV 导出）；测距 = 框高像素 × 类别船高先验（`boat`=2.5 m，milliAmpere 海面以上相机测距同构），量程钳位 [5 m, 2 nm]；协方差 = 径向拉长极坐标旋转入 NE（σ_r = max(15% r, 2 m)，σ_⊥ = max(r·max(2px/fx, 1°), 2 m)）。**位姿快照方案写档**：v1 georef 用收货时刻权威 ownship 状态近似当帧位姿（同机回环亚秒级延迟 ≪ 船长级精度阈；`frame_time_s` 保留 Unity 域参考戳，Unity 侧另在 FrameMetadata 附诊断位姿快照，见 frame-publisher-v1 演进行）。**量测缓存**：接受框经 georef 进会话级 `ExternalCameraSensor`（`core/sensing.py`，ISensor 族；tracker 消费走 clutter 槽 do_idx=-1，无真值关联语义）；GET `/api/sessions/{id}/observations` = 计数 + 待消化量测状态钩（E2E 断言 sensor_id 键）。会话替换即清理（`WebSessionManager._activate` 重建缓存）。默认馈送机位 = `mast_ptz_eo`（前向 EO = PTZ 白光通道；写档偏差注：EO 环视 ±60° 前向双不含正前，正前 = PTZ 档） | spec #90 S2 |
