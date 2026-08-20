# Deepen Mid-MPC L4 Plan Acceptance

## Problem Statement

Mid-MPC已经具备冻结的Python CasADi/IPOPT core、Candidate 2 Encounter Lifecycle和Candidate 3 Problem Assembler，也能在Playground输出真实81点、80×15 s预测轨迹。当前控制链仍把“IPOPT返回可行解”和“该计划允许下发”近似视为同一个结论。

从仿真操作者与算法开发者视角，存在以下缺口：

- solver success主要证明数值termination与有限primal feasibility，不证明同步连续hull clearance、完整COLREG动作合同或真实plant可执行性。
- continuous CPA与部分约束信息仍主要作为diagnostics，不是统一production acceptance gate。
- 当前Adapter在shape、首状态与deadline检查后写入solution、current plan和trace；缺少L4通过后的单一原子commit。
- hold周期复用上次solution及SUCCESS，未按当前ownship state、目标集合、Lifecycle、route、prediction、plant capability和absolute timeline重新许可active prefix。
- Lifecycle已拥有role、side、phase、commit与release authority，但下发前没有独立模块机械验证candidate是否遵守该immutable action contract。
- KinematicCSOG静态能力box不能证明Viknes+FLSC active execution prefix；reference trajectory也不能自动成为1200 s闭环可跟踪保证。
- selected target、solver slot、Lifecycle target、prediction和execution track之间缺少一次完整reconciliation；第17个relevant target不得静默截断。
- PlannerTrace、artifact、inline payload与GUI可从不同字段拼装，容易显示旧accepted trajectory、隐藏本tick rejection或混淆Planner与Evaluator证据。
- MASS parity、COLAV_STRICT production acceptance、Ship0场景G3、global all-vessel安全与MASS-L3系统接受仍需严格分层。

因此，现有HO、CS、OT和多目标场景即使通过固定seed闭环，也不能证明每次下发前都完成了同一套可重放、fail-closed、policy-bound计划许可。

## Solution

建立deep、pure、stateless、deterministic `MidMpcPlanAcceptance` module。唯一主seam为`evaluate(request) -> result`，固定在L3 candidate形成后、CustomMPCAdapter原子commit之前。

Acceptance Request使用四个immutable命名空间：candidate、authority、execution、prior。Module编排integrity、numerical、safety、COLREG、trackability、quality与evidence七层检查，返回包含全部per-layer、per-target witness与canonical hash的typed result；不修改candidate、不重分类COLREG、不生成替代轨迹、不拥有fallback。

Fresh candidate执行完整L4。Held accepted plan按原absolute timeline、当前ownship/targets/context和真实active capability重验到下一solve窗口的active prefix；stale时仅允许一次同算法immediate replan。最终拒绝无command、无fallback，清除active plan、receipt和warm eligibility并使Session fail-stop。

MASS_PARITY恒为diagnostic-only。COLAV_STRICT production接受必须同时证明：eligible solver termination、同点original bounds、strict preparation/options、fixed-zero slack、81/80同步swept hull clearance、Lifecycle action contract、active-prefix trackability、evidence chain、总20 s deadline和final freshness。

Adapter仅在L4通过后生成Accepted Plan Receipt并一次原子发布solution、command、active plan、warm eligibility和event。Canonical semantic record成为full artifact、≤8 KiB inline payload与GUI的唯一投影源；active accepted plan与latest attempt使用独立时间线。

## User Stories

1. As a simulator operator, I want every Mid-MPC command accepted before dispatch, so that IPOPT success is not mistaken for operational permission.
2. As a simulator operator, I want rejected plans to produce no command and no fallback, so that another controller is never silently substituted.
3. As a simulator operator, I want fresh solves and held-plan validations displayed separately, so that I know what produced the active command.
4. As a simulator operator, I want the latest rejected attempt visible without replacing the active accepted timeline, so that failures are not hidden by old success.
5. As a simulator operator, I want Planner and Evaluator evidence labeled separately, so that post-run scoring cannot certify the controller that produced the plan.
6. As a safety engineer, I want synchronized continuous hull clearance checked over all 80 intervals, so that coarse 15 s nodes cannot hide a between-node collision.
7. As a safety engineer, I want the first executable interval included, so that the command being applied now cannot escape the safety proof.
8. As a safety engineer, I want both vessel footprints and trusted prediction uncertainty subtracted from center distance, so that point-mass CPA cannot overstate clearance.
9. As a safety engineer, I want the physical hard hull-clearance gate fixed at 50 m, so that numerical epsilon or comfort objectives cannot weaken it.
10. As a safety engineer, I want static chart hazards checked whenever the active profile requires them, so that ship-ship safety cannot hide grounding risk.
11. As a safety engineer, I want missing or stale static context to fail closed, so that unknown safety is not reported as PASS.
12. As a multi-target operator, I want every fresh, usable, relevant target reconciled, so that unselected contacts cannot disappear from acceptance.
13. As a multi-target operator, I want each TrackKey to pass mandatory checks independently, so that one safe target cannot compensate for another unsafe target.
14. As a multi-target operator, I want more than 16 relevant targets rejected explicitly, so that frozen graph capacity is never handled by silent truncation.
15. As a multi-target operator, I want target-target scripted contacts reported as global diagnostics, so that Ship0 acceptance scope remains truthful.
16. As a numerical engineer, I want eligible IPOPT termination verified separately from primal feasibility, so that status strings alone do not authorize control.
17. As a numerical engineer, I want finite raw x, g, bounds and objective checked at the same candidate point, so that mixed or stale solver evidence is rejected.
18. As a numerical engineer, I want quantity-specific absolute and relative tolerances, so that rad, m, m² and objective values are not judged by one arbitrary tolerance.
19. As a numerical engineer, I want KKT evidence advisory when same-point multipliers are unavailable, so that the implementation does not fabricate a hard optimality proof.
20. As a parity researcher, I want MASS_PARITY to remain diagnostic-only, so that reference reproduction cannot sign a production receipt.
21. As a production user, I want COLAV_STRICT to verify preparation, options and fixed-zero slack, so that penalties cannot purchase a hard violation.
22. As a COLREG developer, I want Encounter Lifecycle to remain the sole role, side, phase, commitment and release authority, so that L4 cannot become a second FSM.
23. As a COLREG developer, I want head-on candidates checked for timely action and port-to-port passing, so that a late or wrong-side path is rejected.
24. As a COLREG developer, I want crossing give-way candidates checked for passing astern, so that a nominal starboard turn without safe geometry is insufficient.
25. As a COLREG developer, I want standard overtaking candidates checked against the locked starboard corridor, so that an initial left turn cannot be accepted accidentally.
26. As a COLREG developer, I want explicitly locked mirror or restricted overtaking corridors respected, so that L4 does not overwrite Lifecycle policy.
27. As a COLREG developer, I want stand-on and Rule 17 stages checked against the frozen entry baseline, so that repeated replans cannot accumulate undetected drift.
28. As a COLREG developer, I want action start and achievement deadlines checked, so that a candidate that turns only near CPA cannot pass.
29. As a COLREG developer, I want actual cumulative achievement measured from the committed baseline, so that repeated small candidate-relative turns cannot masquerade as substantial action.
30. As a COLREG developer, I want predicted past-and-clear separated from current release permission, so that a future path cannot prematurely end the current duty.
31. As a route follower, I want route and speed recovery measured after actual release, so that avoidance does not permanently redefine the voyage.
32. As a controls engineer, I want COG/SOG references distinguished from body psi/u/v/r states, so that coordinate semantics do not corrupt trackability checks.
33. As a controls engineer, I want state knots and piecewise-constant interval commands modeled explicitly, so that 81/80 indexing is consistent.
34. As a controls engineer, I want active-prefix reachability checked against the real active plant/controller capability, so that static KinematicCSOG limits are not presented as Viknes+FLSC proof.
35. As a controls engineer, I want the claim reduced when no full tracking tube exists, so that 1200 s planned safety is not advertised as 1200 s closed-loop executability.
36. As a quality engineer, I want smoothness, cross-solve churn, efficiency, route progress and recovery reported, so that operational quality is observable.
37. As a quality engineer, I want V1 quality checks advisory, so that a safe straight trajectory is not rejected merely because it looks simple.
38. As a quality engineer, I want raw objective excluded as a cross-cycle quality score, so that changing targets and units cannot create false comparisons.
39. As an Adapter developer, I want acceptance completed before any active state becomes visible, so that rejected candidates cannot leak into hold, trace or warm start.
40. As an Adapter developer, I want one atomic commit after final deadline and freshness checks, so that solution, command, receipt and event cannot disagree.
41. As an Adapter developer, I want held plans revalidated against current state and context, so that stale SUCCESS cannot survive a large state deviation or new target.
42. As an Adapter developer, I want one bounded same-algorithm replan when hold becomes stale, so that recovery is possible without fallback or retry loops.
43. As an Adapter developer, I want final rejection to clear active and warm authority, so that no cached command remains executable.
44. As a warm-start developer, I want only compatible accepted receipts eligible, so that rejected, reset, parity or policy-mismatched candidates cannot seed IPOPT.
45. As a warm-start developer, I want heading/speed primal resampled on absolute time with a cold tail, so that grid age does not corrupt seed alignment.
46. As a warm-start developer, I want strict slacks rebuilt to zero and dual warm start disabled, so that unsupported multiplier or slack history cannot weaken strict semantics.
47. As an evidence reviewer, I want Request→Problem→Prepared→Candidate→Acceptance→Receipt hashes, so that every plan can be replayed and attributed.
48. As an evidence reviewer, I want semantic acceptance and dispatch records separated, so that runtime delivery outcomes cannot rewrite the verdict.
49. As an evidence reviewer, I want one canonical in-memory record, so that artifact, inline payload and GUI cannot drift independently.
50. As a GUI user, I want target prediction fields consistently named north/east, so that valid target trajectories are not silently omitted.
51. As a GUI user, I want a bounded inline acceptance summary, so that long sessions remain responsive without hiding failure causes.
52. As an operations engineer, I want persistence bounded by item and byte capacity, so that evidence writing cannot grow memory without limit.
53. As an operations engineer, I want persistence failure reported without changing a completed semantic verdict, so that slow disk cannot alter control logic.
54. As a realtime engineer, I want Assembly, Preparation, IPOPT, L4, freshness and commit inside one 20 s deadline, so that acceptance latency is included honestly.
55. As a realtime engineer, I want solver cutoff to reserve measured L4/commit time, so that IPOPT cannot consume the entire deadline.
56. As a capability maintainer, I want uncalibrated full-L4 p99 reservation to block production readiness, so that a guessed zero budget cannot authorize control.
57. As a capability maintainer, I want V1 through V6 gates independent, so that focused unit tests or a visible GUI button cannot replace closed-loop and runtime evidence.
58. As a capability maintainer, I want claims bound to exact commit, policy, tracker, plant, seed and scenario tuples, so that evidence is not generalized beyond its ODD.
59. As a repository maintainer, I want the frozen eight-record parity corpus unchanged, so that L4 work cannot rewrite upstream truth.
60. As a repository maintainer, I want vertical TDD at public seams, so that implementation remains reviewable and failures localize to contracts.

## Implementation Decisions

- Build one deep `MidMpcPlanAcceptance` module. Its only public operation is `evaluate(request) -> result`; it remains pure, stateless and deterministic.
- Place the seam after one complete L3 candidate bundle exists and before the Adapter mutates solution, command, receipt, warm eligibility, diagnostics or events.
- Use immutable, versioned request namespaces named candidate, authority, execution and prior. Do not read mutable Facade, Adapter, Session or free-form trace state.
- Use ENU/SI/rad internally. World positions are north/east meters; body axes are x-forward/y-port; course and heading are north-zero clockwise radians; right turn is positive.
- Represent 80 control intervals at 15 s and 81 state knots from 0 through 1200 s. Commands are piecewise constant on intervals.
- Distinguish ground-fixed COG/SOG reference from body psi/u/v/r execution state.
- Use `TrackKey=(session_epoch,target_id,generation)` and versioned schema-specific canonicalization. Do not claim RFC 8785/JCS compatibility.
- Produce typed layers: integrity, numerical, safety, COLREG, trackability, quality and evidence.
- Produce typed outcomes: PASS, FAIL, WARN, UNKNOWN, N/A and NOT_EVALUATED. Mandatory layers fail closed; quality is advisory in V1.
- Keep full failure lists with owner, code, recoverability and witness. Existing public PlanStatus remains a stable coarse projection.
- Require eligible IPOPT termination and independently recheck finite raw x/g, original bounds, strict preparation/options and objective consistency at the same candidate point.
- Use identity tolerance zero; heading/ROT/minimum-alteration and speed/acceleration tolerances of abs 1e-6, rel 1e-10; position/direction and CPA m² tolerances of abs 1e-4, rel 1e-10; fixed-zero slack abs 1e-7; objective abs 1e-8, rel 1e-10.
- Treat KKT as advisory in V1. Missing same-point multipliers produce NOT_EVALUATED and WARN, not fabricated PASS or mandatory FAIL.
- Keep MASS_PARITY diagnostic-only. It can never produce command, receipt or warm-start eligibility.
- Permit production acceptance only under COLAV_STRICT with matching preparation/options/hash chain and fixed-zero hard slacks.
- Recompute dynamic safety independently over all 81 knots and 80 synchronized intervals. Use analytic relative-segment minima and report the exact interval/time/positions witness.
- Compute conservative hull clearance as center minimum minus own radius, target radius and trusted uncertainty. Require the physical lower bound to be at least 50 m; keep 150 m advisory.
- Use zero prediction uncertainty only for the God profile. Any non-God profile requires a calibrated per-time envelope or is rejected for production.
- Require chart-backed static-hazard clearance when the selected ODD says it is applicable. Missing or stale context fails closed.
- Reconcile execution tracks, Lifecycle decisions, predictions, Assembler admission/bindings and solver slots for every relevant target. More than 16 relevant targets is a typed capacity rejection.
- Aggregate mandatory results by per-TrackKey conjunction. Primary target is display-only. Target-target contacts remain global diagnostic evidence.
- Consume Lifecycle snapshots as the sole COLREG authority. L4 never reclassifies, chooses passing side, advances phase, grants release or resolves duty conflicts.
- Check HO port-to-port, CS give-way pass-astern, OT locked corridor and stand-on/Rule17 predicates over the complete candidate trajectory.
- Use the standard Playground overtaking policy locked by Lifecycle; standard OT is starboard, while mirror/restricted port is accepted only when explicitly locked upstream.
- Require the Lifecycle action contract to expose commitment baseline, action-start and achievement deadlines, actual cumulative achievement, reachability certificate and current release permission.
- Check early action on the first executable interval. A predicted future past-and-clear state does not grant current release.
- Bind production trackability to a typed snapshot of the actual active plant/controller tuple. Single-encounter HO/CS/OT uses Viknes+FLSC; the existing multiship scenario may use only its actual KinematicCSOG+pass-through tuple. Neither tuple may substitute for or inherit the other's evidence.
- Claim hard executability only for the active prefix when no full tracking tube exists. Keep full-horizon planned safety and active-prefix execution claims separate.
- Keep smoothness, cross-solve churn, efficiency, full-polyline progress, recovery and straightness as V1 advisory evidence. Safe straight plans remain acceptable.
- Evaluate fresh candidates through full L4. Evaluate held accepted plans on their original absolute timeline using current ownship, current targets, current context and active-prefix capability.
- Allow one immediate same-algorithm replan only when hold is stale, no solver has run in the tick and total budget permits. No fallback and no warm-to-cold retry loop.
- On final rejection, emit no command, clear active plan/receipt/warm eligibility and move the Session to terminal FAILED.
- Perform final total-deadline and freshness checks after L4. Then atomically publish solution, active plan, command, receipt, warm eligibility and event.
- Separate L4 Plan Acceptance Certificate, Adapter Accepted Plan Receipt and neutral PreviousAcceptedPlan contracts.
- Warm start only from a compatible receipt. Resample absolute-time heading/speed primal, use a cold tail, rebuild strict slacks as zero and keep dual warm start disabled.
- Build one canonical semantic record and hash chain: Request→Problem→Prepared→Candidate→Acceptance→Receipt. Keep wall timing, artifact path, compression and queue state outside the semantic hash.
- Derive full artifact, ≤8192-byte inline summary and GUI projections mechanically from the canonical record. Maintain separate active-plan and latest-attempt timelines.
- Cover Assembly→Preparation→IPOPT→L4→final freshness→atomic commit inside the existing 20 s total deadline. Reserve solver cutoff from measured full-L4 p99 plus safety margin.
- Mark policy NOT_PRODUCTION_READY while the reservation is unset. Do not infer a complete value from geometry-only or solver-only timing.
- Use a bounded asynchronous persistence sink: default artifact maximum 16 MiB, queue 32 items/64 MiB, shutdown drain 2 s and retention 256 artifacts.
- Persistence COMPLETE/INCOMPLETE/BACKPRESSURE never rewrites the same-cycle semantic verdict, but incomplete persistence blocks evidence and capability claims.
- Store a typed immutable policy in the Registry and freeze/hash it at Session start. V1 freezes N=80, dt=15 s, hard=50 m, advisory=150 m, max relevant targets=16, total deadline=20 s, inline=8192 bytes, God-only production, strict-zero slacks and dual warm start off.
- Preserve stable runtime algorithm identity `mid_mpc_ipopt` and visible label `Mid-MPC`.
- Promote capability only after V1 pure contract, V2 independent oracles, V3 real L3/IPOPT, V4 closed loop, V5 real 8010/UI and V6 performance/full regression all pass for an exact evidence tuple.

## Testing Decisions

- Primary feature seam is `MidMpcPlanAcceptance.evaluate(request) -> result`. Most numerical, safety, COLREG, target, hold and evidence behavior is asserted only through this public contract.
- Adapter transaction seam verifies `CustomMPCAdapter.plan(...)` behavior: fresh acceptance, held-plan validation, one replan, atomic commit, rejection isolation, no fallback and public trace projection.
- Closed-loop seam is the existing fixed-seed `P1RunHarness`; it measures realized Ship0 behavior with the independent Evaluator and real IPOPT.
- Runtime seam is the real port-8010 Session/API event; it proves executed algorithm identity, L3/L4 source separation, active/latest timelines, bounded projection and no fallback.
- Tests verify external behavior and immutable outputs. They do not mock or assert private L4 layer functions, private solver offsets or serialization internals.
- Expected results come from hand-worked geometry, rule fixtures, frozen C++ parity records, typed Lifecycle contracts and independent realized trajectories. Tests do not recompute expected values using the implementation under test.
- V1 contract tests cover schema/version rejection, canonical replay, taxonomy, precedence, mandatory/advisory behavior, finite JSON, hash mutation and deterministic repeatability.
- V2 oracle tests cover synchronized segment minima, footprints, uncertainty, static applicability, HO/CS/OT/Rule17 predicates, absolute-time slicing, plant-envelope boundaries and mixed-unit tolerances.
- V3 real-solver tests preserve all eight C++ parity records and add COLAV_STRICT adversarial candidates for NaN, termination, raw bounds, objective mismatch, slack and 0/1/16/17 targets.
- V4 closed loops cover route/no-contact, head-on, crossing give-way, crossing stand-on, standard OT starboard, mirror OT port, overtaken, Rule17 escalation and multiship.
- Closed-loop acceptance requires real IPOPT, no fallback, Ship0 raw G3 and independent hard gate, realized hull clearance at least 50 m, correct passing geometry, timely action, release and route/speed recovery.
- Target-target collisions remain asserted explicitly as global diagnostics but do not fail Ship0 L4 acceptance.
- Hold tests mutate current ownship state, target generation, prediction, route, Lifecycle phase, plant capability and clock independently. Stale hold must replan once or fail-stop; it may never inherit old SUCCESS silently.
- Failure-injection tests stop at each precommit point and prove no solution, command, receipt, warm seed or accepted event becomes visible.
- Evidence tests prove full artifact replay, ≤8 KiB inline projection, GUI field consistency, active/latest separation, persistence backpressure and policy/receipt invalidation.
- Performance tests measure full L4 with 0/1/16 targets, derive p50/p95/p99/max and freeze a solver reservation only from the target production environment.
- Final verification runs focused suites, scoped Ruff/format, `git diff --check`, full pytest, capability exact-tuple checks and a live 8010 planner event.
- Development follows vertical red-green-refactor slices; scenario-ID branches, fallback, forced PASS and threshold reduction are forbidden fixes.

## Out of Scope

- Modifying frozen L3 IPOPT equations, objective, row topology, target model or solver backend.
- acados, ROS2/MASS M4/M6/M7, GNC publication, ASDR or A4000 deployment.
- Reclassifying encounters, selecting passing side, advancing Lifecycle phase or granting release inside L4.
- Online trajectory repair, second optimization, BC-MPC, MRM or any fallback controller.
- Controlling target vessels or eliminating scripted target-target collisions.
- Non-God production acceptance until a calibrated per-time prediction uncertainty envelope exists.
- Full-horizon closed-loop tracking guarantee without a validated tracking tube.
- Global all-vessel safety, arbitrary plant capability, NLP global optimum, legal compliance or real-ship certification.
- Changing scenario definitions, scenario-ID branching, reducing 50 m safety gate or using Evaluator output as Planner input.
- Synchronous event-sourced control infrastructure, remote artifact store or organization-wide retention service.

## Further Notes

- Authoritative design inputs are the accepted L4 solution pack, decision log, `VR-01..24`, `TS-01..42`, `ALT-01..150`, `R1..R81` and `SC-01..82`.
- Implementation baseline is Candidate 3 `marine/main@1f459d8`; its completed full regression was `464 passed, 2 skipped, 1 warning`.
- Frozen upstream algorithm provenance remains `mass-l3-mid-mpc-ipopt@ced58f8576f3772ef7c1bc72bb0f8b0368688b5a`.
- Candidate 2 Lifecycle and Candidate 3 Assembler remain independent upstream authorities. L4 may require additional immutable evidence projection fields but may not change their business decisions or numerical semantics.
- Known frozen L3 own(k+1)/target(k) timing and disabled midpoint rows remain parity facts. L4 compensates through independent synchronized continuous safety; it does not alter the graph.
- Current production blockers are explicit implementation gates: Lifecycle deadline/reachability projection, exact-tuple active capability contract, mixed-tolerance boundary corpus and calibrated full-L4 p99 reservation.
- User ruling on 2026-08-12 resolves the multiship capability conflict: KinematicCSOG+pass-through is acceptable only for its exact multiship tuple and is never presented as Viknes+FLSC evidence.
- A straight predicted line can be a real optimal solution. L4 rejects unsafe or contract-inconsistent plans, not visually simple ones.
