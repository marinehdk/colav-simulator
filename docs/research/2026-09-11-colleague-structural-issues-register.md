# 同事侧结构性问题登记册（colleague structural issues register）

日期：2026-09-11。性质：沟通契约 + 修改门。登记对象：原版 FCB45 栈（同事开发内容）与我们适配层之间暴露的结构性问题。定位与比较规则见[双栈定位 ADR](2026-09-11-dual-fcb45-stack-positioning.md)；升级口径见[诊断运行政策](2026-09-11-original-gnc-diagnostic-policy.md)。

## 规则（约束性）

**同事开发内容只允许在满足以下两个条件后被修改：(1) 登记册已存在对应条目；(2) 已有验证过的修复（verified fix）证明该问题已解决。**登记册是与同事的沟通契约：条目即工单，证据列即问题陈述，验证结果列是结账栏。任何对 colleague-side 内容（冻结源、原版 C++/Python 模块、原配置）的修改若不满足该条件即为违规，必须回退。我们侧适配器内容的修改不设此前置，但涉及 colleague-side 行为假设的缓解须回写对应条目。

状态枚举：`open` / `adapter-mitigated` / `proposed-to-colleague` / `verified-fixed`。层级枚举：`colleague-side` / `our-side` / `shared`。

## 登记册

| ID | 状态 | 层级 | 问题 | 证据 | 适配器侧缓解 | 同事侧修改建议 | 预期效果 | 验证方法 | 验证结果 |
|---|---|---|---|---|---|---|---|---|---|
| R1 | open | colleague-side | engagement floor：首个变更航点须距本船 ≥150 m（avoidance 层）/ ≥500 m（strict 层），6 m/s 下即机动前 ≥25 s / ≥83 s 已不可及；短 TCPA 遭遇（head-on、近距 crossing）无法在有效窗口内发出可接纳的避碰 route | `coordinate_transform_node.cpp:223,226`（500/150 m 参数）、`:856-876`（first-changed 拒绝路径）；`ship_config.yaml:965,968`；准入审计 11,048 次 first-change 拒绝（24 格全事件，worktree `build/original-final-route-admission-audit.json`） | 无：几何门在原坐标模块内，适配器不应也不能绕过 | avoidance 层下限参数化至 ~60 m，或改为按距离比例的 guard（τ×速度），保留 500 m 名义值 | 短 TCPA 遭遇存在 ≥1 个可接纳窗口；D2 拒因直方图中 first-changed 类降为残差（诊断政策 D2） | CT 边界向量 59.99 / 60.01 m 两侧 + 24 格 rerun 中 t_detect→first-accepted < 25 s | |
| R2 | open | shared | Mid-MPC t=0 双重失配。我们侧：IPOPT 首解 t=0 超时（User_Requested_Stop，1.0–2.3 s 时限），8/8 mid 格 L4 `TRACKABILITY_CAPABILITY` 拒绝。同事侧：speed 通道一阶响应不合格 τ=29.62 s、R²=0.344（course τ=73.49 s、R²=0.941 通过），一阶近似不足以支撑速度通道预测 | worktree `build/original_gnc-glibc-v8/product-acceptance-summary-v2.json`（8/8 L4 拒绝、IPOPT 终态与迭代数）；`colav_simulator/original_gnc/data/response_approximation.json`（`UNQUALIFIED_FIRST_ORDER_APPROXIMATION`） | 我们侧：首解 deadline / warm-up——t=0 前预解或放宽首解时限，消除 t=0 全格拒绝 | 同事侧：speed 通道改二阶/带滞后响应模型；最终做真实 thrust-speed 标定（现有水动力系数均为 C 级 Mock，见冻结源 `ship_config.yaml` mock 标签，待实船标定） | mid 8 格 t=0 不再因首解超时全拒；速度通道预测误差进入可接受带，trackability 资格可重估 | 我们侧：t=0 首解 Converged fixtures；同事侧：重拟 R² 达标阈值；联合：8 个 mid 格 t=0 通过 | |
| R3 | open | colleague-side | avoidance 速度帽：导引层对 avoidance 标记航点把 surge 压到 3.2 m/s。若标记按航段混合传播（leg-scoped），仅避碰段减速，可接受；若 route-global，则每个被接纳的避碰机动都全航线减速——减速限制 0.08 m/s² 下 6→3.2 m/s 需约 35 s | `ship_guidance_node.cpp:75-81`（emergency_avoidance 模式归类）、`:2536-2543`（目标或前一航点任一为 avoidance 即激活）、`:5970-5976`（cap clamp 与 `u_cmd=min`）；`ship_config.yaml:475-477`（`emergency_avoidance_speed_cap_mps: 3.2`） | leg-scoped 假设的缓解在测（标传染范围受控化）；若证实 route-global 则适配器无解 | 区分 "avoidance"（巡航速度路径跟踪）与 "emergency_avoidance"（限速）两类标记，或上调 3.2 m/s 帽 | 避碰机动的航段过境时间不再系统性拉长；COLREG 打分 P_delay 项恢复 | avoidance 段 transit time 遥测 + COLREG P_delay 重打分 | |
| R4 | open | shared | 规划器与原版可行性包络的结构性不可行：VO 6 格仅剩 stop/last-resort 候选被拒；Fan 7 格在原包络（最低操舵 3 m/s、回转 R≈380–450 m、XTE 100 m）下不存在连续 footprint-safe 轨迹；1 格到达框架 goal 但最小船体净距 15.9 m < 50 m 硬门。非 seam 问题：桥接无 bug，是规划器约束输入与可行性预门缺失 | [避碰集成报告 §关键不兼容与 24 格表](2026-09-10-original-gnc-integration-report.md)（vo-* 六格 FAILED；potocnik_colreg_fan_mpc 七格 `NoContinuouslyFootprintSafeTrajectory`；CS-E4 15.921 m）；`product-acceptance-summary-v2.json` | 无：不可行问题不能靠适配器翻译掉 | 同事侧待定：先按 ADR 比较规则产出成对运行证据后发起沟通；我们侧 planner track：把原包络（min steerage / 回转半径 / XTE / 减速限制）作为规划约束喂入并加 feasibility pre-gate | 规划器只输出原栈可接纳的候选；拒因直方图从"结构性不可行"转为正常重规划流 | 24 格 rerun：VO/Fan 可行性拒绝降为残差；goal 到达格净距 ≥50 m | |
| R5 | open | our-side | 证据基础设施：A4000 R0 trace 曾为唯一副本（sole-copy risk）；原始证据图未入库 | 已缓解：2026-09-11 完成 2962 文件 / 25.6 GB 归档并逐哈希核验至 `/Users/marine/Code/external_sources/L4-5_r0_traces_20260824/`（tarball SHA256 `153a0abd07a2855bf44d3ff7025c4cf26cfd346c031b6b21917cb07caa941012`，见该目录 `verification.json`）。未决：所在盘 96% 满，需迁出并建第二地点副本（3-2-1）；worktree 内 77 张原始证据 png 未纳入版本管理 | 已落地：冷归档 + 哈希验证；待办：异地第二副本 | 不适用（我们侧基础设施） | R0 原始 trace 具备可复核性，fidelity 链证据不随单盘故障丢失 | 第二副本落地 + 抽样哈希复验；png 以 evidence bundle 归档并登记 SHA | |

## 维护约定

- 新问题先登记后行动；条目只增不改写历史，状态与验证结果列滚动更新。
- D2 拒因直方图（[诊断政策](2026-09-11-original-gnc-diagnostic-policy.md)）是本登记册的输入源之一：可归因类出现即建条目，降为残差方可转 `verified-fixed`。
- 对同事的沟通以条目为单位输出（问题 + 双方 trace + 建议 + 验证方法），不整册转发。

## 关联文档

- [原版 GNC 诊断运行政策](2026-09-11-original-gnc-diagnostic-policy.md)、[双 FCB45 栈定位 ADR](2026-09-11-dual-fcb45-stack-positioning.md)。
- [原版 GNC 避碰集成报告](2026-09-10-original-gnc-integration-report.md)、[嵌入保真报告](2026-09-10-original-gnc-fidelity-report.md)、[迁入方案](2026-09-10-original-gnc-migration-plan.md)、[源运行报告](2026-09-10-original-gnc-source-runtime-report.md)。
- [GNC ↔ COLAV 集成调研](2026-09-11-gnc-colav-integration-survey.md)。
