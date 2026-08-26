# 设计日志: Threat Authority and Management

> **模式**: 重构        **创建**: 2026-08-21
> **关联 spec**: GitHub Issue #29 + `docs/superpowers/specs/2026-08-21-predictive-threat-historical-ais.md`
> **原附件 SHA-256**: `902faaede72f0952fbb2ccb298fde88de322c7b2738d842c80dd02af781c6681`
> **状态**: Step3已完成；DP-01–DP-21 implementation-ready contract 已冻结

本日志记录 Threat Management 与现有 COLREG Lifecycle、Plan Acceptance、Independent Evaluator、Web Projection 和 Historical AIS 之间的 authority 边界。它保留历史调研与裁决过程；正式实现契约以 canonical Spec 为准，外部研究盲区不允许被实现者静默填补。

## 0. 决策树状态(权威索引 · 可变快照)

### 0.1 决策点注册表 [DP]

| ID | 描述 | 类型 | 父/分解 | 状态 | 详见 |
|---|---|---|---|---|---|
| DP-01 | Coordinator 在 Threat Management Cycle 开始时从 Ownship State + TrackSnapshot 生成唯一 Canonical PhysicalEncounterFacts | 架构 | TD-01 | 已裁决 | VR-03 |
| DP-02 | EncounterLifecycle 与 ThreatAssessment 共同消费 Canonical PhysicalEncounterFacts，不在线重复计算同义 CPA/geometry | 接口 | TD-01/TD-02/TD-03 | 已裁决 | VR-03 |
| DP-03 | 每类威胁事实一个 canonical authority；保留独立 L4 Gate、Independent Evaluator，Web 仅 projection | 架构 | — | 已裁决 | VR-01 |
| DP-04 | Session/Runtime 级唯一 ThreatManagementCoordinator；每 Own Ship、每 Active Session 一个实例，内部持有唯一 EncounterLifecycle 与 Primary state | 架构 | TD-02/TD-03 | 已裁决 | VR-02 |
| DP-05 | Ship Domain facts 如何参与 domain-aware Primary 而不产生第二个 Primary | 架构 | TD-02/TD-03 | 已冻结 | Step3→Spec DP-05 |
| DP-06 | ThreatAssessment public seam 与是否保持纯派生 | 技术 | TD-03 | 已冻结 | Step3→Spec DP-06 |
| DP-07 | Threat Vector 的独立字段与 display-only 指数边界 | 接口 | TD-01/TD-03 | 已冻结 | Step3→Spec DP-07 |
| DP-08 | ShipDomainProfile 的形状、参数、假设与版本边界 | 技术 | TD-03 | 已冻结 | Step3→Spec DP-08 |
| DP-09 | ObservationHealth、uncertainty、缺失 prediction 的 UNKNOWN 语义 | 约束 | TD-01/TD-03 | 已冻结 | Step3→Spec DP-09 |
| DP-10 | Threat priority 的 lexicographic classes、reason 与 tie-break | 算法 | TD-03 | 已冻结 | Step3→Spec DP-10 |
| DP-11 | Threat Window 的 entry/peak/exit 与 prediction time-axis | 算法 | TD-03 | 已冻结 | Step3→Spec DP-11 |
| DP-12 | Current/Concurrent/Next/Monitor Threat Schedule membership 与 rolling 更新 | 架构 | TD-03 | 已冻结 | Step3→Spec DP-12 |
| DP-13 | Primary/challenger hysteresis、emergency preemption、generation/rearm 行为 | 算法 | TD-02/TD-03 | 已冻结 | Step3→Spec DP-13 |
| DP-14 | baseline 与 accepted plan 的 plan-induced conflict 证据条件 | 约束 | TD-03/TD-04 | 已冻结 | Step3→Spec DP-14 |
| DP-15 | typed Conflict Graph 与 deterministic Conflict Cluster 规则 | 算法 | TD-03 | 已冻结 | Step3→Spec DP-15 |
| DP-16 | Ship Domain/Threat Index 与 hard hull-clearance/L4 verdict 的边界 | 约束 | TD-04/TD-05 | 已冻结 | Step3→Spec DP-16 |
| DP-17 | EncounterMonitor、Independent Evaluator 与在线 ThreatAssessment 的关系 | 架构 | TD-05/TD-06 | 已冻结 | Step3→Spec DP-17 |
| DP-18 | Web 仅消费 canonical ThreatManagement projection 的迁移边界 | 架构 | TD-06 | 已冻结 | Step3→Spec DP-18 |
| DP-19 | Threat snapshot schema、hash、event retention、replay equality | 接口 | TD-03/TD-04/TD-06 | 已冻结 | Step3→Spec DP-19 |
| DP-20 | Historical AIS raw source、Historical Actor、Tracker observation、Human Reference 的威胁事实边界 | 架构 | TD-07 | 已冻结 | Step3→Spec DP-20 |
| DP-21 | Legacy algorithms 的 global rollout、capability evidence 与缺失 Lifecycle/accepted-plan facts 的边界 | 架构 | TD-03/TD-06/TD-07 | 已冻结 | Step3→Spec DP-21；受 VR-02 约束 |

### 0.2 技术分解注册表 [TD]

| ID | 技术 | 分解子模块(→DP) | 触发步骤 |
|---|---|---|---|
| TD-01 | Canonical Physical Threat Facts | identity/health/uncertainty(DP-01/02/09); geometry(DP-01/02); units/hash(DP-01/19) | Step1 |
| TD-02 | EncounterLifecycle | classification/role(DP-02); risk/commitment/release(DP-04/13); Primary(DP-04/05/13); aggregate obligation(DP-12/16) | Step1 |
| TD-03 | ThreatAssessment | domain(DP-06/07/08); prediction/window(DP-09/11); priority/schedule(DP-10/12/13); plan conflict/graph(DP-14/15); evidence(DP-19) | Step1 |
| TD-04 | Plan Acceptance/L4 Gate | accepted-plan identity(DP-14/19); hard hull/swept safety(DP-16); failure ownership(DP-03/16) | Step1 |
| TD-05 | Independent Evaluator | realized trajectory/CPA/collision/grounding(DP-16/17); independent COLREG scoring(DP-03/17) | Step1 |
| TD-06 | Web Projection | versioned projection(DP-17/18/19); unavailable/degraded display(DP-09/18); no browser authority(DP-03/18) | Step1 |
| TD-07 | Historical AIS Threat Boundary | raw digest/quality(DP-20); Historical Actor replay(DP-20); T0/Human Reference isolation(DP-20); legacy rollout evidence(DP-21) | Step1 |

### 0.3 盲区注册表 [BL]

| ID | 问题 | 归属决策点 | 优先级 | 调研状态 |
|---|---|---|---|---|
| BL-01 | 当前 Lifecycle 与 Evaluator/Monitor 各自计算 geometry；是否抽取一个共享 online physical-facts seam | DP-01/02 | 高 | 已闭环→[R12] |
| BL-02 | Ship Domain 的 profile、数值和适用 ODD 缺少本项目已验证的统一答案 | DP-08/10/11 | 高 | UNKNOWN |
| BL-03 | domain-aware Primary 是否必须改变 Lifecycle 输入与 Primary ranking | DP-04/05/13 | 高 | 调研中 |
| BL-04 | plan-induced conflict 的 materiality、baseline、accepted receipt 和 witness 最小集合 | DP-14/15 | 高 | 调研中 |
| BL-05 | Evaluator 与 online ThreatAssessment 可共享哪些 physical formulas 而不形成 policy/self-certification 耦合 | DP-01/16/17 | 高 | 仍未决（共享公式边界） |
| BL-06 | legacy algorithms 没有统一 Lifecycle/accepted-plan evidence 时的 global rollout 资格 | DP-21 | 中 | UNKNOWN |
| BL-07 | Web 删除旧排序、DCPA levels、distance threat 后的 runtime/projection evidence | DP-18/19 | 中 | 调研中 |
| BL-08 | NotebookLM fast research 与 CodeGraph 均不可用时，外部 domain facts 的最新确认 | DP-08/10/14/16 | 中 | UNKNOWN |

### 0.4 证据矩阵 [EV]

| ID | 来源类型 | 引用 | 检索置信 | 来源权威 | 场景适用 | 归属 |
|---|---|---|---|---|---|---|
| [R1] | DOCUMENTED_INTENT | Issue #29 与附件 `colav_predictive_threat_historical_ais_spec.md`：单一 Backend Threat Management、Lifecycle authority、独立 L4/Evaluator、Web projection | 高 | 高 | 高 | DP-03/06/07/08/10/11/12/14/15/16/18/19/20 |
| [R2] | PROJECT_FACT | `colav_simulator/core/colav/encounter_lifecycle.py`：TrackKey、RiskPhase、Commitment、Rule17、release/rearm、AggregateDirective、Primary hysteresis、atomic snapshot | 高 | 高 | 高 | DP-02/04/05/13 |
| [R3] | PROJECT_FACT | `colav_simulator/evaluation/encounter.py`、`gui_server/main.py`：EncounterMonitor 真值输入、独立 Pairwise FSM、Web weighted Primary | 高 | 高 | 高 | DP-01/02/10/17/18 |
| [R4] | PROJECT_FACT | `colav_simulator/evaluation/evaluator.py`：完整 trajectory、trajectory CPA、collision/grounding、COLREG scoring、hard gate | 高 | 高 | 高 | DP-16/17 |
| [R5] | PROJECT_FACT + DOCUMENTED_INTENT | Lifecycle 与 Assembler solution pack：Lifecycle 是 state owner；Assembler 不重新分类；L4/Evaluator 独立 | 高 | 高 | 高 | DP-02/03/04/16/17/19 |
| [R6] | PROJECT_FACT | `prediction_evidence.py`、`mid_mpc_acceptance.py`、`mid_mpc_ipopt.py`：prediction purpose、accepted plan、acceptance hash、typed evidence | 高 | 高 | 高 | DP-06/11/14/16/19 |
| [R7] | PROJECT_FACT | `colav_simulator/core/tracking/trackers.py`：TrackKey、TrackSnapshot、covariance、observed/generated time、health/status/source | 高 | 高 | 高 | DP-01/02/09/19/20 |
| [R8] | PROJECT_FACT + DOCUMENTED_INTENT | `Design/Colav-Simulator-Architecture.md` 与现有 Web projection：风险展示字段及前端派生事件/阈值 | 高 | 中 | 高 | DP-17/18 |
| [R9] | UNKNOWN | NotebookLM：已认证，但三次 `research --depth fast` 均因 `CSRF token not found in HTML` 失败 | 高 | 低 | 不适用 | DP-08/10/14/16 |
| [R10] | UNKNOWN | CodeGraph：目标 worktree 无 `.codegraph/`，无法提供索引证据；本轮以窄范围源码读取降级 | 高 | 低 | 不适用 | 全部 PROJECT_FACT 结构复核 |
| [R11] | DOCUMENTED_INTENT | 既有 Lifecycle design log 引用的 Ship Domain、COLREG、多目标与 Evaluator 论文清单；本轮未重新验证外部原文 | 中 | 中 | 中 | DP-08/10/14/15/16 |
| [R12] | USER_CONFIRMED_DESIGN | 用户确认：Coordinator 周期开始生成唯一 Canonical PhysicalEncounterFacts；Lifecycle/ThreatAssessment 共同消费；L4/Evaluator 保留各自 trajectory facts/verdicts | 高 | 高 | 高 | DP-01/02/16/17 |

### 0.5 场景注册表 [SC]

| ID | 场景描述 | 约束/边界 | 驱动决策点 |
|---|---|---|---|
| SC-01 | 多目标同周期：A 为 Primary，B 仍为 required | Primary 不得删除 AggregateDirective required target | DP-04/12/16 |
| SC-02 | Ship Domain 先于 CPA 进入 | domain exposure 不得伪装成已发生 collision，也不得等到 CPA 才出现 | DP-08/10/11 |
| SC-03 | Lifecycle 与 ThreatAssessment 对同一 target 的角色/优先级不一致 | 必须报告 source mismatch，不得静默覆盖 | DP-03/05/17 |
| SC-04 | accepted plan 使 C 的未来 Threat Window 新出现或恶化 | 无 accepted receipt、仅有 raw solver candidate 时不得产出 plan-induced edge | DP-14/15/16 |
| SC-05 | target coasting、degraded、generation reuse | 数据质量不等于 CLEAR；旧 generation 不得继承 active facts | DP-01/09/13/19 |
| SC-06 | Web reconnect、session replacement、sealed replay | projection 不得重算 risk；snapshot/order/edge 应可重放 | DP-18/19 |
| SC-07 | Historical AIS T0 前后 | Historical Actor 可作为环境，post-T0 Human Reference 不得进入 Planner | DP-20 |
| SC-08 | legacy algorithm global rollout | 无 Lifecycle/accepted-plan/Threat evidence 的组合必须显式 capability boundary | DP-21 |
| SC-09 | 目标间 direct overlap 与 transitive conflict | edge 类型可审计，cluster connected components 稳定 | DP-14/15 |

### 0.6 裁决注册表 [VR]

| ID | 裁决对象 | 结论 | 采纳/弃用 | 理由 | 时间 |
|---|---|---|---|---|---|
| VR-01 | DP-03 authority partition | 每类威胁事实一个 canonical authority；保留独立 L4 Gate 与 Independent Evaluator；拒绝巨型 ThreatAssessment 同时负责在线威胁、执行验收和离线评价；Web 只做 projection | 采纳(final) | 用户明确确认；避免并行 risk/ordering/verdict source，保留 failure ownership 与独立性 | 2026-08-21 |
| VR-02 | DP-04 Session/Runtime online authority | 每 Own Ship、每 Active Session 一个唯一 ThreatManagementCoordinator；内部持有唯一 EncounterLifecycle；Planner/Web/Evidence 共用同一 ThreatManagementSnapshot；accepted plan 只进入下一周期；legacy algorithm 不得发布竞争性 canonical threat | 采纳(final) | 用户明确确认；消除 Planner/GUI 第二 Lifecycle 与同周期反馈循环，同时保留 L4/Evaluator 独立 | 2026-08-21 |
| VR-03 | DP-01/DP-02 Canonical PhysicalEncounterFacts | Coordinator 在每个 Threat Management Cycle 开始时，从 Ownship State + TrackSnapshot 生成一次包含 identity/health/age、relative geometry、signed TCPA、forward DCPA、validity/unavailable reason、current hull geometry 的 canonical online facts；EncounterLifecycle 与 ThreatAssessment 共同消费，在线链禁止重复计算同义 CPA/geometry；L4 candidate trajectory 与 Evaluator realized trajectory 保持各自 facts/verdicts | 采纳(final) | 用户明确确认；消除在线物理事实漂移，同时避免把 online CPA 冒充 L4/Evaluator 证据 | 2026-08-21 |

### 0.7 备选/弃用方案 [ALT]

| ID | 方案 | 弃用理由 | 对比于 |
|---|---|---|---|
| ALT-01 | 一个 ThreatAssessment 同时拥有 Lifecycle、在线威胁、L4 acceptance 和 Independent Evaluator | 混合 state、prediction、execution safety 与 retrospective scoring；允许 Planner 自证，失败边界不可归属 | DP-03 |
| ALT-02 | EncounterMonitor、Web、ThreatAssessment 各自维护风险排序 | 同一 target 可得到不同 Primary、DCPA level、distance risk；无法形成唯一 replay evidence | DP-03 |
| ALT-03 | 用 online ThreatAssessment 或 Planner verdict 替代 Independent Evaluator/L4 | 把预测或控制意图冒充已实现轨迹安全；破坏独立验收 | DP-03/16/17 |
| ALT-04 | Planner 自己持有在线 Coordinator 或创建第二 Lifecycle | 产生按算法分叉的 lifecycle/Primary，且 accepted plan 可在同周期回灌形成循环 | DP-04 |
| ALT-05 | GUI/Browser 持有在线 ThreatManagement authority | 刷新、投影 fallback 和显示逻辑会改变 safety semantics；重演现有多套排序 | DP-04/18 |
| ALT-06 | accepted plan 在同一 Threat Management Cycle 立即回灌 | 形成 candidate→acceptance→threat snapshot 的循环依赖，snapshot 不再是单一周期事实 | DP-04/14/19 |
| ALT-07 | Lifecycle 与 ThreatAssessment 各自重新计算 CPA/geometry | 同义事实的符号、validity、unavailable handling、hull assumptions 或 units 可能漂移，破坏 canonical online facts | DP-01/02 |
| ALT-08 | 用 online CPA/geometry 替代 L4 candidate 或 Evaluator realized trajectory facts | 混淆 current observation、candidate plan 和 realized behavior 的证据与 verdict owner | DP-01/02/16/17 |

### 0.8 技术规约注册表 [TS]

| ID | 类别 | 规约内容 | 单位/定义 | 来源 | 关联DP/接口 | 与现状差异 |
|---|---|---|---|---|---|---|
| — | Step3 后登记 | DP-05–DP-21 的实现边界、typed unavailable、版本/哈希、无 fallback 和无第二 truth 约束见 canonical Spec；未在 Spec 明示的数值阈值仍须由独立 oracle/上游 contract 冻结，不得实现者临时发明 | — | — | DP-05..DP-21 | 允许实现具体模块，不允许改变 authority 或安全边界 |

---

## 参考文献

- [R1] GitHub Issue #29 and `/Users/marine/Downloads/colav_predictive_threat_historical_ais_spec.md`.
- [R2] `colav_simulator/core/colav/encounter_lifecycle.py`.
- [R3] `colav_simulator/evaluation/encounter.py`; `gui_server/main.py`; `web_gui/modules/telemetry-projection.js`; `web_gui/modules/situation-display.js`.
- [R4] `colav_simulator/evaluation/evaluator.py`; `colav_simulator/core/colav/mid_mpc_acceptance.py`.
- [R5] `docs/superpowers/specs/2026-08-11-mid-mpc-l0-l1-encounter-lifecycle-solution-pack.md`; `docs/superpowers/specs/2026-08-11-mid-mpc-l1-l2-problem-assembler-solution-pack.md`.
- [R6] `colav_simulator/core/colav/prediction_evidence.py`; `colav_simulator/core/colav/mid_mpc_acceptance.py`; `colav_simulator/integrations/mid_mpc_ipopt.py`.
- [R7] `colav_simulator/core/tracking/trackers.py`.
- [R8] `Design/Colav-Simulator-Architecture.md` and current Web projection modules.
- [R9] NotebookLM fast-research attempts on 2026-08-21; authenticated session but client CSRF failure.
- [R10] CodeGraph availability check on the target worktree; no `.codegraph/` index found.
- [R11] `docs/superpowers/design-logs/2026-08-10-mid-mpc-l0-l1-encounter-lifecycle-design-log.md` and its cited external research bibliography; original sources not re-queried in this Step.

---

## 演进日志(append-only · 时序 · 不可覆盖)

### Step1 · 行业调研·发现决策点  [2026-08-21 14:41]

- 模式判定：**重构模式**。目标领域已有 `EncounterLifecycle`、`EncounterMonitor`、Independent `Evaluator`、Plan Acceptance、prediction evidence 和 Web risk projection；本轮目标是 authority 查漏补缺，不推翻现有已接受边界。
- NLM routing：读取 `.nlm/config.json`，目标选择 `domain:colav_algorithms`、`domain:maritime_regulations`、`domain:safety_verification`。三次 fast research 均失败于客户端 `CSRF token not found in HTML`；未将外部研究结论伪装成已验证事实。[R9]
- CodeGraph：目标 worktree 无 `.codegraph/`；按工具限制停止 CodeGraph 调用，使用窄范围源码/既有文档证据。[R10]
- 当前项目事实：
  - `EncounterLifecycle` 是 Planner 侧 state owner，拥有 per-target lifecycle、AggregateDirective、Primary hysteresis 与 immutable `DecisionSnapshot`。[R2][R5]
  - `EncounterMonitor` 接收 Web truth dictionaries，使用 Evaluator profile 和另一套 pairwise FSM；当前 Web server 以 weighted DCPA/TCPA/range 重新选择 primary。[R3]
  - Independent `Evaluator` 使用 realized VesselData trajectories、trajectory CPA、collision/grounding oracle、COLREG scoring 和 hard gate，不消费 Planner lifecycle verdict。[R4]
  - prediction evidence 与 `MidMpcPlanAcceptance` 已有 accepted-plan identity、prediction purpose、hash/evidence 结构；raw solver candidate 不能直接证明 accepted plan。[R6]
  - `TrackSnapshot`/`TrackKey` 提供 identity、generation、health、covariance、observation time 和 source；EncounterMonitor 当前路径未消费这些完整语义。[R7][R3]
  - Web projection 与 situation display 仍含 DCPA sorting、DCPA level、distance-based threat style 等派生逻辑，构成迁移对象，不是未来 authority。[R3][R8]
- 行业/项目共同事实类型：Observation/Identity、Physical Geometry、COLREG Lifecycle、Prediction/Accepted Plan、Ship Domain、Threat Vector/Window/Schedule、Conflict Graph、Hard Safety、Independent Evaluation、Web Projection、Historical AIS lineage。
- 新增决策点：登记 DP-01..DP-20；补充 DP-21 `Legacy algorithm global rollout`。
- 触发技术分解：TD-01 Physical Facts、TD-02 Lifecycle、TD-03 ThreatAssessment、TD-04 Plan Acceptance/L4、TD-05 Independent Evaluator、TD-06 Web Projection、TD-07 Historical AIS。
- Step1 结论：决策点非空；技术分解已登记；Ship Domain 数值、domain-aware Primary 接入、plan-induced materiality、legacy rollout 和外部行业证据保持未决/UNKNOWN，不能直接进入正式 Spec。

### Step2 · grilling 压力测试  [2026-08-21 14:41]

- 用户确认 DP-03：**每类威胁事实一个 canonical authority；保留独立 L4 Gate 与 Independent Evaluator；拒绝巨型 ThreatAssessment 同时负责在线威胁、执行验收和离线评价。**
- 写入 VR-01，并记录 ALT-01..ALT-03。此为本日志目前唯一已裁决决策。
- 该裁决不自动裁决 DP-01/02/04..DP-21：具体 seam、Primary/domain coupling、阈值、window、graph、schema、legacy rollout 仍需逐项 grilling。
- Step2 当前暂停点：下一步应先逐项确认 DP-01/02/04/05，尤其是“domain-aware Primary 如何进入唯一 Lifecycle owner”这一边界；不得在未确认前创建正式 ThreatAssessment Spec 或改代码。

### Step2 · Session/Runtime online authority confirmation  [2026-08-21 14:55]

- 用户确认 DP-04：采用 Session/Runtime 级唯一 `ThreatManagementCoordinator`；每 Own Ship、每 Active Session 一个实例；其内部持有唯一 `EncounterLifecycle`。
- 周期顺序已确认：冻结本周期 current facts、既有 Lifecycle state、profiles 与上周期可用 accepted-plan evidence → 唯一 Lifecycle 推进 → 产出一个 `ThreatManagementSnapshot` → Planner/Web/Evidence 共用该 snapshot → Planner 产生 candidate → 独立 L4 Gate 验收 → accepted plan 仅作为下一周期 evidence。
- Planner 不再创建第二 Lifecycle；GUI 不拥有 online Threat Management authority；legacy algorithm 可以消费 canonical snapshot 并发布 namespaced diagnostics，但不得发布竞争性 canonical threat。
- 写入 VR-02，并登记 ALT-04..ALT-06。DP-21 保持未决；本裁决只约束其 rollout 必须基于同一 canonical snapshot，不能按 legacy algorithm 发布第二套 threat truth。其 capability evidence、缺失 lifecycle/accepted-plan facts 的具体降级策略仍待确认。
- L4 Gate 与 Independent Evaluator 保持独立：前者负责 executable-plan hard safety，后者负责 realized trajectory Safety/COLREG；二者不被 Coordinator 吸收，也不反写 online snapshot。
- DP-04 状态更新为已裁决；其余 DP 仍保持未决。下一步继续 grilling DP-01/02/05，确认 canonical physical-facts seam 与 domain-aware Primary 的输入边界。

### Step2 · Canonical PhysicalEncounterFacts confirmation  [2026-08-21 15:05]

- 用户确认 DP-01/DP-02：每个 Threat Management Cycle 开始时，由唯一 Coordinator 从 Ownship State + TrackSnapshot 生成一次 Canonical PhysicalEncounterFacts。
- canonical facts 至少包含：TrackKey/generation、observation health/age、relative position/velocity、range/bearings、signed TCPA、forward DCPA、validity/unavailable reason、current hull geometry facts。
- EncounterLifecycle 与 ThreatAssessment 共同消费同一份 online facts；在线链禁止重复计算同义 CPA/geometry。Legacy algorithm 可消费，但只允许发布 namespaced diagnostics，不得建立第二套 canonical physical facts。
- L4 candidate trajectory 与 Independent Evaluator realized trajectory 保持各自 facts/verdicts；online CPA 不得冒充 L4 candidate evidence 或 Evaluator verdict。
- 写入 VR-03，并登记 ALT-07/ALT-08。BL-01 标记已闭环→[R12]；BL-05 仍未决，具体共享公式边界与独立 policy/verdict 责任尚未裁决。
- DP-01/DP-02 状态更新为已裁决；其他 DP 保持原状态。下一步继续 grilling DP-05，确认 Ship Domain facts 如何进入唯一 Lifecycle Primary authority。

### Step3 · 用户确认后冻结 implementation-ready contract  [2026-08-21]

- 用户确认此前提出的五个 TDD seams：ThreatAssessment `evaluate`、ThreatManagementCoordinator `cycle`、HistoricalAISDatasetReader `read`、HistoricalAISCaseBuilder `build`，以及现有 SimulationSession/ExperimentRunner + API/WS 的 Historical Replay/Counterfactual/Web projection seam。所有行为测试必须在这些最高公共边界验证，不测试私有 helper 或浏览器内重算。
- DP-05–DP-21 已按父 Agent 推荐冻结到 `docs/superpowers/specs/2026-08-21-predictive-threat-historical-ais.md`。该文件是实现 source of truth；本日志保留裁决脉络，不再作为未决问题清单。
- DP-05/06/07：Threat Assessment 只派生 domain/horizon facts；Lifecycle 是唯一 Primary state owner；Threat Vector 保留物理、domain、prediction、health、lifecycle、priority 与 provenance 独立字段；Threat Index 若存在只可 display-only。
- DP-08/09/10/11/12/13：ShipDomainProfile 版本化、椭圆 V1、缺尺寸 `UNQUALIFIED`、缺失事实 typed `UNKNOWN/UNAVAILABLE`；priority 使用 hard-gate-first lexicographic order；Threat Window 使用 entry/peak/exit；Schedule 按 Current/Concurrent/Next/Monitor/Released rolling 重算；hysteresis 按 primary/challenger、紧急 preempt、generation/rearm 确定化。
- DP-14/15/16：plan-induced edge 必须有 explicit baseline、fresh accepted/committed receipt、identity/hash 与 before/after witness；raw candidate/stale GUI path 禁止；typed graph + deterministic connected components；Ship Domain/Threat Index 不得替代或削弱 L4 hard safety 与 Independent Evaluator。
- DP-17/18/19：EncounterMonitor 仅 diagnostic；Evaluator 只评 realized trajectory；Web 仅 projection；snapshot canonical serialization/hash、input/profile/plan lineage、event/cluster identity 与 sealed replay equality 必须可审计，旧证据不可原地重写。
- DP-20/21：raw/normalized AIS、Historical Actor、Tracker observation、Human Reference 四类事实分离；T0 后人类轨迹 Compare-only，Nominal Intent 严格只读 `< T0`；缺 lifecycle/accepted-plan/capability evidence 显式 unavailable/incomplete，禁止 fallback、算法替换和第二 canonical threat。
- 以原离线 Spec SHA-256 `902faaede72f0952fbb2ccb298fde88de322c7b2738d842c80dd02af781c6681`、baseline `ba80bf8270b47e76f1811f85ff3aa5fb2c0c3199` 和 Issues #29–#40 内容复核完成。#29 body 应链接 canonical repo Spec 并保留 `ready-for-agent`；不新建 Issue。
