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
| 0 | 586.356, 531.813, 525.897, 526.114, 526.912 | 526.912 | 542.722 | 586.356 |
| 1 | 579.549, 582.775, 577.373, 578.596, 591.257 | 579.549 | 584.472 | 591.257 |
| 16 | 1276.601, 1253.206, 1255.861, 1257.952, 1257.584 | 1257.584 | 1261.682 | 1276.601 |

All zero-target solves reached native `Solve_Succeeded/Converged` in five
iterations. All 1/16-target solves executed two IPOPT iterations, preserved the
native `User_Requested_Stop/Timeout` termination, then passed an independent
quality gate selecting the lowest-objective feasible non-seed IPOPT iterate.
Their operational result is explicitly `FeasibleNonOptimal`; terminal output,
accepted iteration, seed objective/violation, decision delta, and primal checks
remain separate replay evidence. No timeout/infeasible native status is silently
renamed as IPOPT success. Observed p95 is below the configured 20 s deadline.

Five samples and non-threatening contacts make this regression evidence, not a
general real-time, KKT convergence, or adversarial 16-target capability claim.
Closed-loop HO/CS/OT and multiship tests remain the behavior/safety gate.
