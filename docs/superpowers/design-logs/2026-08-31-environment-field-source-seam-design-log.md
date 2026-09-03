# 设计日志: EnvironmentField source seam 回炉

> **模式**: 重构        **创建**: 2026-08-31
> **关联 spec**: `docs/superpowers/specs/2026-08-28-agx-l45-gnc-integration-design.md`
> **状态**: 已裁决(2026-09-01)·可派发实现

> **回炉原因**: Issue #49 实施前发现既有 DP-09/VR-09 只冻结了“环境数据与船舶载荷分离、wind/current/first-order-wave/mean-drift 分项”，没有冻结 `EnvironmentField` 对 mean drift 的物理字段。领域证据表明 mean wave drift 通常是波浪与具体浮体/船体耦合产生的二阶力/矩或 QTF 响应，不能无证据地伪装成 vessel-independent `force_ne` field。

## 0. 决策树状态(权威索引 · 可变快照)

### 0.1 决策点注册表 [DP]

| ID | 描述 | 类型 | 父/分解 | 状态 | 详见 |
|----|------|------|---------|------|------|
| DP-01 | 划定 vessel-independent wave field 与 vessel-dependent first-order/mean-drift load 的职责边界 | 架构 | TD-01 | 已裁决 | VR-49-01 |
| DP-02 | 冻结 wind/current/first-order-wave/mean-drift 四类 source identity 的最小 typed 字段与单位 | 接口 | TD-01 | 已裁决 | VR-49-02 |
| DP-03 | 冻结 simulation tick 与 RK-stage 查询的精确时间坐标，避免 float stage identity 漂移 | 接口 | TD-01 | 已裁决 | VR-49-03 |
| DP-04 | 选择 order-independent deterministic field 生成机制：解析场、keyed PRF 或 stateful RNG | 算法 | TD-01 | 已裁决 | VR-49-04 |
| DP-05 | 冻结 truth、observation、estimate、unavailable 的类型边界及 quality/age/source 语义 | 接口 | TD-01 | 已裁决 | VR-49-05 |
| DP-06 | 冻结 shared pure field、per-stack held sample/observation、reset/snapshot/restore 的状态所有权 | 架构 | TD-01 | 已裁决 | VR-49-06 |

### 0.2 技术分解注册表 [TD]

| ID | 技术 | 分解子模块(→DP) | 触发步骤 |
|----|------|------------------|----------|
| TD-01 | EnvironmentField public contract | field/load boundary(DP-01)、source schema(DP-02)、time query(DP-03)、determinism(DP-04)、truth/observation(DP-05)、lifecycle ownership(DP-06) | Step1 |

### 0.3 盲区注册表 [BL]

| ID | 问题 | 归属决策点 | 优先级 | 调研状态 |
|----|------|-----------|--------|----------|

### 0.4 证据矩阵 [EV]

| ID | 来源类型 | 引用 | 检索置信 | 来源权威 | 场景适用 | 归属 |
|----|----------|------|----------|----------|----------|------|
| [R1] | DOCUMENTED_INTENT | 既有 binding spec、solution pack、主设计日志 DP-09/VR-09/TS-07..10/15/16/21 | 高 | 高 | 高 | DP-01..DP-06 |
| [R2] | PROJECT_FACT | 当前 modular contracts/scheduler/pass-through modules 与 Issue #49 acceptance | 高 | 高 | 高 | DP-03..DP-06 |
| [R3] | PROJECT_FACT | frozen v2 env_engines headers/source 与 #48 characterization fixture | 高 | 高 | 中 | DP-01/DP-02 |
| [R4] | DOMAIN_EVIDENCE | ITTC 7.5-02-07-03.1 drift-force procedure | 高 | 高 | 中 | DP-01/DP-02 |
| [R5] | INDUSTRY_EVIDENCE | OrcaFlex vessel wave-drift/QTF theory | 高 | 中高 | 高 | DP-01/DP-02 |

### 0.5 场景注册表 [SC]

| ID | 场景描述 | 约束/边界 | 驱动决策点 |
|----|----------|-----------|-----------|
| SC-01 | 同一不可变环境场被多船以不同顺序、同一 tick/stage/position 查询 | 查询顺序不改变每个结果；无 shared mutable RNG | DP-03/DP-04/DP-06 |
| SC-02 | #50/#51 使用同一 wave source 为不同 vessel asset 计算不同 first-order/mean-drift loads | EnvironmentField 不含 vessel force/moment、RAO/QTF 或船型系数 | DP-01/DP-02 |
| SC-03 | modular plant 消费 truth，guidance/controller 只消费 observation/estimate | 类型层拒绝 truth leakage；缺失 source 显式 unavailable/failure | DP-05/DP-06 |
| SC-04 | RK4 在同一 simulation tick 查询多个 stage time | stage query 精确、纯函数、无离散 RNG/state advance | DP-03/DP-04 |

### 0.6 裁决注册表 [VR]

| ID | 裁决对象 | 结论 | 采纳/弃用 | 理由 | 时间 |
|----|----------|------|-----------|------|------|
| VR-49-01 | DP-01 职责边界 | EnvironmentField 仅含 vessel-independent 原始环境描述符（风/流矢量、波浪谱分量）；一切环境力/矩（含一阶浪、mean-drift）属 #50/#51 vessel-dependent load；field 无力/矩/RAO/QTF/船型系数 | 采纳(final) | frozen `WaveDriftModelCalculator` 全部 API 需 `WaveModelVesselParams` 且输出 load [R3]；`WaveModelLoadsSeparated` 为 8 分量力/矩结构非场结构 [R3]；spec L103 field/load 分离；ITTC/OrcaFlex drift=二阶船体响应 [R4][R5] | 2026-09-01 |
| VR-49-02 | DP-02 source schema | 四类 source 最小 typed 字段：`WindSample{velocity_ne(vn,ve) m/s, reference_height_m}`、`CurrentSample{velocity_ne, reference∈{surface,depth_averaged}}`、`WaveFieldSample{significant_height_m, peak_period_s, direction_to_rad, components[{amplitude_m, omega_radps, phase_rad, direction_to_rad}]}`、`MeanDriftSourceSample{波能输入引用(波分量+方向分布), 显式标注非力}` | 采纳(final) | frozen drift API 输入(components+directional samples)反推覆盖 [R3]；TS-07 to-矢量；#49 验收 distinct samples；不伪造 vessel-independent 力 | 2026-09-01 |
| VR-49-03 | DP-03 时间坐标 | 查询=`sample_at(tick:int, stage_offset_s:float∈[0,dt), position_ne)` 纯函数，`t=tick*dt_s+stage_offset`；env phase 按 `plant_period_ticks` 到期采样并 ZOH；stage-time 采样 API 现在冻结，RK4 实现留 #52 | 采纳(final) | TS-08 integer tick 唯一时间权威、TS-09 固定 phase order+ZOH、TS-13/14 stage-time forcing 纯计算 [R1][R2] | 2026-09-01 |
| VR-49-04 | DP-04 确定性机制 | 构造期一次性 keyed PRF 派生（field_seed=derive(episode_seed,"environment_field")，不含 ship index），查询期纯函数零 RNG；风/流时间变化=解析基值+PRF(tick) 扰动，无状态递推 | 采纳(final) | TS-16 seed tree+禁 random_device；VR-21 共享 immutable 场+顺序无关 replay [R1][R2]；legacy `GaussMarkovDisturbance` 为 stateful 递推不可共享化 [R2] | 2026-09-01 |
| VR-49-05 | DP-05 truth/observation 边界 | `EnvironmentTruth`/`EnvironmentObservation`(+source/quality/age) 独立 frozen dataclass；plant-facing API 参数类型=Truth，guidance/controller-facing 仅 Observation/estimate；unavailable=显式 status 枚举+结构化 failure，禁 fallback | 采纳(final) | spec L102/L124；TS-21；RA-05 类型级隔离手法 [R1]；#49 阶段 observation 由 truth 显式构造 pass-through 且类型隔离 | 2026-09-01 |
| VR-49-06 | DP-06 状态所有权 | 每 episode 一个共享 immutable field（或相同 config_hash+field_seed 确定性重建的等价 immutable 实例）；per-stack 最近 held sample 为 per-ship 状态并进 `StackSnapshot` 参与 reset/snapshot/restore；field 本身不序列化进 snapshot | 采纳(final) | spec L126 共享场 immutable+每船拥有可变状态；TS-15 snapshot 绑定 hash [R1][R2]；stack.py:40-72 骨架已在 | 2026-09-01 |

### 0.7 备选/弃用方案 [ALT]

| ID | 方案 | 弃用理由 | 对比于 |
|----|------|----------|--------|
| ALT-49-01 | EnvironmentField 增加 `mean_drift_force_ne` vessel-independent 漂移力字段 | 无证据支持 vessel-independent 漂移力；违反 VR-09/[R4][R5] | VR-49-01 |
| ALT-49-02 | 查询期 stateful shared RNG | 船序依赖，违反 VR-21/SC-01 | VR-49-04 |
| ALT-49-03 | per-ship 独立演化环境场 | 违反 DP-21 共享纯场 | VR-49-04 |
| ALT-49-04 | truth/observation 同类型+bool flag | 可绕过，非类型级隔离 | VR-49-05 |
| ALT-49-05 | legacy polar `(speed, direction-from)` 标量形态入 field | 违反 TS-07 核心内禁猜方向 | TS-49-01 |
| ALT-49-06 | snapshot 序列化整个 field | 冗余；field 由 config_hash+field_seed 可重建 | VR-49-06 |

### 0.8 技术规约注册表 [TS]

| ID | 类别 | 规约内容 | 单位/定义 | 来源 | 关联DP/接口 | 与现状差异 |
|----|------|----------|-----------|------|-------------|-----------|
| TS-49-01 | 坐标系/方向 | field 全部矢量=NE world to-方向；标量方向角=compass rad（0=+N，顺时针正，=atan2(ve,vn)）；SI 单位（m/s、m、rad、rad/s） | NE world / SI | DESIGN_DECISION(VR-49-01/02)+TS-07 | EnvironmentField | legacy 为 polar from-标量（stochasticity.py:273），转换责任在 adapter 层 |
| TS-49-02 | 接口 | 四 source dataclass 字段冻结：`WindSample{velocity_ne, reference_height_m}`；`CurrentSample{velocity_ne, reference}`；`WaveFieldSample{significant_height_m, peak_period_s, direction_to_rad, components[{amplitude_m, omega_radps, phase_rad, direction_to_rad}]}`；`MeanDriftSourceSample{wave 分量+方向分布引用, 显式非力}` | 见 VR-49-02 | DESIGN_DECISION(VR-49-02) | contracts.py / #51 | 现状 contracts.py 零环境类型 |
| TS-49-03 | 时序 | `sample_at(tick:int, stage_offset_s:float, position_ne:(n,e) m)` 纯函数；`t_s=tick*dt_s+stage_offset`；`stage_offset∈[0,dt)` 由 scheduler 传入；env phase 按 `plant_period_ticks` 到期采样并 ZOH | integer tick | TS-08/09 [R1] | stack.py `_phase_due` / #52 | 现 passthrough environment phase 仅记录 |
| TS-49-04 | 随机 | field 内容=纯函数(config, field_seed, source, index, tick)；`field_seed=derive(episode_seed, "environment_field")` 不含 ship index；wave 相位构造期 PRF 定死；查询期零 RNG、禁 random_device/wall clock | integer seed tree | TS-16 [R1] | EnvironmentField | legacy GaussMarkov 为 stateful，不做等价承诺 |
| TS-49-05 | 类型 | `EnvironmentTruth`/`EnvironmentObservation` 独立 frozen dataclass；Observation 含 source/quality/age；plant-facing API 参数类型=Truth；guidance/controller-facing 仅 Observation/estimate；unavailable=显式 status 枚举+FailureCode 结构化失败，禁 fallback/外推 | type-level | TS-21/RA-05 [R1] | contracts.py / #49 API | 新增 |
| TS-49-06 | 生命周期 | field 构造后 deep-frozen 无 setter；per-stack 最近 held sample 为 per-ship 状态，参与 reset 幂等/snapshot/restore（含 tick 对齐）；field 不进 snapshot，由 config_hash+field_seed 重建 | deterministic | TS-15 [R1] | StackSnapshot | stack.py 已有 reset/snapshot/restore 骨架，补 held sample |

---

## 参考文献

- [R1] `docs/superpowers/specs/2026-08-28-agx-l45-gnc-integration-design.md`；`docs/superpowers/specs/2026-08-28-agx-l45-gnc-integration-solution-pack.md`；`docs/superpowers/design-logs/2026-08-28-agx-l45-gnc-integration-design-log.md`。
- [R2] `colav_simulator/modular_gnc/{contracts.py,stack.py,passthrough_modules.py,configuration.py}`；GitHub Issue #49。
- [R3] `/Users/marine/Code/external_sources/L4-5_source_only_20260824_v2/src/environment/env_engines/`；`tests/fixtures/gnc_characterization/`。
- [R4] ITTC, *Recommended Procedures and Guidelines: Floating Offshore Platform Experiments*, 7.5-02-07-03.1, section 3.2.11 Drift Force, https://www.ittc.info/media/8115/75-02-07-031.pdf.
- [R5] Orcina, *Vessel theory: Wave drift and sum frequency loads*, https://www.orcina.com/webhelp/OrcaFlex/Content/html/Vesseltheory%2CWavedriftandsumfrequencyloads.htm.

---

## 演进日志(append-only · 时序 · 不可覆盖)

### Step1 · 行业调研·发现决策点 [2026-08-31 21:40]

- 模式判定: 重构；既有 DP-09/VR-09 保留，回炉仅补全 Issue #49 暴露的 source-field interface 空白。
- 快调来源: binding spec/current code/frozen source/#48 oracle；NotebookLM `ship_maneuvering` 因认证过期不可用；补充 ITTC 与工业 QTF 文档快查。
- 新增决策点: DP-01..DP-06。
- 触发技术分解: TD-01 EnvironmentField public contract。
- 当前仅完成决策点发现；未形成 VR/ALT/TS，未写测试或实现。

### Step2-4 压缩裁决 · 用户单轮确认 [2026-09-01]

- 用户授权压缩节奏（2026-09-01）：六 DP 决策表单轮展示、单轮确认，替代 design-grounding 逐 DP 确认链；自即日起 GNC 后续设计改用 grill-with-docs 压缩模式（用户裁决，见记忆 design-skill-preference-grill-with-docs）。
- 证据补充：research subagent 编制 #49 evidence brief（issue #49/#50/#51 原文、binding spec 冻结条款 VR-21/TS-07..10/15/16/21、modular contracts/stack/configuration 现状、frozen env_engines API 签名、legacy `Disturbance`/`GaussMarkovDisturbance` 路径、#48 fixture 字段）。
- 用户确认 DP-01..06 全部采纳：VR-49-01..06 标 final；ALT-49-01..06 弃用；TS-49-01..06 落盘 0.8。
- 盲区：无阻断项；NLM 认证过期不阻塞（R1–R5 已答 Step1 空白）。legacy polar vs world-vector 歧义由 TS-49-01（adapter 转换责任）了结。
- 状态：已裁决，可派发 #49 实现（TDD seams 按 issue 验收+VR-49/TS-49）；RK stage 采样仅冻结 API，RK4 实现留 #52。
