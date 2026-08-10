# Mid-MPC IPOPT migration validation

## Scope and provenance

- Source: private MASS-L3 GitLab `l3-tdl` at
  `ced58f8576f3772ef7c1bc72bb0f8b0368688b5a`.
- Ported surface: Mid-MPC nonlinear program, constraint rows, IPOPT solve, and
  normalized diagnostics.
- Colav-Simulator surface: `PlannerInput -> MPCSolution`, LOS route reference,
  encounter classification, target selection, scheduling, deadline handling,
  reset, trace, registry, capability evidence, and scenario harness.
- Excluded: ROS2 messages and nodes, M4/M6/M7, GNC publication, acados,
  BC-MPC, vessel-specific plant logic, static/ENC/grounding avoidance, fallback,
  and UI work.

Runtime dependency is pinned to CasADi 3.7.2. The wheel used for the checked-in
oracle and Python tests bundles Ipopt 3.14.11. MASS-L3 pins Ipopt 3.14.19, so
the contract is numerical tolerance rather than byte identity.

## Changed modules

- `colav_simulator/core/colav/mid_mpc`: immutable problem/result models and the
  parity-preserving CasADi/IPOPT core.
- `colav_simulator/integrations/mid_mpc_ipopt.py`: Colav-native facade and
  `CustomMPCAdapter` integration under stable id `mid_mpc_ipopt`.
- `config/mid_mpc_ipopt.yaml`: published planner profile.
- `colav_simulator/experiment/capabilities.py` and
  `colav_simulator/integrations/registry.py`: registry and evidence surface.
- `tools/mid_mpc_ipopt_oracle`: frozen C++ exporter and compatibility-only
  optimizer data types.
- `tests/fixtures/mid_mpc_ipopt/v1.jsonl`: eight C++/IPOPT oracle records.

## Numerical parity

The eight oracle records cover route/speed tracking, head-on and crossing
starboard constraints, stand-on HOLD, overtaking port preference, nonzero CPA
slack, committed prefix `K=2`, and two-target row ordering. They include
prepared `p/x0/lbx/ubx/lbg/ubg`, raw `x/f/g`, row layout, both raw slacks,
public trajectory/status, continuous CPA diagnostics, normalized core intent
and row schedule, and eight independently evaluated objective components. All
eight pass the Python core's recorded tolerances without fixture-id metadata
lookups.

Regenerate the oracle from a detached frozen MASS-L3 worktree:

```sh
git -C "/path/to/MASS-L3-Tactical Layer" worktree add --detach \
  "/tmp/mass-mid-mpc-frozen" \
  ced58f8576f3772ef7c1bc72bb0f8b0368688b5a

sh tools/mid_mpc_ipopt_oracle/export_oracle.sh \
  "/tmp/mass-mid-mpc-frozen" /tmp/mid_mpc_ipopt_v1.jsonl
```

The exporter rejects any other source commit. It compiles the frozen
formulation, solver, and constraint compiler without modifying or copying MASS
production source into this repository.

## Closed-loop evidence

Five fixed-seed, God-tracker single-encounter runs pass raw G3, evaluator hard
gates, COLREG direction/timing assertions, recovery assertions, real IPOPT
execution, and strict no-fallback identity checks:

| Scenario | Minimum Ship0 hull clearance |
| --- | ---: |
| `head_on` | 507.58 m |
| `crossing_give_way` | 407.43 m |
| `crossing_stand_on` | 53.43 m |
| `overtaking` | 63.61 m |
| `overtaken` | 78.48 m |

`paper_ccta2023_multiship` also passes the Ship0 raw G3 and evaluator hard
gate. Ship0 clearances to Ship1/Ship2/Ship3 are 217.842 m, 156.517 m, and
80.080 m. All 100 solves report real IPOPT success, no fallback, multi-contact
selection, and route/speed recovery.

Global all-vessel safety does not pass in that paper scenario: scripted target
ships make three target-target contacts, present in nominal and Mid-MPC runs.
Mid-MPC controls Ship0 only. This evidence therefore proves Ship0-vs-target
safety, not global target-vessel safety.

A final-tree live feature-worktree server on port 8011 produced session
`ff7b4729-d077-4c87-b2c6-018cef05d6ac` and a planner event with
`solver_executed=true`, algorithm `mid_mpc_ipopt`, backend IPOPT,
`Solve_Succeeded`, 50 iterations, 470.24 ms event elapsed, objective 15.6673,
selected targets `[2, 1]`, and zero reported nonnegative slacks. The existing
main service on port 8010 (PID 64401) was not replaced.

## Reproduce tests

From this repository checkout:

```sh
uv sync --group dev

uv run pytest -q \
  tests/test_mid_mpc_parity_fixtures.py \
  tests/test_mid_mpc_ipopt_core.py \
  tests/test_mid_mpc_ipopt_integration.py

uv run pytest -q tests/test_mid_mpc_single_encounter.py
uv run pytest -q tests/test_mid_mpc_multiship_runtime.py
uv run pytest -q
```

Final-tree results: 69 focused parity, core, adapter, capability, scenario, and
API tests passed in 259.18 seconds; the full suite completed with 408 passed,
2 skipped, and 1 Starlette deprecation warning in 947.74 seconds.

Start an isolated feature server without disturbing the fixed main port:

```sh
uv run colav-sim serve --host 127.0.0.1 --port 8011
```

In another shell, create the agreed multiship run, execute its first step, and
inspect the real planner trace:

```sh
BASE=http://127.0.0.1:8011
SESSION_ID=$(
  curl -fsS -X POST "$BASE/api/sessions" \
    -H 'content-type: application/json' \
    -d '{
      "validation_rule_id":"multiship",
      "scenario_id":"paper_ccta2023_multiship",
      "algorithm_id":"mid_mpc_ipopt",
      "tracker_id":"god",
      "seed":0,
      "strict_no_fallback":true,
      "t_end":0.2
    }' | jq -r .session_id
)

curl -fsS -X POST "$BASE/api/sessions/$SESSION_ID/step" |
  jq '.latest_planner_solve | {
    algorithm_id, solver_executed, status, iterations, elapsed_ms,
    objective, feasible, constraints, algorithm_details
  }'
```

Expected identity fields are `algorithm_id="mid_mpc_ipopt"`,
`solver_executed=true`, `status="SUCCESS"`, `feasible=true`,
`algorithm_details.solver_backend="ipopt"`, and
`algorithm_details.ipopt_return_status="Solve_Succeeded"`. Iterations, elapsed
time, objective, selected targets, and slack values are machine-dependent
diagnostics and must be finite rather than copied as golden constants.

## Known boundaries

- The frozen equations intentionally retain upstream quirks needed for parity:
  own `k+1` versus target `k` CPA indexing, disabled midpoint CPA rows,
  graph-baked target rows, unused transition weight, and no upstream warm start.
- The facade compensates the preserved node-index offset using both vessel
  footprint radii and own maximum one-step displacement. It does not rewrite
  frozen core mathematics.
- Although frozen configuration parsing accepts horizons up to 120, its fixed
  142-slot parameter layout reserves prefix values for only 18 steps; larger N
  overlaps target slots. This port rejects `N > 18` rather than reproduce that
  unsafe aliasing. The published Colav profile uses N=18.
- Both IPOPT CPU-time control and the frozen 20-second wall-clock iteration
  abort are active in the Python solver.
- IPOPT soft direction and squared-distance CPA slacks can be materially
  nonzero while raw rows remain feasible. Scenario acceptance independently
  checks synchronized hull clearance and maneuver behavior.
- Capability evidence is fixed-seed God-tracker G3 for the agreed scenarios.
  It is not MASS-L3 ROS2/GNC/M7, A4000/SIL, ENC, or global all-vessel acceptance.
- The stable algorithm id is registered and callable through the backend. No
  Web GUI selector/card was added because UI work is outside this migration.
