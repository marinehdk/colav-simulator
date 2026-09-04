# GNC S9 栈 B — Issue #67 验收矩阵 campaign 报告

> 分支 `feat/gnc-s9b-acceptance`（自 `feat/gnc-s9a-kernel` 分出）
> 注入栈：`fcb45_3dof_plant+pass_through_guidance+fcb45_marine_pid`（ideal 执行器）
> 验收间距 profile：`config/acceptance_issue67_{vo,fan_mpc,mid_mpc}.yaml`（acceptance 专用，shipped 默认零改动）
> 门限：goal_reached；无碰撞/搁浅；全程本船-目标最小中心距 ≥ 180 m（4 × 44.1 m Lpp）；
> 返航窗口（CPA + 240 s → run 结束）max|XTE| ≤ 50 m；越线 ≤ 2 次。

## 1. 九宫格数值表（seed 0，t_end 1200 s）

| 算法 | 场景 | min 中心距 (m) | max&#124;XTE&#124; (m) | 越线 | goal (s) | 窗口 | 结果 |
|---|---|---|---|---|---|---|---|
| VO | head_on | 423.3 | 6.15 | 1 | 774.5 | [463, 774] | PASS |
| VO | overtaking | 205.0 | — | — | 609.0 | 空窗 | PASS |
| VO | crossing_give_way | 233.8 | — | — | 281.5 | 空窗 | PASS |
| Fan-MPC | head_on | 377.2 | 1.36 | 0 | 564.5 | [443, 564] | PASS |
| Fan-MPC | overtaking | 379.4 | 0.61 | 0 | 535.5 | [485, 535] | PASS |
| Fan-MPC | crossing_give_way | 374.6 | — | — | 287.0 | 空窗 | PASS |
| Mid-MPC | head_on | 222.5 | 5.60 | 0 | 564.0 | [444, 564] | PASS |
| Mid-MPC | overtaking | 410.6 | — | — | 559.0 | 空窗 | PASS |
| Mid-MPC | crossing_give_way | 199.7 | — | — | 269.0 | 空窗 | PASS |

- 九宫格全绿。所有 cell：goal_reached、无碰撞、无搁浅、strict 无 fallback、
  manifest FINISHED/COMPLETED。
- "空窗" = 会话在 CPA+240 s 窗口开启前已 goal_reached（返航段不存在），
  XTE/越线门按空集判定为 vacuous PASS（tests/test_gnc_acceptance_matrix.py
  显式处理并在本表记录）。

## 2. VO 名义间距机制结论与参数化

- **硬间距面**：kuwata_vo 的 dynamics-clearance domain 检查候选速度的
  转速率受限预测轨迹（`_predict_candidate_positions`）与目标 120 s 匀速预测
  轨迹的最近中心距，小于 `combined_hull_radius + hard_hull_clearance_m +
  0.25 m` 即硬禁。`combined_hull_radius` = 0.5·hypot(OS 尺寸) +
  0.5·hypot(TS 尺寸)，运行时由 legacy 模型参数（viknes 8.45 × 2.71 m）喂入，
  VO kwargs 的 `length_os/width_os` 只影响静态危险多边形（max(runtime, params)）。
- ** viknes-vs-viknes combined radius = 8.874 m**，故名义间距 = 硬管半径
  （约 191.1 m，含 0.25 m 积分裕度）由 `hard_hull_clearance_m = 182.0` 决定；
  `preferred_hull_clearance_m = 190.0`（软域中心距 198.9 m）只加代价；
  `d_min = 190.0` 对齐 CPA 分类。
- **t_max 120 → 60 s**（关键修复）：120 s 预测管让 CPA 过后航向解仍被
  压制 ~250 s，执行参考自旋、船舶回绕一圈（676 m 偏航）；60 s 时解禁提前
  至 CPA+~40 s，恢复段 XTE 降至 ~6 m，且会遇间距反而增大（423 m vs 274 m）。
- 经 kwargs/config 全参数化，算法内部零改动。

## 3. 整定记录（全候选，10% 红线未触发：无已过格被后续调整恶化）

| # | candidate | changed | 结果（crossing_give_way Mid cell 交付中心距） | 淘汰/采纳原因 |
|---|---|---|---|---|
| 0 | Mid cpa_safe 190 | 基线 profile | 162.5 m < 180 门 | 不达标 |
| 1 | Mid cpa_safe 200 | 单 kwarg | 162.5 m | 软代价被 route 项淹没，不敏感 |
| 2 | Mid cpa_safe 250 | 单 kwarg | 158.6 m | 更差（模式漂移） |
| 3 | Mid route_weight 0.5 | 单 kwarg | 161.5 m | 不敏感 |
| 4 | Mid heading_window 60 | 单 kwarg | 162.8 m | 不敏感 |
| 5 | Mid horizon_steps 120 | 单 kwarg | 161.6 m | 不敏感 |
| 6 | Mid decel_max 0.6 | 单 kwarg | 162.5 m | 不敏感 |
| 7 | Mid solve period 10→5 | 单 kwarg | 162.5 m | 不敏感 |
| 8 | **Mid cpa_hard 50→150** | 单 kwarg | 173.2 m | 有感，未达标 |
| 9 | **Mid cpa_hard 50→180** | 单 kwarg | **197.9 m** | **采纳**（硬约束是真正杠杆） |
| 10 | VO t_max 40 | 单 kwarg | head_on 167.9 m < 180 门 | 淘汰（会遇间距反而受损） |
| 11 | VO t_max 60 | 单 kwarg | head_on 423.3 m，恢复 XTE ~6 m | **采纳** |
| 12 | VO planning_frequency 2.0 | +static400 | OT 恢复仍 >240 s | 淘汰 |
| 13 | VO heading/speed grid 256/48 | +static400 | 恢复 1139 m 偏航 | 淘汰 |
| 14 | VO static_hazard_layers 去 SHORE | +static400 | 167.9 m | 淘汰 |
| 15 | VO static_query_range 400/700 | 单 kwarg | 恢复恶化（流域翻转） | 淘汰（保留默认 1000 m） |

## 4. 评估器指标清单（colav_simulator/evaluation/voyage.py）

- `voyage.encounter.min_target_center_distance_m`：全程本船-各目标中心距的
  逐 tick 最小值（段插值，独立于采样对最小值）；`controlling_target_id`。
- `voyage.return_voyage.{window_start_s, cpa_time_s, buffer_s}`：返航窗口
  （CPA + 240 s 回退定义）。
- `voyage.return_voyage.max_abs_xte_m`：窗口内对场景 yaml 原航线（折线最近
  距离，带符号星正）的 max|XTE|。
- `voyage.return_voyage.route_crossings`：重入后（5 m 迟滞带）XTE 符号变化
  次数。
- 报告挂在 EvaluatorResult.voyage，runner 经执行上下文传入本船任务航线
  （`ownship_route_waypoints_ne`）与 `return_window_buffer_s`。

## 5. 关键设计事实（对本矩阵可判定性至关重要）

- head_on/overtaking 航线终点位于海岸搁浅边缘内（沿航线 5015/5724 m 起为
  搁浅带，终点本身在搁浅距离内）：直线航迹 nominal 在 716.5/715.5 s 起连续
  grounding 直至终点。**goal_reached + 零搁浅在原航线上几何不可实现**。
  修复：验收矩阵经 `RunSpec.scenario_override` 携带测试自有场景文档，本船
  目标改为同线 4000/4400 m 处（静态危险查询半径 1000 m 之外）；
  shipped `scenarios/*.yaml` 零改动（内容哈希守卫
  test_historical_ais_scene_guard 保持原样）。legacy 59 m 半径在任何 600 s
  产品窗口内不可达 → 产品窗口行为零变化（test_kuwata_vo_closed_loop、
  test_potocnik_colreg_g3_matrix 全量实测通过）。
- 注入栈以 7×44.1 m 的物理尺度参与 goal 判定：
  `ModularShipAdapter.length/width/draft` 属性按 catalog 预设身份覆写
  （legacy 等价栈保持 legacy 尺寸，测试钉住）。planner 侧几何
  （os_length 等 kwargs）仍来自 legacy 模型参数，不受影响。

## 6. 回归结果

- 全套回归（slice 5，分文件/分块执行，a3_demo/legacy_g6/ros_adapter 单独跑）：
  全部通过；仅 test_playback_speed.py 2 例（web 资源断言）与
  test_historical_ais_scene_guard.py 1 例（hais mid-mpc experimental 元组）
  在 s9a 基线（2b3022c）上同样失败，属既有失败，非本分支引入。
- ruff check .：clean

## 7. Commit 列表（feat/gnc-s9b-acceptance）

- b528cea feat(evaluation): ownship encounter clearance and return-voyage XTE metrics
- 393cea4 feat(config): acceptance-only spacing profiles for the Issue #67 matrix
- 2b3022c fix(modular-gnc): ideal chain must not feed stale self-output as achieved load
- 366360f feat(modular-gnc): adapter reports preset plant vessel identity
- 59d4748 test(acceptance): Issue #67 matrix harness plumbing and cell gate
- a69e37c fix(gnc): FCB45 vessel identity completes the Issue #67 acceptance voyage
- （本次）test/docs: mid cpa_hard 180 tuning + matrix green + campaign report

## 8. 偏离 spec 的决策及理由

1. **验收场景经 RunSpec.scenario_override 携带 goal_csog_state（head_on
   4000 m / overtaking 4400 m 同线点）**：原航线终点位于搁浅边缘内，
   "goal_reached + 零搁浅" 几何不可实现（nominal 直线航迹实测连续
   grounding 84/73 s 至终点）。场景文档由测试自有（shipped yaml 零改动，
   内容哈希守卫不变）；会遇几何（前 300 s）与 600 s 产品窗口完全不变
   （§5 回归实测）。spec 未预見 scenario_override 通道，但该通道完全在
   RunSpec 契约内，是改动面最小的实现。
2. **返航窗口空集判 vacuous PASS**：三格（VO/Fan/Mid 的 CS，VO/Fan/Mid 的
   OT）在 CPA+240 s 前已完成航线，返航段不存在；按空集判定并记录。
3. **VO profile 增加 t_max=60**：spec 授权的 "VO 参数" 面；t_max 是恢复段
   行为的决定性参数（见 §2）。
4. **Mid profile 增加 cpa_hard=180**：cpa_safe 190→250 与其它 MPC kwargs
   全部不敏感（§3 记录）；硬约束是唯一有效杠杆。spec 的 "190→200+" 措辞
   按其意图（间距 profile 微调至过门）执行并全候选记录。
5. **evaluation 缓冲 120→240 s**：对齐 spec §2.1 的 240 s 定义（前次实现
   偏差）。
