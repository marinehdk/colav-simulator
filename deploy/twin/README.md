# Twin runtime — launchd 双服务（spec #91 前置批）

Deployment 选 T 后视口无画面的根因：URS 信令（:8080）与 sango twin player 都是手动进程，
退出/重启后无人拉起，浏览器（8010 前端）停在"信令活着、player 不在"的空等态。本目录把
两个进程装成用户域 LaunchAgent 统一管理。

**运行策略（2026-10-06 起）：默认不自启。** plist 为 `RunAtLoad=false` + `KeepAlive=false`
——开机/登录不拉起、杀进程不复活。人工可用 `deploy/twin/twinctl start`；
Deployment 选 **DT** 时，WEB 通过当前会话的 `/api/sessions/{session_id}/twin/start`
启动信令与 player，再连接 live 数据流。暂停保留连接；FINISHED/FAILED、Reset/会话替换
和后端正常退出会异步停掉本会话启动的双服务，停止命令不会阻塞仿真线程。
切回海图仅断开该视口，后台保留到会话结束；再次选 DT 可重新连接。
此自动启停限当前 macOS 本地 runtime；Evaluation 的封存回放仍走既有连接流程。

## A4000 远程渲染

当前已选择仅迁移 Unity 渲染/编码。仿真后端与 WEB 留本机；浏览器通过 SSH 转发的
信令连接 A4000，媒体走 WebRTC。启用 `remote-runtime.json` 后，`twinctl` 自动使用远端
控制器；`remote-runtime.example.json` 是当前部署的端点模板。

- 隔离路径：`/home/marine.huang/.local/share/colav-twin-renderer`，不使用或覆盖 MASS-L3 checkout。
- 本机 `127.0.0.1:8080` → A4000 信令；A4000 `127.0.0.1:18010` → 本机后端 `127.0.0.1:8010`。
- Linux/Vulkan 使用 GPU 0、NVENC H.264；虚拟显示 `:93` 不在本机显示 Unity 窗口。
- `LD_PRELOAD` 仅对播放器设置系统 `libstdc++`，修复已实测的 Unity/WebRTC NVENC 初始化符号冲突。
- 完成/失败/Reset：仅停止本服务记录的 player、signaling、Xvfb 进程组并关闭自有 SSH 通道。
- 本机默认禁止自动启动本地 Unity；仍可移走机器配置恢复本地模式。

**WEB 画质与隐藏窗口运行**：player 以 `--sango-web-only -force-metal` 启动，正常 GPU
渲染循环保留；播放器在启动阶段禁止窗口激活并隐藏自身窗口。流相机启用 HDRP TAA，
编码器发送目标 30 fps，渲染上限 60 fps；默认 1920×1080@30，Deployment 根据
实际视口像素协商 2560×1440@30。连续 5 个实测样本低于 26 fps 或解码丢帧超过 3%
时降至 1080p，视口改变后重新选择档位。HUD 显示接收分辨率、解码 fps 和接收码率，
不再将 Unity Update 帧率和 live 固定零延迟作为视频质量指标。

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

bootstrap 后服务仅注册不运行（RunAtLoad=false）——首次拉起用 `deploy/twin/twinctl start`。

## 启停（twinctl）

```bash
deploy/twin/twinctl start     # 信令→player 依次拉起（未注册则先 bootstrap）
deploy/twin/twinctl stop      # player→信令依次 bootout（杀进程亦不会复活）
deploy/twin/twinctl restart
deploy/twin/twinctl status    # 注册/运行态 + 8080 探活 + player 进程
```

原生 launchctl 等价：start = `bootstrap`（如未注册）+ `kickstart`；stop = `bootout`。

## 验证

服务 start 后：

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
# 8080 被杂散 node 占用时：lsof -nP -iTCP:8080 -sTCP:LISTEN 找 PID → kill → twinctl start 重新拉起（不自拉）
# 进程（含 player 界面 Cmd+Q / kill -9）退出后不会复活（KeepAlive=false）——恢复用 twinctl start
```

## 与探针的单实例纪律

六支 twin 探针（`tools/sango_twin_{obs,bridge,live,lidar}_probe.mjs`、
`sango_phase3_e2e_probe.mjs`、`sango_twin_camera_probe.mjs`）与用户路径全功能验证
`tools/sango_userpath_probe.mjs` 各自要起**自有** player（bridge 探针例外：launchd
player 即其"外部已起 player"前置）。
launchd player 在跑时会双实例抢信令/页面连接——探针公共模块 `tools/lib/twin_launchd.mjs`
在起自有 player 前 `launchctl bootout` 本服务、退出时 `bootstrap` + `kickstart` 恢复。
探针全绿 = launchd player 共存协议生效的验收（spec #91 前置批验收 3）。
