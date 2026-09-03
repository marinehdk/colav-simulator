# Issue #54 modular GNC performance evidence

- Schema: `gnc-performance.v2`
- Claim ceiling: `performance_characterization_and_A2_blocker_evidence_only`
- Execution source commit H: `cc67b92f3080c75f8316caab573699054ba0ba5a`
- Execution source archive SHA-256: `039cdd9170e8908809fb4a4740b8a3afc00acf73a46542fb79537e439f177488`
- Execution source manifest SHA-256: `a39c1e78da2d11232cd14282de8e14c155b7bdd84a7fd1a385445ac178500df7`
- Execution source dirty: `False`
- Platform: `macOS-26.6.2-arm64-arm-64bit`, `25.6.0`, `arm64`
- Python: `/Users/marine/Code/.worktrees/Colav-Simulator/modular-gnc-stack/.venv/bin/python` / `3.11.15`
- uv.lock SHA-256: `5f6803e4b18ff2d5480b515779900409f8d40983d2e108b3ff71c7cc3ab24ce4`
- Dependency freeze SHA-256: `b167da0e039d6c309ba2e0e739ba3928afc6bb2c5680e2ae4d1959303cc4ee1f`
- Harness config SHA-256: `f894bc6f47a92152ee34e06dc8c1755ccb8023a5e1cbf8cfe20feca0e70431c1`
- Input SHA-256: `3c0097608c9504fd5b2e5b1761a3e6ee7eaf867e83d3fda2cd7cac86589a3887`
- `result_file_sha256`: `cb66ed257d2e81bc65bc33c929f4acbd045e1302a839403fbb3d78e66a40441b`
- `payload_sha256`: `53a82b4439f6fe4eb3572269155950592e2ed0514771c05b6f9ecd657e0ca777`
- CPU affinity: `uncontrolled`

## Contract and traceability

Direct path: `AnalyticEnvironmentField` + `EnvironmentalLoadModel` + `Generic3DOFPlant` + scheduler-owned `rk4_step`; GUI, legacy simulation, COLAV, and adapters excluded. Fixed 50 Hz × RK4 × 4 stages = 200 direct RHS evaluations per ship per simulated second. Each k1/k2/k3/k4 sample directly times stage-specific environment query, load model, and plant RHS. Parent RSS monitoring is outside worker timing loop.

Authoritative RA-03: `docs/superpowers/specs/2026-08-28-agx-l45-gnc-integration-design.md`, section `Review Amendments (2026-08-31, binding), RA-03`.

## Matrix results

Scenario RTF = common-axis simulated seconds / wall seconds. Aggregate ship-s/s = ships × scenario simulated seconds / wall seconds. Percentiles below pool direct samples across all three repeats.

| Ships | Harmonics | Scenario RTF median (min/max/CV) | Aggregate ship-s/s | k1 p95 | k2 p95 | k3 p95 | k4 p95 | Pooled RHS p95 | RK4 step p95 | Peak current RSS | Max row delta RSS |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 8 | 57.871 (57.340/58.168/0.006) | 57.871 | 86.291 us | 85.833 us | 85.291 us | 85.333 us | 85.791 us | 352.837 us | 34.98 MiB | 0.56 MiB |
| 1 | 32 | 30.161 (30.090/30.431/0.005) | 30.161 | 167.463 us | 166.586 us | 166.000 us | 166.419 us | 166.625 us | 673.710 us | 34.97 MiB | 0.52 MiB |
| 1 | 128 | 10.421 (10.340/10.511/0.007) | 10.421 | 486.254 us | 485.295 us | 485.046 us | 484.960 us | 485.458 us | 1.950 ms | 34.98 MiB | 0.48 MiB |
| 5 | 8 | 11.724 (11.690/11.730/0.002) | 58.622 | 85.000 us | 84.333 us | 83.958 us | 83.791 us | 84.500 us | 347.333 us | 36.77 MiB | 2.31 MiB |
| 5 | 32 | 6.036 (6.018/6.082/0.004) | 30.182 | 166.627 us | 165.959 us | 165.625 us | 165.458 us | 166.000 us | 672.833 us | 36.81 MiB | 2.33 MiB |
| 5 | 128 | 2.078 (2.070/2.081/0.002) | 10.391 | 488.127 us | 487.833 us | 487.836 us | 487.625 us | 487.877 us | 1.956 ms | 36.77 MiB | 2.28 MiB |
| 20 | 8 | 2.897 (2.880/2.902/0.003) | 57.941 | 86.625 us | 85.917 us | 85.792 us | 85.666 us | 86.125 us | 354.500 us | 41.31 MiB | 6.81 MiB |
| 20 | 32 | 1.515 (1.505/1.516/0.003) | 30.296 | 167.292 us | 166.583 us | 166.375 us | 166.209 us | 166.625 us | 674.875 us | 39.84 MiB | 5.41 MiB |
| 20 | 128 | 0.516 (0.510/0.518/0.006) | 10.311 | 490.125 us | 489.417 us | 489.542 us | 489.375 us | 489.625 us | 1.963 ms | 39.88 MiB | 5.41 MiB |

## Harmonic scaling

Ratios are descriptive measurements relative to the 8-harmonic row for each ship count; no complexity model is claimed.

| Ships | From | To | Direct pooled RHS p95 ratio | Scenario RTF ratio |
|---:|---:|---:|---:|---:|
| 1 | 8 | 8 | 1.000 | 1.000 |
| 1 | 8 | 32 | 1.942 | 1.919 |
| 1 | 8 | 128 | 5.659 | 5.553 |
| 5 | 8 | 8 | 1.000 | 1.000 |
| 5 | 8 | 32 | 1.964 | 1.942 |
| 5 | 8 | 128 | 5.774 | 5.641 |
| 20 | 8 | 8 | 1.000 | 1.000 |
| 20 | 8 | 32 | 1.935 | 1.912 |
| 20 | 8 | 128 | 5.685 | 5.619 |

## Threshold proposal — PROPOSED_NOT_APPROVED

No GO/NO-GO decision is made here. These candidate thresholds require issue-owner approval.

| Candidate | Limit | Observed representative 20 ships/32 harmonics | Result |
|---|---:|---:|:---:|
| 20_ship_8_to_128_rhs_p95_ratio | 5.25 | 5.68505 | False |
| 20_ship_8_to_32_rhs_p95_ratio | 2.0 | 1.93469 | True |
| representative_delta_current_rss_mib | 64.0 | 5.40625 | True |
| representative_direct_pooled_rhs_p95_ms | 0.25 | 0.166625 | True |
| representative_peak_current_rss_mib | 128.0 | 39.8438 | True |
| representative_scenario_rtf_floor | 1.0 | 1.51482 | True |
| stress_20_ship_128_scenario_rtf_floor | 0.25 | 0.51555 | True |

- Representative row: 20 ships / 32 harmonics.
- Scenario RTF floor: 1.00.
- Direct pooled RHS p95 ceiling: 0.25 ms for 20-ship serial aggregate; separate per-ship reference: 5 ms.
- Memory ceilings: 128 MiB peak current RSS and 64 MiB per-row current-RSS delta.
- Harmonic guards: 8→32 ≤ 2.00 and 8→128 ≤ 5.25 direct pooled RHS p95 ratio.
- Stress row: 20 ships / 128 harmonics, candidate Scenario RTF floor 0.25; not representative GO row.
- Decision options recorded only: Python GO; remediation-vectorization; same-contract native adapter.

## Boundaries

- Performance characterization and A2 blocker evidence only.
- No plant parity, vessel validation, COLAV, SIL, HIL, or sea-trial claim.
- A2 remains blocked pending the performance decision; #55 remains blocked.
- Rollback point: `17c075b0cb8fd3d13a1f5cc9294e319fe1bd2c98`.
