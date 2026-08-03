# Romsdal Busy-Water Scenarios

## Scope

The two deterministic Romsdal scenarios are behavior-compatible stress fixtures
inspired by the traffic density in Potočnik (2025). They do not reproduce the
paper's Adriatic route or numerical results. The paper demonstration used 80
ships, a 3000 s limit, 45 fan trajectories, and 16 prediction steps. Its video
seed, GSHHG coastline subset, and exact Split-Sućuraj route are unavailable.

The first implementation uses the existing validated 5 x 5 km navigable subset
of `More_og_Romsdal_utm33.gdb`. Expanding to the full Romsdal source window
requires a separately validated route and cached ENC preprocessing; it is not
implied by these scenarios.

## Scenarios

### `romsdal_busy_water_16`

- Ship0 plus 15 scripted targets, 600 s, `dt_sim=0.1 s`.
- Default mix is crossing 60%, head-on 20%, and overtaking 20%. Fifteen targets
  therefore produce 9 CS, 3 HO, and 3 OT routes. CS and OT responsibility roles
  alternate with a difference of at most one.
- Every target follows one constant-speed, two-point shuttle route near Ship0's
  nominal lane. Endpoint overshoot is reflected and the vessel reverses course.
- Nominal, VO, SB-MPC, and COLREG fan MPC are selectable with God tracker as
  experimental G2 combinations. Selection is not verified G3 evidence.

### `romsdal_busy_water_80_stress`

- Ship0 plus 79 scripted targets, 600 s, `dt_sim=0.5 s`.
- Same route-adjacent seeded generator and crossing-dominant distribution.
- Capacity and UI-load fixture only. Global collision freedom and algorithm G3
  are not claimed.
- Live per-step Ship0 CCD is disabled only for this stress fixture. Final
  evaluation uses a conservative broad phase, then runs the full C2A footprint
  oracle for every potential contact and the nearest pair. Its evaluation
  status remains `PARTIAL`; the 16-ship acceptance scenario keeps full CCD.
- The committed 600 s fixture replaces the paper's 3000 s duration as the
  practical interactive target. A 3000 s run remains an optional soak test.

## Generate And Preflight

The committed YAML files are runtime truth. Tests regenerate them and compare
the normalized documents to prevent drift.

```bash
MPLBACKEND=Agg .venv/bin/python -m colav_simulator.cli busy-water-generate \
  --profile acceptance \
  --seed 20250731 \
  --target-count 15 \
  --crossing-ratio 0.6 --head-on-ratio 0.2 --overtaking-ratio 0.2 \
  --output scenarios/romsdal_busy_water_16.yaml

MPLBACKEND=Agg .venv/bin/python -m colav_simulator.cli busy-water-generate \
  --profile stress \
  --seed 20250731 \
  --output scenarios/romsdal_busy_water_80_stress.yaml

MPLBACKEND=Agg .venv/bin/python -m colav_simulator.cli busy-water-preflight \
  scenarios/romsdal_busy_water_16.yaml --with-enc

MPLBACKEND=Agg .venv/bin/python -m colav_simulator.cli busy-water-preflight \
  scenarios/romsdal_busy_water_80_stress.yaml --with-enc
```

Static preflight checks ship count and IDs, active windows, initial footprint
separation, map bounds, nominal target-target collisions, planned encounter
roles, navigable initial points, and scripted route intersections with ENC
hazards.

## Interactive Authoring

Open the busy-water settings button on the chart to choose 3-79 targets, seed,
and encounter ratios. The generated document enters the normal RunSpec,
manifest, scenario hash, and evaluation path as a validated override.

Before starting the simulation, select any target ship to edit speed and both
UTM route endpoints. Endpoints may be typed or picked on the map. Applying an
edit creates a new paused session; a running session is never mutated. Complete
documents can be saved and reloaded from ignored `runs/scenario_drafts` YAML
files, preserving every vessel state and route.

## Evidence Boundaries

`run_metrics.json` separates three evidence layers:

- `ship0_safety`: fallback, grounding, Ship0 collision evidence, and per-target
  conservative footprint-clearance lower bounds.
- `global_world_events`: all-pair collisions, grounded vessel IDs, and nearest
  vessel pair.
- `traffic_load`: active/risk target counts, step latency, and solver latency.

Ship0 safety does not imply global fleet safety. Raw collision and grounding
gates do not prove smooth or legally compliant COLREG maneuvers. The acceptance
scenario stays G2 until its maneuver-quality observations are reviewed and
committed as versioned evidence.

For the 80-ship fixture, use Nominal first to measure simulator and browser
capacity independently of planner complexity. A COLREG fan MPC soak is a
separate algorithm-load test; it must not silently lower its 5 s solve period
or reuse a nominal result as algorithm evidence.
