# Mid-MPC / Original GNC 5x runtime optimization

## Scope and numerical contract

Production checkout: `/Users/marine/Code/Colav-Simulator`, base HEAD `7b8095fe`. The separate `mid-gnc-acceptance` worktree is not promoted by this change. Existing unrelated assembler/route-bridge edits are preserved.

The validation tuple is `rule13 / overtaking / mid_mpc_ipopt / god / original-gnc-20260914-v1-env-on`, seed 0. The 80x5 s horizon, 10 s planner cadence, 0.5 s outer simulation step, native GNC periods, double precision, solver tolerances, objectives, constraints, L4/HOLD checks, 20 s deadline and strict-no-fallback policy remain unchanged. No targets are pruned and no numerical work is skipped to meet wall time.

## Changes

- Bound the cache of chart unions to 16 entries, keyed by exact ordered immutable geometry and its precision/SRID metadata. Recreated identical geometry reuses the union; changed geometry/depth-derived geometry or precision misses. All live motion/safety checks and current source-status evidence remain live. No geometric simplification is added.
- Pass initial preparation input through the factory context and build the actual chart/hull-specific graph before RUNNING. Preparation creates no threat cycle, accepted plan or optimizer execution. The first solve still executes IPOPT and normal acceptance.
- Expand the single-target chart NLP using the same CasADi expressions, just as the multi-target path already does. No barrier, Hessian, tolerance, iteration or feasibility settings change.
- Keep the GIL during each short synchronous native GNC callback, avoiding repeated handoffs to telemetry/recording threads. ABI, C++ library, messages and callback order remain the same. [Python documents this behavior for PYFUNCTYPE](https://docs.python.org/3/library/ctypes.html#ctypes.PYFUNCTYPE).
- Bound scheduler catch-up debt by three wall-clock seconds instead of eight steps. The previous limit allowed only 0.8 seconds at 5x, discarding recoverable solver delays. The scheduler still yields between complete simulation steps and bounds backlog after a long system stall.

## Numerical and motion evidence

Five frozen actual GNC inputs, including the 166-iteration T250 input, produce exactly equal decision vectors, constraint vectors, objectives and iteration counts with expanded versus original evaluation. The T250 measured optimizer time was 2.902 s versus 1.966 s in the diagnostic replay. Timing is machine/load dependent.

For the original live T0–270 run versus the first optimized closed loop, all 540 frames across both ships have byte-identical state/reference/input JSON. SHA256: `b218fbf954bf70fee4daaaea02f6967da11dca97282968910b6613aa56c847dc`.

Native binding A/B preserves all original states and emitted latest messages across fractional scheduler steps. A bounded contention probe measured 0.114 s versus 0.094 s per simulated second; this is diagnostic evidence, not the end-to-end acceptance.

Evidence summaries and final source hashes are in `evidence/mid-mpc-5x-20260916/`. Full traces/profiling tools are under `tmp/mid_perf_20260916/`.

## Earlier runtime trials and their limits

The original 270-s run's simulation-step work alone took 76.65 s, an upper bound of 3.52x before server transport. The first optimized 1200-s uncapped server-path trial completed with 5.37x aggregate throughput, zero collisions/groundings/fallback, and a largest measured step of 2.025 s. It predates the final prewarm, native binding and scheduler changes; later parallel checks also contaminated some timing windows.

The first browser trial, run `56382fb8-e67e-4bf8-9701-415cdc5df0d6`, finished 1200 simulated seconds in 267.09 wall seconds (4.493x). It does **not** pass 5x. It had the old scheduler and native binding, and startup overlapped additional load. Later intervals recovered approximately 5x, but dropped catch-up debt persisted. Final acceptance must use the frozen deployed revision with no concurrent test campaign.

## Tests and existing failures

- Main focused core/adapter/integration/performance run: 174 passed, 1 failed. The failure is existing `test_captured_cs_problem_converges_without_restoration_stall[4]`: the unmodified HEAD solver also fails its <10-iteration assertion. Its multi-target numerical strategy is unchanged here.
- Final focused integration/native/scheduler selection: 78 passed, 2 failed, 1 deselected. Both failures assert obsolete frontend strings absent from unchanged HEAD files (`speedStatus` and an old sprite call). Baseline source comparison is recorded. The separately run speed-authority API test passes.
- Final static/grounding suite: 20 passed. Geometry-cache/precision regressions: 2 passed. Native binding suite: 10 passed. Scheduler recovery/bounded-backlog tests: 3 passed. These counts overlap; do not add them as unique tests.
- New frozen slow-input regression checks exact expanded/unexpanded results, strict primal/bound tolerances and zero hard slack.
- Changed production code introduces zero Ruff findings relative to HEAD. Existing complexity/line-length findings remain in solver/adapter; repository-wide lint/tests are not claimed green.

## Final deployed acceptance

**PASS for this configuration's 5x performance acceptance.** Deployed on 8010 (PID 17578), run `7a048a09-629e-40b1-86f8-4c1023e67255`.

| Measurement | Final result |
|---|---:|
| Simulated duration / full frames | 1200 s / 2400 |
| Start-to-final WebSocket wall time | 240.254286 s |
| End-to-end measured multiplier | **4.994708x** |
| First-step graph cache / graph construction | hit / 0 ms |
| First full simulation step | 878.84 ms |
| Largest full simulation step | 2429.32 ms |
| Largest planning attempt / accepted IPOPT | 2338.67 / 2029.41 ms |
| Largest new-frame publication gap | 2.50082 s |
| Running browser samples / buffer exhaustion / non-advancing samples | 190 / 0 / 0 |
| Maximum sampled display delay | 3.0 s |
| Collisions / groundings / fallback | 0 / 0 / false |

The endpoint multiplier is measured independently from the UI's cumulative estimate; start command and final WebSocket delivery are included. The 0.106% difference from exactly 5x is wall-clock delivery/scheduling overhead. Browser sampling is 0.5-s observational evidence, not a frame-by-frame FPS guarantee. Transient ~2.34-s planner stalls remain; the existing reserve absorbed them in this run.

There were 120 scheduled planning attempts: 61 new accepted plans and 59 rejected-candidate continuations using the previously accepted plan after normal revalidation. This pre-existing continuity policy was preserved, not introduced as a performance shortcut. Do not call all 120 attempts new accepted solutions.

Final 2400-frame two-ship state/reference/input outputs are exactly equal to the first optimized full run (before final prewarm/native/scheduler changes), hash `c45fb7200ac79dc3a761e6535bf452bdf3d4e8181de14f995f63725934151f1e`. The earlier original-live comparison separately covers T0–270. This distinguishes complete final-change parity from the shorter original baseline.

Current service is left available with the completed validation. Unrelated dirty files are preserved; no commit or merge was made. Full records remain in the run directory. The final screenshot is `evidence/mid-mpc-5x-20260916/browser-finished.png`.

**Acceptance boundary:** current environment-ON overtaking performance, at the configured 1200-s limit. It is not full overtaking/recovery/arrival acceptance, a guarantee for other scenarios, or a bound under arbitrary concurrent system load. Original GNC's broader diagnostic qualification remains unchanged.
