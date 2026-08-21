# Colav-Simulator V1 P0 Object Traceability Matrix

> **Purpose:** implementation-readiness cross-check for PR #28  
> **Normative source:** `Design/Colav-Simulator-V1-PRD.md`  
> **UI source:** `Design/Colav-Simulator-V1-UI-Spec.md`  
> **Implementation source:** `Design/Colav-Simulator-V1-Implementation-Plan.md`  
> **Status:** P0 object coverage matrix after design-baseline review corrections  
> **Last updated:** 2026-08-19

## 1. Use of this matrix

This matrix verifies that every V1 first-class object has an explicit implementation path. It does not replace the PRD. If this matrix conflicts with the PRD, the PRD governs.

Legend:

- **Owner**: primary UI/workface/global route; background-only objects may have inspection rather than full authoring UI.
- **Persistence**: durable identity expected in Metadata Store unless explicitly embedded/versioned under a parent object; large payloads live in CAS.
- **Milestone**: primary milestone from the Implementation Plan; later milestones may extend the object.
- **Acceptance/Test**: minimum evidence path proving the object is not merely a schema placeholder.

## 2. Core engineering objects

| Object | Key PRD IDs / domain role | UI owner / route | Persistence identity | Primary milestone | Acceptance / test path |
|---|---|---|---|---|---|
| `Investigation` | §8.1, GW/WB | Workbench Home / Investigation | `investigations` | M1, M9 | Golden Workflow reaches `CLOSED` only after Fix Verified + Regression + CORE PASS |
| `Requirement` | §8.2, EVA | Cases > Requirements | `requirements` | M1, M5 | Requirement version appears in Case/Evaluation lineage and Coverage |
| `ScenarioFamily` | §8.3, CASE | Cases > Scenario Families | `scenario_families` | M1, M5 | Template instantiate → Concrete Case; later Template version does not mutate old Case |
| `CaseVersion` | §8.4, CASE | Case Designer / Case Detail | `case_versions` | M1, M5 | Four encounter baseline Cases Published/Qualified/immutable |
| `TrafficActorBehavior` | CASE-007 | Case Designer | versioned Case subobject or normalized identity | M5 | Scripted/triggered maneuver reproducibly executes and is visible in qualification evidence |
| `ConditionProfile` | §8.11, CASE-008 | Cases / Preflight | `condition_profiles` | M1, M5 | Same Case executes under distinct condition profiles without duplicating Case definition |
| `TestPhaseContract` | CASE-010 | Case Designer / Run Evaluation | versioned Case subobject | M5 | Expected phase contract resolves to observed Run windows with provenance |
| `ScenarioQualificationPolicy` | §8.12, CASE-011 | Case Qualification Preview | `scenario_qualification_policies` | M1, M5 | Qualification Evidence binds exact policy; Algorithm Capability shown NOT EVALUATED |
| `CaseQualificationRecord` | §8.12 | Case Detail / Qualification | `case_qualification_records` | M1, M5 | Case change invalidates/stales prior qualification; requalification required before Publish |
| `RegressionCase` | §8.5, GW-009 | Cases > Regression | CaseVersion + regression metadata/lineage | M5, M10, M11 | Exact failure → curated Regression Case → Stability Qualification → CORE membership |

## 3. Source, algorithm and runtime identity

| Object | Key PRD IDs / domain role | UI owner / route | Persistence identity | Primary milestone | Acceptance / test path |
|---|---|---|---|---|---|
| `SourceWorkspace` | §8.6, ALG-011, ARCH-006 | Global Engineering Workspace | `source_workspaces` | M1, M2, M4B | Register worktree; inspect clean/dirty/HEAD without silently changing Run context |
| `SourceSnapshot` / `EphemeralSourceSnapshot` | §8.7, ALG-004 | Global Workspace + Run source detail | `source_snapshots` + CAS source payload/patch | M1, M2 | Two dirty states yield distinct immutable snapshots; historical Run unaffected by later edits |
| `AlgorithmDefinition` | §8.8, ALG | Algorithms Catalog | `algorithm_definitions` | M1, M6 | Manifest/role/contract registered and discoverable |
| `ImplementationArtifact` | §8.9, ALG-003/004 | Algorithms > Implementations | `implementation_artifacts` + CAS/build digest | M1, M2, M6 | Cannot represent dirty source; Published ADP binds immutable artifact |
| `ADP` | §8.10 | Algorithms > ADP Detail | `adps` | M1, M6 | Published immutable; Candidate change creates Diff/Impact; Promotion requires Implementation Artifact |
| `ExecutionEnvironmentProfile` | §8.27, ARCH-008 | Global Engineering Workspace | `execution_environment_profiles` | M1, M12 | Local compatible vs Qualified CI environment distinguished; Fast Merge uses qualified profile |
| `ReproducibilityContract` | §8.28, ARCH-009 | Regression / environment detail | `reproducibility_contracts` | M1, M11/M12 | Every CORE member has current Stability Qualification; representative D3 repeated fixture |

## 4. Run and evidence objects

| Object | Key PRD IDs / domain role | UI owner / route | Persistence identity | Primary milestone | Acceptance / test path |
|---|---|---|---|---|---|
| `EvidenceCaptureProfile` | §8.13 | Preflight / Run Evidence | `evidence_capture_profiles` | M1, M3 | DEVELOPMENT/DIAGNOSTIC/REGRESSION profiles enforce Core Evidence Floor |
| `RunSpec` | §8.14 | Preflight / Run identity | immutable structured snapshot + digest | M1, M2 | Purpose-aware bindings work for Development, Qualification, Integration Smoke and CORE |
| `Run` | §8.14, RUN | Runs / Workbench | `runs` | M1, M2, M8 | Orthogonal Record/Execution/Evaluation states persist; Run ID survives restart |
| `ExecutionGroup` | §8.15 | Runs / Regression group detail | `execution_groups` | M1, M8/M11 | CORE action produces member Runs and aggregate result without hiding individual Run IDs |
| `EvidenceManifest` | §8.16 | Run > Evidence | `evidence_manifests` | M1, M3 | Crash-safe finalization; SEALED manifest immutable and integrity-verifiable |
| `EvidenceArtifact` | §8.16 | Run > Evidence Explorer | `artifacts` metadata + CAS payload | M1, M3 | Digest verification, deduplication, missing/corrupt state, reachability-aware retention |
| `LineageEdge` | §27 / RUN-013 | Run/objects > Lineage | `lineage_edges` | M1, M8 | Semantic lineage path and expandable graph traverse canonical object refs |
| `AttentionItem` | UX-004 | Global Attention Center + local surfaces | `attention_items` | M1, M4B+ | `ACKNOWLEDGED` does not resolve underlying Gate/Capability/asset condition |

## 5. Evaluation and coverage objects

| Object | Key PRD IDs / domain role | UI owner / route | Persistence identity | Primary milestone | Acceptance / test path |
|---|---|---|---|---|---|
| `EvaluatorDefinition` | §8.17, EVA-004 | Cases > Requirements > Evaluators/Profile detail | `evaluator_definitions` | M1, M5/M7 | Stable semantic contract distinct from implementation |
| `EvaluatorImplementationArtifact` | §8.17, EVA-004/008 | Evaluation Profile detail | `evaluator_implementation_artifacts` | M1, M7 | Reconstructed evaluator registered with provenance; implementation change requires new identity |
| `EvaluationProfile` | §8.18 | Cases > Requirements > Evaluation Profiles | `evaluation_profiles` | M1, M5/M7 | Published immutable; Qualification Suite passes before use in formal evidence |
| `EvaluationRecord` | §8.19 | Run > Evaluations | `evaluation_records` | M1, M7/M8 | Re-evaluation never overwrites Original Evaluation; missing evidence yields NOT_EVALUABLE/NOT_ESTABLISHED |
| `CoverageContract` | §8.20, EVA-006 | Cases > Requirements > Coverage | `coverage_contracts` | M1, M5/M7 | Coverage Matrix derives from qualified applicable evidence; FAIL may be COVERED+FAIL |
| `GoldenEvidenceFixture` | EVA-005 | Cases > Requirements > Golden Evidence | durable fixture metadata + CAS payload as appropriate | M5/M7 | Profile Qualification detects expected/unexpected Verdict Diff independent of algorithm Run |

## 6. Compare, Agent and fix-verification objects

| Object | Key PRD IDs / domain role | UI owner / route | Persistence identity | Primary milestone | Acceptance / test path |
|---|---|---|---|---|---|
| `ComparisonContract` | §8.21, GW-007 | Workbench > Compare | `comparison_contracts` | M1, M10 | Controlled/intended/unexpected differences + Fidelity generated from two immutable Runs |
| `FixVerificationRecord` | §8.21, GW-008 | Workbench > Compare | `fix_verification_records` | M1, M10 | `FAIL → PASS` alone cannot produce `FIX_VERIFIED`; no-new-mandatory-failure rule enforced |
| `DebugHandoff` | §8.22, AGENT | Workbench > Debug Handoff | `debug_handoffs` + export artifacts | M1, M10 | Versioned immutable Markdown+JSON; Facts/Findings/Hypotheses separated |
| `AgentResult` | §8.22 | Workbench > Agent Result review | `agent_results` + source/patch refs | M1, M10 | Imported as data; protected-asset changes detected; platform re-verification required |

## 7. Regression and governance objects

| Object | Key PRD IDs / domain role | UI owner / route | Persistence identity | Primary milestone | Acceptance / test path |
|---|---|---|---|---|---|
| `RegressionSuite` | §8.23, REG-001 | Regression > Suite detail | `regression_suites` | M1, M11 | Published immutable exact Case/Profile/Policy refs; change creates new version |
| `ProtectedBaselineSet` | §8.24, REG-009 | Regression > Protected Baselines | `protected_baseline_sets` | M1, M11 | Fast Merge protects all mandatory baselines; impact tests only add |
| `SuiteChangeProposal` | §8.26, REG-013 | Regression > Suite Change Proposal | `suite_change_proposals` | M1, M11 | Protection Diff computed; active failure removal explicitly flagged |
| `BaselineTransitionProposal` | §8.26, REG-010 | Regression > Baseline Transition | `baseline_transition_proposals` | M1, M11 | Old baseline stays protected until successor Ready-to-Switch |
| `MergeWaiver` | §8.26, REG-012 | Regression > Merge Waiver | `merge_waivers` | M1, M11 | Gate remains FAIL/INCOMPLETE; merge recorded `MERGED_WITH_EXCEPTION` |
| `RemediationObligation` | §8.26 | Regression / Attention Center | `remediation_obligations` | M1, M11 | Waiver automatically creates unresolved remediation until later passing evidence closes it |
| `GateAttestation` | §8.25, REG-011 | Regression > Gate Attestation | `gate_attestations` + evidence refs | M1, M11/M12 | Real GitHub Check traces exact source/baseline/suite/environment/Runs/Evidence |

## 8. Cross-object invariants checked by implementation

```text
Published ADP
→ immutable ImplementationArtifact
→ never mutable SourceWorkspace
```

```text
Development Run
→ SourceSnapshot or ImplementationArtifact
→ exact EvidenceCaptureProfile
→ exact RunSpec digest
```

```text
CASE_QUALIFICATION Run
→ ScenarioQualificationPolicy
→ no Algorithm Capability claim
```

```text
Original Evaluation
→ immutable
Re-evaluation
→ new EvaluationRecord
```

```text
Original Verdict
≠ Current Evidence Trust/Impact
≠ Claim-specific Eligibility
```

```text
Capability grade
→ exact ADP × role-compatible capability × conditions × evidence
```

```text
CORE member
→ current Stability Qualification
→ D3 policy in applicable Qualified Environment
```

```text
Gate PASS
→ exact candidate source identity
→ ProtectedBaselineSet
→ RegressionSuite(s)
→ Qualified Environment
→ SEALED member Evidence
→ immutable GateAttestation
```

## 9. Review coverage disposition

The design-baseline review correction is implementation-ready only if changes to the PRD/UI/Implementation Plan do not leave any matrix row without:

1. stable domain identity;
2. durable persistence or explicit versioned parent embedding;
3. UI/global owner where user interaction is required;
4. implementation milestone;
5. acceptance/test evidence path.
