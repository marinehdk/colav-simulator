# Threat-card lifecycle repair — 2026-09-07

Baseline: `eba2526b`. Scope: canonical Threat Management state, VO execution
observations feeding that state, and the event-list presentation. No VO cost,
constraint, guidance, PID or plant parameters were changed.

## Reproduction

A captured, real 600 s GUI OT session reproduced the screenshots. Replaying
its immutable `EncounterCycle` inputs took 1.47 s and failed these assertions:
actual avoidance at 100 s must be HIGH, and safe recovery at 545 s must be
CLEAR. Before the repair the card remained LOW through 326 s, became HIGH
around 362.5 s during recovery, and stayed HIGH through the end.

## Causes and changes

1. The card used `action_achieved` (the prescribed maneuver's amplitude and
   direction) as if it meant action had started. The canonical OT recommendation
   chose PORT, while VO actually passed to STARBOARD. Its return turn was the
   first movement that satisfied that recommendation, producing the late red.
   `action_started` is now independent, latched from observed motion. The
   existing `action_achieved` remains separate quality evidence.
2. Physical release was gated by prescribed action achievement, and OT passage
   required the recommended side. Release now checks actual passing clearance
   on either side, separation, uncertainty and safe return conditions. It does
   not require a prescribed maneuver to have succeeded. Stand-on vessels can
   also release when the other vessel has passed safely without ownship acting.
3. Ordinary route turns must not count as avoidance of unrelated future targets.
   The baseline cycle now carries optional target-key-bound execution intent.
   With explicit intent, motion is measured from when that intent was first
   observed, not from an old course before an ordinary route turn. Merely
   publishing intent does not turn the card red.
4. VO's stand-on/overtaken maneuvers can include speed changes. They are recognized
   when the driving target has a nominal-reference domain conflict inside the
   planner's horizon and the selected velocity departs from nominal. The
   per-target conflict check prevents CS recovery from being attributed to a
   distant future TS3 merely because it became the VO focus.
5. The baseline recovery check used current evasive course/speed as its route
   reference. It now uses VO's actual nominal LOS velocity, so turning away
   cannot by itself prove that returning to the mission route is safe. The
   current-motion prediction remains separately identified as CURRENT_MOTION_BASELINE.
6. For non-OT cases the entry to PAST_CLEAR now uses the same clearance as its
   confirmation. The previous weaker entry condition caused red/green flicker
   in the stand-on case. No clearance threshold was lowered.
7. The event formatter treated every string containing COMMITTED as AVOIDING,
   including PAST_CLEAR/COMMITTED. It now checks clearance first and uses the
   canonical display class to distinguish monitoring from observed avoidance.

The monitor-grade onset defaults are 3 degrees of observed heading response
(or the smaller required angle), or 0.25 m/s of observed speed change. Once
started, the red state remains latched until physical clearance; steady
avoidance heading or a larger DCPA does not demote it to yellow. Unknown
observations remain UNKNOWN. Motion thresholds are engineering parameters,
not claimed COLREG statutory limits.

VO supplies read-only nominal-velocity, planning-horizon and per-target
nominal-domain-entry diagnostics. These identify intent, not release or color.
The coordinator remains the single owner of state and color. Current and
nominal TTC diagnostics share one batched call; the existing five-call test
passes, and 100 scalar-versus-batched samples were bit-identical.

## Verified state sequence

Times below are the first observed card-state changes. Green starts at
PAST_CLEAR once physical release/return conditions hold; RELEASED follows
its existing confirmation interval.

| GUI case | First red (s) | First green (s) |
| --- | ---: | ---: |
| Single OT | 48.5 | 320.5 |
| Three-target OT / TS1 | 8.1 | 336.1 |
| Single HO | 133.5 | 242.5 |
| Single give-way CS | 63.5 | 149.5 |
| Single stand-on crossing | 64.5 | 179.5 |
| Overtaken, extended observation | 116.5 | 600.5 |

Single OT is therefore green at 326 s, 367 s and 545 s. In the three-target
scene at 253 s, ownship is still about 27.6 m behind along the target's course;
starting route recovery does not establish full passage. The card correctly
remains red until the actual release conditions hold, but is already red
from 8.1 s rather than first turning red during recovery.

Future TS2/TS3 are not colored as avoiding during earlier route turns. TS2
first turns red at 667.3 s and green at 761.9 s; TS3 at 1051.3 s and 1201.5 s.
The overtaken scene's default 600 s horizon ends just before its dynamic
clearance requirement is met. A validation-only extension to 700 s confirmed
normal green at 600.5 s; the shipped scenario duration was not changed.

## Evidence and validation

- Final core/lifecycle/baseline/VO diagnostic tests: **221 passed**.
- Full GUI OT/HO and three-target runtime regressions: **4 passed**.
- Frontend suite, including functional event presentation: **248 passed**.
- Additional VO/transport regression run: **112 passed** (overlaps the core
  run's 85 VO reconstruction tests; counts must not be added without deduplication).
- Ruff, Node syntax and `git diff --check`: checked separately.
- Single OT motion parity: all **2400 vessel/frame rows** (ownship plus target)
  match baseline exactly for position, heading, surge, sway and yaw rate.
- Full repository and external-platform acceptance were not run.

Local artifacts: `tmp/debug_threat_cards/runtime_colors.json`, `comparison.png`,
`motion_parity.txt`, immutable cycle captures, red regression outputs,
`final_core.log`, `final_runtime.log`, `web_full.log`, and `final_vo.log`.
No debug instrumentation was added to production code.
