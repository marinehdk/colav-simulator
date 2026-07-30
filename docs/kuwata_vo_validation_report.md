# Kuwata VO Reconstruction Validation

Date: 2026-07-30

Label: `kuwata_2011_behavior_compatible_reconstruction`

Profile: seed `0`, God tracker, strict no fallback, `t_max=120 s`,
`d_min=100 m`.

## Verification

- Standard six-scenario raw G3: `6/6 PASS`.
- Phase 3 evaluator chain for VO: `6/6 PASS`.
- VO behavior, decision-space API, and web targeted suite: `52 passed`.
- Full regression: `273 passed, 2 skipped`.
- Targeted Ruff, JavaScript syntax, and `git diff --check`: passed.

Commands:

```bash
MPLBACKEND=Agg uv run pytest \
  tests/test_rule14_planner_trace.py \
  tests/test_rule13_15_g3_matrix.py \
  tests/test_multiship_g3.py \
  tests/test_phase3_evaluation_matrix.py -q

MPLBACKEND=Agg uv run pytest \
  tests/test_kuwata_vo_paper_reconstruction.py \
  tests/test_kuwata_vo_closed_loop.py \
  tests/test_web_api.py -q
```

## Raw G3 evidence

Distances below are synchronized center distance from the versioned G3
predicate. Footprint distance is the sampled rectangle-to-rectangle distance.
Physical collision uses the continuous `c2a-rect2d-v1` oracle.

| Scenario | Center min | Footprint min | Max heading delta | Max speed delta | Solves | Result |
|---|---:|---:|---:|---:|---:|---|
| Head-on | 321.34 m | 316.75 m | 59.66 deg | 0.56 m/s | 300 | PASS |
| Overtaking | 234.13 m | 226.37 m | 27.31 deg | 0.71 m/s | 300 | PASS |
| Overtaken | 15.62 m | 11.60 m | 36.53 deg | 1.59 m/s | 300 | PASS |
| Crossing give-way | 456.96 m | 450.05 m | 18.27 deg | 5.23 m/s | 300 | PASS |
| Crossing stand-on | 9.81 m | 2.06 m | 51.16 deg | 1.02 m/s | 284 | PASS |
| Three targets | 98.75 m | 93.12 m | 55.29 deg | 3.99 m/s | 482 | PASS |

All cells have requested algorithm equal to executed algorithm, zero fallback,
zero Ship0 collision, and zero Ship0 grounding. No standard cell uses
`emergency_rule_relaxation`.

Multi-ship Ship0 clearance by target is `98.75 m`, `365.82 m`, and
`282.46 m` center distance. Three target-target collisions remain. Ship0
safety passes; global all-vessel safety fails.

## Crossing action quality

Crossing give-way:

- `CR_SS_COMMITTED` entry: `26.0 s`, inside the `120 s` CPA horizon.
- First active command: `+1.49 m/s` body-starboard.
- Active selected-course reversals above `2.5 deg`: `0`.
- Closest-approach target stern-plane clearance: `107.04 m`.
- Commitment released after the encounter; no emergency relaxation.

Crossing stand-on:

- Before current velocity enters the base VO, maximum heading deviation:
  `0.0 deg`.
- Before base-VO entry, maximum speed deviation: `0.14 m/s`.
- Base-VO safety action starts at `179.0 s` in this non-cooperative target
  scenario.

These checks establish the requested project behavior policy. They do not
establish complete Rules 8/15/17 compliance or numerical paper reproduction.

## Decision-space evidence

`vo_velocity_space.v1` exposes the real `32 x 128` solve grid only through:

```text
GET /api/sessions/{session_id}/planner/decision-space?solve_id=N
```

The snapshot preserves overlapping base-VO, WVO, COLREG V1, and crossing
commitment state bits. Non-finite cost/TTC values serialize as JSON `null`.
Dense arrays are absent from 10 Hz telemetry and evidence frames.

## Reproduction boundary

The implementation reproduces paper structure: VO/WVO partitioning, TTC and
reference-velocity cost, COLREG candidate regions, hysteresis, and
deterministic grid search. The `120 s`, `100 m`, crossing commitment, and
stand-on hold are documented project profiles. No full legal COLREG
compliance, vessel-dynamics optimization, or numerical identity with the
paper is claimed.
