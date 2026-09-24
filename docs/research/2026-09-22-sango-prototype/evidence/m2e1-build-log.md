# M2-E1 build log — encounter scenarios + top-down COLREG view (spec #84)

2026-09-24 · branch `main`（local only, no push）· Unity 6000.3.24f1 + HDRP 17.3.0, Mac M3 arm64 batchmode.
前置：#80–#83 已闭。**编目与 `pipelineVersion` 未动**（gate 日志无 "vessel assets built" 行 = EnsureBuilt 零开销跳过；VesselAssetPipeline / VesselCatalog 零 diff）。

## Gates

| Gate | Command | Result |
|---|---|---|
| EditMode suite（红） | `-batchmode -runTests -testPlatform EditMode -testResults /tmp/m2e1-tests-red.xml`（无 -quit） | exit 2，**82 total / 64 pass / 18 fail** —— 24 条新测试中 18 条对 stub 红恒（全部形态断言 + 碰撞仿真 + 时间球非退化档 + 烘焙艏向合成 + reset；6 条对 stub 空真：时间球退化 interval 档 ×3、确定性、offset=0 默认档）；既有 58 条全绿 |
| EditMode suite（绿，Gate 1） | `-testResults /tmp/m2e1-tests.xml` | exit 0，**82 / 82 / 0**（58 既有 + 24 新增） |
| Headless M1 重建（Gate 2，含放置修复） | `-batchmode -quit -executeMethod Sango.Editor.M1SceneBootstrapper.Build` | **exit 0**；"vessel assets built" 0 次；放置自证行见下节 |
| Headless M2E 重建（Gate 2'） | `-batchmode -quit -executeMethod Sango.Editor.M2ESceneBootstrapper.Build` | **exit 0**；`TMP Essentials import ... OK (37 files extracted)`；两船放置自证行 OK；`scene written: M2E-Encounter.unity` |
| Mono player M1（Gate 3） | `pkill -f 'MacOS/sango'` → `M1VerifyCapture.BuildStandalonePlayer` | **exit 0**，`Succeeded size=184MB out=Builds/M1-Standalone.app`（+2 MB = TMP Essentials 进 Resources） |
| Mono player M2E（Gate 3'） | `M1VerifyCapture.BuildEncounterStandalonePlayer` | **exit 0**，`Succeeded size=182MB out=Builds/M2E-Standalone.app` |
| EditMode suite（终轮复跑，成品态） | `-testResults /tmp/m2e1-tests-final.xml` | exit 0，**82 / 82 / 0** |
| M2E 真机播放器烟测 | `caffeinate -disu Builds/M2E-Standalone.app/Contents/MacOS/sango -screen-fullscreen 0`，75 s 后读 Player.log | `[Sango.M2E] pattern HeadOn: own 'OWN LINER' spawn (100.00, -450.00) hdg 0° 5 m/s wps[1] | target 'TARGET CARGO' spawn (-100.00, 450.00) hdg 180° 4 m/s wps[1] | extent 520m`；两船 `VesselBuoyancy samples=64/63 queries (failed 0)`；**0 exceptions** |

绿轮前编译侧修正三处（非约定问题）：WaypointFollower stub 与正式 ResetToTransform 重复定义（CS0111）；EncounterPanel 按钮构建器返回类型 Text vs Button（CS0029）；M2E bootstrapper 缺 `UnityEngine.Rendering` using（CS0246）+ `PackageInfo` 二义（CS0104，显式消歧）。

## 放置层修复（spec #84 授权，M2-D 遗留 heading+180° 陷阱）

`M1SceneBootstrapper.PlaceCatalogShip`（改 public static，M2E bootstrapper 复用同一放置路径）：

- **修复前**：`rotation = Euler(0, heading, 0)` 绝对赋值，覆盖 prefab 根上"原生艏→+Z"烘焙 —— Medium（bowYaw 180°）以艉朝 heading 渲染（视觉艏 = heading+180°）。天气场景 Medium @ (30,90) heading −35° → 根 eulerY −35°，视觉艏 145°。
- **修复后**：`rotation = Euler(0, heading, 0) · Euler(0, BowYawDeg(class), 0)`（组合烘焙）。渲染艏（世界）= rotation·原生艏向量 = heading，对全部档位成立。
- **重建后自证**（batchmode 日志逐行"expected vs actual"）：
  - `placed Small @ (14,-6) heading 20° + bowYaw 0° -> root eulerY 20°, rendered bow (0.34,0,0.94) expect heading dir (0.34,0,0.94)` ✓
  - `placed Medium @ (30,90) heading -35° + bowYaw 180° -> root eulerY 145°, rendered bow (-0.57,0,0.82) expect heading dir (-0.57,0,0.82)` ✓
  - 场景 YAML 复核：M1-Weather Medium PrefabInstance `m_LocalRotation (0, 0.953717, 0, 0.3007058)` = yaw 145°（= −35 + 180）逐位吻合。
- **一次性观感变化（预期内）**：天气场景邮轮渲染朝向翻转 180°（艏朝 heading，不再艉朝 heading）。M2-D 灯具锚点在根局部空间随根旋转，无回归。
- **跟随器同坑同修**（composition 契约的另一半）：WaypointFollower 新增 `bowYawDegOffset`（默认 0 = M1/M2-C 行为逐位不变）——初始化捕获 `psi = euler.y − offset`，写回 `rotation.y = psi·Rad2Deg + offset`。EditMode 测试钉死：offset 180 + 放置 eulerY 180 → 导航艏向 0（北）且渲染艏指北。M2E 两船由 bootstrapper 注入 `BowYawDeg(Medium)=180 / BowYawDeg(Large)=0`。

## 纯核心（Sango.Vessels，确定性、无引擎 API）

- **`EncounterGeometry.Build(type, area)`** → `EncounterPattern{Own, Target, ExtentM}`，`EncounterRole{SpawnXZ, HeadingDeg, CruiseSpeedMps, Waypoints, Label}`。own = Medium liner（直航/追越船），target = Large cargo（让路/被追越船）。缺省场域 900×300 m。
- **`TrackClock.BallsDue(simTime, interval)`** = floor(t/N)，t<N → 0，N≤0 禁用（每 N 仿真秒一球，首个恰在 N；worked examples 钉死在测试）。

### 模式几何（worked examples，COLREGs 形态全部测试钉死）

| 类型 | own (liner) | target (cargo) | 会遇形态 / 最小间距（仿真实测） |
|---|---|---|---|
| Head-on | spawn (100, −450) hdg 0° 5 m/s → (100, 450) | spawn (−100, 450) hdg 180° 4 m/s → (−100, −450) | 艏向互逆、右行车线（own 东线）；最近会遇 t≈101 s 间距 **200.0 m**，target 在 own 左舷（lateral −200 m）= **port-to-port** |
| Crossing | spawn (0, −450) hdg 0° 5 m/s → (0, 450)（stand-on） | spawn (450, 350) hdg 270° 4 m/s → (−450, 350)（give-way） | target 方位 29°（own 右舷艏侧，starboard hand ✓）、正交横越；最小间距 t≈143 s **149.1 m** |
| Overtaking | spawn (0, −150) hdg 0° 6 m/s → (150, 300), (150, 700) | spawn (0, 225) hdg 0° 3 m/s → (0, 700) | 同向总轨迹；target 在 own 正前 0°、own 在 target 艉后 180°（rule-13）；own 经东舷 150 m 平行车道的动态追越（t≈135 s target 仍在航），最小间距 **149.7 m**；终态双车停在 z≈692 侧距 150 m |

全部三型：真实 WaypointFollower.StepOnce 全航程仿真（0.1 s 步）min sep ≥ **125 m（=1.25× Large LOA，独立真值）**，双双到终点。不设并回腿：对仍在航慢船的"超车并回"几何上不存在碰撞自由的时机（实测并回腿最近 104–117 m < 125 m 裕度），时机决策属 phase 2 —— 追越在平行车道完成后即收束。

- **碰撞自由仿真走真实消费路径**：测试里起两个真 `WaypointFollower`（`bowYawDegOffset` 180/0），非几何抽象复算 —— 航点推进/减速/转弯语义与运行时逐位一致。
- **`WaypointFollower.ResetToTransform()`**：清初始化/到达/索引/速度，reset 流程 = 摆位姿 → 换表 → 调它（Toggle 无法从"暂停中"强制重置，故新增；不属运动代码）。

## 遭遇场景（M2E-Encounter.unity + 运行时构建）

- **Bootstrapper**（`Sango.Editor.M2ESceneBootstrapper.Build`，幂等）：深蓝开阔水面（Ocean + Script Interactions，**无岛**）+ 独立 `M2E-GlobalVolumeProfile.asset`（不与 M1 共享：M1 重建先删后建换 GUID，共享会静默断引用）+ 方向光 + WeatherController/WeatherGUI（复用，面板左上）+ 两编目船（放置修复路径）+ WaypointFollower×2（**enabled=false**，demoHotkeysEnabled=false）+ EncounterDirector + EncounterPanel（右上角）+ 北向上正交俯视相机（`LookRotation(down, north)`：屏上=北、屏右=东，海图方向）。
- **EncounterDirector**（纯编排零运动代码）：仿真时钟（累积 `min(Time.deltaTime, 0.1)·timeScale`；暂停/倍速只作用于此时钟，天气/浮力照常）→ `follower.StepOnce(simDt)`；Start/Pause（完局再按=重跑）、×1/×2/×4 循环、Reset；每 tick 追加双船轨迹点（3 m 抽稀）+ 按 TrackClock 对账落时间球（默认 10 s）；模式切换按 `ExtentM` 重设正交视野（520/520/720 m）。
- **EncounterView**：双轨迹 LineRenderer（own 青 (0.25,0.85,1)、target 琥珀 (1,0.72,0.15)，宽 2.5 m 贴水面 y=0.4）、时间球（直径 7 m 贴水小球、色随船）、Start/WP 标签 ×4（TMP 世界文本，平铺水面字头朝北；偏东北 30 m 防压轨迹）、50 m 比例尺（白线 + "50 m" 标签，视野南缘）。材质 = 运行时 HDRP/Unlit（M2-D 同款，真机已验证路径）。
- **EncounterPanel**（WeatherGUI idiom：深色半透明 UGUI 运行时构建、legacy Text、零资产依赖、右上角 400 px）：模式 dropdown（3 选项 + 双船 spawn/hdg/speed 描述行，描述自占一行）、Start⇄Pause、×1/×2/×4、Reset、仿真时钟读数；键盘 Space/R/1-3/X（见验收后修复轮）。

## TMP Essentials（spec 要求，所需手工步骤 = 零；有实现曲折）

- `AssetDatabase.ImportPackage` 在 `-batchmode -quit` 下是"排队到下个 editor tick"语义，批跑直接退出 → **永不执行**（首轮实测 FAILED，资产未落）。
- 落地：bootstrapper 内手工解包 unitypackage（gzipped tar：`<guid>/asset + asset.meta + pathname`，逐 512 字节头解析，GUID 原样保留 = 与菜单导入同结果）→ `Assets/TextMesh Pro/`（TMP Settings + LiberationSans SDF 等 37 文件）→ Refresh。幂等（已存在即跳过）。**该资产目录随本批提交**（标准做法：TMP Essentials 属 Assets 内版本化资产）。

## Player 构建场景处理

`BuildStandalonePlayer` 的场景表是**显式单场景列表**（`new[] { "Assets/Scenes/M1-Weather.unity" }`，EditorBuildSettings 为空）。多场景打包可行但 scene 0 只有一个——为不扰动 M1 播放器验收流程（scene 0 = M1 保持逐字节不变），**新增独立构建方法** `M1VerifyCapture.BuildEncounterStandalonePlayer` → scene 0 = M2E-Encounter，输出独立 `Builds/M2E-Standalone.app`。两个 app、两条验收路径，互不干扰。

## 偏离与说明

- spec "at most one new key if genuinely needed" → 落地为四键（Space/R/1-3/X）：编排验收在本机被 CUA 鼠标不可靠卡死后追加（与 M1 天气热键 / M2-C G 键同级的正式演示输入）；冲突以 WeatherGUI 数字档门控收敛（见验收后修复轮）。
- 任务书说追越"target astern"——按 rule-13 与"target slower / own faster"自洽解读为：**own 自 target 艉后追上**（target 在前、在 own 正前扇区；own 在 target 艉后扇区 >135°）。测试按此钉死（`Overtaking_OwnAsternFasterOnSameGeneralTrack`）。
- 追越模式无"超车并回"腿（见上节几何表注）：几何上无法 while-keep-safe 并回，时机决策留给 phase 2。终态为双车并行 150 m，非串线排队。
- 世界标签阅读方向用了 TMP 负缩放镜像技巧（`rotation = Euler(0,180,0)·Euler(−90,0,0)` + `localScale.x = −0.2`，SDF shader Cull Off 安全）——俯视北向上可读。若编排验收发现字面镜像，一行回退：去掉 localScale 的负号（标签变为字头朝南）。
- 场景重建连带重生 `M1-GlobalVolumeProfile.asset` / 新建 `M2E-GlobalVolumeProfile.asset`（builder 既有幂等行为，与场景同 commit）。
- `Assets/Resources/PerformanceTestRun*.json` 为 test framework 运行产物，未纳入提交。

## 验收后修复轮（键盘操作 affordance + 面板布局，spec #84 追加）

**背景**：编排方视觉验收被操作输入卡死 —— 本机 CUA 鼠标点击不可靠（UGUI 点击坐标被忽略、事件落在物理光标位置，与 M1 结论同源，当日复核）；键盘（accessibility 注入）是唯一可靠的程序化输入。遭遇面板补齐与 M1 天气热键 / M2-C G 键同级的正式键位。

**键位（EncounterPanel.Update 自持 HandleHotkeys，不经 WeatherGUI）**：

| 键 | 动作 |
|---|---|
| `Space` | Start ⇄ Pause（完局后再按 = 重跑） |
| `R` | Reset（回当前模式初始几何） |
| `1` / `2` / `3` | 选模式：head-on / crossing / overtaking |
| `X` | 时间倍率循环 ×1 → ×2 → ×4 |

**键位冲突账本**（同屏 WeatherGUI + EncounterPanel + WaypointFollower）：

- WeatherGUI 数字键 0-9（直设蒲福级）与 1/2/3 一键双义 → 新增 `WeatherGUI.digitHotkeysEnabled`（默认 true，M1 零变更），遭遇场景 bootstrapper 置 false —— 遭遇场景里 1/2/3 唯一归模式选择，0/4-9 空闲；**T/F（时刻/雾距预设）保留给天气侧**。
- G 为 per-instance 门控（demoHotkeysEnabled），遭遇两船未启用。
- Space 无主；另有 UI 焦点双触发坑（鼠标点过的按钮持有焦点，StandaloneInputModule 会把 Space/Enter 再派发给它）→ 面板每帧清空 EventSystem 选中，Space 只走面板处理器。

**键鼠状态同步**：键盘与按钮走同一条路（改 director 状态 → 同一 MirrorState 回读）——dropdown 选中项 / Start⇄Pause 标签 / ×N 标签 / 时钟读数恒一致；每次键入都有 `[Sango.M2E] hotkey ...` 日志行（模式切换另打既有 pattern 全行）。

**布局修复（验收截图发现）**：PatternDropdown 建立后 `_cursorY` 未推进，PatternDesc 与下拉框选中项标题同 y 重叠（截图中 "own liner 5 m/s from…" 压在 "head-on (port-to-port)" 上）——描述行自占一行（下移 34+6 px）。面板提示行同步改为键位清单 `Space start/pause · R reset · 1/2/3 pattern · X speed`。

| Gate（修复轮） | Command | Result |
|---|---|---|
| EditMode suite | `-testResults /tmp/m2e1-tests-keys.xml`（无 -quit） | exit 0，**82 / 82 / 0**（键位是引擎 Input，非纯缝可测——按约不加测试） |
| Headless M1 重建 | `M1SceneBootstrapper.Build`（带 -quit） | **exit 0**；放置自证行与上轮逐位一致 |
| Headless M2E 重建 | `M2ESceneBootstrapper.Build`（带 -quit） | **exit 0**；Weather GUI 序列化 `digitHotkeysEnabled: 0` |
| Mono player M1 | `BuildStandalonePlayer` | **exit 0** |
| Mono player M2E | `BuildEncounterStandalonePlayer` | **exit 0** |

## Orchestrator 视觉验收清单

- **Head-on**：两船从上/下边缘对开，各偏东西 100 m；交汇点在画面中部，各自左舷对对方（左舷对左舷通过），全程间距 ≥200 m；青线（liner，南→北）与琥珀线（cargo，北→南）平行对拉，时间球每 10 s 一颗对称分布。
- **Crossing**：liner 自南正北直航，cargo 自右侧（东）横越航向正西，横越点在 liner 前方约 350 m；cargo 从 liner 右舷侧驶来（rule-15 形态）；时间球揭示 cargo 更慢（4 vs 5 m/s）。
- **Overtaking**：双船同向北上；liner（青，6 m/s）自 cargo（琥珀，3 m/s）艉后追上，经东舷 150 m 车道完成动态超越后终点减速；t≈135 s 前后超越瞬间最直观；时间球间距对比呈现速度差。
- **面板（右上角）**：模式 dropdown 三项（切换即重摆+清轨迹）、Start⇄Pause（完局后再按=重跑）、×1/×2/×4 循环、Reset、仿真时钟读数 `t = N s (paused)`；**键盘为正式操作输入**：`Space` start/pause、`R` reset、`1/2/3` 选模式、`X` 倍率；天气侧 `T/F` 仍有效，遭遇场景数字键归模式选择（蒲福数字档已关），遭遇船不响应 G。键鼠状态经镜像恒同步。
- **标签/比例尺**：各轨迹起点 "Start OWN / Start TARGET"、终点 "WP OWN / WP TARGET"（色随船、平铺水面、向东北偏 30 m 不压轨迹）；画面南缘白色 50 m 比例尺线 + "50 m" 标签。俯视正交相机北向上（模式切换自动缩放视野 520/520/720 m）。
- **健康线**：暂停时船随浪起伏（浮力照常）、×4 下轨迹拉伸速率 ×4；天气面板（左上）仍可调风浪。

## Orchestrator visual acceptance (2026-09-24)

- First acceptance attempt was BLOCKED at the controls: CUA mouse clicks
  cannot drive UGUI buttons on this machine (coordinates ignored, events land
  at the physical cursor — re-confirmed; keyboard is the only reliable
  programmatic input). Fixed by the hotkey round (abb92476): Space/R/1-2-3/X
  on the panel, weather digit hotkeys gated off in this scene
  (digitHotkeysEnabled=0), dropdown overlap fixed.
- Driven run on M2E-Standalone (windowed 1600x900), ×4 time scale:
  - `m2e1-initial-topdown.jpg` — north-up top-down orthographic, two ships at
    spawns with correct rendered headings (placement fix visible: liner bow
    north), ENCOUNTER panel (pattern row + own-row description + Start/×1/Reset),
    weather panel, 50 m scale bar, deep-blue no-island sea.
  - `m2e1-headon-converging.jpg` / `m2e1-headon-passed-paused.jpg` — amber
    (cargo) and cyan (liner) tracks with evenly spaced time balls; right-hand
    lanes → port-to-port pass; Space pause freezes mid-run, ships still bob
    (buoyancy), Start label restored while paused.
  - `m2e1-crossing.jpg` — cargo entering from east heading west, liner
    northbound: target on own starboard hand (rule-15 picture).
  - `m2e1-overtaking.jpg` — cargo ahead slower, liner overtaking from astern,
    both heading north (rule-13 picture).
- Verdict: PASS (all three patterns, tracks/balls/labels/scale-bar/panel
  controls verified).
