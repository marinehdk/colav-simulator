# AGX L4-5 tests / validation / historical constraints evidence audit

日期：2026-08-28

范围：回答 design-grounding Step3 的两个盲区：

- BL-02：恢复的 tests、validation、trace 能证明什么，是否足以构建迁移 characterization oracle。
- BL-08：哪些源行为具有物理/算法依据，哪些更像船型参数、运行机制、实验候选或历史场景修补。

方法：只使用 AGX 与本地冻结副本的一手源码、测试、设计文件、campaign 报告和 trace。未使用 NLM。后台 research 代理未能在大证据树中收敛写盘，最终证据由主线程直接审计；不降低原始文件权威，但降低“检索覆盖”置信度。

## 1. Evidence snapshot

本地目录：`/Users/marine/Code/external_sources/L4-5_evidence_20260828`

- 1784 个受控文件；`SHA256SUMS.txt` digest：`6b33f861f65e34bb2122847e666d02c92dfac5f39877b7cb35c604e35cd5c644`。
- Whole/filtered `rsync -anic --delete`：`diff_groups=0`。
- 包含 core tests、docs、reports、validation scenarios、SDK、quality audit metadata、10 个代表 campaign 的小于等于 5 MiB 文本/JSON/YAML/CSV。
- 包含 hash 验证的 2026-08-24 code-quality source archives 和 2026-08-25 control-architecture 前备份。
- 排除 17 GiB 全量 campaigns、大 build/install/log/image 和大于 5 MiB 的 campaign 文件；因此不是完整运行档案。

关键版本事实：

- 2026-08-24 source-only manifest 的 183 项与 2026-08-28 当前正式源码比较：25 changed、1 missing。
- 当前 core tests 不能自动视为与 `L4-5_source_only_20260824_v2` 同版。
- 8/04 hydrodynamics V&V contract 冻结的 `ship_dynamics_node.cpp` hash 是 `ee3a...`，而 source-only v2 manifest 是 `a475...`；该 contract 的 generated config hash 也与 v2 不同。
- 因此任何 oracle 必须绑定 source/config/test 三者 hash，不能混用“当前 tests + 8/24 source-only”。

## 2. BL-02: tests/validation 能证明什么

### 2.1 已恢复的强证据

#### Environmental pure kernels

`core_tests/environment/test_env_load_p8_wind_current_model_contract.py:16-178`：

- 明确要求 wind/current model 无 ROS 依赖；
- 单独用 C++17 编译运行纯模型；
- 验证节点调用纯模型 interface。

`test_env_load_p9_model_baseline_contract.py:20-150+`：

- 记录 wind/current/wave 三个数值 baseline；
- 使用 per-case abs/rel tolerance；
- 明确资产 replacement contract；
- 可直接转为 C++/Python differential fixture。

`core_tests/environment/test_env_physics.cpp:10-64`：

- encounter frequency 使用完整 body velocity projection；
- current reference 恢复方向；
- current load 对相对速度二次缩放。

结论：环境纯 kernel 已有较好的 characterization 起点。它证明软件公式在固定输入上自洽，不证明 mock coefficient 或目标船型准确。

#### Plant mathematical contracts

`core_tests/ship_dynamics/test_dynamics_contracts.cpp:24-101`：

- 质量矩阵对称正定；
- Coriolis skew-symmetry / power-neutral；
- 阻尼自耗散、耦合项不注入能量；
- 代表速度网格检查。

`test_relative_damping_model.cpp:10-64`：

- 零流与 legacy 一致；
- 顺流/逆流改变 surge damping；
- 横流只改变 sway/yaw 分项；
- drag scale 显式。

归档 `test_hydrodynamics_vv_contract.py:43-119` 增加：

- V0/V1/V2/V3 证据等级；
- damping oddness、Coriolis power neutrality、左右镜像；
- V3 被明确标记 `blocked_until_external_data_exist`。

结论：足以复用为新通用 plant 的 G2 physics kernel contract；不足以证明 source-only v2 全步 derivative/RK4 parity。

#### Controller helper tests

`core_tests/ship_control/test_control_math.cpp:1-49` 只覆盖：

- back-calculation；
- finite clamp；
- heading quiet-zone hysteresis；
- yaw-rate shaping；
- DP position deadband。

未覆盖完整 `control_loop()` 中的 P/I/D/SMC/NDO/gain schedule/feedforward/mode transition/update order。

结论：可作为小 helper characterization；不能作为“PID controller 已有 oracle”。必须新增完整 state trace harness。

#### Guidance policy tests

`test_guidance_policy.cpp` 包含大量独立 policy tests，例如 corridor、terminal channel、DP stop、cruise envelope、turn cap、current crab filter。它证明这些函数在给定常数下符合当前预期。

局限：测试大量使用 `30m/60m/7.2mps/900m/440m` 等固定门限，通常验证现状而非门限来源；未覆盖约 3719 行 `calculate_los()` 的完整时序、route switch、integral state 和 cross-module interaction。

#### Allocator kernels

`test_pgd_solver.cpp:9-71`：

- box-constrained QP 的 PGD 解；
- warm-start deterministic；
- achieved/residual evaluation；
- side-thruster/rudder policy 的特定门限。

`test_propeller_curve_map.cpp:22-74`：

- grid、bilinear interpolation、inverse mapping；
- 超表/倒车状态。

结论：PGD 和 curve-map 可形成独立 fixtures；特定 actuator policy/curve 属于 vessel asset/policy，不是通用 allocator 证明。

### 2.2 闭环与 campaign 证据

`PID参数寻优交接文档.md:57-144` 冻结一组正式 yaw `Kp/Ki/Kd` 和三个场景 baseline；`148-204` 记录两个候选因横流退化被拒；`238-340` 明确逐场景优化/淘汰流程。

`h34_guidance_control_attribution_v2/H34_离线归因结论.md:3-13`：

- 只对一条 H24 转弯 trace 做离线归因；
- 相关系数 0.07、低置信；
- 明确不能把问题归因于单一 ILOS 参数，不宣称推广。

`h39...严格结论.md:3-24`、`h40...严格结论.md:3-24`、`h70...验证结论.md:7-20`：

- 多个 controller/guidance 候选被明确拒绝或停止推广；
- XTE 改善可伴随舵活动或 heading/yaw 退化；
- 正式源码 hash 未被候选污染。

`ilos_guidance_simplification.../selection_manifest.json:2-15`：

- D30 仅被选为 fallback baseline；
- `promotion_status=NOT_PROMOTED`；
- G3D/G4/G4.1/G5/G6 被拒。

`selected_D30_campaign_summary.md:1-7`：三次重复运行仍全部列为 FAIL，包含 XTE、late divergence 和 speed instability。

结论：campaign 很适合证明“哪些方案尝试过、哪些明确失败、哪些 trade-off 存在”；不适合作为通用算法成功证书。

### 2.3 BL-02 证据判断

恢复证据足以：

- 建立 environment pure-model golden fixtures；
- 建立 M/C/D/relative-damping 物理 contract；
- 建立 PGD/curve-map fixtures；
- 提取 guidance/controller helper characterization；
- 建立闭环场景/metric/trade-off 库；
- 识别 source behavior 的失败历史和有意回退。

恢复证据仍不足以：

- 直接证明 source-only v2 与当前 tests 同版；
- 证明完整 `ship_dynamics` derivative+RK4 单步数值；
- 证明完整 controller P/I/D/SMC/NDO 内部 state update；
- 证明完整 ILOS route lifecycle；
- 证明 45m vessel hydrodynamic fidelity；
- 证明任一候选跨船型通用。

必须补建：绑定 v2 manifest 的 C++ characterization harness，输出 derivative/RK stages/controller state/guidance state/actuator achieved tau。当前证据是 harness 的材料，不是完成的 oracle。

## 3. BL-08: source behavior classification evidence

### 3.1 DomainInvariant 候选（强）

- M finite/symmetric/positive-definite contract。
- C skew-symmetry / power neutrality。
- D dissipativity 与 zero-velocity zero-load。
- relative-water velocity 的 damping 语义。
- encounter frequency 对 full body velocity projection。
- frame/unit/direction 显式验证需求。
- deterministic PGD kernel 与 achieved/residual 计算。

依据：上述纯函数/数学 property tests。它们适合进入通用 kernel，但实现形式仍需重新设计。

### 3.2 VesselParameter / DebugAsset（强）

- 45m vessel `Lpp=44.1/B=8/draft=2/mass=220000/Izz=27000000`。
- hydrodynamic coefficients、PID gains、actuator layout/curve、rudder/tunnel-thruster limits。
- wind/current/QTF mock asset；RAO missing。

归档 `hydrodynamics_vv_contract.yaml:4-7,26-42,56-76,166-173` 明确：

- 目标是 bound、not claim 45m trajectory fidelity；
- coefficient confidence D；
- V3 需要 CFD/tank/trial/full-scale data，当前 blocked。

它们应作为 preset/asset 和 debug baseline，不进入通用公式默认值。

### 3.3 RuntimeAdapter（强）

- ROS topic/QoS/timer/health/freshness/parameter callback。
- source-text contract tests、status escalation、asset metadata bridge。
- Domain ID、single-publisher、stale message 等运行完整性门。

这些要求对 ROS/SIL 有价值，但不属于 Python kernel 数学接口。

### 3.4 ExperimentalCandidate（中高）

- SMC robust term、NDO、gain scheduling。
- current/wind crab、current vector preview、environment feedforward。
- ILOS turn/rejoin/corridor/cruise envelope policy。
- inferred wave drift without real QTF/RAO。
- rudder floor、side-thruster speed authority policy。

证据显示这些功能有局部测试和 campaign，但多数只在一个 45m/H24/少量路线环境验证。多个候选明确 NOT_PROMOTED/FAIL/REJECT。适合独立 option/ablation，不应默认进入 baseline。

### 3.5 Reject 候选（中高）

- Plant 内速度硬 clip、yaw-rate guard、异常自动 state reset：归档 V&V contract `invalidation_rules:156-163` 明确把 guard activation 视为无效证据。
- 依赖场景阈值才能 PASS 的 turn/rejoin/speed floor：缺跨船型依据。
- 多层重复环境补偿：campaign 报告显示 XTE 改善可换来 heading/yaw/saturation 退化。
- 将 invalid/NaN 数值强制变零并继续正式结果：适合外围 fail-safe，不适合作为物理真值。

这些仍需逐 behavior card 确认；“Reject 候选”不是 Step3 最终裁决。

### 3.6 Historical tuning concentration

AGX 顶层 `validation_campaigns` 共 220 个目录：

- `ilos*`：133；
- 名称含 `pid`：13；
- `h<number>*`：55。

该计数不能证明每个规则错误，但结合 H34/H39/H40/H70、D30 selection 和代码质量报告，可高置信证明：Guidance/Control 的当前复杂度大量形成于连续单场景/单问题候选迭代，不应整体视为通用需求。

`L4-5_CPP_HPP源码质量审计与整理报告_20260824.md:36-47,87-96`：

- `calculate_los` 约 3719 行；
- controller loop 约 599 行；
- 建议逐个提取 pure policy 并每次做行为保持回归；
- 不建议巨型机械重构。

这与本设计的 kernel seam、逐行为证据卡和小切片发布一致。

## 4. Evidence confidence matrix

| Evidence | Answers | Retrieval confidence | Source authority | Scenario applicability |
|---|---|---|---|---|
| Snapshot scope/hash and rsync verification | Evidence copy identity | 高 | 高（直接文件/hash） | 高 |
| Current-vs-v2 manifest comparison | Tests/source version drift | 高 | 高 | 高 |
| Env pure tests + numeric baseline | Env kernel characterization | 高 | 高（执行型测试） | 高（软件）/低（真实船） |
| Dynamics property tests | M/C/D invariants | 高 | 高 | 高（通用 contract） |
| Archived hydrodynamics V&V contract | Evidence levels/limits | 高 | 中（项目自定义 contract） | 中（hash/convention 与 v2 有差异） |
| Controller helper tests | Helper semantics | 高 | 高 | 低（不覆盖完整 controller） |
| Guidance policy tests | Current policy semantics | 高 | 高 | 中低（固定门限/单船） |
| PID handoff + selected campaigns | Tuning history/trade-offs | 高 | 中（内部工程报告） | 中（45m/H24 场景） |
| Code-quality audit | Structure/test-count/build history | 高 | 中（内部自审） | 中（current formal，不完全等于 v2） |
| 220 campaign inventory | Tuning concentration | 高 | 高（目录事实） | 高（复杂度来源），不证明单项正确性 |

## 5. Step3 answer

### BL-02

证据已回答“现有材料能否直接作为 oracle”：**不能直接作为 source-only v2 的完整 oracle，但足以建立分层 characterization harness；环境和数学 property 部分已有可复用 fixtures。**

建议状态：等待用户确认后，将 BL-02 从“未闭环”改为“已闭环→证据表明必须新建 version-aligned harness”。

### BL-08

证据已回答 family-level 分类：物理不变量、船型资产、ROS 运行机制、实验候选、Reject 候选可以明确区分；也高置信证明 Guidance/Control 复杂度高度受历史 candidate tuning 影响。

限制：尚未对源代码每一个 threshold 建完 behavior card；该工作属于 Step4/实施前审计清单，不应阻塞 family-level 方案设计。

建议状态：等待用户确认后，将 BL-08 标为“已闭环→采用逐 behavior evidence card，不整体采纳历史门限”。

## 6. New conflicts exposed by evidence

1. **Version conflict**：current tests/current formal source 与 2026-08-24 source-only baseline 不同版。
2. **Coordinate conflict**：归档 V&V contract 使用 body `y=port/z=up/yaw CCW`；当前消息/代码多处描述 `y=starboard/z=down/right-turn positive`。迁移 fixture 必须绑定版本并由 basis-vector probe 判定，不能信注释。
3. **Claim conflict**：部分报告标题/selection 使用“baseline/完整航线”，但同一证据又标 FAIL/NOT_PROMOTED。报告解析必须读取 machine status，不凭标题。
4. **Test coverage conflict**：质量审计报告称正式 221 tests pass，但 source-only bundle 排除 tests，且 recovered tests 不同版；这不是 v2 acceptance proof。

这些冲突进入 Step4 的风险/失效边界，不在 Step3 自动裁决。
