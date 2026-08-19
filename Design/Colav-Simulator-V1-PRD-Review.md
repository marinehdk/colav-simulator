# Colav-Simulator V1 PRD Design-Baseline Review

> **Review target:** PR #28 (`docs/colav-v1-prd`)  
> **Review date:** 2026-08-19  
> **Status:** Changes required before the PR is promoted from Draft to Ready for Review  
> **Scope:** internal consistency, repository alignment, V1/V2 leakage, implementability, OpenBridge adoption, evidence/assurance integrity

## 1. Review basis

The review cross-checks the three V1 documents against the current repository design baseline and source facts, especially:

- `MISSION.md`
- `CONTEXT.md`
- `Design/Colav-Simulator-Architecture.md`
- `Design/Algorithm-Capability-Matrix.md`
- `Design/Evaluator-Audit.md`
- `Design/Implementation-Traceability.md`
- `.github/workflows/ci.yml`
- current `web_gui/` structure
- `THIRD_PARTY_NOTICES.md`

The review does **not** reopen D-001–D-144 product strategy. It identifies implementation ambiguities, missing normative constraints and cross-document inconsistencies that can be resolved without changing the frozen strategic scope.

## 2. Overall assessment

The V1 baseline is directionally coherent and preserves the most important repository principles:

- one real simulation/evidence chain rather than a second Web truth;
- explicit separation of runtime readiness, verification and release eligibility;
- immutable published/sealed facts;
- Development + CORE Regression as the V1 boundary;
- preserve/characterize/adapt the simulation core rather than rewriting it for UI purposes;
- OpenBridge component/token reuse before custom UI;
- FAIL versus INCOMPLETE semantics;
- local-first worktree/Codex workflow with server-ready boundaries.

The documents are **not yet ready to be treated as implementation-complete specifications**. The items below should be corrected first.

## 3. Blocking findings

### REV-B01 — Dirty Source Snapshot is conflated with Implementation Artifact

**Affected:** PRD §8.11, ALG-004/005, Implementation Plan M1/M2.

The workshop decision distinguishes:

```text
SourceWorkspace
→ Ephemeral Source Snapshot (dirty development identity)
→ Immutable Implementation Artifact (formal reusable implementation identity)
```

The current PRD says an `Implementation Artifact` may include clean/dirty/snapshot state and then separately says formal ADP/CORE requires an immutable Implementation Artifact. This can lead an implementer to model dirty snapshots as formal implementation artifacts.

**Required correction:**

- Add first-class `SourceWorkspace` and `SourceSnapshot`/`EphemeralSourceSnapshot` objects.
- Define `ImplementationArtifact` as immutable formal identity only.
- Define Run source identity as an explicit union/reference: Ephemeral Source Snapshot for Development, Implementation Artifact for formal flows.
- Published ADP must bind an immutable Implementation Artifact; ADP Candidate/Experiment execution may bind a candidate source snapshot until promotion.
- Add persistence entities/migrations for workspace/snapshot identities.

### REV-B02 — Evidence Capture Profile and mandatory Core Evidence were lost from the normative PRD

**Affected:** PRD §8/§12/ARCH-004, Implementation Plan M3.

D-038 established versioned Evidence Capture Profiles and mandatory Core Evidence. The PRD mentions a capture profile in Run identity but does not define it as a first-class versioned contract or define the mandatory evidence floor.

**Required correction:**

Add `EvidenceCaptureProfile` with at least V1 system profiles such as:

```text
DEVELOPMENT@1
DIAGNOSTIC@1
REGRESSION@1
FORMAL_VALIDATION@future
```

Mandatory Core Evidence shall include, at minimum:

- frozen RunSpec;
- source/implementation/ADP identity as applicable;
- truth/ownship trajectory;
- target truth/tracks required by the execution contract;
- encounter/risk events;
- planner core status/selected output/fallback-hold events;
- evaluation inputs/results when evaluation is requested;
- runtime/process errors and execution-control events;
- execution environment/version manifest.

Missing required diagnostic data must be represented as `NOT_AVAILABLE`/`NOT_CAPTURED`/`MISSING` according to cause and never fabricated.

### REV-B03 — P0 persistence entity list is incomplete relative to first-class PRD objects

**Affected:** Implementation Plan M1.

The initial metadata list omits multiple P0 first-class objects required elsewhere, including source workspaces/snapshots, evaluator identities, capture profiles, coverage contracts, comparison/fix verification, agent handoff/result and assurance-governance records.

**Required correction:** provide an authoritative P0 domain/persistence catalog or explicitly schedule later schema migrations for at least:

```text
source_workspaces
source_snapshots
evidence_capture_profiles
evaluator_definitions
evaluator_implementation_artifacts
coverage_contracts
comparison_contracts
fix_verification_records
debug_handoffs
agent_results
case_qualification_records
scenario_qualification_policies
execution_environment_profiles
reproducibility_contracts
suite_change_proposals
baseline_transition_proposals
merge_waivers
remediation_obligations
```

The exact relational normalization may differ, but the first-class identities must not disappear into unversioned JSON blobs.

### REV-B04 — Current reconstructed Evaluator boundary is not normative enough in the PRD

**Affected:** PRD Evaluation section and acceptance claims.

`Design/Evaluator-Audit.md` explicitly states that the current evaluator is a reconstructed implementation, not the official numerical evaluator, and outputs `functional_reproduction` with `numerical_reproduction_confirmed=false`.

The Implementation Plan mentions this only under legacy migration. The PRD must itself prevent future UI/Capability/Gate work from accidentally relabeling the reconstructed evaluator as official/numerically validated.

**Required correction:** add a hard Evaluation requirement:

- register the reconstructed evaluator with explicit implementation/provenance identity;
- retain `functional_reproduction` / numerical-not-confirmed semantics until a separately qualified official/numerically calibrated implementation exists;
- no V1 Gate/Capability/UI language may imply paper numerical reproduction, certification or type-approval evidence from the reconstructed evaluator.

## 4. Major findings

### REV-M01 — G0–G4 capability semantics are used but not defined in the PRD

The UI and Capability Matrix use G grades, but the normative PRD does not import or redefine their meanings. `Design/Algorithm-Capability-Matrix.md` currently defines:

```text
G0 Discoverable
G1 Short smoke test
G2 Full closed loop
G3 Capability demonstration
G4 Benchmark validation
```

**Required correction:** define the grade vocabulary in the PRD, preserve role/scope/evidence provenance, and state explicitly:

- grade is scoped to exact ADP + capability cell + conditions;
- V1 CORE PASS does not automatically imply G4;
- V1 acceptance does not require any algorithm to reach G4;
- G4 remains a benchmark-validation concept and must be awarded only when the versioned grade policy/evidence requirements are satisfied.

### REV-M02 — Existing planning terminology in `CONTEXT.md` needs explicit preservation

The PRD/UI uses generic `Committed Planner Output/Committed Plan`. Repository terminology already distinguishes:

- Mission Route;
- Avoidance Corridor;
- Horizon Encounter Plan;
- Hard Row Window;
- Rolling Plan;
- Plan Revision.

`CONTEXT.md` explicitly warns against ambiguous names such as “committed route”.

**Required correction:**

- Use generic `Selected/Accepted Planner Output` for algorithm-agnostic visualization rather than `Committed Plan` as a canonical domain term.
- When an algorithm exposes the repository planning concepts, render their canonical names and do not conflate them with Mission Route, current solver candidate or warm start.
- Preserve Mission Route as authoritative voyage intent before/after the encounter.

### REV-M03 — Run state axes and Stop/Abort/Cancel semantics are underspecified

The PRD mixes record sealing lifecycle, execution status and evaluation verdict. It also lists `CANCELLED`/`ABORTED` but Workbench decisions distinguish Development `STOP` from formal workflow `ABORT`.

**Required correction:** define orthogonal axes, for example:

```text
Record lifecycle: CREATED → RUNNING → FINALIZING → SEALED
Execution status: QUEUED/RUNNING/FINISHED/STOPPED/ABORTED/CRASHED/CANCELLED
Evaluation: COMPLETE|INCOMPLETE × PASS|FAIL|NOT_ESTABLISHED
```

Suggested semantics:

- `STOPPED`: user intentionally ends a Development Run early;
- `ABORTED`: an execution expected to complete (CORE/Gate/formal workflow) is interrupted;
- `CANCELLED`: execution is cancelled before meaningful execution starts or is superseded by orchestration policy;
- `CRASHED`: abnormal worker/process termination.

Exact enums can be refined in implementation ADRs, but the axes must remain independent.

### REV-M04 — RunSpec currently assumes an ADP/Evaluation Profile even for qualification/integration runs

Case Qualification and Algorithm Integration Smoke are real executions but may occur before a formal ADP exists or without normal algorithm compliance evaluation.

**Required correction:** define purpose-aware execution subjects and optional/applicable bindings. At minimum reserve Run purposes:

```text
DEVELOPMENT
REPRODUCTION
FIX_VERIFICATION
CASE_QUALIFICATION
INTEGRATION_SMOKE
CORE_REGRESSION
```

with future `FORMAL_VALIDATION` reserved. `CASE_QUALIFICATION` binds a versioned Scenario Qualification Policy rather than claiming algorithm capability; `INTEGRATION_SMOKE` may bind an Algorithm Definition/Implementation candidate before ADP publication.

### REV-M05 — Requirement/Evaluation Profile/Coverage UI ownership is missing

Requirements and Evaluation Profiles are first-class P0 objects, but the P0 screen inventory has no explicit Requirement Detail, Evaluation Profile authoring/qualification, Coverage Contract or Golden Evidence qualification surfaces.

This must be solved without adding a sixth V1 workface.

**Required correction:** keep the agreed Cases top-level view `Requirements`, but make it a Requirement & Evaluation hub with local object/detail routes for:

- Requirement Catalog/Detail/Version;
- Evaluation Profile Detail/Qualification;
- Coverage Contract Detail/Matrix;
- Golden Evidence Fixtures used by profile qualification.

### REV-M06 — Source Workspace / Execution Environment UI ownership is missing

The product depends on registered Git worktrees and qualified execution environments, but P0 UI inventory does not specify where users inspect/register/select them.

**Required correction:** add a Global/Settings engineering workspace area (or Context Ribbon drill-down) for Source Workspaces and Execution Environment Profiles. Opening/inspecting these objects must not silently change Run execution context.

### REV-M07 — OpenBridge dependency/license provenance is not part of acceptance

The repository already maintains `THIRD_PARTY_NOTICES.md`. The V1 plan pins an OpenBridge catalog/package but does not require a license/NOTICE/provenance check before adoption.

**Required correction:** before M4 foundation acceptance, record:

- exact OpenBridge package/repository/component catalog version;
- source URL/provenance;
- applicable license(s);
- attribution/NOTICE obligations;
- commercial/distribution compatibility decision for the selected packages;
- required update to `THIRD_PARTY_NOTICES.md`/dependency inventory.

Do not state a license conclusion in the PRD unless it has been verified against the selected upstream version.

### REV-M08 — Local-first execution needs an explicit security boundary

The V1 Control Plane can inspect worktrees, execute algorithms and read/write local evidence. A local-first architecture is not safe if it accidentally exposes these capabilities on an unauthenticated remote interface.

**Required correction:** add V1 security NFRs:

- default bind to loopback/local access only;
- remote/multi-user exposure is out of V1 unless separately secured;
- only registered repositories/workspaces/artifact roots may be accessed by application services;
- frontend/API cannot request arbitrary filesystem paths or shell commands;
- imported manifests/Agent Results are data, not executable command authority;
- high-impact execution/governance endpoints must apply the same domain authorization/action policy even in single-user mode.

### REV-M09 — CAS retention, crash consistency and sealing atomicity are underspecified

The PRD requires immutable sealed evidence but does not state how automatic cleanup may interact with it.

**Required correction:** add persistence NFRs:

- artifacts referenced by SEALED Runs, Published assets, Gate Attestations or retained Evidence Bundles cannot be garbage-collected automatically;
- V1 cleanup is explicit/reachability-aware with impact preview;
- sealing is crash-safe: a Run cannot be reported SEALED until required manifest/artifact references and digests are committed consistently;
- orphan/unfinalized artifacts after worker/control-plane crashes are detectable/recoverable/cleanable without mutating sealed history.

### REV-M10 — Baseline characterization must pin the actual implementation source ref

`Design/Colav-Simulator-Architecture.md` documents a specific isolated `codex/colav-paper-closed-loop` snapshot, while PR #28 is based on `main`. The implementation plan currently says “characterize existing simulation core” without first freezing which source ref is the preservation baseline.

**Required correction:** Milestone 0 must produce a `Baseline Characterization Manifest` containing exact repository, branch/worktree/commit, environment, selected algorithms/scenarios and known limitations. Design documents cannot substitute for live source/ref verification.

### REV-M11 — Frontend host stack is intentionally unresolved but the plan needs an ADR gate

Current `web_gui/` is a static `index.html` + large `app.js` + `style.css` implementation and no root `package.json` was found in the current Web tree review. The new UI specification talks about wrappers/framework integration but does not intentionally decide whether the V1 host is native Web Components, TypeScript/Vite, React, etc.

This is acceptable at PRD level, but not acceptable for Codex to guess during implementation.

**Required correction:** add a pre-M4 architecture decision record/spike that selects the frontend host stack based on:

- OpenBridge Web Component interoperability;
- typed domain/projection models;
- routing/deep-link requirements;
- state separation (task vs presentation);
- testing/accessibility/tooling;
- migration from current `web_gui`;
- bundle/build/dependency management.

Do not assume React in normative wording before this ADR is accepted.

### REV-M12 — V1 acceptance only repeats one D3 case, while every CORE member must be stability-qualified

ACC-007 currently demonstrates a representative CORE case reaching D3, while REG-004 correctly requires all CORE Cases to pass Stability Qualification.

**Required correction:** ACC-007 shall additionally verify that every member of the Published V1 CORE Suite has current Stability Qualification under the applicable policy/environment. A representative repeated execution may remain the end-to-end demonstration fixture.

### REV-M13 — Algorithm role must constrain capability comparison

The existing capability audit explicitly distinguishes dynamic COLAV (VO/SB-MPC), static ENC path planning (RRT), tracking and nominal guidance roles. A common Capability Matrix must not imply that every registered algorithm should be scored against every dynamic COLAV requirement.

**Required correction:** capability/compatibility views must be role-aware. Unsupported/not-applicable capability dimensions are distinct from “declared but not yet verified”, and cross-algorithm comparison must state compatible role/scope before presenting comparative claims.

## 5. Minor/clarification findings

### REV-C01 — Risk-tier count typo

PRD UX-005 says “four impact tiers” while listing Tier 0 through Tier 4. This is five tiers.

### REV-C02 — Current Evidence Trust and Claim Eligibility should remain distinguishable in the domain model

The UI may summarize `NOT_ELIGIBLE`, but implementation should avoid turning Trust and purpose-specific eligibility into one Boolean/enum. Preserve:

```text
Historical Original Verdict
Current evidence trust/impact
Claim-specific eligibility
```

as separately derivable semantics.

### REV-C03 — Qualification Preview needs a versioned Scenario Qualification Policy identity

The case preview is algorithm-neutral only if the ownship/reference execution behavior and phase/encounter resolver versions are frozen. Add a `ScenarioQualificationPolicy` identity to qualification evidence.

### REV-C04 — CI supersession/cancellation should not be confused with Gate Early

Current CI uses `cancel-in-progress`. A new commit may legitimately supersede/cancel an older candidate run. This is different from stopping remaining CORE Cases after a deterministic failure, which is prohibited. Formal gate orchestration should represent superseded/cancelled candidates distinctly and preserve any already-sealed evidence where practical.

## 6. Scope-leak review

No new V1 workface is required by the corrections above.

The following remain correctly outside V1 product scope:

- Formal Validation Campaign UI;
- Release/MASS handoff workflow;
- large Monte Carlo/DOE product workflow;
- strict deployment-performance qualification workflow;
- central multi-user/RBAC server;
- fully automated coding-agent loop.

Corrections above are foundation/clarity work required to implement the already-frozen V1 safely; they are not V2 feature additions.

## 7. Required cross-document corrections

Before PR #28 becomes Ready for Review:

1. Update the PRD for REV-B01–B04 and REV-M01–M13 where normative.
2. Update UI Spec for Requirements/Evaluation ownership, Workspace/Environment inspection, terminology and OpenBridge provenance/conformance.
3. Update Implementation Plan for complete P0 entity catalog, baseline-characterization manifest, frontend-host ADR, security/storage NFR implementation and acceptance tasks.
4. Correct REV-C01–C04.
5. Re-run a cross-document traceability pass and confirm every P0 first-class object has:
   - domain definition;
   - owner/workface or global route;
   - persistence identity;
   - implementation milestone;
   - acceptance/test path where applicable.

## 8. Review disposition

```text
Current disposition: CHANGES_REQUIRED

Strategic baseline D-001–D-144: ACCEPTED / NOT REOPENED
V1/V2 scope: ACCEPTED
OpenBridge-native strategy: ACCEPTED
Assurance direction: ACCEPTED
Implementation readiness: BLOCKED pending corrections above
```
