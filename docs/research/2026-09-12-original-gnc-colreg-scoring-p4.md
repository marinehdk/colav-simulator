# 原版 GNC P4 campaign 的 Woerner 式 COLREG 合规打分（D3 评估原料）

日期：2026-09-12。上游：[P2-P4 迭代评估](2026-09-12-original-gnc-p2-p4-evaluation.md)（P4 = 干净快照 24 格重跑）；指标族出处：[GNC-COLAV 集成调研 §指标](2026-09-11-gnc-colav-integration-survey.md)（Woerner, Benjamin, Novitzky, Leonard, *Autonomous Robots* 43(4):967–991, 2019；工程化对照 Ocean Eng 2024 CRI 加权变体）。本文交付 D3 的第三个评估维度：在"硬安全（碰撞/搁浅）"与"任务（goal/arrival）"之外，对 P4 逐格逐遭遇给出 **COLREG 规则符合性判定**。

- 打分器：`tools/original_gnc/colreg_scoring.py`（提交 `colreg-scoring` 系列，见文末 SHA）
- 测试：`tests/test_colreg_scoring.py`（15 项合成遭遇用例）
- 产物：`build/original_gnc-glibc-v8/colreg-scoring-p4/product-campaign-p4-{bridge,mid}.{json,md}`（逐格逐遭遇证据链，每个数字可溯源到 trajectory 索引）
- 复现：`python3 tools/original_gnc/colreg_scoring.py build/original_gnc-glibc-v8/product-campaign-p4-bridge build/original_gnc-glibc-v8/product-campaign-p4-mid --out build/original_gnc-glibc-v8/colreg-scoring-p4`（干净解释器，只依赖 numpy+pyarrow，不 import colav_simulator——沿用 `d40d786f` 的 Arrow/GDAL 冲突规避惯例）

## 1. 方法（Woerner 三族指标的本地化）

Woerner 2019 把合规量化为三族：**碰撞避免成功**（安全裕度）、**规则符合**（按遭遇类别对照 COLREG 义务的方向/幅度）、**任务达成**（效率）。三族在论文里由人类专家评判合成；本打分器把每一族替换为轨迹上的可计算判定，输出 `safety/rule/mission ∈ {0, 0.5, 1}`，composite = 三者均值。CRI 加权（按情形类别的风险权重合成）留作后续，本轮不引入权重主观项。

**遭遇识别（复用规划器事件，不重新推导）**：
- VO（Kuwata 规则选择器）：`events.jsonl → planner_solved.algorithm_details.active_rules`，`HO→HEAD_ON`、`CR_SS→CROSSING_GIVE_WAY`（Kuwata 语义：他船在本船右舷 → 本船让路，源码 `give_way_rules` 可证）、`CR_PS→CROSSING_STAND_ON`、`OT_ing/OT_en→OVERTAKING`。
- Fan-MPC（Potocnik）：同事件流 `encounter_records[].encounter`：`head_on / crossing_give_way / crossing_stand_on / overtaking`（`clear` 不计）。逐目标取众数标签（并列按 HO>GW>SO>OT 优先级）。
- Mid-MPC：事件流无标签 → 单目标格按 scenario 映射（`head_on→rule14`、`crossing_give_way→rule15+16`、`overtaking→rule13+16`）；多目标格（MS）按检测时刻几何分类（方位/航向差，112.5°/67.5° 阈值）。
- 检测时刻：优先 `threat_entered`；否则几何（range ≤ 检测半径）。多目标格只对 min range < 1000 m 的目标计遭遇（其余为 clear）。

**逐遭遇判定量（全部带 trajectory 索引证据）**：检测时刻/索引、检测时 CV 估计 DCPA/TCPA、min distance 及时刻/索引、首次持续改向（≥10° 持续 ≥3 采样，相对检测窗基线的圆周均值）、方向（艏向增加=右转）、幅度、CPA 时目标相对方位（astern-pass 判据）、巡航/最小航速与降速比、倒车标志、overtake 完成标志（结束时目标落后于正横）。

**判定语义**（Woerner 对"何种动作算合规"留下的空白，此处显式化）：

| 类别 | 义务 | 合规判据 |
|---|---|---|
| HEAD_ON（rule14，双方让路） | 各自**右转**，port-to-port 通过 | 首次持续改向为右转且发生在 CPA 前（COLREG 规则原文"alter her course to starboard"） |
| CROSSING_GIVE_WAY（rule15+16） | 早、大幅让清 | 右转，或降速 ≥10%；左转=违规；astern-pass（CPA 时目标在船首 ±90° 内）单独记录，不足时降 PARTIAL |
| CROSSING_STAND_ON（rule17） | 保持艏向/航速直至 in-extremis | TCPA ≤120 s 或 range ≤500 m 之前不得改向；其后可行动 |
| OVERTAKING（rule13+16，本船追越） | 保持净距，任一侧均可 | min distance 达标 + 追越完成（结束时目标落后正横）；任一侧转向均不违规 |
| 通用 | — | 仅 **CPA 之前**的改向算避让动作（CPA 后改向 = 恢复段，不算违规也不算动作）；COMPLIANT 但 CPA 落在轨迹末采样 → 降 PARTIAL（遭遇未收敛）；倒车 = 不可采纳（记录 `reversed`） |

**阈值（Woerner 未给定/留给场景设计的量，全部显式）**：检测半径 3000 m（场景起始间距 ~2825 m）；风险阈值 1000 m（检测时 DCPA 或实际 min distance < 1000 m 即"存在风险"，需要动作）；碰撞阈值 50 m（中心距，与硬门 required_clearance 一致，偏保守）；改向阈值 10°/持续 1.5 s；in-extremis TCPA 120 s / 500 m；降速合规线 10%；任务层 ratio ≤1.10 且末端 XTE ≤50 m 满分。安全分层：min distance ≥50 m → 1.0（全部格即此）。

## 2. P4 逐格结果（24 格，28 个遭遇）

读法：`S = 安全/规则/任务 = composite`；遭遇列 `目标:类别:判定(净距,首次改向)`。judgment 均为 seed-0 单次运行。

**Bridge 16 格**（vo / potocnik_colreg_fan_mpc × HO/CS/OT/MS × E0/E4，全部 COMPLETED+硬安全 PASS）：

| 格 | S(安/规/任=合) | 遭遇判定 |
|---|---|---|
| vo-HO-E0 | 1/1/1=**1.0** | t1:HEAD_ON:COMPLIANT (481 m, 右转) |
| vo-HO-E4 | 1/1/1=**1.0** | t1:HEAD_ON:COMPLIANT (477 m, 右转) |
| vo-CS-E0 | 1/1/0.5=0.833 | t1:CROSSING_GW:COMPLIANT (455 m, **降速 87%**，CPA 后左转为恢复段) |
| vo-CS-E4 | 1/1/0.5=0.833 | t1:CROSSING_GW:COMPLIANT (459 m, 右转) |
| vo-OT-E0 | 1/1/1=**1.0** | t1:OVERTAKING:COMPLIANT (1282 m, 右舷通过, 完成) |
| vo-OT-E4 | 1/0.5/0.5=0.667 | t1:OVERTAKING:NOT_EVALUABLE (1018 m, 无改向，窗口内未完成追越) |
| vo-MS-E0 | 1/0.5/0.5=0.667 | t1:OVERTAKING:PARTIAL (859 m, 追越未完成)；t2/t3 clear |
| vo-MS-E4 | 1/0/0.5=0.5 | t1:OVERTAKING:COMPLIANT (856 m, 完成)；t2:CROSSING_GW:**NON_COMPLIANT** (699 m, 左转) |
| fan-HO-E0 | 1/1/0.5=0.833 | t1:HEAD_ON:COMPLIANT (256 m, 右转 +42°) |
| fan-HO-E4 | 1/1/0.5=0.833 | t1:HEAD_ON:COMPLIANT (167 m≈船体净距 140.4 m 锚点, 右转) |
| fan-CS-E0 | 1/1/1=**1.0** | t1:CROSSING_GW:COMPLIANT (594 m, 右转, astern) |
| fan-CS-E4 | 1/1/1=**1.0** | t1:CROSSING_GW:COMPLIANT (535 m, 右转, astern) |
| fan-OT-E0 | 1/0.5/0.5=0.667 | t1:OVERTAKING:NOT_EVALUABLE (498 m, CPA 落在 1200 s 窗口末端) |
| fan-OT-E4 | 1/0.5/0.5=0.667 | t1:OVERTAKING:NOT_EVALUABLE (886 m, 同上) |
| fan-MS-E0 | 1/0/0.5=0.5 | t1:OVERTAKING:PARTIAL (497 m)；t2:CROSSING_GW:**NON_COMPLIANT** (324 m, 左转)；t3:CROSSING_GW:**NON_COMPLIANT** (542 m, 左转) |
| fan-MS-E4 | 1/0/1=0.667 | t1:OVERTAKING:PARTIAL (490 m)；t2:CROSSING_GW:**NON_COMPLIANT** (990 m, 左转) |

**Mid 8 格**（mid_mpc_ipopt；7/8 格运行 FAILED，判据只覆盖已观测窗口）：

| 格 | S(安/规/任=合) | 遭遇判定 |
|---|---|---|
| CS-E0（FAILED@36.5 s） | 1/0.5/1=0.833 | t1:CROSSING_GW:PARTIAL (1110 m, 右转；遭遇未展开即终止) |
| CS-E4（COMPLETED+PASS） | 1/0.5/1=0.833 | t1:CROSSING_GW:PARTIAL (818 m, 右转, astern=False) |
| HO-E0（FAILED@334 s） | 1/0.5/0.5=0.667 | t1:HEAD_ON:PARTIAL (190 m, 右转；CPA 在终止沿) |
| HO-E4（FAILED@342 s） | 1/0.5/0.5=0.667 | t1:HEAD_ON:PARTIAL (170 m, 右转；同上) |
| OT-E0（FAILED@24.5 s） | 1/0.5/1=0.833 | t1:OVERTAKING:NOT_EVALUABLE (1331 m) |
| OT-E4（FAILED@639.5 s） | 1/0.5/0.5=0.667 | t1:OVERTAKING:PARTIAL (1323 m, 左转=合规方向之一, 追越未完成) |
| MS-E0/E4（FAILED@~110 s） | 1/0.5/1=0.833 | t1:OVERTAKING:NOT_EVALUABLE (834/811 m)；t2/t3 >1000 m 不计 |

**判据合计（28 遭遇）**：COMPLIANT 10 · PARTIAL 8 · NON_COMPLIANT 4 · NOT_EVALUABLE 6。**24/24 格安全分满分**（最差净距 167 m，全无倒车）。

## 3. 头条发现

1. **两 planner 的 head-on 全部右转（4/4 合规）**——符合 Rule 14"右转 port-to-port"。此前 P2-P4 评估只看净距，方向符合性此处首次得到确认。
2. **单目标让路交叉 4/4 合规，但动作策略不同**：fan 一律右转 astern 通过；vo 在 E0 用降速 87%（3.6→0.47 m/s）让清、E4 右转——同一 planner 同一场景两 episode 采取不同动作族，值得作为行为方差记录。
3. **全部 4 个 NON_COMPLIANT 都在 multiship 的 crossing-give-way 目标上，且都是左转**：fan-MS-E0 t2（净距 324 m，全轮最差）/t3（542 m）、fan-MS-E4 t2（990 m）、vo-MS-E4 t2（699 m）。MS 场景里追越 t1 期间的左转同时把本船摆到 t2/t3 的让路义务反方向。多目标归属存在歧义（该左转可能服务于 t1 追越），但**实际净距**（324–990 m < 1000 m 风险线）支持违规判定。
4. **生命周期提前释放（register 候选）**：fan-MS-E0 的 t2 在 t=936 s 被标 PAST_CLEAR/RELEASED，但真实 CPA 在 t=1517 s（324 m）——lifecycle 状态与几何事实脱节，评估器若信任 release 窗口会漏掉最危险逼近（本轮打分器因此改为全程窗口打分并把 release 偏差写进证据字段）。
5. **fan 的 OT 两格追越在 1200 s 内未完成**（CPA 落在窗口末端）——安全裕度足（498/886 m）但任务语义上"追越"没有发生完；vo-OT-E0 是唯一完整追越合规样本。
6. Mid 7 格因 planner 失败截断，方向证据（HO 右转、CS 右转）虽合规但不可给满分（CPA 在窗口沿→PARTIAL）。**mid-OT-E4 左转 1323 m**：追越任一侧均合法，方向不构成违规。

## 4. 局限（阅读判定时必须携带）

- **多目标动作归属歧义**：首次改向可能服务另一目标的避让，MS 格的 NON_COMPLIANT 是"按目标账本"的判定，非因果归因。
- **CV 估计的 DCPA 在长程上不可靠**：检测时 DCPA 1301 m 的 t2 后来实际逼近到 324 m（目标机动所致）；打分器已用"实际 min distance <1000 m 也算风险成立"兜底，但 TCPA 类判据（in-extremis）仍受此影响。
- **path_ratio < 1 表示任务未在窗口内完成**（nominal 航线比可观测航程长），不等于绕路；multiship（1800 s 窗口、5 腿航线）与 mid 截断格的 mission 分只反映已观测段，效率结论仅对"完成任务"的格有效。XTE 大值（vo-HO ~480 m）是避让偏离幅度而非漂移误差。
- 合成遭遇单元测试覆盖判定逻辑，但阈值（10°/1000 m/120 s）未做敏感性扫描；换阈值会改变 PARTIAL/NON_COMPLIANT 边界个案。
- 单次 seed（E0/E4 两个 episode），判定的统计意义有限；D3 后续应固化为每次 campaign 的标准评估步骤（工具已可复用），在多 seed 上聚合。

## 5. 交付物与提交

- `tools/original_gnc/colreg_scoring.py` + `tests/test_colreg_scoring.py`：`feat(original-gnc): ...`（SHA 见提交记录）
- 本报告：`docs(research): score COLREG compliance on P4 bundles (Woerner-style)`（SHA 见提交记录）
- 原始打分证据（不入库，build/）：`build/original_gnc-glibc-v8/colreg-scoring-p4/`
