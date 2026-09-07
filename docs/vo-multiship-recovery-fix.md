# VO three-target recovery and 300 s trail repair

Baseline: `597470f`; scenario `paper_ccta2023_multiship`, seed 0,
FCB45 3DOF plant + pass-through guidance + FCB45 PID + ideal actuation +
calm water. The scenario has one ownship and three staged targets (OT, CS,
HO). Its original route, speeds, timestep 0.1 s and termination conditions
are retained. This is a local simulator repair, not paper reproduction or
external-platform acceptance.

The first-corner problem was not simply a short LOS lookahead. At 239 s,
the ownship was about 287 m inside the turn, still 616 m east of the
northbound leg. The incoming-leg LOS commanded a southwest correction
back toward WPT2, then switched to north only after crossing the corner
plane. VO had intentionally disengaged its overtaking heading commitment
through `separated_without_pass`; the canonical Rule 13 responsibility
was still committed. Those states are distinct.

The VO wrapper now opts into adjacent-leg recovery after its maneuver
commitment ends. LOS advances one segment only when cross-track deviation
exceeds its configured lookahead, the vessel lies inside the next turn,
its projection is within the outgoing leg, and the incoming LOS would turn
away while the outgoing LOS permits a forward turn in the route direction.
The full mission route is retained, progress never rewinds, and all VO
collision/static-hazard checks still apply to the new reference. Ordinary
LOS callers and ordinary waypoint passage retain their existing behavior.
Regression coverage includes translated fixture geometry, rotations,
mirrored turns, ordinary tracking, outside-turn and beyond-segment cases,
and ongoing avoidance commitments.

For HO, active-rule qualification used entry into the preferred ship domain,
while the heading lock waited for centre CPA to enter the horizon. The
scenario therefore had an active HO rule at TCPA ~83 s and domain entry
~55 s with a 60 s horizon, but no HO lock. Its own avoidance turn changed
raw geometry into CR_PS, replacing the responsibility and driving severe
speed reduction. Lock entry now accepts the same approaching domain-risk
evidence as activation. A locked HO remains HO until its existing release
conditions hold; instantaneous maneuver-induced geometry does not replace
it. An already established CS give-way rule likewise cannot acquire a new
HO lock because of its own right turn. A recorded pre-CS input also exposed
WVO soft TTC costs beyond the configured planning horizon: they commanded
an 11-degree port alteration before the crossing rule activated, followed
by a forced starboard reversal. The pre-activation WVO soft cost is now bounded to that target's configured
horizon for a new CS approach. Static-hazard costs, established duties,
other encounter types and post-encounter recovery retain their full forecasts;
the hard safety masks and uncertainty geometry are unchanged. These are duty-continuity fixes;
no separation threshold or fallback gate was relaxed.

The trail discrepancy was fixed-point retention: 500 frames covered only
49.9 s at dt=0.1 s, versus 249.5 s at dt=0.5 s. Retention is now
`ceil(300 / dt) + 1` samples for every vessel, covering at least 300 s
independently of scenario timestep. Publication still samples the complete
retained span down to at most 120 points and preserves endpoints, so network
payload size is unchanged. History naturally covers only elapsed time for
sessions younger than 300 s; stationary vessels have stationary trails.

Diagnostic alternatives were rejected rather than shipped: extending every
OT heading commitment until a longitudinal pass postponed the corner turn
and did not address wrong-leg recovery. Allowing a new HO lock during an
existing CS maneuver caused rule relaxation in a full run; the CS continuity
regression identified and prevented that interaction.

New failing regressions were run before their fixes: corner recovery
(three rotated cases), HO domain activation, CS-to-HO responsibility
replacement, and 300 s retention. The end-to-end regression runs the
original GUI specification to its natural goal, checking all three
encounters, no southwest WPT2 chase, no large west-side overshoot, HO lock
and speed, target abaft the beam at both planner and displayed releases,
and no fallback, emergency rule relaxation, collision or grounding.

Local diagnostic artifacts and before/after traces are retained under
`tmp/debug_vo_multiship/`. Production code contains no debug instrumentation.

## Final verification

- Unit and transport: **96 passed** (`final_unit.log`).
- Single encounters, static hazards, GUI defaults, planner audit and FCB45 VO
  matrix: **46 passed, 6 unrelated matrix cells deselected** (`final_regression.log`).
- Original three-target GUI session: **1 passed** in 214.89 s
  (`multiship_final.log`). No scenario override or shortened time limit.
- Ruff and `git diff --check`: passed. Full repository suite not run.

The final three-target run reached its natural goal at **1387.6 s**, with
minimum ownship-target centre distance **226.91 m**, no collisions or
grounding events, no fallback, and **zero** emergency rule-relaxation solves.
HO locking ran from approximately **1047.8–1135.8 s**; minimum surge during
that phase was **11.02 kn**. At the first unlocked solve TS3 was **49.5 m
abaft the ownship beam**; at the displayed release around **1211.9 s**, it
was approximately **321.8 m abaft**. The full-frame integration assertions
also verify those signs, not just rounded sampled metrics.

The final red-to-green checks include the exact 239 s corner geometry,
pre-CS wrong-port input at ~648.6 s, active HO without a lock, and wrong HO
promotion during an existing CS. A global truncation of all far-TTC costs
was rejected because it regressed static-hazard behavior and single OT
clearance; the final change is per-target and limited to new CS anticipation.

Local evidence: `tmp/debug_vo_multiship/metrics.json`, `final_rows.json`,
`final_summary.json`, `comparison.png`, and the three final test logs above.
The baseline and rejected trial artifacts remain in that clearly marked
diagnostic directory. Production files contain no `[DEBUG-...]` logging.
