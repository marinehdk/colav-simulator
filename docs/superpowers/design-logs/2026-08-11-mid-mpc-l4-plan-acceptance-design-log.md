# 设计日志: Mid-MPC L4 Plan Acceptance

> **模式**: 重构        **创建**: 2026-08-11
> **权威起点**: `codex/mid-mpc-l4-acceptance-design@0732cf13e386447e0fd476b21903f797b2e3f819`
> **并行上游**: Candidate 3 L1/L2 Assembler 已完成并推送 `marine/main@1f459d8`；本分支仍仅做设计，不改生产代码
> **状态**: Step6方案包已接受；已交付to-spec

## 0. 决策树状态(权威索引 · 可变快照)

### 0.1 决策点注册表 [DP]

| ID | 描述 | 类型 | 父/分解 | 状态 | 详见 |
|----|------|------|---------|------|------|
| DP-01 | Plan Acceptance Module 的责任、Depth 与 Seam；排除 Lifecycle 决策、OCP 装配、IPOPT 求解、Evaluator 事后评分与 L5 fallback | 架构 | — | Step4推荐final | Step4-DP01；VR-01 |
| DP-02 | L4 输入是 immutable hash-linked plan bundle，还是读取 facade/trace/free-form diagnostics；如何验证同一 cycle、profile 与时轴 | 接口 | TD-01 | Step4推荐final | Step4-DP02；VR-02 |
| DP-03 | 接受结论采用单一布尔值，还是 solver/safety/COLREG/trackability/quality/evidence 分层 verdict 与总 verdict | 接口 | TD-01 | Step4推荐final | Step4-DP03；VR-03 |
| DP-04 | 数值接受检查覆盖 raw IPOPT status、原始 bounds、有限性、primal violation、slack、KKT/termination 证据到何种程度 | 数值 | TD-01 | Step4推荐final | Step4-DP04；VR-04 |
| DP-05 | synchronized swept hull clearance 如何覆盖 81 个状态点的 80 个区间、第一段、footprint、预测不确定性与每目标 witness | 安全 | TD-01 | Step4推荐final | Step4-DP05；VR-05 |
| DP-06 | L4 是否只复核 Candidate 3 `COLAV_STRICT` hard contract；MASS parity profile 的接受结论如何隔离，避免把 parity 当生产安全 | 安全 | TD-01 | Step4推荐final | Step4-DP06；VR-06 |
| DP-07 | COLREG consistency 如何消费 Candidate 2 已锁定的 role/side/phase，不重分类；HO/CS/OT/overtaken/Rule17 分别检查哪些动作与通过证据 | 规则 | TD-01 | Step4推荐final | Step4-DP07；VR-07 |
| DP-08 | early/substantial、wrong-side、past-and-clear、release、route/speed recovery 的物理量、窗口与 profile ownership | 规则 | TD-01 | Step4推荐final | Step4-DP08；VR-08 |
| DP-09 | trackability 如何检查 heading/speed/ROT/accel/decel、曲率与 first executable segment；静态 `KinematicCSOG` envelope 缺失事实如何表达 | 执行 | TD-01 | Step4推荐final | Step4-DP09；VR-09 |
| DP-10 | solution quality 如何检查抖动、周期反复、过度转向/减速、route progress、rejoin 延迟；哪些是 hard reject，哪些仅 warning | 质量 | TD-01 | Step4推荐final | Step4-DP10；VR-10 |
| DP-11 | 多目标如何形成 per-target verdict、Ship0 aggregate verdict 与冲突解释；目标船互撞保持 out-of-scope evidence | 规则 | TD-01 | Step4推荐final | Step4-DP11；VR-11 |
| DP-12 | fresh solve 与 adapter hold frame 分别何时复核；held plan 如何按当前绝对时间切片、检测 stale/deviation，而非沿用旧 success | 时序 | TD-01 | Step4推荐final | Step4-DP12；VR-12 |
| DP-13 | 计划拒绝后的 no-fallback/fail-stop 行为、`PlanStatus` 映射、recoverability 与用户可观察错误 | 失败 | TD-01 | Step4推荐final | Step4-DP13；VR-13 |
| DP-14 | Accepted Plan Handoff 如何成为唯一 warm-start eligibility authority，且不形成 Assembler↔L4 循环依赖 | 架构 | TD-01 | Step4推荐final | Step4-DP14；VR-14 |
| DP-15 | acceptance evidence schema、hash、artifact、inline 摘要、GUI projection 与 Planner/Evaluator source labeling | 证据 | TD-01 | Step4推荐final | Step4-DP15；VR-15 |
| DP-16 | L4 在线预算、确定性、artifact 异步写入、evidence-incomplete 与 20s solver deadline 的关系 | 运行 | TD-01 | Step4推荐final | Step4-DP16；VR-16 |
| DP-17 | 阈值、单位、容差、版本与 profile ownership；禁止场景 ID 分支、降低 50m 门或用现有 PASS 反推阈值 | 配置 | TD-01 | Step4推荐final | Step4-DP17；VR-17 |
| DP-18 | Module 验证矩阵：纯 contract/反例、真实 IPOPT、HO/CS/OT/Rule17/多船、hold、8010、full regression 与 claim 边界 | 验证 | TD-01 | Step4推荐final | Step4-DP18；VR-18 |

### 0.2 技术分解注册表 [TD]

| ID | 技术 | 分解子模块(→DP) | 触发步骤 |
|----|------|------------------|----------|
| TD-01 | Independent Plan Acceptance | immutable handoff/identity(DP-02) → layered verdict(DP-03) → numerical truth(DP-04) → swept safety/profile isolation(DP-05/06) → COLREG semantics(DP-07/08) → trackability/quality(DP-09/10) → multi-target/time(DP-11/12) → fail-stop/accepted-plan handoff(DP-13/14) → evidence/runtime/config/tests(DP-15..18) | Step1 |

### 0.3 盲区注册表 [BL]

| ID | 问题 | 归属决策点 | 优先级 | 调研状态 |
|----|------|-----------|--------|----------|
| BL-01 | Candidate 3 正在改 result、solver、adapter、persistence 与 evidence schema；最终 handoff/hash 尚未冻结 | DP-02/DP-14/DP-15 | 高 | EVIDENCE_CONFIRMED；R63，clean 1f459d8已固定五段chain与handoff placeholder，不再阻塞设计 |
| BL-02 | 当前 core 只把 IPOPT normalized status + primal row recheck 映射为 success；KKT/stationarity/scaling 证据是否可稳定取得未知 | DP-04 | 高 | EVIDENCE_CONFIRMED；R15..R21，terminal可取，callback incumbent当前缺同点multipliers |
| BL-03 | 当前 continuous CPA 是 point-center、依赖 core trajectory，不能直接证明同步 footprint hull clearance 与不确定性 margin | DP-05 | 高 | EVIDENCE_CONFIRMED；R22/R27..R29，需独立81点/80区间保守lower-bound oracle |
| BL-04 | 15s reduced model 到 `KinematicCSOG` plant 的 trackability 保守关系无独立 oracle；live GNC envelope 不存在 | DP-09 | 高 | EVIDENCE_CONFIRMED；R44/R45，无active Plant/GNC envelope，跨plant claim不成立 |
| BL-05 | COLREG Rule 8 的 early/substantial/ample time 没有跨场景统一数值；需要明确它属于 Planner profile，不是法规常数 | DP-08/DP-17 | 高 | EVIDENCE_CONFIRMED；R34，法规无统一数值，profile ownership留Step4/5 |
| BL-06 | quality hard reject 可能把“难看但安全”与“未来会失效”混在一起；warning/reject 边界无当前证据 | DP-10/DP-17 | 高 | EVIDENCE_CONFIRMED；R49/R50，仅trade-off metrics有证据，hard阈值留Step4/5 |
| BL-07 | hold frame 当前沿用上次 solution 的 feasible/status，不重新证明当前切片；stale/deviation policy 缺失 | DP-12/DP-13 | 高 | EVIDENCE_CONFIRMED；R52/R53/R60，旧success跨偏差泄漏，最小active-prefix重验有据 |
| BL-08 | rejected plan 若完全不能 warm start，可能损害实时性；若能 warm start，又会污染 accepted-plan 语义 | DP-14/DP-16 | 高 | EVIDENCE_CONFIRMED；R56/R57，warm是数值机制，资格必须来自L4 receipt；收益UNKNOWN |
| BL-09 | L4 拒绝后 Session 是立即 FAILED、暂停等待新 snapshot，还是下一 cycle 可重试；no-fallback 不等于无恢复策略 | DP-13 | 高 | EVIDENCE_CONFIRMED；R54/R61，当前terminal FAILED；bounded retry/recovery属Step4 policy |
| BL-10 | per-target COLREG 检查与 aggregate directive 冲突时，哪一层拥有最终 maneuver compatibility 解释 | DP-07/DP-11 | 高 | EVIDENCE_CONFIRMED；R42，Lifecycle是唯一compatibility authority |
| BL-11 | acceptance full artifact 与 inline 证据体积/延迟预算未知；同步持久化不能拖慢控制路径 | DP-15/DP-16 | 中 | EVIDENCE_CONFIRMED；R64/R66..R68，当前体积/本机成本已量化，exact p95留性能batch |
| BL-12 | target prediction、own trajectory、lifecycle、assembly、raw solver 五类 time axis/provenance 能否在 Candidate 3 后完全对齐尚未验证 | DP-02/DP-05/DP-12 | 高 | EVIDENCE_CONFIRMED；R22，assembly证据可对齐，core CPA摘要自身不完整 |
| BL-13 | 现有 Evaluator 是事后独立 oracle；若复用其分类/clearance代码，可能形成 Planner 自评或共享缺陷 | DP-05/DP-07/DP-18 | 高 | EVIDENCE_CONFIRMED；R27..R29，production与Evaluator需不同实现路径 |
| BL-14 | `TIMEOUT_FEASIBLE` 能否进入 L4、何种证据下允许控制下发，以及连续 timeout 上限如何叠加 | DP-03/DP-04/DP-13 | 高 | EVIDENCE_CONFIRMED；R15/R16/R18，native status语义已答，最终eligibility留Step4 |
| BL-15 | NLM 快调因本机缺少 `socksio` 未执行；未修改依赖或知识库，需以一手论文/官方文档替代 | DP-04..DP-10 | 中 | EVIDENCE_CONFIRMED；R14..R81，用户授权web替代，官方/一手资料与项目事实完成交叉验证 |
| BL-16 | Candidate 3 本地 16-target cold 单样本约 5.37s，不是 p95；L4 预算缺少完整闭环性能测量 | DP-16/DP-18 | 中 | EVIDENCE_CONFIRMED；R73，5-sample baseline与全selected单次已取得，full L4 p95仍UNKNOWN |
| BL-17 | acceptance thresholds/profile 由谁作为 trusted authority 提供，避免候选生产者同时定义要求与证明 | DP-02/DP-17 | 高 | EVIDENCE_CONFIRMED；R33/R63/R66，L4 runtime-resolved policy必须独立于candidate facts |
| BL-18 | layer outcome枚举、hard/soft分类、UNKNOWN/N/A语义、primary failure precedence与integrity short-circuit规则 | DP-03 | 高 | EVIDENCE_CONFIRMED；R55，coarse transport status与layer failures需分离；precedence留Step4 |
| BL-19 | v1是否必须独立重算KKT/stationarity；若需要，CasADi/IPOPT需暴露哪些dual、gradient和scaling证据 | DP-04 | 高 | EVIDENCE_CONFIRMED；R17..R21，terminal可计算，public result与callback incumbent证据不足 |
| BL-20 | mixed-unit row的分类容差表，以及strict fixed slack允许的数值诊断容差 | DP-04/DP-17 | 高 | EVIDENCE_CONFIRMED；R18/R20，row-family units及parity quirks已定位 |
| BL-21 | L4动态安全检查覆盖所有fresh/usable tracks还是仅Assembler admitted targets；如何避免admission自证与容量/性能失控 | DP-05/DP-11/DP-16 | 高 | EVIDENCE_CONFIRMED；R22/R32，全部fresh/usable tracks可审计，总量/预算留Step4 |
| BL-22 | L4 safety是否必须检查预测grounding/static ENC clearance；当前动态净距设计不足以证明static safety | DP-05/DP-18 | 高 | EVIDENCE_CONFIRMED；R30/R31，static是独立claim，模块归属/ENC缺失语义留Step4/5 |
| BL-23 | L4如何证明actual prepared problem真正使用strict bounds/slack policy，而非只信profile label | DP-02/DP-06/DP-15 | 高 | EVIDENCE_CONFIRMED；R15/R18，需actual bounds/options/parent chain |
| BL-24 | profile identity如何进入algorithm details、GUI、capability tuple和artifact，避免同一algorithm id下的claim混淆 | DP-06/DP-15/DP-17 | 中 | EVIDENCE_CONFIRMED；R18/R20，expected/actual/solver evidence须并列 |
| BL-25 | Playground OT profile是starboard-only，还是standard场景优先starboard且受限/镜像场景允许Lifecycle锁定port | DP-07/DP-17 | 高 | EVIDENCE_CONFIRMED；R35..R37/R41，Rule13非单侧；当前standard test claim不足 |
| BL-26 | plan-level COLREG几何predicate：port-to-port、pass-astern、past-and-clear、wrong-side、回切、stand-on envelope | DP-07/DP-08 | 高 | EVIDENCE_CONFIRMED；R35/R40，几何predicate可独立重算；stand-on bundle字段缺口已定位 |
| BL-27 | Lifecycle/Assembler需提供哪些action onset、latest-safe achievement deadline及reachability witness，L4才可判断early | DP-08/DP-17 | 高 | EVIDENCE_CONFIRMED；R38/R39，commit/deadline/reachability字段缺口已定位 |
| BL-28 | 初始wrong-side但物理可恢复时，允许的transient envelope、单调修正要求和容差 | DP-08/DP-09/DP-17 | 高 | EVIDENCE_CONFIRMED；R34/R38..R40，判定量已定位；容差留Step4/5 |
| BL-29 | 无状态L4如何识别跨solve连续小幅改向；是否需baseline、actual achievement及previous accepted plan摘要 | DP-08/DP-10/DP-14 | 高 | EVIDENCE_CONFIRMED；R34/R38/R39，固定commit baseline+actual achievement可识别 |
| BL-30 | 15s grid是否足以验证early/substantial；哪些检查必须使用first command或连续时间模型 | DP-08/DP-09 | 高 | EVIDENCE_CONFIRMED；R34/R39/R40，需first executable interval+后续achievement |
| BL-31 | trackability hard gate覆盖first executable prefix还是完整1200s rollout；远期误差如何进入safety margin | DP-05/DP-09 | 高 | EVIDENCE_CONFIRMED；R12/R44/R47，active prefix可绑定执行，full-horizon需tracking tube |
| BL-32 | Mid core heading/surge与Plant COG/SOG、body sway及9-state command字段的权威转换语义 | DP-02/DP-09/DP-17 | 高 | EVIDENCE_CONFIRMED；R43/R46/R47，COG/SOG与body psi/u错位已复现 |
| BL-33 | course/speed/position tracking error容差及其与50m safety margin的关系 | DP-05/DP-09/DP-17 | 高 | EVIDENCE_CONFIRMED；R12/R23/R44/R45，当前无calibrated tube，具体值UNKNOWN |
| BL-34 | quality metric的物理定义、归一化、hard/warn分类和profile阈值 | DP-10/DP-17 | 高 | EVIDENCE_CONFIRMED；R48..R50，物理metrics可定义；profile阈值留Step4/5 |
| BL-35 | 5s solve与15s grid下previous accepted plan的绝对时间重采样与重叠比较 | DP-10/DP-12/DP-14 | 高 | EVIDENCE_CONFIRMED；R46/R47，state knot与interval command需按absolute time分别对齐 |
| BL-36 | route progress/recovery基于何种稳定route reference；单bearing/line能否支持弯曲航线 | DP-10/DP-17 | 高 | EVIDENCE_CONFIRMED；R48/R50，需polyline arc-length，单bearing不足 |
| BL-37 | objective components能否归一化为跨target/cycle可比diagnostic，或v1完全不用于acceptance | DP-10/DP-15 | 中 | EVIDENCE_CONFIRMED；R48，raw objective跨cycle不可比，使用方式留Step4/5 |
| BL-38 | Lifecycle/PlannerInput/Assembler admission/predictions/solver bindings五类target集合的完备性、排除reason与identity reconciliation | DP-02/DP-05/DP-11 | 高 | EVIDENCE_CONFIRMED；R22/R32，identity可一一核对，显式排除reason仍是设计缺口 |
| BL-39 | 多个individually valid obligation无共同解时，Assembler failure与L4 defensive rejection的typed code/evidence统一 | DP-03/DP-11/DP-13 | 高 | EVIDENCE_CONFIRMED；R42/R55，保留Lifecycle/Assembler不同owner/code，public可coarse映射 |
| BL-40 | all-fresh-target continuous safety与per-target COLREG检查的复杂度、target上限和运行预算 | DP-11/DP-16 | 中 | EVIDENCE_CONFIRMED；R74，16×80 O(TN)几何成本已量化，full layers待实施benchmark |
| BL-41 | hold hard revalidation覆盖当前到next solve还是完整remaining horizon；两者的claim与成本 | DP-12/DP-16 | 高 | EVIDENCE_CONFIRMED；R52/R53/R60，active-prefix是最小hard scope；full-horizon成本UNKNOWN |
| BL-42 | control_trajectory是piecewise-constant intervals还是knot references；Adapter/Plant/GUI sampling统一语义 | DP-02/DP-09/DP-12/DP-17 | 高 | EVIDENCE_CONFIRMED；R46/R47，Mid为interval commands，当前Adapter误作knots插值 |
| BL-43 | hold期间新target/generation变化/显著机动如何触发same-algorithm immediate replan而不成为fallback | DP-12/DP-13/DP-16 | 高 | EVIDENCE_CONFIRMED；R52..R54，当前仅时钟；context identity/facts可形成失效触发 |
| BL-44 | shifted remaining trajectory、parent receipt、hold acceptance进入PlannerTrace/GUI的schema与payload | DP-12/DP-15 | 中 | EVIDENCE_CONFIRMED；R69，parent receipt/absolute-time support/current context/hold verdict字段已定位 |
| BL-45 | L4多层失败如何稳定映射现有公共`PlanStatus`、详细failure code与owner，避免枚举扩散或last-error-wins | DP-03/DP-13/DP-15 | 高 | EVIDENCE_CONFIRMED；R55，stable coarse status+完整layer list |
| BL-46 | hold immediate replan的eligibility、最大次数、deadline与fallback边界尚未量化 | DP-12/DP-13/DP-16 | 高 | EVIDENCE_CONFIRMED；R54/R61，须commit前、总deadline内、有界；次数为Step2 policy |
| BL-47 | L4前后的原子commit顺序及Session状态迁移尚未冻结；拒绝plan可能泄漏至hold/trace/warm-start | DP-13/DP-14/DP-15 | 高 | EVIDENCE_CONFIRMED；R54/R58/R59，现有异常路径不统一，需L4前后单一事务边界 |
| BL-48 | GUI/event如何展示无selected command的rejection并保留全部layer failures与source identity | DP-13/DP-15 | 中 | EVIDENCE_CONFIRMED；R59，需latest-attempt/active-plan双时间线与空command |
| BL-49 | neutral acceptance receipt/record schema、hash字段、存储owner及反循环依赖尚未冻结 | DP-02/DP-14/DP-15 | 高 | EVIDENCE_CONFIRMED；R6/R58，五段父链与receipt最小绑定字段已定位，exact schema留Step4/5 |
| BL-50 | session/profile/layout/target/lifecycle/time/deviation warm-start eligibility矩阵及cold-vs-invalid边界 | DP-12/DP-14/DP-17 | 高 | EVIDENCE_CONFIRMED；R56/R57，正常不兼容cold、identity损坏invalid，检查维度已定位 |
| BL-51 | 5s solve偏移到15s grid的primal重采样、terminal tail-fill与当前problem slack重建规则 | DP-09/DP-12/DP-14/DP-17 | 高 | EVIDENCE_CONFIRMED；R46/R56/R57，absolute-time primal-only规则已回答 |
| BL-52 | warm seed对IPOPT局部解盆地、确定性、耗时及cold-result差异的影响 | DP-04/DP-14/DP-16/DP-18 | 中 | EVIDENCE_CONFIRMED；R56/R57/R62，影响机制成立，实际收益明确UNKNOWN待性能验证 |
| BL-53 | L4 AcceptanceStage schema及L3 solver-candidate acceptance与L4 production acceptance命名隔离 | DP-03/DP-14/DP-15 | 高 | EVIDENCE_CONFIRMED；R58，solver candidate selection与production plan acceptance需分名 |
| BL-54 | full artifact、inline summary与GUI projection的字段预算、canonical映射和一致性验证 | DP-02/DP-15/DP-16 | 高 | EVIDENCE_CONFIRMED；R66/R70，三层骨架与acceptance-hash机械投影边界已回答 |
| BL-55 | fresh/hold/reject的active-plan timeline与latest-attempt timeline如何同时持久化和展示 | DP-12/DP-13/DP-15 | 高 | EVIDENCE_CONFIRMED；R59/R69，需Adapter唯一发布attempt/active/hold关系，UI不推断 |
| BL-56 | full artifact异步持久化、失败、retention、访问及bounded backpressure策略 | DP-15/DP-16 | 中 | EVIDENCE_CONFIRMED；R64/R67/R68，当前缺口与in-memory/persistence分责已回答 |
| BL-57 | per-target witness的frame、unit、absolute time与`TrackKey` generation序列化规范 | DP-02/DP-05/DP-15/DP-17 | 高 | EVIDENCE_CONFIRMED；R70，统一layer/code/TrackKey/frame/unit/time/sample/segment字段已定位 |
| BL-58 | L4 critical-path子预算及总20s deadline分配缺少真实16-target基准 | DP-16/DP-18 | 高 | EVIDENCE_CONFIRMED；R73/R74，solver与几何基线已回答，hard budget留Step4/5 |
| BL-59 | `TIMEOUT_FEASIBLE`到达过晚时freshness复核、总deadline与commit eligibility边界 | DP-03/DP-12/DP-13/DP-16 | 高 | EVIDENCE_CONFIRMED；R61，commit前须总deadline+context freshness，具体budget待性能batch |
| BL-60 | canonical float/hash、stable target/failure/witness ordering及telemetry排除规范 | DP-02/DP-15/DP-16/DP-17 | 高 | EVIDENCE_CONFIRMED；R65/R66，当前非JCS、equivalent-number hash差异与versioning需求已回答 |
| BL-61 | bounded artifact persistence queue的backpressure、shutdown、crash与retention语义 | DP-15/DP-16 | 中 | EVIDENCE_CONFIRMED；R64/R67/R68，需bounded async状态机；exact capacity/retention留Step4/5 |
| BL-62 | 16 targets×80 intervals full acceptance及hold validation的p95/p99性能门 | DP-11/DP-12/DP-16/DP-18 | 高 | EVIDENCE_CONFIRMED；R73/R74/R78，现状与完整测量protocol已回答，具体门留Step4/5 |
| BL-63 | 50m/150m在Lifecycle、Assembler、L4、Evaluator之间的authority graph与重复配置消除 | DP-05/DP-08/DP-17 | 高 | EVIDENCE_CONFIRMED；R23/R33，当前多处复制且无单一policy authority/hash |
| BL-64 | mixed-unit numerical tolerance表，尤其CPA m² row、strict slack与保守几何边界 | DP-04/DP-05/DP-17 | 高 | EVIDENCE_CONFIRMED；R15/R18/R20，具体阈值留Step4/5 |
| BL-65 | covariance/track quality到per-sample position uncertainty margin的置信公式及防重复计入 | DP-05/DP-17 | 高 | EVIDENCE_CONFIRMED；R24..R26，per-sample Gaussian公式成立，God-only与joint-risk边界明确 |
| BL-66 | L4 policy版本治理、更新审批及receipt/warm-start/capability claim失效范围 | DP-14/DP-15/DP-17/DP-18 | 高 | EVIDENCE_CONFIRMED；R63/R71，dependency hash变更须失效warm/claim，历史artifact保留 |
| BL-67 | quality/action/trackability阈值的独立校准集；禁止用现有五个PASS场景反推门槛 | DP-08/DP-09/DP-10/DP-17/DP-18 | 高 | EVIDENCE_CONFIRMED；R46/R49..R51，当前无independent calibration corpus |
| BL-68 | numerical/safety/COLREG/trackability/quality/evidence各layer独立oracle及禁止共享production helper边界 | DP-04/DP-05/DP-07/DP-09/DP-10/DP-18 | 高 | EVIDENCE_CONFIRMED；safety R27..R29、COLREG R40/R41、trackability/quality R44/R47..R51、evidence R66/R72均已回答 |
| BL-69 | negative/boundary/mutation/metamorphic corpus的覆盖完整性与最小充分集 | DP-02/DP-03/DP-18 | 高 | EVIDENCE_CONFIRMED；R75/R76/R81，SC-73..82最小类别骨架已回答 |
| BL-70 | capability tuple绑定L4 policy/plant/evaluator/scenario版本和artifact hashes的治理方式 | DP-15/DP-17/DP-18 | 高 | EVIDENCE_CONFIRMED；R71/R78/R80，dependency document/hash集合与失效语义已回答 |
| BL-71 | 8010真实accepted/rejected planner event、artifact及GUI projection的端到端检查清单 | DP-13/DP-15/DP-18 | 高 | EVIDENCE_CONFIRMED；R77，listener→HTTP→solver→L4→artifact→command→GUI清单已回答 |
| BL-72 | 性能环境、p50/p95/p99、determinism replay与flakiness门 | DP-16/DP-18 | 高 | EVIDENCE_CONFIRMED；R73/R74/R78，环境/case/percentile/canonical replay protocol已回答 |
| BL-73 | Candidate 3集成后完整baseline及Candidate 1增量/full regression范围 | DP-01/DP-16/DP-18 | 中 | EVIDENCE_CONFIRMED；R75/R79/R80，464/2 baseline与增量回归范围已回答 |

### 0.4 证据矩阵 [EV]

| ID | 来源类型 | 引用 | 检索置信 | 来源权威 | 场景适用 | 归属 |
|----|----------|------|----------|----------|----------|------|
| [R1] | PROJECT_FACT | `MidMpcIpoptSolver.solve`、`MidMpcResult`、`_continuous_cpa` 当前实现 | 高 | 高 | 高 | DP-03..06 |
| [R2] | PROJECT_FACT | `_MidMpcFacade.solve`、`_plan_status`、`MPCSolution` 映射 | 高 | 高 | 高 | DP-02..04/DP-07/DP-13 |
| [R3] | PROJECT_FACT | `CustomMPCAdapter` fresh solve/hold/validate/deadline/failure 执行链 | 高 | 高 | 高 | DP-09/DP-12..16 |
| [R4] | PROJECT_FACT | `Evaluator` Ship0 hard gate、footprint clearance 与 global target-target evidence | 高 | 高 | 高 | DP-05/DP-11/DP-18 |
| [R5] | ACCEPTED_DESIGN | Candidate 2 L0/L1 Encounter Lifecycle solution pack、`DecisionSnapshot`、role/side/commit/release authority | 高 | 高 | 高 | DP-07/08/11 |
| [R6] | ACCEPTED_DESIGN | Candidate 3 L1/L2 Assembler design/solution pack：81点、strict/parity、hash chain、accepted-plan seed placeholder | 高 | 高 | 高 | DP-02/05/06/14/15 |
| [R7] | DOCUMENTED_INTENT | 用户提供 M5 七层架构文档 L4.1..4.5 与 L5 分责 | 高 | 中高 | 中高 | DP-01/04/07..10/13 |
| [R8] | PROJECT_FACT | Mid-MPC single/multiship real-IPOPT tests、G3 capability 与 8010 planner event 历史证据 | 高 | 高 | 高 | DP-07..11/DP-18 |
| [R9] | PRIMARY_PAPER | Eriksen et al., Scenario-Based MPC：有限时域内联合检查 collision hazards 与 COLREG behavior | 高 | 高 | 中高 | DP-05/07/11 |
| [R10] | PRIMARY_PAPER | Johansen et al., predictive collision-risk assessment：目标状态/意图不确定性需进入风险证据 | 高 | 高 | 中 | DP-05/15/17 |
| [R11] | PRIMARY_PAPER | Predictive safety filter：计划/控制可在执行前由独立预测约束证据认证 | 中高 | 高 | 中 | DP-01/03/05 |
| [R12] | PRIMARY_PAPER | Safe trajectory tracking：reference infeasibility 与约束未知会损害跟踪安全/可行性 | 中高 | 高 | 中高 | DP-09/10 |
| [R13] | PRIMARY_PAPER | Multi-step predictive safety filter：时序证据、chattering 与 recursive feasibility 不可只靠单周期布尔判断 | 中高 | 高 | 中 | DP-10/12/14 |
| [R14] | EVIDENCE_SUBSTITUTION | NLM 因缺少 `socksio` 未执行；当前源码、用户文档与一手论文替代，未安装依赖 | 高 | 高 | 高 | DP-04..10 |
| [R15] | OFFICIAL_DOC | COIN-OR Ipopt options：desired/acceptable convergence、unscaled primal/dual/complementarity thresholds、scaling、bound relaxation与fixed-variable treatment | 高 | 高 | 高 | DP-04/06/17 |
| [R16] | OFFICIAL_DOC | COIN-OR Ipopt output/status：`Solve_Succeeded`仅为desired tolerance内局部最优；acceptable、callback stop、timeout、restoration各有不同语义 | 高 | 高 | 高 | DP-03/04/13/16 |
| [R17] | OFFICIAL_DOC | CasADi 3.7.2 `nlpsol`契约输出`x/f/g/lam_x/lam_g/lam_p`，因此terminal candidate multiplier evidence技术上可取得 | 高 | 高 | 高 | DP-04/14/15 |
| [R18] | PROJECT_FACT | Candidate 3 `1f459d8` solver/result审计：strict设置bound relaxation=0/slack fixed zero，但`MidMpcResult`未保留multipliers或iteration residual history | 高 | 高 | 高 | DP-04/06/15 |
| [R19] | PROJECT_EXPERIMENT | 本地CasADi 3.7.2/Ipopt strict fixture实验：terminal `lam_x/lam_g`和iteration stats可取；两例独立stationarity max约`1.70e-5/2.21e-4` | 高 | 中高 | 高 | DP-04/18 |
| [R20] | PROJECT_FACT | frozen row单位审计：heading/min-alt为rad、speed为m/s、CPA为m²、direction/terminal为m；同一dir slack跨m/rad且CPA seed用m缺口填m²变量 | 高 | 高 | 高 | DP-04/06/17 |
| [R21] | OFFICIAL_DOC | Ipopt callback/violation接口区分scaled/internal与unscaled/original量；默认iteration `inf_du`是scaled internal，不能冒充独立original KKT proof | 高 | 高 | 高 | DP-04/15/17 |
| [R22] | PROJECT_FACT | Candidate 3 `1f459d8` time/target audit：81点own path与全部PlannerInput target predictions可对齐到同一`sim_time+0..1200s`；frozen core自带CPA摘要仅覆盖selected targets与80点/79区间，漏最终15s区间 | 高 | 高 | 高 | DP-02/05/11/12 |
| [R23] | PROJECT_FACT | Assembler安全裕量审计：solver node floor已混入双方包围圆、当前position covariance及target一步位移补偿；L4同步复核不得把该frozen-index补偿当物理不确定性或再次叠加 | 高 | 高 | 高 | DP-05/06/17 |
| [R24] | OFFICIAL_DOC+DERIVATION | NIST二维高斯/卡方资料：99%置信椭圆量级为`chi2_2=.99=9.210`；其方向无关包围半径为`sqrt(9.210*lambda_max(P_pos))`，仅在Gaussian且covariance校准时成立 | 高 | 高 | 中高 | DP-05/17 |
| [R25] | PROJECT_FACT | Tracker采用`[x,y,Vx,Vy]` CV模型并以`F P F^T+Q`传播4x4 covariance；God covariance为零。Assembler却只读当前`P[:2,:2]`并把margin常量复制81点，未传播velocity/cross covariance或process noise | 高 | 高 | 高 | DP-05/17/18 |
| [R26] | PROJECT_EXPERIMENT | 使用当前KF默认`P0=diag(49,49,.5,.5),q=.4`做只读CV传播：99%包围半径约从0s的21.24m增至15s的75.05m、60s的531.31m、1200s的46.14km；证明朴素长时域传播不可直接作为可用production profile | 高 | 中高 | 中 | DP-05/17/18 |
| [R27] | PROJECT_FACT | Evaluator动态硬门用同步分段中心最小距离减双方包围圆；物理碰撞另用rectangle C2A；grounding另用ENC hazard+C2A。三种证据语义不同，当前L4不可直接复用Evaluator verdict | 高 | 高 | 高 | DP-05/18 |
| [R28] | PRIMARY_PAPER | Tang等C2A：连续刚体碰撞需在运动区间内做距离与motion-bound推进；离散node无碰撞不能推出区间无接触 | 高 | 高 | 中高 | DP-05/18 |
| [R29] | PROJECT_DERIVATION | 对被包围圆包含的矩形船体，`true hull distance >= center distance-r_os-r_ts`；同步线性中心段的analytic minimum再减segment最大uncertainty可形成独立、保守、方向无关的L4充分条件，但不是精确矩形净距 | 高 | 中高 | 高 | DP-05/18 |
| [R30] | PROJECT_FACT | Mid-MPC descriptor当前`requires_enc=False`且solver/Assembler无static hazard；PlannerInput已有ENC/draft，Evaluator把Ship0 grounding列为hard gate，其他planner已有chart hazard提取/C2A能力 | 高 | 高 | 高 | DP-05/18 |
| [R31] | OFFICIAL_STANDARD | IMO MSC.232(82)要求route planning/monitoring检查安全等深线、禁区、孤立危险及look-ahead告警；证明static navigation hazard与dynamic collision是不同必要证据，不直接裁决其模块归属 | 高 | 高 | 中高 | DP-05/18 |
| [R32] | PROJECT_FACT | target集合审计：frozen solver最多16个selected targets；Assembler为全部PlannerInput tracks发布prediction并要求Lifecycle decision一一对应；Adapter/Lifecycle拒绝>5s或UNUSABLE输入，但全体track数量无独立上限/排除reason schema | 高 | 高 | 高 | DP-02/05/11/16 |
| [R33] | PROJECT_FACT | 50m/150m当前分别复制在Lifecycle、Assembler/integration与Evaluator；值一致但无单一policy authority/hash，容易发生“决策门槛、求解门槛、L4门槛、事后门槛”静默漂移 | 高 | 高 | 高 | DP-05/08/17/18 |
| [R34] | OFFICIAL_RULE | COLREG Rules 8/16要求positive、ample time、readily apparent、early/substantial、safe-distance并持续检查到past-clear，但不提供统一角度、距离或秒数 | 高 | 高 | 高 | DP-07/08/17 |
| [R35] | OFFICIAL_RULE | Rule13锁定overtaking责任直到finally past and clear；Rule14要求HO双方右转并port-to-port；Rule15要求GW避免cross ahead；Rule17定义stand-on保持及MAY/MUST升级 | 高 | 高 | 高 | DP-07/08 |
| [R36] | OFFICIAL_GUIDANCE | AMSA Rule34说明OT可约定从目标船starboard或port侧通过；MAIB经验建议标准态势优先把目标留在本船port侧，但这是good-practice，不是Rule13硬常数 | 高 | 高 | 中高 | DP-07/08/17 |
| [R37] | PROJECT_FACT+EXPERIMENT | Candidate 2 Lifecycle以两侧可达clearance→route deviation→starboard tie-break选择OT corridor并锁定；当前centerline/port/starboard三例focused test `3 passed` | 高 | 高 | 高 | DP-07/08/18 |
| [R38] | PROJECT_FACT | `TargetDecision`已有commit baseline、required signed course change、action achieved与recovery permission；但无commit/action deadline，stand-on entry own course/speed也未暴露，public lifecycle projection还丢baseline | 高 | 高 | 高 | DP-02/07/08/15 |
| [R39] | PROJECT_FACT | Lifecycle以固定commit baseline累计actual achievement，Assembler按ROT可达性启用min-alt；因此可识别跨solve小步累积，但当前没有latest-safe deadline、first-action witness或同源reachability certificate | 高 | 高 | 高 | DP-08/09/17 |
| [R40] | PROJECT_DERIVATION | HO port-to-port、CS-GW pass-astern、OT locked target-track corridor/past-clear、stand-on hold与recovery guard均可由同步trajectory+immutable directive独立几何复核；具体容差/窗口仍必须由trusted profile提供 | 高 | 中高 | 高 | DP-07/08/18 |
| [R41] | PROJECT_FACT | 当前真实IPOPT closed-loop tests只在run后断言方向/通过/恢复；标准OT测试允许任一locked side，Lifecycle unit test才明确centerline tie→starboard；尚无per-solve plan-level COLREG oracle | 高 | 高 | 高 | DP-07/08/18 |
| [R42] | PROJECT_FACT | 多目标compatibility由Lifecycle aggregate唯一裁决：同侧合并、可安全STOP则STOP、否则`MANEUVER_CONFLICT`；Assembler再次拒绝side集合不一致，L4无需也不得重选aggregate maneuver | 高 | 高 | 高 | DP-07/11/13 |
| [R43] | PRIMARY_PAPER | Fossen的船舶path-following研究明确区分heading autopilot与course autopilot；COG/SOG由地固速度定义，不能在存在sway时与body heading/surge静默等同 | 高 | 高 | 高 | DP-02/09/17 |
| [R44] | PRIMARY_PAPER | 低阶reference planner到高阶plant的安全接口需显式motion prediction/reference governor；低阶路径自身可行不推出高阶闭环可跟踪 | 高 | 高 | 中高 | DP-05/09/18 |
| [R45] | PROJECT_FACT | 当前标准HO/CS/OT场景执行Viknes+FLSC；Ship仅对KinematicCSOG提取动态参数，Adapter又不保留这些kwargs，Assembler最终使用静态`published_kinematic_csog` capability且声明无live Plant/GNC envelope | 高 | 高 | 高 | DP-02/09/17/18 |
| [R46] | PROJECT_EXPERIMENT | current-code只读probe证明两处语义错位：`u=4,v=1,psi=0`被core当`psi=0,u=4`，实际COG/SOG为14.036°/4.123m/s；15s interval commands `[10°,20°]`在hold t=5s被线性采样为13.333°而非piecewise-constant 10° | 高 | 高 | 高 | DP-02/09/12/17/18 |
| [R47] | PROJECT_FACT | Mid输出81个state knots与80个interval commands；Adapter对interval commands使用knot线性插值。core仅约束reduced COG/SOG-like变量的ROT/decel，不能证明Viknes/FLSC或其他active plant的完整1200s响应 | 高 | 高 | 高 | DP-05/09/12/17 |
| [R48] | PROJECT_FACT | route anchor投影到完整polyline，但core route frame仍是单bearing无限直线；objective heading/speed/route项为context-dependent horizon sums，COLREG项又依赖target set/reference，raw total/components没有跨cycle统一物理标尺 | 高 | 高 | 高 | DP-10/15/17 |
| [R49] | PRIMARY_PAPER | 船舶trajectory planning文献把安全域、连续速度变化、路径长度、原计划偏差与ETA偏差作为分离目标；这些是trade-off metrics，不给本项目通用hard阈值 | 高 | 高 | 中高 | DP-10/17/18 |
| [R50] | PRIMARY_PAPER | MPCC以route arc-length progress、orthogonal contour error、lag error与control effort分离描述path-following quality；支持使用稳定route parameterization而非单bearing或raw NLP objective作为质量证明 | 高 | 高 | 中高 | DP-10/17/18 |
| [R51] | PROJECT_FACT+EXPERIMENT | focused suite `21 passed`仍未发现COG/heading与interval/knot语义错位；当前closed-loop Mid tests验证run后安全/方向/恢复，不验证每次solve的active-prefix trackability、cross-solve churn或route-progress quality | 高 | 高 | 高 | DP-09/10/18 |
| [R52] | PROJECT_FACT | Adapter仅按`last_solve_time+solve_period`决定SOLVE/HOLD；HOLD采样旧control/trajectory并原样继承旧status、feasible、objective与整条prediction，不检查当前ownship deviation、新target/generation、Lifecycle/policy/profile变化或剩余安全证据 | 高 | 高 | 高 | DP-12/13/16 |
| [R53] | PROJECT_EXPERIMENT | current-code只读probe：t=0接受north=0的fresh plan；t=0.5把current ownship改为north=100后，Adapter仍输出held north=0.5、`SUCCESS`、`solver_executed=false`且无重求，实证旧success会跨状态偏差泄漏 | 高 | 高 | 高 | DP-12/13/18 |
| [R54] | PROJECT_FACT | fresh solve只在状态/feasible检查后更新`_solution/_last_solve_time/current_plan`，但异常路径不统一：solve内`ColavExecutionError`有failure trace，post-solve validation/普通异常可跳过记录并保留旧trace；Session捕获任意异常后进入terminal `FAILED`，当前无pause/retry恢复态 | 高 | 高 | 高 | DP-12..15 |
| [R55] | PROJECT_FACT | 公共`PlanStatus`只有6个coarse outcome、`FailureSource`只有3个owner；Lifecycle已有`MANEUVER_CONFLICT`，Assembler已有`CORE_CAPABILITY_MISMATCH`，integration却都压为`INVALID_INPUT`并仅在details保留code/owner，证明coarse status与layer failure taxonomy必须分层 | 高 | 高 | 高 | DP-03/11/13/15 |
| [R56] | ACCEPTED_DESIGN+PROJECT_FACT | Candidate 3已冻结`ExecutionPrefixPlan(NO_EXECUTION_ACKNOWLEDGEMENT)`与`SeedPlan(DETERMINISTIC_COLD_START,warm_start_used=false)`；solution pack规定仅显式L4 accepted receipt可提供primal resample seed、dual v1禁用。当前实现没有accepted-plan handoff，故尚无rejected-plan seed污染，但也无warm收益 | 高 | 高 | 高 | DP-09/12/14/17 |
| [R57] | OFFICIAL_DOC | Ipopt `warm_start_init_point`消费previous related problem的primal/dual初值，`warm_start_same_structure`还要求相同NLP结构；CasADi说明非凸NLP解通常非唯一且依赖initial guess。warm start只是数值初始化，不是执行安全资格或accepted-plan证明 | 高 | 高 | 高 | DP-04/14/16/18 |
| [R58] | PROJECT_FACT | solver字段`accepted_by_quality_gate/accepted_candidate_source`只表示L3在terminal与best-feasible iterate间选candidate；replay artifact另有L4 `acceptance` placeholder。当前facade在真正L4不存在时已hash并持久化`NOT_EVALUATED_BY_ASSEMBLER`，说明命名边界已出现、但最终receipt必须在L4后形成 | 高 | 高 | 高 | DP-03/14/15/16 |
| [R59] | PROJECT_FACT | GUI server只把`solver_executed=true`保存为`latest_planner_solve`；frontend在当前HOLD/失败无新solve时回退显示上一solve的diagnostic/prediction。当前schema/UI不能同时表达“latest attempt rejected且无command”与“previous accepted plan仅作历史证据” | 高 | 高 | 高 | DP-12/13/15/18 |
| [R60] | PRIMARY_PAPER | Multi-Step Model Predictive Safety Filters指出只校正immediate next input会产生chattering，并在bounded model uncertainty等假设下用多步机制建立recursive feasibility；支持把hold持续可执行性视为需重新证明的时序性质，而非沿用一次accepted布尔值 | 高 | 高 | 中高 | DP-12/14/16/18 |
| [R61] | PROJECT_FACT | Adapter只对`_solve` wall elapsed实施总deadline：late SUCCESS降为`TIMEOUT_FEASIBLE`，连续次数受profile限制但仍可commit；当前无L4子预算、完成后freshness gate或hold-replan独立attempt budget。仿真时间在同步solve期间不推进，但operational deadline仍会过期 | 高 | 高 | 高 | DP-03/12/13/16 |
| [R62] | PROJECT_FACT+EXPERIMENT | focused schedule/contract/Assembler suite `39 passed in 17.78s`；现有测试覆盖solve周期、timeout、cold seed与typed assembly failure，却不覆盖100m stale-hold probe、L4 rejection atomicity、accepted receipt、5s/15s warm resample或latest-attempt GUI | 高 | 高 | 高 | DP-12..18 |
| [R63] | PROJECT_FACT | Candidate 3已在clean `1f459d8`形成稳定request/problem/prepared/solver/acceptance五段namespace与hash链；但L4仍是placeholder、accepted-plan handoff仍cold-only。Candidate 1可据此设计，不再被Assembler schema持续漂移阻塞 | 高 | 高 | 高 | DP-02/14/15 |
| [R64] | PROJECT_FACT+EXPERIMENT | 现有19份Mid replay artifact为98.7..122.9KiB raw、6.1..23.9KiB gzip；最大样本本地同步gzip+write 100次median 3.17ms/max 8.12ms。该测量只说明当前本机小样本成本，不是16-target/L4扩展后的p95 | 高 | 中高 | 中高 | DP-15/16/18 |
| [R65] | OFFICIAL_STANDARD+PROJECT_EXPERIMENT | RFC 8785要求确定的object排序、string与ECMAScript number serialization；当前`json.dumps(sort_keys=True)`只在当前Python contract内deterministic，probe中`0.0/-0.0`与`1/1.0`产生不同hash，且未声明canonicalization version。跨语言/跨版本identity不能默认为JCS | 高 | 高 | 高 | DP-02/15/17 |
| [R66] | PROJECT_FACT | replay artifact已把full prepared/raw vectors、stage documents与parent hashes存gzip；PlannerTrace仅放compact assembly ref、render projection及artifact digest/path。mutation tests可检测request/solver parent替换，inline assembly有`<8192`测试，但acceptance尚无真实layer receipt/witness | 高 | 高 | 高 | DP-02/15/18 |
| [R67] | PROJECT_FACT | `EvidenceWriter.write_mid_mpc_artifact`在solver调用栈同步canonicalize/gzip/write/rename；sink异常被转成`artifact.status=INCOMPLETE`且不改变candidate status/control。当前无bounded queue、backpressure、shutdown drain、retention/quota或crash-recovery契约 | 高 | 高 | 高 | DP-13/15/16 |
| [R68] | ACCEPTED_DESIGN+PROJECT_FACT | Candidate 2已采用1024 live-event ring+incremental JSONL，sink失败仅标evidence incomplete；Candidate 3已裁决inline≤8KiB、full content-addressed gzip、持久化失败不阻塞控制。两者支持把canonical in-memory verdict与异步persistence state分离 | 高 | 高 | 高 | DP-13/15/16 |
| [R69] | PROJECT_FACT | fresh trace发布solve-time完整trajectory；HOLD仍发布同一旧trajectory、旧target predictions与同一solve id，仅details增加held elapsed，不提供shifted remaining path、parent receipt或hold validation verdict。GUI又维护自己的current/previous/latest缓存，形成多处时间线authority | 高 | 高 | 高 | DP-12/15/18 |
| [R70] | PROJECT_FACT | render projection明确`ENU/sample/dt/duration`并给ownship field units；target prediction兼容性重复`north_m/east_m`与`x/y`，solver/L4 witness尚无统一`TrackKey generation/frame/quantity/unit/absolute_time/segment`结构。当前可画，不足以支持可复核per-failure witness | 高 | 高 | 高 | DP-02/05/07/15/17 |
| [R71] | PROJECT_FACT | capability key仅为`rule/scenario/algorithm/tracker`，evidence另带seed、legacy encounter profile与G3 predicate version；未绑定L4 policy hash、plant profile、formulation/build、scenario content、Evaluator version或acceptance receipt corpus，因此相关变更不会自动使既有G3 tuple失效 | 高 | 高 | 高 | DP-14/15/17/18 |
| [R72] | PROJECT_FACT+EXPERIMENT | artifact/hash focused tests `8 passed`，验证content hash、父链篡改、render projection和8KiB assembly；未有independent receipt verifier从artifact重算L4 verdict，也未覆盖canonical float edge、queue failure、双时间线或capability invalidation | 高 | 高 | 高 | DP-15/16/18 |
| [R73] | PROJECT_FACT+EXPERIMENT | Candidate 3已有M3/arm64、80×15s、cold、0/1/16-target各5次benchmark：solver p95约568.8/590.4/2159.2ms；本轮另用真实Lifecycle commitment确认16 targets全selected单次solver 1873.0ms、facade wall 2045.6ms。均低于20s，但样本少、非adversarial，不是production p95 guarantee | 高 | 高 | 中高 | DP-11/16/18 |
| [R74] | PROJECT_EXPERIMENT | 独立Python analytic swept-circle/segment probe覆盖16×80=1280 intervals、200次：median 4.33ms、p95 4.89ms、max 5.46ms。证明连续几何可按O(TN)低成本实现；不包含COLREG、trackability、hash或artifact，不能冒充full L4 benchmark | 高 | 中高 | 中高 | DP-05/11/12/16/18 |
| [R75] | PROJECT_FACT | 当前Mid测试含66个test functions：8-record frozen C++ parity、strict core/integration、19个Assembler contracts、HO/CS-GW/CS-SO/OT standard+mirror/overtaken及multiship真实IPOPT闭环。现有seams足够复用，但均未消费真实L4 verdict/receipt | 高 | 高 | 高 | DP-01/18 |
| [R76] | PROJECT_FACT | 当前negative coverage集中在fixture schema、Assembler typed failures与generic G3 mutations；只有target-order hash invariance。缺每个L4 layer独立mutation、同时多失败、hold stale/replan、receipt tamper/replay、translation/time/scenario-label metamorphic及accepted/rejected 8010事件 | 高 | 高 | 高 | DP-02/03/12..18 |
| [R77] | PROJECT_FACT+RUNTIME_OBSERVATION | 既有Candidate 2证据已证明8010 Mid-MPC 81点/15s/1200s accepted solve；本轮只读检查8010 listener PID 25955 cwd为Candidate 3 worktree，但未制造L4 accepted/rejected event。Candidate 1必须重新证明listener cwd、HTTP session、真实IPOPT attempt、L4 verdict/receipt、artifact digest、空/有command及GUI双时间线 | 高 | 高 | 高 | DP-13/15/18 |
| [R78] | PROJECT_FACT | 当前benchmark只有5 samples/case，无warm、hold、L4 full layers、p99、repeated canonical verdict/hash或flakiness gate。可复现protocol必须固定commit/OS/CPU/Python/CasADi/Ipopt/profile/deadline/target set/cold-warm、warmup与sample count，并把wall timing/artifact path排除出canonical verdict | 高 | 高 | 高 | DP-14/16/18 |
| [R79] | PROJECT_FACT+EXPERIMENT | Candidate 3 clean `1f459d8`完整`uv run pytest -q`结果为`464 passed, 2 skipped, 1 warning in 1627.55s`；Starlette warning为既有依赖告警。该结果是Candidate 1实施前权威full baseline，不替代未来L4 focused/performance/8010 evidence | 高 | 高 | 高 | DP-01/16/18 |
| [R80] | PROJECT_FACT | Candidate 2 `b94148c`是Candidate 3 `1f459d8`祖先；Candidate 3增量触及18 files、约3276 insertions/173 deletions，集中在Mid core/Assembler/integration/persistence/GUI/tests。Candidate 1回归至少需冻结parity expected、Lifecycle/Assembler contracts、全部Mid场景、artifact/API/GUI、capability与全仓 | 高 | 高 | 高 | DP-01/06/14..18 |
| [R81] | PROJECT_DERIVATION | SC-73..82已形成最小分层验收骨架：route-only positive；每mandatory layer一项independent defect；HO/CS/OT/overtaken/multiship真实闭环；fresh→hold→replan→reject；accepted/rejected 8010；16-target fresh/hold/cold/warm性能；full regression；dependency invalidation；translation/order/time/label metamorphic。它覆盖claim类别而非穷举物理空间 | 高 | 中高 | 高 | DP-18 |

### 0.5 场景注册表 [SC]

| ID | 场景描述 | 约束/边界 | 驱动决策点 |
|----|----------|-----------|-----------|
| SC-01 | route-only、真实 IPOPT 收敛、轨迹近直线 | 可接受，不把“直线”本身判失败；仍需有限性、trackability、progress | DP-03/04/09/10 |
| SC-02 | HO give-way | 生命周期已锁定右舷行动；检查早期/明显动作、wrong-side、通过、past-clear、recovery | DP-07/08/10 |
| SC-03 | CS give-way 与 CS stand-on/Rule17 escalation | 不重分类；分别检查让路动作和维持/升级语义 | DP-07/08/11 |
| SC-04 | OT 左右镜像与 overtaken | overtaking passing side 来自 immutable decision；两侧镜像不能硬编码场景 ID | DP-07/08/17 |
| SC-05 | 多目标 compatible/conflicting directives | per-target verdict + Ship0 aggregate；required target 不可被 aggregate success 隐藏 | DP-07/11 |
| SC-06 | node 全可行但 15s 区间发生 footprint clearance violation | L4 必须拒绝；不能依赖 NLP node status 或事后 Evaluator 才发现 | DP-05/06 |
| SC-07 | IPOPT `Solve_Succeeded` 但 raw NaN、原始 bounds 超差、strict slack 非零或证据 hash 不匹配 | fail-closed；不得发布 SUCCESS | DP-02/03/04/06/13 |
| SC-08 | solver timeout 但 primal 可行 | 分层输出 `TIMEOUT_FEASIBLE` 资格与 L4 verdict；禁止用 status 字符串单独放行 | DP-03/04/13/14 |
| SC-09 | safe 但过激/抖动/过度减速/迟迟不回航 | 区分 hard reject 与 quality warning；不得为过 PASS 降安全门 | DP-08/10/17 |
| SC-10 | fresh plan 通过后多个 5s hold frame | 按当前绝对时间切片、检查 staleness/deviation/剩余安全证据 | DP-12/13/14 |
| SC-11 | Candidate 3 `MASS_PARITY` 结果数学匹配但 production hard slack 可用 | 只宣称 parity，不得输出 production accepted | DP-03/06/15 |
| SC-12 | target-target 脚本碰撞、Ship0 对每目标安全 | 保留 global evidence；不作为 Ship0 Mid-MPC L4 failure | DP-11/15/18 |
| SC-13 | 各对象与hash分别合法，但来自不同cycle/profile；或candidate携带被降低的clearance requirement | L4验证事务父链和trusted expected profile，必须拒绝拼接/降门 | DP-02/15/17 |
| SC-14 | 有效候选同时违反continuous safety、COLREG side和trackability；另一个candidate integrity损坏 | 有效bundle稳定列出全部失败；integrity损坏时停止解释不可信下游语义 | DP-03/04/05/07/09 |
| SC-15 | IPOPT状态与原始数值证据对抗组合 | 覆盖success+x越界、NaN objective、strict slack噪声/实质超差、timeout primal-feasible、acceptable-level、restoration failure | DP-04/13/17 |
| SC-16 | solver slots均安全，但未selected且仍fresh/usable的target与候选轨迹相交 | 用于验证L4 safety target scope与admission独立性 | DP-05/11/16 |
| SC-17 | 动态目标全部安全，但避让轨迹在预测时域进入岸线/浅水hazard | 用于裁决static ENC safety是否属于L4 | DP-05/18 |
| SC-18 | 同一semantic request分别产生parity与strict结果 | parity可收敛且有slack，strict可为不同轨迹或infeasible；不得回退、串hash或交叉promotion | DP-06/13/15 |
| SC-19 | request声称strict，但prepared bounds/hash来自parity | 即使当前轨迹安全，integrity/profile gate仍拒绝 | DP-02/06/15 |
| SC-20 | 候选开始正确转向后瞬时分类变成CLEAR/CROSSING | L4继续按原锁定encounter检查至release，不重分类 | DP-07/08/12 |
| SC-21 | 标准OT锁定starboard，受限/镜像场景锁定port | 分别验证整段corridor与past-and-clear，不按scenario ID编码 | DP-07/08/17 |
| SC-22 | Rule17仍为STAND_ON但预测安全失败 | L4拒绝并报告Lifecycle/safety conflict，不自行升级Rule17 | DP-03/05/07/13 |
| SC-23 | 候选最终达到required course change，但晚于latest-safe deadline或CPA | 必须拒绝，终点达标不能洗白迟行动 | DP-08/09/17 |
| SC-24 | 连续多个5s solve各增加小角度，最终达到required change | 不得把阶梯小改向/抖动误认为单次substantial action | DP-08/10/14 |
| SC-25 | 当前已在wrong-side且受ROT限制，只能逐步纠正 | 最大能力持续修正与继续扩大wrong-side必须区分 | DP-08/09/17 |
| SC-26 | 预测将past-clear后回航，但Lifecycle尚未允许，或回航造成二次close-quarters | 必须拒绝，不用预测反向推进Lifecycle | DP-05/08/10/12 |
| SC-27 | ideal OCP path满足rate rows且安全，但KinematicCSOG rollout因T_chi滞后在第一段进入<50m | trackability/safety必须拒绝 | DP-05/09/17 |
| SC-28 | first command可跟踪，后续stage jump使executable rollout偏离并失去安全 | 用于裁决full-horizon trackability hard scope | DP-05/09；BL-31 |
| SC-29 | 初始存在sway，heading与COG不同 | 错误转换会产生相反first-turn或错误速度 | DP-02/07/09 |
| SC-30 | active model非KinematicCSOG，或缺T_chi/T_U/r_max | production trackability为UNKNOWN/UNSUPPORTED_ODD，不使用默认值放行 | DP-03/09/13 |
| SC-31 | 无目标或稳定corridor产生真实直线最优解 | quality应PASS，不为展示MPC而强迫曲率 | DP-10/17 |
| SC-32 | 计划安全但无必要地转45度并降至近零速度 | 验证quality warning/hard边界，不降低安全要求 | DP-10/17 |
| SC-33 | 连续solve在+10度/-10度间切换，每个单独计划均安全 | 跨计划churn必须可见并按profile裁决 | DP-10/12/14 |
| SC-34 | Lifecycle已允许recovery，但计划长期保持大横向偏移和低速 | 报告recovery delay，不能强迫不安全回航 | DP-08/10/17 |
| SC-35 | 三目标中HO安全、crossing wrong-side、CLEAR无义务 | aggregate拒绝并精确指向crossing target | DP-03/07/11/15 |
| SC-36 | 两个required targets锁定不兼容port/starboard corridor | 正常路径Assembler失败；注入candidate时L4 defensive reject | DP-02/11/13 |
| SC-37 | target ID相同但generation/episode变化 | 旧prediction/commitment不能与新track拼接 | DP-02/07/11/12 |
| SC-38 | Ship0对全部目标安全且规则一致，但目标船彼此碰撞 | Ship0 L4可PASS，global evidence明确非零 | DP-11/15/18 |
| SC-39 | fresh plan接受后1s出现新近距离target | hold失效，不能等待固定5s周期 | DP-05/11/12/13 |
| SC-40 | 本船actual state偏离accepted rollout，旧计划从新状态不再保持50m | hold revalidation拒绝 | DP-05/09/12/13 |
| SC-41 | stage0=+10度、stage1=-10度，hold发生在t=5s | piecewise-constant语义继续stage0，不线性插值 | DP-09/12/17 |
| SC-42 | reset/time rewind/profile change/track generation替换后复用旧receipt | integrity gate拒绝 | DP-02/12/13/15 |
| SC-43 | IPOPT成功且候选格式有效，但L4 continuous safety拒绝 | 不更新solution/current plan/receipt，不发`planner_solved`，Session fail-stop | DP-03/05/13/15 |
| SC-44 | hold因新target失效并触发同周期重求 | 最多一次同算法Mid-MPC重求；接受则commit，拒绝则fail-stop，无循环retry | DP-12/13/16 |
| SC-45 | 同一有效候选同时违反numerical、safety与COLREG | public status按固定precedence稳定映射；完整failure list不丢失 | DP-03/13/15 |
| SC-46 | 已有accepted plan后，新候选被L4拒绝 | 不复用旧plan、不把拒绝plan用作warm-start、不输出隐式last-safe控制 | DP-13/14 |
| SC-47 | 连续两个strict fresh cycle均正常，第二周期距前次5s | 第二周期可使用经验证的shifted primal seed，但新candidate仍经过完整L4 | DP-02/12/14/18 |
| SC-48 | previous receipt正常过期/结构不兼容，另一次receipt hash被篡改 | 正常不兼容显式cold start；证据损坏`INVALID_INPUT` fail-closed | DP-02/13/14/15 |
| SC-49 | IPOPT成功但L4拒绝、parity diagnostic或hold PASS | 三者均不签production accepted receipt，不获得warm-start资格 | DP-06/12/13/14 |
| SC-50 | 使用合法warm seed的新solve失败或被L4拒绝 | 不自动cold retry；按DP-13 fail-stop | DP-13/14/16 |
| SC-51 | 5s solve offset落在15s control interval内部 | 验证heading/speed primal重采样、terminal tail-fill、当前problem slack重建及dual禁用 | DP-09/12/14/17 |
| SC-52 | L3 `Solve_Succeeded`但L4 continuous safety拒绝 | GUI显示L3 candidate与L4 rejection；无command，artifact末段为真实rejection | DP-03/05/13/15 |
| SC-53 | L4接受并写出full artifact、inline summary与render projection | 三者hash/trajectory/verdict一致；任一篡改可检测 | DP-02/15/18 |
| SC-54 | 同一fresh receipt后出现hold PASS与hold stale | 两者引用原receipt；latest-attempt不被旧`planner_solved`遮蔽，不签新receipt | DP-12/15 |
| SC-55 | artifact sink失败或持久化不完整 | 内存裁决不改变；`persistence=INCOMPLETE`可观察且不伪造artifact完整性 | DP-13/15/16 |
| SC-56 | L4接受Ship0 plan，Evaluator事后报告target-target collision | 两source同时可见、scope明确，互不改写verdict | DP-11/15/18 |
| SC-57 | safety/COLREG witness缺frame、unit、absolute time或TrackKey generation | integrity gate拒绝，不允许GUI projection补充authority | DP-02/03/15/17 |
| SC-58 | 16 targets×80 intervals执行全部mandatory L4 layers | 验证最坏耗时/内存及无layer skipping | DP-11/16/18 |
| SC-59 | IPOPT成功，但L4完成时总critical-path deadline已超 | 不commit command、不签receipt；不得用磁盘I/O耗时混淆authority timing | DP-12/13/16 |
| SC-60 | IPOPT `TIMEOUT_FEASIBLE`，L4通过且当前时刻freshness仍在总deadline内 | 明确保留solver与L4双状态；允许次数仍受consecutive-timeout policy限制 | DP-03/04/12/16 |
| SC-61 | artifact sink阻塞、失败或bounded queue满 | canonical verdict/hash不变；persistence状态为`INCOMPLETE/BACKPRESSURE` | DP-15/16 |
| SC-62 | 同一canonical bundle重复100次但wall timing、artifact path不同 | verdict、failure/witness顺序、acceptance hash与receipt eligibility一致 | DP-02/15/16/18 |
| SC-63 | 任一L4 mandatory layer异常或预算耗尽 | fail-closed，不输出partial verdict/receipt，不跳过后续安全义务后误接受 | DP-03/13/16 |
| SC-64 | hold validation超出独立预算 | 不继续旧plan；最多一次same-algorithm replan，否则fail-stop | DP-12/13/16 |
| SC-65 | candidate evidence声明30m hard clearance，但trusted ODD profile要求50m | integrity拒绝；candidate不能自带降级门自证 | DP-02/05/17 |
| SC-66 | 同一物理状态分别正确标ENU/rad与错误标NED/degree | 正确输入稳定；frame/unit错配在integrity gate拒绝 | DP-02/09/15/17 |
| SC-67 | CPA m² row、heading rad、speed m/s与clearance m同时位于各自容差边缘 | 按quantity/row-family裁决，不使用统一`1e-3` | DP-04/05/17 |
| SC-68 | Lifecycle基于不同几何/能力输出不同minimum action与deadline | L4逐cycle消费snapshot，不使用固定5°/30°或本地deadline | DP-07/08/17 |
| SC-69 | 相同trajectory下prediction uncertainty从0增加 | required margin只增加一次，来源/置信语义可追踪 | DP-05/15/17 |
| SC-70 | L4 policy version/hash改变 | 旧receipt/warm seed不兼容；claim需按新policy重新验证 | DP-14/15/17/18 |
| SC-71 | active plant envelope比YAML更窄，或live capability事实缺失 | 使用live事实或`UNKNOWN`拒绝；不得静态默认放行 | DP-03/09/17 |
| SC-72 | 相同物理bundle只改变scenario ID或seed标签 | L4 verdict语义不变，禁止scenario-specific threshold分支 | DP-10/17/18 |
| SC-73 | route-only真实IPOPT产生近直线candidate | L4接受；直线不是质量缺陷，证据链与receipt完整 | DP-03/10/15/18 |
| SC-74 | numerical/safety/COLREG/trackability/evidence各植入一个可控缺陷 | 对应独立oracle稳定捕获；不依赖production helper自证 | DP-04/05/07/09/15/18 |
| SC-75 | HO、CS-GW、CS-SO、OT标准/镜像、overtaken真实IPOPT闭环 | strict、God、固定seed、无fallback；安全/规则/recovery及L4 receipt通过 | DP-05/07/08/10/18 |
| SC-76 | multiship中Ship0对全部目标安全，目标船脚本互撞 | Ship0 L4/G3 scope可PASS；global Evaluator collision显式保留 | DP-11/15/18 |
| SC-77 | fresh→hold PASS→new target stale→single replan→reject/reset | 验证active/latest双时间线、no fallback、receipt清理与fail-stop | DP-12/13/14/15/18 |
| SC-78 | 8010分别产生真实accepted与rejected Mid-MPC planner event | 验证listener cwd、solver identity、L4 source、artifact、GUI及无虚假command | DP-13/15/18 |
| SC-79 | 16-target fresh、hold、cold/warm各运行性能基准 | 记录环境与p50/p95/p99；mandatory layers完整执行 | DP-11/14/16/18 |
| SC-80 | Candidate 3 baseline、Candidate 1 focused suites及full repository regression | 无L3 parity/Lifecycle/Assembler/其他算法回归 | DP-01/06/18 |
| SC-81 | L4 policy hash、plant profile或scenario/evaluator version变化 | 旧receipt及G3 evidence不继承；tuple需重新验证 | DP-14/15/17/18 |
| SC-82 | translation、target order、absolute time、scenario label metamorphic变换 | 物理等价输入保持verdict语义；canonical hash按契约稳定/变化 | DP-02/15/16/18 |

### 0.6 裁决注册表 [VR]

| ID | 裁决对象 | 结论 | 采纳/弃用 | 理由 | 时间 |
|----|----------|------|-----------|------|------|
| VR-01 | DP-01 Module/Seam | 采用深、纯、无状态、确定性Plan Acceptance Module；单一窄Interface位于L3 candidate之后、Adapter原子commit之前；内部编排L4 mandatory layers，不改candidate | 采纳(final) | 最大化Depth/locality/replay；不侵入Lifecycle、Assembler、IPOPT、L5或Evaluator authority | 2026-08-12 |
| VR-02 | DP-02 Input/Identity | 采用单一immutable/versioned/self-contained request，顶层分candidate/authority/execution/prior四个typed namespace；ENU/SI/rad、81 state knots/80 piecewise-constant intervals、TrackKey generation、expected/actual profile、versioned schema normalization与offline replay | 采纳(final) | authority与candidate facts分离；消除free-form/time/frame/target/hash漂移；不把I/O放进在线Interface | 2026-08-12 |
| VR-03 | DP-03 Layered Verdict | 采用integrity/numerical/safety/COLREG/trackability/quality/evidence typed layers及PASS/FAIL/WARN/UNKNOWN/N/A/NOT_EVALUATED taxonomy；mandatory hard fail-closed，quality V1 advisory，MASS_PARITY diagnostic-only，primary仅为完整failure list的稳定projection | 采纳(final) | 保留多失败、applicability与source witness；避免bool/score/exception丢失语义；持久化状态不回写内存裁决 | 2026-08-12 |
| VR-04 | DP-04 Numerical Acceptance | 采用eligible termination class、同一candidate original-primal hard recheck、strict preparation proof与objective一致性；KKT在V1为同点structured advisory，callback incumbent无同点dual时明确NOT_EVALUATED；mixed-unit按quantity/row-family容差 | 采纳(final) | 不把Ipopt字符串、scaled residual或统一容差误作原始可行/最优证明；保留callback/timeout feasible数值资格但把最终dispatch交给deadline/freshness与全部业务hard layers | 2026-08-12 |
| VR-05 | DP-05 Swept Safety | 采用全部fresh/usable相关目标的81-knot/80-interval同步连续保守船体净距；50m为trusted physical hard gate；God uncertainty显式为零，其他预测需校准envelope；chart-backed applicable profile独立执行static hazard hard check | 采纳(final) | 覆盖selected-only、node-only、footprint、末段、uncertainty与static缺口；不复用solver/Assembler/Evaluator自证；Ship0与target-target scope分离 | 2026-08-12 |
| VR-06 | DP-06 Profile Isolation | 采用同一L4 implementation与显式versioned profile contract；MASS_PARITY永远DIAGNOSTIC_ONLY，COLAV_STRICT仅在trusted expected profile、actual preparation、effective options及完整parent chain一致且全部mandatory gates通过时具production eligibility | 采纳(final) | parity fidelity与production acceptance正交；机械复核实际bounds/options而非标签；strict失败无parity fallback，profile/hash变化使receipt与claim失效 | 2026-08-12 |
| VR-07 | DP-07 COLREG Consistency | 采用Lifecycle directive作为唯一规则决策authority，L4按TrackKey/episode消费已锁定role/phase/side/action并用完整absolute-time trajectory独立验证HO port-to-port、CS pass-astern、OT locked corridor、stand-on/Rule17语义；不重分类、重选侧或仲裁冲突 | 采纳(final) | 防止candidate动作后的intent flicker；定位上游directive与下游trajectory错误；standard OT右转偏好留Lifecycle policy，镜像/受限场景允许锁定另一侧 | 2026-08-12 |
| VR-08 | DP-08 Action Timing/Recovery | 采用Lifecycle发布的带absolute deadlines动作义务；L4以固定commit baseline、actual cumulative achievement、first executable interval及reachability certificate验证early/substantial/持续性；仅Lifecycle实际release后允许recovery，有限wrong-side transient须立即且单调可达地纠正 | 采纳(final) | 法规无通用角度/秒数；避免每solve累计清零、远期安全冒充早行动、预测past-clear冒充当前release；阈值由versioned policy提供 | 2026-08-12 |
| VR-09 | DP-09 Trackability | 采用全时域command/state语义hard check、真实active plant/controller execution-prefix envelope hard gate及full-horizon claim降级；81 state knots与80 piecewise-constant commands分离，COG/SOG不得静默映射为body heading/surge；无可信active envelope即UNKNOWN reject | 采纳(final) | reduced Mid模型可行不证明Viknes/FLSC可执行；阻止sway/frame和hold插值错位；无calibrated full tracking tube时只声明active-prefix executable与planned-trajectory safety | 2026-08-12 |
| VR-10 | DP-10 Solution Quality | V1采用advisory-only物理质量指标：control smoothness、cross-solve churn、maneuver efficiency、polyline route progress、recovery与straightness；quality不单独reject，mandatory failure仍归safety/COLREG/trackability/numerical owner | 采纳(final) | 当前无独立校准支持hard阈值；安全合规近直线不是缺陷；absolute-time/context-compatible比较避免5s/15s错位与正当新风险响应被误报 | 2026-08-12 |
| VR-11 | DP-11 Multi-target Aggregate | 采用execution tracks、Lifecycle decisions、target predictions、Assembler admissions与solver slots五集合reconciliation；按TrackKey generation形成per-target mandatory verdict并取AND生成Ship0 aggregate；primary仅展示，target-target事件保留global diagnostic但不进入Ship0 hard gate | 采纳(final) | 防止selected-only、primary-only、silent truncation和ID reuse；保留Lifecycle/Assembler冲突authority；Ship0与all-vessels scope诚实分离 | 2026-08-12 |
| VR-12 | DP-12 Fresh/Hold/Replan | fresh candidate执行完整L4；held accepted plan按原absolute timeline、当前ownship/context及到next solve的active prefix轻量重验，commands保持piecewise-constant；stale时仅允许同cycle同算法一次immediate replan，失败即fail-stop | 采纳(final) | 旧SUCCESS不能跨偏差/新目标继承；hold不伪装新solve、不签新receipt或延长validity；active/latest双时间线防止stale trajectory泄漏 | 2026-08-12 |
| VR-13 | DP-13 Failure/Commit | L4返回typed result，Adapter按稳定precedence映射现有PlanStatus/FailureSource并在总deadline/freshness复核后原子提交plan、command、receipt、warm与trace；任何最终rejection无command/no fallback、清除active authority并使Session terminal FAILED | 采纳(final) | 保持公共API兼容且保留完整failure details；防止L4前solution/event泄漏、old-plan复用和隐藏替代控制；TIMEOUT_FEASIBLE仅限完整L4且及时commit | 2026-08-12 |
| VR-14 | DP-14 Receipt/Warm Authority | 采用L4 PlanAcceptanceCertificate、Adapter atomic AcceptedPlanReceipt与neutral immutable PreviousAcceptedPlan三层contract；Assembler只据兼容receipt按absolute time生成heading/speed primal seed，tail用deterministic cold填充，strict slacks重建为0且dual禁用 | 采纳(final) | acceptance与commit事实分离且无Assembler-L4循环；warm只是数值初值，不继承安全或prefix authority；正常不兼容cold、证据损坏fail-closed、warm失败无cold retry | 2026-08-12 |
| VR-15 | DP-15 Evidence/Projection | 采用单一canonical in-memory acceptance record及hash-linked full artifact、<=8KiB inline trace、GUI/API三投影；固定Request到Commit证据链、typed witnesses与fresh/hold/replan双时间线，L4 Ship0 plan acceptance和Evaluator post-run/global evidence分源 | 采纳(final) | canonical evidence构造是mandatory authority；GUI不重算且不回退stale trajectory；full persistence异步失败不回滚command但阻断replay/capability claim | 2026-08-12 |
| VR-16 | DP-16 Runtime/Persistence | 采用20s Adapter总deadline、IPOPT reserved cutoff、完整deterministic L4、post-L4 timely/fresh commit gate及item+byte bounded async artifact sink；semantic acceptance hash与runtime dispatch attempt分离，任何预算压力不得跳mandatory layer | 采纳(final) | 相同canonical bundle保持同一L4事实，慢机器只影响dispatch；reservation须以16-target full-L4 p99校准，未校准不production-ready；persistence incomplete不回滚command但阻断claim | 2026-08-12 |
| VR-17 | DP-17 Policy/Thresholds | 采用Registry typed immutable policy与Session freeze/hash；固定80x15s、50m hard、150m advisory、<=16 relevant targets、20s、God-only V1、strict zero-slack、quantity-specific numerical tolerances；action/plant/tube/reservation由对应authority动态提供 | 采纳(final) | candidate不能自降门；frame/unit/profile变化使receipt/claim失效；禁止scenario调参/hot reload/现有PASS拟合，full-L4 reservation未校准前NOT_PRODUCTION_READY | 2026-08-12 |
| VR-18 | DP-18 Validation/Claims | 采用V1 contract、V2 independent oracles、V3 real L3-L4、V4 closed-loop Playground、V5 real 8010/UI、V6 performance/regression/capability六级promotion gates；全部通过且reservation落盘后才production/G3，claim仅限exact Ship0 tuple | 采纳(final) | 防止happy-path/mock/self-oracle/HTTP200/full-pytest假成熟；保留target-target global evidence但不污染Ship0，明确不外推MASS-L3/global/real-world | 2026-08-12 |
| VR-19 | Step5 direct adoption / DP-18 | 用户判定DP-18为低风险直接采纳项；保留Step4六级promotion gates与exact Ship0 claim，不增加DC-06 | 采纳(final) | 不改变在线算法；替代方案均明显缺真实IPOPT、独立oracle、8010或性能证据，方向一致且边界明确 | 2026-08-12 |
| VR-20 | Step5 DC-01 / TD-01 topology | 采纳方案A Independent Pure L4：L3 candidate后、Adapter atomic commit前单一pure deterministic Module；Adapter只编排fresh/hold/replan/transaction，Lifecycle/Assembler/Evaluator authority保持独立 | 采纳(final) | 唯一完整覆盖DP-01..18且支持single identity/verdict、deterministic replay、fail-closed与rejected-plan isolation的方案 | 2026-08-12 |
| VR-21 | Step5 DC-02 / numerical-safety-profile kernel | 采纳方案A：eligible termination + same-candidate original-primal hard复核、KKT advisory、all-relevant 81/80 swept conservative hull/static safety及strict/parity typed isolation | 采纳(final) | 以当前可得证据实现execution-before-acceptance；不虚构callback dual或exact rigid tube，同时覆盖selected/node/末段/profile缺口并保留versioned升级路径 | 2026-08-12 |
| VR-22 | Step5 DC-03 / COLREG-execution-multitarget | 采纳方案A：Lifecycle锁定episode/role/phase/side/action/deadlines/release，L4用固定baseline、完整trajectory和真实active-plant execution prefix验证履约；五集合reconcile后所有相关target mandatory AND，quality advisory | 采纳(final) | 阻止candidate-relative重分类/intent flicker和事后才发现错误动作；保持Lifecycle/Assembler/Evaluator authority并覆盖标准/镜像OT、Rule17与多目标 | 2026-08-12 |
| VR-23 | Step5 DC-04 / fresh-hold-receipt-warm | 采纳方案A：fresh完整L4，hold按原absolute timeline/current context重验到next solve的active prefix，stale仅同算法一次replan；Adapter在final deadline/freshness后原子commit certificate-bound receipt与warm authority | 采纳(final) | 保留5s solve成本优势，同时消除旧SUCCESS/stale command/rejected warm泄漏；hold不伪装solve、不续receipt，失败no-fallback fail-stop | 2026-08-12 |
| VR-24 | Step5 DC-05 / evidence-runtime-policy | 采纳方案A：canonical in-memory semantic acceptance record/hash + 独立dispatch/receipt record + item/byte bounded async durable artifact sink；Registry typed policy由Session freeze/hash，full/inline/GUI机械投影 | 采纳(final) | 保持20s控制路径确定性且不让慢盘改变command；persistence失败显式阻断claim，避免free-form trace/source/policy漂移 | 2026-08-12 |

### 0.7 备选/弃用方案 [ALT]

| ID | 方案 | 状态 | 原因/待验证 |
|----|------|------|---------------|
| ALT-01 | 在 `_MidMpcFacade.solve`/Adapter继续追加布尔检查 | 弃用(final) | shallow；hold/reject/evidence继续分散，无法独立replay |
| ALT-02 | 直接把现有 Evaluator 当在线 L4 authority | 弃用(final) | Planner/Evaluator形成自评耦合，且事后truth不等于预测时plan evidence |
| ALT-03 | 只要 IPOPT success + primal feasible 就接受 | 暂不采纳 | 不覆盖同步 swept safety、COLREG、trackability、quality、evidence integrity |
| ALT-04 | L4 自动修正或 fallback 到另一计划 | 排除 | 用户要求 no-fallback；属于 L5/BC-MPC，不是 Plan Acceptance |
| ALT-05 | Candidate 3 未完成时直接实现 provisional L4 schema | 排除 | 会与正在修改的 result/adapter/evidence seam 冲突并产生返工 |
| ALT-06 | Stateful acceptance controller同时拥有retry、warm、persistence与commit | 弃用(final) | 越权进入Adapter/L5，状态破坏deterministic replay并扩大failure blast radius |
| ALT-07 | 把业务acceptance放进冻结IPOPT core | 弃用(final) | 污染L3 parity并耦合COLREG/plant/runtime facts，无法覆盖hold revalidation |
| ALT-08 | 继续传`MPCSolution+algorithm_details/constraints`自由字典 | 弃用(final) | 缺raw/Lifecycle/trusted authority，已出现字段、单位与80/81时轴漂移 |
| ALT-09 | request只传artifact hash/path，由Module在线读取 | 弃用(final) | I/O失败/延迟进入control authority path，破坏纯函数与offline-equivalent evaluate |
| ALT-10 | candidate同时提供acceptance policy并自证满足 | 弃用(final) | producer可静默降低50m/profile/tolerance，破坏trusted authority分离 |
| ALT-11 | 直接宣称当前`json.dumps(sort_keys)`为RFC 8785/JCS | 弃用(final) | number serialization不等价；采用versioned schema-specific normalization且不虚称JCS |
| ALT-12 | 只返回`accepted: bool, reason: str` | 弃用(final) | 丢失UNKNOWN/N/A、多target、多layer、warm/retry与evidence语义 |
| ALT-13 | 把所有layer压成一个加权score | 弃用(final) | hard safety/COLREG可被其他分数抵消且单位无共同标尺 |
| ALT-14 | 第一个layer失败即抛domain exception | 弃用(final) | 丢失其他独立失败，evaluation order影响可观察结果 |
| ALT-15 | V1把quality单独设为hard reject | 弃用(final) | 无独立阈值证据，会拒绝安全直线或保守计划 |
| ALT-16 | 只信Ipopt status或`success=true` | 弃用(final) | 漏original bounds、strict slack、NaN、candidate错配与scaled/internal semantics |
| ALT-17 | V1强制KKT/stationarity hard gate | 弃用(final) | callback incumbent无同点multipliers，80x15s residual阈值未校准，会无依据误拒 |
| ALT-18 | 所有slack/violation必须精确为零 | 弃用(final) | Ipopt存在浮点边界噪声；semantic strict仍零容忍，但solution复核需quantity-specific数值容差 |
| ALT-19 | 所有变量/row统一使用`1e-3` | 弃用(final) | rad、m/s、m、m2无共同物理尺度，可能同时过松与过严 |
| ALT-20 | L4重求一次NLP作为验证 | 弃用(final) | 不是独立oracle，增加deadline与非确定性，违反single-candidate acceptance |
| ALT-21 | 只检查solver selected targets | 弃用(final) | candidate admission可漏碰撞目标，形成自证 |
| ALT-22 | 只检查81个node center CPA | 弃用(final) | 漏15s区间穿越、双方footprint和terminal interval |
| ALT-23 | 复用Evaluator clearance/collision verdict或helper | 弃用(final) | Planner自评及共享缺陷；事后actual truth不等于预测plan acceptance |
| ALT-24 | V1直接以oriented rectangle/C2A作为唯一hard gate | 弃用(final) | 需可信姿态/旋转sweep与更复杂独立oracle，首版runtime和误差风险更高 |
| ALT-25 | 将当前CV covariance朴素传播到1200s | 弃用(final) | 未校准margin可达数十km，不具production可用性 |
| ALT-26 | static hazard永久排除L4 | 弃用(final) | chart-backed profile可能下发grounding plan，无法支持static-safety claim |
| ALT-27 | target-target碰撞进入Ship0 hard aggregate | 弃用(final) | Ship0 Mid-MPC无权控制脚本目标船，混淆scope并造成固有场景失败 |
| ALT-28 | 直接信任solver CPA摘要或Assembler effective center floor | 弃用(final) | 只覆盖selected/不完整区间，且包含frozen-index工程补偿，不能证明物理同步船体净距 |
| ALT-29 | parity与strict各维护一套L4 checker | 弃用(final) | safety/COLREG逻辑会漂移，修复与验证需双维护 |
| ALT-30 | 只检查`profile_name`或algorithm id字符串 | 弃用(final) | 可伪造标签，不能证明actual bounds/options/slacks |
| ALT-31 | strict拒绝后自动回退MASS parity | 弃用(final) | 违反production safety、no-fallback和profile claim边界 |
| ALT-32 | strict production要求与8条MASS fixture逐元素一致 | 弃用(final) | strict preparation语义不同；把port fidelity误作production gate |
| ALT-33 | 修改旧parity fixture/expected以符合strict | 弃用(final) | 销毁冻结上游oracle与迁移可追溯性 |
| ALT-34 | artifact/GUI只显示`Mid-MPC`并隐藏profile/eligibility | 弃用(final) | 用户无法辨认parity diagnostic与production strict执行身份 |
| ALT-35 | L4按candidate终态或每个knot重新分类COLREG | 弃用(final) | candidate动作改变几何后会丢失原责任并重现intent flicker |
| ALT-36 | L4为所有OT硬编码starboard-only | 弃用(final) | 把标准Playground偏好冒充Rule13通用法律常数，错误拒绝锁定port/受限情形 |
| ALT-37 | 只检查first command方向 | 弃用(final) | 可先正确微转后回切、cross ahead或未past-clear |
| ALT-38 | 只检查final CPA或最终passing point | 弃用(final) | 漏动作时机、过程中wrong-side与责任连续性 |
| ALT-39 | 复用Evaluator COLREG FSM/classifier | 弃用(final) | Planner自评且基于不同时间/actual state，可能共享缺陷或重分类 |
| ALT-40 | L4重新解决multi-target maneuver conflict | 弃用(final) | 越权成为Lifecycle/Assembler/Planner并违反pure acceptance与no modification |
| ALT-41 | L4统一硬编码`5deg/30deg/60s`动作门 | 弃用(final) | 法规无通用数值，跨速度、距离与plant不成立 |
| ALT-42 | 只要1200s horizon最终安全即视为early | 弃用(final) | 允许临近碰撞才行动，违反ample-time/early语义 |
| ALT-43 | 每次solve相对当前艏向重算minimum alteration | 弃用(final) | 小步动作每周期清零，无法证明累计substantial或识别反复 |
| ALT-44 | 初始wrong-side一律立即reject | 弃用(final) | 拒绝立即、单调且deadline内可恢复的安全计划 |
| ALT-45 | wrong-side只看horizon终点已恢复 | 弃用(final) | 允许先恶化、迟纠正或中途不安全 |
| ALT-46 | candidate预测past-clear后立即允许route recovery | 弃用(final) | 把未来计划事实冒充当前Lifecycle release authority |
| ALT-47 | L4自行推进phase或签发release | 弃用(final) | 形成第二Lifecycle与双authority，破坏pure stateless acceptance |
| ALT-48 | 缺deadline/reachability时从1200s horizon推断可用时间 | 弃用(final) | horizon长度不证明及时可达，必须UNKNOWN fail-closed |
| ALT-49 | 只复核Mid NLP自身ROT/decel bounds | 弃用(final) | 仅证明reduced model，不证明Viknes/FLSC/controller可执行 |
| ALT-50 | 用静态`published_kinematic_csog`代替真实active plant | 弃用(final) | 与标准场景实际plant不一致，制造虚假trackability claim |
| ALT-51 | 无tracking tube时要求完整1200s plant-hard trackability | 弃用(final) | 当前无oracle/certificate，会无依据拒绝全部production计划 |
| ALT-52 | 完全跳过trackability并等待Evaluator事后发现 | 弃用(final) | 不可执行reference可能先被下发，违背plan acceptance目的 |
| ALT-53 | L4内运行Viknes/FLSC闭环仿真 | 弃用(final) | 复制runtime/controller并扩大deadline/非确定性，仍缺独立模型误差证明 |
| ALT-54 | 对81 state knots和80 commands统一线性插值 | 弃用(final) | 改变piecewise-constant控制语义，复现已知hold command错误 |
| ALT-55 | 将COG/SOG静默映射为heading/surge | 弃用(final) | sway/current存在时物理错误，复现已知偏差 |
| ALT-56 | 缺active capability字段时按无限能力放行 | 弃用(final) | 缺证据不是无限包络，必须UNKNOWN fail-closed |
| ALT-57 | 所有quality metric超过经验阈值即hard reject | 弃用(final) | 无独立校准，可能拒绝安全直线、STOP或保守避让 |
| ALT-58 | raw NLP objective作为唯一quality score | 弃用(final) | 跨target/cycle/reference不可比且权重单位混合 |
| ALT-59 | 预测轨迹必须具有明显曲率 | 弃用(final) | route-only或稳定避让的真实最优解可以是直线 |
| ALT-60 | 只评估单cycle candidate，不比较previous accepted plan | 弃用(final) | 无法发现solve-to-solve churn、回切和恢复振荡 |
| ALT-61 | 无条件比较相邻solve plans | 弃用(final) | 新目标、phase或route变化会把正当响应误报为抖动 |
| ALT-62 | 将quality WARN加入加权overall score | 弃用(final) | 可能抵消或遮蔽hard obligations，破坏layered verdict |
| ALT-63 | route quality继续使用单bearing无限直线 | 弃用(final) | 弯曲route的progress/rejoin语义错误 |
| ALT-64 | 只检查primary或earliest-risk target | 弃用(final) | 漏其他目标的安全与COLREG义务 |
| ALT-65 | 只检查solver selected最多16个targets | 弃用(final) | 形成admission自证并漏unselected危险目标 |
| ALT-66 | 每目标结果压成minimum clearance加一个global bool | 弃用(final) | 丢失role、wrong-side、past-clear、identity与failure provenance |
| ALT-67 | 对per-target score求平均或加权 | 弃用(final) | 一个目标的hard failure可被其他目标高分抵消 |
| ALT-68 | L4对冲突directive投票或选择最危险目标 | 弃用(final) | 越权重做Lifecycle/Assembler决策并牺牲其他义务 |
| ALT-69 | 所有target-target事件进入Ship0 hard aggregate | 弃用(final) | Ship0无控制authority，固有脚本碰撞会错误否决Ship0计划 |
| ALT-70 | 超capacity时截断低风险目标 | 弃用(final) | 被截断目标可能是真实危险且claim不完整 |
| ALT-71 | 使用裸target ID而不带generation | 弃用(final) | ID复用后receipt、prediction与Lifecycle可能串入旧目标 |
| ALT-72 | 未selected目标一律视为trusted exclusion | 弃用(final) | solver admission不是安全排除理由，仍需完整safety evidence |
| ALT-73 | hold直接继承旧SUCCESS直到下次solve | 弃用(final) | 已实证可跨大偏差、新目标和stale context泄漏 |
| ALT-74 | 每个hold tick重做完整IPOPT与full L4 | 弃用(final) | 实质取消hold并增加deadline/算力，改变调度契约 |
| ALT-75 | hold只检查ownship deviation | 弃用(final) | 漏新目标、target maneuver、Lifecycle/policy/plant变化与prefix safety |
| ALT-76 | 将旧trajectory时间轴平移到`now` | 弃用(final) | 改写计划语义并伪造support/provenance |
| ALT-77 | hold线性插值interval commands | 弃用(final) | 改变真实piecewise-constant执行语义 |
| ALT-78 | stale后无限次same-cycle replan或warm-to-cold retry | 弃用(final) | 可能超deadline、非确定且违反一次尝试/no-fallback边界 |
| ALT-79 | hold失败后继续上一command等待下一周期 | 弃用(final) | 已无当前安全许可，属于未声明fallback |
| ALT-80 | hold PASS签新full receipt并延长validity | 弃用(final) | 用短prefix验证无限续期，破坏acceptance/warm authority |
| ALT-81 | solver未执行的hold显示新IPOPT success/solve id | 弃用(final) | 制造虚假求解证据并混淆active plan与latest attempt |
| ALT-82 | 为每个L4 failure新增一个`PlanStatus`枚举 | 弃用(final) | 破坏公共兼容、造成枚举爆炸且仍无法表达并发失败 |
| ALT-83 | 所有L4 rejection统一映射`INFEASIBLE` | 弃用(final) | 丢失input/numerical/dependency/timeout owner与恢复语义 |
| ALT-84 | 第一个失败立即抛异常且不生成完整result | 弃用(final) | 丢失并发failure、hash、GUI与replay evidence |
| ALT-85 | L4前先保存solution，失败后再rollback | 弃用(final) | exception/event/并发可泄漏rejected plan且rollback难保证完整 |
| ALT-86 | rejection后继续previous accepted plan | 弃用(final) | 无当前许可，违反no-fallback与fresh rejection边界 |
| ALT-87 | rejection后输出零速或保持舵命令 | 弃用(final) | 未经L4验证的替代控制，属于隐藏fallback且可能更危险 |
| ALT-88 | fresh rejection自动warm/cold retry | 弃用(final) | 扩大deadline和非确定性，绕过一次candidate裁决 |
| ALT-89 | artifact持久化失败时回滚已下发command | 弃用(final) | 磁盘状态反向改变控制决定并造成时序不一致 |
| ALT-90 | 总deadline已过仍以`TIMEOUT_FEASIBLE`下发 | 弃用(final) | native solver feasibility不能替代全链路时效与freshness |
| ALT-91 | 只要solver success就保存`previous_x` | 弃用(final) | 会混入L4拒绝、parity、旧epoch和不兼容目标 |
| ALT-92 | L4直接生成`SeedPlan`并调用Assembler | 弃用(final) | 形成反向依赖并侵入L1/L2数值初始化authority |
| ALT-93 | Assembler读取Adapter/L4全局last solution | 弃用(final) | 隐式状态、不可重放且受reset/并发污染 |
| ALT-94 | 旧raw x整体shift一个stage | 弃用(final) | 5s/15s错10s，angle/target/capability未对齐 |
| ALT-95 | V1启用primal+dual完整warm start | 弃用(final) | dual绑定row order/active bounds，缺稳定same-point证据和benchmark |
| ALT-96 | warm failure后自动cold retry | 弃用(final) | 超deadline、非确定并违反一次candidate/fail-stop边界 |
| ALT-97 | hold validation每tick签新receipt | 弃用(final) | 用短prefix复核无限续期并混淆fresh authority |
| ALT-98 | receipt不兼容或损坏均静默cold | 弃用(final) | 会隐藏篡改与identity corruption；损坏必须fail-closed |
| ALT-99 | 将previous accepted plan作为prefix equality | 弃用(final) | warm建议可撤销，不是execution acknowledgement，会错误冻结旧episode/side |
| ALT-100 | 继续扩展free-form `algorithm_details` dict | 弃用(final) | 字段、单位、大小和命名漂移，无法可靠hash/replay |
| ALT-101 | 将全部raw vectors塞入PlannerTrace/HTTP | 弃用(final) | payload失控并阻塞UI/网络，混淆authority职责 |
| ALT-102 | trace只保存artifact path并在线读取 | 弃用(final) | disk I/O进入控制/GUI路径，文件缺失即不可解释 |
| ALT-103 | GUI从raw solver fields重算acceptance | 弃用(final) | GUI成为第二checker并可能与L4分歧 |
| ALT-104 | acceptance hash包含elapsed/path/queue/wall time | 弃用(final) | 相同物理输入产生不同hash，破坏determinism |
| ALT-105 | 同步写盘成功后才允许command commit | 弃用(final) | 慢盘或失败改变控制时序，违反in-memory authority |
| ALT-106 | rejected attempt覆盖active plan trajectory | 弃用(final) | 用户会把不可执行candidate误认当前命令来源 |
| ALT-107 | 使用同一`PASS`标签混合L4与Evaluator | 弃用(final) | 混淆预测计划接受、Ship0事后安全与global结果 |
| ALT-108 | inline超8KiB时静默删除targets/failures | 弃用(final) | 可能隐藏hard failure；必须保留计数、hash与canonical全量 |
| ALT-109 | 保留target trajectory `x/y`与`north/east`双协议 | 弃用(final) | 已造成Mid目标预测静默丢失，必须统一typed ENU schema |
| ALT-110 | IPOPT独占20s后再无限时运行L4 | 弃用(final) | candidate可能过总deadline或stale仍被下发 |
| ALT-111 | 为每layer设soft timeout并跳过后继续ACCEPT | 弃用(final) | partial evidence被伪装为完整安全结论 |
| ALT-112 | L4读取clock并按剩余时间改变target/layer scope | 弃用(final) | 相同bundle verdict不确定且可能漏hard failure |
| ALT-113 | 按4.89ms geometry p95直接设10ms完整L4预算 | 弃用(final) | 证据不含COLREG/trackability/hash/static，欠校准 |
| ALT-114 | 同步完整artifact写盘后才commit | 弃用(final) | 慢盘改变控制deadline并阻塞安全plan |
| ALT-115 | 使用unbounded artifact queue | 弃用(final) | 内存无界、延迟积压和crash风险 |
| ALT-116 | queue满时阻塞control thread | 弃用(final) | I/O backpressure改变command时效 |
| ALT-117 | queue满时覆盖最旧未完成artifact | 弃用(final) | 破坏既有evidence承诺且不可审计 |
| ALT-118 | wall timing进入semantic acceptance hash | 弃用(final) | 同一物理输入无法byte-identical replay |
| ALT-119 | 超总deadline仍提交semantic ACCEPT | 弃用(final) | 忽视snapshot staleness和20s public contract |
| ALT-120 | 让`mid_mpc_ipopt.yaml`同时定义Lifecycle/L3/L4/Evaluator authority | 弃用(final) | producer可自降门且多authority静默漂移 |
| ALT-121 | candidate自报threshold并由L4验证其自报值 | 弃用(final) | candidate可把50m改30m后自证通过 |
| ALT-122 | 所有量统一`1e-3` tolerance | 弃用(final) | rad/m/s/m/m2无共同尺度，会同时过松与过严 |
| ALT-123 | 物理50m门使用`50m-numeric epsilon`放行 | 弃用(final) | 实质降低hard safety requirement |
| ALT-124 | 将150m preferred clearance升级为hard | 弃用(final) | 改变ODD语义并可能无共同可行解，当前只支持objective偏好 |
| ALT-125 | 按scenario/seed/target id设置不同阈值 | 弃用(final) | 场景作弊且无法形成通用capability claim |
| ALT-126 | 用现有五个PASS场景拟合action/quality阈值 | 弃用(final) | 数据泄漏，无法证明边界或泛化 |
| ALT-127 | 运行中hot reload acceptance policy | 弃用(final) | 同session receipt/verdict authority变化且不可重放 |
| ALT-128 | policy变化后继续复用旧receipt/G3 claim | 弃用(final) | dependency已变，旧证据不再证明新contract |
| ALT-129 | full-L4 reservation未校准时设0并production启用 | 弃用(final) | IPOPT可能耗尽20s并使L4/commit过时 |
| ALT-130 | 只给现有HO/CS/OT测试加`accepted=true` | 弃用(final) | 不能证明checker能拒绝缺陷、hold/hash/UI/performance正确 |
| ALT-131 | 所有layer测试复用production helper计算expected | 弃用(final) | production与oracle共享同一bug，形成自证 |
| ALT-132 | 只跑mock solver或unit tests | 弃用(final) | 不证明真实CasADi/IPOPT、prepared evidence与deadline链 |
| ALT-133 | 只跑full pytest | 弃用(final) | 回归通过不证明L4负例、性能或8010真实执行 |
| ALT-134 | HTTP 200或页面可打开即算8010通过 | 弃用(final) | 不证明正确listener、solver、L4、command、artifact或GUI数据 |
| ALT-135 | 先升G3再补artifact/performance | 弃用(final) | claim无完整证据且reservation仍UNSET |
| ALT-136 | 按现有PASS结果修改threshold直到全绿 | 弃用(final) | 数据泄漏和场景作弊，破坏50m与independent acceptance |
| ALT-137 | target-target collision存在则multiship整体失败 | 弃用(final) | 超出Ship0 control authority并与确认scope冲突 |
| ALT-138 | 一次warm-cache performance run作为p99 | 弃用(final) | 无统计意义，掩盖cold/hold/rejected/worst-case |
| ALT-139 | 用Colav结果宣称MASS-L3 system acceptance | 弃用(final) | 未验证ROS2/GNC/M7/SIL及真实部署链 |
| ALT-140 | 任一scenario通过后外推所有seed/plant/tracker | 弃用(final) | capability证据只支持绑定的exact dependency tuple |
| ALT-141 | Step5 DC-01方案B：Stateful Adapter Acceptance Controller | 弃用(final) | 调度、裁决、receipt、warm、retry、persistence集中为mutable巨类；当前hold/exception已有状态泄漏反证，replay与组合测试复杂 |
| ALT-142 | Step5 DC-01方案C：Distributed solver/facade/Adapter/Evaluator gates | 弃用(final) | 无单一identity/aggregate/transaction authority；局部PASS无法形成执行前完整plan acceptance证明 |
| ALT-143 | Step5 DC-02方案B：KKT-hard + Exact Rigid Geometry | 弃用(final) | callback/timeout缺同点dual，目标姿态/continuous rigid sweep/tracking tube与p99证据未就绪，会无依据普遍fail-stop |
| ALT-144 | Step5 DC-02方案C：Solver-native + Post-run Gate | 弃用(final) | Ipopt status/node CPA/事后Evaluator无法阻止selected-only、区间、末段、footprint或伪strict缺陷先下发 |
| ALT-145 | Step5 DC-03方案B：Candidate-relative Reclassification + Full-horizon Rules | 弃用(final) | candidate动作会反向改变自身分类并解除原责任，重现intent flicker；每solve baseline重置且reduced horizon不等于真实plant能力 |
| ALT-146 | Step5 DC-03方案C：Safety-only Online + Post-run COLREG | 弃用(final) | wrong-side、迟行动、Rule17或不可跟踪command会先下发，Evaluator只能事后报告 |
| ALT-147 | Step5 DC-04方案B：Every-tick Fresh Solve | 弃用(final) | 当前16-target约2s且未含完整L4，无法证明满足更快tick；高频非凸candidate、deadline、artifact与CPU压力过高 |
| ALT-148 | Step5 DC-04方案C：Last-plan Continuation + Fallback | 弃用(final) | 直接保留100m偏差继承SUCCESS、旧trace/command、rollback和warm/fallback authority混淆等已证实缺陷 |
| ALT-149 | Step5 DC-05方案B：Synchronous Event-sourced Durable Commit | 弃用(final) | WAL/fsync/store/reducer/migration成为20s控制关键依赖；项目无现成基础且磁盘故障会阻断semantic-safe candidate |
| ALT-150 | Step5 DC-05方案C：Lightweight Trace + Best-effort Logs | 弃用(final) | 无canonical parent chain/replay/policy invalidation，继续暴露field mismatch、stale GUI与claim无法绑定exact decision的问题 |

### 0.8 技术规约注册表 [TS]

| ID | 类别 | 冻结规约 | 来源/理由 | 关联DP/接口 | 与现状差异/修正 |
|----|------|----------|-----------|-------------|---------------|
| TS-01 | 接口 | 唯一入口为pure/stateless/deterministic `evaluate(request)->result`；位于L3 candidate之后、Adapter原子commit之前 | DESIGN_DECISION；R1..R7 | DP-01；L3→L4→Adapter | 新增独立L4 seam；不得塞回facade/adapter |
| TS-02 | 接口 | request使用`candidate/authority/execution/prior`四个immutable命名空间；每个对象versioned | DESIGN_DECISION；R4/R25/R58 | DP-02/14/15 | 替代读取mutable facade/free-form details |
| TS-03 | 坐标系 | world统一ENU：north/east以m；body明确x-forward/y-port；转换只能由具名边界完成 | PROJECT_FACT+DESIGN_DECISION；R4/R46 | DP-02/09/17 | 禁止NED/ENU与body/world静默混用 |
| TS-04 | 符号 | course/heading以rad；0=北，顺时针为正；相对角先wrap到`[-pi,pi)`；右转为正 | PROJECT_FACT；R4/R46 | DP-02/07/09/17 | 禁止degree与普通角/航向混用 |
| TS-05 | 单位 | 速度m/s、加速度m/s²、角速度rad/s、时间s、线性距离m、CPA row为m² | PROJECT_FACT；R4/R20/R79 | DP-04/05/09/17 | UI可显示deg，但canonical contract不变 |
| TS-06 | 时序 | sim-time为语义时钟；wall-time仅runtime telemetry；所有plan/prediction/receipt用absolute sim-time绑定 | DESIGN_DECISION；R34/R52/R58 | DP-02/08/12/15/16 | 替代只按`last_solve_time`年龄判断hold |
| TS-07 | 网格 | production plan固定80 intervals×15s=1200s、81 state knots；command在每区间piecewise-constant | frozen upstream+Candidate3；R1/R4/R46 | DP-02/05/09/17 | 明确state/command off-by-one语义 |
| TS-08 | 轨迹 | canonical candidate为地固COG/SOG reference；body `psi/u/v/r`为执行状态，不得互相冒充 | PROJECT_FACT+DESIGN_DECISION；R46 | DP-09/17 | 修正当前显示/执行语义混合风险 |
| TS-09 | 身份 | `TrackKey=(session_epoch,target_id,generation)`；同cycle/profile/policy/preparation/options必须由parent hashes闭合 | DESIGN_DECISION；R25/R57/R58 | DP-02/11/15 | 替代裸target id和松散trace关联 |
| TS-10 | canonical | semantic bytes采用versioned schema-specific canonicalization；不宣称RFC 8785/JCS兼容 | DESIGN_DECISION；R58/R63 | DP-02/15/17 | 新增确定性字段排序/数值编码测试 |
| TS-11 | 容量 | 所有fresh/usable/relevant contacts都必须进入reconciliation；上限16，超限拒绝，不截断 | frozen L3+DESIGN_DECISION；R25/R31 | DP-05/11/17 | 替代risk排序后静默丢弃相关目标 |
| TS-12 | verdict | layer=`integrity/numerical/safety/COLREG/trackability/quality/evidence`；outcome=`PASS/FAIL/WARN/UNKNOWN/N/A/NOT_EVALUATED` | DESIGN_DECISION；R7/R55 | DP-03/13 | 替代单bool/last-error-wins |
| TS-13 | 聚合 | mandatory层fail-closed；UNKNOWN/NOT_EVALUATED仅在policy显式允许的advisory项可继续；quality V1 advisory | DESIGN_DECISION；R7/R55 | DP-03/10/13 | public status只做稳定投影，不丢完整failure list |
| TS-14 | 数值 | 仅eligible IPOPT termination可进入；在同一raw candidate上复核finite、原始`x/g` bounds、strict preparation/options、objective consistency | IPOPT docs+PROJECT_FACT；R15..R21 | DP-04/06 | 扩展当前status+uniform primal tolerance |
| TS-15 | 容差 | identity=0；heading/ROT/min-alt abs1e-6 rel1e-10；speed/accel/decel abs1e-6 rel1e-10；position/direction abs1e-4 rel1e-10；CPA m² abs1e-4 rel1e-10；fixed-zero slack abs1e-7 rel0；objective abs1e-8 rel1e-10 | DESIGN_DECISION；R20/R79 | DP-04/17 | 替代solver统一1e-3；production前需边界corpus |
| TS-16 | KKT | V1 KKT仅advisory；缺同点multipliers时`NOT_EVALUATED+WARN`，不得伪造或用别点乘子 | IPOPT docs；R15..R21 | DP-04 | callback incumbent不足以作同点KKT hard proof |
| TS-17 | profile | `MASS_PARITY`恒为`DIAGNOSTIC_ONLY`，不得产command/receipt/warm；production仅`COLAV_STRICT` | DESIGN_DECISION；R1/R19/R22 | DP-06/14/17 | 将数值复现与生产接受隔离 |
| TS-18 | slack | strict production要求hard/slack policy与prepared proof一致；V1 fixed strict slacks为零容差规约；观测到实质非零即拒绝 | DESIGN_DECISION；R20/R22 | DP-04/06/17 | 不再用场景PASS掩盖soft slack |
| TS-19 | 动态安全 | 对81 knots/80同步区间做解析相对线段最小值；`clearance_lb=center_min-own_radius-target_radius-trusted_uncertainty` | geometry+PROJECT_FACT；R8..R14 | DP-05 | 替代仅node/selected target/point-center CPA |
| TS-20 | 安全门 | 物理hard hull clearance为50m，不减epsilon；150m仅advisory；每目标输出interval/time/positions/clearance witness | DESIGN_DECISION；R8/R14/R79 | DP-05/11/15/17 | 禁止降门、场景特判或只看primary target |
| TS-21 | 不确定性 | God profile uncertainty=0；非God必须提供校准、逐时刻、可信envelope，否则production拒绝 | risk literature+DESIGN_DECISION；R10/R14 | DP-05/17/18 | V1 production scope限God |
| TS-22 | 静态安全 | chart-backed profile下static hazard clearance为mandatory hard；context缺失/过期拒绝 | DESIGN_DECISION；R14/R40 | DP-05/17 | 不能只证明ship-ship安全 |
| TS-23 | 规则权威 | Lifecycle是role/side/phase/commit/release唯一authority；L4不重分类、不选边、不推进phase、不仲裁冲突 | Candidate2 accepted design；R22..R33 | DP-07/08/11 | 消除第二COLREG FSM |
| TS-24 | 规则谓词 | HO验证port-to-port；CS give-way验证pass-astern；OT验证locked corridor；stand-on/Rule17验证冻结动作合同 | COLREG+DESIGN_DECISION；R22..R33 | DP-07/08 | 标准OT默认右舷；受限/镜像可由Lifecycle锁定左舷 |
| TS-25 | 动作时序 | action contract必须含commit baseline、start/achievement deadlines、actual cumulative achievement、reachability certificate；first executable interval检查early action | DESIGN_DECISION；R28/R34/R38 | DP-07/08/09 | 仅“最终预测转够”不算及时行动 |
| TS-26 | 释放 | predicted past-and-clear不能授权当前release；仅消费Lifecycle当前permission；恢复检查route/speed progress | COLREG+DESIGN_DECISION；R28/R39 | DP-07/08/10 | L4不自行提前结束encounter |
| TS-27 | 可执行性 | production hard gate绑定exact tuple的真实active plant/controller capability；单船HO/CS/OT绑定Viknes+FLSC，现有multiship仅绑定KinematicCSOG+pass-through且不得冒充Viknes证据 | PROJECT_FACT+USER_RULING；R40..R46 | DP-09/18 | 未接入当前tuple真实plant envelope前NOT_PRODUCTION_READY |
| TS-28 | claim窗口 | active-prefix reachability为hard；无full tracking tube时只声明active-prefix executable与planned safety，不声明1200s可跟踪 | DESIGN_DECISION；R40/R45 | DP-09/18 | 避免把reference polyline当闭环保证 |
| TS-29 | 质量 | V1 advisory检查smoothness、cross-solve churn、efficiency、全polyline progress、recovery、straightness信息；安全直线允许 | DESIGN_DECISION；R47..R51 | DP-10 | raw objective不作为跨周期质量分数 |
| TS-30 | 多目标 | execution tracks、Lifecycle decisions、predictions、Assembler admission/bindings、solver slots必须一一reconcile；per-TrackKey mandatory AND | DESIGN_DECISION；R25/R31 | DP-11 | primary target只用于显示；target-target碰撞仅global diagnostic |
| TS-31 | fresh/hold | fresh执行完整L4；hold按原absolute timeline从current state/context重验active prefix，不续期receipt | DESIGN_DECISION；R52..R62 | DP-12/14 | 不再继承旧SUCCESS/旧轨迹 |
| TS-32 | replan | hold stale且本tick尚未求解、预算允许时，仅一次同算法immediate replan；仍拒绝则fail-stop | DESIGN_DECISION；R52/R60 | DP-12/13/16 | 禁止fallback/cold retry循环 |
| TS-33 | failure | 最终拒绝无command、无fallback；清active plan/receipt/warm eligibility；Session`RUNNING→FAILED`；保留typed原因 | DESIGN_DECISION；R54/R55 | DP-13/14 | 统一异常/post-validation失败路径 |
| TS-34 | commit | L4通过后再做总deadline/freshness检查；Adapter一次原子写入solution、active plan、receipt、warm、event | DESIGN_DECISION；R54/R58 | DP-13/14/16 | 禁止部分字段先可见 |
| TS-35 | warm | receipt兼容时只重采样absolute-time heading/speed primal，tail cold，strict slack重建零，dual关闭；warm失败不cold retry | DESIGN_DECISION；R56/R57 | DP-14 | rejected/parity/reset/profile-mismatch均无warm authority |
| TS-36 | evidence | hash chain=`Request→Problem→Prepared→Candidate→Acceptance→Receipt`；semantic acceptance与dispatch/persistence分记录 | DESIGN_DECISION；R58..R68 | DP-02/15/16 | 新增canonical source of truth |
| TS-37 | 投影 | full artifact、<=8192-byte inline、GUI均由同一canonical record机械投影；active/latest attempt双时间线；字段统一north/east | PROJECT_FACT+DESIGN_DECISION；R59/R63 | DP-15/17 | 修复旧trace回退、target x/y mismatch、source混淆 |
| TS-38 | deadline | 总20s覆盖Assembly→Preparation→IPOPT→L4→final freshness→atomic commit；solver使用预留cutoff | DESIGN_DECISION；R60/R73 | DP-16/17 | full-L4 p99 reservation未校准时NOT_PRODUCTION_READY |
| TS-39 | 持久化 | artifact默认max16MiB；bounded queue=32 items/64MiB；shutdown drain=2s；retention=256；async sink失败不回写semantic verdict但阻断claim | DESIGN_DECISION；R64/R67/R68 | DP-15/16/17 | 新增bounded backpressure状态机 |
| TS-40 | policy | Registry持有typed immutable policy，Session启动时freeze/hash；V1固定N80/dt15/50m/150m/max16/20s/inline8192/God-only/strict-zero-slack/dual-off | DESIGN_DECISION；R69/R74/R79 | DP-17 | 替代分散YAML/free-form参数 |
| TS-41 | promotion | V1..V6依次为pure contract、independent oracles、real L3/IPOPT、closed-loop、real8010/UI、performance/full regression/exact tuple；任一缺失不晋级 | DESIGN_DECISION；R69..R81 | DP-18 | 不以focused tests或GUI可见代替完整claim |
| TS-42 | claim | 只声明exact tuple下Ship0安全/规则/执行证据；不声明global all-vessel、非God、任意plant、global optimum、法律/实船或MASS-L3 SIL/GNC/M7接受 | DESIGN_DECISION；R69/R77/R81 | DP-11/18 | 保留目标船互撞为显式out-of-scope evidence |

### 0.9 依赖与并行注册表 [SYNC]

| ID | 上游事实 | 当前状态 | 本设计动作 | 实现 Gate |
|----|----------|----------|------------|-----------|
| SYNC-01 | Candidate 2 Lifecycle 为 role/side/phase/commit/release 唯一 authority | 已冻结并合并 | 只消费 immutable snapshot；不重分类 | 无 |
| SYNC-02 | Candidate 3 public 81-state grid、prediction、safety plan、strict/parity profile | 已实现并推送`marine/main@1f459d8` | Step1..6按已实现contract设计；L4实现前先集成到目标branch | Candidate 3 integration commit |
| SYNC-03 | Candidate 3 evidence chain `Problem→Preparation→Prepared→RawSolver→Acceptance` | 前四段已冻结；Acceptance仍由本设计定义 | L4只追加Acceptance link，不反向修改Assembler authority | L4 schema/hash contract frozen |
| SYNC-04 | private NumericalPreparer 与 original-bound recheck | 已实现 | 不复制numerical layout；L4消费具名solver evidence | L3 readiness tests green |
| SYNC-05 | accepted-plan warm start | v1 disabled | L4 设计 eligibility token；不提前启用 seed | L4 accepted-plan handoff tests green |
| SYNC-06 | production code surfaces | Candidate 3 worktree clean；目标本地`main`尚未集成其提交 | 本分支只写docs；不cherry-pick、不改共享生产文件 | Candidate 3 integrated into implementation base |

## 1. Step1 范围与问题框架

### 1.1 直接结论

- **可并行**：Candidate 1 完整设计 Step1..6 可在独立 docs worktree 进行。
- **不可并行实现**：Candidate 3 正在修改 L4 必须消费的 result、solver、adapter、persistence/evidence seam。提前编码会固化 provisional schema。
- **实现前硬 Gate**：Candidate 3 合并后的 commit；Assembler/Core/Adapter contract tests；`MASS_PARITY` oracle；`COLAV_STRICT` original-bound/slack/swept witness；81-state/hash-chain replay；工作树 clean。
- **无算法研究阻碍**：L4 不修改 frozen L3 方程，不需要等待新 solver backend，也不要求先让轨迹变弯。

### 1.2 当前能力缺口

1. L3 `CONVERGED` 仅由 IPOPT return status 与 raw row primal recheck决定。
2. Facade 对 `CONVERGED` 无条件映射 `PlanStatus.SUCCESS/feasible=true`。
3. core continuous CPA 是诊断值，不参与 public plan acceptance；现状还是 point-center，不是同步 footprint hull witness。
4. Adapter 验证 shape、首状态、运动连续性、deadline、status/feasible 一致性；不验证 COLREG、hull safety、trackability envelope 或 quality。
5. Evaluator 有独立 Ship0 hard gate，但属于事后场景评价，不能替代每次控制下发前的 plan acceptance。
6. hold frame 沿用旧 solution 的 status/feasible，未重新证明当前时间切片仍可接受。

### 1.3 本轮 Scope

**In**

- 独立、可 replay、无状态的 L4 Plan Acceptance Module 设计。
- L4.1 数值收敛/原始可行性、L4.2 同步连续安全、L4.3 COLREG consistency、L4.4 trackability、L4.5 quality。
- fresh/hold 两类时序、multi-target、typed verdict、no-fallback failure、accepted-plan eligibility、evidence/hash/GUI source。
- 与 Candidate 2/3 的单向依赖、接口最小化、验证矩阵和实现 Gate。

**Out**

- 不改 L3 IPOPT 方程、objective、row layout、solver backend。
- 不改 Candidate 2 Lifecycle role/side/commit/release decision。
- 不设计 L5 BC-MPC/MRM/fallback/control arbitration。
- 不用在线 L4 自动修轨迹；拒绝后 fail-stop/retry 语义另行明确。
- 不把 target-target 脚本碰撞算作 Ship0 Mid-MPC failure。
- 不以“让所有场景 PASS”为理由改 scenario、降低 50m、按场景 ID 分支或复制 Evaluator authority。

### 1.4 Step1 完成条件

- DP-01..18 覆盖架构、接口、数学安全、COLREG、执行、质量、时序、失败、证据、性能、配置、测试。
- TD-01 的每个子问题均映射到至少一个 DP。
- SC-01..12 覆盖正常、对抗、fresh/hold、single/multi、parity/strict 与 evidence failure。
- 并行工作仅限 docs；实现 Gate 明确，不与 Candidate 3 共享代码修改。
- 用户确认决策点完整后进入 Step2 deep research。

## 参考

- [R1] `colav_simulator/core/colav/mid_mpc/solver.py`
- [R2] `colav_simulator/integrations/mid_mpc_ipopt.py`
- [R3] `colav_simulator/core/colav/custom_mpc_adapter.py`
- [R4] `colav_simulator/evaluation/evaluator.py`
- [R5] `docs/superpowers/specs/2026-08-11-mid-mpc-l0-l1-encounter-lifecycle-solution-pack.md`
- [R6] `docs/superpowers/specs/2026-08-11-mid-mpc-l1-l2-problem-assembler-solution-pack.md`
- [R7] `/Users/marine/Desktop/MPC/M5_MPC_业务流程分层架构.md`
- [R8] `tests/test_mid_mpc_single_encounter.py`、`tests/test_mid_mpc_multiship_runtime.py`、capability/runtime evidence
- [R9] Eriksen et al., [Ship Collision Avoidance Using Scenario-Based Model Predictive Control](https://www.sciencedirect.com/science/article/abs/pii/S2405896316319024), IFAC-PapersOnLine, 2016.
- [R10] Johansen et al., [On Collision Risk Assessment for Autonomous Ships Using Scenario-Based MPC](https://www.sciencedirect.com/science/article/abs/pii/S2405896320318668), IFAC-PapersOnLine, 2020.
- [R11] Wabersich et al., [A Predictive Safety Filter for Learning-Based Racing Control](https://arxiv.org/abs/2102.11907), 2021.
- [R12] Koller et al., [Safe Trajectory Tracking in Uncertain Environments](https://arxiv.org/abs/2001.11602), 2020.
- [R13] Didier et al., [Multi-Step Model Predictive Safety Filters](https://arxiv.org/abs/2309.11453), 2023.
- [R15] COIN-OR, [Ipopt Options](https://coin-or.github.io/Ipopt/OPTIONS.html), convergence tolerances、bound relaxation、scaling与fixed variables，访问2026-08-12。
- [R16] COIN-OR, [Ipopt Output](https://coin-or.github.io/Ipopt/OUTPUT.html), return status与iteration quantities，访问2026-08-12。
- [R17] CasADi, [CasADi Documentation: NLP solver inputs/outputs](https://web.casadi.org/docs/#nonlinear-programming), 3.7系列文档，访问2026-08-12。
- [R18] 本项目`marine/main@1f459d8`：`colav_simulator/core/colav/mid_mpc/solver.py`与`models.py`，审计2026-08-12。
- [R19] 本地只读实验，CasADi 3.7.2/Ipopt，`route_speed_cold`与`head_on_starboard` strict fixtures，2026-08-12；未修改源码/fixture。
- [R20] 本项目`marine/main@1f459d8` frozen graph/row bounds与seed unit inventory，审计2026-08-12。
- [R21] COIN-OR, [Ipopt callback current violations](https://coin-or.github.io/Ipopt/classorg_1_1coinor_1_1Ipopt.html#get_curr_violations)及[output quantity semantics](https://coin-or.github.io/Ipopt/OUTPUT.html)，访问2026-08-12。
- [R22] 本项目`marine/main@1f459d8`：`mid_mpc/solver.py::_trajectory/_continuous_cpa`、`mid_mpc_ipopt.py::_native_trajectories`与`mid_mpc_assembler.py::_target_predictions`，审计2026-08-12。
- [R23] 本项目`marine/main@1f459d8`：`mid_mpc_assembler.py::_effective_node_clearance`及`tests/test_mid_mpc_problem_assembler.py::test_assembler_compensates_frozen_timing_with_target_step_displacement`，审计2026-08-12。
- [R24] NIST/SEMATECH, [Multivariate Normal Distribution](https://www.itl.nist.gov/div898/handbook/pmc/section5/pmc542.htm)与[Chi-Square Critical Values](https://itl.nist.gov/div898/handbook/eda/section3/eda3674.htm)，访问2026-08-12；包围半径为对confidence ellipsoid的谱分解推导。
- [R25] 本项目`marine/main@1f459d8`：`core/tracking/trackers.py::CVModel/KF.predict/GodTracker`与`mid_mpc_assembler.py::_target_predictions`，审计2026-08-12。
- [R26] 本地只读计算，使用当前`KFParams.P_0/q`与`CVModel.F/Q`，2026-08-12；未修改源码，不作为阈值校准。
- [R27] 本项目`marine/main@1f459d8`：`evaluation/evaluator.py`与`core/collision.py`，审计2026-08-12。
- [R28] Tang, Kim, Manocha, [C2A: Controlled Conservative Advancement for Continuous Collision Detection of Polygonal Models](https://gamma-web.iacs.umd.edu/papers/documents/articles/2009/tang09.pdf), IEEE ICRA, 2009。
- [R29] 项目几何推导：矩形包含于半径`0.5*hypot(length,width)`圆；基于同步piecewise-linear center path的保守lower bound，2026-08-12。
- [R30] 本项目`marine/main@1f459d8`：`custom_mpc_adapter.py::PlannerInput/ExecutionProfile`、`integrations/mid_mpc_ipopt.py::create`、`evaluation/evaluator.py`及现有ENC hazard integrations，审计2026-08-12。
- [R31] IMO, [Resolution MSC.232(82), Revised Performance Standards for ECDIS](https://wwwcdn.imo.org/localresources/en/KnowledgeCentre/IndexofIMOResolutions/MSCResolutions/MSC.232%2882%29.pdf), clauses 11.2, 11.3.4-11.3.5, 11.4.3-11.4.4，2006。
- [R32] 本项目`marine/main@1f459d8`：`mid_mpc_assembler.py::_bind_targets/_admit_target_keys/_compile_numerical_preparation`、Adapter/Lifecycle track-age gates，审计2026-08-12。
- [R33] 本项目`marine/main@1f459d8`：`encounter_lifecycle.py::PlannerOddProfile`、`mid_mpc_assembler.py::MidMpcAssemblyConfig`、`mid_mpc_ipopt.py::create`与`evaluation/evaluator.py::_hard_gate`，审计2026-08-12。
- [R34] USCG Navigation Center, [International Navigation Rules: Rule 8 and Rule 16](https://navcen.uscg.gov/navigation-rules-amalgamated), 72 COLREG official text mirror，访问2026-08-12。
- [R35] IMO, [COLREG Convention overview](https://www.imo.org/en/about/conventions/pages/colreg.aspx)；USCG Navigation Center, [Rules 13-17](https://navcen.uscg.gov/navigation-rules-amalgamated)，访问2026-08-12。
- [R36] Australian Maritime Safety Authority, [Close proximity manoeuvres and overtaking situations](https://www.amsa.gov.au/safety-navigation/navigating-coastal-waters/close-proximity-manoeuvres-and-overtaking-situations), 2020；UK MAIB, [Safety Digest 3/2001](https://assets.publishing.service.gov.uk/media/5e7df42bd3bf7f134447df82/2001-SD3-MAIBSafetyDigest.pdf)。
- [R37] 本项目`marine/main@1f459d8`：`encounter_lifecycle.py::_passing_side`、`tests/test_encounter_lifecycle_contract.py::test_overtaking_selects_reachable_mirrored_corridor_and_locks_it`；focused test `3 passed in 2.27s`，2026-08-12。
- [R38] 本项目`marine/main@1f459d8`：`encounter_lifecycle.py::TargetDecision/_TargetState`、`mid_mpc_ipopt.py::_snapshot_document`与Assembler request hash，审计2026-08-12。
- [R39] 本项目`marine/main@1f459d8`：`encounter_lifecycle.py::_advance_target/_commit`与`mid_mpc_assembler.py::_compile_semantic_problem/_activation_plan`，审计2026-08-12。
- [R40] 项目几何推导，输入为immutable Lifecycle directive、target-track frame与同步81点trajectory；与现有post-run scenario assertions交叉核对，2026-08-12。
- [R41] 本项目`marine/main@1f459d8`：`tests/test_mid_mpc_single_encounter.py`与`tests/test_encounter_lifecycle_contract.py`，审计2026-08-12。
- [R42] 本项目`marine/main@1f459d8`：`encounter_lifecycle.py::_aggregate`与`mid_mpc_assembler.py::_resolve_policy`，审计2026-08-12。
- [R43] Fossen, [Line-of-sight path-following control utilizing an extended Kalman filter for estimation of speed and course over ground from GNSS positions](https://ntnuopen.ntnu.no/ntnu-xmlui/bitstream/handle/11250/3058079/s00773-022-00872-y.pdf?sequence=2), Journal of Marine Science and Technology, 2022。
- [R44] Isleyen, van de Wouw, Arslan, [From Low to High Order Motion Planners: Safe Robot Navigation using Motion Prediction and Reference Governor](https://arxiv.org/abs/2202.12816), 2022。
- [R45] 本项目`marine/main@1f459d8`：standard scenario YAML、`Ship.plan`、`CustomMPCAdapter._planner_input`、`CapabilitySnapshot`与`mid_mpc_ipopt.solve`，审计2026-08-12。
- [R46] 本地current-code只读probe：`_sample_trajectory` interval case与nonzero-sway ownship conversion，2026-08-12；未修改源码。
- [R47] 本项目`marine/main@1f459d8`：`_native_trajectories`、`MPCSolution`、`_execute_hold/_sample_trajectory`、frozen ROT/decel rows与active plant执行链，审计2026-08-12。
- [R48] 本项目`marine/main@1f459d8`：`_nearest_route_anchor`、`_compile_semantic_problem`、`_build_graph/_route_cost/_colreg_cost`，审计2026-08-12。
- [R49] Akdag et al., [A decision support system for autonomous ship trajectory planning](https://ntnuopen.ntnu.no/ntnu-xmlui/handle/11250/3133130), Ocean Engineering, 2023。
- [R50] Liniger et al., [Optimization-based autonomous racing of 1:43 scale RC cars](https://onlinelibrary.wiley.com/doi/10.1002/oca.2123), Optimal Control Applications and Methods, 2015。
- [R51] focused test：`test_hold_uses_explicit_executable_control_trajectory`+`test_mid_mpc_problem_assembler.py`，`21 passed in 1.34s`；并审计`test_mid_mpc_single_encounter.py`，2026-08-12。
- [R52] 本项目`0732cf1`：`custom_mpc_adapter.py::plan/_execute_hold`；并对照Candidate 3 `1f459d8`确认行为未改变，审计2026-08-12。
- [R53] 本地current-code只读stale-hold probe，输出`solve_calls=1, held_command_north=0.5, current_ownship_north=100.0, trace_status=SUCCESS, solver_executed=False`，2026-08-12；未修改源码。
- [R54] 本项目`custom_mpc_adapter.py::_execute_solve/_record_execution_failure`与`experiment/session.py::_advance`，审计2026-08-12。
- [R55] 本项目`diagnostics.py::PlanStatus/FailureSource`、`encounter_lifecycle.py::LifecycleFailure`、`mid_mpc_assembler.py::AssemblyFailureCode`及`mid_mpc_ipopt.py`failure mapping，审计2026-08-12。
- [R56] Candidate 3 accepted solution pack，`docs/superpowers/specs/2026-08-11-mid-mpc-l1-l2-problem-assembler-solution-pack.md`；实现`mid_mpc_assembler.py::ExecutionPrefixPlan/SeedPlan`，`marine/main@1f459d8`。
- [R57] COIN-OR, [Ipopt Options](https://coin-or.github.io/Ipopt/OPTIONS.html)，`warm_start_init_point/warm_start_same_structure`；CasADi, [Nonlinear programming](https://web.casadi.org/docs/#nonlinear-programming)，访问2026-08-12。
- [R58] Candidate 3 `mid_mpc/solver.py`、`integrations/mid_mpc_ipopt.py::_replay_artifact_document`及facade hash/artifact sink顺序，`marine/main@1f459d8`，审计2026-08-12。
- [R59] 本项目`gui_server/main.py::latest_planner_solve`与`web_gui/app.js::diagnosticPlannerForData/updatePlannerPanel`，审计2026-08-12。
- [R60] Pizarro Bejarano et al., [Multi-Step Model Predictive Safety Filters](https://arxiv.org/abs/2309.11453), 2023。
- [R61] 本项目`custom_mpc_adapter.py::_execute_solve` deadline/consecutive-timeout逻辑与同步`SimulationSession`执行链，审计2026-08-12。
- [R62] focused test：`uv run pytest tests/test_custom_mpc_schedule.py tests/test_experiment_contracts.py tests/test_mid_mpc_problem_assembler.py -q`，`39 passed in 17.78s`，2026-08-12。
- [R63] Candidate 3 clean `marine/main@1f459d8`：`mid_mpc_assembler.py`、`mid_mpc_ipopt.py`及accepted solution pack，审计2026-08-12。
- [R64] 本地已有`runs/*/artifacts/mid_mpc/*.json.gz`只读统计19份；最大raw artifact 118017 bytes同步gzip/write 100次microbenchmark，2026-08-12；未修改artifact。
- [R65] IETF, [RFC 8785 JSON Canonicalization Scheme](https://www.rfc-editor.org/rfc/rfc8785.html)，2020；本地`json.dumps`number-form probe，2026-08-12。
- [R66] Candidate 3 `mid_mpc_ipopt.py::_replay_artifact_document`、`EvidenceWriter.write_mid_mpc_artifact`与`test_adapter_publishes_hash_linked_replay_artifact_without_inlining_vectors`，审计2026-08-12。
- [R67] 本项目`experiment/persistence.py::write_mid_mpc_artifact`及facade artifact sink调用顺序，审计2026-08-12。
- [R68] Candidate 2 accepted lifecycle solution pack TS-34/35；Candidate 3 accepted Assembler solution pack TS-20/21，2026-08-11。
- [R69] 本项目`custom_mpc_adapter.py::_execute_solve/_execute_hold`、`PlannerTrace`、`gui_server/main.py`及`web_gui/app.js`缓存链，审计2026-08-12。
- [R70] Candidate 3 `mid_mpc_ipopt.py::render_projection/_target_prediction`、PlannerTrace与GUI server projection mapping，审计2026-08-12。
- [R71] 本项目`experiment/capabilities.py::VERIFIED_COMBINATIONS/_evidence`与`g3_gate.py::PREDICATE_VERSION`，审计2026-08-12。
- [R72] focused test：`uv run pytest tests/test_mid_mpc_ipopt_integration.py::test_adapter_publishes_hash_linked_replay_artifact_without_inlining_vectors tests/test_experiment_contracts.py -q`，`8 passed`，2026-08-12。
- [R73] `docs/superpowers/benchmarks/2026-08-11-mid-mpc-strict-runtime.md`；本轮真实16-target committed solve只读benchmark，Apple M3/macOS 26.5.2/Python 3.11.15/CasADi 3.7.2，2026-08-12。
- [R74] 本地independent analytic swept-circle/segment 16×80 microbenchmark，200 repeats，2026-08-12；未修改源码。
- [R75] 当前`tests/test_mid_mpc_*.py` test inventory与P1RunHarness seams，`marine/main@1f459d8`，审计2026-08-12。
- [R76] 当前Mid tests、generic `test_g3_display_predicate.py` mutation inventory与SC-73..82 gap analysis，2026-08-12。
- [R77] Candidate 2 accepted solution pack 8010 evidence；本轮`lsof/ps/cwd`只读listener observation，2026-08-12；未重启或修改8010。
- [R78] 当前strict runtime benchmark metadata/limitations、artifact canonical fields与Candidate 1 deterministic replay需求分析，2026-08-12。
- [R79] Candidate 3 clean `1f459d8`：`uv run pytest -q`，`464 passed, 2 skipped, 1 warning in 1627.55s`，2026-08-12。
- [R80] `git merge-base --is-ancestor b94148c 1f459d8`及`git diff --stat/name-only b94148c..1f459d8`，2026-08-12。
- [R81] 本设计日志SC-73..82与现有test seams的coverage derivation，2026-08-12。

## Step 演进

| 时间 | Step | 变化 | 状态 |
|------|------|------|------|
| 2026-08-11 | Step1 | 建立 18 个决策点、16 个盲区、14 类证据、12 个场景与 6 项 Candidate 3 并行同步约束 | 用户确认 |
| 2026-08-11 | Step2-DP01 | 确认 L4 为 L3 后、计划提交前的深无状态 Module；不拥有决策、装配、求解、修轨迹、fallback或事后评分 | 用户确认 |
| 2026-08-11 | Step2-DP02 | 确认immutable self-contained bundle；验证schema/cycle/profile/parent hash/time axis/target binding；新增BL-17与SC-13 | 用户确认 |
| 2026-08-11 | Step2-DP03 | 确认分层typed verdict与派生总裁决；mandatory FAIL/UNKNOWN fail-closed；新增BL-18与SC-14 | 用户确认 |
| 2026-08-11 | Step2-DP04 | 确认status翻译之外独立复核原始x/g/bounds/slack/finite；KKT与mixed-unit tolerance进入Step3；新增BL-19/20与SC-15 | 用户确认 |
| 2026-08-11 | Step2-DP05 | 确认同步连续footprint+uncertainty动态安全重算及per-target witness；新增BL-21/22与SC-16/17 | 用户确认 |
| 2026-08-11 | Step2-DP06 | 确认同一L4诊断两profile，仅事实验证的strict可签production receipt；新增BL-23/24与SC-18/19 | 用户确认 |
| 2026-08-11 | Step2-DP07 | 确认Lifecycle为唯一role/side/phase authority及full-horizon plan consistency；新增BL-25/26与SC-20..22 | 用户确认 |
| 2026-08-11 | Step2-DP08 | 确认baseline-relative reachable commitment、deadline、保持与recovery边界；新增BL-27..30与SC-23..26 | 用户确认 |
| 2026-08-11 | Step2-DP09 | 确认active KinematicCSOG facts、command semantics、executable rollout及rollout safety；新增BL-31..33与SC-27..30 | 用户确认 |
| 2026-08-11 | Step2-DP10 | 确认物理/时间对齐quality指标、直线非缺陷及hard/warn分责；新增BL-34..37与SC-31..34 | 用户确认 |
| 2026-08-11 | Step2-DP11 | 确认per-target不可抵消hard conjunction、集合reconciliation及Ship0 scope；新增BL-38..40与SC-35..38 | 用户确认 |
| 2026-08-11 | Step2-DP12 | 确认fresh receipt与轻量hold revalidation、piecewise control语义及stale-context处理；新增BL-41..44与SC-39..42 | 用户确认 |
| 2026-08-12 | Step2-DP13 | 确认L4前原子提交、严格no-fallback、hold单次同算法重求、稳定PlanStatus映射与可观察fail-stop；新增BL-45..48与SC-43..46 | 用户确认 |
| 2026-08-12 | Step2-DP14 | 确认Adapter-mediated accepted-plan handoff、L4 receipt唯一资格、optional cold-vs-corrupt fail边界、primal-only warm start；新增BL-49..52与SC-47..51 | 用户确认 |
| 2026-08-12 | Step2-DP15 | 确认五段唯一hash链、full/inline/GUI三层证据、L3/L4命名隔离、fresh/hold/reject事件与Planner/Evaluator分源；新增BL-53..57与SC-52..57 | 用户确认 |
| 2026-08-12 | Step2-DP16 | 确认总critical-path deadline覆盖L4、canonical决策与telemetry分离、bounded O(TN)、artifact落盘移出authority路径；新增BL-58..62与SC-58..64 | 用户确认 |
| 2026-08-12 | Step2-DP17 | 确认trusted policy与candidate facts分离、ODD/Lifecycle/capability/L4/Evaluator authority分层、canonical units与quantity-specific tolerances；新增BL-63..67与SC-65..72 | 用户确认 |
| 2026-08-12 | Step2-DP18 | 确认V1..V6验证门、独立layer oracle、真实IPOPT Playground矩阵、8010/full regression与严格claim边界；新增BL-68..73与SC-73..82 | 用户确认 |
| 2026-08-12 | Step2 | DP-01..18逐项三视角grilling全部确认；累计BL-01..73、SC-01..82，等待进入Step3逐盲区证据闭环 | 用户确认DP，步骤间门待授权 |
| 2026-08-12 | Step3-Batch01 | 完成BL-02/14/19/20/23/24/64相关的Ipopt/CasADi官方调研、当前源码审计与本地strict KKT实验；新增R15..R21 | 证据待用户确认，BL仍OPEN |
| 2026-08-12 | Step3-Batch01 | 用户确认R15..R21已回答BL-02/14/19/20/23/24/64；不在Step3裁决KKT hard/warn或具体容差 | EVIDENCE_CONFIRMED |
| 2026-08-12 | Step3-Batch02 | 完成BL-03/12/13/21/22/38/63/65/68相关的连续净距、time/target scope、不确定性与ENC static hazard调研；新增R22..R33 | 证据待用户确认，BL仍OPEN |
| 2026-08-12 | Step3-Batch02 | 用户确认R22..R33已回答BL-03/12/13/21/22/38/63/65及BL-68 safety部分；static归属、uncertainty ODD与阈值裁决仍留Step4/5 | EVIDENCE_CONFIRMED |
| 2026-08-12 | Step3-Batch03 | 完成BL-05/10/25..30及BL-68 COLREG部分的规则正文、Lifecycle contract、plan predicate与focused test调研；新增R34..R42 | 证据待用户确认，BL仍OPEN |
| 2026-08-12 | Step3-Batch03 | 用户确认R34..R42已回答BL-05/10/25..30及BL-68 COLREG部分；profile数值与standard-starboard证据门留Step4/5 | EVIDENCE_CONFIRMED |
| 2026-08-12 | Step3-Batch04 | 完成BL-04/06/31..37/42/67及BL-68 trackability/quality部分的active-plant、COG/SOG、interval semantics、route/quality调研；新增R43..R51 | 证据待用户确认，BL仍OPEN |
| 2026-08-12 | Step3-Batch04 | 用户确认R43..R51已回答BL-04/06/31..37/42/67及BL-68 trackability/quality部分；Plant tube与具体quality阈值仍为UNKNOWN/留Step4/5 | EVIDENCE_CONFIRMED |
| 2026-08-12 | Step3-Batch05 | 完成BL-07..09/18/39/41/43/45..53/59相关的hold freshness、reject atomicity、failure taxonomy、accepted-plan warm handoff、deadline与GUI timeline调研；新增R52..R62 | 证据待用户确认，BL仍OPEN |
| 2026-08-12 | Step3-Batch05 | 用户确认R52..R62已回答BL-07..09/18/39/41/43/45..53/59；retry/precedence/exact schema与budget裁决留Step4/5或性能batch | EVIDENCE_CONFIRMED |
| 2026-08-12 | Step3-Batch06 | 完成BL-01/11/17/44/54..57/60/61/66/68相关的hash canonicalization、full/inline/render分层、artifact persistence、timeline与capability governance调研；新增R63..R72 | 证据待用户确认，BL仍OPEN |
| 2026-08-12 | Step3-Batch06 | 用户确认R63..R72已回答BL-01/11/17/44/54..57/60/61/66及BL-68 evidence部分；exact schema/queue budget/canonical方案留Step4/5 | EVIDENCE_CONFIRMED |
| 2026-08-12 | Step3-Batch07 | 完成BL-15/16/40/58/62/69..73相关的16-target性能、O(TN)成本、negative/metamorphic corpus、capability治理、8010与full baseline调研；新增R73..R81 | 证据待用户确认，BL仍OPEN |
| 2026-08-12 | Step3-Batch07 | 用户确认R73..R81已回答BL-15/16/40/58/62/69..73；具体性能门、fixture数量与runtime策略留Step4/5裁决 | EVIDENCE_CONFIRMED |
| 2026-08-12 | Step3 | BL-01..73均已有用户确认的证据或显式UNKNOWN边界；R1..R81覆盖全部TD-01子模块，Step3步骤间门通过 | 完成；等待进入Step4授权 |
| 2026-08-12 | Step4 | 用户授权进入逐DP汇总推荐；按内部确认门从DP-01开始，不批量裁决 | 进行中 |
| 2026-08-12 | Step4-DP01 | 用户确认深pure无状态Module、单一Seam、责任排除、fail-closed边界与验证要求；写入VR-01/ALT-01/02/06/07 | final |
| 2026-08-12 | Step4-DP02 | 用户确认四namespace self-contained request、authority分离、ENU/SI/rad、81/80时序、TrackKey reconciliation、versioned canonicalization与offline replay；写入VR-02/ALT-08..11 | final |
| 2026-08-12 | Step4-DP03 | 用户确认typed layers/outcomes、integrity short-circuit、mandatory fail-closed、quality advisory、parity diagnostic-only、primary projection与persistence分责；写入VR-03/ALT-12..15 | final |
| 2026-08-12 | Step4-DP04 | 用户确认eligible termination、同一candidate original-primal/strict/objective hard复核、KKT V1 advisory、callback/timeout数值资格边界与mixed-unit tolerance原则；写入VR-04/ALT-16..20 | final |
| 2026-08-12 | Step4-DP05 | 用户确认all-relevant 81/80同步连续保守船体净距、50m physical hard gate、God/校准uncertainty边界、applicable static hard check及Ship0/target-target scope分离；写入VR-05/ALT-21..28 | final |
| 2026-08-12 | Step4-DP06 | 用户确认同一checker显式隔离MASS_PARITY diagnostic与COLAV_STRICT production；actual preparation/options/hash chain机械复核、strict无parity fallback、profile可见及receipt/claim失效语义；写入VR-06/ALT-29..34 | final |
| 2026-08-12 | Step4-DP07 | 用户确认Lifecycle为唯一COLREG directive authority；L4按完整trajectory验证HO/CS/OT/stand-on/Rule17且不重分类、重选侧或仲裁冲突；standard OT右转偏好与镜像锁定侧边界；写入VR-07/ALT-35..40 | final |
| 2026-08-12 | Step4-DP08 | 用户确认带deadline的Lifecycle action contract、固定commit baseline跨solve累计、first executable interval early/substantial、有限wrong-side单调恢复及actual release后方可recovery；写入VR-08/ALT-41..48 | final |
| 2026-08-12 | Step4-DP09 | 用户确认81/80 state-command语义、COG/SOG与body状态分离、真实active-plant execution-prefix hard gate、reachability certificate及无full tube时1200s claim降级；写入VR-09/ALT-49..56 | final |
| 2026-08-12 | Step4-DP10 | 用户确认V1 quality advisory-only、物理指标分离、absolute-time/context-compatible cross-solve比较、polyline route recovery与近直线非缺陷边界；写入VR-10/ALT-57..63 | final |
| 2026-08-12 | Step4-DP11 | 用户确认五目标集合reconciliation、TrackKey generation、per-target mandatory AND、Lifecycle/Assembler conflict authority、capacity fail-closed及Ship0/target-target global scope分离；写入VR-11/ALT-64..72 | final |
| 2026-08-12 | Step4-DP12 | 用户确认fresh完整L4、hold absolute-time active-prefix重验、piecewise-constant command、一次同算法immediate replan、hold不签receipt及active/latest双时间线；写入VR-12/ALT-73..81 | final |
| 2026-08-12 | Step4-DP13 | 用户确认typed L4 result到稳定PlanStatus projection、总deadline/freshness后的atomic commit、TIMEOUT_FEASIBLE边界、fresh rejection清理/no-fallback及Session terminal FAILED；写入VR-13/ALT-82..90 | final |
| 2026-08-12 | Step4-DP14 | 用户确认L4 certificate、Adapter commit receipt、neutral previous record三层authority；absolute-time primal resample/cold tail/zero slack/dual disabled，正常不兼容cold、损坏reject及warm无retry；写入VR-14/ALT-91..99 | final |
| 2026-08-12 | Step4-DP15 | 用户确认canonical acceptance record、full/inline/GUI三projection、Request-to-Commit hash chain、typed event双时间线、81/80真实轨迹与L4/Evaluator分源；写入VR-15/ALT-100..109 | final |
| 2026-08-12 | Step4-DP16 | 用户确认20s全链路deadline、solver reservation、完整deterministic L4、semantic/dispatch分离及bounded async crash-safe persistence；reservation以full-L4 p99校准且未校准不production-ready；写入VR-16/ALT-110..119 | final |
| 2026-08-12 | Step4-DP17 | 用户确认typed immutable policy/owner graph、canonical units、80x15s/50m/150m/16-target/20s/God strict constants、quantity tolerances、dynamic authority delegation、bounded persistence defaults及version/claim invalidation；写入VR-17/ALT-120..129 | final |
| 2026-08-12 | Step4-DP18 | 用户确认V1..V6六级promotion gates、独立oracles、真实IPOPT/Playground/8010、p99 reservation/full regression及exact Ship0 capability/claim边界；写入VR-18/ALT-130..140 | final |
| 2026-08-12 | Step4-Audit | 完成18个DP注册表/section/VR、证据链、备选、风险、TD-01与未决生产门机械审计；发现并修正DP-01..03 section标题仍为DRAFT的文档状态漂移 | 审计结果待用户确认；不自动进入Step5 |
| 2026-08-12 | Step5-Selection | 用户确认Step4审计并授权进入Step5；提出5张DESIGN-IT-TWICE卡与DP-18低风险直接采纳候选 | 对比对象/跳过项待用户确认，尚未生成或裁决卡片 |
| 2026-08-12 | Step5-Selection | 用户确认DC-01..05对比范围，并判定DP-18低风险直接采纳；写入VR-19，不增加DC-06 | final；开始DC-01，尚未裁决 |
| 2026-08-12 | Step5-DC01 | 用户裁决采纳方案A Independent Pure L4，弃用stateful Adapter controller与distributed gates；写入VR-20/ALT-141..142 | final；开始DC-02 |
| 2026-08-12 | Step5-DC02 | 用户裁决采纳方案A primal-hard/KKT-advisory + swept conservative safety，弃用KKT-hard exact geometry与solver-native/post-run gate；写入VR-21/ALT-143..144 | final；开始DC-03 |
| 2026-08-12 | Step5-DC03 | 用户裁决采纳方案A Lifecycle-locked obligations + active-prefix capability + per-target AND，弃用candidate-relative reclassification与safety-only/post-run COLREG；写入VR-22/ALT-145..146 | final；开始DC-04 |
| 2026-08-12 | Step5-DC04 | 用户裁决采纳方案A prefix revalidation + atomic receipt/warm transaction，弃用every-tick solve与last-plan continuation/fallback；写入VR-23/ALT-147..148 | final；开始DC-05 |
| 2026-08-12 | Step5-DC05 | 用户裁决采纳方案A canonical semantic record + async durable sink，弃用synchronous event-sourced commit与lightweight trace；写入VR-24/ALT-149..150 | final；开始Step5完整性审计 |
| 2026-08-12 | Step5-Audit | 用户确认DC-01..05、VR-19..24、ALT-141..150、DP/TD覆盖与production gates完整；授权进入Step6 | 用户确认 |
| 2026-08-12 | Step6 | 提取术语表、TS-01..42，组装八组件solution pack并冻结to-spec权限边界 | 方案包待用户接受；未交付to-spec |
| 2026-08-12 | Step6-Acceptance | 用户明确回复“接受”；八组件方案包成为to-spec权威输入 | 已交付to-spec |
| 2026-08-12 | to-spec | 综合accepted方案包生成正式Spec、12-slice实施Plan，并发布GitHub issue #26与`ready-for-agent` | 完成 |

## 2. Step2 grilling 压力测试

### Step2-DP01 · Module 责任、Depth 与 Seam

| 视角 | 已确认结论 |
|---|---|
| 专家 | L4 位于 L3 候选解之后、Adapter提交执行计划之前；消费 immutable plan bundle，输出分层 verdict，不改变候选解。[R6][R7][R11] |
| 新手 | facade 的 solver-status 映射、Adapter shape/continuity校验、Evaluator事后评分均不能独立回答“本次计划能否下发”。[R1..R4] |
| 悲观 | 过浅会放过业务不可接受解；过深会复制 Lifecycle/Assembler/Evaluator authority；有状态会破坏retry/replay；修改轨迹会越界进入L5。 |
| 机制C默认最简版失效 | `converged && max_violation < tol`漏掉节点间碰撞、wrong-side、不可跟踪、质量恶化和stale hold，见SC-06/07/09/10。 |
| 盲区 | BL-07、BL-09、BL-13，优先级均为高。 |

用户确认的责任范围：深、无状态、确定性 Module；单一窄 Interface；内部编排 L4.1..4.5；不拥有 Encounter 决策、OCP/bounds、IPOPT、轨迹修正、fallback/MRM、事后评分或 capability promotion。

### Step2-DP02 · 输入、identity、time与profile契约

| 视角 | 已确认结论 |
|---|---|
| 专家 | L4消费immutable、versioned、self-contained plan bundle，验证同一cycle/problem/preparation/raw-solver父链；不读取GUI、PlannerTrace自由字典或日志文本作为authority。[R6] |
| 新手 | bare `MPCSolution`缺raw数值证据；bare `MidMpcResult`缺Lifecycle、安全要求、footprint、prediction和公共81点轨迹。 |
| 悲观 | mutable引用、独立但未关联的hash、artifact在线读取、候选生产者自带降级门均会产生可自证的错误接受。 |
| 机制C默认最简版失效 | `algorithm_details + constraints`字典导致字段/单位漂移、80/81点错位、strict/parity混用、跨cycle拼接和不可replay。 |
| 盲区/场景 | 保留BL-01/11/12；新增BL-17 trusted profile authority与SC-13跨cycle/profile拼接或降门。 |

用户确认的Interface压力结论：request至少区分trusted expected facts、candidate plan、upstream identities、solver evidence、time grid、target predictions和execution context；字段名等Candidate 3冻结后确定。hash只证明内容未变，不证明内容正确或属于同一事务。

### Step2-DP03 · 分层verdict与总acceptance

| 视角 | 已确认结论 |
|---|---|
| 专家 | outcome同时保留integrity/numerical/safety/COLREG/trackability/quality/evidence分层事实与派生总裁决；不是两套判断。 |
| 新手 | Adapter虽最终只需下发/拒绝，单一布尔无法解释失败、warm-start资格、retry条件或GUI证据。 |
| 悲观 | 无precedence、滥用WARN/UNKNOWN/N/A、在integrity失败后继续解释、只保留最后失败，都会产生矛盾或不稳定裁决。 |
| 机制C默认最简版失效 | bare `accepted/reason`丢失多失败、timeout资格、hard与quality差异及source witness。 |
| 盲区/场景 | 保留BL-06/09/14；新增BL-18 layer taxonomy与SC-14多失败/integrity short-circuit。 |

用户确认的聚合原则：integrity先行；有效bundle收集全部独立失败；mandatory hard FAIL或UNKNOWN导致拒绝；N/A须有applicability证据；primary failure使用固定precedence并保留完整failure列表；parity diagnostic不能产生production accepted receipt。

### Step2-DP04 · IPOPT数值接受与原始可行性

| 视角 | 已确认结论 |
|---|---|
| 专家 | IPOPT success只证明满足其局部数值终止条件；L4必须按原始`x/g/lbx/ubx/lbg/ubg`复核，不能外推业务安全或全局最优。[R1] |
| 新手 | status不能发现raw x越界、NaN objective、strict slack或row/layout错误。 |
| 悲观 | 只信status会漏原始越界；统一`1e-3`混淆rad/m/s/m²；精确零会拒绝数值噪声；无证据强制KKT会扩大改动。 |
| 机制C默认最简版失效 | `Solve_Succeeded && max_g_violation<=1e-3`漏掉变量边界、finite、strict slack、shape/layout和scaled-vs-original差异。 |
| 盲区/场景 | 保留BL-02/14/18；新增BL-19 KKT证据、BL-20 mixed-unit tolerance、SC-15对抗status/数值组合。 |

用户确认的数值检查分解：termination、shape/finite、原始variable bounds、原始constraint bounds、strict slack、objective一致性、KKT/stationarity证据、逐类violation/witness。`TIMEOUT_FEASIBLE`不自动获得production接受资格；KKT是否为v1 hard gate交Step3调研。

### Step2-DP05 · 同步连续船体净距

| 视角 | 已确认结论 |
|---|---|
| 专家 | 对同一绝对时刻的ownship/target path覆盖81个state形成的全部80个区间，含第一段和末段；node CPA不等于continuous safety。[R4][R6] |
| 新手 | 中心node安全仍可能在15s区间穿越；center distance还需扣除双方footprint与prediction uncertainty。 |
| 悲观 | 只查selected target会形成admission自证；只查point/node会漏大船与区间穿越；复用Evaluator verdict会形成Planner自评。 |
| 机制C默认最简版失效 | `min(node_center_distance)>=50m`漏第一段、区间、footprint、uncertainty、non-selected target和witness。 |
| 盲区/场景 | 保留BL-03/12/13；新增BL-21 safety target scope、BL-22 static safety、SC-16 non-selected target、SC-17 shoreline/hazard。 |

用户确认的动态安全分解：共享time grid、81-state own/target path、footprint、逐stage uncertainty、80区间continuous minimization、50m hard threshold、per-target/segment/time witness。L4使用planner-neutral pure geometry直接重算，不信任solver汇总或Evaluator verdict。

### Step2-DP06 · MASS_PARITY与COLAV_STRICT隔离

| 视角 | 已确认结论 |
|---|---|
| 专家 | parity证明冻结方程/packing一致；strict用于production hard-safety语义，二者claim不可替代。[R6] |
| 新手 | parity plan偶然安全不等于parity profile具备production eligibility。 |
| 悲观 | strict失败后回退parity、只信profile字符串、双checker漂移、GUI隐藏profile都会产生错误claim。 |
| 机制C默认最简版失效 | `profile_name==COLAV_STRICT`无法发现伪标签、旧prepared vectors、错误slack bounds或跨profile hash拼接。 |
| 盲区/场景 | 保留BL-01/17/20；新增BL-23 strict preparation proof、BL-24 profile visibility、SC-18 parity/strict分歧、SC-19伪strict。 |

用户确认的profile原则：两profile使用同一L4 Implementation；parity可产完整diagnostic但总结果为non-dispatchable，不能产receipt/warm-start/G3 production evidence；仅trusted expected profile、actual preparation和全部mandatory gates共同证明strict时可签production accepted receipt。

### Step2-DP07 · COLREG consistency authority与场景语义

| 视角 | 已确认结论 |
|---|---|
| 专家 | L4消费Candidate 2冻结的encounter/role/risk/commitment/passing-side/Rule17，不以已改变的瞬时几何重分类。[R5] |
| 新手 | 转向后相对方位变化，重分类会重现intent flicker；L4验证已锁定决定，不生成新决定。 |
| 悲观 | 只看first command/final CPA、复用Evaluator分类、忽略Rule17 stage或只看aggregate side会漏回切、提前/迟延行动和per-target违规。 |
| 机制C默认最简版失效 | `sign(first_heading_delta)==passing_side`漏小幅假动作、远期回切、crossing ahead、未past-clear、stand-on违规与多目标冲突。 |
| 盲区/场景 | 保留BL-10/13/18；新增BL-25 OT profile、BL-26几何predicate、SC-20 locked encounter、SC-21 OT双侧、SC-22 Rule17/safety conflict。 |

用户确认的规则边界：HEAD_ON/CROSSING/OVERTAKING/STAND_ON按Lifecycle锁定directive检查完整相关窗口；CLEAR/RELEASED仍通过safety层；L4只证明预测计划一致，不代替实际Evaluator。Rule13不把右侧超越规定为通用法律常数；Step3按“标准OT优先右侧、受限/镜像允许Lifecycle锁定左侧”方向验证Playground profile。

### Step2-DP08 · early/substantial/past-clear/recovery

| 视角 | 已确认结论 |
|---|---|
| 专家 | Rule8要求positive/ample/substantial/safe passing并检查至past-clear，但不提供统一角度、秒数或距离；L4消费Candidate 2 commitment contract，不发明法律常数。[R5] |
| 新手 | 最终转够角度仍可能太迟；需分别验证开始、达到、保持、安全效果和允许回航。 |
| 悲观 | 固定5°、current-relative累加、只看终点、首节点硬禁wrong-side、预测past-clear反推actual release均会误判。 |
| 机制C默认最简版失效 | `side_sign*(psi[1]-baseline)>=required`漏deadline、小改向、回切、speed action、保持及recovery许可。 |
| 盲区/场景 | 保留BL-05/17/26；新增BL-27..30 action deadline/transient/history/grid；新增SC-23..26迟行动、小改向、可恢复wrong-side、过早/不安全回航。 |

用户确认的物理语义：early基于explicit latest-safe deadline；substantial相对immutable baseline且可由course/speed联合满足；unavoidable wrong-side transient由reachability envelope约束；past-clear/recovery仅消费Lifecycle actual facts；15s grid不足部分必须使用first executable command或continuous evidence。

### Step2-DP09 · trackability与first executable segment

| 视角 | 已确认结论 |
|---|---|
| 专家 | OCP rate rows不证明active Plant能跟踪；L4同时检查candidate path、command path和active plant response。[R12] |
| 新手 | 理想heading/speed可瞬跳，KinematicCSOG受T_chi/T_U/r_max限制；ideal safe不等于executable safe。 |
| 悲观 | 只查差分、只查first command、误读9-state fields或用静态YAML冒充live plant会形成虚假trackability。 |
| 机制C默认最简版失效 | rate-box漏first-order lag、saturation、heading/COG、surge/SOG、sway、first segment和ideal-vs-rollout差异。 |
| 盲区/场景 | 保留BL-04/28/30；新增BL-31 full-horizon scope、BL-32 state/command semantics、BL-33 tracking margin、SC-27..30 executable rollout/ODD反例。 |

用户确认的trackability分解：active model identity与live facts、command semantics、initial COG/SOG、full command rollout、ideal-vs-executable error、rollout continuous safety/COLREG、first executable witness。v1只对声明的KinematicCSOG Playground profile签PASS；缺事实或模型不匹配fail-closed。

### Step2-DP10 · solution quality与hard/warning边界

| 视角 | 已确认结论 |
|---|---|
| 专家 | quality关注稳定、适度、progress与recovery，不等同于collision safety；近似直线在route-only/HOLD/stable corridor可自然PASS。[R13] |
| 新手 | raw objective随targets/weights/profile变化，不能直接作跨cycle质量阈值。 |
| 悲观 | 全部hard会拒绝安全计划；全部warning会放过抖动/无故停车；Evaluator评分会形成自评；额外nominal solve扩大实时路径。 |
| 机制C默认最简版失效 | `objective_total<threshold`无法定位churn、speed loss、progress、recovery或target-count scaling。 |
| 盲区/场景 | 保留BL-06/29/33；新增BL-34..37 metric/history/route/objective；新增SC-31..34直线、过激、跨solve抖动、迟恢复。 |

用户确认的quality原则：使用物理可解释、absolute-time aligned指标；安全/COLREG/trackability拥有hard facts；quality仅对versioned profile明确的operational failure设hard，其余warning；不降50m、不改变Lifecycle、不修改plan、不用当前场景PASS反推阈值。

### Step2-DP11 · 多目标per-target verdict与Ship0 aggregate

| 视角 | 已确认结论 |
|---|---|
| 专家 | 先形成每个TrackKey/episode的safety/COLREG verdict，再与global gates合成Ship0裁决；hard failure不可由其他target抵消。[R5][R9] |
| 新手 | global minimum/score无法说明哪个目标wrong-side、未past-clear或Rule17违规。 |
| 悲观 | primary-only、any-starboard、平均score、裸ID、selected-only和target-target全局失败都会错误聚合。 |
| 机制C默认最简版失效 | `min_clearance>=50 && primary_colreg_pass`漏per-target obligation、集合/identity错误、non-selected target与conflict。 |
| 盲区/场景 | 保留BL-10/18/21；新增BL-38..40 target-set/conflict/performance；新增SC-35..38 per-target fail、directive conflict、ID reuse、target-target out-of-scope。 |

用户确认的aggregate原则：核对Lifecycle/tracks/admission/predictions/solver bindings五集合；all relevant per-target mandatory gates取AND；primary仅展示；无共同corridor由Assembler先fail、L4防御拒绝；target-target collision保留global evidence但不进入Ship0 hard aggregate。

### Step2-DP12 · fresh solve与hold revalidation

| 视角 | 已确认结论 |
|---|---|
| 专家 | fresh通过完整L4后签accepted receipt；hold基于当前state/tracks和剩余计划轻量revalidate，不沿用旧SUCCESS。[R3][R13] |
| 新手 | hold只是不重新求解，不代表新观测和执行偏差无需重新检查。 |
| 悲观 | 无复核会执行stale plan；每tick完整L4过重；hold重分类越权；线性插值interval controls改变执行语义；旧轨迹标当前时间误导。 |
| 机制C默认最简版失效 | `now<next_solve → sample(previous_plan)`漏expiry/reset/deviation/new target/prediction invalidation及sampling错误。 |
| 盲区/场景 | 保留BL-07/12/35；新增BL-41..44 hold scope/control semantics/replan/trace；新增SC-39..42新target、deviation、sampling、stale receipt。 |

用户确认的hold原则：fresh receipt绑定absolute time/hash/validity；hold只复核执行窗口，不重做IPOPT/KKT或Lifecycle；失效返回typed stale/replan结果；control interval与state interpolation分离；hold PASS不签新的full-plan receipt。

### Step2-DP13 · rejection、no-fallback与fail-stop

| 视角 | 已确认结论 |
|---|---|
| 专家 | L4是纯裁决者；Adapter/Session把typed rejection映射为公共`PlanStatus`与执行状态。只有L4 production acceptance后，才可原子提交solution、current plan、receipt、warm-start eligibility与`planner_solved`。[R2][R3][R7] |
| 新手 | IPOPT成功不等于plan可执行；L4拒绝后继续旧plan、输出零舵/停车或切换算法，均是未声明fallback。 |
| 悲观 | 先写`_solution`再复核会让拒绝plan进入hold；全部映射`INFEASIBLE`会丢owner/recoverability；retry无上限会超deadline；事件先报solved会制造虚假成功。 |
| 机制C默认最简版失效 | `if not accepted: raise ColavExecutionError(INFEASIBLE)`不保证原子性、多失败证据、稳定status映射、single-replan边界或GUI真实性。 |
| 盲区/场景 | 保留BL-07/09/14/18/39/43；新增BL-45..48 status/replan/atomic commit/UI；新增SC-43..46 fresh reject、hold replan、多失败、旧plan隔离。 |

用户确认的失败原则：fresh候选被拒后不复用旧plan、不输出替代控制、不切算法；hold stale仅在本cycle尚未求解且预算允许时最多触发一次同算法Mid-MPC重求，失败即fail-stop。公共enum保持稳定：integrity/input→`INVALID_INPUT`，数值证据失败→`NUMERICAL_FAILURE`，安全/COLREG/trackability hard reject→`INFEASIBLE`，详细原因由L4 failure code表达。所有失败保留，primary code按固定precedence派生；rejection event明确`fallback_used=false`且无selected command。

### Step2-DP14 · Accepted Plan Handoff与warm-start eligibility

| 视角 | 已确认结论 |
|---|---|
| 专家 | L4只在production overall ACCEPTED后签receipt；Adapter原子保存immutable accepted record并在下一cycle传给Assembler；Assembler只判断数值seed eligibility，新candidate仍完整L4复核。 |
| 新手 | warm start只是IPOPT初值，不是安全证明、继续执行许可、fallback或旧acceptance继承。 |
| 悲观 | 直接保存`previous_x`会混入L4拒绝解、旧profile/target/layout/time/reset状态；L4生成SeedPlan或Assembler调用L4都会形成责任倒置。 |
| 机制C默认最简版失效 | `if solver_success: previous_x=raw_x`没有acceptance authority、原子提交、5s/15s时移、tail-fill、slack重建、identity/hash或reset隔离。 |
| 盲区/场景 | 保留BL-01/08/29/35/47；新增BL-49..52 receipt/eligibility/resampling/solver-basin；新增SC-47..51 consecutive solve、stale/corrupt、ineligible result、no retry、sub-grid shift。 |

用户确认的handoff原则：L4、Assembler不直接互调；Adapter通过neutral contract传递`AcceptedPlanReceipt/Record/PreviousAcceptedPlan`。receipt绑定session/epoch/cycle/time、algorithm/solver/formulation/layout、strict profile/policy、parent hashes、Lifecycle/TrackKey slots、accepted primal与validity。正常缺失/过期/不兼容使用显式cold start；证据损坏fail-closed。只允许heading/speed primal seed；slack按当前problem重建、dual禁用；hold不签新receipt；warm solve失败不自动cold retry。

### Step2-DP15 · evidence、hash、artifact、trace与GUI projection

| 视角 | 已确认结论 |
|---|---|
| 专家 | 唯一canonical链为Request→Problem→Prepared→Solver Candidate→L4 Acceptance；full replay artifact是离线authority，inline trace与GUI只是有hash绑定的projection。Candidate 3 placeholder必须由真实L4 stage替换。 |
| 新手 | L3的`accepted_by_quality_gate`仅表示选择了一个IPOPT candidate；不能显示为L4“可执行计划已接受”。Planner在线裁决与Evaluator事后评分也不是同一source。 |
| 悲观 | free-form `algorithm_details`会漂移/膨胀；旧`planner_solved`会遮蔽新rejection；hold会覆盖fresh provenance；artifact先于L4组装会永久保存假acceptance。 |
| 机制C默认最简版失效 | 把raw vectors、verdict、GUI字段全部塞入一个dict，无法保证schema、size、source、hash、active-plan/latest-attempt双时间线或篡改检测。 |
| 盲区/场景 | 保留BL-11/13/24/37/44/47/48/49；新增BL-53..57 schema/projection/timeline/persistence/witness；新增SC-52..57 reject、consistency、hold、sink failure、Evaluator分源、witness integrity。 |

用户确认的证据原则：full artifact保存完整五段链、layer verdict/failures/witness/policy；inline≤8KiB只含稳定摘要与hash；GUI不成为authority。accepted/rejected fresh、validated/stale hold使用不同typed events；rejected candidate不得作为active trajectory。L4使用内存完整证据裁决；mandatory evidence构造失败则拒绝，磁盘持久化失败不反向改变已完成裁决但必须标`INCOMPLETE`。hold record以原acceptance hash为parent；Ship0 L4与global Evaluator分别标source/scope。

### Step2-DP16 · runtime budget、determinism与artifact I/O

| 视角 | 已确认结论 |
|---|---|
| 专家 | Adapter monotonic总deadline覆盖Assembly→Preparation→IPOPT→L4→atomic commit；canonical acceptance/hash在关键路径，full JSON/gzip/file I/O移出authority路径。 |
| 新手 | solver耗时<20s不代表计划及时；L4若在deadline后完成，snapshot可能已经stale。慢磁盘也不应把相同安全计划变成不同裁决。 |
| 悲观 | 只给IPOPT计时、hash包含wall telemetry、queue无限、预算压力跳过mandatory layer或L4异常后留下partial receipt都会破坏fail-closed与replay。 |
| 机制C默认最简版失效 | 在现有同步`_solve()`末尾追加L4和artifact写盘，会漏算L4、让I/O控制status、产生非确定hash并可能阻塞hold/replan。 |
| 盲区/场景 | 保留BL-14/40/41/46/52/54/56；新增BL-58..62 budget/freshness/canonicalization/queue/worst-case；新增SC-58..64 max-target、deadline、timeout-feasible、I/O、determinism、partial failure、hold budget。 |

用户确认的运行原则：total deadline以monotonic clock覆盖所有控制authority阶段；L4有独立子预算但具体数值交Step3。IPOPT timeout-feasible仍须完整L4及当前freshness检查；总deadline超限不commit。相同canonical bundle/policy产生相同verdict/hash/witness，wall timing、artifact path、queue ID不入hash。v1复杂度固定`T≤16,N=80`的bounded `O(TN)`，禁止额外NLP/Evaluator/network/disk read或按耗时跳层。artifact使用bounded persistence；失败只改变persistence telemetry，不改变已完成的内存裁决。

### Step2-DP17 · threshold、unit、tolerance与profile ownership

| 视角 | 已确认结论 |
|---|---|
| 专家 | candidate只报告observed facts/hashes；Registry/Session冻结trusted expected L4 policy。Lifecycle拥有role/side/action，ODD profile拥有50m/150m需求，active capability拥有plant envelope，L4 policy拥有checker tolerance/quality/runtime，Evaluator保持独立事后门。 |
| 新手 | 50m hull clearance是船体边界净距；Assembler为point/node NLP编译的effective center CPA可能更大，二者不能混称或重复加footprint。 |
| 悲观 | YAML单点配置会造成多authority漂移；统一`1e-3`混淆m/m²/rad；candidate降低门、uncertainty双计、静态3°/s覆盖live plant、按场景调参都会制造虚假PASS。 |
| 机制C默认最简版失效 | 继续让`mid_mpc_ipopt.yaml`同时决定Planner intent、L3 bounds、L4 acceptance和Evaluator claim，无法证明trusted requirement、单位一致、版本失效或无场景作弊。 |
| 盲区/场景 | 保留BL-05/17/20/22/30/33/34/36/42/57/60；新增BL-63..67 authority/tolerance/uncertainty/governance/calibration；新增SC-65..72降门、unit、mixed tolerance、dynamic action、uncertainty、version、live capability、scenario invariance。 |

用户确认的profile原则：canonical为ENU/m/s/rad及具名m² rows；identity/hash零容忍，各物理量使用独立保守tolerance。L4 policy包含schema/id/version/hash、expected strict/ODD profile、allowed plant、numerical/safety/quality/runtime rules，Session启动冻结。任何policy变化使旧receipt失效并要求claim重验。禁止MASS_PARITY production、scenario/target/seed分支或以现有PASS拟合阈值；50m hard门不得通过容差实质降低。OT side仍消费Lifecycle锁定结果，不在L4硬编码。

### Step2-DP18 · validation matrix与claim boundary

| 视角 | 已确认结论 |
|---|---|
| 专家 | 验证分V1 contract、V2 independent layer oracles、V3 real L3→L4、V4 closed loop、V5 8010/UI、V6 regression/claim；capability evidence绑定algorithm/scenario/tracker/seed/policy/plant/evaluator/artifact身份。 |
| 新手 | full pytest只证明无已知回归，不能替代真实IPOPT闭环；HTTP 200不证明Mid-MPC/L4执行；Evaluator PASS也不证明每次plan在执行前已接受。 |
| 悲观 | mock solver、happy-only、自用production helper作oracle、先升capability后补证据、按当前场景拟合阈值或只测单次warm-cache都会制造虚假成熟度。 |
| 机制C默认最简版失效 | 只给现有HO/CS/OT测试加`accepted=true`断言，无法证明checker能拒绝缺陷、hash/source正确、hold/reject安全、性能确定或8010展示真实。 |
| 盲区/场景 | 保留BL-13/16/19/21/22/24/25/31/34/40/52/58/62/66/67；新增BL-68..73 independent oracle/corpus/capability/live/performance/regression；新增SC-73..82 route、mutation、closed-loop、multiship、timeline、8010、performance、full regression、claim invalidation、metamorphic。 |

用户确认的验证原则：每个L4 layer必须有不复用production判断helper的独立oracle与negative/boundary证据；V3/V4必须真实CasADi/IPOPT、80×15s、81 states、strict、God、固定seed、no fallback。Playground覆盖route-only、HO、CS-GW/SO、OT标准/镜像、overtaken及multiship；Ship0安全与target-target global evidence分开。8010必须证明listener cwd、真实planner event、L4 source/artifact/GUI；最后跑focused、performance、full regression。声明仅限精确policy/plant/tracker/seed/scenario tuple，不扩展为全球最优、任意输入安全、全船安全、MASS-L3 SIL/GNC/M7、法规或实船认证。

## 3. Step3 深度证据调研

### Batch-01 · numerical acceptance、KKT、mixed-unit tolerance与strict/parity

> 用户已授权本对话使用联网一手资料替代NLM；本批使用COIN-OR/CasADi官方文档、当前源码与只读本地实验。以下是证据，不是最终裁决；BL在用户确认前保持OPEN。

| 盲区 | 证据回答 | 证据 | 检索置信 | 来源权威 | 场景适用 |
|---|---|---|---|---|---|
| BL-02/19 KKT证据能否稳定取得 | terminal result可从CasADi取得`lam_x/lam_g`，结合CasADi graph梯度/Jacobian可独立重算stationarity；当前`MidMpcResult`丢弃multipliers/stats，故现有public L4 bundle尚不能做完整KKT复核。[R17..R19] | 官方contract+源码+两fixture实验 | 高 | 高 | 高 |
| BL-02/19 KKT应否只读`inf_du` | 不能。Ipopt iteration `inf_du`是scaled internal dual infeasibility；desired termination还同时涉及scaled overall error及unscaled dual/primal/complementarity门。完整original proof需同一candidate的multipliers与明确scaling/固定变量语义。[R15][R21] | 官方Ipopt | 高 | 高 | 高 |
| BL-14 timeout/nonoptimal资格 | `Solve_Succeeded`只表示desired tolerance内局部最优；`Solved_To_Acceptable_Level`、`User_Requested_Stop`、CPU/wall timeout语义不同。当前strict设`acceptable_iter=0`，官方说明此举禁用acceptable heuristic；当前非最优路径实际来自callback stop/best feasible iterate，不能借native success语义放行。[R15][R16][R18] | 官方+源码 | 高 | 高 | 高 |
| BL-14 callback candidate KKT | 当前callback保存`x/f/g`，忽略同次callback已有的`lam_x/lam_g`；best-feasible accepted iterate可能不是terminal iterate，因此terminal multipliers不能证明被选中incumbent的KKT。[R17][R18] | 官方contract+源码 | 高 | 高 | 高 |
| BL-20/64 mixed-unit tolerance | frozen rows至少含rad、m/s、m²、m；统一`1e-3`不是同一物理含义。CPA row规模随距离平方增长，应按row family使用单位明确的absolute+scale-aware diagnostic；identity/finite/shape仍零容忍。[R18][R20] | 源码unit inventory | 高 | 高 | 高 |
| BL-20/64 slack语义 | CPA slack进入m² row，但其cold seed用m距离缺口；direction slack同时加入m cross-track与rad min-alt rows。两者是必须保留的parity quirks，不能获得单一物理单位；strict把两slack固定0，因此production L4应检查原始固定bounds，不把parity slack数值解释为物理安全margin。[R18][R20] | frozen源码 | 高 | 高 | 高 |
| BL-23 strict preparation proof | strict不应靠profile字符串：需验证actual `lbx/ubx`两slack均`[0,0]`、`bound_relax_factor=0`、original x/g bounds、formulation/layout/profile父链。Ipopt官方确认默认会relax变量bounds且终止报告不含original-bound violation；当前strict显式关闭relax是必要事实。[R15][R18] | 官方+源码 | 高 | 高 | 高 |
| BL-24 parity/strict可见性 | 当前runtime integration硬编码`COLAV_STRICT`且solver strict=true；Assembler也能生成parity preparation。因二者是分离入口，evidence必须同时记录expected profile、actual preparation/slack bounds和solver options，防止标签/准备不一致。[R18][R20] | 项目源码 | 高 | 高 | 高 |

#### 本地实验边界

- 环境：Candidate 3 clean `1f459d8`，CasADi 3.7.2，wheel内Ipopt。
- `route_speed_cold` strict：`Solve_Succeeded`，7 iter，terminal stats `inf_pr≈2.90e-7`、`inf_du≈1.70e-5`；独立stationarity max `≈1.70e-5`。
- `head_on_starboard` strict：`Solve_Succeeded`，10 iter，terminal stats `inf_pr≈5.83e-8`、`inf_du≈1.26e-3`；独立stationarity max `≈2.21e-4`。
- 仅两条N=8 fixture；证明“证据可取得与数值不等同”，不证明80×15s production阈值或p95。

### Batch-02 · continuous hull safety、uncertainty、target scope与static ENC hazard

> 本批使用Candidate 3 clean `1f459d8`源码/测试、NIST/IMO官方资料、C2A一手论文与只读计算。以下是证据，不是最终裁决；BL在用户确认前保持OPEN。

| 盲区 | 证据回答 | 证据 | 检索置信 | 来源权威 | 场景适用 |
|---|---|---|---|---|---|
| BL-03/12 81点是否真能做80区间同步复核 | 可以从Candidate 3 assembly证据构造：own path经`_native_trajectories`成为当前实测点+80个积分终点；target predictions为同一`sim_time`下0..1200s共81点。当前core `_continuous_cpa`仍只用80个pre-step点、selected targets与79区间，漏最终15s，不能作为L4证据。[R22] | 源码+测试 | 高 | 高 | 高 |
| BL-03 footprint连续净距 | node无接触不能推出区间无接触；C2A论文与项目物理oracle都按连续刚体运动求contact。对于L4 50m hard clearance，包围圆lower bound可独立证明“至少50m”，但会比精确矩形更保守；它不是“真实矩形净距”等值。[R27..R29] | 一手论文+源码+推导 | 高 | 高 | 高 |
| BL-13/68 如何避免Planner自评 | Evaluator hard-clearance、rectangle contact、grounding由Evaluator聚合；直接读取其verdict会自评。项目已有planner-neutral geometry，但若production与Evaluator调用同一实现仍有shared-defect风险。独立小型analytic circle/segment oracle可提供不同实现路径；精确C2A可留事后Evaluator交叉验证。[R27..R29] | 源码+推导 | 高 | 中高 | 高 |
| BL-21/38 safety target scope | solver admission最多16 targets；Assembler却保留全部PlannerInput tracks、要求Lifecycle decision一一对应，并为全体发布81点prediction。故动态L4无需受solver selected集合限制，可按Lifecycle health检查全部fresh/usable tracks；但当前无全体数量上限及显式排除reason，性能/typed reconciliation仍需后续裁决。[R22][R32] | 源码+测试 | 高 | 高 | 高 |
| BL-65 当前uncertainty margin含义 | `sqrt(9.210*lambda_max(P_pos))`是二维Gaussian 99% confidence ellipse的方向无关包围半径；前提是Gaussian与covariance校准。它是per-sample probability，不是81点联合99% guarantee，也不是distribution-free bound。[R24] | NIST+推导 | 高 | 高 | 中高 |
| BL-65 当前实现是否逐stage传播 | 否。tracker的4x4 state含velocity并用`F P F^T+Q`传播；Assembler仅取当前position block，把同一margin复制81次，忽略velocity/cross-covariance/process noise。God profile covariance=0时该缺陷不影响当前固定seed G3；非God/KF claim不能沿用此证据。[R25] | 源码 | 高 | 高 | 高 |
| BL-65 能否直接把tracker CV covariance推1200s | 不宜。按当前默认`P0/q`机械传播，99%半径60s已约531m、1200s约46.14km；这暴露的是long-horizon model/ODD张力，不是合理阈值。需要God-only scope，或另行定义经校准的intent/process model、joint-risk budget及有效预测时域。[R26] | 只读项目实验 | 高 | 中高 | 中 |
| BL-63/65 如何防margin重复计入 | solver `effective_cpa_hard_m`已混入50m、双方包围圆、当前covariance与frozen target一步位移补偿，且对selected targets取最大allowance。L4同步几何应从trusted physical 50m与per-target facts重算；不能再把`effective_cpa_hard_m`当基础物理净距，也不能把一步补偿解释为uncertainty。[R23][R33] | 源码+测试 | 高 | 高 | 高 |
| BL-22 static ENC是否是独立安全证据 | 是独立风险种类：动态targets全安全仍可grounding。当前Mid-MPC不要求ENC且无预测static check；Evaluator事后hard gate检查Ship0 grounding。IMO ECDIS标准也把safety contour/prohibited area/isolated danger look-ahead作为route planning/monitoring职责。证据不决定必须放进L4，但证明“无ENC仍宣称完整Playground safety PASS”不成立。[R30][R31] | 官方标准+源码 | 高 | 高 | 中高 |

#### 关键适用边界

- 当前发布G3 tuples为`God` tracker；本批只支持deterministic target mean/zero covariance claim，不扩大到KF/真实感知。
- 包围圆连续lower bound是hard-safety充分条件：通过可信，拒绝可能保守；精确矩形净距仍由独立Evaluator提供。
- 99%是单时刻Gaussian confidence语义；不等于全81点、全targets、全run 99%。joint-risk allocation仍未裁决。
- static hazard模块归属、ENC缺失时`FAIL`还是`N/A`、以及是否把`requires_enc`改为true，留Step4/5；当前只确认claim边界。

### Batch-03 · COLREG plan semantics、action timing与Lifecycle authority

> 本批使用COLREG官方/政府文本、AMSA/MAIB官方指导、Candidate 2/3 clean `1f459d8`源码与focused test。以下是证据，不是最终裁决；BL在用户确认前保持OPEN。

| 盲区 | 证据回答 | 证据 | 检索置信 | 来源权威 | 场景适用 |
|---|---|---|---|---|---|
| BL-05 early/substantial是否有法规统一数值 | 没有。Rules 8/16只给出positive、ample time、readily apparent、early、substantial、safe distance及持续监视等定性要求；不能把5°、30°、10s或某TCPA包装为COLREG常数。[R34] | 官方规则 | 高 | 高 | 高 |
| BL-25 OT是否必须starboard-only | Rule13只要求keep out并持续到finally past and clear，不指定唯一侧。Rule34明确存在两侧超越信号；MAIB仅把“目标留在本船port侧”作为标准态势good-practice。故标准Playground可profile优先starboard，但受限/镜像态势必须允许Lifecycle锁定port。[R35][R36] | 官方规则+官方指导 | 高 | 高 | 高 |
| BL-25 当前标准OT会不会再左转 | Candidate 2 centerline tie明确选择STARBOARD；两侧clearance不等时选更安全侧，commit后不翻转。focused unit三例`3 passed`。当前closed-loop标准OT测试仍只断言`port|starboard`，因此尚不能单独证明standard-starboard claim；是否收紧留Step4/5裁决。[R37][R41] | 源码+测试 | 高 | 高 | 高 |
| BL-26 HO/CS/OT plan predicate | Rule14支持HO signed-starboard action+port-to-port；Rule15支持CS-GW pass-astern/avoid-ahead；Rule13支持OT locked corridor直到past-clear；Rule17支持stand-on hold→MAY/MUST。均可从同步trajectory和immutable directive重算，不能用求解器intent标签代替。[R35][R40] | 规则+几何推导 | 高 | 高 | 高 |
| BL-26 stand-on predicate数据是否够 | 当前不够做跨cycle独立证明。Lifecycle内部有`standon_since_s`，但`TargetDecision`未暴露stand-on entry own course/speed；若L4每次以当前状态重置baseline，连续小偏航可逃逸hold检查。[R38] | 源码 | 高 | 高 | 高 |
| BL-27 early/action deadline数据是否够 | 当前有baseline、required change、action achieved、ROT，但无`committed_at_s`、first-action deadline、latest-safe achievement deadline或reachability certificate。commit event只在发生cycle可见，后续stateless L4不能可靠恢复deadline。[R38][R39] | 源码 | 高 | 高 | 高 |
| BL-28 初始wrong-side如何区分候选缺陷 | 要可靠判定，必须区分“输入时已在wrong side”与“候选继续恶化”：可用first executable command、signed baseline progress与reachable deadline判定单调修正。只检查第一个15s node会漏立即错误控制；具体瞬态容差仍属trusted profile。[R34][R38..R40] | 规则+项目推导 | 高 | 中高 | 高 |
| BL-29 跨solve小步动作如何识别 | Candidate 2固定commit baseline并按actual heading累计`action_achieved`，因此L4无须自有FSM；bundle保留baseline即可识别succession of small changes。stand-on仍需独立entry baseline字段。[R34][R38][R39] | 规则+源码 | 高 | 高 | 高 |
| BL-30 15s grid能否证明及时动作 | 不能单独证明action onset。L4至少需检查first executable command及其piecewise interval语义，再检查后续reachable achievement；81点trajectory用于通过/保持，不能把`t=15s`首node当真实起动时刻。[R34][R39][R40] | 规则+源码 | 高 | 高 | 高 |
| BL-10 aggregate冲突由谁解释 | Lifecycle是唯一兼容性authority：同侧合并；安全STOP可输出STOP；否则typed `MANEUVER_CONFLICT`。Assembler做防御性一致性检查；L4只对每目标hard conjunction验候选，不能重选方向或优先目标。[R42] | 源码 | 高 | 高 | 高 |
| BL-68 COLREG oracle独立性 | Production L4应实现pure trajectory predicates；不调用Evaluator score/FSM，也不重跑Lifecycle分类。Evaluator继续以actual run提供独立事后oracle。当前项目缺per-solve plan-level oracle，现有test只证明run末结果。[R40][R41] | 源码+推导 | 高 | 中高 | 高 |

#### 关键契约缺口

- Lifecycle需向immutable bundle补充：`commit_time_s`、`first_action_due_s`、`achievement_due_s`、signed action contract、reachability basis。
- Stand-on需补充：entry time、own course/speed baseline、允许偏差来源；否则无状态L4不能防跨cycle drift。
- L4只验证Lifecycle选择的OT side。standard centerline强制starboard应在Lifecycle profile/test固化，不在L4偷换side。
- Prediction达到“未来past-clear”不改变当前Lifecycle phase；实际release仍只由下一cycle actual observation推进。

### Batch-04 · active-prefix trackability、command semantics与quality evidence

> 本批使用Candidate 3 clean `1f459d8`源码、current-code只读probe、focused tests及一手论文。以下是证据，不是最终裁决；BL在用户确认前保持OPEN。

| 盲区 | 证据回答 | 证据 | 检索置信 | 来源权威 | 场景适用 |
|---|---|---|---|---|---|
| BL-04 active Plant envelope是否存在 | 不存在。标准HO/CS/OT实际执行Viknes+FLSC；当前bundle却只携静态`published_kinematic_csog` ROT/decel，且明确`NO_LIVE_PLANT_OR_GNC_ENVELOPE`。因此L3 rate rows不能证明active plant可跟踪，当前只能声明Playground固定plant的经验闭环通过，不能形成跨plant证书。[R44][R45] | 一手论文+源码 | 高 | 高 | 高 |
| BL-31 trackability检查多长 | 当前证据只能把hard execution claim绑定到“现在到next solve”的active prefix：这是会实际下发且可由当前state、interval commands与active plant envelope复核的部分。远期1200s可做静态command-envelope筛查，但在没有tracking tube/model-error bound时，不能称完整plant rollout已认证；远期误差还必须进入safety margin才可扩展claim。[R12][R44][R47] | 一手论文+源码 | 高 | 高 | 中高 |
| BL-32 heading/surge与COG/SOG转换 | 当前有实质错位。core位置积分变量物理上是COG/SOG，PassThroughCS也消费course/SOG；facade初值却直接用body `psi/u`。nonzero sway probe中输入`psi=0,u=4,v=1`，真实COG/SOG为`14.036°/4.123m/s`，core收到`0°/4m/s`。转换需以地固NE velocity为权威，不能只改字段名掩盖。[R43][R46][R47] | 一手论文+源码+probe | 高 | 高 | 高 |
| BL-42 control trajectory语义 | Mid明确输出81个state knots、80个interval commands；Adapter却把80列command当knot线性插值。probe中`[10°,20°]`的15s intervals在`t=5s`输出`13.333°`，而piecewise-constant应仍为`10°`。因此fresh/hold/L4/GUI必须共享显式interval start/end与hold policy，不能只靠shape推断。[R46][R47] | 源码+probe | 高 | 高 | 高 |
| BL-33 tracking error与50m关系 | 当前没有经校准tracking tube。Assembler的one-step compensation是frozen k+1/k indexing补偿，不是plant tracking error；把未界定误差忽略会高估clearance，把任意常数叠加又会重复/过度保守。证据只支持“有同源per-stage/prefix bound才可加入safety radius”，具体值未知。[R12][R23][R44][R45] | 一手论文+源码 | 高 | 高 | 中高 |
| BL-06/34 quality hard还是warn | 外部文献把smoothness、route deviation、progress、ETA等作为分离trade-off metrics；没有支持本项目通用hard阈值。当前证据可区分：触发已确认安全/COLREG/trackability边界的是对应hard failure；仅难看、抖动或低效但仍守hard contract的quality量尚无依据升级为reject。[R49][R50] | 一手论文 | 高 | 高 | 中高 |
| BL-34 quality物理定义 | 可观测量有：wrapped course/speed一阶及二阶变化；overlap-aligned previous accepted command/path churn；polyline arc-length progress与orthogonal contour error；`route_recovery_allowed`后回归时间。它们必须分量、单位化输出，不能压成单一score后丢失原因。[R48..R50] | 一手论文+源码推导 | 高 | 中高 | 高 |
| BL-35 5s/15s重叠比较 | state knots可按绝对时间做position/shortest-angle interpolation；piecewise-constant interval commands应按区间取值，不能共用当前`_sample_trajectory`。比较窗口只能取previous/current两份计划在同一absolute-time上的重叠区，并保留parent receipt；否则index-to-index比较错位10s。[R46][R47] | 源码+推导 | 高 | 高 | 高 |
| BL-36 route reference是否足够 | 当前nearest anchor虽来自polyline，但core只持单bearing直线；弯曲route上的full-horizon cross-track/progress/recovery会失真。质量证据需稳定polyline+arc-length projection；COLREG committed corridor可保留局部直线，但不能冒充全route reference。[R48][R50] | 一手论文+源码 | 高 | 高 | 高 |
| BL-37 raw objective能否做acceptance | 不宜。heading/speed/route为context-dependent horizon sums，COLREG受targets/reference影响，route origin/bearing也随cycle变化；即使component齐全，raw total或跨cycle下降都不是统一物理质量证书。可保留为solver diagnostic；是否另建归一化指标留Step4/5。[R48] | 源码 | 高 | 高 | 高 |
| BL-67 threshold calibration现状 | 当前五个fixed-seed PASS场景与现有papers都不能给出independent hard阈值；focused suite `21 passed`甚至未发现COG/heading及interval/knot错位。必须另有未参与调参的negative/boundary corpus或真实plant envelope，才能校准quality/action/trackability阈值。[R46][R49..R51] | 源码+测试+论文 | 高 | 高 | 高 |
| BL-68 independent oracle边界 | trackability oracle需从trusted active-plant contract独立rollout/包络first executable prefix，不能复用candidate的reduced trajectory作为自证；quality oracle需从canonical route、absolute-time plans与commands重算物理量，不能读raw objective或Evaluator score。当前二者均缺production实现。[R44][R47..R51] | 一手论文+源码推导 | 高 | 中高 | 高 |

#### 关键适用边界

- 本批证明当前contract/语义缺口，不证明Viknes+FLSC具体tracking tube数值。
- 远期1200s trajectory仍用于dynamic safety/COLREG prediction；“不做完整plant trackability hard proof”不等于删除远期trajectory。
- `piecewise-constant`是当前Mid core每stage单一`psi/u`与Adapter显式control horizon的自然语义；若未来采用ramp/interpolation，必须作为新versioned policy裁决。
- quality metrics与hard thresholds分开：本批回答“能测什么、现有证据支持到哪里”，不在Step3决定reject/warn数值。

### Batch-05 · hold freshness、rejection、accepted-plan handoff与deadline

> 本批使用Candidate 3 clean `1f459d8`、当前Adapter/Session/GUI源码、只读stale-hold probe、focused tests、Ipopt/CasADi官方文档与一手论文。以下是证据，不是最终裁决；BL在用户确认前保持OPEN。

| 盲区 | 证据回答 | 证据 | 检索置信 | 来源权威 | 场景适用 |
|---|---|---|---|---|---|
| BL-07/41 held plan当前是否仍被证明 | 否。HOLD由周期时钟触发，直接继承旧`SUCCESS/feasible`；100m ownship偏差probe仍输出旧轨迹命令。至少“当前到next solve active prefix”必须按当前state/context重验；是否每个hold完整重跑1200s全部层、以及成本，当前无基准，留Step4/5。[R52][R53][R60] | 源码+probe+论文 | 高 | 高 | 高 |
| BL-43 immediate replan需要哪些触发 | 当前没有任何事件触发，只有固定5s时钟。已有immutable identities可检测ownship deviation、target key/generation/health集合、Lifecycle obligation、profile/policy/ENC事实变化；这些变化若使hold证据失效，就必须在同cycle选择“重求或拒绝”，不能继续标HOLD SUCCESS。[R52..R54] | 源码+推导 | 高 | 高 | 高 |
| BL-09/46 拒绝后能否重试/恢复 | 当前fresh异常使Session直接`FAILED`，无暂停/下一cycle恢复；hold失效也没有重求。现有证据不提供自然“重试次数”，只证明任何same-algorithm重求必须是commit前、总deadline内、显式有界attempt。Step2已选hold最多一次重求；fresh rejection与warm失败是否重试仍留Step4/5。[R54][R61] | 源码 | 高 | 高 | 高 |
| BL-18/45 outcome与public status如何共存 | 当前coarse `PlanStatus`不足以承载layer/target/witness原因，但已有details code/owner模式。证据支持稳定coarse transport status与完整layer failure list分离，避免扩展一个状态对应每个L4原因；integrity short-circuit、primary precedence与UNKNOWN/N/A hard性仍是Step4裁决。[R55] | 源码+类型审计 | 高 | 高 | 高 |
| BL-39 conflict failure如何保持typed | Lifecycle `MANEUVER_CONFLICT`表示决策义务不可共同表达；Assembler `CORE_CAPABILITY_MISMATCH`表示冻结core不能实现一致输入。二者都可对外映射coarse `INVALID_INPUT`，但receipt必须保留不同owner/code/identity，L4 defensive rejection不能把它们改名为普通safety failure。[R42][R55] | 源码 | 高 | 高 | 高 |
| BL-47 rejected candidate是否会泄漏 | 当前成功路径接近commit-after-validation，但failure trace并不原子统一：某些post-solve异常保留旧trace/solution；旧solution也仍在对象中。Candidate 1需要一个明确事务边界：L4 verdict完成前candidate、receipt、current plan、hold source均不可见；拒绝后不得回用旧plan或candidate seed。[R54][R58][R59] | 源码+控制流审计 | 高 | 高 | 高 |
| BL-48 rejection UI/event可见性 | 当前server/frontend把`latest_planner_solve`定义为最近成功执行solver的trace；HOLD或无solver rejection会回退画旧预测。故需拆分latest attempt与active accepted plan时间线，rejection带attempt identity、L3状态、L4 layer failures且selected command为空；历史accepted plan只能显示为历史，不能成为隐式控制。[R59] | 源码 | 高 | 高 | 高 |
| BL-49 neutral receipt最小父链 | Candidate 3已有request→problem→prepared→solver→acceptance父链与L4 placeholder，但placeholder在真实L4前被hash/持久化。生产receipt至少需绑定parent solver hash、cycle/session identity、policy/profile/build/formulation/layout/grid、target/lifecycle set、accepted plan hash、layer verdict/witness摘要与裁决时间；具体canonical schema留Step4/5。[R6][R58] | accepted design+源码 | 高 | 高 | 高 |
| BL-08/50 warm eligibility与rejected seed | 当前固定cold，没有性能污染也没有收益。Ipopt只规定数值warm输入，不提供安全资格；因此eligibility必须由L4 receipt独立证明。正常过期/结构不兼容应显式cold，hash/identity损坏应invalid；session epoch、profile/layout/grid、target/lifecycle/side、绝对时间重叠与deviation是现有bundle可检查维度。[R56][R57] | 官方文档+accepted design+源码 | 高 | 高 | 高 |
| BL-51 5s/15s怎样shift seed | 5s不是15s整数stage，不能删一个column。Candidate 3 accepted design已限定primal-only：state knots按absolute time插值、interval commands按piecewise-constant取值、只使用overlap support、terminal tail deterministic cold-fill、current problem重建slack、dual v1禁用。[R46][R56][R57] | accepted design+官方文档+源码推导 | 高 | 高 | 高 |
| BL-52 warm是否改善实时性/确定性 | UNKNOWN。CasADi/Ipopt确认initial guess可能改变非凸局部解与迭代，但当前没有cold-vs-warm 0/1/16-target重复基准，也没有accepted-plan handoff实现。不能把预期加速写成能力；cold deterministic必须保留基线。[R56][R57][R62] | 官方文档+测试缺口 | 高 | 高 | 中 |
| BL-53 L3/L4 acceptance命名 | 当前`accepted_by_quality_gate`实为L3 candidate selection，L4 placeholder另有owner；若都叫acceptance会混淆。证据支持schema明确分为`solver_candidate_selection`与`production_plan_acceptance`，后者才产生dispatch/receipt/warm资格；最终字段名留Step4/5。[R58] | 源码 | 高 | 高 | 高 |
| BL-59 late result何时失去资格 | 当前deadline只包`_solve` wall time，late successful candidate降为`TIMEOUT_FEASIBLE`后仍可commit；没有给L4保留预算或完成后freshness复核。同步仿真不推进不等于控制deadline有效。production eligibility需在原子commit前检查总critical-path deadline与bundle/context freshness，具体budget留性能batch/Step4。[R61] | 源码+时序审计 | 高 | 高 | 高 |

#### 关键适用边界

- 本批不把“最多一次重求”伪装成论文结论；它是Step2已确认的bounded no-fallback policy，Step3只验证当前代码与deadline约束。
- warm start仅是可选性能机制；Candidate 1 correctness不能依赖它，且rejected/parity/hold-only结果均无资格。
- hold revalidation的最小hard scope已有证据，完整1200s复核成本、exact deviation threshold与retry deadline仍需Step4/性能batch裁决。
- rejection后Session fail-stop是当前事实，不代表最终架构只能有terminal failure；任何恢复都必须不下发旧plan、不跨越L5 fallback边界。

### Batch-06 · evidence schema、artifact、canonicalization与claim governance

> 本批使用Candidate 2/3 accepted design、Candidate 3 clean `1f459d8`源码、19份本地artifact只读统计、RFC 8785及focused tests。以下是证据，不是最终裁决；BL在用户确认前保持OPEN。

| 盲区 | 证据回答 | 证据 | 检索置信 | 来源权威 | 场景适用 |
|---|---|---|---|---|---|
| BL-01 Candidate 3是否仍阻塞schema设计 | 不再阻塞设计。clean `1f459d8`已固定五段namespace/hash链、81点prediction、strict preparation与cold seed placeholder；Candidate 1只需替换真实L4 placeholder并增加accepted receipt handoff，不修改L1/L2数学责任。[R63] | accepted implementation | 高 | 高 | 高 |
| BL-11 full与inline体积/延迟 | 当前full artifact约99..123KiB raw、6..24KiB gzip；inline assembly有8KiB门。同步落盘本机microbenchmark很小但非16-target/L4 p95，且不应进入authority path。证据支持保留full artifact+bounded inline summary，exact queue/size budget留Step4/性能batch。[R64][R66..R68] | artifact+probe+accepted design | 高 | 高 | 中高 |
| BL-17 trusted policy authority | 当前request hash能证明“candidate收到什么config”，不能证明该config来自独立trusted authority；integration同时提供50m/profile并生成candidate。L4 receipt必须绑定runtime-resolved L4 policy/profile hash，candidate事实仅作对照，不能自带降低门槛。[R33][R63][R66] | 源码+authority分析 | 高 | 高 | 高 |
| BL-44 shifted hold evidence | 当前HOLD不切出remaining trajectory，不记录parent receipt/validation，GUI自己按solve time猜index。hold record需引用parent accepted receipt、absolute-time shifted state/interval support、当前context hash、revalidation verdict及active command；不签新production receipt。[R69] | 源码 | 高 | 高 | 高 |
| BL-54 full/inline/render一致性 | 现有三层骨架成立：full含raw/replay，inline含hash/ref，render含ENU/time-axis projection；但真实L4 verdict/witness缺失。render应是receipt/full artifact的非权威投影，三者用同一acceptance hash关联，GUI字段不得补写authority facts。[R66][R70] | 源码+测试 | 高 | 高 | 高 |
| BL-55 active/latest双时间线 | 当前Adapter、server、frontend各持一份旧plan/solve缓存，rejection会被上一solve遮蔽。唯一canonical timeline应由Adapter发布latest attempt、active accepted plan、executed hold三种关系；server/frontend仅投影，不自行推断authority。[R59][R69] | 源码 | 高 | 高 | 高 |
| BL-56/61 persistence/backpressure | 当前同步sink无queue/retention/shutdown语义；sink失败只返回INCOMPLETE且继续控制，符合既有责任边界。需要bounded async writer状态机与可观察backpressure，但磁盘失败不能改变已完成的in-memory verdict/command；只能使persisted-evidence/capability claim不完整。[R64][R67][R68] | 源码+accepted design+probe | 高 | 高 | 高 |
| BL-57 witness序列化 | 当前render frame/time明确，但target字段重复且solver witness只有row index；L4 witness需统一绑定layer/code、`TrackKey(target_id,generation)`、ENU、quantity/unit、absolute time、sample/segment与measured/required margin。否则artifact虽有hash，仍无法人工/独立oracle重放失败原因。[R57][R70] | 源码+schema分析 | 高 | 高 | 高 |
| BL-60 canonical float/hash | 当前hash在同一Python/version内可重复，但不是声明的RFC 8785 canonical JSON；`-0.0/0.0`和integer/float表达会造成物理等价内容hash不同。需版本化canonicalization并明确number normalization、nonfinite拒绝、stable list ordering与telemetry exclusion；采用JCS还是项目内规范留Step4/5。[R65][R66] | 标准+probe | 高 | 高 | 高 |
| BL-66 policy变更如何失效旧证据 | 当前G3 tuple不绑定L4 policy/plant/build/scenario/Evaluator hashes，无法自动失效。receipt、warm seed与capability evidence必须引用这些dependency identities；任一authority hash改变，旧receipt不得warm，新policy下G3需重跑，历史artifact仍只读保留。[R63][R71] | 源码+治理分析 | 高 | 高 | 高 |
| BL-68 evidence oracle独立性 | 现有mutation test只证明hash链可检出篡改，不证明L4 verdict正确。需要独立receipt verifier从full artifact按schema/hash/units重算各layer或对照negative corpus；不得调用production acceptance aggregate helper。当前此oracle不存在。[R66][R72] | 源码+测试缺口 | 高 | 高 | 高 |

#### 关键适用边界

- RFC 8785只回答canonical representation，不回答本项目哪些字段应进入receipt、failure precedence或policy ownership。
- 本机3.17ms median不是持久化性能门；APFS cache、artifact大小、并发与16 targets均未覆盖。
- `persistence=INCOMPLETE`不撤销同周期内存裁决，但该run不能宣称完整可复核acceptance/capability evidence。
- GUI render projection不是第四份truth；必须由canonical record机械投影，禁止frontend推导新的接受结论。

### Batch-07 · performance、negative corpus、8010与regression matrix

> 本批使用Candidate 3 clean `1f459d8` benchmark/test inventory、只读性能probe、当前full regression与既有8010 evidence。以下是证据，不是最终裁决；BL在用户确认前保持OPEN。

| 盲区 | 证据回答 | 证据 | 检索置信 | 来源权威 | 场景适用 |
|---|---|---|---|---|---|
| BL-15 NLM缺失是否仍阻塞 | 不阻塞。用户已授权web替代；Batch01..07已使用Ipopt/CasADi/IMO/COLREG/NIST/RFC官方资料及一手论文，并与项目源码/probe交叉验证。未修改知识库或依赖。[R14..R81] | 官方/一手资料+项目事实 | 高 | 高 | 高 |
| BL-16/58 solver与L4预算是否有基础 | 有baseline、无最终预算。cold solver 16-target五样本p95约2.159s；全selected commitment单次约1.873s solver/2.046s facade wall。相对20s存在观察余量，但样本/态势不足，不能直接分配L4 hard budget或承诺p95。[R73] | benchmark+真实solver probe | 高 | 高 | 中高 |
| BL-40/62 O(TN) acceptance是否明显不可承受 | 未发现架构性性能阻碍。独立16×80 swept geometry p95约4.89ms，支持bounded O(TN)；但full L4、hold、trackability与artifact尚不存在，因此full p95/p99仍UNKNOWN，必须实施后测量，不能用几何probe代替。[R74] | independent probe | 高 | 中高 | 中高 |
| BL-69 最小negative/metamorphic corpus | 现有66个Mid tests提供强上游基础，但不覆盖L4。SC-73..82已覆盖每layer单缺陷、cross-layer多失败、hold/reject/receipt、real closed-loop、8010、performance、dependency invalidation及四类metamorphic；这可作为类别最小骨架，具体fixture数量留Step4/5。[R75][R76][R81] | test inventory+coverage derivation | 高 | 高 | 高 |
| BL-70 capability如何绑定治理身份 | 现有tuple不能自动失效。最小依赖集合是L4 policy、active plant profile、algorithm/formulation/build、tracker、scenario content、Evaluator/predicate、seed与acceptance corpus root；tuple key可保持稳定，但evidence必须绑定dependency document/hash，任何不匹配降级为unverified并重跑。[R71][R78][R80] | 源码+治理分析 | 高 | 高 | 高 |
| BL-71 8010验收清单 | 既有accepted runtime seam可复用；Candidate 1必须同一实施树分别证明accepted/rejected：listener PID/cwd→HTTP session→real IPOPT attempt→L4 verdict/receipt→artifact digest/readback→selected command有/空→GUI latest-attempt/active-plan一致。当前没有L4 event，故不提前宣称通过。[R77] | runtime observation+existing seam | 高 | 高 | 高 |
| BL-72 performance/determinism/flakiness | 当前5-sample solver表不足。实施验收需记录完整环境和case identity，分别测fresh/hold、0/1/16、cold/warm、full mandatory layers的p50/p95/p99/max；同一canonical bundle重复验证verdict/hash/failure ordering稳定，timing/path排除；具体repeats和阈值留Step4/5。[R73][R74][R78] | benchmark gap analysis | 高 | 高 | 高 |
| BL-73 baseline与增量范围 | Candidate 3当前full baseline为`464 passed,2 skipped`；Candidate 1不得修改8条parity expected，需新增L4 contract/negative/performance/runtime tests，并重跑Lifecycle、Assembler、Mid core/integration、全部七类闭环、artifact/API/GUI/capability及full suite。[R75][R79][R80] | full test+git scope | 高 | 高 | 高 |

#### 关键适用边界

- 16-target现有p95仅5样本且contacts不构成adversarial convergence corpus；只用于证明“没有已知20s级阻碍”。
- analytic geometry probe使用独立实现，适合复杂度预估；不证明production L4正确性或完整时延。
- SC-73..82是claim-category coverage，不是所有初始条件、船型、海况或真实感知空间的形式完备证明。
- 8010本轮仅只读listener identity；Candidate 1实现前没有L4 accepted/rejected runtime evidence。

## 4. Step4 汇总分析与推荐

> 本节推荐在用户逐项确认前均为DRAFT；确认后才写入VR/ALT注册表并标final。

### Step4-DP01 · Module责任、Depth与Seam（final）

#### 初步推荐

采用一个**深、纯、无状态、确定性Plan Acceptance Module**。外部只暴露一个窄Interface：消费单个immutable/versioned acceptance request，返回单个immutable layered result。Seam固定在“L3已选定solver candidate并形成完整bundle”之后、“Adapter原子提交command/active plan/receipt”之前。Module内部编排L4 mandatory layers；不改变candidate，不产生替代轨迹。

| 维度 | 推荐草案 |
|---|---|
| Module | `MidMpcPlanAcceptance`（概念名；最终命名Step6冻结） |
| Interface形态 | `evaluate(request) -> result`；无第二个public method，无隐式全局读取 |
| 输入责任 | 调用方提供完整candidate、trusted policy/context、identity/hash/time/target/execution facts；细节由DP-02裁决 |
| 输出责任 | layered verdict、aggregate dispatch eligibility、failures/witnesses、canonical evidence/receipt material；细节由DP-03/15裁决 |
| Adapter责任 | schedule、deadline、hold/replan、原子commit、failure/session mapping、accepted-plan handoff |
| 明确排除 | Encounter/Lifecycle决策、OCP/bounds、IPOPT、轨迹修正、fallback/MRM、Evaluator事后评分、artifact I/O、capability promotion |
| 内部seams | 允许private layer evaluators供Module自身测试；不成为caller需学习的多个public interfaces |

#### 证据链

| 证据 | 推导 |
|---|---|
| [R6][R63] Candidate 3已产完整五段candidate evidence | L4可位于solver后，不必侵入L1/L2或L3 |
| [R7] 用户七层设计把L4.1..4.5置于求解后、执行前 | Seam与业务分层一致 |
| [R11][R13][R60] independent/multi-step safety filter文献 | 一次solver success或旧hold布尔值不足以证明下发资格 |
| [R1..R4][R52..R55] 当前检查分散且failure/hold语义不完整 | 深Module可获得locality；删除它会让复杂度重新散回Facade、Adapter、GUI与tests |
| [R75][R79] 现有pure solver/Assembler/public runtime seams与full baseline | 可以新增Module而不修改frozen方程/parity expected |

#### 备选与弃用草案

| 方案 | 优点 | 弃用理由 |
|---|---|---|
| A 深pure Module（推荐） | 单一truth、可replay、无状态、caller Interface小、各layer集中 | 实施初期需构造完整bundle并调整commit顺序 |
| B Facade/Adapter中追加若干`if`检查 | diff最小、短期快 | shallow；职责继续分散，hold/reject/evidence规则多处漂移，删除后复杂度不会明显变化 |
| C Stateful acceptance controller同时拥有retry/warm/persistence | 可集中整条流程 | 越权进入Adapter/L5；状态破坏deterministic replay，扩大failure blast radius |
| D 直接复用Evaluator hard gate | 现成事后指标 | 发生太晚且形成Planner自评；不能验证candidate、hold或command提交前资格 |
| E 在IPOPT core内增加业务acceptance | 数值证据接近solver | 污染L3 frozen parity，强耦合COLREG/plant/UI事实，无法服务hold revalidation |

#### 风险、失效边界与验证

| 项 | 评估 |
|---|---|
| 实现风险 | **中高**：主要风险是bundle/Adapter事务集成，不是IPOPT数学修改 |
| 性能风险 | **中**：16-target solver有余量、几何O(TN)成本低；full Module p95仍UNKNOWN |
| 兼容风险 | **中**：需保持`MPCSolution/PlannerTrace`公共行为和8条parity expected |
| 失效边界 | trusted facts缺失、identity损坏、mandatory layer异常或预算耗尽均fail-closed；Module不修轨迹、不fallback、不沿用旧plan |
| 核心验证 | pure request重复得到相同verdict/hash/order；单layer与多layer negative；fresh/hold/reject public seam；8条parity不变；全部Mid闭环；真实8010 accepted/rejected；full regression |

#### 技术分解状态

DP-01只冻结Module位置、Depth与责任。Interface字段、layer taxonomy、数学检查、hold、commit、receipt、性能及测试分别由DP-02..18继续裁决；Step4结束时这些子项已全部裁决，技术分解缺口为0。

### Step4-DP02 · immutable input、identity、time与profile contract（final）

#### 初步推荐

采用单一immutable、versioned、self-contained `PlanAcceptanceRequest`。为保持Interface窄，request顶层只分四个typed namespace；Module调用期间不读取artifact、GUI、PlannerTrace、日志或mutable runtime object。

| Namespace | 内容与authority |
|---|---|
| `candidate` | L3选定candidate、public 81-state path、80 interval commands、全部target predictions、raw solver/prepared证据及五段parent hashes；仅陈述candidate facts，不定义接受门槛 |
| `authority` | runtime-resolved L4 policy、expected profile、ODD/clearance/tolerance、algorithm/formulation/layout/build与policy hash；由candidate之外的trusted provider产生 |
| `execution` | attempt identity=`epoch/sequence/sim_time/attempt_id`、current ownship、route/ENC availability、active plant capability、全部track/Lifecycle bindings、absolute time grid |
| `prior` | optional previous accepted receipt+plan摘要；只能用于cross-cycle quality/hold/warm eligibility，不能覆盖当前candidate mandatory checks |

所有数组在构造时copy并read-only；所有nested records frozen。request同时携带值与identity，不能只给hash或artifact reference。Producer负责物理事实转换，L4仍独立验证schema、父链、集合、时轴、frame/unit/profile一致性。

#### 关键契约

| 项 | 推荐草案 |
|---|---|
| Frame/unit | global/local均canonical ENU；distance=m、time=s、angle=rad；core变量按COG/SOG物理语义，不把body `psi/u`静默当等价 |
| Time grid | `reference_time_s=attempt sim_time`；81 state knots覆盖0..1200s；80 commands显式`[start,end)` interval、piecewise-constant；target同81点绝对时轴 |
| Target identity | `TrackKey(target_id,generation)`唯一；Lifecycle/input/all predictions/admitted/excluded/solver slots一一reconcile；excluded必须有typed reason |
| Profile proof | 同时携带expected profile、actual assembly preparation、solver options/bounds/slack与parent hashes；profile label不能自证strict |
| Canonical hash | 使用项目自有、versioned schema-specific canonicalization，不冒充RFC 8785；typed normalization后SHA-256，reject NaN/Inf，`-0.0→0.0`，physical numerics统一float representation |
| Stable ordering | targets=`TrackKey`；failures=`layer precedence/code/TrackKey/time`；witnesses=`layer/TrackKey/segment/sample/quantity`；unordered input先normalize |
| Hash exclusion | wall timing、artifact path、compressed bytes、GUI状态等telemetry不进入semantic hash；sim time、policy、candidate facts必须进入 |
| Offline replay | request本身足够evaluate；artifact persistence只保存/传输相同canonical document，不是在线依赖 |

#### 证据链

| 证据 | 推导 |
|---|---|
| [R6][R22][R63][R66] Candidate 3已提供81点、target predictions、prepared/raw及五段chain | 不需发明第二套solver/Assembler DTO；扩展真实L4 stage即可 |
| [R15][R18][R20] strict必须核对actual bounds/options/row units | expected/actual/profile不能合成一个字符串 |
| [R43][R46][R47] COG/SOG与body、state knots与interval commands存在实证错位 | frame/time/control semantics必须进入typed contract |
| [R32][R38][R70] target集合与generation/witness字段需要显式reconciliation | 不能只传selected target IDs |
| [R65] 当前JSON canonicalization对物理等价number form不稳定 | 需要versioned schema normalization；当前不引入未验证JCS实现 |
| [R52][R69] hold沿用旧trajectory且无parent receipt | prior/attempt/current context必须显式分离 |

#### 备选与弃用草案

| 方案 | 优点 | 弃用理由 |
|---|---|---|
| A 四namespace self-contained request（推荐） | authority清晰、single-call、offline replay、可hash | schema较大，需version治理与builder contract tests |
| B 继续传`MPCSolution+algorithm_details` | 改动最小 | free-form、缺raw/Lifecycle/authority，已发生字段与时轴漂移 |
| C 只传artifact hash/path，Module按需读取 | request很小 | I/O进入authority path；文件缺失/延迟影响控制；破坏纯函数 |
| D candidate自带policy并证明自己满足 | producer简单 | candidate既定义门槛又自证，可静默把50m降为30m |
| E 直接宣称当前`json.dumps(sort_keys)`为跨语言JCS | 无新normalizer | 与RFC 8785 number serialization不等价，`-0.0/0.0`已实证不同hash |

#### 风险、失效边界与验证

| 项 | 评估 |
|---|---|
| 实现风险 | **高**：schema跨Lifecycle/Assembler/Solver/Adapter，但Candidate 3已有大部分facts |
| 性能风险 | **低至中**：内存request避免在线I/O；copy/canonicalization需在full benchmark测量 |
| 演进风险 | **中高**：schema/canonicalization改变会失效receipt/warm/capability；必须major version+dependency hash |
| 失效边界 | 缺字段、mutable/nonfinite、parent mismatch、time/grid/frame/profile/target reconciliation失败均为integrity rejection；不继续解释不可信下游layer |
| 核心验证 | roundtrip+immutability；hash tamper；`-0/0` normalization；target order/translation/time/label metamorphic；cross-cycle/profile拼接拒绝；80/81 interval边界；16 targets；offline evaluate无I/O |

#### 技术分解状态

DP-02冻结输入结构、authority与canonical identity；layer outcome在DP-03、具体quantity tolerances在DP-04/17、receipt输出在DP-14/15继续裁决。当前不冻结Python类名或全部字段名，Step6技术规约统一命名。

### Step4-DP03 · layered verdict与aggregate decision（final）

#### 初步推荐

采用一个typed layered result，不使用单一布尔、单一score或exception-as-domain-outcome。每个layer返回统一`LayerResult`，aggregate由固定规则机械派生；primary failure只是projection，完整failure/witness列表始终保留。

| Layer | V1分类 | 主要事实 |
|---|---|---|
| `integrity` | mandatory hard | schema、immutability、finite、parent chain、cycle/profile/time/grid/target reconciliation |
| `numerical` | mandatory hard | termination、raw x/g bounds、strict slack、objective/KKT evidence |
| `safety` | mandatory hard | synchronized continuous hull clearance、uncertainty、适用的static hazard |
| `colreg` | applicable时mandatory hard | Lifecycle locked role/side/phase下的trajectory consistency |
| `trackability` | declared ODD内mandatory hard | first executable prefix、command/plant capability、rollout evidence |
| `quality` | advisory | churn、smoothness、progress、recovery；V1仅`PASS/WARN/N/A`，不单独reject |
| `evidence` | mandatory hard | canonical in-memory result/receipt material完整且可hash；durable persistence状态不属于此layer |

#### Outcome taxonomy

| Outcome | 语义 | Aggregate影响 |
|---|---|---|
| `PASS` | applicable check满足 | 不阻塞 |
| `FAIL` | 已证明违反要求 | mandatory→reject；advisory→warning |
| `WARN` | 未越过hard contract但需观察 | 不阻塞，必须可见 |
| `UNKNOWN` | 应检查但trusted facts不足 | mandatory→reject |
| `NOT_APPLICABLE` | 有typed applicability witness证明不适用 | 不阻塞 |
| `NOT_EVALUATED` | integrity short-circuit、预算耗尽或上游依赖失败，未执行 | mandatory→reject；不得伪装N/A |

`LayerResult`至少包含`layer/outcome/severity/code/owner/message/witnesses`；per-target result使用`TrackKey`。failure/witness按DP-02 canonical order保存。

#### Aggregate规则

1. 先运行`integrity`。若`FAIL/UNKNOWN/NOT_EVALUATED`，停止依赖不可信内容的layers；这些layers标`NOT_EVALUATED`。
2. integrity通过后，尽量收集全部独立mandatory failures；不采用last-error-wins。
3. 任一mandatory `FAIL/UNKNOWN/NOT_EVALUATED`→`REJECT`。
4. mandatory均`PASS/NOT_APPLICABLE`且evidence layer完成→`ACCEPT`；quality `WARN`不改变dispatch eligibility。
5. `MASS_PARITY`无论数学结果如何均为`DIAGNOSTIC_ONLY`，不得产production receipt或warm资格。
6. `NOT_APPLICABLE`必须携带applicability witness；缺witness按`UNKNOWN`。
7. persistence sink状态独立为`COMPLETE/INCOMPLETE/BACKPRESSURE`；不回写同周期in-memory decision，但会阻断完整evidence/capability claim。

#### Primary failure precedence

`integrity > numerical > safety > colreg > trackability > evidence > quality`。同layer再按`code/TrackKey/absolute_time`排序。该precedence只服务公共`PlanStatus/reason/GUI`投影；不删除并发失败。具体`PlanStatus`映射由DP-13裁决。

#### 证据链

| 证据 | 推导 |
|---|---|
| [R1..R4][R55] 当前coarse status/details无法稳定表达所有layer | 需要coarse transport与typed domain result分离 |
| [R15..R21] native status、original feasibility、KKT语义不同 | numerical不能压成`solver_success`布尔 |
| [R27..R29][R40][R44] safety/COLREG/trackability使用不同independent evidence | 必须分layer，不能合成单score |
| [R49][R50] quality为trade-off metrics，无通用hard阈值 | V1质量只warn，不单独reject |
| [R54][R67][R68] persistence失败不应改变控制裁决 | in-memory evidence integrity与durable persistence必须分离 |
| [R58] L3 candidate selection与L4 production acceptance不同 | `DIAGNOSTIC_ONLY/ACCEPT/REJECT`不能复用solver quality gate命名 |

#### 备选与弃用草案

| 方案 | 优点 | 弃用理由 |
|---|---|---|
| A layered typed result+derived aggregate（推荐） | 可解释、可复核、保留多失败、稳定投影 | schema和测试量增加 |
| B `accepted: bool, reason: str` | 最小Interface | 丢失UNKNOWN/N/A、多target、多layer、warm/retry/evidence语义 |
| C 所有layer转一个加权score | 便于排序 | safety/COLREG等hard义务可被其他分数抵消，单位无共同标尺 |
| D 第一个失败即exception | 实现直接 | 丢失其他独立失败，exception ordering影响结果，难以replay |
| E quality hard fail | 可强迫轨迹好看 | 当前无独立阈值证据，会拒绝安全直线/保守计划 |

#### 风险、失效边界与验证

| 项 | 评估 |
|---|---|
| 实现风险 | **中**：主要为taxonomy、aggregation与projection，不改solver方程 |
| 误拒风险 | **中**：mandatory UNKNOWN fail-closed；通过明确N/A applicability与V1 quality-warn控制 |
| 可观察性风险 | **低**：完整列表+primary projection优于当前last reason |
| 失效边界 | integrity失败后不解释candidate业务含义；budget/exception不得返回partial ACCEPT；persistence失败不撤销in-memory decision但claim incomplete |
| 核心验证 | 每outcome truth table；integrity short-circuit；simultaneous numerical+safety+COLREG failure；N/A无witness→UNKNOWN；quality-only WARN仍ACCEPT；parity→DIAGNOSTIC_ONLY；stable ordering/hash；persistence failure不改decision |

#### 技术分解状态

DP-03冻结taxonomy与aggregate语义；数值hard条件DP-04、各业务layer DP-05..10、失败到公共`PlanStatus`/Session映射DP-13、receipt/persistence DP-14..16继续裁决。

### Step4-DP04 · IPOPT numerical acceptance与KKT evidence（final）

#### 初步推荐

V1采用“**eligible termination class + original primal hard recheck + strict preparation proof + advisory KKT**”。Numerical layer只证明同一candidate在原始数值contract内可行；不证明业务安全、全局最优或控制可下发。

#### Mandatory hard checks

| 顺序 | Check | Failure语义 |
|---:|---|---|
| 1 | solver/formulation/layout/prepared/raw candidate identity与parent hash一致 | mismatch归`integrity`，numerical不继续 |
| 2 | `x/f/g/lbx/ubx/lbg/ubg` shape、row layout、active indices完全一致 | `NUMERICAL_LAYOUT_INVALID` |
| 3 | raw arrays、objective及必要components全部finite | `NUMERICAL_NONFINITE` |
| 4 | native/normalized termination进入受支持class | `TERMINATION_INELIGIBLE` |
| 5 | original variable bounds按quantity tolerance逐项复核 | `VARIABLE_BOUND_VIOLATION` |
| 6 | original constraint bounds按row-family tolerance逐项复核 | `CONSTRAINT_BOUND_VIOLATION` |
| 7 | strict preparation实际满足slack fixed-zero、`bound_relax_factor=0`及trusted options | mismatch归`integrity/profile`; solution slack超数值容差归`STRICT_SLACK_VIOLATION` |
| 8 | raw objective与独立graph evaluation/component sum在objective tolerance内一致 | `OBJECTIVE_INCONSISTENT` |
| 9 | callback/best-feasible candidate必须有同一点`x/f/g`、accepted iteration、seed improvement与primal witness | `INCUMBENT_EVIDENCE_INCOMPLETE` |

所有violation输出`index/row family/quantity/unit/measured/lower/upper/tolerance` witness。CPA m²、heading rad、speed m/s、position m、dimensionless rule rows分别配置；禁止统一`1e-3`。具体数值由DP-17冻结。

#### Termination classes

| Class | Numerical outcome | 限制 |
|---|---|---|
| `DESIRED_LOCAL_SOLUTION` | hard checks全过则`PASS` | 可声明“满足本地数值终止/原始primal contract”，不可声明global optimum |
| `ACCEPTABLE_LOCAL_SOLUTION` | 当前strict `acceptable_iter=0`下不应出现；出现则`FAIL`，除非未来policy显式版本化启用 | 不从Ipopt字符串自动提升 |
| `CALLBACK_FEASIBLE_NONOPTIMAL` | 同点raw/primal+objective-improvement gate全过可`PASS`，附optimality warning | 保留native callback-stop身份，不改写为Solve_Succeeded |
| `WALL_TIMEOUT_FEASIBLE` | original primal全过时numerical可`PASS`并附timeout warning | 最终dispatch仍受DP-13/16总deadline、freshness与consecutive policy |
| `INFEASIBLE/RESTORATION/INVALID_NUMBER/INTERNAL_ERROR` | `FAIL` | 不允许best-effort plan或fallback |

#### KKT/stationarity裁决

V1 **不把KKT设为hard gate**：

- terminal candidate有同点`lam_x/lam_g`时，独立计算stationarity、dual feasibility与complementarity，作为structured diagnostic。
- callback-selected incumbent当前没有同点multipliers；标`KKT_NOT_EVALUATED` warning，不拿terminal multipliers证明另一个candidate。
- 缺KKT不得声称local optimality quality；但若eligible termination+全部original primal+全部L4业务hard layers通过，不因未校准dual residual单独拒绝。
- 收集真实80×15s corpus后，才可通过新policy version把某项KKT门升级为hard；不在实现时临时拍阈值。

#### Numerical tolerance原则

| 类型 | 原则 |
|---|---|
| identity/shape/layout/finite | 零容忍 |
| fixed strict bounds/options | semantic零容忍；solution value允许quantity-specific floating diagnostic tolerance |
| variable/constraint bounds | row-family `abs_tol + rel_tol*scale`，scale定义随quantity固定；witness保留原单位 |
| CPA m² row | scale-aware数值复核；不得把m² violation或slack解释为物理m安全margin |
| physical safety | 不由numerical tolerance放宽；DP-05以m为单位独立重算50m净距 |

#### 证据链

| 证据 | 推导 |
|---|---|
| [R15][R16][R21] Ipopt区分desired/acceptable/timeout/restoration及scaled/unscaled量 | status和`inf_du`不能单独成为原始可行/最优证明 |
| [R17..R19] terminal multipliers可取，但public result/callback incumbent缺完整同点证据 | KKT可诊断，V1 hard gate证据不足 |
| [R18][R20] strict fixed-zero与mixed-unit/parity quirks | actual preparation与row-family tolerance必须显式复核 |
| [R22][R29] frozen core CPA摘要/row feasibility不证明continuous hull safety | numerical PASS不得替代DP-05 |
| [R73] callback feasible-nonoptimal路径已在真实strict benchmark出现 | 不能粗暴只允许`Solve_Succeeded`，也不能隐藏native status |

#### 备选与弃用草案

| 方案 | 优点 | 弃用理由 |
|---|---|---|
| A primal hard+KKT advisory（推荐） | 与现有证据/场景兼容，保留完整optimality诊断 | 暂不提供dual-hard质量保证 |
| B 只信Ipopt status/`success=true` | 简单 | 漏original bounds、strict slack、NaN、candidate错配和scaled semantics |
| C V1强制KKT hard | optimality证据更强 | callback incumbent无同点dual、80×15s阈值未校准，会无依据误拒 |
| D 所有slack/violation精确等于0 | 直观 | Ipopt数值噪声可约`-1e-8`，与浮点求解现实不符 |
| E 所有row统一`1e-3` | 配置少 | rad/m/s/m/m²物理意义不同，可能过松或过严 |
| F L4再调用一次solver验证 | 可产生第二意见 | 扩大deadline与非确定性，且不是独立oracle，违反single candidate acceptance |

#### 风险、失效边界与验证

| 项 | 评估 |
|---|---|
| 实现风险 | **中高**：需暴露terminal multipliers/graph evaluation且保持callback candidate identity |
| 误接受风险 | **中**：KKT不hard；通过明确不声明optimality及后续safety/COLREG/trackability hard layers控制 |
| 误拒风险 | **中高**：mixed-unit tolerance错误会影响生产；必须DP-17 table+boundary corpus |
| 兼容风险 | **低至中**：8条MASS parity expected不改；strict只新增复核/evidence fields |
| 失效边界 | numerical PASS仅为原始primal/termination资格；任何业务layer仍可reject；timeout最终资格不在本DP决定 |
| 核心验证 | status×primal truth table；NaN/shape/layout；x/g上下界；strict bounds/slack；objective重算；terminal KKT；callback同点/错点；mixed-unit边界；8条parity expected不变；真实80×15s strict路径 |

#### 技术分解状态

DP-04冻结数值检查流程及KKT V1 advisory地位；具体tolerance值DP-17、timeout commit DP-13/16、continuous physical safety DP-05继续裁决。

### Step4-DP05 · synchronized swept hull/static safety（final）

#### 初步推荐

V1 safety layer采用“**全部相关目标的同步连续保守船体净距 + profile-controlled static hazard hard check**”。L4从canonical physical paths独立重算，不信任solver CPA摘要、Assembler effective center floor或Evaluator verdict。

动态结论严格命名为`PLANNED_TRAJECTORY_HULL_CLEARANCE`：证明给定预测与不确定性contract下的计划几何安全，不外推目标必然照预测运动、active plant必然精确跟踪或全船global safety。

#### Dynamic target scope与identity

| 输入集合 | V1裁决 |
|---|---|
| execution snapshot中全部fresh、usable、safety-relevant TrackKey generations | 全部hard检查；含Assembler selected与unselected targets |
| solver selected slots | 仅用于核对binding完整性，不能定义safety全集 |
| fresh/usable target缺81点prediction、尺寸、时间或generation映射 | `SAFETY_EVIDENCE_UNKNOWN`→reject |
| stale/unusable但仍位于监视集合 | 必须有typed exclusion reason；若policy不能证明可安全排除则UNKNOWN→reject |
| target-target pair | 记录为global diagnostic；不进入Ship0 hard aggregate |

target/prediction/Lifecycle/solver binding按DP-02 TrackKey generation一一核对。数量超policy/runtime上限不截断，返回`SAFETY_TARGET_CAPACITY_EXCEEDED`；不得只检查前16个后宣称全部安全。

#### 81 knots / 80 intervals连续检查

对每个目标、每个`i=0..79`，使用同一absolute interval `[t_i,t_{i+1}]`上的own/target piecewise-linear center paths。令relative segment为`r(tau)=r0+tau*(r1-r0), tau in [0,1]`，解析求clamped最小点；必须覆盖current-state→knot1第一段和knot79→terminal knot80末段。

保守净距下界：

`clearance_lb = min_center_distance - r_own - r_target - uncertainty_margin`

其中双方footprint先以可信length/beam构成circumscribed-circle radius。若`clearance_lb >= required_hull_clearance_m`，则可充分证明真实矩形船体净距不低于门槛；这是保守充分条件，不是精确oriented-rectangle距离。

`required_hull_clearance_m=50m`来自trusted ODD/L4 policy，不读取candidate自报门槛。比较容差只处理浮点计算，不得把物理门槛降到50m以下。Assembler中为frozen k+1/k、point-node NLP加入的footprint/一步位移补偿不再次计入。

#### Uncertainty与trackability边界

| 情形 | V1语义 |
|---|---|
| God tracker且canonical evidence证明位置/预测不确定性为零 | margin=0，允许当前Playground production profile |
| policy提供经校准、逐knot、同一confidence语义的target uncertainty envelope | 每segment取覆盖整段的保守上界且只计一次 |
| 只有当前4x4 covariance或未校准CV process model | 不把其朴素传播1200s；`UNCERTAINTY_MODEL_UNSUPPORTED`→UNKNOWN/reject |
| policy声明robust execution safety并提供own tracking tube | 同样从clearance扣除；来源/hash进入witness |
| 无own tracking tube | 只声明planned-trajectory clearance；active-prefix command feasibility由DP-09 hard gate，禁止宣称full-plant robust safety |

不把prediction covariance、Assembler safety allowance、tracking tube重复相加。所有margin必须携带source、confidence、time support、unit及policy hash。

#### Static navigation safety

static safety与dynamic target clearance为同一safety layer内的独立subcheck：

- chart-backed Playground/ODD profile若要求grounding/static-hazard claim，则为mandatory hard check；缺ENC/static context、chart hash、draft或coverage时UNKNOWN→reject。
- pure Module不读取ENC文件、不调用Evaluator；request携带trusted、immutable、ENU化hazard/navigable geometry及provenance，L4对81 knots/80 swept segments按own footprint与适用margin复核。
- non-chart/明确不承担static claim的profile可`NOT_APPLICABLE`，但必须有policy applicability witness；receipt/capability不得声称grounding safety。
- current Mid `requires_enc=False`不能自动推出static N/A；是否要求由trusted acceptance policy/ODD决定，candidate descriptor无权降低。

V1使用保守circumscribed-circle swept clearance against supplied hazard geometry；精确oriented rectangle/C2A可作为独立diagnostic或后续policy版本，不作为首版hard authority。

#### Witness与aggregate

每目标至少输出`TrackKey/segment index/absolute closest time/tau/own-target centers/center distance/radii/uncertainty components/clearance_lb/required margin/pass`；static输出hazard/chart identity、closest segment/time、clearance lower bound与coverage。全局minimum只作摘要；任一相关目标或适用static subcheck FAIL/UNKNOWN/NOT_EVALUATED即safety `FAIL/UNKNOWN`，不能被其他安全目标抵消。

#### 证据链

| 证据 | 推导 |
|---|---|
| [R22][R32] canonical 81点时轴可对齐，但frozen CPA漏terminal interval且只覆盖selected targets | L4必须独立覆盖80段与全部相关targets |
| [R27..R29] node/point CPA不证明连续船体净距；circumscribed-circle lower bound保守且可独立实现 | 采用同步relative-segment解析最小值并扣footprint |
| [R23][R33] Assembler margin含frozen-index工程补偿，50m配置又多处复制 | L4只消费trusted physical threshold并防重复计入 |
| [R24..R26] Gaussian envelope有条件成立，朴素CV长时传播可膨胀到不可用 | V1仅支持God zero或经校准逐时域envelope，其他fail-closed |
| [R30][R31] static hazard与dynamic collision是独立必要claim | chart-backed profile需独立static subcheck，非适用profile必须缩窄claim |
| [R4][R27] Evaluator是事后独立oracle且包含不同几何语义 | production L4不复用Evaluator verdict/helper |

#### 备选与弃用草案

| 方案 | 优点 | 弃用理由 |
|---|---|---|
| A all-relevant swept conservative clearance + applicable static hard check（推荐） | 保守、可解释、覆盖admission与节点间缺口 | 对大船/长时不确定性可能保守误拒；request证据增大 |
| B 只检查solver selected targets | 成本最小 | candidate admission可漏碰撞目标，形成自证 |
| C 只检查81个node center CPA | 简单且与solver接近 | 漏15s区间穿越、footprint与末段 |
| D 复用Evaluator clearance/collision verdict | 代码少 | Planner自评，共享缺陷；事后actual truth不等于预测plan acceptance |
| E V1直接用oriented rectangle/C2A作唯一hard gate | 准确度更高 | 需可信姿态/转动sweep与更复杂oracle，独立性和runtime风险更高 |
| F 将当前CV covariance直接传播到1200s | 自动覆盖非God | 未校准时margin可达数十km，无可用production意义 |
| G static hazard永久排除L4 | 缩小模块 | chart-backed profile仍会把可能grounding计划下发，无法支持完整static-safety claim |
| H target-target碰撞进入Ship0 hard aggregate | global统计统一 | Ship0 Mid-MPC无权控制脚本目标船；混淆scope并造成固有场景失败 |

#### 风险、失效边界与验证

| 项 | 评估 |
|---|---|
| 实现风险 | **高**：target reconciliation、continuous geometry、static context与evidence schema均需严格实现 |
| 误拒风险 | **中高**：包围圆、全部目标和未知不确定性均保守；通过God V1 ODD、typed UNKNOWN与后续versioned geometry/envelope演进控制 |
| 误接受风险 | **中**：piecewise-linear target prediction和planned path不等于真实闭环；通过明确claim、DP-09 active-prefix hard gate及Evaluator事后证据控制 |
| 失效边界 | prediction/model/trackability contract外不保证；non-God无calibrated envelope不接受；无static context不作grounding claim；不证明target-target安全 |
| 核心验证 | 第一/末段交叉；node安全但segment碰撞；大footprint；恰好50m边界；unselected target；TrackKey reuse/missing prediction；God zero；unsupported covariance；margin单计；static hazard/coverage missing；target-order/translation metamorphic；独立geometry oracle；真实HO/CS/OT/multiship |

#### 技术分解状态

DP-05冻结planned-trajectory动态/static safety算法与scope；MASS_PARITY隔离DP-06、COLREG行为DP-07/08、active-prefix trackability DP-09、target aggregate DP-11、exact阈值/不确定性profile DP-17继续裁决。

### Step4-DP06 · MASS_PARITY / COLAV_STRICT profile isolation（final）

#### 初步推荐

采用“**同一L4 implementation、显式versioned profile contract、不同aggregate eligibility**”：

- `MASS_PARITY_<frozen-source>`只验证冻结C++/Python方程与packing一致性。L4仍可运行完整layer并生成diagnostic evidence，但总结果固定为`DIAGNOSTIC_ONLY`。
- `COLAV_STRICT_<policy-version>`是唯一可进入production `ACCEPT/REJECT`的profile；必须同时证明trusted expected profile、candidate actual preparation及parent hash chain一致。
- strict失败不得自动改用parity、旧strict或放宽slack/threshold；profile转换只能由新solve request显式触发，不能在同一attempt内fallback。

profile不是一个可相信的字符串，而是authority/candidate双边可核对的typed contract。

#### Expected / actual / preparation三方核对

| 证据 | Authority | Candidate actual | L4检查 |
|---|---|---|---|
| profile schema/id/version/hash | trusted Session/Registry policy | result/preparation identity | 完全相等；错配归integrity |
| formulation/layout/source baseline | trusted manifest | problem/prepared/raw parent hashes | parent chain连续且layout一致 |
| slack policy | strict要求fixed zero；parity保留frozen语义 | actual lbx/ubx、slack indices、raw values | 不信profile label，机械复核actual vectors |
| Ipopt options | trusted option allowlist/hash | actual effective options | strict必须含`bound_relax_factor=0`等已裁决设置 |
| safety/ODD threshold | trusted L4 policy | candidate仅报告observed facts | candidate不得定义或降低50m等门槛 |
| target/row schedule | trusted problem contract | actual row registry/active indices | schedule、slots、target identity与hash一致 |

任一expected/actual/prepared/raw cross-splice、缺字段或语义不支持：`PROFILE_EVIDENCE_MISMATCH`/`STRICT_PREPARATION_UNPROVEN`，integrity fail-closed。禁止用`algorithm_id=mid_mpc_ipopt`或`profile_name`替代实际证据。

#### Aggregate、receipt与warm eligibility

| Profile | Layer evaluation | Overall | Production command | Accepted receipt / warm seed | Capability evidence |
|---|---|---|---|---|---|
| `MASS_PARITY` | 全部可计算layer照常输出 | 永远`DIAGNOSTIC_ONLY` | 禁止 | 禁止 | 仅numerical parity claim |
| `COLAV_STRICT`且全部mandatory pass | 完整执行 | `ACCEPT` | 可进入Adapter原子commit | 可签production receipt | 绑定完整policy/plant/tracker/scenario tuple |
| `COLAV_STRICT`任一mandatory fail/unknown | 完整失败列表 | `REJECT` | 禁止 | 禁止 | 不新增/继承production claim |
| profile identity/evidence mismatch | integrity short-circuit | `REJECT` | 禁止 | 禁止 | claim invalid |

MASS parity candidate即使偶然满足50m/COLREG，也不能升级为production strict acceptance；strict candidate也不要求与MASS fixture逐元素相等。两类claim正交：parity验证port fidelity，strict验证当前production contract。

#### Evidence与用户可观察性

full artifact、inline trace、GUI/card诊断必须同时展示：

- `expected_profile_id/version/hash`
- `actual_profile_id/version/hash`
- `formulation/layout/preparation/solver hashes`
- `dispatch_eligibility=DIAGNOSTIC_ONLY|PRODUCTION`
- actual strict checks摘要及first mismatch

GUI算法名仍为`Mid-MPC`，但不得隐藏当前profile/eligibility；capability tuple只引用strict acceptance artifacts。更新strict policy、solver/preparation contract或frozen parity baseline时，旧receipt/claim按DP-14/17失效，不覆盖历史artifact。

#### 证据链

| 证据 | 推导 |
|---|---|
| [R6][R18][R20] parity保留冻结方程/packing quirks，strict改变slack/bound preparation | 两profile claim不同，不能互相替代 |
| [R15][R18] profile label不能证明effective Ipopt options与actual bounds | L4必须检查actual prepared vectors/options |
| [R23][R33] production safety门与frozen solver工程补偿不同 | threshold authority必须留在trusted L4 policy |
| [R58] L3 candidate quality acceptance与L4 production acceptance已存在命名冲突 | 明确`DIAGNOSTIC_ONLY`与production receipt边界 |
| [R63][R71] policy/dependency hash变化需使warm/capability失效且保留历史证据 | profile/version/hash进入receipt与claim tuple |

#### 备选与弃用草案

| 方案 | 优点 | 弃用理由 |
|---|---|---|
| A 同一checker、显式profile contract、不同eligibility（推荐） | 避免双实现漂移，claim清晰，保留parity诊断价值 | schema/hash/preparation验证增加 |
| B parity与strict各写一套L4 checker | 分支直观 | safety/COLREG逻辑会漂移，修复需双维护 |
| C 只检查`profile_name`字符串 | 最省成本 | 可伪造标签，不能证明actual bounds/options/slacks |
| D strict拒绝后自动回退MASS parity | 提高表面可用率 | 直接违反production safety与no-fallback边界 |
| E strict production也要求8条MASS fixture逐元素一致 | 强化回归 | strict preparation语义不同；把port fidelity误作production gate |
| F 修改旧parity fixture/expected使其符合strict | 统一数据 | 销毁冻结上游oracle与迁移可追溯性 |
| G artifact/GUI只显示`Mid-MPC`，profile留内部 | UI简洁 | 用户无法判断正在运行parity还是production strict |

#### 风险、失效边界与验证

| 项 | 评估 |
|---|---|
| 实现风险 | **中**：主要为typed profile manifest、actual preparation proof与projection，不改IPOPT方程 |
| 误接受风险 | **低至中**：最大风险是伪strict/cross-splice；通过parent chain与机械bound/option复核控制 |
| 误拒风险 | **低**：strict manifest漂移会fail-closed；需通过version migration与明确diagnostic处理 |
| 失效边界 | parity层结果只支持冻结baseline数值claim；strict只支持绑定的ODD/policy/plant/tracker；二者均不证明MASS-L3 SIL/GNC/M7 |
| 核心验证 | 真实8条parity expected不变且overall diagnostic-only；parity偶然安全仍无receipt；strict全过可receipt；伪标签、cross-splice、slack未锁、option错配拒绝；strict失败无parity fallback；profile变更使旧receipt失效；GUI/trace expected-vs-actual可见 |

#### 技术分解状态

DP-06冻结profile isolation与claim boundary；具体strict数值值/manifest governance由DP-17、receipt失效由DP-14、artifact/GUI projection由DP-15、capability验证由DP-18继续裁决。

### Step4-DP07 · COLREG directive consistency authority与场景语义（final）

#### 初步推荐

采用“**Lifecycle directive是唯一规则决策authority，L4是独立轨迹一致性证明者**”。L4消费Candidate 2已锁定的每目标episode/role/phase/passing side/action requirement与aggregate directive，不基于candidate改变后的瞬时几何重新分类，也不重选通过侧或解决多目标冲突。

L4检查对象是完整81-knot planned trajectory及absolute-time target prediction；first command只用于动作开始/可执行性证据，不能代替完整通过语义。动态safety DP-05始终先独立成立；COLREG PASS不能抵消净距失败。

#### Authority与identity contract

| 项 | Authority | L4责任 |
|---|---|---|
| encounter type、own role、rule、phase、episode | immutable Lifecycle snapshot | 按TrackKey generation核对；不重分类 |
| locked passing side / required signed action | Lifecycle | 验证trajectory一致；不更改侧别 |
| aggregate directive / conflict | Lifecycle，Assembler防御装配 | 验证per-target obligations与aggregate兼容；不重新仲裁 |
| target predictions / planned path | Candidate 3 bundle | 在共同absolute time/frame独立重算几何predicate |
| post-run actual COLREG compliance | Evaluator | L4不替代，只输出planned evidence |

Lifecycle decision缺失、episode/generation不匹配、同一目标存在矛盾directive，均为integrity/`COLREG_AUTHORITY_UNKNOWN`并reject。不得用Evaluator classifier填补缺口。

#### Per-directive V1 predicates

| Directive/role | Mandatory planned evidence | 明确不做 |
|---|---|---|
| `HEAD_ON / GIVE_WAY` | action窗口内与commit baseline同符号的starboard course alteration；计划在relevant encounter window保持该侧；closest-passing几何满足port-to-port；无提前回切 | 不接受仅首点右转后远期左切 |
| `CROSSING / GIVE_WAY` | 与Lifecycle signed action一致；不得cross ahead；以synchronized along/cross-track或relative passing witness证明pass astern；持续到past-and-clear/release条件 | 不因candidate转向后相对方位变化改判stand-on |
| `OVERTAKING / GIVE_WAY` | 沿Lifecycle锁定corridor/side完成通过；保持责任到finally past-and-clear；达到clear前不得跨回目标航迹禁区 | 不把Rule13硬编码成法律上永远starboard-only |
| `STAND_ON / HOLD` | action escalation前维持entry course/speed envelope；若Lifecycle已进入Rule17 MAY/MUST action，改按其锁定action验证 | L4不自行决定何时从MAY升级MUST |
| `OVERTAKEN / STAND_ON` | 在Lifecycle允许范围内保持course/speed；安全威胁升级时服从Rule17 snapshot | 不把被追越船当give-way |
| `CLEAR / RELEASED` | COLREG subcheck可N/A，但必须有Lifecycle applicability witness；DP-05 safety仍全时域hard | 不因clear/released跳过安全 |
| `MANEUVER_CONFLICT` | 不存在production candidate资格 | 不在L4搜索新侧、STOP或折中轨迹 |

所有predicate使用trusted policy tolerance，但不能改变role/side/phase。具体early/substantial、past-clear与recovery窗口由DP-08裁决。

#### OT侧别与Playground claim

Rule 13本身不规定只能从目标船某一固定侧超越。V1因此：

- 标准无约束Playground OT：Lifecycle corridor选择应按其已确认policy产生starboard maneuver/把目标留在本船port侧；L4只验证这个锁定结果。
- 镜像或受限场景：Lifecycle可锁定port maneuver；L4验证对应corridor，不错误拒绝为“违反Rule13”。
- capability claim必须分别覆盖standard-starboard与mirror/locked-port证据，不能用一个标准OT样例外推所有OT。

这解决“OT一开始左转”担忧的责任边界：错误若来自Lifecycle锁错侧，修Lifecycle/policy；若directive正确但candidate左转或回切，L4 hard reject。L4不通过硬编码右转掩盖上游决策错误。

#### Geometry witnesses

每目标输出：`TrackKey/episode/rule/role/phase/locked_side/baseline/action requirement`，以及action onset、signed course change、closest approach absolute time、passing-side/cross-ahead/pass-astern/corridor/past-clear predicate的原始几何量、阈值和首次失败segment。角度按普通unwrap和signed convention；禁止只存最终bool。

per-target全部mandatory取AND。primary target只用于GUI摘要；任一相关目标COLREG fail/unknown均不能被另一目标或aggregate score抵消。多目标compatibility与out-of-scope target-target collision由DP-11细化。

#### 证据链

| 证据 | 推导 |
|---|---|
| [R5][R37..R39][R42] Lifecycle已拥有episode、role、side、commit/action与multi-target compatibility | L4不得重分类、重选侧或重新仲裁 |
| [R34][R35] Rules 8/13/14/15/17要求持续动作/责任/通过语义 | first-command sign不足，需完整relevant window predicates |
| [R36][R37] OT两侧在规则/受限语境可成立，当前Lifecycle已有corridor选择与tie-break | 不把Rule13误写成universal starboard-only |
| [R40][R41] HO/CS/OT/stand-on几何可从轨迹独立复核，而现有测试仅run后断言 | 新增per-solve plan-level oracle与witness |
| [R27][R29] Evaluator是事后独立证据 | 不复用其classifier/verdict作为production authority |

#### 备选与弃用草案

| 方案 | 优点 | 弃用理由 |
|---|---|---|
| A Lifecycle authority + L4 independent predicates（推荐） | 分责清晰，防intent flicker，能定位上游决策与下游轨迹错误 | request/witness较丰富 |
| B L4按每次candidate终态重新分类COLREG | 看似自包含 | candidate动作改变几何后会丢失原责任，重现intent flicker |
| C L4为OT统一强制starboard | 符合标准Playground偏好 | 把工程偏好冒充Rule13法律常数，错误拒绝锁定port/受限情形 |
| D 只检查first command方向 | 快且简单 | 可先正确微转后回切、cross ahead或未past-clear |
| E 只检查final CPA/passing point | 能判断最终侧别 | 漏动作时机、过程中wrong-side与责任连续性 |
| F 复用Evaluator Pairwise COLREG FSM/classifier | 减少代码 | Planner自评且基于不同时间/actual state，可能共享缺陷或重分类 |
| G L4重新解决multi-target maneuver conflict | 提高可用性 | 越权成为Lifecycle/Assembler/Planner，违反pure acceptance和no modification |

#### 风险、失效边界与验证

| 项 | 评估 |
|---|---|
| 实现风险 | **高**：每类directive需稳定absolute-time几何predicate及witness |
| 误拒风险 | **中高**：angle unwrap、side/corridor与phase窗口若定义不准会误拒；通过DP-08/17 versioned tolerance及mirror/boundary corpus控制 |
| 误接受风险 | **中**：planned consistency不等于actual compliance；通过Evaluator post-run独立证据和hold revalidation控制 |
| 失效边界 | Lifecycle authority错误时L4不自行纠正，只能验证/暴露矛盾；法规无统一early/substantial数值；不声称法律或实船认证 |
| 核心验证 | locked HO右转后回切；CS cross-ahead/pass-astern边界；标准OT starboard、镜像locked-port、责任持续到past-clear；stand-on保持与Rule17 MAY/MUST；candidate转向后不重分类；missing/mismatched episode；multi-target conflicting directives；独立geometry oracle；真实HO/CS/OT/overtaken closed loop |

#### 技术分解状态

DP-07冻结authority与场景predicate分类；动作时机、substantial、past-clear/recovery具体窗口DP-08，multi-target aggregate DP-11，阈值与OT Playground policy DP-17继续裁决。

### Step4-DP08 · early/substantial、wrong-side、past-clear与recovery（final）

#### 初步推荐

采用“**Lifecycle发布有期限的动作义务，L4在固定commit baseline与absolute time上验证计划履约**”。法规只给定early/substantial/ample-time等义务，不给通用角度、秒数或距离；因此具体门槛必须来自trusted、versioned policy与当前Lifecycle obligation，禁止L4自行写死`5deg/30deg/60s`或按scenario ID调参。

L4为纯无状态模块：跨solve累计动作使用Lifecycle固定commit baseline、episode、actual achievement与previous accepted receipt；绝不以“本次candidate相对当前艏向又转了几度”替代累计证据。

#### Required action obligation

每个active obligation必须携带：

| 字段 | 语义/authority |
|---|---|
| `commit_time / commit_course / commit_speed` | Lifecycle锁定episode时的固定基线 |
| `required_signed_course_change`或stand-on envelope | Lifecycle结合role/side与trusted policy产生 |
| `action_start_deadline` | 最迟开始positive action的absolute time |
| `action_achievement_deadline` | 最迟达到required substantial action的absolute time |
| `actual_signed_achievement`与witness time | Lifecycle按实测状态相对固定baseline累计 |
| `reachability_certificate` | Assembler基于当前active capability证明deadline内可达；含hash/time/assumptions |
| `past_clear_predicate/profile` | trusted policy定义的几何条件与guard window |
| `recovery_permission` | 仅Lifecycle在past-and-clear/release后授予 |

缺deadline、baseline、reachability或字段互相矛盾时，L4返回`ACTION_CONTRACT_INCOMPLETE`/`UNKNOWN`并reject；不得从1200s horizon长度推断“还有时间”。这要求Candidate 2/3 contract在实现前补齐当前缺失投影，但不改变其authority。

#### Early与substantial判定

| Check | V1 hard semantics |
|---|---|
| positive/on-side onset | earliest executable command/trajectory response必须与locked signed action同符号，并超过policy deadband |
| early | planned onset absolute time不晚于`action_start_deadline`；若deadline落在首个15s knot前，必须消费first executable interval/command证据，不能等knot1 |
| substantial | `actual achievement + planned cumulative achievement`相对固定commit baseline达到required signed magnitude，且不晚于achievement deadline |
| readily apparent | 达到阈值后在obligation window内持续保持，不允许单个knot脉冲、振荡抵消或立即回切 |
| reachable | candidate path与reachability certificate assumptions一致；certificate stale/mismatched则UNKNOWN |
| already achieved | 仍保持required side/action直到past-clear；不能因已达角度就释放责任 |

planned onset/achievement time由81-knot trajectory和80 interval commands在absolute time上给出；跨阈值可线性插值形成witness，但first executable command保持piecewise-constant interval语义。普通角度unwrap；累计动作始终相对commit baseline，不对每周期重新置零。

#### Initial wrong-side但可恢复

不采用“一出现wrong-side即无条件reject”，也不允许无边界宽限。仅当全部成立时接受有限transient：

1. Lifecycle仍锁定正确目标侧/方向；没有authority矛盾。
2. first executable command立即朝纠正方向。
3. signed violation在active prefix内单调不增；不得先继续恶化再恢复。
4. reachability certificate证明在achievement deadline前越过正确侧并达到required action。
5. DP-05 continuous 50m safety与DP-09 trackability全程通过。

否则`WRONG_SIDE_NOT_RECOVERABLE`。具体deadband、单调容差与deadline由DP-17 policy冻结，不按HO/CS/OT测试结果反推。

#### Past-and-clear、release与recovery

| Phase | L4 hard check |
|---|---|
| active/not past-clear | 保持locked corridor/action；禁止向route过早回切、穿越目标航迹禁区或解除give-way责任 |
| predicted past-clear | 使用同步relative geometry验证前后/横向分离、相对运动已发散、50m safety，以及policy guard interval内无re-entry；只是计划证据，不自行改变Lifecycle phase |
| Lifecycle尚未release | 即使candidate预测会past-clear，仍不得把未来release当当前权限提前恢复 |
| Lifecycle已授予recovery | 允许开始回归route/speed；DP-08只hard-check无wrong-side/re-entry，DP-10评估恢复质量，DP-09检查可跟踪 |
| new risk/re-entry | Lifecycle新episode/directive优先；旧recovery permission失效，identity mismatch则reject/replan |

L4不能签发release。只有Lifecycle依据实际past-and-clear事实改变snapshot后，candidate才获得当前recovery permission。这样避免1200s预测中的“未来已安全”被错误解释为现在可以回切。

#### Stand-on / Rule17 timing

- `STAND_ON_HOLD`阶段：course/speed相对entry baseline必须保持在trusted envelope内，直到Lifecycle MAY/MUST action transition。
- `RULE17_MAY_ACTION`：若Lifecycle选择动作，则按其方向、start/achievement deadline验证；未选择时继续stand-on envelope。
- `RULE17_MUST_ACTION`：必须满足immediate action deadline及safety/trackability；L4不自行延后或退回HOLD。
- deadline已过且actual/planned obligation未满足，candidate hard reject；不能靠远期1200s最终避开补救迟行动。

#### Evidence witnesses

每target记录baseline、deadlines、required/actual/planned signed achievement、onset/achievement absolute time、first executable command、reachability hash、wrong-side monotonic samples、past-clear closest/re-entry/guard证据、recovery permission source。失败按最早绝对时间稳定排序；不只输出“Rule 8 PASS”。

#### 证据链

| 证据 | 推导 |
|---|---|
| [R34][R35] Rules 8/13/16/17要求early/substantial、持续到past-clear，但无统一数值 | 数值门归trusted profile/obligation，不硬编码法规常数 |
| [R38][R39] Lifecycle已有commit baseline/required action/actual achievement，但deadline/reachability projection缺失 | 扩展immutable action contract，保持Lifecycle authority |
| [R40] passing/past-clear/recovery可由同步trajectory独立复核 | L4输出计划级predicate witness，但不签发actual release |
| [R46][R47] 15s state knots与interval commands语义不同 | early必须检查first executable interval，不能只等第一个knot |
| [R34][R38][R39] 固定baseline能识别跨solve连续小改向 | 不以每cycle delta重置substantial achievement |
| [R48..R50] route recovery质量需稳定route reference与独立metrics | DP-08只hard-checkpermission/no-reentry，恢复快慢/平滑留DP-10 |

#### 备选与弃用草案

| 方案 | 优点 | 弃用理由 |
|---|---|---|
| A deadline-bearing Lifecycle obligation + absolute-time L4 proof（推荐） | 责任清晰，跨solve可累计，能区分迟行动/假动作/提前回切 | 需补齐deadline/reachability contract |
| B L4统一写死5deg、30deg或60s | 实现快 | 法规无该通用常数，跨速度/距离/plant不成立 |
| C 只要1200s horizon最终安全即视为early | 宽松且易PASS | 允许临近碰撞才行动，违反ample-time/early语义 |
| D 每次solve相对当前艏向检查minimum alteration | 无需历史 | 小步动作每周期清零，无法证明累计substantial或识别反复 |
| E 初始wrong-side一律立即reject | 简单保守 | 拒绝物理可恢复且立即纠正的计划，可能造成不必要fail-stop |
| F wrong-side只看horizon终点已恢复 | 容错高 | 允许先恶化、迟纠正或中途不安全 |
| G candidate预测past-clear后立即允许route recovery | 提前恢复 | 把未来计划事实冒充当前Lifecycle release authority |
| H L4自己推进phase/release状态 | 可自包含 | 使pure stateless acceptance变为第二Lifecycle，产生双authority |

#### 风险、失效边界与验证

| 项 | 评估 |
|---|---|
| 实现风险 | **高**：Candidate 2/3需补齐deadline/reachability投影，且15s trajectory/first-command时序必须严格对齐 |
| 误拒风险 | **中高**：deadline/deadband/stand-on envelope缺独立校准；必须versioned policy与boundary corpus |
| 误接受风险 | **中**：planned achievement不等于实际执行；通过actual Lifecycle achievement、DP-09 active-prefix gate、hold revalidation与Evaluator控制 |
| 失效边界 | 无可信deadline/reachability时fail-closed；不自行定义法规常数、不签发release、不保证未来目标按预测运动 |
| 核心验证 | immediate/late onset；跨solve累计small steps；single-knot pulse；正确侧后回切；wrong-side单调恢复/先恶化；deadline恰好边界；first interval早于knot1；predicted vs actual release；premature recovery/re-entry；stand-on MAY/MUST transition；HO/CS/OT完整闭环 |

#### 技术分解状态

DP-08冻结动作义务、时间与release/recovery分责；active plant可达性/first executable trackability由DP-09、恢复质量DP-10、hold时序DP-12、具体policy阈值DP-17继续裁决。

### Step4-DP09 · active-plant trackability与command semantics（final）

#### 初步推荐

采用“**command语义完整性全时域hard + active execution prefix的plant-envelope hard gate + 远期rollout的显式claim降级**”。L4不把Mid reduced model的`course/speed`轨迹直接宣称为Viknes/FLSC或任意plant可跟踪；必须消费Session冻结的active plant/capability contract。

V1 production最低要求：

1. candidate状态明确为地固`COG/SOG` reference，不静默当作body `heading/surge`。
2. 81个state knots与80个piecewise-constant interval commands严格分离；执行/hold不得线性插值control intervals。
3. 从当前实测状态到下一次正常solve/commit窗口的active prefix必须满足当前plant可执行包络。
4. 无可信active-plant envelope或frame/command mapping时`TRACKABILITY_UNKNOWN`→reject；不得回退静态`published_kinematic_csog`假装已证明Viknes/FLSC。
5. 若无经验证full-horizon tracking tube，只能声称active-prefix executable及planned-trajectory safety；不得声称1200s plant-robust safety。

#### Canonical command/state semantics

| 对象 | V1语义 |
|---|---|
| planned state knots | `north_m,east_m,cog_rad,sog_mps`，absolute times `t0..t80` |
| interval commands | 每个`[t_i,t_{i+1})`一个piecewise-constant `cog_ref_rad,sog_ref_mps`或明确的plant-neutral reference；共80个 |
| current ownship | 同时提供body `psi/u/v/r`与ground `COG/SOG/velocity_NE`，来源和timestamp明确 |
| plant adapter mapping | 独立、版本化contract定义ground reference如何送入FLSC/autopilot；若controller实际需要heading/surge，必须给出含sway/current的可信转换或声明unsupported |
| angle | ordinary unwrap后比较；0=north、clockwise-positive的现有planner convention进入技术规约，转换点单一 |

禁止使用`u=4,v=1,psi=0`时把`psi=0,u=4`冒充`COG=14.0deg,SOG=4.123m/s`；也禁止hold t=5s把`[10deg,20deg]`两个interval command线性采成`13.33deg`。state可按定义插值；control在interval边界才切换。

#### Active execution prefix

prefix终点取`min(next mandatory solve/commit time, accepted-plan validity end, policy max prefix)`；至少覆盖本cycle真正可能下发的全部command。默认solve period为5s、grid interval为15s时，通常验证当前interval的剩余0..5s，而不是只检查15s knot。

Hard checks按active capability提供的物理量逐项执行：

| Check | Witness |
|---|---|
| first command jump / reference rate | current COG/SOG到command的signed delta、允许slew/rate |
| ROT/course-rate | 每段unwrap course change / elapsed time；使用active controller可实现上界 |
| accel/decel/speed envelope | reference和变化率相对current SOG、允许上下界 |
| curvature/lateral acceleration（若capability提供） | `kappa`、`v^2*kappa`及限值 |
| command continuity/dwell | interval边界、切换次数、minimum dwell |
| predicted tracking tube（若提供） | prefix每时刻position/course/speed error bound及certificate hash |

只检查capability明确支持的量，但缺少证明当前command可执行所需的关键维度即UNKNOWN，不得将“字段未提供”解释为无限能力。candidate内部NLP的ROT/decel bounds只能作cross-check；不能代替active plant authority。

#### Full 1200s horizon

| 能力证据 | L4结果/claim |
|---|---|
| active plant有经独立校准、与当前controller/version绑定的full-horizon tracking tube | 可将tube并入DP-05 margin并执行full-horizon robust trackability check |
| 只有instantaneous envelope，无long-horizon tube | active prefix hard PASS；远期trackability标`NOT_EVALUATED/ADVISORY`，receipt明确claim scope |
| 连active prefix envelope也没有 | mandatory UNKNOWN→reject |

远期reference仍全时域执行semantic sanity：finite、速度域、course/ROT/accel不超过已声明planner physical bounds、80/81时间连续；但这些只证明reference自身一致，不等于高阶plant闭环可跟踪。

#### Reachability certificate与DP-08接口

Assembler可依据同一active capability生成action deadline reachability certificate；L4机械核对certificate的plant/controller/policy/state/time/hash与当前request一致，再验证candidate确实落在certificate支持的control envelope内。L4不重新运行plant simulation或另一个MPC；certificate stale/错配/假定KinematicCSOG而active plant为Viknes+FLSC时hard UNKNOWN。

DP-08的early/substantial deadline只有在该certificate成立时可接受。DP-05若没有tracking tube，只保留planned-trajectory hull-clearance claim；不把first-prefix check外推1200s。

#### 证据链

| 证据 | 推导 |
|---|---|
| [R43] heading autopilot与course autopilot不同，COG/SOG由地固速度定义 | canonical state/command必须显式为COG/SOG且转换可审计 |
| [R45] 标准场景实际Viknes+FLSC，但当前只发布静态KinematicCSOG能力 | 不能用published static envelope宣称active plant可跟踪 |
| [R46] sway状态和hold插值已实证产生COG/heading、interval/knot错位 | 两类语义必须成为hard contract tests |
| [R44][R47] reduced planner可行不推出高阶plant/full-horizon跟踪安全 | active prefix hard，full horizon需独立tube，否则缩窄claim |
| [R12] reference infeasibility会破坏安全/约束 | 缺active envelope必须UNKNOWN fail-closed |
| [R39] action reachability已参与Assembler row启用，但缺公开certificate | 通过versioned certificate连接DP-08而非在L4复制装配逻辑 |

#### 备选与弃用草案

| 方案 | 优点 | 弃用理由 |
|---|---|---|
| A semantic hard + active-prefix envelope hard + scoped horizon claim（推荐） | 与实际执行窗口匹配，诚实表达当前能力缺口，可渐进加入tracking tube | 需plant capability contract与Adapter语义修复 |
| B 只复核Mid NLP自身ROT/decel bounds | 无新接口 | 只证明reduced model，不证明Viknes/FLSC/controller可执行 |
| C 用静态`published_kinematic_csog`代替active plant | 当前已有 | 与标准场景真实plant不一致，制造虚假trackability claim |
| D 要求无tube时完整1200s全部hard trackable | claim最强 | 当前无oracle/certificate，所有production计划都会无依据拒绝 |
| E 完全跳过trackability，只靠Evaluator最终轨迹 | 实现最省 | 不可执行reference可能先被下发，违反plan acceptance目的 |
| F L4内运行Viknes/FLSC闭环仿真 | 看似真实 | 复制runtime/controller、扩大deadline和非确定性，仍缺模型误差独立性 |
| G 将81 state knots和80 commands都做线性插值 | API统一 | 改变piecewise-constant控制语义，已产生错误执行command |
| H 将COG/SOG静默映射为heading/surge | 接口简单 | sway/current存在时物理错误，复现已知偏差 |

#### 风险、失效边界与验证

| 项 | 评估 |
|---|---|
| 实现风险 | **高**：需active plant/controller capability schema、Adapter command mapping与certificate链 |
| 误拒风险 | **中高**：现有Viknes/FLSC缺live envelope；实现前必须先提供可信active-prefix capability，否则按设计拒绝 |
| 误接受风险 | **中**：prefix envelope不是实际闭环proof；通过短validity、hold重验、tracking tube可选升级与Evaluator控制 |
| 失效边界 | 无full tube不证明1200s plant robust safety；不支持任意plant/current/sway；certificate仅对绑定controller/state/time有效 |
| 核心验证 | `u/v/psi`与COG/SOG反例；80/81 shape/time；5s hold不插值command；first jump/ROT/accel/decel边界；active plant与static capability错配；missing/stale certificate；prefix恰到next solve；无tube claim降级；真实Viknes+FLSC HO/CS/OT；metamorphic time shift/angle wrap |

#### 技术分解状态

DP-09冻结command语义、active-prefix hard scope与full-horizon claim边界；质量/churn DP-10、hold重采样DP-12、plant/profile阈值DP-17、验证矩阵DP-18继续裁决。

### Step4-DP10 · solution quality、cross-solve stability与recovery quality（final）

#### 初步推荐

采用“**V1 quality layer全部advisory，不单独阻止安全且合规的计划下发；只有已被其他mandatory layer定义为操作失效的事实才hard reject**”。Quality负责解释“计划是否平滑、经济、稳定、有效推进”，不复制safety/COLREG/trackability authority，也不因为预测轨迹近似直线就判差。

这直接回应当前Mid-MPC视觉担忧：真实IPOPT结果若route-only或已完成一次小幅改向后形成近恒定COG/SOG直线，只要mandatory layers通过，就是合法计划。Quality只揭示objective组成、route progress和cross-solve变化，不要求“轨迹必须看起来弯”。

#### V1 metric set

所有metric使用canonical ENU/SI/rad、absolute time及稳定route polyline reference；禁止用单bearing无限直线或raw NLP total objective直接跨cycle比较。

| Metric family | 物理定义 | V1 outcome |
|---|---|---|
| control smoothness | interval command的course/speed first/second differences、总变差、切换次数 | WARN；超plant envelope已由DP-09 hard fail |
| cross-solve churn | 新旧accepted plans在重叠absolute-time window的COG/SOG/position差异、directive不变时的side/sign翻转 | WARN；若违反locked COLREG则DP-07/08 hard fail |
| maneuver efficiency | 相对stable route的额外arc length、route deviation、speed loss、ETA delay | WARN |
| route progress | 沿trusted route polyline的arc-length progress、contour/lag error | WARN；负progress本身不hard，除非另有operational obligation |
| recovery | Lifecycle release后首次rejoin time、route cross-track decay、speed restoration、overshoot/re-entry | WARN；premature recovery/re-entry由DP-08 hard fail |
| plan/reference consistency | candidate objective components与这些物理metrics并列显示 | diagnostic only，不作跨cycle归一化score |
| straightness/curvature | 实际course range与path curvature | informational；不得要求非零弯曲 |

每metric输出value/unit/time window/baseline/reference/policy threshold/quality outcome。无previous accepted receipt时，cross-solve metrics为`NOT_APPLICABLE`并附witness，不得UNKNOWN reject整份plan。

#### Cross-solve absolute-time comparison

previous accepted plan只通过DP-14 neutral record输入。比较步骤：

1. 验证相同session/epoch/algorithm/policy/route/Lifecycle episode与兼容TrackKey set。
2. 取两plan state knots的absolute-time重叠区间；位置/COG/SOG按state语义重采样。
3. interval commands仅按piecewise-constant区间对齐，禁止knot线性插值。
4. 仅在相同directive/phase与未发生重大观测变化时解释churn；新目标、Lifecycle transition、policy/route变化时标`NOT_APPLICABLE/CONTEXT_CHANGED`。
5. telemetry wall time、solve iteration或artifact path不进入quality metric/hash。

这样避免把正当的新风险响应误判为抖动，也避免5s solve/15s grid造成假差异。

#### Route progress与recovery reference

使用Candidate 3/PlannerInput的trusted route polyline和当前route anchor：

- 将每个planned point投影到polyline arc-length `s`，计算contour error与lag/progress。
- 弯曲航线不得退化为单一初始bearing；若route geometry/projection identity缺失，route-quality metric为`NOT_EVALUATED` warning，不影响mandatory acceptance。
- recovery只在Lifecycle实际授予permission后计时；目标是观察rejoin delay、cross-track单调趋势、speed恢复与overshoot。
- Route progress不足不自动hard fail：STOP、stand-on、受限水域或安全避让可能合理牺牲效率。

#### Hard/soft边界

| 现象 | Owner / verdict |
|---|---|
| 50m、wrong side、迟行动、提前回切、不可执行ROT/accel | 对应DP-05/07/08/09 mandatory hard fail，不由quality重复裁决 |
| 计划在有限窗口完全无route progress但Lifecycle允许STOP | quality WARN，不hard reject |
| 安全合规的近直线 | quality PASS/INFO |
| objective异常/非finite/component sum错 | DP-04 numerical hard fail |
| objective较上一cycle更高 | diagnostic，不直接WARN/FAIL；target set/reference不同不可比 |
| 重复sign flip但始终未越mandatory threshold | churn WARN；用于调试/后续校准，不在V1阻断 |
| 已versioned policy将某metric提升为hard | 不在V1；需新证据、独立校准集与policy major version，回炉design-grounding |

#### Quality aggregate与GUI

Quality layer可为`PASS/WARN/NOT_APPLICABLE/NOT_EVALUATED`；V1不产生独立`FAIL`。Overall mandatory全过时，quality WARN仍`ACCEPT`。GUI展示最多高信号摘要：straight/curved provenance、route progress、max command variation、cross-solve churn、recovery state与quality warning codes；不能把raw objective显示为“安全分数”或把直线标红。

#### 证据链

| 证据 | 推导 |
|---|---|
| [R48] Mid raw objective是context-dependent horizon sum，target/reference变化导致跨cycle不可比 | 不以objective total作为quality gate或统一score |
| [R49] trajectory planning把clearance、smoothness、path length、deviation与ETA分开 | 采用分离物理metrics，避免加权抵消mandatory facts |
| [R50] MPCC以route arc-length、contour/lag error和control effort描述progress | 使用完整polyline而非单bearing |
| [R46][R47] 5s solve与15s intervals存在重采样错位 | cross-solve按absolute time并区分state/command语义 |
| [R51] 当前测试未覆盖cross-solve churn或route-progress quality | 新增独立quality contract/negative corpus，但不冒充hard校准 |
| [R41] 真实OT在提交动作后可产生近直线真实解 | straightness只作provenance/info，不作为缺陷 |

#### 备选与弃用草案

| 方案 | 优点 | 弃用理由 |
|---|---|---|
| A V1 advisory physical metrics（推荐） | 不误拒安全计划，提供调试依据，可经独立校准后版本化升级 | 初版不能阻断纯质量退化 |
| B 所有quality metric超过经验阈值即hard reject | 强制轨迹好看 | 无独立校准，可能拒绝安全直线、STOP或保守避让 |
| C 把raw NLP objective作为唯一quality score | 已有数值 | 跨target/cycle/reference不可比，权重单位混合 |
| D 预测轨迹必须有明显曲率 | 视觉直观 | route-only/稳定避让的真实最优解可能是直线 |
| E 只比较本cycle candidate，不看previous accepted plan | 无历史依赖 | 无法发现solve-to-solve churn、回切和recovery振荡 |
| F 无条件比较相邻solve计划 | 容易实现 | 新目标/phase/route变化时会把正当响应误报为抖动 |
| G 将quality WARN纳入加权overall score | 可排序 | 可能抵消或掩盖hard obligation，破坏DP-03 layered semantics |
| H route quality继续使用单bearing无限直线 | 沿用core | 弯曲route progress/rejoin语义错误 |

#### 风险、失效边界与验证

| 项 | 评估 |
|---|---|
| 实现风险 | **中**：主要为route projection、absolute-time overlap与metric evidence，不改control authority |
| 误拒风险 | **低**：V1 advisory；mandatory failures仍由其owner层处理 |
| 误接受风险 | **中**：纯质量恶化不会阻断；但当前无证据支持hard阈值，先保留可观测性与校准数据 |
| 失效边界 | 不证明安全/COLREG/trackability；无route/prior context时部分metric N/A/NOT_EVALUATED；不支持跨不兼容context比较 |
| 核心验证 | 安全直线不warn曲率；控制抖动WARN但ACCEPT；mandatory ROT violation仍DP-09 reject；5s/15s重叠对齐；context变化不报假churn；弯曲polyline progress；STOP无progress；release后快/慢/re-entry恢复；objective target-set变化不比较；quality WARN不改overall |

#### 技术分解状态

DP-10冻结V1 quality advisory与metric families；previous accepted record DP-14、hold/current comparison DP-12、exact warning阈值与未来hard promotion DP-17、GUI evidence DP-15、校准/验证DP-18继续裁决。

### Step4-DP11 · multi-target reconciliation、per-target verdict与Ship0 aggregate（final）

#### 初步推荐

采用“**先核对五类目标集合，再形成per-TrackKey verdict，最后以mandatory conjunction生成Ship0 aggregate**”。Primary target只服务展示；不拥有更高安全权重。任何相关目标的mandatory `FAIL/UNKNOWN/NOT_EVALUATED`均不能被另一目标的安全余量、规则PASS或加权分数抵消。

L4不重新规划多目标动作。Lifecycle拥有obligation compatibility和aggregate directive；Assembler负责将兼容directive装配进单个NLP并对明显冲突fail-fast；L4只防御性验证candidate是否同时履行每个目标义务以及各集合/identity是否完整。

#### 五集合reconciliation

对每个`TrackKey=(stable_id,generation)`建立canonical target manifest：

| 集合 | 预期内容 | L4核对 |
|---|---|---|
| execution tracks | 当前snapshot全部targets、freshness/quality/exclusion facts | 定义safety审计全集，不允许裸ID复用 |
| Lifecycle decisions | 每个usable relevant target的episode/role/phase/side/action或typed exclusion | 与track generation一一对应 |
| target predictions | 81 absolute-time states及uncertainty/footprint provenance | DP-05所需目标必须完整 |
| Assembler admissions/bindings | admitted/excluded reason、slot、schedule、constraint role | 不得静默丢目标 |
| solver selected slots/rows | 最多16个graph-baked target slots及actual row registry | 与Assembler binding/hash一致 |

每个track最终必须落入唯一状态：

- `SAFETY_AND_COLREG_RELEVANT`
- `SAFETY_ONLY`（例如CLEAR/RELEASED，但仍需动态安全）
- `EXCLUDED_WITH_TRUSTED_REASON`
- `UNRECONCILED`

`UNRECONCILED`、generation错配、重复slot、prediction缺失、Lifecycle decision缺失或静默truncation：integrity/target-set UNKNOWN并reject。Exclusion reason必须来自trusted policy并含time/provenance；“超过16个”“非primary”“未被solver选择”不是安全排除理由。

#### Per-target verdict

每个相关TrackKey产生独立record：

| 子结果 | 适用性 |
|---|---|
| identity/evidence | 全部target mandatory |
| swept hull safety | 全部`SAFETY_*` target mandatory；含unselected |
| COLREG consistency | active Lifecycle obligation mandatory；CLEAR/RELEASED为N/A+applicability witness |
| action timing/past-clear | 对应active role/phase mandatory |
| uncertainty/prediction | 按DP-05 profile mandatory |
| quality contribution | advisory |

record含所有failure/witness，不采用“一个target一个bool”。排序固定为`TrackKey generation → layer precedence → absolute time → code`，不依赖输入顺序或risk排序。

#### Lifecycle aggregate与candidate compatibility

| Upstream状态 | L4裁决 |
|---|---|
| Lifecycle给出兼容aggregate directive，Assembler成功装配 | 独立验证candidate同时满足全部per-target obligations |
| Lifecycle同侧合并或合法STOP | 不质疑仲裁；验证每目标安全/COLREG及STOP trackability |
| Lifecycle返回`MANEUVER_CONFLICT` | 无production candidate资格；保留冲突targets/obligations evidence |
| Assembler返回directive/side/schedule conflict | typed pre-solver rejection；L4若收到candidate则integrity reject |
| individually valid obligations但candidate仅满足部分 | 对应targets fail；Ship0 aggregate reject |
| candidate通过全体，但某target不是solver selected | 只要完整预测下L4 safety/COLREG均通过可接受；selected与relevant不等价 |

L4不选择“最危险目标优先而忽略其他目标”，不把starboard/port投票，也不搜索新corridor。若所有义务确实无共同解，正确结果是上游typed conflict/no candidate，而不是L4折中放行。

#### Ship0 aggregate与scope

Ship0 aggregate规则：

1. integrity先核对全目标集合。
2. 所有相关target的mandatory safety/COLREG/action checks取AND。
3. global numerical、trackability、evidence mandatory checks再取AND。
4. quality warning不改变接受资格。
5. `primary_target`取earliest-risk或稳定display policy，仅作summary，不能改变aggregate。

目标船之间的collision/grounding：

- 可由Evaluator/global evidence报告；明确`scope=GLOBAL_ALL_VESSELS`。
- 不进入`scope=SHIP0_PLAN_ACCEPTANCE` hard aggregate，因为Ship0 Mid-MPC不控制脚本目标船。
- 不删除、不隐藏。GUI/capability必须同时表述“Ship0 PASS”与“global target-target event存在”。
- Ship0与任一target碰撞/净距失败仍是Ship0 hard failure。

#### Capacity与runtime

L4几何审计复杂度固定`O(TN)`，`N=80`。Policy必须声明max execution tracks；超过上限时返回`TARGET_CAPACITY_EXCEEDED`并fail-closed，禁止截断。Solver最多16 selected是L3 capability：若第17个安全相关目标需进入NLP才能形成可接受candidate，Assembler应在solve前返回`CORE_CAPABILITY_MISMATCH`。L4不能通过只检查16个掩盖该限制。

#### Evidence projection

Full artifact保存canonical target manifest、五集合来源、admission/exclusion、slot/row binding、per-target verdicts、aggregate directive和所有witness。Inline/GUI保留目标总数、relevant/selected/excluded/unreconciled计数、Ship0 minimum clearance、primary failure及target-target global event计数；不得只显示primary target造成“其他目标已通过”的假象。

#### 证据链

| 证据 | 推导 |
|---|---|
| [R22][R32] solver最多16 selected，但Assembler可发布全部track predictions；当前排除reason schema不足 | safety全集不能由solver selected定义，必须五集合核对 |
| [R42] Lifecycle已拥有同侧合并、STOP与`MANEUVER_CONFLICT` authority | L4不重新仲裁，只验证aggregate兼容性 |
| [R4][R8] multiship实证Ship0安全可PASS而脚本target-target发生碰撞 | Ship0 hard scope与global diagnostic必须分离 |
| [R55] Lifecycle/Assembler typed failures被coarse status压缩 | 保留owner/code/targets，公共status仅稳定投影 |
| [R74] 16x80 pure geometry成本远小于NLP且可bounded O(TN) | 全目标审计可行，但容量必须显式fail-closed |
| [R70][R72] witness需统一TrackKey/frame/unit/time且projection不可成为authority | per-target完整record与稳定排序进入canonical artifact |

#### 备选与弃用草案

| 方案 | 优点 | 弃用理由 |
|---|---|---|
| A 五集合reconcile + per-target mandatory AND（推荐） | 完整、可解释、防silent admission与ID reuse | schema与证据量增加 |
| B 只检查primary/earliest-risk target | 最快 | 漏其他目标安全和COLREG义务 |
| C 只检查solver selected最多16个target | 接近NLP | admission自证，漏unselected碰撞目标 |
| D 将每目标结果取minimum clearance +一个global bool | 摘要简单 | 丢失role、wrong-side、past-clear、identity与failure provenance |
| E 对per-target score求平均/加权 | 便于排序 | 一个目标的hard failure可被其他目标高分抵消 |
| F L4对冲突directive投票或选最危险目标 | 提高candidate产出 | 越权重做Lifecycle/Assembler决策并牺牲其他义务 |
| G 将所有target-target事件纳入Ship0 hard aggregate | global安全表面更强 | Ship0无控制authority；固有脚本碰撞会错误否决Ship0计划 |
| H 超容量时截断低风险目标 | 保持实时性 | 被截断目标可能成为真实危险，且claim不完整 |
| I 继续用裸target ID而不带generation | 字段少 | ID复用后receipt/prediction/Lifecycle可能串到旧目标 |

#### 风险、失效边界与验证

| 项 | 评估 |
|---|---|
| 实现风险 | **中高**：需五集合canonical manifest、typed exclusions和稳定per-target aggregate |
| 误拒风险 | **中**：缺现有exclusion schema或>16相关目标会fail-closed；这是能力边界而非场景调参问题 |
| 误接受风险 | **低至中**：主要风险是trusted exclusion错误；通过policy provenance、mutation tests与all-track safety oracle控制 |
| 失效边界 | 仅证明Ship0 candidate对当前预测targets；不控制target-target行为；超capacity不声称部分安全 |
| 核心验证 | primary PASS/secondary FAIL；unselected collision target；CLEAR safety-only；missing Lifecycle/prediction；duplicate slot；ID generation reuse；target order permutation；same-side merge；legal STOP；MANEUVER_CONFLICT；candidate只满足部分义务；16/17 target capacity；Ship0 PASS+target-target collision diagnostic |

#### 技术分解状态

DP-11冻结目标集合、per-target与Ship0 aggregate语义；hold期间新target与generation变化DP-12、公共failure映射DP-13、artifact projection DP-15、capacity budget DP-16、exact exclusion/capability policy DP-17继续裁决。

### Step4-DP12 · fresh acceptance、hold revalidation与immediate replan（final）

#### 初步推荐

采用“**fresh candidate完整L4；held plan按当前absolute time和execution prefix轻量重验；context失效最多触发一次同算法immediate replan**”。Hold仅表示本周期不重新运行IPOPT，不代表旧`SUCCESS/feasible`可继承。

同一纯Module继续使用单一`evaluate(request)`入口，由typed `mode=FRESH_CANDIDATE|HELD_ACCEPTED_PLAN`选择已冻结check plan。L4不保存状态；Adapter持有上一份immutable accepted record并负责SOLVE/HOLD调度、一次replan和fail-stop。

#### Fresh candidate

Fresh模式执行DP-02..11全部适用layers：identity、numerical、swept safety、profile、COLREG、trackability、quality、evidence。只有overall production `ACCEPT`后，Adapter才原子提交active plan、receipt、hold eligibility和warm authority。Rejected fresh candidate不得替换旧active plan，也不得被下一tick当hold计划。

#### Held plan validation view

Hold不修改原receipt或伪造新solver result。基于当前`now`构造只读validation view：

| 内容 | 规则 |
|---|---|
| parent acceptance | 必须为同session/epoch/algorithm/policy的production receipt，hash完整且未过期 |
| support interval | `now`必须落在原plan absolute-time support内；禁止把旧trajectory重新贴到当前时间 |
| state slice | 从原81 knots按absolute time切取remaining reference；state按定义插值 |
| command slice | 从80 intervals取当前piecewise-constant command；禁止相邻commands线性插值 |
| current execution | 使用当前实测ownship state、最新tracks/Lifecycle/predictions/route/plant capability |
| active prefix | 从`now`覆盖到`min(next scheduled solve, receipt validity end, policy hold horizon)` |
| provenance | 输出parent receipt hash、support time、slice indices、current context hash与validation mode |

验证ownship实际状态到held reference的偏差，再以当前状态、current command和可信active-prefix capability/tube形成execution-prefix prediction。不得只截取旧planned position并假装ownship仍在那里。

#### Hold mandatory checks

Hold不重做已接受candidate的IPOPT/KKT/objective，也不重新执行完整1200s质量评价；必须重验当前可能执行窗口：

1. parent receipt/hash/profile/session/epoch完整性与validity。
2. current ownship position/COG/SOG/time相对held reference的deviation envelope。
3. target set TrackKey generations、freshness与Lifecycle episode/directive兼容性。
4. 最新target predictions下active prefix的全部目标continuous hull safety。
5. active COLREG action deadline、locked side、wrong-side/recovery权限未失效。
6. current held command在真实active plant envelope内可执行。
7. route/static context、policy、plant/controller/profile identity未变化。
8. evidence/canonical result在hold子预算内完整生成。

Hold结果使用独立typed aggregate：

- `HELD_PLAN_VALIDATED`：只允许执行该active prefix；不延长原plan validity。
- `HELD_PLAN_REPLAN_REQUIRED`：context可由同算法新solve处理；无command commit。
- `HELD_PLAN_REJECTED`：integrity、deadline、不可恢复安全/规则/trackability失败；fail-stop。

不得把hold validation显示为新的`Solve_Succeeded`，不得签新的full-plan acceptance receipt，也不得更新warm seed来源。

#### Immediate replan triggers

以下变化使旧plan不可直接hold：

| Trigger | 结果 |
|---|---|
| 新target或TrackKey generation变化 | `REPLAN_REQUIRED` |
| Lifecycle episode/role/side/phase/action变化 | `REPLAN_REQUIRED`；若authority矛盾则reject |
| ownship deviation超过envelope | `REPLAN_REQUIRED`；若当前prefix已不安全则reject |
| target显著机动、prediction hash/uncertainty envelope变化 | `REPLAN_REQUIRED` |
| route/ENC/policy/plant/controller/profile变化 | receipt不兼容；通常`REPLAN_REQUIRED`，identity损坏则reject |
| active-prefix safety/COLREG/trackability失败 | 若新solve仍可能且未超deadline则replan，否则reject |
| receipt过期、support耗尽、hash损坏 | 过期/耗尽replan；损坏integrity reject |

Adapter仅在本cycle尚未执行solver、总critical-path deadline仍足够、相同`mid_mpc_ipopt`且未replan过时，允许一次immediate fresh solve。不能切换算法、输出零控制、继续旧command或warm/cold双重retry。一次replan失败、被L4拒绝或超总deadline：fail-stop。

#### Scope与claim

Hold hard scope至少覆盖当前到next solve的active prefix；完整remaining horizon可作为advisory/缓存优化，但不能替代prefix重验。每个hold tick的`VALIDATED`只证明当前snapshot下该短执行窗口可继续，不继承原fresh plan对未来时刻的永恒许可。

如果hold检查预算不足或mandatory evidence未完成，结果为`UNKNOWN/REPLAN_REQUIRED`或reject，禁止按耗时跳过layer后沿用旧SUCCESS。具体预算和replan eligibility由DP-13/16冻结。

#### Timeline与用户可观察性

Adapter维护两条不可混淆的时间线：

- `active_plan_timeline`：最后一份accepted fresh plan及本tick hold validation状态。
- `latest_attempt_timeline`：本tick hold/replan/fresh attempt，即使被拒也记录。

GUI显示`HELD VALIDATED / REPLAN REQUIRED / REJECTED`、parent acceptance hash、current support interval、deviation与first failure；rejected/stale candidate轨迹不得继续作为active预测线。Solver未执行时不得显示新求解编号或IPOPT成功。

#### 证据链

| 证据 | 推导 |
|---|---|
| [R52][R53] 当前Adapter按时钟hold并继承旧status，100m状态偏差仍输出SUCCESS | hold必须消费current state/context并重新验证prefix |
| [R46][R47] commands为15s intervals，现有hold却线性插值 | state interpolation与piecewise-constant command sampling必须分离 |
| [R54][R59] 失败/hold timeline与旧solver trace混淆 | active plan与latest attempt双时间线，hold不伪装新solve |
| [R60] multi-step safety filter表明持续可执行性不能由单周期bool永久继承 | active prefix需每hold tick重验 |
| [R56][R58] receipt/warm只可来自production accepted fresh plan | hold不签新receipt、不产生新warm authority |
| [R61] timeout/commit仍需总deadline与context freshness | immediate replan受同一总deadline约束且最多一次 |

#### 备选与弃用草案

| 方案 | 优点 | 弃用理由 |
|---|---|---|
| A fresh full L4 + hold active-prefix revalidation + one replan（推荐） | 安全、bounded、保持5s solve/15s grid效率 | schema与Adapter状态机增加 |
| B hold直接继承旧SUCCESS直到下次solve | 最简单 | 已实证可跨大偏差、新目标和stale context泄漏 |
| C 每个hold tick重做完整IPOPT和full L4 | 最强更新 | 实质取消hold，增加deadline/算力且改变调度契约 |
| D hold只检查ownship deviation | 成本低 | 漏新目标、target maneuver、Lifecycle/policy/plant变化与prefix safety |
| E 将旧trajectory时间轴平移到`now` | 容易绘图 | 改写计划语义并伪造未来support/provenance |
| F 线性插值interval commands | 表面平滑 | 改变真实piecewise-constant执行语义 |
| G stale后无限次same-cycle replan或warm→cold retry | 提高表面成功率 | 可超deadline、非确定且违反一次尝试/no-fallback边界 |
| H hold失败后继续上一command等待下一周期 | 避免中断 | 已知无当前安全许可，属于未声明fallback |
| I hold PASS签新full receipt并延长validity | 减少fresh solve | 用短prefix验证无限续期，破坏acceptance/warm authority |

#### 风险、失效边界与验证

| 项 | 评估 |
|---|---|
| 实现风险 | **高**：需Adapter调度事务、absolute-time slicing、prefix prediction与双时间线协同 |
| 误拒风险 | **中**：频繁prediction/context变化可能触发replan；通过typed compatibility与校准deviation envelope控制 |
| 误接受风险 | **中**：短prefix只覆盖到next solve；依赖每tick重验、deadline和Session fail-stop纪律 |
| 失效边界 | `VALIDATED`不证明完整remaining horizon或延长receipt；replan只限同算法一次；无预算/证据不继续旧plan |
| 核心验证 | 5s hold command不插值；100m deviation；小偏差VALIDATED；新target/generation；Lifecycle transition；target maneuver；route/policy/plant变化；receipt expiry/hash corruption；prefix collision；one-replan success/reject/timeout；hold不签receipt；active/latest GUI timelines；rejected trajectory不显示 |

#### 技术分解状态

DP-12冻结fresh/hold/replan时序语义；rejection到公共status与Session事务DP-13、receipt/warm DP-14、timeline artifact DP-15、budget DP-16、deviation/validity阈值DP-17继续裁决。

### Step4-DP13 · rejection、PlanStatus projection、atomic commit与Session fail-stop（final）

#### 初步推荐

采用“**L4只返回typed裁决；Adapter完成稳定公共状态投影与单一原子commit；任何未接受计划均无command并使Session fail-stop**”。现有`PlanStatus`/`FailureSource`枚举保持兼容，不为每个L4原因扩散公共枚举；完整layer failures、owner、recoverability与witness保存在typed acceptance result/details中。

唯一例外是DP-12已裁决的hold stale：在尚未求解且总预算允许时，Adapter可先执行一次同算法immediate replan。它不是fallback；replan失败或fresh candidate被拒后立即终止执行。

#### Stable `PlanStatus` projection

公共status由完整failure list按DP-03稳定precedence派生，绝不采用last-error-wins：

| L4/native outcome | Public `PlanStatus` | `feasible` | Selected command |
|---|---|---:|---|
| strict fresh ACCEPT + desired solution | `SUCCESS` | true | 有，原子commit后 |
| strict fresh ACCEPT + eligible solver wall-timeout candidate，且总deadline/freshness仍满足 | `TIMEOUT_FEASIBLE` | true | 有，原子commit后 |
| safety/COLREG/trackability mandatory fail或unknown | `INFEASIBLE` | false | 空 |
| numerical/KKT-required-evidence/candidate feasibility failure | `NUMERICAL_FAILURE` | false | 空 |
| request/schema/frame/unit/profile/hash/target-set/authority integrity invalid | `INVALID_INPUT` | false | 空 |
| required runtime dependency确实不可用 | `DEPENDENCY_UNAVAILABLE` | false | 空 |
| MASS_PARITY diagnostic被送入production dispatch seam | `INVALID_INPUT` + `PROFILE_NOT_DISPATCHABLE` | false | 空 |
| total critical-path deadline超过，未完成commit | `NUMERICAL_FAILURE` + `TOTAL_DEADLINE_EXCEEDED` | false | 空 |
| unexpected L4 internal exception | `NUMERICAL_FAILURE` + `L4_INTERNAL_ERROR` | false | 空 |

`TIMEOUT_FEASIBLE`只表示native solver timeout但同一candidate已通过完整L4且仍能及时commit；不是“超总deadline也下发”。若该candidate被业务层拒绝，使用对应`INFEASIBLE`而不是timeout status掩盖主因。

`FailureSource`保持现有三值：scenario提供的无效输入用`SCENARIO`，调度/事务/deadline问题用`ADAPTER`，solver/candidate/L4 plan-content失败用`ALGORITHM`。更精确owner另存`failure.owner=LIFECYCLE|ASSEMBLER|SOLVER|L4_*|PERSISTENCE`，不丢失责任边界。

#### Atomic acceptance transaction

Adapter必须在任何执行状态可见前完成以下顺序：

1. 收到完整in-memory L4 result与canonical acceptance hash。
2. 再检查total monotonic deadline、current snapshot/context freshness及Session仍处于本attempt。
3. 构造待提交的immutable active plan、selected command、accepted receipt、warm eligibility、latest-attempt/active-plan trace。
4. 在单一临界区原子替换`_solution/current_plan/receipt/_last_solve_time/warm authority/active trace`。
5. 仅原子提交成功后发布`planner_solved/command_selected`事件。
6. full artifact异步持久化；其失败按DP-15/16标incomplete，不回滚已完成in-memory decision。

禁止在L4前写入`_solution`、更新时间、发布solved事件或暴露candidate prediction。任何一步在commit前失败，全部active state保持未提交；但本次latest-attempt rejection evidence必须形成。

#### Rejection transaction与old-plan isolation

Fresh rejection或replan rejection时：

- selected command为空；`fallback_used=false`。
- rejected candidate trajectory只进入latest-attempt evidence，不成为active plan/GUI active prediction。
- 清除本算法active plan、hold eligibility、accepted receipt和warm eligibility；不能回到上一份计划。
- 生成完整rejection result/hash、稳定primary reason及全部并发failures。
- 发布`planner_rejected`，绝不发布`planner_solved`。
- 抛出携带structured acceptance reference的`ColavExecutionError`，由Session统一进入terminal `FAILED`。

旧accepted plan不因“之前安全”继续控制；这与no-fallback一致。用户显式reset/new session后方可重新启动，不在下一tick隐式恢复。

#### Recoverability taxonomy

Recoverability用于解释，不改变当前cycle无command事实：

| Class | 例子 | 当前动作 |
|---|---|---|
| `REPLAN_ONCE_ALLOWED` | hold出现新target、轻度deviation、prediction变更且预算足够 | DP-12同算法一次fresh replan |
| `RESET_REQUIRED` | profile/policy/route/plant epoch变化、receipt incompatibility | 本attempt停止；显式reset/restart |
| `INPUT_CORRECTION_REQUIRED` | frame/unit/schema/authority缺失 | fail-stop，修复输入后新session |
| `DEPENDENCY_RESTORE_REQUIRED` | IPOPT/CasADi/required capability不可用 | fail-stop，恢复依赖后新session |
| `NONRECOVERABLE_THIS_SESSION` | candidate mandatory hard failure、internal invariant损坏、deadline exhausted | terminal FAILED |

Fresh rejection不得标`REPLAN_ONCE_ALLOWED`后自动再求一次；仅hold stale在本cycle尚未solve时享有该边界，避免warm/cold或重复NLP retry。

#### Session与UI行为

Session对任何最终rejection采用单一状态迁移：`RUNNING -> FAILED`，暂停仿真推进且不调用plant step应用替代command。保留最后已执行actual state，但不保留可继续执行的planner command。

GUI/API必须同时显示：

- public status、primary code、source和recoverability；
- `accepted=false`、`selected_command=null`、`fallback_used=false`；
- 完整layer failure计数/首条摘要及acceptance artifact/hash；
- latest attempt与previous historical accepted plan明确分区；previous只作history，不能画成active；
- timeout candidate是accepted还是因总deadline/revalidation被拒。

#### 证据链

| 证据 | 推导 |
|---|---|
| [R54] 当前fresh异常路径记录不一致且Session最终进入FAILED | 统一Adapter事务与terminal fail-stop，不新增隐式恢复态 |
| [R55] 公共PlanStatus/FailureSource较粗，现有typed owner/code被压缩 | 保持enum稳定，用structured failures保存细节 |
| [R58] L3 candidate selection不等于L4 production acceptance | 仅L4后原子commit和发布planner_solved |
| [R59] GUI当前可回退显示上一solve，遮蔽新rejection | active/latest双时间线与空command明确化 |
| [R61] solver timeout仍须总deadline和freshness | `TIMEOUT_FEASIBLE`只在完整L4及及时commit后成立 |
| [R67][R68] persistence失败不应改变已完成控制裁决 | artifact sink移出原子authority事务，但claim标incomplete |

#### 备选与弃用草案

| 方案 | 优点 | 弃用理由 |
|---|---|---|
| A typed L4 result + stable projection + atomic commit + terminal fail-stop（推荐） | 兼容公共API、无状态泄漏、失败可解释 | Adapter事务实现复杂度增加 |
| B 为每个L4 failure新增一个`PlanStatus`枚举 | 直接可见 | 破坏公共兼容并造成枚举爆炸，仍无法表达并发失败 |
| C 所有L4 rejection统一映射`INFEASIBLE` | 简单 | 丢失input/numerical/dependency/timeout owner与恢复语义 |
| D 第一个失败立即抛异常且不生成完整result | 快速fail | 丢失并发failure、hash、GUI与replay evidence |
| E L4前先保存solution，失败后再rollback | 易接现有Adapter | exception/事件/并发可泄漏rejected plan，rollback难保证完整 |
| F rejection后继续previous accepted plan | 服务不中断 | 无当前许可且违反no-fallback/fresh rejection边界 |
| G rejection后输出零速/保持舵命令 | 看似安全 | 未经L4验证的替代控制，属于隐藏fallback且可能更危险 |
| H fresh rejection自动再做cold/warm retry | 可能偶然成功 | 扩大deadline/非确定性并绕过一次candidate裁决 |
| I artifact持久化失败时回滚已下发command | evidence强一致 | 磁盘状态反向改变控制决定，可能造成时序不一致 |

#### 风险、失效边界与验证

| 项 | 评估 |
|---|---|
| 实现风险 | **高**：需重构Adapter提交点、异常路径、Session事件与GUI projection为同一事务语义 |
| 误拒风险 | **低至中**：映射不改变L4裁决；总deadline/freshness最终门可能拒绝数值可行candidate |
| 状态泄漏风险 | **高后降为低**：若任一字段/事件先写会泄漏；以transaction tests和failure injection控制 |
| 失效边界 | fail-stop不提供BC-MPC或安全停车；恢复需用户reset/new session；TIMEOUT_FEASIBLE不绕过总deadline |
| 核心验证 | 每layer到PlanStatus truth table；并发failure precedence；desired/timeout accepted；timeout过总deadline；fresh rejection无old plan/command/warm；L4各commit步骤failure injection；planner_solved只在commit后；artifact sink失败不回滚；Session RUNNING→FAILED；GUI无stale trajectory；fallback_used永远false |

#### 技术分解状态

DP-13冻结公共status、recoverability、atomic commit与Session fail-stop；accepted receipt/warm字段DP-14、artifact/timeline schema DP-15、deadline/persistence budget DP-16继续裁决。

### Step4-DP14 · Accepted Plan Receipt、neutral handoff与warm-start authority（final）

#### 初步推荐

采用“**L4 acceptance certificate + Adapter atomic commit receipt + immutable previous accepted plan record**”两阶段authority。L4只证明candidate满足production policy；Adapter只在DP-13最终deadline/freshness检查及原子commit成功后，赋予该certificate“已成为active accepted plan”的事实。Assembler仅消费这一neutral record生成数值seed，不与L4直接互调。

这避免三个循环：L4不调用Assembler；Assembler不调用L4；Lifecycle不持有warm/acceptance状态。Adapter/Orchestrator是唯一handoff owner。

#### Neutral contract分层

| Contract | Producer | Consumer | 内容/权限 |
|---|---|---|---|
| `PlanAcceptanceCertificate` | pure L4 | Adapter/evidence | candidate-bound ACCEPT/DIAGNOSTIC/REJECT、layer hashes、policy/parent identity；本身不证明已commit |
| `AcceptedPlanReceipt` | Adapter atomic commit，嵌入certificate hash | hold/Assembler/GUI | 证明某production accepted candidate在某session/epoch/cycle已原子激活；轻量、immutable |
| `PreviousAcceptedPlan` | Adapter保存的immutable record | Assembler及L4 quality/hold request | receipt + accepted state knots/interval commands + eligible primal payload；不是prefix commitment |
| `SeedPlan` | Assembler | NumericalPreparer/solver | 当前problem的deterministic cold或previous-primal initial guess及完整provenance |

这些类型放在planner-neutral contract module，不能定义在L4 implementation或Assembler private module中。L4/Assembler只依赖contracts，避免import cycle和authority倒置。

#### Receipt minimum binding

`AcceptedPlanReceipt`必须绑定：

- schema/version、session id、reset epoch、cycle/attempt/solve identity；
- algorithm id、solver/backend/version、formulation/layout/grid identity；
- expected/actual strict profile、L4 policy与active ODD hash；
- request/problem/prepared/raw candidate/acceptance certificate hashes；
- acceptance outcome、native termination class、commit absolute time；
- plan support `[start,end]`、hold/warm validity；
- route/ENC identity、active plant/controller/capability hashes；
- Lifecycle snapshot/episode/aggregate directive hash；
- ordered TrackKey generations、target slot/binding hashes；
- accepted state/control/primal payload hash与canonicalization version；
- `fallback_used=false`、persistence state单独记录。

Receipt不包含可变telemetry、artifact path、wall clock或完整raw vectors。`PreviousAcceptedPlan`通过hash链接实际immutable arrays；arrays复制/read-only，修改后hash不一致即integrity failure。

#### Warm eligibility matrix

Assembler收到previous record后机械判定：

| 条件 | 结果 |
|---|---|
| receipt/certificate/hash损坏、数组被篡改、identity自相矛盾 | `PREVIOUS_ACCEPTED_PLAN_CORRUPT`，assembly/input fail-closed |
| 正常缺失、过期、support不足 | 显式deterministic cold seed，不视为错误 |
| session/reset epoch、algorithm、formulation/layout/grid、strict profile/policy不兼容 | cold seed，记录具体incompatibility |
| Lifecycle episode/locked side、route、plant/controller、TrackKey generation/slot语义不兼容 | cold seed；不把旧方向/目标带入新NLP |
| production strict accepted + compatible + absolute support足够 | eligible previous-primal seed |
| accepted `TIMEOUT_FEASIBLE`但完整L4及atomic commit均成立 | 与SUCCESS同样按compatibility判定，可eligible |
| L3 converged但L4 rejected、MASS_PARITY diagnostic、fallback、hold validation、旧epoch | 禁止作为seed authority |

正常不兼容走cold，不让warm优化机会成为可用性硬依赖；证据损坏则fail-closed，避免把篡改伪装成普通cold。

#### Absolute-time primal resampling

与Candidate 3已裁决SeedPlan保持一致：

1. 新problem的每个absolute state/control time，从旧accepted plan support重采样；禁止`shift(x,1)`，因为5s solve period不整除15s stage。
2. Heading先ordinary unwrap再插值/hold；speed按相应state/control语义采样。
3. 重叠区使用旧accepted heading/speed primal；超出旧support的tail由当前directive-guided deterministic cold seed补齐。
4. 投影到当前`StageCapabilityEnvelope`并复核rate/decel/common corridor；projection后仍不满足numeric bounds则放弃previous seed，使用cold并记录原因。
5. Current problem的CPA/direction slacks按当前strict preparation重建为fixed zero；不得沿用旧slack。
6. V1只用heading/speed primal；dual multipliers、bound/constraint multipliers与`warm_start_same_structure`均禁用。

Warm seed只是IPOPT初值。新candidate仍重新运行全部L3与完整L4；receipt不继承旧safety/COLREG acceptance，也不把旧plan变为prefix equality。

#### Failure、reset与retry

- Fresh rejection、commit failure、Session reset/time rewind/algorithm switch立即清除receipt、previous record与warm eligibility。
- Hold validation只引用原receipt，不签新receipt、不延长support。
- Warm-seeded solve失败或被L4拒绝时，禁止自动同cycle cold retry；遵守DP-13 fail-stop。
- Graph cache可独立复用，但不得显示为warm plan；seed、cache、hold三类概念分别统计。
- Warm收益只记录iterations/latency/candidate difference；无p95证据前不写入capability claim。

#### Evidence与GUI

每次assembly/solve输出`seed_source=COLD|PREVIOUS_ACCEPTED_PRIMAL`、receipt/plan hash、eligibility checks、resample overlap、tail fill、projection magnitude、rejection reason、`primal_seed_used`、`dual_seed_used=false`。GUI可显示“accepted-plan warm/cold”，但不能把warm解释为更安全或沿用旧解。

#### 证据链

| 证据 | 推导 |
|---|---|
| [R56] Candidate 3已冻结stateless Assembler、absolute-time previous-primal seed和dual disabled | L4 handoff必须适配该contract，不另造shift/dual机制 |
| [R57] Ipopt warm start是数值初始化，非安全或执行资格 | 新candidate仍完整L4，warm不继承acceptance |
| [R58] L3 candidate acceptance与L4 production acceptance不同 | 只有L4 certificate + Adapter commit receipt可授权seed |
| [R46] 5s/15s时轴不整除且angle/command语义不同 | 使用absolute-time resample、unwrap和cold tail fill |
| [R52][R54] hold/reset/failure可能遗留旧状态 | receipt绑定epoch并在rejection/reset原子清除 |
| [R62] warm收益与solver basin影响存在但实际p95未知 | 只记录性能，不宣称稳定收益或自动retry |

#### 备选与弃用草案

| 方案 | 优点 | 弃用理由 |
|---|---|---|
| A L4 certificate + Adapter receipt + neutral previous record（推荐） | authority与commit事实分离、无循环、可重放 | contract/hash字段较多 |
| B 只要solver success就保存`previous_x` | 最简单 | 会混入L4拒绝、parity、旧epoch和不兼容目标 |
| C L4直接生成`SeedPlan`并调用Assembler | acceptance可控制warm | 形成反向依赖并侵入L1/L2数值初始化authority |
| D Assembler自行读取Adapter/L4全局last solution | 调用参数少 | 隐式状态、不可重放、reset和并发污染 |
| E 旧raw x整体shift一个stage | 实现快 | 5s/15s错10s，angle/target/capability未对齐 |
| F V1启用primal+dual完整warm start | 潜在更快 | dual绑定row order/active bounds，当前无稳定same-point证据和benchmark |
| G warm failure后自动cold retry | 提高表面成功率 | 超deadline、非确定并违反一次candidate/fail-stop边界 |
| H hold validation每tick签新receipt | 延长warm来源 | 用短prefix复核无限续期并混淆fresh authority |
| I 所有receipt不兼容/损坏都静默cold | 高可用 | 会隐藏篡改与identity corruption；损坏必须fail-closed |

#### 风险、失效边界与验证

| 项 | 评估 |
|---|---|
| 实现风险 | **中高**：需neutral schema、certificate/commit两阶段hash及Candidate 3 handoff接线 |
| 误用风险 | **中**：最危险是把warm当acceptance/prefix；通过命名、types与完整L4复核控制 |
| 数值风险 | **中**：previous seed可改变非凸局部解盆地；接受标准不变且记录cold/warm差异 |
| 失效边界 | 不保证warm更快或同解；dual禁用；不兼容正常cold，证据损坏hard fail；无自动cold retry |
| 核心验证 | accepted SUCCESS/TIMEOUT receipt；L4 reject/parity/hold禁用；5s/15s resample；angle wrap；cold tail fill；projection；slack zero重建；dual false；target/episode/profile/layout/reset失配cold；tampered hash reject；warm failure无retry；graph cache与seed分离；new candidate完整L4 |

#### 技术分解状态

DP-14冻结certificate/receipt/previous record与warm authority；exact artifact schema/hash projection DP-15、runtime performance DP-16、compatibility/profile version DP-17、warm/cold validation DP-18继续裁决。

### Step4-DP15 · canonical evidence、artifact、trace与GUI projection（final）

#### 初步推荐

采用“**一个canonical in-memory acceptance record，三种有hash约束的投影**”：full replay artifact、bounded inline trace、GUI view。只有canonical record是L4裁决authority；inline/GUI不得重算、猜测或改变结果。Evaluator事后证据使用独立source/scope，不能覆盖或冒充L4。

完整链条固定为：

`Request → Assembly/Problem → Numerical Preparation/Prepared → Solver Candidate → L4 Acceptance Certificate → Adapter Commit Receipt`

每一段包含schema/version、content hash和parent hash。Artifact envelope可在commit后同时保存certificate与receipt，但不得形成循环hash：L4 acceptance hash排除commit/persistence telemetry；receipt引用acceptance hash；artifact envelope再引用两者。

#### Canonical acceptance record

`MidMpcPlanAcceptanceRecordV1`至少包含：

| Section | 内容 |
|---|---|
| identity | schema/canonicalization、session/epoch/cycle/attempt、algorithm/profile/policy、source/scope |
| parent chain | request/problem/preparation/prepared/candidate hashes及verified flags |
| authority snapshot | trusted ODD、50m门、plant/controller/capability、route/ENC、Lifecycle、target manifest identities |
| candidate | native/normalized status、81 states、80 commands、target predictions、raw/prepared evidence refs |
| layers | integrity/numerical/safety/COLREG/trackability/quality/evidence typed results |
| failures/warnings | 完整有序list、primary projection、recoverability |
| witnesses | per-row/per-target/per-segment/time/metric原始事实与threshold/tolerance |
| aggregate | ACCEPT/REJECT/DIAGNOSTIC_ONLY、dispatch eligibility、selected command presence |
| certificate | canonical acceptance hash、生成版本、determinism metadata |

Canonical construction属于critical path mandatory evidence。若typed record、稳定排序、hash或required witness构造失败，evidence layer `UNKNOWN/FAIL`并拒绝；不能只返回bool后补证据。

#### Witness schema与ordering

统一witness fields：

- `layer/code/outcome/severity/owner/scope`
- `TrackKey(stable_id,generation)`与Lifecycle episode（适用时）
- `frame/unit/quantity`
- absolute time、state knot或interval segment、`tau`
- measured/lower/upper/required/tolerance/scale
- source section/hash、policy rule id/version
- compact geometry/numerical values及message key

排序固定为`layer precedence → TrackKey generation → absolute time → segment/index → code`；targets、failures、rows不依赖input/risk/dict顺序。Nonfinite拒绝；`-0.0`按DP-02规范化。Telemetry elapsed time、artifact path、queue id和wall timestamp不进入acceptance hash。

#### 三种projection

| Projection | 内容 | Authority/大小 |
|---|---|---|
| Full replay artifact | 完整parent chain、raw/prepared arrays、81/80 plans、all target predictions、all layer results/witnesses、certificate、receipt、persistence envelope | Offline replay authority；压缩后异步持久化，不设inline大小限制 |
| Inline PlannerTrace summary | acceptance/receipt/artifact hashes、profile/source/scope、status/aggregate、solve/hold identity、selected command或null、target counts、min clearance、first failures、timing摘要 | deterministic `<=8KiB`；critical path构造；有截断计数/完整artifact ref |
| GUI/API view | 仅消费inline typed projection与active/latest timeline；显示高信号字段和真实trajectory | 非authority；不得从旧trace或raw details推断 |

Inline超预算时按固定字段优先级裁剪secondary witnesses，只可裁投影，不可裁canonical record；保留`omitted_count/full_artifact_hash`。若mandatory摘要本身无法在8KiB内编码，拒绝并修schema，不静默截断identity/primary failures。

#### Typed event timeline

每tick只发布明确event type：

- `FRESH_ACCEPTED`
- `FRESH_REJECTED`
- `HOLD_VALIDATED`
- `HOLD_REPLAN_REQUIRED`
- `HOLD_REJECTED`
- `REPLAN_ACCEPTED`
- `REPLAN_REJECTED`

Event绑定attempt、parent receipt/attempt、`solver_executed`和active plan hash。Accepted/rejected fresh均进入latest attempt；只有accepted/validated进入active plan timeline。Hold不得增加solve id或复用`planner_solved`；rejected candidate的trajectory只能在diagnostic detail显式查看，默认地图不得画为active预测。

#### GUI/API requirements

Mid-MPC视图必须直接展示：

- `Mid-MPC`、`IPOPT`、expected/actual `COLAV_STRICT|MASS_PARITY`及production/diagnostic eligibility；
- fresh/hold/replan event、public status、L4 aggregate、primary failure与full failure count；
- `80 x 15.0s`、81 actual solver-derived state knots、当前active support和trajectory provenance；
- selected command或明确“无命令”，`fallback_used=false`；
- Ship0 per-target minimum clearance、COLREG role/locked side/action phase、trackability scope；
- quality warnings、objective/component diagnostics，但不把objective称安全分数；
- accepted/latest attempt分区、acceptance/receipt/artifact hash短标识；
- L4 `SHIP0_PLAN_ACCEPTANCE`与Evaluator `SHIP0_POST_RUN/GLOBAL_ALL_VESSELS`分源显示。

Trajectory/target prediction统一typed `north_m/east_m/absolute_time_s`字段，不保留server端另读`x/y`的双协议。GUI按真实81点/80 interval time标注，不生成SB-MPC 90s或旧trace fallback。Mid objective存在时正常显示；无candidate costs时不显示“暂无候选控制代价”作为错误暗示。

#### Persistence与claim

Canonical in-memory decision完成后才进入bounded async persistence。状态为`COMPLETE/INCOMPLETE/BACKPRESSURE`：

- 持久化失败不回写同周期ACCEPT/command。
- 但该run不能声称full replay evidence或新增capability tuple；inline/GUI必须显示evidence incomplete。
- 历史artifact immutable，不因policy升级覆盖；retention/delete留下tombstone/manifest evidence。
- Artifact读取只用于offline replay，不进入online L4 control path。

具体queue、compression、retention和shutdown由DP-16冻结。

#### 证据链

| 证据 | 推导 |
|---|---|
| [R58] Candidate 3已有L4 placeholder且L3 accepted命名易混淆 | 真实L4 certificate必须追加到parent chain并单独命名 |
| [R59][R69] 当前GUI回退旧solve，无法同时表达active/latest/hold provenance | typed events与双时间线，禁止UI推断 |
| [R63..R66][R70] 当前JSON hash非JCS且projection需stable ordering/frame/unit/time | versioned canonical record和统一witness schema |
| [R64][R67][R68] full artifact较大，sync I/O不应进入控制authority | canonical/hash在内存，full artifact bounded async |
| [R71][R72] capability需dependency hashes，projection mutation不可改裁决 | artifact/receipt hash绑定claim，UI只机械投影 |
| [R1][R2] Mid objective/trajectory实际存在但当前UI映射不完整 | 统一81/80 typed trajectory和objective diagnostics，移除旧SB-MPC/VO假设 |

#### 备选与弃用草案

| 方案 | 优点 | 弃用理由 |
|---|---|---|
| A canonical record + full/inline/GUI hash-linked projections（推荐） | 单一事实源、可replay、bounded在线payload、UI不漂移 | schema和projection测试量大 |
| B 继续扩展free-form `algorithm_details` dict | 改动小 | 字段/单位/大小/命名漂移，无法可靠hash/replay |
| C 把全部raw vectors塞进PlannerTrace/HTTP | 无需artifact | payload失控、阻塞UI/网络并泄漏authority职责 |
| D trace只保存artifact path，在线按需读取 | inline很小 | disk I/O进入控制/GUI路径，文件缺失即不可解释 |
| E GUI直接从raw solver fields重算acceptance | 灵活 | GUI成为第二checker并可能与L4分歧 |
| F acceptance hash包含elapsed/path/queue/wall time | 字段全覆盖 | 相同物理输入产生不同hash，破坏determinism |
| G 同步写盘成功后才允许command commit | 证据强一致 | 慢盘/失败改变控制时序，违反in-memory authority |
| H rejected attempt覆盖active plan trajectory | latest优先 | 用户会把不可执行candidate误认当前命令来源 |
| I 使用同一`PASS`标签混合L4与Evaluator | UI简洁 | 混淆预测计划接受、Ship0事后安全与global all-vessels结果 |
| J witness超8KiB时静默删除targets/failures | 保持大小 | 摘要可能隐藏hard failure；必须保留计数/hash及canonical全量 |

#### 风险、失效边界与验证

| 项 | 评估 |
|---|---|
| 实现风险 | **高**：跨core/Adapter/trace/server/JS/artifact/capability，需schema-first和mechanical projections |
| 性能风险 | **中**：canonical serialization/hash处于critical path；full serialization/compression移出关键路径 |
| 漂移风险 | **低至中**：单一typed source显著降低，但需golden schema/projection mutation tests |
| 失效边界 | GUI/inline非authority；persistence incomplete不回滚command但阻断replay/capability claim；artifact不用于online decision |
| 核心验证 | canonical deterministic replay；target/order/-0 mutation；parent tamper；full-inline-GUI hash一致；8KiB边界与omitted count；accepted/rejected/hold/replan timeline；无stale trajectory；solver_executed/solve id真实；81/80 trajectory；north/east target keys；objective显示；L4/Evaluator分源；sink failure不改decision但claim incomplete |

#### 技术分解状态

DP-15冻结canonical evidence与三projection contract；persistence queue/runtime DP-16、schema/policy version governance DP-17、artifact/8010/capability tests DP-18继续裁决。

### Step4-DP16 · total deadline、determinism与bounded persistence（final）

#### 初步推荐

采用“**20s Adapter total deadline + solver reserved cutoff + deterministic complete L4 + post-L4 timely-commit gate + bounded async artifact sink**”。所有mandatory层必须完整执行；预算不足或超时只能阻止commit，不能跳层、返回partial ACCEPT或改变阈值。

把两个不同结论分开：

- `semantic_acceptance`：pure L4对给定canonical request/policy/candidate的确定性结果与hash，不包含wall timing。
- `dispatch_attempt`：Adapter根据monotonic total deadline、freshness和原子commit结果决定本次能否下发；可拒绝一个语义上ACCEPT但到达过晚的candidate。

因此相同canonical bundle/policy始终产生相同L4 verdict/hash/witness；运行机器较慢只改变attempt outcome `TOTAL_DEADLINE_EXCEEDED`，不篡改L4安全事实。

#### Critical-path deadline

总deadline起点为Adapter接受本cycle validated PlannerInput/开始Assembly的monotonic timestamp，终点为atomic command commit完成：

`Assembly → Numerical Preparation → IPOPT → L4 canonical evaluation/hash → final freshness → atomic commit`

以下不在authority critical path：full artifact JSON/gzip/file I/O、GUI rendering、HTTP response formatting、Evaluator、network upload、retention cleanup。

| Gate | 规则 |
|---|---|
| total deadline | 当前contract保持20s；所有production attempts统一，不按scenario/target/seed调大 |
| solver cutoff | IPOPT可用时间=`total deadline - measured elapsed - reserved complete-L4/commit budget`；必须在调用前配置/传递 |
| L4 start gate | 剩余时间低于reserved budget时不启动production L4，attempt以deadline reject；不运行一半 |
| L4 completion gate | pure L4不可按时钟跳层；完整返回后Adapter检查总deadline |
| final freshness | commit前重核snapshot/context identity和age；过期即不commit |
| atomic commit | 必须在20s内完成；超时即使semantic ACCEPT也dispatch reject |

Reserved L4/commit budget是trusted runtime policy字段，生产启用前必须由DP-18固定环境的16-target full-L4 p99加安全裕量校准；当前只有geometry p95约4.89ms，不能据此拍一个完整L4常数。未校准时profile状态为`NOT_PRODUCTION_READY`，不能用0ms reservation放行。

Native solver `WALL_TIMEOUT_FEASIBLE`只有在reserved cutoff前产生同点candidate、完整L4通过、final freshness成立且atomic commit在20s内完成时，公共状态才可为`TIMEOUT_FEASIBLE`。IPOPT自身花满20s后再运行L4必然拒绝。

#### Complexity与complete evaluation

V1 bounds固定：`N=80`，solver selected `<=16`，execution-track safety总量受DP-11 policy hard cap。L4各几何/规则/trackability层为bounded `O(TN)`，canonical sorting/hashing为bounded `O(T log T + TN)`；禁止：

- 第二次NLP、plant closed-loop simulation、Evaluator调用；
- network/disk reads；
- 随剩余时间降低target scope、跳过static/COLREG/trackability/evidence；
- 先返回ACCEPT后异步补mandatory层；
- 超容量静默截断。

Unexpected exception、memory allocation failure或budget watchdog只可产生`L4_INTERNAL_ERROR/DEADLINE_EXCEEDED` attempt rejection；不得保留partial receipt/command。

#### Determinism contract

Pure L4不读取系统clock、随机数、环境变量、global cache、文件或network。`now`、absolute deadlines、policy、target ordering等均由request显式提供。Canonical result排除：

- elapsed/p50/p95、wall timestamp、thread id；
- artifact path、queue sequence、compression bytes；
- log message、本地locale、unordered dict iteration；
- cache hit/miss和GUI projection。

相同canonical request/policy重复执行必须得到byte-identical semantic result/hash。Targets/failures/witnesses使用DP-15稳定排序；float normalization使用DP-02 versioned规则。并行实现若未来引入，也必须先局部计算、稳定merge，禁止first-completed ordering。

Adapter `dispatch_attempt`另有独立hash/record，绑定semantic acceptance hash、monotonic deadline result和freshness facts；它可以随运行时变化，但不得反向改变semantic hash或冒充L4 verdict。

#### Bounded async artifact persistence

控制路径只构造canonical record/hash和<=8KiB inline summary；full artifact交给进程内bounded sink：

| 状态/动作 | 语义 |
|---|---|
| enqueue success | `PENDING`，command decision不变 |
| write/fsync/manifest success | `COMPLETE`，具备full replay/capability evidence资格 |
| serialization/compression/write failure | `INCOMPLETE`，保留inline hash/error；不回滚command，不得新增claim |
| queue满/byte budget满 | `BACKPRESSURE`，不得阻塞control path；本attempt claim incomplete |
| shutdown | bounded flush至policy timeout；剩余项目标记INCOMPLETE，不无限等待 |
| crash recovery | 启动时清理temp并把无complete manifest的items标incomplete；不伪造成功 |

Queue同时按item count与bytes bounded；容量、retention、flush timeout、artifact maximum bytes由DP-17 runtime policy冻结并经DP-18压力测试。策略为“拒绝新artifact入队并显式BACKPRESSURE”，不删除队列内较早未完成证据、不覆盖历史artifact、不阻塞控制线程。

写入采用temp→fsync→atomic rename→manifest complete；retention只删除已complete且超过policy的artifact，并保留hash/tombstone manifest。Artifact path/queue id不进入semantic/receipt hash。

#### Performance evidence与claim gate

当前证据只支持设计可行性：

- solver 5样本p95：0/1/16 targets约568.8/590.4/2159.2ms；16-target真实commit单次solver约1873ms、facade约2046ms。
- 独立16x80 swept geometry 200次p95约4.89ms。
- 未覆盖full L4、warm/hold、artifact、p99或adversarial cases。

因此Step4不把这些值写成production SLA。实施时promotion gate必须测：cold/warm fresh、hold、accepted/rejected、16 relevant targets、max witnesses、static applicable、canonical hashing、queue saturation；记录固定环境下p50/p95/p99/max与deterministic hash。`reserved_budget >= measured p99 + reviewed margin`后才允许`COLAV_STRICT` production profile启用。

#### 证据链

| 证据 | 推导 |
|---|---|
| [R73] solver当前远低于20s但样本少、非adversarial | 保留20s总门，不能把小样本当p99保证 |
| [R74] 16x80 continuous geometry约5ms p95但不含完整layers | 支持bounded O(TN)，不据此拍完整L4 reservation |
| [R61] timeout candidate仍需final freshness与总deadline | semantic feasible与timely dispatch分离 |
| [R64][R67][R68] full artifact/I/O体积和失败不应控制command | bounded async sink，persistence状态独立 |
| [R65][R66] timing/path会破坏canonical hash | telemetry与semantic result分离 |
| [R78] 当前缺warm/hold/full L4/p99/flakiness protocol | reserved budget必须经DP-18 production calibration gate |
| [R79] 464 passed baseline是回归起点，不是性能/时效证明 | 性能claim需独立batch，full suite仍需保持 |

#### 备选与弃用草案

| 方案 | 优点 | 弃用理由 |
|---|---|---|
| A total deadline + reserved solver cutoff + deterministic complete L4 + async sink（推荐） | 时效、安全完整性、replay和I/O分责一致 | 需先校准reservation才能production |
| B IPOPT独占20s，结束后再无限时运行L4 | solver机会最大 | candidate可能过总deadline/stale仍被下发 |
| C 给每layer设soft timeout，超时跳过并继续ACCEPT | 表面实时 | partial evidence被伪装为完整安全结论 |
| D L4内部读取clock并按剩余时间改变target/layer scope | 自适应快 | 相同bundle verdict不确定且可能漏hard failure |
| E 现在按4.89ms geometry p95直接设10ms完整L4预算 | reservation小 | 证据不含COLREG/trackability/hash/static，必然欠校准 |
| F 同步完整artifact写盘后才commit | 证据完整 | 慢盘改变控制deadline并可阻塞安全plan |
| G unbounded artifact queue | 不丢artifact | 内存无界、延迟积压和crash风险 |
| H queue满时阻塞control thread | 保证不丢 | I/O backpressure改变command时效 |
| I queue满时覆盖最旧未完成artifact | 保留最新 | 破坏既有evidence承诺且难以审计 |
| J wall timing进入acceptance hash | 完整记录 | 同一物理输入不可重放为同一hash |
| K 超总deadline仍提交semantic ACCEPT | 减少失败 | 忽视snapshot staleness与20s public contract |

#### 风险、失效边界与验证

| 项 | 评估 |
|---|---|
| 实现风险 | **高**：需solver cutoff、完整L4计时边界、semantic/dispatch双record及bounded crash-safe sink |
| 误拒风险 | **中**：reservation过大会压缩IPOPT，过小会导致post-L4 deadline reject；必须p99校准与版本化 |
| 实时风险 | **中**：L4不可被中途跳层；最坏情况可超出20s后才返回但绝不commit，production需用benchmark确保bounded completion |
| 确定性风险 | **低至中**：pure input/ordering可控；runtime dispatch结果天然受timing影响，必须与semantic verdict分名 |
| 失效边界 | 未校准reservation不production-ready；persistence incomplete阻断claim但不回滚command；不提供real-time certification |
| 核心验证 | phase timing边界；solver cutoff；semantic ACCEPT但deadline reject；timeout-feasible timely/late；freshness变化；mandatory layer不可跳；16-target/max witness p99；byte-identical replay；target order；wall telemetry hash exclusion；queue count/byte saturation；write/fsync/rename failure；shutdown/crash recovery；sink failure不改command但claim incomplete |

#### 技术分解状态

DP-16冻结critical-path、semantic/dispatch分离、determinism与persistence状态机；exact reservation/queue/retention policy DP-17、performance/8010/full regression DP-18继续裁决。

### Step4-DP17 · trusted policy、units、thresholds、tolerances与version governance（final）

#### 初步推荐

采用“**Registry发布typed immutable L4 policy，Session启动时resolve/freeze/hash，各owner只消费自己字段，candidate只报告facts**”。所有影响acceptance的阈值、单位、算法和runtime边界进入一个versioned policy manifest；但authority仍按领域拆分，不能让一个YAML字符串同时成为Lifecycle决定、L3约束、L4证明和Evaluator事后真值。

生产profile只允许`mid_mpc_l4_colav_strict_v1`。Policy schema与canonicalization version固定；任何canonical字段变化都会改变policy hash、使旧receipt/warm不兼容，并要求capability tuple重新验证。

#### Authority graph

| Authority | 拥有内容 | 不拥有 |
|---|---|---|
| Registry/published L4 policy | expected strict profile、ODD、50m门、checker numerical tolerances、runtime/persistence bounds、allowed capability identities、schema/version | candidate observed facts、Lifecycle实时role/side |
| Lifecycle policy/snapshot | encounter role/phase、locked side、required action、deadlines、release permission | L4 safety verdict、solver slack |
| Active plant/controller capability | ROT/accel/decel/speed/curvature/dwell/tracking tube及certificate | 通过场景PASS反推的静态能力 |
| Assembler | 将Lifecycle/ODD/capability编译成actual L3 problem/preparation facts | 修改L4门槛、自证production acceptance |
| L4 | 对trusted expected与candidate actual执行本设计checks | 改directive、轨迹、threshold或fallback |
| Evaluator | 独立post-run Ship0/global gates | online L4 authority |

Session把resolved expected policy/hash同时传给Lifecycle、Assembler、L4与trace，确保它们引用同一版本；各模块只读取有权字段。Candidate中的`configured_hull_clearance_m`等仅为actual evidence，不覆盖expected requirement。

#### Canonical technical conventions

| 类别 | V1规约 |
|---|---|
| world frame | local ENU：north/east in m；所有origin/chart/route/prediction带frame id/hash |
| angles | rad；COG/heading 0=north、clockwise-positive；比较前ordinary unwrap |
| speed/acceleration | m/s、m/s2；ROT rad/s |
| time | simulation absolute seconds + monotonic runtime deadline；81 knots at `t0+k*15s`，80 commands on half-open intervals |
| distances | physical hull clearance m；solver CPA row明确m2；不得互换 |
| target identity | `TrackKey(stable_id,generation)`；裸ID无authority |
| invalid values | NaN/Inf一律invalid；canonical float归一化`-0.0`，不虚称RFC8785/JCS |

Frame/unit/schema不匹配是integrity failure，不能在checker中“猜测degree/rad、NED/ENU或heading/COG”自动修复。

#### V1 fixed acceptance constants

| 字段 | V1值/语义 | 依据与边界 |
|---|---|---|
| horizon | `N=80`, `dt=15.0s`，81 states/80 commands | 已确认Mid production contract；非SB-MPC 90s |
| required hull clearance | `50.0m`，one-sided hard：`clearance_lb >= 50.0` | ODD/现有G3 hard gate；数值epsilon不得下调物理门 |
| preferred clearance | `150.0m`，objective/quality diagnostic only | 不是acceptance hard safety门 |
| profile | expected+actual `COLAV_STRICT`；MASS_PARITY diagnostic-only | DP-06 |
| production slack | CPA/direction slack bounds exact `[0,0]`；observed value只允许数值bound tolerance | strict semantics，不把soft slack称hard |
| relevant target capacity | `<=16` safety/COLREG relevant TrackKeys；超出fail-closed | frozen L3 graph capability；不截断 |
| total deadline | `20.0s` Assembly到atomic commit | 当前public contract；所有场景一致 |
| inline summary | `<=8192 bytes` canonical encoded | DP-15 |
| uncertainty ODD | V1 production仅God zero-uncertainty；非God须新policy提供经校准envelope | 当前朴素CV传播不可用 |
| static claim | chart-backed Playground profile mandatory；无trusted ENC context则UNKNOWN reject | 不由`requires_enc=False`静默降级 |
| quality | advisory-only，无独立hard threshold | DP-10 |
| dual warm | disabled；`dual_seed_used=false` | DP-14 |

标准Playground OT的Lifecycle policy固定“无约束、两侧等价时选择starboard maneuver/目标留在本船port侧”；镜像/受限场景仍消费其locked side，不在L4按scenario ID硬编码。

#### Numerical tolerance table

Tolerance只用于浮点复核，不改变physical safety/action/plant requirement。V1采用quantity-specific `abs_tol + rel_tol*scale`，scale记录在witness：

| Quantity/row family | `abs_tol` | `rel_tol` | 备注 |
|---|---:|---:|---|
| identity/shape/layout/index/options semantic equality | `0` | `0` | bit/schema语义零容忍 |
| heading/ROT/min-alteration rows, rad | `1e-6` | `1e-10` | 约0.000057deg absolute |
| speed/accel/decel rows, SI | `1e-6` | `1e-10` | 不与角度共享配置键 |
| position/direction rows, m | `1e-4` | `1e-10` | 0.1mm，仅数值复核 |
| squared CPA rows, m2 | `1e-4` | `1e-10` | scale=`max(1,abs(g),abs(bound),R_required^2)`；不得解释为m margin |
| fixed-zero slack variables, native historical units | `1e-7` | `0` | 覆盖已见约`-1e-8`数值噪声；bound语义仍exact zero |
| objective/component consistency | `1e-8` | `1e-10` | 只比较同candidate同graph |
| canonical physical geometry | outward-conservative epsilon由实现数值误差界给出；**不允许**`clearance >= 50-epsilon` | — | epsilon从lower bound中扣除，再与50m比较 |

这些是V1初始strict candidates，不是由五个PASS场景拟合。Production启用前，DP-18必须用independent negative/boundary corpus证明：低于bound的缺陷不会被tol放行；现有真实strict accepted candidates均在表内；若失败，只能通过policy version回炉调整，禁止测试内局部放宽。Ipopt现有统一`1e-3`可继续作为L3内部candidate筛选，但不能冒充L4 quantity-specific acceptance。

#### Delegated dynamic thresholds

以下不得在L4 policy写死一个通用常数：

| 字段 | 来源/生产门 |
|---|---|
| early/substantial deadband、start/achievement deadline | Lifecycle obligation + versioned Lifecycle policy；缺失即UNKNOWN |
| stand-on course/speed envelope、Rule17 transition | Lifecycle snapshot/policy |
| ROT/accel/decel/speed/curvature/dwell | 当前active plant/controller capability；静态fallback禁止 |
| own tracking tube、target uncertainty envelope | 经独立校准且绑定tracker/plant/version；V1 God可为0 |
| hold state deviation/validity | active tracking tube + accepted receipt support；缺证据replan/reject |
| full-L4 reservation | 固定环境max-target p99 + reviewed safety margin |

这样避免用当前HO/CS/OT PASS反推`5deg/30deg/50m之外的行为常数`，也避免一个静态3deg/s覆盖所有active plants。

#### Runtime/persistence initial operational bounds

为保证实现有界，V1先给保守operational defaults；它们不影响semantic acceptance，仅影响persistence/production readiness：

| 字段 | V1 default | 行为 |
|---|---:|---|
| artifact max uncompressed bytes | `16 MiB` | 超出标INCOMPLETE，不阻塞commit |
| queue item capacity | `32` | 满则BACKPRESSURE |
| queue byte capacity | `64 MiB` | item/byte任一满即拒绝新enqueue |
| shutdown flush timeout | `2.0s` | 超时剩余items标INCOMPLETE |
| retained complete artifacts | `256 per algorithm/profile` | 只删complete，保留tombstone manifest |
| full-L4 reservation | `UNSET`直到DP-18 p99 calibration | UNSET即`NOT_PRODUCTION_READY` |

这些值可经运行证据调整，但任一变化进入policy hash。不能用增大queue掩盖长期sink故障；持续BACKPRESSURE必须告警且阻断capability evidence累积。

#### Version与claim governance

- `schema_version`：字段/编码兼容性；breaking change升major。
- `policy_version`：任何accept/reject语义、threshold/tolerance/ODD/runtime reservation变化升version并改hash。
- `formulation/layout/profile`：由L3独立version；row/索引/方程变化不得只改L4 policy。
- Display wording、artifact path等noncanonical变化不改变semantic policy；但GUI schema可独立version。
- Policy发布需code review、independent boundary tests、signed/committed manifest；Session启动冻结，运行中不hot reload。
- Policy hash变化：旧receipt/warm失效；历史artifacts保留；G3/capability tuple不继承，须重跑exact dependency tuple。

Capability tuple至少绑定algorithm/formulation/profile/L4 policy/plant-controller/tracker/scenario/seed/evaluator/commit/artifact hashes。禁止把God固定seed结果宣传为non-God、任意plant、global all-vessel或MASS-L3 system acceptance。

#### 证据链

| 证据 | 推导 |
|---|---|
| [R20] frozen rows混合rad/m/s/m/m2且direction slack历史量纲混用 | quantity-specific table，strict slack固定0 |
| [R23][R33] 50/150及Assembler compensation多处复制 | 50m physical hard、150m advisory，expected authority集中且actual只作证据 |
| [R24..R26] 非God covariance envelope有条件且朴素1200s传播失控 | V1 production限定God，扩展需校准profile |
| [R34][R38][R39] COLREG无通用early/substantial数值，Lifecycle已有动态action authority | deadline/action门委托Lifecycle，不在L4拍常数 |
| [R43..R47] active plant与静态Kinematic envelope/COG-body语义可能错位 | trackability门来自live capability，缺失UNKNOWN |
| [R63][R71] policy dependency变化需使receipt/claim失效 | Session freeze/hash及version governance |
| [R73][R74][R78] runtime小样本不足以确定full L4 p99 | reservation保持UNSET直到DP-18校准 |

#### 备选与弃用草案

| 方案 | 优点 | 弃用理由 |
|---|---|---|
| A typed immutable policy + owner graph + fixed/delegated thresholds（推荐） | 单一可审计manifest但不混淆领域authority；receipt/claim可失效 | schema/governance工作量增加 |
| B 继续让`mid_mpc_ipopt.yaml`同时定义Lifecycle/L3/L4/Evaluator | 文件少 | producer可自降门且多authority静默漂移 |
| C candidate自报threshold，L4验证其自报值 | 接口简单 | candidate可把50m改30m后自证通过 |
| D 所有量统一`1e-3` tolerance | 配置少 | rad/m/s/m/m2无共同尺度，会同时过松/过严 |
| E 物理50m门使用`50m - numeric epsilon`放行 | 避免边界抖动 | 实质降低hard safety requirement |
| F 把150m preferred clearance升级hard | 更保守 | 改变现有ODD语义并可能无共同可行解；当前只支持objective偏好 |
| G 按scenario id/seed/target id设置不同阈值 | 容易让测试PASS | 直接场景作弊且无法形成通用capability claim |
| H 用现有五个PASS场景拟合action/quality阈值 | 快速校准 | 数据泄漏，无法证明边界或泛化 |
| I 运行中hot reload acceptance policy | 调参方便 | 同session receipt/verdict authority变化且不可重放 |
| J policy变化后继续复用旧receipt/G3 claim | 降低重测成本 | dependency已变，证据不再证明新contract |
| K 未校准full-L4 reservation时设0并production启用 | 立即可用 | IPOPT可能耗尽20s并使L4/commit过时 |

#### 风险、失效边界与验证

| 项 | 评估 |
|---|---|
| 实现风险 | **高**：需typed manifest、owner-specific views、hash/version migration及Registry/Session接线 |
| 误拒风险 | **中高**：初始numerical tolerances、God-only ODD和missing live capability较严格；通过independent boundary corpus与versioned review调整 |
| 误接受风险 | **低至中**：主要来自错误trusted policy或double-count/漏计margin；通过authority/hash、metamorphic与mutation tests控制 |
| 失效边界 | V1仅God + bound active plant/controller + exact policy tuple；reservation UNSET前不production-ready；不支持hot reload或场景阈值 |
| 核心验证 | frame/unit/degree/NED negative；50m±boundary且不降门；150m advisory；mixed-unit tolerance每类两侧边界；strict slack约-1e-8；MASS parity隔离；non-God reject；live/static plant mismatch；scenario/seed/target-label invariance；policy hash/receipt/capability invalidation；queue bounds；reservation UNSET gate；signed manifest/session freeze |

#### 技术分解状态

DP-17冻结policy authority、canonical units、V1 known constants、numerical tolerance candidates、dynamic threshold delegation、operational bounds与version governance；full-L4 reservation的数值是明确production calibration gate，由DP-18完成后写入新policy hash，不以UNKNOWN值静默放行。

### Step4-DP18 · validation matrix、promotion gates与claim boundary（final）

#### 初步推荐

采用“**六层验证门，全部通过后才启用COLAV_STRICT production与更新G3 tuple**”。顺序固定为contract→independent layer oracles→真实L3/L4→closed-loop Playground→8010/UI→performance/full regression/claim。测试遵循TDD vertical slices；每个mandatory layer先有能稳定拒绝缺陷的RED，再实现GREEN，不能只给现有PASS场景加`accepted=true`。

任何一层失败不通过promotion；不得降50m、改scenario、切fallback、用mock solver替代真实IPOPT或把target-target固有碰撞隐藏掉。

#### V1 · Pure contract与determinism gate

| Scope | 必测 |
|---|---|
| request/result types | immutable/frozen、copy/read-only arrays、81/80 shapes、ENU/SI/rad、absolute time、TrackKey generations |
| identity/hash | complete parent chain、canonical ordering、`-0.0` normalization、NaN/Inf reject、tamper/cross-splice/profile mismatch |
| layer truth table | PASS/FAIL/WARN/UNKNOWN/N/A/NOT_EVALUATED、integrity short-circuit、mandatory AND、quality advisory、parity diagnostic-only |
| aggregation | simultaneous failures、stable primary precedence、per-target AND、primary display-only、Ship0/global scope |
| metamorphic | global ENU translation、target order、absolute-time shift、scenario/seed/display label change；物理verdict保持，hash按contract稳定/变化 |
| replay | 同一canonical request/policy至少100次byte-identical semantic result/hash/witness |

Production helpers不得作为expected-value oracle。Golden bytes只用于schema/canonicalization；业务expected由独立公式/hand-computed fixtures产生。

#### V2 · Independent layer-oracle gate

每个layer使用与production不同实现路径：

| Layer | Independent oracle/negative-boundary set |
|---|---|
| numerical | NumPy/hand formula重算x/g bounds、row units、strict zero slacks、objective sum；每类tolerance内/外、callback same/wrong candidate、terminal dual/KKT availability |
| safety | 独立relative-segment analytic或dense high-resolution cross-check；first/last interval、node-safe segment-collision、footprint、50m±boundary、unselected target、static safe/hazard/coverage missing、uncertainty single-count |
| COLREG | hand-constructed HO port-to-port/wrong-return、CS astern/ahead、OT standard-starboard/mirror-port/past-clear责任、stand-on/Rule17 MAY/MUST；不调用Lifecycle classifier或Evaluator FSM |
| action timing | onset/achievement deadline两侧、first interval before knot1、cross-solve cumulative action、pulse/reversal、wrong-side monotonic recovery、predicted-vs-actual release |
| trackability | independent COG/SOG from`u/v/psi`、piecewise-constant control sampling、ROT/accel/decel/capability edge、active/static plant mismatch、missing/stale certificate |
| quality | safe straight route-only不判坏、churn WARN仍ACCEPT、context change N/A、polyline progress/recovery、objective不可比 |
| evidence | full-inline-GUI mechanical projection、8KiB boundary、typed event timeline、L4/Evaluator source separation、sink incomplete semantics |

Mutation requirement：每mandatory layer至少一个单缺陷；再注入numerical+safety+COLREG并发缺陷，验证全部failure保留且primary稳定。Boundary测试不得通过调整threshold使当前candidate恰好PASS。

#### V3 · Real Candidate 3 → IPOPT → L4 integration gate

必须使用真实CasADi 3.7.2/IPOPT、80x15s、81 states、COLAV_STRICT、God、固定seed、no fallback：

- route-only cold及accepted-plan primal warm；warm/cold均重新完整L4，记录但不要求相同局部解。
- desired local、callback feasible-nonoptimal、wall-timeout feasible及时/过晚、infeasible、invalid-number/证据错配路径。
- 0/1/16 relevant targets；selected/unselected reconciliation；17th relevant target typed capacity/core failure。
- fresh ACCEPT/REJECT、hold VALIDATED/REPLAN/REJECT、一次same-algorithm replan、receipt/reset/tamper/warm eligibility。
- 8条冻结MASS C++ parity records expected不改；完整L4 diagnostic可运行，但overall永远DIAGNOSTIC_ONLY、无receipt。
- Parent chain、actual strict bounds/options、quantity tolerance、acceptance certificate、commit receipt和artifact round-trip逐段验证。

验收：所有selected commands来自同一已接受candidate；任何rejected/diagnostic candidate无command、无active trajectory、无warm authority。

#### V4 · Closed-loop Playground gate

公共`P1RunHarness`/真实Session运行以下固定矩阵：

| Scenario | 必须证明 |
|---|---|
| route-only | 真实IPOPT近直线可ACCEPT；route progress/recovery、81/80 provenance正确 |
| HO | Ship0 swept hull clearance≥50m、early substantial starboard、port-to-port、无回切 |
| CS give-way | ≥50m、pass astern、不cross ahead、past-clear后恢复 |
| CS stand-on | ≥50m、Rule17 transition前course/speed envelope；必要时MAY/MUST动作正确 |
| OT standard | Lifecycle锁定starboard maneuver、目标留在本船port侧、责任到past-clear、恢复 |
| OT mirror/restricted | 按Lifecycle locked port corridor通过，不被universal-starboard误拒 |
| overtaken | stand-on/Rule17语义、≥50m及恢复 |
| explicit Rule17 | MAY/MUST deadline、action与safety同时满足；无迟行动远期补救 |
| multiship | Ship0对每个target≥50m、全部per-target obligations、多接触selection/reconciliation、恢复 |
| static ENC positive/negative | 安全航线通过；grounding/hazard或missing coverage被L4拒绝且无command |

每个accepted run同时要求：raw G3 gate、L4 production ACCEPT/receipt、Evaluator Ship0 hard gate、真实IPOPT statuses、无fallback、active Viknes+FLSC capability identity、无collision/Ship0 grounding、最终route/speed recovery。Multiship target-target scripted collisions保留`GLOBAL_ALL_VESSELS`事件；不影响Ship0 L4，但禁止声称all-vessel safe。

不得只断言最终DCPA；逐solve/hold检查directive、acceptance、command provenance与timeline。至少一个closed-loop rejection场景验证Session fail-stop和旧command隔离。

#### V5 · Real 8010 HTTP/GUI gate

最终合并后在主checkout验证真实`localhost:8010`：

1. 记录listener PID、cwd、commit、asset checksum；确认不是旧worktree/service。
2. 分别启动accepted、rejected、hold→replan session；HTTP事件证明`mid_mpc_ipopt/IPOPT/COLAV_STRICT/L4`真实执行。
3. Accepted事件：command非空、fallback false、acceptance/receipt/artifact hashes完整。
4. Rejected事件：command null、fallback false、Session FAILED、previous trajectory不再active。
5. GUI显示Mid-MPC、Fan-MPC命名，真实80x15s/81点、fresh/hold/replan、profile/eligibility、Ship0/global分源、objective/quality，不显示SB-MPC 90s或VO候选代价文案。
6. Target prediction使用north/east typed schema并可见；active/latest timeline一致。
7. Artifact digest可离线重放出相同semantic result；persistence状态COMPLETE后才能作claim。
8. Desktop及mobile Playwright截图检查文本不溢出、轨迹非空、按钮/诊断无重叠。

Pre-merge开发可用8011/8012，但最终promotion证据必须来自8010；不得停止或复用错误listener后宣称通过。

#### V6 · Performance、regression与capability gate

##### Performance protocol

固定commit、macOS/CPU、Python、CasADi、Ipopt、policy、plant/controller、tracker、target set、cold/warm与deadline；记录warmup、sample count和原始样本。最低批次：

- Pure complete L4：20 warmups + 500 measured，覆盖max-target/max-witness accepted与rejected。
- Hold validation：20 warmups + 500 measured，覆盖valid/stale/replan-required。
- Full fresh chain：10 warmups + 100 measured，分别cold/warm、0/1/16 targets、accepted/rejected/timeout-feasible。
- Persistence：1000 enqueue/write及queue item/byte saturation、slow/failing sink、shutdown/crash recovery。

报告p50/p95/p99/max、hash determinism、RSS/queue bytes和flakiness。`full_l4_commit_reservation`不得小于固定环境max-target full-L4 measured p99加reviewed margin，并必须确保100个full fresh样本全部在20s内完成或正确reject、无late commit。若环境变化，reservation和claim重校准。

##### Regression gate

- Candidate 3权威baseline：`464 passed, 2 skipped, 1 warning`。
- Focused：parity/core/Assembler/Lifecycle/L4/Adapter/scenarios/artifact/API/GUI/capability全部green。
- Full：`uv run pytest -q`完成，无新fail/skip；8条parity expected、其他算法能力/registry不退化。
- Scoped Ruff/format/type/static checks、`git diff --check`、clean generated artifacts。
- 至少一次重复full critical matrix，排除偶发seed/timing PASS。

##### Capability promotion

只有以下全部成立才从`NOT_PRODUCTION_READY`切换并更新G3：

- DP-17 tolerance boundary corpus通过；full-L4 reservation已写入新policy hash。
- Exact scenario tuple的V4 artifacts全部`COMPLETE`。
- V5 8010 accepted/rejected证据完成。
- V6 performance与full regression通过。
- Capability metadata绑定algorithm/formulation/profile/L4 policy/plant-controller/tracker/scenario/seed/evaluator/commit/artifact hashes。

每个tuple单独列出，不因一个HO或OT扩展到其他scenario/seed/plant/tracker。Policy/plant/tracker/evaluator/scenario版本变化立即失效相关tuple并重测。

#### Claim boundary

通过上述门只支持：

> Colav-Simulator指定commit与`COLAV_STRICT` policy下，God tracker、指定Viknes+FLSC capability、固定seed和已列Playground scenarios中，真实IPOPT Mid-MPC候选在执行前通过L4 Ship0计划验收，并在Evaluator中满足对应Ship0闭环门。

明确不支持：global all-vessel safety、任意target motion/uncertainty、任意plant/controller、global optimum、法规/实船认证、MASS-L3 ROS2/GNC/M7/SIL acceptance。MASS parity只支持冻结数值迁移一致性。

#### 证据链

| 证据 | 推导 |
|---|---|
| [R75] 已有66个Mid test functions和真实场景seams，但无L4 verdict/receipt | 可复用公共seam，需补L4负例与receipt assertions |
| [R76] 当前缺layer mutation、多失败、hold/replay/metamorphic与8010 rejection | 六层矩阵必须覆盖这些缺口 |
| [R77] 8010已有81点历史证据但无真实L4 event | promotion前重做listener/cwd→event→artifact→GUI链 |
| [R73][R74][R78] 当前性能样本少且不含full L4/p99 | 规定固定环境、多case、p99/max与reservation calibration |
| [R79][R80] Candidate 3 full baseline及18-file blast radius已明确 | focused外必须完成全仓回归且冻结parity expected |
| [R4][R8] Ship0与target-target global事实可分离 | multiship保留global events但claim只限Ship0 |
| [R71] capability依赖版本/hash集合 | exact tuple promotion与变更失效，不做宽泛G3外推 |

#### 备选与弃用草案

| 方案 | 优点 | 弃用理由 |
|---|---|---|
| A 六层promotion gates + independent oracles + exact claims（推荐） | 从pure defect rejection到真实8010闭环完整，claim可审计 | 测试与运行时间较大 |
| B 只给现有HO/CS/OT测试加`accepted=true` | 改动少 | 不能证明checker能拒绝缺陷、hold/hash/UI/performance正确 |
| C 全部layer测试复用production helper计算expected | 易维护 | production与oracle共享同一bug，自证通过 |
| D 只跑mock solver/unit tests | 快 | 不证明CasADi/IPOPT候选、prepared evidence和deadline链 |
| E 只跑full pytest | 一条命令 | 回归通过不证明新L4负例、性能或8010真实执行 |
| F HTTP 200或页面可打开即算8010通过 | 快 | 不证明正确listener、solver、L4、command、artifact或GUI数据 |
| G 先升G3再补artifact/performance | 提前发布 | claim没有完整证据且reservation仍UNSET |
| H 按现有PASS结果修改threshold直到全绿 | 容易通过 | 数据泄漏/场景作弊，破坏50m和independent acceptance |
| I target-target collision存在则multiship整体失败 | global严格 | 超出Ship0 control authority并与已确认scope冲突 |
| J 一次warm-cache performance run作为p99 | 时间短 | 无统计意义，掩盖cold/hold/rejected/worst-case |
| K 用Colav结果宣称MASS-L3 system acceptance | 范围扩大 | 未验证ROS2/GNC/M7/SIL及真实部署链 |

#### 风险、失效边界与验证

| 项 | 评估 |
|---|---|
| 实施成本 | **高**：真实IPOPT closed-loop、8010、性能与full regression预计为主要耗时 |
| 假阳性风险 | **低**：independent oracles、mutation、真实solver和exact tuple共同约束 |
| 假阴性风险 | **中**：initial strict tolerance/capability可能暴露真实缺口；不得通过场景调参解决，需回炉affected DP |
| Flakiness风险 | **中**：IPOPT/timing/GUI；固定环境/seed、重复critical matrix及原始artifact控制 |
| 失效边界 | 任一promotion gate未通过保持NOT_PRODUCTION_READY；只声明exact Ship0 tuple，不外推MASS/global/real-world |
| 验证完成定义 | V1..V6全部green；reservation非UNSET；8010 accepted+rejected可重放；full artifact COMPLETE；full suite完成；capability tuple/hash更新且旧claim失效测试通过 |

#### 技术分解状态

DP-18冻结验证/promotion/claim边界。DP-01..18均已完成Step4推荐；用户确认DP-18后进行TD-01完整性审计与Step4步骤间门检查，不自动进入Step5。

## 5. Step4完整性审计（已确认）

### 机械检查

| 检查 | 结果 |
|---|---|
| DP注册表 | 18/18均为`Step4推荐final` |
| Step4 sections | 18/18均为`final`；审计修正DP-01..03残留DRAFT标题 |
| VR | VR-01..18连续、唯一、均有用户逐项确认 |
| ALT | ALT-01..140连续、唯一；每个Step4 section均含备选/弃用理由 |
| Evidence | 18/18均有具名R证据链 |
| Risk/failure/verification | 18/18均完整 |
| Draft残留 | 0 |
| `git diff --check` | PASS |

### TD-01技术分解就绪度

| 子模块 | DP | 状态 |
|---|---|---|
| Module seam/depth | DP-01 | 已裁决 |
| immutable identity/input | DP-02 | 已裁决 |
| layered verdict | DP-03 | 已裁决 |
| numerical/KKT | DP-04 | 已裁决 |
| swept/static safety | DP-05 | 已裁决 |
| strict/parity isolation | DP-06 | 已裁决 |
| COLREG authority/predicates | DP-07 | 已裁决 |
| timing/past-clear/recovery | DP-08 | 已裁决 |
| active-plant trackability | DP-09 | 已裁决 |
| quality/churn/recovery metrics | DP-10 | 已裁决 |
| multi-target aggregate | DP-11 | 已裁决 |
| fresh/hold/replan | DP-12 | 已裁决 |
| rejection/atomic commit | DP-13 | 已裁决 |
| receipt/warm handoff | DP-14 | 已裁决 |
| evidence/artifact/GUI | DP-15 | 已裁决 |
| runtime/determinism/persistence | DP-16 | 已裁决 |
| policy/units/thresholds | DP-17 | 已裁决 |
| validation/promotion/claims | DP-18 | 已裁决 |

技术分解缺口为0，可进入Step5。以下不是未裁决设计盲区，而是已明确的implementation/promotion gates：Candidate 2/3补齐action deadlines/reachability projection；提供真实Viknes+FLSC active-prefix capability；DP-18校准full-L4 reservation并写入新policy hash。任一未完成时保持`NOT_PRODUCTION_READY`，不阻塞Step5方案对比，但阻塞production promotion。

### Step4 gate结论

每个DP均有推荐、证据、弃用、风险、失效边界与验证；TD-01无遗漏；已知UNKNOWN均转化为fail-closed production gate而非隐式默认。Step4步骤间门满足。等待用户确认本审计后，才进入Step5 DESIGN-IT-TWICE。

## 6. Step5 DESIGN-IT-TWICE（对比对象待确认）

### 6.1 对比对象提案

| Card | 对比对象 | 覆盖DP | 纳入原因 | 拟比较的完整方案 |
|---|---|---|---|---|
| DC-01 | TD-01整体Module topology与authority | DP-01..18整体 | 技术分解整体方案必须至少二次设计；防止局部正确但端到端authority循环 | A独立pure L4；B stateful Adapter acceptance controller；C分布式solver/facade/Evaluator gates |
| DC-02 | Numerical + physical safety + profile kernel | DP-04..06 | KKT、original primal、continuous hull/static safety、strict/parity共同决定误接/误拒 | A primal-hard/KKT-advisory+swept conservative；B KKT-hard+exact geometry；C solver-native status/constraints+post-run gate |
| DC-03 | COLREG behavior + active-plant execution + multi-target | DP-07..11 | 当前OT方向、intent flicker、Rule17、trackability和多目标是业务成败核心 | A Lifecycle-locked directives+prefix capability；B instantaneous reclassification+full-horizon hard quality；C safety-only planner+post-run COLREG |
| DC-04 | Fresh/hold/replan + receipt/warm transaction | DP-12..14 | 最易发生旧SUCCESS泄漏、stale command、rollback和warm authority污染 | A prefix revalidate+atomic receipt；B every-tick fresh solve；C stateful last-plan continuation/fallback |
| DC-05 | Evidence + runtime + policy governance | DP-15..17 | 决定可重放、20s时效、GUI真实性、persistence及claim失效 | A canonical semantic record+async sink；B synchronous event-sourced durable commit；C lightweight trace/no full artifact |

每张卡都会完整覆盖七维：来源、工程验证、技术分解、失效边界、实现风险、可测性、推荐度；逐张展示、逐张等用户裁决，不批量final。

### 6.2 低风险直接采纳候选

| DP | Step4方案 | 提议直接采纳理由 | 若不同意 |
|---|---|---|---|
| DP-18 | V1..V6六级promotion gates与exact Ship0 claim | 这是验证/claim gate，不改变在线算法；替代方案均明显缺少独立oracle、真实IPOPT、8010或性能证据；证据方向一致、失效边界明确 | 增加DC-06，对比“六级门 / risk-based最小门 / shadow rollout后延迟promotion”三套完整发布策略 |

用户已判定DP-18为低风险并直接采纳Step4结论，登记VR-19，不增加DC-06。其他DP均被DC-01整体卡或DC-02..05专项卡再次覆盖。

### 6.3 DC-01 · TD-01整体Module topology与authority（final）

#### 完整方案定义

| 子模块 | 方案A：Independent Pure L4 | 方案B：Stateful Adapter Acceptance Controller | 方案C：Distributed Layer Gates |
|---|---|---|---|
| topology | L3 candidate后、Adapter commit前单一pure `evaluate(request)->result` | 把全部acceptance checks、hold、receipt、warm、persistence并入一个stateful Mid Adapter/controller | numerical在solver、safety/COLREG在facade、trackability/hold在Adapter、post-run truth在Evaluator；Adapter聚合booleans |
| input/identity | self-contained immutable candidate/authority/execution/prior bundle与parent hashes | controller直接读取自身mutable solution、Lifecycle、Session与latest trace | 各层消费自己的局部对象/free-form details；用algorithm/status/target IDs关联 |
| verdict | typed mandatory layers、全failure list、stable aggregate | controller内部状态机产生public status与单一active decision，同时保存详细原因 | 每层各自PASS/FAIL/exception；Adapter按顺序/优先级合并 |
| numerical/safety/profile | original primal/KKT diagnostic、all-target swept/static safety、strict/parity隔离均在pure Module编排 | controller依次调用solver result checks及几何checks；可访问内部candidate/state | solver负责status/bounds/profile；facade做CPA/COLREG；Evaluator验证实际轨迹 |
| COLREG/trackability/quality | 消费immutable Lifecycle/active capability；独立predicates，quality advisory | controller持有episode/commit/quality历史并直接决定继续/恢复 | facade/算法私有COLREG；Adapter做shape/continuity；Evaluator做最终规则/clearance |
| temporal/transaction | Adapter仅编排fresh/full、hold/prefix、one-replan、atomic commit；L4自身无状态 | controller同时拥有schedule、last plan、receipt、warm、retry、commit和reset | 每层独立缓存last result；Adapter尝试复用旧plan并聚合当前状态 |
| evidence/runtime/policy | canonical semantic record；dispatch record分离；async sink；Registry typed policy | controller序列化完整内部状态和events；sync/async persistence由controller决定 | 各层写details/log/artifact；GUI/server从多个来源拼装；YAML分别配置 |
| validation/claim | pure oracle+real L3/L4+closed loop+8010+exact tuple | 以controller状态机integration/closed-loop为主，补部分unit tests | 主要靠full integration/Evaluator/G3结果；各层局部tests |

#### 七维决策卡

| 维度 | 方案A：Independent Pure L4 | 方案B：Stateful Adapter Controller | 方案C：Distributed Gates |
|---|---|---|---|
| 来源 | [R5..R13][R15..R81]；Candidate 2/3 immutable seams、predictive safety filter/independent evidence、项目全部失败实验共同支持 | [R2][R3][R52..R59]；当前CustomMPCAdapter已有schedule/hold/trace/last solution，可扩展 | [R1..R4][R27][R55][R59]；当前系统事实上接近此分布式形态 |
| 工程验证 | **项目设计/局部seam已验证，完整L4尚未实现**；pure core/Assembler/parity/closed-loop提供强落地基础，非外部production认证 | **当前项目部分存在**；但100m hold偏差仍SUCCESS、异常/trace路径不一，已有反证 | **当前项目部分运行并取得G3**；但solver CPA、facade policy、Adapter、Evaluator之间存在已验证语义缺口，不能证明online acceptance |
| 技术分解 | input✓ verdict✓ numerical✓ swept/static✓ profile✓ COLREG✓ timing✓ trackability✓ quality✓ multi-target✓ hold✓ fail-stop✓ receipt/warm✓ evidence✓ runtime✓ policy✓ validation✓ | 全子模块可放入controller✓；但Module depth✗、deterministic replay需序列化全部隐式state△、authority separation△ | 局部功能均可放置△；无单一identity/aggregate/receipt authority✗，cross-layer transaction/evidence completeness✗ |
| 失效边界 | 缺deadline、active capability、uncertainty或reservation即fail-closed/NOT_PRODUCTION_READY；实现schema较大但边界显式。关联SC-06..82 | reset/exception/concurrency漏清状态时stale plan/warm泄漏；Adapter变更blast radius大；replay依赖完整状态快照。关联SC-39..57 | checks漂移/顺序变化导致last-error-wins；selected-only/self-evaluation、旧trace/GUI回退无法排除。关联SC-06/07/09/10/35..57 |
| 实现风险 | **高但局部化**：新增deep module/contracts，Adapter只改事务seam；不动frozen equations | **中高且长期高**：初始文件少，但controller成为浅巨类，测试状态组合爆炸，未来owner继续耦合 | **初始低、系统风险高**：最少重构，但已知缺口跨5处修复，无法给完整acceptance claim |
| 可测性 | **最高**：pure deterministic replay、独立layer mutation、same bundle byte-identical；再过真实IPOPT/hold/8010 | **中**：可测state machine，但必须构造历史/clock/cache/exception组合；单次函数replay困难 | **低**：需大量integration/closed-loop才能发现跨层错误；production helper易成为self-oracle |
| 推荐度 | **★★★★★** | **★★☆☆☆** | **★☆☆☆☆** |

#### 初步裁决建议

推荐**方案A Independent Pure L4**。它是唯一同时覆盖TD-01全部子模块、保持Lifecycle/Assembler/Adapter/Evaluator authority边界、支持deterministic replay并把fail-closed条件显式化的完整方案。[R5][R6][R52..R72]

方案B虽能实现全部检查，但把调度、裁决、receipt、warm、persistence集中为mutable controller，删除测试后复杂性会回流同一巨类；当前hold/异常反证说明其状态blast radius已经存在。方案C实现最省，但正是本次architecture review要修复的现状：局部PASS不能合成可执行计划证明。

用户裁决采纳方案A，登记VR-20；弃用方案B/C，登记ALT-141..142。

### 6.4 DC-02 · Numerical + physical safety + profile kernel（final）

#### 完整方案定义

| 子模块 | 方案A：Primal-hard + Swept Conservative | 方案B：KKT-hard + Exact Rigid Geometry | 方案C：Solver-native + Post-run Gate |
|---|---|---|---|
| termination | eligible desired/callback-feasible/timeout-feasible classes；同candidate original primal hard；KKT同点可得时advisory | 只接受desired terminal solution；stationarity/dual/complementarity全hard；callback/timeout因缺同点dual一律拒绝 | 信任Ipopt `success/return_status`和现有`feasible` bool |
| numerical | independent graph/objective/bounds复核；mixed-unit quantity tolerances；strict zero-slack actual proof | 同A并强制校准KKT阈值；要求terminal multipliers/scaling完整 | 使用solver统一`1e-3` primal recheck和prepared diagnostics，不做第二层复核 |
| dynamic safety | all relevant targets，81 knots/80 synchronized intervals；解析center segment minimum减双方包围圆和trusted uncertainty | all relevant targets；continuous oriented-rectangle/C2A motion bounds、姿态旋转、tracking/prediction tube | 依赖L3 selected-target node CPA/continuous point摘要；实际安全交Evaluator |
| static safety | supplied immutable ENU hazard geometry上做保守circle swept clearance；chart profile mandatory | oriented hull against exact ENC hazard/C2A swept collision；需要完整姿态和chart topology | online不检查；仅Evaluator报告grounding |
| uncertainty | God zero或经校准逐时域conservative envelope；其他UNKNOWN | joint probabilistic/robust tube进入exact geometry，需校准风险分配 | 使用当前point prediction/常量margin；缺失时继续 |
| profile | 同一checker；MASS_PARITY diagnostic-only，COLAV_STRICT机械证明actual bounds/options/hash | 同A；strict再要求KKT/exact-geometry profile和完整model hashes | 只看`profile_name`/algorithm id；parity/strict主要由solver config区分 |
| evidence/runtime | per-row/per-target/segment witness，bounded O(TN)，无需第二NLP | multipliers、C2A iterations、closest rigid features和tube witnesses；计算/实现更重 | 保存status、CPA摘要与Evaluator run result；在线成本最低 |

#### 七维决策卡

| 维度 | 方案A：Primal-hard + Swept Conservative | 方案B：KKT-hard + Exact Rigid Geometry | 方案C：Solver-native + Post-run Gate |
|---|---|---|---|
| 来源 | [R15..R33]；Ipopt官方语义、CasADi outputs、frozen row审计、continuous geometry推导及现有Evaluator分责 | [R17][R19][R27][R28][R31]；terminal dual可取、C2A/rigid geometry有论文与Evaluator局部基础 | [R1][R2][R18][R22]；接近当前solver/facade实现和既有G3路径 |
| 工程验证 | **核心数值/几何seams已项目验证**：8 parity records、strict original bounds、16x80 analytic geometry probe；完整L4待实现 | **局部实验/论文**：terminal KKT probe和Evaluator C2A存在；无planned 81x80 online exact implementation、无callback dual | **当前项目运行验证**：真实IPOPT closed-loop PASS；但只证明现有场景结果，已知selected/node/末段/profile缺口 |
| 技术分解 | termination✓ original primal✓ mixed units✓ dynamic/static✓ uncertainty✓ all-target✓ strict/parity✓ witnesses✓ | 数值/几何/uncertainty/profile均完整✓；callback/timeout availability✗，active rigid attitude/tube inputs△ | solver status✓ node CPA✓ post-run Evaluator✓；all-target continuous/static/profile proof/online evidence✗ |
| 失效边界 | 包围圆保守误拒大船/狭水域；non-God无calibrated envelope即reject；不声明exact rectangle distance。SC-15..19/65..69 | callback/timeout全部误拒；目标姿态/rotation/tube缺失无法运行；C2A/dual阈值可能超budget。SC-15/17/58..60 | node间/末段/footprint/unselected碰撞可漏；Evaluator发现时command已执行；伪strict可放行。SC-06/07/16..19 |
| 实现风险 | **中高**：mixed-unit与static schema严格，但O(TN)约5ms级几何已有可行证据 | **很高**：需exact continuous rigid motion、可靠姿态/tube、KKT calibration；p99和独立oracle复杂 | **低实现、高安全风险**：改动少，但无法满足execution-before-acceptance目标 |
| 可测性 | **高**：independent formula、50m boundary、first/last interval、same-point/KKT advisory、profile mutation | **中**：exact oracle可测但构造昂贵；KKT随scaling/solver/active set敏感，callback无法同点证明 | **低至中**：status/node tests容易；关键缺陷只能靠closed-loop/Evaluator偶然暴露 |
| 推荐度 | **★★★★★** | **★★☆☆☆** | **★☆☆☆☆** |

#### 初步裁决建议

推荐**方案A**。它在当前可取得的candidate evidence下，把original numerical feasibility和physical Ship0 safety设为hard，同时不虚构缺失的callback multipliers或exact rigid tracking tube。[R15..R29]

方案B提供更强的局部最优/几何精度，但不是A的“更严格直接升级”：它会丢失真实出现的callback feasible candidate，并要求当前contract不存在的完整姿态、旋转sweep与校准tube；在这些输入准备好前只会把系统变成普遍fail-stop。方案C已有运行基础，但事后Evaluator不能补救已下发的unsafe plan，且selected/node/profile label缺口正是L4要解决的问题。

用户裁决采纳方案A，登记VR-21；弃用方案B/C，登记ALT-143..144。

### 6.5 DC-03 · COLREG behavior + active-plant execution + multi-target（final）

#### 完整方案定义

| 子模块 | 方案A：Lifecycle-locked Obligations + Prefix Capability | 方案B：Candidate-relative Reclassification + Full-horizon Rules | 方案C：Safety-only Online + Post-run COLREG |
|---|---|---|---|
| rule authority | Lifecycle唯一拥有episode/role/phase/locked side/action/deadlines/release；L4只验证trajectory履约 | L4在每个candidate/knot按相对几何重新分类，并自行选择role/side/Rule17 phase | Online只做collision safety；COLREG role/quality由Evaluator在run后判定 |
| HO/CS/OT/stand-on | 完整window验证port-to-port、pass-astern、locked OT corridor、stand-on/Rule17；standard OT tie-break由Lifecycle选starboard | 使用candidate-relative bearings逐时判断规则；选择使整段规则cost/constraints最小的side | MPC自由选择安全轨迹；不设online passing-side、early或stand-on obligation |
| action timing | 固定commit baseline、absolute start/achievement deadlines、actual cumulative achievement、first executable interval、reachability certificate | 每次solve基于当前course重置action baseline；全1200s trajectory只要最终满足rule geometry即可 | 无online early/substantial gate；事后从actual trajectory统计 |
| past-clear/recovery | 仅Lifecycle基于actual facts授予release；L4验证无提前回切/re-entry，quality观察recovery | L4由predicted future past-clear自行推进phase并允许candidate恢复 | MPC按route objective自由恢复；Evaluator事后判断是否过早 |
| trackability | COG/SOG与body state显式；80 piecewise-constant commands；真实active-plant execution-prefix envelope hard；无full tube缩窄claim | 对完整1200s reduced trajectory执行静态ROT/accel等hard limits，视为full-plant trackable | 只依赖Mid NLP ROT/decel和generic Adapter continuity；plant mismatch交closed-loop结果 |
| quality | smoothness/churn/polyline progress/recovery为advisory；mandatory规则/执行问题各归owner | quality与rule cost共同hard gate，限制全时域曲率、route deviation、recovery time | 主要使用NLP objective和Evaluator最终metrics，不做cross-solve acceptance |
| multi-target | 五集合reconcile、TrackKey generation、all relevant per-target mandatory AND；Lifecycle/Assembler仲裁冲突 | L4对per-knot classifications/risks加权或选择dominant target/共同side | solver selected/primary target在线；global collision/规则由Evaluator汇总 |

#### 七维决策卡

| 维度 | 方案A：Locked Obligations + Prefix Capability | 方案B：Candidate-relative Reclassification | 方案C：Safety-only + Post-run COLREG |
|---|---|---|---|
| 来源 | [R34..R55]；COLREG正文、Candidate 2 Lifecycle、passing predicates、COG/SOG与active-plant实验、多目标authority | [R34][R40][R43..R50]；瞬时几何和全时域trajectory可计算，类似一体化规则checker思路 | [R4][R8][R27][R41]；接近传统安全planner + independent evaluator流程 |
| 工程验证 | **项目核心seams已验证**：Lifecycle standard/mirror OT、真实HO/CS/OT/multiship；active-prefix L4尚待实现 | **局部数学可行、项目反证明显**：早期facade曾因转向后重分类产生intent flicker；无full-plant tube | **现有场景运行验证**：Evaluator可判断最终结果；但发现时command已经执行，不能构成online acceptance |
| 技术分解 | authority✓ HO/CS/OT/Rule17✓ timing✓ past-clear✓ active plant✓ quality✓ five-set multi-target✓ | 全时域classification/rules/quality/limits✓；stable episode/actual release✗，真实plant/full tube△，conflict authority△ | safety✓ post-run COLREG/quality✓；online rule/timing/trackability/all-target acceptance✗ |
| 失效边界 | Lifecycle缺deadline/capability即fail-closed；planned compliance不等于actual compliance；standard/mirror side按policy。SC-20..38/68/71 | candidate转向会改变classification并解除原责任；每solve baseline重置；reduced 1200s limits冒充plant能力。SC-20/22/23/29..34 | Wrong-side/迟行动/不可跟踪plan可先下发；Evaluator只能报告，不能阻断。SC-09/10/20..34 |
| 实现风险 | **高但分责清晰**：需deadline/reachability/active capability contract和independent predicates | **很高**：L4成为第二Lifecycle+Planner，phase/side/quality/conflict状态复杂且与candidate互相影响 | **低实现、高业务风险**：保留现状，无法满足用户OT/HO/CS execution-before-pass目标 |
| 可测性 | **高**：locked episode fixtures、standard/mirror OT、deadline边界、prefix capability、per-target mutation、closed-loop cross-check | **中低**：分类与candidate循环依赖；需要大量轨迹/phase组合，expected authority不稳定 | **中**：Evaluator场景容易跑；但online缺陷只能用事故式closed-loop证伪 |
| 推荐度 | **★★★★★** | **★☆☆☆☆** | **★☆☆☆☆** |

#### 初步裁决建议

推荐**方案A**。它把“规则决定是什么”和“候选是否遵守决定”分开：Lifecycle稳定锁定责任/侧别/phase，L4用当前candidate和真实active-prefix能力给出执行前证据。[R35][R37..R47]

方案B看似更完整自主，却会让candidate动作反向改变自身规则分类，正好重现已诊断的intent flicker；还把1200s reduced trajectory误作Viknes+FLSC全时域能力。方案C适合独立事后评价，但无法修复用户关心的OT初始错误转向、迟行动或不可跟踪command先下发。

用户裁决采纳方案A，登记VR-22；弃用方案B/C，登记ALT-145..146。

### 6.6 DC-04 · Fresh/hold/replan + receipt/warm transaction（final）

#### 完整方案定义

| 子模块 | 方案A：Prefix Revalidate + Atomic Receipt | 方案B：Every-tick Fresh Solve | 方案C：Last-plan Continuation + Fallback |
|---|---|---|---|
| fresh | Candidate完整L4；deadline/freshness后Adapter原子commit active plan/command/receipt/warm/trace | 每个simulation tick都Assembly→IPOPT→完整L4→commit，无HOLD模式 | 按solve period fresh solve；solver success后立即保存last solution，轻量validate |
| hold | 原absolute timeline切片；current ownship/context下验证到next solve的active prefix；state可插值、command piecewise-constant | 不存在hold；每tick均产生新candidate/new receipt | 直接采样last plan；按clock沿用旧status/feasible，command可插值 |
| stale/replan | 新target、generation/phase、deviation、prediction/route/plant变化触发同算法一次immediate replan；失败fail-stop | 下一tick本来就重求；本ticksolve失败立即fail-stop或等待下tick，取决运行策略 | stale时继续旧plan、重试、cold/warm或切换fallback/零速/保持舵 |
| transaction | L4 certificate与Adapter commit receipt分离；commit前无可见solution/event；rejection清除active/warm | 每tick同样原子commit，但receipt churn高、solver与L4持续占用deadline | solution/status/trace分别更新；异常后尽量rollback或继续previous plan |
| receipt | Fresh accepted后签一次；hold只引用parent且不续期 | 每tickaccepted即签新receipt，previous仅存极短时间 | solver success或feasible即作为last-plan authority，无独立L4 receipt |
| warm | 兼容receipt的heading/speed primal按absolute time重采样；cold tail、slack重建、dual off；失败无cold retry | 几乎每tick尝试previous-primal warm；仍需5s/15s或更细elapsed重采样 | 直接shift raw x/复用last solution；可warm→cold retry，甚至将last plan视prefix |
| failure/UI | rejection无command、no fallback、Session FAILED；active/latest双时间线 | 本tick无accepted candidate即无command；高频attempt在UI独立显示 | 保留last command/trajectory以维持服务；UI常显示最近success并隐藏本tick failure |
| runtime | solver每5s周期，仅hold做bounded O(TN) prefix check；一次replan受20s总门 | tick频率乘以完整IPOPT/L4成本，需更强算力/更长tick或异步planner | 在线成本最低，但安全许可和状态一致性弱 |

#### 七维决策卡

| 维度 | 方案A：Prefix Revalidate + Atomic Receipt | 方案B：Every-tick Fresh Solve | 方案C：Last-plan Continuation + Fallback |
|---|---|---|---|
| 来源 | [R52..R62]；hold偏差实证、multi-step safety filter、accepted-plan/warm与atomicity证据 | [R13][R54][R60][R73]；持续重算可减少staleness，但需满足实时求解 | [R3][R52..R59]；接近当前CustomMPCAdapter和常见hold-last策略 |
| 工程验证 | **部分seam已验证**：5s solve/15s grid、receipt/SeedPlan设计、real solver timing；完整hold L4事务待实现 | **solver可运行但未工程验证该频率**：16-target单次约2s，simulation tick通常远快于此 | **当前项目存在且有反证**：100m偏差仍SUCCESS、旧trace/command泄漏风险已复现 |
| 技术分解 | fresh✓ hold✓ stale✓ one-replan✓ atomic commit✓ receipt✓ warm✓ reset✓ failure/UI✓ deadline✓ | fresh/atomic/receipt/warm✓；hold/stale由重求消除✓；算力/real-time feasibility△，tick miss policy需额外设计 | scheduling/last-plan/fallback✓；current-prefix proof✗、acceptance receipt✗、atomicity△、no-fallback✗ |
| 失效边界 | hold只证明到next solve；replan一次后fail-stop；偏差/capability阈值缺失时replan/reject。SC-39..64 | 求解时长超过tick或连续失败时无及时command；高频nonconvex解波动和artifact flood。SC-58..64/79 | 新目标/偏差期间继续unsafe plan；rollback不完整；warm/hold/fallback authority混淆。SC-39..57 |
| 实现风险 | **高但bounded**：需absolute slicing、prefix prediction、Adapter transaction与双timeline | **很高运行风险**：架构较简单，但CPU、deadline、determinism、IPOPT churn和I/O不满足现状 | **低改动、高状态风险**：保留已知bug类别，无法证明rejection isolation |
| 可测性 | **高**：fresh/hold/replan truth table、clock/context mutation、failure injection、receipt tamper、5s/15s sampling | **中**：每tick路径统一，但需长时压力、deadline/overrun和solver flakiness测试 | **中低**：happy path易测；异常/rollback/cache/history组合爆炸且old-plan safety缺oracle |
| 推荐度 | **★★★★★** | **★★☆☆☆** | **★☆☆☆☆** |

#### 初步裁决建议

推荐**方案A**。它保留Mid-MPC每5s求解的成本优势，但把hold从“沿用旧成功”升级为“当前snapshot下的短执行许可”，并通过certificate/receipt/atomic commit隔离rejected plan与warm authority。[R52..R61]

方案B概念最简单：没有hold就没有stale hold。然而当前真实16-target solve约2s、完整L4尚未计入，无法在更快simulation tick上可靠每tick重算；高频nonconvex candidate还会增加churn与artifact压力。方案C性能最好，却直接保留100m偏差仍SUCCESS、旧trace回退和隐藏fallback等已证实缺陷。

用户裁决采纳方案A，登记VR-23；弃用方案B/C，登记ALT-147..148。

### 6.7 DC-05 · Evidence + runtime + policy governance（final）

#### 完整方案定义

| 子模块 | 方案A：Canonical Semantic Record + Async Durable Sink | 方案B：Synchronous Event-sourced Durable Commit | 方案C：Lightweight Trace + Best-effort Logs |
|---|---|---|---|
| source of truth | pure L4生成canonical semantic acceptance record/hash；Adapter生成独立dispatch/receipt record | 所有request/layer/event/commit先追加durable event log；reducer状态决定command是否可见 | `PlannerTrace/algorithm_details`和runtime logs为主要事实；无完整canonical record |
| evidence chain | Request→Problem→Prepared→Candidate→Acceptance→Receipt parent hashes | 每一步转为严格序列event及stream offset/hash；receipt引用durable commit event | 保存solve status、trajectory、CPA和少量details；artifact按需/手工生成 |
| runtime/deadline | 20s涵盖semantic record/hash与atomic memory commit；full serialization/I/O移出关键路径 | disk fsync/transaction log write纳入20s且先于command commit | 最小在线开销；只计solver/Adapter，evidence和GUI异步best-effort |
| determinism | semantic hash排除wall timing/path/queue；dispatch record单独表达运行时 | event bytes/order/offset成为authority；需确定性event schema，runtime ordering可影响state | 无byte-identical replay contract；以日志和最终测试结果解释 |
| persistence | item+byte bounded async queue；temp/fsync/rename/manifest；INCOMPLETE/BACKPRESSURE不回滚command但阻断claim | append-only durable store/WAL，同步fsync成功才commit；崩溃后replay恢复active state | 普通文件/log/trace；写失败告警或丢失，不影响claim metadata |
| policy | Registry typed immutable policy，Session freeze/hash；owner-specific views，变化失效receipt/claim | policy change作为event，event stream按版本重放；可支持受控runtime transition | YAML/free-form config分散在algorithm/evaluator/GUI；版本主要靠commit |
| projections | full artifact、<=8KiB inline、GUI mechanical projections；L4/Evaluator source/scope分离 | UI订阅event-derived read model；完整审计强，但需event schema/migration/store | GUI直接读latest solve/details并组合Evaluator结果；可能回退旧trace |
| claim | 只有artifact COMPLETE + V1..V6 exact tuple才能promotion | durable log完整且projection/replay通过后promotion | closed-loop/full pytest通过即可保留/提升capability |

#### 七维决策卡

| 维度 | 方案A：Canonical + Async Sink | 方案B：Synchronous Event-sourced Commit | 方案C：Lightweight Trace |
|---|---|---|---|
| 来源 | [R58..R81]；现有artifact/hash/GUI/persistence缺口、canonical实验、性能与capability治理共同支持 | [R54][R58][R64][R67][R68]；event sourcing/WAL能提供强durability和crash replay，但项目无现成store | [R1..R4][R59][R77]；接近当前PlannerTrace、details、GUI和测试证据方式 |
| 工程验证 | **项目基础较强**：Candidate 3已有前四段artifact链、hash与persistence seam；完整L4/async sink待实现 | **通用工程模式成熟，本项目未验证**：无durable event store、schema migration、transactional read model | **当前项目已运行**：8010/G3/trace可用；但旧solve回退、field mismatch、source混淆已有证据 |
| 技术分解 | canonical✓ chain✓ deadline✓ determinism✓ bounded persistence✓ policy✓ projections✓ claim invalidation✓ | 全部子模块完整✓，另有crash state recovery✓；但同步I/O实时隔离✗，store/migration依赖高 | trace/GUI/log✓；canonical/replay/parent integrity/bounded sink/policy invalidation/claim completeness✗ |
| 失效边界 | sink失败时command仍有效但claim incomplete；queue持续满需运维；semantic与dispatch需清晰分名。SC-52..64/70/78..82 | fsync慢/磁盘满会让安全candidate超deadline；event ordering/schema migration可阻断控制；store成为关键依赖。SC-58/61/63/64 | 字段漂移、日志丢失、stale GUI和无法replay；claim无法绑定exact decision。SC-52..57/70/78/81 |
| 实现风险 | **高但适配现有seams**：typed schema、projection、bounded sink和policy接线 | **很高**：新基础设施、同步durability、reducer、migration、operational recovery，偏离当前小型Simulator | **低实现、高审计风险**：短期快，长期每次GUI/claim修复继续跨层散落 |
| 可测性 | **最高**：canonical mutation/replay、projection golden、queue/failure injection、semantic/dispatch分离 | **高但昂贵**：event/reducer/property/crash tests完整；需真实磁盘故障和migration矩阵 | **低至中**：API/UI snapshots可测；无法机械证明完整parent chain或同输入同裁决 |
| 推荐度 | **★★★★★** | **★★☆☆☆** | **★☆☆☆☆** |

#### 初步裁决建议

推荐**方案A**。它在当前20s控制contract内把“裁决必须确定且完整”留在内存关键路径，把“完整artifact必须durable”作为独立persistence/claim状态，既不让慢盘改变command，也不让写盘失败被隐藏。[R63..R78]

方案B审计最强，但同步WAL/fsync成为控制关键依赖；项目没有event store/migration基础，新增复杂度远超L4本身，而且磁盘故障会把semantic-safe candidate变成时序失败。方案C开发最快，却继续依赖free-form details、旧trace回退和测试结果作claim，无法满足receipt、replay、policy失效或8010 source真实性。

用户裁决采纳方案A，登记VR-24；弃用方案B/C，登记ALT-149..150。

### 6.8 Step5完整性审计（用户确认）

| 检查 | 结果 |
|---|---|
| 对比范围 | DC-01..05覆盖TD-01整体及DP-01..17全部在线设计；DP-18由用户判定低风险直接采纳 |
| DC-01 | A Independent Pure L4，七维完整，用户final |
| DC-02 | A primal-hard/KKT-advisory + swept conservative safety，七维完整，用户final |
| DC-03 | A Lifecycle-locked obligations + active-prefix capability，七维完整，用户final |
| DC-04 | A prefix revalidation + atomic receipt/warm，七维完整，用户final |
| DC-05 | A canonical semantic record + async durable sink，七维完整，用户final |
| 直接采纳 | DP-18六级promotion gates；由用户明确判定低风险，登记VR-19 |
| Step5裁决 | VR-19..24连续、唯一；DC-01..05各有最终采纳理由 |
| Step5弃用 | ALT-141..150连续、唯一；每个竞争方案有明确失效/弃用理由 |
| DRAFT残留 | 0（Step5 selection标题除状态说明外，所有卡片final） |
| 技术分解 | 无残缺竞争方案被采纳；方案A组合完整覆盖Module、kernel、behavior、transaction、evidence/runtime/policy、validation |
| `git diff --check` | PASS |

Step5步骤间门满足。实施/promotion gates仍为：action deadlines/reachability contract、真实Viknes+FLSC active capability、full-L4 p99 reservation、V1..V6验证；它们不会被Step5方案对比隐式放宽。用户确认后进入Step6。

## 7. Step6 术语、技术规约与方案包

### 7.1 状态

- Step5完整性审计：用户已确认。
- 技术规约：`TS-01..42`已从全部final VR、证据、场景和技术分解提取。
- 独立方案包：`docs/superpowers/specs/2026-08-12-mid-mpc-l4-plan-acceptance-solution-pack.md`。
- 用户已明确接受八组件方案包；方案包成为to-spec权威输入。
- 当前会话未提供可调用的`to-spec` skill；交付状态已完成，正式Spec生成需在提供该skill的后续步骤执行。

### 7.2 分解闭环

| 检查 | 结果 |
|---|---|
| DP覆盖 | DP-01..18全部映射到VR-01..24、TS-01..42 |
| TD覆盖 | TD-01全部子模块已有final裁决；无`DECOMPOSITION_INCOMPLETE` |
| 证据覆盖 | R1..R81全部进入方案包证据矩阵 |
| 场景覆盖 | SC-01..82全部进入方案包验收族 |
| 弃用覆盖 | ALT-01..150全部保留；关键竞争方案在方案包中按族汇总，权威逐项理由仍在本日志0.7 |
| 未决项 | 无技术语义TBD；四项production gates显式保留，不是设计缺口 |

### 7.3 Step6移交

方案包已接受并交付。to-spec必须以方案包为权威输入；可做工程细节设计，不可推翻VR、重提ALT或修改TS。发现新矛盾证据必须回本流程重开受影响DP。

移交声明：

> 本方案的核心技术决策已通过design-grounding裁决。to-spec负责把既有结论综合为设计与实施Spec、测试seams和issue，不得推翻已裁决方案、重提弃用方案或修改技术规约；发现新矛盾证据时回炉design-grounding。

### 7.4 to-spec产物

- Spec：`docs/superpowers/specs/2026-08-12-mid-mpc-l4-plan-acceptance-design.md`
- Implementation Plan：`docs/superpowers/plans/2026-08-12-mid-mpc-l4-plan-acceptance-implementation.md`
- Ready issue：<https://github.com/marinehdk/colav-simulator/issues/26>
- Plan comment：<https://github.com/marinehdk/colav-simulator/issues/26#issuecomment-5262965820>
- Primary test seam：`MidMpcPlanAcceptance.evaluate(request)->result`
- Integration seams：`CustomMPCAdapter.plan(...)`、`P1RunHarness`、real port-8010 Session/API event

### 7.5 实施前矛盾裁决

2026-08-12用户确认：active capability按exact tuple绑定，不把KinematicCSOG当作Viknes+FLSC替代物。单船HO/CS/OT以Viknes+FLSC接受；`paper_ccta2023_multiship`仅以其实际KinematicCSOG+pass-through tuple接受。最终仅合并Colav-Simulator本地`main`和GitHub`main`，不移植GitLab MASS `l3-tdl`。
