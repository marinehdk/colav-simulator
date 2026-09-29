# 付费船模的免费/开源替代方案调研 — free-alternatives-ships

- 日期：2026-09-29 ｜ 服务对象：Colav-Simulator 阶段1（Unity 6.3 LTS + HDRP）
- 上游档案：[00-REPORT.md](2026-09-24-scene-ship-fidelity/00-REPORT.md) §1 船模双轨制、§3.1 可信感结论；[procurement-checklist.md](2026-09-24-scene-ship-fidelity/procurement-checklist.md) 表A（A1–A6 付费船模）
- 研究问题：表A 六类付费船模（≈$123 配角包 + $58 FCB 占位）各自有没有免费/开源替代？增量在哪、边界在哪？

## 方法与证据等级

- **发现**：Sketchfab Data API v3 `/v3/search`（downloadable=true）逐类检索；poly.pizza 站内搜索；quaternius.com；OpenGameArt 高级搜索（3D 类）。
- **逐条一手核实**：每个入选候选调用 `/v3/models/{uid}` 取**许可原文要点**（requirements 字段逐字："Author must be credited. Commercial use is allowed."，CC 系许可均无 AI 限制条款）+ 官方面数（faceCount）；并下载官方缩略图**逐张目检**造型/涂装/风格（共 33 张）。poly.pizza/Quaternius/OpenGameArt/UAS 逐页抓取原文。
- **诚实原则执行**：查不到的字段标"未核"；反爬源（CGTrader/Free3D/TurboSquid/Fab/itch.io 免费区）如实记录为未能一手核验；上传者自述"not mine / ripped"的模型单独标**来源链风险**，不入选推荐。
- 标注：【核实】=API/页面原文；【目检】=缩略图判读；【推断】=工程判断。

---

## 0. 结论速览

| 表A 付费项 | 免费最佳替代 | 档位 | 结论 |
|---|---|---|---|
| A1 渔船 $4.99 | Sketchfab「Trawler」by JasperTobias（CC-BY，5.3k 面） | 中远 | **可全替代** |
| A2 集装箱船 $45 | Sketchfab「Container Ship」by RM02（CC-BY，189k 面，满载集装箱） | 中景 | **可替代**（需减面/限中景） |
| A5 杂货 $17.99 | Sketchfab「Cargo ship」by hungry_drifter（CC-BY，73k 面，红壳吊机杂货船） | 中景 | **可替代** |
| A3 油轮 $24.90 | Sketchfab「Tanker Ship」Suez-Max by ArtBlender（CC-BY，193k）+「LNG Ship」90k 同作者成对 | 中远 | **可替代**（同款风格两艘） |
| A4 拖轮 $30 | Sketchfab「Rastar 3200 tugboat」by davidbroutian（CC-BY，47k，作者声明 UE/Unity 可用） | 中景 | **可替代**（候选薄） |
| A6 FCB $58 占位 | Sketchfab「Type 22 missile boat」17.8k +「Lowpoly USS Hurricane (PC-3)」14.5k（均 CC-BY） | 中景/剪影 | **部分替代**：远景+中景占位可覆盖，近景 hero 无解 |
| 配角全套 CC0 | Kenney Watercraft（已有）+ Quaternius Ships Pack（OGA CC0 副本）+ Alstra「Boats - PolyPack」（UAS 免费，HDRP 兼容） | 远景剪影 | **剪影档已有免费底座** |

**一句话边界**：免费替代的真实增量=中精度中景档（本项目此前只有 Kenney 剪影档）；hero 近景档与 CC0（免署名）现代船**双双为零**——对标 00-REPORT §3.1 H3 结论（可信感分水岭在船-水运动/参照物，非资产豪华度），配角包 $123 可省，FCB 双轨制不应动摇。

---

## 1. 总体边界（先读这个）

1. **CC0 现代船 ≈ 0**【核实】：Sketchfab 全站 downloadable+CC0 检索，"fishing boat/container ship/oil tanker/tugboat/patrol boat" 命中的全是博物馆扫描（Shetland 四桨木船、Cutty Sark 船首像、半剖船模、MV Spartan 扫描/点云），无一 game-ready 现代船。免费现代船的唯一可行许可 = **CC-BY 4.0（商用✓ + 署名义务，无 AI 限制条款）**，全部入 asset-registry 署名。
2. **hero 近景档免费不可得**【推断】：免费中最佳 FCB 类候选 14–36k 面、平板着色或需要换装，距 §1.1 验收条件（≤150k tri + 3 级 LOD + 细构件拆分 + 干净 UV）仍差一个制作流程；FCB 外包精模（$2–8K）无替代。
3. **与 H3 一致**：免费组合的观感上限靠 §3.2 工艺清单（艏波/号灯/湿感）与尺度参照物拉平，不靠资产本身——Sea Power/Aeolus 先例已证。
4. **来源链风险类**：若干高面数好模型（Armidale 级 133k、Sea Axe 203k、42manako 系列舰艇）上传者自述 "not mine" 或 "Ripped from Cold Waters"——CC-BY 徽章与真实权利人不符，**不得入工程**，仅作记录（§6）。
5. HDRP 转换代价（对全部 Sketchfab 候选，【推断】）：下载件为 glTF(+OBJ/FBX/Blend 源文件，逐模型未核)；glTF PBR→HDRP Lit 材质重接连 0.5–1 人日/船，flat-color 低模 ≈0.5 人日；与 00-REPORT §1.2 已核的 Built-in 资产 1–2 天/船同量级或更低。

---

## 2. 逐类候选

评级口径：**hero 近景档**（可当主角近景）/ **中景档**（50–500m 可信）/ **剪影档**（远距离轮廓即可）。面数为 Sketchfab API faceCount【核实】；PBR 有无据描述原文+缩略图【目检】，未解包资产。

### 2.1 渔船（对标 A1 Pingo Fishing Boat Trawler $4.99）

| 模型 / 作者 | URL | 许可要点【核实】 | 面数 | 贴图【目检】 | 档位 | 备注 |
|---|---|---|---|---|---|---|
| **Trawler** / JasperTobias | https://sketchfab.com/3d-models/trawler-421f3239115c44539686fcb62835f115 | CC-BY 4.0：商用✓，须署名，无 AI 条款 | 5,253 | flat 低模，吊架/桅杆齐全，剪影正确 | 剪影～中远 | **首推**。Blender 2.9 制作，为游戏项目而做 |
| Fishing Boat / RafaelBR873D | https://sketchfab.com/3d-models/fishing-boat-6e33005fba3542a2aa61e187321d465e | 同上 CC-BY | 26,682 | 蓝/白/橙低模，起重臂+渔获，干净 | 中远 | Sketchfab Weekly 挑战作品 |
| Fishing boat（老旧木拖网船）/（见页面） | https://sketchfab.com/3d-models/fishing-boat-7ef191da28bc4428b8ede2f62562f1ac | 同上 CC-BY | 25,402 | 写实做旧木纹+锈，锈迹污渍可直接喂 §3.2 湿感工艺 | 中景 | 风格偏写旧，作渔村/旧船 |
| **Fishing Trawler 44.2m** / agt14032013 | https://sketchfab.com/3d-models/fishing-trawler-442m-856589e1b5ec4099a0d3f4ca95da1901 | 同上 CC-BY | 218,198 | CAD 级干净现代拖网船（蓝白），需减面 | 中景（免费渔船保真上限） | 同作者还有 40m/45m 版（308k/2.99M 面）；下载件 OBJ+DAE【核实 desc】 |
| Stylized fishing boat / trivial.cat | https://sketchfab.com/3d-models/stylized-fishing-boat-eb459efb50d643a2b5112806e5530bef | 同上 CC-BY | 15,209 | 手绘卡通蒸汽渔船，**轮胎护舷**（与 FCB 概念同款元素） | 剪影（卡通风） | 风格不匹配写实，备选 |

排除：Pabooklas「Fishing boat」7,244 面（目检=木制划艇）、2f894eb7（独木舟）、6692824b（帆船）——检索名不符实【目检】。

### 2.2 集装箱/杂货船 ×2（对标 A2 $45 + A5 Fab $17.99）

| 模型 / 作者 | URL | 许可要点 | 面数 | 贴图 | 档位 | 备注 |
|---|---|---|---|---|---|---|
| **Container Ship** / RM02 | https://sketchfab.com/3d-models/container-ship-aaa41cca946b4a08bc08cf692b7757be | CC-BY（同上要点） | 188,711 | 满载彩箱+黑红壳+"MRC"虚构涂装，球鼻艏正确 | 中景（对标 A2 主选） | 与付费 A2 同样超 hero 档面数，同需减面/限中景（§6 风险2 同款） |
| **Cargo ship** / hungry_drifter | https://sketchfab.com/3d-models/cargo-ship-b7c97df584824ca682d26daabf401f87 | CC-BY | 73,448 | 红壳杂货船+双吊机+舱盖，锈迹污带现成 | 中景（对标 A5 主选） | 469 like，本类口碑最高 |
| Cargo Ship 02 / agt14032013 | https://sketchfab.com/3d-models/cargo-ship-02-22135f8937194b6aba964b05e3608620 | CC-BY | 564,505 | 白壳红饰+彩箱，风格化干净 | 中远（需 LOD） | 同作者 Container Ship 02（538k）同系列 |
| A Full Container Ship / mixmamo.studio | https://sketchfab.com/3d-models/a-full-container-ship-5b69bf89f02b4cd89de6e49656f3499f | CC-BY | 112,754 | **真实品牌箱（Evergreen/OOCL/Hamburg Süd）** | 中远 | ⚠ 商标涂装——入工程前换色/换贴图【推断】 |
| Container Ship / Alex Safayan（poly.pizza） | https://poly.pizza/m/3AmDGcCu6Ll | CC-BY 3.0（页面核实） | 未核（Google Blocks 风低模） | 纯色低模 | 剪影 | GLTF/OBJ 直下 |

### 2.3 油轮（对标 A3 Tanker HDRP $24.90）

| 模型 / 作者 | URL | 许可要点 | 面数 | 贴图 | 档位 | 备注 |
|---|---|---|---|---|---|---|
| **Tanker Ship（Suez-Max 322m）** / ArtBlender | https://sketchfab.com/3d-models/tanker-ship-96ebf61af42b4062ae98a6ad848e1a25 | CC-BY；desc 原文注明全长 322m/型宽 47m，含动画 | 193,100 | 红黑壳自绘贴图【核实 desc"自绘"】 | 中远 | **首推**；尺度即新加坡海峡常见档 |
| **LNG Ship（Moss 型 305m）** / ArtBlender | https://sketchfab.com/3d-models/lng-ship-fa335b96450d4344863bbf5d912a0288 | CC-BY；"All textures were created by myself... can be used for any purpose" | 90,331 | 4 球罐+绿甲板，贴图齐全 | 中远 | 同作者成对入手，风格统一；LNG 船是海峡高频船型【推断】 |
| Oil tanker / factorydottcat | https://sketchfab.com/3d-models/oil-tanker-63339c2e2f274672a9bdcf924864ae62 | CC-BY | 710,865 | **素模无贴图**（缩略图为黏土渲染） | 几何捐赠件 | 仅当 A3 贴图工艺的自制底模 |

排除：SANKETPUSHKAR「Oil Tanker」14.7k——**目检实为铁路油罐车**（检索名误导）；Kilmuir class 76k 为 1917 年代灰壳船（年代不符）。desc 附加 "Do not resell" 与 CC-BY 并存的（SANKETPUSHKAR），按更严者执行——已排除，无影响。

### 2.4 拖轮（对标 A4 PA Tug Boat $30）

| 模型 / 作者 | URL | 许可要点 | 面数 | 贴图 | 档位 | 备注 |
|---|---|---|---|---|---|---|
| **Rastar 3200 tugboat** / davidbroutian | https://sketchfab.com/3d-models/rastar-3200-tugboat-1bbadbe4ab0a4b2599cd3f450942e6fe | CC-BY；desc 原文"textures ready for use in game engines such as Unreal Engine, Unity3D" | 46,880 | 红黑壳+黑橡胶护舷+绿玻璃驾驶室，贴图齐全【目检】 | 中景 | **首推**。RAstar-3200 级现代 ASD 港作拖轮，与 PSA 港区场景同款气质【推断】 |
| Cartoon Lowpoly Tugboat / antonmoek | https://sketchfab.com/3d-models/cartoon-lowpoly-tugboat-illustration-643b1c7643344802865726158832623d | CC-BY | 43,356 | 卡通渲染 | 剪影（卡通） | 备选 |
| Azimuth Stern Drive Tugboat (HULL ONLY) / jhervianto | https://sketchfab.com/3d-models/azimuth-stern-drive-tugboat-hull-only-ad2979c6f71343a99408f66708fd02b8 | CC-BY | 51,424 | 仅壳体 | 几何捐赠件 | 自贴图工艺用 |
| TugBoat / Some "Random" Person（poly.pizza） | https://poly.pizza/m/0C28iix4FPm | CC-BY 3.0（页面核实） | 未核 | 纯色低模 | 剪影 | GLTF/OBJ 直下 |

### 2.5 ★45m FCB 主角船（对标 A6 CGTrader $58 占位 + A9 外包 $2–8K）

| 模型 / 作者 | URL | 许可要点 | 面数 | 贴图 | 档位 | 与 45m FCB 的差距【目检+推断】 |
|---|---|---|---|---|---|---|
| **Type 22 missile boat（Houbei 级）** / dannzjs | https://sketchfab.com/3d-models/type-22-missile-boat-d90464e6ca2e4d23a7a5a9865d220945 | CC-BY | 17,762 | 现代隐身穿浪双体，蓝迷彩需换白壳绿装 | 中景（免费 FCB 首选） | 船长 42m≈45m，隐身快速剪影最接近；武器系统需删改；来源描述为百科式介绍，无"ripped"自述 |
| **Lowpoly USS Hurricane (PC-3)** / S1Priv | https://sketchfab.com/3d-models/lowpoly-uss-hurricane-pc3-9582af31655d43ddbb0d3d2af9a037eb | CC-BY | 14,484 | flat 灰壳红底，栏杆/桅杆/炮座齐全，**含动画** | 中远（任务剖面最像） | Cyclone 级巡逻艇 53m，公务巡逻任务剖面与 FCB 一致；需换装+自加轮胎护舷 |
| Patrol Boat PBR MK2 / SavyTheCreator | https://sketchfab.com/3d-models/patrol-boat-pbr-mk2-dbd87172b2934063aa93ffd0c6f85750 | CC-BY | 24,522 | PBR 贴图（深度/磨损可见），越战内河巡逻艇 | 中景小目标 | ~10m 小艇，年代/尺度不符；适合改作近岸巡逻配角或 FCB 舷外小艇 |
| CB-90 Fast Assault Craft / DIGITAL01 | https://sketchfab.com/3d-models/cb90-fast-class-assault-craft-1a674c118767487a8d0f63063be9d87c | CC-BY | 260,406 | 绿色涂装（**恰好对位绿壳涂装目标**），须减面 | 中远 | Strb90 仅 15m；高速公务艇气质对，尺度不对 |
| Fast Rescue Craft Mako 655 / stefan.lengyel1 | https://sketchfab.com/3d-models/fast-rescue-craft-mako-655-8ea6bfc85e5d43b881dec5d224583f19 | CC-BY | 30,068 | 橙色 FRC，质感好（268 like） | 中景小目标 | ~8m 救助艇；充作 FCB 随艇/救助科目配角 |
| Visby Corvette / Vavtrudner | https://sketchfab.com/3d-models/visby-corvette-06d445dc90304c598286d63f52f2ff85 | CC-BY | 150,005 | 隐身舰体，贴图较好 | 中景 | 72m 护卫舰，尺度偏大；远景军用背景 |
| 20m search and rescue boat / Nutical3D | https://sketchfab.com/3d-models/20m-search-and-rescue-boat-6d53e735521f44af82142e6292b2f340 | CC-BY（desc 要求署名提醒） | 149,440 | 橙色 flat | 中远 | SAR 科目配角 |
| Coast Guard Cutter 3D / soufianeoujihi | https://sketchfab.com/3d-models/coast-guard-cutter-3d-8037d82f1e174f39b2237ed20a99997f | CC-BY | 9,905 | 白红小艇 | 剪影 | 远景公务艇填充 |

**FCB 结论**：免费组合可搭出"远景剪影 + 中景换装占位"两层（Houbei 换白壳绿装 + Hurricane 剪影 + PBR MK2 小目标），替代 $58 占位的大部分用途；但 §1.1 双轨制的轨道 B（外包精模）**没有免费替代**——轮胎护舷、栏杆、雷达桅、白驾驶台的 hero 细节全部要人工重做，工作量≈重做一半模型。【推断】另：免费候选均无 no-AI 条款（CC-BY），比 $58 付费件反而少一条限制（可对其跑 AI 重贴图试验），但注意部分模型要求"衍生品同样署名"。来源链风险件（Armidale/Sea Axe）见 §6。

### 2.6 整包 CC0/免费船队（对标"配角全套 $123"的底座）

| 包 / 来源 | URL | 许可要点 | 内容 | 档位 | 备注 |
|---|---|---|---|---|---|
| **Kenney Watercraft Kit**（项目已有） | https://opengameart.org/content/watercraft-kit | **CC0**【核实 OGA 页："Credit not mandatory"】 | 45+ 低模水上载体 | 剪影 | 基线，不重复采购 |
| **Quaternius Ships Pack**（OGA 副本） | https://opengameart.org/content/lowpoly-ship-pack | **CC0 1.0**【核实：OGA 页由 quaternius 本人 2018-03 上传，许可 CC0 徽章+链接】 | 6 艘简单船，带贴图，FBX/OBJ/Blend | 剪影 | **取 OGA 副本**（许可白纸黑字）；quaternius.com 现行站点许可页已改 QAL v1.0（免费商用、免署名、禁转售资产本身）——新包按 QAL，本 2018 包按 CC0【核实两页】 |
| **Boats - PolyPack** / Alstra Infinite | https://assetstore.unity.com/packages/3d/vehicles/sea/boats-polypack-189866 | 免费，Standard UAS EULA；**发行商带 AI 生成标记**【核实】 | 低模船/皮划艇/摩托艇；Built-in/URP/HDRP 兼容声明 | 剪影 | 653KB Unity 包直装；AI 标记对喂感知算法需评估（几何简单，风险低）【推断】 |
| itch.io free tag:ships | https://itch.io/game-assets/free/tag-ships | **未核**（403 反爬） | — | — | 需人工浏览器复核一次 |
| Sketchfab「Chinese ships 2024」/ Anshinowara2 | https://sketchfab.com/3d-models/chinese-ships-2024-1c3309db732049cfb15540576f61a7dc | CC-BY 徽章，来源链存疑 | 152,470 面多船合集 | — | 记录不推荐（同 §6 风险） |

### 2.7 政府/公共领域来源（仅记录，不作主推）

- **Sketchfab CC0 船类全集=博物馆扫描**【核实】：如 "Chinese Junk Ship - Science Museum"（CC0）、MV Spartan（CC0，含点云版）、Cutty Sark 船首像（CC0）——均为文物级高面数扫描，非 game-ready。
- **NOAA 海洋保护区 Sketchfab 账号**（沉船扫描为主）：https://sketchfab.com/noaasanctuaries — 页面 JS 渲染未能抓取，**未核**；即便可用也是水下沉船场景件，与本任务无关。
- 结论【核实+推断】：公共领域渠道对"现代交通船队"供给为零，维持仅记录地位。

---

## 3. 推荐组合（免费替代映射）

| 表A 项 | 免费替代组合 | 预计人日【推断】 | 省额 |
|---|---|---|---|
| A1 渔船 $4.99 | JasperTobias Trawler（中远）+ agt14032013 Fishing Trawler 44.2m（中景，减面） | 1 | $4.99 |
| A2+A5 集装箱/杂货 $62.99 | RM02 Container Ship（中景）+ hungry_drifter Cargo ship（杂货中景）+ agt14032013 系（中远）+ Alex Safayan（远景） | 2–3（含减面） | $62.99 |
| A3 油轮 $24.90 | ArtBlender Tanker + LNG 成对 | 1–2 | $24.90 |
| A4 拖轮 $30 | davidbroutian Rastar 3200 + poly.pizza TugBoat（远景） | 0.5–1 | $30 |
| A6 FCB $58 | **暂缓购买**：Houbei（换装 1–2 人日）+ Hurricane（剪影+动画）+ PBR MK2/CB-90（配角）分层占位；轨道 B 外包精模不变 | 2–3 | $58（占位档） |
| 全部 CC-BY 候选 | 统一入 `sango/Docs/asset-registry.md` 署名表（作者+模型页 URL+CC-BY-4.0） | 0.5 | — |

**合计可省 ≈ $180（表A 的 $122.88 配角包 + $58 占位全部或部分）**，代价 ≈ 6–10 人日 HDRP 材质/减面/换装工序（原本买付费件也要 1–2 天/船做 HDRP 重建，净增 ≈ 3–5 人日）【推断】。

**决策建议**：① 配角流走免费组合，把 $123 预算挪给 MicroSplat 模块/Amplify Impostors（对观感权重更高）；② FCB 免费分层占位先用，$58 付费件降级为"若换装后中景仍不过关再买"；③ 轨道 B 不变。

## 4. 与付费方案的质量差（诚实评估）

- **风格统一性**：付费包（同一 Unity 商店生态）出包即 HDRP 声明、风格接近；免费组合来自 6+ 作者，flat/PBR/CAD 风格混杂，需统一调色+统一水线工艺（§3.2 P0 本来就要做）。**这是免费方案最大隐性成本**。【推断】
- **几何可信度**：中景档免费件（RM02/hungry_drifter/ArtBlender/Rastar/Houbei）缩影正确、结构齐全，50–500m 观感与付费现货同级——付费 A2 的 231k tri 本来也要减面。【目检+推断】
- **面数纪律**：免费件面数散（5k–2.9M），必须逐个过减面/LOD 工序；付费件同样超标的先例（A2）说明这不是免费方案独有的坑。
- **许可**：免费=CC-BY 署名义务（一次性登记），**无 AI 限制条款**；付费 CGTrader 件带 no-AI 条款。此维度免费反而更宽。【核实】
- **hero 档**：免费为零，维持 00-REPORT §1.1 双轨制；H3 结论不变——可信感分水岭在船-水耦合运动与参照物体系，免费组合不拖后腿。

## 5. 未能核验项（如实清单）

| 项 | 状态 |
|---|---|
| CGTrader 免费区（船类）许可原文 | **未核**：站内搜索反爬（curl 0 字节）。搜索摘要显示免费件为 "Royalty Free License (no AI)"——以该站条款特征推断有 AI 限制，**用前必须人工开页核对** |
| Free3D / TurboSquid 免费区 | **未核**（403 / 渲染为空） |
| Fab 免费区有无船模 | **未核**（403 反爬；上游档案已知 Megascans 免费层=材质/植被，无船记录） |
| itch.io free tag:ships 全量 | **未核**（403），仅 Alstra Infinite 包经 UAS 页核实 |
| Unity Asset Store 免费船全量搜索 | 未做（搜索页 JS），仅 PolyPack 一例经详情页核实 |
| 各 Sketchfab 下载包内源格式（glTF 之外） | 未核（需注册下载后解包） |
| poly.pizza 两件面数 | 页面未标注（未核） |

## 6. 排除与风险记录

- **来源链风险（CC-BY 徽章但权利链存疑，禁入工程）**：Armidale patrol boat（ammar_ssr，desc"not mine, for download"，133k）、Sea Axe vessel（ammar_ssr，"not mine"，203k）、Sovremenny-class（42manako，"Ripped from Cold Waters"，27.5k/48.9k）、Jiangwei Luoyang（42manako，"Not my model"，23.3k）、Type 22 Houbei 36k 版（42manako，"Not my model"）。
- **名不符实（目检排除）**：SANKETPUSHKAR「Oil Tanker」=铁路油罐车；Pabooklas「Fishing boat」=划艇；2f894eb7=独木舟；6692824b=帆船；MK II Patrol River Boat=博物馆展台模型（带木座）。
- **年代/风格不符**：Kilmuir class tanker（1917 灰壳）、Swedish torpedo boat 1908、各历史帆船/沉船扫描。

## 7. 引用 URL 索引

- Sketchfab 检索/详情（许可原文）：`https://api.sketchfab.com/v3/search?type=models&downloadable=true&q=<词>&license=<cc0|cc-by>`；`https://api.sketchfab.com/v3/models/<uid>`（license.requirements="Author must be credited. Commercial use is allowed."）
- 逐候选模型页：见 §2 各表 URL 列
- poly.pizza：https://poly.pizza/m/3AmDGcCu6Ll ｜ https://poly.pizza/m/0C28iix4FPm
- Quaternius：https://quaternius.com/packs/ships.html ｜ https://quaternius.com/license.html（QAL v1.0）｜ OGA CC0 副本：https://opengameart.org/content/lowpoly-ship-pack
- Kenney：https://opengameart.org/content/watercraft-kit
- Alstra Infinite：https://assetstore.unity.com/packages/3d/vehicles/sea/boats-polypack-189866 ｜ https://alstrainfinite.itch.io/boats-asset（403 未核）
- 上游对照：[procurement-checklist.md](2026-09-24-scene-ship-fidelity/procurement-checklist.md) 表A ｜ [00-REPORT.md](2026-09-24-scene-ship-fidelity/00-REPORT.md) §1.1/§1.2/§3.1
