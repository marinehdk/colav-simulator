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
| 0 | 575.406, 528.741, 536.249, 548.940, 537.106 | 537.106 | 568.790 | 575.406 |
| 1 | 584.995, 585.938, 583.898, 588.158, 591.212 | 585.938 | 590.449 | 591.212 |
| 16 | 2141.605, 2160.779, 2154.353, 2146.713, 2146.679 | 2146.713 | 2159.173 | 2160.779 |

All non-threatening samples reached native `Solve_Succeeded/Converged`: seven
iterations without targets and four with 1/16 targets. A separately replayed
threatening head-on commitment exercised the nonoptimal path: IPOPT produced a
primal-feasible non-seed iterate whose objective improved from `249.348371` to
`247.939670`; the callback stopped on that explicit quality witness after one
optimizer iteration (`613.017 ms`). Native termination remains
`User_Requested_Stop/Timeout`; operational result is `FeasibleNonOptimal` only
after the independent primal and objective-improvement gate. Terminal output,
accepted iteration, seed objective/violation, decision delta, and primal checks
remain separate replay evidence. A wall-clock stop without that improvement
stays `Timeout/TIMEOUT_FEASIBLE`. No timeout/infeasible native status is renamed
as IPOPT success. Observed p95 remains below the configured 20 s deadline.

Five samples and non-threatening contacts make this regression evidence, not a
general real-time, KKT convergence, or adversarial 16-target capability claim.
Closed-loop HO/CS/OT and multiship tests remain the behavior/safety gate.
