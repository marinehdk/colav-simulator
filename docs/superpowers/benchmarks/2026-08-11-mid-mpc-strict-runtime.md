# Mid-MPC COLAV_STRICT Runtime Evidence

## Scope

- Date: 2026-08-11
- Machine: Apple arm64, macOS 26.5.2
- CasADi: 3.7.2, bundled IPOPT
- Problem: 80 intervals, 15 s step, deterministic cold seed, fixed-zero CPA/direction slack
- Samples: five solves for each 0/1/16-target case
- Cache: no graph cache exists; every sample rebuilds the CasADi/IPOPT graph
- Targets: constant-velocity, non-threatening benchmark contacts

## Results

| Targets | Samples (ms) | p50 (ms) | p95 (ms) | max (ms) |
|---:|---|---:|---:|---:|
| 0 | 537.762, 526.053, 522.770, 522.139, 522.765 | 522.770 | 535.420 | 537.762 |
| 1 | 593.465, 597.677, 593.149, 593.535, 593.874 | 593.535 | 596.916 | 597.677 |
| 16 | 1447.277, 1446.139, 1439.634, 1439.987, 1436.519 | 1439.987 | 1447.049 | 1447.277 |

All 15 solves returned `Solved_To_Acceptable_Level/FeasibleNonOptimal` after one
iteration and passed the independent strict primal-bound check. Observed p95 is
below the configured 20 s deadline for all three loads.

Five samples and non-threatening contacts make this regression evidence, not a
general real-time or adversarial 16-target capability claim. Closed-loop
HO/CS/OT and multiship tests remain the behavior/safety gate.
