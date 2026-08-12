# 设计日志: RLMPC main 集成

> **模式**: 重构/补全        **创建**: 2026-08-10
> **关联 spec**: 未创建
> **状态**: Step1 进行中, 等待用户确认决策点覆盖

## 0. 决策树状态(权威索引 · 可变快照)

### 0.1 决策点注册表 [DP]

| ID | 描述 | 类型 | 父/分解 | 状态 | 详见 |
|----|------|------|---------|------|------|
| DP-01 | 首次集成对象: 固定参数基线 NMPC、SAC 调参 RLMPC, 或分阶段同时交付 | 架构 | TD-01/TD-02 | 未决 | - |
| DP-02 | RLMPC 算法身份与现有 `rlmpc` 稳定 ID 的兼容策略 | 接口 | TD-03 | 未决 | - |
| DP-03 | Python/Acados/CasADi/RRT/ML 依赖采用同环境还是隔离运行 | 架构 | TD-03 | 未决 | - |
| DP-04 | 船舶状态、控制量、动力学模型与低层控制器契约 | 技术 | TD-01 | 未决 | - |
| DP-05 | 预测时域、离散步长、求解频率、实时 deadline | 阈值 | TD-01 | 未决 | - |
| DP-06 | 路径跟踪、航速、控制平滑、COLREG 势函数之间的目标函数层级 | 约束 | TD-01 | 未决 | - |
| DP-07 | TPS-RBF ENC 静态障碍表示、缓冲和 anti-grounding 约束语义 | 技术 | TD-01 | 未决 | - |
| DP-08 | 动态目标运动预测、船域、跟踪协方差和目标数量上限 | 技术 | TD-01 | 未决 | - |
| DP-09 | HO/CR/OT 分类、保持、释放、stand-on 与多目标冲突处理 | 技术 | TD-01 | 未决 | - |
| DP-10 | Acados/CasADi 求解器、warm start、QP/NLP 失败处理, 且禁止静默 fallback | 技术 | TD-01/TD-03 | 未决 | - |
| DP-11 | SAC 的角色: 直接控制、NMPC actor, 或有界 MPC parameter provider | 技术 | TD-02 | 未决 | - |
| DP-12 | RL 观测: 航迹相对量、ENC 图像、目标轨迹、扰动、MPC 参数 | 技术 | TD-02 | 未决 | - |
| DP-13 | RL 可调参数集合与硬安全边界, 特别是动态船域和 COLREG 权重 | 约束 | TD-02 | 未决 | - |
| DP-14 | 奖励函数、训练分布、课程、随机化和验证集隔离 | 技术 | TD-02 | 未决 | - |
| DP-15 | SAC 梯度是否使用 OCP/KKT sensitivity, 以及非最优解时的梯度语义 | 技术 | TD-02 | 未决 | - |
| DP-16 | 训练模型 artifact、版本身份、确定性推理、OOD/失效检测 | 接口 | TD-02/TD-03 | 未决 | - |
| DP-17 | 如何映射到当前 `ICOLAV`/`CustomMPCAdapter` 的输入、轨迹、诊断和 reset 契约 | 接口 | TD-03 | 未决 | - |
| DP-18 | 能力分级与验收矩阵: anti-grounding、HO/CR/OT、多船、扰动、COLREG、实时性 | 架构 | TD-03 | 未决 | - |

### 0.2 技术分解注册表 [TD]

| ID | 技术 | 分解子模块(->DP) | 触发步骤 |
|----|------|------------------|----------|
| TD-01 | 基线中层 NMPC | 交付范围(DP-01); 状态/控制/模型(DP-04); 时序(DP-05); 目标函数(DP-06); 静态障碍(DP-07); 动态障碍(DP-08); COLREG(DP-09); 求解/失败(DP-10) | Step1 |
| TD-02 | SAC 自适应 MPC | 交付范围(DP-01); 策略角色(DP-11); 观测(DP-12); action/安全边界(DP-13); 奖励/训练(DP-14); sensitivity 梯度(DP-15); artifact/OOD(DP-16) | Step1 |
| TD-03 | Colav-Simulator 集成 | 身份(DP-02); 依赖(DP-03); 求解失败(DP-10); adapter 契约(DP-17); 能力与验收(DP-18) | Step1 |

### 0.3 盲区注册表 [BL]

| ID | 问题 | 归属决策点 | 优先级 | 调研状态 |
|----|------|-----------|--------|----------|
| BL-01 | 上游仓库未提供训练完成的 SAC checkpoint, 首次交付是否包含重新训练 | DP-01/DP-16 | 高 | 未闭环 |
| BL-02 | 上游固定参数 baseline 和 SAC-RLMPC 分别在哪些场景完成过可复现实验 | DP-18 | 高 | 未闭环 |
| BL-03 | 当前 Acados 版本能否稳定复现, 以及 macOS/Linux 运行差异 | DP-03/DP-10 | 高 | 未闭环 |
| BL-04 | 上游 stand-on 忽略直至 100 m 临界距离的策略是否满足本项目 COLREG 门 | DP-09 | 高 | 未闭环 |
| BL-05 | RL 调整 `r_safe_do`/COLREG 权重时如何保证硬安全约束不被弱化 | DP-13 | 高 | 未闭环 |
| BL-06 | 多目标验证是仅 Ship0-vs-target, 还是全船全局安全 | DP-18 | 高 | 未闭环 |

### 0.4 证据矩阵 [EV]

| ID | 来源类型 | 引用 | 检索置信 | 来源权威 | 场景适用 | 归属 |
|----|----------|------|----------|----------|----------|------|
| [R1] | DOMAIN_EVIDENCE | ACC 2024 RBF/NMPC 论文 | 高 | 高 | 高 | DP-05/DP-07/DP-10/DP-18 |
| [R2] | DOMAIN_EVIDENCE | 上游 RLMPC README | 高 | 中 | 高 | DP-01/DP-03/DP-11/DP-16 |
| [R3] | PROJECT_FACT | 上游 `rlmpc_cas.py`/mid-level MPC, commit `73ef4b8` | 高 | 中 | 高 | DP-04..DP-10 |
| [R4] | PROJECT_FACT | 上游 `action.py`/`policies.py`/`sac.py`, commit `73ef4b8` | 高 | 中 | 高 | DP-11..DP-15 |
| [R5] | PROJECT_FACT | 上游 scenarios/tests/artifacts, commit `73ef4b8` | 高 | 中 | 高 | DP-14/DP-16/DP-18 |
| [R6] | PROJECT_FACT | 当前 main capabilities/registry | 高 | 高 | 高 | DP-02/DP-03/DP-17/DP-18 |
| [R7] | PROJECT_FACT | 当前 legacy `AcadosMPCWrapper` | 高 | 高 | 高 | DP-01/DP-02/DP-10/DP-17 |
| [R8] | PROJECT_FACT | 当前严格 `CustomMPCAdapter` 契约 | 高 | 高 | 高 | DP-10/DP-16/DP-17 |
| [R9] | PROJECT_FACT | 本机 `.venv` dependency probe | 高 | 高 | 高 | DP-03 |
| [R10] | UNKNOWN | NotebookLM COLAV 查询因本地 SOCKS 依赖缺失失败 | 高 | 不适用 | 不适用 | Step1 调研完整性 |

### 0.5 场景注册表 [SC]

| ID | 场景描述 | 约束/边界 | 驱动决策点 |
|----|----------|-----------|-----------|
| SC-01 | 高细节 ENC 海岸附近轨迹跟踪与 anti-grounding | 论文仅 proof-of-concept; 约 3 km, 4 m/s | DP-05/DP-07/DP-10/DP-18 |
| SC-02 | 单目标 head-on | 动态目标, COLREG Rule 14 | DP-08/DP-09/DP-18 |
| SC-03 | 单目标 crossing give-way/stand-on | stand-on 边界需单独验证 | DP-08/DP-09/DP-18 |
| SC-04 | overtaking / being overtaken | Rule 13 状态保持与释放 | DP-08/DP-09/DP-18 |
| SC-05 | 受限水域 4-15 目标多船场景 | 上游存在配置, 无已交付 checkpoint/验收结果 | DP-08/DP-09/DP-14/DP-18 |
| SC-06 | 风流扰动和 noisy tracking | 上游场景存在, NMPC 对扰动/协方差利用边界未证实 | DP-08/DP-12/DP-14/DP-18 |
| SC-07 | 窄航道、近岸测量、靠泊 | 论文列为动机/未来适用方向, 不是已验证覆盖 | DP-07/DP-18 |
| SC-08 | 未见地图/未见交通密度的 OOD 推理 | 需要独立 safety guard 与退化策略 | DP-13/DP-16/DP-18 |

### 0.6 裁决注册表 [VR]

| ID | 裁决对象 | 结论 | 采纳/弃用 | 理由 | 时间 |
|----|----------|------|-----------|------|------|

### 0.7 备选/弃用方案 [ALT]

| ID | 方案 | 弃用理由 | 对比于 |
|----|------|----------|--------|

### 0.8 技术规约注册表 [TS]

| ID | 类别 | 规约内容 | 单位/定义 | 来源 | 关联DP/接口 | 与现状差异 |
|----|------|----------|-----------|------|-------------|-----------|

---

## 参考文献

- [R1] Tengesdal, Gros, Johansen, "Real-time Feasible Usage of Radial Basis Functions for Representing Unstructured Environments in Optimal Ship Control", ACC 2024, DOI 10.23919/ACC60939.2024.10644772; local PDF under `paper/`.
- [R2] `ntnu-itk-autonomous-ship-lab/rlmpc`, README, main commit `73ef4b8cc3850a7a3b007ec14d18b962d134be34`, inspected 2026-08-10.
- [R3] Same repository: `rlmpc/rlmpc_cas.py`, `rlmpc/mpc/mid_level/*`, `rlmpc/mpc/parameters.py`.
- [R4] Same repository: `rlmpc/action.py`, `rlmpc/policies.py`, `rlmpc/sac.py`, `rlmpc/rewards.py`.
- [R5] Same repository: `scenarios/`, `tests/`, `run_examples/`, `rlmpc/networks/models/`, `pyproject.toml`.
- [R6] Current checkout: `colav_simulator/experiment/capabilities.py`, `colav_simulator/integrations/registry.py`.
- [R7] Current checkout: `colav_simulator/guidance/custom_mpc_adapter.py`.
- [R8] Current checkout: `colav_simulator/core/colav/custom_mpc_adapter.py` and tests.
- [R9] 2026-08-10 local probe: Python 3.11.15; `rlmpc`, CasADi, Acados, Torch, Stable-Baselines3, RRT-Star and TensorFlow absent.
- [R10] 2026-08-10 NotebookLM `domain:colav_algorithms` query attempt; blocked before query by missing `socksio` in the NLM helper environment.

## 演进日志(append-only · 时序 · 不可覆盖)

### Step1 · 行业调研·发现决策点 [2026-08-10 13:25 CST]

- 模式判定: 重构/补全。main 已有 `rlmpc` capability、dependency probe、registry 直连和 legacy wrapper, 但没有当前严格 adapter 级真实集成。
- 快调来源: 当前 main 代码; 上游 GitHub main `73ef4b8`; ACC 2024 论文全文与图表; 上游 examples/scenarios/tests/artifacts; 本机 dependency probe。
- 核心事实: 论文研究对象是 TPS-RBF anti-grounding NMPC, 不是 SAC 强化学习论文。
- 核心事实: 上游 SAC-RLMPC 是未发表 WIP; 仓库没有训练完成的 SAC checkpoint, 只有 ENC/tracking VAE 权重。
- 核心事实: 上游 baseline NMPC 实现静态/动态障碍、HO/CR/OT 分组、路径/速度跟踪和 RRT warm start; 这等于代码能力, 不等于已通过本项目 G3/COLREG 验收。
- 新增决策点: DP-01..DP-18。
- 触发技术分解: TD-01 基线 NMPC; TD-02 SAC 自适应 MPC; TD-03 Colav-Simulator 集成。
- 调研限制: NotebookLM COLAV 域未返回内容, 原因记录为 [R10]; 不影响当前原始论文/源码事实, 但行业横向证据仍待 Step3 补充。
- 决策门: 等待用户确认 DP/TD 是否覆盖目标, 未进入 Step2, 未形成正式方案或实现。
