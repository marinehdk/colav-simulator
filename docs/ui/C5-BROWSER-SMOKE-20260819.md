# C5 Browser Smoke Report — 2026-08-19 (port 8012, worktree mass-openbridge-ui)

Cache-bust token served: `20260819-c5-shell-1`. Browser: IAB. Guest crashed mid-session (after a Ctrl+0 keypress on a detaching guest) — verification below is what was established before and independent of the crash.

## Verified PASS

1. **Boot state (#4/#22)**: `html[data-obc-theme="day"]`, `document.title === "综合避碰仿真器 · Config"`, `#brillianceMenu` present and hidden, catalog loads (fresh and reloaded tabs). Confirms applyPalette boot path + WORKFACE_TITLES default execute without error.
2. **Boot-completion chain (static proof listeners bound)**: the "· Config" title suffix is set only by `switchWorkface` during `bootConfig` → bootConfig ran to completion → `bindControls` (which binds workface-tab clicks) ran to completion. App-side handlers are alive; the interactive failures below are environmental.
3. **CDN theme blocks are variable-only**: pinned `openbridge.css` `[data-obc-theme]` rules define CSS custom properties only — no layout/pointer-events changes; adding the attribute cannot break header clicks. Rules out the one C5-specific regression hypothesis.
4. **Regression**: C1-C4 surfaces intact at snapshot level on the fresh tab (catalog, steps, summary, contract).

## Not browser-verified (environment: IAB clicks failed across all coordinate/node/keyboard paths, then guest crashed)

- Palette switch via dimming button + `palette-changed` (4 themes), menu open/Esc/outside-click close, localStorage persistence round-trip.
- Tab-switch title change + workface persistence restore across reload (static chain above covers binding; behavior unit-asserted).
- 520 tier layout (viewport resize never reached).
- Deployment ENC re-smoke after C5 asset changes (situation-display.js zero-diff; app.js wiring around ENC path unchanged in C5 diff).

## Disposition

Static tests (14 new, 135/135) + dual independent review (both PASS, zero P0/P1) carry these behaviors. Next session with a healthy browser should spot-check: palette cycle, 520 viewport, workface restore. The earlier C4 smoke on the same worktree verified ENC/preview/tab-click paths end-to-end.
