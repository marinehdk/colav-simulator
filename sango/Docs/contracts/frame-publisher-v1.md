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
- 图像：逐帧全屏 `ReadPixels` → `EncodeToJPG(quality=60)`（场景渲染分辨率 = 玩家窗口分辨率）。
- PUB 慢加入语义照旧：SUB 连上前发的帧丢弃——探针持续收帧，无需握手。

## 3. 开关与零成本（验收故事 5）

- **编译期总闸 `SangoSeamConfig.PublisherEnabled = false`**：默认一切构建 OFF。
- OFF 成本：`FramePublisher.OnEnable` 早退——不建 socket、不起协程、Update 无逻辑，零每帧开销。
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

- 编辑器 batchmode 无屏，`ReadPixels` 不可用——发布验收只在玩家构建跑（本协议 §3 路径）。
- 逐帧发布未限流：感知宿主按需丢弃即可（帧带 seq/time，R3 异步消费设计不变）。
