# Mid-MPC L0/L1 Encounter Lifecycle Implementation

> **Authority**: accepted solution pack and published to-spec issue
> **Method**: `implement` + `tdd`, vertical red→green slices, then `code-review`
> **Branch**: `codex/mid-mpc-l0-l1-lifecycle`
> **Issue**: [#24 Deepen Mid-MPC L0/L1 encounter lifecycle](https://github.com/marinehdk/colav-simulator/issues/24)

## Completion Definition

- Tracker, Lifecycle, Assembler, Adapter, closed-loop, and runtime seams match the accepted Spec.
- Current facade commitment/release/aggregation containers are removed; Lifecycle becomes the only business-state owner.
- Frozen eight-record C++ parity remains green.
- Standard HO, CS, OT mirror, overtaken, and compatible multiship scenarios satisfy Layer C.
- Conflict, capacity, unusable input, time gap, and core mismatch produce strict typed failures without solver execution or cached-plan fallback.
- Port 8010 emits a real `mid_mpc_ipopt` IPOPT event and displays the 81-sample, 1200-second trajectory with source-separated evidence.
- Focused tests, full pytest, Ruff/format, diff check, and final Standards/Spec review pass.
- Changes are committed and pushed from the isolated feature worktree.

## Pre-Agreed Test Seams

| Seam | Public behavior | Primary tests |
|---|---|---|
| S1 Tracker | Track snapshots expose stable identity, status, time, covariance, provenance | tracker lifecycle/contract tests |
| S2 Lifecycle | EncounterCycle → immutable DecisionSnapshot/events | new lifecycle contract tests |
| S3 Assembler | PlannerInput + Snapshot + route → MidMpcProblem or typed failure | new assembler mapping tests |
| S4 Adapter | public `plan()` → MPCSolution/PlannerTrace with real IPOPT | Mid-MPC integration/parity tests |
| S5 Closed loop | fixed-seed run harness → realized Ship0/evaluator evidence | single/multiship scenario tests |
| S6 Runtime | session/API/GUI payload → real planner event and visible evidence | session/API/browser proof |

No private-method tests. Independent expected facts only.

## Slice 1: Tracker-Authoritative Observation Contract

**RED**

- Add S1 tests proving generation changes on track recreation, UPDATED versus COASTING visibility, observation time/age provenance, termination, and covariance layout.
- Add tests proving missing generation/age cannot become fresh/stable silently.

**GREEN**

- Introduce immutable track identity/status DTOs at the shared tracking boundary.
- Extend God and KF trackers to emit authoritative status/time/generation facts.
- Carry snapshots through Ship and custom-MPC input construction.
- Keep an explicit legacy-unknown bridge only where required by other integrations.

**Verify**

- Tracker contract tests.
- Existing God/KF/custom-adapter tests.
- Ruff and format on changed files.

## Slice 2: EncounterCycle and Planner-Neutral Geometry

**RED**

- Add S2 input tests for ENU/N-E ordering, angle signs, signed TCPA, low-speed COG invalidity, PSD covariance, hull clearance, immutable arrays, and canonical input hash.
- Add dependency test preventing Planner policy from importing Evaluator classification.

**GREEN**

- Add immutable cycle, ownship, maneuverability, pairwise observation, geometry, validity, and profile models.
- Move only physical relative-geometry primitives into a planner-neutral module.
- Build observations without policy labels or fabricated unknown values.

**Verify**

- Geometry golden tests against worked literals and current ordinary HO/CS/OT values.
- Evaluator regression tests remain independent.

## Slice 3: Transaction, Identity, and Observation Health

**RED**

- Add S2 tests for same-cycle idempotency, same-key/different-hash conflict, private-copy rollback on invariant failure, epoch reset, time rewind/gap, short coast, reacquisition, generation change, and tombstone expiry.
- Add solver-not-called tests for UNUSABLE input.

**GREEN**

- Introduce the stateful EncounterLifecycle with atomic `step` and explicit `reset`.
- Implement TrackKey/episode ownership, health phases, coast/reacquisition/tombstone rules, and typed transition envelopes.
- Keep solver execution entirely outside the transition transaction.

**Verify**

- Pure lifecycle tests only; no CasADi imports.
- Adapter failure-source tests.

## Slice 4: Classification, Risk Entry, and Commitment Lock

**RED**

- Add S2 table tests for HO, CS give-way/stand-on, OT/overtaken, Rule 13 doubt, low-speed/boundary unknown, positive/negative TCPA, 5-second confirmation, urgent bypass, flicker, and semantic candidate changes.
- Add tests proving baseline cannot reset or accumulate angle each cycle.

**GREEN**

- Implement orthogonal EncounterKind/OwnshipRole/RiskPhase facts.
- Implement Planner ODD classification tolerances, risk candidate/urgent evidence, physical timers, lock and discrete revision events.

**Verify**

- Pure transition matrix and invariant tests.
- Different solve periods produce equivalent physical-time behavior.

## Slice 5: Substantial Action, OT Corridors, and Rule 17

**RED**

- Add S2 tests proving no fixed 5°/unified 30°, persistent achievement constraints, OT port/starboard mirrored selection, deterministic exact tie, locked side, and auditable revision.
- Add cooperative/non-cooperative stand-on sequences proving STAND_ON/MAY_ACT/MUST_ACT and Rule17(c) scope.

**GREEN**

- Implement maneuverability-aware course/speed corridor commitments.
- Implement OT two-corridor evaluation and target-track passing-side semantics.
- Implement target action evidence and target-alone reachable-set proxy with UNKNOWN provenance.

**Verify**

- Lifecycle mirror/property tests.
- No scenario IDs in production policy.

## Slice 6: Achievement, Past-Clear, Release, and Rearm

**RED**

- Add S2 tests for actual achievement, CPA passed but not clear, footprint margin, relative-speed margin, uncertainty, separating persistence, 10-second confirmation, OT longitudinal/lateral clearance, recovery re-risk, and new episode rearm.

**GREEN**

- Implement COMMITTED→PAST_CLEAR→RELEASED guards and dynamic margin formula.
- Separate route recovery permission from duty release.
- Remove permanent released-target suppression.

**Verify**

- Pure sequence tests and actual-trajectory metric helpers with worked examples.

## Slice 7: Constraint-Set Aggregation

**RED**

- Add S2 tests for compatible mandatory constraints, HO/OT side conflict, Rule17 conditional restriction, speed/STOP, primary hysteresis, UNKNOWN_ROLE capacity, seventeenth required target, and unrepresentable per-target direction.

**GREEN**

- Implement immutable pairwise constraint facts and AggregateDirective.
- Intersect course corridors, apply priority, derive speed/STOP, and emit MANEUVER_CONFLICT/CAPACITY_EXCEEDED.
- Keep primary target evidence-only.

**Verify**

- Pure aggregate contract matrix.
- All active targets remain present in trace evidence.

## Slice 8: Stateless L1 Problem Assembler

**RED**

- Add S3 tests for route mapping, persistent commitment rows, physical schedules, all-target inclusion, footprint/uncertainty margins, speed zero, capacity failure, and CORE_CAPABILITY_MISMATCH.
- Assert Snapshot contains no solver artifacts and Assembler holds no business state.

**GREEN**

- Introduce a stateless Mid-MPC problem assembler.
- Reduce the integration facade to orchestration of LOS, Cycle/Lifecycle, Assembler, pure solver, and mapping.
- Delete old committed-policy, commitment-course, released-ID, target-decision, and first-target aggregation ownership.

**Verify**

- S3 mapping tests.
- Existing eight parity records remain unchanged.

## Slice 9: 80-Interval / 81-State Public Trajectory

**RED**

- Add S4 tests proving raw decision count 80, public state count 81, exact timestamps 0..1200 s, measured state at column zero, target prediction on the same grid, and GUI serialization of terminal time.

**GREEN**

- Preserve raw solver decisions and parity arrays.
- Map decisions into measured state plus 80 integrated future states.
- Separate state-sample count from control-interval count in public validation and descriptor evidence.

**Verify**

- Parity suite.
- Adapter trajectory continuity tests.
- GUI payload tests.

## Slice 10: Typed Evidence, Persistence, and GUI

**RED**

- Add S4/S6 tests for lifecycle schema versioning, optional-field compatibility, profile hashes, bounded 1024-event ring, overflow count, incremental sink failure, source separation, hold/fresh provenance, and JSON finite values.

**GREEN**

- Add lifecycle subdocument and typed events to PlannerTrace without breaking outer 1.x consumers.
- Add bounded live buffering and incremental persistence.
- Expose Planner and Evaluator evidence independently in the GUI.

**Verify**

- Schema golden/round-trip tests.
- Session/persistence/API tests.
- Browser inspection at desktop and mobile widths.

## Slice 11: Real-IPOPT Closed Loops and Capability

**RED**

- Add or strengthen S5 tests for HO, CS give-way, CS stand-on cooperative/non-cooperative, OT port/starboard mirrors, overtaken, compatible multiship, maneuver conflict, capacity, and unusable observation.
- Require actual commitment-window action, passing side, hull clearance, Rule17 sequence, release/recovery, no fallback, and real IPOPT diagnostics.

**GREEN**

- Adjust only general Planner ODD/profile or representational core behavior required by failing evidence.
- Do not change scenario IDs, Evaluator thresholds, fallback policy, or target scripts.
- Promote capability only for evidence tuples that pass.

**Verify**

- Layer C scenario suite.
- Explicit Ship0/global target-target accounting.

## Slice 12: Full Regression, Live 8010, and Review

**RED/GREEN**

- Resolve only regressions caused by this implementation; preserve unrelated behavior.

**Verify**

- All focused tracker/lifecycle/assembler/parity/adapter/scenario/capability tests.
- Full pytest once.
- Ruff/format and `git diff --check`.
- Start or restart only the owned port-8010 process after checking listeners and cwd.
- Prove a real `mid_mpc_ipopt` IPOPT planner event, 81-state/1200-second trajectory, typed lifecycle, profile hashes, and no fallback.
- Run `code-review` against the accepted Spec and repository standards; fix findings with targeted tests.
- Commit selectively, push branch, and publish final evidence in the issue.

## Non-Negotiable Guardrails

- No fallback planner.
- No scenario-specific production branches.
- No lowered Evaluator thresholds.
- No Planner import of Evaluator verdicts.
- No silent target truncation or constraint collapse.
- No fixed 5° or universal 30° action.
- No mechanical OT starboard-only policy.
- No production edit to target-vessel scripts for Ship0 PASS.
- No claim beyond fixed profile/scenario/seed evidence.
- No broad staging, reset, clean, or modification of the user's dirty main worktree.
