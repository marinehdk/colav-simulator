# 采购比价与待证清单（procurement-checklist）

- 基准：docs/research/2026-09-24-scene-ship-fidelity/00-REPORT.md §5/§6、§1.2；verify.md L 系；定价出处 dive_01 / resolve_01。
- 使用规则：表A **"下单前复核"列留空**——下单当日人工打开发售页核对现价与许可后填写；表B 逐条复核后把结论回写本文件，资产到货后同步登记 `sango/Docs/asset-registry.md`。
- 所有价格为访问日 2026-09-24 页面标价（USD）。

## ★免费替代决策表（2026-09-29 调研后，项目初期未定型）

> **用户裁决 2026-09-29：路线 A = 全免费（$0）。** MicroSplat 344008 与 Amplify 均不购买；地形贴图走 HDRP 原生 Terrain Lit；FCB 走 CC-BY 换装占位，hero 档推迟至项目定型。付费表 A 降级为"若免费路线某类观感不过关再回头买"的备选。人闸清单见 [account-guide.md](account-guide.md)。

调研档案：[free-alternatives-ships.md](../2026-09-29-free-alternatives-ships.md)（船模 25 候选一手核证）｜[free-alternatives-tools-hero.md](../2026-09-29-free-alternatives-tools-hero.md)（工具+主角路线）。**采购额可从 ≈$250-300 压到 $0-20**，代价 ≈3-5 净增人日 + CC-BY 署名义务（登记表制度覆盖）。

| 表A 项 | 原付费 | 免费替代（档位） | 建议 |
|---|---|---|---|
| A1 渔船 | $4.99 | JasperTobias「Trawler」CC-BY 5.3k（中远，剪影正确） | **走免费** |
| A2 集装箱船 | $45.00 | RM02「Container Ship」CC-BY 189k（中景；付费款同样 231k 超标需减面） | **走免费** |
| A3 油轮 | $24.90 | ArtBlender「Tanker」193k +「LNG」90k 成对（中远） | **走免费** |
| A4 拖轮 | $30.00 | davidbroutian「Rastar 3200」CC-BY 47k（中景；本类候选最薄） | **走免费** |
| A5 杂货船 | $17.99 | hungry_drifter「Cargo ship」CC-BY 73k（中景） | **走免费** |
| A6 FCB 占位 | $58.00 | dannzjs「Type 22 Houbei」17.8k 换白壳绿装 + S1Priv「USS Hurricane PC-3」14.5k（中景/剪影分层） | **暂缓购买**——CC-BY 分层占位先行，换装后中景不过关再买 |
| A7 MicroSplat | ≈$20-60 | HDRP 原生 Terrain Lit（8 层/逐层法线/高度混合，17.3 官方文档核实）+ 可选自写 Shader Graph 3-5 人日 | 若买：**只买 344008**（HDRP for Unity 6.3，$20）——280884 是 6.0 错版；省下的 $180 足够覆盖 |
| A8 Amplify Impostors | $33 | Kenney CC0 低模远景网格 LOD（零工时）；手搓 billboard 2-4 人日仅 Profiler 证明瓶颈后 | **不买**（Amplify 兼容矩阵无 Unity 6 行，买前必测） |
| A9 FCB 外包 | $2,000-8,000 | 无 hero 档免费替代（CC0 巡逻艇全站=0） | **推迟至项目定型**；窗口期可用 PC-3 CC-BY 基准网格混合路线 |

要点：① 免费现代船**全部 CC-BY**（须署名，无 AI 限制条款——比 CGTrader 付费件的 no-AI 反而更宽）；② hero 近景档免费为零，双轨制轨道 B 不动，仅推迟；③ 地理数据侧（GLO-30/GEBCO/DEMNAS/S2）本就全免费，精度不受本决策影响；④ 来源链存疑件（"not mine/ripped"）已列入调研档案 §6 禁入清单。

## 表A — 拟购资产（付费）

| # | 资产/产品 | 商店/来源 URL | 价格（2026-09-24 核价） | 访问日期 | 下单前复核 | 用途 |
|---|---|---|---|---|---|---|
| A1 | Pingo Fishing Boat Trawler（MARTELO 3D） | Unity Asset Store：https://assetstore.unity.com/packages/3d/vehicles/sea/pingo-fishing-boat-trawler-140261 | $4.99 | 2026-09-24 | | 交通船流—渔船 |
| A2 | Cargo Ship Container Ship（LittleChild Games；231,615 tris / 4K） | Unity Asset Store：https://assetstore.unity.com/packages/3d/vehicles/sea/cargo-ship-container-ship-280480 | $45.00 | 2026-09-24 | | 交通船流—集装箱船。注意：面数超 hero 档（§6 风险2/C3），验收先查面数，需减面或只作中景 |
| A3 | Tanker (ship) HDRP（Minod studio） | Unity Asset Store：https://assetstore.unity.com/packages/3d/vehicles/sea/tanker-ship-hdrp-226846 | $24.90 | 2026-09-24 | | 交通船流—油轮 |
| A4 | PA Tug Boat（Popup Asylum） | Unity Asset Store：https://assetstore.unity.com/packages/3d/vehicles/sea/pa-tug-boat-162168 | $30.00 | 2026-09-24 | | 交通船流—拖轮 |
| A5 | Container Ships | Fab：https://www.fab.com/listings/d15bb4d9-e292-4bc0-a058-14aee645f69e | $17.99 | 2026-09-24 | | 交通船流—杂货。注意：Fab 反爬强，价格档/许可细节需人工核对页面（dive_01） |
| A6 | Fast Patrol Boat Ship Vessel 45M（FBX+PBR） | CGTrader：https://www.cgtrader.com/3d-models/military/military-vehicle/fast-patrol-vessel-with-weapon | $58.00 | 2026-09-24 | | FCB 占位（轨道A）。注意：页面标 "License (no AI)"——不得对其 AI 重贴图/重拓扑 |
| A7 | MicroSplat 核心（免费，96478）+ HDRP for Unity 6 适配包（~~280884~~ **更正：本项目 6000.3.24 应买 344008**，$20，2026-09-29 核）+ 1–2 模块 | Unity Asset Store：核心 https://assetstore.unity.com/packages/tools/terrain/microsplat-96478 ；6.3 适配包 https://assetstore.unity.com/packages/tools/terrain/microsplat-hdrp-for-unity-6-3-344008 ；模块样本 96480 / 96484；发行商页 https://assetstore.unity.com/publishers/25047 | ≈$20–60（核心 FREE 但 **HDRP 下完全不可用**——描述原文 "HDRP/URP support sold separately"；模块实测 $20/个；Ultimate Bundle $99.50） | 2026-09-24（SKU 更正 09-29） | | 地形贴图提质。免费替代=HDRP 原生 Terrain Lit（见顶部决策表） |
| A8 | Amplify Impostors | Unity Asset Store：https://assetstore.unity.com/packages/tools/utilities/amplify-impostors-119877 | 促销 **$33** / 原价 $66；**2026-09-29 LD 实测 $30.00，兼容矩阵最高 2022.3.22 无 Unity 6 行** | 2026-09-24 | | 远景 impostor。免费替代=低模网格远景 LOD（见顶部决策表） |
| A9 | FCB 外包精模（轨道B） | 2–3 家询价，见 [inquiry-letter-fcb-outsource.md](inquiry-letter-fcb-outsource.md) | $2,000–8,000（自由职业档）/ 上限 $15,000（工作室档） | 2026-09-24（定价锚） | | 最终主角船（45m FCB） |

小计（不含 A9 与免费注册）：00-REPORT §5 原文为 **≈$250–300**。逐项加总为 $233.88–273.88（$122.88 配角包 + $58 + $20–60 + $33），与报告约数存在 ±$20 口径差——以逐项现价复核结果为准。

配角包（A1–A5）合计 ≈$123（00-REPORT §1.2：4.99 + 45.00 + 24.90 + 30.00 + 17.99 = $122.88）。

## 表B — 待证项（逐条复核动作）

| 编号 | 事项 | 档案现状 | 复核动作 |
|---|---|---|---|
| B-L1 | Megascans/Fab 免费口径 | 部分消解（verify.md L1）：约 1,500 资产免费 + Megaplants 全免费，经 Fab、Fab Standard License；"全库免费"旧说法不成立；**License 全文待取** | 取得 Fab Standard License 全文并归档至本目录；拟用免费资产逐个登记入 asset-registry 后再使用 |
| B-L2 | dive_05 采购清单价格未核验 | 待办（verify.md L2）：抓取通道故障，价格列多数未核 | 表A逐条人工比价并填"下单前复核"列——本表A即该 pass 的载体 |
| B-L6 | Maxar 商业影像价格量级 | 待证（verify.md L6）：每 km² 数十美元 + 起订面积（推断）；报价页 403 | 经 Maxar 销售渠道索取正式报价；取得前不纳入采购预算 |
| B-L8 | FABDEM 许可全文 / BIG DEMNAS 门户下载协议原文 / 印尼 ENC 对外国开发商政策 / MicroSplat 其余模块单价 | 待证（verify.md L8）：模块抽样 $20/个、Bundle $99.50 | 逐项取得原文归档至本目录；MicroSplat 模块单价在发售页核对后回填表A A7 |
| B-R1 | 许可残余风险（00-REPORT §6 风险1） | Fab Standard License 全文、BIG 门户下载协议原文、FABDEM 许可、Maxar 报价——采购/使用前人工确认 | 与 B-L1 / B-L6 / B-L8 合并执行；数据红线三条款见下节 |
| B-R4 | 价格时效（00-REPORT §6 风险4） | 资产商店促销价波动：Amplify $30/$33 残留差异、Crest 划线价未取得 | 下单当日核对现价并截图留档；Crest 若纳入 P2：Water 4 HDRP $100（164158）/ Water 5 $120（268614），引用以 resolve_01 为基准 |

## 数据红线（重申，对全表约束）

以下三条均**可在线查看，但一律不得提取为引擎资产**（不下载缓存、不烘焙进场景/网格/贴图/地形）——来源 00-REPORT §2.1（dive_03 条款原文）：

1. **Esri World Imagery** —— 条款限定"数据采集/编辑底图"用途；
2. **Google Photorealistic 3D Tiles** —— Map Tiles 政策明禁 "Geodata extraction" 与 "Offline uses"，叠加物不得派生；经 Cesium ion 的同一条款还将 vessel navigations 列入 High Risk；
3. **MPA 新加坡 ENC（S-57）** —— 绑定 type-approved ECDIS 使用；视觉原型用 GEBCO + BATNAS 即可。

## 账号注册清单（全部 $0）

| 账号/门户 | 用途 | 备注 |
|---|---|---|
| BIG（印尼）— DEMNAS / BATNAS | 印尼侧 ≈8m 高程 + 6″ 水深（Batam/Bintan/Riau） | 需注册；门户下载协议原文待归档（B-L8/B-R1） |
| Copernicus Data Space | GLO-30 高程（新加坡侧）+ Sentinel-2 L2A 贴图 | "Full, Free & Open" |
| GEBCO | GEBCO_2025 水深、陆海合并 | 公有领域，免费 |
| OneMap API key | 新加坡官方矢量补充 | SODL 可商用，须按模板署名 |
| Fab | Megascans 约 1,500 免费资产 + Megaplants 全免费 | Standard License 全文待取（B-L1） |
