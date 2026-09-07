# VO overtaking recovery repair — 2026-09-07

The shipped OT scenario with VO, pass-through guidance, FCB45 marine PID,
FCB45 3DOF plant, ideal generalized-force actuation and calm water crossed
its mission route and made a large U-shaped recovery. The fix removes the
spurious stand-on hold and calibrates the existing nominal LOS configuration
for the FCB45 response. No avoidance-distance thresholds, scenario geometry,
PID gains, plant dynamics or evaluator gates were reduced or replaced.

Baseline: `50850cd`, including prior overtaking fix `1b3d978`.
The listener on port 8010 was verified to run this checkout.
GUI configuration was verified through `/api/sessions/current`; its VO
parameters matched `config/acceptance_issue67_vo.yaml`.

| Metric, shipped 600 s OT | Before | Final |
| --- | ---: | ---: |
| Minimum sampled ownship-target centre distance | 420.33 m | 422.26 m |
| Maximum excursion on the opposite side of the route | 408.60 m | 4.34 m |
| Maximum absolute XTE in final 30 s | 81.50 m | 4.89 m |
| Maximum course error in final 30 s | 63.06 deg | 0.085 deg |
| Fallback count | 0 | 0 |

Both full runs were collision-free and grounding-free under the existing
continuous collision / grounding checks. These are this tuple's local
simulator results, not full-repository or external-platform acceptance.
The avoidance excursion on the passing side remains about 580 m; the repair
addresses recovery across the route, not reduction of the passing corridor.

## Reproduction and root cause

`tests/test_kuwata_vo_paper_reconstruction.py -k safe_port_crossing_geometry`
was red before the fix: `1 failed, 1 passed, 68 deselected in 1.36s`.
The failure was `assert not debug["stand_on_hold_active"]` for a single target.
Adding an irrelevant distant target made it pass, exposing the target-count
exception in the hold condition. The fixture was minimized from the real
460 s planning input: one ownship, one target, one reference, no ENC,
no PID, and no accumulated encounter history. Fresh VO reproduced the lock.

At 460 s the ship had already crossed the route (XTE -45.53 m), while LOS
requested 85.36 degrees. The requested velocity was feasible, no crossing
rule was active, and preferred-domain risk eligibility was false. Nevertheless,
raw `CR_PS` geometry caused a hold at the current velocity grid cell
(-42.19 degrees). This persisted until the geometry changed through continued
motion. LOS was pointing to the correct side; the solver's stand-on selection
prevented it from taking effect.

The final hold rule retains active stand-on responsibility and conservative
holding when a geometry-matched crossing has an unsafe requested velocity.
It does not freeze a safe return command merely because a cleared target
appears on the port side. Existing hard masks still gate all selected actions.
A narrower unsafe-reference regression also checks that the conservative
hold remains available.

Removing geometry-based holding entirely was rejected: the double-VO head-on
fixture changed from accepted to a sustained course-tracking failure (20
consecutive violations versus 8 on baseline). The final reference-safety
condition restored that regression. This distinction is intentional.

The remaining overshoot came from the VO wrapper's nominal LOS, upstream
of the selected pass-through guidance: defaults were `K_p=0.02` (50 m
lookahead) and `K_i=0.0001`. FCB45's heading-rate limit is 0.05 rad/s;
at 8 m/s the corresponding radius is about 160 m. The existing profile
now uses `K_p=0.005` (200 m lookahead) and `K_i=0` for calm water.
This flattens the requested intercept before route arrival and avoids
accumulating a persistent-disturbance correction during a temporary detour.

One-variable checks: hold repair alone still overshot 47.2 m and reduced
minimum separation to 362.3 m; 200 m lookahead with the old integral left
about 13.2 m reverse excursion and residual heading oscillation. Disabling
the integral at that same lookahead produced the final settled trajectory.
The change is explicit profile calibration, not a paper-VO reproduction claim.
Product VO sessions without explicit algorithm configuration consume this
profile; non-calm-water convergence was not validated in this repair.

## Regression commands

```sh
.venv/bin/pytest -q tests/test_kuwata_vo_paper_reconstruction.py tests/test_kuwata_vo_regression.py
.venv/bin/pytest -q tests/test_kuwata_vo_closed_loop.py tests/test_kuwata_vo_static_closed_loop.py
.venv/bin/pytest -q tests/test_gui_product_spacing_profile.py tests/test_acceptance_spacing_profiles.py tests/test_gnc_stack_api.py
.venv/bin/pytest -q tests/test_gnc_acceptance_matrix.py -k 'not matrix_cell or vo'
.venv/bin/ruff check colav_simulator/core/colav/kuwata_vo_alg/kuwata_vo.py tests/test_kuwata_vo_paper_reconstruction.py tests/test_gui_product_spacing_profile.py
git diff --check
```

The new GUI regression requires a full 600 s run, at least 400 m encounter
separation, at most 50 m opposite-side overshoot, and at most 10 m XTE / 5 deg
heading error throughout the final 30 s. This catches both the original U
and the insufficient hold-only repair. The previous end-state-only and
CPA+240 s windows did not adequately lock down the entire recovery behavior.

Local diagnostic scripts, red outputs, differential traces and the plotted
comparison are retained under `tmp/debug_vo_recovery/`. No temporary
instrumentation was added to production code. During diagnosis, the user's
paused session was left untouched. After testing, the user explicitly
authorized reloading port 8010 and committing the repair to main.

Final verification: **118 distinct relevant cases passed** after rerunning the
corrected new fixture. The combined run finished with 117 passed and one new
fixture-construction failure: the fixture had set hard clearance to 182 m but
omitted the required preferred clearance >=182 m. Setting its preferred
clearance to 190 m fixed the fixture; the complete unit group then passed
81/81, and `--lf` across the original combined selection passed the remaining
case. The other 37 cases cover VO closed loops (including double-VO HO),
static hazards, GUI/default-profile/API contracts and the FCB45 VO matrix.
The strengthened full-duration GUI OT test was independently rerun: 1 passed.
Ruff and `git diff --check` passed. No full-repository run was claimed.

Evidence logs: `tmp/debug_vo_recovery/final_tests.log`, `final_unit.log`,
`final_rerun.log`, `final_ot_gui.log`; measured comparisons:
`comparison_metrics.json`, `comparison.png`, `baseline_rows.json`,
`final_rows.json`, and `final_summary.json` in the same directory.
