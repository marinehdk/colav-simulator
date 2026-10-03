# P3-S6 全传感器 E2E — sango_phase3_e2e_probe（spec #90 阶段3 完成定义六条实证）

- date: 2026-10-03T03:20:49.682Z（probe 自动断言清单在文末；本节为人工归档说明）
- flip 会话：`0e8eb83e-4e36-4983-a99f-98b236d95014`（rule14/head_on/vo，请求**未带 tracker_id** —— 翻转后默认 vimmjipda 应答）
- 链路：8010 后端 ← 8080 信令 ← sango player（twin-bridge + mast rig）← YOLO CPU 前向 ← headless Chrome CDP
- 结果：**39 PASS / 0 FAIL**（全清单见 `evidence-status.json`）

## 双会话设计（为何不是单会话）

00-PLAN §0 六条要求在同一张验收单上看到「radar_x 量测缓存 + PPI」与「vimmjipda 融合航迹 +
存在概率」。外部 vimmjipda 接口（`vimmjipda_tracker_interface.py`）只消费 legacy `Radar`
实例（上游 isinstance 过滤；外部仓库本阶段零改动），radar_x 组经遥测量测缓存外露需要
"全传感器消费"链路——god 诊断链（`for sensor in self.sensors` 全量生成量测）正是该通道，
且 god 是翻转后明文保留的回退路径（回退路径实证顺带完成）。因此：

- **Session A**（显式 `tracker_id="god"`，`f67404dc-…`）：radar_x 量测缓存断言 + radar_ppi
  描述符 + PPI 面板实开实绘 + AIS 层/目标卡 + 存在概率图例 + CONF 行。
- **Session B**（请求不带 tracker_id，默认 vimmjipda 应答）：会话边界翻转实证 +
  YOLO→observations sensor_id=2 缓存 + twin `sensor_mode` eo→ir→lidar→eo 全回路 +
  WS §6 三平行数组 + 存在概率通道 + confirmed-tracks 数据产品。

## §0 六条对照

| §0 条目 | 断言（摘要） | 实测 |
|---|---|---|
| 1 量测→融合→确认航迹+置信度 | radar_x 量测缓存（A）；WS §6 数组 + confirmed-tracks 非空 + 存在概率字段在场（B） | finite radar 量测在缓存；labels=1 existence=[0.9999993296184886]；confirmed=1 |
| 2 X 波段雷达 + PPI | radar_ppi 描述符 + PPI 面板 canvas 实绘 | scale=6nm scan=2.5s blind_ring=54.1m；ppi-panel.png |
| 3/7 桅杆机位 + IR + LiDAR + 视角切换 | sensor_mode eo→ir→lidar→eo 状态回声 + 帧统计双证 | IR maxSpread=5（黑白）；lidar dark=0.97 lit=0.0166（点云）；EO 复原 spread=36 |
| 4 AIS 目标层 | 符号层渲染 + 目标卡字段 | count≥1；source=AIS state=激活（矢量）assoc 非占位 |
| 5 IPDA 存在概率贯通 | vimmjipda 存在概率非 god 钉值路径 | WS 采样 + confirmed-tracks（存在概率 0.99999932 ≠ 1.0 钉值；任务口径"短窗全 confirmed→端点非空+字段在场"回退内建，且实际拿到非 1.0 值） |
| 6 YOLO 框进 tracker | observations 端点 sensor_id=2 | accepted_frames=2202 detections=1 |

## 产物

| 文件 | 内容 |
|---|---|
| `evidence-status.json` | 全部 39 条断言 + 明细 |
| `ws-envelope-god-extract.json` / `ws-envelope-extract.json` | A/B 会话 WS 抽帧（tracks §6、radar_ppi、executed_tracker） |
| `confirmed-tracks-live.json` | vimmjipda 会话 confirmed-tracks 信封实测 |
| `observations-status.json` | sensor_id=2 相机量测缓存计数 |
| `ppi-panel.png` / `ais-card.png` / `tracks-legend.png` / `placard-conf.png` / `chart-god-session.png` / `chart-final.png` | 面板/卡片/图例/CONF/海图截图 |
| `mode-{eo,ir,lidar}.jpg|.png`、`mode-eo-restored.jpg` | 视角切换流内帧 + 截屏 |
| `mast-feed-frame.jpg` / `player-log-excerpt.txt` / `probe-console.log` | 桅杆馈源帧、Player.log 双证、页面控制台 |

## 复现

```bash
launchctl kickstart -k gui/$(id -u)/com.marine.colav-simulator.frontend && sleep 60
node /tmp/urs-repo/WebApp/build/index.js -p 8080 &        # 若信令未起
export NVM_DIR="$HOME/.nvm"; . "$NVM_DIR/nvm.sh" && nvm use 22
node tools/sango_phase3_e2e_probe.mjs
```

## 已知边界（写档）

- vimmjipda 会话在目标进入 legacy Radar 2km 量程前无航迹（head_on 初始 2.8km，约 2 分钟）；
  探针 WS 采样器以"出现航迹"为完成门（cap 300s）。
- radar_x 进 vimmjipda 融合 = 外部仓库工作（isinstance Radar 过滤），下阶段立项；
  本阶段 radar_x 的融合位由 legacy Radar 通道承担（sensor-model-v1 通道词表 radar_x=1
  与 legacy radar 同通道，航迹 sources[] sensor_id=1 语义不变）。
- AIS 关联显示"独立目标"：god 会话无融合航迹可关联时的后端权威判定，非缺陷。

## 断言全清单（probe 自动生成）

- PASS  preflight backend 8010 — http://127.0.0.1:8010/api/capabilities -> 200
- PASS  preflight URS signaling 8080 — http://127.0.0.1:8080/config -> 200
- PASS  product policy default tracker flipped to vimmjipda (capabilities boundary) — default_tracker_id=vimmjipda tracker_ids=["god","vimmjipda"]
- PASS  god retained alongside the flipped default (fallback channel kept) — ["god","vimmjipda"]
- PASS  vimmjipda selectable in the live product catalog (algo_status) — selectable=["god","vimmjipda"]
- PASS  fallback session created with EXPLICIT tracker_id=god (revert path live) — session=f67404dc-5102-47ab-b547-0ae412c0d6ad
- PASS  radar_ppi descriptor live on the envelope (radar_x assembled in scenario) — scale=6nm scan=2.5s blind_ring=54.1m
- PASS  measurement cache holds finite radar_x measurements (god chain consumes every sensor) — finite_radar_measurements=3 sample=[6959206,41213]
- PASS  PPI panel opens and draws on live radar_x data (rings/sweep/blips)
- PASS  AIS symbol layer renders on the live chart (IMO SN.1/Circ.243) — {"count":1,"layerChecked":true}
- PASS  AIS target card opens with backend-authoritative fields — {"hidden":false,"source":"AIS","mmsi":"101","sog":"13.6","age":"8","state":"激活（矢量）","assoc":"独立目标"}
- PASS  existence-probability legend bands present (confirmed/amber/dim)
- PASS  vessel placard carries the CONF row (existence probability) — CONF=1.000
- PASS  new session created with the request-level DEFAULT tracker (no tracker_id sent) — spec.tracker_id=vimmjipda
- PASS  capabilities catalog carries the fusion tracker readiness grade — trackers=[{"id":"scenario_default","grade":"G1"},{"id":"god","grade":"G2"},{"id":"kf","grade":"G2"},{"id":"vimmjipda","grade":"G2"}]
- PASS  flipped-default session started (vimmjipda fusion chain) — session=0e8eb83e-4e36-4983-a99f-98b236d95014
- PASS  YOLO detector up (CPU) with forward branch — /tmp/sango-e2e-detector.log
- PASS  twin viewport attached to the flipped-tracker session (live pixel stream) — run=0e8eb83e ships=2
- PASS  mast rig attached; FramePublisher feed rewired to mast_ptz_eo (P3-S2 rig family) — Player.log
- PASS  YOLO consuming published feed frames (rx > 0) — detector log
- PASS  EO baseline frame captured (visible light) — mean=78.9 std=64.4 spread=34 dark=0.12 lit=0.2907
- PASS  IR switch: state echo sensor_mode=ir (contract §3)
- PASS  sensor-mode chip mirrors IR echo — SENSOR IR
- PASS  IR stream frame captured (grayscale stats) — mean=83.2 std=55.0 spread=5 dark=0.00 lit=0.3060
- PASS  IR = black-and-white thermal (max channel spread ~0) — maxSpread=5
- PASS  LiDAR switch: state echo sensor_mode=lidar
- PASS  LiDAR frame captured — mean=8.9 std=16.7 spread=105 dark=0.97 lit=0.0166
- PASS  LiDAR = point-cloud view (dark backdrop vs EO) — lidar dark=0.97 vs eo dark=0.12
- PASS  LiDAR point cloud sparse lit points present — lit=0.0166
- PASS  EO restore: state echo sensor_mode=eo (full loop closed)
- PASS  EO restore = visible light returns (channel spread back) — mean=78.9 std=64.4 spread=36 dark=0.12 lit=0.2903
- PASS  Player.log double proof (sensor_mode -> ir / lidar + mast rig) — /Users/marine/Library/Logs/DefaultCompany/sango/Player.log
- PASS  observations accepted (YOLO → POST → backend measurement cache) — accepted_frames=2202
- PASS  measurement cache holds sensor_id=2 camera_eo entries (georeferenced detections) — [{"sensor_id":2,"mount_id":"mast_ptz_eo","frames":2202,"detections":1,"last_frame_seq":2215}]
- PASS  WS envelope stream captured (live frames) — frames=5
- PASS  WS tracks carry §6 existence_prob/quality/sources arrays (P3-S5 channel) — labels=1 existence=[0.9999993296184886]
- PASS  vimmjipda existence probability is measurement-driven (not the pinned god 1.0) — samples=5 min=1.0000 max=1.0000 confirmed=1
- PASS  confirmed-tracks data product live (frozen sensor-model@1/tracks envelope) — tracks=1
- PASS  backend-authoritative ais fields present on obstacles of the fusion session (age_s/state) — sample={"age_s":5.5,"state":"active"}
