# Issue #54 modular GNC performance evidence

- Schema: `gnc-performance.v1`
- Claim ceiling: `performance_characterization_and_A2_blocker_evidence_only`
- Commit: `4000349675ce1bd11e5af5c36ae749376252a466`
- Platform: `macOS-26.6.2-arm64-arm-64bit`, `25.6.0`, `arm64`
- Python: `/Users/marine/Code/.worktrees/Colav-Simulator/modular-gnc-stack/.venv/bin/python` / `3.11.15`
- uv.lock SHA-256: `5f6803e4b18ff2d5480b515779900409f8d40983d2e108b3ff71c7cc3ab24ce4`
- Dependency freeze SHA-256: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
- Harness config SHA-256: `835a627900207d8f531e01760020fe4a48831689d38c4b1b4e0dd78924c55747`
- Result SHA-256: `0d2b9bf9fdeb43fd5c9f6019651124e1d6496aec5af7fbc82903bba87de167ba`
- CPU affinity: `uncontrolled`

## Contract

The harness directly instantiates `AnalyticEnvironmentField`, `EnvironmentalLoadModel`, `Generic3DOFPlant`, and scheduler-owned `rk4_step`. It excludes GUI, legacy simulation, COLAV, and adapter overhead. Each measured simulated second is 50 base ticks × 4 RK4 stages = 200 RHS evaluations per ship per simulated second. No simulation state uses wall time.

## Matrix results

| Ships | Harmonics | Median RTF/ship | RHS p50 | RHS p95 | RK4 step p50 | RK4 step p95 | Peak RSS | RHS identity | Repeat digest |
|---:|---:|---:|---:|---:|---:|---:|---:|:---:|:---:|
| 1 | 8 | 58.928 | 84.521 us | 85.687 us | 338.084 us | 342.625 us | 35.38 MiB | True | True |
| 1 | 32 | 30.640 | 162.958 us | 164.781 us | 651.833 us | 658.733 us | 35.42 MiB | True | True |
| 1 | 128 | 10.406 | 481.656 us | 483.927 us | 1.927 ms | 1.935 ms | 35.42 MiB | True | True |
| 5 | 8 | 11.763 | 85.052 us | 86.156 us | 340.209 us | 344.617 us | 35.44 MiB | True | True |
| 5 | 32 | 6.070 | 165.062 us | 166.625 us | 660.250 us | 666.317 us | 35.44 MiB | True | True |
| 5 | 128 | 2.078 | 482.781 us | 485.812 us | 1.931 ms | 1.943 ms | 35.44 MiB | True | True |
| 20 | 8 | 2.952 | 84.666 us | 86.011 us | 338.666 us | 344.046 us | 35.58 MiB | True | True |
| 20 | 32 | 1.511 | 165.734 us | 167.470 us | 662.937 us | 669.881 us | 35.59 MiB | True | True |
| 20 | 128 | 0.519 | 483.046 us | 486.127 us | 1.932 ms | 1.945 ms | 35.62 MiB | True | True |

## Harmonic scaling ratios

Ratios are measured ratios relative to the 8-harmonic row for the same ship count; they are not a fitted complexity claim.

| Ships | From | To | RHS p95 ratio | RTF ratio |
|---:|---:|---:|---:|---:|
| 1 | 8 | 8 | 1.000 | 1.000 |
| 1 | 8 | 32 | 1.923 | 1.923 |
| 1 | 8 | 128 | 5.648 | 5.663 |
| 5 | 8 | 8 | 1.000 | 1.000 |
| 5 | 8 | 32 | 1.934 | 1.938 |
| 5 | 8 | 128 | 5.639 | 5.662 |
| 20 | 8 | 8 | 1.000 | 1.000 |
| 20 | 8 | 32 | 1.947 | 1.953 |
| 20 | 8 | 128 | 5.652 | 5.688 |

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
