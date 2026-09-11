# 原版 GNC seam 准入 D2 评估（24 格重跑）

24 格产品入口在 seam 修复后全量重跑（seed 0，同基线格集）：24/24 格存在 ≥1 个被原坐标模块接受的避碰 plan（基线 0/24，共 2,935 个唯一 accepted plan ID）；三个可归因拒因类从 13,287 次拒绝降至 13 次残差；运行完成 13 格（基线 3）、硬安全通过 12 格（基线 2）、goal+硬安全 2 格（基线 0）。物理硬安全唯一失败：fan×HO×E4 最小船体净距 43.95 m < 50 m。D2 判定：安全门未过（见下），D2 整体不通过；`diagnostic_only` 不翻转（按诊断政策只有 D3 翻转，本轮仅为报告）。

## 运行身份与协议

- 工作区：`/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration`；分支 `codex/original-gnc-integration`；基线 `49ace990` + 10 个 seam commit（reference-splice 准入、reverse-segment junction guard、Mid capability qualification，头 `5a9e95fc`）。
- 嵌入库与基线完全相同：`build/original_gnc-glibc-v8/liboriginal_gnc-0be0028f097d440abb34242feac84040.dylib`，SHA256 `6e9f2728758b7934296e8da9bfee1a98905e038b29402c6e95ae780c6dc220fa`。本轮差异全部来自 Python 适配层 seam commits；`cpp/original_gnc/` 与外部源未改动。
- 工具未修改：`tools/original_gnc/run_product_campaign.py`（生成）+ `summarize_product_campaign.py`（汇总）。RunSpec 同基线：seed 0、`strict_no_fallback=True`、`terminate_on_collision_or_grounding=False`、solve period 5 s、deadline ENFORCE、mid 使用同一 P1 工程包络 domain profile。逐格运行前 runner 校验 `RUNTIME_SOURCE_FINGERPRINTS` 通过，源快照存入 `runtime-source/`。
- 格集（与基线一致）：3 规划器（`vo`、`potocnik_colreg_fan_mpc`、`mid_mpc_ipopt`）× 4 场景（`head_on`、`crossing_give_way`、`overtaking`、`paper_ccta2023_multiship`）× 2 环境（E0 OFF / E4 ON）。第 4 场景是多船 `paper_ccta2023_multiship`，不存在 `crossing_stand_on` 格。
- 8010/8014 服务未重启、未作为测试实例；无 push。

## D2 判定

对照诊断政策（主工作区 `docs/research/2026-09-11-original-gnc-diagnostic-policy.md`）三条同时满足才过：

| 准则 | 结果 | 判定 |
|---|---|---|
| (a) 硬安全零失败 | **FAIL**：fan×head_on×E4 最小船体净距 43.953 m < 50 m（碰撞 0、搁浅 0）；其余 23 格无物理安全失败，但其中 11 格 run 级失败只有 `run_completion` 检查、安全评估 `NOT_EVALUATED`，不构成安全通过证据 | **未过** |
| (b) ≥80% 格存在 ≥1 个被接受的避碰 plan | **24/24 = 100%**（接受 ID 数 1–461/格，合计 2,935；基线 0/24） | **通过** |
| (c) 三个可归因拒因类降至残差 | 13 次残差 / 24 格（基线 13,287）：`first changed waypoint too close` 12（vo-HO-E4 3、fan-multiship-E4 9；基线 11,048）、`lateral offset exceeds limit` 1（mid-OT-E0；基线 251）、`route update too frequent` 0（基线 1,988）；`reverse segment` / `segment_too_short` 0/0 | **通过** |

**D2 整体：不通过**（(a) 未过）。按政策，这不构成产品验收，`diagnostic_only=True` 维持；(b)(c) 表明 seam 层准入问题已解决，剩余失败集中在规划器可行性（R4）与任务完成层（R6），属 D2→D3 之间的新证据。

## 24 格结果

失败格安全评估 `NOT_EVALUATED`，不补零；goal 指框架 goal 事件；主拒因只列 coordinate 层拒绝，"—" 表示该格零拒绝（详见拒因直方图）。接受/唯一 ID 基线均为 0。

| Case | 运行（基线→本轮） | 仿真 s | 接受/唯一 ID | 转发 | 硬安全 | 最小净距 m | goal | 主拒因 | 证据 |
|---|---|---:|---:|---:|---|---:|---|---|---|
| vo-head_on-E0 | FAILED→FAILED (INFEASIBLE) | 266.0 | 34/34 | 34 | 未评估 | — | False | —（终端 VO 不可行） | [运行](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/product-campaign-seam-01/vo-head_on-E0/7538feca-af4a-40b6-a776-78858878556f/manifest.json) |
| vo-crossing_give_way-E0 | FAILED→COMPLETED | 683.5 | 54/55 | 54 | PASS | 630.7 | **True** | — | [运行](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/product-campaign-seam-01/vo-crossing_give_way-E0/abddf2cd-7c09-41ca-b8c2-be6ea2feff7e/manifest.json) |
| vo-overtaking-E0 | FAILED→COMPLETED | 1200.0 | 1/1 | 1 | PASS | 350.4 | False | — | [运行](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/product-campaign-seam-01/vo-overtaking-E0/493cdf68-53ae-4427-a423-e28c5347b3b0/manifest.json) |
| vo-paper_ccta2023_multiship-E0 | COMPLETED→COMPLETED | 1800.1 | 70/70 | 70 | PASS | 631.5 | False | — | [运行](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/product-campaign-seam-01/vo-paper_ccta2023_multiship-E0/a5e1a909-23ba-4e09-9594-88be029b1140/manifest.json) |
| potocnik_colreg_fan_mpc-head_on-E0 | FAILED→COMPLETED | 1200.0 | 448/448 | 448 | PASS | 85.4 | False | — | [运行](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/product-campaign-seam-01/potocnik_colreg_fan_mpc-head_on-E0/cab63c1e-e7bd-47da-87cb-ff443277b7a7/manifest.json) |
| potocnik_colreg_fan_mpc-crossing_give_way-E0 | FAILED→COMPLETED | 1200.0 | 458/458 | 458 | PASS | 649.3 | False | — | [运行](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/product-campaign-seam-01/potocnik_colreg_fan_mpc-crossing_give_way-E0/fe65504d-07e1-464e-9057-dae41449d41b/manifest.json) |
| potocnik_colreg_fan_mpc-overtaking-E0 | FAILED→COMPLETED | 1200.0 | 449/449 | 449 | PASS | 965.0 | False | — | [运行](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/product-campaign-seam-01/potocnik_colreg_fan_mpc-overtaking-E0/e3c6d44a-3a4b-4dc8-88e5-11b15b29a1aa/manifest.json) |
| potocnik_colreg_fan_mpc-paper_ccta2023_multiship-E0 | FAILED→COMPLETED | 1800.1 | 169/169 | 169 | PASS | 541.1 | False | — | [运行](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/product-campaign-seam-01/potocnik_colreg_fan_mpc-paper_ccta2023_multiship-E0/02746a9a-9c27-445b-891c-889563587fb6/manifest.json) |
| mid_mpc_ipopt-head_on-E0 | FAILED→FAILED (INFEASIBLE) | 57.5 | 8/8 | 8 | 未评估 | — | False | —（L4 拒终端候选） | [运行](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/product-campaign-seam-01/mid_mpc_ipopt-head_on-E0/5aa33f8b-8bc9-49cd-91f1-e6582934e7c8/manifest.json) |
| mid_mpc_ipopt-crossing_give_way-E0 | FAILED→FAILED (NUMERICAL_FAILURE) | 51.0 | 17/17 | 17 | 未评估 | — | False | —（splice margin 不可达） | [运行](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/product-campaign-seam-01/mid_mpc_ipopt-crossing_give_way-E0/1e501d97-3062-4af4-b07a-10ecc4faf8d9/manifest.json) |
| mid_mpc_ipopt-overtaking-E0 | FAILED→FAILED (INFEASIBLE) | 25.0 | 2/2 | 2 | 未评估 | — | False | lateral offset ×1 | [运行](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/product-campaign-seam-01/mid_mpc_ipopt-overtaking-E0/81ea0acb-6080-4184-b36c-6d58b13ba12c/manifest.json) |
| mid_mpc_ipopt-paper_ccta2023_multiship-E0 | FAILED→FAILED (INFEASIBLE) | 50.0 | 1/1 | 1 | 未评估 | — | False | — | [运行](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/product-campaign-seam-01/mid_mpc_ipopt-paper_ccta2023_multiship-E0/61b5c401-3c2a-451d-bb3c-14b4b2a3e78a/manifest.json) |
| vo-head_on-E4 | FAILED→FAILED (INFEASIBLE) | 264.0 | 24/26 | 26 | 未评估 | — | False | first-changed ×3 | [运行](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/product-campaign-seam-01/vo-head_on-E4/2c4053df-66bc-48fc-8f98-49dbc0d2faaf/manifest.json) |
| vo-crossing_give_way-E4 | FAILED→COMPLETED | 451.5 | 55/56 | 55 | PASS | 667.7 | **True** | — | [运行](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/product-campaign-seam-01/vo-crossing_give_way-E4/820552c4-9049-4f61-918d-71f92ee6c78e/manifest.json) |
| vo-overtaking-E4 | FAILED→FAILED (INFEASIBLE) | 694.0 | 40/41 | 40 | 未评估 | — | False | —（终端 VO 不可行） | [运行](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/product-campaign-seam-01/vo-overtaking-E4/762a9643-eede-4332-bb96-fd609bb7e469/manifest.json) |
| vo-paper_ccta2023_multiship-E4 | COMPLETED→COMPLETED | 1800.1 | 41/41 | 41 | PASS | 626.1 | False | — | [运行](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/product-campaign-seam-01/vo-paper_ccta2023_multiship-E4/f7efce2c-b210-41fd-b710-40d2682e217f/manifest.json) |
| potocnik_colreg_fan_mpc-head_on-E4 | FAILED→COMPLETED | 1200.0 | 135/135 | 135 | FAIL | **43.953** | False | — | [运行](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/product-campaign-seam-01/potocnik_colreg_fan_mpc-head_on-E4/39ecd509-4637-4adc-bd31-e0efc20dcd4c/manifest.json) |
| potocnik_colreg_fan_mpc-crossing_give_way-E4 | COMPLETED→COMPLETED | 1200.0 | 461/461 | 461 | PASS | 658.6 | False | — | [运行](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/product-campaign-seam-01/potocnik_colreg_fan_mpc-crossing_give_way-E4/3b9e3dc5-c4f5-4260-b8d8-54bd160d93cc/manifest.json) |
| potocnik_colreg_fan_mpc-overtaking-E4 | FAILED→COMPLETED | 1200.0 | 391/391 | 391 | PASS | 1106.7 | False | — | [运行](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/product-campaign-seam-01/potocnik_colreg_fan_mpc-overtaking-E4/808b77b8-569d-4aa4-9bbe-1faadebb925c/manifest.json) |
| potocnik_colreg_fan_mpc-paper_ccta2023_multiship-E4 | FAILED→COMPLETED | 1800.1 | 46/46 | 46 | PASS | 538.9 | False | first-changed ×9 | [运行](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/product-campaign-seam-01/potocnik_colreg_fan_mpc-paper_ccta2023_multiship-E4/5be6fcfa-95e6-4701-bdd0-148e329aca76/manifest.json) |
| mid_mpc_ipopt-head_on-E4 | FAILED→FAILED (INFEASIBLE) | 64.5 | 9/9 | 9 | 未评估 | — | False | —（L4 拒终端候选） | [运行](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/product-campaign-seam-01/mid_mpc_ipopt-head_on-E4/9d452522-c28b-4b42-ad21-7611119c1212/manifest.json) |
| mid_mpc_ipopt-crossing_give_way-E4 | FAILED→FAILED (NUMERICAL_FAILURE) | 53.5 | 19/19 | 19 | 未评估 | — | False | —（splice margin 不可达） | [运行](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/product-campaign-seam-01/mid_mpc_ipopt-crossing_give_way-E4/2ae43c51-80f1-4a23-a7eb-f1067c896ec7/manifest.json) |
| mid_mpc_ipopt-overtaking-E4 | FAILED→FAILED (INFEASIBLE) | 25.0 | 2/2 | 2 | 未评估 | — | False | — | [运行](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/product-campaign-seam-01/mid_mpc_ipopt-overtaking-E4/b09ea482-994e-433e-a525-cd9a392e8e4b/manifest.json) |
| mid_mpc_ipopt-paper_ccta2023_multiship-E4 | FAILED→FAILED (INFEASIBLE) | 55.0 | 1/1 | 1 | 未评估 | — | False | — | [运行](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/product-campaign-seam-01/mid_mpc_ipopt-paper_ccta2023_multiship-E4/e0a15c9b-767d-4b26-ab10-98578cec9da7/manifest.json) |

运行统计：COMPLETED 13 / FAILED 11；hard gate PASS 12 / FAIL 1 / 未评估 11；goal+硬安全 2（vo×CS×E0、vo×CS×E4）；fallback_used 全 24 格 false。

## 拒因直方图前后对照

coordinate/manager 两层对 avoidance plan 的状态事件（本轮 24 格，接受类注记除外）：

| 拒因 | 基线（summary v2，24 格） | 本轮 |
|---|---:|---:|
| first changed waypoint is too close to current ship position | 11,048 | 12 |
| route update too frequent | 1,988 | 0 |
| dynamic route lateral offset exceeds limit | 251 | 1 |
| reverse segment / segment_too_short | — | 0 / 0 |
| speed_exceeds_vessel_limit / turn_radius_too_small / yaw_rate_too_high / decel_distance_not_enough / heading_path_conflict（dynamic-degrade 类） | 各格零星 | 0 |
| parent mismatch / plan_expired / duplicate（manager 类，avoidance plan 上） | 0 | 0 |

本轮接受侧注记（非拒绝，单一 topic 计数）：`route geometry and metadata are identical to the active route` 7,057、`route accepted and published` 3,006、`route accepted; first waypoint publication gated for startup yaw ordering` 26。manager 层 `decel_distance_tight`（5,017）、`yaw_rate_limited`（3,199）、`turn_speed_limited`（264）、`speed_limited_by_vessel`（15）、`feasible`（1,607）均为 accepted=true 的状态注记（限幅/可行性信息），不是拒绝。fan×multiship 两格各有 9 次 `avoidance_validity_expired`，挂在 nominal route ID 上（accepted=true），不属于 avoidance 拒绝。

## R1 / R3 / R4 / R6 指标（数字口径）

- **R1（t_detect→首个 coordinate-ACCEPTED avoidance）**：`first avoidance request → accepted` 在全部 24 格同拍完成（≈0 s，seam 准入零延迟）。`threat_entered → first accepted`：20/24 格 ≤1 s——其中 12 格为 −0.5～−0.1 s（predicted-threat 路径下 avoidance route 先于 `threat_entered` 事件一拍生效）、8 个 mid 格恰为 0.0 s（逐格值见 metrics JSON `r1` 字段）；4 个 VO 单船格 32.5–112.5 s（head_on-E0 51.5、head_on-E4 52.5、overtaking-E0 32.5、overtaking-E4 112.5）——这是 VO planner 保持名义合规、迟迟不进入 avoidance 分支的激活延迟（request 与 accepted 同拍），不是准入拒绝。登记册 R1 的 <25 s 目标：20/24 格满足。
- **R3（avoidance leg transit，active route `route_type=avoidance` 占用区间）**：vo-CS-E0 4 段合计 216.0 s（均值 54.0 s）；vo-CS-E4 1 段 181.0 s；vo-HO 214.0/211.0 s；vo-OT-E4 282.0 s。fan 单船 4 格各 1 段占满 1200 s 窗口（splice route 持续有效、未触发 return-to-nominal）；fan/vo multiship 全程 1800.1 s 或 10 段均值 180.0 s。mid 8 格 25.0–64.5 s（终端失败前）。注意口径：route 级 occupancy 是 3.2 m/s cap 暴露的上界——mixed tagging 下 cap 只作用于 deviation 段，实际限速段更短。
- **R4（结构性不可行量化）**：VO 终端不可行 3/8 格（head_on E0/E4、overtaking-E4），终端调用标签 `stop_nonpaper_wrapper`、原因 `all_velocity_grid_candidates_inadmissible`（内部不可行候选标签，未作为执行 fallback）；基线同类失败 6/6 单船格，本轮 crossing_give_way 双环境与 overtaking-E0 已可完成。Fan：`NoContinuouslyFootprintSafeTrajectory` 由基线 7 格降为 0 格；唯一物理安全失败 fan-head_on-E4（43.953 m，其他 7 格净距 85.4–1106.7 m）。规划耗时（同口径去重）：VO 中位 25–62 ms、Fan 11–24 ms、Mid 396–1676 ms（p95 至 3741 ms）。
- **R6（Mid 任务层残留）**：TRACKABILITY_CAPABILITY 拒绝 **0**（基线 8 格全部 `TRACKABILITY_CAPABILITY_TUPLE`/`INCOMPLETE` 拒绝，资格 tuple 已被接纳）。goal/mission-arrival：0/8。失败分层：crossing_give_way×2 准入与求解全通（17/19、19/19 accepted；20/20 solver artifact L4-accepted），仅末端失败 `Accepted Mid path never reaches the reference splice margin`——splice 末端构造与 planner 到达判据不匹配，与登记册 R6 预测一致；head_on×2 真实续航 57.5/64.5 s 后终端候选被 L4 接纳层拒绝（`SAFETY_SWEPT_CLEARANCE` / `QUALITY_CPA_RELEASE`）；overtaking 与 multiship ×4 在 25–55 s 内终端 `Mid-MPC optimizer returned INFEASIBLE without a feasible candidate`。solver artifact 全部正迭代真实求解（8 格合计 76 件，逐件 SHA256 校验）：74 个 `FeasibleNonOptimal`/`Timeout`/`User_Requested_Stop`/`IPOPT_BEST_FEASIBLE_ITERATE` + 2 个 `Converged`/`Solve_Succeeded`/`IPOPT_TERMINAL`（multiship 两格各 1）。

## 与基线协议的偏差

1. 首次启动在首个格执行前被 runner 自身的 `RUNTIME_SOURCE_FINGERPRINTS` 校验中止：脚本方式运行时主仓库 editable install 抢先解析了 `colav_simulator`，快照校验按设计失败，0 格执行、0 产物。以 `PYTHONPATH=<worktree>` 重跑成功；属调用方式修正，非工具代码修改。
2. campaign 与 summarizer 工具零改动，无 runner-fix commit。
3. 其余口径与基线相同（seed 0、格集、RunSpec 包络、domain profile、同一嵌入库）；结果差异只能来自 10 个 seam commits 的 Python 适配层。

## 证据束

全部在 worktree `build/`（gitignored，路径为绝对基准 `.../build/original_gnc-glibc-v8/`）：

- `product-campaign-seam-01/` — 原始 24 格运行：`campaign.json`（24 attempts + RunSpec + wall time）、逐格 `<case>.json`（spec/manifest/evaluation 摘要）、各 `<case>/<run_id>/`（`manifest.json` 运行结果与 failure_status、`original-gnc.json` 请求/执行事件全链、`evaluation.json` 硬安全检查与 voyage、`events.jsonl`、`trajectory.parquet`、mid 格 `artifacts/mid_mpc/*.json.gz` 不可变 solver artifact）、`runtime-source/manifest.json` 源快照指纹。
- `product-acceptance-summary-seam-v1.json` — 官方汇总（同基线 schema v1）：admission 计数、coordinate/manager 拒因直方图、hard gate 与最小净距、goal、COLREG aggregate、mid solver artifact 摘要、planner 耗时、逐文件 SHA256。上表"接受/转发/净距/goal"取自本文件。
- `seam-d2-metrics/seam-d2-metrics.json` + 逐格 `<case>.metrics.json`（提取脚本 `extract_seam_metrics.py` 同目录）— R1 detect/request/accept 时刻、avoidance legs 区间、TRACKABILITY 拒绝计数、mid artifact 逐件状态、拒因三分类桶。
- 基线对照：`product-acceptance-summary-v2.json`（基线 24 格）、`build/original-final-route-admission-audit.json`（基线 11,048 次 first-change 全事件口径）。
- 运行日志：`product-campaign-seam-01.log`。
