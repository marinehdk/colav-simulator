# Sealed Run Replay — Orchestrator Task Ledger

> Maintained by the Main Orchestrator only.
> Created: 2026-09-11. Execution contract: `handoff/2026-09-11-sealed-run-replay-orchestrator-handoff.md`.

## Baseline & topology

| Item | Value |
|---|---|
| Integration branch | `feature/sealed-run-replay` (main@dee60ece ⊕ spec/run-replay-evaluation@590e7e49) |
| Integration worktree | `/Users/marine/Code/.worktrees/Colav-Simulator/sealed-run-replay` |
| Spec branch | `spec/run-replay-evaluation` @ 590e7e49 (PR #76 draft, **merge deferred**) |
| Parallel track | GNC session owns main pushes + worktree `original-gnc-integration` (16 unmerged commits + T9b WIP) |

## Ticket states

```text
#70 INTEGRATED+CLOSED 2026-09-12 — merge 664a927c (8721bcff..82cb5979), verifier ACCEPT, evidence issuecomment-5640790063
#71 IMPLEMENTED (implementer stopped pre-report) → VERIFIER dispatch 2026-09-12
    commits 18b6d5b3..973f61ef (4, +2710/−81): window API + derived seek cache / shared kinematics+adapter+parity /
    paused timeline race-safe seek / gz journal events; tools/measure_replay_window_perf.py
    verifier extra duties: canonical_threat.py second-truth audit (NEW unlisted file), perf evidence collection, consolidated issue comment
#72 blocked by #71
#73 blocked by #72
#74 blocked by #73
#75 blocked by #74
```

## Orchestrator decisions (2026-09-11 review)

- **D1 Amendment 1 (spec 590e7e49, comments on #69/#70):** capture default-ON + opt-out; budgeted LRU retention for decision traces (default pinned by #70 measurement); events.jsonl gzip allowance w/ dual-form readers; per-run capture-bytes budget → typed INCOMPLETE. Grounded: runs/ 6.1GB, disk near capacity, 120-tick trace = 8.9MB gz + 9.4MB raw events.
- **D2 PR #76 merge deferred** until GNC session finishes pushing marine/main (avoids non-fast-forward against their local main). Integration branch already carries spec content; implementers read docs from worktree.
- **D3 Spec branch edit deviation:** amended spec/run-replay-evaluation directly (handoff §1.2 said don't modify; overridden by user mandate to adjust plan before execution; recorded here).
- **D4 Baseline drift:** spec authored at 1c2b69a; integration is dee60ece. Before #74/#75 (or when GNC lands on main), re-merge main into feature/sealed-run-replay.
- **D5 Interpolation dedup:** #71/#72 implementers must unify the duplicated kinematic interpolation (telemetry-playback.js:161-179 vs situation-display.js:159-203) into one shared module — noted in dispatch prompts, no spec churn.
- **D6 Reconnaissance facts handed to implementers:** product tick choke = WebSessionManager.tick()/step(); no run registry API exists; TraceBundle gzip random-seek is O(file) per seek (perf = #71 measurement, not #70); historical workflow capture path = #74 scope.

## Dispatch log

| Time (local) | Ticket | Agent/role | Worktree | Branch | Result |
|---|---|---|---|---|---|
| 2026-09-11 | #70 | implementer (bg) | replay-70 | agent/replay-70-full-evidence | ACCEPT-candidate: 4 commits 8721bcff..b757738c, +1987/−73, all ACs claimed green, 32 full-suite failures reproduced byte-identical on baseline af51ee35; evidence comment issuecomment-5640183591 |
| 2026-09-12 | #70 | verifier (bg) | reads replay-70 | agent/replay-70-full-evidence @ b757738c | ACCEPT — all ACs+amendments verified at public seams; defects 2-5 minor → repair; defect 1 = load flake |
| 2026-09-12 | #70 | repair (bg) | replay-70 | agent/replay-70-full-evidence | DONE: 82cb5979 — 4 defects fixed, 8 new tests red→green, orchestrator re-ran 56 pass/62s |
| 2026-09-12 | #70 | orchestrator | sealed-run-replay | feature/sealed-run-replay | merge 664a927c, pushed marine; #70 closed w/ evidence issuecomment-5640790063 |
| 2026-09-12 | #71 | implementer (bg) | replay-71 | agent/replay-71-seek | pending |

## Verifier verdicts

- **#70 (2026-09-12): ACCEPT.** Independently confirmed: backend capture w/o browser, digest re-verification, session-replacement trace closure, old v1 + new gz traces both CLI-readable, GET-only confinement, retention LRU truthfulness, opt-out honored, cwd note. Pre-existing failures validated by subset equivalence (14 under load + 6 solo, baseline-identical) instead of full 68-min suite.
- **Flake registry:** `test_historical_api.py::test_historical_api_uses_normal_session_and_publishes_final_evidence` is flaky under heavy parallel load (passed solo ×2 on branch and baseline; capture-free unchanged path). Future verifiers: do not misread as regression without solo reproduction.
- Known-accepted nits (post-repair state to be re-checked): opt-out run after session replacement classifies REDUCED not UNAVAILABLE·TRACE_CAPTURE_DISABLED (truthful per §4.5; reason granularity only in live describe).
