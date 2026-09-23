# README-M1 — M1-C 执行手册（海况环境与天气 GUI 骨架导入与实机调锚点）

> **状态（2026-09-23）：M1 已收口**。本手册保留作历史执行记录与故障对照表（§7/§8 仍有效）；
> §0-§2 前置待办已全部落地（方案 A：`M0SceneBootstrapper.ConfigureHdrpAssets` 已 public，
> M1SceneBootstrapper 直接调用），§6 验收清单已由
> `sango/Docs/beaufort-water-mapping.md`"M1 实机核对记录"节取代（勾选见下）。
> **雨/雪 VFX 未在本里程碑实现，显式顺延 M2+**（PLAN §5 M1 内容清单含它但四条验收条款不含，故不阻塞）。

本目录是 M1 代码骨架的暂存区（保持未来在 `sango/` 内的相对路径）。执行者目标：把骨架装进已就绪的
`sango/` 工程（M0 已 PASS），编译出 M1 场景，在 Play 中调出 Beaufort 0-11 海况并把锚点值回填映射表。
验收对照 `docs/research/2026-09-22-sango-prototype/PHASE1-PLAN.md` §5 M1 四条。

骨架文件清单：

```
Assets/Scripts/Runtime/PerlinIslandGenerator.cs     程序化岛屿：2D Perlin 高度场→mesh（静态方法，Editor 可直调）
Assets/Scripts/Runtime/WeatherController.cs         天气状态→HDRP 映射核心（Water band/太阳/云/雾，源码出处全注）
Assets/Scripts/Runtime/WeatherGUI.cs                UGUI 天气面板运行时构建（无 prefab 依赖，legacy Text）
Assets/Scripts/Editor/M1SceneBootstrapper.cs        菜单 Sango/M1/Build Weather Scene（一键建场景，幂等）
sango-docs-beaufort-water-mapping.md                → 复制为 sango/Docs/beaufort-water-mapping.md（映射表交付物）
README-M1.md                                        本手册
```

---

## 0. 前置确认

- [ ] M0 已 PASS：`sango/` 工程可打开、M0-WaterSmoke 场景可跑（HDRP Asset 已配 Water，Quality 档已挂）。
- [ ] 工作区干净：`cd sango && git status --short` 无未预期改动（导入前留底）。

## 1. 导入骨架

```bash
cp -R tmp/sango-skeleton-m1/Assets/Scripts sango/Assets/Scripts/
mkdir -p sango/Docs
cp tmp/sango-skeleton-m1/sango-docs-beaufort-water-mapping.md sango/Docs/beaufort-water-mapping.md
```

（Runtime/Editor 目录与 M0 已有目录合并，无同名文件覆盖。）

## 2. M0 文件一处待办（必须做，二选一）

骨架 `M1SceneBootstrapper.cs` 文件头有同款 TODO 注释。推荐方案 A：

- [ ] **A（推荐）**：`sango/Assets/Scripts/Editor/M0SceneBootstrapper.cs:34` 的 `static void ConfigureHdrpAssets()`
  改为 `public static void ConfigureHdrpAssets()`；删除骨架里 `M1SceneBootstrapper.ConfigureHdrpAssets` 私有副本，
  `Build()` 首行改调 `M0SceneBootstrapper.ConfigureHdrpAssets();`
- [ ] **B（不推荐）**：什么都不改，保留骨架内副本（与 M0 逻辑一致，两处同步维护）。

## 3. 编译预期

- 预期：Console 无红色报错；新增类型 `Sango.PerlinIslandGenerator / WeatherController / WeatherGUI`、
  `Sango.Editor.M1SceneBootstrapper`；菜单出现 **Sango/M1/Build Weather Scene**。
- 依赖核对（均已在本机工程核实，无需操作）：
  - uGUI：`com.unity.ugui 2.0.0` 在 packages-lock（Slider/Dropdown/EventSystem/StandaloneInputModule 齐备）；
  - TMP：运行时程序集在但 **TMP Essentials 未导入**，故面板用 legacy uGUI Text（代码注释注明 M2 可升 TMP）；
  - HDRP 17.3：band/云/雾字段全部按 `Library/PackageCache/com.unity.render-pipelines.high-definition@700710090fa9/`
    源码 file:line 注释（见映射表附录表）。

## 4. 一键建场景

菜单点 **Sango/M1/Build Weather Scene**（跑前保存手头未保存场景——NewScene 重建会丢弃，同 M0）。

- 预期（Hierarchy，全新场景）：
  - `Water Surface`（OceanSeaLake + Script Interactions ✓）
  - `Global Volume`（Profile = `Assets/Settings/M1-GlobalVolumeProfile.asset`：PBS 天空 + Volumetric Clouds
    (Simple/Performance) + Fog + Water Rendering）
  - `Directional Light`（WeatherController 驱动旋转/lux）
  - `Ships/Ship-0..1`（2 艘装饰船占位）
  - `Islands/Island-*`（5 岛，seed 42，岛群中心 (0,0,180) 半径 260m）
  - `Weather`（WeatherController，三引用已接线）
  - `Weather GUI`（Play 时 Awake 自建 Canvas/面板）
  - `Main Camera`（(0,12,-40) 望岛群，fov 60，far 8000）
- 产物文件：`Assets/Scenes/M1-Weather.unity`、`Assets/Settings/M1-GlobalVolumeProfile.asset`。
- 失败排查：同 M0 对照表（水面品红→HDRP Asset/Water Rendering；全黑→PBS/方向光）；
  面板不出现→Play 后 Hierarchy 查 WeatherCanvas/EventSystem 是否生成，Console 查字体告警。

## 5. 实机调锚点（M1-C 主工作）

1. 进 Play。左上角出现深色半透明天气面板：标题、**金色风速读数**、5 根滑条（Beaufort 0-11 步进 0.1 /
   风向 0-360 / 时刻 0-24 / 云量 0-1 / 雾距 100-8000m）、谱档下拉（Calm/Moderate/Rough/VeryRough）。
2. 固定基线：风向 30、时刻 12、云量 0.40、雾距 3000、机位不动（存档点：把面板当前值记下即可，场景幂等可重建）。
3. 逐级拖 Beaufort 停靠 B0/B3/B6/B9，对照映射表"量级目标"看观感：
   B0 近镜面 → B3 明显白沫 → B6 大浪 → B9 惊涛。达不到就按 `sango/Docs/beaufort-water-mapping.md` 调值指引
   改 `WeatherController.cs` 顶部 `Tier*` 数组（或 Play 中直接改 Water Surface 组件字段找手感），收敛值回填表格。
4. 面板风速读数与表格"风速 m/s"列**必须一致**（同出自 `BeaufortToWindSpeedMs`，验收条款 2 的一票否决项）。
5. 每级固定机位截图存 `docs/research/2026-09-22-sango-prototype/evidence/m1-beaufort-b*.png`，替换表格截图列。
6. 录屏：Beaufort 0→9 连续拖动（验收条款 2）。
7. 时刻滑条 12h vs 0h 截图对（正午 vs 暗夜空+微弱月光量级）；雾距 3000m vs 8000m（或 300 vs 8000，以对比明显为准）
   截图对（验收条款 3）。
8. 云量滑条四档（Sparse/Cloudy/Overcast/Stormy 量化阈值 0.25/0.50/0.75）过一遍确认无报错（量化设计见
   WeatherController 注释：HDRP 17.3 无标量 coverage 字段）。

## 6. 验收清单（PLAN §5 M1 四条对照）

> ✅ 2026-09-23 全部核过，证据与逐条记录见 `beaufort-water-mapping.md`"M1 实机核对记录"。

- [x] 1. 映射表有数值锚点：风速列（B0≈0.5/B3≈4.5/B6≈12.5/B9≈22.5 级内中值线性内插）+ band 参数锚点列 +
      锚点档固定机位+固定参数截图（B0/B3/B6/B9，非锚点档未逐级采图）；
- [x] 2. Beaufort 0→9 波高/白帽可感知增强，面板风速与映射表一致（timelapse 代替录屏，原因见核对记录）；
- [x] 3. 截图：时刻正午 vs 深夜；雾距两档对比；
- [x] 4. 四画面之画面3/画面4 天气部分要素核对一次（航行灯与矢量属 M2，本条只对天气项）。

~~全部打勾后：`cd sango && git add -A && git status --short` 核对入库清单（Library/ Temp/ Logs/ 不出现），提交。~~（已收口于 41ad7422；`git add -A` 为仓库禁用操作，原手册措辞作废）

## 7. 故障对照表

| 现象 | 根因 | 处置 |
| --- | --- | --- |
| 拖滑条海面无变化 | Weather 对象引用未接（水/Volume/光为空） | 重跑 Sango/M1/Build Weather Scene；Inspector 查 Weather 组件三引用 |
| 面板风速与表格不一致 | 有人改了 BeaufortToWindSpeedMs 或表格手工填了别的数 | 两者必须同源；以代码为准重算表格 |
| 拖时刻到深夜画面仍亮 | 云量 0 + 雾距小叠加，或强度曲线被改 | 查 Weather.ApplySun 的 0.1 lux 夜间钳值与曝光（HDRP 自动曝光） |
| 云量滑条无观感变化 | 云量被量化到同一预设档（阈值 0.25/0.50/0.75） | 属预期；跨档拖动再看 |
| 雾距滑到 8000 无雾感 | meanFreePath 起调系数 0.25 过大/过小 | 按映射表 TBD 项实机调 `ApplyCloudsAndFog` 系数 |
| Dropdown 点开无菜单 | EventSystem 缺失（场景被手工清理） | 重跑 Bootstrapper；确认 Hierarchy 有 EventSystem |
| 岛屿没入水/悬空 | 噪声种子改动后岸线漂移 | 属正常（岸线由高度场决定）；只许改 seed 后重评截图基线 |
| 编译错 `ConfigureHdrpAssets` 不可访问 | 第 2 步待办没做且删了骨架副本 | 回第 2 步，二选一执行 |

## 8. API 版本基线（代码注释中已内嵌出处）

全部按 **Unity 6000.3 / HDRP 17.3.0** 源码核对（`Library/PackageCache/com.unity.render-pipelines.high-definition@700710090fa9/`）：
Water band 字段（`WaterSurface.Simulation.cs` / `.Foam.cs` 分部类，单位 km/h 陷阱见 `WaterSystemDef.cs:17-23`）、
运行时生效机制（`WaterSurface.Simulation.cs:221-231` 每帧 spectrum 失效重建）、
VolumetricClouds 无标量 coverage 字段（`VolumetricClouds.cs:38-69,216-229`，`cloudPreset` setter 触发预设应用 :502）、
Fog 用现行 `Fog` 组件（`AtmosphericScattering/Fog.cs:29,50,55`；旧 `VolumetricFog` 已 Obsolete）、
Volume 运行时副本改法（core 包 `Volume.cs:55-87` `profile` getter Instantiate `sharedProfile`，`VolumeProfile.cs:231` TryGet）。
若升 Unity/HDRP 版本，先重跑一遍这些 file:line 核对。
