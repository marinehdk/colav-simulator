# /handoff — Sealed Run Replay 开发总接力

> Date: 2026-09-11  
> Repository: `marinehdk/colav-simulator`  
> Main baseline at handoff: `main@1c2b69acc52fdd8dfa515d38f86a679c0b4ef082`  
> Normative Spec: GitHub #69  
> Design PR: #76 (`spec/run-replay-evaluation`)  
> Implementation tickets: #70 → #71 → #72 → #73 → #74 → #75  
> Purpose: 交给一个全新的开发对话。**主 Agent 只做任务中心、调度、审查和集成；代码实现、修复、测试 campaign 尽量派发给 subagents，避免主上下文被实现细节污染。**

---

## 0. 最高优先级操作契约

新对话中的主 Agent 必须先接受以下角色约束：

1. **你是 Orchestrator，不是主要 Implementer。**
2. 不要直接承担大段产品代码开发；每个实现 ticket 必须委派给独立 implementation subagent。
3. 不要在主上下文中展开完整源码、长测试日志、完整 diff。要求 subagent 提交结构化短报告，详细证据写入 GitHub issue / repository evidence 文档。
4. 每个 ticket 在集成前必须有独立 verifier subagent 复核；修复由新的 repair subagent 承担，而不是主 Agent 临时下场改代码。
5. 主 Agent 可以做：读取 Spec/Issue、维护任务状态、创建 worktree/branch、派发任务、查看 compact diff summary、决定接受/退回、合并/cherry-pick 已验收 commit、更新 issue/PR、查询 CI。
6. 主 Agent 默认**不做**：核心实现、算法修改、UI 大改、完整测试 campaign、性能 campaign、浏览器验收。它们全部委派。
7. 如果 subagent 发现 Spec 与现有 Canonical Authority 冲突，必须停止并回报；禁止为“完成 ticket”新增第二套 truth、降低 safety threshold、改变算法或 evaluator。
8. #70–#75 有明确 blocking chain。除 #75 内部验收 lanes 外，不要跨 blocker 并行实现后续 ticket。
9. 开发遵守 TDD：public seam 上 Red → Green，一次一个 vertical tracer bullet；不要先横向铺完所有 tests 或所有 backend/UI。
10. 所有 claim 必须有真实 test/evidence 支撑。不得用旧测试计数、旧 benchmark 或 developer 自述代替本 checkout 的验证。

---

## 1. 新对话启动流程

主 Agent 启动后只做 bootstrap，不写业务代码。

### 1.1 检查 GitHub 当前状态

确认：

- `main` HEAD；
- #69 是否仍 open；
- #70–#75 的 open/closed 状态与 blocker 是否变化；
- PR #76 是否已 merge。

当前 handoff 创建时：

- `main = 1c2b69acc52fdd8dfa515d38f86a679c0b4ef082`；
- #69 open；
- #70–#75 均为 `ready-for-agent`；
- #70 是 frontier；
- #76 是 design/spec PR。

若新对话看到状态已变化，以 GitHub 当前事实为准，不以本 handoff 的旧状态覆盖 GitHub。

### 1.2 建立实现 Integration Branch

规则：

- 如果 #76 已 merge：从最新 `main` 创建 `feature/sealed-run-replay`。
- 如果 #76 尚未 merge：不要修改 #76 的 spec branch；从 #76 HEAD 创建独立 `feature/sealed-run-replay`，使实现 worktree 内可读 normative docs。#76 merge 后，再把 integration branch rebase/merge 到最新 `main`。
- 不允许 implementation subagent 直接 commit 到 `main`、`spec/run-replay-evaluation` 或共享 integration branch。

### 1.3 主 Agent 必读顺序

只读，不修改：

1. GitHub #69 — parent Spec；
2. `docs/superpowers/specs/2026-09-11-sealed-run-replay-solution-pack.md`；
3. `...sealed-run-replay-spec.md`；
4. `...sealed-run-replay-prd.md`；
5. `...sealed-run-replay-ui-design.md`；
6. `...sealed-run-replay-technical-design.md`；
7. `docs/superpowers/plans/2026-09-11-sealed-run-replay-implementation.md`；
8. `...sealed-run-replay-verification.md`；
9. `CONTEXT.md`；
10. 当前 ticket issue body。

需要 repo 行为细节时，再按 ticket 范围读取代码。不要在主会话一开始扫描整个仓库。

---

## 2. Source of Truth 层级

发生冲突时按以下顺序裁决：

1. **#69 Sealed Run Replay Spec**；
2. #76 中的 Replay PRD / UI / Technical / Implementation / Verification docs；
3. 当前 child ticket (#70–#75) 的 Acceptance Criteria 与 Strict Contract；
4. `Design/Colav-Simulator-V1-PRD.md`、`UI-Spec`、`Implementation-Plan`；
5. `CONTEXT.md` domain glossary / canonical authority；
6. 与 feature 无冲突的现有代码行为与 tests。

若发现第 1–5 层之间存在真实矛盾：**STOP**。派一个 research/reconciliation subagent 给出矛盾证据和最小决策请求，不要私自解释成实现细节。

---

## 3. 本项目必须保持的语义边界

### 3.1 五个容易混淆的概念

必须始终使用以下术语：

- **Simulation Rate**：Active Session 实时仿真执行倍率；可能 compute-limited。
- **Live Presentation Buffer**：当前约 3 秒真实 telemetry 延迟/插值层；不是历史 Replay。
- **Reproduction / `ExperimentRunner.replay()`**：重新运行冻结 RunSpec 并验证复现；会执行 Simulator。
- **Historical AIS Replay**：历史世界执行模式；属于 Historical AIS benchmark domain。
- **Sealed Run Replay**：本 feature；读取已经记录的 Run evidence，**绝不运行 Simulator/Planner**。
- **Decision Replay**：离线诊断工具；“record once, interrogate offline”。本 feature 的 FULL visual Replay 应复用同一 full Decision Trace evidence。

### 3.2 核心不变量

- Replay 是 inspection，不是 intervention。
- Replay Speed 只推进 presentation playhead，不改变 Active Session。
- Browser 不是 Evidence Recorder。
- FULL visual Replay 使用完整逐 tick Decision Trace；`trajectory.parquet` 只是 reduced evidence。
- 连续运动可以在相邻 sealed frames 之间插值，但绝不 extrapolate。
- Planner/Risk/Lifecycle/Solve ID/Selected Command/Fallback/Event 等离散事实绝不插值或浏览器重算。
- Live 与 Replay 共享 Telemetry Projection / Situation Display 语义，不建第二个海图 renderer 或第二套风险解释器。
- Historical AIS Dataset/Case/Counterfactual/Qualification/Compare authority 保持不变；完成的 Historical AIS Run 进入同一个 shared player。
- Independent Evaluator、Threat Management、Encounter Lifecycle、L4 Plan Acceptance 的 authority 不因 Replay 改变。

---

## 4. 主 Agent / Subagent 组织模型

```text
User
  │
  ▼
MAIN ORCHESTRATOR
  │  owns: scope / blockers / dispatch / review decision / integration / tracker
  │
  ├── Ticket Implementer Subagent
  │      owns one #70-#74 tracer bullet end-to-end
  │
  ├── Independent Verifier Subagent
  │      verifies ticket AC + tests + no-contract-regression
  │
  ├── Repair Subagent (only when verifier rejects)
  │      fixes the exact rejected findings
  │
  └── Integration/Review Subagent (when merge/conflict is non-trivial)
         validates integration branch after accepted commit lands

#75 Final Acceptance:
MAIN ORCHESTRATOR
  ├── Degraded/Security verifier
  ├── Performance verifier
  ├── Browser/Mid-MPC no-reexecution verifier
  ├── Historical AIS verifier
  └── Full-regression verifier
```

### 4.1 主 Agent 的工作产品

主 Agent 只需要持续维护：

- 当前 frontier ticket；
- ticket state；
- subagent branch/worktree/commit；
- verifier verdict；
- integrated commit；
- blocker / unresolved decision；
- final release-gate state。

不要在主 Agent 的 scratchpad 中保存大量源码理解；源码理解属于 ticket subagent 的局部上下文。

---

## 5. Git / Worktree 策略

每个 implementation ticket 使用独立 worktree/branch：

```text
feature/sealed-run-replay              # integration branch; main agent owns
agent/replay-70-full-evidence           # #70 implementer
agent/replay-71-seek                    # #71 implementer
agent/replay-72-clock                   # #72 implementer
agent/replay-73-events                  # #73 implementer
agent/replay-74-evaluation-ia           # #74 implementer
agent/replay-75-acceptance-*            # #75 acceptance/repair lanes
```

规则：

1. ticket branch 总是从最新 integration branch 创建。
2. 一名 implementer 只负责一个 ticket；不得顺手实现 blocker 后面的 feature。
3. implementer 提交 atomic commits；commit message 要能映射 ticket。
4. verifier 在实现 branch 上验证，但默认不改代码。
5. verifier REJECT 时，创建 repair subagent；不要让 verifier 自己边审边大改。
6. ACCEPT 后由主 Agent将 commit merge/cherry-pick 到 integration branch。
7. 如果 merge conflict 需要语义判断，派 integration subagent；主 Agent只接受其最小 conflict report 和 resolved commit。
8. 每次 integration 后，从新的 integration HEAD 创建下一个 ticket branch。
9. 不允许后续 ticket 基于未验证的前 ticket implementation branch 开发。

建议整个 feature 使用一个 cumulative implementation PR：

```text
feature/sealed-run-replay -> main
```

#70 集成后即可开 Draft PR；#71–#75 持续追加，直到最终 acceptance。Spec PR #76 与 implementation PR 保持职责分离。

---

## 6. Ticket 状态机

主 Agent 对每个 child ticket 使用统一状态：

```text
READY
→ DISPATCHED
→ IMPLEMENTING
→ REVIEW_PENDING
→ VERIFYING
→ {REWORK | ACCEPTED}
→ INTEGRATED
→ EVIDENCE_RECORDED
```

进入 `EVIDENCE_RECORDED` 的最低条件：

- implementer commit(s) 可追踪；
- ticket AC 有 verifier verdict；
- focused tests 命令和结果记录；
- integration commit 已进入 feature branch；
- 关键 limitation/风险已写入 issue comment 或 evidence doc。

主 Agent可在 child ticket 真正完成后关闭 child issue；**不要在 #75 最终系统验收与 implementation merge 之前关闭 parent #69**。

---

## 7. Subagent 返回格式：控制上下文污染

所有 subagent 必须返回以下 compact report；不要把整段 diff/日志贴回主会话：

```text
TICKET: #NN
ROLE: implementer | verifier | repair | integration | acceptance
BRANCH/WORKTREE: ...
COMMITS: <sha list or none>
PUBLIC SEAM(S): A/B/C
BEHAVIOR DELIVERED/VERIFIED:
- ...
AC STATUS:
- passed: ...
- failed: ...
TESTS:
- command -> result
FILES/AREAS TOUCHED: high-level only
CONTRACT CHECKS:
- no second truth: PASS/FAIL
- no Replay Active Session mutation: PASS/FAIL/NA
- canonical authority preserved: PASS/FAIL
RISKS/LIMITATIONS:
- ...
VERDICT: ACCEPT | REJECT | BLOCKED
NEXT ACTION: ...
```

建议单个报告控制在约 800–1500 字；详细 logs 写入 repository evidence 或 GitHub issue comment，并只回传链接/path。

---

## 8. Approved Test Seams

#69 已冻结三类 public seams；未经用户/Spec 决策不要扩张：

### Seam A — Replay Service/API

验证：

- replay descriptor；
- full/reduced/incomplete/unavailable evidence state；
- bounded time window；
- canonical events；
- Run ID/path confinement；
- read-only；
- integrity/schema failure。

### Seam B — Replay Controller / ReplayClock

验证：

- direct seek；
- play/pause/end/restart；
- 0.25/0.5/1/2/5/10/20× presentation speed；
- buffering/prefetch；
- race cancellation；
- no extrapolation；
- shortest-angle interpolation；
- discrete facts source-frame semantics。

### Seam C — Product Browser Replay

验证：

- Evaluation > Replay；
- shared Situation Display；
- timeline/events/inspection；
- Historical AIS shared player；
- Simulation Rate vs Replay Speed terminology；
- accessibility/responsive states；
- **zero Replay-induced session mutation calls**。

Tests 要断言 external behavior，不断言 private helper、gzip offset、cache shape 或 CSS class。

---

## 9. Ticket-by-Ticket Dispatch Plan

### #70 — FULL replay-ready normal product Runs

**Implementer profile:** backend/evidence/API engineer。  
**Goal:** 普通 Config/API Active Session 自动写 full Decision Trace；Replay readiness 独立于 execution/result readiness；能返回 Replay Descriptor。  
**Must preserve:** existing Decision Replay `TraceBundle`/probes compatibility。  
**Verifier focus:** browser disconnect 不丢 trace；READY 只在 durable finalize/integrity 后；legacy truthfully REDUCED；result pending 与 replay ready 分离。  
**Do not implement:** seek/play/timeline full UI。

主 Agent dispatch 后不要自己研究 writer internals；让 implementer 阅读 #70 + Technical Design + Decision Replay recorder/bundle。

### #71 — Direct seek + shared Situation Display

**Blocked by:** #70 integrated。  
**Implementer profile:** full-stack replay/API/UI engineer。  
**Goal:** Run ID + arbitrary sim time → bounded frame bracket → Telemetry Projection → existing Situation Display；paused manual seek。  
**Verifier focus:** late direct seek 不从 0 顺序执行；A→B rapid seek race；zero Active Session mutation；exact source-frame Live/Replay projection parity。  
**Do not implement:** automatic playback clock。

### #72 — ReplayClock / Play / Pause / Replay Speed

**Blocked by:** #71 integrated。  
**Implementer profile:** frontend state-machine/timing engineer。  
**Goal:** independent ReplayClock；0.25–20×；buffer/prefetch；pure kinematic interpolation。  
**Verifier focus:** deterministic fake clock；359°→1° shortest path；missing upper bracket → BUFFERING, not extrapolation；solver count unchanged。  
**Do not conflate:** live telemetry buffer adaptive delay/rate semantics。

### #73 — Event-synchronized Replay Timeline

**Blocked by:** #72 integrated。  
**Implementer profile:** UI/evidence timeline engineer。  
**Goal:** canonical event journal markers；Prev/Next Event；Inspection Context。  
**Verifier focus:** event identity/time/order来自 evidence；dense aggregation 不丢 event；high-speed replay event completeness；keyboard navigation。  
**Forbidden:** browser diff frames 生成第二套 Operational Events。

### #74 — Evaluation IA + Historical AIS shared player

**Blocked by:** #73 integrated。  
**Implementer profile:** OpenBridge/UI architecture + full-stack integration engineer。  
**Goal:** `Replay | Results | Evidence | Historical AIS`；Historical AIS 原 authority 全部保留；Historical AIS Run 用 shared player；Deployment 术语改为 Simulation Rate。  
**Verifier focus:** `Open in Deployment` = execute；`Open Replay` = inspect；Historical AIS 无第二个 ReplayClock/player；1920×1080/1440×900；OpenBridge reuse；zero inspection mutation。

### #75 — System Acceptance

**Blocked by:** #74 integrated。  
**不是普通实现 ticket。** 主 Agent 应并行派多个 acceptance subagents，最后聚合结果。

建议 lanes：

1. **Degraded + Security Agent**：REDUCED/INCOMPLETE/UNAVAILABLE、trusted prefix、path traversal、malformed Run ID、oversized window、read-only。
2. **Performance Agent**：VO/Fan-MPC/Mid-MPC capture overhead；~600s trace descriptor/open/random seeks；memory/cache；presentation timing。
3. **Mid-MPC Browser Agent**：普通产品路径只运行一次 Mid-MPC；early/mid/late direct seek；1×/5×/10×/20×；network trace + solver counter 证明 Replay 无 re-execution。
4. **Historical AIS Agent**：至少一个 Historical AIS Run 使用 shared player且 benchmark state 不变；若 source 环境不可用则产出精确 blocker/evidence。
5. **Regression Agent**：full backend tests、full current frontend suite、ruff、diff check、CI；记录真实 counts/failures。

Acceptance findings 若需要代码修复，由主 Agent派 repair subagent。修复后只重跑受影响 focused suite + #75 必要 acceptance lanes，再执行最终 full regression。

---

## 10. 主 Agent 的审查清单

每次 verifier 返回 ACCEPT 后，主 Agent只检查以下内容：

- ticket AC 是否全部有证据；
- implementation 是否越界实现后续 ticket；
- 是否新建第二套 risk/planner/event truth；
- 是否误把 `ExperimentRunner.replay()` 当 Visual Replay；
- 是否让 browser 直接解析任意 raw artifact；
- 是否 Replay 调用 Active Session speed/step/start/pause/reset/create；
- 是否对 reduced evidence 推断/补造 planner/risk facts；
- 是否改变 Safety/COLREG/Evaluator/Mid-MPC equations 为 Replay 服务；
- 是否仍能被 Decision Replay 读取；
- 是否把 Detailed logs/evidence 留在 repo/issue 而非只存在 subagent 上下文。

任何一项失败，退回 repair subagent。

---

## 11. 测试执行原则

### 11.1 每 ticket

- implementer：focused Red → Green tests；
- verifier：从 public seam 独立重跑 focused tests + ticket regression；
- integration verifier：必要时检查 integration HEAD。

### 11.2 Repo baseline gates

当前 CI 的 canonical backend gates 是：

```text
uv run ruff check .
uv run pytest -v tests
```

前端测试命令应由 subagent从当前 repository test layout 中解析并记录；**不要使用旧提交中的测试数量作为当前通过依据**。

### 11.3 最终 #75

必须在同一实现 checkout 上记录：

- focused backend replay suites；
- focused frontend Replay/Evaluation/Historical AIS suites；
- full `uv run pytest -v tests`；
- `uv run ruff check .`；
- current full frontend test command；
- `git diff --check`；
- real browser acceptance；
- real Mid-MPC no-reexecution proof。

已知 unrelated failure 必须如实列出；不得改成 PASS 或删除测试。

---

## 12. 最终验收必须证明的核心事实

功能只有在 #75 证明以下事实后才能称为完成：

1. 一个 normal product Mid-MPC Run **只执行一次**。
2. 该 Run 生成 FULL replay evidence，现有 Decision Replay 也能读取。
3. Replay 可 direct seek 到早/中/晚时间，不逐步执行中间 Simulator ticks。
4. 同一个 Run 可按 1×/5×/10×/20× presentation speed 播放；速度不受原 Mid-MPC solver throughput 限制。
5. Replay 网络请求中没有 Replay 导致的 session create/start/resume/pause/step/speed/reset/replacement。
6. Replay 前后稳定 solver-execution counter 不因 Replay 增加。
7. source-frame parity 证明 Replay 是 recorded truth 的 projection。
8. legacy/reduced/truncated/corrupt evidence 都 fail closed / degrade honestly。
9. Historical AIS 使用同一个 player，不出现第二套 Replay implementation。
10. Evaluation 工作面完成 `Replay | Results | Evidence | Historical AIS` IA。
11. Deployment 显示 Simulation Rate；Evaluation 显示 Replay Speed。
12. full regressions、security、accessibility、performance evidence 全部记录。

---

## 13. 何时必须升级给用户，而不是继续实现

出现以下任一情况，主 Agent停止当前 ticket并向用户提出最小决策问题：

- Spec 与 Encounter Lifecycle / Threat Management / L4 / Evaluator authority 冲突；
- 需要改变 Mid-MPC/VO/Fan-MPC 算法逻辑才能完成 Replay；
- 需要降低 safety/evaluation threshold；
- 需要让 Replay re-run Simulator 来修复缺失 evidence；
- 现有 Decision Trace 无法满足性能，需要破坏兼容性的新格式；
- Historical AIS contract 必须改变才能进入 shared player；
- 需要新增第四个以上 public test seam；
- #75 无法证明 zero re-execution，且原因不是单纯 test instrumentation bug。

对于普通技术不确定性，先派 research subagent，不要直接占用主上下文深挖。

---

## 14. 新对话主 Agent 的首个任务清单

启动后依次执行：

1. 读取本 handoff 全文。
2. 查询 main/#69/#70–#75/#76 当前状态。
3. 建立/确认 `feature/sealed-run-replay` integration branch/worktree。
4. 读取 #69 Solution Pack + #70。
5. 创建一个简短 Task Ledger：`#70 READY; #71 blocked; ...`。
6. **立即派发 #70 implementation subagent。**
7. 主 Agent在等待 #70 时不要自己实现；可以只准备 verifier prompt、查询 GitHub 状态或整理验收 ledger。
8. #70 implementer返回后，派独立 verifier。
9. verifier ACCEPT → integrate；REJECT → repair subagent。
10. 更新 #70 issue evidence；进入 #71。

---

## 15. Copy/Paste Prompt — 新对话直接使用

将下面整段作为新开发对话第一条指令：

```text
你是 Colav-Simulator 的 Sealed Run Replay 开发 Orchestrator。

首先完整读取：
- handoff/2026-09-11-sealed-run-replay-orchestrator-handoff.md
- GitHub #69
- #69 链接的 Solution Pack / PRD / UI Design / Technical Design / Implementation / Verification docs
- CONTEXT.md

然后查询 GitHub 当前 main、#69、#70-#75、PR #76 状态。

工作方式是硬约束：
1. 主 Agent 只负责任务中心、blocker、subagent 调度、验收决策、Git 集成、Issue/PR 更新；不要亲自承担大段代码实现，避免污染主上下文。
2. #70→#71→#72→#73→#74→#75 按 blocker 顺序执行。每个 ticket 使用独立 worktree/branch，由一个 implementation subagent 端到端完成 vertical slice。
3. 每个实现完成后必须派独立 verifier subagent；REJECT 时派 repair subagent，主 Agent不要自己修。
4. non-trivial merge/conflict 派 integration subagent。
5. subagent 只能返回 handoff 中规定的 compact report；详细 logs/evidence 写 repo 或 GitHub，不要把长日志/完整 diff灌入主上下文。
6. Approved test seams 只有 Replay Service/API、Replay Controller/Clock、Product Browser Replay。遵守 TDD Red→Green 和 canonical authority。
7. Sealed Run Replay 绝不能调用 Simulator/Planner 来回放；FULL evidence 复用 Decision Trace；trajectory.parquet 只能 REDUCED；Live/Replay 共享 Telemetry Projection/Situation Display；Historical AIS 不建第二个 player。
8. Deployment = Simulation Rate；Historical player = Replay Speed。
9. 如果发现 Spec 与 Threat Management/Encounter Lifecycle/L4/Independent Evaluator 冲突，停止并上报，不要新增第二 truth 或降低 gate。
10. 最终只有 #75 的真实 Mid-MPC no-reexecution + full regression/性能/security/browser evidence 全部通过，才可以宣称功能完成。

现在不要写业务代码。先完成 bootstrap、输出 Task Ledger，然后派发 #70 implementation subagent。
```

---

## 16. Ticket Implementer Prompt Template

主 Agent派每个实现 subagent时使用：

```text
You own exactly GitHub ticket #<NN> for Colav-Simulator Sealed Run Replay.

Read in order:
1. #<NN> full issue body
2. parent #69
3. relevant sections of sealed-run-replay Technical/UI/Implementation/Verification docs
4. CONTEXT.md
5. only then inspect code needed for this ticket

Work on your dedicated branch/worktree. Do not modify shared integration/main/spec branches.
Follow public-seam TDD Red→Green and deliver this ticket end-to-end. Do not implement future blocked tickets.
Preserve canonical authorities and the strict Replay invariants.
Commit your work atomically.

Return ONLY the compact subagent report format defined in the handoff. Put detailed evidence/logs in repo or the ticket comment.
```

---

## 17. Verifier Prompt Template

```text
You are the independent verifier for GitHub ticket #<NN>.

Do not assume the implementer's claims are correct. Read #<NN>, parent #69, the relevant normative design docs, and inspect the implementation branch.
Verify every Acceptance Criterion at public seams. Run the focused tests yourself. Check contract regressions and scope creep.
Do not make product changes unless explicitly converted into a repair task.

Return the compact report with VERDICT = ACCEPT / REJECT / BLOCKED and list exact failed ACs/tests. Store long logs as issue/repo evidence.
```

---

## 18. Repair Prompt Template

```text
You are a repair subagent for ticket #<NN>.
The independent verifier rejected these exact findings: <findings>.

Fix only the rejected behavior while preserving already-passing Acceptance Criteria and #69 invariants. Add/adjust public-seam regression tests first where applicable. Do not expand scope.
Commit the repair separately and return the compact handoff report.
```

---

## 19. Final Completion / Handoff-out

当 #75 验收通过后，主 Agent应生成新的 final handoff，至少包含：

- final integration commit / implementation PR；
- #70–#75 integrated commits；
- reference Mid-MPC Run ID / exact tuple；
- replay trace schema/digests；
- zero-reexecution proof location；
- frame parity evidence；
- performance evidence；
- degraded/security evidence；
- Historical AIS shared-player evidence；
- exact full test commands/results；
- remaining limitations；
- user-visible UI changes；
- whether #69 can be closed。

在这些证据之前，不要输出“全部完成”“fully validated”等结论。
