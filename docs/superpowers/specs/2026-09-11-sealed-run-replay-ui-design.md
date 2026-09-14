# Sealed Run Replay — UI Design

> **Status:** UI companion to the canonical Replay Spec and PRD  
> **Target:** Current OpenBridge-derived 3-workface application  
> **Primary surfaces:** Evaluation historical inspection + existing Situation Display  
> **Design sizes:** 1920×1080 primary, 1440×900 required

## 1. Design intent

Replay should feel like the same professional maritime situation surface used in Deployment, but unmistakably historical and analytical.

The central design rule is:

```text
Deployment = operate/observe a current Active Session
Evaluation / Replay = inspect immutable recorded evidence
```

The chart geometry, vessel symbology, target placards, ENC palette, planner layers and risk context should therefore remain familiar, while the control model changes from execution control to historical inspection.

No generic video-player skin should replace the maritime workbench. The replay controls are subordinate to the chart and evidence context.

## 2. Information architecture

Top-level workfaces stay unchanged for this delivery:

```text
Config | Deployment | Evaluation
```

Evaluation receives local navigation:

```text
Replay | Results | Evidence | Historical AIS
```

Behavior:

- When Evaluation opens and a replay-capable recent Run exists, `Replay` is selected.
- When the selected Run has no replay evidence, `Results` may become the recommended local view while Replay shows a typed unavailable state.
- Historical AIS remains directly reachable and preserves its workflow state.
- Changing local tabs changes Inspection Context only; it does not create or replace an Active Session.

## 3. Primary Replay layout

### 3.1 1920×1080

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Global top bar / Config · Deployment · Evaluation                           │
├──────────────────────────────────────────────────────────────────────────────┤
│ EVALUATION · R-<id>     SEALED · HISTORICAL        Replay Results Evidence  │
│                                                   Historical AIS             │
├───────────────┬────────────────────────────────────────────┬─────────────────┤
│ RUN CONTEXT   │                                            │ INSPECTION      │
│               │                                            │                 │
│ Run           │             Situation Display              │ Selected target │
│ Scenario      │                                            │ Risk / CPA      │
│ Algorithm     │   ENC / ownship / targets / track         │ COLREG context  │
│ Tracker       │   Mission Route / planner output           │ Planner status  │
│ Evidence      │   predictions / event focus                │ Event evidence  │
│ Verdict       │                                            │                 │
│               │                                            │                 │
├───────────────┴────────────────────────────────────────────┴─────────────────┤
│ 00:00:00   ━━━━━━━━●━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   00:10:00       │
│           △ risk   ◆ solve        ! CPA      ◇ recovery                     │
│ [|◀ Start] [◀ Event] [▶ / ❚❚] [Event ▶] [End ▶|]   1× 2× 5× 10× 20×       │
│ REPLAY 02:14.8 / 10:00.0      source frame #1349      evidence FULL         │
└──────────────────────────────────────────────────────────────────────────────┘
```

The screen is viewport-locked like Deployment. The Replay timeline remains visible.

### 3.2 1440×900

- chart remains dominant;
- left Run Context becomes a narrow summary rail or collapsible drawer;
- right Inspection rail remains available but may collapse to one contextual drawer;
- bottom timeline remains persistent;
- local Evaluation tabs stay in the compact local header;
- no nested vertical scroll chain is allowed on the replay workspace.

## 4. Local Evaluation header

Header fields:

```text
EVALUATION / REPLAY
Run <Run ID> · <Scenario>
<Algorithm> · <Tracker>
```

Persistent status chips use explicit semantic text:

```text
SEALED · HISTORICAL
REPLAY READY
FULL EVIDENCE
```

or degraded combinations:

```text
CRASHED · HISTORICAL
REPLAY INCOMPLETE
LAST TRUSTED 382.5 s
```

```text
HISTORICAL
REDUCED EVIDENCE
PLANNER DETAIL UNAVAILABLE
```

No historical state is color-only.

## 5. Run selection

### 5.1 Primary selection

The local header includes a Run selector/search affordance. The default candidate is the most recent completed/failed Run with inspectable evidence, not necessarily the current Active Session.

Run choice rows show:

- Run ID;
- scenario;
- executed algorithm;
- execution state;
- evaluation verdict if ready;
- replay evidence state;
- finish time or relative recency where available.

Selection changes the historical Inspection Context only.

### 5.2 Empty state

If there are no replayable Runs:

```text
No recorded Run is available for Replay.
Run a Development/Validation session in Deployment, or open Results/Evidence for an existing Run.
```

The empty state does not offer a hidden re-run action as if it were Replay.

## 6. Run Context rail

The left rail answers “what exact execution am I looking at?”

Minimum groups:

### Identity

- Run ID;
- Scenario/Case identity;
- requested/executed algorithm;
- tracker;
- GNC stack where applicable;
- seed / RunSpec digest where available.

### Execution

- FINISHED / FAILED / CRASHED semantics;
- start/end/duration;
- termination reason;
- requested/effective simulation rate is historical execution metadata only, not replay control.

### Evidence

- Replay evidence level: FULL / REDUCED / INCOMPLETE;
- trace schema;
- frame count;
- trace digest;
- event count;
- limitation text.

### Evaluation

- Result ready/pending;
- original hard-gate verdict when available;
- reproduction status when available.

The rail does not expose edit controls.

## 7. Situation Display reuse

Replay uses the same existing operational chart semantics as Deployment.

Default visible layers where evidence exists:

- Ownship;
- Target vessels;
- ENC/chart;
- Mission Route;
- Actual track up to playhead;
- Selected/Accepted Planner Output corresponding to the recorded source frame;
- predictions corresponding to the recorded source frame;
- relevant CPA/risk/threat overlays;
- selected target/POI;
- focused event marker when an event jump is active.

### 7.1 Actual track behavior

By default, actual track is clipped to current replay time. An optional inspection layer may show the full historical track as a lower-salience context, but the current playhead and traversed portion must remain visually distinguishable.

The first delivery can keep only “track to playhead” if full-track context would create ambiguity.

### 7.2 Vessel selection

Clicking ownship/target updates Inspection Context only.

The placard uses recorded/replay-projected facts:

- bearing/range;
- heading/speed;
- DCPA/TCPA when recorded/available;
- source/evidence state;
- MMSI/name where available.

It never changes the recorded Primary Threat or Planner focus.

## 8. Inspection rail

The right rail is driven by the current Replay playhead and selected inspection object.

### No explicit target selected

Show:

- replay time/source frame;
- Primary Threat / monitored risk summary if recorded;
- planner phase/status;
- current historical event focus;
- latest selected command/accepted plan summary;
- evidence limitations.

### Target selected

Show:

- target identity;
- encounter/lifecycle role where recorded;
- DCPA/TCPA/range;
- threat schedule context;
- planner response relevant to target;
- source/evidence age/health where captured.

No frontend reclassification is allowed.

## 9. Replay timeline

The timeline is a first-class inspection control, not merely a progress indicator.

### 9.1 Time axis

Range:

```text
[t_start, t_end]
```

Display:

- elapsed replay time;
- total duration;
- optional absolute AIS UTC when the Run carries historical time identity;
- source frame sequence near the playhead for diagnostic precision.

### 9.2 Scrubbing

Pointer drag:

1. updates the visual playhead continuously;
2. requests the recorded data window needed for the target time;
3. pauses playback while actively dragging unless platform behavior proves a better interaction;
4. settles at the requested historical time;
5. never calls any Active Session endpoint.

Keyboard:

- Arrow Left/Right: bounded small seek step based on recorded frame cadence or a defined presentation step;
- Page Up/Page Down: larger presentation seek;
- Home/End: replay start/end.

Exact keyboard increments may be implemented as presentation policy and tested for consistency.

### 9.3 Event markers

Marker categories use distinct shape/icon semantics. Suggested initial grammar:

| Category | Marker concept |
|---|---|
| Encounter/Lifecycle/Risk | triangle / encounter icon |
| Planner solve/action/fallback | diamond / planner icon |
| CPA/minimum-clearance event | target/cpa glyph |
| Collision/Grounding/Runtime failure | alert glyph |
| Goal/Time limit/Recovery | flag/check glyph |
| Algorithm handoff | transfer glyph |

Marker tooltip/popover includes:

- event type;
- simulation time;
- target identity if applicable;
- short backend-owned description/details;
- `Jump` action only when the marker is not already selected.

### 9.4 Dense events

Dense event timelines must not silently discard events. Visual aggregation may cluster markers at low pixel density, but opening the cluster must expose the underlying recorded events in order.

The first implementation may limit timeline categories to material Operational Events while keeping a full event list in Evidence/diagnostic views.

## 10. Replay controls

Control group:

```text
[Start] [Previous Event] [Play/Pause] [Next Event] [End]
```

Replay Speed group:

```text
0.25×  0.5×  1×  2×  5×  10×  20×
```

Labels and accessible names must say **Replay**.

### 10.1 Play

- If paused before end: start from current playhead.
- If ended: restart from beginning or require explicit Start; choose one behavior and keep it deterministic. Recommended: Play at ended state restarts from beginning with a visible jump.

### 10.2 Pause

Freezes playhead; all inspection remains usable.

### 10.3 Rate change

Changing rate while playing takes effect without moving evidence cursor discontinuously.

### 10.4 Loading

If the next frame bracket is not loaded:

```text
REPLAY · BUFFERING RECORDED DATA
```

The playhead pauses; no extrapolation occurs.

This “buffering” is network/storage buffering, not the Live Presentation Buffer.

## 11. Continuous vs discrete presentation

Replay has two classes of values.

### 11.1 Continuous visual values

May interpolate between lower/upper sealed frames:

- north/east or lat/lon;
- SOG/surge/sway where appropriate for display;
- heading/course with angular wrap handling;
- ownship and target icon position.

### 11.2 Discrete historical facts

Must come from one recorded source frame/event:

- lifecycle state;
- COLREG role;
- Primary Threat;
- risk class;
- planner phase;
- solver status;
- solve ID;
- selected command;
- accepted plan identity;
- fallback state;
- evaluation facts.

UI should optionally expose:

```text
Viewing 214.8 s
Source frame 1349 @ 214.5 s
Interpolated position only
```

when a reviewer needs exact evidence semantics.

## 12. Evidence states

### FULL

All required canonical per-tick trace evidence is present and integrity checks pass.

UI:

```text
FULL EVIDENCE
Decision Trace available
```

All supported planner/risk layers may render when present in the source frame.

### REDUCED

Only reduced trajectory/event evidence exists.

UI:

```text
REDUCED EVIDENCE
Trajectory available · planner/risk detail not captured
```

Unavailable panels show explicit missing-state copy, not empty zeros.

### INCOMPLETE

Trace exists but terminates unexpectedly, has gaps, unsupported segments or integrity failure.

UI:

```text
REPLAY INCOMPLETE
Trustworthy through 382.5 s
```

Do not render beyond the trusted boundary.

### UNAVAILABLE

No supported evidence source.

UI explains why and offers navigation to Results/Evidence, not a fake player.

## 13. Results local view

Results is scoped to the same selected Run.

Recommended groups:

- Original Evaluation verdict and completeness;
- Safety;
- COLREG;
- maneuver/navigation;
- runtime/planner health;
- reproduction status;
- report ready/pending status.

Selecting a metric/event may offer `View in Replay`, which moves the Inspection Cursor to evidence time only when the result contains a supported temporal reference.

Results never rewrites Original Verdict.

## 14. Evidence local view

Evidence is an inspection view, not an artifact editor.

Show:

- RunSpec/manifest identity;
- source/algorithm identities;
- replay trace schema/digest/count/state;
- event journal identity;
- trajectory artifact;
- evaluation/report identities;
- evidence limitations;
- Decision Replay availability;
- Historical AIS lineage where applicable.

Artifact contents are fetched/projected through backend contracts; browser does not parse raw local files.

## 15. Historical AIS local view

The existing Historical AIS Benchmark content is retained and visually simplified into the local view.

Keep:

- catalog-backed scene identity;
- Historical Replay vs Counterfactual mode choice;
- source/ENC/qualification status;
- workflow stages;
- determinism/leakage/threat/evaluation/compare evidence;
- canonical digests/lineage;
- `Open in Deployment` for interactive Counterfactual execution.

Change:

- it no longer occupies the entire Evaluation workface by default;
- it does not implement a separate visual playback timeline;
- when workflow/run evidence provides a Run ID, provide `Open Replay` to select that Run in the shared Replay local view.

## 16. Deployment terminology cleanup

Deployment retains the current live control layout but user-visible copy changes:

```text
SIMULATION RATE
1× | 2× | 5×
Requested 5× · Effective 1.1× · COMPUTE LIMITED
```

Do not say `Replay Speed` or generic `Playback Rate` for Active Session execution.

The existing display-delay status remains distinct:

```text
显示延后 2.7 s
```

or equivalent localized copy.

## 17. State matrix

| Run / replay state | Header | Timeline | Play controls | Results |
|---|---|---|---|---|
| FINISHED + READY | SEALED · HISTORICAL | full | enabled | ready/pending independently |
| FINISHED + REDUCED | HISTORICAL · REDUCED | supported range | enabled with limitations | independent |
| FAILED + READY | FAILED · HISTORICAL | through last frame | enabled | failed/not evaluated |
| FAILED + INCOMPLETE | FAILED · REPLAY INCOMPLETE | trusted portion only | limited | independent |
| FINISHED + CAPTURING/finalizing | REPLAY PREPARING | disabled/loading | disabled | may be pending |
| no evidence | REPLAY UNAVAILABLE | disabled | disabled | independent |

## 18. Interaction invariants

1. Replay UI never sends Active Session mutation commands.
2. Replay target selection never changes historical planner selection.
3. Timeline seek never changes RunSpec.
4. Event filtering never changes event evidence.
5. Local tab navigation never creates/replaces Active Session.
6. Historical AIS `Open in Deployment` is visibly an execution action, not replay.
7. `Open Replay` is visibly an inspection action.
8. A Replay speed value is never shown as the Active Session requested simulation multiplier.

## 19. OpenBridge implementation guidance

Reuse order follows existing V1 UI contract:

```text
OB-NATIVE → OB-COMPOSED → OB-WRAPPED → COLAV-EXTENSION → CUSTOM-EXCEPTION
```

Prefer existing:

- top-bar/application shell;
- local buttons/toggle groups;
- chart vessel components;
- placards;
- badges/alert semantics;
- drawers/side sheets;
- icon buttons;
- scrollbars where a list genuinely scrolls.

The replay timeline itself is likely a COLAV extension because it combines simulation time, event evidence and continuous seeking. It must still use OpenBridge tokens/interaction semantics and remain accessible.

Do not deep-style undocumented Shadow DOM internals.

## 20. Accessibility

Minimum requirements:

- Play/Pause has a stable accessible label reflecting state.
- Timeline exposes current value, minimum, maximum and human-readable time.
- Keyboard seek works without pointer drag.
- Event markers are reachable through an ordered event list/navigation even if individual dense markers are not all keyboard focus targets.
- Historical/readiness/failed/incomplete states use text/icon plus color.
- Focus never disappears behind chart overlays.
- Target placard selection/focus semantics match Deployment.

## 21. Acceptance screenshots / visual review

Required review configurations:

1. 1920×1080 FULL evidence, Mid-MPC, multiple targets, event-rich timeline.
2. 1440×900 same Run with compact rails.
3. REDUCED legacy Run.
4. FAILED/INCOMPLETE Run.
5. Historical AIS local view after migration.
6. DAY/DUSK/NIGHT chart palette where the existing application supports them; Replay controls remain legible.

## 22. UI Definition of Done

- Evaluation opens into a usable Replay for a completed replay-ready Run.
- Main chart visually matches Deployment semantics at the same stored frame.
- Timeline seeks instantly from the user's perspective without stepping simulation.
- Replay Speed supports 0.25×–20× presentation.
- Prev/Next Event works after arbitrary seek/rate changes.
- No Replay interaction invokes Active Session mutation endpoints.
- Historical AIS benchmark remains reachable and functional.
- Reduced/incomplete/unavailable evidence states are explicit.
- 1440×900 and 1920×1080 reviews pass without timeline obstruction or nested-scroll failure.
