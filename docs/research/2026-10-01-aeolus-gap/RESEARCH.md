# Aeolus-Ocean 对照调研与 Sango 阶段一补齐范围

> 调研日期：2026-10-01（Asia/Shanghai）  
> 范围：Aeolus-Ocean 公共仓库、v1.11 Release、作者论文、用户提供的 4 张截图，以及当前 `sango/` Unity 工程与本机验收证据。  
> 证据标记：**[一手事实]** 来自 Aeolus 作者仓库/Release/论文或当前源码、日志；**[本地实测]** 来自当前工作树产物；**[判断]** 是针对 MASS 平台的工程结论。  
> 执行约束：A4000 当前不可连接；本轮研究和验收只采用本机证据，不把远端 GPU、论文描述或截图当作运行通过证明。

## 结论先行

Aeolus-Ocean 的公开仓库不是可复用的 Unity 源码工程。当前 `main` 目录只有 `README.md`、`LICENSE`、`citation.cff`；README 明确写明项目“currently ... available in binary form”，源码未来是否公开取决于兴趣。v1.11 Release 提供约 268 MB 的 Windows 压缩包，Release 页面注明 Windows 10、NVIDIA RTX DirectX12、Unity 2022.2.5f1。**[一手事实]** 因此 Sango 从零搭建、只复用公开技术路线是合理选择；不能把 Aeolus 的内部实现、资产许可、训练权重或指标直接当作可复用物。

实现状态必须按基线区分：`cbad8202` 时，截图 1 的 environment/agents、航点、DEV、传感器和天气控制确有占位/分散缺口；本轮当前工作树已新增并接入 M6 的 `VisualSimulationSession`、`SimulationWorkbench`、目标编辑器、真实海峡/程序化实验场双模式、保存/加载、EGO 切换、手动/航点运动、天气控制和 CameraCaptureBridge 传感输入。**[当前实现]** 最新 native acceptance 已 PASS；报告后菜单抑制 overlay/radar pivot 两处显示修正亦通过独立 ui-final 验收，不回写 native report。

当前 Sango 已覆盖 Aeolus 参考画面的主要展示骨架：真实地形海峡、HDRP 海面、昼夜/雾/云/雨、大气切档、船舶浮态、桥楼/艏/俯视/外部机位、航点运动、自主控制按钮、速度/航点箭头、雷达样式覆盖层、船模预览和本地 YOLO 回环。当前 Workbench 还补齐环境/actor 配置、Perlin 实验场、航点/目标编辑、DEV/sensor 参数、雨雪雷/湿镜和保存加载；native FPS 和 fixed-camera target evidence 已在 [`output/aeolus-acceptance-20261001/native/report.json`](/Users/marine/Code/Colav-Simulator/output/aeolus-acceptance-20261001/native/report.json) 通过，报告后菜单/radar 显示修正另行做 UI evidence。

“航行时动态识别目标船”要分成两种定义：

1. **阶段一链路与固定目标场景：本机最终 native acceptance 已完成。** FramePublisher 从 Unity 画面发布 JPEG，本机 CPU YOLOv8n 服务推理后通过 ZeroMQ 回传，`DetectionOverlay` 能显示 `YOLO live` 框、类别和置信度。最终 fixed-camera 实测实际 2560×1440；day/dusk/rain/rough-sea target matched，night 少量 matched，fog targetMatched=0；FPS 43.45–51.42。此前 32.95 FPS/397/397 live、978/978 Rx/Tx 记录属于旧路径链路证据，旧录像主要外部/第三人称机位检测本船，不能替代最终 report。
2. **Aeolus/数字孪生完整意义：仍不能宣称完整闭环。** 当前最终报告是固定场景 image box 与 GT sidecar 的匹配，不是目标 ID、世界坐标、距离/方位、速度航迹或雷达融合结果；检测框没有进入 COLAV tracker/规划器。当前 YOLO 服务只筛选 COCO `boat` 类，未做一般目标跟踪、数据关联、遮挡恢复或 AP/PR 评测。**[判断]** native acceptance 已支持本地场景链路方向，不能外推为通用感知或避碰能力。

阶段一最小补齐应集中在一个可操作的运行控制面板、一个可重复的移动目标遭遇场景、动态目标注册到画面/雷达/真值框的接线，以及天气/夜景下的识别录像验收。真实雷达、声呐、传感器融合、世界坐标跟踪、COLREG 决策、DRL 训练和后端 WebSocket 控制应继续留在阶段二/三边界内。

## Aeolus 公共来源与可见性核查

| 来源 | 核查结果 | 可复用边界 |
|---|---|---|
| [Aeolus-Ocean 公共仓库](https://github.com/aavek/Aeolus-Ocean) | Public；当前仓库树只有 `LICENSE`、`README.md`、`citation.cff`。仓库 README 自称 binary-only，未提供 `Assets/`、`ProjectSettings/`、C# 脚本、训练配置或模型文件。 | 可引用 README 的功能声明、截图/GIF 链接和参数解释；不能从仓库源码复刻实现。 |
| [v1.11 Release](https://github.com/aavek/Aeolus-Ocean/releases/tag/v1.11) | Alpha Release v1.11；Windows 10 64-bit、NVIDIA RTX DirectX12、6 GB VRAM、16 GB RAM、1 GB storage；Unity 2022.2.5f1；资产为 `AeolusOcean_v1.11_alphabuild.zip`。 | 只能把 Release 当作 Windows 二进制参考。无法在本机 macOS 上把它当作当前运行证据。 |
| [BSD-3-Clause LICENSE](https://github.com/aavek/Aeolus-Ocean/blob/main/LICENSE) | 仓库代码/发布物声明 BSD-3-Clause。 | BSD 条款允许再分发代码形式的使用，但仓库没有列出二进制内第三方船模、纹理、训练数据和权重各自许可；不要复制未知资产。 |
| [作者论文 arXiv:2307.06688](https://arxiv.org/abs/2307.06688) / [PDF](https://arxiv.org/pdf/2307.06688) | 作者说明了算法和训练方法：HDRP、波谱、物理、YOLOX-S、Barracuda、Unity Perception、ML-Agents、PPO 及实验指标。论文是作者技术描述，不等于公开可构建源码。 | 用于功能对照和参数溯源；论文中报告的 30 FPS、AP 或 COLREG 结果不能直接转化为 Sango 验收结果。 |

README 还链接了 [YOLOX](https://github.com/Megvii-BaseDetection/YOLOX) 和 [Unity ML-Agents](https://github.com/Unity-Technologies/ml-agents)。它们是公开技术依赖的上游项目；Sango 当前本机识别服务实际使用的是 Ultralytics YOLOv8n，和 Aeolus 论文中的 YOLOX-S + Barracuda 不是同一模型/推理栈。

## Aeolus 功能基线

### 用户附件截图 1：Simulation Setup 面板

截图中的字段与 Aeolus README 的官方说明逐项对应。下面把“能看到”与“作者公开说明的语义”分开记录，避免把 UI 控件误读成完整的仿真能力。

| 分组 | Aeolus 字段 | 作者公开语义 | 对 Sango 的要求 |
|---|---|---|---|
| Environment | Number of Environments | 并行环境数量；论文训练阶段形成最多 4×4 网格。 | **本轮已实现** `VisualSimulationSettings.environmentCount`，程序化实验场支持 1..16；M6 真实海峡强制单环境。仅为本地运动学展示，不是 ML-Agents 训练并行。 |
| Environment | Agents Per Environment | 每环境 agent 数；环境数 × agent 数不超过 32。 | **本轮已实现** 总 actor ≤32、稳定 ID、单环境增删编辑；由 `WaypointFollower` 驱动，没有 observation/action/reward 学习接口。 |
| Environment | Environment Spacing | 相邻环境间米制间距，最多填满 4×4 网格。 | **本轮已实现** 程序化实验场 spacing；真实海峡模式使用地理场景原点，不套网格。 |
| Environment | Environment Enclosures | 用墙隔离环境，主要为了加速训练。 | **本轮已实现** 本地实验场 travel bounds/边界校验；它是可视化场景隔离，不宣称 Aeolus 训练优化。 |
| Environment | Ocean Current Factor | 控制水流导致的偏航/漂移。 | **本轮已实现** current speed/direction 写入本地运动学；仍不是水动力 current model。 |
| Environment | Wave Spectrum | PM、JONSWAP、JONSWAP+TMA；配 Hasselmann directional spreading。 | 当前 `JsPmTier` 是 HDRP Water band/风强近似，文档已声明不是谱型切换；UI 必须写“近似档”，不能宣称真实 PM/JONSWAP/TMA。 |
| Procedural Islands | Generate Island Per Environment | 每环境中心生成一座 Perlin 岛。 | **本轮已实现** Procedural Experiment Field 每环境生成 Perlin 岛；M6 RealStrait 继续使用 GEBCO/GLO-30/Sentinel-2 真实地形。 |
| Procedural Islands | Scale / Height / Falloff / Octaves | 控制 Perlin 岛面形、起伏、边缘深度和噪声层数。 | **本轮已实现** 程序化实验场参数校验和生成；M6 真实地形模式不显示为可重建 Perlin 岛。 |
| Procedural Islands | Smooth A/B / Persistence / Lacunarity / Offset X/Y | 控制岛体形状、噪声层影响、粗糙度与随机偏移。 | **本轮已实现** 程序化实验场运行时生成；参数只影响 visual experiment，不等于真实地理数据。 |
| Waypoints | Waypoint Change Distance | 到达距离阈值触发当前 agent 的新航点。 | **本轮已实现** arrival distance、route pattern、marker、speed、pause/reset。 |
| Waypoints | Show Waypoint Markers | 显示航点标记和导航箭头。 | **本轮已实现** Workbench 开关与运行 HUD/方向箭头接线。 |
| Waypoints | Min/Max Waypoint Spawn | 相对环境中心的随机航点生成范围。 | **本轮已实现** 程序化实验场范围/随机 route 参数；M6 路线仍可用确定性 preset。 |
| Waypoints | Waypoint Type | Random、crossing、head-on 等场景类型。 | **本轮已实现** ForwardEncounter/Random/HeadOn/Crossing 本地运动学 preset；不含 COLREG 裁决。 |
| DEV | DEV ID | 选择哪艘船作为 designated ego vessel。 | **本轮已实现** EGO ID 选择、CameraRig mount、overlay/radar/publisher/consumer 绑定。 |
| DEV | DEV Camera | 是否观察船载相机。 | **本轮已实现** onboard camera 与 Bridge/Bow/Chase/TopDown/Overlook 控件；最终 fixed-camera native acceptance 已通过。 |
| DEV | Computer Vision | 开启视觉目标检测。 | **本轮已实现** sensor mode、publisher/consumer 状态和 `YOLO live` HUD；仍是外部 YOLO 回环，不是 Unity 内推理。 |
| DEV | Sensors | Full Dynamic Awareness 或 Computer Vision + Simulated Radar。 | **本轮已实现** `GroundTruth`/`YoloAndTruthRadar` 模式；Radar 仍是 truth-assisted visualization，不是真实信号处理。 |
| DEV | Detection Rate / Confidence | 检测帧间隔、检测阈值。 | **本轮已实现** detection interval/confidence 写入 publisher metadata 和本地 detector 输入。 |
| DEV | Vision Detection Distance | 视觉锁定/跟踪距离。 | **本轮已实现** observation distance 与可选 truth-assisted target camera lock；不宣称 tracker/测距。 |
| DEV | Radar Distance / Sweep | 雷达量程和扫描转速。 | **本轮已实现** 200..2000 m、2.5..120 RPM UI；仍是真值 blip/视觉扫掠，不是真实雷达。 |
| Action | Autonomous Vessel Control | 从设置进入自主运行。 | **本轮已实现** Workbench Start/Pause + Manual/Waypoint 控制；仍是本地航点演示，不含 COLREG 决策。 |

**截图 1 的判断：** `cbad8202` 时面板确实不是完整等价物；本轮已经补成可执行 Workbench：真实海峡/程序化实验场、环境/actor 预算、航点、DEV、sensor、天气、目标船编辑和保存加载。native acceptance 已 PASS；报告后菜单 overlay/radar pivot 显示修正已通过 ui-final 验收；“kinematic visual session ≠ RL training / real radar”边界保持。

### 用户附件截图 2–4及 README 运行态

Aeolus README 对运行态的公开描述包括：

- autonomous/user control 切换；User Control 用键盘方向键；
- 左上角 GUI 修改天气和光照；
- 绿色箭头表示到航点方向，蓝色箭头表示船速向量；
- 雨/雪在相机镜头生成水滴，雾、太阳眩光、平静海面反射会影响视觉检测；
- README 展示白天、夜间、雨、雪+雾、对遇/交叉/追越等 GIF/截图，并声明 GIF 可能为控制体积而加速。

**截图证据与能力证据要分开：** 用户附件证明 Aeolus 运行态的目标视觉和 UI 形态；README/论文证明作者声称有这些组件；它们不证明 Sango 已实现同一算法、传感器噪声或训练质量。

### 论文补充的内部技术细节

论文比 README 多披露了以下内容：

1. 波浪：用 Tessendorf/Horvath/Gamper 路线，在频域用波谱和方向分布生成高度场，PM/JONSWAP/TMA 作为非方向谱，GPU HLSL compute + RenderTexture，多个非周期波数范围减少 tiling。
2. 视觉：YOLOX-S，输入 640×640，转 ONNX，在 Unity Barracuda 内执行；用 Pascal VOC + COCO 的 `boat` 图像和 Unity Perception 生成的合成图，混合数据集 6226 张，按方位角、俯仰角、距离、B1/B3/B6.5/B9、Dawn/Midday/Evening 做 curriculum；以 IoU 0.5 计算 AP。
3. 传感器：表 1 给出 radar-like range 500 m、sweep 60 rpm、sonar-like range 150 m、50 条 ray-cast；论文结论称融合重点是“plausible tracking data”，而不是还原真实雷达原始回波。
4. 船舶物理：逐三角形计算水面/船体交叠，包含静水浮力、流体阻力/摩擦、空气阻力和局部风流力；推进器在作用点施力，由 PhysX 处理 6-DOF 刚体运动；使用 Unity Job System/Burst 多线程。
5. 训练：Unity ML-Agents PPO，最多 32 agent 并行环境，奖励包含航点、静态/动态碰撞规避、时间项和 COLREG 相关项；这部分是训练系统，不是简单的运行 UI。
6. 结果边界：论文称在 RTX 2080 Ti 上启用/不启用 YOLOX 均保持至少 30 FPS，并报告多类遭遇重复 100 次；论文还明确指出暗、模糊环境中的检测会变得 sporadic，需要回退到现象学 radar 模型。

这些细节说明 Aeolus 的“逼真展示”与“训练/感知实验”是两层产品：只复刻 UI 外观，不会自动得到传感器闭环或 DRL 能力。

## Sango 能力矩阵：`cbad8202` 基线 vs 当前实现

`cbad8202` 是本轮新增 Workbench 前基线；当前工作树已完成代码和 M6 场景接线。native binary acceptance 已在 `output/aeolus-acceptance-20261001/` 通过；报告后两处菜单/radar 显示修正已通过独立 ui-final 验收。

| 能力 | `cbad8202` 基线缺口 | 当前实现与证据 | 当前边界 |
|---|---|---|---|
| 海面/天空/天气 | 仅有旧 WeatherGUI/大气 preset；雨雪雷独立控件缺失。 | `WeatherController` 新增 wave direction/development/alignment、rain/snow/thunder/wet-lens；`CameraWeatherEffects` 接入。`SimulationWorkbench` 提供运行时控件；六工况 native report 已通过 FPS/水高门。 | 谱型仍是 HDRP visual approximation；非物理 PM/JONSWAP/TMA/RAO。 |
| 真实海峡/实验场 | 只有 M6 真实海峡，没有统一实验场配置。 | `VisualSceneMode.RealStrait/Procedural`；M6 接入 `VisualSimulationSession` + `SimulationWorkbench`；程序化 Perlin 场支持 1..16 env，总 actor ≤32。 | 本地 kinematic visual experiment，不是 ML-Agents/PPO 训练。 |
| 船舶运动 | 只有既有 hero/M7-B 路线，缺统一 manual/autonomous、单目标编辑。 | `VisualSimulationSession` 统一 dispatch；`WaypointFollower.StepManual`；target add/edit/remove、route/motion/speed/loop、stable IDs；Workbench 有 authoring UI。 | 3-DOF/local waypoint；没有 COLREG/动力学推进。 |
| 浮态/视觉物理 | 已有视觉浮态但无 workbench session actor 接线。 | Session 为 ego/target 创建 buoyancy、lights、wetness、wake；已有 B0/B3/B6/B9 测试保留。 | 不是 Aeolus 逐三角形 6-DOF 水动力，也未做实船 RAO。 |
| 机位/DEV | CameraRig 固定 hero，缺 DEV ID/target lock 控件。 | `SetEgo` 重新绑定 camera mounts、overlay、radar、tile reference；Workbench 有 onboard camera、camera cycle 和 observation distance/truth-assisted lock。 | truth-assisted lock 是展示辅助，不是视觉 tracker/测距。 |
| 展示控制 | env/agents、waypoint、DEV、sensor、weather 分散/占位。 | `SimulationWorkbench` 三列 Setup、Runtime HUD、Weather、Target editor；button/input/save/load 均有实际 binding。 | native authoring/scaling 已通过；报告后菜单 overlay/radar pivot 显示修正已通过 ui-final 验收，不要求像素级复刻截图。 |
| 帧发布/纯传感输入 | 旧 `ScreenCapture`/CustomPass 路径含 GUI或 Metal 失败。 | `FramePublisher` 使用 `CameraCaptureBridge.AddCaptureAction`，post-process intermediate、Overlay 前、同一主相机、无第二 scene render；三槽 readback/JPEG/metadata；native report 已通过。 | 仍是 JPEG 外部推理 seam；显示修正已通过独立 ui-final 验收。 |
| YOLO 回传 | 旧链路已通过，但旧视频多为外部机位/本船框。 | 当前 workbench 已有真实运动 ego/target、`targetMatchedFrames/bestTargetIou`、六工况 harness；最终 fixed-camera native acceptance 已通过，fog targetMatched=0 保留。 | COCO `boat`，无通用 ID/tracker/world pose/radar fusion/AP。 |
| 视觉/运行验收 | 只有旧 33 FPS/本船链路证据。 | `output/aeolus-acceptance-20261001/native/report.json` 已 PASS；WorkbenchVerification 覆盖 native FPS、UI authoring、32 actor scaling、六工况与视频。 | fog targetMatched=0；不能宣称全工况识别通过。报告后显示修正已通过独立 ui-final 验收。 |

### 当前与 Aeolus Setup/运行态的差距

| `cbad8202` 基线缺口 | 当前状态 | 源码/证据锚点 | 剩余边界 |
|---|---|---|---|
| 环境数、agents/env 是 placeholder | **本轮已实现** 1..16 environments、总 actor ≤32、稳定 ID、RealStrait/Procedural 双模式。 | [`VisualSimulationSettings.cs:43-116`](/Users/marine/Code/Colav-Simulator/sango/Assets/Scripts/Runtime/Vessels/VisualSimulationSettings.cs:43)、[`VisualSimulationSession.cs:46-166`](/Users/marine/Code/Colav-Simulator/sango/Assets/Scripts/Runtime/VisualSimulationSession.cs:46) | 本地 kinematic actors，不是 RL agents。 |
| Perlin 岛设置在 M6 隐藏 | **本轮已实现** Procedural Experiment Field 运行时生成；RealStrait 保持真实地形。 | [`VisualSimulationSession.cs:63-86`](/Users/marine/Code/Colav-Simulator/sango/Assets/Scripts/Runtime/VisualSimulationSession.cs:63)、[`M6StraitSceneBootstrapper.cs:337-349`](/Users/marine/Code/Colav-Simulator/sango/Assets/Scripts/Editor/M6StraitSceneBootstrapper.cs:337) | Perlin 只为视觉实验，不替代真实 DEM/地理数据。 |
| Waypoint/marker/encounter 缺统一入口 | **本轮已实现** route preset、arrival distance、marker、manual/waypoint、pause/reset、目标 route 编辑。 | [`SimulationWorkbench.cs:70-149`](/Users/marine/Code/Colav-Simulator/sango/Assets/Scripts/Runtime/SimulationWorkbench.cs:70)、[`VisualSimulationSession.cs:178-231`](/Users/marine/Code/Colav-Simulator/sango/Assets/Scripts/Runtime/VisualSimulationSession.cs:178) | 仍是 3-DOF/local motion，不含 COLREG。 |
| DEV/CV/detection/range 缺统一控制 | **本轮已实现** EGO 选择、camera mount、sensor mode、detection interval、confidence、observation distance、radar range/RPM。 | [`VisualSimulationSettings.cs:67-83`](/Users/marine/Code/Colav-Simulator/sango/Assets/Scripts/Runtime/Vessels/VisualSimulationSettings.cs:67)、[`VisualSimulationSession.cs:233-275`](/Users/marine/Code/Colav-Simulator/sango/Assets/Scripts/Runtime/VisualSimulationSession.cs:233)、[`SimulationWorkbench.cs:70-145`](/Users/marine/Code/Colav-Simulator/sango/Assets/Scripts/Runtime/SimulationWorkbench.cs:70) | truth-assisted lock/visual radar，不是 tracker/真实 radar。 |
| Radar 仅真值 blip | **保留为明确边界**；Workbench 已统一 range/RPM 展示并标明 local visual session。 | [`RadarOverlay.cs:7-16,76-127`](/Users/marine/Code/Colav-Simulator/sango/Assets/Scripts/Runtime/RadarOverlay.cs:7) | 真实回波、杂波、漏检、雷达融合留阶段二/三。 |
| M7-B moving targets 未注册到 overlay/radar | **本轮已补注册**：bootstrapper 收集所有 `WaypointFollower`，同步 overlay/radar；Workbench session 另建可编辑 target actors。 | [`M6StraitSceneBootstrapper.cs:320-328`](/Users/marine/Code/Colav-Simulator/sango/Assets/Scripts/Editor/M6StraitSceneBootstrapper.cs:320)、[`VisualSimulationSession.cs:86-146`](/Users/marine/Code/Colav-Simulator/sango/Assets/Scripts/Runtime/VisualSimulationSession.cs:86) | native acceptance 已有 fixed-camera target matched；fog=0，不能写全工况通过。 |
| 缺雪/雨/雷/湿镜独立控件 | **本轮已实现** independent rain/snow/thunder/wet-lens 和 CameraWeatherEffects。 | [`WeatherController.cs:39-55,350-365`](/Users/marine/Code/Colav-Simulator/sango/Assets/Scripts/Runtime/WeatherController.cs:39)、[`SimulationWorkbench.cs:193-222`](/Users/marine/Code/Colav-Simulator/sango/Assets/Scripts/Runtime/SimulationWorkbench.cs:193) | 视觉近似，非气象标定。 |
| YOLO 结果只 image box | **保留为阶段边界**；本轮增加 target sidecar/frame IoU 证据，但未增加 tracker/world pose。 | [`WorkbenchVerification.cs:15-33,205-231`](/Users/marine/Code/Colav-Simulator/sango/Assets/Scripts/Runtime/WorkbenchVerification.cs:15) | 不宣称 ID、距离、速度、AP/PR、fusion 或 COLAV 消费。 |
| 保存/加载、单目标 add/edit/remove 缺失 | **本轮已实现** JSON scene document、target authoring、save/load、稳定 ID；native `authoring-buttons.json` 已验证。 | [`SimulationWorkbench.cs:225-315`](/Users/marine/Code/Colav-Simulator/sango/Assets/Scripts/Runtime/SimulationWorkbench.cs:225)、[`VisualSimulationSession.cs:384-458`](/Users/marine/Code/Colav-Simulator/sango/Assets/Scripts/Runtime/VisualSimulationSession.cs:384) | 单环境支持逐目标编辑；报告后菜单显示修正已通过 ui-final 截图核验，不改变功能结论。 |

## 动态目标识别：当前实现与验收边界

### 当前已实施本地链

```text
M7-B Ferry/Tug moving route
        │ rendered by M6-Strait camera
        ▼
FramePublisher (ZMQ 5556, JPEG, up to 10 Hz)
        │
        ▼
local CPU YOLOv8n (COCO boat, external process)
        │ DetectionResult: frame_seq/time/source/box/class/confidence
        ▼
DetectionResultConsumer (strict schema + seq + 0.5 s freshness)
        │
        ▼
DetectionOverlay: YOLO live box on moving camera frame
```

最终 native acceptance 已完成：真实运动 ego/target 在 day、dusk、night、fog、rain、rough-sea 六个窗口产生 fresh live 结果，报告给出非空结果、target matched 帧和固定场景 best IoU。最终报告为 `output/aeolus-acceptance-20261001/native/report.json`；旧 `output/aeolus-workbench-20261001/native/report.json`（night target matched=13）与旧视频 `output/sango-yolo-video-20261001/` 只作历史证据。最终报告中 fog targetMatched=0，不能写全工况识别通过。`tools/sango_detector_service.py` 明确每个输入帧产生一个检测结果，包括空检测。

### 已实施本地 Visual Simulation Session

当前 Workbench 已把阶段一运行态分成两个可见模式：

| 模式 | 内容 | 可验收上限 |
|---|---|---|
| `M6 Strait / Real Terrain` | 当前 29 tile 真实海峡、hero、M7-B Ferry/Tug、锚泊船、浮标、渔排、船载 Bridge/Bow 机位。 | 一个真实地理场景；可配置动态目标 route、weather、camera、publisher/consumer；不提供环境网格训练语义。 |
| `Procedural Experiment Field` | 复用现有 prefab、Perlin 岛生成和 `WaypointFollower`，在本地生成最多 16 个环境格；每格放 1–2 个 kinematic actors，总数 ≤32。 | 可展示并行场景、环境间距、边界、航点和移动目标；没有 ML-Agents、PPO、reward、训练模型或并行学习吞吐证明。 |

这两个模式解决截图 1 的“环境数量/agents 数量/spacing/enclosure”展示缺口，同时保持证据边界：前者是地理数字孪生展示，后者是本地运动学可视化实验场；二者都不能称为 Aeolus 等价的 RL 训练系统。

### 还不能宣称的内容

- `boat` 框不等于“识别出 M7-B Ferry/Tug 的身份”；当前 COCO 类别只有通用船类。
- 框不等于距离/方位/速度；透视框没有深度解算和世界坐标映射。
- 连续框不等于 tracker；没有目标 ID、关联、轨迹、遮挡恢复和丢失重捕获。
- 回传不等于 radar/vision fusion；RadarOverlay 当前每帧直接读 Transform 真值。
- `liveFrames` 不等于准确率；空检测是合法结果。最新 workbench 额外有固定场景 `targetMatchedFrames/bestTargetIou`，但仍没有可外推的 GT AP/PR。
- 画面在夜、雾、雨下可渲染，不等于模型在这些域上有经验证的召回率。Aeolus 论文自己也指出暗/模糊条件下检测会 sporadic，并依靠 radar-like fallback。

## 收口范围：已实施内容与剩余边界

以下记录本轮 implement 已覆盖范围与剩余验收边界。它不把 Aeolus 的训练架构或阶段三传感器提前塞入阶段一。

### P0：Visual Simulation Session、动态目标场景和目标注册（已实施，native acceptance PASS）

1. 已增加确定性 `Forward encounter` preset：保留 M6 水深门禁，目标船由本地 session 运动。
2. 已将 M7-B moving ship Transform 注册到 `DetectionOverlay`/`RadarOverlay`，Workbench session 另有可编辑 target actors。
3. 已增加 `Procedural Experiment Field`：最多 16 个本地环境、总 actor ≤32；复用 Perlin/prefab/WaypointFollower，UI 标注 `kinematic visual experiment / no RL training`。
4. 已接入 target scenario、run/pause/reset、camera、GT/YOLO source、seq/age/box HUD。
5. native acceptance 已完成：固定机位、day/dusk/night/fog/rain/rough-sea、UI authoring、32 actor scaling、视频和无 GUI sensor frame 均已采集；fog targetMatched=0 作为真实失败边界保留。菜单 overlay/radar pivot 的报告后显示修正已通过独立 ui-final 验收。

### P1：统一运行控制面板（已实施）

当前 `SimulationWorkbench` 已扩展现有运行态：

- `Scenario`：M6 real terrain / Procedural Experiment Field、数据来源、环境数、spacing、boundary、actor count 和 route preset；实验场控件标注 `kinematic / no RL training`。
- `Navigation`：航点 marker、arrival radius、cruise speed、route preset、autonomous/manual control、pause/reset。
- `Camera & perception`：Bridge/Bow/Chase/TopDown/Overlook、EGO、overlay、GT/YOLO、publisher/consumer、detection interval、confidence、freshness。
- `Weather`：Beaufort、wind/wave direction、wave development/alignment、time、cloud、fog、rain/snow/thunder/wet-lens、atmosphere preset。
- `Radar visualization`：range/sweep，明确 `truth blip visualization`。

完成标准已落到设置 DTO、session apply、实际 actor/camera/sensor/weather 绑定；native authoring/scaling 已证明控件改变运行状态，报告后菜单/radar 显示修正另补 UI evidence。

### P2：识别评测和阶段二接口准备

- 采集发布 JPEG 时同步写入真值 sidecar：frame seq/time、目标 ID、屏幕框、类别和可见性。
- 对 YOLO 返回做 IoU 0.5、precision/recall、AP、按 Bft/时刻/雾距分组；只在模型和 sidecar 对齐后发布指标。
- 在后端阶段二定义 `DetectionResult` 到世界坐标/track 的转换、时间同步、丢帧和 tracker 生命周期；当前 `DetectionResult` schema 保持 image-level，不向阶段一偷偷加入规划字段。
- 只有 tracker 输出进入 COLAV/后端 observation 端点后，才可称“感知闭环”；当前后端 WebSocket 遥测和控制环仍未接入。

## 阶段边界：哪些内容应明确留到后续

| 能力 | 原因 |
|---|---|
| ML-Agents PPO/Imitation、并行学习训练 | Aeolus 训练能力，不是本地 kinematic 实验场；需要独立训练 scene、episode/reset、observation/action/reward、模型版本和训练吞吐证据。Sango 可先展示最多 16 环境/32 actor 的运动学场景，但不能把它叫 RL 并行训练。 |
| 逐三角形 6-DOF 水动力、推进器/阻力/风流物理 | 当前 Sango 的浮态 + 3-DOF 路线满足展示，但没有 Aeolus 论文级 hydrodynamics 或实船参数。不能仅凭视觉录像宣称物理等价。 |
| 真实/统计雷达、声呐、地杂波、漏检和多传感器融合 | `RadarOverlay` 是真值可视化；需要观测模型、噪声/杂波、坐标和时间契约。 |
| 目标跟踪、世界坐标、距离和速度估计 | YOLO box 只有 image pixels；要新增 tracker/数据关联/相机标定或深度假设，并和 AIS/雷达对齐。 |
| COLREG 避碰裁决、后端 WebSocket/控制、AGX/A4000 部署 | 属阶段二/三；当前本机证据不能替代后端闭环或远端硬件验收。 |
| Aeolus 第三方船模、纹理、训练权重 | 公共仓库没有逐资产许可清单；BSD 仓库许可不能自动覆盖 Release 内所有第三方内容。 |

## 最终验收命令与证据

历史阶段一证据（不用于本轮动态目标最终结论）：

```text
sango/Docs/stage1-local-acceptance-20261001.md
output/sango-stage1-20261001/acceptance-summary.json
output/sango-stage1-20261001/detector-return/report.json
output/sango-yolo-video-20261001/yolo-live-30s.mp4
output/sango-yolo-video-20261001/yolo-live-full.mp4
```

本轮 Workbench 实施后的最终验收目录：`output/aeolus-acceptance-20261001/`。native acceptance 与后续显示修正的 UI-only 验收均已完成：

1. 场景构建门：M6 bake 成功后再 build player；场景可枚举 hero、M7-B Ferry/Tug、anchorage；Procedural 场景 `scaling-32.json` 已验证 32 actors scaling。
2. 运行门：`authoring-buttons.json` 已验证 Add/Edit/Remove/Save/Load；EGO、Manual/Autonomous、camera/weather/sensor controls 已接入 session。
3. 目标门：`truthAssistedCameraLock=false` fixed-camera；桥楼/艏视角 moving target 已有 target matched；fog 目标未匹配，不能写全工况目标识别通过。旧外部机位/本船影片不计入目标通过。
4. 天气门：day/dusk/night/fog/rain/rough-sea 六窗口已采集；渲染、live freshness、target matched、best IoU 分开记录。
5. 传感门：`sensor-frames.jsonl`/JPEG 不含 GUI，行序正确；发布链未引入第二次场景 render。
6. 性能门：native 2560×1440 wall-clock FPS 43.45–51.42，均 ≥30；六工况窗口已记录。离线视频不作为实时 FPS 证据。
7. 识别门：固定场景 target matched/best IoU 只作为当前样机场景证据；不发布 AP/PR/泛化结论。
8. UI evidence：菜单抑制 overlay、radar 盘 pivot 修正后，`ui-final/report.json` 与 `ui-final/authoring-buttons.json` 通过；截图确认菜单无检测框、预览船模正立、雷达全盘在屏内。事件通过指原生 Unity public Button/InputField seam；computer-use 工具仍报告锁屏，OS 鼠标点击不计通过。此独立报告不回写六工况性能报告。

## Story 35：纯相机传感输入的渲染时序调研

### 结论

`RenderPipelineManager.endCameraRendering` 可以观察相机渲染结束，但不满足“Overlay GUI 之前抓取”的要求。Unity 官方定义它为“after Unity renders an individual Camera”；本机 HDRP 17.3 源码更明确：

1. `HDRenderPipeline.RenderGraph` 在 `RecordRenderGraph` 末尾执行 `RenderScreenSpaceOverlayUI`，把 ScreenSpaceOverlay UI RendererList 写入 `colorBuffer`：[`HDRenderPipeline.RenderGraph.cs:445-448,2616-2633`](/Users/marine/Code/Colav-Simulator/sango/Library/PackageCache/com.unity.render-pipelines.high-definition@700710090fa9/Runtime/RenderPipeline/HDRenderPipeline.RenderGraph.cs:445)。
2. 同一相机的 `EndCameraRendering` 在主 `ExecuteRenderRequest` 完成、提交 command buffer 之后才触发：[`HDRenderPipeline.cs:2451-2479`](/Users/marine/Code/Colav-Simulator/sango/Library/PackageCache/com.unity.render-pipelines.high-definition@700710090fa9/Runtime/RenderPipeline/HDRenderPipeline.cs:2451)。
3. 因此在 `endCameraRendering` 回调中把 `BuiltinRenderTextureType.CameraTarget` 复制到 RT，时间点上已经晚于 HDRP 的 ScreenSpaceOverlay 合成。`CameraTarget` API 本身确实表示当前相机最终目标，但它没有提供“UI 之前”的历史快照。

结论：**endCameraRendering + CameraTarget 可以避免第二次场景渲染，却不能保证不含 GUI；不能作为 Story 35 的纯传感输入方案。** 这不是 API 猜测，而是本机 HDRP 17.3 的渲染图和 `EndCameraRendering` 调用顺序。

### HDRP AOV：语义正确，但当前版本会额外执行一次相机渲染

HDRP 17.3 官方 AOV 文档确认：AOV 是 HDRP Camera 生成的额外图像，运行时可通过 `HDAdditionalCameraData.SetAOVRequests` 配置；官方 API 注释明确 `AOVBuffers.Color` 是 post-processing 前的 color，`AOVBuffers.Output` 是 post-processing 后的 color。两者都在 ScreenSpaceOverlay UI 之前，语义上可以得到纯场景图像。

但本机 17.3 的实现路径不满足性能约束：

- 主 Render 循环先调用 `ExecuteAOVRenderRequests`，遍历 camera 的 AOV request 并调用 `ExecuteRenderRequest`：[`HDRenderPipeline.cs:2419-2455`](/Users/marine/Code/Colav-Simulator/sango/Library/PackageCache/com.unity.render-pipelines.high-definition@700710090fa9/Runtime/RenderPipeline/HDRenderPipeline.cs:2419)。
- AOV request 的 `ExecuteRenderRequest` 会进入完整 RenderGraph；之后主相机还会再次执行普通 `ExecuteRenderRequest`。这不是从已完成的主相机 buffer 免费读取，而是 AOV render request + main render 两次相机执行。
- AOV 的颜色来源位置在 RenderGraph 中是明确的：`AOVBuffers.Color` 在 post-process 前 push，`AOVBuffers.Output` 在 post-process 后 push；ScreenSpaceOverlay UI 在更后面的 `RenderScreenSpaceOverlayUI`：[`HDRenderPipeline.RenderGraph.cs:344-357,376-421,445-448`](/Users/marine/Code/Colav-Simulator/sango/Library/PackageCache/com.unity.render-pipelines.high-definition@700710090fa9/Runtime/RenderPipeline/HDRenderPipeline.RenderGraph.cs:344)。

结论：**AOV 是 UI 排除语义最干净的官方接口，但在当前 HDRP 17.3 调用路径中会增加一次完整相机渲染，不能作为“不得引入第二次全场景渲染”的 Story 35 最小方案。** 若未来接受第二次渲染或使用独立低分辨率传感相机，AOV 才值得重新评估。

### CustomPass 假设已被本机 Metal 证伪

先前推荐的 `CustomPass.AfterPostProcess + CustomPassUtils.Copy` 已实际试跑，不能继续写成“确定可行”。在本机 Unity 6000.3.24f1 / HDRP 17.3 / Metal 播放器中，`CustomPassContext.cameraColorBuffer.rt` 为空，`CustomPassUtils.Copy` 在 RenderGraph 执行时报 `NullReferenceException`，导致没有 fresh inference return。失败证据：[`output/aeolus-workbench-20261001/capture-failed-first/native/report.json`](/Users/marine/Code/Colav-Simulator/output/aeolus-workbench-20261001/capture-failed-first/native/report.json)、[`player.log`](/Users/marine/Code/Colav-Simulator/output/aeolus-workbench-20261001/capture-failed-first/player.log)。

第二次尝试对 CustomPass 输出做额外行序翻转，得到倒置传感帧，且 target detection 未建立；该档只作失败证据，不能混入最终指标：[`output/aeolus-workbench-20261001/capture-inverted-second/native/report.json`](/Users/marine/Code/Colav-Simulator/output/aeolus-workbench-20261001/capture-inverted-second/native/report.json)。

因此，CustomPass 方案保留为 **API 语义分析/失败假设**，不作为当前实现建议。HDRP 官方文档描述的 `cameraColorBuffer` 可用性不能覆盖本机 Metal RenderGraph 运行时 `rt=null` 这一实际平台边界。

### 最终方案：`CameraCaptureBridge.AddCaptureAction`

当前采用 Unity Core/HDRP 内部使用的 `CameraCaptureBridge` capture-action 接口：

1. `FramePublisher.StartPublishing()` 对真实主相机调用 `CameraCaptureBridge.enabled = true` 和 `AddCaptureAction(camera, action)`；停止时成对 `RemoveCaptureAction`：[`FramePublisher.cs:138-169`](/Users/marine/Code/Colav-Simulator/sango/Assets/Scripts/Runtime/FramePublisher.cs:138)。
2. HDRP `HDUtils.PostProcessIsFinalPass` 明确把 `!hdCamera.hasCaptureActions` 纳入 final-pass 判断；存在 capture action 时，HDRP 保留可供 capture 的 post-process intermediate：[`HDUtils.cs:1025-1031`](/Users/marine/Code/Colav-Simulator/sango/Library/PackageCache/com.unity.render-pipelines.high-definition@700710090fa9/Runtime/RenderPipeline/Utility/HDUtils.cs:1025)。
3. `HDCamera.BeginRender` 获取 capture actions；`ExecuteCaptureActions` 接收 `postProcessDest`，按 `finalViewport` 创建临时 capture RT，先完成正确 viewport 的中间 copy，再调用 action：[`HDCamera.cs:1497-1510,1802-1851`](/Users/marine/Code/Colav-Simulator/sango/Library/PackageCache/com.unity.render-pipelines.high-definition@700710090fa9/Runtime/RenderPipeline/Camera/HDCamera.cs:1497)。这发生在 ScreenSpaceOverlay UI 合成前。
4. Core 包 `CameraCaptureBridge` 的公开 API 是 `AddCaptureAction(Camera, Action<RenderTargetIdentifier, CommandBuffer>)` / `RemoveCaptureAction`；本机源码锚点：[`CameraCaptureBridge.cs:4-92`](/Users/marine/Code/Colav-Simulator/sango/Library/PackageCache/com.unity.render-pipelines.core@0bb36005e9ba/Runtime/Utilities/CameraCaptureBridge.cs:4)。
5. 当前 `CaptureScene` 只在同一 capture action 的 `CommandBuffer` 中做 `Blit(sourceTarget, sensorRT)` + `RequestAsyncReadback(sensorRT)`；没有第二个 Camera、AOV request 或第二次 scene render：[`FramePublisher.cs:214-240`](/Users/marine/Code/Colav-Simulator/sango/Assets/Scripts/Runtime/FramePublisher.cs:214)。
6. Core/HDRP capture intermediate 已输出正确编码行序；最终路径不再额外翻转。旧的“第二次翻转”仅存在于失败档，不能作为最终方向结论。

最终时序：

```text
主相机一次 HDRP scene + post process
        ↓
HDRenderPipeline.ExecuteCaptureActions(postProcessDest)
  CameraCaptureBridge action → sensor RT → CommandBuffer.RequestAsyncReadback
        ↓
final blit / CameraTarget
        ↓
ScreenSpaceOverlay UI (不进入 sensor RT)
```

### 最终本机实测

最终原生报告：[`output/aeolus-acceptance-20261001/native/report.json`](/Users/marine/Code/Colav-Simulator/output/aeolus-acceptance-20261001/native/report.json)，`passed=true`，实际 2560×1440，所有窗口 water query failure=0，所有窗口 `truthAssistedCameraLock=false`，使用真实运动 ego/target（ego 约 48 m、target 约 42 m）。历史 `aeolus-workbench` 报告（含 night target matched=13）只保留作中间失败/迭代证据，不作为最终数字。

| 条件 | FPS | 渲染帧 | fresh live | 非空结果 | target matched | best IoU |
|---|---:|---:|---:|---:|---:|---:|
| day | 51.37 | 617 | 547 | 306 | 306 | 0.703 |
| dusk | 51.42 | 620 | 529 | 392 | 392 | 0.668 |
| night | 43.45 | 524 | 299 | 35 | 35 | 0.401 |
| fog | 51.19 | 615 | 552 | 7 | 0 | 0.158 |
| rain | 50.91 | 613 | 525 | 329 | 329 | 0.703 |
| rough-sea | 50.20 | 604 | 542 | 177 | 177 | 0.704 |

原始证据：

- sensor JPEG + frame metadata：[`output/aeolus-acceptance-20261001/sensor-frames/`](/Users/marine/Code/Colav-Simulator/output/aeolus-acceptance-20261001/sensor-frames) 与 [`sensor-frames.jsonl`](/Users/marine/Code/Colav-Simulator/output/aeolus-acceptance-20261001/sensor-frames.jsonl)。
- 真实 YOLO 回传：[`results.jsonl`](/Users/marine/Code/Colav-Simulator/output/aeolus-acceptance-20261001/results.jsonl)。
- 场景/设置快照：[`native/scene.json`](/Users/marine/Code/Colav-Simulator/output/aeolus-acceptance-20261001/native/scene.json)。
- UI authoring 增改删存取：[`native/authoring-buttons.json`](/Users/marine/Code/Colav-Simulator/output/aeolus-acceptance-20261001/native/authoring-buttons.json)。
- 32 actor scaling：[`native/scaling-32.json`](/Users/marine/Code/Colav-Simulator/output/aeolus-acceptance-20261001/native/scaling-32.json)。
- 六工况视频帧：[`native/video-frames/`](/Users/marine/Code/Colav-Simulator/output/aeolus-acceptance-20261001/native/video-frames)。
- 可复跑本机协调器：[`tools/sango_workbench_capture.py`](/Users/marine/Code/Colav-Simulator/tools/sango_workbench_capture.py)；模型身份与 SHA256：[`model-and-capture.json`](/Users/marine/Code/Colav-Simulator/output/aeolus-acceptance-20261001/model-and-capture.json)，`yolov8n.pt` SHA256=`f59b3d833e2ff32e194b5bb8e08d211dc7c5bdf144b90d2c8412c47ccfc83b36`。

这些数据证明：**真实 YOLO 输入已经是主相机 post-process 画面、没有 Overlay GUI、capture path 没有第二次场景 render，且本机实测高于 30 FPS。** day/dusk/rain/rough-sea 有 target matched；night 有较少 matched；**fog targetMatched=0，不能写“全工况目标识别通过”。** 数据仍只证明当前 `yolov8n / COCO boat` 在这组可重复场景中的输入链路和固定场景 frame-level 匹配；不外推到 AP、泛化能力、其他船型、其他硬件或未来天气域。

### 直接回答 Story 35（修订）

| 候选方案 | 是否二次场景渲染 | 是否可靠排除 ScreenSpaceOverlay | 最终判断 |
|---|---:|---:|---|
| `WaitForEndOfFrame` + `ScreenCapture.CaptureScreenshotIntoRenderTexture` | 否 | 否 | 旧传感路径；会带 GUI。 |
| `RenderPipelineManager.endCameraRendering` + `CameraTarget` copy | 否 | 否，事件晚于 HDRP Overlay 合成 | API 假设已排除。 |
| HDRP AOV `AOVBuffers.Output` | 是，17.3 源码显示 AOV request 后再主相机 render | 是 | 语义正确但违反性能约束。 |
| `CustomPass.AfterPostProcess` + `cameraColorBuffer` | 理论上否 | 理论上是 | 本机 Metal `cameraColorBuffer.rt=null`，已证伪为最终方案。 |
| `CameraCaptureBridge.AddCaptureAction` | 否，单次主相机 render | 是，HDRP 在 UI 前提供 post-process intermediate | 最终采用；native/report.json 通过，51/43 FPS 窗口实测。 |

## 来源与本地锚点

### Aeolus 一手来源

- [Aeolus-Ocean README](https://github.com/aavek/Aeolus-Ocean/blob/406429e18dc0d38c697d112a92fa2168f0b140ad/README.md)：项目定位、binary-only 声明、Simulation Setup 字段、运行态天气/控制/检测影响、局限和许可证。
- [Aeolus-Ocean v1.11 Release](https://github.com/aavek/Aeolus-Ocean/releases/tag/v1.11)：Windows/RTX/Unity 2022.2.5f1 运行要求、Release 资产和版本说明。
- [Aeolus-Ocean LICENSE](https://github.com/aavek/Aeolus-Ocean/blob/406429e18dc0d38c697d112a92fa2168f0b140ad/LICENSE)：BSD-3-Clause 条文。
- [Vekinis & Perantonis, arXiv:2307.06688](https://arxiv.org/abs/2307.06688)：作者论文摘要、Ocean Simulation、Environmental Setup、Object Detection、Vessel Dynamics、Training、Table 1、AP 评测和结论/局限。
- [YOLOX 官方仓库](https://github.com/Megvii-BaseDetection/YOLOX)：Aeolus README 指定的 YOLOX 上游。
- [Unity ML-Agents 官方仓库](https://github.com/Unity-Technologies/ml-agents)：Aeolus README/论文指定的训练工具链上游。

### 当前仓库锚点

- 阶段一原始边界和四张参考画面条款：[`docs/research/2026-09-22-sango-prototype/PHASE1-PLAN.md:18-70`](/Users/marine/Code/Colav-Simulator/docs/research/2026-09-22-sango-prototype/PHASE1-PLAN.md:18)。
- 阶段一原始 M3 检测边界与 `DetectionResult`：[`PHASE1-PLAN.md:196-205`](/Users/marine/Code/Colav-Simulator/docs/research/2026-09-22-sango-prototype/PHASE1-PLAN.md:196)。
- M6 场景 hero/移动场景/UI/overlay 接线：[`M6StraitSceneBootstrapper.cs:207-325`](/Users/marine/Code/Colav-Simulator/sango/Assets/Scripts/Editor/M6StraitSceneBootstrapper.cs:207)。
- M7-B Ferry/Tug 动目标创建与循环航线：[`M7BSceneBuilder.cs:117-175`](/Users/marine/Code/Colav-Simulator/sango/Assets/Scripts/Editor/M7BSceneBuilder.cs:117)。
- `cbad8202` 旧 Simulation 面板与 placeholder：[`SimulationPanel.cs:10-22,240-255`](/Users/marine/Code/Colav-Simulator/sango/Assets/Scripts/Runtime/SimulationPanel.cs:10)；本轮统一 Workbench：[`SimulationWorkbench.cs:70-222`](/Users/marine/Code/Colav-Simulator/sango/Assets/Scripts/Runtime/SimulationWorkbench.cs:70)。
- 当前本地 session 配置、环境/actor 生成、EGO/sensor 绑定、目标编辑与 scene JSON：[`VisualSimulationSettings.cs:43-116`](/Users/marine/Code/Colav-Simulator/sango/Assets/Scripts/Runtime/Vessels/VisualSimulationSettings.cs:43)、[`VisualSimulationSession.cs:46-275`](/Users/marine/Code/Colav-Simulator/sango/Assets/Scripts/Runtime/VisualSimulationSession.cs:46)、[`VisualSimulationSession.cs:384-458`](/Users/marine/Code/Colav-Simulator/sango/Assets/Scripts/Runtime/VisualSimulationSession.cs:384)。
- 当前天气独立开关/波向近似/镜头效果：[`WeatherController.cs:39-55,250-365`](/Users/marine/Code/Colav-Simulator/sango/Assets/Scripts/Runtime/WeatherController.cs:39)、[`CameraWeatherEffects.cs:1-82`](/Users/marine/Code/Colav-Simulator/sango/Assets/Scripts/Runtime/CameraWeatherEffects.cs:1)。
- M6 Workbench/动态目标接线：[`M6StraitSceneBootstrapper.cs:320-349`](/Users/marine/Code/Colav-Simulator/sango/Assets/Scripts/Editor/M6StraitSceneBootstrapper.cs:320)。
- Native Workbench acceptance harness：[`WorkbenchVerification.cs:15-275`](/Users/marine/Code/Colav-Simulator/sango/Assets/Scripts/Runtime/WorkbenchVerification.cs:15)。
- Radar 真值 blip 语义与 out-of-scope 声明：[`RadarOverlay.cs:7-16,100-127`](/Users/marine/Code/Colav-Simulator/sango/Assets/Scripts/Runtime/RadarOverlay.cs:7)。
- YOLO/GT overlay 判定与 fresh live 标签：[`DetectionOverlay.cs:7-16,56-96`](/Users/marine/Code/Colav-Simulator/sango/Assets/Scripts/Runtime/DetectionOverlay.cs:7)。
- 回传消费线程、严格 schema、seq/age 新鲜度：[`DetectionResultConsumer.cs:74-182`](/Users/marine/Code/Colav-Simulator/sango/Assets/Scripts/Runtime/DetectionResultConsumer.cs:74)。
- 外部 YOLO 服务输入验证、COCO boat 筛选、ZMQ 回传：[`tools/sango_detector_service.py:1-20,84-139,161-211`](/Users/marine/Code/Colav-Simulator/tools/sango_detector_service.py:1)。
- 本机阶段一验收与边界：[`stage1-local-acceptance-20261001.md:20-61`](/Users/marine/Code/Colav-Simulator/sango/Docs/stage1-local-acceptance-20261001.md:20)。
- 本机 YOLO 回环报告：[`detector-return/report.json`](/Users/marine/Code/Colav-Simulator/output/sango-stage1-20261001/detector-return/report.json)、[`acceptance-summary.json`](/Users/marine/Code/Colav-Simulator/output/sango-stage1-20261001/acceptance-summary.json)。

### Unity/HDRP 一手 API 来源

- [Unity 6 `RenderPipelineManager.endCameraRendering`](https://docs.unity3d.com/2022.2/Documentation/ScriptReference/Rendering.RenderPipelineManager-endCameraRendering.html)：事件语义是单个 Camera 渲染完成后回调；本机 HDRP 17.3 调用顺序见上方源码锚点。
- [Unity 6 `BuiltinRenderTextureType.CameraTarget`](https://docs.unity3d.com/6000.0/ScriptReference/Rendering.BuiltinRenderTextureType.CameraTarget.html)：当前相机最终 render target；没有 UI 之前快照语义。
- [Unity 6 `CommandBuffer.RequestAsyncReadback`](https://docs.unity3d.com/6000.0/Documentation/ScriptReference/Rendering.CommandBuffer.html)：把异步 GPU readback request 排入 CommandBuffer，保证它位于同一 buffer 中此前 copy 命令之后。
- [Unity 6 `AsyncGPUReadback.Request`](https://docs.unity3d.com/6000.0/Documentation/ScriptReference/Rendering.AsyncGPUReadback.Request.html)：异步读取 GPU resource；适合已完成/已正确排队的资源，不应在 CustomPass 记录阶段直接读取尚未执行的 copy 目标。
- [HDRP 17.3 AOV 文档](https://docs.unity3d.com/Packages/com.unity.render-pipelines.high-definition@17.3/manual/AOVs.html)：AOV 是相机额外图像，可通过 scripting API 配置；具体 Color/Output 位置由本机 HDRP RenderGraph 锚点核实。
- [HDRP 17.3 Custom Pass injection points](https://docs.unity3d.com/Packages/com.unity.render-pipelines.high-definition@17.3/manual/Custom-Pass-Injection-Points.html)：`AfterPostProcess` 的 Color buffer 是含 post-process 的最终场景渲染，且可作为 fullscreen custom pass 的 camera color target。
- [HDRP 17.3 `CustomPassContext`](https://docs.unity3d.com/Packages/com.unity.render-pipelines.high-definition@17.3/api/UnityEngine.Rendering.HighDefinition.CustomPassContext.html)：公开 `cameraColorBuffer`（`RTHandle`）和 `cmd`。
- [HDRP 17.3 `CustomPassUtils`](https://docs.unity3d.com/Packages/com.unity.render-pipelines.high-definition@17.3/api/UnityEngine.Rendering.HighDefinition.CustomPassUtils.html)：提供 `Copy(CustomPassContext, RTHandle, RTHandle)`，用于同一渲染内的 GPU buffer copy。
- Unity 6 Core `CameraCaptureBridge` 本机 package source：[`CameraCaptureBridge.cs:4-92`](/Users/marine/Code/Colav-Simulator/sango/Library/PackageCache/com.unity.render-pipelines.core@0bb36005e9ba/Runtime/Utilities/CameraCaptureBridge.cs:4)；HDRP consumer source：[`HDCamera.cs:1802-1851`](/Users/marine/Code/Colav-Simulator/sango/Library/PackageCache/com.unity.render-pipelines.high-definition@700710090fa9/Runtime/RenderPipeline/Camera/HDCamera.cs:1802)。

## 证据限制

- Aeolus 论文和 README 是作者一手说明，但没有可审计的 public source tree；论文中的源码级实现细节和训练结果无法在本仓库复跑。
- 用户附件截图是视觉参考，不是可执行规格；本报告把 README/论文字段作为功能语义，把截图作为布局和展示形态证据。
- Sango 本机 YOLO 结果证明本地链路可运行，不证明模型识别准确率、不同天气域泛化、目标距离或避碰安全性。
- 当前改进建议保持 A4000 不可用假设；未来远端运行需重新采集硬件、吞吐和部署证据，不能从本机 FPS 外推。
- `bestTargetIou` 是当前固定 ego/target 场景的 frame-level 匹配证据，不是 AP、召回率或跨域准确率；不得据此作一般性模型精度承诺。
