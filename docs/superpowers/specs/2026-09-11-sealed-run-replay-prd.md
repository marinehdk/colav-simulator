# Sealed Run Replay — Product Requirements Document

> **Status:** Companion PRD to `2026-09-11-sealed-run-replay-spec.md`  
> **Baseline:** `main@1c2b69acc52fdd8dfa515d38f86a679c0b4ef082`  
> **Current delivery surface:** `Evaluation` workface  
> **Future destination:** `Runs > Run Detail > Replay`

## 1. Purpose

Sealed Run Replay gives Colav-Simulator a true historical player for completed or failed Runs. It lets users inspect recorded trajectories, risk, planner decisions and events at arbitrary presentation speed without re-running the Simulator or the selected COLAV algorithm.

The product problem is not “make Mid-MPC solve faster”. Mid-MPC execution performance and replay inspection speed are separate concerns. Replay removes solver throughput from the inspection path.

## 2. Product principles

1. **Recorded truth only.** Replay is a projection of sealed/durable Run evidence.
2. **No re-execution.** Play, pause, seek and Replay Speed never call Simulator/Planner execution.
3. **One observation surface.** Replay reuses the same situation/telemetry semantics as Deployment.
4. **No invented evidence.** Missing full evidence is shown as reduced/incomplete/unavailable.
5. **Inspection is not intervention.** Replay controls and chart selection are presentation state only.
6. **Historical clarity.** The UI always makes replay visually distinguishable from Live execution.
7. **Backward compatibility.** Existing Decision Replay and Historical AIS workflows remain valid.
8. **Migration-safe architecture.** The player can move from current Evaluation into future Run Detail without redesigning its domain/controller/API.

## 3. Current-state diagnosis

The current product has a compute-limited Active Session Simulation Rate and a short live telemetry buffer. A requested `5×` does not guarantee `5×` wall-clock progress because each simulation step may contain Mid-MPC solve work.

Completed Runs persist trajectory/evaluation/event artifacts, while the existing Decision Replay subsystem separately proves that full per-tick payload evidence can be recorded under the Run and read offline without simulator imports. Normal product Runs do not yet guarantee that full trace.

The current Evaluation workface is mostly Historical AIS benchmark evidence. Historical AIS remains required, but ordinary completed-run replay needs to become a first-class Evaluation capability.

## 4. Personas and jobs

### 4.1 Algorithm / COLAV developer

Primary jobs:

- jump directly to the time where a planner maneuver started or failed;
- compare what was actually recorded before/after a fix;
- inspect Mid-MPC behavior without paying the solver cost again;
- correlate visual track behavior with Decision Replay “why” probes.

### 4.2 V&V / test engineer

Primary jobs:

- verify that replay is a read-only view of immutable evidence;
- inspect original risk/planner/evaluation evidence and event ordering;
- distinguish full, reduced and incomplete historical evidence;
- verify a browser replay against the source Run and recorded artifact identity.

### 4.3 Simulator operator

Primary jobs:

- select a recent completed Run;
- play/pause it;
- drag the timeline;
- change Replay Speed;
- jump to previous/next significant event;
- inspect vessels and risk context without changing historical truth.

## 5. Goals

### G1 — Solver-independent inspection

A completed replay-capable Run shall play at presentation rates independent of the original execution throughput. Mid-MPC is not invoked during Replay.

### G2 — True seeking

The user shall be able to move the Replay playhead to any recorded simulation time without stepping the Simulator through intermediate times.

### G3 — Live/Replay semantic parity

At an exact recorded source frame, the same canonical ownship/targets/planner/risk facts shall be available to the UI in Replay as were captured for Live presentation.

### G4 — Complete event navigation

Recorded material events shall remain available as timeline markers and Previous/Next Event navigation regardless of presentation frame rate.

### G5 — Evidence-grade degradation

Legacy or damaged Runs shall never be silently upgraded into full replay. Evidence state is explicit.

### G6 — Preserve Historical AIS

Existing Historical AIS catalog/workflow/qualification/compare evidence remains available, but it no longer owns the only content of Evaluation. Historical AIS completed Runs use the same visual replay player.

## 6. Non-goals

- guaranteeing Active Session Mid-MPC execution above current compute capability;
- modifying collision-avoidance algorithms or solver equations;
- changing independent Evaluation verdict semantics;
- adding live time-shift/DVR for still-running sessions in the first release;
- reconstructing missing planner state from reduced trajectory rows;
- replacing Historical AIS scenario/counterfactual contracts;
- browser-side raw Parquet/gzip parsing.

## 7. Product terminology

| Term | Product meaning |
|---|---|
| Simulation Rate | Requested rate at which an Active Session advances simulation time; compute-limited. |
| Effective Simulation Rate | Measured realized Active Session time advance relative to wall clock. |
| Live Presentation Buffer | Small delayed real-frame buffer that smooths live vessel motion. |
| Sealed Run Replay | Read-only visual playback of previously recorded Run evidence. |
| Replay Speed | Presentation clock multiplier used only by Sealed Run Replay. |
| Reproduction | Re-execution of the frozen RunSpec to verify reproducibility. |
| Decision Replay | Offline evidence interrogation/probes over the full Decision Trace. |
| Historical AIS Replay | Historical-world execution mode; its resulting Run can later be visually replayed. |

## 8. Information architecture

Current product IA remains:

```text
Config → Deployment → Evaluation
```

Evaluation gains local views:

```text
Replay | Results | Evidence | Historical AIS
```

V1 transition rule:

- `Replay` is the default view when a recent replayable Run exists.
- `Results` shows evaluation/report outputs for the selected Run where available.
- `Evidence` exposes evidence level, identities, artifacts/digests and limitations needed for inspection.
- `Historical AIS` contains the existing benchmark workflow UI and does not implement its own visual player.

Future V1 migration maps the same replay capability into:

```text
Runs > Run Detail > Replay
```

without changing replay domain semantics.

## 9. Replay lifecycle and readiness

Replay readiness is separate from Run execution/evaluation state.

```text
CAPTURING
  ↓
READY          full Decision Trace durable and verified

or

REDUCED        only reduced trajectory/evidence can be displayed
INCOMPLETE     capture exists but has gaps/truncation/integrity failure
UNAVAILABLE    no supported historical replay evidence
```

A failed/crashed Run may still be replayable to its last durable frame. The UI must preserve both facts: e.g. `CRASHED · REPLAY INCOMPLETE`.

## 10. Functional requirements

### PR-001 — Run discovery

Evaluation shall list/select recent completed/failed Runs that have inspectable evidence. Selection is by Run ID, never by arbitrary filesystem path.

### PR-002 — Replay descriptor

For the selected Run, the UI shall receive at least:

- Run ID;
- scenario identity;
- requested/executed algorithm and tracker identity where available;
- execution/evaluation summary states;
- replay evidence state and schema;
- `t_start`, `t_end`, duration and frame count where known;
- event summary/categories;
- static context required by the shared situation display;
- relevant replay artifact digests/identity.

### PR-003 — Play / pause

User can play and pause without altering the Run or Active Session.

### PR-004 — Seek

User can drag or click the timeline to any recorded time. Seek updates the playhead directly; it does not simulate intermediate ticks.

### PR-005 — Replay speed

Supported first-release presets:

```text
0.25× | 0.5× | 1× | 2× | 5× | 10× | 20×
```

Rate affects presentation only.

### PR-006 — Event navigation

User can jump to Previous Event / Next Event. Event identity and order come from recorded evidence.

### PR-007 — Event markers

Timeline displays typed event markers. Initial useful categories include lifecycle/risk, planner health/action, collision/grounding/goal/time-limit, algorithm handoff/recovery and runtime failure where those events exist.

### PR-008 — Event filtering

Marker visibility/filtering changes presentation only and never removes events from evidence.

### PR-009 — Situation surface parity

Replay uses the existing chart/Situation Display semantics for:

- ownship and target vessels;
- ENC/chart context;
- Mission Route and actual tracks;
- Selected/Accepted Planner Output when captured;
- prediction/CPA/risk layers when captured and supported;
- target selection/placard;
- relevant side-rail navigation/risk/planner context.

### PR-010 — Continuous interpolation

Only continuous kinematic presentation facts may interpolate between adjacent recorded frames. No extrapolation outside the recorded bracket.

### PR-011 — Discrete evidence authority

Planner state, lifecycle, risk class, solver result, selected command and event facts are taken from the latest applicable recorded source frame/event. The browser does not synthesize intermediate discrete states.

### PR-012 — Historical indicator

Replay always displays persistent historical status such as `SEALED · HISTORICAL` or an equivalent evidence-qualified historical label. It shall never show `LIVE`.

### PR-013 — End behavior

At `t_end`, replay pauses in an ended state. User can seek backward or restart from the beginning.

### PR-014 — Loading/buffering

When the playhead enters an unloaded window, playback pauses or buffers visibly until recorded data arrives. It does not extrapolate.

### PR-015 — Reduced legacy mode

If only reduced trajectory evidence exists:

- trajectory/navigation facts may be shown if supportable;
- missing planner/risk diagnostics remain unavailable;
- the UI prominently labels `REDUCED EVIDENCE`;
- no full parity claim is made.

### PR-016 — Incomplete evidence mode

If trace capture is truncated/corrupt/gapped, the UI exposes the limitation and never extends beyond the last trustworthy frame.

### PR-017 — Full-trace capture for new product Runs

New replay-capable product Runs shall persist the full per-tick evidence needed for full Replay independently of the browser connection.

### PR-018 — Replay before report completion

Where execution has finished and replay artifacts are durably ready, Replay may become available before expensive evaluation/report generation completes. The UI shall keep Replay readiness and Results readiness distinct.

### PR-019 — Decision Replay compatibility

The evidence used by visual Replay remains consumable by the existing Decision Replay offline reader/probes.

### PR-020 — Historical AIS compatibility

The Historical AIS benchmark view remains available. A Historical AIS Run with replay evidence opens through the same Replay surface.

### PR-021 — Active Session terminology

Deployment execution-rate controls shall be labeled Simulation Rate. If requested and effective rates differ materially, the product shall expose the compute-limited effective state rather than implying that a visual player is running slowly.

### PR-022 — No side effects

Replay operations shall not:

- create/replace an Active Session;
- start/pause/step/reset a session;
- change Simulation Rate;
- run/re-run an algorithm;
- write new evaluation verdicts;
- mutate Run evidence.

## 11. UI requirements

- Primary design target: desktop/large screen, aligned to existing OpenBridge-derived operational surface.
- Main chart remains dominant.
- Timeline and controls stay visible without page-level vertical scrolling on the spatial replay screen.
- Event markers require shape/icon/label semantics, not color alone.
- Historical/evidence state is non-color-only.
- Keyboard users can focus timeline, seek, play/pause and jump events.
- Target selection remains inspection-only.
- 1440×900 and 1920×1080 are required supported review sizes.

Detailed layout and interaction rules are in `2026-09-11-sealed-run-replay-ui-design.md`.

## 12. Data / evidence requirements

### Full replay evidence

The full mode uses a versioned per-tick canonical trace equivalent in fidelity to the existing Decision Trace concept. Each tick must identify sequence, simulation time, source state/payload and tick events sufficient for canonical replay projection.

### Reduced evidence

Reduced trajectory evidence is historical support only. It may not be interpreted as if omitted planner/risk fields were originally `CLEAR`, zero or nominal.

### Integrity

Replay readiness requires:

- supported schema;
- readable index/metadata;
- monotonic frame sequence/time according to schema contract;
- artifact integrity/digest checks where provided;
- bounded Run-owned path resolution.

## 13. Performance requirements

Performance assurance is split into two domains.

### Execution capture overhead

Replay evidence persistence must be characterized on representative VO, Fan-MPC and Mid-MPC product Runs. A release budget is frozen from measured baseline, not guessed in advance. Evidence loss is not an allowed optimization.

### Replay presentation performance

Replay must be solver-independent. A 20× replay request shall not be constrained by Mid-MPC compute because Mid-MPC is not called. If rendering/network cannot paint every recorded source frame at high rate, the playhead may advance and rendering may sample/bracket frames while event evidence remains complete.

A final measured UX budget for initial load/seek shall be established in the verification ticket against a representative 600 s run and recorded in the acceptance report.

## 14. Success criteria

The feature is complete when all of the following hold:

1. A real product Mid-MPC Run completes and produces replay-ready evidence.
2. Evaluation opens that Run and shows historical situation data without running Mid-MPC again.
3. The user can seek directly from early run time to a late run time.
4. Replay works at `1×`, `5×`, `10×`, `20×` presentation rates independently of original execution rate.
5. Browser/network instrumentation proves Replay control creates zero session start/step/speed/reset execution calls.
6. Recorded frame parity tests prove Replay and source capture agree on canonical facts.
7. Event navigation is complete and stable across seeks/rate changes.
8. A reduced legacy run is truthfully degraded rather than fabricated.
9. A failed/truncated run replays only trustworthy evidence and exposes incompleteness.
10. Historical AIS benchmark remains functional and one Historical AIS completed Run uses the same player.
11. Existing Decision Replay probes remain compatible.
12. Full focused tests, full repository tests, frontend tests, static/diff checks and a real browser acceptance session are reported truthfully.

## 15. Release sequencing

Recommended release order:

1. terminology/evidence contract and reusable trace capture;
2. read-only replay API with descriptor/window/events;
3. Replay Controller/clock/projection;
4. Evaluation Replay UI and shared Situation Display;
5. Historical AIS integration/cleanup;
6. final evidence/performance/regression acceptance.

The detailed vertical implementation plan is in `2026-09-11-sealed-run-replay-implementation.md`.
