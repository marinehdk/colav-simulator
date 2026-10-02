# frame-publisher-v1 — Sango 帧发布线上协议（M3 缝钉子②，spec #86）

状态：已冻结（2026-09-28，M3）。方向：**Unity（Sango 场景）→ phase-2 感知宿主**。
实现：`sango/Assets/Scripts/Runtime/FramePublisher.cs`（适配层）+ `Vessels/FramePublisherCore.cs`（元数据组装纯函数，EditMode 已测）+ `Vessels/SangoSeamConfig.cs`（常量与闸）。
验收探针：`tools/sango_zmq_probe.py`（pyzmq；venv 安装见 §4）。

## 1. 传输

- ZeroMQ **PUB**，绑定 `tcp://127.0.0.1:5556`（`SangoSeamConfig.PublisherEndpoint`；localhost only，spec Out of Scope 非 localhost）。
- 订阅方 SUB connect + `subscribe("sango.frame")`（`SangoSeamConfig.PublisherTopic`）。
- 发送高水位 30（订阅端掉线不积压）。
- 库：NetMQ 4.0.1.13（netstandard2.1，**LGPL-3.0**）+ 传递依赖 NaCl.Net 0.1.13（**MPL-2.0**）+ AsyncIO 0.1.69（**MPL-2.0**），未修改 dll 随 `sango/Assets/Plugins/NetMQ/` 分发，许可证全文同目录。（规划材料误记 MIT——实为 LGPL/MPL，均允许未修改库二进制随附分发，已在此更正。NetMQ 首次导入缺传递依赖 NaCl 报 `Unable to resolve reference 'NaCl'`——三个 dll 必须同目录齐备。）

## 2. 帧消息（multipart ×3）

| 段 | 内容 | 校验 |
|---|---|---|
| 1 | topic，恒 `"sango.frame"`（UTF-8） | SUB 过滤键 |
| 2 | `FrameMetadata` JSON（UTF-8） | 键齐全、`jpeg_bytes` == 段3 长度 |
| 3 | JPEG 图像字节 | SOI `0xFFD8` 开头 |

FrameMetadata（`Vessels/FramePublisherCore.cs`）：

```json
{"frame_seq":42,"frame_time_s":12.345,"width":1920,"height":1080,"jpeg_bytes":84213,"source":"sango"}
```

- `frame_seq`：发布器内从 0 单调递增（`DetectionResult.frame_seq` 与之对齐）。
- `frame_time_s`：`Time.timeAsDouble`（秒）。
- 图像：`CameraCaptureBridge` 提供主相机后处理输出，在 ScreenSpaceOverlay/IMGUI 合成前复制到三槽 RenderTexture，异步 GPU 回读与后台 JPEG 编码（quality=60）。尺寸保持玩家窗口像素域，图像不包含 GUI 或旧检测框。
- PUB 慢加入语义照旧：SUB 连上前发的帧丢弃——探针持续收帧，无需握手。

## 3. 开关与零成本（验收故事 5）

- **编译期总闸 `SangoSeamConfig.PublisherEnabled = false`**：默认一切构建 OFF。
- OFF 成本：不建 socket、不起协程，`Update` 仅一次布尔比较（无可测成本，验收故事 5）。
- **启用路径（验收标准路径，不改编译期默认、无需重编译）**：

  ```bash
  # 1) pkill -f 'MacOS/sango'（先清旧实例）
  # 2) 带旗标启动 M1 玩家构建（M1 场景带 FramePublisher 组件）
  ./sango/Builds/sango.app/Contents/MacOS/sango --sango-publisher
  # 3) 另一终端跑探针
  .venv/bin/python tools/sango_zmq_probe.py --count 30   # exit 0 = 验收通过
  # 4) 验收后：Cmd+Q / pkill 播放器 → 默认构建（不带旗标）仍是 OFF
  ```

  `--sango-publisher`（`SangoSeamConfig.PublisherCliFlag`）在 `FramePublisher.Start()` 读 `Environment.GetCommandLineArgs()` 强制 `runtimeEnabled=true`。等价路径：Inspector 勾 `runtimeEnabled` 或运行时调 `StartPublishing()`（编辑器 Play 手动验证用）。
- **回默认 OFF**：不带旗标启动即 OFF（无状态残留；组件序列化值默认 false）。

## 4. 探针依赖（一次性）

```bash
uv pip install pyzmq --python .venv/bin/python   # 2026-09-28 实装 pyzmq==27.2.0（tools-only，未入 pyproject）
.venv/bin/python tools/sango_zmq_probe.py --count 30
```

## 5. 已知边界

- 当前验收目标为本机 Metal/Mono 原生播放器；编辑器离线 Recorder 不作为实时发布性能证据。
- 最小发布间隔0.1s，默认最高10Hz；可配置0.1..2s，过载跳帧。时间戳在采集时锁存，seq单调递增。检测设置可通过可选 `confidence_threshold`（0.01..1）请求推理阈值；旧发布端缺此字段时，服务端使用CLI `--conf`。必需字段与三段 multipart 不变。

## 2026-10-01 纯场景异步路径

主相机通过 Unity `CameraCaptureBridge.AddCaptureAction` 在同一遍 HDRP 渲染内取后处理画面；HDRP负责适配有效视口尺寸。执行一次GPU copy及`CommandBuffer.RequestAsyncReadback`，没有第二次场景 culling/draw。三槽回压、单后台 `ImageConversion.EncodeArrayToJPG` 任务；NetMQ socket始终由主线程发送。

该桥输出已是编码器行序，保留正向输入，不再沿用旧 ScreenCapture 路径的额外翻转。正向/GUI排除的实际证据是 `output/aeolus-workbench-20261001/sensor-frames/` 原始JPEG：天空在上、甲板在下，不含控制文字或旧框；与船载视图相符。旧倒置/黑屏失败存档保留，不用作当前PASS。

停止/resize先注销本组件capture action、失效generation并等待唯一编码任务。CommandBuffer读回没有提前返回request handle，因此仅当本组件仍有pending槽时调用Unity全局`AsyncGPUReadback.WaitAllRequests`，随后释放本组件RT；该teardown等待可能同时等待进程其他读回，正常帧不等待。由CameraCaptureBridge注册字典保留其他订阅者，不关闭全局桥。

新窗口真实1440p性能与其他船检测、模型/参数/源时间戳/返回JSON见本轮原生验收及版本化捕获脚本。10Hz是上限，不保证吞吐；离线编码重复帧不构成更高感知采样率。

## P3-S2 桅杆机位族演进（2026-10-02，spec #90，只加字段）

`FrameMetadata` 只加四字段（`Vessels/FramePublisherCore.cs`；JsonUtility 恒写全字段，
旧接收端宽松消费零影响）：

```json
{"frame_seq":42,"frame_time_s":12.345,"width":640,"height":480,"jpeg_bytes":20480,"source":"sango","mount_id":"mast_ptz_eo","pose_east_m":1.25,"pose_north_m":-2.5,"pose_yaw_deg":90.0}
```

- `mount_id`：桅杆机位标识（observations-v1 §3 引用键；标定表 =
  `sango/Assets/Scripts/Runtime/Vessels/Mast/MastCameraTable.cs` ↔ 后端
  `colav_simulator/core/mast_cameras.py` 双侧同源字面量）。空字符串 = 旧桥楼馈送
  （本字段引入前的语义，零变化）。
- `pose_east_m`/`pose_north_m`/`pose_yaw_deg`：当帧位姿快照——**方案写档**：位姿
  快照旁路进 FrameMetadata（备选是独立旁路通道；载荷最小化故随元数据）。坐标系 =
  Unity 场景系（东=+x、北=+z、yaw 北向东顺时针度），**未加 attached.anchor**
  （发布器不感知数据面锚点，对账由消费方补锚）。**该快照仅诊断/对账用，非
  georef 权威输入**——observations-v1 §5 裁决 (a) 下后端取权威 ownship 状态
  还原当帧相机位姿，本快照不参与。
- 默认源改接：twin 桥（`TwinBridgeService.AttachMastRigWhenOwnShipReady`）在
  own-ship 槽位出现后把 `FramePublisher.sourceCamera` 改接桅杆前向 EO 机位
  `mast_ptz_eo`（PTZ 白光通道，60° HFOV；写档偏差注：EO 环视 ±60° 前向双不含
  正前，正前 = PTZ 档），捕获分辨率覆写 `overrideCaptureSize` = 标定表发布栅格
  640×480（YOLO CPU 预算）。未挂 rig 的构建（Demo 等）零变化。
