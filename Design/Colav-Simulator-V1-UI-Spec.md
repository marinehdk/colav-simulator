# Colav-Simulator V1 UI & OpenBridge Specification

> **Status:** Companion specification to `Colav-Simulator-V1-PRD.md`  
> **Scope:** V1 UI architecture, screen inventory, interaction rules and OpenBridge implementation contract  
> **Design baseline:** Desktop/Large-Screen First, Dark default  
> **Last updated:** 2026-08-19

## 1. Design objective

The V1 UI shall feel like one coherent OpenBridge-derived professional marine engineering application, not a generic admin dashboard with a chart inserted into it.

At the same time, this is a **COLAV Engineering & V&V Workbench**, not an ECDIS/Radar type-approved bridge terminal. The UI must combine:

```text
Maritime Situation Awareness
+
Software Engineering
+
Verification & Validation Evidence
```

The application therefore uses one OpenBridge visual foundation with two semantic surfaces:

- **Maritime Operational Surface** — chart, ownship/targets, vectors, risk, encounter, run/replay and timeline.
- **Engineering Assurance Surface** — requirements, cases, algorithms/ADPs, evidence, regression gates, provenance and governance.

The two surfaces share tokens, typography, spacing, icons, selection/focus language and component density, but operational alarms and engineering assurance states retain different semantics.

## 2. OpenBridge implementation contract

### 2.1 Component reuse order

Every implementation decision follows this order:

```text
OB-NATIVE
→ OB-COMPOSED
→ OB-WRAPPED
→ COLAV-EXTENSION
→ CUSTOM-EXCEPTION
```

Definitions:

- `OB-NATIVE`: use the documented OpenBridge Web Component directly.
- `OB-COMPOSED`: compose multiple documented OpenBridge primitives.
- `OB-WRAPPED`: thin COLAV adapter around an OpenBridge component for framework/event/business integration.
- `COLAV-EXTENSION`: a domain-specific component OpenBridge does not supply, implemented using OpenBridge tokens/primitives.
- `CUSTOM-EXCEPTION`: unavoidable bespoke visual primitive, documented with reason and upgrade risk.

### 2.2 Mandatory component review

Before creating a new visual primitive, implementation shall:

1. Search the current OpenBridge Web Component catalog/Storybook.
2. Prefer an existing component when semantics are adequate.
3. Prefer composition before visual reimplementation.
4. Use a thin wrapper when only API/event/default behavior differs.
5. Create a COLAV extension only for genuinely missing domain visualization.
6. Record a justification for every Custom Exception.

### 2.3 Thin adapter responsibilities

A COLAV adapter may provide:

- framework integration;
- attribute/property normalization;
- event normalization;
- default props;
- domain semantic naming;
- accessibility glue;
- test selectors;
- OpenBridge version isolation.

It shall not become a second design system.

### 2.4 Prohibited OpenBridge customization

Default prohibited patterns:

- undocumented Shadow DOM access;
- dependency on internal component class names;
- deep private CSS selectors;
- copying/forking OpenBridge component implementation locally;
- arbitrary page-level resizing/restyling that changes native component identity;
- page-specific variants of the same primitive created through internal overrides.

Approved custom styling should use documented properties, slots, variants and tokens.

## 3. Design tokens

OpenBridge design tokens are the visual source of truth.

COLAV may create semantic aliases such as:

```text
--colav-state-published
--colav-state-candidate
--colav-state-historical
--colav-assurance-pass
--colav-assurance-fail
--colav-assurance-incomplete
--colav-capability-verified
--colav-capability-stale
--colav-attention-blocked
```

The alias should map to an OpenBridge token family wherever possible.

Business pages shall avoid arbitrary hex colors, font sizes, spacing values and duplicated state CSS.

## 4. Theme and maritime palette

Application Appearance:

```text
DARK      ← V1 default and primary QA baseline
LIGHT
SYSTEM
```

Maritime Chart Palette is an independent concern and may support, where the selected chart/OpenBridge implementation permits:

```text
DAY
DUSK
NIGHT
```

Application Light/Dark shall not be used as a substitute for maritime chart day/night palettes.

## 5. Semantic color budget

### 5.1 Neutral-by-default lifecycle

The following are normally neutral or low-salience:

```text
DRAFT
PUBLISHED
CANDIDATE
SEALED
HISTORICAL
NOT_VERIFIED
```

They are differentiated with text, icons, border/surface and typography rather than unique strong colors.

### 5.2 Assurance emphasis

Strong semantic emphasis is reserved for states such as:

```text
PASS
FAIL
INCOMPLETE
BLOCKED
INVALIDATED
REVALIDATION_REQUIRED
DEGRADED
```

### 5.3 Operational safety vs engineering assurance

A live collision/risk alert may use high-salience maritime operational treatment. A Regression Gate FAIL may use the same broad failure token family but must appear as an engineering gate state, not as a bridge alarm that flashes or requires operational acknowledgment.

No critical state may be represented by color alone.

## 6. Global application shell

### 6.1 Structure

```text
┌──────┬──────────────────────────────────────────────────────────┐
│ App  │ Engineering Context Ribbon                               │
│ Rail ├──────────────────────────────────────────────────────────┤
│      │                                                          │
│  W   │                                                          │
│  C   │                      WORKFACE                            │
│  R   │                                                          │
│  A   │                                                          │
│  G   │                                                          │
│      │                                                          │
│ ───  │                                                          │
│  ⌕   │                                                          │
│  !   │                                                          │
│  ⚙   │                                                          │
└──────┴──────────────────────────────────────────────────────────┘
```

### 6.2 App Rail

Primary workfaces:

```text
Workbench
Cases
Runs
Algorithms
Regression
```

Utilities:

```text
Object Navigator
Attention Center
Settings / Appearance
```

Default Rail is compact/icon-first with tooltip/focus label and strong current-selection indication. An expanded label mode may be provided, but expansion is Presentation State only.

### 6.3 Engineering Context Ribbon

The Ribbon answers **what engineering scope am I currently in?** It is not a hidden configuration editor.

Examples:

```text
WORKFLOW · FIX VERIFICATION
INV-024 · VERIFYING
HO-001@2 · FCB45-Nominal@4-candidate · c82fd18
```

```text
SEALED · HISTORICAL
R-104 · HO-001@2 · FCB45-Nominal@3 · b91c42e
```

```text
WORKFLOW · FAST MERGE GATE
c82fd18 · merge-baseline@4 · core-regression@6
```

The Ribbon shall maintain critical state even when Rails/panels collapse.

## 7. Navigation model

### 7.1 Primary navigation

Only the five Workfaces belong in the App Rail.

### 7.2 Secondary navigation

Use:

```text
Compact Local Header
+
Primary Tabs
+
Contextual Drawers
```

Do not create a permanent second left navigation column.

Examples:

```text
Run Detail
Overview | Replay | Evaluations | Evidence | Lineage
```

```text
ADP Detail
Overview | Configuration | Capabilities | Compatibility | Evidence | Lineage
```

```text
Algorithm
Overview | Implementations | ADPs | Capabilities | Diagnostics | Runs
```

### 7.3 Object Navigator

Global command palette / object search shall accept stable IDs and names such as:

```text
INV-024
R-104
HO-001@2
REG-037@1
FCB45-Nominal@3
COLREG-R14-STARBOARD@2
DH-024@2
RGA-2026-0041
```

Search results are grouped by object type and offer context-valid actions such as Open, Replay, Investigate, Reproduce, Compare, Use in Investigation or Copy Object Reference.

Open/Search affects Inspection Context only unless a separate explicit action changes task/execution context.

## 8. Attention model

### 8.1 Operational Events

Run-time facts belong to Run/Analyze/Replay timelines, e.g. CPA threshold crossing, Tracker lost, Planner fallback.

### 8.2 Immediate UI Alerts

Short-lived feedback such as Preflight failed, Run started or export completed may use banner/toast patterns.

### 8.3 Persistent Engineering Attention

Only lifecycle-bearing unresolved engineering issues enter Global Attention Center, e.g.:

- Regression Gate BLOCKED;
- Protected Baseline DEGRADED;
- Capability REVALIDATION_REQUIRED;
- Case/Profile INVALIDATED;
- Merge Waiver / Remediation OPEN;
- Baseline Transition BLOCKED.

Attention state:

```text
OPEN
ACKNOWLEDGED
IN_PROGRESS
RESOLVED
SUPERSEDED
```

`ACKNOWLEDGED` never means the underlying engineering condition is resolved.

## 9. Risk-tiered action model

### Tier 0 — Inspection

Open, search, select, pin, scrub, replay, filter, compare view. Immediate, no domain mutation.

### Tier 1 — Development Mutation

Draft/Candidate/Override/Hypothesis edits. Low-friction, revision-aware, undo where feasible.

### Tier 2 — Execution

Run, Reproduce, Re-evaluate, CORE, Fast Merge. Use resolved scope + Preflight rather than generic confirmation.

### Tier 3 — Governance / Immutable Asset

Publish Case/Profile/Suite, Promote ADP, Invalidate, Apply Baseline Transition. Require Impact Preview + eligibility + explicit semantic action.

### Tier 4 — Exception / Protection Reduction

Merge Waiver, Protection Reduction, exceptional baseline changes. Require explicit risk statement, compensating action, resolution condition and evidence record.

Button labels shall use semantic verbs such as `Publish ADP`, `Invalidate Case`, `Run Core Regression`, `Merge with Exception` rather than generic `Confirm`.

## 10. Reusable layout templates

### 10.1 SpatialWorkspaceLayout

Used by Workbench Run/Analyze/Compare, Historical Replay and Case Designer.

```text
┌───────────────────────────────────────────────────────────────┐
│ Local Header / Mode Tabs                                      │
├──────────────┬─────────────────────────────────┬──────────────┤
│ Left Rail    │ Primary Canvas                  │ Right Rail   │
│ optional     │ Chart / Timeline / Compare      │ optional     │
├──────────────┴─────────────────────────────────┴──────────────┤
│ Bottom Timeline / Controls / Diagnostics                      │
└───────────────────────────────────────────────────────────────┘
```

### 10.2 ExplorerLayout

Runs, Case Library, Algorithm Catalog.

### 10.3 ObjectDetailLayout

Run, Case, ADP, Requirement, Evaluation Profile, Gate Attestation and similar versioned objects.

### 10.4 AssuranceControlLayout

Regression V1; future Validation/Release.

Priority order:

```text
Current Decision
→ Blockers
→ Health/Coverage
→ Recent Evidence
→ Governance
```

### 10.5 GuidedWorkflowLayout

Algorithm Integration, Profile Qualification, Suite Change Proposal, Baseline Transition.

## 11. Responsive behavior

Primary design target: ≥1440×900. Primary optimization target: 1920×1080.

### ≥1920

Primary + secondary Rails can be visible where useful.

### 1440–1919

Primary task Rail remains; secondary Rail collapses to Drawer/Side Sheet.

### 1280–1439

Canvas dominates; Rails become contextual drawers. Critical state remains in Ribbon/status strip.

### <1280

Inspection-oriented compact mode. Complex authoring/governance may explicitly recommend a larger display.

Ultrawide space should add Evidence, diagnostics and Compare context rather than merely stretching the chart.

## 12. Scroll contracts

Every screen has one dominant scroll owner.

- SpatialWorkspace: viewport-locked; independent contextual rails/drawers may scroll.
- Analyze: timeline remains visible while detail pane scrolls.
- Explorer: explorer content is primary scroll owner; header/tabs may be sticky.
- Object Detail: document-like content scroll.
- Assurance Control: page scroll with compact sticky decision context.
- Guided Workflow: workflow content scroll.

Avoid nested `page → panel → card → list` vertical scroll chains.

## 13. Workspace presentation presets

Supported V1 patterns may include:

Workbench:

```text
Default Run
Focus Chart
Focus Diagnostics
```

Compare:

```text
Balanced Compare
Chart Compare
Diagnostic Compare
```

Case Designer:

```text
Balanced
Geometry Focus
Specification Focus
```

Users may persist bounded presentation preferences:

- Rail collapse/size within limits;
- timeline/diagnostic height;
- optional panels;
- table columns/density;
- saved views.

Engineering context values such as Case/ADP/Seed/Profile never belong in layout preferences.

## 14. Workbench screen specification

### 14.1 Workbench Home

Primary content order:

1. Resume Investigation card.
2. Recommended next action.
3. Recent Failures.
4. Recent Investigations.
5. Quick Reproduce.
6. Current Core Regression status.
7. New Investigation.

Resume card minimum content:

```text
Investigation ID / title
Lifecycle state
Last Run
Case
ADP
Last failure
Recommended next action
```

### 14.2 Investigation Header

Modes:

```text
Run | Analyze | Compare
```

Recommended mode derives from lifecycle. A user may continue last inspection state without changing lifecycle.

### 14.3 Run View

#### Center

Chart/ENC with:

- ownship;
- target vessels;
- Mission Route;
- actual tracks;
- selected/committed planner output;
- predictions;
- optional CPA/risk layers;
- selected POI/target;
- event markers.

#### Situation Rail

Ownship/navigation/sensor-source/quality/age/route/capability summary.

#### Context Rail

Encounter-first hierarchy:

```text
Encounter Focus
COLREG role/responsibility
Risk / CPA / TCPA
Target evidence
Planner response
Events
```

#### Bottom

Simulation timeline + execution controls + event markers.

### 14.4 Encounter Focus Stack

When roles differ:

```text
ALGORITHM
TS-03 · CROSSING
Planner focus

SYSTEM RISK
TS-07 · HEAD-ON
Highest monitored risk

INSPECTION
TS-05 · OVERTAKING
PINNED
```

When all roles coincide, merge into a compact `PRIMARY ENCOUNTER` panel with role markers.

Context divergence must be visible but not labeled as a bug without a confirmed finding.

### 14.5 Live time model

Normal:

```text
Execution 214.8 s
Inspection 214.8 s
LIVE EDGE
```

Historical inspection during live execution:

```text
LIVE RUN · HISTORICAL INSPECTION
Viewing 183.4 s
Live edge 215.2 s
Behind live 31.8 s
[Return to Live]
```

A new critical live event shall be surfaced without stealing the Inspection Cursor; provide `Jump to Live Event`.

### 14.6 Execution controls

Development:

```text
LIVE · RUNNING
[Pause] [Step] [SIM RATE] [Stop]
INTERACTIVE EXECUTION
```

CORE/Gate:

```text
AUTOMATED · LOCKED
Case 7 / 12
[Abort Gate]
```

Historical Replay:

```text
SEALED · HISTORICAL
[Play] [Prev Event] [Next Event] [Replay Speed]
```

### 14.7 Trajectory semantic layers

Default visible:

- Mission Route;
- Actual Tracks;
- Selected/Committed Plan;
- Predictions.

Optional:

- Candidate Plans;
- Rejected Plans;
- CPA Geometry;
- Risk Envelope.

Use line form/shape semantics in addition to color. Candidate plans are subdued and progressively disclosed.

Prediction detail exposes source, generated time, horizon, model/channel and validity/age. Stale prediction is visibly stale or removed according to contract.

### 14.8 Analyze View

Visual center is the Event-Synchronized Diagnostic Timeline, not the chart.

Suggested lanes:

```text
Encounter
Risk
Perception
Planner
Constraints
Control
Evaluator
Runtime
Annotations
```

Selecting a point/interval/transition updates Inspection Cursor, Chart preview, Context Rail, diagnostic detail and Evidence Explorer.

System may mark `FIRST ABNORMAL TRANSITION` and a Failure Window, but shall label it as diagnostic evidence/lead, not root cause.

### 14.9 Findings / hypotheses

Confirmed Investigation Finding UI shall separate:

- confirmed statement;
- affected Requirement;
- supporting evidence;
- rejected alternatives;
- proposed fix.

System diagnostic leads and user annotations remain visibly different from confirmed findings.

### 14.10 Compare View

Primary hierarchy:

1. Baseline/Candidate identity and verdict.
2. Comparison Contract / fidelity.
3. Controlled vs intended vs unexpected differences.
4. Outcome/Requirement/metric diff.
5. synchronized chart/timeline/diagnostic comparison.
6. Fix Verification result.

At 1920 width prioritize two observation surfaces over permanent multi-rail layouts.

Time alignment switch:

```text
Event: FIRST_AVOIDANCE_COMMAND
Absolute Simulation Time
```

Event alignment preserves visible absolute timing delta.

### 14.11 Fix Verification

Status card:

```text
NOT_STARTED
CANDIDATE
FIX_INDICATED
FIX_VERIFIED
FIX_REJECTED
```

`FIX_VERIFIED` shall show the exact baseline Run, candidate Run, target failure/Requirement, Comparison Fidelity and no-new-mandatory-failure evidence.

### 14.12 Debug Handoff

A dedicated Handoff preview should show immutable version identity and clearly group:

```text
Reproduction
Failure Facts
Execution Context
Diagnostics
Confirmed Findings
Open Hypotheses
Agent Task
Agent Change Contract
```

Exports: `summary.md` + structured JSON + Evidence Bundle references.

## 15. Cases screen specification

### 15.1 Case Library

Primary navigation/views:

```text
Requirements
Scenario Families
Regression
Drafts
All Cases
```

Strong facets:

- Encounter type;
- Purpose;
- Environment;
- Lifecycle;
- Requirement;
- Qualification.

Default landing emphasizes requirement coverage rather than raw case count.

### 15.2 Case Designer

```text
┌──────────────┬───────────────────────────────┬───────────────┐
│ TEST SPEC    │ CHART / ENC                   │ QUALIFICATION │
│ Intent       │ OS / TS / Route               │ L1 Definition │
│ Requirements │ CPA/TCPA / geometry           │ L2 Geometry   │
│ Preconditions│ encounter/risk overlays       │ L3 Test Intent│
│ Parameters   │ actor/event markers           │ L4 Execution  │
├──────────────┴───────────────────────────────┴───────────────┤
│ Parameters | Expected Behavior | Events | Advanced | Diff    │
└──────────────────────────────────────────────────────────────┘
```

At compact widths, Test Specification is Primary Rail; Qualification becomes contextual drawer while its summary remains visible.

### 15.3 Encounter-centric parameters

Prefer authoring controls for:

- relative bearing;
- reciprocal/course relation;
- speed ratio/absolute speed;
- initial range;
- desired TCPA/DCPA envelope;
- geometry tolerance.

Clearly distinguish `AUTHORING` from `DERIVED/COMPILED` values.

### 15.4 Exact State mode

Switching between Encounter Parameters and Exact State is an explicit conversion action with an explanatory impact preview. Do not keep both editable as competing sources of truth.

### 15.5 Traffic Actors

Each target has a behavior panel and events timeline with nominal behavior plus scripted/triggered maneuvers. Selecting a maneuver synchronizes chart and parameters.

### 15.6 Encounter Intent Graph

For multi-ship, surface required/allowed/background/prohibited encounter intents and Qualification comparison to derived interactions. Avoid covering the chart with a complex full graph by default; use lightweight overlays and structured side detail.

### 15.7 Test Phase Timeline

Display semantic phases such as Setup, Encounter, Response, Passing, Recovery with event anchors. The design distinguishes Expected Phase Contract from resolved observed phases on a Run.

### 15.8 Qualification Preview

Special mode banner:

```text
CASE QUALIFICATION PREVIEW
Scenario validity: ...
Algorithm capability: NOT EVALUATED
```

Preview supports playback/scrub to inspect encounter activation, scripted maneuvers, unexpected interactions, phase resolution and termination.

## 16. Runs screen specification

### 16.1 Run Explorer

Default main content is dense evidence-aware table.

System views:

```text
Recent | Failures | Investigations | Reproductions | Core Regression | Crashed/Incomplete
```

Suggested default columns:

```text
Run
Purpose
Investigation
Case
Algorithm / ADP
Source
Execution
Original Verdict
Evidence
Trust
Failure Domain
Created
```

Expandable row provides rapid read-only summary and actions without leaving Explorer.

### 16.2 Query presentation

Active filters are visible as chips/summary. Display total-vs-filtered count, e.g. `4 of 2,481 Runs · 5 active filters` with Clear Filters.

Back navigation must restore query and scroll position.

### 16.3 Run Detail header

Stable identity plus semantic landing.

PASS prioritizes key results; FAIL prioritizes failed requirement/time/failure summary; CRASH/INCOMPLETE prioritizes runtime/missing-evidence information.

Tabs:

```text
Overview | Replay | Evaluations | Evidence | Lineage
```

### 16.4 Core Run Summary

Stable cross-algorithm summary groups:

```text
Safety
Encounter
COLREG
Navigation/Recovery
Planner health
Runtime health
```

Profile-specific and algorithm-specific diagnostics follow below/behind disclosure.

### 16.5 Historical Replay

Shared Observation Surface with persistent `SEALED · HISTORICAL`. There is no `Restart Simulation` button. `Reproduce` creates a new Run through Preflight.

### 16.6 Evaluations

Always label Original Evaluation separately from Re-evaluations. Support Evaluation Diff. If a new profile cannot be applied because evidence is missing, show `NOT_EVALUABLE` with missing evidence.

### 16.7 Evidence Explorer

Header:

```text
Capture Profile
Integrity
Completeness
Captured Until
Artifact Count
```

Domain groups:

```text
Experiment Identity
Navigation / Truth
Perception
Encounter / Risk
Planner
Control / Dynamics
Evaluation
Runtime
```

Typed algorithm diagnostic groups appear only when declared/available.

### 16.8 Evidence Trust

Show Original Verdict next to Current Trust; do not replace one with the other.

Example:

```text
Original Verdict: PASS
Current Trust: IMPACTED
Reason: referenced Case was INVALIDATED
```

### 16.9 Lineage

Default: concise engineering path with current object highlighted. Full graph is local/expandable and object references remain clickable.

## 17. Algorithms screen specification

### 17.1 Catalog

Each algorithm card/row shows independent:

```text
Role
Runtime Readiness
Implementation count
ADP count
Validation summary
Capability coverage summary
Attention count
```

Do not use one generic `READY` badge to imply validation.

### 17.2 Algorithm Overview

Generic entry lands on `Algorithm Overview`, showing cross-ADP coverage without mixed grade.

Example:

```text
Rule 14
G4 CURRENT          1 ADP
G3 REVALIDATION     1 ADP
NOT VERIFIED        1 ADP
```

### 17.3 ADP Scope

Explicit selector changes Inspection Scope. ADP detail is clearly labeled `PUBLISHED · IMMUTABLE`, `CANDIDATE`, etc.

ADP tabs:

```text
Overview | Configuration | Capabilities | Compatibility | Evidence | Lineage
```

### 17.4 Capability Matrix

Cell displays:

```text
Verified Grade
Evidence State
```

Examples:

```text
G4
VERIFIED
```

```text
G3
REVALIDATION REQUIRED
```

```text
—
DECLARED · NOT VERIFIED
```

Cell detail drawer exposes declared support, technical compatibility, exact scope, coverage, compliance and evidence basis.

Do not map G0–G4 to a red-to-green gradient.

### 17.5 ADP Candidate

Candidate view continuously displays structured Diff and Validation Impact. Candidate never visually inherits existing verified capability as current.

Actions:

```text
Open in Workbench
Run Preflight
Promote ADP
```

Promotion includes impact preview and creates a new immutable version.

### 17.6 Integration workspace

Guided steps:

```text
1 Manifest
2 Interface/Contract
3 Dependencies/Runtime
4 Smoke Test
5 Diagnostics
6 Create Artifact
```

Failures must be actionable and identify schema/channel/runtime mismatch, not merely `Integration failed`.

## 18. Regression screen specification

### 18.1 Regression Control Center

First screen answers current Gate status.

```text
FAST MERGE GATE
Candidate
Protected Baseline Set
Core Suite / Policy

PASS / FAIL / INCOMPLETE summary
```

Then:

1. Blockers.
2. Suite Health.
3. Core Coverage summary.
4. Recent Gates.
5. Baseline Transitions.
6. Waivers/Remediation.
7. Suite Management.

### 18.2 Gate blockers

Behavioral FAIL and INCOMPLETE must be visually and textually distinct.

Example:

```text
FAIL
CR-CORE-003@1
Rule 15 / COLREG-R15-004
Run R-411
```

```text
INCOMPLETE
REG-037@1
SOLVER_RUNTIME / worker crashed
Run R-414
```

### 18.3 Protected baselines

Show each baseline ADP + Core Suite status and overall Gate aggregation. Targeted ADP CORE is labeled separately from full Fast Merge Gate.

### 18.4 Gate Attestation

Object Detail includes original verdict, current trust, exact source/baseline/suite/profile/environment, execution groups and Evidence links.

### 18.5 Baseline Transition

Guided workflow shows Current Baseline and Proposed Successor side by side, required evidence, impact capability checklist and lifecycle state.

### 18.6 Merge Waiver

Tier-4 interaction. Screen must explicitly state:

```text
Gate Verdict remains FAIL/INCOMPLETE.
This action creates MERGED_WITH_EXCEPTION.
```

Require reason, risk statement, compensating action and resolution condition.

### 18.7 Suite Change Proposal

Show Add/Replace/Remove operations and computed Protection Diff. `ACTIVE_FAILURE_PROTECTION_REMOVAL` requires high-salience governance treatment and explicit justification.

## 19. Preflight UI

Preflight is a reusable COLAV extension/composition used by Run, Reproduce, CORE, Gate, Profile/Case workflows where execution scope matters.

Recommended structure:

```text
RUN PREFLIGHT

Case
ADP
Source
Environment
Perception/Tracker
Evaluation Profile
Seed / Random Streams
Evidence Capture Profile

Execution Compatibility
Evaluation Compatibility
Validation Coverage
Environment Qualification
Reproducibility Eligibility
Formal Claim Eligibility

Result
READY / READY_WITH_LIMITATIONS / BLOCKED
```

Preflight should explain limitations and missing evidence capability before execution.

## 20. OpenBridge conformance matrix template

Detailed implementation/design review shall maintain a table similar to:

| COLAV UI | Reuse class | OpenBridge basis | Extension/custom style | Notes |
|---|---|---|---|---|
| Primary Button | OB-NATIVE | Button | None | native behavior |
| Context Ribbon | OB-COMPOSED | text/tag/icon/button primitives | token-only | COLAV layout composition |
| ADP Selector | OB-WRAPPED | select/menu primitive | token-only | domain object adapter |
| Capability Matrix | COLAV-EXTENSION | OB typography/status/control primitives | domain matrix styles | evidence-first cells |
| Diagnostic Timeline | COLAV-EXTENSION | OB primitives/tokens | domain visualization | typed event lanes |
| Custom exception | CUSTOM-EXCEPTION | N/A | documented | approval required |

The exact OpenBridge component names shall be resolved against the pinned OpenBridge dependency/catalog used by the implementation branch; no design document shall rely on private component internals.

## 21. Critical UI states to design and test

Every P0 screen shall include explicit designs/tests for relevant states, not only the happy path:

```text
EMPTY
LOADING
READY
RUNNING
PAUSED
LIVE HISTORICAL INSPECTION
PASS
FAIL
INCOMPLETE
CRASHED
BLOCKED
SEALED HISTORICAL
DRAFT
CANDIDATE
PUBLISHED
INVALIDATED
REVALIDATION_REQUIRED
STALE / IMPACTED
NOT_AVAILABLE
NOT_EVALUABLE
```

## 22. P0 screen inventory

### Global

- Application Shell.
- Object Navigator.
- Attention Center.
- Settings/Appearance.

### Workbench

- Workbench Home / Resume.
- Investigation Run.
- Investigation Analyze.
- Investigation Compare.
- Finding editor/detail.
- Debug Handoff preview/export.
- Agent Result import/review.
- Run Preflight.

### Cases

- Requirement-centered Case Library.
- Scenario Family detail.
- Case Designer.
- Case Qualification Preview.
- Published Case Detail/Versions.
- Regression promotion flow.

### Runs

- Run Explorer.
- Run Overview.
- Historical Replay.
- Evaluation History/Diff.
- Evidence Explorer.
- Lineage/Provenance.
- Evidence Bundle export/import.

### Algorithms

- Algorithm Catalog.
- Algorithm Overview.
- Implementation Artifact Detail.
- ADP Detail.
- ADP Candidate editor/diff.
- Capability Matrix/Detail.
- Compatibility/Preflight detail.
- Algorithm Integration workflow.

### Regression

- Regression Control Center.
- Execution Group / Gate run detail.
- Gate Attestation detail.
- Protected Baseline Set detail.
- Baseline Transition.
- Suite detail/version history.
- Suite Change Proposal.
- Merge Waiver / Remediation.

## 23. Accessibility and interaction quality

- Keyboard focus shall remain visible in dark and light themes.
- App Rail icon-only mode shall provide accessible labels/tooltips.
- State shall not be conveyed only by color.
- Tables/matrices shall provide text equivalents for semantic status.
- High-impact actions shall expose scope and consequences before mutation.
- Timeline/event/chart selection shall preserve clear focus/selected state.
- Historical/live/candidate modes shall use persistent labels, not transient notifications only.

## 24. UI acceptance criteria

UI is accepted for V1 only when:

1. Golden Workflow can be completed without leaving official product paths except the external code edit itself.
2. Live, Replay, Analyze and Compare visibly preserve source/time/context semantics.
3. PASS/FAIL/INCOMPLETE and Historical/Current Trust are not conflated.
4. OpenBridge Conformance Matrix is complete for P0 components.
5. No undocumented OpenBridge internal styling hacks exist.
6. Dark 1440×900 and 1920×1080 P0 layouts pass design review.
7. Compact desktop preserves critical state when Rails collapse.
8. Custom Exceptions are documented and minimized.
9. Maritime Operational Alerts and Engineering Attention/Gates use distinct semantics.
10. Inspection interactions cannot silently mutate execution context.
