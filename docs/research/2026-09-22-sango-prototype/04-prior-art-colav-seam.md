# 04 既有平台对比 + Colav-Simulator 集成缝

日期：2026-09-22。性质：平台对比（网络一手来源，许可/元数据经 GitHub API 当日复核）+ 本仓库代码调研（file:line）。服务对象：阶段1"视觉优先"Prototype 的复用-vs-自研决策，及阶段2 Unity 接入 Colav-Simulator 的最小桥接。

---

## A. 既有平台对比

### A.1 对比表（事实列均于 2026-09-22 经 GitHub API / raw 文件复核）

| 平台 | 引擎 | 视觉保真度 | 感知输出 | 许可 | 二开成本 | 与阶段1差距 |
|---|---|---|---|---|---|---|
| VRX | Gazebo (Harmonic) + ROS 2 | 低：面向算法竞赛的功能渲染，无电影级水体 | 成熟：camera/3D lidar/GPS/IMU 等 ROS 2 话题 | Apache-2.0（API 复核）；746★，pushed 2026-08 | 高：需 Ubuntu+ROS2 工具链，官方文档默认 Linux | 视觉差距最大 |
| ASVSim | Unreal Engine 5.5.4（Cosys-AirSim fork） | 中高：UE5 写实港/内河环境截图，但水体非海况级谱方法 | 强：相机+实例分割、GPU-LiDAR、PSF 航海雷达、回波传感器 | MIT（LICENSE.txt：AirSim 原 MIT + IDLab 修改同 MIT）；56★ | 中：UE/C++ 插件；**README 自述"will not be actively updated"** | 最接近可用，仍非 Aeolus 海面 |
| HoloOcean | UE5（2.x） | 中：UE5 渲染，产品定位水下声呐 | 声呐系（成像声呐等）、相机；v2.3 文档含 surface-vessel agent | ROS 桥 MIT；**主仿真器源码在 GitHub 不可见**（org 仅 docs+ros 两个仓库） | 高：以发布包分发，二次开发受制 | 水下导向，海面 COLREG 非目标 |
| MARUS | Unity 2021.3 LTS | 低：科研级基础水景 | gRPC 桥传感器接口 | Apache-2.0（marus-core）；27★，pushed 2026-03 | 中：Unity 但版本旧、社区小 | 视觉/体量双不足 |
| BoatAttack | Unity URP demo | 中：风格化低多边形；Gerstner 水体+平面反射+caustics，README 自述"no compute" | 无（纯渲染 demo，仅 C# Jobs 浮力） | Unity Companion License（限 Unity 项目内使用） | 低：即 Unity 项目，水体代码可直接借力 | 非仿真平台，是资产/技术参照 |

来源：VRX 元数据与 README（api.github.com/repos/osrf/vrx；raw README"Gazebo Sim and ROS 2 by default"）；ASVSim README（raw，UE 5.5.4、3-DOF Fossen、PSF 雷达、GPU-LiDAR、Apple Silicon 支持及"not actively updated"声明）与 LICENSE.txt；HoloOcean 组织清单（`gh api users/BYU-HoloOcean/repos` 仅返回 holoocean-docs、holoocean-ros）及 docs 仓库 v2.3.0 目录树含 surface-vessel-agent 页；MARUS marus-core README（Unity 2021.3 LTS、Apache-2.0）与 API 元数据；BoatAttack README（URP、Gerstner、planar reflections、C# Jobs buoyancy）与 LICENSE.md（Unity Companion License）。视觉"低/中/高"评级为对照 Aeolus 参考画面的推断，非官方声明。

### A.2 核心问题：复用 vs Unity 自研

**结论：阶段1 应 Unity 自研（大量现成资产），不复用任何平台。** 依据：

1. **视觉是唯一裁决项，且没有平台达标。** 阶段1 验收基线是 Aeolus Ocean 论文级画面（谱方法海面+SSR/SSS/泡沫+体积云）。VRX/MARUS 是功能渲染；HoloOcean 定位水下；ASVSim 视觉最好但为港/内河场景，且其 README 明示仓库"按现状提供、不积极更新"——把阶段1 画面基线押在一个自述停更的 fork 上不可取。 BoatAttack 的 Gerstner/平面反射/caustics 是可借用的水体技术，但其风格是低多边形竞速而非写实海况（README 自述），只能当资产与技术参考，不能当平台。
2. **阶段1 不需要任何平台的感知输出**（感知接入是阶段3），故"传感器成熟度"不构成复用理由；而 VRX/ASVSim 的传感器语义（相机/LiDAR/雷达话题）在阶段3 仍可作行为对照，不影响现在的决策。
3. **工具链成本不对称。** VRX 需要 Ubuntu+ROS2+Gazebo 全链（开发机是 Apple Silicon Mac；公司 A4000 服务器可跑但迭代回路长）；ASVSim/HoloOcean 需 UE 工具链。而 Aeolus 参照系本身就是 Unity（HDRP+Compute Shader+VFX Graph+Barracuda），照其论文路线在 Unity 内自研是唯一能逐项对齐参考画面事实（Tessendorf 谱、同心 LOD、YOLOX-ONNX 内推）的路径。
4. **许可全部可用且无污染**：Apache-2.0/MIT/UCL 均允许闭源二开；唯一注意 BoatAttack 资产限 Unity 项目内使用——恰与我们的选型一致。

留缝：阶段2/3 若需第三方感知行为对照，ASVSim（MIT+Apple Silicon 支持）是唯一严肃候选，保留评估入口即可，不影响阶段1 选型。

---

## B. Colav-Simulator 现状与最小桥接协议

### B.1 后端对外接口（均已读源码核实）

- **框架**：FastAPI 应用 `gui_server/main.py:1658`（`app = FastAPI(title="COLAV Simulator Research Control")`）；静态前端挂 `/static`（`main.py:1669-1670`，`GUI_DIR=web_gui` 见 `main.py:73`）。
- **REST**（全部路由 `main.py:1673-2090`）：会话生命周期 `POST /api/sessions`（创建，:1818）、`/start`(/pause|/speed|/step|/reset|/replay)（:1845-1891）、`GET /api/sessions/{id}/result|artifacts`（:1901-1919）；场景/能力/算法目录 `/api/scenarios|capabilities|algorithms|gnc/stacks`（:1679-1703）；busy-water 场景草稿与生成（:1741-1816）；坐标换算 `to-wgs84/to-utm`（:1777-1794）；ENC 信息与瓦片 `/api/enc_info`（:1927）、`/api/enc_tile`（:1956）。另有重放路由 `gui_server/replay.py:1117-1181`（`/runs`、`/runs/{id}/replay*`）与历史 AIS 路由 `gui_server/historical_api.py:1288-1367`。
- **WebSocket**：`/ws/sessions/{session_id}`（`main.py:2141`）支持 `?transport=compact-v1|static-once-v1|shared-planner-v1`（:2143-2149）；旧版 `/ws`（:2153）。服务端每轮循环推送最新遥测文档、以 0.1 s 窗口轮询客户端消息（`_stream`，:2093-2125）。
- **时钟与步长**：后台 asyncio 循环 `_simulation_loop`（`main.py:1578-1626`，lifespan 启动 :1648）驱动 `manager.tick`→`session.advance()`（:976-989；`experiment/session.py:204-207`），wall-clock 节拍 `interval = dt / multiplier`（:1612），追帧上限 3 s（:1564-1575）。`dt` 取 `session.config.dt_sim`（:809），无会话默认 0.1（:800）；倍速钳位 0.1–10（:783）。实际倍率/滞后经 `playback.effective_multiplier|realtime_limited|scheduler_lag_ms` 上报（:824-830）。
- **既有前端即消费方**：web_gui 用 `new WebSocket(...?transport=shared-planner-v1)` 连接（`web_gui/modules/session-runtime-instance.js:63`、`active-session-runtime.js:302`），并已有 Cesium 三维视景面板（`web_gui/index.html:494`、`web_gui/modules/scene-3d.js:9-19`）。

### B.2 实体与状态表达

- **遥测文档**（`_telemetry` 于 `main.py:1147`，返回块 `main.py:1479-1560`）：顶层含 `schema_version:"1.0"`、`run_id`、`seq`、`sim_time`、`state`、`truth[]`（全船）、`plans{waypoints,prediction_horizon,target_routes,...}`、`planner`、`threat_management`、`events`、`playback`、`step_time_ms` 等。
- **船实体**（:1186-1211）：`id/mmsi/length/width/x/y/north/east/psi/u/v/r/sog/cog/trajectory/active/measurements/tracks/colav`。坐标系为北东米制：`x = state[0]-origin_n`（北）、`y = state[1]-origin_e`（东）（:1175,:1192-1195），角度 rad（README.md:14）；本船另附 lat/lon（`mapf.local2latlon`，:1215-1217）。地图原点/尺寸/UTM 带/EPSG:258xx 由 `/api/enc_info` 给出（:1083-1103）。
- **环境**：风/浪/流模型在后端进程内（风浪流扰动 `core/stochasticity.py:294`；FCB45 波几何与 Airy/FK 压力波 `modular_gnc/fcb45_environment.py:140,:191`），但**当前遥测文档不含波高/风向等环境场字段**——阶段1 视觉海洋参数先行独立设定，阶段2 再决定是否由后端参数驱动 Unity 海面。
- **现状边界**：全部接口是"遥测下行 + 会话控制上行"；路由清单（`main.py:1673-2155`、`replay.py:1117-1181`、`historical_api.py:1288-1367`）中不存在"外部注入观测/传感器"端点。

### B.3 最小桥接协议建议（阶段2，后端零改动起步）

- **传输**：Unity C# 侧用 WebSocket 客户端直连既有 `/ws/sessions/{id}?transport=compact-v1`（带宽优先）或 `shared-planner-v1`（与现 web_gui 同构），REST 仅用于创建/启动/倍速。零后端改动即可获得 10 Hz 级状态流。
- **消息契约（草案）**：以 `schema_version==1.0` 文档为准；Unity 每帧消费 `truth[]`（位置/艏向/航迹）、`plans.waypoints|prediction_horizon`（本船意图矢量）、`playback.{requested,effective}_multiplier`（检测后端欠载）。Unity→后端控制面仅 `POST /api/sessions`、`/start`、`/speed` 三个调用。
- **时钟/步长**：不做帧级锁步。仿真推进由后端 `_simulation_loop` 唯一拥有（`main.py:1578-1626`）；Unity 以渲染帧率插值消费，键用 `seq`（单调步号）+ `sim_time`（仿真秒）做对齐与丢帧检测：`seq` 倒退=会话重建，`sim_time` 增速与 `effective_multiplier` 偏离=后端 realtime_limited，应放慢动画而非追赶。调试/逐帧审查可用 `POST /api/sessions/{id}/step`（:1871）手动步进。
- **坐标**：Unity 场景原点取 `enc_info.origin`，东为 x、北为 z（Unity 左手系 y 向上），psi（rad，北偏东顺时针为正）→ 绕 y 旋转 **`+psi`**；千米级场景建议 Unity 端做浮点原点偏移防抖。〔勘误 2026-09-22：原稿 `-psi` 有误——后端艏向向量=(北 cosψ，东 sinψ)（`web_gui/modules/scene-geography.js:25-31`、`scene-3d.js:213-214` 核实），Unity rotation.y=0 朝 +Z=北、+90° 朝 +X=东，故取 +psi。〕
- **为阶段3 预留**：Unity 作为"传感器源"上行需要新端点（建议 `POST /api/sessions/{id}/observations` 或专用 WS），把 Unity 虚拟相机/雷达回波接入现有 tracker 输入（对应 `measurements`/`do_estimates` 链路，`main.py:1208`、`_local_tracks` `main.py:1545`）。本阶段只需冻结遥测 schema 版本号，勿向 1.0 文档内塞临时字段。

---

## 结论

阶段1 选 Unity 自研 + 现成资产（BoatAttack 水体技术、Aeolus 论文参数为蓝图）；五平台无一在"视觉优先"约束下胜出，ASVSim 留作阶段3 感知对照候选。阶段2 桥接走"Unity 直连既有 WebSocket 遥测流 + 三条 REST 控制调用"，时钟用 seq/sim_time 软对齐、不做锁步，后端零改动起步。
