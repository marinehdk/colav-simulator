# 设计日志: AGX L4-5 水动力与 GNC 集成

> **模式**: 重构        **创建**: 2026-08-28
> **关联 spec**: —
> **状态**: 已交付 to-spec

> **设计主旨（用户确认）**: 本任务不是照抄或完整复现 L4-5。外部源码是证据源与候选技术库；目标是识别不合理、过度约束、船型/场景特化和重复补偿，提炼成 Colav-Simulator 原生、参数化、可替换、可验证的通用 module。源行为 parity 只作为诊断手段，不自动成为产品需求。

## 0. 决策树状态(权威索引 · 可变快照)

### 0.1 决策点注册表 [DP]

| ID | 描述 | 类型 | 父/分解 | 状态 | 详见 |
|----|------|------|---------|------|------|
| DP-01 | 审计范围与首批重构范围：完整审计 env/plant/control/allocation/guidance 交互，但只实现通过通用性门的最小能力切片 | 架构 | — | 已裁决 | VR-01 |
| DP-02 | 运行架构：Colav-native 接口优先；Python 默认通用实现，C++ kernel/ROS2 为可选 adapter，FMI 延后 | 技术 | TD-01 | 已裁决 | VR-02 |
| DP-03 | 按计算职责提取 EnvironmentalLoadModel/VesselPlant/MotionController/ThrustAllocator/PathGuidance；先 characterization parity，再记录有意泛化偏差 | 架构 | TD-01 | 已裁决 | VR-03 |
| DP-04 | Kernel 使用 typed value interface；现有 NumPy 6/3/9 契约由 adapter 转换；严格 capability/shape/unit/frame/error/diagnostics | 接口 | TD-01 | 已裁决 | VR-04 |
| DP-05 | 单一 simulation-time authority；确定性多速率 scheduler、整数 tick、固定 phase order、plant substep | 架构 | TD-01 | 已裁决 | VR-05 |
| DP-06 | 每 ship/episode 独立实例；显式幂等 reset、snapshot/restore、master-seed 派生、tick freshness 和结构化 failure | 接口 | TD-01 | 已裁决 | VR-06 |
| DP-07 | capability-aware 完整 PlantState + 稳定 3DOF NavigationState 显式投影；不立即改变现有 6 元数组 | 接口 | TD-02 | 已裁决 | VR-07 |
| DP-08 | 保留旧模型；新增通用 Maneuvering3DOF/ManeuveringRoll4DOF option，以 M/C/D/restoring 结构、capability 和物理不变量门约束 | 算法 | TD-02 | 已裁决 | VR-08 |
| DP-09 | EnvironmentSample 与 EnvironmentalLoadModel 分离；风/流/一阶浪/漂移分项保真，wave mode 显式，禁止静默降级 | 架构 | TD-02 | 已裁决 | VR-09 |
| DP-10 | 代码—资产分离；mock/inferred/calibrated/validated_for_vessel 四级，带 provenance/适用域/hash/license，禁止伪验证和静默外推 | 约束 | TD-02 | 已裁决 | VR-10 |
| DP-11 | 新 plant 提供纯 RHS；唯一外部固定步长 RK4；离散 controller/guidance/actuator/RNG 状态与连续 RK stages 严格分离 | 架构 | TD-02 | 已裁决 | VR-11 |
| DP-12 | 新 plant 不静默 clip/reset；actuator 物理约束留在 actuator，适用域/数值健康由外部 monitor 检查，默认 fail-fast | 约束 | TD-02 | 已裁决 | VR-12 |
| DP-13 | 控制身份拆分：先新增纯 marine_pid；NDO/SMC/gain scheduling 独立为有证据的 option/policy；源复合 loop 不作为默认产品身份 | 算法 | TD-03 | 已裁决 | VR-13 |
| DP-14 | 显式 ControlTask；Transit/PoseHold/ControlledStop/ManualLoad 分离，capability 配置门和 bumpless transition | 算法 | TD-03 | 已裁决 | VR-14 |
| DP-15 | `marine_pid` 单一可解释更新链：derivative-on-measurement、dt-aware filter、tracking anti-windup、achieved-output feedback、分项 trace | 算法 | TD-03 | 已裁决 | VR-15 |
| DP-16 | ideal_generalized_load 与 resolved_actuator 双 fidelity profile；数据驱动 ActuatorLayout；allocator 返回 achieved_tau/residual/saturation | 架构 | TD-03 | 已裁决 | VR-16 |
| DP-17 | 保留现有 LOS/KTP；新增干净 ILOS option；RouteGeometry/SpeedProfile/TerminalTask 拆分，源巨型 Guidance 仅作候选证据 | 算法 | TD-04 | 已裁决 | VR-17 |
| DP-18 | PlannerOutput capability：现有 DIRECT_REFERENCE 与新 TRACKED_ROUTE→Guidance 两条显式互斥路径；predicted trajectory 不等于 accepted route | 接口 | TD-04 | 已裁决 | VR-18 |
| DP-19 | Plant 使用 environment truth；GNC 只消费 observation/estimate；显式补偿 option 默认互斥，多频带组合需频带/去重/消融证据 | 架构 | TD-02/TD-03/TD-04 | 已裁决 | VR-19 |
| DP-20 | 核心统一 canonical NE/NED、body x-forward/y-starboard/z-down、heading/yaw/roll 右向正、SI；sign/frame/from-to 仅 adapter 转换 | 接口 | TD-01/TD-02/TD-03/TD-04 | 已裁决 | VR-20 |
| DP-21 | Plant/Controller/Guidance/Allocator/observer per-ship；共享 pure EnvironmentField/immutable assets；支持混合旧新模块与顺序无关 replay | 架构 | TD-01 | 已裁决 | VR-21 |
| DP-22 | 用户作为权利方确认拥有全部权限，可直接修改、开发和优化；实施仍需统一 LICENSE/NOTICE/provenance | 约束 | — | 已裁决 | VR-22 |
| DP-23 | 以 Manifest SHA 冻结 baseline；授权从 AGX 父目录选择性恢复 tests/validation/trace 到仓库外 evidence snapshot，建立 content-addressed fixtures | 约束 | TD-05 | 已裁决 | VR-23 |
| DP-24 | G0–G10 分层 gates：source/interface/physics/parity/redesign/closed-loop/legacy/generalization/COLAV/actuator/ROS2；intentional-deviation ledger | 技术 | TD-05 | 已裁决 | VR-24 |
| DP-25 | A1 Engineering Debug→A7 Sea-Trial 分级声明；首阶段只目标 A1–A3，水动力/Guidance/Control/actuator/COLAV/system 分开报告 | 约束 | TD-05 | 已裁决 | VR-25 |
| DP-26 | 旧 YAML/Builder 不变；新 registry/schema opt-in，module/preset/asset 分离，capability tuple 先验校验，normalized config snapshot+hash | 接口 | TD-01/TD-05 | 已裁决 | VR-26 |
| DP-27 | Python-first/profile-first；正确性→向量化/cache/并行→证据后 C++ adapter；不丢 tick/改 dt，native 为 optional extra | 约束 | TD-01 | 已裁决 | VR-27 |
| DP-28 | 每项源行为建立证据卡并分类 DomainInvariant/VesselParameter/RuntimeAdapter/ExperimentalCandidate/Reject；跨船型消融后准入 | 约束 | TD-01/TD-02/TD-03/TD-04/TD-05 | 已裁决 | VR-28 |
| DP-29 | legacy_gnc_stack 默认冻结；modular_gnc_stack 显式 opt-in；无自动迁移，以小切片逐 option 发布 | 架构 | TD-01/TD-05 | 已裁决 | VR-29 |

### 0.2 技术分解注册表 [TD]

| ID | 技术 | 分解子模块(→DP) | 触发步骤 |
|----|------|------------------|----------|
| TD-01 | ROS2/C++→Colav-Simulator 集成架构 | 范围(DP-01)、运行形态(DP-02)、kernel seam(DP-03)、调用接口(DP-04)、调度(DP-05)、生命周期(DP-06)、符号规约(DP-20)、多实例(DP-21)、配置(DP-26)、平台(DP-27)、通用性门(DP-28)、兼容发布(DP-29) | Step1/Step2 |
| TD-02 | 4DOF 水动力与环境载荷 | 状态/DOF(DP-07)、动力学项(DP-08)、环境 seam(DP-09)、资产可信度(DP-10)、积分器(DP-11)、保护逻辑(DP-12)、环境补偿去重(DP-19)、符号规约(DP-20)、通用性门(DP-28) | Step1/Step2 |
| TD-03 | PID/SMC/NDO 与执行器控制链 | 控制器身份(DP-13)、模式状态机(DP-14)、离散状态/限幅(DP-15)、推力分配/actuator(DP-16)、环境补偿(DP-19)、符号规约(DP-20)、通用性门(DP-28) | Step1/Step2 |
| TD-04 | ILOS/ALOS 导引和避碰航线接入 | 导引身份(DP-17)、COLAV-route seam(DP-18)、环境补偿(DP-19)、符号规约(DP-20)、通用性门(DP-28) | Step1/Step2 |
| TD-05 | 跨语言/跨运行时验证 | 源/oracle(DP-23)、验证架构(DP-24)、接受等级(DP-25)、参数版本(DP-26)、通用性门(DP-28)、兼容发布(DP-29) | Step1/Step2 |

### 0.3 盲区注册表 [BL]

| ID | 问题 | 归属决策点 | 优先级 | 调研状态 |
|----|------|-----------|--------|----------|
| BL-01 | 同事/组织是否授权把 TODO/Proprietary 未明确许可源码转写或链接到 MIT 项目 | DP-22 | 高 | 已闭环→[R12] |
| BL-02 | 被排除的 tests、validation、原始运行证据是否允许提供 | DP-23/DP-24 | 高 | 已闭环→[R14][R15][R16][R17][R18][R21] |
| BL-03 | 源目录没有 Git 元数据；2026-08-24 导出对应哪个开发版本/变更集 | DP-23 | 高 | 已闭环→Manifest baseline |
| BL-04 | 用户首批真正想调试的范围：plant+controller，还是连同 guidance/allocator/env engines | DP-01 | 高 | 已闭环→完整审计+通用性门后最小切片 |
| BL-05 | 目标是本地算法调试、复现同事系统行为，还是获得可信船型水动力结论 | DP-25 | 高 | 已闭环→首阶段 A1–A3 |
| BL-06 | 最终部署是否必须继续支持 ROS2 Humble/AGX，还是只需 Colav-Simulator Python runtime | DP-02/DP-27 | 中 | 已闭环→Python 默认+ROS2 外围 adapter |
| BL-07 | 4DOF 的 roll 是否必须成为评价/可视化公共状态，还是只做 plant 内部状态 | DP-07 | 高 | 已闭环→PlantState truth+NavigationState projection |
| BL-08 | 哪些门限/状态机/补偿有船型或实验依据，哪些只是历史场景修补；当前 source-only 包缺测试和设计记录 | DP-28 | 高 | 已闭环→[R16][R17][R18][R19][R20][R21] |

### 0.4 证据矩阵 [EV]

| ID | 来源类型 | 引用 | 检索置信 | 来源权威 | 场景适用 | 归属 |
|----|----------|------|----------|----------|----------|------|
| [R1] | PROJECT_FACT | AGX source-only README/manifest/stats/verification | 高 | 高 | 高 | DP-01/DP-23/DP-25/DP-27 |
| [R2] | PROJECT_FACT | ship_control C++/header/YAML | 高 | 高 | 高 | DP-03/DP-05/DP-06/DP-13/DP-14/DP-15/DP-19/DP-20/DP-21/DP-26 |
| [R3] | PROJECT_FACT | ship_dynamics C++/header/YAML | 高 | 高 | 高 | DP-03/DP-05/DP-07/DP-08/DP-11/DP-12/DP-16/DP-20/DP-21/DP-26 |
| [R4] | PROJECT_FACT | env_engines pure models/nodes/assets/launch | 高 | 高 | 高 | DP-03/DP-05/DP-09/DP-10/DP-19/DP-20/DP-21/DP-25/DP-26 |
| [R5] | PROJECT_FACT | ship_guidance C++/header/YAML | 高 | 高 | 高 | DP-01/DP-03/DP-05/DP-17/DP-18/DP-19/DP-20/DP-21/DP-26 |
| [R6] | PROJECT_FACT | thrust_allocation C++/policies/YAML | 高 | 高 | 高 | DP-01/DP-03/DP-16 |
| [R7] | PROJECT_FACT | Colav-Simulator IModel/IController/IGuidance/Ship/Simulator | 高 | 高 | 高 | DP-04/DP-06/DP-07/DP-17/DP-18/DP-20/DP-21/DP-26 |
| [R8] | DOMAIN_EVIDENCE | ROS2/C++ GNC port industry research | 高 | 高 | 高 | DP-02/DP-03/DP-04/DP-05/DP-06/DP-07/DP-08/DP-09/DP-11/DP-13/DP-17/DP-20/DP-24/DP-25/DP-27 |
| [R9] | PROJECT_FACT | 13 package.xml license declarations; no LICENSE/NOTICE files | 高 | 中 | 高 | DP-22 |
| [R10] | DOCUMENTED_INTENT | 用户明确要求批判性重构、识别不合理和过度特化，禁止把照抄当目标 | 高 | 高 | 高 | DP-01/DP-28 |
| [R11] | DOCUMENTED_INTENT | 用户要求保证原项目模块正常执行；新水动力/导引/控制像现有算法一样提供不同可选项并渐进提升 | 高 | 高 | 高 | DP-07/DP-26/DP-29 |
| [R12] | DOCUMENTED_INTENT | 用户确认对 AGX L4-5 代码拥有全部权限，可直接修改、开发和优化 | 高 | 高 | 高 | DP-22/DP-23 |
| [R13] | DOCUMENTED_INTENT | 用户授权通过 `ssh agx` 在目标目录及 `/home/mass/sango/` 父目录搜集 tests/validation/evidence | 高 | 高 | 高 | DP-23/DP-24 |
| [R14] | PROJECT_FACT | Evidence snapshot scope/rsync/hash manifest | 高 | 高 | 高 | BL-02/DP-23/DP-24 |
| [R15] | PROJECT_FACT | Current formal vs source-only v2: 183 checked, 25 changed, 1 missing | 高 | 高 | 高 | BL-02/BL-03/DP-23 |
| [R16] | PROJECT_FACT | Recovered env/dynamics/control/guidance/allocator core tests | 高 | 高 | 高(software)/低(vessel fidelity) | BL-02/BL-08/DP-24/DP-28 |
| [R17] | PROJECT_FACT | Archived hydrodynamics V&V contract and open-loop tests | 高 | 中 | 中(hash/convention drift) | BL-02/BL-08/DP-08/DP-20/DP-25 |
| [R18] | PROJECT_FACT | PID handoff and selected H34/H39/H40/H70/D30/current campaigns | 高 | 中 | 中(45m/H24) | BL-02/BL-08/DP-13/DP-17/DP-19/DP-28 |
| [R19] | PROJECT_FACT | 2026-08-24 C/C++ quality audit | 高 | 中 | 中(current formal) | BL-02/BL-08/DP-03/DP-28 |
| [R20] | PROJECT_FACT | Validation campaign inventory: 220 total, 133 ilos-prefix, 13 pid-name, 55 H-series | 高 | 高 | 高(complexity history) | BL-08/DP-28 |
| [R21] | RESEARCH_SYNTHESIS | AGX evidence audit, based only on recovered first-party artifacts | 高 | 中高 | 高 | BL-02/BL-08/DP-23/DP-24/DP-28 |
| [R22] | DOCUMENTED_INTENT | 用户显式要求 Step4 批量展示剩余 DP，避免逐项进度过慢 | 高 | 高 | 高 | Step4 process |

### 0.5 场景注册表 [SC]

| ID | 场景描述 | 约束/边界 | 驱动决策点 |
|----|----------|-----------|-----------|
| SC-01 | 同一套 module 实现用于至少两组不同船型参数和多类场景，不出现船型名/场景名分支 | 船型差异通过参数/能力声明表达；行为门限必须有来源和适用域 | DP-01/DP-25/DP-26/DP-28 |
| SC-02 | 从冻结 C++ 快照迁移到可调试 Python 默认实现 | 每个 kernel 有相同输入、参数、内部状态 trace 和差分测试；先证明一致，再逐项泛化并记录有意偏差 | DP-02/DP-03/DP-23/DP-24 |
| SC-03 | 同一 episode 初态/输入/seed 重放以及 reset 后重复运行 | 两次逐 tick trace 一致；新建实例与 reset 后实例等价；无上一 episode 状态泄漏 | DP-05/DP-06/DP-24 |
| SC-04 | 同一旧场景/配置在未选择新模块时运行 | 旧 model/guidance/controller 身份、参数、轨迹和验收结果不变；新模块仅 opt-in，不允许缺依赖后回退冒充 | DP-26/DP-29 |
| SC-05 | 风/流/一阶浪/漂移分项验证 | 单源隔离、总和、current 去重、wave dt/2、缺资产失败 | DP-09/10/11/24 |
| SC-06 | PID saturation 与 ControlTask transition | P/I/D/FF trace、saturation-release、achieved anti-windup、bumpless handoff | DP-14/15/16/24 |
| SC-07 | Planner route lifecycle | direct/route 互斥、revision/expiry/handoff/rejoin、无 predicted-route 自动转换 | DP-17/18/24 |
| SC-08 | 多船 mixed legacy/modular stack | ship-order/parallel-serial 等价，state/seed 隔离，old/new 同进程 | DP-21/24/29 |
| SC-09 | ROS2 adapter failure | QoS、stale/out-of-order、进程退出、reset；wall clock 不推进 kernel | DP-02/05/24/27 |

### 0.6 裁决注册表 [VR]

| ID | 裁决对象 | 结论 | 采纳/弃用 | 理由 | 时间 |
|----|----------|------|-----------|------|------|
| VR-01 | DP-01 | 完整审计；typed contracts/scheduler/registry→env+plant→marine_pid→ILOS→actuator→route→ROS 分片实施 | 采纳 | [R15][R16][R17][R18][R19][R20][R21]；证据强度由 plant/env 到 guidance 递减 | Step4 |
| VR-02 | DP-02 | Python 默认产品实现；C++ 作为 characterization oracle/证据后可选 pybind；ROS2 外围 adapter；FMI 延后 | 采纳 | [R8][R15][R16][R19]；接口/fixture 控制数值漂移，避免固化 ROS/ABI | Step4 |
| VR-03 | DP-03 | 6 个深 module；ROS/YAML/legacy arrays 留 adapter；逐职责提取，不按 package/file 搬迁 | 采纳 | [R7][R15][R16][R19] | Step4 |
| VR-04 | DP-04 | Typed kernel values；legacy NumPy 仅 adapter；严格 capability/shape/unit/frame/version | 采纳 | [R7][R15][R17] | Step4 |
| VR-05 | DP-05 | 单一仿真时钟、整数 tick、固定 phase order、ZOH、plant substep | 采纳 | [R2][R3][R4][R5] | Step4 |
| VR-06 | DP-06 | Per-ship/episode state；幂等 reset、snapshot/restore、派生 seed、显式 stale/failure | 采纳 | [R16][R18] | Step4 |
| VR-07 | DP-07 | Full PlantState + stable 3DOF NavigationState 显式投影 | 采纳 | [R7][R17] | Step4 |
| VR-08 | DP-08 | 旧模型保留；新增通用 3DOF/4DOF plant；物理不变量门 | 采纳 | [R16][R17] | Step4 |
| VR-09 | DP-09 | 环境数据/载荷分离；wind/current/wave 分项；wave mode 显式；current 去重 | 采纳 | [R4][R16][R17] | Step4 |
| VR-10 | DP-10 | 四级 asset trust、provenance/domain/hash/license；缺资产/超域显式失败 | 采纳 | [R4][R16][R17] | Step4 |
| VR-11 | DP-11 | 纯 RHS、唯一外部 RK4、离散状态与 RK stage 严格分离 | 采纳 | [R3][R7][R17] | Step4 |
| VR-12 | DP-12 | Plant 不静默 clip/reset；外置 validity monitor，默认 fail-fast | 采纳 | [R3][R17] | Step4 |
| VR-13 | DP-13 | 新纯 marine_pid；NDO/SMC/scheduling 独立 option；源复合 loop 仅证据 | 采纳 | [R2][R16][R18][R20] | Step4 |
| VR-14 | DP-14 | 显式 ControlTask、capability gate、独立 Transit/PoseHold 和 bumpless transition | 采纳 | [R2][R18] | Step4 |
| VR-15 | DP-15 | Measurement derivative、dt-aware filter、单一 tracking anti-windup、achieved_tau feedback | 采纳 | [R2][R16] | Step4 |
| VR-16 | DP-16 | ideal/resolved 双 fidelity；data-driven layout；achieved/residual feedback | 采纳 | [R6][R16][R18] | Step4 |
| VR-17 | DP-17 | 保留旧 LOS/KTP；新增干净 ILOS；route/speed/terminal/env 拆分 | 采纳 | [R5][R18][R19][R20] | Step4 |
| VR-18 | DP-18 | PlannerOutput DIRECT_REFERENCE/TRACKED_ROUTE 双 capability，显式互斥 | 采纳 | [R5][R7][R18] | Step4 |
| VR-19 | DP-19 | Plant truth；GNC observation/estimate；补偿默认互斥、证据后组合 | 采纳 | [R18] | Step4 |
| VR-20 | DP-20 | Canonical NE/NED/right-positive/SI；转换只在 adapter；basis probe | 采纳 | [R15][R17][R21] | Step4 |
| VR-21 | DP-21 | Per-ship stack；shared pure environment/immutable assets；mixed legacy/new | 采纳 | [R2][R3][R4][R5][R7] | Step4 |
| VR-22 | DP-22 | 授权闭环；正式迁入补齐 LICENSE/NOTICE/provenance，资产另审 | 采纳 | [R9][R12] | Step4 |
| VR-23 | DP-23 | v2 manifest baseline；evidence 单独 hash；禁止跨版本测试混用；补建 harness | 采纳 | [R14][R15][R17][R21] | Step4 |
| VR-24 | DP-24 | G0–G10 独立 gates；逐量容差；intentional-deviation ledger | 采纳 | [R16][R17][R18][R19][R20][R21] | Step4 |
| VR-25 | DP-25 | A1–A7 分级声明；首阶段 A1–A3；各证据层分报 | 采纳 | [R17][R18] | Step4 |
| VR-26 | DP-26 | 旧配置冻结；新 registry opt-in；module/preset/asset 分离；capability tuple/config hash | 采纳 | [R2][R3][R4][R5][R7][R19] | Step4 |
| VR-27 | DP-27 | Python-first/profile-first；证据后 native；不牺牲确定性 | 采纳 | [R8][R16] | Step4 |
| VR-28 | DP-28 | 逐 behavior 证据卡、五分类、跨船型消融与 deviation ledger | 采纳 | [R18][R19][R20][R21] | Step4 |
| VR-29 | DP-29 | legacy 默认冻结；modular opt-in；无自动迁移；小切片发布 | 采纳 | [R7][R11] | Step4 |
| VR-30 | TD-01..TD-05 整体架构 | 方案 D：Deep Facade 外部 interface + Explicit Typed Internal Pipeline + Functional Tick Discipline | 采纳 | 结合 A/B/C 完整方案；在 depth、归因、效率、replay 间最平衡 | Step5 |

### 0.7 备选/弃用方案 [ALT]

| ID | 方案 | 弃用理由 | 对比于 |
|----|------|----------|--------|
| ALT-01 | 一次迁入 13 个 ROS2 package | 固化 ROS、历史门限和异步时序，差异不可归因 | DP-01 |
| ALT-02 | Plant+PID+ILOS 同时重写 | Controller/Guidance 缺完整 oracle，失败归因混杂 | DP-01 |
| ALT-03 | Guidance 优先 | 复杂度和 historical tuning 最高，NOT_PROMOTED/FAIL 证据多 | DP-01 |
| ALT-04 | 只搭接口不落物理 kernel | 形成浅 scaffold，无法产生数值证据 | DP-01 |
| ALT-05 | pybind 作为唯一主实现 | 固化源偶然复杂度；ABI/GIL/调试成本高 | DP-02 |
| ALT-06 | ROS2 bridge 作为第一数值路径 | 异步/QoS/wall timer 破坏确定性与归因 | DP-02 |
| ALT-07 | FMI/FMU 优先 | 无当前跨工具硬需求；solver/lifecycle 黑盒成本高 | DP-02 |
| ALT-08 | Python/C++ 两套产品实现同时开发 | 首期维护/parity 成本翻倍 | DP-02 |
| ALT-09 | 单一 `L45GncStack.step()` | 错误不可归因，隐藏历史耦合 | DP-03 |
| ALT-10 | 每个源 `.cpp` 建 adapter | 文件结构不是稳定领域 seam | DP-03 |
| ALT-11 | 公式 helper 全部公开 | 浅 module，调用方理解实现细节 | DP-03 |
| ALT-12 | ROS node 直接作为核心 module | topic/timer/parameter server 污染核心 | DP-03 |
| ALT-13 | 裸 NumPy 作为唯一核心接口 | DOF/unit/frame 错位不可防 | DP-04 |
| ALT-14 | 大量 optional 的万能 State | 浅接口、组合不可判定 | DP-04 |
| ALT-15 | 所有 module 每 `dt_sim` 调一次 | 改变多速率控制/波浪/actuator 语义 | DP-05 |
| ALT-16 | 保留 ROS wall timers | 非确定、不可 replay | DP-05 |
| ALT-17 | 只 reset 船位 | 离散状态/RNG 跨 episode 泄漏 | DP-06 |
| ALT-18 | stale 输入自动置零 | 把故障伪装平静环境 | DP-06 |
| ALT-19 | 全项目固定改 8-state | 破坏旧算法/tracking/evaluator | DP-07 |
| ALT-20 | roll/p 完全藏 model 内 | 不可 snapshot/RK stage 验证 | DP-07 |
| ALT-21 | 45m 源模型直接命名 Generic | 船型参数冒充领域规律 | DP-08 |
| ALT-22 | 巨型 model+大量 flags | 组合爆炸、非法配置 | DP-08 |
| ALT-23 | 只保留 total Wrench | 无法隔离/校准/去重 | DP-09 |
| ALT-24 | 缺 RAO/QTF 自动 inferred/mock | 静默降低物理可信度 | DP-09 |
| ALT-25 | Schema 通过即 validated | 格式正确不等于物理/船型正确 | DP-10 |
| ALT-26 | 系数硬编码并静默外推 | 无 provenance、超域伪可信 | DP-10 |
| ALT-27 | Source `x_next` 当 local RHS | Double integration | DP-11 |
| ALT-28 | PID/NDO/RNG 在 RK stage 更新 | 一 tick 更新四次 | DP-11 |
| ALT-29 | Plant 内速度/yaw clip 和 auto reset | 伪造物理稳定 | DP-12 |
| ALT-30 | 完全无 validity monitor | NaN/超域污染 | DP-12 |
| ALT-31 | Source loop 整体注册为 PID | 算法身份错误 | DP-13 |
| ALT-32 | PID/SMC/NDO 全做 flags | 不可独立验证/调参 | DP-13 |
| ALT-33 | `speed=0` 自动进入 DP | 任务语义错误、模式抖动 | DP-14 |
| ALT-34 | 一个 controller 支持所有 task | 欠驱动能力和状态耦合 | DP-14 |
| ALT-35 | 复制多层 clamp/decay/backcalc | 更新链不可解释 | DP-15 |
| ALT-36 | Fixed alpha；NaN 强制零 | dt 语义改变、故障隐藏 | DP-15 |
| ALT-37 | 只提供 ideal generalized load | 无 actuator feasibility | DP-16 |
| ALT-38 | 照搬 FCB 七执行器 allocator | 船型特化 | DP-16 |
| ALT-39 | 全量移植 6200+ 行 Guidance | 过拟合、不可维护 | DP-17 |
| ALT-40 | `advanced_los` + 上百 flags | 重建 configurable monolith | DP-17 |
| ALT-41 | Predicted trajectory 自动转 route | 无接受/连续/版本语义 | DP-18 |
| ALT-42 | Direct heading 与 route 同时发布 | 双 command authority | DP-18 |
| ALT-43 | Guidance/Controller 直接读取 truth | 现实不可得、结果虚高 | DP-19 |
| ALT-44 | NDO+FF+crab 默认全开 | 重复补偿、相互打架 | DP-19 |
| ALT-45 | 各 module 保留 yaw/sign flags | 错误层次被参数掩盖 | DP-20 |
| ALT-46 | 信注释自动猜 convention | 已发现 contract/code 冲突 | DP-20 |
| ALT-47 | 全局 singleton GNC/environment state | 船间污染 | DP-21 |
| ALT-48 | 全局顺序 RNG/cache | Ship order 改变结果 | DP-21 |
| ALT-49 | 有权限后省略 LICENSE/NOTICE | 分发和第三方归属含糊 | DP-22 |
| ALT-50 | 所有源码/资产直接并入主 wheel | 可选/专有依赖无法隔离 | DP-22 |
| ALT-51 | Current tests 直接证明 8/24 v2 | 版本不一致 | DP-23 |
| ALT-52 | 最终轨迹相似即 parity | 内部误译无法定位 | DP-23 |
| ALT-53 | 单一 end-to-end smoke | 不能证明具体层 | DP-24 |
| ALT-54 | 全局宽容差/调阈值求 PASS | 掩盖数值错误和坏设计 | DP-24 |
| ALT-55 | 单一 `verified=true` | 混淆软件/物理/COLAV/系统证据 | DP-25 |
| ALT-56 | A1 跑通即称船型水动力验证 | 真实 RAO/QTF/V3 数据缺失 | DP-25 |
| ALT-57 | 复制源巨型 YAML | 固化 FCB/历史门限 | DP-26 |
| ALT-58 | 首期建设动态插件发现市场 | 单一外部供应方，抽象过早 | DP-26 |
| ALT-59 | C++/pybind-first | 调试/ABI/构建成本先于性能证据 | DP-27 |
| ALT-60 | 为实时性丢 tick/动态改 dt | 方程随机器负载改变 | DP-27 |
| ALT-61 | 所有阈值参数化即通用 | 参数化补丁仍是补丁 | DP-28 |
| ALT-62 | 全删复杂行为不做消融 | 可能恢复真实失效 | DP-28 |
| ALT-63 | Modular stack 直接替换默认路径 | 旧算法/场景退化 | DP-29 |
| ALT-64 | 为共享代码先重构旧 stack | 无行为需求却改变浮点/时序 | DP-29 |
| ALT-65 | 纯 A：Explicit Typed Pipeline 直接暴露给调用方 | 调用面过大，Simulator/用户必须理解内部 pipeline | TD-01..TD-05 |
| ALT-66 | 纯 B：Deep ShipStack Facade 且无稳定内部 seams | 容易形成新的巨型 Ship/Guidance，内部归因困难 | TD-01..TD-05 |
| ALT-67 | 纯 C：全量 immutable StateBundle/dataflow | NumPy copy、schema、两阶段状态和 legacy adapter 成本过高 | TD-01..TD-05 |

### 0.8 技术规约注册表 [TS]

| ID | 类别 | 规约内容 | 单位/定义 | 来源 | 关联DP/接口 | 与现状差异 |
|----|------|----------|-----------|------|-------------|-----------|
| TS-01 | 坐标系 | 平面 world North-East | x=N,y=E,m | VR-20 | Typed state | 当前项目一致；源归档冲突 |
| TS-02 | 坐标系 | 3D world NED | z=down | VR-20 | Plant/adapter | 源归档需转换 |
| TS-03 | 坐标系 | Body x-forward/y-starboard/z-down | body | VR-20 | Plant/Actuator/load | Basis probe 必须 |
| TS-04 | 符号 | Heading 0 North、顺时针/right positive | rad | VR-20 | Navigation/Guidance | 核心禁 yaw_sign |
| TS-05 | 符号 | Roll starboard-down positive；r right-turn positive | rad,rad/s | VR-20 | 4DOF Plant | Source adapter characterization |
| TS-06 | 单位 | 核心全部 SI | m,s,kg,N,Nm,rad | [R7][R8] | 全部 | deg/kn 仅 adapter |
| TS-07 | 环境 | from/to 进入核心前转 world vector | m/s vector | VR-20 | Env adapter | 禁止猜方向 |
| TS-08 | 时序 | 单一 simulation-time authority | integer tick | VR-05 | Scheduler | 无 wall timer |
| TS-09 | 时序 | 固定 phase order，非到期 ZOH | profile-defined | VR-05/30 | Scheduler | 源异步显式化 |
| TS-10 | 时序 | 初始 characterization profile 50/10/2Hz | 0.02/0.1/0.5s | [R2–R5] | Rate profile | 非算法常数 |
| TS-11 | 数值 | Float64/finite/strict shape-layout | float64 | VR-04 | Typed values | 无 silent reshape |
| TS-12 | 状态 | Full PlantState + 3DOF Navigation projection | capability | VR-07 | Facade output | Roll/p 不私藏 |
| TS-13 | 数值 | Pure RHS + 唯一外部 fixed RK4 | derivative | VR-11 | Plant/Scheduler | 禁 double integration |
| TS-14 | 数值 | RK stage 不推进离散状态/RNG | due tick once | VR-11 | Scheduler | Stage forcing pure |
| TS-15 | 生命周期 | Per-ship/episode；reset 幂等；snapshot hash-bound | deterministic | VR-06/21 | Facade | 无 state leak |
| TS-16 | 随机 | Master seed 按 ship/episode/module 派生 | seed tree | VR-06 | Env/Sensor | Ship order independent |
| TS-17 | 错误 | Invalid/stale/nonfinite/out-domain 显式失败 | error code | VR-04/06/12 | Diagnostics | 无 silent fallback |
| TS-18 | Planner | DIRECT_REFERENCE/TRACKED_ROUTE 互斥 | union | VR-18 | PlannerOutput | Prediction 非 route |
| TS-19 | Control | Transit/PoseHold/ControlledStop/ManualLoad 显式 | task | VR-14 | Controller | speed=0 非 DP |
| TS-20 | PID | Measurement derivative、dt-filter、single AW、achieved feedback | discrete | VR-15 | marine_pid | 不复制历史多层规则 |
| TS-21 | 补偿 | Plant truth；GNC estimate；显式补偿默认互斥 | source/age | VR-19 | Env/GNC | 无 truth leakage |
| TS-22 | Actuator | ideal/resolved 双 profile，layout/rate 资产化 | profile | VR-16 | Allocator/Actuator | 无固定七执行器 |
| TS-23 | Asset | 四级 trust+provenance/hash/license/domain | metadata | VR-10 | Registry/Report | Mock 非 validated |
| TS-24 | 配置 | Legacy 不变；ship_modules opt-in；defaults<preset<override | config hash | VR-26/29 | Registry | 首期无 hot update |
| TS-25 | 兼容 | 未选 modular 不 import/check/execute 新路径 | isolation | VR-29 | Composition root | 无自动迁移 |
| TS-26 | 性能 | 不丢 tick/改 dt；profile 后 native | RTF/latency | VR-27 | Backend | Native 非默认 |
| TS-27 | 证据 | Source/config/test/asset/compiler/seed content-hash | SHA-256 | VR-23/24 | Fixture/Report | 禁跨版混用 |
| TS-28 | 接受 | G0–G10 独立，逐量 tolerance，deviation ledger | per quantity | VR-24 | Verification | 无单 smoke |
| TS-29 | 声明 | A1–A7；首阶段 A1–A3 | level | VR-25 | Report/UI | 不升级声明 |
| TS-30 | 通用性 | Behavior 五分类、证据卡、消融、跨船型门 | evidence card | VR-28 | Design/Acceptance | 参数化补丁非通用 |

---

## 参考文献

- [R1] `/Users/marine/Code/external_sources/L4-5_source_only_20260824_v2/{README_SOURCE_ONLY.md,SOURCE_MANIFEST.csv,SOURCE_STATS.json,VERIFICATION.json}`；183 manifest 文件本地复验 `missing=0, mismatch=0`。
- [R2] `/Users/marine/Code/external_sources/L4-5_source_only_20260824_v2/src/gnc/ship_control/{include/ship_control/ship_control_node.hpp,include/ship_control/control_math.hpp,src/ship_control_node.cpp}`；`ship_config.yaml:132-252`。
- [R3] `/Users/marine/Code/external_sources/L4-5_source_only_20260824_v2/src/simulation/ship_dynamics/{include/ship_dynamics/ship_dynamics_node.hpp,include/ship_dynamics/dynamics_contracts.hpp,src/ship_dynamics_node.cpp}`；`ship_config.yaml:257-383`。
- [R4] `/Users/marine/Code/external_sources/L4-5_source_only_20260824_v2/src/environment/env_engines/` pure load models、ROS nodes、asset manifests、benchmark；`sim_launch.py:128-209`。
- [R5] `/Users/marine/Code/external_sources/L4-5_source_only_20260824_v2/src/gnc/ship_guidance/{include/ship_guidance,src}`；`ship_config.yaml:384-742`。
- [R6] `/Users/marine/Code/external_sources/L4-5_source_only_20260824_v2/src/gnc/thrust_allocation/`；`ship_config.yaml:743-881`。
- [R7] `colav_simulator/core/{models.py:342-369,controllers.py:171-193,guidances.py:81-111,ship.py:470-658,integrators.py:17-39}`；`colav_simulator/simulator.py:373-432`。
- [R8] `docs/research/2026-08-28-ros2-cpp-gnc-port-industry-survey.md`，引用 ROS 2、pybind11、FMI、MSS、PythonVehicleSimulator 和原始论文一手来源。
- [R9] `/Users/marine/Code/external_sources/L4-5_source_only_20260824_v2/src/**/package.xml`：MIT、Apache-2.0、Proprietary、TODO 混合声明；导出内未找到 LICENSE/COPYING/NOTICE 文件。
- [R10] 2026-08-28 用户指令：集成不是完全照抄；必须审查不合理设计、过多约束和过强特化，以泛用性为本对话主旨。
- [R11] 2026-08-28 用户指令：保证原项目模块功能正常执行；新水动力、导引、控制应逐步提升，并像现有算法一样作为不同可选项提供。
- [R12] 2026-08-28 用户授权声明：对这些代码拥有全部权限，可以直接修改、开发和优化。
- [R13] 2026-08-28 用户授权声明：可使用 `ssh agx` 在 L4-5 对应目录及 `/home/mass/sango/` 父目录搜集测试、验证和运行证据。
- [R14] `/Users/marine/Code/external_sources/L4-5_evidence_20260828/SNAPSHOT_SCOPE.md` 与 `SHA256SUMS.txt`；1784 files，manifest digest `6b33f861f65e34bb2122847e666d02c92dfac5f39877b7cb35c604e35cd5c644`。
- [R15] 2026-08-28 remote hash comparison：2026-08-24 manifest 183 files vs current `/home/mass/sango/L4-5`，25 changed、1 missing。
- [R16] `/Users/marine/Code/external_sources/L4-5_evidence_20260828/core_tests/`：environment/dynamics/control/guidance/allocation tests。
- [R17] `/Users/marine/Code/external_sources/L4-5_evidence_20260828/baseline_archives/extracted_20260824/src/simulation/mock_scenarios/` hydrodynamics V&V contract/tests；V3 blocked，contract hash/convention 与 source-only v2 不完全一致。
- [R18] Evidence snapshot 中 PID handoff、H34/H39/H40/H70、D30 selection、current-contract reports/config/metrics。
- [R19] `/Users/marine/Code/external_sources/L4-5_evidence_20260828/code_quality_audit/L4-5_CPP_HPP源码质量审计与整理报告_20260824.md`。
- [R20] 2026-08-28 AGX top-level campaign directory inventory：220 total、133 `ilos*`、13 名称含 pid、55 H-series。
- [R21] `docs/research/2026-08-28-agx-l45-evidence-audit.md`。
- [R22] 2026-08-28 用户流程授权：Step4 剩余二十多个 DP 改为批量展示和分组确认。

---

## 演进日志(append-only · 时序 · 不可覆盖)

### Step1 · 行业调研·发现决策点  [2026-08-28]

- 模式判定：**重构**。目标项目已有 `IModel/IController/IGuidance/Ship` seam；外部源码已有完整 ROS2 实现，任务是审计、选择 seam、建立 adapter 和验证，不是从零发明 GNC。
- 本地副本：从 `agx:/home/mass/sango/L4-5_source_only_20260824_v2/` 拷贝到 `/Users/marine/Code/external_sources/L4-5_source_only_20260824_v2/`。隔离在仓库外，避免未明确许可源码被 Git 误收录。
- 完整性：rsync checksum dry-run 无差异；`SOURCE_MANIFEST.csv` 183 项逐文件 SHA-256 复验，`missing=0, mismatch=0`。本地/远端 manifest、verification、stats 三个文件 hash 一致。
- 源范围：13 ROS2 package、191 个本地文件；测试、mock_scenarios、validation、报告、原仓构建产物被导出流程排除。原 `/home/mass/sango/L4-5` 也无 Git 元数据。
- 关键事实：
  - 所谓“PID”实现实际叠加 PID/PD、SMC robust term、可选 NDO、增益调度、feedforward、anti-windup、模式切换和多项工程保护；正式 YAML 中多个 `ki=0`，launch 强制 `ndo.enable=false`。
  - plant 是 `eta=[x,y,roll,yaw]`、`nu=[u,v,p,r]` 的 4DOF，内部 RK4@50Hz；本项目公共 Ship 是 3DOF/6状态且外层 RK4。
  - 风、流、浪 engine 和 aggregator 存在；默认 launch 全关闭，`Hs=0`，aggregator 默认使用 wave drift 而非 raw first-order load。
  - 环境资产明确标为 mock/C 级，真实 RAO 缺失/D 级；benchmark 声明只做软件回归，不是船型水动力证书。
  - Guidance 主节点约 6246 行，包含 ILOS/ALOS、转弯、rejoin、DP、环境补偿等状态化行为；不是简单 LOS 函数。
  - 推力链包含 PGD/QP 分配、优先级降级、舵桨侧推和执行器速率/健康状态；绕过它会改变闭环对象。
- 行业 research：按用户要求使用 `/research`，未使用 NLM；对照纯 Python、C++/pybind11、ROS2 bridge、FMI/FMU，均保留为候选，未裁决。
- NLM 尝试记录：在用户改用 research 前，两次只读 fast query 因本机缺 `socksio` 失败；未安装依赖、未修改 NotebookLM。
- 新增决策点：DP-01..DP-27。
- 技术分解：TD-01..TD-05。
- Step1 内部确认门：**未通过，等待用户确认决策点覆盖是否完整。**

### Step2 · grilling 压力测试  [2026-08-28]

- Step1 用户确认：决策点与技术分解覆盖完整；允许进入 Step2。
- 当前决策点：DP-01 首批集成范围。
- 状态：DP-01 三视角结论待用户确认，尚未落盘裁决。
- 用户纠偏：原“kernel parity 优先”的表述仍过度围绕源行为；将主旨改为批判性重构与通用性。新增 SC-01、BL-08、DP-28；上一版 DP-01 三视角结论作废，未形成裁决。
- [grilling 记录·三视角] DP-01（用户确认）:
  - [专家] 完整审计相关链路，但按“领域不变量/船型参数/运行时 adapter/证据不足候选/拒绝特化”分类；不按 ROS package 搬运。[R10]
  - [新手] 把所有历史门限外置到 YAML 仍是可配置复杂单体，不代表通用 module。
  - [悲观] 盲目保留会固化偶然复杂度；过度抽象会删掉真实物理耦合；以来源、适用域和跨船型场景约束分类。
  - [机制C 默认最简版失效] “照抄公式+参数化阈值”保留 45m FCB 假设、历史修补和重复补偿，不能通过 SC-01。
  - [场景] SC-01：同一实现至少支持两组船型参数和多类环境，无船型名/场景名分支。
  - [盲区] BL-08：源导出缺测试/设计记录，门限物理依据与历史修补尚不可区分（高）。
  - 用户确认：采纳上述 Step2 结论；DP-01 转“调研中”，待 Step3/4 证据闭环与推荐裁决。
- 当前决策点：DP-02 运行架构。
- [grilling 记录·三视角] DP-02（用户确认）:
  - [专家] 先定义同步、无 ROS 的 Colav-native interface；Python/C++/ROS2/FMI 是 adapter，不让源运行时决定领域接口。[R8][R10]
  - [新手] Python-only 易语义漂移；pybind-only 会固化源设计；ROS2 bridge 适合系统联调，不适合作为第一数值路径。
  - [悲观] 错选主运行形态会分别导致数值漂移、ABI/偶然复杂度、异步非确定性或 FMU 黑盒调试困难。
  - [机制C 默认最简版失效] 给 ROS node 套 Python wrapper 会暴露 topic/timer/parameter server，形成浅 adapter。
  - [盲区] BL-01/BL-02/BL-06 仍影响 adapter 的可实施性。
  - 用户确认：采用“接口优先、Python 默认、C++/ROS2 外围可选、FMI 延后”。
  - 用户补充：效率与可调试性并重；必须设计保证代码迁移一致性的过程。新增 SC-02，关联 DP-23/DP-24。
- 当前决策点：DP-03 纯算法 kernel 的提取 seam。
- [grilling 记录·三视角] DP-03（用户确认）:
  - [专家] 不按 ROS package/源文件迁移；按环境载荷、plant、controller、allocator、guidance 的稳定计算职责形成深 module，ROS 留在 adapter。[R8][R10]
  - [新手] 删除 ROS include 后逐行翻译仍保留隐藏时钟、静态状态和 callback 顺序假设。
  - [悲观] seam 太粗会隐藏错误，太细会暴露公式细节形成浅接口；每个 module 只保留 configure/reset/evaluate-or-step/diagnostics 所需最小接口。
  - [机制C 默认最简版失效] C++→Python 逐行翻译会同时丢失异步语义并保留偶然代码结构，产生伪一致。
  - [场景] SC-02：源 C++ characterization harness 与 Python 在同一 kernel seam 做分项差分；泛化修改记录有意偏差。
  - [盲区] BL-02：原 tests/validation 缺失，characterization harness 的原始验收值待恢复。
  - 用户确认：采用 kernel seam 与“先证明迁移一致、再有记录地泛化”。
- 当前决策点：DP-04 Python 调用接口。
- [grilling 记录·三视角] DP-04（用户确认）:
  - [专家] kernel interface 使用显式领域值对象，包含 DOF/layout/version、单位、frame、生命周期和错误语义；旧数组接口由 adapter 承担。[R7][R8]
  - [新手] 裸数组无法防止 3DOF/4DOF 索引错位、degree/radian 和 body/world 混用。
  - [悲观] interface 太泛会形成 optional 字段集合，太死会锁死 3DOF；不支持的 capability 必须显式拒绝。
  - [机制C 默认最简版失效] 静默 reshape/截断会隐藏 roll/yaw/p/r 映射错误。
  - [盲区] DP-07 公共状态布局未定；本 DP 只冻结接口原则。
  - 用户确认：typed kernel interface；现有 `IModel/IController/IGuidance` 数组契约保留为兼容 adapter。
- 当前决策点：DP-05 多速率 scheduler 与仿真时钟。
- [grilling 记录·三视角] DP-05（用户确认）:
  - [专家] 由单一 simulation-time authority 驱动确定性多速率 scheduler；kernel 不读 wall clock、不建 timer。[R2][R3][R4][R5][R8]
  - [新手] 所有 module 每个 `dt_sim` 调一次会把 50Hz plant 降为常见的 2Hz，改变控制、波浪和 actuator 行为。
  - [悲观] ROS wall timer、浮点累计周期和未定义同 tick phase order 会造成不可复现状态错位。
  - [机制C 默认最简版失效] 全部共享一个大 `dt` 在直线短场景可运行，但转弯/波浪/饱和下失稳。
  - [盲区] 通用默认频率需 timestep convergence 与性能证据；源 50/10/2Hz 只作初始 characterization profile。
  - 用户确认：单一时钟、整数 tick/有理周期、固定 phase order、ZOH、plant substep；仿真加速不改变 `dt`。
  - [场景] 新增 SC-03，覆盖同 seed replay 与 reset 等价性。
- 当前决策点：DP-06 episode 生命周期、reset、seed、stale/failure。
- [grilling 记录·三视角] DP-06（用户确认）:
  - [专家] 每 ship/episode 独立 module 状态；configure immutable，reset 幂等，seed 由 master seed 确定派生。[R2][R3][R4][R8]
  - [新手] 只重置船位会遗留 PID/ILOS/NDO/filter/actuator/RNG/route 状态。
  - [悲观] 隐藏 static、wall timestamp、上一指令破坏 replay；缺输入静默置零会把故障伪装成平静环境。
  - [机制C 默认最简版失效] 仅 `state=initial_state`，同 seed 第二次运行仍产生不同 trace。
  - [场景] SC-03：新实例、reset、snapshot restore 三种路径逐 tick 等价。
  - [盲区] 源离散状态清单仍需通过 characterization harness 补全。
  - 用户确认：显式生命周期、可重放 snapshot、无静默 fallback。
- 当前决策点：DP-07 3DOF/4DOF 状态契约。
- [grilling 记录·三视角] DP-07（用户确认）:
  - [专家] 分离完整 physical truth `PlantState` 与稳定 `NavigationState`；plant capability 可为 3DOF/4DOF，COLAV 不被迫理解所有物理状态。[R3][R7][R8]
  - [新手] 直接扩展现有数组会改变索引含义并破坏算法、tracking、evaluator、历史数据。
  - [悲观] 隐藏 roll/p 会破坏 snapshot/RK4/reset；强制公共 4DOF 会污染现有生态；必须显式投影并声明信息损失。
  - [机制C 默认最简版失效] 模型私有保存 roll/p、外部只传 6 状态，完整物理状态不可重放。
  - [盲区] roll 是否进入控制/安全/UI 后续分别裁决；先作为扩展真值 trace。
  - 用户确认：capability-aware PlantState + 稳定 3DOF NavigationState，不立即修改旧数组。
  - 用户补充：旧模块必须正常执行；新 model/guidance/controller 以选项渐进加入。新增 SC-04、DP-29、[R11]。
- 当前决策点：DP-08 水动力方程保留范围与 module 结构。
- [grilling 记录·三视角] DP-08（用户确认）:
  - [专家] 保留质量/附加质量、Coriolis、阻尼、恢复力等物理结构和可验证不变量，不照搬 45m FCB 系数与运行保护。[R3][R10][R11]
  - [新手] 单一巨型模型加大量 enable flag 会产生组合爆炸和不可判定的合法配置。
  - [悲观] 过细拼装允许非物理组合；采用少量内部 module、一个深 `VesselPlant.derivative()` interface 和 capability compatibility。
  - [机制C 默认最简版失效] 把源 4DOF+FCB 参数整体命名 Generic 会把船型校准伪装成领域规律。
  - [场景] SC-01 跨船型；SC-04 旧模型不变、新模型 opt-in。
  - [盲区] 源 added-mass/damping/roll 参数缺 tank-test/CFD/sea-trial 证据。
  - 用户确认：保留旧模型；新增通用 3DOF/4DOF option；配置期物理不变量门；preset 不是新算法类。
- 当前决策点：DP-09 风浪流数据/载荷 seam 与 wave mode。
- [grilling 记录·三视角] DP-09（用户确认）:
  - [专家] 分离环境观测数据与船体载荷计算；风、流、wave first-order、mean drift 保留独立身份，total 仅为派生值。[R4][R8]
  - [新手] 单一 total Wrench 简单但不可隔离、校准、关闭或判断 double-count。
  - [悲观] water-relative damping 与完整 current load 可能重复；first-order 与 drift 混用会改变航迹/横摇语义。
  - [机制C 默认最简版失效] 所有环境源提前聚合，软件能跑但任何来源都不可独立验证。
  - [盲区] 真实 RAO/QTF 缺失；当前仅能做软件结构和 mock/inferred 验证。
  - 用户确认：分项载荷、显式 wave mode、current 去重、fixed seed、缺资产显式失败；旧 DisturbanceData 路径不变。
- 当前决策点：DP-10 水动力/环境资产可信度与适用域。
- [grilling 记录·三视角] DP-10（用户确认）:
  - [专家] 通用代码与船型资产分离；preset/系数/RAO/QTF 必须携带 provenance、适用域、uncertainty 和 allowed profile。[R4][R10][R11]
  - [新手] schema 可解析、数值有限不等于适用当前船型。
  - [悲观] 错船型资产、无界外推、单位/方向错误可产生貌似合理的错误轨迹。
  - [机制C 默认最简版失效] 任意 CSV/YAML 通过 schema 后标 validated，只验证格式不验证物理和船型。
  - [盲区] 真实 RAO/QTF、试验/CFD/海试数据及授权尚缺。
  - 用户确认：四级可信度；mock/inferred 身份进入 trace/UI/report；缺资产显式失败；旧模型参数不重解释。
- 当前决策点：DP-11 数值积分所有权与 RK stage 语义。
- [grilling 记录·三视角] DP-11（用户确认）:
  - [专家] plant 只提供无副作用 derivative；唯一 integrator 由 scheduler 拥有，离散 module 按各自 tick 更新一次。[R3][R7][R8]
  - [新手] source `x_next` 若作为 local derivative 再 RK4 会 double integration。
  - [悲观] RK stage 推进 RNG/PID/NDO/ILOS 会一拍更新四次；state-dependent load 整步常值又会损失准确性。
  - [机制C 默认最简版失效] `step(x,dt)->x_next` 包装为 `IModel.dynamics()`，量纲与轨迹错误。
  - [场景] SC-02/SC-03 加入单步 stage parity、dt/2 convergence、离散状态更新次数断言。
  - 用户确认：纯 RHS、ZOH control、stage-time deterministic forcing、fixed spectrum state；旧模型继续原 RK4。
- 当前决策点：DP-12 物理模型与运行保护的 seam。
- [grilling 记录·三视角] DP-12（用户确认）:
  - [专家] 分离物理方程、actuator 约束、model validity、数值健康和 simulation safety policy。[R3][R10]
  - [新手] clip/reset 防爆但会让错误模型伪装稳定。
  - [悲观] 完全无保护会 NaN 污染；外部 monitor fail-fast，不能反写 plant truth。
  - [机制C 默认最简版失效] 积分后 `clip(state)` 让轨迹脱离模型物理。
  - [场景] 极端输入、错误系数、大 dt、超有效域、NaN 必须显式失败并保存 trace。
  - 用户确认：actuator saturation 保留；超域/非有限/矩阵/积分失败显式终止；continue_degraded 仅显式实验配置；旧模型 bounds 不变。
- 当前决策点：DP-13 controller 算法身份与拆分。
- [grilling 记录·三视角] DP-13（用户确认）:
  - [专家] PID、SMC、NDO、gain schedule、行为 policy 必须有独立算法身份、参数和 diagnostics。[R2][R8][R10][R11]
  - [新手] 全部做 enable flags 无法判断真实控制律、独立调参或公平对比。
  - [悲观] NDO/feedforward/integral 可能重复补偿；无推导的 robust term 可能只是高增益 bang-bang；行为门限掩盖控制性能。
  - [机制C 默认最简版失效] 整体 `control_loop()` 命名 PID，算法身份与执行路径不符。
  - [盲区] SMC/NDO 推导、稳定性、调参和验证证据缺失。
  - 用户确认：`marine_pid` 先行；`marine_pid_ndo`/`integral_smc`/`scheduled_pid` 后续独立；MIMOPID/FLSC 不变；无静默替代。
- 当前决策点：DP-14 control task/mode 与切换。
- [grilling 记录·三视角] DP-14（用户确认）:
  - [专家] Transit/PoseHold/ControlledStop/ManualLoad 是显式 task；controller 声明 supported_tasks，上层 mode manager 选择。[R2][R10][R11]
  - [新手] `speed=0` 不等于 DP，可能是临时停车/等待/制动。
  - [悲观] 欠驱动船无法 pose hold；隐式切换和状态清零产生 mode chatter/control bump。
  - [机制C 默认最简版失效] 零速阈值触发 DP 并清积分，短暂零速命令造成跳变。
  - [盲区] 各 actuator layout 的 pose-hold capability 由 DP-16 闭环。
  - 用户确认：typed ControlTask、capability 配置门、Transit/PoseHold 独立 controller、显式 transition reason/sequence/state transfer；旧路径不变。
- 当前决策点：DP-15 `marine_pid` 离散更新与 anti-windup。
- [grilling 记录·三视角] DP-15（用户确认）:
  - [专家] 固定 validate→wrapped error→derivative/filter→integral candidate→raw+FF→limit→tracking anti-windup→diagnostics 的更新次序。[R2][R8][R10]
  - [新手] 多层 clamp/decay/back-calculation 会互相覆盖，积分状态不可解释。
  - [悲观] controller 本地 limit 与 allocator 能力不一致会继续 windup；固定 alpha 随 dt 改变实际滤波。
  - [机制C 默认最简版失效] 复制全部 anti-windup 和开关形成不可验证的 configurable PID。
  - [盲区] achieved_tau/saturation feedback 由 DP-16 闭环。
  - 用户确认：单一 tracking anti-windup、measurement derivative、dt-aware filter、deadband 默认关闭、NaN reject、参数 episode 冻结、P/I/D/FF/raw/applied trace；旧控制器不变。
- 当前决策点：DP-16 thrust allocation/actuator fidelity profile。
- [grilling 记录·三视角] DP-16（用户确认）:
  - [专家] Controller 请求 generalized load；allocator/actuator 决定实际可实现量，两种 fidelity profile 显式区分。[R3][R6][R10][R11]
  - [新手] 直驱适合控制/plant 调试，但不能代表舵效、侧推、速率与故障。
  - [悲观] 照搬 FCB 七执行器和 PGD/QP 固化船型；allocator/plant 双重 rate limit 会重复约束。
  - [机制C 默认最简版失效] 固定 `[t1,t2,t3,tb1,tb2,r1,r2]` 数组用于所有船型，映射静默错误。
  - [盲区] 真实 actuator layout/curve/rate/effectiveness/failure 资产缺失。
  - 用户确认：双 profile、数据驱动 layout、配置期 task capability、actuator dynamics 单一所有权、achieved_tau 反馈；旧广义力路径不变。
- 当前决策点：DP-17 Guidance 算法身份与通用功能集。
- [grilling 记录·三视角] DP-17（用户确认）:
  - [专家] Guidance option 代表明确数学算法；route progress/geometry、speed policy、terminal task 不塞进 LOS 类。[R5][R8][R10][R11]
  - [新手] 全量移植无法区分性能来自 ILOS 还是历史 rejoin/speed gate。
  - [悲观] 最简 LOS 可能在大 XTE/急转/横流失效；巨型 advanced_los 又过拟合不可解释。
  - [机制C 默认最简版失效] 上百开关的 `advanced_los` 重建可配置单体。
  - [盲区] 源门限依据、场景覆盖和失败回放缺失。
  - 用户确认：existing LOS/KTP 不变；新增独立 ILOS；ALOS 后续证据门；route/speed/terminal/env 拆分；无静默 fallback。
- 当前决策点：DP-18 COLAV plan→Guidance seam。
- [grilling 记录·三视角] DP-18（用户确认）:
  - [专家] 分离 planning/following；planner 声明 DIRECT_REFERENCE 或 TRACKED_ROUTE capability，Guidance 不重新判定 COLREG。[R5][R7][R10][R11]
  - [新手] MPC predicted trajectory 不自动等于连续、接受、可执行 route。
  - [悲观] 每拍换 route 重置 segment/integral/reference；direct heading 与 route 同时存在会双重控制权。
  - [机制C 默认最简版失效] 预测点直接转 waypoints，无 plan ID/revision/validity/handoff，Guidance 持续重置。
  - [盲区] 现有各 COLAV 是否能输出稳定 route 需逐算法审计。
  - 用户确认：旧算法 direct path 不变；tracked route 显式 opt-in；单 command authority；route 切换/失效/回归语义与 trace 明确；无静默 fallback。
- 当前决策点：DP-19 环境补偿所有权与去重。
- [grilling 记录·三视角] DP-19（用户确认）:
  - [专家] 分离 environment truth 与 observation/estimate；每个 compensation 声明算法身份、作用频带和输出项。[R2][R4][R5][R8][R10]
  - [新手] 多层都补偿同一扰动可能过补偿并互相追逐。
  - [悲观] Guidance crab/controller FF/NDO/integral 可能重复；读取仿真 truth 会制造现实不可得的完美预知。
  - [机制C 默认最简版失效] 所有 module 读取 total load 自行抵消，效果不可解释。
  - [盲区] 实际环境传感/估计能力、误差和频率待确认。
  - 用户确认：Plant truth 单独；GNC 默认不读 truth；god estimator 显式调试 option；allocator baseline 不补偿；NDO/直接 FF 默认互斥；组合需频带与消融证据。
- 当前决策点：DP-20 坐标/符号/单位规约。
- [grilling 记录·三视角] DP-20（用户确认）:
  - [专家] 核心单一 canonical convention，外部 WGS84/ROS/YAML/UI 在 adapter 转换；方向尽早转 world/body vector。[R2][R3][R4][R5][R7][R8]
  - [新手] sign 参数能临时修反向，但隐藏错误层次。
  - [悲观] heading/course、body/world、from/to 反向仍产生有限数值，NaN 检查无法发现。
  - [机制C 默认最简版失效] 每 module 各自 sign 开关，靠场景调到可用，换方向/船型再失效。
  - [盲区] 源注释/消息部分矛盾，需 basis-vector characterization。
  - 用户确认：North-East/NED、heading 0北顺时针、body y右舷、roll/r/Y/N 右向正、SI；核心禁止猜 frame 和 sign 调参，adapter 有完整往返测试。
- 当前决策点：DP-21 多船实例隔离与共享环境。
- [grilling 记录·三视角] DP-21（用户确认）:
  - [专家] 所有 GNC/plant 离散/连续状态 per-ship；仅 immutable config/assets 和 pure time-space environment field 可共享。[R2][R3][R4][R5][R7][R11]
  - [新手] 源全局 topic/node 直接搬入会冲突或共享控制状态。
  - [悲观] 共享 integral/index/RNG 产生船间污染；global RNG 使 ship list 顺序改变结果。
  - [机制C 默认最简版失效] 全局 EnvironmentEngine 保存当前船状态，循环时后船覆盖前船。
  - [场景] ship-order permutation、parallel/serial equality、same field/different heading、mixed old/new modules。
  - 用户确认：per-ship module stack；shared pure field；ship_id core identity；ROS namespace 仅 adapter；配置错误只拒绝对应 ship。
- 当前决策点：DP-22 license/授权/发布边界。
- [grilling 记录·三视角] DP-22（用户确认）:
  - [专家] 访问权不自动等于修改/分发权；源码进入仓库前需权利主体、license/notice 和第三方资产 provenance。[R9]
  - [新手] package.xml 混合 MIT/Apache/TODO/Proprietary，且缺完整 license text。
  - [悲观] 未授权源码进入 Git 历史后难以回收；数据资产许可另行核对。
  - [机制C 默认最简版失效] 仅凭 SSH 权限或 package.xml 标签直接复制。
  - [盲区] BL-01 原为高优先级授权盲区。
  - 用户确认 [R12]：对代码拥有全部权限，可直接修改、开发和优化。BL-01 闭环；实施阶段仍统一 LICENSE/NOTICE/provenance，外部副本继续隔离至选定代码正式迁入。
- 当前决策点：DP-23 源 baseline、tests/validation 和 characterization oracle。
- [grilling 记录·三视角] DP-23（用户确认）:
  - [专家] 以 content hash 冻结 baseline，恢复原 tests/validation 后仍需建立逐 kernel characterization fixtures。[R1][R8]
  - [新手] 最终轨迹无法定位环境、导数、积分、控制或 actuator 差异。
  - [悲观] 原测试可能固化场景补丁；活跃 AGX 工作区直接构建可能干扰运行。
  - [机制C 默认最简版失效] 单条相似轨迹当迁移证明，内部符号/状态/饱和已漂移。
  - [盲区] BL-02 授权已给但证据尚未采集；BL-03 以 Manifest baseline 取代缺失 Git commit。
  - 用户确认：baseline=`l45-source-20260824-v2`、manifest SHA；独立 evidence snapshot；隔离构建；原测试按 contract/characterization/calibration/scenario/smoke 分类；intentional deviation 单独记录。
  - 用户授权 [R13]：Step3 可通过 `ssh agx` 搜集目标及父目录证据；Step2 不提前执行搜集。
- 当前决策点：DP-24 分层验证架构和 acceptance gates。
- [grilling 记录·三视角] DP-24（用户确认）:
  - [专家] 迁移一致、物理正确、通用性、闭环、COLAV、actuator 和 ROS2/SIL 分 gate 报告。[R8][R10][R11]
  - [新手] 单条完整航线 smoke 无法定位失败或证明具体层正确。
  - [悲观] golden parity 固化坏设计；宽容差掩盖误译；用 intentional-deviation ledger 串联严格 characterization 与新 contract。
  - [机制C 默认最简版失效] end-to-end 能跑即宣称全部集成完成。
  - [场景] SC-01/02/03/04 全部映射到独立 gates。
  - 用户确认：G0–G10；逐量 abs+rel tolerance；stage parity+dt/2 convergence；无 fallback/场景分支/阈值作弊；focused 不冒充 full acceptance。
- 当前决策点：DP-25 接受等级和对外声明边界。
- [grilling 记录·三视角] DP-25（用户确认）:
  - [专家] 运行、迁移一致、通用仿真、COLAV、船型校准、ROS2/SIL/HIL、海试使用独立接受等级。[R1][R4][R8][R10][R11]
  - [新手] UI 可选/轨迹正常不等于物理、跨船型或系统接受。
  - [悲观] mock 参数和 clip 产生漂亮轨迹，统一 Completed 会污染论文和工程证据。
  - [机制C 默认最简版失效] 单一 `verified=true` 覆盖所有层级。
  - 用户确认：A1–A7；首阶段 A1→A2→A3；报告 module/fidelity/asset/hash/baseline/gates/deviations/domain；安全和系统层分报。
- 当前决策点：DP-26 module registry、配置 schema、参数版本与兼容。
- [grilling 记录·三视角] DP-26（用户确认）:
  - [专家] 分离 module identity、interface/implementation version、parameter schema、asset preset、capability compatibility；旧解析路径保留。[R2][R3][R4][R5][R7][R11]
  - [新手] 把源几百参数直接复制进 scenario 会暴露 FCB 历史复杂度。
  - [悲观] 4DOF/3DOF controller、PoseHold/underactuated、asset-based/missing asset 等组合只做字段校验仍会错误。
  - [机制C 默认最简版失效] `advanced=true` 和全开关 UI 无法追踪身份/能力/参数来源。
  - [场景] SC-04 旧 config regression；新配置冲突 INVALID_INPUT，合法缺依赖 DEPENDENCY_UNAVAILABLE，无 fallback。
  - 用户确认：显式 local registry；defaults<preset<scenario overrides；episode config 冻结；normalized snapshot/hash；热更新和动态市场延后。
- 当前决策点：DP-27 平台矩阵、性能和可选 native 加速。
- [grilling 记录·三视角] DP-27（用户确认）:
  - [专家] Python 默认优先调试；profiler 证明瓶颈后，相同 interface/fixtures 下新增 C++ adapter。[R8][R10][R11]
  - [新手] 全 pybind 增加 ABI/GIL/ownership/build 成本，降低可调试性。
  - [悲观] wave×direction×RK stages×ships 成本高；共享 mutable cache/跳 tick 会破坏确定性。
  - [机制C 默认最简版失效] 为实时因子按负载丢 tick，使方程随机器变化。
  - [盲区] 目标 ship count/RTF 未定，先建立 benchmark profiles。
  - 用户确认：Python-first、profile-first、优化序列、parallel/serial parity、native optional wheel、缺 native 显式选择 Python 而非运行中 fallback。
- 当前决策点：DP-28 通用性分类门。
- [grilling 记录·三视角] DP-28（用户确认）:
  - [专家] 每项能力按 source/purpose/state/basis/assumptions/interactions/fixtures/ablation/cross-vessel 建证据卡，不能按文件整体采纳/否定。[R2][R3][R4][R5][R6][R10]
  - [新手] magic number 外置 YAML 不等于通用，仍可能是参数化场景补丁。
  - [悲观] 直接删除会复发真实问题，全部保留会固化过拟合；需要 characterization 和消融。
  - [机制C 默认最简版失效] 按复杂度删代码或参数化所有数字后宣称泛化。
  - [盲区] BL-08：tests/design history 未恢复，门限来源待 Step3 搜集。
  - 用户确认：五分类、证据卡、跨船型/环境/路线/速度测试、无船型/场景分支、失败显式、保留/删除均有 deviation evidence。
- 当前决策点：DP-29 向后兼容和渐进发布。
- [grilling 记录·三视角] DP-29（用户确认）:
  - [专家] 新能力平行 opt-in；未选择新 stack 时不执行新 scheduler/adapter/asset/dependency 路径。[R7][R11]
  - [新手] 为复用先重构旧 `Ship.forward()`/model/guidance 仍会改变浮点顺序、时序和默认值。
  - [悲观] 全局换 scheduler 会改变旧轨迹；UI 自动迁移会让用户无意运行新模块。
  - [机制C 默认最简版失效] 默认路径经过 modular stack，再用 flag-off 模拟旧行为，仍不是真隔离。
  - [场景] SC-04：旧配置身份、链路、结果和错误语义不变；new/old stack 可同进程混用。
  - 用户确认：legacy 默认冻结；modular opt-in；新 registry 只读新配置段；无静默 fallback；按 interface→env→plant→PID→ILOS→actuator→route→ROS 小切片发布。
- Step2 完成检查：
  - DP-01..DP-29 均已逐点展示三视角、默认最简版失效和盲区，并获用户确认。
  - 技术分解 TD-01..TD-05 的子模块均已覆盖。
  - 场景 SC-01..SC-04 已登记；后续 Step3 研究会补充实验边界。
  - 当前未闭环高优先级：BL-02（测试/验证证据待采集）、BL-08（历史门限依据待分类）；BL-01/03/04/05/06/07 已闭环。
  - Step2 内部确认门：通过。
  - Step3 步骤间门：等待用户明确授权，未自动进入。

### Step3 · 自主深度调研  [2026-08-28]

- 用户确认 Step2 完成并授权进入 Step3。
- 调研方法：按用户要求使用 `/research` 与 AGX 一手源码/测试/设计/运行证据，不使用 NLM。
- 当前目标：BL-02（恢复 tests/validation/trace）与 BL-08（区分物理依据、船型参数、历史修补）。
- 状态：证据采集中；未经用户确认，不把任何 BL 标为已闭环，不进入 Step4。
- Evidence snapshot 完成：仓库外 1784 个受控文件；rsync diff=0；补充 8/24 与 8/25 hash-verified source archives。
- 新证据 R14..R21 已登记。
- BL-02 证据结论（待用户确认）：现有材料不能直接成为 source-only v2 完整 oracle，但足以构建分层 characterization harness；environment 和数学 property 已有可复用 fixtures。
- BL-08 证据结论（待用户确认）：可在 family level 区分 DomainInvariant/VesselParameter/RuntimeAdapter/ExperimentalCandidate/Reject；当前 Guidance/Control 复杂度高度受历史 candidate tuning 影响，不应整体采纳。
- 新暴露冲突：
  - current tests/current formal 与 source-only v2 不同版；
  - archived V&V contract 的 body/yaw convention 与当前消息/代码描述冲突；
  - 部分标题/selection 与 machine FAIL/NOT_PROMOTED 状态并存；
  - 221 tests pass 的质量审计不能当作 v2 acceptance proof。
- Step3 内部确认门：未通过；等待用户逐盲区确认上述证据是否回答问题。
- 用户确认：R14..R21 已回答 BL-02/BL-08；两项标为已闭环。
- Step3 内部确认门：通过。每个高优先级 BL 有证据、三类置信度和适用性评估。
- Step3 步骤间门：通过；允许进入 Step4。

### Step4 · 汇总分析·推荐方案  [2026-08-28]

- 当前决策点：DP-01 审计范围与首批重构范围。
- 状态：推荐待用户确认；尚未写入 VR/ALT final。
- [推荐裁决] DP-01 → VR-01（用户确认）:
  - 推荐：证据最强的 env/plant 先行，完整 GNC 分片递进。
  - 风险：中；coordinate/asset/source drift 由 characterization 和 physical gates 控制。
  - 失效边界：首切片不含 Controller/Guidance，不得声明 GNC closed loop。
  - 验证：G0–G4、G6 legacy regression、两组 vessel preset contract。
  - 弃用：ALT-01..ALT-04。
- 当前决策点：DP-02 运行架构推荐。
- [推荐裁决] DP-02 → VR-02（用户确认）:
  - 推荐：Python 默认；C++ oracle/可选加速；ROS2 外围；FMI 延后。
  - 风险：中；G3 fixture/stage/state parity 控制 Python 误译。
  - 失效边界：只有 benchmark 证实 Python 性能不足才新增 C++ implementation；无运行中 fallback。
  - 弃用：ALT-05..ALT-08。
- 当前决策点：DP-03 kernel seam 与 module 划分。
- [推荐裁决] DP-03 → VR-03（用户确认）:
  - 推荐：EnvironmentField/LoadModel、VesselPlant、MotionController、PathGuidance、ThrustAllocator、ActuatorModel 形成深 module。
  - 风险：中；Controller/Guidance 隐藏状态通过 characterization 控制。
  - 失效边界：interface 暴露 ROS/历史 flags/大量 helper 即停止回审。
  - 弃用：ALT-09..ALT-12。
- 用户流程授权 [R22]：Step4 后续按批次展示；每批统一确认后写入 VR/ALT。
- 当前批次：DP-04..DP-10。
- [批量推荐裁决] DP-04..DP-10 → VR-04..VR-10（用户批量确认）:
  - 采纳：typed interface、deterministic scheduler、explicit lifecycle、dual state、generic 3/4DOF plant、environment/load separation、four-tier assets。
  - 风险：由低中到中高；分别通过 contract/replay/projection/physics/dedup/asset gates 验证。
  - 弃用：ALT-13..ALT-26。
- 当前批次：DP-11..DP-17。
- [批量推荐裁决] DP-11..DP-17 → VR-11..VR-17（用户批量确认）:
  - 采纳：纯 RHS、外置 validity、纯 PID、typed tasks、单 anti-windup、双 actuator profile、干净 ILOS。
  - 风险：DP-16/17 高，其余中低至中高；由 stage/trace/capability/ablation/cross-vessel gates 控制。
  - 弃用：ALT-27..ALT-40。
- 当前批次：DP-18..DP-24。
- [批量推荐裁决] DP-18..DP-24 → VR-18..VR-24（用户批量确认）:
  - 采纳：双 planner capability、补偿去重、canonical convention、per-ship、授权/provenance、versioned oracle、G0–G10。
  - 风险：DP-19/20/23 高，分别由 ablation/basis probe/version bundle 控制。
  - 弃用：ALT-41..ALT-54。
- 当前批次：DP-25..DP-29。
- [批量推荐裁决] DP-25..DP-29 → VR-25..VR-29（用户批量确认）:
  - 采纳：A1–A7、opt-in registry、Python/profile-first、五分类通用性、legacy/modular 双路径。
  - 风险：DP-28 中高，其余低到中；由 evidence cards、config/legacy/performance gates 控制。
  - 弃用：ALT-55..ALT-64。
- Step4 完成检查：
  - DP-01..DP-29 全部有用户确认的 VR-01..VR-29。
  - ALT-01..ALT-64 已记录且有弃用理由。
  - TD-01..TD-05 所有分解子模块均已综合，无 `DECOMPOSITION_INCOMPLETE`。
  - 每个推荐均含证据、风险、失效边界和验证需求。
  - Step4 内部确认门：通过。
- Step5 步骤间门：等待用户明确授权，未自动进入。

### Step5 · DESIGN-IT-TWICE  [2026-08-28]

- 用户授权进入 Step5。
- 拟对比对象：覆盖 TD-01..TD-05 的完整 modular GNC system interface，而非逐个低层 DP 重复设计。
- 拟并行方案：
  - A：Explicit Typed Pipeline（scheduler 显式组合 6 个 module）。
  - B：Deep ShipStack Facade（调用方只见单一 per-ship facade，内部插件化）。
  - C：Functional State Transition（immutable state bundle + pure systems/dataflow）。
- 拟直接沿用 Step4、不过度重复对比的硬约束：asset trust、canonical convention、rights/provenance、A1–A7、legacy default/modular opt-in。
- 状态：等待用户确认对比范围及直接沿用项；尚未 dispatch 方案 agent。
- 用户确认：采用 A/B/C 三套完整系统 interface 对比；DP-10/20/22/25/29 判定为低风险硬约束，直接沿用 Step4，不重复设计。
- 状态：方案 agent 并行设计中；尚未裁决。
- A/B/C 方案 agent 完成：
  - A Explicit Typed Pipeline：模块透明/归因强/可测性高，但外部 interface 大，实现风险高，推荐度 4/5。
  - B Deep ShipStack Facade：调用面最小/深度高，但若无 private seams 会重演巨型类，推荐度 4/5。
  - C Functional State Transition：replay/differential/parallel 最强，但 immutable bundle 与 legacy 成本最高，推荐度 3/5。
- [DESIGN-IT-TWICE 裁决] VR-30（用户确认）:
  - 采纳综合方案 D：外部 `ModularShipStack.reset/step/snapshot` deep facade；内部 6 个 typed module + deterministic scheduler 显式组合；immutable input/output/snapshot、atomic tick、pure RHS，但允许 module 私有高效 mutable state。
  - 方案 A 只作为内部 composition 形态，不作为外部 interface。
  - 方案 B 只作为外部 facade；禁止把领域算法直接堆进 facade，private seams 必须稳定可测。
  - 方案 C 只采纳 immutable boundaries、atomic commit、snapshot/replay；不采用全量 immutable public StateBundle。
  - 风险：中高；低于纯 A/B/C，主要受 scheduler/private-state snapshot/legacy adapter 控制。
  - 可测性：facade contract、internal module、scheduler phase、RK stages、snapshot/replay 分层验证。
  - 弃用：ALT-65..ALT-67。
- Step5 完成检查：
  - 关键整体技术 TD-01..TD-05 已有 3 个完整自洽竞争方案和 1 个用户确认综合方案。
  - 三方案均覆盖来源、工程验证、技术分解、失效边界、风险、可测性、推荐度七维。
  - 用户确认 DP-10/20/22/25/29 为低风险硬约束，直接沿用 Step4。
  - Step5 内部确认门：通过。
- Step6 步骤间门：等待用户明确授权，未自动进入。

### Step6 · 术语+技术规约+方案包  [2026-08-28]

- 用户授权进入 Step6。
- 目标文件：`docs/superpowers/specs/2026-08-28-agx-l45-gnc-integration-solution-pack.md`。
- 状态：方案包装配中；未经用户明确“接受”，不标记“已交付 to-spec”，不调用 to-spec。
- 方案包已生成：`docs/superpowers/specs/2026-08-28-agx-l45-gnc-integration-solution-pack.md`。
- 完整性：术语表、TS-01..TS-30、A/B/C/D 决策卡、R1..R22 证据矩阵、TD-01..TD-05、ALT-01..ALT-67、SC-01..SC-09、G0..G10、A1..A7、已知冲突/外部数据缺口八组件齐全。
- 状态：等待用户明确“接受”；尚未将 TS/SC 标 final，尚未标记“已交付 to-spec”，尚未调用 to-spec。
- 用户明确要求完成 Step6，并调用 `to-spec` 后生成 `handoff`；视为方案包接受。
- TS-01..TS-30 与 SC-05..SC-09 已写入注册表并固化。
- Step6 内部确认门：通过；方案包八组件齐，技术规约无未定项，DECOMPOSITION_INCOMPLETE=无。
- 状态：to-spec 进行中；完成设计文档与 issue 发布后再标“已交付 to-spec”。
- `to-spec` 设计文档已生成：`docs/superpowers/specs/2026-08-28-agx-l45-gnc-integration-design.md`。
- GitHub Issue 已发布：`https://github.com/marinehdk/colav-simulator/issues/41`，标签 `ready-for-agent` 已验证。
- Step6 状态：已完成并交付 to-spec。未进入实现；下一步应在新对话评价方案，之后按需 `to-tickets` 分解。

### 独立方案评审 · 修订落盘  [2026-08-31]

- 模式：新会话独立评审（ZCode），用户指定"航线避碰算法设计+工程实施高级工程师"双视角，对照当前代码库核查已接受设计。
- 代码核验：[R7] 全部属实，补充行级证据：
  - `IModel.dynamics(xs,u,w)` 6-state/3-input 数组契约（models.py:342）。
  - legacy RHS 非纯且隐式 clip：Viknes 原地 sat 输入（models.py:544）、KinematicCSOG 原地 sat 状态（models.py:444）、`erk4_integration_step` 接收 bounds 在积分层截断（ship.py:650→integrators.py:17）——VR-11/12 针对性成立。
  - 船型分支污染：FLSC 内 `model_params.name=="Viknes"/"R/V Gunnerus"` 分支（controllers.py:525）+ Viknes 专用 low-speed 参数组（controllers.py:428）——ALT-61 现实印证。
  - 单速率执行链：`Simulator.step` 每船 plan→forward（simulator.py:373-438），controller 每 sim dt 一次（ship.py:648）——TS-08/09 必要性成立。
  - truth 泄漏现状：plan(w=disturbance_data)（simulator.py:413）。
  - DP-18 对齐：rolling_plan 已有 accepted/revision_reason/expiry/recovery 生命周期（rolling_plan.py:124-172）。
- 评审结论：方案 D 体系成立；VR-01..30、TS-01..30、ALT、G0–G10、A1–A7 无需回炉 design-grounding；发现规格覆盖缺口 P1×4、P2×6、P3×4，均为覆盖缺口而非裁决错误。
- 用户确认（2026-08-31）：接受评审结论；授权落盘修订（RA-01..RA-14 进 spec）；明确不实现代码、不建 tickets、不动无关 dirty 文件。
- 修订落盘：
  - spec `2026-08-28-agx-l45-gnc-integration-design.md` 新增 binding "Review Amendments (2026-08-31)" 节（RA-01..RA-14）+ 修订实施顺序（slice 1 = typed values+facade+`ModularShipAdapter(IShip)`+`CommandInput`+配置节+registry v1+G6 baseline harness+失败策略映射；plant slice 后强制性能检查点）。
  - solution pack 冻结不动（历史记录性质）；RA 体系不修改任何已有 VR/TS 语义。
  - Issue #41 附评审修订评论。
- 未做：实现代码、tickets、Git 提交、worktree/branch 创建（留给执行会话，配置在 handoff）。
- 执行前置事实：main@8968f31 ahead origin/main 308；主 checkout 存在无关 dirty（decision-replay、COLAV core、slide-deck 删除）；RA-04 要求 pin commit 前先由用户裁决 dirty 工作去留。
