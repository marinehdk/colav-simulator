# Issue #54 modular GNC performance evidence

- Schema: `gnc-performance.v1`
- Claim ceiling: `performance_characterization_and_A2_blocker_evidence_only`
- Commit: `132ca19a2a0eb641c707d4c4fa6a7506e0d923a4`
- Platform: `Linux-5.15.148-rt-tegra-aarch64-with-glibc2.35`, `5.15.148-rt-tegra`, `aarch64`
- Python: `/usr/bin/python3` / `3.10.12`
- uv.lock SHA-256: `5f6803e4b18ff2d5480b515779900409f8d40983d2e108b3ff71c7cc3ab24ce4`
- Dependency freeze SHA-256: `abfc6dbeb9145fc2530f500e16e76ef0510cf57051453507bc3d40b23e916dc0`
- Harness config SHA-256: `835a627900207d8f531e01760020fe4a48831689d38c4b1b4e0dd78924c55747`
- Result SHA-256: `77b61ecb5403c525d2b29f73f106aa3052685ee72c1d1a8bc55bcd8a31c376be`
- CPU affinity: `uncontrolled`

## Contract

The harness directly instantiates `AnalyticEnvironmentField`, `EnvironmentalLoadModel`, `Generic3DOFPlant`, and scheduler-owned `rk4_step`. It excludes GUI, legacy simulation, COLAV, and adapter overhead. Each measured simulated second is 50 base ticks × 4 RK4 stages = 200 RHS evaluations per ship per simulated second. No simulation state uses wall time.

## Matrix results

| Ships | Harmonics | Median RTF/ship | RHS p50 | RHS p95 | RK4 step p50 | RK4 step p95 | Peak RSS | RHS identity | Repeat digest |
|---:|---:|---:|---:|---:|---:|---:|---:|:---:|:---:|
| 1 | 8 | 10.875 | 458.785 us | 465.353 us | 1.835 ms | 1.861 ms | 36.38 MiB | True | True |
| 1 | 32 | 6.006 | 832.319 us | 837.175 us | 3.329 ms | 3.348 ms | 36.38 MiB | True | True |
| 1 | 128 | 2.165 | 2.308 ms | 2.322 ms | 9.230 ms | 9.285 ms | 36.38 MiB | True | True |
| 5 | 8 | 2.246 | 443.058 us | 455.577 us | 1.772 ms | 1.822 ms | 36.38 MiB | True | True |
| 5 | 32 | 1.227 | 812.984 us | 825.272 us | 3.252 ms | 3.301 ms | 36.38 MiB | True | True |
| 5 | 128 | 0.439 | 2.271 ms | 2.307 ms | 9.083 ms | 9.222 ms | 36.38 MiB | True | True |
| 20 | 8 | 0.558 | 444.618 us | 461.953 us | 1.778 ms | 1.848 ms | 36.38 MiB | True | True |
| 20 | 32 | 0.306 | 814.713 us | 826.201 us | 3.259 ms | 3.305 ms | 36.38 MiB | True | True |
| 20 | 128 | 0.110 | 2.264 ms | 2.284 ms | 9.056 ms | 9.137 ms | 36.38 MiB | True | True |

## Harmonic scaling ratios

Ratios are measured ratios relative to the 8-harmonic row for the same ship count; they are not a fitted complexity claim.

| Ships | From | To | RHS p95 ratio | RTF ratio |
|---:|---:|---:|---:|---:|
| 1 | 8 | 8 | 1.000 | 1.000 |
| 1 | 8 | 32 | 1.799 | 1.811 |
| 1 | 8 | 128 | 4.989 | 5.024 |
| 5 | 8 | 8 | 1.000 | 1.000 |
| 5 | 8 | 32 | 1.811 | 1.830 |
| 5 | 8 | 128 | 5.063 | 5.113 |
| 20 | 8 | 8 | 1.000 | 1.000 |
| 20 | 8 | 32 | 1.788 | 1.824 |
| 20 | 8 | 128 | 4.945 | 5.066 |

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
