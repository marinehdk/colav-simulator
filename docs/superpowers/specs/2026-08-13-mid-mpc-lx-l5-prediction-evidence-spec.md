# Deepen Mid-MPC LX/L5 Prediction Evidence

## Problem Statement

Mid-MPC已经具备冻结的Python CasADi/IPOPT core、Encounter Lifecycle、Problem Assembler和严格L4 Plan Acceptance。Playground能够显示真实81点、80×15s、1200s预测轨迹，但预测、验收和执行证据仍分散在solver result、free-form algorithm details、PlannerTrace、post-commit artifact reference、server cache和GUI cache中。

当前问题不是“有没有轨迹”，而是无法稳定回答以下问题：

- 地图折线来自本次真实IPOPT primal、上次accepted plan、held plan，还是旧GUI缓存。
- 81个state knots、80个optimization intervals及当前真实执行插值分别代表什么。
- 哪些目标进入NLP、哪些目标被L4独立复核、哪些目标未进入graph，以及预测属于哪个TrackKey generation。
- L4 PASS、Adapter最终commit、Accepted Plan Receipt、artifact COMPLETE和当前command之间的因果关系。
- 最新rejected attempt与当前active plan如何同时展示，且不把历史轨迹误认为可执行计划。
- 8192-byte inline截断后是否仍保留mandatory failure和最差安全witness。
- artifact异步完成或失败后，为什么不能原位改变既有semantic verdict或执行authority。
- 相同证据能否按schema、canonicalizer、hash、lineage、数值、L4和runtime timeline分层复验。

这些缺口已经产生具体可观察问题：GUI曾显示旧90s式预测语义、目标预测字段存在`north/east`与`x/y`错配、Mid objective和真实trajectory provenance不清晰、hold显示完整旧轨迹而非当前active suffix、post-commit worker原位更新共享reference、早期Adapter失败没有完整terminal trace。

Candidate4必须深化LX/L5 Prediction Evidence，但不能借重构改变Mid-MPC方程、IPOPT结果、Lifecycle职责、L4 verdict、hold插值、执行command、fallback政策或capability claim。基线已有7个严格L4闭环失败，必须如实保留，另行处理算法/L4能力缺陷。

## Solution

建立一个有界、Mid-MPC专属的deep Prediction Evidence module。模块把稳定语义事实、运行发生事件和消费投影分开：

- Immutable Semantic Record保存prediction grid、81个本船state knots、80个optimization interval references、TrackKey purpose predictions、solver evidence、L4 Acceptance Certificate及semantic hash lineage。
- Append-only Occurrence Events从Adapter入口覆盖cycle、input validation、attempt、solve、L4、commit、hold、replan、command、artifact、reset及terminal control outcome。
- Pure Reducer成为唯一authority timeline解释器，机械生成bounded inline projection、full artifact view和PredictionRenderSnapshot。

Facade在L4后生成semantic candidate和Acceptance Certificate。Custom MPC Adapter只通过optional algorithm-neutral EvidenceEnvelope接收证据，唯一生成Accepted Plan Receipt及runtime events，并在最终deadline/freshness检查后原子提交receipt与command。Artifact worker只处理immutable descriptor，通过bounded completion channel返回结果；不能修改Adapter、trace或已返回对象。

本船预测契约固定为80个15s区间、81个state knots、1200s。knot 0为当前实测状态，interval k的航向/航速参考作用于`[t_k,t_{k+1})`并生成knot k+1。当前held command继续使用既有相邻控制列线性插值，Evidence同时记录optimization interval reference与runtime applied reference，绝不在Candidate4改为ZOH。

目标证据使用`TrackKey(target_id,generation)`，分别记录NLP selected prediction与L4 all-relevant safety prediction。未进NLP的relevant目标保留admission/exclusion和L4 coverage，不得静默消失。相同purpose输入可以按content hash reconcile；L3和L4仍保持独立复核。

Public verifier提供V0 bytes/digest、V1 schema/canonicalizer、V2 lineage/event causality、V3 numerical replay、V4 L4 replay、V5 projection replay、V6 runtime authority replay。V7 IPOPT re-solve仅为diagnostic，不改原始verdict。V1不引入数字签名、可信密钥或attestation，不声明来源真实性。

Evidence critical tail中的typed validation、canonical hash、inline projection、event append、freshness、receipt/command atomic commit同步计入现有20s总deadline。gzip、write、retention、completion report及V7 re-solve异步有界。现有250ms reservation不是Candidate4常量，必须在相同目标环境针对0/1/16目标及fresh/hold/rejected状态各1000次测量combined tail后重校准。

GUI只消费PredictionRenderSnapshot：默认画active suffix teal solid；失效历史grey dashed；rejected默认隐藏，开启后red dashed；execution cursor按elapsed线性插值；Planner L4与Evaluator G3分栏。GUI不保存第二份active/latest authority，也不重新判断安全或COLREG。

## User Stories

1. As a simulator operator, I want to know whether a displayed trajectory came from a fresh IPOPT solve, a held accepted plan, or history, so that I do not mistake stale geometry for current authority.
2. As a simulator operator, I want the active suffix to begin at the current elapsed point, so that already executed segments are not shown as future commands.
3. As a simulator operator, I want latest rejected attempts visible separately from the active plan, so that failures are not hidden by previous success.
4. As a simulator operator, I want invalid history visibly non-executable, so that a grey audit trace cannot be mistaken for a fallback plan.
5. As a simulator operator, I want rejected trajectories hidden by default and available through an explicit toggle, so that diagnostics do not clutter normal operation.
6. As a simulator operator, I want Planner L4 and Evaluator G3 evidence separated, so that post-run scoring cannot certify the planner that produced the command.
7. As a simulator operator, I want the display to state 80 intervals, 81 state samples, 15s step and 1200s horizon, so that the forecast is not mistaken for the former 90s visualization.
8. As a simulator operator, I want straightness, course span, speed span and lateral deviation shown as evidence, so that a genuine near-linear optimum is distinguishable from a rendering defect.
9. As an MPC developer, I want every ownship knot linked to its raw primal source, so that the plotted trajectory can be reproduced from the actual IPOPT result.
10. As an MPC developer, I want interval references separated from state knots, so that 80 controls are never mislabeled as 81 controls.
11. As an MPC developer, I want knot 0 identified as the current measured state, so that it is not presented as an optimized future sample.
12. As an MPC developer, I want terminal knot 80 marked as having no new control, so that horizon indexing remains exact.
13. As an Adapter developer, I want runtime applied reference recorded independently from optimization interval reference, so that held execution remains truthful.
14. As an Adapter developer, I want Candidate4 to preserve current linear hold interpolation, so that evidence work does not change commands.
15. As a target-tracking developer, I want target identity bound to target ID and generation, so that reused IDs cannot join unrelated trajectories.
16. As a target-tracking developer, I want observation time, reference time, covariance, health and source preserved, so that prediction quality can be audited.
17. As a multi-target operator, I want every relevant contact listed even when it does not enter the frozen NLP graph, so that excluded threats do not disappear.
18. As a multi-target operator, I want NLP-selected and L4-safety predictions labeled by purpose, so that their coverage is never conflated.
19. As a safety reviewer, I want selected-target predictions reconciled when they claim the same model, grid and reference, so that silent prediction drift is detected.
20. As a safety reviewer, I want missing mandatory L4 targets to fail closed, so that incomplete evidence cannot be displayed as PASS.
21. As an evidence reviewer, I want a stable semantic record that never changes after creation, so that its hash remains meaningful.
22. As an evidence reviewer, I want dispatch, hold and artifact completion represented as separate events, so that runtime status cannot rewrite semantic facts.
23. As an evidence reviewer, I want content identity separate from occurrence identity, so that identical solves in two runs remain independently auditable.
24. As an evidence reviewer, I want each event identified by run, epoch and monotonic sequence, so that reset and duplicate delivery are mechanically detectable.
25. As an evidence reviewer, I want `caused_by` and `derived_from` links, so that attempt, candidate, Certificate, Receipt and command form an explicit lineage.
26. As an evidence reviewer, I want one deterministic reducer, so that API, artifact and GUI cannot disagree about active/latest/history state.
27. As an evidence reviewer, I want every planning cycle to have one terminal control outcome, so that early failures and hold-before-first are not invisible.
28. As an evidence reviewer, I want reset to start a new evidence epoch and invalidate old events, so that pre-reset authority cannot leak forward.
29. As a safety engineer, I want Acceptance Certificate distinct from Accepted Plan Receipt, so that L4 PASS is not mistaken for successful dispatch.
30. As a realtime engineer, I want receipt and command committed atomically after final checks, so that they cannot expose contradictory states.
31. As a realtime engineer, I want pre-commit evidence failure to produce no command, so that an unverifiable transaction cannot become active.
32. As a realtime engineer, I want post-commit persistence failure to preserve the command but lower the evidence claim, so that disk faults do not rewrite control history.
33. As an operations engineer, I want artifact queues bounded by item and byte capacity, so that long simulations cannot grow memory without limit.
34. As an operations engineer, I want shutdown to drain or produce terminal INCOMPLETE evidence, so that queued work is never silently abandoned.
35. As an operations engineer, I want workers to return immutable completion values, so that cross-thread mutation cannot change an already returned trace.
36. As an API consumer, I want full artifact, inline and render views mechanically derived from one source, so that payload size does not create alternate truths.
37. As an API consumer, I want inline evidence capped at 8192 canonical UTF-8 bytes, so that response size remains bounded.
38. As an API consumer, I want identity, verdict, artifact reference and truncation counters retained first, so that the summary remains interpretable.
39. As an API consumer, I want mandatory failures retained before advisory details, so that truncation cannot hide why a plan failed.
40. As an API consumer, I want the worst safety witness retained before PASS details, so that the most consequential evidence survives capacity pressure.
41. As a replay developer, I want artifacts to declare schema and canonicalizer, so that old records are verified by their original encoding rules.
42. As a replay developer, I want unsupported schemas to return a typed failure, so that a verifier never guesses a new interpretation.
43. As a replay developer, I want old semantic hashes frozen, so that upgrades produce derived records instead of rewriting history.
44. As a replay developer, I want deterministic V0-V6 verification, so that structural, semantic, numerical and authority claims are independently reportable.
45. As a numerical engineer, I want IPOPT re-solve classified as diagnostic, so that version differences do not invalidate intact historical evidence.
46. As a security reviewer, I want hash integrity clearly separated from source authenticity, so that unsigned evidence is not presented as attested.
47. As a compatibility maintainer, I want Mid-MPC Evidence added through an optional generic envelope, so that other planners need no migration.
48. As a compatibility maintainer, I want Mid PlannerTrace 1.1 additive and other algorithms unchanged at 1.0, so that old clients continue working.
49. As a compatibility maintainer, I want legacy fields retained during Candidate4, so that evidence adoption does not become a breaking Trace 2.0 migration.
50. As a VO, Fan-MPC or Nominal user, I want identical behavior and GUI output, so that Mid-specific evidence work has no cross-algorithm blast.
51. As a performance engineer, I want canonicalization, hashing, projection and commit included in the measured critical tail, so that solver-only timing does not hide overhead.
52. As a performance engineer, I want 0/1/16-target fresh, hold and rejected cases benchmarked, so that reservation covers realistic tails.
53. As a performance engineer, I want the total deadline fixed at 20s, so that overhead is optimized rather than hidden by a relaxed policy.
54. As a test engineer, I want exact discrete/hash/event/command comparisons and quantity-specific numeric tolerances, so that Evidence changes prove non-interference.
55. As a test engineer, I want duplicate, out-of-order, missing-parent, schema, capacity, slow-disk and reset failures injected, so that failure boundaries are executable.
56. As a test engineer, I want REST, WebSocket and browser rendering tested after reconnect, so that the reducer remains the only authority.
57. As a test engineer, I want a real port-8010 Mid planner event, so that HTTP success alone cannot claim runtime validation.
58. As a capability maintainer, I want Candidate4 to preserve the existing seven strict-L4 failure families, so that evidence work cannot fabricate scenario PASS.
59. As a capability maintainer, I want no capability promotion from better visibility alone, so that evidence depth is not confused with algorithm performance.
60. As a repository maintainer, I want vertical TDD through the highest public seams, so that implementation stays reviewable and regressions localize to contracts.

## Implementation Decisions

- Build a Mid-MPC-specific deep Prediction Evidence module. It owns immutable semantic models, occurrence events, deterministic reducer, canonicalization, projections and public verification.
- Keep Lifecycle, Problem Assembler, IPOPT solver and L4 Plan Acceptance as upstream authorities. Prediction Evidence records their outputs and never repeats their decisions.
- Use an optional algorithm-neutral EvidenceEnvelope on the existing normalized solution interface. The generic Adapter may process identity, transaction, artifact and timeline fields but cannot inspect Mid-specific trajectory or COLREG fields.
- Assign stable ownership: Facade creates semantic candidate and Acceptance Certificate; Adapter creates Accepted Plan Receipt and runtime events; sink persists; API and GUI consume projections.
- Separate immutable Semantic Record from append-only Occurrence Events. Event reduction is pure and deterministic.
- Use occurrence identity `(run_id, evidence_epoch, event_seq)`. Use independent versioned SHA-256 semantic hashes for candidate, Certificate, Receipt and evidence root.
- Join occurrence and semantic graphs with typed `caused_by` and `derived_from` links. Never use content hash as occurrence identity.
- Start evidence capture at Adapter cycle entry with a minimal CYCLE_STARTED event. Add INPUT_VALIDATED only after typed input validation. Every cycle must end in exactly one terminal control outcome.
- On terminal solve or replan failure, clear active receipt, active solution and warm state under existing fail-stop behavior. Artifact failure lowers evidence completeness but does not change control verdict.
- Define PredictionGrid as 80 intervals, 81 state knots, 15s step and 1200s duration.
- Represent knot 0 as the measured ownship state; knots 1..80 as solver-integrated endpoints. Represent 80 optimization references separately and mark no control at the terminal knot.
- Preserve the existing linear interpolation policy for held runtime commands. Record elapsed time and runtime applied reference separately from OCP references.
- Use canonical position fields `north_m` and `east_m`; retain `x/y` only as legacy aliases outside the new authority schema.
- Use SI units and radians. Heading zero is north and positive clockwise under the current NE/body transform.
- Represent target identity with TrackKey `(target_id,generation)`. Store observation/reference time, state/covariance, geometry, health, source, Lifecycle authority, admission and purpose predictions.
- Record NLP predictions for selected targets and independent L4_SAFETY predictions for every relevant target. Preserve exclusions and reconcile equal-purpose inputs by content hash.
- Keep full Acceptance Certificate and post-commit Receipt separate. Project both into bounded inline and render models without inventing a new verdict.
- Build inline evidence by deterministic priority: Tier0 identity/verdict/artifact/truncation; Tier1 mandatory failures; Tier2 worst safety; advisory and PASS details truncate first.
- If Tier0 plus Tier1 exceeds 8192 bytes, return typed INLINE_CAPACITY_EXCEEDED and full artifact reference. Never silently emit PASS after mandatory witness loss.
- Add versioned evidence and render schemas. Freeze existing Request-to-Receipt hash encoders. Use `colav.python-json@1` for the new schema and do not claim RFC 8785 compatibility.
- Reject NaN and infinity. Freeze finite float, negative zero, enum, optional, ordered-target and UTF-8 rules in the canonicalizer contract.
- Verify old artifacts using their declared schema/canonicalizer. Upgrades produce new records linked through `derived_from`; they never rewrite old hashes.
- Expose one public verifier with V0 bytes/digest, V1 schema/canonicalizer, V2 lineage, V3 numerical, V4 L4, V5 projection, V6 runtime authority and optional V7 IPOPT diagnostic re-solve.
- Limit verifier claims to integrity, semantic replay and numerical replay. Digital signatures, trusted identity, attestation and non-repudiation remain outside V1.
- Persist one canonical full artifact per terminal attempt. Hold and command events remain small append-only records.
- Separate immutable ArtifactDescriptor from ArtifactStatusEvent. Workers write bounded completion queues; only the simulation/runner thread assigns event sequence and reduces completion events.
- Keep validation, canonical hash, inline projection, event append, freshness and atomic receipt/command commit synchronous inside the existing 20s deadline.
- Keep compression, file writing, retention, completion reporting and V7 re-solve asynchronous and bounded.
- Rebenchmark the combined critical tail with 1000 samples for 0/1/16 targets across fresh, hold and rejected states. Recalculate reservation from reviewed p50/p95/p99/max; do not raise the 20s total deadline.
- Derive PredictionRenderSnapshot only from the reducer. Include active suffix, latest attempt, invalid history, optional rejected candidates, target alignment, execution cursor, grid/provenance, straightness metrics and separate Planner/Evaluator sections.
- Render active suffix as teal solid, invalid history grey dashed and optionally displayed rejected path red dashed. GUI performs coordinate projection and styling only.
- Add Prediction Evidence as PlannerTrace 1.1 optional data. Keep algorithms without Evidence at 1.0 and preserve every legacy field during Candidate4.
- Keep exact numerical and behavioral non-interference: objective absolute tolerance 1e-5; trajectory/raw/diagnostic absolute tolerance 1e-6; existing scale-aware CPA checks; discrete identities, hashes, event topology and commands exact.
- Keep existing seven closed-loop failures at the same failure families. Candidate4 cannot modify L4 thresholds, add scenario branches, add fallback, force PASS or promote capability.

## Testing Decisions

- Prefer the highest pure seam: construct Semantic Records and Occurrence Events, then verify reducer, canonical bytes, projections and V0-V6 results through public module operations.
- Use the public Adapter planning seam for cycle start, early validation failure, fresh solve, hold, stale replan, final deadline, atomic commit, reset, fail-stop and no-fallback behavior.
- Use existing real-IPOPT harnesses for numerical non-interference and HO/CS/OT/multiship baseline delta. Do not create fake solver success for runtime acceptance.
- Use REST, WebSocket and browser seams for active suffix, latest rejection, target prediction alignment, reconnect/reset and Planner/Evaluator separation.
- Use a real port-8010 session event after checking listener PID and cwd. HTTP 200 without a Mid planner event is insufficient.
- V1 Pure Contracts covers deep immutability, finite numbers, grid boundaries, TrackKey, canonical golden bytes and schema failures.
- V2 Timeline covers every transition, exactly-one terminal outcome, reset epoch, duplicate, missing parent and out-of-order events with property tests.
- V3 Public Replay covers valid and tampered artifact corpora across V0-V7, including explicit unsupported schema and diagnostic-only re-solve.
- V4 Adapter Transaction injects failures before and after validation, solve, L4, final freshness, commit callback and artifact submission; asserts no partial authority leakage.
- V5 Numerical Non-interference preserves the eight frozen C++ parity records and compares prepared/raw/objective/trajectory/L4/command using frozen exact/tolerance rules.
- V6 Closed-loop Delta reruns HO, CS give-way, CS stand-on, overtaking, overtaken, overtaking port corridor and multiship; failure count and failure families cannot expand, shrink or change.
- V7 API/GUI covers REST and WebSocket payloads, reconnect, reset, elapsed cursor, active suffix, rejected toggle, provenance, straightness and desktop/mobile rendering.
- V8 Compatibility proves VO, Fan-MPC and Nominal behavior, trace and GUI remain unchanged without an EvidenceEnvelope.
- V9 Performance runs 1000 samples per 0/1/16 target and fresh/hold/rejected case, reports p50/p95/p99/max, queue/RSS bounds and resulting reservation.
- V10 Live 8010 proves requested/executed algorithm identity, real CasADi/IPOPT execution, Receipt, evidence hash, active/latest state and `fallback_used=false`.
- V11 Full Regression requires all new tests green, scoped lint/format and diff checks green, and repository results reported against the frozen baseline rather than falsely called fully green.
- Existing focused baseline is 90 passed. Existing closed-loop baseline is seven failures: four SAFETY_SWEPT_CLEARANCE and three COLREG_STAND_ON_DRIFT. These are acceptance invariants for this refactor, not desired algorithm outcomes.

## Out of Scope

- Modifying the frozen MASS-derived NLP equations, objective, row topology, horizon, IPOPT backend or parity fixtures.
- Changing the current held-command linear interpolation to ZOH or another execution policy.
- Repairing the seven existing strict-L4 HO/CS/OT/multiship failures.
- Relaxing L4 clearance, stand-on, COLREG, trackability, deadline or freshness gates.
- Adding fallback controllers, retries, forced PASS, scenario-ID branches or cached-command continuation after fail-stop.
- Reclassifying encounters, choosing passing side, changing commitment/release or importing another COLREG FSM.
- Promoting Mid-MPC capability because evidence or GUI visibility improved.
- Building a generic event-sourced platform for VO, Fan-MPC, Nominal or all planners.
- Replacing PlannerTrace with a breaking 2.0 schema or removing legacy fields.
- Making a unified dense prediction tensor the canonical public schema.
- Requiring full artifact persistence before command dispatch.
- Deferring Receipt, semantic hash or authority events until after command dispatch.
- Digital signatures, trusted keys, source authentication, attestation and non-repudiation.
- Claiming IPOPT bit-exact behavior across platforms or patch versions.
- Porting Candidate4 into MASS-L3 or claiming MASS-L3 system acceptance.

## Further Notes

- Authoritative design input is the accepted Mid-MPC LX/L5 Prediction Evidence solution pack and its decision log.
- Frozen implementation base is `b95851215fb9afab1e019e383687fe533ce6d6bb`.
- Implementation must use vertical TDD slices and preserve unrelated dirty files and listeners.
- Any new contradiction against final decisions or technical specifications stops implementation and returns the affected decision point to design-grounding.
- Candidate4 completion means prediction and execution evidence becomes observable, attributable and replayable. It does not mean all Playground scenarios pass.
