# 算法与场景真实能力矩阵

> 审计日期：2026-07-27  
> 分支：`codex/colav-paper-closed-loop`  
> 目标：区分“可发现、可导入、可运行、可展示、可验证”，避免把下拉框可选当成算法能力完成。

## 1. 完成等级

| 等级 | 定义 | 可否作为 Web 能力展示 |
|---|---|---|
| G0 可发现 | 场景能解析，或依赖能 import | 否 |
| G1 短烟测 | 适配器构造并推进少量仿真步 | 否 |
| G2 完整闭环 | 代表场景从开始运行到终止，进程稳定，无 fallback | 可展示“能运行” |
| G3 能力展示 | 相对 nominal 出现符合算法职责的可观察动作和诊断 | 可展示算法能力 |
| G4 基准验证 | 固定场景矩阵、多 seed、统一 Evaluator 和统计通过 | 可用于算法结论 |

“真实可用”至少要求 G2；“完整展示能力”至少要求 G3。

## 2. 当前算法结论

| 算法 | 正确角色 | 当前等级 | 已确认事实 | 当前结论 |
|---|---|---:|---|---|
| `nominal` | 场景原生 guidance 基线 | G2 | `head_on + seed 0` 在 God/KF 下均形成碰撞基线 | 正式可选基线，不是独立避碰算法 |
| `vo` | 动态目标反应式避碰 | G3 | God/KF 最小船距分别为 43.36/43.70 m，均明显右转、无碰撞 | Rule 14 能力展示通过 |
| `sbmpc` | 动态目标 COLREGS 避碰 | G3 | God/KF 最小船距分别为 94.17/91.81 m，均明显右转、无碰撞 | Rule 14 能力展示通过 |
| `psbmpc` | 动静态目标 PSB-MPC | G1 | 0.2 s 短烟测成功，收到 19 个 ENC polygons 和 3 tracks | 不可称完整可用 |
| `rrt` | ENC 静态全局路径规划 | G1 未过 | 真实 hazard/CDT/tree-growth 路径已接入；动态船未进入规划 | 当前没有成功代表场景，不能作为动态 COLAV 对比 |
| `rlmpc` | NMPC/学习增强 MPC | G0 未过 | 仓库存在，运行依赖探测失败 | 不可用：缺 `casadi`/Acados 环境 |
| 自研 MPC | 最终待测算法 | 接口阶段 | `module:factory -> ICOLAV` 已冻结 | 算法未提供，未运行 |

### 2.1 PSB-MPC 阻塞证据

- `paper_ccta2023_multiship`、`t_end=0.2 s`：短烟测 `FINISHED`。
- `paper_ccta2023_head_on`、完整 500 s：原生进程退出码 134。
- 退出原因：Eigen `Block.h:126` assertion。
- run `70527617-5353-4c9e-9424-e49de9a28bc8` 只留下 `CREATED` manifest；原生 abort 无法被 Python 捕获。

因此 Web 中直接运行 PSB-MPC 会有杀死后端进程风险。完成进程隔离和完整闭环前，只能标记“实验性/短烟测”。

### 2.2 RRT 阻塞证据

- `paper_ccta2023_multiship`：真实 grow 执行，返回 `INFEASIBLE`。
- `rrt_test`：场景生成阶段失败，`ValueError: Polygon is empty`；尚未进入算法。
- RRT 适配器不使用动态目标 `do_list`，职责是静态 ENC 路径规划，不应与 VO/SB-MPC 混称动态避碰算法。

## 3. 场景目录的真实含义

当前 API 返回 44 个场景：

| 状态 | 数量 | 含义 |
|---|---:|---|
| `valid=true` | 19 | YAML/schema 可解析；不等于完整仿真成功 |
| `valid=false` | 25 | 准备阶段已知不可用 |

25 个不可用场景：

- Imazu 01-22：缺 `data/enc/Trondelag.gdb`；
- 2 个 AIS：缺 `map_origin_enu`；
- `planning_example`：LOS 缺 `cross_track_error_int_threshold`。

2026-07-27 对 19 个 `valid=true` 场景执行 `nominal` 单步运行冒烟：

| 结果 | 数量 | 场景 |
|---|---:|---|
| 单步通过 | 15 | `aalesund_random1`、5 个标准遭遇、`head_on_sbmpc`、2 个论文场景、2 个 RL 场景、3 个 RLMPC/VIM 配置场景、`simple_planning_example` |
| 单步失败 | 4 | `boknafjorden_generation_test`、`rogaland_random_rl`、`rrt_test`、`saved/rlmpc_scenario_ms_channel/...` |

单步通过仅证明场景进入真实主链，不等于完整 episode、算法能力或评价报告已通过。

| 场景 | 单步失败原因 |
|---|---|
| `boknafjorden_generation_test` | 可航域三角化收到空 Polygon |
| `rogaland_random_rl` | 可航域三角化收到空 Polygon |
| `rrt_test` | 可航域三角化收到空 Polygon |
| `saved/rlmpc_scenario_ms_channel/...` | 嵌套场景 ID 无法由 `resolve_scenario()` 解析 |

19 个 schema-valid 场景仍需分级：

| 场景组 | 当前用途 | 完整能力证据 |
|---|---|---|
| `paper_ccta2023_head_on` | CCTA 2023 功能复现 | 保留论文复现；不作为首个算法能力基准 |
| `paper_ccta2023_multiship` | 多船接口、Tracker、PSB-MPC 短烟测 | 仅 0.2 s 集成证据，不是完整 500 s 验收 |
| `head_on` | Rule 14 算法能力基准 | Nominal/VO/SB-MPC × God/KF 六组合完整运行，无 fallback |
| `crossing_*/overtak*` | 后续 Rule 13/15/16/17 | schema-valid；规则模板尚未扩展 |
| `head_on_sbmpc` | 场景原生 SB-MPC | 可用于 SB-MPC 专项；选择 `nominal` 现被后端拒绝 |
| `rrt_test` | 目标为静态 RRT 展示 | 当前生成失败，不能使用 |
| `rl*`、`rlmpc*` | Gym/RL/RLMPC 配置研究 | 场景名不代表对应算法可运行 |
| `aalesund_random1` | nominal 完整基线 | 已有完整 nominal 证据 |
| 其他 ENC/保存/单船场景 | 回归或配置示例 | 需要逐场景完整运行门 |

算法身份已修复：`nominal` 只允许场景原生 guidance。场景嵌入 COLAV 时，
`nominal` 组合直接失败；manifest 同时记录 requested/executed algorithm、tracker、
能力等级、能力 profile 和 fallback。

### 3.1 Rule 14 首个正式能力矩阵

| Tracker | Nominal | VO | SB-MPC |
|---|---|---|---|
| God | 碰撞基线 | 43.36 m，无碰撞 | 94.17 m，无碰撞 |
| KF | 碰撞基线 | 43.70 m，无碰撞 | 91.81 m，无碰撞 |

六组合均识别 `head_on`，requested/executed 身份一致，`fallback=false`。
重建 Evaluator 仍只用于 `functional_reproduction`，不代表论文数值复现。

## 4. 必需的 Web 算法展厅

每个算法使用符合自身职责的代表场景，不强迫所有算法共用一个页面预设：

| 展厅 | 代表场景目标 | 必须展示 |
|---|---|---|
| Nominal | 单船/自然净空基线 | waypoint 跟踪、无算法机动、基线轨迹 |
| VO | 强制进入 VO 激活域的 HO/CR | velocity obstacle、候选速度、选中速度、触发时间 |
| SB-MPC | 动态 HO/CR/MS | 代价面、候选航向/速度、计划轨迹、明显避碰动作 |
| PSB-MPC | ENC + 动态多船 | polygons、tracks/covariance、offset、求解状态；必须进程隔离 |
| RRT | 岛礁/航道静态绕行 | hazard、CDT、tree、最终路径、节点数；不显示动态避碰评分 |
| RLMPC | 抗搁浅/动态约束场景 | NMPC horizon、约束、控制量、Acados 状态 |
| Tracker | 杂波、漏检、多目标交叉 | measurement、track、covariance、NIS、ID switch、RMSE |

Web 场景选择必须按算法 capability 过滤；算法标签必须显示：

```text
role
readiness_grade
supported_obstacles
verified_scenarios
latest_evidence
known_failure
requested/executed/fallback
```

## 5. 建设顺序

1. Rule 14 能力目录、真实身份、God/KF、VO/SB-MPC 诊断：完成。
2. Rule 14 Web/离线轨迹哈希、1440x900 和 390x844 浏览器视觉验收：完成。
3. VIMMJIPDA 完整跟踪门。
4. PSB-MPC 子进程隔离、Eigen 修复和完整 HO/MS。
5. 修复 `rrt_test` 安全海域，完成静态 RRT 展厅。
6. 安装并锁定 RLMPC 求解环境。
7. 复制 Rule 14 模板到 Rule 13/15/16/17，再进入 G4 统一矩阵。
