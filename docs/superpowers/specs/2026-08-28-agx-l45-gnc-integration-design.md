# Modular Hydrodynamics, Guidance, and Control Stack

Status: ready for agent decomposition — amended 2026-08-31 after independent design review; the Review Amendments (RA-01..RA-14) at the end of this document are binding for decomposition and implementation

Published issue: https://github.com/marinehdk/colav-simulator/issues/41

Authoritative technical decisions, evidence, terminology, and acceptance boundaries are defined in the companion solution pack: `2026-08-28-agx-l45-gnc-integration-solution-pack.md`.

## Problem Statement

The simulator can already switch among several ship models, guidance algorithms, and controllers, but its public ship execution chain is centered on a legacy 3DOF, array-based, single-rate contract. A colleague's ROS 2 Humble/C++ L4-5 source contains a 4DOF plant, wind/wave/current load engines, a controller described as PID but combining several control techniques and policies, a large ILOS/ALOS guidance implementation, thrust allocation, and actuator dynamics.

The user needs these ideas available for debugging and comparison without copying the source architecture or preserving designs that are unreasonable, over-constrained, vessel-specific, scenario-specific, or weakly evidenced. The integration must protect every existing model, guidance, controller, scenario, evaluator, and COLAV algorithm. New capabilities must be explicit options, not replacements or hidden fallbacks.

The recovered source and evidence also have hard limits. The source-only baseline has no Git identity, its current remote source has diverged, tests and validation evidence are not version-identical to the source-only export, environmental coefficients are mock or inferred, real vessel RAO/QTF data are unavailable, and several historical guidance/control candidates were rejected or never promoted. The project therefore needs a content-addressed migration and redesign workflow that distinguishes source characterization from physical validation and generalized product behavior.

## Solution

Add an opt-in `modular_gnc_stack` alongside the frozen legacy execution path. The modular stack presents one high-level facade with reset, step, and snapshot operations. Internally, a deterministic scheduler composes typed Environment, Plant, Guidance, Controller, Allocator, and Actuator modules. Inputs, outputs, snapshots, errors, capabilities, assets, plans, tasks, and diagnostics use explicit typed contracts. Continuous plant dynamics expose a pure right-hand-side function and use one externally owned fixed-step RK4 integrator. Stateful guidance, control, observer, actuator, and random-process updates occur once at their declared integer tick.

The default implementation is Python for debuggability. Frozen C++ behavior supplies characterization fixtures and may later become an optional same-interface native adapter only after profiling proves a need. ROS 2 remains an external system adapter. FMI/FMU work is deferred.

Existing configurations and code paths remain unchanged. New module, preset, asset, capability, fidelity, and acceptance metadata are registered only under a new opt-in configuration section. The first implementation slice is the compatibility contract layer: typed values, the `ModularShipStack` facade, a `ModularShipAdapter` bridge that satisfies the existing `IShip` interface, the `CommandInput` facade contract, the opt-in configuration section, a minimal registry v1, and the frozen-commit legacy regression baseline harness (RA-01, RA-02, RA-04, RA-10). Subsequent slices add environmental loads and generic 3DOF/4DOF plants followed by a mandatory performance checkpoint (RA-03), then a clean marine PID, a clean ILOS option, actuator-resolved control, a tracked-route planner seam, and finally the ROS 2 adapter.

## User Stories

1. As a simulator user, I want every existing scenario to retain its current model, guidance, controller, and execution path unless I explicitly select the modular stack, so that current experiments do not regress.
2. As an algorithm developer, I want to select new hydrodynamic, guidance, and control modules independently, so that I can compare combinations without modifying source code.
3. As an experiment owner, I want every selected module and implementation identity recorded, so that results cannot be attributed to the wrong algorithm.
4. As a debugging engineer, I want a single high-level ship-stack step interface, so that I do not need to understand internal scheduler phases to run an experiment.
5. As a module developer, I want stable typed internal interfaces, so that I can replace one implementation without changing callers.
6. As a numerical developer, I want the complete plant state available for snapshot and replay, so that roll and roll-rate are not hidden inside mutable model state.
7. As a COLAV developer, I want a stable 3DOF navigation projection, so that existing collision-avoidance and tracking algorithms do not need to understand roll dynamics.
8. As a validation engineer, I want projection loss declared explicitly, so that a 3DOF result is not mistaken for complete 4DOF acceptance.
9. As a hydrodynamics developer, I want separate mass, Coriolis, damping, restoring, shallow-water, actuator-load, and environmental-load responsibilities, so that each physical contribution can be verified independently.
10. As a hydrodynamics developer, I want mass, Coriolis, damping, and restoring contracts checked at configuration and test time, so that non-physical parameter combinations fail early.
11. As a simulator user, I want wind, current, first-order wave, and mean-drift loads reported separately, so that I can identify which environment source caused a response.
12. As an experiment owner, I want current-relative damping and external current loads checked for duplication, so that the same current is not applied twice.
13. As a wave-model user, I want the wave mode selected explicitly, so that mean drift is not silently substituted for first-order loading.
14. As a vessel-model user, I want environmental and hydrodynamic assets to carry provenance, trust, applicability, uncertainty, and license metadata, so that software fixtures are not confused with vessel-validated data.
15. As a user selecting an asset-backed mode, I want missing or out-of-domain assets to fail explicitly, so that mock or inferred data are not silently substituted.
16. As a control developer, I want a clean marine PID option, so that PID behavior can be understood without hidden SMC, NDO, scheduling, or scenario policies.
17. As a control researcher, I want NDO, SMC, and scheduled PID to have separate identities and evidence, so that advanced techniques can be compared fairly.
18. As a controller tuner, I want P, I, D, feedforward, raw output, achieved output, saturation, and anti-windup correction traced separately, so that tuning failures are attributable.
19. As a controller developer, I want anti-windup to use achieved generalized load when available, so that allocator saturation does not accumulate hidden integral error.
20. As a mission developer, I want transit, pose hold, controlled stop, and manual load to be explicit tasks, so that a zero speed is not incorrectly interpreted as dynamic positioning.
21. As a configuration author, I want controller tasks checked against plant and actuator capabilities, so that an underactuated ship cannot select an impossible pose-hold mode.
22. As a guidance developer, I want the existing LOS and KTP options preserved, so that new work does not modify accepted guidance behavior.
23. As a guidance developer, I want a clean ILOS option with explicit route progress, cross-track error, lookahead, integral state, and reset behavior, so that it can be tested without historical policy gates.
24. As a route developer, I want route geometry, speed profile, terminal-task policy, and environment compensation separated from the ILOS law, so that each concern can evolve independently.
25. As a COLAV developer, I want planners to declare whether they produce a direct reference or an accepted tracked route, so that guidance authority is unambiguous.
26. As a COLAV developer, I want predicted trajectories kept separate from accepted routes, so that a visualization or optimizer horizon is not accidentally executed as a command route.
27. As a runtime engineer, I want route identity, revision, validity, continuity, and handoff metadata enforced, so that stale or discontinuous routes are rejected.
28. As a disturbance-compensation researcher, I want plant truth separated from guidance and controller estimates, so that experiments do not rely on impossible perfect environment knowledge.
29. As a disturbance-compensation researcher, I want explicit compensation options and ablation tests, so that guidance, feedforward, NDO, and integral compensation do not duplicate one another.
30. As an actuator researcher, I want both ideal generalized-load and resolved-actuator fidelity profiles, so that control-law debugging and actuator feasibility are not conflated.
31. As a vessel integrator, I want actuator layout, curves, limits, delays, rates, effectiveness, and failure modes represented as data assets, so that the allocator is not tied to one seven-actuator vessel.
32. As a control developer, I want requested, achieved, residual, and saturated loads returned by allocation, so that command feasibility is observable.
33. As a simulation engineer, I want one integer-tick simulation clock and fixed scheduler phase order, so that wall-clock load cannot change the physics.
34. As a simulation engineer, I want multi-rate guidance, control, allocation, actuator, environment, and plant execution with explicit zero-order hold, so that source rates can be characterized without becoming permanent algorithm constants.
35. As a numerical engineer, I want one externally owned RK4 integrator and a pure plant derivative, so that double integration cannot occur.
36. As a numerical engineer, I want controller, observer, guidance, actuator, and random-process state excluded from RK stages, so that one physical tick does not update discrete state four times.
37. As an experiment owner, I want reset, new-instance execution, and snapshot restore to produce the same trace under the same seed, so that episode results are reproducible.
38. As a multi-ship user, I want every ship's plant and GNC state isolated, so that controller integrals, random streams, and route progress cannot leak between vessels.
39. As a multi-ship user, I want ship-order and serial/parallel execution equivalence, so that list ordering and optimization do not change results.
40. As a developer, I want stale, duplicate, out-of-order, non-finite, unsupported, and out-of-domain inputs to produce structured failures, so that bad state is not disguised as a successful run.
41. As a developer, I want a failed tick to avoid partially committing state, so that replay and diagnosis remain meaningful.
42. As a performance engineer, I want Python profiling and vectorization attempted before native acceleration, so that the code remains easy to debug.
43. As a performance engineer, I want an optional C++ implementation to use the same interface and fixtures, so that acceleration cannot change semantics.
44. As a ROS 2 integrator, I want the ROS adapter to materialize tick-indexed typed inputs and expose QoS and freshness failures, so that DDS behavior does not enter the core physics implicitly.
45. As a release engineer, I want new native and ROS dependencies to remain optional, so that legacy users do not need them.
46. As a UI user, I want only compatible module combinations shown, so that impossible configurations cannot be selected.
47. As a UI user, I want module maturity, fidelity, asset trust, and acceptance level displayed separately, so that an experimental mock model is not shown as verified.
48. As an evidence reviewer, I want source, configuration, test, asset, compiler, seed, and fixture hashes recorded, so that cross-version evidence cannot be mixed.
49. As an evidence reviewer, I want migration parity and intentional redesign reported separately, so that a source difference is either an error or an explicit decision.
50. As an assurance reviewer, I want hydrodynamics, guidance, control, actuator, COLAV, multi-ship, ROS/SIL, vessel calibration, and sea-trial evidence reported separately, so that no focused gate becomes a global acceptance claim.
51. As a project maintainer, I want every source behavior classified as invariant, vessel parameter, runtime adapter, experimental candidate, or rejected specialization, so that historical complexity is not copied wholesale.
52. As a project maintainer, I want every retained or removed historical behavior linked to characterization and ablation evidence, so that simplification does not reintroduce known failures.
53. As a project maintainer, I want the modular stack delivered in small reviewable slices, so that each module can be verified and reverted independently.
54. As a user of the existing simulator, I want the old configuration format and default path unchanged, so that installing a newer version does not alter my results.

## Implementation Decisions

- The accepted architecture is a deep `ModularShipStack` facade with reset, step, and snapshot operations.
- A deterministic private scheduler composes typed EnvironmentField, EnvironmentalLoadModel, VesselPlant, PathGuidance, MotionController, ThrustAllocator, and ActuatorModel modules.
- Facade inputs, outputs, failures, diagnostics, and snapshots are immutable typed values. Modules may use private efficient state but must support complete snapshot and restore.
- Ticks commit atomically. A failed phase must not partially advance plant, guidance, control, allocation, actuator, random, or route state.
- The legacy ship stack remains the default and is not routed through the modular scheduler.
- The modular stack is selected only through a new opt-in module configuration section.
- Existing model, guidance, controller, scenario, evaluator, and COLAV identities are preserved.
- The new stack uses a single integer-tick simulation-time authority and fixed phase order.
- Multi-rate periods are exact integer tick ratios. Non-due references and commands use explicit zero-order hold.
- The initial characterization profile may use 50 Hz plant/environment, 10 Hz control, and 2 Hz guidance, but rates belong to profiles rather than algorithm identities.
- The complete PlantState is capability-aware and may be 3DOF or roll-4DOF.
- A stable typed 3DOF NavigationState is produced by an explicit projection for legacy COLAV, tracking, evaluation, and display consumers.
- Core planar coordinates are North-East. The 3D world frame is NED. Body axes are forward, starboard, down. Heading, yaw rate, yaw moment, and roll are right-positive. Core units are SI.
- External frames, directions, degrees, knots, ROS messages, and legacy arrays are converted only by adapters.
- The plant exposes a pure right-hand-side derivative. One externally owned fixed-step RK4 integrator advances continuous plant state.
- RK stages do not advance controller, observer, guidance, actuator, or random-process discrete state.
- Physical actuator limits remain in the actuator model. The plant does not silently clip velocity, clip yaw rate, reset state, or replace non-finite values with zero.
- A validity monitor reports or terminates on invalid matrices, non-finite values, integration failure, and out-of-domain state without rewriting plant truth.
- Environment truth is separate from environment observations and estimates. The plant consumes truth; guidance and control consume observations or estimates.
- Environment field data are separate from vessel-specific environmental load calculations.
- Wind, current, first-order wave, and mean-drift loads retain separate identities through diagnostics and testing.
- Current-relative damping and external current-load strategies require an explicit de-duplication contract.
- Wave modes are explicit. Missing required RAO, QTF, coefficient, or vessel data cause configuration or runtime failure rather than silent substitution.
- Asset trust uses mock, inferred, calibrated, and validated-for-vessel levels with provenance, hashes, licenses, uncertainty, and applicability domains.
- Generic 3DOF and roll-4DOF maneuvering plants are new options. Existing plants are not modified.
- Mass matrices must be finite, symmetric, and positive definite. Coriolis behavior must be energy-consistent. Damping must be dissipative over its declared domain. Roll restoring behavior must be stable around its declared equilibrium.
- The first new control option is a clean marine PID with derivative on measurement, a time-step-aware derivative filter, one tracking anti-windup strategy, achieved-load feedback, and full term diagnostics.
- NDO, SMC, and gain-scheduled PID are separate future algorithm identities, not feature flags hidden inside PID.
- Control tasks are explicit transit, pose-hold, controlled-stop, and manual-load values.
- Task support is checked against controller, plant, allocator, and actuator capabilities before execution.
- Transit and pose-hold controllers are distinct implementations or policies with explicit bumpless transition rules.
- Ideal generalized-load and resolved-actuator fidelity profiles are explicit and separately reported.
- Actuator layouts and characteristics are data assets, not fixed array ordering in generic code.
- Allocation returns requested, achieved, residual, active constraints, saturation, and degraded status.
- Existing LOS and KTP guidance options remain unchanged.
- A new clean ILOS option contains only route projection, route progress, lookahead, signed cross-track error, integral behavior, course/heading reference, speed ceiling, reset, and trace semantics.
- Route smoothing, speed policy, terminal-task policy, and environment compensation remain separate from the ILOS law.
- Planner outputs explicitly declare direct-reference or tracked-route capability. These authorities are mutually exclusive.
- Accepted routes carry identity, revision, validity, continuity, speed ceilings, terminal task, and acceptance status.
- Predicted trajectories are not converted automatically into accepted routes.
- Plant truth is unavailable to GNC by default. Perfect environment knowledge is a separately identified debugging estimator.
- Explicit guidance compensation, controller feedforward, and NDO are disabled by default as combinations. Combined compensation requires frequency ownership, de-duplication, and ablation evidence.
- Each ship owns all mutable plant and GNC state. Shared environment fields and assets are immutable and order-independent.
- The Python implementation is the default product implementation.
- Frozen C++ behavior is used to build characterization fixtures. A C++ native adapter is added only after profiling and must share the same contract and fixtures.
- The ROS 2 Humble integration is a peripheral adapter driven by simulation time. Core state is not advanced by ROS wall timers.
- FMI/FMU integration is deferred.
- Module registry entries declare identity, implementation and interface versions, capabilities, required assets and dependencies, supported tasks and fidelity profiles, parameter schema, diagnostic schema, and maturity.
- Configuration precedence is defaults, then preset, then controlled scenario overrides. Episode configuration is normalized, frozen, and hashed.
- Unsupported combinations fail as invalid input. Valid combinations with missing dependencies or assets fail as dependency unavailable. Neither case falls back.
- Every historical source behavior is classified with an evidence card before it can become a default capability.
- Implementation proceeds in additive vertical slices: compatibility contracts, environment, plant, marine PID, ILOS, resolved actuators, tracked routes, and ROS adapter.

## Testing Decisions

- The highest public test seam is the `ModularShipStack` reset, step, and snapshot interface.
- Tests assert external behavior, state transitions, structured failures, diagnostics, hashes, and acceptance claims rather than private helper call sequences.
- Stable internal module interfaces are additional characterization seams for numerical attribution, not extra application-facing APIs.
- Legacy regression tests run with no modular configuration and must prove the old execution path, identities, results, and error semantics remain unchanged.
- Interface tests cover shape, dtype, finite values, frames, units, capability declarations, plan authority, task support, and error classification.
- Basis-vector tests prove North-East/NED and body-frame transformations, right-positive heading/yaw/roll/load conventions, and from/to conversion.
- Snapshot tests prove new-instance, reset, restore, and repeated same-seed executions have equivalent per-tick traces.
- Multi-ship tests prove ship-order permutation, state isolation, seed isolation, and serial/parallel equivalence.
- Physics tests cover mass symmetry and positive definiteness, Coriolis power neutrality, damping dissipativity, restoring stability, zero-input equilibrium, left/right mirror behavior, and invalid-parameter rejection.
- Environmental tests cover zero loads, each source independently, declared load summation, current de-duplication, wave modes, first-order time-step convergence, asset absence, asset domain, and trust reporting.
- Integrator tests cover all RK stages, stage-time environment forcing, one update per discrete tick, fixed-step convergence, and prevention of double integration.
- Controller tests cover step response, reference jumps, heading wrap, variable time steps, saturation and release, positive and negative saturation, reset, task transitions, achieved-load anti-windup, and term-level diagnostics.
- Guidance tests cover route progress, route switching, ILOS integral behavior, reset, large initial cross-track error, straight routes, turns, current disturbance, terminal tasks, route revision, route expiry, and rejected discontinuities.
- Planner seam tests prove direct-reference and tracked-route paths are mutually exclusive, predicted trajectories are not executed as routes, and only one command authority is active.
- Allocation tests cover layout permutations, multiple vessel layouts, infeasible requests, residuals, saturation, rate limits, failures, health, and underactuated task rejection.
- Fidelity tests compare ideal generalized load against resolved actuator behavior without treating either as the other's acceptance proof.
- Compensation tests use no-compensation baselines and one-option-at-a-time ablations before any combined compensation experiment.
- Characterization fixtures bind source, configuration, tests, assets, compiler, dependencies, seeds, and expected values by content hash.
- C++ and Python comparisons cover load components, derivatives, RK stages, controller internal state, guidance state, actuator state, requested and achieved loads, and diagnostics.
- Intentional redesign tests record the source behavior, evidence of its problem, new behavior, affected fixtures, updated contract, and cross-vessel result.
- Performance tests record real-time factor, per-module p50/p95/max duration, memory, vessel count, wave-component count, platform, compiler, and dependency hashes.
- Performance work must not drop ticks, modify time steps, change reduction order, or introduce order-dependent random behavior.
- ROS adapter tests cover QoS incompatibility, stale and out-of-order messages, duplicate messages, process termination, reset, and simulation-time ownership.
- Acceptance uses separate G0–G10 gates for source integrity, interfaces, physics, migration parity, redesign, module closed loop, legacy regression, cross-vessel generality, COLAV integration, actuator fidelity, and ROS/SIL.
- Acceptance claims use separate A1–A7 levels. The first implementation target is A1 through A3 only.
- Focused tests, smoke tests, source parity, closed-loop guidance, COLAV safety, multi-ship safety, vessel calibration, ROS/SIL, and sea-trial evidence are reported separately.
- Existing tests for ship composition, models, controllers, guidance, simulation, capability validation, and closed-loop scenarios are prior art for legacy and module behavior.
- Recovered environment pure-model baselines, mass/Coriolis/damping properties, controller helper tests, guidance policies, PGD tests, actuator-curve tests, and campaign traces are prior art for characterization, with their documented version and applicability limits.

## Out of Scope

- Replacing, deleting, or behaviorally refactoring the legacy GNC stack.
- Automatically migrating old YAML configuration to the modular stack.
- Copying all ROS 2 packages or the giant source guidance/controller loops into the new core.
- Treating source parity as proof that source behavior is reasonable or general.
- Treating mock or inferred environmental assets as calibrated vessel hydrodynamics.
- Claiming target-vessel accuracy before appropriate CFD, tank, maneuvering-trial, or full-scale evidence exists.
- Implementing SMC, NDO, scheduled PID, adaptive LOS, or combined multi-band disturbance compensation in the first slice.
- Implementing resolved actuator fidelity before ideal generalized-load plant and controller behavior is stable.
- Making ROS 2 or a native extension a default installation dependency.
- Implementing FMI/FMU support in the first program of work.
- Implementing HIL, real-vessel deployment, regulatory certification, or sea-trial acceptance under this spec.
- Changing COLREG decision logic, threat management, or existing COLAV algorithm semantics.
- Publishing unsupported algorithm/module combinations in the UI.
- Optimizing by dropping simulation ticks, changing numerical time steps, silently switching backends, or loosening tolerances to obtain passing results.

## Further Notes

- The user confirmed full authority to modify, develop, and optimize the AGX L4-5 code. Formal license, notice, source, and asset provenance still need normalization before distribution.
- The source-only export and recovered evidence are stored outside the Git repository to prevent accidental inclusion.
- The source-only baseline is content-addressed because the source workspace has no Git identity.
- Current remote tests and formal source are not version-identical to the source-only baseline. Version-aligned characterization fixtures must be created before migration parity claims.
- An archived validation contract uses a different body/yaw convention from current source descriptions. Adapters require executable basis-vector characterization rather than comment-based assumptions.
- Real RAO/QTF, target-vessel hydrodynamic validation data, actual actuator data, environment-estimator capabilities, and final multi-ship performance targets remain external-data gaps. They do not block A1 through A3 but limit later claims.
- This spec is intentionally large and should be decomposed into blocker-aware implementation tickets before coding.

## Review Amendments (2026-08-31, binding)

Added after an independent senior review of the accepted design against the current codebase. All [R7] legacy-seam claims were verified true at line level (see design log 2026-08-31 entry). No existing VR/TS/ALT/G/A decision is overturned; these amendments close specification-coverage gaps only. RA IDs are the reference for ticket decomposition and acceptance.

### P1 — must be reflected in tickets before/at slice 1

- **RA-01 `ModularShipAdapter(IShip)` bridge is a required deliverable of slice 1.** `Simulator.step` and all downstream consumers (evaluators, web GUI telemetry, decision replay) consume the full `IShip` interface (`colav_simulator/core/ship.py:218-456`: `plan`, `track_obstacles`, `get_sim_data`, `set_references`, `reset`, `set_colav_system`, ...) and the `get_sim_data` dictionary schema (including tracker fields `do_estimates`/`do_NISes`/`csog_state`). The modular stack exposes only `reset/step/snapshot`, so an adapter is mandatory for any modular ship to run inside a scenario. Adapter mapping: `forward(dt, w)` → `stack.step`; `NavigationState` projection → legacy 6-array state; `set_references` (9x1) → `CommandInput` direct reference; `plan`/`track_obstacles`/sensor plumbing delegate to the existing legacy-side COLAV and tracker objects (not reimplemented); the AIS historical-trajectory branch (`ship.py:629`, which overwrites state directly without a model) bypasses the stack entirely. Without this slice, gates G6/G7/G8 cannot execute.
- **RA-02 `CommandInput` facade input contract must be pinned in slice 1.** A discriminated union per simulation tick: `TrackedRoute | DirectReference | None`. Rules: planner runs outside the facade at the simulation tick (current `Simulator.step` order); its output is latched at the tick boundary and consumed at the guidance phase; `DirectReference` authority bypasses `PathGuidance` with zero-order hold at the control rate (declare which latched tick the 10 Hz controller holds); route vs direct reference are mutually exclusive per tick (extends TS-18 to the facade boundary); route rejection/expiry at the facade produces a structured failure or explicit hold, never a silent fallback.
- **RA-03 Performance checkpoint is mandatory immediately after the environment+plant slice, not later.** Record real-time factor, per-RHS and per-stage p50/p95, and wave-harmonic-count scaling for at least 1/5/20 ships (TS-26 metrics). Go/no-go review for vectorization or a native adapter happens before A2 migration parity is claimed for the plant. Budget reference: 50 Hz plant x RK4 x 4 stages = 200 derivative evaluations per ship per simulated second; first-order wave superposition over many harmonics at stage time is the expected dominant cost.
- **RA-04 G6 legacy baseline must be anchored to a pinned commit before any modular code lands.** The baseline capture script (existing test suite + per-tick trace digest on reference scenarios) is a slice-1 deliverable; fixtures bind to the pinned commit via TS-27 content hashes. The anchor commit is fixed when the execution worktree is created; unrelated dirty work in the main checkout (decision-replay and COLAV-core edits as of 2026-08-31) must be either landed or explicitly excluded by the user before pinning. The main checkout is 308 commits ahead of `origin/main`; do not push or rebase as part of this work.

### P2 — handle during decomposition/tickets

- **RA-05 NavigationEstimate seam reservation.** The typed `NavigationState` consumer interface distinguishes truth-projection from estimate from day one (type-level or field-level marker). A1–A3 use the truth projection; A4+ sensor/estimator work must not break the interface.
- **RA-06 Per-COLAV route-output audit is a precondition of the tracked-route slice.** Audit each planner's output shape (`mid_mpc` rolling plan already carries accepted/revision/expiry/recovery lifecycle at `colav_simulator/core/colav/rolling_plan.py:124`; sbmppc/rrt/psbmpc differ). First connection target is the Mid-MPC rolling-plan lifecycle; all other planners stay on the direct-reference path.
- **RA-07 Characterization fixture generation pipeline is an explicit deliverable, not an assumption.** C++ fixtures are built from the frozen source-only v2 baseline on Linux/AGX or in a container; outputs are JSON/NPZ plus SHA-256 (source, config, compiler, seeds per TS-27) committed for consumption; the build recipe is documented once and reused. Operational risk is tracked as a single point of failure.
- **RA-08 Legacy-equivalent profile for G8 attribution.** The modular stack must be runnable in a profile equivalent to legacy execution (kinematic plant + pass-through controller) so G8 experiments can attribute differences: (a) legacy path, (b) modular legacy-equivalent profile, (c) modular new plant + pass-through, (d) modular new plant + marine PID. The existing COLREGs probe suites (single/8/12-probe, rule13/14/15 sweeps) are the G8 harness.
- **RA-09 Facade failure-to-simulator policy mapping is a slice-1 decision.** Each structured facade error code maps to a `Simulator.step` behavior: abort episode (default), skip ship, or explicit degraded-continue experiment config. No unmapped error may be swallowed.
- **RA-10 Registry v1 is minimal.** Slice 1 registry entries carry identity, implementation/interface version, capabilities, and parameter schema only. Maturity, diagnostic-schema, and asset-trust display fields are added when their consumers exist. Schema growth must not become slice 1.

### P3 — record, apply at the relevant slice

- **RA-11 DP-19 scope note.** The COLAV planner layer keeps consuming environment truth (`simulator.py:413` passes `w=disturbance_data` to `plan()`). DP-19 covers only guidance/control/allocation inside the modular stack. A4 COLAV claims must state that the planner layer remains truth-fed in both stacks.
- **RA-12 Roll is unactuated in the roll-4DOF plant.** Allocator/actuator capabilities must not declare a roll moment channel for it; roll dynamics are restoring-dominated.
- **RA-13 Plant input-domain capability.** Plants declare input semantics (generalized-force input vs `[chi_d, U_d]` reference input, cf. `KinematicCSOG`). Configuration must reject `marine_pid` × kinematic-reference plant as an invalid combination; negative test required.
- **RA-14 UI slice precedes the A3 demo.** Compatible-combination filtering and maturity/fidelity/trust display (stories 46–47) are a scheduled slice before any A3-level demonstration, not an afterthought.

### Revised implementation order

1. Slice 1 — typed values + `ModularShipStack` facade + `ModularShipAdapter(IShip)` + `CommandInput` contract + opt-in `ship_modules` configuration section + registry v1 + G6 baseline harness + failure-policy mapping (RA-01/02/04/09/10). Contracts only, no physics kernels.
2. Slice 2 — EnvironmentField/EnvironmentalLoadModel.
3. Slice 3 — generic 3DOF/roll-4DOF plants + external RK4 scheduler wiring.
4. Checkpoint — mandatory performance spike and go/no-go (RA-03).
5. Slice 4 — `marine_pid`.
6. Slice 5 — clean ILOS.
7. Slice 6 — actuator-resolved allocator/model.
8. Slice 7 — COLAV tracked-route seam (precondition: RA-06 audit).
9. Slice 8 — ROS 2 adapter.
