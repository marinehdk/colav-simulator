# M4 Spike Notes — Water Decal 艏波 + 尾迹（HDRP 17.3）

日期：2026-09-28。工程：sango/（Unity 6000.3.24f1 + HDRP 17.3，包在
`Library/PackageCache/com.unity.render-pipelines.high-definition@700710090fa9/`，下称 PKG）。
范围：证明内置 Water Decal 路线能做跟随船只的艏波变形+尾迹泡沫；视觉验收（不跑播放器/不截图）归编排者。

## 1. API 能力核验（17.3 实际暴露面 vs 17.6 文档差异）

结论：**deformation + foam 在 17.3 完整可用，且 17.6 文档的 Bow Wave 模板在 17.3 以
"样例 ShaderGraph + 内置 SDF 函数"形态存在**。逐条源码证据：

- `PKG/Runtime/Water/WaterDecal/WaterDecal.cs`
  - `PassType { Deformation, Foam, SimulationMask, LargeCurrent, RipplesCurrent }` 是 **internal** 枚举
    （WaterDecal.cs:14-21）——pass 类型不暴露在组件上，由材质 ShaderGraph 的
    WaterDecalData（affectsDeformation/affectsFoam/... 复选框）决定生成哪些 pass
    （`PKG/Editor/Material/Water/ShaderGraph/WaterDecalSubTarget.cs:90-102`）。
  - 公开字段：`regionSize`（Vector2，米）、`amplitude`、`surfaceFoamDimmer`、`deepFoamDimmer`、
    `resolution`、`updateMode`、`material`、`SetPropertyBlock`（MPB 会传进 atlas 渲染，
    HDRenderPipeline.WaterSystem.Decals.cs:308——但 atlas 只在 updateCount 变化时重画，
    OnLoad 模式下 MPB 改值不生效）。
  - 材质合法性：编辑器下 `material.GetTag("ShaderGraphTargetId") == "WaterDecalSubTarget"`
    （WaterDecal.cs:104-111）。
- `PKG/Runtime/Water/WaterSurface/WaterSurface.Deformation.cs:14,20`：`deformation`（bool，默认 false）
  + `deformationRes`（默认 Resolution512）。`WaterSurface.Foam.cs:14,16`：`foam`（bool，默认 false）
  + `foamResolution`。**任一 false 时对应 decal pass 直接不可见**
  （HDRenderPipeline.WaterSystem.Decals.cs:198-199 `visible |= waterSurfaces[i].deformation && affectDeformation`）。
- `PKG/Runtime/Water/WaterSurface/WaterSurface.cs:568-621`：`decalRegionSize`（默认 200×200）+
  `decalRegionAnchor`（Transform，非空即以锚点为 decal 区域中心）+ `GetDecalRegion`。
  跟随船只 = anchor 指向船 Transform，无需自写 offset 脚本；区域中心按 foam 分辨率步长取整防闪
  （WaterSurface.cs:613-615）。
- **Bow Wave**：`PKG/Runtime/Water/Shaders/WaterDecalUtilities.hlsl:121-146`
  `EvaluateBowWaveAmplitude_float(uv, elevation, out amplitude)`——抛物线 V 形 SDF（IQ sdParabola）
  + 尾部三次衰减。17.6 文档的 "Bow Wave 模板" 本体就是它；17.3 已随包提供，且样例图
  `PKG/Samples~/WaterSamples/Materials/CurrentWithSplines/Sample Water Decal.shadergraph`
  用 CustomFunctionNode（FunctionName=EvaluateBowWaveAmplitude，源=WaterDecalUtilities.hlsl 的
  资产 GUID）调它。本 spike 的材质即此图拷贝改造（见 §2）。
- 17.6 文档差异：未在 17.3 包内发现现成 "Bow Wave" 预制模板/菜单项；能力（SDF 函数+样例图）
  等价，工艺上要自己拷样例图。17.3 额外有 `Sample Water Decal` 图里的 Type 下拉
  （Sphere/Box/Bow Wave/Shore Wave/Texture，枚举 `_TYPE`，Bow Wave = 索引 2 / keyword
  `_TYPE_BOW_WAVE`）。

## 2. 材质来源与改造方式（对任务前提的两处修正）

任务前提点名 "Cave/SG_DecalDeformation.mat（变形）" 与 "Pool/Decal Foam.mat（泡沫）"——
**两个都不是 WaterDecal 材质**，均已核实：

- Cave/SG_DecalDeformation.shadergraph 是旧格式 **DecalSubTarget**（mesh decal）图；
  Cave.unity 里由 DecalProjector 使用（场景内 m_Script f19d9143… 块，字段 m_DrawDistance/m_Size）。
  挂到 WaterDecal 上过不了 `IsValidMaterial()` 的 WaterDecalSubTarget 校验。
- Pool/Decal Foam.mat 的 shader 是 HDRP 常规 decal（guid 1d64af84…，`_Unity_Identify_HDRP_Decal: 1`），
  同样不是 WaterDecalSubTarget。

实际采用的真 WaterDecal 样例（同样在 WaterSamples/Materials/ 下，符合"拷样例改造"的意图）：

- 源：`CurrentWithSplines/Sample Water Decal.shadergraph`（GUID 54ea0dff6767fe540b7b0eb2bccb01e2）
  + `Shader Graphs_Sample Water Decal.mat`（GUID 7ac1471bc6b69f0499dab746b6c429c8）。
- 拷贝（连 .meta，GUID 保留 → 图内 CustomFunction 的 hlsl 资产引用与 mat→shader 引用原样有效）：
  - `Assets/Art/WaterDecals/BowWaveDecal.shadergraph`（原名 Sample Water Decal.shadergraph）
  - `Assets/Art/WaterDecals/M4_BowWave.mat`（艏波：`_TYPE: 2` + keyword `_TYPE_BOW_WAVE`；
    floats `_AffectDeformation: 1, _AffectFoam: 1, _AffectLargeCurrent: 0`；keywords
    `[_AFFECTS_DEFORMATION, _AFFECTS_FOAM, _TYPE_BOW_WAVE]`）
  - `Assets/Art/WaterDecals/M4_WakeFoam.mat`（尾迹：同图，`_AffectDeformation: 0` 关变形，
    只留 foam pass；新 GUID ce8cf741a0634bafbb8d74bab788d6b9）
- 注意坑：样例 mat 的隐藏 float `_AffectFoam: 0` 会把 foam pass 整个关掉
  （IsAffectingProperty 读 material.GetFloat，HDRenderPipeline.WaterSystem.Decals.cs:129-135）——
  两个新 mat 都显式置 1。
- 尾迹泡沫的强度驱动不走材质：组件字段 `surfaceFoamDimmer` 就是 per-decal 泡沫乘子
  （WaterDecal.shader FoamDecal pass：`atlas.yz × dimmers × _DeltaTime`），适配器每帧写它即可，
  无需 MPB、无需 Realtime updateMode。

## 3. 参数表（提交值）

| 参数 | 值 | 出处/理由 |
|---|---|---|
| WaterDecal bow regionSize | 12×12 m | 12 m 小船 LOA 量级；V 尖顶（uv.y≈0.1）落在艏柱：局部 z = (6 − 0.4·12)/根缩放 ≈ 0.387（根烘焙缩放 ≈3.10） |
| WaterDecal bow amplitude | 0.4 m（全强时） | 小船艏波抬升量级；组件 amplitude 是 graph 输出的米制乘子（WaterDecal.shader:106 `atlas × data.x`，data.x = amplitude×scale.y） |
| WaterDecal wake regionSize | 14×28 m | V 尖顶在船中，双臂外扩向艉，泡沫缓冲持久化拖出尾迹 |
| WaterDecal wake amplitude | 0 | 尾迹只出泡沫；材质侧 `_AffectDeformation: 0` 双保险 |
| wake deepFoamDimmer | 0.6 | 深水泡沫少量（表层为主） |
| decal resolution / updateMode | 256×256 / OnLoad | AddComponent 后 Reset() 把 128 覆写为 256（WaterDecal.cs:134-146）；V 形静态，OnLoad 只画一次 atlas |
| WaterSurface.deformation / foam | true / true | 两个总开关，任一 false 对应 pass 不可见 |
| WaterSurface.decalRegionSize | 64×64 m | 锚船；512 res 下 ≈8 px/m（默认 200 m 只 2.56 px/m，12 m 船的 V 会被抹平） |
| WaterSurface.deformationRes / foamResolution | 512 / 512（默认） | 见 §5 性能 |
| 速度门限 | 0.5 m/s；全强 5 m/s | 静止/锢泊禁用；巡航 5 m/s（WaypointFollower 默认档）达到全强 |

朝向约定（推导自 WaterDecal.shader GetDecalVaryings + EvaluateBowWaveAmplitude）：
图 UV.y=0 边是 V 尖顶侧 = decal 局部 −Z ⇒ decal 子物体 localRotation = Euler(0,180,0)
（decal −Z = 船 +Z 艏）。scaleMode=ScaleInvariant（regionSize 即米，不被 prefab 根烘焙缩放放大）。

## 4. 代码分层（速度门限）

- 纯核心 `Assets/Scripts/Runtime/Vessels/WaterDecalSpeedGate.cs`（Sango.Vessels asmdef，无引擎写）：
  `ShouldEnableDecals(speed, threshold)`（≥ 含等号启用）+ `WakeFoamIntensity(speed, threshold, full)`
  （线性爬坡+钳 1；span≤0 退化阶跃，不除零）。
- 适配器 `Assets/Scripts/Runtime/BoatWaterDecals.cs`（Assembly-CSharp，HDRP 引用在场）：
  每帧 `follower.SpeedMps` → `ApplySpeed` 写两块 decal 的 `enabled`、bow `amplitude`、
  wake `surfaceFoamDimmer`。公开 `ApplySpeed` = EditMode 可测缝（StepOnce 先例）。
- 场景接线 `Assets/Scripts/Editor/M1SceneBootstrapper.cs` `AttachWaterDecals`：材质缺失只 LogError
  跳过（不阻断 batch 重建）；bootstrapper 代码路径重建场景（勿手改 .unity）。

## 5. 性能注意（deformationRes 档位）

- deformation/foam 各开一张 512×512 R16/RG16 RT + 泡沫模拟 CS（reproject/attenuate 每帧）。
  deformationRes/foamResolution 每升一档（512→1024→2048）显存 ×4、reproject 代价 ×4；
  区域 64 m + 512 档对小船足够，升档收益有限。
- decal atlas 每 decal 每 pass 占 `resolution` 一格（256²×2 decal×2 pass 可忽略）；
  updateMode=Realtime 才会每帧重画 atlas——本 spike 全 OnLoad，速度驱动只改组件字段，零 atlas 开销。
- decalRegionAnchor 跟船走：区域步长 = maxRegion/foamResolution = 0.125 m，量化不闪。
- 泡沫缓冲的持久化（foamPersistenceMultiplier，默认 0.5）决定尾迹拖尾时长——M4 调观感的第一个旋钮。

## 6. 已知限制（spike 范围内接受）

- 尾迹泡沫复用 Bow Wave 的 V 形泡沫图案（graph 的 foam 输出=V 形幅度）；真正的湍流尾迹
  （螺旋桨紊流、开尔文波系）需专门图或 CustomFunction，留 M4。
- 艏波幅度静态 V，不随波高/傅汝德数自适应；抬升直接叠加在水面上（无排水量耦合）。
- Medium/Large 船未接 decal（spike 只做 Small demo 船）。
- graph 的 Time 驱动噪声分支（Shore Wave/Texture 模式）在 OnLoad 下不动画；当前 Bow Wave 路径无 Time 依赖，不受影响。
- EditMode 测试经反射驱动 Assembly-CSharp 适配器（asmdef 不能引用预定义程序集，WeatherFogOverrideTests 先例）。

## 7. M4 正式化清单（P0 工艺承接）

1. P0 工艺（现有管线）如何承接：船波 decal 由 M1SceneBootstrapper 场景代码路径生成
   （本 spike 已打通）；正式化时把 `AttachWaterDecals` 提为编目驱动（按 VesselClass 查
   LOA/船宽定 regionSize/amplitude 表），多船接线。
2. 尾迹图升级：V 形 → 湍流尾迹（沿艉流条的噪声条带 + 螺旋桨泡沫点），可再拷
   Shore Wave 分支或自写 CustomFunction 进 WaterDecalUtilities 模式的 hlsl。
3. 强度曲线：线性爬坡 → 按 Froude 数/波高查表；`foamPersistenceMultiplier` 与天气
   （Beaufort 档）联动。
4. 参数暴露进 Simulation 面板（amplitude/regionSize 实机调参回填，beaufort-water-mapping.md 模式）。
5. decalRegionSize 自适应（多船时取包围盒或按船分级）；deformationRes 档位进质量设置。
6. 视觉验收未做（本 spike 不跑播放器）：apex 对位、V 张角、泡沫拖尾长度需实机核对后回填 §3 表。

## 8. 验证记录

- 场景重建：`Unity -batchmode -quit -projectPath sango -executeMethod Sango.Editor.M1SceneBootstrapper.Build`
  exit=0；日志 `[Sango.M4] water decals wired: …`（sango/tmp/w1b-scene.log:498）；
  场景 YAML 核对：两块 WaterDecal（regionSize 12×12 amp 0.4 / 14×28 amp 0）、
  BoatWaterDecals（threshold 0.5 / full 5）、WaterSurface deformation/foam=1、
  decalRegionAnchor 指向 Small 船 transform。
- EditMode 全量：`Unity -batchmode -projectPath sango -runTests -testPlatform EditMode
  -testResults tmp/w1b-selftest.xml`：**133/133 passed, 0 failed**（含新增
  WaterDecalSpeedGateTests 8 例）。
