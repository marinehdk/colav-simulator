# Predictive Multi-Target Threat Management + Historical AIS Counterfactual Benchmark

**Status:** Normative implementation contract; ready for implementation
**Canonical issue:** [#29](https://github.com/marinehdk/colav-simulator/issues/29)
**Child tickets:** [#30](https://github.com/marinehdk/colav-simulator/issues/30)–[#40](https://github.com/marinehdk/colav-simulator/issues/40)
**Implementation baseline:** `main@ba80bf8270b47e76f1811f85ff3aa5fb2c0c3199`
**Original offline attachment:** `colav_predictive_threat_historical_ais_spec.md`, SHA-256 `902faaede72f0952fbb2ccb298fde88de322c7b2738d842c80dd02af781c6681`
**Reference HAIS archive:** `Hais_e716cfac-348c-417b-acbd-04a228732de7.zip`, SHA-256 `d303d719cebaf0238c54b9e27f2a40b4414b26e3189b49cb84fbad4086b3f3d7`
**Specification method:** Matt Pocock `/to-spec`; the repository copy is canonical for implementation.

## Normative rules

Issue #29 and this repository copy are normative. Issues #30–#40 refine delivery and may not weaken or reinterpret this contract. Existing upstream authorities remain authoritative where domains overlap: #24 Encounter Lifecycle, #26 L4 Plan Acceptance, and #27 Prediction Evidence. If implementation exposes a contradiction, stop at that boundary and report it; do not add a second truth.

The package must preserve single authority, immutable evidence, deterministic replay, typed unavailable/incomplete states and fail-closed behavior. It must not use scenario-ID branches, safety-threshold reduction, modified evaluator thresholds, forced PASS, silent fallback, hidden algorithm substitution, browser-side risk semantics, post-T0 human-trajectory leakage, or rewritten sealed evidence to make acceptance green.

## Problem Statement

Colav-Simulator has TrackKey identity, observation health, pairwise geometry, DCPA/TCPA, Encounter Lifecycle, Primary Target, Aggregate Directive, prediction evidence, plan acceptance, AIS scenarios, ENC support and independent evaluation. It lacks one end-to-end contract that makes dense multi-target threat management and real-AIS counterfactual benchmarking reproducible, explainable and independently auditable.

Current DCPA/TCPA/range facts do not express when an engineering Ship Domain is entered, which target is required concurrently, which target is next, why Primary changed, or whether an accepted avoidance plan creates a conflict elsewhere. A weighted risk score would allow a hard danger to be averaged away and would not provide a safety authority.

Historical AIS is currently an input source rather than a complete benchmark. The missing boundaries include immutable raw-source identity, normalized units, quality findings, reconstructed Historical Actors, qualified ENC coverage, Historical Replay, Reference Vessel handoff at T0, pre-T0-only Nominal Intent, post-T0 closed-loop COLAV control, future-leakage protection and separate Human-vs-COLAV assurance domains.

## Solution

Build two first-class capabilities over the existing simulator chain:

1. Predictive Multi-Target Threat Management exposes one deterministic, planner-agnostic operation conceptually equivalent to `evaluate(request) -> ThreatManagementSnapshot`. It consumes frozen online physical facts, the sole Encounter Lifecycle snapshot, prediction evidence, a versioned Ship Domain Profile and, only when valid, an accepted/committed ownship prediction. It emits immutable Threat Vectors, Threat Windows, a rolling Threat Schedule, typed Conflict Graph/Clusters, priority reasons and provenance.
2. Historical AIS Counterfactual Benchmark exposes one Case Builder operation conceptually equivalent to `build(request) -> HistoricalAISCaseBuildOutcome`. Kystverket HAIS GeoParquet is first-class and CSV remains compatible. A Published HistoricalAISCase binds source, selection, reconstruction, ENC, Reference Vessel, T0, intent, human reference, algorithm and evaluation evidence. Historical Replay uses the normal simulator. A Counterfactual Run controls only the Reference Vessel after T0 through the normal closed loop; other actors continue historical playback.

The two capabilities share canonical observation, prediction, evidence and Web projection semantics. The Planner sees current Sensor/Tracker observations only. The Independent Evaluator owns realized Safety/COLREG judgement. Human Similarity is comparison-only and advisory.

## User Stories

1. As a simulator operator, I want one backend threat account per target, so that screens cannot disagree about risk.
2. As a simulator operator, I want Current Primary, Concurrent Required, Next and Monitor targets separated, so that the evolving encounter is understandable.
3. As a simulator operator, I want domain entry, worst exposure and clear times beside DCPA/TCPA, so that anticipatory risk is visible.
4. As a simulator operator, I want typed priority reasons and schedule events, so that handoffs are explainable and replayable.
5. As a simulator operator, I want chart selection to change Inspection Context only, so that inspection cannot change Planner Primary.
6. As a safety engineer, I want Ship Domain parameters versioned with units, provenance and assumptions, so that domain claims are reproducible.
7. As a safety engineer, I want missing or degraded observations to remain explicit, so that bad data cannot make a target look safe.
8. As a safety engineer, I want Ship Domain facts separate from hull-clearance/L4 facts, so that anticipatory risk cannot weaken hard safety.
9. As a safety engineer, I want no weighted score to be the safety gate, so that emergency evidence cannot be averaged away.
10. As a COLREG developer, I want Encounter Lifecycle to remain the sole role, Rule 17, commitment and release authority, so that Threat Management cannot create a second FSM.
11. As a planner developer, I want Primary to mean focus rather than exclusivity, so that required targets remain planner obligations.
12. As a planner developer, I want emergency preemption and physical-time hysteresis, so that real urgency is immediate while jitter does not flap.
13. As a planner developer, I want generation changes and release to reset switching context deterministically, so that stale target state cannot be inherited.
14. As a planner developer, I want accepted-plan conflicts typed separately from direct conflicts, so that plan effects are auditable.
15. As an evidence reviewer, I want every snapshot bound to input/profile/plan hashes, so that sealed replay can reproduce it.
16. As a GUI developer, I want a backend-only threat projection, so that browser code only formats and renders semantic facts.
17. As a data engineer, I want Kystverket GeoParquet first-class and CSV compatible, so that large source files need no manual conversion.
18. As a data engineer, I want raw bytes immutable and normalized data derived, so that source provenance survives cleaning.
19. As a data engineer, I want explicit UTC, WGS84, SOG, COG, heading and ROT conversion, so that units cannot silently drift.
20. As a data engineer, I want invalid rows, duplicates, impossible values and gaps reported as typed quality findings, so that cleaning is auditable.
21. As a data engineer, I want dimensions unknown when unproven, so that formal safety claims do not use arbitrary defaults.
22. As a scenario engineer, I want source coverage limitations and NLOD attribution retained, so that absent small craft are not interpreted as empty water.
23. As a replay engineer, I want raw AIS observations, Historical Actor truth and Tracker observations separated, so that provenance of every state is clear.
24. As a replay engineer, I want the same Dataset plus Reconstruction Profile to replay deterministically, so that fixtures are trustworthy.
25. As a scenario engineer, I want an ENCRegionProfile to bind source, CRS, extent, hazards and qualification, so that enlarging a viewport cannot qualify coverage.
26. As a scenario engineer, I want out-of-coverage cases to fail preflight, so that unqualified execution is never reported as valid.
27. As a case builder, I want discovery labels for head-on, crossing, overtaking and multi-ship candidates, so that real traffic can be selected without overriding runtime Lifecycle truth.
28. As a case builder, I want Dataset, Selection, Reconstruction, Discovery, ENC, actors and digests frozen in a Published Case, so that later source changes cannot alter it.
29. As an algorithm V&V engineer, I want a real Reference Vessel and reviewable T0, so that historical and counterfactual runs share a declared handoff.
30. As an algorithm V&V engineer, I want Nominal Intent derived strictly from samples before T0, so that the algorithm cannot receive its future answer.
31. As an algorithm V&V engineer, I want insufficient pre-T0 evidence to fail typed, so that future human data cannot repair a weak intent claim.
32. As an algorithm V&V engineer, I want the Reference Vessel controlled by the real simulator after T0, so that benchmark behavior exercises the selected algorithm.
33. As an algorithm V&V engineer, I want surrounding Historical Actors to continue playback through the normal Sensor/Tracker chain, so that the Planner never reads their future directly.
34. As an algorithm V&V engineer, I want post-T0 Human Reference sealed for Compare only, so that it cannot enter Planner, Guidance or RunSpec.
35. As an evaluator developer, I want realized Safety/COLREG results from the Independent Evaluator, so that Planner facts cannot self-certify.
36. As a benchmark reviewer, I want Safety, COLREG, Maneuver, Efficiency and Human Similarity separate, so that one average hides no failure.
37. As a benchmark reviewer, I want Human Similarity labelled advisory, so that human likeness cannot change safety verdicts.
38. As an evidence reviewer, I want Dataset → Case → Run → Evaluation → Compare lineage, so that every result is traceable.
39. As a repository maintainer, I want real HAIS archives external and compact fixtures committed, so that Git and CI remain practical.
40. As a repository maintainer, I want focused seams, closed-loop checks and truthful full-suite reporting, so that unit success is not mistaken for system acceptance.

## Implementation Decisions

### Authority and cycle contract (DP-01–DP-04)

- One Session/Runtime `ThreatManagementCoordinator` exists per Own Ship and Active Session. It owns one Encounter Lifecycle and one online Threat Management account.
- At cycle start it freezes Ownship State, TrackSnapshot, prior Lifecycle state, profiles and accepted-plan evidence already available. It creates one immutable `PhysicalEncounterFacts` record per target containing TrackKey/generation, observation health/age, relative position/velocity, range/bearings, signed TCPA, forward DCPA, validity/unavailable reason and current hull geometry.
- Encounter Lifecycle and Threat Assessment consume those same online physical facts. Online code must not recompute equivalent CPA/geometry under another name. L4 candidate trajectories and Independent Evaluator realized trajectories retain separate facts and verdicts.
- The cycle advances Lifecycle, publishes one `ThreatManagementSnapshot`, then allows Planner candidate production and independent L4 acceptance. An accepted-plan receipt becomes eligible only in the next cycle. Web and Evidence consume the same snapshot; they do not create truth.

### Frozen decision contract (DP-05–DP-21)

#### DP-05 — Domain-aware Primary without a second Primary

Threat Assessment computes domain and horizon ranking facts; it never stores or advances Primary state. Encounter Lifecycle remains the only stateful Primary authority. The Coordinator passes canonical ranking facts into the Lifecycle public cycle/snapshot seam. Current Primary is always the Lifecycle result; Lifecycle-required targets and Aggregate Directive membership are never removed because another target ranks higher. A chart pin or inspection selection cannot alter it.

#### DP-06 — Pure Threat Assessment seam

The public operation is an immutable derivation: `evaluate(request) -> ThreatManagementSnapshot` (or an equivalent named seam). It consumes frozen physical facts, Lifecycle Decision Snapshot, prediction evidence, ShipDomainProfile and optional accepted-plan receipt. It does not classify encounters, mutate Lifecycle, call a solver, accept a plan, evaluate realized trajectories or invent missing evidence. Side effects are limited to the canonical evidence publication owned by the Coordinator.

#### DP-07 — Threat Vector fields and index boundary

Every Threat Vector keeps independent identity/generation, lifecycle references, physical DCPA/TCPA/range/closing facts, domain state/scale/TDV/TDE, prediction basis/horizon/completeness, observation health/uncertainty, priority class/reason and evidence references. An optional 0–100 Threat Index is explicitly `display_only`; Planner, L4, Evaluator and capability validation may not consume it.

#### DP-08 — Versioned ShipDomainProfile

V1 supports a deterministic off-centred elliptical engineering domain. The profile freezes version/hash, dimensions or dimension provenance, ellipse scales and offset, units, uncertainty policy, ODD assumptions and applicability. Domain parameters are not statutory COLREG distances. Normalized scale uses `>= 1` for outside and `< 1` for penetration; TDV/TDE are present only when defined. Missing or unqualified dimensions produce typed `UNQUALIFIED`/unavailable facts; no silent arbitrary default may support a formal safety claim.

#### DP-09 — Observation health and UNKNOWN

Health, freshness/age, covariance or uncertainty, source/status, validity and unavailable reason are separate from threat severity. Invalid geometry, low-speed undefined CPA, missing prediction, stale/coasting observation or generation mismatch yields typed `UNKNOWN`/`UNAVAILABLE` with completeness impact, never zero, CLEAR or fabricated certainty. A Lifecycle-required degraded target remains represented. A new TrackKey generation starts new evidence and cannot inherit prior state.

#### DP-10 — Lexicographic priority

Priority is a versioned lexicographic order, never a weighted mean: (1) current hard-clearance/response-time emergency, (2) Rule 17 `MUST_ACT` or equivalent mandatory emergency, (3) committed active duty, (4) current domain violation, (5) predicted domain violation/earliest meaningful entry, (6) future severity and completeness, then (7) deterministic TrackKey/generation tie-break. Each result records the winning class and reason. Role and action authorization remain Lifecycle facts; a high-risk Stand-on target is not made safe by lacking action authority.

#### DP-11 — Threat Window

A Threat Window records predicted entry, worst/peak exposure, clear/exit, relative and absolute/reference time identity, prediction horizon, source/basis and completeness. Boundaries that cannot be established remain typed unknown. The window is recalculated on each rolling horizon and is an explanation of future exposure, not an executable maneuver sequence.

#### DP-12 — Rolling Threat Schedule

Each snapshot assigns a TrackKey to exactly one semantic schedule context: Current Primary from Lifecycle; Concurrent Required from the Lifecycle/Aggregate Directive mandatory set; Next for future non-required threats; Monitor for retained observation/evidence without current obligation; and Released/Historical for retained evidence outside active duty. Schedule recomputation cannot add or remove planner obligations and never becomes a fixed execution script.

#### DP-13 — Hysteresis, preemption and rearm

Lifecycle owns per-primary/per-challenger switching context. A non-emergency challenger must exceed the current Primary for a versioned physical-time confirmation interval; one-cycle jitter cannot switch it. Current hard-clearance/response-time emergency or Rule 17 `MUST_ACT` may preempt and records the reason. Generation change, disappearance, release, unusable observation, session reset and rearm have deterministic behavior. No global “some target is risky” latch is allowed; released evidence remains historical.

#### DP-14 — Plan-induced conflict evidence

`PLAN_INDUCED_CONFLICT` requires an explicit baseline ownship prediction, a fresh accepted/committed plan receipt from #26/#27, matching prediction/target identities, plan/profile hashes and before/after witnesses. The accepted plan must cause a new domain violation, materially earlier entry or versioned meaningful worsening. A raw solver candidate, stale cache or GUI path cannot qualify. Without a valid receipt the result is typed unavailable; baseline/current-motion/mission-route basis may still be reported, but it is not plan-induced evidence. Same-cycle candidate feedback is forbidden.

#### DP-15 — Typed graph and deterministic clusters

V1 graph edges include `DIRECT_WINDOW_OVERLAP` and `PLAN_INDUCED_CONFLICT`, each with typed provenance, witness and prediction basis. Direct overlap uses a versioned time-overlap/gap rule over canonical windows. Clusters are input-order-independent connected components with deterministic semantic identities and lineage. A/B plus B/C is one cluster; disconnected pairs remain separate. Split/merge creates derived evidence; old sealed clusters are not rewritten. Scenario IDs and UI selection cannot create edges.

#### DP-16 — Domain versus hard safety

Ship Domain, Threat Index and online Threat Assessment are anticipatory/advisory evidence. Physical hull clearance and continuous/swept L4 hard safety remain separate authorities, with their own candidate-plan facts and thresholds. The Independent Evaluator separately scores realized collision/grounding/Safety/COLREG behavior. No domain or display score may lower, replace, average away or self-certify an L4/Evaluator verdict.

#### DP-17 — Monitor, Evaluator and online authority boundary

EncounterMonitor may remain diagnostic evidence but cannot publish canonical Planner/Web threat truth. Threat Assessment owns current/predicted online threat interpretation. Independent Evaluator owns realized-trajectory Safety/COLREG judgement. Authority mismatches are typed evidence, not silently overwritten. Online physical facts may share documented formulas, but online facts never masquerade as candidate-plan or realized-trajectory evidence.

#### DP-18 — Web projection only

API, telemetry and Web consume a versioned backend ThreatManagementSnapshot projection. Browser code may format units, draw, filter presentation and maintain Inspection Context; it may not recalculate CPA, domain, TDV/TDE, priority, windows, clusters or Primary. Missing facts remain null/typed unavailable. Web reconnect, session replacement and replay do not create a second risk engine or authoritative cache.

#### DP-19 — Snapshot schema, identity and replay

Snapshots and projections are immutable, versioned and serializable. They bind cycle/session identity, generated/reference time, physical-input hash, Lifecycle snapshot identity, prediction/profile hashes, accepted-plan receipt when used, per-target vectors, schedule, priority reasons, graph/clusters and typed transitions/events. Canonical serialization yields a semantic snapshot hash. Sealed replay must reproduce facts, ordering, edges, clusters and event reasons; a new profile produces a derived re-evaluation and never rewrites old Run evidence.

#### DP-20 — Historical AIS truth boundary

`HistoricalAISDatasetDescriptor` preserves provider, immutable raw digest, format/schema, selection, time/spatial extent, quality findings, attribution and coverage limitations. Raw AIS observations, normalized/derived artifacts, Historical Actor world truth and runtime Sensor/Tracker observations have separate identities and lineage. Historical Actors may use frozen future world trajectories as environment definition, but Planner receives only current Tracker output. T0 is versioned/reviewable and frozen on publication; Nominal Intent consumes timestamps strictly `< T0` and returns typed incomplete/failure when insufficient. Post-T0 Human Reference is sealed comparison-only and absent from RunSpec, Mission Route, Guidance, Planner, prediction and control state. Changing or deleting post-T0 Human Reference may change Compare similarity only; it must not change RunSpec, commands, realized counterfactual trajectory, threat evidence or independent evaluation. Large real archives stay external/content-addressed; CI commits compact fixtures.

#### DP-21 — Legacy rollout and capability evidence

An algorithm may consume the canonical snapshot only through the normal Session/Planner integration and only with explicit capability evidence for the required Lifecycle, prediction and accepted-plan facts. Missing facts become typed `UNAVAILABLE`/`INCOMPLETE` capability evidence or a fail-closed boundary; they never trigger a hidden fallback, algorithm substitution, second Lifecycle, local risk score or fake accepted receipt. Legacy algorithms may emit namespaced diagnostics but cannot publish competing canonical threat truth. Global rollout is accepted only after real-session, replay, no-fallback and upstream #24/#26/#27 checks; focused unit tests alone are insufficient.

### Historical benchmark contract

- Kystverket HAIS GeoParquet is first-class; CSV uses the same normalized contract. Predicate filtering should precede full materialization. Unit conversion is explicit and quality findings are retained.
- `HistoricalAISCase` freezes Dataset, Selection, Reconstruction, Discovery, Reference Vessel, Traffic Actors, ENCRegionProfile, T0 evidence, pre-T0 Nominal Intent, sealed Human Reference and Evaluation/Comparison bindings.
- Historical Replay validates ingestion/reconstruction through the normal Run/Simulator/Sensor/Tracker chain and is not an algorithm counterfactual claim.
- Counterfactual Run reuses the normal RunSpec/Algorithm/Guidance/Control/ship-model path, replaces only Reference Vessel post-T0 evolution, and leaves other Historical Actors in playback.
- Compare keeps Safety, COLREG Behavior, Maneuver Timing/Geometry, Efficiency and Human Similarity separate. Human Similarity uses a versioned alignment/metric contract and is advisory. Independent Evaluator verdicts remain authoritative.

### Issue mapping and execution order

| Issue | Contract slice | Blocked by |
|---|---|---|
| #30 TM1 | DP-06–DP-09, Threat Vector, domain evidence | none |
| #31 TM2 | DP-05, DP-10, DP-13, Lifecycle Primary | #30, #24 |
| #32 TM3 | DP-11–DP-12, schedule/events/Web projection | #31 |
| #33 TM4 | DP-14–DP-16, graph/cluster/replay | #32, #26, #27 |
| #34 AIS1 | DP-20 source descriptor/normalization/quality | none |
| #35 AIS2 | DP-20 Historical Actor and normal replay | #34 |
| #36 ENC1 | DP-20 qualified ENCRegionProfile/preflight | #34 |
| #37 AIS3 | DP-20 discovery and Published Case | #35, #36 |
| #38 AIS4 | DP-20 T0, pre-T0 intent, closed-loop handoff/leakage | #37 |
| #39 AIS5 | DP-16/20 independent Compare domains | #38, #32 |
| #40 INT1 | all frozen contracts and real-data system acceptance | #33, #39 |

Execution frontier is #30 and #34, then #31, (#35 + #36), #32, #37, #38, #39, #33 and #40 subject to the listed blockers. #33 remains blocked by upstream #26/#27.

## Testing Decisions

Tests verify immutable external behavior at the highest public seams; they do not mock private helpers, assert dataframe internals or reproduce risk formulas in the DOM. The user confirmed these seams:

1. `ThreatAssessment.evaluate(request) -> ThreatManagementSnapshot`.
2. `ThreatManagementCoordinator.cycle(...) -> ThreatManagementSnapshot`.
3. `HistoricalAISDatasetReader.read(selection) -> descriptor + normalized observations`.
4. `HistoricalAISCaseBuilder.build(request) -> HistoricalAISCaseBuildOutcome`.
5. Existing `SimulationSession`/`ExperimentRunner` and API/WS seams for Historical Replay, Counterfactual, leakage and Web projection.

Vertical TDD slices must cover independent domain oracles (inside, tangent, entry/exit, receding, low-speed unknown, uncertainty, generation), lexicographic priority and hysteresis, schedule replay, typed direct/plan-induced graph edges, raw/normalized AIS integrity, deterministic reconstruction, ENC fail-closed preflight, T0 equality, post-T0 leakage variants, real algorithm handoff, independent evaluation and five-domain Compare. Compact offline fixtures are mandatory; the real archive is a local smoke input, not a Git or CI dependency.

Focused checks, closed-loop checks, full pytest, Ruff/static/diff checks and real Web evidence are reported separately. A focused test or solver success is not full acceptance. Final acceptance requires #40 on a real qualified Kystverket multi-ship window with Dataset → Case → Run → Evaluation → Compare lineage and deterministic rerun.

## Out of Scope

- Legal COLREG certification, class/type approval, MASS release eligibility or proof of safe deployment.
- Replacing Encounter Lifecycle, L4 hard safety or Independent Evaluator authorities.
- A weighted/fuzzy score as the sole safety gate; a separate historical-AIS simulator; a browser risk engine; or a second evaluator pipeline.
- Controlling all historical traffic vessels with COLAV in V1, live AIS streaming, deep-learning intention inference, VHF reconstruction or nationwide automatic ENC qualification.
- Treating a human trajectory as optimal ground truth or bit-exact human similarity as success.
- Committing the large HAIS archive, importing an external repository wholesale, or using scenario-specific special cases, forced PASS, hidden fallback or threshold reduction.

## Scope Addendum — independent AIS multi-ship scene (2026-08-24)

This addendum is normative for the first front-end Historical AIS delivery. It narrows the initial catalog scope; it does not broaden the source archive or make a general HAIS claim.

### Published scene identity and modes

- Publish one independent catalog descriptor with ID `hais_romsdal_20260701_120000_120100`.
- Expose it through a dedicated Historical AIS catalog/workflow API. ~~The legacy `/api/scenarios` response remains the scripted YAML catalog and must not contain this ID.~~ *[Revised 2026-08-25: the merged catalog seam lists this ID (cheap source-presence gate) per ADR-0004.]*
- The descriptor represents one immutable Historical AIS selection and exposes two workflow modes: `HISTORICAL_REPLAY` and `COUNTERFACTUAL`. The mode is the only semantic branch; do not publish duplicate scenario IDs for the two modes.
- The descriptor is not a Rule 13/14/15 or generic `multiship` validation scene. ~~It must not be added to existing rule `supported_scenarios`, `verified_combinations`, `experimental_combinations`, or generic COLAV Create exact tuples.~~ *[Revised 2026-08-25: Counterfactual-only EXPERIMENTAL `multiship` tuples and ordinary Create are admitted per ADR-0004; the scene never enters `verified_combinations`.]* Existing YAML scenario files and existing exact tuples are compatibility surfaces and remain byte/identity stable.
- Existing scripted scenes (`head_on`, `overtaking`, `crossing_*`, `paper_ccta2023_multiship`, and `romsdal_busy_water_*`) remain unchanged and continue to use the existing Config assembly. The new scene is selected through a dedicated Historical AIS surface.

### Current source, window and actor-count boundary

The first descriptor is limited to the compact, qualified acceptance window already sealed in the repository fixture:

- Source entry: `hais_2026-07-01.snappy.parquet` from the local Kystverket HAIS archive; archive identity, entry identity, schema identity and selection identity remain content-addressed.
- Selection window: `2026-07-01T12:00:00+00:00` through `2026-07-01T12:01:00+00:00`, inclusive/exclusive according to the Historical AIS selection contract; bounding box `[6.05, 62.44, 6.17, 62.50]` in WGS84; selected source MMSIs `[257252000, 258764000, 259189000, 259197000]`.
- Published runtime actors: exactly three dimensioned actors, `[257252000, 258764000, 259189000]`; `259189000` is the Reference Vessel and `T0 = 2026-07-01T12:00:30+00:00`. The fourth selected MMSI is retained as source-selection provenance but is not silently promoted to a runtime actor.
- Current fixture evidence is 24 source rows, 24 normalized rows and 98 retained quality findings. These numbers describe this window only, not the 23-day archive or all HAIS traffic.
- ENC: `romsdal-expanded`, qualification `QUALIFIED`, with preflight required to pass and every selected runtime position contained. This qualification does not extend to the full archive, arbitrary larger windows or regions outside the profile.
- Vessel dimensions come from the named, versioned dimension registry. No default hull dimensions may be applied when a future selection lacks proof.
- HAIS coverage remains an AIS-reporting observation boundary: absent small craft or non-reporting vessels must not be interpreted as empty water. The descriptor must surface this limitation beside source/window/actor counts.

### Future expansion invariants

Future windows, entries, actors, dimension registries or ENC regions require a new Published Case/descriptor or an explicit versioned revision. Expansion must not mutate this descriptor's Dataset, Selection, T0, actor set, ENC qualification, digests or sealed evidence. Each expansion repeats source quality checks, actor reconstruction, dimension provenance and ENC preflight before it becomes selectable. A larger actor count is a new acceptance scope; it is not implied by the current three-actor result.

Conflict-cluster qualification is also a future gate, separate from scene operability. A later qualified window must produce its cluster evidence naturally through canonical Threat Management and reproduce it across independent runs. No descriptor, fixture, acceptance harness or browser projection may seal an expected cluster count of one, inject an edge/cluster, reinterpret `cluster_count=0` as one, or use the older sealed manifest's cluster value as an expected value for this scene.

### Current operational and qualification result

- The bounded scene is operational when its declared source binding and preflight are available: scene status `AVAILABLE`, scope `BOUNDED`. `AVAILABLE/BOUNDED` means this exact source/window/actor/ENC contract can run; it does not mean every predictive capability is qualified.
- The current Counterfactual evidence is two independent runs with deterministic status `PASS` and `mismatches=[]`. Workflow, Independent Evaluator and Compare complete; `fallback=false`; the independent evaluator gate and overall assurance verdict are `PASS` within the declared bounded scope.
- The canonical Threat result is `vector_count=2`, `schedule_entry_count=2`, `cluster_count=0`. Zero clusters is the observed result for this window and must remain visible as zero.
- Predictive vector/schedule evidence is available, but conflict-cluster qualification is `status=NOT_QUALIFIED`, `code=THREAT_EVIDENCE_INCOMPLETE`. This typed qualification gap does not make the bounded Replay/Counterfactual workflow unavailable or rewrite its completed evaluator/compare evidence.
- `ENC QUALIFIED` and the versioned engineering Ship Domain qualification remain facts owned by those profiles. They must not be projected as `Predictive Cluster QUALIFIED` or as an unqualified global scene claim.

### Front-end acceptance contract

- OpenBridge mounts the benchmark surface under a dedicated Historical AIS entry in `Evaluation` *[Revised 2026-08-25: the `Scenario`/`Algorithm` workfaces are deleted; scene browsing lives in Config Step 02, interactive playback in Deployment per ADR-0004]*; it does not alter existing Rule Config cards or their exact-tuple assembly.
- The panel shows source archive/entry, UTC window, WGS84 bounding box, selected and published actor counts, MMSI/Reference Vessel, T0, ENC profile/qualification, coverage limitation and readiness/digest state before run.
- `Historical Replay` invokes the historical workflow and renders playback/evidence. `Counterfactual` invokes the same immutable Case with post-T0 Reference Vessel control through the normal algorithm path; surrounding actors remain playback and Human Reference remains Compare-only.
- The panel consumes the backend REST/WS workflow snapshot and only formats/projects it. It must render typed unavailable/incomplete states and must never compute CPA, domain, Primary, schedule, clusters or verdicts in browser code.
- A front-end acceptance run must expose scene `status=AVAILABLE`, scope `BOUNDED`; completed workflow/evaluator/compare; `overall_assurance_verdict=PASS`; `leakage.status=PASS_CONTRACT`; `fallback=false`; threat counts `2/2/0`; double-run determinism `PASS` with `mismatches=[]`; and independent evaluator gate `PASS`. It must separately expose predictive cluster qualification as `THREAT_EVIDENCE_INCOMPLETE/NOT_QUALIFIED`. These claims are scoped to this bounded three-actor window; cluster qualification remains future work.

### Product capability boundary

- The product Config/API surface exposes only VO, Fan-MPC (`potocnik_colreg_fan_mpc`) and Mid-MPC (`mid_mpc_ipopt`) algorithms, each with the God tracker. The published capability catalog contains only those Product-Selectable Exact Tuples: 6 Rule 13 tuples, 3 Rule 14 tuples, 6 Rule 15 tuples and 3 Multiship verified tuples *[plus Historical-AIS/busy-water EXPERIMENTAL Multiship tuples after the 2026-08-25 revision]*.
- `/api/capabilities` publishes the product policy identity and allowlists alongside the filtered exact tuples, so a client need not infer the product boundary from registry entries or a Cartesian product.
- Nominal, SB-MPC, Potočnik simplified MPC, KF and scenario-default tracker implementations may remain in the runtime registry for internal Historical Replay, evaluator baselines and compatibility fixtures. They are Internal Legacy Tuples: product session validation returns typed `INVALID_INPUT`, and they do not appear in `verified_combinations`, `experimental_combinations` or `selectable_combinations`.
- Busy-water experimental evidence is similarly restricted to the three product algorithms with God; the 80-ship stress scene has no Mid-MPC experimental tuple until separately qualified.
- Historical Replay may continue to use Nominal internally because it is playback, not a product-selectable COLAV validation session. Counterfactual runs use the published product algorithm binding and God tracker.

## Further Notes

The repository glossary in `CONTEXT.md` and ADRs 0001–0003 define the shared vocabulary and authority boundaries. The existing design log records how DP-01–DP-04 were confirmed and how DP-05–DP-21 were frozen for implementation. Research citations in the offline attachment remain background; no external claim supersedes the project contracts above. This document is the implementation source of truth after the original attachment and issue body are synchronized.

## Addendum 2026-08-25 — Product Catalog Integration (ADR-0004)

The scene-visibility boundary above is revised by user decision: the canonical
Historical AIS scene now also enters the product Config catalog as
Counterfactual-only EXPERIMENTAL tuples (`multiship × hais × product algorithm ×
god`), and `POST /api/sessions` creates an ordinary Active Session that
Deployment plays back. Verified tuples, the YAML corpus, the product capability
policy, and the headless Historical Workflow evidence authority (double-run
qualification/determinism/Compare) are unchanged. See
`docs/adr/0004-historical-ais-scene-in-product-catalog.md`.
