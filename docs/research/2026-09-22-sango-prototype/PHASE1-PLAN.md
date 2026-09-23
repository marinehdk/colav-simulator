# 阶段1 工程化实施方案：SANGO Prototype（纯展示型数字孪生雏形）

- 日期：2026-09-22 ｜ 撰写：方案撰写员（dynamic-workflow subagent）
- 依据：本目录五路调研 [01](01-visuals.md)/[02](02-perception-yolo.md)/[03](03-hardware.md)/[04](04-prior-art-colav-seam.md)/[05](05-handoff-audit.md)，以及本仓库源码抽查核实（见文内 file:line）。
- 参照系：Aeolus Ocean 论文 + GitHub README 素材（binary-only，BSD-3-Clause，仅作视觉基准与参数对照，见 05 文档）。
- 标注约定：【事实】= 调研文档已核实或本 session 已执行验证；【推断】= 基于事实的工程判断，未实测处如实声明。

---

## 0. 结论速览

**Unity 6.3 LTS + HDRP 内置 Water System（官方 FFT 谱海面）+ 原生物理天空/体积云/VFX 天气 + 自写逐三角形浮力与航点运动学，检测走真值框投影叠加（零推理），Mac M3 本地开发，a4000 阶段1 不依赖。** 总工程量 **10–17 人日**，里程碑 M0–M3。阶段2 接缝以**四颗钉子**预留：`DetectionOverlay`（框来源无关）、`FramePublisher`（ZeroMQ JPEG 出帧）、`ColavTelemetry` 契约类（按 compact-v1 子集声明）+ 真实遥测 fixture 测试、`DetectionResult` 检测框回传契约（schema + 通道选型稿，默认不激活）。阶段2 桥接 = Unity 直连既有 `/ws/sessions/{id}` WebSocket + 3 条 REST，**后端零改动**。

---

## 1. 目标与验收标准

### 1.1 阶段1 目标（一句话）

在海面上把"MASS 数字孪生"**演出来**：对齐 Aeolus Ocean 的四张参考画面观感，同时把感知与后端两条缝钉死，供阶段2 无痛升级。

### 1.2 阶段1 不做什么（硬边界）

1. **不训练 DRL**：不接 ML-Agents，不做 PPO/强化学习（阶段3 事项）。
2. **不做 Colav 实际联调**：不建立任何到后端的运行时连接，只冻结契约与 fixture（见 M3）；桥接实现留阶段2。
3. **不做阶段3 传感器硬件接入**：不接摄像头/雷达/激光雷达/风速仪，不做观测注入端点。
4. **不接真实 YOLO 推理**：检测框用真值投影（零推理），Sentis 与外部推理均不进阶段1 主线（02 文档结论）。
5. **不写 COLREG 裁决逻辑**：俯视图中的遭遇是**预设轨迹脚本**（简单运动学生成），"Autonomous Control"是**航点跟随演示动画**，不含任何避碰决策（责任原则一：不另写 COLREG 裁决，05 文档保留项）。
6. **不做帧级锁步**：阶段1 无后端，阶段2 也不做（04 文档 B.3）。
7. **不做 a4000 GPU 直通 / Win10 KVM / 远程渲染**：旧方案残留基建全部不建（05 文档）。
8. **不做合成数据批量生产**：导出器接口留缝，课程化量产留阶段3（02 文档 §5 降为可选）。
9. **不为阶段3 预设抽象**：不写"通用传感器插件框架""多后端适配层"等未发生需求的代码；缝 = 四颗钉子 + 坐标约定，仅此而已。

### 1.3 四张参考画面逐张验收条款

整体环境：Mac 本机（M3，10 核 GPU），1440p、HDRP 中画质档，Game 视图 **≥30 fps**（目标值【推断】——参照论文 RTX 2080Ti 上 32 agent ≥30fps 的量级下探到 ≤6 船演示场景；M0 实测定档，见风险 R1）。

#### 画面1 俯视 COLREG 遭遇测试

| 类别 | 条款 |
|---|---|
| 画面要素 | 深蓝海面背景；每船一条彩色轨迹线（≥2 色区分本船/目标船，绿/黄起步）；轨迹起点 `Start` 标签与终点 `WP` 标签；**50m 比例尺**十字标；沿轨迹等时间隔的**时间球**标记 |
| 可演示动作 | 面板选择遭遇类型（对遇/交叉追越/追越 ≥3 种）→ 切俯视相机 → Play：轨迹实时延伸、时间球随仿真时间推进、船体带艏向前进；可暂停/倍速 |
| 验收产物 | 60s 录屏（含全部要素）+ 与 Aeolus README 演示 GIF 的同要素对照卡打勾表，存 `evidence/m2-shot1-*` |

#### 画面2 Simulation 设置面板

| 类别 | 条款 |
|---|---|
| 画面要素 | 海面背景上**深色半透明** GUI 面板，含：环境数、每环境 agent 数、Perlin 岛屿参数（数量/尺度）、航点设置（数量/半径）、雷达距离与转速、船模 3D 预览选择（可旋转） |
| 可演示动作 | 修改岛屿数量 → Apply → 场景重建出对应数量岛屿；修改雷达距离 → 画面雷达圈半径即时变化；切换船模 → 预览模型与场景中模型同步更换 |
| 验收产物 | 一次"改参数→重建→画面变化"完整录屏，存 `evidence/m2-shot2-*` |

#### 画面3 夜间船艏视角

| 类别 | 条款 |
|---|---|
| 画面要素 | 暗夜空（Physical Sky 时刻驱动变暗；月盘/星空为可选加分项，非验收要素，见 §3 表 5）；船艏视角；**红绿舷灯 + 白桅灯/艉灯**；水面灯光反射光路【**待验证要素**：HDRP Water 对局部点光的镜面响应无官方确认，M2 首日 0.5 人日专项验证，不达标以假反射兜底（§7 R2）】 |
| 可演示动作 | 时刻滑条从正午拖到深夜：天空渐暗 → 航行灯点亮 → 水面反射出现（真反射或兜底假反射均算达标，对照表标注实际路径） |
| 验收产物 | 昼/夜对比截图 + 滑动过程录屏，存 `evidence/m2-shot3-*` |

#### 画面4 驾驶桥视角

| 类别 | 条款 |
|---|---|
| 画面要素 | 桥楼视角（船艏可见）；天气 GUI：**Beaufort 0–11 滑条、风向、海浪谱切换（JS-PM 档）、波向对齐、时刻滑条、云量、雾距**；`Autonomous Control` 按钮；画面中**蓝色本船速度矢量**箭头 + **绿色航点方向矢量**箭头 |
| 可演示动作 | Beaufort 0→8 海况明显增强；点击 Autonomous Control → 本船自主转向驶向航点，绿箭头指向航点、蓝箭头随速度变化，到达后停船 |
| 验收产物 | "调海况→开自主→抵航点"全过程录屏，存 `evidence/m2-shot4-*` |

**阶段1 总验收 = 四画面条款全部打勾 + demo build 在 Mac 上双击可演示 + 实测 fps 记录在案。**

---

## 2. 总体架构

### 2.1 分层

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  阶段1 Prototype（Unity 6.3 LTS + HDRP，Mac M3 本地开发运行）                     │
│                                                                              │
│  L1 引擎层（场景与物理，皆为脚本驱动的现成 HDRP 能力）                              │
│    HDRP Water System（FFT 谱海面，CPU 水高查询）                                  │
│    Physical Sky + Volumetric Clouds + Volumetric Fog + VFX Graph 雨/雪          │
│    Perlin 程序化岛屿（自写高度场 → 程序化 mesh）                                    │
│    逐三角形视觉浮力（姿态起伏） + 航点跟随运动学（位置真值，单脚本草方）                 │
│                                                                              │
│  L2 展示层（画面与 GUI）                                                         │
│    俯视正交相机 / 桥楼透视相机 / 船艏相机（自写 2 机位切换器）                         │
│    轨迹 LineRenderer + 时间球 + Start/WP 标签 + 比例尺 + 速度/航向矢量箭头            │
│    UGUI 深色半透明面板：Simulation 设置 / 天气 / 场景选择                            │
│    雷达扫掠可视化（距离圈 + 扫掠线 + 真值 blip，参数由面板驱动）                       │
│                                                                              │
│  L3 感知缝（阶段1 只留钉子，不激活推理）                                            │
│    ShipTruthProvider（本引擎船位真值）──► DetectionOverlay（只认"帧+框列表"）        │
│    FramePublisher（ZeroMQ PUB / JPEG 帧，默认关闭）                                │
│    DetectionResult 契约（检测框回传 schema + 通道选型稿，默认不激活）                 │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       │ 阶段2 激活：ColavBridge（新增组件）
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  后端（阶段2：Colav-Simulator，a4000 宿主，后端零改动起步）                          │
│    FastAPI  gui_server/main.py:1658                                            │
│    REST 控制面仅 3 条：POST /api/sessions、/start、/speed（main.py:1673-2090）    │
│    WebSocket /ws/sessions/{id}?transport=compact-v1（main.py:2141）              │
│      └─► 遥测文档 schema_version 1.0：truth[] / plans / playback / seq / sim_time │
│    _simulation_loop 唯一拥有时钟（main.py:1578-1626）                             │
│      └─► Unity 插值消费，seq+sim_time 软对齐，effective_multiplier 检测后端欠载      │
│    （阶段3 需新增 observations 注入端点——当前路由清单中不存在，04 文档已核实）          │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 关键结构决策

1. **船位真值单一来源**：阶段1 由本地脚本运动学（航点跟随）生成；阶段2 由 `ColavBridge` 把后端 `truth[]` 写进同一个 `ShipTruthProvider`。运动驱动方式可切换，下游（轨迹/矢量/检测框/雷达 blip）全部只认真值——这是最小的缝，不是抽象框架。
2. **视觉浮力与运动学解耦**：浮力只产生姿态起伏（贴浪、横摇），不积分位置——落实责任原则三"状态自由度不双积分"（05 文档保留项），并为阶段2 后端真值驱动留位。
3. **检测框来源无关**：`DetectionOverlay` 接口只收 `frame + List<Detection>`；阶段1 框来自 `Camera.WorldToScreenPoint` 投影，阶段2 换 a4000 YOLO 输出，组件零改动（02 文档两钉子方案）。
4. **场景原点即 ENC 原点**：自第一天起按后端约定建坐标系——NE 米制、rad（`README.md:14`，本次核实），Unity 内东=x、北=z、y 向上，艏向映射 `rotation.y = +psi·Rad2Deg`（**勘误**：初稿沿 04 文档 B.3 写 `-psi` 有误——后端艏向向量=(北 cosψ，东 sinψ)，北偏东顺时针为正（`web_gui/modules/scene-geography.js:25-31`、`scene-3d.js:213-214`，本次核实）；Unity rotation.y=0 朝 +Z=北、+90° 朝 +X=东，故取 `+psi`，04 文档已同步勘误）；千米级场景做浮点原点偏移。阶段1 即按此约定，避免阶段2 重做场景。

### 2.3 工程落位【推断，M0 定稿可逆】

Unity 工程放本仓库 `sango/` 子目录（monorepo）。理由：阶段2 桥接契约与后端改动同仓同 PR 评审。代价：严格 `.gitignore`（`Library/`、`Temp/`、`Logs/`、`obj/`、`Builds/`）。替代：独立仓库，切换成本 ≤1 人日。

---

## 3. 技术选型表

| # | 项 | 选择 | 理由（溯源） | 替代项与触发条件 |
|---|---|---|---|---|
| 1 | 引擎版本 | **Unity 6.3 LTS（6000.3.x）** | 当前 LTS【事实，01 文档§1】；Apple Silicon 原生编辑器+Metal HDRP 官方支持【事实】；Sentis 2.6.1 要求 Unity 6000.0，为阶段2 备选线保住生态【事实，02 文档§2】 | Unity 2022.3 LTS（Aeolus 同版）：Sentis 封顶 2.1.3、LTS 支持期更短——仅当发现 6.3 阻塞性 bug 时回选 |
| 2 | 渲染管线 | **HDRP** | HDRP 内置 Water System 仅 HDRP 有；Aeolus 同为 HDRP，对齐参考画面路径最短【事实，01 文档§2】 | URP：无内置谱海面，排除。macOS 无 HDRP 光线追踪【事实】对阶段1 无影响（Aeolus 亦未用 RT） |
| 3 | 水面方案 | **HDRP 内置 Water System** | 官方 FFT 谱方法（涌浪/风浪/涟漪 ≤3 band），与 Aeolus 自研谱方法观感内核一致；自带 CPU 水高查询可直接喂浮力；免费且许可最干净【事实，01 文档§2 表】 | **Crest Water 5 HDRP（$120）**：M1 打磨后评审仍不达标时升级（自带泡沫/水下/浮力组件）；BoatAttack（仅 URP）、gasgiant/FFT-Ocean（自述 prototype 已停更）、Ocean Community（2020 已死）均只作参考实现【事实】 |
| 4 | 地形/岛屿 | **自写 Perlin 噪声高度场 → 程序化 mesh** | Aeolus 同为自制 Perlin 岛【论文事实】；教科书做法，1–2 人日【推断，01 文档§3】 | Unity Terrain：过重、烘焙成本高，不选 |
| 5 | 天空与昼夜 | **Physical Sky + 太阳角度** | 原生；时刻滑条直接映射太阳角度，驱动昼夜变暗【事实，01 文档§3】。**边界**：Physical Sky 为太阳驱动解析天空，太阳落下只变暗，**不产生月盘/星空**；若夜间画面需要月/星，增配月光方向光 + 程序化星点球壳（或 HDRI 星穹），约 0.5–1 人日【推断】——定位为可选加分项，不计入画面3 验收 | 静态 HDRI 天穹：观感降级备选，不预设 |
| 6 | 云/雾/天气 | **Volumetric Clouds + Volumetric/Aerial Fog + VFX Graph 雨/雪** | 全部 HDRP/VFX Graph 原生，Aeolus 同款方案（VFX Graph 天气为论文事实）；云量/雾距滑条原生可调【事实，01 文档§3】 | 无（原生能力已覆盖参考画面） |
| 7 | 浮力物理 | **自写逐三角形浮力**（HDRP Water CPU 水高查询） | 论文同构（逐三角形静水力+阻力+风阻+流力）【论文事实】；仅作视觉姿态，不积分位置（§2.2-2）；1–2 人日【推断，01 文档§4】 | Crest 自带浮力组件（若换 Crest 触发）；NWH DWP2（付费、集成列表不含 HDRP 内置 Water Surface【事实】——排除） |
| 8 | 船舶运动 | **简化 3-DOF 运动学 + LOS 航点跟随**（单脚本） | 阶段1 要的是可信的航行动画，不是动力学；单真值源（§2.2-1）；不双积分【责任原则】 | 若观感需要转弯惯量，加一阶艏向响应（仍在同一脚本内，不加框架） |
| 9 | 船模来源 | **CC0 低模船 ×2–3**（Kenney / Quaternius / Sketchfab CC0 筛选）+ 简单材质 | 阶段1 船模只需剪影可信；CC0 许可零负担。**此项调研未覆盖，为常识级推断，M2 首日定稿** | 付费资产包（不必要）；Aeolus 包内资产（不可用——binary-only 且第三方资产许可未声明【事实，05 文档§3】） |
| 10 | 相机 | **自写双机位切换器**（俯视正交 + 桥楼/船艏透视，lerp 过渡） | 两个固定机位 0.5 人日够用（Simplicity First） | Cinemachine 3（官方免费包）：出现平滑跟船/运镜需求时引入 |
| 11 | GUI 框架 | **UGUI（Canvas）+ TextMeshPro** | 一套体系同时覆盖深色半透明面板与世界空间标签（Start/WP、时间球编号）；资料最多 | UI Toolkit（官方主推）：面板好用但 3D 世界标签仍需 TMP，混用两套不值，不选 |
| 12 | 检测框链路 | **真值框投影**：`WorldToScreenPoint` 画框 + 类别/置信度标签（置信度恒 1.0 标注 ground-truth） | 零推理成本、零帧率风险；框本引擎已知无需"检测"【02 文档 TL;DR】；升级三级：真值框 → Mac Sentis（可选 A 线）→ a4000 外部推理（阶段2 形态）【02 文档§4】 | Sentis 引擎内 YOLOv8n（可选 A 线，Mac Metal）；Perception 已停更不复刻【事实，02 文档§1】 |
| 13 | 简化传感器 | **雷达扫掠可视化**：距离圈 + 匀速扫掠线 + 真值 blip，距离/转速由面板驱动 | 参考画面2 只要求雷达参数可调且画面可感；真值 blip 零成本；真实回波/声呐射线属阶段3 | `Physics.SphereCast` 半真实 blip（0.5 人日可选，不作主线） |
| 14 | 阶段2 缝钉子 | ① `DetectionOverlay`（帧+框列表，来源无关）② `FramePublisher`（ZeroMQ PUB JPEG，默认关）③ `ColavTelemetry` 契约类（按 compact-v1 子集声明必填字段）+ 真实遥测 fixture 反序列化测试 ④ `DetectionResult` 检测框回传契约（schema + 通道选型稿，默认不激活） | 02 文档两钉子 + 04 文档 B.3 契约冻结；后端路由全部为遥测下行+控制上行、无检测/观测中继端点（`main.py:1673-2155` 路由清单核实），检测框回传必须自有契约，否则阶段2 框无路可回；每一行工作都被阶段2 复用【02 文档§4】 | 无替代——这是"留缝"的全部，不再多加抽象 |

> 许可注意【事实，01 文档§1】：非游戏业务且公司财务 >$1M 须用 Unity Industry、不得用 Personal。**M0 前置动作：按公司实际主体核实许可档位**（对代码功能无影响，不阻塞开工）。

---

## 4. 硬件分工

采用 03-hardware.md 实测结论；任务书"硬件复核修正"为空数组，无修订。Mac→a4000/agx ssh 免密已实测（echo 往返 0.19s / 0.29s）【事实，03 文档 A.4】。

| 设备 | 阶段1 角色 | 约束与注意 |
|---|---|---|
| **Mac M3 8GB** | **唯一主力**：写码、Unity 编辑、git、demo 运行 | 8GB 统一内存 + 数据卷仅剩 25Gi【事实，03 文档 A.1】是最硬约束：Editor 占 7–10GB 后剩 ~15Gi；HDRP 海面编辑内存极紧【推断，03 文档 B】→ 低配 HDRP Asset 起步，M0 冒烟实测定档（风险 R1/R4）；Unity Hub 已装、**Editor 未装**【事实】 |
| **a4000**（2×RTX A4000 16GB，125GB RAM） | 阶段1 **不依赖**；预留角色：Linux 构建机、离屏出片、阶段2 后端宿主 + YOLO 推理容器（GPU1 空闲 16GB）【事实，03 文档 A.2】 | 共享机：GPU0 已被他人占 ~5.2GB、根盘 95% 满仅剩 92G【事实】，且已有他人远程图形会话先例（05 文档§1 引 HANDOFF:124）——任何占用（尤其交互式 GUI/串流会话）先与管理员协调窗口；Docker nvidia runtime 已就绪【事实】 |
| **agx**（Jetson AGX Orin 64GB） | 阶段1/2 不用；阶段3 TensorRT 边缘推理候选 | 无 aarch64 Unity Editor【推断】；容器化 GPU 推理缺 nvidia-container-toolkit【事实，03 文档 A.3】，阶段3 前置补装 |

与 01 文档"Mac 本地即可"与 03 文档"HDRP 8GB 极紧"的分歧处理：**Mac 优先，M0 冒烟为闸门**——Mac 以低配 HDRP 跑通 Water System 即锁 Mac 主力路线；跑不通再启用 a4000 Linux Editor + 串流备选（未验证，时间盒 1 天评估，见 R1）。

---

## 5. 里程碑

工程量合计 **10–17 人日**（与 01 文档 10–16 人日估计一致，+缝钉子余量）。每个里程碑验收 = 可执行命令或可点开产物，证据存 `docs/research/2026-09-22-sango-prototype/evidence/`。

### M0 环境就绪与海面冒烟（1–2 人日）

- **内容**：核实 Unity 许可档位（§3 注意项）；Hub 装 Unity 6.3 LTS Editor；建 HDRP 工程 `sango/` + `.gitignore`；内置 Water Surface 场景 + 基础 Physical Sky；**开启 Water Script Interactions（CPU 水高查询的前置开关；官方文档明示其引入 GPU→CPU 回读代价，评审第 1 轮核实——不开它测出的 fps 偏乐观，而浮力查询是 M2 起的常驻成本）并放置 6 艘低模占位船的逐三角形水高查询**后，Mac 上实测 fps 与内存；定 HDRP 画质档。
- **交付物**：入库的 `sango/` 工程骨架；海面场景；性能实测记录。
- **验收**：
  1. `cd sango && git status --short` 显示工程文件已纳管（Library/ 不入库）；
  2. Mac 打开工程进 Play 模式：1440p 中画质、**Script Interactions 开启 + 6 船逐三角形水高查询运行**的条件下，Game 视图 Profiler 实测 **≥30 fps**（仅测裸海面不算数），截图+读数存 `evidence/m0-fps.png`；Editor 内存占用记录在案；
  3. **闸门**：若 fps <30 或内存 swap 明显 → 触发 R1 回退分支（降 HDRP 档/a4000 串流），M0 不得带病过关。
- **未验证声明**：本里程碑前 Unity Editor 从未在本机/服务器实际运行过（03 文档如实声明），fps 数字以 M0 实测为准。

### M1 海况环境与天气 GUI（3–5 人日）

- **内容**：Perlin 程序化岛屿；Volumetric Clouds + 雾 + VFX 雨/雪；天气 GUI（Beaufort/风向/海浪谱档位/波向/时刻/云量/雾距）并映射到 Water Surface band 参数与天空/雾。**诚实点**：HDRP Water 不直接暴露谱型选择（PM/JONSWAP/TMA），JS-PM 切换档位是对 band 幅值/风强的近似映射【推断】，M1 内验证观感。（可选加分项，不计入基线工程量：月光方向光 + 程序化星穹 0.5–1 人日，见 §3 表 5。）
- **交付物**：桥楼视角海况场景 + 天气面板；**Beaufort→Water 参数映射表**（`sango/Docs/beaufort-water-mapping.md`）。
- **验收**：
  1. 映射表有数值锚点可对：蒲福风级→风速 m/s（公认换算：B0≈0.5、B3≈4.5、B6≈12.5、B9≈22.5，取级内中值；滑条线性插值风速）→ Water Surface band 参数（涌浪幅值/风浪风速/涟漪强度）锚点值【锚点为 M1 起调值，推断】；表中每级配**固定机位 + 固定其余参数**的截图对作为证据；
  2. 录屏：Beaufort 滑条 0→9，波高/白帽可感知增强，且面板显示的风速与映射表一致；
  3. 截图：时刻滑条正午 vs 深夜；雾距滑条两档对比；
  4. 四画面之画面3/画面4 的天气部分要素在本里程碑先行核对一次（航行灯与矢量属 M2）。

### M2 船舶、浮力与四画面成型（4–7 人日）

- **内容**：CC0 船模 ×2–3 入场；逐三角形视觉浮力（Water CPU 水高查询）；3-DOF 航点跟随运动学；遭遇场景脚本（对遇/交叉追越/追越）；俯视 COLREG 画面（轨迹+时间球+Start/WP 标签+50m 比例尺）；Simulation 设置面板（含场景重建与船模预览）；夜间航行灯（发光材质；**首日先做 0.5 人日水面灯光反射专项验证**，见 §7 R2）；桥楼视角速度/航点矢量 + Autonomous Control 按钮；雷达扫掠可视化。
- **交付物**：Mac standalone demo build（双击可运行）。
- **验收**：
  1. §1.3 四张画面条款逐条对照打勾表全绿，录屏 ×4 存 `evidence/m2-shot{1..4}-*`；
  2. `open sango/Builds/sango.app` 双击可进四画面演示（可点开产物）；
  3. demo 内实测 fps 再次记录（对照 M0，劣化 >20% 需说明）。

### M3 检测叠加与阶段2 缝钉子（2–3 人日）

- **内容**：`ShipTruthProvider` + `DetectionOverlay`（真值框叠加，画面1/4 中框住所有船）；`FramePublisher`（NetMQ PUB JPEG，默认关闭、端口可配）；`ColavTelemetry` 契约类——**按 compact-v1 子集声明必填字段**（compact 信封仍为 schema 1.0 文档，但每船剥掉 measurements/tracks/colav，并新增 `transport.schema_version="colav.telemetry.compact@1"`（`gui_server/main.py:151,160,164`，本次核实）——若按全量 1.0 声明必填，阶段2 接真流即反序列化失败）；捕获一份真实 compact-v1 遥测样本作 fixture 并写反序列化 EditMode 测试；**第四颗钉子：`DetectionResult` 回传契约**——冻结 schema（`frame_seq`/`frame_time`/`source`/`detections[]{box_xyxy,class_id,class_name,confidence}`）为 `sango/Docs/contracts/detection-result-v1.md` + C# DTO 与序列化回环测试；**通道选型稿**写入同一文档：默认 Unity 侧 ZeroMQ SUB ↔ a4000 YOLO 服务（与 FramePublisher 对称、后端零改动），备选=阶段3 observations 注入端点（当前后端无此端点，04 文档 B.2 核实）；视觉基准卡（论文+README GIF 对照）终核对。
- **交付物**：叠加层开关与 ZMQ 开关；fixture + 测试；`detection-result-v1.md` + DTO + 回环测试；基准卡对照表。
- **验收**（命令均须实际执行通过）：
  1. 截图：画面1/4 中每艘船被检测框+标签覆盖，存 `evidence/m3-overlay.png`；
  2. `python3 tools/sango_zmq_probe.py --count 30`：订阅 FramePublisher 收到 ≥30 帧 JPEG 并校验文件头（脚本随 M3 交付）；
  3. fixture 捕获（一次性，非联调——不建运行时连接）：`.venv/bin/python -c "…websockets 抓取 /ws/sessions/{id}?transport=compact-v1 单条消息…"` 存 `sango/Assets/Tests/Fixtures/telemetry-sample.json`；Unity EditMode 测试 `ColavTelemetryDeserialize` 反序列化成功，断言 `transport.schema_version=="colav.telemetry.compact@1"`、`truth.Length > 0`、且被剥字段（measurements/tracks/colav）可缺省（Test Runner 截图存证）；
  4. EditMode 测试 `DetectionResultRoundTrip`：DetectionResult DTO 序列化→反序列化回环字段无损（Test Runner 截图存证）；
  5. 四画面对照基准卡（Aeolus README GIF/截图）差异清单出表，达标项/差距项如实记录。

---

## 6. 与 ChatGPT 旧方案对比决策表

旧方案 = HANDOFF.md（Win10 KVM + GPU1 直通跑 Aeolus EXE，276 行，05 文档已审计）。

| 旧方案条目 | 处置 | 理由（溯源） |
|---|---|---|
| P0"先体验原版 EXE 建立视觉基准" | **保留，降为可选支线** | 视觉基准有价值，但不值一周基建；零成本替代=论文+README GIF/截图冻结基准卡【05 文档§4】 |
| 阶段 1A/1B 独立 Unity 工程路线 | **保留** | 与本方案主路线一致【05 文档§2】 |
| 三条责任原则（不另写 COLREG 裁决 / 真值留评价通道 / 状态自由度不双积分） | **保留**，落入 §2.2 | 正确的架构边界【05 文档§2】 |
| run-guide、参数表等调研文档 | **保留** | 任何 Windows 机器跑 EXE 时复用【05 文档§2】 |
| 已校验 Aeolus ZIP（268MB，a4000 在盘） | **保留备用** | 找到现成 Windows 机器即开即跑（推荐补做，半天）；不删【05 文档§2,§4】 |
| Win10 KVM + GPU1 直通 = P0 默认必经 | **放弃默认地位**，降为时间盒兜底 | 直通后 GPU1 对宿主永久消失，与主路线（a4000 Linux）直接冲突；未激活 Windows/失败脚本/127.0.0.1-only VNC 代价失衡【05 文档§1】 |
| "先装完 Windows 再做其他"串行依赖 | **放弃**，改并行 | 阶段1 即日 Mac 起步，不等原版体验【05 文档§2,§4】 |
| 现有 aeolus-win10 VM（占 16GiB running） | **建议立即正常关停**（磁盘保留） | 释放共享资源；ZIP 在盘不急【05 文档§2】 |
| Mac Wine / 付费云 Windows | **放弃，不做** | 双层转换成功率极低【推断】；违背免费偏好【05 文档§4】 |
| （隐含）对齐 Aeolus 技术栈 = Unity 2022.2.5f1 | **替换为 Unity 6.3 LTS** | Aeolus 版本已非 LTS 前沿；6.3 LTS + Sentis 2.6.1 生态对阶段2/3 更有利【01/02 文档】 |
| （隐含）复刻 Perception 合成数据课程管线 | **放弃（阶段1）**，自产真值框导出器 | Perception 已停更（终版 2022-11 preview，README 明示 discontinued）【事实，02 文档§1】 |
| （隐含）复刻 Barracuda+YOLOX 引擎内推理为阶段1 必选 | **替换为真值框叠加（零推理）** | 阶段1 目标是画面；推理对演示零信息增益；两钉子保升级路径【02 文档 TL;DR,§4】 |

---

## 7. 风险与对策

| # | 风险 | 概率/影响 | 对策（含回退路径） |
|---|---|---|---|
| R1 | **HDRP 在 Mac Metal（M3 8GB）性能/内存不足**：8GB 统一内存跑海面+体积云可能 swap、fps <30【推断，M0 前未实测】 | 中/高 | ① M0 即冒烟实测（含 Script Interactions + 6 船水高查询，见 M0），不带病过关；② 低配 HDRP Asset（分辨率 1x、体积云半分辨率、Water band 降档、关无关后处理）；③ 仍不行 → 时间盒 1 天评估 a4000 渲染，**前置条件：先与管理员协调窗口**（共享机：GPU0 有他人进程占 ~5.2GB【03 文档 A.2】、已有他人远程图形会话先例【05 文档§1 引 HANDOFF:124】；交互式串流的等待时间不计入时间盒）；**优先评估非交互路径**：Linux Editor `-batchmode` 离屏出片回传（03 文档 B 已列此能力，未验证），其次才是 Sunshine/Moonlight 串流（**未验证**，含网络/驱动/许可三重不确定）；④ 极端回退：降 URP + 第三方水面（观感损失，最后手段） |
| R2 | **海面效果不达 Aeolus 参考预期**（白帽泡沫/近景 SSS 细节差距）【推断，01 文档§2 已声明差异】 | 中/中 | ① 打磨预算 2–4 人日：band 参数对齐 JONSWAP/TMA 量级、foam/decals、后处理；② 机位纪律：桥楼/俯视视角抬高，避开近景水面特写（四画面本身无贴浪特写）；③ 仍不达 → 买 Crest Water 5 HDRP（$120），路线改 12–19 人日，其浮力组件可替换自写浮力（触发即评审，不预先购买）；④ **画面3 局部点光反射**：HDRP Water 对航行灯点光的镜面响应无官方确认——M2 首日 0.5 人日专项验证，不达标用加色拉伸面片/粒子假反射兜底（已计入 M2 工程量） |
| R3 | **YOLO 链路延迟**（阶段2 关注，阶段1 真值框零延迟无此风险） | 低/中 | 全链估算 ≈1 帧 + 5–15ms（JPEG 0.84ms、Mac→a4000 中位 2.1ms、YOLO26n T4+TensorRT 1.7ms、AsyncGPUReadback ~1 帧）【实测+公开值，02 文档§3】，10–20Hz 可稳【推断】；对策：`DetectionOverlay` 异步按帧消费，框带时间戳、渲染端插值，网络抖动不阻塞渲染线程；阶段2 首日做端到端实测校准 |
| R4 | **Mac 磁盘 25Gi 不足**（Editor 7–10GB + 工程 + 资产）【事实】 | 中/中 | 资产克制（低模、小贴图）；`.gitignore` 纪律 + 定期清 `Library/`；M0 首日记录 Editor 实际占用；红线 ~10Gi 时清理 tmp/（本仓库 tmp/ 有大量历史产物可归档） |
| R5 | **a4000 共享机协调**（GPU0 被占、根盘 95%）【事实】 | 低/低（阶段1） | 阶段1 主路线不依赖 a4000（锁 Mac）；需要构建/推理时用 GPU1 并提前与管理员协调；不放未协调的大资产 |
| R6 | **范围蔓延**：把阶段1 做成"半个阶段2"（写 COLREG、接推理、搞锁步） | 中/高 | §1.2 不做清单为硬边界；评审按里程碑验收条款打勾，越界需求一律记入阶段2 backlog |
| R7 | Unity 许可档位（Industry 强制条件）未核实 | 低/低 | M0 前置动作：按公司主体财务核实【事实，01 文档§1】；对代码与进度零阻塞 |

---

## 8. 阶段2预告：Colav 桥接最小契约

全部结论引自 04 文档 §B（源码行号本次已抽查核实：`gui_server/main.py:1658` FastAPI app、`main.py:2141` WebSocket 路由、`README.md:14` NE 米制 rad）：

1. **传输**：Unity C# WebSocket 客户端直连既有 `/ws/sessions/{session_id}?transport=compact-v1`（带宽优先）或 `shared-planner-v1`（与现 web_gui 同构）；**后端零改动**即得 ~10Hz 遥测流。
2. **控制面**：仅 3 条 REST——`POST /api/sessions`（创建）、`/start`、`/speed`（倍速）；调试逐帧审查加 `POST /api/sessions/{id}/step`。
3. **消息契约**：以 `schema_version=="1.0"` 文档为准；消费 `truth[]`（id/mmsi/x/y/psi/sog/cog/trajectory…）、`plans.waypoints|prediction_horizon`（本船意图矢量）、`playback.effective_multiplier`（后端欠载检测）。**注意 compact-v1 是子集传输**：信封仍标 schema 1.0，但每船剥掉 measurements/tracks/colav，并新增 `transport.schema_version="colav.telemetry.compact@1"`（`gui_server/main.py:151,160,164`，本次核实）——`ColavTelemetry` 必填字段按 compact 子集声明，全量字段一律可缺省（M3 钉子③已落实）。**冻结版本号，勿向 1.0 文档塞临时字段。**
4. **时钟**：仿真时钟由后端 `_simulation_loop` 唯一拥有（`main.py:1578-1626`，wall-clock 节拍 `interval=dt/multiplier`，倍速钳位 0.1–10）。Unity 渲染帧率插值消费，`seq`+`sim_time` 软对齐：`seq` 倒退=会话重建；增速偏离 `effective_multiplier`=后端 realtime_limited，应放慢动画而非追赶。**不做帧级锁步。**
5. **坐标**：场景原点取 `/api/enc_info` 的 origin；后端 NE 米制（x=北、y=东）→ Unity 左手系（东=x、北=z、y 上）；psi（rad，北偏东顺时针为正）→ **`rotation.y = +psi·Rad2Deg`**（勘误：04 文档 B.3 原稿 `-psi` 有误，已同步更正——艏向向量=(北 cosψ，东 sinψ)（`web_gui/modules/scene-geography.js:25-31`、`scene-3d.js:213-214`，本次核实）；Unity rotation.y=0 朝 +Z=北、+90° 朝 +X=东）。**阶段2 首日验收动作：以 psi=90°（朝东）会话做艏向视觉回归**——本船模型艏须指向画面东向；千米级场景 Unity 端浮点原点偏移防抖。
6. **阶段3 预留（不在本阶段实现）**：Unity 作为传感器源上行需新端点（建议 `POST /api/sessions/{id}/observations`）接入现有 tracker 输入（`measurements`/`do_estimates` 链路）——当前路由清单中不存在任何注入端点【04 文档 B.2 核实】。
7. **宿主**：后端 + Unity 前端同机 a4000 部署（125GB RAM/20 线程，回路延迟最低），Web GUI 经局域网暴露（03 文档 §C）。
8. **检测框回传通道（阶段2 激活，M3 已冻结契约）**：阶段1 检测框为真值自产；阶段2 换 a4000 YOLO 输出后，框的回传路径 = M3 钉子④的 `DetectionResult` schema（`sango/Docs/contracts/detection-result-v1.md`）+ 默认通道 Unity 侧 ZeroMQ SUB ↔ a4000 YOLO 服务（后端零改动，与 FramePublisher 对称）；若检测框需进入 Colav tracker（而非仅叠加显示），走第 6 条 observations 端点（需后端新增，不在"零改动"范围内，属阶段3 决策）。

---

## 附：调研文档索引

| 文档 | 内容 | 本方案引用点 |
|---|---|---|
| [01-visuals.md](01-visuals.md) | 引擎/水面/天空/浮力选型 | §3 选型表 1–7、§7 R2 |
| [02-perception-yolo.md](02-perception-yolo.md) | 感知链路与 YOLO 升级路径 | §2.2-3、§3 表 12–14、§7 R3 |
| [03-hardware.md](03-hardware.md) | 三机只读盘点 | §4 硬件分工 |
| [04-prior-art-colav-seam.md](04-prior-art-colav-seam.md) | 平台对比 + 集成缝 | §2、§8 |
| [05-handoff-audit.md](05-handoff-audit.md) | 旧交接方案审计 | §6 对比表、§1.2 不做清单 |

---

## 评审修订记录（第 1 轮，2026-09-22）

| # | 评审发现（severity） | 修订位置 | 修订内容 |
|---|---|---|---|
| 1 | 艏向映射符号错误：`-psi` 应为 `+psi`（high） | §0 无涉；§2.2-4；§8.5；04 文档 B.3 同步勘误 | 全部改为 `rotation.y = +psi·Rad2Deg` 并注明勘误依据（艏向向量=(北 cosψ，东 sinψ)，`web_gui/modules/scene-geography.js:25-31`、`scene-3d.js:213-214` 本次亲自核实）；§8.5 增补阶段2 首日 psi=90°（朝东）艏向视觉回归动作 |
| 2 | 画面3「月/星光」无实现路径：Physical Sky 太阳驱动、只变暗（medium） | §1.3 画面3；§3 表 5；§5 M1 | 画面3 验收要素降为「暗夜空」；月盘/星空改可选加分项（月光方向光+程序化星穹 0.5–1 人日，不计入基线工程量）；表 5 删除「昼夜切换零额外成本」表述，写明解析天空边界 |
| 3 | 「水面灯光拉长反射光路」未验证、R2 不兜此要素（medium） | §1.3 画面3；§5 M2；§7 R2④ | 要素标注「待验证」；M2 首日 0.5 人日专项验证 HDRP Water 对点光的镜面响应；不达标以加色拉伸面片/粒子假反射兜底（计入 M2 工程量），R2 增第 ④ 条 |
| 4 | 检测框回传通道无契约：后端无中继端点，框回不来（medium） | §0；§2.1 L3 图；§3 表 14；§5 M3；§8.8 | 增第四颗钉子：`DetectionResult` schema（`frame_seq`/`frame_time`/`source`/`detections[]{box_xyxy,class_id,class_name,confidence}`）冻结为 `sango/Docs/contracts/detection-result-v1.md` + C# DTO 回环测试；通道选型稿=默认 Unity ZMQ SUB ↔ a4000 YOLO（后端零改动），备选=阶段3 observations 端点；默认不激活。M3 验收增 `DetectionResultRoundTrip` 测试 |
| 5 | compact-v1 为子集传输：剥字段 + `transport.schema_version=colav.telemetry.compact@1`，按全量声明必填会接流即败（low） | §3 表 14；§5 M3 内容与验收 3；§8.3 | `ColavTelemetry` 必填字段按 compact 子集声明；EditMode 测试增断言 `transport.schema_version=="colav.telemetry.compact@1"` 且被剥字段（measurements/tracks/colav）可缺省；引用 `gui_server/main.py:151,160,164`（本次亲自核实） |
| 6 | a4000 串流回退漏算共享机协调：已有他人远程图形会话与 GPU 进程（low） | §4 a4000 行；§7 R1③ | R1③ 增前置条件「先与管理员协调窗口（等待不计入时间盒）」；优先评估 `-batchmode` 离屏出片等非交互路径，串流降为其次；a4000 角色注明协调要求 |
| 7 | M0 冒烟未含浮力查询成本：Water CPU 水高查询需开 Script Interactions 且引入 GPU→CPU 回读代价（low） | §5 M0 内容与验收 2 | M0 冒烟明确「开启 Script Interactions + 6 艘低模船逐三角形水高查询」条件下实测 fps；裸海面读数不算数 |
| 8 | M1 「波高/白帽可感知增强」纯主观、无数值锚点（low） | §5 M1 交付物与验收 1–2 | 交付 `sango/Docs/beaufort-water-mapping.md`：蒲福风级→风速 m/s（B0≈0.5/B3≈4.5/B6≈12.5/B9≈22.5 级内中值，公认换算）→ Water band 参数锚点【起调值，推断】；每级配固定机位+固定参数截图对；录屏验收要求面板风速与映射表一致 |

> 工程量影响：第 2/3/4 条新增工作（星穹为可选项不计；反射专项 0.5、DetectionResult 契约 ~0.5 人日）落在 M2/M3 既有区间内，总计仍为 10–17 人日。全部 8 条均已修复；评审人所引三处源码（scene-geography.js:25-31、scene-3d.js:213、main.py:150-160）已由本方案作者本轮亲自读取核实，行号以本次核实为准（main.py 实测 151/160/164）。
