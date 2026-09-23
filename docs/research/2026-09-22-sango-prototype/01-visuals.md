# 阶段1 视觉与引擎方案调研（SANGO Prototype / 01）

日期：2026-09-22 ｜ 调研员：视觉方案调研员 ｜ 事实/推断均标注。未标注来源的数字为推断。

## 0. 结论速览

**推荐组合（事实依据见下文，工程量为推断）**：Unity 6.3 LTS + HDRP，海面用 **HDRP 内置 Water System**（官方 FFT 谱方法，免费），岛屿用 Perlin 程序化地形，天空/云/雾用 HDRP 原生 Physical Sky + Volumetric Clouds + Volumetric Fog，雨雪用 VFX Graph，浮力**自写逐三角形浮力**（对齐 Aeolus 论文方法、为阶段2 Python GNC/MPC 对接留缝）。观感不达标时再买 **Crest Water 5 HDRP（$120）** 升级。开发在 Mac 本地进行，a4000 上渲染**阶段1无必要**。

---

## 1. 引擎版本、Apple Silicon 与许可

- **版本**：Unity 6.3（6000.3）为当前 LTS（官方发布公告 [1]；下载档案可见 6000.3.x 补丁线 [2]）。事实。
- **Apple Silicon 支持**：Unity 6.1 官方系统要求：macOS Big Sur 11+、CPU "Apple M1 or above"、原生 Apple Silicon 编辑器、Metal-capable GPU；限制为 Apple silicon 上 CPU lightmapping 不可用（GPU only）[3]。事实。HDRP 在 macOS/Metal 上正式支持；但 **HDRP 光线追踪在 macOS 无支持**（Unity 官方答复"no plans to support ray tracing on macOS"）[4]。事实——对阶段1无影响（Aeolus 也未用 RT）。
- **性能口碑**：社区证据有限且偏旧：Unity 官方 known-issues 帖承认 HDRP 比 built-in 慢、Apple silicon 开发体验可能偏慢 [5]（2020 年帖）。**推断**：M Pro/Max 级笔记本跑"海面+体积云+VFX"的演示场景可到流畅，但 4K/超高设置不行；本机实测前不下结论（此项未在本机验证）。
- **许可**：Personal 免费（年营收/融资 < $200K，含默认开屏）；Pro $210/月（约 $2,310/席/年），>$200K 强制 Pro；Enterprise >$25M；**Unity Industry**：非游戏/娱乐业务且公司总财务 >$1M 时必须用 Industry（且不得用 Personal）[6]。事实。**影响**：若公司财务超 $1M 且项目定位非游戏，需 Industry 订阅；若挂在个人/小主体下展示，Personal 合法可用——建议按公司实际情况核实后选档。许可证对代码功能无影响（HDRP 全量可用）。

## 2. 水面方案对比（核心决策）

| 方案 | 许可/价格 | HDRP | 波浪方法 | 状态 | 备注 |
|---|---|---|---|---|---|
| **HDRP 内置 Water System** | Unity 自带，免费 | 原生 | FFT 谱，最多 3 个 band（涌浪/风浪/涟漪）[7][8] | 官方维护 | 自带 CPU 水面高度查询（官方属性页："calculate the height of the water simulation on the CPU"）[8]，可直接喂浮力 |
| **Crest Water 5** | Asset Store $120（原价 $240）[9] | 付费版（GitHub 免费版仅 built-in，MIT）[10][11] | ShapeFFT + ShapeGerstner，LOD 网格 | 活跃（2026-06 仍有提交 [11]） | 泡沫/水下/浮力组件齐全，观感上限最高 |
| BoatAttack water | 自定义（Unity 官方示例，GitHub 识别为非标准许可）[12] | **仅 URP** [12] | FFT/级联 | 2024-10 后低更新 [12] | 移植 HDRP 不现实 |
| gasgiant/FFT-Ocean（及其后继 Ocean-URP） | MIT [13] | built-in/URP，未适配 HDRP | Tessendorf FFT | 作者自述 "prototype. Not recommended for real projects"，2022-07 停更 [13] | 参考实现价值高，不宜直接用 |
| Ocean Community（eliasts/Ocean_Community_Next_Gen） | 非标准 [14] | built-in 时代 | Gerstner | 2020-05 停更 [14] | 已死，排除 |

**选型**：最接近 Aeolus 观感且许可干净的是 HDRP 内置 Water System——Aeolus 用自研 compute shader 谱方法（PM/JONSWAP/TMA+Hasselmann 方向扩散，论文事实，见任务简报），而 HDRP Water System 就是官方谱方法实现（FFT 多 band）[7]，"谱方法海面"这一观感内核一致；差异在白帽泡沫与 SSS 细节，可用其 foam/decals + 后处理逼近。**推断**：4 张参考画面（俯视 COLREG 图、GUI 面板、夜间舷灯反射、桥楼视角）对水面特写要求中等，内置系统足够；若评审后认为泡沫/水下观感不足，花 $120 上 Crest 5 HDRP，其自带浮力组件可省自研工作量。

## 3. 岛屿 / 天空 / 天气

- **天空与昼夜**：HDRP Physical Sky + 太阳角度即时刻滑条，原生支持；**Volumetric Clouds**（Procedural/Layered 两种模式，HDRP Asset + Frame Settings 开关）[15]；Unity 6 官方博客确认物理天空+体积云持续强化 [16]。事实。
- **雨雪雾**：VFX Graph（Aeolus 同款方案，论文事实）+ HDRP Volumetric Fog / Aerial Fog；均原生。事实。
- **岛屿**：无开箱即用的"Perlin 岛屿"，但 Perlin 噪声高度场 + Terrain API/程序化 mesh 是教科书做法（Aeolus 亦为自制 Perlin 岛，论文事实）。**推断**：1–2 人日可做出四画面所需的中远景岛屿。

## 4. 浮力 / 波浪-船体交互

- **NWH Dynamic Water Physics 2**：付费资产，基于船体 mesh 的浮力+水动力；官方集成列表含 **Crest、KWS、Lux Water、R.A.M.**（不直接支持 HDRP 内置 Water Surface）[17]；已知问题：Crest 5.3.x 一度破坏 DWP2 兼容（2025-02 GitHub issue）[18]。事实。
- **自写逐三角形浮力**：Aeolus 论文方法（逐三角形静水力+随 Re 阻力+风阻+流力，论文事实）实现难度低：对 hull mesh 每三角形采样水高（HDRP Water Surface CPU 查询 [8] 或 crest 查询 API）→ 累加力/力矩。**推断**：1–2 人日。
- **建议**：阶段1 自写。理由（推断）：a) 与论文同构，阶段2/3 可复用同一接口对接 Python GNC/MPC；b) 不引入第三方物理资产依赖；c) 船速慢、船型简单，逐三角形法精度足够。若最终选 Crest，可评估其自带 Floating Object/Watercraft Controller 组件替代自写。

## 5. 快速排除项

- **UE5**：官方 Water 插件有 Ocean WaterBody+Buoyancy [19]，Oceanology NextGen（Fab，FFT 谱）观感强 [20]；排除理由（推断）：阶段3 的 RL 与合成数据管线 ML-Agents/Perception 为 Unity 生态独有（ml-agents 仓库活跃 [21]，Perception 为 Aeolus 所用），且 Aeolus=Unity+HDRP，跨引擎复刻对齐成本高、工具链重。
- **Godot 4**：无内置海洋与体积云系统，最好的开源选择 godot4-oceanfft（Tessendorf FFT+浮力，MIT）仍是 WIP [22]；何时反选：若项目变为纯轻量可视化、无 RL/合成数据诉求。

## 6. 自研复刻 vs 现成组合（工程量，人日，推断）

| 路线 | 内容 | 估计 |
|---|---|---|
| 自研复刻论文 | compute shader 海谱+同心 LOD+泡沫+SSR/SSS 打磨+浮力 | 20–40 人日，图形专精，风险高 |
| **现成组合（推荐）** | HDRP Water 调优 2–4 ＋ 岛屿 1–2 ＋ 天空云雾天气 2–3 ＋ 逐三角形浮力 1–2 ＋ 四画面场景/轨迹渲染/IMGUI 面板 3–5 | **10–16 人日** |
| 现成+Crest 备选 | 上表 + $120 + Crest 集成 1–2（浮力可复用其组件） | 12–19 人日 |

推荐理由：HDRP 内置 Water 已把 Aeolus 观感里最难的"谱方法海面"官方化 [7][8]，自研仅剩浮力与场景编排；省下的时间投向四张参考画面的呈现质量与阶段2 接缝（轨迹渲染、时间球、速度矢量箭头均为脚本绘制，与水面方案正交）。

## 7. Mac 开发 + a4000 渲染可行性

- Mac 本地：原生 Apple Silicon 编辑器 + Metal HDRP 官方支持 [3]，**阶段1 完全够用**。事实+推断。
- a4000（规格待盘点）：Unity 有 Linux 编辑器（Ubuntu 22.04/24.04，Vulkan-capable NVIDIA，专有驱动 550+ 支持 Wayland）[3]；A4000 若为 Ampere 工作站卡则 HDRP/Vulkan 可跑（HDRP 在 Linux 依赖 Vulkan，此句为推断，未验证）。代价：远程交互需桌面串流（Sunshine/Moonlight 类，本环境未验证）或无人值守批渲染回传视频；许可按机器/席位管理。**推断**：把渲染搬到 a4000 只在"批量出片/阶段3 合成数据生产"时划算，阶段1 不必。

## 来源

[1] https://discussions.unity.com/t/unity-6-3-lts-is-now-available/1697328
[2] https://unity.com/releases/editor/archive
[3] https://docs.unity3d.com/6000.1/Documentation/Manual/system-requirements.html
[4] https://discussions.unity.com（Unity 官方 RT-for-macOS 答复帖，2021-10，标题 "Path / Ray Tracing for macOS and the new M1 Pro / Max"）
[5] https://discussions.unity.com（"Unity on Apple silicon and Big Sur: Known issues"，2020-07）
[6] https://unity.com/products/pricing
[7] https://unity.com/blog/the-new-water-system-in-unity-2022-lts-and-2023-1
[8] docs.unity3d.com HDRP 手册 Water System 各页（"Capabilities of the water system"、"Settings and properties related to the Water System"；具体子页 URL 本次网络受限未逐一验证，自 https://docs.unity3d.com/Packages/com.unity.render-pipelines.high-definition@17.2/manual/index.html 目录下检索）
[9] https://assetstore.unity.com/packages/tools/particles-effects/crest-water-5-oceans-rivers-lakes-164158
[10] https://docs.crest.waveharmonic.com/About/Introduction.html
[11] https://github.com/wave-harmonic/crest（README line 17："This repository targets the built-in renderer"；仓库活动经 GitHub API 核实：MIT，pushed 2026-06-18）
[12] https://github.com/Unity-Technologies/boat-attack-water（及 BoatAttack 主仓；license=NOASSERTION，pushed 2024-10-17，GitHub API 核实）
[13] https://github.com/gasgiant/FFT-Ocean（MIT；README："This is a prototype. Not recommended for real projects."；pushed 2022-07，GitHub API 核实）
[14] https://github.com/eliasts/Ocean_Community_Next_Gen（pushed 2020-05，GitHub API 核实）
[15] https://docs.unity3d.com/Packages/com.unity.render-pipelines.high-definition@12.0.0/manual/Volumetric-Clouds.html
[16] Unity Blog "Lighting & Environment HDRP Updates in Unity 6"（2025-08，unity.com/blog）
[17] https://nwhcoding.com（DWP2 官方文档集成列表：Crest/KWS/Lux Water/R.A.M.；nwhcoding.com/dwp2/docs/ 本次 404，列表经搜索引文核实）
[18] wave-harmonic GitHub issue "Crest 5.3.x breaks physics interaction with Dynamic Water"（2025-02）
[19] https://dev.epicgames.com/documentation（"Water Body Actors in Unreal Engine" 等 Water 插件文档）
[20] https://www.fab.com（Oceanology NextGen 产品页，FFT Spectral Waves）
[21] https://github.com/Unity-Technologies/ml-agents（GitHub API 核实：pushed 2026-09-17，19.7k stars）
[22] https://github.com/tessarakkt/godot4-oceanfft（MIT，"early work in progress"，GitHub API 核实）
