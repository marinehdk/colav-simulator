# OT env-on speed collapse: rejoin/turn-segment gates lock planner-owned routes at 3-4 m/s

Date: 2026-09-17. Trigger: user report — real-GNC OT full scenario cruises at
7.8 kn planned / 7 kn executed vs Full Stack 15 kn; the overtake drags past
T950 and avoidance+return never completes in the 1200 s production window.

Status: **root cause verified by reproduction; GNC guidance-seam exemption
implemented and speed behavior accepted; late-recovery solve failure (T885
INFEASIBLE) is the remaining known family, unmodified.**

## Reproduction

User run `runs/63962b72-*` (overtaking, mid_mpc_ipopt,
`original-gnc-20260914-v1-env-on`, 1200 s) and identical local campaign
`tmp/mid_complete_20260916/ot_envdiag_on`:

| t | published route speeds | applied_speed_ref | actual STW |
|---|---|---|---|
| 0 | 8.0 (all legs) | 8.00 | 8.00 |
| 300 | 8.0 | 7.38 | 5.88 |
| 500 | 8.0 | 4.71 | 3.21 |
| 800 | 8.0 | 3.61 | 3.60 |
| 1100 | 8.0 | 3.00 | 3.50 |

The planner side is correct throughout (mission_speed_plan 8.0, published
waypoint speeds 8.0, admission accepted every 10 s). The GNC-side applied
reference collapses to the 3.0-4.2 band and never recovers; the loop ends at
goal_distance 1196 m, lead +250 → -163 m.

## Root cause chain

The WP2 fix (GNC `11a21c3`, `external_route_turn_skip_planner_routes`)
exempted planner-owned routes from exactly one speed authority: the
operator-leg external-turn preview (4.2 m/s). Two further gates of the same
design lineage stay active for planner routes and lock the whole
deviate-and-return maneuver:

1. **Rejoin speed gate** (`rejoin_speed_gate_enabled`, cap 3.0, severe 1.5
   at >30 deg): triggers on heading error > 15 deg against the active route
   segment. Mid republishes the retained route every 10 s; the S-shaped
   return leg keeps the vessel in a turning transient with 21-64 deg
   tracking error (reproduction T600 21.6 deg, T700 64.5 deg after a route
   shape swap) — the gate reads each republished route's transient as
   "joining a new line off-course" and holds 3.0 indefinitely.
2. **Turn-segment speed gate** (4.2): activates while a turn is heading-
   limited and the vessel is not "stable" (XTE <= 35 m, heading error
   <= 6 deg, rate limits). A continuous S-return never satisfies the
   release predicate.
3. **Cruise speed recovery** (back to 8.0 via 6.0 base) requires
   `straight_cruise_window = !turn_segment_speed_gate_active_ && ...`, so
   with (1)/(2) latched the recovery path is structurally unreachable —
   the speed lock is permanent, not transient.

Low speed then feeds back: weak rudder authority at 3 m/s under wind/current
(env-on) widens the tracking error, which re-triggers the gates — the
vicious cycle the GNC source itself warns about in the rejoin block. Full
Stack has none of these caps (mission-speed authority path, diagnosis
report R4) and completes the overtake at 15 kn by T~430.

A Sim-side aggravator was observed (not the root cause): at T670 the
publication chain swapped a 170-point mirror for a 14-point route whose
head leg pointed 73 deg off the vessel's heading, spiking the tracking
error to 64 deg (severe rejoin 1.5). The route-head continuity of the
splice/capture chain is recorded as a watch item.

## Fix (GNC guidance seam, WP2-pattern exemption)

GNC branch `fix/planner-route-speed-gates` (commit `8a574a0`, parent
`11a21c3`), worktree `.worktrees/GNC/rejoin-gate-20260917`:

- New rollback parameter `planner_route_speed_gate_skip` (default true).
- Exemption boolean `planner_route_speed_gate_exempt =
  planner_route_speed_gate_skip_ && latest_route_command_source_ ==
  "mid_mpc_ipopt"` — same command-source mechanism as WP2, independent
  switch so external-turn semantics are unchanged.
- Rejoin gate: the heading-error trigger is waived for planner routes;
  the lateral trigger (XTE > 60 m) is preserved — genuine off-corridor
  excursions still slow down.
- Turn-segment gate: not activated for planner routes (its cap duty is
  already covered by the admission-validated per-waypoint speeds); the
  latched state resets through the existing branch, unlocking the cruise
  recovery window.
- No control, hydrodynamic, safety, emergency, or corridor behavior
  changes.

Build `gnc-rejoin-gate-20260917` (source manifest sha `11d291f8…`,
library sha `0884924c…`), pointer `build/original_gnc-current` switched.
Qualification identical to the previous build at full precision (route:
course tau 87.0333 / R² 0.988889, speed tau 24.0675 / R² 0.984821;
velocity: course tau 39.4256 / R² 0.974319, speed tau 12.5054 /
R² 0.940988). New gate tests `tests/test_original_gnc_planner_speed_gate.py`
(4/4): planner route + 20 deg heading error → 6.0 m/s (no 3.0 cap);
rollback → gate restored; operator route → unchanged; planner + 70 m
lateral → lateral leg still caps.

## Acceptance (OT env-on, same scenario, new build)

`tmp/mid_complete_20260916/ot_waiver1_on`: the overtake completes at
T~500 (lead +14.8 m) and reaches max lead +303 m by T~880, versus the
pre-fix +250 m peak with final lead -163 m and 1196 m short of goal.
Speed through the encounter holds 4.2-5.8 m/s; no 3.0 lock.

Remaining failure: T885.5 `Mid-MPC optimizer returned INFEASIBLE without a
feasible candidate` (goal 1699 m out) — the known late-recovery solve
family from the 2026-09-16 report (budget spiral vs long fixed prefix +
recovery windows; e0 died the same way at T1080). Unmodified by this fix;
solver-side follow-up.

## Note for runs against the worktree

Until the GNC branch merges to GNC main, native-stack runs need
`COLAV_ORIGINAL_GNC_SOURCE=/Users/marine/Code/.worktrees/GNC/rejoin-gate-20260917`
(the approved-manifest check reads the source CSV from main, which still
carries the previous revision). The 8010 service needs the same variable
(or the merge) plus a restart before user-facing scenarios pick up the fix.

## Artifacts

- User runs: `runs/63962b72-*`, `runs/c063d784-*`, `runs/c5ccf1bd-*`
- Reproduction: `tmp/mid_complete_20260916/ot_envdiag_on`
- Acceptance: `tmp/mid_complete_20260916/ot_waiver1_on`
- Gate parameters as-run: `runs/63962b72-*/original-gnc.json`
  (`parameters.ship_guidance_node`)
- GNC source anchors: `ship_guidance_node.cpp` rejoin gate (~L5666),
  turn-segment gate (~L5611), cruise recovery window (~L5790),
  WP2 authority flag (~L5183)
