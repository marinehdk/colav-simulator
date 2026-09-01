# Issue #54 modular GNC performance evidence

- Schema: `gnc-performance.v1`
- Claim ceiling: `performance_characterization_and_A2_blocker_evidence_only`
- Commit: `None`
- Platform: `Linux-5.15.148-rt-tegra-aarch64-with-glibc2.35`, `5.15.148-rt-tegra`, `aarch64`
- Python: `/usr/bin/python3` / `3.10.12`
- uv.lock SHA-256: `5f6803e4b18ff2d5480b515779900409f8d40983d2e108b3ff71c7cc3ab24ce4`
- Dependency freeze SHA-256: `abfc6dbeb9145fc2530f500e16e76ef0510cf57051453507bc3d40b23e916dc0`
- Harness config SHA-256: `835a627900207d8f531e01760020fe4a48831689d38c4b1b4e0dd78924c55747`
- Result SHA-256: `ab2bf9a2563bbffa28515456c7246c9b50ca0a3402cd8857ea888ac42d3f0a29`
- CPU affinity: `uncontrolled`

## Contract

The harness directly instantiates `AnalyticEnvironmentField`, `EnvironmentalLoadModel`, `Generic3DOFPlant`, and scheduler-owned `rk4_step`. It excludes GUI, legacy simulation, COLAV, and adapter overhead. Each measured simulated second is 50 base ticks × 4 RK4 stages = 200 RHS evaluations per ship per simulated second. No simulation state uses wall time.

## Matrix results

| Ships | Harmonics | Median RTF/ship | RHS p50 | RHS p95 | RK4 step p50 | RK4 step p95 | Peak RSS | RHS identity | Repeat digest |
|---:|---:|---:|---:|---:|---:|---:|---:|:---:|:---:|
| 1 | 8 | 11.003 | 451.680 us | 464.000 us | 1.807 ms | 1.854 ms | 32.69 MiB | True | True |
| 1 | 32 | 6.027 | 828.905 us | 838.417 us | 3.316 ms | 3.353 ms | 32.69 MiB | True | True |
| 1 | 128 | 2.174 | 2.298 ms | 2.313 ms | 9.192 ms | 9.251 ms | 32.69 MiB | True | True |
| 5 | 8 | 2.250 | 442.080 us | 452.208 us | 1.768 ms | 1.809 ms | 32.69 MiB | True | True |
| 5 | 32 | 1.226 | 809.537 us | 817.465 us | 3.238 ms | 3.270 ms | 32.69 MiB | True | True |
| 5 | 128 | 0.444 | 2.245 ms | 2.263 ms | 8.981 ms | 9.052 ms | 33.78 MiB | True | True |
| 20 | 8 | 0.558 | 443.920 us | 462.556 us | 1.776 ms | 1.850 ms | 33.78 MiB | True | True |
| 20 | 32 | 0.306 | 812.949 us | 827.188 us | 3.252 ms | 3.309 ms | 33.78 MiB | True | True |
| 20 | 128 | 0.110 | 2.261 ms | 2.287 ms | 9.045 ms | 9.149 ms | 33.78 MiB | True | True |

## Harmonic scaling ratios

Ratios are measured ratios relative to the 8-harmonic row for the same ship count; they are not a fitted complexity claim.

| Ships | From | To | RHS p95 ratio | RTF ratio |
|---:|---:|---:|---:|---:|
| 1 | 8 | 8 | 1.000 | 1.000 |
| 1 | 8 | 32 | 1.807 | 1.826 |
| 1 | 8 | 128 | 4.984 | 5.061 |
| 5 | 8 | 8 | 1.000 | 1.000 |
| 5 | 8 | 32 | 1.808 | 1.835 |
| 5 | 8 | 128 | 5.005 | 5.072 |
| 20 | 8 | 8 | 1.000 | 1.000 |
| 20 | 8 | 32 | 1.788 | 1.822 |
| 20 | 8 | 128 | 4.945 | 5.056 |

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
