# Sealed Run Replay — Solution Pack

> **Feature:** Solver-independent visual replay of recorded Runs  
> **Baseline:** `main@1c2b69acc52fdd8dfa515d38f86a679c0b4ef082`  
> **Spec branch:** `spec/run-replay-evaluation`

## 1. Why this pack exists

The current product can execute COLAV Runs and smooth live telemetry, but it does not yet provide a true seekable historical player for a completed Run. Mid-MPC execution speed therefore unnecessarily constrains visual review if users rely on Deployment to watch behavior.

This pack freezes the product, UI, architecture, delivery and verification contracts for **Sealed Run Replay** before implementation.

The central invariant is:

```text
Replay reads recorded evidence.
Replay never executes Simulator or Planner.
```

## 2. Normative documents

### Canonical feature Spec

`2026-09-11-sealed-run-replay-spec.md`

Matt `to-spec` style source of truth covering:

- Problem Statement;
- Solution;
- 52 User Stories;
- Implementation Decisions;
- Testing Decisions;
- Out of Scope;
- Further Notes.

### Product Requirements

`2026-09-11-sealed-run-replay-prd.md`

Defines:

- product goals/non-goals;
- terminology;
- Evaluation IA;
- replay readiness states;
- PR-001 through PR-022;
- product success criteria.

### UI Design

`2026-09-11-sealed-run-replay-ui-design.md`

Defines:

- 1920×1080 and 1440×900 replay layouts;
- Run Context / Situation Display / Inspection rails;
- seekable event timeline;
- Play/Pause/Replay Speed behavior;
- FULL/REDUCED/INCOMPLETE/UNAVAILABLE states;
- Historical AIS local view;
- Simulation Rate terminology cleanup;
- accessibility/visual review requirements.

### Technical Design

`2026-09-11-sealed-run-replay-technical-design.md`

Defines:

- Decision Trace as full replay evidence;
- product trace capture/finalization;
- Replay Descriptor / window / events contracts;
- read-only API architecture;
- shared Telemetry Projection/Situation Display;
- ReplayClock/Controller/source adapter;
- continuous vs discrete evidence semantics;
- Historical AIS integration;
- security/performance/failure boundaries.

### Implementation Plan

`../plans/2026-09-11-sealed-run-replay-implementation.md`

Six tracer-bullet vertical slices:

1. normal product Run → FULL replay descriptor;
2. direct seek → shared Situation Display;
3. Play/Pause/Replay Speed;
4. event timeline + inspection;
5. Evaluation IA + Historical AIS + terminology;
6. degraded evidence + performance + final acceptance.

### Verification & Acceptance Plan

`../plans/2026-09-11-sealed-run-replay-verification.md`

Defines:

- approved test seams;
- deterministic fixture strategy;
- evidence/API/controller/interpolation/parity/browser tests;
- no-reexecution proof;
- degraded/failure/security/accessibility matrices;
- performance characterization;
- real Mid-MPC and Historical AIS acceptance campaigns;
- final release-gate checklist.

## 3. Canonical terminology

```text
Simulation Rate
  Active Session execution request; compute-limited.

Live Presentation Buffer
  short delayed interpolation of actually received live frames.

Sealed Run Replay
  read-only visual historical player over recorded Run evidence.

Replay Speed
  presentation-only multiplier for Sealed Run Replay.

Reproduction
  re-execution of frozen RunSpec for reproducibility verification.

Decision Replay
  offline diagnostic probes over the same full Decision Trace.

Historical AIS Replay
  historical-world execution mode whose resulting Run may be opened in Sealed Run Replay.
```

## 4. Primary architecture

```text
SimulationSession snapshot
       │
       ├────────→ Live telemetry → Live Presentation Buffer
       │                           → Telemetry Projection
       │                           → Situation Display
       │
       └────────→ backend-owned full Decision Trace
                                     │
                    ┌────────────────┴───────────────┐
                    ▼                                ▼
             Decision Replay                    Replay API
                probes                         Run ID/time
                                                     │
                                                     ▼
                                             Replay Controller
                                               Replay Clock
                                                     │
                                                     ▼
                                             Telemetry Projection
                                                     │
                                                     ▼
                                             Situation Display
```

## 5. Approved test seams

### A — Replay service/API

Recorded Run ID → descriptor / bounded frames / events, no simulator execution.

### B — Replay Controller/Clock

Immutable frames/events + deterministic clock → seek/play/pause/rate/event behavior.

### C — Browser Evaluation Replay

Real completed Run → shared situation display and timeline, with zero Active Session mutation calls.

## 6. Required evidence states

```text
CAPTURING
READY       → FULL replay evidence
REDUCED     → limited legacy trajectory/evidence
INCOMPLETE  → trace gap/truncation/integrity limitation
UNAVAILABLE → no supported replay evidence
```

Execution state, Replay state and Evaluation result remain separate axes.

## 7. Evaluation transition design

Current:

```text
Config | Deployment | Evaluation
```

Evaluation local views:

```text
Replay | Results | Evidence | Historical AIS
```

Historical AIS content is retained. It no longer owns a separate player. Historical AIS-produced Runs open in the same Replay view.

Future migration target:

```text
Runs > Run Detail > Replay
```

The Replay domain/API/controller must not be page-owned so this migration is mechanical.

## 8. Definition of Done

A feature implementation is accepted only when a normal product Mid-MPC Run can be completed once and then:

- opened in Evaluation;
- directly seeked to arbitrary recorded time;
- played at presentation rates including 20×;
- navigated by recorded events;
- inspected using the shared Situation Display/Telemetry Projection;
- diagnosed with existing Decision Replay probes from the same full trace;
- replayed with zero Replay-induced session mutation or solver execution;
- truthfully degraded for legacy/incomplete evidence;
- used by Historical AIS Run playback without a second player;
- verified by the complete acceptance plan and recorded acceptance evidence.

## 9. Agent contract

Implementation tickets reference this pack and the canonical Spec. An agent must stop and surface a contradiction instead of:

- adding a second browser risk/planner truth;
- re-running Simulator to fill missing replay evidence;
- treating reduced evidence as full;
- weakening existing safety/evaluation gates;
- changing algorithms to make Replay look smoother;
- conflating Simulation Rate and Replay Speed;
- replacing Historical AIS workflow semantics.
