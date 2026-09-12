# 同事同步修改包（colleague sync package）

日期：2026-09-12。用途：将本轮集成验证（p4→p6，24格产品矩阵、seed 0）中**需要原版 FCB45 栈侧同步修改**的问题打包交付。每条：证据 → 提案 → 预期效果 → 验证方法。背景文档：[登记册](2026-09-11-colleague-structural-issues-register.md)（R1-R12）、[D3 评估](2026-09-12-original-gnc-d3-assessment.md)、[COLREG 评分](2026-09-12-original-gnc-colreg-scoring-p4.md)。

## 一、必改（任务可行性被阻断）

### S1 = 登记册 R3：avoidance 速度帽 3.2 m/s 击穿任务时窗
- **证据**：p5/p6 全 16 VO/Fan 格 ownship 平均 SOG 0.93–4.38 m/s（任务假设巡航 6–8 m/s）；VO-HO 均值 3.2–3.7≈帽值、fan-OT 3.07–3.45≈帽值、fan-MS 1.69–1.77；goal 仅 2-3/16。机理：每次动态遭遇偏差段 surge 压 3.2 m/s（`ship_guidance_node.cpp:2536-2543` target或predecessor为avoidance即激活）+ course τ=86.78 s 回线耗时 → multiship 持续遭遇=全程半速。
- **提案**：区分 `avoidance`（巡航速路径跟踪）与 `emergency_avoidance`（限速）——behavior_mode 字段已有 non-emergency/emergency 区分基础（`active_route_manager_node.cpp:873-875`）；或帽值按 TCPA 分级（远距全速、近距限速）。
- **预期**：遭遇段过境时间 ~2×→~1×；goal 完成率显著回升（配合 S3）。
- **验证**：修后 p7 重跑 24 格 goal 计数 + 遭遇段 transit time 遥测对比（数据采集管道已就绪）。

### S2 = 登记册 R12/R11b：lifecycle 放行时刻与真实 CPA 脱同步
- **证据**：fan-MS-E0 lifecycle 936 s 放行 t2，真实 CPA 1517 s @324 m（放行后 581 s 才到最近点）；同族 t3 放行 856 s 早于 CPA。我方已加"realized range 仍在关闭则不放行"守卫（我侧缓解），但**放行判据本身的预测几何**在原版侧仍按乐观包络计算。
- **提案**：release/complete 判据用一阶滞后感知的 CPA 预测（τ_course 已由我方通过 Maneuverability 传入的先例）；锚定目标（SOG≈0）不应进入 Rule 15 通道（应归静态危害）。
- **预期**：放行时刻与真实 CPA 对齐；不会再出现"放行后仍接近"窗口。
- **验证**：lifecycle_events 放行时刻 vs realized CPA 对照扫描（工具已在 r11_attribution.py）。

## 二、条件修改（需对齐后我方才能动）

### S3 = 登记册 R9 附带：warm-seed 修复被不变量测试阻止
- `test_colav_strict_warm_started_seed_is_not_displaced_by_repair` 编码了"接受几何不被修复迭代替换"的意图。我方遇到：CS-E0 timeout 迭代可行但 warm seed 行违约（viol 3.3）→ seed 回退不触发 → 横漂 551.6 m。需确认不变量意图（是"永不替换"还是"仅质量门通过才替换"）——若是后者，我方可按质量门替换。
- **验证**：确认后我方实现+单测，mid CS/OT 格候选接受率回升。

## 三、观察项（原版行为，请确认为设计意图或排期）

1. **末端低速爬行（R14，未定位归属）**：多格末端 SOG 跌至 0.40–0.56 m/s 而参考速度 3.2 m/s、`decel_distance_tight` 触发数百次——疑似 guidance 减速距离判据在低速段反复触发（`ship_guidance_node` 减速调度）。请确认减速调度逻辑；我方提供 trajectory 证据。
2. **spliced 几何角降级（R13）**：frozen route manager 对偏航折线的转弯舒适度降级曾把航线速度压到 0.892 m/s 平台（我方 bridge 已绕过主因，但原版 corner-degradation 对 >某角度折线整线降速的行为值得复核——避碰航线天然多折点）。
3. **静止目标分类**：SOG≈0 目标进入 Rule 15 give-way 通道（R11 分析确认 4 例）——建议导航模式下锚定/系泊目标归静态危害。
4. C级Mock 系数标定积压（长期，实船数据后）；R1 下限参数化（低优先——实测 150 m 层未构成瓶颈，request→accepted ≈0 s）。

## 四、我方已修（供同步参考，无需对方动作）

fan 静态约束标志绑定化（94c1ae58，避免远距 ENC 危害锁死意图）；fan 速度帽 plumb（7e20ccdd+936cd364）；lifecycle realized-range 放行守卫（463a0338）；VO 速度窗分辨率/闩锁/give-way 右转约束（74b2a0bc+c17ad1e1）；Mid τ感知staging/预算floor/走廊对称（8d26532a/51eea350/4a49b947 等）；评分器 v2 归因修正（e0f446d2——4 例"不合规"确认为评分误判，0 真违规于该批）。

## 五、验证基线（交付时状态）

p6（starboard 约束重跑前的 24 格）：COMPLETED 18、硬安全评估格全 PASS、goal 3、COLREG v2 12/9/1/4、Mid TRACKABILITY 0 拒、addressable 拒因 ~15。p6b（VO 右转修复后）见补记。复现命令见各评估档。
