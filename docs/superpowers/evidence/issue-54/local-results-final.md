# Issue #54 modular GNC performance evidence

- Schema: `gnc-performance.v2`
- Claim ceiling: `performance_characterization_and_A2_blocker_evidence_only`
- Execution source commit H: `6372f961ff39c9048d27baf61cca926d11566a7a`
- Execution source archive SHA-256: `ea9f8ea57b21fbfb29be923fec3bbd6b53cd92e11d35d1ff6ad3b2abc4d62942`
- Execution source manifest SHA-256: `35acb8d2664938fbc4883fda24345b6f7798ad50816d0c1d6a178b01ba1ac0b8`
- Execution source dirty: `False`
- Platform: `macOS-26.6.2-arm64-arm-64bit`, `25.6.0`, `arm64`
- Python: `/Users/marine/Code/.worktrees/Colav-Simulator/modular-gnc-stack/.venv/bin/python` / `3.11.15`
- uv.lock SHA-256: `5f6803e4b18ff2d5480b515779900409f8d40983d2e108b3ff71c7cc3ab24ce4`
- Dependency freeze SHA-256: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
- Harness config SHA-256: `f894bc6f47a92152ee34e06dc8c1755ccb8023a5e1cbf8cfe20feca0e70431c1`
- Input SHA-256: `3c0097608c9504fd5b2e5b1761a3e6ee7eaf867e83d3fda2cd7cac86589a3887`
- `result_file_sha256`: `3418cd81218a935c2b11014ba4344772ef85b76cad2e866dccf2b73abf02fe11`
- `payload_sha256`: `36611865b1788ec3f9d96f2abe38bb75ab59d1471c60717b2c771a3c040ae001`
- CPU affinity: `uncontrolled`

## Contract and traceability

Direct path: `AnalyticEnvironmentField` + `EnvironmentalLoadModel` + `Generic3DOFPlant` + scheduler-owned `rk4_step`; GUI, legacy simulation, COLAV, and adapters excluded. Fixed 50 Hz × RK4 × 4 stages = 200 direct RHS evaluations per ship per simulated second. Each k1/k2/k3/k4 sample directly times stage-specific environment query, load model, and plant RHS. Parent RSS monitoring is outside worker timing loop.

Authoritative RA-03: `docs/superpowers/specs/2026-08-28-agx-l45-gnc-integration-design.md`, section `Review Amendments (2026-08-31, binding), RA-03`.

## Matrix results

Scenario RTF = common-axis simulated seconds / wall seconds. Aggregate ship-s/s = ships × scenario simulated seconds / wall seconds. Percentiles below pool direct samples across all three repeats.

| Ships | Harmonics | Scenario RTF median (min/max/CV) | Aggregate ship-s/s | k1 p95 | k2 p95 | k3 p95 | k4 p95 | Pooled RHS p95 | RK4 step p95 | Peak current RSS | Max row delta RSS |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 8 | 57.961 (57.737/57.983/0.002) | 57.961 | 86.211 us | 85.417 us | 85.000 us | 84.794 us | 85.625 us | 352.086 us | 35.00 MiB | 34.94 MiB |
| 1 | 32 | 30.104 (29.984/30.137/0.002) | 30.104 | 167.083 us | 166.291 us | 166.583 us | 166.377 us | 166.708 us | 674.750 us | 35.03 MiB | 34.95 MiB |
| 1 | 128 | 10.278 (10.270/10.302/0.001) | 10.278 | 492.419 us | 491.927 us | 491.794 us | 491.002 us | 491.836 us | 1.968 ms | 35.03 MiB | 34.62 MiB |
| 5 | 8 | 11.780 (11.704/11.782/0.003) | 58.901 | 85.000 us | 84.209 us | 83.958 us | 83.834 us | 84.416 us | 347.625 us | 36.64 MiB | 36.58 MiB |
| 5 | 32 | 6.006 (5.988/6.035/0.003) | 30.031 | 168.167 us | 167.667 us | 167.291 us | 166.916 us | 167.542 us | 677.419 us | 35.67 MiB | 35.58 MiB |
| 5 | 128 | 2.077 (2.031/2.082/0.011) | 10.386 | 490.963 us | 490.587 us | 489.916 us | 490.208 us | 490.417 us | 1.962 ms | 36.95 MiB | 36.70 MiB |
| 20 | 8 | 2.947 (2.929/2.981/0.007) | 58.942 | 84.833 us | 83.917 us | 83.750 us | 83.459 us | 84.250 us | 346.125 us | 41.38 MiB | 41.34 MiB |
| 20 | 32 | 1.519 (1.506/1.524/0.005) | 30.388 | 165.917 us | 165.459 us | 165.000 us | 164.959 us | 165.417 us | 670.334 us | 42.75 MiB | 42.39 MiB |
| 20 | 128 | 0.518 (0.517/0.520/0.002) | 10.368 | 490.625 us | 490.125 us | 489.666 us | 489.625 us | 490.000 us | 1.963 ms | 39.25 MiB | 39.22 MiB |

## Harmonic scaling

Ratios are descriptive measurements relative to the 8-harmonic row for each ship count; no complexity model is claimed.

| Ships | From | To | Direct pooled RHS p95 ratio | Scenario RTF ratio |
|---:|---:|---:|---:|---:|
| 1 | 8 | 8 | 1.000 | 1.000 |
| 1 | 8 | 32 | 1.947 | 1.925 |
| 1 | 8 | 128 | 5.744 | 5.639 |
| 5 | 8 | 8 | 1.000 | 1.000 |
| 5 | 8 | 32 | 1.985 | 1.961 |
| 5 | 8 | 128 | 5.810 | 5.671 |
| 20 | 8 | 8 | 1.000 | 1.000 |
| 20 | 8 | 32 | 1.963 | 1.940 |
| 20 | 8 | 128 | 5.816 | 5.685 |

## Threshold proposal — PROPOSED_NOT_APPROVED

No GO/NO-GO decision is made here. These candidate thresholds require issue-owner approval.

| Candidate | Limit | Observed representative 20 ships/32 harmonics | Result |
|---|---:|---:|:---:|
| 20_ship_8_to_128_rhs_p95_ratio | 5.25 | 5.81602 | False |
| 20_ship_8_to_32_rhs_p95_ratio | 2.0 | 1.96341 | True |
| representative_delta_current_rss_mib | 64.0 | 42.3906 | True |
| representative_direct_pooled_rhs_p95_ms | 0.25 | 0.165417 | True |
| representative_peak_current_rss_mib | 128.0 | 42.75 | True |
| representative_scenario_rtf_floor | 1.0 | 1.51939 | True |
| stress_20_ship_128_scenario_rtf_floor | 0.25 | 0.518407 | True |

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
