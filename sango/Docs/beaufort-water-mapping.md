# Beaufort → HDRP Water band 参数映射表（M1）

- 状态：**M1 实机核对完成（2026-09-23，锚点档 B0/B3/B6/B9 观感达"调值指引"标准）**。风速列为公认换算（映射代码 `Assets/Scripts/Runtime/WeatherController.cs::BeaufortToWindSpeedMs`，面板读数与表格同源）；band 各列为代码锚点值——锚点档已实机核对达标，非锚点档沿用同档常量未逐级采图（标注 TBD 的仍留待 M2 海况细化时复核）。
- HDRP 17.3 Water 不暴露谱型选择（PM/JONSWAP/TMA），谱档（JS-PM 近似）是对 Water band 幅值/风强的近似映射【PLAN §5 M1 诚实点，推断】。HDRP band 结构：band0 = 涌浪（长波）、band1 = 风浪（中波）、ripples = 涟漪（短波）；幅值由风速经内部查表（`WaterSystemDef.cs:67 k_MaximumAmplitudeTable`）推导，代码可调的是风速与幅值倍率。
- 字段单位注意：`largeWindSpeed`/`ripplesWindSpeed` 单位是 **km/h**（HDRP 内部 ×1/3.6 转 m/s，`WaterSurface.Simulation.cs:291-293`）；`ripplesWindSpeed` 上限 15 km/h（`WaterSystemDef.cs:52`），高海况下涟漪 band 饱和。

## 映射表（锚点档截图已回填）

固定机位 = M1-Weather 场景主相机 (0,12,-40) 望岛群；固定其余参数 = 风向 30° / 时刻 12h / 云量 0.40 / 雾距 3000m，谱档按行取。截图采集走**键盘驾驶**（数字键 0-9 直设 B 级并按本文档默认分配联动谱档；T 循环时刻预设；F 循环雾距预设，见 `WeatherGUI.HandleHotkeys`），面板读数经 `Update` 镜像与 controller 保持一致。

| Beaufort 级 | 风速 m/s | 涌浪 band 幅值 `largeBand0Multiplier` | 风浪 band 风速 `largeWindSpeed` (km/h) | 涟漪强度 `ripplesWindSpeed` (km/h) | 白沫 `simulationFoamAmount` | 谱档 | 固定机位截图 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| B0 | 0.50 | 0.15（实机核对） | 0.6（实机核对） | 0.9（实机核对） | 0.00（实机核对） | Calm | evidence/m1-beaufort-b0.png |
| B1 | 1.83 | 0.15 TBD-实机调值 | 2.3 TBD-实机调值 | 3.3 TBD-实机调值 | 0.00 TBD-实机调值 | Calm | 待实机补 |
| B2 | 3.17 | 0.35 TBD-实机调值 | 6.8 TBD-实机调值 | 9.1 TBD-实机调值 | 0.10 TBD-实机调值 | Moderate | 待实机补 |
| B3 | 4.50 | 0.35（实机核对） | 9.7（实机核对） | 13.0（实机核对） | 0.10（实机核对） | Moderate | evidence/m1-beaufort-b3.png |
| B4 | 7.17 | 0.35 TBD-实机调值 | 15.5 TBD-实机调值 | 15（饱和）TBD-实机调值 | 0.10 TBD-实机调值 | Moderate | 待实机补 |
| B5 | 9.83 | 0.50 TBD-实机调值 | 31.9 TBD-实机调值 | 15（饱和）TBD-实机调值 | 0.25 TBD-实机调值 | Rough | 待实机补 |
| B6 | 12.50 | 0.50（实机核对） | 40.5（实机核对） | 15（饱和）实机核对 | 0.25（实机核对） | Rough | evidence/m1-beaufort-b6.png |
| B7 | 15.83 | 0.50 TBD-实机调值 | 51.3 TBD-实机调值 | 15（饱和）TBD-实机调值 | 0.25 TBD-实机调值 | Rough | 待实机补 |
| B8 | 19.17 | 0.65 TBD-实机调值 | 75.9 TBD-实机调值 | 15（饱和）TBD-实机调值 | 0.45 TBD-实机调值 | VeryRough | 待实机补 |
| B9 | 22.50 | 0.65（实机核对） | 89.1（实机核对） | 15（饱和）实机核对 | 0.45（实机核对） | VeryRough | evidence/m1-beaufort-b9.png |
| B10 | 25.83 | 0.65 TBD-实机调值 | 102.3 TBD-实机调值 | 15（饱和）TBD-实机调值 | 0.45 TBD-实机调值 | VeryRough | 待实机补 |
| B11 | 29.17 | 0.65 TBD-实机调值 | 115.5 TBD-实机调值 | 15（饱和）TBD-实机调值 | 0.45 TBD-实机调值 | VeryRough | 待实机补 |

- 风速列：锚点 B0≈0.5 / B3≈4.5 / B6≈12.5 / B9≈22.5（级内中值，公认换算），锚点间分段线性插值，B9→B11 按末段斜率外推。
- 谱档默认分配：B0-1 Calm、B2-4 Moderate、B5-7 Rough、B8-11 VeryRough（GUI 可手动覆盖）。
- 表中 band 数值 = 谱档统一锚点 × 行内风速换算，仅作起点；`largeChaos`/`ripplesChaos` 另有档位锚点（0.9→0.5 / 0.6→0.9），同见代码表。
- 风向/波向：`largeOrientationValue` = `ripplesOrientationValue` = GUI 风向值（涟漪默认 Inherit 模式随涌浪同向，`WaterSurface.Simulation.cs:284`）；HDRP 角度约定与罗盘北的对应关系 TBD-实机核对。

## 调值指引（实机迭代流程）

1. Play 进入 M1-Weather 场景，拖 Beaufort 滑条逐级停靠 B0/B3/B6/B9（或按数字键 0-9 直设），其余参数保持"固定机位"配置。
2. 量级目标（观感锚点）：**B0 近镜面**（涌浪/风浪近无，只余极轻纹理）；**B3 明显白沫**（碎浪白帽开始可见，波高 ~0.5m 量级）；**B6 大浪**（明显涌浪起伏，白沫成片，波高 ~3-4m 量级）；**B9 惊涛**（船视点被浪遮挡级，白沫大面积，波高 ~7-10m 量级）。
3. 调法：档位锚点在 `Assets/Scripts/Runtime/WeatherController.cs` 顶部 `Tier*` 数组（当前为代码常量，未序列化到 Inspector，改后重进 Play）；单点微调可直接在 Play 中改 Water Surface 组件 `Large Wind Speed` / `Large Band 0/1 Multiplier` / `Ripples Wind Speed` / `Simulation Foam Amount`（Inspector 显示名，运行时改动即生效，见 `WaterSurface.Simulation.cs:221-231`），把收敛值回填上表并同步改代码数组。
4. 每级回填后在固定机位截图（其余参数不动），替换截图列；截图存 `docs/research/2026-09-22-sango-prototype/evidence/`。

## M1 实机核对记录（2026-09-23）

- **锚点档观感**：B0 近镜面 ✓ / B3 白沫适度 ✓ / B6 大浪成形白沫成片 ✓ / B9 惊涛大面积白沫+船体被浪半掩 ✓，全部达"调值指引"第 2 条目标，未触发调参迭代（代码锚点值即收敛值）。
- **面板一致性**（验收②）：各档截图中面板读数（风速 m/s + B 级 + 谱档）与 `BeaufortToWindSpeedMs` 输出一致（B0=0.5 / B3=4.5 / B6=12.5 / B9=22.5），代码与文档同源。
- **扫描影像**（验收②）：本机 shell 无屏幕录制 TCC 权限，`screencapture -v` 不可用；改以键盘驾驶逐档采集 + ffmpeg 装配 timelapse（`evidence/m1-beaufort-sweep.mp4`，B0→B9 每档 6s 收敛后取帧）。
- **昼夜对**（验收③）：`evidence/m1-time-midnight.png`（0.0h，暗夜空+岛剪影）对照 B3/B6 截图正午态。
- **雾距对**（验收③）：`evidence/m1-fog-1000m.png` / `m1-fog-8000m.png` 机制生效但视觉差异弱——岛群最远 ~440m 未达雾距档位差量级；M2 候选：加 2-3km 远距参照物后再采对比对。
- **采集环境**：编辑器 Game view 在本机有 topology 动荡史（背缓冲退化/窗口 offscreen 翻转，见持久记忆坑清单），M1 证据统一改在 **Standalone 播放器**（`Sango/M1/Build Standalone Player (Mono)` 菜单构建）中采集；编辑器内 UGUI 点击"失聪"的两层根因均已修复（raycastTarget 全关 + Game view 背缓冲退化致画布裁剔），真人鼠标交互待人工复核。
5. 验收条款（PLAN §5 M1）：① 本表有可对数值锚点+每级截图对；② 录屏 Beaufort 0→9 波高/白沫可感知增强且**面板风速与映射表一致**；③ 时刻滑条正午 vs 深夜、雾距两档截图；④ 画面3/4 天气要素先行核对。

## HDRP 17.3 字段出处（本表代码锚点的源码依据）

包缓存 `sango/Library/PackageCache/com.unity.render-pipelines.high-definition@700710090fa9/`：

| 字段 | 源码位置 | 类型/范围 | 含义 |
| --- | --- | --- | --- |
| `surfaceType` | WaterSurface/WaterSurface.cs:129 | enum OceanSeaLake/River/Pool | 水体类型 |
| `scriptInteractions` | WaterSurface/WaterSurface.cs:153 | bool | CPU 水高查询前置 |
| `repetitionSize` | WaterSurface/WaterSurface.Simulation.cs:27 | float [250..5000] m | 涌浪 patch 尺寸 |
| `largeOrientationValue` | WaterSurface/WaterSurface.Simulation.cs:32 | float deg | 涌浪/风浪方向 |
| `largeWindSpeed` | WaterSurface/WaterSurface.Simulation.cs:38 | float [0..250] **km/h** | 涌浪风速 |
| `largeChaos` | WaterSurface/WaterSurface.Simulation.cs:44 | float [0..1] | 方向衰减 |
| `largeBand0Multiplier` | WaterSurface/WaterSurface.Simulation.cs:50 | float [0..1] | 涌浪 band 幅值倍率 |
| `largeBand1Multiplier` | WaterSurface/WaterSurface.Simulation.cs:71 | float [0..1] | 风浪 band 幅值倍率 |
| `ripples` | WaterSurface/WaterSurface.Simulation.cs:93 | bool | 涟漪模拟开关 |
| `ripplesOrientationValue` | WaterSurface/WaterSurface.Simulation.cs:103 | float deg | 涟漪方向 |
| `ripplesWindSpeed` | WaterSurface/WaterSurface.Simulation.cs:109 | float [0..15] **km/h** | 涟漪风速 |
| `ripplesChaos` | WaterSurface/WaterSurface.Simulation.cs:115 | float [0..1] | 涟漪方向衰减 |
| `foam` | WaterSurface/WaterSurface.Foam.cs:14 | bool | 白沫模拟开关 |
| `simulationFoamAmount` | WaterSurface/WaterSurface.Foam.cs:55 | float [0..1] | 白沫量（白帽强度） |
| `simulationFoamWindCurve` | WaterSurface/WaterSurface.Foam.cs:80 | AnimationCurve | 白沫-风速曲线（默认 preset 曲线见 WaterSurface.Presets.cs:100） |
| km/h→m/s 换算 | Water/WaterSystemDef.cs:17-23 | const | `largeWindSpeed` 单位为 km/h 的依据（Simulation.cs:291-293 消费处） |
| 涟漪风速上限 | Water/WaterSystemDef.cs:52 | const 15 | `k_RipplesMaxWindSpeed` |
| 运行时生效机制 | WaterSurface/WaterSurface.Simulation.cs:221-231 | — | 每帧重算 spectrum，变化即失效重建 |
