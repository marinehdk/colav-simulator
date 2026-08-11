# Deepen Mid-MPC L1/L2 Problem Assembler

## Problem Statement

Mid-MPC现在能在Playground中运行真实CasADi/IPOPT并输出81点预测，但业务OCP装配仍由Facade、临时Builder和solver preparation共同承担。Lifecycle已经能稳定给出角色、commitment、passing side、Rule17、release/recovery事实；下游仍会重新解释这些事实，并以全局route bearing、静态能力box、裸stage索引、soft slack和自由格式trace构造问题。

结果：MASS parity、IPOPT success、Ship0场景G3和生产hard-safety语义容易混为同一个结论；相同输入无法仅通过一个public seam重放完整问题；目标slot、node clearance、activation、failure和GUI轨迹来源难以审计。

## Solution

建立一个stateless、deep `MidMpcProblemAssembler`。它消费冻结的Planner输入、Candidate 2 `DecisionSnapshot`、稳定route reference、capability profile和可选accepted-plan seed；原子返回`AssemblySuccess`或typed `AssemblyFailure`。

Success包含immutable semantic problem、target bindings、81点prediction bundle、constraint activation plan、seed/profile provenance和canonical hashes。数值`p/x0/lbx/ubx/lbg/ubg`仍由IPOPT core私有唯一layout authority打包，不成为integration API。

保留`MASS_PARITY`研究profile；生产使用`COLAV_STRICT`，在同一frozen graph/layout上把CPA与direction hard slack固定为0。Adapter只调度、映射failure、调用IPOPT、组装evidence，不重分类COLREG、不fallback。

## User Stories

1. As a Mid-MPC developer, I want one assembly public interface, so that I can reproduce the exact OCP without running a full simulation.
2. As a COLREG developer, I want Lifecycle to remain the only role and commitment authority, so that Assembler cannot reverse an accepted maneuver.
3. As a solver developer, I want named semantic preparation inputs, so that positional vector layout stays private and consistent with the graph.
4. As a reviewer, I want request, problem, prepared, solver and acceptance hashes, so that I can prove every artifact belongs to one solve.
5. As a scenario tester, I want 80 control intervals and 81 state points over 0..1200s, so that runtime and GUI use the actual optimizer horizon.
6. As a safety evaluator, I want synchronized hull clearance separated from point-node CPA, so that node feasibility is not misreported as continuous safety.
7. As a safety evaluator, I want every predicted segment checked independently, including the first segment, so that coarse-grid crossings are visible.
8. As a planner engineer, I want 50m hard clearance and 150m soft aspiration to be distinct, so that a comfort objective cannot weaken a safety requirement.
9. As a parity researcher, I want the eight MASS oracle fixtures unchanged, so that architectural changes do not rewrite the upstream reference.
10. As a production user, I want a strict profile with hard CPA and direction slack fixed to zero, so that penalty weights cannot silently buy a hard violation.
11. As a runtime user, I want no fallback and typed fail-stop behavior, so that a failed Mid-MPC cycle is never presented as a successful different controller.
12. As a tracker consumer, I want stable `TrackKey` target binding, so that input order and ID reuse cannot change solver slots silently.
13. As a multi-target user, I want every required target included, so that capacity pressure never silently drops a COLREG obligation.
14. As a multi-target user, I want more than 16 required targets to fail explicitly, so that the frozen graph limit remains truthful.
15. As a planner engineer, I want target predictions on one explicit time axis, so that admission, constraints, GUI and acceptance compare the same states.
16. As a planner engineer, I want covariance provenance and confidence in prediction evidence, so that degraded observations are not treated as exact.
17. As a route follower, I want nominal route, committed maneuver and recovery authority separated, so that avoidance does not permanently redefine the mission route.
18. As an OT tester, I want both port and starboard corridor commitments preserved from Lifecycle, so that Assembler does not hard-code one overtaking side.
19. As an HO/CS tester, I want common physical constraint compilation, so that no scenario-specific Builder is required to obtain PASS.
20. As a stand-on tester, I want HOLD/Rule17 facts compiled without reclassification, so that Lifecycle stage remains stable through solving.
21. As a numerical engineer, I want schedule semantics defined in seconds before stage mapping, so that grid changes do not change business timing accidentally.
22. As a numerical engineer, I want the frozen own(k+1)/target(k) quirk explicit, so that parity behavior and synchronized safety are not confused.
23. As a numerical engineer, I want target one-step displacement in the frozen node allowance, so that the known timing offset is compensated in the correct direction.
24. As a controls engineer, I want Plant/GNC/Mid-ODD limits represented separately, so that static YAML values are not claimed as live GNC authority.
25. As a controls engineer, I want current prefix length fixed to zero without execution acknowledgement, so that hold behavior does not become a false hard commitment.
26. As a numerical engineer, I want deterministic cold initialization when no accepted plan exists, so that replay remains reproducible.
27. As a future integrator, I want only an explicit L4-accepted plan eligible for warm start, so that rejected or stale solutions cannot seed a new episode.
28. As an API consumer, I want assembly failures to carry code, owner, identity and recoverability, so that UI and tests do not parse exception strings.
29. As a session operator, I want assembly failure mapped through existing normalized status, so that shared algorithm APIs remain compatible.
30. As an experiment owner, I want compact inline solve evidence, so that long sessions do not flood websocket and session memory.
31. As an experiment owner, I want full content-addressed gzip artifacts, so that prepared vectors and row witnesses remain replayable.
32. As a GUI user, I want a typed render projection, so that the browser does not guess `x/y` versus `north/east` or reconstruct solver truth.
33. As a GUI user, I want planner and evaluator evidence visibly separate, so that an evaluator result cannot be mistaken for planner input.
34. As a capability maintainer, I want six independent acceptance gates, so that a G3 scenario pass cannot replace parity, strict or runtime proof.
35. As a performance maintainer, I want 0/1/16 target p50/p95/max measurements, so that the 20s deadline claim is evidence-based.
36. As a repository maintainer, I want candidate2 tests reused, so that Candidate 3 does not fork lifecycle behavior.

## Implementation Decisions

- Public seam: `assemble(request) -> AssemblyOutcome`; Assembler is stateless and all public result types are immutable.
- `AssemblyRequest` includes cycle identity, Planner input, Candidate 2 decision snapshot, stable route reference, capability snapshot, assembly profile and optional accepted-plan reference.
- `AssemblyOutcome` is closed: success contains a complete problem snapshot; failure contains no partial problem.
- Candidate 2 remains sole owner of classification, role, risk, commitment, passing side, Rule17, release/rearm, STOP and lifecycle events.
- Assembler validates snapshot identity/hash/profile and target bindings; it never calls geometry classification or advances lifecycle state.
- Internal stages are private pure functions: validation, normalization, target binding/admission, prediction, safety, activation, capability/prefix/seed, profile, snapshot hashing.
- Target slots are deterministic. Required targets are never dropped. Capacity overflow is a typed failure.
- Target prediction uses constant ENU velocity and exposes 81 samples. Covariance is propagated only for declared profile evidence; no maneuvering-target robustness claim.
- Frozen graph parity keeps 80 heading/speed decisions and known own(k+1)/target(k) row timing.
- Synchronized node allowance uses both footprint radii, position covariance margin and one target-step displacement.
- Activation is represented as a typed physical-time plan, then mapped to frozen rows. No raw `TCPA/dt-2` policy remains in the facade.
- Capability values are resolved into an explicit profile. Current release is limited to KinematicCSOG; full live GNC envelope remains out of scope.
- Prefix length remains zero until an execution acknowledgement contract exists.
- Initial seed is deterministic cold start. Warm start remains disabled unless a public L4 accepted-plan handoff is added later.
- `MASS_PARITY` retains oracle behavior. `COLAV_STRICT` uses the same variables and graph topology while fixing CPA and direction slack bounds to zero.
- One private numerical preparer/layout authority packs positional arrays and shares its version with row/layout evidence.
- Expected assembly failures return typed data; Adapter maps them to current normalized status/details and never invokes fallback.
- Evidence namespaces are versioned and immutable. Inline event payload is bounded; full replay data is stored as a content-addressed gzip artifact.
- Target-target scripted collisions remain reported but are not attributed to Ship0 Mid-MPC control.

## Testing Decisions

- Tests assert behavior through four agreed seams: Assembler outcome, IPOPT solver result, CustomMPCAdapter plan, and P1/HTTP runtime.
- Each TDD cycle is vertical: one failing public-seam test, minimal implementation, then next slice.
- Gate A covers determinism, identity, frame, 0/16/17 targets, capacity, replay, failures, prediction and schedule evidence.
- Gate B reuses all eight frozen oracle records; expected values and tolerances are not rewritten.
- Gate C proves strict slack bounds and original-bound feasibility independently from solver status.
- Gate D reuses Candidate 2 HO/CS/OT/overtaken/multitarget scenarios, including both OT mirrors, with real IPOPT and no fallback.
- Gate E proves a real 8010 planner solve event, 81 points at 15s, readable hashes/artifact and source-separated UI data.
- Gate F runs scoped Ruff/format/diff checks and the full repository test suite.
- Tests do not mock internal assembly stages or assert private positional offsets.

## Out of Scope

- New solver backend, acados port, ROS2/MASS M4/M6/M7 contracts.
- Reworking frozen NLP equations, target maneuver models or 5-DOF/MMG dynamics.
- Candidate 1 L4 Plan Acceptance deepening beyond existing independent witnesses.
- Real GNC certification, ship trials, legal COLREG certification or arbitrary unknown-target guarantees.
- Control of scripted target vessels or eliminating target-target scenario collisions.
- Scenario-ID branches, fallback controllers, safety-threshold reduction and evaluator-driven planner decisions.
- Artifact retention service, remote object store and long-term quota policy.

## Further Notes

- Authoritative baseline is Candidate 2 commit `b94148c`; its full regression was `441 passed, 2 skipped`.
- Fixed formulation provenance is `mass-l3-mid-mpc-ipopt@ced58f8576f3772ef7c1bc72bb0f8b0368688b5a`.
- Current published parameters: N=80, dt=15s, solve period=5s, deadline=20s, heading window=45deg, speed=0..8m/s, hard/soft clearance=50/150m, ROT=3deg/s, decel=0.3m/s2, max targets=16.
- Detailed evidence, discarded alternatives and cross-thread alignment live in the accepted solution pack and design log.

