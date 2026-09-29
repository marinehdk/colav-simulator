# 付费工具与主角船精模的免费/开源替代路线 — 调研报告

- 日期：2026-09-29 ｜ 服务对象：Colav-Simulator（Unity 6000.3.24f1 + HDRP 17.3）
- 前置：[00-REPORT.md](2026-09-24-scene-ship-fidelity/00-REPORT.md)（§2.2 地形管线、§6 风险）、[verify.md](2026-09-24-scene-ship-fidelity/verify.md)（L3/L4/L7/L8）、[procurement-checklist.md](2026-09-24-scene-ship-fidelity/procurement-checklist.md) 表A（A7/A8/A9）
- 研究问题：A7（MicroSplat HDRP 适配包 ≈$20-60）、A8（Amplify Impostors $30-33）、A9（FCB 外包精模 $2-8K）三条付费项，免费/开源替代路线各能走多远。
- 方法：官方文档原文、Asset Store 页面内嵌 JSON 直抓（curl）、Sketchfab API 检索、Creative Commons 法律文本原文、Unity Discussions/GitHub 一手帖。标注约定沿用前报：【事实】=一手来源逐字核实；【推断】=工程判断。
- 访问日：2026-09-29（除注明外）。

---

## 结论速览

| 付费项 | 免费替代结论 | 关键事实 |
|---|---|---|
| A7 MicroSplat HDRP 适配包 $20-60 | **半替代可行**：HDRP 原生 Terrain Lit（8 层/逐层法线/平滑度/高度混合）+ 官方 TerrainLit Shader Graph 自写可到 85-90% 观感；但 **MicroSplat 免费核心在 HDRP 完全不可用**，无免费旁路 | 核心描述原文自认 "HDRP/URP support sold separately"；本项目 6000.3.24 应买 **344008（HDRP for Unity 6.3，$20）** 而非清单 A7 所记 280884（6.0 版） |
| A8 Amplify Impostors $30-33 | **功能替代可行**：远景剪影档用「低模网格远景 LOD」或「手搓 billboard」免费够用；但 Asset Store **无任何实质免费 impostor 工具**，手搓有明确坑 | 官方 BillboardRenderer 在 HDRP 不可用（社区一手+文档旁证）；开源 IMP 仓库已 404、URPIMP 已归档且限 URP |
| A9 FCB 外包 $2-8K | **推迟外包成立**：Sketchfab CC-BY 现成低模（Cyclone 级巡逻舰 PC-3 最对位）作基准网格 + Blender 细化，$0-0 天成本；CC0 巡逻艇检索为 **0** | CC-BY 仅署名义务、可商用；NoAI 标签对 CC 许可模型的效力有争议（CC 法条禁止附加额外限制） |

---

## 1. MicroSplat HDRP 适配包（A7）的免费替代

### 1.1 HDRP 原生 Terrain Lit（免费）能力边界【事实，官方 17.3 文档】

来源：HDRP 17.3 手册 Terrain Lit material 页 + Inspector reference 页（引用见 §4.1/§4.2）。

- **层数**："A Terrain can use a Terrain Lit Material with **up to eight Terrain Layers**."（8 层上限，单 pass）
- **逐层法线**：Terrain Layer 资产支持 Normal Map + Normal Scale；Inspector 有 "Enable Per-pixel Normal"（逐像素采样法线贴图，需开 Draw Instanced，"high-resolution Mesh normals, even if your Mesh is low resolution"）。
- **逐层平滑度**：HDRP/URP 用 Diffuse 贴图 **Alpha 通道作 Smoothness**（Terrain Layers 手册原文）；若有 Mask Map，则 Mask Map 承载（HDRP 惯例 R=metallic / G=AO / B=height / A=smoothness；height 位由 17.3 文档侧证："takes the height values from the **blue channel** of the Mask Map"）。
- **高度混合**：内置 "Enable Height-based Blend"（按 Mask Map 蓝通道高度混层）+ Height Transition 参数——MicroSplat 的招牌 height-blend 免费版原生就有。
- **S2 卫星底图叠加**：官方机制就是**把 S2 影像做成第 0 个 Terrain Layer**——"The first Terrain Layer you apply to a Terrain automatically becomes the **base layer** and spreads over the whole landscape"（Terrain Layers 手册原文），逐层 Tiling/Offset 可对齐世界尺度。注意：HDRP Terrain Lit 17.3 文档**未列** BaseMap-distance 类远距淡出属性（Inspector reference 仅列 Receive Decals / Height-based Blend / Per-pixel Normal / Specular Occlusion / GPU Instancing），即内置管线那种"近处细节贴图、远处 BaseMap"的自动切换在 HDRP 没有现成开关【事实-反向核实】。
- 结论：热带海峡场景需要的"S2 底图 + 植被/沙滩/岩石/沥青 splat + 逐层法线平滑度 + 高度混合"，**免费 Terrain Lit 全部覆盖**（6 层 S2+5 类 splat 远在 8 层限内）。

### 1.2 MicroSplat 免费核心不买 HDRP 适配包能否工作？——不能【事实】

来源：Asset Store 96478 页面内嵌 JSON 描述原文（curl 直抓，2026-09-29）。

- 核心包（MicroSplat，96478，FREE，v3.9.49，2025-12-08 更新）描述逐字：
  - "Support for URP/HDRP **with purchase of the correct adapter modules**"
  - "**HDRP/URP support sold separately**: HDRP2019, HDRP2020, HDRP2021, HDRP2022, HDRP Unity 6.0, Unity 6.3 …"
- 即：免费核心只覆盖 **Built-in 管线**；HDRP 下一律粉红，官方无免费旁路。论坛/主页声明与商店描述一致（microsplat 官网本域直抓被反爬，以商店页作者维护的描述为一手）。
- **适配包 SKU 现状**（重要更正）：
  - MicroSplat - HDRP for Unity 6（**280884**，清单 A7 所记）：$20，原始 Unity 版本 **6000.0.23f1**，v1.04（2025-02-08）——对 6000.3.24 是错版本。
  - MicroSplat - HDRP for Unity 6.3（**344008**）：$20，首次发布 2025-11-08，描述原文 "Unity's new Scriptable Render Pipeline (SRP) requires a full rewrite of all shaders for each version of each SRP. This module **adds support for targeting the High Definition Render Pipeline shipping with Unity 6.3**"，兼容版本列表 **6000.3.0**。【事实】
  - → **本项目（6000.3.24f1）正确 SKU = 344008**，procurement-checklist 表A A7 应更正。真要买，$20 一个包即得完整 MicroSplat 基础功能（模块另购 $20/个）。

### 1.3 MapMagic 2 现状复核——L4 结论不变【事实】

来源：Asset Store 165180 页面直抓（2026-09-29）。

- MapMagic 2（165180）LD price **$0.00**（免费核心成立）。
- 页面渲染管线兼容矩阵**仍是单行 "2022.3.62f1：Built-in/URP/HDRP Compatible"**——无 Unity 6 行，与 verify.md L4（2026-09-24 核）一致，**两周内无变化**。
- 旁证：商店评论区近期有 "TerrainPreviewURP has issues running in Unity 6000" 的用户反馈（检索摘要转述，评论页 JS 渲染未直抓）【中转一手】。
- GitLab release 列表 API 403，最新 release 日期**未核**。
- 结论：MM2 免费核心在 Unity 6 属"无官方声明+社区报障"，与 2026-09-24 判定一致，不作为管线组件。

### 1.4 自写 Shader Graph terrain splat 工作量量级【事实+推断】

- **官方原生路线（显著降低成本）**：Unity Manual（Unity 6.6）"Render Terrain with Shader Graph"：右键 `Create > Shader Graph > URP or HDRP > Terrain Lit Shader Graph`，文档明示可做 "high quality tile repetition break-up solutions, detail mapping … parallax mapping, auto materials, tri-planar projection"【事实，§4.5】。Shader Graph 提供 Terrain Texture 节点直读 Terrain Layer（索引须编译期常量）【事实，§4.6】。
- **层数边界**：Unity 员工 Remy_Unity 在官方论坛逐字回复："**HDRP supports up to 8 layers, in a single pass**, and you have to make your own graph with terrain texture index from 0 to 7."（URP 则是 4 层/pass 叠 pass）【事实，§4.7】。
- 工作量量级【推断】：官方 target + Terrain 节点已管掉 pass/instancing/splat 权重，剩余工作 = 逐层法线/平滑度接线 + 反平铺（高度噪声/rotated UV）+ 三平面（陡坡）。对熟悉 Shader Graph 的工程背景开发者，**基础 splat 版 1-2 人日、加反平铺+三平面 3-5 人日**；社区有官方 Terrain Samples 起步模板。风险点：每加一个采样网络都要复制到 8 个索引上，图会大；无 MicroSplat 式"逐层 GUI 微调+自动 PBR 生成"，调参靠手改。

### 1.5 观感上限对比（热带海峡，无雪/湿度需求）

- MicroSplat 对本项目真正有用的增量 = 反平铺模块（$20）、细则混合；雪/湿度/trax/glitter 等模块用不上（前报 §3.3 已判植被/雪不是主角）。
- 免费路线（Terrain Lit + 自写 SG）能到：S2 底图 + 高度混合 splat + 逐层法线/平滑度 + 手写反平铺三平面——**远景与中景观感差异很小；差异集中在近景地面特写的平铺抑制精细度**【推断】。
- 反过来看，付费版其实只要 **$20（344008）** 就能拿回 MicroSplat 全部基础功能，比自写 3-5 人日更便宜——若近景主岛特写重要，$20 是本项目性价比最高的付费项，建议保留 A7 但改 SKU 并压缩为"只买 6.3 适配包、模块按需后补"。

---

## 2. Amplify Impostors（A8）的免费替代

### 2.1 官方 billboard 机制在 HDRP 不可用【事实】

- BillboardRenderer/BillboardAsset 是 Unity 内置远景 billboard 机制，但其内置 billboard 着色器不是 SRP 系着色器；2023-03 官方论坛一手帖逐字："Unity says here that the Billboard Renderer component works in URP (**I've tried, it doesn't**), and in HDRP **'only with VFX graph'**. One problem is I can't find any resources on how to implement the Billboard Renderer with the VFX graph"【事实，§4.9】。
- 现行 Unity 6.6 手册的 Billboard Renderer/Billboard asset 页已**不再标注任何管线支持声明**（逐字核对无 HDRP/URP/VFX 字样），即官方文档层面处于"未声明支持"状态【事实-反向核实，§4.10/§4.11】。
- 同帖另一用户："None of the solutions I have found work properly in HDRP (though some work in URP)"——网上现成 Shader Graph billboard 方案在 HDRP 大多失效【一手】。

### 2.2 手搓 billboard LOD（LOD Group + 朝向面片）可行性/工作量/坑【一手+推断】

同帖社区共识与坑：
- 可行路径："you should be able to write a **simple shader that orients the plane towards the camera** (as billboards do)"——Y 轴朝向相机的顶点变换，HDRP 下用 Shader Graph 或 Amplitude/HLSL 自写可成【一手】。
- 已知坑（一手帖+通用工程判断）：
  1. **Static batching 会打断顶点级 billboard 旋转**（帖中原话："note that this shader does not work for static-batched objects"）——远景船群若被静态合批即失效【事实】；
  2. 烘焙光照 vs 本项目动态太阳/天气档（00-REPORT §3.4 三档大气）——billboard 是烘焙快照，时辰变化会露馅；剪影距离（>3-5km）下可接受【推断】；
  3. 阴影：需 alpha-clipped depth 才能投影，HDRP 需单独调 Shadow pass【推断】；
  4. LOD Group 渐隐/切换 pop 需自调【推断】。
- 工作量【推断】：编辑器脚本多角度烘 atlas（Camera+RenderTexture）+ 朝向 shader + LOD Group 挂接 ≈ **2-4 人日**（含踩坑）；对"锚地几十艘远景剪影"（00-REPORT §3.3）这是上限方案，不是首选。

### 2.3 免费工具逐条核（结论：Asset Store 无实质免费档）

| 工具 | 状态【事实】 | 判定 |
|---|---|---|
| Amplify Impostors（119877） | 现价 **$30.00**（LD 直抓 2026-09-29）；兼容矩阵最高 **2022.3.22f1**，**无 Unity 6 行**；社区确认 Unity 6 需手动解包对应 HDRP shader 包（912169 帖："install the latest ASE + Amplify Imposters … unpack an additional package for the correct shaders, e.g. for HDRP 14"） | 付费档基线；买前需在 6000.3.24 实测 |
| Mirage – Versatile Impostor System（261094） | ~$60（检索转述，页面未直抓【中转】），声明 URP+HDRP | 付费 |
| xraxra/IMP（开源 billboard 烘焙） | GitHub 仓库 **404**（2026-09-29 实测）——912169 帖曾推荐 "does not work in HDRP, but since it's open source, you could convert it"，现无法核许可 | 失效 |
| luezpz/URPIMP（开源） | 仓库存在但 **archived（2022-10）**、限 URP、**无 LICENSE 文件** | 不可用 |
| Unity Asset Transformer SDK（原 Pixyz） | 官方文档确认支持八面体 impostor、HDRP 支持（"In HDRP, depth is also offseted so intersections with other objects will be correct"）；但为付费产品：Toolkit **$1,350/座/年**，SDK 联系销售 | 付费，否决 |
| Asset Store 免费档 impostor 工具 | 两轮检索未命中任何免费 HDRP 可用 impostor 烘焙工具 | 无 |

### 2.4 结论：远景剪影档免费路线够用【推断】

- 本项目远景剪影的真实需求是"锚地几十艘+地平线船影"（§3.3），非树林级数量。**优先用免费低模网格直接作最远 LOD**（前报已列 Kenney Watercraft Kit 30 艘 CC0）+ 距离剔除，0 新增工时；billboard 手搓（2-4 人日）仅当 Profiler 证明网格 LOD 仍是瓶颈再做。
- $30 的 Amplify 若促销可买，但其兼容矩阵无 Unity 6 声明是新增风险（2026-09-29 实测），下单前必须在 6000.3.24 实测——这正是表A"下单前复核"列该做的事。

---

## 3. FCB 主角船 $2-8K 外包（A9）的免费替代

### 3.1 Sketchfab CC0/CC-BY 候选【事实，API 检索 2026-09-29】

**CC0 巡逻艇 = 0**：对 "patrol boat / navy boat / police boat / military boat" 四组可下载检索做 CC 许可过滤，CC-BY 数十命中、**CC0 零命中**。纯 CC0 路线不存在，免费现成路线只能是 CC-BY（署名义务）。

CC-BY 可下载候选（按对位度排序，作者/面数经模型 API 核实）：

| 模型 | 作者 | 许可 | 面数 | 对位评估 |
|---|---|---|---|---|
| **Lowpoly USS Hurricane (PC-3)** | S1Priv | CC Attribution | 14,484 | **Cyclone 级巡逻舰（55m/331t）**——与 45m FCB 同级巡逻舰定位，剪影最对位；低模，适合作中景/基准网格 |
| Patrol Boat PBR MK2 | SavyTheCreator | CC Attribution | 24,522 | PBR 材质齐全但为越战内河 PBR（≈ vaz 7m 级），小艇参照 |
| CB-90 Fast Class Assault Craft | DIGITAL01 | CC Attribution | 260,406 | 现代快速突击艇（15.9m），气质最接近 FCB；面数超标需抽壳/减面 |
| Visby Corvette | Vavtrudner | CC Attribution | 150,005 | 72m 隐身护卫舰，偏大；作港内背景舰 |
| Type 22 Houbei-class missile boat | — | CC Attribution | 36,194 | 22 型导弹艇，吨位对位尚可，涂装需换 |

- NC（非商业）系列（如 Elco 80ft PT，CC-BY-NC）一律排除——不可商用。

### 3.2 许可条款原文（引用与 AI 条款）【事实，CC 法律文本 2026-09-29 抓取】

- **CC BY 4.0 署名义务**（§3a(1)）：Share（含修改后）须保留①创作者身份标识（"in any reasonable manner requested by the Licensor"）②版权声明 ③本许可声明 ④免责声明，并注明修改；**可商用**：§2a(1) 授予 "worldwide, royalty-free … license to reproduce and Share … and produce, reproduce, and Share Adapted Material"，无目的限制。
- **CC BY 4.0 §2b 禁止附加额外限制**（原文）："You may not offer or impose **any additional or different terms or conditions** on, or apply any Effective Technological Measures to, the Licensed Material if doing so restricts exercise of the Licensed Rights by any recipient of the Licensed Material."
- **CC0**（§2 Waiver，原文）："Affirmer hereby overtly, fully, permanently, irrevocably and unconditionally waives, abandons, and surrenders all of Affirmer's Copyright and Related Rights … **for any purpose whatsoever, including without limitation commercial, advertising or promotional purposes**"——无署名义务（本项目 CC0 候选为 0，仅作条款备查）。
- **AI 条款**：Sketchfab 2023-03 起 NoAI 标签——官方博客声明 "The NoAI tag remains contractually enforceable on **Standard-licensed** models once they have been downloaded from Sketchfab"（经检索摘要转述，官方博客页反爬未直抓原文【中转一手】）。**争议点**：NoAI 对 CC 许可模型的效力缺乏明确依据——CC 法条 §2b 明文禁止 licensor 附加额外限制；业界实践（如 TexVerse 数据集）是直接过滤 NoAI 模型自证清白。**本项目的稳妥操作**：只取 CC 许可模型、只作建模/参考用途、不对任何模型跑 AI 生成/重贴图（与 CGTrader $58 占位的 no-AI 条款同口径），即可完全规避争议。模型页面 NoAI 标记逐个核验因 Sketchfab 反爬**未核**。
- 落地动作：入选模型逐条写进 `sango/Docs/asset-registry.md`（作者+许可+来源 URL），署名文本进仿真器"关于"页（与 ODbL/SODL 署名同一容器，00-REPORT §2.1 合规动作）。

### 3.3 Blender 自建工时量级【一手锚点+推断】

社区先例锚点：
- Unity Discussions 工时拆解帖（一手）：简单道具 "Modeling prop 3-6, up to 8 … UVs 1-2, up to 3-4 … Texture 3-6, up to 8 … Testing 1-2 hours, Revisions 3-6"（人时）——单个简单道具全流程 11-28h。
- BlenderArtists USS Monitor（2020，一手）："It took me **a few months** to create the model"——爱好者做高细度历史战舰+场景，数月。
- Bismarck 建模帖：6 周（检索转述【中转】）。
- 交叉验证：前报外包定价 $2-8K ÷ 东南亚时薪 $20-60/h ≈ **100-400 专业工时**（10-30 万面、4×4K、2-4 周），两条线一致。

**自建量级判定【推断】**：45m FCB 游戏级（hero 近景档 8-15 万 tri + 3 级 LOD + 4K 贴图 + 细构件可拆）对非美术背景的工程开发者 = **40-120+ 工时（兼职 3-8 周）**，且一次成品率低；若降级为"中景档 3-5 万 tri + 2K"可压到 **20-40 工时**。用 5 张正交图仅能作参考图集（前报 §1.1 已定，不重查）；AI 3D 生成边界沿用 00-REPORT §1.3（概念档可用、最终资产不可用）。

### 3.4 三路线性价比排序（结论）

1. **保留 $58 CGTrader 占位为主线（性价比最优）**——已在前报 §1.1 定案；外包询价按表A A9 推迟至项目定型（船型细节有验收标准、且"船-水耦合运动感"P0 工艺先在占位船上跑通）再启动。省 $2-8K 的同时不阻塞任何当前里程碑。
2. **CC-BY 基准网格混合路线（第二优先，$0）**——取 Lowpoly USS Hurricane PC-3（同级巡逻舰）为 hull 基准，Blender 只做换装级细化（护舷/桅杆/驾驶台）+ HDRP 材质重建；署名成本≈0（登记表+关于页）；比纯自建省掉大块 hull 建模工时，比占位 $58 省 $58 但多 3-5 人日【推断】。适合"项目初期未定型、但 $58 占位到货前需要并行验证"的窗口。
3. **纯 Blender 自建（推迟）**——工时上限最高、成品率风险最大；仅在 1、2 都无法满足近景特写时启动，且届时更可能直接触发外包而非自建。

---

## 4. 决策表

| 付费项（前报口径） | 2026-09-29 修订建议 | 理由（证据节） | 残余风险 |
|---|---|---|---|
| A7 MicroSplat 280884 + 1-2 模块 ≈$40-60 | **改 SKU**：只买 344008（HDRP for Unity 6.3，$20），模块后补；若坚持免费：Terrain Lit + 自写 SG splat（3-5 人日） | §1.2/§1.4/§1.5 | 344008 首发仅 2025-11，成熟度待 spike 验证 |
| A8 Amplify Impostors $30-33 | **不立即买**；先用免费低模远景 LOD（Kenney CC0），Profiler 证明瓶颈再议；买前必测 6000.3.24 | §2.1-2.4 | Amplify 兼容矩阵无 Unity 6 行（今日实测） |
| A9 FCB 外包 $2-8K | **推迟**；主线=$58 占位；窗口期并行 CC-BY 基准网格路线（USS Hurricane PC-3，登记署名） | §3.1-3.4 | Sketchfab 页面级 NoAI 标记未逐个核（反爬）；已用"不跑 AI"策略规避 |
| 表A 文档动作 | A7 行 URL/价格更正为 344008/$20；A8 补记"$30（2026-09-29 LD 抓取）/兼容矩阵无 6.x 声明" | §1.2/§2.3 | — |

---

## 5. 引用（一手来源）

1. HDRP 17.3 Terrain Lit material（8 层上限）：https://docs.unity3d.com/Packages/com.unity.render-pipelines.high-definition@17.3/manual/terrain-lit-material.html
2. HDRP 17.3 Terrain Lit Material Inspector reference（height-based blend / per-pixel normal / 属性清单反向核实）：https://docs.unity3d.com/Packages/com.unity.render-pipelines.high-definition@17.3/manual/terrain-lit-material-inspector-reference.html
3. Unity 6.3 Manual Terrain Layers（diffuse alpha=smoothness、首层自动为 base layer）：https://docs.unity3d.com/6000.3/Documentation/Manual/class-TerrainLayer.html
4. MicroSplat 核心（96478）页面描述原文 "HDRP/URP support sold separately"（页面内嵌 JSON，curl 直抓）：https://assetstore.unity.com/packages/tools/terrain/microsplat-96478
5. MicroSplat - HDRP for Unity 6.3（344008，$20，6000.3.0）：https://assetstore.unity.com/packages/tools/terrain/microsplat-hdrp-for-unity-6-3-344008
6. MicroSplat - HDRP for Unity 6（280884，$20，6000.0.23）：https://assetstore.unity.com/packages/tools/terrain/microsplat-hdrp-for-unity-6-280884
7. MapMagic 2（165180，$0.00，兼容矩阵 2022.3.62f1）：https://assetstore.unity.com/packages/tools/terrain/mapmagic-2-165180
8. Unity Manual Render Terrain with Shader Graph（HDRP TerrainLit Shader Graph target）：https://docs.unity3d.com/Manual/terrain-shader-graph.html
9. Shader Graph Terrain Texture Node（编译期索引、限 TerrainLit SG）：https://docs.unity3d.com/Packages/com.unity.shadergraph@17.4/manual/Terrain-Texture-Node.html
10. Unity Discussions「Shader Graph Terrain Lit with more than 4 layers」（Remy_Unity："HDRP supports up to 8 layers, in a single pass"）：https://discussions.unity.com/t/help-needed-shader-graph-terrain-lit-with-more-than-4-layers/1695486
11. Unity Discussions「Ideas for implementing Billboards/Imposters in HDRP」（BillboardRenderer HDRP 现状、IMP/Amplify 社区评价、static batching 坑）：https://discussions.unity.com/t/ideas-for-implementing-billboards-imposters-in-hdrp/912169
12. Unity 6.6 Manual Billboard Renderer（无 SRP 支持声明，反向核实）：https://docs.unity3d.com/Manual/class-BillboardRenderer.html
13. Amplify Impostors（119877，$30.00 LD 抓取，兼容矩阵最高 2022.3.22f1）：https://assetstore.unity.com/packages/tools/utilities/amplify-impostors-119877
14. Asset Transformer SDK Impostors（HDRP depth offset 支持）：https://docs.unity3d.com/Packages/com.unity.pixyz.unity-sdk@4.0/manual/features/impostors.html ；定价 https://unity.com/products/unity-asset-transformer
15. Sketchfab 检索（patrol boat 等 4 组，CC0=0、CC-BY 命中清单与作者）：https://api.sketchfab.com/v3/search?type=models&q=patrol+boat&downloadable=true
16. CC BY 4.0 法律文本（§2a 授权、§2b 禁附加限制、§3a 署名）：https://creativecommons.org/licenses/by/4.0/legalcode.txt
17. CC0 1.0 法律文本（§2 Waiver "for any purpose whatsoever … commercial"）：https://creativecommons.org/publicdomain/zero/1.0/legalcode.txt
18. Sketchfab 官方博客 NoAI 条款（Standard license 层面；经检索摘要转述，原文页反爬）：https://sketchfab.com/blogs/community/restricting-generative-ai-use-of-free-models
19. Unity Discussions「Project Time Estimation」（道具人时拆解）：https://discussions.unity.com/t/project-time-estimation/633021
20. BlenderArtists USS Monitor（"a few months"）：https://blenderartists.org（帖题 USS Monitor – Finished Projects，2020-03）
21. luezpz/URPIMP（archived 2022-10、无 LICENSE）：https://github.com/luezpz/URPIMP
22. xraxra/IMP（GitHub 404，2026-09-29 实测）：https://github.com/xraxra/IMP

**未核项**：microsplat 官网本域（TLS/反爬失败，以商店页描述为一手）；MapMagic 2 最新 release 日期（GitLab API 403）；Sketchfab 各模型页 NoAI 标记现状（反爬）；Mirage 标价（检索转述）；NoAI 博客原文逐字（反爬，摘要转述）。
