# 方案包：Mid-MPC L0/L1 Encounter Lifecycle 深化

> **创建**: 2026-08-11
> **来源**: `docs/superpowers/design-logs/2026-08-10-mid-mpc-l0-l1-encounter-lifecycle-design-log.md`
> **状态**: 已交付 to-spec（用户于2026-08-11接受）
> **设计范围**: Colav-Simulator 的态势事实标准化、逐目标 COLREG 生命周期、多目标聚合、L1 问题装配与证据链
> **不在范围**: MASS ROS2/GNC/M7、目标船控制、实船最低风险控制、法律认证、非 IPOPT backend
> **to-spec issue**: [#24 Deepen Mid-MPC L0/L1 encounter lifecycle](https://github.com/marinehdk/colav-simulator/issues/24)

---

## 方案包契约（to-spec / implement 权限边界）

- ✓ 可做：工程细节设计、组件/API 命名、数据流、错误处理、测试组织，以及已裁决方案内的优化。
- ✗ 不可做：推翻 VR-01..VR-21，除非发现新矛盾证据并回炉 design-grounding。
- ✗ 不可做：重提 ALT-01..ALT-58 中的弃用方案。
- ✗ 不可做：擅自修改 TS-01..TS-36 的坐标、单位、符号、时间、数值或接口语义。
- ✗ 不可做：用 fallback、场景特判、降低安全门、复用 Evaluator verdict 等方式制造 PASS。

---

## 组件 1：术语表

| 术语 | 通用定义/来源 | 本方案中的具体含义 | 边界：不是什么 | 关联 DP |
|---|---|---|---|---|
| L0 Encounter Lifecycle | 规则解释与离散行为状态层[R3][R9] | solver-agnostic、stateful、单一状态所有者 | 不是 Tracker、LOS、Problem Assembler、IPOPT 或 Evaluator | DP-01/03 |
| L1 Problem Assembler | 业务约束到数学问题的映射层[R3][R4] | `PlannerInput + Snapshot + LOS -> MidMpcProblem` | 不拥有 lifecycle memory；不重新分类 | DP-01/14 |
| `TrackKey` | 稳定 track identity | `(target_id, generation)` | 不是裸 `target_id`；不是 encounter episode | DP-04/11 |
| generation | Tracker association 生命周期编号[R35][R38] | 同 ID 重建/复用时单调变化，由 Tracker 权威提供 | 不是 Lifecycle 猜测的 missing counter | DP-04/11 |
| episode | 一次风险进入到 release/rearm 的业务生命周期 | Lifecycle 为同一 TrackKey 生成的单调编号 | 不是 generation；release 后可创建新 episode | DP-11 |
| `TrackSnapshot` | 一周期 immutable tracker 输出 | 含 key/status/state/covariance/hull/time/source/quality | 不是自由格式 `do_list` tuple | DP-04/11/13 |
| `EncounterCycle` | 同一时刻的冻结输入集合 | epoch/cycle/time/ownship/maneuverability/全部 observations | 不是 solver iteration；不是可变 facade state | DP-04/14 |
| Geometry Facts | Planner-neutral 相对物理事实 | range、bearing、relative velocity、DCPA、signed TCPA、validity | 不含 encounter label、role、risk 或 action | DP-02/05 |
| EncounterKind | 几何相遇类型 | CLEAR/HEAD_ON/CROSSING/OVERTAKING/UNDETERMINED | 不等于 ownship duty | DP-05 |
| OwnshipRole | 本船规则角色 | GIVE_WAY/STAND_ON/OVERTAKING/OVERTAKEN/UNKNOWN | 不与 EncounterKind 合成字符串 | DP-05 |
| RiskPhase | 风险业务阶段 | MONITOR/CANDIDATE/COMMITTED/PAST_CLEAR/RELEASED | 不由 MPC horizon 或 Evaluator stage 决定 | DP-06/10 |
| commitment | 冻结的可审计行为承诺 | baseline course/speed、action mode、side、achievement condition | 不是每周期累计的小角度；不是首个控制符号 | DP-07/08 |
| substantial action | Rules 8/16 的明显、及时、有效动作[R14][R28] | 以安全缺口、动力学可达性和实际轨迹改善定义 | 不是固定 5°；30°也不是 COLREG 常数 | DP-08/16 |
| TurnDirection | 本船 course 改变量方向 | STARBOARD=正、PORT=负 | 不等于最终 passing corridor | DP-08 |
| PassingCorridor | 本船相对目标航迹所在侧 | `TARGET_TRACK_STARBOARD/PORT`，按目标 COG 横轴定义 | 不是目标在本船哪一舷；Rule13 不规定固定侧 | DP-08/15 |
| Rule17Stage | stand-on 升级阶段[R14][R27] | STAND_ON/MAY_ACT/MUST_ACT | 不是单一 TCPA 阈值；MAY 与 MUST 强度不同 | DP-09 |
| appropriate target action | 对方动作适当性 | 趋势、持续、可达、净空改善的联合证据 | 不是只看到一次 heading change | DP-09 |
| target-alone capability | Rule17(b) 工程 proxy | 目标可达集合是否仍存在独立避碰动作[R29] | 不是法律认可的唯一计算方法 | DP-09 |
| ObservationHealth | 观测可用性正交状态 | OBSERVED/DEGRADED/COASTING/UNUSABLE | 不等于 CLEAR；数据差不解除 duty | DP-11/13 |
| COASTING | Tracker 仅预测、无新观测的有限状态[R38] | 保留 commitment，冻结需 fresh evidence 的正向 transition | 不是无限 CV 外推；不是 fresh observation | DP-11/13 |
| PAST_CLEAR | 通过且持续分离的过渡阶段 | 允许 route recovery，但继续 future-clearance 监视 | 不等于单纯 `TCPA<=0` | DP-10 |
| RELEASED | episode duty 已安全结束 | 保留有限 tombstone，可重新 rearm | 不是永久 released-target 集合 | DP-10/11 |
| `AggregateDirective` | 全目标共同动作约束 | required targets、course corridors、speed/STOP、conflict/capacity/status | 不是一个 global side sign；不是 primary target action | DP-12/14 |
| mandatory/conditional/preference | 多目标约束强度 | 规则硬义务/带条件限制/未锁定选择偏好 | preference 不得覆盖 mandatory 或 locked constraint | DP-12 |
| primary target | 可观测性与稳定排序锚点 | GUI/trace/risk explanation only | 不代表只保证该目标；切换不重置其他状态 | DP-12/15 |
| `CORE_CAPABILITY_MISMATCH` | L1 表达能力错误 | AggregateDirective 无法由当前纯 MPC 模型表达 | 不是把约束折叠后继续 SUCCESS | DP-12/14 |
| Planner ODD Profile | Planner 独立工程策略参数 | canonical resolved values + hash | 不是 Evaluator profile；不是 COLREG 法定数字 | DP-02/06/15 |
| Evaluator Profile | 独立结果评价参数 | 只评实际轨迹和事件 | 不进入 Planner lifecycle 或 Assembler | DP-02/15/16 |
| actual trajectory evidence | Ship0 真实闭环状态序列 | commit→achievement→CPA→past-clear 窗口的 COG/SOG/clearance | 不是 selected command 或预测线本身 | DP-08/15/16 |

---

## 组件 2：技术规约表

| ID | 类别 | 规约内容 | 来源 | 关联 DP/接口 | 与当前代码差异 |
|---|---|---|---|---|---|
| TS-01 | 坐标系 | 全部 L0/L1 平面状态使用 ENU；数组顺序 `(north,east)`，位置 m、速度 m/s | [R1][R34] | DP-02/04；Cycle/Observation | 现有字段常写 `x/y`，需改成显式 north/east 语义 |
| TS-02 | 坐标系 | 航向/course 零点正北，顺时针为正；0→North、`pi/2`→East | PROJECT_FACT + DESIGN_DECISION | DP-04/08；geometry/core | 固化现有 `cos->north,sin->east` 语义 |
| TS-03 | 坐标系 | body/route lateral：x-forward，y-starboard；route cross-track 正值为 starboard | DESIGN_DECISION | DP-08/12/14；Aggregate/Assembler | 替代模糊 `preferred_side=1` 约定 |
| TS-04 | 坐标系 | 相对位置统一为 `target-ownship`；PassingCorridor 另用 `ownship-target` 投影到目标 starboard normal，正值=`TARGET_TRACK_STARBOARD` | [R30] + DESIGN_DECISION | DP-08/15；geometry/evidence | 当前测试/trace 未显式说明向量方向 |
| TS-05 | 坐标系 | L0 不接收 WGS84/UTM；上游先转 ENU。纯 MPC 内部原点为 solve-time ownship，输出再映射回 ENU | [R3][R40] | DP-01/04/14；Builder/Assembler | facade 当前隐式完成，需成为显式映射证据 |
| TS-06 | 物理量单位 | 内部统一 SI/rad/s：距离 m、时间 s、速度 m/s、加速度 m/s²、角度 rad、角速度 rad/s；deg 只允许配置/UI 边界 | [R1][R13][R16] | DP-04/14；全部接口 | 当前 YAML `*_deg` 可保留，但进入 profile 即转 rad |
| TS-07 | 物理量单位 | track state/covariance layout 固定 `[N,E,VN,VE]`；covariance 单位按各维乘积，4×4、对称、PSD | [R34][R38][R39] | DP-04/13；TrackSnapshot | 当前 layout 仅靠约定，需 schema 声明 |
| TS-08 | 物理量单位 | hull position 是几何中心；clearance 是双方 footprint support 扣除后的边到边距离，不是中心距 | [R12][R25] | DP-06/10/16；geometry/evaluator | 当前 core 通过统一半径补偿近似，证据中需区分 |
| TS-09 | 符号约定 | 普通角度 canonical wrap 到 `(-pi,pi]`；commit baseline/reference 可 unwrapped 连续保存，禁止每周期重新 wrap 后累加 | DESIGN_DECISION | DP-07/08/14；FSM/Snapshot | 替代 `current+5°` 累加风险 |
| TS-10 | 符号约定 | signed TCPA：`>0` 为 CPA 未到，`=0` 为 CPA 时刻，`<0` 为已通过；DCPA 非负且带 validity | [R15][R19] | DP-05/06/10；GeometryFacts | 固化现有但未成文语义 |
| TS-11 | 时序约定 | Lifecycle 唯一时间基准为 simulation time；所有确认、coast、release、tombstone 使用物理秒，不使用 solve 次数 | [R41] + DESIGN_DECISION | DP-06/07/10/11/14 | 当前 commitment 无定时器，部分行为按调用次数 |
| TS-12 | 时序约定 | cycle identity=`(session_epoch, cycle_sequence, input_hash)`；同 identity+hash 重试幂等，不重复 event；同 identity 不同 hash=`INPUT_CONFLICT` | [R40][R43][R44] | DP-14/15；Lifecycle.step | 当前只有 solve_id/sim_time |
| TS-13 | 时序约定 | Playground profile：solve period=5 s、deadline=20 s；正常新 cycle 必须单调。gap>`max(2*solve_period, solve_period+dt_sim)` 输出 `TIME_GAP`，要求显式 reset/reseed | PROJECT_FACT + DESIGN_DECISION | DP-14；Adapter/Lifecycle | 当前只拒绝倒退，不识别大 gap |
| TS-14 | 时序约定 | 预测为 N=80 个 15 s control intervals，覆盖 1200 s；public state trajectory 必须 81 samples：t=0 实测 + t=15..1200 预测；target prediction 同 grid | MASS parity + DESIGN_DECISION | DP-14/15/16；Core/MPCSolution/GUI | 当前 80 samples 标成 t=0..1185，需修正映射但保持 raw 80-decision parity |
| TS-15 | 时序约定 | solver failure 不回滚已提交 decision snapshot；hold step 不推进 Lifecycle；UNUSABLE/CAPACITY/CONFLICT 不执行 IPOPT、不继续 cached plan | VR-17/18/20 | DP-13/14；Adapter | 当前 hold 继续旧 plan，且 lifecycle 与 solve 同方法 mutation |
| TS-16 | 数值边界 | core capacity 固定 16；Lifecycle 先处理全部 tracks。required active targets>16=`CAPACITY_EXCEEDED`，禁止截断 | PROJECT_FACT + VR-20 | DP-12/14；Aggregate/Assembler | 删除 facade `decisions[:16]` |
| TS-17 | 数值边界 | Playground tracking：fresh age≤1 s；1<age≤5 s 为 DEGRADED 或 COASTING（取决于 tracker status）；age>5 s=UNUSABLE；reacquisition window=5 s；tombstone TTL=10 s | PROJECT_FACT + DESIGN_DECISION | DP-11/13；TrackSnapshot/FSM | 当前缺 age 时默认 0，且目标缺失立即删 state |
| TS-18 | 数值边界 | `cog_valid_min_sog=0.25 m/s`；低于该值 COG invalid。covariance eigenvalue tolerance=-1e-9；Gaussian position margin confidence=0.99 | PROJECT_FACT + [R37][R39] + DESIGN_DECISION | DP-04/13；ObservationBuilder | 当前低速仍 `atan2`，covariance 未进入 clearance |
| TS-19 | 数值边界 | Planner ODD v1：minimum hull clearance=50 m、comfortable clearance=150 m，独立于 Evaluator profile。center constraint=`h_os(n)+h_ts(n)+50m+uncertainty_margin` | PROJECT_FACT + [R12][R25] + DESIGN_DECISION | DP-06/10/16；Geometry/Aggregate | 当前 50m 与 evaluator 语义容易混淆；需双 profile hash |
| TS-20 | 数值边界 | risk candidate：role/approaching valid、signed TCPA>0、预测最小 hull clearance<150m；连续 5s 后进入 action。urgent：当前 hull clearance≤50m，或 TCPA≤required response time，绕过确认 | [R14][R15][R19] + DESIGN_DECISION | DP-06/07；FSM | 替代 horizon=1200s 或单 DCPA/TCPA 门 |
| TS-21 | 数值边界 | substantial commitment 取最近的动力学可达 course/speed corridor，使独立预测补足全部安全缺口；baseline 固定，约束持续到实际轨迹达到并保持。不得使用固定 5°、统一 30°或 successive increments | [R14][R17][R28][R30] + DESIGN_DECISION | DP-08/16；FSM/Aggregate/L4 | 删除 `commit_course + min_alteration_deg=5` 与 one-shot row |
| TS-22 | 数值边界 | Rule17 evidence window=10s。MAY_ACT：目标动作不适当且仍有 target-alone safe reachable action；MUST_ACT：target-alone reachable set无任何满足50m hull clearance的动作，或 urgent。未知 target dynamics 时 MUST proxy=`UNKNOWN`，不得伪造确定 | [R14][R27][R29] + DESIGN_DECISION | DP-09；FSM | 当前 crossing stand-on/overtaken 永久 HOLD |
| TS-23 | 数值边界 | release 连续确认=10s；要求有效观测、CPA passed、持续 separating、guard 内不再跌破、实际 hull clearance≥`max(50m,max(Los,Lts),|vrel|*max(Tchi,TU,10s))+uncertainty`，再加双方 support | [R12][R13][R25][R26] + DESIGN_DECISION | DP-10/11；FSM | 删除固定190m和单 `TCPA<=0` release |
| TS-24 | 数值边界 | OT commit 前同时评估 target-track port/starboard corridor；先最大化可达最小 clearance，再最小化 route/action deviation；数值并列时 starboard 仅作 deterministic ODD tie-break。commit 后 side 锁定 | [R14][R17][R24][R30] + DESIGN_DECISION | DP-08/12；FSM/Aggregate | 当前无条件 starboard；tie-break 不冒充 Rule13 |
| TS-25 | 数值边界 | constraint priority：MUST_ACT > locked/committed mandatory > action candidate > MAY_ACT > stand-on watch > monitor；无共同 corridor=`MANEUVER_CONFLICT`；course conflict 可产生 speed/STOP，STOP 要求 speed lower bound=0 | [R14][R31][R33] + DESIGN_DECISION | DP-12；Aggregate/Core gate | 当前 any-starboard/first-target；speed floor=0.25 无法 STOP |
| TS-26 | 接口语义 | Tracker 必须输出 immutable `TrackSnapshot(TrackKey,status,state,covariance,hull,observed_at,generated_at,source,quality,optional maneuverability)`；缺 generation 只能显式 legacy unknown | VR-18 | DP-04/11/13；Tracker→Builder | 当前 tuple 无 generation/status/source |
| TS-27 | 接口语义 | ObservationBuilder 只验证/标准化/派生 GeometryFacts 与 health；未知不填 0。Planner 与 Evaluator 各自消费同一 physical facts 后独立解释 | VR-02/18 | DP-02/04/13；Builder | 当前 adapter 合成 age=0，Mid import evaluator classifier |
| TS-28 | 接口语义 | `EncounterLifecycle.step(cycle)->EncounterDecisionSnapshot` 是同步 pure-transition API；内部 private-copy，全部 invariant 通过后 atomic commit；reset 接收 epoch/reason | VR-17/19 | DP-01/03/14；Lifecycle | 当前 facade 逐 dict/set mutation |
| TS-29 | 接口语义 | Snapshot 含每目标 key/episode/health/kind/role/risk/lock/action/side/Rule17/release facts、AggregateDirective、events、profile hash；不得含 CasADi/IPOPT objects | VR-01/19/20 | DP-03/14/15；Lifecycle→Assembler | 当前 decision facts 藏在 facade locals/dicts |
| TS-30 | 接口语义 | L1 只把 Snapshot+LOS 映射为 MidMpcProblem；无法表达 per-target direction/STOP 等约束时返回 `CORE_CAPABILITY_MISMATCH`。Pure core仍只执行数学求解 | VR-17/20 | DP-01/12/14；Assembler/Core | 当前 global preferred side 静默覆盖全部targets |
| TS-31 | 接口语义 | strict failure statuses 至少含 OBSERVATION_UNUSABLE、INPUT_CONFLICT、TIME_GAP、MANEUVER_CONFLICT、CAPACITY_EXCEEDED、CORE_CAPABILITY_MISMATCH；均带owner/reason/evidence且no fallback | VR-13/14/20 | DP-12/13/14；Adapter/Session | 当前多映射为泛化 INVALID_INPUT/NUMERICAL_FAILURE |
| TS-32 | 接口语义 | reset 清空active states/tombstones/LOS/warm-start/cache，递增epoch并记录reason；time rewind/session restart/algorithm change/track authority change必须reset | [R40][R41] + DESIGN_DECISION | DP-11/14/15；Adapter | 当前reset无epoch/reason evidence |
| TS-33 | 接口语义 | 保留 PlannerTrace 1.x 外层；新增 versioned `lifecycle` 子文档和 typed transition events。minor只增optional字段，breaking变更升major | [R42][R43] + VR-21 | DP-14/15；Trace | 当前 Mid 细节为自由字典 |
| TS-34 | 接口语义 | live event ring容量1024；完整events由Experiment persistence增量写JSONL。overflow记录dropped count；sink失败=`EVIDENCE_INCOMPLETE`，不得宣称验收通过 | [R42][R46] + DESIGN_DECISION | DP-15/16；Session/Persistence | 当前frames/events内存无界且无transition sink |
| TS-35 | 接口语义 | Planner ODD hash对resolved values做canonical JSON SHA-256，不含绝对路径；build/profile/evaluator hashes分别记录 | [R43][R44] | DP-15；Trace/Manifest | 当前部分hash含路径或只反映build |
| TS-36 | 接口语义 | GUI 分别标注Planner interpretation/profile和Evaluator verdict/profile；显示真实81-point/1200s轨迹、phase/reason/targets/conflict/capacity/core status、IPOPT identity。能力提升须通过A/B/C/D四层门 | VR-21 | DP-15/16；GUI/Capability | 当前来源混合、轨迹时间网格错误、G3不能证明L0 contract |

### Published Playground Profile v1

| 参数 | 值/公式 | 性质 |
|---|---|---|
| solve/deadline | 5 s / 20 s | 当前工程配置 |
| horizon | 80 intervals × 15 s = 1200 s；81 state samples | MASS parity + 公共映射修正 |
| track age | fresh≤1 s；usable≤5 s；reacquire=5 s；tombstone=10 s | Planner ODD |
| entry/release evidence | entry confirm=5 s；Rule17 window=10 s；release confirm=10 s | Planner ODD |
| clearance | hard hull margin=50 m；comfortable=150 m；release按TS-23动态放大 | Planner ODD，与Evaluator独立 |
| covariance confidence | 0.99；只有Gaussian/PSD/layout已知时使用 | Planner ODD |
| capacity | required targets≤16 | frozen core contract |
| speed/turn dynamics | 从 Ship/TrackSnapshot maneuverability facts读取；缺失ownship facts=INVALID_INPUT | plant authority，不用Mid默认值冒充 |

---

## 组件 3：决策卡片集

### Step4 基础裁决

| VR | 对象 | Final 裁决 |
|---|---|---|
| VR-01 | module scope | L0为纯Python stateful deep module；Assembler/IPOPT/Adapter/L4独立 |
| VR-02 | authority | 共享physical facts；Planner与Evaluator各自解释 |
| VR-03 | state model | per-target deterministic FSM + orthogonal typed facts |
| VR-04 | observation | immutable cycle/observation，generation/provenance/validity/maneuverability显式 |
| VR-05 | classification | EncounterKind与Role正交；边界/低速可UNDETERMINED |
| VR-06 | risk | role+approaching+positive TCPA+footprint/uncertainty clearance；CV-CPA显式baseline |
| VR-07 | lock | physical-time confirmation、semantic candidate key、immutable commitment、auditable revision |
| VR-08 | action | baseline-relative substantial action；持续到actual achievement；OT双侧评估 |
| VR-09 | Rule17 | STAND_ON→MAY_ACT→MUST_ACT；target action evidence + target-alone proxy |
| VR-10 | release | COMMITTED→PAST_CLEAR→RELEASED；dynamic margin、持续分离、future guard |
| VR-11 | identity | `(id,generation)+episode`；coast/reacquire/tombstone/rearm |
| VR-12 | multi-target | 全target lifecycle后constraint aggregation；显式conflict/capacity |
| VR-13 | degraded | OBSERVED/DEGRADED/COASTING/UNUSABLE；UNUSABLE strict fail-stop |
| VR-14 | transaction | frozen Cycle/Snapshot、epoch+cycle+hash、private-copy atomic、solver status分离 |
| VR-15 | observability | typed schema/events、bounded ring+sink、profile provenance、source separation |
| VR-16 | acceptance | A contract→B mapping→C real-IPOPT→D parity/full/runtime |

### Step5 DESIGN-IT-TWICE 最终卡片

| Card/VR | 采纳方案 | 关键收益 | 被弃用方案 |
|---|---|---|---|
| CARD-01 / VR-17 | Deep Transactional Lifecycle | decision与execution分离；atomic/idempotent；单state owner | embedded solver engine；event-sourced actors |
| CARD-02 / VR-18 | Tracker-Authoritative Rich Contract | identity/freshness来自事实源；Lifecycle不猜track | adapter heuristics；Lifecycle内置tracker |
| CARD-03 / VR-19 | Orthogonal Deterministic FSM | 规则阶段稳定、无framework依赖、transition可穷举 | hierarchical statechart；risk score authority |
| CARD-04 / VR-20 | Constraint-Set Aggregation + Single NLP | 全目标共同可行集、一次IPOPT、冲突显式 | multi-mode多次solve；sequential primary arbitration |
| CARD-05 / VR-21 | Typed Schema + Bounded/Live Sink + Layered Gates | contract、runtime和GUI证据可复现 | journal作control authority；trace-only acceptance |

---

## 组件 4：证据矩阵

完整书目信息、链接、代码行与三类置信度见设计日志 0.4 和“参考文献”。本表保留全部 R1..R46 的结论与用途；所有检索置信均已在 Step3 获用户确认。

| Ref | 类型 | 核心证据 | 用途/边界 |
|---|---|---|---|
| R1 | PROJECT_FACT | 当前facade混合classification/commit/release/aggregation/solve | 证明拆分必要；不代表现状正确 |
| R2 | PROJECT_FACT | Mid integration、single、multiship和capability tests | 当前G3基线；不证明新L0 contract |
| R3 | DOCUMENTED_INTENT | 七层架构L0/L1.6/L4.3/LX | 层级责任权威意图 |
| R4 | PROJECT_FACT | MASS pure input/decision seams | 可借鉴边界；不搬ROS/GNC |
| R5 | DOMAIN_EVIDENCE | Eriksen逐目标FSM、COLREG MPC、多目标义务 | FSM/Rule17/multi-target precedent；参数不可照搬 |
| R6 | DOMAIN_EVIDENCE | IMO COLREG Rules 8/13-17 | 规则角色/义务；无工程数值 |
| R7 | DOMAIN_EVIDENCE | 16类分类、逐步安全距离研究 | 分类/约束参考；场景适用有限 |
| R8 | DOMAIN_EVIDENCE | USCG Rule13/14/16/17正文 | OT无固定passing side；early/substantial/past-clear |
| R9 | DOMAIN_EVIDENCE | 逐船DES/FSM、理解与预测分离 | per-target state与multi-target结构 |
| R10 | DOMAIN_EVIDENCE | 离散COLREG state在优化周期冻结 | cycle freeze |
| R11 | PROJECT_FACT | MASS activation FSM非对称hysteresis | pure transition precedent；阈值不迁移 |
| R12 | DOMAIN_EVIDENCE | 动态ship domain依尺度/速度/role/action | dynamic clearance |
| R13 | DOMAIN_EVIDENCE | IMO manoeuvrability criteria | Tchi/TU/turning/stopping事实 |
| R14 | DOMAIN_EVIDENCE | USCG Handbook Rules7/8/13-17 | rule strength、doubt、Rule17、effectiveness |
| R15 | DOMAIN_EVIDENCE | IMO radar CPA/TCPA/trial manoeuvre | Planner参数应按本船设定；无通用阈值 |
| R16 | DOMAIN_EVIDENCE | IMO manoeuvring information | plant maneuverability进入contract |
| R17 | DOMAIN_EVIDENCE | AIS实证动作幅度/时机/OT side随ODD变化 | 否决固定通用角度/side |
| R18 | DOMAIN_EVIDENCE | action point受relative speed/target length/水域影响 | risk timing因素；适用性低 |
| R19 | DOMAIN_EVIDENCE | CPA+ship-domain联合风险 | DCPA/TCPA/尺度/relative speed |
| R20 | DOMAIN_EVIDENCE | CV/straight CPA对目标机动的限制 | prediction失效边界 |
| R21 | DOMAIN_EVIDENCE | protocol evaluation与planner decision分责 | Planner/Evaluator分离 |
| R22 | PROJECT_FACT | MASS onset snapshot和正交facts | locked classification/state precedent |
| R23 | DOMAIN_EVIDENCE | 概率COLREG分类边界翻转 | UNDETERMINED/hysteresis必要；阈值仍ODD |
| R24 | DOMAIN_EVIDENCE | OT执行依环境/速度/间距/能力 | 无固定距离/side |
| R25 | DOMAIN_EVIDENCE | dynamic quaternion ship domain | release/risk需尺度、速度、操纵性 |
| R26 | DOMAIN_EVIDENCE | mission path与COLAV分层、hazard后恢复 | PAST_CLEAR与LOS recovery分离 |
| R27 | DOMAIN_EVIDENCE | The Dream Star Rule17判例 | MAY/MUST trigger不同 |
| R28 | DOMAIN_EVIDENCE | MAIB迟到/轻微动作事故分析 | 反证5°/迟行动作 |
| R29 | DOMAIN_EVIDENCE | target intention + reachable velocity + NL-VO | appropriate action/target-alone proxy |
| R30 | DOMAIN_EVIDENCE | planned-path geometry验证passing | actual side/交点证据，不只首控符号 |
| R31 | DOMAIN_EVIDENCE | 多船候选必须同时避开所有危险目标 | constraint-set aggregation |
| R32 | DOMAIN_EVIDENCE | Imazu多船场景验证 | multi-target fixtures；非最小集标准 |
| R33 | PROJECT_FACT | MASS primary score-gap/sample hysteresis | primary稳定排序；参数不直接迁移 |
| R34 | PROJECT_FACT | tracker→PlannerInput丢generation/status/age authority | CARD-02直接缺口 |
| R35 | DOMAIN_EVIDENCE | radar/AIS lost/swap/association/COG validity | rich track contract；无统一阈值 |
| R36 | PROJECT_FACT | VIMMJIPDA内部有existence/missed/termination/cov propagation | 上游事实可用但当前public contract丢失 |
| R37 | DOMAIN_EVIDENCE | 低速COG/heading可观测限制 | low-speed invalid |
| R38 | DOMAIN_EVIDENCE | ASTERIX track status/coasting/time/accuracy | generation/status/provenance模式 |
| R39 | DOMAIN_EVIDENCE | chi-square ellipse/chance constraint | Gaussian covariance margin；confidence属ODD |
| R40 | PROJECT_FACT | maneuverability/cycle/reset/gap/transaction缺口 | CARD-01/02/05直接缺口 |
| R41 | DOMAIN_EVIDENCE | ROS time jump semantics | gap/reset需应用定义 |
| R42 | PROJECT_FACT | PlannerTrace/session/GUI/tests当前证据链 | CARD-05基础与缺口 |
| R43 | DOMAIN_EVIDENCE | CloudEvents/OpenTelemetry/SemVer | typed event/version/exporter precedent |
| R44 | DOMAIN_EVIDENCE | RFC8785 canonical JSON | stable profile/input hash |
| R45 | PROJECT_FACT | command-angle test与actual trajectory evidence不一致 | L4必须看实际轨迹 |
| R46 | DOMAIN_EVIDENCE | bounded queue/exporter机制 | live ring+durable sink；容量属ODD |

---

## 组件 5：技术分解完整树

### Owner map

```text
Tracker authority
  -> TrackSnapshot[]
  -> ObservationBuilder + Planner-neutral Geometry
  -> EncounterCycle
  -> EncounterLifecycle.step()           [L0, only state owner]
       -> PairwiseDecision[]
       -> ConstraintSetAggregator
       -> AggregateDirective
       -> EncounterDecisionSnapshot
  -> MidMpcProblemAssembler               [L1, stateless mapping]
       -> MidMpcProblem or typed mapping failure
  -> MidMpcIpoptSolver                    [pure mathematical core]
       -> raw result + prepared/row evidence
  -> Solution Acceptance                  [L4, no decision authority]
  -> Adapter / Session / GUI / Persistence[LX execution and evidence]
```

### TD-01 Stateful COLREG Encounter Lifecycle

| 子模块 | DP | 输入 | 输出 | Owner | 状态 |
|---|---|---|---|---|---|
| Track contract | DP-04/11/13 | tracker association/state/covariance | TrackSnapshot | Tracker | ✓ VR-18/TS-26 |
| ObservationBuilder | DP-02/04/13 | TrackSnapshot + ownship plant facts | PairwiseObservation + health | planner-neutral boundary | ✓ VR-02/04/13 |
| Geometry | DP-02/05/06 | ENU kinematics/hulls | range/bearing/relative velocity/DCPA/TCPA/validity | planner-neutral module | ✓ VR-02/TS-01..10 |
| Classification/role | DP-05 | GeometryFacts + Planner ODD | kind/role/doubt | Lifecycle | ✓ VR-05 |
| Risk entry | DP-06 | role/CPA/clearance/uncertainty | monitor/candidate/urgent evidence | Lifecycle | ✓ VR-06/TS-19..20 |
| Lock/hysteresis | DP-07 | candidate key + timers | locked encounter/role/baseline | Lifecycle | ✓ VR-07 |
| Action/side | DP-08 | lock + maneuverability + corridors | course/speed commitment | Lifecycle | ✓ VR-08/TS-21/24 |
| Rule17 | DP-09 | stand-on state + target action/reachable set | STAND_ON/MAY/MUST | Lifecycle | ✓ VR-09/TS-22 |
| Achievement/release | DP-08/10 | actual observation + commitment | achieved/PAST_CLEAR/RELEASED | Lifecycle | ✓ VR-10/TS-23 |
| Identity/rearm | DP-11 | TrackKey/status/discontinuity | episode/coast/tombstone/rearm | Lifecycle | ✓ VR-11/18 |
| Multi-target aggregate | DP-12 | all PairwiseDecisions | AggregateDirective/status | ConstraintSetAggregator | ✓ VR-12/20 |
| Atomic handoff | DP-14 | EncounterCycle | immutable Snapshot/events | Lifecycle | ✓ VR-14/17 |
| L1 mapping | DP-01/12/14 | Snapshot + LOS | MidMpcProblem/mapping failure | Assembler | ✓ VR-17/20/TS-30 |
| Evidence | DP-15 | Snapshot/solve/actual trajectory | typed trace/events/sink | Adapter/Session/Persistence | ✓ VR-15/21 |
| Acceptance | DP-16 | contracts + real runs | A/B/C/D evidence | tests/evaluator/runtime | ✓ VR-16/21 |

无 `DECOMPOSITION_INCOMPLETE`。实现不得跳过 Track authority、atomic handoff、core capability gate 或 Layer A/B，直接从场景结果反推 L0 正确。

### 建议工程切片顺序

1. TrackSnapshot/EncounterCycle/GeometryFacts schema 与 legacy fail-visible bridge。
2. Pure Pairwise FSM：identity、health、classification、risk、lock、Rule17、release/rearm。
3. ConstraintSetAggregator 与显式 conflict/capacity/core capability。
4. Stateless L1 Assembler；删除 facade 旧 commitment/released/aggregation state。
5. 80-interval/81-state trajectory mapping；保留 raw C++ parity。
6. Typed evidence、bounded ring、sink、GUI source separation。
7. Layer A/B 后运行 C/D；逐项提升 capability。

---

## 组件 6：弃用方案及理由

完整逐项文本见设计日志 0.7；以下覆盖 ALT-01..ALT-58，无遗漏。

| ALT | 主题 | 弃用结论 |
|---|---|---|
| 01..03 | L0 scope | helper-only仍浅；把LOS/IPOPT搬入L0过宽；Evaluator FSM作authority形成自评 |
| 04..06 | geometry/classification authority | 直接import Evaluator、复制全部数学、Evaluator verdict输入Planner均破坏职责或产生drift |
| 07..09 | lifecycle model | stateless重分类会flicker；mega enum爆炸；Evaluator FSM不具planner commitment语义 |
| 10..12 | observation | 直接消费PlannerInput泄漏层级；简化track facts不足；缺失字段填0伪造fresh |
| 13..15 | classification | 组合字符串焊死facts；risk门后才分类过晚；边界fallback CLEAR产生假阴性 |
| 16..18 | risk | action lead绑定1200s horizon；Evaluator 50m反控；单DCPA/TCPA/range不足 |
| 19..21 | hysteresis | instant commit、固定solve次数、exact-label reset/无条件merge均不稳定 |
| 22..24 | substantial/OT | 固定5°+one-shot、统一30°、OT固定starboard均被否决 |
| 25..27 | Rule17 | 永久HOLD、单TCPA门、扩大17(c)范围均不符合分阶段语义 |
| 28..30 | release | `TCPA<=0`、固定190m/own-length倍数、过早删state或等route完成均不足 |
| 31..33 | identity/rearm | 永久released ID、一帧丢失即删、裸ID都会丢失或误继承duty |
| 34..36 | multi-target | first/any-starboard、先截断16、pairwise=>aggregate推论均不安全 |
| 37..39 | degraded | 无track=clear、cached plan fallback、忽略covariance/UNKNOWN target均隐藏风险 |
| 40..42 | transaction | facade逐项mutation、无epoch/hash、solver成功才提交decision均破坏幂等与责任 |
| 43..45 | evidence | 自由字典、无界/仅latest、路径hash/仅build hash均不可审计 |
| 46..48 | acceptance | 只看G3、只做unit、Planner/Evaluator共享标签或降阈值均不足 |
| 49..50 | CARD-01 | embedded solver engine让IPOPT反控state；event actors对单进程过重 |
| 51..52 | CARD-02 | adapter推断是第二tracker；Lifecycle内置tracking扩大故障域 |
| 53..54 | CARD-03 | statechart引入并行/event复杂度；risk score不应成为规则阶段authority |
| 55..56 | CARD-04 | 多次IPOPT放大deadline并可能反控commit；sequential primary不证明共同可行 |
| 57..58 | CARD-05 | journal作control authority过重；trace-only无法证明L0/L1 contract |

---

## 组件 7：需求场景与验收边界

### 场景矩阵

| SC | 场景 | 必须观察的 lifecycle | 行为验收 |
|---|---|---|---|
| SC-01 | Head-on | GW candidate→starboard commitment→achievement→past-clear→release | early/substantial starboard；actual hull clearance≥50m；无flicker |
| SC-02A | OT target-track port corridor | OT lock→port corridor commitment→past-clear→recovery | 实际通过侧=port；不累加小转向；持续keep-clear |
| SC-02B | OT target-track starboard corridor | OT lock→starboard corridor commitment→past-clear→recovery | 镜像通过；证明side由态势选择而非固定 |
| SC-03 | Crossing give-way | GW lock→starboard/astern constraint→release | early/substantial；避免cross ahead；actual clearance≥50m |
| SC-04A | Crossing stand-on cooperative | STAND_ON；目标适当动作；不无故升级 | ownship保持；目标动作与风险改善证据完整 |
| SC-04B | Crossing stand-on non-cooperative | STAND_ON→MAY_ACT→MUST_ACT | transition reason/target-alone proxy明确；actual避碰成功 |
| SC-05 | Overtaken | STAND_ON/Rule17 path | 不误判ownship为overtaking；必要时可升级，不永久HOLD |
| SC-06 | Multi-target compatible | 全target states→共同corridor→single NLP | Ship0对全部required targets≥50m；primary切换不重置状态 |
| SC-06X | Multi-target contradictory | MANEUVER_CONFLICT或speed/STOP | contract PASS=结构化冲突，不是伪造SUCCESS |
| SC-07 | Boundary flicker | candidate confirmation/locked semantics | clear/OT/clear噪声不造成port/starboard振荡 |
| SC-08 | Loss/reacquire/ID reuse | OBSERVED→COASTING→reacquire或new generation | 短丢失不消除duty；新generation不继承旧commitment |
| SC-09 | Reset/retry/time gap | same-cycle idempotent、epoch reset、TIME_GAP | 无重复event/半更新；倒退或大gap不静默继续 |
| SC-10 | Capacity/core mismatch | >16 required或per-target direction不可表达 | 明确failure；solver未执行；无cached/fallback |

### 四层 acceptance gate

| Layer | 范围 | 必须通过 | 明确禁止 |
|---|---|---|---|
| A | Lifecycle contract | 全FSM guard、identity、health、Rule17、release/rearm、aggregate、retry/reset；毫秒级、无CasADi/Evaluator verdict | 用scenario结果替代transition证明 |
| B | L0→L1 mapping | commitment不累加、minimum持续、physical schedule、全部required targets、dynamic margin、capacity/core mismatch | silent truncation/global-side collapse |
| C | real IPOPT closed-loop | SC-01..06；raw G3+Evaluator hard gate、real IPOPT、no fallback、actual action/side/clearance/release/recovery | 只断言selected command、预测线或constraint activated |
| D | regression/runtime | frozen C++ parity、focused+full pytest、Ruff/format/diff、capability evidence、8010 real planner event和GUI来源分离 | focused tests冒充full；截图冒充planner event |

### PASS 语义

- 支持的 HO/CS/OT/overtaken/multi-target compatible 场景必须是 Ship0 raw G3 与独立 Evaluator hard gate 同时 PASS。
- `MANEUVER_CONFLICT/CAPACITY_EXCEEDED/CORE_CAPABILITY_MISMATCH/OBSERVATION_UNUSABLE` 场景的 contract PASS 是正确 fail-stop、solver未执行、证据完整；不是碰撞自由 SUCCESS。
- Target-target 固有碰撞单独记录 global evidence；不计为 Ship0 Mid-MPC failure，也不得隐藏。
- G3 仅表示固定 profile/seed/场景下可观察能力；不表示法律认证、任意多船安全、MASS ROS2/GNC 验收或实船可用。

### 8010 可见性门

- 算法卡为 `Mid-MPC`；内部稳定 ID=`mid_mpc_ipopt`；solver=`IPOPT`。
- 轨迹来自本次 raw IPOPT 解：80 control intervals、81 state samples、终点1200s；held plan与fresh solve明确区分。
- 显示 lifecycle phase/reason、Rule17、commit baseline/side、selected/required targets、aggregate status、profile hashes、IPOPT status/iterations/time/objective/slacks。
- Planner 与 Evaluator 两个来源独立显示；Fan-MPC仅为另一个算法，不参与Mid证据。

---

## 组件 8：已知冲突与未闭环盲区

| ID | 冲突/UNKNOWN | 本方案处理 | 是否阻塞 |
|---|---|---|---|
| K-01 | COLREG不提供substantial angle、entry、release、Rule17数值 | Published Planner ODD v1显式定义；hash入证据；不冒充法规 | 不阻塞；需场景标定 |
| K-02 | 当前frozen core只有global side/common schedule | L1 representability gate；不折叠。支持场景若需要则以独立pure-core扩展切片处理，并保留parity mode | 不阻塞L0；可能阻塞特定multi-target SUCCESS |
| K-03 | 当前raw solver 80 decisions却公开80 points t=0..1185 | raw parity不改；public mapping改为81 states t=0..1200 | 必须在Layer B修复 |
| K-04 | frozen CPA rows存在own k+1 vs target k、无midpoint rows的parity quirks | 保留parity；L4使用continuous/swept CPA；不得靠放松50m掩盖 | 已知残余；Layer C持续验证 |
| K-05 | 真实tracker可能没有target maneuverability | Playground God/known plant提供；其他source标UNKNOWN，Rule17 MUST proxy不得伪造 | 不阻塞Playground；限制外推 |
| K-06 | CV target prediction不能覆盖突发机动 | profile/provenance显式；receding update+uncertainty+L4；不宣称任意目标模型安全 | 不阻塞固定场景 |
| K-07 | Gaussian covariance margin依分布/layout/independence | 仅在假设成立时用0.99 margin；否则DEGRADED/UNUSABLE | 不阻塞God zero-covariance场景 |
| K-08 | Rule17(b) target-alone没有唯一法律认可算法 | reachable-set proxy明确标engineering approximation，保留input/model evidence | 不阻塞；不作法律认证 |
| K-09 | target-target碰撞不受Ship0控制 | 分开Ship0/global accounting | 不阻塞Ship0 capability |
| K-10 | 当前God/KF public contract无generation/status | 先扩Tracker-authoritative contract；legacy bridge仅显式UNKNOWN，不默认fresh | 阻塞CARD-02实现首切片 |
| K-11 | current profile speed floor=0.25不能STOP | 新profile STOP mode要求lower bound=0；若plant/core不支持则CORE_CAPABILITY_MISMATCH | 不阻塞普通HO/CS/OT |
| K-12 | 固定seed场景PASS无法外推至任意ODD | capability tuple绑定scenario/seed/profile/build | 不阻塞；声明边界 |

上述均已进入规约、failure status或验收边界；无隐藏 `DECOMPOSITION_INCOMPLETE`。若 to-spec/实现发现新证据证明 VR/TS 不可行，必须暂停并回炉受影响的 design-grounding 决策点。

---

## Step6 移交记录

用户于2026-08-11明确接受本方案包。交付链改为本机现行技能：

移交统计：3个执行阶段，4个现行技能（`to-spec`、`implement`、`tdd`、`code-review`）；0个已移除 superpowers 技能依赖。

1. `to-spec`：把本方案包综合为设计/实施 Spec、确认最高公共测试 seams、发布 ready-for-agent issue。
2. `implement` + `tdd`：按已确认 seams 做逐条 red→green vertical slices。
3. `code-review`：实现完成后按 Standards/Spec 双轴复核。

已移除的 superpowers brainstorming、writing-plans、subagent-driven-development 不再作为交付依赖。
