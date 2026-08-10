# Mid-MPC Colav-Native Integration Surface

Audit baseline: Colav-Simulator branch state on 2026-08-10. This document fixes
the integration and acceptance boundary only; it does not define or implement
the translated IPOPT formulation.

## Decision

Implement Mid-MPC behind the strict in-tree custom-MPC contract:

```text
Ship.plan
  -> CustomMPCAdapter.plan
  -> MidMPC facade.solve(PlannerInput)
       -> Colav-native route and encounter normalization
       -> pure IPOPT core
  -> MPCSolution
  -> 9x1 controller reference and versioned planner trace
```

The public seam remains exactly `solve(PlannerInput) -> MPCSolution`. Use
`colav_simulator/core/colav/custom_mpc_adapter.py`; do not extend the legacy
guidance adapter in `colav_simulator/guidance/custom_mpc_adapter.py`.

The optimizer core must not know about ROS2, MASS-L3 messages, M4/M6/M7,
BC-MPC, GNC publication, ENC, scenario IDs, or another fallback planner. A
small integration facade may translate Colav-native route and encounter facts
into the frozen Mid-MPC numerical input. Translation and later calibration
must remain separate changes.

## Exact Public Contract

`Ship.plan` supplies the current route, speed plan, six-state ownship, tracker
output, vessel geometry, and simulation step to `ICOLAV.plan`
(`colav_simulator/core/ship.py:567`). The adapter converts that call into:

- `PlannerInput`: ENU metres, SI units, radians; `waypoints_enu_m` is `2xN`,
  `speed_plan_mps` aligns with it, `ownship_state` is
  `[x,y,psi,u,v,r]`, and each `TrackedObstacle.state_enu` is
  `[x,y,Vx,Vy]` with covariance, dimensions, age, and degradation state
  (`colav_simulator/core/colav/custom_mpc_adapter.py:195`, `:229`).
- `MPCSolution`: finite `control_reference` `9x1`; finite
  `predicted_trajectory` `9xN`; optional executable `control_trajectory`
  `9xN`; normalized status, feasibility, objective, iterations, constraint
  evidence, target predictions, and JSON-safe algorithm details
  (`colav_simulator/core/colav/custom_mpc_adapter.py:282`).
- State layout: `[x,y,psi,u,v,r,x_ddot,y_ddot,psi_dot]`. Horizon column zero
  must match the solve-time ownship within the descriptor's position, heading,
  and velocity tolerances. Horizon length and `horizon_dt_s` must match the
  descriptor, and translational continuity is checked
  (`colav_simulator/core/colav/custom_mpc_adapter.py:691`).

The facade should return the optimizer's first executable course/speed as the
`control_reference`, while retaining column zero as the current state in the
predicted horizon. When the optimizer exposes a distinct sequence of commands,
put it in `control_trajectory`; otherwise adapter hold steps sample the state
prediction.

## Scheduling, Failure, and Trace Semantics

`CustomMPCAdapter` owns solve scheduling. It solves at the first call and when
`sim_time >= last_solve_time + solve_period`; intermediate calls sample and
hold the last executable trajectory (`custom_mpc_adapter.py:405`, `:638`). The
solve period must be an integer multiple of `dt_sim_s`, simulation time cannot
move backwards, and the horizon must cover the next solve time (`:512`). Mid-MPC
must not add a second wall-clock or simulation-time scheduler.

Adapter-owned behavior:

- Missing imports become `DEPENDENCY_UNAVAILABLE`; unexpected solver failures
  become `NUMERICAL_FAILURE`; malformed results remain distinct invalid-output
  failures (`:535`).
- Deadline enforcement converts a late feasible success to
  `TIMEOUT_FEASIBLE`; repeated timeouts beyond the descriptor limit fail stop.
  `INFEASIBLE`, non-feasible success, and other non-success statuses also fail
  stop. No fallback is permitted.
- Every actual solve increments `solve_id` and records `solver_executed=true`;
  hold steps keep the same id and record `solver_executed=false`. Diagnostics
  preserve requested/executed identity, elapsed time, iterations, objective,
  descriptor/build hashes, constraints, predictions, selected command, and
  algorithm details (`:595`, `:663`).

Populate Mid-MPC evidence through existing fields rather than a side channel:
IPOPT return status, iteration count, objective and objective terms, active or
tight constraints, collision/CPA slack, warm-start use, and target prediction
model belong in `MPCSolution` fields. Include a stable formulation/baseline
identifier in `algorithm_details`.

## Reusable Colav-Native Inputs and Decisions

Reusable shared surfaces:

- `PlannerInput` and `TrackedObstacle` are the authoritative situational input.
  Tracker selection remains owned by `IntegrationRegistry` and the scenario
  runner; Mid-MPC consumes tracks and does not instantiate a tracker.
- `LOSGuidance.compute_references` is the existing shared, stateful route and
  speed decision. It selects the active waypoint segment and returns native
  course/speed references (`colav_simulator/core/guidances.py:531`). A facade
  may own one `LOSGuidance` and feed its `chi_d`/`U_d` to the pure optimizer.
- `instantaneous_cpa`, `velocity_ne`, and `classify_geometry` provide the
  existing constant-velocity CPA convention and geometric labels
  (`colav_simulator/evaluation/encounter.py:45`, `:59`, `:125`). They are useful
  deterministic inputs, but currently live under evaluation rather than a
  planner-domain service.

No repository-wide runtime encounter-decision service exists. In particular:

- `PairwiseColregFSM` is evaluator-owned and profile/stage driven; it is not
  injected through `PlannerInput`.
- Potocnik's `_route_guidance`, `_encounter_policy`, target prediction,
  maneuver phase, stand-on lock, and return logic are private policy inside
  `PotocnikColregFanMPC` (`colav_simulator/integrations/potocnik_colreg_mpc.py:406`,
  `:736`, `:784`, `:949`).
- VO and SB-MPC likewise keep commitment, recovery, and rule policy inside
  their algorithm implementations.

Therefore the Mid-MPC facade may reuse LOS guidance and the shared geometric
CPA/classification functions, but must not import private Potocnik, VO, or
SB-MPC policy. Any role-to-bound/turn-direction mapping required by the frozen
Mid-MPC formulation belongs in the Mid-MPC integration facade, is independently
traceable, and must not be presented as an existing shared Colav policy.

## State Ownership and Reset

`Ship.reset` calls `ICOLAV.reset` at episode reset
(`colav_simulator/core/ship.py:673`). `CustomMPCAdapter.reset` clears schedule,
held plan, solve id, timeout count, diagnostics, and trace, then calls the
registered solver reset (`custom_mpc_adapter.py:392`). The Mid-MPC facade reset
must additionally clear:

- primal/dual warm starts and cached IPOPT problem state;
- previous course/speed command and any continuity state;
- LOS active-segment and integral state, if LOS is facade-owned;
- per-target encounter memory and disappeared-target entries, if the facade
  needs hysteresis.

Keep all mutable state instance-local. Factory construction creates one facade
per algorithm instance; no module-level cache may cross episodes.

## Registry, Capability, and Visibility Hooks

Use a stable internal id, recommended `mid_mpc_ipopt`, throughout:

1. Add an in-tree `create(*, context, **kwargs) -> CustomMPCAdapter` factory and
   published YAML profile following `config/potocnik_colreg_fan_mpc.yaml`.
2. Add the profile to `_PUBLISHED_ALGORITHM_PROFILES` and module availability to
   `IntegrationRegistry._probe_statuses`; plugin loading then supplies a hashed
   `BuildIdentity` and enforces descriptor/id equality
   (`colav_simulator/integrations/registry.py:38`, `:139`, `:269`).
3. Add the algorithm to `experiment.capabilities.ALGORITHMS` at its truthful
   readiness grade. Do not add `VERIFIED_COMBINATIONS` until raw runs pass.
   Exact tuples, not global grade, control selection
   (`colav_simulator/experiment/capabilities.py:118`, `:200`, `:723`).
4. Add the visible label and card to `web_gui/index.html`; the frontend does not
   synthesize algorithm choices from the API. It only applies capability state
   to existing options/cards in `populateCatalogs` (`web_gui/app.js:3222`).
5. `/api/algorithms` exposes import status, while `/api/capabilities` exposes
   actual readiness/selectability. Both must show the stable id before the GUI
   can execute and inspect it (`gui_server/main.py:916`).

CasADi/IPOPT is not currently declared in `pyproject.toml` or `uv.lock`.
Dependency placement and lock strategy remain the packaging ticket's decision;
absence at construction must map to `DEPENDENCY_UNAVAILABLE`, never another
planner.

## Acceptance Surface

`ExperimentRunner.run(RunSpec)` is the canonical closed-loop path. It resolves
and hashes the scenario, injects `FactoryContext`, builds algorithm/tracker,
runs `SimulationSession`, enforces requested/executed identity and no fallback,
then writes manifest, episode, trajectory, events, evaluation, run metrics, and
report (`colav_simulator/experiment/runner.py:139`, `:311`, `:360`). Use the
existing `P1RunHarness` for candidate-versus-nominal comparisons
(`tests/conftest.py:41`).

Required scenario seam: `head_on`, `overtaking`, `overtaken`,
`crossing_give_way`, `crossing_stand_on`, and
`paper_ccta2023_multiship`, with God tracker, fixed seed, formal deadline mode,
and strict no fallback. The raw G3 predicate checks equal run inputs, valid
clock, nominal threat, exact algorithm identity, real solver events, finite
`9xN` plans, complete plugin identity, footprint oracle, normal termination,
all targets observed, Ship0 footprint clearance, and observable action
(`colav_simulator/experiment/g3_gate.py:31`).

Report layers separately:

- Ship0-vs-target collision and clearance: raw G3 and evaluator hard gate.
- Global all-vessel collision/grounding: evaluator aggregate and
  `run_metrics.json`; this is reported, not implied by Ship0 passing.
- COLREG maneuver quality: evaluator pair metrics/FSM evidence plus trace-based
  direction, timing, passing side, stand-on behavior, and recovery assertions.
  `run_metrics.json` currently labels astern passing and legal compliance
  `NOT_EVALUATED`, so explicit scenario assertions are still required.
- Solver truth: planner traces and `_solver_diagnostics` must show real IPOPT
  solves, statuses, timing, iterations, and objective. HTTP success alone is
  insufficient.
- Numerical parity: frozen C++ fixtures, independent of the simulator
  evaluator, remain a separate hard gate.

## Pre-Agreed TDD Seams

1. **Numerical parity:** test the pure Python IPOPT core against frozen C++
   fixtures for status, command, horizon, objective terms, active constraints,
   and slack. No adapter or scenario mocks.
2. **Public adapter contract:** build through `IntegrationRegistry`, invoke
   `ICOLAV.plan`, and observe `MPCSolution` normalization, schedule/hold,
   timeout/error mapping, reset, identity, and trace through public methods.
   Extend `tests/test_custom_mpc_adapter.py` and
   `tests/test_custom_mpc_schedule.py`; do not test private optimizer helpers.
3. **Closed-loop scenario behavior:** run `P1RunHarness.compare` over the six
   agreed scenarios. Assert raw safety, exact execution/no fallback, global
   events, and encounter-specific maneuver behavior from run artifacts.

Each implementation slice follows red then green at one of these seams. Do not
write tests around CasADi expression-tree shape, private helper calls, or copied
algorithm internals.

## Minimal Blast Radius

Expected production/config changes are limited to a new Mid-MPC integration
module and profile plus focused registrations in:

- `colav_simulator/integrations/registry.py`;
- `colav_simulator/experiment/capabilities.py`, only as evidence matures;
- `config/` and dependency metadata/lock;
- `web_gui/index.html` for visibility.

Expected tests are a new parity suite/fixtures, focused adapter/registry tests,
a Mid-MPC six-scenario matrix, capability/API visibility tests, and explicit
maneuver-quality assertions. The simulator, `Ship`, tracker implementations,
`PlannerInput`, `MPCSolution`, evaluator formulas, scenario YAML, and existing
algorithms should not require behavioral changes. Changes there require a new
decision because they expand the migration beyond the audited boundary.
