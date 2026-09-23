# Beaufort → HDRP Water band 参数映射表（M1）

- 状态：**起调值骨架**。风速列为公认换算（映射代码 `Assets/Scripts/Runtime/WeatherController.cs::BeaufortToWindSpeedMs`，面板读数与表格同源）；band 各列为代码锚点值，**全部 TBD-实机调值**——需在 Play 中按"调值指引"节迭代后回填。
- HDRP 17.3 Water 不暴露谱型选择（PM/JONSWAP/TMA），谱档（JS-PM 近似）是对 Water band 幅值/风强的近似映射【PLAN §5 M1 诚实点，推断】。HDRP band 结构：band0 = 涌浪（长波）、band1 = 风浪（中波）、ripples = 涟漪（短波）；幅值由风速经内部查表（`WaterSystemDef.cs:67 k_MaximumAmplitudeTable`）推导，代码可调的是风速与幅值倍率。
- 字段单位注意：`largeWindSpeed`/`ripplesWindSpeed` 单位是 **km/h**（HDRP 内部 ×1/3.6 转 m/s，`WaterSurface.Simulation.cs:291-293`）；`ripplesWindSpeed` 上限 15 km/h（`WaterSystemDef.cs:52`），高海况下涟漪 band 饱和。

## 映射表（固定机位截图列待实机补）

固定机位 = M1-Weather 场景主相机 (0,12,-40) 望岛群；固定其余参数 = 风向 30° / 时刻 12h / 云量 0.40 / 雾距 3000m，谱档按行取。

| Beaufort 级 | 风速 m/s | 涌浪 band 幅值 `largeBand0Multiplier` | 风浪 band 风速 `largeWindSpeed` (km/h) | 涟漪强度 `ripplesWindSpeed` (km/h) | 白沫 `simulationFoamAmount` | 谱档 | 固定机位截图 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| B0 | 0.50 | 0.15 TBD-实机调值 | 0.6 TBD-实机调值 | 0.9 TBD-实机调值 | 0.00 TBD-实机调值 | Calm | 待实机补 |
| B1 | 1.83 | 0.15 TBD-实机调值 | 2.3 TBD-实机调值 | 3.3 TBD-实机调值 | 0.00 TBD-实机调值 | Calm | 待实机补 |
| B2 | 3.17 | 0.35 TBD-实机调值 | 6.8 TBD-实机调值 | 9.1 TBD-实机调值 | 0.10 TBD-实机调值 | Moderate | 待实机补 |
| B3 | 4.50 | 0.35 TBD-实机调值 | 9.7 TBD-实机调值 | 13.0 TBD-实机调值 | 0.10 TBD-实机调值 | Moderate | 待实机补 |
| B4 | 7.17 | 0.35 TBD-实机调值 | 15.5 TBD-实机调值 | 15（饱和）TBD-实机调值 | 0.10 TBD-实机调值 | Moderate | 待实机补 |
| B5 | 9.83 | 0.50 TBD-实机调值 | 31.9 TBD-实机调值 | 15（饱和）TBD-实机调值 | 0.25 TBD-实机调值 | Rough | 待实机补 |
| B6 | 12.50 | 0.50 TBD-实机调值 | 40.5 TBD-实机调值 | 15（饱和）TBD-实机调值 | 0.25 TBD-实机调值 | Rough | 待实机补 |
| B7 | 15.83 | 0.50 TBD-实机调值 | 51.3 TBD-实机调值 | 15（饱和）TBD-实机调值 | 0.25 TBD-实机调值 | Rough | 待实机补 |
| B8 | 19.17 | 0.65 TBD-实机调值 | 75.9 TBD-实机调值 | 15（饱和）TBD-实机调值 | 0.45 TBD-实机调值 | VeryRough | 待实机补 |
| B9 | 22.50 | 0.65 TBD-实机调值 | 89.1 TBD-实机调值 | 15（饱和）TBD-实机调值 | 0.45 TBD-实机调值 | VeryRough | 待实机补 |
| B10 | 25.83 | 0.65 TBD-实机调值 | 102.3 TBD-实机调值 | 15（饱和）TBD-实机调值 | 0.45 TBD-实机调值 | VeryRough | 待实机补 |
| B11 | 29.17 | 0.65 TBD-实机调值 | 115.5 TBD-实机调值 | 15（饱和）TBD-实机调值 | 0.45 TBD-实机调值 | VeryRough | 待实机补 |

- 风速列：锚点 B0≈0.5 / B3≈4.5 / B6≈12.5 / B9≈22.5（级内中值，公认换算），锚点间分段线性插值，B9→B11 按末段斜率外推。
- 谱档默认分配：B0-1 Calm、B2-4 Moderate、B5-7 Rough、B8-11 VeryRough（GUI 可手动覆盖）。
- 表中 band 数值 = 谱档统一锚点 × 行内风速换算，仅作起点；`largeChaos`/`ripplesChaos` 另有档位锚点（0.9→0.5 / 0.6→0.9），同见代码表。
- 风向/波向：`largeOrientationValue` = `ripplesOrientationValue` = GUI 风向值（涟漪默认 Inherit 模式随涌浪同向，`WaterSurface.Simulation.cs:284`）；HDRP 角度约定与罗盘北的对应关系 TBD-实机核对。

## 调值指引（实机迭代流程）

1. Play 进入 M1-Weather 场景，拖 Beaufort 滑条逐级停靠 B0/B3/B6/B9，其余参数保持"固定机位"配置。
2. 量级目标（观感锚点）：**B0 近镜面**（涌浪/风浪近无，只余极轻纹理）；**B3 明显白沫**（碎浪白帽开始可见，波高 ~0.5m 量级）；**B6 大浪**（明显涌浪起伏，白沫成片，波高 ~3-4m 量级）；**B9 惊涛**（船视点被浪遮挡级，白沫大面积，波高 ~7-10m 量级）。
3. 调法：档位锚点在 `Assets/Scripts/Runtime/WeatherController.cs` 顶部 `Tier*` 数组（当前为代码常量，未序列化到 Inspector，改后重进 Play）；单点微调可直接在 Play 中改 Water Surface 组件 `Large Wind Speed` / `Large Band 0/1 Multiplier` / `Ripples Wind Speed` / `Simulation Foam Amount`（Inspector 显示名，运行时改动即生效，见 `WaterSurface.Simulation.cs:221-231`），把收敛值回填上表并同步改代码数组。
4. 每级回填后在固定机位截图（其余参数不动），替换"待实机补"列；截图存 `docs/research/2026-09-22-sango-prototype/evidence/m1-beaufort-b*.png`。
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
