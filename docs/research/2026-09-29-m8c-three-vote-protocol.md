# M8-C 验收「三票制」协议与参照系 — 调研与设计

- 日期：2026-09-29 ｜ 服务对象：Sango 数字孪生海峡仿真（Unity HDRP，29 tile 海峡）M8-C 验收批
- 上游：00-REPORT §7 行动 6（"运动/尺度/光照三票通过制，不比单帧美术"，2026-09-24 调研提出）→ 本文将其落成可执行协议
- 惯例对齐：M7 验收档（[acceptance.md](2026-09-29-m7-strait-setdressing/acceptance.md)）的"交付事实 + findings"格式；参照系沿用 [dive_06](2026-09-24-scene-ship-fidelity/dive_06.md) 的检索结论（不重复，只引用与补核实）
- 标注：【事实】= 本次逐字核实来源；【推断】= 工程设计判断

---

## 0. 结论先行：协议一段话

**M8-C 三票制 = 三个独立评审 × 三轴 BARS 锚点 × 中位数聚合。**
评审只拿到一个材料包（9 段固定机位固定时长录屏，五机位 + 大气三档 + 夜航，与 M8-B 出片镜头脚本同源；无 HUD、无项目上下文、互不见对方评分），按**运动真实感 / 尺度感 / 光照真实感**三轴各打 1–5 分（每分值一句可判读锚点，BARS 风格），并在证据时间戳上落 finding。**每轴取三人中位数，全部三轴中位数 ≥4 且无任何轴中位数 ≤2 → 通过**；任一轴极差 ≥2 → 该轴复评（三人同场重看材料、重新独立打分，仍 ≥2 由技术负责人凭录制证据裁决并记录）；任一评审给出 1 分 → 一票否决即 finding 修复循环。参照系 = Aeolus-Ocean（学术侧，非 NTNU，澄清见 §1）+ Sea Power（游戏侧）官方公开截图/动图，只作观感校准并排评审，不做像素比对；客观门禁只有 fps（双机 ≥30，沿用 M7 干净协议）。

---

## 1. 参照系核实（可引用视觉参照 + 许可/引用方式）

### 1.1 澄清「Aeolus」身份【事实】

| 候选 | 身份 | 结论 |
|---|---|---|
| **Aeolus-Ocean**（arXiv 2307.06688，2023） | Vekinis & Perantonis 的 USV 仿真环境：Unity、COLREG、昼夜、天气、YOLO-X 检测 + DRL。**与 NTNU 无关**（论文页与 README 均未提及 NTNU） | ✅ 即 2026-09-24 调研的"学术标杆"，继续作主参照 |
| **NTNU autoferry** | milliAmpere 渡轮项目；其模拟器叫 **Gemini**（曾用名 CloudSIM），Unity HDRP，repo 已于 2025-11-12 归档只读（[库内证据档](2026-09-17-ntnu-gemini-evidence.md)已核实） | ⚠️ 作运动真实感校准参照（真渡轮影像），**不作主视觉参照**（Gemini README 无公开截图/视频画廊） |

### 1.2 Aeolus-Ocean — 学术侧主参照【事实】

| 材料 | URL | 许可与引用方式 |
|---|---|---|
| 论文 17 张配图（海况/昼夜/COLREG 场景渲染） | https://arxiv.org/abs/2307.06688 | arXiv nonexclusive-distrib/1.0：公开查阅、学术引用（标注 arXiv:2307.06688）；图不入产品 |
| README 日间截图 + 夜间跟踪截图 | https://github.com/aavek/Aeolus-Ocean | 仓库 BSD-3-Clause（代码）；README 图/GIF 版权归作者，引用=注明来源 URL + 内部参照用途，不重分发 |
| COLREG Rule 14/16 与雨/雪/雾跟 animated GIF | 同上（README 内 GitHub user-images 直链） | 同上 |

引用句式：`图来源：Aeolus-Ocean (Vekinis & Perantonis, arXiv:2307.06688)，https://github.com/aavek/Aeolus-Ocean，仅作内部观感校准参照`。

### 1.3 Sea Power — 游戏侧主参照【事实，本次经 Steam appdetails API 复核】

- 商店页：https://store.steampowered.com/app/1286220/ （Triassic Games 开发 / MicroProse 发行；公开页面含 4 条官方预告片与全套官方截图）。2026-09-24 首核（dive_06 脚注），2026-09-29 API 复核通过。
- 官方截图直链（API 返回，1920x1080，示例 3 张）：
  - https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/1286220/ss_bcfa061aafba879959c7a5cded2d25cbd6e48b18.1920x1080.jpg
  - https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/1286220/ss_5741b80b03a814b6e3b49af08c7019a4c41d7341.1920x1080.jpg
  - https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/1286220/ss_15db33844f1c963f3d44f6034cc4ed9c6c2d22d7.1920x1080.jpg
- 预告片：商店页内 "Launch trailer"（id 257072437）、"PLAN update"（id 257215064）等 4 条。
- 社区截图廊（公开）：https://steamcommunity.com/app/1286220/screenshots
- 媒体实测截图（含雾中构图，dive_06 已引）：https://stormbirds.blog/2024/11/09/hands-on-with-sea-power-naval-combat-in-the-missile-age/
- **许可/引用方式**：© Triassic Games / MicroProse 商业版权材料；公开页面可查阅，内部研究引用 = 页面 URL + 版权行 + "仅作内部观感校准"；截图/GIF 一律不进产品包、不外发。
- 选用理由（引 dive_06 结论，不重复拆解）：其可信感两大件 = 高细节船模 + 高质量水体，玩家原话 "the very good illusion of realism"，且为短板效应反面教材（火/烟特效破功）——正适合校准三轴中的运动与光照两轴。

### 1.4 NTNU autoferry（milliAmpere / Gemini）— 运动真实感辅参照【事实】

- 真渡轮实验照片与数据：https://github.com/Autoferry/milliAmpere_data （Apache-2.0，保留许可声明即可复用/引用）。
- 项目博客（含 milliAmpere 实测照与 YouTube 嵌入）：https://autoferry.github.io/2020/04/16/simulation-based-validation/ 及 https://www.ntnu.edu/autoferry/
- Gemini 模拟器仓库（MIT，已归档）：https://github.com/Gemini-team/Gemini — README 无视觉画廊；论文 *Autoferry Gemini: a real-time simulation platform for electromagnetic radiation sensors on autonomous ships*（2020）Figure 1 有 HDRP 渲染管线图，本地副本在 [docs/paper/](../paper/)。
- 用途边界：Gemini 视觉材料不足以当"画面参照"，但 milliAmpere 真渡轮影像是小型渡轮**浮态/转向节奏**的真实校准源（运动轴锚点 4–5 分的地面真值）。

### 1.5 替代参照（备胎，若上述链接失效或需商用级观感上限）【事实，均已在 dive_06 引过产品页】

- **VSTEP NAUTIS**（唯一把 photorealistic 写进官方话术的海事仿真器）：https://vstepsimulation.com/nautis-visualiser/
- **Kongsberg K-Sim Navigation / Polaris**：https://www.kongsbergmaritime.com/products/simulation/k-sim-navigation/
- **DNV 海事仿真器**：https://www.dnv.com/services/maritime-simulator-systems-3797/ （产品页带官方截图）
- **VRSG 3D Ocean**（军用 IG，12 级海况 + 自动尾迹，特性页带截图）：https://mvrsimulation.com/products/vrsg/vrsg-3Doceans.html
- 引用方式同 Sea Power：官网产品图 © 各厂商，注明来源 URL、内部参照、不重分发。

---

## 2. 三票制协议：三轴 BARS 锚点

三票 = **三个独立评审**（互不知对方身份与评分；只发材料包 + 锚点表 + 打分表，不发项目期望、不发参照系背景讨论）。每轴 1–5 分，BARS 风格——每分值一句可判读描述，评审只需回答"画面行为落在哪一句"。【推断：BARS 形式源自 Smith & Kendall 1963（见 §6），锚点句式按本项目"不比单帧美术、只比可信感"的既有原则写】

### 轴 1｜运动真实感（船体运动/浮态/航迹）

| 分 | 锚点（可判读句） |
|---|---|
| 1 | 船像贴在地面上滑行：无横摇纵摇起伏，转向瞬间到位或航迹跳变，无艏波尾迹或闪烁穿模——一眼假。 |
| 2 | 有尾迹但浮态与海况脱节（静水面像滑轨、浪里像钟摆），或掉帧/卡顿破坏运动感，可看但不能用。 |
| 3 | 大体可信：浮态与尾迹定性存在、转向有过程，但节奏细节出戏（如转向无横倾、尾迹与船速不匹配），偶发怪异。 |
| 4 | 可信：横摇/纵摇/垂荡节奏与海况一致，转向有横倾与回正，艏波-尾迹随船速连续演化，航迹连续——连续看 15 秒不出戏。 |
| 5 | 参照级：任意机位任意海况下运动感与 Aeolus-Ocean / 真渡轮影像同级，浮态"定量地对"，可直接当训练素材。 |

### 轴 2｜尺度感（岸桥/船/浮标相对尺度）

| 分 | 锚点 |
|---|---|
| 1 | 无尺度：岸桥浮标与船的大小关系错误，20 节毫无速度感，像在微缩沙盘上空飘。 |
| 2 | 近景可读但比例跳变：岸桥像玩具、浮标像火柴棍，或远近景尺度自相矛盾。 |
| 3 | 大体正确：主要参照物关系成立，但速度感平淡、个别机位 FOV/距离组合造成失真。 |
| 4 | 可信：岸桥-渡轮-浮标-船尺度链全对，低加速度真实感成立，近距离通过（渡轮会遇、浮标擦舷）能产生真实的压迫感与速度感。 |
| 5 | 参照级：任意一帧都能立即读出"这是 45m 的船、那是 60m 的岸桥、那是 3m 的浮标"，尺度错觉与 Sea Power 官方截图同级。 |

### 轴 3｜光照真实感（大气/夜航号灯/水面反射）

| 分 | 锚点 |
|---|---|
| 1 | 破碎：天-海-反射颜色互相矛盾，夜航号灯穿帮（穿模/光弧方向错/闪烁节奏错），雾有"切面"。 |
| 2 | 自洽但假：单帧尚可，但大气三档切换跳变、夜灯浮在船壳上、水面反射方向与光源不符。 |
| 3 | 及格：三档与夜航各自内部自洽，但反射色调/环境光有轻微违和，档间过渡可感知。 |
| 4 | 可信：太阳角-雾-水面反射-曝光联动正确，号灯光弧与闪烁特性符合 COLREG（桅 225°/舷 112.5°/尾 135°，快闪/群闪节奏），三档+夜航全程自洽。 |
| 5 | 参照级：三档大气与夜航的照明错觉达到参照系同级，档间过渡无感，夜航号灯"一眼就懂谁在哪"。 |

### 聚合与分歧规则【推断：聚合口径取 ITU 主观测试惯例（MOS + 离散度检查）的最小子集，见 §6】

1. 每轴三人分数取**中位数**为该轴得分。
2. **通过判据**：三轴中位数全部 ≥4，且无任何轴中位数 ≤2（后者是防"两项 5 分掩盖一项假"的短板效应条款——dive_06 已证可信感按最弱项计）。
3. **极差复评**：任一轴三人极差 ≥2 → 该轴复评：三人同场重看对应材料（可逐帧），再独立打分一次；复评后仍 ≥2 → 技术负责人凭录制证据与锚点裁决，裁决记录进 acceptance 档。
4. **一票否决**：任一评审任一轴打 1 → 不进复评，直接转 findings 修复循环（1 分锚点句即 finding 描述格式）。
5. 评审在收料后 **24h 内**完成；观看顺序不限但每段必须完整看；评分只落在打分表上，讨论留到聚合后。

---

## 3. 评审材料清单（与 M8-B 出片镜头脚本对齐）

固定条件：同一 fresh 构建、同一出生点（M6 泊位，艏向 134°）、默认海况、**HUD 全隐**（M7 修复批披露：Overlook 构图下 PP 天际线被 SIMULATION 面板遮挡——出片必须走 HUD-off 路径）、1080p、≥30fps、每段静置 3s 后开始有效内容。录制机 = a4000（出片机）；Mac 仅跑 fps 门禁不喂评审。【事实：五机位、N 键大气三档、T×2 夜航均已在 M7 修复批（bfc14d69）落地并有实拍】

| # | 片段名 | 机位 | 时段/大气 | 时长 | 主要喂的轴 | 内容要求 |
|---|---|---|---|---|---|---|
| 1 | bridge-day | Bridge | HazyClear | 15s | 运动 | G 自航稳态直航 + 一次 15° 转向 |
| 2 | bow-day | Bow | HazyClear | 15s | 运动+尺度 | 艏波/飞沫特写；若航线附近有浮标，安排擦舷通过 |
| 3 | chase-day | Chase | HazyClear | 15s | 运动 | 全船横摇纵摇 + 尾迹演化全景 |
| 4 | topdown-day | TopDown | HazyClear | 15s | 运动+尺度 | 航迹几何 + 尾迹张开 + 渔排/浮标相对尺度 |
| 5 | overlook-day | Overlook | HazyClear | 15s | 尺度 | 回望 PP 岸桥天际线 + 渡轮/拖轮动目标入画（F1 机位设计目标） |
| 6 | bridge-atmo | Bridge（定点） | N 循环三档 | 60s（前两档各 18s，末档 Thunderstorm 24s，含过渡） | 光照 | 三档切换无剪辑连续录，重点档间过渡与水面反射联动 |
| 7 | bridge-night | Bridge | T×2 至 h=0 | 15s | 光照 | 三船号灯 + 本船舷灯斑 + 月夜海面 |
| 8 | chase-night | Chase | h=0 | 15s | 光照+运动 | 尾迹在夜色的可读性 + 号灯剪影 |
| 9 | overlook-night | Overlook | h=0 | 15s | 光照（可选项） | 回望锚地/渡轮灯光群；若视距不足可由 anchor 群灯带替代 |

- 段前静置 3s 由剪辑/起录时点处理，不进录制时长（SettleSeconds 常量已删，20260930 review 裁决）。
- bridge-atmo 实现以 60s 总长优先，末档 24s（20260930 review 裁决，与 M8ShotList 实现一致）。

- 命名与归档：`m8c-<clip>.mp4` 存入 M8-C 验收目录（与 M7 的 `m7a-*.jpg` 惯例一致），打分表逐段引用片段号。
- 参照并排材料（评审可选看，不强制）：Aeolus README GIF ×3 + Sea Power 官方截图 ×3（§1.2/§1.3 直链），用途=锚点 4–5 分的观感校准，**不做并排像素比对**。
- M8-B 若出片有增减机位，以 M8-B 终版镜头脚本为准增删行——本表只钉"喂给评审的最小集"。

---

## 4. 打分表模板（可直接粘贴）

### 4.1 单评审打分表（每人一份）

```markdown
## M8-C 三票制 — 评审打分表

- 评审:____  日期:____  材料包:build <commit> / 录制机 a4000
- 规则:每轴 1-5 分,按锚点句打分;任一轴打 1 分必须在"证据"列写片段号+时间戳

| 片段 | 运动 | 尺度 | 光照 | 证据(片段/时间戳) | 备注 |
|---|---|---|---|---|---|
| 1 bridge-day  |   |   |   |  |  |
| 2 bow-day     |   |   |   |  |  |
| 3 chase-day   |   |   |   |  |  |
| 4 topdown-day |   |   |   |  |  |
| 5 overlook-day|   |   |   |  |  |
| 6 bridge-atmo |   |   |   |  |  |
| 7 bridge-night|   |   |   |  |  |
| 8 chase-night |   |   |   |  |  |
| 9 overlook-night| |   |   |  |  |
| **轴总分(整包)** |  |  |  | — | 整包印象分,非逐段平均 |
```

说明：逐段打分给 finding 定位用；轴总分为整包印象分（两套都记，聚合用轴总分）。【推断：逐段+整包双层，避免"平均分掩盖单段穿帮"，与 M7 findings 格式兼容】

### 4.2 聚合表（主持人填）

```markdown
## M8-C — 三票聚合

| 轴 | 评审 A | 评审 B | 评审 C | 中位数 | 极差 | 判定(≥4 过 / 极差≥2 复评 / 有 1 否决) |
|---|---|---|---|---|---|---|
| 运动 |   |   |   |   |   |   |
| 尺度 |   |   |   |   |   |   |
| 光照 |   |   |   |   |   |   |
| **M8-C 结论** | | | | — | — | PASS / FAIL / 复评(轴:____) |

- 复评记录(如有):轴____ 复评分 ___/___/___ → 复评中位数 ___,仍极差≥2 → 裁决:____(依据片段/时间戳)
- Findings 转入:M8-C findings 清单(1 分项+复评分歧点,格式同 M7 acceptance.md)
```

### 4.3 双机 fps 记录表（客观门禁，独立于三票）

```markdown
## M8-C — 双机 fps 记录(干净协议:独立会话+零交互+预热后读稳态,`overlays fps` 10s avg ×4 连读)

| 场景 | Mac M3 fps(×4) | a4000 fps(×4) | gate ≥30 | frame_ms_avg | 备注 |
|---|---|---|---|---|---|
| 出生点静置(HazyClear) |  |  |  |  |  |
| G 自航巡航(HazyClear) |  |  |  |  |  |
| 三档循环中(Cumulonimbus) |  |  |  |  |  |
| 雷暴档(雨粒子) |  |  |  |  |  |
| 夜航 h=0(号灯 ON) |  |  |  |  |  |

- 判读惯例(vsync 满帧间隔非饱和、water queries/frame=0)沿用 M7 记录,不重定义。
```

---

## 5. 先例：为什么人评、为什么不用 SSIM 类客观指标【事实+推断，简要】

- **主观协议的行业标准做法**：ITU-R BT.500 / ITU-T P.910 / P.913 把"人看+打 5 级分（ACR）+ MOS 聚合 + 离散度检查/异常评审剔除"标准化了几十年——本协议的 5 分锚点、中位数聚合、极差复评是该惯例的最小子集（https://www.itu.int/rec/T-REC-P.910 ，https://www.itu.int/rec/R-REC-BT.500 ，https://www.itu.int/rec/T-REC-P.913 ）。
- **BARS 的出处**：Smith & Kendall 1963 提出行为锚定等级量表，把"分数"钉到"可判读行为句"上——本协议每分值一句即此法（P. C. Smith & L. M. Kendall, "Retranslation of expectations for an appraisal scale formed in terms of behavior", *Journal of Applied Psychology*, 1963）。
- **图形学验收的先例**：Ramanarayanan et al., *Visual Equivalence: Towards a New Standard for Image Fidelity*（ACM TOG 26(3), SIGGRAPH 2007, DOI 10.1145/1276377.1276472）——渲染验收的标准不是与真值像素一致，而是"传达同样的整体印象"；错处可容忍、可信感优先。这正是"并排参照只作观感校准、不做像素比对"的学理依据。
- **SSIM 类为何不适用**：① SSIM 是全参考指标（Wang et al., IEEE TIP 2004），需要一张真实 ground-truth 图——新加坡海峡的合成画面没有真实对应帧，指标根本无从计算；② SSIM 为压缩/传输失真设计，度量"结构保真"而非"可信感"——视觉等价文献已证二者脱钩（上条）；③ 运动真实感是时序属性、尺度感是跨物体关系，单图指标两轴都覆盖不到；④ 客观视频质量与人评的相关性本就不稳定（Seshadrinathan et al., IEEE TIP 2010, LIVE 视频库系列研究）。图形学界为此发展无参考路线（如 Disney Research 的 NoRM, *No-Reference Image Quality Metric for Realistic Image Synthesis*, https://la.disneyresearch.com/wp-content/uploads/NoRM-No-Reference-Image-Quality-Metric-for-Realistic-Image-Synthesis-Paper.pdf ），但仍是单图纹理级——替代不了三轴人评。
- **领域验收的先例**：海事仿真器认证（DNV-ST-0033）= 客观可视参数（视场角/更新率）+ 演示与实验中的专家主观验证；飞行仿真器适航（FAA 14 CFR Part 60）= 飞行员对视觉线索的定性评定 + 标准化科目表现。游戏侧的"验收"即媒体/玩家人评（Sea Power 91% 好评与"火/烟破功"评论同源并存，dive_06 已引）。共同点：**成品仿真器的视觉验收从来是人评为主、客观指标只管 fps/视场角这类硬参数**——本协议 = 该结构的最小实现。【推断：以上为惯例归纳，DNV/FAA 细则条款未逐条核对】

---

## 6. 来源列表

| # | 来源 | URL | 访问 | 用途 |
|---|---|---|---|---|
| 1 | Aeolus-Ocean 论文（arXiv:2307.06688） | https://arxiv.org/abs/2307.06688 | 2026-09-29 | 学术参照主档（标题/作者/17 图/许可） |
| 2 | Aeolus-Ocean GitHub（BSD-3-Clause） | https://github.com/aavek/Aeolus-Ocean | 2026-09-29 | README 截图/GIF 直链 |
| 3 | Sea Power Steam 商店页 + appdetails API | https://store.steampowered.com/app/1286220/ | 2026-09-24 及 2026-09-29 | 游戏参照主档（截图直链/4 预告片/厂商） |
| 4 | Sea Power 社区截图廊 | https://steamcommunity.com/app/1286220/screenshots | 2026-09-29 | 补充视觉材料 |
| 5 | Stormbirds 实测（媒体截图） | https://stormbirds.blog/2024/11/09/hands-on-with-sea-power-naval-combat-in-the-missile-age/ | 2026-09-24（dive_06） | 雾中构图参照 |
| 6 | NTNU autoferry 博客（仿真验证篇） | https://autoferry.github.io/2020/04/16/simulation-based-validation/ | 2026-09-29 | 真渡轮影像、无截图画廊的核实 |
| 7 | milliAmpere 数据仓（Apache-2.0） | https://github.com/Autoferry/milliAmpere_data | 2026-09-29 | 真渡轮照片（运动轴校准） |
| 8 | Gemini 仓库（MIT，已归档）与库内证据档 | https://github.com/Gemini-team/Gemini ；[2026-09-17-ntnu-gemini-evidence.md](2026-09-17-ntnu-gemini-evidence.md) | 2026-09-29 引用既有核实 | NTNU 模拟器身份/状态 |
| 9 | ITU-T P.910 / ITU-R BT.500 / P.913 | https://www.itu.int/rec/T-REC-P.910 等 | 2026-09-29 | 主观测试方法论先例 |
| 10 | Smith & Kendall 1963（BARS 出处） | *Journal of Applied Psychology*, 1963 | 文献 | 锚点式量表先例 |
| 11 | Ramanarayanan et al. 2007, Visual Equivalence | DOI 10.1145/1276377.1276472 | 2026-09-29 | 图形学验收标准先例 |
| 12 | Wang et al. 2004（SSIM 原始论文） | IEEE TIP 13(4) | 文献 | 全参考指标定义 |
| 13 | Seshadrathan et al. 2010（人评 vs 指标） | IEEE TIP（LIVE Video） | 文献 | 指标-人评相关性证据 |
| 14 | Disney Research NoRM | https://la.disneyresearch.com/wp-content/uploads/NoRM-No-Reference-Image-Quality-Metric-for-Realistic-Image-Synthesis-Paper.pdf | 2026-09-29（仅标题页级） | 图形学无参考指标方向 |
| 15 | DNV-ST-0033 / FAA Part 60 | https://standards.dnv.com/explorer/document/56aa6da4-58cb-4a8d-9e5c-3394704fa26b/detail ；14 CFR Part 60 | 检索级 | 领域验收惯例（细则未逐条核对，如实标注） |
| 16 | 替代参照产品页 ×4 | §1.5 各 URL | 2026-09-24（dive_06） | 备胎参照 |

## 7. 待办与边界（如实记录）

- Sea Power 截图直链由 appdetails API 返回，未逐张下载验图；评审材料打包前若 404，直接用商店页内嵌画廊。
- NoRM 论文 PDF 超过抓取上限，仅核实到标题/托管方；引用时按标题+URL 引。
- DNV-ST-0033 与 FAA Part 60 的"人评为主"结论来自检索与领域常识归纳，未逐条核对细则——若未来要对外引用为依据，需读原文条款。
- 本协议未覆盖：评审人样本量只有 3（远小于 ITU 建议的 ≥15 非专家）——这是内部验收的成本取舍，锚点句与复评规则即为小样本补偿设计；对外论文级评估需扩样。
