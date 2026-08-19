# Colav-Simulator V1 Implementation Plan

> **Source of truth:** `Design/Colav-Simulator-V1-PRD.md`  
> **UI companion:** `Design/Colav-Simulator-V1-UI-Spec.md`  
> **Review record:** `Design/Colav-Simulator-V1-PRD-Review.md`  
> **Delivery model:** worktree-first, incremental full-stack cutover  
> **V1 scope:** Development + Core Regression  
> **Last updated:** 2026-08-19

## 1. Purpose

This document defines the practical V1 implementation sequence. It is intentionally ordered to prevent a visually complete Web UI from being built on an untrustworthy source/evidence/session model.

```text
Freeze exact current source baseline
        ↓
Characterize simulation core
        ↓
Build domain / persistence / source identity
        ↓
Build isolated Run Worker + evidence pipeline
        ↓
Select frontend host stack + pin OpenBridge provenance
        ↓
Build OpenBridge application shell
        ↓
Build Cases / Algorithms / Evaluation / Runs
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

1. No second simulation truth in frontend.
2. No mutation of SEALED historical evidence or Published immutable assets.
3. No page-local hidden execution context.
4. No separate regression logic in Web, CLI and GitHub Actions.
5. No simulation/core rewrite merely to enable UI refactoring unless exact-ref characterization justifies it.
6. Dirty SourceWorkspace state is not an Implementation Artifact.
7. Agent self-reported tests are not Fix Verification.
8. No Formal Validation/Release/MASS workflow in V1 navigation.
9. Prefer documented OpenBridge components/tokens before custom primitives.
10. Do not adopt an OpenBridge dependency until its exact provenance/license/NOTICE obligations are reviewed.
11. Local-first execution defaults to loopback/local access; browser input cannot become arbitrary filesystem/shell authority.
12. A Run is not SEALED until manifest/artifact references/digests are crash-consistently finalized.
13. Do not merge implementation to `main` until applicable milestone evidence/acceptance passes.

## 3. Worktree / branch strategy

Use one integration worktree/branch for redesign, with smaller topic worktrees where useful.

```text
main
  │
  └─ feature/colav-v1-workbench
       ├─ baseline-characterization
       ├─ domain-persistence
       ├─ source-run-worker
       ├─ evidence-pipeline
       ├─ frontend-adr-openbridge
       ├─ cases-evaluation
       ├─ algorithms-adp
       ├─ runs
       ├─ workbench
       ├─ regression
       └─ acceptance-cutover
```

`main` is not the experimentation workspace. SourceWorkspace/dirty-snapshot behavior is developed/tested in dedicated worktrees.

## 4. Target architecture

```text
┌─────────────────────────────────────────────────────────────┐
│ OpenBridge Web Application                                  │
│ Workbench | Cases | Runs | Algorithms | Regression          │
└───────────────────────────────┬─────────────────────────────┘
                                │ Application API / stream
┌───────────────────────────────▼─────────────────────────────┐
│ CONTROL PLANE                                               │
│ FastAPI + Domain/Application Services                       │
│                                                             │
│ Investigation / Case / Requirement / Evaluation             │
│ Algorithm / ADP / Source Workspace                          │
│ Run Orchestration / Evidence / Regression                   │
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

### 4.1 Source identity chain

```text
SourceWorkspace                 mutable
      ↓ freeze
Ephemeral SourceSnapshot        immutable development identity
      ↓ commit/seal/verify
Implementation Artifact         immutable formal implementation identity
      ↓
Published ADP                   immutable deployment/validation object
```

Published ADP/CORE/Protected Baseline never binds a mutable dirty workspace.

## 5. Module boundaries

### 5.1 Domain

Pure domain objects/state machines/policies; no FastAPI request objects, filesystem paths or subprocess handles.

Authoritative P0 concept catalog:

```text
Investigation
Requirement
ScenarioFamily
CaseVersion
CaseQualificationRecord
ScenarioQualificationPolicy
TrafficActorBehavior
ConditionProfile
TestPhaseContract
SourceWorkspace
SourceSnapshot
AlgorithmDefinition
ImplementationArtifact
ADP
EvidenceCaptureProfile
Run
RunSpec
ExecutionGroup
EvidenceManifest
EvidenceArtifact
EvaluatorDefinition
EvaluatorImplementationArtifact
EvaluationProfile
EvaluationRecord
CoverageContract
ComparisonContract
FixVerificationRecord
DebugHandoff
AgentResult
RegressionSuite
ProtectedBaselineSet
SuiteChangeProposal
BaselineTransitionProposal
MergeWaiver
RemediationObligation
GateAttestation
ExecutionEnvironmentProfile
ReproducibilityContract
LineageEdge
AttentionItem
```

Exact relational normalization may differ, but these first-class identities shall not disappear into unversioned opaque JSON blobs.

### 5.2 Application services

Suggested service boundaries:

```text
InvestigationService
RequirementEvaluationService
CaseService
AlgorithmADPService
SourceWorkspaceService
RunOrchestrator
EvidenceService
AssuranceService
EnvironmentQualificationService
ImpactAnalysisService
```

### 5.3 Infrastructure adapters

```text
SqliteMetadataRepository
LocalContentAddressedArtifactStore
GitSourceWorkspaceAdapter
LocalProcessWorkerRuntime
FastAPI transport adapters
Web event/stream adapter
GitHub/CLI adapters
```

### 5.4 Simulation adapters

Bridge the characterized simulation/COLAV core into Run Worker without forcing the core to know Web/domain storage details.

### 5.5 Shared Assurance Engine

Callable by Web, CLI and GitHub Actions. Owns formal Suite/Baseline resolution, Preflight policy, execution aggregation, Evaluation and Gate Attestation semantics.

## 6. Milestone 0 — Exact-ref baseline characterization

### Goal

Establish what current computational behavior is actually being preserved before full-stack cutover.

### Mandatory first deliverable: Baseline Characterization Manifest

Do not use an older Design document/worktree description as the preservation identity. Produce a machine-readable/inspectable manifest containing:

```text
repository
exact branch / worktree
exact commit SHA
clean/dirty state
execution environment / dependency identity
selected algorithms and their roles
selected scenarios
known fallback / dependency / data limitations
characterization evidence references
metric / event tolerances
```

### Tasks

- Verify the live source ref that will be the refactor baseline.
- Identify representative currently runnable algorithms by role.
- Select head-on, crossing, overtaking and basic multi-ship baselines, recording explicit limitation where current source cannot execute one.
- Capture input/output behavior and key events/metrics.
- Document dependencies/runtime/known fallbacks.
- Add/strengthen characterization tests around closed loop.
- Inventory current Web/session features to retire/migrate.
- Record legacy scenario/config import needs.

### Exit criteria

- Baseline Characterization Manifest is immutable/reviewed.
- At least one MPC/dynamic COLAV path and one other representative role/path are characterized where current repository permits.
- Four encounter families have a baseline execution path or explicit current limitation.
- Core refactor safety tests/tolerances exist.

## 7. Milestone 1 — Domain model and persistence foundation

### Goal

Implement stable identities and immutable/versioned semantics before new workflows.

### Tasks

- Domain ID/version conventions.
- SQLite schema + versioned migrations.
- Local CAS with SHA-256 content addressing.
- Artifact inventory/provenance.
- LineageEdge.
- Published/SEALED immutability guards.
- Historical Original Verdict separate from Current Trust/Impact and claim-specific Eligibility.
- JSON/YAML exchange serializers where needed.
- Retention/reachability model.

### Authoritative P0 persistence identity set

The schema/migration plan shall provide durable identities/relations for all P0 objects, including at least:

```text
investigations
requirements
scenario_families
case_versions
case_qualification_records
scenario_qualification_policies
condition_profiles
source_workspaces
source_snapshots
algorithm_definitions
implementation_artifacts
adps
evidence_capture_profiles
runs
execution_groups
evidence_manifests
artifacts
evaluator_definitions
evaluator_implementation_artifacts
evaluation_profiles
evaluation_records
coverage_contracts
comparison_contracts
fix_verification_records
debug_handoffs
agent_results
regression_suites
protected_baseline_sets
suite_change_proposals
baseline_transition_proposals
merge_waivers
remediation_obligations
gate_attestations
execution_environment_profiles
reproducibility_contracts
lineage_edges
attention_items
```

Not necessarily one table per concept; exact normalization is an implementation ADR. Each identity must remain queryable/versioned/auditable.

### CAS/sealing tasks

- SEALED/Published/Attestation-referenced artifacts are protected from automatic GC.
- Cleanup is explicit + reachability-aware + impact-previewed.
- Finalization uses transactional/journaled ordering so Run cannot be marked SEALED before required artifact refs/digests are durable.
- Detect orphan/unfinalized artifacts after crash and allow cleanup/recovery without mutating sealed history.

### Exit criteria

- Immutable objects cannot be silently edited.
- CAS deduplicates identical artifacts and verifies digest.
- Critical IDs survive restart/migration.
- Large telemetry is referenced, not embedded in metadata tables.
- Fault test proves premature SEALED state cannot occur.
- Cleanup cannot delete retained SEALED/Gate evidence.

## 8. Milestone 2 — Source Workspace and isolated Run Worker

### Goal

Create correct source/execution boundary while preserving characterized core.

### Tasks

- SourceWorkspace registration/discovery for approved repositories/worktrees.
- Resolve HEAD/base commit, clean/dirty state, changed and relevant untracked files.
- Freeze EphemeralSourceSnapshot before Development/Reproduction execution.
- Implement formal ImplementationArtifact registration separately from SourceSnapshot.
- Implement `AlgorithmRuntimeAdapter`.
- Implement `InWorkerPythonRuntime` V1 default.
- Isolated local Run Worker process.
- Adapt existing Simulator loop.
- Capture worker exit/exception/crash state.
- Preserve partial evidence after abnormal termination where possible.
- Implement purpose-aware RunSpec bindings.

### Required Run purposes

```text
DEVELOPMENT
REPRODUCTION
FIX_VERIFICATION
CASE_QUALIFICATION
INTEGRATION_SMOKE
CORE_REGRESSION
```

Future `FORMAL_VALIDATION` reserved.

### Run state model

Implement orthogonal axes:

```text
Record lifecycle:
CREATED → RUNNING → FINALIZING → SEALED

Execution status:
QUEUED | RUNNING | FINISHED | STOPPED | ABORTED | CRASHED | CANCELLED

Evaluation:
Completeness × Compliance
```

Do not use one generic `status` field for all semantics.

### Exit criteria

- Dirty worktree runs without commit via SourceSnapshot.
- Two dirty states produce distinct immutable snapshots.
- Subsequent edits do not alter historical source identity.
- Published/formal ImplementationArtifact cannot represent dirty mutable source.
- Controlled worker crash does not terminate Control Plane.
- STOPPED/ABORTED/CANCELLED/CRASHED behavior covered by tests.

## 9. Milestone 3 — Canonical Observation/Event and Evidence pipeline

### Goal

Unify Live/Replay/Analyze/Compare on one schema/evidence model.

### Tasks

- Versioned core Observation schemas.
- Typed Event schema supporting Point/Interval/Transition.
- Core algorithm diagnostic schema.
- First-class EvidenceCaptureProfile model.
- Seed V1 profiles:

```text
DEVELOPMENT@1
DIAGNOSTIC@1
REGRESSION@1
```

- Enforce mandatory Core Evidence Floor from PRD.
- Evidence Writer independent of browser connection.
- Live projection/stream adapter.
- SEALED Evidence Manifest.
- Historical readers/projections; `Read-Old / Write-Current` registry.
- Detailed-artifact refs for high-volume diagnostics.
- Explicit `NOT_AVAILABLE / NOT_CAPTURED / MISSING / CORRUPT / SCHEMA_MISMATCH` semantics.

### Exit criteria

- Browser disconnect/reconnect does not cause evidence loss.
- Live and Replay render same recorded states/events for completed Run.
- SEALED artifacts cannot be overwritten.
- Core Evidence Floor verified for each V1 capture profile.
- Missing causes are semantically distinguishable.

## 10. Milestone 4A — Frontend host-stack ADR

### Goal

Prevent Codex/ZCode from guessing the application host architecture.

Current legacy `web_gui` is a static HTML/large JavaScript/CSS implementation. Before new UI coding, create an ADR/spike selecting the V1 host stack using:

- OpenBridge Web Component interoperability;
- typed Domain/Projection models;
- routing/Canonical Deep Links;
- Task Context vs Presentation State separation;
- testing/accessibility/tooling;
- migration from current `web_gui`;
- build/bundle/dependency management;
- local-first deployment constraints.

Candidate options may include native Web Components, TypeScript/Vite, React or other hosts, but no framework is normative before ADR acceptance.

### Exit criteria

- ADR accepted.
- Minimal spike proves selected host can consume pinned OpenBridge component(s), typed API projection and routing/deep link.

## 11. Milestone 4B — OpenBridge dependency/provenance gate and application foundation

### Goal

Pin the exact OpenBridge implementation basis and build reusable UI foundation.

### Dependency/provenance tasks

For the exact selected OpenBridge package/repository/catalog version:

- record source/provenance URL;
- pin exact version/commit;
- verify applicable license(s);
- document attribution/NOTICE obligations;
- record commercial/distribution compatibility decision;
- update `THIRD_PARTY_NOTICES.md`/dependency inventory as required.

Do not infer license from a different OpenBridge artifact or a generic project name.

### UI foundation tasks

- COLAV OpenBridge adapter layer.
- semantic token aliases.
- Dark primary theme + Light/System mapping.
- Compact App Rail.
- Engineering Context Ribbon.
- Local Header/Tabs/Drawer primitives.
- Object Navigator.
- Attention Center.
- Engineering Workspace/Settings surfaces for registered SourceWorkspaces and Execution Environment Profiles.
- five reusable Layout Primitives.
- OpenBridge Conformance Matrix process.

### Exit criteria

- Provenance/license/NOTICE record complete for exact pinned dependency.
- No P0 foundation component relies on undocumented internals.
- 1440×900 and 1920×1080 shell layouts pass review.
- Presentation State and execution context technically separated.

## 12. Milestone 5 — Requirements, Evaluation assets, Cases and Qualification

### Goal

Replace scenario-as-config thinking with executable Test Engineering and create visible owners for Requirement/Evaluation assets.

### Tasks

- Engineering Requirement catalog/versioning.
- Requirement & Evaluation Hub under `Cases > Requirements`.
- Evaluator Definition/Implementation identity.
- Evaluation Profile Draft/Published model.
- Coverage Contract model.
- Golden Evidence Fixture registry.
- Scenario Family/Template.
- Concrete Case Draft/Published lifecycle.
- Encounter-centric authoring.
- deterministic Geometry Compiler identity/version.
- Exact State conversion.
- Traffic Actor Behavior Contract.
- Condition Profiles/Contract.
- multi-ship Encounter Intent Graph.
- Event-relative Test Phase Contract.
- Expected Behavior Contract + Evaluation binding.
- ScenarioQualificationPolicy model.
- L1–L4 qualification + neutral Qualification Preview.
- Case lifecycle/supersession/invalidation impact hooks.

### Exit criteria

- Head-on/crossing/overtaking/basic multi-ship can be authored and qualified or current source limitation is explicitly addressed during migration.
- Published Case immutable/reproducible.
- Qualification evidence binds exact ScenarioQualificationPolicy.
- Preview says Algorithm Capability NOT EVALUATED.
- Template revision does not mutate old Case.
- Requirement/Evaluation/Coverage objects have usable UI routes and durable identities.

## 13. Milestone 6 — Algorithms, roles, manifests, ADPs and integration

### Goal

Make integration explicit and role-aware.

### Tasks

- Algorithm Definition/Manifest registry with `role` as first-class attribute.
- contract/runtime/smoke verification.
- core diagnostics.
- typed diagnostic registry.
- ImplementationArtifact registration from immutable clean source/build identity.
- ADP Published/Candidate model.
- Experiment Overrides.
- Compatibility/Preflight.
- staged Integration Workspace.
- Evidence-Derived Capability Matrix.
- Validation Impact hooks.
- G0–G4 policy/projection implementation:

```text
G0 Discoverable
G1 Short smoke test
G2 Full closed loop
G3 Capability demonstration
G4 Benchmark validation
```

- Role-aware capability applicability/comparison.

### Exit criteria

- One MPC/dynamic COLAV path and one role-compatible non-MPC dynamic COLAV path complete integration if repository readiness permits; where not, limitation is explicit and acceptance fixture selection is adjusted without misrepresenting RRT/tracker as equivalent dynamic COLAV.
- `RUNTIME_READY` distinct from `VERIFIED`.
- Candidate ADP diff/impact visible.
- technically compatible unverified condition can Development Run with claim warning.
- CORE PASS is not automatically assigned G4.

## 14. Milestone 7 — Evaluation engine foundation

### Goal

Provide versioned, testable evaluation for Development/Fix/CORE without overstating current evaluator provenance.

### Tasks

- Requirement Applicability/Compliance result.
- intrinsic criticality vs Profile enforcement.
- Completeness + Compliance aggregation.
- Evaluator Definition/Implementation identity.
- Register current reconstructed evaluator explicitly with repository provenance limitations:

```text
functional_reproduction = true
numerical_reproduction_confirmed = false
```

- Published Evaluation Profile immutability.
- Profile Qualification Suite.
- Golden Evidence Fixtures.
- Previous Profile Verdict Diff.
- Coverage Contract/Matrix.
- re-evaluation from SEALED evidence with sufficiency checks.

### Exit criteria

- NOT_APPLICABLE, INDETERMINATE, missing evidence and FAIL distinct.
- Published Profile cannot change because current evaluator code changes under it.
- Re-evaluation never overwrites Original Evaluation.
- UI/API outputs from reconstructed evaluator cannot imply official/numerical reproduction/certification.

## 15. Milestone 8 — Runs and Evidence Workface

### Goal

Make immutable history inspectable before advanced debugging depends on it.

### Tasks

- Run Explorer dense table.
- query/deep-link state + Saved Views.
- ExecutionGroup UI.
- Run Detail with orthogonal Record/Execution/Evaluation state display.
- Historical Replay.
- Evaluation history/diff.
- Manifest-centric Evidence Explorer.
- Current Evidence Trust/Impact separate from claim-specific Eligibility.
- Semantic Lineage Path/local Provenance Graph.
- Portable Evidence Bundle export/import.

### Exit criteria

- Canonical Deep Link by Run ID.
- `SEALED + FINISHED + FAIL` and `SEALED + CRASHED + NOT_ESTABLISHED` distinct.
- Export/import preserves digests/source/original verdict.
- Replay never executes current Simulator.
- Evidence Trust and claim eligibility not collapsed.

## 16. Milestone 9 — Workbench Run / Analyze

### Goal

Deliver core investigation experience.

### Tasks

- Workbench Home/resume.
- Investigation lifecycle.
- Baseline + Run Overrides.
- purpose-aware Preflight.
- Run spatial workspace.
- Execution Clock vs Inspection Cursor.
- Development execution controls as typed events.
- Encounter Focus Stack.
- trajectory semantic layers using generic `Selected/Accepted Planner Output` plus canonical repository planning terms when available.
- Analyze multi-lane timeline.
- Failure Window/first-abnormal-transition lead.
- Finding/Hypothesis separation.

### Exit criteria

- Failed Run → Analyze relevant timestamp.
- Scrub does not pause/mutate Simulator.
- Algorithm/System Risk/Inspection encounter contexts diverge without ambiguity.
- Timeline synchronizes chart/context/evidence.
- Mission Route/Avoidance Corridor/Rolling Plan terminology is not conflated.

## 17. Milestone 10 — Compare, Fix Verification and Agent handoff

### Goal

Close loop diagnosis → verified candidate fix.

### Tasks

- immutable Debug Handoff versioning.
- Markdown + JSON export.
- Agent Change Contract templates.
- Agent Result import/validation as data, not command authority.
- Compare Run Pair.
- Comparison Contract/Fidelity.
- absolute + semantic event alignment.
- outcome/Requirement/metric/event/diagnostic diff.
- Fix Verification Record.
- Regression Case curation/promotion.

### Exit criteria

- FAIL→PASS insufficient by itself for FIX_VERIFIED.
- Protected validation asset modifications detected.
- Candidate source traced Handoff/Agent Result → SourceSnapshot/ImplementationArtifact → verification Run.

## 18. Milestone 11 — CORE Regression and Shared Assurance Engine

### Goal

Make regression formal/stable/reusable.

### Tasks

- versioned Core Regression Suite.
- every CORE member Stability Qualification.
- D0–D3 Reproducibility Contract.
- isolated parallel execution.
- Suite Execution Completeness/Verdict.
- Gate Early / Execute to Completion.
- candidate supersession/cancellation distinct from Gate Early.
- Protected Regression Baseline Set.
- Gate Attestation.
- Regression Control Center.
- Suite Change Proposal/Protection Diff.
- Baseline Transition.
- Merge Waiver/Remediation.
- Web + CLI Assurance Engine adapters.

### Exit criteria

- Full CORE mandatory; impact only adds.
- Flaky cannot retry-to-green.
- every Published CORE member has current Stability Qualification.
- one worker crash → Suite INCOMPLETE without erasing other evidence.
- Targeted CORE vs Fast Merge distinct.
- superseding new candidate may cancel obsolete orchestration without being confused with stopping remaining mandatory Cases after a failure.

## 19. Milestone 12 — Qualified environment and GitHub Gate

### Goal

Turn local regression into enforceable merge protection.

### Tasks

- initial `ExecutionEnvironmentProfile` for CI reference.
- pin dependency/solver/runtime identity.
- qualify environment with smoke/Golden/Core comparisons.
- stable checks:

```text
quality/lint
quality/unit-tests
colav/core-regression
```

- migrate/map current CI jobs to stable required names without losing existing `ruff`/`pytest` coverage.
- configure branch protection/ruleset.
- run Shared Assurance Engine via CI frontend/CLI.
- upload/retain regression summary/evidence indices/artifacts as practical.
- link Check to immutable Gate Attestation.
- runtime sanity + significant performance regression guard.

### Exit criteria

- intentional regression blocks real PR.
- known-good passes.
- Gate traces exact source/environment/suite/Runs/Evidence.
- CI failure/incomplete distinct from behavioral failure.

## 20. Milestone 13 — V1 acceptance and Web cutover

### Acceptance scenarios

#### A. Golden Workflow

Complete representative real defect end-to-end through Investigation CLOSED.

#### B. Four Encounter Baselines

Head-on/crossing/overtaking/basic multi-ship each have qualified Case → Run → SEALED Evidence → Evaluation → Replay.

#### C. Multi-algorithm integration

At least one MPC and one role-compatible non-MPC dynamic COLAV path where repository readiness permits. Do not substitute static RRT/tracker role evidence as equivalent dynamic COLAV validation.

#### D. Evidence portability

Export/import SEALED Bundle in isolated registration context; verify digest/verdict/source identity.

#### E. GitHub Gate

Demonstrate pass and intentionally blocked PR.

#### F. Crash/Incomplete

Inject worker/solver/evidence failure; preserve partial evidence and block Gate correctly.

#### G. Reproducibility / CORE stability

- Every Published V1 CORE member has current Stability Qualification under applicable Qualified Environment/Reproducibility Contract.
- At least one representative member is repeated end-to-end to demonstrate D3 semantics/tolerances.

#### H. OpenBridge conformance/provenance

Review P0 screens/component matrix; no undocumented internals; exact OpenBridge provenance/license/NOTICE record complete.

#### I. Local security

Loopback default verified; arbitrary browser filesystem/shell execution denied; only registered/policy-resolved workspaces executable.

#### J. CAS/sealing integrity

Fault injection proves no premature SEALED state and no automatic deletion of retained sealed/attestation evidence.

### Cutover criteria

Only after acceptance:

- new Web becomes active engineering interface;
- legacy session/Web execution truth retired;
- adapters/imports retained only for explicit migration value.

## 21. Suggested delivery epics

```text
EPIC-00  Baseline Characterization
EPIC-01  V1 Domain / Persistence / CAS
EPIC-02  Source Workspace & Run Worker
EPIC-03  Canonical Telemetry / Evidence / Replay
EPIC-04  Frontend ADR & OpenBridge Foundation
EPIC-05  Requirements / Evaluation Assets / Cases
EPIC-06  Algorithm Integration & ADP
EPIC-07  Evaluation & Coverage
EPIC-08  Runs & Evidence UI
EPIC-09  Workbench Run/Analyze
EPIC-10  Compare / Agent / Fix Verification
EPIC-11  Core Regression & Assurance
EPIC-12  GitHub Gate / Qualified Environment
EPIC-13  V1 Acceptance & Cutover
```

Each implementation issue cites PRD IDs and acceptance evidence.

## 22. Testing strategy

### Unit

Domain invariants, state machines, aggregation, serializers, schema adapters, impact/eligibility, retention/reachability.

### Contract

Algorithm I/O, diagnostic channels, Evaluator schemas, Evidence schemas, Observation/Event schemas, OpenBridge adapter behavior.

### Characterization

Protect exact-ref simulation behavior while adapters/application layers change.

### Integration

SourceSnapshot, Run Worker closed loop, Evidence Writer, SQLite/CAS, Replay reader, Evaluation, lineage, sealing.

### Golden Evidence

Profile/Evaluator Qualification independent of current algorithms.

### End-to-end

Golden Workflow, Case Qualification, Evidence portability, Regression Suite/GitHub Gate.

### Fault injection

Worker crash, solver timeout, missing/corrupt artifact, schema mismatch, browser disconnect, finalization crash, orphan artifact recovery.

### Security

Loopback binding, registered-root enforcement, path traversal/arbitrary path rejection, no generic shell-command API, imported Agent Result treated as data.

### Stability

Every CORE member qualification against D3 policy; representative repeated end-to-end fixture.

## 23. Data migration strategy

### Legacy scenario/config

Explicit import adapters → Draft Cases/Condition Profiles; must qualify before Publish.

### Legacy algorithm integrations

Thin adapters around existing algorithms. Runtime-ready/Verified only after new checks.

### Legacy Web sessions

Do not migrate mutable session state as new Run evidence unless exact identity/evidence exists. Treat old exports as legacy/imported artifacts where appropriate.

### Legacy evaluation

Current reconstructed Evaluator gets explicit immutable implementation identity and remains `functional_reproduction` / numerical-not-confirmed. Never silently relabel official/certification evaluator.

## 24. Environment and reproducibility strategy

Development: local compatible/unqualified allowed with explicit eligibility limits.

Fast Merge: versioned Qualified Reference Environment required.

Future strict performance: separate qualified benchmark environment.

Random Stream Registry derived from root seed:

```text
scenario
sensor_noise
tracker
traffic_actor
algorithm
```

Avoid one shared mutable RNG stream. Store resolved stream identities in RunSpec/Evidence. D3 compares semantic stability + configured metric/event tolerances, not universal byte-identical float artifacts.

## 25. OpenBridge implementation sequence

1. Complete frontend host-stack ADR/spike.
2. Pin exact OpenBridge package/catalog version/commit.
3. Verify provenance/license/NOTICE/distribution obligations.
4. Inventory V1 primitives.
5. Classify OB-NATIVE/COMPOSED/WRAPPED/EXTENSION/EXCEPTION.
6. Build thin adapters only where useful.
7. Map semantic tokens.
8. Implement shell/layouts/Engineering Workspace.
9. Build domain extensions such as Capability Matrix, Timeline, Evidence Explorer.
10. Maintain Conformance Matrix + provenance record in review.
11. Treat Custom Exception count as design-debt metric.

## 26. Frontend architecture rules

- Domain data arrives through typed Application API/Projection models.
- Frontend components do not parse raw CAS artifacts ad hoc.
- Shared Observation Surface reused Live/Replay.
- Task Context store and Presentation State store are separate.
- URL query/deep links may store inspection/query state, never hidden RunSpec.
- OpenBridge wrappers thin/centralized.
- Status components use explicit semantic namespace where operational/assurance ambiguity exists.
- No framework-specific assumption beyond the accepted frontend ADR.

## 27. Backend architecture and local security rules

- Domain layer has no FastAPI request objects/filesystem paths.
- Run Worker owns execution, not browser session.
- Browser disconnect does not stop/evaluate/delete Run unless explicit user action reaches worker policy.
- Evidence sealing server/worker-side with crash-consistent finalization.
- Git worktree snapshotted before Run.
- ImplementationArtifact formal identity is immutable and distinct from dirty SourceSnapshot.
- Formal Evaluation references immutable Evaluator/Profile identities.
- Assurance Engine callable without Web.
- Gate Attestation created from execution evidence, not UI state.
- Default service bind loopback/local only.
- Only registered repository/workspace/artifact roots accessible through application services.
- No generic frontend API for arbitrary shell commands or filesystem paths.
- Agent/Handoff imports are data; backend policy resolves allowed commands/workspaces.

## 28. CI migration plan

Preserve current lint/unit workflow while adding regression incrementally.

```text
Stage A
Existing ruff + pytest continue

Stage B
Add non-required colav/core-regression preview

Stage C
Stabilize every CORE member / evidence / qualified environment

Stage D
Expose stable check names and enable branch protection

Stage E
Add Protected Baseline Set + formal Attestation
```

Current `cancel-in-progress`-style orchestration may cancel an obsolete candidate when superseded by a newer commit; model this separately from Gate Early/mandatory execute-to-completion within the active candidate.

Never enable a flaky required gate and normalize reruns/bypasses; stabilize first.

## 29. Risk register

### R-01 — Scope inflation into Formal Validation
Mitigation: five V1 workfaces / D-142 boundary.

### R-02 — UI-first build creates second truth
Mitigation: domain/evidence/runtime before complex Workbench UI.

### R-03 — Core changes accidentally during refactor
Mitigation: exact-ref Baseline Characterization Manifest + adapter-first migration.

### R-04 — OpenBridge wrappers become private design system
Mitigation: reuse classification, documented extension policy, provenance gate.

### R-05 — Solver/native crash destabilizes Web
Mitigation: isolated Run Worker.

### R-06 — Evidence storage growth/unsafe cleanup
Mitigation: CAS, capture profiles, reachability-aware retention, no automatic GC of retained sealed evidence.

### R-07 — Regression flaky
Mitigation: every CORE member Stability Qualification, D3, Quarantine, no retry-to-green.

### R-08 — Gate passes by weakening tests
Mitigation: immutable suites, Suite Change Proposal, Protection Diff, Baseline governance.

### R-09 — Agent changes validation assets
Mitigation: Agent Change Contract/protected asset checks; imported result is data.

### R-10 — Historical schema break
Mitigation: Read-Old/Write-Current, non-destructive projections.

### R-11 — Dirty source treated as formal implementation
Mitigation: separate SourceWorkspace/SourceSnapshot/ImplementationArtifact model.

### R-12 — Local execution exposed remotely
Mitigation: loopback default, registered roots, no arbitrary shell/path API.

### R-13 — Reconstructed Evaluator overclaimed
Mitigation: immutable evaluator provenance + explicit functional/numerical boundary.

### R-14 — Codex guesses frontend framework
Mitigation: mandatory frontend host-stack ADR before M4 implementation.

## 30. Implementation completion rule

A milestone is not complete because its page exists. It must provide evidence that corresponding domain invariants and PRD acceptance criteria are exercised.

Final V1 completion authority is the Evidence-Backed V1 Acceptance Gate in `Colav-Simulator-V1-PRD.md`, not visual feature count.
