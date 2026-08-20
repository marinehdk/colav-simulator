# C4 Browser Smoke Report — 2026-08-19 (port 8012, worktree mass-openbridge-ui)

Cache-bust token served: `20260819-c4-situation-2`. Setup: uvicorn from worktree; session created/started via the app's own REST API (`POST /api/sessions`, `POST .../start`) after GUI clicks proved unreliable in this IAB session — disclosed as environment prep, not a substitute for GUI behavior.

## Verified PASS (each with DOM and/or visual evidence)

1. **Cold boot**: page loads, catalog auto-loads to 4/4 ready, Config workface intact (C1-C3 no regression at snapshot level).
2. **Config scenario preview (ruling 9 / P2-1 fix)**: reference chart image visible, `REFERENCE PREVIEW · NOT LIVE` badge readable on top, transparent grid overlay rendered by the second situation-display adapter, bottom caption bar intact. Screenshots t1/t1d (vision-verified). Phantom overlay_geometry path gone.
3. **ENC load through the new seam (P0 fix proof)**: on session adoption the frontend executed `GET /api/enc_info` → WS connect → `GET /api/enc_tile` (server log), badge shows 已加载, event log shows `ENC chart loaded — UTM33 origin (37000, 6955000)`, and the rendered ENC chart is visible on the canvas (screenshot t4, vision-verified). `resetDeploymentForSession` no longer throws (pre-fix it silently killed this whole path).
4. **Session authority / ruling-20 swap**: CREATED adopted after reload; `Open Deployment` appeared.
5. **RUNNING via WS**: state RUNNING, 仿真时间 advancing (11.5 s+) — telemetry reaches the module's render pipeline.
6. **Workface tab switching** functional (note: tabs sit at y≈48; earlier coordinate misses were automation error, not app bug).

## Not browser-verified (honest gaps — covered by unit tests, not by GUI)

- Ships visible while RUNNING, interactive wheel-zoom/drag-pan, resize pan/zoom preservation (ruling 4), layer toggles, target click selection, route-pick click mode.
- 1366×768 and narrow screenshots: the IAB screenshot channel degraded mid-session (returned cached frames, then failed entirely); only 1920×1080 captures succeeded.
- GUI click reliability in this IAB session was poor (role clicks timed out on most targets; dom_cua node clicks mostly no-oped; only some CUA coordinate clicks landed). Tab-switching and step-02 clicks did work with corrected coordinates, so the app's handlers are alive; the failures are treated as environment, but Start-button click was never GUI-verified this round.

## Artifacts

Screenshots in `docs/ui/c4-screenshots/`: t0/t1/t1d (Config preview), t4 (Deployment, CREATED, ENC chart visible).
