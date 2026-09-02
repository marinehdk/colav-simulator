# A3 Generalized-Simulation Controlled Demo

> Schema: `modular-gnc.a3-demo-report.v1`
> Claim ceiling: `A3` (Generalized Simulation)
> Module: `colav_simulator/modular_gnc/a3_demo.py`
> Test (evidence generator): `tests/test_modular_gnc_a3_demo.py`
> Reproduce: `.venv/bin/python -m pytest tests/test_modular_gnc_a3_demo.py -q`
> Parent issue: #41; demo issue: #61; prerequisite #60 (catalog + evidence labels)

This is the first controlled generalized-simulation demonstration. Two distinct
vessel presets execute one identical, branch-free closed loop through the
`ModularShipStack` facade: integral LOS guidance, marine PID, data-driven
allocator, resolved actuator dynamics, and the generic 3DOF plant. Preset
differences are pure configuration data (plant parameters, PID gains, actuator
layout assets, scheduler-agnostic scenario geometry); no code path branches on
vessel or scenario identity. Everything below is reproduced deterministically
by the test file in one local run; no external runtime is involved.

Every demo configuration is proven valid by `list_stack_catalog()`: the
module-identity combination (including the bound layout assets) equals a listed
entry, and the catalog validity rule (`normalize_ship_modules` +
`ModularShipStack.from_config` assembly + non-empty `supported_tasks`) replays
on the demo configuration itself. The parameter payload deliberately differs
from the catalog's synthetic scaffold parameters: the combination is listed,
the vessel parameters are data.

## Gate summary (G0-G10, three-state)

| Gate | Status | Scope |
|---|---|---|
| G0 | passed | Source integrity (pinned commit + characterization manifest hash) |
| G1 | passed | Interface and module contracts, catalog-listed assembly |
| G2 | passed | Physics kernel (RK4 order, dissipativity, Coriolis neutrality) |
| G3 | passed | Migration parity (legacy-equivalent structure, candidate A2 only) |
| G4 | passed | Intentional redesign ledger (18 decisions, spec-referenced) |
| G5 | passed | Module closed loop on both presets |
| G6 | passed | Existing regression (pinned legacy baseline comparison) |
| G7 | passed | Cross-vessel generality (two presets, one code path) |
| G8 | not run | COLAV integration (pending #62/#63; A4 scope) |
| G9 | passed | Actuator fidelity (resolved profile, rate limits honored) |
| G10 | not run | External platform adapter integration (later slice #64) |

`not run` gates carry no checks and no evidence claims; the COLAV and
platform-adapter classes below are reported as not run for the same reason.

## Vessel presets

Both presets share the module-identity combination
`generic_3dof_plant + integral_line_of_sight + marine_pid +
data_driven_allocator[layout] + resolved_actuator_dynamics[layout]` with
`supported_tasks = [TRANSIT]` and fidelity profile `resolved`.

`demo_preset_a` — lighter vessel, triple actuator layout, zero transport delay:

- Plant: mass 1.2e7 kg, I_z 2.0e10 kg·m², linear+quadratic surge/sway/yaw damping
- PID: kp (2.5e5, 1.5e5, 5.0e8), ki (8.0e4, 5.0e4, 1.0e8), kd (1.5e5, 8.0e4, 2.0e9),
  integral limit (2.6e5, 1.5e5, 2.0e7), output limit ±(9.0e5, 9.0e5, 3.0e7)
- Actuator data: `default_triple_actuator_layout_v1`, rate limit 4.0e5 N/s per
  actuator, delay 0 ticks
- Scenario: straight north route (0,0)→(800,0) at 2.0 m/s, start (0, 6, -0.05),
  1200 ticks at dt 0.1 s, seed 20260902
- `config_hash` `f61a3f5767d0d24bc006d716e92384dcf5947758e3bd4a59367fe0c83b42cbf1`
- Per-tick trace digest `9f2584f101d6c53584fce76c1e9aaed01251df6303f4515240200e3477ba0d14`

`demo_preset_b` — heavier vessel, quad diagonal actuator layout, one-tick
transport delay:

- Plant: mass 2.8e7 kg, I_z 6.0e9 kg·m², heavier linear+quadratic damping
- PID: kp (1.1e5, 6.0e4, 7.2e7), ki (2.0e4, 1.0e4, 0), kd (2.4e6, 8.0e5, 3.0e9),
  integral limit (9.0e5, 6.0e4, 8.0e6), output limit ±(1.5e6, 1.5e6, 2.4e7)
- Actuator data: `quad_diagonal_actuator_layout_v1`, rate limit 4.0e5 N/s per
  actuator, delay 1 tick
- Scenario: diagonal route (0,0)→(500,500) at 1.8 m/s, start (0, -15, 0.5),
  1600 ticks at dt 0.1 s, seed 20260902
- `config_hash` `e0887427ab370480ce8ddb38111459f9d2b04c8d03f5cedd3e9e092515aad429`
- Per-tick trace digest `ba192439ac6e22c345e2764dd270430fc141d9adc2b87ad687146c3f014abc04`

The two config hashes differ (distinct content-addressed configurations), and
both runs execute the same runner function with no identity branching (G7).

## Evidence classes (reported separately, never merged)

### Hydrodynamic (G2 — passed)

RK4 step-halving convergence order against a 64-substep reference, evaluated on
each preset plant through the public plant API:

- `demo_preset_a`: order 4.002392 (accepted band [3.5, 4.5])
- `demo_preset_b`: order 4.004669 (accepted band [3.5, 4.5])

Damping is energy-dissipative (νᵀD(ν)ν ≥ 0) and Coriolis power-neutral
(νᵀC(ν)ν = 0) at sampled velocities for both preset plants. No environmental
load modules are exercised in this demo; they remain catalog-scaffold scope.

### Guidance (G5 guidance records — passed)

| Preset | Initial \|XTE\| | Final \|XTE\| | Max \|XTE\| | Guidance ticks |
|---|---:|---:|---:|---:|
| demo_preset_a | 6.0000 m | 1.1856 m | 6.0000 m | 1200/1200 |
| demo_preset_b | 10.6066 m | 2.3330 m | 13.5507 m | 1600/1600 |

Shared acceptance bars (identical for both presets): final |XTE| ≤ 3.0 m and
max |XTE| ≤ initial |XTE| + 5.0 m. Both presets pass with zero facade failures
and the route consumed at every guidance tick.

### Control (G5 control records — passed)

| Preset | Final \|speed error\| | Controller ticks | Anti-windup active ticks |
|---|---:|---:|---:|
| demo_preset_a | 0.0399 m/s | 1200/1200 | 1199 |
| demo_preset_b | 0.0166 m/s | 1600/1600 | 1600 |

Shared bar: final |speed error| ≤ 0.2 m/s. Term-level traces (P/I/D/feedforward/
raw/saturated/achieved) are recorded every tick; the anti-windup back-calculation
path is exercised, not merely declared.

### Actuator (G5/G9 actuator records — passed)

| Preset | Fidelity | Actuator ticks | Rate-limited ticks | Delay (ticks) |
|---|---|---:|---:|---:|
| demo_preset_a | resolved | 1200/1200 | 10 | 0 |
| demo_preset_b | resolved | 1600/1600 | 8 | 1 |

Per-tick per-actuator delivered forces honor the declared rate limit
(|ΔF| ≤ rate·dt + 1e-6, verified for every actuator and every tick). The
nonzero rate-limited tick counts prove the resolved dynamics are active rather
than a silent ideal pass-through. Achieved loads stay finite; allocator force
saturation, effectiveness, and health remain owned by the allocator.

### COLAV (G8 — not run)

Not run. This demo exercises no COLAV authority: planner route audit and
tracked-route integration are pending (#62, #63). The ILOS module consumes a
directly supplied `TrackedRoute` at module level (covered by G5 module-closed-
loop evidence); that is not COLAV closed-loop acceptance, which is A4 scope.

### System (G0, G1, G3, G4, G6, G7, G10 — passed)

- G0: pinned legacy baseline commit `8968f31b982d48773d08f814439827328bf4b35d`
  matches the ticket map; the characterization fixture is bound to solution-pack
  source manifest SHA-256
  `2c863347de59474a32d26a53d5631ed9a5b376623cd88d6fb83ca8173fc09411`.
- G1: both demo configs normalize, assemble, support `TRANSIT`, are
  catalog-listed, and carry separated evidence fields (maturity, fidelity,
  asset trust, acceptance level).
- G6: the pinned legacy baseline comparison passes against
  `tests/fixtures/gnc_g6/legacy-baseline-v1.json`. This is the pinned-baseline
  regression scope; the full-suite regression is re-observed separately at
  acceptance time.
- G7: two presets, two distinct config hashes, identical code path, identical
  acceptance bars.
- G10: not run — no external platform adapter or simulation-time integration
  harness is exercised in this local demo; that scope remains with the later
  adapter slice (#64) and is not claimed here.
- Determinism (TS-15/SC-03): re-running a preset reproduces the trace digest
  bit-for-bit, and a mid-run snapshot restored into a fresh stack instance
  reproduces the straight-through digest exactly (pinned by
  `TestDeterminism`).

## Source parity vs intentional redesign (declared separately)

**Source parity (candidate A2, legacy-equivalent structure only).** The
four-arm attribution binding pins the `legacy` and `modular_legacy_equivalent`
arms to identical geometry and input hashes, and the modular legacy-equivalent
chain follows the latched kinematic reference schedule exactly (heading and
surge equal the latched references at every tick of the legacy scenario). Raw
trace hashes differ by state representation (legacy 4-element CSOG state vs
modular 6-element plant state) and are informational only; parity is claimed
through shared inputs and exact kinematic reference following, never through
hash equality.

**Intentional redesign (new factory, reported separately).** 18 spec-referenced
redesign decisions (6 generic 3DOF plant, 6 generic roll-4DOF plant, 6 marine
PID) are declared in the deviation ledger with their source behavior and
redesign behavior. The new-factory modules exercised by this demo (generic 3DOF
plant, ILOS, marine PID, data-driven allocator, resolved actuator dynamics) are
intentional redesigns; their behavior is covered by G2/G5/G9 evidence, not by
the parity claim above.

## Claim ceiling and non-claims

Ceiling: **A3 — Generalized Simulation.** Explicitly not claimed:

1. No vessel calibration is claimed at any point in this demo (A5 scope).
2. No COLAV closed-loop acceptance is claimed: G8 is not run and the COLAV
   evidence class is reported as not run (pending #62/#63).
3. No platform-adapter SIL/HIL acceptance is claimed: G10 is not run (later
   adapter slice #64).
4. No sea-trial or vessel validation claims of any kind are made; all assets
   remain mock-trust scaffolding and all claims stay at the A3 ceiling.

All actuator layout assets carry `mock` trust per the immutable asset metadata;
no result here may be presented as vessel-validated.
