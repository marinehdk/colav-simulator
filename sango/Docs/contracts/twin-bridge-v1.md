# twin-bridge-v1 — web ↔ Unity Digital Twin 控制桥契约

状态：**已冻结**（2026-10-02，P2-S3，spec #89）。本文由
`docs/research/2026-10-02-phase2-unity-web-integration/twin-bridge-v1-draft.md` 冻结落地，补实现级细节。
定位：web 页面（唯一 UI 编排权威）↔ Unity sango（渲染端）之间的**控制+状态**通道。遥测不走此桥——
Unity 直连后端（live=WS compact-v1；replay=window REST），浏览器不做中继（00-REPORT §4 原则 1/2）。

实现：`Assets/Scripts/Runtime/TwinBridgeService.cs`（编排）+ `TwinBridgeChannel.cs`（URS DataChannel 载体）+
`Vessels/Twin/TwinBridgeMessage.cs`（DTO/序列化，EditMode 回环已测）+ `Vessels/Twin/TwinReconnectPolicy.cs`（退避纯函数）。
web 侧：`web_gui/modules/twin-view.js` + `web_gui/vendor/urs/`（URS 官方 receiver 模块本地化）。

## 1. 传输绑定

| 路线 | 载体 | 说明 |
|---|---|---|
| **像素流主线（本版冻结）** | URS WebRTC DataChannel，label 恒 `twin-bridge` | Unity 侧 local=true（Unity 创建，浏览器 `createDataChannel` 不需要——onAddChannel 收）；与视频轨同一 PeerConnection |
| 伴生辅线（未启用，保留形状） | `ws://127.0.0.1:5558`（localhost only） | Unity 侧内嵌 WS 服务；5556/5557 已被 frame/detection 占用 |

约束：

- 单页单连接；消息 = **单个 UTF-8 JSON 文本帧**；无二进制。
- 可靠有序（WebRTC DataChannel 默认 reliable/ordered）。
- 连接 ID 约定：URS `connectionId`（uuid）为不透明对端标识，Unity 侧只绑定**最近一次打开**的
  `twin-bridge` 通道；旧通道关闭即失效，不寻址（无 per-connection 路由语义）。
- 演进只加字段不删不改（Unity `JsonUtility` 忽略未知字段；web `JSON.parse` 宽松消费）。
- 握手：web 通道 open 后**必须先发 `hello`**；Unity 回 `ready`。`hello` 之前的其它消息 Unity 静默丢弃（防半开连接脏命令）。

## 2. 消息（web → Unity）

| type | 字段 | 语义 |
|---|---|---|
| `hello` | `protocol:"twin-bridge@1"`, `page` (nonce 字符串) | 握手；Unity 回 `ready` |
| `attach` | `run_id`, `mode:"live"\|"replay"`, `backend_base`, `replay:{t_start,t_end,trusted_t_end}`（replay 必带，秒） | Unity 自连后端取数；新 attach 替换旧（幂等重挂，同 run 重挂 = 重置数据面） |
| `detach` | — | 断开数据面，回空场景态（船清空、泵停、流状态 down→idle） |
| `clock` | `playhead_s`, `rate`, `state:"PLAYING"\|"PAUSED"\|"ENDED"` | **仅 replay 模式**：PLAYING 时 ~10Hz；PAUSED/ENDED 状态切换时至少发一条；Unity 软对齐渲染钟（与 compact-v1 同哲学）；live 模式时钟权威在后端，web 不发此消息 |
| `camera` | `preset:"bridge"\|"bow"\|"chase"\|"top"\|"overlook"` | 预设词汇统一表 → `CameraView.{Bridge,Bow,Chase,TopDown,Overlook}`（00-REPORT §5.3） |
| `camera_free` | `pos:{east,north,height_m}`, `yaw_deg`, `pitch_deg`, `fov_deg` | **P2-S4 演进新增（§8）**：Cesium↔Twin 分屏主从联动的自由位姿（单向 Cesium 主→Twin 从，web 侧默认关，逐帧锁步不做）。`pos` 为相机锚点**全域 UTM 米**（与 `attached.anchor` 同一框架，Unity 侧减锚得场景坐标）；`height_m` 椭球零视觉约定（ENC 网格 h=0 同基准）；`yaw_deg` 北向东顺时针；**`pitch_deg` 负=俯**（CameraPose 语义沿用）；`fov_deg` 垂直向度。生效中 `state.camera`/`attached.camera` 回显 `"free"`；任何 `camera` 预设消息收回控制权 |
| `theme` | `value:"day"\|"night"\|"dusk"` | 映射 Unity 时刻档：`day=12h, dusk=17.5h, night=0h`（`WeatherGUI.k_TimePresets` 同源） |
| `stream_profile` | `value:"1080p"\|"1440p"` | WEB 捕获档：1920×1080 / 2560×1440，30 fps，码率范围 6–14 / 10–24 Mbps；相机 TAA。只改变视频捕获与编码；不影响仿真/回放时钟。仅 `ready.video_profiles` 明确支持时发送。 |
| `detection` | `enabled`, `source:"yolo"\|"truth"` | `enabled=false` = overlay 关；`truth` = 地面真值路径（`requireLive=false`）；`yolo` = live 优先路径（`requireLive=true`，无新鲜结果按 DetectionFreshness 既有规则回退）。复用 M9 `DetectionOverlay` |
| `sensor_mode` | `value:"eo"\|"ir"\|"lidar"` | **P3-S0 演进新增（§8，spec #90）**：主孪生视口传感器模式——eo=可见光（默认，驾驶舱视角）/ ir=黑白热像 / lidar=点云视角；雷达 PPI/AIS 为 web 面板态不经此桥。词汇 = `TwinBridge.SensorModes` / web `TWIN_SENSOR_MODES`；视口按钮组接线属 S2 |

时钟节流：web 端以 `ReplayClock` 驱动，10Hz 定时器对 `playhead_s` 采样发送；`rate` 变更即时补发。
Unity 渲染钟把 `rate` 写进所喂帧的 `playback.effective_multiplier`（S1 管线零改动消费）。

## 3. 消息（Unity → web）

| type | 字段 | 语义 |
|---|---|---|
| `ready` | `protocol`, `build`, `scene`, `modes_supported[]`, `video_profiles[]` | 对 `hello` 的应答；`modes_supported` ⊆ `["live","replay"]`；`video_profiles` 缺失或为空 = 不支持画质协商。 |
| `attached` | `run_id`, `mode`, `anchor:{east,north}`（全域 UTM 米）, `ships`（int，已挂槽位数）, `camera`（当前预设名） | 数据面就绪：replay = context（ENC 原点）取到后发；live = 首帧锚定后发。**数据面重连恢复后重发**（§5） |
| `state` | `fps`, `frame_seq`, `sim_time`, `clock_skew_ms`, `stream:{state:"ok"\|"degraded"\|"down", latency_ms}`, `detection:{source,enabled,live}`, `camera`, `sensor_mode`, `geo_fit` | ~1Hz 心跳。`sim_time` = Unity 渲染插值钟；`clock_skew_ms` = 渲染钟 − web playhead（ms）；`stream`：replay = 帧泵健康（帧前进 ok / 停滞 degraded / 取数失败 down），live = WS 连接态；`latency_ms` = \|clock_skew\|；未知为 0；`detection.enabled` = web 既有开关态回显（P3 演进只加字段，§8）；`sensor_mode` = 当前主视口传感器模式回显，默认 `"eo"`（P3-S0 演进只加字段，§8，spec #90）；`geo_fit` = M6 场景覆盖度判定回显 `"inside"\|"partial"\|"outside"`，空串 = 尚无数据面帧（P3-12 演进只加字段，§8，spec #91） |
| `error` | `code`, `message` | 码表见 §4 |

## 4. 错误码表（冻结）

| code | 致命性 | 触发 |
|---|---|---|
| `BAD_MESSAGE` | 非致命（连接保持） | JSON 解析失败 / 必需字段缺失或非法（未知 `type`、`attach` 缺 `run_id`/`mode`、replay 缺 span 等） |
| `UNSUPPORTED_MODE` | attach 拒绝 | `mode` ∉ `modes_supported` |
| `UNSUPPORTED_PROTOCOL` | 握手拒绝 | `hello.protocol` ≠ `twin-bridge@1` |
| `BACKEND_UNREACHABLE` | 数据面失败 | `backend_base` 连接/超时失败（传输层） |
| `RUN_NOT_FOUND` | attach 拒绝 | 后端 404（run id 无效或已删除） |
| `RUN_NOT_PLAYABLE` | attach 拒绝 | descriptor 状态不可播（非 READY / INCOMPLETE 且不可 seek） |
| `REPLAY_FETCH_FAILED` | 数据面失败 | replay window/context 取数中途失败（非 404/传输层失败归 `BACKEND_UNREACHABLE`）；`state.stream=down`，泵自动重试 |
| `REBUILD` | **非错误**（信息性） | seq 倒退重建（live 会话重建 / replay 回退 seek）；Unity 清船重挂，`attached` 重发 |

错误不关桥：桥通道存活期间 Unity 持续可用；数据面级错误（`BACKEND_UNREACHABLE`/`REPLAY_FETCH_FAILED`）由泵按 §5 重试。

注（P3 台账）：`REBUILD` 现无显式 error 发出路径——重建以 `attached` 重发体现（§3/§5），错误码保留给未来显式场景。

## 5. 断线与重连

- **数据面断（live）**：WS 收包线程退出后若 `autoReconnect`（bridge 侧恒 true）→ 退避
  `1s → 2s → 5s → 5s …`（`TwinReconnectPolicy`，封顶 5s）重连同会话；恢复后 Unity 清管线
  （seq 闸门 Rebuild 语义）并**重发 `attached`**；重连期间 `state.stream=down`。
- **数据面断（replay）**：window 取数失败 → `error REPLAY_FETCH_FAILED` + 退避同表重试当前窗口；连续失败保持 down，playhead 推进后自愈。
- **桥断**：DataChannel 随 PeerConnection 重建（页面刷新 = 新 hello/attach，Unity 幂等重挂，旧槽清空）。
- web 端重连语义：页面只重发 `hello` + `attach` + 当前 `camera`/`theme`/`detection`，随后恢复 clock 节拍。

## 6. 序列化样例（冻结字面量，双侧测试对拍同源）

```json
{"type":"hello","protocol":"twin-bridge@1","page":"s3-probe"}
{"type":"attach","run_id":"3e19f9e6-741c-48b2-84bf-3ec5e90e1ceb","mode":"replay","backend_base":"http://127.0.0.1:8010","replay":{"t_start":0.1,"t_end":40,"trusted_t_end":40}}
{"type":"detach"}
{"type":"clock","playhead_s":12.5,"rate":1,"state":"PLAYING"}
{"type":"camera","preset":"top"}
{"type":"camera_free","pos":{"east":37012.5,"north":6955012.25,"height_m":120},"yaw_deg":45,"pitch_deg":-35,"fov_deg":60}
{"type":"theme","value":"night"}
{"type":"detection","enabled":true,"source":"truth"}
{"type":"sensor_mode","value":"ir"}
{"type":"ready","protocol":"twin-bridge@1","build":"1.0","scene":"SangoTwin","modes_supported":["live","replay"]}
{"type":"attached","run_id":"3e19f9e6-741c-48b2-84bf-3ec5e90e1ceb","mode":"replay","anchor":{"east":544302.5,"north":6323000.25},"ships":3,"camera":"bridge"}
{"type":"state","fps":30.5,"frame_seq":41,"sim_time":12.4,"clock_skew_ms":35.0,"stream":{"state":"ok","latency_ms":35.0},"detection":{"source":"truth","enabled":true,"live":false},"camera":"bridge","sensor_mode":"eo","geo_fit":"inside"}
{"type":"error","code":"RUN_NOT_FOUND","message":"backend returned 404 for run 3e19…"}
```

注：`JsonUtility` 序列化恒写全字段（无可空省略）——`stream.latency_ms` 未知时为 `0`；web 侧按"缺字段 = 取默认"宽松消费。

## 7. 验收钩子

- C# 回环：`TwinBridgeMessageTests`（EditMode）——§6 样例字面量反序列化 + serialize→deserialize→serialize 逐位无损 + 未知字段容忍。
- web 侧：`tests/web_gui/twin-view.test.mjs`——同一批 §6 字面量为期望构造/解析。
- E2E：`tools/sango_twin_bridge_probe.mjs`——伪 UI 驱动真 web_gui 页面走 hello→attach→clock→camera 全消息面，断言 ready/attached/state 回包与 SIM TIME 对拍。

## 8. 演进记录（只加字段条款 §1 的行级台账）

| 日期 | 段 | 变更 | 溯源 |
|---|---|---|---|
| 2026-10-02 | P2-S3 | 契约冻结（§1-§7） | spec #89，`a430fc62` |
| 2026-10-02 | P2-S4 | web→Unity 新增 `camera_free` 消息（§2 表 + §6 样例）；`state.camera`/`attached.camera` 新增回显词汇 `"free"`（§3 注）。**只加字段/只加词汇**：既有消息形状零改动（`JsonUtility` 忽略未知字段、web `JSON.parse` 宽松消费，双侧旧实现互通）。语义边界：仅 Deployment twin 态的默认关联动开关产生此消息；单向 Cesium 主→Twin 从，反向不做，逐帧锁步不做 | spec #89 S4；CesiumJS `camera.changed`（`percentageChanged` 0.01）位姿折算纯函数 = web `twin-view.js#cameraFreePose`，Unity 应用 = `CameraRig.SetFreePose` |
| 2026-10-02 | P3 清零批 | `state.detection` 新增 `enabled`（bool，web 既有 detection 开关态回显；此前 `m_DetectionEnabled` 为死字段）。**只加字段**：`detection:{source,enabled,live}`，旧 web 侧宽松消费零影响；§6 样例同步；附 §4 `REBUILD` 保留注（无显式发出路径，重建以 `attached` 重发体现） | spec #89 P3 残留清零批（review F7/F8 同批） |
| 2026-10-02 | P3-S0 | web→Unity 新增 `sensor_mode` 消息（§2 表 + §6 样例，复用 theme 同款 `value` 字段面）；`state` 新增 `sensor_mode` 回显字段（默认 `"eo"`，词汇 `eo\|ir\|lidar`；§3/§6 同步）。**只加 type/只加字段**：既有消息形状零改动（Unity `JsonUtility` 忽略未知字段、web `JSON.parse` 宽松消费，双侧旧实现互通；旧 Unity 构建的 state 无此字段 = web 侧 undefined，已测）。语义边界：雷达 PPI/AIS 为 web 面板态不经此桥；视口按钮组与渲染切换接线属 S2/S3（本段零运行时行为变化，仅 DTO 词汇面 + 回环测试） | spec #90；词汇/默认值 = `TwinBridge.SensorModes`/`DefaultSensorMode`，web = `TWIN_SENSOR_MODES`/`TWIN_SENSOR_MODE_DEFAULT`，sender = `client.sendSensorMode` |
| 2026-10-02 | P3-S2 | `sensor_mode` 接线落地（spec #90）：Unity 侧 `TwinBridgeService.HandleSensorMode`（BAD_MESSAGE 拒未知词汇）+ 渲染效果 = `TwinBridge.SensorModeEffect` 纯函数——eo=默认渲染 / ir=流相机 IR 白热 pass（`IrViewPass` 静态闸，作用域 = 流相机，Demo 渲染零变化）+ 材质温度 tag（`ThermalTagApplier`，温度档表 `MastCameraTable`）/ **lidar=占位：切换被接受 + state 回显，点云渲染留 S3；UI 方案二选一取"pending 明示"**（Evaluation twin + Deployment twin 按钮组常显 LiDAR·S3 徽标，禁用按钮方案弃——保留消息路径可 E2E）。`camera` 预设与 sensor_mode 正交叠加（切换不改 CameraRig 状态，契约 §2）。web：Evaluation twin（`twin-view.js` 控制器 `twinSensorGroup`）与 Deployment twin（`deployment-twin.js` `sensorGroup`）按钮组 + `state.sensor_mode` 回显投影（`projectSensorMode`/`sensorModeItems`，未知/缺字段回退默认 eo）+ §5 重连 realignment 重发当前模式 | spec #90 S2 |
| 2026-10-02 | P3-S3 | `sensor_mode=lidar` 真实现落地（spec #90，替换 S2 占位）：Unity 侧 `SensorModeEffect` 第二出参改语义 `lidarRenderActive`（词汇/默认值/消息形状零变化）——lidar = 流相机点云视角（`LidarViewPass` 深色背景 + `mast_lidar` 深度采集 16 线点云，`LidarDepthCapturePass` 桅顶深度 CustomPass；静态闸工艺同 IR，Demo 渲染零变化；mast 表加 `mast_lidar` 行 11 m/下倾 10°，后端 `mast_cameras.py` 同字面量互钉）。渲染与相机预设正交叠加不变。web：S2 的 "LiDAR·S3 · PENDING" 徽标移除（`TWIN_SENSOR_MODE_LABELS.lidar='LiDAR'`，`sensorModeItems` 去 `pending` 字段，两处 chip 不再拼 pending 尾巴），三键均真实现。**PiP 副视口降级 backlog**：EO/IR 模式下小窗看 LiDAR 点云需第二路 URS 视频流（调研 §5 640×480@1-2Mbps + 第二硬件编码器 + 第二 track + 接收端多流选择 UI），本段成本不成比例；LiDAR 模式主视口即点云已覆盖核心需求，PiP 留后续段评估 | spec #90 S3 |
| 2026-10-02 | P3-12 | `state` 新增 `geo_fit` 回显字段（词汇 `inside\|partial\|outside`，空串 = 尚无数据面帧；§3/§6 同步）。**只加字段**：既有消息形状零改动（web `JSON.parse` 宽松消费，旧 web 侧 undefined 已测兼容）。语义：M6 孪生场景地理配准（`scenePos = (NE − anchor) + 登记平移 (17000,−4800)`，会话 NE 域为后端合成域、与场景 EPSG:32648 域纯平移对应）的覆盖度判定——inside = 会话观测包络 ≥98% 水面且 DEM 覆盖内 / partial = 混入陆域 / outside = DEM 覆盖外开阔海面；常量与 provenance = `M6TwinGeo` + `M6WaterMask`（tools/m6_water_mask.py 烘焙） | spec #91 批 1 台账 P3-12；Unity = `TwinBridgeState.geo_fit`/`TwinSessionDriver.GeoFit`，web 宽松消费无需改动 |

| 2026-10-08 | WEB 画质适配 | 新增 stream_profile 命令和 ready.video_profiles 协商字段，1080p/1440p 两档 30 fps；旧 Unity 缺字段时 web 不发新命令。Deployment 使用接收端 RTP 计数计量视频 fps/码率，既有 state.fps 与 clock 字段语义不变。 | DT 清晰度修复 |

### 2026-10-08 DT direct camera and live presentation

`state.camera_pose` is an optional additive object: `east`, `north`,
`height_m`, `yaw_deg`, `pitch_deg`, `fov_deg`, using the same global UTM and
vertical FOV convention as `camera_free`. It echoes the actual Unity camera
so the first direct mouse gesture starts at the displayed pose. Legacy clients
may ignore it. Mouse gestures coalesce to at most 30 commands/s, with a final
flush on pointer release; Cesium link mode retains sole camera control.

Live rendering buffers three wall seconds of truth, matching Deployment's
presentation cache, and interpolates between received distinct snapshot times.
Missing playback metadata retains the last known rate; same-seq heartbeats can
update pause/rate without replacing truth. No extrapolation or new simulation
clock authority. Pause snaps to the authoritative snapshot; resume refills the
`state.presentation_buffering` optionally reports cache warmup. Replay retains its explicit web clock. Global UTM
coordinates stay double precision until anchor subtraction and scene placement.

### 2026-10-09 Session environment and six-axis presentation

The additive compact telemetry `environment` object carries session-owned wind,
current, Hs/period/direction and DT weather settings. Compass bearings are FROM
north clockwise; HDRP orientation is converted explicitly. Physical settings
initialize the admitted original/modular environmental models; appearance fields
never create an additional backend dynamics authority. Wind/current/Hs readbacks
use the executing field when available. OFF disables external loads and visual
weather; propulsion-generated bow waves remain possible on calm water.

`truth[].has_roll` and `roll_rad` identify recorded/backend 4DOF roll. Unity
interpolates this source and applies it in the canonical body frame, accounting
for prefab bow yaw, without adding surface-fit roll. Heave/pitch remain damped
water-surface visual responses. `state.motion` echoes `visual_heave_m`,
`visual_pitch_deg`, `roll_deg` (NED sign) and `roll_source` (`backend_4dof` or
`surface_visual`). Optional `propwash_foam`, `wave_contact_foam`, and
`bow_entry_mps` report actual native WaterDecal injection/contact inputs.
`native_foam_peak` is the asynchronously sampled maximum of the whole water
decal-region surface channel (10 s cadence, not a per-frame propulsion-only value). Propwash
requires advancing presented truth (live RUNNING, or advancing replay); initial
configured speed in CREATED, paused/stalled presentation and seek-back do not
inject propulsion wake. Ambient wave contact remains independent of propulsion.
Twin never draws the legacy ribbon/ring meshes. Native foam persists and erodes
in the water buffer; current influence animates erosion, not mass advection.
This is six-axis presentation, not a six-DOF hydrodynamic plant.

New replay contexts preserve recorded environment settings; replay frames use
recorded GNC balance or original `state_8d` for roll. Missing historical appearance
settings stay null. No replay read executes simulation or manufactures acceptance.

DT bow deformation/foam use water decals; propeller wash uses a water-conforming
centre strip advected by current and scaled by through-water speed. Ground-speed
vector displays retain SOG. Rain/sky wind and night navigation lamps are visual
feedback. Spectral style, rain/snow/wet lens, light streaks and water-wave Hs/period
mapping are engineering visual approximations, not certified Aeolus or sea trials.

### DT situation display (2026-10-10)

The hybrid display keeps world geometry in Unity and reuses web OpenBridge POIs,
target cards, AIS symbols and the compass. Dense contacts use OpenBridge offset
POIs: deterministic head placement prioritizes selection/primary/alarm, reserves
space for the card, and leaves each pointer on its original vessel projection.
Auto-grouping is avoided because its shared horizon row ignores per-target
buttonY. It adds three message types:

- presentation: {presentation:{run_id,seq,sim_time,ribbon,waypoints,lines,targets,
  time_markers,vo,ships_visible,waypoints_visible}}. Coordinates are global UTM
  east/north metres. This is read-only display geometry derived from the existing
  web projection, not a ship-state, clock or threat-authority input. Unity uses
  the latest display snapshot whose simulation time has reached its presented
  ship pose. Targets retain the run:id:generation identity and truth flag;
  tracker POIs keep their estimated position rather than snapping to truth.
- situation_frame: {run_id,frame_id,source_seq,telemetry_seq,sim_time,width,height,
  camera,camera_yaw,targets,waypoints,time_markers}. Positions and pick bounds
  are normalized in the actual stream camera, with y downwards.
- pick: {run_id,frame_id,x,y}; reply situation_pick includes the selected
  id,key or null. Picking uses the bounds cached for the displayed video frame,
  chooses the nearest visible vessel and rejects retired target generations.

The ready field situation_sync="frame-marker@1" advertises support. A 256x16 px
camera canvas in the upper-left encodes 32 black/white cells: header 0xD3, 16-bit
frame counter, checksum (high_byte XOR low_byte XOR 0x5A). The web samples decoded
video on requestVideoFrameCallback, matches that counter and resolution to a
bounded DataChannel projection cache and applies object-fit:contain offsets.
The web DT chip covers the marker. Missing, corrupt, mismatched or stale frames
hide the AR layer; they never reuse a newer camera heartbeat. Video and projection
may arrive in either order. Reattach/detach clear projection and pick caches.

Threat appearance and CPA availability come from the same scene-target.js
presentation used by Cesium. The Unity display does not calculate threat levels.
This display protocol does not create, start, reset or replace an Active Session.
