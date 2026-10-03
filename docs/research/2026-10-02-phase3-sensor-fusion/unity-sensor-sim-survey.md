# 调研：Unity/HDRP（+后端）传感器仿真技术路线——实现层调研

> 调研日期 2026-10-02。定位：**实现层**（怎么在 Unity/HDRP + Python 后端里做），域层（要什么）见库内 `docs/research/2026-09-30-mass-situational-awareness/`（02 雷达 / 03 LiDAR-SLAM / 05 视觉-IR / 06 仿真孪生），本文交叉引用不重做。
> 背景锚：sango = Unity 6000.3.24f1 + HDRP 17.3.0（Mac Metal，a4000 Linux 延后）；像素流走 URS fork；后端 FastAPI 已有雷达量测生成 + IPDA 跟踪（CCTA2023 血统）；web = vanilla JS + OpenBridge webcomponents 1.0.1 vendored。
> 标注体系：**【官方确认】**=官方文档/标准原文/一手仓库；**【社区】**=开源社区实现/产品页；**【推断】**=本文基于以上做出的工程判断。来源编号见文末 Sources。

## 0. 结论速览

| 传感器 | 权威量测模型放哪 | 视景呈现怎么做 | 关键依据 |
|---|---|---|---|
| X 波段雷达 | 后端 Python（既有量测链 + He2024/Angelliaume 杂波参数化） | spoke 矩阵→Unity 极坐标 RenderTexture + 余辉 shader；或 web 端 canvas 直绘 PPI | MATLAB 官方海事 PPI 例给全套模型参照 [S1]；arcarum 开源 Unity 海事雷达先例 [S2]；CARLA radar 数据结构 [S6] |
| LiDAR | 后端（量测级），视景点云 Unity 本地生成 | HDRP CustomPass 读 `cameraDepthBuffer` → compute → 点云 buffer；VFX Graph/程序化渲染 | HDRP17 API [S9][S10]；官方 Simulation Pro DepthToPointCloudNode（pre.2）[S11]；CARLA/AWSIM 噪声参数化 [S6][S7] |
| 白光相机 | 无需模型（直接渲染） | 既有五机位画面，零改动 | 仓库现状 |
| 红外相机 | 后端不下发温度场；Unity 端材质温度 tag + 灰体近似 | Fullscreen Shader Graph 灰度化 + white-hot ramp，挂 Custom Pass Volume | Unity 无官方 IR【官方确认（缺失）】；社区 UnityInfrared [S14]；DIRSIG5 物理参照 [S17] |
| AIS | 后端 AIS 模拟器（既有） | web OpenBridge POI 组件复用 + 按 SN.1/Circ.243/Rev.1 自绘三角/圆符号 | IMO 符号原文 [S19]；obc 1.0.1 组件面（仓库事实） |

零采购红线下所有推荐路线均为免费/开源组合，无商业中间件依赖。

---

## 1. X 波段雷达仿真

### 1.1 引擎内雷达视频/PPI 的公开做法

- **通用做法（社区）**：旋转 raycast sweep 把命中写入极坐标 RenderTexture，shader 做"扫描亮线 + 余辉衰减 + 距离衰减"后合成 PPI；这是 Unity 社区反复出现的模式（Unity Discussions 多帖采用 raycast + RenderTexture 组合）[S3]。物理量（功率/增益/波长/波束宽）不做，本质是视觉近似。
- **开源先例（社区，海事专用）**：`arcarum/radar-simulation-unity`（MIT，Unity 2022.3）——浮标载海事雷达网仿真，Unity 输出 **PPI 图像**，`Shaders/` 做 GPU 雷达数据处理与可视化，雷达功率/增益/波长/垂直水平波束宽/雨 RCS 可配置；下游用 CenterNet/YOLO 在 PPI 图上做检测（F1 0.938）并回写地图。证明"PPI 图像→学习式检测"整链在 Unity 内可行 [S2]。其 README 自述反射率对所有材质均匀处理（局限留档）。
- **物理级 workbench（社区）**：`SpaceEngineerSS/RadarSim` 把时域场景引擎接雷达方程模型做物理级仿真 [S4]；`radarsimx/radarsimpy`（Python/C++）从点目标/3D 模型仿真基带数据——注意 radarsimx 为商业授权模式，源码获取受限（以官网为准）[S5]。
- **数据结构参照（官方确认）**：CARLA `sensor.other.radar` = raycast 生成检测点列表，每点 `{altitude, azimuth, depth, velocity}` 极坐标 + 朝向传感器的多普勒速度；默认参数 horizontal/vertical_fov 30°、points_per_second 1500、range 100 m；**radar 无内置噪声/衰减属性**（噪声只给了 lidar），超出即需自建 [S6]。
- **模型参照（官方文档，商业但公开）**：MATLAB Radar Toolbox 官方例 "Simulate a Maritime Radar PPI" 给出海事 X 波段 PPI 的完整建模顺序：10 GHz X 波段、1° 方位波束宽、14 m 距离分辨率、50 rpm 天线；海面用 `seaSpectrum` 海谱 + `surfaceReflectivitySea`（NRL 反射率模型，SeaState 5）经 `clutterGenerator` 逐距离-方位单元生成杂波（`RingClutterRegion` 控制杂波环）；扩展目标用 120×18×22 m cuboid、RCS 40 dBsm；PPI 即"距离×方位强度矩阵"径向渲染 [S1]。**免费引擎做不了这层物理，但其模型分解正是后端 Python 侧的照抄蓝图。**

### 1.2 海事雷达图像特征复现

- **海杂波统计**：域档 02 已有完整证据链——分布选型用 Angelliaume 2019（X-band INGARA 实测，3MD/KR 最优）、生成算法用 He 2024（SIRP：speckle 复高斯×texture 逆高斯，时-空相关矩阵，MSE<0.01）。这两篇可直接替换 `sensing.py` 的 i.i.d. 泊松杂波（域档 02 §2.3，含 DOI）。
- **目标展宽**：PAKF-JPDA 椭圆扩展目标链（Fowdur 2023, DOI 10.3390/rs15102503）把高分辨雷达目标参数化为椭圆 extent——既是跟踪器输入也是"目标在 PPI 上呈展宽弧段"的渲染依据（域档 02 已引）。
- **陆地遮挡**：域档 02 §milliAmpere 用地图过滤；实现层对应 raycast/射线遮挡（后端量测射线对陆地 DEM 求交即可）。
- **RACON**：检索未发现任何开源 RACON（雷达应答标）图像级仿真先例；开源雷达生态（mayara-server/radar_pi/OpenBR24）全部工作在"回波数据/目标"层，不生成应答器编码图像。属空白点，如需 RACON 显示建议按其物理定义（收到 X 波段脉冲→延时重发 Morse 编码）在后端量测层合成，未见可抄的现成实现【推断，基于检索空白】。

### 1.3 Python 侧雷达量测仿真

- `radarsimx/radarsimpy`：transceiver + 点目标/3D 模型基带仿真，含 CA-CFAR/OS-CFAR 处理模块 [S5]；商业授权受限。
- `pyAPRiL`：无源雷达 DSP 库，含杂波对消 + CA-CFAR [S12]。
- `uulm-mrm/clutter-ds`：雷达杂波数据集自动标注脚本（杂波检测标签，非生成）[S13]。
- 天气雷达族（Py-ART / wradlib / Towerpy）是气象杂波，不适用于海杂波【官方文档确认适用域不同】[S13 附]。
- 海杂波**生成**没有现成 Python 库——学术实现即 He 2024 SIRP 算法（域档 02），需自实现（复信号层生成，量级可控）。
- 概念参照：MathWorks "Introduction to Radar Scenario Clutter Simulation"（表面杂波逐单元生成流程 + gamma 反射率）[S1b]。

### 1.4 落地建议（推断）

**量测权威在后端**：spoke 矩阵（方位×距离单元强度，含杂波/遮挡/目标展宽）由 FastAPI 生成——与真实 spoke 数据形态一致（域档 02 §2.4 开源接口生态），tracker 直接吃同源检测。视景二选一：(a) spoke 矩阵经 WS 下发，web canvas 直绘 PPI（零 Unity 开销，推荐先做）；(b) Unity 收 spoke 矩阵→极坐标 RenderTexture→shader 极坐标展开 + 余辉（沉浸驾驶舱画面用）。Unity 自 raycast 扫描仅作视觉备选，物理一致性差且与后端 tracker 不同源。

---

## 2. LiDAR 点云

### 2.1 深度→点云的成熟路径

- **HDRP 17 Custom Pass（官方确认）**：`CustomPassContext` 暴露 `cameraDepthBuffer`（RTHandle）、`cameraColorBuffer`、`cmd`、`renderContext`、`hdCamera` 等 [S9]；注入点按文档列出为 BeforeRendering → AfterOpaqueDepthAndNormal → AfterOpaqueColor → AfterOpaqueAndSky → BeforePreRefraction → BeforeTransparent → BeforePostProcess → AfterPostProcess [S10]。深度金字塔在 `AfterOpaqueDepthAndNormal` 后生成、**只含不透明物**；透明物默认不写深度（Lit 上可开 Transparent Depth Pre/Postpass）；全屏 shader 不能直读当前 color buffer（要走 Scene Color 节点/金字塔）[S10b]。
- **官方新积木（官方确认，预览版）**：`com.unity.simulationpro@1.0.0-pre.2` 的 `DepthToPointCloudNode`（`Unity.SimulationPro.Sensors`）："runs a compute shader on a single input texture"，`ProcessDepthBuffer` dispatch 后走 async GPU readback 产出 `PointCloud2Msg`，自带 `Noise`（GaussianNoise）字段——Unity 官方正在做传感器组件化，但仍是 pre.2 预览、面向汽车仿真 [S11]。
- **HDRP 特有坑（社区）**：HDRP 深度是 Texture2DArray，喂 compute shader 需按数组采样处理 [S15]；透明水面（HDRP Water System 是透明面）默认不出现在深度里——LiDAR 打海面需开水的 depth prepass 或接受"水面丢失"【推断】。
- **GPU raycast 路线（官方确认，Autoware 系）**：AWSIM 用 RobotecGPULidar（RGL）Unity 插件：ray pattern → 位姿变换 → 加高斯噪声 → raytrace → 剔除非命中 → 转传感器系 → ROS2 PointCloud2（10 Hz）发布；支持 Velodyne/Hesai/Ouster 预设 [S7]。这是"不依赖渲染深度、独立 GPU 求交"的成熟工业路线。
- **CARLA（官方确认）**：`sensor.lidar.ray_cast`，每点 XYZI；`noise_stddev` 只沿激光射线方向扰动距离（角度保持精确）[S6]。

### 2.2 点云渲染（HDRP）可行性与开销

- `keijiro/Pcx`：点云导入/渲染器（PLY/PCS），2019 起内置 VFX Graph 支持——点云作为 GraphicsBuffer 喂 VFX Graph 采样渲染；`PcxEffects3` 是完整示例 [S16a]。HDRP 下社区有 ComputeBuffer + 几何 shader 的运行先例 [S16c]。
- HDRP 原生路线：CustomPass 内 `cmd.DrawProcedural`/`Graphics.RenderPrimitives` 画点/小四边形 instanced；`alelievr/HDRP-Custom-Passes`（MIT，HDRP 14 基线）含 Outline/Depth Capture/Copy Buffer 等 17 个现成 pass，其中 "Current Depth To Custom Depth" 演示了全屏 SG 采样深度（custom depth node）[S8]。
- 开销量级（推断）：1e5–1e6 点的 VFX Graph GPU 粒子/DrawProcedural 点元在桌面 GPU 常规可行；瓶颈在每帧读回（AsyncGPUReadback 回 CPU 传后端）而非渲染。点云只做视景时可不读回，成本≈一次 fullscreen 采样 + 一次 drawcall。
- 更高性能渲染器 `FastPoints` 见社区提及 [S16b]，未核验细节，线索级。

### 2.3 噪声模型公开参数化

| 来源 | 距离噪声 | 角度噪声 | 丢失/衰减 | 【】 |
|---|---|---|---|---|
| CARLA lidar | `noise_stddev` 沿射线扰动（默认 0） | 无（角度精确） | `dropoff_general_rate` 0.45、`dropoff_intensity_limit` 0.8、`dropoff_zero_intensity` 0.4、`atmosphere_attenuation_rate` 0.004（强度按 a·d 衰减） | 官方 [S6] |
| AirSim | `GenerateNoise`+`NoiseMean`/`NoiseStdDev` 高斯 | 无单独项 | Range 截断；per-point 分段 id | 官方 [S6b] |
| AWSIM/RGL | 距离高斯：std base 0.02 m + rise per meter 可调 | 角度高斯：std 0.057° | 非命中剔除；速度畸变可选 | 官方 [S7] |

雨雾衰减对 905/1550 nm 的物理参数化无 maritime 公开先例，CARLA 的大气衰减率形态（线性于距离）可作为占位模型【推断】。

### 2.4 点云进不进 tracker / web 链路

- **呈现链路**：Unity 深度点云只渲染，不下发——像素流链路带宽贵（见 §5.3），点云应留在 Unity 内合成进画面，或后端用同帧深度读回自建轻量点云供 web three.js 渲染（数据量 ~1e4 点/帧 JSON 可承受）【推断】。
- **跟踪链路**：海事 LiDAR 目标提取公开做法 = 点云 DBSCAN 族聚类→质心/extent→跟踪器：Applied Ocean Research 2024 用改进 DBSCAN 做 ASV 多目标跟踪 [S20a]；UCL 忙碌水域 LiDAR 船检+跟踪（与视觉融合）[S20b]；arXiv 2511.07950 金字塔聚类 [S20c]；IEEE/CAA JAS 发布海事船点云数据集（实测+仿真）[S20d]。与域档 02 milliAmpere "雷达-激光雷达互补（雷达打不到皮划艇/玻璃钢船）"一致。
- **建议（推断）**：阶段 3 不把 LiDAR 点云塞进既有 IPDA（tracker 吃雷达检测已闭环）；LiDAR 先做视景+独立检测通道，若融合则后端复制 AWSIM 模式——同一深度源读回→量测→DBSCAN→质心交 tracker。

---

## 3. 红外/热成像

### 3.1 Unity 官方支持现状

**无官方热成像/IR 渲染特性**——HDRP 17 文档与 Simulation Pro 传感器清单均无 IR 相机【官方确认（缺失）】。官方提供的积木是：Fullscreen Shader Graph（HDRP）+ Custom Pass Volume 内挂 fullscreen material（HDRP 14 起有 Fullscreen Shader Graph，17.3 文档确认支持"custom post-process and custom pass effects"）[S21][S22]。

### 3.2 社区方案

- `tjbaron/UnityInfrared`：GPU shader 模拟 IR 相机——每个场景对象赋温度范围，用 ramp 纹理映射温度→显示值，C# 脚本管理升/降温动画；未标 license【社区】[S14]。
- `miyehn/unity-thermal-camera`：Built-in RP 的 surface replacement（热视觉材质替换）思路【社区】[S14b]。
- IJEMIN gist：基于标准面光照模型的 thermal effect shader；GameDev SE 有 "per-object Temperature→white-hot 灰度" 的标准问答【社区】[S14c][S14d]。

共同模式 = **温度 tag → ramp/灰度映射**，差异只在注入层（材质替换 vs 后处理）。

### 3.3 学术/物理参照

- **DIRSIG5**（RIT，30 年演进的物理辐射成像框架，EO/IR 通用，官方站有热极化 demo）——灰体（Planck×emissivity）+ 大气辐射传输的权威参照；体量过大不适直连 Unity，但其"材质发射率×温度→辐亮度"分解可借为简化模型依据【官方（学术）】[S17][S17b]。
- `LT1st/Awesome-Infrared-Simulation`：红外仿真工具/论文清单（含 DIRSIG 等），检索入口【社区】[S18]。
- 海面/天空简化（推断）：白天冷海面/暖船体（机舱、排气最热），夜间天空冷背景、目标对比更高；海面温度可绑定场景海况参数。域档 05（视觉-IR 感知）已有 IR 成像文献面，本文不重复。

### 3.4 落地建议（推断）

1) 船模/岸/海/天空挂"温度"材质参数（海面用 HDRP Water 无法换 shader→用 fullscreen pass 对"水面蒙版"单独上温度，或接受水面在 IR 里近似环境温度）；2) Fullscreen Shader Graph 按 emissive/温度缓冲灰度化 + white-hot/black-hot ramp + 增益/NUC 噪声纹理，挂 Custom Pass Volume 的 BeforePostProcess 注入点，单独 Camera 输出 IR 流；3) 与白光路共用相机位姿（同位置双 Camera，同 FOV）。

### 3.5 双光同轴（EO+IR）呈现惯例

船载/舰载光电产品（Quickset Gemini ForeSight、FLIR EO/IR Mk-II、CONTROP、L3Harris WESCAM MX）均为"昼光相机+热像仪共轴/同稳定平台"，white-hot 等多调色板为标配【产品页确认双传感器集成层】[S23a-d]；具体 UI（PiP 还是并排）无标准强制，属产品惯例层【社区】。对本项目：同 FOV 两路独立视频流 + web 端 PiP/切换（OpenBridge 面板已有画中画容器惯例），或单路 Unity 内合成。

---

## 4. AIS 显示

### 4.1 标准符号语义（官方确认）

IMO SN.1/Circ.243/Rev.1（Annex 1，符号准则原文可公开阅读 [S19]；上位标准 MSC.191(79) 及其修正案、测试标准 IEC 62288:2021 [S19b]）：

- **AIS 睡眠目标**：锐角等腰三角形，按艏向（无艏向按 COG）定向；报告位置在三角形中心/半高处；睡眠符号小于激活符号。
- **AIS 激活目标**：同形放大 + COG/SOG 虚线速度矢量（短划、间隔≈2 倍线宽，可带时间刻度）+ 实线艏向线（长为三角形 2 倍）+ 转向率旗标 + 可选路径预测器。
- **危险目标**：加粗红色实心三角形 + 速度矢量，**闪烁直至确认**。选中目标 = 四角方框。
- **AIS 丢失目标**：三角形 + 粗实线十字，保持最后航向，闪烁直至确认；不带矢量/艏向/转向指示。
- **历史位置**：等时间隔的圆点（AIS 与雷达跟踪目标通用）。
- **ARPA/雷达跟踪目标**：实心或空心圆；危险 = 红色实心圆闪烁；捕获中 = 圆弧段（自动捕获的加粗红闪）；丢失 = 圆上加粗线闪烁；参考目标 = 大写 R。
- **AIS-SART**：圆内实线十字。

### 4.2 本仓库 OpenBridge 复用面（仓库事实）

`web_gui/vendor/openbridge/`（@oicl/openbridge-webcomponents@1.0.1，本地 bundle，无 CDN）现有组件 [S24]：

- **目标叠加**：`poi-layer` / `poi-vessel` / `poi-button-vessel`（数据行+告警边框+关系槽，1.0.1 槽转发已打补丁）、`poi-card`——AR 目标投影机制已在 Cesium 3D 场景跑通（仓库 AR 集成记录 2026-09-20）。
- **COLAV 关系图标**：head-on / port-side / starboard-side / overtaking 四枚 + `alert-frame` + outlined vessel icon（2026-09-21 COLAV 数据标记已做）。
- **仪表**：compass、speed-gauge、depth-actual、pitch-roll、roll、rudder、thruster、graph-mini；**面板**：top-bar、card/elevated-card、table、event-list、toggle-button-group、brilliance-menu、dropdown、notification-*、clock。
- **雷达相关图标**：`icon-radar-electronic-range-and-bearing-proposal`（ERBL）、`icon-target-select-iec`、`icon-center-off-iec`、`icon-motion-relative-proposal` 等 IEC 图标提案集。

### 4.3 缺口与做法（推断）

OpenBridge 组件库**没有** S-52/243 标准三角/圆目标符号本体（其图标是 IEC 风格图标，非海图符号）；AIS 目标符号需按 SN.1/Circ.243/Rev.1 几何定义自绘 SVG（三角形+矢量线+红闪状态机，工作量小、规则明确）。数据行/告警框/关系图标复用 obc 现成面； sleeping/activated/dangerous/lost 四态映射到 `poi-button-vessel` 的 state 与 alert-frame。

---

## 5. 融合呈现与数据

### 5.1 跟踪/融合结果在孪生视景的叠加惯例

- **航迹历史**：IMO 标准 = "Dots, equally spaced by time"（等时历史点），AIS 与雷达跟踪目标同规【官方确认】[S19]。
- **危险/告警状态**：红色加粗 + 闪烁直至确认（目标级告警语义），选中 = 四角框【官方确认】[S19]。
- **协方差/扩展目标椭圆**：DLR PAKF-JPDA 把椭圆 extent 作为一等公民输出并图示（域档 02/04 已存文献）；机器人界惯例是 rviz 对 PoseWithCovariance 渲染协方差椭圆【社区常识级惯例】。海事标绘里协方差椭圆不是标准符号——用于研发视图而非驾驶舱视图【推断】。
- **存在概率着色**：公开先例都在**占据栅格层**而非单目标层：NTNU 近岸 mapping 对 OGM 在海事域局限的讨论（arXiv 2502.18368）[S25]、marine radar OGM-SLAM [S26]、milliAmpere 系 map-based filtering（域档 02）。存在概率→栅格热图（航路带状区域着色）比对每目标着色更符合先例【推断】。

### 5.2 数据通路（推断）

融合态（航迹、协方差、存在概率、COLAV 关系）走后端 WS JSON 下发，web 端 OpenBridge POI + 2D 海图/3D 视景叠加——与本仓库 compact-v1/Telemetry Projection 架构同构（CONTEXT.md 术语系）。Unity 侧已有 `DetectionOverlay`（live/GT 双路）可平行扩展航迹层。**原则：融合态不进像素流**（结构化数据体积小、可缩放、可测），像素流只承载"看得见的画面"。

### 5.3 传感器面板画中画的开销评估依据

- **官方参数面**：URS `VideoStreamSender` 暴露 Bitrate (kbits/sec)（分辨率越高需越高码率）、Max/MinBitrate、软件编码时的降采样 scale factor [S27][S27b]；码率可经 `RTCRtpSender.SetParameters` 运行时调（Unity WebRTC 手册）[S27c]。
- **经验面（社区）**：1080p@60 实践值 ~10000 kbps；1080p 下 VP9/H.265 优于默认 codec；软编会压分辨率、硬编避免之；分辨率低于 1920 观感发虚 [S27d-g]。
- **结论（推断）**：每加一路传感器 PiP ≈ +1 相机 render target + 1 路硬件编码 + 1 条 WebRTC track。a4000 上 NVENC 有独立编码单元，增量可控；带宽是主约束。建议：副流降到 640×480–960×540、1–2 Mbps、10–15 fps（雷达 PPI/IR 属低动态画面，低帧率可接受）；雷达 PPI 优先走 §1.4 的 web canvas 方案（零视频流开销），IR 才走第二路视频。

---

## 6. 同类系统先例：传感器架构

### 6.1 CARLA（官方确认）[S6c]

传感器 = **actor**：蓝图（`sensor.lidar.ray_cast` 等）+ 属性（范围/FOV/频率）→ `spawn_actor(attach_to=父actor, attachment=Rigid|SpringArm)` → `listen(callback)` 回调推数据；每个数据对象自带 `frame`/`timestamp`/`transform`；数据按传感器类型分相机（每步图像）、检测器（事件）、其他（GNSS/IMU/LiDAR 4D 点云/Radar 2D 极坐标图/语义 LiDAR）。噪声在传感器实现内、以蓝图属性暴露（lidar 有、radar 无）。数据面向客户端 raw bytes/numpy。

### 6.2 AirSim / Cosys-AirSim（官方确认）[S6b]

传感器在 `settings.json` 声明（SensorType/Enabled/位置/姿态/参数），客户端 `getLidarData()` 拿平坦 float 数组 + 位姿 + per-point 分段；服务端 `DrawDebugPoints` 做命中点可视化。声明式配置 + 数据按帧打戳，与 CARLA 同构。

### 6.3 AWSIM（官方确认，Autoware）[S7]

LiDAR = RGL 节点管线（ray pattern → pose → **noise** → raytrace → 剔除非命中 → sensor frame → ROS2 publish），噪声注入是管线中显式一级；发布直接出自原生库（绕过 C# 托管层）。

### 6.4 对本仓库的映射（推断）

三家的共性分层 = **场景内传感器组件（挂载/几何/采集）+ 采集层参数化噪声 + 帧对齐数据契约（frame/timestamp/transform）**。本仓库已同构：`ColavTelemetry.cs`（契约+软对齐键）/`FramePublisher.cs`（NetMQ）/compact-v1。建议保持：**量测级物理模型在 FastAPI（权威、可测、a4000/Mac 双宿主一致），Unity 传感器组件只做视点几何+视觉呈现，两侧输出共享同一仿真时钟戳**。避免把物理模型塞进 Unity shader（不可测、平台分叉）。

### 6.5 海事专用厂商公开颗粒度（官方产品页/手册级）

- Wärtsilä Navi-Trainer（NTPro 5000）：公开材料为 Technical Description / Instructor Manual（架构与功能级：雷达/ARPA/目标管理），无算法级雷达模型 [S28a-b]。
- Kongsberg K-Sim Navigation：产品页与合规证书（IMO 性能标准合规声明），云雷达训练版有发布稿 [S28c-e]。
- 学术论文只能"使用"这些模拟器，公开不到内部模型。**结论：海事商业模拟器的传感器模型无公开颗粒度可抄；自建（学术开源参数化 + 后端模型）与零采购红线天然一致。**

---

## Sources

| # | 来源 | 性质 |
|---|---|---|
| S1 | MathWorks, Simulate a Maritime Radar PPI — https://www.mathworks.com/help/radar/ug/simulate-maritime-radar-ppi.html | 官方文档（商业产品） |
| S1b | MathWorks, Introduction to Radar Scenario Clutter Simulation — https://www.mathworks.com/help/radar/ug/introduction-to-radar-scenario-clutter-simulation.html | 官方文档 |
| S2 | arcarum/radar-simulation-unity (MIT, Unity 2022.3) — https://github.com/arcarum/radar-simulation-unity | 开源仓库 |
| S3 | Unity Discussions, Radar Implementation in Unity — https://www.reddit.com/r/Unity3D/comments/1agdphr/radar_implementation ；More Efficient Depth Rendering — https://discussions.unity.com/t/more-efficient-depth-rendering/856933 | 社区 |
| S4 | SpaceEngineerSS/RadarSim — https://github.com/SpaceEngineerSS/RadarSim | 开源仓库 |
| S5 | radarsimx/radarsimpy — https://github.com/radarsimx/radarsimpy ；处理模块 https://radarsimx.github.io/radarsimpy/api/process.html | 开源（商业授权模式） |
| S6 | CARLA Sensors reference — https://carla.readthedocs.io/en/latest/ref_sensors/ | 官方文档 |
| S6b | AirSim lidar.md — https://github.com/Microsoft/AirSim/blob/master/docs/lidar.md ；sensors.md — https://github.com/microsoft/AirSim/blob/main/docs/sensors.md | 官方文档 |
| S6c | CARLA Sensors and data — https://carla.readthedocs.io/en/latest/core_sensors/ | 官方文档 |
| S7 | AWSIM Labs LiDAR Sensor — https://autowarefoundation.github.io/AWSIM-Labs/main/Components/Sensors/LiDARSensor/LiDARSensor/ | 官方文档（Autoware） |
| S8 | alelievr/HDRP-Custom-Passes (MIT) — https://github.com/alelievr/HDRP-Custom-Passes | 开源仓库 |
| S9 | HDRP 17.3 CustomPassContext API — https://docs.unity3d.com/Packages/com.unity.render-pipelines.high-definition@17.3/api/UnityEngine.Rendering.HighDefinition.CustomPassContext.html | 官方 API 文档 |
| S10 | HDRP 17.3 Custom Pass injection points — https://docs.unity3d.com/Packages/com.unity.render-pipelines.high-definition@17.3/manual/Custom-Pass-Injection-Points.html | 官方文档 |
| S10b | HDRP 17.3 Custom Pass depth/color buffers — https://docs.unity3d.com/Packages/com.unity.render-pipelines.high-definition@17.3/manual/Custom-Pass-buffers-pyramids.html | 官方文档 |
| S11 | Unity Simulation Pro DepthToPointCloudNode (1.0.0-pre.2) — https://docs.unity3d.com/Packages/com.unity.simulationpro@1.0/api/Unity.SimulationPro.Sensors.DepthToPointCloudNode.html | 官方 API 文档（预览版） |
| S14 | tjbaron/UnityInfrared — https://github.com/tjbaron/UnityInfrared | 社区开源 |
| S14b | miyehn/unity-thermal-camera — https://github.com/miyehn/unity-thermal-camera | 社区开源 |
| S14c | IJEMIN thermal effect gist — https://gist.github.com/IJEMIN/945fc610a3494420fbc35504fe986db9 | 社区开源 |
| S14d | GameDev SE, White hot thermal camera — https://gamedev.stackexchange.com/questions/109964/how-to-create-a-white-hot-thermal-camera | 社区 |
| S15 | Unity Discussions, HDRP depth Texture2DArray → compute — https://discussions.unity.com/t/how-to-sample-depth-texture-from-compute-shader/948720 | 社区 |
| S16a | keijiro/Pcx — https://github.com/keijiro/pcx ；PcxEffects3 — https://github.com/keijiro/PcxEffects3 | 社区开源 |
| S16b | FastPoints（社区提及，未核验）— 见 Unity Discussions https://discussions.unity.com/t/best-way-to-render-a-large-pointcloud-in-unity/880233 | 社区/线索 |
| S16c | Unity Discussions, ComputeBuffer + geometry shader in HDRP — https://discussions.unity.com/t/running-a-geometry-shader-with-computebuffer-in-hdrp/924588 | 社区 |
| S17 | DIRSIG 官方站（RIT）— https://dirsig.cis.rit.edu/demos ；overview — https://dirsig.cis.rit.edu/docs/reveal.js/overview.html | 官方（学术） |
| S17b | DIRSIG5 paper（IEEE）— http://ieeexplore.ieee.org/iel7/4609443/8100662/08100541.pdf | 论文 |
| S18 | LT1st/Awesome-Infrared-Simulation — https://github.com/LT1st/Awesome-Infrared-Simulation | 社区清单 |
| S19 | IMO SN.1/Circ.243/Rev.1 Annex 1 符号准则（原文）— http://www.imorules.com/GUID-541997DE-2C41-4A8E-914B-298C112EFFF5.html | 官方（IMO） |
| S19b | IEC 62288:2021 — https://webstore.iec.ch/en/publication/64659 | 官方（标准页） |
| S20a | Applied Ocean Research 2024, ASV 多目标跟踪（改进 DBSCAN）— https://www.sciencedirect.com/science/article/pii/S0141118724004693 | 论文 |
| S20b | UCL, Reliable LiDAR-based ship detection and tracking for ASVs — https://discovery.ucl.ac.uk/id/eprint/10197444/ | 论文 |
| S20c | arXiv 2511.07950, Obstacle Detection and Tracking in Marine Environments — https://arxiv.org/html/2511.07950v1 | 论文 |
| S20d | IEEE/CAA JAS, A LiDAR Point Clouds Dataset of Ships — https://www.ieee-jas.net/article/doi/10.1109/JAS.2024.124275 | 论文/数据集 |
| S21 | HDRP Fullscreen Shader Graph（14.0 创建路径）— https://docs.unity3d.com/Packages/com.unity.render-pipelines.high-definition@14.0/manual/fullscreen-shader.html | 官方文档 |
| S22 | HDRP 17.3 Fullscreen material — https://docs.unity3d.com/Packages/com.unity.render-pipelines.high-definition@17.3/manual/fullscreen.html ；HDRP 16 挂 Fullscreen Custom Pass — https://docs.unity.cn/Packages/com.unity.render-pipelines.high-definition@16.0/manual/custom-pass-create-gameobject.html | 官方文档 |
| S23a | Quickset Gemini ForeSight（昼光+热像同平台）— https://www.quickset.com/eo-ir-surveillance-camera-gemini-foresight | 产品页 |
| S23b | FLIR EO/IR Mk-II（white-hot 等调色板）— https://defense.flir.com/defense-products/eo-ir-mk-ii | 产品页 |
| S23c | CONTROP 海事 EO/IR — https://www.controp.com/domains/maritime | 产品页 |
| S23d | L3Harris WESCAM MX — https://www.l3harris.com/all-capabilities/wescam-mx-series | 产品页 |
| S24 | 仓库 `web_gui/vendor/openbridge/README.md` + `entry-source.mjs`（@oicl/openbridge-webcomponents@1.0.1 组件清单） | 仓库事实 |
| S25 | arXiv 2502.18368, Near-Shore Mapping for Detection and Tracking of Vessels — https://arxiv.org/pdf/2502.18368 | 论文 |
| S26 | Marine Radar-based Coastal SLAM with OGM — https://www.researchgate.net/publication/373885965 | 论文 |
| S27 | Unity Render Streaming 3.1.0-exp.9 Video Streaming Component — https://docs.unity3d.com/Packages/com.unity.renderstreaming@3.1/manual/video-streaming.html | 官方文档 |
| S27b | VideoStreamSender API — https://docs.unity3d.com/Packages/com.unity.renderstreaming@3.1/api/Unity.RenderStreaming.VideoStreamSender.html | 官方 API |
| S27c | Unity WebRTC 手册（SetParameters 调码率）— https://docs.unity.cn/Packages/com.unity.webrtc@2.4/manual/videostreaming.html | 官方文档 |
| S27d-g | 社区实践：1080p@60 ~10000 kbps — https://discussions.unity.com/t/how-to-increase-frame-rate-and-resolution-in-tutorial/930464 ；软编降采样 — https://discussions.unity.com/t/webrtc-renderstreaming-code-improvements/849373/2 ；codec 影响 — https://stackoverflow.com/questions/79146812/setting-resolution-for-webrtc-using-unity-render-streaming-to-stream-video-file ；分辨率观感 — https://discussions.unity.com/t/unity-render-streaming-introduction-faq/757707 | 社区 |
| S28a | Navi-Trainer 5000 v5.35 Instructor Manual — https://cyberonboard.com/wp-content/uploads/NT_5000_5_35_Instructor_Manual_eng.pdf | 产品手册 |
| S28b | Navi-Trainer 5000 Technical Description（Scribd 流传副本）— https://www.scribd.com/document/467020131/NT-5000-5-35-Technical-Description-Eng | 产品手册（非官方渠道副本） |
| S28c | K-Sim Navigation 产品页 — https://www.tnlcom.gr/en/k-sim-simulators/k-sim-navigation.html | 产品页 |
| S28d | Kongsberg K-Sim Navigation CLOUD 证书页 — https://www.kongsberg.com/maritime/contact/certificates/product-certificates/k-sim-navigation-cloud2 | 官方证书 |
| S28e | Maritime Executive, Kongsberg 云雷达训练发布稿 — https://maritime-executive.com/corporate/kongsberg-releases-cloud-based-simulation-for-maritime-radar-training | 行业媒体 |
| S29 | 域层交叉引用（本文不重做）：`docs/research/2026-09-30-mass-situational-awareness/02-radar-detection-tracking.md`（Angelliaume 2019 / He 2024 / Fowdur 2023 / mayara / OpenBR24 证据链）、`03-lidar-slam.md`、`05-visual-ir-perception.md`、`06-simulation-digital-twin.md`（Stonefish/PyGemini） | 仓库档 |
