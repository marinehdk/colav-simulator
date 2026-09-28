# M3 build log — 四颗 phase-2 缝钉子（spec #86）

日期：2026-09-28。执行：Sango M3（phase-1 末个里程碑）。前序：#80-#85 已闭（HEAD 16a71823）。
规则：EditMode 全绿 → 双场景重建 exit 0 → 双玩家构建 exit 0 → 探针验收（发布器临时启用 → 30 帧 → 回默认 OFF）。

## 0. 交付物总览

| 钉子 | 文件 | 测试 |
|---|---|---|
| ④ DetectionResult 契约 | `sango/Assets/Scripts/Runtime/Vessels/DetectionResult.cs` + `sango/Docs/contracts/detection-result-v1.md` | `DetectionResultRoundTripTests`（4） |
| ③ ColavTelemetry compact-v1 契约 | `sango/Assets/Scripts/Runtime/Vessels/ColavTelemetry.cs` + 真实 fixture `sango/Assets/Tests/Fixtures/telemetry-sample.json` | `ColavTelemetryDeserializeTests`（4） |
| ② FramePublisher（ZMQ PUB，默认 OFF） | `Runtime/FramePublisher.cs` + `Vessels/FramePublisherCore.cs` + `Vessels/SangoSeamConfig.cs` + 协议文档 `sango/Docs/contracts/frame-publisher-v1.md` | `FrameMetadataTests`（3，无 socket） |
| ① DetectionOverlay + 投影纯函数 | `Runtime/DetectionOverlay.cs` + `Vessels/OverlayProjection.cs` | `OverlayProjectionTests`（5） |
| 验收探针 | `tools/sango_zmq_probe.py`（pyzmq SUB；随 M3 交付，PLAN §5 M3 验收 2） | 集成验收（§4） |

新增测试 16：EditMode 套件 108 → **124**（§2）。

## 1. Fixture provenance（真实录制，非合成）

- 2026-09-28 本机实跑后端：`.venv/bin/python -m uvicorn gui_server.main:app --host 127.0.0.1 --port 8731`；
  `POST /api/sessions {scenario_id:"head_on", validation_rule_id:"rule14", algorithm_id:"vo", tracker_id:"god", record_replay_trace:false}`
  → session `bd4e1404-ac39-4986-b1ca-d50676d612b0` → `POST .../start` →
  websockets 连 `ws://127.0.0.1:8731/ws/sessions/{id}?transport=compact-v1` 抓稳态消息（seq 54，sim_time 26.5s，state RUNNING，static_included=false，紧凑后 ~17.6 KB）→ 原样落盘
  `sango/Assets/Tests/Fixtures/telemetry-sample.json`（indent=1 排版，**结构零改动、零合成字段**）。
- 结构自证（录制时校验）：`transport.schema_version=="colav.telemetry.compact@1"`；truth 2 船均无 measurements/tracks/colav 三键（compact 剥字段，gui_server/main.py:178-181）；本船 id 0/mmsi 100/ψ=π/4，目标 id 1/mmsi 101/ψ=-3π/4，均 sog 7 m/s。
- 契约声明与剥字段事实一致：`ColavTelemetry` 必填按 compact 子集（PLAN §8 风险 5），未声明键 JsonUtility 静默跳过。

## 2. EditMode 套件

| 轮 | 结果 | 记录 |
|---|---|---|
| RED（stub 抛 NotImplementedException） | **无有效运行**：编写期间源文件两处 `using` 漏行导致编译失败（CS0246/CS0103），套件未能启动；教训=Unity 批跑期间勿动 Assets 源码。RED 以"测试先行 + stub 编译"形式执行，未取得逐用例失败记录（偏差，如实记录） | /tmp/m3-unity-red.log |
| GREEN 第 1 轮 | **123/124**：唯一失败 `ColavTelemetryDeserializeTests.Fixture_TruthShips_TwinConsumedFields`——期望值误用了 seq 0 首帧（east 39500）而 fixture 是 seq 54 稳态帧（船已航行至 east 39633.0）；期望值回填录制事实后修正。NetMQ/AsyncIO 导入编译零错误 | /tmp/m3-tests-green.xml |
| GREEN 第 2 轮（最终闸） | **124/124 全绿（exit 0）**：108 既有 + 16 新增（DetectionResultRoundTripTests 4 · ColavTelemetryDeserializeTests 4 · FrameMetadataTests 3 · OverlayProjectionTests 5）。NetMQ/NaCl/AsyncIO 三 dll 导入编译零错误 | /tmp/m3-tests.xml |

TBD 最终轮计数。

## 3. Transport 决策：NetMQ 真正 ZMQ PUB（未走 TCP 回退）

- NetMQ 4.0.1.13 + AsyncIO 0.1.69 以未修改 netstandard2.0 dll 随 `sango/Assets/Plugins/NetMQ/` 分发；批跑导入/编译/玩家构建全过，batchmode 并不敌对，无需 TCP 回退。
- **许可更正**：规划材料称"MIT"——实为 NetMQ **LGPL-3.0**、AsyncIO **MPL-2.0**。未修改库二进制随附 + 许可证全文同目录 + THIRD_PARTY_NOTICES.md 增节，合规（LGPL §4/5 可替换库语义；MPL 文件级 copyleft）。
- 线上协议（冻结于 frame-publisher-v1.md）：PUB bind `tcp://127.0.0.1:5556`，3 段 multipart
  `["sango.frame"][FrameMetadata JSON][JPEG 字节]`，HWM 30，JPEG quality 60（全屏 ReadPixels→EncodeToJPG）。
- 默认 OFF：`SangoSeamConfig.PublisherEnabled=false` 编译期总闸；OFF 时 OnEnable 早退（无 socket、无协程、Update 空）。
- 启用路径（不改默认、不重编译）：玩家命令行 `--sango-publisher`（Start() 读 GetCommandLineArgs 强制 runtimeEnabled）；等价 Inspector 勾选 / StartPublishing()。

## 4. 探针验收（PLAN §5 M3 验收 2）

步骤（全部实际执行，输出逐字见 §7）：

1. `pkill -f 'MacOS/sango'`（清旧实例）
2. `./sango/Builds/sango.app/Contents/MacOS/sango --sango-publisher &`（M1 玩家构建，发布器启用）
3. `.venv/bin/python tools/sango_zmq_probe.py --count 30` → **exit 0**，30 帧 SOI/jpeg_bytes 全过
4. `pkill -f 'MacOS/sango'`（验收毕）；默认构建不带旗标 = 发布器回 OFF（无状态残留，无需重建）

探针依赖一次性安装：`uv pip install pyzmq --python .venv/bin/python`（pyzmq 27.2.0，tools-only，未入 pyproject）。

**正向运行**（`--sango-publisher` 玩家 + 探针）：`PROBE_EXIT=0`，玩家侧 Player-prev.log 同步证据
`[Sango.M3] publisher enabled via --sango-publisher` / `publishing frames to tcp://127.0.0.1:5556 (topic sango.frame)` / `frame seq=0 1600x900 jpeg=90717B`。

**反向对照**（默认玩家，无旗标）：`NEGATIVE_PROBE_EXIT=1`，`FAIL: timeout after 30s with 0/30 frames`
——默认构建发布器确实 OFF（零 socket、零帧）。

## 5. 键位分配

- **B = 检测框叠加开/关**（key ledger 原空闲槽；M1/M2E 两场景均可）。
  开时每艘船画框 + 标签 `<船名>  1.0 (gt)`（OverlayProjection.ConfidenceLabel 纯函数，EditMode 钉死字面量）。
  相机取 Camera.main——M1 桥楼/追船/俯视切换（C）后框随视口实时重投影（OverlayProjection.ViewportBoxToPixelRect，y 翻转 + 出屏钳制）。
- 全量账本不变项：0-9/T/F 天气 · G/A demo · C 相机 · V 矢量 · Q/E/Z/X 雷达 · -/= 岛数 · ,/. 缩放 · Enter Apply · P 预览 · 1/2/3 遭遇模式（M2E）。B 无冲突（全部 KeyCode 使用面 grep 核过）。

## 6. 闸门与 exit code

| 闸 | 命令 | exit |
|---|---|---|
| EditMode 套件 | `-batchmode -projectPath sango -runTests -testPlatform EditMode -testResults /tmp/m3-tests.xml`（无 -quit） | **0（124/124）** |
| M1 场景重建 | `-executeMethod Sango.Editor.M1SceneBootstrapper.Build -quit` | **0**（log 1441: `[Sango.M3] wired: detection overlay (B, 2 ships), frame publisher (default OFF, tcp://127.0.0.1:5556)`） |
| M2E 场景重建 | `-executeMethod Sango.Editor.M2ESceneBootstrapper.Build -quit` | **0**（log 454: 同款 M3 wiring 行） |
| M1 玩家构建 | `-executeMethod Sango.Editor.M1VerifyCapture.BuildStandalonePlayer -quit` → `Builds/sango.app`（194MB, Succeeded） | **0** |
| M2E 玩家构建 | `-executeMethod Sango.Editor.M1VerifyCapture.BuildEncounterStandalonePlayer -quit` → `Builds/M2E-Standalone.app`（192MB, Succeeded） | **0** |
| 探针验收 | `tools/sango_zmq_probe.py --count 30` | **0**（30/30 帧；反向对照 exit 1 = 默认 OFF 证明） |

pipelineVersion 未触碰（无 ProjectSettings 改动入库）。

## 7. 探针运行输出（逐字）

正向（`./sango/Builds/sango.app/Contents/MacOS/sango --sango-publisher &` 后）：

```
$ .venv/bin/python tools/sango_zmq_probe.py --count 30
[probe] SUB connected to tcp://127.0.0.1:5556, expecting 30 frames on topic sango.frame
[probe] frame   1/30 seq=826 1600x900 jpeg=91135B t=27.64s
[probe] frame   2/30 seq=827 1600x900 jpeg=91215B t=27.68s
[probe] frame   3/30 seq=828 1600x900 jpeg=91222B t=27.72s
[probe] frame   4/30 seq=829 1600x900 jpeg=91124B t=27.76s
[probe] frame   5/30 seq=830 1600x900 jpeg=90800B t=27.84s
...
[probe] frame  24/30 seq=849 1600x900 jpeg=91228B t=28.50s
[probe] frame  25/30 seq=850 1600x900 jpeg=91260B t=28.50s
[probe] frame  26/30 seq=851 1600x900 jpeg=91213B t=28.57s
[probe] frame  27/30 seq=852 1600x900 jpeg=91154B t=28.58s
[probe] frame  28/30 seq=853 1600x900 jpeg=90978B t=28.61s
[probe] frame  29/30 seq=854 1600x900 jpeg=90916B t=28.68s
[probe] frame  30/30 seq=855 1600x900 jpeg=90903B t=28.71s
[probe] OK: received 30 valid frames (last seq=855, source=sango) in 1.1s
PROBE_EXIT=0
```

（探针连接前发布器已持续发帧至 seq 826——玩家启动即发，PUB 慢加入丢帧语义照旧，不影响验收。）

反向对照（默认玩家，无旗标）：

```
$ .venv/bin/python tools/sango_zmq_probe.py --count 30 --timeout 30
[probe] SUB connected to tcp://127.0.0.1:5556, expecting 30 frames on topic sango.frame
[probe] FAIL: timeout after 30s with 0/30 frames
NEGATIVE_PROBE_EXIT=1
```

## 8. 偏差清单

1. **RED 无逐用例失败记录**（§2）——Unity 批跑期间源码竞态编译失败；测试先行的顺序保持了，负结果未留档。
2. **许可与规划材料不符**（§3）——NetMQ LGPL-3.0 / AsyncIO MPL-2.0 / NaCl MPL-2.0，非 MIT；按未修改库分发处理并在 THIRD_PARTY_NOTICES.md 落账。
3. **NetMQ 缺传递依赖 NaCl**——首次场景重建 exit 1（`Unable to resolve reference 'NaCl'`，Reference validation 在 Mono 加载期拦截）；补 NaCl.dll 并将 NetMQ/NaCl 换 netstandard2.1 版（该档零外部依赖，System.Memory 等 .NET Standard 2.1 已内建）后全闸通过。
4. **fixture 期望值竞态**——GREEN 第 1 轮唯一失败：测试期望误用 seq 0 首帧坐标而 fixture 是 seq 54 稳态帧；回填录制事实后全绿。
5. **pyzmq 未入 pyproject**——探针为 tools-only 验收件；一次性 `uv pip install`，避免与并行中的依赖树冲突（§4）。
6. **首帧 fixture 弃用**——首条消息 static_included=true 含 ENC 静态块（~460 KB），改取稳态消息（static_included=false，~21 KB），结构与剥字段语义一致（§1）。
7. **GUI 框样式用 OnGUI 默认 Box**（spec 明示 OnGUI 或 UGUI 二选一）；phase-2 若需精修样式，替换 DetectionOverlay.OnGUI 单点即可，投影/契约层不动。

## Orchestrator acceptance (2026-09-28)

- Probe independently repeated by the orchestrator: publisher enabled via
  `--sango-publisher`, `tools/sango_zmq_probe.py --count 30` → **30/30 valid
  frames, exit 0** (last seq=508, 1.0 s). Default-off negative control was
  proven by the implementer (timeout 0/30 without the flag).
- Overlay: `m3-overlay-gt-boxes.jpg` — B-key ground-truth boxes on both ships
  (`VesselMedium 1.0 (gt)`, `VesselSmall 1.0 (gt)`), reprojection follows the
  camera.
- Verdict: PASS (probe + overlay + default-off; contracts/fixture tests in
  the 124/124 suite).
- Review pending at time of writing; close-out of #86 follows the review.
