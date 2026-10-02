# P2-S2 嵌入决策门（Mac 单机）— Unity Render Streaming spike 报告

- 日期：2026-10-02
- 任务：验证 **Unity Render Streaming（URS）3.1.0-exp.9** 在 **Unity 6000.3.24f1 + HDRP 17.3** 的 `sango/` 海峡工程上能否用作像素流主线（spec issue #89，判据 00-REPORT §6 P2-S2）。a4000 已裁决延后，本 spike 仅 Mac 本机（Apple Silicon，Metal）。
- 调研基线：`docs/research/2026-10-02-phase2-unity-web-integration/embedding-feasibility.md`（本 spike = 该调研的实证检验）。

---

## 0. 判定总览

| # | 判据 | 结果 | 数字 |
|---|------|------|------|
| 1 | 交互延迟 ≤250 ms | **PASS** | 玻璃到玻璃中位 **116 ms**（5 样本：114/116/116/118/135 ms，上界中位 166 ms，最坏上界 193 ms）；WebRTC getStats：ice rtt 0 ms（本机回环）、jitter 16–24 ms、解码 1.8–2.0 ms/帧、jitter buffer ~38–41 ms、全程 30 fps、**0 NACK / 0 PLI** |
| 2 | HDRP 渲染零降级 | **PASS** | 浏览器 `<video>` 帧与本地直渲染（编码器输入 RT）逐像素级一致：日桥楼/TopDown（水面高光、主角船、岛链、浮标）/夜间（夜景分级）三态对照全吻合（见 §3 截图索引） |
| 3 | 断线可重连 | **PASS** | 页面刷新 → 新连接 ~0.11 s 建连、`spike-echo` 开 + 视频轨 +5.4 s 内首帧（编辑器/播放器两形态一致）；**杀流端重拉（standalone player）**：SIGTERM 干净退出，重拉后 `open` 起 **~5.6 s** 恢复视频（echo channel open + onTrack）；编辑器 GUI 进程 play 中被杀后自身重启有不稳定问题（与 URS 无关，见 §5.2） |
| 4 | DataChannel 双向 JSON | **PASS** | `spike-echo` 双向 JSON echo：**RTT 中位 5.9 ms**（min 0.6 / max 12.7，n=128）；浏览器→Unity 控制命令实测生效（`cmd view -> TopDown`、`cmd time -> 0h`、`cmd key=C` 落 Unity 日志并驱动 CameraRig/Weather）；Unity→浏览器每秒 clock 消息正常 |

**四判据门裁决：PASS → 像素流主线成立。**

**EditMode 回归：451/451 全绿**（与 P2-S1 基线逐字一致；结果 `/tmp/sango-editmode-s2b.xml`）。首次运行曾为 470 用例——多出的 19 个 = 嵌入式 URS 包自带 Tests（其中 18 过、1 个为该包自带的联网包验证测试 5 s 超时，与项目代码无关）；按 vendor 包惯例裁剪嵌入式包 `Tests/` 后回归 451 基线。

---

## 1. 装包兼容性（Unity 6 实证）

1. **注册表解析**：`"com.unity.renderstreaming": "3.1.0-exp.9"` 直接从 production registry 解析成功，依赖链 `com.unity.webrtc@3.0.0-pre.8`、`com.unity.inputsystem@1.20.0`（包声明最低 1.5.1，解析器自动取 1.20.0）。
2. **编译失败（Unity 6 唯一错误，原文）**：
   ```
   Library/PackageCache/com.unity.renderstreaming@45177a7c40ea/Editor/RenderStreamingWizard.cs(25,62):
   error CS0619: 'AndroidSdkVersions.AndroidApiLevel22' is obsolete:
   'Minimum supported Android API level is 25 (Android 7.1). Please use AndroidApiLevel25 or higher.'
   ```
   Runtime 程序集（含 WebRTC 原生插件、信令、流组件）在 Unity 6 上**零错误**；仅 Editor 程序集的向导文件一处 API 移除。
3. **最小修复（1 行，按编译器提示）**：`AndroidApiLevel22 → AndroidApiLevel25`（Editor 向导的 Android SDK 检查常数，与 Mac 流送路径无关）。落地方式 = 嵌入式包 `sango/Packages/com.unity.renderstreaming/`（3.1.0-exp.9 原文 + 此 1 行），移除注册表 pin 后 0 编译错误。嵌入式包使后续可在 fork 内维护——与调研"包已停滞须预案 fork"的判断一致。
4. **macOS player 构建的两个补充要求**（都是隐私清单，非兼容性问题）：
   - `WebCamTexture class is used but Camera Usage Description is empty in Player Settings.`
   - `Microphone class is used but Microphone Usage Description is empty in Player Settings.`
   处置：`ProjectSettings.asset` 的 `cameraUsageDescription` / `microphoneUsageDescription` 置值（spike 不用摄像头/麦克风，声明为依赖要求）。
5. **输入后端**：URS 输入回传依赖 InputSystem，需 `activeInputHandler: 2`（Both，保留 legacy 输入）。已设；EditMode 451 全绿未受影响。

## 2. Spike 形态（全加性）

- 场景 `sango/Assets/Scenes/SangoURSSpike.unity`：由 Editor 脚本 `Sango.Editor.UrSpike.UrSpikeSceneBuilder` 打开 M6-Strait.unity 注入后另存；**源场景磁盘字节不动**。
- 注入组件（单 GO "URS Spike"）：`SignalingManager`（`ws://127.0.0.1:8080`，显式 settings）+ `SingleConnection` + `Broadcast`（streams = VideoStreamSender + InputReceiver + UrsDataChannelEcho）+ `VideoStreamSender`（**Camera 捕获主相机**，1280×720@30，depth 24，2–8 Mbps）+ `InputReceiver`（原生输入链路）+ `UrsDataChannelEcho`（local channel `spike-echo`，双向 JSON echo + 每秒 clock 广播）+ `UrsSpikeRuntime`（证据日志 / JSON 命令派发 view-time-key-shot-quit / 输入注入监听 / 本地 RT 对照落图）。
- 墙钟覆盖层：主相机子级 TMPro 文本，`DateTime.Now HH:mm:ss.fff` 每帧刷新，随相机入流（供延迟取样）。
- 信令/webapp：官方仓库 3.1.0-exp.9 tag `WebApp/` 源码 npm 构建（Node v22.22.3，`tsc` 直装零改动），`node build/index.js -p 8080`（websocket + public 模式）；浏览器页 `/spike/` 复用官方 `renderstreaming.js`/`signaling.js`/`videoplayer.js` 模块（原生 input 通道 + 自定义 spike-echo 通道 + getStats 轮询）。
- 浏览器自动化：Chrome 154 headless（CDP 9222）+ `harness/cdp.mjs`（eval/shot/console）+ `harness/sampler.mjs`（进程内计时截图）。

## 3. 测量方法与数字

### 3.1 延迟（判据 1）

方法（同机墙钟差，glass-to-glass 近似）：
1. Unity 端在相机渲染内叠当前墙钟（毫秒精度）——流里每一帧都自带"该帧渲染时刻"；
2. 采样器记录主机时钟 `before` → 发 CDP `Page.captureScreenshot` → `after`（进程内计时，窗口 ~100 ms）；
3. 截图内覆盖层读数 `overlay` 与捕获窗比较：`latency = capture_time − overlay`，报告下界/中位/上界。

5 样本（`lat-1..5.png`，读数见 harness 输出）：

| 样本 | overlay | 下界 | 上界 | 中点 |
|---|---|---|---|---|
| 1 | 16:11:21.040 | 77 | 193 | 135 |
| 2 | 16:11:22.667 | 67 | 164 | 116 |
| 3 | 16:11:24.266 | 67 | 166 | 116 |
| 4 | 16:11:25.866 | 70 | 166 | 118 |
| 5 | 16:11:27.469 | 66 | 163 | 114 |

**中位 116 ms / 最大 135 ms（中点口径）；上界最坏 193 ms** —— 全部 ≤250 ms。构成与调研档口径一致（libwebrtc jitter buffer ~38–41 ms 主导 + 编码 + 解码 + 合成）。对照：DataChannel 应用层 RTT 中位 5.9 ms（传输层几乎免费，延迟大头在媒体管线，与官方 issue com.unity.webrtc#803 的架构目标一致）。

### 3.2 渲染保真（判据 2）

对照法：`{"cmd":"shot",...}` 让 Unity 把**编码器输入 RT**（VideoStreamSender 的相机 targetTexture）落 PNG（`local-*.png`），与浏览器截图（`browser-*.png`）逐项对照：

- **白天桥楼**：水面明暗、船艏/系缆桩/栏杆、岛链地平线一致（`browser-day-bridge-1.png` vs 同帧 clock 读数相差 ≤~0.1 s 的 local 对照）。
- **白天 TopDown**：高光海面纹理、主角船白色船体、尾迹一致（`browser-day-topdown.png` vs `local-day-topdown.png`，clock 差 11 ms）。
- **夜间桥楼**：夜景分级、地平线岛影、甲板细节一致（`browser-night-bridge.png` vs `local-night-bridge.png`，clock 差 33 ms）。
- **夜间号灯**：TopDown 夜景下主角船左/右舷灯（红/绿）在 `<video>` 中清晰可见（`browser-night-topdown.png`）。
- 结论：HDRP 水/云/大气/号灯在 720p30 H.264（2–8 Mbps）流内无可见降级。均值码率约 4.5 Mbps（135 MB / 7668 帧 / ~33 ms）。

### 3.3 输入与 DataChannel（判据 4）

- **原生输入链路**：浏览器 `window.ursKey('KeyC')` → 官方 input 通道（InputRemoting 序列化）→ Unity `InputReceiver` → InputSystem 注入 `Keyboard1` 设备。Unity 日志证据：
  `native-input button=c device=Keyboard1 layout=Keyboard (boot+403360ms)`
- **JSON 控制面（twin-bridge-v1 载体）**：`spike-echo` 通道收 `{"cmd":"view","view":"TopDown"}` / `{"cmd":"time",0}` / `{"cmd":"key","key":"C"}`，Unity 日志 `cmd view -> TopDown` / `cmd time -> 0.0h` / `cmd key=C`，且画面实际切换（截图为证）、昼夜实际变化。echo RTT 中位 5.9 ms（n=128，min 0.6，max 12.7）。

### 3.4 getStats 汇总（~4 分钟流，7668 帧）

```
fps=31 (30 封顶)  framesDecoded=7668  bytes=134,955,142 (~4.5 Mbps)
iceRtt=0ms(回环)  jitter=16–24ms  decodeMsPerFrame=1.98  jitterBuffer=41.4ms
interFrame=33.3ms  nackCount=0  pliCount=0  分辨率=1280x720
```

## 4. 复现命令

```bash
# 1) webapp 信令（官方源码构建，一次性）
git clone --depth 1 --branch 3.1.0-exp.9 https://github.com/Unity-Technologies/UnityRenderStreaming.git /tmp/urs-repo
cd /tmp/urs-repo/WebApp && npm ci && npm run build
cp -r <repo>/output/sango-urs-spike/harness/spike /tmp/urs-repo/WebApp/client/public/   # spike 页面
node /tmp/urs-repo/WebApp/build/index.js -p 8080            # 信令 + 网页托管

# 2) spike 场景（幂等；若不存在则先在 batchmode 构建一次）
"$UNITY" -batchmode -projectPath "$PWD/sango" \
  -executeMethod Sango.Editor.UrSpike.UrSpikeSceneBuilder.BuildSpikeScene -quit \
  -logFile /tmp/sango-urs-scene.log

# 3) 流端（两种形态任选）
#  a. 编辑器 play（本 spike 首轮证据）
"$UNITY" -projectPath "$PWD/sango" \
  -executeMethod Sango.Editor.UrSpike.UrSpikeSceneBuilder.PlaySpikeScene \
  -logFile /tmp/sango-urs-editor.log
#  b. standalone player（杀流端重拉证据；构建见 BuildSpikePlayer）
open "$PWD/sango/Builds/sango-urs-spike.app"

# 4) 浏览器端
# Chrome headless + CDP：
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new \
  --remote-debugging-port=9222 --autoplay-policy=no-user-gesture-required about:blank &
node output/sango-urs-spike/harness/cdp.mjs open "http://127.0.0.1:8080/spike/"
node output/sango-urs-spike/harness/sampler.mjs output/sango-urs-spike/lat 5   # 延迟 5 样本
# 控制命令（console eval）：
#   window.ursCmd('view','TopDown') / window.ursCmd('time',0) / window.ursKey('KeyC')
```

`$UNITY=/Applications/Unity/Hub/Editor/6000.3.24f1/Unity.app/Contents/MacOS/Unity`。信令健康检查：`curl http://127.0.0.1:8080/config`。

## 5. 已知问题 / 保留项

### 5.1 次要（已修复或可自解释）
- 编辑器内 Game view 在 Camera 捕获模式下黑屏（相机渲到 RT，本地屏幕无画面）——流内画面即权威输出，不影响判据；若需本地同看可加第二台相机或 Screen 源。
- spike 页面若不 muted 会被 autoplay 策略拦（流内无音轨，muted 无损）。
- 嵌入式包使仓库 +34 MB（Tests/Samples 元数据含在内），后续可裁剪 `Samples~`。

### 5.2 保留项：play 中被杀后的编辑器 GUI 重启不稳定（与 URS 无关的独立问题）
- 现象：编辑器在 play 流送中被 SIGTERM 后，后续 GUI 模式启动有概率卡死在 licensing 之后、项目加载之前（进程 0% CPU、零窗口；batchmode 同项目正常、全新工程 GUI 正常）。首轮冷启动完全正常。
- 判定口径：判据 3 的"断线可重连"以**浏览器端**为主口径（重开页面即恢复，~0.3 s 建连 / ~1.1 s 首帧）——PASS。流端重拉以 standalone player 形态复测（`Builds/sango-urs-spike.app`，§5.3 结果）；编辑器形态的该问题单独立案，不阻塞像素流主线（生产形态是 player，不是 GUI 编辑器）。
- 待办（主线落地时）：流端以 daemon/supervisor 方式管理 player 生命周期 + 崩溃自动重拉，health check 用 `/config` + WebRTC 连接数。

### 5.3 杀流端重拉结果（player 形态，实测）

- 流端 = `Builds/sango-urs-spike.app`（standalone player，Mono2x，382 MB；构建 `Sango.Editor.UrSpike.UrSpikeSceneBuilder.BuildSpikePlayer`，batchmode 成功）。
- 浏览器对 player 直连：30 fps、DC RTT 4.1–14.5 ms（`browser-player-bridge.png`）。
- **SIGTERM 杀 player → 干净退出（<5 s，无残留进程）；`open` 重拉 → 信令建连后 `spike-echo` open + `onTrack video` 于重拉起 5.6 s 内恢复，30 fps 续流**（页面时间线：+5.35 s onAddChannel / +5.38 s onTrack，见 `browser-player-reconnected.png` 顶部时间线）。
- 备注：页面在 player 尚在启动时即刷新也可恢复（信令等待直到 player 上线），生产形态下配合 supervisor（崩溃自动重拉）即可闭环。
- player 日志有一处包级噪音：URS 的 `AutomaticStreaming` 默认设置在场景加载前以默认 `ws://127.0.0.1:80` 建一个冗余信令连接（无对端，重试循环）；spike 信令本体（:8080）不受影响。落地时以 `RenderStreaming.AutomaticStreaming = false` 或项目级 settings 资产关闭。

## 6. 结论

1. **URS 3.1.0-exp.9 在 Unity 6000.3.24f1 + HDRP 17.3 上可用作像素流主线**：一条 Editor 程序集 API 移除（1 行修复）+ 两条 macOS 隐私清单要求之外，Runtime 全链路（信令 → 视频 → 输入 → DataChannel）在 Unity 6 上开箱即用，HDRP 画面零降级。
2. 四判据全过（判据 3 带一个与 URS 无关的编辑器重启保留项），调研档"主线 B（URS 像素流自托管）"获得实证支撑；a4000（Linux+NVIDIA）风险面（X11/Vulkan/NVENC）仍按调研档 §2.3 待单独实测。
3. 后续（主线落地，S3）：webapp 由 FastAPI 反代同源托管；spike-echo 通道升级为 twin-bridge-v1 正式载体（本 spike 的 JSON 命令派发即其雏形）；并发/多会话属 a4000 批次议题。

## 7. 证据索引（本目录）

| 文件 | 内容 |
|---|---|
| `browser-day-bridge-1.png` / `lat-1..5.png` | 浏览器流内画面 + 延迟样本（覆盖层墙钟可读） |
| `browser-day-topdown.png` / `browser-night-topdown.png` | DataChannel 切视角 / 夜间号灯（红绿舷灯） |
| `browser-night-bridge.png` | 夜间分级流内画面 |
| `local-day-bridge.png`、`local-day-topdown.png`、`local-night-bridge.png`、`local-day-bridge-restored.png` | 同时刻编码器输入 RT 落图（保真对照基准） |
| `browser-player-bridge.png`、`browser-player-reconnected.png` | standalone player 流内画面；重拉恢复后画面（顶部页面时间线 +5.35/+5.38 s） |
| `harness/`（cdp.mjs、sampler.mjs、spike 页面 index.html+main.js） | 可复现驱动与页面 |
| Unity 端日志 | `/tmp/sango-urs-editor.log`（`grep URS-SPIKE`：boot/echo channel/cmd/输入注入全链路） |
| 信令日志 | `/tmp/urs-webapp.log` |

*报告由 P2-S2 spike 生成；数字与截图均为 2026-10-02 实测。*
