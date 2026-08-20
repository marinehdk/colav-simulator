# Mid-MPC Prediction Evidence Critical Tail

## Environment

- Date: 2026-08-13 Asia/Shanghai
- Host: Apple M3, arm64
- OS: macOS 26.5.2
- Python: 3.11.15
- Grid: 80 intervals, 81 state samples, 15 s interval
- Repetitions: 1,000 per target-count and outcome case
- Command: `uv run python tools/benchmark_mid_mpc_prediction_evidence.py --samples 1000`

## Scope

Each sample includes strict model construction and deep copy, target-purpose reconciliation, canonical semantic hash, bounded inline projection, occurrence-event construction, pure authority reduction and render projection. It excludes IPOPT and disk/compression work. Fresh, hold and rejected cases use their distinct event topology; hold also includes runtime linear interpolation.

## Results

| Targets | Outcome | p50 ms | p95 ms | p99 ms | max ms | max inline bytes |
|---:|---|---:|---:|---:|---:|---:|
| 0 | fresh | 1.375 | 1.739 | 2.077 | 2.809 | 511 |
| 0 | hold | 1.397 | 1.635 | 1.873 | 2.240 | 511 |
| 0 | rejected | 1.402 | 1.692 | 2.011 | 2.513 | 564 |
| 1 | fresh | 1.656 | 2.084 | 2.428 | 3.168 | 511 |
| 1 | hold | 1.711 | 2.548 | 3.573 | 10.629 | 511 |
| 1 | rejected | 1.676 | 2.109 | 3.028 | 7.036 | 564 |
| 16 | fresh | 5.664 | 6.465 | 7.551 | 89.953 | 511 |
| 16 | hold | 5.660 | 6.400 | 6.983 | 47.758 | 511 |
| 16 | rejected | 5.633 | 6.236 | 6.720 | 62.184 | 564 |

Measured max RSS delta after warm-up was 0 KiB. Every inline projection remained below the 8,192-byte hard limit.

## Reservation Decision

Previous strict L4 benchmark measured 16-target p99 35.046 ms and max 123.557 ms. Conservative sequential sums with the worst Evidence result are:

- Combined p99: 42.597 ms.
- Combined max: 213.510 ms.

Retain the existing 250 ms reservation inside the unchanged 20 s total deadline. It covers the conservative combined p99 by 5.87x and combined observed maximum by 1.17x. IPOPT cutoff remains 19.75 s. Artifact compression, writing, retention and completion reporting remain outside this synchronous reservation.

Calibration id: `m3-macos26-python3.11-20260813-l4-evidence-1000x-0-1-16-fresh-hold-rejected`.

This is local Colav-Simulator evidence, not MASS-L3 target-hardware timing evidence.
