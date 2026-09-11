# 同事侧结构性问题登记册（colleague structural issues register）

日期：2026-09-11。性质：沟通契约 + 修改门。登记对象：原版 FCB45 栈（同事开发内容）与我们适配层之间暴露的结构性问题。定位与比较规则见[双栈定位 ADR](2026-09-11-dual-fcb45-stack-positioning.md)；升级口径见[诊断运行政策](2026-09-11-original-gnc-diagnostic-policy.md)。

## 规则（约束性）

**同事开发内容只允许在满足以下两个条件后被修改：(1) 登记册已存在对应条目；(2) 已有验证过的修复（verified fix）证明该问题已解决。**登记册是与同事的沟通契约：条目即工单，证据列即问题陈述，验证结果列是结账栏。任何对 colleague-side 内容（冻结源、原版 C++/Python 模块、原配置）的修改若不满足该条件即为违规，必须回退。我们侧适配器内容的修改不设此前置，但涉及 colleague-side 行为假设的缓解须回写对应条目。

状态枚举：`open` / `adapter-mitigated` / `proposed-to-colleague` / `verified-fixed`。层级枚举：`colleague-side` / `our-side` / `shared`。

## 登记册

| ID | 状态 | 层级 | 问题 | 证据 | 适配器侧缓解 | 同事侧修改建议 | 预期效果 | 验证方法 | 验证结果 |
|---|---|---|---|---|---|---|---|---|---|
| R1 | open | colleague-side | engagement floor：首个变更航点须距本船 ≥150 m（avoidance 层）/ ≥500 m（strict 层），6 m/s 下即机动前 ≥25 s / ≥83 s 已不可及；短 TCPA 遭遇（head-on、近距 crossing）无法在有效窗口内发出可接纳的避碰 route | `coordinate_transform_node.cpp:223,226`（500/150 m 参数）、`:856-876`（first-changed 拒绝路径）；`ship_config.yaml:965,968`；准入审计 11,048 次 first-change 拒绝（24 格全事件，worktree `build/original-final-route-admission-audit.json`） | 已落地（层内合规）：prefix-splice 使计划在 150 m avoidance 层内可接纳——fan×CS×E4 461/461、vo×multiship×E0 70/70、mid 首批 17 接纳（2026-09-11 seam commits）。150 m 下限本身对短 TCPA 仍是结构性约束，适配器不可越 | avoidance 层下限参数化至 ~60 m，或改为按距离比例的 guard（τ×速度），保留 500 m 名义值 | 短 TCPA 遭遇存在 ≥1 个可接纳窗口；D2 拒因直方图中 first-changed 类降为残差（诊断政策 D2） | CT 边界向量 59.99 / 60.01 m 两侧 + 24 格 rerun 中 t_detect→first-accepted < 25 s | seam 层内接纳已验证（上列 cells）；下限参数化未动，待与同事沟通 |
| R2 | verified-fixed | our-side | Mid-MPC t=0 双重失配。【2026-09-11 更正：原诊断两项均误。】(1) "IPOPT 首解超时"系误诊——实际为受控质量停止（`quality_stop_requested`、best-feasible-iterate、`optimization_quality_passed: true`），designed exit，非 deadline 问题。(2) "speed 通道一阶不合格 R²=0.344"系**我们测量基错误**：v1 用导数基（有限差分加速度相关度）而非轨迹预测基。轨迹基重拟合（exact ZOH 离散化 + active window，同一 trace）：speed τ=24.07 s **R²=0.9848**、course τ=86.78 s **R²=0.9898**——一阶即合格；二阶被正确拒绝（speed: `DEGENERATE_SECOND_POLE_NOT_IDENTIFIABLE`；course: `NOT_ADOPTED_IMPLAUSIBLE_DC_GAIN` gain=1.149）。真正 L4 拒绝链根因：`_active_capability` 将 original 后端映射 `unsupported:*` + 冻结 `allowed_capability_tuples` 拒绝 | v1 误诊：`response_approximation.json`@schema-v1 导数基；修复：同文件 schema-v2 + `colav_simulator/original_gnc/qualification.py`（阈值 0.90 显式入码）+ `integrations/mid_mpc_ipopt.py:1622+` `_active_capability` 发射 `original-gnc:first_order_lag:source_control`（不合格自动回落 unsupported）+ `mid_mpc_acceptance.py:276+` `allowed_capability_tuples` 文档化扩展（D-ladder 引用）；worktree commits `014c8a36`/`89ec13dd`/`055b0b5c` | 不适用（我们侧修复）| **同事侧建议撤回**：speed 通道无模型缺陷，误报源于我方度量基；C 级 Mock 系数标定积压与本案无关、另行跟踪 | mid 格 t=0 不再 TRACKABILITY 拒绝；capability 诚实 gating | 单元：阈值+映射 red→green（201 passed，含 41 capability 子集）；E2E：mid×crossing_give_way×rule15×E0 `coordinate_accepted` 0→**17**、18/18 forwarded、**0** TRACKABILITY 拒绝 | 已验证：单元全绿 + 单格 e2e；8 格全量随 D2 campaign 补齐 |
| R3 | adapter-mitigated | colleague-side | avoidance 速度帽：导引层对 avoidance 标记航点把 surge 压到 3.2 m/s。【2026-09-11 已证实 leg-scoped】：`emergency_avoidance_active = target或predecessor为avoidance`（`ship_guidance_node.cpp:2536-2543`），cap 作用范围=标记段+衔接段，非 route-global | `ship_guidance_node.cpp:75-81`、`:2536-2543`、`:5970-5976`；`ship_config.yaml:475-477`（`emergency_avoidance_speed_cap_mps: 3.2`）；cap 参数默认 `:449` | 已落地：mixed tagging（prefix/tail 保留 reference 模式，仅 deviation 段标 avoidance）→ cap 暴露=N_deviation+1 段，最小化；两 smoke 格 COMPLETED+hard_gate PASS 佐证 | 可选优化：区分 "avoidance"（巡航速度路径跟踪）与 "emergency_avoidance"（限速），或上调 3.2 m/s；当前 leg-scoped 下非必需 | 避碰段仍限 3.2 m/s（6→3.2 需 ~35 s @0.08 m/s²）——如需全速避碰机动再升级此条 | avoidance 段 transit time 遥测 + COLREG P_delay 重打分 | leg-scoped 证实（源码+cells 运行）；transit time 遥测随 D2 campaign 采集 |
| R4 | open | shared | 规划器与原版可行性包络的结构性不可行：VO 6 格仅剩 stop/last-resort 候选被拒；Fan 7 格在原包络（最低操舵 3 m/s、回转 R≈380–450 m、XTE 100 m）下不存在连续 footprint-safe 轨迹；1 格到达框架 goal 但最小船体净距 15.9 m < 50 m 硬门。非 seam 问题：桥接无 bug，是规划器约束输入与可行性预门缺失 | [避碰集成报告 §关键不兼容与 24 格表](2026-09-10-original-gnc-integration-report.md)（vo-* 六格 FAILED；potocnik_colreg_fan_mpc 七格 `NoContinuouslyFootprintSafeTrajectory`；CS-E4 15.921 m）；`product-acceptance-summary-v2.json` | 无：不可行问题不能靠适配器翻译掉 | 同事侧待定：先按 ADR 比较规则产出成对运行证据后发起沟通；我们侧 planner track：把原包络（min steerage / 回转半径 / XTE / 减速限制）作为规划约束喂入并加 feasibility pre-gate | 规划器只输出原栈可接纳的候选；拒因直方图从"结构性不可行"转为正常重规划流 | 24 格 rerun：VO/Fan 可行性拒绝降为残差；goal 到达格净距 ≥50 m | |
| R5 | open | our-side | 证据基础设施：A4000 R0 trace 曾为唯一副本（sole-copy risk）；原始证据图未入库 | 已缓解：2026-09-11 完成 2962 文件 / 25.6 GB 归档并逐哈希核验至 `/Users/marine/Code/external_sources/L4-5_r0_traces_20260824/`（tarball SHA256 `153a0abd07a2855bf44d3ff7025c4cf26cfd346c031b6b21917cb07caa941012`，见该目录 `verification.json`）。未决：所在盘 96% 满，需迁出并建第二地点副本（3-2-1）；worktree 内 77 张原始证据 png 未纳入版本管理 | 已落地：冷归档 + 哈希验证；待办：异地第二副本 | 不适用（我们侧基础设施） | R0 原始 trace 具备可复核性，fidelity 链证据不随单盘故障丢失 | 第二副本落地 + 抽样哈希复验；png 以 evidence bundle 归档并登记 SHA | 归档+核验完成；第二副本未落地 |
| R6 | open | shared | Mid 资格解锁后的任务层残留：被接纳的 Mid 路径未到达 reference splice margin（mission-arrival 判据失败）——非准入拒绝，属 D2/D3 任务完成层 | T6b e2e（mid×crossing_give_way×E0）：`coordinate_accepted=17` 但 run-level "Accepted Mid path never reaches the reference splice margin"；worktree `build/original-qualification-e2e/` | 待 D2 campaign 定位：splice 几何 vs planner 到达判据 vs 原版跟踪末端行为 | 视根因归属再定（planner arrival 判据 / splice 末端构造 / 原版 guidance 末端行为） | mid 格 goal/arrival 通过 | 24 格 campaign 中 8 个 mid 格的 goal/arrival 统计 + 末端轨迹对照 | |

## 维护约定

- 新问题先登记后行动；条目只增不改写历史，状态与验证结果列滚动更新。
- D2 拒因直方图（[诊断政策](2026-09-11-original-gnc-diagnostic-policy.md)）是本登记册的输入源之一：可归因类出现即建条目，降为残差方可转 `verified-fixed`。
- 对同事的沟通以条目为单位输出（问题 + 双方 trace + 建议 + 验证方法），不整册转发。

## 关联文档

- [原版 GNC 诊断运行政策](2026-09-11-original-gnc-diagnostic-policy.md)、[双 FCB45 栈定位 ADR](2026-09-11-dual-fcb45-stack-positioning.md)。
- [原版 GNC 避碰集成报告](2026-09-10-original-gnc-integration-report.md)、[嵌入保真报告](2026-09-10-original-gnc-fidelity-report.md)、[迁入方案](2026-09-10-original-gnc-migration-plan.md)、[源运行报告](2026-09-10-original-gnc-source-runtime-report.md)。
- [GNC ↔ COLAV 集成调研](2026-09-11-gnc-colav-integration-survey.md)。
