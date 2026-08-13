# 设计日志: Mid-MPC LX/L5 Prediction Evidence

> **模式**: 重构        **创建**: 2026-08-13
> **关联 spec**: `docs/superpowers/specs/2026-08-13-mid-mpc-lx-l5-prediction-evidence-spec.md`; GitHub #27
> **状态**: 已交付 to-spec

## 0. 决策树状态(权威索引 · 可变快照)

### 0.1 决策点注册表 [DP]

| ID | 描述 | 类型 | 父/分解 | 状态 | 详见 |
|----|------|------|---------|------|------|
| DP-01 | Prediction Evidence采用何种深模块边界与技术模型，使一次规划活动、其派生证据及消费方可独立演进 | 技术 | TD-01 | Step4已确认 | VR-01 |
| DP-02 | 模块位于L4结果/Receipt、Adapter原子提交、持久化、API与GUI之间的准确ownership seam | 架构 | TD-01 | Step4已确认 | VR-04 |
| DP-03 | attempt、solve、candidate、acceptance、receipt、dispatch、hold之间的身份与因果谱系 | 接口 | TD-01 | Step4已确认 | VR-09 |
| DP-04 | latest attempt、latest solve、active accepted plan、previous plan、applied command的时间线和单一权威 | 架构 | TD-01 | Step4已确认 | VR-05 |
| DP-05 | 本船81个state knots、80个control intervals及实测首点/优化点/执行点的typed trajectory语义 | 接口 | TD-01 | Step4已确认 | VR-10 |
| DP-06 | 目标预测的TrackKey、generation、模型、参考时刻、健康度、不确定性及selected/relevant/displayed语义 | 接口 | TD-01 | Step4已确认 | VR-11 |
| DP-07 | L4 typed layers/findings/witnesses、Acceptance Certificate与Accepted Plan Receipt如何投影，且不在LX重复判定 | 架构 | TD-01 | Step4已确认 | VR-06 |
| DP-08 | fresh、hold revalidation、rejected attempt、failure、reset时证据与active authority的状态转换 | 约束 | TD-01 | Step4已确认 | VR-13 |
| DP-09 | schema版本、有限数值、canonical encoding、hash边界、兼容与迁移策略 | 技术 | TD-01 | Step4已确认 | VR-02 |
| DP-10 | canonical full artifact、受限inline projection、artifact reference及异步持久化状态的关系 | 架构 | TD-01 | Step4已确认 | VR-07 |
| DP-11 | replay/verifier能够复算或验证哪些链路，哪些只允许做完整性验证 | 技术 | TD-01 | Step4已确认 | VR-03 |
| DP-12 | GUI/API只消费哪份render projection，怎样解释直线、时间网格、active/latest、目标轨迹及L4证据 | 接口 | TD-01 | Step4已确认 | VR-12 |
| DP-13 | evidence构建、hash、投影与持久化的实时预算、容量、背压和降级边界 | 约束 | TD-01 | Step4已确认 | VR-14 |
| DP-14 | 深模块仅服务Mid-MPC，还是演进通用PlannerTrace；其他算法如何保持兼容且不被迫迁移 | 架构 | TD-01 | Step4已确认 | VR-08 |
| DP-15 | pure contract、mutation、replay、adapter事务、API/GUI、闭环、8010与全回归的验收门 | 约束 | TD-01 | Step4已确认 | VR-15 |

### 0.2 技术分解注册表 [TD]

| ID | 技术 | 分解子模块(→DP) | 触发步骤 |
|----|------|------------------|----------|
| TD-01 | Typed Prediction Evidence与provenance/replay pipeline | ownership seam(DP-02); identity/lineage(DP-03); authority timeline(DP-04); ownship trajectory(DP-05); target prediction(DP-06); L4/receipt projection(DP-07); lifecycle transitions(DP-08); schema/canonicalization(DP-09); artifact/inline persistence(DP-10); replay verifier(DP-11); render projection(DP-12); realtime/backpressure(DP-13); planner compatibility(DP-14); verification gates(DP-15) | Step1 |

### 0.3 盲区注册表 [BL]

| ID | 问题 | 归属决策点 | 优先级 | 调研状态 |
|----|------|-----------|--------|----------|
| BL-01 | canonical record只含稳定语义证据，还是连dispatch、hold及artifact完成状态也纳入同一不可变记录 | DP-01 | 高 | 已闭环→[R13][R15][R16][R9] |
| BL-02 | Adapter通过何种最小typed seam接收Mid-MPC evidence，同时不把Mid专属schema扩散至所有算法 | DP-02 | 高 | 已闭环→[R17] |
| BL-03 | 发生ID采用随机UUID还是`run_id + 类型 + 单调序号`；reset/session恢复后的序号authority由谁保存 | DP-03 | 高 | 已闭环→[R14][R17] |
| BL-04 | 最终rejection后GUI保留并淡化最后committed历史轨迹，还是完全移除轨迹 | DP-04 | 高 | 已闭环→[R16][R18][R17] |
| BL-05 | 航向/航速在knot边界采用左连续还是右连续表达，及其对hold采样、L4对齐和GUI光标的影响 | DP-05 | 高 | 已闭环→[R19][R20] |
| BL-06 | L3 Assembler prediction与L4 Execution prediction强制共用同一对象/hash，还是允许按purpose分别存在并显式记录差异 | DP-06 | 高 | 已闭环→[R21][R6][R11] |
| BL-07 | 8192-byte inline投影的确定性优先级与截断规则，如何保证关键失败和最差安全witness不丢失 | DP-07 | 高 | 已闭环→[R22][R23][R9] |
| BL-08 | evidence从Adapter调用入口还是从有效PlannerInput/candidate开始捕获；早期失败可见性与实时/存储开销如何平衡 | DP-08 | 高 | 已闭环→[R24][R14][R28] |
| BL-09 | 冻结Python浮点编码和schema迁移，同时保持既有Request→Receipt hashes不变并为未来跨语言verifier留出口 | DP-09 | 高 | 已闭环→[R25][R26][R4] |
| BL-10 | worker完成结果如何返回runtime timeline，同时不共享可变dict、不从worker线程直接修改Adapter状态 | DP-10 | 高 | 已闭环→[R27][R15][R28] |
| BL-11 | V1是否需要数字签名/可信密钥证明artifact来源；现有hash链只证明完整性和内部一致性 | DP-11 | 中 | 已闭环→[R29][R30][R26] |
| BL-12 | 默认地图显示active suffix、完整accepted plan、previous/historical及rejected candidate中的哪些组合 | DP-12 | 高 | 已闭环→[R31][R18][R7] |
| BL-13 | 新增Evidence synchronous tail在0/1/16目标下的p99，及现有0.25s solver reservation是否仍足够 | DP-13 | 高 | 已闭环·数值留实施校准门→[R32][R9] |
| BL-14 | 新增字段后PlannerTrace采用1.1、2.0还是保持1.0；legacy字段保留周期及旧client兼容证明 | DP-14 | 高 | 已闭环→[R33][R34][R17] |
| BL-15 | 实施前冻结哪些HO/CS/OT/multiship runtime基线，以及哪些字段exact、哪些按量纲容差比较 | DP-15 | 高 | 已闭环→[R35][R36][R30] |
| BL-16 | 当前hold执行对`control_trajectory`做线性插值，而OCP区间参考值按每段`psi[k],u[k]`积分；是否改变为右连续/ZOH属于执行行为变更还是Evidence范围 | DP-05 | 高 | 已闭环·Candidate4保持现状→[R19][R20] |
| BL-17 | `b958512`严格L4合并后7个HO/CS/OT/multiship闭环测试全部fail；Candidate 4应保持失败基线还是扩展为算法/L4行为修复 | DP-15 | 高 | 已闭环·Candidate4不修复→[R36] |

### 0.4 证据矩阵 [EV]

| ID | 来源类型 | 引用 | 检索置信 | 来源权威 | 场景适用 | 归属 |
|----|----------|------|----------|----------|----------|------|
| [R1] | DOMAIN_EVIDENCE | W3C PROV-DM: entity/activity/derivation/bundle与有效provenance约束 | 高 | 高 | 中 | DP-01, DP-03, DP-09, DP-11 |
| [R2] | DOMAIN_EVIDENCE | OpenTelemetry Trace API/Signals: trace DAG、causal link、immutable event、signal分离 | 高 | 高 | 中 | DP-03, DP-04, DP-13 |
| [R3] | DOMAIN_EVIDENCE | CNCF CloudEvents 1.0.2: source+id唯一、type、time、schema及事件大小边界 | 高 | 高 | 中 | DP-03, DP-04, DP-09, DP-10 |
| [R4] | DOMAIN_EVIDENCE | RFC 8785 JCS:可重复hash所需的JSON canonical representation | 高 | 高 | 中 | DP-09, DP-11 |
| [R5] | PROJECT_FACT | `diagnostics.py`与`custom_mpc_adapter.py` @ `b958512`: PlannerTrace自由字典、fresh/hold/failure写入路径、post-commit证据回填 | 高 | 高 | 高 | DP-02, DP-04, DP-08, DP-10, DP-14 |
| [R6] | PROJECT_FACT | `mid_mpc_ipopt.py` @ `b958512`: Request→Problem→Prepared→Solver→Acceptance→Receipt链、typed L4输入输出、target prediction、render projection | 高 | 高 | 高 | DP-03, DP-05, DP-06, DP-07, DP-09, DP-10 |
| [R7] | PROJECT_FACT | `gui_server/main.py`与`web_gui/app.js` @ `b958512`: latest/active/previous缓存和直接折线/时间标签绘制 | 高 | 高 | 高 | DP-04, DP-12 |
| [R8] | PROJECT_FACT | `BoundedArtifactSink` @ `b958512`: item/byte容量、异步写入、保留和关闭drain | 高 | 高 | 高 | DP-10, DP-13 |
| [R9] | DOCUMENTED_INTENT | Candidate 1 L4 design/implementation @ `b958512`: canonical semantic record、active/latest分离、fail-stop、bounded evidence | 高 | 高 | 高 | DP-02, DP-04, DP-07, DP-08, DP-10, DP-13 |
| [R10] | DOCUMENTED_INTENT | Candidate 2 Lifecycle @ `b94148c`: TrackKey、role/side/commitment/release唯一authority | 高 | 高 | 高 | DP-06, DP-07, DP-08 |
| [R11] | DOCUMENTED_INTENT | Candidate 3 Assembler @ `1f459d8`: lifecycle→assembly→solver→acceptance hash chain与typed ENU render projection | 高 | 高 | 高 | DP-03, DP-05, DP-06, DP-09, DP-11 |
| [R12] | DOCUMENTED_INTENT | 用户提供七层架构: LX X1-X5可观测/归因/复现，L5 route/output/handover/fallback/execution feedback | 高 | 中 | 中 | DP-01, DP-02, DP-11, DP-12, DP-15 |
| [R13] | DOMAIN_EVIDENCE | W3C PROV-DM: entity/activity、generation/invalidation、derivation及bundle分离 | 高 | 高 | 中 | DP-01, DP-03, DP-04 |
| [R14] | DOMAIN_EVIDENCE | CloudEvents 1.0.2: `source+id`唯一；counter或UUID均可；同ID重送可作为duplicate | 高 | 高 | 中 | DP-03, DP-08 |
| [R15] | DOMAIN_EVIDENCE | OpenTelemetry Trace API: event/link immutable；parent/link表达因果；completed span不再修改 | 高 | 高 | 中 | DP-01, DP-03, DP-04, DP-10 |
| [R16] | DOMAIN_EVIDENCE | Azure Event Sourcing: append-only immutable events、materialized read views；同时警告全量event sourcing复杂且不应泛化 | 高 | 中 | 中 | DP-01, DP-04, DP-12 |
| [R17] | PROJECT_FACT | CodeGraph @ `b958512`: MPCSolution仅7处调用而PlannerTrace有20处；Adapter拥有commit/hold/failure/reset；GUI另行缓存active/latest；run_id为UUID且Web reset创建新run | 高 | 高 | 高 | DP-02, DP-03, DP-04, DP-14 |
| [R18] | DOMAIN_EVIDENCE | W3C WCAG status messages: success/result/progress/error状态变化必须程序可判定并呈现 | 高 | 高 | 中 | DP-04, DP-12 |
| [R19] | DOMAIN_EVIDENCE | CasADi官方OCP示例: N个control intervals、N+1个边界state，区间k满足`x[k+1]=F(x[k],u[k])` | 高 | 高 | 高 | DP-05 |
| [R20] | PROJECT_FACT | CodeGraph @ `b958512`: Mid原始80组`psi/u`积分为81个公共state knots；Adapter hold及L4 held candidate均按elapsed在线性插值，非ZOH | 高 | 高 | 高 | DP-05, DP-08, DP-12, DP-15 |
| [R21] | PROJECT_FACT | CodeGraph @ `b958512`: L3只预测NLP selected targets；L4独立按全部PlannerInput tracks重建CV预测，模型/网格当前一致但coverage不同 | 高 | 高 | 高 | DP-06, DP-07, DP-11 |
| [R22] | DOMAIN_EVIDENCE | CloudEvents 1.0.2: event应紧凑并链接大对象；OpenTelemetry: 有界集合防内存耗尽、截断/丢弃规则必须明确 | 高 | 高 | 中 | DP-07, DP-10, DP-13 |
| [R23] | PROJECT_FACT | CodeGraph @ `b958512`: 当前8192-byte投影首次超限会原位移除全部mandatory failure witness与primary safety witness，再超限则抛错 | 高 | 高 | 高 | DP-07, DP-10, DP-15 |
| [R24] | PROJECT_FACT | CodeGraph @ `b958512`: Adapter在`_planner_input`/schedule之后才进入solve异常捕获；failure复用旧solve_id，且hold-before-first异常无terminal trace | 高 | 高 | 高 | DP-08, DP-15 |
| [R25] | PROJECT_FACT | CodeGraph @ `b958512`: Request→Receipt各stage使用Python `json.dumps(sort_keys=True,separators,allow_nan=False)`和各自schema；尚无顶层Evidence canonicalizer/version dispatcher | 高 | 高 | 高 | DP-09, DP-11 |
| [R26] | DOMAIN_EVIDENCE | RFC 8785:可靠hash需固定primitive serialization、递归property sorting、UTF-8与I-JSON；Python现有编码不能仅凭`sort_keys`宣称JCS | 高 | 高 | 高 | DP-09, DP-11 |
| [R27] | PROJECT_FACT | CodeGraph @ `b958512`: BoundedArtifactSink将返回的reference dict与payload一起入队，worker线程原位改写COMPLETE/INCOMPLETE；无immutable completion channel | 高 | 高 | 高 | DP-10, DP-13, DP-15 |
| [R28] | DOMAIN_EVIDENCE | W3C PROV-CONSTRAINTS: provenance validity依赖generation/use/invalidation及activity start/end的相对事件次序，可不依赖全局物理时钟 | 高 | 高 | 中 | DP-08, DP-10, DP-11 |
| [R29] | DOMAIN_EVIDENCE | NIST FIPS 186-5: digital signature提供未授权修改检测与signatory身份认证；SLSA把可信builder/signer及attestation作为更高层trust claim | 高 | 高 | 中 | DP-11 |
| [R30] | PROJECT_FACT | CodeGraph @ `b958512`: 现有run replay只比episode/trajectory hash；parity/L4/artifact测试分散存在，尚无public V0-V7 Prediction Evidence verifier | 高 | 高 | 高 | DP-11, DP-15 |
| [R31] | PROJECT_FACT | CodeGraph @ `b958512`: GUI server自行维护current/previous/latest/active缓存，hold沿用完整trajectory；render projection存在但尚非唯一timeline snapshot | 高 | 高 | 高 | DP-12, DP-14 |
| [R32] | PROJECT_FACT | 2026-08-12固定M3环境1000次full-L4 benchmark: 16目标p99=35.046ms、max=123.557ms，现有reservation=250ms；未覆盖Candidate4同步tail | 高 | 高 | 高 | DP-13, DP-15 |
| [R33] | PROJECT_FACT | CodeGraph及既有项目规约: PlannerTrace消费者不拒绝未知字段；outer 1.x允许additive minor，breaking才升major；MPCSolution仅7处调用 | 高 | 高 | 高 | DP-14, DP-15 |
| [R34] | DOMAIN_EVIDENCE | SLSA Provenance v1 parsing: major标识breaking，minor必须backward-compatible/monotonic，consumer忽略未知字段 | 高 | 高 | 中 | DP-14 |
| [R35] | TEST_EVIDENCE | `b958512`当前focused parity/core/assembler/L4/integration/artifact suite: 90 passed in 93.10s | 高 | 高 | 高 | DP-15 |
| [R36] | TEST_EVIDENCE | `b958512`当前single-encounter+multiship闭环: 7 failed in 171.03s；4项`SAFETY_SWEPT_CLEARANCE`、3项`COLREG_STAND_ON_DRIFT` | 高 | 高 | 高 | DP-12, DP-15 |

### 0.5 场景注册表 [SC]

| ID | 场景描述 | 约束/边界 | 驱动决策点 |
|----|----------|-----------|-----------|
| SC-01 | fresh IPOPT通过L4并提交，artifact随后异步完成，中间经历多个hold tick | GUI始终区分candidate、active accepted plan、当前执行点及artifact状态；异步状态不得改写语义verdict | DP-01, DP-03, DP-04, DP-08, DP-10, DP-12 |
| SC-02 | L4 PASS但Adapter最终总deadline检查失败 | latest attempt保留candidate/L4证据；active plan为空；receipt未生效；无command、无fallback | DP-02, DP-03, DP-04, DP-07, DP-08 |
| SC-03 | 相同输入、配置和solver结果被重放两次 | semantic hashes相同；run/attempt/event发生身份不同；两次均可独立审计 | DP-03, DP-09, DP-11 |
| SC-04 | Plan A已commit，下一次Plan B真实求解但L4拒绝 | latest attempt/solve为B；active为空；A仅可作为明确不可执行的历史计划显示 | DP-04, DP-07, DP-08, DP-12 |
| SC-05 | 首个IPOPT决策`psi[0],u[0]`作用于`[0,15s)`并生成`t=15s`位置knot | GUI显示0..1200s；执行器采样interval 0；不得把首决策误标为15s后才开始 | DP-05, DP-08, DP-12 |
| SC-06 | 三个usable tracks中两个进入NLP，一个远期HOLD目标未进入graph | 第三个目标仍显示identity/Lifecycle/admission/exclusion及L4 relevance，不得静默消失 | DP-06, DP-07, DP-12 |
| SC-07 | 16目标产生大量L4 findings，inline projection超过8192 bytes | mandatory failure codes、owner、target key、最差安全数值及artifact引用不得因截断丢失或误显示PASS | DP-07, DP-10, DP-12, DP-13 |
| SC-08 | Plan A active；hold因target generation变化失效；一次same-algorithm replan B的solver失败 | active/receipt/warm清空，Session fail-stop，无fallback；完整事件链可见 | DP-08, DP-10, DP-12, DP-15 |
| SC-09 | 代码升级后读取旧Prediction Evidence artifact | 按artifact声明的canonicalizer验证原hash；不支持时明确UNSUPPORTED_SCHEMA，不按新规则假重算 | DP-09, DP-11, DP-12 |
| SC-10 | Plan已commit执行，但artifact queue达到byte capacity | control authority保持；inline显示BACKPRESSURE；evidence/capability claim不完整；semantic verdict不变 | DP-10, DP-13, DP-15 |
| SC-11 | 旧artifact在不同IPOPT patch版本环境验证 | 结构/hash/L4重算确定通过；可选re-solve允许容差差异，不改写原verdict | DP-09, DP-11, DP-15 |
| SC-12 | Plan A在`t=180s`求解，当前`t=200s`处于hold | active suffix从elapsed 20s插值点开始；execution marker位于20s而非固定15s knot；full 81点仍可审计 | DP-05, DP-08, DP-12 |
| SC-13 | 16目标、IPOPT接近cutoff且artifact disk故意变慢 | semantic hash/inline/freshness/commit仍在20s内；disk不阻塞；同步tail超时则无command | DP-10, DP-13, DP-15 |
| SC-14 | 同版本分别运行VO、Fan-MPC、Nominal与Mid-MPC | 前三者行为/trace/GUI不变；Mid使用typed evidence；通用Adapter无Mid专属字段访问 | DP-02, DP-14, DP-15 |
| SC-15 | 真实OT Playground运行覆盖首轮IPOPT、hold/replan、右舷超越、active suffix、L4/receipt、artifact及replay | 执行command与改造前基线一致；最终main真实8010可观察；不以GUI可见性提升capability | DP-05, DP-07, DP-08, DP-10, DP-11, DP-12, DP-15 |
| SC-16 | fresh plan后在elapsed=7.5s进入hold，OCP interval 0参考值与当前Adapter插值命令不同 | Evidence同时标明`optimization_interval_reference`与`runtime_applied_reference_policy=LINEAR_INTERPOLATION`；Candidate 4不改变下发command | DP-05, DP-08, DP-12, DP-15 |
| SC-17 | 在`b958512`运行HO/CS/OT/multiship严格L4闭环 | Candidate4必须如实呈现4个swept-clearance与3个stand-on-drift rejection；不得通过Evidence重构放宽L4或伪造PASS | DP-07, DP-12, DP-15 |

### 0.6 裁决注册表 [VR]

| ID | 裁决对象 | 结论 | 采纳/弃用 | 理由 | 时间 |
|----|----------|------|-----------|------|------|
| VR-01 | DP-01 Prediction Evidence模型 | Mid专属immutable semantic record + append-only occurrence events + pure reducer/projections；不重判Lifecycle/L4 | 采纳(Step4 final) | PROV/OTel及项目authority边界一致；控制blast且支持typed replay | 2026-08-13 |
| VR-02 | DP-09 schema/canonical hash | 冻结六级hash；新增versioned Evidence schema/canonicalizer/top hash；旧artifact原规则验证，升级生成derived record | 采纳(Step4 final) | 兼容既有证据并避免虚假JCS声明 | 2026-08-13 |
| VR-03 | DP-11 verifier/replay | Public V0-V6 deterministic verifier；V7 IPOPT re-solve仅diagnostic；V1无签名且claim限定integrity/replay | 采纳(Step4 final) | 区分结构、语义、数值及来源真实性，避免bit-exact和key scope | 2026-08-13 |
| VR-04 | DP-02 ownership | Facade产semantic candidate/certificate；Adapter唯一产receipt及runtime events；sink/API/GUI只消费 | 采纳(Step4 final) | 与L4、deadline及commit authority边界一致 | 2026-08-13 |
| VR-05 | DP-04 timeline | per-run/epoch events经deterministic reducer生成唯一latest/active/history/command/failure snapshot | 采纳(Step4 final) | 消除GUI缓存authority与last-trace歧义 | 2026-08-13 |
| VR-06 | DP-07 Certificate/Receipt | Full Certificate、post-commit Receipt、deterministic Inline及Render分层；Planner/Evaluator分栏 | 采纳(Step4 final) | 保留L4语义和commit事实，满足bounded payload | 2026-08-13 |
| VR-07 | DP-10 artifact lifecycle | immutable descriptor + status events；worker completion queue由simulation/runner线程归约 | 采纳(Step4 final) | 消除共享mutation并保持I/O异步有界 | 2026-08-13 |
| VR-08 | DP-14 compatibility | optional generic EvidenceEnvelope；Mid PlannerTrace1.1，其他算法1.0；legacy保留 | 采纳(Step4 final) | 最小blast、additive兼容 | 2026-08-13 |
| VR-09 | DP-03 identity/lineage | occurrence identity=`run_id+epoch+event_seq`；semantic content独立hash；caused_by/derived_from连接 | 采纳(Step4 final) | 同时满足发生唯一、局部顺序和内容去重 | 2026-08-13 |
| VR-10 | DP-05 ownship trajectory | 81 typed state knots + 80 optimization interval references + 独立runtime linear-interpolation reference；9x81仅兼容投影 | 采纳(Step4 final) | 保持OCP/运行语义及non-interference | 2026-08-13 |
| VR-11 | DP-06 target evidence | TrackKey绑定observation/lifecycle/admission/purpose predictions；NLP selected与L4 all-relevant独立并reconcile | 采纳(Step4 final) | 防ID复用、目标遗漏及自评耦合 | 2026-08-13 |
| VR-12 | DP-12 render/API | reducer唯一生成typed render snapshot；GUI只坐标/样式投影，不推断authority或重判 | 采纳(Step4 final) | 消除stale cache与Planner/Evaluator混淆 | 2026-08-13 |
| VR-13 | DP-08 lifecycle events | Adapter入口至terminal outcome全路径typed events；每cycle一个terminal control outcome；fail-stop清active，artifact failure仅降claim | 采纳(Step4 final) | 覆盖早期失败并保持控制/证据authority分离 | 2026-08-13 |
| VR-14 | DP-13 realtime | 20s不变；critical evidence同步、I/O异步有界；combined-tail重测并重校准reservation | 采纳(Step4 final) | 不猜预算、不用扩大deadline掩盖开销 | 2026-08-13 |
| VR-15 | DP-15 verification | V1..V11；冻结b958512的90-pass与7-fail delta基线；不修复/放宽L4、不提升claim | 采纳(Step4 final) | 符合Candidate4 non-interference与当前真实状态 | 2026-08-13 |
| VR-16 | S5-A 领域与权威架构 | 采用有界Mid深Evidence模块；semantic record、runtime events、pure reducer分离；RenderSnapshot仅为机械投影 | 采纳(Step5 final) | 完整支持因果重放与异步状态，同时不迁移控制authority或其他算法 | 2026-08-13 |
| VR-17 | S5-B 预测契约与展示 | 采用typed语义轨迹图并机械派生RenderSnapshot；tensor只作内部计算格式，artifact只作full transport | 采纳(Step5 final) | 直接表达80/81网格、runtime插值、TrackKey/purpose和L3/L4预测边界 | 2026-08-13 |
| VR-18 | S5-C 完整性、持久化与实时验证 | 同步完整性内核与receipt/command原子提交；full artifact异步有界持久化；V0-V6 public verifier，V7 diagnostic | 采纳(Step5 final) | 不让磁盘决定控制可用性，同时保留明确完整性、回放和性能边界 | 2026-08-13 |

### 0.7 备选/弃用方案 [ALT]

| ID | 方案 | 弃用理由 | 对比于 |
|----|------|----------|--------|
| ALT-01 | 单一巨大可变Evidence JSON或继续扩充自由`algorithm_details` | hash/时态漂移，无法typed replay | VR-01 |
| ALT-02 | 全项目通用event-sourcing平台 | blast过大，迫使其他算法迁移 | VR-01 |
| ALT-03 | 直接把既有hash切换为JCS或按新schema重写旧artifact | 破坏历史hash；当前编码非完整JCS | VR-02 |
| ALT-04 | verifier只验SHA或要求IPOPT bit-exact | 前者无语义/因果证明，后者跨平台假失败 | VR-03 |
| ALT-05 | V1加入数字签名、可信密钥及attestation | 超出本地验证范围；key lifecycle未定义 | VR-03 |
| ALT-06 | Facade提前声明receipt、Adapter读取Mid专属schema或GUI推断authority | ownership错误，多事实源 | VR-04 |
| ALT-07 | 单一last trace或GUI私有active/latest缓存 | rejection/reset/reconnect时产生stale authority | VR-05 |
| ALT-08 | Acceptance bool或Certificate与Receipt合并 | 丢witness并混淆L4 PASS与真实commit | VR-06 |
| ALT-09 | worker原位修改共享artifact dict或同步持久化 | 竞态/hash漂移或挤占deadline | VR-07 |
| ALT-10 | 全局PlannerTrace2.0、Adapter algorithm分支、强迫其他算法迁移 | breaking且范围过大 | VR-08 |
| ALT-11 | 全UUID、全content-hash或仅legacy solve_id标识所有发生 | 缺局部顺序、发生碰撞或覆盖pre-solver事件 | VR-09 |
| ALT-12 | 把81列都当control、只存NE折线或Candidate4改ZOH | 时域错位、不可追溯或改变command | VR-10 |
| ALT-13 | 仅selected ids、无generation或强制L3/L4共享预测对象 | 静默漏目标、ID串线或破坏独立复核 | VR-11 |
| ALT-14 | GUI解释raw trace/缓存authority/重算COLREG与安全 | stale状态、schema耦合及自证循环 | VR-12 |
| ALT-15 | 从candidate才记录或用单一status覆写完整cycle | 早期失败不可见且因果链丢失 | VR-13 |
| ALT-16 | 全同步I/O、全异步commit或无界queue/history | deadline、authority或资源边界失控 | VR-14 |
| ALT-17 | 未重测Candidate4 tail即沿用250ms或提高20s总门 | 无性能证据或掩盖开销 | VR-14 |
| ALT-18 | 要求Candidate4修复7场景、改xfail/降L4或用HTTP200代替执行证据 | 越scope、隐藏缺陷或证据不足 | VR-15 |
| ALT-19 | 每周期不可变全量Snapshot作为canonical evidence | 因果、异步完成与exactly-one terminal仍需隐式推断；仅保留为机械render投影 | VR-16 |
| ALT-20 | 全项目通用Event-Sourced Planner平台 | Candidate4收益不足以承担全算法、API、GUI和saved-run迁移 | VR-16 |
| ALT-21 | 统一稠密Prediction Tensor作为canonical schema | 异构grid/purpose/admission/generation依赖易错位side tables；仅可作内部计算优化 | VR-17 |
| ALT-22 | Artifact-first，由API/GUI懒加载并解释实时轨迹 | async/backpressure时无实时证据且客户端会形成第二authority；仅保留full transport | VR-17 |
| ALT-23 | command前同步完成full artifact压缩、fsync、rename及复验 | 磁盘tail与故障变成控制可用性前置条件 | VR-18 |
| ALT-24 | command-first后再best-effort构造receipt/hash/timeline | crash窗口可产生已执行但无权威证据，无法满足lineage/replay目标 | VR-18 |

### 0.8 技术规约注册表 [TS]

| ID | 类别 | 规约内容 | 单位/定义 | 来源 | 关联DP/接口 | 与现状差异 |
|----|------|----------|-----------|------|-------------|-----------|
| TS-01 | 坐标系 | frame=`ENU`；权威字段为`north_m/east_m`，禁止依赖含糊`x/y` | 水平当地坐标；数组`[north,east]` | [R6][R20] | DP-05/06/12；Input/Evidence/Render | `x/y`只作legacy alias |
| TS-02 | 坐标系 | ownship 6-state布局 | `[north,east,heading,surge,sway,yaw_rate]` | [R6][R17] | DP-05；PlannerInput | Evidence显式命名，不改布局 |
| TS-03 | 坐标系 | target state/covariance布局 | `[north,east,v_north,v_east]`，covariance同序 | [R17][R21] | DP-06；TrackPrediction | 新增purpose/reference元数据 |
| TS-04 | 单位 | 位置/距离、速度、加速度SI | `m`,`m/s`,`m/s^2` | [R6][R17] | DP-05/06/12 | 字段名必须带单位 |
| TS-05 | 单位 | sim/reference/grid时间为秒，性能时长为毫秒 | `s`,`ms` | [R6][R32] | DP-03/05/13 | 禁止无后缀duration |
| TS-06 | 单位 | canonical角度/角速度为rad/rad/s；deg仅UI派生 | `rad`,`rad/s`,`deg(display)` | [R6][R17] | DP-05/12 | UI deg不得回写canonical |
| TS-07 | 符号 | heading 0指北、顺时针为正；body x前/y右舷 | `vN=u cosψ-v sinψ`,`vE=u sinψ+v cosψ` | [R6] | DP-05/06 | Evidence显式固化现状 |
| TS-08 | 符号 | passing side公开接口用typed enum | optimizer内部可兼容`{-1,0,1}` | VR-11/17 | DP-06/12 | 不向Evidence泄漏裸整数 |
| TS-09 | 时序 | OCP网格固定80 intervals/81 knots/15s/1200s | `t_k=k*15s`,`k=0..80` | [R19][R20] | DP-05；PredictionGrid | 替代旧UI 90s含糊展示 |
| TS-10 | 时序 | interval k作用`[t_k,t_{k+1})`并生成knot k+1 | 80 refs对81 states；terminal无control | [R19] | DP-05；OwnshipTrajectory | 显式解决off-by-one |
| TS-11 | 时序 | runtime hold保持线性插值 | `LINEAR_INTERPOLATION`+`elapsed_s` | [R20], VR-10 | DP-05/08/12 | Candidate4不改ZOH |
| TS-12 | 时序 | occurrence ordering=`run_id+epoch+event_seq` | epoch内sequence严格递增 | [R14][R28], VR-09 | DP-03/08/11 | 新增唯一ordering authority |
| TS-13 | 时序 | 每cycle恰一个terminal control outcome | COMMITTED/HELD/REJECTED/FAILED | VR-13 | DP-08；Adapter/Reducer | 补齐早期失败 |
| TS-14 | 数值 | canonical仅finite；使用`colav.python-json@1` | NaN/Inf拒绝；negative-zero规则固定；非JCS | [R25][R26] | DP-09/11 | 新增顶层canonicalizer |
| TS-15 | 数值 | solver目标及inline有界 | targets<=16；inline<=8192 UTF-8 bytes | [R22][R23] | DP-06/07/10/13 | 新增tier/capacity failure |
| TS-16 | 数值 | total deadline 20s不变；Evidence同步tail计入 | 250ms须实测，不是新常量 | [R9][R32], VR-14/18 | DP-13/15 | combined-tail重校准 |
| TS-17 | 数值 | non-interference容差冻结 | objective abs1e-5；trajectory/raw abs1e-6；CPA scale-aware；离散/hash/command exact | [R30][R35] | DP-11/15 | Evidence不得改变基线 |
| TS-18 | 数值 | arrays/mappings深不可变；worker不回填共享对象 | copy+readonly；completion为新value | [R17][R27], VR-07 | DP-01/10 | 修复共享dict mutation |
| TS-19 | 接口 | optional generic`MPCSolution.evidence` | Mid Trace1.1；其他算法1.0 | [R17][R33][R34], VR-08 | DP-02/14 | additive，legacy全保留 |
| TS-20 | 接口 | Facade产candidate/Certificate；Adapter产Receipt/runtime events | sink/API/GUI仅消费 | VR-04/16 | DP-02/04/08 | 消除多事实源 |
| TS-21 | 接口 | semantic hash与OccurrenceId分离 | SHA-256 content hash；`derived_from/caused_by` | [R13][R14], VR-09 | DP-03/09/11 | 不复用solve_id |
| TS-22 | 接口 | TrackKey+purpose prediction显式 | `(target_id,generation)`；NLP selected/L4 all-relevant | [R10][R21], VR-11/17 | DP-06 | 未进NLP目标不消失 |
| TS-23 | 接口 | Certificate、Receipt、artifact status互不替代 | L4 PASS!=commit；artifact status不改verdict | VR-06/07/18 | DP-07/10/13 | 拆分混合状态 |
| TS-24 | 接口 | inline截断顺序固定 | Tier0身份/verdict；Tier1 mandatory；Tier2 worst；advisory先删 | [R22][R23], VR-06 | DP-07/10/12 | 不再丢全部关键witness |
| TS-25 | 接口 | public verifier V0-V6；V7 diagnostic | bytes/schema/lineage/numerical/L4/projection/authority/re-solve | VR-03/18 | DP-11/15 | 不声明authenticity |
| TS-26 | 接口 | RenderSnapshot为新GUI唯一Evidence authority | active teal；invalid grey；rejected toggle red；Planner/Evaluator分栏 | [R18][R31], VR-12/17 | DP-04/12 | GUI不缓存authority |
| TS-27 | 接口 | artifact使用immutable completion channel | bounded queue；close drain/INCOMPLETE；worker不分配event_seq | [R15][R27], VR-07/18 | DP-10/13 | 替换共享reference回填 |

---

## 参考文献

- [R1] W3C. `PROV-DM: The PROV Data Model`. https://www.w3.org/2012/10/prov-dm
- [R2] OpenTelemetry. `Signals` and `Tracing API`. https://opentelemetry.io/docs/concepts/signals/ ; https://opentelemetry.io/docs/specs/otel/trace/api/
- [R3] CNCF CloudEvents. `CloudEvents Specification v1.0.2`. https://github.com/cloudevents/spec/blob/ce@v1.0.2/cloudevents/spec.md
- [R4] RFC Editor. `RFC 8785: JSON Canonicalization Scheme`. https://www.rfc-editor.org/rfc/rfc8785
- [R5] Colav-Simulator `b958512`: `colav_simulator/core/colav/diagnostics.py`; `colav_simulator/core/colav/custom_mpc_adapter.py`.
- [R6] Colav-Simulator `b958512`: `colav_simulator/integrations/mid_mpc_ipopt.py`; `colav_simulator/core/colav/mid_mpc/mid_mpc_acceptance.py`.
- [R7] Colav-Simulator `b958512`: `gui_server/main.py`; `web_gui/app.js`.
- [R8] Colav-Simulator `b958512`: `colav_simulator/experiment/persistence.py`.
- [R9] Colav-Simulator `b958512`: `docs/superpowers/specs/2026-08-12-mid-mpc-l4-plan-acceptance-design.md`.
- [R10] Colav-Simulator `b94148c`: `docs/superpowers/specs/2026-08-11-mid-mpc-l0-l1-encounter-lifecycle-solution-pack.md`.
- [R11] Colav-Simulator `1f459d8`: `docs/superpowers/specs/2026-08-11-mid-mpc-l1-l2-problem-assembler-solution-pack.md`.
- [R12] `/Users/marine/Desktop/MPC/M5_MPC_业务流程分层架构.md`, sections 7-8.
- [R13] W3C. `PROV-DM: The PROV Data Model`, entities/activities, generation/invalidation, derivation and bundles. https://www.w3.org/TR/prov-dm/
- [R14] CNCF CloudEvents. `CloudEvents Specification v1.0.2`, context attributes `id`, `source`, `type`, `time`. https://github.com/cloudevents/spec/blob/ce@v1.0.2/cloudevents/spec.md
- [R15] OpenTelemetry. `Tracing API`, Span/Event/Link and concurrency requirements. https://opentelemetry.io/docs/specs/otel/trace/api/
- [R16] Microsoft Azure Architecture Center. `Event Sourcing pattern`, append-only events, materialized views and complexity trade-offs. https://learn.microsoft.com/en-us/azure/architecture/patterns/event-sourcing
- [R17] CodeGraph audit of Colav-Simulator `b958512`: `MPCSolution`, `PlannerTrace`, `CustomMPCAdapter`, `WebSessionManager`, `RunManifest.create`.
- [R18] W3C WAI. `Understanding Success Criterion 4.1.3: Status Messages`. https://www.w3.org/WAI/WCAG21/Understanding/status-messages
- [R19] CasADi. `Optimal control problems in a nutshell`, multiple-shooting state/control grid. https://web.casadi.org/blog/ocp/
- [R20] CodeGraph audit of Colav-Simulator `b958512`: `MidMpcIpoptSolver._trajectory`, `_native_trajectories`, `CustomMPCAdapter._sample_trajectory`, `_trajectory_state_at`, `_held_acceptance_request`.
- [R21] CodeGraph audit of Colav-Simulator `b958512`: `TargetPrediction`, `MidMpcProblemAssembler`, `_acceptance_request`, `_execution_target`.
- [R22] CNCF CloudEvents. `CloudEvents Specification v1.0.2`, Size Limits; OpenTelemetry. `Common specification concepts`, Attribute Limits. https://github.com/cloudevents/spec/blob/ce@v1.0.2/cloudevents/spec.md ; https://opentelemetry.io/docs/specs/otel/common/
- [R23] CodeGraph audit of Colav-Simulator `b958512`: `_acceptance_inline_projection`.
- [R24] CodeGraph audit of Colav-Simulator `b958512`: `CustomMPCAdapter.plan`, `_execute_solve`, `_execute_hold`, `_record_execution_failure`.
- [R25] CodeGraph audit of Colav-Simulator `b958512`: Request/Problem/Prepared/Solver/Acceptance/Receipt hash functions and schema constants.
- [R26] RFC Editor. `RFC 8785: JSON Canonicalization Scheme`. https://www.rfc-editor.org/rfc/rfc8785
- [R27] CodeGraph audit of Colav-Simulator `b958512`: `BoundedArtifactSink.__call__`, `_run`, `close`.
- [R28] W3C. `Constraints of the PROV Data Model`, validity and event ordering. https://www.w3.org/TR/prov-constraints/
- [R29] NIST. `FIPS 186-5 Digital Signature Standard`; SLSA. `Provenance v1`. https://csrc.nist.gov/pubs/fips/186-5/final ; https://slsa.dev/spec/v1.0/provenance
- [R30] CodeGraph audit of Colav-Simulator `b958512`: Web replay, Mid-MPC parity, assembler/L4 and artifact tests.
- [R31] CodeGraph audit of Colav-Simulator `b958512`: `WebSessionManager._telemetry`, render projection and planner cache fields.
- [R32] Colav-Simulator `docs/superpowers/benchmarks/2026-08-12-mid-mpc-l4-acceptance-reservation.md`.
- [R33] CodeGraph audit of Colav-Simulator `b958512`; prior project schema evolution rule in Dynamic MPC Playground and Encounter Lifecycle design logs.
- [R34] SLSA. `Provenance v1`, parsing rules and monotonic extensions. https://slsa.dev/spec/v1.0/provenance
- [R35] Local pytest on `b958512`, 2026-08-13: focused six-file Mid-MPC suite.
- [R36] Local pytest on `b958512`, 2026-08-13: `test_mid_mpc_single_encounter.py` and `test_mid_mpc_multiship_runtime.py`; failure manifests independently inspected.

---

## 演进日志(append-only · 时序 · 不可覆盖)

### Step1 · 行业调研·发现决策点  [2026-08-13 09:08]

- 模式判定: **重构**。当前树已有L4 typed acceptance、六级hash链、受限inline projection、异步artifact sink、PlannerTrace、API缓存与GUI轨迹绘制；候选4应深化并收敛这些责任，不另造平行观测链。[R5][R6][R7][R8][R9]
- 上下文基线: Candidate 2 Lifecycle `b94148c`、Candidate 3 Assembler `1f459d8`、Candidate 1 L4 merge `b958512`。三者分别保持决策authority、问题装配authority、下发前acceptance authority。[R9][R10][R11]
- 快调来源: W3C PROV-DM、OpenTelemetry Trace API/Signals、CNCF CloudEvents、RFC 8785，加当前代码、三份已合并设计及用户七层架构。[R1]..[R12]
- 现状校正: 本船预测轨迹已来自真实IPOPT结果；目标预测已同时提供`north_m/east_m`及兼容`x/y`。候选4不再修复已不存在的字段缺陷，而解决“谁生成、何时有效、是否active、由何证据派生、如何重放和展示”。[R6][R7]
- 关键现状缺口: `PlannerTrace.algorithm_details`仍为自由字典；fresh solve先构造trace再由post-commit原位回填artifact；hold trace继续携带原始完整预测；GUI自行缓存latest/active/previous并按全局`horizon_dt_s`解释轨迹。[R5][R7]
- 边界发现: 用户七层文档的MASS-L3 L5含GNC handover、BC-MPC/MRM fallback；本项目既定边界是`PlannerInput -> MPCSolution`、no fallback、无M4/M6/M7。候选4的L5仅讨论“accepted plan输出证据、dispatch/hold/applied command关联”，不移植MASS平台链路。[R9][R12]
- 新增决策点: DP-01..DP-15。
- 触发技术分解: TD-01 → DP-02..DP-15。不得只决定“建立Prediction Evidence module”后直接实现。
- Step1门状态: 决策点非空；技术型父项DP-01已完整展开。待用户确认覆盖面后进入Step2逐DP三视角grilling。

### Step2 · grilling 压力测试  [2026-08-13 09:18]

- [grilling记录·三视角] DP-01:
  - [专家] 采用typed、immutable Prediction Evidence domain model；一次规划活动产生有身份、派生关系和版本的证据，artifact/inline/API/GUI只做机械投影。[R1][R2][R3]
  - [新手] 现有`algorithm_details`自由字典由fresh、hold、failure、post-commit和GUI分别解释/修改，不能保证求解、active、持久化及画面一致。[R5][R7]
  - [悲观] 做成通用日志平台会扩大范围；让Evidence重新判断安全/COLREG会侵占L4和Lifecycle authority。
  - [机制C默认最简版失效] 单个巨大JSON/dataclass会产生可变嵌套状态、重复事实、超大inline payload及GUI对solver内部schema的耦合。
  - 用户确认的方向: “不可变语义核心 + 追加式运行事件”作为后续调研假设；不引入OpenTelemetry/CloudEvents运行依赖。
  - 新增盲区: BL-01(高)。
  - 新增场景: SC-01。

- [grilling记录·三视角] DP-02:
  - [专家] Facade在L4完成后构造semantic candidate record；Adapter在原子提交点追加runtime authority event；持久化/API/GUI只消费、不拥有状态。
  - [新手] Facade不知道最终deadline、Adapter commit、hold采样及执行失败；通用Adapter也不应理解Mid-MPC L4/Lifecycle/solver rows。
  - [悲观] seam放错会把L4 PASS误显示为已下发，或把artifact成功误当command成功，或把hold误记为新solve。[R5][R6]
  - [机制C默认最简版失效] 继续用`post_commit`回调原位修改`algorithm_details`，会令hash、trace和artifact对应不同瞬间的状态。
  - 用户确认的方向: L4只给verdict/witness；Facade组装Mid semantic record；Adapter唯一拥有commit/reject/hold/reset事件；sink与GUI/API只消费；canonical record不被post-commit原位修改。
  - 新增盲区: BL-02(高)。
  - 新增场景: SC-02。

- [grilling记录·三视角] DP-03:
  - [专家] 发生身份与内容身份分离：事件使用唯一ID，语义内容使用canonical hash，通过`caused_by`/`derived_from`连接。[R1][R3][R4]
  - [新手] 当前`solve_id`无法覆盖复用同solve的hold、没有solver execution的pre-solver rejection及相同内容的两次发生。[R5]
  - [悲观] 混用ID与hash会导致重复事件误去重、rejected attempt覆盖accepted plan、reset后碰撞及candidate被误认为已下发。
  - [机制C默认最简版失效] 全部对象随机UUID只能提供唯一性；全部用hash则无法区分同内容的两次发生。两者都没有完整因果层级。
  - 用户确认的身份层级: run、cycle、attempt、solve、candidate hash、acceptance hash、receipt id/hash、event id；发生ID暂按`run_id + event_type + 单调序号`作为调研假设。
  - 新增盲区: BL-03(高)。
  - 新增场景: SC-03。

- [grilling记录·三视角] DP-04:
  - [专家] runtime authority events机械归约唯一timeline snapshot；GUI不得自行推断active/latest。
  - [新手] latest attempt、latest solve、L4 PASS、Adapter commit、hold及applied command不是同一事实。
  - [悲观] GUI自行缓存latest/active/previous，在断线重连、rejection、reset或post-commit failure时可能继续把旧计划画成active。[R7]
  - [机制C默认最简版失效] 单一“最后trace”会让rejection覆盖active；单一“最后成功”会隐藏当前失败。
  - 用户确认的方向: typed snapshot包含latest cycle/attempt/solve、active、last/previous committed、hold validation、applied command及terminal failure；COMMITTED/HELD/REJECTED/ARTIFACT_COMPLETED/RESET均有明确转换。
  - 新增盲区: BL-04(高)，建议保留但淡化并明确标记不可执行的历史轨迹。
  - 新增场景: SC-04。

- [grilling记录·三视角] DP-05:
  - [专家] 显式分开81个state knots与80个control intervals；状态时刻为0..1200s，控制区间为`[0,15)..[1185,1200]`。
  - [新手] 公共`9x81 predicted_trajectory`不是原始solver变量：第0列为实测状态，第1..80列由80组IPOPT航向/速度积分得到。[R6]
  - [悲观] 把81列全称优化航点、或把heading/speed同时模糊当state/control，会产生一拍偏移并令hold从错误区间取command。
  - [机制C默认最简版失效] 只保存north/east折线无法证明solver来源、时间区间、实测首点、直线成因或重放执行command。
  - 用户确认的方向: canonical grid、81个typed state knots、80个右连续control intervals及raw primal reference分离；公共9x81仅为兼容投影；terminal state无新control。
  - 新增盲区: BL-05(高)，右连续区间作为调研假设。
  - 新增场景: SC-05。

- [grilling记录·三视角] DP-06:
  - [专家] 目标证据绑定`epoch + TrackKey(target_id,generation)`，分离observation、prediction、Lifecycle authority、solver admission和L4 relevance。[R10][R11]
  - [新手] observed、Lifecycle-required、NLP-selected、L4-checked及GUI-displayed是不同集合，不能退化为`selected_target_ids`。
  - [悲观] ID复用、generation变化、排序变化或非selected目标省略会导致约束归错船、历史串接、GUI漏目标及L4无法归因。
  - [机制C默认最简版失效] `id+north/east`丢失generation、参考时刻、模型、不确定性、solver slot及排除原因。
  - 用户确认的方向: 每目标typed identity/observation/lifecycle/admission/predictions；canonical只用north/east；solver slot显式；GUI筛选不改变relevance；不同purpose预测不静默覆盖。
  - 新增盲区: BL-06(高)。
  - 新增场景: SC-06。

- [grilling记录·三视角] DP-07:
  - [专家] Acceptance Certificate表示L4语义判定；Accepted Plan Receipt表示Adapter commit后的执行authority；两者独立关联，不折叠为`feasible=true`。[R9]
  - [新手] IPOPT success、L4 accepted、receipt committed及Evaluator G3 PASS是四个不同结论，GUI必须标owner。
  - [悲观] 单一绿色成功会隐藏mandatory failure、active-prefix限制及预测边界；Evaluator反馈Planner会形成自证循环。
  - [机制C默认最简版失效] 完整AcceptanceResult复制进每tick trace导致payload膨胀；压成bool则丢失witness。
  - 用户确认的方向: Full Certificate、Inline Summary、Render Projection三层机械派生；Adapter commit后receipt才生效；hold引用原receipt；artifact状态不改写verdict；Planner/Evaluator分栏。
  - 新增盲区: BL-07(高)，截断优先去除advisory与PASS细节，mandatory失败及最差安全证据必须保留。
  - 新增场景: SC-07。

- [grilling记录·三视角] DP-08:
  - [专家] fresh、hold、replan、rejection、failure及reset表现为追加式事件，每个事件引用cycle/attempt/candidate/receipt，不原位覆写最后状态。
  - [新手] 输入无效、solver异常、L4拒绝、Adapter超时虽然都可能无active plan，但责任层和recoverability不同。
  - [悲观] 覆写式状态会隐藏hold stale→replan→failure链，令GUI保留旧SUCCESS或reset后旧receipt继续参与warm start。[R5]
  - [机制C默认最简版失效] 单一`status+reason`无法定位Assembler、IPOPT、L4、deadline、commit或artifact失败，也无法证明旧plan是否仍获授权。
  - 用户确认的方向: typed cycle/attempt/solve/L4/commit/hold/replan/command/artifact/reset/session事件；final failure清除active/receipt/warm；artifact failure不改写control verdict。
  - 新增盲区: BL-08(高)，建议Adapter入口先创建仅含身份/时刻/算法/input hash的轻量cycle事件。
  - 新增场景: SC-08。

- [grilling记录·三视角] DP-09:
  - [专家] hash绑定schema与canonicalizer版本；内容排序、数字表示、可选值和集合顺序均属于hash contract。[R4]
  - [新手] 当前Assembler、L4及Facade分别复制`json.dumps(sort_keys=True...)`，未来字段转换、Infinity处理和数组排序可能漂移。[R5][R6]
  - [悲观] 直接改变现有规则会令历史artifact、parity fixtures及六级链失验；未完整实现却宣称JCS会制造跨语言假一致。
  - [机制C默认最简版失效] `dataclass→dict→SHA256`无法稳定处理enum、NumPy scalar、负零、非有限值、unordered target及schema新增字段。
  - 用户确认的方向: 既有stage hashes不改；新增顶层evidence hash；项目专属versioned canonical JSON，不声称JCS；semantic与occurrence metadata分离；非有限值typed化；migration生成derived record、不改原artifact。
  - 新增盲区: BL-09(高)。
  - 新增场景: SC-09。

- [grilling记录·三视角] DP-10:
  - [专家] artifact内容、artifact descriptor及持久化lifecycle分离；内容hash不因QUEUED→COMPLETE变化，状态变化形成独立事件。
  - [新手] 当前BoundedArtifactSink返回共享dict，worker线程原位修改status，trace/diagnostics/GUI可能读到不同瞬间。[R5][R8]
  - [悲观] 异步状态进入canonical record会令hash漂移；每hold复制完整数组会耗尽容量；背压静默会高估evidence claim。
  - [机制C默认最简版失效] 每5s tick dump完整81点×多目标×solver arrays会快速触及16MiB单件和64MiB队列限制。
  - 用户确认的方向: immutable record、artifact descriptor、artifact event分离；每terminal attempt一个full artifact；hold/command只追加小事件；worker completion经bounded queue由simulation线程归约。
  - 新增盲区: BL-10(高)。
  - 新增场景: SC-10。

- [grilling记录·三视角] DP-11:
  - [专家] 确定性的record verification与受solver/platform影响的IPOPT re-solve分离；后者仅diagnostic。
  - [新手] 当前测试验证gzip digest和parent chain，但没有public verifier重查prepared vectors、f/g、L4、projection及runtime causality。[R6]
  - [悲观] 要求IPOPT逐bit一致产生假失败；仅验SHA256不能证明来源，重写全部内容并重算chain仍可通过。
  - [机制C默认最简版失效] `读取JSON+hash相同`没有重算OCP数值、L4、trajectory或authority timeline。
  - 用户确认的方向: V0 bytes、V1 schema、V2 lineage、V3 numerical、V4 acceptance、V5 projection、V6 runtime及可选V7 re-solve；不替代Evaluator/plant proof。
  - 用户确认V1不引入数字签名/key management；claim限定为INTEGRITY_VERIFIED，未来attestation作为外层扩展。
  - 新增盲区: BL-11(中)。
  - 新增场景: SC-11。

- [grilling记录·三视角] DP-12:
  - [专家] GUI消费typed render projection，不读solver内部字段、不缓存authority、不重算L4；地图、诊断及API来自同一timeline snapshot。
  - [新手] 当前地图虽画真实81点，但hold沿用原始完整轨迹，execution marker固定取index 1，不代表当前sim time。[R5][R7]
  - [悲观] hold中把已走区段继续画成active、固定15s execution point或rejected覆盖active会误导操作者。
  - [机制C默认最简版失效] 只给旧JSON加字段，GUI仍需自行判断fresh/hold/active/rejected、切suffix和对齐目标时刻。
  - 用户确认的方向: typed active/latest/historical/targets/acceptance/solver/quality render model；active suffix实线；失效历史灰虚线；rejected默认隐藏；execution按elapsed插值；Planner/Evaluator分栏。
  - 新增盲区: BL-12(高)。
  - 新增场景: SC-12。

- [grilling记录·三视角] DP-13:
  - [专家] evidence关键路径纳入20s总deadline；磁盘、压缩、retention及optional re-solve异步；预算只来自目标环境p99。
  - [新手] 当前0.25s reservation覆盖L4 p99约35ms，但Candidate 4新增record/hash/projection/event commit，不能假定零成本。[R6][R9]
  - [悲观] 全同步会让safe candidate因证据I/O超时；全异步会在没有稳定hash/receipt时发command；无界history/queue导致长场景内存增长。
  - [机制C默认最简版失效] API轮询时反复解析full artifact并生成投影，会把sim thread、浏览器与disk延迟耦合。
  - 用户确认的方向: typed validation/hash/inline/event/freshness/atomic commit同步；gzip/write/retention/completion/report/re-solve异步；沿用现有容量默认值并使completion/history有界。
  - 新增盲区: BL-13(高)；必须0/1/16目标测p50/p95/p99/max并重算reservation，不提高20s掩盖开销。
  - 新增场景: SC-13。

- [grilling记录·三视角] DP-14:
  - [专家] 深语义留在Mid-MPC模块；通用Adapter只接收最小algorithm-neutral evidence envelope；不强迫其他算法迁移。
  - [新手] `algorithm_details`没有typed seam；全面重写PlannerTrace则扩大至全部算法和API。
  - [悲观] 全局迁移影响其他trace/GUI/saved run/registry；Mid-aware Adapter破坏通用边界。
  - [机制C默认最简版失效] Adapter按algorithm_id分支读取Mid字段，后续每个事件继续增加专属逻辑。
  - 用户确认的方向: `MPCSolution.evidence`可选generic envelope；Mid内部生成deep typed record；Adapter只处理identity/transaction/artifact/timeline；legacy projection暂保留；GUI feature-detect。
  - 新增盲区: BL-14(高)，PlannerTrace 1.1作为待Step3核验假设，legacy至少保留明确迁移周期。
  - 新增场景: SC-14。

- [grilling记录·三视角] DP-15:
  - [专家] Candidate 4是evidence架构重构；除新字段正确外，必须证明不改变数学问题、solver result、L4 verdict及execution command。
  - [新手] unit tests不能覆盖Adapter transaction、async artifact、API timeline、browser active suffix和legacy algorithm兼容。
  - [悲观] evidence顺序可能改变deadline，hash可能破坏parity，GUI可能显示旧plan，async sleep tests可能偶发通过。
  - [机制C默认最简版失效] serializer-only tests无法发现precommit泄漏、hold错位、rejection残留、target错绑、backpressure deadlock或GUI stale cache。
  - 用户确认的方向: V1 pure、V2 timeline、V3 replay、V4 adapter、V5 numerical non-interference、V6 closed loop、V7 API/GUI、V8 compatibility、V9 performance、V10 live 8010、V11 full regression。
  - 新增盲区: BL-15(高)，建议先冻结main的HO/CS/OT/multiship canonical input/raw primal/L4 hash/command trace；离散与hash exact，浮点按既有量纲容差。
  - 新增场景: SC-15。

- Step2 gate: DP-01..DP-15均已逐点完成专家/新手/悲观/机制C grilling并获用户确认；BL-01..BL-15均有优先级；SC-01..SC-15已登记。待用户授权进入Step3逐盲区深调与证据确认。

### Step3 · 自主深度调研  [2026-08-13 10:04]

- Batch A覆盖BL-01..BL-04，新增证据[R13]..[R18]；证据已写入矩阵，待用户确认是否回答盲区，尚未标闭环。
- BL-01证据指向: stable semantic entity与runtime activity/event分离；L4 verdict/receipt不被dispatch、hold或artifact状态原位改写。[R13][R15][R16][R9]
- BL-02证据指向: optional `MPCSolution.evidence`为最小blast seam；Adapter只解释generic envelope/runtime event；避免改写20-call-site PlannerTrace或加入Mid分支。[R17]
- BL-03证据指向: CloudEvents允许counter或UUID；本项目run_id已有UUID且Web reset生成新run，故`run_id + evidence_epoch + monotonic event_seq`满足发生唯一性；semantic hash继续独立。[R14][R17]
- BL-04证据指向: event reducer生成唯一read model，GUI不自己缓存authority；标准只要求状态程序可判定，并不裁决历史轨迹必须保留或删除。结合用户已确认策略，历史轨迹可保留，但必须`executable=false`且视觉/文本状态明确。[R16][R18][R17]

- [用户确认门·2026-08-13 10:20] 用户确认Batch A证据回答BL-01..BL-04；四项已标闭环。Step3继续，未进入Step4。

- Batch B覆盖BL-05..BL-07，新增证据[R19]..[R23]；发现Step2“右连续control interval”与当前hold线性插值行为并不等价，新增BL-16/SC-16，待用户确认范围后才能闭环BL-05。
- BL-05证据指向: OCP数学网格确定为80个区间、81个state knots，`psi[k],u[k]`生成`t[k+1]`状态；但当前Adapter及held L4 candidate均按elapsed在相邻列线性插值。Candidate 4若改为ZOH将改变真实command，违反DP-15 non-interference。建议canonical evidence同时记录OCP区间参考与当前runtime插值策略，不在本候选改变执行语义。[R19][R20]
- BL-06证据指向: 不强制L3/L4共享同一对象。L3保留solver-selected预测，L4保留对全部tracks的独立安全预测；selected target在同一reference/grid/model下必须hash一致或产生显式reconciliation failure。每个track保留admission disposition，未进NLP者不得静默消失。[R21][R6][R11]
- BL-07证据指向: 8192-byte投影按确定性tier构建，不再原位抹除全部关键witness。Tier 0保留schema/hash/identity/verdict/artifact reference/truncation counters；Tier 1在FAIL/UNKNOWN保留每个mandatory failure的compact tuple；Tier 2保留最差安全数值witness；advisory/PASS细节最先丢弃。若Tier 0+1仍超限，产生typed `INLINE_CAPACITY_EXCEEDED`并引用full artifact，不得静默显示PASS。[R22][R23][R9]

- [用户确认门·2026-08-13 10:33] 用户确认Batch B证据回答BL-05..BL-07，并同意Candidate 4不改变当前hold线性插值行为；BL-05..BL-07与范围冲突BL-16均已闭环。Step3继续，未进入Step4。

- Batch C覆盖BL-08..BL-11，新增证据[R24]..[R30]；证据已写入矩阵，待用户确认是否回答盲区，尚未标闭环。
- BL-08证据指向: 在Adapter `plan`入口追加极轻`CYCLE_STARTED` occurrence，仅含run/epoch/event identity、sim time、requested/executed algorithm；`PlannerInput`成功后再追加带input hash的`INPUT_VALIDATED`。`_planner_input`、schedule、hold-before-first、solver、L4、deadline等每条异常路径必须有typed terminal event和owner/stage；无效原始输入不伪造candidate或full artifact。[R24][R14][R28]
- BL-09证据指向: 既有六级stage hash与Python字节规则冻结不改。新增Evidence声明`schema_id`与`canonicalizer_id=colav.python-json.v1`，明确finite float、negative zero、enum、optional、ordered target和UTF-8规则；不声称JCS。verifier按artifact声明的canonicalizer派发；升级产生derived record并引用旧hash，绝不按新规则重写旧artifact。[R25][R26][R4]
- BL-10证据指向: immutable `ArtifactDescriptor`只含submission/content identity、digest/path/size；QUEUED/BACKPRESSURE/COMPLETE/INCOMPLETE为独立`ArtifactStatusEvent`。worker仅向bounded completion queue提交immutable result，simulation/runner线程poll并分配event_seq、归约timeline；run close必须drain或生成terminal incomplete event。禁止worker持有并原位修改Adapter/trace返回对象。[R27][R15][R28]
- BL-11证据指向: V1不引入签名和key management。hash/canonical replay只允许声明`INTEGRITY_VERIFIED`、`SEMANTIC_REPLAY_VERIFIED`或`NUMERICAL_REPLAY_VERIFIED`，不得声明source authenticity、attested或non-repudiation；未来签名作为外层attestation引用同一evidence hash，不改变canonical record。当前分散测试不能冒充public verifier，仍需V0-V6入口；V7 IPOPT re-solve保持diagnostic。[R29][R30][R26]

- [用户确认门·2026-08-13 10:45] 用户确认Batch C证据回答BL-08..BL-11；四项已标闭环。Step3继续，未进入Step4。

- Batch D覆盖BL-12..BL-15，并因当前闭环基线新发现BL-17；新增证据[R31]..[R36]。BL-12..BL-15待用户确认；BL-17必须先确认scope。
- BL-12证据指向: GUI/API只消费event reducer生成的typed timeline/render snapshot。默认地图仅画active suffix为teal solid并按elapsed插值execution cursor；previous隐藏；last committed若已失效仅作`executable=false`灰虚线；rejected默认隐藏、开关后红虚线。诊断显示IPOPT source、81 states/80 controls/15s/1200s、fresh/held、course/speed span及lateral deviation；Planner L4与Evaluator G3分栏。GUI不得保留独立authority cache。[R31][R18][R7]
- BL-13证据指向: 现有250ms reservation有真实full-L4标定，但不包含Candidate4的validation/canonicalization/hash/inline/event/atomic commit同步tail，不能直接宣称仍足够。实施promotion gate沿同环境、每case 1000次测0/1/16目标及fresh/hold/rejected的p50/p95/p99/max；仅当combined critical path满足reviewed margin才保留或重算reservation，IPOPT cutoff相应缩短，总deadline仍20s。具体新数值是实施校准门，不是可提前猜测的设计常量。[R32][R9]
- BL-14证据指向: Mid trace带generic `evidence`时outer `PlannerTrace.schema_version=1.1`；无Evidence的VO/Fan/Nominal等继续1.0。1.1只add optional envelope，全部legacy字段保留且本候选不删除；Evidence/Render子文档各有独立schema。server/JS feature-detect 1.1，旧client忽略未知字段；任何删除/重命名另开breaking 2.0迁移，不在Candidate4。[R33][R34][R17]
- BL-15证据指向: non-interference基线冻结`b958512`、锁文件、8-record C++ oracle、focused 90-pass结果及当前7-fail闭环结果。schema/IDs/TrackKey顺序/row layout/schedules/failure codes/no-fallback/event topology exact；objective abs 1e-5、trajectory/raw/diagnostic abs 1e-6并对CPA行用既有scale-aware规则；wall time/path/event occurrence ID不做exact。Candidate4验收不得把当前L4 rejection变成PASS或改变command。[R35][R36][R30]
- BL-17冲突: 当前并非“所有Playground场景PASS”。复测7项全部fail：HO、CS give-way、OT双侧为`SAFETY_SWEPT_CLEARANCE`；CS stand-on、overtaken、multiship为`COLREG_STAND_ON_DRIFT`。这是Candidate1严格L4暴露的行为/契约缺陷，不是Prediction Evidence缺陷。推荐Candidate4保持non-interference、如实呈现并把修复拆为后续算法/L4专票；若要求Candidate4顺便修复，须回到Step1重新扩展scope。[R36]

- [用户确认门·2026-08-13 11:05] 用户确认Batch D证据回答BL-12..BL-15，并确认BL-17采用推荐scope：Candidate4不修复7个既有闭环失败，后续独立处理。BL-12..BL-15、BL-17已闭环。
- Step3 gate: BL-01..BL-17全部有证据与用户确认；14个高优先级与1个中优先级原始盲区，加2个新发现高优先级盲区均闭环。无未覆盖DP、无缺失三维置信度。允许进入Step4，尚未形成裁决。

### Step4 · 汇总分析·推荐方案  [2026-08-13 11:08]

- DP-01待确认推荐:

| 维度 | 内容 |
|---|---|
| 初步推荐 | 建立Mid-MPC专属deep `PredictionEvidence`模块：不可变semantic record描述candidate/L4/trajectory/targets；append-only occurrence events描述cycle/commit/hold/command/artifact/reset；pure reducer机械生成timeline、inline、render及artifact投影。Evidence只记录既有authority结论，不重新分类COLREG、不重新接受plan。[R13][R15][R16][R9] |
| 证据链 | PROV entity/activity与generation/invalidation分离[R13]；OTel completed/event immutable与causal links[R15]；event read model适合active/latest视图但不宜全局泛化[R16]；当前L4已冻结verdict/receipt authority[R9]。一致支持“稳定事实+运行事件+机械投影”。 |
| 弃用A | 单一巨大可变Evidence JSON：dispatch/hold/artifact回填会改变同一对象与hash，重现当前post-commit原位修改缺陷。 |
| 弃用B | 继续扩充`PlannerTrace.algorithm_details`自由字典：无法建立immutable lineage、typed replay及唯一authority。 |
| 弃用C | 全项目通用event-sourcing/observability平台：blast过大，VO/Fan/Nominal被迫迁移，违反Candidate4最小范围。 |
| 实现风险 | **中**。风险源：typed schema数量、semantic/event重复事实、reducer状态转换遗漏。以Mid模块边界、不可变构造、唯一字段owner和bounded event tail控制。 |
| 失效边界 | event缺失、乱序、parent/hash不一致或schema不支持时Evidence状态为`INCOMPLETE/INVALID`；不得据此生成新command authority，也不得改写L4 verdict或当前执行命令。 |
| 验证需求 | dataclass/array深不可变；canonical record同输入同hash；事件顺序与reducer属性测试；mutation/duplicate/out-of-order negative tests；Adapter command/L4/solver non-interference。 |

- DP-01内部确认门: 待用户确认后才写VR/ALT final；当前仅为Step4初步推荐。

- [用户授权·2026-08-13 11:12] Step4改为按同一`类型`批量展示；批内仍逐DP给出推荐、证据、弃用、风险、失效边界和验证，用户按类型批次确认后再写对应VR/ALT final。

#### Step4批次T · 技术型DP-01/DP-09/DP-11（待确认）

| DP | 初步推荐与证据链 | 弃用方案及理由 | 风险、失效边界、验证 |
|---|---|---|---|
| DP-01 深模块模型 | Mid专属deep module：immutable semantic record + append-only occurrence events + pure reducer/projections；不重判Lifecycle/L4。[R13][R15][R16][R9] | A巨大可变JSON：hash/时态漂移；B继续堆自由`algorithm_details`：无typed replay；C全项目event sourcing：blast过大。 | **风险中**：schema/transition遗漏。乱序、缺event、hash mismatch→Evidence `INCOMPLETE/INVALID`，不改变command。验证深不可变、hash确定、event reducer属性/negative、non-interference。 |
| DP-09 schema/canonical hash | 冻结现有Request→Receipt六级hash字节规则；新增`colav.prediction-evidence@1`及`canonicalizer_id=colav.python-json@1`，明确UTF-8、finite float、negative-zero、enum/null、ordered targets；新增顶层evidence hash。旧schema由声明的canonicalizer验证，升级只生成`derived_from`新记录。[R25][R26][R4] | A直接改成JCS：破坏历史hash且当前Python编码非完整JCS；B无canonicalizer版本：未来无法复验；C迁移时原位重写：破坏原始证据。 | **风险中**：float/optional/order漂移。unsupported schema/canonicalizer→`UNSUPPORTED_SCHEMA`，禁止按新规则猜测。验证golden bytes、边界float/Unicode/NaN/Inf/负零、target重排、旧artifact兼容。 |
| DP-11 verifier/replay | 建立单一public verifier：V0 bytes/digest；V1 schema/canonicalizer；V2 lineage/event causality；V3 prepared/raw/trajectory numerical；V4 L4重算；V5 inline/render机械投影；V6 runtime authority timeline；V7可选IPOPT re-solve仅diagnostic。V1只声明完整性/重放，不声明来源真实性。[R28][R29][R30][R26] | A只验SHA：无法证明语义/因果；B要求IPOPT bit-exact：跨patch/平台假失败；C本候选加入签名/key management：范围与运维成本过大。 | **风险中高**：旧schema dispatcher、独立重算、自引用hash。任一级失败给typed result且不改原verdict；V7差异不否定V0-V6。验证tamper corpus、parent断链、乱序/重复、量纲容差、L4差异、跨IPOPT patch。 |

- 批次T内部确认门: 待用户一次确认DP-01/09/11；确认前不写VR/ALT final。

- [用户确认门·2026-08-13 11:16] 用户批量确认技术型DP-01/09/11；已写VR-01..03与ALT-01..05 final。

#### Step4批次A · 架构型DP-02/DP-04/DP-07/DP-10/DP-14（待确认）

| DP | 初步推荐与证据链 | 弃用方案及理由 | 风险、失效边界、验证 |
|---|---|---|---|
| DP-02 ownership seam | Facade在L4后组装Mid semantic candidate/certificate并放入optional generic `MPCSolution.evidence`；Adapter唯一创建commit/reject/hold/reset/command occurrence及Accepted Plan Receipt；sink/API/GUI只消费reducer projection。[R17][R9][R15] | A Facade声明已下发：不知道最终Adapter deadline/commit；B Adapter读取Mid字段：污染通用边界；C sink/GUI推断authority：多事实源。 | **风险中**：跨Facade/Adapter事务切点。Adapter commit前不得出现receipt/active；post-commit artifact失败不撤销command。验证pre/post deadline、callback异常、generic Adapter无Mid字段访问。 |
| DP-04 authority timeline | 每run/epoch一个event store + deterministic reducer；snapshot显式区分latest cycle/attempt/solve、active receipt、last committed history、held validation、applied command、terminal failure。当前fail-stop terminal rejection清active；历史仅`executable=false`。[R16][R17][R18] | A GUI缓存active/latest：重连/reset漂移；B只存last trace：rejection覆盖active或隐藏failure；C event log直接当控制状态：replay/运行时耦合。 | **风险中高**：状态机遗漏/乱序。非法transition、epoch错配、receipt parent缺失→timeline INVALID且active为空。验证transition table、property/fuzz、reconnect/reset、duplicate/out-of-order。 |
| DP-07 Certificate/Receipt/projections | Full Acceptance Certificate保持L4语义；Adapter commit后生成独立Accepted Plan Receipt。Inline按Tier0身份/verdict、Tier1 mandatory failure、Tier2 worst safety、后续advisory截断；Render机械压缩且Planner/Evaluator分栏。[R22][R23][R9] | A certificate=receipt：把L4 PASS误作已执行；B只保留bool：丢witness；C超限删除全部witness：可能误导PASS。 | **风险中**：8192-byte budgeting。Tier0+1超限→`INLINE_CAPACITY_EXCEEDED`、无虚假PASS、full artifact引用；artifact状态不改verdict。验证16目标边界、stable ordering、每字节阈值、failure witness保留。 |
| DP-10 artifact lifecycle | Immutable semantic record、`ArtifactDescriptor`与`ArtifactStatusEvent`分离；sink worker只写bounded completion queue，simulation/runner线程poll、分配event_seq并归约；每terminal attempt一份full artifact，hold/command只小事件。[R27][R15][R28] | A共享dict原位更新：跨线程竞态/hash漂移；B同步gzip/fsync：挤占deadline；C每hold复制full artifact：容量爆炸。 | **风险中高**：shutdown/drain/backpressure。queue满或write失败→typed status、control不回滚但evidence claim incomplete；close必须drain或terminal incomplete。验证item/byte limits、slow/failing writer、close timeout、retention、无共享mutation。 |
| DP-14 generic compatibility | 只给`MPCSolution`增加optional algorithm-neutral EvidenceEnvelope；Mid有Evidence时PlannerTrace 1.1，其他算法仍1.0；legacy字段全部保留，server/GUI feature-detect；任何删除另走2.0 breaking迁移。[R17][R33][R34] | A全局PlannerTrace 2.0：无必要破坏；B Adapter按algorithm_id分支：专属schema扩散；C强迫VO/Fan迁移：范围失控。 | **风险低中**：双投影短期漂移。typed/legacy不一致→Evidence projection为权威并报compatibility mismatch，不能静默混合；本候选不删除legacy。验证VO/Fan/Nominal byte/behavior regression、旧client fixture、Mid 1.1 feature detection。 |

- 批次A内部确认门: 待用户一次确认DP-02/04/07/10/14；确认前不写对应VR/ALT final。

- [用户确认门·2026-08-13 11:20] 用户批量确认架构型DP-02/04/07/10/14；已写VR-04..08与ALT-06..10 final。

#### Step4批次I · 接口型DP-03/DP-05/DP-06/DP-12（待确认）

| DP | 初步推荐与证据链 | 弃用方案及理由 | 风险、失效边界、验证 |
|---|---|---|---|
| DP-03 identity/lineage | 发生身份统一为`OccurrenceId(run_id UUID, evidence_epoch, event_seq)`；cycle/attempt/solver execution/receipt/event均有各自occurrence identity并用`caused_by`连接。candidate/acceptance/receipt/evidence保留独立semantic hash，通过`derived_from`连接；Web reset新run，same-run reset升epoch且sequence重置。[R14][R17][R13] | A全部UUID：唯一但无局部顺序；B全部content hash：相同内容两次发生碰撞；C复用legacy solve_id：覆盖pre-solver reject/hold/reset。 | **风险中**：双身份混用。event sequence重复/倒退、epoch错配、parent不存在→V2 lineage fail。验证同内容重复、reset、replay、duplicate delivery、missing parent。 |
| DP-05 ownship trajectory | `PredictionGrid(80,81,15s,1200s)`；81个typed state knots含`t=0`实测首点和80个solver积分终点；80个`OptimizationIntervalReference`明确作用域`[t_k,t_{k+1})`并引用raw primal。另记录当前`RuntimeAppliedReference(policy=LINEAR_INTERPOLATION, elapsed)`；公共9x81仅兼容投影，terminal knot无新control。[R19][R20][R6] | A把81列都叫优化control：一拍错位；B只存NE折线：无法证明solver/control来源；C在Candidate4改ZOH：改变实际command。 | **风险高**：off-by-one/angle wrap/hold错位。grid/shape/source不一致→evidence invalid，不修正trajectory。验证k=0/80、7.5s hold、angle wrap、raw→knots复算、command non-interference。 |
| DP-06 target evidence | 每个`TrackKey(id,generation)`包含observation/reference time、geometry/covariance/health、Lifecycle authority、admission disposition/solver slot、purpose-keyed predictions。`NLP`只覆盖selected；`L4_SAFETY`独立覆盖全部relevant tracks；相同purpose inputs下比较content hash，差异生成reconciliation failure；display selection不改变relevance。[R21][R10][R11] | A仅selected_target_ids：静默丢目标；B按target_id无generation：ID复用串线；C强制L3/L4共享对象：破坏L4独立复核。 | **风险中高**：集合/slot/时基错绑。duplicate TrackKey、grid/reference mismatch或required target缺失→fail-closed。验证ID reuse、排序置换、selected/unselected、CV hash equality、generation变化。 |
| DP-12 render/API | Evidence reducer唯一输出`PredictionRenderSnapshot`：active suffix、latest attempt、invalid history、optional rejected、aligned target predictions、execution cursor、grid/provenance、straightness metrics、Planner L4与Evaluator G3。GUI只坐标投影/样式，不缓存authority、不重算安全/COLREG。[R31][R18][R7] | A继续让GUI解释raw trace：stale/字段漂移；B永远画完整plan：hold已走段误标active；C把Evaluator反馈作Planner判定：自证循环。 | **风险中**：API/GUI迁移和视觉误导。snapshot缺失时降级legacy且显式`evidence_unavailable`，不能合并新旧authority。验证REST/WS重连、active suffix像素/时间标签、rejected toggle、mobile/desktop、旧算法兼容。 |

- 批次I内部确认门: 待用户一次确认DP-03/05/06/12；确认前不写对应VR/ALT final。

- [用户确认门·2026-08-13 11:24] 用户批量确认接口型DP-03/05/06/12；已写VR-09..12与ALT-11..14 final。

#### Step4批次C · 约束型DP-08/DP-13/DP-15（待确认）

| DP | 初步推荐与证据链 | 弃用方案及理由 | 风险、失效边界、验证 |
|---|---|---|---|
| DP-08 lifecycle transitions | Adapter入口起始轻量`CYCLE_STARTED`；有效输入后`INPUT_VALIDATED`；随后typed attempt/solve/L4/commit/hold/replan/command/artifact/reset/terminal events。每cycle恰有一个terminal control outcome；当前fail-stop下任何terminal solve/replan failure清active receipt、solution与warm state，artifact failure仅降Evidence claim。[R24][R28][R17] | A从candidate才记录：早期失败消失；B单一status覆写：丢因果链；C artifact failure撤销command：混淆控制与持久化。 | **风险高**：异常路径和exactly-one terminal。重复terminal、缺terminal、reset后旧epoch event→V6 fail且active为空。验证每个failure injection、hold stale→replan、reset、deadline、callback、no-fallback。 |
| DP-13 realtime/backpressure | 20s总deadline不变。typed validation、canonical hash、inline、event append、freshness和atomic receipt/command commit同步；gzip/write/retention/completion/report/V7异步有界。现250ms仅为旧full-L4 reservation，实施后用同环境每case1000次0/1/16及fresh/hold/rejected combined-tail p50/p95/p99/max重校准；不得靠提高20s掩盖开销。[R32][R27][R9] | A全部同步：I/O致late reject；B全部异步：无稳定receipt先发command；C沿用250ms不测：无Evidence-tail证据；D无界queue/history：长场景耗尽内存。 | **风险中高**：p99、GC、queue shutdown。pre-commit critical evidence失败/超时→无command；post-commit persistence失败→command保留但claim incomplete。验证benchmark、slow disk、queue saturation、RSS/history bounds、deadline边界。 |
| DP-15 verification/claims | 分级门：V1 pure contracts；V2 reducer/timeline；V3 public replay verifier；V4 Adapter transaction；V5 solver/L4/command non-interference；V6真实HO/CS/OT/multiship delta；V7 REST/WS/browser；V8 VO/Fan/Nominal compatibility；V9 combined-tail performance；V10真实8010；V11全回归。基线固定`b958512`：focused 90 pass，闭环7项维持相同failure code；Candidate4不修复或放宽L4，不提升capability claim。[R35][R36][R30] | A只测serializer：漏事务/GUI；B要求7个场景转PASS：越过已确认scope；C把7项改xfail或降门：隐藏现存缺陷；D用HTTP200代替planner event：无执行证明。 | **风险高**：验收量大且baseline非全绿。新增测试必须全绿；旧7-fail集合不得扩大、缩小或换码；full suite以baseline delta报告，不能宣称全绿。验证exact/tolerance矩阵、real IPOPT、no fallback、artifact/replay、browser像素与live event。 |

- 批次C内部确认门: 待用户一次确认DP-08/13/15；确认前不写对应VR/ALT final。确认后将检查TD-01分解完整性并决定是否允许进入Step5。

- [用户确认门·2026-08-13 11:28] 用户批量确认约束型DP-08/13/15；已写VR-13..15与ALT-15..18 final。
- TD-01分解完整性检查: ownership(DP-02)✓；identity(DP-03)✓；timeline(DP-04)✓；ownship(DP-05)✓；targets(DP-06)✓；Certificate/Receipt(DP-07)✓；events(DP-08)✓；schema/hash(DP-09)✓；artifact(DP-10)✓；verifier(DP-11)✓；render(DP-12)✓；realtime(DP-13)✓；compatibility(DP-14)✓；verification(DP-15)✓。`DECOMPOSITION_READY`。
- Step4 gate: DP-01..DP-15全部有推荐、证据链、弃用理由、风险、失效边界与验证需求，并经用户按类型批量确认；TD-01无遗漏。允许进入Step5 DESIGN-IT-TWICE。

### Step5 · DESIGN-IT-TWICE  [2026-08-13 11:31]

- 比较对象选择: 不把任何DP直接标为低风险跳过；15个DP按耦合关系并入三个完整比较对象，全部接受替代设计压力测试。
  - S5-A 领域与权威架构: DP-01/02/04/07/08/14。
  - S5-B 预测契约与展示: DP-03/05/06/12。
  - S5-C 完整性、持久化与实时验证: DP-09/10/11/13/15。

#### S5-A · 领域与权威架构（待确认）

| 七维决策卡 | 方案A：有界深Evidence模块（推荐） | 方案B：每周期不可变全量Snapshot | 方案C：全项目通用Event-Sourced Planner平台 |
|---|---|---|---|
| 来源 | PROV稳定Entity/Activity分离、OTel immutable event/link、项目既有Facade→Solution→Adapter权威切点。[R13][R15][R17] | 当前PlannerTrace/latest-state API形态；以不可变快照修补当前可变dict与GUI缓存。[R17][R31] | Event Sourcing完整日志+projection模式。[R16] |
| 工程验证 | 外部模式成熟；本项目L4/Adapter seam、90项focused基线已验证。尚无本项目Candidate4实现证据。[R9][R35] | 项目已有snapshot式trace可运行；但当前post-commit回填、早期失败缺失、GUI stale cache正是反例。[R23][R24][R31] | 行业模式可用；本项目无跨算法event-store/reducer运行证据，且VO/Fan/Nominal未设计迁移。 |
| 技术分解 | Mid模块生成immutable semantic record；Facade拥有candidate/Certificate；Adapter追加cycle/commit/hold/command/reset及Receipt；pure reducer输出timeline/inline/render；optional generic envelope跨通用边界；legacy投影暂留。 | 每周期生成一个含candidate、L4、receipt、command、artifact status的不可变完整快照；后续状态生成新快照并`supersedes`前项；API只取latest/history，不设独立event reducer。 | 所有规划算法统一命令、求解、验收、执行、artifact事件；通用event store/reducer成为唯一状态；删除PlannerTrace专属路径并一次迁移全部GUI/API。 |
| 失效边界 | event缺失、乱序、epoch/hash/parent错误→Evidence `INCOMPLETE/INVALID`、active清空；artifact失败只降证据claim，不撤销已提交command；Evidence不得重判L4。 | snapshot生成中断→可能只有前一快照；async artifact完成必须复制全快照或另设补丁，容易出现latest覆盖执行权威；快照链断裂时难区分“没发生”和“未记录”。 | event store/reducer故障影响全部算法；schema迁移或projection bug可同时破坏控制可观测性；升级回滚范围跨全系统。 |
| 实现风险 | **中**：新typed schema、event transition、双投影；范围限Mid，Adapter仅generic transaction，blast可控。 | **中低初始/中高长期**：代码少，但重复数据、全快照hash、异步更新及causal semantics逐步堆叠；容易重新长成隐式事件系统。 | **高**：全算法、API、GUI、saved run迁移；明显超出Candidate4并违反最小范围。 |
| 可测性 | **高**：semantic构造、reducer、transition、projection均pure；可做property、tamper、duplicate/out-of-order、non-interference测试。 | **中**：单快照golden测试简单；跨周期因果、exactly-one terminal、async completion与replay需额外推断。 | **高但成本极高**：统一模型利于系统级重放；必须新增所有算法迁移、兼容和回归矩阵。 |
| 推荐度 | **5/5**。深模块承担复杂度；控制authority不迁移；完整覆盖DP-01/02/04/07/08/14。 | **2/5**。可作短期诊断DTO，不足以承载权威时间线、异步artifact及因果重放。 | **1/5**。长期平台议题；本候选收益不足以覆盖blast。 |

- S5-A初步裁决: 推荐方案A；拒绝B作为canonical evidence模型，允许其仅作为A的机械render snapshot；拒绝C进入Candidate4。
- S5-A确认门: 待用户确认采用A、拒绝B/C后，才写该比较对象final VR/ALT并进入S5-B。

- [用户确认门·2026-08-13 11:34] 用户确认S5-A采用方案A；VR-16、ALT-19/20已写final。方案B仅作为A的机械RenderSnapshot，方案C不进入Candidate4。

#### S5-B · 预测契约与展示（待确认）

| 七维决策卡 | 方案A：typed语义轨迹图 + 派生RenderSnapshot（推荐） | 方案B：统一稠密Prediction Tensor | 方案C：Artifact-first懒加载展示 |
|---|---|---|---|
| 来源 | 当前CasADi 80 interval/81 state knot语义、Adapter hold线性插值、L3 selected与L4 all-relevant双预测、PROV identity。[R19][R20][R21][R13] | 数值计算常用统一tensor/batch表示；当前公共9xN trajectory可视为简化先例。[R6][R19] | 当前full artifact + inline reference模式及常见离线分析流水线。[R4][R27] |
| 工程验证 | 本项目raw primal→trajectory、target prediction、Adapter执行链已运行；TrackKey/purpose/reconciliation与typed render尚待Candidate4验证。[R19][R21][R35] | ndarray路径成熟且紧凑；项目没有把异构目标、purpose、covariance、admission和不同网格放进统一tensor的验证。 | artifact sink已有运行证据；但异步完成、容量截断和GUI cache已经证明不能承担实时authority/display。[R23][R27][R31] |
| 技术分解 | `OccurrenceId`负责发生谱系；`PredictionGrid`固定80/81/15s；`OwnshipTrajectory`含81 state knots、80 interval refs和独立runtime interpolation；每个`TrackKey(id,generation)`按purpose保存预测、admission与reference；reducer派生active suffix、target alignment、straightness/provenance render。 | 一个`PredictionTensor[entity,state,knot]`承载ownship和targets，公共grid；control tensor与mask并列；identity、purpose、admission、covariance放side tables；GUI按mask直接切片。 | canonical trajectory仅写full JSON/NPZ artifact；inline只保留identity/hash/verdict/artifact URL和粗摘要；API/GUI需要时加载artifact、在服务端或浏览器计算active suffix及target alignment。 |
| 失效边界 | shape/grid/source/TrackKey/reconciliation错误→typed invalid，禁止猜测或修正；render缺失可显式legacy降级，但不能混合authority；Candidate4不改变现有线性hold command。 | 异构grid被padding/resample可能改变语义；side-table错位会把预测绑错目标/purpose；terminal knot和control mask易产生off-by-one；无法自然表达同目标两套独立预测。 | artifact未完成、丢失、backpressure或网络失败时实时轨迹不可用；客户端重算可能版本漂移；加载旧artifact时active/hold状态无法仅由文件决定。 |
| 实现风险 | **中高**：类型较多、坐标/时基/角度/索引严格；边界清晰且局部在Mid Evidence与纯projection。 | **中**：初始代码紧凑；语义side tables、mask和resample规则复杂，长期错误难定位。 | **中低后端/高运行体验**：canonical写入简单；把I/O、版本、投影和authority复杂度转嫁API/GUI。 |
| 可测性 | **高**：raw→knots复算、k=0/80、7.5s hold、angle wrap、ID reuse、selected/unselected、reconciliation、render golden和browser像素可分层测试。 | **中高数值/低语义**：shape与向量运算易测；purpose、generation、admission、mask错绑需要大量组合测试。 | **低实时/中离线**：artifact golden容易；async availability、重连、active suffix和跨版本客户端难做确定测试。 |
| 推荐度 | **5/5**。直接编码既有数学、执行和目标语义；RenderSnapshot保持GUI简单。 | **2/5**。适合作为内部批量计算格式，不适合作为canonical evidence contract。 | **1/5**。适合离线归档，不可承担L5实时展示与权威解释。 |

- S5-B初步裁决: 推荐方案A；方案B只允许作为局部计算优化且不得成为公开/canonical schema；方案C只保留为full artifact transport，不承担实时render authority。
- S5-B确认门: 待用户确认采用A、限定B/C后，才写该比较对象final VR/ALT并进入S5-C。

- [用户确认门·2026-08-13 11:38] 用户确认S5-B采用方案A；VR-17、ALT-21/22已写final。方案B仅可作为内部计算优化，方案C仅作full artifact transport。

#### S5-C · 完整性、持久化与实时验证（待确认）

| 七维决策卡 | 方案A：同步完整性内核 + 有界异步持久化（推荐） | 方案B：全同步durable事务后下发 | 方案C：command-first best-effort telemetry |
|---|---|---|---|
| 来源 | 既有Adapter原子commit/deadline、OTel异步export、SLSA/hash provenance分层、项目artifact sink经验。[R9][R15][R27][R29] | 数据库/WAL式“先持久后生效”事务思想；通过durable artifact换取最强本地留证。 | 常见低侵入日志/遥测：主路径不等待序列化、hash、写盘或export。 |
| 工程验证 | 当前L4 p99、250ms reservation、bounded sink及90项focused基线可作起点；Candidate4 combined tail仍必须重新标定。[R32][R35] | fsync/transaction可提供明确完成语义；项目20s实时路径没有磁盘tail、慢盘和queue饱和下可接受性的证据。 | 最容易保持现有求解延迟；但当前共享对象回填、artifact状态漂移和早期失败缺失已证明best-effort证据不足。[R23][R24][R27] |
| 技术分解 | 同步完成typed validation、versioned canonical hash、bounded inline、event append、freshness及receipt/command atomic commit；仅immutable descriptor入bounded worker；gzip/write/retention/completion/report/V7异步；public verifier执行V0-V6，V7 re-solve仅diagnostic；20s不变并重测0/1/16目标各状态tail。 | command前完成canonical full artifact编码、压缩、写临时文件、fsync、原子rename、digest复验及artifact COMPLETE；任何持久化失败均拒绝command；不需要异步completion事件。 | L4通过后立即commit command；semantic record、hash、inline、artifact和timeline全部进入异步队列；API先返回legacy trace，worker完成后回填或发布新状态。 |
| 失效边界 | pre-commit critical evidence失败/超时→无command；post-commit write/backpressure→command保留、artifact claim `INCOMPLETE/BACKPRESSURE`；V0-V6失败不改原始verdict，V7差异仅diagnostic。 | 慢盘、quota、fsync抖动或artifact体积导致deadline rejection，即使solver/L4本可安全执行；存储故障直接成为控制可用性故障。 | process crash、queue丢失或worker错误可产生“command已执行但无receipt/hash”；异步mutation使API、artifact和真实command无法可靠对齐。 |
| 实现风险 | **中高**：精确划分同步/异步边界、bounded queue、shutdown/drain、verifier dispatcher和性能门；但失效语义可局部定义。 | **高实时风险/中实现风险**：代码直观，I/O tail与控制deadline强耦合；不同机器难稳定复现。 | **低初始/高保证风险**：修改少，但无法满足Candidate4 replay、lineage、receipt和完整性目标。 |
| 可测性 | **高**：golden bytes、tamper、lineage、slow/failing writer、queue saturation、deadline、RSS、V0-V7及baseline delta可分别测试。 | **中高**：durability/failure injection可测；真实fsync tail、平台差异和偶发deadline难形成稳定CI门。 | **低**：主路径性能易测；crash window、最终一致性、回填竞态及缺失证据难确定复现。 |
| 推荐度 | **5/5**。最小同步安全核心；不让磁盘决定控制；仍能明确声明证据完整度。 | **2/5**。适合审计优先、无实时deadline系统；不适合当前20s控制链。 | **1/5**。只适合非权威观测，不满足Prediction Evidence目标。 |

- S5-C初步裁决: 推荐方案A；拒绝B把持久化可用性变成控制authority；拒绝C在command后才构造关键receipt/hash。实施前必须以combined-tail benchmark校准同步预算，不预先承诺250ms仍足够。
- S5-C确认门: 待用户确认采用A、拒绝B/C后，才写该比较对象final VR/ALT并完成Step5 gate。

- [用户确认门·2026-08-13 11:42] 用户确认S5-C采用方案A；VR-18、ALT-23/24已写final。全同步durable与command-first best-effort两方案弃用。
- Step5 gate: S5-A/S5-B/S5-C三张关键决策卡均完整填写来源、工程验证、技术分解、失效边界、实现风险、可测性、推荐度，并逐张获用户确认；DP-01..DP-15全部覆盖，无自主低风险跳过项。允许在用户授权后进入Step6方案包。

### Step6 · 术语 + 技术规约 + 方案包  [2026-08-13 11:45]

- [用户授权门] 用户明确授权进入Step6。
- 已生成独立方案包: `docs/superpowers/specs/2026-08-13-mid-mpc-lx-l5-prediction-evidence-solution-pack.md`。
- 八组件完整性:
  - 术语表: 21项，均含定义/方案含义/非含义/关联DP。
  - 技术规约: TS-01..TS-27，覆盖坐标系、单位、符号、时序、数值、接口六类；无未定项。
  - 决策卡片: S5-A/S5-B/S5-C final。
  - 证据矩阵: R1..R36分组溯源，并引用日志完整逐条矩阵。
  - 技术分解树: TD-01全部14个子模块+verification，`DECOMPOSITION_READY`。
  - 弃用方案: ALT-01..ALT-24完整保留。
  - 场景/验收: SC-01..SC-17、V1..V11、claim边界。
  - 冲突/盲区: 7项既有闭环失败、hold/OCP语义差异、L3/L4 coverage、performance calibration、authenticity和legacy migration均有明确边界；研究盲区为0。
- 方案包契约已写首部: to-spec可深化工程设计；不可推翻VR、重提ALT、修改TS或借Evidence改变solver/L4/command/capability。
- Step6内部确认门: **待用户完整接受方案包**。接受前不得标“已交付to-spec”，不得调用to-spec或写生产代码。
- [用户接受门·2026-08-13 11:55] 用户确认接受完整方案包；Step6 gate满足。
- to-spec已完成综合，不重新裁决VR/ALT/TS；测试seam沿用已确认V1..V11。
- 正式Spec: `docs/superpowers/specs/2026-08-13-mid-mpc-lx-l5-prediction-evidence-spec.md`。
- GitHub issue: `marinehdk/colav-simulator#27`，label=`ready-for-agent`。
- design-grounding状态: **已交付 to-spec**。后续实现必须使用`implement`+`tdd` vertical slices；出现新矛盾证据则回炉受影响DP。
