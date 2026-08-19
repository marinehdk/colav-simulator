# Colav-Simulator V1 UI & OpenBridge Specification

> **Status:** Companion specification to `Colav-Simulator-V1-PRD.md`; review corrections applied  
> **Scope:** V1 UI architecture, screen inventory, interaction rules and OpenBridge implementation contract  
> **Design baseline:** Desktop/Large-Screen First, Dark default  
> **Last updated:** 2026-08-19

## 1. Design objective

The V1 UI shall feel like one coherent OpenBridge-derived professional marine engineering application, not a generic admin dashboard with a chart inserted into it.

This is a **COLAV Engineering & V&V Workbench**, not an ECDIS/Radar type-approved bridge terminal. It combines:

```text
Maritime Situation Awareness
+
Software Engineering
+
Verification & Validation Evidence
```

One OpenBridge visual foundation supports two semantic surfaces:

- **Maritime Operational Surface** — chart, ownship/targets, vectors, risk, encounter, run/replay and timeline.
- **Engineering Assurance Surface** — requirements, cases, algorithms/ADPs, evidence, regression gates, provenance and governance.

They share tokens, typography, spacing, icons, selection/focus language and component density. Operational alarms and engineering assurance states retain different semantics.

## 2. OpenBridge implementation contract

### 2.1 Component reuse order

```text
OB-NATIVE
→ OB-COMPOSED
→ OB-WRAPPED
→ COLAV-EXTENSION
→ CUSTOM-EXCEPTION
```

- `OB-NATIVE`: documented OpenBridge Web Component directly.
- `OB-COMPOSED`: compose documented OpenBridge primitives.
- `OB-WRAPPED`: thin COLAV adapter for framework/event/business integration.
- `COLAV-EXTENSION`: missing COLAV/V&V domain visualization using OpenBridge tokens/primitives.
- `CUSTOM-EXCEPTION`: unavoidable bespoke primitive with documented reason/upgrade risk.

### 2.2 Mandatory component review

Before a new visual primitive:

1. Search the pinned OpenBridge component catalog/Storybook.
2. Prefer existing semantics when adequate.
3. Prefer composition before reimplementation.
4. Wrap when only API/event/default behavior differs.
5. Create COLAV extension only for genuinely missing domain visualization.
6. Document every Custom Exception.

### 2.3 Thin adapter responsibilities

Allowed:

- framework integration;
- attribute/property normalization;
- event normalization;
- defaults;
- domain semantic naming;
- accessibility glue;
- test selectors;
- OpenBridge version isolation.

It shall not become a second design system.

### 2.4 Prohibited customization

Default prohibited:

- undocumented Shadow DOM access;
- dependency on internal component class names;
- deep private CSS selectors;
- copying/forking OpenBridge component implementation locally;
- arbitrary page-level restyling that changes native component identity;
- page-specific internal overrides of the same primitive.

Use documented properties, slots, variants and tokens.

### 2.5 Dependency and license provenance

UI implementation shall not assume a generic “OpenBridge license.” Before the selected OpenBridge dependency/catalog is accepted, the implementation branch must record:

```text
Exact package/repository/catalog version or commit
Official source/provenance URL
Applicable license(s)
Attribution / NOTICE requirements
Distribution/commercial compatibility decision
THIRD_PARTY_NOTICES / dependency inventory update
```

The UI Conformance Review is incomplete until this provenance record exists for the exact selected artifacts.

## 3. Design tokens and themes

OpenBridge design tokens are visual source of truth. COLAV may add semantic aliases such as:

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

Aliases map to OpenBridge token families wherever possible. Business pages avoid arbitrary hex colors, font sizes, spacing values and duplicated state CSS.

Application Appearance:

```text
DARK      ← V1 default / primary QA baseline
LIGHT
SYSTEM
```

Maritime Chart Palette, where supported, is independent:

```text
DAY
DUSK
NIGHT
```

## 4. Semantic color budget

Lifecycle states such as `DRAFT`, `PUBLISHED`, `CANDIDATE`, `SEALED`, `HISTORICAL`, `NOT_VERIFIED` are neutral/low-salience by default.

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

Operational Safety and Engineering Assurance use different presentation semantics even when sharing broad semantic token families. No critical state is color-only.

## 5. Global application shell

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

### 5.1 App Rail

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
Engineering Workspace / Settings
Appearance
```

Rail is compact/icon-first with tooltip/accessible label and clear current selection. Expanded mode is Presentation State only.

### 5.2 Engineering Context Ribbon

Answers **what engineering scope am I in?** It is not a hidden configuration editor.

Examples:

```text
WORKFLOW · FIX VERIFICATION
INV-024 · VERIFYING
HO-001@2 · FCB45-Nominal@4-candidate · source-snapshot ss-024-017
```

```text
SEALED · HISTORICAL
R-104 · HO-001@2 · FCB45-Nominal@3 · implementation b91c42e
```

```text
WORKFLOW · FAST MERGE GATE
candidate c82fd18 · merge-baseline@4 · core-regression@6
```

Critical state remains visible when Rails/panels collapse.

## 6. Navigation and object ownership

### 6.1 Secondary navigation

Use:

```text
Compact Local Header
+
Primary Tabs
+
Contextual Drawers
```

No permanent second left navigation column.

Examples:

```text
Run Detail
Overview | Replay | Evaluations | Evidence | Lineage
```

```text
ADP Detail
Overview | Configuration | Capabilities | Compatibility | Evidence | Lineage
```

### 6.2 Object Navigator

Accept stable IDs/names such as:

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

Results grouped by object type with context-valid actions. Open/Search changes Inspection Context only unless explicit action changes execution context.

### 6.3 Requirement & Evaluation Hub

`Cases > Requirements` is the V1 local hub for first-class Requirement/Evaluation assets without adding a sixth Workface.

Local views/routes:

```text
Requirement Catalog
Requirement Detail / Versions
Evaluation Profiles
Evaluation Profile Qualification
Coverage Contracts / Coverage Matrix
Golden Evidence Fixtures
```

Opening an Evaluation Profile or Coverage Contract is inspection/authoring of that asset; it does not silently change a Workbench RunSpec.

### 6.4 Engineering Workspace / Environment

Global Settings/Engineering Workspace owns inspection/registration of:

```text
Registered SourceWorkspaces
SourceSnapshot history / identity
Execution Environment Profiles
Environment qualification state
```

Selecting a workspace/environment for inspection does not silently change an Investigation or pending Run execution context. Changes enter Run context only through explicit `Use in Investigation` / Preflight-resolved actions.

## 7. Attention model

Separate:

1. **Operational Events** — Run/Analyze/Replay timeline facts such as CPA threshold, Tracker lost, Planner fallback.
2. **Immediate UI Alerts** — short-lived feedback such as Preflight failed/Run started/export complete.
3. **Persistent Engineering Attention** — lifecycle-bearing unresolved issues such as Gate BLOCKED, Baseline DEGRADED, Capability REVALIDATION_REQUIRED, Case/Profile INVALIDATED, Waiver/Remediation OPEN.

Attention state:

```text
OPEN
ACKNOWLEDGED
IN_PROGRESS
RESOLVED
SUPERSEDED
```

`ACKNOWLEDGED ≠ RESOLVED`.

## 8. Risk-tiered action model

Exactly five tiers:

- **Tier 0 — Inspection:** open/search/select/pin/scrub/replay/filter.
- **Tier 1 — Development Mutation:** Draft/Candidate/Override/Hypothesis edits.
- **Tier 2 — Execution:** Run/Reproduce/Re-evaluate/CORE/Fast Merge using Preflight.
- **Tier 3 — Governance / Immutable Asset:** Publish/Promote/Invalidate/Apply Transition using Impact Preview.
- **Tier 4 — Exception / Protection Reduction:** Merge Waiver/Protection Reduction with risk/remediation evidence.

Use semantic action labels such as `Publish ADP`, `Invalidate Case`, `Run Core Regression`, `Merge with Exception`.

## 9. Reusable layout templates

### 9.1 SpatialWorkspaceLayout

Workbench Run/Analyze/Compare, Historical Replay, Case Designer.

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

### 9.2 ExplorerLayout

Runs, Case Library, Requirement Catalog, Algorithm Catalog.

### 9.3 ObjectDetailLayout

Run, Case, Requirement, Evaluation Profile, Coverage Contract, Algorithm, ADP, Implementation Artifact, SourceSnapshot, Environment Profile, Gate Attestation.

### 9.4 AssuranceControlLayout

Regression V1; future Validation/Release.

```text
Current Decision
→ Blockers
→ Health/Coverage
→ Recent Evidence
→ Governance
```

### 9.5 GuidedWorkflowLayout

Algorithm Integration, Profile Qualification, Case Qualification, Suite Change Proposal, Baseline Transition.

## 10. Responsive behavior and scroll

Primary design target ≥1440×900; optimized around 1920×1080.

- ≥1920: primary + secondary Rails where useful.
- 1440–1919: primary Rail visible; secondary to Drawer/Side Sheet.
- 1280–1439: Canvas dominant; Rails become contextual drawers; critical state remains visible.
- <1280: inspection-oriented compact mode; complex authoring/governance may recommend larger display.

Ultrawide adds Evidence/diagnostics/Compare context rather than merely stretching chart.

One dominant scroll owner per screen:

- Spatial Workspace viewport-locked.
- Analyze keeps timeline visible while detail pane scrolls.
- Explorer content scroll.
- Object Detail document-like scroll.
- Assurance Control page scroll + compact sticky decision context.
- Guided Workflow content scroll.

Avoid nested `page → panel → card → list` vertical scroll chains.

## 11. Workspace presentation presets

Examples:

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

Persist bounded Presentation preferences only: Rail collapse/size, timeline height, optional panels, table columns/density, saved views. Case/ADP/Seed/Profile/Source are never layout preferences.

## 12. Workbench screen specification

### 12.1 Workbench Home

Order:

1. Resume Investigation.
2. Recommended next action.
3. Recent Failures.
4. Recent Investigations.
5. Quick Reproduce.
6. Current Core Regression status.
7. New Investigation.

Resume card: Investigation ID/title, lifecycle, Last Run, Case, ADP/config, last failure, recommended next action.

### 12.2 Investigation modes

```text
Run | Analyze | Compare
```

Recommended mode derives from lifecycle. Last Inspection State can be restored without changing lifecycle.

### 12.3 Run View

Center Chart/ENC includes:

- ownship/targets;
- **Mission Route**;
- actual tracks;
- **Selected/Accepted Planner Output**;
- predictions;
- optional CPA/risk layers;
- selected POI/target;
- event markers.

`Selected/Accepted Planner Output` is algorithm-agnostic UI language. Where diagnostics expose repository concepts, render canonical terms exactly:

```text
Mission Route
Avoidance Corridor
Horizon Encounter Plan
Hard Row Window
Rolling Plan
Plan Revision
```

Do not label Mission Route as “committed route”; do not label Rolling Plan as warm start/current candidate.

Situation Rail: ownship/navigation/sensor-source/quality/age/route/capability summary.

Context Rail:

```text
Encounter Focus
COLREG role/responsibility
Risk / CPA / TCPA
Target evidence
Planner response
Events
```

Bottom: Simulation Timeline + execution controls + event markers.

### 12.4 Encounter Focus Stack

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

When all coincide, merge to `PRIMARY ENCOUNTER` with role markers. Divergence is diagnostic, not automatically labeled bug.

### 12.5 Live time model

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

Critical new live event is surfaced without stealing Inspection Cursor; provide `Jump to Live Event`.

### 12.6 Execution controls

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

UI shall not conflate `STOPPED`, `ABORTED`, `CANCELLED`, `CRASHED` or Evaluation FAIL.

### 12.7 Trajectory semantic layers

Default visible:

- Mission Route;
- Actual Tracks;
- Selected/Accepted Planner Output;
- Predictions.

Optional:

- Candidate Plans;
- Rejected Plans;
- CPA Geometry;
- Risk Envelope.

Use line/shape semantics in addition to color. Prediction detail exposes source, generated time, horizon, model/channel, validity/age.

### 12.8 Analyze View

Visual center = Event-Synchronized Diagnostic Timeline.

Lanes:

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

Selecting Point/Interval/Transition updates Inspection Cursor, Chart preview, Context Rail, diagnostics and Evidence Explorer.

`FIRST ABNORMAL TRANSITION`/Failure Window is diagnostic evidence/lead, not root cause.

### 12.9 Findings / hypotheses

Confirmed Finding UI separates statement, affected Requirement, supporting evidence, rejected alternatives, proposed fix. Diagnostic leads/user annotations remain distinct.

### 12.10 Compare

Hierarchy:

1. Baseline/Candidate identity/verdict.
2. Comparison Contract/Fidelity.
3. Controlled/intended/known/unexpected differences.
4. Outcome/Requirement/metric diff.
5. synchronized chart/timeline/diagnostic comparison.
6. Fix Verification result.

At 1920 prioritize two observation surfaces over multi-rail five-column layout.

Alignment:

```text
Event: FIRST_AVOIDANCE_COMMAND
Absolute Simulation Time
```

Absolute timing delta remains visible.

### 12.11 Fix Verification

```text
NOT_STARTED
CANDIDATE
FIX_INDICATED
FIX_VERIFIED
FIX_REJECTED
```

`FIX_VERIFIED` shows exact Baseline Run, Candidate Run, target Requirement/failure, Comparison Fidelity and no-new-mandatory-failure evidence.

### 12.12 Debug Handoff / Agent Result

Handoff preview groups:

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

Exports `summary.md` + structured JSON + Evidence Bundle refs.

Agent Result review displays changed files/source identity, Agent-side tests, contract compliance, protected-asset change requests and `PLATFORM RE-VERIFICATION REQUIRED`.

## 13. Cases and Requirement/Evaluation screen specification

### 13.1 Case Library

Views:

```text
Requirements
Scenario Families
Regression
Drafts
All Cases
```

Strong facets: Encounter, Purpose, Environment, Lifecycle, Requirement, Qualification.

### 13.2 Requirements Hub

`Requirements` landing emphasizes Coverage/Requirement navigation and provides local tabs/links:

```text
Requirements | Evaluation Profiles | Coverage | Golden Evidence
```

Requirement Detail:

```text
Overview | Applicability | Expected Behavior | Evaluator Bindings | Evidence | Versions
```

Evaluation Profile Detail:

```text
Overview | Requirement Bindings | Evaluators | Thresholds | Evidence Requirements | Qualification | Versions
```

Profile Qualification clearly shows Static Validation, Evaluator Verification, Golden Evidence and Verdict Diff.

Coverage Contract Detail displays required cells, current Evidence Coverage, Compliance and lineage; Coverage and Compliance use separate visual columns/states.

### 13.3 Case Designer

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

Compact widths: Test Specification Primary Rail; Qualification becomes Drawer while summary remains visible.

### 13.4 Encounter-centric parameters / Exact State

Prefer relative bearing, course relation, speed, initial range, desired TCPA/DCPA envelope, geometry tolerance. Distinguish `AUTHORING` vs `DERIVED/COMPILED`.

Switch Encounter Parameters ↔ Exact State is explicit conversion with impact preview; never keep two editable sources of truth.

### 13.5 Traffic Actors / Encounter Intent / Phases

Traffic Actor panels show nominal behavior + scripted/triggered maneuvers. Multi-ship shows Required/Allowed/Background/Prohibited intents and derived comparison using lightweight chart overlays. Test Phase Timeline shows Setup/Encounter/Response/Passing/Recovery with event anchors.

### 13.6 Qualification Preview

Persistent banner:

```text
CASE QUALIFICATION PREVIEW
Scenario validity: ...
Algorithm capability: NOT EVALUATED
Qualification policy: SQP@...
```

Preview playback/scrub exposes encounter activation, maneuvers, unexpected interactions, phase resolution and termination.

## 14. Runs screen specification

### 14.1 Run Explorer

Dense evidence-aware table. Views:

```text
Recent | Failures | Investigations | Reproductions | Core Regression | Crashed/Incomplete
```

Suggested columns:

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
Trust / Impact
Failure Domain
Created
```

Expandable row for rapid read-only summary/actions.

### 14.2 Query state

Active filters visible; show filtered/total count and Clear Filters. Back restores query/scroll position.

### 14.3 Run Detail

PASS prioritizes key results; behavioral FAIL prioritizes failed Requirement/time; CRASH/INCOMPLETE prioritizes runtime/missing Evidence.

Tabs:

```text
Overview | Replay | Evaluations | Evidence | Lineage
```

Run header/status must preserve independent axes:

```text
Record: SEALED
Execution: CRASHED
Evaluation: INCOMPLETE · NOT_ESTABLISHED
```

or

```text
Record: SEALED
Execution: FINISHED
Evaluation: COMPLETE · FAIL
```

### 14.4 Core Run Summary

Groups Safety, Encounter, COLREG, Navigation/Recovery, Planner health, Runtime health. Profile-/algorithm-specific diagnostics follow by disclosure.

### 14.5 Historical Replay

Shared Observation Surface with persistent `SEALED · HISTORICAL`; no Restart Simulation. `Reproduce` creates new Run via Preflight.

### 14.6 Evaluations

Original Evaluation distinct from Re-evaluations. Evaluation Diff supported. Insufficient evidence → `NOT_EVALUABLE` with missing evidence.

The reconstructed evaluator's provenance must remain visible where it is the active basis, including `functional_reproduction` / numerical-not-confirmed boundary; UI must not imply official numerical reproduction.

### 14.7 Evidence Explorer

Header:

```text
Capture Profile
Integrity
Completeness
Captured Until
Artifact Count
```

Groups Experiment Identity, Navigation/Truth, Perception, Encounter/Risk, Planner, Control/Dynamics, Evaluation, Runtime, typed diagnostics.

Evidence state explicitly distinguishes `NOT_AVAILABLE`, `NOT_CAPTURED`, `MISSING`, `CORRUPT`, `SCHEMA_MISMATCH`.

### 14.8 Evidence Trust and Eligibility

Do not collapse to one status.

Example:

```text
Original Verdict    PASS
Current Trust       IMPACTED
Reason              referenced Case INVALIDATED

Claim Eligibility
Development/Diagnosis        ELIGIBLE
Core Regression Claim        NOT ELIGIBLE
Rule 14 Capability Claim     REVALIDATION REQUIRED
```

### 14.9 Lineage

Concise engineering path by default; full graph local/expandable; object refs clickable.

## 15. Algorithms screen specification

### 15.1 Catalog

Each row/card shows:

```text
Role
Runtime Readiness
Implementation count
ADP count
Validation summary
Capability coverage summary
Attention count
```

No generic READY implying validation.

### 15.2 Role-aware scope

Role is a primary facet. Dynamic COLAV, static ENC/global planning, tracker and nominal guidance algorithms are not automatically compared against the same capability dimensions.

When a capability dimension does not apply to an algorithm role, show a role-aware state such as `NOT APPLICABLE TO ROLE`, not `NOT VERIFIED`.

### 15.3 Algorithm Overview / ADP Scope

Generic entry = Algorithm Overview showing cross-ADP coverage without mixed grade. Explicit ADP selector changes Inspection Scope only.

ADP tabs:

```text
Overview | Configuration | Capabilities | Compatibility | Evidence | Lineage
```

### 15.4 G0–G4 Capability Matrix

Vocabulary:

```text
G0 Discoverable
G1 Short smoke test
G2 Full closed loop
G3 Capability demonstration
G4 Benchmark validation
```

Cell displays derived Grade + Evidence State and never maps G0–G4 to red→green gradient.

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

```text
—
NOT APPLICABLE TO ROLE
```

Detail drawer exposes role, declared support, technical compatibility, exact ADP/conditions, Coverage, Compliance and Evidence basis.

CORE PASS is not visually equated to G4.

### 15.5 Source identity

Algorithm/ADP surfaces distinguish:

```text
SourceWorkspace             mutable working state
Ephemeral SourceSnapshot    frozen development source
Implementation Artifact     immutable formal implementation identity
```

Published ADP always points to Implementation Artifact. Candidate/Development UI may show SourceSnapshot until promotion.

### 15.6 ADP Candidate

Continuous structured Diff + Validation Impact. Candidate never visually inherits existing verified capability as current.

Actions:

```text
Open in Workbench
Run Preflight
Promote ADP
```

Promotion impact preview explicitly requires immutable Implementation Artifact.

### 15.7 Integration workspace

```text
1 Manifest
2 Interface/Contract
3 Dependencies/Runtime
4 Smoke Test
5 Diagnostics
6 Create Artifact
```

Smoke may operate on candidate source before Published ADP. Failures identify exact schema/channel/runtime mismatch.

## 16. Regression screen specification

### 16.1 Control Center

First screen answers Gate status:

```text
FAST MERGE GATE
Candidate
Protected Baseline Set
Core Suite / Policy
PASS / FAIL / INCOMPLETE
```

Then Blockers, Suite Health, Core Coverage, Recent Gates, Baseline Transitions, Waivers/Remediation, Suite Management.

### 16.2 Blockers

Behavioral FAIL vs INCOMPLETE visually/textually distinct.

### 16.3 Protected baselines

Each baseline ADP + Core Suite status; Targeted CORE clearly distinct from full Fast Merge Gate.

### 16.4 Gate Attestation

Original verdict, current trust, exact source/baseline/suite/profile/environment, ExecutionGroups and Evidence links.

### 16.5 Baseline Transition / Suite Change / Waiver

Guided workflows show current/proposed identity, required evidence/impact and lifecycle. `ACTIVE_FAILURE_PROTECTION_REMOVAL` has high-salience governance treatment.

Merge Waiver explicitly states:

```text
Gate Verdict remains FAIL/INCOMPLETE.
This action creates MERGED_WITH_EXCEPTION.
```

Require reason, risk statement, compensating action, resolution condition.

## 17. Preflight UI

Reusable Preflight supports purpose-aware bindings.

Example:

```text
RUN PREFLIGHT

Purpose
Case / Qualification Policy where applicable
Algorithm / ADP / candidate config where applicable
Source: Snapshot or Implementation Artifact
Environment
Perception / Tracker
Evaluation Profile if requested
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

A `CASE_QUALIFICATION` Preflight does not require a Published ADP. An `INTEGRATION_SMOKE` Preflight may occur before ADP publication. A formal CORE Preflight requires Published immutable ADP and Qualified Environment.

## 18. OpenBridge conformance matrix

Maintain a matrix:

| COLAV UI | Reuse class | OpenBridge basis | Extension/custom style | Notes |
|---|---|---|---|---|
| Primary Button | OB-NATIVE | Button | None | native behavior |
| Context Ribbon | OB-COMPOSED | text/tag/icon/button primitives | token-only | COLAV composition |
| ADP Selector | OB-WRAPPED | select/menu primitive | token-only | domain adapter |
| Capability Matrix | COLAV-EXTENSION | OB typography/status/control primitives | domain matrix styles | evidence-first |
| Diagnostic Timeline | COLAV-EXTENSION | OB primitives/tokens | domain visualization | typed lanes |
| Custom exception | CUSTOM-EXCEPTION | N/A | documented | approval required |

Conformance record shall also identify the pinned OpenBridge source/version/license-provenance record used for review. Exact component names are resolved against the pinned catalog; no reliance on private internals.

## 19. Critical UI states

Relevant P0 screens design/test:

```text
EMPTY
LOADING
READY
QUEUED
RUNNING
PAUSED
STOPPED
ABORTED
CANCELLED / SUPERSEDED
CRASHED
LIVE HISTORICAL INSPECTION
PASS
FAIL
INCOMPLETE
NOT_ESTABLISHED
BLOCKED
SEALED HISTORICAL
DRAFT
CANDIDATE
PUBLISHED
INVALIDATED
REVALIDATION_REQUIRED
STALE / IMPACTED
NOT_AVAILABLE
NOT_CAPTURED
MISSING
NOT_EVALUABLE
ROLE_NOT_APPLICABLE
```

## 20. P0 screen inventory

### Global

- Application Shell.
- Object Navigator.
- Attention Center.
- Engineering Workspace / Settings.
- SourceWorkspace list/detail/register.
- SourceSnapshot inspection/history.
- Execution Environment Profile list/detail/qualification state.
- Appearance.

### Workbench

- Workbench Home / Resume.
- Investigation Run.
- Investigation Analyze.
- Investigation Compare.
- Finding editor/detail.
- Debug Handoff preview/export.
- Agent Result import/review.
- Run Preflight.

### Cases / Requirements

- Requirement-centered Case Library.
- Requirement Catalog / Detail / Versions.
- Evaluation Profile Catalog / Detail / Qualification.
- Coverage Contract / Coverage Matrix detail.
- Golden Evidence Fixture inspection.
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
- ExecutionGroup / Gate run detail.
- Gate Attestation detail.
- Protected Baseline Set detail.
- Baseline Transition.
- Suite detail/version history.
- Suite Change Proposal.
- Merge Waiver / Remediation.

## 21. Accessibility and interaction quality

- Visible keyboard focus in Dark/Light.
- Icon-only App Rail has accessible labels/tooltips.
- State never color-only.
- Tables/matrices provide text equivalents.
- High-impact actions expose scope/consequence before mutation.
- Timeline/chart selection preserves clear focus/selection.
- Historical/live/candidate/source-snapshot/implementation-artifact modes use persistent labels.

## 22. UI acceptance criteria

UI accepted only when:

1. Golden Workflow completes via official product paths except external code edit.
2. Live/Replay/Analyze/Compare preserve source/time/context semantics.
3. Record Lifecycle, Execution Status, Evaluation Verdict and Evidence Trust are not conflated.
4. Requirement/Evaluation/Coverage assets have inspectable P0 routes under Cases without adding a sixth Workface.
5. SourceWorkspace/Environment objects have inspectable P0 routes without silent context switching.
6. G0–G4 display is exact-scope/role-aware and CORE PASS is not represented as G4.
7. Reconstructed evaluator provenance and numerical-not-confirmed boundary are visible where relevant.
8. OpenBridge Conformance Matrix and exact dependency/license/NOTICE provenance review are complete.
9. No undocumented OpenBridge internal styling hacks exist.
10. Dark 1440×900 and 1920×1080 P0 layouts pass review; compact desktop preserves critical state.
11. Custom Exceptions are documented/minimized.
12. Maritime Operational Alerts and Engineering Attention/Gates use distinct semantics.
13. Inspection cannot silently mutate execution context.
