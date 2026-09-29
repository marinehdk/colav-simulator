# M6 主 agent 实机验收 — 2026-09-29

验收对象：`sango/Builds/sango.app`（海峡场景播放器，f0500aef 构建产物，二进制 mtime 14:44 本日）。
证据帧：`evidence/`（fps1=默认追尾、topdown=俯视、bow=船艏、sail=G 自航 8s）。

## 门禁与实测

| 项 | 结果 | 证据 |
|---|---|---|
| EditMode | **256/256**（+15 M6 测试） | workflow 门禁（tmp/m6u-gate.xml 解析 total=256 failed=0） |
| 场景重建 | M6+M1 均 exit=0 | workflow 门禁 |
| 播放器 | exit=0，二进制 fresh | stat mtime > marker |
| fps（干净协议：无 publisher、零采样预热后隔 4.5s 采 3 帧） | **120.0**（frame 8.33ms；闸门 ≥30） | evidence/m6-accept-fps1.jpg HUD |
| ZMQ probe | **30/30 exit 0**（--sango-publisher，seq 241-270 连续，jpeg ~115KB/帧） | probe 输出日志在会话档案 |
| 视觉-地形 | ✓ S2 底图贴合、主岛/航道/锚地渲染、无空洞闪烁粉紫破面 | topdown 帧 analyze_image 复核 |
| 视觉-船与航路 | ✓ 船艏视角入画；G 自航 V 形艏波+尾迹白沫清晰；无搁浅/悬空/穿模（构建期水深断言的实机印证） | bow/sail 帧 |
| 视觉-锚地 | ✓ 6 艘（1 主角+5 锚泊） | topdown 帧 |

## 遗留 findings（已交 code-review 核根因）

- **F-A 水面偏暗**：俯视/船艏两视角白天正午海面发暗。历史先例 M2-E2（无 Exposure override，类默认 Fixed 0EV）。候选根因=M6-GlobalVolumeProfile 缺自动曝光或水色参数。
- **F-B 追尾相机首帧无船**：启动默认视角（追尾）主视口未见主角船；切 C 后俯视/船艏正常。候选=追尾相机位姿参数（过高/过远）。
- **F-C UI 重叠**：左上性能面板与天气面板文字重叠。候选=FpsProbe overlay 与 WeatherGUI 锚点冲突。

## 已知限制（数据段带过，非阻塞）

- 近景带 NE 陆面云斑 10-15%（S2 单景现实；补丁方案在数据段 notes.md §已知限制）。
- GEBCO 15″ 上采样水下块状纹理（水深细节天花板；BATNAS/DEMNAS 升级路径在档）。
- 远景环 9 tile 禁用留下的空洞带（12-24km，默认雾距 3000m 遮蔽；M8 流送接棒——覆盖语义裁决见 workflow 升级问答）。

## 验收判定

**通过**。三条视觉 findings 转 review-修复批处理（不阻塞 M6 判定：核心判据"真实地形海峡+航路+锚地+全链门禁"全绿）。

## Review 终局与修复复测（2026-09-29 批末）

**Review verdict：approve-with-fixes**（范围 0caea3b5..f0500aef 双轴；Spec 11 项核心全 verified 通过：数据契约/RAW 导入/远景去重 9 块/水深门/15 测试 fresh 路径/资产纪律 29+29+29+1）。

三 findings 根因与处置：

| id | 根因（review verified） | 修复（d7b9300b） | 复测 |
|---|---|---|---|
| S1 首帧无船 | CameraViews Bridge 分支写死 M1 世界机位 (0,12,-40) 望北；M6 船在 (-1500,-5000)=相机背后 5.2km（Player.log census `boatNDC z=-4959` 铁证） | `bridgeShipRelative`（M6 置 true，船位+航向系偏移解算；M1 数值逐位不变）+ 视锥内纯几何测试 | ✓ 启动即船入画（中央偏右白船体） |
| S2 海面偏暗 | **体积雾主因实证**（A/B：3000m 档深灰墨绿 vs 8000m 档明亮蓝绿，单调变化；`expMode=Automatic(ovr=True)` 排除 M2-E2 类曝光缺失——编排者假设被 review 证伪） | M6 场景默认雾距 8000（WeatherController 场景参数注入，M1 默认 3000 不变） | ✓ 海面明亮蓝绿 |
| S3 UI 重叠 | FpsProbe IMGUI `Rect(8,8,560,116)` 永远最上层，与 WeatherGUI 左上面板 (20,-20,380×640) 重叠（M1 从未同屏，无先例） | FpsProbe `screenAnchor` 序列化字段，M6 置底 | ✓ 面板分开可读 |

复测环境：d7b9300b 播放器，EditMode **265/265**（+9），fps **119.8**（无回归）。证据帧：`evidence/m6-recheck-bridge.jpg`（S1+S2+S3 同帧）、`m6-recheck-fps.jpg`、雾距 A/B `m6-ab-fog3000/8000.jpg`。
