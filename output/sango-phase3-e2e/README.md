# P3-S6 全传感器 E2E — sango_phase3_e2e_probe

- date: 2026-10-03T15:46:45.979Z
- live session: `bef5ba12-efb8-4bd4-9a45-312395611fab`（rule14/head_on/vo，请求未带 tracker_id —— 翻转后默认 vimmjipda 应答）
- 链路：8010 后端 ← 8080 信令 ← sango player（twin-bridge + mast rig）← YOLO CPU 前向 ← headless Chrome CDP

## 断言

- PASS  preflight backend 8010 — http://127.0.0.1:8010/api/capabilities -> 200
- PASS  preflight URS signaling 8080 — http://127.0.0.1:8080/config -> 200
- PASS  product policy default tracker flipped to vimmjipda (capabilities boundary) — default_tracker_id=vimmjipda tracker_ids=["god","vimmjipda"]
- PASS  god retained alongside the flipped default (fallback channel kept) — ["god","vimmjipda"]
- PASS  vimmjipda selectable in the live product catalog (algo_status) — selectable=["god","vimmjipda"]
- PASS  launchd twin-player downed for probe (single-instance) — gui/502/com.marine.colav-simulator.twin-player
- PASS  fallback session created with EXPLICIT tracker_id=god (revert path live) — session=f13d5565-e7e8-4c1b-bf1d-5e8046667a7e
- PASS  radar_ppi descriptor live on the envelope (radar_x assembled in scenario) — scale=6nm scan=2.5s blind_ring=54.1m
- PASS  measurement cache holds finite radar_x measurements (god chain consumes every sensor) — finite_radar_measurements=3 sample=[6959206,41213]
- PASS  PPI panel opens and draws on live radar_x data (rings/sweep/blips)
- PASS  AIS symbol layer renders on the live chart (IMO SN.1/Circ.243) — {"count":1,"layerChecked":true}
- PASS  AIS target card opens with backend-authoritative fields — {"hidden":false,"source":"AIS","mmsi":"101","sog":"13.6","age":"8","state":"激活（矢量）","assoc":"独立目标"}
- PASS  existence-probability legend bands present (confirmed/amber/dim)
- PASS  vessel placard carries the CONF row (existence probability) — CONF=1.000
- PASS  new session created with the request-level DEFAULT tracker (no tracker_id sent) — spec.tracker_id=vimmjipda
- PASS  capabilities catalog carries the fusion tracker readiness grade — trackers=[{"id":"scenario_default","grade":"G1"},{"id":"god","grade":"G2"},{"id":"kf","grade":"G2"},{"id":"vimmjipda","grade":"G2"}]
- PASS  flipped-default session started (vimmjipda fusion chain) — session=bef5ba12-efb8-4bd4-9a45-312395611fab
- PASS  YOLO detector up (CPU) with forward branch — /tmp/sango-e2e-detector.log
- PASS  twin viewport attached to the flipped-tracker session (live pixel stream) — run=bef5ba12 ships=2
- PASS  mast rig attached; FramePublisher feed rewired to mast_ptz_eo (P3-S2 rig family) — Player.log
- PASS  YOLO consuming published feed frames (rx > 0) — detector log
- PASS  EO baseline frame captured (visible light) — mean=75.9 std=52.1 spread=79 dark=0.24 lit=0.4001
- PASS  IR switch: state echo sensor_mode=ir (contract §3)
- PASS  sensor-mode chip mirrors IR echo — SENSOR IR
- PASS  IR stream frame captured (grayscale stats) — mean=72.2 std=44.6 spread=6 dark=0.21 lit=0.3592
- PASS  IR = black-and-white thermal (max channel spread ~0) — maxSpread=6
- PASS  LiDAR switch: state echo sensor_mode=lidar
- PASS  LiDAR frame captured — mean=6.1 std=4.4 spread=133 dark=1.00 lit=0.0015
- PASS  LiDAR = point-cloud view (dark backdrop vs EO) — lidar dark=1.00 vs eo dark=0.24
- PASS  LiDAR point cloud sparse lit points present — lit=0.0015
- PASS  EO restore: state echo sensor_mode=eo (full loop closed)
- PASS  EO restore = visible light returns (channel spread back) — mean=76.5 std=52.9 spread=63 dark=0.24 lit=0.4056
- PASS  Player.log double proof (sensor_mode -> ir / lidar + mast rig) — /Users/marine/Library/Logs/DefaultCompany/sango/Player.log
- PASS  observations accepted (YOLO → POST → backend measurement cache) — accepted_frames=115
- PASS  measurement cache holds sensor_id=2 camera_eo entries (georeferenced detections) — [{"sensor_id":2,"mount_id":"mast_ptz_eo","frames":115,"detections":68,"last_frame_seq":125}]
- PASS  WS envelope stream captured (live frames) — frames=312
- PASS  WS tracks carry §6 existence_prob/quality/sources arrays (P3-S5 channel) — labels=1 existence=[0.9999299223955188]
- PASS  vimmjipda existence probability is measurement-driven (not the pinned god 1.0) — samples=5 min=0.9999 max=0.9999 confirmed=1
- PASS  confirmed-tracks data product live (frozen sensor-model@1/tracks envelope) — tracks=1
- PASS  backend-authoritative ais fields present on obstacles of the fusion session (age_s/state) — sample={"age_s":9,"state":"active"}
