# Mid-MPC L0/L1 Encounter Lifecycle

## Problem Statement

Colav-Simulator can execute the Python Mid-MPC IPOPT core and has fixed-seed G3 evidence, but its current integration still mixes tracker interpretation, encounter classification, COLREG commitment, release policy, target truncation, problem assembly, solver execution, and free-form diagnostics inside one facade.

From the simulator operator's perspective, this produces several capability gaps:

- The displayed prediction claims an 80×15 s horizon, while the public state trajectory currently contains only 80 samples from t=0 to t=1185 s.
- Instantaneous geometry can overwrite the business duty after the ownship begins maneuvering.
- A fixed 5° one-shot alteration can yield an almost straight predicted path and does not establish early, substantial, effective action.
- Overtaking is mechanically biased to one side even though Rule 13 does not mandate a passing side.
- Stand-on encounters remain HOLD without an explicit Rule 17 MAY_ACT/MUST_ACT lifecycle.
- Release relies on TCPA or a fixed 190 m value rather than footprint, relative motion, maneuverability, and sustained separation.
- Track age, coasting, generation, reacquisition, and ID reuse are not represented truthfully.
- Multi-target handling can silently discard the seventeenth active target and collapse conflicting duties into one global side.
- Planner interpretation and Evaluator judgment are not sufficiently separated in runtime evidence.

The result may pass selected closed-loop scenarios while still leaving the overall OT/HO/CS decision chain difficult to explain, test, and safely extend.

## Solution

Introduce a deep, solver-agnostic L0 Encounter Lifecycle and a stateless L1 Mid-MPC Problem Assembler while preserving the equation-identical Python IPOPT core.

The solution will:

- Make the Tracker authoritative for identity, generation, observation status, time, covariance, and provenance.
- Convert tracker outputs into immutable ENU/SI/rad observations and planner-neutral geometry facts.
- Advance every target through one deterministic, orthogonal COLREG lifecycle before selecting optimizer targets.
- Keep encounter duty, role, risk phase, commitment, passing side, Rule 17 stage, observation health, release, and episode identity as explicit facts.
- Choose overtaking port or starboard corridors from the relative situation, then lock the selected corridor for the episode.
- Define substantial action by the safety deficit and vessel maneuverability, not by a fixed 5° or universal 30° constant.
- Aggregate all pairwise mandatory, conditional, locked, and preferred constraints into one common course/speed directive before one IPOPT solve.
- Fail visibly when observations are unusable, required targets exceed 16, duties conflict, or the frozen optimizer cannot represent the directive.
- Preserve raw C++/Python parity while mapping 80 control intervals to 81 public state samples spanning t=0 through t=1200 s.
- Emit versioned lifecycle snapshots and transition events through a bounded live buffer and incremental evidence sink.
- Prove the feature through public contract tests, L0-to-L1 mapping tests, real-IPOPT closed loops, full regression, and a real port-8010 planner event.

## User Stories

1. As a simulator operator, I want the Mid-MPC trajectory to cover the declared 1200-second horizon, so that the map does not overstate the prediction duration.
2. As a simulator operator, I want fresh solves and held plans identified separately, so that I know whether a displayed path came from the current IPOPT invocation.
3. As a simulator operator, I want Planner interpretation and Evaluator judgment labeled separately, so that scoring logic cannot be mistaken for control logic.
4. As a simulator operator, I want structured failure states instead of silent fallback, so that unsupported situations are visible.
5. As a simulator operator, I want target-target contacts reported separately from Ship0 safety, so that Mid-MPC is judged only for vessels it controls.
6. As a COLREG algorithm developer, I want physical geometry facts separated from rule interpretation, so that coordinate mathematics can be shared without self-evaluation.
7. As a COLREG algorithm developer, I want encounter type and ownship role represented independently, so that Rule 13, crossing, and stand-on facts do not collapse into fragile strings.
8. As a COLREG algorithm developer, I want a deterministic per-target lifecycle, so that ownship maneuvers do not cause encounter-label flicker.
9. As a COLREG algorithm developer, I want risk entry based on approaching motion and footprint-aware predicted clearance, so that the 1200-second optimizer horizon is not misused as an action trigger.
10. As a COLREG algorithm developer, I want physical-time confirmation and hysteresis, so that behavior does not change when the solve frequency changes.
11. As a COLREG algorithm developer, I want urgent risks to bypass ordinary confirmation, so that hysteresis cannot delay necessary action.
12. As a COLREG algorithm developer, I want the commitment baseline frozen, so that repeated replanning cannot accumulate a sequence of small course changes.
13. As a COLREG algorithm developer, I want minimum action constraints to remain active until actual achievement, so that they are not a one-cycle pulse.
14. As a COLREG algorithm developer, I want substantial action derived from safety deficit and maneuverability, so that neither 5° nor 30° becomes a universal rule constant.
15. As a COLREG algorithm developer, I want both overtaking corridors evaluated before commitment, so that Rule 13 does not become a mechanical starboard-only policy.
16. As a COLREG algorithm developer, I want the overtaking side locked after commitment, so that receding-horizon replanning cannot alternate passing sides.
17. As a COLREG algorithm developer, I want the actual passing corridor measured against the target track, so that first-turn direction is not mistaken for final overtaking geometry.
18. As a COLREG algorithm developer, I want stand-on behavior to expose STAND_ON, MAY_ACT, and MUST_ACT, so that Rule 17 escalation is explicit.
19. As a COLREG algorithm developer, I want target action adequacy based on trend, persistence, reachability, and clearance improvement, so that one heading sample cannot prove compliance.
20. As a COLREG algorithm developer, I want target-alone capability represented as an engineering proxy with provenance, so that Rule 17(b) uncertainty is not hidden.
21. As a COLREG algorithm developer, I want past-and-clear based on footprints, relative speed, maneuverability, and sustained separation, so that fixed 190 m release is removed.
22. As a COLREG algorithm developer, I want route recovery separated from COLREG release, so that returning to the route cannot prematurely end the duty.
23. As a COLREG algorithm developer, I want released targets able to form new episodes, so that later risks are not permanently suppressed.
24. As a tracker developer, I want track generation and association status in the public contract, so that ID reuse cannot inherit an old commitment.
25. As a tracker developer, I want UPDATED, COASTING, and TERMINATED states preserved downstream, so that prediction is not presented as fresh observation.
26. As a tracker developer, I want observation time, covariance, source, and quality preserved, so that the Planner can make auditable degraded-data decisions.
27. As a tracker developer, I want unknown metadata represented as unknown, so that the adapter cannot fabricate age zero or stable identity.
28. As a Mid-MPC integrator, I want an immutable cycle and snapshot contract, so that the assembler cannot reinterpret mutable lifecycle state.
29. As a Mid-MPC integrator, I want same-cycle retries to be idempotent, so that solver errors cannot duplicate transitions.
30. As a Mid-MPC integrator, I want solver failure separated from decision commitment, so that IPOPT cannot roll back the world and rule state.
31. As a Mid-MPC integrator, I want all targets processed before optimizer capacity selection, so that the seventeenth threat cannot disappear silently.
32. As a Mid-MPC integrator, I want conflicting course obligations reported explicitly, so that one target cannot silently override another.
33. As a Mid-MPC integrator, I want speed reduction and STOP represented when course corridors conflict, so that Rule 8(e) is not excluded by a positive speed floor.
34. As a Mid-MPC integrator, I want an explicit optimizer capability gate, so that per-target direction requirements are not collapsed into the frozen global side parameter.
35. As a Mid-MPC core maintainer, I want the frozen eight-record C++ parity corpus preserved, so that lifecycle work cannot rewrite the translated mathematics unnoticed.
36. As a Mid-MPC core maintainer, I want raw 80-decision parity separated from the 81-state public trajectory mapping, so that the interface can be corrected without changing the oracle.
37. As an evaluator developer, I want realized Ship0 trajectories to be the evaluation input, so that Planner labels cannot certify themselves.
38. As an evaluator developer, I want actual course/speed alteration, passing geometry, clearance, and recovery checked over lifecycle windows, so that selected commands are not treated as outcomes.
39. As a test author, I want pure lifecycle tests without CasADi or an Evaluator verdict, so that rule defects are fast to localize.
40. As a test author, I want mapping tests at the immutable Snapshot-to-Problem seam, so that target inclusion and constraint semantics are independently verified.
41. As a test author, I want real-IPOPT tests at the public adapter seam, so that fake solvers cannot establish execution capability.
42. As a test author, I want mirrored overtaking scenarios, so that side selection is proven rather than assumed.
43. As a test author, I want cooperative and non-cooperative stand-on scenarios, so that Rule 17 transitions are exercised.
44. As a test author, I want loss, reacquisition, generation change, reset, retry, and time-gap sequences, so that lifecycle persistence is deterministic.
45. As a maintainer, I want a versioned lifecycle schema, so that GUI and persistence consumers can evolve compatibly.
46. As a maintainer, I want a bounded live event buffer and incremental durable sink, so that long sessions remain observable without unbounded memory.
47. As a maintainer, I want canonical Planner ODD, Evaluator, build, and run identities recorded separately, so that evidence can be reproduced.
48. As a maintainer, I want capability promotion blocked until all acceptance layers pass, so that focused success cannot be advertised as complete support.

## Implementation Decisions

- Use the accepted Deep Transactional Lifecycle architecture. The lifecycle is the only owner of encounter business state; tracker, assembler, optimizer, adapter, evaluator, and persistence remain separate.
- Use a Tracker-authoritative rich contract. A compatibility bridge may mark legacy fields unknown, but it may not infer stable identity or fabricate freshness.
- Use one immutable cycle per lifecycle step and one immutable decision snapshot per successful transition.
- Use a session epoch, cycle sequence, and canonical input hash for idempotency and conflict detection.
- Use a pure, deterministic transition function with orthogonal identity, health, encounter, role, risk, commitment, side, Rule 17, release, and evidence facts.
- Use planner-neutral geometry primitives; Planner and Evaluator use independent profiles and state machines.
- Use ENU/SI/rad internally, north-first arrays, north-zero clockwise angles, and starboard-positive route lateral coordinates.
- Use `(target_id, generation)` as track identity and a separate lifecycle episode number.
- Use UPDATED, DEGRADED, COASTING, and UNUSABLE observation semantics. Unusable input stops planning; it is never equivalent to no target.
- Use the accepted Playground profile: fresh age at most 1 s, usable age at most 5 s, 5 s reacquisition, 10 s tombstone, 0.25 m/s COG validity threshold, and 0.99 Gaussian covariance confidence.
- Use footprint-aware hard and comfortable hull clearances of 50 m and 150 m in the independent Planner profile.
- Enter ordinary action after 5 s of confirmed approaching unsafe clearance. Bypass confirmation for urgent hard-clearance or response-time cases.
- Keep the commitment baseline fixed. Derive the nearest reachable course/speed corridor that closes the safety deficit; do not apply a fixed alteration angle.
- Evaluate both overtaking corridors. Maximize reachable minimum clearance, then minimize route/action deviation; use starboard only as an exact deterministic tie-break.
- Use a 10 s Rule 17 evidence window and explicit STAND_ON, MAY_ACT, and MUST_ACT stages.
- Use a 10 s release confirmation and a dynamic release margin based on both hulls, relative speed, uncertainty, and maneuverability.
- Process all pairwise lifecycles before aggregation. Required targets above 16 produce CAPACITY_EXCEEDED.
- Aggregate mandatory, conditional, locked, and preferred constraints into one common course/speed directive and perform one IPOPT solve.
- Produce MANEUVER_CONFLICT when no common directive exists and CORE_CAPABILITY_MISMATCH when the pure optimizer cannot represent a valid directive.
- Permit STOP only with a zero speed lower bound. Do not silently replace STOP with the current 0.25 m/s floor.
- Keep the equation-identical raw IPOPT core and frozen parity corpus unchanged unless a separately reviewed pure-core extension is required.
- Treat the optimizer horizon as 80 control intervals of 15 s. Publish 81 state samples from t=0 through t=1200 s.
- Keep the existing PlannerTrace outer contract compatible and add a versioned lifecycle subdocument plus typed transition events.
- Use a 1024-event bounded live ring and incremental JSONL persistence. Evidence loss prevents an acceptance claim but does not roll back the lifecycle decision.
- Record canonical resolved Planner ODD, Evaluator, build, and run hashes separately.
- Keep the stable runtime algorithm ID `mid_mpc_ipopt` and visible label `Mid-MPC`.
- Use strict no-fallback behavior. Invalid input, capacity, conflict, mapping, and evidence failures remain visible and attributable.

## Testing Decisions

- Tests verify public behavior, not private helper calls or internal dictionaries.
- Expected results come from rule fixtures, worked geometry, the frozen C++ oracle, or independent realized-trajectory measurements. Tests must not recompute expectations using the implementation under test.
- The test seams were accepted with the solution pack on 2026-08-11:
  - Tracker seam: public track snapshots expose generation, status, time, covariance, and provenance.
  - Lifecycle seam: an immutable encounter cycle produces one immutable decision snapshot and typed events.
  - Mapping seam: a Planner input, decision snapshot, and route reference produce one normalized optimizer problem or typed mapping failure.
  - Adapter seam: the public custom-MPC adapter produces a solution and PlannerTrace using the real IPOPT core.
  - Closed-loop seam: the public fixed-seed run harness measures realized Ship0 behavior with the independent Evaluator.
  - Runtime seam: the port-8010 session API emits a real Mid-MPC planner event and source-separated GUI payload.
- Development uses vertical TDD slices. Each slice begins with one failing public-seam test, implements the minimum behavior, then proceeds to the next slice.
- Layer A covers lifecycle contracts: classification boundaries, risk confirmation, urgent bypass, lock, achievement, Rule 17, release/rearm, observation health, identity, aggregation, retry, reset, and time gaps.
- Layer B covers Snapshot-to-Problem mapping: persistent commitment, target inclusion, dynamic margins, physical schedules, STOP, capacity, and optimizer capability failure.
- Layer C runs real IPOPT in head-on, crossing give-way, crossing stand-on cooperative/non-cooperative, overtaking port/starboard mirrors, overtaken, compatible multi-target, and maneuver-conflict cases.
- Layer D preserves all eight C++ parity records, then runs focused tests, the full test suite, lint/format checks, capability validation, and a real port-8010 event.
- Closed-loop success requires Ship0 raw G3 and the independent Evaluator hard gate, at least 50 m realized hull clearance, real IPOPT statuses, no fallback, actual substantial action, correct passing geometry, release, and route/speed recovery.
- Structured fail-stop scenarios pass only when the solver is not executed, no cached command is used, and the exact typed failure evidence is emitted.
- Existing custom-MPC schedule, adapter, parity, single-encounter, multiship, capability, session, and GUI tests provide prior art.

## Out of Scope

- MASS-L3 ROS2 nodes, messages, M4/M6/M7, GNC publication, ASDR, and A4000 deployment.
- acados or any optimizer backend other than CasADi 3.7.2 with IPOPT.
- Importing BC-MPC, SB-MPC, Fan-MPC, or vessel-specific MASS control logic.
- Controlling target vessels or treating scripted target-target contacts as Ship0 Mid-MPC failures.
- Legal certification or a claim that engineering thresholds are COLREG statutory values.
- Arbitrary real-sensor association correctness or real-vessel minimum-risk fallback.
- ENC/static-obstacle/shallow-water avoidance changes.
- Scenario-ID branches, forced PASS paths, fallback planners, or lowered Evaluator thresholds.
- A general event-sourced control architecture or per-target actor runtime.
- A full multi-mode multiple-IPOPT planner.

## Further Notes

- Authoritative design decisions and evidence are in the accepted solution pack and design log.
- Rule 13 does not mandate a fixed overtaking side. The starboard exact-tie preference is only a deterministic Planner ODD choice.
- The current public trajectory grid is a confirmed interface defect: raw decisions span 80 intervals, but the public state path ends at t=1185 s. Correcting this mapping is required before runtime acceptance.
- The frozen core currently exposes one global preferred side and common row schedule. A valid directive that requires per-target direction constraints must fail visibly until a separately reviewed pure-core extension exists.
- The frozen formulation's own-step/target-step offset and disabled midpoint rows remain parity facts. Independent continuous/swept clearance remains mandatory.
- Fixed-seed G3 evidence is scoped to the declared scenario, profile, tracker, plant, and build. It is not a global safety or legal claim.
