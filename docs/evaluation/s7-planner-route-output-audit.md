# S7.0 Planner Route-Output Audit (pre-tracked-route integration)

> Issue: #62 (S7.0); parent #41; prerequisite of #63 (tracked-route seam, slice 7 / RA-06)
> Baseline: `ac765d6` (branch `feat/modular-gnc-stack`), zero planner behavior modified
> Registry: `colav_simulator/integrations/registry.py` (`IntegrationRegistry`)
> Evidence test: `tests/test_gnc_planner_audit.py`
> Reproduce: `.venv/bin/python -m pytest tests/test_gnc_planner_audit.py -q`
> Claim ceiling: none claimed. This audit is an **A4 prerequisite** only; no A4 (COLAV Closed Loop) level is declared (TS-29).

Method: characterization only. For every registered planner a deterministic
minimal scenario drives the planner through its public seam (`ICOLAV.plan`,
`get_current_plan`, `get_diagnostics`, `get_colav_data`, and for plugin planners
the `CustomMPCAdapter` contract) and the observed facts are pinned as pytest
assertions. Facts and interpretation are separated: assertions pin facts; this
document may add interpretation, and every interpretation is marked
*(interpretation)*. Findings that look like defects are recorded in the issue
list below, not fixed.

## 1. Registered planner set (authoritative enumeration)

`IntegrationRegistry._probe_statuses()` registers these algorithm-kind ids
(trackers `scenario_default`/`god`/`kf`/`vimmjipda` are out of scope):

| id | availability at baseline | build result |
|---|---|---|
| `nominal` | builtin, available | `None` (no COLAV authority) |
| `vo` | builtin, available | `VOWrapper` (Kuwata VO + LOS) |
| `sbmpc` | builtin, available | `SBMPCWrapper` (SB-MPC + LOS) |
| `mid_mpc_ipopt` | available | `CustomMPCAdapter` over `_MidMpcFacade` (plugin `create`) |
| `potocnik_simplified_mpc` | available | `CustomMPCAdapter` over `PotocnikSimplifiedMPC` |
| `potocnik_colreg_fan_mpc` | available | `CustomMPCAdapter` over `PotocnikColregFanMPC` |
| `psbmpc` | external, available (ecosystem `PSBMPCInterface` build) | `PSBMPCColav` |
| `sbmpc_reference` | external, available (same pinned build) | `OfficialSBMPCReference` |
| `rrt` | external, available (ecosystem `rrt-rs`) | `RRTStarColav` |
| `rlmpc` | external, **unavailable here** (`No module named 'torch'`) | raw `rlmpc.rlmpc_cas.RLMPC` (never built in this environment) |

Difference from the issue text: the issue names Mid-MPC, SBMPC, RRT, PSBMPC.
The actual registered set additionally contains `vo`, `sbmpc_reference`,
`potocnik_simplified_mpc`, `potocnik_colreg_fan_mpc`, `rlmpc` and `nominal`.
Per the issue's own rule the registered set is authoritative and all of them
are audited. In addition, `_build_plugin` accepts arbitrary `factory:` config
ids at runtime (dynamic plugin set, not statically enumerable); every such
plugin is forced through the same `CustomMPCAdapter` contract audited in §3.4
(behavior identity: the adapter section covers the class, the three registered
plugin planners are its observed instances).

## 2. Common consumption path (direct-reference, unchanged)

`Ship.plan` (`colav_simulator/core/ship.py:589-625`) stores `colav.plan(...)`
output as `self._references` after `validate_plan` (9 x N>=1, finite;
`colav_simulator/core/colav/diagnostics.py:125`). `Ship.forward` then calls
`self._controller.compute_inputs(self._references[:, 0], ...)`: **column 0
only, zero-order hold at each simulation tick**. On this legacy path no planner
output carries route identity, revision, acceptance, expiry or recovery
semantics; there is no route object anywhere between planner and controller.
Only Mid-MPC maintains an accepted-plan lifecycle internally (§3.4).

## 3. Per-planner audit

All values below are pinned in `tests/test_gnc_planner_audit.py`. Row layout
for every 9-row artifact: `[x, y, psi, u, v, r, x_ddot, y_ddot, psi_dot]`
(course/speed reference lives in rows 2/3 of column 0).

### 3.1 `nominal`

- Output shape: `build_algorithm("nominal")` returns `None`; the ship falls
  back to its onboard guidance module (`ship.py` `_guidance.compute_references`
  branch, also 9xN). Pinned: build result is `None`.
- Direct-reference behavior: pure LOS guidance references per tick.
- Route lifecycle: none. Prediction fields: none. Continuity: references
  recomputed every tick; no plan object exists.

### 3.2 `vo` (VOWrapper)

- Output shape: `plan()` returns `(9, 1)`; rows 0-1 are zero (no position
  reference), row 2 = course (0.0 rad on-route), row 3 = LOS speed
  (7.0968 m/s at the pinned geometry), rows 4-8 zero.
- Direct-reference behavior: reactive. LOS produces a course/speed reference,
  VO overrides it with a collision-free velocity-obstacle command.
- Route identity/revision/acceptance/expiry/recovery: none.
- Prediction fields: none. The `PlannerTrace.predicted_trajectory` is the
  command reference with the ownship position written into rows 0-1 of
  column 0 — a `(9, 1)` snapshot, not a horizon grid. (interpretation: VO is a
  reactive layer; calling this field a "trajectory" is a schema legacy.)
- Continuity: stateless across ticks beyond internal VO rule memories
  (locks/commitments); output is recomputed every tick.
- Fallback semantics (code-level, not exercised in the audit scenario geometry): when
  the VO core is infeasible the wrapper sets `fallback_used=True`,
  `status=INFEASIBLE`, `reason="fallback=stop_nonpaper_wrapper"`; the command
  itself comes from the VO core's internal stop fallback.

### 3.3 `sbmpc` (SBMPCWrapper)

- Output shape: `plan()` returns the LOS reference array `(9, 1)` with only
  column 0 modified: row 2 = held course command, row 3 = nominal speed x
  speed-scale.
- Direct-reference behavior: offset planner. The SB-MPC core returns
  `(speed_scale, course_offset)` against the nominal LOS reference.
- Activation gate: solver runs when `t - t_last >= 5.0` **and** at least one
  track is within `D_INIT_ = 1000 m` (`core/colav/sbmpc/sbmpc.py:29`);
  otherwise offsets stay `(1.0, 0.0)`. Pinned: first call at t=0 reports
  `solver_executed=False`; at t=5 with a head-on track at 800 m the solve runs
  (`solve_id=1`, course offset +0.2618 rad = +15 deg, speed scale 1.0).
- Route identity/revision/acceptance/expiry/recovery: none. Diagnostics are
  always `SUCCESS`/`feasible=True`, even on ticks where the solver did not
  execute.
- Prediction fields: `PlannerTrace.predicted_trajectory` is the SB-MPC
  prediction grid `(9, 60)` (T_=150 s at DT_=2.5 s), anchored at the
  solve-time ownship state; `target_predictions` from the core debug data.
- Continuity: between solves the held course command is re-applied and
  rate-limited during overtaking recovery (<= 15 deg per solve step,
  `SBMPCWrapper.plan`); LOS is recomputed fresh each tick.
- **Boundary finding:** `SBMPCWrapper.get_current_plan()` returns the
  *prediction grid* (`self._planner_trace.predicted_trajectory`), not the
  executed command — the opposite of what the name suggests (issue list #1).
  The ship never consumes it on the legacy path.

### 3.4 `mid_mpc_ipopt` (CustomMPCAdapter over `_MidMpcFacade`)

Audited at the repo's own fast-horizon convention (`horizon_steps=4`,
`deadline_mode=OFF`, cf. `tests/test_mid_mpc_ipopt_integration.py`);
`deadline_s` stays frozen at 20 s and production default is 80 steps x 5 s.

- Output shape: `plan()` returns the single executed command column `(9, 1)`
  (`MPCSolution.control_reference`); rows 0-1 carry the reference position at
  the horizon knot (inert for the legacy controller, which reads rows 2/3).
- Direct-reference behavior: on the legacy path it is consumed like any other
  planner's column 0.
- **Route lifecycle (unique among registered planners):**
  - identity: `RollingPlanIdentity = (route_hash, target_keys, capability_hash,
    authority_hash)` (`core/colav/rolling_plan.py:29`);
  - revision: typed `PlanRevisionReason` (INITIAL_PLAN, CONTINUITY_PRESERVED,
    RESET, MISSION_ROUTE_CHANGED, TARGET_GENERATION_CHANGED,
    CAPABILITY_CHANGED, COLREG_AUTHORITY_CHANGED, PRIOR_PLAN_UNSAFE,
    PREFIX_CONTINUITY_EXCEEDED, PASSING_SIDE_CHANGED, RECOVERY_TIME_CHANGED);
    pinned: fresh solve reports `INITIAL_PLAN`, and an authority-hash change
    reports `COLREG_AUTHORITY_CHANGED` with the rolling reference inactive;
  - acceptance: L4 plan acceptance gates the candidate before commit
    (`MidMpcPlanAcceptance`); rejection raises `INFEASIBLE` with
    `preserve_accepted_plan=True`;
  - expiry: `AcceptedPlanReceipt.valid_until_s = accepted_at_s +
    decision_period_s` (pinned 0.0 -> 5.0 at solve period 5 s); `validate_hold`
    rejects a held plan past receipt validity (`HOLD_RECEIPT_EXPIRED`);
  - recovery: passing-side consistency and `recovery_at_s` drift
    (`RECOVERY_TIME_CHANGED`, `recovery_drift_max_s=5.0`) are assessed on every
    candidate.
  - evidence: SHA-256 hash chain request -> problem -> prepared -> solver ->
    acceptance -> receipt (pinned 64-hex for all six stages) — TS-27.
- Prediction fields: `predicted_trajectory` `(9, N+1)` NLP grid,
  `control_trajectory` `(9, N)` held course/speed knots, per-target
  constant-velocity predictions with lifecycle metadata, and a
  `PredictionEvidenceRecord` envelope.
- Continuity: between solves the adapter samples the held control trajectory
  at elapsed time (`trajectory_source="held_plan"`); when a fresh candidate is
  rejected the adapter preserves the accepted plan for one solve period
  (`hold_acceptance.mode="ROLLING_PLAN_CONTINUATION"`,
  `candidate_rejected=True`, pinned with `revision_reason=OPTIMIZER_UNRESOLVED`
  at the reduced audit horizon).
- **Boundary finding:** `CustomMPCAdapter.get_current_plan()` returns the
  prediction grid, not the command column. Prediction and executable reference
  are distinct artifacts at this seam and only the command column is executed.

### 3.5 `potocnik_simplified_mpc`

- Output shape: command column `(9, 1)`; at the pinned head-on geometry the
  selected fan candidate is -0.1745 rad (-10 deg), speed 7.0 m/s.
- Direct-reference behavior: exhaustive fan (45 candidates x 20 steps at 5 s)
  filtered by constant-velocity target clearance
  (`collision_distance_m = 0.5 NM`); best-scored candidate's first knot becomes
  the command.
- Route identity/revision/acceptance/expiry/recovery: none.
  `constraints` keys: `dynamic_collision`, `heading_increment`,
  `planning_zone`.
- Prediction fields: `predicted_trajectory (9, 21)` selected fan arm;
  per-target constant-velocity predictions; no evidence envelope.
- Continuity: solve period 5 s; between solves the adapter samples the held
  trajectory — and because `control_trajectory is None` for this planner the
  hold interpolates the **prediction grid** (issue list #4). Infeasible fans
  raise `INFEASIBLE`; the adapter then resets the cached plan to zeros
  `(9, 1)` (pinned).
- Observation recorded, not judged here: the simplified planner selects a
  port-side (-10 deg) turn in the deterministic head-on audit scenario while the
  COLREG-fan variant selects starboard +5 deg (issue list #5).

### 3.6 `potocnik_colreg_fan_mpc`

- Output shape: command column `(9, 1)`; head-on scenario command is +5 deg
  starboard (early substantial action), speed 7.0 m/s.
- Direct-reference behavior: course/speed fan with COLREG encounter policy,
  continuous footprint clearance check, optional ENC static constraint.
- Route identity/revision/acceptance/expiry/recovery: none.
- Prediction fields: `predicted_trajectory (9, 21)` and an explicit
  `control_trajectory (9, 21)` with
  `control_trajectory_semantics="held_course_speed_reference"`.
- Continuity: hold samples the control trajectory (not the prediction grid —
  clean separation, unlike §3.5); infeasible candidates raise `INFEASIBLE`
  (same adapter reset semantics as §3.5).

### 3.7 `psbmpc` (PSBMPCColav, external)

- Output shape: `plan()` returns `validate_plan(los_references)` `(9, 1)` with
  column 0 modified by `(speed_scale, course_offset)` from the native solver.
- Direct-reference behavior: offset planner on a fixed solve period (5 s
  default); offsets are recomputed from the native PSB-MPC
  `calculate_optimal_offsets` result.
- ENC boundary: hard requirement — `plan(enc=None)` raises `INVALID_INPUT`
  ("PSB-MPC requires an ENC"); before the first solve `get_current_plan()` is
  zeros `(9, 1)`. All pinned under the availability guard.
- Route lifecycle: none. No acceptance, revision, expiry or recovery concept
  exists on this path.
- Prediction fields: `result.predicted_trajectory` stored raw in
  `self._trajectory` without `validate_plan` (issue list #2) and surfaced via
  `get_colav_data()["predicted_trajectory"]`.
- Continuity: offset zero-order hold between periods; LOS recomputed fresh
  each tick.

### 3.8 `sbmpc_reference` (OfficialSBMPCReference, external)

- Output shape: `plan()` returns `validate_plan(los_references)` `(9, 1)` with
  the native `(u_opt, chi_opt)` offsets applied to column 0; without
  obstacles/ENC the pinned audit scenario yields course 0.0, speed 4.0.
- ENC boundary: **tolerates `enc=None`** (runs the native solver with empty
  polygon set) — asymmetric with `psbmpc`/`rrt` (issue list #3).
- Route lifecycle: none.
- Prediction fields: native `(4, N)` trajectory mapped to `(9, N)` by
  `_map_native_trajectory` (finite-difference velocities/accelerations, then
  `validate_plan`); trace carries it with `horizon_dt_s` from native params.
- Continuity: offset zero-order hold between solves; pinned: second call at
  t=2 has `solver_executed=False`, same `solve_id`, identical
  `selected_command`.
- **Boundary finding:** `get_current_plan()` returns the current *command*
  (`self._command`), not a prediction — third distinct meaning of
  `get_current_plan` across planners (issue list #1).

### 3.9 `rrt` (RRTStarColav, external)

- Output shape: `plan()` returns `validate_plan(los_references)` `(9, 1)` —
  LOS references computed against the RRT* path waypoints.
- Direct-reference behavior: plan **once** at first call against the real ENC
  (grounding hazards + safe-sea triangulation), then track the resulting path
  with LOS forever after; dynamic obstacles (`do_list`) are ignored by
  contract (`ARG002`).
- ENC boundary: hard requirement at `plan` (`INVALID_INPUT` without ENC);
  before the first solve `get_current_plan()` is zeros `(9, 1)`.
- Route lifecycle: none. The internally tracked RRT* path is a private
  waypoint list, not an identity-carrying route object.
- Prediction fields: `get_current_plan()` returns the planned trajectory
  zero-padded from 6 to 9 rows; `get_colav_data()` labels it
  `predicted_trajectory` although it is the tracked path (interpretation:
  naming conflation, see issue list #1).
- Continuity: plan-once-then-track; no re-plan, no revision, no expiry.

### 3.10 `rlmpc` (external, unavailable here)

- Registered; `_module_status` reports unavailable in this environment
  (`No module named 'torch'`); `build_algorithm` raises
  `DEPENDENCY_UNAVAILABLE` (pinned, availability-branched test keeps passing
  if the dependency is installed).
- Code-level (not executable here): `build_algorithm("rlmpc")` returns the raw
  `RLMPC` object without any `ICOLAV` conformance check — the only registered
  id whose build result is not wrapper-validated (issue list #7).
- No output-shape, lifecycle or prediction claims are made for it in this
  environment; it stays on the direct-reference path by default and requires
  its own audit before any tracked-route consideration.

## 4. Prediction vs executable boundary (per planner)

| planner | executable output (`plan()`) | prediction artifacts | prediction is executed? |
|---|---|---|---|
| nominal | guidance refs (no planner) | none | n/a |
| vo | `(9,1)` command | command snapshot mislabeled as trajectory | no |
| sbmpc | `(9,1)` LOS+offset column | `(9,60)` prediction grid | no (grid only for tracing) |
| mid_mpc_ipopt | `(9,1)` control_reference column | `(9,N+1)` grid + `(9,N)` control knots + target predictions + evidence | no (hold interpolates the *control* trajectory, which is a distinct declared artifact) |
| potocnik_simplified_mpc | `(9,1)` command | `(9,21)` fan arm | **hold path interpolates the prediction grid** (issue #4) |
| potocnik_colreg_fan_mpc | `(9,1)` command | `(9,21)` prediction + `(9,21)` control knots | no (hold uses control knots) |
| psbmpc | `(9,1)` LOS+offset column | raw native trajectory (unvalidated) | no |
| sbmpc_reference | `(9,1)` LOS+offset column | mapped `(9,N)` native trajectory | no |
| rrt | `(9,1)` LOS column along path | zero-padded planned path | no |
| rlmpc | not executable here | unknown | n/a |

No registered planner exposes a route object. A predicted trajectory is never
an accepted route: the only lifecycle-bearing plan (Mid-MPC rolling plan) is
held internally by the facade, and its executable emission is still a single
`(9, 1)` direct reference. *(interpretation)* This is exactly the TS-18/VR-18
predicate ("predicted trajectory is not a route") observed at the planner seam.

## 5. Conclusion

### 5.1 First tracked-route integration target: Mid-MPC rolling-plan lifecycle

Mid-MPC is the only registered planner that already owns an accepted-plan
lifecycle — identity `(route_hash, target_keys, capability_hash,
authority_hash)`, typed revision reasons, L4 acceptance gating, receipt expiry
(`valid_until_s`), passing-side/recovery consistency and a SHA-256 evidence
chain — so #63 can map `TrackedRoute` (route_id/revision/accepted/validity)
onto existing, tested semantics (`RollingPlan`, `AcceptedPlanReceipt`)
1:1 instead of inventing lifecycle for a planner that has none.

### 5.2 All other planners stay on the direct-reference path

`vo`, `sbmpc`, `potocnik_simplified_mpc`, `potocnik_colreg_fan_mpc`,
`psbmpc`, `sbmpc_reference`, `rrt`, `rlmpc` and `nominal` emit bare
`(9,1)`/9xN references with no identity, acceptance, expiry or recovery
concept (§3, §4). Treating any of their outputs as an accepted executable
route before a per-planner acceptance audit would fabricate lifecycle that
does not exist. They remain on the legacy `references[:, 0]` path until
individually accepted (AC4).

### 5.3 Requirement mapping (locally verifiable only)

| requirement | mapping in this audit |
|---|---|
| RA-06 | This document + `tests/test_gnc_planner_audit.py`: every registered planner audited at its output seam; Mid-MPC named first connection target; others stay direct-reference. |
| TS-18 / VR-18 | §4 table: prediction and executable artifacts are distinct per planner; `CommandInput` already enforces DIRECT_REFERENCE/TRACKED_ROUTE mutual exclusion at the facade; audit records that no planner output is or carries a route. |
| TS-27 | Mid-MPC six-stage SHA-256 hash chain pinned (request/problem/prepared/solver/acceptance/receipt, all 64-hex). |
| TS-28 / VR-24 | Pins are per-quantity observed values with explicit tolerances, one assertion per fact; no single-smoke claim. Contributes to gate evidence; gates themselves are not run here. |
| TS-29 | No acceptance level claimed; audit is an A4 prerequisite only. |
| TS-30 / VR-28 | Per-planner evidence sections (§3) with classification: output shapes and lifecycle semantics = DomainInvariant; geometry/speed values = scenario scaffolding (not vessel parameters); external availability + ENC requirements = RuntimeAdapter; simplified-Potocnik side selection = ExperimentalCandidate observation (issue #5). Cross-vessel generality is out of scope for this audit. |
| G1 | ICOLAV 9xN contract + `validate_plan` pinned at every planner seam. |
| G8 | Not executed (A4 scope, #63+). This audit is its precondition input. |

## 6. Issue list (recorded for later tickets; nothing fixed here)

1. `get_current_plan()` has three different meanings: command reference (vo,
   sbmpc_reference, custom-adapter-before-first-solve), solver prediction
   (sbmpc wrapper, mid-mpc adapter), planned path (rrt); and
   `get_colav_data()["predicted_trajectory"]` repeats the conflation
   (psbmpc, rrt). Any tracked-route consumer must define which artifact it
   reads.
2. `PSBMPCColav` stores `result.predicted_trajectory` raw (no `validate_plan`):
   shape/finite-ness of the native trajectory is unenforced on that path
   (`colav_simulator/integrations/psbmpc.py:183-185`).
3. ENC boundary asymmetry: `psbmpc` and `rrt` hard-require an ENC;
   `sbmpc_reference` silently runs ENC-less with an empty static set.
4. `potocnik_simplified_mpc` hold path interpolates the prediction grid
   (`control_trajectory is None`): between solves the predicted fan arm doubles
   as the executable reference source. Clean separation exists in the colreg
   variant; the simplified variant could adopt it if ever migrated.
5. Side-selection divergence in the deterministic head-on audit scenario:
   `potocnik_simplified_mpc` selects a port turn (-10 deg) while
   `potocnik_colreg_fan_mpc` selects starboard (+5 deg). Not judged here;
   relevant for any future COLREGs conformance sweep of the paper planners.
6. VO infeasible branch (`fallback=stop_nonpaper_wrapper`) is not exercisable
   with simple deterministic geometry; pinned at code level only, no execution
   evidence in this audit.
7. `rlmpc` build path returns the raw `RLMPC` object without an `ICOLAV`
   conformance check; it is also the only registered algorithm unavailable in
   this environment. Needs its own audit before any integration consideration.
8. Observation: the Mid-MPC rolling-plan revision reason was
   `COLREG_AUTHORITY_CHANGED` between two solves with unchanged route and
   target keys (audit scenario t=0 -> t=5). This is lifecycle functioning as designed
   (authority hash churn breaks continuity), noted so #63 does not misread an
   inactive rolling reference as a bug.

## 7. Reproduction

```
.venv/bin/python -m pytest tests/test_gnc_planner_audit.py -q
```

20 characterization tests, all local and deterministic; external-planner tests
branch on registry availability and skip cleanly where a dependency is absent.
