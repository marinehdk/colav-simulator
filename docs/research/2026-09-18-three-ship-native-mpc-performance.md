# Three-Ship / Mid-MPC / original GNC performance

## Scope and measured result

Exact product tuple: `paper_ccta2023_multiship`, Mid-MPC, God tracker, original GNC ENV ON, seed 0, strict no-fallback. The scenario contains Ship0 and three targets. Prediction remains **80 × 5 s**, simulation step **0.1 s**, and replan period **10 s**. No safety, arrival, tracking, or recovery threshold was relaxed. The 3000 s diagnostic ceiling matches the prior acceptance campaign; actual arrival remains earlier than the scenario's normal 1800 s limit.

A real HTTP/WebSocket run requested **5×** and delivered **1744.9 simulation seconds in 349.4029 wall seconds: 4.99395×**. Backend completion time is T1745.0; the final telemetry sample is the pre-step T1744.9 frame. Maximum observed packet gap was **1.9003 s**. Short solve bursts remain; instantaneous production is not a constant-rate stream.

Full recording was enabled throughout: **17,450 frames**, **5,377,842,722 uncompressed capture bytes**, no truncation, replay **READY**, and SHA-256 `6c488eb12d0a97604ea154a8862af25a62e4c2768704bba33ae045325658ba98`. This test explicitly used the existing **8 GiB capture-budget override**. The product's default remains 2 GiB; the full Three-Ship trace exceeds that default. A prior diagnostic stopped recording at T652.5 and is not used as complete-recording acceptance.

Runtime: local Apple Silicon machine, 8 GiB RAM. The unrelated Git repack completed before final measurement. Other diagnostic simulation/export processes were not running during the accepted playback measurement. This is backend HTTP/WebSocket playback evidence, not a browser-rendering FPS benchmark or MASS-L3 release acceptance.

## Diagnosis and fixes

1. **Monotone IPOPT barrier stalls.** A captured real-GNC input at T224.2 reproduced exactly 260 iterations and objective 1110.5338668411955. Adaptive barrier updates need 24 iterations under the same feasibility and recovery-admission checks. The objective, constraints, horizon, and acceptance predicates are unchanged. The uncharted single-target and non-strict calibration paths retain their previous settings. The frozen-input regression rejects the original 260-iteration behavior.
2. **Wrong prewarm graph.** Native identity incorrectly implied retained spatial corridor rows, although timed native trajectories replace the plan. Preparation now selects the graph from the actual retention contract. The accepted run had zero graph builds during RUNNING.
3. **Repeated diagnostic materialization.** The native speed display fetched complete planner diagnostics to read two planner fields. It now reads the planner projection directly. Detached diagnostic snapshots preserve nested values without invoking generic dataclass/deepcopy dispatch for every scalar.
4. **JSON bridge overhead.** Native callbacks, replay capture, and shared telemetry used repeated Python JSON conversions. Native input/output encoding is accelerated, with strict rejection of nonfinite input before C++ execution preserved. Callback outputs, states, ordering, and environmental execution are checked against the previous codec. No C++ GNC kernel changed.
5. **Whole-file replay sealing allocation.** Sealing previously read the entire raw JSONL file into memory. It now hashes and compresses 1 MiB chunks. The old implementation allocates over 10 MiB in the 10 MiB regression; the fixed implementation stays below 4 MiB and retains every frame and the original uncompressed digest.

Exact Hessians reduced the frozen case to 78 iterations but remained too slow. JIT generated a 31 MiB C file with excessive preparation cost. Neither experiment was shipped. Timing samples obtained during the unrelated Git repack are diagnostic only; the final live test above is the acceptance measurement.

## Solver and maneuver evidence

Across the accepted playback run:

| Metric | Result |
|---|---:|
| Real optimizer attempts | 186 |
| L4 accepted / rejected candidates | 185 / 1 |
| IPOPT median | 39.48 ms |
| IPOPT P95 | 394.45 ms |
| IPOPT maximum | 1517.05 ms |
| Graph builds while RUNNING | 0 |
| Actual goal distance at T1745 | 308.617 m |
| Existing arrival radius | 308.7 m |
| Final-leg cross-track | -8.911 m |
| Existing recovery tolerance | 20 m |

The post-step arrival position comes from `original-gnc.json`'s `final_state_8d` plus its frame origin. The last telemetry frame precedes that last physical step and must not be substituted for the termination state.

All attempts report `FeasibleNonOptimal`; this is not a claim of full optimization convergence. Existing candidate-selection policy is unchanged: 182 attempts selected an IPOPT iterate and four selected `PRIMAL_SEED` after an optimizer call. The prior accepted baseline already contained six such seed selections. The prior report's zero-rejection statement was also incomplete: its raw artifacts contain two rejected candidates. These facts must remain separate from the normalized algorithm fallback flag and physical safety verdict.

Independent evaluation: **COMPLETE / ownship hard gate PASS**. Minimum ownship hull clearance is **230.805 m**; ownship and global collision/grounding counts are zero. The complete 69,800 state/control rows also match the independently evaluated reference run exactly; see [evaluation](evidence/three-ship-performance-20260918/evaluation.json) and [state parity](evidence/three-ship-performance-20260918/state-parity.json).

## Why 30 s is not enabled

The 30 s comparison failed at T30 with `Mid-MPC lifecycle TIME_GAP: lifecycle cycle gap exceeds profile`. The current canonical lifecycle advances on solver cycles and requires gaps no larger than 10 s. Merely changing the solve period violates that contract. Supporting a longer optimization period requires an independently scheduled threat/lifecycle update, while retaining timely HOLD validation and early replanning on changed authority. The 10 s limit was not widened to make this test pass.

## Regression and reproduction

- Combined core, native, replay, transport and acceptance regression: **306 passed**, one existing Starlette deprecation warning.
- Subsequent bounded-memory replay validation: **27 passed**.
- Subsequent native encoding, source-vector and timed-trajectory validation: **47 passed**.
- These groups overlap; they are not summed into a fabricated total. No full-repository CI claim is made.

The original 20 s feedback window improved from **2.859× (FAIL)** to **6.545× (PASS)** after deployment, with complete window recording. This short check is separate from the full live playback acceptance above.

Uncapped production-capacity check, from the repository root:

```sh
.venv/bin/python -m tools.benchmark_native_mid_mpc \
  --spec docs/research/evidence/three-ship-performance-20260918/run-spec.json \
  --output tmp/native-mid-mpc-performance \
  --duration-s 3000 --solve-period-s 10 \
  --capture-budget-bytes 8589934592 --minimum-multiplier 5
```

Preparation and final report export are outside the simulation-throughput interval. The benchmark preserves full capture and requires replay READY. Live playback was measured separately through the real server scheduler and shared-planner WebSocket transport.

Evidence: [live playback](evidence/three-ship-performance-20260918/live-playback.json), [solver attempts](evidence/three-ship-performance-20260918/solver-timing.json), [arrival and capture](evidence/three-ship-performance-20260918/arrival-and-capture.json), [checks](evidence/three-ship-performance-20260918/checks.json), and [30 s comparison](evidence/three-ship-performance-20260918/live30.json).

The complete accepted run is `74e2fa1e-2150-4bc7-b0b8-5137073de0fd` under `/Users/marine/.codex/worktrees/three-ship-native-performance/Colav-Simulator/runs/`. Diagnostic logs and rejected experiments remain under `/Users/marine/Code/Colav-Simulator/tmp/three_ship_perf_20260918/`.

## Prevention and deployment

Keep the captured solver-cost, codec parity, snapshot detachment, and bounded sealing regressions. Qualify playback over a full encounter with recording active, not just average offline solver time. A future 30 s mode needs separate lifecycle and optimization clocks. Post-run evaluation/export remains slow and is excluded from the playback interval. Sampling found substantial Python GC work during repeated frame decoding; semantic hashing also materializes large row collections. Streaming semantic hashing and process-isolated background evaluation are follow-up work, so that report generation cannot interfere with a subsequent live run. These are not claims of a 5× end-to-end report-generation rate.

Implementation commits: `40bc2fb8` and `2c7c4247`, based on the previously accepted `546769bc`. Another task reset main to `65d5164e` during this investigation; the user explicitly requested restoring `546769bc` and incorporating these fixes. Main has been fast-forwarded to the fixes, restoring the accepted baseline. The 8010 launchd service was restarted, returns HTTP 200, and the original unstarted Three-Ship configuration was recreated as session `bbe52057-56a1-4c0c-bea9-0c283916d386` in CREATED state. Replanning remains 10 s. No remote push was performed. See [deployment verification](evidence/three-ship-performance-20260918/deployment.json).
