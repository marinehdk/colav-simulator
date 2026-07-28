# Dynamic MPC Playground Phase 2 实施计划

> 日期: 2026-07-28
> 状态: P2-Platform PASS / P2-Algorithm pending
> 实施分支: `codex/colav-backend-algorithms`
> 审计基线 commit: `3ece120`
> 当前 working tree 回归: `111 passed, 1 skipped`
> Source Spec: `docs/superpowers/specs/2026-07-28-dynamic-mpc-playground-design.md`

## 0. 实施结果

P2-Platform 已完成:

- strict `module:factory -> CustomMPCAdapter(ICOLAV)` 入口;
- typed PlannerInput/MPCSolution/AlgorithmDescriptor/build identity;
- t=0 solve、solve/hold、deadline、reset、六态失败;
- `DEPENDENCY_UNAVAILABLE -> SKIPPED/NOT_EVALUATED`;
- 矩形 footprint 同步连续段 boolean oracle;
- `plugin-check`、示例 fixture、Custom 专用 G3 附加 gate;
- 全量回归 `158 passed, 2 skipped`;
- Phase 2 修改面 targeted ruff PASS。

完整 P2 尚未通过。当前未收到 §3.3 定义的用户论文/自研 MPC factory、
依赖 lock、最小 config、native state/control/horizon 语义。示例 fixture 未加入
capability catalog，也未运行或冒充六场景 Custom G3 matrix。

## 1. Phase 2 目标

建立正式、低摩擦、可审计的 Custom MPC 接入链:

```text
外部 module:factory
  -> CustomMPCAdapter(ICOLAV)
  -> typed PlannerInput
  -> 用户/论文 MPC solve
  -> MPCSolution(control reference + 9xN horizon + diagnostics)
  -> solve/hold 调度
  -> Simulator 闭环执行
  -> footprint truth collision
  -> raw G3 evidence
```

完成后，导入一个兼容的 Python/CasADi MPC 不需修改 Simulator、Ship、
Session 或 registry 分支逻辑。算法作者只提供:

1. 一个 `module:factory`;
2. 一个 solve callable;
3. 一个 `AlgorithmDescriptor`;
4. 最小构造配置;
5. 依赖 lock/hash。

Phase 2 最终出口仍按 Spec:

- 用户实际论文/自研 MPC 经正式 Adapter;
- `head_on/overtaking/overtaken/crossing_give_way/
  crossing_stand_on/paper_ccta2023_multiship` 全部 raw G3;
- `strict_no_fallback=true`;
- physical collision 不再使用中心距阈值，而使用矩形 footprint 连续段
  boolean oracle。

## 2. 两级交付边界

### 2.1 P2-Platform:接入平台完成

可独立完成:

- Adapter、DTO、Descriptor、factory loader;
- solve/hold、deadline、六态错误;
- manifest SKIPPED/NOT_EVALUATED;
- footprint continuous-segment boolean;
- 示例插件、CLI conformance check、白盒测试。

示例/fixture MPC 只证明平台契约，不获得 capability grade，不代表用户论文
算法，不可用于宣告 Phase 2 完成。

### 2.2 P2-Algorithm:实际算法验收完成

依赖用户交付:

- 可加载 factory;
- 依赖 lock;
- 最小 config;
- 原生 state/control/horizon 语义说明;
- 实际 MPC 在六场景中的 raw run。

缺少任何入口材料时，只能宣布 `P2-Platform PASS`。不得宣布完整 P2 PASS。

## 3. 实施前必须冻结的 GATE

### 3.1 AlgorithmDescriptor 文档对齐

当前存在一个文档级不一致:

- 已确认 design-log DP-11 的 12 字段:
  `algorithm_id/version/control_form/state_layout/predictor_model/
  horizon_dt/horizon_steps/objective_terms/constraint_terms/solver/
  seed_policy/execution_profile`;
- Spec §5.3.3 第 394 行列出另一组 12 字段。

这不是新技术证据，不要求回炉 design-grounding；但实现前必须消除双 schema。

本 Plan 建议:

1. 以用户已确认的 DP-11 字段作为 `AlgorithmDescriptor` 唯一 canonical schema;
2. Spec 中第二组字段作序列化 envelope/派生字段:
   - `solver_type -> solver`;
   - `horizon_N -> horizon_steps`;
   - `dt_solve -> execution_profile.solve_period_s`;
   - `constraints -> constraint_terms`;
   - `cost_components -> objective_terms`;
   - `dependency_hash -> build_identity`;
   - `fallback_policy="forbidden"` 由正式 Adapter 固定;
   - `schema_version` 放 descriptor envelope;
   - `role="collision_avoidance"`、`supported_obstacles` 由 Adapter capability
     声明派生，不增加算法作者重复配置。
3. 实施首个 commit 将 Spec 该处改成 canonical + projection 说明。

未确认此映射，不开始 Descriptor 代码。

### 3.2 Factory 唯一路径

正式路径固定:

```text
RunSpec.algorithm_id
  + algorithm_config.factory="module:callable"
  -> IntegrationRegistry
  -> factory(context=FactoryContext, **kwargs)
  -> CustomMPCAdapter
```

约束:

- factory 必须返回 `CustomMPCAdapter`;
- 不接受任意 `ICOLAV` 绕过 Adapter;
- descriptor `algorithm_id` 必须严格等于 requested ID;
- registry 不为每个新论文算法增加 `if algorithm_id == ...`;
- legacy `guidance/custom_mpc_adapter.py` 不得被 registry import;
- legacy 只增加 deprecation doc marker，不修、不删、不复用 fallback。

### 3.3 实际算法 entry criterion

开始 P2-Algorithm 前，算法交付包须包含:

```text
my_mpc/
  plugin.py                 # 暴露 factory
  algorithm.py              # 算法本体，可在外部仓库
  config.yaml               # 最小构造参数
  requirements.lock         # 或 uv.lock/conda-lock
  README-contract.md        # native state/control/horizon 语义
```

P2 仅支持能在当前 Python 进程安全 import/execute 的算法。以下留 P5 Worker:

- 可触发 native abort/segfault;
- ABI/solver 依赖冲突;
- 必须独立 conda/container;
- 需要 hard process kill 才能执行 deadline。

### 3.4 身份与禁止 fallback

每个正式 run 必须可证明:

- `requested_algorithm == descriptor.algorithm_id == executed_algorithm`;
- `fallback_used == false`;
- factory ref、factory module SHA、descriptor hash、frozen config hash、
  dependency lock hash 均写 manifest;
- factory/solver exception 不得返回 nominal、VO、SB-MPC 或 previous plan;
- 只有 `TIMEOUT_FEASIBLE` 可执行本次可行解;
- 其他非 SUCCESS 状态正式 run fail-stop。

### 3.5 Footprint oracle

P2 不接受“每个 sim timestamp 采一个矩形”的实现。

固定采用同步时间自适应 subdivision:

1. 每步保存所有 active vessel 的 pre/post RK4 pose;
2. position 线性插值，heading 用 shortest-angle 插值;
3. 同一归一化时间 `tau` 同时求 A(tau)、B(tau);
4. 用矩形 footprint 做相交/距离检查;
5. 相对 corner motion 大于 `ccd_step_tolerance_m` 时递归二分;
6. 叶节点不确定时保守判 collision，禁止 false negative;
7. 返回 boolean + interval，不在 P2 伪造 first-TOC。

初始 tolerance 建议 `0.25 m`，并跑 `0.5/0.25/0.125 m` 收敛测试。
若标准 adversarial case 的 boolean 不稳定，默认值继续缩小，不放宽测试。

精确 synchronous C2A、first-TOC、screw-motion bound 留 P3。

## 4. 公共接入契约

### 4.1 FactoryContext

Adapter runtime 由平台注入，不让算法作者手填:

| 字段 | 语义 |
|---|---|
| `requested_algorithm` | RunSpec 选择的稳定 ID |
| `algorithm_seed` | `SeedBundle.algorithm` |
| `strict_no_fallback` | 正式 run 必须为 true |
| `solve_period_override_s` | RunSpec 可选覆盖 |
| `deadline_mode` | `ENFORCE` 或 `OFF` |

factory 示例:

```python
def create(*, context: FactoryContext, config_path: str) -> CustomMPCAdapter:
    solver = PaperMPC.from_yaml(config_path, seed=context.algorithm_seed)
    return CustomMPCAdapter(
        descriptor=build_descriptor(),
        solve=solver.solve,
        reset=solver.reset,
        context=context,
    )
```

不要求 subclass，不新增与 `ICOLAV` 平行的完整算法接口。算法只实现一个 typed
solve callable 和可选 reset callable。

### 4.2 PlannerInput

`PlannerInput` 为 frozen dataclass，由 Adapter 从现有 `ICOLAV.plan()` 参数构造:

| 字段 | 契约 |
|---|---|
| `sim_time_s` | simulator monotonic time |
| `dt_sim_s` | 正数，SI seconds |
| `waypoints_enu_m` | finite `(2,N)`,East/North local contract |
| `speed_plan_mps` | finite `(N,)`,与 waypoints 对齐 |
| `ownship_state` | finite `(6,)=[x,y,psi,u,v,r]` |
| `tracks` | frozen `TrackedObstacle` tuple |
| `enc` | in-process 完整 ENC，可为空但须由 descriptor 声明 |
| `goal_state` | `None` 或 finite `(6,)` |
| `disturbance` | 原样只读传递 |
| `algorithm_seed` | run 级 algorithm stream |
| `coordinate_frame` | 固定 `ENU` |
| `linear_unit` | 固定 `SI` |
| `angle_unit` | 固定 `rad` |

`TrackedObstacle`:

| 字段 | 契约 |
|---|---|
| `target_id` | 非负且唯一 |
| `state_enu` | finite `(4,)=[x,y,Vx,Vy]` |
| `covariance` | finite symmetric PSD `(4,4)` |
| `length_m/width_m` | 正数 |
| `observed_at_s/age_s` | 非负、profile 限内 |
| `degraded` | 过期但仍允许的 track 显式标记 |

当前 Ship 在同一个 `sim_time` 先 tracker 后 planner。P2 将该 same-step
事实显式转换为 `observed_at_s=sim_time_s, age_s=0`。不从未知 tuple 猜单位，
不以 God truth 替换无效 track。

输入错误 -> `INVALID_INPUT`，source=`SCENARIO`。

### 4.3 MPCSolution

solve callable 返回 frozen `MPCSolution`:

| 字段 | 契约 |
|---|---|
| `control_reference` | finite `9x1`,当前控制器执行参考 |
| `predicted_trajectory` | finite `9xN`,col-0=solve-time ownship |
| `status` | 六态之一 |
| `horizon_dt_s` | 正数，匹配 Descriptor |
| `objective` | optional，不跨算法比较 |
| `iterations` | optional，非负 |
| `feasible` | required bool for SUCCESS/TIMEOUT_FEASIBLE |
| `constraints` | 公共分类 + SI minimum margins |
| `target_predictions` | VR-14 schema |
| `algorithm_details` | 动态权重/mode/native diagnostics |

验证:

- `N == descriptor.horizon_steps`;
- Custom MPC G3 要求 `N >= 2`;
- trajectory col-0 与 ownship pose/state 在版本化 tolerance 内;
- horizon motion 连续、无非物理跳跃;
- `control_reference` 与同一 solve 输出绑定;
- `SUCCESS` 必须 `feasible=true`;
- `TIMEOUT_FEASIBLE` 必须有可执行 finite plan;
- 非成功状态不得携带待执行 fallback plan。

输出错误 -> `INVALID_INPUT` 或 `NUMERICAL_FAILURE`，source=`ALGORITHM`。

### 4.4 AlgorithmDescriptor

canonical 12 字段:

```text
algorithm_id
version
control_form
state_layout
predictor_model
horizon_dt
horizon_steps
objective_terms
constraint_terms
solver
seed_policy
execution_profile
```

`execution_profile` 至少包含:

```text
solve_period_s
deadline_s
max_consecutive_timeout
requires_enc
```

规则:

- frozen、可 canonical JSON、可 SHA-256;
- tuple/enum 等稳定值，禁止自由拼写的临时 key;
- solve period 必须是 `dt_sim` 整数倍;
- horizon 必须覆盖到下一次 solve;
- dependency/build identity 缺失时写 `UNKNOWN`，但正式 G3 不允许 UNKNOWN;
- 动态权重/horizon/mode 只写 `PlannerTrace.algorithm_details`，绑定 solve_id。

### 4.5 Solve/Hold

调度只在正式 Custom Adapter 内统一，P2 不迁移 VO/SB-MPC，避免破坏 P1:

| 时刻 | 行为 |
|---|---|
| `t=0` | 必须 solve，`solve_id=1` |
| solve due | 调 solver，成功后 solve_id +1 |
| hold | 不调 solver，solve_id 不变 |
| hold command | 按 `t_now-t_solve` 采样同一 horizon |
| hold trace | `solver_executed=false`，保留原 horizon/solve_time |
| reset | 清空 solve id、horizon、deadline counters、调用 solver reset |

deadline:

- Adapter wall-clock 包住 solve callable;
- 超 deadline 且有可行解 -> `TIMEOUT_FEASIBLE`;
- G3 不接受任何 `TIMEOUT_FEASIBLE`;
- `deadline_mode=OFF` -> manifest `diagnostic_only=true`，不得参加 G3;
- 连续 timeout 超 profile 上限 -> fail-stop，reason=`REALTIME`。

## 5. 实施任务

### Task 0:文档对齐与实施 checkpoint

**修改**

- `docs/superpowers/specs/2026-07-28-dynamic-mpc-playground-design.md`
- `docs/superpowers/plans/2026-07-28-dynamic-mpc-playground-phase2.md`

**步骤**

1. 按 §3.1 修正 Descriptor 双清单;
2. 记录 Phase 2 branch、base commit、工作区状态;
3. 排除所有当前用户 WIP，审计时包括:
   `colav_simulator/common/plotters.py`、
   `colav_simulator/viz/visualizer.py`、`tests/conftest.py`、
   `tests/test_matplotlib_backend.py`、
   `tools/macos/com.marine.colav-simulator.frontend.plist`、`AGENT.md`;
4. 文档单独 commit，代码尚未开始。

**Gate**

- Spec/Plan 对 Descriptor、factory、P2 exit 无矛盾;
- 不改 VR/ALT/技术规约。

### Task 1:落地 typed contracts

**新增/修改**

- `colav_simulator/core/colav/custom_mpc_adapter.py`
- `colav_simulator/core/colav/__init__.py`
- `tests/test_planner_input_validation.py`
- `tests/test_algorithm_descriptor.py`

**实现**

1. `FactoryContext/TrackedObstacle/PlannerInput/MPCSolution`;
2. canonical `AlgorithmDescriptor`;
3. stable serialization/hash/build identity;
4. 输入 shape/finite/PSD/age/dimension/unit validation;
5. 输出 `9x1/9xN`、col-0、continuity、descriptor consistency validation;
6. 错误 source 为 `SCENARIO/ADAPTER/ALGORITHM`。

**测试**

- valid same-step God/KF track;
- non-PSD、非对称、NaN covariance;
- duplicate/negative target ID;
- invalid ownship/waypoint/speed/goal shape;
- stale/degraded/rejected track boundaries;
- descriptor missing/unknown field、hash determinism、config mutation isolation;
- `9x1` horizon 只到 G2，不能满足 Custom G3;
- wrong col-0、wrong N、NaN、discontinuous trajectory。

**Gate**

```bash
uv run pytest \
  tests/test_planner_input_validation.py \
  tests/test_algorithm_descriptor.py -q
```

### Task 2:正式 Adapter 与 factory loader

**新增/修改**

- `colav_simulator/core/colav/custom_mpc_adapter.py`
- `colav_simulator/integrations/registry.py`
- `colav_simulator/experiment/runner.py`
- `colav_simulator/guidance/custom_mpc_adapter.py`
- `tests/custom_mpc_fixture.py`
- `tests/test_custom_mpc_adapter.py`

**实现**

1. 完整实现 `ICOLAV` 六个方法;
2. `plot_results()` no-op 返回 handles;
3. registry 传入 `FactoryContext`;
4. 未知 algorithm ID 只允许 factory 返回正式 Adapter;
5. descriptor ID 与 requested ID 严格匹配;
6. factory module/config/dependency hashes 写 manifest;
7. legacy module 只加 deprecation marker;
8. import/factory/solve exception 精确映射六态;
9. requested/executed/fallback identity 写 diagnostics + trace + manifest。

**异常矩阵**

| 注入 | 结果 |
|---|---|
| factory ref 无 `:` | INVALID_INPUT |
| module/dependency 缺失 | DEPENDENCY_UNAVAILABLE |
| callable 不存在 | INVALID_INPUT |
| 返回非 Adapter | INVALID_INPUT |
| descriptor ID 不匹配 | INVALID_INPUT |
| solver 返回 INFEASIBLE | fail-stop INFEASIBLE |
| solver exception | NUMERICAL_FAILURE |
| solver 返回 previous/nominal fallback | contract FAIL |

**Gate**

```bash
uv run pytest tests/test_custom_mpc_adapter.py -q
uv run pytest tests/test_ecosystem_integration.py tests/test_experiment_contracts.py -q
```

### Task 3:多率调度、deadline 与 trace

**新增/修改**

- `colav_simulator/core/colav/custom_mpc_adapter.py`
- `colav_simulator/core/colav/diagnostics.py`
- `colav_simulator/experiment/contracts.py`
- `colav_simulator/experiment/session.py`
- `tests/test_custom_mpc_schedule.py`
- `tests/test_rule14_planner_trace.py`

**实现**

1. `RunSpec.solve_period_s` optional override;
2. `RunSpec.deadline_mode`;
3. `RunManifest.diagnostic_only` + reasons;
4. t=0 solve、integer-ratio validation、hold sampling;
5. heading shortest-angle interpolation;
6. horizon exhaustion在构造/首 solve 时拒绝;
7. full solve event 只写一次;
8. hold frame 只引用同一 solve_id;
9. reset 清空 warm state/counters;
10. deadline 与 `TIMEOUT_FEASIBLE` policy。

**测试**

- `dt=0.5, solve_period=2.0` 的 solve 时刻严格为
  `0/2/4/...`;
- t=0 `solve_id=1`;
- hold 不增加 solve_id、不重置 horizon origin;
- hold 采样位置、course wrap 正确;
- non-integer solve period -> INVALID_INPUT;
- horizon 不覆盖下一 solve -> INVALID_INPUT;
- reset 后下一 episode重新从 solve_id 1;
- timeout feasible 可执行但 G3 predicate fail;
- deadline OFF -> diagnostic_only，G3 fail。

**Gate**

```bash
uv run pytest \
  tests/test_custom_mpc_schedule.py \
  tests/test_rule14_planner_trace.py -q
```

### Task 4:六态 run outcome 与 SKIPPED

**新增/修改**

- `colav_simulator/experiment/contracts.py`
- `colav_simulator/experiment/runner.py`
- `colav_simulator/experiment/batch.py`
- `colav_simulator/experiment/persistence.py`
- `gui_server/main.py`
- `tests/test_experiment_contracts.py`
- `tests/test_batch.py`
- `tests/test_web_api.py`

**实现**

1. 新增 machine-readable `execution_outcome`:
   `COMPLETED/FAILED/SKIPPED`;
2. `DEPENDENCY_UNAVAILABLE -> SKIPPED`;
3. evaluator status 固定 `NOT_EVALUATED`;
4. SKIPPED 保留 manifest/failure evidence，但不进入 failure rate、solver
   failure rate、score aggregate;
5. BatchRecord/summary 分开 `failure_count/skip_count`;
6. 其他五态保持 SUCCESS/soft-fail/fail-stop 语义;
7. strict run 任一 diagnostics fallback 立即失败。

**Gate**

```bash
uv run pytest \
  tests/test_experiment_contracts.py \
  tests/test_batch.py \
  tests/test_web_api.py -q
```

### Task 5:矩形 footprint continuous-segment collision

**新增/修改**

- `colav_simulator/core/collision.py`
- `colav_simulator/common/map_functions.py`
- `colav_simulator/simulator.py`
- `colav_simulator/experiment/session.py`
- `colav_simulator/gym/environment.py`
- `colav_simulator/schemas/simulator.yaml`
- `config/simulator.yaml`
- `tests/test_footprint_collision.py`
- `tests/test_simulator.py`
- `tests/test_gym.py`

**实现**

1. `create_ship_polygon()` 改为中心对称 `L x W` 四角矩形;
2. 新建单一 P2 collision oracle;
3. Simulator step 保存所有船 pre/post pose，避免顺序积分造成异步判断;
4. 同步自适应 subdivision;
5. 叶节点使用运动 bound 保守判定;
6. `determine_ship_collision()` 保持 bool API，内部改用新 oracle;
7. 增加 pair-level collision evidence:
   target ID、interval、oracle ID、tolerance;
8. Session/Gym 共用 Simulator oracle;
9. manifest 记录 `collision_oracle_id` 与 tolerance;
10. 中心距函数保留诊断用途，不再定义 physical collision。

**测试**

- 静态重叠/接触/明确分离;
- 高速 head-on 一步穿透;
- 高速 perpendicular crossing 一步穿透;
- 两船同向同速不误碰;
- 一船旋转扫过另一船;
- 只有独立 swept union 相交、同步时刻不相交的 false-positive case;
- 多船只返回真实碰撞 pair;
- tolerance 收敛;
- Session event/Gym info/Simulator bool 一致;
- rectangle 面积=`L*W`，四个角且旋转中心不漂移。

**Gate**

```bash
uv run pytest tests/test_footprint_collision.py tests/test_simulator.py tests/test_gym.py -q
```

### Task 6:快速导入工具与示例

**新增/修改**

- `colav_simulator/cli.py`
- `examples/custom_mpc_plugin.py`
- `config/custom_mpc_example.yaml`
- `docs/custom-mpc-plugin-guide.md`
- `tests/test_cli.py`

**实现**

1. `colav-sim plugin-check`;
2. `colav-sim run/batch --algorithm-config <yaml>`;
3. plugin-check 只做:
   import -> construct -> descriptor -> reset -> fixed-input solve ->
   output validation;
4. 示例插件使用确定性 fixture solver，不宣称真实 MPC;
5. 文档提供最小 30-50 行 factory/solve 示例;
6. 文档列出 ENU/SI/rad、state layout、failure/status、G3 matrix 命令;
7. plugin-check 输出 JSON，便于 CI:
   identity/hash/descriptor/status/horizon shape/reasons。

**目标**

新增兼容算法时，核心仓库代码改动为零。算法作者只新增外部 package + config。

**Gate**

```bash
uv run pytest tests/test_cli.py tests/test_custom_mpc_adapter.py -q
uv run colav-sim plugin-check \
  --algorithm custom_mpc_example \
  --algorithm-config config/custom_mpc_example.yaml
```

### Task 7:接入用户实际 MPC

**前置**

- 用户提供 §3.3 五项材料;
- 算法可 in-process 安全执行;
- Descriptor schema 已冻结。

**步骤**

1. 只写算法特定 plugin glue，不改正式 Adapter;
2. native state -> public `9xN` 映射逐维记录:
   source/unit/estimated/method;
3. 固定一组 `PlannerInput` 做白盒 golden fixture;
4. 先跑 `plugin-check`;
5. 再跑 `head_on × God × seed=0` 短 smoke;
6. 再跑完整 head_on，检查 solve/hold/deadline/footprint;
7. 最后跑六场景 raw matrix;
8. 算法行为未达 G3时，只修改算法或算法 config;
   不放宽 Adapter/G3/footprint gate。

**白盒 Gate**

- factory/descriptor/build identity PASS;
- fixed input 可重复;
- reset 后首 solve一致;
- full horizon `N>=2`;
- no fallback;
- injected infeasible/numerical/dependency failure 分类正确。

### Task 8:Custom MPC raw G3 matrix 与 promotion

**新增/修改**

- `tests/test_custom_mpc_g3_matrix.py`
- `colav_simulator/experiment/capabilities.py`
- `tests/test_p1_capability_api.py`
- 仅在实际算法需要时修改其外部 plugin/config

**固定矩阵**

`seed=0`、God tracker、`strict_no_fallback=true`,
`terminate_on_collision_or_grounding=false`:

| Scenario | Nominal threat | Custom MPC |
|---|---:|---:|
| `head_on` | required | G3 required |
| `overtaking` | required | G3 required |
| `overtaken` | required | G3 required |
| `crossing_give_way` | required | G3 required |
| `crossing_stand_on` | required | G3 required |
| `paper_ccta2023_multiship` | required | G3 required |

每个 Custom cell 同时满足:

1. P1 `G3DisplayPredicate-v1` 全部条件;
2. descriptor/build/dependency identity 完整;
3. t=0 solve，solve/hold 序列正确;
4. 每个真实 solve 都是 finite full `9xN`,`N>=2`;
5. 所有 planner status 为 SUCCESS;
6. 无 TIMEOUT_FEASIBLE;
7. 无 fallback;
8. footprint oracle 无 physical collision;
9. 正常 `time_limit|goal_reached`;
10. nominal/candidate scenario、seed、tracker、ENC、dt、t_end hash 相同。

promotion 顺序:

1. 保存 6 nominal + 6 Custom raw evidence;
2. raw matrix测试 PASS;
3. 人工核对 manifest/trace/footprint events;
4. 才加入 exact verified tuples;
5. capability API 回归。

fixture/example plugin 永不写入 capability catalog。

**Gate**

```bash
uv run pytest tests/test_custom_mpc_g3_matrix.py -q
uv run pytest tests/test_p1_capability_api.py tests/test_web_api.py -q
```

### Task 9:Phase 2 总验收

**回归**

```bash
uv run pytest -q
uv run ruff check \
  colav_simulator/core/colav/custom_mpc_adapter.py \
  colav_simulator/core/collision.py \
  colav_simulator/integrations/registry.py \
  colav_simulator/experiment \
  colav_simulator/cli.py \
  tests
```

**证据审计**

- 随机抽 1 个 solve event，核对 descriptor/config/build hashes;
- 随机抽 1 个 hold frame，核对 solve_id/horizon origin/command sample;
- 检查一个 injected dependency failure 为 SKIPPED/NOT_EVALUATED;
- 检查一个高速 tunneling fixture 被 footprint oracle 捕获;
- 检查六个 Custom G3 evidence directory;
- 检查 capability promotion 只含实际通过 exact tuples。

## 6. 推荐 commit 切片

1. `docs: lock phase2 adapter and descriptor contracts`
2. `feat: add typed custom mpc contracts`
3. `feat: load custom mpc through strict icolav adapter`
4. `feat: add custom mpc solve hold scheduling`
5. `feat: persist skipped algorithm outcomes`
6. `feat: detect continuous rectangular footprint collisions`
7. `feat: add custom mpc plugin check and example`
8. `test: gate user custom mpc across colregs scenarios`
9. `feat: promote verified custom mpc capability tuples`

每个 commit 对应独立 test gate。禁止把实际算法调参与 Adapter/footprint 修改混在
同一 commit。

## 7. 明确不在 Phase 2

- Woerner/Eriksen FSM 与 Rule 17 profile;
- C2A exact first-TOC;
- 三套 CPA 统一;
- grounding footprint CCD 与 ENC 四类清理;
- canonical set、3 seeds、统计结论;
- subprocess/container isolation;
- PSB/RLMPC native mapping/修复;
- P6 replay/evidence package/Web read-only 扩展;
- 论文 numerical reproduction;
- 不同算法 objective 横向比较。

## 8. 主要风险与止损

| 风险 | 止损 |
|---|---|
| 双 Descriptor schema | Task 0 先对齐，未确认不写代码 |
| factory 返回任意 ICOLAV 绕过验证 | registry 强制返回正式 Adapter |
| 外部算法污染 core | callback + config，禁止按算法 ID 分支 |
| native abort 杀主进程 | P2 拒绝该 execution profile，转 P5 |
| track tuple 无 age | same-step 显式 age=0，不猜未知来源 |
| hold horizon 过短 | 构造/首 solve 时拒绝 |
| TIMEOUT 被统计为成功 | G3 hard reject，单独记录 REALTIME |
| SKIPPED 混入 failure/score | 独立 execution_outcome |
| footprint timestamp tunneling | 同步 subdivision + conservative leaf |
| conservative CCD false positive | tolerance 收敛测试，P3 C2A 精化 |
| fixture 被冒充实际 MPC | fixture 永不 promotion |
| 为过 G3 调低门槛 | 只改算法/plugin config，不改 gate |

## 9. Definition of Done

只有全部满足才标 Phase 2 完成:

- Descriptor 文档冲突已消除;
- 正式 Adapter 是 Custom MPC 唯一生产入口;
- 新算法接入不修改 core/registry 分支;
- PlannerInput/MPCSolution/Descriptor contract tests PASS;
- factory/identity/exception mapping tests PASS;
- t=0 solve、hold、deadline、reset tests PASS;
- DEPENDENCY_UNAVAILABLE 为 SKIPPED/NOT_EVALUATED;
- physical collision 使用矩形 footprint continuous-segment boolean;
- 用户实际 MPC 白盒 conformance PASS;
- 用户实际 MPC 六场景 raw G3 PASS;
- raw evidence 先于 exact capability promotion;
- VO/SB-MPC P1 回归无退化;
- 全量 pytest 与 targeted ruff PASS。

若用户算法尚未提供或任一 Custom G3 cell 未通过，状态只能是:
`P2-Platform complete / P2-Algorithm pending`。
