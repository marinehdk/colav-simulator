# P2-S4 — 统一收口交付证据（spec #89，2026-10-02）

本目录 = `tools/sango_twin_live_probe.mjs`（live 重连 + 联动 spike + D 接线 E2E）的产物 + 复现说明。
契约：`sango/Docs/contracts/twin-bridge-v1.md`（§8 演进记录 = camera_free 只加字段扩展）；
前置三段：S1 `28a1e27f` / S2 `46e5e4ec` / S3 `a430fc62`。

## 1. 结论速览

| # | 验收项（任务书） | 结果 | 数字/证据 |
|---|---|---|---|
| 1 | web 测试全绿 | **PASS** | **425/425**（402 基线 + 23 新增：twin-view 5 / deployment-view 6 / deployment-twin 12） |
| 2 | Unity EditMode 全绿 | **PASS** | **476/476**（464 基线 + 12 新增：camera_free 回环 2 + 重连序列 2 + CameraRig 自由位姿 3 + Twin sog 视觉 5） |
| 3 | S3 E2E 探针回归 | **PASS** | 13/13 断言，exit 0（`output/sango-twin-s3/report.md` 本次复跑）；对拍 \|8.42−9.00\|=0.58s |
| 4 | live 断线重连实测 | **PASS** | kill player → 重启 → 页面重 attach → **attached 重发**（mode=live，同 run）+ SIM TIME 续进（17.60s → 76.50s） |
| 5 | 联动 spike 双证 | **PASS** | 默认关（0 条 camera_free）→ 开 → Cesium 拖拽/滚轮 → camera_free 到 Unity：`state.camera=free`（状态侧）+ Player.log `camera_free east=… yaw=… pitch=-89.9 fov=60`（日志侧）→ 关 → 零再发（40→40） |
| 6 | sog 接矢量/尾迹 | **PASS** | EditMode 数值测试 5 项 + Player.log 每槽位 `vector arrows rig built … on Twin vessel N` / `wake foam rig built …`；`twin-live.png` |

E2E 关键数值：live 会话页面自采（REST 建 → `/api/sessions/current` 引导采纳）；attach anchor=(39565,6957565) ships=2；
HUD `OK · 60 FPS`；SIM TIME live Δ=17.6s/6s 窗（head_on 场景仿真倍率 ≠ 墙钟，属正常）。

## 2. 复现命令

前置一次性（同 S3 README §2）：URS 信令 webapp（`node /tmp/urs-repo/WebApp/build/index.js -p 8080`）、
twin 场景/播放器构建（TwinBridgeSceneBuilder）。S4 改了 Unity 侧代码，播放器需重建：

```bash
UNITY=/Applications/Unity/Hub/Editor/6000.3.24f1/Unity.app/Contents/MacOS/Unity
"$UNITY" -batchmode -projectPath "$PWD/sango" \
  -executeMethod Sango.Editor.TwinBridge.TwinBridgeSceneBuilder.BuildTwinPlayer -quit -logFile /tmp/sango-twin-player.log
```

每次运行（backend 8010 launchd 常驻；player 由探针全权管理——起前 pgrep 清残留、退场必杀）：

```bash
source ~/.nvm/nvm.sh && nvm use 22
node tools/sango_twin_live_probe.mjs          # 产物落本目录；exit 0 = 全断言过
# 回归门（Evaluation twin 零回归；player 需常驻）：
./sango/Builds/sango-twin.app/Contents/MacOS/sango --sango-twin-bridge &
node tools/sango_twin_bridge_probe.mjs        # 13/13
```

单测回归：

```bash
source ~/.nvm/nvm.sh && nvm use 22 && node --test tests/web_gui/*.test.mjs   # 425/425
"$UNITY" -batchmode -projectPath "$PWD/sango" -runTests -testPlatform EditMode \
  -testResults /tmp/sango-editmode-s4.xml -logFile /tmp/sango-editmode-s4.log # 476/476
```

web 人工路径：`http://127.0.0.1:8010/` → Deployment → 显示条 **T** 钮 → live 孪生视口（HUD/联动开关）→
勾"联动" → 右侧 Cesium 主视口拖拽/滚轮 → Unity 相机跟随（左视口画面变化）。

## 3. 证据索引（本目录）

| 文件 | 内容 |
|---|---|
| `report.md` | live 探针断言清单 + 关键数值（探针自动生成） |
| `sim-time-series.json` | kill 前后 SIM TIME 采样（Unity state 回显） |
| `link-spike.png` | 联动开：分屏（左 twin 视口 + HUD + 联动勾选，右 Cesium 主视口俯视 + 机位工具条）+ 既有 live sidebar |
| `twin-live.png` | 联动关：全宽 twin 视口（联动未勾）+ live sidebar |
| `player-log-excerpt.txt` | `[Sango.TwinBridge] camera_free …` + 每槽位矢量/尾迹 rig 构建行 + live 重连日志 |
| `probe-console.log` | 页面控制台节选（探针失败时诊断用） |

## 4. 实现要点（对后继有价值的实证）

1. **工厂即 await 缝**：deployment-view 的 `createTwin` 工厂 promise 覆盖"建 viewport + URS 流 + attach"全程，
   失败走 enterTwin 的既有 exit/onError 路径——attach 不能晚于工厂 resolve（首次实现挂在 return 后死代码，探针
   以 `__deploymentTwin` 句柄 + WS 包桩定位）。
2. **receiver offer 竞态**：URS public 信令下 offer 只在 receiver `createDataChannel('input')` 的
   negotiationneeded 发一次；player 未就绪时该 offer 石沉大海，重试 = 视口 exit/enter（新 RS = 新 offer）。
3. **联动相机频率**：`camera.changed`（percentageChanged 0.01）在 Cesium follow 相机随投影刷新时也会触发
   （非仅用户拖拽），实测 ~4Hz 量级——spike 语义内可接受，逐帧锁步仍不做；反向（Twin→Cesium）不做。

## 5. 已知边界 / 遗留

- headless Chrome 截图 WebRTC `<video>` 恒黑帧（本机截图管线限制）；流健康以 HUD `OK · 60 FPS` 与
  `videoWidth=1280` 断言为证。人工浏览器里画面正常（S3 twin-day/night.png 同管线曾出画）。
- Deployment twin HUD 的 `60000 MS` 延迟显示 = live 无 web playhead 时 skew 钳位值（S3 契约字段 live 语义的
  展示瑕疵，不影响控制/数据面；留阶段3 打磨）。
- 后端侧 WS 断连（uvicorn 重启）场景按任务书以单测覆盖（TwinReconnectPolicy.ReconnectSequence，
  TwinBridgeMessageTests 两项）；未做运行时实测（会全局影响 8010）。
- 联动开时 camera_free 频率随 Cesium follow 刷新（~4Hz），未做节流；默认关时零消息零开销（40→40 断言）。
