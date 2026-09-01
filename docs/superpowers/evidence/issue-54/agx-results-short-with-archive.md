# Issue #54 modular GNC performance evidence

- Schema: `gnc-performance.v1`
- Claim ceiling: `performance_characterization_and_A2_blocker_evidence_only`
- Commit: `None`
- Platform: `Linux-5.15.148-rt-tegra-aarch64-with-glibc2.35`, `5.15.148-rt-tegra`, `aarch64`
- Python: `/usr/bin/python3` / `3.10.12`
- uv.lock SHA-256: `5f6803e4b18ff2d5480b515779900409f8d40983d2e108b3ff71c7cc3ab24ce4`
- Dependency freeze SHA-256: `abfc6dbeb9145fc2530f500e16e76ef0510cf57051453507bc3d40b23e916dc0`
- Harness config SHA-256: `835a627900207d8f531e01760020fe4a48831689d38c4b1b4e0dd78924c55747`
- Result SHA-256: `719adab07c5a69ece46fceb1021e50de9ac9483bd4f6e1beb56f87e428768892`
- CPU affinity: `uncontrolled`

## Contract

The harness directly instantiates `AnalyticEnvironmentField`, `EnvironmentalLoadModel`, `Generic3DOFPlant`, and scheduler-owned `rk4_step`. It excludes GUI, legacy simulation, COLAV, and adapter overhead. Each measured simulated second is 50 base ticks × 4 RK4 stages = 200 RHS evaluations per ship per simulated second. No simulation state uses wall time.

## Matrix results

| Ships | Harmonics | Median RTF/ship | RHS p50 | RHS p95 | RK4 step p50 | RK4 step p95 | Peak RSS | RHS identity | Repeat digest |
|---:|---:|---:|---:|---:|---:|---:|---:|:---:|:---:|
| 1 | 8 | 11.109 | 446.265 us | 459.248 us | 1.785 ms | 1.836 ms | 32.79 MiB | True | True |
| 1 | 32 | 6.086 | 822.353 us | 827.409 us | 3.289 ms | 3.309 ms | 32.79 MiB | True | True |
| 1 | 128 | 2.194 | 2.277 ms | 2.287 ms | 9.108 ms | 9.149 ms | 32.79 MiB | True | True |
| 5 | 8 | 2.266 | 439.274 us | 451.337 us | 1.757 ms | 1.805 ms | 32.79 MiB | True | True |
| 5 | 32 | 1.233 | 808.714 us | 821.681 us | 3.235 ms | 3.286 ms | 32.79 MiB | True | True |
| 5 | 128 | 0.447 | 2.235 ms | 2.246 ms | 8.941 ms | 8.985 ms | 32.79 MiB | True | True |
| 20 | 8 | 0.564 | 439.978 us | 456.900 us | 1.760 ms | 1.828 ms | 33.78 MiB | True | True |
| 20 | 32 | 0.309 | 807.284 us | 820.981 us | 3.229 ms | 3.284 ms | 33.78 MiB | True | True |
| 20 | 128 | 0.111 | 2.243 ms | 2.267 ms | 8.971 ms | 9.069 ms | 33.78 MiB | True | True |

## Harmonic scaling ratios

Ratios are measured ratios relative to the 8-harmonic row for the same ship count; they are not a fitted complexity claim.

| Ships | From | To | RHS p95 ratio | RTF ratio |
|---:|---:|---:|---:|---:|
| 1 | 8 | 8 | 1.000 | 1.000 |
| 1 | 8 | 32 | 1.802 | 1.825 |
| 1 | 8 | 128 | 4.981 | 5.063 |
| 5 | 8 | 8 | 1.000 | 1.000 |
| 5 | 8 | 32 | 1.821 | 1.837 |
| 5 | 8 | 128 | 4.977 | 5.067 |
| 20 | 8 | 8 | 1.000 | 1.000 |
| 20 | 8 | 32 | 1.797 | 1.825 |
| 20 | 8 | 128 | 4.962 | 5.066 |

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
