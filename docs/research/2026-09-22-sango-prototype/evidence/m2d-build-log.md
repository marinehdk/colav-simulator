# M2-D build log — night navigation lights + water reflection spike (spec #83)

2026-09-24 · branch `main`（local only, no push）· Unity 6000.3.24f1 + HDRP 17.3.0, Mac M3 arm64 batchmode.
前置：#80 / #81 / #82 已闭。**编目与 `pipelineVersion` 未动**（gate 2 日志无 "vessel assets built" 行 = EnsureBuilt 零开销跳过；git status：VesselAssetPipeline / VesselCatalog 零 diff）。

## Gates

| Gate | Command | Result |
|---|---|---|
| EditMode suite（红） | `-batchmode -runTests -testPlatform EditMode -testResults /tmp/m2d-tests-red.xml` | exit 2，**55 total / 47 pass / 8 fail** —— 11 条新测试中 8 条对 stub 红恒（5 锚点几何全红 + 3 条夜侧明灭红；3 条昼侧"灭灯"断言对恒灭 stub 空真，与 M2-B/C 护栏型同款纪律）；既有 44 条全绿 |
| EditMode suite（绿，Gate 1） | `-testResults /tmp/m2d-tests.xml` | exit 0，**55 total / 55 pass / 0 fail**（44 既有 + 11 新增） |
| Headless scene rebuild（Gate 2） | `-batchmode -quit -executeMethod Sango.Editor.M1SceneBootstrapper.Build` | **exit 0**；`[Sango.M1] M2-D navigation lights wired on both ships (on/off follows time-of-day; port RED / starboard GREEN / white masthead + stern)`；场景 YAML 含 2 × NavigationLights 组件 |
| Mono standalone player（Gate 3） | `pkill -f 'MacOS/sango'` → `-executeMethod Sango.Editor.M1VerifyCapture.BuildStandalonePlayer` | **exit 0**，`Succeeded size=182MB out=Builds/M1-Standalone.app` |
| EditMode suite（终轮复跑，成品代码态） | `-testResults /tmp/m2d-tests-final.xml` | exit 0，**55 / 55 / 0** |
| 真机播放器烟测 | `caffeinate -disu .../MacOS/sango -screen-fullscreen 0 -screen-width 1600 -screen-height 900`，25 s 后读 Player.log | 两船 rig 构建行 + `navigation lights OFF at h=12.0`（默认正午启动 = 昼态零光晕引导）；0 exceptions；VesselBuoyancy failed 0（无回归） |
| 夜间 perf（user story 7） | 窗口化编辑器 `-executeMethod Sango.Editor.M2DLightsProbe.RunPerf`（FpsProbe 1 s 窗 jsonl，各 12 s） | 正午 **162.5 fps** / 午夜 **141.1 fps**（Game view 1536×801，B3 Moderate；M0 闸 ≥30 fps @1440p 远远覆盖；夜灯相对成本 ≈ −13%） |

首轮绿前三处测试侧修正（非约定问题）：NUnit `Is.EqualTo(Vector3).Within(ε)` 走精确比较（epsilon 不逐分量生效），off-center worked example 改逐分量标量断言（0.3f·20f 一类二进制分数必须标量容差）。

## 纯核心（Sango.Vessels.NavigationLightsCore，纯静态、无引擎场景依赖、同输入逐位同输出）

- **缝 a `IsLightsOn(float timeOfDayHours)`**：仰角 = 60·cos(π(h−12)/12)，与 `WeatherController.ApplySun` 逐字同式（同一时刻语义，注释钉死"改公式须两处同步"）；**仰角 ≤ 0 开灯**（6h/18h 地平线恰 0° 时直射日光贡献 0 lux，归夜侧；COLREGs 日落点灯 → 17.5h 傍晚档仰角 +7.8° 仍灭灯）。
- **缝 b `DeriveAnchors(Bounds hullBounds)` → NavigationLightLayout{PortSidelight, StarboardSidelight, Masthead, SternLight}**：根局部空间（艏 +Z / 右舷 +X），舷灯 = ±X 极值 + 甲板高（center+0.5·ext.y）+ 艏侧 1/3 站位（+0.3·ext.z）；桅灯 = 中线 + 舱顶 + 艏部上方（+0.4·ext.z）；艉灯 = 中线 + 甲板高 + 艉端极值（−ext.z）。归一化分数偏移，零手工摆位，任意未来编目条目直接可用。

测试钉死的 worked examples（独立几何事实，非回声）：对称例 center(0,5,0) size(10,10,60) → port(−5,7.5,9) stbd(5,7.5,9) mast(0,10,12) stern(0,7.5,−30)；非对称例 center(2,3,−4) size(8,6,40) → 四点全表断言；细长/扁平极端 hull 侧性永不翻转。

## R2 spike —— 数值协议与裁定（真实 vs 兜底）

**协议**（M2DLightsProbe，batchmode play + `RenderPipeline.SubmitRenderRequest(RenderPipeline.StandardRequest)` 同步渲染主相机到 ARGBHalf RT → 逐像素回读；夜 h=0、B0 Calm；小渔船向相机一侧 10 m / 30 m 水面补丁 + 80 m 横向对照补丁；灯 ON vs OFF）。

**裁定判据（渲染前预先声明）**：近船补丁 (meanOn−meanOff) ≥ 3× 对照补丁漂移 且 相对提升 ≥ +50% → 真实路径可读；否则按 spec 落兜底。

**实测（灯 = 点光 300/600/200 lm，无拖尾）**：

| 补丁 | ON mean | OFF mean | Δ | 相对 |
|---|---|---|---|---|
| near1（10 m） | 0.00515 | 0.00236 | +0.00279 | +118% |
| near2（30 m） | 0.00467 | 0.00134 | +0.00332 | +247% |
| control（80 m 侧向） | 0.00497 | 0.00310 | +0.00187（=噪声底） | +60% |

- 近补丁 Δ 仅为噪声底的 **1.5× / 1.8×**（判据要求 ≥3×）→ **HDRP Water 对本地点光的镜面响应数值上存在（方向正确、近场更强），但在演示机位/曝光下不可读**——绝对亮度 ~0.003–0.005（线性 HDR），且跨帧对比被曝光适应漂移污染（渲染确定性已证：三次运行逐位相同；run 内 ON/OFF 的全局漂移由对照补丁如实捕捉）。
- **裁定：FALLBACK**（spec："if real reflections read poorly, take the fallback without ceremony"）。

**兜底实现与确认**（同探针复测）：每灯一条贴水面叠加混合（additive，SrcAlpha）长条 quad，逐帧长轴对准相机方向、从灯位向观者延伸（倒影几何），0.25 m 悬水；HDRP/Unlit 透明档（_SurfaceType=1 + _SURFACE_TYPE_TRANSPARENT、_BlendMode=2 + _BLEND_MODE_ADD、透明队列、ZWrite off）。昼夜明灭随 rig 整树开关（"opacity tied to night state" 的结构性实现）。

复测：拖尾补丁（取 Masthead.Streak 实时世界位姿）ON mean 0.0100 / max 0.0277，同帧开阔水面 0.0047–0.0051 → **同帧对比度 1.95×**（判据 ≥1.5），拖尾是全帧最亮特征 → `FALLBACK_STREAK_VISIBLE`。跨帧 changedFrac/ΔL 类指标全帧被曝光适应漂移污染（对照补丁 ±60%），证据一律以同帧对比度为准。

探针遗留为仓库内可复跑工具：`Sango/M2D/Run Water Reflection Spike`（batchmode 数值）、`Sango/M2D/Run Night Perf Probe`（窗口化 perf）。

## 灯参数（夜景一次调定，全部可 Inspector 调）

| 参数 | 值 | 依据 |
|---|---|---|
| 明灭阈值 | 仰角 ≤ 0 ⇔ h∈[0,6]∪[18,24]（滑条边界 0/24 = 深夜开灯） | 与 ApplySun 同式；COLREGs 日落点灯 |
| 舷灯点光 | range 50 m，300 lm，RED (1,0.12,0.08) / GREEN (0.15,1,0.25) | 场景尺度数十米；无阴影 |
| 桅灯点光 | range 80 m，600 lm，WHITE (1,0.98,0.92) | 最远可见灯 |
| 艉灯点光 | range 50 m，200 lm，WHITE | — |
| 灯片 | 交叉双面十字 quad ×2/灯，边长 = 0.03·LOA（Small ≈0.35 m / Medium ≈1.8 m 世界），HDRP/Unlit HDR ×12 nits | 水平全向可读，免 billboard |
| 拖尾 | 长 clamp(0.45·LOA+3, 4, 30) m × 宽 max(0.5, 4×灯片) m（Small 4.7×1.9 / Medium 12.6×7.2 m），×3 nits，α 0.55 additive，悬水 0.25 m | 同帧对比度实测 1.95× |
| 昼态 | rig 整树 SetActive(false)（renderer + light 全零参与） | 零光晕的结构性保证；Player.log 启动即 `OFF at h=12.0` |

实现注记：编目 prefab 根 transform 含烘焙统一缩放（局部单位 ≠ 米，M2-B 同坑二次确认：Small 局部 LOA 3.9 / Medium 21.3）——拖尾世界尺寸/悬水高度一律经 lossyScale 换算；锚点在根局部空间由父子关系自然继承缩放。

## 偏离与说明

- spec Testing Decisions 写"five world positions"、Implementation Decisions 与任务书说四灯 —— **按四灯实现**（port/stbd 舷灯 + 桅灯 + 艉灯；不设第五盏船艏白灯）。
- 点光保留（船体/甲板有真实响应）+ 兜底拖尾，两者叠加；R2 的"真实路径"分支代码不存在（探针数据不支持，不留半吊子实现）。
- spike 采集走 batchmode `SubmitRenderRequest`（任务书指定的 RT readback 数值路径的 HDRP 17.3 落地形态），非截图。
- 场景 rebuild 连带重生成 M1-GlobalVolumeProfile.asset（builder 既有幂等行为，与场景同 commit）。
- 无新键位：明灭只随既有 T 循环 / 时刻滑条；`demoHotkeysEnabled` 未触碰。

## 验收后修复轮（visual acceptance PASS with P2 — Medium 锚点镜像实锤与修复）

编排 agent 验收：小渔船夜灯/颜色/拖尾全 PASS；**P2 发现 Medium（ship-ocean-liner）桅灯落在艉部烟囱区、红灯异常内缩**。假设：−Z 原生艏被静默镜像。查证 **属实**：

- `VesselMedium.prefab` 根 `m_LocalRotation = (0,1,0,≈0)` = 180° yaw、均匀缩放 2.8195，模型子节点保持原生轴（`VesselAssetPipeline.BuildPrefabsAndCatalog`：`root.transform.rotation = Euler(0, spec.bowYawDeg, 0)`；k_Specs：Large 0 / **Medium 180** / Small 0——编目资产未持久化该列）。
- 首轮 rig 日志：Medium 桅灯 local z **+4.26** = 指向原生 +Z = 该船**原生艉** → 渲染在视觉艉部（烟囱区）；port 在原生 −X，而 bow = 原生 −Z 时船右舷 = 原生 −X → **红灯落在船右舷**。小渔船 yaw=0 不受影响（与其 PASS 一致）。

**修复**：`DeriveAnchors(Bounds, float bowYawDeg)`——锚点先按艏 +Z 舷框架计算，再按 native = R(−bowYawDeg)·(p−center)+center 映射回根局部原生轴（由 root 旋转 R(yaw)·native = corrected 反解；绕包围盒中心，180° 下 AABB 旋转不变 → 精确；编目 yaw 仅 {0,180}）。适配器新增 `bowYawDeg` 字段；bootstrapper 按 pipeline k_Specs 字面量注入（Small 0 / Medium 180；资产无此列，字面量同步注释钉在两处）。

| Gate | Command | Result |
|---|---|---|
| EditMode suite（红，3 条 180° 测试） | `-testResults /tmp/m2d2-tests-red.xml` | exit 2，**58 total / 55 pass / 3 fail**（全部新 180° 锚点测试对忽略 yaw 的 stub 红） |
| EditMode suite（绿，Gate 1''） | `/tmp/m2d2-tests.xml` | exit 0，**58 total / 58 pass / 0 fail**（55 + 3 新增：180° 对称例全表、船体侧性/艏艉事实、off-center 绕中心旋转例） |
| Headless scene rebuild（Gate 2''） | `-executeMethod Sango.Editor.M1SceneBootstrapper.Build`（带 `-quit`） | **exit 0**；"vessel assets built" 0 次（编目未动） |
| Mono player（Gate 3''） | `M1VerifyCapture.BuildStandalonePlayer` | **exit 0**，182MB |
| batchmode 探针复跑（修后锚点取证） | `M2DLightsProbe.RunSpike` | Medium：`bowYaw=180° port=(2.38,6.70,−3.19) stbd=(−2.38,6.70,−3.19) mast=(0,8.93,−4.26) stern=(0,6.70,10.64)` —— 桅灯转原生 −Z（视觉艏）半段、艉灯原生 +Z、红灯原生 +X（船左舷）✓；Small 锚点逐位不变（无回归）；夜灯 ON 状态行正常 |
| 真机播放器烟测 | 20 s Player.log | 修后 bowYaw 标注锚点两船各一行、昼态 OFF、0 exceptions |

**连带发现（不在本批修，移交 M2-E）**：`PlaceCatalogShip` 用 `rotation = Euler(0, heading, 0)` 绝对赋值，会**覆盖** prefab 根烘焙的 180°——场景里的 Medium 实际以"艉朝 heading"渲染（视觉艏向 = heading+180）。M2-C 的合成契约（rotation.y = psi 绝对）同样内含"根局部 = 艏向 +Z"假设。修法属管线/放置层（根烘焙改烘焙进网格，或放置/跟随层复合 yaw），须动 `pipelineVersion`——超出本批"编目与 pipelineVersion 不动"约束。锚点修复后，灯具相对**渲染出的船体**是 COLREGs 正确的（红灯在船左舷、桅灯在视觉艏上方），与演示机位观感一致；遭遇脚本批次取 Medium 朝向时须注意此偏移。

## Orchestrator visual acceptance（2026-09-24，核心 PASS + P2 已修待复核）

- **PASS（核心）**：夜景两船灯亮、小渔船颜色正确（B0 午夜放大核实 port 红 左 / starboard 绿 右）、静水面红/绿/白拖尾清晰、昼态零光晕、日志健康；证据已采集。
- **P2（已修复，待复核）**：Medium 桅灯在烟囱区/红灯内缩 → −Z 原生艏锚点镜像（见修复轮）。复核要点：放大 Medium 夜景——白桅灯应在**最前**（上层建筑前端之上）、白艉灯在最后、红灯在朝向行进方向的左手侧、拖尾从船体两舷与艏部拉向观者。

## 原验收清单（首轮，供复核对照）

- 夜景（T 循环第 3 档 h=0）：两船 port 红 / starboard 绿 / 白桅灯（艏部上方）/ 白艉灯，灯下水面有色拖尾拉向观者；Medium（135 m）灯组可辨。
- 昼景（h=12）：零光晕（rig 整树关闭）；T 循环切换 h=12→17.5→0 时 17.5 仍灭灯、0 亮灯（`[Sango.M2D] ... ON at h=0.0` 日志行可核对）。
- 拖尾应从船体向相机一侧延伸并随艏向/浮力姿态跟随；站桥楼机位 (0,12,−40) 小渔船拖尾最明显（G 航行中应随船移动）。
