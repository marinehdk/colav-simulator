# Colav-Simulator V1 Implementation Plan

> **Source of truth:** `Design/Colav-Simulator-V1-PRD.md`  
> **UI companion:** `Design/Colav-Simulator-V1-UI-Spec.md`  
> **Delivery model:** worktree-first, incremental full-stack cutover  
> **V1 scope:** Development + Core Regression  
> **Last updated:** 2026-08-19

## 1. Purpose

This document defines a practical implementation sequence for the V1 redesign. It is intentionally ordered to prevent a visually complete Web UI from being built on top of an untrustworthy session/evidence model.

The implementation strategy is:

```text
Characterize existing simulation core
        ↓
Build domain/evidence/runtime foundation
        ↓
Build OpenBridge application shell
        ↓
Connect Cases / Algorithms / Runs
        ↓
Build Workbench Golden Workflow
        ↓
Build CORE Regression / GitHub Gate
        ↓
Evidence-backed V1 acceptance
        ↓
Retire legacy Web truth
```

## 2. Non-negotiable implementation constraints

1. Do not implement a second simulation truth in the frontend.
2. Do not make historical evidence mutable.
3. Do not allow page-local state to become hidden execution context.
4. Do not build separate regression logic in Web, CLI and GitHub Actions.
5. Do not rewrite functioning simulation/algorithm computation merely to enable UI refactoring unless characterization evidence demonstrates a required change.
6. Do not use Agent self-reported test success as formal Fix Verification.
7. Do not build Formal Validation/Release/MASS workflows into V1 navigation.
8. Prefer OpenBridge Web Components/tokens before custom primitives.
9. Do not merge implementation to `main` until the applicable milestone acceptance tests pass.

## 3. Recommended worktree/branch strategy

Use one integration worktree/branch for the redesign, with smaller topic branches/worktrees where useful.

Conceptual structure:

```text
main
  │
  └─ feature/colav-v1-workbench
       ├─ domain/evidence-foundation
       ├─ run-worker
       ├─ openbridge-shell
       ├─ cases
       ├─ algorithms
       ├─ workbench
       ├─ regression
       └─ acceptance-cutover
```

Do not make `main` the experimentation workspace. SourceWorkspace/dirty-snapshot behavior should itself be developed and validated in a dedicated worktree.

## 4. Target architecture

```text
┌─────────────────────────────────────────────────────────────┐
│ OpenBridge Web Application                                  │
│ Workbench | Cases | Runs | Algorithms | Regression          │
└───────────────────────────────┬─────────────────────────────┘
                                │ Application API / stream
┌───────────────────────────────▼─────────────────────────────┐
│ CONTROL PLANE                                               │
│ FastAPI                                                     │
│                                                             │
│ Domain/Application Services                                 │
│ ├─ InvestigationService                                     │
│ ├─ CaseService                                              │
│ ├─ Algorithm/ADPService                                     │
│ ├─ SourceWorkspaceService                                   │
│ ├─ RunOrchestrator                                          │
│ ├─ EvidenceService                                          │
│ └─ Regression/AssuranceService                              │
│                                                             │
│ Shared Assurance Engine                                     │
└──────────────┬─────────────────────────┬────────────────────┘
               │                         │
               ▼                         ▼
      Isolated Run Workers       Metadata / Artifact Stores
               │                 SQLite + local CAS (V1)
               ▼
 Canonical Observation/Event Model
               │
        ┌──────┼────────┐
        ▼      ▼        ▼
      Stream  Evidence  Evaluation
```

## 5. Proposed module boundaries

Exact Python/package names may be adapted to repository conventions, but the following boundaries should be explicit.

### 5.1 Domain

Pure domain objects, state machines, policies and invariants. Avoid FastAPI/filesystem/process details.

Suggested concepts:

```text
Investigation
Requirement
ScenarioFamily
TestCase / CaseVersion
TrafficActorBehavior
ConditionProfile
TestPhaseContract
Run / RunSpec
ExecutionGroup
EvidenceManifest
EvaluationRecord
AlgorithmDefinition
ImplementationArtifact
ADP
EvaluationProfile
RegressionSuite
ProtectedBaselineSet
GateAttestation
DebugHandoff
AgentResult
LineageEdge
AttentionItem
```

### 5.2 Application services

Use-case orchestration around domain objects.

### 5.3 Infrastructure adapters

```text
SqliteMetadataRepository
LocalContentAddressedArtifactStore
GitSourceWorkspaceAdapter
LocalProcessWorkerRuntime
FastAPI transport adapters
Web event/stream adapter
```

### 5.4 Simulation adapters

Bridge the existing verified simulation/COLAV core into the new Run Worker without forcing the core to know about Web/domain storage details.

### 5.5 Assurance engine

Reusable from:

```text
Web
CLI
GitHub Actions
```

It owns formal Suite/Baseline resolution, Preflight, aggregation and Gate Attestation semantics.

## 6. Milestone 0 — Baseline characterization and safety net

### Goal

Establish evidence of current computational behavior before full-stack cutover.

### Tasks

- Identify representative currently runnable algorithms.
- Select representative scenarios for head-on, crossing, overtaking and basic multi-ship.
- Capture current input/output behavior and key metrics.
- Document current dependencies, runtime and known fallbacks.
- Add/strengthen characterization tests around the simulation closed loop.
- Identify which current Web/session behavior can be retired versus which simulation behavior must be preserved.
- Record existing scenario/config import needs.

### Deliverables

```text
Characterization case list
Representative baseline outputs
Core simulation adapter boundary proposal
Legacy Web/API retirement inventory
Known numerical/behavioral tolerances
```

### Exit criteria

- At least one MPC and one non-MPC path can be characterized.
- Four encounter types have a baseline execution path or an explicitly documented current limitation.
- Refactoring safety tests exist for the core loop.

## 7. Milestone 1 — Domain model and persistence foundation

### Goal

Implement stable identities and immutable/versioned object semantics before new UI workflows.

### Tasks

- Add domain IDs/version identity conventions.
- Implement metadata schema and migrations.
- Implement Local CAS with SHA-256 addressing.
- Implement artifact inventory/provenance records.
- Implement LineageEdge model.
- Implement Published/Sealed immutability guards.
- Implement current-trust/impact state separately from historical verdict.
- Implement import/export-friendly JSON/YAML serializers where required.

### Initial metadata tables/entities

At minimum:

```text
investigations
requirements
scenario_families
case_versions
condition_profiles
algorithm_definitions
implementation_artifacts
adps
runs
execution_groups
evaluation_profiles
evaluation_records
evidence_manifests
artifacts
regression_suites
protected_baseline_sets
gate_attestations
lineage_edges
attention_items
```

### Exit criteria

- Immutable objects cannot be silently edited.
- CAS deduplicates identical artifacts and verifies digest.
- Run/Case/ADP/Evaluation/Gate IDs survive restart.
- Metadata can reference artifacts without embedding large telemetry blobs.

## 8. Milestone 2 — Source Workspace and Run Worker foundation

### Goal

Create the new execution boundary while preserving the existing computational core.

### Tasks

- Implement Git/worktree SourceWorkspace discovery.
- Resolve clean/dirty status, HEAD/base commit and changed/untracked relevant source files.
- Freeze an Ephemeral Source Snapshot before Development Run.
- Implement `AlgorithmRuntimeAdapter` abstraction.
- Implement `InWorkerPythonRuntime` as V1 default.
- Implement isolated local Run Worker process.
- Adapt existing Simulator closed loop into the Worker.
- Capture worker exit/exception/crash state.
- Preserve partial evidence after abnormal termination where possible.

### Exit criteria

- A dirty worktree can run without committing first.
- Two Runs made from different dirty states have distinct source identities.
- Subsequent file changes do not change historical Run identity.
- A controlled worker crash does not terminate FastAPI/control-plane process.

## 9. Milestone 3 — Canonical Observation/Event and Evidence pipeline

### Goal

Unify Live, Replay and Analyze on one data/evidence model.

### Tasks

- Define versioned core observation schemas.
- Define typed event schema supporting Point/Interval/Transition.
- Add core diagnostic schema.
- Implement Evidence Capture Profiles.
- Implement Evidence Writer in/adjacent to Run Worker independent of browser connection.
- Implement live stream projection.
- Implement sealed Evidence Manifest.
- Implement historical readers/projections.
- Implement `Read-Old / Write-Current` reader registry.
- Implement detailed-artifact references for large diagnostics.

### Exit criteria

- Browser disconnect/reconnect does not cause formal evidence loss.
- Live and Replay render the same recorded states/events for a completed Run.
- A sealed Run cannot have its evidence artifacts overwritten.
- Missing/unavailable/corrupt evidence states are distinguishable.

## 10. Milestone 4 — OpenBridge application foundation

### Goal

Build reusable UI infrastructure before feature-specific bespoke screens.

### Tasks

- Pin and document the OpenBridge dependency/catalog version used by implementation.
- Build COLAV OpenBridge adapter layer.
- Build semantic token aliases.
- Build Dark primary theme and Light/System mapping.
- Implement Compact App Rail.
- Implement Engineering Context Ribbon.
- Implement Local Header/Tabs/Drawer primitives.
- Implement Object Navigator.
- Implement Attention Center.
- Implement five reusable Layout Primitives.
- Establish OpenBridge Conformance Matrix process.

### Exit criteria

- No P0 foundation component relies on undocumented OpenBridge internals.
- 1440×900 and 1920×1080 shell layouts pass design review.
- Presentation state and execution context are technically separated.

## 11. Milestone 5 — Requirements, Cases and Qualification

### Goal

Replace scenario-as-config thinking with executable Test Engineering.

### Tasks

- Implement Engineering Requirement catalog and versioning.
- Implement Scenario Family/Template.
- Implement Concrete Case Draft/Published lifecycle.
- Implement Encounter-centric authoring model.
- Implement deterministic Geometry Compiler with identity/version.
- Implement Exact State mode conversion.
- Implement Traffic Actor Behavior Contract.
- Implement Condition Profiles/Condition Contract.
- Implement multi-ship Encounter Intent Graph.
- Implement Event-relative Test Phase Contract.
- Implement Expected Behavior Contract + Evaluation binding.
- Implement L1–L4 qualification.
- Implement Algorithm-neutral Scenario Qualification Preview.
- Implement Case lifecycle/supersession/invalidation impact hooks.

### Exit criteria

- Head-on, crossing, overtaking and basic multi-ship cases can be authored and qualified.
- Published Case is immutable and reproducible.
- Qualification Preview clearly states algorithm capability is not evaluated.
- Template revision does not mutate existing case versions.

## 12. Milestone 6 — Algorithms, manifests, ADPs and integration

### Goal

Make algorithm integration explicit and algorithm-agnostic.

### Tasks

- Implement Algorithm Definition/Manifest registry.
- Implement contract/runtime/smoke verification.
- Implement core diagnostics requirement.
- Implement typed diagnostic extension registry.
- Implement Implementation Artifact registration.
- Implement ADP Published/Candidate model.
- Implement Experiment Overrides in Investigation.
- Implement Compatibility Contract/Preflight.
- Implement staged Integration Workspace.
- Implement initial Capability Matrix projection, with no manual grade mutation.
- Implement Validation Impact hooks.

### Exit criteria

- One MPC and one non-MPC algorithm complete the integration workflow.
- `RUNTIME_READY` is visibly distinct from `VERIFIED`.
- A candidate ADP change produces structured Diff and Impact state.
- A technically compatible but unverified condition can run in Development with correct warning/claim eligibility.

## 13. Milestone 7 — Evaluation engine foundation

### Goal

Provide one versioned, testable evaluation system for Development/Fix/CORE.

### Tasks

- Implement Requirement Applicability/Compliance two-stage result.
- Implement intrinsic criticality vs profile enforcement.
- Implement Evaluation Completeness + Compliance aggregation.
- Implement Evaluator Definition/Implementation identity.
- Implement Published Evaluation Profile immutability.
- Implement Profile Qualification Suite.
- Implement Golden Evidence Fixtures.
- Implement Previous Profile Verdict Diff.
- Implement Coverage Contract/Matrix projection.
- Implement re-evaluation from sealed evidence with evidence sufficiency checks.

### Exit criteria

- `NOT_APPLICABLE`, `INDETERMINATE`, missing evidence and FAIL produce distinct outcomes.
- Published profile behavior cannot change because evaluator code changed underneath it.
- Re-evaluation never overwrites Original Evaluation.

## 14. Milestone 8 — Runs and Evidence Workface

### Goal

Make immutable execution history fully inspectable before advanced debugging UI depends on it.

### Tasks

- Implement Run Explorer dense table.
- Implement explicit query/deep-link state and Saved Views.
- Implement ExecutionGroup UI.
- Implement Run Detail verdict-aware landing.
- Implement Historical Replay.
- Implement Evaluations history/diff.
- Implement Manifest-centric Evidence Explorer.
- Implement Current Evidence Trust / Claim Eligibility.
- Implement Semantic Lineage Path and local Provenance Graph.
- Implement Portable Evidence Bundle export/import.

### Exit criteria

- A Run can be found by ID and opened through a canonical deep link.
- `FINISHED+FAIL` and `CRASHED+NOT_ESTABLISHED` are not conflated.
- Export/import preserves digests, source identity and original verdict.
- Historical Replay does not execute the current Simulator.

## 15. Milestone 9 — Workbench Run / Analyze

### Goal

Deliver the core developer investigation experience.

### Tasks

- Implement Workbench Home/resume.
- Implement Investigation lifecycle.
- Implement Baseline + Run Overrides.
- Implement Preflight.
- Implement Run spatial workspace.
- Implement Execution Clock vs Inspection Cursor.
- Implement interactive Development execution controls as typed events.
- Implement Encounter Focus Stack.
- Implement trajectory semantic layers.
- Implement Analyze multi-lane timeline.
- Implement Failure Window and first-abnormal-transition lead.
- Implement Finding/Hypothesis separation.

### Exit criteria

- User can start from a failed Run and enter Analyze at relevant timestamp.
- Scrubbing does not silently pause or mutate the simulator.
- Planner/System Risk/Inspection encounter contexts can diverge without ambiguity.
- Timeline selection synchronizes chart/context/evidence.

## 16. Milestone 10 — Compare, Fix Verification and Agent handoff

### Goal

Close the engineering loop from diagnosis to verified candidate fix.

### Tasks

- Implement immutable Debug Handoff versioning.
- Implement Markdown + JSON export.
- Implement Agent Change Contract templates.
- Implement Agent Result import/validation.
- Implement Compare Run Pair selection.
- Implement Comparison Contract and Fidelity.
- Implement absolute + semantic event alignment.
- Implement outcome/requirement/metric/event/diagnostic diff.
- Implement Fix Verification Record.
- Implement Regression Case curation/promotion.

### Exit criteria

- `FAIL → PASS` is insufficient by itself to produce FIX_VERIFIED.
- Protected validation asset modifications are detected in Algorithm-fix task context.
- Candidate source can be traced from Debug Handoff/Agent Result to verification Run.

## 17. Milestone 11 — CORE Regression and Shared Assurance Engine

### Goal

Make regression a formal, stable and reusable assurance capability.

### Tasks

- Implement versioned Core Regression Suite Manifest.
- Implement Stability Qualification and Quarantine.
- Implement D0–D3 Reproducibility Contract support.
- Implement isolated parallel suite execution.
- Implement Suite Execution Completeness/Regression Verdict.
- Implement Gate Early / Execute to Completion.
- Implement Protected Regression Baseline Set.
- Implement Regression Gate Attestation.
- Implement Regression Control Center.
- Implement Suite Change Proposal/Protection Diff.
- Implement Baseline Transition.
- Implement Merge Waiver/Remediation.
- Expose Assurance Engine through Web and CLI adapters.

### Exit criteria

- Full CORE is mandatory; impact-selected tests can only add.
- Flaky test cannot be retried into green.
- One worker crash yields Suite INCOMPLETE without erasing other evidence.
- Targeted CORE and Fast Merge Gate are visibly distinct.

## 18. Milestone 12 — Qualified environment and GitHub Gate

### Goal

Turn regression from local feature into enforceable merge protection.

### Tasks

- Define initial `ExecutionEnvironmentProfile` for CI reference.
- Pin dependency/solver/runtime identity.
- Qualify environment with smoke/golden/core comparisons.
- Add stable GitHub checks:

```text
quality/lint
quality/unit-tests
colav/core-regression
```

- Configure branch protection/ruleset so required checks actually block merge.
- Run Shared Assurance Engine via CI frontend/CLI.
- Upload/retain regression summary and evidence indices/artifacts as practical.
- Link GitHub check to immutable Gate Attestation identity.
- Add runtime sanity + significant performance regression guard.

### Exit criteria

- Intentional regression blocks a real PR.
- Known-good change passes.
- Gate result can be traced to exact source, environment, suite, Runs and Evidence.
- CI failure/incomplete is distinguishable from behavioral algorithm failure.

## 19. Milestone 13 — V1 acceptance and Web cutover

### Goal

Prove the product itself meets D-144 and retire the legacy Web truth.

### Acceptance scenarios

#### A. Golden Workflow

Complete one real representative defect end-to-end through Investigation CLOSED.

#### B. Four Encounter Baselines

Head-on, crossing, overtaking and basic multi-ship each have qualified Case → Run → sealed Evidence → Evaluation → Replay.

#### C. Multi-algorithm integration

At least one MPC and one non-MPC path complete integration and Development Run.

#### D. Evidence portability

Export/import a sealed Run bundle in an isolated registration context and verify digest/verdict/source identity.

#### E. GitHub Gate

Demonstrate both pass and intentionally blocked PR.

#### F. Crash/Incomplete

Inject worker/solver/evidence failure; preserve partial evidence and block gate correctly.

#### G. Reproducibility

Representative CORE Case reaches D3 GATE_STABLE.

#### H. OpenBridge conformance

Review P0 screens and component matrix; eliminate/document exceptions.

### Cutover criteria

Only after acceptance:

- make new Web the active engineering interface;
- retire legacy session/Web execution truth;
- retain adapters/imports only where they provide explicit migration value.

## 20. Suggested delivery epics

For issue/project tracking, milestones can be grouped into epics:

```text
EPIC-01  V1 Domain & Evidence Foundation
EPIC-02  Run Worker & Source Workspace
EPIC-03  Canonical Telemetry / Replay
EPIC-04  OpenBridge Application Foundation
EPIC-05  Case/Test Engineering
EPIC-06  Algorithm Integration & ADP
EPIC-07  Evaluation & Coverage
EPIC-08  Runs & Evidence UI
EPIC-09  Workbench Run/Analyze
EPIC-10  Compare / Agent / Fix Verification
EPIC-11  Core Regression & Assurance
EPIC-12  GitHub Gate / Qualified Environment
EPIC-13  V1 Acceptance & Cutover
```

Each implementation issue should cite relevant PRD IDs.

Example:

```text
Title: Implement Event-Synchronized Analyze Timeline

PRD:
- WB-011
- WB-012
- ARCH-004

UI:
- UI Spec §14.8

Acceptance:
- Timeline event selection updates shared Inspection Cursor
- Observed event and Evaluation Finding use distinct semantics
- First abnormal transition is labeled lead, not root cause
```

## 21. Testing strategy

### 21.1 Unit tests

Domain invariants, state machines, aggregation policies, serializers, schema adapters, impact/eligibility policies.

### 21.2 Contract tests

- Algorithm input/output contracts.
- Diagnostic channel schemas.
- Evaluator schemas.
- Evidence artifact schemas.
- Canonical observation/event schemas.
- OpenBridge adapter event/prop behavior where useful.

### 21.3 Characterization tests

Protect existing simulation behavior while adapters and application layers change.

### 21.4 Integration tests

Run Worker closed loop, source snapshot, evidence writer, database/CAS, replay reader, evaluation and lineage.

### 21.5 Golden Evidence tests

Profile/evaluator qualification independent of current algorithms.

### 21.6 End-to-end tests

Golden Workflow, Case qualification, evidence portability, regression suite and GitHub gate.

### 21.7 Fault-injection tests

Worker crash, solver timeout, missing evidence, corrupted artifact, schema mismatch, browser disconnect.

### 21.8 Stability tests

Repeated identical CORE execution checked against Reproducibility Contract/D3 policy.

## 22. Data migration strategy

### Legacy scenario/config

Use explicit import adapters to create Draft Cases/Condition Profiles. Imported assets must pass new qualification before publication.

### Legacy algorithm integrations

Prefer thin adapters around existing algorithms. Do not mark runtime-ready or verified until new integration checks pass.

### Legacy Web sessions

Do not migrate mutable session state as new Run evidence unless exact identity/evidence is available. Treat old session exports as imported/legacy artifacts where appropriate.

### Legacy evaluation

The existing reconstructed evaluator may be represented with explicit implementation identity and reproduction limitations; do not silently relabel it as official/certification evaluator.

## 23. Environment strategy

### Development

Allow local compatible/unqualified environments for rapid edit/reproduce/debug with explicit eligibility limits.

### Fast Merge

Require a versioned Qualified Reference Environment.

### Future strict performance

Use a separate qualified performance benchmark environment rather than overloading ordinary CI timing.

## 24. Reproducibility implementation guidance

Implement a Random Stream Registry derived from a Run root seed:

```text
scenario
sensor_noise
tracker
traffic_actor
algorithm
```

Avoid one shared mutable RNG stream across subsystems.

Store resolved stream identities in RunSpec/evidence.

D3 Gate-Stable should compare semantic stability and configured metric/event tolerances, not require universal byte-identical floating-point artifacts.

## 25. OpenBridge implementation sequence

1. Pin OpenBridge package/component catalog version.
2. Inventory required V1 primitives.
3. Mark each UI need as OB-NATIVE/COMPOSED/WRAPPED/EXTENSION/EXCEPTION.
4. Build thin framework adapters only where useful.
5. Map COLAV semantic tokens to OpenBridge tokens.
6. Implement global shell/layouts.
7. Build domain extensions such as Capability Matrix, Timeline, Evidence Explorer.
8. Maintain Conformance Matrix in code review.
9. Treat Custom Exception count as a design debt metric.

## 26. Suggested frontend architecture rules

- Domain data arrives through typed application API/projection models.
- Do not parse raw CAS artifacts directly in arbitrary React/Web components.
- Shared Observation Surface must be reused across Live and Replay.
- Investigation task context and UI presentation stores are separate.
- URL query/deep links may store inspection/query state but not hidden RunSpec state.
- OpenBridge wrappers should be thin and centralized.
- Domain-specific status components shall require explicit semantic namespace (operational vs assurance) where ambiguity is possible.

## 27. Suggested backend architecture rules

- Domain layer has no FastAPI request objects or filesystem paths.
- Run Worker owns execution, not browser sessions.
- Browser disconnect does not stop/evaluate/delete a Run unless an explicit user action reaches the worker policy.
- Evidence sealing happens server/worker-side.
- Git worktree source is snapshotted before Run execution.
- Formal evaluation references immutable evaluator/profile identities.
- Assurance Engine is callable without Web.
- Gate Attestation is created from formal execution evidence, not from UI state.

## 28. CI migration plan

Current lint/unit workflow should be preserved while new regression checks are introduced incrementally.

Recommended progression:

```text
Stage A
Existing lint + pytest continue

Stage B
Add non-required colav/core-regression preview

Stage C
Stabilize D3 CORE and evidence artifacts

Stage D
Enable branch protection required checks

Stage E
Add Protected Baseline Set and formal Attestation
```

Do not enable a flaky gate as required and then normalize manual reruns/bypasses; stabilize it first.

## 29. Risk register

### R-01 — Scope inflation into Formal Validation

Mitigation: keep five V1 workfaces and D-142 scope boundary.

### R-02 — UI-first build creates second truth

Mitigation: implement milestones 1–3 before complex Workbench UI.

### R-03 — Simulation core accidentally changes during refactor

Mitigation: M0 characterization and adapter-first migration.

### R-04 — OpenBridge wrappers become a private design system

Mitigation: conformance classification and documented extension policy.

### R-05 — Solver/native crash destabilizes Web

Mitigation: isolated Run Worker boundary.

### R-06 — Evidence storage grows rapidly

Mitigation: CAS, content deduplication, capture profiles and detailed-artifact references.

### R-07 — Regression becomes flaky

Mitigation: D3 contract, stability qualification and quarantine; no retry-to-green.

### R-08 — Gate passes by weakening tests

Mitigation: immutable published suites, Suite Change Proposal, Protection Diff, protected baseline governance.

### R-09 — Agent changes test/evaluator to get green

Mitigation: Agent Change Contract and protected asset checks.

### R-10 — Historical data breaks after schema change

Mitigation: Read-Old/Write-Current readers and non-destructive derived projections.

## 30. Implementation completion rule

A milestone is not complete merely because its page exists. Each milestone must provide evidence that the corresponding domain invariants and PRD acceptance criteria are exercised.

The final V1 completion authority is the Evidence-Backed V1 Acceptance Gate in `Colav-Simulator-V1-PRD.md`, not visual feature count.
