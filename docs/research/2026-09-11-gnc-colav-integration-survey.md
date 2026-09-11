# GNC ↔ COLAV 集成耦合架构调研（可执行代码为主）

日期：2026-09-11。性质：网络一手来源调研（GitHub 仓库、论文、官方文档），服务于"同事 4DOF FCB45 全栈（ILOS + PID/SMC + QP/PGD 三推进器两舵两艏推）嵌入本项目 VO + 双 MPC 避碰栈之下"的集成决策。约 45 m 欠驱动船；双方均无实船海试数据；先集成、后找有证据支撑的优化点。

本地背景（不重复展开，详见既有文档）：

- 上游接口与适配路线：`docs/research/2026-08-28-gnc-hydrodynamics-integration-survey.md`
- 原版 GNC 迁入方案（RoutePlan/AvoidancePlan 契约、调度、降级）：`docs/research/2026-09-10-original-gnc-migration-plan.md`
- 现有外部 MPC 集成：`colav_simulator/integrations/`（potocnik、psbmpc、sbmpc、rrt）

---

## 1. 开源栈盘点

每条含：耦合架构 / 动力学保真度 / 规划器-控制器交接 / 许可 / 维护状态 / 一行信任注记 / 我们能抄什么。

### 1.1 ntnu-itk-autonomous-ship-lab 生态（即本项目上游，全部 MIT）

| 仓库 | 作用 | 耦合与交接 | 状态（as of 2026-09） |
|---|---|---|---|
| [colav-simulator](https://github.com/ntnu-itk-autonomous-ship-lab/colav-simulator) | COLAV 策略评估框架（本项目上游） | `ICOLAV` 输出 9×N 参考量（位姿/速度/加速度），经 `IController`→`IModel`；`PassThroughCS`（运动学模型直接吃 course/speed）与 `PassThroughInputs`（规划器直出广义力）两种旁路 | 757 commits，2025 秋开源，MIT。Tengesdal & Johansen CCTA 2023 论文配套代码 |
| [rlmpc](https://github.com/ntnu-itk-autonomous-ship-lab/rlmpc) | NMPC 轨迹跟踪 + 抗搁浅 + mid-level 路径跟踪 NMPC 兼 COLAV；SAC 在线调 NMPC 参数 | 规划器为 mid-level：输出参考给低层控制；与 colav-simulator 以 git 依赖直接耦合 | 524 commits，MIT；README 自述 acados 版本敏感、参数敏感、训练脚本未清理 |
| [psbmpc](https://github.com/ntnu-itk-autonomous-ship-lab/psbmpc) | C++/CUDA 的 SB-MPC / 概率 PSB-MPC | 附 `psbmpc_ros_package`（ROS1）与 `sbmpc_catkin_ws`：SB-MPC + VO 双算法栈、对目标丢失鲁棒；GPU 版在 milliAmpere 2 渡轮验证 | 1115 commits，MIT，2024-06 README 后基本冻结 |
| [pybind_im_and_psbmpc](https://github.com/ntnu-itk-autonomous-ship-lab/pybind_im_and_psbmpc) | C++ 算法 → Python 绑定范式 | 原生库 → pybind → adapter → simulator 接口 | 小仓库，MIT |
| [rrt-rs](https://github.com/ntnu-itk-autonomous-ship-lab/rrt-rs) / [vimmjipda](https://github.com/ntnu-itk-autonomous-ship-lab/vimmjipda) / [ship_intention_inference](https://github.com/ntnu-itk-autonomous-ship-lab/ship_intention_inference) / [collision_avoidance_identifier](https://github.com/ntnu-itk-autonomous-ship-lab/collision_avoidance_identifier) | 轨迹规划、跟踪、意图推断、AIS 场景提取 | 支撑件，均围绕 colav-simulator | 均为研究级小仓库 |

信任注记：上游组织 8 个公开仓库全部 MIT（2026-09-11 复核 org 页面），但均为研究代码——README 自述的坑（rlmpc 参数敏感、psbmpc 无 colav-simulator 官方接口文档）要当作真实约束。

**我们能抄**：9×N 参考契约 + 两个 PassThrough 控制器是"规划器输出语义可切换"的现成范式；`pybind_im_and_psbmpc` 是同事 C++ 栈做本地绑定的官方模板；`sbmpc_catkin_ws` 的 VO+MPC 并存栈与本项目处境同构，可对照其仲裁方式。

### 1.2 DNV（注意：没有叫 "Collavoid" 的公开仓库）

检索确认 DNV 公开的是一组"测试基础设施"，不是避碰算法实现：

- [dnv-opensource/ship-traffic-generator](https://github.com/dnv-opensource/ship-traffic-generator)：`pip install trafficgen`，按情形类型/相对方位/速度比生成结构化遭遇场景；MIT；461 commits，活跃（dev 分支 + ruff/pyright/mypy）。背景论文（ICMASS 2023，验证 CAGA 系统）附在 `docs/`。信任注记：只生成几何场景，目标船不动态执行 COLREG 响应。
- [dnv-opensource/maritime-schema](https://github.com/dnv-opensource/maritime-schema)：COLAV 测试的开放交换格式——`traffic_situation.json`（场景输入：本船航点 + 目标船路径）、`situation_output.json`（"避碰系统产出的解"）、仿真输出用 Apache Arrow、`marzip` 打包；MIT，v0.2.1，229 commits。信任注记：schema 文档对 "solution" 的编码（航点 vs 动作）在 README 层面未展开，需读 `schemas/` 源文件。

**我们能抄**：把 `situation_output.json` 当作"规划器→执行栈"交接物的外部参照格式（显式、可校验、可跨工具复现）；用 trafficgen 扩充我们的场景矩阵。信任注记即风险：两者演进快，锁定版本（as of 2026-09）。

### 1.3 VRX / ROS2 海事仿真

- [osrf/vrx](https://github.com/osrf/vrx)：Gazebo Harmonic + ROS 2 Jazzy（Release 3.0，2025-08 wiki 仍活跃），WAM-V USV，波浪/风/流插件 + 传感器仿真；任务世界不含 COLREG。许可见仓库（OSRF 项目，BSD 风格，用前核对）。信任注记：动力学是 Gazebo 插件级（浮力+波面+推力），不是 MMG/参数化操纵模型，对标 45 m 操纵性欠保真。
- [FieldRoboticsLab/MultiVessel_Simulation](https://github.com/FieldRoboticsLab/MultiVessel_Simulation)：VRX Classic 扩展，多船 + AIS 航路 + 船域检测节点 → switch-mechanism 节点触发 RRT 局部规划器生成 COLREG 局部路径 → Pure Pursuit 推力转向；配套 OCEANS 2023 论文（Bayrak & Bayram）。信任注记：**页面未见 LICENSE 文件**，复用前必须核查；ROS Noetic/Gazebo Classic 已过维护期。

**我们能抄**：它的"encounter 检测 → 显式 switch → 局部规划器接管 → 跟踪控制器"链，正是 pattern (a) 的 ROS 化实现，且其切换语义（何时让避碰接管名义航路）值得对照；AIS 航路注入做流量场景。

### 1.4 TU Delft（"RAMlab" 检索澄清）

检索未发现 TU Delft RaM（Robotics & Mechatronics）组有公开 COLREG 代码。TU Delft 系 COLREG-MPC 的实际主体是 Laura Ferranti 组（r2clab；她已转 KU Leuven，代码未公开）：

- Tsolakis, Benders, de Groot, Negenborn, Ferranti, "COLREGs-aware Trajectory Optimization for Autonomous Surface Vessels", IFAC-PapersOnLine 2022（[TU Delft PDF](https://repository.tudelft.nl/file/File_7e2ff5d8-5d79-48cd-998d-667a1a9bb6c6)、[ScienceDirect](https://www.sciencedirect.com/science/article/pii/S2405896322024879)）；期刊扩展 "Model Predictive Trajectory Optimization and Control for Autonomous Surface Vessels Considering Traffic Rules", IEEE T-ITS 2024（[实验室 PDF](https://r2clab.com/wp-content/uploads/2024/01/Tsolakis_TITS_2024.pdf)）。要点：COLREG 情形编成 MPC 约束、**转弯半径约束**进轨迹优化、输出整条时参轨迹给跟踪 NMPC。2026-09 检索无公开配套代码。
- [AUTOBarge/autobargesim](https://github.com/AUTOBarge/autobargesim)：EU ETN AUTOBarge（含 TU Delft）的 MATLAB 内河自主船 G/C 设计工具箱（[arXiv 2503.21594](https://arxiv.org/html/2503.21594)）。MATLAB，非 Python，参考价值在模块划分不在代码复用。

### 1.5 Fossen / MSS 工具链（MATLAB，可执行性受限）

- [cybergalactic/MSS](https://github.com/cybergalactic/MSS)：MIT；MATLAB/Simulink（m 文件兼容 Octave）；CRAFT/GNC/HYDRO/INS；船模目录含 CyberShip II（MCLab 缩比模型试验系数）、Otter（**实试辨识**）、frigate/tanker 等；737 stars，长期维护。信任注记：权威数值 oracle，但直接进我们的 Python 步进链不可行，只做对照。
- [cybergalactic/PythonVehicleSimulator](https://github.com/cybergalactic/PythonVehicleSimulator)：MIT；纯 Python 10 个船模（Otter、frigate、tanker、Clarke83 回归模型等），README 明确系数来自 MSS 目录而非独立试验复现；388 stars。
- MSS 目录系数溯源（外部佐证）：CyberShip II 来自 Skjetne/Fossen 的 MCLab 模型试验完整设计（经典论文，见 [NTNU 数字-物理试验台综述 arXiv 2505.06787](https://arxiv.org/html/2505.06787v5) 的船模清单）；Otter 见 Martinsen 等实试辨识 + [OtterROS](https://arxiv.org/html/2404.05627v2)（开源 ROS 集成 + Otter NMPC）。

**我们能抄**：PythonVehicleSimulator 的 guidance/control 分层写法做参照；MSS 船模做本框架 3DOF 回归 oracle；Clarke83 做参数化合理性 sanity check（45 m 船可比对量级）。

### 1.6 其他 MPC-COLREG 可执行实现

- [ppotoc/MPC-Autonomous-Ship-Navigation](https://github.com/ppotoc/MPC-Autonomous-Ship-Navigation)：MATLAB R2024b；GSHHG 海图全局规划 + 简化 MPC 局部跟踪/避碰，COLREG 写进代价；MIT；JMSE 2025 论文（doi:10.3390/jmse13071246）。**本项目已集成**（`colav_simulator/integrations/potocnik_mpc.py`），此处仅登记。信任注记：作者 Primož Potočnik（Univ. of Ljubljana），"简化 MPC"以实时性优先，保真度有限，与我们内部复刻的定位一致。
- [aavek/Aeolus-Ocean](https://github.com/aavek/Aeolus-Ocean)：Unity 端到端 RL（PPO+模仿）COLREG 数字孪生，Rules 14/15/16 演示；BSD-3-Clause；**仅 Windows 二进制，源码未放**。仅作环境保真度与指标叙事参照，不可抄代码。
- Kongsberg：[kognifai org](https://github.com/kognifai/Kognifai) 仅为平台/SDK 文档，Autonomy Engine 无开源栈样本（2026-09 检索）。结论：无可执行参考。

---

## 2. Mid-level 避碰 ↔ 低层 GNC 耦合模式

三种模式 + 交接语义。每条给"我们能抄"。

### Pattern A：名义航路 LOS/ILOS + 避碰改写期望航向/航速（setpoint 覆盖）

- 代表：BC-MPC（Eriksen & Breivik, JFR 2019, [arXiv 1907.00039](https://arxiv.org/abs/1907.00039)）：避碰 MPC 求解安全**期望航向**交给低层航向 autopilot 跟踪；名义 LOS 航路跟踪在避碰触发时被"期望航向"覆盖，解除后回到 LOS。COLREG Rules 8/13–17 编入代价，全尺寸海试验证。后续 Hybrid BC-MPC（Eriksen et al. 2020, IEEE）把 Voronoi 长期航路规划器与短期 BC-MPC 分层组合，抑制转弯中的振荡行为。
- 多船 ROS 实现：MultiVessel_Simulation（见 1.3）——encounter 开关触发局部 RRT 规划器，Pure Pursuit 跟踪。
- 上游 colav-simulator 的 `PassThroughCS`：运动学模型直接吃 course/speed，即此模式的框架内表达。
- **适配我们**：VO 与 Fan-MPC 输出的正是航向/速度意图——最贴合同事栈的做法是"短航路化"：把意图转成带锚点的 2–4 个稀疏航点，交给原版 `active_route_manager`→ILOS→PID/SMC，而不是让 MPC 每拍直发航向（会与 30 m 最小航段、10 s 最小更新间隔等原版保护打架，见 2026-09-10 方案）。
- **交接语义（accept/reject）**：BC-MPC 类无显式 accept——它逐拍重解，隐式接受。同事栈有显式契约（`RoutePlan`/`AvoidancePlan`、`parent_route_id/revision`、有效期、accept/reject/degrade），这比 BC-MPC 更强；我们应保留显式接受并把拒绝/降级作为一等事件上报规划器（参考 DNV `situation_output` 的显式化思路）。
- **速率失配**：setpoint 覆盖模式天然容错——planner 0.1–0.2 Hz 重解，autopilot 10 Hz 跟当前 setpoint；交接用"latch 最近有效计划 + 有效性窗口"。`sbmpc_catkin_ws` 对目标跟踪丢失鲁棒的处理（psbmpc 仓库）是同类先例；本项目 `modular_gnc/command_latch.py` 已有本地实现。

### Pattern B：避碰输出整条时参轨迹 → 轨迹跟踪控制器消费

- 代表：
  - Tsolakis et al. T-ITS 2024：MPC 轨迹优化（COLREG + 转弯半径约束）→ 跟踪 NMPC。mid/low 分层明确。
  - Abdelaal, Fränzle, Hahn, "NMPC-based trajectory tracking and collision avoidance of USVs with rule-based COLREGs confinement"（IEEE CCTA 2016, [IEEE Xplore](https://ieeexplore.ieee.org/document/7920697/)）：单 NMPC 同时做跟踪+避碰（椭圆船域），属该谱系的紧凑形态。
  - rlmpc（上游生态）：mid-level 路径跟踪 NMPC 输出参考，经 colav-simulator 低层链执行。
  - 本项目 Mid-MPC 即此模式：9×N 时参参考 + 缓冲回放/重接续（`docs/mid-mpc-buffered-playback.md`、`mid-mpc-rejoin-continuity.md`）。
- **适配我们**：Mid-MPC → 同事栈需要"轨迹→航路"降采样桥（时参轨迹折算成带到达时间的稀疏航点），且要预测可行性：轨迹跟踪 NMPC（Tsolakis/Abdelaal）的"约束内生可行性"我们没有——同事栈是 ILOS+PID，会忠实跟踪不可行轨迹直到饱和。因此 B 模式必须前置可行性过滤（见 §3）。
- **交接语义**：轨迹模式必须显式 commit/latch——一旦接受就跟踪到 rejoin 点或被新版本替换；本项目 `historical_acceptance.py`/`rolling_plan.py` 已有雏形。REJECT 语义：接受前检查（转弯半径、速度窗、与原线夹角、执行延迟），不满足则要求规划器重出或降级（减速通过）。
- **速率失配**：0.1–0.2 Hz 轨迹 vs 10 Hz 控制的标准解：计划 ID + revision 锁定、旧计划过期时间 > 重规划周期 × 安全系数、跟踪端对参考做时间对齐（buffered playback）。本地文档已落地，prior art 佐证为 receding-horizon 常规实践（BC-MPC/Tsolakis 均按周期重解、控制器连续跟踪）。

### Pattern C：规划器直出力/力矩（广义力直配）

- 代表：colav-simulator `PassThroughInputs`（README 明示"planner emits low-level generalized forces, e.g., via rudder–propeller mapping"）；文献上多为端到端 NMPC/RL（Aeolus-Ocean）。
- **判断**：对我们是反模式——同事栈的价值恰在"分配（QP/PGD）+ 执行器动态 + 4DOF 船体"这条真实链；绕过它等于丢弃被评估对象。仅保留为诊断对照（理想执行器上界）。

### 交接物的格式参照

- DNV `situation_output.json`（显式解）；同事栈 `RoutePlan/AvoidancePlan/RouteExecutionStatus.msg`（内部 ROS msg，含接受状态与执行反馈）。两者共同点：**计划是带身份（ID/revision）、带约束承诺（exact heading/speed?）、带接受结果的实体，不是一帧 setpoint**。这是我们自己 VO/Fan 桥接最缺的部分（当前航向/速度意图需经批准的转换规则短航路化，见 2026-09-10 方案 §接口）。

---

## 3. 饱和与欠驱动下保持避碰计划动力学可行

- **转弯半径/低速操舵能力**：
  - Tsolakis T-ITS 2024 把转弯半径约束写进轨迹优化——"先验证可行再 commit"的范式来源。
  - [Turning-circle CBFs（arXiv 2504.19247, 2025）](https://arxiv.org/html/2504.19247v1)：用船的回转圆构造 CBF 做 COLREG 避碰——把"可达机动集"显式化为几何过滤，成本低，适合做我们的接受前检查。
  - 速度相关操舵能力：Nomoto K、T 随航速变化（K 随 u 下降、舵效近似 ∝ u²）（Sutulo 2024 综述, [Ocean Engineering](https://www.sciencedirect.com/science/article/pii/S0029801824009764)；Lan et al. 2023, JMSE, 非线性 Nomoto 参数随主机转速/吃水）；低速 MMG 模拟器谱系（Tannuri 等 USP；Hasegawa 低进速模型）。实践锚点：舵效在 ~2 kn 量级以下趋零（引水/驾驶实践，见检索引文），船级/autopilot 文献亦以阈值航速描述舵效丧失。
  - **对 FCB45**：有双艏隧推，低速可操能力比纯舵船强——但艏推能力要作为分配可行性的一部分进检查，不能默认"有隧推=低速随便转"。同事栈 PGD 的 Level-2/3 降级是原版能力的一部分（2026-09-10 方案），必须保留并计入可行性判定。
- **饱和处理谱系**（按侵入性排序）：
  1. 计划侧约束内求解（Tsolakis；BC-MPC 的输入/输出约束）——首选，零运行时开销。
  2. 接受前可行性过滤（turning-circle 几何 + 速度窗 + 舵/推能力查表）——我们现状的正确补强点。
  3. 安全滤波（CBF-QP 最小修正）：von Ellenrieder 2022/2024（[IEEE 9775402](https://ieeexplore.ieee.org/document/9775402/)；[IEEE JOE 2024 relaxed CBF for CPA](https://ieeexplore.ieee.org/iel8/48/10719023/10639539.pdf)）欠驱动 USV CBF 避碰；HOCBF+输入饱和（Zhang 2025, Ocean Engineering/IEEE）；理论可行性（饱和下安全）见 Rabiee 2024（[arXiv 2406.16874](https://arxiv.org/abs/2406.16874)）与 ICCBF（[arXiv 2402.12512](https://arxiv.org/html/2402.12512v1)）。对我们是第二阶段选项：可作 VO/Fan 输出的"最小修正层"，但注意欠驱动船的 CBF 相对阶高、构造难（RPCBF, arXiv 2410.11157 即为此问题）。
  4. 运行时降级分层：同事 PGD Level-2/3 + `allow_degraded_execution` 映射；软约束/slack 在 Mid-MPC 内已有。原则：**计划拒绝、仲裁降速、执行器降级是三类不同事件，分开记录**（与 2026-09-10 方案一致）。

**我们能抄**：turning-circle 几何过滤（低实现成本、可解释）；"速度窗 + 转弯半径 + 艏推贡献"三查表作为 accept gate；CBF 安全滤波列为 Tier-2 优化候选（有文献支撑，但非集成前提）。

---

## 4. 无海试数据下的验证实践（prior art 怎么做）

- **系数来源谱系（诚实标注）**：
  - 缩比模型试验：CyberShip II（Skjetne/Fossen, MCLab）——完整设计+试验闭环的经典范式（[NTNU 试验台综述](https://arxiv.org/html/2505.06787v5)）。
  - 实尺寸试航辨识：Otter（Martinsen 等；MSS `otter` 目录即实试辨识参数；[OtterROS](https://arxiv.org/html/2404.05627v2) 用于 NMPC/滤波研究）。
  - 回归/参数化估计：Clarke83（PythonVehicleSimulator 内置）——45 m 船的量级 sanity check。
  - 仿真内系统辨识：Wu et al. 2022, "Identification method of nonlinear maneuver model for …"（[J. Mech. Sci. Technol., Springer doi:10.1007/s12206-022-0743-0](https://link.springer.com/article/10.1007/s12206-022-0743-0)）用 RK4 仿真数据 + 优化反演非线性操纵模型系数；滤波/辨识研究惯例另见 OtterROS（EKF 系列）。
  - HIL/数字-物理：NTNU CyberShip 台（arXiv 2505.06787）；SIL 平台 VRX/Stonefish（后者 GPL-3.0，见 2026-08-28 调研）。milliAmpere 2（PSB-MPC GPU 实验载体）证明"仿真验证→全尺寸实验"的衔接路径，但其海试结论不可外推到我们的 45 m 船型。
- **Sim-to-real 差距的文档化**：BC-MPC（JFR 2019）报告全尺寸实验与仿真的偏差来源；PSB-MPC 在 milliAmpere 2 上区分 GPU 实时性与控制性能。共同点：**把"哪些参数可信、哪些是占位"写成表**。对我们：FCB45 系数来源必须向同事索要溯源说明（模型试验/CFD/经验公式各占哪些项），并登记进 `docs/research/2026-09-08-fcb45-fullstack-review-sources.md` 同级的证据文件——没有溯源的项标为"mock/未验证"，禁止用于对外结论。
- **指标**：
  - COLREG 合规：Woerner, Benjamin, Novitzky, Leonard, "Quantifying protocol evaluation for autonomous collision avoidance: Toward establishing COLREGS compliance metrics", Autonomous Robots 43(4):967–991, 2019（[MIT OA PDF](https://dspace.mit.edu/bitstream/handle/1721.1/116295/springer_submit.pdf)）——安全裕度 + 任务达成 + 人类专家判断合成行为指数；后续工程化见 [Ocean Engineering 2024 情形分类与合规评估（CRI 加权）](https://www.sciencedirect.com/science/article/pii/S0029801824028907)。
  - 场景生成标准化：[ISO/AWI 25927](https://www.iso.org/standard/92071.html)（MASS 避碰测试场景生成流程，在研，as of 2026-09 未发布）；DNV trafficgen + schema 是其开源近似。
  - 执行质量：XTE（名义线/活动线分开）、CPA/TCPA 裕度、舵/推活动、饱和时间、能耗——本框架已有记录面（2026-09-10 方案 §S5），外部佐证为 Woerner 指标族 + DNV Arrow 输出 schema。
- **对我们无海试约束的验证阶梯**（见 §5 R4）。

---

## 5. 综合建议（按优先级排序）

**R1. 耦合架构：RouteBridge 单一交接面，A/B 双模式分流（首选实现）。**
VO/Fan-MPC 输出走 Pattern A（意图 → 批准的转换规则 → 稀疏短航路 → 原 active route manager 仲裁 → ILOS → PID/SMC → PGD）；Mid-MPC 时参轨迹走 Pattern B（轨迹 → 带到达时间的稀疏航路降采样 → 同一仲裁面）。两者共用同一计划契约（ID/revision/parent/有效期/accept-reject-degrade）。这样保留同事栈全部保护（30 m 航段、8 m/s、转弯/减速可行性检查、10 s 更新间隔、横向跳变上限）为天然可行性过滤，而不是绕开它们。不做 Pattern C（力直配），只留理想执行器对照模式。
依据：§2 A/B 交接语义；colav-simulator 9×N 契约与 PassThrough 旁路；2026-09-10 方案已定方向，本调研补充了 BC-MPC/Tsolakis/MultiVessel 三个 prior art 锚点。

**R2. 把"接受前可行性检查"做成显式三查表组件（复制同事栈规则，不新造）。**
查表 = 回转圆几何（当前航速下可达机动集，参照 turning-circle CBF 的几何化）+ 速度窗（含最低操舵航速、隧推低速贡献）+ 执行延迟（计划生效时刻 vs 重规划周期）。检查失败→返回 reject + 机器可读原因码，规划器据此重出或降级；通过→commit 并 latch。理由码直接成为遥测指标（拒因分布 = 优化点探测器）。
依据：§3；同事栈原保护清单（2026-09-10 方案）。

**R3. 复制 vs 重设计边界。**
复制不动：ILOS/ALOS 策略、PID/SMC 增益与限幅、PGD 分配与降级、4DOF 船体与环境引擎、调度周期。重设计仅限适配层：坐标系/单位（WGS84 经纬度↔本地米制、NE 顺序、rad/deg、HDG/COG、SOG/对水）在 RouteBridge 单点转换并做往返测试；速率桥（latch+过期+buffered playback，已有本地实现）；执行反馈（accept/reject/degrade 事件上行到规划器遥测）。参照 pybind/ROS 两条路径的取舍见 2026-09-10 方案（A 原包优先，B 提取绑定次之）。
依据：§1.1、§2 交接物格式；已知坑清单（见下）。

**R4. 验证阶梯（无海试版）。**
① 系数溯源表：FCB45 每个水动力/执行器项标注来源（模型试验/CFD/经验/未知），未知项冻结为"mock"标签，结论措辞随之分级；② GNC-only 闭环基线：静水直航/回转/Z 形，对照 MSS 同尺度模型（Clarke83 量级 + tanker/frigate 操纵性趋势）做量级 sanity，记录 XTE/超调/舵推活动；③ 场景矩阵：用 trafficgen（锁定版本）生成 HO/CS/OT/多船 × 环境，导出/导入 maritime-schema 格式，保证可跨工具复核；④ 合规打分：Woerner 指标族（安全裕度+任务达成+行为判断）替代"不碰撞即通过"；⑤ 参数敏感性扫描代替保真度声明（无海试时，结论只能是"在系数误差带 X 内策略仍成立"）。HIL/台架列为后续项（参照 NTNU 数字-物理台做法），非本轮。
依据：§4；2026-09-10 方案 S1/S5 证据门槛。

**R5. 优化点探测器（集成完成后启动）。**
拒因码分布（R2 产出）、饱和时间/分配残差（PGD Level 触发频率）、Mid-MPC 轨迹被仲裁修改的比例、XTE 分解（名义 vs 活动线）、CPA 裕度分布对 COLREG 规则分桶。文献对照：BC-MPC 的振荡抑制（Hybrid 版动机）、Tsolakis 的转弯半径约束（可行性失配动机）——若我们遥测出现同类症状（避碰后振荡、计划被频繁拒），优化方向直接对号。
依据：§2/§3 prior art 的"动机即故障模式"。

### 常见坑（prior art 与本仓库教训汇总）

1. 坐标/单位错位：WGS84 度 vs 本地米制 rad；NE vs EN；HDG vs COG——2026-09-10 方案已列，DNV schema（北东、米）可作第三方对照。
2. 计划契约错配：MPC 密集时参点 vs 原栈 30 m 最小航段/10 s 更新间隔——直接拒计划；必须降采样 + 锚点化，不是稀疏化原轨迹了事。
3. 第二积分器：适配器内再跑一次 RK4 或用框架位置覆盖原状态——原栈必须是本船唯一积分来源。
4. mock 系数当真：本框架 Viknes/Gunnerus 响应参数冒充 FCB45 身份进规划器——先测原栈响应、另立身份。
5. 隐式接受：把"框架接受计划"当"原 GNC 已接受"——两态分开记录。
6. 暂停/步进语义：原栈 wall timer 内部读 `now()`，冻结 `/clock` 不够——详见 2026-09-10 方案。
7. 速率失配未 latch：planner 迟到/缺帧时 autopilot 跟过期 setpoint——过期窗口 > 重规划周期 × 安全系数，超时显式失败。

### 时效性注记（as of 2026-09）

- ntnu-itk-autonomous-ship-lab 各仓库 2025 秋才开源、无 release/tag——引用时锁定 commit，不追 main。
- rlmpc README 自述 acados 新版本需修代码；psbmpc 2024-06 后活动低。
- DNV maritime-schema v0.2.1、trafficgen 均在活跃演进——锁定版本使用。
- Ferranti 组迁往 KU Leuven，Tsolakis 系列代码未公开——不可依赖其发布。
- VRX 主线 3.0（Gazebo Harmonic/Jazzy）；MultiVessel_Simulation 停留在 ROS Noetic/Gazebo Classic 且无 LICENSE 文件——复用前核查，不可直接引入。
- Aeolus-Ocean 仅 Windows 二进制，源码"未来可能开放"（README 原话）——按不可用处理。
- ISO/AWI 25927 在研未发布；Woerner 指标的工程化版本（Ocean Eng 2024 等）仍在分裂演化。
- 许可证均于 2026-09-11 经仓库页面复核；之后如需依赖，重新核对 LICENSE 文件。
