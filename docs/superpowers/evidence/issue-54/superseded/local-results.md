# Issue #54 modular GNC performance evidence

- Schema: `gnc-performance.v1`
- Claim ceiling: `performance_characterization_and_A2_blocker_evidence_only`
- Commit: `4000349675ce1bd11e5af5c36ae749376252a466`
- Platform: `macOS-26.6.2-arm64-arm-64bit`, `25.6.0`, `arm64`
- Python: `/Users/marine/Code/.worktrees/Colav-Simulator/modular-gnc-stack/.venv/bin/python` / `3.11.15`
- uv.lock SHA-256: `5f6803e4b18ff2d5480b515779900409f8d40983d2e108b3ff71c7cc3ab24ce4`
- Dependency freeze SHA-256: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
- Harness config SHA-256: `f894bc6f47a92152ee34e06dc8c1755ccb8023a5e1cbf8cfe20feca0e70431c1`
- Result SHA-256: `f466576d95a2ab28ad3a59cc442e0744bdfa2ef4c59d47779205106999f2a986`
- CPU affinity: `uncontrolled`

## Contract

The harness directly instantiates `AnalyticEnvironmentField`, `EnvironmentalLoadModel`, `Generic3DOFPlant`, and scheduler-owned `rk4_step`. It excludes GUI, legacy simulation, COLAV, and adapter overhead. Each measured simulated second is 50 base ticks × 4 RK4 stages = 200 RHS evaluations per ship per simulated second. No simulation state uses wall time.

## Matrix results

| Ships | Harmonics | Median RTF/ship | RHS p50 | RHS p95 | RK4 step p50 | RK4 step p95 | Peak RSS | RHS identity | Repeat digest |
|---:|---:|---:|---:|---:|---:|---:|---:|:---:|:---:|
| 1 | 8 | 58.981 | 84.661 us | 86.151 us | 338.646 us | 344.606 us | 34.44 MiB | True | True |
| 1 | 32 | 30.197 | 165.822 us | 167.511 us | 663.292 us | 670.046 us | 34.45 MiB | True | True |
| 1 | 128 | 10.338 | 485.365 us | 488.284 us | 1.941 ms | 1.953 ms | 34.48 MiB | True | True |
| 5 | 8 | 11.781 | 84.812 us | 86.385 us | 339.250 us | 345.543 us | 35.47 MiB | True | True |
| 5 | 32 | 6.045 | 165.343 us | 167.895 us | 661.375 us | 671.583 us | 35.48 MiB | True | True |
| 5 | 128 | 2.065 | 482.807 us | 488.250 us | 1.931 ms | 1.953 ms | 35.52 MiB | True | True |
| 20 | 8 | 2.901 | 85.427 us | 88.156 us | 341.708 us | 352.625 us | 38.88 MiB | True | True |
| 20 | 32 | 1.493 | 166.302 us | 171.145 us | 665.208 us | 684.583 us | 38.88 MiB | True | True |
| 20 | 128 | 0.514 | 484.531 us | 490.292 us | 1.938 ms | 1.961 ms | 38.89 MiB | True | True |

## Harmonic scaling ratios

Ratios are measured ratios relative to the 8-harmonic row for the same ship count; they are not a fitted complexity claim.

| Ships | From | To | RHS p95 ratio | RTF ratio |
|---:|---:|---:|---:|---:|
| 1 | 8 | 8 | 1.000 | 1.000 |
| 1 | 8 | 32 | 1.944 | 1.953 |
| 1 | 8 | 128 | 5.668 | 5.705 |
| 5 | 8 | 8 | 1.000 | 1.000 |
| 5 | 8 | 32 | 1.944 | 1.949 |
| 5 | 8 | 128 | 5.652 | 5.704 |
| 20 | 8 | 8 | 1.000 | 1.000 |
| 20 | 8 | 32 | 1.941 | 1.943 |
| 20 | 8 | 128 | 5.562 | 5.640 |

## Threshold proposal (PROPOSED_NOT_APPROVED)

No numeric threshold is approved by this artifact. Issue #54 requires approval in the issue before subsequent slices; absence remains NO-GO for subsequent slices.

Options recorded without decision:

1. Python GO
1. approved remediation/vectorization
1. optional same-contract native adapter

- Required 20-ship representative RTF floor: `None`
- RHS reference budget: `5.0 ms` per serial RHS budget
- Memory ceiling: `None`
- Harmonic scaling guard: `None`

## Boundaries and remaining blockers

- This is performance characterization and A2 blocker evidence only.
- It is not plant parity, vessel validation, COLAV, SIL, HIL, or sea-trial evidence.
- A2 parity remains blocked pending the performance decision; issue #55 remains blocked.
- CPU affinity/governor was uncontrolled unless separately recorded by the execution environment.
- Per-RHS latency is a stage-batch wall-time attribution divided by four; RK4 step timing is directly measured.
