# 原版 GNC D3 层评估（p5 快照）

日期：2026-09-12。前置：[P2-P4 评估](2026-09-12-original-gnc-p2-p4-evaluation.md)（D2 三判据 PASS）。本档汇总 D3 修复轮（R8 预算 floor `51eea350`、R9 τ 感知 recovery staging `eaba2de6`、R10 τ 感知 action deadline `1d738296`+激活 `02120543`、VO 速度窗 `2862e6ff`、Woerner 评分器 `a70c454b`）与 p5 全量重跑（24 格、seed 0），给出 **D3 判定**。

## p5 结果

### VO/Fan（`product-campaign-p5-vofan/`，summary `product-acceptance-summary-p5-vofan.json`）

**16/16 COMPLETED + 16/16 硬安全 PASS**（与 p4 持平）。goal 1→**2**：fan-CS-E0/E4 转 True；**vo-CS-E0 回落 F**（速度窗改动副作用）。净距全部 ≥165 m。

### Mid（`product-campaign-p5-mid/`）

| 格 | p4 | p5 | 解读 |
|---|---|---|---|
| OT-E4 | QUALITY_CPA_RELEASE | **COMPLETE + 硬安全 PASS（1298 m）** | 新达标 |
| CS-E4 | COMPLETED+PASS | L4 早拒（~17 s wall） | **回归**：R9 τ 感知 staging 改变候选族，CS 候选不再被接受——需再调（open-2） |
| HO-E0 | INFEASIBLE @335 s（预算饥饿） | 诚实 L4 拒（过墙） | R8 floor 生效：预算饥饿消除，暴露下一层=候选质量 |
| HO-E4 | INFEASIBLE @335 s | INFEASIBLE（更晚/不同 NLP） | 部分进展 |
| MS-E0/E4 | COLREG_ACTION_DEADLINE @80 s | NUMERICAL_FAILURE @长时（282/819 s wall） | R10 deadline 只延长不缩短生效；死因转为数值 |
| OT-E0 | QUALITY_CPA_RELEASE | L4 拒（358 accepted） | 同族待调 |
| CS-E0 | QUALITY_RECOVERY_SUFFIX | L4 拒 | 同族待调 |

Mid 达标 1/8（OT-E4）；accepted publishes 153–13308 全格为正；TRACKABILITY 拒保持 0。

## D3 判定（[诊断政策](2026-09-11-original-gnc-diagnostic-policy.md) D3 = 硬安全 + 任务完成 + COLREG 行为评分 + 主套件无新失败）

| 轴 | 结果 | 证据 |
|---|---|---|
| 硬安全 | **PASS** | VO/Fan 16/16 + Mid 2/2（OT-E4、评估格）全 PASS；零 hard-gate FAIL |
| 任务完成（goal） | **FAIL** | goal 3/24（vo/fan 2 + mid 0 确认；OT-E4 goal 字段待口径确认）——主因见下"低速巡航诊断" |
| COLREG 行为 | **PARTIAL/FAIL** | Woerner 评分（[报告](2026-09-12-original-gnc-colreg-scoring-p4.md)）：10 COMPLIANT/8 PARTIAL/**4 NON_COMPLIANT**（全为 MS give-way port-side 改向）/6 NOT_EVALUABLE |
| 主套件回归 | **PASS（零新增）** | 全量 1881 passed / 9 skipped / **32 failed——同 32 项在 main 基线逐一复现（1774 s 对照跑），分支引入回归 = 0**；评分器 15/15 单独通过。已知环境项：test_behavior_generator（main 同败，FileNotFoundError）；全量单进程存在 gui_server 遗留 finalize 线程（GEOS）×新测试并发段错误——分段跑规避（`--ignore tests/test_colreg_scoring.py` + 单独跑） |

**D3 = NOT PASSED → `diagnostic_only` 保持 true。** 诚实结论：准入与安全已稳定（两轮全绿）；剩余三缺口全部在任务层与行为层，且主因已有结构性定位。

## 低速巡航诊断（任务完成缺口主因，给同事的核心证据）

p5 全 16 VO/Fan 格 ownship **平均 SOG 0.93–3.74 m/s**（任务假设巡航 6–8 m/s）；fan-CS 双格 goal=True 仅因 goal 近（t=670/890 s 提前结束）。拆解：

1. **3.2 m/s 避碰帽（R3，colleague-side）**：每次动态遭遇偏差段限速 3.2 m/s；multiship 持续遭遇 → 全程近半速。VO-HO 均值 3.2–3.7 ≈ 帽值；fan-OT 3.1–3.5 ≈ 帽值。τ_course=86.78 s 下偏离+回线耗时巨大，两者相乘击穿任务时窗。**建议（登记册 R3 升级）：区分 avoidance（巡航速跟踪）与 emergency_avoidance（限速），或帽值随 TCPA 分级。**
2. **fan-HO 异常低速（0.93–1.38 m/s，低于帽）**：待查（候选：恢复段速度未回升/rollout 命令低）——open-3。
3. 名义段巡航恢复是否及时：R-B3 已隔离静态帽，动态帽作用中——与 1 同族。

## 登记册变更摘要

- R3：**升级 proposed-to-colleague**（附 p5 平均 SOG 表与 transit 时序数学）
- R8：verified-fixed（HO-E0 过墙复现；floor 生效）
- R9：adapter-mitigated→**部分回归**（OT-E4 达标、CS-E4 回归、CS-E0/OT-E0 同族待调）
- R10：adapter-mitigated（MS 过 deadline 墙，死因转 NUMERICAL_FAILURE）
- 新增 R11（MS give-way port-side 改向不合规族）、R12（fan-MS lifecycle 936 s 放行 vs 真 CPA 1517 s 脱同步）
- R6：Mid 达标 1/8（OT-E4）

## 证据

`build/original_gnc-glibc-v8/product-campaign-p5-vofan/`、`product-campaign-p5-mid/`（含 per-cell run_dir/original-gnc.json execution_events）；COLREG 评分 `colreg-scoring-p4/`（p5 评分待跑，评分器已就绪：`tools/original_gnc/colreg_scoring.py`）。复现命令同 P2-P4 评估档。
