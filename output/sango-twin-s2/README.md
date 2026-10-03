# P3-S2 — 相机链贯通 + 传感器视角切换 E2E 证据（spec #90，2026-10-02）

本目录 = `tools/sango_twin_obs_probe.mjs`（P3-S2 新 E2E 探针）的产物 + 复现说明。
契约：`sango/Docs/contracts/observations-v1.md`（§8 S2 演进行 = 端点落地 + georef 方案写档）+
`twin-bridge-v1.md`（§8 S2 演进行 = sensor_mode 接线）+ `frame-publisher-v1.md`（P3-S2 只加字段行）。
前置段：S0 `83d1cb61`（契约冻结）/ S1 `27328286`（RadarXBand）。

## 1. 结论速览

| # | 验收项（任务书） | 结果 | 数字/证据 |
|---|---|---|---|
| 1 | Unity EditMode 全绿 | **PASS** | **495/495**（479 基线 + 16 新增：机位表 9 + IR 温度分级/ramp 3 + sensor_mode 效果表 1 + FrameMetadata mount/pose 3） |
| 2 | pytest 子集全绿 | **PASS** | **134 passed / 2 skipped**（105 基线 + 29 新增 `test_observations_endpoint.py`：标定表 7 + georef 数值 5 + 端点 HTTP 11 + KF 量测缓存 2 + SFD 形状等） |
| 3 | web 全绿 | **PASS** | **447/447**（442 基线 + 5 新增：twin-view 按钮组/回显 2 + deployment twin 3） |
| 4 | 既有双探针不回归 | **PASS** | bridge 探针**全 PASS**（23 断言，`output/sango-twin-s3/report.md` 本次复跑）；live 探针**全 PASS**（重连 + 联动 + D 接线，`output/sango-twin-s4/report.md` 本次复跑） |
| 5 | E2E：live→twin→YOLO→observations→量测缓存 sensor_id=2 | **PASS** | live 会话（rule14/head_on/vo）→ mast 馈送（`mast_ptz_eo`，640×480）→ YOLO CPU rx=2140 → POST 200×2141 → **GET status：channel `sensor_id=2 / mast_ptz_eo`，detections=1，pending 量测 NE=(136.4, 60.4) m，径向协方差特征值 500.6/6.8（≈8:1 径向拉长，契约 §3 E5 形态）** |
| 6 | EO↔IR 切换流内可见（双证） | **PASS** | 截图双证：`ir-frame.jpg`（白热黑白热像，maxSpread=5）vs `eo-frame.jpg`（彩色可见光，maxSpread=34）+ 状态侧 `state.sensor_mode` ir→eo 回显 + 日志侧 Player.log `sensor_mode -> ir` |

E2E 关键数值：YOLO CPU 推理 41-55 ms/帧 @640×480；observations 端点 POST 全部 200（ok=2140 err=0）；
本船锚定 (39565, 6957565)；IR 灰度帧 mean=82.9 std=55.0 / EO mean=78.8 std=64.5 spread=34。

## 2. 证据索引（本目录）

| 文件 | 内容 |
|---|---|
| `report.md` | 探针断言清单 + 关键数值（探针自动生成） |
| `ir-frame.jpg` | **IR 模式流内解码帧**：白热黑白热像（艏甲板热亮、天空/海面冷暗——`IrWhiteHot` pass + 温度 tag） |
| `eo-frame.jpg` | EO 模式流内解码帧：彩色可见光（同一视口，切换恢复） |
| `ir-mode.png` / `eo-mode.png` | 页面整页截图（Deployment twin 视口 + 传感器模式按钮组 + `SENSOR IR`/`SENSOR EO` 状态芯片） |
| `feed-frame.jpg` | 桅杆前向 EO 馈送机位（`mast_ptz_eo`）实拍帧——YOLO 的输入视图（艏甲板+前向海面） |
| `observations-status.json` | GET `/api/sessions/{id}/observations`：计数 + 通道 + **pending georef 量测（sensor_id=2，径向协方差）** |
| `georef-error-stats.json` | **P2-2 终审补证（2026-10-02）**：georef 反算数值误差存证（pytest `test_georef_error_stats.py` 产出——已知真值正投影→1px 量化→georef 反算，多距离/方位/航向采样；YOLO 可检包络（框≥4px，≤300m）内 max 误差 22.9 m ≤ 船长级 45 m 锚，2nm 亚像素尾如实记录） |
| `detector-log.txt` | YOLO 服务日志尾部（forward 分支 POST 记录） |
| `player-log-excerpt.txt` | Player.log 尾部（mast rig attach + feed rewire + sensor_mode -> ir） |

## 3. 复现命令

前置一次性：URS 信令（`node /tmp/urs-repo/WebApp/build/index.js -p 8080`）；twin 场景/播放器
（本段改了 Unity 侧，场景+播放器都要重建）：

```bash
UNITY=/Applications/Unity/Hub/Editor/6000.3.24f1/Unity.app/Contents/MacOS/Unity
"$UNITY" -batchmode -projectPath "$PWD/sango" \
  -executeMethod Sango.Editor.TwinBridge.TwinBridgeSceneBuilder.BuildTwinScene -quit -logFile /tmp/sango-twin-scene.log
"$UNITY" -batchmode -projectPath "$PWD/sango" \
  -executeMethod Sango.Editor.TwinBridge.TwinBridgeSceneBuilder.BuildTwinPlayer -quit -logFile /tmp/sango-twin-player.log
```

每次运行（backend 8010 launchd 常驻需重启加载 S2 路由：`launchctl kickstart -k gui/$UID/com.marine.colav-simulator.frontend`；
player/YOLO/Chrome 由探针全权管理——起前 pgrep 清残留、退场必杀）：

```bash
source ~/.nvm/nvm.sh && nvm use 22
node tools/sango_twin_obs_probe.mjs          # 产物落本目录；exit 0 = 全断言过
```

单测回归：

```bash
.venv/bin/python -m pytest tests/ -q -k "sensor or tracker or observation or compact or transport or radar_x"   # 134p/2s
source ~/.nvm/nvm.sh && nvm use 22 && node --test tests/web_gui/*.test.mjs                                     # 447/447
"$UNITY" -batchmode -projectPath "$PWD/sango" -runTests -testPlatform EditMode \
  -testResults /tmp/sango-editmode-s2.xml -logFile /tmp/sango-editmode-s2.log                                   # 495/495
```

YOLO 检测服务带 observations 转发支路的手册命令（默认关，ZMQ 既有行为零变化）：

```bash
.venv-detector/bin/python tools/sango_detector_service.py --device cpu \
  --forward-url http://127.0.0.1:8010/api/sessions/<session_id>/observations \
  --forward-mount mast_ptz_eo
```

## 4. 实现要点（对后继有价值的实证）

1. **Resources 进包**：`Shader.Find` 只解析构建引用到的 shader——IR 白热 shader 放
   `Vessels/Mast/Resources/IrWhiteHot.shader`（`Resources.Load` 兜底）才进播放器；
   场景预烘焙 CustomPassVolume + `EnsureIrPassVolume` 运行期自举双保险。
2. **挂点时序**：mast rig 挂载依赖 own-ship 槽位（首帧遥测）→ bridge attach 之后；
   `AttachMastRigWhenOwnShipReady` 轮询到槽位即挂载 + FramePublisher 馈源改接
   （`--sango-publisher` 先以 Camera.main 起发布，改接后即桅杆视角）。
3. **检测窗口**：head_on 目标初始 2.8 km 正前，闭合 ~14 m/s——YOLO（COCO boat，
   conf 0.25）在目标接近至数百米才出框；探针观测窗 330 s 覆盖 CPA 前沿。
4. **截屏双证工艺**：headless Chrome 对 WebRTC `<video>` 页面截屏可能黑帧（S4 已知），
   本探针以 canvas `drawImage`（MediaStream 不 taint）解码取帧——灰度统计（maxSpread）
   + 全分辨率 JPEG 落盘即为双证，页面截屏仅作视口布局佐证。
5. **tracker 词汇**：capabilities 现仅 `god`（S6 末翻转）——E2E 用 god 会话跑链路；
   kf 消费外部量测的腿由 pytest `ExternalCameraSensorCache` 集成测试覆盖。

## 5. 已知边界 / 遗留

- PTZ 控制不做（固定机位）；LiDAR 渲染不做（S3）——UI 按"pending 明示"方案保留按钮
  （`LiDAR·S3 · PENDING`），消息路径可 E2E（见 twin-bridge-v1 §8 S2 行）。
- IR 温度 tag 简化档：`_BaseColor`/emission 改写 + 灰度 ramp；夜幕主题下热目标对比
  最佳（白天 IR 仍为灰度但热分级对比弱——裁决 3 的简化模型边界内）。
- live 会话的桅杆量测暂不入 Ship 传感器列表（S5 融合贯通接线；本段缓存 =
  会话级 `ExternalCameraSensor` + GET 状态钩，ISensor 形状 KF 兼容已测）。
- headless 页面截屏 `<video>` 黑帧风险同 S4（本探针已用 canvas 解码绕开）。
- YOLO CPU 推理 ~45 ms/帧 + JPEG 编码：单机回环实测 10 fps 馈送稳定，a4000 批延后。
