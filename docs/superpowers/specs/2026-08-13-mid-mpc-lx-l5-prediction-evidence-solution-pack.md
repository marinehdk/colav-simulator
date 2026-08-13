# Mid-MPC LX/L5 Prediction Evidence 方案包

> 状态: 用户已接受，已交付to-spec  
> 模式: Redesign  
> 冻结基线: `b95851215fb9afab1e019e383687fe533ce6d6bb`  
> 权威决策日志: `docs/superpowers/design-logs/2026-08-13-mid-mpc-lx-l5-prediction-evidence-design-log.md`
> 正式Spec: `docs/superpowers/specs/2026-08-13-mid-mpc-lx-l5-prediction-evidence-spec.md`; GitHub `marinehdk/colav-simulator#27`

## 方案包契约

- 可做: 在本方案已裁决边界内完成组件、数据流、错误处理、测试 seam、命名和局部实现优化。
- 不可做: 推翻 semantic record + occurrence events + pure reducer 核心方案；发现新矛盾证据时必须回炉 design-grounding。
- 不可做: 重提 `ALT-01..ALT-24` 已弃用方案。
- 不可做: 擅改坐标、单位、符号、时序、数值或接口规约；变更必须回炉裁决。
- 不可做: 借 Evidence 重构修改 Mid-MPC 数学问题、IPOPT 结果、L4 verdict、执行命令、fallback 或 capability claim。
- 不可做: 把当前 7 个严格 L4 闭环失败改为 PASS、xfail、降低阈值或隐藏；它们属于后续算法/L4能力工作。

## 1. 术语表

| 术语 | 定义与来源 | 本方案含义 | 不是 | 关联DP |
|---|---|---|---|---|
| Prediction Evidence | 可重放的预测、求解、验收和执行证据集合。[R1][R12] | Mid-MPC 专属深模块；由稳定语义记录、运行事件和机械投影组成。 | 新规划器、COLREG决策器或L4复核器。 | DP-01 |
| Semantic Record | 在生成后不再改变的实体及其派生关系。[R13][R15] | candidate、grid、ownship/target prediction、solver/L4 Certificate等稳定事实。 | dispatch、hold或artifact完成状态的可变容器。 | DP-01,09 |
| Occurrence Event | 一次运行中不可变、可排序、可建立因果关系的发生记录。[R14][R15] | cycle、input、attempt、solve、L4、commit、hold、command、artifact、reset和terminal outcome。 | content hash或覆盖式status字段。 | DP-03,08 |
| EvidenceEnvelope | 跨`MPCSolution`通用边界的最小algorithm-neutral封装。[R17] | 携带semantic root、初始events、schema和projection入口；Adapter不解析Mid内部字段。 | 全局PlannerTrace重写或Mid-aware Adapter。 | DP-02,14 |
| Acceptance Certificate | L4对candidate的typed结论、layers、findings及witness。[R9] | 证明L4当时为何接受或拒绝candidate。 | 计划已经commit或正在执行的证明。 | DP-07 |
| Accepted Plan Receipt | Adapter完成最终deadline/freshness检查并原子提交后的事实。[R9] | 唯一“计划已进入执行authority”证明。 | L4 PASS的别名。 | DP-02,07 |
| Authority Timeline | 由事件归约得到的唯一运行read model。[R16] | 同时区分latest cycle/attempt/solve、active receipt、history、held validation、applied command和failure。 | GUI缓存、最后一条trace或控制状态本身。 | DP-04 |
| OccurrenceId | 一次发生的局部唯一身份。[R14][R17] | `(run_id, evidence_epoch, event_seq)`；sequence在epoch内严格递增。 | semantic content hash。 | DP-03 |
| Semantic Hash | 对versioned canonical bytes的内容标识。[R25][R26] | candidate、Certificate、Receipt及evidence root分别计算并用`derived_from`连接。 | 发生次数、来源真实性或数字签名。 | DP-03,09,11 |
| PredictionGrid | OCP预测时域及采样拓扑。[R19][R20] | 80个15s区间、81个state knots、总时域1200s。 | 81个独立controls或旧90s轨迹。 | DP-05 |
| State Knot | OCP区间边界的状态样本。[R19] | knot 0为当前实测状态；knot `k+1`由interval `k`决策积分得到。 | interval control本身。 | DP-05 |
| Optimization Interval Reference | 求解器在区间`[t_k,t_{k+1})`使用的航向/航速决策。 | 80个typed references并引用raw primal位置。 | hold时真实下发值。 | DP-05 |
| Runtime Applied Reference | Adapter在当前elapsed时刻真实采样的控制参考。[R20] | 保持现有相邻控制列线性插值策略并明确记录policy/elapsed。 | Candidate4新增ZOH策略。 | DP-05,08 |
| TrackKey | tracker目标世代身份。[R10] | `(target_id, generation)`；generation变化代表新目标实体。 | 单独`target_id`。 | DP-06 |
| Purpose Prediction | 为明确消费目的生成的目标轨迹。[R21] | 至少区分`NLP` selected与`L4_SAFETY` all-relevant；同输入时可reconcile。 | 强迫L3/L4共享同一可变对象。 | DP-06 |
| Inline Projection | 有界、确定性的实时证据摘要。[R22][R23] | 8192-byte内按Tier0身份/verdict、Tier1 mandatory failures、Tier2 worst safety保留。 | full artifact或静默删除失败witness。 | DP-07,10 |
| Full Artifact | terminal attempt的完整canonical证据文件。 | 每terminal attempt一份；异步持久化；由immutable descriptor和status events描述。 | 每个hold tick复制一份文件。 | DP-10 |
| PredictionRenderSnapshot | Authority Timeline的只读展示投影。[R18][R31] | API/GUI唯一新Evidence展示输入；含active suffix、aligned targets、provenance和Planner/Evaluator分栏。 | GUI自行重判COLREG/L4或缓存authority。 | DP-12 |
| Integrity Verification | bytes、schema、hash、lineage及机械投影一致性验证。[R26][R28] | public verifier V0-V6的一部分。 | 来源认证、签名、attestation或IPOPT bit-exact。 | DP-11 |
| Numerical Replay | 按冻结问题、容差和L4规则复算数值语义。 | V3/V4确定验证；V7 IPOPT re-solve仅diagnostic。 | 用新IPOPT结果改写历史verdict。 | DP-11 |
| Fail-stop | 失败后不继续沿用可执行计划且禁止fallback。[R9] | terminal solve/replan failure清active receipt、solution和warm state。 | 删除历史审计证据或让artifact失败撤销已提交command。 | DP-04,08 |

## 2. 技术规约表

| ID | 类别 | 锁定规约 | 单位/定义 | 来源 | 关联DP/接口 | 与现状差异 |
|---|---|---|---|---|---|---|
| TS-01 | 坐标系 | 公共frame标识保持`ENU`；轨迹数组必须用命名字段`north_m`,`east_m`，禁止依赖含糊`x/y`解释。 | 水平当地坐标；字段顺序`[north,east]`。 | PROJECT_FACT [R6][R20] | DP-05,06,12；PlannerInput/Evidence/Render | 新schema取消`x/y`作为权威；legacy alias仅兼容投影。 |
| TS-02 | 坐标系 | ownship 6-state布局冻结。 | `[north_m,east_m,heading_rad,surge_mps,sway_mps,yaw_rate_rad_s]`。 | PROJECT_FACT [R6][R17] | DP-05；PlannerInput | 不改现有布局；Evidence显式命名。 |
| TS-03 | 坐标系 | target state布局冻结。 | `[north_m,east_m,v_north_mps,v_east_mps]`；covariance同顺序`4x4`。 | PROJECT_FACT [R17][R21] | DP-06；TrackedObstacle/TrackPrediction | 不改数学；新增purpose/reference元数据。 |
| TS-04 | 物理量单位 | 线性位置/距离、速度、加速度统一SI。 | `m`,`m/s`,`m/s^2`。 | PROJECT_FACT [R6][R17] | DP-05,06,12；全部trajectory/witness | 无变化；字段名强制带单位。 |
| TS-05 | 物理量单位 | 时间统一秒；性能持续时间统一毫秒并显式后缀。 | sim/reference/grid=`s`；solver/tail=`ms`。 | PROJECT_FACT [R6][R32] | DP-03,05,13 | 无变化；禁止无后缀duration。 |
| TS-06 | 物理量单位 | 航向/角速度使用弧度与弧度每秒；UI可派生度显示。 | canonical=`rad`,`rad/s`；display=`deg`仅投影。 | PROJECT_FACT [R6][R17] | DP-05,12；Evidence/Render | GUI不可把度回写canonical evidence。 |
| TS-07 | 符号约定 | 航向0指北，正方向顺时针；body x向前、y向右舷；NE速度按现有变换。 | `vN=u*cos(psi)-v*sin(psi)`；`vE=u*sin(psi)+v*cos(psi)`。 | PROJECT_FACT [R6] | DP-05,06；ownship/target reconciliation | 无变化；Evidence固定符号说明。 |
| TS-08 | 符号约定 | passing side与转向不得用裸整数跨公开接口。 | typed enum；兼容`preferred_side∈{-1,0,1}`只留optimizer内部。 | DESIGN_DECISION VR-11,17 | DP-06,12；TrackEvidence/Render | 新Evidence从内部整数提升为语义enum。 |
| TS-09 | 时序约定 | OCP网格固定80 intervals/81 knots/15s/1200s。 | `t_k=k*15s`,`k=0..80`。 | DOMAIN+PROJECT [R19][R20] | DP-05；PredictionGrid | 替代旧UI 90s含糊展示；不改solver。 |
| TS-10 | 时序约定 | interval `k`作用于`[t_k,t_{k+1})`并生成knot `k+1`；terminal knot无新control。 | 80 control references对应81 states。 | DOMAIN [R19] | DP-05；OwnshipTrajectory | 新Evidence显式化，解决off-by-one。 |
| TS-11 | 时序约定 | runtime hold保持现有线性插值。 | `policy=LINEAR_INTERPOLATION`；以accepted time计算`elapsed_s`。 | PROJECT_FACT+DECISION [R20], VR-10 | DP-05,08,12；Adapter/Render | 明确记录；Candidate4不得改ZOH。 |
| TS-12 | 时序约定 | 发生排序不依赖wall clock。 | `run_id + evidence_epoch + event_seq`；epoch内sequence从0或1固定实现后不可混用、严格递增。 | DOMAIN+DECISION [R14][R28], VR-09 | DP-03,08,11；EventStore/Verifier | 新增唯一ordering authority。 |
| TS-13 | 时序约定 | 每cycle恰有一个terminal control outcome。 | `COMMITTED|HELD|REJECTED|FAILED`之一；artifact status不是control outcome。 | DESIGN_DECISION VR-13 | DP-08；Adapter/Reducer | 补齐当前早期失败缺口。 |
| TS-14 | 数值边界 | canonical Evidence只接受有限数值。 | NaN/Inf拒绝；negative zero按`colav.python-json@1`定义归一；不声称JCS。 | PROJECT+DOMAIN [R25][R26] | DP-09,11；Canonicalizer | 新增顶层canonicalizer contract；旧hash不变。 |
| TS-15 | 数值边界 | 目标容量与inline容量保持有界。 | solver targets `<=16`；inline UTF-8 canonical bytes `<=8192`。 | PROJECT+DOMAIN [R22][R23] | DP-06,07,10,13 | 新增确定性tier和capacity failure。 |
| TS-16 | 数值边界 | 总deadline保持20s；同步Evidence tail计入同一deadline。 | 20s冻结；250ms不是新设计常量，须实测重校准。 | PROJECT+DECISION [R9][R32], VR-14/18 | DP-13,15；Adapter/Benchmark | 新增combined-tail预算；不得提高20s。 |
| TS-17 | 数值边界 | non-interference比较规则冻结。 | objective abs `1e-5`；trajectory/raw/diagnostic abs `1e-6`；CPA raw-g沿既有scale-aware规则；离散/hash/command exact。 | TEST_EVIDENCE [R30][R35] | DP-11,15；Replay/Tests | 新增Evidence不得改变数值基线。 |
| TS-18 | 数值边界 | immutable arrays/mappings构造时复制并只读；输入不可原位回填。 | 深不可变；worker只返回新completion value。 | PROJECT+DECISION [R17][R27], VR-07 | DP-01,10；Models/Sink | 修复当前worker共享dict mutation。 |
| TS-19 | 接口语义 | `MPCSolution.evidence`为optional generic envelope。 | Mid存在Evidence→PlannerTrace1.1；其他算法无Evidence→1.0。 | PROJECT+DECISION [R17][R33][R34], VR-08 | DP-02,14；MPCSolution/PlannerTrace | additive minor；所有legacy字段保留。 |
| TS-20 | 接口语义 | Facade/Adapter ownership固定。 | Facade: candidate+Certificate；Adapter: Receipt+runtime events+atomic commit；sink/API/GUI: consume only。 | DESIGN_DECISION VR-04/16 | DP-02,04,08 | 消除多事实源。 |
| TS-21 | 接口语义 | semantic identity与occurrence identity分离。 | semantic objects用versioned SHA-256 content hash；events用OccurrenceId；`derived_from/caused_by`连接。 | DOMAIN+DECISION [R13][R14], VR-09 | DP-03,09,11 | 不再复用solve_id覆盖所有发生。 |
| TS-22 | 接口语义 | Track identity和预测purpose显式。 | `TrackKey(target_id,generation)`；`NLP`与`L4_SAFETY`分别记录coverage/reference/model/hash。 | PROJECT+DECISION [R10][R21], VR-11/17 | DP-06；TargetEvidence | 未进NLP目标不再静默消失。 |
| TS-23 | 接口语义 | Certificate、Receipt、artifact状态互不替代。 | L4 PASS≠commit；artifact COMPLETE/INCOMPLETE不改verdict；post-commit写失败不撤销command。 | DESIGN_DECISION VR-06/07/18 | DP-07,10,13 | 拆分当前混合状态。 |
| TS-24 | 接口语义 | inline截断按固定优先级。 | Tier0身份/verdict/reference；Tier1 mandatory failure；Tier2 worst safety；advisory/PASS先删。 | DOMAIN+DECISION [R22][R23], VR-06 | DP-07,10,12 | 不再超限即删除全部关键witness。 |
| TS-25 | 接口语义 | public verifier分层且claim受限。 | V0 bytes/digest；V1 schema；V2 lineage；V3 numerical；V4 L4；V5 projection；V6 authority；V7 re-solve diagnostic。 | DECISION VR-03/18 | DP-11,15；Verifier CLI/API | 新增单一入口；不声明authenticity/attestation。 |
| TS-26 | 接口语义 | RenderSnapshot是新GUI唯一authority projection。 | active suffix teal solid；invalid history grey dashed；rejected默认隐藏、开启后red dashed；Planner L4与Evaluator G3分栏。 | DOMAIN+DECISION [R18][R31], VR-12/17 | DP-04,12；REST/WS/GUI | GUI不再维护独立active/latest权威缓存。 |
| TS-27 | 接口语义 | 异步artifact通过immutable completion channel回到runner线程。 | bounded item/byte queue；close drain或terminal INCOMPLETE；worker不分配event_seq。 | DOMAIN+DECISION [R15][R27], VR-07/18 | DP-10,13；ArtifactSink/Adapter | 替换共享reference dict回填。 |

## 3. 最终决策卡片集

| 卡片 | 采纳方案 | 来源/工程验证 | 技术分解 | 失效边界 | 风险 | 可测性 | 推荐度 |
|---|---|---|---|---|---|---|---|
| S5-A 领域与权威 | 有界Mid深Evidence模块 | PROV、OTel、现有Facade/Adapter seam；focused基线。[R13][R15][R17][R35] | semantic record + occurrence events + reducer；Facade产Certificate，Adapter产Receipt/events，Render仅投影 | 缺失/乱序/hash/parent错误→INVALID且active为空；不改L4/command | 中 | 高：pure reducer、transition/property/tamper/non-interference | 5/5，VR-16 |
| S5-B 预测与展示 | typed语义轨迹图 + RenderSnapshot | CasADi 80/81语义、现有linear hold、L3/L4双预测。[R19][R20][R21] | Grid、81 knots、80 refs、runtime interpolation、TrackKey purpose predictions、render | shape/grid/source/reconciliation错误→INVALID；不猜测、不改command | 中高 | 高：raw复算、k边界、hold、ID reuse、render/browser | 5/5，VR-17 |
| S5-C 完整性与实时 | 同步完整性内核 + 有界异步持久化 | Adapter deadline、OTel export、sink及L4性能基线。[R9][R15][R27][R32] | validation/hash/inline/receipt/command同步；artifact/report异步；V0-V6 deterministic、V7 diagnostic | precommit evidence失败→无command；postcommit I/O失败→claim incomplete但command保留 | 中高 | 高：golden/tamper/slow disk/backpressure/deadline/RSS/delta | 5/5，VR-18 |

## 4. 证据矩阵

| 证据组 | 证据 | 支持结论 | 覆盖DP |
|---|---|---|---|
| Provenance/事件标准 | R1-R3、R13-R16、R28 | stable entity与activity/event分离；event immutable；因果/排序可验证；避免全项目event sourcing | 01,03,04,08,09,10,11,13 |
| Canonical/信任标准 | R4、R25-R26、R29、R34 | 固定canonicalizer/version；现有Python JSON非JCS；hash不等于signature；minor schema additive | 09,11,14 |
| 可访问状态/容量 | R18、R22 | status程序可判定；inline/event集合必须有界且明确截断 | 04,07,10,12,13 |
| OCP网格语义 | R19-R20 | 80 controls/81 states；当前hold是线性插值，Candidate4不改执行行为 | 05,08,12,15 |
| 目标预测 | R10-R11、R21 | TrackKey authority；L3 selected与L4 all-relevant预测coverage不同且都需记录 | 03,05,06,07,09,11 |
| 当前接口/authority | R5-R9、R17、R24、R31、R33 | Facade/Adapter ownership；PlannerTrace和GUI现有漂移；早期失败缺口；最小MPCSolution seam | 02,04,07,08,10,12,14 |
| Artifact现状 | R8、R23、R27 | 有界sink基础存在；inline会丢关键witness；worker当前原位修改共享dict | 07,10,13,15 |
| Replay/性能/测试 | R30、R32、R35-R36 | verifier仍分散；旧L4性能不含Evidence tail；focused 90 pass；严格闭环7 fail | 11,12,13,15 |
| 七层业务意图 | R12 | LX负责可观测/归因/复现，L5负责输出/交接/执行反馈 | 01,02,11,12,15 |

完整逐条引用、检索置信度、来源权威和场景适用性见权威设计日志`0.4 [EV]`；R1-R36均已在Step3逐批获用户确认，无UNKNOWN证据项。

## 5. 技术分解完整树

```text
TD-01 Typed Prediction Evidence + provenance/replay pipeline [DECOMPOSITION_READY]
├── Domain model: DP-01 -> VR-01, VR-16
├── Ownership seam: DP-02 -> VR-04, VR-16
├── Identity/lineage: DP-03 -> VR-09, VR-17
├── Authority timeline: DP-04 -> VR-05, VR-16
├── Ownship trajectory: DP-05 -> VR-10, VR-17
├── Target predictions: DP-06 -> VR-11, VR-17
├── Certificate/Receipt/projections: DP-07 -> VR-06, VR-16
├── Lifecycle events: DP-08 -> VR-13, VR-16
├── Schema/canonicalization: DP-09 -> VR-02, VR-18
├── Artifact lifecycle: DP-10 -> VR-07, VR-18
├── Replay verifier: DP-11 -> VR-03, VR-18
├── Render projection: DP-12 -> VR-12, VR-17
├── Realtime/backpressure: DP-13 -> VR-14, VR-18
├── Planner compatibility: DP-14 -> VR-08, VR-16
└── Verification gates: DP-15 -> VR-15, VR-18
```

全部子模块已完成Step2 grilling、Step3证据闭环、Step4裁决和Step5替代架构压力测试。无`DECOMPOSITION_INCOMPLETE`项。

## 6. 弃用方案及理由

| 类别 | 弃用方案 | 理由 | ALT |
|---|---|---|---|
| 模型 | 可变大JSON、自由`algorithm_details`、全项目event平台、全量snapshot canonical | hash/时态漂移，或blast过大，或因果仍需隐式推断 | 01,02,19,20 |
| Hash/验证 | 直接JCS重写旧artifact、SHA-only、IPOPT bit-exact、V1签名 | 破坏历史hash、验证不足、跨平台假失败或越scope | 03,04,05 |
| Ownership/兼容 | Facade提前receipt、GUI推断authority、单last trace、全局Trace2.0 | 混淆commit、产生stale状态或强迫其他算法迁移 | 06,07,10,14 |
| Certificate/Artifact | Certificate=Receipt、共享dict回填、同步持久化 | 丢失执行事实、竞态或挤占deadline | 08,09,23 |
| Identity/轨迹/目标 | 全UUID/全hash/solve_id；81 controls；只存NE；改ZOH；无generation；强制L3/L4共享 | 顺序/语义/执行行为/目标身份错误 | 11,12,13,21 |
| GUI/存储 | GUI重判；Artifact-first懒加载实时authority | 第二事实源；async失败时无实时轨迹 | 14,22 |
| Lifecycle/实时 | 从candidate才记；全同步I/O；全异步commit；无界queue；未测即沿用250ms；command-first telemetry | 早期失败消失、deadline/authority/资源失控或证据窗口 | 15,16,17,24 |
| 验收 | Candidate4顺带修7场景、xfail/降L4、HTTP200代替planner event | 越scope、隐藏缺陷或证据不足 | 18 |

## 7. 需求场景与验收边界

### 场景集合

| 组 | 场景 | 必须结果 |
|---|---|---|
| Fresh/commit/hold | SC-01,02,12,16 | Certificate与Receipt分离；active suffix按elapsed线性插值；deadline拒绝无Receipt/command。 |
| Replay/upgrade | SC-03,09,11 | semantic hash可重复；occurrence不同；旧canonicalizer可派发；IPOPT re-solve差异仅diagnostic。 |
| Rejection/fail-stop | SC-04,08 | latest failure可见；active清空；历史只读不可执行；无fallback。 |
| Grid/targets | SC-05,06 | 0..1200s、80/81无错位；未进NLP目标仍有TrackKey、admission和L4 relevance。 |
| Capacity/artifact | SC-07,10,13 | mandatory failure/worst witness保留；queue/backpressure不撤销command；同步tail仍受20s约束。 |
| Compatibility/live | SC-14,15 | VO/Fan/Nominal行为与trace保持；真实8010 Mid事件、IPOPT、no-fallback、active suffix、artifact/replay可见。 |
| Non-interference | SC-17 | 既有4项`SAFETY_SWEPT_CLEARANCE`、3项`COLREG_STAND_ON_DRIFT`保持相同failure family；不得伪造PASS。 |

### V1-V11验收门

| 门 | 验证面 | 完成条件 |
|---|---|---|
| V1 | Pure contracts | immutable models、canonical bytes、finite-number、grid/TrackKey边界及negative tests通过。 |
| V2 | Timeline | transition table、exactly-one terminal、reset、duplicate/out-of-order/property tests通过。 |
| V3 | Public replay | V0-V6 CLI/API对golden及tamper corpus给出typed结果；V7明确diagnostic。 |
| V4 | Adapter transaction | pre/post deadline、fresh/hold/reject/failure、callback、artifact failure、no-fallback全部证明。 |
| V5 | Numerical non-interference | 8条C++ oracle、raw/prepared/objective/trajectory/L4/command按TS-17通过。 |
| V6 | Closed loop delta | HO/CS/OT/multiship不新增、不减少、不换码；Candidate4不宣称这些场景PASS。 |
| V7 | REST/WS/browser | reconnect/reset、active suffix、target alignment、straightness/provenance、Planner/Evaluator分栏、rejected toggle可验证。 |
| V8 | Compatibility | VO/Fan/Nominal无Evidence仍Trace1.0，行为、JSON和GUI回归通过；Mid为1.1。 |
| V9 | Performance | 同环境每case 1000次，0/1/16目标及fresh/hold/rejected测combined critical tail p50/p95/p99/max；review后重算reservation，总deadline不变。 |
| V10 | Live 8010 | 确认listener PID/cwd；真实Mid planner event含solver执行、IPOPT状态、Receipt、evidence/replay；非HTTP-only。 |
| V11 | Full regression | 新增测试全绿；全套结果按`b958512` delta报告；现有7失败不隐藏。 |

### Claim边界

- 可声明: Evidence结构完整性、semantic/numerical replay等级、真实IPOPT来源、L4结论、Receipt/command时间线、artifact持久化状态。
- 不可声明: source authenticity、签名/attestation、跨平台IPOPT bit-exact、全Playground场景PASS、MASS-L3系统验收、capability升级。
- Candidate4完成不等于解决直线轨迹或COLREG行为缺陷；它负责让真实求解、预测、L4拒绝及执行状态可观察、可归因、可复现。

## 8. 已知冲突与未闭环盲区

| 类型 | 状态 | 处理边界 |
|---|---|---|
| 现有7项严格L4闭环失败 | 已知冲突，非Candidate4缺陷 | 保持4项swept-clearance、3项stand-on-drift failure family；后续算法/L4专票处理。 |
| 当前hold线性插值与OCP interval reference不同 | 已裁决语义差异 | 两者分别记录；Candidate4不改为ZOH。 |
| L3 selected与L4 all-relevant预测coverage不同 | 已裁决语义差异 | 按purpose分别记录并reconcile，不强制共享对象。 |
| 250ms reservation是否足够 | 实施校准门，不是未定设计 | V9实测combined tail后确定；不得提高20s。 |
| 来源真实性/签名 | 明确out-of-scope | V1仅integrity/replay；未来外层attestation引用evidence hash。 |
| legacy Trace1.0删除时间 | 明确不在本候选 | Candidate4仅additive 1.1；任何删除另开2.0迁移。 |

未闭环研究盲区: 无。实施期若发现技术规约不可实现或新证据与VR冲突，暂停并回炉受影响DP。

## 参考文献

R1-R36完整书目、版本、路径及置信度见权威设计日志`0.4 [EV]`与“参考文献”章节。方案包引用保持相同编号，不复制漂移副本。
