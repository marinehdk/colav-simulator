# Sealed Run Replay — Technical Design

> **Status:** Implementation design companion to the canonical Spec/PRD  
> **Baseline:** `main@1c2b69acc52fdd8dfa515d38f86a679c0b4ef082`  
> **Core rule:** read recorded evidence; never execute Simulator/Planner during visual replay

## 1. Executive architecture

The implementation reuses the repository's existing Decision Replay evidence concept and existing Web Situation Display.

```text
                    ACTIVE EXECUTION
RunSpec → SimulationSession.advance()
                    │
                    ├──────────────→ Live telemetry → Live Presentation Buffer
                    │                                 → Telemetry Projection
                    │                                 → Situation Display
                    │
                    └──────────────→ Decision Trace persistence
                                      (browser-independent)
                                               │
                                               ▼
                                      runs/<run_id>/decision/
                                               │
                          ┌────────────────────┴────────────────────┐
                          ▼                                         ▼
                 Decision Replay CLI                         Replay API
                    / probes                              descriptor/window/events
                                                                    │
                                                                    ▼
                                                             Replay Controller
                                                             + Replay Clock
                                                                    │
                                                                    ▼
                                                             Replay Source Adapter
                                                                    │
                                                                    ▼
                                                             Telemetry Projection
                                                                    │
                                                                    ▼
                                                             Situation Display
```

The leverage point is the recorded per-tick Decision Trace. Visual replay and offline diagnostic probes become two consumers of the same evidence.

## 2. Existing primitives to preserve

### 2.1 `SimulationSession`

The session already produces one `SessionSnapshot` per simulation step with:

- sequence;
- sim time;
- session state;
- step timing;
- full payload;
- step events.

It also retains frames for final evaluation/evidence.

### 2.2 Decision Replay subsystem

`colav_simulator.decision_replay` already provides:

- full per-tick recording;
- `decision/frames.jsonl.gz`;
- `decision/events.jsonl`;
- `decision/index.json`;
- `TraceBundle` read-only offline access;
- deterministic probes over stored evidence;
- explicit `full` vs `reduced` evidence semantics.

This is the preferred full replay evidence seam. Do not introduce a separate browser-only recorder.

### 2.3 `trajectory.parquet`

Finalized Runs persist reduced trajectory rows suitable for evaluation/reproduction hashes and basic historical facts. Planner evidence is deliberately reduced. It is not the source for a full replay claim.

The existing project Decision Replay skill also records a practical constraint: Parquet access has caused in-process instability in this environment. Browser replay must not motivate direct in-process/raw-browser Parquet parsing.

### 2.4 Web modules

Current useful boundaries include:

- `active-session-runtime.js` — Active Session network/control authority;
- `telemetry-playback.js` — live buffered presentation only;
- `telemetry-projection.js` — read-only telemetry interpretation;
- `situation-display.js` — chart/ENC/vessel/planner visualization;
- `session-runtime-instance.js` — current live runtime/projection wiring;
- Historical AIS controller/projection/render modules — benchmark UI authority.

Replay must reuse projection/display and avoid Active Session control authority.

## 3. Design boundaries

### 3.1 Replay evidence boundary

A **Decision Trace** is the durable source for full visual replay. It is immutable historical evidence once finalized.

The minimum trace record remains conceptually:

```text
sequence
sim_time
step_time_ms
state
payload
events
```

The trace index supplies:

```text
schema
tick_count
t_start
t_end
frame digest
truncated / completeness state
```

### 3.2 Replay API boundary

The browser never receives a local filesystem path. It asks for a Run ID and a simulation-time window.

### 3.3 Replay presentation boundary

Replay owns only:

```text
selectedRunId
replayDescriptor
playheadSimTime
playbackState
replayRate
loadedFrameWindow
loadedEvents
inspectionSelection
loading/error state
```

It does not own RunSpec, Active Session state or planner state.

### 3.4 Shared projection/display boundary

Replay must feed historical frame facts through the existing Telemetry Projection/Situation Display semantics. Any new adapter is only responsible for source/wrapper normalization.

## 4. Evidence capture design

### 4.1 Current gap

The standalone Decision Replay recorder writes full frames, but normal product Web Runs do not guarantee this trace as an artifact. This is the primary backend gap.

### 4.2 Refactor direction

Extract the reusable trace-writing responsibility from the debug-only recorder into a backend evidence component usable by both:

- the Decision Replay `record` command;
- normal product Active Sessions.

Recommended logical API:

```text
TraceSink.open(run_identity)
TraceSink.append(session_snapshot)
TraceSink.close(final_events, final_state)
TraceSink.fail(reason)
```

The concrete naming can differ. The important contract is one producer-facing evidence sink.

### 4.3 Execution overhead

Do not copy the debug recorder's synchronous “jsonable + write + flush + whole-file gzip” path into the live simulation loop without measurement.

Preferred product behavior:

1. detach/enqueue one immutable snapshot record with bounded overhead;
2. a background writer serializes/persists trace records;
3. queue/backpressure is bounded;
4. no frame is silently discarded;
5. persistence failure marks Replay evidence incomplete;
6. where in-process retained frames remain available at normal FINISHED finalization, the replay finalizer may reconcile/repair a temporary capture gap before declaring `READY`;
7. a process crash may leave a valid partial trace marked `INCOMPLETE`.

A release ticket must benchmark the selected strategy before freezing queue/size/timing budgets.

### 4.4 Artifact finalization order

Recommended product order after physical execution ends:

```text
Session FINISHED/FAILED
        ↓
stop trace admission
        ↓
flush/verify Decision Trace + event journal + index
        ↓
publish replay_status READY/INCOMPLETE/REDUCED
        ↓
continue expensive Evaluation/report work
        ↓
publish result_ready
```

This extends the existing separation between terminal execution state and report readiness.

Replay readiness does not imply Evaluation readiness.

### 4.5 Full vs legacy evidence

New product Runs should target `FULL` evidence.

Legacy Runs:

- full Decision Trace present → `READY/FULL`;
- no Decision Trace but reduced trajectory exists → `REDUCED`;
- trace exists but truncated/corrupt → `INCOMPLETE`;
- no supported artifact → `UNAVAILABLE`.

Reduced replay is optional in the first vertical slice; the state contract is mandatory even if the UI initially renders only a reduced summary rather than trajectory animation.

## 5. Trace storage / seek strategy

### 5.1 First implementation

Prefer compatibility with the existing Decision Trace schema before inventing a new format.

The backend may build a derived replay index/cache for fast time-window reads. This index/cache is not canonical evidence and can be discarded/rebuilt.

### 5.2 Existing v1 limitation

The current `TraceBundle` scans times and repeatedly opens/seeks a gzip text stream. This is appropriate for occasional CLI probes but may be inefficient for frequent UI scrubbing.

Implementation should first measure representative trace sizes and seek behavior.

### 5.3 Escalation only if measured need exists

If the existing trace plus server-side cache cannot meet measured local replay UX requirements, introduce a backward-compatible derived or v2 chunked representation, for example:

```text
decision/index.json
  chunks:
    - t_start/t_end
    - sequence_start/end
    - frame_count
    - relative artifact identity
    - digest
```

The exact chunk policy must be versioned and chosen from measurement. Existing v1 traces remain readable by `TraceBundle` and the Replay API.

Do not make a new format a prerequisite without evidence.

### 5.4 Capture policy, retention, and disk budget (2026-09-11 orchestrator amendment)

Measured machine reality (2026-09-11): `runs/` already holds 6.1 GB across 2 689 run dirs; the development disk is near capacity; an existing 120-tick multiship trace occupies 8.9 MB `frames.jsonl.gz` plus an uncompressed 9.4 MB `decision/events.jsonl`. Default-on FULL capture without a budget would grow disk unboundedly.

Decisions:

1. **Capture default ON for normal product Active Sessions**, with an explicit opt-out (session-create/API/config level). Default-on is required by the product goal ("a normal product Run is replay-ready"); the opt-out covers disk-constrained or performance-sensitive use.
2. **Budgeted retention for Decision Traces.** The backend enforces a configurable total budget for `decision/` trace directories (default single-digit GiB, pinned by #70 measurement). On trace finalization, oldest-finalized traces beyond the budget are pruned LRU; pruning only ever removes replay evidence directories, never manifests, trajectories, reports, or artifacts. A pruned Run must be reported by the Replay Descriptor as its truthful degraded state (`REDUCED` or `UNAVAILABLE`), never `INCOMPLETE-with-truncated-claim`. Pruning is recorded as a lifecycle event.
3. **Event journal size control.** The per-tick frame records already carry `events`; the close-time `decision/events.jsonl` journal may be gzip-compressed (`events.jsonl.gz`) when measurement shows it dominates trace size. `TraceBundle`/Replay readers must accept both forms (the existing reader already falls back to the run-level journal). Frame content is unchanged.
4. **Per-run capture budget.** The bounded capture queue (#4.3) must also have a bounded total-bytes budget per Run; exceeding it is a typed `INCOMPLETE` failure reason, not silent truncation.

Nothing in this section weakens evidence immutability: retention is an explicit, logged, budget-driven deletion policy applied only to replay evidence directories, and the descriptor always tells the truth afterwards.

## 6. Backend replay domain model

### 6.1 ReplayEvidenceState

```text
CAPTURING
READY
REDUCED
INCOMPLETE
UNAVAILABLE
```

Suggested reasons include:

```text
TRACE_MISSING
TRACE_SCHEMA_UNSUPPORTED
TRACE_DIGEST_MISMATCH
TRACE_TRUNCATED
TRACE_GAP
REDUCED_TRAJECTORY_ONLY
RUN_NOT_FOUND
```

No reason is represented as implicit null/zero if it affects trust.

### 6.2 ReplayDescriptor

Versioned public shape, conceptually:

```json
{
  "schema_version": "colav.run-replay.descriptor@1",
  "run_id": "...",
  "run": {
    "execution_state": "FINISHED",
    "scenario_id": "head_on",
    "requested_algorithm": "mid_mpc_ipopt",
    "executed_algorithm": "mid_mpc_ipopt",
    "tracker_id": "god",
    "result_ready": true
  },
  "replay": {
    "state": "READY",
    "evidence_level": "FULL",
    "trace_schema": "colav.decision-replay.v1",
    "frame_count": 6001,
    "t_start": 0.0,
    "t_end": 600.0,
    "trusted_t_end": 600.0,
    "frames_sha256": "...",
    "truncated": false
  },
  "events": {
    "count": 42,
    "categories": ["encounter", "planner", "runtime"]
  },
  "capabilities": {
    "full_frame": true,
    "planner_detail": true,
    "risk_detail": true,
    "continuous_interpolation": true
  }
}
```

Exact fields should reuse current manifest terminology rather than invent parallel identities.

### 6.3 ReplayFrameWindow

Versioned bounded response:

```json
{
  "schema_version": "colav.run-replay.window@1",
  "run_id": "...",
  "requested": {"from_s": 210.0, "to_s": 216.0},
  "frames": [
    {
      "sequence": 2101,
      "sim_time": 210.0,
      "state": "RUNNING",
      "payload": {},
      "events": []
    }
  ],
  "before": null,
  "after": null
}
```

The service should ensure the client can obtain one predecessor and successor frame needed to bracket a playhead near window boundaries. This can be explicit `before/after` fields or included sentinel frames.

### 6.4 ReplayEventJournal

Public event response keeps canonical identity/order/time/details and may add presentation category labels only if those are backend-owned projections.

Browser code does not derive new operational events by diffing frames.

## 7. HTTP API design

Recommended read-only routes:

```text
GET /api/runs?replayable=true&limit=<n>
GET /api/runs/{run_id}/replay
GET /api/runs/{run_id}/replay/window?from=<seconds>&to=<seconds>
GET /api/runs/{run_id}/replay/events
```

If a Run listing route already emerges elsewhere during implementation, reuse it rather than adding a duplicate catalog.

### 7.1 Constraints

- `run_id` resolves only beneath the configured Run root.
- reject path separators/traversal identities;
- enforce a bounded time-window/request size;
- reject unsupported schema/integrity states with typed responses;
- no POST/PATCH/DELETE replay controls are required because replay state is client presentation state;
- replay endpoints never create/replace Active Session.

### 7.2 Static chart context

The Replay API must make available whatever immutable/static context the shared Situation Display requires but which is not repeated in every stored frame, such as ENC navigation area or session specification.

Prefer descriptor/static-context projection over repeating static data in every window response.

## 8. Live/Replay projection parity

### 8.1 Goal

At a source frame boundary, Replay should feed the same canonical historical facts into `telemetry-projection.js` that Deployment received when that frame was captured.

### 8.2 Adapter strategy

Introduce a source adapter that converts one stored Decision Trace record + immutable Run/static context into the versioned Telemetry Envelope shape expected by Telemetry Projection.

The adapter may set a presentation namespace such as:

```text
presentation.mode = HISTORICAL_REPLAY
presentation.source_sequence
presentation.source_sim_time_s
presentation.interpolated = true/false
```

It must not set live transport/session connectivity state as if the Run were active.

### 8.3 Avoid a second projection

Do not duplicate these interpretations in Replay code:

- risk projection;
- planner display selection policy;
- target position source policy;
- operational timeline semantics;
- outcome interpretation.

If current Telemetry Projection depends on Active Session-only wrapper fields, refactor those dependencies so both sources can supply the same input contract.

## 9. Continuous interpolation design

### 9.1 Shared math

Extract pure kinematic interpolation helpers from `telemetry-playback.js` into a reusable module. Reuse:

- scalar linear interpolation;
- vessel position/velocity interpolation;
- shortest-angle heading/course interpolation.

Do not share:

- live delay reserve;
- live queue length;
- live measured/requested rate reconciliation;
- terminal drain behavior;
- live buffering status.

### 9.2 Replay rule

For playhead `t` bracketed by source frames `A` and `B`:

```text
continuous vessel presentation = interpolate(A, B, alpha)
discrete canonical source facts = A
source evidence cursor = A.sequence
```

If `A == B` or no upper frame exists, show `A` exactly.

Never extrapolate.

## 10. Frontend Replay Controller

Recommended new modules:

```text
web_gui/modules/replay-api.js
web_gui/modules/replay-clock.js
web_gui/modules/replay-controller.js
web_gui/modules/replay-projection.js
web_gui/modules/evaluation-replay.js
```

Names can adapt to repository conventions; responsibilities should stay separated.

### 10.1 ReplayApi

Responsibilities:

- list/select Runs;
- fetch descriptor;
- fetch frame windows;
- fetch events;
- abort superseded seek/prefetch requests;
- no DOM.

### 10.2 ReplayClock

Pure deterministic presentation clock.

Inputs:

```text
wall clock
rate
playhead
start/end bounds
play/pause
```

Outputs:

```text
next playhead
ENDED transition
```

It does not fetch data or render.

### 10.3 ReplayController

State authority for Replay presentation.

Suggested state:

```text
runId
descriptor
status = EMPTY | LOADING | READY | BUFFERING | ERROR
playback = PAUSED | PLAYING | ENDED
rate
playhead
window
events
selectedEventId
selectedTargetId
requestGeneration
```

Actions:

```text
selectRun
play
pause
seek
setRate
prevEvent
nextEvent
selectTarget
prefetch
```

### 10.4 Request race safety

Rapid timeline dragging can issue overlapping window requests. Each request must carry generation/cancellation semantics; a stale response cannot overwrite a newer seek.

### 10.5 Prefetch

Controller keeps a window around the playhead and requests the next window before exhaustion. Prefetch horizon can scale with Replay Speed.

No exact window length is normative before measurement.

## 11. Replay state machine

```text
NO_RUN
  │ selectRun
  ▼
LOADING_DESCRIPTOR
  ├── error ──→ ERROR
  ├── unavailable ──→ UNAVAILABLE
  └── descriptor ready
           ▼
     LOADING_INITIAL_WINDOW
           ├── error ──→ ERROR
           └── ready ──→ PAUSED
                           │ play
                           ▼
                         PLAYING
                           │ missing bracket
                           ▼
                        BUFFERING
                           │ data ready
                           └──────→ PLAYING
                           │ pause/seek
                           ▼
                         PAUSED
                           │ t_end
                           ▼
                         ENDED
```

Seek is valid from PAUSED, PLAYING, BUFFERING and ENDED. A seek cancels stale fetch generation and establishes the new playhead.

## 12. Timeline/event model

Timeline uses simulation time as the primary coordinate.

Event jump semantics:

```text
playhead = event.sim_time
selectedEvent = event.identity
source discrete frame = latest frame at/before event time
continuous position = bracket interpolation at event time
```

If the event is outside the trusted replay boundary, do not offer a jump that fabricates a view.

Dense visual markers may aggregate by pixels, but event data remains complete.

## 13. Run discovery and storage abstraction

Current repository is local-first and Run evidence lives beneath the local `runs` root. The first Replay API may enumerate this store.

Keep the API behind a small repository/service abstraction so future V1 SQLite/CAS Run metadata can replace directory enumeration without changing frontend contracts.

Conceptual service:

```text
RunReplayRepository.list_runs()
RunReplayRepository.describe(run_id)
RunReplayRepository.window(run_id, t0, t1)
RunReplayRepository.events(run_id)
```

## 14. Historical AIS integration

Historical AIS benchmark workflow remains separate from normal Run Replay because it owns:

- Dataset selection/source;
- Historical Replay vs Counterfactual execution mode;
- qualification;
- leakage/determinism;
- compare evidence.

Integration point is the produced Run identity/evidence.

```text
Historical AIS workflow
       │
       ├─ Historical Replay run ───→ Run ID ─→ Sealed Run Replay
       └─ Counterfactual run ───────→ Run ID ─→ Sealed Run Replay
```

The Historical AIS local view can emit `Open Replay(run_id)` as an inspection navigation action.

It must not instantiate its own ReplayClock or chart player.

## 15. Active Session terminology migration

User-visible Deployment controls change from ambiguous playback wording to Simulation Rate.

Internal compatibility identifiers such as `livePlaybackRate` may be migrated incrementally; do not perform a risky wide rename unless tests justify it.

The execution backend can retain `requested_multiplier` / `effective_multiplier` field names for compatibility while UI/domain copy exposes them as Simulation Rate metadata.

`telemetry-playback.js` should be described/documented as live presentation buffering even if the filename remains initially.

## 16. Result/replay readiness split

Current server already separates physical FINISHED from later result generation. Add replay readiness to the session/public snapshot where useful:

```text
execution_state = FINISHED
replay_status = CAPTURING | READY | INCOMPLETE
result_ready = false | true
```

The frontend can therefore switch to Evaluation/Replay immediately after `READY` while Results may still say `GENERATING`.

No old result/replay finalizer may overwrite a newer Active Session's current-session status; historical Run artifacts remain addressable by Run ID independently.

## 17. Failure handling

### Trace write failure

- Run execution/evaluation may continue according to existing policy.
- Replay status becomes `INCOMPLETE` with reason.
- no full replay claim.

### Process crash

- partial durable trace may be readable;
- descriptor uses last trustworthy frame/time;
- UI shows crashed/incomplete state.

### Unsupported schema

- descriptor reports unavailable/incompatible;
- do not reinterpret with current schema silently.

### Missing events

- frame playback may remain possible if trace is valid;
- event navigation capability becomes unavailable/incomplete explicitly.

### Window fetch error

- pause playhead;
- show recorded-data loading/error state;
- retry is read-only;
- never extrapolate.

## 18. Security / local authority

- never accept arbitrary path from browser;
- validate Run ID against the configured run repository;
- resolve and verify paths remain under Run root;
- cap window duration/frame count/response bytes;
- do not expose environment paths in normal descriptor payload;
- replay parser accepts only supported versioned schemas;
- historical evidence is read-only through replay endpoints.

## 19. Performance model

Replay performance has three independent costs:

```text
Evidence capture cost
Storage/window-read cost
Browser projection/render cost
```

None includes solver execution.

### Capture

Benchmark added persistence vs current baseline on product VO/Fan/Mid-MPC runs. If asynchronous capture is used, report queue high-water/backpressure/incomplete events.

### Storage

Measure descriptor/open and random seek/window reads on a representative 600 s full trace. Only add chunked trace representation if measurement demonstrates need.

### Browser

At high Replay Speed, render loop may sample visual updates while playhead keeps correct simulation-time progression. Event list/markers remain complete.

## 20. Test seams

Approved implementation seams derived from the accepted architecture:

### Seam A — Replay service/API

Given one recorded Run, external requests can describe and read historical windows/events without simulator execution.

### Seam B — Replay Controller/Clock

Given deterministic frames/events/clock, public controller behavior correctly plays, pauses, seeks, rates and navigates events.

### Seam C — Product browser Replay

A completed real Run is opened in Evaluation, scrubbed and replayed through the shared Situation Display with zero Active Session mutation calls.

The highest-value end-to-end assertion is Seam C; A/B exist to isolate deterministic contract failures.

## 21. Proposed code impact map

Existing areas expected to change:

```text
colav_simulator/decision_replay/
    reusable trace writer/reader compatibility

gui_server/
    run replay repository/service/API
    product session trace capture + replay readiness

web_gui/modules/
    replay API/controller/clock/source adapter
    shared interpolation helper
    Evaluation local replay host

web_gui/index.html / style.css / app wiring
    local Evaluation navigation and Replay surface
    Simulation Rate terminology

tests/
    backend trace/replay API
    decision replay compatibility
    Web replay controller/projection/browser contracts
```

This map is guidance, not a requirement to put all logic in those exact filenames.

## 22. Migration strategy

1. Preserve current Decision Replay v1 reader/probes.
2. Extract reusable trace persistence without changing CLI behavior.
3. Add normal product trace capture and replay state.
4. Add read-only Replay API over full v1 trace.
5. Add frontend controller and shared projection.
6. Add Evaluation Replay UI.
7. Move Historical AIS presentation into local view and link produced Runs into Replay.
8. Measure seek/capture behavior; only then decide whether trace v2/chunking is required.
9. Keep architecture ready to move into future Runs workface.

## 23. Architectural invariants

- Replay code path contains no simulator advance/run operation.
- Browser never parses raw local evidence files directly.
- Full Replay and Decision Replay share evidence identity.
- Telemetry Projection remains canonical browser interpretation.
- Situation Display remains shared.
- Continuous interpolation is presentation-only and bounded by two sealed frames.
- Discrete planner/risk facts are never interpolated.
- Event identity/order/time is backend evidence.
- Replay readiness does not rewrite execution/evaluation state.
- Historical AIS benchmark authority is preserved.
- Reduced evidence is never promoted by inference.
