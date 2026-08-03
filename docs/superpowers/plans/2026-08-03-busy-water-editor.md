# Busy-Water Scenario Generation and Editing Plan

> Date: 2026-08-03
> Branch: `codex/busy-water-editor`
> Base: `main@d27d16b`
> Status: implemented and validated

## Goal

Replace the current lane-fill busy-water fixtures with deterministic traffic
around Ship0's nominal route. Targets must follow editable two-point shuttle
routes at constant speed, produce a crossing-dominant encounter mix, remain
traceable by seed, and support save/reload before a real simulation session.

This is an experimental scenario-authoring workflow. Making an algorithm
selectable does not promote its capability grade or prove global fleet safety.

## Frozen Defaults

- target count: 15 for the acceptance profile, configurable from 3 to 79;
- seed: `20250731`, configurable and persisted;
- encounter mix: crossing 60%, head-on 20%, overtaking 20%;
- crossing roles alternate give-way and stand-on;
- overtaking roles alternate ownship-overtaking and ownship-overtaken;
- target motion: constant speed between two waypoints with reflected overshoot;
- simulation duration: 600 seconds;
- selectable experimental algorithms: Nominal, VO, SB-MPC and COLREG fan MPC;
- tracker: God tracker for the authoring and comparison workflow.

Integer encounter counts use largest-remainder allocation. A fixed seed breaks
ties and controls route placement, so the normalized scenario document is
repeatable.

## Implementation Tasks

1. Rework `experiment.busy_water` into a parameterized deterministic generator.
   Generate route-adjacent target segments, planned nominal encounter times and
   role-balanced traffic. Keep committed 16/80 fixtures reproducible.
2. Add a scripted two-waypoint shuttle integrator to `Simulator`. Reflect excess
   distance at endpoints, update course on reversal and preserve configured
   speed. Do not give scripted targets autonomous collision avoidance.
3. Add a validated scenario override to `RunSpec` so generated and edited
   documents enter the same runner, manifest, hash and evidence path as files.
4. Add busy-water generate, preflight, draft-list, draft-load and draft-save API
   endpoints. Store user drafts below ignored `runs/scenario_drafts`; sanitize
   names and revalidate every loaded document.
5. Include initial ship truth and target shuttle routes in CREATED telemetry so
   every configured target is visible before the simulation starts.
6. Expand experimental capability tuples for Nominal, VO, SB-MPC and COLREG fan
   MPC without changing their verified G3 matrices or the G2 scenario grade.
7. Add a compact map setup dialog for count, seed and encounter ratios. Add a
   target editor for speed and both route endpoints, including map-point pick
   mode. Applying an edit recreates a paused session from the complete override.
8. Save and load complete normalized scenario documents. Display draft identity
   separately from the base capability scenario.
9. Add generator, shuttle-motion, override, API, capability and frontend-contract
   tests. Run targeted Ruff, JavaScript syntax, full pytest and diff checks.
10. After clean validation, merge locally into `main`, restart only the main
    checkout on 8010, and prove a generated session plus a saved/reloaded draft.

## Acceptance Boundaries

- Every target route endpoint and complete segment must pass ENC/navigation
  checks; initial hulls must not overlap.
- Generated counts must sum exactly and follow the configured mix.
- The same seed and settings must produce the same canonical document.
- Manual edits must never mutate a running session silently.
- Requested/executed algorithm identity and fallback evidence remain mandatory.
- Ship0 safety and global target-target events remain separate reports.
- No claim of paper numerical reproduction or legal COLREG compliance is made.
