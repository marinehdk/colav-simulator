# P3-S2 observations + sensor_mode E2E — sango_twin_obs_probe

- date: 2026-10-02T17:01:58.147Z
- live session: `fc534d1b-a0d2-4343-910a-64b1869108a8` (rule14/head_on/vo, tracker=god — capabilities gate; kf leg = pytest cache integration)
- mast feed: mast_ptz_eo 640x480 (Player.log rig attach + feed rewire); YOLO CPU rx>0
- IR switch: state echo ir, chip "SENSOR IR", grayscale stats {"mean":82.9044076527773,"std":55.03504283581002,"maxSpread":5,"w":1280,"h":720}
- EO restore: state echo eo, grayscale stats {"mean":78.76541040277822,"std":64.46002704999282,"maxSpread":34,"w":1280,"h":720}
- observations cache: accepted_frames=2141 channels=[{"sensor_id":2,"mount_id":"mast_ptz_eo","frames":2141,"detections":1,"last_frame_seq":2186}]

## Assertions

- PASS  preflight backend 8010 — http://127.0.0.1:8010/api/capabilities -> 200
- PASS  preflight URS signaling 8080 — http://127.0.0.1:8080/config -> 200
- PASS  observations route live (404 SESSION_NOT_FOUND on unknown session) — status 404
- PASS  live session created (POST /api/sessions, tracker=god; capabilities-gated) — status 200
- PASS  live session started — session=fc534d1b-a0d2-4343-910a-64b1869108a8
- PASS  YOLO detector up (CPU) with forward branch — /tmp/sango-obs-detector.log
- PASS  video frames arriving (live pixel stream) — attached run=fc534d1b ships=2
- PASS  mast rig attached to own ship; FramePublisher feed rewired to mast_ptz_eo — Player.log
- PASS  YOLO consuming published feed frames (rx > 0) — detector log
- PASS  feed-view frame artifact saved (mast feed camera view) — /Users/marine/Code/Colav-Simulator/output/sango-twin-s2/feed-frame.jpg
- PASS  IR switch: state echo sensor_mode=ir (contract §3)
- PASS  sensor-mode chip mirrors the echo — SENSOR IR
- PASS  IR stream frame captured (grayscale stats) — std=55.0 spread=5
- PASS  IR = black-and-white thermal (max channel spread ~0) — maxSpread=5
- PASS  IR frame artifact (decoded stream frame)
- PASS  EO restore: state echo sensor_mode=eo
- PASS  EO stream frame captured — std=64.5 spread=34
- PASS  EO = visible light (channel spread returns) — maxSpread=34
- PASS  EO frame artifact (decoded stream frame)
- PASS  observations accepted (frames flowed YOLO → POST → backend) — accepted_frames=2141 channels=[{"sensor_id":2,"mount_id":"mast_ptz_eo","frames":2141,"detections":1,"last_frame_seq":2186}]
- PASS  measurement cache holds sensor_id=2 camera_eo entries (YOLO detections georeferenced) — [{"sensor_id":2,"mount_id":"mast_ptz_eo","frames":2141,"detections":1,"last_frame_seq":2186}]
- PASS  detector forward branch reported POSTs — [detector] forward: ok=2140 err=0 last=HTTP 200 {"accepted":true,"frame_seq":2185,"detections_accepted":0}
- PASS  Player.log double proof (sensor_mode -> ir + mast rig attached) — /Users/marine/Library/Logs/DefaultCompany/sango/Player.log
