# Mid-MPC static ENC constraints

The native Mid-MPC adapter requires ENC input and constrains known land,
shore, unsafe depth areas and reef geometry throughout its prediction horizon.
Static rows have no slack. An infeasible solve cannot return a fallback command.
The frozen `MASS_PARITY` assembly does not add ENC rows.

## Source geometry

`extract_typed_grounding_hazards` remains the common geometry source for planning,
L4 evidence and grounding evaluation. The simulator's online grounding check also
uses its union. The minimum available depth bin at or above vessel draft defines
the shallow-water exclusion.

Seacharts exposes land, shore and depth polygons but omits the point reef layers
in the local Kartverket database. `enc_point_hazards.py` loads the current ENC
window from the same configured source files, transforms source coordinates to
the ENC's EUREF89 UTM zone and retains a fixed source snapshot per ENC instance:

- `grunne` becomes `UWTROC`; retain depths at or below the required depth bin,
  and retain missing or nonfinite depths conservatively.
- `skjer` becomes `SKJER`; retain all exposed reef records.
- Explicit native ENC `uwtroc`/`obstrn` geometry remains authoritative when supplied.
- Unsupported layers keep `UNAVAILABLE_SOURCE`; absence is not evidence of an
  obstacle-free survey.

Kartverket explicitly maps [Grunne to S-57 UWTROC](https://objektkatalog.geonorge.no/Objekttype/Index/EAID_3BAB8089_444B_430c_94BB_8F75549C1089).
The [dataset specification](https://objektkatalog.geonorge.no/Pakke/Index/EAPK_BBE76DD8_33C1_421a_A67F_14822DA42B91)
defines the chart-datum depth and high-water references.

The installed three-target chart window contains 248 `grunne` records; a 2 m
minimum-depth bin selects 56, plus two `skjer` records. Point records do not
describe complete rock footprints. Tide, vertical UKC, chart positional accuracy
and unknown coverage remain outside this geometric constraint's evidence.

## Hard constraint and independent acceptance

The assembler builds an immutable signed-distance grid in absolute north/east
coordinates enclosing the complete supplied chart geometry. It is reused while
ownship moves, so movement does not trigger new graph construction. Polygon holes stay
navigable. Point and line features remain obstacles even when smaller than a grid
cell. Exact boundary-segment spatial queries accelerate grid construction.

For grid spacing `h = 20 m`, bilinear interpolation can overestimate a 1-Lipschitz
signed distance by at most `h / sqrt(2)`. The solver subtracts this bound. Each
control segment is checked at its midpoint, with an additional half-segment-length
allowance. Every point of the segment lies within that distance of its midpoint.
Thus each of the `N` static rows certifies the entire interval:

```
interpolated_distance - h/sqrt(2)
    >= circumscribed_hull_radius + 1 m + abs(speed)*dt/2
```

Outside the grid, the query is projected onto its enclosing box. If `q` is that
projection and all chart hazards `h` lie inside the box, then
`|p-h|² >= |p-q|² + |q-h|²`. This extends a conservative clearance bound outside
the grid without extrapolating its interpolant or assuming extra chart coverage.
Chart regions exceeding one million grid nodes are rejected explicitly.
The
static rows occupy `row_layout.zone`, always use `[0, +inf]` bounds, and are
independent of encounter activation, CPA slack, direction slack and prefix
softening. The 1 m value is horizontal clearance beyond the circumscribed hull;
it is separate from the configured ship-to-ship CPA clearance.

L4 receives original source geometry, not a solver safety verdict. It recomputes
the minimum distance of the entire predicted polyline from that geometry and
subtracts the circumscribed hull radius. HOLD validation refreshes chart evidence
and includes the connection from measured ownship position to the shifted plan.
Missing required ENC cannot dispatch a command through the native adapter.

Original geometry and source statuses are bound into request evidence. Numerical
grid values use lossless base64-encoded little-endian float64, north varying
fastest. This avoids repeated per-float evidence copies while preserving replay.
Static graph construction keeps the scenario's prewarmed target capacity and a
bounded cache of chart fields. Unallocated target slots have zero packed
weights; their identically zero cost terms are omitted during static graph
construction, with the frozen normalization preserved. Cost and gradient
equivalence to the full-slot expression are tested.
The existing retry budget now covers assembly, chart preprocessing, graph
construction and solver preparation, with the L4 reservation deducted before
IPOPT starts. Timing a fresh two seconds only around IPOPT could exceed the
retry cycle's budget after adding ENC work. The 20 s production deadline and
all physical acceptance thresholds remain unchanged.
Static checks expose `SAFETY_STATIC_VALID` / `SAFETY_STATIC_CLEARANCE` and a
clearance witness. Adapter diagnostics include the static row count and margin.

## Validation scope

`tests/test_mid_mpc_static_hazards.py` exercises real IPOPT island avoidance,
reef and obstruction input, between-knot crossing rejection, measured-position
HOLD coverage, depth selection, polygon holes, source changes, actual Kartverket
records, missing ENC and a physically blocked local planning problem.

`tests/test_mid_mpc_anticipatory_runtime.py` checks the complete three-target run,
every emitted actual position and every executable predicted polyline against
ENC geometry. All three targets must receive anticipatory scheduling, enter
ACTIVE in order and reach RELEASED. The test retains its 250 m
minimum realized target range and 2 s planning-time gates.

This is local simulation evidence for the tested inputs, not full COLREG,
all-scenario, chart-coverage or MASS-L3 system acceptance. Conservative circular
hulls and grid/sweep allowances can reject narrow passages that a detailed hull
planner could navigate. No global route search is added.

## Verified result — 2026-09-08

- Focused core, parity, integration, grounding, evaluator and GNC boundary
  regression: **266 passed, 1 deselected**. The deselected audit is listed below.
- Static-specific tests, including the added outside-grid swept-row witness:
  **15 passed**.
- Complete three-target runtime: **1 passed**, all original scheduling,
  ordered ACTIVE, final RELEASED, 250 m separation and 2 s latency checks retained.
- Lint and `git diff --check` passed. Existing unrelated formatter differences
  in `map_functions.py` and the two GNC audit files were reproduced on HEAD
  and left untouched.

| Runtime measurement | Result |
| --- | ---: |
| Goal reached at simulation time | 1380.0 s |
| Minimum center ranges to targets 1 / 2 / 3 | 296.27 / 284.07 / 277.70 m |
| Minimum predicted static hull-clearance lower bound | 75.29 m |
| Minimum sampled actual static hull-clearance lower bound | 115.44 m |
| Maximum complete planning latency | 1342.98 ms |
| Fallback used | false |

Local evidence is in `tmp/debug_mid_static/`: `three_target_metrics.json`,
`final_closed_loop.log`, `final_validation.log`, `final_static.log`,
`first_accepted.json.gz`, `last_accepted.json.gz`, and the island comparison
PNG/JSON. The original island-crossing regression was reproduced before the fix;
the constrained real IPOPT prediction clears the island and continues forward.

Known prior failure: `test_mid_mpc_preserves_accepted_plan_when_candidate_is_rejected`
in `tests/test_gnc_planner_audit.py` expects a retained plan across a mission-route
change. The same failure was reproduced using an untouched archive of HEAD
`14730d7b`; it is not repaired or waived by this static-constraint change.
Its separate result is recorded in `preexisting_gnc_audit.log`.
