# Potočnik COLREG Fan MPC

## Identity

`potocnik_colreg_fan_mpc` is an executable, COLREG-aware extension of the
paper-derived fan planner. It is intentionally separate from
`potocnik_simplified_mpc`, which remains the behavior-compatible reference
profile for Potočnik (2025), Equations (13)-(17).

This extension is not a numerical reproduction of the paper and is not a
continuous nonlinear MPC solver. It performs deterministic, exhaustive
course-speed fan rollout, feasibility filtering, and receding-horizon
selection.

## Runtime behavior

- bounded first-order course and speed response predictions;
- an explicit control trajectory, held between five-second solves;
- command-course centering on the previous command, plus early-horizon
  trajectory continuity, to prevent receding-horizon branch jumps;
- `TRACK` / `AVOID` / `RETURN` maneuver phases with maneuver-course locking;
- line-of-sight route recapture using projection and a 200 m lookahead point;
- continuous relative-motion clearance checks between horizon samples;
- conservative vessel-radius inflation around the configured hull clearance;
- optional ENC grounding filtering using vessel draft and a swept centerline
  with a circumscribed footprint radius;
- persistent controller-side encounter classification;
- Rule 14 starboard action;
- Rule 15 give-way starboard action with pass-astern filtering;
- Rule 13 overtaking action with maneuver-side persistence;
- stand-on course/speed locking for Rule 13/15;
- documented stand-on and safety-buffer recovery when the nominal constraint
  is already infeasible;
- lower speed candidates used only when no faster rule-compatible candidate
  remains, followed by recovery toward route-plan speed.

The five-second solve period is retained. Increasing it to ten seconds would
hold stale commands for twice as long and delay safety reactions; plan
continuity and explicit return state address the observed oscillation instead.

Controller-side encounter logic is an operational policy, not a legal proof of
COLREG compliance. The evaluator remains independent.

## Verified project envelope

The seed-0 God-tracker raw G3 matrix passes for:

- `head_on`;
- `overtaking`;
- `overtaken`;
- `crossing_give_way`;
- `crossing_stand_on`;
- `paper_ccta2023_multiship`.

G3 proves Ship0 safety improvement, execution identity, completion, and no
fallback under the versioned display predicate. It does not prove numerical
paper reproduction, all-conditions COLREG compliance, or global target-vessel
safety in the multi-ship scenario. Target ships follow scenario trajectories
and are not controlled by this planner.

## Run

```bash
.venv/bin/python -m colav_simulator.cli plugin-check \
  --algorithm potocnik_colreg_fan_mpc \
  --algorithm-config config/potocnik_colreg_fan_mpc.yaml

MPLBACKEND=Agg .venv/bin/python -m colav_simulator.cli run \
  --scenario head_on \
  --algorithm potocnik_colreg_fan_mpc \
  --tracker god \
  --algorithm-config config/potocnik_colreg_fan_mpc.yaml \
  --seed 0

MPLBACKEND=Agg .venv/bin/python -m pytest -q \
  tests/test_potocnik_colreg_mpc.py \
  tests/test_potocnik_colreg_g3_matrix.py
```
