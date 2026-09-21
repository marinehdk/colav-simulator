# Spec: CR_PS crossing completion (past-and-clear release for the stand-on side)

## Background (evidence: runs/loop_analysis/6e4d4ccb, 2026-09-04)

FCB45 head_on + VO: after the correct starboard avoidance turn the ownship
draws a full portward circle (recovery-window gross sweep 442 deg, net
-360 deg, XTE +423 -> -274 m) before re-acquiring the route at ~CPA+210 s.
Frame forensics:

- t=230..355 `stand_on_hold_active=True` with `driving_rule=CR_PS`; the
  selected heading freezes to the current velocity cell and then drifts
  with the residual turn rate (ROT ~ -1 deg/s): 25.3 -> 241.9 deg. This is
  the circle.
- The dynamics-clearance tube is NOT the blocker: hard-mask count decays
  963 (t=200) -> 0 (t=320); from t=320 all 4096 candidates are feasible and
  the hold is pure freeze.
- CR_PS persists because `_update_crossing_completion` gates on
  `CR_SS not in previous_rules -> return False`: the stand-on side
  (CR_PS, own keeps course per Rule 17) has no passed/completion path at
  all. The t~355 release was accidental (own heading drifted until
  |heading_delta| < rule_heading_tolerance broke the crossing window).

## Change (single mechanism, no parameter tuning)

`VO._update_crossing_completion` learns the CR_PS branch, mirroring the
existing CR_SS passed-predicate on the own ship's beam frame:

- Applies when CR_PS (and not CR_SS) is in the target's previous rules.
- passed_candidate = tcpa <= 0 AND target abaft the own beam
  ((p_do - p_os) . u_os <= 0, u_os from the own velocity when speed > 0)
  AND distance >= crossing_passed_distance_m AND distance >= previous - 1e-9.
- Confirmation: crossing_confirmation_steps consecutive ticks (same as
  CR_SS) -> target joins `_completed_crossing_targets`, CR_PS is discarded
  from `_active_rules` and `_rule_memory` (mirrors CR_SS cleanup).
- Own speed ~ 0 (no beam frame): no completion that tick.
- CR_SS branch and its semantics unchanged; approaching encounters
  (tcpa > 0) never complete, so correct stand-on hold is untouched.

## Acceptance gates

1. Unit (tests/test_kuwata_vo_paper_reconstruction.py): post-CPA port
   quarter geometry releases CR_PS and the hold after confirmation steps;
   approaching geometry keeps the hold (existing risky-hold test stays).
2. GUI-path E2E (tests/test_gui_product_spacing_profile.py): the xfail
   circling gate flips to passing (recovery gross sweep < 360 deg); on
   xpass the mark is removed and the gate becomes hard.
3. Encounter spacing unchanged: acceptance-matrix head_on/VO cell keeps
   min centre distance >= 180 m (pre-CPA geometry untouched).
4. No cross-scenario regression: nine-grid matrix, legacy VO closed-loop
   tests, and legacy G6 baseline stay green.
