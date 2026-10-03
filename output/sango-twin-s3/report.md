# P2-S3 Digital Twin E2E — sango_twin_bridge_probe

- date: 2026-10-03T15:43:52.825Z
- run: `cbe1400b-1cfa-447b-be62-8235dcbd6345` (sealed READY, seekable)
- twin SIM TIME (Unity state echo, 10s @1×): first=0.00s last=7.73s Δ=7.73s (n=10)
- replay SIM TIME (web 2D, same run 10s @1×): first=0.00s last=9.00s Δ=9.00s (n=10)
- 对拍 |Δtwin − Δreplay| = 1.27s (tolerance 2.5s)
- bridge totals: sent=98 received=49 attached=yes stateCameraEcho=top simTimeEcho=0.00001570800000649797
- camera Unity log evidence: yes (/Users/marine/Library/Logs/DefaultCompany/sango/Player.log)

## Assertions

- PASS  preflight backend 8010 — http://127.0.0.1:8010/api/capabilities -> 200
- PASS  preflight URS signaling 8080 — http://127.0.0.1:8080/config -> 200
- PASS  twin row reachable (page size + footer pagination)
- PASS  video frames arriving (URS pixel stream) — 1280x720
- PASS  bridge attached received — mode=replay anchor=(37000,6955000)
- PASS  bridge state echo received (frame_seq >= 0)
- PASS  attached.ships == run ship count (replay context semantics) — attached.ships=2 context.ships=2
- PASS  twin SIM TIME advances (Unity echo) — first=0.00 last=7.73 delta=7.73s n=10
- PASS  camera preset echo (bridge→Unity→state.camera)
- PASS  camera switch Unity log evidence — /Users/marine/Library/Logs/DefaultCompany/sango/Player.log
- PASS  twin viewport screenshots (day/night)
- PASS  detection toggle sends bridge messages — sent +3
- PASS  no bridge errors during probe — errorCount=0
- PASS  state.detection.enabled echoes the web toggle (F7) — enabled=true source=truth
- PASS  second sealed READY run available for re-attach step — ff43f552-1f96-4787-a16b-fc4c0fe56718
- PASS  viewer closed, detach sent (runs panel back)
- PASS  run B row reachable (page size + footer pagination)
- PASS  attach after detach accepted (幂等重挂) — runB=ff43f552 mode=replay anchor=(37000,6955000)
- PASS  no channel rebuild on re-attach (Player.log: no new bridge channel open, attach logged) — channel opens 1→1, attach run=ff43f552 logged=true
- PASS  same client instance reused (message counters grew) — sent 92→98, received 35→36
- PASS  replay row reachable (pagination)
- PASS  replay SIM TIME advances (web 2D) — first=0.00 last=9.00 delta=9.00s n=10
- PASS  same-run SIM TIME 对拍 within tolerance — |twinΔ 7.73s − replayΔ 9.00s| = 1.27s (tol 2.5s)
