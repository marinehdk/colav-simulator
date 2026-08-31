# AGX L4-5 水动力与 GNC 通用化集成方案包

> **状态**：用户已接受；to-spec 权威输入
> **日期**：2026-08-28
> **权威设计日志**：`docs/superpowers/design-logs/2026-08-28-agx-l45-gnc-integration-design-log.md`
> **源 baseline**：`l45-source-20260824-v2`
> **源 Manifest SHA-256**：`2c863347de59474a32d26a53d5631ed9a5b376623cd88d6fb83ca8173fc09411`
> **Evidence snapshot manifest SHA-256**：`6b33f861f65e34bb2122847e666d02c92dfac5f39877b7cb35c604e35cd5c644`
> **设计 Spec**：`2026-08-28-agx-l45-gnc-integration-design.md`
> **Issue**：https://github.com/marinehdk/colav-simulator/issues/41

## 方案包契约

本方案核心技术决策已经 design-grounding Step1–Step5 裁决。

- 可做：在已裁决范围内完成架构、数据流、错误处理、测试 seam、配置和分片实施设计。
- 不可做：把源 ROS2 package 整体照抄进主项目。
- 不可做：推翻 VR-01–VR-30，除非发现新矛盾证据并回到 design-grounding。
- 不可做：重提 ALT-01–ALT-67。
- 不可做：擅自修改本包坐标、单位、符号、时序和失败语义。
- 不可做：把 A1/A2/A3 证据升级解释为船型验证、SIL/HIL 或海试。
- 实施发现新矛盾：暂停，带证据回炉受影响 DP。

## 顶层裁决

采用方案 D：

```text
Deep Facade
+ Explicit Typed Internal Pipeline
+ Functional Tick Discipline
```

```text
Simulator
   │
   ▼
ModularShipStack
  reset()
  step()
  snapshot()
   │
   └── Deterministic Scheduler
        ├── EnvironmentField / EnvironmentalLoadModel
        ├── PathGuidance
        ├── MotionController
        ├── ThrustAllocator
        ├── ActuatorModel
        └── VesselPlant + external RK4
```

外部 interface 小；内部 module seam 明确可测。Input/output/snapshot immutable；module 可使用私有高效状态；每 tick 原子提交。

---

## 1. 术语表

| 术语 | 定义 | 本方案含义 | 不是 | 关联 |
|---|---|---|---|---|
| Module | 具有 interface 和 implementation 的可替换单元 | Env、Plant、Guidance、Controller、Allocator、Actuator | ROS node/file/package 的同义词 | DP-03 |
| Interface | 调用方正确使用 module 所需全部事实 | 类型、单位、frame、时序、错误、配置、性能 | 只有函数签名 | DP-04 |
| Seam | 可替换行为而无需修改调用处的位置 | Typed internal module interface | 任意 helper 函数 | DP-03 |
| Adapter | 在 seam 满足 interface 的具体转换角色 | Legacy NumPy、ROS2、C++/pybind | 领域算法本身 | DP-02/03 |
| Deep Facade | 小 interface 隐藏大量内部行为 | `ModularShipStack.reset/step/snapshot` | 巨型算法类 | VR-30 |
| PlantState | 完整物理真值状态 | 3DOF 或 roll-4DOF capability | COLAV 公共状态 | DP-07 |
| NavigationState | 稳定 3DOF 导航视图 | `[N,E,heading,u,v,r]` typed projection | 完整 4DOF truth | DP-07 |
| Environment Truth | 仿真真实风浪流状态 | 只供 field/load/plant | GNC 可直接读取的传感值 | DP-19 |
| Environment Estimate | Guidance/Controller 可得环境观测/估计 | 带 source/quality/age | Truth 的别名 | DP-19 |
| RHS | 连续动力学状态导数 | 无副作用 `VesselPlant.derivative()` | `x_next` 或内部 RK4 | DP-11 |
| ControlTask | 明确控制任务 | Transit/PoseHold/ControlledStop/ManualLoad | `speed=0` 隐式模式 | DP-14 |
| Direct Reference | Planner 直接给 controller reference | 旧算法兼容路径 | Route | DP-18 |
| Tracked Route | 被接受、版本化、有效期明确的 route | 经 PathGuidance 跟踪 | Predicted trajectory | DP-18 |
| Fidelity Profile | 执行器逼真度模式 | ideal generalized load / resolved actuator | acceptance level | DP-16 |
| Asset Trust | 数据资产证据等级 | mock/inferred/calibrated/validated-for-vessel | 软件 module maturity | DP-10 |
| Characterization | 冻结现有行为的可执行事实 | 用于防误译 | 自动证明设计合理 | DP-23/24 |
| Intentional Deviation | 有证据地改变源行为 | 删除特化/修正缺陷的审计记录 | 随意改 tolerance | DP-24/28 |
| Legacy Stack | 当前原项目执行链 | 默认冻结 | 待删除旧代码 | DP-29 |
| Modular Stack | 新 typed GNC 执行链 | 显式 opt-in | 自动替代 legacy | DP-29 |
| Acceptance Gate | 独立验证层 | G0–G10 | 单一 `verified=true` | DP-24 |
| Acceptance Level | 对外声明等级 | A1–A7 | Gate 的同义词 | DP-25 |

---

## 2. 技术规约表

| ID | 类别 | 规约 | 单位/定义 | 来源 | 关联 interface | 与现状差异 |
|---|---|---|---|---|---|---|
| TS-01 | 坐标 | 平面 world 使用 North-East | x=N, y=E, m | DESIGN_DECISION/VR-20 | 全部 typed state | 与当前项目一致；源归档有冲突 |
| TS-02 | 坐标 | 3D world 使用 NED | z=down | DESIGN_DECISION/VR-20 | Plant/adapter | 源归档 contract 有 y-port/z-up 冲突 |
| TS-03 | 坐标 | Body 使用 x-forward/y-starboard/z-down | body frame | DESIGN_DECISION/VR-20 | Plant/Actuator/loads | Adapter 必须 basis-probe |
| TS-04 | 符号 | Heading 0=North，顺时针/right positive | rad | DESIGN_DECISION/VR-20 | Navigation/Guidance | 禁止核心 yaw_sign |
| TS-05 | 符号 | Roll positive=starboard down；yaw rate positive=right turn | rad, rad/s | DESIGN_DECISION/VR-20 | 4DOF Plant | 需 source adapter characterization |
| TS-06 | 单位 | 核心全部 SI | m,s,kg,N,Nm,rad | [R7][R8] | 全部 module | deg/kn 仅 adapter/UI |
| TS-07 | 环境 | from/to 方向进入核心前转 world vector | m/s vector | VR-20 | Environment adapter | 禁止核心猜方向 |
| TS-08 | 时序 | 单一 simulation-time authority | integer tick | VR-05 | Scheduler | 不用 wall timer |
| TS-09 | 时序 | 固定 phase order；非到期输出 ZOH | profile-defined | VR-05/30 | Scheduler | 源异步 order 被显式化 |
| TS-10 | 时序 | Characterization 初始 profile 可用 plant/env 50Hz、controller 10Hz、guidance 2Hz | 0.02/0.1/0.5s | [R2–R5] | SchedulerProfile | 不是算法永久常数 |
| TS-11 | 数值 | Typed numeric 核心默认 float64、finite、严格 shape/layout | float64 | VR-04 | Typed values | 禁止 silent reshape/truncate |
| TS-12 | 状态 | PlantState 完整；NavigationState 3DOF 显式 projection | capability-aware | VR-07 | Facade output | Roll/p 不私藏、不污染 COLAV |
| TS-13 | 数值 | Plant 提供 pure RHS；唯一外部 fixed-step RK4 | derivative | VR-11 | VesselPlant/Scheduler | 禁止 double integration |
| TS-14 | 数值 | RK stage 不推进 PID/ILOS/NDO/RNG/actuator 离散状态 | once per due tick | VR-11 | Scheduler | Stage-time forcing 可纯计算 |
| TS-15 | 生命周期 | 每 ship/episode 独立 state；reset 幂等；snapshot/restore 绑定 hash | deterministic | VR-06/21 | ModularShipStack | 禁止跨 episode 泄漏 |
| TS-16 | 随机 | Master seed 按 ship/episode/module 派生；禁止 replay 路径 random_device | integer seed tree | VR-06 | Environment/Sensors | Ship 顺序不影响结果 |
| TS-17 | 错误 | Invalid/stale/nonfinite/out-of-domain/capability mismatch 显式失败 | structured code | VR-04/06/12 | Facade diagnostics | 禁止静默置零/fallback |
| TS-18 | Planner | DIRECT_REFERENCE 与 TRACKED_ROUTE 为互斥 capability | discriminated union | VR-18 | PlannerOutput | Predicted trajectory 非 route |
| TS-19 | Control | Transit/PoseHold/ControlledStop/ManualLoad 显式 task | typed task | VR-14 | Controller | speed=0 不推断 DP |
| TS-20 | PID | Measurement derivative、dt-aware filter、单 tracking anti-windup、achieved_tau feedback | discrete-time | VR-15 | marine_pid | 不复制多层历史规则 |
| TS-21 | 补偿 | Plant 用 truth；GNC 用 observation/estimate；显式补偿默认互斥 | source/age/quality | VR-19 | Env/Guidance/Control | 禁止 truth leakage/重复补偿 |
| TS-22 | Actuator | ideal/resolved 双 profile；layout/curve/rate 为资产；dynamics 单一所有者 | profile + assets | VR-16 | Allocator/Actuator | 禁止固定七执行器数组 |
| TS-23 | Asset | 四级 trust；必须 provenance/hash/license/domain；缺失/超域失败 | metadata | VR-10 | Registry/Report | Mock 不得显示 validated |
| TS-24 | 配置 | Legacy YAML 不变；新 `ship_modules` opt-in；defaults<preset<scenario override | normalized hash | VR-26/29 | Registry | 首期无 runtime hot update |
| TS-25 | 兼容 | 未选 modular stack 时不 import/check/execute 新路径 | strict isolation | VR-29 | Composition root | 无自动迁移 |
| TS-26 | 性能 | 不丢 tick、不动态改 dt；profile 后向量化/cache/并行/native | RTF/latency | VR-27 | Scheduler/backend | Native 非默认依赖 |
| TS-27 | 证据 | Source/config/test/asset/compiler/seed 绑定 content hash | SHA-256 | VR-23/24 | Fixture/report | 禁止跨版混用 |
| TS-28 | 接受 | G0–G10 独立 gate；逐量 abs+rel tolerance；intentional deviation | per quantity | VR-24 | Verification | 不用单一 smoke |
| TS-29 | 声明 | A1–A7 分级；首阶段仅 A1–A3 | declared level | VR-25 | Report/UI | 不把软件 pass 升级船型验证 |
| TS-30 | 通用性 | 每 behavior 五分类、证据卡、消融、跨船型门 | evidence card | VR-28 | Design/acceptance | 参数化补丁不算通用 |

---

## 3. 决策卡片集

### 方案 A：Explicit Typed Pipeline

| 维度 | 结论 |
|---|---|
| 来源 | [R7][R16][R19] |
| 工程验证 | Pure kernels 有局部验证；完整 pipeline 新建 |
| 技术分解 | TD-01–TD-05 全覆盖 |
| 失效边界 | 外部调用面过大，易错组装 |
| 实现风险 | 高 |
| 可测性 | 高 |
| 推荐度 | 4/5；仅采纳为内部 composition |

### 方案 B：Deep ShipStack Facade

| 维度 | 结论 |
|---|---|
| 来源 | [R7][R19] |
| 工程验证 | 当前 Ship 证明 facade 使用自然；新 facade 未实现 |
| 技术分解 | TD-01–TD-05 全覆盖 |
| 失效边界 | 无 private seams 会形成新巨型类 |
| 实现风险 | 高 |
| 可测性 | 中高 |
| 推荐度 | 4/5；仅采纳为外部 interface |

### 方案 C：Functional State Transition

| 维度 | 结论 |
|---|---|
| 来源 | [R14][R16][R17][R21] |
| 工程验证 | Pure property tests 有基础；完整 immutable stack 新建 |
| 技术分解 | TD-01–TD-05 全覆盖 |
| 失效边界 | NumPy copy、schema、legacy mutable adapter 成本高 |
| 实现风险 | 很高 |
| 可测性 | 最高 |
| 推荐度 | 3/5；只采纳 state discipline |

### 方案 D：综合方案（采纳）

| 维度 | 结论 |
|---|---|
| 来源 | [R7][R14][R16][R19][R21]，综合 A/B/C |
| 工程验证 | 延续 Ship 调用形态；复用 pure kernel/fixture；整体新建 |
| 技术分解 | TD-01–TD-05 全覆盖，外/内 interface 分层 |
| 失效边界 | Facade 不得含算法；scheduler 不读 module 私有状态；module 必须 snapshot/diagnostics |
| 实现风险 | 中高 |
| 可测性 | 高：facade/module/phase/stage/replay 分层 |
| 推荐度 | 5/5 |

裁决：VR-30。纯 A/B/C 分别进入 ALT-65/66/67。

---

## 4. 证据矩阵

| ID | 来源 | 检索置信 | 来源权威 | 场景适用 | 用途 |
|---|---|---|---|---|---|
| [R1] | Source-only README/manifest/stats/verification | 高 | 高 | 高 | 源范围/完整性 |
| [R2] | ship_control C++/YAML | 高 | 高 | 高 | Controller 现状 |
| [R3] | ship_dynamics C++/YAML | 高 | 高 | 高 | 4DOF/积分/guard |
| [R4] | env_engines source/assets | 高 | 高 | 高 | 环境模型/资产 |
| [R5] | ship_guidance source/YAML | 高 | 高 | 高 | Guidance 复杂度 |
| [R6] | thrust_allocation source/YAML | 高 | 高 | 高 | Allocator/actuator |
| [R7] | Colav-Simulator current interfaces | 高 | 高 | 高 | Legacy seam |
| [R8] | ROS2/pybind/FMI/MSS/PVS 行业调研 | 高 | 高 | 高 | 运行架构 |
| [R9] | package.xml license declarations | 高 | 中 | 高 | 许可元数据 |
| [R10] | 用户批判性重构主旨 | 高 | 高 | 高 | 通用性 |
| [R11] | 用户 legacy 兼容/可选模块要求 | 高 | 高 | 高 | 兼容发布 |
| [R12] | 用户完整修改开发权限 | 高 | 高 | 高 | 授权 |
| [R13] | 用户 AGX evidence 搜集授权 | 高 | 高 | 高 | Step3 evidence |
| [R14] | Evidence snapshot/hash | 高 | 高 | 高 | Evidence identity |
| [R15] | Current-vs-v2 25 changed/1 missing | 高 | 高 | 高 | Version conflict |
| [R16] | Recovered core tests | 高 | 高 | 软件高/船型低 | Kernel fixtures |
| [R17] | Archived hydrodynamics V&V contract | 高 | 中 | 中 | Evidence levels/conflicts |
| [R18] | PID/H34/H39/H40/H70/D30/current campaigns | 高 | 中 | 中 | Trade-off/tuning history |
| [R19] | C/C++ quality audit | 高 | 中 | 中 | 巨型函数/测试历史 |
| [R20] | 220 campaign inventory | 高 | 高 | 高（复杂度来源） | Tuning concentration |
| [R21] | AGX evidence audit | 高 | 中高 | 高 | BL-02/BL-08 synthesis |
| [R22] | 用户 Step4 批量授权 | 高 | 高 | 流程 | 批量裁决记录 |

Evidence limitations：

- Current tests 与 source-only v2 不同版。
- Archived contract 与 v2 source/config hash 不完全一致。
- 真实 RAO/QTF、目标船 CFD/tank/sea-trial 缺失。
- Controller/Guidance 完整内部状态 oracle 尚需新建。

---

## 5. 技术分解完整树

| TD | 子模块 | 对应裁决 | 就绪 |
|---|---|---|---|
| TD-01 集成架构 | facade、typed seam、scheduler、lifecycle、registry、multi-ship、platform、legacy | VR-01–07、21、26–30 | 已裁决 |
| TD-02 水动力/环境 | PlantState、M/C/D/restoring、env split、assets、RK4、validity、compensation | VR-07–12、19–20、23–25、28 | 已裁决 |
| TD-03 控制/执行器 | controller identity、task、PID semantics、allocator、actuator fidelity、compensation | VR-13–16、19–20、24–28 | 已裁决 |
| TD-04 Guidance/COLAV | LOS/ILOS、route capability、handoff、terminal/env、authority | VR-17–20、24–30 | 已裁决 |
| TD-05 验证/发布 | oracle、G0–G10、A1–A7、config hash、generality、legacy release | VR-23–30 | 已裁决 |

`DECOMPOSITION_INCOMPLETE`：无。

---

## 6. 弃用方案及理由

详细逐项记录见设计日志 ALT-01–ALT-67。分组如下：

| ALT | 类别 | 主要弃用理由 |
|---|---|---|
| ALT-01–04 | 实施范围 | 全量迁移/多模块同时重写/Guidance-first/空 scaffold 均破坏归因或价值 |
| ALT-05–08 | 运行形态 | pybind-only、ROS-first、FMI-first、双产品实现首期成本过高 |
| ALT-09–12 | Seam | 单体 stack、per-file adapter、公开 helper、ROS core 均不是深 module |
| ALT-13–20 | Interface/time/state | 裸数组、万能 state、单 rate、wall timer、弱 reset、silent stale、全 8-state、隐藏 roll |
| ALT-21–26 | Plant/env/assets | 45m 伪 Generic、flags、total wrench、silent fallback、schema=validated、外推 |
| ALT-27–30 | Integrator/guard | double integration、stage side effect、clip/reset、无 monitor |
| ALT-31–36 | Controller/task/PID | 复合 PID、flags、零速 DP、万能 controller、多 anti-windup、fixed alpha/NaN zero |
| ALT-37–40 | Actuator/Guidance | ideal-only、FCB allocator、全量 Guidance、advanced_los monolith |
| ALT-41–48 | Planner/compensation/coords/multiship | predicted route、双 authority、truth leakage、全补偿、sign flags、猜 frame、singleton/global RNG |
| ALT-49–54 | Rights/oracle/verification | 缺 notice、全入 wheel、跨版 tests、轨迹 parity、单 smoke、宽容差 |
| ALT-55–64 | Acceptance/registry/performance/generality/compat | 单 verified、A1 冒充验证、巨 YAML、插件市场、native-first、丢 tick、参数化补丁、全删行为、默认替换、先改 legacy |
| ALT-65 | 纯 A | 外部 interface 太大 |
| ALT-66 | 纯 B | 无内部 seams 会巨型化 |
| ALT-67 | 纯 C | 全 immutable 成本过高 |

---

## 7. 需求场景与验收边界

| ID | 场景 | 验收边界 | 主要 gates |
|---|---|---|---|
| SC-01 | 两组不同船型 preset 使用同一 implementation | 无船型/场景分支；参数/asset 明确；两组 contract 通过 | G2/G7 |
| SC-02 | Source C++→Python kernel 迁移 | source/config/test hash 一致；逐项/state/stage parity；intentional deviations 另记 | G0/G3/G4 |
| SC-03 | Reset/snapshot/replay | 新实例、reset、restore 逐 tick 等价；相同 seed deterministic | G1/G3 |
| SC-04 | Legacy 配置未 opt-in | 原 identity、执行链、结果、错误语义不变；不加载新依赖 | G6 |
| SC-05 | 风/流/一阶浪/漂移分项 | 单源隔离；总和；current 去重；wave dt/2；缺资产失败 | G2/G5 |
| SC-06 | PID saturation/transition | P/I/D/FF trace；saturation-release；achieved anti-windup；task handoff bumpless | G3/G5/G9 |
| SC-07 | Guidance route lifecycle | direct/route 互斥；revision/expiry/handoff/rejoin；无 predicted-route 自动转换 | G5/G8 |
| SC-08 | 多船 mixed stack | ship order/parallel serial 等价；old/new ship 同进程；state/seed 隔离 | G6/G7/G8 |
| SC-09 | ROS2 adapter failure | QoS mismatch、stale/out-of-order、进程退出、reset；kernel state 不被 wall clock 推进 | G10 |

### G0–G10

| Gate | 含义 |
|---|---|
| G0 | Source integrity |
| G1 | Interface/contract |
| G2 | Physics kernel |
| G3 | Migration parity |
| G4 | Intentional redesign/deviation |
| G5 | Module closed loop |
| G6 | Existing regression |
| G7 | Cross-vessel generality |
| G8 | COLAV integration |
| G9 | Actuator fidelity |
| G10 | ROS2/SIL |

### A1–A7

| Level | 允许声明 |
|---|---|
| A1 | Engineering Debug |
| A2 | Migration Verified |
| A3 | Generalized Simulation |
| A4 | COLAV Closed Loop |
| A5 | Vessel Calibrated |
| A6 | ROS2/SIL/HIL |
| A7 | Sea-Trial Evidence |

首阶段目标：A1→A2→A3。任何未执行 gate 必须在报告列出。

---

## 8. 已知冲突与未闭环外部数据

### 已知冲突

1. Current formal source vs source-only v2：183 checked，25 changed，1 missing。
2. Archived V&V contract vs v2：source/config hash 不完全一致。
3. Coordinate convention：归档 y-port/z-up/yaw CCW；当前描述多处 y-starboard/z-down/right-positive。
4. Report title/selection vs machine status：存在 baseline/完整航线标题但 FAIL/NOT_PROMOTED。
5. Quality audit 221 tests pass 不能当作 v2 acceptance proof。

### 不阻塞 A1–A3 的外部数据缺口

- 真实 RAO/QTF。
- 目标船 CFD/tank/manoeuvring/sea-trial 数据。
- 实际 actuator curve、rate、delay、effectiveness、failure data。
- 实际环境 sensor/estimator 可用字段、误差和更新率。
- 目标多船规模与 real-time factor 门槛。

处理：缺失时 capability/acceptance level 降低或显式失败；禁止用 mock/inferred 冒充验证。

---

## 实施顺序（供 to-spec 综合，不是本轮实现）

```text
1. Legacy regression baseline
2. Typed values + facade + registry + scheduler contract
3. EnvironmentField/LoadModel
4. Generic 3DOF/4DOF Plant + external RK4
5. marine_pid
6. Clean ILOS
7. Actuator-resolved allocator/model
8. COLAV tracked-route seam
9. ROS2 adapter
```

每片：TDD vertical slice → relevant G gates → Standards/Spec review → selective commit。不能跨片宣称后续 acceptance。
