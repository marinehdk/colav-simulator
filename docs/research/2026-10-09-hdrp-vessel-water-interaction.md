# Aeolus-Ocean 对照、HDRP 船水交互优化方案与首阶段实施

日期：2026-10-09。环境：Unity 6000.3.24f1、HDRP 17.3.0、A4000 Vulkan/NVENC；本机继续运行仿真后端。原文、作者仓库、Unity 官方文档及项目锁定的 SDK 源码为证据；GIF 仅作为视觉参考。

## 结论与能力边界

原有 DT 白条来自独立透明尾迹网格，并非水面泡沫。恢复原生泡沫后，又核实 HDRP 17.3 两处实现不一致：移动区域的泡沫绘制目标未重新绑定；Shader Graph 写 R/G 而运行时消费者读 G/B。首阶段已通过项目内适配处理，未修改 PackageCache。

本阶段继续保留后端 4-DOF 的位置、航向、横摇与风浪流负载。DT 查询 HDRP 波面补视觉升沉/纵摇；浪花跟随船体相对入水变化；推进尾流按对水速度注入原生水面。它不是 Aeolus 的完整六轴水动力或 CFD 复现。风浪流参数的 HDRP 显示仍为工程映射，不能声明与论文波谱严格数值一致。

## 1. Aeolus 原文如何实现

用户原文：[Aeolus Ocean PDF](</Users/marine/Documents/Paper/Aeolus Ocean - A simulation environment for the autonomous COLREG-compliant navigation of Unmanned Surface Vehicles using Deep Reinforcement Learning and Maritime Object Detection.pdf>)，22 页，以下页码按 PDF 页序。在线作者版本：[arXiv:2307.06688](https://arxiv.org/pdf/2307.06688)。

| 原文位置 | 方法 | 当前系统对应及差别 |
|---|---|---|
| 第 2–4 页，§2.I | 波谱和高斯初相、有限水深色散、IFFT、高度/水平位移；PM、JONSWAP、TMA、方向扩展及多尺度波段 | HDRP 提供频谱水面；现有 Hs/Tp 控制映射到风速、波段能量和重复尺度，尚未逐谱校准 |
| 第 8 页，§3.A.i | GPU compute 纹理、近密远疏的相机跟随 LOD 海面；HDRP 反射/折射/次表面散射/Fresnel；自定义波峰白沫、降水 ripple；VFX Graph 天气、体积云与灯光 | 使用 HDRP 原生波面/云/灯光；船尾与接触泡沫应进入水面渲染，而不是悬浮白色平面 |
| 第 10–11 页，§3.C、式 33–40 | 按水线拆分浸没三角形；面片速度 U+Ω×CG；浮力、法向阻力、切向摩擦、局部流速、风载；在面片中心施力形成力矩 | 当前显示求解器只从水高估计姿态，没有这套湿面受力积分 |
| 第 12 页 | 推进点施力、PhysX 六轴刚体积分，Jobs/Burst 加速 | 按用户已确认边界保留后端 4-DOF；不在 Unity 再建第二套导航物理权威 |

论文示例船约 **8 m、3.5 t**（第 2 页）；本船约 45 m。相同海况下不能靠放大摇摆使两者画面一致。原文没有公开可直接移植、经验证的船尾 CFD 算法，也没有明确给出 slamming 模型。

[作者仓库](https://github.com/aavek/Aeolus-Ocean) 当前提供说明与 binary，没有 Unity 源码；README 描述简化粒子泡沫并提示大浪下的视觉限制。因此本次借鉴公开方法，不声称私有源码移植。

## 2. HDRP 原生路径与两个已核实问题

官方入口：[HDRP WaterSurface API](https://docs.unity3d.com/Packages/com.unity.render-pipelines.high-definition@17.3/api/UnityEngine.Rendering.HighDefinition.WaterSurface.html)、[Unity Water samples](https://github.com/Unity-Technologies/WaterScenes)、[官方 foam overview](https://github.com/Unity-Technologies/Graphics/blob/master/Packages/com.unity.render-pipelines.high-definition/Documentation~/introduction-to-foam.md)。具体版本事实以项目内 17.3 源码为准。

### 2.1 区域移动时的绘制目标

[WaterSystem.Decals.cs:377](/Users/marine/Code/Colav-Simulator/sango/Library/PackageCache/com.unity.render-pipelines.high-definition@700710090fa9/Runtime/Water/HDRenderPipeline.WaterSystem.Decals.cs:377) 的区域变化分支只执行 ReprojectFoam/AttenuateFoam compute；稳定区域的 else 分支才显式绑定 currentFoamBuffer。其后共同执行 FoamDecal DrawProcedural。没有找到前置的 graphics target 绑定兜底。

逐帧跟船移动的 anchor 会频繁走此分支，影响新泡沫累积。工程适配：独立世界区域，船在其中移动；离区域中心超过短边的 10% 才重定位。FCB45 的 108 m 区域约每 10.8 m 重定位，艏/艉源仍在区域内。重定位帧可能缺一次注入；不是完整修复引擎内核。

### 2.2 Shader Graph 与消费者通道错位

[WaterDecalShaderPass.template:126](/Users/marine/Code/Colav-Simulator/sango/Library/PackageCache/com.unity.render-pipelines.high-definition@700710090fa9/Editor/Material/Water/ShaderGraph/WaterDecalShaderPass.template:126) 的 Foam pass 返回 float2(surface, deep)，实际写入 atlas R/G。[ProcessWaterDecals:306](/Users/marine/Code/Colav-Simulator/sango/Library/PackageCache/com.unity.render-pipelines.high-definition@700710090fa9/Runtime/Water/HDRenderPipeline.WaterSystem.Decals.cs:306) 直接绘制到 RGBA atlas，没有通道重排。[WaterDecal.shader:127](/Users/marine/Code/Colav-Simulator/sango/Library/PackageCache/com.unity.render-pipelines.high-definition@700710090fa9/Runtime/Water/Shaders/WaterDecal.shader:127) 却读取 atlas.yz。

| 写入 | 原生消费者实际解释 |
|---|---|
| Graph SurfaceFoam → R | 被忽略 |
| Graph DeepFoam → G | 当作表层泡沫 |
| B = 0 | 深层泡沫为零 |

原纹理 G 为 R 的 20%，解释了稳定区域下峰值约 0.10 的低强度。项目本地 [TwinFoamInjector.shader](/Users/marine/Code/Colav-Simulator/sango/Assets/Art/WaterDecals/TwinFoamInjector.shader) 用合法 WaterDecal atlas `Foam` pass 显式输出 **(0, surface, deep, 0)**，与该版本消费者匹配。Vulkan 真机峰值随后达约 0.50。后续升级 HDRP 必须重新核对 ABI，不能盲用此适配。

### 2.3 其他 API 约束

- 输入纹理 R=期望表层、G=期望深层；项目 shader 再转为 atlas G/B。原生 foam buffer 本身则是 R=表层、G=深层。三种布局不要混淆。
- `HDShaderIDs._AffectsFoam` 的真实 shader property 名为 **_AffectFoam**，见 [HDStringConstants.cs:634](/Users/marine/Code/Colav-Simulator/sango/Library/PackageCache/com.unity.render-pipelines.high-definition@700710090fa9/Runtime/RenderPipeline/HDStringConstants.cs:634)。
- 注入 pass 已乘 `_DeltaTime`，C# dimmer 不再乘 dt。GPU 数据接受 surface/deep dimmer；源材质改变后调用 RequestUpdate。
- 最终相机的 WaterDecals frame setting 必须开启，否则水面绑定黑泡沫纹理，见 [WaterSystem.cs:710](/Users/marine/Code/Colav-Simulator/sango/Library/PackageCache/com.unity.render-pipelines.high-definition@700710090fa9/Runtime/Water/HDRenderPipeline.WaterSystem.cs:710)。真机诊断确认本次为 true。
- `foamPersistenceMultiplier=.75` 控制指数消散；不是“保留越久越真实”。
- `foamCurrentInfluence` 在 [FoamUtilities.hlsl](/Users/marine/Code/Colav-Simulator/sango/Library/PackageCache/com.unity.render-pipelines.high-definition@700710090fa9/Runtime/Water/Shaders/FoamUtilities.hlsl) 改变侵蚀纹理采样位置，不对沉积泡沫做质量平流。[WaterFoam.compute](/Users/marine/Code/Colav-Simulator/sango/Library/PackageCache/com.unity.render-pipelines.high-definition@700710090fa9/Runtime/Water/Shaders/WaterFoam.compute) 只有重投影与衰减相关 kernel。区域重投影保持世界位置，也不是海流平流。

## 3. 首阶段实施

| 项目 | 实施 |
|---|---|
| 生硬白条 | DT 禁绘 legacy ribbon 与 waterline ring；保留 Demo 路径。DT 不再执行它们的逐顶点水高查询 |
| 推进尾流 | 短艉部多孔纹理向原生水面注入；表层/深层独立强度；HDRP 负责水面光照、细节侵蚀、持久与消散 |
| 艏部破波 | 保留 Froude 驱动的原生艏波变形；左右艏接触点在本帧升沉/纵摇/横摇后的水线查询，按浸没及相对入水速度生成原生泡沫和小规模喷溅 |
| 静止与暂停 | CREATED 的配置初速不产生推进尾流；暂停、缓冲停帧、倒退 seek 都停止推进注入。环境波面及接触反馈仍可运动 |
| 六轴显示 | 后端 x/z/yaw/roll 保留；原生波面查询 + 阻尼视觉 heave/pitch；不重复添加波面横摇；自造艏波不回馈成自激船体升沉 |
| 性能 | Ownship 泡沫区域 512，变形 256；接触点每船两次查询；64/16 点的既有船体查询保留；最多 144 喷溅粒子 |
| 生命周期 | 先 detach 桅杆 rig 再销毁旧船；新船独立重绑相机；旧场景自由位姿在重绑时清除；区域、材质、纹理随槽位清理 |
| 观测 | state.motion 的推进注入、接触泡沫、入水速度、升沉/纵摇/横摇；每 10 s 异步回读实际水面泡沫峰值，非 UI 估算值 |

源码入口：[BoatWaterDecals.cs](/Users/marine/Code/Colav-Simulator/sango/Assets/Scripts/Runtime/BoatWaterDecals.cs)、[TwinSessionDriver.cs](/Users/marine/Code/Colav-Simulator/sango/Assets/Scripts/Runtime/TwinSessionDriver.cs)、[WakeFoamRig.cs](/Users/marine/Code/Colav-Simulator/sango/Assets/Scripts/Runtime/WakeFoam/WakeFoamRig.cs)、[TwinBridgeService.cs](/Users/marine/Code/Colav-Simulator/sango/Assets/Scripts/Runtime/TwinBridgeService.cs)。

入水泡沫/喷溅强度是显示用启发式，不是面片力、冲击压力或螺旋桨 CFD。海流进入既有后端负载及对水速度；本阶段没有新增真实泡沫平流或水面反作用力。

## 4. 后续优化顺序

1. **波面量值校准**：用空间/时间水高采样核对实际 Hs、峰值周期、方向扩展；明确 HDRP 原生谱与 PM/JONSWAP/TMA 的差别；进一步对齐加速回放的波面/泡沫时间尺度。验收采用统计量，不靠“摇得更大”。
2. **船型接触与破波**：按真实船体水线布置更多接触点，加入基于入水速度、艏向与相对水流的 VFX 粒子；校准近船短波、艏破波、艉部两个推进器的喷流外观，避免整圈白沫。
3. **远尾迹与海流**：沿历史航迹生成原生水面变形/泡沫，衰减并考虑流场输运；原生 current map 只提供局部流向/纹理反馈，真实平流需另行实现和验证。先在 A4000 检查 30 FPS 再扩预算。
4. **完整动力学（另项）**：若以后需要 Aeolus 式 6-DOF，先取得质量、质心/惯量、湿面、阻力、推进点及 RAO 数据，确定唯一物理权威，再重验导航与避碰。不是本次显示改动的验收结论。

## 5. 验证与证据

- Unity EditMode **66 passed, 0 failed**：推进时钟门、区域保持/重定位、原生泡沫材质与源码 shader、High 档不再压制 native foam、无 ribbon/ring draw、旧桅杆脱离/重挂、旧自由机位清除、既有浮态/回放/环境契约。
- 最终 Linux Player 构建成功；A4000 部署独立 renderer 目录，旧 Player 已备份。没有修改服务器其他项目或 Unity 包缓存。
- 真机 1080p 与 1440p H264 均约 **30 FPS**；1440p 样本 30.52 FPS、24.41 Mb/s。这是接收帧率，不是零抖动或 GPU profiler 验收。样本的 compositor P95 约 50–67 ms、最大约 83 ms，仍有短时帧间隔波动。
- GPU 泡沫峰值：初始持续移动区域约 .04；稳定区域约 .10；正确双通道约 **.497–.511**。暂停后推进注入为 **0**，区域峰值降至约 **.039**，残余包含环境接触泡沫。
- 实际画面：[1440p 航行](/Users/marine/Code/Colav-Simulator/output/dt-water-contact-20261009/native-running-1440p.png)、[暂停消散](/Users/marine/Code/Colav-Simulator/output/dt-water-contact-20261009/paused-decayed.png)。数据和最终重连/恢复记录：[验收报告](/Users/marine/Code/Colav-Simulator/output/dt-water-contact-20261009/report.md)。
- 只验收显示与接入；不从本次截图、focused tests 或运行完成推断完整 COLAV、MASS-L3 或 Aeolus 物理复现验收。
