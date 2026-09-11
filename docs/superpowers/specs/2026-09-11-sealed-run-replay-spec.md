# Sealed Run Replay — Canonical Feature Spec

> **Status:** Ready for implementation tickets  
> **Spec baseline:** `main@1c2b69acc52fdd8dfa515d38f86a679c0b4ef082`  
> **Product surface:** Current `Evaluation` workface; future-compatible with `Runs > Run Detail > Replay`  
> **Assurance boundary:** Read-only historical inspection; no Simulator/Planner execution  
> **Companions:** PRD, UI Design, Technical Design, Implementation Plan, Verification Plan dated 2026-09-11

## Problem Statement

Colav-Simulator currently makes an operator wait for live simulation execution in order to watch a run. This is especially costly for Mid-MPC: the UI may request `5×` execution, but actual progress remains limited by synchronous simulation and solver work. A requested simulation multiplier therefore cannot guarantee fast inspection of an already-known trajectory.

The current codebase also uses several different meanings of “Replay” or “Playback”:

- Active Session execution-rate control in Deployment;
- `telemetry-playback.js`, which is a short live presentation buffer used to smooth real received frames;
- `ExperimentRunner.replay()`, which re-executes a RunSpec to verify reproducibility;
- Historical AIS `HISTORICAL_REPLAY`, which reconstructs historical actors and runs the normal simulation path;
- `colav_simulator.decision_replay`, which records full per-tick evidence and interrogates it offline.

The missing capability is a **visual, seekable, solver-independent playback of one already-recorded Run**.

The repository already contains strong primitives for this feature. `colav_simulator.decision_replay` persists full per-tick payloads under a run's `decision/` evidence directory and explicitly follows “record once, interrogate offline”. `TraceBundle` can read this evidence without importing the simulator. Existing normal finalized runs also contain `trajectory.parquet` and `events.jsonl`, but that trajectory is intentionally reduced and cannot reproduce every live planner/risk/diagnostic fact. Current normal Web Active Sessions do not yet make the full decision trace a guaranteed run artifact.

The current Evaluation workface is dominated by Historical AIS benchmark evidence. That content is valuable and must not be discarded, but it does not provide the normal completed-run visual replay required by algorithm development. The third workface therefore needs to become a reusable historical inspection surface, while preserving Historical AIS as a scoped benchmark view.

This feature must implement the V1 architectural rule already frozen in the repository: **Live, Replay, Analyze and Compare are projections of canonical recorded evidence; Replay must never execute the current Simulator.**

## Solution

Add **Sealed Run Replay**, a read-only presentation of recorded Run evidence.

A replay-capable Run records a full, versioned per-tick Decision Trace independent of browser connectivity. After execution ends, the backend exposes a read-only replay descriptor, time-window frame reads and canonical event reads. A frontend Replay Controller advances an independent presentation clock over sealed simulation time and feeds stored frames through the same Telemetry Projection / Situation Display semantics used by Deployment.

The user can select a completed Run, play/pause it, seek to any recorded simulation time, jump between events and change Replay Speed without calling the Simulator, Planner, tracker or controller. Continuous vessel position/heading may be interpolated only between two sealed adjacent frames. Discrete risk, planner, lifecycle, evaluation and event facts always come from recorded evidence and are never interpolated or recalculated in the browser.

The current Evaluation workface becomes a local historical-inspection shell with Replay as the primary view. Existing Historical AIS benchmark functionality moves behind a local `Historical AIS` view and keeps its current dataset/workflow/qualification authority. Any Historical AIS replay or counterfactual Run that produces a replay-capable Run ID can be opened by the same Sealed Run Replay surface; no second visual player is created.

Product terminology is made explicit:

- **Simulation Rate** — how quickly an Active Session attempts to advance simulation time; compute-limited.
- **Live Presentation Buffer** — short delayed interpolation of real received live frames; not historical replay.
- **Sealed Run Replay** — visual read-only playback of recorded Run evidence; solver-independent.
- **Reproduction** — re-execution of a frozen RunSpec to verify reproducibility.
- **Historical AIS Replay** — a historical-world execution mode that may itself later be visually inspected through Sealed Run Replay.
- **Decision Replay** — offline diagnostic probes over the same full Decision Trace evidence.

## User Stories

1. As a COLAV developer, I want to replay a completed Mid-MPC Run without solving Mid-MPC again, so that solver speed does not limit inspection speed.
2. As a COLAV developer, I want to drag a timeline to any recorded simulation time, so that I can inspect a failure window immediately.
3. As a COLAV developer, I want Replay Speed to be independent of Simulation Rate, so that `20×` replay means presentation speed rather than a solver throughput request.
4. As a COLAV developer, I want previous and next event navigation, so that I can move directly between material behavior transitions.
5. As a COLAV developer, I want the same Situation Display in Live and Replay, so that visual differences do not come from two rendering implementations.
6. As a COLAV developer, I want the selected/accepted planner output recorded and replayed at its original time, so that I can see what the planner actually decided.
7. As a COLAV developer, I want solver status, iterations and timing to remain historical facts during replay, so that replay cannot accidentally trigger a new solve.
8. As a COLAV developer, I want a recorded decision trace to remain usable by existing offline Decision Replay probes, so that visual replay and diagnostic replay share one evidence source.
9. As a V&V engineer, I want a replayable Run to identify its RunSpec, source identity, algorithm, tracker, scenario and evidence level, so that I know exactly what I am inspecting.
10. As a V&V engineer, I want Replay to preserve event identity, time, content and ordering, so that an event jump points to the same historical fact every time.
11. As a V&V engineer, I want missing replay evidence reported as `UNAVAILABLE`, `REDUCED` or `INCOMPLETE`, so that a legacy or damaged Run is not presented as full evidence.
12. As a V&V engineer, I want a reduced legacy replay to be visibly degraded, so that trajectory-only playback is not confused with full planner evidence.
13. As a V&V engineer, I want Original Evaluation verdicts to remain immutable while replaying, so that inspection cannot mutate assurance history.
14. As a V&V engineer, I want Replay controls to be presentation state only, so that seeking or selecting a vessel cannot modify Run state or Planner state.
15. As a V&V engineer, I want a finished Run to become replayable independently of report-generation latency, so that long evaluation/report work does not keep the visual result inaccessible.
16. As a V&V engineer, I want replay evidence capture to be backend-owned rather than browser-owned, so that a disconnected browser does not cause formal replay evidence loss.
17. As an operator, I want a clear `SEALED · HISTORICAL` or equivalent historical state indicator, so that I never mistake replay for a live ship state.
18. As an operator, I want current replay time and total duration visible, so that I understand where I am in the recorded Run.
19. As an operator, I want event markers on the timeline, so that CPA/risk/planner/lifecycle/runtime transitions can be located spatially in time.
20. As an operator, I want to filter event marker categories without changing recorded evidence, so that dense Runs remain inspectable.
21. As an operator, I want vessel selection to update Inspection Context only, so that chart clicks never change recorded control decisions.
22. As an operator, I want Replay to pause automatically at the end and support replay-from-start, so that playback behaves predictably.
23. As an operator, I want a high replay speed to preserve event markers even when not every visual frame is painted, so that presentation frame skipping cannot delete evidence.
24. As an operator, I want headings to interpolate through the shortest angular path, so that vessel icons do not visually rotate the long way around north.
25. As an operator, I want continuous positions to interpolate only inside recorded frame bounds, so that the UI never extrapolates a vessel beyond known evidence.
26. As an operator, I want discrete risk/planner values to stay on the latest recorded source frame at or before the playhead, so that the browser never invents an in-between safety state.
27. As an operator, I want the timeline to remain seekable while replay is paused, so that analysis does not require restarting playback.
28. As an operator, I want a recent completed Run to be discoverable from Evaluation, so that I do not need to know the run directory path.
29. As an operator, I want the latest completed Run to be easy to open while older Runs remain selectable, so that normal iteration is fast without losing history.
30. As an operator, I want failed/truncated Runs to be replayable up to their last sealed frame when evidence exists, so that failures can be investigated rather than discarded.
31. As a GUI developer, I want one replay projection contract, so that normal paper scenarios and Historical AIS Runs do not require separate visual players.
32. As a GUI developer, I want Replay to consume canonical backend frame/event documents rather than parse raw CAS/Parquet artifacts in the browser, so that format evolution remains backend-owned.
33. As a GUI developer, I want the existing Telemetry Projection to remain the interpretation authority, so that replay does not create a second JavaScript risk/planner model.
34. As a GUI developer, I want continuous interpolation logic shareable with live buffered presentation while keeping queue/delay behavior separate, so that common math is reused without conflating modes.
35. As a backend developer, I want the existing Decision Trace schema to remain readable, so that the new UI adds capability without breaking the decision-replay CLI and skill.
36. As a backend developer, I want normal replay-capable Runs to record full frames through a reusable evidence sink, so that the debug-only recorder is no longer the only path to full replay evidence.
37. As a backend developer, I want replay reads to import no Simulator or planner runtime, so that the no-reexecution boundary is structural rather than conventional.
38. As a backend developer, I want time-window reads rather than whole-run transfer, so that long Runs do not require loading all evidence into the browser.
39. As a backend developer, I want replay reads bounded to the selected run directory/evidence identity, so that a browser cannot request arbitrary filesystem paths.
40. As a backend developer, I want trace integrity and schema version checked before a Run is marked full-replay-ready, so that corrupted evidence fails closed.
41. As a product owner, I want Deployment `1×/2×/5×` controls labeled as Simulation Rate, so that users do not confuse compute-limited execution with replay.
42. As a product owner, I want Evaluation to prioritize Sealed Run Replay while retaining Historical AIS benchmark evidence, so that the third workface supports ordinary algorithm iteration and specialist AIS validation.
43. As a product owner, I want the Evaluation replay design to migrate cleanly to future `Runs > Run Detail > Replay`, so that the current 3-workface transition does not create throwaway architecture.
44. As a Historical AIS engineer, I want the current Historical AIS workflow authority preserved, so that adding normal Run Replay does not rewrite dataset/case/counterfactual semantics.
45. As a Historical AIS engineer, I want a completed Historical AIS Run to open in the same Sealed Run Replay view, so that Historical AIS does not maintain a second player.
46. As an evidence reviewer, I want Decision Replay probes and visual replay to answer from the same full trace, so that a visual observation can be followed by an exact offline “why” query.
47. As an evidence reviewer, I want frame/event digests and replay descriptor identity exposed, so that exported or copied evidence can be integrity-checked.
48. As a performance engineer, I want replay throughput characterized separately from solver throughput, so that performance reports distinguish presentation from algorithm execution.
49. As a performance engineer, I want evidence capture overhead measured on VO, Fan-MPC and Mid-MPC product Runs, so that replay support does not silently degrade execution timing.
50. As a test engineer, I want a deterministic fixture with known frame times, vessel positions and events, so that seek, interpolation and event navigation can be verified independently of current algorithms.
51. As a test engineer, I want a browser acceptance test that proves replay controls never call session start/step/speed endpoints, so that visual replay cannot regress into re-execution.
52. As a test engineer, I want a cross-mode parity test that compares a recorded live frame with the same replayed frame, so that Replay is demonstrably a projection of recorded truth.

## Implementation Decisions

- The feature name is **Sealed Run Replay**. It is distinct from Decision Replay, Reproduction and Historical AIS Replay.
- Current V1 repository principles remain upstream authority: Replay is a projection of canonical Observation/Event/Evidence and never a second simulation truth.
- The primary evidence source for **full** replay is the existing versioned full per-tick Decision Trace concept demonstrated by `colav_simulator.decision_replay`; its schema remains backward readable.
- `trajectory.parquet` is treated as **reduced** historical evidence. It may support a visibly degraded legacy trajectory replay, but it is not sufficient to claim full Live/Replay parity because planner/risk evidence is intentionally reduced.
- Normal product Runs intended for replay must capture full trace evidence through backend-owned persistence independent of browser connectivity.
- Evidence capture must not silently drop mandatory replay frames. Backpressure or persistence failure produces typed incomplete replay evidence; the run may remain an execution record but cannot claim full replay readiness.
- Replay readiness is an orthogonal projection/evidence state, not a replacement for Run execution/evaluation state. At minimum: `CAPTURING`, `READY`, `REDUCED`, `INCOMPLETE`, `UNAVAILABLE`.
- A completed/failed Run may expose replay as soon as its replay artifacts are durably finalized; full Evaluation/report generation may complete later.
- The backend owns raw artifact parsing, schema compatibility and integrity checks. The browser receives versioned replay descriptors, canonical frame windows and canonical events.
- Replay API inputs use Run identity and simulation-time ranges only. Browser-provided filesystem paths are not accepted.
- Replay reads are strictly read-only and contain no Simulator, Planner, tracker, guidance or controller execution path.
- The product exposes a descriptor sufficient to identify run, time bounds, evidence level, schema, frame count, available event categories, static scenario/chart context and relevant artifact digests.
- The product exposes bounded time-window frame reads suitable for prefetch around the playhead; whole-run transfer is not the default contract.
- The product exposes the canonical historical event journal separately from frames so timeline markers remain complete even when visual rendering samples frames.
- Existing Decision Replay CLI/probes continue to work against the same trace evidence. Visual Replay must not fork a second recorder format solely for the browser.
- If seek performance requires a derived index or chunk cache, it is a derived artifact/cache over immutable trace evidence; it does not alter original frame/event facts.
- The Replay Controller owns only presentation state: selected Run, playhead, play/pause state, replay rate, loaded window, buffering/loading state and inspection selection.
- Replay speed presets initially support `0.25×`, `0.5×`, `1×`, `2×`, `5×`, `10×`, `20×`; this list is presentation policy and may evolve without changing Run evidence.
- Replay playhead advances from wall-clock elapsed time multiplied by Replay Speed and is clamped to recorded `[t_start, t_end]`.
- Seeking immediately sets the Inspection Cursor/playhead and requests the required recorded window. It never invokes Active Session control.
- Continuous kinematics may interpolate between two adjacent sealed frames. Heading/course interpolation uses shortest-angle interpolation.
- Interpolation never extrapolates before the lower frame or after the upper frame.
- Discrete planner/risk/lifecycle/control/evidence facts are sampled from the authoritative recorded source frame at or before the playhead; they are not interpolated or recomputed.
- Operational Event identity/time/order comes from recorded event evidence, not browser-detected transitions.
- High Replay Speed may reduce paint frequency, but it may not delete, merge or rewrite event evidence.
- The existing Situation Display and Telemetry Projection semantics are reused for Replay. Any adapter is a transport/source adapter, not a second risk/planner interpretation layer.
- The continuous interpolation helper may be extracted from current live buffered presentation for shared use; the live queue, delay reserve and recovery-rate logic remain Live-only.
- The current Evaluation workface gains local historical-inspection navigation. Replay is the primary ordinary-run view; Evaluation/Evidence views may expose existing result/lineage data; Historical AIS retains its existing benchmark authority in a dedicated local view.
- Historical AIS “Open in Deployment” remains an execution action. Once that execution produces a replay-capable Run, the same Run can be inspected by Sealed Run Replay.
- Deployment execution controls are labeled **Simulation Rate**, and the UI shows requested vs effective compute-limited execution where available. Replay controls are labeled **Replay Speed**.
- Sealed Run Replay displays a persistent historical-state indicator and cannot display `LIVE` status.
- The design remains compatible with the future V1 `Runs > Run Detail > Replay` IA: replay domain/controller/API modules are not owned by the current Evaluation page.
- No new safety score, COLREG classifier, Primary Threat selector, evaluator or planner semantics are introduced by this feature.

## Testing Decisions

- Tests verify external behavior at approved seams, not private helpers, DOM class names, gzip implementation details or internal cache shape.
- The highest product seam is: **open a recorded Run through the replay API/UI, seek/play it, and observe the canonical recorded situation without executing the simulator**.
- Backend contract tests cover replay descriptor, bounded frame window, event journal, full/reduced/incomplete evidence states, schema/integrity failure and path confinement.
- A replay API test must fail if replay code imports or invokes the active simulation execution path through a request; network-level tests assert no session mutation occurs.
- Replay-controller tests use a deterministic synthetic clock and known sealed frames to verify play, pause, rate changes, seek, end behavior and window prefetch requests.
- Interpolation tests use independent known literals for positions and wrap-around headings; they do not compute expected values by calling the implementation under test.
- Discrete-fact tests prove planner/risk/lifecycle state remains bound to the recorded lower/source frame and is never averaged between frames.
- Event-navigation tests prove previous/next event selection preserves recorded event identity and ordering across rate changes and seeks.
- High-speed tests prove the playhead advances at presentation rate independent of solver availability and that event markers remain complete even if paint frames are skipped.
- Full-trace parity tests compare canonical facts from a live-captured frame and the same replay frame at the same source sequence/time.
- Reduced legacy tests prove trajectory-only Runs are explicitly marked `REDUCED` and do not fabricate unavailable planner/risk/diagnostic facts.
- Truncated/failed-run tests prove replay ends at the last durable frame and indicates incompleteness without extrapolation.
- Evidence-capture tests prove browser disconnect does not stop backend trace capture.
- Evidence-capture performance tests measure overhead on representative VO, Fan-MPC and Mid-MPC product Runs before a release budget is frozen; no invented budget may be used to hide a regression.
- Browser tests cover Evaluation local navigation, run selection, historical badge, timeline drag, replay rate, event jumps, target selection and transition to Historical AIS view.
- Browser tests explicitly intercept session create/start/pause/step/speed/reset endpoints and require zero calls while manipulating Replay controls.
- Browser parity tests confirm the same stored source frame produces equivalent ownship/target positions, planner display selection and threat/evidence presentation in Deployment-capture vs Replay projection.
- Historical AIS integration tests prove the existing benchmark workflow remains available and that a completed Historical AIS Run can be opened in the same Replay surface.
- Terminology tests prevent user-visible `Playback Rate` from being used for Active Session execution after the migration; Active Session says Simulation Rate, historical player says Replay Speed.
- Accessibility tests require timeline and playback controls to be keyboard-operable with non-color-only historical/readiness states.
- Supported desktop layout tests cover 1440×900 and 1920×1080 without nested scroll regressions that obscure the timeline.
- Final verification includes focused backend/frontend tests, full repository pytest, frontend test suite, Ruff/static/diff checks, a real Mid-MPC Run captured through the product path, and a browser replay of that exact Run.

## Out of Scope

- Making Mid-MPC itself run at guaranteed `5×`, `10×` or `20×` real-time execution.
- Asynchronous/parallel MPC redesign solely for replay.
- Live DVR/time-shift inspection of a still-running Active Session; this can reuse the architecture later but is not required for the first delivery.
- Replacing the independent Evaluator or changing Safety/COLREG thresholds.
- Reconstructing missing planner/risk facts from `trajectory.parquet` and presenting them as original evidence.
- Re-running the Simulator to fill missing replay frames.
- Treating Historical AIS Human Reference as planner input or changing Historical AIS counterfactual semantics.
- Building a second chart renderer for Replay.
- Browser-side Parquet, gzip or raw evidence parsing.
- Distributed/cloud replay streaming.
- Formal Validation/Release/MASS claims.
- Replacing the future V1 Runs workface; this feature is intentionally migration-compatible with it.

## Further Notes

- This spec follows Matt Pocock's `skills/engineering/to-spec` structure: synthesize the existing conversation and codebase, use project glossary, identify high-level test seams, publish a complete issue-ready spec, avoid file-path prescriptions in the normative decisions, and apply `ready-for-agent` to implementation tickets.
- The user already accepted the key seam/architecture direction in the preceding design discussion: recorded evidence → replay reader/API → independent replay clock → shared Situation Display, with Historical AIS retained but not owning the player.
- Repository V1 PRD already requires Replay to read evidence and never invoke Simulator; this feature operationalizes that requirement on the current 3-workface UI before the larger five-workface V1 migration.
- Existing `colav-decision-replay` is important prior art. It proves full per-tick evidence can answer offline questions and explicitly documents that normal `finalize()` currently persists only reduced trajectory rows. The implementation should promote that evidence capability rather than invent another browser-only truth.
- `telemetry-playback.js` remains a Live Presentation Buffer. Its interpolation mathematics is reusable; its delay/reserve queue semantics are not Replay semantics.
- `ExperimentRunner.replay()` remains reproduction/re-execution behavior even if its internal name is retained for compatibility. User-facing product language must call that operation Reproduce/Re-run, not Sealed Run Replay.
- If a conflict is discovered between this spec and the canonical V1 PRD/UI Spec or current Threat/Lifecycle/Evaluator authority boundaries, implementation stops and surfaces the contradiction instead of inventing a second truth.
