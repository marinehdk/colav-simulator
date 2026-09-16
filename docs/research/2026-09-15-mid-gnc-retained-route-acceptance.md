# Mid-MPC + GNC: retained-route integration and OT acceptance

Status: **NOT ACCEPTED — awaiting recovery-search configuration decision. Not deployed to 8010.**

## Agreed boundaries

- Mid owns route planning; GNC owns guidance, control, actuators, hydrodynamics and environment.
- Preserve GNC route update admission. Compile the retained near segment before optimization; the adapter must not splice or reshape an accepted route afterward.
- Use the common simulator arrival radius, seven ownship lengths (308.7 m for this GNC vessel). Report exact stopping separately. The generic Mid 5 m / 0.05 m/s predicate remains available, but does not override the shared GNC simulator arrival policy.
- No GNC control, actuator, hydrodynamic or environmental source modifications.
- Keep numerical, physical-safety, COLREG action deadlines and recovery checks. No fallback solver or forced PASS.

## Original failure and evidence

Original 8010 run: `e197f279-7bf1-4bf8-9e27-69549d1f3765`, OT, environment ON, failure at 35 s.

The original IPOPT result was numerically feasible; L4 rejected it with `SAFETY_SWEPT_CLEARANCE` and `QUALITY_CPA_RELEASE`. Its hard CPA window ended at knot 49 of 80, allowing an unsafe recovery suffix. Frozen artifact `e2be73fd1adcd1c0d18336af54410a4db0382277359e4a1fb34542e83104d535` predicts minimum hull clearance **126.08798 m**, below the 180 m gate. Re-solving that frozen problem with the hard window retained to knot 80 gives **707.513 m** clearance. MASS_PARITY remains unchanged.

This was followed by real integration defects, rather than a need to weaken GNC:

1. The old adapter changed native Mid geometry after acceptance and flattened waypoint speed metadata. Native Mid now emits a hashed execution-route packet, including the retained segment, transition and optimized suffix; transport copies it verbatim. Missing, stale, mutated or expired authority is rejected.
2. Body heading was being mixed with ground-course point-mass prediction. Native-route input now preserves world velocity while converting to COG/SOG before strict input/first-state validation.
3. Reachable RELEASED contacts were removed from physical optimization. They now remain physical constraints without changing Lifecycle duty or rearming the encounter.
4. Before OT side confirmation, an arbitrary lateral branch could make GNC turn opposite to the subsequently committed side. During the short confirmation state, publish a neutral follow/braking route along the retained tangent; lateral planning resumes after confirmation. Rate-feasible braking initial guesses supplement heading initial guesses. IPOPT and all acceptance gates still execute.
5. A minimum achieved course change used as an asymptotic guidance setpoint can miss a finite deadline. The native planning target now accounts for the already-qualified route-response time constant and retained-leg travel time. Lifecycle minimum alteration and deadlines remain unchanged.
6. Recovery geometry was staged at requested cruise speed even when GNC was executing substantially slower. Native recovery prediction now starts from measured SOG.
7. The free suffix speed floor was staged from the pre-prefix state, although the retained prefix ended slower. One environment-ON failure required about 6.5 m/s directly after a roughly 4.57 m/s prefix, exceeding the unchanged 1.5 m/s per-step limit. Suffix bounds now stage from the fixed prefix endpoint. The frozen failed NLP becomes feasible; acceleration and braking regressions cover both boundary directions.

8. An unconditional extra straight segment beyond the protected 160 m anchor removed near-shore recovery space. The frozen 1310 s failure becomes feasible after removing that unnecessary extension, with all static rows retained. Nonzero maneuver transitions still preserve their turn-radius construction.
9. Uniform-speed prefix sampling had artificial integer-horizon gaps (for example 161 m from 8 m/s). A rate-bounded ramp now reaches the same anchor without changing speed/acceleration limits. Curve arithmetic uses local coordinates.

10. Requested waypoint speeds and GNC-admitted speed limits are distinct. Preserve requested metadata for transport, while the retained-prefix forecast consumes the admitted braking limits. This avoids both false acceleration into a protected turn and command-speed ratcheting.
11. The runtime arrival predicate alone was insufficient: GNC-mode planning now uses navigation passage through the common arrival region instead of the private 5 m / 0.05 m/s braking tail. Precision references remain unchanged for their original non-GNC policy.
12. Native sailing commands consume the published steerage floor (3 m/s in this source configuration), including when the lifecycle floor yields inside CPA windows. Retained transients are still rate-staged from measured state. A transit NLP also requires enough free-suffix extent to create a GNC-admissible waypoint segment, rather than discovering that mismatch after solving.
13. New post-clearance route points carry `cruise` mode; retained current-segment metadata stays intact. This restores GNC's own cruise-recovery policy without bypassing its turn or safety limits.

The fixed prefix is a **kinematic retained-route interception forecast**, not a native GNC rollout. The calibrated response is an approximation. Full closed-loop evidence is therefore necessary.

## Bounded GNC guidance fixes

Development source: `/Users/marine/Code/.worktrees/GNC/mid-route-local-speed`, based on `b3b7b2b`.

Production changes stay within the guidance package: two node implementations. The curve-preview experiment was withdrawn and archived; its new header is not part of this change.

- `active_route_manager_node.cpp`: apply corner speed limits locally and preserve the unchanged backward braking envelope. Previously, one tight corner capped every waypoint, including a long straight outgoing leg. Independent native/ROS probes: old route `[4.1797, ... all]`; fixed profile `[8, 4.1797, 4.1799, 8, 8]`. Exact-speed requests still reject the infeasible turn.
- `ship_guidance_node.cpp`: retain crab/current compensation and cruise-recovery state when the processed local segment remains unchanged. The target index denotes segment `[idx-1, idx]`. Compare processed endpoints with a 1 micrometre numerical tolerance; actual geographic round trips changed 115/116 retained prefixes by at most 2.37 nanometres. A genuine segment change still resets state. Independent ROS regressions went from four FAILs to four PASSes: next-segment change, round-trip jitter, speed metadata update, and current-segment change. These tests also verify that 7.8 m/s cruise-recovery state is not reset to base speed by every new plan.

No control gains, plant parameters, hydrodynamics, disturbance models or route-admission thresholds were changed. The micrometre comparison above concerns floating-point identity of an unchanged local guidance frame. The source manifest comparison and independent ROS probes are retained under `tmp/mid_gnc_20260915/reference/` in the main checkout.

Current source manifest SHA256: `e701a2c64b4231a9ff9ff36ab7a7c3befdcbffff810573dc4870b1f3ca0b86da`.

Current native library SHA256: `d49a7acf86de3356b27630313b2dacf1c39333b9b86d7111c2b22ce788271999`.

Both route and velocity response calibrations were rerun against this source/build. Route course tau: 86.783916 s, trajectory R² 0.989817; speed tau: 24.067536 s, trajectory R² 0.984821. These are calibration evidence, not full algorithm acceptance.

### Onset authority correction and withdrawn preview experiment

The canonical Lifecycle defines maneuver onset as an observed course change **or** an observed speed change; prescribed course achievement is a separate latch. In the completed environment-OFF OT run, `action_started` was already true at 5 s because of the real commanded deceleration. Its course first exceeded 15 degrees at 86.5 s, before the 144.673 s achievement deadline.

The initial audit incorrectly treated course change alone as onset. L4 `AuthorityTarget` also omitted `action_started`, and therefore kept reimposing the start-course check even after canonical onset. The fix passes the existing observed latch to L4 and skips only the already-satisfied onset requirement. Locked-side, course-achievement and physical-safety checks remain unchanged. A regression verifies all four outcomes: observed onset accepted, unobserved onset rejected, insufficient course achievement rejected, and wrong-side movement rejected.

The exploratory curve-preview changes were unnecessary to resolve this contract mismatch and produced undesirable closed-loop oscillation. They were withdrawn. Their ROS sampling tests and logs remain archived for traceability, not as accepted production evidence. The source is restored **byte-for-byte to the qualified e701 guidance version** with only local speed-limit and local-state-continuity fixes.

## Runtime evidence and current limits

All runs use real IPOPT and the native GNC stack. Development runtime snapshots are stored per run under this worktree's `tmp/mid_gnc_20260915/`; solver artifacts, trajectories and source identity remain available in each run directory.

| Trial | Result | Acceptance limit |
|---|---|---|
| `aligned_goal`, run `5cb99bd6-21b3-4c3d-8ec0-fc3fdc4d9e55` | Earlier environment-ON variant arrived around 1091 s; minimum hull clearance 557.064 m; no collision/grounding/fallback | Predates later environment-OFF and prefix-boundary fixes; cannot qualify current code |
| `response_e0`, run `c12c3e6f-14a6-47ab-be7d-43dd40a41d4a` | Completed default 1200 s; minimum hull clearance 690.649 m; no collision/grounding/fallback | Did not reach goal; FINISHED/evaluator PASS alone is insufficient |
| `actual_speed_e0` | Completed 1200 s safely; last-frame goal distance 749.007 m; final mission XTE 650.270 m; ownship ahead of target by 644.138 m | Default-duration arrival not passed |
| `actual_speed_e0_extended`, run `61643851-b804-40dc-a078-cdf0a1dc1baa` | Diagnostic duration set to 1800 s; shared arrival at **1357 s**, goal distance **308.162 m**, SOG **3.20049 m/s** | Precision stopping not passed; default 1200 s arrival not passed; predates latest suffix-speed-boundary fix |
| `actual_speed_e4`, run `39fc6a87-2473-4d2c-814d-8a6c32731f5a` | Revealed retained-prefix/free-suffix speed conflict around 575 s | Regression input, not accepted |
| `boundary_e4`, run `c8ba2911-8968-490f-99c3-0187ba8c833d` | Completed 1200 s; minimum hull clearance 739.851 m; zero collision/grounding/fallback; goal distance 1096.03 m | Arrival not passed |
| `boundary_e4_extended`, run `490ddd94-bf21-4239-9694-41433f731aa5` | Extended diagnostic failed around 1355 s; frozen 1310 s NLP identifies the extra-prefix/static-space conflict | Regression input, not accepted |
| `neutral_course_e4` / `neutral_course_e0` | Exposed interpolation feasibility gaps during recovery | Frozen regression inputs, not accepted |
| `guidance_v2_e4`, run `44d4b77e-b3f9-484a-9b87-496ea0cbe548` | Arrived 1291 s; minimum hull clearance 601.615 m; zero collision/grounding/fallback; actual onset 2.124 degrees at 24.365 s | Default 1200 s deadline not passed; precision stop not passed |
| `guidance_v2_e0`, run `fa1126f3-fa5c-4dd1-a32d-da26115257d5` | Arrived 1363 s; minimum hull clearance 518.722 m; zero collision/grounding/fallback | Course-only onset audit was incomplete: canonical speed-based onset was true at 5 s; prescribed 15 degree course achieved at 86.5 s. Final L4 propagation regression pending full rerun |

The user has been asked whether 1200 s is an acceptance deadline or only a configurable simulation limit. Production scenario duration has not changed. Extended diagnostic results must not be reported as default-duration passes.

## Verification status

Current v2 integrated focused suite: **305 passed**. Source-manifest comparison confirms that only the two guidance source files above differ from the authority baseline. Route and velocity calibrations were freshly rerun for v2; all four measured trajectory R² values exceed 0.9.

- Focused Mid/transport/arrival suite: **197 passed** after the confirmation-course and near-shore prefix fixes.
- Current retained-route regressions: **16 passed**; real solves must return CONVERGED or FEASIBLE_NONOPTIMAL as well as satisfy the hard rows. Cases include acceleration/braking boundaries, neutral confirmation, and the frozen near-shore failure.
- Native admission tests updated to the explicitly agreed planner-owned route contract: 16 passed. The old silent adapter-splice/hold expectation is replaced with rejection of raw receipts lacking a compiled route.
- Broader native suite: **95 passed** after updating the three obsolete adapter-splice expectations. The latest prefix-geometry version is being rerun against this suite.
- Existing Ruff findings in legacy solver/assembler/adapter code remain separate from runtime acceptance. Do not report repository-wide lint or full tests green.
- Historical P1 multiship test also fails its unchanged baseline with `COLREG_ACTION_DEADLINE`; it is not the user's previously accepted three-ship scenario.

## Recovery-completion follow-up

The shared arrival circle is not a substitute for mission-leg recovery. The initial navigation reference aimed directly at the final waypoint and entered the circle while still about 260 m off the leg. Native navigation references now capture the mission leg before final approach, while retaining cruising speed and all safety checks.

This exposed a lifecycle interface gap: the recovery guard was cleared when heading momentarily crossed the mission bearing, despite large lateral displacement. The same OT target was then reclassified as a new crossing stand-on/give-way obligation during the ongoing return. An optional actual route-recovery confirmation now keeps the original guard until the vessel is back within the existing 20 m mission-leg acceptance corridor; the existing heading condition also remains. Only the native Mid path supplies this confirmation. Other planners retain their previous cycle behavior. Reachable released targets continue to receive full-horizon physical constraints, so this does not hide a collision risk.

Regression: the guard remains with heading aligned but recovery confirmation false, and releases after confirmation true. Lifecycle/arrival/retained-route/authority focused checks: 80 passed. Fresh closed-loop recovery checks remain pending.

## Remaining work

1. Finish current environment-ON closed loop; repeat environment-OFF on final frozen code with the agreed time policy.
2. Report physical clearance, actual overtaking lead, return-path progress, shared arrival and precision stopping separately.
3. Run the required additional encounter / actual user three-ship checks before claiming general Mid acceptance.
4. Preserve unrelated main-checkout changes. No source promotion, commit, or 8010 restart has happened for this development series.
5. Replay UI and missing business logic remain deferred until Mid acceptance.


## Latest checkpoint

- Current focused integration tests: **355 passed**. New retained-route modules and focused regression files pass Ruff; repository-wide Ruff is not claimed clean.
- Actual GNC source remains the qualified e701 version. The source-preview experiment is withdrawn. Control/hydrodynamics/environment sources remain unchanged.
- `aligned_contract_e0`, run `30cc7733-ffa8-411d-b67d-7840cb406439`: recovery solve failure around 1215 s. The original +/-45 degree numerical heading window did not yield a feasible candidate. Frozen wider-search diagnostic satisfies the unchanged primal constraints and the recovery-progress filter. Full L4/native execution of that experiment is not yet verified.
- `aligned_contract_e4`, run `54631109-f30a-44ca-9e31-f3fa054ade08`: recovery remained unaccepted, failing around 1565 s.
- Actual user three-ship scenario `paper_ccta2023_multiship`, run `2a80ba6d-1178-49fd-8fd0-6f50e7c97465`: progressed beyond the former ~610 s failure after correcting the lateral metric, but failed near 1740 s because the retained route could no longer be reached inside the active motion envelope. The late actual yaw/sway behavior also needs investigation. This is not a passing three-ship result.
- No background simulation remains active. No commits, source promotion, 8010 restart or replay-UI changes were performed.

Pending user decisions: whether +/-45 degrees is mandatory throughout recovery, and whether the default 1200 s OT simulation limit is a mission deadline. Neither production setting has been changed.

The wider-search evidence is in `evidence/mid-gnc-retained-route-20260915/recovery-search-proposal.json`. It is a diagnostic proposal, not permission to weaken collision, COLREG, yaw-rate, acceleration or GNC admission checks.


Formatting/lint checkpoint: `git diff --check` passes. New retained-route and focused native-regression files pass Ruff. Full changed-file Ruff check and whole-file format check remain non-green (legacy long functions/docstrings plus expanded validation complexity); exact logs are in the main checkout's `tmp/mid_gnc_20260915/final-ruff-check.log` and `final-ruff-format.log`. Changed hunks were range-formatted without broad unrelated reformatting. This is another reason not to label the branch ready to merge.

### 2026-09-16 recovery-window authorization checkpoint

The user authorized widening the numerical heading search only during native post-encounter recovery. The implementation uses a 90 degree recovery envelope; active encounter bounds remain 45 degrees. Collision/CPA, COLREG, yaw-rate, acceleration, static-field, retained-route and GNC admission rows are unchanged. Seed repair now searches the declared recovery envelope and combines heading offsets with braking profiles. Retained-prefix compilation can extend the planner-owned anchor in route order when the first protected anchor is kinematically infeasible; it does not splice or reshape the route after solving.

Focused verification after these changes: **356 passed**. No GNC control, hydrodynamics, actuator or environment source was changed in this checkpoint. No source promotion, commit, 8010 restart or UI work was performed.

The final native environment-OFF OT replay with the authoritative v2 GNC library (`recovery90_e0_seed`, run `4d7a28a2-41fc-4bc4-b272-db587c57ea48`) no longer stops at the earlier T1215 optimizer failure and runs to T1599.5. It then grounds while the unresolved late recovery plans are being held; shared arrival was not reached (goal distance **663.114 m**, arrival radius **308.7 m**). Frozen T1295–T1320 artifacts now solve with feasible seeds after the recovery-envelope repair, but the later route/GNC recovery remains unaccepted. This is diagnostic evidence, not a Mid-MPC pass.

The remaining boundary is a GNC guidance/route execution alignment issue: around T1575 the route status has advanced to the current segment while the observed guidance path remains on an earlier bend, leaving about 55 m cross-track before the late grounding. The exact GNC guidance fix still needs an independently rebuilt, source-identity-qualified native library and a fresh full replay; the current qualified library remains deployed only in the development harness.
