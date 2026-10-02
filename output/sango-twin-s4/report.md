# P2-S4 live twin E2E — sango_twin_live_probe

- date: 2026-10-02T12:13:59.889Z
- live session: `c9b54f51-377b-497d-b1c0-f76da9dbfb21` (created via REST; page attached c9b54f51-377b-497d-b1c0-f76da9dbfb21)
- first attach: mode=live anchor=(39565.24609375,6957565) ships=2
- SIM TIME (attach, 6s): Δ=17.60s
- player kill → restart → page re-attach: attached re-sent (mode=live)
- SIM TIME (after restart, 6s): Δ=76.50s last=76.50s (pre-kill last=17.60s)
- §8 link spike: default off (0 camera_free) → enable → Cesium drag/wheel → camera_free flowing, state.camera=free, Player.log double proof → off → zero further
- D: twin-slot VectorArrows=wired WakeFoamRig=wired (Player.log)

## Assertions

- PASS  preflight backend 8010 — http://127.0.0.1:8010/api/capabilities -> 200
- PASS  preflight URS signaling 8080 — http://127.0.0.1:8080/config -> 200
- PASS  no leftover twin player
- PASS  live session created (POST /api/sessions) — status 200
- PASS  live session started (POST /start) — session=c9b54f51-377b-497d-b1c0-f76da9dbfb21
- PASS  video frames arriving (live pixel stream) — 1280x720
- PASS  bridge attached (mode live, anchor present) — run=c9b54f51 anchor=(39565.24609375,6957565) ships=2
- PASS  attach used the active live session — page attached c9b54f51 (created c9b54f51)
- PASS  SIM TIME advances (live, backend clock) — Δ=17.60s n=6
- PASS  live semantics: no camera_free before the link spike — sent=3
- PASS  player kill observed (connection idle)
- PASS  attached re-sent (contract §5 page-level reconnect) — run=c9b54f51 ships=2
- PASS  SIM TIME continues after player restart — pre-kill last=17.60s post Δ=76.50s last=76.50s
- PASS  link switch defaults to off
- PASS  link on: companion Cesium scene created (split pane)
- PASS  camera.changed → camera_free messages flowing
- PASS  state.camera echo = free (state-side proof)
- PASS  camera_free Player.log evidence (bridge log + rig pose) — /Users/marine/Library/Logs/DefaultCompany/sango/Player.log
- PASS  link-spike screenshot (twin video + Cesium master pane)
- PASS  link off: zero further camera_free (零消息零开销) — 40 → 40
- PASS  D: twin-slot VectorArrows wired (log)
- PASS  D: twin-slot WakeFoamRig wired (log)
