# Issue #54 modular GNC performance evidence

- Schema: `gnc-performance.v2`
- Claim ceiling: `performance_characterization_and_A2_blocker_evidence_only`
- Execution source commit H: `638e6908f057577a9cbe7907170c58fd19767d9a`
- Execution source archive SHA-256: `5323b72340677bf21d80a6222caab80cdcd14401225de4ce6081836cdbca1359`
- Execution source manifest SHA-256: `e14a2c21d0a20fd7e1bd64b2c15e1f5bbc62d01d4f913d7fc117d56e2f0bd1da`
- Execution source dirty: `False`
- Platform: `macOS-26.6.2-arm64-arm-64bit`, `25.6.0`, `arm64`
- Python: `/Users/marine/Code/.worktrees/Colav-Simulator/modular-gnc-stack/.venv/bin/python` / `3.11.15`
- uv.lock SHA-256: `5f6803e4b18ff2d5480b515779900409f8d40983d2e108b3ff71c7cc3ab24ce4`
- Dependency freeze SHA-256: `b167da0e039d6c309ba2e0e739ba3928afc6bb2c5680e2ae4d1959303cc4ee1f`
- Harness config SHA-256: `f894bc6f47a92152ee34e06dc8c1755ccb8023a5e1cbf8cfe20feca0e70431c1`
- Input SHA-256: `3c0097608c9504fd5b2e5b1761a3e6ee7eaf867e83d3fda2cd7cac86589a3887`
- `result_file_sha256`: `f63846b4253f4031c6f6a327549eb7d7b40693ca0ac7a51e75c9b9186bdf10e1`
- `payload_sha256`: `e69f81aa3ddf131581ac948e20ec13bf480c59484cdac9a650d9d6ca5a2c3f14`
- CPU affinity: `uncontrolled`

## Contract and traceability

Direct path: `AnalyticEnvironmentField` + `EnvironmentalLoadModel` + `Generic3DOFPlant` + scheduler-owned `rk4_step`; GUI, legacy simulation, COLAV, and adapters excluded. Fixed 50 Hz × RK4 × 4 stages = 200 direct RHS evaluations per ship per simulated second. Each k1/k2/k3/k4 sample directly times stage-specific environment query, load model, and plant RHS. Parent RSS monitoring is outside worker timing loop.

Authoritative RA-03: `docs/superpowers/specs/2026-08-28-agx-l45-gnc-integration-design.md`, section `Review Amendments (2026-08-31, binding), RA-03`.

## Matrix results

Scenario RTF = common-axis simulated seconds / wall seconds. Aggregate ship-s/s = ships × scenario simulated seconds / wall seconds. Percentiles below pool direct samples across all three repeats.

| Ships | Harmonics | Scenario RTF median (min/max/CV) | Aggregate ship-s/s | k1 p95 | k2 p95 | k3 p95 | k4 p95 | Pooled RHS p95 | RK4 step p95 | Peak current RSS | Max row delta RSS |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 8 | 174.078 (170.442/174.918/0.011) | 174.078 | 28.086 us | 27.794 us | 27.625 us | 28.504 us | 28.084 us | 138.402 us | 35.27 MiB | 0.58 MiB |
| 1 | 32 | 166.191 (165.908/171.623/0.016) | 166.191 | 29.291 us | 29.210 us | 28.463 us | 29.750 us | 29.209 us | 147.187 us | 35.34 MiB | 0.59 MiB |
| 1 | 128 | 147.375 (103.219/151.430/0.163) | 147.375 | 37.059 us | 43.258 us | 40.416 us | 34.710 us | 38.796 us | 183.612 us | 35.28 MiB | 0.64 MiB |
| 5 | 8 | 34.240 (33.933/34.359/0.005) | 171.200 | 29.417 us | 29.502 us | 28.833 us | 29.627 us | 29.375 us | 143.171 us | 37.06 MiB | 2.45 MiB |
| 5 | 32 | 33.780 (33.613/33.862/0.003) | 168.900 | 29.250 us | 29.084 us | 28.750 us | 29.375 us | 29.125 us | 141.048 us | 36.97 MiB | 2.34 MiB |
| 5 | 128 | 29.616 (29.570/29.719/0.002) | 148.080 | 33.167 us | 33.627 us | 32.958 us | 33.336 us | 33.291 us | 157.417 us | 37.06 MiB | 2.41 MiB |
| 20 | 8 | 8.474 (8.152/8.693/0.026) | 169.484 | 31.208 us | 31.042 us | 30.625 us | 31.416 us | 31.042 us | 151.710 us | 39.62 MiB | 4.83 MiB |
| 20 | 32 | 7.989 (7.685/8.466/0.040) | 159.783 | 34.083 us | 33.250 us | 32.961 us | 33.083 us | 33.375 us | 172.791 us | 37.72 MiB | 4.12 MiB |
| 20 | 128 | 7.567 (7.566/7.622/0.003) | 151.337 | 31.875 us | 31.792 us | 31.667 us | 32.208 us | 31.834 us | 136.875 us | 40.30 MiB | 5.62 MiB |

## Harmonic scaling

Ratios are descriptive measurements relative to the 8-harmonic row for each ship count; no complexity model is claimed.

| Ships | From | To | Direct pooled RHS p95 ratio | Scenario RTF ratio |
|---:|---:|---:|---:|---:|
| 1 | 8 | 8 | 1.000 | 1.000 |
| 1 | 8 | 32 | 1.040 | 1.047 |
| 1 | 8 | 128 | 1.381 | 1.181 |
| 5 | 8 | 8 | 1.000 | 1.000 |
| 5 | 8 | 32 | 0.991 | 1.014 |
| 5 | 8 | 128 | 1.133 | 1.156 |
| 20 | 8 | 8 | 1.000 | 1.000 |
| 20 | 8 | 32 | 1.075 | 1.061 |
| 20 | 8 | 128 | 1.026 | 1.120 |

## Threshold proposal — PROPOSED_NOT_APPROVED

No GO/NO-GO decision is made here. These candidate thresholds require issue-owner approval.

| Candidate | Limit | Observed representative 20 ships/32 harmonics | Result |
|---|---:|---:|:---:|
| 20_ship_8_to_128_rhs_p95_ratio | 5.25 | 1.02551 | True |
| 20_ship_8_to_32_rhs_p95_ratio | 2.0 | 1.07516 | True |
| representative_delta_current_rss_mib | 64.0 | 4.125 | True |
| representative_direct_pooled_rhs_p95_ms | 0.25 | 0.033375 | True |
| representative_peak_current_rss_mib | 128.0 | 37.7188 | True |
| representative_scenario_rtf_floor | 1.0 | 7.98914 | True |
| stress_20_ship_128_scenario_rtf_floor | 0.25 | 7.56683 | True |

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
