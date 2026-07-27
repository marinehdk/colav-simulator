# COLAV 闭环实现追踪

本表定义稳定需求 ID。状态只接受 `未开始`、`实现中`、`功能完成`、`数值确认`、`算法验证完成`。

| ID | 论文/架构来源 | 功能 | 公共接口 | 测试/证据 | 当前状态 |
|---|---|---|---|---|---|
| CTR-01 | 架构 4.1-4.7 | 坐标、单位、9xN 计划契约 | `ICOLAV.plan`、`validate_plan` | `test_experiment_contracts.py` | 功能完成 |
| CTR-02 | 架构 9.1 | 独立随机流 | `RunSpec.seeds` | seed 确定性测试 | 部分实现：独立派生/记录完成，通用 tracker seed 注入待扩展 |
| EXP-01 | 论文 Fig. 1 | 单一真实执行链 | `SimulationSession` | 离线/Web 逐步一致性 | 功能完成 |
| EXP-02 | 架构 M11 | 可复现实验定义 | `RunSpec`、`RunManifest` | manifest round-trip | 功能完成 |
| EXP-03 | 架构 M09/M11 | 证据包 | `EvidenceWriter` | 六类产物读取测试 | 功能完成 |
| EXP-04 | 架构 5.3 | 批量矩阵与失败保留 | `BatchRunner` | 成功/失败混合矩阵测试 | 功能完成 |
| EVA-01 | 论文 Sec. II-C | Evaluator 可替换接口 | `Evaluator.evaluate` | 解析/异常输入测试 | 功能完成 |
| EVA-02 | 论文 Rule 13-17 | 遭遇分类与阶段 | `PairEvaluation` | HO/CR/OT 人工轨迹 | 功能完成 |
| EVA-03 | 论文 Table I/II | 论文评分字段 | `EvaluatorResult.metrics` | 表字段完整性测试 | 功能完成 |
| EVA-04 | 未公开官方实现 | 数值校准 | 同一 Evaluator 接口 | 两位小数表格对齐 | 未开始 |
| WEB-01 | 项目扩展 | 真实 Web 会话 | `/api/sessions` | API 状态机测试 | 功能完成 |
| WEB-02 | 项目扩展 | 版本化实时遥测 | `/ws/sessions/{id}` | WebSocket schema 测试 | 功能完成 |
| WEB-03 | 项目扩展 | 真实 ENC、结果、证据 | ENC/result/artifact API | Playwright + 像素检查 | 功能完成 |
| PAP-01 | 论文 Fig. 2/Table I | 随机对遇场景 | `paper_ccta2023_head_on` | 500 s、0.1 s、固定 episode | 功能完成 |
| PAP-02 | 论文 Fig. 4/Table II | 四船场景 | `paper_ccta2023_multiship` | 三类船对关系 | 功能完成 |
| INT-01 | 扩展 | VIMMJIPDA | tracker registry | 配置路径、真实闭环证据包 | 短闭环完成；完整感知矩阵待验收 |
| INT-02 | 扩展 | 官方 PSB-MPC | `PSBMPCColav` | ENC polygons + tracks + solver 诊断 | G1：0.2 s 烟测通过；完整场景 Eigen abort |
| INT-03 | 扩展 | RRT* | `RRTStarColav` | hazard/CDT/tree-growth | 实现中：固定论文场景返回 `INFEASIBLE` |
| INT-04 | 扩展 | RLMPC | registry direct adapter | 真实 solver 状态 | 实现中：`casadi` 依赖门未通过 |
| INT-05 | 最终目标 | 自研 MPC | `module:factory -> ICOLAV` | 同 episode 基准矩阵 | 接口完成：算法待提供 |

`EVA-04` 完成前，任何报告只能标记 `functional_reproduction`，不能标记 `numerical_reproduction`。

外部算法门证据见 `Integration-Evidence.md`；Evaluator 来源和数值边界见 `Evaluator-Audit.md`。
