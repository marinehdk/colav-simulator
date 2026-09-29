# M6 正式批·Unity 段 —— 新加坡海峡场景（真实地形）2026-09-29

数据段前置：`tmp/m6-data/`（manifest 契约与规格见 `docs/research/2026-09-29-m6-terrain-pipeline/notes.md`）。

## 交付件

| 件 | 路径 | 说明 |
|---|---|---|
| 数据层纯函数 | `sango/Assets/Scripts/Runtime/Vessels/M6TerrainModel.cs` | manifest 模型（JsonUtility，字段名即契约）/ RAW 小端 u16 解码（行序北上→SetHeights 垂直翻转）/ u16↔米换算 / tile 布局（Unity 原点=区域中心）/ 水深验证纯函数 |
| 地形资产管线 | `sango/Assets/Scripts/Editor/M6TerrainPipeline.cs` | manifest→逐 tile RAW→TerrainData（2049²/513²，size=(12000, 带高程全量程, 12000)）+ TerrainLayer（S2 底图 sRGB，tileSize=12000）+ HDRP/TerrainLit 材质 → `sango/Assets/TerrainM6/`；幂等=原路径覆盖重建（GUID 稳定）；>100MB 即抛错停批 |
| 场景生成器 | `sango/Assets/Scripts/Editor/M6StraitSceneBootstrapper.cs` | `Sango/M6/Build Strait Scene`（batchmode `-executeMethod Sango.Editor.M6StraitSceneBootstrapper.Build`，门禁契约方法名）；NewScene 重建照 M1 模式 |
| 播放器 | 同上 `BuildStraitPlayer` | M1VerifyCapture.BuildStandalonePlayer 同款（Mono 后端 + runInBackground）→ `sango/Builds/sango.app`（海峡场景接棒主 demo；M1-Weather 场景与 M2E app 不动） |
| EditMode 测试 | `sango/Assets/Scripts/Tests/EditMode/M6TerrainModelTests.cs` | 15 个（+基线 241 = 256 目标）；fixture = `Assets/Tests/Fixtures/m6-manifest-fixture.json` + `m6-tile-33x33.raw`（合成 2×2 近景/5×5 远景，33² 顶点格=Unity 地形最小分辨率） |
| 场景 | `sango/Assets/Scenes/M6-Strait.unity` | 29 块地形 + 单实例 Ocean 水面 + M6 Global Volume（独立 profile，自动曝光 override 在内）+ WeatherController/GUI + SimulationPanel（岛数控件隐藏）+ FpsProbe + FcbHoubei 主角（G 键主航路）+ AnchorageFleet 7 槽 + DetectionOverlay/FramePublisher |

## 远景 tile 去重裁决（编排者批准，2026-09-29）

任务文本"近景带覆盖住的 4 个远景 tile SetActive(false)（其余 21 个激活）"的 **4** 基于近景带与远景网格 2×2 对齐假设；真实网格**半 tile 偏移**（中心落在远景 r2c2 tile 内部）：近景带与远景 tile 交叠 **9** 块（r1–r3 × c1–c3，重叠 25%/50%/100%），全覆盖仅 r2c2 一块——无任何划分得 4。
**裁决：覆盖语义**——与近景带有实际交叠（面积 >1 m²）的全部远景 tile `SetActive(false)`（海峡场景 9 块隐藏/16 块激活）。理由：共面双层地形 z-fight 是硬伤（近景带内必现闪烁）；隐藏产生的无地形洞在 12–24 km 远景环、默认雾距 3000 m（最大档 8000 m）外被雾遮蔽；M8 流送整体接棒此策略。实现：`M6TerrainMath.FarTileUnderNearBand`（纯函数，fixture 测试钉契约）。

## 水深验证（防搁浅，构建期 fail-fast）

- 门：泊位/锚地全船位与 G 航路逐航点间 100 m 插值采样，一律要求高程 < **−5 m**（0 硬门 + 5 m 防搁浅裕量）；违规抛异常终止构建、报采样点坐标，**不静默换点**。采样走 `Terrain.SampleHeight`（构建期实采，含 elevMin 锚定）。
- 采样纯函数 `ValidateDepths/ValidateRoute` 进 EditMode（合成地形 fixture）。
- 场景字面量选点 provenance（对近景带 RAW 逐 50 m 采样离线选点 + 构建期 gate 实采复验，2026-09-29）：
  - **首版航路被 gate 拦下（gate 自证有效）**：初版直接 SE 航线在 (3407,−6370) 读 −4.8 m ≥ −5 m 门——Bukom/Sudong 岛群浅滩（+9~+27 m 陆域横在 (3.8–5.6k, −7.0..−7.3k)）；首版离线验证误用"段内**最深**处"统计，gate 纠正为"段内**最浅**处 < −5 m"口径。重选 = 100 m 深水格 (<−10 m) BFS 连通搜索的解：绕岛群南侧深水航道。
  - 主角泊位 `(-1500, -5000)`：200 m 盒**最浅 −13.3 m**（中心 −15.0 m）；艏向 134°（沿航线首段）。
  - G 航路 3 航点 `(5200,-11400)→(7200,-11200)→(9500,-8800)`：三段**最浅 −15.0/−46.9/−46.9 m**，全长 14.6 km。
  - 锚地 7 槽（z≈−10 km 深水锚区，档位沿用 M5 船队 Tug→Tanker）：含 300 m 大船 ±153 m 角点盒**最浅 −23.8 ~ −73.1 m**（逐槽 PASS）。
- 构建日志 `[Sango.M6] depth gate PASS` 行为准（实测值见 `sango/tmp/m6u-build.log`，不入库；首跑拦截记录见上 provenance）。

## 其他契约决定

- **世界坐标**：区域中心（manifest `center_utm`，EPSG:32648）= Unity 原点；+X=东、+Z=北；terrain `position.y = elev_min` + 归一化高度 × 带全量程 → 世界 y=真实高程，海面 y=0 天然成立。相机 far **32000 m** / near **0.5**。
- **JsonUtility 类型先例**：坐标数组 `float[]`（DetectionResult.box_xyxy）、标量 `double`（ColavTelemetry.sim_time）；UTM 大数 float 化误差 ~2 cm（无缝断言容差 0.5 m），`double[]` 无先例不用。
- **跨 tile 共享边**：RAW 光栅 2049/513 比 12 km 逻辑域多东/南各 1 共享 px（notes.md §采样格约定），Unity 按 terrain size=12000 导入即格点恰跨 2048 格——无缝由数据段 V4 checksum 保证，EditMode 钉布局层无重叠无缺口。
- **SimulationPanel**：`islandControlsVisible=false` 只隐藏岛数段（UI+−/=、,/. 键位+岛群重建）；锚地密度/M4 水面工艺滑条、雷达、Enter(雷达收权)保留；M1 默认 true 语义不变。
- **AnchorageFleet.SetSlots**：海峡锚地字面量注入口（M5 Defaults 保留为默认）。
- **M1 三个接线 helper 转公开**（AttachNavigationLights/AttachHullWaterlineDecals/AttachWaterDecals）：M6 复用同一放置路径，单一修复点（PlaceCatalogShip 先例）。

## followUps

1. **M8 流送前远景环有雾区遮蔽的空洞带**（裁决直接后果）：9 块隐藏 tile 的未交叠外缘无地形，依赖默认 3000 m 雾距遮蔽；雾距拉到 8000 m 时 12–24 km 环带可见洞，M8 流送接棒前不修。
2. 近景带陆面云斑（数据段已知限制 1）→ Unity 段 splat 压暗方案未做（云在陆不在海，视觉权重低）。
3. 锚地槽位清障只做了水深门 + 大船角点盒抽查；未像 M5 那样建全套清障不变量测试（海峡地形是真实数据非确定性岛群，字面量改动的守门靠构建期 depth gate）。
