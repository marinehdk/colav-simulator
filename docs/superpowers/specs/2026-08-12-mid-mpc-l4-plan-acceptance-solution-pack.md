# Mid-MPC L4 Plan Acceptance Solution Pack

> **状态**：用户已接受；已交付to-spec
> **日期**：2026-08-12
> **权威决策日志**：`docs/superpowers/design-logs/2026-08-11-mid-mpc-l4-plan-acceptance-design-log.md`
> **设计基线**：Candidate 2 Encounter Lifecycle已合并；Candidate 3 L1/L2 Assembler为`marine/main@1f459d8`

## 方案包契约

to-spec获得以下权限与限制：

- **可做**：在本方案已裁决边界内完成架构、组件、数据流、错误处理、测试seam与实施分片；可以优化工程细节。
- **不可做**：推翻`VR-01..24`核心裁决；发现新矛盾证据时必须回design-grounding重开受影响DP。
- **不可做**：重提`ALT-01..150`已弃用方案。
- **不可做**：修改`TS-01..42`技术规约，包括坐标、单位、符号、时序、阈值、接口语义；需要修改时必须回design-grounding。
- **不可混淆**：L4 production acceptance、Evaluator事后G3、MASS parity、Ship0安全、global all-vessel安全、MASS-L3系统接受是不同claim。

## 1. 术语表

| 术语 | 本方案定义 | 不是 | 来源/关联 |
|---|---|---|---|
| L3 IPOPT Core | frozen-equation CasADi/IPOPT优化内核；产出raw candidate与数值证据 | COLREG决策器、执行控制器、最终安全许可 | R1..R4；DP-01/04/06 |
| L4 Plan Acceptance | 下发前对单个immutable candidate做完整、无状态、确定性复核 | 第二个solver、trajectory repair、Evaluator | R5..R7；DP-01/03 |
| Acceptance Request | `candidate/authority/execution/prior`四命名空间的versioned immutable bundle | 读取facade mutable state或free-form trace | R4/R25/R58；DP-02 |
| Acceptance Result | 全layer outcome、witness、aggregate与canonical hash | 单一bool或异常字符串 | R7/R55；DP-03/15 |
| Mandatory Layer | 不满足即拒绝command的integrity/numerical/safety/COLREG/trackability/evidence检查 | 可用总分抵消的软评分 | R7；DP-03 |
| Quality Layer | V1仅产生WARN/信息的平滑、churn、效率、progress、recovery检查 | raw objective二次判优或安全豁免 | R47..R51；DP-10 |
| Lifecycle Authority | Candidate 2冻结role/side/phase/commit/release的唯一规则状态源 | L4或Evaluator的重新分类结果 | R22..R33；DP-07/08 |
| Action Contract | commit baseline、deadline、累计实测achievement、reachability、release permission的immutable snapshot | 仅当前encounter label | R28/R34/R38；DP-07/08 |
| Candidate | L3同一solve point的raw primal、trajectory、bounds、rows、status与objective证据 | UI重建轨迹或旧held plan | R15..R21；DP-02/04 |
| Fresh Candidate | 本tick执行真实L3后产生、尚未commit的candidate | 已接受plan的继续执行 | R52..R62；DP-12 |
| Held Accepted Plan | 既有accepted receipt在原absolute timeline上的当前切片 | 继承旧SUCCESS而不复核 | R52/R53；DP-12 |
| Active Prefix | 从当前实测状态到下次正常solve/commit窗口的执行区间 | 对全部1200s闭环可跟踪性的替代证明 | R40..R46；DP-09 |
| Trackability | candidate active prefix在真实Viknes+FLSC plant capability内可实现 | reference polyline数学连续性 | R40..R46；DP-09 |
| Synchronized Swept Clearance | 同一时间参数下两船在每个区间的解析相对线段最小hull clearance lower bound | 离散node DCPA、不同步最近点或point-center距离 | R8..R14；DP-05 |
| Trusted Uncertainty | 逐时刻、经校准、由policy认可的预测误差包络 | 任意安全margin或事后调参 | R10/R14；DP-05/17 |
| TrackKey | `(session_epoch,target_id,generation)`目标身份 | 可跨reset复用的裸target id | R25/R57；DP-02/11 |
| Per-target AND | 每个relevant TrackKey的mandatory verdict都必须通过 | 只看primary或最危险目标 | R25/R31；DP-11 |
| MASS_PARITY | 复现frozen MASS数值行为的诊断profile | production command safety profile | R1/R19/R22；DP-06 |
| COLAV_STRICT | 使用strict preparation、policy与完整L4 proof的唯一production profile | “IPOPT成功”别名 | R19/R22；DP-06 |
| Plan Acceptance Certificate | pure L4对candidate及policy给出的immutable semantic证明 | command已下发证明 | R56/R58；DP-14/15 |
| Accepted Plan Receipt | Adapter在L4通过、deadline/freshness通过后原子commit生成的执行权威 | solver success或L4 result本身 | R56..R58；DP-14 |
| PreviousAcceptedPlan | 由兼容receipt导出的中性warm输入摘要 | Assembler读取Adapter全局last solution | R56/R57；DP-14 |
| Semantic Record | 决定接受与否的canonical、可hash、可replay内容 | wall timing、文件路径或queue状态 | R58/R63；DP-15/16 |
| Dispatch Record | command提交/下发尝试及结果；引用acceptance hash | 改变semantic verdict的输入 | R58/R64；DP-15/16 |
| Atomic Commit | 通过全部门后一次性发布solution、active plan、receipt、warm与event | 多字段逐步写入再尽力rollback | R54/R58；DP-13/14 |
| Fail-stop | 最终拒绝后无command、无fallback、Session进入FAILED | hold-last、零速替代或算法切换 | R54/R55；DP-13 |
| Canonical Projection | full artifact、inline、GUI从同一semantic record机械派生 | 多处独立拼字段 | R59/R63；DP-15 |
| Production Ready | policy、plant contract、runtime reservation、V1..V6 exact tuple全部闭合 | 某个focused suite PASS或按钮可见 | R69..R81；DP-18 |

## 2. 技术规约表

下表是实现约束摘要；完整逐项规约及现状差异以决策日志`TS-01..42`为准。

| 类别 | 冻结技术规约 | TS |
|---|---|---|
| Module | pure/stateless/deterministic `evaluate(request)->result`；L3后、atomic commit前；不改candidate | TS-01/02 |
| 坐标/符号 | world ENU；body x-forward/y-port；rad；0北、顺时针/右转为正；角wrap `[-pi,pi)` | TS-03/04 |
| 单位 | m、s、m/s、m/s²、rad/s；linear distance m；CPA NLP row m² | TS-05 |
| 时钟 | sim-time决定语义；wall-time仅telemetry；所有plan/prediction/receipt绑定absolute sim-time | TS-06 |
| 网格 | 80×15s intervals，81 knots，1200s；state at knots，command piecewise constant per interval | TS-07/08 |
| 身份/哈希 | TrackKey含epoch/id/generation；versioned schema-specific canonicalization；完整parent chain | TS-09/10 |
| 目标集合 | 所有fresh/usable/relevant目标reconcile；max16；超限拒绝不截断 | TS-11/30 |
| Verdict | 七层与六态taxonomy；mandatory fail-closed；quality advisory；完整failure list | TS-12/13 |
| 数值 | eligible termination；同点raw x/g原始bounds、finite、options、objective；KKT V1 advisory | TS-14/16 |
| 数值容差 | rad/speed类abs1e-6 rel1e-10；position/CPA类abs1e-4 rel1e-10；zero slack abs1e-7；objective abs1e-8 | TS-15 |
| Profile | MASS_PARITY只诊断；COLAV_STRICT才可production；strict slack实质非零拒绝 | TS-17/18 |
| 动态安全 | 81/80同步解析swept clearance；减两船radius与trusted uncertainty；physical hull hard gate=50m | TS-19/20 |
| ODD安全 | 150m advisory；God uncertainty=0；非God无校准envelope拒绝；chart profile缺static context拒绝 | TS-20/21/22 |
| COLREG | Lifecycle唯一authority；HO port-to-port、CS astern、OT locked corridor、stand-on/Rule17 contract | TS-23/24 |
| 行动/释放 | baseline、deadline、actual achievement、reachability；first executable interval；current release permission | TS-25/26 |
| Trackability | 真实Viknes+FLSC active capability hard；无full tube只claim active prefix executable/planned safety | TS-27/28 |
| Quality | smoothness/churn/efficiency/progress/recovery/straightness advisory；安全直线不拒绝 | TS-29 |
| Fresh/Hold | fresh全L4；hold按当前state/context重验active prefix；一次同算法replan；不续receipt | TS-31/32 |
| Failure/Commit | rejection无command/fallback、清状态、Session FAILED；final deadline/freshness后atomic commit | TS-33/34 |
| Warm | compatible receipt才可用；absolute-time heading/speed primal；cold tail；slack归零；dual off；无cold retry | TS-35 |
| Evidence/UI | Request→Problem→Prepared→Candidate→Acceptance→Receipt；full/<=8192B inline/GUI同源；双时间线 | TS-36/37 |
| Runtime | 总20s；solver reserved cutoff；未校准full-L4 p99 reservation即NOT_PRODUCTION_READY | TS-38 |
| Persistence | max16MiB；queue32 items/64MiB；drain2s；retention256；sink失败不回写verdict但阻断claim | TS-39 |
| Policy | Registry typed immutable policy，Session freeze/hash；N80/dt15/50/150/max16/20s/God-only/strict/dual-off | TS-40 |
| Promotion/claim | V1..V6全过；只claim exact tuple Ship0，不扩展到global/non-God/arbitrary plant/MASS-L3 | TS-41/42 |

## 3. 决策卡片集

完整七维卡片位于决策日志Step5。最终选择：

| Card | 方案A（采纳） | 方案B（弃用） | 方案C（弃用） | Final |
|---|---|---|---|---|
| DC-01 Module topology | Independent Pure L4 | Stateful Adapter Acceptance Controller | Distributed Validators | VR-20；ALT-141/142 |
| DC-02 Numerical+safety kernel | Primal-hard/KKT-advisory + swept conservative safety | Full NLP/KKT certification | Reuse solver/evaluator flags | VR-21；ALT-143/144 |
| DC-03 Behavior+execution | Lifecycle-locked obligations + active-prefix capability | L4 behavior decider | Static post-checks | VR-22；ALT-145/146 |
| DC-04 Temporal+transaction | Prefix revalidation + atomic receipt/warm | Every-tick fresh solve | Last-plan continuation + fallback | VR-23；ALT-147/148 |
| DC-05 Evidence+runtime+policy | Canonical semantic record + async durable sink | Synchronous event-sourced durable commit | Lightweight trace + best-effort logs | VR-24；ALT-149/150 |
| Validation | DP-18六级promotion gates直接采纳 | 不以focused PASS替代 | 不以GUI可见替代 | VR-19 |

组合理由：方案A把数学复核、行为合同、执行许可、事务提交、证据治理分责；L4保持深而无状态。删除L4后，检查会重新散回solver/facade/adapter/evaluator/UI，证明该module拥有足够depth。方案B状态blast radius或实时依赖过大；方案C保留已复现的stale success、selected-only、旧trace和不可replay缺陷。

## 4. 证据矩阵

| 证据范围 | 类型 | 支撑结论 | 对应DP |
|---|---|---|---|
| R1..R4 | PROJECT_FACT/UPSTREAM | frozen L3 equations、81/80网格、public adapter与Candidate3 contract | DP-01/02/04/06/09 |
| R5..R7 | ARCHITECTURE/SAFETY PRACTICE | 独立acceptance seam、typed layered verdict、fail-closed | DP-01/03/13 |
| R8..R14 | GEOMETRY/PAPER/PROJECT | synchronized continuous CPA、hull footprint、不确定性、static context | DP-05/11/17 |
| R15..R21 | IPOPT DOCS/ORACLE | termination、primal bounds、KKT可得性、slack/objective、mixed tolerances | DP-04/06/17 |
| R22..R33 | COLREG/PROJECT/LIFECYCLE | role/side/phase authority、HO/CS/OT/stand-on/Rule17与多目标合同 | DP-07/08/11 |
| R34..R42 | CONTROL/PROJECT | commit baseline、累计achievement、deadline、reachability、plant state | DP-08/09/10 |
| R43..R51 | PLANT/QUALITY/PROJECT | COG/body区别、active-prefix capability、quality与straight plan边界 | DP-09/10 |
| R52..R62 | PROJECT PROBES/ARCHITECTURE | stale hold反证、absolute slicing、one-replan、atomic commit、receipt/warm | DP-12/13/14 |
| R63..R72 | EVIDENCE/RUNTIME/PROJECT | canonical record、async bounded sink、deadline、policy hash、projections | DP-15/16/17 |
| R73..R81 | PERFORMANCE/TEST/CAPABILITY | solver timing、full-L4 reservation缺口、V1..V6与exact claim | DP-16/17/18 |

证据置信边界：现有证据足以冻结设计；不等于production evidence完成。真实active plant envelope、full-L4 p99 reservation、边界容差corpus、V1..V6仍是实施/promotion gates。

## 5. 技术分解完整树

```text
TD-01 Mid-MPC L4 Plan Acceptance
├── Module boundary and immutable contract ........ DP-01, DP-02
├── Layered verdict and aggregation ............... DP-03
├── Numerical acceptance kernel ................... DP-04, DP-06
├── Synchronized swept safety ..................... DP-05
├── Lifecycle-locked COLREG obligations ........... DP-07, DP-08
├── Active-plant trackability ..................... DP-09
├── Advisory solution quality ..................... DP-10
├── Multi-target reconciliation ................... DP-11
├── Fresh/hold/replan temporal contract ........... DP-12
├── Failure projection and atomic commit .......... DP-13
├── Receipt and warm-start authority .............. DP-14
├── Canonical evidence and UI projections ......... DP-15
├── Deadline and bounded persistence .............. DP-16
├── Typed policy, thresholds, units and versions .. DP-17
└── Six-level validation and exact claim .......... DP-18
```

闭环结果：18/18 DP有final VR；5/5关键设计卡完成DESIGN-IT-TWICE；DP-18由用户判定低风险直接采纳；无`DECOMPOSITION_INCOMPLETE`。L3 IPOPT Core有意保持独立，不被L4重新实现。

## 6. 弃用方案及理由

权威逐项清单为决策日志`ALT-01..150`。下表按失效机制覆盖全部弃用族：

| 弃用族 | 代表ALT | 弃用理由 |
|---|---|---|
| 把L4塞入Facade/Adapter或做stateful controller | ALT-01/06/141 | authority耦合、reset/replay困难、状态blast radius大 |
| 分散validator或依赖Evaluator/GUI结果 | ALT-02/07/142/144 | 无单一truth、selected-only、事后评价不能下发前许可 |
| L4改candidate、重求或拥有fallback | ALT-03..05 | 越界进入L3/L5，破坏frozen parity和no-fallback约束 |
| bool/score/exception聚合 | ALT-08..15 | 丢applicability、多失败、owner与witness；可能用质量抵消安全 |
| 只看IPOPT success/uniform tolerance | ALT-16..29/143 | 无原始bounds/同点证据，mixed-unit错误，KKT伪证明 |
| node-only/point-center/selected-only safety | ALT-30..40 | 漏区间内最近点、footprint、第一段、unselected target和不确定性 |
| parity即production或soft slack放行 | ALT-41..48 | 数值复现不等于安全；实质slack隐藏合同违反 |
| 静态plant envelope或full-horizon虚假claim | ALT-49..56 | 不代表Viknes+FLSC active capability；reference不等于可跟踪 |
| L4重分类/重选边/推进phase | ALT-57..69/145 | 形成第二Lifecycle，HO/CS/OT authority冲突 |
| quality hard阈值/用objective判断质量 | ALT-70..77 | 会拒绝安全直线；objective量纲随cycle/target变化 |
| primary target或risk truncation | ALT-78..84 | 漏relevant contact；不能证明Ship0对所有目标安全 |
| hold-last/继承SUCCESS/多次retry/fallback | ALT-85..92/147/148 | stale state/context泄漏，deadline不可控，隐藏算法失败 |
| Assembler/L4/Adapter循环读取last solution | ALT-93..100 | 隐式状态、reset污染、rejected plan进入warm |
| free-form trace/旧solve回退/多源GUI | ALT-101..116/150 | schema漂移、source混淆、无法replay exact decision |
| 同步durable store作为控制前置 | ALT-117..124/149 | fsync/磁盘故障进入20s关键路径，基础设施过重 |
| 可变YAML/场景ID阈值/降低50m | ALT-125..140 | policy不可追溯、test overfit、claim失真 |
| every-tick full solve | ALT-147相关方案B | 16-target成本与tick不匹配，增加nonconvex churn和artifact压力 |

## 7. 需求场景与验收边界

| 场景族 | 必须证明 | 禁止替代证据 |
|---|---|---|
| Route/no contact | 安全直线可接受；quality不强迫弯曲；恢复/progress正常 | “轨迹直线所以不是求解结果” |
| Head-on | Lifecycle锁定give-way；first executable action timely；最终port-to-port；50m swept hull | 只看最终heading或Evaluator PASS |
| Crossing give-way | early/substantial且pass astern；全相关目标per-target PASS | 当前瞬时classifier或primary DCPA |
| Crossing stand-on | entry baseline course/speed保持；Rule17触发前不擅自give-way；危险时合同一致 | 每cycle重置baseline |
| Standard overtaking | standard policy锁定starboard corridor；wrong-side reject；past-and-clear后恢复 | 只看“最终超过目标” |
| Mirror/restricted overtaking | 仅Lifecycle明确锁定port时允许左舷；L4验证该锁定corridor | L4按场景ID自行选左/右 |
| Overtaken | stand-on合同、clearance、release与route/speed recovery | 把无动作等于无需复核 |
| Rule17 escalation | phase/deadline/reachability与实际累计achievement一致 | predicted future action替代当前行动 |
| Multi-target <=16 | 五路身份集合reconcile；每TrackKey mandatory AND；冲突来源可解释 | risk truncation或target-target碰撞算Ship0失败 |
| Relevant target >16 | fail-closed、明确capacity原因、无command | 静默取前16 |
| Static/chart hazard | chart profile完整且clearance hard PASS | ship-ship安全替代static proof |
| Fresh numerical adversarial | NaN、x/g越界、objective mismatch、slack、termination组合得到确定typed结果 | `Solve_Succeeded`字符串 |
| Hold deviation/new target | current snapshot active-prefix重验；stale触发一次replan；失败fail-stop | 旧receipt/SUCCESS继续执行 |
| Warm/reset/tamper | 仅兼容accepted receipt可warm；reset/generation/policy/hash变化失效 | previous raw_x无条件shift |
| Persistence failure | semantic verdict不被慢盘改写；claim标INCOMPLETE/BACKPRESSURE | 写盘失败回滚已安全commit或静默丢失 |
| Deadline boundary | L3+L4+freshness+commit总计<=20s；timeout candidate仍需完整L4 | IPOPT单独<=20s |
| Real 8010 | 确认listener PID/cwd；真实planner event含L3、L4、active/latest、无fallback、source | HTTP 200或按钮显示 |

### 六级验收

| Gate | 验收内容 | 通过后允许的claim |
|---|---|---|
| V1 Pure contract | schema/canonical/hash、layer truth tables、mutation/property tests、failure precedence | module contract正确 |
| V2 Independent oracles | swept geometry、COLREG predicate、time slicing、plant envelope、boundary tolerance corpus | 检查公式有独立oracle |
| V3 Real L3/IPOPT | 8 parity records + strict adversarial candidates + original-bound/slack/objective证据 | 真solver candidate可被正确裁决 |
| V4 Closed loop | route、HO、CS-GW、CS-SO、OT、overtaken、Rule17、多目标、hold/replan | 固定场景Ship0闭环证据 |
| V5 Real 8010/UI | 正确服务进程、真实planner events、active/latest时间线、full/inline/GUI同源 | 浏览器可观察证据可信 |
| V6 Performance/regression | full-L4 p99 reservation、queue/failure injection、full pytest、exact capability tuple | 允许production capability promotion |

最终claim仅限：被冻结commit、policy、God prediction、Viknes+FLSC active capability、seed与场景tuple下的Ship0 plan acceptance/closed-loop证据。明确不包括global all-vessel安全、非God预测、任意plant、NLP global optimum、法律合规证明、实船验证、MASS-L3 SIL/GNC/M7系统接受。

## 8. 已知冲突与未闭环Gate

### 已解释冲突

| 冲突 | 裁决 |
|---|---|
| frozen L3 own `k+1` vs target `k`、midpoint rows disabled | parity保留；L4用独立同步81/80 swept geometry复核，不改L3方程 |
| IPOPT nominal bound slack可能约`-1e-8` | mixed-unit diagnostic tolerance；strict production fixed-zero slack门独立冻结 |
| 当前某些G3场景soft slack实质非零 | 不隐藏；COLAV_STRICT production按strict policy拒绝，不用closed-loop PASS覆盖 |
| OT可以直线或左舷 | 安全直线本身不失败；standard OT由Lifecycle锁starboard，mirror/restricted只有显式锁定才可port |
| 目标船之间脚本碰撞 | 记录global diagnostic；不算Ship0 Mid-MPC hard failure，不宣称all-vessel safe |
| KKT证据不完整 | V1 advisory `NOT_EVALUATED+WARN`；不阻断primal-safe candidate，不伪造hard proof |
| artifact写盘失败 | 不改变已完成semantic verdict；persistence/claim为INCOMPLETE，不能作完整promotion evidence |

### 实施前Gate

| Gate | 当前状态 | 未满足时行为 |
|---|---|---|
| Candidate 3集成到目标implementation base | `marine/main@1f459d8`已推送；本设计branch未集成 | 不开始L4生产实现 |
| Lifecycle action deadline/reachability projection | 设计要求已冻结；字段实现待验证 | COLREG mandatory UNKNOWN→reject |
| 真实Viknes+FLSC active capability contract | 未接入L4 | trackability UNKNOWN→NOT_PRODUCTION_READY |
| mixed-tolerance boundary corpus | 数值规约已冻结；corpus待建 | COLAV_STRICT不promotion |
| full-L4 p99 reserved budget | 仅已有geometry/solver局部数据；完整值UNSET | runtime policy NOT_PRODUCTION_READY |
| V1..V6 | 尚未实施 | 不提升capability、不声称全部Playground PASS |

这些是明确的实施与promotion gates，不是可由to-spec重新裁决的技术TBD。若实现发现它们与现有contract不可同时满足，必须携带新证据回design-grounding。

## Step6交付

用户于2026-08-12明确回复“接受”。方案包八组件齐全，技术分解无缺口，技术规约无TBD；本文件成为to-spec权威输入。

移交声明：

> 本方案的核心技术决策已通过design-grounding裁决。to-spec负责把既有结论综合为设计与实施Spec、测试seams和issue，不得推翻已裁决方案、重提弃用方案或修改技术规约；发现新矛盾证据时回炉design-grounding。

to-spec产物：

- 正式Spec：`docs/superpowers/specs/2026-08-12-mid-mpc-l4-plan-acceptance-design.md`
- 实施Plan：`docs/superpowers/plans/2026-08-12-mid-mpc-l4-plan-acceptance-implementation.md`
- Ready issue：<https://github.com/marinehdk/colav-simulator/issues/26>
- Plan comment：<https://github.com/marinehdk/colav-simulator/issues/26#issuecomment-5262965820>
