# Real-GNC OT failure: speed authority is route geometry, not route speeds

Date: 2026-09-16. Session task: diagnose why Mid-MPC completes the overtaking
scenario under the Full Stack GNC but cannot complete it under the real
(authoritative) GNC, including the observed solve-to-solve instability and the
"planned 11 kn / executed 8.4 kn" gap.

Status: **diagnosis complete from recorded-run evidence; no fix applied.**
All numbers below come from recorded run artifacts; no simulation was re-run
for this analysis.

## Runs analyzed

| Run | Stack | Evidence |
|---|---|---|
| `runs/9f9be417-9461-4450-8bbb-02a65e9275b7` (16:22) | Full Stack (`fcb45_roll_4dof...`) | User screenshot 1: overtake complete, released ~T430, DCPA 549.6 m |
| `runs/44e8c018-933d-49ff-bcf3-f40495a77f01` (16:02) | Real GNC `original-gnc-20260914-v1-env-on` | User screenshot 2: T=630.5 s ships just abeam, planner SOG 5.65, GNC surge 4.34, actual 4.15 |
| `$DEV/tmp/mid_complete_20260916/ot_join10_e0/runs/b9ab9456-...` | Real GNC env-OFF, 3000 s | Latest acceptance failure: T2183.5 optimizer INFEASIBLE |

Feedback loop: `tmp/mid_speed_20260916/diff_two_stacks.py` (deterministic
trace analysis, seconds). Verdict on the pair above: Full Stack GREEN (max
lead +550 m), Real GNC RED (max lead -15 m over the recorded 630 s; 21 solves
commanded cruise >= 7 m/s at k10 while the executed reference stayed <= 5.5).

## Differential behavior

| t | Full Stack: sog / lead | Real GNC (env-on): sog / aref / lead |
|---|---|---|
| 60 | 8.03 / -1156 | 5.69 / 6.00 / -1256 |
| 300 | 7.28 / +32 | 5.77 / 5.97 / -648 |
| 420 | 8.12 / +497 | 5.17 / 5.37 / -341 |
| 600 | (released, on route) | 4.55 / 4.48 / -58 |

Full Stack closes the 1414 m initial deficit at ~4-5 m/s and is past by T~300.
Real GNC closes at ~1.5-2 m/s, crosses lead=0 only at ~T630 (matches the
screenshot), and in the env-OFF 3000 s run still hovers at lead 0..+250 m for
another 1000 s before the optimizer dies at T2183.

## Verified causal chain

### R1 (execution layer, dominant): GNC derives execution speed from route GEOMETRY, not route speeds

Submitted Mid execution routes carry `command_speed_mps = 8.0` on the legs
around the ship (verified at t=60/120/300/600 in the env-OFF run: near-ship
waypoint speeds 6.5-8.0). But a deviate-and-return avoidance route inherently
contains cumulative turns of 55-95 degrees starting 41-243 m ahead of the
ship (measured from the submitted geometry). The colleague's guidance node
caps speed from that geometry:

- `external_route_turn_speed_cap_mps = 4.2`, preview 2600 m, hold 4500 m,
  cumulative-angle threshold 12 deg (`ship_guidance_node.cpp`, log tag
  `[EXTERNAL TURN SPEED]`)
- dense-turn pre-deceleration to ~4.2 within the capture window
  (`[DENSE TURN PREDECEL]`, `turn_segment_speed_cap_mps = 4.2`)
- turn approach tables (`turn_speed_45deg = 4.2` at 450 m slow-down distance)

Computed external-turn cap vs actually executed reference (env-OFF run):

| t | first turn ahead | cumulative turn | computed cap | executed |
|---|---|---|---|---|
| 60 | 243 m | 58 deg | 4.55 | 4.53 |
| 120 | 130 m | 8.5 deg* | 4.39 | 4.20 |
| 300 | 41 m | 73 deg | 4.26 | 4.20 |
| 600 | 99 m | 55 deg | 4.34 | 4.00 |

*within the 2600 m preview window the cumulative sum keeps growing.

The caps match the executed speed point-for-point. The user's "planned 11 kn,
executed 8.4 kn" gap is exactly this: the planner's route asks 8 m/s, the GNC
honors ~4.2-4.5 because the route's own avoidance geometry always has a bend
within the preview window. As long as the route deviates laterally and must
return, the ship is permanently in "approach to next turn" mode.

### R2 (planner layer, initiator): first solve brakes hard under the GNC capability tuple

First-solve assembly diff (from artifacts):

| field | Full Stack | Real GNC |
|---|---|---|
| `speed_bounds_mps` | [0, 8] | [3, 8] (steerage floor) |
| `cpa_braking_floor_mps` | 0.0 | 3.0 |
| `route_constraint_limit_m` | None | 480 (retained-route corridor) |
| capability | `fcb45:roll4dof:marine_pid` | `original-gnc:first_order_lag:source_control` |

At t=0 (reference route = nominal [8, 8], so no inherited slow speeds can
explain it) the GNC-tuple NLP brakes 8 -> 4.1 m/s (env-OFF) / 8 -> 2.7-3.4
(env-ON); the Full-Stack NLP holds ~5.7-6.6 and its stack executes mission
speed regardless (see R4). Why the GNC-tuple NLP prefers braking (objective
shape vs CPA/corridor constraints under the 24 s lag) is the one still-open
sub-question; a frozen-frame re-solve at t=0 toggling one assembly field at a
time is the cheap next experiment.

### R3 (loop layer, instability + never-completes): no closed-loop reconciliation

The planner's execution model is a first-order lag (speed tau ~24 s,
response-qualified R^2 ~0.98 for a step) and contains nothing about R1's
geometry caps. So every 10 s re-solve:

1. re-anchors at measured SOG (~4.1-4.5), plan k0 = measured, k1 = +1.3-1.5,
   k10 = 7.25 (the acceleration always lives 50-250 m ahead);
2. the GNC executes ~4.2 (R1), the planned acceleration tail is superseded
   before the ship reaches it;
3. the ship falls further behind the previous plan's along-track expectation,
   the CPA knot and lateral branch shift, and the next plan differs visibly
   from the last — the user's "two consecutive solves differ greatly" with a
   constant-speed target. It is re-anchoring drift, not solver noise.

Closure stays ~1.5-2 m/s, so the overtake that Full Stack finishes by T~300
never completes: the UI run ends uncompleted; the env-OFF 3000 s run hovers
then hits optimizer INFEASIBLE at T2183.

### R4 (why Full Stack works): different speed authority path

In the Full Stack run the tracker executes the mission speed via
`references[3] ~ 7.7-8.0` for the entire encounter — even at t=300-410 when
the plan's own k0 speed profile was 0.3-1.5 m/s (post-encounter braking tail).
Its speed authority is the mission plan + geometry tracking; Mid's plan speed
profile is not what the stack executes. There is also no geometry-derived
speed cap of the R1 kind. So closure ~4-5 m/s and the overtake completes.

## User hypotheses, resolved

1. "Solve instability under real GNC" — real, but downstream: caused by R3
   re-anchoring at a lagged, under-executed state; with a constant-speed
   target the geometry drift comes from the own ship, not the target.
2. "Route not fully executed (11 kn solved, 8.4 kn executed)" — confirmed,
   but the mechanism is not speed-following lag and not ignored waypoint
   speeds (routes asked 8.0). It is R1: the GNC re-derives a ~4.2-4.5 m/s
   envelope from the route's turn geometry and holds it for the whole
   avoidance phase.
3. "T=630 just abeam, sim ends before completing avoidance+return" —
   confirmed numerically (lead crosses 0 at ~T630 in the env-ON run; the
   env-OFF run needed until ~T660 to abeam and never established a lead).

## What is NOT the cause (ruled out by evidence)

- GNC ignoring/mistranslating commanded waypoint speeds (near-ship speeds
  were 8.0 and admission kept them).
- The frozen `[8, 8, 6.74, 4.49]` join dip: it exists and self-propagates via
  the reference mirror, but those points sit behind the ship after the first
  minutes; it kick-starts nothing after t=0 (R2's t=0 braking needs no
  inheritance).
- The late `_navigation_recovery_errors` infinite-line conflict (handoff
  hypothesis): real but late-phase; the speed freeze is already total by
  T~120.

## Recommended next steps (design decision, not applied)

The colleague's guidance gains/tables are out of scope by constraint, so the
fix belongs to the planner/adapter seam: Mid's execution model or route
emission must account for the GNC's geometry-derived speed envelope, for
example by (a) including a turn-preview cap in the capability/response model
the NLP plans against, (b) emitting avoidance geometry whose local curvature
does not permanently trigger the 4.2 m/s class of caps, or (c) planning
speeds the GNC will actually honor so the NLP does not keep deferring.
R2's first-solve braking should be root-caused with a frozen-frame re-solve
before choosing, since fixing only execution still leaves the initial brake.

## Artifacts

- Loop: `tmp/mid_speed_20260916/diff_two_stacks.py` (red on `44e8c018`,
  green on `9f9be417`)
- Key evidence: `runs/44e8c018.../artifacts/mid_mpc/*` (plan profiles),
  `.../original-gnc.json` (`requested_plans`, `execution_events`,
  `parameters.ship_guidance_node`), campaign bundle under
  `$DEV/tmp/mid_complete_20260916/ot_join10_e0/runs/b9ab9456.../original-gnc.json`
- GNC source anchors: `src/gnc/ship_guidance/src/ship_guidance_node.cpp`
  (`[EXTERNAL TURN SPEED]`, `[DENSE TURN PREDECEL]`, `[前瞻规划]` turn
  tables, `[Fix-C v2]` 300 m min-upcoming window) at GNC main `4dcfedd`.
