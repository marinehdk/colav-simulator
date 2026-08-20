# C4 — ENC Situation Display Implementation Notes (2026-08-19)

Work order: `C4-WORKORDER-20260819.md`. All milestones M1–M5 executed in the
worktree `mass-openbridge-ui` (branch `codex/mass-openbridge-ui`). No commits
made; nothing under `.codegraph/` or `docs/ui/` staged.

## What moved where

- `web_gui/modules/situation-display.js` (NEW, ~1750 lines): the ENC situation
  canvas extracted from `app.js`. Rendering internals relocated near-verbatim;
  the module additionally owns view state (ruling 3/4 `userAdjusted` resize
  semantics), ENC loading with the C2 generation guards, layer state (ruling 6),
  hit-testing/selection + click modes (ruling 7), the telemetry
  interpolation/rAF pipeline (moved out of app.js per M3 preference), the
  mission-route freeze Map, planner-surface-on-map (VO fan + MPC fan), and the
  canvas palette (ruling 10 / M5).
- `web_gui/app.js` (3688 → ~2305 lines): now the Deployment adapter. Keeps the
  planner surface panel (`plannerSurface` canvas + VO decision-space fetch),
  target-edit panel, busy-water tools, catalogs, event log, boot.
- `web_gui/modules/config-shell.js`: `renderScenarioOverlay` +
  `scenario?.overlay_geometry` deleted (ruling 1). New
  `renderScenarioPreviewCanvas` is the second adapter on the same seam
  (ruling 9): static, ENC-less grid frame only — no geometry invented, visual
  contract (frame colors/labels) unchanged. No session lifecycle is ever
  started on this instance (`fetchInfo` stub never called because
  `beginSession` is never invoked).
- `web_gui/index.html`: overlay `<svg>` + markers `<div>` replaced by
  `<canvas id="validationScenarioOverlayCanvas">`; `?v=` cache-bust bumped on
  style.css / app.js / config-shell.js to `20260819-c4-situation`.
- `web_gui/style.css`: `--situation-*` token sheet added to `:root` with the
  pre-C4 hardcoded values; dead overlay/vessel-marker CSS removed; new
  `.scenario-preview-canvas` rule (token-only, keeps the Config CSS slice
  hex-free).

## Public seam (createSituationDisplay options + methods)

Options: `canvas`, `wrapper`, `fetchInfo`, `fetchTile`, `createImage`, `now`,
`raf`, `cancelRaf`, `getResponseRange`, `getScenarioId`, `getPlannerSurface`,
`onEncStatus`, `onLog`, `onLayerStateChange`, `onSelectionChange`.
`fetchInfo` may return either a Response-like or a pre-parsed info object.

Methods (work-order API + minimal additions): `render(snapshot)`,
`beginSession(runId)`, `clearSession()`, `setLayerVisible(id, v)`,
`getLayerState()`, `onLayerStateChange(cb)`, `setClickMode(mode|null)`,
`onSelectionChange(cb)`, `selectTarget(id)`, `fitView()`, `zoomIn()`,
`zoomOut()`, `zoomAt(x, y, f)`, `setEncVisible(v)`, `isEncVisible()`,
`setPlannerSurfaceAttached(v)`, `isPlannerSurfaceAttached()`,
`refreshPalette()`, `getPalette()`, `resize()`, `rerender()`, `destroy()`,
plus transform/test accessors (`worldToCanvas`, `utmToCanvas`, `canvasToUtm`,
`getViewScale`, `getPan`, `getDrawSequence`, `getEncStatus`, `getEncInfo`,
`handleClickAt`).

Pure exports: `interpolateTelemetry`, `telemetryRenderDurationMs`,
`validRoute`, `chooseGridSpacing(worldWidth)`, `clampZoomScale`,
`updateFrozenRoute(store, data)`, `targetsForDisplay`, `plannerSurfaceType`,
`wrapRadians`, `voCandidateColor`, `drawVelocityArrow`,
`simplifiedMpcFanGeometry`, `hexToRgba`, `THREAT_STYLES`, `LAYER_ORDER`,
`TELEMETRY_RENDER_MIN_MS/MAX_MS`.

Render-order contract: `LAYER_ORDER` is the single ordered table; every draw
pass records actually-drawn ids, exposed via `getDrawSequence()` (ruling 8 —
deterministic call-trace regression, no pixel diff).

## Rulings implemented

1. overlay_geometry block deleted; no seam interface reserved. ✔
2. Data boundary as specified; `telemetry-projection.js` untouched (zero diff). ✔
3. View state internal, survives workface switches, refits on
   `beginSession`/ENC load. ✔
4. `userAdjusted` flag set on first wheel/drag; resize refits only while
   unset; `fitView()` clears it. ✔
5. No keyboard handlers added. ✔
6. Layer ids/defaults/visibility module-owned; availability still derived per
   render and emitted through `onLayerStateChange` (app.js syncs the
   checkboxes/legend DOM). ✔
7. Click modes mutually exclusive with selection; host receives UTM
   `{north, east}` (app converts to WGS84 via `/api/coordinates/to-wgs84`). ✔
8. See LAYER_ORDER above. ✔
9. Config preview canvas adapter replaces the SVG; `config-shell-static`
   gap-#12 assertions rewritten for the seam. ✔
10. Palette reads `--situation-*` via `getComputedStyle` with pre-C4 hardcoded
    fallbacks; `refreshPalette()` exposed for C5. ✔
11. Layout untouched beyond the overlay swap. ✔

## Deviations from the letter of the order (with justification)

- `mount()` was folded into the factory (listeners + ResizeObserver bound at
  construction; `destroy()` is the unmount). The order listed "mount/render";
  a separate mount call would only restate construction. `render(snapshot)`
  kept as specified.
- `beginSession(runId)` / `clearSession()` were added beyond the listed API:
  the C2 ENC generation guards need an explicit lifecycle signal that a new
  run_id alone cannot express (ENC loads before the first telemetry frame).
- ENC availability DOM sync (checkbox disable/enable) stays in app.js, driven
  by `onLayerStateChange` — the module must stay DOM-free beyond the canvas.
- `SBMPC_RESPONSE_RANGE_M` literal lives in app.js's `plannerResponseRange`
  (unchanged logic; it reads `telemetryProjection`, which the module must not
  import — the range is injected via `getResponseRange`).
- The work order's preservation list mentioned `frozenMissionRoute`;
  renamed to pure `updateFrozenRoute(store, data)` so route-freeze semantics
  are directly unit-testable.

## Remaining glue in app.js (intentional)

- Planner-surface panel drawing (`plannerSurface` canvas, VO decision space
  fetch/pacing, objective history) — different canvas, stays host-side.
- Target-edit panel + busy-water document flows (REST via `apiRequest`).
- Catalogs / selection carousels / runtime controls / event log.
- `selectedTargetId` mirror variable kept in sync via `onSelectionChange`
  (busy-water list and edit form read it).

## Gates

- `/Users/marine/.nvm/versions/node/v22.18.0/bin/node --test
  tests/web_gui/*.test.mjs` → 118 pass / 0 fail (baseline 104 + 14 new in
  `tests/web_gui/situation-display.test.mjs`).
- `node --check` clean on app.js, situation-display.js, config-shell.js, both
  touched test files.
- `git diff --check` clean; no duplicate ids in index.html;
  `active-session-runtime.js` / `validation-assembly.js` / `telemetry-projection.js`
  / `session-runtime-instance.js` zero diff.
- Python side untouched.

## Fix round (dual-review BLOCK, 2026-08-19)

- **P0** `app.js` `resetDeploymentForSession`: deleted the 5 stale lines
  referencing the module-closure animation vars (`renderFrameId`,
  `renderFromData`, `renderToData`, `renderStartedAt`) — they threw a silent
  ReferenceError that aborted the session-reset path before
  `situationDisplay.beginSession()` ran (ENC never loaded). Regression test
  added (`situation-display.test.mjs`, "app.js never references the
  module-closure animation pipeline vars") asserting app.js source contains
  none of the five identifiers.
- **P0-adjacent bug found while testing** (`situation-display.js`,
  `queueTelemetryRender`/`renderTelemetryFrame`): with a synchronous rAF
  implementation the `renderFrameId = raf(cb)` assignment landed after the
  callback had already run and nulled the handle, freezing subsequent frames.
  Fixed with a pending-handle guard (also makes the module robust for hosts
  with sync rAF). Covered by the new draw-sequence test's second render.
- **P1** response-range label sync restored in `app.js` `updateUI`
  (`setText('response-range-control-label'/'response-range-legend-label', ...)`
  driven by `plannerResponseRange()?.label`, refreshed per telemetry frame —
  same cadence as the pre-C4 `updateLayerAvailability`).
- **P2-1** preview occlusion: new `backgroundMode: 'transparent'` option skips
  the opaque `--situation-bg` fill; Config preview adapter passes it.
  `.scenario-preview-canvas` background now `transparent`; badge
  (`.reference-preview-badge`) and `.scenario-preview-copy` get `z-index: 4`
  above the canvas (z-index 2).
- **P2** module DOM/network leakage: scale-bar writes now go through an
  injected optional `onScaleLabel(text)` sink (Deployment passes a
  `#scaleBarLabel` writer; Config passes nothing → no-op) — the module no
  longer touches `document` at all (static test asserts no `getElementById`).
  Sprites load only when `loadSprites: true` (default); the Config preview
  passes `false` → no image elements, no network requests.
- **P3** quick kills: dead `.scenario-preview-markers` rule removed from
  style.css; stray double blank line after the `--situation-*` token block
  collapsed; `layerStateSink` hoisted next to the other layer state vars;
  LAYER_ORDER tightened — `drawHorizon` returns before claiming a slot when a
  horizon has <2 points, `targetPredictions`/`tracks`/`targetRoutes` push only
  when something actually drew (new regression test covers single-point
  horizons claiming no slot).
- **Cache-bust** bumped to `20260819-c4-situation-2` on style.css, app.js,
  config-shell.js (index.html) and on both `situation-display.js` import
  specifiers.

Final gate: `node --test tests/web_gui/*.test.mjs` → **121 pass / 0 fail**
(118 + 3 fix-round tests); `node --check` clean; `git diff --check` clean; no
duplicate ids; frozen modules still zero-diff.
