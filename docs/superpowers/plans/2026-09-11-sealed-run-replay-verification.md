# Sealed Run Replay — Verification & Acceptance Plan

> **Normative feature spec:** `docs/superpowers/specs/2026-09-11-sealed-run-replay-spec.md`  
> **PRD:** `docs/superpowers/specs/2026-09-11-sealed-run-replay-prd.md`  
> **UI:** `docs/superpowers/specs/2026-09-11-sealed-run-replay-ui-design.md`  
> **Technical design:** `docs/superpowers/specs/2026-09-11-sealed-run-replay-technical-design.md`  
> **Implementation:** `docs/superpowers/plans/2026-09-11-sealed-run-replay-implementation.md`  
> **Baseline:** `main@1c2b69acc52fdd8dfa515d38f86a679c0b4ef082`

## 1. Purpose

This document defines how Sealed Run Replay is proven complete. It is intentionally stricter than “the player looks right”. The release claim is:

> A recorded Colav-Simulator Run can be inspected visually, seeked and replayed through the shared situation surface without executing the Simulator or COLAV algorithm, while preserving recorded evidence identity, limitations and event order.

The plan follows the repository's engineering/V&V principles and Matt Pocock TDD guidance: tests are written against approved public seams, expected values come from independent fixtures/specification rather than the implementation under test, and development proceeds in vertical red → green slices.

## 2. Approved public test seams

Only these seams establish feature behavior.

### Seam A — Run Replay service/API

**Question:** Given a Run ID, can a consumer discover replay evidence and read bounded historical frames/events without executing simulation?

Externally observable behavior:

- list/discover replay-capable Runs;
- obtain a versioned Replay Descriptor;
- obtain a bounded frame window by simulation time;
- obtain the canonical event journal;
- receive explicit `READY`, `REDUCED`, `INCOMPLETE`, `UNAVAILABLE` semantics;
- reject invalid identity/path/range requests;
- remain read-only.

### Seam B — Replay Controller / Replay Clock

**Question:** Given immutable historical frames/events and a deterministic wall clock, does the presentation cursor behave correctly?

Externally observable behavior:

- select run;
- seek;
- play/pause;
- change Replay Speed;
- reach end deterministically;
- previous/next event;
- request/prefetch required historical windows;
- cancel superseded seek requests;
- interpolate only continuous vessel presentation;
- bind discrete facts to recorded source frames.

### Seam C — Evaluation browser Replay

**Question:** Can a user open a real completed Run in Evaluation and inspect/replay the exact historical situation through the shared Situation Display with zero Active Session mutation calls?

This is the highest-value acceptance seam and the final release proof.

## 3. Testing principles

1. **Behavior over implementation.** Do not test private helper names, queue internals, gzip implementation, DOM class names or cache layout where a public behavior can be asserted.
2. **Independent expected values.** Interpolation fixtures use literal worked examples. Event order fixtures are handwritten. Do not generate expected outputs by calling Replay implementation code.
3. **Red before green.** For each implementation slice, add one failing behavior test before the smallest implementation that passes it.
4. **Vertical tracer bullets.** Avoid a horizontal phase of “all backend tests first, all UI later”. Each ticket proves a narrow end-to-end behavior.
5. **No test-only second truth.** Tests may use deterministic source fixtures, but they must not reproduce planner/risk logic in JavaScript or a parallel oracle identical to production code.
6. **Fail closed.** Missing/corrupt evidence assertions expect unavailable/incomplete semantics, never permissive defaults.
7. **Evidence-backed acceptance.** Final acceptance records run IDs, digests, browser/network evidence, test logs and measured performance.

## 4. Test data strategy

Three evidence classes are required.

### 4.1 Hand-authored deterministic replay fixture

A compact full Decision Trace fixture with known values:

```text
frames at t = 0.0, 1.0, 2.0, 3.0 s
ownship moves north/east by known literals
one target moves by known literals
heading crosses 359° → 1°
discrete planner state changes only at t=2.0
events at 0.5, 1.75 and 3.0 s
```

Independent expected assertions include:

- position halfway between known coordinates;
- heading halfway across north is `0°`, not `180°`;
- planner state at `1.9 s` remains the lower/source frame's state;
- previous/next event sequence remains fixed.

The fixture must conform to the public trace schema but contain no current-algorithm-generated expected values.

### 4.2 Legacy/reduced fixture

A Run directory without full Decision Trace but with currently supported reduced artifacts. It verifies truthful degradation and that missing planner/risk evidence is not fabricated.

### 4.3 Real product acceptance Runs

At minimum:

- one VO product Run;
- one Fan-MPC product Run;
- one Mid-MPC product Run;
- one Historical AIS replay/counterfactual Run when the configured source is available for the acceptance environment.

The Mid-MPC Run is the primary proof that visual Replay speed is independent of solver throughput.

## 5. Backend evidence-capture tests

### VE-001 — Normal product Run captures full trace

Given a normal product-created session, when it advances and finishes, the Run contains a supported full Decision Trace and a replay descriptor reports `READY/FULL` after durable finalization.

Assert through public/run evidence interfaces, not by calling a private writer helper.

### VE-002 — Browser disconnect does not stop capture

Start a product Run, disconnect the WebSocket/browser consumer while the backend continues, reconnect or allow completion, then verify full trace frame/time continuity is preserved independently of the browser.

### VE-003 — Decision Replay compatibility

Open the same normal product Run with the existing `TraceBundle` / public Decision Replay command and confirm `evidence_level == full`, summary works, and at least one existing probe can consume it.

### VE-004 — Replay readiness is distinct from result readiness

Demonstrate a terminal Run state in which replay evidence is durable/ready while expensive Evaluation/report readiness remains pending. Assert the two statuses are independent.

### VE-005 — Trace persistence failure is explicit

Inject a supported storage failure at the evidence boundary. Run execution state must not silently become replay-ready. Expected replay state is `INCOMPLETE` with a typed reason.

### VE-006 — Partial crash evidence

Terminate a controlled test process/session after several durable frames. The replay repository either exposes the trustworthy prefix as `INCOMPLETE` or reports it unavailable according to the frozen policy. It must never claim complete full replay.

### VE-007 — Monotonicity/integrity

A deliberately malformed fixture with sequence/time regression or digest mismatch fails replay readiness with a typed reason.

## 6. Replay repository/API contract tests

### API-001 — Run discovery

`replayable=true` returns only Run records the service can describe using supported evidence states. Returned identity is Run ID, not a path.

### API-002 — Descriptor schema

For a full fixture, descriptor values match known manifest/index literals:

- Run ID;
- scenario/algorithm/tracker;
- replay evidence state;
- trace schema;
- frame count;
- `t_start/t_end/trusted_t_end`;
- frame digest;
- capabilities.

### API-003 — Bounded window

Request a small `[from,to]` interval and verify only the expected recorded frames plus the defined bracketing behavior are returned.

### API-004 — Direct late seek

Request a window near the end of a long fixture/run without requesting preceding simulation time. Verify response does not require a simulator step or sequential replay from zero.

### API-005 — Events

Events endpoint preserves known identity/order/time/details. Repeated reads are semantically identical.

### API-006 — Path confinement

Reject:

- `../` traversal;
- path separators encoded into Run identity;
- absolute paths;
- unknown Run IDs.

Verify the request cannot read outside the configured Run repository.

### API-007 — Request bounds

Reject or clamp according to the frozen API policy:

- negative/NaN/infinite times;
- `from > to`;
- oversized time/frame windows;
- abusive result limits.

### API-008 — Unsupported schema

Unsupported trace schema returns typed incompatibility. No current-schema reinterpretation is attempted.

### API-009 — Reduced legacy descriptor

Legacy fixture reports `REDUCED`; planner/risk-detail capabilities are false/unavailable rather than zero-valued.

### API-010 — Read-only proof

Snapshot Active Session authority before/after replay descriptor/window/events requests. No session identity, session state, speed revision, simulation time or result/evidence object is mutated.

## 7. Replay Clock tests

Use a fake deterministic monotonic clock.

### CLOCK-001 — 1× progression

From `playhead=10.0`, advance wall clock 2.0 s at 1× → playhead 12.0.

### CLOCK-002 — 5×/20× progression

At 5×, 2 wall seconds advances 10 simulation seconds. At 20×, 0.5 wall seconds advances 10 simulation seconds.

### CLOCK-003 — Pause

Paused clock does not advance despite wall-clock movement.

### CLOCK-004 — Rate continuity

Changing from 1× to 10× does not jump the playhead at the rate-change instant; only subsequent elapsed wall time uses the new rate.

### CLOCK-005 — End clamp

Playhead is clamped to `t_end` and transitions to ENDED exactly once.

### CLOCK-006 — Seek from ENDED

Seek backward transitions to a paused/seekable state according to controller contract and can play again.

### CLOCK-007 — Invalid rate

Unsupported/nonpositive/nonfinite rate is rejected by presentation policy rather than corrupting playhead state.

## 8. Replay Controller tests

### CTRL-001 — Select Run

Selecting a Run resets prior run-specific playhead/window/event/selection state and loads the new descriptor.

### CTRL-002 — Initial playhead

A ready run initializes at `t_start`, paused, with a loadable frame bracket.

### CTRL-003 — Direct seek

Seek from an early time to a late time sets the requested historical playhead and loads the appropriate window without simulated intermediate steps.

### CTRL-004 — Stale seek response

Issue seek A then seek B before A completes. Deliver response A last. State must remain on B; stale data may not overwrite the newer Inspection Cursor.

### CTRL-005 — Prefetch

While playing near the edge of a loaded window, controller requests a future window before the current bracket is exhausted. The exact threshold is implementation policy; behavior must avoid unnecessary playback stalls in the deterministic fixture.

### CTRL-006 — Buffering

If the required upper/lower frame is missing while playing, state becomes BUFFERING/paused until recorded data is available. No extrapolation occurs.

### CTRL-007 — Event navigation

Previous/Next Event from between events resolves to the correct known literal events. Behavior at first/last event is deterministic and documented.

### CTRL-008 — Marker filtering

Filtering event presentation does not mutate the underlying event journal or change Previous/Next Event semantics unless the UI explicitly chooses “navigate visible categories”; whichever contract is chosen must be specified and tested consistently. Recommended first release: event navigation follows current visible category filter but original journal remains intact and inspectable.

### CTRL-009 — Target selection

Selecting a target changes only inspection selection and never source frame/planner facts.

## 9. Interpolation tests

### INT-001 — Linear position

Known frame A `(N=0,E=0)` at `0 s`, B `(N=10,E=20)` at `2 s`; at `1 s`, displayed continuous position is `(5,10)`.

### INT-002 — Heading wrap

A `359°`, B `1°`; halfway result follows the shortest angular path through `0°` within floating tolerance.

### INT-003 — No extrapolation before start

Playhead before first trusted frame is clamped/unsupported; no backward projected vessel position is created.

### INT-004 — No extrapolation after end

At/after last trusted frame, last recorded position is used and playback ends; no forward prediction is presented as actual track.

### INT-005 — Discrete planner source

A planner state at A is `HOLD`, B is `SOLVE`; at an in-between playhead before B, the displayed discrete planner fact remains A's `HOLD`.

### INT-006 — Risk/lifecycle source

Risk/lifecycle transition exists only at B; no in-between state is invented.

### INT-007 — Event non-interpolation

Events remain point/interval/transition evidence at recorded time. They are never time-shifted by visual interpolation.

## 10. Projection parity tests

### PARITY-001 — Exact frame boundary

Take one known full captured product frame. Project it through the live Telemetry Projection input contract and through Replay source-adapter input at the same source sequence/time. Compare canonical projection sections relevant to Replay:

- navigation;
- risk;
- planner;
- outcome where historical semantics permit;
- timeline/event identity;
- raw historical frame reference.

Expected differences are restricted to presentation/transport/live-connection metadata and must be enumerated.

### PARITY-002 — Situation Display model parity

At the same exact source frame, ownship and target marker anchors/heading inputs, route/planner layers and target placard source facts are semantically equivalent between captured Live and Replay.

Do not assert pixel hashes where component rendering makes them unstable; assert stable public model/DOM semantics and use browser visual review for layout.

### PARITY-003 — Missing evidence parity

A source frame missing a fact remains unavailable in Replay. Replay may not infer it from neighboring frames if Live did not capture it.

## 11. Browser / end-to-end tests

Use the real local product API and supported browser harness used by the repository.

### WEB-001 — Evaluation opens recent replayable Run

Complete a Run, enter Evaluation, select Replay, verify Run ID and historical/readiness state.

### WEB-002 — Timeline seek

Drag/click from early time to late time. Verify displayed simulation time and ownship/target state match the recorded source/bracket.

### WEB-003 — Replay controls never mutate Active Session

Intercept/log the following endpoint families while using Replay controls:

```text
session create
start/resume
pause
step
speed/rate change
reset/replacement
```

Expected calls caused by Replay interactions: **zero**.

Read-only replay API calls are expected.

### WEB-004 — Replay Speed

For a short known segment, test 1×/5×/10×/20×. Compare wall-clock-to-playhead progression with tolerance suitable for browser scheduling. This is presentation timing only; do not require every source frame to paint.

### WEB-005 — Previous/Next Event

Navigate several recorded events and verify timeline/playhead/focused event/inspection details move together.

### WEB-006 — Target inspection

Select ownship and one target at multiple replay times; placard changes inspection context only.

### WEB-007 — Historical badge

Replay surface never displays a live-state label. Historical/readiness state remains visible when rails collapse.

### WEB-008 — Reduced evidence

Open a reduced fixture. UI clearly says reduced; planner/risk unavailable states are visible, not zero-filled.

### WEB-009 — Incomplete failed run

Open a failed/truncated fixture. Timeline ends at trustworthy boundary and the limitation is visible.

### WEB-010 — Results pending vs replay ready

Open Evaluation while replay is ready and result generation is still pending. Replay remains usable; Results separately communicates pending state.

### WEB-011 — Historical AIS local view

Open Evaluation > Historical AIS and verify current benchmark/mode/workflow/deploy semantics still function.

### WEB-012 — Historical AIS Open Replay

For a Historical AIS workflow/run that exposes a replayable Run ID, use `Open Replay` and verify the shared player selects that Run. No second replay clock/player is created.

### WEB-013 — Terminology

Deployment presents **Simulation Rate** and requested/effective rate semantics. Evaluation player presents **Replay Speed**. Ambiguous user-visible “Playback Rate” for Active Session is absent.

## 12. Network/no-execution acceptance proof

For final Mid-MPC acceptance, capture two independent facts.

### 12.1 HTTP/WS control trace

Record browser network or backend request log during Replay. It must show:

- Replay descriptor/window/events reads;
- no Active Session mutation endpoints due to Replay controls.

### 12.2 Solver execution counter

Record a stable backend/algorithm solve counter before Replay and after a complete Replay pass. It must not increase because of Replay.

If another unrelated live session is running concurrently, the test environment is invalid for this assertion. Use a controlled idle Active Session state or no active session.

## 13. Historical integrity tests

### HIST-001 — Repeated replay is deterministic

Read/seek the same run at the same timestamps twice. Historical source sequence/frame/event identities are equal.

### HIST-002 — Replay does not rewrite Original Evaluation

Hash/read original evaluation/manifest before and after arbitrary Replay interactions. Values/digests remain unchanged.

### HIST-003 — Replay does not rewrite trace

Frame/event artifact digests remain unchanged after Replay.

### HIST-004 — New code does not reinterpret old profile facts

Historical threat/lifecycle/planner fields are shown as originally recorded. A newer current profile/configuration does not cause browser/backend replay to recalculate old risk.

## 14. Failure/degradation matrix

| Fault | Expected behavior |
|---|---|
| no `decision/` trace, reduced trajectory exists | `REDUCED`; no invented planner/risk facts |
| trace file absent | `UNAVAILABLE` or `REDUCED` according to artifacts |
| unsupported trace schema | typed unavailable/incompatible |
| digest mismatch | `INCOMPLETE`/integrity error; no full claim |
| sequence/time gap | `INCOMPLETE`; trusted boundary/limitation visible |
| controlled crash | replay trustworthy prefix if policy supports it |
| window request error | pause/buffer/error; no extrapolation |
| superseded seek response | ignored |
| selected run deleted between list and open | typed not-found; no fallback to another run |
| result not ready | Replay may work independently |
| Historical AIS source unavailable | its benchmark view reports source limitation; normal Run Replay unaffected |

## 15. Security tests

- path traversal and encoded traversal;
- arbitrary absolute path attempt;
- excessive range/window request;
- malformed Run ID;
- unsupported schema payload;
- JSON/event data with unexpected strings does not become executable DOM/HTML;
- Replay endpoints expose no write operation;
- Replay does not reveal arbitrary host filesystem path in normal response payloads.

The local-first trust model remains the repository's model; these tests protect browser-to-filesystem authority boundaries rather than claiming hostile multi-tenant isolation.

## 16. Accessibility tests

At minimum:

- Play/Pause is keyboard focusable and state label changes correctly;
- timeline exposes min/max/current value/time label to accessibility APIs;
- keyboard seek works;
- Previous/Next Event works without pointer;
- historical/full/reduced/incomplete states have textual/non-color semantics;
- collapsed rails do not remove critical historical state;
- focus remains visible over chart controls;
- 200% browser zoom or equivalent compact check does not make the timeline unusable within supported desktop scope.

## 17. Layout / visual verification

Required screenshots or browser-captured evidence:

1. 1920×1080 FULL Mid-MPC replay with event-rich timeline.
2. 1440×900 same Run with compact rail behavior.
3. REDUCED legacy replay state.
4. FAILED/INCOMPLETE state.
5. Results pending while Replay ready.
6. Historical AIS local view after migration.
7. Historical AIS Run opened in shared Replay.

Review for:

- main chart dominance;
- persistent timeline;
- no nested page/panel scroll trap;
- target placards not obscuring replay controls;
- clear historical state;
- OpenBridge-consistent spacing/components/tokens.

## 18. Performance characterization

No release budget is invented before measurement. Record baseline and candidate measurements on the same machine/environment.

### PERF-001 — Capture overhead

For representative VO, Fan-MPC, Mid-MPC Runs, compare with replay capture disabled/baseline where technically possible without changing algorithm behavior:

- wall execution time;
- median/P95/max step time;
- planner solve timing distribution separately;
- trace writer queue/backpressure metrics if applicable;
- trace bytes per simulation minute;
- finalization time;
- replay evidence completeness.

The acceptance report must distinguish solver time from evidence-persistence overhead.

### PERF-002 — Descriptor/open latency

Measure cold/warm descriptor open for a representative 600 s trace.

### PERF-003 — Random seek latency

Select at least 20 deterministic pseudo-random seek times across the 600 s trace. Record median/P95/max time from API request to usable frame bracket, and browser request-to-render where tooling permits.

Only after this measurement may the implementation add a chunk/cache/index optimization and freeze a UX budget.

### PERF-004 — Replay presentation

For a controlled 60 s segment at 1×/5×/10×/20×:

- verify playhead progression;
- record dropped/skipped visual paint samples if available;
- verify event journal/markers remain complete;
- verify solver count does not change.

### PERF-005 — Memory bounds

Replay a long trace with repeated seeking. Browser and backend memory must remain bounded by cache/window policy rather than accumulating the complete Run unboundedly.

A practical measured bound is recorded in the acceptance report; do not assert an invented fixed MB number before implementation measurement.

## 19. Regression suites

At each ticket:

### Focused backend

Run the new replay/evidence tests plus existing tests for:

- Decision Replay;
- Experiment/session finalization;
- Web API/session authority;
- playback/simulation rate behavior touched by terminology/refactor;
- Historical AIS integration when modified.

### Focused frontend

Run existing repository Node tests plus new replay controller/projection/Evaluation tests.

### Full repository gates before final acceptance

Use the repository's established environment/commands. At minimum the final report must include results of:

```bash
.venv/bin/pytest -q
.venv/bin/ruff check .
git diff --check
```

and the repository's complete frontend Node test command/test set discovered in the checkout.

Do not hard-code a stale frontend glob into the normative spec; report the exact command actually used by the implementation checkout.

Recent baseline evidence at Spec time records approximately `914 backend passed, 1 skipped` and `255 frontend passed` in the latest GNC integration commit. These counts are context, not frozen Replay acceptance counts; final acceptance reports exact current counts.

## 20. Real Mid-MPC acceptance campaign

### Setup

Use one normal product-selectable Mid-MPC exact tuple and normal Config → Deployment creation path. Prefer a scenario that lasts long enough to include at least one real planner action and several solves.

Record:

- baseline/implementation commit;
- Run ID;
- RunSpec digest/identity;
- scenario/algorithm/tracker/GNC identity;
- execution requested/effective rate history if relevant;
- Decision Trace schema/frame/event/digest;
- evaluation/result readiness timing.

### Execution acceptance

1. Start Run in Deployment.
2. Let it complete normally.
3. Confirm replay status reaches READY/FULL.
4. Switch to Evaluation > Replay.
5. Seek near start, middle, late run.
6. At exact source frames, compare recorded/Replay canonical values.
7. Play a known 60 s segment at 1×/5×/10×/20×.
8. Jump between at least three meaningful events.
9. Inspect a target before/after a risk/planner transition.
10. Record network control trace and solver counter.
11. Confirm zero Replay-induced simulator/solver mutation.
12. Run Decision Replay summary/explain or another existing probe against the same Run.

### Required result

The Run can be fully inspected after completion even if its original Active Session could not realize 5× execution in real time. Replay presentation speed and original compute throughput are visibly/architecturally separate.

## 21. Historical AIS acceptance

Where the configured real/fixture source permits:

1. open Evaluation > Historical AIS;
2. confirm catalog/workflow authority still works;
3. create/run one Historical Replay or Counterfactual workflow/session according to existing product contract;
4. obtain its Run identity;
5. `Open Replay` into shared Replay local view;
6. verify historical AIS time/actor context and shared player behavior;
7. return to Historical AIS view and confirm workflow evidence remains unchanged.

No Human Reference / Counterfactual semantics are changed by this acceptance.

## 22. Final acceptance report template

Create a repository evidence report under the project's established evidence/design-log area containing:

```text
# Sealed Run Replay Acceptance

Baseline:
Implementation:
Date/environment:

## Reference Runs
- VO: Run ID / tuple / trace digest / state
- Fan-MPC: ...
- Mid-MPC: ...
- Historical AIS: ... or explicit unavailable reason

## No-Reexecution Proof
- network/request evidence
- solver counter before/after

## Frame/Projection Parity
- sampled times/sequences
- compared canonical sections
- expected presentation-only differences

## Replay Behavior
- seek
- play/pause
- 1×/5×/10×/20×
- event navigation

## Degraded Evidence
- REDUCED fixture result
- INCOMPLETE fixture result

## Performance
- capture overhead
- trace size
- descriptor/open
- random seek median/P95/max
- browser memory/cache observation

## Historical AIS
- benchmark UI regression
- shared player result

## Tests
- focused commands/results
- full pytest
- frontend tests
- Ruff/static/diff

## Limitations / Open Questions
- explicit remaining constraints
```

## 23. Release gate

Sealed Run Replay is **not complete** unless all are true:

- [ ] normal product Run produces full replay evidence;
- [ ] visual Replay never executes Simulator/Planner;
- [ ] direct seek works by simulation time;
- [ ] Replay Speed is solver-independent and presentation-only;
- [ ] continuous interpolation and discrete-source semantics are correct;
- [ ] event navigation uses recorded evidence;
- [ ] shared Telemetry Projection/Situation Display parity is demonstrated;
- [ ] reduced/incomplete evidence fails/degrades truthfully;
- [ ] Decision Replay compatibility passes;
- [ ] Historical AIS benchmark is preserved and uses the shared player for Run playback;
- [ ] Simulation Rate vs Replay Speed terminology is clear;
- [ ] capture/seek/performance is measured, not assumed;
- [ ] full backend/frontend/static/browser gates are reported truthfully;
- [ ] final acceptance report records reproducible evidence.
