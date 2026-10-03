# 预存失败台账（P3-S6 收口，spec #90，2026-10-02）

目的：S6 收口时把「与阶段3 无关、本段不修不追」的测试失败逐条落档，供后续独立立项。
对照方法：`git stash`（S6 全部 diff：trackers.py D1/D3 + capabilities + gui_server + 场景 +
探针）后在裸 HEAD 上跑同口径全量，再 pop 对照。两条全量命令与结果：

```
# 裸 HEAD 基线（stash 后）
.venv/bin/python -m pytest tests/ -q --ignore=tests/test_colreg_scoring.py
#   → 45 failed / 2441 passed / 10 skipped（37m18s）
# S6 工作树（pop 后，同一命令）
#   → 46 failed / 2444 passed / 10 skipped（37m42s）
#   差集 = 恰好 1 例（test_historical_replay 翻转假设 god，已按"显式声明"修绿，见 §3）
```

## 0. 采集环境注意

- 全量命令必须 `--ignore=tests/test_colreg_scoring.py`：该文件在**全量上下文**下段错误
  （见 §2），不排除则整轮中断、无汇总行。
- 今日机器上全量一次约 37 分钟；后台跑，避免并发重负载（deadline 类测试对 CPU 争用敏感）。

## 1. 任务时点已知预存红（S5 会话已 stash 对照证实，9 例）

| 域 | 例数 | 测试（今日基线中均在场） | 症状 |
|---|---|---|---|
| scene-guard | 2 | `test_historical_ais_scene_guard.py::test_existing_scenario_yaml_files_are_byte_stable`、`::test_existing_verified_exact_tuples_remain_unchanged_and_independent` | 数据集字节稳定性断言 |
| mid_mpc | 5 | `test_mid_mpc*` 家族子集（PRIMAL_SEED ≠ IPOPT_BEST_FEASIBLE_ITERATE 断言族） | 求解器迭代路径不稳定 |
| web_api | 2 | `test_web_api.py::test_deprecated_algorithm_selector_cannot_bypass_product_policy`、`::test_vo_head_on_recommended_tier1_executes_safe_maneuver` | 实测报 `Unsupported algorithm: potocnik_colreg_fan_mpc`（本机算法目录缺 potocnik 注册） |

## 2. S6 当日新增环境退化批（裸 HEAD 即红，36 例 + 1 个段错误文件）

S5 收口时全量仅 9 红；S6 当日同一 HEAD 全量 45 红。差 36 例与 S6 diff 无关（裸 HEAD 复现），
按文件归域如下（每文件一句域描述，均非 tracker/传感器域）：

| 文件 | 例数 | 域 |
|---|---|---|
| `test_gnc_acceptance_matrix.py` + `_s10` | 6+6 | GNC 验收矩阵动态单元（vo/mid_mpc cell 安全门槛） |
| `test_gui_product_spacing_profile.py` | 3 | GUI 默认间距恢复行为 |
| `test_standard_scenario_completion_window.py` | 4 | 标准遭遇 600s 完成窗/回航路由 |
| `test_mid_mpc_single_encounter.py` | 5 | mid-MPC 单遭遇闭环行为 |
| `test_mid_mpc_single_product_runtime.py` | 3 | mid-MPC 产品运行时安全 |
| `test_mid_mpc_multiship_runtime.py` | 1 | mid-MPC 多船闭环 |
| `test_mid_mpc_anticipatory_runtime.py` | 1 | mid-MPC 预见性运行时 |
| `test_kuwata_vo_static_closed_loop.py` | 1 | Kuwata VO 静态障碍闭环（显式 GodTracker 注入的测试） |
| `test_vo_multiship_recovery.py` | 1 | VO 三目标恢复 |
| `test_gnc_planner_audit.py` | 1 | mid-MPC 计划保持审计 |
| `test_scenario_generator.py` | 1 | 场景生成器（ValueError） |
| `test_behavior_generator.py` | 1 | 行为生成器（FileNotFoundError，疑似本地数据缺失） |
| `test_historical_cold_start.py` | 1 | 历史回放冷启动 deadline |
| `test_ship_domain_profile_injection.py` | 1 | 域剖面注入工厂 |
| `test_validation_config_api.py` | 1 | Config seam 会话创建 |
| `test_threat_web_projection.py` | 1 | 威胁 REST/WS 投影 |
| `test_playback_speed.py` | 2 | 回放 UI/精灵 |
| `test_web_solver_responsiveness.py` | 1 | 求解器响应终帧发布 |

**段错误（阻断全量，1 文件）**：`tests/test_colreg_scoring.py` 在全量上下文随机于文件内
某测试处 `Fatal Python error: Segmentation fault`（两轮崩点均在 `_write_run_dir` →
`colav_simulator/experiment/persistence.py:401` 后台写线程；裸 HEAD 与 S6 工作树崩点相同；
单文件独立运行 29/29 全绿）。疑 pyarrow 后台线程写盘路径与全量上下文的交互问题，域外，立项排查。

> 立项建议：a) 36 例按上表逐文件 triage（先 diff S5 收口日与今日的运行环境：OS 小版本/
> brew 升级/venv 包漂移均可能）；b) colreg_scoring 段错误单独立项（faulthandler + 单测隔离复跑）。

## 3. S6 diff 引入并已修复的失败（非预存，留痕）

- `tests/test_historical_replay.py::test_replay_reappearance_rearms_tracker_generation`
  —— D1 翻转后该测试经场景默认吃到 KF 链，而「重现身重置 generation」语义是 GodTracker
  生命周期通道的。修法 = 按任务约束**显式声明**：`HistoricalReplayFactory.prepare(..., trackers=[(0, GodTracker())])`
  （与 `test_kuwata_vo_static_closed_loop.py:86` 既有工艺一致），不改断言语义。
- `tests/test_historical_session_create.py::test_hais_scene_listed_with_source_presence_gate`
  —— D2 元组镜像后历史场景 catalog 的 experimental 组合集新增 vimmjipda 平行三元组，
  测试钉值跟随（断言集合加 3 个 vimmjipda 元组，语义不变；终轮全量后单独修绿并文件级复验
  6 passed）。
- 翻转同步的策略钉值更新（非失败，属契约跟随）：`test_p1_capability_api`（policy 字典 +
  selectable 集合）、`test_product_execution_policy`（CLI/batch 默认、algo_status product 集）、
  `test_web_api::test_rule14_capability_api`（catalog defaults + trackers selectable）——
  均为「产品策略就是 spec」的钉值跟随，见 self-review §Standards。
