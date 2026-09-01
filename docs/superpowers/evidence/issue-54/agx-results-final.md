# Issue #54 modular GNC performance evidence

- Schema: `gnc-performance.v2`
- Claim ceiling: `performance_characterization_and_A2_blocker_evidence_only`
- Execution source commit H: `6372f961ff39c9048d27baf61cca926d11566a7a`
- Execution source archive SHA-256: `ea9f8ea57b21fbfb29be923fec3bbd6b53cd92e11d35d1ff6ad3b2abc4d62942`
- Execution source manifest SHA-256: `35acb8d2664938fbc4883fda24345b6f7798ad50816d0c1d6a178b01ba1ac0b8`
- Execution source dirty: `False`
- Platform: `Linux-5.15.148-rt-tegra-aarch64-with-glibc2.35`, `5.15.148-rt-tegra`, `aarch64`
- Python: `/usr/bin/python3` / `3.10.12`
- uv.lock SHA-256: `5f6803e4b18ff2d5480b515779900409f8d40983d2e108b3ff71c7cc3ab24ce4`
- Dependency freeze SHA-256: `abfc6dbeb9145fc2530f500e16e76ef0510cf57051453507bc3d40b23e916dc0`
- Harness config SHA-256: `f894bc6f47a92152ee34e06dc8c1755ccb8023a5e1cbf8cfe20feca0e70431c1`
- Input SHA-256: `3c0097608c9504fd5b2e5b1761a3e6ee7eaf867e83d3fda2cd7cac86589a3887`
- `result_file_sha256`: `93f2e2c546773b9064b79e861c1eabc6be4ed7df9570238eca230c7c3223565a`
- `payload_sha256`: `2f7a12a30204161e9d2947fc992bb62a032a3360b597b9c20f680167433d7c9b`
- CPU affinity: `uncontrolled`

## Contract and traceability

Direct path: `AnalyticEnvironmentField` + `EnvironmentalLoadModel` + `Generic3DOFPlant` + scheduler-owned `rk4_step`; GUI, legacy simulation, COLAV, and adapters excluded. Fixed 50 Hz × RK4 × 4 stages = 200 direct RHS evaluations per ship per simulated second. Each k1/k2/k3/k4 sample directly times stage-specific environment query, load model, and plant RHS. Parent RSS monitoring is outside worker timing loop.

Authoritative RA-03: `docs/superpowers/specs/2026-08-28-agx-l45-gnc-integration-design.md`, section `Review Amendments (2026-08-31, binding), RA-03`.

## Matrix results

Scenario RTF = common-axis simulated seconds / wall seconds. Aggregate ship-s/s = ships × scenario simulated seconds / wall seconds. Percentiles below pool direct samples across all three repeats.

| Ships | Harmonics | Scenario RTF median (min/max/CV) | Aggregate ship-s/s | k1 p95 | k2 p95 | k3 p95 | k4 p95 | Pooled RHS p95 | RK4 step p95 | Peak current RSS | Max row delta RSS |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 8 | 10.991 (10.860/11.065/0.008) | 10.991 | 468.879 us | 471.134 us | 470.321 us | 471.796 us | 470.446 us | 1.892 ms | 34.14 MiB | 34.14 MiB |
| 1 | 32 | 5.984 (5.805/6.030/0.016) | 5.984 | 877.568 us | 878.980 us | 876.428 us | 879.293 us | 877.676 us | 3.660 ms | 34.14 MiB | 34.14 MiB |
| 1 | 128 | 2.192 (2.173/2.197/0.005) | 2.192 | 2.326 ms | 2.331 ms | 2.327 ms | 2.322 ms | 2.327 ms | 9.347 ms | 34.14 MiB | 34.14 MiB |
| 5 | 8 | 2.205 (2.199/2.218/0.004) | 11.025 | 463.276 us | 463.374 us | 462.351 us | 462.125 us | 462.767 us | 1.856 ms | 35.68 MiB | 35.68 MiB |
| 5 | 32 | 1.225 (1.219/1.231/0.004) | 6.123 | 837.792 us | 835.942 us | 836.192 us | 835.584 us | 836.318 us | 3.313 ms | 35.69 MiB | 35.69 MiB |
| 5 | 128 | 0.441 (0.441/0.443/0.002) | 2.206 | 2.292 ms | 2.295 ms | 2.291 ms | 2.293 ms | 2.293 ms | 9.157 ms | 34.91 MiB | 34.91 MiB |
| 20 | 8 | 0.555 (0.548/0.556/0.007) | 11.107 | 467.120 us | 467.664 us | 466.127 us | 466.926 us | 467.022 us | 1.869 ms | 40.73 MiB | 40.73 MiB |
| 20 | 32 | 0.306 (0.303/0.306/0.004) | 6.114 | 839.553 us | 839.910 us | 837.954 us | 839.045 us | 839.074 us | 3.328 ms | 41.99 MiB | 41.98 MiB |
| 20 | 128 | 0.110 (0.109/0.110/0.007) | 2.194 | 2.314 ms | 2.316 ms | 2.314 ms | 2.316 ms | 2.315 ms | 9.270 ms | 40.35 MiB | 40.35 MiB |

## Harmonic scaling

Ratios are descriptive measurements relative to the 8-harmonic row for each ship count; no complexity model is claimed.

| Ships | From | To | Direct pooled RHS p95 ratio | Scenario RTF ratio |
|---:|---:|---:|---:|---:|
| 1 | 8 | 8 | 1.000 | 1.000 |
| 1 | 8 | 32 | 1.866 | 1.837 |
| 1 | 8 | 128 | 4.946 | 5.015 |
| 5 | 8 | 8 | 1.000 | 1.000 |
| 5 | 8 | 32 | 1.807 | 1.801 |
| 5 | 8 | 128 | 4.954 | 4.997 |
| 20 | 8 | 8 | 1.000 | 1.000 |
| 20 | 8 | 32 | 1.797 | 1.817 |
| 20 | 8 | 128 | 4.957 | 5.062 |

## Threshold proposal — PROPOSED_NOT_APPROVED

No GO/NO-GO decision is made here. These candidate thresholds require issue-owner approval.

| Candidate | Limit | Observed representative 20 ships/32 harmonics | Result |
|---|---:|---:|:---:|
| 20_ship_8_to_128_rhs_p95_ratio | 5.25 | 4.95715 | True |
| 20_ship_8_to_32_rhs_p95_ratio | 2.0 | 1.79665 | True |
| representative_delta_current_rss_mib | 64.0 | 41.9844 | True |
| representative_direct_pooled_rhs_p95_ms | 0.25 | 0.839074 | False |
| representative_peak_current_rss_mib | 128.0 | 41.9883 | True |
| representative_scenario_rtf_floor | 1.0 | 0.305697 | False |
| stress_20_ship_128_scenario_rtf_floor | 0.25 | 0.109704 | False |

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
