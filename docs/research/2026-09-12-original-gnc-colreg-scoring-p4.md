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

## v2 rescore (attribution corrections)

日期：2026-09-12。依据 [R11 归因报告](2026-09-12-original-gnc-r11-attribution.md) §4 落实 4 项修正并版本化打分器。**输出 JSON/MD 带 `version` 字段（`colreg-scoring-v2`，默认；`--scorer v1` 完整保留旧账本，已逐条验证与本文 §2 的 v1 结果一致）**。复现：`python3 tools/original_gnc/colreg_scoring.py build/original_gnc-glibc-v8/product-campaign-p4-{bridge,mid} --out build/original_gnc-glibc-v8/colreg-scoring-p4-v2`。产物：`build/original_gnc-glibc-v8/colreg-scoring-p4-v2/`（不入库）。

修正内容（各带单元测试，测试 15→28 项）：

1. **改向检测迁移到指令层**：信号取 `trajectory.parquet.applied_course_ref_rad`；参考恒定（vo 后端把参考钉在航线航向）时改由 `events.jsonl → planner_solved.selected_command.course_rad` 重建指令阶跃信号（首解前以航线参考播种）。v2 基线取**检测前**窗口（航线参考）：检测即刻即出避让指令的动作（vo 首解 t=0）不再被基线吞掉。闭环艏向摆动/滞后不再构成"改向"。
2. **事件链归属**：改向只记到 `avoidance_action_started / primary_switched` primary 时间线在改向时刻指向的目标（primary-target projection）；多目标格无事件链证据不记账；单目标格不受影响。
3. **锚泊目标重分类**：CPA 前 60 s 窗口内目标 SOG 中位 < 0.5 m/s → `STATIC_HAZARD`，只计净距（≥50 m 判 COMPLIANT），不套 Rule 14/15 方向义务，并豁免"CPA 未收敛→PARTIAL"降级（未收敛证据保留在 `incomplete` 字段）。
4. **航向否决移除**：psi 左转读数不再否决合规降速（v1 对 vo-CS 的误判机制）；指令层真实 port 改向仍按 Rule 15 拒绝。

**24 格 28 遭遇合计：COMPLIANT 10→12 · PARTIAL 8→8 · NOT_EVALUABLE 6→6 · NON_COMPLIANT 4→2。安全分 24/24 格保持 1.0。**其余 19 格判定与三分项不变。变化的 5 格：

| 格 | 变化 | v1→v2 composite |
|---|---|---|
| fan-MS-E0 | t2/t3 NON→COMPLIANT（STATIC_HAZARD，324/542 m；改向均不成立：cref 恒定/斜坡记到 t1 名下） | 0.5→0.667 |
| fan-MS-E4 | t2 NON→COMPLIANT（STATIC_HAZARD，990 m，窗口末端未收敛仍记 COMPLIANT） | 0.667→0.833 |
| vo-MS-E4 | t2 NON→COMPLIANT（STATIC_HAZARD，699 m；降速 57% 并列在案） | 0.5→0.833 |
| vo-CS-E0 | COMPLIANT→**NON**（见下） | 0.833→0.5 |
| vo-CS-E4 | COMPLIANT→**NON**（见下） | 0.833→0.5 |

**v2 下仍 NON_COMPLIANT 的 2 例 = vo-CS-E0/E4，且是新暴露的真实发现**：vo 规划器对让路交叉的解算从首解（t=0，先于 threat_entered 0.5 s）即持续指令 **port 偏航 59.1°/78.7°（相对航线参考）**——指令层为 Rule 15 的 "avoid crossing ahead"（左转抢越）方向，同时伴随 87%/97% 降速。v1 的艏向滞后恰好把这笔 port 改向的"检出"推迟到 CPA（168.5 s）之后而误记为恢复段——与 R11 同族的账本错位、方向相反：v1 对 fan 伪造左转、对 vo 隐瞒左转。按修正 #4 保留指令层方向拒绝；降速证据并列在 `speed_reduction_fraction` 字段。

局限：vo 指令层重建假设 `selected_command.course_rad` 与参考同角约定（佐证：vo-HO cmd 81.6° 与 psi 45°→99° 右转响应相符；run 末端 cmd 与 ref 重合于 45.0°）；即期动作场景的检测前基线窗近空，依赖航线参考播种。fan-MS-E4/vo-MS-E4 的 t2 min 距在窗口末端未收敛，v2 仍记 COMPLIANT 系 R11 §4 预期的直接落实（锚泊目标无方向义务），净距未收敛的事实由 `incomplete=true` 携带。测试：`tests/test_colreg_scoring.py` 28 项（15 项 v1 合成遭遇 + 13 项 v2/R11，含 4 个 R11 案例降维 fixture，均断言 v2 COMPLIANT/no-action、v1 维持原 NON 判定）。
