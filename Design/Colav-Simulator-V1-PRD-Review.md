# Colav-Simulator V1 PRD Design-Baseline Review

> **Review target:** PR #28 (`docs/colav-v1-prd`)  
> **Review date:** 2026-08-19  
> **Second-pass date:** 2026-08-19  
> **Status:** Documentation baseline review **PASSED**; PR may be promoted to Ready for Review after owner confirmation  
> **Scope:** internal consistency, repository alignment, V1/V2 leakage, implementability, OpenBridge adoption, evidence/assurance integrity

## 1. Review basis

Cross-checked the V1 PRD/UI/Implementation Plan against current repository evidence, especially:

- `MISSION.md`
- `CONTEXT.md`
- `Design/Colav-Simulator-Architecture.md`
- `Design/Algorithm-Capability-Matrix.md`
- `Design/Evaluator-Audit.md`
- `Design/Implementation-Traceability.md`
- `.github/workflows/ci.yml`
- current `web_gui/`
- `THIRD_PARTY_NOTICES.md`

The review does **not** reopen D-001–D-144 strategy. It validates whether the frozen strategy is expressed precisely enough for implementation.

A companion coverage artifact now exists:

- `Design/Colav-Simulator-V1-Traceability-Matrix.md`

It maps P0 first-class objects to domain identity, UI owner, persistence identity, implementation milestone and acceptance path.

## 2. Overall second-pass assessment

The corrected baseline now preserves and makes normative the repository principles required for safe implementation:

- one real simulation/evidence chain;
- immutable Published/SEALED facts;
- explicit SourceWorkspace → SourceSnapshot → ImplementationArtifact separation;
- purpose-aware RunSpec and orthogonal Run state axes;
- versioned EvidenceCaptureProfile + mandatory Core Evidence Floor;
- explicit reconstructed-Evaluator functional/numerical boundary;
- role-aware G0–G4 capability semantics;
- canonical planning terminology from `CONTEXT.md`;
- Development + CORE Regression V1 boundary;
- exact-ref simulation-core characterization before preservation claims;
- OpenBridge component/token reuse with provenance/license/NOTICE gate;
- local-first security boundary;
- CAS retention and crash-consistent sealing;
- frontend host-stack ADR before UI implementation;
- every Published CORE member requiring current Stability Qualification.

No new top-level Workface or V2 feature was introduced by the corrections.

## 3. Blocking findings disposition

| Finding | Resolution | Status |
|---|---|---|
| REV-B01 Dirty Source Snapshot vs Implementation Artifact | PRD now defines first-class `SourceWorkspace`, `SourceSnapshot/EphemeralSourceSnapshot`, immutable-only `ImplementationArtifact`; Run source is purpose-aware; Published ADP binds immutable artifact. Implementation Plan/persistence catalog updated. | RESOLVED |
| REV-B02 Evidence Capture Profile/Core Evidence lost | PRD defines `EvidenceCaptureProfile`, DEVELOPMENT/DIAGNOSTIC/REGRESSION profiles and mandatory Core Evidence Floor; Plan M3 implements/validates them; UI Preflight/Evidence surfaces expose capture profile and missing-cause semantics. | RESOLVED |
| REV-B03 P0 persistence entity list incomplete | Implementation Plan now contains authoritative P0 concept/persistence catalog; Traceability Matrix cross-checks durable identity/owner/milestone/test path. | RESOLVED |
| REV-B04 Reconstructed Evaluator boundary weak | PRD EVA-008 makes `functional_reproduction` / `numerical_reproduction_confirmed=false` boundary normative; Plan M7 and UI Evaluation surfaces preserve provenance and prohibit official/numerical/certification overclaim. | RESOLVED |

## 4. Major findings disposition

| Finding | Resolution | Status |
|---|---|---|
| REV-M01 G0–G4 undefined | PRD CAP-001 defines G0 Discoverable, G1 Smoke, G2 Full Closed Loop, G3 Capability Demonstration, G4 Benchmark Validation; scope is exact ADP × capability × conditions × evidence; CORE PASS/V1 acceptance do not auto-grant G4. | RESOLVED |
| REV-M02 `CONTEXT.md` planning terminology | PRD/UI use generic `Selected/Accepted Planner Output` only as algorithm-agnostic display language; canonical Mission Route/Avoidance Corridor/Horizon Encounter Plan/Hard Row Window/Rolling Plan/Plan Revision preserved. | RESOLVED |
| REV-M03 Run state axes | PRD defines Record Lifecycle, Execution Status and Evaluation axes separately; STOPPED/ABORTED/CANCELLED/CRASHED semantics documented; UI/Plan updated. | RESOLVED |
| REV-M04 RunSpec assumes ADP/Profile | Purpose-aware RunSpec added for DEVELOPMENT, REPRODUCTION, FIX_VERIFICATION, CASE_QUALIFICATION, INTEGRATION_SMOKE, CORE_REGRESSION; qualification/smoke may precede Published ADP/Evaluation. | RESOLVED |
| REV-M05 Requirement/Evaluation UI ownership | `Cases > Requirements` is defined as Requirement & Evaluation Hub with Requirement, Evaluation Profile, Coverage Contract and Golden Evidence routes. | RESOLVED |
| REV-M06 Workspace/Environment UI ownership | Global Engineering Workspace/Settings owns registered SourceWorkspace/SourceSnapshot and Execution Environment inspection/registration; no silent task-context switch. | RESOLVED |
| REV-M07 OpenBridge provenance/license | PRD OB-008 and Plan M4B require exact package/version/source/license/NOTICE/distribution review and repository notice update; no generic license conclusion is asserted. | RESOLVED |
| REV-M08 Local-first security boundary | PRD ARCH-011 and Plan security tests require loopback default, registered roots, no arbitrary browser filesystem/shell authority, Agent imports treated as data. | RESOLVED |
| REV-M09 CAS retention/crash consistency | PRD ARCH-012 and Plan M1 require reachability-aware retention, no automatic GC of retained SEALED/Attestation artifacts, and crash-consistent sealing/orphan recovery. | RESOLVED |
| REV-M10 Exact baseline source ref | PRD ARCH-014 and Plan M0 require immutable Baseline Characterization Manifest with exact repo/ref/commit/environment/algorithms/scenarios/limitations/evidence. | RESOLVED |
| REV-M11 Frontend host stack ADR | PRD ARCH-013 and Plan M4A require ADR/spike before UI implementation; no React/Vue/native framework is assumed normatively. | RESOLVED |
| REV-M12 ACC-007 only one D3 case | ACC-007 now requires every Published V1 CORE member to have current Stability Qualification; representative repeated case remains end-to-end D3 demonstration. | RESOLVED |
| REV-M13 Algorithm role comparison | PRD CAP-002/ALG-013 and UI role-aware Capability views distinguish role-not-applicable from not-verified; static RRT/tracker evidence is not presented as equivalent dynamic COLAV capability. | RESOLVED |

## 5. Clarification findings disposition

| Finding | Resolution | Status |
|---|---|---|
| REV-C01 Risk-tier count | PRD/UI now explicitly say **five** tiers: Tier 0–4. | RESOLVED |
| REV-C02 Trust vs Eligibility | PRD P-008/RUN-011 and UI separate Original Verdict, Current Trust/Impact and claim-specific Eligibility. | RESOLVED |
| REV-C03 Scenario Qualification Policy identity | PRD §8.12/CASE-011, UI Qualification Preview and Plan M5 bind exact versioned `ScenarioQualificationPolicy`. | RESOLVED |
| REV-C04 CI cancellation vs Gate Early | PRD RUN-014/REG-007 and Plan M11/M28 distinguish superseded candidate cancellation from mandatory execute-to-completion inside active CORE Gate. | RESOLVED |

## 6. P0 object coverage second pass

The Traceability Matrix confirms coverage for these first-class categories:

```text
Investigation
Requirement / Evaluation / Coverage
Scenario Family / Case / Qualification
SourceWorkspace / SourceSnapshot
Algorithm Definition / Implementation Artifact / ADP
Execution Environment / Reproducibility
RunSpec / Run / ExecutionGroup
EvidenceCaptureProfile / Manifest / Artifact
Evaluator / Evaluation Profile / Evaluation Record
Comparison / Fix Verification
Debug Handoff / Agent Result
Regression Suite / Protected Baseline
Suite Change / Baseline Transition / Merge Waiver / Remediation
Gate Attestation
Lineage / Attention
```

Each has a defined domain identity, persistence identity or explicit versioned parent embedding, UI/global owner where required, implementation milestone and acceptance/test path.

## 7. Repository-alignment observations retained as implementation gates

The documentation baseline intentionally does **not** claim the following work is already implemented:

1. The actual refactor preservation baseline must still be generated from a live exact source ref in Milestone 0.
2. The frontend host stack must still be selected by ADR/spike.
3. The exact OpenBridge dependency/license/NOTICE review must still be performed against the selected upstream version.
4. Current reconstructed Evaluator remains functional-reproduction-only until a separately qualified numerical/official implementation exists.
5. Branch protection/required checks, CORE D3 stability and new Gate Attestation are future implementation milestones, not documentation-complete facts.

These are implementation gates, not unresolved PRD ambiguities.

## 8. Scope-leak second pass

The following remain outside V1 product scope:

- Formal Validation Campaign UI;
- Release/MASS handoff workflow;
- large Monte Carlo/DOE product workflow;
- strict deployment-performance qualification workflow;
- central multi-user/RBAC server;
- fully automated coding-agent loop.

No correction introduced a sixth V1 Workface.

## 9. Final review disposition

```text
Strategic baseline D-001–D-144: ACCEPTED / NOT REOPENED
V1/V2 scope: ACCEPTED
OpenBridge-native strategy: ACCEPTED
Assurance direction: ACCEPTED
Repository alignment: PASSED after corrections
Cross-document P0 traceability: PASSED
Documentation implementation-readiness: PASSED

PR #28 status recommendation:
READY_FOR_REVIEW after repository owner confirmation
```

Passing this documentation review does not mean V1 runtime implementation is complete. It means the PRD/UI/Implementation baseline is sufficiently explicit to begin controlled implementation without the known review ambiguities above.
