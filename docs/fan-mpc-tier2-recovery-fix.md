# Fan-MPC Tier2 encounter and route recovery

## Reproduction

The original GUI tuple is `paper_ccta2023_multiship`, `potocnik_colreg_fan_mpc`,
God tracker, `fcb45_3dof_plant+pass_through_guidance+fcb45_marine_pid`, ideal
actuation, calm water, seed 0. The route, targets, 0.1 s simulation step,
1800 s time limit, 5 s solve period, and shipped planner configuration were
retained. Baseline source: `46b50cda`.

The baseline replay reproduced all three reported symptoms:

- At 400 s, RETURN selected a left correction toward the incoming leg. At
  600 s, ownship was 407.25 m west of the northbound leg.
- CS repeatedly reported `minimum_colreg_action` and `pass_astern`
  relaxations. The realized TS2-track crossing at 753.6 s was about 784.5 m
  ahead of TS2, not astern.
- The final leg selected the destination's zero speed as its transit speed.
  At 1300 s the command was zero; the controller transient included negative
  surge (minimum -1.41 m/s). No goal event occurred by 1800 s.

`tmp/debug_fan_multiship/replay.py` reproduces the three decision failures in
about 2.5 s using frozen real solver inputs/state. ENC geometry is cached for
replay; no live GUI session is modified. Minimal regression tests initially
failed for corner recovery, terminal speed, and CS action reference.

## Causes and changes

1. **Mission route and speed.** Fan guidance selected the nearest leg anew
   and clipped lookahead at its endpoint. It now preserves forward segment
   progress, permits adjacent-leg recovery on the inside of a corner when
   chasing the incoming leg would reverse the intended turn, and carries
   lookahead across the route polyline. The ordinary leg speed comes from
   its departure waypoint, matching native LOS, rather than the arrival
   waypoint. This removes both premature speed changes and the terminal
   zero-speed trap. Session goal completion remains authoritative.

2. **Action direction.** The right-turn constraint was measured from the
   changing LOS recapture bearing. When that bearing lay outside the bounded
   fan, the planner relaxed the constraint and continuity could preserve a
   wrong course. New encounters retain an action reference separate from LOS.
   Anticipated HO at a bend uses the intended-leg reference; feasible
   rightward steps reach it within the existing command rate before requiring
   the complete starboard offset. Astern constraints retain priority over
   the command-rate preference. Disjoint encounters get a fresh reference.

3. **Passing side.** A closest point within a truncated horizon is not the
   target-track crossing. Candidate filtering now checks interpolated track
   crossings for ahead/astern position. When a crossing lies beyond the
   rollout, terminal relative motion supplies a passing-side forecast.
   This extension is not an additional guaranteed safety horizon: the normal
   rolling solve and continuous hard clearance checks remain necessary.

4. **Encounter continuity.** A temporary avoidance heading must not lock a
   distant future target when mission-leg continuation is clear. Initial
   give-way activation checks the existing hull-inflated clearance on the
   intended leg, or current-motion entry into that clearance within the
   existing prediction horizon. Every track still participates in candidate
   collision checks. When intended motion exposes a future conflict, its
   geometry also supplies the encounter kind; current geometric diagnostics
   remain separate. An approaching encounter retains its type through the
   maneuver instead of changing CS into HO or vice versa as ownship turns.

No scenario IDs or time triggers were introduced into the planner. Collision
clearances, static clearances, prediction length, PID gains, and plant physics
were not loosened. This is the engineering Fan-MPC extension, not a claim of
numerical reproduction of the original paper. Its diagnostics do not replace
canonical Threat Management or the independent evaluator.

## Original three-target run

| Measure | Baseline | Fixed |
| --- | ---: | ---: |
| Goal reached | No, at 1800 s limit | 1390.8 s |
| Absolute active-leg XTE at 600 s | 407.25 m | 53.21 m |
| Minimum ownship speed | -1.41 m/s | 4.23 m/s (8.22 kn) |
| TS1 minimum center distance | 311.57 m | 378.24 m |
| TS2 minimum center distance | 261.53 m | 344.95 m |
| TS3 minimum center distance | 235.70 m | 369.73 m |
| TS2 first track crossing | 784.5 m ahead | 533.6 m astern |
| Last 30 s maximum absolute XTE | 344.60 m | 3.18 m |

Planner encounter sequence is OT/TS1, CS/TS2, HO/TS3. HO is active from
970 s to the 1105 s release solve; TS3 is abaft ownship at release. Recovery
reaches TRACK by 1315 s. No collision, grounding, reverse transit command,
or policy relaxation occurs in the fixed three-target run.

Active-leg XTE changes its reference when the selected leg advances. The
jump around the first corner is a reference change, not an instantaneous
physical displacement. Avoidance still intentionally leaves the route to
maintain target clearance; recovery convergence is assessed after passing.

## Verification

Commands:

```bash
.venv/bin/pytest -q tests/test_fan_mpc_recovery.py \
  tests/test_potocnik_colreg_mpc.py tests/test_fan_mpc_tier2.py \
  tests/test_potocnik_colreg_g3_matrix.py
.venv/bin/ruff check colav_simulator/integrations/potocnik_colreg_mpc.py \
  tests/test_fan_mpc_recovery.py tests/test_fan_mpc_tier2.py
.venv/bin/python tmp/debug_fan_multiship/replay_final.py
```

Final results: **39 passed** in the combined command (605.67 s). The
three-target test was additionally rerun with the sequence/abaft-release
assertions: **1 passed**. Ruff and `git diff --check` pass. All **279** saved
solver snapshots reproduce identical controls, predicted trajectories,
constraints, and next-state continuity with the final source.
The Tier2 test covers actual forward speed, all ownship-target distances,
no policy relaxation, rightward action onset, realized CS astern passage,
OT/CS/HO sequence, HO abaft release, natural goal, and final recovery.
The existing six-scene G3 matrix checks its separate legacy-stack acceptance.
Neither is full-repository/remote-CI acceptance or all-vessel safety proof.

Local artifacts: `tmp/debug_fan_multiship/`, including before/final frames,
solver snapshots, event logs, `comparison.png`, metrics, and rejected
intermediate experiments. The GUI service is not restarted by these tests.
