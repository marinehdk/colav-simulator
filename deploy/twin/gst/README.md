# DT 像素流 GStreamer 链路 — 运维手册(M5 桥接产品化)

> 适用:Colav-Simulator DT 像素流双路由(`gst-xvfb` 现役 / `legacy-urs` 回退)。
> 设计: `docs/research/2026-10-12-dt-frame-delivery-2k/DESIGN.md` §5;数据:同目录 `notes/01-04`。
> a4000 远程根:`/home/marine.huang/.local/share/colav-twin-renderer/`;gst 工作区 `~/gst-spike/`。

## 1. 拓扑与模式开关

```
gst-xvfb(默认,M5 变体 B,浏览器零改动):
  浏览器(web_gui :8010, Deployment T 视口)
    ↕ WebRTC H264 1080p@30 —— GStreamer webrtcbin(NVENC, GPU1, 容器 gst-base)
    ↕ twin-bridge DataChannel(同一条 PC)—— sender ↔ 回环 TCP 127.0.0.1:18020 ↔ player 桥适配器
  本地 8080 --ssh -L 重映射--> 远程 webapp 8081(浏览器+sender 同室;Unity 挂 8080 闲置)
  player 窗口 1920×1080 相机上屏(ximagesrc 抓 Xvfb :93);启动旗标
  `--sango-twin-bridge --sango-twin-bridge-local --sango-twin-hud-hide`
  (UDS 设计落地为回环 TCP:sender 在 --network host 容器内,免宿主 socket 卷)

legacy-urs(回退,M4 前行为逐字节等价):
  浏览器 ↕ WebRTC H264 —— com.unity.webrtc/URS(NVENC, GPU0)
  本地 8080 --ssh -L--> 远程 webapp 8080 ↔ Unity player(窗口 640×360, 相机走 RenderTexture)
```

**开关 = `deploy/twin/remote-runtime.json` 的 `video_route` 字段**(`legacy-urs` | `gst-xvfb`),改完 `twinctl restart` 生效:

```bash
./deploy/twin/twinctl restart     # 重启进程组并按 video_route 重建路由/隧道
./deploy/twin/twinctl status      # 任意模式显示: 进程 PID + gst 容器/发送器态
```

- gst 分支进程组:display → signaling-8080 → signaling-8081 → player(player_window 档,默认 1920x1080)→ gst 容器+sender;stop 反向(gst 组最先停)。
- 隧道随路由重建:gst = `-L 8080→远程8081(重映射)` + `-L 8081→8081(诊断直连)`;legacy = `-L 8080→8080`。浏览器信令 URL 恒为 ws://127.0.0.1:8080,healthMonitor 探测无需改。
- sender 启动参数:`x11 源、窗口同尺寸、30fps、gop 30、--bridge-port 18020`;码率默认 20000kbps,
  stream_profile 拦截映射(1080p=16000/1440p=20000)。
- **M5 起产品 T 视口在 gst 模式正常可用**(桥已接通);旧「gst 模式禁开产品 T 视口」禁忌废止。

## 2. status 输出解读

```json
{"display":…, "signaling":…, "player":…, "gst": "stopped|running|exited", "gst_sender": "up|down"}
```

- gst 模式多一行 `signaling-8081`(第二 webapp,幂等:手工实例在位时不重复起、不进 STATE,下轮全量重启时收编)。
- sender 日志(远程):`~/gst-spike/bench/spike/sender-gst-<label>.log`(STATUS 行每 10s:ice/conn/enc_frames/keyframes/fku/dc/**bridge/profile**;30fps=每 10s +300 帧;`bridge=up`=player 回环桥通,`profile`=stream_profile 拦截档)。

## 3. 采样纪律(先读再测)

1. M5 起 gst 模式下产品 T 视口正常使用(桥经 sender↔player 回环 TCP 转发);**同一时刻只允许一个浏览器视口 attach**(每开一个新页/换一次页,旧 peer 由 sender 换 peer 拆旧 epoch 兜底,但同窗多页会互相顶替)。
2. CDP 采集(真实视口):**自建会话后必须 Page.reload 页面才 adopt;结束必 reset;脚本退出必 SIGKILL Chrome**(SIGTERM 杀不死 headless Chrome——游魂 peer 在信令室 5s 重发 offer,是 sender SRD 连败的主要来源;sender 已有换 peer 拆旧 + SRD 失败重建重试双防御,仍应避免)。
3. 真实视口回归用 `probe/twin_stream_stats.mjs`(支持 `--seconds N --window W,H`;facade 的 videoStats 快照在通道重开竞态下停更,探针已带 hud-dataset 兜底,`source` 字段标明来源);spike 链用 `probe/spike_cdp.mjs` + `spike/receiver.html`(8090);六场景稳定性用 `probe/twin_stability_monitor.mjs`。
4. headless Chrome CDP 端口:9226(stats/spike_cdp)、9225(stability);跑前确认空闲,跑后确认退出。
5. E1 类 GPU 基线实验须 GPU0 冷却态;**本机重载(仿真后端+多进程)会压浏览器解码 fps**——采样期尽量闲置本机,M0(远程 log `[Sango.M0]` 行)与 sender STATUS 是分责证据(渲染/发送/网络/解码四级定位)。

## 4. 故障口诀

| 症状 | 处置顺序 |
|---|---|
| 黑屏 + fps 0 + 速率 0 | ① `nvidia-smi` 看 GPU0 VRAM(Vulkan low memory 刷屏=显存爆)→ ② `curl -x http://127.0.0.1:7897 -I https://tile.googleapis.com`(代理断;Cesium root.json 失败不自愈,须 `twinctl restart`) |
| gst 模式黑屏 | ① `docker logs gst-base` + `tail ~/gst-spike/bench/spike/sender-gst-*.log`(STATUS 是否 conn=connected/enc_frames 增长/**bridge=up**)→ ② `DISPLAY=:93 xwininfo -root -tree \| grep sango`(窗口应与 player_window 档同尺寸)→ ③ 本地 8080 探活(curl /config,经重映射应命中远程 8081)→ ④ player 日志 `local channel`(TwinBridgeLocalChannel 服务/OPEN) |
| T 视口视频在但控制全无(相机/主题不响应) | 桥断:sender STATUS `bridge=down` 或 player 无 `local channel OPEN` → `twinctl restart`(回环链随组重建;player 端后到者接管,半开自愈) |
| 浏览器连不上流(重试卡) | sender 日志看 `SRD offer reply not ok`(游魂 peer;自动重建重试已内置,持续失败则 `pkill -f sender.py` + `twinctl restart` 重拉);确认本地无残留 headless Chrome(`pgrep -fl headless`) |
| a4000 出网失败(pull/apt/构建) | 走代理 `http://127.0.0.1:7897`(build.sh 已固化);docker 镜像用全路径 `docker.io/library/ubuntu:24.04` |
| 流卡住后不恢复 | reload 浏览器页(新 offer→新管线→IDR);gst 链 PLI 不翻译,恢复上界 = gop 周期(30fps gop30 = 1s) |
| Chrome 预热冻结 | 每次新页面 t≈12-14s 有 2-4 个低分样本(确定性复现,发送侧无隙)——短窗(≤60s)采样占比会显著偏低,判达标用 ≥190s 窗 |

## 5. 回退步骤(由轻到重)

1. **模式切换(分钟级,首选)**:`remote-runtime.json` → `"video_route": "legacy-urs"` → `./deploy/twin/twinctl restart`。stop 阶段自动停 sender+容器+8081;重启后即 URS 原链路(窗口 640×360,player_window 仅 gst 路由透传)。M5 回退演练实证可用(新 player 下 legacy 视口正常出流)。验证:`twinctl status`(三进程 + gst exited)+ 视口 ≥25fps。
2. **部署脚本回退**:`git checkout HEAD -- deploy/twin/renderer_control.py deploy/twin/remote_control.py`(或 revert 提交)+ rsync 远程 + `twinctl restart`(M5 起改动全部 mode 门控,此层通常不需要)。
3. **player 恢复**(仅 player 自身损坏):`rsync -a player-backup-m5-20261013/ ~/.local/share/colav-twin-renderer/player/` + `twinctl restart`(M5 前基线=player-backup-m5-20261013 的上一份 player-backup-cesiumfix-20261012)。
4. **本地仓库**:`git reset ae18f719`(M5 批改动在 sango C#/测试、deploy/twin 两脚本、gst sender/probe、README、模板)。

## 6. 已知环境事实(勿重复排查)

- **legacy 路径 native 帧交付缺陷(终局判定 2026-10-13)**:attach 期渲染被采集钟 pacing 至 ~30fps、per-attach ~2min 后与流双衰减至 26-27 滞留(com.unity.webrtc 3.0.0-pre.8 native 路径,包停更,归档直方图 87,211s 零秒 55-60)。**gst 路径 attach 期 M0 渲染恒 60**(M5 实测 200s×多轮死平)——这就是切默认的依据。
- **同机负载/WiFi 微突发是浏览器解码 fps 的地板**(M5 实测):本机跑仿真后端+重会话时,headless 探针 fpsGe29 落在 65-75%(偶发 4-16fps 深坑与本机 CPU 峰及 0.7-2.5% 微突发 loss tick 相关);链路四级证据全绿(sender 30.00fps 死平/零 PLI/零丢帧、rtt 3-5ms、解码 2-3ms、渲染 60)。同口径 legacy 基线=28.1%(fps 25-27 平台+悬崖)。**轻载复测或真前台浏览器观感为准**。
- **GPU0 热学天花板**:1440p60 持续渲染 ~8-25min 后 SW 热节流;1080p 档无此问题(~79W,600s 热平衡 85-88°C 稳定)。1440p 长时运营前置 = 物理散热整改(笔记 03 §5)。
- WiFi 微突发丢包:本机→路由→a4000 偶发 15-60 包突发,webrtcbin 无 NACK,恢复等 IDR;gop=30 把代价压到 ≤1s。
- webrtcbin 不翻译 PLI/FIR→force-keyunit(1.24.2);无 goog-remb;公网化需换 webrtcsink+pacing(DESIGN R9)。
- 浏览器上行 candidate 的 sdpMid/sdpMLineIndex 互换是产品既有怪癖(peer.js:34),sender 侧已容错。
- **HUD 元素**:deployment 工作面的活 HUD 是 `#deploymentTwinHud`(renderHud 每 tick 写 `SIGNAL · WxH · FPS · Mb/s`);`#twinStatusLine` 在该工作面不被更新(静态初始文本)。CDP 探针读视频指标优先 `#deploymentTwinVideo` 的 dataset(receivedFps/dropRatio 等,每 250ms 刷新),`window.__deploymentTwin` facade 在通道重开竞态下可能钉死死 epoch 的快照(client 引用仍活)。
- player 日志真实路径 = 远程 `~/.local/share/colav-twin-renderer/logs/unity-player.log`(非 player/Logs/);M0 帧率行 `[Sango.M0] fps=…` 在出片模式(hud-hide)下照常输出(FpsProbe 只静默 IMGUI)。

## 7. spike 数据存档

- 本地:`deploy/twin/gst/spike/results/`(m2/m3/m4 按里程碑子目录;SDP 语料在 `results/*/sdp/`)+ `deploy/twin/gst/bench/`(M1 基准)。
- 远程:`~/gst-spike/bench/spike/`(sender/wslog 原始日志,容器 /out 卷)。需要回收时 rsync 回本地 results 再清理远程。
- SDP 差异台账:`spike/sdp-diff.md`(webrtcbin vs Unity 差异 D1-D9 + 怪癖 Q1-Q6)。

## 8. 检测分流(--detect-tap,DT 视口 YOLO)

sender 可选把用户所见帧分流喂给 mac 上的 YOLO 检测服务(检测框随遥测 WS `viewport_detections` 键广播绿框):**默认关**——`--detect-tap` 缺省时管线逐链路不变(tee 都不插)。

```
ximagesrc → cf_raw(240Hz 采样门控)┬→ vconv → NV12 → NVENC → RTP → webrtcbin   (主路,不变)
                                   └→ tee → queue(leaky=downstream, max-size-buffers=2)
                                           → videoconvert → videoscale
                                           → capsfilter(video/x-raw, 1280x720)
                                           → jpegenc(quality=60)
                                           → appsink(max-buffers=1, drop=True)
                                             → 独立线程节流(--detect-rate,默认 5Hz)
                                             → ZMQ PUB bind --detect-endpoint(默认 tcp://127.0.0.1:5556, SNDHWM 30)
```

ZMQ 消息 = frame-publisher-v1 三段式(`sango/Docs/contracts/frame-publisher-v1.md`):
`b"sango.frame"` + FrameMetadata JSON `{frame_seq(自增), frame_time_s(=buffer.pts 秒), width:1280, height:720, jpeg_bytes, source:"twin-viewport"}` + JPEG 字节。

### 8.1 容器装 pyzmq(一次性)

```bash
docker exec -e https_proxy=http://127.0.0.1:7897 -e http_proxy=http://127.0.0.1:7897 \
  gst-base pip3 install pyzmq
```

(未装 pyzmq 时默认路径照常;开 tap 后 sender 日志报 `detect tap disabled: pyzmq unavailable`。)

### 8.2 sender.py 更新步骤(挂载直读,不 docker cp)

`run.sh` 把 a4000 宿主 `~/gst-spike/gst` **只读**挂载到容器 `/gst`(renderer_control.py 以 `/gst/sender/sender.py` 启动),所以更新 = 推文件到宿主挂载源 + 重拉 sender:

```bash
# 1) 仓库文件 → a4000 宿主挂载源(容器内 /gst/sender/sender.py 即时可见新内容)
scp deploy/twin/gst/sender/sender.py a4000:~/gst-spike/gst/sender/sender.py
# 2) 重拉 sender(容器不动;renderer_control pkill 旧进程后按新文件启动)
./deploy/twin/twinctl restart
```

### 8.3 启用(任选其一)

- 声明式(推荐):`remote-runtime.json` → `"detect_tap": true` → `./deploy/twin/twinctl restart`。经 SSH env `TWIN_GST_DETECT_TAP=1`(`TWIN_GST_DETECT_RATE` 同理)透传给 renderer_control,给 sender 追加旗标。
- 手工:`docker exec gst-base pkill -f sender.py` 后按 §2 命令行 exec 启动,追加 `--detect-tap --detect-rate 5 --detect-endpoint tcp://127.0.0.1:5556`。
  ⚠️ sender 即容器 PID1:pkill 后容器随退(exit 137),须走 `twinctl start` 重造容器(其内部含 docker run)。

### 8.4 mac 侧消费链(免会话)

`remote_control.py` gst 路由隧道含 `-L 127.0.0.1:15556:127.0.0.1:5556`(mac 15556 → a4000 容器 host netns 5556)。**常规入口=web"海图显示→YOLO 检测"勾选**:app.js POST `/api/viewport-detection-engine` 让后端拉起/停掉检测器(detached,pidfile `deploy/twin/logs/detector.pid`);检测器把结果 POST 到**免会话端点** `/api/viewport-detections`,后端路由进当前活动会话——**会话 reset/新建零重接线**。运维旁路=`./deploy/twin/detectctl start|stop|status`(与后端引擎共管 pidfile);等价手工命令:

```bash
.venv-detector/bin/python tools/sango_detector_service.py \
  --endpoint tcp://127.0.0.1:15556 \
  --out tcp://127.0.0.1:15557 \
  --viewport-forward-url http://127.0.0.1:8010/api/viewport-detections
```

(按会话定向前向仍可用:`/api/sessions/<session_id>/viewport-detections`。)

后端把最新一帧存会话级缓存,随遥测 WS 顶层键 `viewport_detections`(schema `viewport_detections@1`,received_at 超 2s 键整体缺省)广播;模型见 `colav_simulator/schemas/viewport_detections_v1.py`。

### 8.5 a4000 GPU 检测器(20261015 上位,远程模式)

用户裁决:检测器部署 a4000 GPU(**GPU1 推理,Unity 渲染占 GPU0;不动驱动,marine 用户级安装**)。mac 后端以 `TWIN_VIEWPORT_DETECTOR_REMOTE=a4000` 启动时,engine 端点(`/api/viewport-detection-engine`)改走 ssh 托管:

- a4000 侧(一次性,已完成):`~/twin-detector-venv`(torch 2.5.1+cu121/ultralytics/sahi/pyzmq)+ 脚本 `~/twin-detector/sango_detector_service.py`;权重 `yolov8s.pt` 首启自动下载。
- 引擎启动命令(常量在 `gui_server/main.py:_REMOTE_DETECT_CMD`):`CUDA_VISIBLE_DEVICES=1 … --device cuda:0 --model yolov8s.pt --slice-size 640 --pidfile detector.pid`——**SAHI 切片推理**(720p→640×640×6 片,小目标召回 +17%)。
- 探活=远端 pidfile(`~/twin-detector/detector.pid`,serve 启动自写/退出自清);**不要用 pgrep -f 裸模式**(ssh/bash 包装进程自匹配假阳性)。
- 结果回传走 `remote_control.py` 常驻反向隧道 `-R 127.0.0.1:18010:127.0.0.1:8010`(a4000:18010 → mac:8010):检测器 POST `http://127.0.0.1:18010/api/viewport-detections`。**渲染栈 stop 会拆隧道**(remote_control stop 语义),期间 POST 丢帧不致命,start 后自愈。
- mac 8010 启动须带 env:`TWIN_VIEWPORT_DETECTOR_REMOTE=a4000 nohup .venv/bin/colav-sim serve --port 8010 …`(不带=回退本地 mac CPU 模式)。远程启动会先收口本地残留实例,防双推理双 POST。
- 无观看者时 sender tap 不发帧(管线懒构建),检测器空转 recv 超时循环属正常态;日志 `~/twin-detector/logs/detector.log`。
- a4000 shell 有 http_proxy,curl 测 18010 须 `--noproxy "*"`。
