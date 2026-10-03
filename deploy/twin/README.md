# Twin runtime — launchd 双服务（spec #91 前置批）

Deployment 选 T 后视口无画面的根因：URS 信令（:8080）与 sango twin player 都是手动进程，
退出/重启后无人拉起，浏览器（8010 前端）停在"信令活着、player 不在"的空等态。本目录把
两个常驻进程装成用户域 LaunchAgent（KeepAlive 拉活），装好后 T 视口自动恢复。

## 组件

| 服务 | Label | 端口/产物 | plist |
|---|---|---|---|
| URS 信令 webapp | `com.marine.colav-simulator.twin-signaling` | :8080（HTTP + WS 信令） | `com.marine.colav-simulator.twin-signaling.plist` |
| sango twin player | `com.marine.colav-simulator.twin-player` | `sango/Builds/sango-twin.app --sango-twin-bridge` | `com.marine.colav-simulator.twin-player.plist` |

日志：`deploy/twin/logs/*.log`（launchd StandardOut/Error 重定向；gitignore）。
Unity 侧自身日志照旧 `~/Library/Logs/DefaultCompany/sango/Player.log`。

## urs-webapp 来源与版本

`urs-webapp/build/` = **Unity Render Streaming 官方 tag `3.1.0-exp.9`**（github.com/Unity-Technologies/UnityRenderStreaming）
`WebApp/` 的 TypeScript 构建产物（`npm ci && npm run build`），vendor 进仓库以摆脱 /tmp 不持久依赖。
`urs-webapp/package.json` 是**本仓库重写的最小运行时清单**（upstream 清单漏列 `commander` 等
运行时依赖且混入全量 devDependencies）；`node_modules/` 为 `npm install --omit=dev` 产物
（~5.3MB），已实测 `node build/index.js -p 8080` 独立可跑（`GET /config` 200）。

上游版本核对：`/config` 应答 `{"useWebSocket":true,"startupMode":"public",...}`；构建产物
与官方 tag 的 `WebApp/build/*.js` 逐文件同源（.map 已剥离减体积）。

## 安装（一次性）

```bash
REPO=/Users/marine/Code/Colav-Simulator
mkdir -p "$REPO/deploy/twin/logs"
cp "$REPO/deploy/twin/com.marine.colav-simulator.twin-signaling.plist" \
   "$REPO/deploy/twin/com.marine.colav-simulator.twin-player.plist" \
   ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.marine.colav-simulator.twin-signaling.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.marine.colav-simulator.twin-player.plist
```

前置：`sango/Builds/sango-twin.app` 已构建（Unity batchmode，见
`sango/Assets/Scripts/Editor/TwinBridgeSceneBuilder.cs#BuildTwinPlayer`）；8080 无其它进程占用。

## 验证

```bash
launchctl print gui/$(id -u)/com.marine.colav-simulator.twin-signaling | grep state   # state = running
launchctl print gui/$(id -u)/com.marine.colav-simulator.twin-player    | grep state
curl -s http://127.0.0.1:8080/config                                                   # 信令活
pgrep -fl "sango-twin.app.*sango-twin-bridge"                                          # player 活
```

## 卸载

```bash
launchctl bootout gui/$(id -u)/com.marine.colav-simulator.twin-player
launchctl bootout gui/$(id -u)/com.marine.colav-simulator.twin-signaling
rm ~/Library/LaunchAgents/com.marine.colav-simulator.twin-{signaling,player}.plist
```

## 排障

```bash
tail -50 deploy/twin/logs/twin-signaling.error.log    # 信令起不来看这里（端口占用最常见）
tail -50 deploy/twin/logs/twin-player.error.log
launchctl kickstart -k gui/$(id -u)/com.marine.colav-simulator.twin-player      # 手动重启 player
launchctl kickstart -k gui/$(id -u)/com.marine.colav-simulator.twin-signaling
# 8080 被杂散 node 占用时：lsof -nP -iTCP:8080 -sTCP:LISTEN 找 PID → kill → KeepAlive 自拉起
```

## 与探针的单实例纪律

六支 twin 探针（`tools/sango_twin_{obs,bridge,live,lidar}_probe.mjs`、
`sango_phase3_e2e_probe.mjs`、`sango_twin_camera_probe.mjs`）与用户路径全功能验证
`tools/sango_userpath_probe.mjs` 各自要起**自有** player（bridge 探针例外：launchd
player 即其"外部已起 player"前置）。
launchd player 在跑时会双实例抢信令/页面连接——探针公共模块 `tools/lib/twin_launchd.mjs`
在起自有 player 前 `launchctl bootout` 本服务、退出时 `bootstrap` + `kickstart` 恢复。
探针全绿 = launchd player 共存协议生效的验收（spec #91 前置批验收 3）。
