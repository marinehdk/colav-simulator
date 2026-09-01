# Issue #54 modular GNC performance evidence

- Schema: `gnc-performance.v2`
- Claim ceiling: `performance_characterization_and_A2_blocker_evidence_only`
- Execution source commit H: `cc67b92f3080c75f8316caab573699054ba0ba5a`
- Execution source archive SHA-256: `039cdd9170e8908809fb4a4740b8a3afc00acf73a46542fb79537e439f177488`
- Execution source manifest SHA-256: `a39c1e78da2d11232cd14282de8e14c155b7bdd84a7fd1a385445ac178500df7`
- Execution source dirty: `False`
- Platform: `Linux-5.15.148-rt-tegra-aarch64-with-glibc2.35`, `5.15.148-rt-tegra`, `aarch64`
- Python: `/usr/bin/python3` / `3.10.12`
- uv.lock SHA-256: `5f6803e4b18ff2d5480b515779900409f8d40983d2e108b3ff71c7cc3ab24ce4`
- Dependency freeze SHA-256: `abfc6dbeb9145fc2530f500e16e76ef0510cf57051453507bc3d40b23e916dc0`
- Harness config SHA-256: `f894bc6f47a92152ee34e06dc8c1755ccb8023a5e1cbf8cfe20feca0e70431c1`
- Input SHA-256: `3c0097608c9504fd5b2e5b1761a3e6ee7eaf867e83d3fda2cd7cac86589a3887`
- `result_file_sha256`: `3e222ed0dbf8caef868347dce059bb496b14a8d32ff8637f550bed4a19dbe299`
- `payload_sha256`: `9dff2abd10b2d5bf81653b91dcc2bb1f967f620e31db542f6e6962fd7b42d453`
- CPU affinity: `uncontrolled`

## Contract and traceability

Direct path: `AnalyticEnvironmentField` + `EnvironmentalLoadModel` + `Generic3DOFPlant` + scheduler-owned `rk4_step`; GUI, legacy simulation, COLAV, and adapters excluded. Fixed 50 Hz × RK4 × 4 stages = 200 direct RHS evaluations per ship per simulated second. Each k1/k2/k3/k4 sample directly times stage-specific environment query, load model, and plant RHS. Parent RSS monitoring is outside worker timing loop.

Authoritative RA-03: `docs/superpowers/specs/2026-08-28-agx-l45-gnc-integration-design.md`, section `Review Amendments (2026-08-31, binding), RA-03`.

## Matrix results

Scenario RTF = common-axis simulated seconds / wall seconds. Aggregate ship-s/s = ships × scenario simulated seconds / wall seconds. Percentiles below pool direct samples across all three repeats.

| Ships | Harmonics | Scenario RTF median (min/max/CV) | Aggregate ship-s/s | k1 p95 | k2 p95 | k3 p95 | k4 p95 | Pooled RHS p95 | RK4 step p95 | Peak current RSS | Max row delta RSS |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 8 | 11.070 (11.015/11.090/0.003) | 11.070 | 466.785 us | 465.738 us | 462.537 us | 465.457 us | 465.090 us | 1.884 ms | 33.79 MiB | 0.32 MiB |
| 1 | 32 | 6.060 (6.043/6.146/0.007) | 6.060 | 844.836 us | 848.409 us | 847.331 us | 848.518 us | 846.977 us | 3.367 ms | 33.80 MiB | 0.32 MiB |
| 1 | 128 | 2.191 (2.188/2.199/0.002) | 2.191 | 2.320 ms | 2.320 ms | 2.321 ms | 2.321 ms | 2.320 ms | 9.291 ms | 33.80 MiB | 0.32 MiB |
| 5 | 8 | 2.220 (2.211/2.228/0.003) | 11.101 | 462.783 us | 463.903 us | 462.017 us | 462.401 us | 462.847 us | 1.846 ms | 35.34 MiB | 1.86 MiB |
| 5 | 32 | 1.232 (1.226/1.238/0.004) | 6.160 | 832.672 us | 832.637 us | 831.584 us | 832.803 us | 832.416 us | 3.291 ms | 34.57 MiB | 1.09 MiB |
| 5 | 128 | 0.446 (0.444/0.449/0.004) | 2.229 | 2.264 ms | 2.261 ms | 2.263 ms | 2.261 ms | 2.262 ms | 9.051 ms | 34.54 MiB | 1.09 MiB |
| 20 | 8 | 0.554 (0.551/0.560/0.007) | 11.072 | 463.070 us | 464.481 us | 462.752 us | 464.190 us | 463.710 us | 1.855 ms | 39.72 MiB | 6.25 MiB |
| 20 | 32 | 0.305 (0.304/0.308/0.004) | 6.108 | 836.384 us | 837.052 us | 835.389 us | 835.837 us | 836.124 us | 3.316 ms | 40.20 MiB | 6.73 MiB |
| 20 | 128 | 0.112 (0.111/0.112/0.004) | 2.237 | 2.267 ms | 2.267 ms | 2.265 ms | 2.266 ms | 2.266 ms | 9.098 ms | 40.00 MiB | 6.53 MiB |

## Harmonic scaling

Ratios are descriptive measurements relative to the 8-harmonic row for each ship count; no complexity model is claimed.

| Ships | From | To | Direct pooled RHS p95 ratio | Scenario RTF ratio |
|---:|---:|---:|---:|---:|
| 1 | 8 | 8 | 1.000 | 1.000 |
| 1 | 8 | 32 | 1.821 | 1.827 |
| 1 | 8 | 128 | 4.989 | 5.052 |
| 5 | 8 | 8 | 1.000 | 1.000 |
| 5 | 8 | 32 | 1.798 | 1.802 |
| 5 | 8 | 128 | 4.888 | 4.979 |
| 20 | 8 | 8 | 1.000 | 1.000 |
| 20 | 8 | 32 | 1.803 | 1.813 |
| 20 | 8 | 128 | 4.888 | 4.950 |

## Threshold proposal — PROPOSED_NOT_APPROVED

No GO/NO-GO decision is made here. These candidate thresholds require issue-owner approval.

| Candidate | Limit | Observed representative 20 ships/32 harmonics | Result |
|---|---:|---:|:---:|
| 20_ship_8_to_128_rhs_p95_ratio | 5.25 | 4.88765 | True |
| 20_ship_8_to_32_rhs_p95_ratio | 2.0 | 1.80312 | True |
| representative_delta_current_rss_mib | 64.0 | 6.72656 | True |
| representative_direct_pooled_rhs_p95_ms | 0.25 | 0.836124 | False |
| representative_peak_current_rss_mib | 128.0 | 40.1992 | True |
| representative_scenario_rtf_floor | 1.0 | 0.305414 | False |
| stress_20_ship_128_scenario_rtf_floor | 0.25 | 0.111841 | False |

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
