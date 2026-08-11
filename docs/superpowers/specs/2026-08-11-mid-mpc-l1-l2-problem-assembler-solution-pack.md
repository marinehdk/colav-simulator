# 方案包：Mid-MPC L1/L2 Problem Assembler 深化

> **创建**: 2026-08-11
> **权威起点**: `marine/main@b94148c1e91a90830bfac6cf1a6d61b9509e7e70`
> **来源**: `docs/superpowers/design-logs/2026-08-11-mid-mpc-l1-l2-problem-assembler-design-log.md`
> **状态**: 用户已接受；交付 `to-spec`
> **上游契约**: Candidate 2 L0/L1 Encounter Lifecycle，GitHub Issue #24
> **to-spec issue**: [#25 Deepen Mid-MPC L1/L2 Problem Assembler](https://github.com/marinehdk/colav-simulator/issues/25)

## 方案包契约

- 可做：在已裁决范围内确定类名、字段组织、私有 stage、测试组织、迁移顺序和性能实现。
- 不可做：推翻 VR-01..VR-23、重提 ALT-01..ALT-66、修改本包技术规约，除非出现新矛盾证据并回炉 `design-grounding`。
- 不可做：重新分类 COLREG、修改 Lifecycle 状态、按场景 ID 分支、静默截断目标、降低 50 m 门、使用 fallback 或把 Evaluator 当 Planner authority。
- Candidate 2 的 `DecisionSnapshot`、`TargetDecision`、`AggregateDirective`、typed events/errors 是权威上游事实；其 `mid_mpc_assembler.py` 是迁移 bridge，不是长期边界。

## 组件 1：术语表

| 术语 | 本方案定义 | 不是 | 关联 |
|---|---|---|---|
| L1 Semantic Assembly | immutable lifecycle/route/track/capability facts 到业务 OCP 的确定性映射 | 不是 COLREG 分类、IPOPT packing 或解接受 | DP-01..16 |
| L2 Numerical Preparation Plan | 对 seed、bounds、row activation、slack profile、layout identity 的具名语义计划 | 不是 public positional arrays | DP-15..17 |
| `AssemblyRequest` | 一个 solve cycle 的冻结输入，含 cycle identity、snapshot、route、capability、previous accepted plan、profile | 不是 mutable facade state | DP-03..05 |
| `AssemblyOutcome` | `AssemblySuccess` 或 `AssemblyFailure` 的 closed sum type | 不是 exception 文本或 partial problem | DP-04/18 |
| `ProblemSnapshot` | 可 hash/replay 的 semantic `MidMpcProblem` 加 bindings、predictions、activation、seed、evidence | 不是 CasADi graph | DP-04/19 |
| `AssemblyProfile` | `MASS_PARITY` 或 `COLAV_STRICT` | 不是算法 backend selector | DP-16/17 |
| `MASS_PARITY` | 保持 frozen C++ oracle 的研究 profile | 不是生产 hard-safety claim | DP-16/20 |
| `COLAV_STRICT` | 同一 frozen graph/layout，CPA/direction hard slack 上界固定 0 | 不允许 hard row 被 penalty 替代 | DP-16/20 |
| Route Reference | 稳定 nominal segment/anchor/tangent/speed | 不是每周期重锚到本船，也不是 Lifecycle 状态 | DP-07 |
| Target Binding | `TrackKey` 到固定 solver slot 的确定性映射 | 不是裸 target id 或输入顺序 | DP-08 |
| Prediction Bundle | 81 点 CV mean、time axis、uncertainty envelope | 不是机动目标鲁棒预测 | DP-09/10 |
| Constraint Activation Plan | 物理时间定义的逐目标/逐 row 激活语义 | 不是裸 `TCPA/dt-2` | DP-12 |
| Capability Envelope | Plant、GNC、Mid ODD 的逐 stage 交集 | 不是 YAML 单值冒充 live GNC authority | DP-13 |
| Execution Prefix | 已被执行队列确认、不可撤销的 control stages | 不是 hold plan 或 previous optimum | DP-14 |
| Accepted Plan Seed | L4 已接受解的显式 warm-start 来源 | 不是任意上次 solver 输出 | DP-15 |
| Synchronized Hull Clearance | 同一物理时刻双方 footprint 的边到边距离 | 不是 point-center node distance | DP-11/20 |
| Evidence Chain | Problem→Preparation→Prepared→RawSolver→Acceptance 的 immutable hash 链 | 不是 free-form details dict | DP-19 |

## 组件 2：技术规约表

| ID | 类别 | 固定规约 | 来源/差异 |
|---|---|---|---|
| TS-01 | Backend | 唯一 runtime backend 为 CasADi 3.7.2/IPOPT；不新增 backend abstraction | 用户裁决；一致 |
| TS-02 | Grid | 80 control intervals，`dt=15 s`，public 81 states，`t=0..1200 s` | Candidate 2 已验收 |
| TS-03 | Runtime | solve period 5 s；deadline 20 s | published config |
| TS-04 | Frame | ENU；数组位置 `(North,East)`；局部 OCP `x=North,y=East` | 现状隐含，改为显式 evidence |
| TS-05 | Angle | navigation angle 北为 0、顺时针正；course alteration 右转为正；ordinary unwrap | Candidate 2 contract |
| TS-06 | Units | m、m/s、m/s²、s、rad、rad/s；deg 只在 config/UI 边界 | SI/rad |
| TS-07 | Identity | cycle identity=`epoch/sequence/sim_time/input_hash/profile_hash`；request/problem/prepared 分别 canonical hash | 新增 |
| TS-08 | Capacity | frozen core max 16；required 全入；`>16` typed failure；禁止截断 | Candidate 2 + frozen core |
| TS-09 | Prediction | target CV mean；81 点；covariance 99% position envelope；机动目标 robustness 不宣称 | Candidate 2 profile confidence=0.99 |
| TS-10 | Safety | required synchronized hull clearance=50 m；preferred=150 m；CPA slack单位 m² | 现状字段需拆义 |
| TS-11 | Frozen timing | parity rows保留 own `(k+1)dt` 对 target `k dt`；同步安全补偿使用 target 一步位移，不使用 own 一步位移 | 修正 bridge |
| TS-12 | Node floor | `50m + own radius + target radius + covariance margin + target_speed*15s`，逐目标后取 solver global max | 新增明确公式 |
| TS-13 | Swept witness | L4/验收独立检查81点全部区间，含第一段；node feasible不等于 continuous safe | 不下沉到 solver status |
| TS-14 | Activation | 业务 schedule 先用物理秒表达，再映射 frozen grid；逐目标 CPA plan + global common direction corridor | 替换 `floor(TCPA/dt)-2` |
| TS-15 | Capability | heading window默认±45°；speed 0..8 m/s；ROT 3°/s；decel 0.3 m/s²；未来 live GNC facts 缺失时明确 ODD limitation | published profile |
| TS-16 | Prefix | 当前 execution chain 无不可撤销多步 ack，`K=0`；partial stage unsupported | Candidate 2 audit |
| TS-17 | Seed | v1 cold deterministic；仅显式 L4 accepted plan允许 primal resample；dual warm start disabled | 现状无 accepted-plan handoff |
| TS-18 | Profiles | `MASS_PARITY`保持8条oracle；`COLAV_STRICT`同graph/layout、CPA与direction slack lb=ub=0 | 新增 production profile |
| TS-19 | Failure | expected assembly failure为typed data：code/owner/status/recoverability/identity/evidence；无partial problem | 替换 public `ValueError` |
| TS-20 | Evidence | `lifecycle/assembly/solver/acceptance`独立versioned namespace；inline compact JSON≤8KiB | Candidate 2只拥有 lifecycle |
| TS-21 | Artifact | full 81点/rows/vectors存content-addressed gzip JSON；写入失败标 evidence incomplete，不阻塞 solver control path | 新增 |
| TS-22 | Route | nominal route anchor/tangent稳定；Lifecycle提供commit/recovery authority；Assembler编译reference，不持有状态 | bridge当前混责 |
| TS-23 | Target order | required先按Lifecycle obligation；剩余eligible按risk；最终slot以`TrackKey` canonical稳定绑定 | 新增 |
| TS-24 | Failure mapping | Adapter只机械映射现有`PlanStatus`和`ColavExecutionError.details`；no fallback，Session fail-stop | 保留公共兼容面 |
| TS-25 | Formulation | `mass-l3-mid-mpc-ipopt@ced58f8576f3772ef7c1bc72bb0f8b0368688b5a` | frozen provenance |

## 组件 3：决策卡片集

| Card | 采纳 | 弃用 | 裁决 |
|---|---|---|---|
| CARD-01 Module architecture | Deep Semantic Assembler + Private Numerical Codec | Facade thin builder；public staged numerical pipeline | VR-21；ALT-61/62 |
| CARD-02 OCP semantics | Explicit Physical Semantics + `COLAV_STRICT`，保留独立 parity profile | parity-only；场景 builders | VR-22；ALT-63/64 |
| CARD-03 Evidence | Hash-linked tiered evidence + six gates | inline G3 only；full synchronous trace | VR-23；ALT-65/66 |

## 组件 4：证据矩阵

| 证据 | 结论 | 限制 |
|---|---|---|
| Candidate 2 `b94148c`、Issue #24、441 passed | L0/L1 lifecycle、镜像OT、81点、8010基线已完成 | 不证明Candidate 3 strict assembly |
| 8条frozen C++/IPOPT JSONL oracle | Python core可做方程/packing parity | Ipopt 3.14.11；不证明COLAV strict安全 |
| 七层架构文档 | L1定义OCP语义、L2定义seed/bounds/parameters，L4/LX独立 | MASS/acados专有值不移植 |
| architecture review HTML | Candidate 3的Locality/Leverage/deletion test成立 | 只读评审，不是验收结果 |
| bridge源码 | 当前own-step allowance、裸TCPA schedule、ValueError、双solver是明确迁移缺口 | 不能作为最终契约 |
| published config | N=80、dt=15、5s/20s、45°、0..8、50/150、3°/s、0.3 | 真实GNC envelope仍缺 |
| local benchmark | 0/1/16目标cold单样本约0.84/1.02/5.37s | 非p95、非能力声明 |

## 组件 5：技术分解完整树

```text
EncounterLifecycle DecisionSnapshot                 [Candidate 2, state owner]
  + PlannerInput / stable RouteReference
  + CapabilitySnapshot / PreviousAcceptedPlan
  -> MidMpcProblemAssembler.assemble(request)        [Candidate 3 public seam]
       validate identity/profile/frame
       normalize route and physical facts
       bind/admit targets deterministically
       build 81-point prediction/envelope
       build safety and activation plans
       resolve capability/prefix/seed/profile
       emit ProblemSnapshot or AssemblyFailure
  -> MidMpcIpoptSolver private NumericalPreparer     [one layout authority]
       pack p/x0/lbx/ubx/lbg/ubg
       solve frozen graph
  -> Adapter                                         [mapping only]
       namespace evidence / artifact ref
       MPCSolution / no fallback
  -> L4 acceptance + evaluator                       [independent]
```

所有DP-01..20已由VR-21..23覆盖，无`DECOMPOSITION_INCOMPLETE`。

## 组件 6：弃用方案

- ALT-01..60：见权威设计日志0.7；涵盖Facade混责、生命周期重复、raw arrays公开、静默截断、错误时轴、hard/soft混淆、fallback、trace-only与阈值作弊。
- ALT-61/62：不保留Facade浅Builder，不公开数值pipeline。
- ALT-63/64：不把parity profile当生产配置，不建HO/CS/OT专用Builder。
- ALT-65/66：不以G3 inline摘要代替replay证据，不把全量大对象同步塞入PlannerTrace。

## 组件 7：需求场景与验收边界

### 预先确认的测试 seams

1. `MidMpcProblemAssembler.assemble(request)->AssemblyOutcome`：最高纯业务seam。
2. `MidMpcIpoptSolver.solve(problem)->result`：8条frozen parity和strict bounds seam。
3. `CustomMPCAdapter.plan(PlannerInput)->MPCSolution`：公共integration/no-fallback/evidence seam。
4. `P1RunHarness`与真实8010 HTTP planner event：闭环与运行证据seam。

### 六层 Gate

| Gate | 必须通过 |
|---|---|
| A Assembler | 0/16/17、bad identity/frame/time/hash/capability、replay、typed failure、deterministic slot/hash |
| B MASS_PARITY | 8条oracle expected不改；prepared/raw/objective tolerances通过 |
| C COLAV_STRICT | CPA/direction hard slack=0；original-bound recheck；node与swept witness分离 |
| D Closed loop | HO、CS-GW、CS-SO、OT左右镜像、overtaken/Rule17、multitarget；真实IPOPT、无fallback、Ship0≥50m、正确side/recovery |
| E Runtime/UI | 8010真实solve event；81点、15s、0..1200；hash/artifact可读；Planner/Evaluator分源 |
| F Regression | scoped Ruff/format/diff check；完整pytest |

目标船之间脚本碰撞继续报告，但不作为Ship0 Mid-MPC失败。性能记录0/1/16目标cold/cache p50/p95/max；hard gate为p95≤20s，5s只作为优化目标。

## 组件 8：已知冲突与未闭环限制

| 项 | 当前结论 |
|---|---|
| Candidate 2 Snapshot无顶层schema_version | Candidate 3 request binding记录类型/version=`candidate2-decision-snapshot@1`和content hash；不修改上游状态语义 |
| AggregateDirective仍含global passing_side | per-target constraints读取TargetDecision；aggregate只表达共同corridor/STOP；若不可共同表达typed failure |
| bridge使用own-step allowance | Candidate 3改target-step allowance；需新unit和闭环验证 |
| bridge使用`TCPA/dt-2` | Candidate 3改physical activation plan；若缺deadline/reachability facts，按显式保守policy，不伪造 |
| live GNC完整envelope缺失 | v1明确限制为`KinematicCSOG` profile，使用published envelope；不得称真实GNC认证 |
| accepted-plan warm start无公共handoff | v1 cold deterministic，`warm_start_used=false`；不把last solver plan冒充accepted plan |
| artifact retention TTL/quota | 属Experiment policy；当前实现content-addressed local sink与明确evidence-incomplete，不影响控制语义 |
| CV目标模型 | 只对当前固定场景/God或短期CV ODD；不宣称机动目标鲁棒性 |

## Candidate 2最终对齐

| SYNC | 状态 | Candidate 3动作 |
|---|---|---|
| 01..06 | MATCHED/PARTIAL | 绑定现有immutable Snapshot/TargetDecision/events；补request schema/hash，不改Lifecycle |
| 07 | MIGRATE | 用deep Assembler替换transitional bridge，禁止双路径 |
| 08 | MATCHED | 消费ENU/physical facts；Assembler唯一投影frozen COG/SOG |
| 09..11 | PARTIAL | 补stable route、admission、81点prediction profile |
| 12 | MATCHED | 保持80 decisions/81 public states |
| 13..15 | CANDIDATE3 | 修node allowance、activation、capability plan |
| 16 | MATCHED | K=0 |
| 17..21 | CANDIDATE3 | seed/profile/private preparation/failure/evidence chain |
| 22 | MATCHED | 复用Candidate 2 tests；Candidate 3扩展，不复制 |
