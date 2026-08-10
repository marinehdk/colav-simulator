# Frozen IPOPT Mid-MPC portability boundary

## Decision

Freeze the reference algorithm at MASS-L3 GitLab commit
`ced58f8576f3772ef7c1bc72bb0f8b0368688b5a`.

Port the heading/speed nonlinear program, its explicit row-bound policy, IPOPT
status policy, and post-solve numerical witnesses. Do not port the ROS2 node or
the MASS-L3 behavior, dispatch, committed-route, fallback, and publication
layers. The Colav-Simulator adapter must convert its own route, risk, encounter,
and COLREG decision into a normalized optimization problem.

This produces two intentionally separate layers:

1. `reference`: preserves the frozen C++ equations and numerical quirks for
   C++/Python parity.
2. `colav-native`: owns `PlannerInput -> normalized MidMPC problem ->
   MPCSolution`; it may replace MASS-L3 input derivation, but not silently change
   the frozen equations. Any equation or calibration change is a later,
   separately evidenced change.

## Frozen source set

The portable reference is concentrated in these source units:

| Source unit | Decision | Reason |
| --- | --- | --- |
| `mid_mpc_nlp_formulation.hpp/.cpp` | Include | Decision variables, parameter layout, costs, constraints, CasADi graph, IPOPT options, packing, unpacking, strict status mapping. [S1] [S2] |
| `mid_mpc_solver.hpp/.cpp` IPOPT path | Include | Initial guess, variable and row bounds, reachability schedules, solver call, primal feasibility recheck, and result diagnostics. [S3] [S4] |
| `row_registry.hpp` | Include | Fixed constraint-row order and per-cycle activation/softening policy. [S5] |
| `constraint_compiler.cpp::compile_cpa_distance` | Include | Frozen constant-velocity target prediction and node CPA equations. [S6] |
| `constraint_compiler.cpp::compile_colregs_rules` | Compatibility only | It emits one trivially satisfied audit row per rule; direction and minimum-alteration mathematics live in the formulation. The Python core should accept a direct asymmetry flag and explicit direction intent instead of MASS rule numbers. [S7] |
| `mid_mpc_iteration_callback.hpp` | Include solver-control behavior | The frozen solver uses a CasADi iteration callback as a 20 s wall-clock abort. [S8] |
| `continuous_cpa_check.hpp` | Include as post-solve witness, not an NLP row | The IPOPT path performs a swept-interval CPA check after solving, while midpoint CPA constraints are disabled in the frozen NLP. [S9] [S10] |
| `common/types.hpp` | Re-express only the minimal data shapes | `TrajectoryPoint`, target kinematics, normalized problem inputs, status, and diagnostics are needed. ROS message types and unrelated M5 data structures are not. [S11] |

The formulation stores `ConstraintInputs` and bakes hard-target rows into the
symbolic graph. A target or compiled-row change therefore requires a graph
rebuild; packing the 142-slot parameter vector alone does not update hard CPA
rows. [S1] [S6]

## Canonical portable problem

### Coordinates and horizon

- NED convention: `x` is north, `y` is east, `psi=0` is north, and positive
  heading/yaw is clockwise/starboard. [S11]
- Frozen defaults are `N=18`, `dt=5 s`, and at most 16 targets. Runtime code may
  resolve a different horizon up to 120 steps, so fixtures must serialize the
  effective `N` and `dt`, not assume defaults. [S1] [S12]
- Every target follows constant-velocity prediction from `(x, y, cog, sog)`.
  There is no target intent dynamics in the IPOPT graph. [S2] [S6]

### Decision vector

For horizon `N`, the decision vector is:

```text
z = [psi[0:N], u[0:N], sigma_cpa?, sigma_dir?]
```

`sigma_cpa` and `sigma_dir` are each one non-negative scalar shared across all
rows of their class. Both are enabled by default, giving `2N+2` variables.
[S1] [S2]

The model has no position state. Positions are dead-reckoned from the heading
and speed sequence. Output trajectory positions are reconstructed separately
after the solve. [S11] [S13]

### Normalized inputs

The Python mathematical core should receive one simulator-independent
`MidMpcProblem` with these fields:

- Effective formulation configuration: `N`, `dt`, all objective weights,
  barrier constants, slack enable flags and penalties, terminal constants, and
  max target count.
- Own state: local `x`, `y`, heading, and surge speed.
- Route reference: route bearing, planned speed, route-frame origin and unit
  normal, lateral scale, and route-cost guard/weight.
- Motion bounds: heading interval, speed interval, maximum yaw rate, maximum
  deceleration.
- Safety bounds: soft CPA distance and hard CPA floor.
- COLREG optimization intent already decided by Colav-Simulator: lateral role
  active/inactive, signed preferred side (`+1` starboard, `-1` port, `0` none),
  minimum heading alteration, and starboard-asymmetry active/inactive.
- Targets: local position, COG, SOG, and TCPA for each included target.
- Optional optimizer continuity intent: prefix length and reprojected prefix
  heading/speed arrays.
- Explicit row-bound schedule: prefix softening, first hard CPA step, first hard
  direction step, first hard minimum-alteration step, and terminal-row enable.

MASS-L3 rule numbers, M4/M6 enum values, WGS84 reprojection, GNC guard distance,
vessel manifest lookup, and behavior lifecycle must stop at the adapter. The
normalized core consumes their mathematical result, not their source-system
representation. The frozen parameter packing shows the exact data consumed by
the graph. [S14]

### Position conventions that parity must preserve

The frozen source has two time-index conventions:

- Route/direction/terminal terms evaluate `pos[k] = pos0 + sum(j<k) step[j]`.
  Therefore route cross-track at `k=0` is current cross-track. [S15]
- Soft collision cost and hard CPA rows advance own ship by `u[k]*dt` before
  evaluating row `k`, but predict target position at `k*dt`. This effectively
  compares own `k+1` with target `k`; output point `k` is reconstructed at
  `k*dt`. [S16] [S6] [S13]

This offset is a frozen parity behavior, not a recommended model correction.
The reference port must reproduce it first. A later formulation ticket may
correct it only with new C++ fixtures and closed-loop evidence.

Angles are used as ordinary real values: heading tracking is
`sum(psi-bearing)^2`, and yaw-rate rows use direct subtraction. No circular
distance is used inside the NLP. The adapter must unwrap/normalize the heading
window consistently before calling the core. [S15] [S17]

## Objective

The frozen objective is:

```text
J = w_colreg * J_colreg
  + w_dist   * J_heading
  + w_vel    * J_speed
  + w_route  * J_route
  + J_asym
  + J_terminal
  + w_cpa_l1 * sigma_cpa + w_cpa_l2 * sigma_cpa^2
  + w_dir_l1 * sigma_dir + w_dir_l2 * sigma_dir^2
```

Default weights and constants are frozen from `Config`; they are calibration,
not validated Colav-Simulator values. [S1]

| Term | Frozen equation/behavior |
| --- | --- |
| `J_heading` | `sum_k (psi[k] - route_bearing)^2`. [S17] |
| `J_speed` | `sum_k (u[k] - planned_speed)^2`. [S18] |
| `J_route` | `route_weight * (sum_k (l[k]/l_scale)^2 + 2*(l[N-1]/l_scale)^2)`, where `l[k]` is signed route-frame cross-track. [S15] |
| `J_colreg` | Mean over all configured target slots and steps of `range_weight * exp(-k*dt/Td) * exp(-zeta*(distance-cpa_safe))`; empty padded target slots have zero range weight. [S16] [S14] |
| `J_asym` | Give-way Rule-14/15 gate times a smooth port-side penalty relative to route bearing; the native adapter should expose this as a direct boolean instead of rule numbers. [S19] |
| `J_terminal` | Give-way wrong-side softplus plus a two-sided terminal lateral-band softplus, gated off for non-lateral intent. [S20] |
| Slack penalties | Mixed L1/L2 exact-penalty forms for the shared CPA and direction slacks. [S2] |

`w_trans`, `k_dchi`, and `k_du` exist in `Config`, but the frozen IPOPT objective
does not reference them, and previous-cycle trajectory is not a transition-cost
parameter. The reference Python implementation must not invent a transition
cost. [S1] [S2]

## Constraints and activation

Variable bounds are IPOPT `lbx/ubx`:

```text
heading_min <= psi[k] <= heading_max
speed_min   <= u[k]   <= speed_max
sigma_cpa >= 0
sigma_dir >= 0
```

General rows use a fixed order and per-row `lbg/ubg`. [S4] [S5]

| Row class | Count | Frozen expression/activation |
| --- | ---: | --- |
| Yaw rate | `2N` | Bounds own heading to `psi[0]` and every inter-step heading delta by `rot_max*dt`; always hard. [S21] |
| Deceleration | `N` | `decel_max*dt - (u_prev-u[k]) >= 0`, including own speed to `u[0]`; there is no symmetric acceleration-rate row. [S21] |
| Prefix heading/speed | `2N` | First `K` rows are equalities to adapter-supplied prefix; remaining rows disabled. [S21] [S5] |
| CPA | `N*Nt` | `dx^2 + dy^2 - cpa_hard^2 + sigma_cpa >= 0` on active suffix rows; early/prefix rows may be disabled by bounds. Midpoint rows are absent. [S6] [S5] |
| Direction | `N` | `preferred_side*l[k] + sigma_dir >= 0` when lateral give-way is active. [S21] |
| Minimum alteration | `N` | `preferred_side*(psi[k]-own_psi) - min_alt + sigma_dir >= 0` when active. [S21] |
| Terminal | `3` | Preferred-side minimum and two lateral maximum rows. Frozen default `terminal_nlp_soft=true` disables all three via bounds even for give-way. [S21] [S5] |
| Rule audit | One per applicable rule | Constant `0` inside `[0,+inf]`; no maneuver constraint. [S7] |
| Zone | Variable | ENC/TSS polygon constraints. Excluded from this dynamic-target port. [S21] |

The row-bound policy softens early rows according to `K`, reachable minimum
alteration, reachable preferred-side cross-track, and CPA deadline. MASS-L3's
derivation contains M4-specific reachability fields and a surrogate factor tied
to its MMG gap. Preserve that derivation only in the reference-compatibility
adapter. Colav-native execution should supply explicit schedules derived by its
own decision chain. [S22] [S5]

### Frozen numerical caveats

These are parity facts, not approved optimizations:

1. The CPA row adds `sigma_cpa` to a squared-distance expression, so its
   dimensional role is squared distance. The C++ cold-start seed is calculated
   as the linear distance shortfall and assigned directly to that variable.
   Preserve this for reference parity; investigate correction separately. [S6]
   [S23]
2. Hard CPA target states are numeric constants embedded during graph build,
   while soft-cost target states are in the 142-slot parameter vector. Rebuild
   the reference graph when the target snapshot changes. [S6] [S14]
3. `continuous_cpa_enabled` defaults false, and the compiler forcibly disables
   midpoint rows. Setting it true would make the row registry expect rows the
   compiler does not emit. Lock it false in parity fixtures. [S1] [S6]
4. The shared CPA slack can hide one target/step's infeasibility across every
   CPA row. Report its value and do not count `Solve_Succeeded` alone as dynamic
   safety. [S1] [S6]
5. `dir_slack` is part of the solution vector but is only logged, not stored in
   `MidMpcSolution`. A parity exporter must read the raw decision vector. [S13]
6. `MidMpcSolution.cost_*` fields are left zero by IPOPT unpacking. A parity
   exporter must read raw objective `f` and evaluate components explicitly.
   [S13]

## Solver and state semantics

The actual frozen IPOPT graph uses hard-coded options, not values in
`MidMpcSolver::IpoptOptions`: max iterations `5000`, tolerance `1e-4`, MUMPS,
limited-memory Hessian with history 50, adaptive barrier, constraint tolerance
`1e-3`, and max CPU time `20 s`. Only `Solve_Succeeded` maps to converged;
acceptable/feasible statuses fail closed. A second primal feasibility check
tests returned `g` against the same bounds with tolerance `1e-3`. [S24] [S25]
[S26]

The C++ constructor stores `IpoptOptions`, but the graph builder does not read
them. Fixtures must record the hard-coded effective options. [S3] [S24]

Warm-state behavior is narrower than the names suggest:

- The cold start repeats current heading and current speed (or planned speed,
  then `5.14 m/s` if both are near zero). [S3]
- `solve()` explicitly ignores the previous `warm_start`. It pins the active
  prefix from current input and cold-starts the free suffix. [S4]
- CPA slack is seeded from the maximum active-row distance shortfall; direction
  slack starts at zero. [S23]
- The formulation caches a CasADi graph and callback. Its constraint snapshot
  is mutable and graph-baked. [S1]
- `consecutive_failures` and M7/BC-MPC escalation are MASS orchestration state,
  not optimizer state. Do not port them into the mathematical core. [S3] [S4]

The Python result should expose at least raw IPOPT status, normalized status,
iterations, elapsed time, objective total and components, trajectory, both
slacks, `g`, active-row labels/bounds, maximum row violation, and swept CPA.
Colav-Simulator's adapter can then map this into `MPCSolution` diagnostics.

## Inclusion and exclusion boundary

### Include in reference Python

- CasADi symbolic equations and IPOPT backend.
- Frozen configuration and effective hard-coded solver options.
- Heading/speed kinematics, costs, variable bounds, and general constraints.
- Fixed row registry and explicit row-bound activation.
- Cold-start, prefix seed, both slack seeds, strict status mapping, and primal
  feasibility recheck.
- Raw numerical diagnostics and post-solve swept CPA witness.

### Reuse from Colav-Simulator

- `PlannerInput` units/frame conversion and target selection.
- Route-leg selection and route-frame construction.
- Encounter classification, give-way/stand-on role, preferred maneuver side,
  risk ordering, and minimum-alteration policy.
- Scheduler, timeout containment, plugin registry, diagnostics envelope,
  `MPCSolution`, scenario runner, and evaluator.

### Exclude

- ROS2 nodes, subscriptions, messages, launch files, lifecycle, timestamps, and
  schema/rationale publication.
- M1/M2/M4/M6/M7 ownership logic, BC-MPC takeover, plan decider, degraded
  candidate adapter, fallback route generation, MRM escalation, and ASDR.
- `mid_mpc_input_builder`, committed-route builder, WGS84 route reprojection,
  waypoint generator, GNC/AvoidancePlan publication, and tail-gate acceptance.
- acados formulation/solver/code generation and FCB/MMG vessel-specific tuning.
- zone/ENC/TSS, static obstacle, shallow-water, and grounding constraints.
- MASS-L3 target-intent/compliance fields unused by the IPOPT graph.

## Smallest C++ parity-export surface

Do not export ROS messages or execute the full M5 node. Add a test-only JSONL
CLI linked directly to the frozen IPOPT formulation and solver.

### Request record

One request must contain:

- `schema`, frozen commit, fixture id, effective config, and effective solver
  options;
- the normalized input fields listed above;
- the explicit or C++-derived `RowBoundConfig`;
- exact decimal doubles (`max_digits10`) and no NaN/Inf JSON literals.

The existing diagnostic serializer already covers most `MidMpcInput` fields at
`max_digits10`, but it is dead code at this commit, is named for acados, and
captures neither config nor solver output. Reuse its serialization conventions,
not its environment-variable integration. [S27]

### Response record

Export, in one deterministic record:

```text
p, x0, lbx, ubx, lbg, ubg,
row class/name/index,
x_opt, f_opt, g_opt,
J_colreg, J_heading, J_speed, J_route, J_asym, J_terminal,
J_sigma_cpa, J_sigma_dir,
return_status, normalized_status, iter_count, elapsed_ms,
trajectory, sigma_cpa, sigma_dir, max_constraint_violation,
continuous_cpa_min, continuous_cpa_violated
```

Smallest production-facing instrumentation needed:

1. Add one optional, read-only `MidMpcSolveTrace*` sink to the IPOPT `solve`
   path. Populate it from locals already present around the solver call
   (`p/x0/bounds/res/stats`). Default `nullptr` must preserve behavior.
2. Add one formulation method returning the complete objective breakdown for a
   supplied `(x,p)`. Existing public evaluators already cover COLREG, heading,
   route, and terminal; extend the same pattern for speed, asymmetry, slack, and
   total. [S28]
3. Keep JSON parsing/printing entirely in the test executable. No ROS, node,
   fallback, or filesystem capture dependency enters the optimizer library.

This is smaller and safer than duplicating the C++ preparation path in an
external exporter. Duplicating `x0`, slack seeding, row scheduling, and bounds
would test the duplicate rather than the actual solver boundary.

### Minimum fixture families enabled by that surface

- Cold, target-free route/speed tracking.
- Head-on/crossing starboard give-way with direction rows active.
- Stand-on/HOLD with direction and terminal rows disabled.
- Overtaking with a supplied port or starboard preference.
- Close target requiring non-zero CPA slack.
- Active committed prefix (`K>0`) to prove equality/softening parity.
- Multiple targets to prove row ordering and shared-slack behavior.

Each fixture should compare prepared arrays before comparing the optimum. This
localizes mismatch to input packing, row activation, graph equations, IPOPT
behavior, or output mapping.

## Dependency and license provenance

- The frozen MASS-L3 commit has no root `LICENSE`, `LICENSE.md`, `COPYING`, or
  `NOTICE`. User authorization permits this public adaptation, but the source
  tree itself does not establish redistribution terms. Prefer an independently
  written Python implementation from the frozen mathematical contract, retain
  commit/path attribution, and obtain project-owner license confirmation before
  copying C++ text. This is provenance guidance, not legal advice.
- MASS-L3 pins CasADi `3.7.2` and Ipopt `3.14.19` as submodules; its build requires
  exact CasADi 3.7.2 and the IPOPT plugin. [S29] [S30]
- CasADi 3.7.2 is distributed under LGPL-3.0 in its official license. [L1]
- Ipopt 3.14.19 is distributed under EPL-2.0 in its official license. [L2]
- Colav-Simulator's root `LICENSE` is MIT. A new Python module can follow that
  repository license, subject to the unresolved MASS-L3 source-license boundary
  above and the dependency licenses.

## Newly sharp follow-up tickets

1. Define the normalized `MidMpcProblem`/result schema and exact
   `PlannerInput -> MidMpcProblem` mapping, including frame and angle unwrapping.
2. Implement the C++ JSONL parity exporter and freeze fixture records.
3. Decide parity tolerances separately for prepared arrays, objective/rows,
   optimizer solution, and status because IPOPT optima can be non-unique.
4. Implement the equation-identical Python reference with parity tests before
   adding the Colav-native adapter.
5. After parity, investigate the own/target time-index offset and CPA slack unit
   mismatch as formulation changes, never as translation cleanup.

## Primary sources

[S1]: https://gitlab.sangoai.com/mass_devgroup/01-dynamics/01-simulation/-/blob/ced58f8576f3772ef7c1bc72bb0f8b0368688b5a/src/l3_tdl_kernel/m5_tactical_planner/include/m5_tactical_planner/mid_mpc/mid_mpc_nlp_formulation.hpp#L43-208
[S2]: https://gitlab.sangoai.com/mass_devgroup/01-dynamics/01-simulation/-/blob/ced58f8576f3772ef7c1bc72bb0f8b0368688b5a/src/l3_tdl_kernel/m5_tactical_planner/src/mid_mpc/mid_mpc_nlp_formulation.cpp#L628-750
[S3]: https://gitlab.sangoai.com/mass_devgroup/01-dynamics/01-simulation/-/blob/ced58f8576f3772ef7c1bc72bb0f8b0368688b5a/src/l3_tdl_kernel/m5_tactical_planner/src/mid_mpc/mid_mpc_solver.cpp#L24-97
[S4]: https://gitlab.sangoai.com/mass_devgroup/01-dynamics/01-simulation/-/blob/ced58f8576f3772ef7c1bc72bb0f8b0368688b5a/src/l3_tdl_kernel/m5_tactical_planner/src/mid_mpc/mid_mpc_solver.cpp#L186-661
[S5]: https://gitlab.sangoai.com/mass_devgroup/01-dynamics/01-simulation/-/blob/ced58f8576f3772ef7c1bc72bb0f8b0368688b5a/src/l3_tdl_kernel/m5_tactical_planner/include/m5_tactical_planner/mid_mpc/row_registry.hpp#L38-405
[S6]: https://gitlab.sangoai.com/mass_devgroup/01-dynamics/01-simulation/-/blob/ced58f8576f3772ef7c1bc72bb0f8b0368688b5a/src/l3_tdl_kernel/m5_tactical_planner/src/shared/constraint_compiler.cpp#L241-346
[S7]: https://gitlab.sangoai.com/mass_devgroup/01-dynamics/01-simulation/-/blob/ced58f8576f3772ef7c1bc72bb0f8b0368688b5a/src/l3_tdl_kernel/m5_tactical_planner/src/shared/constraint_compiler.cpp#L160-239
[S8]: https://gitlab.sangoai.com/mass_devgroup/01-dynamics/01-simulation/-/blob/ced58f8576f3772ef7c1bc72bb0f8b0368688b5a/src/l3_tdl_kernel/m5_tactical_planner/include/m5_tactical_planner/mid_mpc/mid_mpc_iteration_callback.hpp#L1-149
[S9]: https://gitlab.sangoai.com/mass_devgroup/01-dynamics/01-simulation/-/blob/ced58f8576f3772ef7c1bc72bb0f8b0368688b5a/src/l3_tdl_kernel/m5_tactical_planner/src/mid_mpc/mid_mpc_solver.cpp#L637-660
[S10]: https://gitlab.sangoai.com/mass_devgroup/01-dynamics/01-simulation/-/blob/ced58f8576f3772ef7c1bc72bb0f8b0368688b5a/src/l3_tdl_kernel/m5_tactical_planner/include/m5_tactical_planner/mid_mpc/mid_mpc_nlp_formulation.hpp#L123-137
[S11]: https://gitlab.sangoai.com/mass_devgroup/01-dynamics/01-simulation/-/blob/ced58f8576f3772ef7c1bc72bb0f8b0368688b5a/src/l3_tdl_kernel/m5_tactical_planner/include/m5_tactical_planner/common/types.hpp#L28-101
[S12]: https://gitlab.sangoai.com/mass_devgroup/01-dynamics/01-simulation/-/blob/ced58f8576f3772ef7c1bc72bb0f8b0368688b5a/src/l3_tdl_kernel/m5_tactical_planner/include/m5_tactical_planner/mid_mpc/mid_mpc_nlp_formulation.hpp#L379-393
[S13]: https://gitlab.sangoai.com/mass_devgroup/01-dynamics/01-simulation/-/blob/ced58f8576f3772ef7c1bc72bb0f8b0368688b5a/src/l3_tdl_kernel/m5_tactical_planner/src/mid_mpc/mid_mpc_nlp_formulation.cpp#L876-975
[S14]: https://gitlab.sangoai.com/mass_devgroup/01-dynamics/01-simulation/-/blob/ced58f8576f3772ef7c1bc72bb0f8b0368688b5a/src/l3_tdl_kernel/m5_tactical_planner/src/mid_mpc/mid_mpc_nlp_formulation.cpp#L756-872
[S15]: https://gitlab.sangoai.com/mass_devgroup/01-dynamics/01-simulation/-/blob/ced58f8576f3772ef7c1bc72bb0f8b0368688b5a/src/l3_tdl_kernel/m5_tactical_planner/src/mid_mpc/mid_mpc_nlp_formulation.cpp#L90-245
[S16]: https://gitlab.sangoai.com/mass_devgroup/01-dynamics/01-simulation/-/blob/ced58f8576f3772ef7c1bc72bb0f8b0368688b5a/src/l3_tdl_kernel/m5_tactical_planner/src/mid_mpc/mid_mpc_nlp_formulation.cpp#L325-393
[S17]: https://gitlab.sangoai.com/mass_devgroup/01-dynamics/01-simulation/-/blob/ced58f8576f3772ef7c1bc72bb0f8b0368688b5a/src/l3_tdl_kernel/m5_tactical_planner/src/mid_mpc/mid_mpc_nlp_formulation.cpp#L90-100
[S18]: https://gitlab.sangoai.com/mass_devgroup/01-dynamics/01-simulation/-/blob/ced58f8576f3772ef7c1bc72bb0f8b0368688b5a/src/l3_tdl_kernel/m5_tactical_planner/src/mid_mpc/mid_mpc_nlp_formulation.cpp#L314-323
[S19]: https://gitlab.sangoai.com/mass_devgroup/01-dynamics/01-simulation/-/blob/ced58f8576f3772ef7c1bc72bb0f8b0368688b5a/src/l3_tdl_kernel/m5_tactical_planner/src/mid_mpc/mid_mpc_nlp_formulation.cpp#L395-417
[S20]: https://gitlab.sangoai.com/mass_devgroup/01-dynamics/01-simulation/-/blob/ced58f8576f3772ef7c1bc72bb0f8b0368688b5a/src/l3_tdl_kernel/m5_tactical_planner/src/mid_mpc/mid_mpc_nlp_formulation.cpp#L248-312
[S21]: https://gitlab.sangoai.com/mass_devgroup/01-dynamics/01-simulation/-/blob/ced58f8576f3772ef7c1bc72bb0f8b0368688b5a/src/l3_tdl_kernel/m5_tactical_planner/src/mid_mpc/mid_mpc_nlp_formulation.cpp#L439-622
[S22]: https://gitlab.sangoai.com/mass_devgroup/01-dynamics/01-simulation/-/blob/ced58f8576f3772ef7c1bc72bb0f8b0368688b5a/src/l3_tdl_kernel/m5_tactical_planner/src/mid_mpc/mid_mpc_solver.cpp#L664-858
[S23]: https://gitlab.sangoai.com/mass_devgroup/01-dynamics/01-simulation/-/blob/ced58f8576f3772ef7c1bc72bb0f8b0368688b5a/src/l3_tdl_kernel/m5_tactical_planner/src/mid_mpc/mid_mpc_solver.cpp#L317-374
[S24]: https://gitlab.sangoai.com/mass_devgroup/01-dynamics/01-simulation/-/blob/ced58f8576f3772ef7c1bc72bb0f8b0368688b5a/src/l3_tdl_kernel/m5_tactical_planner/src/mid_mpc/mid_mpc_nlp_formulation.cpp#L19-50
[S25]: https://gitlab.sangoai.com/mass_devgroup/01-dynamics/01-simulation/-/blob/ced58f8576f3772ef7c1bc72bb0f8b0368688b5a/src/l3_tdl_kernel/m5_tactical_planner/src/mid_mpc/mid_mpc_nlp_formulation.cpp#L700-750
[S26]: https://gitlab.sangoai.com/mass_devgroup/01-dynamics/01-simulation/-/blob/ced58f8576f3772ef7c1bc72bb0f8b0368688b5a/src/l3_tdl_kernel/m5_tactical_planner/include/m5_tactical_planner/mid_mpc/mid_mpc_nlp_formulation.hpp#L331-377
[S27]: https://gitlab.sangoai.com/mass_devgroup/01-dynamics/01-simulation/-/blob/ced58f8576f3772ef7c1bc72bb0f8b0368688b5a/src/l3_tdl_kernel/m5_tactical_planner/include/m5_tactical_planner/mid_mpc/mid_mpc_diagnostic_capture.hpp#L1-225
[S28]: https://gitlab.sangoai.com/mass_devgroup/01-dynamics/01-simulation/-/blob/ced58f8576f3772ef7c1bc72bb0f8b0368688b5a/src/l3_tdl_kernel/m5_tactical_planner/include/m5_tactical_planner/mid_mpc/mid_mpc_nlp_formulation.hpp#L259-267
[S29]: https://gitlab.sangoai.com/mass_devgroup/01-dynamics/01-simulation/-/blob/ced58f8576f3772ef7c1bc72bb0f8b0368688b5a/.gitmodules#L46-54
[S30]: https://gitlab.sangoai.com/mass_devgroup/01-dynamics/01-simulation/-/blob/ced58f8576f3772ef7c1bc72bb0f8b0368688b5a/src/l3_tdl_kernel/m5_tactical_planner/CMakeLists.txt#L50-75
[L1]: https://github.com/casadi/casadi/blob/3.7.2/LICENSE.txt
[L2]: https://github.com/coin-or/Ipopt/blob/releases/3.14.19/LICENSE
