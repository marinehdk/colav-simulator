# P2-S4 live twin E2E — sango_twin_live_probe

- date: 2026-10-03T13:54:11.928Z
- live session: `bb3be111-26a7-4391-9781-0e393c8c7542` (created via REST; page attached bb3be111-26a7-4391-9781-0e393c8c7542)
- first attach: mode=live anchor=(39565.24609375,6957565) ships=2
- SIM TIME (attach, 6s): Δ=18.08s
- player kill → restart → page re-attach: attached re-sent (mode=live)
- SIM TIME (after restart, 6s): Δ=76.82s last=76.82s (pre-kill last=18.08s)
- §8 link spike: default off (0 camera_free) → enable → Cesium drag/wheel → camera_free flowing, state.camera=free, Player.log double proof → off → zero further
- D: twin-slot VectorArrows=wired WakeFoamRig=wired (Player.log)

## Assertions

- PASS  preflight backend 8010 — http://127.0.0.1:8010/api/capabilities -> 200
- PASS  preflight URS signaling 8080 — http://127.0.0.1:8080/config -> 200
- PASS  no leftover twin player
- PASS  live session created (POST /api/sessions) — status 200
- PASS  live session started (POST /start) — session=bb3be111-26a7-4391-9781-0e393c8c7542
- PASS  video frames arriving (live pixel stream) — 1280x720
- PASS  bridge attached (mode live, anchor present) — run=bb3be111 anchor=(39565.24609375,6957565) ships=2
- PASS  attach used the active live session — page attached bb3be111 (created bb3be111)
- PASS  live clock_skew_ms == 0 (playhead replay-only) — clock_skew_ms=0
- PASS  SIM TIME advances (live, backend clock) — Δ=18.08s n=6
- PASS  live semantics: no camera_free before the link spike — sent=4
- PASS  player kill observed (connection idle)
- PASS  attached re-sent (contract §5 page-level reconnect) — run=bb3be111 ships=2
- PASS  SIM TIME continues after player restart — pre-kill last=18.08s post Δ=76.82s last=76.82s
- PASS  link switch defaults to off
- PASS  link on: companion Cesium scene created (split pane)
- PASS  camera.changed → camera_free messages flowing
- PASS  state.camera echo = free (state-side proof)
- PASS  camera_free Player.log evidence (bridge log + rig pose) — /Users/marine/Library/Logs/DefaultCompany/sango/Player.log
- PASS  link-spike screenshot (twin video + Cesium master pane)
- PASS  link off: zero further camera_free (零消息零开销) — 46 → 46
- PASS  D: twin-slot VectorArrows wired (log)
- PASS  D: twin-slot WakeFoamRig wired (log)
