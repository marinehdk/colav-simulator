# DT 像素流 GStreamer 链路 — 运维手册(M4 产品化收尾)

> 适用:Colav-Simulator DT 像素流双路由(`legacy-urs` 现役 / `gst-xvfb` 过渡)。
> 设计: `docs/research/2026-10-12-dt-frame-delivery-2k/DESIGN.md` §5;数据:同目录 `notes/01-04`。
> a4000 远程根:`/home/marine.huang/.local/share/colav-twin-renderer/`;gst 工作区 `~/gst-spike/`。

## 1. 拓扑与模式开关

```
legacy-urs(默认,现役产品):
  浏览器(web_gui :8010, Deployment T 视口)
    ↕ WebRTC H264 1080p@30 —— com.unity.webrtc/URS(NVENC, GPU0)
  本地 8080 --ssh -L--> 远程 webapp 8080 ↔ Unity player(窗口 640×360, 相机走 RenderTexture)

gst-xvfb(M3 达标的过渡路由, Xvfb 屏幕旁路):
  浏览器(spike: receiver.html @8090;生产重映射见 DESIGN §5.3)
    ↕ WebRTC H264 —— GStreamer webrtcbin(NVENC, GPU1, 容器 gst-base)
  本地 8081 --ssh -L--> 远程 webapp 8081(隔离信令室)↔ sender(容器内)
  player 窗口 2560×1440 相机上屏(ximagesrc 抓 Xvfb :93);Unity URS 挂线闲置(8080 室无 offer)
```

**开关 = `deploy/twin/remote-runtime.json` 的 `video_route` 字段**(`legacy-urs` | `gst-xvfb`,默认 legacy),改完 `twinctl restart` 生效:

```bash
./deploy/twin/twinctl restart     # 重启进程组并按 video_route 重建路由
./deploy/twin/twinctl status      # 任意模式显示: 进程 PID + gst 容器/发送器态
```

- legacy 分支与 M4 前行为逐字节等价:窗口 640×360、单 webapp 8080、无 gst 容器(start 不触碰 docker)。
- gst 分支进程组:display → signaling-8080 → signaling-8081 → player(2560×1440)→ gst 容器+sender(DESIGN §5.3 顺序);stop 反向(gst 组最先停)。
- `stop/restart` 在**任何**路由下都会清场 gst 组(sender→容器 stop→8081 webapp),保证停完无残留组——这是 legacy 定义「无 gst 容器」的一部分。
- sender 启动参数 = M3 达标档:`x11 源、窗口同尺寸、30fps、gop 30、CBR 20000kbps`;1080p 档手动实验:
  `ssh a4000 'TWIN_VIDEO_ROUTE=gst-xvfb TWIN_PLAYER_WINDOW=1920x1080 TWIN_GST_BITRATE=16000 python3 ~/.local/share/colav-twin-renderer/renderer_control.py restart-player'`
  (restart-player 不动 display/signaling;但 sender 尺寸跟随窗口,需 `twinctl restart` 或手动重拉 sender)

## 2. status 输出解读

```json
{"display":…, "signaling":…, "player":…, "gst": "stopped|running|exited", "gst_sender": "up|down"}
```

- gst 字段来自 `docker inspect`(STATE pids json + docker inspect 双轨);**`exited` 即 docker 语义的 stopped**(终态约定显示 exited)。
- gst 模式多一行 `signaling-8081`(第二 webapp,幂等:手工实例在位时不重复起、不进 STATE,下轮全量重启时收编)。
- sender 日志(远程):`~/gst-spike/bench/spike/sender-gst-<label>.log`(STATUS 行每 10s:ice/conn/enc_frames/keyframes;30fps=每 10s +300 帧)。

## 3. 采样纪律(先读再测)

1. **gst 模式采样期间,8080 信令室必须无任何浏览器 attach**——任何真实 DT 视口 attach 都会触发 Unity `CreateTrack()` → 相机转 RenderTexture → Xvfb 画面冻结,并让 URS 1080p 编码污染 GPU0/CPU 基线(`VideoStreamSender.cs:574/584`)。前置检查:本地 `lsof -nP -iTCP:8080` 无浏览器 ESTAB;事后检查 player.log 无新 offer/track Signaling 行。
2. **同一信令室同一时刻只允许一个 answerer**(Unity 与 gst sender 永不同室;8080/8081 隔离即为此设计)。
3. CDP 采集(真实视口):**自建会话后必须 Page.reload 页面才 adopt;结束必 reset**。脚本已内置(probe/ 下)。
4. 真实视口回归用 `probe/twin_stream_stats.mjs`;spike 链用 `probe/spike_cdp.mjs` + `spike/receiver.html`(8090);六场景稳定性用 `probe/twin_stability_monitor.mjs`。
5. headless Chrome CDP 端口:9226(stats/spike_cdp)、9225(stability);跑前确认空闲,跑后确认退出(spike_cdp.mjs 结尾无 exit,手动杀;stats 已修)。
6. **E1 类 GPU 基线实验必须在 GPU0 冷却态跑**(1440p 连续渲染超 ~8min 进热节流,见 §6);pidstat 用 `docker run --pid=host` 装 sysstat(宿主无权限,模板见笔记 03)。

## 4. 故障口诀

| 症状 | 处置顺序 |
|---|---|
| 黑屏 + fps 0 + 速率 0 | ① `nvidia-smi` 看 GPU0 VRAM(Vulkan low memory 刷屏=显存爆)→ ② `curl -x http://127.0.0.1:7897 -I https://tile.googleapis.com`(代理断;Cesium root.json 失败不自愈,须 `twinctl restart`) |
| gst 模式黑屏 | ① `docker logs gst-base` + `tail ~/gst-spike/bench/spike/sender-gst-*.log`(STATUS 是否 conn=connected/enc_frames 增长)→ ② `DISPLAY=:93 xwininfo -root -tree | grep sango`(窗口应为 2560×1440)→ ③ 本地 8081 隧道在否(`lsof -iTCP:8081`)→ ④ 8080 室是否有浏览器 attach(纪律 1,画面冻结首要嫌疑) |
| a4000 出网失败(pull/apt/构建) | 走代理 `http://127.0.0.1:7897`(build.sh 已固化);docker 镜像用全路径 `docker.io/library/ubuntu:24.04` |
| 流卡住后不恢复 | reload 浏览器页(新 offer→新管线→IDR);gst 链 PLI 不翻译,恢复上界 = gop 周期(30fps gop30 = 1s) |
| Chrome 预热冻结 | 每次新页面 t≈12-14s 有 2-4 个低分样本(fps 5-12,确定性复现,发送侧无隙)——短窗(≤60s)采样占比会显著偏低,判达标用 ≥190s 窗 |

## 5. 回退步骤(由轻到重,DESIGN §6.4)

1. **模式切换(分钟级,首选)**:`remote-runtime.json` → `"video_route": "legacy-urs"` → `./deploy/twin/twinctl restart`。stop 阶段自动停 sender+容器+8081;重启后即 URS 1080p 原链路(窗口 640×360)。验证:`twinctl status`(三进程 + gst exited)+ 视口 1080p ≥29fps。
2. **部署脚本回退**:`git checkout HEAD -- deploy/twin/renderer_control.py deploy/twin/remote_control.py`(或 revert 提交)+ rsync 远程 + `twinctl restart`(M4 起改动全部 mode 门控,此层通常不需要)。
3. **player 恢复**(仅 player 自身损坏):`rsync -a player-backup-cesiumfix-20261012/ ~/.local/share/colav-twin-renderer/player/` + `twinctl restart`。
4. **本地仓库**:`git reset 0e2c2145`(本批工作全部在 `deploy/twin/gst/`、`deploy/twin` 两脚本、`remote-runtime.example.json`、docs)。

## 6. 已知环境事实(勿重复排查)

- **legacy 路径 per-attach ~2min 交付悬崖(M4 实测,三遍复现含全新 player)**:真实视口连续流 ~105-130s 后 URS 交付从 ~30fps 落到 ~26-27fps 并滞留至 teardown;渲染侧全程 60fps、player CPU 平坦 ~220%、零丢包、decode 2-3ms、Unity 无异常日志、Cesium 稳——衰减在 com.unity.webrtc 交付路径内部。既往基线证据(29.8fps 稳/93-95% ≥29)全部来自 ≤60s 窗与 90s×6 场景(场景间 teardown 会重置悬崖),从未覆盖 ≥3min 连续窗。**gst 路径无此悬崖**(M3 190s×多轮 95.8%,sender 精确 30.00fps)。附:产品档位逻辑决定任何 ≥720p 视口初始必请求 1440p(~20s@21-25fps)再自动降 1080p(视口 <720p 才直接 1080p),连续窗采样前 ~20s 必含 1440p 段。
- **GPU0 热学天花板**:1440p60 持续渲染 ~8-25min 后 RTX A4000(SLOT 散热 ~100W)进 SW 热节流,M0 掉 44-56fps(对流无影响,渲染仍 >30fps 采集钟);1080p 档无此问题(~90W)。1440p 长时运营前置 = 物理散热整改(笔记 03 §5)。
- **WiFi 微突发丢包**:本机→路由→a4000 路径偶发 15-60 包突发(~0.02%),webrtcbin 无 NACK,恢复等 IDR;gop=30 把每次突发代价压到 ≤1 个样本。freezeCount≤2 是环境依赖项,不是链路缺陷。
- webrtcbin 不翻译 PLI/FIR→force-keyunit(1.24.2);无 goog-remb;公网化需换 webrtcsink+pacing(DESIGN R9)。
- 浏览器上行 candidate 的 sdpMid/sdpMLineIndex 互换是产品既有怪癖(peer.js:34),sender 侧已容错。
- **HUD 元素**:deployment 工作面的活 HUD 是 `#deploymentTwinHud`(renderHud 每 tick 写 `SIGNAL · WxH · FPS · Mb/s`,SIGNAL OK=活态);`#twinStatusLine`("TWIN LIVE" 文案)在该工作面不被更新(静态初始文本),属另一工作面的元素,勿以其判活。

## 7. spike 数据存档

- 本地:`deploy/twin/gst/spike/results/`(m2/m3/m4 按里程碑子目录;SDP 语料在 `results/*/sdp/`)+ `deploy/twin/gst/bench/`(M1 基准)。
- 远程:`~/gst-spike/bench/spike/`(sender/wslog 原始日志,容器 /out 卷)。需要回收时 rsync 回本地 results 再清理远程。
- SDP 差异台账:`spike/sdp-diff.md`(webrtcbin vs Unity 差异 D1-D9 + 怪癖 Q1-Q6)。
