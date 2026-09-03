# Issue #54 modular GNC performance evidence

- Schema: `gnc-performance.v1`
- Claim ceiling: `performance_characterization_and_A2_blocker_evidence_only`
- Commit: `None`
- Platform: `Linux-5.15.148-rt-tegra-aarch64-with-glibc2.35`, `5.15.148-rt-tegra`, `aarch64`
- Python: `/usr/bin/python3` / `3.10.12`
- uv.lock SHA-256: `5f6803e4b18ff2d5480b515779900409f8d40983d2e108b3ff71c7cc3ab24ce4`
- Dependency freeze SHA-256: `abfc6dbeb9145fc2530f500e16e76ef0510cf57051453507bc3d40b23e916dc0`
- Harness config SHA-256: `835a627900207d8f531e01760020fe4a48831689d38c4b1b4e0dd78924c55747`
- Result SHA-256: `ab249dd20fe953640bf127621ba94528cd55778d5b080751bd680b529d817fd3`
- CPU affinity: `uncontrolled`

## Contract

The harness directly instantiates `AnalyticEnvironmentField`, `EnvironmentalLoadModel`, `Generic3DOFPlant`, and scheduler-owned `rk4_step`. It excludes GUI, legacy simulation, COLAV, and adapter overhead. Each measured simulated second is 50 base ticks × 4 RK4 stages = 200 RHS evaluations per ship per simulated second. No simulation state uses wall time.

## Matrix results

| Ships | Harmonics | Median RTF/ship | RHS p50 | RHS p95 | RK4 step p50 | RK4 step p95 | Peak RSS | RHS identity | Repeat digest |
|---:|---:|---:|---:|---:|---:|---:|---:|:---:|:---:|
| 1 | 8 | 10.874 | 456.048 us | 485.158 us | 1.824 ms | 1.931 ms | 32.89 MiB | True | True |
| 1 | 32 | 6.008 | 829.398 us | 843.277 us | 3.318 ms | 3.373 ms | 32.89 MiB | True | True |
| 1 | 128 | 2.159 | 2.320 ms | 2.329 ms | 9.278 ms | 9.316 ms | 32.89 MiB | True | True |
| 5 | 8 | 2.263 | 439.665 us | 449.792 us | 1.759 ms | 1.799 ms | 32.89 MiB | True | True |
| 5 | 32 | 1.223 | 814.431 us | 835.037 us | 3.258 ms | 3.340 ms | 32.89 MiB | True | True |
| 5 | 128 | 0.438 | 2.283 ms | 2.305 ms | 9.132 ms | 9.221 ms | 32.89 MiB | True | True |
| 20 | 8 | 0.564 | 440.697 us | 454.144 us | 1.763 ms | 1.817 ms | 33.79 MiB | True | True |
| 20 | 32 | 0.306 | 813.108 us | 836.294 us | 3.252 ms | 3.345 ms | 33.79 MiB | True | True |
| 20 | 128 | 0.110 | 2.271 ms | 2.307 ms | 9.085 ms | 9.228 ms | 33.79 MiB | True | True |

## Harmonic scaling ratios

Ratios are measured ratios relative to the 8-harmonic row for the same ship count; they are not a fitted complexity claim.

| Ships | From | To | RHS p95 ratio | RTF ratio |
|---:|---:|---:|---:|---:|
| 1 | 8 | 8 | 1.000 | 1.000 |
| 1 | 8 | 32 | 1.738 | 1.810 |
| 1 | 8 | 128 | 4.801 | 5.035 |
| 5 | 8 | 8 | 1.000 | 1.000 |
| 5 | 8 | 32 | 1.856 | 1.851 |
| 5 | 8 | 128 | 5.125 | 5.171 |
| 20 | 8 | 8 | 1.000 | 1.000 |
| 20 | 8 | 32 | 1.841 | 1.843 |
| 20 | 8 | 128 | 5.080 | 5.135 |

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
