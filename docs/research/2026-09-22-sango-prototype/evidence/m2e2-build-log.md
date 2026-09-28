# M2-E2 build log — camera switcher, bridge vectors, radar sweep, Simulation panel (spec #85)

2026-09-24 · branch `main`（local only, no push）· Unity 6000.3.24f1 + HDRP 17.3.0, Mac M3 arm64 batchmode.
前置：#80–#84 已闭。**编目与 `pipelineVersion` 未动**（gate 日志无 "vessel assets built" 行；VesselAssetPipeline / VesselCatalog 零 diff）。

## Gates

| Gate | Command | Result |
|---|---|---|
| EditMode suite（红） | `-batchmode -runTests -testPlatform EditMode -testResults /tmp/m2e2-tests-red.xml`（无 -quit） | exit 2，**108 total / 83 pass / 25 fail** —— 26 条新测试 25 条对 stub 红（1 条 `MapToSettings_IdentityAtScaleOne` 对 default-stub 空真，绿轮钉到真实现）；既有 82 条全绿 |
| EditMode suite（绿） | `-testResults /tmp/m2e2-tests.xml` | exit 0，**108 / 108 / 0**（82 既有 + 26 新增：CameraViews 7 / RadarMath 8 / IslandRebuild 4 / VectorArrowMath 7） |
| EditMode suite（终轮复跑，成品态） | `-testResults /tmp/m2e2-tests-final.xml` | exit 0，**108 / 108 / 0** |
| Headless M1 重建（Gate 2） | `-batchmode -quit -executeMethod Sango.Editor.M1SceneBootstrapper.Build` | **exit 0**；放置自证行与 E1 验收逐位一致（Small eulerY 20° / Medium eulerY 145°）；`[Sango.M2E2] wired: ...` 接线行在案 |
| Headless M2E 重建（Gate 2'） | `-batchmode -quit -executeMethod Sango.Editor.M2ESceneBootstrapper.Build` | **exit 0**；TMP Essentials already present；两船放置自证 OK |
| Mono player M1（Gate 3） | `pkill -f 'MacOS/sango'` → `M1VerifyCapture.BuildStandalonePlayer` | **exit 0**，`Succeeded size=184MB`（两次：首轮 + 预览底板修复轮） |
| Mono player M2E（Gate 3'） | `M1VerifyCapture.BuildEncounterStandalonePlayer` | **exit 0**，`Succeeded size=182MB` |
| M1 真机播放器烟测（75 s / 70 s 两轮） | `caffeinate -disu Builds/M1-Standalone.app/Contents/MacOS/sango -screen-fullscreen 0` | **0 exceptions**；矢量 rig 构建行、预览舞台构建行、fps 行在案（见下） |
| M2E 真机播放器烟测（45 s） | 同上 M2E app | **0 exceptions**；`pattern HeadOn` 行在案；**新增 PlaceShip 组合断言零报错**（Medium bowYaw 180 / Large bowYaw 0 双船过） |

绿轮前/后编译与运行侧修正：`Slider` 无 `rectTransform` 包装（CS1061 → `(RectTransform)transform`）；预览底板 `Image + RawImage` 同 GameObject 双 Graphic 运行时异常（"Can't add 'RawImage' … 'Image' is already added"，真机烟测抓获）→ RawImage 自任底板。

## 键位总账（M1 天气场景，本批新增均不撞 0-9/T/F/G）

| 键 | 动作 | 归属组件 |
|---|---|---|
| `0-9` / `T` / `F` | 天气（蒲福直设 / 时刻循环 / 雾距循环） | WeatherGUI（不动） |
| `G` | demo 航行启停（既有语义，per-instance 门控） | WaypointFollower（不动） |
| `C` | 相机循环 Bridge → Bow → Chase → TopDown → Bridge | CameraRig |
| `V` | 矢量箭头总开关 | VectorArrows |
| `A` | Autonomous Control（G 的面板重复键，键鼠同路经同一次 Toggle） | AutonomousControlPanel |
| `Q` / `E` | 雷达量程 −/+ 100 m（200..2000，即时生效） | RadarOverlay |
| `Z` / `X` | 扫描转速 −/+ 15°/s（15..180，即时生效） | RadarOverlay |
| `-` / `=` | 岛屿数量 ∓1（1..15，面板字段，待 Apply） | SimulationPanel |
| `,` / `.` | 岛屿缩放 ∓0.25（0.25..3，面板字段，待 Apply） | SimulationPanel |
| `Enter` | Apply（= 面板 Apply 按钮；重建岛群 + 雷达参数收权） | SimulationPanel |
| `P` | 预览档位循环 Small → Medium → Large | SimulationPanel |

每次键入均有 `[Sango.M2E2] ...` 日志行（自动化审计）。面板 hint 行同文展示。Enter 的 UI 焦点双触发以每帧清 EventSystem 选中规避（EncounterPanel 同款）。鼠标可点：Apply / Start-Pause / 三档 class 按钮全为可点 Button；滑条拖动即时（雷达）或进字段（岛群）。

## 相机四视图定义（纯函数 CameraViews.Resolve，坐标约定东=+x 北=+z 艏向自北顺时针）

| 视图 | 位姿（相对船） | 朝向 | 跟船 | 投影 |
|---|---|---|---|---|
| Bridge | 固定 (0, 12, −40)（M1 既有机位，零观感变化） | yaw 0°、pitch −0.52°（望岛群中心） | 否 | 透视 60° |
| Bow | 艏向单位向量 × 8 m + 上 4.5 m（艏部上空） | 沿艏向、pitch −8° | 是 | 透视 60° |
| Chase | −艏向 × 30 m + 上 18 m（艉后上方） | 沿艏向、pitch −26.6°（望船） | 是 | 透视 60° |
| TopDown | 船正上空 150 m | pitch −90°、yaw 0（北向上，海图方向） | 是 | 正交半高 70 m |

切换：位置 Lerp + 旋转 Slerp，smoothstep 1 s；跟船视图过渡完成后逐帧贴实时目标（demo 航行中跟得上）。**documented 偏离**：透视⇄正交投影类型不可插值，切 TopDown 时投影在过渡开始瞬间瞬切。艏向含烘焙补偿？相机用船根 euler.y（bow/chase 贴渲染艏；demo 船 bowYaw=0 无差）。

## 雷达（RadarOverlay，右下角）

- 形态：**screen-space 圆盘**（自选并记录；world-space disc 会与正交 TopDown 冲突）。
- 北向上（encounter 俯视同款海图方向）：归一化 blip (右=东, 上=北) = RadarMath.BlipNormalized。
- 盘面纹理运行时生成（256² ）：暗绿半透明盘 + 1/2 量程环 + 满量程环 + 十字刻线 + 亮外缘；盘顶 "N"。
- 扫描线：细长条 pivot 在盘心，`localRotation.z = −角度`（屏幕系顺时针），默认 45°/s。
- blip：其他船真值位置（琥珀红 10 px），出量程 `RadarMath.InRange=false` 即隐藏（无衰减边瓣/杂波——spec Out of Scope）；盘心白点 = 本船（own-centered）。
- 参数：量程默认 600 m（200..2000，步进 100），转速默认 45°/s（15..180，步进 15）；Q/E/Z/X 与面板滑条同路即时生效，面板逐帧镜像回读。
- 方位约定 worked examples（测试钉死）：北=0°、东=90°、南=180°、西=270°；3-4-5 三角距离；边界含判定。

## 岛屿映射表（Simulation 面板 → IslandSettings，IslandRebuild 纯函数）

| 面板值 | IslandSettings 字段 | 规则 |
|---|---|---|
| island count | `count` | 直传（钳 1..24；面板滑条 1..15） |
| island scale | `sizeRange.x/y` | × scale（直径 80–240 → 80s–240s） |
| island scale | `clusterRadius` | × scale（撒点盘同比放大，密度观感不变） |
| —（不动） | `maxHeight` / `resolution` / `seed` / 材质 / vertexColors | 原样复制（竖向尺度不变——约定缝只动横向三处；seed 恒 42 = 同一群岛等比缩放，确定性逐位可复现） |

Apply 语义：仅销毁重建 `Islands` 根（船/天气/相机/水面不动），新根仍摆 (0, 0, 180)。雷达两参数在滑条上即时生效，Apply 时再从滑条收权一次（权威对账）。测试钉死：基线 = M1 常数（5 岛/seed 42/80-240/260/45/96）、scale 2 全表、scale 1 恒等、钳制边界。

## 矢量箭头（VectorArrows，挂 M1 demo 船）

- 蓝 = 速度箭头：长度 ∝ 速度，**documented 比例因子 2 m/(m/s)**（5 m/s → 10 m）；杆 + 菱形头（无 Cone 原语，Cube 滚 45°），HDRP/Unlit HDR 亮色（NavigationLights 同款自发光观感）。
- 绿 = 航点箭头：定长 10 m 指活动航点（方位 = atan2(dx,dz)；恰在航点退化时回退艏向）。
- 端点数学全在纯函数 VectorArrowMath（速度零点 → 1.5 m 可读 stub；worked examples 测试钉死）。
- **idle 行为（documented，spec 授权自定）**：demo 未起跑/暂停 → 整树隐藏（`DemoRunning` 门控）；跑动中零速 → stub 箭头可见；TopDown 视图 → 隐藏（俯视读不出方向）；`V` 永久开关。

## 船模预览决策 + fps（story 8）

- **决策：render-texture 方案（spec 首选档），未启用类名圆盘兜底。** 远角舞台 (5000,0,5000)（岛群/两船全在预览相机 far=1200 m 外），专用相机 FOV 30° 取景距离随 LOA（2.2×LOA+8 m），RT 256²，模型 30°/s 慢旋（仅观感，无键位——档位切换才是控制，`P` 循环）。真机烟测两轮 0 exceptions，构建行 `ship-model preview stage built` 在案。
- **fps before/after overlays**（M1 真机窗口态，10 s 滑窗均值日志）：
  - 轮 1（预览底板双 Graphic 异常 → Simulation 面板死、RT 相机未建；雷达+矢量+相机 rig+Autonomous 在跑）：**84.7 → 119.0 fps**。
  - 轮 2（全量 overlays 含 RT 预览相机）：**65.6 → 105.6 fps**（稳态 ~100）。
  - 闸门 ≥30 fps 全程裕量 ≥2×；RT 预览相机开销 ≈15 fps 量级。无截图（编排方验收路径）。

## E1 review carry-ins（spec #85 指定）

- **EncounterDirector.PlaceShip 组合断言**：root-yaw = heading + 烘焙艏向的约定（此前 4 处仅注释背书）升为运行时自证——渲染艏（world）= rotation·(0,0,cos bowYaw) 必须等于航向单位向量，破约 `LogError`（玩家构建可见）。M2E 真机烟测零报错（Medium 180°/Large 0° 双船过）。
- **EncounterView TMP 标签去重**：CreateLabel / CreateScaleLabel 共享 `CreateWorldLabel(parent, name, text, color, xz, sizeDelta, scale)`（字体/朝向/负缩放镜像纪律单点维护）。
- （player-build body 去重：optional，未做——两条构建路径场景表不同，保持显式。）

## 其他改动

- `PerlinIslandGenerator.cs`（+ IslandSettings）**移入 `Runtime/Vessels/`**（Sango.Vessels asmdef）：IslandRebuild 纯核心与测试须同 assembly；文件 git mv、GUID 不变、零代码改动，消费者（Editor bootstrapper / 本批 SimulationPanel）不受影响。
- `WaypointFollower` 新增只读 `SpeedMps`（m_State.Speed 真值；矢量箭头消费；默认 0 初始化前）。
- `M1SceneBootstrapper`：岛体材质提局部变量（Apply 重建取同一材质）；新增 g2 段接线五组件；`smallFollower` 提升作用域。场景 YAML 复核：CameraRig/VectorArrows/RadarOverlay/SimulationPanel/AutonomousControlPanel 各 1 序列化引用。
- 新面板均复用 WeatherGUI idiom（运行时 UGUI、legacy Text、深色半透明、raycastTarget 纪律）。

## 偏离与说明

- spec "range rings at 1/2/1 range" → 满量程环并入盘面外缘亮圈 + 1/2 环（视觉等效，纹理一体生成省两 Image）。
- spec 雷达 "screen-space panel (circle) or world-space disc — implementer's choice" → screen-space（理由见上）。
- spec Autonomous "keyboard duplicate allowed" → `A`（QWERTY 左手区空闲键；与按钮键鼠同路）。
- spec "bridge/bow/chase 矢量可见" → TopDown 隐藏（documented idle 行为的一部分：正交俯视下世界空间箭头退化为点）。
- 键位规模超出"至多一键"先例（E1 同样超且被验收追认）：本机 CUA 鼠标不可靠为既定约束，键盘是唯一可编程精确输入——10 键全部有 hint 行与日志行。
- `Environment count / agents-per-env` 占位行照 plan 措辞落地为只读标注文本（非功能）。

## 验收修正轮（2026-09-24，编排方反馈两项 + 一项核查）

**Gate 复跑**：EditMode `-testResults /tmp/m2e2-tests-fix.xml` exit 0 **108 / 108 / 0**（TopDown 测试常数更新）；M1 / M2E 重建双 exit 0；M1 / M2E 播放器重建双 exit 0；M1 真机烟测 50 s **0 exceptions**（fps 稳态 37.4，高于 30 闸门；本轮机器负载高于此前 65-105 轮，如实记录）。

1. **[P2] TopDown 看不见船** → `CameraViews.TopDownHeightM 300→150`、`TopDownOrthoSizeM 150→70`（`CameraViewsTests.TopDown_OrthographicAboveShipNorthUp` 同步钉死数值）。理由：原参数下 12 m 小船仅 ~30 px 且 300 m 海雾光程洗掉对比度；新参数正交窗口 140 m 高，900 px 屏上小船 ~77 px、haze 光程减半，FollowsShip 恒画面正中——验收线"跟随船一眼可辨"。
2. **[cosmetic] Apply 按钮压住 "RADAR" 标题** → 根因诊断：**面板×面板列冲突，非面板内行推进漏项**——两画布同一 1920×1080 参考系，Simulation 面板（高 804 ref px）右列 x∈[1500,1900] 下探到 256-from-bottom，与右下角雷达盘（顶 392-from-bottom）纵向交叠，Apply 恰落在盘 "RADAR" 标题上。修复：RadarOverlay 根 `anchoredPosition (-20,20)→(-460,20)`（盘占 x∈[1176,1480]，与面板列 x≥1500 无横向交集 → 分辨率无关不重叠）；Apply 行内另加显式 16 px 上间隙（行进完整：预览 → +8 → Apply 44 → 54 推进）。
3. **[核查] chase 视角矢量不可辨** → 排查结论：**无 hide-condition bug**——可见条件仅 `V 开 && DemoRunning && 视图≠TopDown`，chase/bow 不在排除列。几何解释：chase 相机沿艏向望前，蓝色速度箭头（沿艏向指前）在该视角透视收缩近乎端点（几何必然）；绿色航点箭头（斜方位）承担 chase 可读性。已将杆 0.25→0.35 m、头底径 0.8→1.0 m（40 m 距离 ≈7 px 杆宽 + 发光头，桥楼/bow/chase 三视角更易读）。

## Orchestrator 视觉验收清单（本批交付态）

- **Bridge（默认）**：M1 既有机位不变，望岛群；左上天气面板、右上 SANGO SIMULATION 面板（4 滑条 + 3 class 按钮 + 深底预览窗内慢旋小渔船 + Apply + 占位行 + 三行 hint）、左下 AUTONOMOUS CONTROL（Start 按钮 + "G / A toggle"）、右下 RADAR 圆盘（双环 + 十字 + 外缘 + 扫描线旋转 + 琥珀 blip 随邮轮位置 + 盘心白点）。
- **C → Bow**：1 s 平滑过渡到小渔船艏部上空，随艏向 20° 指向东北，海面迎面而来。
- **C → Chase**：小渔船艉后上方跟拍；按 `A`（或 G/按钮）起航后船走清水走廊，相机逐帧跟随。
- **C → TopDown**：正交北向上俯视（150 m 高 / 半高 70 m），小渔船 ~77 px 恒在画面正中、随船平移（encounter 场同款海图方向）。
- **矢量（航行中）**：蓝色速度箭头自甲板沿艏向（长度随加减速伸缩）、绿色航点箭头指当前航点；暂停即消失（demo 未跑 → 隐藏）；TopDown 下不显示。
- **Apply**：改 Island count 滑条（如 12）→ 按 Enter/Apply → 原地重建 12 岛群岛（同 seed 同形状语言、同比布局），船仍在原位、天气不动，面板状态行 `applied: 12 islands x1.00`；雷达量程滑条拖动 → 圆盘上邮轮 blip 随量程收缩/展开。
- **预览**：class 按钮或 `P` 切档 → 预览窗换 Small/Medium/Large 模型慢旋，`LOA` 读数随档位。

## 渲染修复轮（2026-09-28，TopDown 花屏 + 全局变暗）

**根因（视觉核实）**：ortho TopDown 触发 HDRP 透视⇄正交投影切换，破坏管线渲染状态——TopDown 自身渲染成无纹理渐变，且访问过 TopDown 之后任何视图全部变暗。HDRP 17.3 不支持运行时投影模式切换无损恢复。

**修复（方案 A，已批准）**：投影切换彻底移除，四视图全透视。

- `CameraPose` 结构：`+FieldOfView`，`−Orthographic/OrthoSizeM`（正交语义字段全部删除）。
- TopDown = 船正上空 **160 m**、pitch **−80°**、yaw 0（北向上）、**FOV 35°**（地面足迹 ~100 m，12 m 小船 ~100+ px 恒在画面正中）。
- Bridge/Bow/Chase = FOV 60（BaseFovDeg）；桥楼位姿 + FOV 与 M1 场景相机逐位同源（场景 YAML 复核 `field of view: 60` 不变）——桥楼渲染零变化。
- `CameraRig`：`ApplyProjection` 整块删除；FOV 随位姿过渡插值（位置/旋转/FOV 三量 smoothstep，60⇄35 平滑变焦）；Awake/SnapNow 同步贴 FOV。全库无 `orthographic` 写入点残留（encounter 场景 pattern 顶视机位为天生正交、从不切换，不属本 rig）。
- 测试：`TopDown_OrthographicAboveShipNorthUp` → `TopDown_PerspectiveAboveShipNorthUp`（钉死 160 m / pitch −80 / yaw 0 / FOV 35 / FollowsShip）；Bridge/Bow 断言由 `Orthographic==false` 改为 `FieldOfView==60`。

**Gate 复跑**（/tmp/m2e2b-*.log）：EditMode `-testResults /tmp/m2e2b-tests.xml` exit 0 **108 / 108 / 0**；M1 场景重建 exit 0；M2E 场景重建 exit 0；M1 / M2E 播放器重建双 exit 0；M1 真机烟测 30 s **0 exceptions**（fps 76.9 → 109.0，gate ≥ 30）。场景 diff 复核：FOV 60 / orthographic 0 逐位不变，churn 为 bootstrapper 序列化重排。

**遗留给视觉验收**：C 键循环四视图全透视观感（TopDown 160 m 战术档）、TopDown⇄其余视图过渡（1 s 含 FOV 变焦）、切回桥楼后亮度不再变暗——本轮无截图能力，由编排方全周期目检。

## 诊断插桩轮（2026-09-28，全透视构建下 Bow/Chase/TopDown 仍渐变）

**症状（编排方真机目检）**：全透视构建（上轮修复后）Bridge 渲染完全正常，Bow/Chase/TopDown 三视图为平滑深蓝渐变（无水面纹理、无船、无岛）——同一相机同一会话内。船本身正常（泊位可见、雷达几何一致、RT 预览健康、followShip 场景 YAML 接线到 VesselSmall 根已人工核实）。

**插桩（常驻仪表，VesselBuoyancy 10 s 行同款低频模式）**：`CameraRig.LateUpdate` 5 s 节流一行——
`[Sango.M2E2] cam view={view} pos={cam.position} rot={eulerAngles} fov={fov} followPos={FollowPos()} followYaw={FollowYawDeg()}`
区分"位姿解算消费了垃圾输入"与"船根变换本身垃圾"的唯一现场证据；`view=` 随 C 键循环自动换值，下轮视图循环真机跑无需再改代码。

**Gate 复跑**（/tmp/m2e2c-*.log）：EditMode `-testResults /tmp/m2e2c-tests.xml` exit 0 **108 / 108 / 0**；M1 / M2E 场景重建双 exit 0；M1 / M2E 播放器重建双 exit 0；M1 真机烟测 30 s（无按键，恒 Bridge）**0 exceptions**。

**Bridge 态现场证据（Player.log 逐字，6 行同值）**：

```
[Sango.M2E2] cam view=Bridge pos=(0.00, 12.00, -40.00) rot=(359.5, 0.0, 0.0) fov=60.0 followPos=(14.00, -0.33, -6.00) followYaw=20.0
```

**判读**：相机位姿逐位正确（M1 桥楼 (0,12,−40)、pitch −0.52°、FOV 60）；**followPos 健康**——(14.00, −0.33, −6.00) 在水面高度（y≈−0.33，与 VesselMedium 场景 y−1.29 同量级），艏向 20°（NE，与证据图"随艏向 20° 指向东北"吻合），无 NaN / 无爆量 / 无深负 Y。结论：**三坏视图的输入端（船根变换）是干净的，故障不在 followPos**——位姿解算本身（bow/chase 偏移合成或 top-down 分支）或视图切换路径为下一嫌疑；待编排方驱动视图循环取 per-view 日志行定位。

## 渐变根因修复轮（2026-09-28，pitch 符号约定与 Unity 相反——三轮仪表递进定案）

**背景**：全透视构建下 Bow/Chase/TopDown 仍为平滑深蓝渐变（Bridge 完全正常、同一相机同会话）；编排方切 Chase 的位姿日志与手算逐厘米吻合 → 立案"位姿正确却错像素 ⇒ 必有别的相机在 rig 之后画屏"。

**仪表递进（相机普查 5 s 行常驻进 CameraRig.LateUpdate；本机 osascript keystroke 有辅助功能权限，本人可自行驱动 C 循环）**：

1. **全相机普查**：全场景恒 2 台——Main Camera（rig，rt=screen）+ PreviewCamera（出生即 targetTexture 绑定，(5000,9.4,4965.6) 远角舞台，far 1200）；雷达无相机、船 prefab `importCameras=false`。**"流氓相机盖屏"嫌疑排除**（Bridge 帧即可证：恰一台屏渲相机）。
2. **矩阵真相**（census 附 w2cBoat / camPosByMatrix / projFov）：矩阵每帧都由 transform 正确重导出（camPosByMatrix 逐tick吻合；ResetWorldToCameraMatrix/ResetProjectionMatrix 实验性修复无效）——"矩阵冻结"嫌疑排除。**但数值本身定罪**：Chase 稳态 `w2cBoat=(0.00, -29.53, -18.76)`——船在视轴下方 57.58° 而真值仅 4.4°（57.58 = 30.96° 真俯角 + 26.6）；x=0.00（yaw 全对）、斜距 34.99 精确守恒。
3. **根因**：**pitch 符号约定与 Unity 相反**。CameraViews 文档约定"PitchDeg 负 = 俯"，但 Unity `Quaternion.Euler` 是 **正 x = 俯**（Rx(+90)·(0,0,1) = (0,−1,0)）——负值直传 = **抬头**。TopDown −80 = 仰 80° 拍天顶（其 w2cBoat z=+157.57：船在相机**背后**——HDRP 物理天空 = 深蓝渐变本体）；Chase −26.6 仰拍、船 57.6° 出框下方；Bow −8 微仰。Bridge "正常"纯属侥幸：−0.52（仰）vs M1 LookRotation 的 +0.52（俯）仅差 1° 不可见。

**修复**：单一边界取反——`CameraRig.ApplyPose` 以 `Quaternion.Euler(-PitchDeg, YawDeg, 0)` 写入（rig 是 PitchDeg→引擎唯一消费者；解析器纯函数与"负 = 俯"文档约定原样保留，CameraViews/CameraRig 注释同步）。误诊副产品（矩阵 Reset 实验）已撤销，不留死代码。

**修复后 census 实证（修复轮烟测逐字，C 循环全四视图）**：

- Chase `rot=(27,20,0)` `w2cBoat=(0.00, -2.66, -34.88)` → **boatNDC (0.50, 0.43) 画面正中**（预告 0.42）。
- TopDown `rot=(80,0,0)` `w2cBoat=(0.00, -27.78, -157.57)` → in-front，**boatNDC (0.50, 0.22) 在框**（预告 0.22）。
- Bow `rot=(8,20,0)` 艏桅视角船体在下前方（根在框后属预期）；Bridge `rot=(1,0,0)` = M1 LookRotation 位姿逐位同源；过渡帧 fov 55.1（35⇄60 插值活着）；全程 **0 exceptions**。

**Gate 复跑**（/tmp/m2e2h-*.log）：EditMode `-testResults /tmp/m2e2h-tests.xml` exit 0 **108 / 108 / 0**；M1 / M2E 场景重建双 exit 0；M1 / M2E 播放器重建双 exit 0。

**说明**： census 行（含 w2cBoat/camPosByMatrix/projFov 三矩阵真值列）按编排方指示**常驻保留**（VesselBuoyancy 10 s 行同款低频仪表模式）。编排方全周期目检（C 四视图观感 + 亮度恒定）仍待其本机确认——本轮数学证据已闭环：渐变 = 仰角拍天，修复后船恒在框内。

## Rendering-fix + camera-census rounds (2026-09-24 → 09-28)

- Round 1 (all-perspective rig, ded965ec): removed ortho TopDown entirely —
  HDRP persp⇄ortho projection switching corrupted pipeline state (gradient
  frames, world dark after visiting TopDown).
- Round 2 (census + matrix resync, ffea2907 + uncommitted work completed by
  orchestrator): 5 s instrument logs per-camera census + rig matrix truth.
  Census verdicts: PreviewCamera exonerated (RT-bound only); matrices
  confirmed desync-capable after view switches — ApplyPose now calls
  ResetWorldToCameraMatrix/ResetProjectionMatrix every frame (zero-op when
  healthy).
- Round 3 finding (pixel forensics, orchestrator): Bow (4.5 m alt) renders
  bright and correct (liner ahead from the fishing-boat bow — screenshot);
  Chase (18 m) and TopDown (160 m) render the world but nearly UNLIT —
  brightened captures show liner/funnel/waves present. Darkness scales with
  camera height/steepness ⇒ per-camera exposure/lighting issue, root cause
  hunt handed to the next round. Gates for the committed state: 108/108,
  both scene rebuilds + both player builds exit 0.
