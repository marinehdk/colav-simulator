# Colav-Simulator V1 Product Requirements Document

> **Status:** V1 scope frozen; design-baseline review corrections applied  
> **PRD baseline:** D-001 through D-144  
> **Product boundary:** Engineering V&V-grade, safety-assurance-ready; **not** a certification/type-approval claim  
> **Primary delivery:** Local-first COLAV Engineering & V&V Workbench  
> **V1 focus:** Development + Core Regression  
> **Companion review:** `Design/Colav-Simulator-V1-PRD-Review.md`  
> **Last updated:** 2026-08-19

## 1. Purpose and normative precedence

This document is the product and engineering requirements source of truth for the V1 full-stack redesign of `colav-simulator`.

It converts workshop decisions D-001 through D-144 into an implementable specification. Companion documents are:

- `Design/Colav-Simulator-V1-UI-Spec.md` — OpenBridge UI, screen and interaction specification.
- `Design/Colav-Simulator-V1-Implementation-Plan.md` — implementation milestones, migration order and acceptance sequence.
- `Design/Colav-Simulator-V1-PRD-Review.md` — repository-alignment and implementation-readiness review record.

Existing architecture/evidence documents under `Design/` remain repository evidence and technical background. Where an older Web/session/application model conflicts with this PRD, this PRD governs the V1 Web/Application redesign. Existing simulation/COLAV computational behavior must first be characterized against an exact source ref before it is treated as a preservation baseline.

This PRD aligns with `MISSION.md`: understand and verify the chain from scenario through perception, planning, control, dynamics, evaluation and Web; safely optimize/add COLAV algorithms; and distinguish safety, COLREG behavior quality, research reproduction and engineering performance.

Repository planning terminology from `CONTEXT.md` is normative where applicable: **Mission Route, Avoidance Corridor, Horizon Encounter Plan, Hard Row Window, Rolling Plan, Plan Revision**. Generic UI language shall not redefine or conflate those terms.

## 2. Executive summary

Colav-Simulator V1 shall become a unified, reproducible engineering workbench for developing, debugging and regression-validating collision-avoidance algorithms.

The V1 Golden Workflow is:

```text
Algorithm/code change
    ↓
Development Run
    ↓
Failure
    ↓
Investigation
    ↓
Exact Reproduction
    ↓
Analyze / Failure Window
    ↓
Debug Handoff to Codex/ZCode
    ↓
Candidate Source
    ↓
Re-run
    ↓
Before/After Compare
    ↓
FIX_VERIFIED
    ↓
Regression Case
    ↓
CORE Regression
    ↓
Fast Merge Gate
    ↓
Investigation CLOSED
```

V1 is not a MASS deployment product and does not claim algorithm certification. It shall produce traceable engineering evidence and domain objects that can later support Formal Validation, release eligibility and MASS handoff.

## 3. Problem statement

The current project can execute representative COLAV scenarios, but it does not yet provide one coherent engineering V&V system that answers all of the following reliably:

1. How is a real algorithm failure reproduced exactly?
2. Where in the scenario/perception/planner/control/evaluation chain did abnormal behavior first appear?
3. Which scenario families and boundary conditions are sufficient to test a particular requirement?
4. What does a single successful run prove, and what does it not prove?
5. How are algorithms compared without changing several experimental conditions at once?
6. How is a verified algorithm configuration identified so it cannot drift before downstream use?
7. How are historical defects converted into permanent regression protection?
8. How is a GitHub merge gate tied to exact source, ADP, cases, profiles, environment and evidence?

Highest-priority risks are algorithm defect escape, false safety confidence, regression escape and poor algorithm selection/comparison caused by fragmented/non-unified evidence.

## 4. Primary users and jobs to be done

### 4.1 Primary personas

V1 treats these as equally primary roles, even when one engineer performs both:

- **Algorithm/COLAV/MPC Developer / Research Engineer** — fast reproduction, diagnosis, controlled experimentation and source-level handoff.
- **Algorithm V&V / Test Engineer** — qualified cases, reproducibility, regression suites, evidence, pass/fail semantics and traceability.

V1 does not require separate people to author/review/approve assets, but data models shall retain provenance fields such as `created_by`, `executed_by`, `reviewed_by`, `approved_by` for future team workflows.

### 4.2 Highest-frequency V1 jobs

1. Reproduce and diagnose a known algorithm issue.
2. Quickly validate behavior after algorithm/source/configuration change.
3. Convert a fixed defect into a stable regression asset.
4. Run protected CORE regression locally and in GitHub CI.
5. Understand why a gate is PASS, FAIL or INCOMPLETE and inspect underlying evidence.

## 5. Product principles

### P-001 — Evidence before presentation

The Web UI shall not maintain a second simulation truth. Live UI, Replay, Analyze and Compare are projections of the same versioned Observation/Event/Evidence model.

### P-002 — Immutable historical facts

Published test definitions, SEALED Run evidence, Original Evaluation verdicts and Gate Attestations shall not be overwritten. Later interpretation/trust state is stored as derived/versioned records.

### P-003 — Published is not validated

```text
Discoverable ≠ Runtime Ready ≠ Published ≠ Validated ≠ Release Eligible
```

### P-004 — Inspection is not intervention

Select, pin, scrub, replay, filter and layer visibility shall never silently alter Simulator or Planner state. State-changing test intervention must be explicit, versioned into Run Override/Revision and preserved as evidence.

### P-005 — Reproducibility first

Every real execution receives a Run ID and freezes result-critical identity sufficient to interpret and reproduce that execution according to its Reproducibility Contract.

### P-006 — Hard gates are not averaged away

Mandatory Safety/COLREG failures cannot be offset by efficiency, smoothness or aggregate scores.

### P-007 — OpenBridge-native first

The V1 Web shall remain as visually and behaviorally consistent with OpenBridge as practical and reuse documented OpenBridge Web Components/tokens before custom primitives.

### P-008 — Historical result is not current eligibility

Original Verdict, current Evidence Trust/Impact, and claim-specific Evidence Eligibility are distinct semantics.

## 6. V1 scope

### 6.1 V1 P0 product scope

V1 shall fully implement:

- Global OpenBridge application shell.
- Workbench: Run, Analyze, Compare.
- Persistent Investigations/lifecycle.
- Case/Test Engineering system.
- Immutable Runs and SEALED Evidence.
- SourceWorkspace/SourceSnapshot identity.
- Algorithm Definition, immutable Implementation Artifact and ADP model.
- Algorithm integration workspace/runtime verification.
- Engineering Requirement/Evaluation foundation.
- Versioned Evidence Capture Profiles.
- Core Regression and Fast Merge Gate.
- Portable Evidence Bundle export/import.
- GitHub required regression gate integration.

### 6.2 V1 top-level information architecture

Exactly five primary workfaces:

```text
Workbench
Cases
Runs
Algorithms
Regression
```

Formal `Validation` and `Releases / MASS Handoff` are intentionally not top-level V1 workfaces.

### 6.3 V2+ / out of V1 product scope

Reserved by the domain model but not fully implemented in V1:

- Formal Validation Campaign workface.
- Full Release Gate and validated algorithm release workflow.
- MASS handoff package/workflow.
- Large Monte Carlo/DOE/parameter-sweep campaigns.
- Automated EXTENDED regression scheduling.
- Dedicated strict deployment-performance qualification product workflow.
- HIL/SIT/sea-trial integration.
- Rich reactive intelligent traffic-agent library beyond V1 deterministic needs.
- Central multi-user server, organizations, RBAC and mandatory multi-person approval.
- Distributed remote worker scheduling.
- Fully automated Codex/ZCode agent loop.

## 7. Assurance level and lifecycle

V1 targets **Engineering V&V-grade, safety-assurance-ready, not certification/type approval**.

Lifecycle language:

```text
Develop
→ Debug/Diagnose
→ Core Scenario PASS
→ Fast Merge Gate
→ main
→ Full Validation (future)
→ Validated ADP (future)
→ Release Eligible (future)
→ Validated Algorithm Release (future)
→ MASS Handoff (future)
```

`Merged ≠ Validated ≠ Release Eligible` is a hard semantic invariant.

## 8. Domain model

### 8.1 Investigation

Persistent first-class object representing the engineering problem being solved and why multiple Runs belong together.

Lifecycle:

```text
OPEN
→ REPRODUCING
→ DIAGNOSING
→ FIX_IN_PROGRESS
→ VERIFYING
→ REGRESSION_PENDING
→ CLOSED
```

`BLOCKED` is available where appropriate.

`CLOSED` requires:

- failure reproduced;
- fix verified;
- Regression Case created;
- required CORE suite passed.

Optional external GitHub issue references may be stored; hard issue binding is not required.

### 8.2 Engineering Requirement

Versioned first-class object, not a string tag.

Minimum fields:

- stable ID/version;
- title/category;
- normative/source reference;
- engineering interpretation;
- applicability contract;
- expected behavior;
- evaluator bindings;
- required evidence;
- intrinsic criticality;
- lifecycle/supersession.

External COLREG/legal/normative source references shall be distinguished from platform engineering interpretation, evaluator implementation and threshold policy.

### 8.3 Scenario Family / Case Template

Versioned authoring template defining parameter schemas/ranges, geometric constraints, default Requirements/Expected Behavior and qualification expectations.

Template updates shall never silently modify instantiated Concrete Cases.

### 8.4 Concrete Test Case

Executable test specification containing:

- intent;
- Requirement references;
- preconditions;
- scenario definition;
- traffic-actor behaviors;
- Condition Contract;
- Encounter Intent Graph where applicable;
- Test Phase Contract;
- declarative Expected Behavior;
- Evaluation Profile binding/default;
- Qualification evidence;
- exact executable snapshot/digest.

Published Case Versions are immutable.

Lifecycle governance:

```text
ACTIVE
DEPRECATED
RETIRED
INVALIDATED
```

Invalidation does not delete historical references; it triggers impact analysis on dependent Evidence/Claims.

### 8.5 Regression Case

A historical defect produces two related assets:

1. **Exact Failure Reproduction** — preserves original Case/RunSpec/seed/ADP/evidence.
2. **Curated Regression Case** — minimal stable trigger, affected Requirement, root-cause/finding lineage and Expected Behavior.

Regression tiers:

```text
CORE
EXTENDED
ON_DEMAND
```

V1 fully implements CORE; other tiers are reserved.

### 8.6 SourceWorkspace

Registered Git repository/worktree context used for development inspection and source freezing.

Minimum identity:

- repository identity;
- worktree path registered through backend configuration/service, not arbitrary browser path input;
- branch/HEAD/base commit;
- clean/dirty state;
- changed/relevant untracked files;
- workspace digest/provenance.

A SourceWorkspace is mutable working state and is **not** formal implementation evidence.

### 8.7 SourceSnapshot / EphemeralSourceSnapshot

Immutable frozen source identity created before a Development/Reproduction/diagnostic execution from a SourceWorkspace.

A dirty snapshot shall record, at minimum:

```text
base commit
tracked patch/diff identity
included relevant untracked source files
source-tree digest
dependency identity/reference
```

Subsequent worktree edits shall not change historical Run source identity.

### 8.8 Algorithm Definition

Stable algorithm-family identity containing:

- algorithm ID/name/role;
- entrypoint/runtime contract;
- parameter schema;
- input/output contract;
- runtime requirements;
- declared capabilities;
- diagnostic capabilities.

Declared Capability is not Verified Capability.

### 8.9 Implementation Artifact

**Immutable formal implementation identity only.** It shall not represent mutable dirty worktree state.

Minimum identity:

- clean Git revision and/or sealed build identity;
- source/build digest;
- dependency lock/runtime identity;
- manifest identity;
- runtime/contract verification evidence.

Published ADPs, CORE protected baselines and future Formal/Release flows shall bind immutable Implementation Artifacts. Development/Candidate execution may bind an EphemeralSourceSnapshot until promotion.

### 8.10 Algorithm Deployment Profile (ADP)

Formal algorithm validation object. It includes:

- Algorithm Definition;
- immutable Implementation Artifact for Published ADP;
- exact parameters;
- prediction-model configuration;
- solver/runtime configuration;
- ship capability profile;
- timing/update assumptions;
- I/O contract/profile digest.

Tracker, Scenario/Case, Seed and similar values are validation conditions, not part of Algorithm Definition.

Published ADPs are immutable. Editing occurs through Candidate Revisions and Workbench Experiment Overrides. Candidate/Experiment execution may temporarily bind a SourceSnapshot, but promotion requires an immutable Implementation Artifact.

### 8.11 Condition Profile

Versioned execution-condition asset covering concrete environment/perception/tracker/noise/latency conditions. Case stores a Condition Contract; RunSpec binds exact profiles.

### 8.12 Scenario Qualification Policy and Qualification Record

`ScenarioQualificationPolicy` is a versioned algorithm-neutral execution policy defining the deterministic ownship/reference behavior, Traffic Actor execution, encounter/phase resolvers and termination rules used to qualify a Case.

A Case Qualification Record binds:

- exact Case draft/version/digest;
- Scenario Qualification Policy;
- qualification implementation/environment;
- qualification evidence;
- L1–L4 result.

Scenario Qualification Evidence cannot contribute Algorithm Capability or Regression PASS evidence.

### 8.13 Evidence Capture Profile

Versioned contract defining required/optional evidence channels, sampling/resolution and capture policy.

V1 system profiles include at least:

```text
DEVELOPMENT@1
DIAGNOSTIC@1
REGRESSION@1
FORMAL_VALIDATION@future
```

Every executable Run shall satisfy a mandatory **Core Evidence Floor** regardless of profile. At minimum:

- frozen RunSpec;
- SourceSnapshot or Implementation Artifact identity, and ADP identity when applicable;
- exact Case/qualification/condition identity when applicable;
- ownship truth/trajectory;
- target truth/tracks required by execution contract;
- Encounter/Risk events and key derived context;
- Planner core status, Selected/Accepted Planner Output, fallback/hold state/events;
- Evaluation inputs/results when Evaluation is requested;
- runtime/process errors and execution-control events;
- Execution Environment/version manifest;
- schema identities and artifact digests.

Profile-specific diagnostics may add solver iterations, prediction sets, constraints, tracker covariance, control internals and similar channels.

Missing diagnostic data shall use explicit cause semantics such as `NOT_AVAILABLE`, `NOT_CAPTURED` or `MISSING`; it shall never be fabricated.

### 8.14 Run and RunSpec

Run is an immutable execution record. Every real execution receives a Run ID.

#### Purpose-aware RunSpec

V1 Run purposes include at least:

```text
DEVELOPMENT
REPRODUCTION
FIX_VERIFICATION
CASE_QUALIFICATION
INTEGRATION_SMOKE
CORE_REGRESSION
```

Future `FORMAL_VALIDATION` is reserved.

Bindings are purpose-aware rather than universally requiring a Published ADP/Evaluation Profile:

- `DEVELOPMENT/REPRODUCTION/FIX_VERIFICATION` bind a Case/Case Snapshot, source identity, runtime conditions and ADP or candidate algorithm configuration as applicable.
- `CASE_QUALIFICATION` binds a Case and `ScenarioQualificationPolicy`; it does not establish algorithm capability.
- `INTEGRATION_SMOKE` may bind Algorithm Definition + candidate/Implementation identity before Published ADP exists.
- `CORE_REGRESSION` binds Published immutable ADP, Suite/Baseline/Profiles and Qualified Environment according to policy.

Run identity freezes, when applicable:

- purpose;
- Investigation/config revision;
- Case snapshot/version/digest;
- source identity as `SourceSnapshot | ImplementationArtifact`;
- ADP/config identity if applicable;
- Condition Profiles;
- random-stream identity;
- Evaluation Profile if evaluation is requested;
- Evidence Capture Profile;
- Execution Environment;
- Reproducibility Contract;
- RunSpec digest;
- Execution Policy.

#### Orthogonal Run state axes

Run state shall not collapse record lifecycle, execution status and evaluation result.

```text
Record lifecycle:
CREATED → RUNNING → FINALIZING → SEALED

Execution status:
QUEUED | RUNNING | FINISHED | STOPPED | ABORTED | CRASHED | CANCELLED

Evaluation result:
Completeness = COMPLETE | INCOMPLETE
Compliance = PASS | FAIL | NOT_ESTABLISHED
```

Semantics:

- `STOPPED`: user intentionally ends a Development Run early.
- `ABORTED`: an execution expected to complete (e.g. CORE/Gate) is interrupted.
- `CANCELLED`: execution is cancelled before meaningful execution starts or is superseded by orchestration policy/new candidate.
- `CRASHED`: abnormal worker/process termination.
- `SEALED` describes evidence-record finalization and may coexist with `CRASHED` + `NOT_ESTABLISHED` when partial evidence is finalized.

### 8.15 ExecutionGroup

Represents multiple Runs intentionally created by one batch action such as CORE regression or Case Qualification. Distinct from Investigation and Run lineage.

### 8.16 Evidence Manifest / Artifact

A terminal Run may enter `FINALIZING` and then `SEALED` only after required manifest/artifact references/digests are committed consistently.

Evidence state distinguishes:

```text
AVAILABLE
NOT_CAPTURED
NOT_AVAILABLE
MISSING
CORRUPT
SCHEMA_MISMATCH
```

SEALED evidence is immutable.

### 8.17 Evaluator Definition and Evaluator Implementation Artifact

Evaluator identity is two-layered:

```text
Evaluator Definition
→ immutable Evaluator Implementation Artifact
```

The artifact records exact source/build/digest/runtime/schema verification. Evaluation Profiles bind exact evaluator implementations.

### 8.18 Evaluation Profile

Versioned definition of how evidence is interpreted, binding exact:

- Requirement versions;
- Evaluator Implementation Artifacts;
- applicability policies;
- thresholds;
- enforcement;
- evidence requirements;
- aggregation policy.

Published Evaluation Profiles are immutable and must pass a Qualification Suite before publication.

### 8.19 Evaluation Record

Versioned interpretation of SEALED evidence.

- Original Evaluation is immutable and remains the Run's Original Verdict.
- Re-evaluations create new records and never overwrite the original.
- Re-evaluation requires sufficient source evidence.
- Missing evidence shall not default to PASS.

### 8.20 Coverage Contract

Versioned contract defining which validation dimensions/cells constitute coverage for a Requirement/capability scope. Coverage is derived from qualified Evidence and is independent from Compliance.

### 8.21 Comparison Contract and Fix Verification Record

`ComparisonContract` records Baseline/Candidate Runs, controlled conditions, intended changes, known variations, unexpected differences and Comparison Fidelity.

`FixVerificationRecord` binds target failure/Requirement, Baseline/Candidate, Comparison Contract and evidence. It may become `FIX_VERIFIED` only under requirements in GW-008.

### 8.22 Debug Handoff and Agent Result

Debug Handoff is a versioned immutable Agent-ready context snapshot with Markdown + JSON representations separating facts, confirmed findings, hypotheses/diagnostic leads, Agent task and change contract.

Agent Result records what coding Agent changed/reported. Agent-reported tests are development information, not formal Fix Verification evidence.

### 8.23 Regression Suite

Published immutable Suite Manifest referencing exact Case Versions, Evaluation Profiles, Execution Policy, Evidence Capture Profile and Reproducibility/Environment requirements.

Any modification creates a new Suite Version through Suite Change Proposal.

### 8.24 Protected Regression Baseline Set

Versioned set defining which mature ADP baselines `main` promises not to break.

- Core Suite: which tests are required for one validation object?
- Protected Baseline Set: which validation objects must every merge protect?

### 8.25 Regression Gate Attestation

Immutable proof object for one formal Fast Merge Gate execution, binding exact source, baseline set, suites, ADPs, profiles, environment, ExecutionGroups, evidence and original gate verdict.

Original gate verdict is immutable; current trust may later become `STALE`, `IMPACTED` or `REASSESSMENT_REQUIRED`.

### 8.26 Assurance-governance objects

P0 first-class governance records include:

- `SuiteChangeProposal`;
- `BaselineTransitionProposal`;
- `MergeWaiver`;
- `RemediationObligation`;
- persistent `AttentionItem` where applicable.

### 8.27 Execution Environment Profile

Versioned runtime identity/qualification contract including OS/architecture, Python/runtime, dependency lock, solver/native libraries, threading/resource/timing policy and optional container/build digest.

Environment qualification levels:

```text
UNQUALIFIED
COMPATIBLE
QUALIFIED
```

Fast Merge requires the applicable Qualified Reference Environment.

### 8.28 Reproducibility Contract

Versioned policy defining random streams, solver determinism, scheduling/threading policy, environment identity and event/metric tolerances.

Determinism classes:

```text
D0 UNCONTROLLED
D1 SEEDED
D2 REPRODUCIBLE
D3 GATE_STABLE
```

CORE/Fast Merge require D3 under the applicable Qualified Environment.

## 9. Capability maturity and algorithm-role semantics

### CAP-001 — Normative G0–G4 vocabulary

The V1 Capability Matrix uses the repository maturity vocabulary:

```text
G0 — Discoverable
     Algorithm/scenario/dependency can be resolved/discovered; no execution claim.

G1 — Short smoke test
     Adapter/runtime can construct and advance a short execution path.

G2 — Full closed loop
     Representative scenario completes through the real closed loop without unexpected fallback.

G3 — Capability demonstration
     Evidence demonstrates behavior consistent with the algorithm's declared role in representative conditions.

G4 — Benchmark validation
     Versioned benchmark/coverage/evaluation requirements are satisfied according to an explicit grade policy.
```

Grade is always scoped to:

```text
Exact ADP
× Capability cell / Requirement scope
× Validation conditions/envelope
× Evidence basis
```

It is never a manually editable global Algorithm property.

CORE PASS does **not** automatically imply G4. V1 platform acceptance does not require any algorithm to reach G4.

### CAP-002 — Role-aware capability comparison

Algorithm role constrains meaningful capability dimensions/comparison. Dynamic COLAV, static ENC/global planning, tracking, nominal guidance and other roles shall not be treated as interchangeable.

UI/Evaluation shall distinguish:

```text
ROLE_NOT_APPLICABLE
DECLARED_NOT_VERIFIED
TECHNICALLY_INCOMPATIBLE
VERIFIED / grade
```

Cross-algorithm comparison shall establish compatible role/scope before presenting comparative claims.

## 10. Golden workflow requirements

### GW-001 — Failure creation

User shall create Development Run from Published Case, Draft Case or Ephemeral Case Variant with frozen source/execution identity.

### GW-002 — Failure-to-Investigation

Failed/Incomplete Run supports `Investigate`, linking/creating Investigation without re-entering configuration.

### GW-003 — Exact reproduction

`Reproduce` clones frozen experiment definition, runs Preflight and creates new Run. Reproduction Fidelity:

```text
EXACT
CONTROLLED_VARIATION
DERIVED
NOT_REPRODUCIBLE
```

### GW-004 — Analyze

Analyze synchronizes Chart, Encounter, Planner/Diagnostics, Evidence and typed multi-lane event timeline at one Inspection Cursor.

### GW-005 — Debug handoff

Generate versioned Debug Handoff package with exact reproduce instructions, RunSpec, source/ADP identity, failure window, evidence refs, diagnostics, findings/hypotheses and Agent Change Contract.

### GW-006 — Agent result reintegration

Accept structured Agent Result/candidate source identity, verify Change Contract, freeze source snapshot and allow platform re-verification.

### GW-007 — Compare

Before/After verification compares two immutable Runs using Comparison Contract. Fidelity:

```text
CONTROLLED
CONTROLLED_WITH_KNOWN_VARIATIONS
COMPROMISED
NON_COMPARABLE
```

### GW-008 — Fix Verification

`FIX_VERIFIED` requires:

- Baseline contains target failure under applicable conditions;
- Candidate re-activates same target Requirement/intent;
- target failure changes FAIL → PASS;
- Candidate Evaluation is COMPLETE;
- no new mandatory failure;
- Comparison Fidelity meets policy.

States:

```text
NOT_STARTED
CANDIDATE
FIX_INDICATED
FIX_VERIFIED
FIX_REJECTED
```

### GW-009 — Regression promotion

Confirmed/fixed defect supports promotion/curation to Regression Case with lineage.

### GW-010 — Closure

Investigation cannot close before Regression Case exists and required CORE regression passes.

## 11. Workbench requirements

### WB-001 — Resume-first home

Prioritize active Investigation resume, recommended next action, recent failures/investigations, quick reproduction and current Core Regression status.

### WB-002 — Investigation entry paths

Enter/create from Failed Run, existing Case, Algorithm/ADP or Scratch. Failed-run entry inherits reproducible context and opens analysis at relevant failure timestamp when available.

### WB-003 — Workbench modes

Exactly:

```text
Run | Analyze | Compare
```

Lifecycle-aware resume recommends a mode; last Inspection/Presentation state is separate.

### WB-004 — Baseline + Overrides

Configuration = Investigation Baseline + versioned Run Overrides + Preflight. Overrides create revisions; no silent baseline mutation.

### WB-005 — Run layout

Chart-first with optional Situation Rail, Context Rail and bottom Simulation Timeline/controls.

### WB-006 — Encounter-first context

```text
Encounter
→ COLREG/responsibility
→ Risk/CPA/TCPA
→ Target evidence
→ Planner response
→ Events
```

### WB-007 — Three encounter contexts

Always distinguish Algorithm Context, System Risk Context and Inspection Context. Divergence is visible/diagnostic; selection never alters Planner focus.

### WB-008 — Execution vs inspection clock

Maintain Execution Clock and Inspection Cursor. Scrubbing backward shall not pause Simulator. Historical inspection during Live Run shows distance behind Live Edge and `Return to Live`.

### WB-009 — Execution controls

Development/diagnostic workflows may allow Pause, Resume, deterministic Step, Simulation Execution Rate and Stop; every control is a typed Run Event.

CORE/Fast Merge is `AUTOMATED_LOCKED`; manual Pause/Step/Rate Change prohibited. Abort yields INCOMPLETE. Replay Speed is Presentation State and is not Simulation Execution Rate.

### WB-010 — Trajectory semantic layers and repository planning language

Chart distinguishes:

1. Historical Fact;
2. Mission/Reference;
3. Selected/Accepted Planner Output;
4. Prediction;
5. Candidate/Rejected Plans.

`Selected/Accepted Planner Output` is generic visualization language, **not** a replacement domain term for `Mission Route`, `Avoidance Corridor`, `Horizon Encounter Plan`, `Rolling Plan` or `Plan Revision`.

When diagnostics expose those repository planning concepts, UI shall use their canonical names and keep:

- Mission Route authoritative voyage intent before/after encounter;
- Avoidance Corridor temporary passing-side commitment;
- Horizon Encounter Plan distinct from current encounter state/current solver candidate;
- Rolling Plan distinct from warm start/current solver candidate;
- Plan Revision explicitly justified/traceable where provided.

Predictions require source, generated time, horizon and validity/age. Candidate/rejected plans are progressively disclosed.

### WB-011 — Analyze timeline

Typed multi-lane timeline with at least Encounter, Risk, Perception, Planner, Constraints, Control, Evaluator, Runtime and Annotation. Events support POINT, INTERVAL, TRANSITION and distinguish observed, derived, evaluation finding, diagnostic lead and user annotation.

### WB-012 — Failure localization

Build factual Failure Window from evaluator/runtime/planner/constraint/fallback/risk events and mark first abnormal transition/key transitions. System shall not auto-declare root cause. Root cause/finding is engineer-confirmed with evidence/alternatives/affected Requirement/proposed fix.

### WB-013 — Compare alignment

Compare supports Absolute Simulation Time and evidence-based Semantic Event Alignment simultaneously; semantic alignment never hides real timing differences.

### WB-014 — Agent Change Contract

Every Debug Handoff defines allowed change domains, protected validation assets, prohibited success strategies and required verification.

## 12. Cases requirements

### CASE-001 — Requirement-centered library and hub

Cases are organized primarily around validation Requirements, with Scenario Family/Encounter/Purpose/Environment/Lifecycle as strong facets.

`Cases > Requirements` is also the V1 **Requirement & Evaluation Hub** for local routes to Requirement Catalog/Detail/Version, Evaluation Profile Detail/Qualification, Coverage Contract/Matrix and Golden Evidence Fixtures. This does not add a sixth top-level workface.

### CASE-002 — Designer layout

Chart-centered executable test designer with Test Specification rail, Chart/ENC center, Qualification rail and Parameters/Expected Behavior/Events/Advanced/Diff areas. Chart and structured parameters are synchronized views of one Case model.

### CASE-003 — Declarative expected behavior

Case stores behavior semantics/Requirement bindings. Common measurement logic/thresholds belong to versioned Evaluation Profiles. Case-specific numeric assertions are explicit `LOCAL_ASSERTION` with rationale.

### CASE-004 — Template instantiation

Concrete Case stores exact template-version lineage/snapshot. New Template versions offered through Compare/Rebase into a new Draft; no live inheritance.

### CASE-005 — Draft execution

Draft Cases/Ephemeral Variants may run for Development with frozen exact snapshots and Development-only formal eligibility. Only Published + Qualified Cases may enter formal Regression/Gate evidence; CORE additionally requires Stability Qualification.

### CASE-006 — Encounter-centric authoring

Primary authoring language is encounter geometry, supporting relative bearing, course relationship, speed, initial range, desired CPA/TCPA envelope, risk window and tolerances.

Versioned deterministic Geometry Compiler produces exact executable initial state. Published Case freezes Authoring Specification + Compiler Identity + Compiled Exact State + Digest. Explicit Exact State mode supports historical reproduction.

### CASE-007 — Traffic Actor Behavior Contract

Targets are versioned Traffic Actors with initial state, nominal behavior, scripted/condition-triggered maneuvers and reserved reactive-policy extension. V1 CORE defaults to deterministic traffic behavior.

### CASE-008 — Condition Contract

Case declares required/allowed/prohibited conditions. Exact Environment/Perception/Tracker/Noise/Latency values supplied through versioned Condition Profiles bound in RunSpec.

### CASE-009 — Multi-ship Encounter Intent

Multi-ship uses Encounter Intent Graph roles `REQUIRED | ALLOWED | BACKGROUND | PROHIBITED`. Qualification compares Intent Graph to Derived Encounter Graph. Case shall not predefine Planner focus unless focus itself is under test.

### CASE-010 — Test phases

Event-relative Test Phase Contracts cover Setup, Encounter Formation, Applicability, Response, Passing, Encounter Clear, Recovery. Each Run resolves actual windows from evidence. Absolute time windows are explicit special cases with rationale.

### CASE-011 — Qualification

Before publication, Case must pass L1 Definition, L2 physical/geometric, L3 test-intent, L4 executability and algorithm-neutral Scenario Qualification Preview under an exact `ScenarioQualificationPolicy` identity.

Qualification Preview cannot contribute algorithm validation/regression evidence.

### CASE-012 — Invalidation impact

Published Case content immutable. DEPRECATED/RETIRED/INVALIDATED do not delete historical Runs. INVALIDATED triggers evidence/coverage/capability/regression impact analysis.

## 13. Runs and Evidence requirements

### RUN-001 — Run Explorer

Unified views: Recent, Failures, Investigations, Reproductions, Core Regression, Crashed/Incomplete, User Saved Views.

### RUN-002 — Dense evidence-aware table

Default dense table includes Run ID, Purpose, Investigation, Case, Algorithm/ADP, Source Identity, Execution Status, Original Verdict, Evidence State, Failure Domain, Created At.

### RUN-003 — Explicit query state

Filters/search/sort/grouping/columns are Inspection/Presentation Query State serialized to restorable Deep Links. Active filters always visible. Saved Views explicit and separate from system presets.

### RUN-004 — Grouping

Run Catalog remains flat; every Run independently addressable. Optional UI grouping by Investigation, ExecutionGroup, Algorithm/ADP, Case or Source.

### RUN-005 — Immutable Run Detail

Run Detail is immutable historical record + read-only inspection. Full debug mutations occur in Workbench. Tabs at minimum:

```text
Overview | Replay | Evaluations | Evidence | Lineage
```

### RUN-006 — Verdict-aware landing

Landing differs for PASS, behavioral FAIL, INCOMPLETE/CRASHED and missing-evidence outcomes while tabs remain stable.

### RUN-007 — Historical replay

Replay shares Observation Surface with Live but visibly `SEALED · HISTORICAL`; controls read evidence and never invoke Simulator.

### RUN-008 — Original verdict

Original Verdict immutable. Re-evaluations are separate Evaluation Records and never replace Explorer/Overview Original Verdict.

### RUN-009 — Evidence Explorer

Manifest-centric grouping: Experiment Identity, Navigation/Truth, Perception, Encounter/Risk, Planner, Control/Dynamics, Evaluation, Runtime and typed diagnostics. Evidence and Replay share Inspection Cursor.

### RUN-010 — Portable Evidence Bundle

Export/import self-describing Bundle containing manifest, frozen RunSpec/provenance, artifacts, evaluations, derived artifacts/summaries and checksums. Import verifies integrity before registration; original digests/verdicts unchanged.

### RUN-011 — Evidence trust and claim eligibility

Three distinct semantics:

```text
Historical Original Verdict
Current Evidence Trust/Impact
Claim-specific Evidence Eligibility
```

Top-level Trust may summarize `CURRENT | IMPACTED | STALE`; `NOT_ELIGIBLE` is preferably displayed as claim eligibility rather than rewriting Trust. Eligibility may differ for debug, regression, capability and future formal claims.

### RUN-012 — Run summary

Identity/Outcome + stable algorithm-agnostic Core Summary + Evaluation Profile results + typed diagnostic extensions. Every displayed metric exposes evidence/evaluator/window provenance.

### RUN-013 — Lineage

Concise Semantic Engineering Lineage Path + expandable local Provenance Graph with controlled relation semantics.

### RUN-014 — Cancellation/supersession

CI/workflow supersession of an older candidate is distinct from Gate Early behavior. A superseded candidate may become `CANCELLED`/superseded according to orchestration policy; already SEALED evidence remains preserved. A deterministic failure within an active mandatory Suite does not permit stopping remaining CORE members.

## 14. Algorithms and ADP requirements

### ALG-001 — Algorithm catalog

Organized by Algorithm Definition; independently exposes Runtime Readiness, Validation Readiness, Algorithm Role and Evidence-Derived Capability summary. `AVAILABLE` never implies `VERIFIED`.

### ALG-002 — Algorithm scope

Generic navigation opens Algorithm Overview. Formal ADP scope only via explicit selection/exact Deep Link. Cross-ADP summary does not create mixed global grade.

### ALG-003 — Algorithm identity

Formal identity:

```text
Algorithm Definition
→ immutable Implementation Artifact
→ ADP
```

Mutable development source is modeled separately as SourceWorkspace/SourceSnapshot.

### ALG-004 — Dirty source

Development Runs may execute frozen EphemeralSourceSnapshot. Published ADP/CORE baseline requires immutable Implementation Artifact.

### ALG-005 — ADP candidates

Published ADP read-only. Changes create Candidate Revision; temporary Workbench changes use Experiment Overrides. Promotion requires immutable Implementation Artifact and creates new immutable ADP version. Promotion does not grant validation.

### ALG-006 — Capability matrix

Evidence-Derived Capability Matrix scoped to exact ADP + role-compatible capability + validation conditions. Cell shows derived grade/evidence state; detail exposes role, declared support, technical compatibility, scope, coverage, compliance and lineage.

### ALG-007 — Capability invalidation

Validation Impact Analysis handles changes. Evidence may be reusable, revalidation-required, stale or not verified; new versions never silently inherit verified claims.

### ALG-008 — Compatibility

Preflight distinguishes Technical Compatibility, Evaluation/Evidence Compatibility and Validation Coverage. Technical incompatibility may block. Unverified coverage does not block Development but limits claims.

### ALG-009 — Core diagnostics/extensions

All algorithms provide algorithm-independent core diagnostics: identity, solve/execution status, plan status, Selected/Accepted Planner Output, fallback/hold, computation time, availability. Typed extension channels may include prediction, optimization, constraints, collision geometry, candidate selection, tree search, policy, observation/action, uncertainty. Missing = `NOT_AVAILABLE`.

### ALG-010 — Integration workspace

```text
Manifest
→ Contract Verification
→ Runtime Verification
→ Smoke Execution
→ Diagnostics Verification
→ Implementation Artifact
→ ADP
```

Technical integration success grants `RUNTIME_READY`, not verified COLAV capability. Integration Smoke may precede Published ADP.

### ALG-011 — Source workspace registry

V1 maintains registered Git/worktree SourceWorkspace objects and freezes SourceSnapshot before Development execution.

### ALG-012 — Runtime adapter

`AlgorithmRuntimeAdapter` with V1 primary `InWorkerPythonRuntime`; reserved ExternalProcess, Container, Remote and future MASS/HIL adapters.

### ALG-013 — Role-aware comparison

Algorithm Catalog/Capability/Compare shall not compare incompatible roles as if they implement the same dynamic COLAV responsibility. Role applicability is explicit before comparative claims.

## 15. Evaluation and Requirement requirements

### EVA-001 — Requirement applicability

```text
Applicability:
APPLICABLE | NOT_APPLICABLE | INDETERMINATE

Compliance:
PASS | FAIL | INCOMPLETE | NOT_EVALUATED
```

`NOT_APPLICABLE` never counts as PASS/coverage.

### EVA-002 — Intrinsic criticality vs enforcement

Requirement intrinsic criticality:

```text
SAFETY_CRITICAL
MISSION_CRITICAL
BEHAVIORAL
QUALITY
```

Profile enforcement:

```text
HARD_GATE
REQUIRED
ADVISORY
OBSERVATIONAL
```

Safety-critical Requirements cannot be silently downgraded. Explicit Waiver may permit research execution but cannot grant capability evidence.

### EVA-003 — Evaluation aggregation

Two axes:

```text
Completeness: COMPLETE | INCOMPLETE
Compliance: PASS | FAIL | NOT_ESTABLISHED
```

Domain verdicts retained for Safety, COLREG, Navigation, Recovery, Performance, Runtime/extensions. Known mandatory failure remains FAIL even if other evidence incomplete.

### EVA-004 — Evaluator identity

```text
Evaluator Definition
→ Evaluator Implementation Artifact
→ Evaluation Profile binding
```

Published Profile freezes exact implementation identity.

### EVA-005 — Profile qualification

Qualification Suite contains static validation, evaluator verification/unit/contract tests, Golden Evidence Fixtures and previous-profile Verdict Diff with explained intended changes. Unexplained drift blocks publication.

### EVA-006 — Coverage

Versioned Coverage Contract + Evidence-Derived Coverage Matrix. Coverage and Compliance independent; qualified complete FAIL may prove condition is covered.

Coverage states include:

```text
NOT_COVERED
PARTIAL
COVERED
STALE
INSUFFICIENT_EVIDENCE
```

### EVA-007 — No silent pass

`NOT_APPLICABLE`, `INDETERMINATE`, Waiver, unqualified Draft, missing required evidence, invalidated Case/Profile shall not create formal PASS/coverage.

### EVA-008 — Reconstructed Evaluator provenance boundary

The repository's current Evaluator is a reconstructed/public-interface implementation, not the official paper numerical Evaluator. V1 shall register it with explicit Evaluator Definition/Implementation provenance and preserve the repository boundary:

```text
functional_reproduction = true
numerical_reproduction_confirmed = false
```

until a separately sourced, licensed/authorized, qualified and numerically calibrated implementation is available.

No V1 UI, Capability Grade, Regression Gate or Acceptance language may imply that use of the reconstructed Evaluator establishes:

- paper numerical reproduction;
- official evaluator equivalence;
- certification evidence;
- type-approval evidence.

If/when a different evaluator implementation is introduced, it must receive its own immutable implementation identity and Profile Qualification; historical evaluations remain unchanged.

## 16. Regression requirements

### REG-001 — Versioned CORE Suite

Published Immutable Manifest references exact Case Versions, Evaluation Profiles, Evidence Capture Profile, Execution Policy, Environment/Reproducibility requirements.

### REG-002 — Completeness before verdict

Top-level Suite result:

```text
PASS
FAIL
INCOMPLETE
```

Infrastructure/worker failure is not mislabeled as algorithm behavioral FAIL.

### REG-003 — All CORE cases mandatory

V1 CORE uses no percentage tolerance: when execution complete, all required CORE Cases/hard gates must pass.

### REG-004 — Stability qualification

Every CORE member must have current Stability Qualification under applicable Reproducibility/Environment policy. Non-deterministic `PASS → FAIL → PASS` becomes `TEST_STABILITY / INCOMPLETE`, enters Quarantine/Investigation and cannot be retried into green.

### REG-005 — Isolated parallel execution

CORE executes isolated worker units with versioned timeout/parallelism/resource/environment policy. One crash shall not destroy other Run evidence.

### REG-006 — Full CORE every merge

Fast Merge runs full current CORE Suite for every Protected Baseline. Impact Analysis may add tests, never subtract.

### REG-007 — Gate early, execute to completion

First deterministic failure may mark Gate failed immediately; mandatory CORE Runs continue to obtain complete regression picture. This is distinct from orchestration cancellation of an obsolete/superseded candidate.

### REG-008 — GitHub required checks

Stable required check contract includes, at minimum:

```text
quality/lint
quality/unit-tests
colav/core-regression
```

Implementation may map existing workflow jobs to these stable check names during migration.

### REG-009 — Protected baselines

Fast Merge binds Published `ProtectedRegressionBaselineSet`; all Baselines mandatory. Adding/removing/replacing ADPs publishes new version.

### REG-010 — Baseline transition

Replacement uses `BaselineTransitionProposal` with old baseline still protected while successor completes CORE/impact/required revalidation.

```text
DRAFT → QUALIFYING → READY_TO_SWITCH → APPLIED
```

with BLOCKED/REJECTED.

### REG-011 — Gate Attestation

Every formal Fast Merge creates immutable Regression Gate Attestation. New source identity means prior Attestation is not a valid Gate for the new candidate.

### REG-012 — Merge Waiver

Waiver may exceptionally change Merge Eligibility but never change FAIL/INCOMPLETE to PASS. Result `MERGED_WITH_EXCEPTION`, creates Remediation Obligation and cannot contribute verified capability/release evidence.

### REG-013 — Suite Change Proposal

Any CORE add/replace/remove uses Suite Change Proposal and computes Requirement/historical-defect/protection diff. Removing current failure blocker is `ACTIVE_FAILURE_PROTECTION_REMOVAL` and cannot silently restore green.

### REG-014 — Gate control center

Regression home is Gate-centered Assurance Control Center with current candidate/baseline/suite, Gate decision, blockers, Suite Health, lightweight coverage, recent gates, transitions, waivers/remediation and suite management.

## 17. Global UX requirements

### UX-001 — Scoped context

Global Shell maintains Application Scope such as registered Repository/Worktree, Source and Runtime Environment. Case/ADP/Profile/Tracker/Seed are explicit Task Context and cannot silently inherit across workfaces.

### UX-002 — Context Ribbon

Always expose current workflow/scope such as Investigation, SEALED historical Run or Fast Merge Gate.

### UX-003 — Object Navigator

Global Object Navigator/Command Palette with stable Object IDs, Canonical Deep Links, recent history and object-specific actions. Opening object changes Inspection Context only unless explicit action changes execution context.

### UX-004 — Attention model

Separate Run Operational Events, Immediate UI Alerts and Persistent Engineering Attention. `ACKNOWLEDGED ≠ RESOLVED`.

### UX-005 — Risk-tiered actions

Exactly **five** impact tiers:

- Tier 0 Inspection — immediate/read-only;
- Tier 1 Development mutation — low-friction draft/candidate changes;
- Tier 2 Execution — Preflight + resolved scope;
- Tier 3 Governance/immutable assets — Impact Preview + explicit commit;
- Tier 4 Exception/protection reduction — risk acceptance + remediation/evidence.

Use specific verbs rather than generic `Confirm/Apply/Submit`.

### UX-006 — Context-derived workflow

No global Development/Regression/Validation mode switch. Workflow mode derives from formal context. Each Run retains explicit Purpose.

### UX-007 — Desktop-first

Primary baseline ≈1440×900+, optimized ≈1920×1080; ultrawide adds engineering context; compact desktop collapses Rails without hiding critical state; tablet/mobile primarily inspection.

### UX-008 — Requirement & Evaluation Hub ownership

Within `Cases > Requirements`, V1 shall provide local routes/screens for:

- Requirement Catalog/Detail/Version;
- Evaluation Profile Detail/Qualification;
- Coverage Contract Detail/Matrix;
- Golden Evidence Fixture inspection/qualification context.

No sixth top-level workface is introduced.

### UX-009 — Engineering workspace/environment ownership

Global Settings/Engineering Workspace (and/or Context Ribbon drill-down) shall provide inspect/register/manage surfaces for:

- registered SourceWorkspaces;
- SourceSnapshot history/identity;
- Execution Environment Profiles/qualification state.

Inspecting these objects shall not silently switch current Task/Run execution context.

## 18. OpenBridge design-system requirements

### OB-001 — Foundation

OpenBridge is shared visual/interactivity foundation across Maritime Operational Surface and Engineering Assurance Surface. Engineering pages may use different information structures but shall not fall back to unrelated generic SaaS language.

### OB-002 — Reuse priority

```text
OB-NATIVE
→ OB-COMPOSED
→ OB-WRAPPED
→ COLAV-EXTENSION
→ CUSTOM-EXCEPTION
```

### OB-003 — Thin adapter

Business code may consume thin COLAV wrappers for framework/event/default/business/test/version integration. Adapter shall not recreate the design system.

### OB-004 — Token source of truth

OpenBridge design tokens are visual source of truth. COLAV may add semantic aliases/extensions; avoid page-level arbitrary colors/spacing/typography.

### OB-005 — Themes

Support `DARK | LIGHT | SYSTEM`; Dark is V1 primary design baseline. Maritime Chart DAY/DUSK/NIGHT palette, where supported, is separate.

### OB-006 — Semantic color budget

Draft/Candidate/Published/Historical neutral-by-default. Strong semantic color reserved for assurance/blocking/operational states. Operational Safety and Engineering Assurance have distinct presentation semantics. State never color-only.

### OB-007 — Documented extensions only

Prohibit undocumented Shadow DOM manipulation, internal class dependencies, deep private selectors, local forks/copies and page-specific internal overrides. Custom Exceptions require justification/maintenance risk.

### OB-008 — OpenBridge dependency and license provenance gate

Before an OpenBridge dependency/component catalog is accepted for V1 implementation, record and review:

- exact package/repository/catalog version or commit;
- official source/provenance URL;
- applicable license(s);
- attribution/NOTICE obligations;
- distribution/commercial compatibility decision for the exact selected artifacts;
- required updates to `THIRD_PARTY_NOTICES.md` and dependency inventory.

This PRD does **not** assert a license conclusion for an unpinned or unverified OpenBridge artifact. Implementation acceptance requires evidence for the actual selected version.

## 19. Layout requirements

### LAYOUT-001 — Global shell

Compact OpenBridge-style App Rail + Engineering Context Ribbon.

### LAYOUT-002 — Secondary navigation

Compact Local Header + Primary Tabs + Contextual Drawers; avoid persistent second left nav.

### LAYOUT-003 — Reusable layouts

```text
SpatialWorkspaceLayout
ExplorerLayout
ObjectDetailLayout
AssuranceControlLayout
GuidedWorkflowLayout
```

### LAYOUT-004 — Adaptive rails

Mode-aware adaptive Rails with Canvas priority; critical state remains visible when Rails collapse.

### LAYOUT-005 — Scroll contracts

One dominant scroll owner per layout. Spatial Workspace viewport-locked; Explorer/ObjectDetail/Assurance/Guided use their defined content scroll model. Avoid nested-scroll chains.

### LAYOUT-006 — Personalization

Curated presets and bounded Presentation customization; no arbitrary IDE docking/floating in V1. Presentation State never contains engineering execution context.

## 20. Technical architecture and NFR requirements

### ARCH-001 — Clean Web/API cutover

V1 Web/API/Application layer may be replaced without long-term backward compatibility for old Web/session API. Existing simulation/COLAV computation is preserved only after exact-ref characterization demonstrates the behavior to preserve.

### ARCH-002 — Control Plane / Execution Plane

```text
Control Plane
FastAPI/Web + domain/application orchestration

Execution Plane
Isolated Run Workers
```

Native/solver crash should primarily terminate affected Worker/Run, not Web control plane.

### ARCH-003 — Shared Assurance Engine

Web, CLI and GitHub Actions call same Assurance/Execution/Evaluation implementation. No duplicated regression semantics.

### ARCH-004 — Canonical Observation/Event Model

Run Worker emits one versioned model consumed by Live UI, Evidence Writer, Analyze, Replay and Compare through projections/adapters. Browser is Observer, not Evidence Recorder. Browser disconnect shall not cause formal evidence loss.

### ARCH-005 — Persistence

```text
Relational Metadata Store
+
Content-Addressed Artifact Store
```

V1 target: SQLite + local filesystem CAS behind repository/store interfaces.

### ARCH-006 — Source Workspace

Git/worktree-aware Workspace Registry resolves and freezes SourceSnapshot before Development execution. Browser/API shall not accept arbitrary filesystem paths as execution authority.

### ARCH-007 — Local-first, server-ready

V1 target: single-engineer Local Engineering Workstation; service/adapter boundaries do not hardcode domain semantics to one machine.

### ARCH-008 — Qualified execution environment

Development may use unqualified/compatible environments; Fast Merge requires Qualified Reference Environment.

### ARCH-009 — Reproducibility contract

Independent Random Stream Registry plus versioned Reproducibility Contract. CORE/Fast Merge require D3 in Qualified Environment.

### ARCH-010 — Historical compatibility

`Read-Old / Write-Current`. SEALED Evidence never migrated in place. Versioned readers may create non-destructive derived projections. Missing historical fields shown unavailable; current algorithms never fabricate historical facts.

Compatibility:

```text
FULL
DEGRADED
RAW_EVIDENCE_ONLY
UNSUPPORTED_SCHEMA
```

### ARCH-011 — Local security boundary

V1 is local-first and shall default to loopback/local-only binding. Remote/multi-user exposure is out of V1 unless separately secured.

Application services may access only registered repositories/workspaces/artifact roots. Frontend/API shall not provide general arbitrary filesystem-path or shell-command execution endpoints.

Imported manifests, Debug Handoffs and Agent Results are **data**, not executable command authority. Any actual source/run command is resolved by trusted backend policy from registered identities/contracts.

Tier-2/3/4 endpoints shall apply the same domain action/eligibility policy even in single-user mode.

### ARCH-012 — CAS retention and sealing crash consistency

Artifacts referenced by any retained SEALED Run, Published asset, Gate Attestation or retained Evidence Bundle shall not be automatically garbage-collected.

V1 cleanup shall be explicit, reachability-aware and provide impact preview. Deletion of a referenced artifact must be blocked unless the owning record is itself being removed under an explicit retention policy that does not violate immutable-history requirements.

Run sealing is crash-safe: a Run cannot report `SEALED` until required manifest/artifact references and digests are durably/consistently committed. Orphan/unfinalized artifacts after worker/control-plane crash must be detectable and recoverable/cleanable without mutating SEALED history.

### ARCH-013 — Frontend host stack ADR

Before OpenBridge application implementation begins, an Architecture Decision Record/spike shall select the V1 frontend host stack. Decision criteria include:

- OpenBridge Web Component interoperability;
- typed Domain/Projection models;
- routing/Canonical Deep Links;
- Task Context vs Presentation State separation;
- testing/accessibility/tooling;
- migration from current `web_gui`;
- build/bundle/dependency management.

The PRD does not assume React, Vue or another framework before this ADR is accepted.

### ARCH-014 — Exact baseline characterization manifest

Before simulation-core preservation claims are used to constrain refactoring, Milestone 0 shall produce an immutable `Baseline Characterization Manifest` containing:

- repository identity;
- exact branch/worktree/commit;
- execution environment;
- selected algorithms/scenarios;
- known fallbacks/limitations;
- characterization outputs/tolerances/evidence.

Design documents describing a different historical worktree/ref do not substitute for live source/ref verification.

## 21. Performance assurance requirements

### PERF-001 — Fast Merge performance guard

Fast Merge checks runtime sanity/significant performance regression including crash/timeout/unexpected fallback and broad absolute/relative regression policy. PASS does not claim MASS real-time qualification.

### PERF-002 — Future strict performance qualification

Strict deadline, p99/max latency, deadline-miss rate/resource-budget claims reserved for dedicated qualified performance environment/Suite.

## 22. Preflight requirements

Every execution resolves and visibly presents effective scope before starting.

Checks may include:

- purpose/applicable subject bindings;
- Case validity/qualification;
- Scenario Qualification Policy for qualification runs;
- ADP/config compatibility where applicable;
- source identity (SourceSnapshot vs ImplementationArtifact);
- assets/ENC availability;
- runtime/dependencies;
- parameters/schema;
- technical compatibility;
- evidence/diagnostic capability;
- Evidence Capture Profile/Core Evidence floor;
- environment qualification;
- reproducibility eligibility;
- formal-claim eligibility.

Failure categories distinguish invalid config, dependency, capability, scenario/data, evidence and runtime failures.

## 23. Agent workflow requirements

### AGENT-001 — Structured Debug Handoff

Markdown + JSON, referencing Evidence Bundle rather than duplicating large telemetry. Minimum sections: reproduction, failure facts, execution context, diagnostics, confirmed findings, open hypotheses, Agent task, change contract.

### AGENT-002 — Protected validation assets

Default Algorithm-fix task protects Published Cases, Requirements, Evaluation Profiles, Evaluator implementations, Golden Evidence, Core Suite, Gate policies and baseline Run evidence. Agent may request protected-asset change but not silently perform it as success strategy.

### AGENT-003 — Platform authority

Agent Result does not establish PASS/FIX_VERIFIED. Platform executes new Candidate Run/Evaluation under frozen test/evaluation conditions.

## 24. Metrics and success measures

Instrument:

- Requirement Coverage by Coverage Contract;
- Scenario-family/condition coverage;
- mean time to reproduce known defect;
- mean time failure → confirmed finding;
- regression escape count;
- Fast Merge duration/first-pass rate;
- INCOMPLETE vs behavioral FAIL rate;
- CORE flaky/quarantined case count;
- OpenBridge component reuse/conformance ratio.

Engineering metrics only; not certification claims.

## 25. V1 acceptance gate / Definition of Done

V1 Release Candidate shall pass a versioned platform acceptance profile such as `v1-acceptance@1`.

### ACC-001 — Golden Workflow

At least one real representative defect completes official path:

```text
FAIL Run
→ Investigation
→ Exact Reproduction
→ Analyze
→ Finding
→ Debug Handoff
→ Codex/ZCode candidate change
→ Agent Result/source identity
→ Candidate Run
→ Compare
→ FIX_VERIFIED
→ Regression Case
→ Stability Qualification
→ CORE PASS
→ Fast Merge Gate PASS
→ Investigation CLOSED
```

No manual DB editing/hidden one-off scripts substitute required product steps.

### ACC-002 — Four encounter baselines

Head-on, Crossing, Overtaking, Basic Multi-ship each have Qualified Published Case + real Run + SEALED Evidence + Evaluation + Historical Replay. This proves platform breadth, not G4.

### ACC-003 — Multi-algorithm integration

At least one MPC-based algorithm and one **role-compatible non-MPC dynamic COLAV planner where repository readiness permits** complete Manifest → Contract → Runtime → Smoke → Diagnostics → Implementation Artifact → ADP → Development Run. Static path planning/tracking roles may be integrated but shall not be presented as equivalent dynamic COLAV evidence.

### ACC-004 — Evidence integrity

Export SEALED Run Bundle, import into isolated/clean registration context, verify checksums/integrity, replay history and retain original source identity/digests/verdict.

### ACC-005 — GitHub gate

Real PR demonstrates known-good merge eligible and intentional regression blocked; check traces to Gate Attestation → ExecutionGroup → Runs → Evaluation → Evidence.

### ACC-006 — Crash/incomplete semantics

Inject controlled worker/solver/evidence failure; affected Run becomes CRASHED/INCOMPLETE as appropriate, other isolated Runs preserve evidence, partial evidence preserved, Gate blocked/incomplete, UI does not mislabel infrastructure failure as behavioral FAIL.

### ACC-007 — Reproducibility and CORE stability

Every member of the Published V1 CORE Suite shall have **current Stability Qualification** under the applicable Reproducibility Contract and Qualified Environment.

At least one representative CORE Case shall additionally be repeated end-to-end as a demonstration fixture showing D3 Gate-Stable Applicability, Verdict, critical event ordering and metric/event tolerances.

### ACC-008 — OpenBridge conformance and provenance

Produce OpenBridge Conformance Report for P0 components. No undocumented internal styling hacks. The exact OpenBridge dependency/catalog provenance/license/NOTICE review required by OB-008 is complete and repository notices/inventory are updated as required.

### ACC-009 — P0 defect state

No unresolved P0 defect.

### ACC-010 — Semantic boundary

Passing platform acceptance shall not be represented as algorithm formal validation, MASS approval, paper numerical reproduction or certification.

### ACC-011 — Security boundary

Default local deployment binds to local/loopback access; tests confirm untrusted frontend input cannot request arbitrary filesystem access or shell execution outside registered/policy-resolved workspaces.

### ACC-012 — Sealing/retention integrity

Fault-injection confirms sealing does not report SEALED before durable manifest/artifact consistency; reachability-aware cleanup does not delete retained SEALED/Attestation evidence.

## 26. Migration strategy

Old Web/session/API model is not long-term compatibility contract.

1. Produce Baseline Characterization Manifest for exact source ref.
2. Characterize representative simulation/algorithm behavior.
3. Define adapters around verified computational core.
4. Establish domain/application boundaries and Run Worker.
5. Introduce Canonical Observation/Event/Evidence model.
6. Complete frontend host-stack ADR and OpenBridge dependency/provenance gate.
7. Build new OpenBridge Web workfaces.
8. Import useful legacy scenarios/configurations as Draft Cases where practical.
9. Verify four encounter baselines and representative algorithms.
10. Cut over active Web only after Golden Workflow and acceptance gates pass.
11. Retire legacy Web execution truth; do not maintain two active session truths.

## 27. Requirement traceability conventions

Implementation/tests/detailed design shall cite stable IDs from this PRD.

Each critical P0 requirement traces:

```text
PRD Requirement
→ Domain/API implementation
→ UI/API owner/surface
→ Persistence identity
→ Test/Fixture
→ Evidence/Acceptance proof
→ Status
```

Every P0 first-class object shall have explicit domain identity, UI owner/global route where applicable, persistence identity, implementation milestone and acceptance/test path.

## 28. Decision register summary (D-001 — D-144)

The full workshop decisions are normalized above. This summary preserves decision lineage.

### D-001 — D-010: Product/persona/gate foundation

- D-001: Algorithm developer/research engineer and V&V/test engineer are equal primary personas.
- D-002: Gate ownership is hybrid Web V&V + CI/CD Gate.
- D-003: Two-stage quality gate: Fast Merge + future Full Release.
- D-004: V1 does not deploy to MASS; handoff foundations only.
- D-005: Validation object is exact ADP; scenario/tracker/seed are conditions.
- D-006: Engineering V&V-grade, safety-assurance-ready, not certification.
- D-007: Requirement-driven layered parametric validation.
- D-008: Requirement-based layered evaluation + versioned Evaluation Profiles.
- D-009: Evidence strategy prioritizes defect escape, false confidence, regression risk and comparison.
- D-010: Structured Agent-ready Debug Handoff is V1 core.

### D-011 — D-021: Debug lifecycle, IA and Workbench foundations

- D-011: Bug closure requires root cause, fix verification, Regression Case and CORE PASS.
- D-012: OpenBridge UI/UX refactor primary but constrained by real algorithm workflow.
- D-013: V1 = Development + Core Regression; V2 = Formal Validation.
- D-014: Golden Workflow real failure → CORE PASS.
- D-015: Full-stack refactor permitted with single-truth/evidence principles.
- D-016: V1 IA = Workbench, Cases, Runs, Algorithms, Regression.
- D-017: Investigation persistent first-class object.
- D-018: Investigation lifecycle/closure fixed.
- D-019: Workbench Run/Analyze.
- D-020: Compare added.
- D-021: Config = Investigation Baseline + Overrides + Preflight.

### D-022 — D-029: Workbench diagnosis

- D-022: Resume-first Workbench Home.
- D-023: Multi-entry Investigation creation.
- D-024: Chart-first Run layout.
- D-025: Encounter-first Context Rail.
- D-026: Algorithm/System Risk/Inspection contexts separated.
- D-027: Inspection vs Intervention separated.
- D-028: Analyze centered on synchronized diagnostic timeline.
- D-029: Evidence-first localization; no automatic root-cause claim.

### D-030 — D-043: Case and Run/Evidence foundation

- D-030: Hybrid Case Designer.
- D-031: Test Case = executable test specification.
- D-032: Scenario Family distinct from Concrete Case.
- D-033: Draft → immutable Published Case Version.
- D-034: Multi-level Case Qualification distinct from algorithm verdict.
- D-035: Bug creates exact reproduction + curated Regression Case.
- D-036: Regression tiers CORE/EXTENDED/ON-DEMAND; V1 CORE.
- D-037: Run immutable; execution status distinct from verdict.
- D-038: Mandatory Core Evidence + versioned Evidence Capture Profiles.
- D-039: Replay vs Reproduce distinct.
- D-040: Reproduction Fidelity.
- D-041: Evidence Manifest + Run sealing.
- D-042: Evaluation versioned interpretation.
- D-043: Portable Evidence Bundle V1.

### D-044 — D-057: Algorithm/ADP and CORE foundation

- D-044: Manifest + Runtime Verification; declared vs verified.
- D-045: Algorithm identity = Definition → Implementation Artifact → ADP.
- D-046: Experiment Override → Candidate → ADP promotion.
- D-047: Dirty source Development-only for formal baseline purposes.
- D-048: Core diagnostics + typed extensions.
- D-049: Evidence-Derived Capability Matrix.
- D-050: Impact-driven evidence invalidation/reuse.
- D-051: CORE Suite immutable versioned manifest.
- D-052: Suite Completeness separate from Verdict.
- D-053: Flaky CORE → Stability Qualification/Quarantine.
- D-054: Isolated parallel execution.
- D-055: Every merge full CORE; impact only adds.
- D-056: Gate early, execute to completion.
- D-057: Stable GitHub Required Check + case matrix.

### D-058 — D-076: Runs/Cases/Evaluation workfaces

- D-058–D-063: Run Explorer, immutable Run Detail, verdict-aware landing, shared Replay surface, Original Verdict, Manifest-centric Evidence Explorer.
- D-064–D-069: Requirement-centered Cases, chart-centered Designer, declarative behavior, template snapshot/rebase, Draft execution, lifecycle/supersession.
- D-070–D-076: Versioned Requirement Catalog, Applicability/Compliance, Criticality/Enforcement, dual-axis Evaluation, Evaluator identity, Profile Qualification, Coverage Contract.

### D-077 — D-094: Compare/Agent/Algorithm/Regression governance

- D-077–D-082: Comparison Contract, dual-time alignment, Fix Verification, immutable Debug Handoff, Agent Change Contract, Agent Result + platform re-verification.
- D-083–D-088: Algorithm Catalog, explicit ADP scope, Evidence-first Capability Cell, Compatibility separation, immutable ADP, Manifest-driven Integration.
- D-089–D-094: Gate-centered Regression, Protected Baselines, Baseline Transition, Gate Attestation, Merge Waiver, Suite Change Proposal.

### D-095 — D-112: Global UX, OpenBridge and layout

- D-095–D-100: Explicit scoped context, Object Navigator, Attention, risk-tiered actions, context-derived workflow, desktop-first.
- D-101–D-106: OpenBridge-native first, component-first + thin adapter, token source, dual theme, semantic color budget, documented extensions.
- D-107–D-112: App Rail + Ribbon, local tabs/drawers, five layouts, adaptive Rails, scroll contracts, curated presets.

### D-113 — D-130: Detailed Workbench/Case/Run UX

- D-113–D-118: lifecycle-aware resume, Execution Clock vs Inspection Cursor, workflow controls, Encounter Focus Stack, trajectory layers, typed event timeline.
- D-119–D-124: encounter-centric authoring, Traffic Actors, Condition Profiles, multi-ship Intent Graph, event-relative phases, neutral Qualification Preview.
- D-125–D-130: dense Run table, explicit query state, ExecutionGroup, semantic lineage, Original Verdict vs current trust, stable Core Run Summary.

### D-131 — D-144: Architecture, scope and acceptance

- D-131: Algorithm Overview default; ADP scope explicit.
- D-132: Git/worktree Registry + frozen Source Snapshot.
- D-133: Control Plane + isolated Run Worker + pluggable runtime.
- D-134: Shared Assurance Engine + multiple frontends.
- D-135: Qualified Execution Environment Profiles.
- D-136: Two-level performance assurance.
- D-137: Relational Metadata + Content-Addressed Artifact Store.
- D-138: Canonical Observation/Event model powers Live/Evidence/Replay.
- D-139: Local-first workstation; server-ready boundaries.
- D-140: Reproducibility Contract + Determinism Classes.
- D-141: Read-old/write-current historical compatibility.
- D-142: V1 Production Core = Development + Core Regression.
- D-143: Clean Web/API cutover; characterize/preserve/adapt simulation core.
- D-144: Evidence-Backed V1 Acceptance Gate.

## 29. Final V1 product statement

V1 is complete when a COLAV engineer can use an OpenBridge-native Web workbench to move from a real algorithm failure to exact reproduction, evidence-backed diagnosis, coding-agent handoff, controlled before/after verification, permanent regression protection and an enforced GitHub merge gate — with immutable, reproducible and inspectable evidence throughout the chain — without confusing functional reproduction, numerical reproduction, runtime readiness, capability evidence or release eligibility.
