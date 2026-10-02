# P2-S3 Digital Twin E2E — sango_twin_bridge_probe

- date: 2026-10-02T10:22:03.760Z
- run: `745d63fd-8be9-4f59-9813-87ca2846f9b1` (sealed READY, seekable)
- twin SIM TIME (Unity state echo, 10s @1×): first=0.00s last=8.77s Δ=8.77s (n=10)
- replay SIM TIME (web 2D, same run 10s @1×): first=0.00s last=9.00s Δ=9.00s (n=10)
- 对拍 |Δtwin − Δreplay| = 0.23s (tolerance 2.5s)
- bridge totals: sent=86 received=33 attached=yes stateCameraEcho=top simTimeEcho=10.022036667000002
- camera Unity log evidence: yes (/Users/marine/Library/Logs/DefaultCompany/sango/Player.log)

## Assertions

- PASS  preflight backend 8010 — http://127.0.0.1:8010/api/capabilities -> 200
- PASS  preflight URS signaling 8080 — http://127.0.0.1:8080/config -> 200
- PASS  video frames arriving (URS pixel stream) — 1280x720
- PASS  bridge attached received — mode=replay anchor=(37000,6955000)
- PASS  bridge state echo received (frame_seq >= 0)
- PASS  twin SIM TIME advances (Unity echo) — first=0.00 last=8.77 delta=8.77s n=10
- PASS  camera preset echo (bridge→Unity→state.camera)
- PASS  camera switch Unity log evidence — /Users/marine/Library/Logs/DefaultCompany/sango/Player.log
- PASS  twin viewport screenshots (day/night)
- PASS  detection toggle sends bridge messages — sent +3
- PASS  no bridge errors during probe — errorCount=0
- PASS  replay row reachable (pagination)
- PASS  replay SIM TIME advances (web 2D) — first=0.00 last=9.00 delta=9.00s n=10
- PASS  same-run SIM TIME 对拍 within tolerance — |twinΔ 8.77s − replayΔ 9.00s| = 0.23s (tol 2.5s)
