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
#70 READY → DISPATCHED 2026-09-11 (implementer worktree replay-70, branch agent/replay-70-full-evidence)
#71 blocked by #70
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
| 2026-09-11 | #70 | implementer (bg) | replay-70 | agent/replay-70-full-evidence | pending |

## Verifier verdicts

(none yet)
