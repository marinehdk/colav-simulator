# Colav-Simulator V1 Product Requirements Document

> **Status:** V1 scope frozen for detailed design and implementation  
> **PRD baseline:** D-001 through D-144  
> **Product boundary:** Engineering V&V-grade, safety-assurance-ready; **not** a certification/type-approval claim  
> **Primary delivery:** Local-first COLAV Engineering & V&V Workbench  
> **V1 focus:** Development + Core Regression  
> **Last updated:** 2026-08-19

## 1. Purpose

This document is the product and engineering requirements baseline for the V1 full-stack redesign of `colav-simulator`.

It converts the requirements workshop decisions D-001 through D-144 into an implementable specification. It is the primary requirements source of truth for V1. The companion documents are:

- `Design/Colav-Simulator-V1-UI-Spec.md` — OpenBridge UI, screen and interaction specification.
- `Design/Colav-Simulator-V1-Implementation-Plan.md` — implementation milestones, migration order and acceptance sequence.
- Existing architecture/evidence documents under `Design/` remain technical evidence and background. Where an older Web/session model conflicts with this PRD, this PRD governs the V1 Web/Application redesign while the verified simulation/COLAV computational core should be preserved and adapted.

This PRD aligns with the repository mission: establish a verifiable understanding across scenario, perception, planning, control, dynamics, evaluation and Web; safely optimize or add COLAV algorithms; and distinguish safety, COLREG behavior quality, research reproduction and engineering performance.

## 2. Executive summary

Colav-Simulator V1 shall become a unified, reproducible engineering workbench for developing, debugging and regression-validating collision-avoidance algorithms.

The primary V1 workflow is:

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

V1 is not a MASS deployment product and does not claim algorithm certification. It shall, however, produce traceable engineering evidence and domain objects that can later support Formal Validation, release eligibility and MASS handoff.

## 3. Problem statement

The current project can execute representative COLAV scenarios, but it does not yet provide one coherent engineering V&V system that answers all of the following reliably:

1. How is a real algorithm failure reproduced exactly?
2. Where in the scenario/perception/planner/control/evaluation chain did abnormal behavior first appear?
3. Which scenario families and boundary conditions are sufficient to test a particular requirement?
4. What does a single successful run actually prove, and what does it not prove?
5. How are algorithms compared without changing several experimental conditions at once?
6. How is a verified algorithm configuration identified so it cannot drift before downstream use?
7. How are historical defects converted into permanent regression protection?
8. How is a GitHub merge gate tied to exact source, ADP, cases, profiles, environment and evidence?

The highest-priority risks are algorithm defect escape, false safety confidence, regression escape and poor algorithm selection/comparison caused by non-unified evidence.

## 4. Primary users and jobs to be done

### 4.1 Primary personas

V1 treats the following as equally primary roles, even when one engineer performs both:

- **Algorithm/COLAV/MPC Developer / Research Engineer** — needs fast reproduction, diagnosis, controlled experimentation and source-level handoff.
- **Algorithm V&V / Test Engineer** — needs qualified cases, reproducibility, regression suites, evidence, pass/fail semantics and traceability.

The system shall not require separate people to author and approve assets in V1, but data models shall retain `created_by`, `executed_by`, `reviewed_by`, `approved_by` and related provenance fields for future team workflows.

### 4.2 Highest-frequency V1 jobs

1. Reproduce and diagnose a known algorithm issue.
2. Quickly validate behavior after an algorithm/source/configuration change.
3. Convert a fixed defect into a stable regression asset.
4. Run the protected CORE regression set locally and in GitHub CI.
5. Understand why a gate is PASS, FAIL or INCOMPLETE and inspect the underlying evidence.

## 5. Product principles

### P-001 — Evidence before presentation

The Web UI shall not maintain a second simulation truth. Live UI, replay, analysis and comparison are projections of the same versioned observation/event/evidence model.

### P-002 — Immutable historical facts

Published test definitions, sealed run evidence, original evaluation verdicts and gate attestations shall not be overwritten. Later interpretation or trust state is stored as derived/versioned records.

### P-003 — Published is not validated

The following shall remain distinct:

```text
Discoverable ≠ Runtime Ready ≠ Published ≠ Validated ≠ Release Eligible
```

### P-004 — Inspection is not intervention

Select, pin, scrub, replay, filter and layer visibility shall never silently alter Simulator or Planner state. Any state-changing test intervention must be explicit, versioned into a Run Override/Revision and preserved as evidence.

### P-005 — Reproducibility first

Every real execution receives a Run ID and freezes the result-critical identity needed to understand and reproduce that execution.

### P-006 — Hard gates are not averaged away

Safety/COLREG mandatory failures cannot be offset by efficiency, smoothness or aggregate scores.

### P-007 — OpenBridge-native first

The V1 Web shall remain as visually and behaviorally consistent with OpenBridge as practical, and shall reuse OpenBridge Web Components and design tokens before creating custom primitives.

## 6. V1 scope

### 6.1 V1 P0 product scope

V1 shall fully implement:

- Global OpenBridge application shell.
- Workbench: Run, Analyze, Compare.
- Persistent Investigations and lifecycle.
- Case/Test Engineering system.
- Immutable Runs and sealed Evidence.
- Algorithm Definition, Implementation Artifact and ADP model.
- Algorithm integration workspace and runtime verification.
- Evaluation/Requirement foundation.
- Core Regression and Fast Merge Gate.
- Git/worktree-aware source snapshots.
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

The following are reserved by the domain model but not fully implemented in V1:

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

The lifecycle language shall remain:

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

A persistent first-class object representing the engineering problem being solved and why multiple runs belong together.

Required lifecycle:

```text
OPEN
→ REPRODUCING
→ DIAGNOSING
→ FIX_IN_PROGRESS
→ VERIFYING
→ REGRESSION_PENDING
→ CLOSED
```

`BLOCKED` shall be available where appropriate.

`CLOSED` requires all of:

- failure reproduced;
- fix verified;
- regression case created;
- required CORE suite passed.

Optional external GitHub issue references may be stored; hard issue binding is not required.

### 8.2 Engineering Requirement

A versioned first-class object, not a string tag.

Minimum fields:

- stable ID and version;
- title/category;
- normative/source reference;
- engineering interpretation;
- applicability contract;
- expected behavior;
- evaluator bindings;
- required evidence;
- intrinsic criticality;
- lifecycle/supersession.

External COLREG/legal/normative source references shall be distinguished from the platform's engineering interpretation and evaluator thresholds.

### 8.3 Scenario Family / Case Template

A versioned authoring template defining parameter schemas/ranges, geometric constraints, default requirements/expected behavior and qualification expectations.

Template updates shall never silently modify already-instantiated Concrete Cases.

### 8.4 Concrete Test Case

An executable test specification containing:

- intent;
- requirement references;
- preconditions;
- scenario definition;
- traffic-actor behaviors;
- condition contract;
- encounter intent graph where applicable;
- test-phase contract;
- declarative expected behavior;
- evaluation-profile binding;
- qualification evidence;
- exact executable snapshot and digest.

Published Case Versions are immutable.

Lifecycle governance states:

```text
ACTIVE
DEPRECATED
RETIRED
INVALIDATED
```

Invalidation never deletes historical references; it triggers impact analysis on dependent evidence/claims.

### 8.5 Regression Case

A historical defect shall produce two related assets:

1. **Exact Failure Reproduction** — preserves original Case/RunSpec/seed/ADP/evidence.
2. **Curated Regression Case** — minimal stable trigger, affected requirement, root cause/finding lineage and expected behavior.

Regression tiers:

```text
CORE
EXTENDED
ON_DEMAND
```

V1 fully implements CORE; the other tiers are reserved.

### 8.6 Run

An immutable execution record. Every real execution creates a Run ID including terminal outcomes such as FINISHED, CRASHED, ABORTED and CANCELLED.

Run identity shall freeze, at minimum:

- purpose;
- Investigation/config revision if present;
- exact Case snapshot/version/digest;
- ADP/source identity;
- tracker/perception/environment profiles;
- seed/random-stream identity;
- evaluation profile;
- evidence-capture profile;
- execution environment;
- RunSpec;
- execution policy.

Execution status and evaluation verdict are independent.

Examples:

```text
FINISHED + FAIL
CRASHED + NOT_ESTABLISHED
FINISHED + PASS
```

### 8.7 ExecutionGroup

Represents multiple Runs intentionally created by one batch operation such as CORE regression or case qualification.

ExecutionGroup is distinct from Investigation and Run lineage.

### 8.8 Evidence Manifest / Evidence Artifact

Terminal Runs enter:

```text
CREATED → RUNNING → FINALIZING → SEALED
```

A sealed Run receives an immutable Evidence Manifest with provenance, artifact inventory, schemas, digests and original evaluation references.

Evidence status shall distinguish:

```text
AVAILABLE
NOT_CAPTURED
NOT_AVAILABLE
MISSING
CORRUPT
SCHEMA_MISMATCH
```

### 8.9 Evaluation Record

A versioned interpretation of sealed evidence.

- Original Evaluation is immutable and remains the Run's `Original Verdict`.
- Re-evaluations create new records and never overwrite the original.
- Re-evaluation is only allowed when required evidence is available.
- Missing evidence shall not default to PASS.

### 8.10 Algorithm Definition

Stable algorithm-family identity containing:

- algorithm ID/name/role;
- entrypoint/runtime contract;
- parameter schema;
- input/output contract;
- runtime requirements;
- declared capabilities;
- diagnostic capabilities.

Declared Capability is not Verified Capability.

### 8.11 Implementation Artifact

Exact source/build/runtime implementation identity including:

- Git revision/base commit;
- clean/dirty/snapshot state;
- source/build digest;
- dependency identity;
- runtime verification evidence.

Dirty source snapshots may be used for Development. ADP promotion, CORE candidate baseline and future formal/release work require immutable Implementation Artifacts.

### 8.12 Algorithm Deployment Profile (ADP)

The formal algorithm validation object. It includes:

- Algorithm Definition;
- Implementation Artifact;
- exact parameters;
- prediction model configuration;
- solver/runtime configuration;
- ship capability profile;
- timing/update assumptions;
- I/O contract/profile digest.

Tracker, Scenario/Case, Seed and similar values are validation conditions, not part of the Algorithm Definition.

Published ADPs are immutable. Editing occurs through Candidate Revisions and Workbench Experiment Overrides.

### 8.13 Evaluation Profile

Versioned definition of how evidence is interpreted, binding exact:

- Requirement versions;
- Evaluator implementations;
- applicability policies;
- thresholds;
- enforcement;
- evidence requirements;
- aggregation policy.

Published Evaluation Profiles are immutable and must pass a Qualification Suite before publication.

### 8.14 Regression Suite

Published immutable suite manifest referencing exact Case Versions, Evaluation Profiles and Execution Policy.

Any modification creates a new Suite Version through a Suite Change Proposal.

### 8.15 Protected Regression Baseline Set

Versioned set defining which mature ADP baselines `main` promises not to break.

It answers a different question from Core Suite:

- Core Suite: which tests are required for one validation object?
- Protected Baseline Set: which validation objects must every merge protect?

### 8.16 Regression Gate Attestation

Immutable proof object for one formal Fast Merge Gate execution, binding exact source, baseline set, suites, ADPs, profiles, execution environment, execution groups, evidence and original gate verdict.

Original gate verdict is immutable; current trust may later become `STALE`, `IMPACTED` or `REASSESSMENT_REQUIRED`.

### 8.17 Debug Handoff and Agent Result

Debug Handoff is a versioned immutable Agent-ready context snapshot with Markdown + JSON representations.

It shall separate:

- facts;
- confirmed findings;
- hypotheses/diagnostic leads;
- Agent task;
- change contract.

Agent Result records what the coding Agent changed and reported. Agent-reported tests are development information, not formal Fix Verification evidence.

## 9. Golden workflow requirements

### GW-001 — Failure creation

The user shall be able to create a Development Run from a published case, draft case or ephemeral case variant with frozen source and execution identity.

### GW-002 — Failure-to-Investigation

A failed/incomplete Run shall support `Investigate`, creating or linking an Investigation without requiring users to re-enter the Run configuration.

### GW-003 — Exact reproduction

`Reproduce` shall clone the frozen experiment definition, run Preflight and create a new Run. Reproduction fidelity shall be classified as:

```text
EXACT
CONTROLLED_VARIATION
DERIVED
NOT_REPRODUCIBLE
```

### GW-004 — Analyze

Analyze shall synchronize Chart, Encounter, Planner/Diagnostics, Evidence and a typed multi-lane event timeline at the same Inspection Cursor.

### GW-005 — Debug handoff

The user shall be able to generate a versioned Debug Handoff package containing exact reproduce instructions, RunSpec, ADP/source identity, failure window, evidence references, diagnostics, findings/hypotheses and Agent Change Contract.

### GW-006 — Agent result reintegration

The platform shall accept a candidate source identity and structured Agent Result, verify it against the Change Contract, freeze a source snapshot and allow platform re-verification.

### GW-007 — Compare

Before/After verification shall compare two immutable Runs using a Comparison Contract that identifies controlled conditions, intended changes, known variations, unexpected differences and Comparison Fidelity.

Comparison fidelity states:

```text
CONTROLLED
CONTROLLED_WITH_KNOWN_VARIATIONS
COMPROMISED
NON_COMPARABLE
```

### GW-008 — Fix Verification

A formal Fix Verification Record shall only reach `FIX_VERIFIED` when:

- baseline contains the target failure under applicable conditions;
- candidate re-activates the same target requirement/intent;
- target failure changes from FAIL to PASS;
- candidate evaluation is complete;
- no new mandatory failure is introduced;
- comparison fidelity meets policy.

States:

```text
NOT_STARTED
CANDIDATE
FIX_INDICATED
FIX_VERIFIED
FIX_REJECTED
```

### GW-009 — Regression promotion

A confirmed/fixed defect shall support promotion/curation to a Regression Case with traceable lineage.

### GW-010 — Closure

Investigation cannot close before a Regression Case exists and required CORE regression passes.

## 10. Workbench requirements

### WB-001 — Resume-first home

Workbench Home shall prioritize resuming active Investigations, followed by recent failures, investigations, quick reproduction and current Core Regression status.

### WB-002 — Investigation entry paths

Create/enter an Investigation from:

- Failed Run;
- existing Case;
- Algorithm/ADP;
- scratch.

A failed-run entry shall inherit the reproducible context and open analysis at the relevant failure timestamp when available.

### WB-003 — Workbench modes

Workbench modes are exactly:

```text
Run | Analyze | Compare
```

Lifecycle-aware resume recommends a mode while preserving last inspection/presentation state separately.

### WB-004 — Baseline + Overrides

Configuration is modeled as Investigation Baseline + versioned Run Overrides + Preflight. Overrides create revisions; they do not silently mutate baseline.

### WB-005 — Run layout

Run View shall be chart-first with an optional Situation Rail, Context Rail and bottom Simulation Timeline/controls.

### WB-006 — Encounter-first context

Context Rail shall be encounter-first:

```text
Encounter
→ COLREG/responsibility
→ Risk/CPA/TCPA
→ Target evidence
→ Planner response
→ Events
```

### WB-007 — Three encounter contexts

Always distinguish:

- Algorithm Context — what Planner focuses on;
- System Risk Context — platform monitor's highest risk;
- Inspection Context — what the user is viewing/pinning.

Divergence must be visible and diagnostic; user selection must not alter Planner focus.

### WB-008 — Execution vs inspection clock

Live Run maintains:

- Execution Clock — actual simulator position;
- Inspection Cursor — user-viewed evidence time.

Scrubbing backward shall not pause the simulator. Historical inspection during a live run must visibly show distance behind the live edge and provide `Return to Live`.

### WB-009 — Execution controls

Development/diagnostic workflows may allow Pause, Resume, deterministic Step, Simulation Execution Rate and Stop; every execution control is a typed Run event.

CORE/Fast Merge execution is `AUTOMATED_LOCKED`; manual Pause/Step/Rate Change is prohibited. Abort yields INCOMPLETE.

Simulation Execution Rate and Historical Replay Speed are separate concepts.

### WB-010 — Trajectory semantic layers

The Chart shall distinguish:

1. Historical Fact;
2. Mission/Reference;
3. Committed Planner Output;
4. Prediction;
5. Candidate/Rejected Plans.

Predictions require source, generation time, horizon and validity/age. Candidate/rejected plans are progressively disclosed and not shown by default.

### WB-011 — Analyze timeline

Analyze is centered on a synchronized typed multi-lane timeline with lanes for at least Encounter, Risk, Perception, Planner, Constraints, Control, Evaluator, Runtime and Annotation.

Events support POINT, INTERVAL and TRANSITION time forms and distinguish observed events, derived events, evaluation findings, system diagnostic leads and user annotations.

### WB-012 — Failure localization

The system shall build a factual failure window from evaluator/runtime/planner/constraint/fallback/risk events and mark first abnormal transition/key transitions. It shall not auto-declare root cause.

Root cause/finding is an engineer-confirmed Investigation Finding with hypothesis/evidence/rejected alternatives/affected requirement/proposed fix.

### WB-013 — Compare alignment

Compare supports Absolute Simulation Time and evidence-based Semantic Event Alignment simultaneously. Semantic alignment never hides real timing differences.

### WB-014 — Agent Change Contract

Every Debug Handoff shall define allowed change domains, protected validation assets, prohibited success strategies and required verification. Protected assets cannot be silently modified to make a test green.

## 11. Cases requirements

### CASE-001 — Requirement-centered library

Cases shall be organized primarily around validation Requirements, with Scenario Family/Encounter/Purpose/Environment/Lifecycle as strong facets.

### CASE-002 — Designer layout

Case Designer is a chart-centered executable test designer with:

- Test Specification rail;
- Chart/ENC scenario geometry center;
- Qualification rail;
- detailed Parameters/Expected Behavior/Events/Advanced YAML/JSON/Diff areas.

Chart and structured parameters are synchronized views of one Case model.

### CASE-003 — Declarative expected behavior

Case stores behavior semantics and Requirement bindings. Common measurement logic and thresholds belong to versioned Evaluation Profiles.

Case-specific numeric assertions are allowed only as explicit `LOCAL_ASSERTION` with rationale.

### CASE-004 — Template instantiation

Concrete Case stores exact template-version lineage and executable snapshot. New template versions are offered through Compare/Rebase into a new draft; no live inheritance.

### CASE-005 — Draft execution

Draft Cases and Ephemeral Case Variants may run for Development. Their Runs shall freeze exact snapshots and clearly mark formal eligibility as Development-only.

Only Published + Qualified Cases may enter formal Regression/Gate evidence; CORE additionally requires Stability Qualification.

### CASE-006 — Encounter-centric authoring

Primary authoring language shall be encounter geometry, not raw latitude/longitude alone. It shall support relative bearing, course relationship, speed, initial range, desired CPA/TCPA envelope, risk window and tolerances.

A versioned deterministic Geometry Compiler produces exact executable initial state. Published Case freezes Authoring Specification + Compiler Identity + Compiled Exact State + Digest.

An explicit Exact State mode is supported for precise historical reproduction.

### CASE-007 — Traffic Actor Behavior Contract

Targets are versioned Traffic Actors with initial state, nominal behavior, scripted/condition-triggered maneuvers and a reserved reactive-policy extension.

V1 CORE defaults to deterministic traffic behavior.

### CASE-008 — Condition Contract

Case declares required/allowed/prohibited execution conditions. Exact environment/perception/tracker/noise/latency settings are supplied through versioned Condition Profiles bound in RunSpec.

### CASE-009 — Multi-ship encounter intent

Multi-ship Cases use an Encounter Intent Graph with semantic roles:

```text
REQUIRED
ALLOWED
BACKGROUND
PROHIBITED
```

Qualification compares Intent Graph to the Derived Encounter Graph. The Case shall not predefine Planner focus unless that focus itself is under test.

### CASE-010 — Test phases

Case uses Event-Relative Test Phase Contracts for Setup, Encounter Formation, Applicability, Response, Passing, Encounter Clear and Recovery. Each Run resolves actual Evaluation Windows from evidence.

Absolute time windows are supported only as explicit special cases, especially historical regression, with rationale.

### CASE-011 — Qualification

Before publication, Case must pass:

- L1 Definition validity;
- L2 physical/geometric validity;
- L3 test-intent qualification;
- L4 executability qualification;
- algorithm-neutral Scenario Qualification Preview.

Qualification Preview evaluates scenario validity, not algorithm capability, and cannot contribute algorithm validation/regression evidence.

### CASE-012 — Invalidation impact

Published Case content is immutable. DEPRECATED/RETIRED/INVALIDATED status changes do not delete historical runs. INVALIDATED Cases trigger evidence/coverage/capability/regression impact analysis.

## 12. Runs and Evidence requirements

### RUN-001 — Run Explorer

Runs shall use one unified Run Explorer with system views:

- Recent;
- Failures;
- Investigations;
- Reproductions;
- Core Regression;
- Crashed / Incomplete;
- User Saved Views.

### RUN-002 — Dense evidence-aware table

Default view is a dense table, not a card grid. Default columns include Run ID, Purpose, Investigation, Case, Algorithm/ADP, Source Identity, Execution Status, Original Verdict, Evidence State, Failure Domain and Created At.

### RUN-003 — Explicit query state

Run filters/search/sort/grouping/columns are explicit Inspection/Presentation Query State, serialized to restorable Deep Links. Active filters shall always be visible. Saved Views are explicit and distinct from system preset views.

### RUN-004 — Grouping

Run Catalog remains flat and every Run remains independently addressable. Optional UI grouping may use Investigation, ExecutionGroup, Algorithm/ADP, Case or Source.

### RUN-005 — Immutable Run Detail

Run Detail is an immutable historical record plus read-only inspection. Full debug mutations occur in Workbench.

Tabs include, at minimum:

```text
Overview | Replay | Evaluations | Evidence | Lineage
```

### RUN-006 — Verdict-aware landing

Run Detail first screen emphasizes different content for PASS, behavioral FAIL, INCOMPLETE/CRASHED and missing-evidence outcomes while retaining stable tabs.

### RUN-007 — Historical replay

Historical Replay shares the Observation Surface with live Run but is visibly `SEALED · HISTORICAL`; play/scrub controls read evidence and never invoke Simulator.

### RUN-008 — Original verdict

Original Verdict is immutable. Re-evaluations appear as separate Evaluation Records and never silently replace the Run verdict in Explorer/Overview.

### RUN-009 — Evidence Explorer

Evidence UI is Manifest-centric and grouped by engineering semantics, not only file tree:

- Experiment Identity;
- Navigation/Truth;
- Perception;
- Encounter/Risk;
- Planner;
- Control/Dynamics;
- Evaluation;
- Runtime;
- typed diagnostic extensions.

Evidence inspection and Replay share the same Inspection Cursor.

### RUN-010 — Portable Evidence Bundle

V1 shall export/import a self-describing bundle containing manifest, frozen RunSpec/provenance, evidence artifacts, evaluations, derived artifacts/summaries and checksums.

Imported evidence is verified before registration. Original digests and verdicts must remain unchanged.

### RUN-011 — Evidence trust

Historical Original Verdict and Current Evidence Trust/Claim Eligibility are independent.

Top-level trust states:

```text
CURRENT
IMPACTED
STALE
NOT_ELIGIBLE
```

Claim eligibility may differ by purpose (debug, regression, capability, formal validation).

### RUN-012 — Run summary

Run Overview contains:

1. Identity & Outcome;
2. Stable algorithm-agnostic Core Run Summary;
3. Evaluation Profile results;
4. typed algorithm diagnostic extensions.

Every displayed metric must expose evidence/evaluator/window provenance.

### RUN-013 — Lineage

Run Detail shall display a concise Semantic Engineering Lineage Path and provide an expandable local Provenance Graph. Relationships use controlled semantics such as `DERIVED_FROM`, `REPRODUCES`, `VERIFIES`, `COMPARED_WITH`, `QUALIFIES`, `GENERATED_BY`, `MEMBER_OF`, `PROMOTED_TO_REGRESSION`, `SUPERSEDES`.

## 13. Algorithms and ADP requirements

### ALG-001 — Algorithm catalog

Algorithm Catalog is organized by Algorithm Definition and directly exposes independent Runtime Readiness, Validation Readiness and Evidence-Derived Capability summary.

`AVAILABLE` shall never imply `VERIFIED`.

### ALG-002 — Algorithm scope

Generic navigation to an algorithm opens Algorithm Overview. Formal ADP scope is entered only through explicit selection or an exact ADP Deep Link.

Algorithm-level summaries may show capability coverage across ADPs but shall not produce a mixed global grade.

### ALG-003 — Algorithm identity

Identity layers are strictly:

```text
Algorithm Definition
→ Implementation Artifact
→ ADP
```

### ALG-004 — Dirty source

Development Runs may execute a frozen dirty source snapshot. Promotion to formal ADP/CORE baseline requires immutable Implementation Artifact.

### ALG-005 — ADP candidates

Published ADP is read-only. Changes create an ADP Candidate Revision; temporary Workbench changes use Experiment Overrides. Promotion creates a new immutable ADP version.

Promotion does not grant validation.

### ALG-006 — Capability matrix

Validation maturity is an Evidence-Derived Capability Matrix scoped to exact ADP and validation conditions.

Capability cells display verified grade and evidence state; detail exposes declared support, technical compatibility, scope, coverage, compliance and evidence lineage.

Grade is derived; it is not manually editable.

### ALG-007 — Capability evidence invalidation

Changes are handled through Validation Impact Analysis. Evidence belongs to exact implementation/ADP/conditions and may become reusable, revalidation-required, stale or not verified. New versions never silently inherit G4/validated claims.

### ALG-008 — Compatibility

Run Preflight distinguishes:

- Technical Compatibility;
- Evaluation/Evidence Compatibility;
- Validation Coverage.

Technical incompatibility can block execution. Unverified coverage does not block Development; it blocks formal claims as policy requires.

### ALG-009 — Core diagnostics and extensions

All algorithms provide algorithm-independent core diagnostics such as identity, solve/execution status, plan status, selected output, fallback/hold, computation time and availability.

Manifest-declared typed extension channels may include prediction, optimization, constraints, collision geometry, candidate selection, tree search, policy, observation/action and uncertainty.

Unavailable diagnostics are explicitly `NOT_AVAILABLE`.

### ALG-010 — Integration workspace

New algorithms shall be integrated through a staged Manifest-driven workflow:

```text
Manifest
→ Contract Verification
→ Runtime Verification
→ Smoke Execution
→ Diagnostics Verification
→ Implementation Artifact
→ ADP
```

Technical integration success grants `RUNTIME_READY`, not verified collision-avoidance capability.

### ALG-011 — Source workspace registry

V1 shall maintain Git/worktree-aware SourceWorkspace objects. Each Run freezes a source snapshot before execution. Subsequent worktree edits do not alter historical Run source identity.

### ALG-012 — Runtime adapter

Algorithm execution is abstracted by `AlgorithmRuntimeAdapter` with V1 primary `InWorkerPythonRuntime` and reserved ExternalProcess, Container, Remote and future MASS/HIL adapters.

## 14. Evaluation and Requirement requirements

### EVA-001 — Requirement applicability

Applicability and Compliance are independent:

```text
Applicability:
APPLICABLE | NOT_APPLICABLE | INDETERMINATE

Compliance:
PASS | FAIL | INCOMPLETE | NOT_EVALUATED
```

`NOT_APPLICABLE` never counts as PASS/coverage.

### EVA-002 — Intrinsic criticality vs enforcement

Requirement stores intrinsic criticality:

```text
SAFETY_CRITICAL
MISSION_CRITICAL
BEHAVIORAL
QUALITY
```

Evaluation Profile stores enforcement:

```text
HARD_GATE
REQUIRED
ADVISORY
OBSERVATIONAL
```

Safety-critical requirements cannot be silently downgraded. Explicit Waivers may permit research execution but cannot grant capability evidence.

### EVA-003 — Evaluation aggregation

Evaluation uses two axes:

```text
Completeness: COMPLETE | INCOMPLETE
Compliance: PASS | FAIL | NOT_ESTABLISHED
```

Domain verdicts are retained for Safety, COLREG, Navigation, Recovery, Performance, Runtime and extensions.

A known mandatory failure remains FAIL even if other evidence is incomplete.

### EVA-004 — Evaluator identity

Evaluator identity is:

```text
Evaluator Definition
→ Evaluator Implementation Artifact
→ Evaluation Profile binding
```

A Published Profile freezes exact implementation identities.

### EVA-005 — Profile qualification

Evaluation Profile must pass a qualification suite containing:

- static validation;
- evaluator verification/unit/contract tests;
- Golden Evidence Fixtures;
- previous-profile Verdict Diff with explained intended changes.

Unexplained verdict drift blocks publication.

### EVA-006 — Coverage

Requirement Coverage uses a versioned Coverage Contract + Evidence-Derived Coverage Matrix.

Coverage and Compliance are independent. A qualified, complete FAIL can still prove that a condition was covered.

Formal coverage states include:

```text
NOT_COVERED
PARTIAL
COVERED
STALE
INSUFFICIENT_EVIDENCE
```

### EVA-007 — No silent pass

`NOT_APPLICABLE`, `INDETERMINATE`, Waiver, unqualified Draft, missing required evidence, invalidated Case/Profile shall not create formal PASS or coverage.

## 15. Regression requirements

### REG-001 — Versioned CORE Suite

CORE suite is a Published Immutable Manifest referencing exact Case Versions, Evaluation Profiles and Execution Policy.

### REG-002 — Completeness before verdict

Suite evaluation first establishes Execution Completeness. Formal top-level states are:

```text
PASS
FAIL
INCOMPLETE
```

A worker/infrastructure failure is not mislabeled as algorithm behavioral FAIL.

### REG-003 — All CORE cases mandatory

V1 CORE does not use percentage tolerance: once execution is complete, all required CORE Cases and hard gates must pass.

### REG-004 — Stability qualification

CORE Cases must pass Stability Qualification. Non-deterministic `PASS → FAIL → PASS` becomes `TEST_STABILITY / INCOMPLETE`, enters Quarantine/Investigation and cannot be retried into green.

### REG-005 — Isolated parallel execution

CORE executes as isolated process/worker units with versioned timeout, parallelism, resource policy and environment identity. One crash shall not destroy evidence from other Runs.

### REG-006 — Full CORE every merge

Fast Merge Gate always runs the full current CORE Suite for every protected baseline. Impact Analysis may add tests; it cannot subtract the minimum set.

### REG-007 — Gate early, execute to completion

First deterministic failure may mark the Gate failed immediately, but mandatory CORE Runs continue so final evidence exposes the full regression picture.

### REG-008 — GitHub required checks

Stable Required Check names include, at minimum:

```text
quality/lint
quality/unit-tests
colav/core-regression
```

Internal Case matrix can change with suite versions without changing branch-protection names.

### REG-009 — Protected baselines

Fast Merge Gate binds a Published `ProtectedRegressionBaselineSet`. All baselines are mandatory. Adding/removing/replacing protected ADPs publishes a new version.

### REG-010 — Baseline transition

Protected baseline replacement uses `BaselineTransitionProposal` with old baseline still protected while the successor completes CORE, impact and required revalidation.

Lifecycle:

```text
DRAFT → QUALIFYING → READY_TO_SWITCH → APPLIED
```

with BLOCKED/REJECTED as needed.

### REG-011 — Gate Attestation

Every formal Fast Merge Gate creates immutable Regression Gate Attestation. New source identity invalidates applicability of previous gate results to the new candidate.

### REG-012 — Merge Waiver

A Merge Waiver may exceptionally change merge eligibility but shall never change FAIL/INCOMPLETE to PASS.

Waived merge is recorded as `MERGED_WITH_EXCEPTION`, creates a remediation obligation and cannot contribute verified capability/release evidence.

### REG-013 — Suite Change Proposal

Any CORE Suite add/replace/remove operation uses a Suite Change Proposal and automatically computes Requirement, historical-defect and protection diffs.

Removing a current failure blocker is explicitly marked `ACTIVE_FAILURE_PROTECTION_REMOVAL` and cannot silently restore green status.

### REG-014 — Gate control center

Regression home is a Gate-centered Assurance Control Center showing current candidate/baseline/suite, Gate decision, blockers, Suite Health, lightweight coverage, recent gates, transitions, waivers/remediation and suite management.

## 16. Global UX requirements

### UX-001 — Scoped context

Global Shell maintains only Application Scope such as Repository, Worktree/Workspace, Source and Runtime Environment.

Case/ADP/Profile/Tracker/Seed are explicit Task Context and cannot silently inherit across workfaces.

### UX-002 — Context Ribbon

Engineering Context Ribbon shall always expose the current workflow/scope, e.g. Investigation, sealed historical Run or Fast Merge Gate.

### UX-003 — Object Navigator

Provide global Object Navigator/Command Palette with stable Object IDs, Canonical Deep Links, recent history and object-specific actions.

Opening an object changes Inspection Context only unless an explicit action such as `Use in Investigation` changes execution context.

### UX-004 — Attention model

Separate:

1. Run Operational Events;
2. Immediate UI Alerts;
3. Persistent Engineering Attention Items.

`ACKNOWLEDGED ≠ RESOLVED`.

### UX-005 — Risk-tiered actions

Actions use four impact tiers:

- Tier 0 Inspection — immediate/read-only;
- Tier 1 Development mutation — low-friction draft/candidate changes;
- Tier 2 Execution — Preflight + resolved scope;
- Tier 3 Governance/immutable assets — Impact Preview + explicit commit;
- Tier 4 Exception/protection reduction — explicit risk acceptance + remediation/evidence.

High-impact actions shall use specific verbs rather than generic `Confirm/Apply/Submit`.

### UX-006 — Context-derived workflow

No global Development/Regression/Validation mode switch. Workflow mode derives from formal context (Investigation, Gate, historical run, integration, etc.). Each Run retains explicit purpose.

### UX-007 — Desktop-first

V1 primary design baseline is desktop/large-screen:

- baseline approximately 1440×900 or above;
- optimized around 1920×1080;
- ultrawide adds useful engineering context;
- compact desktop collapses Rails without hiding critical state;
- tablet/mobile are primarily inspection experiences.

## 17. OpenBridge design-system requirements

### OB-001 — Foundation

OpenBridge shall be the shared visual/interactivity foundation across both:

- Maritime Operational Surface;
- Engineering Assurance Surface.

Engineering pages may use different information structures but shall not fall back to an unrelated generic SaaS visual language.

### OB-002 — Reuse priority

Every UI element follows:

```text
OB-NATIVE
→ OB-COMPOSED
→ OB-WRAPPED
→ COLAV-EXTENSION
→ CUSTOM-EXCEPTION
```

### OB-003 — Thin adapter

Business code should consume a thin COLAV adapter/wrapper where useful for framework integration, event normalization, defaults, business semantics, testing hooks and OpenBridge-version isolation. The adapter shall not recreate the design system.

### OB-004 — Token source of truth

OpenBridge design tokens are visual source of truth. COLAV may add semantic aliases/extensions for V&V states but shall avoid page-level arbitrary colors, spacing and typography magic values.

### OB-005 — Themes

Support OpenBridge-native `DARK`, `LIGHT`, `SYSTEM`; Dark is the V1 primary design baseline.

Maritime Chart palette (e.g. DAY/DUSK/NIGHT where supported) is separate from Application Appearance.

### OB-006 — Semantic color budget

Lifecycle states such as Draft/Candidate/Published/Historical are neutral-by-default. Strong semantic color is reserved for assurance/blocking/operational states. Operational Safety and Engineering Assurance use distinct presentation semantics.

Important state shall never be expressed by color alone.

### OB-007 — Documented extensions only

Default prohibited patterns:

- undocumented Shadow DOM manipulation;
- dependency on internal OpenBridge class names;
- deep private CSS selectors;
- local forks/copies of OpenBridge components;
- page-specific component variants built by overriding internals.

Custom exceptions require documented justification and maintenance risk.

## 18. Layout requirements

### LAYOUT-001 — Global shell

Use Compact OpenBridge-style App Rail + Engineering Context Ribbon.

App Rail owns only primary workfaces and global utility; Ribbon owns current engineering scope.

### LAYOUT-002 — Secondary navigation

Use Compact Local Header + Primary Tabs + Contextual Drawers. Avoid a persistent second left navigation column.

### LAYOUT-003 — Reusable layout primitives

Primary screens shall preferentially use exactly five task-oriented layout families:

```text
SpatialWorkspaceLayout
ExplorerLayout
ObjectDetailLayout
AssuranceControlLayout
GuidedWorkflowLayout
```

### LAYOUT-004 — Adaptive rails

Spatial Workspace uses mode-aware adaptive rails with Canvas priority. Critical state remains visible when rails collapse.

### LAYOUT-005 — Scroll contracts

Each layout has one dominant scroll owner. Spatial Workspace is viewport-locked; Explorer/ObjectDetail/Assurance/Guided workflows use their defined content scroll models. Avoid nested-scroll chains.

### LAYOUT-006 — Personalization

V1 supports curated layout presets and bounded presentation customization such as collapse/resize/panel visibility/table columns. It does not implement arbitrary IDE-style docking/floating windows.

Presentation State never contains engineering execution context.

## 19. Technical architecture requirements

### ARCH-001 — Clean Web/API cutover

The V1 Web/API/Application layer may be replaced without long-term backward-compatibility requirements for the old Web/session API.

The verified simulation/COLAV computational core shall be preserved, characterized and adapted unless a separate justified change is required.

### ARCH-002 — Control Plane / Execution Plane

Architecture separates:

```text
Control Plane
FastAPI/Web + domain/application orchestration

Execution Plane
Isolated Run Workers
```

A solver/native crash should primarily terminate the affected Worker/Run, not the Web control plane.

### ARCH-003 — Shared Assurance Engine

Web, CLI and GitHub Actions call the same Assurance/Execution/Evaluation implementation. No duplicated regression semantics are allowed.

### ARCH-004 — Canonical Observation/Event Model

Run Worker emits one versioned Canonical Observation/Event Model consumed by Live UI, Evidence Writer, Analyze, Replay and Compare through projections/adapters.

Browser is an observer, not evidence recorder. Browser disconnect shall not cause formal evidence loss.

### ARCH-005 — Persistence

Use:

```text
Relational Metadata Store
+
Content-Addressed Artifact Store
```

V1 implementation target:

```text
SQLite + local filesystem CAS
```

through repository/store interfaces so future PostgreSQL/object storage can be introduced without changing domain semantics.

### ARCH-006 — Source Workspace

Git/worktree-aware Workspace Registry resolves and freezes source snapshot before each Run. Web may inspect/diff sources but is not a source editor.

### ARCH-007 — Local-first, server-ready

V1 deployment target is a single-engineer Local Engineering Workstation. Service/adapter boundaries must not hardcode single-machine assumptions into domain logic.

### ARCH-008 — Qualified execution environment

Environment identity is versioned and qualified. Development may use unqualified/compatible environments; Fast Merge Gate requires a Qualified Reference Environment.

### ARCH-009 — Reproducibility contract

Use versioned Reproducibility Contract and independent Random Stream Registry.

Determinism classes:

```text
D0 UNCONTROLLED
D1 SEEDED
D2 REPRODUCIBLE
D3 GATE_STABLE
```

CORE/Fast Merge require D3 in the qualified execution environment.

### ARCH-010 — Historical compatibility

Use `Read-Old / Write-Current`.

SEALED Evidence is never migrated in place. Historical schema adapters/readers create non-destructive derived projections if needed. Missing old fields are shown as unavailable; current algorithms shall never be used to fabricate historical facts.

Compatibility states may include:

```text
FULL
DEGRADED
RAW_EVIDENCE_ONLY
UNSUPPORTED_SCHEMA
```

## 20. Performance assurance requirements

### PERF-001 — Fast Merge performance guard

Fast Merge shall check runtime sanity and significant performance regression, including crash/timeout/unexpected fallback and broad absolute/relative regression policy.

Fast Merge PASS does not claim MASS real-time qualification.

### PERF-002 — Future strict performance qualification

Strict deadline, p99/max latency, deadline-miss rate and resource-budget claims are reserved for a dedicated qualified performance environment and Performance Qualification Suite.

## 21. Preflight requirements

Every Run/Gate execution shall resolve and visibly present the effective execution scope before starting.

Preflight checks may include:

- Case validity/qualification;
- ADP compatibility;
- source/artifact identity;
- assets/ENC availability;
- runtime/dependencies;
- parameters/schema;
- technical compatibility;
- evidence/diagnostic capability;
- environment qualification;
- reproducibility eligibility;
- formal-claim eligibility for the requested workflow.

Failure categories shall distinguish invalid config, dependency, capability, scenario/data and runtime failures.

## 22. Agent workflow requirements

### AGENT-001 — Structured Debug Handoff

Debug Handoff export includes Markdown + JSON and references the full Evidence Bundle rather than duplicating large telemetry.

Minimum sections:

- reproduction;
- failure facts;
- execution context;
- diagnostics;
- confirmed findings;
- open hypotheses;
- Agent task;
- change contract.

### AGENT-002 — Protected validation assets

Default Algorithm-fix tasks protect published Cases, Requirements, Evaluation Profiles, Evaluator implementations, Golden Evidence, Core Suite, Gate policies and baseline Run evidence.

An Agent may request a protected-asset change but not silently make it as a success strategy.

### AGENT-003 — Platform authority

Agent Result does not establish PASS/FIX_VERIFIED. The platform must execute a new candidate Run and evaluation under frozen test/evaluation conditions.

## 23. Metrics and success measures

V1 shall instrument quantitative baselines for future improvement. Initial measurements include:

- requirement coverage by coverage contract;
- scenario-family/condition coverage;
- mean time to reproduce a known defect;
- mean time from failure to confirmed finding;
- regression escape count;
- Fast Merge duration;
- Fast Merge first-pass rate;
- frequency of INCOMPLETE vs behavioral FAIL;
- number of CORE flaky/quarantined cases;
- OpenBridge component reuse/conformance ratio.

These are engineering metrics, not certification claims.

## 24. V1 acceptance gate / Definition of Done

V1 Release Candidate shall pass a versioned platform acceptance profile such as `v1-acceptance@1`.

### ACC-001 — Golden Workflow

At least one real representative algorithm defect shall be taken through the complete official product path:

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

No manual database editing or hidden one-off scripts may substitute for required product steps.

### ACC-002 — Four encounter baselines

Head-on, Crossing, Overtaking and Basic Multi-ship shall each have at least:

- Qualified Published Case;
- real Run;
- SEALED Evidence;
- Evaluation;
- Historical Replay.

This proves platform breadth, not G4 validation for every encounter.

### ACC-003 — Multi-algorithm integration

At least one MPC-based algorithm and one non-MPC planner (for example VO if repository readiness permits) shall complete Manifest → Contract → Runtime → Smoke → Diagnostics → Implementation Artifact → ADP → Development Run.

### ACC-004 — Evidence integrity

A sealed Run shall be exported as Portable Evidence Bundle, imported into an isolated/clean registration context, pass checksum/integrity verification, replay historical evidence and retain original source identity/digests/verdict.

### ACC-005 — GitHub gate

In a real Pull Request, required checks shall demonstrate:

- known-good change → merge eligible;
- intentional regression fixture → blocked;
- GitHub check can be traced to Regression Gate Attestation → ExecutionGroup → Runs → Evaluation → Evidence.

### ACC-006 — Crash/incomplete semantics

Inject a controlled runtime/worker/evidence failure and prove:

- affected Run becomes CRASHED/INCOMPLETE as appropriate;
- other isolated Runs retain their evidence;
- partial evidence is preserved;
- Gate is blocked/incomplete;
- UI does not mislabel infrastructure failure as behavioral algorithm FAIL.

### ACC-007 — Reproducibility

A representative CORE Case shall meet D3 Gate-Stable requirements through repeated execution with fixed source, ADP, Case, environment and random streams.

### ACC-008 — OpenBridge conformance

Produce an OpenBridge Conformance Report showing component reuse class, token use and custom exceptions. No undocumented Shadow DOM/internal CSS hacks are allowed in accepted P0 screens.

### ACC-009 — P0 defect state

No unresolved P0 defect may remain at V1 acceptance.

### ACC-010 — Semantic boundary

Passing the V1 platform acceptance gate shall not be represented as algorithm formal validation, MASS deployment approval or certification.

## 25. Migration strategy

The old Web/session/API model is not a long-term compatibility contract.

Migration sequence shall:

1. Characterize representative current simulation/algorithm behavior.
2. Define adapters around the existing simulation computational core.
3. Establish new domain/application boundaries and Run Worker.
4. Introduce Canonical Observation/Event and Evidence model.
5. Build new OpenBridge Web workfaces against the new model.
6. Import useful legacy scenarios/configurations as Draft Cases through adapters where practical.
7. Verify four encounter baselines and representative algorithms.
8. Cut over the active Web interface only after Golden Workflow and acceptance gates pass.
9. Retire legacy Web execution truth; do not maintain two active session truths.

## 26. Requirement traceability conventions

Implementation artifacts, tests and future detailed design should cite stable IDs from this PRD such as `WB-012`, `CASE-011`, `REG-008`, `ARCH-004`.

The repository's existing implementation traceability convention should be extended so each critical P0 requirement can be traced:

```text
PRD Requirement
→ Domain/API implementation
→ UI/API surface
→ Test/Fixture
→ Evidence/Acceptance proof
→ Status
```

## 27. Decision register summary (D-001 — D-144)

The full workshop decisions are normalized into the requirements above. This section preserves the high-level decision lineage without reproducing the conversational questions.

### D-001 — D-010: Product/persona/gate foundation

- D-001: Algorithm developer/research engineer and V&V/test engineer are equal primary personas.
- D-002: Gate ownership is hybrid Web V&V + CI/CD Gate.
- D-003: Two-stage quality gate: Fast Merge + future Full Release.
- D-004: V1 does not deploy to MASS; produce validated handoff foundations only.
- D-005: Validation object is exact ADP; scenario/tracker/seed are conditions.
- D-006: Engineering V&V-grade, safety-assurance-ready, not certification.
- D-007: Requirement-driven layered parametric validation.
- D-008: Requirement-based layered evaluation + versioned Evaluation Profiles.
- D-009: Evidence strategy prioritizes defect escape, false confidence, regression risk and comparison.
- D-010: Structured Agent-Ready Debug Handoff is V1 core.

### D-011 — D-021: Debug lifecycle, IA and Workbench foundations

- D-011: Bug closure requires root cause, fix verification, Regression Case and CORE PASS.
- D-012: OpenBridge UI/UX refactor is primary but constrained by real algorithm workflow.
- D-013: V1 scope = Development + Core Regression; V2 = Formal Validation.
- D-014: Golden Workflow fixed from real failure through CORE PASS.
- D-015: Full-stack refactor permitted with single-truth/evidence principles.
- D-016: V1 IA = Workbench, Cases, Runs, Algorithms, Regression.
- D-017: Investigation is a persistent first-class object.
- D-018: Investigation lifecycle and closure conditions fixed.
- D-019: Workbench initially Run/Analyze.
- D-020: Compare added as third Workbench mode.
- D-021: Config becomes Investigation Baseline + Overrides + Preflight.

### D-022 — D-029: Workbench interaction/diagnosis

- D-022: Resume-first Workbench Home.
- D-023: Multi-entry Investigation creation.
- D-024: Chart-first Run layout.
- D-025: Encounter-first Context Rail.
- D-026: Algorithm/System Risk/Inspection Encounter contexts separated.
- D-027: Inspection vs Intervention strictly separated.
- D-028: Analyze centered on synchronized diagnostic timeline.
- D-029: Evidence-first failure localization; no automatic root-cause claim.

### D-030 — D-036: Case/Test Engineering

- D-030: Hybrid Case Designer: Parameter + Chart + Advanced definition.
- D-031: Test Case = executable test specification.
- D-032: Scenario Family/Template distinct from Concrete Case.
- D-033: Draft → immutable Published Case Version.
- D-034: Multi-level Case Qualification distinct from algorithm verdict.
- D-035: Real bug creates exact reproduction + curated Regression Case.
- D-036: Regression tiers CORE/EXTENDED/ON-DEMAND; V1 fully implements CORE.

### D-037 — D-043: Run/Evidence model

- D-037: Run is immutable execution record; execution status distinct from verdict.
- D-038: Mandatory Core Evidence + versioned Evidence Capture Profiles.
- D-039: Replay and Reproduce are distinct operations.
- D-040: Reproduction Fidelity defined.
- D-041: Evidence Manifest + Run sealing.
- D-042: Evaluation is versioned interpretation, not mutable Run fact.
- D-043: Portable Evidence Bundle fully implemented in V1.

### D-044 — D-050: Algorithm/ADP foundation

- D-044: Algorithm Manifest + Runtime Verification; declared vs verified separated.
- D-045: Algorithm identity = Definition → Implementation Artifact → ADP.
- D-046: Workbench Experiment Override → Candidate → ADP promotion.
- D-047: Dirty source allowed for Development but not formal baseline/promotion.
- D-048: Core diagnostics + typed extension channels.
- D-049: Validation maturity truth = Evidence-Derived Capability Matrix.
- D-050: Capability evidence uses impact-driven invalidation/reuse.

### D-051 — D-057: CORE semantics and CI

- D-051: CORE Suite = immutable versioned manifest.
- D-052: Suite Execution Completeness separated from Regression Verdict.
- D-053: Flaky CORE tests require Stability Qualification/Quarantine.
- D-054: Isolated parallel execution + versioned resource policy.
- D-055: Every merge runs full CORE; impact can only add.
- D-056: Gate early, execute to completion.
- D-057: Stable GitHub Required Check + internal Case matrix.

### D-058 — D-063: Runs workface

- D-058: Unified Run Explorer + Saved Views.
- D-059: Run Detail = immutable record + read-only inspection.
- D-060: Verdict-aware landing with stable structure.
- D-061: Live/Replay share Observation Surface; Historical mode explicit.
- D-062: Original Verdict fixed; re-evaluations derived.
- D-063: Manifest-centric Evidence Explorer synchronized with Replay.

### D-064 — D-069: Cases workface

- D-064: Requirement-centered Case Library.
- D-065: Chart-centered executable Case Designer + Qualification Rail.
- D-066: Declarative Behavior Contract + Evaluation binding.
- D-067: Immutable Template version + snapshot instantiation + explicit rebase.
- D-068: Draft/Ephemeral execution allowed for Development only.
- D-069: Published Case uses lifecycle/supersession instead of deletion.

### D-070 — D-076: Evaluation/Requirements

- D-070: Versioned Engineering Requirement Catalog.
- D-071: Applicability and Compliance separated.
- D-072: Intrinsic Criticality + Profile Enforcement Policy.
- D-073: Evaluation uses Completeness + Compliance dual axes.
- D-074: Evaluator Definition + Implementation Artifact identity.
- D-075: Evaluation Profile Qualification Suite.
- D-076: Coverage Contract + Evidence-Derived Coverage Matrix.

### D-077 — D-082: Compare and Agent workflow

- D-077: Change-aware Run Pair + Comparison Contract.
- D-078: Dual-time alignment: absolute + semantic event.
- D-079: Structured Fix Verification Record.
- D-080: Versioned immutable Debug Handoff.
- D-081: Agent Change Contract with protected validation assets.
- D-082: Structured Agent Result + platform re-verification.

### D-083 — D-088: Algorithms UI/integration

- D-083: Algorithm Catalog + evidence-derived readiness summary.
- D-084: Algorithm layer cannot create cross-ADP mixed grade.
- D-085: Evidence-first Capability Cell.
- D-086: Compatibility contract separated from validation coverage.
- D-087: Published ADP immutable; edit through Candidate Revision.
- D-088: Manifest-driven Algorithm Integration Workspace.

### D-089 — D-094: Regression control/governance

- D-089: Regression homepage is Gate-centered control center.
- D-090: Fast Merge binds versioned Protected Regression Baseline Set.
- D-091: Baseline replacement requires Baseline Transition Proposal.
- D-092: Formal Fast Merge generates immutable Gate Attestation.
- D-093: Merge Waiver changes merge decision, never Gate verdict.
- D-094: CORE Suite changes require Suite Change Proposal + Protection Diff.

### D-095 — D-100: Global application UX

- D-095: Explicit scoped context; no silent inheritance.
- D-096: Global Object Navigator + Canonical Deep Links.
- D-097: Layered Attention Model.
- D-098: Risk-tiered Action Model.
- D-099: Workflow mode context-derived, no global mode switch.
- D-100: Desktop/large-screen-first responsive strategy.

### D-101 — D-106: OpenBridge design system

- D-101: OpenBridge-native first across the product.
- D-102: Component reuse priority and thin adapter layer.
- D-103: OpenBridge Tokens are visual source of truth.
- D-104: OpenBridge dual theme, Dark as V1 primary baseline.
- D-105: Semantic Color Budget + neutral-by-default.
- D-106: Documented extensions only + OpenBridge Conformance Policy.

### D-107 — D-112: Layout system

- D-107: Compact App Rail + Engineering Context Ribbon.
- D-108: Local Header + Tabs + Contextual Drawers.
- D-109: Five reusable task-oriented layout templates.
- D-110: Mode-aware adaptive Rails with Canvas priority.
- D-111: Layout-specific scroll contracts + one dominant scroll owner.
- D-112: Curated Layout Presets + limited personalization.

### D-113 — D-118: Workbench detailed UX

- D-113: Lifecycle-aware Investigation resume.
- D-114: Execution Clock and Inspection Cursor separated.
- D-115: Workflow-specific Execution Control Policy.
- D-116: Encounter Focus Stack for Algorithm/System/Inspection contexts.
- D-117: Trajectory Semantic Layers + progressive disclosure.
- D-118: Typed multi-lane Event Timeline.

### D-119 — D-124: Case Designer detailed UX

- D-119: Encounter-centric authoring + deterministic Geometry Compiler.
- D-120: Versioned Traffic Actor Behavior Contract.
- D-121: Case Condition Contract + versioned Condition Profiles.
- D-122: Encounter Intent Graph + Derived Encounter Graph for multi-ship.
- D-123: Event-relative Test Phase Contract + resolved Run windows.
- D-124: Algorithm-neutral Scenario Qualification Preview before Publish.

### D-125 — D-130: Runs detailed UX

- D-125: Evidence-aware dense Run table.
- D-126: Explicit Query State + URL/deep-link serialization + Saved Views.
- D-127: Flat Run Catalog + formal ExecutionGroup + optional grouping.
- D-128: Semantic lineage path + expandable provenance graph.
- D-129: Original Verdict separated from Current Evidence Trust/Claim Eligibility.
- D-130: Stable Core Run Summary + Profile/Diagnostic extensions.

### D-131 — D-136: Algorithm/runtime/assurance architecture

- D-131: Algorithm generic entry lands on Algorithm Overview; ADP scope explicit.
- D-132: Git/worktree Workspace Registry + frozen source snapshot.
- D-133: Control Plane + isolated Run Worker + pluggable Algorithm Runtime.
- D-134: Shared Assurance Engine + multiple frontends.
- D-135: Qualified Execution Environment Profiles.
- D-136: Two-level performance assurance.

### D-137 — D-141: Persistence, telemetry, deployment and reproducibility

- D-137: Relational Metadata + Content-Addressed Artifact Store.
- D-138: Canonical Observation/Event model powers Live/Evidence/Replay.
- D-139: Local-first Engineering Workstation; architecture server-ready.
- D-140: Versioned Reproducibility Contract + Determinism Classes.
- D-141: Read-old/write-current + non-destructive historical projection migration.

### D-142 — D-144: Final V1 scope and acceptance

- D-142: V1 Production Core = Development + Core Regression; V2+ boundaries frozen.
- D-143: Clean Web/API cutover; preserve/characterize/adapt simulation core.
- D-144: Evidence-Backed V1 Acceptance Gate is the formal Definition of Done.

## 28. Final V1 product statement

V1 is complete when a COLAV engineer can use an OpenBridge-native Web workbench to move from a real algorithm failure to exact reproduction, evidence-backed diagnosis, coding-agent handoff, controlled before/after verification, permanent regression protection and an enforced GitHub merge gate — with immutable, reproducible and inspectable evidence throughout the entire chain.
