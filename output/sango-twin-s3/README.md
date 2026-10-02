# P2-S3 — Evaluation 02 Digital Twin 交付证据（spec #89，2026-10-02）

本目录 = `tools/sango_twin_bridge_probe.mjs`（E2E 探针）的产物 + 复现说明。
契约：`sango/Docs/contracts/twin-bridge-v1.md`（冻结）；实现：Unity `TwinBridgeService` +
web `web_gui/modules/twin-view.js`。设计与裁决：`docs/research/2026-10-02-phase2-unity-web-integration/00-REPORT.md` §4-§6。

## 1. 结论速览

| # | 验收项（spec #89 / 任务书） | 结果 | 数字 |
|---|---|---|---|
| 1 | web 测试全绿（含新增 twin-view.test.mjs） | **PASS** | **402/402**（36 文件，基线全绿保持） |
| 2 | Unity EditMode 全绿（451 基线 + 新增） | **PASS** | **464/464**（新增 13：契约回环 12 + 重连退避 1） |
| 3 | E2E probe exit 0 + 报告 | **PASS** | 14/14 断言，见 `report.md` |
| 4 | 同 run SIM TIME 对拍一致 | **PASS** | twin Δ=8.77s vs replay Δ=9.00s（10s 窗），**差 0.23s** |
| 5 | 截图（twin 视口含 HUD，日/夜） | **PASS** | `twin-day.png` / `twin-night.png` |

E2E 关键数值：视频 1280x720 像素流；`attached` anchor=(37000, 6955000)（= run 的 ENC 原点，S1 原点锚定语义）；
state 回包 frame_seq≥0、`camera` 回显 top、fps 85-87、skew 0ms；bridge 收发 sent=82/recv≈33；errorCount=0。

## 2. 复现命令

前置一次性：

```bash
# URS 信令 webapp（官方 3.1.0-exp.9 WebApp 源码构建；spike 同款）
git clone --depth 1 --branch 3.1.0-exp.9 https://github.com/Unity-Technologies/UnityRenderStreaming.git /tmp/urs-repo
cd /tmp/urs-repo/WebApp && npm ci && npm run build
node /tmp/urs-repo/WebApp/build/index.js -p 8080          # 信令 + 网页托管（curl :8080/config 验活）

# Unity 侧（仓库根为 $PWD；场景幂等可跳过若已存在）
UNITY=/Applications/Unity/Hub/Editor/6000.3.24f1/Unity.app/Contents/MacOS/Unity
"$UNITY" -batchmode -projectPath "$PWD/sango" \
  -executeMethod Sango.Editor.TwinBridge.TwinBridgeSceneBuilder.BuildTwinScene -quit -logFile /tmp/sango-twin-scene.log
"$UNITY" -batchmode -projectPath "$PWD/sango" \
  -executeMethod Sango.Editor.TwinBridge.TwinBridgeSceneBuilder.BuildTwinPlayer -quit -logFile /tmp/sango-twin-player.log
# 产物：sango/Builds/sango-twin.app（382MB，Mono2x，仅 SangoTwin 场景）
```

每次运行（三个常驻 + 探针）：

```bash
# 1) 后端（launchd 常驻；若挂：）
.venv/bin/python -m uvicorn gui_server.main:app --port 8010        # 仓库根
# 2) URS 信令（若挂：）
node /tmp/urs-repo/WebApp/build/index.js -p 8080
# 3) twin 流端（--sango-twin-bridge = TwinBridgeService 总闸，SangoSeamConfig.TwinBridgeCliFlag）
./sango/Builds/sango-twin.app/Contents/MacOS/sango --sango-twin-bridge &
# 4) E2E 探针（自起 headless Chrome，CDP 9223；产物落本目录）
source ~/.nvm/nvm.sh && nvm use 22
node tools/sango_twin_bridge_probe.mjs --run 745d63fd-8be9-4f59-9813-87ca2846f9b1
#    不带 --run 时自动选第一个 READY+seekable 且时长足够的密封 run
```

web 面上人工路径：`http://127.0.0.1:8010/` → Evaluation → 02 Digital Twin → run 行 Twin 按钮 →
播放/倍率/timeline → 相机 B/W/C/T/O → GT BOXES/YOLO 切换 → 顶栏亮度钮切日夜主题（同步 Unity 时刻档）。

单测回归：

```bash
source ~/.nvm/nvm.sh && nvm use 22 && node --test tests/web_gui/*.test.mjs        # 402/402
UNITY=/Applications/Unity/Hub/Editor/6000.3.24f1/Unity.app/Contents/MacOS/Unity
"$UNITY" -batchmode -projectPath "$PWD/sango" -runTests -testPlatform EditMode \
  -testResults /tmp/sango-editmode-s3.xml -logFile /tmp/sango-editmode-s3.log      # 464/464
```

## 3. 证据索引（本目录）

| 文件 | 内容 |
|---|---|
| `report.md` | 探针断言清单 + 关键数值（探针自动生成） |
| `sim-time-series.json` | 同 run 双视角 SIM TIME 原始采样（twin=Unity state 回显，replay=web 2D readout） |
| `twin-day.png` | 日主题：孪生视口（TopDown、HDRP 海面+FCB45）+ HUD `OK · 87 FPS · 0 MS` + timeline bar（SIM TIME 10.0s、0.5-20×、GT BOXES、`TWIN LIVE · SIGNAL OK`）+ run 语境条（`DIGITAL TWIN · 745d63fd · HEAD_ON · VO`） |
| `twin-night.png` | 夜主题：壳层 OpenBridge 夜间配色 + 流内夜景分级、本船号灯（红/绿舷灯）可见——`data-obc-theme` → bridge theme → Unity 0h 档全链路 |
| `player-log-excerpt.txt` | Unity 端 `[Sango.TwinBridge]` 日志节选（service started / hello→ready / attach / attached / camera 切换 / theme / detection） |

## 4. 落地实现里解决的三件事（对后继有价值的实证）

1. **URS 命令行解析陷阱**：player 带 `--sango-twin-bridge` 时 URS 的
   `evaluateCommandlineArguments` 会把无 ice-server 参数解析成 `IceServer(urls:null)`，
   `_Run` 的 `op_Explicit(urls.ToArray())` 抛 ArgumentNullException、信令进程起不来——
   场景侧 `evaluateCommandlineArguments=0` + 显式一条 STUN 兜底（TwinBridgeSceneBuilder）。
2. **public 信令模式的 offer 发起方**：webapp `-p 8080`（public）只把 `connect` 回显给发送者——
   纯接收页永远等不到 Unity 的 offer。官方 receiver 样例靠 `createDataChannel('input')` 的
   negotiationneeded 触发页面侧 offer（spike 页面同款）；twin-view.js 沿用该工艺。
3. **暂停时钟权威**：TwinClock（S1）无暂停概念（锚点+墙钟×倍率恒推进），sealed 回放暂停时
   渲染 sim 会按墙钟漂移。`TwinSessionDriver.AnchorReplayClock`（新）由 TwinBridgeService 在
   非 PLAYING 态持续锚到 web playhead——契约 §2"时钟权威在 web"的落地。

## 5. 已知边界 / 遗留

- live 模式 attach（WS compact-v1 + 断线退避重连）已实现并随契约冻结，但 S3 验收只覆盖 replay
  路径（Deployment live twin 属 S4）；`TwinReconnectPolicy` 的重连循环有 EditMode 单测，未做
  运行时断网实测。
- 相机词汇映射（§5.3 统一表）在 bridge 内落地（bridge/bow/chase/top/overlook）；Cesium↔Twin
  分屏联动（默认关）按计划留 S4。
- vendor 的 `signaling.js` 带 1 处本地补丁（构造器增 explicitUrl 参），升级需重放（`vendor/urs/README.md`）。
- `output/sango-twin-s3/report.md` 的 bridge totals 每次运行略有浮动（时钟消息数取决于采样窗）。
