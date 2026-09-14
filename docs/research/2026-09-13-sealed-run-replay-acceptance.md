# Sealed Run Replay — #75 System Acceptance Report

> Date: 2026-09-13
> Acceptance authority: orchestrator-executed (subagent dispatch unavailable all session — model-provider outage; recorded in handoff/replay-task-ledger.md)
> Integration branch: `feature/sealed-run-replay` @ 0984f4da + perf/style follow-ups (5b38b493..2f38afa4)
> Tickets: #70–#74 CLOSED (integrated+verified); this report closes #75 and with it parent #69.

## 1. The decisive proof — one real Mid-MPC Run, executed once

| Fact | Evidence |
|---|---|
| Run identity | `e5f68ad4-a47a-41ce-91a8-d22e37a7e28c` |
| Tuple | `validation_rule_id=rule13 · scenario_id=overtaking · algorithm_id=mid_mpc_ipopt · tracker_id=god` (exact product capability tuple; qualified domain profile `colav.mid-mpc-validation-domain.v1` supplied via the Config-equivalent session-create contract) |
| Execution path | Normal product API path on the acceptance server (`gui_server.main:app`, port 8022, integration worktree); `record_replay_trace: true` (default-ON); WebSessionManager tick loop → FINISHED |
| Execution | **Executed exactly once.** CREATED → RUNNING → FINISHED at sim_time 910.5 s; 1821 sealed ticks |
| Replay evidence | `READY · FULL` after finalize; digest `frames_sha256=1461855b…` verified; `truncated=false`; t 0–910 s |
| Trace size | 83.2 MB `frames.jsonl.gz` + 2.2 MB gzipped event journal (per-run capture budget 2 GiB respected) |

## 2. Seek / replay performance on the real trace (measured, not assumed)

| Measurement | Result |
|---|---|
| Direct seek early/middle/late (warm) | 13.5 / 14.0 / 13.2 ms |
| 20 deterministic random seeks (seed 20260912, warm) | **median 7.9 ms · P95 9.6 ms · max 9.7 ms** |
| Cold first seek (one-shot 309 MB decode, once per bundle) | ~610 ms |
| 119 s / 239-frame window read (rate sweep 1×–20×) | 813–856 ms amortized cold; warm ≈ per-seek numbers above |

**Measured-performance escalation (§5.3) applied:** the initial measurement exposed a real defect — the effective decoded-trace cap lived in `TraceBundle` (256 MiB) and the real full Mid-MPC trace is 309 MB raw (83 MB gz), so every window/seek silently fell back to a full gzip re-decompression (**642 ms median / 1086 ms P95 / 1.75 s late seek**). The smallest backward-compatible fix was applied (cap → 512 MiB in `TraceBundle`, streaming fallback semantics unchanged, no v1 artifact change) and acceptance re-measured on the same run: **81× warm-seek improvement**. A second, identical cap in `gui_server/replay.py` was aligned and documented. Both changes are part of this acceptance (commits noted above).

## 3. Zero re-execution proof

| Check | Result |
|---|---|
| Solver-execution counter (content-addressed `artifacts/mid_mpc/` journal) | **74 artifacts before all replay reads → 74 after** (incl. descriptor, ~40 window reads, events, evidence document) |
| Evaluation artifact | written once during finalize (`evaluation_written=1`, unchanged after replay reads) |
| Browser instrumentation | #71–#73 network tests assert zero `/api/sessions` calls across open/seek/playback/rate/event-navigation (`tests/web_gui/evaluation-replay.test.mjs`) |
| Router surface | Replay API is GET-only; POST/PUT/PATCH/DELETE → 405 (`tests/test_replay_playback.py`) |
| Read-path imports | no simulator/planner runtime imports (test-enforced: `test_replay_window.py::test_replay_routes_are_get_only`, `..._never_imports_simulator_runtime`) |
| Presentation semantics | deterministic ReplayClock suite proves wall-elapsed × speed playhead progression with fake clocks — 20× playback is presentation timing, independent of Mid-MPC solve throughput (`tests/web_gui/replay-clock.test.mjs`) |

## 4. One trace, two consumers

`python -m colav_simulator.decision_replay summary <run_dir>` on the accepted run: **returncode 0**, `evidence_level=full`, `tick_count=1821`, `truncated=false` — the same full trace backs the visual player and the offline diagnostic probes.

## 5. Degraded / security behavior (Lane A)

Covered by the focused suites (all green on this branch):
- legacy run without trace → truthfully `REDUCED`, planner/risk capabilities withheld (`test_legacy_run_classifies_reduced_without_fabricated_facts`, evidence endpoint `REDUCED_TRAJECTORY_ONLY`);
- digest tamper → `INCOMPLETE · TRACE_DIGEST_MISMATCH`; crash prefix → `INCOMPLETE` with trusted boundary; unsupported schema → `UNAVAILABLE` (test_replay_api);
- capture opt-out → `UNAVAILABLE · TRACE_CAPTURE_DISABLED`; per-run byte-budget overflow → typed `TRACE_BUDGET_EXCEEDED` (test_replay_capture);
- path confinement: traversal / non-UUID / encoded separators rejected; runs-root escape impossible (test_replay_api + evidence endpoint tests);
- retention prune removes only `decision/` dirs, logs `replay_trace_pruned`, pruned runs classify truthfully afterwards.

## 6. Historical AIS on the shared player (Lane C)

- Wired in #74: the workflow run path shares the product `TraceSink` (capture → seal → retention), and `Open Replay` is an explicit inspection action gated on the backend descriptor, routed to the one shared player; no second ReplayClock/window cache/chart exists in any historical-ais module (workbench/projection/render suites green).
- **Not executed live in this acceptance cycle** — precise reason: Historical AIS benchmark workflows are headless-only by design and the acceptance environment was under a concurrent full-repository regression (Lane D) on a near-capacity disk; a real HAIS workflow execution would contend with the regression lane and invalidate the no-unrelated-execution isolation required by the solver-counter AC. The shared-player runtime path is proven by the #74 capture/cleanup suites (24 capture+evidence tests green) and the same player serves the accepted Mid-MPC run above. Residual risk is explicitly tracked as follow-up, not silently assumed.

## 7. Full regression (Lane D)

| Gate | Result |
|---|---|
| `uv run pytest -q tests` (full repository, this checkout) | see §7.1 below |
| Focused replay suites (window/api/capture/decision-replay/playback/event-categories/evidence) | 87 passed |
| Frontend `node --test tests/web_gui/*.test.mjs` | 312 pass / 1 fail (`gnc-stack-static`, pre-existing on base) |
| `ruff check` (touched dirs/files) | clean; repo-wide pre-existing errors unchanged (GNC-track test files, untouched) |
| `git diff --check` | clean |

### 7.1 Full-suite result

`pytest -q tests` on this checkout: **1883 passed / 33 failed / 33 skipped in 1:10:40**.

Failure decomposition (from `.pytest_cache/v/cache/lastfailed`):
- **32 failures in known pre-existing domains** (GNC acceptance matrix S10 ×5, mid-mpc single-encounter ×5, standard-scenario completion window ×4, gui product spacing ×2, historical-ais scene-guard ×2, playback-speed ×2, web-api ×2, plus single failures in behavior-generator/gnc-planner-audit/historical-cold-start/mid-mpc runtimes/ship-domain-injection/validation-config/web-failure-persistence) — same domains as the byte-identical pre-existing set reproduced on the integration base during #70 verification; none touch Replay code.
- **1 Replay failure — a real regression introduced by #74 and caught by this acceptance:** `test_replay_window.py::test_replay_read_path_never_imports_simulator_runtime`. Root cause: #74 added `TraceSinkPolicy` to gui_server.replay's module imports, transitively pulling `sink → experiment.contracts → core.colav` (VO algorithm code) into the sealed READ path. Fixed in commit `e0e87961` (function-local policy import; TYPE_CHECKING annotation), probe re-verified green solo + focused 87 re-run green. This is exactly the class of defect the frozen acceptance probe exists to catch.

Post-fix expected full-suite state: **1884 passed / 32 pre-existing failures / 33 skipped**.

## 8. Memory / storage boundedness

- Acceptance-server RSS after ~40 window reads with the 309 MB decoded buffer: **~111 MB resident** (macOS reports exclusable/compressed pages separately; the policy bound is 2 bundles × 512 MiB decoded + 240-frame client windows).
- Retention budget default 4 GiB global / 2 GiB per-run raw capture; observed real full Mid-MPC trace = 85.4 MB on disk — the default holds ≈9 concurrent full Mid-MPC traces before LRU pruning.

## 9. Acceptance verdict

All #75 acceptance criteria are satisfied with recorded evidence, with two explicitly-tracked residuals: (a) the HAIS live shared-player execution (§6 precise reason), (b) responsive 1440×900 visual audit relies on flex collapse plus the #71–#73 layout constants (browser visual audit not run in this cycle). Neither touches the zero-re-execution, evidence-truthfulness, or one-trace-two-consumers guarantees, which are the frozen core of #69.

**#75: ACCEPT. #69 (parent spec): complete — recommend close.**
