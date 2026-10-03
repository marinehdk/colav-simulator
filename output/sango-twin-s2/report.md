# P3-S2 observations + sensor_mode E2E — sango_twin_obs_probe

- date: 2026-10-03T16:43:27.175Z
- live session: `1a0b9fa6-318a-4426-8a0f-ef847aa2226e` (rule14/head_on/vo, default tracker post-S6-flip — vimmjipda chain)
- mast feed: mast_ptz_eo 640x480 (Player.log rig attach + feed rewire); YOLO CPU rx>0
- IR switch: state echo ir, chip "SENSOR IR", grayscale stats mean=64.7 std=26.8 maxSpread=5
- EO restore: state echo eo, grayscale stats mean=65.0 std=34.0 maxSpread=66
- observations cache: accepted_frames=134 channels=[{"sensor_id":2,"mount_id":"mast_ptz_eo","frames":134,"detections":77,"last_frame_seq":166}]

## Assertions

- PASS  preflight backend 8010 — http://127.0.0.1:8010/api/capabilities -> 200
- PASS  preflight URS signaling 8080 — http://127.0.0.1:8080/config -> 200
- PASS  observations route live (404 SESSION_NOT_FOUND on unknown session) — status 404
- PASS  live session created (POST /api/sessions, default tracker — S6 flip) — status 200
- PASS  live session started — session=1a0b9fa6-318a-4426-8a0f-ef847aa2226e
- PASS  YOLO detector up (CPU) with forward branch — /tmp/sango-obs-detector.log
- PASS  video frames arriving (live pixel stream) — attached run=1a0b9fa6 ships=2
- PASS  mast rig attached to own ship; FramePublisher feed rewired to mast_ptz_eo — Player.log
- PASS  YOLO consuming published feed frames (rx > 0) — detector log
- PASS  feed-view frame artifact saved (mast feed camera view) — /Users/marine/Code/Colav-Simulator/output/sango-twin-s2/feed-frame.jpg
- PASS  IR switch: state echo sensor_mode=ir (contract §3)
- PASS  sensor-mode chip mirrors the echo — SENSOR IR
- PASS  IR stream frame captured (grayscale stats) — std=26.8 spread=5
- PASS  IR = black-and-white thermal (max channel spread ~0) — maxSpread=5
- PASS  IR frame artifact (decoded stream frame)
- PASS  EO restore: state echo sensor_mode=eo
- PASS  EO stream frame captured — std=34.0 spread=66
- PASS  EO = visible light (channel spread returns) — maxSpread=66
- PASS  EO frame artifact (decoded stream frame)
- PASS  observations accepted (frames flowed YOLO → POST → backend) — accepted_frames=134 channels=[{"sensor_id":2,"mount_id":"mast_ptz_eo","frames":134,"detections":77,"last_frame_seq":166}]
- PASS  measurement cache holds sensor_id=2 camera_eo entries (YOLO detections georeferenced) — [{"sensor_id":2,"mount_id":"mast_ptz_eo","frames":134,"detections":77,"last_frame_seq":166}]
- PASS  detector forward branch reported POSTs — [detector] forward: ok=130 err=0 last=HTTP 200 {"accepted":true,"frame_seq":162,"detections_accepted":1}
- PASS  Player.log double proof (sensor_mode -> ir + mast rig attached) — /Users/marine/Library/Logs/DefaultCompany/sango/Player.log
