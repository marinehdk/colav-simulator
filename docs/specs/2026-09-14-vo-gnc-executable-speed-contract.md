## Problem Statement

用户选择 Original GNC，在无环境作用的超越场景中，任务/VO持续请求8m/s，而GNC实际速度设定常为3.2m/s。用户无法判断这是规划决策、正常控制滞后，还是未公开的执行限制；以原请求速度评估的避碰预测也不能自动代表最终执行行为。

诊断已通过真实原生GNC最小输入复现：初速8m/s、直线航线、无环境、无尖角，manager对cruise、avoidance、emergency_avoidance三组均接纳8m/s且路线限速为8m/s；导引分别输出8、3.2、3.2m/s。普通避碰与紧急避碰航点均编码为6。普通避碰重复运行给出相同结果。该RED是产品期望与冻结策略之间的差异，不是原版移植数值保真失败。

另外，VO速度能力窗口依赖自身遇险状态和实际TCPA门，而GNC限速依赖执行航点模式。实际航速反馈虽存在，但无法代替模式、有效速度上限及生效原因的合同。旧路线尖角累积与动态约束模式误判已另行修复，本规格不以那两项修复代替速度合同闭合。

## Solution

建立一份由GNC执行侧提供、VO规划前消费、执行后可核对的速度合同。用户应能看到任务速度、规划请求、接纳上限、最终控制设定和实际速度，以及每次限制的来源与解除条件。

采用顺序实施：

1. **阶段A：在当前冻结原版上闭合合同。** 诚实报告普通避碰当前上限3.2m/s；VO不能仅因TCPA门开启就重新选择执行侧禁止的高速。若当前能力无法在既定工况完成超越，明确显示能力/任务不匹配。此阶段不声称获得高速超越能力。
2. **阶段B：在唯一权威GNC源码修订普通/紧急策略。** 普通避碰按任务速度与物理/路线能力执行，不再仅因普通标签施加紧急3.2m/s固定上限；真正紧急避碰保留现有保守限速，直至有依据的专门修订。高航速只有在完整链路接纳并验证后才可执行，并非无条件承诺8m/s。
3. **阶段C：将新的权威版本同步集成并验收。** 独立原C++参考与本地嵌入版针对同一新版本重验；新Run封存新身份，旧快照、旧Run保留原身份。产品只维护一个当前执行基线。

用户已批准建立独立权威GNC仓库并修订源码；集成和完整验收在隔离工作树进行，通过验收前不替换8010执行基线。

## User Stories

1. As a simulation operator, I want to distinguish mission speed from planner demand, so that I know what VO actually selected.
2. As a simulation operator, I want to distinguish admitted speed limits from final control setpoints, so that route acceptance cannot conceal guidance clipping.
3. As a simulation operator, I want actual speed shown separately from the setpoint, so that normal tracking transients are not mistaken for planner decisions.
4. As a simulation operator, I want every active speed limit to show its reason and source, so that 3.2m/s is explainable.
5. As a simulation operator, I want the release condition of a limit, so that I can understand when speed recovery is permitted.
6. As a simulation operator, I want ordinary avoidance separated from emergency avoidance, so that an overtaking maneuver is not silently treated as an emergency.
7. As a simulation operator, I want genuine emergency protection retained, so that improving overtaking does not remove a safety function.
8. As a simulation operator, I want high-speed commands executed only when feasible, so that a requested8m/s is not confused with a guaranteed8m/s.
9. As a simulation operator, I want infeasible overtaking capability reported explicitly, so that waiting behind a faster target is not labeled successful overtaking.
10. As a simulation operator, I want overtaking, clearance, route recovery and goal arrival reported separately, so that run completion does not imply mission success.
11. As a planner integrator, I want VO to consume the execution-side speed envelope before selection, so that it does not repeatedly request prohibited velocities.
12. As a planner integrator, I want route-dependent limitations checked before execution acceptance, so that geometry conversion cannot invalidate an accepted velocity silently.
13. As a planner integrator, I want material command degradation to trigger revalidation or replanning, so that the original prediction is not retained after its command changes.
14. As a planner integrator, I want stale capability or route revisions rejected explicitly, so that mismatched snapshots cannot authorize execution.
15. As a planner integrator, I want course, heading, SOG and surge-speed semantics stated, so that environment-on runs do not mix different quantities.
16. As a GNC maintainer, I want the authoritative source to define mode policy, so that the simulator does not maintain a second behavioral implementation.
17. As a GNC maintainer, I want coordinate conversion to preserve ordinary/emergency distinctions, so that transport encoding does not change policy.
18. As a GNC maintainer, I want curvature, deceleration, vessel, actuator and terminal restrictions retained, so that removing one inappropriate fixed cap does not disable other guards.
19. As a GNC maintainer, I want3.2m/s documented as the existing emergency-policy setting with its qualification limits, so that an unexplained constant is not presented as a universal vessel capability.
20. As a verification engineer, I want independent native-reference comparison for a new source version, so that previous fidelity evidence is not reused for changed behavior.
21. As a verification engineer, I want the real VO-to-vessel chain as the acceptance entry point, so that isolated green unit tests cannot substitute for execution evidence.
22. As a verification engineer, I want failed and constrained runs preserved without fallback, so that limitations remain observable.
23. As a verification engineer, I want ownship and all-vessel safety separated, so that target-vessel failures cannot disappear in an ownship PASS.
24. As a replay user, I want historical speed reasons and policy versions sealed with each Run, so that replay does not reinterpret old evidence using current policy.
25. As a frontend user, I want missing or stale speed evidence marked unavailable, so that default zeros and held values cannot appear as fresh commands.
26. As a project owner, I want one current GNC baseline and immutable historical evidence, so that upstream improvements do not create two maintained originals.

## Implementation Decisions

1. Extend the existing Original GNC adapter, VO capability input, route-admission feedback and Telemetry Envelope. Do not introduce a parallel planner, second lifecycle, browser risk engine or new general-purpose control framework.
2. Preserve the accepted domain authority boundaries: Encounter Lifecycle owns duties; runtime Threat Management freezes current evidence; GNC owns execution policy; plan acceptance evaluates executable safety; Independent Evaluator assesses realized outcomes. Web projects these facts without creating policy.
3. Resolve the intended operation mode from canonical evidence and the existing command contract. A visible HIGH risk label, a nonzero hazard count or the word avoidance alone must not automatically mean emergency. The exact escalation mapping must be documented and tested; unsupported or unknown mode combinations cannot silently become cruise.
4. Publish a versioned execution capability snapshot containing source/build/policy identity, generation time and validity, relevant active route revision, intended mode, speed semantics, applicable ceilings and their reasons. Reuse existing containers where possible; this is one execution authority, not a second table of hand-maintained constants in VO.
5. Separate mode-dependent hard ceilings from maneuver desirability. VO may keep its own conservative choices below the execution ceiling, but its TCPA/phase gates cannot widen a hard execution ceiling. Stage A must reflect the current ordinary-avoidance3.2m/s policy honestly.
6. VO and Fan-MPC publish native course/SOG velocity intents throughout cruise, avoidance and recovery; the adapter must not invent a path or rejoin curve. Only Mid-MPC publishes an executable path through the existing route admission and geometry guards. GNC owns course tracking, motion limits and actuator control for both input kinds; telemetry preserves planner provenance and reports any downstream clipping.
7. A materially different admitted command must not inherit the original candidate's safety conclusion. Revalidate its executed trajectory or replan within the existing bounded cycle. Use a previously accepted plan only while its existing validity and safety conditions remain satisfied; otherwise report an explicit failure. Do not silently select a fallback algorithm or extend stale intent validity.
8. Respect the established cycle boundary: execution feedback from cycle N becomes planning evidence in a subsequent cycle. Do not create an unbounded same-cycle feedback loop or rewrite the frozen Threat Management Snapshot from the selected plan.
9. At the authoritative GNC source, distinguish any-avoidance predicates from emergency-only speed-policy predicates. Preserve that distinction across the route manager, coordinate encoding and guidance decoding. Audit existing guards that currently inspect the shared code so their intended protection is retained; changing a tag to cruise is not an acceptable workaround.
10. The proposed ordinary-avoidance ceiling is governed by vessel, route and dynamic feasibility, rather than the emergency-only fixed3.2m/s cap. This does not mandate8m/s through a sharp turn, insufficient stopping distance, severe tracking error or terminal maneuver. Existing emergency3.2m/s remains a documented conservative setting pending separate justification; no universal optimality claim is made.
11. Do not overwrite the immutable original source snapshot. Prepare an explicit successor in the single authoritative GNC source, obtain source-version/policy confirmation before promotion, then rebuild both the independent reference and local integration from that successor. The previous P-C1 experiment is prior art, not permission to restore proposal-full or maintain a local behavioral fork. P-C2/P-C3 are not bundled into this change.
12. Record requested speed, route-admitted ceiling, final guidance/control setpoint and measured speed as different facts, with aligned simulation times and plan/route identities. Preserve all active limiting reasons and the binding reason; a later deceleration check must not erase the earlier curvature limit that actually bound speed.
13. Treat course versus heading and ground speed versus source surge-speed reference explicitly. Environment-OFF comparisons and environment-ON transformations have separate evidence. Do not silently assume scalar SOG equals body surge speed when current or lateral motion is material; unavailable observation or mapping evidence remains explicit.
14. Reuse the existing frontend and replay panels to display mode, speed stages, current binding restriction and policy/build identity. Missing initial output must be unavailable rather than a fabricated zero; held/stale evidence must be distinguishable from a fresh setpoint. Version new recorded fields; do not mutate older Run evidence.
15. Preserve user sessions and dirty workspace changes. Deployment requires a fresh Run after source/policy changes; never replace the executing native library in a live or paused Run. Keep one current product baseline, with old artifacts retained solely as historical references.

## Testing Decisions

The user explicitly confirmed the primary test seam: **Run Specification → real VO → adapter → original GNC → realized trajectory → Independent Evaluator**. Existing independent native replay is the supporting diagnostic seam, not an alternative acceptance gate.

Good tests assert observable command semantics, realized behavior and evidence integrity. They must not merely repeat implementation formulas, accept a PASS flag without executed solver evidence, or require actual ship speed to jump instantaneously to the requested value.

1. **Minimal diagnostic control:** initialize the original native stack at north1000m/east2000m, speed8m/s and course0; initial mission is a straight route to north6000m. After11s submit a straight three-point avoidance contract through north1000/1700/6000m at constant east2000m and requested speeds8m/s, with valid parent binding,100s validity, exact heading/speed disabled and degraded execution allowed. Change only the middle navigation tag among cruise, avoidance and emergency_avoidance; observe after another30s. Current baseline must reproduce8/3.2/3.2m/s guidance outputs with8m/s route limits. Native source and library identities must be recorded.
2. **Stage A full-chain contract:** under frozen policy, the planner must not issue a fresh accepted velocity above the applicable execution ceiling. Missing, expired or mismatched capability evidence must fail explicitly. A policy-constrained slow run cannot be marked successful overtaking merely because safety passed.
3. **Stage B ordinary/emergency distinction:** with the approved successor and no other active limiter in the straight control case, ordinary avoidance must no longer be clipped solely by the emergency cap; the8m/s request must be admissible and the final guidance reference must agree with the unconstrained cruise control within the existing same-input speed tolerance. Genuine emergency mode must retain its configured ceiling. Check normal→emergency→normal transitions and guard recovery without repeated label-induced switching.
4. **Physical restriction controls:** add curvature, short deceleration distance, actuator/plant limits and terminal/DP cases. They must continue to constrain or reject unsafe commands, with correct binding reasons. Test ordinary high speed and emergency low speed separately from source fidelity. No collision, steering or deadline threshold may be weakened to obtain PASS.
5. **Original reference fidelity:** compare the independent authoritative C++ reference and local embedded successor with the same inputs, clocks and callback order, retaining existing dimensional tolerances and exact discrete checks. Explicitly changed mode/speed semantics are validated against the new authoritative version; historical28-case results remain attached to the old version. Declare required extended coverage before promotion rather than relying on library availability or smoke tests.
6. **Real product matrix:** VO/Truth with OT, head-on, crossing give-way and stand-on, Environment OFF first and ON separately. Keep seeds, target states, solver deadlines, safety gates and original run durations fixed. Record real solver execution, no fallback, ownship safety, all-vessel safety, COLREG behavior, overtaking completion, clearance, route recovery and goal arrival independently. Existing full-chain and native-adapter suites provide prior art; add no new service boundary solely for tests.
7. **OT task acceptance:** the ordinary high-speed improvement is not accepted until the existing OT case actually completes overtaking and recovery within its existing scenario limits, with the independent safety checks satisfied. If another original limitation blocks completion, retain a failed qualification and report that blocker; do not extend1200s, slow the target, relabel the scenario, weaken clearance or hide a failed goal to finish this ticket.
8. **Speed tracking:** compare final setpoints and realized response using the existing source characterization envelope and explicit stable/maneuver windows. Report startup and switching transients separately. Do not claim every actual-speed deviation is a policy bug or choose post-hoc tolerance windows to force PASS.
9. **Evidence and browser checks:** verify the five speed stages, limit source/release condition, mode and source identity at aligned times in live telemetry and sealed replay. Seek old and new Runs and confirm they retain their own policy. Test missing initial output, stale feedback, constraint release and rejected plans. The browser cannot convert missing evidence into a success or an emergency decision.
10. **Acceptance ordering:** complete Stage A contract tests, then authoritative policy review and native reference tests, then the unchanged full product matrix and frontend verification. Module parity, source runtime stability, scenario safety and complete OT acceptance remain separate verdicts.

## Out of Scope

- Implementing or deploying the proposed policy during this diagnosis/specification turn.
- Silently raising emergency3.2m/s to8m/s, disabling guidance/actuation, writing directly to vessel state, or changing avoidance labels to evade protections.
- Maintaining both a local modified original and a separate authoritative original as ongoing implementations.
- Restoring the old proposal-full build or bundling unrelated corner/deceleration patches.
- Replacing VO with another avoidance algorithm, rewriting Fan/Mid planning logic, or tuning unrelated controller gains and physical models.
- Changing encounter thresholds, safety distances, target trajectories, scenario time limits or evaluator criteria to produce a passing overtaking result.
- Claiming vessel certification, universal optimality of3.2m/s, universal8m/s maneuver capability, or equivalence of all native ROS asynchronous trajectories.

## Further Notes

The current product still uses the frozen original baseline. This proposal deliberately separates immediate truthful capability coordination from a subsequent authoritative behavior revision. If authoritative GNC policy changes are not approved, only Stage A is possible: VO must honor the3.2m/s ceiling and the high-speed OT requirement remains unsupported. There is no honest adapter-only solution that simultaneously preserves that unconditional source cap and executes8m/s on the capped leg.

The3.2m/s value is verified in code/configuration; its derivation and suitability for ordinary overtaking are not established by available evidence. The source route-arbitration helper already distinguishes ordinary and emergency behavior, while waypoint encoding collapses them. This is evidence of differing policy granularity, not proof of the original author's undocumented intent.

The existing ADRs require one canonical authority per threat fact and runtime ownership of online threat management; accepted-plan feedback crosses the cycle boundary. Keep those constraints while extending the execution-speed contract.

No current execution policy or source parameters were changed by this investigation. Diagnostic probes and the local report retain the measured control results. This issue is ready for implementation planning and the gated work above; deployment and full OT acceptance remain future work.

## Confirmed input ownership

| Planner | Native output | GNC input | Recovery owner |
|---|---|---|---|
| VO | Course + SOG | VelocityIntent | VO continues nominal-reference commands after clearance |
| Fan-MPC | Course + SOG | VelocityIntent | Fan nominal/reference planner continues after clearance |
| Mid-MPC | Native avoidance path + speed profile | RoutePlan | Explicit route/return contract |

Scalar requests retain parent route identity, solve identity, ordinary/emergency mode and finite expiry. A held tick cannot renew an expired solve. Expiry stops in GNC until fresh authorization or explicit return; clearing an encounter alone must not silently transfer guidance ownership. SOG demand and signed body-surge controller reference are distinct quantities. Both response profiles are remeasured against the revised source.

## Confirmed monitoring priority integration

The completed monitoring lifecycle snapshot feeds the next VO solve. Monitoring commitment preserves the encounter duty but must not itself activate maneuver constraints. VO admits a maneuver through its existing current-motion risk gates, or when the nominal recovery reference would enter the preferred clearance domain or violate the established duty within a finite execution window. That window uses the existing prediction horizon, course response time and the available turn rate to account for the reference turn or the nearest moving COLREG-admissible avoidance turn; monitoring status alone is not an activation gate. Only after VO has admitted that target rule may the monitoring recovery guard sustain the maneuver through clearance; local release logic cannot silently supersede that guard. A distant monitored target with neither current-motion nor reference conflict must not acquire global direction/progress constraints merely because it is ACTIVE/COMMITTED. Existing overtaking completion and re-encounter protection remain unchanged. The admitted duty persists across solves. The time window governs activation, not truncation of COLREG exclusions after admission. Crossing candidates may reduce an earlier starboard alteration while staying on the permitted side of the entry course and satisfying all physical and COLREG exclusions; overtaking and head-on progress protections remain unchanged. Physical collision constraints remain independent. Record measured geometry, monitored duty and active rule separately. Verify the actual passing side and astern geometry in addition to minimum clearance and mission completion. A native velocity backend may explicitly advertise stationary hold; this does not make zero route-speed limits a stop command.
