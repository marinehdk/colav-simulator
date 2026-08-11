# 设计日志: Mid-MPC L1/L2 Problem Assembler

> **模式**: 重构        **创建**: 2026-08-11
> **关联 spec**: `docs/superpowers/specs/2026-08-11-mid-mpc-l1-l2-problem-assembler-solution-pack.md`
> **状态**: Step6方案包已接受；已交付to-spec

## 0. 决策树状态(权威索引 · 可变快照)

### 0.1 决策点注册表 [DP]

| ID | 描述 | 类型 | 父/分解 | 状态 | 详见 |
|----|------|------|---------|------|------|
| DP-01 | Problem Assembler Module 的责任、Depth 与 Seam；排除 Encounter Lifecycle、IPOPT 数值求解、L4 解接受、GUI 映射 | 架构 | — | 已裁决 | VR-01 |
| DP-02 | OCP Problem Assembly 采用何种内部技术结构 | 技术 | TD-01 | 已裁决 | VR-02 |
| DP-03 | 从候选2 Encounter Lifecycle 接收何种 immutable decision facts；如何避免复制分类、锁定、释放逻辑 | 接口 | TD-01 | 已裁决 | VR-03 |
| DP-04 | Assembler 输出是语义级 `MidMpcProblem`、带证据的 `ProblemSnapshot`，还是直接暴露数值向量 | 接口 | TD-01 | 已裁决 | VR-04 |
| DP-05 | cycle/session/config/schema identity、输入 hash、幂等重试与确定性回放 contract | 接口 | TD-01 | 已裁决 | VR-05 |
| DP-06 | 坐标系、单位、角度 unwrap、速度语义、低速航向有效性与 route frame 的唯一归一化权威 | 约束 | TD-01 | 已裁决 | VR-06 |
| DP-07 | LOS 名义航线、已提交避让航向、回归航线之间的 reference construction 权责 | 架构 | TD-01 | 已裁决 | VR-07 |
| DP-08 | 多目标 admission、风险排序、active/monitor 优先级、16-target 容量与 fail-closed 行为 | 算法 | TD-01 | 已裁决 | VR-08 |
| DP-09 | 目标运动预测采用常速度、逐 stage 轨迹还是带不确定性 envelope；降级观测如何进入问题 | 算法 | TD-01 | 已裁决 | VR-09 |
| DP-10 | 预测时域/grid 与所有业务语义先按物理秒定义、再映射 stage；如何处理已知 k+1/k parity quirk | 约束 | TD-01 | 已裁决 | VR-10 |
| DP-11 | `cpa_safe`、`cpa_hard`、船体净距、点质点 node floor、离散步长 allowance 的独立语义和换算 | 约束 | TD-01 | 已裁决 | VR-11 |
| DP-12 | CPA/direction/min-alt/terminal row 的物理时间激活、reachability 与 ample-time schedule | 算法 | TD-01 | 已裁决 | VR-12 |
| DP-13 | heading/speed/ROT/decel/GNC 可跟踪能力边界是 live facts 还是静态配置；矛盾边界如何拒绝 | 接口 | TD-01 | 已裁决 | VR-13 |
| DP-14 | committed prefix 的来源、重投影、长度、hard/soft 语义、不可安全前缀的 fail-closed 处理 | 约束 | TD-01 | 已裁决 | VR-14 |
| DP-15 | cold seed、规则引导 seed、shifted primal/dual warm start 的生成、失效条件与 provenance | 算法 | TD-01 | 已裁决 | VR-15 |
| DP-16 | hard/soft row、slack class、slack 单位/作用域、prefix exception 与 terminal contract | 约束 | TD-01 | 已裁决 | VR-16 |
| DP-17 | L2 数值准备 `p/x0/lbx/ubx/lbg/ubg` 归 Assembler 公共 Interface，还是纯 IPOPT core 的私有 Implementation | 架构 | TD-01 | 已裁决 | VR-17 |
| DP-18 | assembly failure taxonomy：输入无效、容量超限、schedule 不可达、unsafe prefix、invariant 破坏；如何传给 no-fallback Adapter | 接口 | TD-01 | 已裁决 | VR-18 |
| DP-19 | LX evidence：规范化快照、target admission、constraint activation、bounds/slack、hash/reason 的统一 schema | 接口 | TD-01 | 已裁决 | VR-19 |
| DP-20 | Module contract 的验证矩阵：纯函数测试、MASS parity、OT/HO/CS、多船、容量、grid、prefix、坏边界与 replay | 架构 | TD-01 | 已裁决 | VR-20 |

### 0.2 技术分解注册表 [TD]

| ID | 技术 | 分解子模块(→DP) | 触发步骤 |
|----|------|------------------|----------|
| TD-01 | OCP Problem Assembly | lifecycle handoff(DP-03) → semantic snapshot(DP-04/DP-05) → normalization/reference(DP-06/DP-07) → target prediction/admission(DP-08/DP-09) → grid/safety/schedule(DP-10..DP-12) → capability/prefix/seed(DP-13..DP-15) → hard-soft/slack(DP-16) → numerical preparation seam(DP-17) → failure/evidence/verification(DP-18..DP-20) | Step1 |

### 0.3 盲区注册表 [BL]

| ID | 问题 | 归属决策点 | 优先级 | 调研状态 |
|----|------|-----------|--------|----------|
| BL-01 | 候选2的 `EncounterDecisionSnapshot` 尚未冻结，Assembler 需要稳定最小 handoff 而非抢先固化其全部 schema | DP-03/DP-05 | 高 | 已闭环 |
| BL-02 | 当前 facade 同时生成 route、target selection、schedule、safety allowance 与 `MidMpcProblem`，没有可单独 replay 的 assembly transaction | DP-01/DP-04/DP-05 | 高 | 已闭环 |
| BL-03 | 当前 15s grid 只检查 node CPA；连续区间穿越风险和 frozen k+1/k 索引补偿仍由 facade 隐式承担 | DP-10/DP-11/DP-12 | 高 | 已闭环 |
| BL-04 | `cpa_hard_m` 当前由 hull radii 加 own-step allowance 转换；这个换算是保守 envelope 还是 parity 补丁尚未形成可审计 contract | DP-11 | 高 | 已闭环 |
| BL-05 | 当前 `lateral_active` 只绑定 newly-committed cycle；constraint activation 与持续 commitment 的真实物理时间语义耦合不清 | DP-03/DP-12 | 高 | 已闭环 |
| BL-06 | PlannerInput 没有完整保留 MASS 文档中的 live manoeuvrability/reachability facts；静态 YAML 是否足够尚未证明 | DP-13 | 高 | 已闭环(含UNKNOWN) |
| BL-07 | 当前 prefix 字段存在于 core model/parity corpus，但 Colav runtime 尚未给出统一来源、shift、reset 和安全见证 | DP-14/DP-15 | 高 | 已闭环 |
| BL-08 | 当前运行时明确 `warm_start_used=False`；80×15s IPOPT 重求解是否需要 warm start 尚无本项目测量 | DP-15 | 中 | 已闭环 |
| BL-09 | frozen core 的 CPA slack 使用平方距离量纲，不能与米制 hull clearance 或 UI 数值直接比较 | DP-11/DP-16/DP-19 | 高 | 已闭环 |
| BL-10 | 语义 `ProblemSnapshot` 与数值 `PreparedProblem` 若同一公共 Interface，会把 CasADi/IPOPT row layout 泄漏到 L1；若完全分开，又需防止 L2 静默改题 | DP-04/DP-17 | 高 | 已闭环 |
| BL-11 | NLM `colav_algorithms` 快调因本机缺少 `socksio` 未执行；Step3 需用一手资料补足 domain evidence，不修改知识库 | DP-09..DP-17 | 中 | 已闭环(替代证据) |
| BL-12 | MASS 7层文档包含 acados、ROS/GNC/M4/M6、1852m 等专项目约束；哪些仅作架构反例，哪些适用于 Colav 未裁决 | DP-01/DP-11..DP-17 | 高 | 已闭环 |
| BL-13 | 当前 Adapter/SimulationSession 未提供明确 session epoch、monotonic cycle ID 与 retry identity；authority 和 legacy migration 需补齐 | DP-05 | 高 | 已闭环 |
| BL-14 | frozen reduced model 使用 heading+surge，真实 ENU 速度含 sway；允许的 model-mismatch/低速 validity 阈值没有 Colav ODD 证据 | DP-06/DP-13 | 高 | 已闭环(含UNKNOWN) |
| BL-15 | frozen core 的 route objective 只有单 bearing/line；当前 route-frame origin 每周期重置为本船，无法表达原航线 cross-track/rejoin 或 horizon 内曲线路径 | DP-07 | 高 | 已闭环(含UNKNOWN) |
| BL-16 | monitor target admission 的 risk ranking 需结合 lifecycle urgency、预测首次安全包络违反与不确定性；具体 metric/tie tolerance 未有本项目证据 | DP-08/DP-09 | 高 | 已闭环(含UNKNOWN) |
| BL-17 | target slot 在风险排序抖动时会 churn；cold canonical order 与 future warm-start slot preservation 的一致 contract 尚未确定 | DP-08/DP-15 | 中 | 已闭环 |
| BL-18 | 4x4 track covariance 如何传播为每stage位置envelope、采用何种confidence multiplier，以及global CPA floor如何容纳per-target margin | DP-09/DP-11 | 高 | 已闭环 |
| BL-19 | `TrackedObstacle.state_enu` 是measurement-time还是cycle-time state；age/coasting时是否已由tracker外推，当前contract未显式 | DP-09 | 高 | 已闭环(含UNKNOWN) |
| BL-20 | 1200s constant-velocity prediction对真实maneuvering target的有效ODD/刷新阈值未知；当前只被God定速场景验证 | DP-09/DP-20 | 高 | 已闭环(含UNKNOWN) |
| BL-21 | 不同业务schedule的物理时间→stage映射需要区分“首个不早于”与“最迟不得晚于”等安全语义；统一floor/ceil会产生一stage偏差 | DP-10/DP-12 | 高 | 已闭环 |
| BL-22 | frozen own-state `k+1` 对 target `k` 的 CPA row 物理错时15s；当前one-step allowance是否对全部相对速度/方位保守尚未证明 | DP-10/DP-11 | 高 | 已闭环 |
| BL-23 | 业务 required hull clearance 目前无法被 frozen global CPA row 真正表示：per-target/time-varying floor缺失，且suffix CPA row可被global m² slack放松 | DP-11/DP-16 | 高 | 已闭环 |
| BL-24 | robust reachability需 live `T_chi/r_max/current r/speed/decel` 或可验证surrogate；当前PlannerInput能力facts不足 | DP-12/DP-13 | 高 | 已闭环(含UNKNOWN) |
| BL-25 | early/substantial action 的 latest-achievement deadline无通用COLREG数值；必须由独立Planner ODD/Lifecycle提供 | DP-12 | 高 | 已闭环 |
| BL-26 | 当前global `MidMpcRowSchedule`不能表达per-target REQUIRED hard CPA与MONITOR soft-only；扩展bounds layout的parity/测试面待研究 | DP-12/DP-16/DP-17 | 高 | 已闭环 |
| BL-27 | active Ship/model 的 `T_chi/T_U/r_max/accel/decel/GNC limits` 如何进入共享 PlannerInput 而不污染其他算法 Interface | DP-13 | 高 | 已闭环(含UNKNOWN) |
| BL-28 | heading+surge reduced model 的stage-wise robust reachable envelope及其与真实GNC trackability的保守关系未有本项目oracle | DP-12/DP-13 | 高 | 已闭环(含UNKNOWN) |
| BL-29 | 实测状态落在algorithm search window之外但仍在plant absolute limits内时，应fail还是生成受控recovery corridor | DP-13 | 中 | 已闭环(含UNKNOWN) |
| BL-30 | 当前CustomMPCAdapter是否存在不可撤销多步command queue/latency commitment；若只有held reference，runtime prefix应为0还是1尚需执行链证据 | DP-14 | 高 | 已闭环 |
| BL-31 | commitment duration非15s整数倍时，frozen whole-stage prefix用floor会漏承诺、ceil会过度冻结；partial-stage不可表示 | DP-14 | 高 | 已闭环 |
| BL-32 | committed prefix safety witness应使用reduced kinematics还是实际Ship/GNC rollout，及其保守误差边界未知 | DP-14/DP-20 | 高 | 已闭环(含UNKNOWN) |
| BL-33 | prefix后必须保留多少可控suffix stages才能形成有效避让问题，当前无Colav ODD最小值 | DP-14 | 中 | 已闭环(含UNKNOWN) |
| BL-34 | solve period 5s与prediction grid 15s不整除；previous accepted primal如何连续时间resample及允许多大execution deviation | DP-15 | 高 | 已闭环(含UNKNOWN) |
| BL-35 | target set/row schedule变化时dual multiplier remap是否稳定、是否真正降低IPOPT latency，当前无benchmark | DP-15/DP-17 | 中 | 已闭环(含UNKNOWN) |
| BL-36 | rule-guided feasible seed如何在prefix/stage bounds/rate limits下生成且不预先编码场景特例 | DP-15 | 中 | 已闭环 |
| BL-37 | 保留frozen slack variables但在production将ub固定0，对IPOPT收敛/conditioning及8条parity fixture graph identity的影响需benchmark | DP-16/DP-17 | 中 | 已闭环(含UNKNOWN) |
| BL-38 | node hard rows即使true-hard仍不能替代同步continuous hull witness；两者容差/拒绝关系需L4 contract闭环 | DP-11/DP-16/DP-20 | 高 | 已闭环 |
| BL-39 | raw constraint units混合(rad、m/s、m²、m)，单一IPOPT feasibility tolerance如何映射成各业务物理容差 | DP-16/DP-19 | 高 | 已闭环 |
| BL-40 | graph shape当前依target count/audit rows/slack config变化；structural signature、graph cache与prepared layout manifest如何一致需L3性能证据 | DP-17 | 中 | 已闭环 |
| BL-41 | stage-wise bounds、per-target row schedule、strict slack ub=0加入后，如何同时保持8条oracle prepared-vector parity与production invariants | DP-16/DP-17/DP-20 | 高 | 已闭环 |
| BL-42 | shared `PlanStatus`缺少UNSUPPORTED_ODD/POLICY_CONFLICT/CAPACITY等细粒度状态；需用detail code保真且避免扩大全局enum blast radius | DP-18/DP-19 | 中 | 已闭环 |
| BL-43 | actual solve失败后SimulationSession应停止、暂停还是只拒绝本周期command；当前no-fallback runtime行为需端到端证据 | DP-18/DP-20 | 高 | 已闭环 |
| BL-44 | 哪些assembly failure只需新cycle重试，哪些必须reset/profile修复；recoverability matrix尚未定义 | DP-18 | 中 | 已闭环 |
| BL-45 | 81×16 prediction、逐row evidence与prepared vectors的trace体积/retention/artifact storage预算未知 | DP-19 | 中 | 已闭环(含UNKNOWN) |
| BL-46 | dedicated Mid-MPC evidence schema如何嵌入现有PlannerTrace 1.0而不破坏其他算法与GUI兼容 | DP-19 | 高 | 已闭环 |
| BL-47 | GUI应展示哪些inline摘要、哪些full artifact按需加载；现有target prediction key mismatch与Mid objective隐藏需端到端修复 | DP-19/DP-20 | 中 | 已闭环 |
| BL-48 | 80×15 strict profile在single/multiship与16-target adversarial下的p50/p95/max latency和memory预算未知 | DP-15/DP-17/DP-20 | 中 | 已闭环(含UNKNOWN) |
| BL-49 | candidate L4 Acceptance Gate尚未冻结；Assembler tests需要稳定的independent continuous witness seam而不能复制evaluator实现 | DP-11/DP-20 | 高 | 已闭环(含UNKNOWN) |

### 0.4 证据矩阵 [EV]

| ID | 来源类型 | 引用 | 检索置信 | 来源权威 | 场景适用 | 归属 |
|----|----------|------|----------|----------|----------|------|
| [R1] | PROJECT_FACT | 当前 Colav facade/core models/solver | 高 | 高 | 高 | DP-01..DP-20 |
| [R2] | PROJECT_FACT | 当前 parity、core、integration、single/multiship tests | 高 | 高 | 高 | DP-08..DP-20 |
| [R3] | DOCUMENTED_INTENT | 用户提供的 M5 七层架构文档 | 高 | 中高 | 中高 | DP-01/DP-02/DP-10..DP-19 |
| [R4] | PROJECT_FACT | GitLab `l3-tdl@4c8ff3bd` pure input builder、row registry、solver | 高 | 高 | 中高 | DP-01/DP-04/DP-10..DP-18 |
| [R5] | DOCUMENTED_INTENT | 候选2 Encounter Lifecycle 设计日志当前已确认 handoff 方向 | 高 | 中 | 高 | DP-03/DP-05/DP-08/DP-18/DP-19 |
| [R6] | PRIMARY_DOC | CasADi 官方 NLP/OCP、参数、bounds、primal/dual warm-start contract | 高 | 高 | 高 | DP-04/DP-10/DP-15/DP-17 |
| [R7] | PRIMARY_PAPER | Eriksen & Breivik Mid-level MPC/NLP | 高 | 高 | 高 | DP-07/DP-09..DP-12/DP-16 |
| [R8] | PRIMARY_PAPER | Eriksen et al. Hybrid COLAV Rule 8/13–17 | 高 | 高 | 中高 | DP-03/DP-07/DP-12/DP-20 |
| [R9] | PRIMARY_PAPER | Johansen et al. scenario-based predictive hazard assessment | 高 | 高 | 中 | DP-08/DP-09/DP-19/DP-20 |
| [R10] | ACCEPTED_DESIGN | 候选2已接受Step6方案包的Cycle/Snapshot/AggregateDirective/L1 handoff规约 | 高 | 高 | 高 | DP-03/DP-05/DP-08/DP-12/DP-18 |
| [R11] | PROJECT_FACT | `CustomMPCAdapter` 当前PlannerInput、reset、solve/hold与trace执行链 | 高 | 高 | 高 | DP-05/DP-13/DP-14/DP-18/DP-19 |
| [R12] | PROJECT_FACT | `Ship.plan`已产生T_chi/T_U/r_max kwargs，但`_planner_input`未写入PlannerInput | 高 | 高 | 高 | DP-13 |
| [R13] | PROJECT_FACT | 当前`MidMpcProblem→_prepare→MidMpcPreparedProblem`语义与数值packing责任分布 | 高 | 高 | 高 | DP-04/DP-15/DP-16/DP-17 |
| [R14] | PROJECT_FACT | `SimulationSession._advance`异常转FAILED；`PlanStatus`/`FailureSource`与`ColavExecutionError.details`现有合同 | 高 | 高 | 高 | DP-18/DP-20 |
| [R15] | PROJECT_FACT | `PlannerTrace 1.0`自由字典与GUI server prediction/target projection当前消费合同 | 高 | 高 | 高 | DP-19/DP-20 |
| [R16] | PROJECT_FACT | frozen CPA row、continuous CPA checker、global node-floor conversion与15s grid源码 | 高 | 高 | 高 | DP-10/DP-11/DP-16/DP-20 |
| [R17] | PROJECT_FACT | KinematicCSOG plant、God/KF tracker cycle-time prediction与CV covariance model | 高 | 高 | 高 | DP-06/DP-09/DP-12/DP-13 |
| [R18] | PRIMARY_PAPER | Eriksen/Breivik原始Mid-level MPC的moving-obstacle/OCP/grid/warm-start实验边界 | 高 | 高 | 中 | DP-09/DP-10/DP-15/DP-20 |
| [R19] | PRIMARY_STANDARD | IMO COLREG Rule 8/13–17文本：ample time/safe distance/early-substantial但无统一数值 | 高 | 高 | 高 | DP-03/DP-11/DP-12 |
| [R20] | PRIMARY_DOC | IPOPT官方constraint violation与NLP scaling语义 | 高 | 高 | 高 | DP-16/DP-17/DP-19 |
| [R21] | PRIMARY_DOC | SciPy官方chi-square PPF/interval合同；confidence数值仍属Planner ODD选择 | 高 | 高 | 中 | DP-09/DP-11 |
| [R22] | DERIVED_PROOF | exact frozen方程上的错时补偿与node-only连续穿越反例 | 高 | 高 | 高 | DP-10/DP-11/DP-20 |
| [R23] | PROJECT_FACT | prefix/row bounds/cold seed/graph construction与8条frozen parity fixture | 高 | 高 | 高 | DP-14..DP-17/DP-20 |
| [R24] | PRIMARY_DOC | IPOPT warm-start、same-structure、fixed-variable与bound-relax官方合同 | 高 | 高 | 高 | DP-15..DP-17 |
| [R25] | PRIMARY_PAPER | 原始Mid-level MPC以前次解初始化及其reported latency | 高 | 高 | 中 | DP-15/DP-20 |
| [R26] | EXPERIMENT | Apple M3本地80×15 cold/cache/primal-seed/strict-slack微基准 | 高 | 中高 | 中 | DP-15..DP-17/DP-20 |
| [R27] | DERIVED_PROOF | 5s solve与15s piecewise-constant control grid的绝对时间重采样/prefix表达边界 | 高 | 高 | 高 | DP-14/DP-15 |
| [R28] | COMPARATIVE_PROJECT_FACT | MASS七层文档、GitLab当前pure builder/row registry与Colav当前Interface逐层责任对照 | 高 | 高 | 高 | DP-01/DP-02/DP-17/DP-20 |
| [R29] | PROJECT_FACT | frozen `_route_cost/_cross_track_all`单直线参考与facade每周期local-origin/commitment-bearing装配 | 高 | 高 | 高 | DP-07/DP-18/DP-20 |
| [R30] | PROJECT_FACT+DERIVED_CONTRACT | 当前TCPA/DCPA/range/id截断顺序、Lifecycle全量事实与确定性分层admission合同 | 高 | 高 | 高 | DP-03/DP-08/DP-09 |
| [R31] | PROJECT_FACT+DERIVED_CONTRACT | `SimulationSession` fail-stop行为与assembly failure remediation/恢复权限矩阵 | 高 | 高 | 高 | DP-05/DP-18/DP-20 |
| [R32] | EXPERIMENT | 当前worktree 80×15/16-target真实IPOPT结果构造full artifact与inline summary的JSON/gzip体积测量 | 高 | 中高 | 中高 | DP-19/DP-20 |
| [R33] | PROJECT_FACT | solver point-center continuous CPA、public plan validation与独立Evaluator hard-gate当前责任边界 | 高 | 高 | 高 | DP-11/DP-18/DP-20 |
| [R34] | EVIDENCE_SUBSTITUTION | NLM缺少`socksio`未运行；以当前源码、官方CasADi/IPOPT/IMO/SciPy文档及原始论文替代，未修改知识库 | 高 | 高 | 高 | DP-09..DP-17 |

### 0.5 场景注册表 [SC]

| ID | 场景描述 | 约束/边界 | 驱动决策点 |
|----|----------|-----------|-----------|
| SC-01 | 无目标 route-only | 80×15s；不得凭空激活 COLREG rows | DP-04/DP-07/DP-10/DP-12 |
| SC-02 | HO/CS give-way/OT 已提交避让 | lifecycle facts 已锁；Assembler 不得重分类或改侧 | DP-03/DP-07/DP-12/DP-20 |
| SC-03 | CS stand-on/overtaken monitor | 先维持；仅明确升级后进入 active optimization | DP-03/DP-08/DP-12 |
| SC-04 | 多目标冲突 | 先全量 lifecycle，再 aggregate，再 admission；active 不可静默丢失 | DP-03/DP-08/DP-18 |
| SC-05 | 恰好16目标与第17个 active 目标 | `16` 可装配；`>16 active` 显式容量失败 | DP-08/DP-18/DP-20 |
| SC-06 | 15s 粗网格近距离交汇 | node 可行但 swept CPA 可能不安全 | DP-10/DP-11/DP-12/DP-20 |
| SC-07 | 已执行 committed prefix | shift/reproject 后 prefix 仍需 hard safety witness | DP-14/DP-15/DP-16 |
| SC-08 | 低速、航向无效、目标观测老化 | 不能用任意 COG/heading 填充后继续求解 | DP-06/DP-09/DP-18 |
| SC-09 | live bounds 不一致或 schedule 物理不可达 | assembly fail-closed；不得交给 IPOPT 猜 | DP-12/DP-13/DP-18 |
| SC-10 | 相同输入重放 | snapshot/hash/target order/prepared vectors 确定一致 | DP-05/DP-19/DP-20 |

### 0.6 裁决注册表 [VR]

| ID | 裁决对象 | 结论 | 采纳/弃用 | 理由 | 时间 |
|----|----------|------|-----------|------|------|
| VR-01 | DP-01 | 深 Module 消费 validated PlannerInput + immutable lifecycle facts；拥有 L1 OCP 语义及确定性 L2 准备；不拥有 lifecycle、Adapter authority、IPOPT、L4、MPCSolution/GUI mapping | 采纳(final) | 高 Depth、窄 Interface；让 assembly 可独立测试/replay，保留 frozen core | Step4 |
| VR-02 | DP-02 | 采用单个深 Module、一个窄 public Interface、私有 typed immutable staged pipeline；assembly 原子完成，失败不返回部分问题 | 采纳(final) | 避免巨型函数继续混责，也避免每阶段 public micro-module 与中间格式扩散 | Step4 |
| VR-03 | DP-03 | Assembler 消费同 epoch/cycle/time 的原子 immutable lifecycle snapshot；含全量逐目标 identity/observation/policy/evidence 与 aggregate directive；Lifecycle 不按16截断，Assembler 不重判 lifecycle | 采纳(final) | 防止时序拼接、ID复用、双 COLREG authority 与静默容量丢失 | Step4 |
| VR-04 | DP-04 | public Interface 返回 immutable `AssemblyOutcome`；成功含 semantic `MidMpcProblemSnapshot` + bindings/plans/evidence，失败含 typed reason 且无部分 problem；不公开 positional numerical vectors | 采纳(final) | 兼顾可 replay/audit 与 core layout encapsulation；避免上层依赖 CasADi/IPOPT slots | Step4 |
| VR-05 | DP-05 | 分离 cycle instance identity 与 semantic content identity；Session/Adapter 提供 epoch+cycle，Assembler验证并计算 versioned canonical request/problem hashes；retry复用同一snapshot | 采纳(final) | 防止reset/time重复、配置漂移、随机retry identity与同周期异题 | Step4 |
| VR-06 | DP-06 | 固定 ENU/SI/rad、North/East local OCP、navigation angle clockwise-from-North/starboard-positive；显式分离 physical heading/surge/sway 与 frozen reduced heading+surge；目标由 ENU velocity pack COG/SOG | 采纳(final) | 保持 MASS parity，同时消除 sway、COG/heading、atan2、wrap 与大坐标语义漂移 | Step4 |
| VR-07 | DP-07 | L0 existing LOS/Route Adapter 产生 nominal reference，Lifecycle产生 maneuver directive，stateless Assembler只编译 OCP reference；nominal/commit/recovery anchor 跨周期有明确来源，不再每周期重锚本船 | 采纳(final) | 避免retry状态漂移、固定5度双authority与route cost丢失cross-track/rejoin | Step4 |
| VR-08 | DP-08 | 全量target先分REQUIRED/ELIGIBLE/EXCLUDED；所有REQUIRED必入，超过16显式CAPACITY_EXCEEDED；仅时域内有interaction的ELIGIBLE按risk补槽；cold slot按typed identity canonical绑定 | 采纳(final) | 消除静默截断、out-of-horizon HOLD不稳定、输入排列依赖与primary target控制偏置 | Step4 |
| VR-09 | DP-09 | v1仅支持 frozen-parity deterministic CV mean；Assembler生成同源stage/continuous prediction与covariance envelope供admission/safety/L4/GUI，IPOPT仍收等价CV参数；不宣称maneuvering-target鲁棒 | 采纳(final) | 保持上游方程parity，同时让timestamp、uncertainty与真实能力边界可审计 | Step4 |
| VR-10 | DP-10 | `N=80,dt=15s`定义80区间/81状态时刻；业务schedule仅用物理秒和显式mapping policy；同步安全轴与frozen k+1/k parity轴并存并标证据；下游轨迹prepend x0而不覆盖首优化点 | 采纳(final) | 消除裸k、grid变化、UI时间标签和own/target错时被隐藏 | Step4 |
| VR-11 | DP-11 | 分离required/preferred hull clearance、per-target center distance、frozen global node floor、m² slack与actual swept hull witness；50m为项目hard gate、150m为soft aspiration；不可表示的envelope fail-closed | 采纳(final) | 防止点中心/船体、hard/soft、m/m²和node/continuous安全claim混淆 | Step4 |
| VR-12 | DP-12 | 采用per-row/per-target physical-time activation plan；capability/prefix全程hard，REQUIRED CPA从可控suffix持续，MONITOR仅soft barrier；COURSE direction/min-alt持续到Lifecycle release并按robust reachability/deadline映射 | 采纳(final) | 消除newly-committed闪现、TCPA裸k延迟、stand-on偷转与不可达约束伪装 | Step4 |
| VR-13 | DP-13 | plant、GNC trackability、MidMPC ODD三类能力分离并逐stage取交集；产出stage-wise heading/speed/rate envelope；缺失/空交集/unsupported action显式失败，禁止YAML或0.08隐式plant default | 采纳(final) | 让IPOPT variable feasibility对应真实可达/可跟踪域，而非静态box | Step4 |
| VR-14 | DP-14 | prefix仅表示不可撤销execution commitment，previous optimum仅作warm start；prefix必须先通过capability+continuous hull witness再hard equality，runtime无执行证据时K=0；partial stage禁止静默floor | 采纳(final) | 防止旧计划锁死、unsafe prefix被row disable/slack吞掉与5s/15s承诺错配 | Step4 |
| VR-15 | DP-15 | Assembler stateless，PreviousAcceptedPlan由orchestrator显式传入；valid warm primal按绝对时间从5s重采样到15s grid并投影stage envelope，否则生成directive-guided deterministic cold seed；dual v1 disabled | 采纳(final) | 避免旧episode/L4拒绝解/错误index shift污染，同时保留可审计数值初始化 | Step4 |
| VR-16 | DP-16 | 分离MASS_PARITY与COLAV_STRICT profile；production保留frozen graph/layout但将global CPA/direction slack ub固定0；hard row不得可松弛，monitor/150m/route等仅作soft objective；prefix安全外部验证 | 采纳(final) | 在保持graph topology/parity研究路径同时恢复真实hard语义并消除m²/m/rad slack混淆 | Step4 |
| VR-17 | DP-17 | Assembler拥有L2 semantic preparation plan；private core NumericalPreparer唯一拥有positional layout/packing并与graph共享layout authority；integration不传prepared arrays绕过校验 | 采纳(final) | 防止offset双实现和core隐藏policy，同时保留prepared-vector parity diagnostics | Step4 |
| VR-18 | DP-18 | expected assembly domain failures返回typed `AssemblyFailure`，含layer/code/status/source/identity/recoverability/evidence；Adapter只传播，不调用其他算法、不把last plan/默认控制包装成功 | 采纳(final) | 保持失败责任与可复现证据，落实用户no-fallback要求 | Step4 |
| VR-19 | DP-19 | 采用versioned hash-linked evidence链：Problem→Prepared→RawSolver→Acceptance；planner event仅内联稳定摘要，full grids/rows/vectors存artifact；GUI只消费typed render section，不重算轨迹 | 采纳(final) | 统一replay/trace/UI事实源，修复字段漂移同时控制payload体积 | Step4 |
| VR-20 | DP-20 | 采用六层验证门：A纯Assembler对抗测试、B frozen MASS parity、C COLAV_STRICT生产约束、D HO/CS-GW/CS-SO/OT/overtaken/multiship闭环、E真实8010事件与81点轨迹、F全量回归；Ship0连续船体净距≥50m、真实IPOPT、无fallback、strict slack=0、侧向/通过/recovery正确；目标船脚本互撞保留证据但不作为Ship0 Mid-MPC失败 | 采纳(final) | 分离数学等价、生产hard语义、闭环行为、运行时/UI与全仓回归证据，避免单一G3或solver success过度外推 | Step4 |
| VR-21 | CARD-01 / DP-01..DP-05、DP-17、DP-18 | 采用Deep Semantic Assembler + Private Numerical Codec：单一`assemble(request)->AssemblyOutcome`，私有typed stages，semantic snapshot/named preparation plan可审计，positional layout只由core私有codec拥有；candidate2临时bridge必须迁移删除 | 采纳(final) | 唯一同时满足高Module Depth、窄接口、semantic replay、private layout、typed fail-closed与frozen parity | Step5 |
| VR-22 | CARD-02 / DP-06..DP-16 | 采用Explicit Physical Semantics + COLAV_STRICT：ENU/SI/rad、81点0..1200s、统一target admission/prediction、50m同步船体hard、物理时间activation、stage capability、K=0、validated seed；保留独立MASS_PARITY profile，禁止HO/CS/OT场景Builder | 采纳(final) | 同时保留数学parity与生产hard语义，所有场景共享可审计物理装配规则 | Step5 |
| VR-23 | CARD-03 / DP-19..DP-20 | 采用Hash-Linked Tiered Evidence + Six Gates：`lifecycle/assembly/solver/acceptance`独立namespace，在线摘要≤8KiB，full gzip artifact，typed GUI projection；Assembler/parity/strict/closed-loop/8010/full regression六Gate不可互相替代 | 采纳(final) | 在可观测性、可重放、claim边界和运行成本间形成明确分层 | Step5 |

### 0.7 备选/弃用方案 [ALT]

| ID | 方案 | 弃用理由 | 对比于 |
|----|------|----------|--------|
| ALT-01 | 继续扩展`_MidMpcFacade.solve`承载全部装配 | 职责混杂，无法独立replay/测试assembly，继续耦合Lifecycle与结果映射 | DP-01 |
| ALT-02 | 将装配拆成多个public微模块/流水线 | 中间DTO和调用顺序扩散为公共API，降低Module Depth与原子性 | DP-01 |
| ALT-03 | 将业务装配全部下沉到`MidMpcIpoptSolver._prepare` | Lifecycle/ODD/hard-soft policy污染数值Core与frozen parity | DP-01 |
| ALT-04 | 单个巨型`assemble`函数直接构造全部字段 | public seam虽窄，内部不变量、单位、failure owner仍混成一体 | DP-02 |
| ALT-05 | Stateful fluent builder逐步`set_*`再`build()` | 调用顺序、缺字段、跨cycle残留和retry mutation成为隐式状态 | DP-02 |
| ALT-06 | Event/plugin stage registry | 当前无第三方stage或第二实现需求，动态顺序与扩展点增加不可见行为 | DP-02 |
| ALT-07 | Assembler只接收`AggregateDirective` | 丢失逐目标identity、health、required/monitor、release与constraint provenance | DP-03 |
| ALT-08 | Assembler接收raw tracks并重跑分类/policy | 形成第二COLREG authority，可推翻Lifecycle lock/Rule17/release | DP-03 |
| ALT-09 | Assembler注入并调用stateful`EncounterLifecycle` | retry会推进或重复transition/event，破坏幂等与atomic handoff | DP-03 |
| ALT-10 | Public直接返回bare`MidMpcProblem`/transitional wrapper | 无失败union、identity/hash、provenance和完整下游证据 | DP-04 |
| ALT-11 | Public直接暴露`MidMpcPreparedProblem`数值向量 | positional layout泄漏L3并把上层绑定到fixture/backend slots | DP-04 |
| ALT-12 | Expected assembly failure仅抛异常字符串 | 丢失recoverability、identity、owner与machine-readable evidence | DP-04 |
| ALT-13 | 仅用`solve_id+sim_time`作assembly identity | reset复用、time rewind、同周期异题和跨session碰撞无法区分 | DP-05 |
| ALT-14 | request/cycle/problem/artifact共用一个总hash | 无法区分运行实例、业务语义、配置漂移与存储位置变化 | DP-05 |
| ALT-15 | 每次assembly使用随机UUID或墙钟hash | retry不幂等，replay/golden/cache全部失效 | DP-05 |
| ALT-16 | 用own COG/SOG替代frozen core的`psi/u` | 改变MASS方程、rate/decel语义与parity，sway时尤其错误 | DP-06 |
| ALT-17 | 将body surge/sway直接当作North/East速度 | 忽略heading rotation，CPA/geometry/control mapping错误 | DP-06 |
| ALT-18 | 各angle/bound独立wrap到`[-pi,pi]` | ±pi附近连续corridor会翻转成空集或超大区间 | DP-06 |
| ALT-19 | COMMITTED时用commit course覆盖route bearing和route frame | 原航线cross-track/rejoin丢失，优化长期沿新直线 | DP-07 |
| ALT-20 | 始终只给Core nominal LOS reference | hard direction与heading objective持续对抗，弱化明显动作并损害conditioning | DP-07 |
| ALT-21 | Assembler内部持有stateful LOS/recovery limiter | retry/reference不幂等，reset/route/Lifecycle authority再次混入 | DP-07 |
| ALT-22 | 按当前TCPA/DCPA/range排序后直接截前16 | REQUIRED可能静默丢失，membership与slot binding耦合 | DP-08 |
| ALT-23 | NLP只装REQUIRED，不纳入ELIGIBLE monitor | 无soft提前塑形，commit threshold附近目标突然进入问题 | DP-08 |
| ALT-24 | 按tracker输入顺序并padding固定16 slots | 输入排列改变hash/vector，padding破坏frozen layout并产生虚假目标 | DP-08 |
| ALT-25 | 延续80点轨迹并混用`t=0..1185`/`t=15..1200`标签 | 与80 interval/81 state不一致，首段或终点缺失 | DP-09 |
| ALT-26 | CV mean传播但covariance/margin固定不变 | horizon越远仍显示当前精度，形成虚假长期确定性 | DP-09 |
| ALT-27 | 本轮新增交互/MMG/多模型目标预测 | 无目标控制/辨识authority与oracle，超出纯Mid-MPC验证范围 | DP-09 |
| ALT-28 | Public继续80列并用实测状态覆盖首优化列 | 丢失15s优化点，终点/标签错误 | DP-10 |
| ALT-29 | 所有physical schedule统一floor/ceil成裸stage | activation/deadline/prefix不同语义产生一stage偏差 | DP-10 |
| ALT-30 | 本轮直接修frozen own(k+1)/target(k) CPA方程 | 破坏MASS parity，需独立formulation id与oracle corpus | DP-10 |
| ALT-31 | 继续用own最大一步位移补偿frozen CPA错时 | target更快时不保守，已存在同步距离反例 | DP-11 |
| ALT-32 | 将`cpa_hard_m=50`直接解释为船体净距 | 实际仅中心距，遗漏双方船体与不确定性 | DP-11 |
| ALT-33 | 仅依赖15s node CPA rows | 区间中点可碰撞且现有checker漏首段 | DP-11 |
| ALT-34 | 用`floor(min TCPA/dt)-2`统一激活CPA | 无reachability/deadline语义且一个目标控制全部rows | DP-12 |
| ALT-35 | direction/min-alt只在`newly_committed`cycle激活 | 后续约束消失，commitment回摆 | DP-12 |
| ALT-36 | 所有hard rows从k0强开，不可达时soften | 物理不可达被误报infeasible或hard安全被slack吞掉 | DP-12 |
| ALT-37 | 继续只用YAML静态rate/decel/speed/window | 无active Plant/GNC authority，运行状态变化时静默错误 | DP-13 |
| ALT-38 | 只取三类global min/max并广播全horizon | 忽略Tchi/TU/current state/slew/latency，早期stage虚假可达 | DP-13 |
| ALT-39 | 用frozen core自身rate/decel row证明Plant/GNC能力 | reduced surrogate反向证明自身，形成循环论证 | DP-13 |
| ALT-40 | 因5s hold/solve period固定设置prefix K=1 | held reference可替换且不足完整15s，不是不可撤销command | DP-14 |
| ALT-41 | partial commitment统一ceil/floor到whole stage | ceil过冻，floor漏承诺，均改变执行事实 | DP-14 |
| ALT-42 | 将PreviousAcceptedPlan前若干点转成prefix equality | 可撤销优化建议被错误锁死，旧episode/side污染新问题 | DP-14 |
| ALT-43 | 每次只广播current heading/speed作cold seed | 正确但浪费accepted trajectory连续性与已测primal leverage | DP-15 |
| ALT-44 | 旧raw x数组直接shift一个15s stage | 实际elapsed=5s，时间错10s且无angle/capability投影 | DP-15 |
| ALT-45 | v1立即启用primal+dual full warm start | dual绑定row order，graph每次重建且无真实场景稳定性benchmark | DP-15 |
| ALT-46 | 保留可用slack并只提高L1/L2 penalty | penalty不能使row变hard，global mixed-unit slack仍隐藏违反 | DP-16 |
| ALT-47 | Production删除slack variables | 改graph/layout/indices，破坏frozen parity与cache复用 | DP-16 |
| ALT-48 | MASS_PARITY与COLAV_STRICT共享完全相同prepared vectors | strict slack/per-target bounds必然不同，语义矛盾 | DP-16 |
| ALT-49 | AssemblyOutcome public携带prepared positional arrays | 上层耦合backend layout，升级成为跨层breaking change | DP-17 |
| ALT-50 | Assembler和solver各维护一套offset/row layout | 双authority必然漂移，hash只能发现不能预防 | DP-17 |
| ALT-51 | seed/bounds/slack/schedule policy继续全部藏在`_prepare` | semantic snapshot无法重放实际问题，L1继续隐藏在L3 | DP-17 |
| ALT-52 | Expected failure继续用public`ValueError(str)` | 丢失code/owner/identity/recoverability，consumer只能匹配文本 | DP-18 |
| ALT-53 | 每个Mid detail code扩展shared`PlanStatus` | 扩大全算法/GUI/manifest blast radius并混淆normalized状态 | DP-18 |
| ALT-54 | Assembly failure后last-plan/nominal/其他算法标SUCCESS | 违反no-fallback并隐藏本周期Mid-MPC未执行 | DP-18 |
| ALT-55 | Full grids/rows/vectors内联每个PlannerTrace frame | 单solve约216KB，websocket/session内存和hold重复膨胀 | DP-19 |
| ALT-56 | 只存inline摘要，不保full artifact | 无法重放prepared/raw rows或解释solver/acceptance分歧 | DP-19 |
| ALT-57 | 继续扩展free-form`algorithm_details/constraints` | 无version/unit/owner，候选2/3与GUI相互覆盖漂移 | DP-19 |
| ALT-58 | 只沿用G3 capability与场景PASS | 不能证明assembly确定性、strict slack、81点、failure/hash或真实prepared问题 | DP-20 |
| ALT-59 | 只跑unit与MASS parity | 不能证明真实执行、通过侧、船体净距、recovery、8010/GUI和no-fallback | DP-20 |
| ALT-60 | 为PASS降低50m、缩短目标集合、加fallback或场景特例 | 属于threshold cheating，直接违背既定验收边界 | DP-20 |
| ALT-61 | Facade Orchestrator + Thin Builder | 保留当前双authority、混责与只能闭环末端发现装配缺陷的根因 | CARD-01 |
| ALT-62 | Public Staged/Numerical Pipeline | public stage/vector泄漏调用顺序和layout，当前无第二backend/plugin收益抵消复杂度 | CARD-01 |
| ALT-63 | Frozen-Parity Single Profile | 数学等价不能证明50m同步船体hard、可跟踪性或COLREG maneuver quality | CARD-02 |
| ALT-64 | Encounter-Specific Problem Builders | 场景分支与调参造成策略重复、组合爆炸和阈值过拟合，无法形成统一能力 | CARD-02 |
| ALT-65 | Inline G3/Scenario Evidence Only | 无完整hash/replay/strict证据，G3与solver success容易被过度外推 | CARD-03 |
| ALT-66 | Full Synchronous Monolithic Trace | 单solve大payload造成deadline、websocket、内存与retention风险 | CARD-03 |

### 0.8 技术规约注册表 [TS]

| ID | 类别 | 规约内容 | 单位/定义 | 来源 | 关联DP/接口 | 与现状差异 |
|----|------|----------|-----------|------|-------------|-----------|
| TS-01 | solver | 唯一数值 backend 为 IPOPT；不新增 backend abstraction | CasADi/IPOPT | 用户已确认/[R1] | DP-17 | 一致 |
| TS-02 | grid | Playground 当前 Mid-MPC 预测时域 `80 × 15s = 1200s` | N=80, dt=15s | 当前 config/[R1] | DP-10 | 一致 |
| TS-03 | 坐标/单位 | Colav native Interface 使用 ENU、SI、rad；角度需 ordinary unwrap | m,m/s,s,rad | [R1] | DP-06 | 一致但权威分散 |
| TS-04 | capacity | frozen MASS parity core 固定最多16目标 | target count ≤16 | [R1][R4] | DP-08/DP-18 | 一致但失败语义未集中 |
| TS-05 | runtime | 无 fallback；assembly 无安全问题时必须显式失败给 Adapter | fail-closed | 用户已确认/[R1] | DP-18 | 当前异常链存在，taxonomy 不完整 |
| TS-06 | provenance | frozen formulation identity | `mass-l3-mid-mpc-ipopt@ced58f8576f3772ef7c1bc72bb0f8b0368688b5a` | [R1][R2] | DP-05 | 现有details有名称，snapshot尚无强identity |
| TS-07 | 坐标/符号 | local OCP `x=North,y=East`；navigation angle clockwise from North；正 course alteration=starboard | m/rad | [R1][R4] | DP-06 | 现状隐含，需显式snapshot evidence |
| TS-08 | grid | 80 control intervals；state times `0..1200s` 共81点；frozen own row `(k+1)dt`、target row `kdt` | N=80,dt=15s | [R1][R2] | DP-10 | UI/mapper当前覆盖首优化点，需修 |
| TS-09 | safety | required hull clearance=50m project gate；preferred hull clearance=150m soft aspiration；CPA slack单位=m² | m/m² | [R1][R2] | DP-11/DP-16 | legacy字段与GUI语义需拆分 |
| TS-10 | runtime | solve period=5s；deadline=20s | s | published config/b94148c | DP-05/20 | 一致 |
| TS-11 | identity | cycle identity=`epoch/sequence/sim_time/input/profile hashes`；request/problem/prepared分别canonical hash | versioned SHA-256 | VR-05/23 | DP-05/19 | 新增 |
| TS-12 | prediction | target CV mean 81点；position covariance 99% envelope；不宣称maneuver-target robustness | m/m² | VR-09/[R21] | DP-09/10 | bridge未输出完整bundle |
| TS-13 | frozen timing | 同步node补偿使用target一步位移，不使用own一步位移 | `target_sog*15s` | [R22]/VR-11 | DP-10/11 | 修正bridge公式 |
| TS-14 | activation | schedule先用物理秒和reachability表达，再映射frozen rows；禁止裸`TCPA/dt-2` | s→stage | VR-12 | DP-12 | 替换bridge heuristic |
| TS-15 | capability | published KinematicCSOG envelope: heading±45°、speed0..8m/s、ROT3°/s、decel0.3m/s² | rad,m/s,rad/s,m/s² | b94148c config | DP-13 | 明确ODD限制，不冒充live GNC |
| TS-16 | prefix | 无execution ack时K=0；partial stage unsupported | stage count | VR-14 | DP-14 | 一致 |
| TS-17 | seed | v1 deterministic cold；仅L4 accepted-plan可primal resample；dual disabled | provenance | VR-15 | DP-15 | 当前无accepted-plan handoff |
| TS-18 | profile | `MASS_PARITY`保8 oracle；`COLAV_STRICT`同graph/layout且CPA/direction slack lb=ub=0 | bounds-only | VR-16/22 | DP-16/17 | 替换双solver临时捷径 |
| TS-19 | route | nominal anchor/tangent稳定；Lifecycle给commit/recovery authority；Assembler只编译 | ENU/rad | VR-07 | DP-07 | bridge当前混有recovery step |
| TS-20 | target binding | required全入；eligible按risk；slot按TrackKey canonical；>16 typed failure | ≤16 | VR-08 | DP-08/18 | bridge只取required |
| TS-21 | failure | closed typed failure含code/owner/status/recoverability/identity/evidence；无partial problem | JSON-safe | VR-18 | DP-18 | 替换ValueError文本 |
| TS-22 | evidence | `lifecycle/assembly/solver/acceptance`独立namespace；inline≤8KiB | compact JSON | VR-19/23 | DP-19 | 替换free-form混写 |
| TS-23 | artifact | full grids/rows/vectors存content-addressed gzip；sink失败不阻塞control | gzip JSON/SHA-256 | VR-19 | DP-19 | 新增 |
| TS-24 | runtime mapping | Adapter只机械映射PlanStatus/details；no fallback；Session fail-stop | existing public API | VR-18 | DP-18/20 | 一致但detail需补全 |
| TS-25 | acceptance | A Assembler、B parity、C strict、D closed-loop、E 8010、F full regression不可互替 | six gates | VR-20/23 | DP-20 | 新增统一门 |

### 0.9 跨线程对齐注册表 [SYNC]

> 上游线程: `019fe958-c44a-7052-95dc-1b6f4e22e302`；实施worktree: `/Users/marine/Code/.worktrees/Colav-Simulator/mid-mpc-l0-l1-lifecycle`。accepted solution pack是语义权威；worktree代码为进行中实现，不反向改写本设计。候选2完成/合并、候选3Step6、候选3开始实现前各复核一次。

| ID | 对齐面 | accepted语义 | 2026-08-11进行中实现观察 | Owner/后续动作 |
|----|--------|-------------|--------------------------|----------------|
| SYNC-01 | Snapshot名称/版本/身份 | versioned immutable `EncounterDecisionSnapshot`；epoch/cycle/time/input/profile identity | 类名暂为`DecisionSnapshot`；有epoch/sequence/time/input/profile hash，但Snapshot本体未见显式schema version | Lifecycle定schema；Assembler按versioned contract消费，不锁临时类名；合并后更新binding |
| SYNC-02 | Target identity/health | 全量TrackKey+episode+health+kind/role/risk/lock/action/side/Rule17/release facts | `TargetDecision`已有大部分字段；`TrackKey`/`TrackSnapshot`正在落地 | Lifecycle拥有事实；Assembler只校验、绑定、排序，不重算 |
| SYNC-03 | AggregateDirective | required targets、course corridor、speed/STOP、conflict/capacity/status；不是global side sign | 当前仅`required_targets/passing_side/minimum_course_change/speed_bounds` | Lifecycle扩充或version bump；Assembler不得把临时global side当最终合同 |
| SYNC-04 | Failure taxonomy | OBSERVATION_UNUSABLE/INPUT_CONFLICT/TIME_GAP/MANEUVER_CONFLICT/CAPACITY_EXCEEDED/CORE_CAPABILITY_MISMATCH带owner/evidence | 当前LifecycleFailure已有部分code；transitional assembler多用`ValueError` | Lifecycle产L0 failure；候选3装配映射产L1 typed AssemblyFailure；禁止ValueError穿透公共seam |
| SYNC-05 | Reset/epoch/retry | reset递增epoch并记录reason；同identity+hash幂等；同identity异hash冲突 | Lifecycle已有epoch/sequence/input_hash状态；Adapter/reset集成进行中 | Lifecycle/Adapter拥有reset；Assembler stateless，只验证identity |
| SYNC-06 | Evidence/profile/events | Snapshot带profile hash/events；PlannerTrace lifecycle子schema versioned | 当前Snapshot有profile hash/events/evidence flag；Trace/持久化仍进行中 | Lifecycle产transition evidence；Assembler引用hash/event ids，不复制事件日志 |
| SYNC-07 | `mid_mpc_assembler.py` ownership overlap | Lifecycle止于Snapshot；候选3拥有完整L1/L2 deep Assembler | 候选2worktree已有transitional `assemble_mid_mpc_problem`，返回bare problem wrapper，且仍含route/schedule/CPA换算 | 标记临时integration bridge；候选2完成后候选3迁移/替换，禁止形成第二长期Assembler或双装配路径 |
| SYNC-08 | 坐标/速度/角度事实 | Lifecycle/Tracker提供ENU position/velocity、physical heading、hull与validity；不提供伪造COG | 当前`OwnshipObservation`为NE position/velocity+heading，`TargetObservation/TrackSnapshot`为`state_enu`；frame/unit metadata仍主要靠类型名 | Lifecycle保持physical facts；Assembler唯一投影到frozen heading+surge/COG+SOG并记录validity，合并后加符号contract测试 |
| SYNC-09 | Nominal/commit/recovery reference | L0 Route Adapter提供稳定segment/anchor/tangent/speed；Lifecycle只给maneuver/recovery authority；Assembler stateless编译 | 当前Cycle仅带`route_bearing/planned_speed`，transitional assembler内部又计算commit/recovery bearing并把route origin设0 | 候选2不得成为第二Route/LOS authority；候选3迁移为separated nominal frame+heading reference，合并后删临时recovery计算 |
| SYNC-10 | Required/admission/capacity owner | Lifecycle必须保留全量targets并给required/urgency/directive；Assembler做ELIGIBLE预测admission与core max16 gate，任何层都不得截断 | 当前Lifecycle`_aggregate`可能在生成Snapshot前抛`CAPACITY_EXCEEDED`；transitional assembler只装`required_targets` | 候选2完成后核对是否仍可保留全量证据；允许上游fail-stop但必须携带全量required/count/evidence；候选3保留最终core capacity invariant |
| SYNC-11 | Track time/covariance/prediction profile | Snapshot需state reference time、observed/generated time、4x4 covariance与quality；Planner ODD提供versioned CV process-noise/confidence profile | 当前TrackSnapshot/TargetObservation已有time/covariance/source/health；未见完整target prediction process-noise contract | Lifecycle不外推第二套轨迹；Assembler统一生成81点CV mean/envelope；合并后补prediction profile/hash或限制God zero-cov ODD |
| SYNC-12 | Grid/trajectory time contract | Core=80 control intervals×15s；public own/target prediction=81 state points`t=0..1200`；frozen CPA错时单独标注 | accepted candidate2 pack已同意81点；进行中transitional assembler仍直接构造legacy80-variable problem，UI/mapper修改进行中 | 候选2合并后验证raw parity仍80 decisions，public prepend x0且不覆盖首优化点；Assembler统一time-axis metadata |
| SYNC-13 | Hull/node/quirk allowance | 50m=同步conservative hull hard clearance；150m=soft aspiration；frozen wrong-time node floor需target displacement allowance，不是own displacement | transitional assembler当前`50+own_radius+max(target_radius+cov)+own_speed_max*dt` | 候选2桥接值不得固化；候选3改为per-target synchronized envelope→global frozen max，并由独立81点swept hull witness验收 |
| SYNC-14 | Constraint activation schedule | Lifecycle给action/achievement/deadline/release authority；Assembler按physical time+reachability编译per-target CPA与global common corridor rows | transitional assembler仍用`floor(min TCPA/dt)-2`、global row schedule和当前minimum-change公式 | 候选2不得固化裸TCPA heuristic；候选3迁移为typed ActivationPlan，合并后用HO/CS/OT未达成/已达成/release fixtures对齐 |
| SYNC-15 | Ownship capability facts | 需区分Plant、GNC trackability、Mid ODD并生成stage-wise intersection；resolved Tchi/TU/rate/accel/decel/speed/latency需有authority/hash | 当前candidate2`Maneuverability`只有turn rate/deceleration/speed bounds；PlannerInput仍未完整承载Tchi/TU/GNC envelope | 候选2可保留Lifecycle所需最小facts；候选3AssemblyRequest另接完整CapabilitySnapshot，禁止用Lifecycle DTO或YAML伪装GNC authority |
| SYNC-16 | Execution prefix authority | Prefix只来自不可撤销command ack/queue；当前Adapter hold/resample不是commitment，v1必须K=0 | candidate2正在修改Adapter/reset/control mapping，但尚无多步command queue/ack contract | 候选2合并后重新审计执行链；若仍无authority保持K=0；不得把previous plan或5s hold映射成K=1 |
| SYNC-17 | Previous plan/seed handoff | 只有L4 accepted plan可作为显式primal seed；absolute-time resample，reset/epoch/formulation失配即丢弃；dual v1 disabled | candidate2 Adapter/Facade仍管理last solution/hold；transitional assembler未实现完整seed provenance | 候选2只交付accepted-plan reference/identity，不在Lifecycle或bridge内shift；候选3统一SeedPlan和diagnostics |
| SYNC-18 | Hard/soft/slack profile | MASS_PARITY保留oracle bounds；COLAV_STRICT保留同graph variables但CPA/direction slack lb=ub=0，hard rows不可soften | candidate2当前有普通solver+`dir_slack_enabled=False`第二solver，可能按flag改变graph；transitional assembler未区分profile invariant | 候选2不固化双solver捷径；候选3统一profile/preparer，strict bounds-only时保graph identity并新增raw original-bound recheck |
| SYNC-19 | Semantic→Numerical seam | 候选3输出named PreparationPlan；private core唯一LayoutAuthority打包p/x/bounds并与graph/manifest共享版本 | candidate2 transitional assembler直接构造legacy`MidMpcProblem`；当前solver `_prepare`仍混有seed/broadcast/slack policy | 候选2不得新增第二offset/packing；候选3迁出business policy但保留private codec和8条parity diagnostics |
| SYNC-20 | Failure code/owner propagation | Lifecycle产L0 code；Assembler产L1/L2 AssemblyFailure；Adapter映射现有PlanStatus+ColavExecutionError.details；Session fail-stop | candidate2`LifecycleFailure`已有部分code，但bridge/assembler仍有`ValueError`；GUI error detail当前可能只保status/reason | 候选2完成后统一code/version/owner，消除public ValueError；候选3补recoverability/evidence并验证HTTP/PlannerTrace保真 |
| SYNC-21 | PlannerTrace/evidence namespace | 保留PlannerTrace1.x；candidate2写versioned`lifecycle`，候选3写versioned`assembly`，solver/acceptance分别hash链接；禁止共写free-form keys | candidate2正在实现lifecycle events/evidence flag/UI；当前Mid仍大量`algorithm_details/constraints/target_predictions`自由字典 | 合并后冻结namespace/version/renderer，迁移旧keys；两线程schema测试共同断言不覆盖、hash链闭合和artifact ref可读 |
| SYNC-22 | Cross-thread acceptance ownership | 候选2证明Track/Lifecycle/Rule17/aggregate contract；候选3证明L1/L2 assembly/parity/strict/closed-loop/8010；最终合并跑共同场景与全仓 | candidate2计划已有四层A-D并正改同一integration/tests/UI；候选3尚未实现 | 候选2完成后先rebase/merge其权威tests，再由候选3扩展而不复制；共同fixture id/profile/hash必须一致 |

---

## 参考文献

- [R1] Colav-Simulator 当前源: `colav_simulator/integrations/mid_mpc_ipopt.py`, `colav_simulator/core/colav/mid_mpc/models.py`, `colav_simulator/core/colav/mid_mpc/solver.py`, `config/mid_mpc_ipopt.yaml`，2026-08-11 工作区快照。
- [R2] Colav-Simulator 当前验证面: `tests/test_mid_mpc_ipopt_core.py`, `tests/test_mid_mpc_parity_fixtures.py`, `tests/test_mid_mpc_ipopt_integration.py`, `tests/test_mid_mpc_single_encounter.py`, `tests/test_mid_mpc_multiship_runtime.py`。
- [R3] `/Users/marine/Desktop/MPC/M5_MPC_业务流程分层架构.md`，重点 L1 OCP assembly、L2 solve preparation、L4 gate、LX evidence；其 MASS/acados 专有数值不自动移植。
- [R4] MASS GitLab `mass_devgroup/01-dynamics/01-simulation`, `l3-tdl@4c8ff3bd37591b3bc301537eae8876c25b208bf8`, `mid_mpc_input_builder.hpp`, `mid_mpc_nlp_formulation.hpp`, `row_registry.hpp`, `mid_mpc_solver.hpp`, `types.hpp`；2026-08-11 只读核验。
- [R5] `docs/superpowers/design-logs/2026-08-10-mid-mpc-l0-l1-encounter-lifecycle-design-log.md`，当前已确认 L0→L1 handoff 方向；仍在设计，不视为冻结 schema。
- [R6] CasADi, *Documentation*, parametric NLP、OCP、explicit primal/dual warm start: https://web.casadi.org/docs/
- [R7] B.-O. H. Eriksen and M. Breivik, *MPC-based Mid-level Collision Avoidance for ASVs using Nonlinear Programming*: https://ntnuopen.ntnu.no/ntnu-xmlui/bitstream/handle/11250/2479486/CCTA17_0172_FI.pdf?sequence=2
- [R8] B.-O. H. Eriksen et al., *Hybrid Collision Avoidance for ASVs Compliant with COLREGs Rules 8 and 13–17*: https://ntnuopen.ntnu.no/ntnu-xmlui/bitstream/handle/11250/2641164/Eriksen2019c%2B-%2BHybrid%2BCollision%2BAvoidance%2Bfor%2BASVs%2BCompliant%2Bwith%2BCOLREGs%2BRules%2B8%2Band%2B13--17.pdf?sequence=2
- [R9] T. A. Johansen, A. Cristofaro, T. Perez, *Ship Collision Avoidance Using Scenario-Based Model Predictive Control*: https://torarnj.folk.ntnu.no/colregs_cams.pdf
- [R10] `docs/superpowers/specs/2026-08-11-mid-mpc-l0-l1-encounter-lifecycle-solution-pack.md`，用户于2026-08-11接受；TS-28..TS-31固定`EncounterLifecycle.step(cycle)->EncounterDecisionSnapshot`、逐目标facts、`AggregateDirective`与typed failure handoff。
- [R11] `colav_simulator/core/colav/custom_mpc_adapter.py`，`PlannerInput`、`TrackedObstacle`、`plan`、`_planner_input`、`_execute_solve`、`_execute_hold`、`reset`，2026-08-11工作区快照。
- [R12] `colav_simulator/core/ship.py:567-607` 与 `colav_simulator/core/colav/custom_mpc_adapter.py:453-510`，2026-08-11工作区快照。
- [R13] `colav_simulator/core/colav/mid_mpc/models.py` 与 `colav_simulator/core/colav/mid_mpc/solver.py:415-592`，2026-08-11工作区快照。
- [R14] `colav_simulator/core/colav/diagnostics.py`、`colav_simulator/experiment/session.py:82-143`、`gui_server/main.py:457-491`，2026-08-11工作区快照。
- [R15] `colav_simulator/core/colav/diagnostics.py:53-95`、`gui_server/main.py:707-735`、`web_gui/app.js`，2026-08-11工作区快照。
- [R16] `colav_simulator/core/colav/mid_mpc/solver.py:185-410,618-652` 与 `colav_simulator/integrations/mid_mpc_ipopt.py:317-356`，2026-08-11工作区快照。
- [R17] `colav_simulator/core/models.py:416-452`、`colav_simulator/core/tracking/trackers.py:179-222,284-358,443-480`、`colav_simulator/core/ship.py:567-607,662-671`，2026-08-11工作区快照。
- [R18] B.-O. H. Eriksen and M. Breivik, *MPC-based Mid-level Collision Avoidance for ASVs using Nonlinear Programming*, moving obstacle model/OCP/Table I/initialization；本地`paper/MPC-based mid-level collision avoidance for ASVs using nonlinear programming.pdf`及https://ntnuopen.ntnu.no/ntnu-xmlui/bitstream/handle/11250/2479486/CCTA17_0172_FI.pdf?sequence=2 。
- [R19] IMO, *Convention on the International Regulations for Preventing Collisions at Sea, 1972* overview: https://www.imo.org/en/about/conventions/pages/colreg.aspx ；IMO Annex 7 reproduction, A7.2.4-A7.3.7: https://wwwcdn.imo.org/localresources/en/MediaCentre/Documents/MODEL%20final%20SAFETY%20REGULATIONS%20INLAND%20Africa-1.pdf 。
- [R20] COIN-OR, *Ipopt Options*, `tol`、`constr_viol_tol`、`acceptable_constr_viol_tol`、NLP scaling: https://coin-or.github.io/Ipopt/OPTIONS.html 。
- [R21] SciPy, `scipy.stats.chi2` PPF/interval documentation: https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.chi2.html 。
- [R22] 机械推导与可执行反例，基于R16：同步距离下界`d_sync≥d_frozen-|v_target|dt`；node反例`r0=(-100,0),r1=(100,0)`两端100m而区间最小0m。2026-08-11本地复算。
- [R23] `colav_simulator/core/colav/mid_mpc/models.py:127-225`、`solver.py:65-123,185-315,415-592`、`tests/fixtures/mid_mpc_ipopt/v1.jsonl`与`tests/test_mid_mpc_ipopt_core.py`，2026-08-11工作区快照。
- [R24] COIN-OR, *Ipopt Options*, `warm_start_init_point`、`warm_start_same_structure`、`fixed_variable_treatment`、`bound_relax_factor`: https://coin-or.github.io/Ipopt/OPTIONS.html 。
- [R25] B.-O. H. Eriksen and M. Breivik, *MPC-based Mid-level Collision Avoidance for ASVs using Nonlinear Programming*, Eq.(20)/Section V：后续MPC以前次解初始化；原文实验h=10s,Np=24，非本项目80×15。来源同R18。
- [R26] 2026-08-11本地只读微基准：Apple M3/8GB/arm64、CasADi3.7.2+IPOPT。80×15 cold solve单样本：0/1/16 targets分别836/1022/5368ms；breakdown单样本graph build 570/654/1321ms、IPOPT 114/235/3857ms。相同1-target problem与同一graph：cold 43 iter/614ms，previous primal作为x0为15 iter/152ms。far-target free slack 20 iter/271ms，ub=0 strict为24 iter/321ms。均非p95/闭环结论。
- [R27] 基于R23的机械时间轴分析：旧solve在`0,15,30...`定义piecewise-constant interval decisions，新solve在5s后使用`5,20,35...`边界；不存在整数stage shift。whole-stage prefix也不能无损表达5s/10s等partial commitment。

---

## 演进日志(append-only · 时序 · 不可覆盖)

### Step1 · 行业调研·发现决策点  [2026-08-11 10:32 +0800]

- 模式判定: **重构**。现有 `_MidMpcFacade.solve` 已实际承担 problem assembly，`MidMpcProblem`/`MidMpcPreparedProblem`/IPOPT core 已存在；目标是深化 Module，不重写 frozen NLP。[R1][R2]
- 代码调用链: `PlannerInput → _MidMpcFacade.solve → MidMpcProblem → MidMpcIpoptSolver._prepare → CasADi/IPOPT → MPCSolution`。当前最大 Locality 问题位于 facade：一次调用同时做 LOS、lifecycle、target admission、route commitment、safety allowance、row schedule、problem construction、solver selection、solution mapping。[R1]
- Module 设计目标: 高 Depth、窄 Interface。把 L1/L2 assembly 规则集中在可 replay 的深 Module；保留薄 Adapter/orchestrator；纯 IPOPT core 继续 equation-identical，不吸收 COLREG lifecycle 或 GUI 责任。
- 与候选2同步: 候选2只交 immutable decision facts；本候选只消费。不得重复分类、commit/release/rearm；其 schema 未冻结，所以 DP-03 先确定最小稳定 handoff 与版本策略。[R5]
- 七层映射: L1 负责业务 OCP 语义；L2 负责 seed、参数和 bounds/slack preparation；L3 IPOPT 不改；L4 acceptance 独立。是否在公开 Seam 同时暴露 L1 snapshot 与 L2 vectors，留给 DP-04/DP-17 裁决。[R3][R6]
- GitLab 边界: 只借鉴 current remote 的 pure input-builder、row-registry、solver responsibility split；不移植 ROS/GNC/M4/M6、acados、BC-MPC、1852m 等专项目因素。[R3][R4]
- 外部决策维度: 参数化 NLP、显式 bounds/initial primal-dual、预测模型和 grid、target uncertainty、COLREG intent 固定周期、trajectory/hazard evidence。[R6][R7][R8][R9]
- NLM 快调: `domain:colav_algorithms --no-add-sources` 因本机缺 `socksio` 未执行；没有修改 NLM。已以一手文档/论文完成 Step1 广度扫描，BL-11 留待 Step3 补足。
- 新增决策点: DP-01..DP-20。
- 触发技术分解: TD-01 `OCP Problem Assembly` → handoff、snapshot、normalization、reference、target prediction/admission、grid/safety/schedule、capability/prefix/seed、hard-soft、numerical preparation、failure/evidence/verification。
- Step1 gate: 主干决策维度非空；技术型 DP-02 已分解；注册表/技术树/模式齐全。进入 Step2 前等待用户确认本批决策覆盖面。

### Step2 · grilling 压力测试  [2026-08-11 10:39 +0800]

- 用户确认 Step1 决策覆盖面；开始逐 DP 裁决。
- 当前待裁决: DP-01 Problem Assembler Module 责任、Depth 与 Seam。
- [grilling 记录·三视角] DP-01:
  - [专家] Problem Assembler 应消费已验证输入与 immutable decision facts，集中问题定义复杂度；solver/acceptance/output 保持单向下游。[R1][R3][R4][R6]
  - [新手] 只移动 `MidMpcProblem(...)` 构造器不能改善 Locality；target/reference/safety/schedule/bounds/prefix/seed 仍散落。
  - [悲观] 过宽会复制 lifecycle 与接受逻辑；过浅只是字段 wrapper。两者都会让 OT/HO/CS 缺陷继续跨层混淆。
  - [机制C默认最简版失效] 提取 builder 函数但业务规则留在 facade；deletion test 不成立。
  - [盲区] BL-02/BL-10 保留，交 DP-04/DP-17 深挖。
- 用户确认 DP-01；登记 VR-01。
- 当前待裁决: DP-02 OCP Problem Assembly 内部技术结构。
- [grilling 记录·三视角] DP-02:
  - [专家] 采用单个深 Module 与私有分阶段纯 Implementation；L1 完成语义问题，L2 完成确定性准备，assembly 原子提交。[R3][R4][R6]
  - [新手] 单个巨型 `assemble()` 仍混合坐标、选择、schedule、slack 与 seed，无法分层诊断。
  - [悲观] 每阶段 public class 会制造浅 Module 和中间 schema；mutable dict pipeline 会产生调用顺序依赖。
  - [机制C默认最简版失效] 把 facade 代码整体复制到新文件，只改变位置，不改善 Depth、测试性或确定性。
  - [盲区] BL-10 保留；公共 L1/L2 Seam 交 DP-04/DP-17。
- 用户确认 DP-02 方案 B；登记 VR-02。
- 当前待裁决: DP-03 immutable lifecycle handoff。
- [grilling 记录·三视角] DP-03:
  - [专家] Handoff 必须是同周期原子 immutable snapshot，并关联 exact observation 与 policy facts；禁止 Assembler 回调 Lifecycle 查询。
  - [新手] 仅传 aggregate `intent/side/targets` 会丢失逐目标 role、phase、health、urgency、generation 与 evidence。
  - [悲观] 按整数 target ID 与当前 PlannerInput 二次拼接会混用旧 decision/新 observation 或同 ID 新 generation；重分类形成双 authority。
  - [机制C默认最简版失效] 传 aggregate policy 加预截断16目标，隐藏第17个 active threat，无法 replay 原周期问题。
  - [盲区] BL-01 保留；候选2最终 DTO 待其 Step6 冻结。DP-05 继续处理 version/hash。
- 用户确认 DP-03；登记 VR-03。
- 当前待裁决: DP-04 Assembler 输出 Interface。
- [grilling 记录·三视角] DP-04:
  - [专家] public output 应为 immutable `AssemblyOutcome`；成功返回 semantic snapshot，positional numerical packing 留私有 Seam。[R1][R4][R6]
  - [新手] 仅返回 `MidMpcProblem` 缺 cycle identity、target-slot binding、assembly evidence、failure reason 与 replay hash。
  - [悲观] 直接公开 `p/x0/lb*` 会令 integration 依赖 core slot/row layout；仅返回业务 DTO 又可能让 solver 静默改题。
  - [机制C默认最简版失效] `assemble()->MidMpcProblem` 能求解但无法解释 target order、stage activation 或 trace 一致性。
  - [盲区] BL-10 保留，numerical packing 内部所有权交 DP-17；hash/schema/evidence 交 DP-05/DP-19。
- 用户确认 DP-04；登记 VR-04。
- 当前待裁决: DP-05 identity、provenance 与 replay contract。
- [grilling 记录·三视角] DP-05:
  - [专家] 分离周期实例身份与问题内容身份；同内容可跨周期复现，同一周期不可对应两套内容。
  - [新手] 仅 `sim_time_s` 无法区分 reset/pause/replay，也不包含配置、profile 与 formulation provenance。
  - [悲观] per-call UUID 破坏 retry 幂等；wall clock/unordered data 破坏 canonical hash；只 hash 输入无法发现 Assembler 静默改题。
  - [机制C默认最简版失效] `timestamp+target_ids` 忽略 generation、配置、target order 与 row schedule。
  - [盲区] 新增 BL-13，Session/Adapter identity authority 与 legacy migration 待 Step3。
- 用户确认 DP-05；登记 VR-05、TS-06。
- 当前待裁决: DP-06 normalization 与 reduced-model state contract。
- [grilling 记录·三视角] DP-06:
  - [专家] 显式分离真实 physical state 与 frozen reduced state；core 保持 heading+surge parity，geometry 使用 sway-aware ENU velocity。[R1][R4]
  - [新手] `u` 不是地速，COG 不是艏向；静默互换会让 geometry、core 与 GUI 使用不同运动语义。
  - [悲观] ENU `atan2` 参数反转会旋转90度，wrap会反转跨2π bounds，零速 target COG 未定义，大坐标会恶化数值条件。
  - [机制C默认最简版失效] 全部压成 `x,y,psi,speed` 且不记来源/validity，无法诊断模型偏差。
  - [盲区] 新增 BL-14，sway/reduced-model mismatch 与低速阈值交 Step3/L4；Assembler 不猜数值。
- 用户确认 DP-06；登记 VR-06、TS-07。
- 当前待裁决: DP-07 route/reference construction ownership。
- [grilling 记录·三视角] DP-07:
  - [专家] L0 Route Adapter 负责名义航线事实，Lifecycle负责maneuver directive，stateless Assembler只编译OCP reference。
  - [新手] 单 `route_bearing` 无法区分 nominal/avoidance/recovery，也不保留cross-track与rejoin。
  - [悲观] Assembler运行stateful LOS会破坏retry幂等；每周期本船零点重锚会清空累计横向偏差；固定5度会形成双COLREG authority。
  - [机制C默认最简版失效] 继续 `route_bearing + origin=(0,0)`，真实解仍是不断从当前位置出发的直线，缺恢复语义。
  - [盲区] 新增 BL-15，frozen单直线reference的能力边界交Step3验证。
- 用户确认 DP-07；登记 VR-07。
- 当前待裁决: DP-08 target admission、ordering与capacity。
- [grilling 记录·三视角] DP-08:
  - [专家] 所有 REQUIRED threats 必须同时入 OCP；容量不足则不能形成安全结论。Monitor仅在horizon内有interaction时占slot。
  - [新手] 简单top-16会隐藏第17个active threat；反向填满所有远期monitor会重现out-of-horizon HOLD数值不稳。
  - [悲观] 单range/DCPA排序忽略发生时间；risk顺序直接作slot会因抖动破坏warm-start。
  - [机制C默认最简版失效] `sorted(... )[:16]` 正常返回解却无法证明未选目标安全。
  - [盲区] 新增 BL-16/BL-17，prediction risk与slot preservation交DP-09/DP-15。
- 用户确认 DP-08；登记 VR-08。
- 当前待裁决: DP-09 target prediction与uncertainty。
- [grilling 记录·三视角] DP-09:
  - [专家] v1保持 frozen CV target model；Assembler生成同源prediction/evidence，不静默引入逐stage maneuver backend。[R4][R7][R9]
  - [新手] 1200s直线可是真实CV求解结果，但不等于真实maneuvering target的可靠预测。
  - [悲观] state timestamp不清会double-predict；忽略covariance夸大安全；全局margin可能过度保守。
  - [机制C默认最简版失效] `p=p0+vt` 不记录state time、covariance、health和ODD，God PASS被误报为传感器鲁棒。
  - [盲区] 新增 BL-18..BL-20，交Step3；required UNUSABLE target fail-closed。
- 用户确认 DP-09；登记 VR-09。
- 当前待裁决: DP-10 horizon/grid与physical-time mapping。
- [grilling 记录·三视角] DP-10:
  - [专家] 80×15s 是80区间、81状态时刻；业务schedule先以秒定义，再用具名policy映射stage。[R3][R6]
  - [新手] 当前mapper覆盖首优化点，丢失t=15s；N点UI不等于N区间的完整state trajectory。
  - [悲观] 裸floor公式无法表达deadline语义；frozen row比较own `(k+1)dt` 与 target `kdt`，可能漏区间碰撞。
  - [机制C默认最简版失效] 全链路直接传整数k，dt变化后物理激活时机与UI时间解释漂移。
  - [盲区] 新增 BL-21/BL-22，分别交DP-12与Step3安全证明。
- 用户确认 DP-10；登记 VR-10、TS-08。
- 当前待裁决: DP-11 safety-distance semantics与conversion。
- [grilling 记录·三视角] DP-11:
  - [专家] 业务船体净距、中心距、node floor、continuous clearance、不确定性margin与slack单位必须分离。[R1][R3]
  - [新手] 中心距50m不等于船体净距50m；soft 150m也不应自动成为hard floor。
  - [悲观] frozen所谓hard row可被global m² slack放松；单global floor无法精确表示不同船体/时间/covariance。
  - [机制C默认最简版失效] 原样传50/150并把solver success解释为hull clearance PASS，结论不成立。
  - [盲区] 新增 BL-23；BL-18/BL-22保留。真实安全只由同步continuous hull witness确认。
- 用户确认 DP-11；登记 VR-11、TS-09。
- 当前待裁决: DP-12 constraint activation与reachability schedule。
- [grilling 记录·三视角] DP-12:
  - [专家] row activation由Lifecycle action authority、physical reachability、prefix可控时间与safety deadline共同决定。[R3][R4]
  - [新手] `newly_committed`仅首周期为真，导致direction/min-alt下一周期消失；TCPA裸公式无安全语义。
  - [悲观] global schedule会逼MONITOR提前动作；不可达min-alt直接hard会制造人工不可行；延迟required CPA会失去早期floor。
  - [机制C默认最简版失效] `new commit→rows on`、后续off，commitment不由OCP维持。
  - [盲区] 新增 BL-24..BL-26，交Step3/DP-13/DP-16/DP-17。
- 用户确认 DP-12；登记 VR-12。
- 当前待裁决: DP-13 live capability与stage bounds。
- [grilling 记录·三视角] DP-13:
  - [专家] plant、GNC trackability、algorithm search window分离后逐stage取交集。[R3]
  - [新手] ±45度是搜索窗口，不是15s可达角；speed floor也决定STOP是否可表示。
  - [悲观] 静态rot/decel可能产生真实船不可跟踪轨迹；uniform bounds忽略前段reachability；隐式0.08不可审计。
  - [机制C默认最简版失效] YAML四标量广播80步，IPOPT可行不等于plant/GNC可执行。
  - [盲区] 新增 BL-27..BL-29，live capability seam与oracle交Step3。
- 用户确认 DP-13；登记 VR-13。
- 当前待裁决: DP-14 committed prefix contract。
- [grilling 记录·三视角] DP-14:
  - [专家] prefix只表达不可撤销执行承诺，先做capability与continuous safety witness，再从首个可控stage优化。[R3][R4]
  - [新手] previous optimum未必已下发，只能是warm-start，不应hard-fix。
  - [悲观] unsafe prefix靠关闭row/slack会虚假Converged；partial 15s stage用floor/ceil各有风险。
  - [机制C默认最简版失效] shift旧解前K步设equality，无execution authority/timestamp/rollout/witness。
  - [盲区] 新增 BL-30..BL-33，当前runtime基线K=0，等待执行链证据。
- 用户确认 DP-14；登记 VR-14。
- 当前待裁决: DP-15 seed与warm-start。
- [grilling 记录·三视角] DP-15:
  - [专家] seed是数值初值，不是execution commitment；previous accepted primal需显式eligibility与continuous-time resample。[R6]
  - [新手] solve period5s与grid15s不整除，shift一数组stage会错10s。
  - [悲观] 旧side/episode/dual、L4拒绝解或直接clip会污染新问题和rate continuity。
  - [机制C默认最简版失效] `shift(previous_x,1)` 忽略时间、target slots、angle unwrap与reset。
  - [盲区] 新增 BL-34..BL-36；dual v1 disabled，先测再开。
- 用户确认 DP-15；登记 VR-15。
- 当前待裁决: DP-16 hard/soft/slack contract。
- [grilling 记录·三视角] DP-16:
  - [专家] hard不能靠大penalty；production可保留frozen variables/layout但将slack ub固定0，parity profile保留oracle bounds。[R1][R3][R4]
  - [新手] CPA slack是m²；同一direction slack同时作用m与rad row，量纲不统一。
  - [悲观] global slack可掩盖某target/stage严重违反；IPOPT Success不能推出hard safety。
  - [机制C默认最简版失效] 继续可用slack、提高weight并宣称hard，业务结论仍错误。
  - [盲区] 新增 BL-37..BL-39；strict production必须输出逐row单位与physical margin evidence。
- 用户确认 DP-16；登记 VR-16。
- 当前待裁决: DP-17 numerical preparation ownership。
- [grilling 记录·三视角] DP-17:
  - [专家] Assembler拥有L2 semantic decisions，private core唯一拥有positional vector/layout codec。[R4][R6]
  - [新手] `p[17]`无业务语义，必须通过manifest映射target/stage/constraint。
  - [悲观] 双方各维护offset会错位；反向把policy全留`_prepare`会保留隐式decel/schedule/slack defaults。
  - [机制C默认最简版失效] 只重命名当前 `_prepare`，未迁出业务裁决。
  - [盲区] 新增 BL-40/BL-41；graph/preparer共享唯一layout authority。
- 用户确认 DP-17；登记 VR-17。
- 当前待裁决: DP-18 assembly failure taxonomy与no-fallback propagation。
- [grilling 记录·三视角] DP-18:
  - [专家] expected domain failure用typed outcome，携带layer/code/identity/evidence/recoverability；Adapter只传播。
  - [新手] 单 `INFEASIBLE` 无法区分capacity、unsafe prefix、capability或solver。
  - [悲观] actual solve失败后last-plan-as-success隐藏安全失效；裸exception丢cycle trace与责任层。
  - [机制C默认最简版失效] `except Exception:return previous_solution`，场景继续但已非本周期Mid-MPC。
  - [盲区] 新增 BL-42..BL-44；细粒度code嵌入现有PlanStatus，不扩大shared enum。
- 用户确认 DP-18；登记 VR-18。
- 当前待裁决: DP-19 LX evidence与GUI/replay schema。
- [grilling 记录·三视角] DP-19:
  - [专家] 各层产出immutable hash-linked evidence，不共同mutation临时dict。
  - [新手] 当前Mid target keys与GUI读取不一致，objective也未作为统一schema呈现。
  - [悲观] 全量inline会膨胀；只存摘要无法replay；GUI重算会产生第四套trajectory truth。
  - [机制C默认最简版失效] 继续向 `algorithm_details` 添加临时keys，单位/版本/consumer持续漂移。
  - [盲区] 新增 BL-45..BL-47；inline summary与full artifact分层。
- 用户确认 DP-19；登记 VR-19。
- 当前待裁决: DP-20 contract/acceptance verification matrix。
- [grilling 记录·三视角] DP-20:
  - [专家] 验证必须分层证明纯装配确定性、frozen formulation parity、production hard semantics、真实闭环行为、8010运行时可观测性与全仓兼容；任何单层不能替代其他层。[R1][R2][R3]
  - [新手] `IPOPT Solve_Succeeded` 只证明数值求解状态，不证明连续船体净距、COLREG通过侧、恢复、无fallback或UI轨迹时间语义。
  - [悲观] 仅跑五个场景会漏容量/坏边界/replay；仅跑unit/parity会漏真实执行链；把目标船脚本互撞计入Ship0失败会误判控制责任边界。
  - [机制C默认最简版失效] 沿用现有G3 capability tuple作为全部验收，不能证明strict slack=0、81点轨迹、assembly failure taxonomy与真实8010 planner event。
  - [盲区] BL-41/BL-43/BL-48/BL-49保留；性能p95与独立L4 seam交Step3实证，不凭设计值宣布通过。
- 用户确认 DP-20；登记 VR-20。
- Step2 gate: DP-01..DP-20全部裁决；进入Step3逐批补证。任何盲区在用户确认该批证据前不标记关闭。

### Step3 · 自主深度调研  [2026-08-11]

- Batch-01范围: contract/runtime boundary；覆盖BL-01/02/05/06/07/10/13/27/30/42/43/46/47。证据已登记R10..R15，等待用户确认，尚未标闭环。
- BL-01: 候选2已形成Step6草案，明确`EncounterCycle→EncounterDecisionSnapshot`原子handoff、全量目标facts与`AggregateDirective`；但草案仍等待该线程用户接受。最小语义依赖已可定义，最终DTO名字/字段/version仍为UNKNOWN。[R10]
- BL-02/BL-10: 当前无replayable assembly transaction；facade直接构造`MidMpcProblem`。现有core虽区分semantic problem与prepared vectors，`_prepare`仍决定cold seed、广播bounds、slack ub、row softening和CPA slack seed。证据支持“public semantic snapshot + private positional codec”，但需实施时抽离L2 business policy。[R1][R13]
- BL-05: 当前direction/min-alt只由`newly_committed`单周期激活；候选2草案要求commitment action持续到achievement/release。Assembler应消费持续action/deadline/achievement facts，不消费one-shot edge；exact DTO待候选2方案包接受。[R1][R10]
- BL-06/BL-27: `Ship.plan`已向ICOLAV边界提供ownship `T_chi/T_U/r_max`，但`CustomMPCAdapter._planner_input`忽略这些kwargs；PlannerInput只保留状态、hull、tracks。accel/decel/GNC trackability也没有统一live authority。结论不是“YAML足够”，而是共享输入seam有真实信息损失，完整capability contract仍UNKNOWN。[R11][R12]
- BL-07/BL-30: runtime没有多步不可撤销command queue。5s solve间隔内Adapter从上次`control_trajectory`按elapsed time重新采样并返回当前9x1 reference；reset清空solution/plan。由现有执行链可证runtime prefix基线应为K=0；未来只有新增明确command-ack/queue evidence后才能K>0。[R11]
- BL-13: reset把solve_id归零且无epoch/reason；PlannerInput仅sim_time/seed，无session epoch或monotonic cycle identity。候选2草案提出`(session_epoch,cycle_sequence,input_hash)`，但authority迁移尚未实现。[R10][R11]
- BL-42/BL-43: shared `PlanStatus`仅6值、`FailureSource`仅3值；`ColavExecutionError.details`可承载typed detail code而无需扩大enum。solve/assembly异常沿Ship→Simulator→Session传播，`SimulationSession._advance`原子标记FAILED并重抛；不存在fallback或失败后继续cached plan的成功包装。[R11][R14]
- BL-46/BL-47: `PlannerTrace 1.0`已有稳定外层，但Mid证据仍在自由格式`constraints/algorithm_details/target_predictions`。GUI server只投影predicted前两行，并按`x/y`读取目标预测；Mid当前写`north_m/east_m`，目标线会丢失。证据支持保留外层1.x、增加versioned typed子文档/renderer；具体artifact加载与retention预算留BL-45。[R15]
- Batch-01新增张力: 候选2Step6方案包尚未被该线程用户接受；本候选不得把其草案字段当冻结依赖。Step4前需再次读取关联线程并锁定accepted版本或显式versioned compatibility boundary。
- 用户确认Batch-01证据回答盲区；BL-01/02/05/06/07/10/13/27/30/42/43/46/47标记闭环，其中BL-01/06/27保留具名UNKNOWN，不伪造尚不存在的最终DTO或完整capability authority。
- Batch-02范围: safety/grid/model boundary；覆盖BL-03/04/09/14/18/19/20/21/22/23/24/25/28/38/39。证据已登记R16..R22，等待用户确认，尚未标闭环。
- BL-03/BL-38: 15s node可行不推出区间安全；两端各100m的线性相对段可在中点0m相撞。现有`_continuous_cpa`只检查solver trajectory的`t=15..1200s`段，缺`t=0→15s`首段，且仍是中心距。业务hard acceptance必须消费81点同步轨迹并独立检查每个区间的hull clearance。[R16][R22]
- BL-04/BL-22: frozen row比较own `(k+1)dt`与target `kdt`。保证同步距离D需要frozen floor至少`D+|v_target|dt`；当前却加`own speed_max*dt`，仅在`|v_target|≤own speed_max`且无额外模型误差时保守。反例`D=50,dt=15,Vos,max=8,Vt=10`：frozen 170m满足，sync仅20m。故当前换算是带隐含前提的parity补偿，不是无条件安全envelope。[R16][R22]
- BL-09/BL-23: CPA row为`d²-D²+sigma_cpa≥0`，所以slack单位m²且正值放松全部suffix/全部target；direction同一slack又混用于cross-track m与min-alt rad。global floor可用最大margin做保守统一约束，但不能表达per-target/time-varying hard floor、REQUIRED hard与MONITOR soft-only。COLAV_STRICT固定slack=0只能消除放松，不能补足表达能力。[R16]
- BL-14/BL-24/BL-28: built-in KinematicCSOG plant为一阶course/speed模型，受`T_chi/T_U/r_max/U_max`限制；其state固定`[N,E,chi,U,0,0]`，不含sway。其他船模若出现`sway/r`，当前Mid reduced model没有已证明保守映射。可由exact plant rollout生成stage reachability envelope，但与GNC trackability的误差oracle仍UNKNOWN；v1只能将KinematicCSOG+完整capability facts列为支持ODD，不能发明低速/mismatch阈值。[R17]
- BL-18: 当前KF已有CV transition `F(dt)`与process noise `Q(dt)`，可生成每stage covariance。二维Gaussian各向同性保守margin可写为`sqrt(chi2.ppf(alpha,2)*lambda_max(Ppos))`；但`alpha=0.99`是Planner ODD选择，不是COLREG/paper常数。frozen global floor只能取所有target/stage margin最大值，丢失方向性并可能过度保守；精确per-target envelope需row-layout扩展。[R17][R21]
- BL-19: GodTracker直接输出cycle-time真值；KF每周期先predict到当前`t`再按当期measurement update，因此内建tracker的`state_enu`是cycle-time estimate。问题在于tuple不携带measurement timestamp/coasting/status，Ship也未传`track_ages_s`，Adapter默认age=0；所以God场景可用，sensor/KF freshness与coasting contract仍UNKNOWN。[R11][R17]
- BL-20: 原始论文moving obstacle允许一般`p_mi(t)`，其实验为`h=10s,Np=24`即240s，并用前次解warm start；没有验证本项目1200s CV maneuvering-target可靠性。本项目现有闭环证据来自God定速目标。故v1只能声明“deterministic CV target + 5s replanning”ODD，真实机动目标鲁棒性明确UNKNOWN。[R18]
- BL-21: physical-time→stage不存在统一rounding。事件“不得早于t”映射`ceil(t/dt)`；deadline“不得晚于t”映射`floor(t/dt)`；覆盖不可撤销时段需`ceil`但产生partial-stage过冻。每个schedule字段必须携带mapping policy和原始秒值，不能只存k。[R16]
- BL-25: IMO只要求positive/readily apparent/ample time/safe distance/early and substantial，并要求持续检查到past and clear；没有通用秒数或米数。因此latest-achievement deadline必须来自Lifecycle根据风险、能力、ODD计算，Assembler只验证可达并映射grid。[R19]
- BL-39: IPOPT `constr_viol_tol`是原始NLP最大范数绝对违反，当前同一向量混合rad、m/s、m、m²；单个`1e-3`不能解释为统一物理安全容差。必须逐row记录单位/scale并做业务post-check；IPOPT success只作为数值证据。[R16][R20]
- Batch-02新增张力: exact plant/GNC reachability oracle、1200s maneuvering-target ODD、sensor/KF coasting age三项仍为具名UNKNOWN；这些未知应限制production profile，而不是用YAML默认值填充。
- 用户确认Batch-02证据回答盲区；BL-03/04/09/14/18/19/20/21/22/23/24/25/28/38/39标记闭环，其中BL-14/19/20/24/28保留具名UNKNOWN与production ODD限制。
- Batch-03范围: prefix/warm-start/numerical structure/performance；覆盖BL-08/17/26/29/31/32/33/34/35/36/37/40/41/48。证据已登记R23..R27，等待用户确认，尚未标闭环。
- BL-08/BL-34: 当前每次cold seed且重建graph。5s solve与15s control interval没有整数shift；必须用absolute-time trajectory重采样，再投影到新stage envelope，不能`shift(x,1)`。相同问题理想微基准previous primal使43→15 iter、614→152ms，但真实5s state/target/constraint变化收益仍UNKNOWN。[R23][R26][R27]
- BL-17/BL-35: primal只有own `psi/u`与global slacks，没有target-specific decision slot，所以canonical target order主要影响problem hash/rows而非primal remap；dual则绑定CPA row order。IPOPT full warm-start要求primal/dual且`same_structure`要求复用同一NLP object；当前每solve重建graph。v1禁用dual有证据支持，待稳定signature/benchmark后再启用。[R23][R24]
- BL-26/BL-40: CPA rows已按`stage×target`独立存在，per-target hard/disabled activation可只改变`lbg/ubg`，无需改变frozen graph；global direction/min-alt没有per-target row，无法仅靠bounds扩展。当前graph shape依`N,target_count,audit_row_count,slack flags`，且每次重建；安全cache key必须是versioned structural signature并携带layout manifest。为保parity，优先按target-count缓存，不把不足16目标静默padding成新layout。[R23]
- BL-29: current uniform heading/speed box若与first-stage plant-reachable set无交集，IPOPT problem本身不代表可执行恢复。没有已验证recovery corridor policy；v1应在assembly返回typed capability failure。未来只有exact plant/GNC rollout证明stage-wise非空后才允许受控recovery，保留UNKNOWN。[R17][R23]
- BL-31/BL-32/BL-33: frozen prefix只接受whole stages；row bounds还会soften prefix期间CPA/direction/min-alt，且无independent prefix safety witness，也不要求保留可控suffix。当前runtime已证K=0，故v1固定K=0最诚实。未来K>0必须有command authority、exact plant/GNC continuous witness和deadline-derived controllable suffix；最小suffix stage数无通用常数，保留UNKNOWN。[R11][R23][R27]
- BL-36: frozen cold seed只是current course/speed，必要时用CPA slack使初值可接受；strict slack=0后不能称其feasible。通用directive-guided seed应从AggregateDirective与stage capability rollout生成，先校验bounds/rates/prefix并标provenance；即使不满足CPA也只能叫`initial guess`，不能伪装可行解。原论文同样允许infeasible initial guess并依赖后续warm start。[R18][R23][R25]
- BL-37: slack变量ub固定0不改symbolic graph；IPOPT默认把fixed variable作parameter处理，但默认bound relaxation可导致约`-1e-8`诊断值，仍需original-bound post-check。单样本strict从20→24 iter、271→321ms；说明可运行但conditioning成本未完成场景benchmark。MASS_PARITY保持原ub，COLAV_STRICT单独断言ub=0/raw slack tolerance。[R23][R24][R26]
- BL-41: “同一prepared vector同时parity又strict”不成立。MASS_PARITY必须逐项匹配8条oracle；COLAV_STRICT保持可保持的graph identity，但stage bounds/per-target CPA bounds/slack ub使用独立profile invariants。任何per-target direction新row都必须升级formulation ID并新增oracle/contract测试，不能冒充frozen parity。[R23]
- BL-48: 本地cold单样本80×15：0 target 0.84s、1 target 1.02s、16 target 5.37s；16-target已略超拟议5s p95门但低于20s deadline。graph build本身0.57-1.32s，存在明确cache leverage。该结果不是p50/p95/max，也未覆盖strict闭环和memory；BL-48只能部分闭环，正式性能门仍需场景矩阵统计。[R26]
- Batch-03新增张力: graph cache与primal resample有明显性能潜力，但不得先以单样本升级能力；runtime nonzero prefix、dual warm-start、recovery corridor、5s p95仍为具名UNKNOWN。
- 用户确认Batch-03证据回答盲区；BL-08/17/26/29/31/32/33/34/35/36/37/40/41/48标记闭环，其中BL-29/32/33/34/35/37/48保留具名UNKNOWN，不把单样本性能、未接入GNC oracle或未来dual/prefix能力伪装成已验证能力。
- Batch-04范围: portability/route/admission/failure/artifact/L4 boundary；覆盖BL-11/12/15/16/44/45/49。证据已登记R28..R34，等待用户确认，尚未标闭环。
- BL-11: NLM失败是本机可选检索工具缺少`socksio`，不是领域证据缺失。Step3已直接读取当前/远端源码、用户七层文档、官方CasADi/IPOPT/IMO/SciPy资料与原始Mid-MPC论文；其权威性、检索路径和适用边界均已逐条登记。无需安装依赖或修改NotebookLM知识库，可按“替代证据闭环”处理。[R6..R9][R18..R25][R34]
- BL-12: 可移植的是单向`validated input→semantic OCP→numerical preparation→solver→independent acceptance`责任链、pure builder、唯一row/layout authority、hard/soft分离、physical-time schedule和hash evidence。不可移植的是MASS专属ROS2 topic、M4/M6/GNC/M7/BC-MPC链、acados backend、1852m阈值与平台fallback。本项目继续锁IPOPT、50m hull hard gate、150m soft aspiration和Colav PlannerInput；MASS只作边界/失败教训与frozen parity来源。[R3][R4][R28]
- BL-15: frozen objective只计算相对单个`route_origin+normal`的直线cross-track；当前facade又把local origin设`(0,0)`，即每周期从本船重锚，GIVE_WAY时将route bearing换成commitment course加固定最小改向。因此真实IPOPT最优轨迹接近新直线，不是GUI伪造；同时原航线cross-track/rejoin语义已丢。v1 Assembler应保留L0 nominal segment的稳定origin/normal/provenance并单独编译Lifecycle maneuver/recovery reference；若1200s内任务需要单直线无法表达的曲线corridor，显式`CORE_CAPABILITY_MISMATCH`。允许曲率/折线复杂度阈值无本项目证据，保留UNKNOWN。[R18][R29]
- BL-16: 当前先按approaching/TCPA/DCPA/range/id排序并在Lifecycle/optimization分层前截到16，可能静默丢REQUIRED目标。标准与论文未给通用混合单位risk score或tie epsilon；v1不发明权重，采用typed lexicographic admission：tier(REQUIRED先全入)→Lifecycle urgency→首次required-envelope违反时刻→首次preferred-envelope违反时刻→最小同步hull clearance→uncertainty evidence→TrackKey。相同immutable snapshot用canonical数值与TrackKey确定性收尾；近似相等时的跨周期hysteresis属于Lifecycle/Planner ODD，具体epsilon仍UNKNOWN。[R9][R10][R19][R30]
- BL-44: 同一immutable assembly request的确定性domain failure不允许“原地重试并换题”。`recoverability`只给调用者修复权限，不代表runtime自动继续：新鲜输入可修复的观测/能力缺失=`REFRESH_INPUT_THEN_NEW_SESSION`；epoch/time/identity冲突=`RESET_SESSION`；缺配置/非法bounds=`FIX_CONFIGURATION`；超过16 REQUIRED、曲线路径或direction能力不表达=`CHANGE_PROFILE_OR_CORE`；unsafe prefix、hash/invariant破坏=`TERMINAL_FOR_RUN`。当前`SimulationSession`异常后必为FAILED，所以任何恢复都需显式新session/reset，不可复用last plan作为成功。[R14][R31]
- BL-45: 在当前worktree用真实80×15/16-target IPOPT结果测得：`p=266,x=162,g=1843`，逐row evidence 1843条；补齐设计目标81状态点与16条81点target prediction后，compact full JSON约216315B、gzip约48366B，inline hash/status摘要约512B、gzip257B；120次solve约25.96MB raw。该单次测量不是p95/memory或长期retention预算，但足以否定“full artifact每帧内联”：event只带摘要+content hash/ref，full artifact按solve去重压缩保存。TTL/磁盘quota/远端artifact sink仍UNKNOWN，由实验基础设施策略决定。[R15][R32]
- BL-49: 当前solver所谓continuous CPA只验证优化轨迹点之间的目标中心距，缺首个`t=0→15s`物理段与hull几何；public adapter只做shape/finite/首状态连续性；Evaluator hard gate是独立回顾性oracle，不是production acceptance authority。Assembler不得吸收L4，也不得复制Evaluator；它只产出hash-linked 81点同步own/target prediction、hull/capability/schedule evidence。未来L4以versioned handoff消费Problem/Prepared/RawSolution/Prediction/ExecutionContext并返回AcceptanceOutcome；候选L4 schema尚未冻结，测试先断言handoff完整性与用fake consumer做contract，闭环继续用Evaluator独立验收，最终DTO名保留UNKNOWN。[R16][R33]
- Batch-04新增张力: 候选2Step6 solution pack在关联线程仍等待用户明确“接受方案包”，故本设计只依赖其已确认语义方向，不冻结草案DTO字段；route曲率门、admission近似tie epsilon、artifact retention预算与L4最终schema继续作为具名UNKNOWN，不阻止Assembler v1在当前直线/God/KinematicCSOG/IPOPT ODD内设计。
- 用户确认Batch-04证据回答盲区；BL-11/12/15/16/44/45/49标记闭环，其中BL-11使用替代一手证据，BL-15/16/45/49保留具名UNKNOWN。Step3全部49项盲区均有证据或明确UNKNOWN，技术分解无未登记空洞；Step3 gate完成，进入Step4逐DP推荐确认。

### Step4 · 汇总分析与推荐  [2026-08-11]

- DP-01推荐草案(等待用户确认，尚未final): 采用单一深`MidMpcProblemAssembler`责任边界。输入为validated PlannerInput、versioned immutable Lifecycle Snapshot、Planner ODD/capability facts及可选PreviousAcceptedPlan；输出为原子`AssemblyOutcome`。Module拥有L1语义OCP和确定性L2 semantic preparation，不拥有Encounter Lifecycle、Adapter调度、CasADi/IPOPT求解、L4 acceptance、`MPCSolution`或GUI mapping。[R1][R3][R4][R10][R13][R28][R33]
- DP-01备选A: 继续扩展`_MidMpcFacade.solve`。弃用理由: 当前已同时承担LOS、分类/commit、admission、schedule、safety换算、problem构造、solver选择、结果映射和trace；无法独立replay/测试assembly，候选2和L4继续耦合。[R1]
- DP-01备选B: 把每个stage做成public micro-module/pipeline。弃用理由: 中间DTO与调用顺序成为公共API，Depth降低，原子不变量分散，AI/人类调用者必须理解整条流水线。[R3][R28]
- DP-01备选C: 把全部业务装配下沉到`MidMpcIpoptSolver._prepare`。弃用理由: Lifecycle、ODD、hard/soft和admission policy被隐藏进numerical core，污染frozen parity并让L1审计依赖positional slots。[R4][R13]
- DP-01风险: 实施风险中；主要来自候选2最终DTO尚未接受、现有facade迁移面较宽、route/capability/L4存在具名UNKNOWN。失效边界: lifecycle version不兼容、能力facts缺失、单直线core不表达或required target超16时必须typed fail，不得降级偷算。
- DP-01验证: public seam纯函数/幂等/hash测试；现有facade输入的语义golden对照；8条MASS parity prepared-vector不变；Assembler不导入Evaluator/GUI/Adapter调度；异常沿现有no-fallback链使session FAILED。
- DP-01技术分解就绪度: TD-01全部子模块已有裁决或具名UNKNOWN限制，未发现`DECOMPOSITION_INCOMPLETE`。
- 用户确认DP-01推荐；VR-01标记Step4 final，登记ALT-01..ALT-03。
- DP-02推荐草案(等待用户确认，尚未final): public仅暴露`assemble(request) -> AssemblyOutcome`；内部采用stateless、typed、immutable staged pipeline，顺序固定为identity/validation→normalization/reference→prediction/admission→capability/reachability→grid/safety/schedule→seed/preparation-plan→snapshot/evidence。每阶段只能返回完整immutable value或typed failure；任何阶段失败都不暴露partial problem。[R1][R3][R4][R13][R28]
- DP-02备选A: 单个巨型`assemble`函数直接构造所有字段。弃用理由: 虽public seam窄，但内部不变量、单位转换、failure owner和测试定位仍混在一处，重演当前facade问题。
- DP-02备选B: stateful fluent builder逐步`set_*`后`build()`。弃用理由: 调用顺序、缺字段、跨cycle残留和retry mutation成为新隐式状态；与幂等/replay目标冲突。
- DP-02备选C: event-driven/plugin stage registry。弃用理由: 当前无第三方stage或第二实现需求；动态顺序和扩展点增加不可见行为，违反最小方案。
- DP-02风险: 实施风险中低；主要风险是私有stage过细导致样板代码，或过粗退化为巨型函数。失效边界: stage不得持有跨cycle状态、不得I/O、不得调用solver/evaluator；失败不得返回可被误用的半成品。
- DP-02验证: 同request byte-equivalent outcome/hash；每个stage invariant由public adversarial cases覆盖；注入单项非法输入能定位唯一typed failure；失败后再次合法assemble不受污染；pipeline顺序和schema version进入evidence。
- DP-02技术分解就绪度: 内部stage覆盖TD-01全部子模块且不新增public seam，未发现`DECOMPOSITION_INCOMPLETE`。
- 用户确认DP-02推荐；VR-02标记Step4 final，登记ALT-04..ALT-06。
- 跨线程同步更新: 候选2solution pack已被用户明确接受，`EncounterDecisionSnapshot`/`AggregateDirective`语义合同现为accepted design；关联线程已在独立worktree实施。本候选只设计/实现下游Assembler，不重复拥有或修改Lifecycle transition authority。[R10]
- DP-03推荐草案(等待用户确认，尚未final): Assembler直接消费accepted、versioned、immutable `EncounterDecisionSnapshot`，并与同一AssemblyRequest中的PlannerInput/capability facts核对`session_epoch/cycle_sequence/input_hash/sim_time/profile_hash`。使用全量逐目标key/episode/health/kind/role/risk/lock/action/side/Rule17/release facts及`AggregateDirective`；不消费mutable Lifecycle对象，不调用`Lifecycle.step()`，不重新分类、commit、release或聚合。[R10]
- DP-03备选A: 只接收`AggregateDirective`。弃用理由: 丢失逐目标identity、health、required/monitor、release与constraint provenance，无法做capacity/admission/safety evidence核对。
- DP-03备选B: 只接收raw tracks，由Assembler重跑`classify_geometry`和policy。弃用理由: 产生第二COLREG authority，瞬时分类可推翻Lifecycle lock/Rule17/release。
- DP-03备选C: 注入stateful `EncounterLifecycle`对象并由Assembler调用。弃用理由: assembly retry会推进或重复transition/event，破坏幂等、原子handoff和owner boundary。
- DP-03风险: 实施风险中；关联线程正在实现accepted schema，存在短期类名/字段落地与design TS的version skew。失效边界: schema major不兼容、identity/time/hash不一致、snapshot缺目标/aggregate invariant或Lifecycle声明的约束无法表达时typed fail；不得回退到legacy reclassification。
- DP-03验证: Lifecycle accepted fixture直通Assembler；snapshot顺序扰动不改变semantic hash；stale epoch/cycle/time、重复TrackKey不同episode、aggregate引用缺失target逐项RED；Assembler源码依赖测试禁止导入Evaluator classifier或写Lifecycle state；同snapshot retry不产生新event。
- DP-03技术分解就绪度: accepted TS-28..TS-31已覆盖handoff owner、schema内容、core capability gate与failure；未发现`DECOMPOSITION_INCOMPLETE`。
- 用户确认DP-03推荐，并要求显式标注候选2跨线程对齐面；VR-03标记Step4 final，登记ALT-07..ALT-09与SYNC-01..SYNC-07。候选2完成/合并后必须按SYNC表刷新，不允许两个Assembler长期并存。
- DP-04推荐草案(等待用户确认，尚未final): public输出使用closed immutable sum type `AssemblyOutcome = AssemblySuccess | AssemblyFailure`。Success包含semantic `MidMpcProblemSnapshot`、target bindings、prediction/capability/activation/seed plans、cycle/problem hashes与evidence refs；Failure包含typed layer/code/status/identity/recoverability/evidence且`problem=None`。公共输出不得含CasADi object、positional `p/x0/lb*/ub*`或mutable ndarray。[R3][R4][R10][R13][R28]
- DP-04备选A: 直接返回bare `MidMpcProblem`或当前`AssembledMidMpcProblem`。弃用理由: 无失败union、identity/hash、完整provenance和L4/GUI所需证据，调用者需猜partial validity；SYNC-07当前实现仅可视为transitional bridge。
- DP-04备选B: public直接返回`MidMpcPreparedProblem(p/x0/lbx/ubx/lbg/ubg)`。弃用理由: positional layout泄漏L3，实现/fixture耦合，业务层无法辨识row单位和policy来源。
- DP-04备选C: 抛异常作为唯一输出，不建typed Failure。弃用理由: expected domain failure丢失recoverability、identity和evidence；GUI/Session只能得到字符串。
- DP-04风险: 实施风险中；Success schema若过宽会复制full artifact，过窄又无法replay。失效边界: 任何stage失败只返回Failure；不得同时携带partial problem；大数组用artifact ref/hash，不内联公共event。
- DP-04验证: Success/Failure exhaustive match；canonical JSON/hash roundtrip；冻结/深不可变测试；Failure序列化不含problem；Success不含CasADi/positional arrays；SYNC-07 transitional wrapper迁移后只有一个production assembly path。
- DP-04技术分解就绪度: semantic snapshot、failure、evidence与private numerical seam已由DP-04/17/18/19共同覆盖，未发现`DECOMPOSITION_INCOMPLETE`。
- 用户确认DP-04推荐；VR-04标记Step4 final，登记ALT-10..ALT-12。
- DP-05推荐草案(等待用户确认，尚未final): 分离三类identity。`CycleIdentity=(session_epoch,cycle_sequence,sim_time_s,lifecycle_input_hash)`标识运行实例；`assembly_request_hash`覆盖versioned normalized PlannerInput、accepted Lifecycle Snapshot、route/capability/ODD/profile、formulation identity及eligible previous-plan metadata；`semantic_problem_hash`只覆盖求解题的规范语义，不含solve id、artifact路径或墙钟。相同cycle可重算得到相同request/problem hash；不同cycle可产生相同semantic problem hash。[R5][R10][R11][R13][R15]
- DP-05权责: Stateless Assembler负责内部一致性校验、canonical hash计算和输出identity；Lifecycle负责同epoch/cycle的input conflict；Adapter/Session负责跨调用idempotency ledger、reset/time-rewind/algorithm-change authority。Assembler不得为检测retry保存隐式状态。[R10][R11]
- DP-05 canonical contract: SHA-256+versioned canonical JSON；mapping keys排序、tuple/list语义固定、enum用稳定value、仅finite SI数值、angle先ordinary unwrap/normalize、禁止绝对路径/对象repr/NaN/Infinity进入hash。schema/profile/formulation变化必须改变相应hash；artifact storage位置变化不得改变problem hash。[R10][R15]
- DP-05备选A: 只用`solve_id+sim_time`。弃用理由: reset复用、time rewind、同周期异题和跨session碰撞无法区分。
- DP-05备选B: 所有内容只算一个总hash。弃用理由: 无法区分“同一业务题不同cycle”与“输入/配置真正漂移”，cache、replay和审计语义混淆。
- DP-05备选C: 每次assembly生成随机UUID或含墙钟hash。弃用理由: 同request retry不幂等，golden/replay/cache均失效。
- DP-05风险: 实施风险中；主要风险是canonical float/schema演进、Lifecycle与Adapter identity字段version skew。失效边界: 非finite、identity/hash不一致、同cycle不同input hash、未知breaking schema必须typed `INPUT_CONFLICT/INVALID_INPUT`；不得自动重写identity。
- DP-05验证: dict/target输入顺序扰动hash不变；任一业务字段变化request hash变化；artifact路径/序列化空白变化problem hash不变；跨epoch同sequence不冲突；同epoch/cycle异hash RED；相同request重复输出byte-equivalent且无新增Lifecycle event。SYNC-01/SYNC-05列为合并后强制contract测试。
- DP-05技术分解就绪度: identity authority、canonicalization、retry/reset owner与evidence linkage已覆盖，未发现`DECOMPOSITION_INCOMPLETE`。
- 用户确认DP-05推荐；VR-05标记Step4 final，登记ALT-13..ALT-15。
- DP-06推荐草案(等待用户确认，尚未final): Assembler是OCP归一化唯一权威。Public/physical facts固定ENU、SI、rad；local OCP轴`x=North,y=East`，航海角`0=North`、顺时针为正，starboard course alteration为正。所有角度先相对reference ordinary unwrap，不独立wrap上下界。[R1][R4][R10][R17]
- DP-06状态分层: Snapshot保留physical ownship`position_NE,heading,surge,sway,yaw_rate,velocity_NE`及validity；frozen reduced projection严格使用`psi=physical heading,u=surge`以保MASS parity，不偷偷换成COG/SOG。Own COG/SOG仅作geometry/evidence，`course=heading+atan2(sway,surge)`,`speed=hypot(surge,sway)`；若sway/model mismatch超Planner ODD则`UNSUPPORTED_ODD`，具体阈值仍UNKNOWN。[R1][R14][R17]
- DP-06目标投影: target以finite`velocity_NE`为事实权威，`sog=hypot(vN,vE)`,`cog=atan2(vE,vN)`；明确stationary时允许`sog=0,cog=0`作为标注为`canonical_numerical_only`的无影响编码，不冒充观测航向。低速/航向validity tolerance来自versioned Planner ODD；观测不可用typed fail，不用0或上次值填充。[R17]
- DP-06坐标原点: 数值local origin可选本周期ownship改善conditioning，但必须把稳定world route anchor/target/hull evidence同一刚体平移到local frame；`route_frame.origin`不得因此被无条件重置`(0,0)`。translation进入snapshot/evidence，semantic world reference不随retry漂移。[R29]
- DP-06备选A: 用own COG/SOG替代frozen`psi/u`。弃用理由: 改变MASS方程与rate/decel语义，sway下不再parity。
- DP-06备选B: 把body surge/sway直接当North/East速度。弃用理由: 忽略heading rotation，目标几何、CPA和控制映射错误。
- DP-06备选C: 每个angle/bound独立wrap到`[-pi,pi]`。弃用理由: 穿越±pi时可把连续heading corridor翻转成空集/超大区间。
- DP-06风险: 实施风险中高，属于符号/单位高后果边界；主要风险是physical vs reduced vs COG混用、local translation丢route anchor、低速伪航向。失效边界: frame/unit/version不符、nonfinite、required heading无效、unsupported sway/mismatch必须typed fail。
- DP-06验证: 四象限NE速度→COG/SOG；sway非零时physical COG与core heading明确不同；±pi unwrap；world↔local roundtrip；route anchor平移不变cross-track；stationary target canonical编码不改变预测位置；SYNC-08与候选2facts做contract fixture。
- DP-06技术分解就绪度: physical facts、reduced projection、target packing、route translation与low-speed validity均已覆盖；仅model-mismatch数值阈值保留Planner ODD UNKNOWN，不构成`DECOMPOSITION_INCOMPLETE`。
- 用户确认DP-06推荐；VR-06标记Step4 final，登记ALT-16..ALT-18与SYNC-08。
- DP-07推荐草案(等待用户确认，尚未final): 输入明确分为`NominalRouteReference`、Lifecycle `ManeuverDirective`和`RecoveryAuthority`。L0 Route/LOS Adapter拥有稳定route segment id、world anchor、tangent/normal、corridor/progress、planned speed与rejoin reference；Lifecycle只拥有commit action/corridor及何时允许recovery；stateless Assembler将两者编译成OCP reference，不维护LOS积分或commit状态。[R1][R3][R10][R29]
- DP-07编译语义: semantic snapshot分离`heading_reference_rad`与`nominal_route_frame`。NOMINAL使用route tangent/LOS heading；COMMITTED使用Lifecycle可行corridor选定的heading reference和hard direction/min-alt，但cross-track soft cost继续相对原nominal route anchor/normal，不能把原航线覆盖成避让直线；RECOVERY使用L0提供的rejoin reference并受Lifecycle release/recovery authority门控。NumericalPreparer再映射到legacy`route_bearing_rad/route_frame`字段。[R7][R18][R29]
- DP-07 route更新: 每周期local translation允许变化，但world route segment/anchor必须带稳定id/provenance并同变换进入local frame。真正跨waypoint切换必须由L0显式发布新segment/progress并改变request hash；Assembler不得以当前本船位置重建“新航线”。
- DP-07 frozen能力边界: 当前core只表达一个constant heading reference+一条straight route frame，不能在1200s horizon内表达stage-varying curved/polyline corridor。当前Playground直线HO/CS/OT可支持；需要多段/曲线路径时typed`CORE_CAPABILITY_MISMATCH`，具体曲率容差保留Planner ODD UNKNOWN。[R29]
- DP-07备选A: 沿用当前COMMITTED时用commit course覆盖route bearing和route frame。弃用理由: 真实优化会沿新直线航行，丢失原航线cross-track/rejoin，正是当前预测长期直线的结构原因。
- DP-07备选B: 始终只用nominal LOS/reference，不向objective表达commitment。弃用理由: hard direction与heading objective持续对抗，可能增加slack/conditioning并弱化明显动作。
- DP-07备选C: 在Assembler内部保留stateful`LOSGuidance`和recovery rate limiter。弃用理由: retry会改变reference，reset/route authority与Lifecycle状态再次混入Assembler。
- DP-07风险: 实施风险中高；reference分离会改变当前HO/CS/OT objective形状，但不改frozen方程。失效边界: route segment identity缺失、rejoin reference与Lifecycle authority矛盾、曲线路径不表达时typed fail，不得回到current-position reanchor。
- DP-07验证: world/local translation后cross-track一致；commit只改变heading reference、不改变nominal anchor；release前禁止recovery、release后rejoin连续无跳变；same retry reference/hash相同；route segment切换显式改变hash；闭环OT/HO/CS出现真实避让+回归而非永久新直线。SYNC-09列为候选2合并后的强制迁移项。
- DP-07技术分解就绪度: nominal/commit/recovery owner、编译语义、route identity和frozen能力边界已覆盖；曲率容差保留具名UNKNOWN，不构成`DECOMPOSITION_INCOMPLETE`。
- 用户确认DP-07推荐；VR-07标记Step4 final，登记ALT-19..ALT-21与SYNC-09。
- DP-08推荐草案(等待用户确认，尚未final): admission分两步，先决定membership，再决定stable slot binding。Lifecycle Snapshot全量target先映射`REQUIRED/ELIGIBLE/EXCLUDED`：`REQUIRED`仅由accepted directive/locked action/Rule17 mandatory事实产生，全部必入；`ELIGIBLE`为健康、非required且预测在1200s内进入required/preferred interaction envelope者；其余`EXCLUDED`保留typed reason。不得在分层前truncate。[R9][R10][R19][R30]
- DP-08容量: 若`len(REQUIRED)>16`，返回`CAPACITY_EXCEEDED`并记录全部required TrackKey/count/core limit；不得挑“最危险16个”。否则先放全部REQUIRED，再按risk key给ELIGIBLE补至16。Lifecycle若已因同一容量fail-stop，Adapter直接传播其全量evidence；Assembler仍保留max16 invariant，防止绕过/版本漂移。[R10]
- DP-08 ranking/binding: ELIGIBLE membership rank使用typed lexicographic key：Lifecycle urgency→首次required-envelope违反时刻→首次preferred-envelope违反时刻→最小同步hull clearance→uncertainty margin→TrackKey，不做混合单位weighted score。选中集合确定后，cold numerical slot按TrackKey canonical排序，不按风险排名绑定；membership evidence保留risk rank。future warm-start slot policy另由DP-15控制。[R30]
- DP-08备选A: 当前approaching/TCPA/DCPA/range/id排序后直接`[:16]`。弃用理由: REQUIRED可静默丢失，policy与数值slot混在一个排序，输入排列/风险抖动影响problem identity。
- DP-08备选B: 只装REQUIRED，不纳入ELIGIBLE monitor。弃用理由: 无法用soft aspiration提前塑形，接近commit threshold才突然进入NLP，损害early action与warm continuity。
- DP-08备选C: 按tracker输入顺序绑定并padding到固定16。弃用理由: 非确定顺序改变prepared vectors/hash；padding改变frozen layout/parity且引入虚假目标。
- DP-08风险: 实施风险高，影响多目标安全与可解释性；主要风险是Lifecycle capacity preemption、risk metric单位/near-tie、required/eligible身份漂移。失效边界: required observation缺失、directive引用未知TrackKey、required>16、同TrackKey多episode冲突必须typed fail。
- DP-08验证: 0/1/16/17 required；17th required绝不丢；required在horizon外仍入；ELIGIBLE只补空位；输入排列和risk tie不改变selected set/slot order；risk轻微变化只影响membership evidence；每个excluded target有reason；SYNC-10与候选2capacity行为做合并contract。
- DP-08技术分解就绪度: tier、risk key、capacity、membership/slot分离与failure evidence已覆盖；near-tie epsilon仍为Planner ODD UNKNOWN，但TrackKey deterministic收尾保证同snapshot replay，不构成`DECOMPOSITION_INCOMPLETE`。
- 用户确认DP-08推荐；VR-08标记Step4 final，登记ALT-22..ALT-24与SYNC-10。
- DP-09推荐草案(等待用户确认，尚未final): v1唯一target predictor为versioned deterministic constant-velocity model。对每个全量target生成共同grid`t=0,15,...,1200s`共81点：`p(t)=p0+v_NE*t`；reference time必须与Cycle sim time一致或先按明确timestamp外推到cycle time。Lifecycle current geometry只作policy evidence，不作为第二套trajectory truth。[R7][R9][R17][R18]
- DP-09 covariance: state顺序固定`[N,E,VN,VE]`，`P(t)=F(t)P0F(t)^T+Q_profile(t)`；二维position envelope采用profile confidence与`lambda_max(Ppos)`的保守各向同性margin。`confidence=0.99`是Published Planner ODD选择，不是COLREG常数。缺process-noise authority时不得假装长期robust：God zero-cov可继续；KF/sensor profile要么提供versioned Q，要么标`UNCERTAINTY_UNSUPPORTED/OBSERVATION_UNUSABLE`。[R17][R21]
- DP-09 provenance: 每条Prediction保存TrackKey/episode、model id/version、state reference/observed/generated time、age/coasting/health/source、mean grid、covariance/margin grid、confidence/profile hash。Admission、CPA floor、L4和GUI必须引用同一Prediction id/hash，禁止各自重算。[R15][R17]
- DP-09 ODD边界: 1200s CV只对God/确定性定速目标和5s receding-horizon刷新有当前证据；不宣称对真实机动目标鲁棒。required target观测过期、state time语义不明、covariance非PSD或检测到超profile机动时typed fail；非required可EXCLUDED并留reason。真实maneuver target predictor是后续独立能力，不在v1补做。[R18]
- DP-09备选A: 延续当前80点`t=0..1185`或`t=15..1200`混用。弃用理由: 与80 interval/81 state contract不一致，首段或终点缺失，GUI/L4时间错位。
- DP-09备选B: 只传播CV mean，covariance固定不变或只用当前footprint。弃用理由: horizon越远不确定性不增长，admission与hard floor产生虚假精度。
- DP-09备选C: 本轮直接新增交互/MMG/多模型目标预测。弃用理由: 无目标控制输入/辨识authority/fixture，破坏最小IPOPT parity验证范围。
- DP-09风险: 实施风险高；1200s预测对timestamp、Q和maneuver mismatch敏感。失效边界: reference time不闭合、nonfinite/非PSD covariance、required track超age/coasting/profile、unsupported maneuver必须typed fail或限制ODD。
- DP-09验证: 81 timestamps严格递增且覆盖0/1200；解析CV mean；P(t)对称PSD、zero-cov God保持zero、Q存在时margin不减；measurement→cycle time alignment；stale required RED/nonrequired EXCLUDED；同Prediction hash贯穿admission/L4/GUI；SYNC-11与候选2TrackSnapshot contract合并测试。
- DP-09技术分解就绪度: mean、time alignment、covariance/envelope、provenance、degradation和ODD均覆盖；真实maneuvering target鲁棒性保留具名UNKNOWN/后续能力，不构成当前v1`DECOMPOSITION_INCOMPLETE`。
- 用户确认DP-09推荐；VR-09标记Step4 final，登记ALT-25..ALT-27与SYNC-11。
- DP-10推荐草案(等待用户确认，尚未final): 固定GridSpec=`N=80 intervals,dt=15s,state_count=81,horizon=1200s`。Control interval k覆盖`[t_k,t_{k+1}]`；raw frozen decision有80组`psi_k/u_k`并积分得到`t_1..t_80`的80个优化状态；public prediction在前面prepend实测`x_0@t=0`，绝不覆盖第一个优化点，形成81点。[R1][R2][R10][R16]
- DP-10多时间轴: semantic snapshot必须分别声明`STATE_TIME(k)=k*dt`、`CONTROL_INTERVAL(k)=[k*dt,(k+1)dt]`与parity-only `FROZEN_CPA_ROW(k): own@t_(k+1) vs target@t_k`。同步prediction/L4/UI使用同一state time；frozen错时row只作NLP/parity evidence，不能标成同步CPA。[R16][R22]
- DP-10 schedule map: 每个业务schedule保留原始physical seconds、time-axis、relation和映射残差，不只存k。`NOT_BEFORE`选首个axis time≥事件；`DEADLINE_NOT_AFTER`选最后axis time≤deadline；interval coverage使用覆盖完整承诺区间的control intervals。具体index由统一`PhysicalTimeMapper`按该row的axis计算，禁止全局统一floor/ceil和裸`-2 stages`。[R21][R27]
- DP-10兼容: MASS_PARITY继续保留frozen k+1/k方程与8条prepared/raw oracle；COLAV_STRICT另产生同步81点witness和业务schedule evidence。本候选不顺手修冻结方程索引；若未来修正，必须新formulation id/oracle corpus。[R2][R23]
- DP-10备选A: 当前mapper用80列并将第0列覆盖成实测状态。弃用理由: 丢失`t=15s`首优化点，末端时间和UI标签虚假。
- DP-10备选B: 所有schedule先转一个裸stage k并统一floor或ceil。弃用理由: activation/deadline/prefix语义相反，必然出现一stage偏差。
- DP-10备选C: 本轮直接修frozen CPA own(k+1)/target(k)索引。弃用理由: 破坏冻结MASS parity，扩大算法数学变更，需独立formulation defect ticket。
- DP-10风险: 实施风险高，属于off-by-one与安全claim高后果边界。失效边界: horizon/grid/schema不一致、schedule物理时间不在可映射域、public points不是81或parity row被误标同步时typed invariant failure。
- DP-10验证: index/time表0/1/79/80；public shape9×81和labels 0/15/1200；raw first optimized point保留；target与own state times完全一致；NOT_BEFORE/DEADLINE边界在0/14.9/15/15.1/1200；8条parity不变；SYNC-12候选2/UI合并contract。
- DP-10技术分解就绪度: grid、state/control/row axes、schedule relation、public mapping与parity split均覆盖，未发现`DECOMPOSITION_INCOMPLETE`。
- 用户确认DP-10推荐；VR-10标记Step4 final，登记ALT-28..ALT-30与SYNC-12。
- DP-11推荐草案(等待用户确认，尚未final): 固定三种独立量。`required_hull_clearance=50m`是同步连续实际安全门；`preferred_hull_clearance=150m`只作soft aspiration；`frozen_node_center_floor`是为旧方程服务的中心距数值bound，绝不在UI/trace命名为hull clearance。每个量携带unit/method/target/time/provenance。[R1][R2][R16][R22]
- DP-11 hull envelope: v1目标姿态不足，使用方向无关保守circumscribed radius。同步时刻每target center floor=`50m + R_own + R_target + uncertainty_margin + declared_model_margin`；preferred同理以150m换算。证据明确method=`circumscribed_radius_conservative`，不冒充精确旋转polygon distance。
- DP-11 parity quirk: frozen row比较own`t_(k+1)`与target`t_k`。要保证同步`t_(k+1)`距离D，保守frozen floor至少`D + target_displacement_bound(k→k+1)`，不是当前`own_speed_max*dt`。target displacement来自同一CV prediction/capability envelope；global scalar core只能取所有selected target/stage的最大floor。若该global overbound使题不可表达/不可行，typed`CORE_CAPABILITY_MISMATCH`，不得减少50m或重新启用slack。[R22]
- DP-11 continuous witness: L4输入使用81点同步own/target trajectory，逐段解析最小relative distance并减双方circumscribed radii/uncertainty；必须覆盖首段`t=0→15s`。Node rows、IPOPT status或frozen错时CPA均不能替代该witness。Assembler只产prediction/envelope/witness contract，不作最终Acceptance裁决。[R16][R33]
- DP-11备选A: 沿用`50+own radius+max target radius+own_speed_max*dt`。弃用理由: 错时补偿应界定target在15s内移动；target更快时存在已证反例，不是无条件保守。
- DP-11备选B: 直接把`cpa_hard_m=50`解释成中心距。弃用理由: 船体半径被遗漏，center 50m不等于hull clearance 50m。
- DP-11备选C: 只依赖15s node constraints。弃用理由: 两端安全可在区间中点相撞，且当前checker还漏首段。
- DP-11风险: 实施风险高，直接关系安全claim；global max可能过度保守、target displacement/model margin authority可能缺失。失效边界: required target缺hull/covariance/displacement bound、global floor超core表达域、swept witness缺首段时必须fail。
- DP-11验证: 不同船体尺寸/目标速度的per-target floor；target快于own反例；node endpoints安全但midpoint碰撞；首段碰撞；50/150与center/hull/m²字段不可混淆；global floor等于per-target最大值；SYNC-13候选2桥接公式迁移测试。
- DP-11技术分解就绪度: hard/preferred hull、center conversion、uncertainty、frozen quirk和continuous witness已覆盖；精确polygon clearance留future L4增强，conservative v1可完整判别，未发现`DECOMPOSITION_INCOMPLETE`。
- 用户确认DP-11推荐；VR-11标记Step4 final，登记ALT-31..ALT-33与SYNC-13。
- DP-12推荐草案(等待用户确认，尚未final): Assembler生成typed `ConstraintActivationPlan`，每条记录constraint class、target/common-corridor binding、physical start/end/deadline、time axis/mapping relation、mapped rows、reachability source与hard/soft class。禁止只传三个global`*_from_k`而丢物理语义。[R3][R4][R10][R21]
- DP-12安全层级: capability/rate/prefix equality全程hard；REQUIRED target的50m同步安全在prefix/uncontrollable段由独立witness先证明，frozen per-target CPA row从最早可控suffix持续到horizon；ELIGIBLE/MONITOR只启用150m soft barrier，不获得可松弛“hard”row。任何未受NLP控制的早期区间若witness不安全，直接`NO_SAFE_PLAN/UNSAFE_PREFIX`。[R16][R23]
- DP-12动作层级: Lifecycle已提交common maneuver corridor持续到achievement/release。Wrong-side direction row按最早可控时刻启用；full minimum-alteration row按`latest_safe_achievement_s`的`DEADLINE_NOT_AFTER`映射并持续到Lifecycle确认achievement/release；已达成但未release仍保持corridor/commitment，不依赖`newly_committed`单周期脉冲。具体deadline由Lifecycle/ODD给，Assembler只验证reachable window非空并映射。[R10][R19][R25]
- DP-12 representability: frozen CPA rows本来按target×stage存在，可用bounds实现per-target activation且不改graph。Direction/min-alt为global rows，只能编译Lifecycle已聚合出的共同course corridor；若不同target约束无共同表达或需要per-target direction row，返回`MANEUVER_CONFLICT/CORE_CAPABILITY_MISMATCH`，不得压成first/any-side。Terminal rowsv1保持disabled，直到有独立业务语义与oracle。[R23]
- DP-12备选A: 继续`cpa_hard_from_k=floor(minTCPA/dt)-2`。弃用理由: 裸heuristic无reachability/deadline语义，一个target控制全部target rows，15s/1200s变化即漂移。
- DP-12备选B: direction/min-alt只在`newly_committed`cycle启用。弃用理由: 后续cycle约束消失，优化回摆，commitment不再持续。
- DP-12备选C: 所有hard rows从k=0强开，若不可达就soften/slack。弃用理由: 把物理不可达误报NLP infeasible，或用soften吞掉真正hard安全。
- DP-12风险: 实施风险高；耦合Lifecycle achievement/deadline、reachability、frozen row表达能力。失效边界: deadline缺失/已过、reachable window为空、required早期witness失败、common corridor不表达时必须typed fail。
- DP-12验证: per-target REQUIRED/MONITOR不同CPA bounds；两个target不同TCPA互不控制；newly-committed后多cycle持续；achievement/release边界；deadline 14.9/15/15.1映射；unreachable deadline RED；terminal disabled；8条parity profile保持原bounds；SYNC-14与候选2fixture合并测试。
- DP-12技术分解就绪度: safety/action/terminal三类schedule、physical map、reachability与representability均覆盖；通用COLREG秒数明确不存在并由Lifecycle/ODD提供，未发现`DECOMPOSITION_INCOMPLETE`。
- 用户确认DP-12推荐；VR-12标记Step4 final，登记ALT-34..ALT-36与SYNC-14。
- DP-13推荐草案(等待用户确认，尚未final): AssemblyRequest显式携带三个versioned事实源：`PlantCapabilitySnapshot`、`GncTrackabilitySnapshot`、`MidMpcOddProfile`。Plant描述当前state、model id、Tchi/TU、turn-rate、accel/decel、absolute speed和control latency；GNC描述可跟踪course/speed/rate envelope、tracking error/latency与validity；Mid ODD描述reduced-model/search/formulation支持域。三者owner/hash分别保留，不合成一个YAML结构。[R3][R11][R12][R17]
- DP-13 stage envelope: 对`t_0..t_80`以active Plant exact rollout/reachable-set生成heading/speed/rate物理包络，再与GNC trackable envelope和Mid search/ODD逐stage求交，形成immutable`StageCapabilityEnvelope`。初始实测state单独固定，后续bounds必须非空、ordinary-unwrapped且rate/accel连续；static heading window只可作为Mid search limit，不是plant reachability。
- DP-13 v1 ODD: 当前只对KinematicCSOG+完整resolved capability facts声明支持；其一阶`Tchi/TU/r_max`可作为exact project plant oracle。其他dynamics、显著sway/model mismatch或缺GNC authority标`UNSUPPORTED_ODD/CAPABILITY_UNAVAILABLE`。状态落在plant absolute limits但在Mid search window外时v1 fail，不clip；controlled recovery corridor留具名UNKNOWN/后续能力。[R17]
- DP-13 STOP/速度: Lifecycle可请求STOP或lower bound=0，但Assembler仅在plant deceleration与GNC envelope证明stage-wise可达时编译；planned speed、absolute limit、reachable bound与optimizer bound分字段。不得用`speed_min=0.25`偷偷否定STOP，也不得直接把0写进全horizon而忽略减速率。
- DP-13备选A: 继续从`config/mid_mpc_ipopt.yaml`读取固定rate/decel/speed/heading window。弃用理由: 无active Ship/GNC authority，船模或运行状态变化时静默错误。
- DP-13备选B: 只取三类global min/max交集，所有stage相同。弃用理由: 忽略Tchi/TU、当前rate/speed、slew/latency，早期stage可达性虚假。
- DP-13备选C: 把frozen core rate/decel constraints反向当Plant/GNC能力证明。弃用理由: reduced surrogate不是独立物理oracle，形成循环论证。
- DP-13风险: 实施风险高；当前共享Interface缺完整capability/GNC facts，exact GNC oracle仍UNKNOWN。失效边界: 任一required authority缺失/过期、stage交集为空、STOP不可达、model id不支持时typed fail；不得填默认值。
- DP-13验证: KinematicCSOG解析/数值rollout envelope；不同Tchi/TU/rate产生不同早期bounds；Plant∩GNC∩ODD空集RED；STOP可达/不可达；当前state超search但未超plant仍fail；缺GNC hash/facts RED；SYNC-15候选2最小Maneuverability与完整CapabilitySnapshot边界测试。
- DP-13技术分解就绪度: 三事实源、stage intersection、v1 plant ODD、STOP和failure均覆盖；非Kinematic/GNC真实误差oracle保留具名UNKNOWN并限制能力声明，不构成当前v1`DECOMPOSITION_INCOMPLETE`。
- 用户确认DP-13推荐；VR-13标记Step4 final，登记ALT-37..ALT-39与SYNC-15。
- DP-14推荐草案(等待用户确认，尚未final): `CommittedPrefix`只表示执行层已经不可撤销接受的未来command interval，不表示previous optimum、当前hold reference或warm start。来源必须是versioned `ExecutionCommitmentSnapshot`，含command/ack ids、authority、absolute start/end、plant/GNC rollout、hash与reset epoch。当前CustomMPCAdapter没有多步queue/ack，因此Published v1强制`prefix_active_k=0`。[R11][R23][R27]
- DP-14 future K>0: 先验证commitment与Cycle epoch/time连续，再按absolute time映射到完整15s control intervals；frozen core只支持whole-stage`psi/u` equality。partial-stage commitment不可floor漏承诺，也不可ceil多冻结，返回`PREFIX_UNREPRESENTABLE/CORE_CAPABILITY_MISMATCH`，除非未来formulation支持partial interval。
- DP-14 safety/controllability: 在装配NLP前，用actual Plant/GNC rollout和81点target prediction对全部committed interval做连续50m hull witness及capability check；失败=`UNSAFE_PREFIX/NO_SAFE_PLAN`，不得soften CPA/direction或加slack。Prefix后必须存在Lifecycle deadline内的nonempty controllable suffix；所需长度由reachability/deadline算，不发明固定stage数。
- DP-14 reset/provenance: time rewind、session/algorithm/track authority change使commitment snapshot失效；Adapter reset清authority/cache，Assembler仍stateless。Prefix equality、witness、uncontrolled/controllable boundary和reason进入semantic snapshot/hash。
- DP-14备选A: 因solve period=5s或held control而固定K=1。弃用理由: 5s<15s且hold reference可在下次solve替换，不是15s不可撤销command。
- DP-14备选B: partial commitment统一ceil到下一15s stage。弃用理由: 过度冻结可吞掉唯一可控避让时间；floor则漏掉真实承诺。
- DP-14备选C: 将PreviousAcceptedPlan前若干点当prefix。弃用理由: 优化建议尚未ack，可撤销；会把旧episode/side错误锁死。
- DP-14风险: 当前v1 K=0实施风险低；未来K>0安全风险高且缺GNC/command authority oracle。失效边界: authority/ack/time/hash缺失、partial interval、prefix witness失败、suffix window为空必须typed fail。
- DP-14验证: 当前Adapter证据K=0；hold/resample不产生prefix；伪造K=1无ack RED；partial7s/15s/30s映射；unsafe prefix RED；deadline前suffix存在/为空；reset/epoch变化失效；8条MASS prefix fixture仅留parity profile，不证明production K>0。SYNC-16合并后重审。
- DP-14技术分解就绪度: authority、time mapping、whole-stage限制、safety witness、suffix与reset均覆盖；future K>0 oracle/最小suffix常数保留具名UNKNOWN且v1禁用，不构成当前`DECOMPOSITION_INCOMPLETE`。
- 用户确认DP-14推荐；VR-14标记Step4 final，登记ALT-40..ALT-42与SYNC-16。
- DP-15推荐草案(等待用户确认，尚未final): Assembler stateless；`PreviousAcceptedPlanRef`由Adapter/Orchestrator显式输入，只接受L4 accepted、同epoch、compatible formulation/grid/profile且有absolute timestamps/hash的计划。IPOPT Converged但L4拒绝、timeout-unaccepted、fallback/hold或旧epoch计划均不得作seed。[R6][R11][R24]
- DP-15 resample: 用`new_cycle_time + t_k`从旧计划absolute-time support重采样到新80×15 grid；heading先ordinary unwrap再插值/hold，speed按control semantics重采样。重叠区使用旧primal，尾部无support区由deterministic cold seed补齐；随后投影到StageCapabilityEnvelope并检查rate/decel/common corridor。禁止`shift(x,1)`，因为5s/15s不整除。[R27]
- DP-15 cold seed: 从当前reduced state沿capability envelope渐进朝`heading_reference/speed_reference`生成directive-guided deterministic initial guess；只保证finite、bounds、rate/decel/prefix equality，不宣称CPA-feasible。每次记录`seed_source/previous_plan_hash/resample_interval/projection_delta/rejection_reason`。Strict profile允许infeasible NLP initial guess，但不能靠hard slack伪装可行。[R18][R23]
- DP-15 warm terminology: v1仅启用previous-primal initialization，不启用dual multiplier warm start或IPOPT`warm_start_same_structure`声明。Graph cache与seed分开统计；diagnostics明确`primal_seed_used`、`dual_seed_used=false`、iterations/latency，不把单样本收益宣传为p95能力。[R24][R26]
- DP-15备选A: 每次只用current heading/speed广播cold seed。弃用理由: 可保持正确但浪费已接受轨迹的数值连续性；80×15微基准显示存在明显primal leverage。
- DP-15备选B: 旧raw x数组直接shift一个stage。弃用理由: 实际elapsed=5s而stage=15s，时间错10s，angle/target/capability变化未处理。
- DP-15备选C: v1立即启用primal+dual full warm start并remap multipliers。弃用理由: dual绑定row order/active bounds，当前每solve重建graph且无真实场景benchmark，收益和稳定性未证。
- DP-15风险: 实施风险中；主要风险是tail fill、angle interpolation、L4 acceptance identity和projection改变seed过大。失效边界: timestamp/support/hash不完整、epoch/formulation/grid不兼容或投影后仍违反numeric bounds时丢弃previous seed并用cold seed，不导致assembly失败。
- DP-15验证: 5s/15s absolute resample、±pi heading、尾部cold fill、target set改变、reset/epoch/formulation变化、L4 rejected plan禁用、projection/rejection provenance；cold/previous seed均满足numeric bounds；dual始终false；性能仅记录不设未经测量的提升门。SYNC-17候选2合并contract。
- DP-15技术分解就绪度: eligibility、absolute resample、tail、projection、cold seed、dual禁用与provenance均覆盖；真实p95收益/dual稳定性保留具名UNKNOWN，不构成`DECOMPOSITION_INCOMPLETE`。
- 用户确认DP-15推荐；VR-15标记Step4 final，登记ALT-43..ALT-45与SYNC-17。
- DP-16推荐草案(等待用户确认，尚未final): 同一frozen formulation下发布两个显式Assembly Profile。`MASS_PARITY`逐项保持8条oracle的prepared bounds/slack语义；`COLAV_STRICT`保留相同symbolic variables/layout，但将global`cpa_slack`与`direction_slack`都设`lb=ub=0`，所有required CPA/direction/min-alt/capability/prefix rows不可soften。Profile id进入request/prepared/evidence hash。[R2][R16][R23]
- DP-16 soft scope: 150m preferred clearance、nominal route、heading/speed tracking、comfort/control smoothness只存在objective；MONITOR目标不获得伪hard inequality。50m required hull、common committed corridor、stage capability与未来合法prefix是hard。Terminal rowsv1 disabled。Strict infeasible必须返回solver/acceptance failure，不切parity profile、不放slack、不fallback。
- DP-16 unit/evidence: frozen CPA slack单位m²；frozen direction slack历史上同时放松cross-track m和min-alt rad，量纲混合，故production只能固定0。逐row manifest记录unit/scale/target/stage/hardness；IPOPT success后按original unrelaxed bounds重检，允许数值diagnostic tolerance解释约`-1e-8`，但UI不得截断后称真实非负/无违反。[R20][R24]
- DP-16 identity: MASS_PARITY与COLAV_STRICT的prepared vectors/hash必然不同，不能要求同一golden；若仅改bounds，symbolic formulation id可相同、profile id不同。未来新增per-target direction row或修CPA索引必须升级formulation id并生成新oracle corpus。
- DP-16备选A: 保留可用slack但把L1/L2 penalty调极大。弃用理由: penalty不能使row变hard，global m²/m/rad slack仍可隐藏业务违反。
- DP-16备选B: production直接删除两个slack variables。弃用理由: 改graph/layout/indices，破坏frozen parity与cache复用；bounds固定0已能表达strict。
- DP-16备选C: 要求parity和strict共享完全相同prepared vectors。弃用理由: strict slack ub和per-target activation必然改变bounds，语义互相矛盾。
- DP-16风险: 实施风险高；strict可能降低收敛率，mixed-unit row tolerance需业务post-check。失效边界: hard row被任何slack/softening覆盖、profile/hash不一致、original-bound recheck失败必须拒绝结果。
- DP-16验证: 8条MASS oracle逐向量不变；strict同symbolic size/layout且两slack lb=ub=0；故意需要slack的case strict infeasible；prefix/required hard row无soft flag；raw约-1e-8按documented diagnostic tolerance处理但original-bound evidence保留；SYNC-18候选2双solver迁移测试。
- DP-16技术分解就绪度: profile split、hard/soft scope、slack units、identity与post-check均覆盖；完整strict闭环conditioning/p95保留具名UNKNOWN并由DP-20验证，不构成`DECOMPOSITION_INCOMPLETE`。
- 用户确认DP-16推荐；VR-16标记Step4 final，登记ALT-46..ALT-48与SYNC-18。
- DP-17推荐草案(等待用户确认，尚未final): Assembler只输出named immutable `NumericalPreparationPlan`：selected target bindings、GridSpec、stage capability bounds、ConstraintActivationPlan、strict/parity slack policy、SeedPlan、audit/evidence refs和semantic/structural signatures。它不创建positional arrays。Private Mid-MPC core内唯一`NumericalPreparer+LayoutAuthority`把该plan编码为`p/x0/lbx/ubx/lbg/ubg`。[R4][R6][R13][R23]
- DP-17 manifest: LayoutAuthority与symbolic graph builder共享同一versioned `MidMpcLayoutManifest`，列出decision slices、parameter slots、row block→target/stage/unit/hardness映射、sizes和formulation id。Prepared result携带`problem_hash/preparation_plan_hash/layout_hash/prepared_hash`，允许parity/exporter诊断读取，但不成为Integration public API。
- DP-17 structural/cache: semantic plan产生`StructuralSignature=(formulation id,N,dt,target_count,audit_row_count,slack-variable topology,terminal/layout version)`；graph cache归solver/core，不归Assembler。相同signature可复用graph，不足16目标不padding；per-target CPA activation和strict slack ub只改bounds，不改signature。新增row/修index必须新formulation/layout version。[R23][R26]
- DP-17 policy migration: 当前`_prepare`中的cold seed、广播bounds、slack ub、prefix softening和CPA activation业务决定迁到Assembler named plan；core只验证manifest并机械pack。任何offset只能在LayoutAuthority定义一次，禁止Assembler与solver各维护副本。
- DP-17备选A: Public AssemblyOutcome直接携带prepared arrays。弃用理由: 上层绑定backend slots，layout升级成为跨层breaking change。
- DP-17备选B: Assembler和solver分别维护offset/row math，再比较hash。弃用理由: 双实现迟早错位，hash只能发现不能消除authority冲突。
- DP-17备选C: 保持所有seed/bounds/slack/schedule policy在`_prepare`。弃用理由: public semantic snapshot不完整，replay看不出实际求了什么题，L1继续隐藏在L3。
- DP-17风险: 实施风险中高；迁移policy时最易破坏8条prepared parity，cache引入后还可能错复用graph。失效边界: plan/layout/formulation hash不匹配、size/row mapping不闭合、未知signature必须拒绝prepare，不猜offset。
- DP-17验证: 8条oracle prepared arrays逐项不变；semantic plan→manifest→arrays roundtrip；每row反查target/stage/unit；strict与parity同signature但不同prepared hash；target_count不同signature；input排列不影响canonical binding；故意layout version错配RED；cache hit/miss不改变raw result。SYNC-19候选2合并边界测试。
- DP-17技术分解就绪度: named plan、private codec、single layout authority、manifest/hash与cache key均覆盖，未发现`DECOMPOSITION_INCOMPLETE`。
- 用户确认DP-17推荐；VR-17标记Step4 final，登记ALT-49..ALT-51与SYNC-19。
- DP-18推荐草案(等待用户确认，尚未final): 所有expected assembly domain failure返回immutable versioned `AssemblyFailure`，至少含`cycle_identity/request_hash/failed_stage/layer/code/normalized_status/owner/recoverability/reason/evidence_refs`，且Success字段/partial problem为空。Unexpected programming/dependency exception不伪装成domain infeasible，保留原异常链并由Session fail-stop。[R10][R14][R31]
- DP-18 code families: INPUT=`INVALID_SCHEMA/INVALID_FRAME/NONFINITE/INPUT_CONFLICT/OBSERVATION_UNUSABLE`；CAPABILITY=`CAPABILITY_UNAVAILABLE/UNSUPPORTED_ODD/EMPTY_STAGE_ENVELOPE/STOP_UNREACHABLE`；ASSEMBLY=`CAPACITY_EXCEEDED/MANEUVER_CONFLICT/CORE_CAPABILITY_MISMATCH/SCHEDULE_UNREACHABLE/PREFIX_UNREPRESENTABLE/UNSAFE_PREFIX`；INVARIANT=`HASH_MISMATCH/LAYOUT_MISMATCH/INVARIANT_VIOLATION`。Lifecycle同名code保留upstream owner，不由Assembler重写根因。
- DP-18 shared mapping: 不扩大全仓`PlanStatus`。Assembly detail code映射现有`INVALID_INPUT/INFEASIBLE/NUMERICAL_FAILURE`中的合适外层状态，并通过`ColavExecutionError.details`保真；`FailureSource`保持现有兼容值，同时details写具体`owner_layer=ASSEMBLER/CAPABILITY/LIFECYCLE`。Adapter只做机械转换，不选择算法或控制。
- DP-18 recoverability: `REFRESH_INPUT_THEN_NEW_SESSION`、`RESET_SESSION`、`FIX_CONFIGURATION`、`CHANGE_PROFILE_OR_CORE`、`TERMINAL_FOR_RUN`五类仅作修复提示。当前SimulationSession异常即FAILED，因此没有同session自动retry；恢复必须显式新session/reset。相同immutable request原地重试不得换题、不得产生新Lifecycle event。
- DP-18备选A: bridge继续抛`ValueError(str)`。弃用理由: code/owner/identity/recoverability丢失，GUI和测试只能匹配文本。
- DP-18备选B: 为每个detail code扩展shared`PlanStatus`。弃用理由: 扩大全算法/GUI/manifest blast radius，且混淆跨算法normalized status与Mid专属根因。
- DP-18备选C: failure后返回last plan/nominal/其他算法并标SUCCESS。弃用理由: 违反用户no-fallback，隐藏本周期Mid-MPC未执行与安全失效。
- DP-18风险: 实施风险中；主要风险是Lifecycle/Assembler重复code、HTTP/trace丢details、expected与unexpected exception误分类。失效边界: 未知code/version、Failure携带partial problem、Adapter吞错或Session继续运行均为contract violation。
- DP-18验证: 每个family至少一条public-seam RED/GREEN；Failure JSON roundtrip；Lifecycle upstream owner保留；ColavExecutionError details与HTTP/PlannerTrace一致；session进入FAILED；fallback_used=false/executed_algorithm不变；last plan不返回；unexpected exception保留cause。SYNC-20候选2合并测试。
- DP-18技术分解就绪度: taxonomy、outer mapping、owner、recoverability、no-fallback与unexpected error边界均覆盖，未发现`DECOMPOSITION_INCOMPLETE`。
- 用户确认DP-18推荐；VR-18标记Step4 final，登记ALT-52..ALT-54与SYNC-20。
- DP-19推荐草案(等待用户确认，尚未final): 保留planner-neutral `PlannerTrace schema_version=1.x`外层，Mid内部采用独立versioned namespaces：`lifecycle`(候选2)、`assembly`(候选3)、`solver`、`acceptance`。证据链固定`Problem hash→PreparationPlan hash→Layout/Prepared hash→RawSolver hash→Acceptance hash`，每层immutable、只引用上游hash，不共同mutation一个free-form dict。[R10][R15][R32]
- DP-19 inline summary: 每个planner event只内联cycle/problem/profile/formulation identity、selected/required/excluded counts+ids、reference/capability/activation/seed摘要、solver status/iterations/latency/objective、acceptance verdict/min hull clearance/max violation、failure code和`artifact_ref/hash`。固定schema自然有界，并设工程门`compact JSON≤8KiB`；不内联81×16 grids、1843 rows或prepared/raw vectors。
- DP-19 full artifact: content-addressed、per-solve、atomic gzip JSON保存normalized request/snapshot refs、81点own/target predictions、uncertainty/capability envelopes、activation/seed plan、layout manifest、prepared arrays、raw x/f/g、逐row evidence、solution/acceptance witness。16-target实测约216315B raw/48366B gzip，120 solves约25.96MB raw；retention TTL/quota/sink属于Experiment infrastructure，仍是具名UNKNOWN，不进入控制语义。[R32]
- DP-19 GUI/replay: GUI只消费typed render projection和artifact endpoint，不重算CPA/prediction/route truth；target坐标统一north/east schema或明确renderer转换，修复当前`north_m/east_m`对`x/y`错配。Artifact hash不含绝对路径，移动存储不改变内容identity；sink失败标`EVIDENCE_INCOMPLETE`，不能宣称该run完成验收。[R10][R15]
- DP-19备选A: full grids/rows/vectors全部塞进每帧PlannerTrace。弃用理由: 16-target每solve约216KB，session/websocket/内存膨胀且hold frames重复。
- DP-19备选B: 只留inline摘要，不保存full artifact。弃用理由: 无法重放prepared/raw rows、解释solver/acceptance分歧或证明真实轨迹来源。
- DP-19备选C: 继续向`algorithm_details/constraints`添加临时keys。弃用理由: 无version/单位/owner，候选2/3和GUI会互相覆盖并漂移。
- DP-19风险: 实施风险中；主要风险是跨线程schema冲突、artifact写入影响控制路径、JSON nonfinite和retention无界。失效边界: hash链断裂、namespace version不兼容、inline超8KiB、artifact声明存在但不可读时evidence gate失败；planner solve本身不得等待远端sink。
- DP-19验证: schema/json roundtrip且无NaN/Infinity；inline≤8KiB；16-target artifact gzip/read/hash；problem→acceptance链逐层校验；hold frame不复制artifact；candidate2 lifecycle keys与assembly keys互不覆盖；GUI显示同一81点/target prediction；sink failure产生EVIDENCE_INCOMPLETE。SYNC-21合并contract。
- DP-19技术分解就绪度: namespace、hash链、inline/full分层、storage/GUI/replay与failure均覆盖；长期TTL/quota保留Experiment policy UNKNOWN，不构成Assembler`DECOMPOSITION_INCOMPLETE`。
- 用户确认DP-19推荐；VR-19标记Step4 final，登记ALT-55..ALT-57与SYNC-21。
- DP-20推荐草案(等待用户确认，尚未final): 采用六层不可互相替代的verification gates。A=`Assembler contract`纯函数/对抗/identity/hash/failure；B=`MASS_PARITY` 8条C++ oracle prepared/raw/objective；C=`COLAV_STRICT` hard bounds/slack0/per-target schedule/original-bound+swept witness；D=`closed-loop behavior`；E=`8010 runtime/UI/artifact`；F=`full repository regression`。[R2][R10][R23][R33]
- DP-20 Gate D: 至少HO、CS give-way、CS stand-on、OT左右镜像、overtaken、noncooperative Rule17、多目标conflict/capacity及现有multiship。每case断言真实`mid_mpc_ipopt/CasADi-IPOPT`、no fallback、Ship0无collision/grounding、同步conservative hull clearance≥50m、role/action/passing side与accepted Lifecycle一致、commit/achievement/release/recovery和route progress正确。目标船脚本互撞照实记录但不算Ship0 Mid-MPC失败。
- DP-20 Gate E/F: 8010必须出现真实planner solve event，solver_executed/status/iterations/latency/objective/selected targets/hash/artifact可读；GUI own/target均81点并标0..1200s，Planner/Evaluator来源分开。最后跑scoped lint/format/diff check、全部pytest；任何focused pass不得替代full suite。
- DP-20 performance/evidence: strict 0/1/16-target记录cold/cache p50/p95/max、iterations、graph/solve split、memory/artifact size；hard运行门为`p95≤configured deadline 20s`，5s solve period只作为优化目标，未达不得宣称real-time 5s。当前单样本结果冲突且不构成capability；必须在最终代码/机器重测。[R26][R32]
- DP-20备选A: 只沿用G3 capability/scenario PASS。弃用理由: 不能证明assembly确定性、strict slack、81点、failure/hash或真实prepared题。
- DP-20备选B: 只跑unit+MASS parity。弃用理由: 不能证明真实执行、通过侧、hull clearance、recovery、8010/GUI和no fallback。
- DP-20备选C: 为PASS降低50m、缩短目标集合、加fallback或场景特例。弃用理由: threshold cheating，直接违背用户验收边界。
- DP-20风险: 实施/验收风险高；候选2并行改同一integration/tests/UI，strict 16-target latency和完整GNC capability仍未证。失效边界: 任一Gate失败不得提升capability或宣称“全部场景PASS”；需按owner定位回Lifecycle/Assembler/Solver/L4/Runtime。
- DP-20验证矩阵细项: A覆盖0/16/17、bad frame/time/hash/capability/prefix/replay；B固定8 fixtures且expected不改；C覆盖两profile/row units/slacks/swept first segment；D固定seed/God/KinematicCSOG与COLREG行为；E真实8010+artifact/renderer；F全仓。SYNC-01..SYNC-22全部在候选2合并后标`MATCHED`或新矛盾回炉。
- DP-20技术分解就绪度: contract/parity/strict/behavior/runtime/regression与performance均覆盖；真实GNC/机动目标/5s p95仍作为能力限制而非当前PASS前提，未发现`DECOMPOSITION_INCOMPLETE`。
- 用户确认DP-20推荐；VR-20标记Step4 final，登记ALT-58..ALT-60。
- Step4完整性检查: DP-01..DP-20均有已确认推荐、证据链、弃用理由、风险、失效边界与验证；TD-01全部子模块已综合，无`DECOMPOSITION_INCOMPLETE`。Step4 gate通过，暂停等待用户授权进入Step5 DESIGN-IT-TWICE。

### Step5 · DESIGN-IT-TWICE 方案对比 [2026-08-11]

- 用户授权进入Step5。
- 对比对象分组草案（等待用户确认）:
  - CARD-01 `Module architecture and authority`: DP-01..DP-05、DP-17、DP-18。比较深语义Assembler、现状式Facade浅Builder、public staged/numerical pipeline；覆盖authority、snapshot、identity、failure、semantic/numerical seam。
  - CARD-02 `OCP semantic assembly and safety`: DP-06..DP-16。比较显式物理语义+strict profile、frozen-parity单配置、场景策略化装配；覆盖坐标/参考、预测/admission、grid、clearance/schedule、capability/prefix/seed、hard-soft。
  - CARD-03 `Evidence and acceptance`: DP-19..DP-20，并跨接全部DP。比较hash-linked分层证据+六Gate、inline-only G3、full-inline monolithic trace；覆盖replay、GUI、8010、closed-loop、full regression、性能门。
- 低风险跳过项草案: 无。DP-01..DP-20全部进入上述三张完整卡片，不以“低风险”静默直接采纳。
- 跨线程要求: 三张卡均把SYNC-01..SYNC-22作为candidate2完成后的合并前置校验；candidate2当前仍在独立worktree实施，未把其进行中DTO/bridge当冻结事实。
- 用户确认CARD-01..CARD-03分组；无低风险跳过项。

#### CARD-01 草案: Module architecture and authority（等待用户裁决）

| 维度 | 方案A: Deep Semantic Assembler + Private Numerical Codec | 方案B: Facade Orchestrator + Thin Builder | 方案C: Public Staged/Numerical Pipeline |
|---|---|---|---|
| 完整描述 | `MidMpcProblemAssembler.assemble(request)->AssemblyOutcome`是唯一public seam；消费validated input、immutable Lifecycle snapshot、capability与previous accepted plan；私有纯stage生成semantic snapshot和named preparation plan；core私有codec/layout authority打包数值；typed failure原子返回 | Facade继续拥有reference/admission/schedule/capability/seed；thin builder只构造legacy `MidMpcProblem`；solver `_prepare`拥有bounds/layout；Adapter/Facade维护retry和错误转换 | normalization、prediction、admission、schedule、seed、prepare各成public stage；stage DTO显式串联；最后public numerical DTO暴露`p/x0/lbx/ubx/lbg/ubg`；pipeline runner汇总错误 |
| 来源 | [R1][R3][R4][R6][R23][R28]；MASS current pure builder/solver责任切分与本项目frozen core一致 | [R1][R2][R23]；接近当前Colav实现与candidate2临时bridge，已有G3运行证据 | [R6][R10][R15]；通用data pipeline思想，项目内无第二Assembler/backend需求 |
| 工程验证 | MASS当前分层提供结构证据；Colav现有pure solver/parity seam可复用；完整方案尚未在本项目生产闭环，需实现验证 | 本项目已有单船/多船G3和8010运行；但Facade混责、字段漂移、schedule/allowance缺陷已被实际诊断 | 无本项目生产验证；只有通用pipeline可组合性经验，未证明适配IPOPT固定layout与实时控制周期 |
| 技术分解 | authority✓ snapshot✓ identity/hash✓ atomic outcome✓ semantic L1✓ named L2✓ private layout✓ typed failure✓ no-fallback✓ | authority△（分散） snapshot△ identity△ semantic L1△ numerical L2△ typed failure✗ private layout✓ no-fallback△ | authority△ snapshot✓ identity✓ semantic L1✓ numerical L2✓ typed failure✓ private layout✗（vectors公开） no-fallback✓ |
| 失效边界 | Lifecycle schema/version不匹配、capability缺失、required targets>16、layout version冲突时fail-closed；若私有stage偷藏state或candidate2 bridge并存则方案失效 [SC-05][SC-10] | Facade继续同时演进Lifecycle/assembly/result mapping时出现双authority；retry/reset、target order、单位或row policy漂移；缺陷只能在闭环末端发现 [SC-01][SC-10] | stage版本/顺序组合爆炸；调用者可跳过stage或篡改prepared arrays；layout变化传播到integration/tests；实时路径出现过多DTO和序列化边界 [SC-05][SC-09] |
| 实现风险 | 中高：需迁移candidate2临时bridge、冻结handoff、拆semantic policy与private codec；但改动集中且deletion test成立 | 低短期/高长期：最少迁移，但已知混责和缺陷保留，后续每个场景修复继续跨层 | 高：新public API数量最大；迁移、版本、维护、误用面均高，当前没有插件或第二backend收益 |
| 可测性 | 纯`assemble`覆盖0/16/17、bad identity/hash/capability/prefix/replay；private codec用8条oracle parity；public seam断言typed failure与no partial output | 主要依赖Facade/integration/closed-loop；单独证明assembly determinism、failure owner、semantic hash困难 | 每stage可unit test；但还需大量非法stage组合、version matrix、bypass与vector tamper测试 |
| 推荐度 | ★★★★★ | ★★☆☆☆ | ★★☆☆☆ |

- 初步裁决: 推荐方案A。它唯一同时满足高Module Depth、窄public Interface、semantic replay、private layout authority、typed fail-closed和frozen parity。
- 拟弃用方案B: 短期最省改动，但没有消除当前根因；candidate2 `mid_mpc_assembler.py`只能作为迁移bridge，不能成为长期边界。
- 拟弃用方案C: 可测性表面更强，但公开stage/vector造成浅Module、调用顺序依赖与layout泄漏；当前无扩展需求抵消复杂度。
- SYNC对齐: 方案A要求candidate2最终只交权威Lifecycle snapshot/failure/evidence；候选3迁移并删除临时assembly policy。重点复核SYNC-01..SYNC-07、SYNC-17..SYNC-20。
- 用户确认CARD-01采纳方案A、弃用B/C；登记VR-21、ALT-61..ALT-62。

#### CARD-02 草案: OCP semantic assembly and safety（等待用户裁决）

| 维度 | 方案A: Explicit Physical Semantics + COLAV_STRICT | 方案B: Frozen-Parity Single Profile | 方案C: Encounter-Specific Problem Builders |
|---|---|---|---|
| 完整描述 | 全部输入先归一为ENU/SI/rad；分离nominal route、maneuver directive、recovery authority；全量targets做REQUIRED/ELIGIBLE/EXCLUDED与canonical slots；CV生成81点mean/envelope；业务约束按物理秒编译；50m同步船体hard、150m soft；stage capability envelope、K=0 prefix、validated warm seed；生产hard slack ub=0，另保MASS_PARITY profile | 直接采用frozen MASS变量、全局route bearing/global target rows、CV参数和80决策；单一profile保留原slack、global floor、k+1/k错时、global schedule/static bounds；以oracle等价和solver可行为主要正确性 | HO、CS-GW、CS-SO、OT、overtaken、Rule17分别使用专用reference、target selection、CPA floor、schedule、seed和权重；按场景调参满足各自闭环；共享同一IPOPT core但问题装配分支化 |
| 来源 | [R6][R7][R8][R9][R11][R16][R18][R20][R22][R23][R25][R27]；物理语义、COLREG职责与frozen parity边界同时保留 | [R2][R16][R23]；8条C++ oracle与当前Python core提供强数学等价证据 | [R1][R10][R29]；当前Facade已有按encounter directive/commitment的局部分支，场景调试可快速得到单case结果 |
| 工程验证 | 各组成能力已有项目/标准/论文证据；strict bounds、per-target schedule、full capability envelope尚需本项目闭环和性能验证 | MASS parity与本项目8 fixtures已验证；当前G3场景也基于该core，但不证明strict hard或同步船体安全 | 本项目历史场景校准能产生PASS；但OT左/右、commit flicker、stand-on与multitarget已展示分支策略脆弱性 |
| 技术分解 | frame✓ reference✓ admission✓ prediction✓ 80/81 grid✓ safety semantics✓ activation✓ capability✓ prefix✓ seed✓ parity/strict split✓ | frame△ reference△ admission△ prediction✓ grid△ safety△ activation△ capability△ prefix✗ seed△ hard/soft✗ | frame✓ reference△ admission△ prediction✓ grid✓ safety△ activation△ capability△ prefix△ seed△ hard/soft△；各场景重复实现 |
| 失效边界 | 缺失GNC facts、required>16、uncertainty不可界、unsafe prefix、strict infeasible时typed fail；CV只适用非机动目标，5s p95与真实GNC仍是能力限制 [SC-03][SC-05][SC-09] | node可行但swept碰撞、soft slack掩盖hard违约、目标错时和static bounds不可跟踪时仍可能返回SUCCESS [SC-06][SC-07] | 新几何/镜像/多目标冲突落不到已有分支；同一物理规则在分支间漂移；通过调阈值造成场景过拟合 [SC-02][SC-04][SC-08] |
| 实现风险 | 高：覆盖语义最多，需保持8 oracle不变并引入strict profile；风险可按stage和Gate隔离 | 低：最少变更；但安全与COLREG claim风险高，已知缺陷被制度化 | 高：初期快、长期组合爆炸；测试场景数随分支乘法增长，无法给统一能力声明 |
| 可测性 | 纯assembler property/contract；8 oracle parity；strict row/slack/witness；HO/CS/OT镜像、Rule17、capacity、multitarget闭环 | oracle parity强；同步船体hard、passing side、trackability只能由外部测试补洞，题内无法证明 | 单场景容易测；跨场景不变量、镜像、任意几何、target order和新COLREG组合难以穷举 |
| 推荐度 | ★★★★★ | ★★☆☆☆ | ★☆☆☆☆ |

- 初步裁决: 推荐方案A。它保留MASS parity作为研究profile，但不把parity quirks误当生产安全语义；所有场景共享同一物理装配规则。
- 拟弃用方案B: 数学等价必要但不充分。单profile无法证明50m同步船体hard、可跟踪性或COLREG maneuver quality。
- 拟弃用方案C: 直接违反无场景特例/不调低阈值边界；局部PASS不能形成统一Mid-MPC能力。
- SYNC对齐: 重点复核SYNC-08..SYNC-18；candidate2负责role/action/commit/recovery facts，Assembler只编译，禁止再次按HO/CS/OT分类。
- 用户确认CARD-02采纳方案A、弃用B/C；登记VR-22、ALT-63..ALT-64。

#### CARD-03 草案: Evidence and acceptance（等待用户裁决）

| 维度 | 方案A: Hash-Linked Tiered Evidence + Six Gates | 方案B: Inline G3/Scenario Evidence Only | 方案C: Full Synchronous Monolithic Trace |
|---|---|---|---|
| 完整描述 | `lifecycle/assembly/solver/acceptance`独立versioned namespace，以Problem→Preparation→Prepared→RawSolver→Acceptance hash链接；planner event内联≤8KiB稳定摘要，81点grids/rows/vectors存content-addressed gzip artifact；GUI只消费typed render projection；验收依次经过Assembler、MASS parity、COLAV_STRICT、closed-loop、8010、full regression六Gate | 继续使用现有PlannerTrace/free-form details、capability G3与场景断言；GUI从inline字段重构轨迹；solver success、场景PASS和少量实时事件作为主要证据；不保存完整prepared/raw replay artifact | 每次solve把normalized input、81×targets prediction、activation、layout、prepared arrays、raw x/f/g、row witness、solution、acceptance全部同步写入单个PlannerTrace/event并持久化；GUI和测试直接读取该大对象 |
| 来源 | [R10][R15][R23][R26][R28][R32][R33]；本地体积实验、现有parity与分层责任提供直接证据 | [R1][R10]；当前仓库G3 capability、场景tests、8010 event已有工程运行 | [R10][R32]；全量记录具备最大单事件自包含性，但项目内无工程验证 |
| 工程验证 | 现有oracle/closed-loop/8010/full suite各自已验证部分Gate；hash链和artifact分层为新组合，candidate2也在实现lifecycle evidence，最终需合并验证 | 当前项目运行最成熟，能快速展示算法与场景PASS；已出现target schema mismatch、cost隐藏、证据来源混淆 | 本地测得16-target单solve约216KB raw/48KB gzip；尚无高频session/websocket/retention工程验证 |
| 技术分解 | schema/version✓ provenance/hash✓ compact event✓ full replay✓ GUI projection✓ parity✓ strict✓ behavior✓ runtime✓ regression✓ performance✓ | schema△ provenance✗ replay✗ GUI△ parity△ strict✗ behavior✓ runtime✓ regression△ performance△ | schema✓ provenance△ replay✓ GUI✓ parity✓ strict✓ behavior✓ runtime△ regression✓ performance✗ |
| 失效边界 | hash断链、artifact不可读、namespace冲突、inline>8KiB时evidence gate失败；artifact sink不能阻塞控制；任一Gate失败不得提升capability [SC-09][SC-10] | solver success但装配/strict/continuous safety错误仍可能标G3；field drift静默丢轨迹；focused/scenario pass被过度外推 [SC-01][SC-06] | 16-target×长session造成websocket/session内存、IO和retention膨胀；同步持久化影响20s deadline甚至控制周期 [SC-05][SC-09] |
| 实现风险 | 中高：需schema、artifact store、hash canonicalization、renderer与六Gate；但每层owner明确，可逐slice实现 | 低：沿用现状；证据完整性和诊断风险高，无法回答“轨迹是否真实题解” | 高：实现看似直接，但性能、存储、UI transport、nonfinite JSON和重复hold frame风险最大 |
| 可测性 | schema roundtrip、hash tamper、artifact gzip/read、≤8KiB、8 oracle、strict witness、场景矩阵、真实8010、full pytest、0/1/16 target p95 | 场景与HTTP易测；无法独立重放prepared题、row violation或证明GUI与solver同源 | 单artifact内容易断言；需额外压力测试payload、IO、websocket、retention和deadline，且failure会污染控制路径 |
| 推荐度 | ★★★★★ | ★★☆☆☆ | ★☆☆☆☆ |

- 初步裁决: 推荐方案A。它在可观测性、可重放与运行时成本间唯一形成明确分层，并让G3、parity、strict、行为和runtime claims互不替代。
- 拟弃用方案B: 工程现状可保留为迁移起点，但无法形成Assembler/L2的可信验收证据。
- 拟弃用方案C: 单事件自包含不等于可运行；已测payload规模足以使同步大trace成为deadline与存储风险。
- SYNC对齐: candidate2只写`lifecycle` namespace与其event refs；候选3写`assembly`，solver/acceptance各自独立。最终按SYNC-21/22验证namespace不覆盖、hash链闭合、共同场景与全仓通过。
- 用户确认CARD-03采纳方案A、弃用B/C；登记VR-23、ALT-65..ALT-66。
- Step5完整性检查: CARD-01..CARD-03均含来源、工程验证、完整技术分解、失效边界、实现风险、可测性、推荐度七维；DP-01..DP-20全部覆盖，无低风险跳过项；每张卡已逐张获用户裁决。Step5 gate通过，暂停等待用户授权进入Step6术语表、技术规约与八组件方案包。

### Step6 · 术语、技术规约与方案包 [2026-08-11]

- 用户提供Candidate 2最终handoff并接受Candidate 3方案包。权威起点=`marine/main@b94148c1e91a90830bfac6cf1a6d61b9509e7e70`；Candidate 2 Issue #24关闭；baseline=`441 passed,2 skipped`、OT双镜像真实IPOPT PASS、8010 81点/15s/0..1200s。
- 已读取上游线程`019fe958-c44a-7052-95dc-1b6f4e22e302`、handoff、Candidate 2 solution pack、final source、七层文档和`mid-mpc-architecture-review-20260810-180251.html`。
- 最终SYNC复核:
  - MATCHED: SYNC-02/05/06/08/12/16/22。复用TrackKey/health/decision facts、epoch/retry/RESET evidence、ENU facts、81点轨迹、K=0与Candidate 2验收。
  - PARTIAL: SYNC-01/03/04/09/10/11/15/20/21。Candidate 3只补request schema/hash、per-target bindings、stable route/prediction/capability/failure/assembly namespace，不改变Lifecycle authority。
  - MIGRATE/FIX: SYNC-07/13/14/17/18/19。替换transitional assembler；target-step allowance；physical activation；cold/accepted seed contract；parity/strict profiles；private numerical codec。
- 方案包八组件齐全: 术语表、TS-01..25、CARD-01..03、证据矩阵、TD完整树、ALT-01..66、场景/六Gate、已知限制。
- pre-agreed TDD seams: `MidMpcProblemAssembler.assemble`、`MidMpcIpoptSolver.solve`、`CustomMPCAdapter.plan`、`P1RunHarness/8010 event`。来自CARD-01..03用户确认，不新增访谈。
- 交付文件:
  - `docs/superpowers/specs/2026-08-11-mid-mpc-l1-l2-problem-assembler-solution-pack.md`
  - `docs/superpowers/specs/2026-08-11-mid-mpc-l1-l2-problem-assembler-design.md`
  - `docs/superpowers/plans/2026-08-11-mid-mpc-l1-l2-problem-assembler-implementation.md`
- Step6 gate: 术语完整；技术规约无未定字段；八组件齐；契约明确；无`DECOMPOSITION_INCOMPLETE`。用户已明确接受并要求连续执行`to-spec→implement+tdd→code-review`，标记已交付to-spec。
- to-spec已发布GitHub Issue #25: `https://github.com/marinehdk/colav-simulator/issues/25`，label=`ready-for-agent`。
