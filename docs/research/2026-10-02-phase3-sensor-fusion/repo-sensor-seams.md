# 阶段3 传感器/融合：本仓库接缝与缺口清单（考古档案 2026-10-02）

> 供阶段3规划直接引用。全部结论带 file:line 证据（行号核对于 2026-10-02 当前 HEAD）。
> 方法：codegraph + 全文 grep 逐一核实既有记忆锚点；只读考古，未改任何代码。

---

## 1. 后端感知管线现状

### 1.1 传感器模型 `colav_simulator/core/sensing.py`（Tengesdal CCTA2023 框架本体，锚点属实）

- ISensor 接口 `sensing.py:20-58`：六方法 R/H/h/reset/seed/generate_measurements；量测格式统一 `list[(do_idx, z)]`。
- 实现仅两个：`Radar`（`sensing.py:191`）、`AIS`（`sensing.py:300`）。**全仓库无第三种 ISensor**（grep `ISensor)` 仅此两处）——无 LiDAR、无相机、无 AoA/方位-only、无红外传感器类。
- RadarParams `sensing.py:62-96`：max_range=1000（:65）、R_ne（:67）、generate_clutter（:71）、clutter_cardinality_expectation=5（:72）、detection_probability=0.9（:73）、include_polar_meas_noise（:74）、R_polar_true（:75）。
- Radar.generate_measurements `sensing.py:219-267`：速率闸（:229，非采样时刻返回 NaN 占位）；距离+检测概率闸（:232-235，**detection_probability 仅在 generate_clutter=True 时生效**，:227）；笛卡尔/极坐标噪声（:236-257）；未检出→NaN（:261）。
- 杂波 generate_clutter `sensing.py:269-289`：Poisson 基数（:282），ownship 为心均匀环内撒点（:283-288），id=-1 标记。
- AIS `sensing.py:300-412`：AISParams max_range=5000（:110）、R 4 维（:112-117）；generate_measurements（:350-374）；速率按航速/等级（:376-404，Class A 2s–180s 分档）。
- **陆地遮挡：无**。sensing.py 全文无 ENC/land/occlusion 引用（grep 证实）；探测判据只有距离圆（:235）。阶段3 雷达陆地遮挡是纯增量。
- **AoA：无**。雷达输出仍是位置（极坐标噪声只是畸变手段，:237-255）；无 bearing-only 量测通道。

### 1.2 tracker 族 `colav_simulator/core/tracking/trackers.py`

- ITracker 接口 `trackers.py:121-182`：`track(t, dt, true_do_states, ownship_state) -> (tracks, measurements)`；`get_track_information -> (tracks, NISes)`（:161-178，第二返回值语义是 **NIS**，非存在概率）。
- TrackSnapshot `trackers.py:54-119`：字段 key/state/covariance/length_m/width_m/observed_at_s/generated_at_s/status/source（:58-66）——**无 existence probability / confidence 字段**（快照层断路证实）。TrackStatus 仅 UPDATED/COASTING/TERMINATED（:24-29）。
- GodTracker `trackers.py:251-353`：detection_range_m=2000（:254）；**绕过传感器**——直接拷贝真值状态（:316-319），协方差恒零阵（:317），量测仍走传感器生成（:336-340）。锚点"GodTracker 绕过之"属实。
- **置信度占位 0.0 仍在原处**：GodTracker.get_track_information `trackers.py:348-353`（0.0 在 :353）；KF 同款 `trackers.py:536-541`（0.0 在 :541）。锚点 trackers.py:536 确认。
- KF `trackers.py:356-541`：CV 模型（:365）；初始化用真值（:424-439，NIS 初值 NaN :437）；数据关联=按 do_idx 精确匹配（:462，注释自称 "Automatic data association"，实为已知 id 关联，无 PDA/JPDA/GNN）；update（:521-534，NaN 量测直通跳过 :524-525）。
- TrackerBuilder `trackers.py:231-248`：config.kf→KF、god_tracker→GodTracker、缺省 KF；**Config 默认 god_tracker=True（:205）**——场景默认走 God。
- VIMMJIPDA：外部 repo。`colav_simulator/integrations/registry.py:122`（`$COLAV_ECOSYSTEM_ROOT/vimmjipda`）、动态 import `vimmjipda.vimmjipda_tracker_interface`（:255-258）；capability=G1，"仅 0.2s 烟雾测试；RMSE/NIS/NEES/ID-switch 门未关"（`colav_simulator/experiment/capabilities.py:190-196`；TRACKERS 注册表 ：180-197）。
- **IPDA 三层断路核实（全部成立）**：
  1. 接口层：get_track_information 只回 NIS（`trackers.py:161-178`），无存在概率通道；KF NIS 初值 NaN（:437）。
  2. 快照层：TrackSnapshot 无字段（:54-66）；ship.get_sim_data 只发布 do_estimates/do_covariances/do_NISes/do_labels/do_generations（`colav_simulator/core/ship.py:868-872`）。
  3. 决策层：NIS 消费仅剩诊断信号 `colav_simulator/decision_replay/signals.py:192-194`；planner/risk 无任何 confidence/existence 消费（grep "confidence|existence" 在决策代码零命中）；唯一协方差决策消费 = `_position_uncertainty_margin`（`colav_simulator/core/colav/encounter_lifecycle.py:1619-1622`，profile.covariance_confidence :131）。

### 1.3 仿真主循环接线 `colav_simulator/simulator.py`

- 真值提取：`simulator.py:395` `mhm.extract_do_states_from_ship_list`（实现 `colav_simulator/common/miscellaneous_helper_methods.py:953`）；relevant 过滤 `simulator.py:404`（mhm:926）；`tracking_from_ownship_only` 闸 `simulator.py:401-403`。
- tracker 调用：`simulator.py:405` `ship_obj.track_obstacles(...)` → `ship.py:711-720` → `trackers.track`。
- 量测保持：`extract_valid_sensor_measurements` `simulator.py:606-633`（缓存最近一次非 NaN 量测，per-ship per-sensor，容器 `simulator.py:97/:178`）。
- 发布：`sim_data["sensor_measurements"]` `simulator.py:423`；planner 输入 do_list=tracks `simulator.py:416`。
- 适配层：`modular_gnc/adapter.py:185-187/:350-351`、`original_gnc/adapter.py:208`；gym 侧自调 track（`gym/observation.py:1064/:1383`）与 get_do_track_information（:166/:1066/:1387）。

### 1.4 快照/文档层（WS 发布）

- 全量 1.0：`gui_server/main.py:1235-1236` 每船 `measurements=raw["sensor_measurements"]`、`tracks=self._local_tracks(raw,...)`；`_local_tracks` `main.py:1572-1587`（labels/generations/states/covariances/**nis**）。envelope `schema_version:"1.0"` `main.py:1177`。
- **compact 剥除点**：`_compact_stream_payload` `main.py:166-192`，`:179` `if key not in {"measurements","tracks","colav"}`——compact-v1（transport :174-175）与 static-once-v1（:195-198）均无感知字段。WS transport 选择 `main.py:2182-2188`（compact-v1 / static-once-v1 / shared-planner-v1）。→ 阶段3 若发置信度，须同时改全量与 compact 两层（compact 是 sango twin 数据面子集契约）。
- decision_replay chart 快照保留全部感知字段（`colav_simulator/decision_replay/chart.py:15-28`：sensor_measurements/do_labels/do_generations/do_estimates/do_covariances/do_NISes）。

### 1.5 决策/风险层消费断点（一句话）

- tracks 进 planner（`simulator.py:416`）；威胁卡/encounter 生命周期只吃 track 状态+协方差（`encounter_lifecycle.py:1619-1622`），**track 置信度链在 tracker→ship→WS 之后断裂：`main.py:1586` 已把 nis 下发到 web，但 UI 不渲染、决策不读、tracker 无字段可给**。

---

## 2. AIS 线

- 仿真 AIS 传感器（仅喂 tracker）：`sensing.py:300-412`。不直接对外发布，Web 看不到" AIS 传感器视角"。
- 真实/历史 AIS 数据流：`colav_simulator/historical_ais.py`（1473 行：dataset descriptor/selection/quality 类族 ：54 起）→ `historical_ais_parquet_worker.py` → `historical_scenario_assembly.py` → `historical_replay.py` 重放为 truth actor。
- 重放 actor 真值发布：`colav_simulator/historical_replay.py:570-576` `payload["historical_actor_truth"]`（actor_id/mmsi/**sample_kind**/trajectory_digest/state_vxvy）；尺寸溯源 ：577-585。
- GUI 层透传：`gui_server/main.py:1231-1234`（`historical_sample_kind` 入 truth 船对象）；shadow 比对 `main.py:1473/:1498`（"INACTIVE / DATA GAP"）。
- AIS 时基：`main.py:792-806` `_runtime_time_document`（ais_utc = time_origin_utc + source_time_s）；web 显示 `web_gui/app.js:700-701`（liveAisUtc）。
- 静态路由：`gui_server/historical_api.py:1288-1367`（/api/historical/scenarios… /ws/historical/{workflow_id}）；web 专用模块 `web_gui/modules/historical-ais-{api,controller,render,workbench,projection}.js`（workbench 面板，不进 situation-display 主图）。
- **阶段3"AIS 数据显示"要接的缝**：live 会话中 AIS 目标 = 真值 actor + sample_kind 标签（`app.js:1244` "AIS state" 卡），**没有独立 AIS 目标层**（无 last-seen 时龄、超时灰显、AIS 目标卡）；`sensing.py` 的 AIS 传感器与展示层完全脱节。接缝=truth[].historical_sample_kind 已有字段 + situation-display 新层 + `_local_tracks` 同款透传点（`main.py:1572`）。

---

## 3. Unity 侧（sango，HDRP 17.3.0）

- **FramePublisher** `sango/Assets/Scripts/Runtime/FramePublisher.cs:26`：PUB bind tcp://127.0.0.1:5556（:31-32/:277），topic `sango.frame`，3 段 multipart [topic][FrameMetadata JSON][JPEG]（:253-255），10Hz 上限（:79），默认关闸 `PublisherEnabled=false`（`Runtime/Vessels/SangoSeamConfig.cs:15`），CLI 旗标 `--sango-publisher`（SangoSeamConfig.cs:24）。捕获=单相机 CameraCaptureBridge（:145-149），3 slot 异步读回（:63/:204）。
- **检测回传**：`Runtime/DetectionResultConsumer.cs:24` SUB connect 5557（:30；SangoSeamConfig.cs:27），topic `sango.detection`（:33），后台线程（:134-166），TryTakeFresh 新鲜度（:112-131）。YOLO 服务 `tools/sango_detector_service.py:42-51`（SUB 5556→ultralytics YOLO→PUB 5557，默认 models/yolov8n.pt :44）。
- **DetectionOverlay live/GT 双路** `Runtime/DetectionOverlay.cs:10-11`：有新鲜 YOLO 结果按 box_xyxy 直绘，否则回退 ground-truth（:42-54 判定）；GT 构造 ：129-153（source="ground-truth", confidence=1）。契约 `sango/Docs/contracts/{frame-publisher-v1,detection-result-v1,detection-return-v1}.md`。
- **相机阵列扩展点**：`Runtime/Vessels/CameraViews.cs:6-13` 五视图枚举（Bridge/Bow/Chase/TopDown/Overlook）+ 纯函数位姿解析（:76/:84）；`Runtime/CameraRig.cs:15` 单相机受控切换。加"传感器机位"两条路：(a) 扩 CameraView 枚举（最省，但 FramePublisher 只挂一个 sourceCamera，:41/:145）；(b) **每传感器独立 Camera + 独立 FramePublisher 实例**（组件天然多实例，endpoint/topic 可配）——推荐 (b)，X 波段/IR/LiDAR 各一机位互不抢渲染预算。
- **雷达呈现已有底座**：`Runtime/RadarOverlay.cs:17`（PPI 风格 UI：RangeM :26，200–2000m 步进 :32，sweep :29，blips :113）——但目前 blip=真值 Transform，无检测/遮挡语义。
- **夜景/IR 曝光链**：`Runtime/NightGrade/NightGradeCore.cs:13-62`（NightEvFadeDeg :17、NightFloorEv :20 曝光补偿纯函数、灯标 halo :36-62）——IR 白热/黑热呈现可挂此分级思路，但无 IR sensor pass/热成像材质。
- **点云渲染现成依赖**：`sango/Packages/manifest.json`（HDRP `com.unity.render-pipelines.high-definition 17.3.0`）；`packages-lock.json:114` `com.unity.visualeffectgraph 17.3.0`——VFX Graph 可用于 LiDAR 点云渲染；**无专用 point cloud 包**（需自写 VFX Graph SampleTexture/GraphicBuffer 路径）。
- Twin 数据面：`TwinBridgeService` + 契约 `sango/Docs/contracts/twin-bridge-v1.md`（attached.ships :49）——传感器叠加/置信度下发 Unity 的扩展缝=同一 URS DataChannel 加消息词汇（先例：2026-10-02 加 camera_free，只加字段不改形，twin-bridge-v1.md:107）。

---

## 4. 观测注入端点（评估，不改）

- 路由清单：`gui_server/main.py` POST 仅 `/api/sessions`(:1857) `/start`(:1884) `/pause`(:2063) `/reset`(:2075) `/select_algorithm`(:2088) `/set_speed`(:2120) `/busy-water/drafts`(:1849)；WS `/ws/sessions/{id}`(:2180) `/ws`(:2192)。**无任何 observations 注入端点**——PHASE1-PLAN 预留判断仍成立（`docs/research/2026-09-22-sango-prototype/PHASE1-PLAN.md:253/:255`，建议路径 `POST /api/sessions/{id}/observations`）。
- **量测进入分界（唯一入口）**：`simulator.py:405 track_obstacles` → `trackers.py:338`（God）/:446（KF）`sensor.generate_measurements(t, true_do_states, ownship_state)`——量测由 tracker 内部从**真值**即时仿真，不存在外部量测通道；`true_do_states` 参数仅用于"仿真出"量测。
- 最小改动面：
  1. 端点：FastAPI 路由 → `WebSessionManager`（`main.py:541`）→ session.simulator；坐标系换算复用 ENC origin（`main.py:1204` origin_n/origin_e 先例）。
  2. 量测通道：**per-ship per-sensor 缓存已存在**（`simulator.py:97/:178` + `extract_valid_sensor_measurements` :606-633）——外部量测可作为"虚拟传感器"并列写入该缓存；KF.update 按 sensor_id 取 R/H（`trackers.py:459-467`），天然支持新增 sensor，**tracker 签名零改动**。
  3. 或新增 `ExternalSensor(ISensor)`：generate_measurements 返回注入队列而非真值仿真——ISensor 接口（`sensing.py:20-58`）即缝。
  4. **关键风险：GodTracker 无视量测**（`trackers.py:316` 直用真值）——注入端点仅在 KF/VIMMJIPDA 路径生效，而 Config 默认 god_tracker=True（`trackers.py:205`）；阶段3 须先切默认 tracker。

---

## 5. web 展示（web_gui）

- situation-display.js 图层契约：`LAYER_ORDER` `web_gui/modules/situation-display.js:76-96`（measurements/tracks/covariance/detectionZones 均为独立层）；DEFAULT_LAYERS measurements/tracks/covariance 默认关（:108-110）。
- 渲染：drawMeasurements :1028、drawTracks :1029（密集交通 ≥40 目标抑制 :1385）、协方差椭圆 :1264-1276、drawCovariance :1279-1298（只取 [0][0]/[1][1]/[0][1]）；雷达探测圈 RADAR_DETECTION_RANGE_M=2000（:39，绘制 ：1629）；radarRange/responseRange 圈 palette :112-113。
- radar-mini-map.js `buildRadarModel` :12-40：**只吃 truth obstacles（snapshot.obstacles），不吃 tracks/measurements**；调用点 `web_gui/app.js:2517/:2574/:2628`。
- **nis 已下发但不渲染**：`main.py:1586` → `web_gui/modules/replay-source.js:105`（`nis: raw.do_NISes ?? []`）仅透传；situation-display 无消费。
- 阶段3 挂点：(a) 置信度/存在概率 → `_local_tracks`（`main.py:1572-1587`）单点扩字段 + situation-display 新 layer/目标卡（threatPlot 层 :84-85 是先例）；(b) AIS 目标卡 → truth[].historical_sample_kind（`main.py:1231`）已可用；(c) compact-v1 契约若扩感知字段须同步 sango 侧 `ColavTelemetry` 必填字段声明（PHASE1-PLAN.md:198 已警告按子集声明）。

---

## 6. 缺口总表（传感器 × 四列）

| 传感器/能力 | 后端模型 | Unity 呈现 | web 展示 | 融合输入 |
|---|---|---|---|---|
| X 波段雷达 | **有**：Radar（sensing.py:191）圆界+杂波+Pd；**无**陆地遮挡/海杂波/扇区 | 部分：RadarOverlay.cs:17 PPI（真值 blip，无检测语义） | 部分：radar-mini-map truth + 2000m 圈（situation-display.js:39） | **有**：KF 已吃（trackers.py:459-467） |
| LiDAR 点云 | **无**（无 ISensor 实现） | 部分：VFX Graph 17.3.0 可用（packages-lock.json:114），无现成点云渲染器 | **无** | **无** |
| 白光相机 | **无**（检测在 Unity 侧 YOLO） | **有**：FramePublisher→YOLO→DetectionOverlay 全链（5556/5557） | **无** | **无**：DetectionResult 止步叠加，无 observations 端点 |
| 红外相机 | **无** | 部分：HDRP+NightGrade 曝光链（NightGradeCore.cs:13），无 IR pass/热成像 | **无** | **无** |
| AIS | 部分：AIS 传感器（sensing.py:300）只喂 tracker；历史 AIS 真值链完整（historical_replay.py:570） | **无**（twin ships 无 AIS 语义） | 部分：sample_kind 标签（app.js:1244），无独立目标层/目标卡 | 部分：KF 可吃 AIS 4 维量测；**无雷达-AIS 融合器** |
| 持续跟踪 | 部分：KF CV+id 关联（trackers.py:356）；无 PDA/GNN、无航迹生命周期管理（M/N 删逻辑） | 有：DetectionOverlay 框 | 有：tracks 层（situation-display.js:1029） | — |
| 置信度/存在概率 | **无**：0.0 占位（trackers.py:353/:541）、TrackSnapshot 无字段（:54-66）、默认 God（:205）绕过全部 | **无** | **无**：nis 透传不渲染（replay-source.js:105） | **无**：决策唯一协方差消费 encounter_lifecycle.py:1619 |

**三条最短关键路径**：(1) 默认 tracker God→KF/VIMMJIPDA（trackers.py:205）是置信度/融合一切的前置；(2) observations 端点最小面 = 新路由 + ExternalSensor(ISensor) + simulator 量测缓存（simulator.py:606），tracker 零签名改动；(3) 感知字段过 compact 需同改 main.py:179 剥除名单与 sango ColavTelemetry 子集契约。
