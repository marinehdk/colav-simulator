# Kuwata VO Reconstruction Validation

Date: 2026-07-30

Label: `kuwata_2011_behavior_compatible_reconstruction`

Command:

```bash
.venv/bin/python examples/validate_kuwata_vo.py \
  --include-project-fixtures \
  --output-root runs/kuwata_vo_validation
```

Machine-readable matrix:
`runs/kuwata_vo_validation/capability_matrix.json`.
Every scenario directory also contains `summary.json`, `timeline.csv`, and
`closed_loop_diagnostics.png`.

## Verification

- Five-layer targeted VO suite: `52 passed`.
- Full regression: `267 passed, 2 skipped`.
- Targeted Ruff: passed.
- `git diff --check`: passed.

## Closed-loop capability matrix

Collision truth uses `continuous_footprint_collision`. Clearance is sampled
footprint distance and is not used as a collision substitute.

| Scenario | Causal nominal threat | Ship0 collision | Global collision | Hull clearance | COLREG entry / first body-starboard command | Release | Fallback | Result |
|---|---|---:|---:|---:|---|---:|---:|---|
| Head-on | collision | no | no | 7.10 m | 144.0 s / +1.75 m/s, `HO` | yes | 0 | pass |
| Starboard crossing | collision | no | no | 39.65 m | 83.0 s / +2.08 m/s, `CR_SS` | yes | 0 | pass |
| Port crossing, stand-on target violates | collision | no | no | 22.32 m | 83.0 s / -0.37 m/s, `CR_PS` | yes | 0 | pass; base VO emergency protection |
| Ownship overtaking | collision | no | no | 6.48 m | 191.0 s / +2.06 m/s, `OT_ing` | yes | 0 | pass |
| Ownship overtaken | clearance below 5 m | no | no | 11.88 m | 174.0 s / 0.00 m/s, `OT_en` | yes | 0 | pass; no V1 direction constraint |
| Three targets | collision | no | **yes** | 7.62 m | 188.5 s / -0.38 m/s | yes | 0 | Ship0 pass; global deferred |
| Dynamic target plus local island | grounding | no | no | 1738.30 m to vessel | no dynamic rule | n/a | 0 | pass; no grounding |
| 20 dynamic targets | performance-only; no nominal threat | no | no | 111.07 m | active at 0 s | no, run ends at 30 s | 0 | performance pass |
| Both head-on vessels use VO | uses head-on nominal baseline | no | no | 35.03 m | both `HO` at 144 s; both +2.69 m/s | both yes | 0 | pass |
| Static blockage | starts inside blocking land | no | no | n/a | n/a | n/a | 1 | expected `INFEASIBLE` |

The multi-target global collision is between target vessels that do not run
VO. Ship0-to-target safety passes; global fleet safety does not. Per current
scope decision, multi-vessel VO acceptance is deferred and is not a completion
gate.

## Performance

The 20-target, `32 x 128` grid run measured planner latency of 153.06 ms p50,
199.85 ms p95, and 537.01 ms maximum. All solves stayed below the 1 s project
acceptance limit. This is Python closed-loop evidence, not a reproduction of
the paper's C++ timing.

## Profiles and provenance

Default reconstruction uses `w_ttc=500`, WVO scale `0.25`, and square
velocity uncertainty `W_B=+/-1.2 m/s` per axis. The local-island fixture uses
`w_ttc=100` and `W_B=+/-1 m/s` per axis. The dual-VO head-on fixture uses
`w_ttc=1000`, WVO scale `1`,
and `W_B=+/-2 m/s` per axis. All three numerical profiles are
`inferred_reconstruction`, not paper-explicit values. Full provenance is in
`docs/kuwata_vo_reconstruction.md`.

## Evidence conclusions

**Raw safety:** Head-on, both crossing cases, overtaking, overtaken, Ship0 in
the three-target case, local island, 20-target case, and dual-VO head-on have
no continuous footprint collision. Local-island VO has no grounding.

**COLREG action quality:** Head-on and starboard crossing enter their rule
sets from the nominal CPA gate, make a positive body-frame starboard first
action, never select base VO or forbidden V1 candidates, and release after
past-and-clear. Port crossing and being overtaken have no V1 direction
constraint but retain base-VO emergency protection. Dual-VO head-on shows
both vessels command and execute starboard displacement.

**Paper structure:** Tests cover rectangular Minkowski expansion, relative-ray
first TTC, WVO Minkowski uncertainty, V1/V2/V3 partitioning, hard base VO and
V1 exclusion, soft WVO TTC cost, deterministic `32 x 128` search, multiple
hazards, CPA rule screening, per-rule hysteresis, and local static hazards.
This is structural and behavior-compatible evidence, not a numerical
reproduction of the unavailable 2014 journal implementation.

## Preserved failure evidence

- Default `w_ttc=100` missed the existing multi-target G3 clearance for two
  targets. `w_ttc=500` fixed that earlier profile. After nominal-velocity CPA
  eligibility was restored, `W_B=+/-1 m/s` missed the single-target G3
  clearance (6.79 m versus 8.87 m required). The smallest tested passing
  tested G3-passing profile, `W_B=+/-1.1 m/s`, reaches 9.46 m but its first
  closed-loop head-on action is to port. `W_B=+/-1.2 m/s` is the smallest
  tested profile that also produces the required first starboard action.
- A centered symmetric island produced oscillation and grounding. It remains
  outside accepted evidence; the accepted fixture is explicitly asymmetric
  and locally bypassable.
- Default dynamic profile in the dual-VO head-on case produced correct
  starboard commands but a real footprint collision from insufficient
  execution margin. The stronger inferred WVO profile passes.
- `w_ttc=500` conflicted with the accepted local-island geometry. A separately
  labeled inferred local-island profile passes; no universal paper weight is
  claimed.
- Global all-vessel safety fails in the three-target scenario because target
  vessels collide with each other.
- The 20-target fixture is not causal avoidance evidence because its nominal
  baseline is already safe.

## Not reproduced

No full COLREG Rules 2-19 legal semantics, visibility rules, Rule 8/16/17
seamanship judgment, acceleration or rudder reachable set, vessel-dynamics
optimization, global route search, concave-island escape, depth/UKC/CATZOC
reasoning, or 2014 journal numerical identity is claimed.
