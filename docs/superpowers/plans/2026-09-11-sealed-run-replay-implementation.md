# Sealed Run Replay — Implementation Plan

> **Source of truth:** `docs/superpowers/specs/2026-09-11-sealed-run-replay-spec.md`  
> **Product requirements:** `docs/superpowers/specs/2026-09-11-sealed-run-replay-prd.md`  
> **UI:** `docs/superpowers/specs/2026-09-11-sealed-run-replay-ui-design.md`  
> **Technical design:** `docs/superpowers/specs/2026-09-11-sealed-run-replay-technical-design.md`  
> **Testing:** `docs/superpowers/plans/2026-09-11-sealed-run-replay-verification.md`  
> **Delivery style:** tracer-bullet vertical slices, red → green at approved public seams

## 1. Delivery objective

Deliver a true visual replay of recorded Runs in Evaluation without making Replay depend on Simulator or Mid-MPC throughput.

The shortest valid product path is:

```text
Product Run
  ↓
backend-owned full Decision Trace
  ↓
Replay READY
  ↓
read-only replay API
  ↓
Evaluation selects Run
  ↓
seek stored frame on shared Situation Display
  ↓
play/pause/rate
  ↓
event timeline
  ↓
Historical AIS uses same player
  ↓
real Mid-MPC acceptance
```

Do not start by redesigning Evaluation visuals in isolation. The first slice must prove evidence capture/readback through the product execution path.

## 2. Non-negotiable implementation rules

1. Replay controls never invoke Simulator/Planner/tracker/guidance/control execution.
2. New normal product replay-capable Runs persist full per-tick evidence independent of the browser.
3. Existing `colav_simulator.decision_replay` remains compatible.
4. `trajectory.parquet` does not become a fabricated source of missing planner/risk facts.
5. Browser never accepts/constructs arbitrary local evidence paths.
6. Telemetry Projection remains the browser interpretation authority.
7. Situation Display remains shared between Live and Replay.
8. Continuous interpolation is bounded between adjacent sealed frames; discrete facts are not interpolated.
9. Replay readiness is separate from `result_ready` and Evaluation verdicts.
10. Historical AIS benchmark authority remains intact.
11. Active Session execution-rate UI uses Simulation Rate terminology; Replay uses Replay Speed.
12. Each ticket must leave the branch demonstrably coherent at its public seam.
13. Red tests precede behavior changes within each vertical slice.
14. Missing evidence is typed; never default missing risk/planner values to `CLEAR`, zero or nominal.
15. Any contradiction with V1 PRD/UI Spec, Threat Management, Encounter Lifecycle, L4 or Independent Evaluator authority stops implementation for review.

## 3. Approved test seams

### Seam A — Replay service/API

Given a recorded Run ID, a caller can discover replay state and read a bounded historical frame/event window without simulation execution.

### Seam B — Replay Controller/Clock

Given deterministic historical frames/events and a deterministic clock, replay presentation can seek/play/pause/change rate/navigate events correctly.

### Seam C — Browser product behavior

A completed real Run opens in Evaluation and displays/scrubs/replays recorded facts on the shared Situation Display while no Active Session mutation endpoint is called.

The strongest Definition of Done is Seam C. Lower seams isolate deterministic failures.

## 4. Branch/worktree strategy

Recommended implementation branch:

```text
feature/sealed-run-replay
```

Do not perform unrelated Mid-MPC/VO/GNC behavior changes on the replay branch. If capture overhead exposes an algorithm timing problem, record it separately rather than tuning the algorithm to make replay tests pass.

## 5. Slice 1 — Make a product Run replay-addressable

### Goal

After a normal product Run finishes, Evaluation/backend can truthfully say whether it has FULL replay evidence and expose its descriptor.

### Red tests first

Add behavior tests proving:

- a product Run emits/finishes full trace evidence through the normal product execution path;
- browser disconnect does not stop trace capture;
- Decision Replay can still read/probe the resulting evidence;
- the descriptor reports `READY/FULL` only after index/artifact integrity is complete;
- a trace persistence failure reports `INCOMPLETE`, not `READY`;
- replay-ready may become true before result-ready;
- Active Session execution state remains independent of replay readiness.

### Implementation work

- factor the Decision Trace writer responsibility into a reusable evidence component;
- wire normal product sessions to it;
- persist trace events/index/digest through the same Run evidence root;
- publish replay readiness/reason for a Run;
- add read-only run replay descriptor service/API;
- expose a minimal Evaluation run selector/state panel capable of showing `FULL/REDUCED/INCOMPLETE/UNAVAILABLE` without yet rendering the chart.

### Demo

1. Create a normal product VO or Mid-MPC session from Config.
2. Run to terminal state.
3. Switch to Evaluation.
4. The Run appears and reports `REPLAY READY · FULL EVIDENCE` with time range/frame count.
5. Existing Decision Replay `summary` can inspect the same Run directory.

### Exit criteria

- no debug-only `decision_replay record` command is required to make a normal product Run replay-capable;
- no browser-owned recorder exists;
- current Decision Replay CLI/skill compatibility tests remain green.

## 6. Slice 2 — Seek one historical frame on the real Situation Display

### Goal

A user can select a completed Run and directly seek to a time in Evaluation, showing the historical vessel situation without stepping simulation.

### Red tests first

- replay window API returns requested frame window plus sufficient bracketing data;
- API rejects invalid Run IDs/path traversal and oversized/unbounded windows;
- a browser seek to `t=...` results in the correct historical source frame/bracket;
- Replay seek causes zero Active Session create/start/pause/step/speed/reset calls;
- source frame facts pass through existing Telemetry Projection semantics;
- no browser raw gzip/Parquet parse occurs.

### Implementation work

- add bounded frame-window reader/API over Decision Trace;
- add replay source adapter to historical Telemetry Envelope input;
- create Replay API client/controller skeleton;
- render selected historical source frame through shared Situation Display;
- implement paused timeline/playhead and direct seek;
- add loading/error/stale-request cancellation behavior.

### Demo

Open a completed Mid-MPC Run, drag from `30 s` directly to `450 s`, and show the historical ownship/targets/planner context immediately without iterating 420 seconds of simulator time.

### Exit criteria

- direct seek is independent of original solver runtime;
- source-frame parity is proven at multiple timestamps.

## 7. Slice 3 — Add deterministic Play/Pause and Replay Speed

### Goal

Turn the seekable historical inspection view into a real player with rates up to 20×.

### Red tests first

- deterministic ReplayClock advances `playhead = elapsed_wall × rate` within bounds;
- pause freezes playhead;
- rate changes preserve continuity;
- end transitions to `ENDED`;
- seek from PLAYING/ENDED cancels stale prefetch and lands at requested time;
- positions/headings interpolate correctly between two known sealed frames;
- discrete risk/planner/lifecycle values remain bound to recorded source frame;
- no extrapolation when upper frame is missing;
- high speed may skip paint frames but not event evidence.

### Implementation work

- create pure ReplayClock;
- add play/pause/end/restart behavior;
- add rate presets `0.25×` through `20×`;
- add frame-window prefetch/buffering;
- extract/share pure kinematic interpolation math from live presentation buffering;
- keep live buffering queue/delay logic separate;
- show replay time/source frame/evidence state.

### Demo

Replay a 60-second segment at 1× then 20×. Browser instrumentation shows no algorithm/Simulator calls; visual playhead reaches the same historical end state.

### Exit criteria

- Replay Speed is presentation-only;
- Mid-MPC compute utilization is not required for replay progression.

## 8. Slice 4 — Add event-synchronized timeline and inspection navigation

### Goal

Let the user navigate behavior changes rather than watching the whole run linearly.

### Red tests first

- events API preserves recorded event order/identity/time;
- Previous/Next Event is correct after arbitrary seek and rate changes;
- event jump chooses correct source frame/bracket;
- marker filters affect visibility only, never event data;
- dense marker aggregation does not delete underlying events;
- selected vessel/event changes inspection state only.

### Implementation work

- add canonical event journal endpoint/projection;
- render typed timeline markers;
- implement Previous/Next Event;
- add event filtering/popup/focus;
- wire Inspection rail to playhead + target/event selection;
- optionally add `View in Replay` from a time-bearing Results item where existing data supports it.

### Demo

Jump from `planner action` to `CPA` to `recovery` events in a recorded run and inspect the corresponding chart/risk/planner state without manually scrubbing.

### Exit criteria

- event navigation is stable and evidence-backed;
- browser does not derive new risk transition events by frame differencing.

## 9. Slice 5 — Complete Evaluation IA and Historical AIS convergence

### Goal

Make Evaluation a coherent historical-inspection workface and eliminate misleading Playback terminology while preserving Historical AIS.

### Red tests first

- Evaluation local views are `Replay | Results | Evidence | Historical AIS`;
- changing local view never mutates Active Session;
- existing Historical AIS mode/workflow/deploy behavior remains available;
- a Historical AIS workflow/run with a Run ID can open the shared Replay view;
- Historical AIS does not instantiate a separate replay player;
- Deployment execution-rate UI says Simulation Rate;
- Replay controls say Replay Speed;
- requested/effective simulation rate display remains correct.

### Implementation work

- move current Historical AIS benchmark DOM/rendering behind local view ownership;
- add Results/Evidence local views bound to selected Run using existing available data;
- add `Open Replay` bridge from Historical AIS run/workflow evidence;
- change user-facing live-rate terminology;
- preserve OpenBridge component reuse and current chart palette behavior;
- complete 1440×900/1920×1080 layout behavior.

### Demo

Run a Historical AIS Counterfactual session, open Evaluation > Historical AIS to inspect benchmark evidence, then open its Run in Evaluation > Replay and play it through the same shared chart used for an ordinary paper scenario Run.

### Exit criteria

- one visual player exists;
- Historical AIS evidence is retained, not deleted;
- product terminology no longer conflates execution and replay.

## 10. Slice 6 — Evidence degradation, performance and final acceptance

### Goal

Prove the feature under legacy, failure, performance and real Mid-MPC conditions and freeze release evidence.

### Red/acceptance tests

- legacy no-full-trace Run reports `REDUCED` without invented planner/risk facts;
- truncated trace reports `INCOMPLETE` and trusted end boundary;
- failed/crashed Run replays through last trustworthy frame where available;
- unsupported/corrupt trace fails closed;
- full replay frame parity matches captured live canonical facts;
- real product Mid-MPC Run replays at 20× with zero solver execution;
- capture overhead is measured on VO/Fan/Mid-MPC;
- random seek/open performance is measured on representative 600 s trace;
- if measured seek performance is unacceptable, implement only the smallest compatible derived index/cache/chunk strategy necessary and rerun the same acceptance tests;
- Decision Replay probes remain green;
- Historical AIS one-player integration remains green;
- full backend/frontend/static/browser gates pass or failures are reported truthfully.

### Acceptance evidence

Produce a final report containing:

```text
baseline commit
implementation commit
reference Runs
trace schemas/digests
capture overhead measurements
replay open/seek measurements
1×/5×/10×/20× presentation observations
zero-execution-call proof
live/replay parity evidence
legacy/incomplete behavior
Historical AIS integration result
test commands/results
known limitations
```

### Exit criteria

All canonical Spec success criteria are demonstrated by recorded evidence, not developer assertion.

## 11. Ticket dependency graph

Recommended GitHub tickets map directly to these slices:

```text
REPLAY1 Product Run → FULL replay descriptor
  ↓
REPLAY2 Direct seek → shared Situation Display
  ↓
REPLAY3 Play/Pause/Replay Speed
  ↓
REPLAY4 Event timeline + inspection
  ↓
REPLAY5 Evaluation IA + Historical AIS + terminology
  ↓
REPLAY6 Degraded evidence + performance + final acceptance
```

If implementation proves Slice 5 can safely proceed after Slice 2, it may be developed in parallel with Slices 3–4 on an integration branch, but REPLAY6 remains blocked by all functional slices.

## 12. TDD operating procedure per ticket

For every ticket:

1. identify the smallest user-visible behavior at the approved seam;
2. add one failing behavior test;
3. implement only enough to make it pass;
4. repeat vertical tracer bullets;
5. run focused suite;
6. run affected broader suites;
7. review for second-truth/authority violations;
8. only then perform safe refactoring with tests green;
9. record evidence in ticket/PR.

Avoid horizontal “write all API, then all UI, then tests” implementation.

## 13. Expected backend file impact

Likely affected areas:

- `colav_simulator/decision_replay/` — reusable full trace persistence/reader compatibility;
- `colav_simulator/experiment/` — only where a clean evidence hook belongs; do not move replay UI semantics into simulation core;
- `gui_server/` — replay repository/service/routes and product-session capture/readiness integration;
- tests covering decision trace, session API/finalization and new replay contracts.

Prefer a dedicated replay router/service over growing `gui_server/main.py` with another large subsystem.

## 14. Expected frontend file impact

Likely new responsibilities under `web_gui/modules/`:

- Replay API adapter;
- ReplayClock;
- ReplayController;
- Replay source/projection adapter;
- Evaluation Replay host;
- shared pure interpolation helper.

Existing expected reuse:

- `telemetry-projection.js`;
- `situation-display.js`;
- OpenBridge components/tokens;
- existing Evaluation/Historical AIS modules after ownership cleanup.

`active-session-runtime.js` must not become Replay control authority.

## 15. Review checklist before each merge

- Does this change cause Replay to execute anything?
- Does it create a second telemetry/risk/planner interpretation?
- Does it silently downgrade missing evidence?
- Does it break Decision Replay trace/probes?
- Does it introduce browser filesystem/raw artifact authority?
- Does it conflate Simulation Rate and Replay Speed?
- Does it mutate Historical AIS workflow semantics?
- Does it make a performance claim without measurement?
- Does it test external behavior rather than internals?

Any “yes” outside an explicitly approved migration is a blocker.
