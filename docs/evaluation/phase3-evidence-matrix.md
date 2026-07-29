# Phase 3 Evaluation Matrix

> Profile: `ccta_2023_demo-v1`
> Seed: `0`
> Tracker: `god`
> Strict no fallback: `true`
> Test: `tests/test_phase3_evaluation_matrix.py`
> Full regression: `214 passed, 2 skipped`

## Result

| Algorithm | Head-on | Overtaking | Overtaken | Crossing GW | Crossing SO | Multi-ship |
|---|---:|---:|---:|---:|---:|---:|
| VO | PASS | PASS | PASS | PASS | PASS | PASS |
| SB-MPC | PASS | PASS | PASS | PASS | PASS | PASS |
| Potočnik simplified MPC | PASS | PASS | PASS | PASS | PASS | PASS |

PASS means:

- requested algorithm equals executed algorithm;
- no fallback;
- evaluation schema complete;
- Ship0-vs-target physical collision/grounding hard gate passes;
- instantaneous and actual-trajectory CPA evidence exists;
- applicable pairwise FSM transitions exist;
- every safety metric carries formula evidence.

This matrix proves traceable Phase 3 evaluation on the existing raw G3 cells. It
does not prove G4, statistical superiority, full COLREG coverage, or numerical
paper reproduction.

Multi-ship target-target contacts are reported by
`global_all_vessel_collision_count` but do not fail the Ship0 algorithm hard
gate. Ship0-vs-target and all-vessel safety must not be conflated.

Target-vessel grounding is likewise reported globally but does not fail the
Ship0 algorithm gate.
