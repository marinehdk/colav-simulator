# DT 仿真环境与船舶真实性：HDRP、论文和替代实现的一手资料

日期：2026-10-09  
范围：DT 环境、船体与航行过程的视觉真实性；不评价避碰算法。  
当前项目版本：[Unity 6000.3 / HDRP 17.3.0](</Users/marine/Code/Colav-Simulator/sango/Library/PackageCache/com.unity.render-pipelines.high-definition@700710090fa9/package.json:4>)。本报告只写研究结论，没有修改生产代码。

## 结论

当前 HDRP 足够支持第一阶段的可信视觉效果：海面、近船艏波、船尾泡沫、喷溅、天空、大气、云和远景地形都可以继续留在 Unity/HDRP 内完成。HDRP 水系统已经提供两条不同路径：

1. 全海面的风驱动 simulation foam；
2. 跟随 GameObject 的 Water Decal 局部泡沫，以及可选的水面变形。

因此，图 1–3 的“只有白色点/短白条”不能归因于 HDRP 完全做不到尾流。更可能是当前只注入了短局部 decal，并且没有持续的世界空间历史尾迹；HDRP 原生 Water Decal 也不是船体 CFD 或水动力尾流求解器。官方文档明确把船后泡沫定义为 local foam / Water Decal，把水模拟定义为只接受风和流速等简化输入的数学构造，而非完整流体动力学。[HDRP foam](https://docs.unity.cn/Packages/com.unity.render-pipelines.high-definition@17.3/manual/water-foam-in-the-water-system.html)、[HDRP water simulation](https://docs.unity.cn/Packages/com.unity.render-pipelines.high-definition@17.3/manual/water-water-system-simulation.html)

图 4 的天空首先应按配置故障处理，而不是先换引擎。M6 配置把 `skyType` 写成 Physically Based Sky 的值 `4`，但对应的 `m_OverrideState` 是 `0`；同一 profile 的 Physically Based Sky 参数也没有启用 override。HDRP 默认 Volume Profile 则把 `skyType=1`（HDRI Sky）和 HDRI exposure `11` 设为有效 override。运行时云代码会打开 VolumetricClouds 的 override，却没有打开 VisualEnvironment 的 `skyType`。这会产生“动态云 + 默认静态 HDRI 天空 + 100000 lux 方向光”的混合结果，和截图中天空发假、曝光不协调的现象一致。[M6 profile](</Users/marine/Code/Colav-Simulator/sango/Assets/Settings/M6-GlobalVolumeProfile.asset:616>)、[默认 VisualEnvironment](</Users/marine/Code/Colav-Simulator/sango/Assets/HDRPDefaultResources/DefaultSettingsVolumeProfile.asset:1388>)、[默认 HDRI](</Users/marine/Code/Colav-Simulator/sango/Assets/HDRPDefaultResources/DefaultSettingsVolumeProfile.asset:1128>)、[运行时云 override](</Users/marine/Code/Colav-Simulator/sango/Assets/Scripts/Runtime/WeatherController.cs:318>)。

Unity 17.3 官方要求 Physically Based Sky override 存在、Visual Environment 的 Sky Type 指向 Physically Based Sky、方向光启用 Affect Physically Based Sky；官方示例给出的物理日光强度是 130000 lux。[Create a physically based sky](https://docs.unity.cn/Packages/com.unity.render-pipelines.high-definition@17.3/manual/create-a-physically-based-sky.html) 云还需要同时在 HDRP Asset 和 Camera Frame Settings 中开启，并由 Volume override 控制。[Create realistic clouds](https://docs.unity.cn/Packages/com.unity.render-pipelines.high-definition@17.3/manual/create-realistic-clouds-volumetric-clouds.html)

建议顺序是：先修正天空/大气配置并验收远景地形，再用 HDRP 原生 Water Decal + VFX Graph 完成近船艏艉效果，最后再决定是否需要 Crest 的动态波面模拟。没有证据表明现在必须迁移 UE5 或购买第三方水系统。

## 1. HDRP 17.3 能做什么、不能做什么

### 1.1 水面、波浪和泡沫

项目内 17.3 文档把 Ocean/Sea/Lake 定义为三频段水面：两个 swell 频段和一个 ripple 频段；风和 current 影响水面位移，脚本可查询水面位置和 current。水系统明确把这些输入称为 simplified inputs，官方 limitations 中没有船舶 wake solver、船体压力场或螺旋桨流场。[本地 capabilities 文档](</Users/marine/Code/Colav-Simulator/sango/Library/PackageCache/com.unity.render-pipelines.high-definition@700710090fa9/Documentation~/water-capabilities-of-the-water-system.md:2>)、[本地 simulation 文档](</Users/marine/Code/Colav-Simulator/sango/Library/PackageCache/com.unity.render-pipelines.high-definition@700710090fa9/Documentation~/water-water-system-simulation.md:1>)

官方 17.3 foam 文档区分：simulation foam 用于整片海面的风浪白沫；local foam 用于移动物体后的泡沫轨迹。[Introduction to foam](https://docs.unity.cn/Packages/com.unity.render-pipelines.high-definition@17.3/manual/introduction-to-foam.html) 的操作页明确要求在 Water Surface 打开 Foam，再把 Water Decal 作为移动 GameObject 的子节点，移动 GameObject 后即可形成 trail。[Create local foam near a GameObject](https://docs.unity.cn/Packages/com.unity.render-pipelines.high-definition@17.3/manual/create-local-foam-in-the-wake-of-a-gameobject.html)

这条路径能解决“水面上有连续泡沫”，但它仍是视觉输入。泡沫衰减在 17.3 shader 中是指数衰减：`exp(-_DeltaTime * _FoamPersistenceMultiplier * 0.5)`。[WaterDecal.shader](</Users/marine/Code/Colav-Simulator/sango/Library/PackageCache/com.unity.render-pipelines.high-definition@700710090fa9/Runtime/Water/Shaders/WaterDecal.shader:234>)；`_FoamPersistenceMultiplier` 由 `1 / Lerp(0.05, 1, foamPersistenceMultiplier)` 得到。[WaterSystem.cs](</Users/marine/Code/Colav-Simulator/sango/Library/PackageCache/com.unity.render-pipelines.high-definition@700710090fa9/Runtime/Water/HDRenderPipeline.WaterSystem.cs:305>) 即使 persistence 取最大值，half-life 约为 1.386 s；项目运行时 ownship 目前设为 `0.75`。[TwinSessionDriver.cs](</Users/marine/Code/Colav-Simulator/sango/Assets/Scripts/Runtime/TwinSessionDriver.cs:575>) 这解释了为什么单纯把 persistence 调大仍然不能生成几十秒、几十米的远尾迹。需要持续把带年龄的历史轨迹重新注入世界空间泡沫，或引入动态波面模拟。

### 1.2 艏波和水面变形

HDRP 17.3 Water Decal 模板有 Bow Wave 类型：`Bow Wave Elevation` 控制最大波高；把 decal 设为船体子节点即可随船艏移动。官方也提醒 decal 只能在 Water Surface 的 deformation area 内移动，保持大范围航行需要脚本更新 `deformationAreaOffset`。[Deform a water surface](https://docs.unity.cn/Packages/com.unity.render-pipelines.high-definition@17.3/manual/water-deform-a-water-surface.html)

这正适合当前第一阶段：用 bow decal 形成两侧艏波/水线抬升，用接触入水速度和对水速度调节高度、泡沫和喷溅强度。它不能证明压力、排水量、阻力或纵向波系是真实的；MASS/导航物理仍应保持唯一后端权威。

### 1.3 喷溅、波面采样和云

HDRP VFX Graph 可采样单个全局绑定水面的位置、水高、法线和 current，因此适合做艏部喷溅、艉部螺旋桨水花，并让粒子贴合波面；官方同时说明一个 VFX Graph 同时只能绑定一个水面，且必须显式匹配 deformation/current/mask 设置。[VFX Graph water interaction](https://docs.unity.cn/Packages/com.unity.render-pipelines.high-definition@17.3/manual/water-vfx-interaction.html)

云的正确组合是：Physically Based Sky 负责大气/天空；Volumetric Clouds 负责近处可受雾和光照影响的体积云；远处云层可用 Cloud Layer。HDRP 官方明确支持两者叠加，并说明体积云默认在实时 Reflection Probe 中关闭或低分辨率渲染，因此不能只看水面反射判断云是否配置正确。[Understand clouds](https://docs.unity.cn/Packages/com.unity.render-pipelines.high-definition@17.3/manual/understand-clouds.html)

## 2. 当前场景配置的具体诊断

### 2.1 天空

M6 profile 的关键值如下：

| 项目 | 当前文件证据 | 解释 |
|---|---|---|
| `VisualEnvironment.skyType` | `m_Value: 4`，但 `m_OverrideState: 0`，见 [M6 profile](</Users/marine/Code/Colav-Simulator/sango/Assets/Settings/M6-GlobalVolumeProfile.asset:616>) | 期望值是 Physically Based Sky，但 Volume 栈不会采用该 override |
| `PhysicallyBasedSky` | `active: 1`，但主要属性的 override 仍为 `0`，见 [M6 profile](</Users/marine/Code/Colav-Simulator/sango/Assets/Settings/M6-GlobalVolumeProfile.asset:656>) | 组件存在不代表被当前 Volume 栈采用 |
| 默认 sky | `skyType=1`、override 为 `1`，HDRI exposure `11`，见 [默认 profile](</Users/marine/Code/Colav-Simulator/sango/Assets/HDRPDefaultResources/DefaultSettingsVolumeProfile.asset:1128>) | 很可能是截图中的静态 HDRI 来源 |
| 运行时环境 | WeatherController 对云调用 `SetAllOverridesTo(true)`，但没有同步打开 `VisualEnvironment.skyType`，见 [WeatherController](</Users/marine/Code/Colav-Simulator/sango/Assets/Scripts/Runtime/WeatherController.cs:328>) | 云和天空可能来自不同的 Volume 设定 |
| 方向光 | M6 bootstrapper 创建 100000 lux 方向光，见 [M6 bootstrapper](</Users/marine/Code/Colav-Simulator/sango/Assets/Scripts/Editor/M6StraitSceneBootstrapper.cs:189>) | 方向光强度本身合理，但必须配合 PBS 的 Affect Physically Based Sky |

最小修复验证应在运行时检查最终 `volumeStack`，而不是只检查 profile 文件：`VisualEnvironment.skyType == SkyType.PhysicallyBased`、PBS 组件 active、`Affect Physically Based Sky=true`、Camera Frame Settings 的 Volumetric Clouds 开启。若这四项成立后天空仍假，再调 aerosol、exposure、sun elevation、cloud preset 和 temporal accumulation。

### 2.2 陆地和远景

M6 不是没有陆地数据：场景构建器注释描述 29 块真实地形 tile，且构建时以水深和航线采样做 gate。[M6StraitSceneBootstrapper.cs](</Users/marine/Code/Colav-Simulator/sango/Assets/Scripts/Editor/M6StraitSceneBootstrapper.cs:15>) 因此当前“看不见陆地”应先分为三类验证：

1. 相机当前朝向是否真的看到 tile，而不是开放海面方向；
2. 地形材质、远近 LOD 和大气雾是否在地平线处把地形压成同色；
3. sky/曝光修复后，地形是否仍缺少岸线植被、岩体和近景细节。

不能从论文中的静态海岛截图推断项目地形已经达到真实地貌；需要固定相机方位、近景/中景/远景三组截图再验收。

## 3. 论文证据

### 3.1 Aeolus Ocean

来源：[本地 PDF](</Users/marine/Documents/Paper/Aeolus Ocean - A simulation environment for the autonomous COLREG-compliant navigation of Unmanned Surface Vehicles using Deep Reinforcement Learning and Maritime Object Detection.pdf>)、[arXiv](https://arxiv.org/abs/2307.06688)、[作者仓库](https://github.com/aavek/Aeolus-Ocean)。作者仓库是 BSD-3-Clause，但 README 明确当前只发布 binary；不能把它当作可直接移植的 Unity 源码。[README](https://github.com/aavek/Aeolus-Ocean/blob/main/README.md#description)

| PDF 页 | 原文证据 | 对当前项目的可用启示与边界 |
|---|---|---|
| 2–4 | Tessendorf/Horvath 路线；PM、JONSWAP、TMA、方向扩展、有限水深色散 | 可用于海况参数和波谱校准；不能仅凭 HDRP sliders 声称与某个谱数值一致 |
| 8 | HDRP；多层同心 LOD 海面；GPU HLSL compute；反射、折射、次表面散射、Fresnel；custom crest foam；VFX Graph 天气 | 说明 HDRP 能承载天空、海面和天气的工程组合。论文把波峰泡沫称为 custom shader，没有给出船尾 CFD/wake solver |
| 9 | 合成图像变化：Beaufort 1、3、6.5、9，Dawn/Midday/Evening，5/20/50 倍船长距离 | 可作为画面验收矩阵，不应把检测训练背景等同于航行物理真实性 |
| 10–12 | Perlin 地形；按水线拆分三角形；浮力、流体阻力、摩擦、风力/current；推进点施力；Unity PhysX 6-DOF | 可借鉴水线受力和 6-DOF 研究方向。项目当前已确认后端 4-DOF，因此不应在 Unity 再建第二个导航物理权威 |
| 19–20 | RTX 2080 Ti 场景最低约 30 FPS；作者承认大浪/暴风海况对方法的有效范围仍不确定 | 论文自己没有把视觉表现升格为海况或动力学验证 |

原文和 README 都没有可验证的真实船尾尾流模型。README 反而明确说明 foam 使用 simplified particle system，在大浪中可能不好看；因此 Aeolus 可以借鉴天空、天气、波谱和场景组合，不能作为当前尾流必须照搬的“正确答案”。

### 3.2 MMUSV-Sim

来源：[本地 PDF](</Users/marine/Documents/Paper/MMUSV-Sim- A Perception-Oriented Simulation and Data-Generation Platform for Multi-USV Cooperative Perception.pdf>)、[arXiv 2608.14207](https://arxiv.org/abs/2608.14207)。

| PDF 页 | 原文证据 | 对当前项目的可用启示与边界 |
|---|---|---|
| 1–3 | UE5 + Project AirSim；岛屿、港口、开海；天气/时刻/波浪；30+ 船舶资产；Fig. 3 展示日时和云/雾/雨/雪 | 可作为环境内容和感知数据管线的参考；它不是 Unity HDRP 的插件方案 |
| 4 | spline 路线 + 合成 heave/roll/pitch；原文明确写明模型优先 perception-relevant sensor-attitude variation over hydrodynamic fidelity | 这直接说明该平台不适合拿来证明船体水动力、艏艉波或尾流真实性 |
| 5 | W0–W3 几何波高 0.5–3.5 m，对应 heave/roll/pitch RMS；同时验证标注投影一致性 | 可借鉴“波浪档位必须用姿态 RMS 验证”的测试方式，不是 wake 验证 |
| 6 | 感知检测 AP、时延和 pose noise 评估 | 属于感知系统验证，和当前 DT 画面真实性是不同验收层 |

两篇论文的共同边界：画面/传感器多样性、海况参数和姿态扰动可以证明“场景可控”，不能证明船舶水面相互作用已经物理正确。用户要求的顺序“先环境/船舶/航行过程，再避碰和可视化决策”是合理的，但视觉验收和物理验收仍应分开。

## 4. 用户附 GIF 的来源核对

附件 `/Users/marine/Desktop/Desktop/截屏/220569086-4b1245b7-66e0-43ad-90be-f1f9d15445ec.gif` 与 Aeolus README 中的 “DEV tracking another target vessel during rain” GIF 是同一文件：两者文件名相同，下载作者链接后 MD5 都是 `ea594b2c0110d79e11310d5f8a07b9c3`。[Aeolus README GIF 行](https://github.com/aavek/Aeolus-Ocean/blob/main/README.md#during-the-simulation)、[直接 GIF](https://user-images.githubusercontent.com/93454699/220569086-4b1245b7-66e0-43ad-90be-f1f9d15445ec.gif)

该 GIF 是雨天目标跟踪视觉参考，不是船艉 wake 物理基准；同一 README 的 limitations 说明 foam 使用简化粒子系统且大浪下可能不好看。

## 5. Crest 作为条件性替代方案

Crest 官方文档把“环境波”和“动态波”分开：环境波可以用 FFT、Gerstner 和 Pierson–Moskowitz spectrum；动态波是多分辨率模拟，会把对象 interaction 加到最终水面。船体通过多个 `SphereWaterInteraction` 近似，官方船舶章节明确说该组件用于添加 wakes。[Crest waves](https://crest.readthedocs.io/en/latest/user/waves.html)、[Crest watercraft](https://crest.readthedocs.io/en/latest/user/watercraft.html)

Crest 当前官方文档要求 Unity 2022.3.62f3 或更高、HDRP 至少 10.10；项目 Unity 6000.3 在版本范围内。[Crest initial setup](https://crest.readthedocs.io/en/latest/user/initial-setup.html) 但需要区分许可证和发行渠道：Crest GitHub 仓库是 MIT 且 README 明确仓库目标是 Built-in Renderer；HDRP/URP 发行版链接到 Unity Asset Store，Crest Water 5 是单独产品。[Crest GitHub README](https://github.com/wave-harmonic/crest#crest-water-4)、[Crest Water 5 Asset Store](https://assetstore.unity.com/packages/tools/particles-effects/crest-water-5-oceans-rivers-lakes-268614)

Crest 的价值是“若 HDRP 原生视觉注入仍达不到长尾迹和动态水面响应，可做隔离 A/B 原型”；代价是额外系统、性能和集成风险。Crest 自己也声明 buoyancy physics 不是核心重点，并建议专业物理另用其他资产。[Crest watercraft](https://crest.readthedocs.io/en/latest/user/watercraft.html#boats) 所以不应因为尾流好看就把 Crest 的船体响应当成导航物理真实性。

## 6. 推荐实施与验收顺序

### A. 先锁定天空和远景

1. 在最终 M6 runtime volume stack 中强制验证 `VisualEnvironment.skyType=PhysicallyBased`，并让该参数 `overrideState=true`；保留 PBS override，开启 Affect Physically Based Sky。
2. 用固定太阳高度拍三组图：正午、低太阳、夜间；每组关闭 Volumetric Clouds 做基准，再开启 Simple/Quality 两档云。检查天空颜色、地平线、云阴影、水面反射是否由同一套太阳/大气驱动。
3. 对近、中、远三圈地形分别验收：纹理/植被/岸线细节、雾衰减、LOD 切换和地平线融合。不要先用黑色或高密度雾把缺失地形隐藏。

### B. 保留 HDRP，重做船水视觉层

1. 艏部：Water Decal Bow Wave + 左右水线接触点；波高按对水速度、浸没和相对入水速度调节。
2. 艉部：继续用 native foam atlas，但记录船体世界轨迹和年龄，持续注入多个带衰减的尾迹片段；不要只移动一个短尾部 decal。
3. 喷溅：VFX Graph 从 HDRP 水面取高度/法线/current；喷溅粒子只负责视觉，不能反写导航物理。
4. 尾迹：直航、转弯、减速、停止和倒退分别验收。尾迹应跟随历史航迹并逐渐消散；船停止后不能继续产生推进泡沫。

### C. 物理边界单独验收

画面验收通过后，再用波高、周期、方向、对水速度、船体响应的统计量验证；不要用“白沫更多”或“船摇得更大”证明真实水动力。Aeolus 的三角形受力/6-DOF 方法和 MMUSV-Sim 的姿态 RMS 都只能作为研究参考，不能替代本项目已确认的后端动力学权威。

### D. 何时评估 Crest

只有在上述 HDRP 路径完成且固定相机验收仍显示“长尾迹必须有动态波面传播”时，再建立独立 Crest 原型，比较：

| 指标 | 原生 HDRP | Crest 原型 |
|---|---|---|
| 海面/天空/HDRP 场景一致性 | 高 | 需额外材质/反射集成 |
| Water Decal 局部艏艉泡沫 | 原生支持 | 支持 foam/wake 输入 |
| 船体导致的动态水面波 | 需自定义历史注入 | 多分辨率 dynamic waves |
| 物理船舶真实性 | 仍需项目自己的动力学 | Crest 文档称 buoyancy 非核心 |
| 许可证/成本 | 项目已有 | GitHub MIT 版本仅 Built-in；HDRP/Water 5 走 Asset Store |

## 7. 陆地、岸线和港口资产补充诊断

新增实机证据：[M6 coast-near capture](</Users/marine/Code/Colav-Simulator/output/dt-realism-20261009/render-1/coast-near.png>)。该帧已经在 runtime 验证 `skyType=4`；画面仍暴露资产和采样分辨率问题，因此 HDRP 天空切换不能修复岸线/港区质量：

- 12 km Terrain tile 只使用一张卫星 JPG 作为 TerrainLayer diffuse；near 2049/2048 采样约 5.86 m/px，far 512/512 约 23.44 m/px，放大高度图不会新增岸线几何细节。[manifest near](</Users/marine/Code/Colav-Simulator/tmp/m6-data/manifest.json:20>)、[manifest far](</Users/marine/Code/Colav-Simulator/tmp/m6-data/manifest.json:84>)
- 管线把卫星 TCI/radiance JPG 直接作为 sRGB diffuse，并把 `diffuseRemapMax` 固定为 0.65；这能抑制过曝，却不能把影像变成岩石、泥滩、混凝土、草地等物理材质。[M6TerrainPipeline](</Users/marine/Code/Colav-Simulator/sango/Assets/Scripts/Editor/M6TerrainPipeline.cs:88>)
- M7 注释明确 A1 岸桥/箱堆是基本体组合，A4 因无可用 3D 树资源而使用树卡兜底；截图中的巨型方盒岸桥、彩色箱堆和扁平树卡与源码一致。[M7BackdropBuilder](</Users/marine/Code/Colav-Simulator/sango/Assets/Scripts/Editor/M7BackdropBuilder.cs:8>)
- M6 当前是新加坡海峡场景：manifest 为 `EPSG:32648`，`center_lonlat=[103.8,1.28]`。[M6 manifest](</Users/marine/Code/Colav-Simulator/tmp/m6-data/manifest.json:1>) 这是把海峡数据放到 Unity 原点的局部地理场景，不是挪到挪威，也没有当前 Norway 港口的真实地理配准。

Copernicus GLO-30 的产品说明列出 Norway National DEM 作为全球产品可能使用的填补源之一；这是数据生产 provenance，不是当前 M6 的地理位置或港口外观来源。[Copernicus DEM sources](https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM#sources)

### 7.1 可行资产路线

| 路线 | 一手来源和许可 | 可解决的问题 | 边界与运行时影响 |
|---|---|---|---|
| 保留 Copernicus GLO-30 + GEBCO | [Copernicus DEM](https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM)：GLO-30 全球 30 m、免费许可、需按页面要求保留来源声明；当前 CDSE 下载需遵守 CCM 注册/访问条件 | 远景地形、海岸大形、水下地形底座 | 30 m 是近岸几何细节上限；不能用 5.86 m 上采样冒充 1 m 岸线 |
| Sentinel-2 L2A 只做底图/分类 | [Copernicus Sentinel-2](https://dataspace.copernicus.eu/data-collections/copernicus-sentinel-missions/sentinel-2)：10/20/60 m 多光谱，数据免费；L2A 提供大气校正地表反射率 | 远景色彩、陆海/植被/裸地/城市 material mask | 不是 PBR albedo，也没有港口建筑立面；不要继续把原始 TCI 直接铺成近景地面 |
| CC0 岩石、泥滩、混凝土、植被 PBR | [Poly Haven license](https://polyhaven.com/license)：HDRI、纹理和模型 CC0；[ambientCG](https://ambientcg.com/license)：PBR materials 按站点许可页为 CC0 | 近岸 Terrain Lit 材质、岸壁、礁石、散布岩块、树/灌木 hero assets | 需要统一米制尺度、法线/粗糙度/高度通道和 LOD；资产导入本身不是地理真值 |
| OSM 矢量 + 程序化港区建筑 | [OSM copyright/license](https://www.openstreetmap.org/copyright)：ODbL，必须 attribution，改造数据库需同许可证；[Simple 3D Buildings](https://wiki.openstreetmap.org/wiki/Simple3DBuildingsV1)：可用 footprint、height、roof tags 做 LOD1/LOD2 挤出 | 港区建筑 footprint、仓库、道路、堆场边界、建筑高度 | OSM 不是精确码头 BIM/扫描；用于布局和远景建筑，岸桥/管线/船厂应由项目自己建模 |
| 新加坡官方建筑/道路数据 | [SLA Digitised Land Information](https://www.sla.gov.sg/geospatial/digitised-land-information/)：building outline、road network 等为可授权数据；[OneMap API](https://www.onemap.gov.sg/apidocs/) 是 SLA 权威国家地图 | 真实 Singapore 港区建筑轮廓和道路 | SLA 页面说明这些数据用于 licensing；OneMap 条款不自动授予内容 IP 权利。当前只建议作为地理参考/API，不把在线图层直接烘焙进可分发 Player |
| 真正近岸 DEM/正射影像 | 向 SLA 申请/购买相应高分辨率官方数据许可，或使用项目拥有权利的测量/摄影数据；[OneMap 条款](https://www.onemap.gov.sg/legal/apitermsofservice.html) | 1–2 m 级岸线、码头平台、堤岸和建筑底面 | 当前公开一手资料没有给出可直接离线分发的 Singapore 高分辨率 DEM/orthophoto；不能把 OneMap/地图截图当 CC0 资产 |

### 7.2 资产和运行时预算

现有项目已经有可执行的护栏：TerrainM6 总资产预算 100 MB，TerrainM7 新增资产预算 60 MB，树卡上限 4000。[M6 budget](</Users/marine/Code/Colav-Simulator/sango/Assets/Scripts/Editor/M6TerrainPipeline.cs:18>)、[M7 budget](</Users/marine/Code/Colav-Simulator/sango/Assets/Scripts/Runtime/Vessels/M7BackdropMath.cs:20>) 不应通过批量加入 8K 纹理或高面数港口模型来解决截图问题。

当前 Terrain 实例的 `m_DrawInstanced: 0`、Tree Distance 5000 m、Billboard Distance 50 m、Splat Map Distance 1000 m。[M6 scene Terrain settings](</Users/marine/Code/Colav-Simulator/sango/Assets/Scenes/M6-Strait.unity:507>) Unity 6 的 [Terrain.drawInstanced](https://docs.unity3d.com/6000.0/ScriptReference/Terrain-drawInstanced.html) 默认值为 false；[Terrain details](https://docs.unity3d.com/6000.0/Manual/terrain-Grass.html) 建议大量重复草/岩石使用 GPU-instanced mesh。应在独立 profile 做 `drawInstanced=true` 的性能 spike，再决定是否纳入产品质量档；不能把性能结论从文档直接推断为本机通过。

### 7.3 7 条实际落地线

1. 保持 M6 的 Singapore `EPSG:32648` 地理锚点；不再用“挪威/真实港口”描述当前画面。
2. 保留 GLO-30/GEBCO 做远景和海底；近景 0–1 km 单独寻找有许可的高分辨率 DEM/orthophoto。
3. 停止把 Sentinel-2 TCI 直接当近岸 PBR diffuse；用它生成陆海/植被/城市 mask，再叠加 CC0 PBR 岩石、泥滩、混凝土和植被材质。
4. 把 M7 基本体岸桥替换为 1 个近景 hero crane + 低面数重复 LOD；箱堆使用共享 mesh/material 实例。
5. 把树卡只留作远景过渡；近岸使用少量真实树/灌木/岩石实例，先解决 billboard 近景穿帮。
6. 维持 100 MB TerrainM6、60 MB TerrainM7、4000 树实例预算；near 纹理 2K/4K，far 纹理 1K 级，所有候选资产先做 GPU/内存 profiling。
7. 以 near/mid/far 三个固定机位复验：岸线轮廓、地表纹理、植被/岩石、港区建筑、LOD 过渡和 30 FPS；天空修复不能替代这组资产验收。

## 8. 挪威目标海域：当前 ENC 的可落地数据路线

最新选择已把实施目标切换为截图所示的挪威海域；上一节 Singapore 资产建议保留作审计历史，不再作为生产场景方向。截图点约为 `62.4558 N, 6.0437 E`。现有 ENC/场景使用 ETRS89 / UTM zone 33 的水平部分（EPSG:25833），本地 ENC 原点约 `E=39000, N=6956450`、6 km 画布；[scene geography fixture](</Users/marine/Code/Colav-Simulator/tests/web_gui/fixtures/scene-geography.json:160>)。

用 EPSG:25833 将截图点转换为约 `E=38997.91, N=6956998.88`，所以 parent 侧提出的 ENC 扩展域 `E 33000..51000, N 6950450..6968450` 是正确的 18 km × 18 km 数据窗口。

### 8.1 首选：Kartverket Nasjonal høydemodell WCS

Kartverket 公开 WCS capabilities：

```text
https://wcs.geonorge.no/skwms1/wcs.hoyde-dtm-nhm-25833?service=WCS&request=GetCapabilities
```

实测 capabilities 返回：

- provider `Kartverket`；`Fees=free`；`AccessConstraints=None`；
- coverage `nhm_dtm_topo_25833`；
- supported CRS `EPSG:25833` / `EPSG:4326`；
- GeoTIFF、HDF、JPEG2000、NetCDF；
- 服务覆盖 `57.27..72.10 N, -2.01..33.34 E`，包括 62.4558 N, 6.0437 E。

18 km ENC 域、10 m overview 的可复现请求：

```text
https://hoydedata.no/arcgis/services/NHM_DTM_25833/ImageServer/WCSServer?service=WCS&version=1.0.0&request=GetCoverage&coverage=nhm_dtm_topo_25833&crs=EPSG:25833&bbox=33000,6950450,51000,6968450&format=GeoTIFF&width=1800&height=1800
```

该请求已实际返回 1800×1800、10 m 像元、EPSG:25833 GeoTIFF，约 11.7 MB；统计值约 -2.9..775.8 m。1 km 近岸、1 m 像元请求也已成功：

```text
https://hoydedata.no/arcgis/services/NHM_DTM_25833/ImageServer/WCSServer?service=WCS&version=1.0.0&request=GetCoverage&coverage=nhm_dtm_topo_25833&crs=EPSG:25833&bbox=38500,6958500,39500,6959500&format=GeoTIFF&width=1000&height=1000
```

此小窗口返回 1000×1000、1 m 像元、EPSG:25833 GeoTIFF，约 3.2 MB，最大高程约 58.97 m。[本轮 10 m 域样本](</Users/marine/Code/Colav-Simulator/tmp/kartverket-norway-research/dtm25833-enc-domain-10m.tif>)、[本轮 1 m 近岸样本](</Users/marine/Code/Colav-Simulator/tmp/kartverket-norway-research/dtm25833-near-1m-land.tif>)、[capabilities 原文](</Users/marine/Code/Colav-Simulator/tmp/kartverket-norway-research/dtm25833-capabilities.xml>)。

### 8.2 首选数据文件：DTM1 Atom feed

如果要离线重建而不是每次运行时调用 WCS，Kartverket 的 DTM1 feed 是直接 GeoTIFF 路线：

```text
https://nedlasting.geonorge.no/geonorge/ATOM/hoydedata/datasett/DTM1.atom
```

feed 中与截图点相交的 tile 已定位为 `33-109-135`，直接 URL：

```text
https://nedlasting.geonorge.no/hoydedata/DTM1/33-109-135.tif
```

该 tile 覆盖约 `5.9509..6.2784 E, 62.3981..62.5497 N`，包含截图点；feed 标注的文件大小约 432 MB，故不应为了 10 km 画面直接把整块塞入 Player。应使用 WCS 按 near/mid/far 裁剪，或离线裁剪后只保留 Unity 所需窗口。feed 顶部声明 NLOD 2.0；data.norge 记录把该服务列为 Creative Commons Attribution 4.0，发布时保留 Kartverket 来源、原始 URL 和版本日期。[DTM1 service record](https://data.norge.no/en/data-services/df1adc4b-7575-351a-b9d4-4891decc8b16/dtm1-atom-feed-tjeneste)

### 8.3 开放 shoreline / land-mask / harbor vector

Kartverket N50 Kartdata 是更适合做岸线和陆地 mask 的开放矢量底座：产品覆盖 mainland Norway，包含 area cover、buildings、transport 和 place names；元数据显示 CC BY 4.0、UTM32/33/35 分发、按市/县和 Atom feed 下载。[N50 Kartdata metadata](https://kartkatalog.geonorge.no/metadata/uuid/ea192681-d039-42ec-b1bc-f3ce04c189ac)

截图所在 Ålesund 区域直接 GML 下载链接已在官方 Atom feed 中验证并返回 HTTP 200：

```text
https://nedlasting.geonorge.no/geonorge/Basisdata/N50Kartdata/GML/Basisdata_1508_Alesund_25833_N50Kartdata_GML.zip
https://nedlasting.geonorge.no/geonorge/Basisdata/N50Kartdata/GML/Basisdata_1531_Sula_25833_N50Kartdata_GML.zip
https://nedlasting.geonorge.no/geonorge/Basisdata/N50Kartdata/GML/Basisdata_1532_Giske_25833_N50Kartdata_GML.zip
```

N50 是 1:50 000 制图数据，适合远景 coastline、岛屿、水陆 mask、建筑/道路布局，不适合替代 1 m 岸线测量。近岸建筑和海堤应以 DTM1 + 可授权正射影像复核后再建模。

### 8.4 正射影像的现实边界

官方 Norge i bilder 服务现行地址：

```text
https://services.norgeibilder.no/wms/ortofoto?service=WMS&request=GetCapabilities
https://tilecache.norgeibilder.no/wmts/utm32_euref89?SERVICE=WMTS&REQUEST=GetCapabilities
```

本轮无 token 实测：WMS 返回 ArcGIS `http.499`，WMTS 返回 `{"error":{"code":499,"message":"Token Required"}}`。Kartverket 官方迁移公告说明这些服务需要 GeoID/Norge digitalt 访问，公开旧 WMTS 正在停用；data.norge 将 WMS-Ortofoto 和 WMTS 标为 restricted access，并指向 Norge digitalt license。[Norge i bilder service changes](https://www.geonorge.no/nib)、[WMS-Ortofoto record](https://data.norge.no/nb/data-services/6c92dae8-8fb1-3af4-81ff-52e572d2c971/digitale-ortofoto-norge-i-bilder-wms-ortofoto-ny)、[本轮无 token 返回](</Users/marine/Code/Colav-Simulator/tmp/kartverket-norway-research/orthophoto-wmts-no-token.json>)

所以当前无凭证方案不能把 Norge i bilder 正射影像作为可离线再分发的输入。可用的开放回退是 Copernicus Sentinel-2 L2A：免费、10 m 多光谱、提供地表反射率，但它不是航空正射影像，不能解决近岸 1 m 建筑/岩石细节。[Norge i bilder service changes](https://www.geonorge.no/nib)、[Sentinel-2 official data](https://dataspace.copernicus.eu/data-collections/copernicus-sentinel-missions/sentinel-2)

若 Kartverket WCS 暂时不可用，Copernicus GLO-30 S3 COG 可作 30 m fallback，N62E005/E006 公共对象当前 HEAD 返回 200：

```text
https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N62_00_E005_00_DEM/Copernicus_DSM_COG_10_N62_00_E005_00_DEM.tif
https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N62_00_E006_00_DEM/Copernicus_DSM_COG_10_N62_00_E006_00_DEM.tif
```

GLO-30 只能作为远景/应急地形，不能替代已经验证可用的 Kartverket DTM1/DTM WCS。

## 9. Google Photorealistic 3D Tiles：Ålesund 覆盖结论

### 9.1 能确认的官方事实

Google 官方 Photorealistic 3D Tiles 文档把产品描述为“many of the world's populated areas”，并要求 Google Maps Platform 项目、计费账户、Map Tiles API 和 API key；官方示例的 root tileset 是 `https://tile.googleapis.com/v1/3dtiles/root.json?key=...`。[Google Photorealistic 3D Tiles](https://developers.google.com/maps/documentation/tile/3d-tiles)

Google 的国家级 coverage 表中，Norway 的 `Map Tiles 2D / 3D` 显示为可用，但官方同时说明覆盖会因数据许可等原因变化。该表没有给出 Ålesund 或坐标级 Photorealistic 3D Tiles coverage，不能从“Norway=3D available”推出 `6.0437E, 62.4558N` 一定有真实 3D 建筑。[Google coverage details](https://developers.google.com/maps/coverage)

本轮没有访问 Google 或 Cesium 的任何用户 token。无凭证请求 Google root tileset 返回 HTTP 403 `PERMISSION_DENIED`，所以不能把 endpoint 可达、Norway 国家级标记或当前代码中的 asset ID 当作本地覆盖证据。

### 9.2 Cesium ion 标准路径

Cesium for Unity 1.26.0 的标准路径是：连接 Cesium ion → Quick Add 的服务器资产列表 → 选择 “Google Photorealistic 3D Tiles” → `CesiumGeoreference` 设置经纬高 → `Cesium3DTileset` 从 Cesium ion 加载。官方 Unity 教程明确要求 Cesium ion 账号、项目 token 和 `showCreditsOnScreen`；每个从 ion streaming 的资产都需要 Access Token。[Cesium Unity Google Photorealistic tutorial](https://cesium.com/learn/unity/unity-photorealistic-3d-tiles/)

项目内 SDK 证据：

- Cesium package 为 1.26.0。[package.json](</Users/marine/Code/Colav-Simulator/sango/Library/PackageCache/com.cesium.unity@D454711FBE38/package.json:1>)
- `Cesium3DTileset` 支持 `FromCesiumIon`、ion asset ID、ion access token、ion server；官方 SDK 不要求把 Google URL 直接硬编码到 Unity。[Cesium3DTileset](</Users/marine/Code/Colav-Simulator/sango/Library/PackageCache/com.cesium.unity@D454711FBE38/Source/Runtime/Cesium3DTileset.cs:127>)
- Quick Add 资产列表由 ion server 运行时拉取，因此没有 token 时本地源码不会包含或验证 Google 资产的完整覆盖信息。[CesiumEditorWindow](</Users/marine/Code/Colav-Simulator/sango/Library/PackageCache/com.cesium.unity@D454711FBE38/Source/Editor/CesiumEditorWindow.cs:279>)
- 当前项目已经有 Photoreal 分支，使用 `--twin-cesium-photoreal` 和本机 token 文件，并选择 asset ID `2275207`；这证明接入路径存在，但不是对 Ålesund 覆盖的独立证据。[TwinCesiumLandscape](</Users/marine/Code/Colav-Simulator/sango/Assets/Scripts/Runtime/TwinCesiumLandscape.cs:33>)

### 9.3 推荐的无泄密覆盖检测

拿到已有的标准 Cesium ion token 后，只需在本地运行现有 Photoreal 分支，不打印 token、不提交 token 文件，做两组隔离实验：

1. **Google-only**：暂时关闭 World Terrain、Bing、OSM Buildings 和 HDRP Water，只保留 Photoreal tileset；设置 origin 到 `6.0437, 62.4558`，等待 tileset load progress 收敛，记录是否创建了本地 tile mesh、是否出现 load failure、最终 credits 和相机高度。
2. **Water-overlap**：确认 Google-only 有实际土地/建筑 tile 后再打开 HDRP 水面；如果 Google mesh 在海面下/上形成矩形或遮挡水面，用 `CesiumCartographicPolygon` / tile exclusion 隔离土地范围，保持 HDRP 水面为唯一海面渲染源。Cesium 官方说明重叠 tileset 会产生相交伪影，并建议用 cartographic polygon 隐藏冲突区域。[Cesium clipping](https://cesium.com/learn/unity/unity-clipping/)

判定标准应是“该坐标下确实加载了 photogrammetry tile mesh 和影像纹理”，而不是 root 请求成功或国家 coverage 表有圆点。如果 Google-only 在 Ålesund 无 tile/无建筑而只加载空海面或低分辨率底层，则结论是当地没有可用 Photoreal coverage，直接回退已验证的 Kartverket DTM1/WCS + N50 + 自建材质路线。

当前可靠结论：**官方资料确认 Norway 国家级 Map Tiles 3D 可用，Cesium ion 标准接入路径可用；公开官方资料和无凭证请求不足以确认 Ålesund 坐标级 Photorealistic 3D Tiles 覆盖。必须由已有授权 token 做 Google-only 实测后才能下结论。**

## 10. Cesium 反选裁剪：native 根因定位

这次“只剩 8 个粗 mesh、进度 100%、陆地全空”与 Cesium native 的既有失败模式高度一致。Cesium Unity 1.26.0 的变更记录明确说明它更新到 cesium-native v0.65.0。[Cesium Unity 1.26 CHANGES](https://github.com/CesiumGS/cesium-unity/blob/v1.26.0/CHANGES.md)、[Cesium native v0.65 CHANGES](https://github.com/CesiumGS/cesium-native/blob/v0.65.0/CHANGES.md)

native 调用链很具体：`CesiumPolygonRasterOverlayImpl` 把 Unity 点转成弧度后创建 `CartographicPolygon`；当 `excludeSelectedTiles=true` 时，再把同一个 overlay 放进 `RasterizedPolygonsTileExcluder`。excluder 在 `invertSelection=true` 时调用 `outsidePolygons(tile.getBoundingVolume(), ...)`。[Unity native bridge](https://github.com/CesiumGS/cesium-unity/blob/v1.26.0/native~/src/Runtime/CesiumPolygonRasterOverlayImpl.cpp)、[Tile excluder](https://github.com/CesiumGS/cesium-native/blob/v0.65.0/Cesium3DTilesSelection/src/RasterizedPolygonsTileExcluder.cpp)

`outsidePolygons` 不是对已加载 mesh 顶点做点-in-polygon。它先把 tile bounding volume 估算成 `GlobeRectangle`，再用这个估算矩形与 polygon 的包围矩形、顶点和边做相交判定；判定为 outside 就在树选择阶段把该 tile 及其 descendants 排除。[TileUtilities](https://github.com/CesiumGS/cesium-native/blob/v0.65.0/Cesium3DTilesSelection/src/TileUtilities.cpp)、[CartographicPolygon](https://github.com/CesiumGS/cesium-native/blob/v0.65.0/CesiumGeospatial/src/CartographicPolygon.cpp)、[BoundingVolume estimate](https://github.com/CesiumGS/cesium-native/blob/v0.65.0/Cesium3DTilesSelection/src/BoundingVolume.cpp) 因此，6552 点的经纬度范围正确，只能证明 polygon 输入正确，不能证明 Google tile bounding volume 的估计矩形与这些 polygon 相交。

这不是猜测出来的开关语义：Cesium 官方 issue #803 就记录了 **Google Photorealistic 3D Tiles + Invert Selection + Exclude Selected Tiles 会把所有 tile 排除**；关闭 Exclude 后 inverted clip 正常。[issue #803](https://github.com/CesiumGS/cesium-native/issues/803) 后续 PR #808 修复了包围球/盒包含 ECEF 原点时的全球矩形估计；PR #917 又修复了弧度坐标下过小三角形被误判为 degenerate，以及 raster overlay upsampled bounding volume 问题。[PR #808](https://github.com/CesiumGS/cesium-native/pull/808)、[PR #917](https://github.com/CesiumGS/cesium-native/pull/917) v0.65 已包含这些历史修复，所以当前复现更准确的描述是：**excluder 路径被 A/B 证实为根因类别；仍需确认当前 Google asset 的 tile-BV 估计或本机 native binary 是否触发同一类 false-outside，不能把旧 issue 直接等同为已证明的版本 bug。**

本地运行结果已经给出最有区分力的 A/B：`google-refined` 有 2632 个 terrain mesh 且能看到 Ålesund 岸山，[report](</Users/marine/Code/Colav-Simulator/output/dt-realism-20261009/google-refined/report.json>)；打开反选 tile exclusion 后的 `google-clipped` 只剩 8 个 terrain mesh、画面无陆地，[report](</Users/marine/Code/Colav-Simulator/output/dt-realism-20261009/google-clipped/report.json>)。这把问题从坐标、OnEnable 顺序、HDRP 水面和 materialKey 缩小到 `excludeSelectedTiles` 的 tile-tree pruning；`invertSelection=true, excludeSelectedTiles=false` 是当前可用的临时工作点，视觉 mask 仍能隐藏海面，只是会继续加载海域 tile。

当前 N50 mask 的 179 个环均为顺时针（平面有向面积为负），但 Cesium native 的 earcut 不要求固定 winding；用同一 JSON 点集做的 179 次 earcut 结果均为非空三角索引。[本轮 mask](</Users/marine/Code/Colav-Simulator/sango/Assets/Resources/NorwayLandMask.json>)、[本轮 earcut 检查](</Users/marine/Code/Colav-Simulator/tmp/dt-realism-20261009/earcut-test.out>) 因而目前没有证据支持“全场为空是 winding 反了”。

最小区分实验：保持 `invertSelection=true` 和 `excludeSelectedTiles=true`，把 179 环临时替换为覆盖整个 18 km chart 域的一个简单凸四边形。若仍只有 8 个 mesh，直接指向 Google tile bounding-volume / native binary；若恢复岸山，再逐步加入 N50 环，说明复杂环的 bounding rectangle/triangulation 触发 false-outside。另可在 `excludeSelectedTiles=false` 状态记录一个可见 Google tile 的 Cesium tile bounds，再与 `5.912665..6.290667 / 62.390265..62.572064` 做相交检查；若 Unity mesh 可见但估算 bounds 不与 mask 相交，即为可复核的 native pruning 证据。不要用 token、国家 coverage 或 100% progress 代替这个检查。

## 11. 主要一手链接

- Unity HDRP 17.3：[Water foam](https://docs.unity.cn/Packages/com.unity.render-pipelines.high-definition@17.3/manual/water-foam-in-the-water-system.html)、[Water decal deformation/Bow Wave](https://docs.unity.cn/Packages/com.unity.render-pipelines.high-definition@17.3/manual/water-deform-a-water-surface.html)、[Water VFX interaction](https://docs.unity.cn/Packages/com.unity.render-pipelines.high-definition@17.3/manual/water-vfx-interaction.html)、[Physically Based Sky](https://docs.unity.cn/Packages/com.unity.render-pipelines.high-definition@17.3/manual/create-a-physically-based-sky.html)、[Volumetric Clouds](https://docs.unity.cn/Packages/com.unity.render-pipelines.high-definition@17.3/manual/create-realistic-clouds-volumetric-clouds.html)
- Aeolus Ocean：[论文](https://arxiv.org/abs/2307.06688)、[作者仓库/README](https://github.com/aavek/Aeolus-Ocean)、[BSD-3-Clause](https://github.com/aavek/Aeolus-Ocean/blob/main/LICENSE)
- MMUSV-Sim：[论文](https://arxiv.org/abs/2608.14207)
- Crest：[GitHub](https://github.com/wave-harmonic/crest)、[动态波/水工艺文档](https://crest.readthedocs.io/en/latest/user/waves.html)、[Unity Asset Store](https://assetstore.unity.com/packages/tools/particles-effects/crest-water-5-oceans-rivers-lakes-268614)
