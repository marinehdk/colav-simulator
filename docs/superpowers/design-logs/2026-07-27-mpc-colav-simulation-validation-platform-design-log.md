# 设计日志: MPC 避碰仿真控制与集成验证平台

> **模式**: 重构        **创建**: 2026-07-27
> **关联方案包**: `docs/superpowers/specs/2026-07-27-mpc-colav-simulation-validation-platform-solution-pack.md`
> **状态**: 旧范围已终止；由 `2026-07-27-dynamic-mpc-playground-design-log.md` 继续
> **工作分支**: `codex/colav-backend-algorithms`
> **设计对象**: MPC 避碰算法所需的闭环仿真、算法接入、诊断、评价、批量验证和证据体系

## 0. 决策树状态(权威索引 · 可变快照)

### 0.1 决策点注册表 [DP]

| ID | 描述 | 类型 | 父/分解 | 状态 | 详见 | 来源 |
|---|---|---|---|---|---|---|
| DP-01 | 平台验证对象、ODD 边界及“控制器/规划器/完整 COLAV 系统”验收层级 | 架构 | - | 调研中 | Step2 DP-01 | [R1][R9][R10] |
| DP-02 | 是否采用分层/混合 COLAV 控制架构及各层职责 | 技术 | TD-01 | 未决 | - | [R3][R4][R5][R11] |
| DP-03 | 全局/高层路径规划与 MPC 避碰的职责边界 | 架构 | TD-01 | 未决 | - | [R3][R4][R5] |
| DP-04 | 中层 MPC 的时间/空间责任范围 | 架构 | TD-01 | 未决 | - | [R3][R5] |
| DP-05 | 近场/紧急反应层是否属于被测算法、平台保护层或对照算法 | 架构 | TD-01 | 未决 | - | [R4][R5] |
| DP-06 | 多层计划/指令仲裁、优先级和唯一 executed identity | 接口 | TD-01 | 未决 | - | [R5][R9][R13] |
| DP-07 | 正常、降级、紧急、恢复的切换及迟滞语义 | 约束 | TD-01 | 未决 | - | [R4][R5] |
| DP-08 | 求解失败时 fail-stop、hold-last、保护控制或后备算法的政策 | 架构 | TD-01 | 未决 | - | [R4][R5][R10][R12] |
| DP-09 | 统一 MPC/COLAV 插件契约及其版本边界 | 技术 | TD-02 | 未决 | - | [R1][R9][R11][R12] |
| DP-10 | 本船状态向量、估计状态和算法可观测量 | 接口 | TD-02 | 未决 | - | [R3][R6][R11] |
| DP-11 | MPC 决策变量：轨迹、航向/航速、加速度、力/力矩或执行器量 | 算法 | TD-02 | 未决 | - | [R3][R4][R6] |
| DP-12 | 预测模型：运动学、3DOF、控制器闭环模型或多模型 | 算法 | TD-02 | 未决 | - | [R3][R4][R5] |
| DP-13 | 离散化、预测时域、控制时域、规划周期和仿真步长的多率关系 | 阈值 | TD-02 | 未决 | - | [R3][R4][R5][R12] |
| DP-14 | 名义路径、速度计划、goal 和终端条件的参考语义 | 接口 | TD-02 | 未决 | - | [R3][R4][R11] |
| DP-15 | 目标船运动/意图预测模型及多模态预测表示 | 算法 | TD-02 | 未决 | - | [R4][R6] |
| DP-16 | Track covariance、过程噪声、意图不确定性进入 MPC 的方式 | 算法 | TD-02 | 未决 | - | [R6][R11] |
| DP-17 | ENC、吃水、岸线/浅水区、静态障碍的算法输入和几何表示 | 接口 | TD-02 | 未决 | - | [R6][R8][R11] |
| DP-18 | 船体几何、安全域、动态/静态安全裕度及碰撞判定 | 约束 | TD-02 | 未决 | - | [R4][R6][R7][R8] |
| DP-19 | 目标函数分项、优先级、归一化及“安全不能被收益抵消”的语义 | 算法 | TD-02 | 未决 | - | [R3][R4][R5] |
| DP-20 | 硬约束、软约束、slack、约束松弛顺序及最小裕度输出 | 约束 | TD-02 | 未决 | - | [R3][R5][R6] |
| DP-21 | COLREGS 通过外部 FSM、MPC 约束、代价或候选剪枝接入 | 算法 | TD-02 | 未决 | - | [R2][R4][R5] |
| DP-22 | 求解器类型、线性/NLP/采样式执行路径及依赖环境 | 技术 | TD-02 | 未决 | - | [R3][R4][R6][R15] |
| DP-23 | 初始猜测、热启动、上次可行解和求解重启策略 | 算法 | TD-02 | 未决 | - | [R3][R5] |
| DP-24 | SUCCESS、超时可行、不可行、数值失败及 deadline miss 判定 | 接口 | TD-02 | 未决 | - | [R9][R12] |
| DP-25 | 预测轨迹到 guidance/controller/actuator 的输出兼容与跟踪误差反馈 | 接口 | TD-02 | 未决 | - | [R3][R4][R11][R13] |
| DP-26 | 代价、约束、预测、求解状态、候选集和内部策略的可观测诊断 | 接口 | TD-02 | 未决 | - | [R1][R10][R12] |
| DP-27 | COLREGS 遭遇生命周期和规则状态机 | 技术 | TD-03 | 未决 | - | [R2][R5][R7][R14] |
| DP-28 | 风险形成、规则触发、阶段推进、解除及再次进入条件 | 算法 | TD-03 | 未决 | - | [R2][R5][R7] |
| DP-29 | Rule 13/14/15 的船对分类、让路/直航角色及边界角 | 算法 | TD-03 | 未决 | - | [R2][R5][R7] |
| DP-30 | 规则锁定、迟滞及转向后不错误切换遭遇类型 | 约束 | TD-03 | 未决 | - | [R5][R7][R14] |
| DP-31 | Rule 8/13/14/15/16/17 行为要求的机器可执行表示 | 算法 | TD-03 | 未决 | - | [R2][R5][R7] |
| DP-32 | 多船同时义务、冲突规则和优先级合成 | 算法 | TD-03 | 未决 | - | [R5][R7] |
| DP-33 | 他船不合作、规则违反、晚发现和 Rule 17 紧急动作 | 算法 | TD-03 | 未决 | - | [R2][R4][R5] |
| DP-34 | 算法内部规则状态、实时监视状态、Evaluator 真值状态的隔离与对照 | 接口 | TD-03 | 未决 | - | [R7][R9][R14] |
| DP-35 | 唯一闭环仿真执行链及确定性时序 | 技术 | TD-04 | 未决 | - | [R1][R9][R13] |
| DP-36 | truth→sensor→tracker→plan→guidance/control→plant→log 的相位顺序 | 架构 | TD-04 | 未决 | - | [R1][R9][R13] |
| DP-37 | 被测 MPC 预测模型、仿真船模和控制器之间的模型失配策略 | 算法 | TD-04 | 未决 | - | [R3][R4][R5] |
| DP-38 | 风、浪、流及扰动输入、可见性和可重复注入 | 接口 | TD-04 | 未决 | - | [R1][R5][R11] |
| DP-39 | 真值、Radar/AIS、God/KF/VIMMJIPDA 的输入隔离和跟踪质量验证 | 架构 | TD-04 | 未决 | - | [R1][R6][R9] |
| DP-40 | 仿真时钟、wall clock、求解 deadline、超时和调度抖动 | 约束 | TD-04 | 未决 | - | [R3][R4][R9] |
| DP-41 | 碰撞、搁浅、越界、NaN/Inf、连续失败及目标到达终止语义 | 约束 | TD-04 | 未决 | - | [R1][R8][R9] |
| DP-42 | episode、量测、tracker、扰动和算法随机流的确定性重放 | 架构 | TD-04 | 未决 | - | [R1][R9] |
| DP-43 | C++/Rust/Acados 原生依赖的进程隔离、退出码和崩溃证据 | 技术 | TD-04 | 未决 | - | [R9][R10][R15] |
| DP-44 | 插件发现、依赖身份、配置、reset、状态迁移和无静默 fallback | 接口 | TD-04 | 未决 | - | [R9][R10][R11][R15] |
| DP-45 | MPC 能力资格验证方法和等级体系 | 技术 | TD-05 | 未决 | - | [R1][R7][R9][R10] |
| DP-46 | G0-G4 的证据生成、自动晋级/降级和组合兼容判定 | 架构 | TD-05 | 未决 | - | [R9][R10][R15] |
| DP-47 | 标准遭遇、ENC、论文、多船、AIS、Imazu 和故障场景分类 | 架构 | TD-05 | 未决 | - | [R1][R7][R9] |
| DP-48 | 几何、船型、速度、感知、扰动、模型、时序和算法参数覆盖轴 | 约束 | TD-05 | 未决 | - | [R1][R7][R9] |
| DP-49 | Evaluator profile、工程指标、控制品质和实时性指标 | 架构 | TD-05 | 未决 | - | [R7][R8][R9][R14] |
| DP-50 | 共同 episode、公平对比、seed 数、统计量、置信区间和失败样本政策 | 约束 | TD-05 | 未决 | - | [R1][R7][R9] |
| DP-51 | PlannerTrace、manifest、trajectory、events 和 evaluation 的证据 schema | 接口 | TD-05 | 未决 | - | [R1][R9][R12][R13] |
| DP-52 | 单元、契约、闭环、Monte Carlo、论文数值和回放回归测试分层 | 架构 | TD-05 | 未决 | - | [R1][R7][R9] |
| DP-53 | MPC 参数整定、参数版本、训练/验证/保留场景隔离和防过拟合 | 架构 | TD-05 | 未决 | - | [R1][R7] |
| DP-54 | 功能复现、数值复现、算法验证及可发布结论边界 | 约束 | TD-05 | 未决 | - | [R1][R7][R9] |
| DP-55 | 反事实、边界、故障注入和最差场景挖掘策略 | 算法 | TD-05 | 未决 | - | [R1][R7][R9] |

### 0.2 技术分解注册表 [TD]

| ID | 技术 | 分解子模块(→DP) | 触发步骤 |
|---|---|---|---|
| TD-01 | 分层/混合 COLAV 控制架构 | 高层边界(DP-03)、中层 MPC(DP-04)、紧急层(DP-05)、仲裁(DP-06)、切换/恢复(DP-07)、失败政策(DP-08) | Step1 |
| TD-02 | 统一 MPC/COLAV 插件 | 状态(DP-10)、决策变量(DP-11)、模型(DP-12)、时域/多率(DP-13)、参考(DP-14)、目标预测(DP-15)、不确定性(DP-16)、ENC(DP-17)、安全域(DP-18)、目标函数(DP-19)、约束/slack(DP-20)、COLREGS 耦合(DP-21)、求解器(DP-22)、热启动(DP-23)、状态语义(DP-24)、控制输出(DP-25)、诊断(DP-26) | Step1 |
| TD-03 | COLREGS 遭遇生命周期/FSM | 触发/解除(DP-28)、分类/角色(DP-29)、锁定/迟滞(DP-30)、规则行为(DP-31)、多船冲突(DP-32)、不合作/紧急(DP-33)、三套状态隔离(DP-34) | Step1 |
| TD-04 | 闭环仿真执行系统 | 相位顺序(DP-36)、模型失配(DP-37)、环境(DP-38)、感知/跟踪(DP-39)、时钟/deadline(DP-40)、终止(DP-41)、随机重放(DP-42)、原生隔离(DP-43)、插件生命周期(DP-44) | Step1 |
| TD-05 | 仿真资格与统计验证 | 能力证据(DP-46)、场景分类(DP-47)、覆盖轴(DP-48)、Evaluator/指标(DP-49)、公平统计(DP-50)、证据 schema(DP-51)、测试分层(DP-52)、整定治理(DP-53)、结论边界(DP-54)、故障/最差场景(DP-55) | Step1 |

### 0.3 盲区注册表 [BL]

| ID | 问题 | 归属决策点 | 优先级 | 调研状态 |
|---|---|---|---|---|
| BL-01 | 自研 MPC 最终在 TDL 中接收什么输入、输出什么层级指令 | DP-01 | 高 | 未调研 |
| BL-02 | Playground 与 TDL 只做数据契约对齐，还是还需离线导入 TDL trace | DP-01 | 中 | 未调研 |
| BL-03 | 仿真船模与 TDL 使用船模需要多大程度一致 | DP-01 | 高 | 未调研 |

### 0.4 证据矩阵 [EV]

| ID | 来源类型 | 引用 | 检索置信 | 来源权威 | 场景适用 | 归属 |
|---|---|---|---|---|---|---|
| [R1] | DOMAIN_EVIDENCE | CCTA 2023 仿真评价框架论文 | 高 | 高 | 高 | DP-01, DP-35, DP-45..55 |
| [R2] | DOMAIN_EVIDENCE | IMO COLREG 规则概览 | 高 | 高 | 高 | DP-21, DP-27..33 |
| [R3] | DOMAIN_EVIDENCE | 2017 中层 NLP-MPC 论文 | 高 | 高 | 高 | DP-02..25 |
| [R4] | DOMAIN_EVIDENCE | 2019 BC-MPC 论文 | 高 | 高 | 高 | DP-02..25, DP-33 |
| [R5] | DOMAIN_EVIDENCE | 2020 分层 Hybrid COLAV 论文 | 高 | 高 | 高 | DP-02..34 |
| [R6] | DOMAIN_EVIDENCE | PSB-MPC 风险/抗搁浅论文体系 | 高 | 高 | 高 | DP-15..23 |
| [R7] | DOMAIN_EVIDENCE | 2023 Safety/COLREG Evaluator 论文 | 高 | 高 | 高 | DP-27..34, DP-45..55 |
| [R8] | DOMAIN_EVIDENCE | 2024 grounding evaluation 扩展 | 高 | 高 | 高 | DP-17, DP-18, DP-41, DP-49 |
| [R9] | DOCUMENTED_INTENT | 当前完整架构文档 | 高 | 中 | 高 | 全部 |
| [R10] | PROJECT_FACT | 当前算法能力矩阵 | 高 | 中 | 高 | DP-01, DP-08, DP-43..54 |
| [R11] | PROJECT_FACT | `ICOLAV` 与 integration registry | 高 | 中 | 高 | DP-09..26, DP-44 |
| [R12] | PROJECT_FACT | `PlanDiagnostics` / `PlannerTrace` | 高 | 中 | 高 | DP-13, DP-24..26, DP-51 |
| [R13] | PROJECT_FACT | Simulator/Session/Runner/Persistence | 高 | 中 | 高 | DP-35..44, DP-51 |
| [R14] | PROJECT_FACT | 当前 EncounterMonitor/Evaluator | 高 | 中 | 高 | DP-27..34, DP-49 |
| [R15] | PROJECT_FACT | capability catalog、legacy custom adapter 与外部集成 | 高 | 中 | 高 | DP-22, DP-43, DP-44, DP-46 |

### 0.5 场景注册表 [SC]

| ID | 场景描述 | 约束/边界 | 驱动决策点 |
|---|---|---|---|
| SC-01 | MPC 白盒验证 | 固定 ownship/track/ENC 输入；检查预测、约束、代价、状态和求解时间 | DP-01 |
| SC-02 | MPC 最小闭环验证 | 可选 God/KF；真实 guidance/controller/ship model 执行；Evaluator 离线评分 | DP-01 |
| SC-03 | TDL 边界验证 | 只做数据契约对齐和离线证据交换；不复制生产级 TDL 模块 | DP-01 |

### 0.6 裁决注册表 [VR]

| ID | 裁决对象 | 结论 | 采纳/弃用 | 理由 | 时间 |
|---|---|---|---|---|---|
| - | 尚未裁决 | - | - | - | - |

### 0.7 备选/弃用方案 [ALT]

| ID | 方案 | 弃用理由 | 对比于 |
|---|---|---|---|
| - | 尚未裁决 | - | - |

### 0.8 技术规约注册表 [TS]

| ID | 类别 | 规约内容 | 单位/定义 | 来源 | 关联DP/接口 | 与现状差异 |
|---|---|---|---|---|---|---|
| - | Step6 后登记 | - | - | - | - | - |

---

## 参考文献

- [R1] Tengesdal, T.; Johansen, T. A. “Simulation Framework and Software Environment for Evaluating Automatic Ship Collision Avoidance Algorithms.” CCTA 2023, DOI 10.1109/CCTA54093.2023.10252863；本地 `paper/Simulation_Framework_and_Software_Environment_for_Evaluating_Automatic_Ship_Collision_Avoidance_Algorithms.pdf`。
- [R2] International Maritime Organization. “COLREG - Preventing collisions at sea.” Rules 8 and 13-17 overview.
- [R3] Eriksen, B.-O. H.; Breivik, M. “MPC-based Mid-level Collision Avoidance for ASVs using Nonlinear Programming.” CCTA 2017, DOI 10.1109/CCTA.2017.8062554；本地 `paper/MPC-based mid-level collision avoidance for ASVs using nonlinear programming.pdf`。
- [R4] Eriksen, B.-O. H.; Breivik, M.; et al. “The branching-course model predictive control algorithm for maritime collision avoidance.” Journal of Field Robotics 36, 2019, DOI 10.1002/rob.21900；本地同名 PDF。
- [R5] Eriksen, B.-O. H.; Bitar, G.; Breivik, M.; Lekkas, A. M. “Hybrid Collision Avoidance for ASVs Compliant With COLREGs Rules 8 and 13-17.” Frontiers in Robotics and AI 7:11, 2020, DOI 10.3389/frobt.2020.00011；本地同名 PDF。
- [R6] Tengesdal, T.; Johansen, T. A.; et al. “On Collision Risk Assessment for Autonomous Ships Using Scenario-Based MPC,” IFAC-PapersOnLine 53(2), 2020, DOI 10.1016/j.ifacol.2020.12.1454；及 “Ship Collision Avoidance and Anti Grounding Using Parallelized Cost Evaluation in Probabilistic Scenario-Based Model Predictive Control,” IEEE Access 10, 2022, DOI 10.1109/ACCESS.2022.3215654。
- [R7] Hagen, I. B.; Vassbotn, O.; Skogvold, M.; Johansen, T. A.; Brekke, E. F. “Safety and COLREG evaluation for marine collision avoidance algorithms.” Ocean Engineering 288, 2023, 115991.
- [R8] Hagen, I. B.; Murvold, M. N.; Johansen, T. A.; Brekke, E. F. “Grounding hazard considerations in evaluation of COLREGS collision avoidance algorithms.” Ocean Engineering 308, 2024, 118204.
- [R9] `Design/Colav-Simulator-Architecture.md`。
- [R10] `Design/Algorithm-Capability-Matrix.md`。
- [R11] `colav_simulator/core/colav/colav_interface.py`；`colav_simulator/integrations/registry.py`。
- [R12] `colav_simulator/core/colav/diagnostics.py`；`tests/test_rule14_planner_trace.py`。
- [R13] `colav_simulator/simulator.py`；`colav_simulator/experiment/session.py`；`runner.py`；`persistence.py`。
- [R14] `colav_simulator/evaluation/encounter.py`；`evaluator.py`。
- [R15] `colav_simulator/experiment/capabilities.py`；`colav_simulator/guidance/custom_mpc_adapter.py`；`colav_simulator/integrations/psbmpc.py`；`rrt.py`。

---

## 演进日志(append-only · 时序 · 不可覆盖)

### Step1 · 行业调研·发现决策点 [2026-07-27]

- 模式判定：**重构模式**。当前已有真实 `Simulator.step()`、`ICOLAV`、`PlannerTrace`、ExperimentRunner、Evaluator 重建版及 Rule 14 六组合；目标为查漏补缺和重新裁定关键语义，不全盘推倒。
- 快调来源：本地 CCTA/BC-MPC/NLP-MPC/Hybrid COLAV 论文；IMO COLREG；PSB-MPC 与评价论文；当前架构、能力矩阵和真实源码。
- NLM 状态：项目未配置 `.nlm/config.json`，本步骤未创建/写入 NotebookLM；使用本地论文和权威 Web 来源完成广度扫描。
- 代码索引状态：本会话未提供 codegraph MCP；使用 `rg`、`nl` 和目标源码读取降级完成。
- 项目事实：
  - `ICOLAV.plan()` 已定义 ownship、tracks/covariance、ENC、goal、disturbance 和 9xN 输出，但动态障碍仍为位置/速度元组，缺显式时间戳、预测模式和输入有效性语义。
  - `PlannerTrace` 已冻结求解状态、9xN 预测、指令、目标预测、约束和算法专项信息。
  - 当前 SB-MPC 为有限航向/速度候选、恒定目标速度预测和简化本船预测；Rule 14 可展示，但不是通用 NMPC 验证完成证明。
  - `custom_mpc_adapter.py` 仍存在第二条 `IGuidance` 接入路径、硬编码本机路径、势场算法冒充 MPC、缺依赖时静默 fallback；与正式 `ICOLAV`/无 fallback 契约冲突，必须在后续决策中裁定隔离或移除。
  - 当前 `EncounterMonitor` 每步重新分类，只有阶段单调化；规则身份锁定、迟滞和完整生命周期未裁定。
  - 当前 Evaluator 明确为 `functional_reproduction`，评分公式仍是透明启发式重建，不能支撑论文数值结论。
  - 当前 G3 证据仅 `head_on`、Nominal/VO/SB-MPC、God/KF；能力目录为静态声明加手工 evidence，尚未由资格任务自动生成。
- 新增决策点：DP-01..DP-55。
- 触发技术分解：
  - TD-01 分层/混合 COLAV → DP-03..DP-08。
  - TD-02 统一 MPC/COLAV 插件 → DP-10..DP-26。
  - TD-03 COLREGS 生命周期/FSM → DP-28..DP-34。
  - TD-04 闭环仿真执行 → DP-36..DP-44。
  - TD-05 仿真资格与统计验证 → DP-46..DP-55。
- Step1 内部确认门：用户于 2026-07-27 确认 DP-01..DP-55 覆盖，授权进入 Step2。

### Step2 · grilling 压力测试 [2026-07-27]

#### DP-01 · 平台验证对象与 ODD 边界

- [专家] CCTA 框架支持算法无关的注入和闭环评价，但不要求测试平台复制生产系统。[R1]
- [新手] 仅看 MPC 预测不够；需要最小船模/控制器验证可执行性，但这些是测试夹具，不是 TDL 产品模块。
- [悲观] 若不区分被测算法和测试夹具，保护层救场、真值输入或控制器行为会被错误计入 MPC 能力。
- [机制C默认最简版失效] 只检查 9xN 非空和最终无碰撞，不能证明约束满足、可执行、无 fallback 或算法确实产生避碰行为。
- 用户补充：本项目目标是独立 MPC playground，避免在 MASS-L3 TDL 中因多模块耦合无法判断 MPC 正确性；不得在本项目复制 TDL。
- 用户确认结论：
  - 被测对象是 MPC 避碰规划器。
  - V1 为固定输入的 MPC 白盒验证。
  - V2 为使用必要测试夹具的最小闭环验证。
  - TDL 仅保留 adapter、数据契约对齐和证据交换边界。
  - Playground 正确性优先；支持后续新 MPC 快速接入。
- 新增盲区：BL-01..BL-03。
- 新增场景：SC-01..SC-03。

#### 范围修订请求

- 用户澄清：本项目仅专注中层航行避碰 MPC playground；安全前提为 ENC 可航水域，并测试/验证 COLREGS 避碰行为。
- 用户明确排除：不得复制 `/Users/marine/Code/MASS-L3-Tactical Layer` 的生产级 TDL 系统，不建设高层任务规划、生产级低层安全接管或完整感知/运行架构。
- 处理：暂停 DP-02 grilling，回到 Step1 重新裁剪 DP-01..DP-55；稳定 ID 不复用，待用户确认精简树后再更新注册表状态。

### Step1 · 旧范围终止 [2026-07-27]

- 用户确认新范围：一个动态 MPC Playground 主链；论文复现、RRT 和 VIM 为条件插件；`Custom MPC` 指用户自研算法。
- 本日志保留原 DP-01..DP-55，避免抹除历史或复用稳定 ID。
- 精简后的独立决策树转入 `2026-07-27-dynamic-mpc-playground-design-log.md`；本日志不再进入 Step2。
