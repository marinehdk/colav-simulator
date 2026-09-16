# Two prior GNC tasks: integration audit

Requested scope: finish the second task's recovery/grounding/three-ship issues, then merge all intended changes into local Simulator main and deploy 8010. User confirmed that 1200 s is a default simulation duration, not a mission deadline; retain production configuration and extend diagnostic runs for complete overtaking/recovery.

## Verified starting state

| Work | Git/source state | 8010 at audit |
|---|---|---|
| First task `01a09e5b-734d-7ac3-8cc6-d9ea632386ab`: GNC card, native velocity/route input, Evaluation replay, VO monitored-duty fixes, UI adjustments | Production commits merged through `7b8095fe`; original `gnc-avoidance-contract` worktree has no modified tracked source. Only raw diagnostic files remain untracked. | Present; actual new GNC source is a separately verified local dependency, not implied by Simulator commit alone. |
| Second task `01a0a3ec-4919-7e40-aaf8-26a490442e49`: planner-owned retained-route contract, measured-speed prediction, source local-speed/guidance-state fixes, shared arrival, lifecycle guard, recovery search/seed repairs | Dirty, uncommitted `mid-gnc-acceptance` worktree at same base `7b8095fe`. 20 modified tracked files plus retained-route module, tests, fixtures and report/evidence. | Not present in full. Main held only early partial assembler/bridge changes. The previous restart did not promote these files. |
| This task: 5x performance repair | Main working-tree changes; validated old-speed run `7a048a09...` achieved 4.9947x, but not committed yet. | Present. Performance acceptance did not claim OT maneuver/arrival acceptance. |

The first task's `45e274c9`, `59813124`, `bb6e36aa`, `85d45eb0`, `297c2769`, `8c8659a8`, `02d1b251` changes are part of the main history. Its final handoff is `2026-09-15-gnc-replay-main-handoff.md`. Temporary experiments/raw logs are not missing product features.

## Integration strategy

An independent worktree `mid-gnc-complete-20260916` combines the full intended second-task patch with the 5x changes. Original development worktrees and unrelated main files are preserved. Route-bridge conflict resolves to planner-owned, hashed route packets transported verbatim, superseding the early adapter-side splice implementation. Solver cache keys preserve both retained-route topology and static-chart identity; native prewarm includes the retained-route graph.

Independent GNC source worktree has the two local-speed/guidance-state fixes plus a reproduced target-index correction. No control gains, actuator, hydrodynamic or environmental source is modified. Rebuilt library and freshly measured response evidence are required before deployment.

## Timing authority

User reconfirmed a 10 s Mid-MPC solve period for every subsequent acceptance run and production deployment. Factory configuration now resolves the RunSpec override before constructing both the assembly configuration and adapter execution descriptor. Scheduler, retained-plan validity and bridge metadata consequently share the same period. Horizon discretization remains 5 s; it is not the solve cadence. A separate 5 s diagnostic failed at T880 and is not acceptance evidence or a production configuration change.

## Required completion gates

1. Native source/binary/parameter identities verified; fresh route and velocity response qualification; focused integration and frozen-regression tests.
2. Extended OT environment OFF and ON: real IPOPT, no fallback, positive overtaking progress, safe passing, mission-route recovery and shared arrival. Time-limit completion alone is insufficient.
3. Actual `paper_ccta2023_multiship` complete closed loop, all targets retained and all-vessel safety inspected.
4. Final deployed current-user configuration rechecked at 5x with browser buffering evidence.
5. Selective local commits, main integration and 8010 source/build identity verification. No remote push requested.

## User-requested development deployment

After being informed that full recovery remains unaccepted, the user explicitly requested committing the current code to local main and restarting 8010. This supersedes the earlier hold-until-full-acceptance deployment sequence; it does not change any acceptance result.

- Simulator main already contains Replay UI merge `24efc3fe`, including default history trails and the scale/view/chart controls. This integration preserves all 13 Replay UI files byte-for-byte.
- GNC source is committed as `4dcfedd` and fast-forwarded to its local main. Source manifest `0af8012364c477d91f135614ba9c3fb6b1eb1a280a29557c9fb2f2fb79f06417`; native library SHA256 `24b2f1b83ef9d35d81071779f9ae3df01829bcb2724d0c0285304b4fa2e17094`. Guidance/control/plant gains are unchanged. Route and velocity response qualifications were freshly measured for this source.
- Nominal Mid-MPC solve cadence is 10 s across factory, scheduler and assembly; horizon discretization remains 5 s. Safety-invalid held plans can still trigger an early solve; this is not a second configured cadence.
- Frozen join regression: sampled forecast ended 51.62 degrees away from the retained route tangent. Enforcing the existing turn-step limit at that join selects a feasible 2.90-degree join without reducing accuracy or relaxing limits.
- Latest extended OT environment-OFF run (`ot_join10_e0`) failed at T2183.5 with INFEASIBLE, after passing the former prefix failure point. Full mission recovery, environment-ON and three-ship acceptance remain open. Old 4.9947x performance evidence belongs to the earlier behavior and does not certify this new full version.
- Development worktrees, raw failure traces and unrelated main untracked files are retained. No remote push is part of this request.

Predeployment checks: 166 focused Python tests passed; two pre-existing obsolete UI string assertions in `test_playback_speed.py` failed (also recorded in the earlier baseline evidence). All 327 Web tests passed. Source/library verification and Simulator diff whitespace checks passed. Full closed-loop acceptance remains incomplete as described above.

Runtime restart and browser verification are recorded separately after deployment.
