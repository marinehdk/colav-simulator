# R11 归因：multiship 让路 NON_COMPLIANT 左转是账本错位还是真实违规

日期：2026-09-12。上游：[P4 COLREG 打分](2026-09-12-original-gnc-colreg-scoring-p4.md) §3.3/§4（4 个 NON_COMPLIANT 全部是 multiship crossing-give-way 目标上的"左转"）。本报告只做只读归因：离线重放已录制的 P4 轨迹/事件，不重跑 episode（分析脚本 `tools/original_gnc/r11_attribution.py`，本次输出 `tmp/r11_attribution.json`，均不入库）。

## 1. 结论

**4/4 都是归因伪影（verdict (a)），不是"规划器在右转可行时选了左转"的真实违规（(b) 不成立）；任务假设的"左转服务于 t1 追越"机制也不成立。** 真实机制是三件事叠加：

1. **打分器的首次改向检测以艏向（psi）为对象**：闭环艏向保持的 ±6–10° 摆动/滞后在基线恰好取到摆动峰值时即被记为"首次改向"。4 例中被记为改向的时刻，**applied course 指令全部纹丝不动**（fan 两条 = -85.0° 恒定，vo 一条 = +30.9° 恒定；fan 规划器诊断 `maneuver_turn_sign=0, phase=RETURN, encounters=[clear×3]`）。
2. **两个 give-way 目标都按场景脚本在航程末端抛锚**（TS2 在 900–1200 s 间、TS3 在 1500–1795 s 间 SOG 归零），而实际 CPA（324/542/990/699 m）全部发生在**抛锚之后**——对锚泊船的 Rule 15 交叉让路义务本身不适定，打分器没有重分类。
3. **生命周期过早释放**（p4 报告 §3.4 已登记）：planner 在 t=936/938 s（fan-E0）/916.7 s（fan-E4 的 t3）/1382.7 s（vo-E4）把 t2/t3 标 RELEASED，真实 CPA 在 580–860 s 之后；此后本船对走廊内的静止目标"失明"，324 m 通过是路线几何（leg-2 航线距 TS2 锚点 257 m、距 TS3 锚点 221 m）而非主动避让。

| 遭遇 | 净距 | 判定 | 归因 | 右转反事实（对全目标 min range） |
|---|---|---|---|---|
| fan-MS-E0 t2 | 324 m @1517.5 s | NON_COMPLIANT（port 179.7°@559.9 s） | **(a) 伪影**：艏向摆动误记；CPA 对锚泊 TS2 | 1702 m（TS2）/514 m（t1）/3652 m（t3），均优于实录 |
| fan-MS-E0 t3 | 542 m @1794.5 s | NON_COMPLIANT（port 180.0°@1128.6 s） | **(a) 伪影**：改向实为恢复 leg-2 的指令斜坡（31.8°→3.2°，检测前已开始）；CPA 对锚泊 TS3 | 1389 m（TS3）/826 m（t2），均优于实录 |
| fan-MS-E4 t2 | 990 m @1800 s（未收敛） | NON_COMPLIANT（port 125.7°@504.7 s） | **(a) 伪影**：同 E0 t2 机制（cref -85.0° 恒定） | 1759 m（TS2），优于实录 |
| vo-MS-E4 t2 | 699 m @1800 s（未收敛） | NON_COMPLIANT（port 180.0°@396.6 s） | **(a) 伪影**（带 (c) 注脚）：记到的"左转"是规划器自身 TS2 避让指令序列（cmd -59°→-180°@t≈200–300 s，t=45.3 s 起 TS2 即 primary）的滞后尾段，且 t≈420 s 已回摆右转（-87.2°）；CPA 对锚泊 TS2 | 775 m（TS2）vs 实录 699 m，差异不显著（锚泊目标） |

## 2. 方法

离线重放三个 run_dir（`build/original_gnc-glibc-v8/product-campaign-p4-bridge/{potocnik_colreg_fan_mpc,vo}-paper_ccta2023_multiship-E{0,4}/<run_id>/`，trajectory.parquet + events.jsonl + lifecycle_events.jsonl）：

1. **时间线**：primary_switched/avoidance_action_started 事件 → primary 时间线；lifecycle_events → CANDIDATE/ACTIVE/PAST_CLEAR/RELEASED 时刻；每 0.1 s 的 psi、applied_course_ref、applied_speed_ref、planner selected_command、目标 range/bearing。
2. **被记改向时刻的指令核查**：取打分器证据里的 first_alteration_index，读当时的 applied course/speed 与 fan 规划器诊断（turn_sign/phase/encounter_records）。
3. **右转反事实**：从改向索引起用记录 SOG + 镜像艏向剖面（psi_alt = 2·baseline − psi_rec，即把同一幅度改为右转）航位推演整条替代轨迹，再用打分器同款中心距 range 逻辑对全部目标算 min range（碰撞阈值 50 m / 风险 1000 m）；同时算"保持基线航向"对照。代码 `tools/original_gnc/r11_attribution.py`。

## 3. 逐遭遇时间线（关键数字）

**fan-MS-E0 t2（run de40b477）**：t1 ACTIVE/COMMITTED 5.3 s（追越，dcpa_detect 22.2 m）；t2 检测 398.0 s（range 3050 m，右舷）；**改向被记于 559.9 s：psi -87.2° vs 基线 -77.2°（dev -10.0°），cref 全程 -85.0° 恒定，sref 6.68→4.63（565 s，leg-2 名义降速）**；t2 此时 range 2550.8 m、右舷 +92.8°，primary = t1。planner 605–940 s：turn_sign=0、spd_scale=1.0、phase=RETURN、encounters 全 clear。实际 SOG 在 650–920 s 塌到 0.37–0.50 m/s（**规划器同期指令 4.63 m/s —— 是被控对象失速，不是减速决策**，但行为上构成 Rule 16"大幅降速"）。t2 lifecycle：608.9 s ACTIVE → **926.3 s PAST_CLEAR / 936.3 s RELEASED**；TS2 于 ≤1200 s 锚泊（SOG=0）；实录 min 324.1 m @1517.5 s = 本船（40932, 6957616，北向）通过锚定 TS2（40609, 6957635）的左正横。

**fan-MS-E0 t3**：检测 1094.5 s（range 2862 m，右舷 +13.5°）；**改向被记于 1128.6 s：psi 16.9°→6.6°（dev -10.2°），实为 cref 31.8°→3.2° 恢复斜坡的尾段（1080 s 起于 t3 检测之前）**，primary = t1；t3 于 665.3 s 曾 ACTIVE/COMMITTED、928.1/938.1 s 即 PAST_CLEAR/RELEASED；TS3 ≈1730 s 锚泊；min 542.3 m @1794.5 s（窗口末端，本船 (40953, 6958373) vs 锚定 TS3）。

**fan-MS-E4 t2（run a84e1fc7）**：与 E0 同构：检测 396.0 s；**改向被记于 504.7 s（dev -10.0°，cref -85.0° 恒定，sref 6.68 恒定）**；t2 612.9 s ACTIVE（avoidance_action_started）；SOG 塌至 0.389 m/s（-88.6%）；min 990.3 m @1800 s 窗口末端未收敛，TS2 已锚泊；本例 lifecycle 无 t2 释放事件（release_before_cpa=false）。

**vo-MS-E4 t2（run 7ceef4f5）**：追越 t1 于 38.2 s 完成（855.8 m）；**TS2 于 45.3 s 即 primary（PREEMPT_RESPONSE_TIME_EMERGENCY，预测 dcpa 26.9 m）**；VO 指令：speed 2.9 m/s（t≈10 s 起），course -64.7°→-61.9°→-59.1°→**-180.0°（t≈300–410 s）→-87.2°（t≈420 s）**→+19.7°（t≈1100 s 恢复）；艏向跟踪长期滞后指令 5–90°，psi 于 396.6 s 才越过打分器 10° 门限（基线取自 322.4 s 检测窗）。t2 lifecycle：43.7 s ACTIVE → 1372.5/1382.7 s PAST_CLEAR/RELEASED；TS2 ≤1200 s 锚泊；min 698.8 m @1800 s 未收敛。

## 4. 打分器含义（should the scorer attribute multi-target actions via primary-target projection?）

**应该，且证据已齐**——但"primary-target projection"要用**指令层**而非艏向层做，否则只是把错误记到别的账本上：

1. **改向检测改用 applied/planner course 指令**（trajectory.parquet 已含 `applied_course_ref_rad`；fan 另有 `maneuver_turn_sign`）。本例 4/4 的伪 port 改向在指令层不存在。
2. **改向→目标归属需事件链证据**（avoidance_action_started / primary_switched / active encounters 与改向时刻对齐），无证据不记账。按此规则 fan 三例记 0 笔针对 t2/t3 的改向；vo 一例会把 t≈200–300 s 的 port 摆动记到 t2（当时 primary）名下——这才是正确账本。
3. **锚泊目标重分类**：CPA 时目标 SOG≈0（场景抛锚腿）→ 记 `static_hazard`，只计净距，不套 Rule 14/15 方向义务（COLREG 交叉局面预设双方在航）。
4. **判定顺序**：`_verdict_crossing_give_way` 现把"改向 port"放在降速检查之前，一笔 56–89% 的 Rule 16 合规降速被方向读数直接否决——应并列呈现方向与降速证据，方向违规不吞并降速合规。
5. **"降速"的出处标注**：fan 两例的 SOG 塌陷（指令 4.63 m/s、实际 0.4 m/s）是对象级跟踪故障而非决策；账本可给合规分，但应记录 provenance（ commanded vs tracked），否则会掩盖一个真实故障。

按 1–4 重打分：4 例全部转为 COMPLIANT（speed-reduction 分支 89.0%/76.0%/88.6%/56.6%）或 no-action-required，同时以 `static_hazard` 注记 324/542/990 m 通过。

## 5. Register 文本候选（不实现）

- **R11a（打分器）**：colreg_scoring 首次改向检测迁移到指令层 + 事件链归属 + 锚泊重分类 + 方向/降速并列判定（§4.1–4.4）。
- **R11b（planner，既有候选的量化）**：lifecycle 过早释放——PAST_CLEAR/RELEASED 比真实 CPA 早 581–856 s（fan-E0 t2 936.3 s vs 1517.5 s；fan-E0 t3 938.1 s vs 1794.5 s；vo-E4 t2 1382.7 s vs >1800 s），释放判据应加"目标 SOG≈0 且位于本船走廊 N m 内"的抑制条件。
- **R11c（planner/被控层，新）**：fan-MS 的 SOG 塌陷（cmd 4.63 → 实测 0.37 m/s，持续 ~250 s）与 vo-MS 的艏向跟踪滞后（cmd -180° 未执行、psi 偏离 applied_course_ref 达 88°）——两个被控对象级故障，R11 的"89% 合规降速"实为前者副作用，值得独立立项。

## 6. 局限

- 右转反事实只验证**交通几何**（中心距足迹），未加载海图栅格验证搁浅约束（场景为 Romsdal 图层）；西南向替代航线的静态可行性未证。
- 反事实用记录 SOG + 艏向航位推演，不含控制器闭环——结论"右转对全目标可行"是几何必要条件而非可执行性证明。
- 判定基于单 seed（E0/E4），锚泊时刻（±10 s）由 SOG 采样推得。
