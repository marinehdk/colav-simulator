# C4 — ENC Situation Display Work Order (2026-08-19)

Worktree: `$HOME/Code/.worktrees/Colav-Simulator/mass-openbridge-ui` (branch `codex/mass-openbridge-ui`).
NEVER touch `.codegraph/` or stage `docs/ui/`. No push. No commits — the main agent commits.

## Objective

Concentrate the ENC Situation Display (currently inline in `web_gui/app.js`, lines ~99-330 state + ~437+ rendering) into a new module `web_gui/modules/situation-display.js`, with a clean seam. DO NOT rewrite the Canvas rendering logic — relocate and encapsulate it. app.js becomes the Deployment adapter/host. Config workface scenario preview becomes a second adapter on the same seam (replacing the static SVG reference).

## Approved rulings (user-confirmed 2026-08-19 — binding, do not re-decide)

1. **Delete the `overlay_geometry` phantom path**: `web_gui/modules/config-shell.js` lines ~366-380 (comment + `scenario?.overlay_geometry` read + empty-layer design). Backend never emits it. No seam interface reserved for it. The static-SVG replacement (ruling 9) supersedes this block entirely.
2. **Data boundary**: Situation Display consumes ONLY (a) ENC assets via injected fetchers (`/api/enc_info`, `/api/enc_tile`), (b) per-frame state pushed from the Runtime adapter (vessels, predictions, planner route, telemetry snapshots), (c) layer visibility flags via its own API, (d) internally-owned view state. `telemetry-projection.js` stays decoupled (zero imports either way).
3. **View state lifecycle**: survives workface switches; resets (fit ENC) only on new session generation or ENC asset change. View state lives inside the module (no app.js globals).
4. **Resize**: module tracks a `userAdjusted` flag (set on first wheel/drag). Resize: if not userAdjusted → current fit-ENC behavior; if userAdjusted → preserve pan/zoom (canvas-center anchored on the resized backing store). Explicit zoomReset button and new generation always fit.
5. **Keyboard**: none this round. Do not add tabindex/key handlers; do not break existing tab order.
6. **Layer state ownership**: layer ids/defaults/visibility all inside the Display module; UI calls `setLayerVisible(id, visible)` / reads `getLayerState()`. Layer state survives session replacement (view preference, not session state).
7. **Click routing**: Display owns hit-testing + selected-target state. Host may register a mutually-exclusive click mode (e.g. route-pick): while registered, clicks call back the host with UTM coords; on unregister, default target selection resumes. Host subscribes to selection changes.
8. **Render-order contract**: single ordered layer table constant inside the module, documented as the contract. Regression via deterministic mock-ctx draw-call-sequence tests (record method call order, assert layer order + toggle filtering). No pixel-diff automation.
9. **Second adapter**: Config workface scenario preview switches to the same Canvas seam (static adapter rendering scenario geometry without ENC/live telemetry), replacing the static SVG. Keep Config's #a9a9e77-accepted visual contract (colors/labels) — update `config-shell-static.test.mjs` expectations accordingly.
10. **Color tokens**: palette init reads CSS custom properties via `getComputedStyle` (`--ob-*` plus new canvas-specific tokens if needed, defined in style.css), falls back to current hardcoded colors when absent. Expose `refreshPalette()` for C5 theme switching.
11. **Screenshots**: human-inspected at three widths (1920×1080, 1366×768, narrow) during browser smoke by the main agent — not your concern beyond not breaking layout.

## Non-negotiable preservations (regression-test these BEFORE the seam)

DPR-aware sizing (`resizeCanvas`); ENC metadata/tile + WGS84/UTM mapping (`utmToCanvas`/`canvasToUtm`/`utmToWgs84`); render ordering (see `renderCanvas` body); initial mission-route freeze per run (`frozenMissionRoute`/`missionRoutes` Map); vessel interpolation (`interpolateTelemetry` chain + rAF pacing); current vs previous prediction distinction; planner surface attach (`plannerSurfaceAttached` + VO/fan); layer visibility + hit regions (`targetHitRegions`, reverse-order hit test); session-generation guards from C2 (`encLoadGeneration`, run_id checks).

## Implementation milestones (TDD — write failing test first per behavior)

- **M1 — characterization tests** (new `tests/web_gui/situation-display.test.mjs`): transform round-trips (world↔canvas↔UTM), render-order call trace with mock ctx, route-freeze semantics, interpolation math, hit-testing reverse order, zoom/pan clamping, resize semantics (post-ruling-4), layer toggle filtering. These test the EXTRACTED module's public seam; write them against the module's intended API, red first, then make green via M2 extraction. Pure-function parts (interpolateTelemetry, telemetryRenderDurationMs, zoom math, chooseGridSpacing, validRoute) must be exported for direct testing.
- **M2 — extract seam** `web_gui/modules/situation-display.js`: factory `createSituationDisplay({ canvas, wrapper, fetchInfo, fetchTile, now, ... })` owning view state, ENC loading (generation guards), layers, palette, rendering internals. Canvas implementation stays internal; public API: mount/render(snapshot), setLayerVisible, getLayerState, setClickMode(mode|null), onSelectionChange(cb), fitView(), refreshPalette(), destroy(). Snapshot shape = today's `currentData` (os/obstacles/truth/plans/waypoints/measurements/tracks/playback/seq/run_id/state) + planner surface payload.
- **M3 — app.js adapter**: app.js constructs one Display instance, pushes runtime snapshots (`queueTelemetryRender` pipeline can stay in app.js OR move interpolation into module — prefer moving, keep app.js as thin adapter), wires zoom buttons/ENC toggle/layer checkboxes/click modes/target-details panel. Remove now-duplicated globals. Route-pick mode registers via setClickMode. **Ownership rules still hold**: `/api/sessions` REST only in active-session-runtime.js; `new WebSocket` only in session-runtime-instance.js; planner decision-space route only in app.js; `active-session-runtime.js` and `validation-assembly.js` are zero-diff frozen.
- **M4 — Config preview second adapter** + delete overlay_geometry block (ruling 1/9). Preview adapter renders scenario catalog geometry (start/end points, route, ENC-less grid) via the same module. Update `config-shell-static.test.mjs` assertions that referenced the SVG/overlay block.
- **M5 — palette tokens**: define needed `--situation-*` (or reuse `--ob-*`) vars in style.css with current hardcoded values as fallback defaults; wire refreshPalette().

## Environment / gates

- Node: `/Users/marine/.nvm/versions/node/v22.18.0/bin/node --test tests/web_gui/*.test.mjs` — baseline 104 passing; must stay green and grow.
- `node --check` (v22) on every changed JS file.
- Python side untouched (no pytest needed unless gui_server changes — it shouldn't).
- **Any style.css or JS change served to the browser MUST bump the `?v=` cache-bust token in `web_gui/index.html`.**
- `git diff --check` clean; no duplicate ids in index.html.
- Lit components: attribute names all-lowercase (not relevant here, but don't introduce kebab attr reads).

## Report back

Summary of API surface, test count added/passed, files changed with line counts, any deviation from this order with justification, known remaining glue in app.js.
