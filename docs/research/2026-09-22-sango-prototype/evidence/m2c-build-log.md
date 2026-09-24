# M2-C build log — 3-DOF waypoint follower (spec #82)

2026-09-24 · branch `main`（local only, no push）· Unity 6000.3.24f1 + HDRP 17.3.0, Mac M3 arm64 batchmode.
前置：#80 / #81 已闭。**编目与 `pipelineVersion` 未动**（gate 2 日志无 "vessel assets built" 行 = EnsureBuilt 零开销跳过）；VesselAssetPipeline / VesselCatalog 零 diff。

## Gates

| Gate | Command | Result |
|---|---|---|
| EditMode suite（红） | `-runTests -testPlatform EditMode -testResults /tmp/m2c-tests-red.xml` | exit 2（有失败），**43 total / 32 pass / 11 fail** —— 12 条新测试中 11 条对 stub 核心红（唯一绿的是确定性护栏型，对 stub 恒真，与 M2-B 同款纪律）；既有 31 条全绿 |
| EditMode suite（绿，Gate 1） | 同上 `/tmp/m2c-tests.xml` | exit 0，**43 total / 43 pass / 0 fail**（31 既有 + 12 新增） |
| Headless scene rebuild（Gate 2） | `-executeMethod Sango.Editor.M1SceneBootstrapper.Build`（**须带 `-quit`**：`-runTests` 自带退出语义，`-executeMethod` 没有——首轮忘带挂起 20 min，杀进程清 UnityLockfile 后复跑） | **exit 0**；`[Sango.M1] M2-C waypoint demo wired on Small ship: press G to sail/stop; route (14,-6) -> (40,0) -> (60,-20) -> (20,-30) -> (5,-12), cruise 5 m/s`；场景 YAML 含 WaypointFollower 组件 |
| Mono standalone player（Gate 3） | `-executeMethod Sango.Editor.M1VerifyCapture.BuildStandalonePlayer` | **exit 0**，`Succeeded size=182MB out=Builds/M1-Standalone.app` |
| 真机播放器实测 | `caffeinate -disu .../MacOS/sango -screen-fullscreen 0 -screen-width 1600 -screen-height 900`，25s 后读 Player.log | 见下节，**failed 0、跟随器 idle 无干扰** |

绿轮前三条测试修正记录（均为测试侧算术/边界，非约定问题）：
1. 约定例（东/北位移）原用 `P()` 默认 cruise=5 > 当前速 4，`MoveTowards` 一步内把速度拉满 → 位移 2.5 非 2.0；改 `cruise:4` 让几何例干净（4 m/s × 0.5 s = 2 m）。
2. 转艏测试原断言"速度 0 不位移"，但核心语义是"当步先加速再沿新艏向积分"，首步位移 ≤ accel·dt² = 0.02 m 属正确行为；改为独立物理上界断言。
3. **真实设计修正**：减速剖面原定"零速点恰在到达半径边界 R"，离散步进下步进位移在距边界毫米级时低于浮点分辨率，船在半径外渐进 stall、`WithinArrival` 永不触发。零速点内移 δ=0.5 m（`k_StopInsideMarginM`）后停船点确定落在半径内（到达触发，残余速度 ≤0.16 m/s 时被适配器归零，观感无感）。

## 核心（Sango.Vessels.WaypointKinematics，纯静态、无引擎 API、同输入逐位同输出）

API：
- `VesselKinematicState { X, Z, Psi, Speed }` —— 位姿+速度真值载体，仅此四字段（结构即"跟随器只产 x/z/yaw/速度"的结构性断言；引擎写回范围由适配器测试守）。
- `WaypointKinematicsParams { CruiseSpeedMps, MaxYawRateRadPerSec, ArrivalRadiusM, MaxAccelMps2 }`，Default = 5 m/s / 20°/s / 8 m / 2 m/s²。
- `WithinArrival(in state, Vector2 wp, float radiusM)` —— 水平距离 ≤ 半径（含边界）。
- `Step(in state, Vector2 wp, bool isFinal, in params, float dt)` —— 单步：速度目标（巡航值；终点腿减速剖面）→ MoveTowards 有界逼近 → 转艏有界捕捉方位 `atan2(Δx, Δz)`（WrapPi 取最短弧）→ 沿新艏向积分。dt≤0 原样返回。

**钉死坐标约定**（web GUI scene-geography 先例，永不翻转）：东 = +x，北 = +z，psi 弧度、`rotation.y = +psi·Rad2Deg`，艏向单位向量 = (sin psi, cos psi)——psi=0 朝北，psi=+π/2 朝东，psi 增大 = 俯视顺时针 = Unity rotation.y 增大。相位 2 后端位姿直接对齐。

**终点腿减速剖面**：target = cruise·clamp01((dist − (R−δ)) / 2R)，δ=0.5 m（零速点内移半径内，理由见 gates 节 #3）；进入到达半径后 target=0 且保艏向（不调头不打舵）。默认档下剖面所需最大减速度 = cruise²/(2·2R) ≈ 0.78 m/s² < MaxAccelMps2 = 2 → 速度跟得住剖面，入位残余速度 ~0.15 m/s 量级。

## 测试钉死的关键约定（worked examples，独立几何事实，非回声）

| 例 | 输入 | 断言 |
|---|---|---|
| 朝东 | psi=+π/2、速 4、wp 正东、dt 0.5 | x +2.0（4 m/s×0.5 s），z ≈ 0，psi 不变 |
| 朝北 | psi=0、速 4、wp 正北、dt 0.5 | z +2.0，x ≈ 0 |
| 向东转 | psi=0、wp 正东、20°/s、dt 0.1 | psi = +0.0349 rad（恰 2°）> 0 且 < 90°（no snap）；位移 ≤ accel·dt² |
| 跨 ±180 缝 | psi=+170°、目标方位 −170° | 取 +20° 最短弧（步进 +2°），非 −340° |
| 起步 ramp | 静止、wp 正北 500 m、2 m/s²、dt 0.1 | 首步速 0.2，单调升至 5.0 收敛；步加速度 ≤ 0.2 |
| 终点减速 | 5 m/s 直冲 40 m 外终点（R=8）、dt 0.05 | 减速带内明显减速；半径边界速度 ≤ 0.5；收敛后速度 0、停船点距终点 ≤ 8；此后 50 步 x/z/psi/speed 逐位冻结 |
| 半径内到终点 | dist 4 < R、速 3、isFinal | psi 不变（保艏向），速 3→2.8 |
| 到达边界 | 距 wp 5、R=5 / R=4.9 | true（≤ 含边界）/ false |
| 确定性 | 137 步转弯+变速场景双跑 | x/z/psi/speed 逐步逐位相等 |

适配器（WaypointFollower，Sango.Vessels 薄壳）测试：StepOnce 只写 position.x/z 与 rotation.y，y（−0.33 水线）/euler X（2°）/euler Z（1°）分毫不动（M2-B 合成契约另一半）；到达半径内推进航点索引（中间到达不停车）；终点到达即 `IsArrived` 且位姿冻结。G 键热键无法在 EditMode 测（Input 为 player-only），属薄 Update 层，键位冲突以 grep 全库 `GetKeyDown` 兜底（仅 WeatherGUI 0-9/T/F）。

## 参数与 demo 航线

| 参数 | 值 | 依据 |
|---|---|---|
| CruiseSpeedMps | 5 m/s（≈9.7 kn） | 12 m 渔船排水速航速量级（hull speed ≈4.6 m/s），场景尺度下运动可读 |
| MaxYawRateDegPerSec | 20°/s | 小 craft 灵活但船感（30°/s 以上开始像快艇）；90° 转弯 ≈4.5 s |
| ArrivalRadiusM | 8 m | ≈2/3 LOA，中间航点不甩尾、终点停船点位精度足够 |
| MaxAccelMps2 | 2 m/s² | 0→5 m/s 2.5 s，demo 节奏紧凑；≥ 剖面所需 0.78，减速充分 |

Demo 航线（挂小渔船，泊位 (14,-6) yaw 20°，桥楼相机最近）：`(14,-6) →G→ (40,0) → (60,-20) → (20,-30) → (5,-12)`，全程 ≈119.6 m，巡航 5 m/s + 3 次 ~90° 转弯 + 终点减速 ≈ **30 s**。G 再按 = 硬暂停/恢复；到达后再按 = 从当前位置重跑全程。

清水走廊核算（seed-42 五岛，可视岸线 ≈0.8R）：
- isl2 (142,-17) R67 vis 53.6：W2 (60,-20) 距 82.0（裕 28.5）
- isl3 (129,33) R98 vis 78.4：leg W1→W2 最近逼近 (68,-28) 距 86.3（**裕 ≈7.9，全线最小**）；W2 本身在任务书"proven clear"走廊端点
- isl5 (-31,52) R76.5 vis 61.2：起点/W4 均距 73.4（裕 12.2）
- isl1/isl4 全线距离 >150 m。返程段 W2→W3→W4 逐步远离 isl2/isl3。

## 真机播放器实测（Gate 3 后）

跟随器 idle（G 未按，demo 不自启）25 s，Player.log `[VesselBuoyancy]` 10s 周期行逐字：

```
[VesselBuoyancy] VesselMedium: samples=64 queries=64 (failed 64) query_ms=0.440 target(h/r/p)=0.00/0.00/0.00 smoothed=0.00/0.00/0.00
[VesselBuoyancy] VesselSmall: samples=60 queries=124 (failed 124) query_ms=0.449 target(h/r/p)=0.00/0.00/0.00 smoothed=0.00/0.00/0.00
[VesselBuoyancy] VesselMedium: samples=64 queries=64 (failed 0) query_ms=0.210 target(h/r/p)=0.00/-0.01/0.00 smoothed=0.00/0.00/0.00
[VesselBuoyancy] VesselSmall: samples=60 queries=124 (failed 0) query_ms=0.405 target(h/r/p)=0.00/-0.01/0.00 smoothed=0.00/-0.01/0.00
[VesselBuoyancy] VesselMedium: samples=64 queries=64 (failed 0) query_ms=0.331 target(h/r/p)=0.00/0.01/0.00 smoothed=0.00/0.00/0.00
[VesselBuoyancy] VesselSmall: samples=60 queries=124 (failed 0) query_ms=0.645 target(h/r/p)=0.00/0.02/0.01 smoothed=0.00/-0.01/0.01
```

首 tick 全失败 = 水面回读未就绪（M2-B 既有已知时序，非回归）；其后 failed 0、目标近零、log 无 WaypointFollower 报错 —— 移动系统待命不影响浮力，合成契约 idle 侧成立。按键驱动的航行合成（sail 时 failed 仍 0、船动而姿态正常）由编排 agent 视觉验收。

## 遗留与偏离

- 参数比 spec 命名的三个多暴露一个 `MaxAccelMps2`：spec 的"speed ramps to cruise / decelerates to zero"需要有界速率才是确定性可测的（回放/对齐也要求它入参）。默认档四参数一体记录于本文件。
- G 停止是硬暂停（不步进，浮力照常）；优雅减速停船只属于终点到达。demo 语义下按 G 即走即停，不为此加第三种核心模式。
- 场景 rebuild 会连带重生成 M1-GlobalVolumeProfile.asset（幂等 builder 先删后建，子资产 fileID 全变）——与场景同 commit 保持 GUID 一致，属 builder 既有行为非本次引入。

## 验收后清理轮（visual acceptance PASS 后，review 三项）

| Gate | Command | Result |
|---|---|---|
| EditMode suite（红，新钳制测试） | `-testResults /tmp/m2c-tests-red2.xml` | exit 2，44 total / 43 pass / **1 fail**：`StepOnce_ShorterWaypointListSwappedMidRoute_NoThrow_ConsistentState` 抛 `IndexOutOfRangeException`（review 预判复现） |
| EditMode suite（绿，Gate 1'） | `/tmp/m2c-tests.xml` | exit 0，**44 total / 44 pass / 0 fail**（43 + 1 新增） |
| Headless scene rebuild（Gate 2'） | `M1SceneBootstrapper.Build`（带 `-quit`） | **exit 0**；场景含 `m_Waypoints`（新序列化名）与 `demoHotkeysEnabled: 1`（仅小渔船） |
| Mono player（Gate 3'） | `M1VerifyCapture.BuildStandalonePlayer` | **exit 0** |

三项修复：
1. **运行时换表钳制（M2-E 足枪）**：`waypoints` 由公共字段改为属性（序列化后备字段 `m_Waypoints`），赋值即把活动索引钳入 [0, len−1]（空表归 0）；`StepOnce` 消费点再加一道兜底钳制（防旁路 setter 的换表路径）。已到达态不被赋值清除——到达后换表按 G 即从当前位置重跑新表（Toggle 语义）。新测试钉死：换短表后下一步不抛异常、索引归 0、不误判到达、y 不动。
2. **WrapPi 注释对齐实际契约**：`Mathf.Repeat(a+π, 2π)−π` 返回 **[−π, π)**（±π 处映射到 −π），注释由 (−π, π] 改正；行为不动（确定性、±180° 缝测试钉住）。
3. **demo 热键按实例门控**：G 键轮询移到 `demoHotkeysEnabled`（serialized，默认 **false**）之后——M2-E 多跟随器实例"一按全动"消除；仅 M1SceneBootstrapper 的小渔船 wiring 置 true。M1 bootstrapper 日志行不变（小渔船仍响应 G）；G=启停/暂停/重跑语义不变。

## Orchestrator visual acceptance (2026-09-24)

- Player (windowed 1600x900), G pressed via accessibility keyboard path
  (after one window-offscreen retry — known topology flake; note: double-G
  = start+freeze, single-G resumes, semantics as documented).
- `m2c-route-strip.png` — four frames across the run: heading changes
  gradually (rate-limited turns, no snap), position migrates along the
  route, hull stays in clear water the whole way (no island grounding).
- `m2c-arrived.jpg` vs `m2c-arrived-plus5s.jpg` — end of route: boat at
  rest near the final waypoint; the two frames differ only in wave
  shimmer, position/heading identical (vessel stop confirmed).
- Buoyancy composition while under way: visible wave heel in moving
  frames; live `[VesselBuoyancy]` lines during sailing show failed 0,
  124 queries/frame, ~0.38-0.58 ms (unchanged budget).
- Verdict: PASS.
