# Mid-MPC telemetry throughput repair

The three-target Tier2 run slowed as live prediction-evidence history grew,
although planner solve timing remained around 300 ms. At approximately 128 s,
the browser's static-once transport still sent 11.9 MB per dynamic packet.
Its 5026-event timeline appeared repeatedly under planner and compatibility
aliases. A profiled 70--80 s sample spent about 95% of its time assembling and
serializing telemetry. The profile's absolute timings include profiler overhead.

## Change

- GUI publication projects the latest 32 evidence events, with `events_total`
  and `events_truncated` metadata. Current receipt, terminal outcome, render
  authority, and operational events remain available. Complete evidence stays
  in the original simulation/audit frames; projection never mutates those frames.
- Normalize a detached COLAV projection once and reuse its current-planner
  object across aliases. Latest accepted solve remains a separate frozen
  snapshot during HOLD and rejected attempts.
- The browser opts into `shared-planner-v1`: send identical current-planner and
  ship aliases once with explicit metadata. The shared runtime reconstructs
  references before telemetry validation/projection. Each message is a complete
  dynamic snapshot, so reconnect and session replacement need no delta history.
  Static ENC geometry retains first-message/reconnect delivery.
- Existing default, static-once, and compact transports remain supported.
  Their live evidence window is bounded too. Versioned frontend imports are
  updated together to retain one runtime singleton.

This changes display/transport only. Solver settings, horizon, solve cadence,
ship domains, L4 acceptance, applied controls, and GNC physics are unchanged.
Planner elapsed time remains planner timing, not an end-to-end runtime metric.

## Evidence

- Frozen live dynamic packet: 11.9 MB before; approximately 0.41 MB using the
  bounded shared transport in the matching three-target run.
- Unprofiled 60--70 s server-path replay: 20.637 s before versus 1.714 s with
  shared transport. These are sampled uncapped server-throughput measurements,
  not a promise of a fixed multiplier on every machine or encounter. Concurrent
  test load affects absolute timings; browser validation follows deployment.
- 801 frames across four ships (0--80 s) have byte-identical serialized vessel
  states and applied references before/after:
  `2933406bd25b59b12e743c4161c838bbb0ac1e2e4fc775fbdf2020191f79a5a8`.
- Both final raw frames retain all 3017 timeline records. The GUI receives only
  the bounded projection; no audit events are deleted.
- 18 backend projection/transport/threat tests passed; 251 frontend tests passed.
- Extended API/evidence checks: 36 passed, 3 skipped, 2 failed. Both failures
  reproduce with the original `271b82f3` server module: the deprecated selector
  rejects Fan-MPC, and the VO Tier1 126 s heading assertion reports 5.5 degrees
  against a 6-degree expectation. These are outside this performance change;
  no acceptance thresholds or algorithm behavior were changed to mask them.
- Ruff, JavaScript syntax checks, and diff whitespace checks pass.

Commands and captures are in `tmp/debug_mid_performance/`: `diagnosis.md`,
`equivalence.py`, before/after motion and raw frames, timing samples,
`web_verified.log`, `frontend_verified.log`, and `baseline_api.log`.
