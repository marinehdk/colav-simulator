# sango_userpath_probe — 用户路径全功能验证（spec #91 前置批 D）

- 会话：`fdadb7d6-d3fd-4f12-97a3-1f7e261bdbce`（head_on / rule14 / vo，页面默认档）
- 链路：8010 前端（真实页面点击）← 8080 信令 ← sango twin player ← CDP headless Chrome
- 断言：28/28 PASS

## 截图/证据

| 项 | 产物 |
|---|---|
| ① 前端打开/建会话 | `00-frontend-open.png` `01-session-created.png` |
| ① T → EO 画面 | `02-eo-viewport.jpg` `02-eo-viewport-full.png` |
| P3-11 槽位对拍 | `03a-bridge-view-band.jpg` `03b-bridge-view-full.png` `slot-parity.json` `target-geometry.json` |
| P3-12 地理配准 | `03c-twin-aerial-target.jpg` `geo-registration.json`（水面断言=e<0 实采高程 + geo_fit=inside） |
| ② IR/LiDAR | `04-ir-viewport.jpg` `05-lidar-viewport.jpg` |
| ③ PPI | `06-ppi-panel.png` |
| ④⑤ AIS+CONF | `07-ais-layer.png` `08-target-card-conf.png` |
| ⑥ Evaluation 回放 | `10-evaluation-twin-replay.png` |

## 复现

```bash
node tools/sango_userpath_probe.mjs
```

前置：backend 8010（launchd frontend）+ twin-signaling 8080（deploy/twin/）在跑；
探针自行 bootout launchd twin-player、起自有 player、退出恢复。
