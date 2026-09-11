# 原版 GNC 诊断运行政策（diagnostic_only 政策）

日期：2026-09-11。性质：治理决策，对 `original_gnc` 后端的全部实验/产品运行生效。分工：两栈各管什么见[双栈定位 ADR](2026-09-11-dual-fcb45-stack-positioning.md)，逐条工程问题见[同事侧结构性问题登记册](2026-09-11-colleague-structural-issues-register.md)，资格升级（本文）只回答"哪一次运行今天可以算什么"。

## 决策

`diagnostic_only=True` 保持为所有 original-backend（`original_gnc`）运行的默认值，且不提供按 case 关闭的旁路。原版后端的任何运行结果，在分级资格验收（下文 D1→D2→D3）通过之前，一律不得计为产品验收（product acceptance）。

这是诚实门（honesty gate），不是缺陷标签：24 格产品入口 0 个原坐标模块接受的避碰 plan、0 个同时任务完成与硬安全通过已成文（[避碰集成报告](2026-09-10-original-gnc-integration-report.md)）。运行器在存在原版证据链时自动打标：`manifest.diagnostic_only=True`，理由 `original_gnc_response_unqualified`（[runner.py:747-748](../../colav_simulator/experiment/runner.py)）；目录侧接受级别固定 `EXPERIMENTAL_ORIGINAL_SOURCE`（[original_gnc/catalog.py](../../colav_simulator/original_gnc/catalog.py)）。本政策只是把代码里已有的事实升格为决策：这些结果今天只能用于诊断与集成定位。

## 升级阶梯

每一级都不会自动翻转任何开关；每级要求记录在案的证据（evidence bundle + 指针）。上一级通过不构成下一级证据，下一级重新计时。

### D1 准入（admission）

- 门：seeded acceptance 子集中，VO / Fan / Mid 三个规划器各自至少产生 1 条被原坐标模块 ACCEPTED 的避碰 route。
- 产物：`coordinate_accepted_ids > 0`，逐规划器记录 plan/route id、接受时刻与几何上下文。当前基线为 0/24，见 24 格全事件准入审计（`zero_accepted_avoidance_routes=True`）。

### D2 安全（safety）

- 门：全 24 格重跑，同时满足三条：硬安全零失败；≥80% 格存在 ≥1 个被接受的避碰 plan；拒因直方图中三个可归因类降至残差（仅长尾，不再构成主要失败类）——
  - route update too frequent（原 10 s 最小更新间隔保护）；
  - first changed waypoint too close（500 m 名义 / 150 m avoidance 层下限，工程账见登记册 R1）；
  - lateral offset exceeds limit under avoidance tier（100 m 名义 / 500 m avoidance 层横向跳变上限）。
- 产物：24 格 rerun 审计 + 拒因直方图前后对照；登记册对应条目（如 R1）状态随之更新。

### D3 产品（product）

- 门：全 24 格同时通过：硬安全 + 任务完成（原 GNC 末端与框架 goal、统一位置/速度判据分别保留，不互替）+ COLREG 行为打分（Woerner 式：安全裕度 + 任务达成 + 行为判断，方法学依据见[集成调研 §4](2026-09-11-gnc-colav-integration-survey.md)）+ 主测试套无新增失败（以干净基线逐一复现口径为准，同[集成报告 §UI 与回归](2026-09-10-original-gnc-integration-report.md)）。
- 只有此时，才允许把 `diagnostic_only` 对该具体 preset 置 false：以配置变更落地，变更记录写入 catalog metadata（identity/config_hash 随之变化），并携带 evidence bundle 指针。不接受运行期自动翻转、UI 开关或单次运行覆盖；也不能以关闭任何原版保护门槛换取"通过"。

## 运行口径表

今天（2026-09-11）每一类运行各算什么：

| 运行类型 | python modular_gnc presets（legacy / ideal / without_guidance / full，8010 面） | original_gnc 栈（8014 面） |
|---|---|---|
| fidelity evidence | 不适用：python 栈没有保真对象，只算工程基线/回归证据 | 有效：R0→R1→E 固定输入与共同调度保真链已通过（[保真报告](2026-09-10-original-gnc-fidelity-report.md)），但不外推为自由闭环等价、控制循环硬实时或实船资格 |
| integration verification | 只验证 python 栈自身，不回答任何"同事栈是否支持我们的避碰"的问题 | 有效：24 格全事件准入审计、focused 回归、UI 会话等，证明的是兼容现状与失败可追溯性，不是避碰能力 |
| product acceptance | 可作为 python 栈的产品演示与回归验收证据；不得冒充 FCB45 产品验收 | 不算：0/24 验收；仅当某 preset 经 D3 通过并按上文记录配置变更后，方可对该 preset 起算 |

两栏结论不可互相替代：python 栈跑通不升级原版栈，原版栈保真通过不替代 python 栈回归。

## 关联文档

- [双 FCB45 栈定位 ADR](2026-09-11-dual-fcb45-stack-positioning.md) —— 两栈分工与成对比较规则。
- [同事侧结构性问题登记册](2026-09-11-colleague-structural-issues-register.md) —— D2 拒因类的逐条工程账（R1–R5）。
- [原版 GNC 避碰集成报告](2026-09-10-original-gnc-integration-report.md)、[嵌入保真报告](2026-09-10-original-gnc-fidelity-report.md)、[迁入方案](2026-09-10-original-gnc-migration-plan.md)、[源运行报告](2026-09-10-original-gnc-source-runtime-report.md)、[测试集成计划](2026-09-10-original-gnc-test-integration-plan.md)。
- [GNC ↔ COLAV 集成调研](2026-09-11-gnc-colav-integration-survey.md) —— Woerner 打分与无海试验证阶梯依据。
