# Mid-MPC L4 Acceptance Reservation

## Environment

- Date: 2026-08-12 Asia/Shanghai
- Host: Apple M3, arm64
- OS: macOS 26.5.2 (25F84), Darwin 25.5.0
- Python: 3.11.15
- Branch baseline: `codex/mid-mpc-l4-plan-acceptance` at `7b7cdfa` plus review fixes
- Grid: 81 state samples, 80 intervals, 15 s interval
- Repetitions: 1,000 evaluations for each target count

## Results

All requests used `COLAV_STRICT`, God zero-uncertainty target evidence, full 81-knot candidate arrays, and the public `MidMpcPlanAcceptance.evaluate` seam.

| Relevant targets | p50 ms | p95 ms | p99 ms | max ms |
|---:|---:|---:|---:|---:|
| 0 | 0.391 | 0.534 | 1.276 | 5.119 |
| 1 | 1.179 | 2.132 | 2.528 | 2.794 |
| 16 | 13.508 | 16.153 | 35.046 | 123.557 |

## Frozen Reservation

Reserve `0.25 s` inside the existing `20.0 s` total deadline. This exceeds the observed 16-target maximum by 2.02x and the observed p99 by 7.13x. IPOPT cutoff is therefore `19.75 s`; final L4, freshness, commit, and evidence-enqueue work must finish before the same 20 s adapter deadline.

Calibration id: `m3-macos26-python3.11-20260812-1000x-0-1-16`.

This calibration supports this exact local production environment and policy only. It is not MASS-L3 timing evidence and must be regenerated when target environment, policy, Python, or acceptance implementation changes materially.
