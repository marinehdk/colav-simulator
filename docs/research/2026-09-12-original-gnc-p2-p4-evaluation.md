# 原版 GNC P2-P4 迭代评估（seam 修复后第二轮 D2 判定）

日期：2026-09-12。前置：[seam 准入 D2 评估](2026-09-11-original-gnc-seam-evaluation.md)（D2 = (a)FAIL/(b)PASS/(c)PASS）。本文记录 P2（planner 轨）/P3（bridge+mid 第二轮）修复与 P4 全量重跑（干净快照、seed 0）结果，以及 **D2 第二次判定**。

代码链：`dee60ece`（seam 合并基线）→ T8a VO/Fan（`e751e5f3`,`1665bfe7`,`ed4bb004`,`7ad674d0`,`d40d786f`）→ T8b Mid（`b45717e5`,`c3055592`,`7188ab6e`,`664a7908`）→ T10 Mid 二轮（`4a49b947`,`c8fa7414`,`d74e32a0`,`70928754`,`2e10d5e3`,`f0971c67`,`39a0be8e`）→ T9b bridge（`110e0ecd`,`0394772c`）。P4 重跑即此 HEAD。

## 修复内容（按根因）

**VO**（T8a）：速度网格加包络 mask（速度窗 [最小舵效 3 m/s, cap] + 限速 course 弧作 availability 非硬约束）；horizon = t_max + τ_course（206.8 s）；包络内 hysteresis 选点。激活延迟 32.5–112.5 s → **0**（4 格）。
**Fan**（T8a）：rollout 用 reported 响应（τ=max(报告值), yaw rate=min），不再比真船灵活；course 行按 adapter modulo 形式预 wrap（1-ULP 抖动消除，20 万样本验证）。
**Mid**（T8b+T10）：速度界 staging 到 rate-reachable 走廊；CPA 窗起点 min(TCPA, 违约物理可能时刻)、空窗回退全 horizon；走廊 re-entry 夹紧对称化（原 starboard-only bug）；CPA 硬窗含 recovery knot+1（覆盖只增不减）；终端制动尾部（lag-based，落 executed band）；恢复后横漂软屏障（843.8→551.6 m）；`_mid_deviation` 短于 splice margin 时 hold 活跃航线不 raise（frozen-manager 语义忠实）。
**Bridge**（T9b `110e0ecd`，R-B1/B2/B3）：intent 变更加数值容差（替代逐 tick 精确比较）；splice 偏移/rejoin 一律对 **nominal 任务参考**计算（nominal 镜像与 accepted 路径分离）；manager 降解速度**不**吸收进参考镜像（棘轮消除）；internal-return 参考 sub-floor（<30 m）prefix 腿清理；intent 丢弃必带原因遥测（零静默）；静态危害偏差不再触发 avoidance tag（3.2 m/s 帽仅动态遭遇偏差）。

## P4 结果（seed 0，24 格）

### VO/Fan 16 格（`build/original_gnc-glibc-v8/product-campaign-p4-bridge/`，summary `product-acceptance-summary-p4-bridge.json`）

**16/16 COMPLETED，16/16 硬安全 PASS**。基线（seam-01）：13 COMPLETED / 1 硬安全 FAIL。

| 格 | 结果 | 净距 m | goal | 备注 |
|---|---|---|---|---|
| vo-HO-E0/E4 | C+PASS | 453.7 / 450.2 | F/F | seam-01 FAILED(INF)→修复 |
| vo-CS-E0 | C+PASS | 428.6 | **T** | 保持 |
| vo-CS-E4 | C+PASS | 431.9 | F | **goal T→F**（见 open-5） |
| vo-OT-E0/E4 | C+PASS | 1255.1 / 991.2 | F/F | seam-01 E0 假爬行 / E4 FAILED → 真通过 |
| vo-MS-E0/E4 | C+PASS | 830.2 / 670.1 | F/F | 保持 |
| fan 全 8 格 | C+PASS | 140.4–858.9 | F | HO-E4 43.95→140.4（安全余量恢复） |

### Mid 8 格（`build/original_gnc-glibc-v8/product-campaign-p4-mid/`）

| 格 | 结果 | 失败类别 | accepted publishes |
|---|---|---|---|
| CS-E4 | **COMPLETED + 硬安全 PASS（790.9 m）** | — | 4344 |
| CS-E0 | FAILED @39 s | QUALITY_RECOVERY_SUFFIX（候选横漂 551.6 m） | 120 |
| HO-E0/E4 | FAILED @~335 s | 优化器 INFEASIBLE = **预算饥饿**（open-1） | 1461 / 1557 |
| OT-E0/E4 | FAILED @25/45 s | QUALITY_CPA_RELEASE = recovery 先于实际 CPA（open-2） | 121 / 2922 |
| MS-E0/E4 | FAILED @80 s | COLREG_ACTION_DEADLINE 生命周期时序（open-4） | 1875 / 2007 |

Mid addressable 拒因：全 8 格合计 **2** 条（OT-E0 "lateral offset exceeds limit; split the avoidance maneuver"——设计内分步提示）。

## D2 第二次判定（[诊断政策](2026-09-11-original-gnc-diagnostic-policy.md)）

| 判据 | 结果 | 证据 |
|---|---|---|
| (a) 零硬安全失败 | **PASS** | 全部完成评估的 17 格硬门全 PASS；无任何格记录 hard-gate FAIL |
| (b) ≥80% 格 ≥1 接纳避碰计划 | **PASS** | **24/24**（VO 1-27、Fan 1-80、Mid 120-4344 accepted） |
| (c) addressable 拒因残差 | **PASS** | 13,287 → **~15**（seam-01 残差 13 + mid 2） |

**D2 = PASS**（三判据全过）。诚实注记：17/24 格 COMPLETED；7 个 mid 格在 planner 接受/优化层早夭（未进入安全评估，非安全失败），属 D3 任务完成层——正是 D3 门槛存在的原因。`diagnostic_only` 保持 true（仅 D3 可翻转）。

## 进度总览（三轮）

| 指标 | 2026-09-10 基线 | seam-01（P1） | **P4（本轮）** |
|---|---|---|---|
| 接纳避碰计划格数 | 0/24 | 24/24 | 24/24 |
| COMPLETED | 3 | 13 | **17** |
| 硬安全 PASS | 2 | 12 | **17（评估格全过）** |
| goal+PASS | 2 | 2 | 3 |
| addressable 拒因 | 13,287 | 13 | **~15** |
| Mid TRACKABILITY 拒 | 8/8 | 0 | 0 |

## Open 项（转入下轮，登记册 R6/R8/R9/R10）

1. **R8 mid 晚期预算饥饿**（our-side）：L4 拒后 `_unresolved_streak≥1` 将周期预算 20 s→2 s（`mid_mpc_ipopt.py:469`），上游静态上下文+held-authority 重验证吃掉大头，IPOPT 只剩 ~0.1 s → t>300 s INFEASIBLE。同 NLP 独立求解 4-9 次迭代即收敛。修法在预算策略/runner ENFORCE 记账。
2. **R9 recovery staging 先于实际 CPA 约 8 结点**：预测器按 max-rate 回转假设（horizon_encounter_plan.py），advisory 门要 150 m；需 recovery 重 staging 或生命周期重推导（OT/CS-E0）。
3. CS-E0 恢复后横漂 551.6 m（软屏障已减 843.8→551.6，未达标）；timeout 迭代可行而 warm seed 行违约（viol 3.3）致 seed 回退不触发；warm-seed 修复被既有不变量测试阻止（colleague 决策项）。
4. **R10 MS COLREG_ACTION_DEADLINE**：优化器已可行，生命周期 action-start/achievement 时序失败。
5. vo-CS-E4 goal T→F（R-B3 tag 策略改动后到时限未达 goal；vo-CS-E0 仍 T）——观察项，非安全。
6. VO 速度窗在默认 32 样网格坍缩到单行（2.903 m/s，执行 ≥3.0）；fan speed 7.0 m/s 请求未过 `PlannerInput`（cap 未 plumb）——planner 细化项。

## 证据

- VO/Fan：`build/original_gnc-glibc-v8/product-campaign-p4-bridge/`（16 格 run 目录 + per-cell JSON）+ `product-acceptance-summary-p4-bridge.json` + `product-campaign-p4-bridge.log`
- Mid：`build/original_gnc-glibc-v8/product-campaign-p4-mid/`（campaign.json + per-cell JSON + run_dir/original-gnc.json execution_events）
- 过程快照：`product-campaign-p2-vo-fan/`、`product-campaign-p3-mid*`（被 bridge WIP 污染，仅过程参考）、`product-campaign-p3-bridge/`（截断 5/16）
- 复现：`tools/original_gnc/run_product_campaign_subset.py --output … --summary …`；`tools/original_gnc/run_mid_product_campaign.py --output …`（env：`PYTHONPATH=<worktree>`、`COLAV_ORIGINAL_GNC_BUILD=<worktree>/build/original_gnc-current`）
