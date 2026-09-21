# 临时 Spec: GNC S9 栈 B — 验收矩阵与评估器指标（Issue #67 子集）

> 状态: 主 Agent 设计固化，供 subagent 严格执行
> 基线: feat/gnc-s9a-kernel（7 commits，已 push marine，含 FCB45 预设/内核补齐）
> 执行分支: feat/gnc-s9b-acceptance（自 s9a 分出）
> Worktree: /Users/marine/Code/Colav-Sim-gnc-s9a

## 1. 目标与验收门（不可协商）

九宫格矩阵 OT/HO/CS × {VO, potocnik_colreg_fan_mpc, mid_mpc_ipopt}，注入 FCB45 本船 stack：
- stack id: `fcb45_3dof_plant+pass_through_guidance+fcb45_marine_pid`（ideal 执行器）
- 每格断言：
  1. goal_reached（航线完成）
  2. 无碰撞、无搁浅
  3. 全程本船-各目标船最小中心距 ≥ 180 m（4×Lpp 44.1m）
  4. 返航窗口内对原航线 max|XTE| ≤ 50 m
  5. 重入后越线次数 ≤ 2（无 S 形拉锯）

场景本船航速 7.0 m/s（FCB45 服务 7.8 m/s 包线内）。

## 2. 设计决策

### 2.1 评估器指标（colav_simulator/evaluation/evaluator.py 附近，无 XTE 现状）
- `encounter_min_distance_m`：全程每个目标船与本船中心距的逐 tick 最小值（复用/扩展现有 trajectory_cpa 邻近逻辑，独立几何手算样例做测试期望值）
- 返航窗口定义：优先取 planner 返航/避碰结束状态；不可得则回退 CPA 时刻 + 240s 缓冲
- `return_max_abs_xte_m`：窗口内对**场景 yaml 原航线**（waypoint 折线最近距离）的 max|XTE|
- `return_route_crossings`：重入点（CPA 后 |XTE| 首次 < 100 m）到 run 结束的 XTE 符号变化次数
- 指标进 evaluator 报告结构，跟随现有 profile/结构惯例；不破坏现有报告消费方

### 2.2 验收间距 profile（acceptance 专用，shipped 默认零改动）
- Fan-MPC: `collision_distance_m` 150 → 190
- Mid-MPC: `cpa_safe_m` 150 → 190
- VO: 先挖 kuwata_vo.py 的名义间距形成机制（combined_hull_radius 由 OS/TS 尺寸组合 L715-720；VOParams.length_os=10/width_os=5 默认，os_length/os_width kwargs L374-377），把 OS 尺寸改 44.1×8.0，并找出把名义间距抬到 ≥190m 的参数面（VO 边界外扩/安全半径参数），记录推导；只经 kwargs/配置，禁改算法代码
- profile 落 config/ 下新文件，命名对齐现有惯例并标注 acceptance 专用

### 2.3 矩阵测试（tests/ 新文件）
- 先 VO×HO 单场景冒烟打通注入全链路，再铺满矩阵
- Mid-MPC 慢：参考 test_mid_mpc_single_encounter.py 规模与 domain profile 要求；必要时 pytest marker 分层
- 先例：test_kuwata_vo_closed_loop.py / test_potocnik_colreg_g3_matrix.py / test_mid_mpc_single_encounter.py / test_runner_gnc_stack_injection.py L52-70

### 2.4 整定规则（仅在格失败时）
- 优先级：间距 profile 微调（190→200+）> VO 参数 > 控制器预设确定性变体（推导值 ±30% 内，≤8 个）
- 10% 红线：任何调整不得使已过格指标恶化 >10%（同事寻优方法论，全候选记录：candidate/changed/结果/淘汰原因）
- 全绿后固化参数，campaign 报告 markdown（每格数值表：min distance/max XTE/越线数/pass）落 docs/ 或 runs/ 惯例位置

## 3. 操作纪律（踩坑清单）

1. **每切片完成立即 commit**（长测试可能触发派发超时被杀，commit 保进度；被杀后主 Agent 会从 commit 续派）
2. **分文件跑 pytest**：a3_demo/legacy_g6/ros_adapter 与其他 gnc 测试同进程组合跑会 SIGSEGV（main 基线既有问题）；单次 pytest 运行控制在 ~6 分钟内，长矩阵拆文件/拆场景跑
3. parquet 持久化同进程崩：测试内禁用 parquet 输出
4. 禁止：colregs-probe/MASS-L3 探测（另一项目）、GUI/serve 启动、改 colav_simulator/core/（legacy）与算法内部实现
5. legacy_g6 测试必须零改动零回归（单独跑验证）
6. TDD：每片先失败测试（行为断言、独立来源期望值），红→绿→commit

## 4. 切片顺序

1. 评估器指标（2.1）→ commit
2. 间距 profile + 加载测试（2.2）→ commit
3. VO×HO 冒烟（FCB45 注入全链路）→ commit；随后铺满矩阵测试 → commit
4. 矩阵执行 + 受约束整定（2.4）+ campaign 报告 → commit
5. 回归门：分文件 modular_gnc 全套 + evaluation 相关 + ruff + legacy_g6 单独 → 最终 commit
6. push: `git push marine feat/gnc-s9b-acceptance`

## 5. 回报格式

九宫格数值表（每格 min distance / max XTE / crossings / pass）、VO 间距机制结论与参数化方式、整定记录（若有）、评估器指标清单、回归结果、commit SHA 列表、偏离本 spec 的决策及理由。
