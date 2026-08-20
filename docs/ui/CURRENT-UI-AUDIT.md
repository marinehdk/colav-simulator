# Current UI Audit

## 1. Purpose And Scope

This document records the current Colav-Simulator Web UI architecture before
the OpenBridge-based product redesign. It is a source-backed inventory, not a
target design and not evidence that planned pages already exist.

Audited surfaces:

- Frontend entry, layout, state, controls, rendering, styling, and responsive behavior.
- FastAPI session lifecycle, REST API, WebSocket telemetry, and evidence endpoints.
- Scenario, algorithm, tracker, and exact capability-combination gates.
- Evaluation and reproduction semantics that the UI must not collapse.
- Existing visual hierarchy and migration risks.

Baseline environment and screenshot evidence are recorded in
[`references/BASELINE.md`](references/BASELINE.md).

## 2. Executive Summary

The current frontend is a single operational console, not a multi-page product.
FastAPI serves one static HTML document. A 3,918-line global JavaScript module
owns DOM state, session orchestration, WebSocket recovery, Canvas rendering,
configuration, telemetry, solver diagnostics, and result loading. A 1,879-line
stylesheet implements a dark three-column dashboard.

The console already contains valuable domain behavior that must survive the
redesign:

- Exact Rule / Scenario / Algorithm / Tracker combination gating.
- `strict_no_fallback=true` session creation.
- One-active-session replacement and cross-tab recovery rules.
- ENC metadata, raster, coordinate conversion, and Canvas render order.
- Separation between current-frame planner data and the latest real solver run.
- SOLVE/HOLD, DCPA/TCPA, COLREG, prediction, event, playback, and evidence semantics.

The primary problem is not missing telemetry. It is missing product structure.
Configuration, live operation, expert diagnostics, and post-run evidence share
one page and equal visual weight. There is no first-level business navigation,
no explicit Configure -> Live Run -> Analysis lifecycle, no run history API,
and no Compare application surface.

## 3. Source Of Truth

Current source and tests outrank older architecture status claims. In
particular, `Design/Colav-Simulator-Architecture.md:3-6` describes a 2026-07-27
snapshot from another branch. Its responsibility boundaries remain useful, but
its capability and evaluator status is stale relative to current code.

Authority order for this audit:

1. Current runtime contracts and implementation.
2. Current capability catalog and focused tests.
3. Current evaluator and evidence contracts.
4. Architecture documents for intended layering and prohibited coupling.
5. Supplied screenshot for visual observations.

## 4. Frontend Architecture

### 4.1 Entry And Delivery

- `gui_server/main.py:905-914` creates the global Web session manager, mounts
  `web_gui` at `/static`, and returns `web_gui/index.html` from `GET /`.
- `web_gui/index.html` is the only application document. There is no frontend
  router, URL-backed page state, bundler, framework, or component runtime.
- `web_gui/app.js` contains 3,918 lines and approximately 253 indexed symbols.
- `web_gui/style.css` contains 1,879 lines.
- Tracked visual assets are the generated ENC tile and two vessel sprites.

### 4.2 Current Page Composition

The page is one shell with all workflows mounted at once:

- `web_gui/index.html:11-33`: header, brand, Beijing time, simulation time,
  and connection state.
- `web_gui/index.html:38-168`: three-column workspace with an initially empty
  left insights column, central Canvas, and right configuration sidebar.
- `web_gui/index.html:45-163`: ENC/Canvas, map tools, layers, legend, event log,
  and playback controls.
- `web_gui/index.html:170-475`: scenario, algorithm, tracker, busy-water editor,
  safety, telemetry, planning, performance, and evidence controls.
- `web_gui/app.js:3863-3892`: boot-time DOM relocation moves safety, telemetry,
  planning, and performance cards into the left column; wraps configuration in
  a scroll region; and creates collapse controls dynamically.

There is no first-level navigation for the confirmed business areas:

1. Scenarios and Conditions.
2. Algorithms and Components.
3. Simulation Run.
4. Validation and Analysis.

There are also no dedicated New Run, Live Run, Run Detail, Replay, Compare,
Batch, or System pages.

### 4.3 State Ownership

`web_gui/app.js:93-193` holds a broad set of mutable globals: catalogs, Canvas
view, layer visibility, WebSocket, current telemetry, active session, render
interpolation, planner surfaces, busy-water drafts, selected targets, and
request coordination.

The DOM also acts as application state:

- `web_gui/app.js:3111-3123` builds the Run request directly from three Select
  elements and forces `strict_no_fallback: true`.
- `web_gui/app.js:3773-3793` recreates a session after scenario, algorithm, or
  tracker changes.
- Configuration draft state and applied runtime state are therefore not
  separate concepts today.

This coupling is the central migration constraint. A new Configure page cannot
write directly into the active session on every field change. It needs an
explicit draft/apply boundary while preserving the existing backend contract.

### 4.4 Existing UI Primitives

The CSS and markup contain reusable visual ideas, but not reusable components:

- Glass/card panels and collapsible sections.
- Selection cards and integration status chips.
- Risk metrics and telemetry cells.
- Planner surface, sparkline, solve timeline, and event terminal.
- Playback bar and map disclosure controls.

All are coupled through global classes, IDs, and imperative DOM writes. They
should be treated as behavior references, not copied as a component system.

## 5. Configure And Capability Flow

### 5.1 Catalog Loading

- `web_gui/app.js:3240-3307` loads `/api/capabilities` and updates rule,
  scenario, algorithm, tracker, dependency, and availability displays.
- `web_gui/app.js:3309-3404` applies exact-combination constraints, repairs an
  invalid selection to a permitted tuple, and disables invalid options.
- A globally available algorithm is not necessarily valid for the selected
  Rule / Scenario / Tracker tuple.

This logic is a validation and evidence boundary. It must not be replaced by
four independent filters or a purely client-authored compatibility matrix.

### 5.2 Capability Semantics

`colav_simulator/experiment/capabilities.py:15-23` defines integration metadata,
but the final execution gate is the exact tuple. `capabilities.py:791-826`
requires:

- A scenario with at least one selectable tuple.
- Available algorithm and tracker dependencies.
- An exact Rule / Scenario / Algorithm / Tracker entry.

Capability grades have distinct meanings, documented in
`Design/Algorithm-Capability-Matrix.md:7-17`:

| Grade | Meaning |
|---|---|
| G0 | Discoverable integration |
| G1 | Short smoke execution |
| G2 | Full closed loop without fallback |
| G3 | Responsibility-matched action and diagnostics versus nominal threat |
| G4 | Multi-seed statistical benchmark under unified evaluation |

Current catalog facts include:

- Rule 13, Rule 14, Rule 15, and canonical multiship have G3-qualified entries
  (`capabilities.py:26-57`).
- Static planning is G1 (`capabilities.py:26-57`).
- `head_on`, both overtaking roles, both crossing roles, and the canonical
  CCTA multiship scenario have G3 entries (`capabilities.py:59-106`).
- `paper_ccta2023_head_on` is G2 functional reconstruction, not numerical paper
  reproduction (`capabilities.py:72-105`).
- Busy-water 16 and 80 are G2 scenario assets, not G3 proof
  (`capabilities.py:95-105`).
- Mid-MPC, VO, SB-MPC, simplified MPC, and Fan-MPC have G3 entries;
  Nominal is a G2 guidance/threat baseline (`capabilities.py:118-165`).
- PSB-MPC is G1 with a known Eigen abort; RRT is G1 without a successful
  representative path; RLMPC is G0 with an unavailable solver environment
  (`capabilities.py:144-164`).
- God and KF are G2 trackers, but KF is limited to Rule 14/head-on tuples.
  Scenario Default and VIMMJIPDA are G1 (`capabilities.py:167-184`).

The current verified tuple inventory is locked by
`tests/test_p1_capability_api.py:8-123`. It explicitly rejects invalid Cartesian
products. Busy-water combinations are experimental and separately tested in
`tests/test_busy_water_scenarios.py:98-124`.

### 5.3 Required UI Distinctions

Future UI must keep these states visually and textually separate:

- Dependency available.
- Runtime ready.
- Runnable/selectable.
- Experimentally runnable.
- G3 qualified for one exact tuple.
- G4 statistically validated.
- Execution succeeded or failed.
- Evaluation hard gate passed or failed.
- Paper numerical reproduction confirmed or unconfirmed.

A single green `Available` treatment would be materially misleading.

## 6. Session And Runtime Architecture

### 6.1 Ownership Model

`gui_server/main.py:320-369` defines `WebSessionManager` as a single active
research session. It owns one `prepared`, `result`, and `latest` record.

- A new session cannot replace a RUNNING session (`main.py:346-350`).
- A non-running session may be replaced.
- Old run files remain on disk, but the manager no longer accepts their IDs.
- The manager is in-memory; service restart does not restore an active run.
- There is no run-history, batch-history, load-run, archive, or compare API.

`session_id` is the current run manifest UUID (`main.py:343-344`). All current
session routes validate against that one identifier (`main.py:610-613`).

### 6.2 Creation Contract

`gui_server/main.py:121-146` exposes these creation inputs:

- Scenario, validation rule, algorithm, tracker.
- Seed and episode index.
- Optional timestep and end time.
- Strict no-fallback policy.
- Evaluator profile.
- Algorithm and tracker configuration.
- Optional busy-water scenario override.

`colav_simulator/experiment/contracts.py:63-87` contains additional internal
RunSpec fields that are not currently exposed by the Web create endpoint.

Preparation performs capability validation, scenario/ENC construction,
algorithm/tracker construction, strict-no-fallback checks, and initial evidence
writes before the UI receives the created description. The Web layer then
renders `enc.png` (`gui_server/main.py:346-368`).

### 6.3 State Machine

The authoritative state set is `CREATED`, `RUNNING`, `PAUSED`, `FINISHED`, and
`FAILED` (`colav_simulator/experiment/contracts.py:22-27`).

```text
NONE --create----------------------> CREATED
CREATED --start--------------------> RUNNING
CREATED --step---------------------> PAUSED | FINISHED | FAILED
RUNNING --pause--------------------> PAUSED
RUNNING --tick/step----------------> RUNNING | FINISHED | FAILED
PAUSED --start---------------------> RUNNING
PAUSED --step----------------------> PAUSED | FINISHED | FAILED
non-running state --reset/create---> new CREATED with new UUID
FINISHED with result --replay------> new CREATED with replay_of_run_id
FINISHED/FAILED --start or step----> conflict/error
```

Important details from `colav_simulator/experiment/session.py:71-143`:

- Repeated start records another start event rather than rejecting RUNNING.
- Pause outside RUNNING is a successful no-op.
- Step from CREATED or PAUSED returns to PAUSED unless terminal.
- Step while RUNNING remains RUNNING.
- Goal, time limit, collision, or grounding may finish a session.
- Exceptions set FAILED and preserve a failure reason.
- There is no cancel, delete, or archive state.

### 6.4 Client Replacement And Recovery

- `web_gui/app.js:3126-3176` uses a request key, revision counter, and shared
  Promise to prevent stale session-creation responses from becoming active.
- If the current session is RUNNING, the client pauses it before replacement
  (`app.js:3138-3164`).
- `app.js:3179-3222` atomically clears old diagnostic, result, event, ENC, and
  animation state before connecting the replacement session.
- `app.js:2947-2992` binds WebSocket handlers to both the current socket and
  active session ID, ignoring stale responses and reconnecting after 2.5 s.
- `app.js:2994-3017` allows a focused tab to recover a missing session; a
  background tab does not automatically seize the single active slot.

These are correctness rules, not incidental implementation details.

## 7. REST And WebSocket Contracts

### 7.1 Route Groups

Current routes in `gui_server/main.py:917-1242`:

| Group | Routes |
|---|---|
| Catalog | `/api/scenarios`, `/api/capabilities`, `/api/algorithms` |
| Busy water | generate, draft list/load/save, coordinate conversion |
| Session | create, current, describe |
| Control | start, pause, speed, step, reset, replay |
| Outcome | result, artifact list, artifact download |
| Map/diagnostic | ENC info/tile, navigation area, planner decision space |
| Compatibility | legacy start/pause/reset/select/speed routes and `/ws` |
| Live transport | `/ws/sessions/{session_id}` |

The current production JavaScript uses the session-scoped API. Legacy endpoints
should be treated as compatibility surface, not as the new UI foundation.

### 7.2 Response Shapes And Errors

Control responses are intentionally different:

- Start/pause/reset/replay return session descriptions.
- Step returns telemetry.
- Speed returns a playback object.
- Result exists only after successful finalization.
- Failed runs expose failure state and artifacts, not a normal result.

Error shapes are not uniform:

- 422 commonly represents invalid creation, capability, or generation.
- 404 represents a non-current session or missing artifact.
- 409 represents invalid lifecycle state, unavailable result/replay, or stale
  decision-space solve ID.
- 503 represents an ENC tile with no active session.
- 204 represents no planner decision-space data.
- `detail` may be a string or a structured `{status, reason}` object.

`web_gui/app.js:2901-2911` currently supports both error-envelope shapes.

### 7.3 Telemetry

`/ws/sessions/{id}` sends `manager.latest` every 100 ms. It is a repeated
snapshot stream, not an append-only event bus (`gui_server/main.py:1222-1237`).

The schema version is `1.0`. `main.py:759-807` exposes modern fields including:

- Run, scenario, sequence, time, and lifecycle state.
- Truth, measurements, tracks, plans, and ENC navigation area.
- Encounters and primary encounter.
- Current-frame planner and latest real planner solve.
- Execution, events, playback, failure, and reproduction status.

Legacy aliases remain for the current UI (`main.py:783-803`). Migration should
move production components to modern fields before aliases are removed.

`planner` and `latest_planner_solve` are not interchangeable:

- `planner` describes the current frame and may have `solver_executed=false`.
- `latest_planner_solve` retains the latest actual solve.
- Solver monitoring must show both current hold state and last real solve.

Events belong only to the latest step snapshot. Because the same snapshot is
resent, the client de-duplicates by a stable composite key
(`web_gui/app.js:2869-2895`). A complete refreshable Timeline requires an event
history API or the persisted `events.json`; the current WebSocket alone cannot
reconstruct history.

## 8. ENC And Canvas Renderer

### 8.1 Rendering Pipeline

The Canvas renderer is a mature operational asset:

- `web_gui/app.js:198-218`: Canvas initialization, DPR-aware sizing, and resize
  observation.
- `app.js:224-290`: world/screen coordinate transforms and view controls.
- `app.js:363-397`: ENC metadata polling and independent raster loading.
- `app.js:412-451`: deterministic render ordering.
- `app.js:542-577`: requestAnimationFrame telemetry interpolation.

Current render order:

1. ENC and grid.
2. Navigable/safe-water overlays.
3. Fairways, reference routes, and waypoints.
4. History and perception.
5. Motion vectors and detection ranges.
6. Predictions and CPA.
7. Target routes and planner decision surfaces.
8. Vessels and compass.

`app.js:636-642` freezes the initial route per `run_id`; that initial-reference
meaning must survive componentization.

### 8.2 Interaction Constraints

- Resize currently invokes fit-to-ENC, so panel layout changes reset user pan
  and zoom (`app.js:202-214`).
- Map click serves both target selection and busy-water route editing
  (`app.js:292-332`).
- Pan, zoom, target selection, and route selection are mouse-only.
- Layer visibility is local, non-persisted state (`app.js:108-126`).
- Overlay z-order, hit regions, and view dimensions are tightly coupled.

The first implementation stage should move the application shell around the
renderer, not rewrite the renderer. Renderer extraction can follow after visual
and interaction regression coverage exists.

## 9. Planner, Safety, And Evidence Semantics

### 9.1 Live Planner Information

`web_gui/app.js:1625-1703` already differentiates:

- SOLVE versus HOLD.
- Status and feasibility.
- Command course/speed.
- Horizon and prediction error.
- Solve period and solve timeline.

These semantics map directly to future `ColavAdvice`, `ColavPredictionPath`,
and `ColavSolverStatus` components. They should be extracted without inventing
new solver truth.

### 9.2 Safety And Event Information

`web_gui/app.js:2838-2896` derives display events for COLREG transitions, DCPA
risk bands, and real `planner_solved` events. This is useful for a Timeline
store, but formal evaluation must still come from persisted evaluator output.

The current evaluator is a behavior-compatible reconstruction, not a confirmed
numerical paper reproduction:

- `colav_simulator/evaluation/evaluator.py:41-43` identifies evaluator v2.
- `evaluator.py:217-240` sets numerical reproduction false and reproduction
  status to behavior-compatible reconstruction.

Validation UI must keep three layers separate:

1. Hard gate: collision, hull clearance, grounding, fallback, completion.
2. Scores: pairwise/COLREG/safety measures.
3. Diagnostics: algorithm identity, solver, runtime, and evidence.

The main hard-gate scope is Ship0 versus targets and Ship0 grounding. Global
collision/grounding counts are additional evidence, not the same claim
(`evaluator.py:678-805`).

## 10. Styling And Responsive Behavior

### 10.1 Current Theme

`web_gui/style.css:7-37` defines a partial token layer:

- Dark green/black surfaces.
- Cyan, blue, green, red, amber, gold, purple, and teal accents.
- System UI and monospace font stacks.
- 8 px panel radius and deep card shadows.

Canvas JavaScript still hardcodes colors, including risk and overlay colors
(`web_gui/app.js:33-38`, `app.js:1197-1219`). This creates token drift between
DOM controls and maritime overlays.

### 10.2 Layout Breakpoints

- Desktop: `270px / minmax(0, 1fr) / 320px`
  (`style.css:183-189`).
- 901-1500 px: `240px / minmax(0, 1fr) / 280px`
  (`style.css:1667-1676`).
- At or below 900 px: single-column flow with a 500 px map
  (`style.css:1678-1749`).
- At or below 520 px: 440 px map and repositioned overlays
  (`style.css:1751-1879`).

Desktop body scrolling is disabled while side columns scroll independently
(`style.css:43-49`, `style.css:779-802`). This creates several competing scroll
regions and can hide lower-priority controls.

## 11. Accessibility Audit

Existing strengths:

- Semantic header/main/aside/section landmarks.
- Labels and fieldsets for many controls.
- Named buttons and several live/status regions.
- `aria-pressed` on many selection controls.

Priority gaps:

| Priority | Gap | Evidence |
|---|---|---|
| P1 | Canvas has no keyboard pan, zoom, target-select, or route-edit alternative | `app.js:292-332` |
| P1 | Most buttons/cards lack a clear `:focus-visible` treatment | only `style.css:265,913` match |
| P1 | Rule cards use tab role without `aria-selected`, panels, or arrow-key behavior | `index.html:204-216` |
| P1 | Invisible native Select controls remain focusable at 1 px | `style.css:983-991` |
| P2 | Many operational labels use 0.58-0.72 rem text | stylesheet and baseline image |
| P2 | Pulse animation has no reduced-motion alternative | `style.css:153-178` |
| P2 | A high-frequency event terminal is one polite live region | `index.html:137-141` |

## 12. Baseline Visual Review

The supplied 2137 x 1300 screenshot shows a map-dominant console with left
monitoring panels, right configuration panels, a bottom playback strip, and a
floating event terminal.

Strengths:

- Real ENC is the clear visual center.
- Monitoring and configuration sides are broadly recognizable.
- Selection, connection, and risk colors are mostly consistent.
- Dense information fits the intended expert audience better than a generic
  marketing dashboard would.

Problems:

- There is no business navigation or lifecycle context.
- The screen reads as one debugging console rather than a product workflow.
- DCPA danger, COLREG rule, connection health, and execution state lack one
  coherent alert hierarchy.
- Vessel, prediction, and risk overlays are thin at the displayed map scale.
- The event window and playback strip obscure the lower map region.
- Right-side cards give selection, capability grade, and implementation status
  similar visual weight.
- Header whitespace is not used for Run identity, selected configuration,
  lifecycle state, or critical alert summary.
- Small descriptive text reduces rapid scanning at operational distance.

## 13. Four-Business IA Reality Check

### 13.1 Scenarios And Conditions

Available now:

- Scenario catalog and provenance/validity metadata.
- Busy-water generation and preflight.
- Busy-water draft save/load.
- Coordinate conversion and map-based target/route editing.

Not available as a general product capability:

- A general YAML scenario editor.
- Complete AIS/Imazu repair workflow.
- Versioned scenario library beyond current files and busy-water drafts.

### 13.2 Algorithms And Components

Available now:

- Algorithm and tracker registry.
- Dependency/runtime status.
- Global integration metadata and known failures.
- Exact compatibility tuples and latest evidence.

Recommended future representation: algorithm summary plus a Rule x Scenario x
Tracker matrix. The summary grade must never imply every matrix cell.

### 13.3 Simulation Run

Available now:

- New Run configuration and one active Live Run.
- Start, pause, speed, step, reset, and completed-run replay.
- ENC situation, telemetry, planner diagnostics, events, and current evidence.

Constraint: this is one active session, not a queue or concurrent scheduler.

### 13.4 Validation And Analysis

Available now:

- Current successful session result and artifacts.
- Failure artifacts.
- Replay of the current successfully finalized session.
- Offline run directories and BatchRunner reports.

Not available through current Web APIs:

- Run history index.
- Arbitrary historical run loading/replay.
- Batch history/index.
- Compare service or UI.
- Cross-run query, archive, or audit workflow.

Those pages remain product roadmap until their backing contracts exist.

## 14. Reusable Boundaries

Preserve without semantic change:

- FastAPI session-scoped REST and WebSocket contracts.
- Exact capability tuple and backend execution gate.
- Strict no-fallback creation policy.
- Session creation race guards and cross-tab conflict behavior.
- ENC metadata/raster and coordinate contract.
- Canvas rendering order, interpolation, initial-route semantics, and hit regions.
- Current-frame HOLD versus latest real SOLVE evidence.
- Failure state and artifact preservation.
- Playback requested/effective/realtime-limited distinction.

Preserve semantics, replace presentation:

- Safety summary and target risk.
- COLREG encounter state.
- Planner advice and executed command.
- Prediction path and solver status.
- Timeline/event display.
- Playback controls and contextual Inspector.

Safe to replace after design approval:

- Boot-time DOM relocation.
- Permanent dual sidebars.
- Glass-dashboard styling.
- Hidden native Select plus card duplication.
- Equal-weight card stacks and nested scroll regions.

## 15. Migration Risks And Required Gates

### P0: Must Resolve Before Production Migration

1. **Session model mismatch.** Runs/Compare must not imply concurrent or indexed
   historical runs while the backend owns one current session.
2. **Configuration side effects.** Page separation must introduce draft versus
   applied RunSpec without silently creating a session on every selection.
3. **Stale async writes.** Old WebSocket, ENC, result, and decision-space
   responses must never update a replacement run.
4. **Evidence misrepresentation.** Current HOLD, latest SOLVE, execution result,
   evaluator hard gate, reproduction status, Ship0 safety, and global safety
   must remain distinct.
5. **Capability flattening.** Integration grade must not replace exact tuple
   eligibility or experimental/verified status.

### P1: Required During Component Foundation

1. Preserve the implicit HTML ID contracts until replacement components have
   tests; current `setText()` silently ignores missing nodes
   (`web_gui/app.js:1554-1557`).
2. Move the shell first; do not combine renderer replacement with page migration.
3. Define explicit API error-to-recovery behavior for 204/404/409/422/503.
4. Add a durable Timeline source before promising refreshable event history.
5. Add keyboard and focus behavior for map-adjacent workflows.
6. Keep failed and dependency-skipped evidence visible in Analysis.

### P2: Design-System Follow-Up

1. Unify DOM and Canvas semantic color tokens.
2. Add reduced-motion behavior.
3. Increase operational text size and scan hierarchy.
4. Reduce permanent map overlays and competing scroll regions.
5. Prevent absolute local `run_dir` values from becoming a product dependency.

## 16. Test Coverage And Gaps

Current focused baseline passed 21 tests across capability API, clock/ENC, and
playback speed. Existing repository coverage also includes:

- Real create -> step -> finish -> result -> artifacts -> WebSocket -> replay
  integration in `tests/test_web_api.py:291-352,657-680`.
- Current frame versus latest real solver evidence in
  `tests/test_web_api.py:520-550`.
- Lazy VO decision-space retrieval and stale solve handling in
  `tests/test_web_api.py:553-617`.
- Playback authority/reset behavior in `tests/test_playback_speed.py:29-99`.

Important gaps before major UI implementation:

- No dedicated unit or DOM-interaction tests for `web_gui/app.js`.
- Create while RUNNING.
- No-current-session startup and service restart.
- FAILED result/artifact presentation.
- WebSocket reconnect and multi-tab replacement.
- Step while RUNNING and idempotent pause/start behavior.
- Artifact traversal rejection.
- Legacy-route compatibility.
- Replay verification mismatch.
- Keyboard Canvas alternatives and focus order.
- Screenshot regression at 1920 x 1080 and 1366 x 768.

## 17. Audit Exit Criteria

This audit is complete when it can anchor the next Design Context and Brief
without implying implementation completion. It establishes these non-negotiable
facts:

- The product is currently one static operational console.
- The map renderer and runtime contracts are migration assets.
- The server supports one active session only.
- Capability and evidence semantics are multidimensional.
- Validation/Analysis is partly backed by artifacts, but history and Compare
  need new contracts.
- The next phase may define `AGENTS.md`, `DESIGN.md`, OpenBridge guidance, COLAV
  extensions, and frozen IA. It must not yet rewrite production Web code.
