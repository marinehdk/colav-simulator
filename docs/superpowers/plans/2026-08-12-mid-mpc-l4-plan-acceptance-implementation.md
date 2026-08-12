# Mid-MPC L4 Plan Acceptance Implementation Plan

> **Base**: `marine/main@1f459d8`
> **Branch**: `codex/mid-mpc-l4-plan-acceptance`
> **Method**: `implement` + `tdd`; vertical slices; no production change before RED
> **Review fixed point**: `1f459d8`
> **Authoritative inputs**: accepted L4 solution pack, design log, Spec, VR-01..24, TS-01..42

## Completion Definition

Work is complete only when all conditions hold:

1. One pure `MidMpcPlanAcceptance.evaluate(request)->result` contract owns L4 semantic acceptance.
2. Every production candidate passes integrity, numerical, safety, COLREG, trackability and evidence mandatory layers before command visibility.
3. Fresh, hold, one-replan, rejection and reset paths use one atomic Adapter transaction boundary.
4. MASS_PARITY remains diagnostic-only; COLAV_STRICT alone can generate accepted receipt and warm eligibility.
5. All relevant targets are reconciled and independently accepted; target count above 16 fails closed.
6. Independent 81/80 swept hull-clearance witness proves at least 50 m for every Ship0-target pair.
7. Lifecycle remains sole COLREG authority; L4 only verifies immutable obligations and deadlines.
8. Real active Viknes+FLSC capability governs active-prefix trackability; otherwise profile remains NOT_PRODUCTION_READY.
9. Request→Problem→Prepared→Candidate→Acceptance→Receipt chain is replayable and projects one consistent full/inline/GUI truth.
10. Total Assembly→Preparation→IPOPT→L4→freshness→commit meets the measured 20 s policy.
11. V1..V6 gates pass, full regression is green, and a real port-8010 event proves L3+L4 execution with no fallback.
12. Capability metadata claims only exact Ship0 evidence tuple; global target-target contacts remain explicit diagnostics.

## Confirmed Test Seams

### Primary Seam

`MidMpcPlanAcceptance.evaluate(request) -> AcceptanceResult`

Use this seam for contract, numerical, geometry, COLREG, multi-target, trackability, quality, canonicalization and replay tests. Do not expose or test private layer helpers.

### Integration Seams

1. `CustomMPCAdapter.plan(...)` for fresh/hold/replan, final deadline, atomic commit, receipt/warm authority, fail-stop and PlannerTrace projection.
2. Existing `P1RunHarness` for real-IPOPT closed-loop Ship0 behavior and independent Evaluator evidence.
3. Real port-8010 Session/API event for process identity, L3/L4 source, active/latest timelines, bounded payload and no fallback.

The Assembler and Solver remain upstream producers. They are exercised through real candidate bundles; L4 tests do not duplicate their internal tests.

## Dependency Gates

| Gate | Required evidence | Stop behavior |
|---|---|---|
| Candidate 3 base | `1f459d8` ancestor; assembler/core/adapter suites green | Do not implement on older facade schema |
| Lifecycle projection | immutable baseline, deadlines, achievement, reachability, release permission | Mandatory COLREG UNKNOWN; no production acceptance |
| Active plant capability | typed Viknes+FLSC identity, limits, validity and hash | Trackability UNKNOWN; NOT_PRODUCTION_READY |
| Numerical corpus | quantity-specific boundary cases around all TS-15 tolerances | No COLAV_STRICT promotion |
| Runtime reservation | target-environment full-L4 p99 plus safety margin | Reservation UNSET; NOT_PRODUCTION_READY |

## Vertical Slices

### Slice 0: Baseline and Contract Inventory

- Verify Candidate 3 commit ancestry and clean worktree.
- Run existing assembler, core, parity, adapter, single-encounter, multiship and capability suites.
- Capture current public behavior for solve success, held plan, failure trace and Session transition.
- Record target environment and current 0/1/16-target solver timing without changing policy.
- No production code in this slice.

Acceptance:

- Existing expected values unchanged.
- Baseline commands, test counts and known warning recorded in issue evidence.
- No hidden dirty changes or listener replacement.

### Slice 1: Immutable Acceptance Request and Layered Result

- RED: valid versioned request returns deterministic immutable result; schema/cycle/profile/parent mismatch returns typed integrity failure.
- RED: mandatory FAIL/UNKNOWN, advisory WARN, N/A and NOT_EVALUATED aggregate according to frozen precedence.
- RED: repeated evaluation yields equal semantic bytes/hash regardless of map insertion order.
- GREEN: add request namespaces, TrackKey, policy snapshot, layer/outcome taxonomy, failure/witness types and pure facade.
- Keep wall timing, artifact path and persistence state outside semantic hash.

Acceptance:

- One public operation only.
- No Facade, Adapter, Session or global reads.
- All types immutable and JSON-finite.
- Schema-specific canonicalization golden tests pass; no JCS claim.

Commit intent: `feat: establish Mid-MPC L4 acceptance contract`

### Slice 2: Numerical and Profile Acceptance

- RED: eligible and ineligible IPOPT terminations produce distinct outcomes.
- RED: NaN/Inf, raw x/g bound violations, objective mismatch, preparation/options/hash mismatch and strict nonzero slack reject.
- RED: boundary corpus exercises every quantity-specific abs/rel tolerance immediately below, at and above the threshold.
- RED: missing same-point multipliers produces KKT NOT_EVALUATED+WARN, not hard failure.
- RED: MASS_PARITY remains diagnostic-only even when every check passes.
- GREEN: implement numerical checker over one same-point CandidateEvidence bundle and explicit profile policy.

Acceptance:

- All eight frozen C++ parity fixtures remain byte/expected-value unchanged.
- COLAV_STRICT requires fixed-zero CPA/direction slack within abs 1e-7.
- Existing uniform solver tolerance is never reused as the L4 mixed-unit policy.
- No receipt or command path exists for MASS_PARITY.

Commit intent: `feat: verify Mid-MPC numerical candidates before acceptance`

### Slice 3: Independent Swept Safety and Multi-target Reconciliation

- RED: hand-worked crossing segments detect interval-interior minimum missed by both endpoints.
- RED: first interval, final interval, stationary/parallel/zero-length and exact 50 m boundary cases.
- RED: clearance subtracts both circumscribed radii and per-time trusted uncertainty.
- RED: God accepts zero uncertainty; non-God without calibrated envelope rejects.
- RED: applicable static context PASS/FAIL and missing/stale context reject.
- RED: target permutation preserves result/hash; missing/mismatched binding and 17 relevant targets reject.
- GREEN: implement independent synchronized segment oracle, conservative clearance witness and five-set target reconciliation.

Acceptance:

- 81 knots and 80 intervals evaluated for every relevant TrackKey.
- Every failure names TrackKey, interval, absolute time, own/target positions and clearance lower bound.
- Per-target mandatory conjunction determines Ship0 aggregate.
- Target-target contacts are retained as global diagnostics only.

Commit intent: `feat: add conservative swept Mid-MPC safety gate`

### Slice 4: Lifecycle Action Contract and COLREG Predicates

- RED: missing commit baseline, deadlines, actual achievement, reachability or release permission rejects production request.
- RED: HO late action/wrong passing side, CS bow crossing, standard OT wrong corridor, mirror OT wrong corridor, stand-on drift and premature release reject.
- RED: compliant HO port-to-port, CS astern, locked OT corridors and Rule17 escalation pass.
- RED: predicted past-clear without current release permission remains active and cannot enter recovery.
- GREEN: extend Lifecycle snapshot only with immutable evidence projection fields; do not change classification, side, phase, aggregation or release decisions.
- GREEN: implement trajectory predicates consuming the frozen action contract.

Acceptance:

- L4 contains no encounter classifier, side selector, phase reducer or conflict resolver.
- Standard OT verifies the Lifecycle-locked starboard corridor; explicit mirror/restricted port remains valid.
- First executable interval and absolute deadlines are covered.
- Cumulative achievement is measured from frozen commit baseline, never from current candidate heading.

Commit intent: `feat: enforce Lifecycle obligations at Mid-MPC L4`

### Slice 5: Active-prefix Trackability and Advisory Quality

- RED: missing, stale, mismatched or KinematicCSOG-only capability cannot pass production trackability.
- RED: active prefix outside heading/speed/ROT/accel/decel/reachability envelope rejects.
- RED: correct COG/SOG and body psi/u/v/r conversion passes; swapped semantics reject.
- RED: quality detects cross-solve churn, poor progress and delayed recovery but does not reject a safe straight route plan.
- GREEN: add typed active-plant capability snapshot and prefix checker; add advisory quality summaries.

Acceptance:

- Capability identity and validity are included in request/policy hashes.
- Real Viknes+FLSC contract is used for production tuple.
- Without a validated full tracking tube, result wording claims only active-prefix executability plus planned full-horizon safety.
- Raw objective is not used as cross-cycle quality score.

Commit intent: `feat: bind Mid-MPC acceptance to active plant capability`

### Slice 6: Fresh Acceptance and Atomic Adapter Commit

- RED: inject failure after solve, after validation, after L4 and after final freshness; no partial solution/command/receipt/warm/event becomes visible.
- RED: accepted candidate commits all active fields together and returns selected command.
- RED: final total-deadline or freshness failure rejects even after semantic L4 PASS.
- RED: TIMEOUT_FEASIBLE is allowed only for an eligible same-point candidate that passes complete L4 and commits within total deadline.
- GREEN: restructure Adapter fresh path into prepare/evaluate/final-check/atomic-commit transaction.

Acceptance:

- Existing stable PlanStatus and FailureSource outer enums remain compatible.
- Full typed acceptance result remains in details/artifact.
- Rejection emits no command, no fallback, clears active/warm authority and transitions Session RUNNING→FAILED.
- No accepted planner event exists before atomic commit.

Commit intent: `feat: atomically commit L4-accepted Mid-MPC plans`

### Slice 7: Held-plan Revalidation, One Replan and Receipt/Warm Handoff

- RED: mutate current ownship by 100 m; old SUCCESS cannot continue.
- RED: mutate target generation, target set, prediction, Lifecycle phase, route, policy, capability and clock independently.
- RED: compatible held plan revalidates only the active prefix on its original absolute timeline and does not sign or extend a receipt.
- RED: stale hold performs one same-algorithm immediate replan only when no solver has run and budget permits; second failure is fail-stop.
- RED: accepted compatible receipt produces resampled heading/speed seed, cold tail, zero strict slacks and no duals.
- RED: rejected, parity, reset, corrupt or incompatible receipt cannot warm; warm failure does not cold retry.
- GREEN: add PlanAcceptanceCertificate, AcceptedPlanReceipt, PreviousAcceptedPlan and Adapter hold transaction.

Acceptance:

- Held command is licensed only until the next solve window.
- No receipt renewal on hold.
- Reset clears epoch-bound active/receipt/warm state.
- No fallback, retry loop or old command remains after final rejection.

Commit intent: `feat: revalidate held Mid-MPC plans and accepted warm starts`

### Slice 8: Canonical Evidence, Projections and Bounded Persistence

- RED: Request→Problem→Prepared→Candidate→Acceptance→Receipt parent mutation invalidates replay.
- RED: full artifact round-trips and re-evaluates to identical semantic result/hash.
- RED: inline projection remains ≤8192 bytes and contains all mandatory failures/primary witness.
- RED: GUI projection uses north/east target fields and exposes active accepted plan separately from latest attempt.
- RED: queue item/byte overflow, write failure, crash-safe rename, shutdown timeout and retention behavior are explicit.
- GREEN: implement canonical semantic record, dispatch record, mechanical projections and bounded async sink.

Acceptance:

- Persistence state cannot alter same-cycle semantic verdict or command.
- INCOMPLETE/BACKPRESSURE blocks evidence/capability claim.
- Defaults: artifact 16 MiB, queue 32 items/64 MiB, drain 2 s, retention 256.
- Rejected trajectory never becomes active map trajectory.

Commit intent: `feat: publish replayable Mid-MPC acceptance evidence`

### Slice 9: Runtime Policy and Deadline Reservation

- RED: Session freezes typed policy/hash; runtime mutation invalidates receipt and is rejected.
- RED: solver cutoff reserves L4/freshness/commit budget; IPOPT consuming the full 20 s cannot be accepted afterward.
- Measure complete L4 with 0/1/16 targets on the exact production environment.
- Freeze reservation only after stable p50/p95/p99/max evidence and documented safety margin.
- GREEN: integrate Registry policy, Session freeze, cutoff and NOT_PRODUCTION_READY state.

Acceptance:

- Total critical path, not solver alone, is ≤20 s.
- Reservation remains UNSET until measured; no zero/default bypass.
- Semantic result remains deterministic regardless of wall telemetry.
- Queue/persistence work stays outside control critical path.

Commit intent: `feat: enforce Mid-MPC total acceptance deadline`

### Slice 10: Real-IPOPT Closed-loop Acceptance

- Run route/no-contact, HO, CS-GW, CS-SO, standard OT starboard, mirror OT port, overtaken, Rule17 escalation and multiship.
- Use real CasADi 3.7.2/IPOPT, God tracker, strict no-fallback and exact published policy.
- Add public-seam RED only for observed contract defects; never add scenario-ID branches or reduce thresholds.

Acceptance per run:

- Requested/executed algorithm=`mid_mpc_ipopt`; solver backend=IPOPT; L4 profile=COLAV_STRICT.
- Every dispatched command references a PASS acceptance and receipt.
- Ship0 raw G3 and independent Evaluator hard gate PASS.
- Every Ship0-target realized hull clearance ≥50 m.
- HO port-to-port; CS-GW astern; stand-on/Rule17 contract; OT locked corridor; actual release and route/speed recovery.
- All relevant targets reconciled; no fallback or cached command after rejection.
- Scripted target-target contacts remain explicit global evidence and do not become Ship0 failures.

Commit intent: `test: prove Mid-MPC L4 closed-loop acceptance`

### Slice 11: Real 8010, Capability Promotion and Full Regression

- Start candidate service on 8011 first; verify listener PID/cwd.
- Exercise real Session/API solve and inspect canonical full/inline/GUI projections.
- After merge-ready evidence, validate fixed 8010 without overwriting unrelated dirty checkout or existing listener blindly.
- Update capability only for exact V1..V6 tuples that passed.
- Run full suite, scoped lint/format, diff check and code review.

Acceptance:

- Real event includes L3 status, L4 layer summary, acceptance hash, receipt hash, active/latest timeline, solver timing and `fallback_used=false`.
- Map displays actual accepted 81-point trajectory; rejected attempt is visible but not active.
- Target predictions render from canonical north/east fields.
- Capability evidence names commit, policy hash, tracker, plant/controller, seed, scenario and source scope.
- Full repository suite has no new failure; review findings resolved through new RED/GREEN slices.

Commit intent: `test: close Mid-MPC L4 runtime and capability evidence`

## Acceptance Matrix

| Gate | Required suites/evidence | Promotion blocked by |
|---|---|---|
| V1 Contract | request/result/taxonomy/canonical/hash/property tests | nondeterminism, partial result, schema ambiguity |
| V2 Oracles | swept geometry, COLREG predicates, prefix/capability, tolerance corpus | implementation-derived expected values |
| V3 L3/IPOPT | 8 frozen parity fixtures, strict adversarial candidate corpus | fixture edits, soft slack, mismatched evidence |
| V4 Closed loop | route, HO, CS-GW/SO, OT both corridors, overtaken, Rule17, multiship | fallback, <50 m, wrong geometry, no recovery |
| V5 8010/UI | correct listener, real planner event, active/latest, full/inline/GUI consistency | HTTP-only proof, stale projection, source mixing |
| V6 Performance/regression | calibrated p99 reservation, failure injection, full pytest, exact tuple | reservation UNSET, persistence claim incomplete |

## Acceptance Commands

Exact new filenames may be selected during implementation; commands express required behavioral groups:

```bash
uv run pytest tests/test_mid_mpc_plan_acceptance.py -q
uv run pytest tests/test_mid_mpc_plan_acceptance_numerical.py -q
uv run pytest tests/test_mid_mpc_plan_acceptance_safety.py -q
uv run pytest tests/test_mid_mpc_plan_acceptance_colregs.py -q
uv run pytest tests/test_mid_mpc_plan_acceptance_transaction.py -q
uv run pytest tests/test_mid_mpc_problem_assembler.py -q
uv run pytest tests/test_mid_mpc_ipopt_core.py tests/test_mid_mpc_parity_fixtures.py -q
uv run pytest tests/test_mid_mpc_ipopt_integration.py tests/test_custom_mpc_adapter.py -q
uv run pytest tests/test_mid_mpc_single_encounter.py tests/test_mid_mpc_multiship_runtime.py -q
uv run pytest tests/test_web_api.py tests/test_p1_capability_api.py -q
uv run ruff check <changed-python-files>
uv run ruff format --check <changed-python-files>
git diff --check
uv run pytest -q
```

## Required Evidence in Originating Issue

- Branch and exact base/head commits.
- RED command/output for every slice, then GREEN command/output.
- Frozen parity fixture checksum/no-change proof.
- Mixed-tolerance boundary corpus summary.
- 0/1/16-target full-L4 p50/p95/p99/max and frozen reservation.
- Scenario table: L3 status, L4 outcome, minimum Ship0 hull clearance, action timing, passing side/geometry, release/recovery, fallback.
- Global target-target collision/grounding accounting, explicitly separate from Ship0.
- Full artifact and inline/GUI projection hashes for at least one accepted and one rejected attempt.
- Real 8010 listener PID/cwd, Session id and planner-event summary.
- Full pytest, Ruff, format and diff-check results.
- Standards and Spec review findings/resolution.
- Exact capability tuples promoted; explicit non-claims retained.

## Stop Conditions

- Any change to frozen parity expected values, L3 equations, objective or row topology.
- Any need for L4 to reclassify encounters, choose side, advance phase or grant release.
- Any scenario-ID branch, fallback controller, forced PASS or reduction of the physical 50 m gate.
- Any production acceptance based only on KinematicCSOG, absent prediction uncertainty, stale chart context or uncalibrated deadline reservation.
- Any L4 rejection leaking candidate trajectory, command, receipt, warm seed or success event.
- Any target truncation when relevant count exceeds 16.
- Any synchronous artifact I/O placed before semantic/command commit.
- Any new contradictory evidence against VR-01..24 or TS-01..42. Stop implementation and return to design-grounding with the contradiction.

## Review and Publication

1. Commit each vertical slice independently with only its production/test/docs changes.
2. Run `code-review` against fixed point `1f459d8`, both Standards and Spec axes.
3. Resolve severity high/medium findings with additional RED/GREEN slices.
4. Rerun affected gates and full regression.
5. Push the implementation branch and publish final evidence to the ready-for-agent issue.
6. Merge only after exact capability metadata and live-runtime evidence match the accepted claim boundary.
