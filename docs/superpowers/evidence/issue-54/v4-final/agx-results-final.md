# Issue #54 modular GNC performance evidence

- Schema: `gnc-performance.v2`
- Claim ceiling: `performance_characterization_and_A2_blocker_evidence_only`
- Execution source commit H: `638e6908f057577a9cbe7907170c58fd19767d9a`
- Execution source archive SHA-256: `5323b72340677bf21d80a6222caab80cdcd14401225de4ce6081836cdbca1359`
- Execution source manifest SHA-256: `e14a2c21d0a20fd7e1bd64b2c15e1f5bbc62d01d4f913d7fc117d56e2f0bd1da`
- Execution source dirty: `False`
- Platform: `Linux-5.15.148-rt-tegra-aarch64-with-glibc2.35`, `5.15.148-rt-tegra`, `aarch64`
- Python: `/usr/bin/python3` / `3.10.12`
- uv.lock SHA-256: `5f6803e4b18ff2d5480b515779900409f8d40983d2e108b3ff71c7cc3ab24ce4`
- Dependency freeze SHA-256: `abfc6dbeb9145fc2530f500e16e76ef0510cf57051453507bc3d40b23e916dc0`
- Harness config SHA-256: `f894bc6f47a92152ee34e06dc8c1755ccb8023a5e1cbf8cfe20feca0e70431c1`
- Input SHA-256: `3c0097608c9504fd5b2e5b1761a3e6ee7eaf867e83d3fda2cd7cac86589a3887`
- `result_file_sha256`: `ad0043116f8760eb70410f6bdf2ed3455af4e001c7c919344eeac951c167ce4a`
- `payload_sha256`: `e1671f1c6f1251a03648447c4d550c95da2ef62c27ae7807601b0a1c6dddc0b1`
- CPU affinity: `uncontrolled`

## Contract and traceability

Direct path: `AnalyticEnvironmentField` + `EnvironmentalLoadModel` + `Generic3DOFPlant` + scheduler-owned `rk4_step`; GUI, legacy simulation, COLAV, and adapters excluded. Fixed 50 Hz × RK4 × 4 stages = 200 direct RHS evaluations per ship per simulated second. Each k1/k2/k3/k4 sample directly times stage-specific environment query, load model, and plant RHS. Parent RSS monitoring is outside worker timing loop.

Authoritative RA-03: `docs/superpowers/specs/2026-08-28-agx-l45-gnc-integration-design.md`, section `Review Amendments (2026-08-31, binding), RA-03`.

## Matrix results

Scenario RTF = common-axis simulated seconds / wall seconds. Aggregate ship-s/s = ships × scenario simulated seconds / wall seconds. Percentiles below pool direct samples across all three repeats.

| Ships | Harmonics | Scenario RTF median (min/max/CV) | Aggregate ship-s/s | k1 p95 | k2 p95 | k3 p95 | k4 p95 | Pooled RHS p95 | RK4 step p95 | Peak current RSS | Max row delta RSS |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 8 | 47.911 (47.580/47.941/0.003) | 47.911 | 103.551 us | 99.522 us | 98.722 us | 101.474 us | 101.442 us | 440.030 us | 33.91 MiB | 1.06 MiB |
| 1 | 32 | 46.294 (46.146/46.398/0.002) | 46.294 | 107.618 us | 103.747 us | 102.018 us | 105.122 us | 104.896 us | 457.832 us | 33.90 MiB | 1.05 MiB |
| 1 | 128 | 39.772 (39.449/40.224/0.008) | 39.772 | 128.045 us | 120.895 us | 119.487 us | 125.477 us | 123.429 us | 530.742 us | 33.90 MiB | 1.05 MiB |
| 5 | 8 | 9.770 (9.756/9.877/0.006) | 48.852 | 101.633 us | 96.991 us | 96.162 us | 99.615 us | 98.912 us | 432.096 us | 35.45 MiB | 2.61 MiB |
| 5 | 32 | 9.429 (9.362/9.493/0.006) | 47.143 | 105.727 us | 101.055 us | 99.680 us | 103.455 us | 102.655 us | 447.422 us | 35.45 MiB | 2.60 MiB |
| 5 | 128 | 8.100 (8.073/8.144/0.004) | 40.501 | 123.711 us | 118.463 us | 117.407 us | 121.312 us | 120.608 us | 517.469 us | 35.45 MiB | 2.60 MiB |
| 20 | 8 | 2.450 (2.415/2.458/0.008) | 49.003 | 101.951 us | 97.119 us | 95.935 us | 100.895 us | 98.943 us | 431.712 us | 41.30 MiB | 8.46 MiB |
| 20 | 32 | 2.347 (2.340/2.353/0.002) | 46.935 | 106.114 us | 101.343 us | 100.191 us | 104.319 us | 103.232 us | 450.430 us | 40.90 MiB | 8.05 MiB |
| 20 | 128 | 2.009 (2.008/2.048/0.009) | 40.184 | 123.743 us | 119.199 us | 117.984 us | 122.015 us | 121.344 us | 520.927 us | 41.41 MiB | 8.57 MiB |

## Harmonic scaling

Ratios are descriptive measurements relative to the 8-harmonic row for each ship count; no complexity model is claimed.

| Ships | From | To | Direct pooled RHS p95 ratio | Scenario RTF ratio |
|---:|---:|---:|---:|---:|
| 1 | 8 | 8 | 1.000 | 1.000 |
| 1 | 8 | 32 | 1.034 | 1.035 |
| 1 | 8 | 128 | 1.217 | 1.205 |
| 5 | 8 | 8 | 1.000 | 1.000 |
| 5 | 8 | 32 | 1.038 | 1.036 |
| 5 | 8 | 128 | 1.219 | 1.206 |
| 20 | 8 | 8 | 1.000 | 1.000 |
| 20 | 8 | 32 | 1.043 | 1.044 |
| 20 | 8 | 128 | 1.226 | 1.219 |

## Threshold proposal — PROPOSED_NOT_APPROVED

No GO/NO-GO decision is made here. These candidate thresholds require issue-owner approval.

| Candidate | Limit | Observed representative 20 ships/32 harmonics | Result |
|---|---:|---:|:---:|
| 20_ship_8_to_128_rhs_p95_ratio | 5.25 | 1.2264 | True |
| 20_ship_8_to_32_rhs_p95_ratio | 2.0 | 1.04335 | True |
| representative_delta_current_rss_mib | 64.0 | 8.05469 | True |
| representative_direct_pooled_rhs_p95_ms | 0.25 | 0.103232 | True |
| representative_peak_current_rss_mib | 128.0 | 40.9023 | True |
| representative_scenario_rtf_floor | 1.0 | 2.34673 | True |
| stress_20_ship_128_scenario_rtf_floor | 0.25 | 2.00921 | True |

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
